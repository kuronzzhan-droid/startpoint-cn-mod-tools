# -*- coding: utf-8 -*-
"""索利兹 129986 · 完成态 kit（中秋批次 / GBF 导入包 `gbf-soriz-20260919`）。

设计真源：``work/character_packs/midautumn-20260920/design/soriz.md`` / ``soriz.json``
（主控裁决 §1/§2/§3/§6/§8 与作者决定「按 wfchar 原稿；扣 Fever 能实现」）。

本模块只写候选包（`work/character_packs/gbf-soriz-20260919/package`）与它的 evidence，
**不碰 live store / assets / .cdn / 设备 / 存档，不发布**。

装配纪律（裁决 §6）：
- 行一律「官方 donor 行 + 逐格改」：内容块与触发块分别整块搬（``_compose``），逐行过
  ``wf_client_legality`` 三件套 + ``invoke_skill_string_problems``，并与设计稿登记的
  cells / describe 文案逐字核对（漂移即报错）。
- DSL 从官方 donor 树改参数；``write_dsl`` 只吃裸树，写后回读 ``parse_dsl`` 自检。
- ``CreateCondition`` 下标 10（付与对象种类）按**所在选择器**取值：官方 rare5 语料
  FindAllSubjects 33/34/49/82 → 3（33 共 195 处）、97 球 → 2、无 FindAll 的自身(-17) → 3
  （198 处）。写错 = 施法 C16102（记忆卡 wf-createcondition-target-kind）。
- 固有状态上限一律不写 ``(None)``（wf-unique-cap-none-trap）。
- 629 的 string_id 必须在 ``custom_ability_string`` 有同键行，否则详情页 C8601。
"""
from __future__ import annotations

import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    pass  # Imports resolve from this checkout/package, not external source copies.

import wf_client_legality as L  # noqa: E402
import wf_describe  # noqa: E402
import wf_dsl  # noqa: E402

# ------------------------------------------------------------------ 身份 / 常量

CID = 129986
CID_S = "129986"
CODE = "soriz"
ELEMENT = 1                 # 水（内部码 1）
DSL_ELEMENT = 2             # DSL 显式元素 = 内部 + 1（wf-dsl-element-code-offset）
FIND_PARTY = 33             # 己方全体（含自身）—— 裁决 §8：35 是「除自身外」
FIND_ENEMY = 49
GRANT_MEMBER = 3            # CreateCondition 下标 10

ABILITY = "master/ability/ability.orderedmap"
LEADER = "master/ability/leader_ability.orderedmap"
UNIQUE = "master/character/unique_condition.orderedmap"
CAS = "master/string/custom_ability_string.orderedmap"
PFA = "master/skill/power_flip_action.orderedmap"
ACTION = "master/skill/action_skill.orderedmap"
TEXT = "master/character/character_text.orderedmap"

CROWS, VET, GUTS, HEAT, BURN, DUO = (12998601, 12998602, 12998603,
                                     12998604, 12998605, 12998606)
UNIQUE_IDS = (CROWS, VET, GUTS, HEAT, BURN, DUO)

AP = "battle/action/skill/action/ability_skill/{0}${0}"
PROGRAMS = ("soriz_fever_begin", "soriz_fever_end", "soriz_adversity_tick",
            "soriz_assist_eugen", "soriz_assist_jin", "soriz_assist_duo",
            "soriz_heat_end", "soriz_heat_begin", "soriz_pf_resist")
PF_KEY = "override_soriz_fever_special"
PF_STRING = "override_string_soriz_fever_special"
PF_PATH = "battle/action/power_flip/action/override/{k}${k}_lv{n}"
SKILL_PATH = "battle/action/skill/action/rare5/{0}${0}_{1}"
DONOR_SKILL = "battle/action/skill/action/rare5/waterdragon_kunfu$waterdragon_kunfu_2"
DONOR_SPECIAL = "battle/action/power_flip/action/special$special_lv{n}"

DESC_KEYS = (f"desc_override_{CODE}_leader",
             *[f"desc_override_{CODE}_{i}" for i in range(1, 7)])
CAS_KEYS = (*DESC_KEYS, *PROGRAMS, PF_STRING)

EFFECT_DIR = "battle/effect/skill_unique/soriz"
FX_SKILL, FX_EUGEN, FX_JIN = "04164345c46a", "78c360966612", "be59886986c7"
# 大招特效改「整路径引用官方 donor 的水拳演出」：作者决定「技能特效可拼接任意官方角色的
# 技能特效」＋裁决 §4「优先直接引用官方路径（不复制不占图集）」。跨 code_name 引用官方特效
# 不会「数据不足」（记忆卡 wf-effect-family-under-codename 2026-09-10 更正：
# AssetPathCollectionBuilder 按路径推 sheet，无 code_name 过滤，线上已有 7 组真跨角色引用）。
FX_OFFICIAL_SKILL = "battle/effect/skill_unique/waterdragon_kunfu/waterdragon_kunfu"
FX_DROP = ("1b7a2cc19dec", "53da6a4c9793", "334d4d577f51", "39c6a55e6971", FX_SKILL)
# 仁援护按设计稿自己的目标（≤ 512×256 ≈ 0.13 Mpx）重打；宽度锁死让它出方块而不是宽条，
# 宽条在 4096 货架上抢宽度，是 five-boss-r1 装不下的直接原因。
FX_REPACK = {FX_JIN: 0.375}
FX_REPACK_WIDTH = {FX_JIN: 384}
SOURCE_ZIP = "soriz-compiled.zip"
SOURCE_MEMBER = "compiled/common/{0}"

DESIGN_REL = "work/character_packs/midautumn-20260920/design/soriz.json"

CAPABILITIES = ("kyubi-fever-ratio-v1", "panel-description-override-v2")

# ability c2 雕像组：裁决 §8「每个键必须单值」。按官方语料挑覆盖该键全部 kind 的组；
# 混合键取官方最常用的 special（1299862 的 153、1299866 的 18 在该组上是新组合，见 kit-report
# deviations）。1299861 = action_skill（211/245/50/213 全有官方先例）、1299865 = attack_common。
STATUE = {1: "action_skill", 2: "special", 3: "special", 4: "special",
          5: "attack_common", 6: "special"}

# ---- 2026-09-27 平衡调整第二批（作者口径 A/B，修订模块 ``wf_balance_20260927b_gbf.py``；
# 本 kit 输出必须 == 修订模块 revise() 输出，测试 test_balance_20260927b_gbf 断言）。
#: 三羽乌逐层成长：(内容 kind, 名称, 改前每层, 能力3 封顶版每层, 队长每层)。强度单位 1000 = 1%。
#: 能力3 #1-#3 原为「每层、不设上限」→ 能力侧改为最多计 CROWS_CAP 层；原行（无上限）搬进队长并放缓 1/5
#: （3 分钟约 23–27 次触发，落 15–30 档 ⇒ 1/5；413 的 0.6% 按复核 C09 取 0.5%）。
#: 同日第三轮（c，成长复核，``wf_balance_20260927c_soriz.py``；作者「1/10 砍太多了」「可以砍到2/3」「数值尽量取5的
#: 倍数」）：队长每层回调到 2/3 档 —— 100×2/3 向上取 70%、3×2/3=2%；能力3 封顶版不动。
CROWS_CAP = 10
CROWS_GROWTH = ((0, "攻击力", 100000, 15000, 70000),
                (23, "PF伤害", 100000, 10000, 70000),
                (413, "独立乘区PF伤害", 3000, 1000, 2000))
#: 三棵援护 629 的 CreateNormalAttack p13（削韧）：口径 B3 每次 ≤3（CT 15 秒 / 每次 Fever 至多 1 次）。
ASSIST_TOUGHNESS = 3
#: Fever 特殊 PF 分支的 p13：(第一判定区每段, 终结段)。11 段 + 1 段 = 15 / 20 / 25（口径 B2 顶到每级上限）；
#: 非 Fever 分支是官方 special 原树副本（5/5/6.25 × 3–4 段 = 15/20/25），不动。
PF_FEVER_TOUGHNESS = {1: (1.25, 1.25), 2: (1.5, 3.5), 3: (2, 3)}

SPEC = {
    "required_capabilities": CAPABILITIES,
    "extra_keys": {
        UNIQUE: tuple(str(u) for u in UNIQUE_IDS),
        CAS: CAS_KEYS,
        PFA: (PF_KEY,),
    },
}


class KitError(RuntimeError):
    pass


# ------------------------------------------------------------------ 表布局

_EM = wf_describe.enum_map()
LAY = {name: {k: int(v) for k, v in _EM["layouts"][name]["blocks"].items()}
       for name in ("ability", "leader_ability")}
MODE_COL = {"ability": 5, "leader_ability": 3}
BLKLEN = {"precondition": 7, "instant_trigger": 12, "during_trigger": 11,
          "instant_precontent": 7, "instant_content": 38, "during_content": 14,
          "during_accumulation_trigger": 12}
NCOLS = {"ability": 126, "leader_ability": 124}


def g(row: Sequence[str], i: int) -> str:
    return row[i] if i < len(row) else ""


def rinfo(row: Sequence[str], table: str) -> dict[str, str]:
    b = LAY[table]
    if g(row, MODE_COL[table]) == "1":
        return {"mode": "D", "tk": g(row, b["during_trigger"]),
                "ck": g(row, b["during_content"]),
                "target": g(row, b["during_content"] + 1)}
    return {"mode": "I", "tk": g(row, b["instant_trigger"]),
            "ck": g(row, b["instant_content"]),
            "target": g(row, b["instant_content"] + 1)}


