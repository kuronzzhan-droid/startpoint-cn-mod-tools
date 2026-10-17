# -*- coding: utf-8 -*-
"""菲莉亚·夏祭浴衣（159996 ``wind_oracle_yukata``）套件施工器。

真源两层：
- 底稿 ``work/character_packs/seasonal7-20260916/design/philia.json``（status=final，1.4.868 上线版）；
- **第一轮改版真源** ``…/revision-20260916/philia/plan.json``（作者 2026-09-16 试玩后的要求，逐条 R1–R31）；
- **第二轮文案真源** ``…/revision2-20260916/philia/strings.json``（作者 2026-09-16 晚补充的两条面板文案规则：
  规则1「没有上限就什么都不写」、规则2「能力里的技能强化条目不写数字和时间」）。第二轮**只改字符串**，
  行 / DSL / 特效 / 像素 / 语音一格未动；``text_rule_problems`` 是这两条规则的硬门禁，非空即拒写。
  行装配一律「design 派生行 → plan 覆盖（keep/edit/replace/move_in/new）→ 与 plan.full_row_after 逐格核对」；
  design 侧被 plan 取代的数值改由 ``SUPERSEDED_*`` 常量钉死，design 再变仍会变红。
本模块只写 ``work/character_packs/s7-philia/``（经 KitContext）与本批 ``fx/philia``、``impl/philia``、
``revision-20260916/philia`` 下的证据；不写 live store / assets / .cdn / src，不发布。

落地内容（build(ctx)）：
- 词条 6 键 16 条、队长 6 行：按 donor（官方基线或 live 已上线行）+ edits 派生，
  逐格核对 plan ``full_row_after``；跑 wf_client_legality 三件套，非空即拒写。
- custom_ability_string：``change_skill_wind_oracle_yukata``（536 c70）、
  ``override_string_wind_oracle_yukata_pf``（722 c82）；撤销框架自动克隆但不用的
  ``change_skill_wind_oracle_yukata_2``。
- 特效三族克隆（codename 布局 sword/rain/heal，基名保留）；``fx/philia/out/manifest.json``
  存在时按其 {源 sheet 逻辑路径 → 染色 PNG} 替换 sheet（尺寸必须一致、alpha 默认必须一致）。
- 技能两档 DSL：meteor23 / 1anv / wind_oracle / light_ballot23_2 四母本拼树（官方基线，sha 锁定）；
  本轮 R1/R2/R3/R16/R29：10 把慢速追踪光剑、每把命中点降剑雨、根头部 ``tree[10]=3``（走强化弹射乘区）、
  命中时按共鸣旗（536）追加强化弹射伤害抗性下降。
  PF 覆盖三档（R4–R7）：官方 ``special_lv{1,2,3}`` 整树（plan sha 锁定）作底座，
  追加 supporter 辅助增益块 + 爆炸中心 5 方向追踪光剑 + 每把光剑命中点剑雨。
  特效引用一律 ``rewrite_effect_refs(strict=True)``；写前跑 DSL 门禁（往返/主体绑定/命中目标/
  元素/方向/严格作用域/签名参数个数与形状/DoNothing/重复绑定 id）。
- action_skill 两档、power_flip_action、switched_action_skill ``<code>_voice_ready``（17 列 = c7..c23）、
  character c9–c16 语音路由与 c18 队长名、character_text 12 列；镜像同步。
- 像素小人（Integrate）：``pixel/philia/out/{sprite_sheet,special_sprite_sheet}.png`` 在 report 门禁全过、
  ``pixel/_review/verify_all.json`` 复核全过且 sha 一致时，以存储态写入 ``character/<code>/pixelart/``
  （owner=pixel），写后核对尺寸/alpha = 母本、元数据 = 母本（仅路径前缀）。语音由
  ``wf_seasonal7_voice pack`` + ``impl/philia/voice_merge.py`` 装包，kit 只读记录 ``voice_state``。
- **2026-09-27 平衡第二批**（``wf_balance_20260927b_philia``）：行在 stock / nofly 之后先补 0917 的
  ``wf_seasonal_pf_revision``（能力 3 +2 行），再叠无上限成长修订（队长 6→8 行、能力 3 三行有上限）；
  技能树剑雨 p13 2.5→1、PF 随机选项风刃/剑雨 p13→0。
- **2026-09-27 平衡第三轮**（``wf_balance_20260927c_philia``）：接在第二批 ``growth_rows`` 之后，队长四条成长
  c49/c50 回调（每次 PF 光队攻 2.5→20%、自身 PF 伤 7→40%、施放光队攻 20→80%、每 5 次 PF 自身攻 10→35%）。
- kit-report：离线门禁（``impl/philia/run_gates.py`` → ``impl/philia/gates.json``）全过、且其
  ``kit_digest`` 与本次产物摘要一致时写 ``ready-for-review``，否则 ``draft``。
"""
from __future__ import annotations

import copy
import hashlib
import io
import json
import zlib
from pathlib import Path
from typing import Any, Callable

import wf_client_legality as L
import wf_dsl
import wf_dsl_sig
import wf_gerald_native_pf_dsl as GPF
import wf_seasonal7_common as C

KEY = "philia"
CID = 159996
CODE = "wind_oracle_yukata"
ELEMENT = 4                                    # 光（0 基内部）
BATCH = "work/character_packs/seasonal7-20260916"
DESIGN_REL = f"{BATCH}/design/philia.json"
REVISION_DIR_REL = f"{BATCH}/revision-20260916/philia"
REVISION_REL = f"{REVISION_DIR_REL}/plan.json"
PROTO_REL = f"{REVISION_DIR_REL}/proto"
# 第二轮（作者 2026-09-16 晚补充的两条面板文案规则）文案真源；只覆盖字符串，不碰任何行/树。
REVISION2_DIR_REL = f"{BATCH}/revision2-20260916/philia"
REVISION2_REL = f"{REVISION2_DIR_REL}/strings.json"
FX_MANIFEST_REL = f"{BATCH}/fx/philia/out/manifest.json"
IMPL_REL = f"{BATCH}/impl/philia"
GATES_REL = f"{IMPL_REL}/gates.json"
SUPPORTER_SOURCES = (f"work/codex_out/newchars-r2-20260906/gerald-native-pf",
                     f"{IMPL_REL}/sources")

ABILITY = "master/ability/ability.orderedmap"
LEADER = "master/ability/leader_ability.orderedmap"
CAS = "master/string/custom_ability_string.orderedmap"
PFA = "master/skill/power_flip_action.orderedmap"
SW = "master/skill/switched_action_skill.orderedmap"
CHAR = "master/character/character.orderedmap"
TEXT = "master/character/character_text.orderedmap"
ACTION = "master/skill/action_skill.orderedmap"
SPEECH = "master/character/character_speech.orderedmap"     # 8 行字幕，玩家在角色档案/语音页可见
SKILL_SRC = "battle/action/skill/action/rare5/"
PF_KEY = f"{CODE}_pf"
PF_PROGRAMS = tuple(f"battle/action/power_flip/action/override/{PF_KEY}${PF_KEY}_lv{n}" for n in (1, 2, 3))
SPECIAL_PROGRAMS = {n: f"battle/action/power_flip/action/special$special_lv{n}" for n in (1, 2, 3)}
VOICE_KEY = f"{CODE}_voice_ready"
CAS_CHANGE_SKILL = f"change_skill_{CODE}"
CAS_PF_OVERRIDE = f"override_string_{CODE}_pf"
UNUSED_FRAMEWORK_CAS = (f"change_skill_{CODE}_2",)

# ---- 模块级覆盖（get_spec 合并；tables 重跑时生效）。与 revision plan.json strings 段逐字一致，build 时再核对。
# R31「技能描述不再写太复杂省略一下」：8 分句 190 字 → 6 分句 96 字。
_DESC = ("射出10把追踪光剑，并在命中位置降下剑雨，造成光属性伤害【以强化弹射伤害计算】"
         "【伤害量随自身增益效果数量提升】／恢复队伍角色与协力球的生命值／赋予参战者浮游效果／"
         "提升队伍强化弹射伤害与队长攻击力／提升连击数／强化时追加降低命中敌人的强化弹射伤害抗性")
# 上一轮（1.4.868 上线）的技能说明与 PF 覆盖文案：只用于钉住 design 基线，改了就变红。
SUPERSEDED_DESIGN_DESC_SHA256 = "30b2c796702ff830d54fe9a9b7a426070c5c94500e5acb80f84fe7d07998a74b"
SUPERSEDED_DESIGN_PF_STRING_SHA256 = "2329afa218ed7b98887c6c3268122f4f8a0207f9e92215b12f900d58e9748948"
# 536 强化说明（1.4.868 上线版）：「强化『绣球光剑·夏夜花火』的剑雨威力」。本轮 536 旗标除了抬剑雨 ALv
# 还门控 R29 的抗性下降，旧文只说了一半，与 action_skill c1 新文案对不上（审查 minor#6）。
SUPERSEDED_DESIGN_CHANGE_SKILL_SHA256 = "e3dc7ce44584b2c090318b7a2c1d77b5f4e0b75570e48120848c79a60010938c"
TEXTS = {
    "name": "菲莉亚",
    "furigana": "FEILIYA",
    "profile": ("换上白底青纹浴衣参加夏祭的风之巫女。绣球花与风铃摇曳的木台上，她为大家祈求平安，"
                "也悄悄期待夜空绽放的烟花。当晚风点亮光之剑，她会轻声许愿——愿今夜的欢笑，不被任何人夺走。"),
    "title": "绣球夜祭的光剑巫女",
    "leader": "夏祭夜空的祈愿",
    "skill1": "绣球光剑·夏夜花火",
    "desc1": _DESC,
    "skill2": "绣球光剑·夏夜花火＋",
    "desc2": _DESC,
    "cv": "AI 合成配音",
}
SPEC = {
    "required_capabilities": ("kyubi-fever-ratio-v1",),
    "extra_keys": {
        CAS: (CAS_PF_OVERRIDE, CAS_CHANGE_SKILL),
        PFA: (PF_KEY,),
        SW: (VOICE_KEY,),
    },
}

# ---- 技能树参数。design 仍管的项见 DESIGN_TRACKED_SKILL_PARAMS；本轮 plan 改的项见 REVISED_SKILL_PARAMS。
SKILL_PARAMS = {
    "1": dict(sword=(1.20, 1.20), rain=(0.75, 0.75), alv=(0.10, 0.25), fly=(480, 480), heal=(0.06, 0.06),
              pfdmg_frames=900, pfdmg=(1.0, 1.0), ldatk_frames=900, ldatk=(1.4, 1.4), combo=(10, 10)),
    "2": dict(sword=(1.25, 1.40), rain=(0.80, 0.90), alv=(0.10, 0.25), fly=(600, 720), heal=(0.08, 0.10),
              pfdmg_frames=1200, pfdmg=(1.2, 1.5), ldatk_frames=1200, ldatk=(1.6, 2.0), combo=(10, 15)),
}
DESIGN_TRACKED_SKILL_PARAMS = ("fly", "heal", "heal_slayer", "pfdmg_frames", "pfdmg", "ldatk_frames", "combo")
REVISED_SKILL_PARAMS = ("sword", "rain", "ldatk")
# design 里被本轮取代的值（钉死；design 再动仍会变红）
SUPERSEDED_DESIGN_SKILL_PARAMS = {
    "1": {"sword": (0.65, 0.65), "rain": (3.6, 3.6, 0.5, 1.25), "ldatk": (0.8, 0.8)},
    "2": {"sword": (0.70, 0.80), "rain": (4.2, 5.0, 0.5, 1.25), "ldatk": (1.0, 1.2)},
}
SUPERSEDED_PF_PARAMS = {1: (4, 0.9, 6), 2: (6, 1.1, 6), 3: (8, 1.3, 6)}   # 上一轮 supporter 版 (把数, 倍率, Wait)

SKILL_BUFF_TARGET_AS = 3                        # R16：根头部 tree[10]=3 → 技能伤害走强化弹射乘区
SKILL_SWORDS = 10                               # R1：16 → 10 把
SKILL_SWORD_WAIT_STEP = 9                       # R2：子 Wait 4i → 9i
SKILL_SWORD_SPEED = 18                          # R2：MoveHitArea p3 30 → 18
SKILL_SWORD_HITAREA_LIFETIME = 100              # R2：CreateHitArea p12 60 → 100
SKILL_SWORD_REFPOINT_LIFETIME = 110             # R2：CreateReferencePoint p8 60 → 110
# R2b（审查 minor#3）：间隔拉到 9 帧后最后一把剑在第 20+9*9=101 帧发射，母本 StopBall 只停到第 80 帧，
# 后 3 把会从「已经弹开的球」当前位置飞出（光剑锚点 = -18 且 trackingPos=false）。停球窗口必须盖住末发。
SKILL_STOPBALL_FRAMES = 110                     # 母本 80 → 110（末发 101 + 9 帧余量）
# R3b（审查 minor#4）：光剑 p14 maxNumOfHits=Some(1) 只是**按目标**封顶（ActionHitAreaGroup.as:694-768
# 的 key 带 targetId），寿命 100 帧内一把剑可以连续命中多个敌人，每次命中都再挂一棵重型剑雨。
# totalHitToEliminate 是**跨目标**累计（同文件 :172-183，None→2147483647），写 Some(1) 才能把
# 「一把剑 = 一份剑雨」钉死，多杂兵波次的单帧面片峰值才有上限（wf-battle-atlas-budget / U_1d93f4）。
SWORD_TOTAL_HIT_TO_ELIMINATE = 1                # CreateHitArea p17 = ["Some", 1]（官方 num，不是 SLv）
SKILL_RAIN_BASE_ID = 200                        # R3：每把光剑的剑雨占 200+4i .. 200+4i+3
SKILL_RAIN = dict(y_offset=260, lifetime=140, scale=2.0, radius=130, max_hits=2)
RESONANCE_FLAG_INDEX = 1                        # R29：536 行硬写 ability power index = 1（官方 236 处全是 1）
RESIST_KIND = "ACPowerFlipDamageResistance"     # R29：AdditionalConditionKind 第 5 项
RESIST_FRAMES = 900                             # 15 秒
RESIST_VALUE = -0.25
RESIST_TARGET_KIND = 3                          # CreateCondition p9：命中目标官方 331/331 都写 3

# PF 三档（R4–R7）：官方 special 底座 + 5 把光剑 + 每把命中点剑雨
PF_PARAMS = {1: dict(sword=0.8, rain=0.4), 2: dict(sword=1.0, rain=0.55), 3: dict(sword=1.3, rain=0.8)}
PF_SWORDS = 5
PF_LAUNCH_DIRS = (0.3141592654, 1.5707963268, 2.8274333882, 4.0840704497, 5.3407075111)  # pi/10 + 2pi*i/5
PF_EXPLOSION_BIND = 1                           # special 底座爆炸中心 CreateReferencePoint 的绑定 id
PF_SUBJECT_OFFSET = 200                         # 光剑单元 200+5i .. 200+5i+4
PF_RAIN_BASE_ID = 300                           # 剑雨 300+4i .. 300+4i+3
PF_SUPPORT_OFFSET = 400                         # supporter 辅助增益块
PF_SWORD_SPEED_SCATTER = 14                     # 第一段：按自身朝向散射（CD）
PF_SWORD_SPEED_TRACK = 22                       # 第二段：转为追踪（GH）
PF_SWORD_TRACK_WAIT = 10
PF_SWORD_HITAREA_LIFETIME = 90
PF_TRACK_REFPOINT_LIFETIME = 100
PF_RAIN = dict(y_offset=260, lifetime=140, scale=1.5, radius=110, max_hits=2)
PF_EFFECT_LABEL_SUFFIX = "_pfsword"
HEAL_SLAYER_LIGHT = [5]                         # CreateRatioHeal p3：1 基光（官方 compliment_oiran_xm22_2 同构）

# 主体槽（命令数组下标，0 = 命令名）与 GH 坐标槽 —— 与 d8_proto / wf-dsl-subject-lookup-map 一致
SUBJECT_SLOTS = {"FindAllSubjects": (1,), "FindNearSubjects": (1, 5), "CreateReferencePoint": (1, 10),
                 "CreateHitArea": (2, 19, 21, 22), "ShowEffect": (3,), "MoveHitArea": (1,),
                 "CreateNormalAttack": (1,), "CreateCondition": (1,), "CreateRatioHeal": (1,)}
COORD_SLOTS = {"CreateHitArea": (3,), "ShowEffect": (6,), "MoveHitArea": (2,), "CreateReferencePoint": (2,)}


class KitError(C.S7Error):
    pass


# ================================================================ 纯函数：树工具

def slv(a, b, **extra) -> list[dict]:
    d = {"min": a, "max": b}
    d.update(extra)
    return [d]


def cmds(node, name: str | None = None, out: list | None = None) -> list[list]:
    out = [] if out is None else out
    if isinstance(node, list):
        if node and node[0] == "Command" and isinstance(node[1], list) and (name is None or node[1][0] == name):
            out.append(node[1])
        for child in node:
            cmds(child, name, out)
    return out


def events(node, out: list | None = None) -> list[list]:
    out = [] if out is None else out
    if isinstance(node, list):
        if node and node[0] == "Event" and isinstance(node[1], list):
            out.append(node[1])
        for child in node:
            events(child, out)
    return out


def conditional_nodes(node, name: str = "ConditionalsChangeSkillFlag", out: list | None = None) -> list[list]:
    """树里所有 ``Conditionals*`` 节点（默认只收 ChangeSkillFlag）。节点形状 ``[名, p0, then, else]``。"""
    out = [] if out is None else out
    if isinstance(node, list):
        if node and isinstance(node[0], str) and node[0].startswith("Conditionals") \
                and (name is None or node[0] == name):
            out.append(node)
        for child in node:
            conditional_nodes(child, name, out)
    return out


