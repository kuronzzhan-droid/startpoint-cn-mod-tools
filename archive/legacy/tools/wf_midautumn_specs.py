# -*- coding: utf-8 -*-
"""中秋批次（midautumn-20260920）12 个非 GBF 角色的规格表。

薄壳：身份/校验/合并逻辑照抄 :mod:`wf_seasonal7_specs`，只放宽两条与「七角色」绑死的假设
（workspace 前缀 ``s7-`` → ``ma-``、名册不限 7 人），并加一条本批新纪律：
固有状态 ID 一律 8 位 ``cid*100+n``（裁决 §1；169990 段与基诺维 1699901/02 撞过）。

``SeasonalSpec`` 本体、``occupancy_problems``/``assert_unoccupied`` 直接复用旧模块，
**不改 ``wf_seasonal7_*`` 一行**。

spec 合并顺序（:func:`get_spec`）::

    注册表默认  →  B/design/<key>.json 的 spec / texts（文件存在才并）
                →  mod-tools/wf_midautumn_kit_<key>.py 的 SPEC / TEXTS

身份字段（key/cid/code/pkg_id/workspace/template_*）任何一层都不许覆盖。
设计稿未到位时 texts 里的 title/profile/leader 是占位符 :data:`TEXT_PLACEHOLDER`，
保证任何时刻都能跑 tables；``--step check`` 会把仍是占位的角色列出来。
"""
from __future__ import annotations

import dataclasses
import importlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    pass  # Imports resolve from this checkout/package, not external source copies.

from wf_seasonal7_specs import (  # noqa: E402  (再导出，供 kit / 测试使用)
    ELEMENT_COLORS, ELEMENT_SE_DIRS, ELEMENT_TOKENS, ELEMENT_WORDS, IDENTITY_FIELDS,
    PF_TYPES, SERVER_JSONS, STANCES, TEXT_FIELDS, SeasonalSpec, assert_unoccupied,
    occupancy_problems,
)

BATCH_DIR = "work/character_packs/midautumn-20260920"
REQUIRES_CLIENT_BASE = "1.4.933"          # 裁决 §1；reanchor 后的链尾由主控在发布前复核
PACKAGE_VERSION = "1.0.0"
WORKSPACE_PREFIX = "work/character_packs/ma-"
PKG_SUFFIX = "-20260920"
UNIQUE_CONDITION_LOGICAL = "master/character/unique_condition.orderedmap"
TEXT_PLACEHOLDER = "（待设计稿）"
KIT_PREFIX = "wf_midautumn_kit_"
# design json 里允许覆盖的 spec 字段（身份字段与 texts 永远不许）
DESIGN_SPEC_FIELDS = ("pf_type", "stance", "theme", "backdrop_colors", "gacha_se_map",
                      "required_capabilities", "extra_keys", "identity",
                      "requires_client_base", "package_version")


def batch_dir(root: Path) -> Path:
    return Path(root) / BATCH_DIR


def design_path(root: Path, key: str) -> Path:
    return batch_dir(root) / "design" / f"{key}.json"


def _texts(name: str, furigana: str) -> dict[str, Any]:
    """占位 texts：只有名字是真的，称号/简介/队长技名待设计稿，技能名/描述/CV 继承母本。"""
    return {"name": name, "furigana": furigana, "title": TEXT_PLACEHOLDER,
            "profile": TEXT_PLACEHOLDER, "leader": TEXT_PLACEHOLDER,
            "skill1": None, "desc1": None, "skill2": None, "desc2": None, "cv": None}


def _spec(key: str, cid: int, code: str, name: str, furigana: str, *, template_id: int,
          template_code: str, template_element: int, template_identity: int, element: int,
          pf_type: int, stance: str, theme: str,
          backdrop_colors: tuple[tuple[int, int, int], tuple[int, int, int]],
          **extra: Any) -> SeasonalSpec:
    return SeasonalSpec(
        key=key, cid=cid, code=code, pkg_id=f"ma-{key}{PKG_SUFFIX}",
        workspace=f"{WORKSPACE_PREFIX}{key}", template_id=template_id,
        template_code=template_code, template_element=template_element,
        template_identity=template_identity, element=element,
        element_token=ELEMENT_TOKENS[element], rarity=5, pf_type=pf_type, stance=stance,
        identity=cid, theme=theme, texts=_texts(name, furigana),
        backdrop_colors=backdrop_colors, requires_client_base=REQUIRES_CLIENT_BASE,
        package_version=PACKAGE_VERSION, **extra)