# ------------------------------------------------------------------ donor 检索


class Rows:
    """官方 / store 表的行索引；donor 一律先官方（``.cdn/cn`` 归档），store 只用于
    官方零先例的 kind（629 / 724 / 189）。

    2026-09-27：store donor 一律按设计稿记录的键钉死。按「store 里第一条 ck=724」全表检索会随 live
    变动漂移——1.4.1050 风巨蜥能力3 #4 改成 724 后排在前面，把它的持续块残值带进了本角色 A3#8。
    键内再按行号钉（``key=``/``idx=``）也会漂：别的单元在该键增删行时行号就换了内容（稻穗 inaho2 把
    1399951 从 6 行删到 4 行，724 行从第 4 行挪到第 2 行）。所以键内行号会变的 donor 用 ``key=`` + 内容条件
    （键内第一条匹配，标签 ``{src}:{table}[{key}]{mode=…,ck=…}`` 不带行号）；``idx=`` 只留给行号稳定的键。"""

    def __init__(self, ctx) -> None:
        self.ctx = ctx
        self._cache: dict[tuple[str, str], list] = {}

    def index(self, src: str, table: str) -> list:
        key = (src, table)
        if key not in self._cache:
            logical = ABILITY if table == "ability" else LEADER
            flat = self.ctx.official_flat(logical) if src == "official" else self.ctx.live_flat(logical)
            self._cache[key] = [(k, i, row, rinfo(row, table))
                                for k, text in flat.items()
                                for i, row in enumerate(self.ctx.csv_split(text))]
        return self._cache[key]

    def find(self, table: str, *, src: str, mode: str | None = None, tk: Any = None,
             ck: Any = None, target: Any = None, puller: Any = None,
             key: str | None = None, idx: int | None = None) -> tuple[str, list[str]]:
        """``key`` + ``idx``：钉死键#行；``key`` + 条件：该键内第一条满足条件的行（标签不带行号）；
        只给条件：全表第一条。"""
        b = LAY[table]
        query = [(name, value) for name, value in (("mode", mode or None), ("tk", tk), ("ck", ck),
                                                   ("target", target), ("puller", puller))
                 if value is not None]
        if key is not None and idx is None and not query:
            raise KitError(f"donor {src}/{table}[{key}] needs idx= or a content condition")
        for k, i, row, info in self.index(src, table):
            if key is not None:
                if k != key:
                    continue
                if idx is not None:
                    if i == idx:
                        return f"{src}:{table}[{k}]#{i}", list(row)
                    continue
            if mode and info["mode"] != mode:
                continue
            if tk is not None and info["tk"] != str(tk):
                continue
            if ck is not None and info["ck"] != str(ck):
                continue
            if target is not None and info["target"] != str(target):
                continue
            if puller is not None:
                base = b["during_trigger"] if info["mode"] == "D" else b["instant_trigger"]
                if g(row, base + 1) != str(puller):
                    continue
            if key is not None:
                return f"{src}:{table}[{k}]{{{','.join(f'{n}={v}' for n, v in query)}}}", list(row)
            return f"{src}:{table}[{k}]#{i}", list(row)
        raise KitError(f"no donor {src}/{table} key={key} idx={idx} mode={mode} tk={tk} ck={ck} "
                       f"target={target} puller={puller}")


def _copy_block(dst: list[str], src: Sequence[str], table: str, block: str) -> list[str]:
    base = LAY[table][block]
    for off in range(BLKLEN[block]):
        while len(dst) <= base + off:
            dst.append("")
        dst[base + off] = g(src, base + off)
    return dst


P0 = ("0",)
RES = ("2", "", "", 600000, 600000, "Blue", "")          # 水属性共鸣（编成≥6）
FEV = ("12",)
NOF = ("186",)
LDR = ("42",)


def UNI(uid: int, n: int = 1) -> tuple:
    """前置 144 ConditionAccumulationCountUnique：数的是层数（前置 188 数实例数，恒 1）。"""
    return ("144", "0", "", n * 100000, n * 100000, "", uid)


def HAS(uid: int) -> tuple:
    return ("187", "0", "", "", "", "", uid)


def HPLOW(pct: int) -> tuple:
    return ("205", "0", "", pct * 1000, pct * 1000, "", "")


class Composer:
    def __init__(self, ctx, design: Mapping[str, Any]) -> None:
        self.ctx = ctx
        self.rows = Rows(ctx)
        self.design = design
        self.records: list[dict[str, Any]] = []

    def compose(self, tag: str, table: str, content: Mapping[str, Any],
                trigger: Mapping[str, Any] | None, pres: Sequence[Sequence],
                cells: Mapping[int, Any]) -> list[str]:
        cname, row = self.rows.find(table, **content)
        row = list(row)
        tname = ""
        if trigger:
            tname, tdon = self.rows.find(table, **trigger)
            mode = rinfo(tdon, table)["mode"]
            _copy_block(row, tdon, table, "during_trigger" if mode == "D" else "instant_trigger")
            if mode == "I":
                _copy_block(row, tdon, table, "instant_precontent")
                row[LAY[table]["instant_delay"]] = g(tdon, LAY[table]["instant_delay"])
            else:
                base = LAY[table]["during_accumulation_trigger"]
                for off in range(BLKLEN["during_accumulation_trigger"]):
                    while len(row) <= base + off:
                        row.append("")
                    row[base + off] = "(None)" if off == 0 else ""
                row[LAY[table]["even_if_owner_dead"]] = "false"
        for slot in (1, 2, 3):
            base = LAY[table][f"precondition{slot}"]
            values = list(pres[slot - 1]) if slot - 1 < len(pres) else ["0"]
            values += [""] * (7 - len(values))
            for off in range(7):
                while len(row) <= base + off:
                    row.append("")
                row[base + off] = str(values[off])
        for col, value in cells.items():
            col = int(col)
            while len(row) <= col:
                row.append("")
            row[col] = str(value)
        while len(row) < NCOLS[table]:
            row.append("")
        return self._record(tag, table, row, cname, tname)

    def derive(self, tag: str, table: str, row: Sequence[str], cells: Mapping[int, Any],
               source: str) -> list[str]:
        """不搜 donor：在已装配好的行上逐格改（例：能力行搬进队长），同样过闸门并登记。"""
        row = list(row)
        for col, value in cells.items():
            col = int(col)
            while len(row) <= col:
                row.append("")
            row[col] = str(value)
        if len(row) != NCOLS[table]:
            raise KitError(f"{tag}: {len(row)} columns, expected {NCOLS[table]}")
        return self._record(tag, table, row, source, "")

    def _record(self, tag: str, table: str, row: list[str], cname: str, tname: str) -> list[str]:
        problems = (L.client_legality_problems(table, row)
                    + L.declared_block_field_problems(table, row)
                    + L.invoke_skill_string_problems(row, set(CAS_KEYS), table)
                    + L.ability_element_column_problems(table, row, ELEMENT))
        if problems:
            raise KitError(f"{tag}: client legality rejected the row: {problems}")
        self.records.append({
            "tag": tag, "table": table, "ncols": len(row),
            "content_donor": cname, "trigger_donor": tname,
            "describe": wf_describe.describe_line(row, table),
            "capabilities": L.required_client_capabilities(table, row),
            "cells": {str(i): c for i, c in enumerate(row) if c != ""},
        })
        return row


def leader_from_ability(row: Sequence[str], leader_c0: str) -> list[str]:
    """口径 A3：能力行搬进队长 = ``[队长 c0, '0', ''] + 能力行[5:]``（能力 c≥5 → 队长 c−2）。"""
    if len(row) != NCOLS["ability"]:
        raise KitError(f"ability row has {len(row)} columns")
    return [leader_c0, "0", ""] + list(row[5:])


def crows_row(co: "Composer", tag: str, ck: int, val: int, limit: Any) -> list[str]:
    """能力3「三羽乌每层 → 自身 X」during 134 行（``limit`` = c102 最多计层数，``(None)`` = 不设上限）。"""
    T = "ability"
    B = LAY[T]
    DC, DT = B["during_content"], B["during_trigger"]
    cells = {0: f"{CODE}_3", 1: "false", 2: STATUE[3], 3: "0",
             DT: 134, DT + 1: 0, DT + 2: "", DT + 3: 100000, DT + 4: 100000,
             DT + 5: limit, DT + 6: "", DT + 7: CROWS, DT + 8: "", DT + 9: "",
             DC: ck, DC + 4: val, DC + 5: val}
    if ck == 0:
        cells[DC + 1] = 0
        cells[DC + 2] = ""
    return co.compose(
        tag, T,
        dict(src="official", mode="D", ck=ck, puller=9) if ck != 413
        else dict(src="official", mode="D", ck=413),
        dict(src="official", mode="D", tk=134), [P0, P0, P0], cells)


# ------------------------------------------------------------------ 行装配