def spec_paths(node):
    if isinstance(node, list):
        if len(node) == 2 and node[0] == "SpecifyEffectDirectly" and isinstance(node[1], str):
            yield node[1]
        for child in node:
            yield from spec_paths(child)


def remap_subjects(node, mapping: Callable[[int], int]) -> None:
    """就地重映射非负主体 id（lookup 位 + 绑定位 + GH 坐标）。mapping 抛 KeyError = 出现计划外 id。"""
    if isinstance(node, list):
        if node and node[0] == "Command" and isinstance(node[1], list):
            cmd = node[1]
            for i in SUBJECT_SLOTS.get(cmd[0], ()):
                if isinstance(cmd[i], int) and not isinstance(cmd[i], bool) and cmd[i] >= 0:
                    cmd[i] = mapping(cmd[i])
            for i in COORD_SLOTS.get(cmd[0], ()):
                if isinstance(cmd[i], list) and cmd[i] and cmd[i][0] == "GH" and cmd[i][1] >= 0:
                    cmd[i][1] = mapping(cmd[i][1])
        for child in node:
            remap_subjects(child, mapping)


def find_one(block: list, pred, label: str) -> list:
    hits = [i for i, entry in enumerate(block) if pred(entry)]
    if len(hits) != 1:
        raise KitError(f"locate {label}: expected exactly one match, got {len(hits)}")
    return copy.deepcopy(block[hits[0]])


def is_cmd(name: str, **params):
    return lambda e: (e[0] == "Command" and e[1][0] == name
                      and all(e[1][int(k[1:])] == v for k, v in params.items()))


def is_find_all(kind: int):
    return lambda e: e[0] == "Command" and e[1][0] == "FindAllSubjects" and e[1][2] == kind


def bound_ids(tree) -> list[int]:
    ids: list[int] = []
    for c in cmds(tree):
        if c[0] == "FindAllSubjects":
            ids.append(c[1])
        elif c[0] == "FindNearSubjects":
            ids.append(c[5])
        elif c[0] == "CreateReferencePoint":
            ids.append(c[10])
        elif c[0] == "CreateHitArea":
            ids += [c[19], c[21], c[22]]
    return ids


# ================================================================ 纯函数：DSL 门禁

def scope_problems(tree) -> list[str]:
    """严格作用域：lookup 位 / GH 坐标只能引用外层已绑定 id（比 legality 更严）。"""
    probs: list[str] = []
    bind = {"FindAllSubjects": ((1,), 9), "FindNearSubjects": ((5,), 6), "CreateReferencePoint": ((10,), 11)}
    look = {"ShowEffect": (3,), "CreateHitArea": (2,), "FindNearSubjects": (1,), "CreateReferencePoint": (1,),
            "CreateNormalAttack": (1,), "CreateCondition": (1,), "CreateRatioHeal": (1,), "MoveHitArea": (1,),
            "StopBall": (1,)}

    def walk(node, bound: frozenset) -> None:
        if not isinstance(node, list):
            return
        if node and node[0] == "Event" and node[1][0] == "CollisionOfBallAndEnemy":
            # Native ListeningEvent binds the collided enemy only inside this event.
            walk(node[1][5], bound | {node[1][4]})
            return
        if node and node[0] == "Command" and isinstance(node[1], list):
            c = node[1]
            name = c[0]
            for i in look.get(name, ()):
                v = c[i]
                if isinstance(v, int) and not isinstance(v, bool) and v >= 0 and v not in bound and v != 255:
                    probs.append(f"{name}[{i}]={v} unbound")
            for i in COORD_SLOTS.get(name, ()):
                v = c[i]
                if isinstance(v, list) and v and v[0] == "GH" and v[1] >= 0 and v[1] not in bound:
                    probs.append(f"{name} GH {v[1]} unbound")
            if name in bind:
                ids, blk = bind[name]
                walk(c[blk], bound | {c[i] for i in ids})
                return
            if name == "CreateHitArea":
                inner = bound | {c[19], c[21], c[22]}
                walk(c[20], inner)
                walk(c[23], inner)
                return
            for child in c[1:]:
                walk(child, bound)
            return
        for child in node:
            walk(child, bound)

    walk(tree, frozenset())
    return probs


_EXPR_TAGS = ("Block", "Command", "Event")


def _is_expr(value) -> bool:
    """``ActionDslExpression`` 只有 Block / Event / Command 三个构造。

    客户端 ``ActionDslExpression.as`` ``__constructs__ = ['Block','Event','Command']``；
    ``Conditionals*`` 是 **ActionDslCommand** 的构造名（``wf_dsl_sig.COMMANDS`` 收录），必须包一层
    ``["Command", …]``。裸着塞进表达式位时 ``DataConcreter.concreteEnum`` 查不到名字 → 索引 0（Block），
    Block 的第 1 参被当 ``Array<ActionDslExpression>`` 取，而那里是裸 int → AS3 #1034（详情页/战斗加载即崩）。
    2026-09-16 审查 blocker：旧实现放行 ``startswith("Conditionals")``，正是它让缺壳变异全绿通过。
    """
    return isinstance(value, list) and bool(value) and isinstance(value[0], str) and value[0] in _EXPR_TAGS


