# -*- coding: utf-8 -*-
"""中秋批次 12 个 kit 的共用库。

每个 ``mod-tools/wf_midautumn_kit_<key>.py`` 只写「这个角色是什么」；行怎么装、怎么过闸门、
怎么写回执，全在这里。所有函数都是纯函数或只写候选包，**不碰 live store / assets / .cdn**。

核心纪律（裁决 §6 / 记忆卡 wf-dsl-row-assembly-discipline）：
行一律「官方 donor 行 + 逐格改」——:func:`donor_row` 取官方基线的整行，:func:`apply_cells`
按列号改；每行过 :func:`row_problems`（``wf_client_legality`` 三件套）与 :func:`describe`
（``wf_describe`` 回读，面板上真正会显示的中文）。面板文案另过 :func:`panel_problems`。

API 速查::

    donor_row(ctx, table, key, index=0, source="official") -> list[str]
    apply_cells(row, {列号: 值}, ncols=None)               -> list[str]
    build_row(ctx, table, donor, cells, ...)               -> (row, evidence)
    row_problems(kind, row, element=None)                  -> {检查名: [问题]}
    describe(kind, row)                                    -> 面板中文
    panel_problems(text)                                   -> [问题]
    unique_id(spec, n) / unique_row(ctx, spec, n, donor, cells)
    voice_route(code, route) / switched_action_rows(ctx)
    install_staged_assets(ctx)                             -> 装 B/pixel/<key>/install.json
    png_transform_from_lut(path)                           -> clone_effect_family 的 png_transform
    report(ctx, ...)                                       -> 写 evidence/kit-report.json（带指纹）
"""
from __future__ import annotations

import colorsys
import hashlib
import json
import re
import sys
import zlib
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    pass  # Imports resolve from this checkout/package, not external source copies.

import wf_client_legality as L  # noqa: E402
import wf_midautumn_specs as MS  # noqa: E402

ABILITY = "master/ability/ability.orderedmap"
LEADER = "master/ability/leader_ability.orderedmap"
UNIQUE = MS.UNIQUE_CONDITION_LOGICAL
ACTION = "master/skill/action_skill.orderedmap"
SWITCHED = "master/skill/switched_action_skill.orderedmap"
CAS = "master/string/custom_ability_string.orderedmap"
CHARACTER = "master/character/character.orderedmap"

ABILITY_NCOLS = 126
LEADER_NCOLS = 124
UNIQUE_NCOLS = 15

READY = "ready-for-review"
DRAFT = "draft"

# 「character/<一个完整路径段>/」——带两边的斜杠，前缀型 code 不会误伤。
_CHARACTER_SEGMENT = re.compile(rb"character/([A-Za-z0-9_]+)/")


class KitError(RuntimeError):
    pass


# ---------------------------------------------------------------- 面板文案规则

# 裁决 §3 + 记忆卡 wf-no-hplow-text-discipline / wf-leader-override-text-rules。
FORBIDDEN_PANEL_WORDS = (
    "自身为队长时",          # desc_override 禁语（队长技面板已自带标题）
    "觉醒后",                # 「(觉醒后X%)」两列写法禁用
    "生命值100%以下", "生命值 100%以下", "HP100%以下", "HP 100%以下",   # 恒真条件文本
    "null", "(None)",        # 组列空串读成 null 时的漏网文本
    "无上限", "无限叠加", "不设上限", "可无限",                          # 无上限就写到效果为止
)
# 能力里的「技能强化」条目不写数字与时间（裁决 §3）。
# 705 = 切换技能旗号 3（2026-09-27 平衡第三批：特克托队长专用撤封顶开关，能力 1399931#2）。
SKILL_FLAG_KINDS = ("536", "704", "705")


def panel_problems(text: str, *, skill_flag: bool = False) -> list[str]:
    """面板文案规则检查。``skill_flag=True``：这是「技能强化」条目，不许出现数字与时间。"""
    if not isinstance(text, str):
        return ["panel text is not a string"]
    problems = [f"panel text contains forbidden word {word!r}" for word in FORBIDDEN_PANEL_WORDS
                if word in text]
    if skill_flag:
        if any(ch.isdigit() for ch in text):
            problems.append("skill-flag panel entry must not carry numbers")
        for unit in ("秒", "％", "%"):
            if unit in text:
                problems.append(f"skill-flag panel entry must not carry {unit!r}")
    return problems