def build_rows(ctx, design) -> tuple[list[list[str]], dict[str, list[list[str]]], Composer]:
    co = Composer(ctx, design)
    T = "leader_ability"
    B = LAY[T]
    IC, DC, IT, DT = (B["instant_content"], B["during_content"],
                      B["instant_trigger"], B["during_trigger"])
    SID = {0: f"{CODE}_leader", 1: "0"}
    leader: list[list[str]] = []

    leader.append(co.compose(
        "L#0 全队(水)攻击力+100%", T,
        dict(src="official", mode="I", ck=32, target=5),
        dict(src="official", mode="I", tk=0, ck=32), [P0, P0, P0],
        {**SID, IC: 32, IC + 1: 5, IC + 2: "Blue", IC + 4: 100000, IC + 5: 100000}))
    leader.append(co.compose(
        "L#1 自身强化弹射伤害+100%", T,
        dict(src="official", mode="I", ck=55),
        dict(src="official", mode="I", tk=0, ck=55), [P0, P0, P0],
        {**SID, IC: 55, IC + 4: 100000, IC + 5: 100000}))
    leader.append(co.compose(
        "L#2 水共鸣+Fever中 自身PF伤害+300%", T,
        dict(src="official", mode="D", ck=23),
        dict(src="official", mode="D", tk=4), [RES, P0, P0],
        {**SID, DC: 23, DC + 4: 300000, DC + 5: 300000}))
    leader.append(co.compose(
        "L#3 水共鸣+Fever 每次弹射连击+16", T,
        dict(src="official", mode="I", ck=226),
        dict(src="official", mode="I", tk=6), [RES, FEV, P0],
        {**SID, IT: 6, IT + 3: 100000, IT + 4: 100000, IT + 7: "(None)", IT + 8: 0,
         IC: 226, IC + 4: 1600000, IC + 5: 1600000}))
    leader.append(co.compose(
        "L#4 722 Fever特殊PF覆盖", T,
        dict(src="official", key="141201", idx=1),
        dict(src="official", key="141201", idx=1), [RES, P0, P0],
        {**SID, IC: 722, IC + 35: PF_KEY, IC + 36: "1,2,3", IC + 37: PF_STRING}))
    for tag, trig, name in (("L#5 629 进Fever", 8, "soriz_fever_begin"),
                            ("L#6 629 Fever结束", 184, "soriz_fever_end")):
        leader.append(co.compose(
            tag, T,
            dict(src="official", key="111183", idx=4),
            dict(src="official", key="111183", idx=4), [RES, P0, P0],
            {**SID, IT: trig, IT + 3: 100000, IT + 4: 100000, IT + 7: "(None)", IT + 8: 0,
             IC: 629, IC + 23: name, IC + 24: AP.format(name)}))
    for tag, ck, val in (("L#7 自身每失血1%→攻击力+5%", 0, 5000),
                         ("L#8 自身每失血1%→PF伤害+10%", 23, 10000)):
        cells = {**SID, DT: 110, DT + 1: 0, DT + 2: "", DT + 3: 1000, DT + 4: 1000,
                 DT + 5: 100, DT + 6: "", DT + 7: "", DT + 8: 100000, DT + 9: 100000,
                 DC: ck, DC + 4: val, DC + 5: val}
        if ck == 0:
            cells[DC + 1] = 0
            cells[DC + 2] = ""
        leader.append(co.compose(
            tag, T, dict(src="official", mode="D", ck=ck, puller=9),
            dict(src="official", mode="D", tk=110, puller=9), [P0, P0, P0], cells))

    # 2026-09-27b：能力3 原「三羽乌每层 → 自身 X（不设上限）」三行原样搬进队长，只把每层强度放缓 1/5。
    # 队长原本没有同触发（during 134 / 三羽乌）的行 ⇒ 不合并、新起三行。母本行用临时 Composer 装配
    # （与搬入前的 live 行逐字相同），不登记进本 kit 的 records。
    scratch = Composer(ctx, design)
    scratch.rows = co.rows
    LD = LAY[T]["during_content"]
    for n, (ck, name, legacy, _capped, per_layer) in enumerate(CROWS_GROWTH, start=1):
        moved = crows_row(scratch, f"A3#{n} 搬入前", ck, legacy, "(None)")
        leader.append(co.derive(
            f"L#{8 + n} 每层三羽乌 {name}+{per_layer / 1000:g}%", T,
            leader_from_ability(moved, SID[0]), {LD + 4: per_layer, LD + 5: per_layer},
            f"move:ability[{CID}3]#{n}"))

    # ---------------------------------------------------------------- 词条表
    T = "ability"
    B = LAY[T]
    IC, DC, IT, DT, PC = (B["instant_content"], B["during_content"], B["instant_trigger"],
                          B["during_trigger"], B["instant_precontent"])

    def head(slot: int, main: bool = False) -> dict[int, Any]:
        return {0: f"{CODE}_{slot}", 1: "false" if main else "true", 2: STATUE[slot], 3: "0"}

    ab: dict[str, list[list[str]]] = {f"{CID}{i}": [] for i in range(1, 7)}

    # 能力 1
    ab["1299861"].append(co.compose(
        "A1#0 水共鸣 全队(水)技能槽+100%", T,
        dict(src="official", mode="I", ck=211, target=5),
        dict(src="official", mode="I", tk=0, ck=211), [RES, P0, P0],
        {**head(1), IC: 211, IC + 1: 5, IC + 2: "Blue",
         IC + 4: 100000, IC + 5: 100000}))
    ab["1299861"].append(co.compose(
        "A1#1 水共鸣 全队(水)最大技能槽+30%", T,
        dict(src="official", mode="I", ck=245, target=5),
        dict(src="official", mode="I", tk=0, ck=245), [RES, P0, P0],
        {**head(1), IC: 245, IC + 1: 5, IC + 2: "Blue",
         IC + 4: 30000, IC + 5: 30000}))
    ab["1299861"].append(co.compose(
        "A1#2 水共鸣 全队(水)Fever获取+50%", T,
        dict(src="official", mode="I", ck=50, target=5),
        dict(src="official", mode="I", tk=0, ck=50), [RES, P0, P0],
        {**head(1), IC: 50, IC + 1: 5, IC + 2: "Blue",
         IC + 4: 50000, IC + 5: 50000}))
    for tag, trig, pull, val, lim in (
            ("A1#3 非Fever 每次PF3 +350 Fever", 65, "", 35000000, "(None)"),
            ("A1#4 非Fever 发动技能 +650 Fever", 23, "0", 65000000, "(None)"),
            ("A1#5 非Fever 首次发动技能 +1500 Fever", 23, "0", 150000000, "1")):
        ab["1299861"].append(co.compose(
            tag, T, dict(src="official", mode="I", ck=213),
            dict(src="official", mode="I", tk=trig, ck=213) if trig == 23
            else dict(src="official", mode="I", tk=65),
            [NOF, P0, P0],
            {**head(1), IT: trig, IT + 1: pull, IT + 2: "", IT + 3: 100000,
             IT + 4: 100000, IT + 7: lim, IT + 8: 0, IT + 9: "",
             IC: 213, IC + 4: val, IC + 5: val}))

    # 能力 2
    ab["1299862"].append(co.compose(
        "A2#0 每3次PF3 得1层老当益壮", T,
        dict(src="official", mode="I", ck=461),
        dict(src="official", mode="I", tk=65), [P0, P0, P0],
        {**head(2), IT: 65, IT + 3: 300000, IT + 4: 300000,
         IT + 7: "(None)", IT + 8: 0, IC: 461, IC + 1: 0, IC + 4: 100000,
         IC + 5: 100000, IC + 12: 100000, IC + 13: 100000, IC + 21: VET}))
    for tag, ck, val in (("A2#1 Lv1 攻击力+200%", 0, 200000),
                         ("A2#2 Lv1 PF伤害+300%", 23, 300000)):
        cells = {**head(2),
                 DT: 134, DT + 1: 0, DT + 2: "", DT + 3: 100000, DT + 4: 100000,
                 DT + 5: 1, DT + 6: "", DT + 7: VET, DT + 8: "", DT + 9: "",
                 DC: ck, DC + 4: val, DC + 5: val}
        if ck == 0:
            cells[DC + 1] = 0
            cells[DC + 2] = ""
        ab["1299862"].append(co.compose(
            tag, T, dict(src="official", mode="D", ck=ck, puller=9),
            dict(src="official", mode="D", tk=134), [P0, P0, P0], cells))
    ab["1299862"].append(co.compose(
        "A2#3 Lv2 每3次PF3 下次弹射连击+99", T,
        dict(src="official", mode="I", ck=489),
        dict(src="official", mode="I", tk=65), [UNI(VET, 2), P0, P0],
        {**head(2), IT: 65, IT + 3: 300000, IT + 4: 300000,
         IT + 7: "(None)", IT + 8: 0, IC: 489, IC + 4: 9900000, IC + 5: 9900000,
         IC + 12: 100000, IC + 13: 100000, IC + 15: 1}))
    ab["1299862"].append(co.compose(
        "A2#4 Lv2 非Fever 每次弹射连击+8", T,
        dict(src="official", mode="I", ck=226),
        dict(src="official", mode="I", tk=6), [UNI(VET, 2), NOF, P0],
        {**head(2), IT: 6, IT + 3: 100000, IT + 4: 100000,
         IT + 7: "(None)", IT + 8: 0, IC: 226, IC + 4: 800000, IC + 5: 800000}))
    ab["1299862"].append(co.compose(
        "A2#5 Lv3 队伍每失血1% PF伤害+20%", T,
        dict(src="official", mode="D", ck=23, puller=9),
        dict(src="official", mode="D", tk=110, puller=9), [UNI(VET, 3), P0, P0],
        {**head(2), DT: 110, DT + 1: 9, DT + 2: "", DT + 3: 1000,
         DT + 4: 1000, DT + 5: 100, DT + 7: "", DT + 8: 100000, DT + 9: 100000,
         DC: 23, DC + 4: 20000, DC + 5: 20000}))
    ab["1299862"].append(co.compose(
        "A2#6 Lv4 每5秒 629 给全队(水)逆境25~50%", T,
        dict(src="store", key="1611053", idx=0),
        dict(src="official", mode="I", tk=77), [UNI(VET, 4), P0, P0],
        {**head(2), IT: 77, IT + 3: 30000000, IT + 4: 30000000,
         IT + 7: "(None)", IT + 8: 0, IC: 629, IC + 23: "soriz_adversity_tick",
         IC + 24: AP.format("soriz_adversity_tick")}))
    ab["1299862"].append(co.compose(
        "A2#7 Lv5 PF3伤害特攻+15%", T,
        dict(src="official", mode="I", ck=153),
        dict(src="official", mode="I", tk=65), [UNI(VET, 5), P0, P0],
        {**head(2), IT: 65, IT + 3: 100000, IT + 4: 100000,
         IT + 7: 1, IT + 8: 0, IC: 153, IC + 4: 15000, IC + 5: 15000}))

    # 能力 3（Ⓜ 主位专用）
    ab["1299863"].append(co.compose(
        "A3#0 进Fever 得1层三羽乌", T,
        dict(src="official", mode="I", ck=461),
        dict(src="official", mode="I", tk=8), [P0, P0, P0],
        {**head(3, main=True), IT: 8, IT + 3: 100000, IT + 4: 100000,
         IT + 7: "(None)", IT + 8: 0, IC: 461, IC + 1: 0, IC + 4: 100000,
         IC + 5: 100000, IC + 12: 100000, IC + 13: 100000, IC + 21: CROWS}))
    # 2026-09-27b：封顶版——每层强度按 CROWS_GROWTH，最多计 CROWS_CAP 层（c102）；无上限部分已搬进队长。
    for n, (ck, name, _legacy, capped, _per_layer) in enumerate(CROWS_GROWTH, start=1):
        ab["1299863"].append(crows_row(
            co, f"A3#{n} 每层三羽乌 {name}+{capped / 1000:g}%(最多{CROWS_CAP}层)", ck, capped, CROWS_CAP))
    for tag, name, pres in (
            ("A3#4 Fever中 每次PF 欧根援护(CT15秒)", "soriz_assist_eugen", [FEV, P0, P0]),
            ("A3#5 非Fever 每次PF 仁援护(CT15秒)", "soriz_assist_jin", [NOF, P0, P0])):
        ab["1299863"].append(co.compose(
            tag, T, dict(src="store", key="1611053", idx=0),
            dict(src="official", mode="I", tk=2), pres,
            {**head(3, main=True), IT: 2, IT + 1: "", IT + 2: "",
             IT + 3: 100000, IT + 4: 100000, IT + 7: "(None)", IT + 8: 900,
             IC: 629, IC + 23: name, IC + 24: AP.format(name)}))
    ab["1299863"].append(co.compose(
        "A3#6 Fever中 首次PF3 双人援护(消耗合击预备)", T,
        dict(src="store", key="1611053", idx=0),
        dict(src="official", mode="I", tk=65), [FEV, HAS(DUO), P0],
        {**head(3, main=True), IT: 65, IT + 3: 100000, IT + 4: 100000,
         IT + 7: "(None)", IT + 8: 0,
         PC: 2, PC + 1: 0, PC + 2: "", PC + 3: 100000, PC + 4: 100000, PC + 5: "", PC + 6: DUO,
         IC: 629, IC + 23: "soriz_assist_duo", IC + 24: AP.format("soriz_assist_duo")}))
    ab["1299863"].append(co.compose(
        "A3#7 水共鸣+Fever+队长 每次PF 全队(水)15%护盾", T,
        dict(src="official", mode="I", ck=227),
        dict(src="official", mode="I", tk=2), [RES, FEV, LDR],
        {**head(3, main=True), IT: 2, IT + 1: "", IT + 3: 100000, IT + 4: 100000,
         IT + 7: "(None)", IT + 8: 0, IC: 227, IC + 1: 5, IC + 2: "Blue",
         IC + 4: 15000, IC + 5: 15000}))
    ab["1299863"].append(co.compose(
        "A3#8 水共鸣+Fever+队长 每次PF Fever槽-20%", T,
        dict(src="store", key="1399951", mode="I", ck=724),     # 稻穗能力1 的 724 行；行号随稻穗改版漂移，按内容取
        dict(src="official", mode="I", tk=2), [RES, FEV, LDR],
        {**head(3, main=True), IT: 2, IT + 1: "", IT + 3: 100000, IT + 4: 100000,
         IT + 7: "(None)", IT + 8: 0, IC: 724, IC + 1: "", IC + 4: -20000, IC + 5: -20000}))
    ab["1299863"].append(co.compose(
        "A3#9 队长 队友致死 消耗3层不死不休", T,
        dict(src="official", mode="I", ck=525),
        dict(src="store", key="1699976", idx=1), [LDR, P0, P0],
        {**head(3, main=True), IT: 189, IT + 1: 5, IT + 2: "",
         IT + 3: 100000, IT + 4: 100000, IT + 7: "(None)", IT + 8: 0,
         IC: 525, IC + 1: 0, IC + 4: 300000, IC + 5: 300000, IC + 21: GUTS}))
    ab["1299863"].append(co.compose(
        "A3#10 队长 队友致死 触发者4秒无敌", T,
        dict(src="official", mode="I", ck=16),
        dict(src="store", key="1699976", idx=1), [LDR, P0, P0],
        {**head(3, main=True), IT: 189, IT + 1: 5, IT + 2: "",
         IT + 3: 100000, IT + 4: 100000, IT + 7: "(None)", IT + 8: 0,
         IC: 16, IC + 1: 7, IC + 2: "", IC + 10: 24000000, IC + 11: 24000000,
         IC + 12: 100000, IC + 13: 100000, IC + 20: 1}))

    # 能力 4
    for n, thr in enumerate(range(90, 0, -10)):
        ab["1299864"].append(co.compose(
            f"A4#{n} 水共鸣 非Fever 自身HP首次跌破{thr}% → Fever+500", T,
            dict(src="official", mode="I", ck=213),
            dict(src="official", mode="I", tk=25), [RES, NOF, P0],
            {**head(4), IT: 25, IT + 1: 0, IT + 2: "", IT + 3: thr * 1000,
             IT + 4: thr * 1000, IT + 7: 1, IT + 8: 0, IT + 9: "",
             IC: 213, IC + 4: 50000000, IC + 5: 50000000}))
    ab["1299864"].append(co.compose(
        "A4#9 自身HP<50% 全队(水)技能加速10%", T,
        dict(src="official", mode="D", ck=3),
        dict(src="official", mode="D", tk=227), [P0, P0, P0],
        {**head(4), DT: 227, DT + 1: 0, DT + 2: "", DT + 3: 50000,
         DT + 4: 50000, DT + 5: "", DT + 6: "", DT + 7: "", DT + 8: "", DT + 9: "",
         DC: 3, DC + 1: 5, DC + 2: "Blue", DC + 4: 10000, DC + 5: 10000}))
    ab["1299864"].append(co.compose(
        "A4#10 自身HP<20%+Fever 每次PF 压敌方PF抗性至 -15%", T,
        dict(src="store", key="1611053", idx=0),
        dict(src="official", mode="I", tk=2), [HPLOW(20), FEV, P0],
        {**head(4), IT: 2, IT + 1: "", IT + 3: 100000, IT + 4: 100000,
         IT + 7: "(None)", IT + 8: 0, IC: 629, IC + 23: "soriz_pf_resist",
         IC + 24: AP.format("soriz_pf_resist")}))

    # 能力 5
    ab["1299865"].append(co.compose(
        "A5#0 水共鸣 每次进Fever PF伤害+100%(限10次)", T,
        dict(src="official", mode="I", ck=55),
        dict(src="official", mode="I", tk=8), [RES, P0, P0],
        {**head(5), IT: 8, IT + 3: 100000, IT + 4: 100000,
         IT + 7: 10, IT + 8: 0, IC: 55, IC + 4: 100000, IC + 5: 100000}))
    for tag, ck, val in (("A5#1 自身每失血1%→攻击力+5%", 0, 5000),
                         ("A5#2 自身每失血1%→PF伤害+10%", 23, 10000)):
        cells = {**head(5), DT: 110, DT + 1: 0, DT + 2: "", DT + 3: 1000,
                 DT + 4: 1000, DT + 5: 100, DT + 7: "", DT + 8: 100000, DT + 9: 100000,
                 DC: ck, DC + 4: val, DC + 5: val}
        if ck == 0:
            cells[DC + 1] = 0
            cells[DC + 2] = ""
        ab["1299865"].append(co.compose(
            tag, T, dict(src="official", mode="D", ck=ck, puller=0),
            dict(src="official", mode="D", tk=110, puller=0), [P0, P0, P0], cells))

    # 能力 6
    for tag, trig, name in (("A6#0 Fever结束 → 三羽乌换余热", 184, "soriz_heat_end"),
                            ("A6#1 进Fever → 余热换余热·燃", 8, "soriz_heat_begin")):
        ab["1299866"].append(co.compose(
            tag, T, dict(src="store", key="1611053", idx=0),
            dict(src="official", mode="I", tk=trig), [P0, P0, P0],
            {**head(6), IT: trig, IT + 1: "", IT + 2: "", IT + 3: 100000,
             IT + 4: 100000, IT + 7: "(None)", IT + 8: 0,
             IC: 629, IC + 23: name, IC + 24: AP.format(name)}))
    for tag, uid, ck, val, pres in (
            ("A6#2 非Fever 每层余热 PF伤害+30%", HEAT, 23, 30000, [NOF, P0, P0]),
            ("A6#3 非Fever 每层余热 全队(水)Fever获取+15%", HEAT, 18, 15000, [NOF, P0, P0]),
            ("A6#4 Fever中 每层余热·燃 PF伤害+50%", BURN, 23, 50000, [FEV, P0, P0])):
        cells = {**head(6), DT: 134, DT + 1: 0, DT + 2: "", DT + 3: 100000,
                 DT + 4: 100000, DT + 5: "(None)", DT + 6: "", DT + 7: uid,
                 DT + 8: "", DT + 9: "", DC: ck, DC + 4: val, DC + 5: val}
        if ck == 18:
            cells[DC + 1] = 5
            cells[DC + 2] = "Blue"
        ab["1299866"].append(co.compose(
            tag, T, dict(src="official", mode="D", ck=ck),
            dict(src="official", mode="D", tk=134), pres, cells))

    for key, rows in ab.items():
        slot = int(key[-1])
        for row in rows:
            if row[0] != f"{CODE}_{slot}":
                raise KitError(f"ability {key}: c0 {row[0]!r} != {CODE}_{slot}")
        if len({r[1] for r in rows}) != 1 or len({r[2] for r in rows}) != 1:
            raise KitError(f"ability {key}: mixed c1/c2 {[(r[1], r[2]) for r in rows]}")
    return leader, ab, co