def _is_num(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _shape_ok(value, typ: str, path: str, probs: list[str]) -> None:
    """按 wf_dsl_sig 类型表检查参数形状（F1034：非 Array 进 Array 参；F1009：DoNothing 进表达式槽）。

    null 一律放行：官方树大量可空参数（如 CreateCondition p7 HitCountCheckTargetKind=null），
    客户端 undefined/null 静默处理（记忆卡 wf-dsl-param-shape-f1034）。"""
    if value is None or typ in ("Object", "Dynamic"):
        return
    if typ in ("int", "Number"):
        if not _is_num(value):
            probs.append(f"{path}: want {typ} got {type(value).__name__}")
        return
    if typ == "Boolean":
        if not isinstance(value, bool):
            probs.append(f"{path}: want Boolean got {type(value).__name__}")
        return
    if typ == "String":
        if not isinstance(value, str):
            probs.append(f"{path}: want String got {type(value).__name__}")
        return
    if typ == "Array":
        if not isinstance(value, list):
            probs.append(f"{path}: want Array got {type(value).__name__}")
        return
    if typ == "ActionDslExpression":
        if not _is_expr(value):
            probs.append(f"{path}: want ActionDslExpression got {json.dumps(value, ensure_ascii=False)[:60]}")
        return
    enum = wf_dsl_sig.ENUMS.get(typ)
    if enum is None:
        return                                   # 未收录类型：不下结论
    if not (isinstance(value, list) and value and isinstance(value[0], str)):
        probs.append(f"{path}: want enum {typ} got {json.dumps(value, ensure_ascii=False)[:60]}")
        return
    ctor = value[0]
    if ctor not in enum:
        probs.append(f"{path}: {ctor!r} is not a constructor of {typ}")
        return
    args = enum[ctor]
    if len(value) - 1 != len(args):
        probs.append(f"{path}: {typ}.{ctor} arity {len(value) - 1} != {len(args)}")
        return
    for j, (arg, arg_t) in enumerate(zip(value[1:], args), 1):
        _shape_ok(arg, arg_t, f"{path}>{ctor}#{j}", probs)


def expr_tag_problems(tree) -> list[str]:
    """每个 ``ActionDslExpression`` 位置的构造名只能是 Block / Event / Command。

    与 ``signature_problems`` 的区别：这里是**自顶向下按表达式位走**（Block 体的每一项、Event/Command
    签名里每个 ``ActionDslExpression`` 参数、以及 ``HitAreaGuardMode.Suppress`` 这类内嵌表达式的枚举参数），
    所以「裸 ``Conditionals*`` 被 append 进 on-hit 块」这种缺壳变异一定会被逮到——
    ``cmds()`` 只收 ``["Command", …]``，缺壳节点根本进不了签名检查。
    """
    probs: list[str] = []

    def enum_args(value, where: str) -> None:
        if not (isinstance(value, list) and value and isinstance(value[0], str)):
            return
        for ctors in wf_dsl_sig.ENUMS.values():
            args = ctors.get(value[0])
            if args is None or "ActionDslExpression" not in args:
                continue
            for i, typ in enumerate(args):
                if typ == "ActionDslExpression" and i + 1 < len(value):
                    expr(value[i + 1], f"{where}>{value[0]}#p{i}")

    def expr(node, where: str) -> None:
        if not (isinstance(node, list) and node and isinstance(node[0], str)):
            probs.append(f"{where}: not an ActionDslExpression: {json.dumps(node, ensure_ascii=False)[:60]}")
            return
        tag = node[0]
        if tag not in _EXPR_TAGS:
            probs.append(f"{where}: expression tag {tag!r} not in {list(_EXPR_TAGS)}"
                         f" (bare command construct must be wrapped in [\"Command\", ...]; AS3 #1034)")
            return
        if tag == "Block":
            body = node[1] if len(node) > 1 else None
            if not isinstance(body, list):
                probs.append(f"{where}>Block: body is not a list")
                return
            for i, child in enumerate(body):
                expr(child, f"{where}>Block[{i}]")
            return
        args = node[1] if len(node) > 1 else None
        if not (isinstance(args, list) and args and isinstance(args[0], str)):
            probs.append(f"{where}>{tag}: payload is not a construct list")
            return
        sig = (wf_dsl_sig.EVENTS if tag == "Event" else wf_dsl_sig.COMMANDS).get(args[0])
        if sig is None:
            return                                # 未知构造名由 signature_problems 报
        for i, typ in enumerate(sig):
            if i + 1 >= len(args):
                break
            if typ == "ActionDslExpression":
                expr(args[i + 1], f"{where}>{tag} {args[0]}#p{i}")
            else:
                enum_args(args[i + 1], f"{where}>{tag} {args[0]}#p{i}")

    body = tree[11] if isinstance(tree, list) and len(tree) == 12 else None
    if not (isinstance(body, list) and body[:1] == ["Block"]):
        return ["root body is not a Block"]
    expr(body, "root")
    return probs


def signature_problems(tree) -> list[str]:
    probs: list[str] = []
    for c in cmds(tree):
        sig = wf_dsl_sig.COMMANDS.get(c[0])
        if sig is None:
            probs.append(f"unknown command {c[0]}")
            continue
        if len(c) - 1 != len(sig):
            probs.append(f"arity {c[0]} {len(c) - 1} != {len(sig)}")
            continue
        for i, (value, typ) in enumerate(zip(c[1:], sig)):
            _shape_ok(value, typ, f"{c[0]}#p{i}", probs)
    for e in events(tree):
        sig = wf_dsl_sig.EVENTS.get(e[0])
        if sig is None:
            probs.append(f"unknown event {e[0]}")
            continue
        if len(e) - 1 != len(sig):
            probs.append(f"arity event {e[0]} {len(e) - 1} != {len(sig)}")
            continue
        for i, (value, typ) in enumerate(zip(e[1:], sig)):
            _shape_ok(value, typ, f"Event {e[0]}#p{i}", probs)

    def conditionals(node) -> None:
        if isinstance(node, list):
            if node and isinstance(node[0], str) and node[0].startswith("Conditionals"):
                for branch in node[1:]:
                    if isinstance(branch, list) and branch[:1] == ["DoNothing"]:
                        probs.append(f"{node[0]} branch is ['DoNothing'] (F1009; empty branch = ['Block', []])")
            for child in node:
                conditionals(child)
    conditionals(tree)
    return probs


def official_signature_problems(tree, official_sig: dict[str, list[str]]) -> list[str]:
    """官方全库 (构造, 参数位) → kind 集合差分（design/_tmp review_zehr_engine/sigdiff.py 同口径）。"""
    probs: list[str] = []
    known_cmds = {k.split("#")[0] for k in official_sig}

    def tag(v):
        return v[0] if isinstance(v, list) and v and isinstance(v[0], str) else None

    def kind(v):
        if v is None:
            return "null"
        if isinstance(v, bool):
            return "bool"
        if isinstance(v, (int, float)):
            return "num"
        if isinstance(v, str):
            return "str"
        if isinstance(v, dict):
            return "dict"
        if isinstance(v, list):
            if v and all(isinstance(x, dict) for x in v):
                return "slv"
            t = tag(v)
            if t in _EXPR_TAGS:
                return "expr"
            if t is not None:
                return "enum:" + t
            return "list"
        return type(v).__name__

    def add(key, k, where):
        allowed = official_sig.get(key)
        if allowed is None:
            probs.append(f"no official key {key} kind={k} @ {where}")
        elif k not in allowed:
            probs.append(f"{key}: kind {k} not in official {allowed} @ {where}")

    def walk(node, where):
        if isinstance(node, list):
            t = tag(node)
            if t in ("Command", "Event") and isinstance(node[1], list):
                c = node[1]
                if c[0] not in known_cmds:
                    probs.append(f"unknown command {c[0]}")
                for i, p in enumerate(c[1:], 1):
                    k = kind(p)
                    add(f"{c[0]}#{i}", k, where + "/" + c[0])
                    if k.startswith("enum:"):
                        for j, q in enumerate(p[1:], 1):
                            add(f"{c[0]}#{i}>{p[0]}#{j}", kind(q), f"{where}/{c[0]}#{i}")
                    if k == "list":
                        for q in p:
                            if tag(q) and tag(q) not in _EXPR_TAGS:
                                for j, r in enumerate(q[1:], 1):
                                    add(f"{q[0]}#{j}", kind(r), f"{where}/{c[0]}>{q[0]}")
            for child in node:
                walk(child, where)

    walk(tree[11], "root")
    return sorted(set(probs))


def dsl_gates(tree, *, element: int = ELEMENT) -> dict[str, Any]:
    """技能/PF 树静态门禁（与 design _tmp d8_proto.report 同口径，外加参数形状）。"""
    enc = wf_dsl.encode_amf3(tree)
    roundtrip = wf_dsl.parse_dsl(enc)["tree"] == tree
    raw = zlib.compress(enc, 9)[2:-4]
    ids = bound_ids(tree)
    return {
        "roundtrip": roundtrip,
        "deflate_bytes": len(raw),
        "wrapper": isinstance(tree, dict),
        "head_ok": isinstance(tree, list) and len(tree) == 12 and tree[0] == "ActionDsl"
                   and isinstance(tree[11], list) and tree[11][:1] == ["Block"],
        "legality_subject": L.action_dsl_subject_binding_problems(tree),
        "legality_hit_target": L.action_dsl_hit_area_target_problems(tree),
        "legality_element": L.action_dsl_element_problems(tree, element),
        "player_side": wf_dsl.player_side_dsl_problems(tree),
        "scope_strict": scope_problems(tree),
        "signature": signature_problems(tree),
        "expr_tags": expr_tag_problems(tree),
        "dup_bind_ids": sorted({i for i in ids if ids.count(i) > 1}),
        "n_attacks": len(cmds(tree, "CreateNormalAttack")),
        "movementPriority": tree[1],
        "buffTargetAs": tree[10],
        "fx_paths": sorted(set(spec_paths(tree))),
    }


GATE_LIST_KEYS = ("legality_subject", "legality_hit_target", "legality_element", "player_side",
                  "scope_strict", "signature", "expr_tags", "dup_bind_ids")


def dsl_gate_failures(gates: dict[str, Any]) -> list[str]:
    bad = [f"{k}={gates[k][:3]}" for k in GATE_LIST_KEYS if gates.get(k)]
    if not gates.get("roundtrip"):
        bad.append("roundtrip=false")
    if gates.get("wrapper") or not gates.get("head_ok"):
        bad.append("tree head/wrapper invalid")
    return bad


# ================================================================ 纯函数：行门禁

def row_problems(kind: str, row: list[str], element: int = ELEMENT) -> list[str]:
    probs = L.client_legality_problems(kind, row) + L.declared_block_field_problems(kind, row)
    if kind == "ability":
        probs += L.ability_element_column_problems(kind, row, element)
    return probs


def string_key_refs(kind: str, row: list[str]) -> list[tuple[str, int, str]]:
    """行内引用 custom_ability_string 的键：536 c70 / 629 c70（leader c68）/ 722 c82（leader）。"""
    import wf_describe
    blocks = wf_describe.layout(kind)["blocks"]
    base = int(blocks["instant_content"])
    refs = []
    content = row[base] if base < len(row) else ""
    sid_col = base + L.INVOKE_SKILL_STRING_OFFSET
    if content in ("536", "629") and sid_col < len(row):
        refs.append((content, sid_col, row[sid_col]))
    if kind == "leader_ability" and content == "722" and len(row) > 82:
        refs.append(("722", 82, row[82]))
    return refs


# ================================================================ 设计读取与派生

def load_design(root: Path) -> dict[str, Any]:
    design = json.loads((root / DESIGN_REL).read_text(encoding="utf-8"))
    ident = design.get("identity") or {}
    if design.get("status") != "final" or design.get("key") != KEY:
        raise KitError(f"design not final/philia: status={design.get('status')} key={design.get('key')}")
    if (ident.get("cid"), ident.get("code"), ident.get("element")) != (CID, CODE, ELEMENT):
        raise KitError(f"design identity drift: {ident.get('cid')}/{ident.get('code')}/{ident.get('element')}")
    return design


def _design_edit(block: dict, needle: str) -> Any:
    hits = [e["new"] for e in block["param_edits"] if needle in e["param"]]
    if len(hits) != 1:
        raise KitError(f"design block {block['order']} ({block['name']}): expected one param_edit with "
                       f"{needle!r}, got {len(hits)}")
    return hits[0]


def skill_param_drift(design: dict) -> list[str]:
    """design 侧参数核对（两档都查）。

    - 本轮 plan 没动的项（``DESIGN_TRACKED_SKILL_PARAMS``）对 ``SKILL_PARAMS``；
    - 本轮 plan 取代的项（``REVISED_SKILL_PARAMS``）对 ``SUPERSEDED_DESIGN_SKILL_PARAMS``，
      这样 design 被人改动仍然变红，而不是被改版悄悄吞掉。
    """
    drift: list[str] = []
    for level in ("1", "2"):
        blocks = {b["order"]: b for b in design["skills"][f"tree_plan_{level}"]["blocks"]}
        p = SKILL_PARAMS[level]
        old = SUPERSEDED_DESIGN_SKILL_PARAMS[level]
        pairs = {
            "fly": (_design_edit(blocks[3], "ACFlying"), slv(*p["fly"])),
            "heal": (_design_edit(blocks[4], "比例"), slv(*p["heal"])),
            "heal_slayer": (_design_edit(blocks[4], "slayer"), HEAL_SLAYER_LIGHT),
            "pfdmg_frames": (_design_edit(blocks[7], "帧"), slv(p["pfdmg_frames"], p["pfdmg_frames"])),
            "pfdmg": (_design_edit(blocks[7], "强度"), slv(*p["pfdmg"])),
            "ldatk_frames": (_design_edit(blocks[8], "帧"), slv(p["ldatk_frames"], p["ldatk_frames"])),
            "combo": (_design_edit(blocks[9], "AddCombo"), slv(*p["combo"])),
            "ldatk": (_design_edit(blocks[8], "强度"), slv(*old["ldatk"])),
            "sword": (_design_edit(blocks[10], "倍率"), slv(*old["sword"])),
            "rain": (_design_edit(blocks[11], "倍率"),
                     slv(old["rain"][0], old["rain"][1], alv_min=old["rain"][2], alv_max=old["rain"][3])),
        }
        for name, (want, have) in pairs.items():
            if want != have:
                side = "kit" if name in DESIGN_TRACKED_SKILL_PARAMS else "superseded"
                drift.append(f"skill{level}.{name}: design {want} != {side} {have}")
    return drift


def pf_param_drift(design: dict) -> list[str]:
    """design pf_override.lvN.donor（上一轮 supporter 版 4/6/8 把）对照 SUPERSEDED_PF_PARAMS。

    本轮 PF 已整体换成官方 special 底座 + 5 方向光剑（plan pf_dsl），design 这一段只作为历史基线被钉死。
    """
    import re
    drift: list[str] = []
    for level, (count, mult, delay) in SUPERSEDED_PF_PARAMS.items():
        donor = design["pf_override"][f"lv{level}"]["donor"]
        m_count = re.search(r"前\s*(\d+)\s*个", donor["locate"])
        m_wait = re.search(r"Wait\((\d+)", donor["wrap"])
        mults = [json.loads(t.split("→", 1)[1].strip()) for t in donor["transform"] if t.startswith("CNA p5")]
        want = (int(m_count.group(1)) if m_count else None, mults[0] if len(mults) == 1 else None,
                int(m_wait.group(1)) if m_wait else None)
        have = (count, slv(mult, mult), delay)
        if want != have:
            drift.append(f"pf lv{level}: design {want} != kit {have}")
        if not any("p9" in t and "false" in t for t in donor["transform"]):
            drift.append(f"pf lv{level}: design no longer turns CNA p9 buff-count bonus off")
    return drift


# ================================================================ 本轮改版真源（revision plan.json）

def load_revision(root: Path) -> dict[str, Any]:
    plan = json.loads((root / REVISION_REL).read_text(encoding="utf-8"))
    if (plan.get("key"), plan.get("cid"), plan.get("code")) != (KEY, CID, CODE):
        raise KitError(f"revision plan identity drift: {plan.get('key')}/{plan.get('cid')}/{plan.get('code')}")
    if plan.get("leader", {}).get("table") != LEADER or plan.get("abilities", {}).get("table") != ABILITY:
        raise KitError("revision plan table paths drift")
    cols = plan["column_layout"]
    if (cols["leader_ability"]["ncols"], cols["ability"]["ncols"]) != (124, 126):
        raise KitError("revision plan column counts drift")
    return plan


# ================================================================ 第二轮文案真源（revision2 strings.json）

#: 规则 1（作者 2026-09-16）：面板不再出现「无上限」三个字，没有上限的成长写到效果为止，后面什么都不跟。
FORBIDDEN_TEXT_WORDS = ("无上限", "无限叠加", "可无限", "不设上限", "上不封顶", "无次数限制", "无上限制")
#: 规则 2：能力里由 ChangeSkillFlag（536/704）驱动的「技能强化」条目不写具体数字和时间。
CHANGE_SKILL_FORBIDDEN_CHARS = "0123456789０１２３４５６７８９"
CHANGE_SKILL_FORBIDDEN_WORDS = ("秒", "帧", "％", "%")


def load_revision2(root: Path) -> dict[str, Any]:
    """本轮（第二轮）文案真源。只有 ``strings`` 段，机制项一律不在这里。"""
    doc = json.loads((root / REVISION2_REL).read_text(encoding="utf-8"))
    if (doc.get("key"), doc.get("cid"), doc.get("code")) != (KEY, CID, CODE):
        raise KitError(f"revision2 identity drift: {doc.get('key')}/{doc.get('cid')}/{doc.get('code')}")
    if doc.get("mechanism_change") is not False:
        raise KitError("revision2 claims a mechanism change; philia round 2 is text-only")
    strings = doc["strings"]
    if set(strings[CAS]["keys"]) != {CAS_PF_OVERRIDE, CAS_CHANGE_SKILL}:
        raise KitError(f"revision2 custom_ability_string keys drift: {sorted(strings[CAS]['keys'])}")
    for where, text in _revision2_texts(doc).items():
        if C.sha256(text.encode("utf-8")) != _revision2_sha(doc, where):
            raise KitError(f"revision2 {where}: text does not match its recorded sha256")
    return doc


def _revision2_texts(doc: dict[str, Any]) -> dict[str, str]:
    strings = doc["strings"]
    out = {ACTION: strings[ACTION]["value"]}
    for key, entry in strings[CAS]["keys"].items():
        out[key] = entry["value"]
    return out


def _revision2_sha(doc: dict[str, Any], where: str) -> str:
    strings = doc["strings"]
    if where == ACTION:
        return strings[ACTION]["sha256"]
    return strings[CAS]["keys"][where]["sha256"]


def text_rule_problems(texts: dict[str, str]) -> list[str]:
    """两条面板文案规则的硬门禁。

    ``texts`` 是「落点 → 玩家可见文本」的映射：规则 1 对**传进来的每一条**生效，
    规则 2 只对 ``CAS_CHANGE_SKILL``（536「技能强化」条目）那一条生效。

    ⚠ 覆盖面由**调用方**决定，本函数不自己去扫包：

    * ``build()`` 在写表前调用，喂的是本函数能在写表那一刻拿到的文案（技能说明 +
      ``character_text`` 12 列 + ``custom_ability_string`` 两键）——``character_speech``
      的字幕不由 kit 写，写表期扫不到；
    * 真正的「包内文本全集」扫描在 ``impl/philia/run_gates.py`` 的 ``panel_text_rules_round2``：
      它按 ``table_claims`` 遍历本包**全部 24 条认领**的每一个字符串单元格（含 speech 字幕）。
    """
    problems: list[str] = []
    for where, text in texts.items():
        for word in FORBIDDEN_TEXT_WORDS:
            if word in text:
                problems.append(f"{where}: 规则1 违例，出现「{word}」")
    change = texts.get(CAS_CHANGE_SKILL)
    if change is not None:
        bad_digits = sorted({ch for ch in change if ch in CHANGE_SKILL_FORBIDDEN_CHARS})
        if bad_digits:
            problems.append(f"{CAS_CHANGE_SKILL}: 规则2 违例，技能强化条目写了数字 {bad_digits}")
        for word in CHANGE_SKILL_FORBIDDEN_WORDS:
            if word in change:
                problems.append(f"{CAS_CHANGE_SKILL}: 规则2 违例，技能强化条目写了「{word}」")
        if not change.startswith("强化"):
            problems.append(f"{CAS_CHANGE_SKILL}: 规则2 违例，技能强化条目不是「强化『…』…」句式")
    return problems


def _alv_pair(text: str) -> tuple[float, float]:
    """把 plan 里的 ``"alv 0.10→0.25"`` 解析成 (min, max)。"""
    import re
    m = re.search(r"alv\s*([\d.]+)\s*→\s*([\d.]+)", str(text))
    if not m:
        raise KitError(f"cannot parse alv range from {text!r}")
    return float(m.group(1)), float(m.group(2))


def revision_param_drift(plan: dict) -> list[str]:
    """kit 常量逐项对照 plan.json 的机器可读值（DSL 侧的数值真源）。"""
    import re
    drift: list[str] = []

    def eq(name: str, want, have):
        if want != have:
            drift.append(f"{name}: plan {want!r} != kit {have!r}")

    sk = plan["skill_dsl"]
    eq("skill.tree[10]", sk["root_head"]["after"], SKILL_BUFF_TARGET_AS)
    blocks = {b["id"]: b for b in sk["blocks"]}
    b8 = blocks["block8_leader_attack"]["after"]
    eq("skill1.ldatk", [round(v, 6) for v in b8["inner1"]], [round(v, 6) for v in SKILL_PARAMS["1"]["ldatk"]])
    eq("skill2.ldatk", [round(v, 6) for v in b8["inner2"]], [round(v, 6) for v in SKILL_PARAMS["2"]["ldatk"]])
    b0 = {c["field"]: c for c in blocks["block0_stopball"]["changes"]}
    eq("skill.stopball_frames", b0["StopBall p2 停球帧数"]["after"], SKILL_STOPBALL_FRAMES)
    ch = {c["field"]: c for c in blocks["block10_swords"]["changes"]}
    eq("skill.swords", ch["单元数"]["after"], SKILL_SWORDS)
    m = re.match(r"^\s*(\d+)\s*\*\s*i", str(ch["子 Wait 帧号"]["after"]))
    eq("skill.sword_wait_step", int(m.group(1)) if m else None, SKILL_SWORD_WAIT_STEP)
    eq("skill.sword_speed", ch["MoveHitArea p3 速度"]["after"], SKILL_SWORD_SPEED)
    eq("skill.sword_hitarea_lifetime", ch["CreateHitArea p12 寿命"]["after"], SKILL_SWORD_HITAREA_LIFETIME)
    eq("skill.sword_refpoint_lifetime", ch["CreateReferencePoint p8 寿命"]["after"], SKILL_SWORD_REFPOINT_LIFETIME)
    sword = ch["CreateNormalAttack p5 倍率"]["after"]
    eq("skill1.sword", list(sword["inner1"]), list(SKILL_PARAMS["1"]["sword"]))
    eq("skill2.sword", list(sword["inner2"]), list(SKILL_PARAMS["2"]["sword"]))
    eq("skill.sword_buff_count_bonus", ch["CreateNormalAttack p9 enablesBuffCountBonus"]["after"], True)
    eq("skill.sword_total_hit_to_eliminate", ch["CreateHitArea p17 totalHitToEliminate"]["after"],
       ["Some", SWORD_TOTAL_HIT_TO_ELIMINATE])

    rain = blocks["block10b_rain_on_hit"]["node"]
    eq("skill.rain_base_id", rain["CreateReferencePoint"]["p9"], f"{SKILL_RAIN_BASE_ID}+4*i")
    eq("skill.rain_y_offset", rain["CreateReferencePoint"]["p3"], SKILL_RAIN["y_offset"])
    eq("skill.rain_lifetime", rain["CreateReferencePoint"]["p8"], SKILL_RAIN["lifetime"])
    fx, hit = rain["inner"][0], rain["inner"][1]
    eq("skill.rain_scale", fx["ShowEffect"]["p11_scale"]["after"], SKILL_RAIN["scale"])
    eq("skill.rain_radius", hit["CreateHitArea"]["p8"]["after"], ["Circle", SKILL_RAIN["radius"]])
    eq("skill.rain_max_hits", hit["CreateHitArea"]["p13"]["after"], ["CalculatedUsingMaxNumOfHits", SKILL_RAIN["max_hits"]])
    eq("skill.rain_p23", hit["CreateHitArea"]["p23"], 0)
    cna = hit["on_hit"]["CreateNormalAttack"]
    for lv, key in (("1", "inner1"), ("2", "inner2")):
        after = cna["p5_after"][key]
        eq(f"skill{lv}.rain", [after[0], after[1]], list(SKILL_PARAMS[lv]["rain"]))
        eq(f"skill{lv}.alv", list(_alv_pair(after[2])), list(SKILL_PARAMS[lv]["alv"]))
    eq("skill.rain_buff_count_bonus", cna["p9"], False)
    eq("skill.rain_shake_removed", hit["on_hit"]["ShakeCamera"]["after"], "删除")

    deb = blocks["block10c_resonance_debuff"]["node"]["ConditionalsChangeSkillFlag"]
    eq("skill.resonance_flag_index", deb["p0"], RESONANCE_FLAG_INDEX)
    cc = deb["p1_then"][1][0]["CreateCondition"]
    eq("skill.resist_kind", cc["p1"][0][0], RESIST_KIND)
    eq("skill.resist_frames", cc["p1"][0][1][0]["min"], RESIST_FRAMES)
    eq("skill.resist_value", cc["p1"][0][2][0]["min"], RESIST_VALUE)
    eq("skill.resist_target_kind", cc["p9"], RESIST_TARGET_KIND)
    eq("skill.resist_else_branch", deb["p2_else"], ["Block", []])

    pf = plan["pf_dsl"]
    eq("pf.table_key", pf["table_key"], PF_KEY)
    eq("pf.family", pf["base"]["family"], "special")
    appended = {a["id"]: a for a in pf["appended"]}
    eq("pf.support_ids", appended["P1_support_buffs"]["subject_ids"], [PF_SUPPORT_OFFSET, PF_SUPPORT_OFFSET + 1])
    p2 = appended["P2_five_way_swords"]
    eq("pf.swords", p2["count"], PF_SWORDS)
    eq("pf.launch_dirs", p2["launch_dirs"], list(PF_LAUNCH_DIRS))
    unit = p2["per_unit"]
    eq("pf.sword_explosion_bind", unit["CreateHitArea"]["p1"], PF_EXPLOSION_BIND)
    eq("pf.sword_hitarea_lifetime", unit["CreateHitArea"]["p12"],
       ["SpecifyHitAreaLifetimeDirectly", PF_SWORD_HITAREA_LIFETIME])
    eq("pf.sword_p23", unit["CreateHitArea"]["p23"], 0)
    eq("pf.sword_bind_base", unit["CreateHitArea"]["p18"], f"{PF_SUBJECT_OFFSET}+5*i")
    eq("pf.sword_total_hit_to_eliminate", unit["CreateHitArea"]["p17"],
       ["Some", SWORD_TOTAL_HIT_TO_ELIMINATE])
    stage1 = next(s for s in unit["on_create"] if s.get("stage") == 1)
    stage2 = next(s for s in unit["on_create"] if s.get("stage") == 2)
    eq("pf.sword_speed_scatter", stage1["MoveHitArea"]["p3"], PF_SWORD_SPEED_SCATTER)
    eq("pf.sword_speed_track", stage2["MoveHitArea"]["p3"], PF_SWORD_SPEED_TRACK)
    eq("pf.sword_track_wait", stage2["event"], f"Wait({PF_SWORD_TRACK_WAIT})")
    eq("pf.track_refpoint_lifetime", stage2["CreateReferencePoint"]["p8"], PF_TRACK_REFPOINT_LIFETIME)
    eq("pf.sword_buff_count_bonus", unit["on_hit"][0]["CreateNormalAttack"]["p9"], False)
    p3 = appended["P3_rain"]
    eq("pf.rain_count", p3["count"], PF_SWORDS)
    eq("pf.rain_scale", p3["overrides"]["effect_scale"], PF_RAIN["scale"])
    eq("pf.rain_radius", p3["overrides"]["hit_area_radius"], PF_RAIN["radius"])
    eq("pf.rain_max_hits", p3["overrides"]["max_num_of_hits"], PF_RAIN["max_hits"])
    eq("pf.rain_p23", p3["overrides"]["p23"], 0)
    eq("pf.rain_ids", p3["subject_ids"], f"{PF_RAIN_BASE_ID}+4*i .. {PF_RAIN_BASE_ID}+4*i+3")
    for level in (1, 2, 3):
        lv = pf["levels"][f"lv{level}"]
        eq(f"pf.lv{level}.sword", lv["sword_mult"], PF_PARAMS[level]["sword"])
        eq(f"pf.lv{level}.rain", lv["rain_mult"], PF_PARAMS[level]["rain"])
    return drift


def special_source_hashes(plan: dict) -> dict[int, str]:
    out: dict[int, str] = {}
    for level in (1, 2, 3):
        src = plan["pf_dsl"]["base"]["sources"][f"special_lv{level}"]
        if src["logical"] != wf_dsl.dsl_logical(SPECIAL_PROGRAMS[level]):
            raise KitError(f"plan special_lv{level} logical path drift: {src['logical']}")
        if not src.get("official_baseline_identical"):
            raise KitError(f"plan special_lv{level} is not官方基线逐字节相同；不得作为底座")
        out[level] = src["sha256"]
    return out


def _plan_donor_row(ctx, donor: dict, cache: dict) -> list[str]:
    flat = _donor_table(ctx, donor["source"], donor["table"], cache)
    if donor["key"] not in flat:
        raise KitError(f"revision donor {donor['table']}#{donor['key']} missing from {donor['source']}")
    rows = C.csv_split(flat[donor["key"]])
    if donor["record"] >= len(rows):
        raise KitError(f"revision donor {donor['key']} has no record {donor['record']}")
    return list(rows[donor["record"]])


def _apply_edits(row: list[str], edits: dict, ncols: int, label: str) -> list[str]:
    out = list(row)
    for col, value in (edits or {}).items():
        index = int(col)
        if index >= ncols:
            raise KitError(f"{label}: edit column c{index} out of range ({ncols})")
        out[index] = value
    if len(out) != ncols:
        raise KitError(f"{label}: ncols {len(out)} != {ncols}")
    return out


def _check_after(row: list[str], entry: dict, label: str) -> None:
    want = entry.get("full_row_after")
    if want is None:
        return
    if row != want:
        diff = [(i, row[i] if i < len(row) else None, want[i] if i < len(want) else None)
                for i in range(max(len(row), len(want)))
                if (row[i] if i < len(row) else None) != (want[i] if i < len(want) else None)]
        raise KitError(f"{label}: revised row != plan full_row_after: {diff[:5]}")


def revise_leader(ctx, base_rows: list[list[str]], plan: dict, cache: dict) -> tuple[list[list[str]], list[dict]]:
    entries = plan["leader"]["rows"]
    if len(entries) != len(base_rows):
        raise KitError(f"revision leader rows {len(entries)} != design rows {len(base_rows)}")
    rows, trace = [], []
    for entry in entries:
        index, action = entry["index"], entry["action"]
        label = f"leader#{index}"
        if [e["index"] for e in entries] != list(range(len(entries))):
            raise KitError("revision leader row indices are not 0..n-1")
        if action == "keep":
            row, source = list(base_rows[index]), "design"
        elif action == "edit":
            row = _apply_edits(base_rows[index], entry["edits"], 124, label)
            source = "design+edits"
        elif action == "replace":
            donor = entry["donor"]
            row = _apply_edits(_plan_donor_row(ctx, donor, cache), entry["edits_from_donor"], 124, label)
            source = f"{donor['source']} {donor['table']}#{donor['key']}[{donor['record']}]"
        else:
            raise KitError(f"{label}: unknown revision action {action!r}")
        _check_after(row, entry, label)
        rows.append(row)
        trace.append({"index": index, "action": action, "source": source,
                      "requirement": entry.get("requirement", []),
                      "describe_after": entry.get("describe_after", entry.get("describe_before"))})
    return rows, trace


def revise_abilities(ctx, base_by_key: dict[str, list[list[str]]], plan: dict,
                     cache: dict) -> tuple[dict[str, list[list[str]]], dict[str, list[dict]]]:
    """按 plan 覆盖词条记录：edit / move_in / new(built_from|donor)，并核对 base 每条都有去处。"""
    keys = plan["abilities"]["keys"]
    consumed: dict[str, set[int]] = {key: set() for key in keys}
    out: dict[str, list[list[str]]] = {}
    trace: dict[str, list[dict]] = {}
    for key, spec_ in keys.items():
        if key not in base_by_key:
            raise KitError(f"revision ability key {key} absent from design")
        base = base_by_key[key]
        rows: list[list[str]] = []
        entries: list[dict] = []
        for entry in spec_["records"]:
            record, action = entry["record"], entry["action"]
            label = f"{key}#{record}"
            if record != len(rows):
                raise KitError(f"{label}: revision records must be listed in order")
            if action == "edit":
                src_index = entry.get("was_record", record)
                consumed[key].add(src_index)
                row = _apply_edits(base[src_index], entry["edits"], 126, label)
                source = f"design {key}[{src_index}]"
            elif action == "move_in":
                moved = entry["moved_from"]
                consumed.setdefault(moved["key"], set()).add(moved["record"])
                row = _apply_edits(base_by_key[moved["key"]][moved["record"]], entry["edits"], 126, label)
                source = f"design {moved['key']}[{moved['record']}]"
            elif action == "new" and "built_from" in entry:
                built = entry["built_from"]
                pool = rows if built["key"] == key else out.get(built["key"])
                if pool is None or built["record"] >= len(pool):
                    raise KitError(f"{label}: built_from {built} not available yet")
                row = _apply_edits(pool[built["record"]], entry["edits_from_base"], 126, label)
                source = f"revised {built['key']}#{built['record']}"
            elif action == "new":
                donor = entry["donor"]
                row = _apply_edits(_plan_donor_row(ctx, donor, cache), entry["edits_from_donor"], 126, label)
                source = f"{donor['source']} {donor['table']}#{donor['key']}[{donor['record']}]"
            else:
                raise KitError(f"{label}: unknown revision action {action!r}")
            _check_after(row, entry, label)
            if row[1] != spec_["c1"] or row[2] != spec_["c2"]:
                raise KitError(f"{label}: c1/c2 {row[1]}/{row[2]} != plan {spec_['c1']}/{spec_['c2']}")
            rows.append(row)
            entries.append({"record": record, "action": action, "source": source,
                            "requirement": entry.get("requirement", []),
                            "describe_after": entry.get("describe_after")})
        out[key] = rows
        trace[key] = entries
    for key, spec_ in keys.items():
        removed = {item["record"] for item in spec_.get("removed", [])}
        accounted = consumed[key] | removed
        want = set(range(len(base_by_key[key])))
        if accounted != want:
            raise KitError(f"{key}: design records {sorted(want - accounted)} unaccounted / "
                           f"{sorted(accounted - want)} out of range")
    return out, trace


def _donor_table(ctx, source: str, table: str, cache: dict) -> dict[str, str]:
    logical = f"master/ability/{table}.orderedmap"
    if source.startswith("官方"):
        kind = "official"
    elif source.startswith("live"):
        kind = "live"
    else:
        raise KitError(f"unknown donor source {source!r}")
    if (kind, logical) not in cache:
        cache[(kind, logical)] = ctx.official_flat(logical) if kind == "official" else ctx.live_flat(logical)
    return cache[(kind, logical)]


def derive_rows(ctx, entries: list[dict], table: str, label: str,
                cache: dict | None = None) -> tuple[list[list[str]], list[dict]]:
    cache = {} if cache is None else cache
    rows, trace = [], []
    for n, entry in enumerate(entries):
        flat = _donor_table(ctx, entry["donor_source"], table, cache)
        if entry["donor"] not in flat:
            raise KitError(f"{label}#{n}: donor {entry['donor']} missing from {entry['donor_source']}")
        donor_rows = C.csv_split(flat[entry["donor"]])
        row = list(donor_rows[entry["row_index"]])
        for col, want in entry.get("donor_before", {}).items():
            if row[int(col)] != want:
                raise KitError(f"{label}#{n}: donor {entry['donor']} c{col}={row[int(col)]!r} != design {want!r}")
        for col, value in entry["edits"].items():
            row[int(col)] = value
        if row != entry["full_row"]:
            diff = [(i, a, b) for i, (a, b) in enumerate(zip(row, entry["full_row"])) if a != b]
            raise KitError(f"{label}#{n}: derived row != design full_row: {diff[:5]}")
        if len(row) != entry["ncols"]:
            raise KitError(f"{label}#{n}: ncols {len(row)} != {entry['ncols']}")
        rows.append(row)
        trace.append({"donor": entry["donor"], "row_index": entry["row_index"],
                      "source": entry["donor_source"], "edits": entry["edits"]})
    return rows, trace


# ================================================================ 特效：fx 染色钩子

def load_fx_manifest(root: Path) -> tuple[dict[str, dict], dict[str, Any]]:
    """``fx/philia/out/manifest.json`` → {源 sheet 逻辑路径: {"file": Path, "allow_alpha_change": bool}}。

    接受三种写法（值为相对 manifest 目录的 PNG 路径，或 {"file"/"png": 路径, "allow_alpha_change": bool}）：
    ``{"sheets": {源: 值}}``、``{"entries": [{"source": 源, "file": 路径}]}``、或顶层直接 ``{源: 值}``。
    源可写 sheet 逻辑路径（``…/wind_oracle_1anv/wind_oracle_1anv.png``）或源目录（``…/wind_oracle_1anv``）。
    """
    path = root / FX_MANIFEST_REL
    info: dict[str, Any] = {"path": FX_MANIFEST_REL, "present": path.is_file()}
    if not path.is_file():
        return {}, info
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and data.get("all_gates_ok") is False:
        raise KitError(f"{FX_MANIFEST_REL}: Effects stage reports all_gates_ok=false")
    details = data.get("details") if isinstance(data, dict) and isinstance(data.get("details"), dict) else {}
    items: list[tuple[str, Any]] = []
    if isinstance(data, dict) and isinstance(data.get("sheets"), dict):
        items = list(data["sheets"].items())
    elif isinstance(data, dict) and isinstance(data.get("entries"), list):
        for entry in data["entries"]:
            if isinstance(entry, dict) and "source" in entry:
                items.append((entry["source"], entry))
    elif isinstance(data, dict):
        items = [(k, v) for k, v in data.items() if isinstance(k, str) and k.startswith("battle/")]
    out: dict[str, dict] = {}
    for source, value in items:
        source = str(source).rstrip("/")
        if not source.endswith(".png"):
            donor = source.rsplit("/", 1)[-1]
            source = f"{source}/{donor}.png"
        if isinstance(value, str):
            file, allow = value, False
        elif isinstance(value, dict):
            file = value.get("file") or value.get("png") or value.get("path")
            allow = bool(value.get("allow_alpha_change", False))
        else:
            raise KitError(f"fx manifest entry for {source} has unsupported value {value!r}")
        if not file:
            raise KitError(f"fx manifest entry for {source} lacks a PNG file")
        file_path = (path.parent / file).resolve()
        if not file_path.is_file():
            raise KitError(f"fx manifest PNG missing: {file_path}")
        detail = details.get(source) if isinstance(details.get(source), dict) else {}
        if detail.get("gates_all_ok") is False:
            raise KitError(f"fx manifest entry {source}: Effects stage gates_all_ok=false")
        out[source] = {"file": file_path, "allow_alpha_change": allow,
                       "source_rgba_sha256": detail.get("source_rgba_sha256"),
                       "out_rgba_sha256": detail.get("out_rgba_sha256")}
    info["entries"] = {k: {"file": str(v["file"]), "allow_alpha_change": v["allow_alpha_change"],
                           "sha256": C.sha256(v["file"].read_bytes()),
                           "source_rgba_sha256": v["source_rgba_sha256"],
                           "out_rgba_sha256": v["out_rgba_sha256"]} for k, v in sorted(out.items())}
    return out, info


def make_png_transform(sheet_logical: str, override: dict | None, log: dict[str, Any]):
    """无覆盖返回 None（官方原色）；有覆盖时整张替换并核对尺寸 / alpha。"""
    if override is None:
        log[sheet_logical] = {"recolor": None}
        return None

    def transform(img):
        from PIL import Image
        img = img.convert("RGBA")
        want_src = override.get("source_rgba_sha256")
        if want_src and hashlib.sha256(img.tobytes()).hexdigest() != want_src:
            raise KitError(f"fx recolor {sheet_logical}: source sheet RGBA drifted from what Effects stage recolored")
        raw = override["file"].read_bytes()
        new = C.png_open(raw) if raw[:4] == b"\x89png" else Image.open(io.BytesIO(raw)).convert("RGBA")
        want_out = override.get("out_rgba_sha256")
        if want_out and hashlib.sha256(new.tobytes()).hexdigest() != want_out:
            raise KitError(f"fx recolor {sheet_logical}: recolored PNG RGBA != manifest out_rgba_sha256")
        if new.size != img.size:
            raise KitError(f"fx recolor {sheet_logical}: size {new.size} != source {img.size} (atlas rects break)")
        alpha_changed = sum(1 for a, b in zip(img.getchannel("A").tobytes(), new.getchannel("A").tobytes())
                            if a != b)
        if alpha_changed and not override["allow_alpha_change"]:
            raise KitError(f"fx recolor {sheet_logical}: {alpha_changed} alpha pixels changed "
                           "(design rule: RGB only; set allow_alpha_change to accept)")
        log[sheet_logical] = {"recolor": str(override["file"]), "size": list(new.size),
                              "alpha_changed_pixels": alpha_changed}
        return new
    return transform


# ================================================================ 技能 / PF 组树

def _source_tree(ctx, program: str, want_sha: str | None) -> list:
    logical = wf_dsl.dsl_logical(program)
    raw = ctx.official_read(logical, "common")
    source = "official"
    if raw is None:
        raw = ctx.live_read(logical)
        source = "live"
    if want_sha is not None and C.sha256(raw) != want_sha:
        raise KitError(f"source DSL fingerprint drift ({source}): {program}")
    return ctx.template_dsl(program) if source == "official" else C.amf_parse(raw)


def design_source_hashes(design: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for plan in ("tree_plan_1", "tree_plan_2"):
        for block in design["skills"][plan]["blocks"]:
            src = block["source"]
            if out.setdefault(src["dsl"], src["sha256"]) != src["sha256"]:
                raise KitError(f"design lists two hashes for {src['dsl']}")
    return out


def _one_cmd(node, name: str) -> list:
    hits = cmds(node, name)
    if len(hits) != 1:
        raise KitError(f"expected exactly one {name}, got {len(hits)}")
    return hits[0]


def slow_sword_unit(unit, *, speed: int, hit_lifetime: int, ref_lifetime: int, mult) -> None:
    """R2：一个 1anv 光剑单元就地放慢（速度 / 判定区寿命 / 参考点寿命）并按档写倍率。"""
    move = _one_cmd(unit, "MoveHitArea")
    if move[4] != 30:
        raise KitError(f"1anv sword MoveHitArea speed drift: {move[4]}")
    move[4] = speed
    crp = _one_cmd(unit, "CreateReferencePoint")
    if crp[9] != 60:
        raise KitError(f"1anv sword CreateReferencePoint lifetime drift: {crp[9]}")
    crp[9] = ref_lifetime
    cha = _one_cmd(unit, "CreateHitArea")
    if cha[13] != ["SpecifyHitAreaLifetimeDirectly", 60]:
        raise KitError(f"1anv sword CreateHitArea lifetime drift: {cha[13]}")
    cha[13] = ["SpecifyHitAreaLifetimeDirectly", hit_lifetime]
    if cha[18] != ["None"]:
        raise KitError(f"1anv sword CreateHitArea p17 totalHitToEliminate drift: {cha[18]}")
    cha[18] = ["Some", SWORD_TOTAL_HIT_TO_ELIMINATE]      # R3b：一把剑只结算一次 → 一份剑雨
    if cha[24] != 0:
        raise KitError("sword CreateHitArea p23 must stay 0")
    atk = _one_cmd(unit, "CreateNormalAttack")
    if atk[10] is not True:
        raise KitError("1anv sword CNA p9 enablesBuffCountBonus expected true")
    atk[6] = slv(*mult)


def make_rain(rain_donor: list, *, anchor: int, base: int, mult, alv, y_offset: int, lifetime: int,
              scale: float, radius: int, max_hits: int) -> list:
    """命中点剑雨子树：克隆 meteor23 的 CreateReferencePoint 整块，锚到命中位置，删 ShakeCamera。

    母本 RP 挂球、CHA 在 −260、演出在 −190；把 RP 整体下移 +260 让 CHA 正好落在命中点，
    内部两个偏移一格不动（最小改动面）。10/5 份同时在场，所以演出 scale、半径、期望命中数都降档
    （wf-battle-atlas-budget / wf-maou-fx-lag：卡顿判据是单帧面片峰值）。
    """
    node = copy.deepcopy(rain_donor)
    remap_subjects(node, {0: base, 1: base + 1, 2: base + 2, 3: base + 3}.__getitem__)
    rp = node[1]
    if rp[0] != "CreateReferencePoint" or rp[1] != -18 or rp[9] != 160:
        raise KitError(f"rain donor drift: {rp[:2]} lifetime={rp[9]}")
    rp[1] = anchor
    if rp[4] != 0:
        raise KitError(f"rain donor RP y offset expected 0, got {rp[4]}")
    rp[4] = y_offset
    rp[9] = lifetime
    fx = _one_cmd(node, "ShowEffect")
    if fx[12][0] != "Some":
        raise KitError(f"rain ShowEffect scale shape drift: {fx[12]}")
    fx[12] = ["Some", slv(scale, scale)]
    cha = _one_cmd(node, "CreateHitArea")
    if cha[9][0] != "Circle" or cha[14][0] != "CalculatedUsingMaxNumOfHits":
        raise KitError("rain CreateHitArea shape drift")
    cha[9] = ["Circle", slv(radius, radius)]
    cha[14] = ["CalculatedUsingMaxNumOfHits", max_hits]
    if cha[24] != 0:
        raise KitError("rain CreateHitArea p23 must stay 0")
    on_hit = cha[23][1]
    kept = [e for e in on_hit if not (e[0] == "Command" and e[1][0] == "ShakeCamera")]
    if len(kept) != len(on_hit) - 1:
        raise KitError("rain donor lost its single ShakeCamera anchor")
    on_hit[:] = kept
    atk = _one_cmd(node, "CreateNormalAttack")
    if atk[10] is not False:
        raise KitError("rain CNA p9 enablesBuffCountBonus expected false")
    atk[6] = slv(mult[0], mult[1], alv_min=alv[0], alv_max=alv[1]) if alv else slv(mult[0], mult[1])
    return node


def make_resonance_debuff(target: int, template: list) -> list:
    """R29：共鸣（536 旗标）时对命中的敌人挂强化弹射伤害抗性下降。

    ``ConditionalsChangeSkillFlag(n, then, else)`` → ``Environment.hasAbilityPower(n)``；536 行硬写
    ability power index = 1（``InstantAbilitySource.as:5015-5018``，官方 62/62 处 p0 都是 1）。
    **else 分支必须 ``["Block", []]``**：写 ``["DoNothing"]`` 进游戏 F1009（wf-dsl-donothing-enum-trap）。
    """
    cond = copy.deepcopy(template)
    if cond[0] != "CreateCondition" or cond[4] != ["GenericConditionHitEffect"]:
        raise KitError("resonance debuff template must be an official GenericConditionHitEffect CreateCondition")
    cond[1] = target
    cond[2] = [[RESIST_KIND, slv(RESIST_FRAMES, RESIST_FRAMES), slv(RESIST_VALUE, RESIST_VALUE), slv(1, 1)]]
    cond[3] = slv(1, 1)
    cond[10] = RESIST_TARGET_KIND
    cond[11] = slv(1, 1)
    # ⚠ 外层 ``["Command", …]`` 不是可选的：``ConditionalsChangeSkillFlag`` 是 ActionDslCommand 的构造，
    # 表达式位只认 Block/Event/Command（官方 kyouka_1 / still_obstinator_1 祖先链同形）。
    # 缺壳 = 详情页/战斗加载 AS3 #1034，往返自检抓不到（2026-09-16 审查 blocker）。
    return ["Command", ["ConditionalsChangeSkillFlag", RESONANCE_FLAG_INDEX,
                        ["Block", [["Command", cond]]], ["Block", []]]]


def build_skill_tree(ctx, level: str, params: dict, families: list[dict], hashes: dict[str, str]):
    wo = _source_tree(ctx, f"{SKILL_SRC}wind_oracle$wind_oracle_{level}",
                      hashes.get(f"{SKILL_SRC}wind_oracle$wind_oracle_{level}"))
    av = _source_tree(ctx, f"{SKILL_SRC}wind_oracle_1anv$wind_oracle_1anv_{level}",
                      hashes.get(f"{SKILL_SRC}wind_oracle_1anv$wind_oracle_1anv_{level}"))
    mt = _source_tree(ctx, f"{SKILL_SRC}wind_oracle_meteor23$wind_oracle_meteor23_{level}",
                      hashes.get(f"{SKILL_SRC}wind_oracle_meteor23$wind_oracle_meteor23_{level}"))
    lb = _source_tree(ctx, f"{SKILL_SRC}light_ballot23$light_ballot23_2",
                      hashes[f"{SKILL_SRC}light_ballot23$light_ballot23_2"])
    wb, ab, mb, lbb = wo[11][1], av[11][1], mt[11][1], lb[11][1]
    stop = find_one(mb, is_cmd("StopBall"), "meteor23 StopBall")
    fx_all = find_one(mb, is_cmd("ShowEffect"), "meteor23 ShowEffect 全体演出")
    rain = find_one(mb, is_cmd("CreateReferencePoint"), "meteor23 CreateReferencePoint")
    charge = find_one(ab, is_cmd("ShowEffect"), "1anv ShowEffect チャージ演出")
    swords = find_one(ab, lambda e: e[0] == "Event" and e[1][0] == "Wait" and e[1][1] == 20, "1anv Wait(20)")
    self_atk = find_one(ab, lambda e: (e[0] == "Command" and e[1][0] == "CreateCondition"
                                       and e[1][2][0][0] == "ACAttackPoint"), "1anv self ACAttackPoint")
    fly = find_one(wb, is_find_all(33), "wind_oracle FindAll(33)")
    heal113 = find_one(wb, is_find_all(113), "wind_oracle FindAll(113)")
    heal145 = find_one(wb, is_find_all(145), "wind_oracle FindAll(145)")
    heal_mate = find_one(wb, is_cmd("CreateRatioHeal", p1=-33), "wind_oracle CreateRatioHeal(-33)")
    pf_dmg = find_one(lbb, is_find_all(97), "light_ballot23 FindAll(97)")
    leader_atk = find_one(lbb, is_find_all(34), "light_ballot23 FindAll(34)")
    add_combo = find_one(lbb, is_cmd("AddCombo"), "light_ballot23 AddCombo")
    # 定位特征核对（design tree_plan locate）
    if stop[1][1] != -18 or stop[1][3] != ["Stop"] or stop[1][2] != 80:
        raise KitError(f"StopBall shape drift: {stop[1][:4]}")
    stop[1][2] = SKILL_STOPBALL_FRAMES          # R2b：停球窗口盖住最后一把光剑（20 + 9*9 = 101 帧）
    if (fx_all[1][1], fx_all[1][3]) != ("全体演出", -1) or (charge[1][1], charge[1][3]) != ("チャージ演出", -18):
        raise KitError("ShowEffect label/subject drift in meteor23/1anv sources")
    if rain[1][1] != -18 or rain[1][9] != 160:
        raise KitError(f"rain CreateReferencePoint drift: origin={rain[1][1]} lifetime={rain[1][9]}")
    if self_atk[1][1] != -17:
        raise KitError("1anv self ACAttackPoint subject drift")
    head = ["ActionDsl", 2, ["None"], False, False, False, False, False, False, False, 0]
    if mt[:11] != head:
        raise KitError(f"meteor23 head drift: {mt[:11]}")

    remap_subjects(fly, {0: 110}.__getitem__)
    remap_subjects(heal113, {1: 111}.__getitem__)
    remap_subjects(heal145, {2: 112}.__getitem__)
    remap_subjects(pf_dmg, {1: 120}.__getitem__)
    remap_subjects(leader_atk, {0: 121}.__getitem__)
    # 作者 2026-09-21 真机反馈第 3 轮：「之前做的菲莉亚也去掉浮游效果」。
    # 母本 `wind_oracle` 的 FindAll(33) → ACFlying 整块**仍然逐项校验**（母本被改了要变红），
    # 但不再进 body：去掉后这条搜索块会空掉、绑定 110 无人引用，等价于整条摘除。
    # 与 live 侧的节点级删除（wf_philia_no_flying_revision.strip_flying）结果逐节点一致。
    fly_cc = cmds(fly, "CreateCondition")
    if len(fly_cc) != 1 or fly_cc[0][2][0][0] != "ACFlying":
        raise KitError("fly block drift")
    fly_cc[0][2][0][1] = slv(*params["fly"])
    heals = cmds(heal113, "CreateRatioHeal") + cmds(heal145, "CreateRatioHeal") + [heal_mate[1]]
    if len(heals) != 3:
        raise KitError("heal blocks drift")
    for h in heals:
        h[3] = slv(*params["heal"])
        h[4] = list(HEAL_SLAYER_LIGHT)
    pc = cmds(pf_dmg, "CreateCondition")
    lc = cmds(leader_atk, "CreateCondition")
    if len(pc) != 1 or pc[0][2][0][0] != "ACPowerFlipDamage" or pc[0][10] != 2:
        raise KitError("light_ballot23 97 block drift (ACPowerFlipDamage / 付与种类 2)")
    if len(lc) != 1 or lc[0][2][0][0] != "ACAttackPoint" or lc[0][10] != 1:
        raise KitError("light_ballot23 34 block drift (ACAttackPoint / 付与种类 1)")
    cond_template = copy.deepcopy(pc[0])          # 官方 GenericConditionHitEffect 形状，供 R29 debuff 用
    pc[0][2][0][1] = slv(params["pfdmg_frames"], params["pfdmg_frames"])
    pc[0][2][0][2] = slv(*params["pfdmg"])
    lc[0][2][0][1] = slv(params["ldatk_frames"], params["ldatk_frames"])
    lc[0][2][0][2] = slv(*params["ldatk"])
    add_combo[1][1] = slv(*params["combo"])

    # ---- R1/R2/R15：16 把 → 前 10 把，间隔 4→9 帧，速度 30→18，寿命 60→100/110，倍率按档
    units = swords[1][3][1]
    if [e[1][1] for e in units] != [4 * i for i in range(16)]:
        raise KitError(f"1anv sword sub-waits drift: {[e[1][1] for e in units][:4]}")
    del units[SKILL_SWORDS:]
    for i, unit in enumerate(units):
        unit[1][1] = SKILL_SWORD_WAIT_STEP * i
        slow_sword_unit(unit, speed=SKILL_SWORD_SPEED, hit_lifetime=SKILL_SWORD_HITAREA_LIFETIME,
                        ref_lifetime=SKILL_SWORD_REFPOINT_LIFETIME, mult=params["sword"])
        cha = _one_cmd(unit, "CreateHitArea")
        # ---- R29：共鸣（536 旗标）时对命中的敌人挂强化弹射伤害抗性下降；R3：命中位置降剑雨
        cha[23][1].append(make_resonance_debuff(cha[22], cond_template))
        cha[23][1].append(make_rain(rain, anchor=cha[21], base=SKILL_RAIN_BASE_ID + 4 * i,
                                    mult=params["rain"], alv=params["alv"], **SKILL_RAIN))
    if len(cmds(swords, "CreateNormalAttack")) != 2 * SKILL_SWORDS:
        raise KitError("sword+rain attack count drift")

    # ---- R3：原「球上方一次剑雨」整块删除（由 10 份命中点剑雨取代）
    body = [stop, fx_all, charge, heal113, heal145, heal_mate, pf_dmg, leader_atk, add_combo,
            swords, self_atk]                               # `fly` 已按作者要求不再产出（见上）
    tree = head[:10] + [SKILL_BUFF_TARGET_AS] + [["Block", body]]   # R16：tree[10]=3 走强化弹射乘区
    from wf_philia_wind_revision import revise_skill
    rewritten, counts = rewrite_all(ctx, tree, families)
    return revise_skill(rewritten), counts


def rewrite_all(ctx, tree, families: list[dict]):
    counts = {}
    for fam in families:
        tree, info = ctx.rewrite_effect_refs(tree, fam, strict=True)
        counts[fam["dst_dir"]] = info["rewritten"]
    return tree, counts


def supporter_raw(root: Path, level: int) -> bytes:
    name = f"supporter_lv{level}{GPF.SUFFIX}"
    for rel in SUPPORTER_SOURCES:
        path = root / rel / name
        if path.is_file():
            raw = path.read_bytes()
            if C.sha256(raw) != GPF.SOURCE_HASHES[f"supporter_lv{level}"]:
                raise KitError(f"official supporter PF lv{level} fingerprint drift: {path}")
            return raw
    raise KitError(f"official supporter PF lv{level} source not found in {SUPPORTER_SOURCES}")


def pf_support_block(root: Path, level: int, *, keep_flying: bool = True) -> list:
    """P1：从官方 supporter_lv{n} 克隆「FindAllSubjects(33) → ACAttackPoint / ACPiercing / ACFlying」整块。

    作者只说「改为特殊类型」，没说撤掉辅助增益；``override_string`` 一直写着这三件，而 special 底座本身不带，
    直接换底座 = 静默砍功能。要纯 special 就删这一块（一个开关）。

    作者 2026-09-21 真机反馈第 3 轮「去掉浮游效果」只点名了菲莉亚与澄波响：donor 永远按官方三件校验
    （母本变了要变红）；``keep_flying=False`` 时克隆出来的块只留 ACAttackPoint / ACPiercing，与 live 侧的
    节点级删除（``wf_philia_no_flying_revision.strip_flying``）结果逐节点一致。**默认保留三件套**——
    这个函数同时被芙拉菲、丝缇涅尔、澄波响的中秋 kit 借用，默认行为一变就会连坐没被点名的角色
    （芙拉菲硬断言三件套会直接建包失败，丝缇涅尔会静默丢浮游）。
    """
    base = C.amf_parse(supporter_raw(root, level))
    if base[0] != "ActionDsl" or base[1] != 1 or base[10] != 0:
        raise KitError(f"supporter lv{level} head drift: {base[:11]}")

    def is_buffs(entry) -> bool:
        return (entry[0] == "Command" and entry[1][0] == "FindAllSubjects" and entry[1][2] == 33
                and [c[2][0][0] for c in cmds(entry, "CreateCondition")]
                == ["ACAttackPoint", "ACPiercing", "ACFlying"])

    block = find_one(base[11][1], is_buffs, f"supporter lv{level} 辅助增益块")
    if cmds(block, "ShowEffect") or cmds(block, "CreateNormalAttack"):
        raise KitError("supporter buff block unexpectedly holds effects/attacks")
    # 各档母本的绑定 id 不同（lv1=1、lv3=4…），统一归到 400 段，三档 id 一致
    order = {old: PF_SUPPORT_OFFSET + n for n, old in enumerate(dict.fromkeys(bound_ids(block)))}
    if len(order) > 2:
        raise KitError(f"supporter buff block binds {len(order)} subjects (reserved 400/401 only)")
    remap_subjects(block, order.__getitem__)
    if keep_flying:
        return block
    inner = block[1][9][1]
    flying = [st for st in inner if st[0] == "Command" and st[1][0] == "CreateCondition"
              and [kind[0] for kind in st[1][2]] == ["ACFlying"]]
    if len(flying) != 1:
        raise KitError(f"supporter lv{level} ACFlying statement drift: {len(flying)}")
    inner.remove(flying[0])
    if [c[2][0][0] for c in cmds(block, "CreateCondition")] != ["ACAttackPoint", "ACPiercing"]:
        raise KitError(f"supporter lv{level} buff block must keep exactly attack + piercing")
    return block


def pf_sword_unit(donor_unit: list, *, bind_base: int, launch_dir: float, mult: float, rain: list) -> list:
    """P2/P3：一把爆炸中心放射的追踪光剑（含命中点剑雨）。

    官方直接对照 = ``override_haniwa_green_burst_lv{1,2,3}``：同为 special 骨架，在爆炸中心 RP 里
    ``CreateHitArea(p1=RP, p2=["AB"], p5=朝向)`` + ``MoveHitArea(bind, ["CD"], 0, 速度)`` 放射发弹。
    第二段改向（同一 bind 两次 MoveHitArea，官方 261 处）把它转成追踪；搜索原点写 −18（球）而不是
    爆炸中心 RP —— 后者寿命只有 20/30 帧。
    """
    unit = copy.deepcopy(donor_unit)
    crp = _one_cmd(unit, "CreateReferencePoint")
    cha_node = copy.deepcopy(find_one(crp[11][1], is_cmd("CreateHitArea"), "1anv_2 光剑 CreateHitArea"))
    remap_subjects(cha_node, {1: 1, 2: bind_base, 3: bind_base + 1, 4: bind_base + 2}.__getitem__)
    cha = cha_node[1]
    if cha[2] != -18 or cha[3] != ["GH", 1]:
        raise KitError(f"1anv_2 光剑 CreateHitArea 母本形状漂移: p1={cha[2]} p2={cha[3]}")
    cha[2] = PF_EXPLOSION_BIND                      # p1：挂爆炸中心（创建瞬间取位置，trackingPos=false）
    cha[3] = ["AB"]                                 # p2：绝对坐标系
    cha[6] = launch_dir                             # p5：朝向 = 放射角
    cha[13] = ["SpecifyHitAreaLifetimeDirectly", PF_SWORD_HITAREA_LIFETIME]
    if cha[18] != ["None"]:
        raise KitError(f"1anv_2 光剑 CreateHitArea p17 totalHitToEliminate drift: {cha[18]}")
    cha[18] = ["Some", SWORD_TOTAL_HIT_TO_ELIMINATE]      # R3b：一把剑只结算一次 → 一份剑雨
    if cha[24] != 0:
        raise KitError("PF sword CreateHitArea p23 must stay 0 (4 skips the PF damage bucket)")

    on_create = cha[20][1]
    shoot = next(e[1] for e in on_create if e[0] == "Command" and e[1][0] == "ShowEffect"
                 and e[1][1] == "発射演出")
    shoot[3] = PF_EXPLOSION_BIND
    shoot[6] = ["AB"]
    move = _one_cmd(cha_node, "MoveHitArea")
    if move[1] != bind_base or move[2] != ["GH", 1]:
        raise KitError(f"1anv_2 光剑 MoveHitArea 母本形状漂移: {move[:3]}")
    move[2] = ["CD"]                                # 第一段：按自身朝向散射
    move[4] = PF_SWORD_SPEED_SCATTER

    # 第二段：Wait(10) 后搜最近敌人，建参考点，改向追踪（官方 Event-in-p19 1842 处 / 412 个程序）
    shell = copy.deepcopy(find_one(unit[1][3][1], is_cmd("FindNearSubjects"), "1anv_2 FindNearSubjects"))
    track_rp = _one_cmd(shell, "CreateReferencePoint")
    if track_rp[11][0] != "Block" or len(track_rp[11][1]) != 1:
        raise KitError("1anv_2 追踪参考点母本形状漂移")
    track_rp[9] = PF_TRACK_REFPOINT_LIFETIME
    track_rp[11] = ["Block", []]                    # 先清空，重映射后再挂 MoveHitArea（它引用 CHA 绑定）
    remap_subjects(shell, {0: bind_base + 3, 1: bind_base + 4}.__getitem__)
    turn = copy.deepcopy(move)
    turn[2] = ["GH", bind_base + 4]
    turn[4] = PF_SWORD_SPEED_TRACK
    _one_cmd(shell, "CreateReferencePoint")[11] = ["Block", [["Command", turn]]]
    on_create.append(["Event", ["Wait", PF_SWORD_TRACK_WAIT, "*", ["Block", [shell]]]])

    on_hit = cha[23][1]
    atk = next(e[1] for e in on_hit if e[0] == "Command" and e[1][0] == "CreateNormalAttack")
    if atk[10] is not True:
        raise KitError("1anv sword CNA p9 expected true before PF override")
    atk[6] = slv(mult, mult)
    atk[10] = False                                 # PF 光剑不吃增益数加成（审查 minor#8）
    on_hit.append(rain)
    return cha_node


def build_pf_tree(ctx, level: int, donor_1anv_2: list, rain_donor: list, families: list[dict],
                  special_hashes: dict[int, str]):
    """R4–R7：官方 special_lv{n} 整树作底座 + 辅助增益块 + 爆炸中心 5 方向追踪光剑 + 每把命中点剑雨。"""
    params = PF_PARAMS[level]
    tree = _source_tree(ctx, SPECIAL_PROGRAMS[level], special_hashes[level])
    if tree[0] != "ActionDsl" or tree[1] != 1 or tree[10] != 0:
        raise KitError(f"special lv{level} head drift: {tree[:11]}")
    root_body = tree[11][1]
    aura = [n for n, e in enumerate(root_body)
            if e[0] == "Command" and e[1][0] == "ShowEffect" and e[1][1] == "オーラ演出"]
    if len(aura) != 1:
        raise KitError("special base オーラ演出 not unique")
    if len([e for e in events(tree) if e[0] == "CollisionOfBallAndEnemy"]) != 1:
        raise KitError("special base CollisionOfBallAndEnemy not unique")
    if not cmds(tree, "SetPowerFilpSuppress") or not cmds(tree, "NotifyPowerflipEnd"):
        raise KitError("special base lost suppress / NotifyPowerflipEnd")
    root_body.insert(aura[0] + 1, pf_support_block(ctx.root, level, keep_flying=False))

    burst = [c for c in cmds(tree, "CreateReferencePoint") if c[10] == PF_EXPLOSION_BIND and c[1] == -18]
    if len(burst) != 1:
        raise KitError("special base explosion-centre CreateReferencePoint not unique")
    outers = [e for e in donor_1anv_2[11][1] if e[0] == "Event" and e[1][0] == "Wait" and e[1][1] == 20]
    if len(outers) != 1:
        raise KitError("1anv_2 Wait(20) sword unit not unique")
    donor_unit = outers[0][1][3][1][0]
    if donor_unit[1][1] != 0:
        raise KitError("1anv_2 first sword sub-wait is not Wait(0)")
    appended: list = []
    for i in range(PF_SWORDS):
        bind_base = PF_SUBJECT_OFFSET + 5 * i
        rain = make_rain(rain_donor, anchor=bind_base + 1, base=PF_RAIN_BASE_ID + 4 * i,
                         mult=(params["rain"], params["rain"]), alv=None, **PF_RAIN)  # PF 剑雨不吃共鸣 ALv
        appended.append(pf_sword_unit(donor_unit, bind_base=bind_base, launch_dir=PF_LAUNCH_DIRS[i],
                                      mult=params["sword"], rain=rain))
    for node in appended:
        if cmds(node, "NotifyPowerflipEnd"):
            raise KitError("appended PF block unexpectedly holds NotifyPowerflipEnd")
        for c in cmds(node, "CreateHitArea"):
            if c[24] != 0:
                raise KitError("CreateHitArea p23 must stay 0 (4 skips the PF damage bucket)")
        for c in cmds(node, "ShowEffect"):
            c[1] = c[1] + PF_EFFECT_LABEL_SUFFIX
    burst[0][11][1].extend(appended)
    from wf_philia_wind_revision import revise_pf
    rewritten, counts = rewrite_all(ctx, tree, families)
    return revise_pf(rewritten), counts


# ================================================================ 像素小人 / 语音（Integrate 阶段）

PIXEL_DIR_REL = f"{BATCH}/pixel/philia"
PIXEL_VERIFY_REL = f"{BATCH}/pixel/_review/verify_all.json"
# sheet 基名 → 同组元数据（atlas / frame / timeline），元数据保持母本（只改 character/<母本>/ 前缀）
PIXEL_SHEETS = {
    "sprite_sheet": ("sprite_sheet.atlas.amf3.deflate", "pixelart.frame.amf3.deflate",
                     "pixelart.timeline.amf3.deflate"),
    "special_sprite_sheet": ("special_sprite_sheet.atlas.amf3.deflate", "special.frame.amf3.deflate",
                             "special.timeline.amf3.deflate"),
}


def pixel_inputs(root: Path) -> tuple[dict[str, Path], list[str]]:
    """像素染色产物是否可装包：``pixel/philia/report.json`` 门禁全过、``pixel/_review/verify_all.json``
    philia 复核全过（REVIEW.md §5 修复轮），且两者记录的 sha256 = ``out/<sheet>.png`` 当前字节；
    report 记录的母本 sha 必须 = 当前母本（染色基于同一份母本）。

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
        digest = C.sha256(png.read_bytes())
        rep_sha = ((report.get("outputs") or {}).get(name) or {}).get("sha256")
        if rep_sha != digest:
            probs.append(f"{name}.png sha256 != pixel report outputs ({rep_sha})")
        if (reviewed.get(name) or {}).get("sha256") != digest:
            probs.append(f"{name}.png sha256 != reviewed verify_all H8 sha")
        out[name] = png
    return out, probs


def _pixel_prefix(spec) -> dict[str, str]:
    return {f"character/{spec.template_code}/": f"character/{spec.code}/"}


def pixel_problems(ctx, *, check_owner: bool = True) -> list[str]:
    """包内像素小人核对（不写盘）：sheet 存储态（小写魔数）解码字节 = 染色 PNG 原字节；
    尺寸 / alpha = 母本；染色所据母本 sha = 当前母本；atlas/frame/timeline = 母本树（仅路径前缀改写）；
    归属 owner=pixel 且登记 sha = 盘上字节。"""
    import wf_assets
    spec = ctx.spec
    pngs, probs = pixel_inputs(ctx.root)
    if probs:
        return [f"pixel inputs not ready: {p}" for p in probs]
    report = json.loads((ctx.root / PIXEL_DIR_REL / "report.json").read_text(encoding="utf-8"))
    sources = report.get("source_files") or {}
    prefix = _pixel_prefix(spec)
    for name, metas in PIXEL_SHEETS.items():
        logical = f"character/{CODE}/pixelart/{name}.png"
        tpl_logical = f"character/{spec.template_code}/pixelart/{name}.png"
        if not ctx.pack.pkg_has("common", logical):
            probs.append(f"package pixel sheet missing {logical}")
            continue
        raw = ctx.pack.pkg_path("common", logical).read_bytes()
        if raw[:8] != wf_assets.PNG_FAKE:
            probs.append(f"{logical} lacks store PNG magic")
            continue
        if wf_assets.png_decode(raw) != pngs[name].read_bytes():
            probs.append(f"{logical} != {PIXEL_DIR_REL}/out/{name}.png (store form)")
        _r, donor_raw, _src = ctx.pack.template_asset(tpl_logical)
        if (sources.get(tpl_logical) or {}).get("sha256") != C.sha256(donor_raw):
            probs.append(f"{tpl_logical}: template bytes != pixel report source_files sha (recolor base drift)")
        pkg_img, donor = ctx.png_open(raw), ctx.png_open(donor_raw)
        if pkg_img.size != donor.size:
            probs.append(f"{logical} size {pkg_img.size} != donor {donor.size}")
        elif pkg_img.getchannel("A").tobytes() != donor.getchannel("A").tobytes():
            probs.append(f"{logical} alpha differs from donor {tpl_logical}")
        if check_owner:
            record = ctx.pack.owned_record("common", logical) or {}
            if record.get("owner") != "pixel" or record.get("sha256") != C.sha256(raw):
                probs.append(f"{logical} owner record {record} (expected pixel + current sha)")
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


def install_pixel(ctx) -> dict[str, Any]:
    """把复核通过的像素染色 sheet 以存储态（小写魔数、PNG 字节不重编码）写进包，owner=pixel。

    重跑幂等：字节相同不改盘，登记 sha 不变。产物未就绪时不写、返回 pending。"""
    import wf_assets
    pngs, probs = pixel_inputs(ctx.root)
    if probs:
        return {"status": "pending", "problems": probs}
    written = {}
    for name, png in pngs.items():
        logical = f"character/{CODE}/pixelart/{name}.png"
        data = wf_assets.png_encode(png.read_bytes())
        ctx.write_asset("common", logical, data, owner="pixel")
        written[logical] = {"source": f"{PIXEL_DIR_REL}/out/{png.name}", "decoded_sha256": C.sha256(png.read_bytes()),
                            "store_sha256": C.sha256(data)}
    after = pixel_problems(ctx)
    if after:
        raise KitError(f"pixel sheets did not land in the package: {after}")
    return {"status": "installed", "sheets": written, "problems": []}


def voice_state(ctx) -> dict[str, Any]:
    """只读：语音是否已由 wf_seasonal7_voice pack 装包（22 槽文件在包内且归属 voice、speech 行引用新槽、
    无多余旧母本语音）。"""
    import wf_seasonal7_voice as V
    missing = [s for s in V.SLOTS if not ctx.pack.pkg_has("common", f"character/{CODE}/voice/{s}.mp3")]
    not_voice_owned = [s for s in V.SLOTS if s not in missing
                       and ctx.pack.owner_of("common", f"character/{CODE}/voice/{s}.mp3") != "voice"]
    speech_flat = ctx.pkg_flat("master/character/character_speech.orderedmap") \
        if ctx.pack.pkg_has("common", "master/character/character_speech.orderedmap") else {}
    speech = ctx.csv_split(speech_flat.get(str(CID), "")) if speech_flat.get(str(CID)) else []
    refs = [cells[4] for cells in speech if len(cells) == 5]
    want_refs = [*V.HOME_SLOTS, "ally/join", "ally/evolution"]
    base = ctx.pack.package / "roots" / "common" / "character" / CODE / "voice"
    extra = sorted(p.relative_to(base).with_suffix("").as_posix() for p in base.rglob("*")
                   if p.is_file() and p.relative_to(base).with_suffix("").as_posix() not in V.SLOTS) \
        if base.is_dir() else []
    packed = not missing and not not_voice_owned and refs == want_refs and not extra
    return {"packed": packed, "missing_slots": missing, "not_voice_owned": not_voice_owned,
            "speech_refs": refs, "extra_voice_files": extra}


# ================================================================ 产物摘要（门禁绑定）

DIGEST_TABLE_KEYS = (
    (ABILITY, tuple(f"{CID}{slot}" for slot in range(1, 7))),
    (LEADER, (str(CID),)),
    (CAS, (CAS_CHANGE_SKILL, CAS_PF_OVERRIDE)),
    (PFA, (PF_KEY,)),
    (CHAR, (str(CID),)),
    (TEXT, (str(CID),)),
)


def kit_digest(ctx) -> dict[str, Any]:
    """kit 产物摘要：自有表行文本 + DSL 字节 + 特效族全部文件字节（含染色 sheet）。

    sheet 计入摘要：Effects 阶段改了染色产物、kit 重跑后摘要随之变化，status 回落 draft，
    必须重跑 run_gates（其中核对包内 sheet == fx manifest out_rgba）才能再次 ready-for-review。"""
    parts: dict[str, Any] = {}
    for logical, keys in DIGEST_TABLE_KEYS:
        flat = ctx.pkg_flat(logical) if ctx.pack.pkg_has("common", logical) else {}
        parts[logical] = {k: flat.get(k) for k in keys}
    parts[ACTION] = ctx.pkg_nested(CODE)
    parts[SW] = ctx.pkg_nested(VOICE_KEY, SW)
    files = {}
    programs = [wf_dsl.dsl_logical(ctx.program_path(lv)) for lv in ("1", "2")] + \
               [wf_dsl.dsl_logical(p) for p in PF_PROGRAMS]
    for logical in programs:
        path = ctx.pack.pkg_path("common", logical)
        files[logical] = C.sha256(path.read_bytes()) if path.is_file() else None
    fx_root = ctx.pack.pkg_path("common", f"battle/effect/skill_unique/{CODE}")
    if fx_root.is_dir():
        base = ctx.pack.package / "roots" / "common"
        for path in sorted(fx_root.rglob("*")):
            if path.is_file():
                files[path.relative_to(base).as_posix()] = C.sha256(path.read_bytes())
    parts["files"] = files
    blob = json.dumps(parts, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return {"sha256": hashlib.sha256(blob).hexdigest(), "files": len(files)}


def gate_status(root: Path, digest: str) -> tuple[str, str]:
    path = root / GATES_REL
    if not path.is_file():
        return "draft", f"{GATES_REL} 不存在：先跑 python {IMPL_REL}/run_gates.py"
    try:
        gates = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        return "draft", f"{GATES_REL} 无法解析: {exc}"
    if not gates.get("all_pass"):
        failed = [k for k, v in (gates.get("checks") or {}).items() if not v.get("pass")]
        return "draft", f"离线门禁未全过: {failed}"
    if gates.get("kit_digest") != digest:
        return "draft", "产物已变化（kit_digest 与 gates.json 不一致）：重跑 run_gates.py"
    return "ready-for-review", "离线门禁全过且产物摘要一致"


# ================================================================ build

def _write_checked_flat(ctx, logical: str, rows: dict[str, list[list[str]] | str]) -> None:
    ctx.write_flat(logical, rows)
    back = ctx.pkg_flat(logical)
    for key, value in rows.items():
        want = C.csv_split(value) if isinstance(value, str) else [list(r) for r in value]
        if C.csv_split(back[key]) != want:
            raise KitError(f"readback mismatch {logical}#{key}")


def build(ctx) -> dict[str, Any]:
    spec = ctx.spec
    if (spec.cid, spec.code, spec.element) != (CID, CODE, ELEMENT):
        raise KitError(f"spec identity drift: {spec.cid}/{spec.code}/{spec.element}")
    root = Path(ctx.root)
    design = load_design(root)
    plan = load_revision(root)
    plan2 = load_revision2(root)
    evidence: dict[str, Any] = {"design": DESIGN_REL, "revision": REVISION_REL, "revision2": REVISION2_REL}
    param_drift = skill_param_drift(design) + pf_param_drift(design) + revision_param_drift(plan)
    if param_drift:
        raise KitError(f"kit parameters drift from design/revision: {param_drift}")

    # ---- 文案：design 基线钉死（sha256），本轮按 plan 覆盖技能说明（R31）与 PF 覆盖文案（R4–R7）
    text_row = list(design["text"]["character_text_row"])
    if len(text_row) != 12 or text_row[8:10] != ["(None)", "(None)"]:
        raise KitError("design character_text_row shape drift")
    if text_row[5] != text_row[7] or C.sha256(text_row[5].encode("utf-8")) != SUPERSEDED_DESIGN_DESC_SHA256:
        raise KitError("design skill description is not the superseded 1.4.868 text any more")
    if plan["strings"][ACTION]["key"] != CODE or plan["strings"][TEXT]["key"] != spec.cid_s:
        raise KitError("revision strings keys drift")
    if plan["strings"][TEXT]["c5"] != plan["strings"][TEXT]["c7"]:
        raise KitError("revision character_text c5/c7 are not the same text")
    # 第二轮：技能说明真源换成 revision2；revision1 的那一版必须仍能被逐字复现（否则是有人偷改了上一轮基线）。
    plan_desc = plan2["strings"][ACTION]["value"]
    superseded_desc = plan["strings"][ACTION]["c1_inner_1_and_2"]
    if plan2["strings"][ACTION]["changed"] != (plan_desc != superseded_desc):
        raise KitError("revision2 action_skill c1 'changed' flag disagrees with the revision1 text")
    text_row[5] = text_row[7] = plan_desc
    want_texts = {"name": text_row[0], "furigana": text_row[1], "profile": text_row[2], "title": text_row[3],
                  "skill1": text_row[4], "desc1": text_row[5], "skill2": text_row[6], "desc2": text_row[7],
                  "leader": text_row[10], "cv": text_row[11]}
    if TEXTS != want_texts or spec.texts != {**spec.texts, **want_texts}:
        raise KitError("module TEXTS drift from revision plan / design text.character_text_row")
    if design["text"].get("desc_override") is not None or plan["desc_override"]["write"]:
        raise KitError("design/plan now asks for desc_override; kit does not implement it")

    # ---- 队长 6 行 / 词条 6 键：design 派生 → plan 覆盖 → 与 plan full_row_after 逐格核对
    donor_cache: dict = {}
    design_leader, _ = derive_rows(ctx, design["leader"], "leader_ability", "leader", donor_cache)
    design_ability: dict[str, list[list[str]]] = {}
    for slot, entries in design["abilities"].items():
        key = design["ability_keys"][slot]
        rows, _ = derive_rows(ctx, entries, "ability", slot, donor_cache)
        for row in rows:
            if row[1] != design["ability_unisonable_c1"][slot] or row[2] != design["ability_statue_group_c2"][slot]:
                raise KitError(f"{slot}: c1/c2 drift from design")
        design_ability[key] = rows
    if sum(len(v) for v in design_ability.values()) != design["ability_record_total"]:
        raise KitError("design ability record total drift")
    leader_rows, leader_trace = revise_leader(ctx, design_leader, plan, donor_cache)
    ability_rows, ability_trace = revise_abilities(ctx, design_ability, plan, donor_cache)
    if sorted(ability_rows) != spec.ability_keys:
        raise KitError(f"ability keys {sorted(ability_rows)} != spec {spec.ability_keys}")
    row_gate: dict[str, Any] = {"leader": [], "ability": {}}
    caps: list[str] = []
    for row in leader_rows:
        probs = row_problems("leader_ability", row)
        row_gate["leader"].append(probs)
        caps += L.required_client_capabilities("leader_ability", row)
    for key, rows in ability_rows.items():
        row_gate["ability"][key] = [row_problems("ability", row) for row in rows]
        for row in rows:
            caps += L.required_client_capabilities("ability", row)
    flat_probs = [p for probs in row_gate["leader"] for p in probs] + \
                 [p for rows in row_gate["ability"].values() for probs in rows for p in probs]
    if flat_probs:
        raise KitError(f"row legality problems: {flat_probs[:5]}")
    caps = sorted(set(caps))
    if caps != sorted(design["required_capabilities"]) or tuple(caps) != tuple(sorted(spec.required_capabilities)):
        raise KitError(f"capabilities {caps} != design {design['required_capabilities']} / spec "
                       f"{spec.required_capabilities}")

    # ---- 面板渲染逐行对 plan describe_expected（作者原句 → 面板中文的验收锚）
    import wf_describe
    rendered = {f"L{i}": d for i, d in enumerate(wf_describe.describe_rows(leader_rows, "leader_ability"))}
    for key, rows in ability_rows.items():
        for i, d in enumerate(wf_describe.describe_rows(rows, "ability")):
            rendered[f"{key}#{i}"] = d
    describe_bad = [(k, rendered.get(k), want) for k, want in plan["describe_expected"].items()
                    if rendered.get(k) != want]
    if describe_bad:
        raise KitError(f"describe drift from revision plan: {describe_bad[:3]}")

    # ---- 字符串键（PF 覆盖文案按 plan 改写；change_skill 键沿用 design）
    cas_rows = {item["key"]: item["text"] for item in design["custom_strings"]}
    if set(cas_rows) != {CAS_CHANGE_SKILL, CAS_PF_OVERRIDE}:
        raise KitError(f"design custom_strings keys drift: {sorted(cas_rows)}")
    superseded_cas = {CAS_PF_OVERRIDE: SUPERSEDED_DESIGN_PF_STRING_SHA256,
                      CAS_CHANGE_SKILL: SUPERSEDED_DESIGN_CHANGE_SKILL_SHA256}
    for key, want_sha in superseded_cas.items():
        if C.sha256(cas_rows[key].encode("utf-8")) != want_sha:
            raise KitError(f"design custom_ability_string {key} is not the superseded 1.4.868 text any more")
    plan_cas = plan["strings"][CAS]["keys"]
    if set(plan_cas) != {CAS_PF_OVERRIDE, CAS_CHANGE_SKILL}:
        raise KitError(f"revision custom_ability_string keys drift: {sorted(plan_cas)}")
    # 第二轮：custom_ability_string 真源换成 revision2；revision1 的值留作被取代基线，drift 仍变红。
    plan2_cas = plan2["strings"][CAS]["keys"]
    for key, entry in plan2_cas.items():
        superseded = plan_cas[key]["value"]
        if entry["changed"] != (entry["value"] != superseded):
            raise KitError(f"revision2 {key}: 'changed' flag disagrees with the revision1 text")
        if entry["changed"]:
            want = entry.get("superseded_revision1_sha256")
            if C.sha256(superseded.encode("utf-8")) != want:
                raise KitError(f"revision2 {key}: revision1 baseline is not the recorded superseded text")
        cas_rows[key] = entry["value"]
    # 两条面板文案规则的硬门禁（作者 2026-09-16 晚补充）。
    # 覆盖面 = 写表期 kit 手上的三处文案：技能说明 + character_text 12 列 + CAS 两键。
    # **不是**包内文本全集（character_speech 字幕不由 kit 写）；全集扫描见 run_gates 的 panel_text_rules_round2。
    text_problems = text_rule_problems({ACTION: plan_desc,
                                        **{f"character_text.c{i}": v for i, v in enumerate(text_row)},
                                        **cas_rows})
    if text_problems:
        raise KitError(f"panel text rule problems: {text_problems}")
    refs = [ref for row in leader_rows for ref in string_key_refs("leader_ability", row)] + \
           [ref for rows in ability_rows.values() for row in rows for ref in string_key_refs("ability", row)]
    if sorted(r[2] for r in refs) != sorted(cas_rows):
        raise KitError(f"string key references {refs} != custom_strings {sorted(cas_rows)}")
    pf_leader = [row for row in leader_rows if row[45] == "722"]
    if len(pf_leader) != 1 or pf_leader[0][80] != PF_KEY or pf_leader[0][81] != "1,2,3":
        raise KitError("leader 722 row drift (c80/c81)")

    # ---- 写表：词条 / 队长 / 字符串（撤销框架克隆的未用键）
    import wf_philia_combo_stock as stock
    ability_rows[spec.cid_s+'1'], ability_rows[spec.cid_s+'4'] = stock.revise_abilities(
        ability_rows[spec.cid_s+'1'], ability_rows[spec.cid_s+'4'])
    # 作者 2026-09-21：能力 4 的条件由「浮游效果中」换成「持有贯穿效果期间」。放在 stock 之后，
    # 因为 wf_philia_combo_stock.revise_abilities 的基线断言仍按首发形态（c97=31）把关。
    import wf_philia_no_flying_revision as nofly_rows
    ability_rows[spec.cid_s+'4'] = nofly_rows.ability4_rows(ability_rows[spec.cid_s+'4'])
    # 2026-09-17 PF 修订（``wf_seasonal_pf_revision``：能力 3 追加「每 5 次 PF → 队长攻击力 / 自身 PF 伤害」
    # 两行；原为 kit 重建后手动再套的一次性候选，不补就少两行）→ 2026-09-27 平衡第二批
    # （``wf_balance_20260927b_philia``：队长每次 PF 成长 1/10、施放 / 每 5 次 PF 两行搬入队长 1/5，能力 3
    # 三行换成有上限的弱化版）→ 2026-09-27 平衡第三轮（``wf_balance_20260927c_philia``：队长四条成长回调到
    # 原值 2/3–4/5）。三者都只接受上一步的精确形态，kit 重跑产物 == 暂存候选。
    import wf_seasonal_pf_revision as pf_revision
    import wf_balance_20260927b_philia as balance_b
    import wf_balance_20260927c_philia as balance_c
    try:
        ability_rows[spec.cid_s+'3'] = pf_revision.revise_rows('philia', ability_rows[spec.cid_s+'3'])
        leader_rows, ability_rows[spec.cid_s+'3'] = balance_b.growth_rows(
            leader_rows, ability_rows[spec.cid_s+'3'])
        leader_rows = balance_c.growth_rows(leader_rows)
    except ValueError as exc:
        raise KitError(f"0917 PF revision / balance 20260927b/c rows: {exc}") from exc
    _write_checked_flat(ctx, stock.UNIQUE, {str(stock.UID): stock.unique_row()})
    stock_icon = ctx.workspace/'source/wind-stock-icon.png'
    # The revision candidate owns the generated source; rebuilds must not redraw it.
    if not stock_icon.is_file():
        raise KitError(f'wind-stock icon source missing: {stock_icon}')
    ctx.write_asset('common', stock.ICON+'.png', C.png_store_bytes(C.png_open(stock_icon.read_bytes())))
    _write_checked_flat(ctx, ABILITY, ability_rows)
    _write_checked_flat(ctx, LEADER, {spec.cid_s: leader_rows})
    from wf_philia_wind_revision import PF_TEXT, skill_description
    # 作者 2026-09-21「去掉浮游效果」：链到最后再删「浮游」分句，
    # 免得有人重跑 kit 把浮游文案带回来（wf_philia_wind_revision 的 PF_TEXT 仍是含浮游的旧常量）。
    import wf_philia_no_flying_revision as nofly
    for index in (5, 7):
        text_row[index] = nofly.skill_description(
            stock.skill_description(skill_description(text_row[index])))
    cas_rows[CAS_PF_OVERRIDE] = nofly.pf_override_text(PF_TEXT)
    cas_rows[CAS_CHANGE_SKILL] = stock.DESCRIPTION
    _write_checked_flat(ctx, CAS, {k: [[v]] for k, v in cas_rows.items()})
    unclaimed = []
    claimed_cas = next((c for c in ctx.pack.load_claims() if c["logical_path"] == CAS and c["root"] == "common"), None)
    pkg_cas = ctx.pkg_flat(CAS)
    for key in UNUSED_FRAMEWORK_CAS:
        if (claimed_cas and key in claimed_cas["outer_keys"]) or key in pkg_cas:
            ctx.unclaim(CAS, [key])
            unclaimed.append(key)
    if any(key in ctx.pkg_flat(CAS) for key in UNUSED_FRAMEWORK_CAS):
        raise KitError("unused framework custom_ability_string key survived unclaim")
    claimed_cas = next((c for c in ctx.pack.load_claims() if c["logical_path"] == CAS and c["root"] == "common"), None)
    if claimed_cas is None or any(key in claimed_cas["outer_keys"] for key in UNUSED_FRAMEWORK_CAS):
        raise KitError("custom_ability_string claim missing or still holds the unused framework key")

    # ---- 特效三族
    fx_overrides, fx_info = load_fx_manifest(root)
    recolor_log: dict[str, Any] = {}
    families: list[dict] = []
    for clone in design["effects"]["clone"]:
        src_dir = clone["src_dir"].rstrip("/")
        dst = clone["dst"].rstrip("/")
        prefix = f"battle/effect/skill_unique/{CODE}/"
        if not dst.startswith(prefix) or "/" in dst[len(prefix):]:
            raise KitError(f"design effect dst {dst} is not codename layout")
        donor = src_dir.rsplit("/", 1)[-1]
        sheet = f"{src_dir}/{donor}.png"
        fam = ctx.clone_effect_family(src_dir, dst[len(prefix):], clone["fx_names"], layout="codename",
                                      png_transform=make_png_transform(sheet, fx_overrides.get(sheet),
                                                                       recolor_log))
        if fam["dst_dir"] != dst or fam["missing_effects"]:
            raise KitError(f"effect clone drift {src_dir}: dst={fam['dst_dir']} missing={fam['missing_effects']}")
        if sorted(fam["copied_bases"]) != sorted(clone["fx_names"]):
            raise KitError(f"effect clone {src_dir}: copied {fam['copied_bases']} != {clone['fx_names']}")
        pkg_sheet = ctx.pack.pkg_path("common", f"{fam['dst_dir']}/{fam['dst_name']}.png")
        pkg_rgba = hashlib.sha256(C.png_open(pkg_sheet.read_bytes()).tobytes()).hexdigest()
        want_rgba = (fx_overrides.get(sheet) or {}).get("out_rgba_sha256")
        if want_rgba and pkg_rgba != want_rgba:
            raise KitError(f"effect clone {src_dir}: package sheet RGBA != fx manifest out_rgba_sha256")
        recolor_log.setdefault(sheet, {})["package_sheet"] = {
            "logical": f"{fam['dst_dir']}/{fam['dst_name']}.png", "rgba_sha256": pkg_rgba,
            "file_sha256": C.sha256(pkg_sheet.read_bytes())}
        families.append(fam)
    unused_fx = sorted(k for k in fx_overrides
                       if not (recolor_log.get(k) or {}).get("recolor"))
    if unused_fx:
        raise KitError(f"fx manifest entries not applied to any cloned family: {unused_fx}")
    fx_info["unused_entries"] = unused_fx
    family_targets = {e["target"] for fam in families for e in fam["effects"]}

    # ---- 技能两档 DSL
    hashes = design_source_hashes(design)
    energy = design["skills"]["energy"]
    template_inner = C.core.load_nested_table_bytes(ctx.pack.template_table_bytes(ACTION), ACTION) \
        .rows["wind_oracle_1anv"].text_rows()
    skill_gates: dict[str, Any] = {}
    programs: list[str] = []
    action_rows: dict[str, list[list[str]]] = {}
    for level in ("1", "2"):
        tree, counts = build_skill_tree(ctx, level, SKILL_PARAMS[level], families, hashes)
        gates = dsl_gates(tree)
        bad = dsl_gate_failures(gates)
        if gates["movementPriority"] != 2 or gates["buffTargetAs"] != SKILL_BUFF_TARGET_AS \
                or gates["n_attacks"] != 2 * SKILL_SWORDS:
            bad.append(f"head/attacks drift {gates['movementPriority']}/{gates['buffTargetAs']}/{gates['n_attacks']}")
        stray = [p for p in gates["fx_paths"] if p.startswith(f"battle/effect/skill_unique/{CODE}/")
                 and p not in family_targets]
        if stray:
            bad.append(f"fx refs outside cloned families: {stray}")
        if bad:
            raise KitError(f"skill {level} DSL gates failed: {bad}")
        # 2026-09-27 平衡第二批（Down）：剑雨爆发段 p13 2.5→1（单体每次施放 57.5→27.5），其余节点不动
        tree = balance_b.skill_tree(tree)
        gates = dsl_gates(tree)
        bad = dsl_gate_failures(gates) + [f"batch 20260927b: {p}" for p in balance_b.dsl_problems(tree)]
        if bad:
            raise KitError(f"skill {level} DSL gates failed after balance 20260927b: {bad}")
        gates["effect_rewrites"] = counts
        skill_gates[level] = gates
        programs.append(ctx.write_dsl(ctx.program_path(level), tree))
        src = C.csv_split(template_inner[level])[0]
        cells = [text_row[4] if level == "1" else text_row[6], text_row[5] if level == "1" else text_row[7],
                 "dynamic/skill/atk_nearest", "true", str(energy[level]["c4"]), str(energy[level]["c5"]),
                 str(energy[level]["c6"]), ctx.program_path(level), *src[8:24]]
        if len(cells) != 24:
            raise KitError(f"action_skill row length {len(cells)}")
        action_rows[level] = [cells]

    # ---- PF 覆盖三档（R4–R7：官方 special 底座 + 辅助增益 + 5 方向光剑 + 命中点剑雨）
    donor_1anv_2 = _source_tree(ctx, f"{SKILL_SRC}wind_oracle_1anv$wind_oracle_1anv_2",
                                hashes[f"{SKILL_SRC}wind_oracle_1anv$wind_oracle_1anv_2"])
    rain_donor = find_one(_source_tree(ctx, f"{SKILL_SRC}wind_oracle_meteor23$wind_oracle_meteor23_2",
                                       hashes[f"{SKILL_SRC}wind_oracle_meteor23$wind_oracle_meteor23_2"])[11][1],
                          is_cmd("CreateReferencePoint"), "meteor23 CreateReferencePoint (PF rain donor)")
    special_hashes = special_source_hashes(plan)
    pf_value = design["pf_override"]["power_flip_action"]["value"]
    if pf_value.split(",") != list(PF_PROGRAMS) or design["pf_override"]["power_flip_action"]["key"] != PF_KEY:
        raise KitError("design power_flip_action drift")
    pf_gates: dict[str, Any] = {}
    want_attacks = 2 + 2 * PF_SWORDS          # special 底座 2 段爆炸 + 5 把光剑 + 5 份剑雨
    for level in (1, 2, 3):
        tree, counts = build_pf_tree(ctx, level, donor_1anv_2, rain_donor, families, special_hashes)
        gates = dsl_gates(tree)
        bad = dsl_gate_failures(gates)
        if gates["movementPriority"] != 1 or gates["buffTargetAs"] != 0 or gates["n_attacks"] != want_attacks:
            bad.append(f"PF head/attacks drift {gates['movementPriority']}/{gates['buffTargetAs']}/"
                       f"{gates['n_attacks']} (want {want_attacks})")
        stray = [p for p in gates["fx_paths"] if p.startswith(f"battle/effect/skill_unique/{CODE}/")
                 and p not in family_targets]
        if stray:
            bad.append(f"fx refs outside cloned families: {stray}")
        if bad:
            raise KitError(f"PF lv{level} DSL gates failed: {bad}")
        from wf_philia_random_pf import revise_pf as random_pf
        tree = random_pf(tree)
        # 2026-09-27 平衡第二批（Down）：随机选项风刃 p13 0.75→0、剑雨 2.5→0（单体 43.75/48.75/53.75→15/20/25）
        tree = balance_b.pf_tree(tree)
        bad = [f"batch 20260927b: {p}" for p in balance_b.dsl_problems(tree)]
        if bad:
            raise KitError(f"PF lv{level} DSL gates failed after balance 20260927b: {bad}")
        gates = dsl_gates(tree)
        gates["effect_rewrites"] = counts
        gates["attacks_per_execution_path"] = want_attacks
        pf_gates[str(level)] = gates
        programs.append(ctx.write_dsl(PF_PROGRAMS[level - 1], tree))
    _write_checked_flat(ctx, PFA, {PF_KEY: [list(PF_PROGRAMS)]})

    # ---- action_skill 两档 → switched_action_skill（语音路由）→ character / character_text
    ctx.write_nested(ACTION, CODE, action_rows, replace_inner=True)
    acts = ctx.pkg_nested(CODE)
    if set(acts) != {"1", "2"} or any(len(c) != 24 for c in acts.values()) \
            or any(acts[lv] != action_rows[lv][0] for lv in acts):
        raise KitError("action_skill readback mismatch")
    route = list(design["voice"]["route"]["character_c9_c16"])
    if route != ["3", "", "", "", "", VOICE_KEY, "false", "false"] or \
            design["skills"]["switched_action_skill"]["key"] != VOICE_KEY:
        raise KitError(f"design voice route drift: {route}")
    ctx.write_nested(SW, VOICE_KEY, {lv: [cells[7:24]] for lv, cells in acts.items()}, replace_inner=True)
    got = ctx.pkg_nested(VOICE_KEY, SW)
    if set(got) != {"1", "2"} or any(len(got[lv]) != 17 or got[lv] != acts[lv][7:24] for lv in ("1", "2")):
        raise KitError("switched_action_skill readback mismatch (17 columns = action_skill c7..c23)")
    char_row = ctx.pack.pkg_character_row()
    edits = design["identity"]["character_row_edits_from_template"]
    char_row[9:17] = route
    char_row[18] = text_row[10]
    for col in ("c0", "c2", "c3", "c4", "c6", "c7", "c8", "c17", "c25", "c26", "c27", "c36"):
        if char_row[int(col[1:])] != edits[col]:
            raise KitError(f"character {col}={char_row[int(col[1:])]!r} != design {edits[col]!r}")
    if char_row[19:25] != edits["c19..c24"] or char_row[18] != edits["c18"]:
        raise KitError("character ability keys / leader name drift")
    _write_checked_flat(ctx, CHAR, {spec.cid_s: [char_row]})
    _write_checked_flat(ctx, TEXT, {spec.cid_s: [text_row]})
    mirrors = ctx.sync_character_mirrors()

    # ---- 像素小人（复核通过才装，owner=pixel）；语音只读状态（由 wf_seasonal7_voice pack + impl/philia/voice_merge.py 装）
    pixel = install_pixel(ctx)
    voice = voice_state(ctx)
    ctx.evidence_write("pixel-report.json", {       # manifest 读 summary/status 进 snapshot
        "summary": (f"像素小人染色 sheet 已装包（{PIXEL_DIR_REL}/out，存储态，owner=pixel）"
                    if pixel["status"] == "installed" else "像素小人 pending（母本原色占位）"),
        "status": pixel["status"], **pixel})

    # ---- 证据与报告
    digest = kit_digest(ctx)
    status, reason = gate_status(root, digest["sha256"])
    panel = [f"队长{i}：{d}" for i, d in enumerate(wf_describe.describe_rows(leader_rows, "leader_ability"))]
    for key, rows in ability_rows.items():
        panel += [f"词条{key[-1]}#{i}：{d}" for i, d in enumerate(wf_describe.describe_rows(rows, "ability"))]
    evidence.update({
        "rows": {"leader": leader_trace, "ability": ability_trace, "legality": row_gate,
                 "required_capabilities": caps, "describe": rendered},
        "custom_ability_string": {"written": sorted(cas_rows), "unclaimed_this_run": unclaimed,
                                  "unused_framework_keys_absent": list(UNUSED_FRAMEWORK_CAS),
                                  "references": [list(r) for r in refs],
                                  "texts": dict(cas_rows)},
        "panel_text_rules": {"source": REVISION2_REL, "problems": text_problems,
                             "forbidden_words": list(FORBIDDEN_TEXT_WORDS),
                             "changed_this_round": sorted(k for k, e in plan2_cas.items() if e["changed"])
                                                   + ([ACTION] if plan2["strings"][ACTION]["changed"] else []),
                             "forbidden_word_hits": 0,
                             "scanned_here": ["action_skill 两档 c1", "character_text 12 列",
                                              "custom_ability_string 两键"],
                             "rule": "规则1 上列写表期文案不出现「无上限」等措辞；"
                                     "规则2 536 技能强化条目无数字、无「秒/帧/%」且为「强化『…』…」句式。"
                                     "包内文本全集（含 character_speech 字幕）的扫描在 "
                                     "impl/philia/run_gates.py:panel_text_rules_round2"},
        "effects": {"families": [{k: fam[k] for k in ("src_dir", "dst_dir", "copied_bases", "prefix_map")}
                                 for fam in families],
                    "fx_manifest": fx_info, "recolor": recolor_log},
        "skills": skill_gates, "power_flip": pf_gates,
        "power_flip_action": {PF_KEY: list(PF_PROGRAMS)},
        "action_skill": {lv: cells for lv, cells in acts.items()},
        "switched_action_skill": {VOICE_KEY: got},
        "character_c9_c16": route, "mirrors": mirrors.get("server_character"),
        "pixel": pixel, "voice": voice,
        "kit_digest": digest, "status": status, "status_reason": reason,
    })
    ctx.evidence_write("kit-build.json", evidence)
    notes = [
        "特效 sheet 仍为官方原色，等 Effects 阶段产出 fx/philia/out/manifest.json 后重跑 kit" if not fx_overrides
        else f"特效 sheet 染色来自 {FX_MANIFEST_REL}（{len(fx_overrides)} 张）",
        (f"像素小人已装包（{PIXEL_DIR_REL}/out 存储态，owner=pixel，复核 verify_all 通过）"
         if pixel["status"] == "installed" else f"像素小人 pending：{pixel['problems'][:3]}"),
        ("语音已装包（22 槽 AI 合成，speech 8 行引用新槽，旧母本语音已清）" if voice["packed"]
         else f"语音未装齐：missing={voice['missing_slots'][:3]} extra={voice['extra_voice_files'][:3]}；"
              "character c9–c16 已按 kind 3 路由写好，pack_voice 可直接接受"),
        f"已撤销框架自动克隆但未引用的字符串键 {list(UNUSED_FRAMEWORK_CAS)}",
        f"本轮改版真源 {REVISION_REL}：队长 6 行（L1/L3 整行换 donor，L4/L5 改值，全部加光共鸣门）、"
        f"词条 16 条（536 行 A3→A1 并改主位+共鸣双门，A3 新增 3 条）、技能 10 把慢速光剑 + 命中点剑雨 + "
        f"tree[10]=3 + 共鸣 debuff、PF 换官方 special 底座 + 5 方向光剑",
        "零先例两处（真机不生效按 requirements.md §8 降级）：技能 tree[10]=3 走强化弹射乘区；"
        "ACPowerFlipDamageResistance 在官方技能 DSL 无用例",
        "PF 换族副作用：suppress 90→20/30/30（触发变慢），且 special 族要球撞到敌人才结算",
        "2026-09-27 平衡第二批（wf_balance_20260927b_philia）：队长每次 PF 光队攻 25→2.5%、自身 PF 伤 50→7%"
        "（并入每 5 次 PF 行），新增施放→光队攻 20%、每 5 次 PF→自身攻 10%；能力 3 施放/每 5 次 PF 两行"
        "最多 8 次、每 5 次 PF 伤害行改为持有「风刃余势」期间 PF 伤害 +50%；技能单体削韧 57.5→27.5、"
        "PF 43.75/48.75/53.75→15/20/25。未经真机验收",
        "2026-09-27 平衡第三轮（wf_balance_20260927c_philia）：队长每次 PF 光队攻 2.5→20%、自身 PF 伤 7→40%、"
        "施放→光队攻 20→80%、每 5 次 PF→自身攻 10→35%；能力 3 封顶版不动。未经真机验收",
        "静态门禁通过不等于真机验收；金丝雀清单见 design/philia.md §10 + revision-20260916/philia/verify.md",
        f"status={status}：{reason}",
    ]
    ctx.report({
        "summary": f"菲莉亚·夏祭浴衣 kit（改版 revision-20260916）：六词条{sum(len(v) for v in ability_rows.values())}条/"
                   f"队长{len(leader_rows)}行/技能两档/"
                   "PF special 覆盖三档/语音路由/特效三族",
        "status": status,
        "skills": {"programs": sorted(programs)},
        "unique_condition": {str(stock.UID): {"icon": stock.ICON+'.png', "name": stock.NAME}},
        "required_capabilities": caps,
        "panel": panel,
        "notes": notes,
        "kit_digest": digest["sha256"],
        "gates": GATES_REL,
    })
    return {"status": status, "reason": reason, "programs": len(programs), "kit_digest": digest["sha256"],
            "unclaimed_this_run": unclaimed, "fx_recolor": bool(fx_overrides)}


# ======================================================================== 框架缺口规避：发布后的 inspect
#
# 角色已上线（1.4.872，active 账本里已有本包的 ownership hash）后，``flow preflight`` 必须拿到
# installed manifest，否则直接报 ``active ownership hash exists but installed manifest was not supplied``
# （rc=2）。``wf_seasonal7_build.step_inspect`` 不传 ``--installed-package-dir``，所以框架的
# ``--step inspect`` 在改版重建包时必然失败。这里在 kit 内补上该参数（不改框架公共文件），
# 其余（复制到临时副本、只在副本里封存、回写 evidence/flow-inspect.json）与框架一致。
# 同批 zantetsu / primula 两个 kit 已用同一写法。

PKG_ARCHIVE_DIRNAME = "pkgarchive"                # <仓库父目录>/pkgarchive/<package_id>-<链号>/


def installed_package_candidates(root: Path, pkg_id: str) -> list[Path]:
    """已发布包的归档目录（链号新→旧）。"""
    import re
    base = root.parent / PKG_ARCHIVE_DIRNAME
    if not base.is_dir():
        return []

    def version_key(path: Path):
        return [int(x) for x in re.findall(r"\d+", path.name[len(pkg_id) + 1:])] or [0]

    found = [d for d in base.iterdir()
             if d.is_dir() and d.name.startswith(pkg_id + "-") and (d / "manifest.json").is_file()]
    return sorted(found, key=version_key, reverse=True)


def run_inspect(installed_dir: str | None = None) -> dict[str, Any]:
    """``--step inspect`` 的替代：在 workspace 副本上跑 flow preflight，并补上 ``--installed-package-dir``。"""
    import os
    import shutil
    import wf_seasonal7_build as B
    import wf_seasonal7_specs as S
    spec = S.get_spec(KEY)
    pack = C.S7Pack(spec)
    pack.check_identity()
    root = pack.root
    candidates = ([Path(installed_dir)] if installed_dir
                  else installed_package_candidates(root, spec.pkg_id))
    guarded = [pack.package / "manifest.json", pack.evidence / "status.json", pack.evidence / "hash-cache.json"]
    before = {str(f): (f.read_bytes() if f.is_file() else None) for f in guarded}
    base = pack.batch_dir / B.INSPECT_DIR
    attempts: list[dict[str, Any]] = []
    rc, payload, used, workspace_copy = None, None, None, None
    for candidate in candidates or [None]:
        copy_root = base / f"{KEY}-{os.getpid()}"
        if copy_root.exists():
            shutil.rmtree(copy_root)
        try:
            copy_root.mkdir(parents=True)
            workspace_copy = copy_root / pack.workspace.name
            shutil.copytree(pack.workspace, workspace_copy)
            extra = ["--profile", "cn"]
            if candidate is not None:
                extra += ["--installed-package-dir", str(candidate)]
            rc, payload = B._flow("preflight", workspace_copy, root, extra)
        finally:
            shutil.rmtree(copy_root, ignore_errors=True)
            try:
                base.rmdir()
            except OSError:
                pass
        errors = payload.get("errors") or []
        attempts.append({"installed_package_dir": None if candidate is None else str(candidate),
                         "returncode": rc, "errors": errors})
        used = candidate
        if not any("not hash-bound" in e or "different package_id" in e for e in errors):
            break
    after = {str(f): (f.read_bytes() if f.is_file() else None) for f in guarded}
    if after != before:
        raise KitError("inspect modified the real workspace")
    text = json.dumps(payload, ensure_ascii=False)
    if workspace_copy is not None:
        for old in (workspace_copy, workspace_copy.resolve()):
            text = text.replace(json.dumps(str(old))[1:-1], json.dumps(str(pack.workspace))[1:-1])
    payload = json.loads(text)
    ready, reason = B.kit_readiness(pack)
    result = B._preflight_summary(rc, payload, pack, pack.workspace)
    result.update({"sealed_real_workspace": False, "sealed_copy_only": True, "kit_ready": ready,
                   "kit_reason": reason, "structurally_ready": rc == 0,
                   "flow_next_command": result.get("next_command"),
                   "installed_package_dir": None if used is None else str(used),
                   "installed_package_attempts": attempts,
                   "framework_gap": "wf_seasonal7_build.step_inspect 不传 --installed-package-dir，"
                                    "角色上线后（active ledger 已有 ownership hash）必然 rc=2；"
                                    "本 kit 的 inspect 子命令补上该参数，其余与框架一致",
                   "foreign_shadow_conflicts": foreign_shadow_conflicts(pack, result),
                   "foreign_key_delta": foreign_key_delta(pack)})
    pack.write_evidence("flow-inspect.json", {"summary": result, "payload": payload})
    if rc == 2:                                   # rc=3 = 预检未达发布条件（本批串行发布的 live 漂移），由主控 rebase 处理
        raise KitError(f"flow preflight (inspect copy) rc={rc}: {payload.get('errors')}")
    return result


def owned_claim_keys(pack) -> dict[str, set[str]]:
    """{logical_path: 本包认领的 outer key 集合}（认领表按 logical_path 归并，忽略 root）。"""
    out: dict[str, set[str]] = {}
    for claim in pack.load_claims():
        keys = out.setdefault(claim["logical_path"], set())
        keys.update(claim.get("outer_keys") or [])
        for inner in claim.get("inner_keys") or []:
            if inner.get("outer_key"):
                keys.add(inner["outer_key"])
    return out


def foreign_shadow_conflicts(pack, summary: dict) -> dict[str, Any]:
    """把 preflight conflicts 分成「别家键的共享表影子漂移」与「碰到自家键」两堆。

    本批 7 个角色串行发布：philia 的包在 1.4.872 建好，之后 primula/yuki/zantetsu 又发了 873-875，
    于是 philia 包里的共享表全表载荷在**别家键**上落后于 live，preflight 报 ``unclaimed_change``。
    这是主控 publish 前 ``flow rebase`` 负责的事（wf-flow-serial-publish-order / wf-package-shadow-table-refresh），
    不是本角色的缺陷；但只要有一条 conflict 碰到自家键，就必须变红。
    """
    conflicts = ((summary.get("preflight") or {}).get("conflicts") or [])
    claimed = owned_claim_keys(pack)
    own, foreign = [], []
    for item in conflicts:
        path, _, key = str(item.get("claim", "")).partition(":")
        outer = key.split("/", 1)[0]
        mine = (pack.spec.cid_s in key or CODE in key
                or outer in claimed.get(path, set()) or key in claimed.get(path, set()))
        (own if mine else foreign).append(item)
    return {"total": len(conflicts), "foreign": len(foreign), "own": own,
            "all_unclaimed_change": all(c.get("kind") == "unclaimed_change" for c in conflicts),
            "foreign_keys": sorted({str(c.get("claim", "")).partition(":")[2] for c in foreign})}


#: 共享表（本包声明了它、但表里绝大多数外层键属于别家角色）。逐张比对键集合，
#: 因为 preflight 把「内容变了」「键多了」「键少了」三件事一律标成 ``unclaimed_change``。
SHARED_TABLE_CLAIMS = (
    ("common", "master/ability/ability.orderedmap"),
    ("common", "master/ability/leader_ability.orderedmap"),
    ("common", "master/string/custom_ability_string.orderedmap"),
    ("common", "master/character/character.orderedmap"),
    ("common", "master/character/character_text.orderedmap"),
    ("common", "master/character/character_speech.orderedmap"),
    ("common", "master/character/character_status.orderedmap"),
    ("common", "master/skill/action_skill.orderedmap"),
    ("common", "master/skill/switched_action_skill.orderedmap"),
    ("common", "master/skill/power_flip_action.orderedmap"),
    ("common", "master/generated/trimmed_image.orderedmap"),
    ("server", "cdndata/character.json"),
    ("server", "cdndata/character_text.json"),
    ("server", "character.json"),
)


def _outer_keys_of_table(raw: bytes, codec_id: str) -> list[str]:
    """按 codec 取一张表的外层键序（不解内层、不解压行）。"""
    import wf_mod_tool as core
    if codec_id == "json_object":
        value = json.loads(raw.decode("utf-8"))
        if not isinstance(value, dict):
            raise KitError("server JSON table is not an object")
        return list(value)
    # flat / raw_outer / action_nested / switched_nested 的索引结构相同，只有行是否 zlib 不同
    return list(core.read_orderedmap_raw_rows_from_bytes(raw).keys)


def foreign_key_delta(pack) -> dict[str, Any]:
    """逐张共享表比对「包内全表载荷的外层键集合 vs live 的外层键集合」。

    为什么单独做：``preflight`` 把**内容变更 / 键多了 / 键少了**三件事一律标成 ``unclaimed_change``，
    而发布的投递单位是**整文件**——包里少一个别家键，发布出去就等于把那一行从 live 删掉。
    本函数把漂移拆开，``missing_in_package`` 是删除语义（最危险的一档）。

    这三档都由主控 publish 前的 ``flow rebase`` 归零：rebase 以 **live 全表为底**、只覆盖本包认领的
    outer key（``wf_release._merge_claimed_rows``），所以别家键既不会被改也不会被删。
    ``own_key_missing`` 非空才是本角色自己的缺陷（自家声明键没写进包）。
    """
    claims = {(c["root"], c["logical_path"]): c for c in pack.load_claims()}
    owned = owned_claim_keys(pack)
    tables: list[dict[str, Any]] = []
    missing_total = extra_total = 0
    own_key_missing: list[str] = []
    errors: list[str] = []
    for root, logical in SHARED_TABLE_CLAIMS:
        claim = claims.get((root, logical))
        if claim is None:
            continue
        try:
            pkg_raw = pack.pkg_path(root, logical).read_bytes()
            if root == "server":
                live_raw = (pack.server_base / Path(*logical.split("/"))).read_bytes()
            else:
                live_raw = pack.live_table_bytes(logical)
            pkg_keys = _outer_keys_of_table(pkg_raw, claim["codec_id"])
            live_keys = _outer_keys_of_table(live_raw, claim["codec_id"])
        except Exception as exc:                                   # noqa: BLE001
            errors.append(f"{root}:{logical}: {type(exc).__name__}: {exc}")
            continue
        missing = [k for k in live_keys if k not in set(pkg_keys)]
        extra = [k for k in pkg_keys if k not in set(live_keys)]
        mine = owned.get(logical, set())
        own_key_missing += [f"{logical}:{k}" for k in mine if k not in set(pkg_keys)]
        missing_total += len(missing)
        extra_total += len(extra)
        tables.append({"root": root, "logical_path": logical,
                       "package_keys": len(pkg_keys), "live_keys": len(live_keys),
                       "missing_in_package": missing, "extra_in_package": extra,
                       "own_claimed_keys_present": sorted(k for k in mine if k in set(pkg_keys))})
    return {"tables": tables, "errors": errors,
            "missing_in_package_total": missing_total, "extra_in_package_total": extra_total,
            "own_key_missing": sorted(own_key_missing),
            "deletion_semantics": sorted(f"{t['logical_path']}:{k}"
                                         for t in tables for k in t["missing_in_package"]),
            "rebase_clears_all": missing_total + extra_total > 0,
            "note": ("包内共享表是建包时的 live 快照；本批 7 包串行发布，后发的包会让 live 前移，"
                     "于是本包对 live 既可能内容落后、也可能**少掉别家新增的键**（删除语义）。"
                     "主控 publish 前的 flow rebase 以 live 全表为底重铺，三档一起归零；"
                     "own_key_missing 非空才是本包缺陷。")}


def main(argv: list[str] | None = None) -> int:
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] != ["inspect"] or len(args) > 2:
        print("usage: python mod-tools/wf_seasonal7_kit_philia.py inspect [<installed package dir>]")
        return 2
    result = run_inspect(args[1] if len(args) == 2 else None)
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
