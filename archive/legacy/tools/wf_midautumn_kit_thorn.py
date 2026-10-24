# -*- coding: utf-8 -*-
"""中秋批次 kit：索恩 159994 ``tweyen_light``（光属性技伤辅助·打异常状态，原创）。

定位「二王弓」：一次施技给单体敌人挂满 **5 个弱体**（麻痹 1 ＋ 迟缓 1 ＋ 累积全属性抗性↓
3 层），再由队长技与词条把「敌方弱体数」换算成全队光属性的攻击力与技能伤害，并叠
麻痹 / 气绝 / 迟缓三条独立乘区特攻。零固有状态、零 629 / 722 / 422 / 724。设计与数值以
``work/character_packs/midautumn-20260920/design/thorn.{md,json}`` 为准。

**rework1（2026-09-21，作者 09-20 23:2x 原话 + 09-21「开做」）**：目标面板＝
``rework1/panel/thorn.json``，落法＝``rework1/panel/_deviations.json``，施工单＝
``rework1/impl/thorn.md``。本轮改动：

- 词条 11 条 → **17 条**：能力 1 去掉「光·MySelf」前置改成开局 ＋50%、新增 536 技能强化开关；
  能力 2 加光共鸣前置并改成 100%／层・不设上限；能力 3 整槽重排（状态技伤 200% 可叠加、
  弱体阶梯技伤、光属性角色施技的技伤/攻击双阶梯、连击 ＋50）；能力 4 整槽换成
  麻痹 / 气绝 / 迟缓三条 **独立乘区** 特攻各 15%；能力 5／6 与队长技 4 行一格不动。
- **面板覆盖**：能力 1–4 四个槽走 ``desc_override_<string_id>``，逐行 ＝ ``panel/thorn.json``；
  能力 5／6 与队长技继续走客户端自渲染（本轮未改，文案照旧）。
- **技能**：倍率 42× → **50×**（4 段 × 12.5，两档都拉平成满级单值）；命中块的麻痹 / 迟缓
  外包 ``ConditionalsChangeSkillFlag(1)``——536 开着（光共鸣）时走长时长分支。

**平衡第二批（2026-09-27，作者：「索恩改成自身发动技能」）**：能力 3 #1（自身技伤 20%，限 10）与
#2（光队充能 1.5%，限 10）的触发方由 donor 带来的 c28=7 全队合计 + c29=White（光属性角色施技）改成
自身 c28=0、c29 空，与面板「自身发动技能时」一致；数值、限次、面板不动。``design/thorn.json`` 由
``wf_balance_20260927b_thorn.sync_mirrors`` 同步；``ABILITY_DONORS`` 两行的 ``changed`` 加 28/29。

本模块是「设计 JSON 驱动」的薄壳：队长 4 行、词条 6 键 11 条记录的 donor／逐格改／预期
``wf_describe`` 全部从 ``design/thorn.json`` 的 ``plan`` 读出后交给
:func:`wf_midautumn_kitlib.build_row` 装配 —— 本文件只登记「每行该用哪条官方 donor、
改动该落在哪几列」，成品行必须与设计稿登记的整行逐格一致，donor 侧漂移（官方基线换版、
设计稿被改）当场报错，不在这里手抄 15 行的具体数值。

本模块自己负责设计 JSON 管不到的部分：

- 技能 DSL 两档「星之猎手」：官方朝户八重 ``psychic_gal_{lv}`` 箭雨整树 + 五处逐格改
  （S1 CNA 条件特攻 ``[["DCParalysis"]]``、S2 倍率、S3 命中块追加三条 ``CreateCondition``、
  S4 换尾 → 光属性队友技伤状态、S5 麻痹 / 迟缓外包 ``ConditionalsChangeSkillFlag(1)``），
  三条弱体与新尾巴**整句取自官方 donor 树**再改参数；
- ``action_skill`` 两档：施法目标列换成箭雨骨架的 ``dynamic/skill/atk_nearest``、能量
  510→460 改 500→450（名称／描述由 tables 写 TEXTS，这里只核验）；
- 技能特效：**默认零克隆直接引用官方 ``skill_unique/psychic_gal/*``**（裁决 §4／框架 §10.3，
  图集零增量）；``B/pixel/thorn/fx_lut.json`` 交付后才整族克隆到 ``skill_unique/tweyen_light/``
  并套 LUT 换色（见 :func:`build`.deviations D-8）；
- 语音路由（kind 0 HpHigh 0.5，设计 D-3）与 ``switched_action_skill``；
- ``B/pixel/thorn/install.json`` 里的像素小人成品（缺文件静默跳过）。

不碰：live store / ``assets/`` / ``.cdn`` / 设备 / 存档；不发布。
由 ``python mod-tools/wf_midautumn_build.py --char thorn --step kit`` 调用 :func:`build`。
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any, Iterable, Sequence

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    pass  # Imports resolve from this checkout/package, not external source copies.

import wf_client_legality as L  # noqa: E402
import wf_dsl  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_midautumn_specs as MS  # noqa: E402

KitError = KL.KitError

KEY = "thorn"
CID, CODE = 159994, "tweyen_light"
ELEMENT = 4                                      # 光（0 基内部编号，token White）
TEMPLATE_ID, TEMPLATE_CODE = 151081, "high_priestess_ny22"
PF_TYPE, STANCE = 2, "Jammer"                    # c6 射击（PF 走射击原生，不做 722）；c26 设计 D-7

ABILITY_KEYS = tuple(f"{CID}{slot}" for slot in range(1, 7))
LEADER_ROWS = 4
ABILITY_RECORDS = 17                             # rework1：11 → 17

VOICE_KEY = KL.switch_key(CODE)                  # tweyen_light_voice_ready
VOICE_ROUTE: dict[str, Any] = {"kind": 0, "threshold": "0.5"}   # HpHigh（设计 D-3）

# ---------------------------------------------------------------- rework1：面板与字符串
#
# 536「技能强化」的 c70 串（未注册 = C8601）；裁决 §3：技能强化条目不写数字与时间。
CAS_CHANGE_SKILL = f"change_skill_{CODE}"
# 2026-09-27 第三轮（wf_balance_20260927c_panels，主会话 C）：「迟缓」统一按数据改「冻结」——开关分支挂的是
# ACFrozen（客户端名「冻结」）；技能说明（design/thorn.json texts.desc1/desc2）同步改。
# 同日技能强化文案（wf_balance_20260927c_panels，R2）：官方格式「强化『<技能名>』：<定性>」，点明『星之猎手』。
CHANGE_SKILL_TEXT = "强化『星之猎手』：赋予的麻痹效果、冻结效果持续时间大幅延长"
SKILL_FLAG_INDEX = 1                             # ConditionalsChangeSkillFlag 的开关号（536 ⇒ 1）

#: 走面板覆盖的词条槽（能力 5／6 本轮未改，继续走客户端自渲染）。
OVERRIDE_SLOTS = (1, 2, 3, 4)
CAS_ABILITY = {slot: f"desc_override_{CODE}_{slot}" for slot in OVERRIDE_SLOTS}

#: 逐行 ＝ ``rework1/panel/thorn.json``（作者已过目）。desc_override 会整块盖掉客户端
#: 自动文案，所以这里必须是**满级单值**，对应的行也必须拉平（min = max）。
PANEL_ABILITY: dict[int, tuple[str, ...]] = {
    # 2026-09-27 第三轮（wf_balance_20260927c_panels）：作者「迟缓」改「冻结」（技能 DSL 是 ACFrozen，kind 119 客户端
    # 也渲成冻结）；主会话口径3「光属性共鸣时：」→「光属性共鸣时，」。536 技能开关的光共鸣是真实条件，保留。
    # 同日技能强化文案（R2）：第2行 = 光共鸣前缀 + CHANGE_SKILL_TEXT。
    1: ("战斗开始时：自身技能槽立即＋50%",
        "光属性共鸣时，" + CHANGE_SKILL_TEXT,
        "光属性角色减益技能特攻＋40%"),
    # 2026-09-27 第三轮（主会话 F）：口径3 冒号→逗号；光共鸣是真实数据前置，保留。
    2: ("光属性共鸣时，敌人身上每有1个弱体效果，光属性角色对该敌人的攻击力＋100%",),
    # 2026-09-27 第三轮面板合并（wf_balance_20260927c_panels）：#1 自身技能伤害、#2 光属性角色技能充能
    # 数据同条件（自身施技、限 10 次、CT 0、主位）⇒ 原第2、3行并为一行，后缀「（最多叠加10次）」只写一次；
    # 第4、5行口径3 冒号→逗号。同日技能强化文案（R1）：能力3 没有 536 开关行，第3行去掉误导的「强化技能，」。
    3: ("自身发动技能时：光属性角色状态技能伤害＋200%（持续10秒，可叠加）",
        "自身发动技能时：自身技能伤害＋20%，光属性角色技能充能速度＋1.5%（最多叠加10次）",
        "光属性共鸣时，敌方每有1个弱体效果，自身技能伤害＋40%，且连击＋50",
        "光属性共鸣时，光属性角色发动技能时，光属性角色技能伤害＋50%（最多＋350%）、"
        "攻击力＋50%（最多＋350%）"),
    # 2026-09-27 第三轮：作者二选一定稿「合成一句并改冻结」——118 麻痹 / 53 眩晕畏缩(气绝) / 119 冻结 三条数据同条件、
    # 强度同为 15%，合写一句、「＋15%」只写一次。
    4: ("光属性角色对处于麻痹、气绝、冻结状态的敌人造成的伤害，额外乘区＋15%",),
}
#: 主位限定的槽（c1 = false）在覆盖文案里要自己带 <icon id='main'>——desc_override 会盖掉
#: 客户端逐行画的 Ⓜ 角标，图标不许再写成字面字符「Ⓜ」（本批 magnus/fluffy/stinel/kuro/hibiki
#: 同款做法，玩家反馈 09-21：写字面 Ⓜ 在客户端里渲成白色文字而不是红色主位图标）。
MAIN_ICON = " <icon id='main'>  "


def override_text(slot: int, unisonable: str) -> str:
    prefix = "" if str(unisonable).lower() == "true" else MAIN_ICON
    return "\n".join(prefix + line for line in PANEL_ABILITY[slot])


CAS_TEXTS: dict[str, str] = {CAS_CHANGE_SKILL: CHANGE_SKILL_TEXT}

# 队长表写 422/724/713 = C7050（裁决 §2／§8）。瞬发 kind 在 c45，持续 kind 在 c107。
FORBIDDEN_LEADER_KINDS = ("422", "724", "713")
LEADER_INSTANT_KIND, LEADER_DURING_KIND = 45, 107
ABILITY_INSTANT_KIND, ABILITY_DURING_KIND = 47, 109
# during 136（任一敌方状态计数减益）的 puller 列必须留空，否则 parseAt98 崩 C7050
# （记忆卡 wf-precondition-puller-c7050；设计风险 R-5）。
LEADER_DURING_PULLER = (96,)
ABILITY_DURING_PULLER = (98, 99)
DURING_DEBUFF_COUNT_KIND = "136"

TEXTS: dict[str, str] = {}        # 10 个文本键在 design/thorn.json 的 texts 块（build 里核验）
SPEC = {
    # desc_override_* 要生效需要 V14 APK（缺补丁不崩，只是面板回落到客户端自动文案）。
    "required_capabilities": (L.PANEL_OVERRIDE_V2,),
    "extra_keys": {
        KL.SWITCHED: (VOICE_KEY,),
        KL.CAS: (CAS_CHANGE_SKILL, *(CAS_ABILITY[slot] for slot in OVERRIDE_SLOTS)),
    },
}

# ---------------------------------------------------------------- 行 donor 清单
#
# ``donor`` = 官方基线（``OfficialBaseline('.cdn/cn')``）里的「键#记录号(0 基)」；
# ``changed`` = 允许与 donor 不同的列号集合（成品行的其余列必须与 donor 逐字相同）。
# 这两项是防漂移的双锁：官方基线换版或设计稿被改，diff 会跳出 ``changed`` 立刻报错。

LEADER_DONORS: tuple[dict[str, Any], ...] = (
    {"index": 0, "tag": "光共鸣→全队(光)攻击力", "donor": "151165#0", "changed": (0, 49, 50)},
    {"index": 1, "tag": "弱体数(限3)→全队(光)技能伤害", "donor": "121165#0",
     "changed": (0, 100, 107, 109, 111, 112)},
    {"index": 2, "tag": "弱体数(限5)→全队(光)触发敌方攻击特攻", "donor": "121165#0",
     "changed": (0, 109, 111, 112)},
    {"index": 3, "tag": "光共鸣→全队(光)技能槽充能", "donor": "151165#2", "changed": (0,)},
)

ABILITY_DONORS: dict[str, tuple[dict[str, Any], ...]] = {
    f"{CID}1": ({"tag": "开局自身技能槽 50%", "donor": "1510811#1", "changed": (0, 6, 11, 52)},
                {"tag": "536 光共鸣→切换技能形态", "donor": "1411113#0",
                 "changed": (0, 1, 2, 11, 70)},
                {"tag": "全队(光)减益技能特攻", "donor": "2110446#0",
                 "changed": (0, 2, 48, 49, 51, 52)}),
    f"{CID}2": ({"tag": "光共鸣+弱体数(无上限)→全队(光)触发敌方攻击特攻", "donor": "1110932#0",
                 "changed": (0, 2, 6, 9, 10, 11, 102, 111, 113, 114)},),
    f"{CID}3": ({"tag": "施技→全队(光)状态技能伤害 10 秒(可叠加)", "donor": "1510813#2",
                 "changed": (0, 51, 52, 61)},
                # 平衡第二批（2026-09-27）：donor 1510813#0/#1 的触发方是 c28=7 全队合计 + c29=White
                # （光属性角色施技），面板写「自身发动技能时」⇒ 触发方改成自身 c28=0、c29 空
                # （官方自身施技写法，同母本 1510813#2 与本键 #0/#6）。
                {"tag": "施技(限10)→自身技能伤害", "donor": "1510813#0",
                 "changed": (0, 28, 29, 51, 52)},
                {"tag": "施技(限10)→全队(光)技能槽充能", "donor": "1510813#1",
                 "changed": (0, 28, 29, 51, 52)},
                {"tag": "光共鸣+弱体数(无上限)→自身技能伤害", "donor": "1110932#0",
                 "changed": (0, 1, 2, 6, 9, 10, 11, 102, 109, 110, 111, 113, 114)},
                {"tag": "光共鸣+光角色施技(限7)→全队(光)技能伤害", "donor": "1510813#0",
                 "changed": (0, 6, 9, 10, 11, 34, 48, 49, 51, 52)},
                {"tag": "光共鸣+光角色施技(限7)→全队(光)攻击力", "donor": "1510813#1",
                 "changed": (0, 6, 9, 10, 11, 34, 47, 51, 52)},
                {"tag": "光共鸣+施技→自身追加连击 50", "donor": "2310044#0",
                 "changed": (0, 1, 2, 6, 9, 10, 11, 51, 52)}),
    f"{CID}4": ({"tag": "全队(光)麻痹特攻(独立乘区)", "donor": "2310023#0",
                 "changed": (0, 1, 2, 49, 51, 52)},
                {"tag": "全队(光)眩晕畏缩(气绝)特攻(独立乘区)", "donor": "2310053#0",
                 "changed": (0, 1, 2, 49, 51, 52)},
                {"tag": "全队(光)冻结(迟缓)特攻(独立乘区)", "donor": "2510471#0",
                 "changed": (0, 2, 51, 52)}),
    f"{CID}5": ({"tag": "敌方麻痹(限5)→全队(光)技能伤害", "donor": "2310326#0",
                 "changed": (0, 2, 47, 48, 49, 51, 52)},),
    f"{CID}6": ({"tag": "光共鸣→全队(光)技能槽充能", "donor": "1310985#0",
                 "changed": (0, 11, 49, 51, 52)},
                {"tag": "自身麻痹无效", "donor": "1411533#3", "changed": (0, 1, 2)}),
}

#: 本轮新增/改写的行必须带的光共鸣前置列（作者 09-21 00:5x：门槛一律用属性共鸣）。
RESONANCE_CELLS = {"c6": "2", "c9": "600000", "c10": "600000", "c11": "White"}
#: 这些 (键, 记录号) 必须带光共鸣前置——面板上写了「光属性共鸣时」的那几条。
RESONANCE_ROWS = ((f"{CID}1", 1), (f"{CID}2", 0), (f"{CID}3", 3), (f"{CID}3", 4),
                  (f"{CID}3", 5), (f"{CID}3", 6))
#: 面板写「自身发动技能时」的行：触发 23 的 puller 必须是自身（c28=0、c29 空；官方自身施技写法，
#: 469/569 条官方 I23 行即此形）。平衡第二批（2026-09-27）把 #1/#2 从 7+White 改成自身。
SELF_TRIGGER_CELLS = {"c27": "23", "c28": "0", "c29": ""}
SELF_TRIGGER_ROWS = ((f"{CID}3", 0), (f"{CID}3", 1), (f"{CID}3", 2))

# ---------------------------------------------------------------- 技能 DSL

PROGRAM_DIR = "battle/action/skill/action"
SKILL_DONOR = PROGRAM_DIR + "/rare5/psychic_gal$psychic_gal_{lv}"          # 箭雨整树（作者指定「风弓」）
TAIL_DONOR = PROGRAM_DIR + "/rare5/high_priestess_ny22$high_priestess_ny22_{lv}"
PARALYSIS_DONOR = PROGRAM_DIR + "/rare3/bee_girl$bee_girl_{lv}"
FROZEN_DONOR = PROGRAM_DIR + "/rare4/elf_archer$elf_archer_{lv}"
TOLERANCE_DONOR = PROGRAM_DIR + "/rare4/devil_clown_xm21$devil_clown_xm21_{lv}"
SLAYER_DONOR = PROGRAM_DIR + "/rare5/thunder_archer$thunder_archer_2"      # CNA 第 4 参唯一官方形状

DONOR_ROOT_STATEMENTS = 5          # psychic_gal：停球 / 箭雨 / 解弱体 / 浮游×2
KIT_ROOT_STATEMENTS = 3            # 索恩：停球 / 箭雨 / 光属性队友技伤状态
HIT_AREA_NCOLS = 27
HIT_AREA_BIND_SLOTS = (19, 21, 22)
HIT_AREA_ONHIT_SLOT = 23
ONHIT_DONOR_STATEMENTS = 2         # ShakeCamera + CreateNormalAttack
TAIL_BIND = 17                     # 换尾后的 FindAllSubjects 绑定 id（母本尾巴用的是 17）
TAIL_SELECTOR, TAIL_FILTER = 33, [5]          # 33 = 己方全体（含自身）；[5] = 光属性过滤
CONDITION_TARGET_KIND_ENEMY = 3               # CreateCondition 下标 10（记忆卡 wf-createcondition-target-kind）
CONDITION_FORCE_APPLY = False                 # 下标 12：麻痹不对 boss 强制付与（裁决 §2）
TOLERANCE_ELEMENT_ALL = 254                   # ALL：解析后 = 0 ⇒ 任何 boss 都不会静默吃掉（风险 R-1）
TOLERANCE_STACKS = 3

#: 两档的数值（设计 §4.2；官方两档比例 = 倍率 ×2/3、帧数 ×0.8、比例值 ×0.75）。
#:
#: rework1：``cna`` 两档都拉平成满级单值（作者「技能倍率调整为 50 倍」＝ 4 段 × 12.5；
#: SLv1 按官方两档 ×2/3 ＝ 8.33 ⇒ 33.3 倍）。``*_long`` 是 536 开着（光共鸣）时走的
#: 长时长分支（研究卡 B §6.3 给的强化档：麻痹 900–1200、迟缓 1800–2400）。
SKILL_VALUES: dict[str, dict[str, Any]] = {
    "1": {"cna": (8.33, 8.33), "paralysis": (300, 300), "paralysis_long": (900, 900),
          "frozen": (600, 600), "frozen_long": (1200, 1200),
          "tolerance_frames": (3000, 3000), "tolerance_value": (-0.04, -0.04),
          "tail_frames": (720, 720), "tail_value": (0.7, 0.7)},
    "2": {"cna": (12.5, 12.5), "paralysis": (360, 480), "paralysis_long": (1080, 1200),
          "frozen": (750, 900), "frozen_long": (1650, 1800),
          "tolerance_frames": (3300, 3300), "tolerance_value": (-0.05, -0.06),
          "tail_frames": (900, 900), "tail_value": (0.9, 1.1)},
}
SKILL_SEGMENTS = 4                 # 判定区最多 4 段 ⇒ SLv2 满级合计 4 × 12.5 = 50 倍
SKILL_TOTAL_LV2 = 50.0

# 特效：默认零克隆直接引用官方路径；交付 fx_lut.json 才克隆换色（deviations D-8）。
FX_SRC_DIR = "battle/effect/skill_unique/psychic_gal"
FX_SUBDIR = "starhunt"
FX_DST_DIR = f"battle/effect/skill_unique/{CODE}/{FX_SUBDIR}"
FX_MEMBERS = ("psychic_gal_shoot", "psychic_gal_hiteffect") + \
             tuple(f"psychic_gal_arrow{n}" for n in range(1, 7))


# ---------------------------------------------------------------- 设计稿读取

def load_design(root: Path) -> dict[str, Any]:
    design = MS.load_design(Path(root), KEY)
    if not design:
        raise KitError(f"design/{KEY}.json missing (batch {MS.BATCH_DIR})")
    if design.get("schema") != "ma-design/1" or design.get("cid") != CID or design.get("code") != CODE:
        raise KitError(f"design identity drift: {design.get('schema')} {design.get('cid')} {design.get('code')}")
    return design


def design_row(cells: dict[str, Any], ncols: int, label: str) -> list[str]:
    """设计稿的 ``cells``（只列非空列，键写成 ``"c47"``）→ 整行。"""
    row = [""] * ncols
    for col, value in cells.items():
        index = int(str(col).lstrip("cC"))
        if not 0 <= index < ncols:
            raise KitError(f"{label}: column {col!r} out of range (ncols={ncols})")
        row[index] = "" if value is None else str(value)
    return row


def donor_address(spec: str) -> tuple[str, int]:
    key, sep, index = str(spec).partition("#")
    if sep != "#" or not key.isdigit() or not index.isdigit():
        raise KitError(f"donor must be written '<键>#<0基记录号>': {spec!r}")
    return key, int(index)


def edits_from_donor(donor: Sequence[str], want: Sequence[str], allowed: Iterable[int],
                     label: str) -> dict[int, str]:
    """donor → 设计成品行的逐格差；差必须落在 ``allowed`` 之内（donor／设计稿双向防漂移）。"""
    donor = list(donor) + [""] * max(0, len(want) - len(donor))
    changed = sorted(i for i in range(len(want)) if donor[i] != want[i])
    allowed = sorted(set(allowed))
    if changed != allowed:
        raise KitError(f"{label}: donor 逐格差 {changed} != 本模块登记的 {allowed}"
                       f"（官方基线漂移或设计稿被改，须先对账再改这里）")
    return {i: want[i] for i in changed}


def _build(ctx, kind: str, donor_spec: str, cells: dict[str, Any], expect: str,
           allowed: Iterable[int], label: str) -> tuple[list[str], dict[str, Any]]:
    ncols = KL.ABILITY_NCOLS if kind == "ability" else KL.LEADER_NCOLS
    table = KL.ABILITY if kind == "ability" else KL.LEADER
    key, index = donor_address(donor_spec)
    want = design_row(cells, ncols, label)
    donor = KL.donor_row(ctx, table, key, index)
    edits = edits_from_donor(donor, want, allowed, label)
    row, evidence = KL.build_row(ctx, kind, f"{key}#{index}", edits,
                                 element=ELEMENT if kind == "ability" else None,
                                 expect_describe=expect, label=label)
    if row != want:
        diffs = [(i, row[i], want[i]) for i in range(ncols) if row[i] != want[i]]
        raise KitError(f"{label}: 成品行与设计稿 cells 不一致（列, 实际, 设计）: {diffs}")
    KL.check_panel(expect, label=label)
    return row, evidence | {"panel": expect, "tag": label}


def check_design_donor_text(entry: dict[str, Any], donor_spec: str, label: str) -> None:
    """设计稿 donor 那句人话里必须出现同一个 donor 键（防两边各改一半）。"""
    key, _ = donor_address(donor_spec)
    text = str(entry.get("donor", ""))
    if key not in text:
        raise KitError(f"{label}: 设计稿 donor 文本 {text!r} 里没有本模块登记的 donor 键 {key}")


def build_leader_rows(ctx, design: dict[str, Any]) -> tuple[list[list[str]], list[dict[str, Any]]]:
    plan = design["plan"]["leader_ability"]
    if str(plan["key"]) != str(CID) or int(plan["layout"]["ncols"]) != KL.LEADER_NCOLS:
        raise KitError(f"design leader block drift: key={plan.get('key')} layout={plan.get('layout')}")
    entries = list(plan["rows"])
    if len(entries) != LEADER_ROWS or len(LEADER_DONORS) != LEADER_ROWS:
        raise KitError(f"design leader_ability carries {len(entries)} rows, expected {LEADER_ROWS}")
    rows, evidence = [], []
    for entry, spec in zip(entries, LEADER_DONORS):
        if int(entry["index"]) != spec["index"]:
            raise KitError(f"leader row order drift: {entry['index']} != {spec['index']}")
        label = f"leader#{spec['index']}({spec['tag']})"
        check_design_donor_text(entry, spec["donor"], label)
        row, ev = _build(ctx, "leader_ability", spec["donor"], entry["cells"],
                         entry["desc_expected"], spec["changed"], label)
        if row[0] != CODE:
            raise KitError(f"{label}: c0 {row[0]!r} != {CODE}")
        rows.append(row)
        evidence.append(ev)
    return rows, evidence


def build_ability_rows(ctx, design: dict[str, Any]) -> tuple[dict[str, list[list[str]]],
                                                             list[dict[str, Any]]]:
    plan = design["plan"]["ability"]
    if int(plan["layout"]["ncols"]) != KL.ABILITY_NCOLS:
        raise KitError(f"design ability ncols drift: {plan['layout'].get('ncols')}")
    if tuple(sorted(plan["keys"])) != tuple(sorted(ABILITY_KEYS)):
        raise KitError(f"design ability keys drift: {sorted(plan['keys'])}")
    rows_by_key: dict[str, list[list[str]]] = {}
    evidence: list[dict[str, Any]] = []
    total = 0
    for slot, key_name in enumerate(ABILITY_KEYS, start=1):
        block = plan["keys"][key_name]
        specs = ABILITY_DONORS[key_name]
        records = list(block["records"])
        if len(records) != len(specs):
            raise KitError(f"ability {key_name}: 设计 {len(records)} 条 != 本模块登记 {len(specs)} 条")
        unisonable = list(block["unisonable_per_record"])
        if len(set(unisonable)) != 1:
            raise KitError(f"ability {key_name}: c1 是整键语义，设计稿却混用了 {unisonable}")
        rows: list[list[str]] = []
        for index, (entry, spec) in enumerate(zip(records, specs)):
            if int(entry["index"]) != index:
                raise KitError(f"ability {key_name}: record order drift {entry['index']} != {index}")
            label = f"{key_name}#{index}({spec['tag']})"
            check_design_donor_text(entry, spec["donor"], label)
            row, ev = _build(ctx, "ability", spec["donor"], entry["cells"],
                             entry["desc_expected"], spec["changed"], label)
            rows.append(row)
            evidence.append(ev)
            total += 1
        KL.check_ability_key(rows, key_name, CODE, slot)
        if rows[0][1] != str(unisonable[0]) or rows[0][2] != str(block["statue_group"]):
            raise KitError(f"ability {key_name}: c1/c2 {rows[0][1]}/{rows[0][2]} != design "
                           f"{unisonable[0]}/{block['statue_group']}")
        rows_by_key[key_name] = rows
    if total != ABILITY_RECORDS:
        raise KitError(f"design ability carries {total} records, expected {ABILITY_RECORDS}")
    return rows_by_key, evidence


def check_resonance_rows(ability_rows: dict[str, list[list[str]]]) -> list[str]:
    """面板写了「光属性共鸣时」的行必须真的带官方共鸣前置（作者 09-21 00:5x）。"""
    checked = []
    for key, index in RESONANCE_ROWS:
        row = ability_rows[key][index]
        bad = {col: row[int(col[1:])] for col, want in RESONANCE_CELLS.items()
               if row[int(col[1:])] != want}
        if bad:
            raise KitError(f"{key}#{index}: 缺光共鸣前置 {bad}（应为 {RESONANCE_CELLS}）")
        checked.append(f"{key}#{index}")
    return checked


def check_self_trigger_rows(ability_rows: dict[str, list[list[str]]]) -> list[str]:
    """面板写「自身发动技能时」的行，触发方必须真的是自身（平衡第二批，作者「索恩改成自身发动技能」）。"""
    checked = []
    for key, index in SELF_TRIGGER_ROWS:
        row = ability_rows[key][index]
        bad = {col: row[int(col[1:])] for col, want in SELF_TRIGGER_CELLS.items()
               if row[int(col[1:])] != want}
        if bad:
            raise KitError(f"{key}#{index}: 面板写「自身发动技能时」，触发方却是 {bad}"
                           f"（应为 {SELF_TRIGGER_CELLS}）")
        checked.append(f"{key}#{index}")
    return checked


def write_strings(ctx, design: dict[str, Any],
                  ability_rows: dict[str, list[list[str]]]) -> dict[str, str]:
    """``custom_ability_string``：536 的 c70 串 ＋ 能力 1–4 的整槽面板覆盖串。

    两个键的反查判据不同：536 的串必须被某条行的 c70 引用（否则是死串）；
    ``desc_override_*`` 的串按键名反查——客户端查的是 ``desc_override_`` ＋ 该槽
    **第 0 行的 c0（string_id）**。
    """
    strings = dict(CAS_TEXTS)
    for slot in OVERRIDE_SLOTS:
        rows = ability_rows[f"{CID}{slot}"]
        want = L.PANEL_OVERRIDE_KEY_PREFIX + rows[0][0]
        if want != CAS_ABILITY[slot]:
            raise KitError(f"panel override key {CAS_ABILITY[slot]!r} != "
                           f"desc_override_<string_id> {want!r}")
        text = override_text(slot, rows[0][1])
        wants_icon = rows[0][1] == "false"
        for line in text.split("\n"):
            if line.startswith(MAIN_ICON) != wants_icon:
                raise KitError(f"slot {slot}: 覆盖文案的主位角标与 c1={rows[0][1]!r} 不一致")
        strings[CAS_ABILITY[slot]] = text

    declared = set(ctx.spec.extra_keys.get(KL.CAS, ()))
    missing = [k for k in strings if k not in declared]
    if missing:
        raise KitError(f"custom_ability_string keys not declared in SPEC['extra_keys']: {missing}")
    official = set(ctx.official_flat(KL.CAS))
    clashes = sorted(set(strings) & official)
    if clashes:
        raise KitError(f"custom_ability_string keys already exist officially: {clashes}")
    # 裁决 §3：技能强化条目不写数字与时间；覆盖串只过通用禁词。
    KL.check_panel(strings[CAS_CHANGE_SKILL], skill_flag=True, label=CAS_CHANGE_SKILL)
    for key in CAS_ABILITY.values():
        for line in strings[key].split("\n"):
            KL.check_panel(line.replace(MAIN_ICON, ""), label=key)
    referenced = {row[70] for rows in ability_rows.values() for row in rows if row[70]}
    if CAS_CHANGE_SKILL not in referenced:
        raise KitError(f"custom_ability_string {CAS_CHANGE_SKILL} not referenced by any ability c70")

    plan = {entry["key"]: entry["text"]
            for entry in design["plan"]["texts"]["custom_ability_string"]["rows"]}
    if plan != strings:
        drift = {k: (plan.get(k), strings.get(k)) for k in set(plan) | set(strings)
                 if plan.get(k) != strings.get(k)}
        raise KitError(f"design custom_ability_string 与本模块不一致（设计, 实际）: {drift}")
    ctx.write_flat(KL.CAS, {k: [[v]] for k, v in strings.items()})
    return strings


def ban_forbidden_leader_kinds(rows: list[list[str]]) -> None:
    for n, row in enumerate(rows):
        if row[LEADER_INSTANT_KIND] in FORBIDDEN_LEADER_KINDS \
                or row[LEADER_DURING_KIND] in FORBIDDEN_LEADER_KINDS:
            raise KitError(f"leader#{n}: forbidden kind in leader_ability "
                           f"(c{LEADER_INSTANT_KIND}={row[LEADER_INSTANT_KIND]!r} "
                           f"c{LEADER_DURING_KIND}={row[LEADER_DURING_KIND]!r})")


def check_during_pullers(leader_rows: list[list[str]],
                         ability_rows: dict[str, list[list[str]]]) -> list[str]:
    """136 的 puller 列必须留空（风险 R-5 / 记忆卡 wf-precondition-puller-c7050）。"""
    checked = []
    for n, row in enumerate(leader_rows):
        if row[95] != DURING_DEBUFF_COUNT_KIND:
            continue
        bad = [c for c in LEADER_DURING_PULLER if row[c]]
        if bad:
            raise KitError(f"leader#{n}: during {DURING_DEBUFF_COUNT_KIND} puller 列非空 {bad}")
        checked.append(f"leader#{n}")
    for key, rows in ability_rows.items():
        for n, row in enumerate(rows):
            if row[97] != DURING_DEBUFF_COUNT_KIND:
                continue
            bad = [c for c in ABILITY_DURING_PULLER if row[c]]
            if bad:
                raise KitError(f"{key}#{n}: during {DURING_DEBUFF_COUNT_KIND} puller 列非空 {bad}")
            checked.append(f"{key}#{n}")
    return checked


# ---------------------------------------------------------------- action_skill

def write_action_skill(ctx, design: dict[str, Any]) -> dict[str, list[str]]:
    """施法目标列换成箭雨骨架的 ``atk_nearest``、能量按设计稿；名称/描述由 tables 写。"""
    spec = ctx.spec
    energy = design["plan"]["skills"]["energy"]
    donor = {level: cells for level, cells in
             _official_action_rows(ctx, "psychic_gal").items()}
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
        pair = energy[f"lv{level}"]
        cells[2] = donor[level][2]                       # dynamic/skill/atk_nearest
        cells[4], cells[5] = str(pair["c4"]), str(pair["c5"])
        # c3 / c6 / c8–c16：箭雨骨架与表母本逐字相同，这里做硬核对，防 donor 侧漂移。
        for col in (3, 6, *range(8, 17)):
            if cells[col] != donor[level][col]:
                raise KitError(f"action_skill {level}: c{col} {cells[col]!r} != psychic_gal "
                               f"{donor[level][col]!r}")
        if any(cells[17:]):
            raise KitError(f"action_skill {level}: c17+ not empty {cells[17:]}")
        out[level] = cells
    ctx.write_nested(KL.ACTION, CODE, {lv: [cells] for lv, cells in out.items()},
                     replace_inner=True)
    return out


def _official_action_rows(ctx, code: str) -> dict[str, list[str]]:
    import wf_seasonal7_common as C
    raw = ctx.pack.official_read(KL.ACTION, "common")
    if raw is None:
        raise KitError(f"official baseline lacks {KL.ACTION}")
    table = C.core.load_nested_table_bytes(raw, KL.ACTION)
    if code not in table.rows:
        raise KitError(f"official action_skill lacks {code}")
    return {level: C.csv_split(value)[0]
            for level, value in table.rows[code].text_rows().items()}


# ---------------------------------------------------------------- DSL 工具

def _statements(tree) -> list:
    body = tree[11]
    if not (isinstance(body, list) and body and body[0] == "Block"):
        raise KitError(f"root statement block drift: {type(body)}")
    return body[1]


def _command(statement):
    if isinstance(statement, list) and len(statement) == 2 and statement[0] == "Command" \
            and isinstance(statement[1], list):
        return statement[1]
    return None


def find_statements(node, name: str, out: list | None = None) -> list:
    """递归找出所有 ``["Command", [name, ...]]`` 语句（返回语句本身，可就地改）。"""
    out = [] if out is None else out
    if isinstance(node, list):
        cmd = _command(node)
        if cmd is not None and cmd[0] == name:
            out.append(node)
        for child in node:
            find_statements(child, name, out)
    return out


def _only(items: list, what: str):
    if len(items) != 1:
        raise KitError(f"expected exactly one {what}, found {len(items)}")
    return items[0]


def _range(pair) -> list[dict[str, Any]]:
    low, high = pair
    return [{"min": low, "max": high}]


def _condition_of(statement):
    cmd = _command(statement)
    if cmd is None or cmd[0] != "CreateCondition":
        raise KitError(f"not a CreateCondition statement: {cmd[0] if cmd else statement!r}")
    return cmd


def pick_condition(tree, ac_name: str, *, ranged: bool = True):
    """从官方 donor 树里取一条 ``CreateCondition``（按 AC 构造名挑，不按下标）。

    ``ranged=True``：只认 ``{min,max}`` 形（排掉 ``alv_min/alv_max`` 的觉醒成长形，
    本套件两档都用定值形）。同名多条时要求它们除主体 id 外逐字相同。
    """
    hits = []
    for statement in find_statements(tree, "CreateCondition"):
        cmd = _command(statement)
        entry = cmd[2][0] if isinstance(cmd[2], list) and cmd[2] else None
        if not (isinstance(entry, list) and entry and entry[0] == ac_name):
            continue
        frames = entry[1][0] if isinstance(entry[1], list) and entry[1] else {}
        if ranged and not (isinstance(frames, dict) and "min" in frames):
            continue
        hits.append(statement)
    if not hits:
        raise KitError(f"donor tree lacks a {ac_name} CreateCondition")
    first = copy.deepcopy(hits[0])
    _command(first)[1] = 0
    for other in hits[1:]:
        probe = copy.deepcopy(other)
        _command(probe)[1] = 0
        if probe != first:
            raise KitError(f"donor {ac_name} CreateCondition rows disagree: {probe} != {first}")
    return copy.deepcopy(hits[0])


def bind_condition(statement, subject: int, *, label: str):
    """把 donor 的 ``CreateCondition`` 绑到本树的主体上，并核对付与对象种类/强制付与。"""
    cmd = _condition_of(statement)
    cmd[1] = subject
    if cmd[10] != CONDITION_TARGET_KIND_ENEMY:
        raise KitError(f"{label}: CreateCondition 付与对象种类 {cmd[10]} != {CONDITION_TARGET_KIND_ENEMY}")
    if cmd[12] is not CONDITION_FORCE_APPLY:
        raise KitError(f"{label}: forceApply {cmd[12]!r} != {CONDITION_FORCE_APPLY}（裁决 §2）")
    return statement


def make_paralysis(ctx, level: str, subject: int, *, key: str = "paralysis"):
    values = SKILL_VALUES[level]
    statement = pick_condition(ctx.template_dsl(PARALYSIS_DONOR.format(lv=level)), "ACParalysis")
    entry = _condition_of(statement)[2][0]
    entry[1] = _range(values[key])
    return bind_condition(statement, subject, label=f"麻痹 lv{level} {key}")


def make_frozen(ctx, level: str, subject: int, *, key: str = "frozen"):
    values = SKILL_VALUES[level]
    statement = pick_condition(ctx.template_dsl(FROZEN_DONOR.format(lv=level)), "ACFrozen")
    entry = _condition_of(statement)[2][0]
    entry[1] = _range(values[key])
    return bind_condition(statement, subject, label=f"迟缓 lv{level} {key}")


def make_flag_branch(ctx, level: str, subject: int):
    """536 开着（光共鸣）走长时长分支，没开走基础时长分支。

    ``ConditionalsChangeSkillFlag(1, thenBlock, elseBlock)``——同批芙拉菲已在用的结构。
    分支必须是完整 ``["Block", [...]]``；空分支写 ``["Block", []]``，**禁写
    ``["DoNothing"]``**（那是 IfTargetNotFound 的枚举，进游戏 F1009，记忆卡
    wf-dsl-donothing-enum-trap）。这里两支都非空，不涉及那个坑。
    """
    long_block = ["Block", [make_paralysis(ctx, level, subject, key="paralysis_long"),
                            make_frozen(ctx, level, subject, key="frozen_long")]]
    base_block = ["Block", [make_paralysis(ctx, level, subject),
                            make_frozen(ctx, level, subject)]]
    return ["Command", ["ConditionalsChangeSkillFlag", SKILL_FLAG_INDEX, long_block, base_block]]


def make_tolerance(ctx, level: str, subject: int):
    """累积全属性抗性↓：元素码写 254（ALL）—— 解析后 = 0，任何 boss 都不会被白名单拒掉（R-1）。"""
    values = SKILL_VALUES[level]
    statement = pick_condition(ctx.template_dsl(TOLERANCE_DONOR.format(lv=level)),
                               "ACToleranceOfElement")
    entry = _condition_of(statement)[2][0]
    if entry[2] not in (1, 2, 3, 4, 5, 6):
        raise KitError(f"抗性↓ donor 的元素码 {entry[2]!r} 不是单属性形")
    entry[1] = _range(values["tolerance_frames"])
    entry[2] = TOLERANCE_ELEMENT_ALL
    entry[3] = _range(values["tolerance_value"])
    entry[4] = _range((TOLERANCE_STACKS, TOLERANCE_STACKS))
    return bind_condition(statement, subject, label=f"抗性↓ lv{level}")


def make_tail(ctx, level: str):
    """换尾：母本 151081 的「光属性队友技伤状态」整句（FindAllSubjects 33 + [5]），只改数值与绑定。"""
    values = SKILL_VALUES[level]
    donor = ctx.template_dsl(TAIL_DONOR.format(lv=level))
    hits = [s for s in find_statements(donor, "FindAllSubjects")
            if _command(s)[2] == TAIL_SELECTOR and _command(s)[3] == TAIL_FILTER]
    statement = copy.deepcopy(_only(hits, f"FindAllSubjects({TAIL_SELECTOR},{TAIL_FILTER})"))
    cmd = _command(statement)
    cmd[1] = TAIL_BIND
    inner = _only(find_statements(cmd[9], "CreateCondition"), "tail CreateCondition")
    condition = _condition_of(inner)
    condition[1] = TAIL_BIND            # CHA/FindAll 的 lookup 位必须与绑定 id 一致（防 C16103）
    entry = condition[2][0]
    if entry[0] != "ACSkillDamage":
        raise KitError(f"tail donor AC drift: {entry[0]}")
    entry[1] = _range(values["tail_frames"])
    entry[2] = _range(values["tail_value"])
    return statement


def slayer_param(ctx):
    """CNA 第 4 参 ``[["DCParalysis"]]``：官方雷弓的唯一形状（官方 34 处全是单条目）。"""
    donor = ctx.template_dsl(SLAYER_DONOR)
    hits = [s for s in find_statements(donor, "CreateNormalAttack") if _command(s)[4]]
    param = copy.deepcopy(_command(_only(hits, "CreateNormalAttack with a condition slayer"))[4])
    if param != [["DCParalysis"]]:
        raise KitError(f"condition slayer donor drift: {param!r}")
    return param


def build_skill_tree(ctx, level: str) -> tuple[Any, dict[str, Any]]:
    """官方箭雨整树 + S1/S2/S3/S4 四处改动（设计 §4.2）。特效引用此时仍是官方 donor 路径。"""
    values = SKILL_VALUES[level]
    tree = copy.deepcopy(ctx.template_dsl(SKILL_DONOR.format(lv=level)))
    if tree[0] != "ActionDsl" or tree[10] != 0:
        raise KitError(f"skill {level} donor head drift: {tree[:2]} bta={tree[10]}")
    body = _statements(tree)
    if len(body) != DONOR_ROOT_STATEMENTS:
        raise KitError(f"skill {level} donor root carries {len(body)} statements, "
                       f"expected {DONOR_ROOT_STATEMENTS}")

    # ---- S4 换尾：解弱体 + 浮游三句 → 光属性队友技伤状态一句
    dropped = []
    for statement in body[2:]:
        cmd = _command(statement)
        if cmd is None or cmd[0] != "FindAllSubjects":
            raise KitError(f"skill {level}: donor statement {cmd[0] if cmd else statement!r} "
                           f"is not a FindAllSubjects tail")
        dropped.append({"selector": cmd[2], "filter": cmd[3]})
    body[2:] = [make_tail(ctx, level)]

    # ---- S1/S2/S3 命中块
    hit_area = _command(_only(find_statements(tree, "CreateHitArea"), "CreateHitArea"))
    if len(hit_area) != HIT_AREA_NCOLS:
        raise KitError(f"skill {level}: CreateHitArea has {len(hit_area)} params, "
                       f"expected {HIT_AREA_NCOLS}")
    onhit = hit_area[HIT_AREA_ONHIT_SLOT]
    if not (isinstance(onhit, list) and onhit and onhit[0] == "Block"):
        raise KitError(f"skill {level}: on-hit slot is not a Block")
    statements = onhit[1]
    if len(statements) != ONHIT_DONOR_STATEMENTS:
        raise KitError(f"skill {level}: donor on-hit carries {len(statements)} statements, "
                       f"expected {ONHIT_DONOR_STATEMENTS}")
    cna = _command(_only(find_statements(onhit, "CreateNormalAttack"), "on-hit CreateNormalAttack"))
    subject = cna[1]
    if subject != hit_area[HIT_AREA_BIND_SLOTS[2]]:
        raise KitError(f"skill {level}: CNA subject {subject} != 判定区第三绑定位 "
                       f"{hit_area[HIT_AREA_BIND_SLOTS[2]]}（第二位必崩 U_34c3bb）")
    if cna[4]:
        raise KitError(f"skill {level}: donor CNA already carries a condition slayer {cna[4]!r}")
    cna[4] = slayer_param(ctx)                       # S1
    cna[6] = _range(values["cna"])                   # S2
    statements.append(make_flag_branch(ctx, level, subject))     # S3 + S5
    statements.append(make_tolerance(ctx, level, subject))
    if len(statements) != ONHIT_DONOR_STATEMENTS + 2:
        raise KitError(f"skill {level}: on-hit now carries {len(statements)} statements")
    if len(_statements(tree)) != KIT_ROOT_STATEMENTS:
        raise KitError(f"skill {level}: root carries {len(_statements(tree))} statements")

    branches = [s for s in find_statements(tree, "ConditionalsChangeSkillFlag")]
    if len(branches) != 1 or _command(branches[0])[1] != SKILL_FLAG_INDEX:
        raise KitError(f"skill {level}: expected exactly one ConditionalsChangeSkillFlag"
                       f"({SKILL_FLAG_INDEX}), found {len(branches)}")
    for side in (2, 3):
        block = _command(branches[0])[side]
        if not (isinstance(block, list) and block and block[0] == "Block" and len(block[1]) == 2):
            raise KitError(f"skill {level}: ConditionalsChangeSkillFlag branch {side} is not a "
                           f"2-statement Block: {block!r}")
    want_total = SKILL_TOTAL_LV2 if level == "2" else SKILL_TOTAL_LV2 * 2 / 3
    total = values["cna"][1] * SKILL_SEGMENTS
    if abs(total - want_total) > 0.05:
        raise KitError(f"skill {level}: 合计倍率 {total} 与登记的「50 倍（SLv1 ×2/3）」对不上")
    if values["cna"][0] != values["cna"][1]:
        raise KitError(f"skill {level}: 倍率未拉平成满级单值 {values['cna']}")

    gates = {"level": level, "dropped_tail": dropped, "cna_subject": subject,
             "cna_multiplier": cna[6], "condition_slayer": cna[4],
             "buff_target_as": tree[10], "onhit_statements": len(statements),
             "skill_flag": SKILL_FLAG_INDEX,
             "total_multiplier": round(values["cna"][1] * SKILL_SEGMENTS, 4)}
    return tree, gates


def check_design_tree(design: dict[str, Any], level: str, tree) -> dict[str, Any]:
    """与设计稿登记的成品树逐节点比对（设计稿的 programs[].tree 是本套件的唯一数值真源）。"""
    programs = {str(p["level"]): p for p in design["plan"]["skills"]["programs"]}
    entry = programs.get(level)
    if entry is None:
        raise KitError(f"design plan.skills.programs lacks level {level}")
    want = entry["tree"]
    if want != tree:
        raise KitError(f"skill {level}: 成品树与设计稿 programs[{level}].tree 不一致"
                       f"（先对账再改；两边都改才算一次改动）")
    return {"logical": entry.get("logical"), "encoded_bytes": entry.get("encoded_bytes")}


def _dsl_problems(tree) -> list[str]:
    problems = [f"direction: {p}" for p in wf_dsl.player_side_dsl_problems(tree)]
    problems += [f"subject: {p}" for p in L.action_dsl_subject_binding_problems(tree)]
    problems += [f"hit_target: {p}" for p in L.action_dsl_hit_area_target_problems(tree)]
    problems += [f"element: {p}" for p in L.action_dsl_element_problems(tree, ELEMENT)]
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


def effect_paths(tree) -> set[str]:
    paths = {str(cmd[2][1]) for cmd in wf_dsl.iter_dsl_commands(tree, "ShowEffect")
             if isinstance(cmd[2], list) and cmd[2][0] == "SpecifyEffectDirectly"}
    for cmd in wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack"):
        hit = cmd[15]
        if isinstance(hit, list) and hit[0] == "SpecifyHitEffectDirectly" \
                and isinstance(hit[1], list) and hit[1][0] == "SpecifyEffectDirectly":
            paths.add(str(hit[1][1]))
    return paths


# ---------------------------------------------------------------- 入口

def build(ctx) -> dict[str, Any]:
    spec = ctx.spec
    if (spec.cid, spec.code, spec.element) != (CID, CODE, ELEMENT):
        raise KitError(f"identity drift: {spec.cid}/{spec.code}/element {spec.element}")
    if (spec.template_id, spec.template_code) != (TEMPLATE_ID, TEMPLATE_CODE):
        raise KitError(f"template drift: {spec.template_id}/{spec.template_code}")
    if spec.pf_type != PF_TYPE or spec.stance != STANCE:
        raise KitError(f"spec drift: pf_type={spec.pf_type} stance={spec.stance}")
    if MS.text_placeholders(spec):
        raise KitError(f"design texts still placeholders: {MS.text_placeholders(spec)}")

    design = load_design(ctx.root)
    if design["plan"]["unique_conditions"]["add"]:
        raise KitError("设计稿登记了固有状态，但本套件是零固有件方案（设计 D-4；rework1 未新增）")
    if design["plan"]["texts"]["custom_ability_power_up_string"]["rows"]:
        raise KitError("设计稿登记了 custom_ability_power_up_string，但本套件不用这条通路")

    # ---- 1) 队长技 4 行 + 词条 6 键 17 条（design.json 驱动，逐行过 legality 与 wf_describe）
    leader_rows, leader_evidence = build_leader_rows(ctx, design)
    ban_forbidden_leader_kinds(leader_rows)
    ability_rows, ability_evidence = build_ability_rows(ctx, design)
    pullers = check_during_pullers(leader_rows, ability_rows)
    resonance = check_resonance_rows(ability_rows)
    self_trigger = check_self_trigger_rows(ability_rows)
    capabilities: set[str] = set()
    for ev in (*leader_evidence, *ability_evidence):
        capabilities.update(ev["capabilities"])
    ctx.write_flat(KL.LEADER, {str(CID): leader_rows})
    ctx.write_flat(KL.ABILITY, ability_rows)

    # ---- 1b) custom_ability_string：536 的 c70 串 + 能力 1–4 的整槽面板覆盖
    strings = write_strings(ctx, design, ability_rows)
    capabilities.add(L.PANEL_OVERRIDE_V2)         # desc_override_* 惰性生效，缺 V14 不崩

    # ---- 2) 面板文案规则（21 行渲染回读 + 覆盖串 + 10 个文本键）
    panel = [ev["panel"] for ev in (*leader_evidence, *ability_evidence)]
    panel += [line for slot in OVERRIDE_SLOTS for line in PANEL_ABILITY[slot]]
    for name in ("title", "profile", "leader", "skill1", "desc1", "skill2", "desc2"):
        KL.check_panel(spec.texts[name], label=f"texts.{name}")

    # ---- 3) action_skill：施法目标列 + 两档能量
    action_rows = write_action_skill(ctx, design)

    # ---- 4) 技能特效：默认零克隆直接引用官方路径；交付 fx_lut.json 才克隆换色（D-8）
    lut_path = KL.pixel_dir(ctx) / "fx_lut.json"
    lut = KL.png_transform_from_lut(lut_path)
    family = None
    if lut is not None:
        family = ctx.clone_effect_family(FX_SRC_DIR, FX_SUBDIR, fx_names=list(FX_MEMBERS),
                                         png_transform=lut)
        if family["dst_dir"] != FX_DST_DIR:
            raise KitError(f"effect family drift: {family['dst_dir']}")
        missing = sorted(set(FX_MEMBERS) - set(family["copied_bases"]))
        if missing:
            raise KitError(f"effect family lost members: {missing}")

    # ---- 5) 技能 DSL 两档
    programs: list[str] = []
    skill_gates: dict[str, Any] = {}
    for level in ("1", "2"):
        tree, gates = build_skill_tree(ctx, level)
        gates["design"] = check_design_tree(design, level, tree)
        gates["effects_before"] = sorted(effect_paths(tree))
        if family is not None:
            tree, info = ctx.rewrite_effect_refs(tree, family, strict=True)
            gates["effect_rewrites"] = info["rewritten"]
        gates["effects_after"] = sorted(effect_paths(tree))
        foreign = {p for p in gates["effects_after"]
                   if not p.startswith((FX_SRC_DIR + "/", FX_DST_DIR + "/"))}
        if foreign:
            raise KitError(f"skill {level} references unexpected effects: {sorted(foreign)}")
        problems = _dsl_problems(tree)
        if problems:
            raise KitError(f"skill {level} DSL gates failed: {problems}")
        programs.append(_write_dsl_checked(ctx, ctx.program_path(level), tree))
        skill_gates[level] = gates

    # ---- 6) 语音路由（kind 0 HpHigh 0.5，设计 D-3）+ character 行
    design_route = design.get("voice", {}).get("route")
    if not isinstance(design_route, dict) or int(design_route.get("kind", -1)) != VOICE_ROUTE["kind"] \
            or str(design_route.get("threshold")) != VOICE_ROUTE["threshold"]:
        raise KitError(f"design voice route drift: {design_route}")
    route = KL.voice_route(CODE, VOICE_ROUTE)
    char_row = ctx.pack.pkg_character_row()
    char_row[9:17] = route
    if char_row[6] != str(PF_TYPE) or char_row[26] != STANCE or char_row[27] != str(CID):
        raise KitError(f"character row drift: c6={char_row[6]} c26={char_row[26]} c27={char_row[27]}")
    ctx.write_flat(KL.CHARACTER, {str(CID): [char_row]})
    voice_ready = KL.write_voice_ready(ctx)

    # ---- 7) 像素成品（缺文件静默跳过）+ 三层镜像
    pixel = KL.install_staged_assets(ctx)
    mirrors = ctx.sync_character_mirrors()
    if mirrors["character"][9:17] != route:
        raise KitError("character mirror lost the voice route")

    ctx.evidence_write("kit-gates.json", {
        "leader": {"rows": leader_rows, "evidence": leader_evidence},
        "ability": {"rows": ability_rows, "evidence": ability_evidence},
        "during_puller_checked": pullers, "resonance_checked": resonance,
        "self_trigger_checked": self_trigger,
        "custom_ability_string": strings,
        "skills": skill_gates, "action_skill": action_rows,
        "effects": {"mode": "clone+lut" if family else "official-reference",
                    "src_dir": FX_SRC_DIR, "dst_dir": FX_DST_DIR if family else None,
                    "members": list(FX_MEMBERS), "fx_lut": str(lut_path), "applied": bool(lut)},
        "voice_route": route, "voice_ready": voice_ready,
        "pixel": pixel, "mirrors": mirrors,
    })

    energy = design["plan"]["skills"]["energy"]
    notes = [
        "技能『星之猎手』：官方朝户八重 psychic_gal 箭雨整树（停球 / FindNearSubjects(49) / "
        "6 支箭演出 / 移动矩形 300×200・寿命 120・最小间隔 3・最多 4 段全部不动）+ 四处逐格改："
        "S1 CNA 第 4 参 [[\"DCParalysis\"]]（对麻痹敌人 +25%，官方雷弓形状）、S2 倍率 "
        f"lv1 {SKILL_VALUES['1']['cna'][0]} / lv2 {SKILL_VALUES['2']['cna'][0]}"
        f"（两档都拉平成满级单值，4 段封顶 ⇒ SLv2 满级 {SKILL_TOTAL_LV2:g}×）、"
        "S3 命中块追加麻痹 / 迟缓 / 累积全属性抗性↓ 三条 CreateCondition（整句取自官方 "
        "bee_girl・elf_archer・devil_clown_xm21，只改帧数/数值/绑定）、S4 换尾成母本 151081 的"
        "「光属性队友技伤状态」、S5 麻痹 / 迟缓外包 ConditionalsChangeSkillFlag(1)（536 开着 ⇒ "
        f"麻痹 {SKILL_VALUES['2']['paralysis_long'][1]} 帧 / 迟缓 "
        f"{SKILL_VALUES['2']['frozen_long'][1]} 帧）；tree[10]=0 保持（自动档＝技能伤害归属）；能量 "
        f"{energy['donor']} → lv1 {energy['lv1']} / lv2 {energy['lv2']}",
        f"抗性↓ 元素码写 {TOLERANCE_ELEMENT_ALL}（ALL，解析后 = 0）而不是 5：带 "
        "resistElementResistance 旗的 boss 只放行「解析后 = 0」与「克制自身属性」的那一支，"
        "写 5/255 会被静默吃掉（设计 R-1，金丝雀 C-3 专验）。文案照写「全属性抗性降低」。",
        "麻痹/迟缓/抗性↓ 的 forceApply 一律 false（裁决 §2：不对 boss 强制付与）；"
        "付与对象种类 = 3（命中块内官方写法）；三条都绑在 CNA 同一主体位（判定区第三绑定位，"
        "写第二位必崩 U_34c3bb）。",
        "面板（rework1）：队长 4 行与能力 5／6 继续走客户端自渲染（desc_expected 逐字核对通过）；"
        f"能力 {'/'.join(str(s) for s in OVERRIDE_SLOTS)} 四个槽走 desc_override_<string_id> 整块接管，"
        "逐行 = rework1/panel/thorn.json（主位限定槽每行自带 <icon id='main'>）。无 629/722/422/724/713；"
        f"required_capabilities = [{L.PANEL_OVERRIDE_V2}]（缺 V14 不崩，只是回落到自动文案）。",
        f"「光属性共鸣时」一律用官方共鸣前置 {RESONANCE_CELLS}（作者 09-21 00:5x），"
        f"覆盖 {len(RESONANCE_ROWS)} 条行：{resonance}。",
        f"「自身发动技能时」三行触发方一律自身 {SELF_TRIGGER_CELLS}（平衡第二批 2026-09-27：#1/#2 由 "
        f"donor 的 c28=7 全队合计 + White 改成自身，同母本 1510813#2 写法）：{self_trigger}。",
        {"pixel_install": pixel},
    ]
    deviations: list[dict[str, Any]] = []
    for entry in design.get("deviations", ()):
        want = entry.get("orig") or entry.get("planned") or entry.get("原设想") or entry.get("want")
        got = entry.get("actual") or entry.get("实际落法") or entry.get("got")
        why = entry.get("why") or entry.get("原因")
        if not (want and got and why):
            raise KitError(f"design deviation is missing 原设想/实际落法/原因: {entry}")
        deviations.append({"id": entry.get("id"), "want": want, "got": got, "why": why})

    gate = {"rows": len(leader_evidence) + len(ability_evidence), "programs": len(programs),
            "fx_mode": "clone+lut" if family else "official-reference",
            "pixel_present": pixel["present"],
            "pixel_missing": [e["logical"] for e in pixel["skipped"]]}
    ready = pixel["present"] and not pixel["skipped"]
    gate["reason"] = "kit 自有产物全部过闸" if ready else (
        f"像素成品未就绪：{gate['pixel_missing'] or 'B/pixel/thorn/install.json 不存在'}")

    return KL.report(
        ctx, summary="索恩：光属性技伤辅助（一次施技挂满 5 个弱体 → 队长/词条按弱体数换算全队光属性特攻与技伤）",
        status=KL.READY if ready else KL.DRAFT, panel=panel, notes=notes, programs=programs,
        required_capabilities=sorted(capabilities), deviations=deviations,
        extra={"effect_families": [FX_DST_DIR] if family else [],
               "effect_mode": gate["fx_mode"], "kit_gate": gate, "voice_route": route,
               "balance": design.get("balance", {})})