def design_drift(co: Composer, design) -> list[str]:
    """逐行与设计稿 ``plan`` 的 cells / donor / describe 对照；漂移即报告。"""
    plan = design["plan"]
    expected: list[dict] = list(plan["leader_ability"]["rows"])
    for key in sorted(plan["ability"]["keys"]):
        expected.extend(plan["ability"]["keys"][key]["records"])
    drift: list[str] = []
    if len(expected) != len(co.records):
        return [f"row count {len(co.records)} != design {len(expected)}"]
    for want, got in zip(expected, co.records):
        tag = got["tag"]
        if want["donor"] != got["content_donor"]:
            drift.append(f"{tag}: content donor {got['content_donor']} != {want['donor']}")
        if want.get("trigger_donor") and want["trigger_donor"] != got["trigger_donor"]:
            drift.append(f"{tag}: trigger donor {got['trigger_donor']} != {want['trigger_donor']}")
        if want["cells"] != got["cells"]:
            diff = sorted(set(want["cells"]) ^ set(got["cells"])) or \
                [c for c in want["cells"] if want["cells"][c] != got["cells"].get(c)]
            drift.append(f"{tag}: cells differ at {diff[:6]}")
        if want.get("desc_expected") and want["desc_expected"] != got["describe"]:
            drift.append(f"{tag}: describe drift {got['describe']!r} != {want['desc_expected']!r}")
    return drift


