# -*- coding: utf-8 -*-
"""中秋批次 kit：米娅·中秋 119992 ``tiger_treasure_hunter_moon``（火属性 PF 主 C）。

定位「+c 连发型强化弹射主 C」：每次强化弹射都追加连击、连击本身再叠连击加成，保底 Lv2、
两三拍连上 Lv3；每次强化弹射点亮一盏「桂灯」，满 3 盏后每 3 次强化弹射撬开「月光宝匣」，
打一发 629 追击『开匣·月华』（按强化弹射伤害结算）。设计与数值以
``work/character_packs/midautumn-20260920/design/mia.{md,json}`` 为准 —— 本模块是「设计 JSON
驱动」的薄壳：队长 8 行、词条 6 键 15 条的 donor/逐格改/预期 ``wf_describe`` 全部从
``design/mia.json`` 的 ``plan`` 块读出后交给 :func:`wf_midautumn_kitlib.build_row` 装配，
两边漂移（donor 缺失、legality 不过、``wf_describe`` 对不上）当场报错，不在本文件里手抄
23 行的具体数值（那是设计代理已核实过的产物，抄一遍只会引入新的转录错误）。

本模块自己负责的是设计 JSON 管不到的部分：
    - 固有状态「桂灯」（``11999201``，官方 donor 15「继承之炎」同形，上限 3）+ 48×48 图标；
    - 技能 DSL 两档：官方**自身**母本 111141 的 ``_1``/``_2`` 树只改参数（不跨角色拼树）；
    - 629 追击『开匣·月华』：官方 ``fire_dragon_zenith`` 整树只改倍率与内层爆裂特效路径，
      根头 ``tree[10]`` 0→3（按强化弹射伤害结算，卖点所在）；
    - 技能特效族 ``tiger_treasure_hunter_xm22`` 换名重打 + ``B/pixel/mia/fx_lut.json`` 染色
      （圣诞红/绿/蓝三色礼盒 → 中秋金/琥珀/暖白），629 与两档技能共用；
    - ``custom_ability_string``：629 的 c68 字符串键 + 队长整块的 ``desc_override``；
    - 语音路由（kind 1 ConditionExist ← 固有「桂灯」）与 ``switched_action_skill``；
    - ``B/pixel/mia/install.json`` 里的像素小人成品（缺文件静默跳过）。

不碰：live store / ``assets/`` / ``.cdn`` / 设备 / 存档；不做 722（官方 ranged 原生 PF）。
由 ``python mod-tools/wf_midautumn_build.py --char mia --step kit`` 调用 :func:`build`。
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    pass  # Imports resolve from this checkout/package, not external source copies.

import wf_client_legality as L  # noqa: E402
import wf_dsl  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_midautumn_specs as MS  # noqa: E402

KitError = KL.KitError

KEY = "mia"
CID, CODE = 119992, "tiger_treasure_hunter_moon"
ELEMENT = 0                                    # 火（0 基内部编号，Red）
TEMPLATE_ID, TEMPLATE_CODE = 111141, "tiger_treasure_hunter_xm22"

ABILITY_KEYS = tuple(f"{CID}{slot}" for slot in range(1, 7))

UID = MS.unique_condition_id(CID, 1)           # "11999201"
UNIQUE_DONOR = "15"                            # 官方 unique_condition[15]「继承之炎」（99999999帧/3层）
UNIQUE_STRING_ID = f"unique_{CODE}_lantern"
UNIQUE_NAME = "桂灯"
UNIQUE_ICON_ROW = f"battle/common/unique_condition/{UNIQUE_STRING_ID}"
UNIQUE_ICON_LOGICAL = UNIQUE_ICON_ROW + ".png"
UNIQUE_ICON_FRAME = "battle/common/unique_condition/unique_resistance_princess_3halfanv.png"
UNIQUE_CAP = "3"                               # 禁 (None)：那是上限 1，during 134 按层加成会全死

CAS_ABILITY_SKILL = f"ability_skill_{CODE}"    # 629 的 c68 string_id（同时是追击程序的 basename）
CAS_DESC_OVERRIDE = f"desc_override_{CODE}"    # 队长整块 8 行共用同一 c0 ⇒ 覆盖整块面板
VOICE_KEY = f"{CODE}_voice_ready"
VOICE_ROUTE = {"kind": 1, "condition_kind": "28", "condition_id": UID}

PURSUIT_DONOR = ("battle/action/skill/action/ability_skill/"
                 "ability_skill_fire_dragon_zenith$ability_skill_fire_dragon_zenith")
# 程序文件 basename 与 c68 的字符串键（CAS_ABILITY_SKILL）故意不同：CODE 全名很长
# （27 字符），若沿用 "ability_skill_<CODE>" 当 basename，"--step inspect" 在 Windows 上把
# workspace 复制到 "_inspect/mia-<pid>-rebase/…" 临时目录时会让这条 .action.dsl.amf3.deflate
# 全路径超过 260 字符（MAX_PATH），触发 shutil.copytree 的 [WinError 3]（本轮实测撞到，
# 220913 已在返回里报告；未改共享的 wf_midautumn_build.py，只在本模块内把 DSL basename
# 换短）。字符串键与文件路径本来就是两件事：c68 只是 custom_ability_string 的查找键，
# 不受文件系统路径长度限制。
PURSUIT_BASENAME = "mia_lantern_pursuit"
PURSUIT_PROGRAM = f"battle/action/skill/action/ability_skill/{PURSUIT_BASENAME}${PURSUIT_BASENAME}"
PURSUIT_MULT = {"min": 8.0, "max": 10.0}       # donor 3.75→5.0；4段×10.0=40×（ALv 满）

# 特效族：母本 tiger_treasure_hunter_xm22 的圣诞礼盒开箱族，换名重打 + LUT 染色，
# 629 与两档技能共用（design/mia.json plan.skills.effects_clone）。
FX_SRC_DIR = f"battle/effect/skill_unique/{TEMPLATE_CODE}"
FX_SUBDIR = "moonbox"                          # clone_effect_family(layout="codename") 强制两级目录
FX_MEMBERS = (f"{TEMPLATE_CODE}_all", f"{TEMPLATE_CODE}_claw", f"{TEMPLATE_CODE}_dash")
FX_DST_DIR = f"battle/effect/skill_unique/{CODE}/{FX_SUBDIR}"
PURSUIT_CLAW_BASENAME = f"{TEMPLATE_CODE}_claw"

# 两档技能的 DSL 参数编辑（donor 现值 → 目标值）；两棵树结构相同，只有这三处数值不同。
SKILL_EDITS = {
    "1": {"cna_from": {"min": 1, "max": 1}, "cna_to": {"min": 5.5, "max": 5.5},
          "pf_frames": 960, "pf_from": {"min": 1, "max": 1}, "pf_to": {"min": 1.5, "max": 1.5},
          "cb_from": ({"min": 1, "max": 1}, {"min": 5, "max": 5}),
          "cb_to": ({"min": 2, "max": 2}, {"min": 10, "max": 10})},
    "2": {"cna_from": {"min": 1.3, "max": 1.5}, "cna_to": {"min": 7.0, "max": 8.5},
          "pf_frames": 1200, "pf_from": {"min": 1.25, "max": 1.5}, "pf_to": {"min": 1.6, "max": 2.0},
          "cb_from": ({"min": 1, "max": 1}, {"min": 10, "max": 15}),
          "cb_to": ({"min": 3, "max": 3}, {"min": 12, "max": 15})},
}

TEXTS: dict[str, str] = {}       # 10 个文本键在 design/mia.json 的 texts 块里（build 里核验）
SPEC = {
    "required_capabilities": ("panel-description-override-v2",),
    "extra_keys": {
        MS.UNIQUE_CONDITION_LOGICAL: (UID,),
        KL.CAS: (CAS_ABILITY_SKILL, CAS_DESC_OVERRIDE),
        KL.SWITCHED: (VOICE_KEY,),
    },
}


# ---------------------------------------------------------------- 设计稿读取

def load_design(root: Path) -> dict[str, Any]:
    design = MS.load_design(Path(root), KEY)
    if not design:
        raise KitError(f"design/{KEY}.json missing (batch {MS.BATCH_DIR})")
    if design.get("schema") != "ma-design/1" or design.get("cid") != CID or design.get("code") != CODE:
        raise KitError(f"design identity drift: {design.get('schema')} {design.get('cid')} {design.get('code')}")
    return design


def _parse_donor(donor: str) -> tuple[str, str]:
    """设计稿的 donor 地址 ``"<o|s>:<A|L>:<键>:<记录号(1基)>"`` → (source, "键#记录号(0基)")。

    ``o`` = 官方基线（``OfficialBaseline('.cdn/cn')``），``s`` = live store 只读（已在线自制角色）。
    记录号是**1基**（design/mia.md 的 ``#L1``/``#L3`` 写法），``kitlib.donor_row`` 要 0 基下标，
    这里统一减 1（同批 wf_midautumn_kit_hibiki.py 的既有约定：「设计稿的 #N 是 1 基记录号」）。
    """
    parts = str(donor).split(":")
    if len(parts) != 4:
        raise KitError(f"unexpected donor address shape: {donor!r}")
    src, table, key, index = parts
    source = {"o": "official", "s": "live"}.get(src)
    if source is None or table not in ("A", "L"):
        raise KitError(f"unrecognised donor address: {donor!r}")
    index0 = int(index) - 1
    if index0 < 0:
        raise KitError(f"donor record number must be >= 1 (1-based): {donor!r}")
    return source, f"{key}#{index0}"


def build_leader_rows(ctx, design: dict[str, Any]) -> tuple[list[list[str]], list[dict[str, Any]]]:
    plan = design["plan"]["leader_ability"]
    if plan["key"] != str(CID) or plan["ncols"] != KL.LEADER_NCOLS:
        raise KitError(f"design leader block drift: key={plan.get('key')} ncols={plan.get('ncols')}")
    rows: list[list[str]] = []
    evidence: list[dict[str, Any]] = []
    for entry in plan["rows"]:
        source, donor = _parse_donor(entry["donor"])
        label = f"leader#{entry['index']}"
        row, ev = KL.build_row(ctx, "leader_ability", donor, entry["cells"], source=source,
                               element=ELEMENT, expect_describe=entry["desc_actual_wf_describe"],
                               label=label)
        if row[0] != CODE:
            raise KitError(f"{label}: c0 {row[0]!r} != {CODE}")
        rows.append(row)
        evidence.append(ev)
    if len(rows) != 8:
        raise KitError(f"design leader_ability carries {len(rows)} rows, expected 8")
    return rows, evidence


def _ban_forbidden_leader_kinds(rows: list[list[str]]) -> None:
    """队长表禁 422/724/713（裁决 §2/§8：写进队长表 = C7050）。瞬发 kind 在 c45，during 在 c107。"""
    for n, row in enumerate(rows):
        if row[45] in ("422", "724", "713") or row[107] in ("422", "724", "713"):
            raise KitError(f"leader#{n}: forbidden kind in leader_ability (c45={row[45]!r} c107={row[107]!r})")


def build_ability_rows(ctx, design: dict[str, Any]) -> tuple[dict[str, list[list[str]]], list[dict[str, Any]]]:
    plan = design["plan"]["ability"]
    if plan["ncols"] != KL.ABILITY_NCOLS:
        raise KitError(f"design ability ncols drift: {plan.get('ncols')}")
    if tuple(sorted(plan["keys"])) != tuple(sorted(ABILITY_KEYS)):
        raise KitError(f"design ability keys drift: {sorted(plan['keys'])}")
    rows_by_key: dict[str, list[list[str]]] = {}
    evidence: list[dict[str, Any]] = []
    for slot, key_name in enumerate(ABILITY_KEYS, start=1):
        block = plan["keys"][key_name]
        if int(block["slot"]) != slot:
            raise KitError(f"ability {key_name}: slot {block['slot']} != {slot}")
        rows: list[list[str]] = []
        for entry in block["records"]:
            source, donor = _parse_donor(entry["donor"])
            label = f"{key_name}#{entry['index']}"
            row, ev = KL.build_row(ctx, "ability", donor, entry["cells"], source=source,
                                   element=ELEMENT, expect_describe=entry["desc_actual_wf_describe"],
                                   label=label)
            rows.append(row)
            evidence.append(ev)
        KL.check_ability_key(rows, key_name, CODE, slot)
        if rows[0][1] != block["unisonable"] or rows[0][2] != block["statue_group"]:
            raise KitError(f"ability {key_name}: c1/c2 {rows[0][1]}/{rows[0][2]} != design "
                           f"{block['unisonable']}/{block['statue_group']}")
        rows_by_key[key_name] = rows
    return rows_by_key, evidence


def write_strings(ctx, design: dict[str, Any]) -> tuple[dict[str, str], set[str]]:
    """custom_ability_string：629 的字符串键 + 队长整块的面板覆盖。"""
    rows = design["plan"]["texts"]["custom_ability_string"]["rows"]
    cas_plan = {entry["key"]: entry["text"] for entry in rows}
    if set(cas_plan) != {CAS_ABILITY_SKILL, CAS_DESC_OVERRIDE}:
        raise KitError(f"design custom_ability_string keys drift: {sorted(cas_plan)}")
    declared = set(ctx.spec.extra_keys.get(KL.CAS, ()))
    missing = [k for k in cas_plan if k not in declared]
    if missing:
        raise KitError(f"custom_ability_string keys not declared in SPEC['extra_keys']: {missing}")
    caps: set[str] = set()
    for key, text in cas_plan.items():
        KL.check_panel(text, label=key)
        cap = L.panel_override_capability(key)
        if cap:
            caps.add(cap)
    ctx.write_flat(KL.CAS, {k: [[v]] for k, v in cas_plan.items()})
    return cas_plan, caps


def write_action_skill(ctx, design: dict[str, Any]) -> dict[str, list[str]]:
    spec = ctx.spec
    energy = design["plan"]["skills"]["energy"]
    inner = ctx.pkg_nested(CODE)
    if set(inner) != {"1", "2"}:
        raise KitError(f"package action_skill inner keys {sorted(inner)}")
    out: dict[str, list[str]] = {}
    for level, cells in sorted(inner.items()):
        cells = list(cells)
        if len(cells) != 24:
            raise KitError(f"action_skill {level}: {len(cells)} columns, expected 24")
        if cells[7] != ctx.program_path(level):
            raise KitError(f"action_skill {level} program path drift: {cells[7]!r}")
        if cells[0] != spec.texts[f"skill{level}"] or cells[1] != spec.texts[f"desc{level}"]:
            raise KitError(f"action_skill {level}: name/desc differ from design texts (rerun tables)")
        e = energy[f"skill{level}"]
        cells[4], cells[5] = str(e["c4"]), str(e["c5"])
        out[level] = cells
    ctx.write_nested(KL.ACTION, CODE, {lv: [cells] for lv, cells in out.items()}, replace_inner=True)
    return out


# ---------------------------------------------------------------- 固有状态图标

def draw_icon(frame):
    """48×48「桂灯」：暗底圆角(#1C1410) + 2px 金边；中央月兔提灯剪影（金轮廓+暖白火芯），右下桂花小点。

    8× 画布绘制后 LANCZOS 缩回 48×48；alpha 取官方图标外框（同批统一工艺，alpha 一格不改）。
    """
    from PIL import Image, ImageDraw
    if frame.size != (48, 48):
        raise KitError(f"icon frame donor must be 48x48, got {frame.size}")
    K, N = 8, 48 * 8
    layer = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    inner = Image.new("L", (N, N), 0)
    ImageDraw.Draw(inner).rounded_rectangle((3 * K, 3 * K, 45 * K - 1, 45 * K - 1), radius=6 * K, fill=255)
    layer.paste(Image.new("RGBA", (N, N), (28, 20, 16, 255)), (0, 0), inner)

    gold, cream = (232, 184, 75, 255), (255, 244, 192, 255)
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle((4 * K, 4 * K, 44 * K - 1, 44 * K - 1), radius=5 * K, outline=gold, width=2 * K)

    # 提灯剪影：椭圆灯身 + 顶部盖 + 底部穗结 + 两只圆润兔耳
    body = Image.new("L", (N, N), 0)
    bd = ImageDraw.Draw(body)
    bd.ellipse((14.0 * K, 15.0 * K, 34.0 * K, 35.0 * K), fill=255)
    bd.rounded_rectangle((19.0 * K, 10.5 * K, 29.0 * K, 15.5 * K), radius=1.5 * K, fill=255)   # 灯盖
    bd.rounded_rectangle((22.5 * K, 35.0 * K, 25.5 * K, 39.0 * K), radius=1.0 * K, fill=255)   # 穗结
    bd.ellipse((15.5 * K, 6.0 * K, 20.5 * K, 13.0 * K), fill=255)                              # 左耳
    bd.ellipse((27.5 * K, 6.0 * K, 32.5 * K, 13.0 * K), fill=255)                              # 右耳
    body_mask = Image.composite(body, Image.new("L", (N, N), 0), inner)
    layer.paste(Image.new("RGBA", (N, N), gold), (0, 0), body_mask)

    # 暖白火芯（灯身内缩一圈）
    core = Image.new("L", (N, N), 0)
    cd = ImageDraw.Draw(core)
    cd.ellipse((17.0 * K, 18.5 * K, 31.0 * K, 32.0 * K), fill=255)
    cd.ellipse((17.5 * K, 8.0 * K, 19.5 * K, 11.5 * K), fill=255)
    cd.ellipse((29.5 * K, 8.0 * K, 31.5 * K, 11.5 * K), fill=255)
    core_mask = Image.composite(core, Image.new("L", (N, N), 0), inner)
    layer.paste(Image.new("RGBA", (N, N), cream), (0, 0), core_mask)

    # 右下一枚桂花小点（四瓣）
    flower_cx, flower_cy, r = 36.5 * K, 36.5 * K, 2.6 * K
    fd = ImageDraw.Draw(layer)
    for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
        fd.ellipse((flower_cx + dx * r - r * 0.75, flower_cy + dy * r - r * 0.75,
                   flower_cx + dx * r + r * 0.75, flower_cy + dy * r + r * 0.75), fill=gold)
    fd.ellipse((flower_cx - r * 0.55, flower_cy - r * 0.55, flower_cx + r * 0.55, flower_cy + r * 0.55),
              fill=cream)

    small = layer.resize((48, 48), Image.LANCZOS)
    out = Image.new("RGBA", (48, 48), (255, 255, 255, 0))
    fp, op, sp = frame.load(), out.load(), small.load()
    for y in range(48):
        for x in range(48):
            r, g, b, a = sp[x, y]
            fa = fp[x, y][3]
            if a:
                op[x, y] = (round((r * a + 255 * (255 - a)) / 255), round((g * a + 255 * (255 - a)) / 255),
                            round((b * a + 255 * (255 - a)) / 255), fa)
            else:
                op[x, y] = (255, 255, 255, fa)
    return out


def install_unique_icon(ctx) -> dict[str, Any]:
    frame_raw = ctx.official_read(UNIQUE_ICON_FRAME)
    if frame_raw is None:
        _root, frame_raw, _how = ctx.pack.template_asset(UNIQUE_ICON_FRAME)
    frame = ctx.png_open(frame_raw)
    data = ctx.png_store_bytes(draw_icon(frame))
    ctx.write_asset("common", UNIQUE_ICON_LOGICAL, data)
    back = ctx.png_open(ctx.pack.pkg_path("common", UNIQUE_ICON_LOGICAL).read_bytes())
    if back.size != (48, 48) or back.getchannel("A").tobytes() != frame.getchannel("A").tobytes():
        raise KitError("unique_condition icon size/alpha differ from the official frame donor")
    return {"logical": UNIQUE_ICON_LOGICAL, "frame_donor": UNIQUE_ICON_FRAME,
            "size": list(back.size), "sha256": _sha256(data), "bytes": len(data)}


def _sha256(data: bytes) -> str:
    import hashlib
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------- DSL 工具

def _cc_ac_entry(tree, kind: str) -> list:
    """恰好一个 ``CreateCondition`` 携带该 AdditionalCondition kind，返回它的整条 AC 条目。"""
    hits = [c for c in wf_dsl.iter_dsl_commands(tree, "CreateCondition") if c[2] and c[2][0][0] == kind]
    if len(hits) != 1:
        raise KitError(f"expected exactly 1 CreateCondition/{kind}, got {len(hits)}")
    return hits[0][2][0]


def _dsl_problems(tree, *, element: int | None = None) -> list[str]:
    problems: list[str] = []
    problems += [f"direction: {p}" for p in wf_dsl.player_side_dsl_problems(tree)]
    problems += [f"subject: {p}" for p in L.action_dsl_subject_binding_problems(tree)]
    problems += [f"hit_target: {p}" for p in L.action_dsl_hit_area_target_problems(tree)]
    if element is not None:
        problems += [f"element: {p}" for p in L.action_dsl_element_problems(tree, element)]
    return problems


def _write_dsl_checked(ctx, program: str, tree) -> str:
    """``write_dsl`` 只吃裸树；写后回读比对（记忆卡 wf-dsl-encode-wrapper-trap）。"""
    if not (isinstance(tree, list) and tree and tree[0] == "ActionDsl"):
        raise KitError(f"write_dsl needs a bare ActionDsl tree, got {type(tree).__name__}")
    logical = ctx.write_dsl(program, tree)
    back = ctx.amf_parse(ctx.pack.pkg_path("common", logical).read_bytes())
    if back != tree:
        raise KitError(f"DSL readback mismatch: {logical}")
    return logical


def build_skill_tree(ctx, level: str, family: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    """官方**自身**母本 111141 的 ``_1``/``_2`` 树，只改参数（不跨角色拼树）。"""
    edits = SKILL_EDITS[level]
    donor_program = ctx.program_path(level).replace(CODE, TEMPLATE_CODE)
    tree = copy.deepcopy(ctx.template_dsl(donor_program))
    if tree[0] != "ActionDsl" or tree[1] != 3 or tree[10] != 0:
        raise KitError(f"skill {level} donor head drift: {tree[:2]} bta={tree[10]}")

    attacks = list(wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack"))
    if len(attacks) != 2:
        raise KitError(f"skill {level} donor should carry 2 CreateNormalAttack, got {len(attacks)}")
    for cna in attacks:
        if cna[6] != [edits["cna_from"]]:
            raise KitError(f"skill {level} CNA multiplier drift: {cna[6]}")
        cna[6] = [edits["cna_to"]]

    pf = _cc_ac_entry(tree, "ACPowerFlipDamage")
    if pf[1] != [{"min": edits["pf_frames"], "max": edits["pf_frames"]}] or pf[2] != [edits["pf_from"]]:
        raise KitError(f"skill {level} ACPowerFlipDamage drift: frames={pf[1]} value={pf[2]}")
    pf[2] = [edits["pf_to"]]

    cb = _cc_ac_entry(tree, "ACComboBoost")
    if cb[1] != [edits["cb_from"][0]] or cb[2] != [edits["cb_from"][1]]:
        raise KitError(f"skill {level} ACComboBoost drift: window={cb[1]} boost={cb[2]}")
    cb[1] = [edits["cb_to"][0]]
    cb[2] = [edits["cb_to"][1]]

    tree, info = ctx.rewrite_effect_refs(tree, family, strict=True)
    problems = _dsl_problems(tree, element=ELEMENT)
    if problems:
        raise KitError(f"skill {level} DSL gates failed: {problems}")
    return tree, {"level": level, "cna": edits["cna_to"], "pf_damage": edits["pf_to"],
                  "combo_boost": edits["cb_to"], "effect_rewrites": info["rewritten"]}


def build_pursuit_tree(ctx, family: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    """629 追击『开匣·月华』：官方 ``fire_dragon_zenith`` 整树只改倍率与内层爆裂特效路径。

    根头 ``tree[10]``：donor 原值 0 → 3（按强化弹射伤害结算——这是本设计的卖点，见
    design/mia.md §2 行#6 的 head_note）；外层「オーラ演出」保留官方 ``fire_dragon_zenith``
    引用不动（未克隆，只引用不改色的官方特效直接引用官方路径，框架 §10.3）。
    """
    tree = copy.deepcopy(ctx.template_dsl(PURSUIT_DONOR))
    if tree[0] != "ActionDsl" or tree[1] != 1 or tree[10] != 0:
        raise KitError(f"pursuit donor head drift: {tree[:2]} bta={tree[10]}")

    areas = list(wf_dsl.iter_dsl_commands(tree, "CreateHitArea"))
    if len(areas) != 2:
        raise KitError(f"pursuit donor should carry 2 CreateHitArea, got {len(areas)}")
    outer = next((a for a in areas if a[9] == ["Circle", [{"min": 60, "max": 60}]]), None)
    inner = next((a for a in areas if a[9] == ["Circle", [{"min": 250, "max": 250}]]), None)
    if outer is None or inner is None:
        raise KitError(f"pursuit hit-area shapes drift: {[a[9] for a in areas]}")
    if outer[14] != ["CalculatedUsingMaxNumOfHits", 1] or outer[15] != ["Some", [{"min": 1, "max": 1}]]:
        raise KitError("pursuit outer 探测层已漂移(maxHits/totalHitToEliminate)："
                       "不能改成 None，否则一次强化弹射命中多个敌人会各挂一棵子树")
    if inner[14] != ["CalculatedUsingMaxNumOfHits", 4]:
        raise KitError(f"pursuit inner maxHits drift: {inner[14]}")

    rps = list(wf_dsl.iter_dsl_commands(tree, "CreateReferencePoint"))
    if len(rps) != 1 or rps[0][9] != 30:
        raise KitError(f"pursuit CreateReferencePoint lifetime drift: {rps}")

    attacks = list(wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack"))
    if len(attacks) != 1 or attacks[0][6] != [{"min": 3.75, "max": 5}]:
        raise KitError(f"pursuit CNA multiplier drift: {attacks}")
    attacks[0][6] = [dict(PURSUIT_MULT)]

    shows = list(wf_dsl.iter_dsl_commands(tree, "ShowEffect"))
    if len(shows) != 2:
        raise KitError(f"pursuit donor should carry 2 ShowEffect, got {len(shows)}")
    special = next((s for s in shows if isinstance(s[2], list) and s[2][0] == "SpecifyEffectDirectly"
                    and str(s[2][1]).endswith("_special_attack")), None)
    if special is None:
        raise KitError("pursuit special (burst) ShowEffect not found")
    special[2] = ["SpecifyEffectDirectly", f"{family['dst_dir']}/{PURSUIT_CLAW_BASENAME}"]

    tree[10] = 3          # 设计 head_note：0 → 3，按强化弹射伤害结算

    tree, info = ctx.rewrite_effect_refs(tree, family, strict=True)
    problems = _dsl_problems(tree, element=None)     # CNA 元素参 255 继承，元素检查在技能侧已做
    if problems:
        raise KitError(f"pursuit DSL gates failed: {problems}")
    return tree, {"multiplier": dict(PURSUIT_MULT), "total": round(PURSUIT_MULT["max"] * 4, 2),
                  "effect_rewrites": info["rewritten"], "bta": tree[10]}


# ---------------------------------------------------------------- 入口

def build(ctx) -> dict[str, Any]:
    spec = ctx.spec
    if (spec.cid, spec.code, spec.element) != (CID, CODE, ELEMENT):
        raise KitError(f"identity drift: {spec.cid}/{spec.code}/element {spec.element}")
    if (spec.template_id, spec.template_code) != (TEMPLATE_ID, TEMPLATE_CODE):
        raise KitError(f"template drift: {spec.template_id}/{spec.template_code}")
    if spec.pf_type != 2 or spec.stance != "Attacker":
        raise KitError(f"spec drift: pf_type={spec.pf_type} stance={spec.stance}")
    if MS.text_placeholders(spec):
        raise KitError(f"design texts still placeholders: {MS.text_placeholders(spec)}")

    design = load_design(ctx.root)

    # ---- 1) 固有状态「桂灯」+ 48×48 图标
    key, row = KL.unique_row(ctx, spec, 1, donor=UNIQUE_DONOR, cells={0: UNIQUE_STRING_ID},
                             name=UNIQUE_NAME, icon=UNIQUE_ICON_ROW)
    if key != UID:
        raise KitError(f"unique id {key} != {UID}")
    plan_unique = design["plan"]["unique_conditions"]["add"]
    if len(plan_unique) != 1 or plan_unique[0]["key"] != key or list(plan_unique[0]["row"]) != row:
        raise KitError(f"unique_condition row differs from the design plan: {row}")
    KL.write_unique(ctx, spec, {key: row})
    icon = install_unique_icon(ctx)

    # ---- 2) 队长技 8 行（design.json 驱动）
    leader_rows, leader_evidence = build_leader_rows(ctx, design)
    _ban_forbidden_leader_kinds(leader_rows)
    capabilities: set[str] = set()
    for ev in leader_evidence:
        capabilities.update(ev["capabilities"])
    ctx.write_flat(KL.LEADER, {str(CID): leader_rows})

    # ---- 3) 词条 6 键 15 条（design.json 驱动）
    ability_rows, ability_evidence = build_ability_rows(ctx, design)
    for ev in ability_evidence:
        capabilities.update(ev["capabilities"])
    ctx.write_flat(KL.ABILITY, ability_rows)

    # ---- 4) 面板覆盖串（629 字符串 + 队长整块覆盖）
    cas_plan, cas_caps = write_strings(ctx, design)
    capabilities.update(cas_caps)

    # ---- 5) action_skill 两档（名称/描述由 tables 写 TEXTS，这里只改能量）
    action_rows = write_action_skill(ctx, design)

    # ---- 6) 技能特效族（换名重打 + LUT 染色，629 与两档技能共用）
    lut = KL.png_transform_from_lut(KL.pixel_dir(ctx) / "fx_lut.json")
    family = ctx.clone_effect_family(FX_SRC_DIR, FX_SUBDIR, fx_names=list(FX_MEMBERS), png_transform=lut)
    if family["dst_dir"] != FX_DST_DIR or sorted(family["copied_bases"]) != sorted(FX_MEMBERS):
        raise KitError(f"effect family drift: {family['dst_dir']} {family['copied_bases']}")

    # ---- 7) 技能 DSL 两档 + 629 追击 DSL
    programs: list[str] = []
    skill_gates: dict[str, Any] = {}
    for level in ("1", "2"):
        tree, gates = build_skill_tree(ctx, level, family)
        programs.append(_write_dsl_checked(ctx, ctx.program_path(level), tree))
        skill_gates[level] = gates
    pursuit_tree, pursuit_gate = build_pursuit_tree(ctx, family)
    programs.append(_write_dsl_checked(ctx, PURSUIT_PROGRAM, pursuit_tree))
    invoke_row = leader_rows[6]
    if invoke_row[68] != CAS_ABILITY_SKILL or invoke_row[69] != PURSUIT_PROGRAM:
        raise KitError(f"leader#6 629 string/path drift: c68={invoke_row[68]!r} c69={invoke_row[69]!r}")

    # ---- 8) 语音路由（kind 1 ConditionExist ← 固有「桂灯」）+ character 行
    route = KL.voice_route(CODE, VOICE_ROUTE)
    design_route = design["voice"]["route"]
    if (int(design_route["kind"]), str(design_route["condition_kind"]), str(design_route["condition_id"])) \
            != (VOICE_ROUTE["kind"], VOICE_ROUTE["condition_kind"], VOICE_ROUTE["condition_id"]):
        raise KitError(f"design voice route drift: {design_route}")
    char_row = ctx.pack.pkg_character_row()
    char_row[9:17] = route
    if char_row[6] != "2" or char_row[26] != "Attacker" or char_row[27] != str(CID):
        raise KitError(f"character row drift: c6={char_row[6]} c26={char_row[26]} c27={char_row[27]}")
    ctx.write_flat(KL.CHARACTER, {str(CID): [char_row]})
    voice_ready = KL.write_voice_ready(ctx)

    # ---- 9) 像素成品（缺文件静默跳过）+ 三层镜像
    pixel = KL.install_staged_assets(ctx)
    mirrors = ctx.sync_character_mirrors()
    if mirrors["character"][9:17] != route:
        raise KitError("character mirror lost the voice route")

    # 面板：队长 8 行整块被 desc_override 覆盖，个别行的 wf_describe 只用于 expect_describe 门禁；
    # 词条 6 键 15 条无覆盖，逐条按 wf_describe 原文显示。
    panel = [cas_plan[CAS_DESC_OVERRIDE], cas_plan[CAS_ABILITY_SKILL]]
    panel.extend(ev["describe"] for ev in ability_evidence)

    ctx.evidence_write("kit-gates.json", {
        "leader": {"rows": leader_rows, "evidence": leader_evidence},
        "ability": {"rows": ability_rows, "evidence": ability_evidence},
        "skills": skill_gates, "pursuit": pursuit_gate,
        "unique_condition": {key: {"row": row, "icon": icon}},
        "effect_family": {k: family[k] for k in ("src_dir", "dst_dir", "layout", "copied_bases",
                                                 "complete_family", "missing_effects")},
        "fx_lut": bool(lut), "voice_route": route, "voice_ready": voice_ready,
        "pixel": pixel, "mirrors": mirrors, "action_skill": action_rows,
    })

    notes = [
        "技能：官方**自身**母本 111141 的 _1/_2 树只改参数（不跨角色拼树）——"
        "skill1 10段×5.5=55×，skill2 满级 10段×8.5=85×（未强化档55×/SLv1 70×，带78-95✓）；"
        "PF伤害buff skill1 +150%/16s、skill2 +200%/20s；ComboBoost skill1 持续2次弹射+10、"
        "skill2 持续3次弹射+12~15；tree[10]=0 保持（技能伤害归属，donor 原值不动）",
        f"629「开匣·月华」：官方 fire_dragon_zenith 原树只改倍率(3.75~5.0→{PURSUIT_MULT['min']}~"
        f"{PURSUIT_MULT['max']}，4段×{PURSUIT_MULT['max']}=40×)与内层爆裂特效路径；"
        "tree[10] 0→3（按强化弹射伤害结算，这是本设计的卖点）；外层オーラ演出保留官方 "
        "fire_dragon_zenith 引用不动（未克隆，只引用不改色的官方特效直接引用，框架 §10.3）",
        f"特效族只克隆 1 族 {FX_DST_DIR}（basename 保留官方前缀 {TEMPLATE_CODE}_*，"
        "clone_effect_family 的 codename 布局不支持「目标即角色根目录、basename 改名」，见 deviations）"
        + ("；已套用 B/pixel/mia/fx_lut.json 换色（红/绿/蓝三色礼盒统一为金/琥珀/暖白）"
           if lut else "；无 fx_lut.json，按母本原色克隆"),
        "面板：队长 8 行共享同一 c0 ⇒ 整块被 desc_override_tiger_treasure_hunter_moon 覆盖；"
        "词条 6 键 15 条无覆盖，按 wf_describe 原文逐条显示",
        {"pixel_install": pixel},
    ]
    deviations = [
        {"want": "design/mia.json plan.skills.effects_clone：dst 目录直接是 "
                 f"battle/effect/skill_unique/{CODE}/（无子目录），basename 改成 {CODE}_*",
         "got": f"clone_effect_family(layout='codename') 强制 skill_unique/<code>/<dst_subdir>/ 两级目录"
                "（预载器规则：sheet/atlas 必须与目录同名）；dst_subdir 定为 "
                f"{FX_SUBDIR!r}，basename 保留官方前缀 {TEMPLATE_CODE}_*（DSL 引用统一走 "
                "rewrite_effect_refs 改写目录前缀，引用正确性不受影响）",
         "why": "同批玛格诺斯 kit 已实测同一框架限制（wf_midautumn_kit_magnus.py 偏离 D12）：框架的 "
                "codename 布局不支持「目标即角色根目录、basename 改名」这一形状，只是路径命名差异，"
                "不影响图集增量或引用正确性"},
    ]
    for entry in design.get("deviations", ()):
        want = entry.get("原设想") or entry.get("want")
        got = entry.get("实际落法") or entry.get("got")
        why = entry.get("原因") or entry.get("why")
        deviations.append({"want": want, "got": got, "why": why})

    gate = {"rows": len(leader_evidence) + len(ability_evidence), "programs": len(programs),
            "pixel_present": pixel["present"], "pixel_missing": [e["logical"] for e in pixel["skipped"]]}
    ready = pixel["present"] and not pixel["skipped"]
    gate["reason"] = "kit 自有产物全部过闸" if ready else \
        f"像素成品未就绪：{gate['pixel_missing'] or 'B/pixel/mia/install.json 不存在'}"

    return KL.report(
        ctx, summary="米娅：火属性 +c 连发型强化弹射主 C（桂灯循环 → 629 追击「开匣·月华」）",
        status=KL.READY if ready else KL.DRAFT, panel=panel, notes=notes, programs=programs,
        unique_condition={key: {"name": UNIQUE_NAME, "cap": UNIQUE_CAP, "icon": UNIQUE_ICON_LOGICAL}},
        required_capabilities=sorted(capabilities | set(SPEC["required_capabilities"])),
        deviations=deviations,
        extra={"custom_ability_string": sorted(cas_plan), "effect_families": [FX_DST_DIR],
               "kit_gate": gate, "voice_route": route})