def check_panel(text: str, *, skill_flag: bool = False, label: str = "") -> str:
    problems = panel_problems(text, skill_flag=skill_flag)
    if problems:
        raise KitError(f"panel text rejected {label or text!r}: {problems}")
    return text


# ---------------------------------------------------------------- 行装配

def _rows(ctx, table: str, source: str) -> dict[str, str]:
    if source == "official":
        return ctx.official_flat(table)
    if source == "package":
        return ctx.pkg_flat(table)
    if source in ("live", "store"):
        return ctx.live_flat(table)
    if source == "template":
        return ctx.template_flat(table)
    raise KitError(f"unknown donor source {source!r}")


def donor_row(ctx, table: str, key: str, index: int = 0, *, source: str = "official") -> list[str]:
    """官方 donor 行（默认取 ``.cdn/cn`` 官方归档，不取 store）。``key`` 支持 ``"2110201#1"``。"""
    if "#" in key:
        key, _, suffix = key.partition("#")
        index = int(suffix)
    rows = _rows(ctx, table, source)
    if key not in rows:
        raise KitError(f"donor {key} missing from {source} {table}")
    lines = ctx.csv_split(rows[key])
    if not 0 <= index < len(lines):
        raise KitError(f"donor {key} has {len(lines)} records; index {index} out of range")
    return list(lines[index])


def apply_cells(row: Sequence[str], cells: Mapping[Any, Any] | None,
                ncols: int | None = None) -> list[str]:
    """donor 行 + 逐格改。``cells`` 的键是列号（int 或数字字符串），值一律转成字符串。

    行短于目标列数时补空串；``ncols`` 给定时结果必须恰好这么长（词条 126 / 队长 124）。
    """
    out = list(row)
    target = ncols if ncols is not None else len(out)
    for col, value in sorted((int(k), v) for k, v in dict(cells or {}).items()):
        if col < 0:
            raise KitError(f"negative column {col}")
        if col >= len(out):
            out.extend([""] * (col + 1 - len(out)))
        out[col] = "" if value is None else str(value)
    if len(out) < target:
        out.extend([""] * (target - len(out)))
    if ncols is not None and len(out) != ncols:
        raise KitError(f"row has {len(out)} columns, expected {ncols}")
    return out


def row_problems(kind: str, row: Sequence[str], element: int | None = None) -> dict[str, list[str]]:
    """逐行 ``wf_client_legality``：合法性 + 声明块字段 + （词条）元素列。"""
    row = list(row)
    problems = {"client_legality": L.client_legality_problems(kind, row),
                "declared_block_fields": L.declared_block_field_problems(kind, row)}
    if kind == "ability" and element is not None:
        problems["element_columns"] = L.ability_element_column_problems(kind, row, element)
    return {name: value for name, value in problems.items() if value}


def capabilities(kind: str, row: Sequence[str]) -> list[str]:
    return L.required_client_capabilities(kind, list(row))


def describe(kind: str, row: Sequence[str]) -> str:
    """``wf_describe`` 渲染回读：面板上真正会显示的中文。"""
    import wf_describe
    return wf_describe.describe_rows([list(row)], kind)[0]


def build_row(ctx, kind: str, donor: str, cells: Mapping[Any, Any] | None = None, *,
              table: str | None = None, source: str = "official", element: int | None = None,
              expect_describe: str | None = None, label: str = "") -> tuple[list[str], dict[str, Any]]:
    """donor + 逐格改 + 合法性 + describe 回读，一步到位；任何问题直接抛错。

    ``kind`` = ``"ability"`` / ``"leader_ability"``；``donor`` 可写 ``"<键>"`` 或 ``"<键>#<记录号>"``。
    ``expect_describe`` 给了就逐字核对（设计稿登记的面板预期文案 ⇒ 行漂移/描述器漂移都会被抓）。
    """
    if kind not in ("ability", "leader_ability"):
        raise KitError(f"build_row supports ability/leader_ability only, got {kind!r}")
    table = table or (ABILITY if kind == "ability" else LEADER)
    ncols = ABILITY_NCOLS if kind == "ability" else LEADER_NCOLS
    row = apply_cells(donor_row(ctx, table, donor, source=source), cells, ncols)
    problems = row_problems(kind, row, element)
    if problems:
        raise KitError(f"{label or donor}: client legality rejected the row: {problems}")
    rendered = describe(kind, row)
    if expect_describe is not None and rendered != expect_describe:
        raise KitError(f"{label or donor}: wf_describe drift\n  got    {rendered!r}\n  expect {expect_describe!r}")
    return row, {"label": label or donor, "kind": kind, "donor": donor, "cells": dict(cells or {}),
                 "describe": rendered, "capabilities": capabilities(kind, row)}