# ------------------------------------------------------------------ DSL 构件


def V(x) -> list[dict]:
    return [{"min": x, "max": x}]


def SLV(base, vid=None, grown=None) -> list[dict]:
    cell: dict[str, Any] = {"min": float(base), "max": float(base)}
    if vid is not None:
        cell["vlv"] = [{"vid": int(vid), "min": 0.0, "max": float(grown)}]
    return [cell]


def CMD(name, *args) -> list:
    return ["Command", [name, *args]]


def BLOCK(*nodes) -> list:
    return ["Block", list(nodes)]


def TREE(*nodes, bta: int = 0) -> list:
    """``tree[10]`` = 伤害归属（0 自动 / 1 技能 / 2 能力 / 3 强化弹射 / 4 直击）。"""
    return ["ActionDsl", 1, ["None"], False, False, False, False, False, False, False,
            bta, BLOCK(*nodes)]


def FIND(subject: int, kind: int, *nodes, elements: Iterable[int] = ()) -> list:
    return CMD("FindAllSubjects", subject, kind, list(elements), [], [], [], [],
               ["DoNothing"], BLOCK(*nodes))


def COND(subject: int, *conditions, key: str = "", cancelable: bool = True,
         grant: int = GRANT_MEMBER, force: bool = False) -> list:
    return CMD("CreateCondition", subject, list(conditions), V(1),
               ["GenericConditionHitEffect"], cancelable, False, key, None, False,
               grant, V(1), force)


def DEL(subject: int, kind: list, key: str = "", cancelable_kind: int = 0) -> list:
    return CMD("DeleteCondition", subject, kind, 99, cancelable_kind, key, ["Default"])


def BUFF(kind: str, amount: float, frames: int = 900) -> list:
    return [kind, V(frames), V(amount), V(1)]


def EFFECT(eid: str, subject: int = -18, scale: float = 1.0) -> list:
    return CMD("ShowEffect", f"{CODE}_{eid}",
               ["SpecifyEffectDirectly", f"{EFFECT_DIR}/{eid}/effect"],
               subject, ["ForesideOfCharacter"], ["PlayOnlyFirstSequence"], ["AB"],
               0, 0, 0, True, False, ["Some", V(scale)])


def OFFICIAL_EFFECT(ctx, path: str, subject: int = -18) -> list:
    """官方特效整路径引用：整块搬官方 donor 的 ``ShowEffect`` 节点，只改主体与偏移。

    缩放/层次/播放模式一律沿用官方原值（那张图的 ``.parts`` 矩阵就是按它编排的），
    不自己编参数——省得重演 wf-dsl-param-shape-f1034 那类形状事故。
    """
    donor = ctx.template_dsl(DONOR_SKILL)
    node = next((n for n in _commands(donor, "ShowEffect")
                 if isinstance(n[2], list) and n[2][-1] == path), None)
    if node is None:
        raise KitError(f"official donor has no ShowEffect for {path}")
    node = deepcopy(node)
    node[3] = subject
    node[7] = node[8] = node[9] = 0      # 判定区内容块里按目标定位，官方那份的 y=-150 不适用
    return ["Command", node]


def WAIT(frames: int, *nodes) -> list:
    return ["Event", ["Wait", frames, "*", BLOCK(*nodes)]]


def hit_area(ctx, body: Sequence[list], *, radius: int = 150, life: int = 10,
             hits: int = 1, anchor: int = -18, offset_y: int = -150) -> list:
    """官方 ``waterdragon_kunfu_2`` 的近身判定区 donor，只改形状/寿命/段数/内容块。"""
    donor = ctx.template_dsl(DONOR_SKILL)
    node = deepcopy(_commands(donor, "CreateHitArea")[0])
    node[2] = anchor
    node[4], node[5] = 0, offset_y
    node[9] = ["Circle", V(radius)]
    node[13] = ["SpecifyHitAreaLifetimeDirectly", life]
    node[14] = ["CalculatedUsingMaxNumOfHits", hits]
    node[20] = BLOCK()
    node[21], node[22] = 10, 11
    node[23] = BLOCK(*body)
    return ["Command", node]


def normal_attack(ctx, subject: int, multiplier: float, *, vid: int | None = None,
                  grown: float | None = None, toughness: float | None = None) -> list:
    """``toughness`` 给了就改 p13（削韧，SLv 单格 {min,max} 同值）；不给沿用官方 donor 的 30。"""
    donor = ctx.template_dsl(DONOR_SKILL)
    node = deepcopy(_commands(donor, "CreateNormalAttack")[0])
    node[1] = subject
    node[2] = 255                      # 元素位：继承角色元素（wf-dsl-element-code-offset）
    node[6] = SLV(multiplier, vid, grown)
    if toughness is not None:
        node[13] = V(toughness)
    return ["Command", node]


def _commands(node, name: str) -> list[list]:
    out: list[list] = []

    def walk(n):
        if isinstance(n, list):
            if n and isinstance(n[0], str) and n[0] == name:
                out.append(n)
            for child in n:
                walk(child)
    walk(node)
    return out


