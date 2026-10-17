# -*- coding: utf-8 -*-
"""官方羁绊武器 8 把：强化 Lv0→120 生成器（只读 live）。

作者 0929：「官方的羁绊武器按照一定比例设计120级属性，满级强化需要消耗深渊币和羁绊证50个，刃值为280%的满级到不超过400%，
不足280%的按一定比例提升」「不足280%的也要按照到280%的比例降低不是全部到400%」「风格参考官方强化前后变化，机兵、普莉莉艾」。
设计与取证：``${WF_ROOT}/out/羁绊武器强化-20260929/设计.md`` + ``design.json``。

## 规则（一个统一倍率）

- 每条刃行 Lv120 总值 = 满破本体值 × 400/280（0.001% 四舍五入），刃合计封顶 400%：280%→400%、210%→300%、140%→200%，
  不足 280% 的不拉到 400%；高于 280% 的（现无）按封顶截断。HP（杜兰德尔）同倍率，只有刃被封顶。触发/条件/次数上限/目标不动。
- 风格照官方机兵/普·莉莉艾：名字加「·改」（Lv1 起）、Lv70 起换重绘的新图标、说明原文、Lv99 起粉框、白值不加（作者 0929「白值不加」：Lv120 只强化词条，HP/ATK 保持本体；状态表仍按官方键形 98/99/120 写 0,0）；
  强化行 = 本体行克隆，只改强度，四段 A/B/C/D 同效果成长（份额 32/20/32/16，bp (24,48)(24,24)(48,48)(2,24)）。
- 成本（满级 Lv0→120，6 阶 69/70/98/99/119/120，一份 = 1 级）：**羁绊证恰 50**（Lv70/99/120 单级节点 10/15/25，商店价格列 c11=2），
  **深渊币 1494**（每级 12、节点 30；深渊武装每把 3735 的 40%；约 9.6 次深渊满通关）。
- 纯数据：不需要新客户端补丁能力；服务端只增 ``equipment_enhancement_shop.json`` 48 键，``src/`` 不改。

## 官方基线

8 把的 equipment / ability_soul / equipment_status 行冻结在 ``assets/bond-weapons/official_baseline.json``
（官方 <=1.4.54，不能取 store；这 8 个键官方与 live 逐字节相同）。运行时断言 live 同键与冻结值逐格一致。

## 美术源（assets/bond-weapons/）

``<stem>.png`` = 官方原图（20×20，取自官方 item/sprite_sheet 图集，门禁的对照物，不入 store）；``<stem>_lv120.png`` = 按官方机兵/莉莉艾幅度
重绘的觉醒图（入 store 为 item/equipment/mod/bond/<stem>_lv120.png）；``bond_weapon_{banner,header}.png`` 由 ``wf_bond_weapon_banner.py``
用这 8 张觉醒图合成。图标门（icon_problems）任一张缺/不合格 ⇒ 整批 ENH c4 退回本体图标路径；横幅与图标不一致
（图标改了没重出横幅）⇒ banner_stale_problems 拒绝暂存。stage 把源图 sha256 写进 report.json，交付前与画图单元的 manifest 核对。

## 用法（全部只读 live；stage 只写 <workdir>）

    python mod-tools/wf_bond_weapon_enhance.py check                 # 体检：逐把 刃值前后/HP·ATK/成本 + problems
    python mod-tools/wf_bond_weapon_enhance.py table [--json]        # 只输出逐把表
    python mod-tools/wf_bond_weapon_enhance.py stage <workdir>       # 写 <workdir>/{plan.json,stage/common/**,stage/server/**}
    python mod-tools/wf_bond_weapon_enhance.py stage <workdir> --icons base   # 分享包退路：ENH c4 保持本体图标路径、不带 8 张独立 PNG

``check`` 与 stage 的 report.json 都带 ``needs_attention``（白值口径 C3、深渊币价 C7、独立 PNG 图标对编成框 b 补丁的依赖、真机冒烟）
和 ``status_alternatives``（白值三种口径逐把对照）：这些是发布前要人看一眼的事，不是生成器能替作者定的。

暂存产物按 ``${WF_ROOT}/out/武器扭蛋-20260928/publish/apply_gacha.py`` 合同：plan.json = tables{逻辑名:{changed,live_sha256,staged_sha256}}、
files{}、server{文件名:{live_sha256,...}}、deleted{}；只有新键与新文件，其余键逐字节等于 live。
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import shutil
import statistics
import struct
import sys
import zlib
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    pass  # Imports resolve from this checkout/package, not external source copies.

import wf_client_legality as L  # noqa: E402
import wf_cursed_weapons as W  # noqa: E402
import wf_share_update_codec as X  # noqa: E402

# ---------------------------------------------------------------------------
# 合同常量（改口径只改这里，然后重跑 check / stage）
# ---------------------------------------------------------------------------

ART = TOOLS / "assets" / "bond-weapons"
BASELINE_PATH = ART / "official_baseline.json"

ENH, EA, ENH_STATUS = W.ENH, W.EA, W.ENH_STATUS
ENH_SHOP, ENH_CATEGORY = W.ENH_SHOP, W.ENH_CATEGORY
SOUL, EQUIPMENT, EQUIPMENT_STATUS = W.SOUL, W.EQUIPMENT, W.EQUIPMENT_STATUS
SOUL_T, EA_T = W.SOUL_T, W.EA_T
SERVER_SHOP = "equipment_enhancement_shop.json"
CLIENT_TABLES = (ENH, EA, ENH_STATUS, ENH_SHOP, ENH_CATEGORY)     # 必须同一条边发（缺 STATUS = C8013，缺 EA = 空引用）

#: 官方 general_shop 100001–100008（价格种类 = 羁绊证）的顺序
WEAPON_IDS = ("5010005", "5030005", "5040022", "5020024", "5070027", "5050026", "5020041", "5060044")
NAME_SUFFIX = "·改"                                    # 机兵「·改」（U+00B7）
ENH_LEVELS = ("1", "70", "1", "99")                    # ENH c1 名 / c3 图 / c5 说明 / c7 强化态：官方 12/12 同款
REQUIRE_AWAKENING = "1"                                # 这 8 把 max_level = 1；写 5 客户端永远禁用强化按钮
MAX_LEVEL = 120

# 刃值规则（作者 0929）：一个统一倍率
RULE_NUM, RULE_DEN = 400, 280
RATIO = Fraction(RULE_NUM, RULE_DEN)                   # 10/7
BLADE_CAP = Fraction(400)                              # 刃合计封顶 %
BLADE_TOLERANCE = 0.0011                               # 0.001% 取整误差（weapon_budget 已按 /1000 给 %）
RATIO_TOLERANCE = 1e-5                                 # 实际倍率与 10/7 的容差（取整误差 ≤ 3e-6）

# 四段（莉莉艾 13 阶线原值）：A learn 1→120（p1 = ½）、B learn 70 恒值、C learn 99 恒值（= A）、D learn 100→120（p1 = ⅒）
SHARE_A, SHARE_B = Fraction(32, 100), Fraction(20, 100)
TIERS = (
    ("A", 1, 120, "24", "48"),
    ("B", 70, 120, "24", "24"),
    ("C", 99, 120, "48", "48"),
    ("D", 100, 120, "2", "24"),
)
STATUS_ROWS = {"98": "0,0", "99": "0,0", "120": "0,0"}          # 作者 0929「白值不加」：键形照官方（末键 = ENH c0），增量全 0

ICON_DIR = "item/equipment/mod/bond"                   # <ICON_DIR>/<stem>_lv120.png：独立 20×20 PNG
#: 图标模式：new = Lv70 起换独立 PNG（官方风格，默认）；base = ENH c4 保持本体图标路径（图集子纹理，不出 8 张独立 PNG）。
#: base 是给「不确定接收方装了编成框 b 补丁」的分享包用的数据侧退路（同官方 17/29 强化武器的写法）。
ICON_MODES = ("new", "base")
ICON_SIZE = (20, 20)
BANNER = "dynamic/equipment_enhancement/bond_weapon_banner"
HEADER = "dynamic/equipment_enhancement/bond_weapon_header"
BANNER_SIZE, HEADER_SIZE = (1000, 184), (1440, 556)

CATEGORY_KEY = "7"
CATEGORY_C0 = "bond_weapon"
CATEGORY_NAME = "羁绊武器·觉醒"
CATEGORY_ORDER = "0"                                   # 诅咒 -2 → 深渊 -1 → 羁绊 0 → 官方 1–4（c1 全表互异整数）
CATEGORY_TEMPLATE_KEY = "6"                            # 诅咒类目行（c6/c7 = 官方歼灭类目已验证存在的值，禁自造 = C8601）
SHOP_TEMPLATE_KEY = "591010102"                        # 诅咒线同形的 50 列商店行

#: 商店 6 阶上限（形状同 死亡使者 / 深渊 / 诅咒）；一份 = 1 级，阶段等级数 69/1/28/1/20/1
STAGE_CAPS = (69, 70, 98, 99, 119, 120)
ABYSS_COIN = "2370099"                                 # 深渊代币（rogue_event_item_99；不是 2370100 觉醒核 / 2370101 王印）
COIN_PER_LEVEL, COIN_PER_NODE = 12, 30                 # 深渊武装 30/级、75/节点 × 0.4
COIN_TOTAL = 1494
#: 羁绊证只放单级阶段（Lv70/99/120）：我方「一份 = 1 级」与灰服「一份 = 整阶」两种规则下总量一致（都是 50）
TOKENS_AT = {70: 10, 99: 15, 120: 25}
TOKEN_TOTAL = 50
BOND_TOKEN_PRICE_KIND = "2"                            # 商店价格列 c11 = PriceKind.BondToken；服务端 userCost.type = 2（AMITY_SCROLL）
ABYSS_WEAPON_COIN = 3735                               # 深渊武装 Lv0→120 单把总深渊币（live 实测 30/级、75/节点）
FULL_CLEAR_COIN = 155                                  # 深渊连战 700099 满通关一次：30 轮 × 5 + 通关 5
LIST_ORDER_BASE = 100                                  # c5 = 101–108（按 general_shop 顺序；排序方向未验证）

START_TIME = W.START_TIME
#: 服务端 ``requireAwakeningLevel`` 与客户端 c31 同值；``userCost`` 只有羁绊证节点阶有
SHOP_TEMPLATE_FILLED = {0, 2, 3, 5, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 29, 30, 31}


class BondError(RuntimeError):
    pass


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise BondError(message)


# ---------------------------------------------------------------------------
# 官方基线（冻结）
# ---------------------------------------------------------------------------

def load_baseline(path: Path = BASELINE_PATH) -> dict[str, dict]:
    """{武器 ID: {name, stem, equipment(16 列), soul_id, soul([123 列行]), status{"1": "hp,atk"}}}，按 WEAPON_IDS 顺序。"""
    doc = json.loads(path.read_text(encoding="utf-8"))
    weapons = doc["weapons"]
    _require(tuple(weapons) == WEAPON_IDS, f"冻结基线的武器集合/顺序漂移：{tuple(weapons)}")
    for wid, w in weapons.items():
        _require(len(w["equipment"]) == 16 and w["equipment"][10] == wid == w["soul_id"], f"{wid} equipment 行形状漂移")
        _require(w["equipment"][8] == "1", f"{wid} max_level != 1（本设计的前提：不可觉醒、requireAwakeningLevel = 1）")
        _require(w["equipment"][6] == f"item/equipment/general/{w['stem']}", f"{wid} 图标路径与 stem 不符")
        _require(all(len(r) == 123 for r in w["soul"]), f"{wid} ability_soul 列数漂移")
    return weapons


def baseline_problems(read: W.LiveReader, baseline: dict[str, dict]) -> list[str]:
    """live 的 equipment / ability_soul / equipment_status 同键必须与冻结基线逐格一致（官方值不能取 store，先查明再动）。"""
    problems: list[str] = []
    live_eq, live_soul, live_es = read.flat(EQUIPMENT), read.flat(SOUL), read.nested(EQUIPMENT_STATUS)
    for wid, w in baseline.items():
        if live_eq.get(wid) != [w["equipment"]]:
            problems.append(f"{w['name']}（{wid}）live 的 equipment 行与官方基线不一致")
        if live_soul.get(w["soul_id"]) != w["soul"]:
            problems.append(f"{w['name']}（{wid}）live 的 ability_soul 行与官方基线不一致")
        if live_es.get(wid) != w["status"]:
            problems.append(f"{w['name']}（{wid}）live 的 equipment_status 与官方基线不一致")
    return problems


# ---------------------------------------------------------------------------
# 数值
# ---------------------------------------------------------------------------

def half_up(x: Fraction) -> int:
    return int((x * 2 + 1) // 2) if x >= 0 else -int((-x * 2 + 1) // 2)


def strength_cols(table: str, mode: str) -> tuple[int, int]:
    """(power1 列, first_max 列)：mode 0 瞬发 = instant_content，其余 = during_content。"""
    block = "instant_content" if mode == "0" else "during_content"
    return W._col(table, block, "strength.power1"), W._col(table, block, "strength.first_max")


def is_blade(mode: str, kind: str) -> bool:
    """刃 = 攻击力/技能伤害/直击伤害/能力伤害/强化弹射伤害的正值（同 wf_cursed_weapons.weapon_budget 口径）。"""
    return kind in (W.BLADE_INSTANT_STATS if mode == "0" else W.BLADE_DURING)


def row_kind(table: str, row: list[str]) -> str:
    mode = row[5] if table == EA_T else row[2]
    return row[W._col(table, "instant_content" if mode == "0" else "during_content", "kind")]


def split_delta(delta: int) -> dict[str, int]:
    """Lv120 差额（存储值 1000 = 1%）拆成 A/B/C/D 四段：A = 32%、B = 20%、C = A、D = 余量（吸收取整误差，约 16%）。"""
    a = half_up(Fraction(delta) * SHARE_A)
    b = half_up(Fraction(delta) * SHARE_B)
    d = delta - 2 * a - b
    _require(d > 0 and a > 0 and b > 0, f"差额 {delta} 太小，无法拆四段")
    return {"A": a, "B": b, "C": a, "D": d}


def tier_p1(tier: str, first_max: int) -> int:
    """成长行起点：A 从满值的一半起、D 从十分之一起（官方 莉莉艾 0.5V→V、0.1W→W）；B/C 是恒值节点。"""
    if tier == "A":
        return half_up(Fraction(first_max, 2))
    if tier == "D":
        return half_up(Fraction(first_max, 10))
    return first_max


def clone_ea_row(soul_row: list[str], slot: int, learn: int, max_level: int, bp: tuple[str, str], p1: int,
                 first_max: int) -> list[str]:
    """EA 行 = 本体行在 c1 后插 3 格 [max_power_level, bp1, bp2]（官方歼灭武器逐格核对无差），再改强度两格。"""
    row = [str(slot), str(learn), str(max_level), bp[0], bp[1]] + list(soul_row[2:])
    c1, c2 = strength_cols(EA_T, soul_row[2])
    row[c1], row[c2] = str(p1), str(first_max)
    _require(len(row) == 126, "EA 行列数漂移")
    return row


def row_value(row: list[str], level: int) -> Fraction:
    """AbilityPowerValue：等级 < learn 未学会 = 0；≥ max 取 first_max；中间线性。"""
    learn, max_level = int(row[1]), int(row[2])
    c1, c2 = strength_cols(EA_T, row[5])
    p1, first_max = int(row[c1]), int(row[c2])
    if level < learn:
        return Fraction(0)
    if level >= max_level:
        return Fraction(first_max)
    return p1 + Fraction(first_max - p1) * (level - learn) / (max_level - learn)


@dataclass
class Effect:
    soul_row: int
    kind: str
    mode: str
    blade: bool
    base: int          # 存储值 1000 = 1%
    total: int         # Lv120 总值
    delta: int
    split: dict[str, int]
    label: str = ""


@dataclass
class Weapon:
    id: str
    name: str
    stem: str
    list_order: str
    equipment_row: list[str]
    soul_rows: list[list[str]]
    effects: list[Effect]
    ea_rows: list[list[str]]
    enh_row: list[str]
    status: dict[str, str]
    base_blade: float
    exact_blade: float
    final_blade: float
    capped: bool
    blade_ratio: Fraction
    base_status: dict[str, str] = field(default_factory=dict)

    @property
    def shop_ids(self) -> list[str]:
        return [f"{self.id}{stage:02d}" for stage in range(1, len(STAGE_CAPS) + 1)]


def blade_ratio_for(base_blade: float) -> Fraction:
    """刃合计的倍率：10/7，若会超过 400% 则取 400/基线（统一封顶）。"""
    if base_blade <= 0:
        return RATIO
    return min(RATIO, BLADE_CAP / Fraction(base_blade).limit_denominator(1000000))


def _describe(rows: list[list[str]]) -> list[str]:
    try:
        import wf_describe as D
        return D.describe_rows(rows, SOUL_T)
    except Exception:  # noqa: BLE001 — 文案只用于报告
        return [""] * len(rows)


def plan_weapon(wid: str, name: str, stem: str, equipment_row: list[str], soul_rows: list[list[str]],
                base_status: dict[str, str], list_order: str, *, icon_c4: str | None = None) -> Weapon:
    """一把武器的全部强化数据（纯函数）。icon_c4 = ENH c4（缺省 = 新图路径；图标门不过时由 build 传本体路径）。"""
    base_blade = W.weapon_budget(soul_rows, [], {}, {})["blades"]
    _require(base_blade < float(BLADE_CAP) - 1e-9,
             f"{name} 本体刃 {base_blade:g}% 已不低于封顶 {float(BLADE_CAP):g}%：规则无法再强化（拒绝出负增量）")
    ratio_blade = blade_ratio_for(base_blade)
    labels = _describe(soul_rows)
    effects: list[Effect] = []
    for i, srow in enumerate(soul_rows):
        mode = srow[2]
        c1, c2 = strength_cols(SOUL_T, mode)
        base = int(srow[c1])
        _require(base == int(srow[c2]), f"{name} 本体行 {i} power1 != first_max（有分级）")
        kind = row_kind(SOUL_T, srow)
        blade = is_blade(mode, kind)
        total = half_up(Fraction(base) * (ratio_blade if blade else RATIO))
        delta = total - base
        effects.append(Effect(i, kind, mode, blade, base, total, delta, split_delta(delta), labels[i]))
    n = len(soul_rows)
    ea_rows: list[list[str]] = []
    for t, (tier, learn, max_level, bp1, bp2) in enumerate(TIERS):
        for i, srow in enumerate(soul_rows):
            fm = effects[i].split[tier]
            ea_rows.append(clone_ea_row(srow, t * n + i, learn, max_level, (bp1, bp2), tier_p1(tier, fm), fm))
    full_blade = W.weapon_budget(soul_rows, ea_rows, {}, {})["blades"]
    exact = base_blade * float(RATIO)
    enh_row = [str(MAX_LEVEL), ENH_LEVELS[0], name + NAME_SUFFIX, ENH_LEVELS[1],
               icon_c4 if icon_c4 is not None else f"{ICON_DIR}/{stem}_lv120", ENH_LEVELS[2], equipment_row[7],
               ENH_LEVELS[3], START_TIME]
    return Weapon(wid, name, stem, list_order, equipment_row, soul_rows, effects, ea_rows, enh_row, dict(STATUS_ROWS),
                  base_blade, exact, full_blade, exact > float(BLADE_CAP) + 1e-9, ratio_blade, dict(base_status))


def ea_effect_totals(soul_rows: list[list[str]], ea_rows: list[list[str]]) -> list[int]:
    """每个本体效果在 Lv120 的强化行合计（存储值）：EA 行 slot % 效果数 = 效果序号（按「先层后效果」排）。"""
    n = len(soul_rows)
    totals = [0] * n
    for row in ea_rows:
        totals[int(row[0]) % n] += int(row_value(row, MAX_LEVEL))
    return totals


def effect_fraction(w: Weapon, effect_index: int, level: int) -> Fraction:
    """效果 effect_index 在 level 级已兑现的强化增量占 Lv120 差额的比例。"""
    n = len(w.soul_rows)
    delta = w.effects[effect_index].delta
    got = sum(row_value(r, level) for r in w.ea_rows if int(r[0]) % n == effect_index)
    return got / delta


def blade_at(w: Weapon, level: int) -> float:
    """level 级时的刃合计（%）。刃行同一比例成长，取第一条刃行的比例（设计 §3.2：四段 A/B/C/D 同效果成长）。"""
    idx = next((e.soul_row for e in w.effects if e.blade), 0)
    return round(w.base_blade + (w.final_blade - w.base_blade) * float(effect_fraction(w, idx, level)), 3)


def number_problems(w: Weapon) -> list[str]:
    """数值门禁（纯函数，可对变异输入求值）：规则按最初的设计逐项复算，任一偏差 = 一条 problem。"""
    name = w.name
    problems: list[str] = []
    base = W.weapon_budget(w.soul_rows, [], {}, {})
    full = W.weapon_budget(w.soul_rows, w.ea_rows, {}, {})
    target = min(float(BLADE_CAP), base["blades"] * float(RATIO))
    if abs(full["blades"] - target) > BLADE_TOLERANCE:
        problems.append(f"{name} Lv120 刃 {full['blades']} != 目标 {target:.3f}（本体 {base['blades']} × {RULE_NUM}/{RULE_DEN}，封顶 {float(BLADE_CAP):g}）")
    if full["blades"] > float(BLADE_CAP) + 1e-9:
        problems.append(f"{name} Lv120 刃 {full['blades']} 超过封顶 {float(BLADE_CAP):g}")
    if base["blades"] and w.base_blade and target < float(BLADE_CAP) - 1e-9:
        ratio = full["blades"] / base["blades"]
        if abs(ratio - float(RATIO)) > RATIO_TOLERANCE:
            problems.append(f"{name} 倍率 {ratio:.7f} 偏离 {RULE_NUM}/{RULE_DEN} = {float(RATIO):.7f}")
    if base["multipliers"] or full["multipliers"]:
        problems.append(f"{name} 出现独立乘区（本设计不新增乘区）")
    if full["unbounded"]:
        problems.append(f"{name} 数值预算存在无上限项：{full['unbounded']}")
    totals = ea_effect_totals(w.soul_rows, w.ea_rows)
    for e, got in zip(w.effects, totals):
        want = half_up(Fraction(e.base) * (blade_ratio_for(base["blades"]) if e.blade else RATIO))
        if e.base + got != want:
            problems.append(f"{name} 效果#{e.soul_row} Lv120 总值 {e.base + got}（本体 {e.base} + 强化 {got}）!= 目标 {want}")
    n = len(w.soul_rows)
    if len(w.ea_rows) != n * len(TIERS):
        problems.append(f"{name} EA 行数 {len(w.ea_rows)} != {n * len(TIERS)}")
    slots = [int(r[0]) for r in w.ea_rows]
    if slots != list(range(len(w.ea_rows))):
        problems.append(f"{name} EA slot 不是 0..{len(w.ea_rows) - 1} 各一行：{slots}")
    for i, r in enumerate(w.ea_rows):
        learn, max_level = int(r[1]), int(r[2])
        c1, c2 = strength_cols(EA_T, r[5])
        if len(r) != 126:
            problems.append(f"{name} EA#{i} 列数 {len(r)} != 126")
        if learn < 1:
            problems.append(f"{name} EA#{i} learn<1 (C14512)")
        if learn > max_level:
            problems.append(f"{name} EA#{i} learn>max (C14511)")
        if learn == max_level and r[c1] != r[c2]:
            problems.append(f"{name} EA#{i} learn==max 但 power1 != first_max (C14510)")
        if max_level != MAX_LEVEL:
            problems.append(f"{name} EA#{i} max_power_level {max_level} != {MAX_LEVEL}")
        if learn == MAX_LEVEL and r[3] != r[4]:
            problems.append(f"{name} EA#{i} learn==c0 但 bp1 != bp2")
        problems += [f"{name} EA#{i}: {p}" for p in L.client_legality_problems(EA_T, r)]
        caps = L.required_client_capabilities(EA_T, r)
        if caps:
            problems.append(f"{name} EA#{i} 需要客户端 capability {caps}（本设计要求纯数据，不新增补丁）")
    return problems


# ---------------------------------------------------------------------------
# 成本 / 商店 / 类目 / 服务端
# ---------------------------------------------------------------------------

def stage_costs() -> list[dict[str, Any]]:
    stages, prev = [], 0
    for k, cap in enumerate(STAGE_CAPS, start=1):
        levels = cap - prev
        per = COIN_PER_NODE if levels == 1 else COIN_PER_LEVEL
        tokens = TOKENS_AT.get(cap, 0)
        stages.append({"stage": k, "cap": cap, "from": prev + 1, "levels": levels,
                       "coin_per_unit": per, "coin_total": per * levels,
                       "token_per_unit": tokens, "token_total": tokens * levels})
        prev = cap
    return stages


def cost_problems(stages: list[dict[str, Any]]) -> list[str]:
    problems: list[str] = []
    caps = [s["cap"] for s in stages]
    if caps != sorted(set(caps)) or caps[-1] != MAX_LEVEL:
        problems.append(f"商店阶段上限须严格递增且末阶 = {MAX_LEVEL}：{caps}")
    if sum(s["levels"] for s in stages) != MAX_LEVEL or [s["from"] for s in stages][0] != 1:
        problems.append("商店阶段没有连续覆盖 Lv1–Lv120")
    if any(s["from"] != p["cap"] + 1 for p, s in zip(stages, stages[1:])):
        problems.append("商店阶段之间有空档/重叠")
    if sum(s["coin_total"] for s in stages) != COIN_TOTAL:
        problems.append(f"深渊币合计 {sum(s['coin_total'] for s in stages)} != {COIN_TOTAL}")
    if sum(s["token_total"] for s in stages) != TOKEN_TOTAL:
        problems.append(f"羁绊证合计 {sum(s['token_total'] for s in stages)} != {TOKEN_TOTAL}")
    if any(s["token_per_unit"] and s["levels"] != 1 for s in stages):
        problems.append("羁绊证只能放单级阶段（灰服一份 = 整阶，多级阶段会让两边总量不同）")
    return problems


def shop_row(template: list[str], wid: str, stage: dict[str, Any], list_order: str) -> list[str]:
    row = list(template)
    row[0], row[2], row[3] = CATEGORY_KEY, wid, str(stage["stage"])
    row[5] = list_order
    if stage["token_per_unit"]:
        row[11], row[12] = BOND_TOKEN_PRICE_KIND, str(stage["token_per_unit"])
    else:
        row[11], row[12] = "(None)", ""
    row[14:22] = W._cost_cells([(ABYSS_COIN, stage["coin_per_unit"])])
    row[22], row[23] = START_TIME, "(None)"
    row[29], row[30], row[31] = wid, str(stage["cap"]), REQUIRE_AWAKENING
    return row


def template_problems(template: list[str]) -> list[str]:
    """商店模板行的形状：其余列必须为空，否则说明 live 模板漂移（会把别人的列带进 8 把）。"""
    if len(template) != 50:
        return [f"商店模板 {SHOP_TEMPLATE_KEY} 列数 {len(template)} != 50"]
    dirty = {i: c for i, c in enumerate(template) if i not in SHOP_TEMPLATE_FILLED and i not in (1, 4, 24) and c not in ("", "(None)")}
    problems = [f"商店模板 {SHOP_TEMPLATE_KEY} 出现意外的非空列 {dirty}"] if dirty else []
    if template[4] != "1" or template[24] != "90":
        problems.append(f"商店模板 c4/c24 漂移：{template[4]!r}/{template[24]!r}（期望 1/90）")
    return problems


def server_row_from_client(row: list[str]) -> dict[str, Any]:
    """服务端镜像行 = 客户端商店行的投影（单一真源）；羁绊证价格列 → userCost {type 2}。"""
    costs = [{"id": int(row[i]), "amount": int(row[i + 1])} for i in (14, 16, 18, 20) if row[i] not in ("", "(None)")]
    out: dict[str, Any] = {"availableFrom": row[22], "availableUntil": None, "costs": costs,
                           "enhancementMaxLevel": int(row[30]), "equipmentId": int(row[29]), "groupId": int(row[2]),
                           "requireAwakeningLevel": int(row[31]), "rewards": [], "shopCategoryId": int(row[0]),
                           "stage": int(row[3]), "stock": -1}
    if row[11] == BOND_TOKEN_PRICE_KIND:
        out["userCost"] = {"type": int(row[11]), "amount": int(row[12])}
    return out


def category_row(template: list[str]) -> list[str]:
    row = list(template)
    _require(len(row) == 10, f"类目模板列数 {len(row)} != 10")
    row[0], row[1], row[3], row[4], row[5], row[8] = CATEGORY_C0, CATEGORY_ORDER, CATEGORY_NAME, BANNER, HEADER, START_TIME
    return row


# ---------------------------------------------------------------------------
# 图标 / 横幅 硬门
# ---------------------------------------------------------------------------

def _open_png(path: Path):
    from PIL import Image
    return Image.open(path)


def icon_problems(stem: str, art_dir: Path = ART) -> list[str]:
    """Lv120 图标硬门（同深渊先例 _check_icon，另加半透明值集）：PNG、20×20、RGBA、alpha 极值 0/255、
    不新引入原图没有的半透明值、且确实改了图。返回空 = 通过。"""
    lv120, orig = art_dir / f"{stem}_lv120.png", art_dir / f"{stem}.png"
    if not lv120.is_file():
        return [f"{stem}_lv120.png 缺失"]
    if not orig.is_file():
        return [f"{stem}.png（官方原图）缺失"]
    problems: list[str] = []
    try:
        with _open_png(lv120) as im:
            if im.format != "PNG" or im.size != ICON_SIZE or im.mode != "RGBA":
                problems.append(f"{stem}_lv120.png 不是 20×20 RGBA PNG：{im.format} {im.size} {im.mode}")
                return problems
            im.load()
            rgba = im.copy()
        with _open_png(orig) as im0:
            im0.load()
            original = im0.convert("RGBA")
        lo, hi = rgba.getchannel("A").getextrema()
        if lo != 0 or hi != 255:
            problems.append(f"{stem}_lv120.png alpha 极值 {lo}/{hi} != 0/255")
        extra = set(rgba.getchannel("A").tobytes()) - set(original.getchannel("A").tobytes())
        if extra:
            problems.append(f"{stem}_lv120.png 新引入原图没有的半透明值 {sorted(extra)}")
        if rgba.tobytes() == original.tobytes():
            problems.append(f"{stem}_lv120.png 与官方原图逐像素相同（没有改图）")
    except Exception as exc:  # noqa: BLE001
        problems.append(f"{stem}_lv120.png 无法读取：{exc}")
    return problems


def banner_problems(art_dir: Path = ART) -> list[str]:
    problems: list[str] = []
    for logical, size in ((BANNER, BANNER_SIZE), (HEADER, HEADER_SIZE)):
        path = art_dir / (logical.rsplit("/", 1)[-1] + ".png")
        if not path.is_file():
            problems.append(f"缺横幅图 {path.name}（先跑 wf_bond_weapon_banner.py）")
            continue
        try:
            with _open_png(path) as im:
                if im.format != "PNG" or im.size != size or im.mode != "RGBA":
                    problems.append(f"{path.name} 须是 {size[0]}×{size[1]} RGBA PNG：{im.format} {im.size} {im.mode}")
        except Exception as exc:  # noqa: BLE001
            problems.append(f"{path.name} 无法读取：{exc}")
    return problems


def banner_stale_problems(art_dir: Path = ART) -> list[str]:
    """横幅/头图必须正是用当前 8 张 Lv120 图标合成的结果（图标改了而横幅没重出 = 交付里图标与横幅不一致）。
    没有字体（无法重新合成）时跳过——单元测试同样按此规则；结果按图标与横幅字节缓存。"""
    import wf_bond_weapon_banner as BN
    if not (Path(BN.abyss.FONT_BOLD).is_file() and Path(BN.abyss.FONT).is_file()):
        return []
    baseline = load_baseline()
    files = [art_dir / f"{w['stem']}_lv120.png" for w in baseline.values()] + [art_dir / BN.BANNER_FILE, art_dir / BN.HEADER_FILE]
    if not all(f.is_file() for f in files):
        return []                                                     # 缺件由 icon_problems / banner_problems 报
    key = hashlib.sha256(b"".join(f.read_bytes() for f in files)).hexdigest()
    if key not in _BANNER_FRESH:
        from PIL import Image
        banner, header = BN.render(art_dir)
        bad = []
        for image, name in ((banner, BN.BANNER_FILE), (header, BN.HEADER_FILE)):
            with Image.open(art_dir / name) as committed:
                if committed.size != image.size or committed.convert("RGBA").tobytes() != image.convert("RGBA").tobytes():
                    bad.append(f"{name} 不是用当前 Lv120 图标合成的（图标改过？重跑 mod-tools/wf_bond_weapon_banner.py）")
        _BANNER_FRESH[key] = bad
    return list(_BANNER_FRESH[key])


_BANNER_FRESH: dict[str, list[str]] = {}


def source_hashes(art_dir: Path = ART) -> dict[str, str]:
    """暂存所依据的源图 sha256（原图 + Lv120 + 横幅），写进 report.json，交付前与画图单元的 manifest 核对。"""
    names = [f"{w['stem']}{suffix}.png" for w in load_baseline().values() for suffix in ("", "_lv120")]
    names += [BANNER.rsplit("/", 1)[-1] + ".png", HEADER.rsplit("/", 1)[-1] + ".png"]
    return {name: sha256((art_dir / name).read_bytes()) for name in names if (art_dir / name).is_file()}


def png_payload(src: Path) -> bytes:
    """store 态 PNG（RGBA 8 位、optimize、魔数混淆）。"""
    import wf_assets as A
    from PIL import Image
    with Image.open(src) as image:
        image.load()
        rgba = image.convert("RGBA")
    buf = io.BytesIO()
    rgba.save(buf, format="PNG", optimize=True)
    return A.png_encode(buf.getvalue())


def stored_same_pixels(stored: bytes, src: Path) -> bool:
    import wf_assets as A
    from PIL import Image
    with Image.open(io.BytesIO(A.png_decode(stored))) as a, Image.open(src) as b:
        a, b = a.convert("RGBA"), b.convert("RGBA")
        return a.size == b.size and a.tobytes() == b.tobytes()


# ---------------------------------------------------------------------------
# 组装
# ---------------------------------------------------------------------------

def _template(read: W.LiveReader, logical: str, key: str, width: int) -> list[str]:
    rows = read.flat(logical).get(key)
    _require(rows is not None and len(rows) >= 1 and len(rows[0]) == width, f"{logical}[{key}] 模板缺失或形状漂移")
    return list(rows[0])


def build(read: W.LiveReader, *, baseline: dict[str, dict] | None = None, art_dir: Path = ART,
          icon_mode: str = "new") -> dict[str, Any]:
    """只读 live 模板（商店 591010102、类目 6、全部类目行的 c1），产出目标态。``problems`` 非空时 stage 拒绝。

    图标门不过（8 张 Lv120 图标缺/不合格）⇒ 整批 ENH c4 退回本体图标路径，其余数据不变（``icon_fallback`` 列出原因）。
    ``icon_mode="base"`` 主动走同一条退路（图标门仍照常检查，横幅照常出）：不出 8 张独立 PNG，c4 = 本体图标路径。
    """
    _require(icon_mode in ICON_MODES, f"icon_mode 只能是 {ICON_MODES}：{icon_mode!r}")
    baseline = baseline if baseline is not None else load_baseline()
    problems: list[str] = []
    shop_tpl = _template(read, ENH_SHOP, SHOP_TEMPLATE_KEY, 50)
    cat_tpl = _template(read, ENH_CATEGORY, CATEGORY_TEMPLATE_KEY, 10)
    problems += template_problems(shop_tpl)

    icon_issues = {b["stem"]: icon_problems(b["stem"], art_dir) for b in baseline.values()}
    icon_fallback = [f"{stem}: {p}" for stem, ps in icon_issues.items() for p in ps]
    use_new_icons = not icon_fallback and icon_mode == "new"
    problems += banner_problems(art_dir)

    stages = stage_costs()
    problems += cost_problems(stages)

    weapons: list[Weapon] = []
    flat: dict[str, dict[str, list[list[str]]]] = {ENH: {}, EA: {}, ENH_SHOP: {}, ENH_CATEGORY: {}}
    nested: dict[str, dict[str, dict[str, str]]] = {ENH_STATUS: {}}
    server: dict[str, dict[str, Any]] = {SERVER_SHOP: {}}
    for index, (wid, b) in enumerate(baseline.items(), start=1):
        icon_c4 = f"{ICON_DIR}/{b['stem']}_lv120" if use_new_icons else b["equipment"][6]
        w = plan_weapon(wid, b["name"], b["stem"], b["equipment"], b["soul"], b["status"], str(LIST_ORDER_BASE + index),
                        icon_c4=icon_c4)
        weapons.append(w)
        problems += number_problems(w)
        if len(w.enh_row[6]) > W.DESC_LIMITS["enhancement"] or "," in w.enh_row[6] or "\n" in w.enh_row[6]:
            problems.append(f"{w.name} ENH 说明超长（{len(w.enh_row[6])} > {W.DESC_LIMITS['enhancement']}）或含半角逗号/换行")
        flat[ENH][wid] = [w.enh_row]
        flat[EA][wid] = w.ea_rows
        nested[ENH_STATUS][wid] = dict(w.status)
        for stage in stages:
            key = f"{wid}{stage['stage']:02d}"
            row = shop_row(shop_tpl, wid, stage, w.list_order)
            flat[ENH_SHOP][key] = [row]
            server[SERVER_SHOP][key] = server_row_from_client(row)
        _require(all(int(k) < 2 ** 31 for k in flat[ENH_SHOP]), "商店键超过 int32")
    flat[ENH_CATEGORY][CATEGORY_KEY] = [category_row(cat_tpl)]

    # 类目 c1 全表互异整数、顺序 诅咒 → 深渊 → 羁绊 → 官方 1–4
    import wf_enhancement_category_order as CO
    live_cat = {k: rows[0] for k, rows in read.flat(ENH_CATEGORY).items()}
    if CATEGORY_KEY in live_cat and live_cat[CATEGORY_KEY] != flat[ENH_CATEGORY][CATEGORY_KEY][0]:
        problems.append(f"live 类目 {CATEGORY_KEY} 已存在且与目标行不同：{live_cat[CATEGORY_KEY]}")
    staged_cat = {**live_cat, CATEGORY_KEY: flat[ENH_CATEGORY][CATEGORY_KEY][0]}
    upsert, order_problems = CO.target_rows(staged_cat)
    problems += order_problems
    if upsert:
        problems.append(f"类目顺序模块还要改这些键的 c1：{sorted(upsert)}（须先按 wf_enhancement_category_order 对齐）")

    files = {}
    banner_paths = {BANNER + ".png": art_dir / "bond_weapon_banner.png", HEADER + ".png": art_dir / "bond_weapon_header.png"}
    for logical, src in banner_paths.items():
        files[logical] = {"src": str(src), "kind": "banner"}
    if use_new_icons:
        for w in weapons:
            files[f"{ICON_DIR}/{w.stem}_lv120.png"] = {"src": str(art_dir / f"{w.stem}_lv120.png"), "kind": "icon"}

    return {"flat": flat, "nested": nested, "files": files, "server": server, "weapons": weapons, "stages": stages,
            "problems": problems, "icon_fallback": icon_fallback, "capabilities": [],
            "icon_mode": "new" if use_new_icons else "base"}


# ---------------------------------------------------------------------------
# 报告
# ---------------------------------------------------------------------------

def abyss_reference(read: W.LiveReader) -> dict[str, int]:
    """live 深渊武装（类目 5）每把 Lv0→120 的深渊币合计：Σ 阶段等级数 × 单价（作者币量的锚点）。"""
    shop = read.flat(ENH_SHOP)
    by_weapon: dict[str, list[tuple[int, int]]] = {}
    for rows in shop.values():
        r = rows[0]
        if r[0] != "5":
            continue
        amount = sum(int(r[i + 1]) for i in (14, 16, 18, 20) if r[i] == ABYSS_COIN)
        by_weapon.setdefault(r[29], []).append((int(r[30]), amount))
    out: dict[str, int] = {}
    for wid, stages in by_weapon.items():
        prev, total = 0, 0
        for cap, amount in sorted(stages):
            total += (cap - prev) * amount
            prev = cap
        if total:                                          # 五重的死亡使者（5900101）不收深渊币
            out[wid] = total
    return out


def weapon_table(out: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    coin = sum(s["coin_total"] for s in out["stages"])
    token = sum(s["token_total"] for s in out["stages"])
    for w in out["weapons"]:
        hp, atk = (int(x) for x in next(iter(w.base_status.values())).split(","))
        add_hp, add_atk = (int(x) for x in w.status[str(MAX_LEVEL)].split(","))
        rows.append({
            "id": w.id, "name": w.name, "enhanced_name": w.enh_row[2],
            "base_blade_pct": w.base_blade, "x_400_280_pct": round(w.exact_blade, 3), "final_blade_pct": w.final_blade,
            "capped": w.capped, "ratio": round(w.final_blade / w.base_blade, 7),
            "blade_at": {str(lv): blade_at(w, lv) for lv in (0, 1, 70, 99, 120)},
            "effects": [{"describe": e.label, "kind": e.kind, "base": e.base / 1000, "lv120": e.total / 1000,
                         "split_pct": {k: v / 1000 for k, v in e.split.items()}} for e in w.effects],
            "hp_atk_before": [hp, atk], "hp_atk_lv120": [hp + add_hp, atk + add_atk],
            "coin_total": coin, "token_total": token,
            "icon_c4": w.enh_row[4], "list_order": w.list_order,
        })
    return rows


def render_table(rows: list[dict[str, Any]]) -> str:
    lines = ["| 武器 | ID | 本体刃 | ×400/280 | Lv120 终值 | 封顶 | HP/ATK 前 | HP/ATK Lv120 | 深渊币 | 羁绊证 |",
             "|---|---|---:|---:|---:|---|---|---|---:|---:|"]
    for r in rows:
        lines.append(f"| {r['name']} | {r['id']} | {r['base_blade_pct']:g}% | {r['x_400_280_pct']:g}% | {r['final_blade_pct']:g}% | "
                     f"{'是' if r['capped'] else '否'} | {r['hp_atk_before'][0]}/{r['hp_atk_before'][1]} | "
                     f"{r['hp_atk_lv120'][0]}/{r['hp_atk_lv120'][1]} | {r['coin_total']} | {r['token_total']} |")
    return "\n".join(lines)


def coin_reasoning(read: W.LiveReader | None = None) -> dict[str, Any]:
    """深渊币定价依据：深渊武装每把 3735（30/级、75/节点）× 0.4；0.4 = 羁绊最大差额 ÷ 深渊差额中位（见设计 §4.3）。"""
    info: dict[str, Any] = {"per_level": COIN_PER_LEVEL, "per_node": COIN_PER_NODE, "total": COIN_TOTAL,
                            "abyss_weapon_reference": ABYSS_WEAPON_COIN,
                            "full_clear_coin": FULL_CLEAR_COIN, "in_full_clears": round(COIN_TOTAL / FULL_CLEAR_COIN, 2),
                            "rule": "深渊武装 30/级、75/节点 × 0.4 = 12/级、30/节点；0.4 = 羁绊最大差额 120% ÷ 深渊差额中位 300%；统一价"}
    if read is not None:
        ref = abyss_reference(read)
        if ref:
            info["abyss_live"] = {"weapons": len(ref), "median": statistics.median(ref.values()), "min": min(ref.values()),
                                  "max": max(ref.values())}
    return info


#: 蒼藍白值红线（外部评分标准，只作提示，不是游戏规则）：ATK > 250 或 HP > 600
HP_REDLINE, ATK_REDLINE = 600, 250


def status_alternatives(out: dict[str, Any]) -> list[dict[str, Any]]:
    """Lv120 白值（HP/ATK）的三种口径逐把对照，供作者拍板（设计 C3）：
    ``flat`` = 官方式固定增量（现行，STATUS_ROWS）、``ratio`` = 按刃值同一倍率 10/7 放大后的终值。"""
    rows = []
    for w in out["weapons"]:
        hp, atk = (int(x) for x in next(iter(w.base_status.values())).split(","))
        add_hp, add_atk = (int(x) for x in w.status[str(MAX_LEVEL)].split(","))
        rows.append({"id": w.id, "name": w.name, "base": [hp, atk], "flat": [hp + add_hp, atk + add_atk],
                     "flat_pct": [round(add_hp * 100 / hp, 2), round(add_atk * 100 / atk, 2)],
                     "ratio": [half_up(Fraction(hp) * RATIO), half_up(Fraction(atk) * RATIO)]})
    return rows


def needs_attention(out: dict[str, Any]) -> list[dict[str, str]]:
    """发布/进分享包之前必须有人看一眼的事项（机读，写进 report.json 与 ``check`` 输出）。
    who = 作者（要拍板）/ 接收方（分享包）/ 发布前（真机冒烟）。数字全部现算，不手写。"""
    alts = status_alternatives(out)
    hp_pct = [a["flat_pct"][0] for a in alts]
    atk_pct = [a["flat_pct"][1] for a in alts]
    flat_hp, flat_atk = [a["flat"][0] for a in alts], [a["flat"][1] for a in alts]
    ratio_hp, ratio_atk = [a["ratio"][0] for a in alts], [a["ratio"][1] for a in alts]
    base_hp_over = sum(1 for a in alts if a["base"][0] > HP_REDLINE)
    flat_hp_over = sum(1 for a in alts if a["flat"][0] > HP_REDLINE)
    max_delta = max(w.final_blade - w.base_blade for w in out["weapons"])
    alt_coins = [round(COIN_TOTAL * (w.final_blade - w.base_blade) / max_delta) for w in out["weapons"]]
    return [
        {"id": "C3", "who": "作者",
         "text": f"已定（作者 0929「白值不加」）：Lv120 白值不加，HP/ATK 保持本体（HP {min(flat_hp)}–{max(flat_hp)}、ATK {min(flat_atk)}–{max(flat_atk)}），"
                 f"只强化词条；未采用的备选：官方式固定 +50/+10，或按刃值同一倍率 ×10/7 = HP {min(ratio_hp)}–{max(ratio_hp)}、ATK {min(ratio_atk)}–{max(ratio_atk)}。"},
        {"id": "C7", "who": "作者",
         "text": f"深渊币统一价 {COIN_TOTAL}（每级 {COIN_PER_LEVEL}、节点 {COIN_PER_NODE}），约 {round(COIN_TOTAL / FULL_CLEAR_COIN, 1)} 次深渊满通关，"
                 f"是深渊武装 {ABYSS_WEAPON_COIN} 的 40%；羁绊武器全模式可用而深渊武装是模式锁定，所以偏宽松，且最低刃的波利克斯（157%）与 400% 的三把付同一价。"
                 f"备选：按差额比例 {min(alt_coins)}–{max(alt_coins)}，或节点加深渊王印/觉醒核。改只动 COIN_PER_LEVEL/COIN_PER_NODE/COIN_TOTAL 与测试。"},
        {"id": "ICON_B", "who": "接收方",
         "text": "Lv70 起的 8 张 Lv120 图标是独立 PNG（item/equipment/mod/bond/*_lv120）。没有编成框 b 补丁"
                 "（equipment-enhanced-party-frame-v1 的 setItemImage 修复）的客户端，编成/选队里格子「有图标→空槽」会释放共享贴图，"
                 "重启前该图标可能不显示（代码层结论，真机未证；client-patch/equipment-enhanced-party-frame/README.md b 版）。"
                 "local-mumu 档案有 b，gray-1047 档案没有；能力闸门看不出（8 个新键不产生能力需求）。"
                 "深渊/诅咒/PARADOX 的 _lv120 图标是同一前提，不是这批新增的风险类别。"
                 "进灰的分享包前三选一：确认灰装了 b（补丁包 L4）；stage --icons base（ENH c4 保持本体图集路径，不带 8 张独立 PNG）；"
                 "给 8 个路径补 trimmed_image 行（README 提到的数据侧加固，未验证，不在本批）。"},
        {"id": "SMOKE", "who": "发布前",
         "text": "强化商店价格列收羁绊证（c11=2）官方和 live 都没有先例：真机冒烟 1 把武器，看商店格价格图标、买入对话框、扣费、"
                 "bond_token 回写、Lv70 名字/新图/Lv99 粉框、类目顺序、list_order 方向。"},
    ]


# ---------------------------------------------------------------------------
# 暂存（只写 <workdir>；live 只读）
# ---------------------------------------------------------------------------

def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def build_nested_leaf(text: str) -> bytes:
    return zlib.compress(text.encode("utf-8"), 9) if text else b""


def build_nested_node(node: dict[str, str]) -> bytes:
    """嵌套行 = 内层 orderedmap（索引 zlib、每个子行 zlib，live 全部用最高压缩级 9，逐字节同 live 现有行）。"""
    key_blob = b""
    row_blob = b""
    pairs = []
    for key, value in node.items():
        key_blob += key.encode("utf-8")
        row_blob += build_nested_leaf(value)
        pairs.append((len(key_blob), len(row_blob)))
    index = struct.pack("<I", len(pairs)) + b"".join(struct.pack("<II", k, r) for k, r in pairs) + key_blob
    packed = zlib.compress(index, 9)
    return struct.pack("<I", len(packed)) + packed + row_blob


def parse_nested_node(raw: bytes) -> dict[str, str]:
    import wf_quest_lib as Q
    node = Q.parse_node(raw)
    _require(isinstance(node, dict), "嵌套行不是 map")
    return node


def _stage_flat(logical: str, raw: bytes, want: dict[str, list[list[str]]]) -> tuple[bytes | None, list[str], list[str]]:
    rows = X.unpack(raw)
    old = dict(rows)
    added: list[str] = []
    problems: list[str] = []
    for key, csv_rows in want.items():
        blob = X.csv_write(csv_rows)
        if key in rows:
            if X.csv_read(rows[key]) != csv_rows:
                problems.append(f"{logical.rsplit('/', 1)[-1]}[{key}] 已在 live 且内容不同（自有键漂移，人工处理）")
            continue
        rows[key] = blob
        added.append(key)
        _require(X.csv_read(blob) == csv_rows, f"{logical} {key} CSV 往返不一致")
    if not added:
        return None, [], problems
    staged = X.pack(rows)
    back = X.unpack(staged)
    _require(list(back)[:len(old)] == list(old) and all(back[k] == v for k, v in old.items()), f"{logical} 既有键字节/顺序变了")
    _require(list(back)[len(old):] == added, f"{logical} 新键顺序不符")
    return staged, added, problems


def _stage_nested(logical: str, raw: bytes, want: dict[str, dict[str, str]]) -> tuple[bytes | None, list[str], list[str]]:
    rows = X.unpack(raw)
    old = dict(rows)
    added: list[str] = []
    problems: list[str] = []
    for key, node in want.items():
        if key in rows:
            if parse_nested_node(rows[key]) != node:
                problems.append(f"{logical.rsplit('/', 1)[-1]}[{key}] 已在 live 且内容不同（自有键漂移，人工处理）")
            continue
        rows[key] = build_nested_node(node)
        added.append(key)
        _require(parse_nested_node(rows[key]) == node, f"{logical} {key} 嵌套往返不一致")
    if not added:
        return None, [], problems
    staged = X.pack(rows)
    back = X.unpack(staged)
    _require(list(back)[:len(old)] == list(old) and all(back[k] == v for k, v in old.items()), f"{logical} 既有键字节/顺序变了")
    return staged, added, problems


def _stage_server(text: str, delta: dict[str, dict[str, Any]]) -> tuple[str | None, list[str], list[str]]:
    import wf_weapon_gacha as G
    current = json.loads(text)
    problems = [f"assets/{SERVER_SHOP}[{k}] 已在 live 且内容不同（自有键漂移，人工处理）"
                for k, v in delta.items() if k in current and current[k] != v]
    missing = {k: v for k, v in delta.items() if k not in current}
    if not missing:
        return None, [], problems
    sibling = next((k for k in ("591010102", "592000101") if k in current), next(iter(current)))
    edit = G.ServerEdit(path=(), upsert=missing, style="default", siblings=(sibling,))
    new_text, added, deleted, updated = G.splice_json(text, edit)
    _require(not deleted and not updated and sorted(added) == sorted(missing), "服务端拼接改到了本批以外的键")
    back = json.loads(new_text)
    _require(all(back[k] == v for k, v in current.items()) and all(back[k] == v for k, v in missing.items())
             and list(back)[:len(current)] == list(current), "服务端拼接后既有键变了")
    return new_text, added, problems


def stage_payloads(live: Any, out: dict[str, Any]) -> dict[str, Any]:
    """在内存里算出全部暂存内容（不写盘）。live 只需要 ``raw(logical, root='upload')`` 与 ``server_bytes(name)``。"""
    problems: list[str] = list(out["problems"])
    tables: dict[str, tuple[bytes, list[str], bytes]] = {}
    for logical in CLIENT_TABLES:
        raw = live.raw(logical)
        if raw is None:
            problems.append(f"store 里没有 {logical}")
            continue
        if logical in out["nested"]:
            staged, added, probs = _stage_nested(logical, raw, out["nested"][logical])
        else:
            staged, added, probs = _stage_flat(logical, raw, out["flat"][logical])
        problems += probs
        if staged is not None:
            tables[logical] = (staged, added, raw)
    files: dict[str, dict[str, Any]] = {}
    for logical, info in out["files"].items():
        src = Path(info["src"])
        if not src.is_file():
            problems.append(f"缺源图 {src}")
            continue
        current = live.raw(logical)
        if current is not None and stored_same_pixels(current, src):
            continue
        files[logical] = {"root": "upload", "logical": logical, "payload": png_payload(src),
                          "live_sha256": None if current is None else sha256(current)}
    server: dict[str, dict[str, Any]] = {}
    text_bytes = live.server_bytes(SERVER_SHOP)
    if text_bytes is None:
        problems.append(f"服务端文件缺失: assets/{SERVER_SHOP}")
    else:
        new_text, added, probs = _stage_server(text_bytes.decode("utf-8"), out["server"][SERVER_SHOP])
        problems += probs
        if new_text is not None:
            server[SERVER_SHOP] = {"payload": new_text.encode("utf-8"), "added": added, "live_sha256": sha256(text_bytes)}
    return {"tables": tables, "files": files, "server": server, "problems": problems}


def _refuse_live_workdir(live: Any, workdir: Path) -> None:
    target = workdir.resolve()
    for attr in ("store", "assets_dir", "cdn_root"):
        root = getattr(live, attr, None)
        if root is None:
            continue
        root = Path(root).resolve()
        if attr == "store":
            root = root.parent
        if target == root or root in target.parents:
            raise SystemExit(f"拒绝把暂存目录放进 live 路径: {target}（{root}）")


def _write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def stage(workdir: Path, live: Any, read: W.LiveReader, *, baseline: dict[str, dict] | None = None,
          art_dir: Path = ART, icon_mode: str = "new") -> dict[str, Any]:
    """写 <workdir>/plan.json 与 <workdir>/stage/{common,server}/**；problems 非空时拒绝（不写任何东西）。"""
    workdir = Path(workdir)
    _refuse_live_workdir(live, workdir)
    baseline = baseline if baseline is not None else load_baseline()
    out = build(read, baseline=baseline, art_dir=art_dir, icon_mode=icon_mode)
    out["problems"] += baseline_problems(read, baseline)
    if not out["icon_fallback"]:
        out["problems"] += banner_stale_problems(art_dir)
    payloads = stage_payloads(live, out)
    if payloads["problems"]:
        return {"refused": True, "problems": payloads["problems"]}
    stage_dir = workdir / "stage"
    if stage_dir.exists():
        shutil.rmtree(stage_dir)
    plan: dict[str, Any] = {"tables": {}, "files": {}, "server": {}, "deleted": {}}
    for logical, (staged, added, raw) in payloads["tables"].items():
        _write(stage_dir / "common" / logical, staged)
        plan["tables"][logical] = {"changed": sorted(added), "added": sorted(added), "live_sha256": sha256(raw),
                                   "staged_sha256": sha256(staged), "live_keys": len(X.unpack(raw)),
                                   "staged_keys": len(X.unpack(staged))}
    for logical, info in payloads["files"].items():
        _write(stage_dir / "common" / logical, info["payload"])
        plan["files"][logical] = {"live_sha256": info["live_sha256"], "staged_sha256": sha256(info["payload"]), "root": "upload"}
    for name, info in payloads["server"].items():
        _write(stage_dir / "server" / name, info["payload"])
        plan["server"][name] = {"live_sha256": info["live_sha256"], "staged_sha256": sha256(info["payload"]),
                                "added": sorted(info["added"]), "deleted": [], "updated": []}
    workdir.mkdir(parents=True, exist_ok=True)
    (workdir / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    table = weapon_table(out)
    report = {"weapons": table, "coin": coin_reasoning(read), "stages": out["stages"],
              "icon_mode": out["icon_mode"], "icon_fallback": out["icon_fallback"], "capabilities": out["capabilities"],
              "status_alternatives": status_alternatives(out), "needs_attention": needs_attention(out),
              "source_sha256": source_hashes(art_dir)}
    (workdir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"refused": False, "plan": plan, "weapons": table, "icon_fallback": out["icon_fallback"], "icon_mode": out["icon_mode"],
            "sizes": {**{k.rsplit("/", 1)[-1]: len(v[0]) for k, v in payloads["tables"].items()},
                      **{k.rsplit("/", 1)[-1]: len(v["payload"]) for k, v in payloads["files"].items()},
                      **{f"assets/{k}": len(v["payload"]) for k, v in payloads["server"].items()}}}


# ---------------------------------------------------------------------------
# 只读 live
# ---------------------------------------------------------------------------

def live_reader(live: Any) -> W.LiveReader:
    import wf_quest_lib as Q

    def flat(logical: str) -> dict:
        """{键: [[单元格]]}（多行键给全部行；空行给 []），与 W.LiveReader 的约定一致（wf_weapon_gacha.Live.flat 只给首行）。"""
        return {key: (X.csv_read(blob) if blob else []) for key, blob in live.rows(logical).items()}

    def nested(logical: str) -> dict:
        return Q.parse_node(live.raw(logical))

    return W.LiveReader(flat, nested, lambda name: live.server_json(name))


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_check = sub.add_parser("check", help="只读体检：逐把表 + problems（含与 live 的撞键/漂移）")
    p_table = sub.add_parser("table", help="逐把 刃值前后 / HP·ATK / 成本表")
    p_table.add_argument("--json", action="store_true")
    p_stage = sub.add_parser("stage", help="写 <workdir>/{plan.json,stage/common/**,stage/server/**}")
    p_stage.add_argument("workdir")
    for sp in (p_check, p_table, p_stage):
        sp.add_argument("--icons", choices=ICON_MODES, default="new",
                        help="new = Lv70 起换独立 PNG 图标（默认）；base = ENH c4 保持本体图标路径、不带 8 张独立 PNG（分享包退路）")
    return ap


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    args = build_parser().parse_args(argv)

    import wf_weapon_gacha as G
    live = G.Live()
    read = live_reader(live)
    baseline = load_baseline()
    if args.cmd == "stage":
        result = stage(Path(args.workdir), live, read, baseline=baseline, icon_mode=args.icons)
        if result["refused"]:
            print(json.dumps({"refused": True, "problems": result["problems"]}, ensure_ascii=False, indent=1))
            return 2
        print(render_table(result["weapons"]))
        print(json.dumps({"tables": {k.rsplit("/", 1)[-1]: len(v["changed"]) for k, v in result["plan"]["tables"].items()},
                          "files": sorted(result["plan"]["files"]), "server": {k: len(v["added"]) for k, v in result["plan"]["server"].items()},
                          "icon_mode": result["icon_mode"], "icon_fallback": result["icon_fallback"], "sizes": result["sizes"]},
                         ensure_ascii=False, indent=1))
        return 0
    out = build(read, baseline=baseline, icon_mode=args.icons)
    out["problems"] += baseline_problems(read, baseline)
    if not out["icon_fallback"]:
        out["problems"] += banner_stale_problems()
    payloads = stage_payloads(live, out)
    problems = payloads["problems"]
    table = weapon_table(out)
    if args.cmd == "table":
        print(json.dumps(table, ensure_ascii=False, indent=1) if args.json else render_table(table))
        return 0
    print(render_table(table))
    print(json.dumps({"coin": coin_reasoning(read), "stages": out["stages"],
                      "would_stage": {"tables": {k.rsplit("/", 1)[-1]: len(v[1]) for k, v in payloads["tables"].items()},
                                      "files": sorted(payloads["files"]),
                                      "server": {k: len(v["added"]) for k, v in payloads["server"].items()}},
                      "icon_mode": out["icon_mode"], "icon_fallback": out["icon_fallback"],
                      "needs_attention": needs_attention(out), "problems": problems}, ensure_ascii=False, indent=1))
    return 2 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