def check_ability_key(rows: Sequence[Sequence[str]], key: str, code: str, slot: int) -> None:
    """一键内多记录的硬约束：c0 = ``<code>_<slot>``，c1（主位限制）与 c2（雕像组）全键一致。"""
    if not rows:
        raise KitError(f"ability {key} has no records")
    for row in rows:
        if row[0] != f"{code}_{slot}":
            raise KitError(f"ability {key}: c0 {row[0]!r} != {code}_{slot}")
    if len({r[1] for r in rows}) != 1 or len({r[2] for r in rows}) != 1:
        raise KitError(f"ability {key}: mixed c1/c2 {[(r[1], r[2]) for r in rows]}")
    if rows[0][2] and rows[0][2] not in L.ABILITY_STATUE_GROUPS:
        raise KitError(f"ability {key}: unknown statue group {rows[0][2]!r}")


# ---------------------------------------------------------------- 固有状态

def unique_id(spec, n: int) -> str:
    """固有状态 ID：8 位 ``cid*100+n``（裁决 §1；7 位撞过基诺维 1699901/02）。"""
    return MS.unique_condition_id(spec.cid, n)


def unique_row(ctx, spec, n: int, donor: str, cells: Mapping[Any, Any] | None = None, *,
               name: str | None = None, icon: str | None = None) -> tuple[str, list[str]]:
    """官方 unique_condition donor + 逐格改。

    c4（累计上限）写 ``(None)`` = 上限 1，会把 during 134 / vlv 成长全部弄死
    （记忆卡 wf-unique-cap-none-trap）；无上限的官方写法是 99。
    """
    key = unique_id(spec, n)
    row = apply_cells(donor_row(ctx, UNIQUE, donor), cells, UNIQUE_NCOLS)
    if name is not None:
        row[1] = name
    if icon is not None:
        row[2] = icon
    if len(row) != UNIQUE_NCOLS:
        raise KitError(f"unique_condition {key} has {len(row)} columns, expected {UNIQUE_NCOLS}")
    if row[4] in ("", "(None)"):
        raise KitError(f"unique_condition {key}: c4 cap {row[4]!r} means cap=1; 无上限写 99")
    if not row[0] or not row[1]:
        raise KitError(f"unique_condition {key}: c0/c1 must be non-empty, got {row[:2]}")
    check_panel(row[1], label=f"unique_condition {key} name")
    return key, row


def write_unique(ctx, spec, entries: Mapping[str, Sequence[str]]) -> list[str]:
    """写固有状态行；键必须已在 ``SPEC["extra_keys"]`` 里声明过（占用断言才覆盖得到）。"""
    declared = set(spec.extra_keys.get(UNIQUE, ()))
    missing = [key for key in entries if key not in declared]
    if missing:
        raise KitError(f"unique_condition keys not declared in SPEC['extra_keys']: {missing}")
    return ctx.write_flat(UNIQUE, {key: [list(row)] for key, row in entries.items()})


# ---------------------------------------------------------------- 语音路由

def voice_route(code: str, route: Any) -> list[str]:
    """character c9–c16 八列（kind 0 HpHigh / 1 ConditionExist / 3 ChangeSkillFlag）。"""
    import wf_seasonal7_voice as V
    return V.normalize_route(route, code)


def switch_key(code: str) -> str:
    import wf_seasonal7_voice as V
    return V.switch_key(code)


def switched_action_rows(ctx) -> dict[str, list[str]]:
    """从包内 action_skill 行派生 switched_action_skill 的两条内层行（c7–c23）。"""
    import wf_seasonal7_voice as V
    rows = {level: list(cells) for level, cells in ctx.pkg_nested(ctx.spec.code, ACTION).items()}
    return V.switched_rows(rows)


def write_voice_ready(ctx) -> dict[str, Any]:
    """写 ``<code>_voice_ready`` 的 switched_action_skill 行（matched_skill_ready 的路由目标）。"""
    spec = ctx.spec
    key = switch_key(spec.code)
    declared = set(spec.extra_keys.get(SWITCHED, ()))
    if key not in declared:
        raise KitError(f"switched_action_skill key {key} not declared in SPEC['extra_keys']")
    rows = switched_action_rows(ctx)
    ctx.write_nested(SWITCHED, key, {level: [cells] for level, cells in rows.items()},
                     replace_inner=True)
    return {"key": key, "levels": sorted(rows)}