def build_programs(ctx) -> dict[str, Any]:
    """9 棵 629 树 + 2 棵技能树 + 3 棵 722 覆盖树。"""
    programs: dict[str, Any] = {}

    # --- 进 FEVER：全队(水)禁疗 + 按已损失生命叠「不死不休」 + 低血给踏止
    ladder: list[list] = []
    for thr in range(90, 0, -10):
        low = [COND(-17, ["ACUnique", GUTS, V(1)], cancelable=False)]
        if thr == 70:
            low.append(FIND(0, FIND_PARTY,
                            COND(0, ["ACGuts", V(1)], key="soriz_guts", cancelable=False),
                            elements=(DSL_ELEMENT,)))
        ladder.append(CMD("ConditionalsHealthPointRatioOf", -17, thr, BLOCK(), BLOCK(*low)))
    programs["soriz_fever_begin"] = TREE(
        FIND(0, FIND_PARTY,
             COND(0, ["ACHealRejection", V(99999999)], key="soriz_fever_no_heal",
                  cancelable=False),
             elements=(DSL_ELEMENT,)),
        *ladder)

    programs["soriz_fever_end"] = TREE(
        FIND(0, FIND_PARTY,
             DEL(0, ["DCHealRejection"], "soriz_fever_no_heal"),
             DEL(0, ["DCGuts"], "soriz_guts"),
             elements=(DSL_ELEMENT,)),
        DEL(-17, ["DCUnique", GUTS]))

    programs["soriz_adversity_tick"] = TREE(
        FIND(0, FIND_PARTY,
             COND(0, ["ACAdversity", V(360), V(0.25), V(0.5), V(1)]),
             elements=(DSL_ELEMENT,)))

    # --- 欧根援护（FEVER 中）：余热·燃层数缩放 15→45 倍；水抗 −30%
    programs["soriz_assist_eugen"] = TREE(
        CMD("BindConditionAccumulationVariable", -17, 2, ["DCUnique", BURN], 1, 10),
        hit_area(ctx, [EFFECT(FX_EUGEN, subject=11, scale=1.0),
                       normal_attack(ctx, 11, 15.0, vid=2, grown=30.0,
                                     toughness=ASSIST_TOUGHNESS)],
                 radius=200, life=12, hits=1),
        FIND(0, FIND_ENEMY,
             COND(0, ["ACToleranceOfElement", V(900), DSL_ELEMENT, V(-0.3), V(1)])),
        COND(-17, ["ACUnique", CROWS, V(1)], cancelable=False), bta=3)

    # --- 仁援护（非 FEVER）：余热层数缩放 20→40 倍；+650 FEVER
    programs["soriz_assist_jin"] = TREE(
        CMD("BindConditionAccumulationVariable", -17, 2, ["DCUnique", HEAT], 1, 10),
        hit_area(ctx, [EFFECT(FX_JIN, subject=11, scale=0.8),
                       normal_attack(ctx, 11, 20.0, vid=2, grown=20.0,
                                     toughness=ASSIST_TOUGHNESS)],
                 radius=250, life=14, hits=1),
        CMD("AddFeverPoint", V(650)),
        COND(-17, ["ACUnique", CROWS, V(1)], cancelable=False), bta=3)

    # --- 双人援护：两张单人特效同播 + 大范围一击 60 倍
    programs["soriz_assist_duo"] = TREE(
        hit_area(ctx, [EFFECT(FX_EUGEN, subject=11, scale=1.4),
                       normal_attack(ctx, 11, 60.0, toughness=ASSIST_TOUGHNESS)],
                 radius=900, life=20, hits=1),
        WAIT(8, EFFECT(FX_JIN, subject=-18, scale=1.4)), bta=3)

    # --- 余热搬运（同帧「先赋予后删除」：不先删目标）
    def transfer(src_uid: int, dst_uid: int, *, cap: int = 10, extra: Sequence[list] = (),
                 clear_source: bool = False) -> list:
        body: list[list] = []
        for count in range(1, cap + 1):
            body.append(CMD("ConditionalsConditionAccumulationNumber", ["DCUnique", src_uid],
                            count, BLOCK(COND(-17, ["ACUnique", dst_uid, V(1)],
                                              cancelable=False)), BLOCK()))
        body.extend(extra)
        if clear_source:
            body.append(DEL(-17, ["DCUnique", src_uid]))
        return body

    programs["soriz_heat_end"] = TREE(
        *transfer(CROWS, HEAT),
        DEL(-17, ["DCUnique", BURN]),
        DEL(-17, ["DCUnique", DUO]))
    programs["soriz_heat_begin"] = TREE(
        *transfer(HEAT, BURN, clear_source=True,
                  extra=[CMD("ConditionalsConditionAccumulationNumber", ["DCUnique", HEAT], 5,
                             BLOCK(COND(-17, ["ACUnique", DUO, V(1)], cancelable=False)),
                             BLOCK())]))

    # --- 压敌方 PF 抗性：删光耐性增益（连不可驱散）+ 强制付与 −15%
    programs["soriz_pf_resist"] = TREE(
        FIND(0, FIND_ENEMY,
             # DC* 的 int 参数 = 驱散方向（2 = 增益）；cancelableKind 2 连不可驱散一起删
             # （官方 48 处先例，其中 28 处配 count 99）。
             DEL(0, ["DCPowerFlipDamageResistance", 2], cancelable_kind=2),
             COND(0, ["ACPowerFlipDamageResistance", V(900), V(-0.15), V(1)],
                  cancelable=False, force=True)))

    out = {AP.format(name): tree for name, tree in programs.items()}

    # --- 主动技能（能量 550）：自损 25% → 三羽乌+3 → 双 200% → 全队贯通/二连击 → 40 倍
    skill = TREE(
        CMD("StopBall", -18, 10, ["RestoreToSpeedBeforeActionExecution"], ["EF"], 0),
        CMD("CreateRatioAttack", -17, 2, V(0.25)),
        COND(-17, BUFF("ACAttackPoint", 2.0), BUFF("ACPowerFlipDamage", 2.0)),
        COND(-17, ["ACUnique", CROWS, V(3)], cancelable=False),
        FIND(0, FIND_PARTY,
             COND(0, ["ACPiercing", V(900)],
                  ["ACAdditionalDirectAttack", V(900), V(2), V(1), V(1)]),
             elements=(DSL_ELEMENT,)),
        WAIT(15, hit_area(ctx, [OFFICIAL_EFFECT(ctx, FX_OFFICIAL_SKILL, subject=11),
                                normal_attack(ctx, 11, 40.0)])))
    for level in ("1", "2"):
        out[SKILL_PATH.format(CODE, level)] = deepcopy(skill)

    # --- 722 覆盖：每档 = ConditionalsFeverMode(Fever 版, 官方 special 原树)
    for level in (1, 2, 3):
        official = ctx.template_dsl(DONOR_SPECIAL.format(n=level))
        normal_body = deepcopy(official[11])
        fever_body = deepcopy(official[11])
        areas = _commands(fever_body, "CreateHitArea")
        if len(areas) != 2:
            raise KitError(f"special_lv{level}: expected 2 hit areas, got {len(areas)}")
        first, final = areas
        final_mult = float(_commands(final, "CreateNormalAttack")[0][6][0]["min"])
        total = {1: 10.0, 2: 20.0, 3: 50.0}[level]
        per_hit = (total - final_mult) / 11.0
        first[13] = ["SpecifyHitAreaLifetimeDirectly", first[13][1] * 2]
        first[14] = ["CalculatedUsingMaxNumOfHits", 11]
        cna = _commands(first, "CreateNormalAttack")[0]
        cna[6] = SLV(round(per_hit, 6))
        # 2026-09-27b：p13（削韧）11 段 + 终结段 = 15/20/25（改前沿用官方每段 5/5/6.25 ⇒ 60/60/75）。
        per_segment, finisher = PF_FEVER_TOUGHNESS[level]
        cna[13] = V(per_segment)
        _commands(final, "CreateNormalAttack")[0][13] = V(finisher)
        root = deepcopy(official)
        root[11] = BLOCK(CMD("ConditionalsFeverMode", fever_body, normal_body))
        out[PF_PATH.format(k=PF_KEY, n=level)] = root
    return out


def program_problems(ctx, path: str, tree, baseline=None) -> list[str]:
    """``baseline`` 给了就做差分：官方 donor 树本来就报的问题（例如 CreateReferencePoint
    绑定的 subject 不在老检查器模型里）不算我方引入的新问题。"""
    from wf_seasonal7_kit_philia import signature_problems, scope_problems
    import wf_gbf_duo_kit as K
    problems = (signature_problems(tree) + scope_problems(tree)
                + K.draft_subject_problems(tree)
                + L.action_dsl_subject_binding_problems(tree)
                + L.action_dsl_hit_area_target_problems(tree)
                + L.action_dsl_element_problems(tree, character_element=ELEMENT)
                + wf_dsl.player_side_dsl_problems(tree))
    blob = wf_dsl.encode_amf3(tree)
    if wf_dsl.parse_dsl(blob)["tree"] != tree:
        problems.append("amf3 roundtrip mismatch")
    if baseline is not None:
        # 覆盖树把官方 body 复制两份（Fever 分支 + 原版分支），同一条官方问题会出现两次，
        # 所以按文本集合扣除，而不是按出现次数。
        known = {item.split(": ", 1)[1] for item in program_problems(ctx, path, baseline)}
        problems = [item for item in problems if item not in known]
    return [f"{path}: {p}" for p in problems]


# ------------------------------------------------------------------ 其他表


def unique_rows(ctx, design) -> tuple[dict[str, list[str]], dict[str, dict]]:
    donor_key = "11"
    donor = None
    flat = ctx.official_flat(UNIQUE)
    if donor_key in flat:
        donor = list(ctx.csv_split(flat[donor_key])[0])
    if donor is None:
        raise KitError("official unique_condition donor row 11 missing")
    icon_pool: list[str] = []
    for key in sorted(flat, key=lambda k: (len(k), k)):
        row = ctx.csv_split(flat[key])[0]
        if len(row) > 2 and row[2] and row[2] not in icon_pool:
            icon_pool.append(row[2])
    rows: dict[str, list[str]] = {}
    icons: dict[str, dict] = {}
    for n, entry in enumerate(design["plan"]["unique_conditions"]["add"]):
        row = list(donor)
        while len(row) < 15:
            row.append("")
        for col, value in enumerate(entry["row"]):
            row[col] = str(value)
        if len(row) != 15:
            raise KitError(f"unique_condition {entry['key']}: {len(row)} columns")
        if row[4] in ("", "(None)"):
            raise KitError(f"unique_condition {entry['key']}: cap {row[4]!r} = 1 层（无上限写 99）")
        rows[str(entry["key"])] = row
        icons[str(entry["key"])] = {"logical": f"{row[2]}.png", "donor": icon_pool[n % len(icon_pool)]}
    if sorted(rows) != sorted(str(u) for u in UNIQUE_IDS):
        raise KitError(f"unique_condition keys {sorted(rows)} != {UNIQUE_IDS}")
    return rows, icons