# 身份字段照抄裁决文件 §1；母本 code / template_element / template_identity 取官方基线
# （.cdn/cn OfficialBaseline）实读核实，不取 store。核实脚本见 framework_api_midautumn.md §8。
_RAW_SPECS: tuple[SeasonalSpec, ...] = (
    _spec("mia", 119992, "tiger_treasure_hunter_moon", "米娅", "MIYA",
          template_id=111141, template_code="tiger_treasure_hunter_xm22",
          template_element=0, template_identity=241001, element=0, pf_type=2,
          stance="Attacker", theme="中秋·火·PF 主C（+c 连发型）",
          backdrop_colors=((214, 122, 74), (58, 30, 26))),
    _spec("nicola", 119991, "sorceress_teacher_moon", "妮可拉", "NIKELA",
          template_id=211020, template_code="sorceress_teacher",
          template_element=0, template_identity=211020, element=0, pf_type=4,
          stance="Supporter", theme="中秋·火·技伤辅助（★4 母本）",
          backdrop_colors=((208, 138, 96), (52, 32, 30))),
    _spec("magnus", 119990, "lion_swordman_moon", "玛格诺斯", "MAGENUOSI",
          template_id=111129, template_code="lion_swordman_playable",
          template_element=0, template_identity=111129, element=0, pf_type=0,
          stance="Attacker", theme="中秋·火·用 PF 打技伤（机车）",
          backdrop_colors=((222, 104, 62), (46, 26, 24))),
    _spec("charlene", 139992, "artificialeye_sniper_moon", "夏琳", "XIALIN",
          template_id=131176, template_code="artificialeye_sniper",
          template_element=2, template_identity=131176, element=2, pf_type=2,
          stance="Supporter", theme="中秋·雷·直击辅助（敌方减益计数轴）",
          backdrop_colors=((198, 172, 82), (40, 36, 28))),
    _spec("kuro", 139991, "outlaw_panther_moon", "黑", "HEI",
          template_id=231069, template_code="outlaw_panther_ny22",
          template_element=2, template_identity=331004, element=2, pf_type=1,
          stance="Supporter", theme="中秋·雷·Fever 中直击轴（★4 母本）",
          backdrop_colors=((186, 158, 70), (34, 30, 26))),
    _spec("kyle", 139990, "kyle_moon", "凯尔", "KAIER",
          template_id=141159, template_code="black_wolf_knight_wt23",
          template_element=3, template_identity=111007, element=2, pf_type=0,
          stance="Attacker", theme="中秋·雷·直击输出（原创，风→雷翻转）",
          backdrop_colors=((206, 180, 88), (30, 28, 34))),
    _spec("fluffy", 149987, "combat_animal_moon", "芙拉菲", "FULAFEI",
          template_id=141033, template_code="combat_animal",
          template_element=3, template_identity=141033, element=3, pf_type=1,
          stance="Attacker", theme="中秋·风·技伤主C",
          backdrop_colors=((126, 182, 140), (28, 48, 38))),
    _spec("rolf", 149986, "black_wolf_knight_moon", "罗尔夫", "LUOERFU",
          template_id=141159, template_code="black_wolf_knight_wt23",
          template_element=3, template_identity=111007, element=3, pf_type=0,
          stance="Attacker", theme="中秋·风·直击输出核心（速度固定／冲刺）",
          backdrop_colors=((110, 168, 132), (26, 42, 36))),
    _spec("stinel", 159995, "still_obstinator_moon", "丝缇涅尔", "SITINIEER",
          template_id=151093, template_code="still_obstinator",
          template_element=4, template_identity=151093, element=4, pf_type=4,
          stance="Supporter", theme="中秋·光·技伤辅助",
          backdrop_colors=((216, 200, 152), (56, 48, 40))),
    _spec("thorn", 159994, "tweyen_light", "索恩", "SUOEN",
          template_id=151081, template_code="high_priestess_ny22",
          template_element=4, template_identity=151013, element=4, pf_type=2,
          stance="Supporter", theme="十天众·光·技伤辅助（打异常状态，原创）",
          backdrop_colors=((226, 208, 160), (48, 44, 38))),
    _spec("rebecca", 169991, "bearish_darkwitch_moon", "蕾贝卡", "LEIBEIKA",
          template_id=241006, template_code="bearish_darkwitch_ny20",
          template_element=3, template_identity=361007, element=5, pf_type=3,
          stance="Supporter", theme="中秋·暗·PF 辅助（★4 母本，风→暗翻转）",
          backdrop_colors=((132, 100, 172), (30, 24, 48))),
    _spec("hibiki", 169988, "psychic_teleport_moon", "澄波响", "CHENGBOXIANG",
          template_id=161183, template_code="psychic_teleport_playable",
          template_element=5, template_identity=161183, element=5, pf_type=3,
          stance="Attacker", theme="中秋·暗·PF 主C（贯通循环型）",
          backdrop_colors=((118, 92, 164), (26, 22, 44))),
)