# ---------------------------------------------------------------- 像素/特效产物装包

def pixel_dir(ctx) -> Path:
    return ctx.pack.batch_dir / "pixel" / ctx.spec.key


def _logical_character(logical: str) -> str | None:
    """``character/<code>/…`` 里的 ``<code>``；不是角色命名空间下的路径返回 ``None``。"""
    parts = str(logical).split("/")
    return parts[1] if len(parts) >= 3 and parts[0] == "character" and parts[1] else None


def donor_code_leaks(data: bytes, code: str) -> list[str]:
    """交付件里内嵌的 ``character/<别人>/`` 路径段（deflate 会先解压再看）。

    ``code`` 是本角色的新 code。按**路径段**精确匹配，所以母本 code 是新 code 的前缀
    （``sorceress_teacher`` vs ``sorceress_teacher_moon``）也不会漏判或误判。
    只看 ``character/`` 命名空间：DSL/表里直接引用官方特效路径
    （``battle/effect/skill_unique/<母本>/…``）是合法设计，不在这条判据里。
    """
    for wbits in (15, -15, 31):
        try:
            data = zlib.decompress(data, wbits)
            break
        except zlib.error:
            continue
    seen: list[str] = []
    for found in _CHARACTER_SEGMENT.findall(data):
        other = found.decode("ascii")
        if other != code and other not in seen:
            seen.append(other)
    return seen


def install_staged_assets(ctx, path: Path | None = None) -> dict[str, Any]:
    """装 ``B/pixel/<key>/install.json``：``[{root, logical, file, owner}]``。

    - ``file`` 相对 install.json 所在目录（也可写绝对路径，但必须在批目录下）；
    - 文件不存在 **静默跳过**（像素代理还没交付时 kit 照样能跑通）；
    - ``owner`` 默认 ``pixel``；写进去的文件被登记所有权，assets 重跑不会覆盖；
    - ``.png`` 交付件若是标准 PNG（``\\x89PNG``），自动换成 WF 存储态魔数（``\\x89png``）。
      这一步只改前 8 个字节，像素数据一位不动；不换会在 manifest 门禁报
      「WF storage signature required」（20260920 magnus 实测）。
    - **非 PNG 交付件（atlas/frame/timeline 等 AMF3）解压后扫一遍内嵌 code**：出现
      ``character/<别人>/`` 直接拒绝。20260920 真机事故：像素代理把母本元数据「字节不动」
      交付，owner=pixel 盖掉了 assets 步已改写好 code 的正确版本，客户端按母本纹理 id
      取图 → 领取演出 C8003「影像短片尚未加载」。LUT 改色不改 atlas/frame/timeline，
      这几个文件本来就该由 assets 步从母本克隆＋改写；确实需要自带元数据的
      （像素母本 ≠ kit 表母本，或程序化合成的新布局）必须先把内嵌 code 改写干净。
    """
    path = Path(path) if path is not None else pixel_dir(ctx) / "install.json"
    if not path.is_file():
        return {"install_json": str(path), "present": False, "installed": [], "skipped": []}
    entries = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(entries, dict):
        entries = entries.get("assets") or entries.get("install") or []
    if not isinstance(entries, list):
        raise KitError(f"install.json must be a list of entries: {path}")
    base = path.parent
    batch = ctx.pack.batch_dir.resolve()
    installed, skipped = [], []
    for item in entries:
        if not isinstance(item, dict):
            raise KitError(f"install.json entry must be an object: {item!r}")
        try:
            root, logical, rel = item["root"], item["logical"], item["file"]
        except KeyError as exc:
            raise KitError(f"install.json entry lacks {exc}: {item!r}") from None
        owner = item.get("owner") or "pixel"
        source = Path(rel)
        source = source if source.is_absolute() else base / source
        source = source.resolve()
        if not source.is_relative_to(batch):
            raise KitError(f"install.json file escapes the batch directory: {source}")
        if not source.is_file():
            skipped.append({"logical": logical, "file": str(source), "reason": "missing"})
            continue
        data = source.read_bytes()
        restored = False
        if str(logical).lower().endswith(".png"):
            if data[:8] == b"\x89PNG\r\n\x1a\n":
                import wf_assets
                data = wf_assets.png_encode(data)
                restored = True
        else:
            # 期望 code 优先取 ctx.spec（权威），取不到就用交付目标路径自己的
            # `character/<seg>/` 段 —— 让这道闸不依赖 ctx 的具体形状（老的 kit
            # 测试用的是只有 write_asset 的桩 ctx），同时口径与验证器一致：
            # 「装在 character/<X>/ 下的文件不许引用别的 character/<Y>/」。
            spec = getattr(ctx, "spec", None)
            own = getattr(spec, "code", None) or _logical_character(logical)
            leaks = donor_code_leaks(data, own) if own else []
            if leaks:
                raise KitError(
                    f"staged asset {logical} still embeds another character's texture paths "
                    f"{['character/%s/' % c for c in leaks]} — it would override the rewritten "
                    f"copy that the `assets` step produces and make the client fetch the donor "
                    f"atlas (C8003 at the character-get movie). LUT recolor does not change "
                    f"atlas/frame/timeline: drop this entry from install.json and let `assets` "
                    f"generate it. If the pixel donor really differs from the table donor, "
                    f"rewrite character/<donor>/ to character/{ctx.spec.code}/ before delivering "
                    f"(source: {source})")
        ctx.write_asset(root, logical, data, owner=owner)
        installed.append({"root": root, "logical": logical, "owner": owner,
                          "sha256": hashlib.sha256(data).hexdigest(), "size": len(data),
                          "source": str(source), "store_signature_applied": restored})
    return {"install_json": str(path), "present": True, "installed": installed, "skipped": skipped}