def install_icons(ctx, icons: Mapping[str, dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for uid, info in icons.items():
        donor_logical = f"{info['donor']}.png"
        raw = ctx.official_read(donor_logical, "common")
        if raw is None:
            _src, raw, _how = ctx.pack.template_asset(donor_logical)
        image = ctx.png_open(raw)
        data = ctx.png_store_bytes(image)
        ctx.write_asset("common", info["logical"], data)
        out[uid] = {"icon": info["logical"], "donor": donor_logical,
                    "size": list(image.size),
                    "sha256": hashlib.sha256(data).hexdigest()}
    return out


PROGRAM_TEXT = {
    "soriz_fever_begin": "FEVER开始：水属性角色无法获得治疗；按自身已损失的生命值获得「不死不休」。",
    "soriz_fever_end": "FEVER结束：解除禁疗与踏止，「不死不休」全部消失。",
    "soriz_adversity_tick": "水属性角色获得逆境25%～50%。",
    "soriz_assist_eugen": "欧根射击：造成强化弹射伤害，目标水属性抗性-30%，「三羽乌」+1层。",
    "soriz_assist_jin": "仁的斩击：造成强化弹射伤害并获得650FEVER，「三羽乌」+1层。",
    "soriz_assist_duo": "欧根与仁的合击：对大范围内的敌人造成一次强化弹射伤害。",
    "soriz_heat_end": "按「三羽乌」层数获得等量的「余热」。",
    "soriz_heat_begin": "消耗全部「余热」，转为本次FEVER的「余热·燃」。",
    "soriz_pf_resist": "清除敌人的强化弹射抗性上升效果，并强制使其强化弹射抗性-15%。",
}


def cas_rows(design) -> dict[str, list[list[str]]]:
    texts = design["plan"]["texts"]["custom_ability_string"]
    mapping = {
        f"desc_override_{CODE}_leader": texts[f"desc_override_{CODE}_leader"],
        **{f"desc_override_{CODE}_{i}": texts[f"desc_override_{CODE}_{i}"] for i in range(1, 7)},
        PF_STRING: texts[PF_STRING],
        **PROGRAM_TEXT,
    }
    if sorted(mapping) != sorted(CAS_KEYS):
        raise KitError(f"custom_ability_string keys {sorted(mapping)} != {sorted(CAS_KEYS)}")
    import wf_midautumn_kitlib as K
    for key, text in mapping.items():
        K.check_panel(text, label=key)
    return {key: [[text]] for key, text in mapping.items()}


def pf_action_row(ctx) -> list[str]:
    flat = ctx.official_flat(PFA)
    donor_key = next((k for k in flat if k.startswith("override_")), None)
    if donor_key is None:
        raise KitError("official power_flip_action has no override_* donor row")
    row = list(ctx.csv_split(flat[donor_key])[0])
    for n in (1, 2, 3):
        row[n - 1] = PF_PATH.format(k=PF_KEY, n=n)
    return row


# ------------------------------------------------------------------ 图集瘦身


def _pack_rects(sizes: Sequence[tuple[str, int, int]], width: int | None = None
                ) -> tuple[dict[str, tuple[int, int]], int, int]:
    """简单货架装箱（按高度降序），返回 {key: (x, y)} 与 sheet 尺寸。

    ``width`` 给了就锁死货架宽度（出方块而不是宽条）；不给沿用原来的 2 的幂自适应。
    """
    order = sorted(sizes, key=lambda item: (-item[2], -item[1], item[0]))
    if width is None:
        width = 1
        total = sum(w * h for _k, w, h in order)
        while width * width < total * 2 and width < 4096:
            width *= 2
    width = max(width, max((w for _k, w, _h in order), default=1))
    placed: dict[str, tuple[int, int]] = {}
    x = y = shelf = 0
    used_w = 0
    for key, w, h in order:
        if x + w > width:
            x, y, shelf = 0, y + shelf, 0
        placed[key] = (x, y)
        x += w
        used_w = max(used_w, x)
        shelf = max(shelf, h)
    return placed, used_w, y + shelf


def source_originals(source, eid: str) -> dict[str, bytes] | None:
    """作者 Studio 导出包里的**原始**特效三件套；拿不到返回 ``None``。

    从原图单次重采样，避免「已重打过的表再缩一次」的二次糊，也让这一步幂等：
    同一个 ``scale`` 跑几遍结果逐字节相同。
    """
    import zipfile
    root = Path(source) if source else None
    if root is None:
        try:
            import wf_gbf_duo as D
            root = Path(D.SOURCE)
        except Exception:
            return None
    archive = root / SOURCE_ZIP
    if not archive.is_file():
        return None
    want = {name: SOURCE_MEMBER.format(f"{EFFECT_DIR}/{eid}/{name}")
            for name in (f"{eid}.png", f"{eid}.atlas.amf3.deflate", "effect.parts.amf3.deflate")}
    try:
        with zipfile.ZipFile(archive) as zf:
            members = set(zf.namelist())
            if not set(want.values()) <= members:
                return None
            return {name: zf.read(member) for name, member in want.items()}
    except Exception:
        return None


def repack_effect(ctx, eid: str, scale: float, *, width: int | None = None,
                  originals: Mapping[str, bytes] | None = None) -> dict[str, Any]:
    """按 ``scale`` 重打一张特效表：逐子图缩放后重排，``.parts`` 矩阵 a/b/c/d 除回。"""
    import wf_seasonal7_common as C
    root = f"{EFFECT_DIR}/{eid}"
    sheet_logical = f"{root}/{eid}.png"
    atlas_logical = f"{root}/{eid}.atlas.amf3.deflate"
    parts_logical = f"{root}/effect.parts.amf3.deflate"
    if originals:
        raw = {"sheet": originals[f"{eid}.png"],
               "atlas": originals[f"{eid}.atlas.amf3.deflate"],
               "parts": originals["effect.parts.amf3.deflate"]}
    else:
        raw = {"sheet": ctx.pack.pkg_path("common", sheet_logical).read_bytes(),
               "atlas": ctx.pack.pkg_path("common", atlas_logical).read_bytes(),
               "parts": ctx.pack.pkg_path("common", parts_logical).read_bytes()}
    sheet = ctx.png_open(raw["sheet"])
    atlas = C.amf_parse(raw["atlas"])
    parts = C.amf_parse(raw["parts"])
    before = list(sheet.size)

    uniq: dict[tuple[int, int, int, int], tuple[int, int]] = {}
    for entry in atlas:
        rect = (entry["x"], entry["y"], entry["w"], entry["h"])
        if rect not in uniq:
            uniq[rect] = (max(1, round(entry["w"] * scale)), max(1, round(entry["h"] * scale)))
    items = [(f"{i}", size[0], size[1]) for i, size in enumerate(uniq.values())]
    keys = list(uniq)
    placed, width, height = _pack_rects(items, width)

    from PIL import Image
    out = Image.new("RGBA", (max(1, width), max(1, height)), (0, 0, 0, 0))
    positions: dict[tuple[int, int, int, int], tuple[int, int, int, int]] = {}
    for i, rect in enumerate(keys):
        w2, h2 = uniq[rect]
        x, y = placed[f"{i}"]
        crop = sheet.crop((rect[0], rect[1], rect[0] + rect[2], rect[1] + rect[3]))
        if (w2, h2) != crop.size:
            crop = crop.resize((w2, h2), Image.LANCZOS)
        out.paste(crop, (x, y))
        positions[rect] = (x, y, w2, h2)
    for entry in atlas:
        rect = (entry["x"], entry["y"], entry["w"], entry["h"])
        entry["x"], entry["y"], entry["w"], entry["h"] = positions[rect]
    for matrix in parts.get("t", []):
        for field in ("a", "b", "c", "d"):
            if field in matrix and matrix[field]:
                matrix[field] = int(round(matrix[field] / scale))

    ctx.write_asset("common", sheet_logical, ctx.png_store_bytes(out))
    ctx.write_asset("common", atlas_logical, C.amf_bytes(atlas))
    ctx.write_asset("common", parts_logical, C.amf_bytes(parts))
    return {"effect": eid, "scale": scale, "before": before, "after": list(out.size),
            "rects": len(atlas), "unique_rects": len(uniq)}


def slim_atlas(ctx, source=None) -> dict[str, Any]:
    dropped = []
    for eid in FX_DROP:
        directory = ctx.pack.pkg_path("common", f"{EFFECT_DIR}/{eid}/{eid}.png").parent
        if directory.is_dir():
            for path in sorted(directory.iterdir()):
                path.unlink()
            directory.rmdir()
            dropped.append(eid)
    repacked = []
    for eid, scale in FX_REPACK.items():
        sheet = ctx.pack.pkg_path("common", f"{EFFECT_DIR}/{eid}/{eid}.png")
        if not sheet.is_file():
            raise KitError(f"effect sheet missing: {eid}")
        originals = source_originals(source, eid)
        record = ctx.pack.owned_record("common", f"{EFFECT_DIR}/{eid}/{eid}.png") or {}
        if originals is None and record.get("owner") == "kit":
            # 拿不到原图又已经重打过：再缩一次会二次糊，宁可保留上一轮结果并报出来。
            repacked.append({"effect": eid, "skipped": "already repacked by kit; source originals unavailable"})
            continue
        repacked.append({**repack_effect(ctx, eid, scale, width=FX_REPACK_WIDTH.get(eid),
                                         originals=originals),
                         "from": "studio-source" if originals else "package"})
    return {"dropped": dropped, "repacked": repacked}


def atlas_budget(ctx) -> dict[str, Any]:
    import wf_atlas_budget_check as A
    roster = A.load_roster()
    report = A.check(roster, mode="pack", pack=str(ctx.workspace)) if hasattr(A, "check") else None
    if report is None:
        return {"note": "atlas budget tool API changed; run the CLI"}
    return report


# ------------------------------------------------------------------ build


def load_design(root: Path) -> dict[str, Any]:
    path = Path(root) / DESIGN_REL
    if not path.is_file():
        raise KitError(f"design plan missing: {DESIGN_REL}")
    return json.loads(path.read_text(encoding="utf-8"))


def build(pack, source=None) -> dict[str, Any]:
    import wf_seasonal7_build as B
    import wf_midautumn_kitlib as K
    ctx = B.KitContext(pack)
    design = load_design(ctx.root)
    notes: list[str] = []
    deviations = [d for d in design.get("deviations", [])]

    leader, ability, composer = build_rows(ctx, design)
    drift = design_drift(composer, design)
    if drift:
        raise KitError("design/plan drift: " + "; ".join(drift[:8]))
    capabilities = sorted({cap for record in composer.records for cap in record["capabilities"]}
                          | {"panel-description-override-v2"})
    if sorted(CAPABILITIES) != capabilities:
        raise KitError(f"required capabilities drift: rows say {capabilities}, SPEC says {sorted(CAPABILITIES)}")

    programs = build_programs(ctx)
    problems: list[str] = []
    for path, tree in programs.items():
        level = next((n for n in (1, 2, 3) if path.endswith(f"_lv{n}")), None)
        baseline = ctx.template_dsl(DONOR_SPECIAL.format(n=level)) if level else None
        problems.extend(program_problems(ctx, path, tree, baseline))
    if problems:
        raise KitError("DSL static checks failed: " + "; ".join(problems[:10]))

    uniques, icon_plan = unique_rows(ctx, design)
    strings = cas_rows(design)

    # ---- 落盘（先状态表/文案，后行表，最后 DSL）
    ctx.write_flat(UNIQUE, {key: [row] for key, row in uniques.items()})
    icons = install_icons(ctx, icon_plan)
    ctx.write_flat(CAS, strings)
    ctx.write_flat(PFA, {PF_KEY: [pf_action_row(ctx)]})
    ctx.write_flat(LEADER, {CID_S: leader})
    ctx.write_flat(ABILITY, {key: rows for key, rows in ability.items()})

    written_programs = []
    for path, tree in programs.items():
        logical = ctx.write_dsl(path, tree)
        import wf_seasonal7_common as C
        back = C.amf_parse(ctx.pack.pkg_path("common", logical).read_bytes())
        if back != tree:
            raise KitError(f"{path}: write_dsl read-back mismatch")
        written_programs.append(logical)

    # ---- action_skill 文案（能量沿用包内 550/500）与角色文本
    texts = design["plan"]["texts"]["character"]
    inner = {level: list(cells) for level, cells in ctx.pkg_nested(CODE).items()}
    if sorted(inner) != ["1", "2"]:
        raise KitError(f"action_skill inner keys {sorted(inner)}")
    for level, cells in inner.items():
        cells[0] = texts["skill1"] if level == "1" else texts["skill2"]
        cells[1] = texts["desc1"] if level == "1" else texts["desc2"]
        if cells[4] != "550":
            raise KitError(f"action_skill lv{level} energy {cells[4]} != 550")
    ctx.write_nested(ACTION, CODE, {level: [cells] for level, cells in inner.items()},
                     replace_inner=True)
    text_row = list(ctx.csv_split(ctx.pkg_flat(TEXT)[CID_S])[0])
    for col, value in ((0, texts["name"]), (2, texts["profile"]), (3, texts["title"]),
                       (4, texts["skill1"]), (5, texts["desc1"]), (6, texts["skill2"]),
                       (7, texts["desc2"]), (10, texts["leader"]), (11, texts["cv"])):
        text_row[col] = value
    ctx.write_flat(TEXT, {CID_S: [text_row]})
    ctx.sync_character_mirrors()

    atlas = slim_atlas(ctx, source)

    panel = [strings[key][0][0].splitlines()[0] for key in DESC_KEYS]
    report = K.report(
        ctx,
        summary="索利兹 129986 完成态 kit：队长 12 行 + 词条 44 行 + 6 固有状态 + 14 棵 DSL"
                "（9×629 / 2 技能 / 3×722 覆盖）+ 17 条面板文案，图集已按裁决瘦身。",
        status=K.READY,
        panel=panel,
        notes=notes + [
            "行装配：官方 donor 行 + 逐格改（第二批搬入队长的 3 行为能力行派生）；56 行逐行过 client_legality / declared_block_fields /"
            " invoke_skill_string / element_columns，并与 design/soriz.json 的 cells·donor·describe 逐字核对。",
            "CreateCondition 下标 10（付与对象种类）按官方 rare5 语料取值（496 棵树统计："
            "FindAll 33→3 共 195 处、49→3、97→2、自身 -17→3 共 198 处）；写错 = 施法 C16102。",
            "选择器：己方全体一律 33（含自身）。设计稿原写 35（除自身外），会让索利兹本人拿不到"
            "禁疗/贯通/二连击/逆境，见 deviations D21。",
            "图集（09-20 修订，deviations D25）：拿掉 5 张（4 张 DSL 不引用的 + 主控点名的 4096×1765 双人援护 +"
            "大招 2048×443），大招改整路径引用官方 battle/effect/skill_unique/waterdragon_kunfu/waterdragon_kunfu"
            "（ShowEffect 节点整块搬官方的，只改主体 11 与偏移归零；跨 code_name 引官方特效不会「数据不足」，"
            "见记忆卡 wf-effect-family-under-codename 2026-09-10 更正）；仁援护从 Studio 原图 0.375 单次重采样 +"
            "锁 384 宽重排 = 382×323 = 0.123 Mpx（上一轮 1017×184 = 0.187 超了设计稿自己写的 0.13 目标）。"
            "wf_atlas_budget_check：subject.layer0_pct = 2.80%（门槛 ≤5）、layer1 1.99%，"
            "five-boss-r0 fits=true（房 93.21%）、five-boss-r1 fits=true（房 95.13%）⇒ 裁决 §2 两项全达标。"
            "注意：fits 随货架形状非单调（上一轮 4.32% 时 0.38/0.34 缩放能装下、0.36/0.32/0.30/0.25 装不下），"
            "只看 layer0_pct 抓不住回归；本包再加约 0.09 Mpx 新表 r1 会重新翻红。"
            "房间整体仍 >90% 软阈值（status=OVER_THRESHOLD、attribution=pre-existing，"
            "不含本包时基线已 92.33% 填充）——那是作者已知的既有状态，不是本包造成的。",
            "flow preflight（批目录 _inspect 副本，真 workspace 字节不变）："
            "把 requires_client_base 临时降到 validated_chain_tail 1.4.928 时 rc=0、can_prepare=true、"
            "release_ready=true、conflicts=[]、master_reference 23 处引用零缺失（重打后的图集也解析得到）。"
            "按裁决 §1 写的 1.4.933 高于当前链尾，preflight 会停在"
            "『requires_client_base 1.4.933 cannot reach validated tail 1.4.928』——"
            "这是全批共用的 wf_midautumn_specs.REQUIRES_CLIENT_BASE，发布前由主控复核链尾，不是本包的缺陷。",
            "语音：按裁决 §5 用包内已有的 19 条原声，本轮不生成。",
            "2026-09-27 平衡调整第二批（wf_balance_20260927b_gbf.py）：能力3「三羽乌每层 攻/PF伤/PF独立」"
            "原样搬进队长并放缓 1/5（20%/20%/0.5%，队长 9→12 行），能力侧换最多计 10 层的"
            " 15%/10%/1%；三棵援护 629 的 p13 30→3；Fever 特殊 PF 分支 p13 改为 11 段+终结段"
            " = 15/20/25（改前 60/60/75）。",
            "2026-09-27 平衡调整第三轮（wf_balance_20260927c_soriz.py，成长复核）：队长三羽乌逐层成长"
            "由第二批 20%/20%/0.5% 回调到 70%/70%/2%（原值的 2/3 档，取 5 的倍数）；能力3 封顶版不动。",
            "同轮暂存前面板修正（主会话口径 A/B/D，wf_balance_20260927c_soriz.soriz_mirror 写进 design/soriz.json，"
            "本 kit 按镜像原样输出）：队长面板 8 行 → 11 行——第 2 行「自身攻击力+70%，强化弹射伤害」、「&」改「，」"
            "（强化弹射伤害不补对象）；FEVER 模式一行按数据条件拆 4 行（禁疗 #5 / PF 伤害 #2 / 连击 #3 / 护盾与"
            " FEVER 槽 能力3#7-#8）；722 三档的半角斜杠改「、」分项；「不死不休」获取行补「水属性共鸣时，」（#5 水共鸣）。",
        ],
        programs=written_programs,
        unique_condition={uid: {**icons[uid], "name": uniques[uid][1], "cap": uniques[uid][4]}
                          for uid in icons},
        required_capabilities=CAPABILITIES,
        deviations=deviations,
        extra={"rows": {"leader": len(leader),
                        "ability": {k: len(v) for k, v in ability.items()}},
               "custom_ability_string": sorted(strings),
               "power_flip_action": [PF_KEY],
               "atlas": atlas,
               "row_evidence": composer.records},
    )
    ctx.evidence_write("soriz-rows.json", composer.records)

    import wf_seasonal7_manifest as manifest
    manifest.build(pack)
    return {"status": "ready-for-review", "character": CODE, "cid": CID,
            "rows": {"leader": len(leader), "ability": {k: len(v) for k, v in ability.items()}},
            "programs": len(written_programs), "unique_condition": sorted(uniques),
            "custom_ability_string": len(strings), "atlas": atlas,
            "kit_fingerprint": report["kit_fingerprint"]}
