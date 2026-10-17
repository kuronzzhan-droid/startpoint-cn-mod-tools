# -*- coding: utf-8 -*-
"""中秋批次 kit：凯尔 139990 ``kyle_moon``（雷 · 近战 · 冲刺型直击主 C）—— rework1。

作者 2026-09-20/21 把凯尔整套重写（``rework1/author-request.md`` 第 16 行 + 09-21 答复），
目标面板 = ``rework1/panel/kyle.json``，引擎落法 = ``rework1/panel/_deviations.json``，
逐行映射与零先例退路见施工单 ``rework1/impl/kyle.md``。三条互相咬合的轴线：

- **冲刺线**：队长位 422 冲刺参数（CD −50% / 弹射速度 +100% / 可从更高位置发动）
  ＋「冲刺 → 付与贯通」；422 只许写 ability 表，全部挂前置 42（Leader），文案由
  ``desc_override_kyle_moon`` 在队长块整体接管（hibiki 能力 5 的同一条既判偏离）。
- **直击线**：每次获得月牙后，629 追击树重新付与 ``ACAdditionalDirectAttack``，
  **段数 = 1 + 月牙层数（vlv 绑定，可超 3）**（杰拉德 v3 路线）；2026-09-27 第二批曾把
  层数贡献封顶 10，第三轮（wf_balance_20260927c_kyle）恢复 99（``PIERCE_VAR_CEIL``，＝月牙上限）。
- **月牙线**：技能 / 每 100 次直击 → 月牙 +1（上限 99 ＝「不设置上限」）→ during 134
  把层数翻成自身与全队的攻击力 / 直击伤害。

技能本体：母本 ``black_wolf_knight_wt23`` 的三段斩 + ``MoveBall``（逐格抄官方
``dog_slasher_proud_2``）＝「向最近的敌人冲刺」；自身挂固有「月狼·觉」15 秒＝强化状态，
期间每 10 次直击由 629 召唤天雷（常态 = 官方千岳十织，零克隆零染色；强化档 = 梅媞斯雷弓
克隆染冷蓝白），两档由词条 536 的 ``ConditionalsChangeSkillFlag`` 分流。

写入边界：只经 ``KitContext`` 写 ``work/character_packs/ma-kyle/``；live store / ``assets/`` /
``.cdn`` / 设备 / 存档一律不碰，不发布、不 git。
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    pass  # Imports resolve from this checkout/package, not external source copies.

import wf_client_legality as L  # noqa: E402
import wf_dsl  # noqa: E402
from wf_midautumn_dash_guard import swift_guard_plan, ability_to_leader
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_midautumn_specs as MS  # noqa: E402
import wf_kyle_pf_ring as PF  # noqa: E402

KitError = KL.KitError

KEY = "kyle"
CID, CID_S = 139990, "139990"
CODE = "kyle_moon"
ELEMENT = 2                                     # 内部 ElementKind：2 = 雷（Yellow）
ELEMENT_TOKEN = "Yellow"
TEMPLATE_ID, TEMPLATE_CODE = 141159, "black_wolf_knight_wt23"

ABILITY_KEYS = tuple(f"{CID}{slot}" for slot in range(1, 7))

# ---------------------------------------------------------------- 固有状态
# ID 一律 8 位 cid*100+n（7 位撞过基诺维）。c4 上限禁写 (None)：那是上限 1，
# during 134 按层加成与 vlv 成长会全死（记忆 wf-unique-cap-none-trap）。

UID_CRESCENT = MS.unique_condition_id(CID, 1)   # 「月牙」13999001
UID_PIERCE = MS.unique_condition_id(CID, 2)     # 旧「贯穿印」兼容资源；不再生产或读取
UID_AWAKE = MS.unique_condition_id(CID, 3)      # 「月狼·觉」13999003

ETERNAL_FRAMES = "99999999"                     # 官方 21 行里 13 行就是这个值 = 无时间限制
NO_CAP = "99"                                   # 「不设置上限」的官方写法
AWAKE_FRAMES = "900"                            # 15 秒（主控放行默认值第 1 条）

UNIQUE_DONOR = "11"                             # 官方 unique_condition[11]「能量吸取」
UNIQUE_ICON_FRAME = "battle/common/unique_condition/unique_blackflower_wiz_smr22.png"

#: (键, string_id, 显示名, 上限, 持续帧, 图标画法)
UNIQUES: tuple[tuple[str, str, str, str, str, str], ...] = (
    (UID_CRESCENT, f"unique_{CODE}_crescent", "月牙", NO_CAP, ETERNAL_FRAMES, "crescent"),
    (UID_PIERCE, f"unique_{CODE}_pierce", "贯穿印", NO_CAP, ETERNAL_FRAMES, "pierce"),
    (UID_AWAKE, f"unique_{CODE}_awake", "月狼·觉", "1", AWAKE_FRAMES, "awake"),
)
UNIQUE_ICON_ROW = {key: f"battle/common/unique_condition/{sid}" for key, sid, *_ in UNIQUES}

VOICE_KEY = f"{CODE}_voice_ready"
VOICE_ROUTE = {"kind": 1, "condition_kind": "31", "condition_id": "0"}   # 31 = 贯通

# ---------------------------------------------------------------- 自有字符串键
CAS_SWITCH = f"change_skill_{CODE}"                    # 536 的面板条目
CAS_PIERCE = f"ability_skill_{CODE}_pierce"            # 629 追击（段数成长）
CAS_THUNDER = f"ability_skill_{CODE}_thunder"          # 629 追击（天雷）
CAS_LEADER = f"desc_override_{CODE}"                   # 队长块整体接管
CAS_ABILITY = {slot: f"desc_override_{CODE}_{slot}" for slot in range(1, 7)}

PIERCE_PROGRAM = f"battle/action/skill/action/ability_skill/{CAS_PIERCE}${CAS_PIERCE}"
THUNDER_PROGRAM = f"battle/action/skill/action/ability_skill/{CAS_THUNDER}${CAS_THUNDER}"

SPEC = {
    # 本轮从「零 APK 补丁 kind」变成需要这两项（422 冲刺参数 + 面板文案接管）；
    # 两者本批 hibiki 已在用，已安装客户端具备。
    "required_capabilities": ("dash-parameter-v1", "panel-description-override-v2"),
    "extra_keys": {
        MS.UNIQUE_CONDITION_LOGICAL: tuple(key for key, *_ in UNIQUES),
        PF.TABLE: (PF.KEY,),
        KL.CAS: (CAS_SWITCH, CAS_PIERCE, CAS_THUNDER, CAS_LEADER, PF.STRING,
                 *(CAS_ABILITY[slot] for slot in range(1, 7))),
        KL.SWITCHED: (VOICE_KEY,),
    },
}

# ---------------------------------------------------------------- 行计划
# 形状：(donor 地址, donor 来源, {列号: 值}, 预期 wf_describe 回读)。
# 列号 0 基；donor 的 ``#N`` 也是 0 基。ability 126 列 / leader 124 列（leader 在 c3 之后逐列 −2）。
# 预期 describe 为 None = 首建时只记录不比对（填好后就是逐字门禁）。

#: 422「冲刺参数(可调)」是客户端补丁 kind，官方零先例，只能从本仓自制角色借行。
#: 现取响（``psychic_teleport_moon``）的 ability 5 —— 但**按 kind 定位，不按记录号**：
#: 响 1.4.974 在该键首位插了一条 413，原来的 ``#0`` 变成了 ``#1``，
#: 写死记录号的后果是下一次共享行改动时 kyle 直接构建失败（2026-09-21 实际发生过一次）。
DASH_DONOR_KEY = "1699885"
DASH_DONOR_KIND = "422"
#: 写在行计划/设计镜像里的地址：``#kind422`` = 「该键里 kind 为 422 的那条记录」，
#: build_rows 开头解析成真正的 ``#<记录号>``。
DASH_DONOR = f"{DASH_DONOR_KEY}#kind{DASH_DONOR_KIND}"
DASH_DONOR_KIND_COL = 109           # ability c109 = 瞬发内容 kind（memory wf-dash-parameter-leader-table-trap）

#: 冷却（词条 c35，单位帧，60 帧 = 1 秒；describe 会渲染成 ``(CTN秒)``）。
#: 作者真机反馈轮 2（09-21 05:1x）：「凯尔召唤雷添加ct3s」「能力3的2s后自身技能槽+10%添加ct10s」。
#: 定位一律按 kind/内容（见 ``_cooltime_problems``），不按记录号——记录号会被共享 donor 的
#: 插行打漂（1.4.974 响在 1699885 首位插 413 就打漂过冲刺行）。
THUNDER_COOLTIME = "180"            # 天雷 629：3 秒
PIERCE_GAUGE_COOLTIME = "600"       # 贯通 → 技能槽 +10%（延迟 2 秒）：10 秒

_PRE_RESONANCE_A = {6: "2", 9: "600000", 10: "600000", 11: ELEMENT_TOKEN}   # ability 前置 1：雷共鸣
_PRE_RESONANCE_A2 = {13: "2", 16: "600000", 17: "600000", 18: ELEMENT_TOKEN}  # ability 前置 2
_PRE_LEADER_A = {6: "42"}                                                   # ability 前置 1：持有者为队长
_PRE_RESONANCE_L = {4: "2", 7: "600000", 8: "600000", 9: ELEMENT_TOKEN}     # leader 前置 1：雷共鸣

#: 月牙每层 → 攻击力 / 直击伤害，雷共鸣 → 技能槽上限 / 充能速度。
#: ⚠ during 134 × target 1（除自身全员）官方与 live 双零先例 ⇒ 不开首例，
#: 改用「t5 全队(雷) 低值 + t0 自身补差」的等价拆分（施工单 R2），合计数值与面板逐字一致。
#: 2026-09-27 作者平衡批次（方案A）：删去「月牙每层 → 自身眩晕蓄积(Stunify 19) +25%」那一项
#: （09-23 追加的 Down 成长）；贯穿 → 雷队眩晕畏缩特攻 5%（面板「追击伤害」）保留。
#: 修订模块 wf_balance_20260927_kyle 断言本表输出 == 其 revise() 输出。
#:
#: 2026-09-27 第二批（口径 A：无上限成长移队长并放缓，wf_balance_20260927b_kyle）：
#: 月牙 3 分钟约 35–60 层（队长位约 60）、贯穿约 30–60 次 ⇒ 都 ≥30 次 ⇒ 每步 ×1/10；
#: 能力 2 两条逐层成长（各 50%）按 ×1/10 搬进同触发/同 kind/同目标/同前置的队长行（合并）。
#:
#: 2026-09-27 第三轮（成长复核，wf_balance_20260927c_kyle）：作者「凯尔的成长降太低了，本身数值就不高」
#: 「砍到4/5」⇒ 第二批 ×1/10 作废，改为 原值×4/5（合并行按两部分原值之和），数值取 5 的倍数。
#: 下面四个值 = (原值 ＋ 搬入原值)×4/5，修订模块断言本表输出 == 其 revise() 输出。
CRESCENT_TEAM_ATTACK = "10000"      # 12.5% ×4/5 = 10%（批二 1.25%）
CRESCENT_SELF_ATTACK = "50000"      # (12.5% ＋ 能力2#1 自身攻击 50%) ×4/5 = 50%（批二 6.25%）
CRESCENT_TEAM_DIRECT = "60000"      # (25% ＋ 能力2#0 雷队直击 50%) ×4/5 = 60%（批二 7.5%）
CRESCENT_SELF_DIRECT = "20000"      # 25% ×4/5 = 20%（批二 2.5%）
#: 能力 2 两条逐层成长的层数上限（原 (None) = 不限；第二批起 10，第三轮口径 D4 保持）。
CRESCENT_ABILITY_LIMIT = "10"
#: 贯穿 → 雷队攻击力 / 眩晕畏缩特攻（面板原写「追击伤害」，第三轮 D 节按数据改为特攻写法）：25% → 20%、5% → 4%（第三轮 ×4/5；
#: 原值 ≤10% 按 0.5% 取整；批二 2.5% / 0.5%）。
PIERCING_GROWTH = (("32", "20000"), ("53", "4000"))
LEADER: tuple[tuple[str, str, dict[int, str], str | None], ...] = (
    ("161123#0", "official",
     {0: CODE, **_PRE_RESONANCE_L, 100: "(None)", 102: UID_CRESCENT, 107: "0", 108: "5",
      109: ELEMENT_TOKEN, 111: CRESCENT_TEAM_ATTACK, 112: CRESCENT_TEAM_ATTACK},
     None),
    ("161063#2", "official",
     {0: CODE, **_PRE_RESONANCE_L, 98: "100000", 99: "100000", 100: "(None)",
      102: UID_CRESCENT, 107: "0", 108: "0", 109: "",
      111: CRESCENT_SELF_ATTACK, 112: CRESCENT_SELF_ATTACK},
     None),
    ("161123#0", "official",
     {0: CODE, **_PRE_RESONANCE_L, 100: "(None)", 102: UID_CRESCENT, 107: "1", 108: "5",
      109: ELEMENT_TOKEN, 111: CRESCENT_TEAM_DIRECT, 112: CRESCENT_TEAM_DIRECT},
     None),
    ("161063#2", "official",
     {0: CODE, **_PRE_RESONANCE_L, 98: "100000", 99: "100000", 100: "(None)",
      102: UID_CRESCENT, 107: "1", 108: "0", 109: "",
      111: CRESCENT_SELF_DIRECT, 112: CRESCENT_SELF_DIRECT},
     None),
    ("131122#2", "official",
     {0: CODE, **_PRE_RESONANCE_L, 46: "5", 47: ELEMENT_TOKEN,
      49: "20000", 50: "20000"},
     "雷·编成≥6 时: 赋予全队(雷) 2号位技能槽 20%"),
    ("141165#2", "official",
     {0: CODE, **_PRE_RESONANCE_L, 46: "5", 47: ELEMENT_TOKEN,
      49: "20000", 50: "20000"},
     "雷·编成≥6 时: 赋予全队(雷) 技能槽充能 20%"),
)

_STATUE = {1: "attack_common", 2: "attack_common", 3: "condition",
           4: "attack_common", 5: "special", 6: "attack_common"}
#: c1 是整键语义（``get_unisonable`` 只读 ``values[0]``）⇒ 同键所有记录必须一致。
#: 作者真机反馈轮 2（09-21 05:1x）：「凯尔的能力1和2都带上主位限制」⇒ 槽 1/2/3 都是 false。
#: ⚠ 能力 1 里有「切换技能形态」（536）与技能强化条目，改主位限制后他在合击位时技能不再强化，
#: 这是作者明确要求的取舍（施工单 §反馈轮 2）。面板的主位图标由 PANEL_ABILITY 从这张表派生。
_UNISONABLE = {1: "false", 2: "false", 3: "false", 4: "true", 5: "true", 6: "true"}
#: 主位限制槽的集合（派生，别再手写第二份）：面板图标、629 宿主校验都读它。
MAIN_ONLY_SLOTS = frozenset(slot for slot, value in _UNISONABLE.items() if value == "false")

PLAN: dict[int, tuple[tuple[str, str, dict[int, str], str | None], ...]] = {
    # ---- 能力 1：开局技能槽 + 共鸣强化技能
    1: (
        ("2310933#0", "official", {51: "50000", 52: "50000"}, None),
        ("1110014#0", "official", {**_PRE_RESONANCE_A, 51: "50000", 52: "50000"}, None),
        ("1411113#0", "official", {11: ELEMENT_TOKEN, 70: CAS_SWITCH}, None),
    ),
    # ---- 能力 2：月牙每层（2026-09-27 第二批：无上限部分已按 ×1/10 并入队长行 #2/#1，
    #      这里换成有上限的弱化版：限 10 层（c102=10，官方 134 限次族 1611231–1611236 同写法），
    #      雷队直击每层 +10%（满 +100%）、自身攻击每层 +16%（满 +160%），数值按设计稿）
    2: (
        ("1610633#0", "official",
         {**_PRE_RESONANCE_A, 100: "100000", 101: "100000", 102: CRESCENT_ABILITY_LIMIT,
          104: UID_CRESCENT, 109: "1", 110: "5", 111: ELEMENT_TOKEN,
          113: "10000", 114: "10000"},
         None),
        ("1611233#2", "official",
         {**_PRE_RESONANCE_A, 102: CRESCENT_ABILITY_LIMIT, 104: UID_CRESCENT, 109: "0", 110: "0",
          113: "16000", 114: "16000"},
         None),
    ),
    # ---- 能力 3（Ⓜ）：月牙生产 + 直击段数 + 两棵 629 追击
    3: (
        ("1611231#0", "official",
         {**_PRE_RESONANCE_A, 28: "5", 29: ELEMENT_TOKEN,
          51: "100000", 52: "100000", 68: UID_CRESCENT}, None),
        ("1611231#0", "official",
         {**_PRE_RESONANCE_A, 27: "20", 28: "7", 29: ELEMENT_TOKEN,
          30: "10000000", 31: "10000000", 34: "(None)",
          51: "100000", 52: "100000", 68: UID_CRESCENT},
         None),
        # 贯通 → 2 秒后技能槽 +10%；作者反馈轮 2 要求 CT 10 秒（否则连续贯通时几乎白送满槽）
        ("2110012#0", "official",
         {**_PRE_RESONANCE_A, 34: "(None)", 35: PIERCE_GAUGE_COOLTIME,
          46: "2", 47: "211", 48: "0", 51: "10000", 52: "10000"},
         None),
        ("1412012#2", "official",
         {6: "187", 7: "0", 12: UID_CRESCENT, **_PRE_RESONANCE_A2,
          48: "5", 49: ELEMENT_TOKEN, 51: "300000", 52: "300000"},
         None),
        # 两个生产月牙的事件都在上方先加层，再重算自身直击段数。
        # 不再生产独立的贯穿印，也不需要等下一次获得贯穿才刷新。
        ("1611053#0", "official",
         {**_PRE_LEADER_A, **_PRE_RESONANCE_A2, 27: "23", 28: "5", 29: ELEMENT_TOKEN,
          30: "100000", 31: "100000", 34: "(None)", 35: "0",
          70: CAS_PIERCE, 71: PIERCE_PROGRAM},
         None),
        ("1611053#0", "official",
         {**_PRE_LEADER_A, **_PRE_RESONANCE_A2, 27: "20", 28: "7", 29: ELEMENT_TOKEN,
          30: "10000000", 31: "10000000", 34: "(None)", 35: "0",
          70: CAS_PIERCE, 71: PIERCE_PROGRAM},
         None),
        # 强化状态中每 10 次自身直击 → 召唤天雷（trigger 20 传入被打的敌人，非 null）
        # 作者反馈轮 2：召唤雷加 CT 3 秒（c35 = 180 帧）
        ("1611053#0", "official",
         {6: "187", 7: "0", 12: UID_AWAKE, **_PRE_RESONANCE_A2,
          27: "20", 28: "0", 30: "1000000", 31: "1000000", 34: "(None)",
          35: THUNDER_COOLTIME, 70: CAS_THUNDER, 71: THUNDER_PROGRAM},
         None),
    ),
    # ---- 能力 4：里布拉姆写法（by_each_trigger_puller）
    4: (
        ("1211593#0", "official",
         {11: ELEMENT_TOKEN, 29: ELEMENT_TOKEN, 47: "0", 48: "5", 49: "",
          51: "100000", 52: "100000"},
         None),
        ("1211593#0", "official",
         {11: ELEMENT_TOKEN, 29: ELEMENT_TOKEN, 47: "214", 48: "5", 49: "",
          51: "100000", 52: "100000"},
         None),
    ),
    # ---- 能力 5：直击计数回槽 + 队长位冲刺参数（4 条 422，不进面板）
    # 2026-09-27 作者平衡批次（方案A）：删去同触发的「雷队眩晕蓄积(Stunify 51) +100%」行。
    5: (
        ("1510573#1", "official",
         {**_PRE_RESONANCE_A, 29: ELEMENT_TOKEN, 30: "5000000", 31: "5000000",
          34: "(None)", 35: "0", 47: "35", 48: "5", 49: ELEMENT_TOKEN,
          51: "5000", 52: "5000"},
         None),
        (DASH_DONOR, "store", {**_PRE_LEADER_A, 113: "100000", 114: "100000", 118: "1"}, None),
        (DASH_DONOR, "store", {**_PRE_LEADER_A, 113: "-50000", 114: "-50000", 118: "0"}, None),
        (DASH_DONOR, "store", {**_PRE_LEADER_A, 113: "40000", 114: "40000", 118: "6"}, None),
        swift_guard_plan(CODE, -50000, statue="special"),
        # 冲刺 → 贯通 5.5 秒（330 帧 ×100000）
        ("1110023#0", "official",
         {**_PRE_LEADER_A, **_PRE_RESONANCE_A2, 27: "4", 28: "", 30: "100000", 31: "100000",
          34: "(None)", 35: "0", 48: "0", 57: "33000000", 58: "33000000",
          59: "100000", 60: "100000"},
         None),
    ),
    # ---- 能力 6：冻结特攻（kind 119 FrozenSlayer；驱散 + 冻结本体 ACFrozen 在强化档 DSL 里）
    6: (
        ("2210013#0", "official",
         {**_PRE_RESONANCE_A, 49: ELEMENT_TOKEN, 51: "15000", 52: "15000"}, None),
    ),
}

#: 首建实跑出来的 ``wf_describe`` 回读，烤成逐字门禁：donor 漂移 / 描述器改版 / 改错格
#: 都会在这里当场炸。面板上真正显示的是 ``desc_override_*``（PANEL_LEADER / PANEL_ABILITY），
#: 这张表只管「表行本身渲染成什么」。
EXPECT: dict[str, str] = {
    "kyle-native-pf": "自身 强化弹射覆盖",
    "leader#4": "雷·编成≥6 时: 赋予全队(雷) 2号位技能槽 20%",
    "leader#5": "雷·编成≥6 时: 赋予全队(雷) 技能槽充能 20%",
    "leader#6": "雷·编成≥6 时: 状态贯通≥1 → 赋予全队(雷) 攻击力 20%",
    "leader#7": "雷·编成≥6 时: 状态贯通≥1 → 赋予全队(雷) 眩晕畏缩特攻 4%",
    "leader#0": "雷·编成≥6 时: 持续·状态累积计数固有≥1[固有13999001] → 赋予全队(雷) 攻击力 10%",
    "leader#1": "雷·编成≥6 时: 持续·状态累积计数固有≥1[固有13999001] → 自身 攻击力 50%",
    "leader#2": "雷·编成≥6 时: 持续·状态累积计数固有≥1[固有13999001] → 赋予全队(雷) Direct伤害 60%",
    "leader#3": "雷·编成≥6 时: 持续·状态累积计数固有≥1[固有13999001] → 自身 Direct伤害 20%",
    "1399901#0": "赋予全队(雷) 技能槽 50%",
    "1399901#1": "雷·编成≥6 时: 自身 技能槽 50%",
    "1399901#2": "雷·编成≥6 时: 自身 切换技能形态[change_skill_kyle_moon]",
    "1399902#0": "雷·编成≥6 时: 持续·状态累积计数固有≥1(限10次)[固有13999001] → 赋予全队(雷) Direct伤害 10%",
    "1399902#1": "雷·编成≥6 时: 持续·状态累积计数固有≥1(限10次)[固有13999001] → 自身 攻击力 16%",
    "1399903#0": "雷·编成≥6 时: 技能发动≥1 → 自身 状态固有 100%×1次",
    "1399903#1": "雷·编成≥6 时: 编成直接攻击≥100 → 自身 状态固有 100%×1次",
    "1399903#2": "雷·编成≥6 时: 状态贯通≥1(CT10秒) → 自身 技能槽 10%(延迟2秒)",
    "1399903#3": "状态固有[固有13999001] 且 雷·编成≥6 时: 赋予全队(雷) DirectAttack3 300%",
    "1399903#4": "队长 且 雷·编成≥6 时: 技能发动≥1 → 自身 发动技能动作[ability_skill_kyle_moon_pierce]",
    "1399903#5": "队长 且 雷·编成≥6 时: 编成直接攻击≥100 → 自身 发动技能动作[ability_skill_kyle_moon_pierce]",
    "1399903#6": "状态固有[固有13999003] 且 雷·编成≥6 时: 编成直接攻击≥10(CT3秒) → 自身 发动技能动作[ability_skill_kyle_moon_thunder]",
    "1399904#0": "雷·编成≥6 时: 技能发动≥1 → 赋予全队 状态攻击力 100%(15秒)×1次",
    "1399904#1": "雷·编成≥6 时: 技能发动≥1 → 赋予全队 状态Direct伤害 100%(15秒)×1次",
    "1399905#0": "雷·编成≥6 时: 编成直接攻击≥50 → 赋予全队(雷) 技能槽充能 5%",
    "1399905#1": "队长 时: 持续·HP≤1 → 自身 冲刺参数(可调) 100%",
    "1399905#2": "队长 时: 持续·HP≤1 → 自身 冲刺参数(可调) -50%",
    "1399905#3": "队长 时: 持续·HP≤1 → 自身 冲刺参数(可调) 40%",
    "1399905#4": "队长 时: 持续·状态冲刺 → 自身 冲刺参数(可调) 175%",
    "1399905#5": "队长 且 雷·编成≥6 时: 冲刺≥1 → 自身 状态贯通(5.5秒)×1次",
    "1399906#0": "雷·编成≥6 时: 赋予全队(雷) 冻结特攻 15%",
}

#: 内容 kind 黑名单：201/202/521 的**瞬发常驻**形态受 C2308 限制（本套件的 202 触发写
#: Initial ⇒ 不在此列）；724 Fever 比例、713 独立乘区本套件不用。
FORBIDDEN_CONTENT_KINDS = ("201", "521", "713", "724")
#: 前置 kind 白名单（裁决 §8：前置留空 = 角色页 C7050，只用有先例的几种）。
#: 2 = 元素编成、3 = MySelf、38 = 状态贯通、42 = Leader、187 = ConditionUnique、202 = OwnerIsMain。
ALLOWED_PRECONDITION_KINDS = ("", "0", "2", "3", "38", "42", "187", "202")

# ---------------------------------------------------------------- 面板文案
# 逐行抄 rework1/panel/kyle.json（作者已过目的那一版）。describe 渲染表达不了的整块接管。
# 一条记录一行，用换行符分行（禁止用「／」挤成一行）；主位限制槽（MAIN_ONLY_SLOTS，本轮 = 1/2/3）
# 的 desc_override 会盖掉客户端逐行画的 Ⓜ，所以每行都要自带 MAIN_ICON
# （写法与 wf_featured_main_ability 的共享常量一致）。

MAIN_ICON = " <icon id='main'>  "

#: 2026-09-27 第三轮（wf_balance_20260927c_kyle）：月牙逐层 / 贯穿成长 = 原值×4/5（含能力 2 搬入部分），
#: 自身 = 全队(雷)行 + 自身行合计；直击判定次数的段数成长 DSL 上限恢复 99（= 月牙上限；第二批曾封顶 10
#: 并单列上限），逐层成长都没有上限 ⇒ 按裁决 §3 写到效果为止（不写「无上限」之类禁语）。
#: 同轮面板共鸣省略（作者「…获取带X属性共鸣，…提供的效果就不用写X属性共鸣」）：「月牙」只由能力 3 #0/#1
#: 获取且都带雷共鸣 ⇒ 月牙提供的效果行（队长第 4、5 行，能力 2 第 1 行，能力 3 末行）不写共鸣前缀，
#: 数据前置不动（wf_balance_20260927c_kyle.RESONANCE_DROPS）。
#: 同轮面板统一口径（wf_balance_20260927c_kyle D 节）：队长 / 能力 2 / 能力 3 / 能力 6 面板的共鸣前缀写「雷属性共鸣时，」；
#: 第 2 行「强化自身冲刺」的冲刺参数行（能力 5 #1–#4）只挂队长前置、没有雷共鸣 ⇒ 不写共鸣前缀；
#: 第 6 行第二个效果的数据是队长 #7 kind 53 眩晕畏缩特攻（不是追击伤害）⇒ 沿用能力 6 的特攻写法。
PANEL_LEADER = "\n".join((
    PF.TEXT,
    "强化自身冲刺",
    "自身冲刺间隔无法进一步缩短",
    "自身“月牙”每上升1层，自身攻击力＋60%、直击伤害＋80%；"
    "除自身外雷属性角色攻击力＋10%、直击伤害＋60%",
    "自身“月牙”每上升1层，自身直击判定次数＋1",
    "雷属性共鸣时，自身每获得一次贯穿效果，雷属性角色攻击力＋20%，"
    "对处于“眩晕”、“畏缩”状态的敌人造成伤害，额外乘区＋4%",
    "雷属性共鸣时，雷属性角色技能槽最大值＋20%、技能充能速度＋20%",
))

#: 技能强化条目（主会话 2026-09-27 口径 R1–R3，wf_balance_20260927c_kyle E 节）：能力 1 #2 kind 536（旗号 1）的 c70 文案，
#: 官方格式点名技能、定性不写数字；内容 = 两档技能树旗号 1 开支（队伍贯穿 / 直接攻击伤害提升 / 加速，最近敌人消除强化效果
#: + 冻结）与 629 天雷树的强化档。能力 1 面板第 3 行 = 共鸣前缀 + 同文（开关行带雷≥6 共鸣前置）。
SKILL_NAME = "月华·狼牙连斩"
CAS_SWITCH_TEXT = (f"强化『{SKILL_NAME}』：追加赋予队伍贯穿、直接攻击伤害提升与加速效果，"
                   "消除距离最近的敌人的部分强化效果并赋予其冻结效果，同时强化自身直击召唤的天雷")

_PANEL_ABILITY_LINES = {
    # 2026-09-27 技能强化条目口径（wf_balance_20260927c_kyle PANEL_ENHANCEMENTS）：原第 2 行把 #1 自身技能槽与 #2 技能强化
    # 挤在一句 ⇒ 拆成数值行 + 强化条目行（与 CAS_SWITCH 同文），两行数据都带雷共鸣前置，口径 3 冒号改逗号。
    1: ("战斗开始时：雷属性角色技能槽＋50%",
        "雷属性共鸣时，自身技能槽＋50%",
        "雷属性共鸣时，" + CAS_SWITCH_TEXT),
    2: ("自身“月牙”每提升1层，自身攻击力＋16%、雷属性角色直击伤害＋10%"
        "（最多10层）",),
    # 2026-09-27 暂存前最后一轮（wf_balance_20260927c_kyle PANEL_SPLITS，主会话口径 5 扩展）：原第 1 行用「；」
    # 挤了两种数据条件（#0 雷属性角色发动技能 / #1 每 100 次直击）⇒ 拆两行，两行都是月牙获取行，各自照写共鸣前缀。
    3: ("雷属性共鸣时，雷属性角色发动技能时，自身“月牙”＋1层",
        "雷属性共鸣时，雷属性角色每造成100次直击，自身“月牙”＋1层",
        "雷属性共鸣时，自身每获得一次贯穿效果，2秒后自身技能槽＋10%（冷却时间：10秒）",
        "自身持有“月牙”时，强化雷属性角色的直接攻击为3次，合计伤害额外乘区＋300%"),
    4: ("雷属性共鸣时：雷属性角色发动技能时，赋予全队直击伤害＋100%、攻击力＋100%（持续1"
        "5秒，每名触发该效果的角色分别独立生效）",),
    5: ("雷属性共鸣时：雷属性角色每造成50次直击，雷属性角色技能充能速度＋5%",),
    # 2026-09-27 暂存前最后一轮（wf_balance_20260927c_kyle PANEL_CORRECTIONS，主会话追加 C）：原第 2 行（现唯一一行）的数据是
    # 1399906#0 kind 119 FrozenSlayer，状态本体是强化档 DSL 的 ACFrozen ⇒「迟缓」按数据改「冻结」；口径 3 冒号改逗号；
    # 原第 1 行「进一步强化技能…」：能力 6 没有技能开关行，强化条目已在能力 1 面板 ⇒ 删除（技能强化条目口径，2026-09-27）。
    6: ("雷属性共鸣时，雷属性角色对处于“冻结”状态的敌人造成伤害，额外乘区＋15%",),
}

#: 主位限制槽（整键 c1="false"）每行带 MAIN_ICON；与 _UNISONABLE 同源，write_strings 再逐行核一次
PANEL_ABILITY = {
    slot: "\n".join((MAIN_ICON + line) if _UNISONABLE[slot] == "false" else line
                     for line in lines)
    for slot, lines in _PANEL_ABILITY_LINES.items()
}

CAS_TEXTS = {
    PF.STRING: PF.TEXT,
    CAS_SWITCH: CAS_SWITCH_TEXT,
    CAS_PIERCE: "自身直击敌人的判定次数＋1",
    CAS_THUNDER: "召唤天雷攻击该敌人",
    CAS_LEADER: PANEL_LEADER,
    **{CAS_ABILITY[slot]: PANEL_ABILITY[slot] for slot in range(1, 7)},
}

# ---------------------------------------------------------------- 特效与 DSL

FX_BLADE_SRC = f"battle/effect/skill_unique/{TEMPLATE_CODE}"
FX_BLADE_SUB = "blade"
FX_BLADE_DST = f"battle/effect/skill_unique/{CODE}/{FX_BLADE_SUB}"

#: 强化档天雷 = 梅媞斯（雷弓）131004；常态档直接引用官方千岳十织，零克隆零染色
#: （作者 09-21 同意；全克隆千岳会让图集 fits=False，卡 C §3.4）。
#: 子目录名与 LUT 文件名都按特效素材代理的交付件（rework1/fx/kyle/README.md §2/§3）。
FX_BOLT_TEMPLATE = "thunder_archer"
FX_BOLT_SRC = f"battle/effect/skill_unique/{FX_BOLT_TEMPLATE}"
FX_BOLT_SUB = "thunder_enhanced"
FX_BOLT_DST = f"battle/effect/skill_unique/{CODE}/{FX_BOLT_SUB}"
FX_BOLT_LUT = "fx_lut.thunder_archer.json"
#: 母本指纹（卡 C §3.2 实读）：sheet 125×462、atlas 59 rect、4 个基名。任一不符 = 母本漂移，拒绝。
FX_BOLT_FINGERPRINT = {"sheet": (125, 462), "bases": 4}

#: 「角色移动时身后的那个特效」= 心角（梅姆拉姆 131068）的光环族，染成雷金。
#: 作者 09-21 澄清：小人本体一格不改，换的是这个独立 ShowEffect（做法同校园奈芙的整族克隆）。
#: 落点＝技能冲刺块上的拖尾（特效代理 README §3.3 的推荐，登记为偏离待作者确认）。
FX_TRAIL_TEMPLATE = "horn_leader"
FX_TRAIL_SRC = f"battle/effect/skill_unique/{FX_TRAIL_TEMPLATE}"
FX_TRAIL_SUB = "moving_trail"
FX_TRAIL_DST = f"battle/effect/skill_unique/{CODE}/{FX_TRAIL_SUB}"
FX_TRAIL_LUT = "fx_lut.horn_leader.json"
FX_TRAIL_BASE = f"{FX_TRAIL_TEMPLATE}_aura"          # 全族唯一带 loop 序列的基名
FX_TRAIL_FINGERPRINT = {"sheet": (523, 256)}
FX_TRAIL_EFFECT = f"{FX_TRAIL_DST}/{FX_TRAIL_BASE}"
FX_TRAIL_LABEL = "月狼の尾"
FX_TRAIL_FRAMES = 60                                  # 与 MoveBall 的 60 帧对齐，卡 loop 边界
FX_TRAIL_SCALE = 2.5                                  # 官方原件只有 51×50，2.5 是代理给的居中起点

#: 风绿 → 雷黄的兜底色相区间（blade 族）；exact 色表在设计稿里。
FX_HUE_FALLBACK = [
    {"from": [75, 160], "sat_min": 0.12, "val_min": 0.04,
     "hue_set": 52, "sat_scale": 1.05},
    {"from": [160, 215], "sat_min": 0.12, "val_min": 0.04,
     "hue_set": 201, "sat_scale": 0.80, "val_scale": 1.02},
]

THUNDER_NORMAL_DONOR = "battle/action/skill/action/rare5/psychic_tohru$psychic_tohru_1"
THUNDER_BOOST_DONOR = "battle/action/skill/action/rare5/thunder_archer$thunder_archer_1"
FROZEN_DONOR = "battle/action/skill/action/rare5/dog_slasher_proud$dog_slasher_proud_2"
ADDITIONAL_DONOR = "battle/action/skill/action/rare5/silence_suzuka$silence_suzuka_2"
PIERCING_DONOR = "battle/action/skill/action/rare5/black_wolf_knight$black_wolf_knight_2"
DIRECT_DONOR = ("battle/action/skill/action/rare5/"
                "combat_animal_meteor23$combat_animal_meteor23_2")
SPEEDUP_DONOR = "battle/action/skill/action/rare5/wind_spgirl_1anv$wind_spgirl_1anv_2"

#: 母本整树的命令计数指纹：任何一项对不上都说明母本漂移或改错了结构。
DONOR_COMMAND_COUNTS = {
    "FindNearSubjects": 1, "CreateReferencePoint": 1, "StopBall": 1, "ShowEffect": 3,
    "CreateHitArea": 2, "ShakeCamera": 2, "CreateNormalAttack": 2,
    "FindAllSubjects": 2, "CreateCondition": 1,
}

#: Z6 开关：True = 把母本的 StopBall 换成官方同形的 MoveBall（＝「向最近的敌人冲刺」）。
#: 真机若发现三段斩与球脱节，改成 False 就退回母本行为（面板「冲刺」改写「突进斩」）。
DASH_REPLACES_STOPBALL = True
#: 逐格抄官方 dog_slasher_proud_2（唯一「冲向最近敌人再砍」的现成蓝本）。
MOVE_BALL = ["MoveBall", -18, ["GH", 0], 0, 60, 3, ["KeepGoing"], True]

RP_LIFETIME = 130                    # 容下第 92 帧的第三段（寿命 20 ⇒ 最晚 112 帧）
FINISH_WAIT = 92
FINISH_BINDS = (8, 9, 10)
FINISH_EFFECT = ("battle/effect/skill_unique/light_adventurer_4anv/"
                 "light_adventurer_4anv_ground_thunder")
FINISH_EFFECT_ANCHOR = ["AB"]
FINISH_EFFECT_SCALE = ["Some", [{"min": 3, "max": 3}]]

HITAREA_EDITS = {
    0: {"radius": 260, "lifetime": 12, "max_hits": 1},
    1: {"radius": 280, "lifetime": 40, "max_hits": 14},
}
FINISH_HITAREA = {"radius": 320, "lifetime": 20, "max_hits": 1, "break_weak_point": True}
BUFF_TARGET_AS_DIRECT = 4

#: ⚠ 键名沿用 0 基参数号：``p12`` 写 node[13] = **削韧**（参数卡 p13），``p13`` 写 node[14] = Fever 点。
#: 2026-09-27 第二批（口径 B1：技能每次施放单目标总削韧 ≤30）：首斩 10→8、终斩 12→8，
#: 连斩 1×14 不动 ⇒ 8 + 14 + 8 = 30（原 10 + 14 + 12 = 36）；Fever 点不动。
CNA_SHAPE = {
    0: {"subject": 4, "base": 200, "p12": 8, "p13": 5},
    1: {"subject": 7, "base": 3, "p12": 1, "p13": 0.5},
    2: {"subject": 10, "base": 200, "p12": 8, "p13": 6},
}
CNA_MULT = {
    "1": ({"min": 26, "max": 30}, {"min": 0.429, "max": 0.5}, {"min": 30, "max": 34}),
    "2": ({"min": 30, "max": 34}, {"min": 0.5, "max": 0.6}, {"min": 34, "max": 38}),
}
EFFECT_NAMES = {0: "月牙斬", 1: "狼牙連斬", 2: "爆発", 3: "月華終斬"}

#: 强化档追加的队伍状态（帧数；贯通 5.5 秒 / 加速 15 秒 —— 面板逐字）。
BOOST_PIERCING_FRAMES = 330
BOOST_SPEEDUP_FRAMES = 900
BOOST_DIRECT_FRAMES = 900
BOOST_DIRECT = {"1": (1.0, 1.0), "2": (1.2, 1.5)}
BOOST_SPEEDUP = {"1": (1.0, 1.0), "2": (1.0, 1.0)}
FROZEN_FRAMES = 900                  # 冻结（ACFrozen）15 秒（官方带 900/1200）
DISPEL_COUNT = 2                     # 驱散敌方 2 个增益
ENEMY_BIND = 20                      # 强化档驱散/冻结块的绑定号（与主树 1/4/7/8/9/10 不冲突）

#: 段数成长：段数 = 1 + min(月牙层数, 上限)（vlv）；合计伤害 300% 与能力 3 的 202 等值，
#: 使 ``AdditionalDirectAttackContent.getBetter``（段数多者胜，段数同比伤害%）在 ≥3 层时取本条。
#: 上限 = ``BindConditionAccumulationVariable`` 第 5 参（客户端 ActionEvaluator case 101：
#: ``bind(vid, min(累积层数 / 第4参, 第5参))``）。2026-09-27 第二批（口径 A5）曾 99 → 10；
#: 第三轮（口径 U1，wf_balance_20260927c_kyle）恢复 99（int，＝月牙固有上限 NO_CAP）：调用方只有
#: 能力 3 的两条 629（前置 42 仅队长 ＋ 前置2 雷共鸣）⇒ 本来就只在「当队长且雷共鸣」时执行，不加旗号。
PIERCE_VAR_ID = 1
PIERCE_VAR_CEIL = int(NO_CAP)
PIERCE_FRAMES = int(ETERNAL_FRAMES)   # 跟随常驻月牙；不能在 20 秒后丢失已经取得的段数
PIERCE_BASE_TIMES = 1
PIERCE_TIMES_PER_LAYER = 1
PIERCE_DAMAGE = 3.0
PIERCE_CONDITION_KEY = "月牙貫通追撃"

#: 天雷倍率（连击成长开关只在强化档打开 ⇒ 基础倍率按 500 连击 ×3.5 反推压低）。
THUNDER_MULT_NORMAL = {"min": 14.0, "max": 16.0}
THUNDER_MULT_BOOST = {"min": 5.0, "max": 6.0}
#: 天雷削韧（CreateNormalAttack node[13]）。触发 CT 3 秒（THUNDER_COOLTIME）⇒ 口径 B3「CT ≤3 秒的
#: 629 每次 ≤1」：常态单段 20 → 1；强化 5 段（CalculatedUsingMaxNumOfHits 5、Some 5）3.6 → 0.2 ＝ 1。
#: 母本（千岳十织 20 / 梅媞斯雷弓 3.6）只有这一格被覆盖。
THUNDER_DETOUGHNESS_NORMAL = 1
THUNDER_DETOUGHNESS_BOOST = 0.2
THUNDER_BOOST_BIND_OFFSET = 30       # 强化分支整体重映射，避免与常态分支重号


# ---------------------------------------------------------------- 设计稿对照

def load_design(root: Path) -> dict[str, Any]:
    design = MS.load_design(Path(root), KEY)
    if not design:
        raise KitError(f"design/{KEY}.json missing (batch {MS.BATCH_DIR})")
    if (design.get("schema"), design.get("cid"), design.get("code")) != ("ma-design/1", CID, CODE):
        raise KitError(f"design identity drift: {design.get('schema')} "
                       f"{design.get('cid')} {design.get('code')}")
    return design


def _design_problems(design: dict[str, Any]) -> list[str]:
    """设计稿 ``plan.rework1`` 是本模块 PLAN/LEADER/UNIQUES 的镜像：两边漂移即红。"""
    problems: list[str] = []
    plan = (design.get("plan") or {}).get("rework1")
    if not isinstance(plan, dict):
        return ["design/kyle.json plan.rework1 missing（本轮重做的镜像块）"]
    want_leader = [f"{src}:{addr}" for addr, src, _cells, _d in LEADER]
    if list(plan.get("leader") or []) != want_leader:
        problems.append(f"leader donor mirror drift: {plan.get('leader')} != {want_leader}")
    ability = plan.get("ability") or {}
    for slot, rows in PLAN.items():
        key = f"{CID}{slot}"
        want = [f"{src}:{addr}" for addr, src, _cells, _d in rows]
        if list(ability.get(key) or []) != want:
            problems.append(f"ability {key} donor mirror drift: {ability.get(key)} != {want}")
    want_unique = [key for key, *_ in UNIQUES]
    if list(plan.get("unique_conditions") or []) != want_unique:
        problems.append(f"unique mirror drift: {plan.get('unique_conditions')} != {want_unique}")
    want_programs = sorted([PIERCE_PROGRAM, THUNDER_PROGRAM])
    if sorted(plan.get("ability_skill_programs") or []) != want_programs:
        problems.append(f"ability_skill program mirror drift: {plan.get('ability_skill_programs')}")
    return problems


# ---------------------------------------------------------------- 行装配

def _ban_kinds(kind: str, rows: list[list[str]], label: str) -> None:
    """内容 kind 黑名单 + 前置 kind 白名单 + 422 的两条硬规矩。"""
    if kind == "ability":
        content, precondition = (47, 109), (6, 13, 20)
    else:
        content, precondition = (45, 107), (4, 11, 18)
    for index, row in enumerate(rows):
        for col in content:
            if row[col] in FORBIDDEN_CONTENT_KINDS:
                raise KitError(f"{label}#{index}: forbidden content kind {row[col]!r} at c{col}")
        for col in precondition:
            if row[col] not in ALLOWED_PRECONDITION_KINDS:
                raise KitError(f"{label}#{index}: precondition kind {row[col]!r} at c{col} "
                               f"is outside the vetted set {ALLOWED_PRECONDITION_KINDS}")
        if kind == "leader_ability" and row[107] in ("422", "724", "713"):
            # LeaderAbilityValues.parseAt107 没打补丁 ⇒ 队长表写 422 = 角色页 C7050
            raise KitError(f"{label}#{index}: 队长表禁止 422/724/713（记忆 "
                           f"wf-dash-parameter-leader-table-trap）")
        if kind == "ability" and row[109] == "422":
            if row[6] != "42":
                raise KitError(f"{label}#{index}: 422 行必须挂前置 42（持有者为队长），"
                               f"否则会与基诺维/泽赫尔的 422 相加")
            if not row[118]:
                raise KitError(f"{label}#{index}: 422 行的 c118 param_id 不能留空"
                               f"（param 0 也要显式写 '0'）")


def _order_problems(rows: list[list[str]]) -> None:
    """两个月牙生产事件都必须先加层，再按同一事件刷新段数，防止落后一拍。"""
    producers = {}
    refreshers = {}
    for index, row in enumerate(rows):
        event = tuple(row[27:32])
        if row[47] == "461" and row[68] == UID_PIERCE:
            raise KitError("ability slot 3 must not produce the retired piercing counter")
        target = (producers if row[47] == "461" and row[68] == UID_CRESCENT
                  else refreshers if row[47] == "629" and row[70] == CAS_PIERCE else None)
        if target is not None:
            if event in target:
                raise KitError(f"ability slot 3 has a duplicate crescent event: {event}")
            target[event] = index
    if len(producers) != 2 or producers.keys() != refreshers.keys():
        raise KitError("ability slot 3 must refresh after both matching crescent production events")
    for event, index in producers.items():
        if index >= refreshers[event]:
            raise KitError("ability slot 3: crescent production must precede its segment refresh")
        row = rows[refreshers[event]]
        if row[6] != "42" or row[13] != "2" or row[18] != ELEMENT_TOKEN:
            raise KitError("ability slot 3 segment refresh must retain leader and thunder resonance gates")
    for index, row in enumerate(rows):
        if row[47] == "629":
            if not row[70] or not row[71]:
                raise KitError(f"ability 3#{index}: 629 行必须同时带字符串键 c70 与程序路径 c71")
            if row[35] == "":
                raise KitError(f"ability 3#{index}: 629 行的 c35 cooltime 不能留空")
            if row[1] != "false":
                raise KitError(f"ability 3#{index}: 629 在副位不生效，该键必须 unisonable=false")


def _cooltime_problems(rows: list[list[str]]) -> None:
    """作者反馈轮 2 的两格冷却：**按内容定位，不按记录号**。

    记录号会漂（1.4.974 响在共享 donor 首位插了一条 413，凯尔写死的 ``1699885#0`` 当场失效），
    所以这里用「这条记录是干什么的」来找：

    - 天雷 = ``c47=629`` 且 ``c70`` 指向 ``CAS_THUNDER`` 的那条 ⇒ c35 必须是 3 秒；
    - 贯通回槽 = ``c47=211`` 且触发 ``c27=51``（获得贯穿）的那条 ⇒ c35 必须是 10 秒。

    两者都要求「恰好一条」：多出一条说明有人复制了行而没同步 CT，少一条说明行被删/改 kind 了。
    """
    thunder = [index for index, row in enumerate(rows)
               if row[47] == "629" and row[70] == CAS_THUNDER]
    gauge = [index for index, row in enumerate(rows)
             if row[47] == "211" and row[27] == "51"]
    for label, hits, want in (("天雷 629", thunder, THUNDER_COOLTIME),
                              ("贯通→技能槽 211", gauge, PIERCE_GAUGE_COOLTIME)):
        if len(hits) != 1:
            raise KitError(f"ability slot 3: 按内容定位「{label}」命中 {len(hits)} 条，应当恰好 1 条"
                           f"（行计划被改动过？CT 断言失去锚点）")
        got = rows[hits[0]][35]
        if got != want:
            raise KitError(f"ability 3#{hits[0]}（{label}）: c35 冷却 {got!r} != {want!r}"
                           f"（{int(want) / 60:g} 秒，作者真机反馈轮 2）")


def resolve_dash_donor(ctx) -> str:
    """把 ``DASH_DONOR`` 哨兵解析成 live store 里真正带 422 的那条记录的地址。"""
    rows = KL._rows(ctx, KL.ABILITY, "store")
    if DASH_DONOR_KEY not in rows:
        raise KitError(f"dash donor {DASH_DONOR_KEY} 不在 live store 的 ability 表里")
    records = ctx.csv_split(rows[DASH_DONOR_KEY])
    hits = [index for index, record in enumerate(records)
            if len(record) > DASH_DONOR_KIND_COL
            and record[DASH_DONOR_KIND_COL] == DASH_DONOR_KIND]
    if not hits:
        kinds = [r[DASH_DONOR_KIND_COL] if len(r) > DASH_DONOR_KIND_COL else "?" for r in records]
        raise KitError(f"dash donor {DASH_DONOR_KEY} 里没有 kind {DASH_DONOR_KIND} 的记录"
                       f"（现有 c{DASH_DONOR_KIND_COL} = {kinds}）")
    return f"{DASH_DONOR_KEY}#{hits[0]}"


def build_rows(ctx) -> dict[str, Any]:
    evidence: list[dict[str, Any]] = []
    caps: set[str] = set()
    dash_donor = resolve_dash_donor(ctx)

    leader_rows: list[list[str]] = []
    for index, (addr, source, cells, expect) in enumerate(LEADER):
        row, ev = KL.build_row(ctx, "leader_ability", addr, cells, source=source,
                               expect_describe=expect or EXPECT.get(f"leader#{index}"),
                               label=f"leader#{index}")
        if row[0] != CODE:
            raise KitError(f"leader#{index}: c0 {row[0]!r} != {CODE}")
        leader_rows.append(row)
        evidence.append(ev)
        caps.update(ev["capabilities"])
    # Native StunWinceSlayer maps to the separate PinchSlayer multiplier when
    # the enemy is Down. Both growth rows share the original piercing trigger.
    for content, strength in PIERCING_GROWTH:
        label = f"leader#{len(leader_rows)}"
        moved, ev = KL.build_row(ctx, "ability", "2110012#0",
            {**_PRE_RESONANCE_A, 34: "(None)", 47: content, 48: "5", 49: ELEMENT_TOKEN,
             51: strength, 52: strength}, element=ELEMENT,
            expect_describe=EXPECT[label])
        moved = ability_to_leader(moved, CODE)
        problems = KL.row_problems("leader_ability", moved, ELEMENT)
        if problems:
            raise KitError(f"piercing growth {content}: {problems}")
        leader_rows.append(moved)
        ev.update(label=label, kind="leader_ability",
                  describe=KL.describe("leader_ability", moved))
        evidence.append(ev)
        caps.update(KL.capabilities("leader_ability", moved))
    pf_row, pf_evidence = PF.leader_row(ctx)
    leader_rows.append(pf_row)
    evidence.append(pf_evidence)
    caps.update(pf_evidence["capabilities"])
    _ban_kinds("leader_ability", leader_rows, "leader")

    ability: dict[str, list[list[str]]] = {}
    for slot in range(1, 7):
        key = f"{CID}{slot}"
        rows: list[list[str]] = []
        for index, (addr, source, cells, expect) in enumerate(PLAN[slot]):
            merged = {0: f"{CODE}_{slot}", 1: _UNISONABLE[slot], 2: _STATUE[slot], **cells}
            label = f"{key}#{index}"
            if addr == DASH_DONOR:
                addr = dash_donor
            row, ev = KL.build_row(ctx, "ability", addr, merged, source=source,
                                   element=ELEMENT,
                                   expect_describe=expect or EXPECT.get(label),
                                   label=label)
            rows.append(row)
            evidence.append(ev)
            caps.update(ev["capabilities"])
        KL.check_ability_key(rows, key, CODE, slot)
        _ban_kinds("ability", rows, key)
        ability[key] = rows
    _order_problems(ability[f"{CID}3"])
    _cooltime_problems(ability[f"{CID}3"])

    missing = sorted(caps - set(ctx.spec.required_capabilities))
    if missing:
        raise KitError(f"rows need client capabilities {missing} that SPEC does not declare")
    return {"leader": leader_rows, "ability": ability, "evidence": evidence,
            "capabilities": sorted(caps)}


# ---------------------------------------------------------------- 固有状态与图标

def build_uniques(ctx) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for n, (key, string_id, name, cap, frames, _style) in enumerate(UNIQUES, start=1):
        built, row = KL.unique_row(ctx, ctx.spec, n, donor=UNIQUE_DONOR,
                                   cells={0: string_id, 2: UNIQUE_ICON_ROW[key],
                                          3: frames, 4: cap},
                                   name=name)
        if built != key:
            raise KitError(f"unique id drift: {built} != {key}")
        if row[13] != "false":
            raise KitError(f"unique_condition {key}: c13 remove_if_encoffin must stay false")
        out[key] = row
    KL.write_unique(ctx, ctx.spec, out)
    return out


def draw_icon(frame, style: str):
    """48×48 图标：深靛圆底 (#1B1A24) ＋ 2px 金环；主体按 ``style`` 画。

    8× 画布绘制后 LANCZOS 缩回 48×48；alpha 取官方图标外框（同批统一工艺，alpha 一格不改）。
    """
    from PIL import Image, ImageDraw
    if frame.size != (48, 48):
        raise KitError(f"icon frame donor must be 48x48, got {frame.size}")
    K, N = 8, 48 * 8
    ink = (27, 26, 36, 255)
    gold = (232, 194, 90, 255)
    chill = (244, 240, 255, 255)

    layer = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    inner = Image.new("L", (N, N), 0)
    ImageDraw.Draw(inner).ellipse((3 * K, 3 * K, 45 * K - 1, 45 * K - 1), fill=255)
    layer.paste(Image.new("RGBA", (N, N), ink), (0, 0), inner)
    ImageDraw.Draw(layer).ellipse((4 * K, 4 * K, 44 * K - 1, 44 * K - 1), outline=gold, width=2 * K)

    body = Image.new("L", (N, N), 0)
    bd = ImageDraw.Draw(body)
    if style == "crescent":
        # 新月 = 大圆减偏移小圆；小圆再被两枚小尖角咬出「狼牙」内缘
        bd.ellipse((12 * K, 10 * K, 36 * K, 34 * K), fill=255)
        bite = Image.new("L", (N, N), 0)
        cut = ImageDraw.Draw(bite)
        cut.ellipse((19 * K, 8 * K, 43 * K, 32 * K), fill=255)
        cut.polygon([(20 * K, 17 * K), (26 * K, 20 * K), (20 * K, 23 * K)], fill=0)
        cut.polygon([(23 * K, 25 * K), (29 * K, 27 * K), (23 * K, 30 * K)], fill=0)
        body = Image.composite(Image.new("L", (N, N), 0), body, bite)
    elif style == "pierce":
        # 贯穿印：一道斜贯的长枪痕 + 两侧破口
        bd.polygon([(12 * K, 33 * K), (17 * K, 33 * K), (36 * K, 13 * K),
                    (31 * K, 13 * K)], fill=255)
        bd.polygon([(33 * K, 11 * K), (38 * K, 11 * K), (38 * K, 16 * K)], fill=255)
        bd.polygon([(10 * K, 30 * K), (10 * K, 35 * K), (15 * K, 35 * K)], fill=255)
    elif style == "awake":
        # 月狼·觉：竖立的狼牙 + 上方一点月芒
        bd.polygon([(24 * K, 9 * K), (31 * K, 26 * K), (24 * K, 38 * K),
                    (17 * K, 26 * K)], fill=255)
        bd.ellipse((21 * K, 6 * K, 27 * K, 12 * K), fill=255)
    else:
        raise KitError(f"unknown icon style {style!r}")
    body = Image.composite(body, Image.new("L", (N, N), 0), inner)
    layer.paste(Image.new("RGBA", (N, N), gold), (0, 0), body)

    spark = Image.new("L", (N, N), 0)
    ImageDraw.Draw(spark).ellipse((32 * K, 32 * K, 38 * K, 38 * K), fill=255)
    layer.paste(Image.new("RGBA", (N, N), chill), (0, 0),
                Image.composite(spark, Image.new("L", (N, N), 0), inner))

    small = layer.resize((48, 48), Image.LANCZOS)
    out = Image.new("RGBA", (48, 48), (255, 255, 255, 0))
    fp, op, sp = frame.load(), out.load(), small.load()
    for y in range(48):
        for x in range(48):
            r, g, b, a = sp[x, y]
            fa = fp[x, y][3]
            if a:
                op[x, y] = (round((r * a + 255 * (255 - a)) / 255),
                            round((g * a + 255 * (255 - a)) / 255),
                            round((b * a + 255 * (255 - a)) / 255), fa)
            else:
                op[x, y] = (255, 255, 255, fa)
    return out


def install_unique_icons(ctx) -> list[dict[str, Any]]:
    frame_raw = ctx.official_read(UNIQUE_ICON_FRAME)
    if frame_raw is None:
        _root, frame_raw, _how = ctx.pack.template_asset(UNIQUE_ICON_FRAME)
    frame = ctx.png_open(frame_raw)
    notes = []
    for key, _sid, name, _cap, _frames, style in UNIQUES:
        logical = UNIQUE_ICON_ROW[key] + ".png"
        data = ctx.png_store_bytes(draw_icon(frame, style))
        ctx.write_asset("common", logical, data)
        back = ctx.png_open(ctx.pack.pkg_path("common", logical).read_bytes())
        if back.size != (48, 48) or back.getchannel("A").tobytes() != frame.getchannel("A").tobytes():
            raise KitError(f"unique icon {key}: size/alpha differ from the official frame donor")
        notes.append({"key": key, "name": name, "logical": logical, "style": style,
                      "frame_donor": UNIQUE_ICON_FRAME,
                      "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
    return notes


# ---------------------------------------------------------------- DSL 工具

def _walk(node):
    yield node
    if isinstance(node, list):
        for child in node:
            yield from _walk(child)
    elif isinstance(node, dict):
        for child in node.values():
            yield from _walk(child)


def _is_command(node, name: str | None = None) -> bool:
    return (isinstance(node, list) and len(node) == 2 and node[0] == "Command"
            and isinstance(node[1], list) and node[1]
            and (name is None or node[1][0] == name))


def _command_counts(tree) -> dict[str, int]:
    counts: dict[str, int] = {}
    for node in _walk(tree):
        if _is_command(node) and isinstance(node[1][0], str):
            counts[node[1][0]] = counts.get(node[1][0], 0) + 1
    return counts


def _bodies(tree, name: str) -> list[list]:
    return [node[1] for node in _walk(tree) if _is_command(node, name)]


def _one(bodies: list[list], name: str) -> list:
    if len(bodies) != 1:
        raise KitError(f"expected exactly one {name}, got {len(bodies)}")
    return bodies[0]


def _cmd(*body) -> list:
    return ["Command", list(body)]


def _block(*children) -> list:
    return ["Block", list(children)]


def effect_paths(tree) -> list[str]:
    return [node[1] for node in _walk(tree)
            if isinstance(node, list) and len(node) == 2
            and node[0] == "SpecifyEffectDirectly" and isinstance(node[1], str)]


def _condition_donor(ctx, program: str, kind: str) -> list:
    """官方树里唯一携带该 AdditionalCondition 的 ``CreateCondition``（整条命令，深拷贝）。"""
    tree = ctx.template_dsl(program)
    hits = [node for node in _walk(tree) if _is_command(node, "CreateCondition")
            and node[1][2] and isinstance(node[1][2][0], list) and node[1][2][0][0] == kind]
    if not hits:
        raise KitError(f"{program}: no CreateCondition/{kind}")
    return copy.deepcopy(hits[0])


def _check_condition_shape(command: list, kind: str, target_kind: int) -> list:
    body = command[1]
    if len(body) != 13:
        raise KitError(f"{kind}: CreateCondition has {len(body) - 1} slots, expected 12")
    if body[2][0][0] != kind:
        raise KitError(f"{kind}: donor carries {body[2][0][0]!r}")
    if body[10] != target_kind:
        # 下标 10 = 付与对象种类；错配 = 施法 C16102（记忆 wf-createcondition-target-kind）
        raise KitError(f"{kind}: CreateCondition target kind {body[10]!r} != {target_kind}")
    return body


def _remap_binds(node, offset: int) -> None:
    """整块绑定号平移（两个互斥分支同树时避免重号；记忆 wf-dsl-subject-lookup-map）。

    声明位与使用位都取 ``wf_client_legality`` 的权威表，别自己抄一份（抄漏 = 悬空主体）。

    使用位必须走 ``L._dsl_lookup_slots``（客户端 ``ActionEvaluator`` 机械提取的**全量**
    lookup 列），不能只用手抄的 ``DSL_SUBJECT_CONSUMERS``：后者漏了
    ``CreateReferencePoint`` node[1]、``ShowEffect`` node[3]、``CreateHitArea`` node[2]，
    2026-09-21 的真机 C16103（强化天雷分支 lookup 母本遗留的 0/1）就是这么漏出去的。
    """
    for cmd in (n[1] for n in _walk(node) if _is_command(n)):
        positions: set[int] = set(L._dsl_lookup_slots(cmd[0]))
        for ids, _block in L.DSL_SUBJECT_BINDERS.get(cmd[0], ()):
            positions.update(ids)
        for index in sorted(positions):
            if index < len(cmd):
                value = cmd[index]
                if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                    cmd[index] = value + offset
        # 坐标系 ["GH", n] 同样走 Environment.lookup（ActionEvaluator.as:1037）
        for slot in cmd[1:]:
            if (isinstance(slot, list) and len(slot) == 2 and slot[0] == "GH"
                    and isinstance(slot[1], int) and not isinstance(slot[1], bool)
                    and slot[1] >= 0):
                slot[1] += offset


# ---------------------------------------------------------------- 主技能树

def _team_block(ctx, level: str) -> list:
    """强化档：``FindAllSubjects(11, 33)`` 一块里挂贯通 / 直击伤害 UP / 加速三条状态。"""
    tree = ctx.template_dsl(PIERCING_DONOR)
    hits = [node for node in _walk(tree) if _is_command(node, "FindAllSubjects")]
    if len(hits) != 1:
        raise KitError(f"{PIERCING_DONOR}: expected exactly 1 FindAllSubjects, got {len(hits)}")
    command = copy.deepcopy(hits[0])
    body = command[1]
    if (body[1], body[2]) != (11, 33):
        raise KitError(f"{PIERCING_DONOR}: FindAllSubjects bind/selector {body[1]}/{body[2]} "
                       f"!= 11/33（33 = 含自身的己方全体）")
    bind = body[1]
    block = body[9]
    if block[0] != "Block" or len(block[1]) != 1:
        raise KitError("FindAllSubjects donor block shape drifted")

    piercing = block[1][0]
    _check_condition_shape(piercing, "ACPiercing", 3)
    piercing[1][2][0][1] = [{"min": BOOST_PIERCING_FRAMES, "max": BOOST_PIERCING_FRAMES}]

    direct = _condition_donor(ctx, DIRECT_DONOR, "ACDirectDamage")
    _check_condition_shape(direct, "ACDirectDamage", 3)
    direct[1][1] = bind
    direct[1][2][0][1] = [{"min": BOOST_DIRECT_FRAMES, "max": BOOST_DIRECT_FRAMES}]
    direct[1][2][0][2] = [{"min": BOOST_DIRECT[level][0], "max": BOOST_DIRECT[level][1]}]

    speedup = _condition_donor(ctx, SPEEDUP_DONOR, "ACSpeedup")
    _check_condition_shape(speedup, "ACSpeedup", 3)
    speedup[1][1] = bind
    speedup[1][2][0][1] = [{"min": BOOST_SPEEDUP_FRAMES, "max": BOOST_SPEEDUP_FRAMES}]
    speedup[1][2][0][2] = [{"min": BOOST_SPEEDUP[level][0], "max": BOOST_SPEEDUP[level][1]}]

    block[1][:] = [piercing, direct, speedup]
    return command


def _enemy_debuff_block(ctx, near_donor: list) -> list:
    """强化档：找最近的敌人 → 驱散 2 个增益 + 施加「冻结」ACFrozen（能力 1 强化条目 CAS_SWITCH_TEXT 的一部分，
    也是能力 6 冻结特攻的状态来源）。"""
    command = copy.deepcopy(near_donor)
    body = command[1]
    if body[0] != "FindNearSubjects" or len(body) != 7:
        raise KitError("FindNearSubjects donor shape drifted")
    # FindNearSubjects 的绑定位是 node[5]（权威表 wf_client_legality.DSL_SUBJECT_BINDERS），
    # node[2] 是搜索个数、node[3] 是选择器（49 = 敌方）。
    if body[3] != 49:
        raise KitError(f"FindNearSubjects donor selector {body[3]} != 49（敌方）")
    body[4] = ["DoNothing"]            # 没有敌人时什么都不做（不造虚拟目标）
    body[5] = ENEMY_BIND
    frozen = _condition_donor(ctx, FROZEN_DONOR, "ACFrozen")
    _check_condition_shape(frozen, "ACFrozen", 3)
    frozen[1][1] = ENEMY_BIND
    frozen[1][2][0][1] = [{"min": FROZEN_FRAMES, "max": FROZEN_FRAMES}]
    dispel = _cmd("DeleteCondition", ENEMY_BIND, ["DCAll", 2], DISPEL_COUNT, 0, "", ["Default"])
    body[6] = _block(dispel, frozen)
    return command


def mutate_tree(ctx, tree, level: str) -> tuple[Any, dict[str, Any]]:
    counts = _command_counts(tree)
    if counts != DONOR_COMMAND_COUNTS:
        raise KitError(f"donor skill tree {level} drifted: commands {counts} != {DONOR_COMMAND_COUNTS}")
    if not (isinstance(tree, list) and len(tree) == 12 and tree[0] == "ActionDsl"):
        raise KitError(f"donor skill tree {level}: unexpected root {tree[:2]!r}")
    if tree[1] != 2 or tree[10] != 0:
        raise KitError(f"donor root header {level}: movementPriority={tree[1]} buffTargetAs={tree[10]}")

    near = _one(_bodies(tree, "FindNearSubjects"), "FindNearSubjects")
    near_donor = ["Command", copy.deepcopy(near)]

    rp = _one(_bodies(tree, "CreateReferencePoint"), "CreateReferencePoint")
    rp[9] = RP_LIFETIME
    rp_block = rp[11]
    if rp_block[0] != "Block":
        raise KitError("CreateReferencePoint does not carry a Block")

    # ---- 冲刺：把母本的 StopBall 换成官方同形的 MoveBall（Z6 一行开关），
    #      并在同一个 Block 里挂上「移动时身后的那个特效」（心角光环族，作者 09-21）。
    show_template = next((node for node in rp_block[1] if _is_command(node, "ShowEffect")), None)
    if show_template is None:
        raise KitError("RP block carries no ShowEffect to clone the trail from")
    trail = copy.deepcopy(show_template)
    trail[1][1] = FX_TRAIL_LABEL
    trail[1][2] = ["SpecifyEffectDirectly", f"{FX_TRAIL_SRC}/{FX_TRAIL_BASE}"]
    trail[1][3] = -18                                   # 球：随移动/冲刺走
    trail[1][4] = ["BacksideOfCharacter"]               # 「身后」
    trail[1][5] = ["SpecifyEffectLifetimeDirectly", FX_TRAIL_FRAMES]
    trail[1][6] = ["AB"]                                # subject 是球不是敌人 ⇒ AB 安全
    trail[1][12] = ["Some", [{"min": FX_TRAIL_SCALE, "max": FX_TRAIL_SCALE}]]

    dash = None
    stop_nodes = [node for node in rp_block[1] if _is_command(node, "StopBall")]
    if len(stop_nodes) != 1:
        raise KitError(f"expected exactly one StopBall in the RP block, got {len(stop_nodes)}")
    index = rp_block[1].index(stop_nodes[0])
    if DASH_REPLACES_STOPBALL:
        rp_block[1][index] = _cmd(*MOVE_BALL)
        dash = {"replaced": "StopBall", "with": copy.deepcopy(MOVE_BALL),
                "donor": "dog_slasher_proud_2"}
    # 追加在块尾：ShowEffect 的树序仍是 slash/smash/explosion 在前，
    # 下面按下标 0/1/2 改名与改参的逻辑不受影响（同一个 Block 内命令同帧执行）。
    rp_block[1].append(trail)

    events = [node for node in rp_block[1] if isinstance(node, list) and node[0] == "Event"]
    if len(events) != 2 or [event[1][1] for event in events] != [9, 49]:
        raise KitError(f"donor event waits drifted: {[e[1][1] for e in events]} != [9, 49]")

    show_effects = _bodies(tree, "ShowEffect")
    hit_areas = _bodies(tree, "CreateHitArea")
    normal_attacks = _bodies(tree, "CreateNormalAttack")
    for index in (0, 1, 2):
        show_effects[index][1] = EFFECT_NAMES[index]
    for index, edit in HITAREA_EDITS.items():
        _set_hitarea(hit_areas[index], label=f"skill{level} hitarea{index}", **edit)
    for index in (0, 1):
        _set_cna(normal_attacks[index], CNA_SHAPE[index], CNA_MULT[level][index],
                 f"skill{level} cna{index}")

    # ---- 第三段「月華終斬」：同树内克隆第 49 帧那块（签名零漂移），只改参数
    finish = copy.deepcopy(events[1])
    finish[1][1] = FINISH_WAIT
    finish_effect = _one(_bodies(finish, "ShowEffect"), "ShowEffect in the cloned block")
    finish_effect[1] = EFFECT_NAMES[3]
    if finish_effect[2][0] != "SpecifyEffectDirectly":
        raise KitError("cloned ShowEffect does not use SpecifyEffectDirectly")
    finish_effect[2][1] = FINISH_EFFECT
    finish_effect[6] = list(FINISH_EFFECT_ANCHOR)
    finish_effect[12] = copy.deepcopy(FINISH_EFFECT_SCALE)
    _set_hitarea(_one(_bodies(finish, "CreateHitArea"), "CreateHitArea in the cloned block"),
                 binds=FINISH_BINDS, label=f"skill{level} finish", **FINISH_HITAREA)
    _one(_bodies(finish, "ShakeCamera"), "ShakeCamera in the cloned block")[1] = 2
    _set_cna(_one(_bodies(finish, "CreateNormalAttack"), "CreateNormalAttack in the cloned block"),
             CNA_SHAPE[2], CNA_MULT[level][2], f"skill{level} cna2")
    rp_block[1].append(finish)

    # ---- 顶层：删掉母本的 PF 伤害块 → 强化状态固有 + 共鸣分档
    top = tree[11]
    if top[0] != "Block" or len(top[1]) != 2:
        raise KitError(f"donor top-level block has {len(top[1])} commands, expected 2")
    if not _is_command(top[1][1], "FindAllSubjects"):
        raise KitError("donor top-level command #2 is not FindAllSubjects")
    removed = top[1][1][1][2]

    awake = _condition_donor(ctx, ADDITIONAL_DONOR, "ACAdditionalDirectAttack")
    _check_condition_shape(awake, "ACAdditionalDirectAttack", 3)
    awake[1][2] = [["ACUnique", int(UID_AWAKE), [{"min": 1, "max": 1}]]]
    awake[1][1] = -17
    awake[1][7] = "月狼覚醒"

    boost = _block(_team_block(ctx, level), _enemy_debuff_block(ctx, near_donor))
    top[1][1] = awake
    top[1].append(_cmd("ConditionalsChangeSkillFlag", 1, boost, _block()))

    evidence = {
        "level": level,
        "dash": dash,
        "reference_point_lifetime": rp[9],
        "hit_areas": [{"radius": area[9][1][0]["min"], "lifetime": area[13][1],
                       "max_hits": area[14][1], "buff_target_as": area[24],
                       "binds": [area[19], area[21], area[22]]}
                      for area in _bodies(tree, "CreateHitArea")],
        "multipliers": [copy.deepcopy(body[6]) for body in _bodies(tree, "CreateNormalAttack")],
        "removed_power_flip_selector": removed,
        "awake_unique": UID_AWAKE,
        "boost": {"piercing_frames": BOOST_PIERCING_FRAMES,
                  "speedup_frames": BOOST_SPEEDUP_FRAMES,
                  "frozen_frames": FROZEN_FRAMES, "dispel": DISPEL_COUNT},
    }
    return tree, evidence


def _set_hitarea(body: list, *, radius: int, lifetime: int, max_hits: int,
                 break_weak_point: bool | None = None, binds: tuple[int, int, int] | None = None,
                 buff_target_as: int = BUFF_TARGET_AS_DIRECT, label: str = "") -> None:
    """``CreateHitArea``：[9] 形状 / [13] 寿命 / [14] 命中数 / [24] 归属（+ 可选破弱点、绑定号）。"""
    if len(body) != 27:
        raise KitError(f"{label}: CreateHitArea has {len(body) - 1} params, expected 26")
    if body[9][0] != "Circle":
        raise KitError(f"{label}: hit area shape {body[9][0]!r} is not Circle")
    if body[13][0] != "SpecifyHitAreaLifetimeDirectly" or body[14][0] != "CalculatedUsingMaxNumOfHits":
        raise KitError(f"{label}: unexpected lifetime/hits constructors {body[13][0]!r} {body[14][0]!r}")
    body[9] = ["Circle", [{"min": radius, "max": radius}]]
    body[13] = ["SpecifyHitAreaLifetimeDirectly", lifetime]
    body[14] = ["CalculatedUsingMaxNumOfHits", max_hits]
    body[24] = buff_target_as
    if break_weak_point is not None:
        body[7] = bool(break_weak_point)
    if binds is not None:
        body[19], body[21], body[22] = binds


def _set_cna(body: list, shape: dict[str, Any], mult: dict[str, float], label: str,
             combo_bonus: bool | None = None) -> None:
    if len(body) != 17:
        raise KitError(f"{label}: CreateNormalAttack has {len(body) - 1} params, expected 16")
    if body[2] != 255:
        # 255 = 随自身属性。显式元素码只有 CreateNormalAttack[2] 有 +1 偏移
        # （记忆 wf-dsl-element-code-offset），写死反而会错，这一格不动。
        raise KitError(f"{label}: CreateNormalAttack element slot {body[2]!r} != 255")
    body[1] = shape["subject"]
    body[5] = shape["base"]
    body[6] = [dict(mult)]
    body[13] = [{"min": shape["p12"], "max": shape["p12"]}]
    body[14] = [{"min": shape["p13"], "max": shape["p13"]}]
    if combo_bonus is not None:
        body[8] = bool(combo_bonus)


# ---------------------------------------------------------------- 629 追击树

def _ability_skill_root(donor_tree, body_block: list) -> list:
    """用官方主树的根头部造一棵 ability_skill 树（629 以 AbilitySkill 执行）。"""
    root = copy.deepcopy(donor_tree[:11])
    if root[0] != "ActionDsl" or root[10] != 0:
        raise KitError(f"ability_skill root header drift: {root[:2]} buffTargetAs={root[10]}")
    return list(root) + [body_block]


def build_pierce_tree(ctx, donor_tree) -> tuple[Any, dict[str, Any]]:
    """段数成长：月牙层数 → ``ACAdditionalDirectAttack`` 段数（1 + 层数，可超 3）。

    三条硬纪律（卡 B §1.2 B 路）：① 绑定与使用必须在同一个 Block；
    ② 带 ``vlv`` 的 ``CreateCondition`` 必须有非空区分键；③ 段数在付与那一刻定格。
    """
    condition = _condition_donor(ctx, ADDITIONAL_DONOR, "ACAdditionalDirectAttack")
    body = _check_condition_shape(condition, "ACAdditionalDirectAttack", 3)
    ac = body[2][0]
    if len(ac) != 5:
        raise KitError(f"ACAdditionalDirectAttack donor has {len(ac) - 1} params, expected 4")
    ac[1] = [{"min": PIERCE_FRAMES, "max": PIERCE_FRAMES}]
    ac[2] = [{"min": PIERCE_BASE_TIMES, "max": PIERCE_BASE_TIMES,
              "vlv": [{"vid": PIERCE_VAR_ID, "min": 0, "max": PIERCE_TIMES_PER_LAYER}]}]
    ac[3] = [{"min": PIERCE_DAMAGE, "max": PIERCE_DAMAGE}]
    ac[4] = [{"min": 1, "max": 1}]
    body[1] = -17
    body[7] = PIERCE_CONDITION_KEY
    bind = _cmd("BindConditionAccumulationVariable", -17, PIERCE_VAR_ID,
                ["DCUnique", int(UID_CRESCENT)], 1, PIERCE_VAR_CEIL)
    tree = _ability_skill_root(donor_tree, _block(bind, condition))
    return tree, {"unique": UID_CRESCENT, "var": PIERCE_VAR_ID, "ceiling": PIERCE_VAR_CEIL,
                  "base_times": PIERCE_BASE_TIMES, "per_layer": PIERCE_TIMES_PER_LAYER,
                  "damage": PIERCE_DAMAGE, "key": PIERCE_CONDITION_KEY}


def _thunder_branch(ctx, program: str, mult: dict[str, float], *, direct: bool,
                    detoughness: float, offset: int = 0) -> tuple[list, dict[str, Any]]:
    """从官方天雷树里取 ``FindNearSubjects`` 整块（含特效 / 判定区 / 伤害），只改参数。"""
    tree = ctx.template_dsl(program)
    hits = [node for node in _walk(tree) if _is_command(node, "FindNearSubjects")]
    if len(hits) != 1:
        raise KitError(f"{program}: expected exactly 1 FindNearSubjects, got {len(hits)}")
    command = copy.deepcopy(hits[0])
    areas = _bodies(command, "CreateHitArea")
    attacks = _bodies(command, "CreateNormalAttack")
    if len(areas) != 1 or len(attacks) != 1:
        raise KitError(f"{program}: expected 1 CreateHitArea + 1 CreateNormalAttack, "
                       f"got {len(areas)}/{len(attacks)}")
    if direct:
        # 能力 1「技能雷击按直接攻击伤害结算，且威力随连击数大幅提升」= 两件事各写一处
        areas[0][24] = BUFF_TARGET_AS_DIRECT
        attacks[0][8] = True
    attacks[0][6] = [dict(mult)]
    donor_detoughness = copy.deepcopy(attacks[0][13])
    attacks[0][13] = [{"min": detoughness, "max": detoughness}]
    if offset:
        _remap_binds(command, offset)
    note = {"donor": program, "multiplier": dict(mult), "direct": direct,
            "detoughness": {"donor": donor_detoughness, "value": detoughness},
            "effects": effect_paths(command)}
    return command, note


def build_thunder_tree(ctx, donor_tree, bolt_family) -> tuple[Any, dict[str, Any]]:
    """天雷两档：常态 = 官方千岳（零克隆零染色）；强化 = 本包克隆的雷弓（冷蓝白）。"""
    normal, normal_note = _thunder_branch(ctx, THUNDER_NORMAL_DONOR, THUNDER_MULT_NORMAL,
                                          direct=False, detoughness=THUNDER_DETOUGHNESS_NORMAL)
    boost, boost_note = _thunder_branch(ctx, THUNDER_BOOST_DONOR, THUNDER_MULT_BOOST,
                                        direct=True, detoughness=THUNDER_DETOUGHNESS_BOOST,
                                        offset=THUNDER_BOOST_BIND_OFFSET)
    boost, rewrite = ctx.rewrite_effect_refs(boost, bolt_family)
    boost_note["effects"] = effect_paths(boost)
    boost_note["rewrite"] = rewrite
    body = _block(_cmd("ConditionalsChangeSkillFlag", 1, _block(boost), _block(normal)))
    tree = _ability_skill_root(donor_tree, body)
    leaked = [path for path in effect_paths(tree)
              if path.startswith(f"battle/effect/skill_unique/{FX_BOLT_TEMPLATE}/")]
    if leaked:
        raise KitError(f"thunder tree still references the un-cloned donor family: {leaked}")
    return tree, {"normal": normal_note, "boost": boost_note}


# ---------------------------------------------------------------- DSL 落盘

def _dsl_problems(tree) -> list[str]:
    problems = [f"direction: {p}" for p in wf_dsl.player_side_dsl_problems(tree)]
    problems += [f"coord: {p}" for p in wf_dsl.coord_sys_source_problems(tree)]
    problems += [f"subject: {p}" for p in L.action_dsl_subject_binding_problems(tree)]
    # 全量 lookup 作用域（C16103）：上面那条只看手抄子集，会漏 CRP/ShowEffect/CHA 的引用位
    problems += [f"lookup_scope: {p}" for p in L.action_dsl_lookup_scope_problems(tree)]
    problems += [f"hit_target: {p}" for p in L.action_dsl_hit_area_target_problems(tree)]
    problems += [f"element: {p}" for p in L.action_dsl_element_problems(tree, ELEMENT)]
    return problems


def _write_tree(ctx, program: str, tree, label: str) -> str:
    problems = _dsl_problems(tree)
    if problems:
        raise KitError(f"{label}: DSL problems {problems}")
    if not (isinstance(tree, list) and tree and tree[0] == "ActionDsl"):
        raise KitError(f"{label}: write_dsl needs a bare ActionDsl tree")
    logical = ctx.write_dsl(program, tree)
    back = ctx.amf_parse(ctx.pack.pkg_path("common", logical).read_bytes())
    if back != tree:
        raise KitError(f"{label}: package DSL read-back differs from the written tree")
    return logical


def write_skills(ctx, blade_family, bolt_family, trail_family) -> tuple[list[str], list[dict[str, Any]]]:
    programs, evidence = [], []
    donor_tree = None
    for level in ("1", "2"):
        donor_program = ctx.program_path(level).replace(CODE, TEMPLATE_CODE)
        raw = ctx.template_dsl(donor_program)
        if donor_tree is None:
            donor_tree = copy.deepcopy(raw)
        tree, ev = mutate_tree(ctx, raw, level)
        tree, rewrite = ctx.rewrite_effect_refs(tree, blade_family)
        tree, trail_rewrite = ctx.rewrite_effect_refs(tree, trail_family)
        paths = sorted(effect_paths(tree))
        expected = sorted([f"{FX_BLADE_DST}/{TEMPLATE_CODE}_slash",
                           f"{FX_BLADE_DST}/{TEMPLATE_CODE}_smash",
                           f"{FX_BLADE_DST}/{TEMPLATE_CODE}_explosion",
                           FX_TRAIL_EFFECT, FINISH_EFFECT])
        if paths != expected:
            raise KitError(f"skill {level} effect refs {paths} != {expected}")
        ev.update({"logical": _write_tree(ctx, ctx.program_path(level), tree, f"skill {level}"),
                   "donor_program": donor_program, "effect_refs": paths,
                   "effect_rewrite": rewrite, "trail_rewrite": trail_rewrite})
        evidence.append(ev)
        programs.append(ctx.program_path(level))

    pierce, pierce_note = build_pierce_tree(ctx, donor_tree)
    pierce_note["logical"] = _write_tree(ctx, PIERCE_PROGRAM, pierce, "pierce")
    pierce_note["program"] = PIERCE_PROGRAM
    evidence.append({"level": "pierce", **pierce_note})
    programs.append(PIERCE_PROGRAM)

    thunder, thunder_note = build_thunder_tree(ctx, donor_tree, bolt_family)
    thunder_note["logical"] = _write_tree(ctx, THUNDER_PROGRAM, thunder, "thunder")
    thunder_note["program"] = THUNDER_PROGRAM
    evidence.append({"level": "thunder", **thunder_note})
    programs.append(THUNDER_PROGRAM)
    return programs, evidence


# ---------------------------------------------------------------- 特效族

def fx_dir(ctx) -> Path:
    return ctx.pack.batch_dir / "rework1" / "fx" / KEY


def fx_lut_path(ctx, name: str) -> Path | None:
    """LUT 查找顺序：``rework1/fx/kyle/<name>`` → ``B/pixel/kyle/<name>``；都没有返回 None。

    ⚠ ``rework1/fx/kyle/fx_lut.json`` 是特效代理的**清单**（``ma-fx-lut-manifest/1``），
    不是 LUT；按族取 ``fx_lut.<母本>.json``，别把清单喂给 ``png_transform_from_lut``。
    """
    for candidate in (fx_dir(ctx) / name, KL.pixel_dir(ctx) / name):
        if candidate.is_file():
            return candidate
    return None


def _staged_lut(ctx, name: str, why: str) -> tuple[Any, dict[str, Any]]:
    """代理交付的族 LUT：在就套用，不在就先不染色（kit 无需改代码）。"""
    staged = fx_lut_path(ctx, name)
    if staged is None:
        return None, {"source": "none", "expected": name, "why": why}
    data = KL.load_lut(staged) or {}
    return KL.png_transform_from_lut(staged), {
        "source": "staged", "path": str(staged), "mode": data.get("mode"),
        "exact_entries": len(data.get("exact") or {}), "hue_rules": len(data.get("hue") or [])}


def _blade_transform(ctx, design: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    staged = KL.pixel_dir(ctx) / "fx_lut.json"
    if staged.is_file():
        fallback = ctx.pack.evidence_path("kit-fx-lut.json")
        if fallback.is_file():
            fallback.unlink()
        data = KL.load_lut(staged) or {}
        return KL.png_transform_from_lut(staged), {
            "source": "staged", "path": str(staged), "mode": data.get("mode"),
            "exact_entries": len(data.get("exact") or {}), "hue_rules": len(data.get("hue") or [])}
    clone = ((design.get("plan") or {}).get("skills") or {}).get("effects_clone") or []
    lut = dict(((clone[0] if clone else {}).get("recolor") or {}).get("lut") or {})
    if not lut:
        return None, {"source": "none", "why": "设计稿没有内联色表且代理未交付 ⇒ 先不改色"}
    payload = {"schema": KL.LUT_SCHEMA, "mode": "both", "tolerance": 0,
               "_source": "design/kyle.json plan.skills.effects_clone[0].recolor.lut",
               "exact": {f"#{src}": f"#{dst}" for src, dst in lut.items()},
               "hue": FX_HUE_FALLBACK}
    path = ctx.pack.evidence_path("kit-fx-lut.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return KL.png_transform_from_lut(path), {"source": "design", "path": str(path),
                                             "entries": len(lut)}


def _assert_fx_donor(ctx, src_dir: str, template: str, fingerprint: dict) -> dict[str, Any]:
    """母本漂移即拒绝：sheet 尺寸对不上就说明调研卡与代理的配方全部失效，当场停工。"""
    raw = ctx.official_read(f"{src_dir}/{template}.png")
    if raw is None:
        raise KitError(f"official baseline lacks {src_dir}/{template}.png")
    size = ctx.png_open(raw).size
    if tuple(size) != fingerprint["sheet"]:
        raise KitError(f"{template} sheet {size} != {fingerprint['sheet']} "
                       f"（母本漂移，调研卡 C 与 rework1/fx/{KEY} 的配方失效，拒绝施工）")
    return {"sheet": list(size)}


def clone_effects(ctx, design: dict[str, Any]) -> tuple[Any, Any, Any, dict[str, Any]]:
    blade_transform, blade_lut = _blade_transform(ctx, design)
    blade = ctx.clone_effect_family(FX_BLADE_SRC, FX_BLADE_SUB, layout="codename",
                                    png_transform=blade_transform)
    if blade.get("missing_effects"):
        raise KitError(f"blade family clone is missing {blade['missing_effects']}")

    bolt_fp = _assert_fx_donor(ctx, FX_BOLT_SRC, FX_BOLT_TEMPLATE, FX_BOLT_FINGERPRINT)
    bolt_transform, bolt_lut = _staged_lut(
        ctx, FX_BOLT_LUT, "特效代理未交付冷蓝白色表 ⇒ 先按原色克隆（到位后自动生效）")
    bolt = ctx.clone_effect_family(FX_BOLT_SRC, FX_BOLT_SUB, layout="codename",
                                   png_transform=bolt_transform)
    if bolt.get("missing_effects"):
        raise KitError(f"bolt family clone is missing {bolt['missing_effects']}")

    trail_fp = _assert_fx_donor(ctx, FX_TRAIL_SRC, FX_TRAIL_TEMPLATE, FX_TRAIL_FINGERPRINT)
    trail_transform, trail_lut = _staged_lut(
        ctx, FX_TRAIL_LUT, "特效代理未交付雷金色表 ⇒ 先按原色克隆（到位后自动生效）")
    trail = ctx.clone_effect_family(FX_TRAIL_SRC, FX_TRAIL_SUB, layout="codename",
                                    fx_names=[FX_TRAIL_BASE], png_transform=trail_transform)
    if trail.get("missing_effects"):
        raise KitError(f"trail family clone is missing {trail['missing_effects']}")
    if FX_TRAIL_BASE not in trail["copied_bases"]:
        raise KitError(f"trail clone did not copy {FX_TRAIL_BASE}: {trail['copied_bases']}")

    surgery = _apply_parts_surgery(ctx, {"blade": blade, "bolt": bolt, "trail": trail})
    note = {
        "blade": {"src": FX_BLADE_SRC, "dst": blade["dst_dir"],
                  "bases": sorted(blade["copied_bases"]), "lut": blade_lut},
        "bolt": {"src": FX_BOLT_SRC, "dst": bolt["dst_dir"],
                 "bases": sorted(bolt["copied_bases"]), "lut": bolt_lut,
                 "donor_fingerprint": bolt_fp},
        "trail": {"src": FX_TRAIL_SRC, "dst": trail["dst_dir"],
                  "bases": sorted(trail["copied_bases"]), "lut": trail_lut,
                  "donor_fingerprint": trail_fp,
                  "attached_to": "技能冲刺块（MoveBall 同一个 Block，subject -18 / "
                                 "BacksideOfCharacter / AB）"},
        "normal_thunder": {"path": THUNDER_NORMAL_DONOR, "cloned": False,
                           "why": "作者 09-21 同意常态档直接引用官方千岳十织、不染色；"
                                  "全克隆它会让单角色 layer0 到 3.44% 且 fits=False（卡 C §3.4）"},
        "parts_surgery": surgery,
    }
    return blade, bolt, trail, note


def _apply_parts_surgery(ctx, families: dict[str, Any]) -> dict[str, Any]:
    """特效代理的 parts 手术（只取末段 / 拆档）钩子：脚本在就跑，不在就跳过。"""
    script = ctx.pack.batch_dir / "rework1" / "fx" / KEY / "parts_surgery.py"
    if not script.is_file():
        return {"applied": False, "script": str(script),
                "why": "特效素材代理尚未交付 parts 手术脚本 ⇒ 按整族克隆"}
    import importlib.util
    spec = importlib.util.spec_from_file_location(f"ma_fx_surgery_{KEY}", script)
    if spec is None or spec.loader is None:
        raise KitError(f"cannot load the parts surgery script {script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    apply = getattr(module, "apply", None)
    if apply is None:
        raise KitError(f"{script} must expose apply(ctx, families)")
    return {"applied": True, "script": str(script), "result": apply(ctx, families)}


# ---------------------------------------------------------------- 表与文案

def check_texts(ctx, design: dict[str, Any]) -> dict[str, str]:
    texts = design["texts"]
    missing = [name for name in MS.TEXT_FIELDS if not texts.get(name)]
    if missing:
        raise KitError(f"design texts lack {missing}")
    drift = {name: (ctx.spec.texts.get(name), texts[name]) for name in MS.TEXT_FIELDS
             if ctx.spec.texts.get(name) != texts[name]}
    if drift:
        raise KitError(f"spec texts differ from design/kyle.json: {sorted(drift)}")
    for name in ("title", "profile", "leader", "skill1", "desc1", "skill2", "desc2"):
        KL.check_panel(texts[name], label=f"texts.{name}")
    return texts


def write_character_row(ctx, texts: dict[str, str]) -> list[str]:
    row = list(ctx.pack.pkg_character_row())
    expect = {0: CODE, 2: "5", 3: str(ELEMENT), 6: str(ctx.spec.pf_type), 8: CODE,
              17: CID_S, 26: ctx.spec.stance, 27: CID_S}
    for index, key in enumerate(ABILITY_KEYS):
        expect[19 + index] = key
    drift = {col: (row[col], value) for col, value in expect.items() if row[col] != value}
    if drift:
        raise KitError(f"package character row differs from spec (rerun tables): {drift}")
    route = KL.voice_route(CODE, VOICE_ROUTE)
    row[9:17] = route
    row[18] = texts["leader"]
    ctx.write_flat(KL.CHARACTER, {CID_S: [row]})
    return route


def write_action_skill(ctx, design: dict[str, Any], texts: dict[str, str]) -> dict[str, list[str]]:
    energy = design["plan"]["skills"]["energy"]
    inner = ctx.pkg_nested(CODE, KL.ACTION)
    if sorted(inner) != ["1", "2"]:
        raise KitError(f"package action_skill inner keys {sorted(inner)} != ['1', '2']")
    out: dict[str, list[str]] = {}
    for level, cells in sorted(inner.items()):
        cells = list(cells)
        if len(cells) != 24:
            raise KitError(f"action_skill {level}: {len(cells)} columns, expected 24")
        if cells[7] != ctx.program_path(level):
            raise KitError(f"action_skill {level}: program {cells[7]!r} != {ctx.program_path(level)!r}")
        if cells[2:4] != ["dynamic/skill/atk_nearest", "true"]:
            raise KitError(f"action_skill {level}: targeting columns changed {cells[2:4]}")
        cells[0] = texts[f"skill{level}"]
        cells[1] = texts[f"desc{level}"]
        cells[4] = str(energy[level]["c4"])
        cells[5] = str(energy[level]["c5"])
        cells[6] = str(energy[level]["c6"])
        out[level] = cells
    ctx.write_nested(KL.ACTION, CODE, {level: [cells] for level, cells in out.items()},
                     replace_inner=True)
    return out


def write_strings(ctx) -> dict[str, str]:
    """``custom_ability_string``：536 / 两条 629 的条目 + 队长与 6 条能力的面板接管。"""
    declared = set(ctx.spec.extra_keys.get(KL.CAS, ()))
    missing = [key for key in CAS_TEXTS if key not in declared]
    if missing:
        raise KitError(f"custom_ability_string keys not declared in SPEC['extra_keys']: {missing}")
    official = ctx.official_flat(KL.CAS)
    clashes = [key for key in CAS_TEXTS if key in official]
    if clashes:
        raise KitError(f"custom_ability_string keys already exist officially: {clashes}")
    for key, text in CAS_TEXTS.items():
        for line in text.split("\n"):
            KL.check_panel(line.replace(MAIN_ICON, ""), skill_flag=(key == CAS_SWITCH), label=key)
    for slot in range(1, 7):
        rendered = CAS_TEXTS[CAS_ABILITY[slot]].split("\n")
        wants_icon = _UNISONABLE[slot] == "false"
        if any(line.startswith(MAIN_ICON) != wants_icon for line in rendered) or "Ⓜ" in "".join(rendered):
            raise KitError(f"slot {slot} desc_override main-position icon does not match c1")
    ctx.write_flat(KL.CAS, {key: [[text]] for key, text in CAS_TEXTS.items()})
    return dict(CAS_TEXTS)


# ---------------------------------------------------------------- build

def build(ctx) -> dict[str, Any]:
    spec = ctx.spec
    if (spec.key, str(spec.cid), spec.code, spec.element) != (KEY, CID_S, CODE, ELEMENT):
        raise KitError(f"spec identity mismatch: {spec.key}/{spec.cid}/{spec.code}/{spec.element}")
    if (spec.template_id, spec.template_code, spec.rarity) != (TEMPLATE_ID, TEMPLATE_CODE, 5):
        raise KitError(f"spec template/rarity mismatch: {spec.template_id}/"
                       f"{spec.template_code}/{spec.rarity}")
    if spec.pf_type != 0:
        raise KitError(f"spec pf_type {spec.pf_type} != 0（剑型 PF 三档由原生 722 替换）")

    design = load_design(ctx.root)
    design_problems = _design_problems(design)
    texts = check_texts(ctx, design)

    # ---- 1) character 行：语音路由 c9–c16 ＋ 队长技名 c18
    route = write_character_row(ctx, texts)

    # ---- 2) 三个固有状态 + 三张 48×48 图标
    uniques = build_uniques(ctx)
    icons = install_unique_icons(ctx)

    # ---- 3) 队长与六个能力槽；行数由当前方案生成
    built = build_rows(ctx)
    ctx.write_flat(KL.LEADER, {CID_S: built["leader"]})
    ctx.write_flat(KL.ABILITY, built["ability"])
    strings = write_strings(ctx)

    # ---- 4) action_skill：名称 / 说明 / 能量
    action = write_action_skill(ctx, design, texts)

    # ---- 5) 特效族（blade 保留 + bolt 新增）与 4 棵 DSL
    blade, bolt, trail, fx_note = clone_effects(ctx, design)
    programs, skill_evidence = write_skills(ctx, blade, bolt, trail)
    pf_report = PF.install(ctx)
    programs.extend(pf_report["programs"])
    fx_note["power_flip"] = pf_report

    # ---- 6) 语音路由目标 + 像素交付件（本轮小人一格不改）
    switched = KL.write_voice_ready(ctx)
    pixel = KL.install_staged_assets(ctx)

    ctx.sync_character_mirrors()

    ctx.evidence_write("kit-rows.json", {
        "leader": built["evidence"][:len(built["leader"])],
        "ability": built["evidence"][len(built["leader"]):],
        "unique_condition": uniques, "icons": icons,
        "custom_ability_string": strings,
    })
    ctx.evidence_write("kit-skills.json", {
        "programs": programs, "action_skill": action, "effects": fx_note,
        "levels": skill_evidence,
    })

    panel = [PANEL_LEADER] + [PANEL_ABILITY[slot] for slot in range(1, 7)]
    for text in panel:
        for line in text.split("\n"):
            KL.check_panel(line.replace(MAIN_ICON, ""), label="panel row")

    notes: list[Any] = [
        {"design_json": str(MS.design_path(ctx.root, KEY)), "stage": design.get("stage"),
         "rows_checked": len(built["evidence"]),
         "how": "每行 donor + 逐格改，过 wf_client_legality 三件套并 wf_describe 回读；"
                "面板文案由 desc_override_* 整块接管，逐行对齐 rework1/panel/kyle.json"},
        {"design_mirror_problems": design_problems,
         "why": "design/kyle.json plan.rework1 是 PLAN/LEADER/UNIQUES 的镜像；非空即两边漂移"},
        {"voice_route": route, "switched_action_skill": switched},
        {"unique_conditions": {key: {"name": row[1], "cap": row[4], "frames": row[3]}
                               for key, row in uniques.items()},
         "why": "上限写 99（「不设置上限」的官方写法）；(None) 会被读成上限 1，"
                "during 134 与 vlv 成长会全死"},
        {"unique_icons": icons},
        {"effects": fx_note},
        {"pixel_install": pixel},
        {"capabilities": built["capabilities"],
         "why": "本轮新增 422 冲刺参数与面板文案接管 ⇒ 不再是零 APK 补丁 kind"},
        {"panel": panel},
    ]

    deviations = [
        {"want": "队长技第 1/3 条写进 leader_ability 表",
         "got": "落在 ability 槽 5（422×3 + 冲刺付与贯通）与槽 3（461 + 629），"
                "各挂前置 42（持有者为队长）；文案由 desc_override_kyle_moon 在队长块接管",
         "why": "422 进队长表 = 角色页 C7050（LeaderAbilityValues.parseAt107 没打补丁）；"
                "触发 51 在队长表零官方先例，杰拉德 v3 手册第 23 条：零先例 kind 必崩"},
        {"want": "「除自身外雷属性角色 +N%」单独一行（during 134 × target 1）",
         "got": "拆成「t5 全队(雷) 低值 + t0 自身补差」，自身与他人的合计数值与面板逐字一致",
         "why": "during 134 × target 1 官方与 live 双零先例（本轮实扫 0 行），不开这个首例"},
        {"want": "能力 4「赋予全队直击 +100%、攻击 +100%」常驻",
         "got": "15 秒状态型（c57/c58=90000000），面板已补写「持续 15 秒」并标 dev:true",
         "why": "by_each_trigger_puller（c72=true）的官方先例全是状态型；"
                "常驻 + by_each 零先例且会无限叠加"},
        {"want": "技能「向最近的敌人冲刺」",
         "got": f"MoveBall 逐格抄官方 dog_slasher_proud_2，替换母本 StopBall"
                f"（开关 DASH_REPLACES_STOPBALL={DASH_REPLACES_STOPBALL}）",
         "why": "引擎没有「冲刺」语义命令；MoveBall 无权威参数卡，只能整组抄官方同形树"},
        {"want": "两档天雷都做 API 染色",
         "got": "常态档直接引用官方千岳十织、不染色（作者 09-21 已同意）",
         "why": "全克隆千岳会让单角色 layer0 到 3.44% 且 fits=False（卡 C §3.4 出路 1）"},
        {"want": "强化档天雷按调研卡 C §3.3 的冷蓝白 LUT 染色",
         "got": fx_note["bolt"]["lut"].get("source"),
         "why": "特效素材代理的 rework1/fx/kyle/fx_lut_bolt.json 到位后自动生效，kit 无需改代码"},
        {"want": "技能「每 10 次直击召唤天雷」不带主位限制",
         "got": "落在 Ⓜ 的能力 3 槽",
         "why": "629 在副位不生效，只能进 unisonable=false 的键"},
        {"want": "不新增面板之外的状态",
         "got": "段数成长复用「月牙」；旧「贯穿印」资源仅保留兼容，不再生产；强化状态使用「月狼·觉」",
         "why": "段数成长按作者 09-23 要求绑定月牙（vlv 读取 DCUnique）；"
                "强化状态需要可当前置的门（前置只认 187 ConditionUnique）"},
    ]

    gate = {"rows": len(built["evidence"]), "programs": len(programs),
            "unique_conditions": sorted(uniques), "pixel_present": pixel.get("present"),
            "design_mirror_ok": not design_problems,
            "bolt_lut": fx_note["bolt"]["lut"].get("source")}
    status = KL.READY if not design_problems else KL.DRAFT

    return KL.report(
        ctx,
        summary="凯尔（139990）：雷 · 冲刺型直击主C —— 队长位 422 冲刺强化 ＋ 月牙层数驱动的"
                "可成长直击段数 ＋ 月牙层数换攻击力/直击；技能冲刺斩后进入 15 秒强化状态，"
                "每 10 次直击召唤天雷（常态千岳／强化雷弓两档）",
        status=status,
        panel=panel,
        notes=notes,
        programs=programs,
        unique_condition={key: {"name": row[1], "cap": row[4]} for key, row in uniques.items()},
        required_capabilities=tuple(built["capabilities"]),
        deviations=deviations,
        extra={"skills": {"programs": programs, "effects": fx_note}, "gate": gate},
    )
