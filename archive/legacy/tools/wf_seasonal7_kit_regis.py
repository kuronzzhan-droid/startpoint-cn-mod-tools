# -*- coding: utf-8 -*-
"""季节换装七角色 kit：雷吉斯·海滨 139994 ``rec_android_seaside``。

**基准 = 三层**：身份/语音路由/能量/基线技能树仍取上一轮定稿 ``design/regis.json``；
行方案、面板文案、固有状态、技能说明与倍率取 2026-09-16 作者改版的
``revision-20260916/regis/plan.json``（``design/`` 本轮不可写，不回写设计稿）；
第二轮（2026-09-16 晚，作者真机试玩后）的两处改动以模块常量 ``REV2_*`` 叠在 plan 之上
（:func:`apply_revision2`）——**能力 1 加主位限制**（整键 c1='false'，面板逐行补
``<icon id='main'>``）与**文案规则①**（面板不再出现「无上限」，没有上限就什么都不跟）；
规则②（能力里的技能强化条目不写数字与时间）在本角色空过，由 :func:`rev2_skill_flag_problems`
钉死「本角色没有 ChangeSkillFlag 行」。规则原文见 ``revision2-20260916/文案规则-补充.md``。

由 ``python mod-tools/wf_seasonal7_build.py --char regis --step kit`` 调用 :func:`build`。
只写 ``work/character_packs/s7-regis/``（经 KitContext）；live store / assets / .cdn / src 只读。

落地内容（全部以设计 JSON 为准，逐项断言）：
- character 行 c9–c16 语音路由、c18 队长名；character_text 12 列；三层镜像；
- 队长 6 行、词条 6 键 16 条：按 donor（官方基线 / live）+ 声明编辑重建，与改版方案
  ``row_built`` 逐格核对，``wf_describe`` 读回的中文也要与方案登记的 ``describe`` 逐字相同；
- 固有状态「浪涌充能」``13999401``（官方 donor 2「带电」，上限 99 = 无上限、入棺不清除）
  与它的 48×48 图标（存储态 PNG，alpha = 官方图标外框）；一个计数器四处消费：
  词条 1399941#2 产（461 每次进 Fever +1 层），队长 L0/L1、词条 1399943#3/#4（during 134）
  与两棵技能树的 ``BindConditionAccumulationVariable`` + ``vlv`` 消费；
- custom_ability_string 7 条 ``desc_override_*``（panel-description-override-v2）；
- action_skill 两档（名称/描述/能量 c4–c6）；upskill 09-16 版曾把 ``skill_damage_up`` 换成
  ``ability_damage_up``（技能删 ACSkillDamage、加 ACAbilityDamage，与官方夏日莉莉丝 151045 同写法），
  2026-09-27 平衡批次恢复母本 ``skill_damage_up``；
- **2026-09-27 平衡批次**（作者确认「能力相关都换成技能伤害」）：浪涌修订之后调用
  ``wf_balance_20260927_regis``（:func:`balance_rows` / :func:`balance_panel` / ``balance.skill_tree``），
  另写能力 2 的 629 全体追击 DSL 与文案键 ``rec_android_seaside_skill_strike``；批次暂存脚本的
  ``revise()`` 用同一组函数，kit 重跑与候选一致；
- **2026-09-27 平衡第二批**（口径 A：无上限成长）：第一批之后再调用 ``wf_balance_20260927b_regis``
  （:func:`balance_b_rows` / :func:`balance_b_panel` / ``balance_b.skill_tree`` / ``balance_b.description``）：
  队长每层成长放缓 1/5 并收下能力 3 的两条自身逐层行（7→9 行），能力 3 两行改为每层 30%、最多 5 层，
  两棵技能树的浪涌层数绑定上限 99→5，技能描述加「（最多5层）」；
- **2026-09-27 平衡第三轮（c）**（成长复核 + 技能倍率撤封顶）：第二批之后再调用 ``wf_balance_20260927c_regis``
  （:func:`balance_c_rows` / :func:`balance_c_panel` / ``balance_c.skill_tree`` / ``balance_c.description``）：
  队长四条每层成长改为原值 4/5（120/80/120/120%），队长追加 536 旗号 1 行（雷共鸣，9→10 行）与文案键
  ``change_skill_rec_android_seaside_leader``；两棵技能树 ≥5 层档按 ``ConditionalsChangeSkillFlag(1)`` 分两支
  （开支上限 99.0、关支保留第二批 5.0）；队长面板同步（强化条目「强化『浪花爆破』：…」= ``balance_c.FLAG_TEXT``；
  技能描述保持第二批「（最多5层）」，强化后的不封顶只写在队长面板，``balance_c.description`` 只核对不改；暂存前最后一轮：
  队长面板「非FEVER / FEVER 冲刺时FEVER槽」一行按数据条件拆两行，``balance_c.SPLIT_LINES_AFTER``，
  由 ``balance_c.panel_text`` 带出）。两支复用同一组绑定号（互斥执行），
  :func:`blueprint_check_with_sig` 的「绑定 id 重复」对旗号两支按分支计数；
- 两棵技能 DSL：官方 131020 骨架 + ★4 231003 光束 + 151045 雷队能力伤害状态（移植
  design/_tmp/regis/d09_compose_final.py），特效引用经 ``rewrite_effect_refs`` 改写，
  先与上一轮定稿树逐节点严格比对；再叠改版增量 D1–D5（两分支各一条 Bind、
  倍率 38×/54×（内层 1）与 50→55×/65→75×（内层 2）、每层固有 +10 倍），
  再与改版参考树 ``revision-20260916/regis/final_rec_android_seaside_{level}.json`` 逐节点比对；
- 两个特效族克隆（``seaside_beam`` / ``seaside_ray``，layout=codename）；按
  ``seasonal7-20260916/fx/regis/out/manifest.json`` 的 {源 sheet 逻辑路径 → 染色 PNG} 替换 sheet，
  写后逐像素核对包内 sheet = 染色 PNG、alpha = 母本（设计 §5 要求两张都换色）；
- switched_action_skill ``rec_android_seaside_voice_ready`` 两档（= action_skill c7–c23，
  与 ``wf_seasonal7_voice.switched_rows`` 同约定）；
- 像素小人（Integrate）：``seasonal7-20260916/pixel/regis/out/{sprite_sheet,special_sprite_sheet}.png``
  在 report 门禁全过、``pixel/_review/verify_all.json`` 复核全过且 sha 一致时，以存储态写入
  ``character/<code>/pixelart/``（owner=pixel），写后核对尺寸/alpha = 母本、元数据 = 母本（仅路径前缀）；
  未就绪时不写。语音由 ``impl/regis/voice_merge.py``（``wf_seasonal7_voice pack``）装包，kit 只读报告状态。

kit-report 的 ``status``：只有 ``impl/regis/gates.json`` 全过、其 ``kit_fingerprint`` 与本次产物
指纹一致、且两张特效 sheet 都已按 fx manifest 换色时才写 ``ready-for-review``，否则 ``draft``
（门禁脚本 ``impl/regis/gates.py``）。指纹含特效 sheet 字节与 fx manifest/染色 PNG 的 sha256：
kit 跑完后染色产物才出现或被重做，重算指纹即与 kit-report / gates.json 不一致。

未跟踪输入（``work/`` 被 .gitignore 排除；干净检出须先恢复 seasonal7-20260916 批目录，
build 开头统一检查并报清单）：``design/regis.json``、``design/_tmp/regis/final_rec_android_seaside_{1,2}.json``、
``revision-20260916/regis/plan.json``、``revision-20260916/regis/final_rec_android_seaside_{1,2}.json``、
``research/_tmp/official_sig.json``（官方全库参数形状表，``research/_tmp/official_sig.py`` 生成）、
``fx/regis/out/``（缺失时不报错，只把 status 压成 draft）。设计期静态校验
（``research/_tmp/blueprint_build.check``）已移植为本模块 :func:`blueprint_check`，不再运行时 import。
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    pass  # Imports resolve from this checkout/package, not external source copies.

import wf_balance_20260927_regis as balance  # noqa: E402  纯函数、只依赖标准库
import wf_balance_20260927b_regis as balance_b  # noqa: E402  第二批（无上限成长），叠在第一批之后
import wf_balance_20260927c_regis as balance_c  # noqa: E402  第三轮（成长 4/5 + 技能撤封顶），叠在第二批之后

KEY = "regis"
CID = "139994"
CODE = "rec_android_seaside"
ELEMENT = 2
BATCH = "work/character_packs/seasonal7-20260916"
DESIGN_REL = f"{BATCH}/design/regis.json"
DESIGN_TREE_REL = BATCH + "/design/_tmp/regis/final_rec_android_seaside_{level}.json"
REVISION_DIR = f"{BATCH}/revision-20260916/regis"
REVISION_REL = f"{REVISION_DIR}/plan.json"
# 第二轮（作者 2026-09-16 晚）：只有文案规则与两处增量，没有新的机器可读方案文件；
# 规则原文在这里，增量以模块常量 REV2_* 表达（plan.json 属第一轮证据，本轮不可写）。
REVISION2_DIR = f"{BATCH}/revision2-20260916/regis"
REVISION2_RULES_REL = f"{BATCH}/revision2-20260916/文案规则-补充.md"
REV_TREE_REL = REVISION_DIR + "/final_rec_android_seaside_{level}.json"
FX_MANIFEST_REL = f"{BATCH}/fx/regis/out/manifest.json"
GATES_REL = f"{BATCH}/impl/regis/gates.json"
OFFICIAL_SIG_REL = f"{BATCH}/research/_tmp/official_sig.json"

CHAR = "master/character/character.orderedmap"
TEXT = "master/character/character_text.orderedmap"
ABILITY = "master/ability/ability.orderedmap"
LEADER = "master/ability/leader_ability.orderedmap"
CAS = "master/string/custom_ability_string.orderedmap"
ACTION = "master/skill/action_skill.orderedmap"
SW = "master/skill/switched_action_skill.orderedmap"
UPSKILL = "master/mana_board/upskill.orderedmap"
UNIQUE = "master/character/unique_condition.orderedmap"
VOICE_KEY = f"{CODE}_voice_ready"

# 改版新增固有状态「浪涌充能」（revision plan §3）：donor = 官方 2「带电」unique_girl_and_mecha
UID = "13999401"
UNIQUE_NAME = "浪涌充能"
UNIQUE_DONOR = "2"
ICON_ROW_PATH = f"battle/common/unique_condition/unique_{CODE}_surge"
ICON_LOGICAL = ICON_ROW_PATH + ".png"
ICON_FRAME_DONOR = f"battle/common/unique_condition/unique_girl_and_mecha.png"

CAS_KEYS = (f"desc_override_{CODE}", *[f"desc_override_{CODE}_{i}" for i in range(1, 7)])
CAPABILITIES = ("kyubi-fever-ratio-v1", "panel-description-override-v2")

EFFECT_FAMILIES = (
    # (源目录, 目标子目录, 基名) —— 设计 effects.clone
    ("battle/effect/skill_unique/rec_android_1anv", "seaside_beam",
     ("rec_android_1anv_beam", "rec_android_1anv_beam_hit", "rec_android_1anv_beam_player",
      "rec_android_1anv_beam_shadow", "rec_android_1anv_laser", "rec_android_1anv_charge",
      "rec_android_1anv_charge_back")),
    ("battle/effect/skill_unique/rec_android", "seaside_ray", ("rec_android",)),
)

# 设计 §4 倍率（[{min,max}]），与 d09_compose_final.LEVELS 相同
LEVELS = {
    "1": dict(fever=[{"min": 3.8, "max": 3.8}], laser=[{"min": 0.9, "max": 0.9}],
              ray=[{"min": 2.0, "max": 2.0}], abd=[{"min": 1.0, "max": 1.0}]),
    "2": dict(fever=[{"min": 4.5, "max": 5.0}], laser=[{"min": 1.25, "max": 1.4}],
              ray=[{"min": 2.6, "max": 2.8}], abd=[{"min": 1.25, "max": 1.5}]),
}
# 改版倍率（revision plan §6 / skill_dsl.edits D1–D5）：单段 min/max，×10 段 = 面板倍数。
# 通常 = 激光 12 + 光束 26（内层 1）/ 16→18 + 34→37（内层 2）= 38× / 50→55×；Fever = 54× / 65→75×。
REV_LEVELS = {
    "1": dict(fever=(5.4, 5.4), laser=(1.2, 1.2), ray=(2.6, 2.6)),
    "2": dict(fever=(6.5, 7.5), laser=(1.6, 1.8), ray=(3.4, 3.7)),
}
# 每层「浪涌充能」每段 +1.0 倍 ⇒ 10 段 = +10 倍/层；vlv = min + (max−min)×min(层数/除数, 上限)
# （ActionEvaluator:4877-4887 / Environment:291/319）。上限 99 与固有 c4 同值。
REV_GROWTH = 1.0
REV_VID = {"fever": 1, "ray": 2}
REV_DIVISOR, REV_CAP = 1, 99.0

SOURCE_PROGRAMS = {
    "skeleton": "battle/action/skill/action/rare5/rec_android_1anv$rec_android_1anv_{level}",
    "ray": "battle/action/skill/action/rare4/rec_android$rec_android_{level}",
    "smr21": "battle/action/skill/action/rare5/resistance_princess_smr21$resistance_princess_smr21_{level}",
}
# 设计记录的官方 deflate sha256（只登记了内层 1；内层 2 取官方基线并与定稿树比对）
SOURCE_SHA_L1 = {
    "skeleton": "14f6659eb98177f791bbd11e9fab3dac6fc88057f8c3b87557a86b81a318b88f",
    "ray": "53783e54097edcd47882cfc3899594b3f91d86802b7a80e1e9e8c2234b483ac2",
    "smr21": "c6b561867bb2d30e2ea5f6ef1a997b40f4c7d5caa5877457bc1304527488face",
}

# 覆盖文案禁词（记忆卡 wf-leader-override-text-rules / wf-no-hplow-text-discipline
# + 作者 2026-09-16 晚文案规则①：面板不再出现「无上限」，也不许换成「可无限叠加」之类的替代说法）
FORBIDDEN_PANEL_WORDS = ("自身为队长时", "觉醒后", "生命值100%以下", "HP100%以下", "null",
                         "无上限", "无限叠加", "不设上限", "可无限")

# ─────────── 第二轮作者改版（2026-09-16 晚）：以声明式增量叠在 plan.json 上 ───────────
#
# plan.json 在第一轮证据目录 revision-20260916/ 下，本轮不可写；所以第二轮的两处改动写成
# 增量，叠加后仍然要过 plan 的「donor + edits 重算 == row_built」与 wf_describe 零漂移。
#
# (1) 作者原话「雷吉斯能1带上主位限制」：能力 1 = 整键 values[0] 的 c1='false'
#     （``get_unisonable()`` 只读 values[0]，且 build_rows 要求同键 c1 一致 ⇒ 三条同改）。
#     不额外加前置 202：c1=false 与 202 同键双写会画两个 Ⓜ（记忆卡 wf-unison-slot-mechanics）。
#     面板 Ⓜ 是客户端逐行画的，但本包的面板文字被 desc_override 整段替换 ⇒ 覆盖文本必须自带
#     ``<icon id='main'>``，与本来就是主位键的能力 3 同写法。
# (2) 文案规则（revision2-20260916/文案规则-补充.md）：
#     ① 没有上限就什么都不跟 —— 删「（无上限）」，句子写到效果为止（机制不动：固有上限仍是 99）；
#     ② 能力里的「技能强化」条目不写数字与时间 —— plan 行里没有 ChangeSkillFlag(536/704) 行，
#        规则②在 plan 层空过（断言见 :func:`rev2_skill_flag_problems`）；2026-09-27 第三轮 c 层在队长表
#        追加的 536 行，其文案键由 ``balance_c.panel_problems``（skill_flag=True）按规则②把关。
MAIN_ICON = " <icon id='main'>  "
REV2_MAIN_SLOT_SLOTS = (1, 3)          # 主位限制的词条槽（3 是上一轮就有的，1 是本轮新加）
REV2_TEXT_DROPS = ("（无上限）",)       # 规则①：整段删掉，不替换成别的说法
SKILL_FLAG_KINDS = ("536", "704")      # ChangeSkillFlag：规则②针对的「技能强化」条目

# 改版 T1「角色技能描述不再写太复杂省略一下」：两档 c1 与 character_text c5/c7 同文（3 行）。
# 1.4.868 上线版是【通常】/【FEVER状态中】分段的 3 行共 130 字；这里压成 3 行短句共 104 字。
# 第 2 行必须把树里真实赋予的三个增益都点到（见 SKILL_DESC_EFFECTS）：技能强化预览页读的是
# upskill 行的标签（condition_attack_up / condition_add_fever_point_up / ability_damage_up），
# 说明里漏写会和预览页对不上（审查 20260916 minor 7）。
SKILL_DESC = ("向最近的敌人释放激光炮与光束，造成雷属性伤害（FEVER模式中威力提升）\n"
              "发动时赋予雷属性角色能力伤害提升效果；非FEVER时追加自身攻击力提升与FEVER槽增加\n"
              "伤害以能力伤害判定；每层「浪涌充能」威力＋10倍")

# 技能树里的效果 → (说明里必须出现的词, upskill 预览标签)。三者必须同进同退：
# 树里有 → 说明必须提到 → upskill 必须挂标签；upskill 挂了标签 → 树里必须真有。
SKILL_DESC_EFFECTS = {
    "ACAbilityDamage": ("能力伤害", "ability_damage_up"),
    "ACAttackPoint": ("攻击力", "condition_attack_up"),
    "AddFeverPoint": ("FEVER槽", "condition_add_fever_point_up"),
    # 2026-09-27 平衡批次（wf_balance_20260927_regis）：雷队增益改为 ACSkillDamage。
    # 旧项保留，老树/旧说明的三方核对仍然成立。
    "ACSkillDamage": ("技能伤害", "skill_damage_up"),
}
# upskill 行里与技能效果无关、不参与上面三方核对的标签（倍率强化 / 空槽）
UPSKILL_IGNORED_TAGS = ("common_attack_up", "(None)", "")

TEXTS = {
    "title": "海滨约会的白花机人",
    "profile": ("为了一场海边约会，特意换上白礼服与草帽的机人绅士。花形浮游机替他捕捉浪花里的光，"
                "白伞总是先倾向身旁的人。他自称此行只为记录人类的休日文化——至于记录里为何总有同一个人的笑容，"
                "想必又是另一桩计谋。"),
    "leader": "约会纪念模式",
    "skill1": "浪花爆破",
    "desc1": SKILL_DESC,
    "skill2": "浪花爆破＋",
    "desc2": SKILL_DESC,
    "cv": "AI 合成配音",
}

SPEC = {
    "required_capabilities": CAPABILITIES,
    # 2026-09-27：能力 2 的 629 文案键（balance.STRIKE_KEY）也由本包认领，漏认领 = rebase 静默回滚 + C8601；
    # 第三轮 c：队长 536 行的文案键（balance_c.FLAG_KEY）同理
    "extra_keys": {CAS: (*CAS_KEYS, balance.STRIKE_KEY, balance_c.FLAG_KEY), SW: (VOICE_KEY,), UNIQUE: (UID,)},
}


class KitError(RuntimeError):
    pass


# ---------------------------------------------------------------- 纯函数

def strict_equal(a: Any, b: Any) -> bool:
    """树逐节点比较：bool/int/float 类型也必须一致（AMF3 int 与 double 编码不同）。"""
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    if isinstance(a, (int, float)) or isinstance(b, (int, float)):
        return type(a) is type(b) and a == b
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(strict_equal(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(strict_equal(a[k], b[k]) for k in a)
    return type(a) is type(b) and a == b


def first_difference(a: Any, b: Any, path: str = "$") -> str | None:
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return f"{path}: len {len(a)} != {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            d = first_difference(x, y, f"{path}[{i}]")
            if d:
                return d
        return None
    if isinstance(a, dict) and isinstance(b, dict):
        if a.keys() != b.keys():
            return f"{path}: keys {sorted(a)} != {sorted(b)}"
        for k in a:
            d = first_difference(a[k], b[k], f"{path}.{k}")
            if d:
                return d
        return None
    return None if strict_equal(a, b) else f"{path}: {a!r} != {b!r}"


def cmd(node):
    return node[1] if isinstance(node, list) and node and node[0] == "Command" else None


def iter_commands(node, name: str | None = None):
    """深度优先枚举 ``["Command", [name, ...]]`` 的参数表。"""
    if isinstance(node, list):
        if node and node[0] == "Command" and len(node) == 2 and isinstance(node[1], list):
            if name is None or node[1][0] == name:
                yield node[1]
        for child in node:
            yield from iter_commands(child, name)
    elif isinstance(node, dict):
        for child in node.values():
            yield from iter_commands(child, name)


def first_cna(block) -> list:
    for x in block[1]:
        c = cmd(x)
        if c and c[0] == "CreateNormalAttack":
            return c
    raise KitError("no CreateNormalAttack in onHit block")


def hits_by_formula(cha: list) -> int:
    life, n = cha[13][1], cha[14][1]
    interval = life / (n - 0.5)
    return math.floor((life - 1e-9) / interval) + 1


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_design(root: Path) -> dict:
    design = json.loads((root / DESIGN_REL).read_text(encoding="utf-8"))
    if design.get("status") != "final" or design.get("key") != KEY:
        raise KitError(f"design not final for {KEY}: status={design.get('status')}")
    ident = design["identity"]
    if (ident["cid"], ident["code"], ident["element"]) != (CID, CODE, ELEMENT):
        raise KitError(f"design identity mismatch: {ident['cid']}/{ident['code']}")
    return design


def load_revision(root: Path) -> dict:
    """改版方案 ``revision-20260916/regis/plan.json``（作者 2026-09-16 要求的机器可读版）。

    上一轮的 ``design/regis.json`` 仍然是身份/语音/能量/基线技能树的来源；
    行方案（队长 6 行、词条 16 条）、面板文案、固有状态、技能说明改由本文件定。
    ``design/`` 不在本轮可写范围，所以不回写设计稿。"""
    plan = json.loads((root / REVISION_REL).read_text(encoding="utf-8"))
    if (plan.get("key"), plan.get("cid"), plan.get("code")) != (KEY, CID, CODE):
        raise KitError(f"revision plan identity mismatch: {plan.get('key')}/{plan.get('cid')}/{plan.get('code')}")
    if plan.get("stage") != "design":
        raise KitError(f"revision plan stage unexpected: {plan.get('stage')}")
    return plan


def rev2_main_slot_cas_keys() -> tuple[str, ...]:
    """主位限制词条槽对应的面板覆盖键（这些键的每一行都要自带 ``<icon id='main'>``）。"""
    return tuple(CAS_KEYS[i] for i in REV2_MAIN_SLOT_SLOTS)


def rev2_panel_text(key: str, text: str) -> str:
    """第二轮文案变换：规则①删「（无上限）」；主位键每行补 ``<icon id='main'>``（已有则不重复）。"""
    for drop in REV2_TEXT_DROPS:
        text = text.replace(drop, "")
    if key in rev2_main_slot_cas_keys():
        text = "\n".join(line if line.startswith(MAIN_ICON) else MAIN_ICON + line
                         for line in text.split("\n"))
    return text


def rev2_skill_flag_problems(kind: str, row: list[str]) -> list[str]:
    """规则②的空过断言：本角色不得出现 ChangeSkillFlag(536/704) 的「技能强化」条目。

    真有这类行时，文案只能写「强化『<技能名>』的效果」，不写数值与秒数；本角色一条都没有，
    所以这里直接把「没有」钉死——将来谁加了这类行，门禁会提醒去按规则②写文案。"""
    cols = (47, 109) if kind == "ability" else (45, 107)
    return [f"{kind} row uses ChangeSkillFlag kind {row[c]!r} at c{c}: 文案必须按规则②只写强化了什么"
            for c in cols if c < len(row) and row[c] in SKILL_FLAG_KINDS]


def apply_revision2(slots: dict[str, list], custom: list[dict]) -> dict[str, Any]:
    """把第二轮的两处改动叠到 plan 解析结果上（就地改），返回可写进 kit-report 的证据。"""
    ability_edits: dict[str, str] = {}
    for slot in REV2_MAIN_SLOT_SLOTS:
        key = f"{CID}{slot}"
        entries = slots.get(f"slot{slot}")
        if not entries:
            raise KitError(f"revision2 main-slot slot{slot} missing")
        for entry in entries:
            entry["edits"] = dict(entry["edits"]) | {"1": "false"}
            row = list(entry["row_built"])
            row[1] = "false"
            entry["row_built"] = row
        ability_edits[key] = "c1=false"
    text_changes = {}
    for item in custom:
        before = item["text"]
        item["text"] = rev2_panel_text(item["key"], before)
        if item["text"] != before:
            text_changes[item["key"]] = {"dropped": [d for d in REV2_TEXT_DROPS if d in before],
                                         "main_icon": item["key"] in rev2_main_slot_cas_keys()}
    probs = [f"{item['key']}: {p}" for item in custom for p in panel_text_problems(item["text"])]
    if probs:
        raise KitError(f"revision2 panel text still has forbidden words: {probs}")
    return {"main_slot_ability_keys": ability_edits, "panel_text_changes": text_changes,
            "main_slot_cas_keys": list(rev2_main_slot_cas_keys())}


def main_slot_panel_problems(ability_rows: dict[str, list[list[str]]],
                             cas_rows: dict[str, list[list[str]]]) -> list[str]:
    """词条键的 c1（主位限制）与它的覆盖文案是否一致：c1=false ⇔ 每行都带 ``<icon id='main'>``。

    面板 Ⓜ 本来由客户端逐行画，但 desc_override 把整段文字换掉了，所以图标要写进文本；
    两边错位 = 面板上「有 Ⓜ 没限制」或「有限制没 Ⓜ」。"""
    probs = []
    for slot in range(1, 7):
        key = f"{CID}{slot}"
        lines = ability_rows.get(key)
        if not lines:
            continue
        cas_key = CAS_KEYS[slot]
        text_cells = cas_rows.get(cas_key)
        if not text_cells:
            probs.append(f"{cas_key} missing")
            continue
        main_only = lines[0][1] == "false"
        want = slot in REV2_MAIN_SLOT_SLOTS
        if main_only != want:
            probs.append(f"ability {key} c1={lines[0][1]!r} but revision2 expects main_only={want}")
        text_lines = text_cells[0][0].split("\n")
        tagged = [ln.startswith(MAIN_ICON) for ln in text_lines]
        if main_only and not all(tagged):
            probs.append(f"{cas_key}: main-slot ability but {tagged.count(False)} line(s) lack {MAIN_ICON!r}")
        if not main_only and any(tagged):
            probs.append(f"{cas_key}: not a main-slot ability but carries {MAIN_ICON!r}")
    return probs


# ─────────── 2026-09-27 平衡批次：能力相关换成技能伤害（叠在浪涌修订之后） ───────────
#
# 转换本体在 ``wf_balance_20260927_regis``（批次暂存脚本的 revise() 用同一组函数），
# kit 只按固定顺序调用：plan → 第二轮 → 浪涌（wf_regis_surge_stages）→ 本批。
# 所以 kit 重跑的产物 == revise() 的产物，不会把候选退回能力伤害版。

def balance_rows(leader: list[list[str]], ability: dict[str, list[list[str]]]):
    """队长 154→2、144→23；能力 2 253→629、能力 3 412→411/144→23/154→2/删自身 411、能力 5 388→34。"""
    ability = dict(ability)
    ability[CID + "2"] = balance.strike_rows(ability[CID + "2"])
    ability[CID + "3"] = balance.third_rows(ability[CID + "3"])
    ability[CID + "5"] = balance.fifth_rows(ability[CID + "5"])
    leader = balance.leader_rows(leader)
    probs = balance.row_problems("leader_ability", leader)
    for key in (CID + "2", CID + "3", CID + "5"):
        probs += [f"{key}: {p}" for p in balance.row_problems("ability", ability[key])]
    if probs:
        raise KitError(f"balance 20260927 row legality problems: {probs}")
    return leader, ability


def balance_b_rows(leader: list[list[str]], ability: dict[str, list[list[str]]]):
    """第二批：队长 #0/#1 每层 1/5、能力 3#3/#4 搬入队长（#7/#8，1/5）并原位改为最多 5 层。
    只接受第一批输出（:func:`balance_rows` 之后调用）；门禁在 ``balance_b.growth_rows`` 内部。"""
    ability = dict(ability)
    try:
        leader, ability[CID + "3"] = balance_b.growth_rows(leader, ability[CID + "3"])
    except ValueError as exc:
        raise KitError(f"balance 20260927b rows: {exc}") from exc
    return leader, ability


def balance_b_panel(cas_rows: dict[str, list[list[str]]]) -> dict[str, list[list[str]]]:
    """第二批：队长 / 能力 3 覆盖文案换成放缓后的数值（:func:`balance_panel` 之后调用）。"""
    missing = sorted(set(balance_b.PANEL_BEFORE) - set(cas_rows))
    if missing:
        raise KitError(f"balance 20260927b panel keys missing: {missing}")
    out = {key: ([[balance_b.panel_text(key, cells[0][0])]] if key in balance_b.PANEL_BEFORE else cells)
           for key, cells in cas_rows.items()}
    probs = [f"{key}: {p}" for key, cells in out.items() for p in panel_text_problems(cells[0][0])]
    if probs:
        raise KitError(f"balance 20260927b panel text has forbidden words: {probs}")
    return out


def balance_c_rows(leader: list[list[str]], ability: dict[str, list[list[str]]]):
    """第三轮 c：队长四条逐层成长 → 原值 4/5，追加 536 旗号 1 行（雷共鸣）。只接受第二批输出
    （:func:`balance_b_rows` 之后调用）；旗号 1 空闲核对（``ability`` 各键无 536/704–708）与门禁在
    ``balance_c.leader_rows`` 内部。能力行不动（口径 D4）。"""
    try:
        leader = balance_c.leader_rows(leader, ability)
    except ValueError as exc:
        raise KitError(f"balance 20260927c rows: {exc}") from exc
    return leader, dict(ability)


def balance_c_panel(cas_rows: dict[str, list[list[str]]]) -> dict[str, list[list[str]]]:
    """第三轮 c：队长覆盖文案换成 4/5 数值、插入技能强化行，并把「；」挤两种数据条件的冲刺 FEVER 槽行拆成两行（口径 5）；
    追加 536 行文案键（:func:`balance_b_panel` 之后调用）。技能强化文案按规则②不写数字与时间。"""
    key = balance_c.PANEL_LEADER
    if key not in cas_rows:
        raise KitError(f"balance 20260927c panel key missing: {key}")
    if balance_c.FLAG_KEY in cas_rows:
        raise KitError(f"balance 20260927c flag text key already present: {balance_c.FLAG_KEY}")
    out = dict(cas_rows)
    try:
        out[key] = [[balance_c.panel_text(key, cas_rows[key][0][0])]]
    except ValueError as exc:
        raise KitError(f"balance 20260927c panel: {exc}") from exc
    out[balance_c.FLAG_KEY] = [[balance_c.FLAG_TEXT]]
    probs = [f"{k}: {p}" for k, cells in out.items() for p in panel_text_problems(cells[0][0])]
    probs += [f"{k}: {p}" for k in (key, balance_c.FLAG_KEY) for p in balance_c.panel_problems(k, out[k][0][0])]
    if probs:
        raise KitError(f"balance 20260927c panel text problems: {probs}")
    return out


def balance_panel(cas_rows: dict[str, list[list[str]]]) -> dict[str, list[list[str]]]:
    """4 个覆盖键换成技能伤害口径；追加能力 2 的 629 文案键。"""
    out = {key: ([[balance.panel_text(key, cells[0][0])]] if key in balance.PANEL_BEFORE else cells)
           for key, cells in cas_rows.items()}
    missing = sorted(set(balance.PANEL_BEFORE) - set(out))
    if missing:
        raise KitError(f"balance 20260927 panel keys missing: {missing}")
    out[balance.STRIKE_KEY] = [[balance.STRIKE_TEXT]]
    probs = [f"{key}: {p}" for key, cells in out.items() for p in panel_text_problems(cells[0][0])]
    if probs:
        raise KitError(f"balance 20260927 panel text has forbidden words: {probs}")
    return out


def revision_rows(plan: dict) -> dict:
    """plan.json → :func:`build_rows` 需要的形状（与上一轮 design 的 leader/abilities/
    custom_strings 同构），并顺手校对 plan 自声明的行数；最后叠第二轮改版增量
    （:func:`apply_revision2`：能力 1 主位限制 + 文案规则①）。"""
    la = plan["tables"]["leader_ability"]
    if la["table"] != LEADER:
        raise KitError(f"revision leader table {la['table']}")
    leader = []
    for e in sorted(la["rows"], key=lambda r: r["record"]):
        if e["key"] != CID:
            raise KitError(f"revision leader key {e['key']} != {CID}")
        leader.append({"id": f"L{e['record']}", "donor": e["donor"], "donor_table": e["donor_table"],
                       "row_index": e["donor_row_index"], "edits": e["edits"],
                       "row_built": e["row_built"], "describe": e["describe"]})
    if len(leader) != la["new_row_count"] or len(leader) != 6:
        raise KitError(f"revision leader row count {len(leader)} != {la['new_row_count']}")
    ab = plan["tables"]["ability"]
    if ab["table"] != ABILITY:
        raise KitError(f"revision ability table {ab['table']}")
    slots: dict[str, list] = {}
    total = 0
    for key, blk in ab["keys"].items():
        if not key.startswith(CID):
            raise KitError(f"revision ability key {key}")
        slot = int(key[len(CID):])
        entries = [{"key": e["key"], "record": e["record"], "donor": e["donor"],
                    "donor_table": e["donor_table"], "row_index": e["donor_row_index"],
                    "edits": e["edits"], "row_built": e["row_built"], "describe": e["describe"]}
                   for e in sorted(blk["rows"], key=lambda r: r["record"])]
        if len(entries) != blk["new_row_count"]:
            raise KitError(f"revision ability {key} count {len(entries)} != {blk['new_row_count']}")
        if [e["record"] for e in entries] != list(range(len(entries))):
            raise KitError(f"revision ability {key} records not 0..n")
        slots[f"slot{slot}"] = entries
        total += len(entries)
    if sorted(slots) != [f"slot{i}" for i in range(1, 7)]:
        raise KitError(f"revision ability slots {sorted(slots)}")
    cas = plan["tables"]["custom_ability_string"]
    custom = [{"table": cas["table"], "key": k, "capability": cas["capability"], "text": v}
              for k, v in cas["rows"].items()]
    unique = [{"table": u["table"], "key": u["key"], "donor": u["donor"], "edits": u["edits"],
               "row_built": u["row_built"], "icon": u["icon"]["logical_path"]}
              for u in plan["unique_conditions"]]
    desc = plan["tables"]["action_skill"]["changes"]["c1_description_both_levels"]
    rev2 = apply_revision2(slots, custom)
    return {"leader": leader, "abilities": slots, "ability_record_count": total,
            "custom_strings": custom, "unique_conditions": unique, "skill_desc": desc,
            "revision2": rev2}


def design_text_rows(design: dict, revision: dict) -> dict:
    """character_text 12 列 + action_skill 两档 c0/c1；技能说明（c5/c7、两档 c1）取改版短文。"""
    t = design["text"]
    desc = revision["skill_desc"]
    return {
        "character_text": [t["name"], t["furigana_c1"], t["profile_c2"], t["nickname_c3"],
                           t["skill1_name_c4"], desc, t["skill2_name_c6"], desc,
                           t["c8"], t["c9"], t["leader_name_c10"], t["cv_c11"]],
        "action": {lv: [v[0], desc] for lv, v in t["action_skill_c0_c1"].items()},
    }


def check_texts_constant(design: dict, revision: dict) -> list[str]:
    """模块常量 TEXTS 必须与设计一致（tables 重跑时靠 TEXTS 写 character_text / action_skill）；
    技能说明两条改与改版方案一致。"""
    t = design["text"]
    desc = revision["skill_desc"]
    want = {"title": t["nickname_c3"], "profile": t["profile_c2"], "leader": t["leader_name_c10"],
            "skill1": t["skill1_name_c4"], "desc1": desc, "skill2": t["skill2_name_c6"],
            "desc2": desc, "cv": t["cv_c11"]}
    probs = [f"TEXTS.{k} != design/revision" for k, v in want.items() if TEXTS.get(k) != v]
    if SKILL_DESC != desc:
        probs.append("SKILL_DESC != revision plan action_skill c1")
    # 技能说明也是玩家可见文案，同样吃第二轮规则①（没有上限就什么都不跟）
    probs += [f"SKILL_DESC: {p}" for p in panel_text_problems(SKILL_DESC)]
    if design["text"]["name"] != "雷吉斯" or design["text"]["furigana_c1"] != "LEIJISI":
        probs.append("design name/furigana differs from spec")
    return probs


def panel_text_problems(text: str) -> list[str]:
    return [f"panel text contains forbidden word {w!r}" for w in FORBIDDEN_PANEL_WORDS if w in text]


def skill_effect_tokens(tree) -> set[str]:
    """技能树里出现的、需要在说明与 upskill 里同步体现的效果构造名。"""
    blob = json.dumps(tree, ensure_ascii=False)
    return {name for name in SKILL_DESC_EFFECTS if f'"{name}"' in blob}


def skill_desc_coverage_problems(trees, desc: str, upskill_row: list[str] | None = None) -> list[str]:
    """技能说明 / 技能树 / upskill 预览标签三方一致（审查 20260916 minor 7）。

    「省略一下」允许压缩措辞，不允许把仍然存在于树里、并且会在技能强化预览页显示标签的
    效果整条删掉：删了以后面板文字与预览标签互相矛盾。反向也查：upskill 挂着的标签
    在树里必须真有对应效果。"""
    present: set[str] = set()
    for tree in trees:
        present |= skill_effect_tokens(tree)
    probs = []
    for name in sorted(present):
        phrase, tag = SKILL_DESC_EFFECTS[name]
        if phrase not in desc:
            probs.append(f"skill desc omits {phrase!r} although the tree applies {name}")
        if upskill_row is not None and tag not in upskill_row:
            probs.append(f"upskill row lacks {tag!r} although the tree applies {name}")
    if upskill_row is not None:
        known = {tag for _p, tag in SKILL_DESC_EFFECTS.values()}
        for cell in upskill_row:
            if cell in UPSKILL_IGNORED_TAGS:
                continue
            if cell not in known:
                probs.append(f"upskill tag {cell!r} is not covered by SKILL_DESC_EFFECTS")
            elif cell not in {SKILL_DESC_EFFECTS[n][1] for n in present}:
                probs.append(f"upskill tag {cell!r} has no matching effect in the skill trees")
    return probs


def untracked_input_problems(root: Path) -> list[str]:
    """kit 运行必需、但位于被 .gitignore 排除的 ``work/`` 下的输入；缺失时给出清单而不是深处的
    ImportError / FileNotFoundError。fx manifest 与 gates.json 可缺（只影响 status）。"""
    needed = {
        DESIGN_REL: "设计定稿（身份 / 语音路由 / 能量的来源）",
        DESIGN_TREE_REL.format(level="1"): "设计定稿技能树 1（改版前基线，严格逐节点比对）",
        DESIGN_TREE_REL.format(level="2"): "设计定稿技能树 2（改版前基线，严格逐节点比对）",
        REVISION_REL: "改版方案（队长/词条/固有状态/面板文案/技能说明的来源）",
        REV_TREE_REL.format(level="1"): "改版参考技能树 1（严格逐节点比对）",
        REV_TREE_REL.format(level="2"): "改版参考技能树 2（严格逐节点比对）",
        OFFICIAL_SIG_REL: "官方全库 DSL 参数形状表（F1034 形状差分；research/_tmp/official_sig.py 生成）",
    }
    return [f"{rel}: {why}" for rel, why in needed.items() if not (root / rel).is_file()]


# ---- 设计期静态校验：移植自 research/_tmp/blueprint_build.check（逐条等价，见 impl/regis/fix-log.md）
_BP_LOOKUP = {"StopBall": [1], "ShowEffect": [3], "AddSkillPoint": [1], "CreateCondition": [1], "CreateHitArea": [2],
              "CreateNormalAttack": [1], "CreateRatioAttack": [1], "CreateFixedAttack": [1], "CreateRatioHeal": [1],
              "FindNearSubjects": [1], "CreateReferencePoint": [1], "MoveHitArea": [1], "RotateHitArea": [1]}
_BP_BUILTIN = {-1, -2, -17, -18, -33}
_OFFICIAL_SIG_CACHE: dict[str, dict[str, list[str]]] = {}


def _bp_tag(v):
    return v[0] if isinstance(v, list) and v and isinstance(v[0], str) else None


def _bp_kind(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, (int, float)):
        return "num"
    if isinstance(v, str):
        return "str"
    if isinstance(v, list):
        if v and all(isinstance(x, dict) for x in v):
            return "slv"
        t = _bp_tag(v)
        if t in ("Block", "Command", "Event"):
            return "expr"
        if t is not None:
            return "enum:" + t
        return "list"
    return "dict"


def load_official_sig(root: Path) -> dict[str, list[str]]:
    path = root / OFFICIAL_SIG_REL
    cache_key = str(path)
    if cache_key not in _OFFICIAL_SIG_CACHE:
        if not path.is_file():
            raise KitError(f"official DSL signature table missing: {OFFICIAL_SIG_REL} "
                           "(work/ is gitignored; regenerate with research/_tmp/official_sig.py)")
        _OFFICIAL_SIG_CACHE[cache_key] = json.loads(path.read_text(encoding="utf-8"))
    return _OFFICIAL_SIG_CACHE[cache_key]


def blueprint_check_with_sig(tree, off: dict[str, list[str]]) -> tuple[list[str], int, bool]:
    """官方签名差分 / 参数个数 / 作用域 C16103 / GH / CD 挂 -17/-18 / Rectangle 三元组 / 绑定 id 重复 /
    AMF3 往返 / 我方方向。与 blueprint_build.check 同口径（问题文本逐字相同）。"""
    import wf_dsl
    import wf_dsl_sig as SIG
    probs: list[str] = []
    ids_seen: dict[Any, int] = {}

    def seen(x):
        ids_seen[x] = ids_seen.get(x, 0) + 1

    def walk(n, scope):
        t = _bp_tag(n)
        if t == "Block":
            for x in n[1]:
                walk(x, scope)
            return
        if t == "Event":
            ev = n[1]
            if ev[0] not in SIG.EVENTS:
                probs.append("未知事件 " + ev[0])
            elif len(ev) - 1 != len(SIG.EVENTS[ev[0]]):
                probs.append(f"事件参数数 {ev[0]} {len(ev) - 1}")
            for x in ev[1:]:
                if _bp_tag(x) in ("Block", "Command", "Event"):
                    walk(x, scope)
            return
        if t == "Command":
            c = n[1]
            nm = c[0]
            if nm not in SIG.COMMANDS:
                probs.append("未知命令 " + nm)
                return
            if len(c) - 1 != len(SIG.COMMANDS[nm]):
                probs.append(f"参数数 {nm} {len(c) - 1}!={len(SIG.COMMANDS[nm])}")
            for i, p in enumerate(c[1:], 1):
                k = _bp_kind(p)
                official = set(off.get(f"{nm}#{i}", []))
                kk = "enum" if k.startswith("enum:") else k
                offk = {("enum" if x.startswith("enum:") else x) for x in official}
                if official and kk not in offk:
                    probs.append(f"形状 {nm} p{i} kind={k} 官方={sorted(official)}")
                if k.startswith("enum:"):
                    en = p[0]
                    for j, q in enumerate(p[1:], 1):
                        o2 = set(off.get(f"{nm}#{i}>{en}#{j}", [])) or set(off.get(f"{en}#{j}", []))
                        if o2 and _bp_kind(q) not in o2:
                            probs.append(f"形状 {nm} p{i} {en}#{j} kind={_bp_kind(q)} 官方={sorted(o2)}")
            for i in _BP_LOOKUP.get(nm, []):
                if isinstance(c[i], int) and c[i] not in _BP_BUILTIN and c[i] not in scope:
                    probs.append(f"C16103风险 {nm} p{i}={c[i]} 不在作用域 {sorted(scope)}")
            for p in c[1:]:
                if _bp_tag(p) == "GH" and p[1] not in _BP_BUILTIN and p[1] not in scope:
                    probs.append(f"GH({p[1]}) 不在作用域")
                if _bp_tag(p) == "CD" and nm in _BP_LOOKUP and c[_BP_LOOKUP[nm][0]] in (-17, -18):
                    probs.append(f"{nm} CD 挂在 {c[_BP_LOOKUP[nm][0]]} 必 throw")
            if nm == "FindAllSubjects":
                walk(c[9], scope | {c[1]})
                seen(c[1])
            elif nm == "FindNearSubjects":
                walk(c[6], scope | {c[5]})
                seen(c[5])
            elif nm == "CreateReferencePoint":
                walk(c[11], scope | {c[10]})
                seen(c[10])
            elif nm == "CreateReferencePointAtSpecifiedPosition":
                walk(c[5], scope | {c[4]})
            elif nm == "CreateHitArea":
                walk(c[20], scope | {c[19]})
                walk(c[23], scope | {c[21], c[22]})
                for x in (c[19], c[21], c[22]):
                    seen(x)
                sh = c[9]
                if _bp_tag(sh) == "Rectangle" and len(sh) != 3:
                    probs.append("Rectangle 非三元组(F1009)")
            elif nm == "ConditionalsChangeSkillFlag":
                # 2026-09-27 第三轮 c：旗号两支互斥（一次施放只执行一支，各在新的局部环境里，
                # ActionEvaluator.as:4509-4526），同一绑定号可在两支各出现一次（live 杰拉德先例）
                # ⇒ 两支各自计数、合并取大；支内重复与支外重复照旧报。其余树不含本构造，结果不变。
                outer = dict(ids_seen)
                branch_counts = []
                for branch in c[2:4]:
                    ids_seen.clear()
                    walk(branch, scope)
                    branch_counts.append(dict(ids_seen))
                ids_seen.clear()
                ids_seen.update(outer)
                for x in {k for counts in branch_counts for k in counts}:
                    ids_seen[x] = ids_seen.get(x, 0) + max(counts.get(x, 0) for counts in branch_counts)
            else:
                for x in c[1:]:
                    if _bp_tag(x) in ("Block", "Command", "Event"):
                        walk(x, scope)
            return
        probs.append("非法节点 " + json.dumps(n, ensure_ascii=False)[:60])

    if tree[0] != "ActionDsl" or len(tree) != 12:
        probs.append("根头形状不对")
    walk(tree[11], set())
    dup = [k for k, v in ids_seen.items() if v > 1]
    if dup:
        probs.append(f"绑定 id 重复 {dup}")
    enc = wf_dsl.encode_amf3(tree)
    rt = wf_dsl.parse_dsl(enc)["tree"] == tree
    probs += wf_dsl.player_side_dsl_problems(tree)
    return probs, len(enc), rt


def blueprint_check(root: Path, tree) -> tuple[list[str], int, bool]:
    """设计 _tmp 用的静态校验（官方签名差分 / 作用域 C16103 / Rectangle / CD / 方向）。"""
    probs, size, rt = blueprint_check_with_sig(tree, load_official_sig(root))
    return list(probs), size, bool(rt)


def dsl_problems(root: Path, tree) -> dict[str, Any]:
    import wf_client_legality as L
    import wf_dsl
    bp, size, rt = blueprint_check(root, tree)
    enc = wf_dsl.encode_amf3(tree)
    rt2 = strict_equal(wf_dsl.parse_dsl(enc)["tree"], tree)
    donothing = []
    for c in iter_commands(tree):
        for p in c[1:]:
            if isinstance(p, list) and p and p[0] == "Block":
                for item in p[1]:
                    if item == ["DoNothing"]:
                        donothing.append(c[0])
    probs = {
        "blueprint_check": bp,
        "element": L.action_dsl_element_problems(tree, ELEMENT),
        "subject_binding": L.action_dsl_subject_binding_problems(tree),
        "hit_area_target": L.action_dsl_hit_area_target_problems(tree),
        "player_side_direction": wf_dsl.player_side_dsl_problems(tree),
        "donothing_in_block": donothing,
    }
    return {"problems": probs, "all_empty": not any(probs.values()), "amf3_bytes": size,
            "roundtrip": bool(rt and rt2)}


# ---------------------------------------------------------------- 行构建

def donor_row(ctx, spec: str, table: str, index: int) -> list[str]:
    source, key = spec.split(":", 1)
    if source == "official":
        rows = ctx.official_flat(table)
    elif source == "store":
        rows = ctx.live_flat(table)
    else:
        raise KitError(f"unknown donor source {spec}")
    if key not in rows:
        raise KitError(f"donor {spec} missing in {table}")
    lines = ctx.csv_split(rows[key])
    return list(lines[index])


def build_rows(ctx, plan_rows: dict) -> tuple[dict, list[dict]]:
    """donor + 声明编辑重建全部行，与改版方案 ``row_built`` 逐格核对（不一致即报错）；
    ``wf_describe`` 读回的中文也要与方案登记的 ``describe`` 逐字相同（描述器漂移/行漂移都会被抓）。"""
    import wf_client_legality as L
    import wf_describe
    evidence: list[dict] = []
    leader_rows: list[list[str]] = []
    for entry in plan_rows["leader"]:
        row = donor_row(ctx, entry["donor"], entry["donor_table"], entry["row_index"])
        for col, val in entry["edits"].items():
            row[int(col)] = val
        if row != entry["row_built"]:
            diff = {i: (a, b) for i, (a, b) in enumerate(zip(row, entry["row_built"])) if a != b}
            raise KitError(f"leader {entry['id']} donor+edits != plan row_built: {diff}")
        leader_rows.append(row)
        evidence.append({"table": LEADER, "key": CID, "id": entry["id"], "donor": entry["donor"],
                         "row": row, "plan_describe": entry.get("describe")})
    ability_rows: dict[str, list[list[str]]] = {}
    for slot in range(1, 7):
        entries = sorted(plan_rows["abilities"][f"slot{slot}"], key=lambda e: e["record"])
        key = f"{CID}{slot}"
        lines = []
        for entry in entries:
            if entry["key"] != key:
                raise KitError(f"plan slot{slot} key {entry['key']} != {key}")
            row = donor_row(ctx, entry["donor"], entry["donor_table"], entry["row_index"])
            for col, val in entry["edits"].items():
                row[int(col)] = val
            if row != entry["row_built"]:
                diff = {i: (a, b) for i, (a, b) in enumerate(zip(row, entry["row_built"])) if a != b}
                raise KitError(f"ability {key}#{entry['record']} donor+edits != plan: {diff}")
            if row[0] != f"{CODE}_{slot}":
                raise KitError(f"ability {key} c0 {row[0]}")
            lines.append(row)
            evidence.append({"table": ABILITY, "key": key, "record": entry["record"],
                             "donor": entry["donor"], "row": row, "plan_describe": entry.get("describe")})
        if len({r[1] for r in lines}) != 1 or len({r[2] for r in lines}) != 1:
            # 词条键内 c1（主位限制）与 c2（玛纳雕像组）必须一致
            raise KitError(f"ability {key} mixed c1/c2 {[(r[1], r[2]) for r in lines]}")
        ability_rows[key] = lines
    total = sum(len(v) for v in ability_rows.values())
    if total != plan_rows["ability_record_count"] or len(leader_rows) != 6:
        raise KitError(f"row counts ability={total} leader={len(leader_rows)}")
    for item in evidence:
        kind = "leader_ability" if item["table"] == LEADER else "ability"
        row = item["row"]
        item["describe"] = wf_describe.describe_rows([row], kind)[0]
        item["problems"] = (L.client_legality_problems(kind, row) + L.declared_block_field_problems(kind, row)
                            + (L.ability_element_column_problems(kind, row, ELEMENT) if kind == "ability" else []))
        item["capabilities"] = L.required_client_capabilities(kind, row)
    drift = [f"{i['table'].rsplit('/', 1)[-1]}#{i['key']}#{i.get('record', i.get('id'))}: "
             f"{i['describe']!r} != {i['plan_describe']!r}"
             for i in evidence if i.get("plan_describe") and i["describe"] != i["plan_describe"]]
    if drift:
        raise KitError(f"wf_describe drifted from the revision plan: {drift}")
    return {"leader": leader_rows, "ability": ability_rows}, evidence


def build_unique_row(ctx, plan_rows: dict) -> list[str]:
    """固有状态「浪涌充能」13999401：官方 donor 2「带电」+ 声明编辑，与方案 row_built 逐格核对。

    ``c4`` 必须是 99（无上限的官方写法）——写 ``(None)`` = 上限 1，会把 during 134 / vlv 成长全部弄死
    （记忆卡 wf-unique-cap-none-trap）；``c13=false`` 是「入棺不清除」。"""
    entries = plan_rows["unique_conditions"]
    if len(entries) != 1 or entries[0]["key"] != UID or entries[0]["table"] != UNIQUE:
        raise KitError(f"revision plan unique_conditions unexpected: {[e['key'] for e in entries]}")
    entry = entries[0]
    rows = ctx.official_flat(UNIQUE)
    if UNIQUE_DONOR not in rows:
        raise KitError(f"official unique_condition lacks donor {UNIQUE_DONOR}")
    row = list(ctx.csv_split(rows[UNIQUE_DONOR])[0])
    for col, val in entry["edits"].items():
        row[int(col)] = val
    if row != entry["row_built"]:
        diff = {i: (a, b) for i, (a, b) in enumerate(zip(row, entry["row_built"])) if a != b}
        raise KitError(f"unique_condition {UID} donor+edits != plan row_built: {diff}")
    if len(row) != 15:
        raise KitError(f"unique_condition row has {len(row)} columns")
    if (row[0], row[1], row[2]) != (f"unique_{CODE}_surge", UNIQUE_NAME, ICON_ROW_PATH):
        raise KitError(f"unique_condition c0-c2 {row[:3]}")
    if row[4] in ("", "(None)") or int(row[4]) != 99:
        raise KitError(f"unique_condition max accumulation must be 99, got {row[4]!r}")
    if row[13] != "false":
        raise KitError(f"unique_condition c13 must be false, got {row[13]!r}")
    if entry["icon"] != ICON_LOGICAL:
        raise KitError(f"plan icon path {entry['icon']} != {ICON_LOGICAL}")
    return row


def draw_icon(frame) -> Any:
    """48×48 固有状态图标「浪涌充能」：沿用官方图标的外框 alpha 与白边，
    内底深海蓝→海绿渐变，底部薄荷绿浪峰 + 白色泡沫线，中心白色闪电 glyph（深色描边）
    加金色火花。先在 8× 画布上绘制再 LANCZOS 缩回 48×48（与普莉姆拉「夜百合」同工艺）。"""
    from PIL import Image, ImageDraw
    if frame.size != (48, 48):
        raise KitError(f"icon frame donor must be 48x48, got {frame.size}")
    K = 8
    N = 48 * K
    layer = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    top, bot = (14, 40, 74), (22, 104, 112)
    grad = Image.new("RGBA", (1, N))
    for y in range(N):
        t = y / (N - 1)
        grad.putpixel((0, y), tuple(round(top[i] + (bot[i] - top[i]) * t) for i in range(3)) + (255,))
    grad = grad.resize((N, N))
    inner = Image.new("L", (N, N), 0)
    ImageDraw.Draw(inner).rounded_rectangle((3 * K, 3 * K, 45 * K - 1, 45 * K - 1), radius=5 * K, fill=255)
    layer.paste(grad, (0, 0), inner)
    d = ImageDraw.Draw(layer)
    mint, mint_dk = (123, 240, 184, 255), (36, 150, 136, 255)
    foam, gold, dark = (236, 255, 248, 255), (242, 193, 78, 255), (7, 26, 44, 255)

    def wave(base_y, amp, phase):
        pts = []
        for i in range(0, 49):
            x = i * K
            y = (base_y + amp * math.sin(math.radians(i * 15 + phase))) * K
            pts.append((x, y))
        return pts + [(N, 45 * K), (0, 45 * K)]

    body = Image.new("L", (N, N), 0)
    bd = ImageDraw.Draw(body)
    bd.polygon(wave(33.5, 2.2, 200), fill=255)
    layer.paste(Image.new("RGBA", (N, N), mint_dk), (0, 0), Image.composite(body, Image.new("L", (N, N), 0), inner))
    body2 = Image.new("L", (N, N), 0)
    ImageDraw.Draw(body2).polygon(wave(36.5, 2.0, 40), fill=255)
    layer.paste(Image.new("RGBA", (N, N), mint), (0, 0), Image.composite(body2, Image.new("L", (N, N), 0), inner))
    crest = Image.new("L", (N, N), 0)
    ImageDraw.Draw(crest).line(wave(36.5, 2.0, 40)[:49], fill=255, width=int(1.4 * K), joint="curve")
    layer.paste(Image.new("RGBA", (N, N), foam), (0, 0), Image.composite(crest, Image.new("L", (N, N), 0), inner))

    bolt48 = [(14, 8), (14, 26), (20, 26), (20, 42), (34, 19), (26, 19), (34, 8)]
    cx = sum(p[0] for p in bolt48) / len(bolt48)
    bolt = [((x - cx) * 0.92 + 24) * K for x, _ in bolt48]
    bolt = [(bolt[i], bolt48[i][1] * K) for i in range(len(bolt48))]
    d.line(bolt + [bolt[0]], fill=dark, width=int(3.4 * K), joint="curve")
    d.polygon(bolt, fill=(255, 255, 255, 255))
    for px, py, r in ((11.5, 13.5, 2.0), (37.0, 16.0, 1.6), (33.5, 33.0, 1.7)):
        d.ellipse((px * K - r * K, py * K - r * K, px * K + r * K, py * K + r * K), fill=gold)
        d.ellipse((px * K - r * K, py * K - r * K, px * K + r * K, py * K + r * K), outline=dark, width=int(0.7 * K))

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
    """画图标并写入包（存储态 PNG，小写魔数）；alpha 必须等于官方图标外框。"""
    frame_raw = ctx.official_read(ICON_FRAME_DONOR)
    if frame_raw is None:
        _src, frame_raw, _how = ctx.pack.template_asset(ICON_FRAME_DONOR)
    frame = ctx.png_open(frame_raw)
    icon = draw_icon(frame)
    data = ctx.png_store_bytes(icon)
    ctx.write_asset("common", ICON_LOGICAL, data)
    back = ctx.png_open(ctx.pack.pkg_path("common", ICON_LOGICAL).read_bytes())
    if back.size != (48, 48) or back.getchannel("A").tobytes() != frame.getchannel("A").tobytes():
        raise KitError("unique_condition icon size/alpha differ from the official frame donor")
    return {"logical": ICON_LOGICAL, "frame_donor": ICON_FRAME_DONOR, "size": list(back.size),
            "sha256": sha256(data), "bytes": len(data)}


# ---------------------------------------------------------------- 特效

def load_fx_manifest(root: Path) -> tuple[dict[str, Path], dict | None]:
    """``fx/regis/out/manifest.json`` → {源 sheet 逻辑路径: 染色 PNG 文件}；不存在返回 ({}, None)。

    兼容三种写法：顶层平铺 ``{logical: path}``；``{"sheets"|"recolor"|"png"|"files": {logical: path}}``；
    ``{"sheets": [{"source"|"src"|"logical_path": …, "png"|"file"|"path"|"output": …}]}``。相对路径先按
    manifest 所在目录解析，再按批目录。
    """
    path = root / FX_MANIFEST_REL
    if not path.is_file():
        return {}, None
    data = json.loads(path.read_text(encoding="utf-8"))
    table: Any = data
    if isinstance(data, dict):
        for name in ("sheets", "recolor", "png", "pngs", "files", "outputs"):
            if name in data:
                table = data[name]
                break
    pairs: list[tuple[str, str]] = []
    if isinstance(table, dict):
        pairs = [(k, v) for k, v in table.items() if isinstance(k, str) and isinstance(v, str)]
    elif isinstance(table, list):
        for item in table:
            if not isinstance(item, dict):
                continue
            src = item.get("source") or item.get("src") or item.get("logical_path")
            png = item.get("png") or item.get("file") or item.get("path") or item.get("output")
            if isinstance(src, str) and isinstance(png, str):
                pairs.append((src, png))
    out: dict[str, Path] = {}
    for src, png in pairs:
        if not src.endswith(".png") or not src.startswith("battle/effect/"):
            continue
        cand = Path(png)
        if not cand.is_absolute():
            for base in (path.parent, root / BATCH, root):
                if (base / cand).is_file():
                    cand = base / cand
                    break
        if not cand.is_file():
            raise KitError(f"fx manifest PNG missing for {src}: {png}")
        out[src] = cand
    if isinstance(data, dict) and data.get("gates_ok") is False:
        raise KitError(f"fx manifest {FX_MANIFEST_REL} reports gates_ok=false; refusing to apply its sheets")
    return out, {"path": str(path), "sha256": sha256(path.read_bytes()), "entries": len(out),
                 "png_sha256": {src: sha256(p.read_bytes()) for src, p in sorted(out.items())}}


def family_sheets() -> dict[str, str]:
    """{母本 sheet 逻辑路径: 包内克隆 sheet 逻辑路径}（EFFECT_FAMILIES 派生，layout=codename）。"""
    out = {}
    for src_dir, sub, _bases in EFFECT_FAMILIES:
        donor = src_dir.rsplit("/", 1)[-1]
        out[f"{src_dir}/{donor}.png"] = f"battle/effect/skill_unique/{CODE}/{sub}/{sub}.png"
    return out


def fx_input_state(root: Path) -> dict | None:
    """指纹用：fx manifest 与其染色 PNG 的 sha256（manifest 不存在为 None）。"""
    _fx_map, info = load_fx_manifest(root)
    if info is None:
        return None
    return {"manifest_sha256": info["sha256"], "png_sha256": info["png_sha256"]}


def recolor_problems(ctx, report: dict | None = None,
                     sheet_bytes: dict[str, bytes] | None = None) -> list[str]:
    """设计 §5 要求两张克隆 sheet 都换色。逐项核对（不写盘）：

    - fx manifest 存在且覆盖 EFFECT_FAMILIES 的全部 sheet；
    - 包内 sheet（或 ``sheet_bytes`` 覆盖值，负向对照用）RGBA 像素 = 染色 PNG；alpha = 母本；
    - 给出 ``report``（kit-report）时：``effects.fx_manifest.sha256`` = 当前 manifest，
      ``effects.recolor`` 覆盖全部 sheet 且 ``png_sha256`` = 当前染色 PNG。
    """
    from PIL import Image
    probs: list[str] = []
    try:
        fx_map, info = load_fx_manifest(ctx.root)
    except KitError as exc:
        return [f"fx manifest unusable: {exc}"]
    sheets = family_sheets()
    if info is None:
        return [f"fx manifest absent ({FX_MANIFEST_REL}): cloned sheets keep donor colours"]
    uncovered = sorted(set(sheets) - set(fx_map))
    if uncovered:
        probs.append(f"fx manifest does not cover sheets {uncovered}")
    for src, dst in sheets.items():
        if src not in fx_map:
            continue
        if sheet_bytes is not None and dst in sheet_bytes:
            raw = sheet_bytes[dst]
        elif ctx.pack.pkg_has("common", dst):
            raw = ctx.pack.pkg_path("common", dst).read_bytes()
        else:
            probs.append(f"package sheet missing {dst}")
            continue
        pkg_img = ctx.png_open(raw)
        dyed = Image.open(fx_map[src]).convert("RGBA")
        _root, donor_raw, _src = ctx.pack.template_asset(src)
        donor = ctx.png_open(donor_raw)
        if pkg_img.size != dyed.size or pkg_img.tobytes() != dyed.tobytes():
            same_as_donor = pkg_img.size == donor.size and pkg_img.tobytes() == donor.tobytes()
            probs.append(f"{dst} pixels != recoloured {fx_map[src].name}"
                         + (" (still donor colours: rerun --step kit)" if same_as_donor else ""))
        if pkg_img.size != donor.size or pkg_img.getchannel("A").tobytes() != donor.getchannel("A").tobytes():
            probs.append(f"{dst} alpha differs from donor {src}")
    if report is not None:
        eff = report.get("effects") or {}
        rep_info = eff.get("fx_manifest") or {}
        if rep_info.get("sha256") != info["sha256"]:
            probs.append("kit-report effects.fx_manifest sha256 != current fx manifest (rerun --step kit)")
        logged = {e.get("source_sheet"): e for e in (eff.get("recolor") or [])}
        for src in sorted(sheets):
            if src not in fx_map:
                continue
            entry = logged.get(src)
            if entry is None:
                probs.append(f"kit-report effects.recolor lacks {src}")
            elif entry.get("png_sha256") != info["png_sha256"][src]:
                probs.append(f"kit-report effects.recolor png_sha256 stale for {src}")
    return probs


def recolor_transform(ctx, src_sheet: str, fx_map: dict[str, Path], log: list[dict]):
    target = fx_map.get(src_sheet)
    if target is None:
        return None

    def transform(img):
        raw = target.read_bytes()
        new = ctx.png_open(raw)
        if new.size != img.size:
            raise KitError(f"recolored sheet size {new.size} != donor {img.size}: {target}")
        a_old, a_new = img.getchannel("A").tobytes(), new.getchannel("A").tobytes()
        alpha_diff = sum(1 for x, y in zip(a_old, a_new) if x != y)
        log.append({"source_sheet": src_sheet, "png": str(target), "png_sha256": sha256(raw),
                    "size": list(new.size), "alpha_pixels_changed": alpha_diff})
        return new
    return transform


def fx_manifest_clone_problems(root: Path) -> list[str]:
    """fx manifest 可选的 ``clone`` 段须与 EFFECT_FAMILIES 一致（染色产物是按同一 dst/基名做的）。"""
    path = root / FX_MANIFEST_REL
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    clone = data.get("clone") if isinstance(data, dict) else None
    if clone is None:
        return []
    sheets = family_sheets()
    bases = {f"{src_dir}/{src_dir.rsplit('/', 1)[-1]}.png": sorted(b) for src_dir, _sub, b in EFFECT_FAMILIES}
    probs = []
    for item in clone:
        src = item.get("src")
        if src not in sheets:
            probs.append(f"fx manifest clone.src {src} not a regis family sheet")
            continue
        if item.get("dst") != sheets[src]:
            probs.append(f"fx manifest clone.dst {item.get('dst')} != {sheets[src]}")
        if item.get("fx_names") is not None and sorted(item["fx_names"]) != bases[src]:
            probs.append(f"fx manifest clone.fx_names for {src} != kit bases")
    return probs


def clone_families(ctx) -> tuple[list[dict], list[dict], dict | None]:
    fx_map, fx_info = load_fx_manifest(ctx.root)
    unknown = sorted(set(fx_map) - set(family_sheets()))
    if unknown:
        raise KitError(f"fx manifest names sheets outside regis families: {unknown}")
    clone_probs = fx_manifest_clone_problems(ctx.root)
    if clone_probs:
        raise KitError(f"fx manifest clone section disagrees with kit: {clone_probs}")
    recolor_log: list[dict] = []
    families = []
    for src_dir, sub, bases in EFFECT_FAMILIES:
        donor = src_dir.rsplit("/", 1)[-1]
        sheet = f"{src_dir}/{donor}.png"
        fam = ctx.clone_effect_family(src_dir, sub, fx_names=list(bases), layout="codename",
                                      png_transform=recolor_transform(ctx, sheet, fx_map, recolor_log))
        if fam["missing_effects"] or sorted(fam["copied_bases"]) != sorted(bases):
            raise KitError(f"effect family {src_dir} incomplete: missing={fam['missing_effects']}")
        if fam["dst_dir"] != f"battle/effect/skill_unique/{CODE}/{sub}":
            raise KitError(f"unexpected effect dst {fam['dst_dir']}")
        families.append(fam)
    # 换色钩子必须对 manifest 里每张 sheet 都真正执行过，且写盘结果逐像素 = 染色 PNG
    applied = sorted(e["source_sheet"] for e in recolor_log)
    if applied != sorted(fx_map):
        raise KitError(f"recolor not applied to every manifest sheet: applied={applied} manifest={sorted(fx_map)}")
    if fx_map:
        probs = [p for p in recolor_problems(ctx) if "does not cover" not in p]
        if probs:
            raise KitError(f"recoloured sheets did not land in the package: {probs}")
        for entry in recolor_log:
            if entry["alpha_pixels_changed"]:
                raise KitError(f"recolour changed alpha of {entry['source_sheet']}: {entry['alpha_pixels_changed']}")
    return families, recolor_log, fx_info


# ---------------------------------------------------------------- 像素小人（Integrate 阶段）

PIXEL_DIR_REL = f"{BATCH}/pixel/regis"
PIXEL_VERIFY_REL = f"{BATCH}/pixel/_review/verify_all.json"
# sheet 基名 → 同组元数据（atlas / frame / timeline），元数据保持母本（只改 character/<code>/ 前缀）
PIXEL_SHEETS = {
    "sprite_sheet": ("sprite_sheet.atlas.amf3.deflate", "pixelart.frame.amf3.deflate",
                     "pixelart.timeline.amf3.deflate"),
    "special_sprite_sheet": ("special_sprite_sheet.atlas.amf3.deflate", "special.frame.amf3.deflate",
                             "special.timeline.amf3.deflate"),
}


def pixel_inputs(root: Path) -> tuple[dict[str, Path], list[str]]:
    """像素染色产物是否可装包：``pixel/regis/report.json`` 门禁全过、``_review/verify_all.json``
    regis 全过（修复轮复核），且两者记录的 sha256 = ``out/<sheet>.png`` 当前字节。

    返回 ({sheet 基名: PNG 路径}, problems)；problems 非空 = pending（不装包）。"""
    probs: list[str] = []
    base = root / PIXEL_DIR_REL
    report_path, verify_path = base / "report.json", root / PIXEL_VERIFY_REL
    if not report_path.is_file():
        return {}, [f"pixel report absent: {PIXEL_DIR_REL}/report.json"]
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("key") != KEY or report.get("gates_passed") is not True:
        probs.append(f"pixel report gates_passed={report.get('gates_passed')} key={report.get('key')}")
    failed = sorted(k for k, v in (report.get("gates") or {}).items() if not (isinstance(v, dict) and v.get("ok")))
    if failed:
        probs.append(f"pixel report gates failed: {failed}")
    verify = json.loads(verify_path.read_text(encoding="utf-8")).get(KEY) if verify_path.is_file() else None
    if not verify:
        probs.append(f"pixel review verdict absent: {PIXEL_VERIFY_REL}")
    else:
        hard_bad = sorted(k for k, v in (verify.get("hard") or {}).items() if not v.get("ok"))
        if verify.get("pass") is not True or hard_bad:
            probs.append(f"pixel review failed: pass={verify.get('pass')} hard={hard_bad}")
    out: dict[str, Path] = {}
    reviewed = (((verify or {}).get("hard") or {}).get("H8_png_roundtrip") or {}).get("detail") or {}
    for name in PIXEL_SHEETS:
        png = base / "out" / f"{name}.png"
        if not png.is_file():
            probs.append(f"pixel output missing: {png.name}")
            continue
        digest = sha256(png.read_bytes())
        rep_sha = ((report.get("outputs") or {}).get(name) or {}).get("sha256")
        if rep_sha != digest:
            probs.append(f"{name}.png sha256 != pixel report outputs ({rep_sha})")
        if (reviewed.get(name) or {}).get("sha256") != digest:
            probs.append(f"{name}.png sha256 != reviewed verify_all H8 sha")
        out[name] = png
    return out, probs


def pixel_problems(ctx, sheet_bytes: dict[str, bytes] | None = None) -> list[str]:
    """包内像素小人核对（不写盘）：sheet 解码字节 = 染色 PNG；尺寸 / alpha = 母本；
    atlas/frame/timeline = 母本树（仅 ``character/<母本>/``→``character/<code>/``）；归属 owner=pixel。"""
    import wf_assets
    spec = ctx.spec
    pngs, probs = pixel_inputs(ctx.root)
    if probs:
        return [f"pixel inputs not ready: {p}" for p in probs]
    prefix = _pixel_prefix(spec)
    for name, metas in PIXEL_SHEETS.items():
        logical = f"character/{CODE}/pixelart/{name}.png"
        tpl_logical = f"character/{spec.template_code}/pixelart/{name}.png"
        if sheet_bytes is not None and logical in sheet_bytes:
            raw = sheet_bytes[logical]
        elif ctx.pack.pkg_has("common", logical):
            raw = ctx.pack.pkg_path("common", logical).read_bytes()
        else:
            probs.append(f"package pixel sheet missing {logical}")
            continue
        if raw[:8] != wf_assets.PNG_FAKE:
            probs.append(f"{logical} lacks store PNG magic")
            continue
        dyed_raw = pngs[name].read_bytes()
        if wf_assets.png_decode(raw) != dyed_raw:
            probs.append(f"{logical} != pixel/regis/out/{name}.png (store form)")
        _r, donor_raw, _src = ctx.pack.template_asset(tpl_logical)
        pkg_img, donor = ctx.png_open(raw), ctx.png_open(donor_raw)
        if pkg_img.size != donor.size:
            probs.append(f"{logical} size {pkg_img.size} != donor {donor.size}")
        elif pkg_img.getchannel("A").tobytes() != donor.getchannel("A").tobytes():
            probs.append(f"{logical} alpha differs from donor {tpl_logical}")
        if sheet_bytes is None and ctx.pack.owner_of("common", logical) != "pixel":
            probs.append(f"{logical} owner={ctx.pack.owner_of('common', logical)} (expected pixel)")
        for meta in metas:
            pkg_meta = f"character/{CODE}/pixelart/{meta}"
            if not ctx.pack.pkg_has("common", pkg_meta):
                probs.append(f"package pixel metadata missing {pkg_meta}")
                continue
            _r, tpl_raw, _src = ctx.pack.template_asset(f"character/{spec.template_code}/pixelart/{meta}")
            want = ctx.replace_strings(ctx.amf_parse(tpl_raw), prefix)
            if ctx.amf_parse(ctx.pack.pkg_path("common", pkg_meta).read_bytes()) != want:
                probs.append(f"{pkg_meta} differs from donor metadata (only path prefix may change)")
    return probs


def _pixel_prefix(spec) -> dict[str, str]:
    return {f"character/{spec.template_code}/": f"character/{spec.code}/"}


def install_pixel(ctx) -> dict[str, Any]:
    """把复核通过的像素染色 sheet 以存储态（小写魔数、PNG 字节不重编码）写进包，owner=pixel。

    重跑幂等：字节相同不改盘（write_pkg），登记 sha 不变。产物未就绪时不写、返回 pending。"""
    import wf_assets
    pngs, probs = pixel_inputs(ctx.root)
    if probs:
        return {"status": "pending", "problems": probs}
    written = {}
    for name, png in pngs.items():
        logical = f"character/{CODE}/pixelart/{name}.png"
        data = wf_assets.png_encode(png.read_bytes())
        ctx.write_asset("common", logical, data, owner="pixel")
        written[logical] = {"source": f"{PIXEL_DIR_REL}/out/{png.name}", "decoded_sha256": sha256(png.read_bytes()),
                            "store_sha256": sha256(data)}
    after = pixel_problems(ctx)
    if after:
        raise KitError(f"pixel sheets did not land in the package: {after}")
    return {"status": "installed", "sheets": written, "problems": []}


def voice_state(ctx) -> dict[str, Any]:
    """只读：语音是否已由 wf_seasonal7_voice pack 装包（22 槽文件在包内、speech 行引用新槽、归属 voice）。"""
    import wf_seasonal7_voice as V
    missing = [s for s in V.SLOTS if not ctx.pack.pkg_has("common", f"character/{CODE}/voice/{s}.mp3")]
    not_voice_owned = [s for s in V.SLOTS if s not in missing
                       and ctx.pack.owner_of("common", f"character/{CODE}/voice/{s}.mp3") != "voice"]
    speech = ctx.csv_split(ctx.pkg_flat("master/character/character_speech.orderedmap").get(CID, ""))
    refs = [cells[4] for cells in speech if len(cells) == 5]
    want_refs = [*V.HOME_SLOTS, "ally/join", "ally/evolution"]
    base = ctx.pack.package / "roots" / "common" / "character" / CODE / "voice"
    extra = sorted(p.relative_to(base).with_suffix("").as_posix() for p in base.rglob("*.mp3")
                   if p.relative_to(base).with_suffix("").as_posix() not in V.SLOTS) if base.is_dir() else []
    packed = not missing and not not_voice_owned and refs == want_refs and not extra
    return {"packed": packed, "missing_slots": missing, "not_voice_owned": not_voice_owned,
            "speech_refs": refs, "extra_voice_files": extra}


# ---------------------------------------------------------------- 技能 DSL

def _rev_slv(bounds: tuple[float, float], vid: int | None = None) -> list[dict]:
    """CreateNormalAttack p6 的 slv 字典；``vid`` 非空时挂上按固有层数成长的 vlv。"""
    cell: dict[str, Any] = {"min": float(bounds[0]), "max": float(bounds[1])}
    if vid is not None:
        cell["vlv"] = [{"vid": int(vid), "min": 0.0, "max": float(REV_GROWTH)}]
    return [cell]


def _rev_bind(vid: int) -> list:
    """把自身（-17）的固有状态层数绑定为变量 ``vid``（官方 161123 / 自制 wind_spgirl_campus 同写法）。"""
    return ["Command", ["BindConditionAccumulationVariable", -17, int(vid), ["DCUnique", int(UID)],
                        REV_DIVISOR, REV_CAP]]


def apply_revision(tree, level: str) -> list[str]:
    """改版方案 ``skill_dsl.edits`` D1–D5：两分支各插一条 BindConditionAccumulationVariable，
    Fever 粗光束与通常分支光束的 CreateNormalAttack p6 换新倍率并挂 vlv 成长；
    通常分支的激光只换倍率、不挂成长（成长只挂一道，避免双倍）。"""
    R = REV_LEVELS[level]
    edits: list[str] = []
    cfm = cmd(tree[11][1][1])
    if cfm is None or cfm[0] != "ConditionalsFeverMode":
        raise KitError("revision: root block[1] is not ConditionalsFeverMode")
    fever_blk, normal_blk = cfm[1][1], cfm[2][1]
    fn0 = cmd(fever_blk[0])
    if not (fn0 and fn0[0] == "FindNearSubjects" and fn0[5] == 0):
        raise KitError("revision: fever branch head is not FindNearSubjects(bind 0)")
    cha0 = cmd(fn0[6][1][0])
    if not (cha0[0] == "CreateHitArea" and cha0[9][1][0]["min"] == 300):
        raise KitError("revision: fever CreateHitArea is not the 300-wide beam")
    cna0 = first_cna(cha0[23])
    old = copy.deepcopy(cna0[6])
    cna0[6] = _rev_slv(R["fever"], REV_VID["fever"])
    edits.append(f"D2 Fever CNA p6 {old} -> {cna0[6]}")
    fever_blk.insert(0, _rev_bind(REV_VID["fever"]))
    edits.append(f"D1 Fever branch head: BindConditionAccumulationVariable(-17, vid {REV_VID['fever']}, "
                 f"DCUnique {UID}, /{REV_DIVISOR}, cap {REV_CAP})")
    names = [cmd(x)[0] for x in normal_blk]
    if names != ["FindNearSubjects", "FindNearSubjects", "AddFeverPoint", "CreateCondition"]:
        raise KitError(f"revision: normal branch unexpected {names}")
    cha_laser = cmd(cmd(normal_blk[0])[6][1][0])
    cha_ray = cmd(cmd(normal_blk[1])[6][1][0])
    if (cha_laser[9][1][0]["min"], cha_ray[9][1][0]["min"]) != (100, 150):
        raise KitError("revision: normal branch hit area widths are not (100, 150)")
    cna_l, cna_r = first_cna(cha_laser[23]), first_cna(cha_ray[23])
    old_l, old_r = copy.deepcopy(cna_l[6]), copy.deepcopy(cna_r[6])
    cna_l[6] = _rev_slv(R["laser"])
    cna_r[6] = _rev_slv(R["ray"], REV_VID["ray"])
    edits.append(f"D4 Normal laser CNA p6 {old_l} -> {cna_l[6]}")
    edits.append(f"D5 Normal ray CNA p6 {old_r} -> {cna_r[6]}")
    normal_blk.insert(0, _rev_bind(REV_VID["ray"]))
    edits.append(f"D3 Normal branch head: BindConditionAccumulationVariable(-17, vid {REV_VID['ray']}, "
                 f"DCUnique {UID}, /{REV_DIVISOR}, cap {REV_CAP})")
    return edits


def compose_skill(ctx, level: str, families: list[dict]) -> tuple[Any, dict]:
    """移植 design/_tmp/regis/d09_compose_final.py；特效改写换成 rewrite_effect_refs(strict)；
    构回上一轮定稿树后再叠加改版增量 D1–D5，两侧各与一棵参考树逐节点比对。"""
    import wf_dsl
    P = LEVELS[level]
    raws = {}
    for name, prog in SOURCE_PROGRAMS.items():
        program = prog.format(level=level)
        raw = ctx.official_read(wf_dsl.dsl_logical(program), "common")
        if raw is None:
            raise KitError(f"official baseline lacks {program} (store 版被增强过，禁止回落 live)")
        if level == "1" and sha256(raw) != SOURCE_SHA_L1[name]:
            raise KitError(f"official {program} sha256 differs from design record")
        raws[name] = raw
    base = ctx.template_dsl(SOURCE_PROGRAMS["skeleton"].format(level=level))
    ray = ctx.template_dsl(SOURCE_PROGRAMS["ray"].format(level=level))
    smr = ctx.template_dsl(SOURCE_PROGRAMS["smr21"].format(level=level))
    for name, tree in (("skeleton", base), ("ray", ray), ("smr21", smr)):
        if not strict_equal(tree, ctx.amf_parse(raws[name])):
            raise KitError(f"template_dsl for {name} did not come from the official baseline")
    edits: list[str] = []
    t = copy.deepcopy(base)
    if not (t[0] == "ActionDsl" and t[1] == 2 and t[10] == 0 and all(x is False for x in t[3:10])):
        raise KitError("skeleton root header unexpected")
    t[10] = 2
    edits.append("root tree[10] buffTargetAs 0->2")
    top = t[11][1]
    if not (len(top) == 2 and cmd(top[0])[0] == "StopBall" and cmd(top[1])[0] == "ConditionalsFeverMode"):
        raise KitError("skeleton root block unexpected")
    cfm = cmd(top[1])
    fever_blk, normal_blk = cfm[1][1], cfm[2][1]
    fn0 = cmd(fever_blk[0])
    if not (fn0[0] == "FindNearSubjects" and fn0[5] == 0):
        raise KitError("fever branch FindNearSubjects unexpected")
    cha0 = cmd(fn0[6][1][0])
    if not (cha0[0] == "CreateHitArea" and cha0[9][1][0]["min"] == 300):
        raise KitError("fever CreateHitArea unexpected")
    cna0 = first_cna(cha0[23])
    edits.append(f"Fever CNA p6 {cna0[6]} -> {P['fever']}")
    cna0[6] = copy.deepcopy(P["fever"])
    names = [cmd(x)[0] for x in normal_blk]
    if names != ["FindNearSubjects", "AddFeverPoint", "CreateCondition", "CreateCondition"]:
        raise KitError(f"normal branch unexpected {names}")
    fn4 = cmd(normal_blk[0])
    cha4 = cmd(fn4[6][1][0])
    if not (fn4[5] == 4 and cha4[9][1][0]["min"] == 100):
        raise KitError("normal CreateHitArea unexpected")
    cna4 = first_cna(cha4[23])
    edits.append(f"Normal laser CNA p6 {cna4[6]} -> {P['laser']}")
    cna4[6] = copy.deepcopy(P["laser"])
    cc_sd = cmd(normal_blk[3])
    if not (cc_sd[1] == -17 and cc_sd[2][0][0] == "ACSkillDamage"):
        raise KitError("normal branch 4th node is not CreateCondition(-17, ACSkillDamage)")
    del normal_blk[3]
    edits.append("Normal: delete CreateCondition(-17, ACSkillDamage)")
    # D2 ★4 光束
    rtop = ray[11][1]
    if [cmd(x)[0] for x in rtop] != ["StopBall", "FindNearSubjects"]:
        raise KitError("rare4 ray root unexpected")
    fnr = copy.deepcopy(rtop[1])
    c = cmd(fnr)
    if c[5] != 0:
        raise KitError("ray FindNearSubjects bind != 0")
    c[5] = 8
    chr_ = cmd(c[6][1][0])
    if not (chr_[0] == "CreateHitArea" and chr_[3] == ["GH", 0] and (chr_[19], chr_[21], chr_[22]) == (1, 2, 3)
            and chr_[13] == ["SpecifyHitAreaLifetimeDirectly", 80]):
        raise KitError("ray CreateHitArea unexpected")
    chr_[3] = ["GH", 8]
    chr_[19], chr_[21], chr_[22] = 9, 10, 11
    chr_[13] = ["SpecifyHitAreaLifetimeDirectly", 70]
    se = cmd(chr_[20][1][0])
    if not (se[0] == "ShowEffect" and se[3] == 1 and se[5] == ["SpecifyEffectLifetimeDirectly", 80]):
        raise KitError("ray ShowEffect unexpected")
    se[3] = 9
    se[5] = ["SpecifyEffectLifetimeDirectly", 70]
    cnr = first_cna(chr_[23])
    if cnr[1] != 3:
        raise KitError("ray CNA target != 3")
    cnr[1] = 11
    old_ray = cnr[6]
    cnr[6] = copy.deepcopy(P["ray"])
    normal_blk.insert(1, fnr)
    edits.append(f"Normal: insert rec_android_{level} ray bind 0->8, GH 8, ids 9/10/11, life 80->70, "
                 f"ShowEffect subj 1->9 life 70, CNA target 3->11 p6 {old_ray}->{P['ray']}")
    # D3 雷队能力伤害状态
    fa = None
    for x in smr[11][1]:
        if cmd(x) and cmd(x)[0] == "FindAllSubjects":
            if fa is not None:
                raise KitError("smr21 has more than one root FindAllSubjects")
            fa = copy.deepcopy(x)
    c = cmd(fa)
    if not (c[1] == 3 and c[2] == 33 and c[3] == [5]):
        raise KitError("smr21 FindAllSubjects unexpected")
    c[1] = 12
    c[3] = [3]
    cc = cmd(c[9][1][0])
    if not (cc[0] == "CreateCondition" and cc[1] == 3 and cc[2][0][0] == "ACAbilityDamage" and cc[10] == 3):
        raise KitError("smr21 CreateCondition unexpected")
    old_abd = cc[2][0][2]
    cc[1] = 12
    cc[2][0][2] = copy.deepcopy(P["abd"])
    top.append(fa)
    edits.append(f"Root: append FindAllSubjects(12,33,[3]) CreateCondition(12, ACAbilityDamage "
                 f"dur {cc[2][0][1]} value {old_abd}->{P['abd']})")
    n24 = 0
    for c_ in iter_commands(t, "CreateHitArea"):
        if c_[24] != 0:
            raise KitError("CreateHitArea cmd[24] not 0 before edit")
        c_[24] = 2
        n24 += 1
    if n24 != 3:
        raise KitError(f"expected 3 CreateHitArea, got {n24}")
    edits.append("all 3 CreateHitArea cmd[24] buffTargetAs 0->2")
    before_fx = [c_[2][1] for c_ in iter_commands(t, "ShowEffect")]
    rewrites = []
    for fam in families:
        t, info = ctx.rewrite_effect_refs(t, fam, strict=True)
        rewrites.append({"family": fam["dst_dir"], **info})
    after_fx = [c_[2][1] for c_ in iter_commands(t, "ShowEffect")]
    if any(p.startswith("battle/effect/skill_unique/rec_android") and f"/{CODE}/" not in p for p in after_fx):
        raise KitError(f"ShowEffect still points at donor dirs: {after_fx}")
    design_tree = json.loads((ctx.root / DESIGN_TREE_REL.format(level=level)).read_text(encoding="utf-8"))
    diff = first_difference(t, design_tree)
    if diff:
        raise KitError(f"composed skill {level} differs from the previous design final tree: {diff}")
    edits += apply_revision(t, level)
    rev_tree = json.loads((ctx.root / REV_TREE_REL.format(level=level)).read_text(encoding="utf-8"))
    diff = first_difference(t, rev_tree)
    if diff:
        raise KitError(f"revised skill {level} differs from the revision reference tree: {diff}")
    est = {}
    cfm2 = cmd(t[11][1][1])
    for label, blk in (("fever", cfm2[1]), ("normal", cfm2[2])):
        nominal, formula = [0.0, 0.0], [0.0, 0.0]
        for c_ in iter_commands(blk, "CreateHitArea"):
            n, h = c_[14][1], hits_by_formula(c_)
            for a in iter_commands(c_[23], "CreateNormalAttack"):
                mn, mx = a[6][0]["min"], a[6][0]["max"]
                nominal = [nominal[0] + mn * n, nominal[1] + mx * n]
                formula = [formula[0] + mn * h, formula[1] + mx * h]
        est[label] = {"nominal": [round(v, 3) for v in nominal], "formula": [round(v, 3) for v in formula]}
    return t, {"level": level, "edits": edits, "effect_rewrites": rewrites,
               "show_effect_paths": {"before": before_fx, "after": after_fx},
               "source_sha256": {k: sha256(v) for k, v in raws.items()}, "multiplier_estimate": est,
               "equals_design_tree": True, "equals_revision_tree": True,
               "growth_per_stack": REV_GROWTH, "growth_unique": UID}


def effect_ref_problems(ctx, tree) -> list[str]:
    """ShowEffect 引用在包内（含 parts 或 timeline）或 live store 可解析。"""
    import wf_assets
    probs = []
    for c in iter_commands(tree, "ShowEffect"):
        spec = c[2]
        if not (isinstance(spec, list) and spec and spec[0] == "SpecifyEffectDirectly"):
            continue
        path = spec[1]
        found = False
        for kind in ("parts", "timeline"):
            logical = f"{path}.{kind}.amf3.deflate"
            if ctx.pack.pkg_has("common", logical) or wf_assets.locate(ctx.store, logical):
                found = True
        if not found:
            probs.append(f"unresolved ShowEffect {path}")
    return probs


# ---------------------------------------------------------------- 指纹

def kit_fingerprint(ctx) -> tuple[str, dict]:
    """kit 自有产物指纹：表行 / DSL / 特效族全部文件字节（含 sheet PNG）/ 能力声明，外加换色输入
    （fx manifest 与染色 PNG 的 sha256）。不含语音、像素小人（Integrate 阶段的产物）。

    特效 sheet 必须计入：换色产物晚于 kit 出现时，旧实现忽略 PNG，包里仍是母本原色却与门禁指纹一致，
    status 保持 ready-for-review（审查 major）。"""
    parts: dict[str, Any] = {}
    parts["character_c9_16_c18"] = ctx.pack.pkg_character_row()[9:19]
    parts["character_text"] = ctx.pack.pkg_character_text_row()
    ab = ctx.pkg_flat(ABILITY)
    parts["ability"] = {k: ab[k] for k in [f"{CID}{i}" for i in range(1, 7)]}
    parts["leader"] = ctx.pkg_flat(LEADER)[CID]
    cas = ctx.pkg_flat(CAS)
    parts["custom_ability_string"] = {k: cas[k] for k in CAS_KEYS}
    parts["custom_ability_string"][balance.STRIKE_KEY] = cas.get(balance.STRIKE_KEY)
    parts["custom_ability_string"][balance_c.FLAG_KEY] = cas.get(balance_c.FLAG_KEY)
    parts["upskill"] = ctx.pkg_flat(UPSKILL)[CID]
    parts["unique_condition"] = ctx.pkg_flat(UNIQUE)[UID]
    parts["unique_icon"] = sha256(ctx.pack.pkg_path("common", ICON_LOGICAL).read_bytes()) \
        if ctx.pack.pkg_has("common", ICON_LOGICAL) else None
    parts["action_skill"] = ctx.pkg_nested(CODE)
    parts["switched_action_skill"] = ctx.pkg_nested(VOICE_KEY, SW)
    import wf_dsl
    progs = {}
    for level in ("1", "2"):
        logical = wf_dsl.dsl_logical(ctx.program_path(level))
        progs[logical] = sha256(ctx.pack.pkg_path("common", logical).read_bytes())
    strike = wf_dsl.dsl_logical(balance.STRIKE_PROGRAM)
    progs[strike] = sha256(ctx.pack.pkg_path("common", strike).read_bytes()) \
        if ctx.pack.pkg_has("common", strike) else None
    parts["dsl"] = progs
    fx = {}
    for src_dir, sub, _bases in EFFECT_FAMILIES:
        base = ctx.pack.package / "roots" / "common" / "battle" / "effect" / "skill_unique" / CODE / sub
        for p in sorted(base.rglob("*")):
            if p.is_file():
                rel = p.relative_to(ctx.pack.package / "roots" / "common").as_posix()
                fx[rel] = sha256(p.read_bytes())
    parts["effects"] = fx
    parts["fx_inputs"] = fx_input_state(ctx.root)
    parts["required_capabilities"] = sorted(CAPABILITIES)
    blob = json.dumps(parts, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return sha256(blob), parts


def gates_status(root: Path, fingerprint: str, blockers: list[str] | None = None) -> tuple[str, str]:
    """``blockers`` 非空（如特效未换色）时一律 draft，不看 gates.json。"""
    if blockers:
        return "draft", "; ".join(blockers)
    path = root / GATES_REL
    if not path.is_file():
        return "draft", "impl/regis/gates.json 不存在（门禁未跑）"
    try:
        gates = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return "draft", "gates.json 无法解析"
    if not gates.get("all_pass"):
        return "draft", "gates.json all_pass=false"
    if gates.get("kit_fingerprint") != fingerprint:
        return "draft", "gates.json kit_fingerprint 与当前产物不一致（需重跑门禁）"
    return "ready-for-review", f"gates.json all_pass @ {gates.get('generated_at')}"


# ---------------------------------------------------------------- 主流程

def build(ctx) -> dict[str, Any]:
    import wf_client_legality as L
    import wf_dsl
    import wf_seasonal7_voice as V
    spec = ctx.spec
    if (spec.key, spec.cid_s, spec.code, spec.element) != (KEY, CID, CODE, ELEMENT):
        raise KitError(f"spec identity mismatch {spec.key}/{spec.cid}/{spec.code}")
    missing_inputs = untracked_input_problems(ctx.root)
    if missing_inputs:
        raise KitError("kit inputs under gitignored work/ are missing (restore the seasonal7-20260916 batch "
                       f"directory before running the kit): {missing_inputs}")
    design = load_design(ctx.root)
    plan = load_revision(ctx.root)
    revision = revision_rows(plan)
    problems: list[str] = check_texts_constant(design, revision)
    if problems:
        raise KitError(f"TEXTS constant drifted from design/revision: {problems}")
    texts = design_text_rows(design, revision)
    notes: list[str] = []

    # ---- character 行：spec 列断言 + c9–c16 语音路由 + c18 队长名
    crow = ctx.pack.pkg_character_row()
    ident = design["identity"]
    expect = {0: CODE, 2: str(ident["rarity"]), 3: str(ident["element"]), 4: ident["race"], 6: str(ident["pf_type"]),
              7: ident["gender"], 8: CODE, 17: CID, 26: ident["stance"], 27: str(ident["c27_policy"]["value"])}
    for i, key in enumerate(range(19, 25)):
        expect[key] = f"{CID}{i + 1}"
    bad = {i: (crow[i], v) for i, v in expect.items() if crow[i] != v}
    if bad:
        raise KitError(f"package character row spec columns differ from design (rerun tables): {bad}")
    route_cols = V.normalize_route(design["voice"]["route"], CODE)
    if route_cols != ["1", "29", "0", "", "", VOICE_KEY, "false", "false"]:
        raise KitError(f"voice route unexpected {route_cols}")
    new_crow = list(crow)
    new_crow[9:17] = route_cols
    new_crow[18] = design["text"]["leader_name_c10"]
    V.route_character_row(new_crow, route_cols, CODE)          # 语音装包约定自检
    ctx.write_flat(CHAR, {CID: [new_crow]})
    ctx.write_flat(TEXT, {CID: [texts["character_text"]]})

    # ---- 词条 / 队长 / 固有状态
    rows, row_evidence = build_rows(ctx, revision)
    unique_row = build_unique_row(ctx, revision)
    row_problems = {f"{e['table'].rsplit('/', 1)[-1]}#{e['key']}#{e.get('record', e.get('id'))}": e["problems"]
                    for e in row_evidence if e["problems"]}
    if row_problems:
        raise KitError(f"row legality problems: {row_problems}")
    # 规则②的空过断言：plan 行没有 ChangeSkillFlag「技能强化」条目（有就必须按规则②改文案）；
    # 第三轮 c 层追加的队长 536 行，其文案在 balance_c_panel 里按规则②（skill_flag=True）把关
    flag_probs = [f"{e['key']}#{e.get('record', e.get('id'))}: {p}" for e in row_evidence
                  for p in rev2_skill_flag_problems("leader_ability" if e["table"] == LEADER else "ability", e["row"])]
    if flag_probs:
        raise KitError(f"revision2 rule 2 (technique-enhancement wording) applies now: {flag_probs}")
    import wf_regis_surge_stages as surge
    rows['leader'], rows['ability'][CID+'3'] = surge.revise_rows(
        rows['leader'], rows['ability'][CID+'3'], rows['ability'][CID+'1'])
    # 2026-09-27 平衡批次：浪涌之后再换成技能伤害口径（顺序固定，见 balance_rows）
    rows['leader'], rows['ability'] = balance_rows(rows['leader'], rows['ability'])
    # 2026-09-27 平衡第二批：第一批之后再叠无上限成长修订（队长 7→9 行、能力 3 最多 5 层）
    rows['leader'], rows['ability'] = balance_b_rows(rows['leader'], rows['ability'])
    # 2026-09-27 平衡第三轮 c：第二批之后再叠成长 4/5 + 队长 536 旗号 1 行（9→10 行，能力不动）
    rows['leader'], rows['ability'] = balance_c_rows(rows['leader'], rows['ability'])
    description = balance_c.description(balance_b.description(balance.description(surge.DESCRIPTION)))
    texts['character_text'][5] = texts['character_text'][7] = description
    for level in ('1', '2'):
        texts['action'][level][1] = description
    ctx.write_flat(TEXT, {CID: [texts['character_text']]})
    ctx.write_flat(LEADER, {CID: rows["leader"]})
    ctx.write_flat(ABILITY, rows["ability"])
    ctx.write_flat(UNIQUE, {UID: [unique_row]})
    icon = install_unique_icon(ctx)

    # ---- 面板覆盖文案
    cas_rows = {}
    for item in revision["custom_strings"]:
        if item["table"] != CAS or item["capability"] != "panel-description-override-v2":
            raise KitError(f"unexpected custom string entry {item['key']}")
        if UNIQUE_NAME not in item["text"] and item["key"] in (CAS_KEYS[0], CAS_KEYS[1], CAS_KEYS[3]):
            raise KitError(f"{item['key']}: panel text no longer mentions {UNIQUE_NAME}")
        if L.panel_override_capability(item["key"]) != "panel-description-override-v2":
            raise KitError(f"panel capability mismatch for {item['key']}")
        text_probs = panel_text_problems(item["text"])
        if text_probs:
            raise KitError(f"{item['key']}: {text_probs}")
        cas_rows[item["key"]] = [[item["text"]]]
    if sorted(cas_rows) != sorted(CAS_KEYS):
        raise KitError(f"custom string keys {sorted(cas_rows)} != {sorted(CAS_KEYS)}")
    # 覆盖键 = desc_override_ + 第 0 行 string_id(c0)；逐条核对确有行引用
    string_ids = {rows["leader"][0][0]} | {lines[0][0] for lines in rows["ability"].values()}
    if {f"desc_override_{s}" for s in string_ids} != set(CAS_KEYS):
        raise KitError(f"desc_override keys do not match row string ids {sorted(string_ids)}")
    # 第二轮：主位限制（c1=false）与面板 <icon id='main'> 必须同进同退
    ms_probs = main_slot_panel_problems(rows["ability"], cas_rows)
    if ms_probs:
        raise KitError(f"main-slot marker mismatch: {ms_probs}")
    for slot, key in ((0, 'desc_override_'+CODE), (3, 'desc_override_'+CODE+'_3')):
        cas_rows[key][0][0] = surge.revise_text(slot, cas_rows[key][0][0])
    cas_rows = balance_panel(cas_rows)
    cas_rows = balance_b_panel(cas_rows)
    cas_rows = balance_c_panel(cas_rows)
    ms_probs = main_slot_panel_problems(rows["ability"], cas_rows)
    if ms_probs:
        raise KitError(f"main-slot marker mismatch after balance 20260927: {ms_probs}")
    ctx.write_flat(CAS, cas_rows)

    # ---- action_skill：名称 / 描述 / 能量
    inner = ctx.pkg_nested(CODE)
    if set(inner) != {"1", "2"}:
        raise KitError(f"package action_skill inner keys {sorted(inner)}")
    energy = design["skills"]["energy"]
    new_inner = {}
    for level, cells in inner.items():
        cells = list(cells)
        if len(cells) != 24 or cells[7] != ctx.program_path(level):
            raise KitError(f"action_skill {level} schema/program unexpected")
        cells[0], cells[1] = texts["action"][level]
        e = energy[level]
        cells[4], cells[5], cells[6] = (str(e["c4_min_skill_weight"]), str(e["c5_max_skill_weight"]),
                                        str(e["c6_skill_chain_strength"]))
        if cells[2:4] != ["dynamic/skill/atk_nearest", "true"] or cells[8:17] != \
                ["1", "2", "2400", "3000", "0", "0", "0", "0", "(None)"]:
            raise KitError(f"action_skill {level} other cols differ from official 131020: {cells}")
        new_inner[level] = [cells]
    ctx.write_nested(ACTION, CODE, new_inner, replace_inner=True)

    # ---- upskill：技能强化项与新技能一致
    template_up = ctx.csv_split(ctx.template_flat(UPSKILL)[str(spec.template_id)])
    if len(template_up) != 1 or template_up[0].count("skill_damage_up") != 2:
        raise KitError(f"template upskill row unexpected: {template_up}")
    # 2026-09-16 版把母本 skill_damage_up 换成 ability_damage_up；2026-09-27 平衡批次技能树改回
    # ACSkillDamage，标签随之恢复母本写法。旧形态（ability_damage_up）仍接受为包内现值。
    old_up = [["ability_damage_up" if c == "skill_damage_up" else c for c in template_up[0]]]
    new_up = balance.upskill_rows(old_up)
    if new_up != template_up:
        raise KitError(f"balance upskill row differs from template: {new_up}")
    current_up = ctx.csv_split(ctx.pkg_flat(UPSKILL)[CID])
    if current_up not in (template_up, old_up):
        raise KitError(f"package upskill row edited by someone else: {current_up}")
    ctx.write_flat(UPSKILL, {CID: new_up})
    notes.append("upskill: 恢复母本 skill_damage_up（2026-09-27 技能树雷队增益改回 ACSkillDamage；"
                 "09-16 版曾换成 ability_damage_up）")

    # ---- 特效族 + 技能 DSL
    families, recolor_log, fx_info = clone_families(ctx)
    skills_report = {}
    built_trees = []
    for level in ("1", "2"):
        tree, info = compose_skill(ctx, level, families)   # 内部已与定稿树 + 改版参考树逐节点比对
        tree = surge.revise_skill(tree)
        tree = balance.skill_tree(tree)                     # 2026-09-27：bta 2→0、ACSkillDamage
        tree = balance_b.skill_tree(tree)                   # 2026-09-27 第二批：浪涌层数绑定上限 99→5
        tree = balance_c.skill_tree(tree)                   # 2026-09-27 第三轮 c：≥5 层档按旗号 1 分支（开支 99）
        built_trees.append(tree)
        checks = dsl_problems(ctx.root, tree)
        if not checks["all_empty"] or not checks["roundtrip"]:
            raise KitError(f"skill {level} static checks failed: {checks}")
        ref_probs = effect_ref_problems(ctx, tree)
        if ref_probs:
            raise KitError(f"skill {level} effect refs unresolved: {ref_probs}")
        logical = ctx.write_dsl(ctx.program_path(level), tree)
        info.update(checks=checks, effect_ref_problems=ref_probs, logical=logical,
                    sha256=sha256(ctx.pack.pkg_path("common", logical).read_bytes()))
        skills_report[level] = info

    # ---- 2026-09-27：能力 2 的 629 全体追击（20 倍雷属性技能伤害，复用包内光束命中特效）
    strike = balance.strike_tree()
    strike_checks = dsl_problems(ctx.root, strike)
    strike_probs = balance.dsl_problems(strike)
    if not strike_checks["all_empty"] or not strike_checks["roundtrip"] or strike_probs:
        raise KitError(f"strike DSL static checks failed: {strike_checks} {strike_probs}")
    strike_refs = effect_ref_problems(ctx, strike)
    if strike_refs:
        raise KitError(f"strike DSL effect refs unresolved: {strike_refs}")
    strike_logical = ctx.write_dsl(balance.STRIKE_PROGRAM, strike)
    strike_report = {"logical": strike_logical, "string_key": balance.STRIKE_KEY, "checks": strike_checks,
                     "sha256": sha256(ctx.pack.pkg_path("common", strike_logical).read_bytes())}

    # ---- 技能说明 / 技能树 / upskill 预览标签三方一致（审查 20260916 minor 7）
    desc_probs = skill_desc_coverage_problems(built_trees, texts["action"]["1"][1], new_up[0])
    if desc_probs:
        raise KitError(f"skill description / tree / upskill mismatch: {desc_probs}")
    notes.append("技能说明覆盖树里三个增益（技能伤害 / 自身攻击力 / FEVER槽）并与 upskill 预览标签对齐")

    # ---- switched_action_skill（语音 matched_skill_ready 路由的目标技能）
    action_now = {lv: list(c) for lv, c in ctx.pkg_nested(CODE).items()}
    switched = V.switched_rows(action_now)
    ctx.write_nested(SW, VOICE_KEY, {lv: [cells] for lv, cells in switched.items()}, replace_inner=True)

    # ---- 三层镜像
    mirrors = ctx.sync_character_mirrors()

    # ---- 像素小人（复核通过的染色 sheet，owner=pixel；未就绪时不写）与语音装包状态（只读）
    pixel = install_pixel(ctx)
    ctx.evidence_write("pixel-report.json", {
        "summary": ("像素小人染色 sheet 2 张已装包（owner=pixel，存储态，元数据保持母本）" if pixel["status"] == "installed"
                    else "像素小人产物未就绪，包内仍为母本原色"),
        "status": pixel["status"], "mode": "recolor-lut (pixel/regis)",
        "source": {"report": f"{PIXEL_DIR_REL}/report.json", "review": PIXEL_VERIFY_REL},
        **{k: v for k, v in pixel.items() if k != "status"}})
    voice = voice_state(ctx)

    # ---- 能力声明一致性
    row_caps = sorted({c for e in row_evidence for c in e["capabilities"]}
                      | {L.panel_override_capability(k) for k in CAS_KEYS})
    if row_caps != sorted(CAPABILITIES) or sorted(spec.required_capabilities) != sorted(CAPABILITIES):
        raise KitError(f"capabilities rows={row_caps} spec={spec.required_capabilities}")

    fingerprint, _parts = kit_fingerprint(ctx)
    recolor_blockers = recolor_problems(ctx)
    status, status_reason = gates_status(ctx.root, fingerprint, recolor_blockers)
    programs = [wf_dsl.dsl_logical(ctx.program_path(lv)) for lv in ("1", "2")] + [strike_logical]
    panel = [f"{e['table'].rsplit('/', 1)[-1].split('.')[0]} {e['key']}"
             f"#{e.get('record', e.get('id'))}: {e['describe']}" for e in row_evidence]
    if fx_info is None:
        notes.append("特效 sheet 仍为母本原色：fx/regis/out/manifest.json 未产出（Effects 阶段后重跑 kit 即换色；"
                     "未换色时 status 固定为 draft）")
    else:
        notes.append(f"特效 sheet 已按 fx manifest 换色 {len(recolor_log)} 张（manifest sha256 "
                     f"{fx_info['sha256'][:12]}…；包内像素 = 染色 PNG、alpha = 母本已逐像素核对）")
    if voice["packed"]:
        notes.append("语音：c9–c16 ConditionExist(29) 路由与 switched_action_skill 已写；22 槽 AI 合成语音已由 "
                     "wf_seasonal7_voice pack 装包（owner=voice，speech 8 行引用 home_0..5/join/evolution，母本旧语音已移除）")
    else:
        notes.append("语音：c9–c16 已写 ConditionExist(29) 路由与 switched_action_skill；matched_skill_ready.mp3 "
                     "等 22 条须由 wf_seasonal7_voice pack 装包（Integrate 阶段）；当前 "
                     f"missing={len(voice['missing_slots'])} extra={len(voice['extra_voice_files'])}")
    if pixel["status"] == "installed":
        notes.append("像素小人：pixel/regis/out 两张染色 sheet 已按存储态装包（owner=pixel；解码字节 = 复核 sha，"
                     "尺寸/alpha = 母本，atlas/frame/timeline = 母本仅路径前缀改写）")
    else:
        notes.append(f"像素小人仍为母本原色（pixel 产物未就绪：{pixel['problems'][:3]}）")
    notes.append(f"固有状态「{UNIQUE_NAME}」{UID}：官方 donor 2「带电」改 c0/c1/c2/c4/c13，"
                 f"上限 {unique_row[4]} 层（无上限官方写法，不写 (None)）、入棺不清除；"
                 f"图标 {ICON_LOGICAL}（alpha = 官方外框）。产：词条 {CID}1#2（进 Fever +1 层）；"
                 f"耗：队长 L0/L1、词条 {CID}3#3/#4、两棵技能树的 vlv")
    notes.append("改版（2026-09-16 作者要求）：队长 6 行整体替换为成长型（旧四条静态行删除）、"
                 "词条 11→16 条、技能 50→55 倍 / 65→75 倍并按固有层数 +10 倍/层、"
                 "Fever 时间 −50%（队长 kind 56 负值）、冲刺±Fever 槽（词条 724 + pre 42）。"
                 "两处口径偏差：「2.5 秒」实装为 2 秒（instant_delay 只吃整秒）；"
                 "「进入 Fever 叠加」走同一个固有层数计数器")
    notes.append("第二轮改版（2026-09-16 晚，作者真机试玩后）：能力 1 加主位限制（整键 c1=false，面板逐行带 "
                 "<icon id='main'>，不加前置 202 以免双 Ⓜ）；面板文案按新规则①删掉全部「（无上限）」——"
                 f"机制不动（固有上限仍是 {unique_row[4]} 层）；规则②（技能强化条目不写数字与时间）本角色"
                 "无 ChangeSkillFlag 行，空过并已由门禁钉死")
    notes.append("待作者拍板（取设计默认）：c27=自身 cid、语音参考 A/B")
    notes.append("2026-09-27 平衡批次（作者确认「能力相关都换成技能伤害」，wf_balance_20260927_regis）："
                 "技能树 bta 2→0、判定区 node[24] 2→0、雷队 ACAbilityDamage→ACSkillDamage；队长 154→2、"
                 "144→23（1 次）；能力 2 253→629 全体 20 倍雷属性技能伤害（不加 202，保留副位）；"
                 "能力 3 412→411、144→23（1 次）、154→2、删除自身 411；能力 5 388→34；upskill 恢复 "
                 "skill_damage_up；面板 4 键与技能描述同步。未经真机验收")
    notes.append("2026-09-27 平衡第二批（口径 A 无上限成长，wf_balance_20260927b_regis）：队长每层雷队技伤 "
                 "150→30%、攻击 100→20%，新增自身每层攻/技伤 30%（由能力 3 搬入，7→9 行）；能力 3 两行改为每层 "
                 "30%、最多 5 层（c102=5）；技能树浪涌层数绑定上限 99→5（每层 +15 倍最多 5 层）；"
                 "面板 2 键与技能描述同步。未经真机验收")
    notes.append("2026-09-27 平衡第三轮 c（成长复核 + 技能倍率撤封顶，wf_balance_20260927c_regis）：队长每层雷队技伤 "
                 "30→120%、攻击 20→80%、自身攻/技伤 30→120%（原值 4/5）；队长追加 536 旗号 1 行（雷共鸣，9→10 行，"
                 f"文案键 {balance_c.FLAG_KEY}）；两棵技能树 ≥5 层档按 ConditionalsChangeSkillFlag(1) 分两支（开支 Bind "
                 "上限 99.0、关支保留 5.0）；队长面板同步（强化条目点名『浪花爆破』），技能描述保持第二批（不写强化后效果）；"
                 "能力 3 封顶版不动。未经真机验收")
    report = {
        "summary": f"雷吉斯·海滨 kit（改版 2026-09-16）：{len(rows['leader'])} 队长行 / "
                   f"{sum(len(v) for v in rows['ability'].values())} 词条行 / 7 覆盖文案 / "
                   f"固有状态「{UNIQUE_NAME}」+ 48×48 图标 / "
                   f"两档技能（技能伤害 55/75 倍 + 按层数 +10 倍）/ 能力 2 全体追击 629 / 两特效族克隆 / 语音路由",
        "status": status,
        "status_reason": status_reason,
        "kit_fingerprint": fingerprint,
        "design": {"path": DESIGN_REL, "sha256": sha256((ctx.root / DESIGN_REL).read_bytes())},
        "revision": {"path": REVISION_REL, "sha256": sha256((ctx.root / REVISION_REL).read_bytes()),
                     "trees": {lv: sha256((ctx.root / REV_TREE_REL.format(level=lv)).read_bytes())
                               for lv in ("1", "2")}},
        "revision2": revision["revision2"] | {"rules": REVISION2_RULES_REL},
        "skills": {"programs": programs},
        "unique_condition": {UID: {"icon": ICON_LOGICAL, "name": UNIQUE_NAME,
                                   "max_accumulation": int(unique_row[4]), "row": unique_row,
                                   "icon_sha256": icon["sha256"]}},
        "required_capabilities": list(CAPABILITIES),
        "panel": panel,
        "notes": notes,
        "rows": row_evidence,
        "skill_trees": skills_report,
        "strike_skill": strike_report,
        "effects": {"families": [{k: f[k] for k in ("src_dir", "dst_dir", "copied_bases", "missing_effects")}
                                 | {"files": len(f["files"])} for f in families],
                    "fx_manifest": fx_info, "recolor": recolor_log, "recolor_problems": recolor_blockers},
        "pixel": pixel,
        "voice": voice,
        "switched_action_skill": {VOICE_KEY: switched},
        "character_route": route_cols,
        "mirrors": {"server_character": mirrors["server_character"]},
    }
    ctx.report(report)
    return {"status": status, "status_reason": status_reason, "kit_fingerprint": fingerprint,
            "rows": {"leader": len(rows["leader"]), "ability_records": sum(len(v) for v in rows["ability"].values())},
            "unique_condition": {UID: {"name": UNIQUE_NAME, "max_accumulation": unique_row[4],
                                       "icon": ICON_LOGICAL}},
            "skills": {lv: {"bytes": s["checks"]["amf3_bytes"], "estimate": s["multiplier_estimate"]}
                       for lv, s in skills_report.items()},
            "effects": [f["dst_dir"] for f in families], "recolored": len(recolor_log),
            "pixel": pixel["status"], "voice_packed": voice["packed"]}