# ---------------------------------------------------------------- 静态校验（放宽版）

def _validate(specs: tuple[SeasonalSpec, ...]) -> None:
    """照抄 ``wf_seasonal7_specs._validate_static``，改两条、加一条：

    - workspace 前缀 ``work/character_packs/ma-``（原 ``s7-``）；
    - 不假设名册长度（原实现无此断言，但旧测试钉了 7 人，见 01 报告 §0.2）；
    - **新增**：``extra_keys`` 里 unique_condition 的键必须是 8 位 ``cid*100+n``（裁决 §1）。
    """
    seen: dict[str, dict[Any, str]] = {name: {} for name in ("key", "cid", "code", "pkg_id", "workspace")}
    for spec in specs:
        for name in seen:
            value = getattr(spec, name)
            if value in seen[name]:
                raise AssertionError(f"duplicate spec {name}={value!r}: {seen[name][value]} / {spec.key}")
            seen[name][value] = spec.key
        if not re.fullmatch(r"[a-z]+", spec.key):
            # 语音工具的输出目录正则只认 [a-z]+
            raise AssertionError(f"{spec.key}: role key must be lowercase letters only")
        if not re.fullmatch(r"[a-z][a-z0-9_]*", spec.code):
            raise AssertionError(f"{spec.key}: invalid code_name {spec.code}")
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", spec.pkg_id):
            raise AssertionError(f"{spec.key}: invalid package_id {spec.pkg_id}")
        if spec.code == spec.template_code or spec.cid == spec.template_id:
            raise AssertionError(f"{spec.key}: target equals template")
        if not (0 <= spec.element <= 5) or ELEMENT_TOKENS[spec.element] != spec.element_token:
            raise AssertionError(f"{spec.key}: element {spec.element} != token {spec.element_token}")
        if spec.stance not in STANCES:
            raise AssertionError(f"{spec.key}: illegal stance {spec.stance}")
        if spec.pf_type not in PF_TYPES:
            raise AssertionError(f"{spec.key}: illegal pf_type {spec.pf_type}")
        if spec.rarity != 5:
            raise AssertionError(f"{spec.key}: midautumn batch is ★5 only")
        if spec.identity not in (spec.cid, spec.template_identity):
            raise AssertionError(f"{spec.key}: identity {spec.identity} must be cid {spec.cid} "
                                 f"or template c27 {spec.template_identity}")
        if not isinstance(spec.extra_keys, Mapping):
            raise AssertionError(f"{spec.key}: extra_keys must be a mapping")
        for logical, keys in spec.extra_keys.items():
            if not (isinstance(logical, str) and (logical.endswith(".orderedmap") or logical.endswith(".json"))
                    and not logical.startswith("/") and ".." not in logical.split("/")):
                raise AssertionError(f"{spec.key}: extra_keys logical invalid: {logical!r}")
            if isinstance(keys, str) or not all(isinstance(k, str) and k for k in keys):
                raise AssertionError(f"{spec.key}: extra_keys[{logical}] must be a sequence of non-empty str")
            if logical == UNIQUE_CONDITION_LOGICAL:
                for key in keys:
                    if not unique_condition_ok(spec.cid, key):
                        raise AssertionError(
                            f"{spec.key}: unique_condition id {key!r} must be 8 digits cid*100+n "
                            f"({spec.cid * 100 + 1}…{spec.cid * 100 + 99}); 7 位撞过基诺维 1699901/02")
        if set(spec.texts) != set(TEXT_FIELDS):
            raise AssertionError(f"{spec.key}: texts fields {sorted(spec.texts)}")
        for field in ("name", "furigana", "title", "profile", "leader"):
            if not isinstance(spec.texts.get(field), str) or not spec.texts[field].strip():
                raise AssertionError(f"{spec.key}: texts.{field} must be a non-empty string")
        if spec.element_flip:
            old_dir = ELEMENT_SE_DIRS[spec.template_element]
            for src in spec.gacha_se_map:
                if not src.startswith(f"sound_effect/{old_dir}/"):
                    raise AssertionError(f"{spec.key}: gacha SE map source {src} not old element")
        if spec.cid // 10000 != {0: 11, 1: 12, 2: 13, 3: 14, 4: 15, 5: 16}[spec.element]:
            raise AssertionError(f"{spec.key}: cid {spec.cid} does not follow element prefix")
        if not Path(spec.workspace).as_posix().startswith(WORKSPACE_PREFIX):
            raise AssertionError(f"{spec.key}: workspace outside ma-* sandbox: {spec.workspace}")