# ---------------------------------------------------------------- 特效换色 LUT

LUT_SCHEMA = "ma-fx-lut/1"


def _parse_hex(value: str) -> tuple[int, int, int]:
    text = str(value).strip().lstrip("#")
    if len(text) == 8:                      # #RRGGBBAA：alpha 由图自己保留，这里只取 RGB
        text = text[:6]
    if len(text) != 6:
        raise KitError(f"color must be #RRGGBB: {value!r}")
    return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)


def load_lut(path: Path) -> dict[str, Any] | None:
    path = Path(path)
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != LUT_SCHEMA:
        raise KitError(f"fx_lut schema must be {LUT_SCHEMA!r}: {path}")
    mode = data.get("mode", "exact")
    if mode not in ("exact", "hue", "both"):
        raise KitError(f"fx_lut mode must be exact|hue|both: {mode!r}")
    return data


def png_transform_from_lut(path: Path) -> Callable[[Any], Any] | None:
    """读 ``B/pixel/<key>/fx_lut.json``，返回 ``clone_effect_family(png_transform=...)`` 用的函数。

    文件不存在返回 ``None``（＝不换色，直接克隆原图）。JSON 形状（``schema="ma-fx-lut/1"``）::

        {"schema": "ma-fx-lut/1",
         "mode": "exact" | "hue" | "both",
         "tolerance": 0,                       # exact 匹配的每通道容差（0 = 逐字节相等）
         "exact": {"#3f8fe0": "#e0c23f", ...}, # 精确色表映射
         "hue": [                              # 色相区间映射（按顺序，第一个命中的生效）
           {"from": [90, 170],                 # 色相区间（度，可跨 360：[340, 20]）
            "sat_min": 0.15, "val_min": 0.06,  # 低饱和/暗像素不动（白芯、黑边）
            "hue_set": 52,                     # 或 "hue_shift": -38
            "sat_scale": 1.0, "sat_shift": 0.0,
            "val_scale": 1.0, "val_shift": 0.0}
         ]}

    硬规则：**alpha 一格不动**（``alpha==0`` 的像素连 RGB 都不碰，避免把透明区染成实色
    —— 记忆卡 wf-pixel-art-tooling 的 alpha 门禁）；输出仍是 RGBA。
    """
    data = load_lut(path)
    if data is None:
        return None
    mode = data.get("mode", "exact")
    tolerance = int(data.get("tolerance", 0))
    exact = {_parse_hex(k): _parse_hex(v) for k, v in dict(data.get("exact") or {}).items()}
    ranges = list(data.get("hue") or [])
    if mode in ("exact", "both") and not exact and mode == "exact":
        raise KitError("fx_lut mode=exact but no exact map")
    if mode in ("hue", "both") and not ranges and mode == "hue":
        raise KitError("fx_lut mode=hue but no hue ranges")

    def _hue_hit(rule: Mapping[str, Any], hue_deg: float) -> bool:
        low, high = (float(x) % 360.0 for x in rule.get("from", (0, 360)))
        if low <= high:
            return low <= hue_deg <= high
        return hue_deg >= low or hue_deg <= high      # 跨 0 度

    def transform(image):
        import numpy as np
        from PIL import Image

        arr = np.asarray(image.convert("RGBA")).astype(np.int16)
        rgb = arr[:, :, :3]
        alpha = arr[:, :, 3]
        visible = alpha > 0
        out = rgb.copy()
        done = np.zeros(alpha.shape, dtype=bool)
        if exact:
            for src, dst in exact.items():
                src_arr = np.array(src, dtype=np.int16)
                if tolerance <= 0:
                    hit = np.all(rgb == src_arr, axis=2)
                else:
                    hit = np.all(np.abs(rgb - src_arr) <= tolerance, axis=2)
                hit &= visible & ~done
                out[hit] = np.array(dst, dtype=np.int16)
                done |= hit
        if ranges:
            todo = visible & ~done
            ys, xs = np.nonzero(todo)
            for y, x in zip(ys.tolist(), xs.tolist()):
                r, g, b = (int(v) for v in rgb[y, x])
                h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
                hue_deg = h * 360.0
                for rule in ranges:
                    if not _hue_hit(rule, hue_deg):
                        continue
                    if s < float(rule.get("sat_min", 0.0)) or v < float(rule.get("val_min", 0.0)):
                        continue
                    if "hue_set" in rule:
                        h = (float(rule["hue_set"]) % 360.0) / 360.0
                    elif "hue_shift" in rule:
                        h = ((hue_deg + float(rule["hue_shift"])) % 360.0) / 360.0
                    s = min(1.0, max(0.0, s * float(rule.get("sat_scale", 1.0))
                                     + float(rule.get("sat_shift", 0.0))))
                    v = min(1.0, max(0.0, v * float(rule.get("val_scale", 1.0))
                                     + float(rule.get("val_shift", 0.0))))
                    nr, ng, nb = colorsys.hsv_to_rgb(h, s, v)
                    out[y, x] = [round(nr * 255), round(ng * 255), round(nb * 255)]
                    break
        result = np.dstack([np.clip(out, 0, 255).astype(np.uint8), alpha.astype(np.uint8)])
        return Image.fromarray(result, mode="RGBA")

    return transform