def unique_condition_ok(cid: int, key: str) -> bool:
    """固有状态 ID 纪律：8 位、等于 ``cid*100 + n``（n = 1…99）。"""
    if not (isinstance(key, str) and key.isdigit() and len(key) == 8):
        return False
    return 1 <= int(key) - cid * 100 <= 99


def unique_condition_id(cid: int, n: int) -> str:
    if not 1 <= n <= 99:
        raise ValueError(f"unique_condition index out of range: {n}")
    key = str(cid * 100 + n)
    if not unique_condition_ok(cid, key):
        raise ValueError(f"cid {cid} cannot host 8-digit unique_condition ids")
    return key


_validate(_RAW_SPECS)
SPECS: dict[str, SeasonalSpec] = {spec.key: spec for spec in _RAW_SPECS}


# ---------------------------------------------------------------- kit / design 合并

def kit_module_name(key: str) -> str:
    return f"{KIT_PREFIX}{key}"


def load_kit_module(key: str):
    """导入角色 kit 模块；不存在返回 None。"""
    if not (HERE / f"{kit_module_name(key)}.py").is_file():
        return None
    return importlib.import_module(kit_module_name(key))


def _coerce(name: str, value: Any) -> Any:
    """JSON 里的 list 还原成 dataclass 要的 tuple。"""
    if name == "backdrop_colors":
        pair = tuple(tuple(int(c) for c in item) for item in value)
        if len(pair) != 2 or any(len(item) != 3 for item in pair):
            raise ValueError("backdrop_colors must be two RGB triples")
        return pair
    if name == "required_capabilities":
        return tuple(str(v) for v in value)
    if name == "extra_keys":
        return {str(k): tuple(str(x) for x in v) for k, v in dict(value).items()}
    if name == "gacha_se_map":
        return {str(k): str(v) for k, v in dict(value).items()}
    if name in ("pf_type", "identity"):
        return int(value)
    return value


#: 设计稿里的注释字段（不是 spec 字段，直接忽略）
_ANNOTATION_SUFFIXES = ("_why", "_note", "_len", "_reason", "_source")
#: texts 里这五个必须是非空字符串；其余五个（skill*/desc*/cv）写 None = 继承母本
_REQUIRED_TEXTS = ("name", "furigana", "title", "profile", "leader")
#: 形状不对只警告、不报错的字段（纯装饰，缺了不影响机制）
TOLERATED_SHAPE_FIELDS = ("backdrop_colors",)


def _is_annotation(name: str) -> bool:
    return name.startswith("_") or name == "note" or name.endswith(_ANNOTATION_SUFFIXES)