# ---------------------------------------------------------------- kit-report 与指纹

def _owned_digest(ctx) -> dict[str, str]:
    pack = ctx.pack
    out = {}
    for name, owner in sorted(pack.owned_outputs().items()):
        root, _, logical = name.partition(":")
        record = pack.owned_record(root, logical) or {}
        out[name] = f"{owner}:{record.get('sha256')}"
    return out


def fingerprint(ctx, extra: Any = None) -> str:
    """kit 产物指纹：认领 + 产物所有权 sha + 调用方给的附加信息。"""
    payload = {"claims": ctx.pack.load_claims(), "owned": _owned_digest(ctx), "extra": extra}
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def report(ctx, *, summary: str, status: str = DRAFT, panel: Iterable[str] = (),
           notes: Iterable[Any] = (), programs: Iterable[str] = (),
           unique_condition: Mapping[str, Any] | None = None,
           required_capabilities: Iterable[str] = (), deviations: Iterable[Any] = (),
           extra: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """拼 ``evidence/kit-report.json`` 并写盘。

    ``status="ready-for-review"`` 是 ``--step preflight`` 的放行条件；草稿保持 ``"draft"``。
    ``panel`` 的每条都过 :func:`panel_problems`；``deviations`` 登记「原设想→实际落法→原因」
    （裁决 §6：做不到的条目不许静默降级）。
    """
    if status not in (DRAFT, READY):
        raise KitError(f"kit status must be {DRAFT!r} or {READY!r}, got {status!r}")
    panel = list(panel)
    bad = {text: panel_problems(text) for text in panel if panel_problems(text)}
    if bad:
        raise KitError(f"kit panel text violates the batch rules: {bad}")
    programs = sorted(set(programs) | set(ctx.pack.pkg_dsl_programs()))
    value: dict[str, Any] = {
        "batch": "midautumn-20260920", "character": ctx.spec.key, "cid": ctx.spec.cid,
        "code": ctx.spec.code, "summary": summary, "status": status,
        "skills": {"programs": programs},
        "panel": panel, "notes": list(notes), "deviations": list(deviations),
        "required_capabilities": sorted(set(required_capabilities)),
    }
    if unique_condition:
        value["unique_condition"] = dict(unique_condition)
    if extra:
        value.update(extra)
    value["kit_fingerprint"] = fingerprint(ctx, {k: value[k] for k in
                                                 ("summary", "status", "skills", "panel",
                                                  "required_capabilities")})
    ctx.report(value)
    return value