def _apply_overrides(spec: SeasonalSpec, overrides: Mapping[str, Any], texts: Mapping[str, Any],
                     origin: str, *, allowed: tuple[str, ...] | None = None,
                     warnings: list[str] | None = None) -> SeasonalSpec:
    """把一层覆盖并进 spec。

    设计稿是人写的，形状会有出入，所以这里**宽进严判**：
    - 注释字段（``_x`` / ``x_why`` / ``x_note`` …）与 ``None`` 值直接忽略（None = 沿用上一层）；
    - 不认识的字段忽略并记进 ``warnings``（``--step check`` 会报出来），不中断今晚的产线；
    - 身份字段与本层不许改的字段：**值与现状相同就接受**（设计稿常把身份抄一遍存档），
      **不同就报错**——那是真冲突，必须人来定。
    """
    fields = {f.name for f in dataclasses.fields(SeasonalSpec)}
    warn = warnings if warnings is not None else []
    changes: dict[str, Any] = {}
    for name, value in dict(overrides or {}).items():
        if _is_annotation(name) or value is None:
            continue
        if name not in fields:
            warn.append(f"{origin}: 忽略无法识别的 spec 字段 {name!r}")
            continue
        try:
            coerced = _coerce(name, value)
        except (TypeError, ValueError, KeyError) as exc:
            if name in TOLERATED_SHAPE_FIELDS:
                # 纯装饰字段（图标底色圈）形状不对就忽略，不拖垮整条产线；把话说清楚给所有者。
                warn.append(f"{origin}: spec.{name} 形状不对，已忽略（期望 "
                            f"[[内圈R,G,B],[外圈R,G,B]]，收到 {type(value).__name__}）：{exc}")
                continue
            raise ValueError(f"{origin}: spec.{name} 取值非法: {exc}") from None
        locked = name in IDENTITY_FIELDS or name == "texts" or \
            (allowed is not None and name not in allowed)
        if locked:
            if coerced != getattr(spec, name):
                raise ValueError(f"{origin} may not override identity/texts field {name}: "
                                 f"{getattr(spec, name)!r} -> {coerced!r}")
            continue                       # 与现状一致的重复声明：接受，不改
        changes[name] = coerced
    merged_texts = dict(spec.texts)
    for name, value in dict(texts or {}).items():
        if _is_annotation(name):
            continue
        if name not in TEXT_FIELDS:
            warn.append(f"{origin}: 忽略无法识别的 texts 字段 {name!r}")
            continue
        if value is None and name in _REQUIRED_TEXTS:
            continue                       # None = 保留上一层（占位符或注册表值）
        merged_texts[name] = value
    changes["texts"] = merged_texts
    return dataclasses.replace(spec, **changes)


def load_design(root: Path, key: str) -> dict[str, Any]:
    """读 ``B/design/<key>.json``（不存在返回 {}）。"""
    path = design_path(root, key)
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"design json must be an object: {path}")
    return data


def get_spec(key: str, *, with_kit: bool = True, with_design: bool = True,
             root: Path | None = None, warnings: list[str] | None = None) -> SeasonalSpec:
    """注册表 → design json → kit 模块，逐层覆盖后重跑静态校验。

    ``warnings``：给个 list 就能收到「忽略了哪些无法识别的字段」（``--step check`` 会打印）。
    """
    if key not in SPECS:
        raise KeyError(f"unknown midautumn character: {key}; known {sorted(SPECS)}")
    spec = SPECS[key]
    if with_design:
        if root is None:
            import wf_mod_tool as core
            root = core.project_root()
        design = load_design(Path(root), key)
        if design:
            spec = _apply_overrides(spec, design.get("spec") or {}, design.get("texts") or {},
                                    f"design/{key}.json", allowed=DESIGN_SPEC_FIELDS,
                                    warnings=warnings)
    if with_kit:
        module = load_kit_module(key)
        if module is not None:
            spec = _apply_overrides(spec, getattr(module, "SPEC", {}) or {},
                                    getattr(module, "TEXTS", {}) or {}, kit_module_name(key),
                                    warnings=warnings)
    _validate(tuple(spec if s.key == key else s for s in _RAW_SPECS))
    return spec


def spec_warnings(key: str, root: Path | None = None) -> list[str]:
    warnings: list[str] = []
    get_spec(key, root=root, warnings=warnings)
    return warnings


def all_keys() -> list[str]:
    return list(SPECS)


def resolve_keys(value: str) -> list[str]:
    """``all`` 或逗号分隔的 key 列表。"""
    if value == "all":
        return all_keys()
    keys = [k.strip() for k in value.split(",") if k.strip()]
    unknown = [k for k in keys if k not in SPECS]
    if unknown:
        raise KeyError(f"unknown midautumn characters: {unknown}; known {sorted(SPECS)}")
    return keys


def text_placeholders(spec: SeasonalSpec) -> list[str]:
    """仍然是占位符的文本字段（设计稿未到位的信号）。"""
    return [name for name in ("title", "profile", "leader")
            if isinstance(spec.texts.get(name), str) and TEXT_PLACEHOLDER in spec.texts[name]]


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    print(json.dumps({k: s.to_dict() for k, s in SPECS.items()}, ensure_ascii=False, indent=1))
