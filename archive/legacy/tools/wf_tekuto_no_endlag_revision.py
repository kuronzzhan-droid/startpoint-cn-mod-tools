# -*- coding: utf-8 -*-
"""特克托（139993 / ``super_robot_tailcoat``）取消技能的「固定」段。

作者 2026-09-21 原话：「上次的特克托取消技能释放后的后摇」，追加澄清：
「就是要去掉固定的这一段或者大幅缩短」。

**先说交付口径（别用「整段去掉」一句话交差）：玩家实际感知到的定住是 70 帧 → 60 帧，只少了 14%。**
数据层（DSL）的停球确实从 10 帧清零到 0 帧，但它前面还压着客户端写死的 60 帧技能 cut-in，
而且两段是**先后**关系、不重叠（证据见下面「两段锁是串行的」）。``lock_report()`` 的
``total_locked_frames`` 就是这两段之和，70 → 60。

落点（**在当前 live 技能树上做节点级删除**，不重跑旧 kit 整包重建，否则会把 897/901/920
那几轮改版——激光头部块修复、队长攻/技双上限、能力2 按「引擎启动」层数、Codex 的半血重炮与
强化技能护盾——一起冲掉）：

* 技能两档 ``super_robot_tailcoat_{1,2}``：根块唯一一条
  ``StopBall [-18, 10, ["RestoreToSpeedBeforeActionExecution"], ["EF"], 0]``
  整条摘除 ⇒ **DSL 层**一帧都不定住球（客户端那 60 帧 cut-in 仍在，见上）；
  其余 8 条根语句与整棵演出树逐节点不动。
* 技能说明两档 + ``character_text`` c5/c7 追加「释放技能后不再进入硬直，可立即行动」
  （与本批黑 ``outlaw_panther_moon`` 的 live 文案逐字同一句，只是本角色用「；」分隔）。

# 先查清（2026-09-21，证据都在本文件的常量与 ``lock_report()`` 里）

**live 的「固定」比任务书假设的短得多，这一点必须先说清楚。** 逐字节实测（live store ==
workspace 候选，两棵树 sha256 相同）：

| | 母本官方特克托 ``super_robot`` | 本批黑（已验收的「取消后摇」） | 特克托 live（改前） |
|---|---|---|---|
| ``tree[1]`` movementPriority | 2 = STOP（抢球的移动权） | 1 = NONE | **1 = NONE** |
| ``StopBall`` | ``[-18, 140, ["Stop"], …]`` | ``[-18, 30, ["Restore…"], …]`` | **``[-18, 10, ["Restore…"], …]``** |

也就是说：kit 首发时就已经把母本的「停球 140 帧 + Stop（停住不再恢复）」换成了
「停 10 帧 + 恢复发动前速度」，并且没有 ``SuppressBallActivity``。本次把这最后 10 帧也整条删掉，
DSL 侧的定住归零。

**顺带一个必须转告作者的对照**：同批的黑 ``outlaw_panther_moon`` 与丝缇涅尔 ``still_obstinator_moon``
至今 live 仍各带一条 ``StopBall [-18, 30, ["RestoreToSpeedBeforeActionExecution"], ["AB"], 0]``
（且 ``tree[1] = 2 = STOP``），也就是黑 = 60 + 30 = **90 帧**。所以特克托改完应当**明显比黑更跟手
（快 30 帧 ≈ 0.5 s）**；真机对比时如果两边手感一样，说明这次改动根本没生效，要回头查，
**不能**拿「和黑一致」当验收通过。

# 剩下的 60 帧：客户端硬编码，数据层无杠杆（引文 2026-09-21 复核更正）

``SquadManagerImpl.invokeActionSkill()``（``弹国服/scripts/pinball/scene/battle/battle/squad/
SquadManagerImpl.as:573``）末尾 **734-735 行**：

.. code-block:: actionscript

    stopForSkillCutin(60, Option.Some(primary));            // 冻住除施法者以外的所有队
    primary.invokeActionSkill(60, Option.Some(_loc47_));    // → ball.startToSkillCutin(60, innovation)

``SquadImpl.invokeActionSkill`` → ``BallImpl.startToSkillCutin`` ⇒ 球进 ``BallState.SkillCutin(60, …)``，
``enterSkillCutinState`` 把碰撞设成 ``Never``、``exitSkillCutinState`` 再把 vx/vy 放回来。

**注意别引错**（上一版就引错了）：``MemberImpl.as:2593`` 那句
``squadManager.stopForSkillCutin(60, Option.Some(squad))`` 在 ``ActionKind.SummonsMultiball`` 分支，
而 ``ActiveSquadManager.stopForSkillCutin``（:119-141）对每一队算 ``_loc5_ = param2.params[0] == squad``、
``if(!_loc5_)`` 才冻 ⇒ ``Option.Some(squad)`` **恰好跳过施法者自己那一队**，它冻的是别人的球。
施法者自己被冻 60 帧的唯一出处就是上面 734-735。结论（写死 60、全角色同一个字面量、
数据层改不了、要动只能 APK 补丁）不变，只是引文改对。

# 两段锁是串行的，不是重叠的

``BallImpl`` 状态机 ``case 7``（SkillCutin，:405-418）：``stateFrame == params[0]``(=60) 时才
``changeState(保存的状态)`` 并 ``innovation.invoke(this)`` → ``ActionSkillInnovationData.invoke``
→ ``invoker.startActionSkills(…)`` ⇒ **本技能树是在 60 帧 cut-in 结束的那一帧才开始跑的**。
所以 DSL f0 的 ``StopBall 10`` 排在 cut-in 之后，两段相加 = 70 帧。
（旁证：``BallImpl.applyMovement`` :2763-2772，若执行 StopBall 时球正处在 ``SkillCutin``，
新的 ``SkillMoving`` 只会被塞进 cut-in 的「保存状态」槽里等 cut-in 结束再生效——它从不与 cut-in 并行。）
删掉这 10 帧 ⇒ 70 → 60 帧，**-14%**。详见 ``lock_report()`` 与 ``plan_document()`` 的 ``findings``。

客户端语义（``弹国服/scripts`` 反编译源码，逐行核对）：

* ``ActionEvaluator`` case 14（StopBall）→ ``subject.applyMovement(coordSys, {w:角度},
  时长=params[1], 速度=0, EndingSpeedKind=params[2], TweenSource.None, **true**, …)``；
* ``BallImpl.applyMovement``：第 7 参恒 true ⇒ ``squad.suppressDirectAttack(时长)``（这 10 帧
  直击也不算数）；球进 ``BallState.SkillMoving(时长, 0, 0, …)``，速度被钉成 0；
* ``BallImpl`` 状态机 case 2：``stateFrame == 时长`` 时回 ``PhysicalMoving``，
  ``exitSkillMovingState`` 按 ``EndingSpeed`` 收尾——``Stop``=速度归零（球**停在原地**，
  黑/丝缇涅尔改前就是这一种）、``RestoreToSpeedBeforeActionExecution``=还原发动前的 vx/vy；
* ``BallImpl._canInvokeActionSkill``：``SkillCutin`` 与 ``SkillMoving`` 期间**全队都不能发动技能**
  ⇒ 删掉这 10 帧同时少 10 帧「按不出技能」。
* ``StopBall`` 的坐标系 ``["EF"]`` 在球上合法（``BallImpl.getDirEF() = angle``；``getDirCD()`` 才 throw），
  删掉它也就不再改写球的 ``angle``。

**为什么能整条删、不必退而求其次去缩短**：瞄准（雷达/aim_line）与发射（四段 + 终幕 + 5 个延长槽）
的**伤害倍率、段数、帧号时序**一个不动——本工具的测试用「其余命令逐节点、逐顺序不变 + Wait 帧号
集合不变 + 8 类节点计数不变」把这句话钉死；第一段判定区在 f90 才创建，远在这 10 帧之后，
不存在「某段 Wait/事件时序依赖球静止」的耦合。

**但不能写成「位置不变」**（2026-09-21 复核更正，上一版把这句夸大了）：这棵树 12 个
``CreateHitArea`` 里有 11 个主体是球 ``-18``、第 7 参 ``trackingPos = True``、坐标系 ``["GH", 0]``。

* ``trackingPos = True`` ⇒ 判定区/光束**每帧重取锚点位置**，本来就是跟着球跑的；
* ``["GH", 0]`` 走 ``ActionEffect.calcDir()`` 的 case 3 ⇒ 朝向 =
  ``atan2(锁定目标 - 球当前位置)``，``trackingDir = false`` 只是把这个**数值**冻在创建的那一帧。

球不再被钉住 10 帧 ⇒ 此后每一帧球都比原来多飞 10 帧的行程，f90 / 150 / 210 / 270 / 332 以及
f372–612 五个延长槽的**发射原点**（连带由原点算出的那个角度数值）都会落在与原来不同的位置。
不变的是伤害、段数、时序，以及「从球出发、指向 f0 用 ``FindNearSubjects`` 锁定的那名敌人」这条
语义（锁定发生在 f0，球位置两版相同 ⇒ 锁的是同一个敌人）。**这是「不定住球」的应有后果，
不是缺陷，但它不是免检牌。** 唯一不受影响的是 f94 的导弹落点：它挂参照点 ``23``，
两个跟随位都 ``False``、锚在锁定目标上。

# 诊断保留意见：作者说的「固定」可能根本不是这 10 帧

* 特克托改前的停球 **10 帧是全批最短的**；同批黑/丝缇涅尔各 30 帧，作者已经真机验收接受。
  作者偏偏**单独点名特克托**，说明他感觉到的「固定」多半不是这 10 帧（否则黑更该被点名）。
* 特克托独有、而且真的长的那一段是**发动到第一段激光之间的 ~90 帧（1.5 s）雷达扫描 + 瞄准线**
  （f0 radar/aim_line → f5 Sector 判定 → f20 charge_S → f24 missile_launch → **f90 第一段激光**）。
  黑/丝缇涅尔没有这种前摇。这一段**不定住球**（球在 f70 之后就能自由操作），但确实是
  「按下去之后等了一秒半才看见激光」。
* ⇒ 发布前请作者先回答一句：**「你说的固定，是发动瞬间球被钉住，还是发动后等了 1.5 秒才出激光？」**
  前者＝本轮这个改动；后者要改 ``STAGES`` 帧号整体前移，**会动伤害时序与段数窗口，属于设计改动，
  本轮没有授权、没有动**。

（历史：上一版把这条放在 findings 第 4 条的脚注位置，复核判定应当提到最前面当主假设。）

设计纪律：``strip_ball_hold`` 是纯函数（不碰 live、不碰盘），基线不符立即抛错，重复调用幂等。
本工具**只会写 workspace 候选**（``--write-candidate``）。铸边/登记 pending/发布由主控做，
命令见 ``--plan-out`` 生成的 plan.json 的 ``publish`` 段。
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
import zlib
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    pass  # Imports resolve from this checkout/package, not external source copies.

import wf_dsl  # noqa: E402
import wf_mod_tool as core  # noqa: E402
import wf_seasonal7_kit_philia as PH  # noqa: E402  （共享门禁：dsl_gates / text_rule_problems）
import wf_seasonal7_kit_tekuto as K  # noqa: E402
from wf_character_revision import RevisionCandidate, encode_tree  # noqa: E402

CID = K.CID                       # "139993"
CODE = K.CODE                     # "super_robot_tailcoat"
ELEMENT = K.ELEMENT               # 2 = 雷
PACKAGE_VERSION = "1.0.6"
SNAPSHOT_KEY = "no_endlag_20260921"
EVIDENCE_NAME = "no-endlag-20260921.json"
REVISION_DIR = "work/character_packs/seasonal7-20260916/revision7-tekuto-no-endlag"
PLAN_REL = REVISION_DIR + "/plan.json"
#: 方案 B（压缩前摇）的备选产物目录。**只往这里写**，候选包与 plan.json 一律不碰。
OPTION_B_REL = REVISION_DIR + "/option-b"
WORKSPACE_REL = "work/character_packs/s7-tekuto"

SKILL_SRC = "battle/action/skill/action/rare5/"
SKILL_PROGRAMS = tuple(f"{SKILL_SRC}{CODE}${CODE}_{level}" for level in (1, 2))

#: 会「把球固定住」的两条 DSL 命令。两条都删，名字写死免得靠字符串拼。
HOLD_COMMANDS = ("StopBall", "SuppressBallActivity")
#: live 改前的唯一一条 StopBall（逐值锁死；对不上＝基线漂移，拒绝动手）。
STOPBALL_BASELINE = [-18, 10, ["RestoreToSpeedBeforeActionExecution"], ["EF"], 0]
#: 每棵树期望删除的「固定」条数。
EXPECTED_HOLDS = 1
#: 根头 ``tree[1]``：1 = NONE（不抢球的移动权）。2/3（STOP/MOVE）要另外处理，见 docstring。
MOVEMENT_PRIORITY_NONE = 1
#: 客户端硬编码的技能 cut-in 帧数，数据层改不了。出处（2026-09-21 复核更正）：
#: ``弹国服/scripts/pinball/scene/battle/battle/squad/SquadManagerImpl.as:734-735``，
#: 在 ``SquadManagerImpl.invokeActionSkill()``（:573）末尾——
#: ``stopForSkillCutin(60, Option.Some(primary))`` 冻住**除施法者以外**的所有队，
#: ``primary.invokeActionSkill(60, Option.Some(innovation))`` → ``BallImpl.startToSkillCutin(60)``
#: 才是冻住施法者自己那颗球的地方。
#: **不要引 MemberImpl.as:2593**：那句在 ``ActionKind.SummonsMultiball`` 分支，且它传的
#: ``Option.Some(squad)`` 会被 ``ActiveSquadManager.stopForSkillCutin``(:119-141) 的
#: ``if(!_loc5_)`` 跳过施法者自己那一队 —— 它冻的是别人的球。
SKILL_CUTIN_FRAMES = 60
#: cut-in 与本树是**串行**的：``BallImpl`` 状态机 case 7 要等 ``stateFrame == 60`` 才
#: ``innovation.invoke(this)`` → ``startActionSkills`` 启动技能树。所以两段帧数直接相加。
CLIENT_CUTIN_SOURCE = "弹国服/scripts/pinball/scene/battle/battle/squad/SquadManagerImpl.as:734-735"

#: 同批已被作者真机验收接受的对照角色：live 至今仍各带一条 30 帧 StopBall + ``tree[1]=2(STOP)``。
#: 真机对比判据靠它 —— 黑 = 60+30 = 90 帧，特克托改完 = 60 帧 ⇒ 特克托应当**更短**，不是「一致」。
PEER_CODES = ("outlaw_panther_moon", "still_obstinator_moon")
PEER_STOPBALL = [-18, 30, ["RestoreToSpeedBeforeActionExecution"], ["AB"], 0]
PEER_MOVEMENT_PRIORITY = 2

#: ``CreateHitArea`` 的参数位（命令列表含命令名在 0 位）。见 work/codex_out/hitarea_params.md。
HIT_AREA_SUBJECT, HIT_AREA_TRACKING_POS, HIT_AREA_TRACKING_DIR = 2, 7, 8
BALL_SUBJECT = -18


class NoEndlagError(ValueError):
    pass


# ================================================================ 纯函数：树

def _blocks(node, out: list | None = None) -> list[list]:
    """树里所有 ``["Block", [语句…]]`` 节点本身（``node[1]`` 就是语句表）。"""
    out = [] if out is None else out
    if isinstance(node, list):
        if len(node) == 2 and node[0] == "Block" and isinstance(node[1], list):
            out.append(node)
        for child in node:
            _blocks(child, out)
    return out


def _is_hold_statement(statement) -> bool:
    return (isinstance(statement, list) and len(statement) == 2 and statement[0] == "Command"
            and isinstance(statement[1], list) and statement[1][0] in HOLD_COMMANDS)


def hold_statements(tree) -> list[list]:
    """树里每一条「把球固定住」的语句（``["Command", ["StopBall"|"SuppressBallActivity", …]]``）。"""
    return [st for block in _blocks(tree) for st in block[1] if _is_hold_statement(st)]


def hold_frames(tree) -> int:
    """DSL 侧「球被钉住」的总帧数（``StopBall`` 的 ``params[1]`` 之和）。"""
    return sum(int(st[1][2]) for st in hold_statements(tree) if st[1][0] == "StopBall")


def commands(tree, name: str) -> list[list]:
    """树里所有叫 ``name`` 的命令（返回命令列表本身，0 位是命令名）。"""
    return [st[1] for block in _blocks(tree) for st in block[1]
            if isinstance(st, list) and len(st) == 2 and st[0] == "Command"
            and isinstance(st[1], list) and st[1][0] == name]


def beam_anchors(tree) -> dict:
    """判定区的锚点画像——说清删掉停球之后**什么变了、什么没变**。

    上一版把结论写成「删掉 f0 的停球不改变任何一段的位置」，这是事实性夸大。真实情况：
    本树 12 个 ``CreateHitArea`` 里 11 个主体是球 ``-18`` 且第 7 参 ``trackingPos = True``
    ⇒ 判定区/光束每帧重取球的位置，本来就跟着球跑；球不再被钉住 10 帧，此后每帧都比原来
    多飞 10 帧行程 ⇒ **各段的发射原点会落在不同位置**（坐标系 ``["GH", 0]`` 的朝向数值同理，
    它是 ``atan2(锁定目标 − 球当前位置)`` 在创建帧的快照）。

    不变的是伤害倍率、段数、帧号时序，以及「从球出发、指向 f0 锁定的那名敌人」这条语义。
    """
    areas = commands(tree, "CreateHitArea")
    follows = [a for a in areas
               if a[HIT_AREA_SUBJECT] == BALL_SUBJECT and a[HIT_AREA_TRACKING_POS] is True]
    others = [dict(subject=a[HIT_AREA_SUBJECT], tracking_pos=a[HIT_AREA_TRACKING_POS],
                   tracking_dir=a[HIT_AREA_TRACKING_DIR]) for a in areas if a not in follows]
    return {
        "hit_areas": len(areas),
        "anchored_to_ball_and_tracking_pos": len(follows),
        "not_following_the_ball": others,
        "origin_follows_ball": bool(follows),
        "claim": "伤害倍率／段数／帧号时序不变；发射原点（连带由原点算出的朝向数值）随球位移。"
                 "不可写成「位置不变」。",
    }


def peer_drift(code: str, tree) -> list[str]:
    """对照角色（黑／丝缇涅尔）是否仍是 ``60 + 30 = 90`` 帧。

    真机判据「特克托应当比黑短约 30 帧」完全建立在这上面；哪天它们也被改短了，
    这个函数会红，判据必须跟着改，而不是继续让作者去对一个不存在的差。
    """
    problems = []
    stops = [st[1][1:] for st in hold_statements(tree)]
    if stops != [PEER_STOPBALL]:
        problems.append(f"{code}: StopBall {stops!r} != {PEER_STOPBALL!r}")
    priority = tree[1] if isinstance(tree, list) and len(tree) > 1 else None
    if priority != PEER_MOVEMENT_PRIORITY:
        problems.append(f"{code}: movementPriority {priority!r} != {PEER_MOVEMENT_PRIORITY}")
    return problems


def lock_report(tree) -> dict:
    """发动技能之后「不能动/不能按技能」的窗口，按来源拆开——给作者对账用。

    ``dsl_stop_frames`` 是本次能动的那一段；``client_cutin_frames`` 是 APK 里的字面量 60，
    只有客户端补丁能改，**不在数据层授权范围内**。两段是**先后**关系（cut-in 跑完才启动本树），
    所以 ``total_locked_frames`` 才是作者手上感觉到的那个数——交付时报这个数，不要只报 DSL 侧。
    """
    stops = [st[1][1:] for st in hold_statements(tree)]
    return {
        "movement_priority": tree[1],
        "movement_priority_meaning": {1: "NONE(不抢球的移动权)", 2: "STOP", 3: "MOVE",
                                      17: "NONE_EXCEPTION"}.get(tree[1], "unknown"),
        "hold_commands": stops,
        "dsl_stop_frames": hold_frames(tree),
        "client_cutin_frames": SKILL_CUTIN_FRAMES,
        "total_locked_frames": hold_frames(tree) + SKILL_CUTIN_FRAMES,
        "note": "cut-in 60 帧写死在 SquadManagerImpl.invokeActionSkill()（SquadManagerImpl.as:734-735）："
                "stopForSkillCutin(60, Option.Some(primary)) 冻别人、"
                "primary.invokeActionSkill(60, …) → BallImpl.startToSkillCutin(60) 冻自己；"
                "全角色同一个字面量，数据层改不了。"
                "（别引 MemberImpl.as:2593——那句在 SummonsMultiball 分支，且 Option.Some(squad) "
                "会被 ActiveSquadManager.stopForSkillCutin 的 if(!_loc5_) 跳过施法者自己那一队。）"
                "BallImpl 状态机 case 7 要等 stateFrame==60 才 innovation.invoke() 启动技能树 ⇒ "
                "cut-in 与 dsl_stop_frames 串行相加，不重叠。",
        "comparison": "同批黑 outlaw_panther_moon / 丝缇涅尔 still_obstinator_moon live 仍各带 "
                      "StopBall 30 帧（tree[1]=2 STOP）⇒ 它们是 60+30=90 帧。"
                      "特克托改完 60 帧，应当比黑明显更跟手（快 30 帧）；真机两边一样即为未生效。",
    }


def strip_ball_hold(tree, *, expected: int | None = EXPECTED_HOLDS):
    """删掉树里所有「把球固定住」的语句，其余节点原样保留。

    * 已经删干净的树原样返回（幂等，返回的是副本）；
    * ``expected`` 不是 ``None`` 时，待删条数必须正好等于它，否则抛 :class:`NoEndlagError`；
    * 每条 ``StopBall`` 的参数必须逐值等于 :data:`STOPBALL_BASELINE`——参数变了说明有人在
      中途调过这一段，删掉就不是「按已知基线动手」了，拒绝；
    * 根头 ``tree[1]`` 必须是 NONE(1)。STOP/MOVE 的树还会通过 ``updateMovementId`` 抢走球的
      移动权（``ActionSkillInnovationData`` → ``BallImpl.updateMovementId``），只删 StopBall
      不够，必须另外决定根头怎么改 ⇒ 这里直接抛错，不偷偷放过；
    * 删完若所在 ``Block`` 变空，抛错——本树里它和另外 8 条根语句同块，变空说明结构已经不是
      我们核对过的那棵，宁可红也不要留一个空块。
    """
    out = copy.deepcopy(tree)
    hits = [(block, st) for block in _blocks(out) for st in block[1] if _is_hold_statement(st)]
    if not hits:
        return out
    if expected is not None and len(hits) != expected:
        raise NoEndlagError(f"ball-hold baseline drift: found {len(hits)}, expected {expected}")
    if not (isinstance(out, list) and len(out) > 1 and out[1] == MOVEMENT_PRIORITY_NONE):
        raise NoEndlagError(
            f"movementPriority {out[1] if isinstance(out, list) and len(out) > 1 else None!r} "
            f"!= {MOVEMENT_PRIORITY_NONE}(NONE); a STOP/MOVE tree also grabs the ball's moving right")
    for _, statement in hits:
        if statement[1][0] == "StopBall" and statement[1][1:] != STOPBALL_BASELINE:
            raise NoEndlagError(f"StopBall baseline drift: {statement[1][1:]!r} != {STOPBALL_BASELINE!r}")
    for block, statement in hits:
        block[1].remove(statement)
        if not block[1]:
            raise NoEndlagError("removing the hold emptied its block; refusing to leave a dead block")
    if hold_statements(out):
        raise NoEndlagError("a ball hold survived the strip")
    return out


# ================================================================ 方案 B：压缩前摇（默认关闭）
#
# 作者的「固定」如果指的是**发动后要等 1.5 秒才看见第一段激光**（见 plan.json 的 author_question
# 与 findings 第 1 条），方案 A 一帧都解决不了。方案 B 把 f0 → 第一段激光的 90 帧前摇压到 N 帧，
# **第一段激光及其之后的一切相对时序、段数、倍率、判定区几何、特效资源一律不动**（整体平移 90-N 帧）。
#
# 本段全部默认关闭：``compress_windup`` 是纯函数，``--windup-frames`` 不给就完全不参与
# ``apply_candidate``；候选包（work/character_packs/s7-tekuto/package）永远只拿方案 A 的结果。
#
# ---------------------------------------------------------------- 时间轴（live 1.4.920，逐棵实读）
#
# 帧号是**绝对帧**（技能树自己的 f0＝客户端 60 帧 cut-in 结束那一帧），两档 lv1/lv2 逐帧相同：
#
# | f | 事件 | 备注 |
# |---|---|---|
# | 0 | 根块：清事件、两条 HideEffect、3 条 CreateCondition、FindNearSubjects 锁敌 | 锁敌在 f0 完成 |
# | 0 | ``aim_line`` 瞄准线（``laser_notice``，寿命 **90**） | 寿命刚好覆盖到第一段激光 |
# | 0 | ``radar`` 雷达盘（``PlayOnlyFirstSequence``，自身动画 **32** 帧） | DSL 无寿命参数，压不了 |
# | 5 | 雷达扇形判定区：Sector 半径 500 / 开角 1.5708(90°)，寿命 **30**，``RotateHitArea 0.05236`` | 0 伤害 |
# | 5 | └ 命中：``radar_hit`` 特效、元素耐性 −6%、技能伤害耐性 −6%、``RemoveEvent(missile_cancel)`` | |
# | 20 | ``charge_S`` 蓄力（``super_robot_laser_100px``，寿命 **70**） | 自身第 **67** 帧钉着 ``se_thunder_stamp`` |
# | 23 | ``missile_cancel``：``RemoveEvent(missile_event)`` | 雷达没标到人就取消导弹 |
# | 24 | ``missile_event``：``missile_launch`` 发射演出 | 必须**严格晚于** f23 |
# | 85 | └ 雷达命中 +80：``CreateReferencePoint``(寿命 65) + ``missile_drop`` 落点 | |
# | **90** | **第一段激光 S**：Rect 100×2400，寿命 60，间隔 10，上限 6 段，×1.36 | 前摇终点 |
# | 94 | └ 参照点 +9：导弹判定 Circle 50，寿命 15，4 段，×1.2 | 比第一段激光晚 4 帧 |
# | 150 / 210 / 270 | 激光 L / LL / LLL（320 / 490 / 760 宽），各 ×1.52 / 1.68 / 1.84 | |
# | 332 | 终幕 Rect 900，1 段 ×8.8 | |
# | 362 | 提前收炮门（「重炮展开」已消失才走 else） | 720 帧下恒不执行 |
# | 372/432/492/552/612 | 5 个延长槽（各 ×1.84，寿命 70，间隔 10，上限 6） | 由「重炮展开」开门 |
# | 682 | 打完收炮余晖 | |
#
# ---------------------------------------------------------------- 三处必须点名的耦合
#
# **① 蓄力的雷鸣音改不了位置（本方案最大的代价）。** ``super_robot_laser_100px.timeline`` 是
# ``sequences=[{begin:1, end:130, kind:once}]`` + ``sounds=[{path: sound_effect/thunder/se_thunder_stamp,
# begin: **67**}]``；``flatomo.timeline.Playhead.playSoundWhenExists(currentFrame)`` 只在播放头**走到
# 自身第 67 帧**时才放这一声。live 里它挂在 f20、寿命 70 ⇒ 声音落在 f86，正好是第一段激光（f90）前 4 帧。
# 前摇压到 N ≤ 70 时，「第 67 帧的声音落在第 N 帧之前」在几何上不可能成立。
# 所以本方案**把这条 ShowEffect 整条钉住不动**（起始帧 20、寿命 70 都不改）：
# 雷鸣仍在 f86 响，仍然是「一声炸响紧接着一道激光」，只是它配对的从第一段变成了**第二段**
# （N=36 ⇒ 第二段在 f96，雷鸣早 10 帧；N=30 ⇒ f90，早 4 帧；N=24 ⇒ f84，晚 2 帧）。
# 代价是蓄力提前量只剩 ``N-20`` 帧，且蓄力贴图会与第一段激光重叠约 70-(N-20) 帧
# （两者都是球上同方向的 100 px 激光贴图，叠在一起基本读不出差别）。
# **另一条路（不采用，留给作者）**：把寿命压到 ``N-20``，蓄力干净利落，但这一声**彻底不响**，
# 整个技能只剩雷达 warp / 导弹开门 / 落点火焰三个音。
#
# **② 雷达扇形要保住「扫中敌人」的角度覆盖。** 扇形不产生任何伤害（命中块里没有 CreateNormalAttack），
# 它只负责标记 + 两条 debuff + 放行导弹。``ActionEvaluator`` case 26 ⇒ ``RotateHitArea`` 的第 2 参是
# **角速度（rad/帧）**，``ActionHitArea.move()`` 每帧 ``r += vr`` ⇒ 整条寿命扫过的总角度
# = 30 × 0.05236 = 1.5708 rad = 90°（恰好等于扇形自己的开角）。本方案把寿命按比例压到 ``round(30N/90)``，
# 同时把角速度改成 ``1.5708 / 新寿命`` ⇒ **总扫掠角恒为 90°，而且「导弹取消线之前已扫过的角度」
# 也几乎逐度相同**（见 ``windup_report()`` 的 ``radar``）。每帧步进最多 11.25°，远小于 90° 的开角，
# 不存在「转太快跳过目标」。扇形的半径/开角/朝向一个字节不动。
#
# **③ ``missile_event`` 必须严格晚于 ``missile_cancel``。** 按比例压缩后 23/24 会撞到同一帧
# （N=30 时都是 8），而 ``missile_cancel`` 注册在前、先执行 ⇒ 会把当帧的 ``missile_event`` 直接删掉，
# 雷达明明标中了却不放导弹。所以 ``missile_event`` 取 ``max(按比例, missile_cancel + 1)``，保住 live 的 1 帧间隔。
#
# ---------------------------------------------------------------- 查过、确认不受影响的
#
# * **根块 f0 的三条 CreateCondition 不动**：「引擎启动」13999301 永续（c3=99999999）、
#   「重炮展开」13999302 live c3=**900** 帧（kit 原值 720，Codex 改版提到 900；判据按更紧的 720 写）。整条延长链平移后结束得更早（N=36 ⇒ f628 < 720），
#   kit 的 S13/S17 判据（``ext_end ≤ 720``、``COOLDOWN_FRAME < 720``、``BEAM_END_FRAME < 720``）
#   全部仍然成立，而且余量更大 ⇒ **段数与开门情况完全不变**。
# * **技能树里没有任何发声命令**（16 条 ShowEffect / 12 条 CreateHitArea / … 全表见 ``timeline()``），
#   音效一律来自特效自身的 timeline，随 ShowEffect 的帧号一起走；语音走 speech 表，与本方案无关。
# * **``aim_line`` 可以放心压**：``laser_notice.timeline`` 只有一条 1–7 帧的 ``loop``、零 sounds，
#   寿命就是「显示多久」；改成 N 仍然是「瞄准线在第一段激光那一帧消失」。
# * ``CreateReferencePoint`` 寿命 65 不动（落点标记 ``missile_drop`` 自身 67 帧，压它只会截掉落点动画）。
# * ``SetSkillSuppress`` / 冷却：树里没有；技能消耗是 action_skill 表 c4/c5（580/580、580/530），与帧号无关。
# * ``StopBall`` / ``SuppressBallActivity``：方案 A 已清零，B 不再涉及球的控制权。
#
# ---------------------------------------------------------------- 唯一一处真实的数值外溢（必须报给作者）
#
# 根块 f0 那条 ``ACSkillDamage``（lv1 480 帧 +65%、lv2 600 帧 +85~100%）是**从 f0 起算**的自增益，
# 不随激光一起平移。整条序列提前 90-N 帧 ⇒ 原来掉在窗口外的延长段命中会挪进窗口里。
# 逐帧数出来是 **两档各 +6 跳**（30 跳延长命中里，lv1 11→17、lv2 23→29），换算成总倍率
# lv1 ≈ +7.2×、lv2 ≈ 见 ``windup_report()`` 的 ``self_buff_window``。**这是变强，不是变弱**，
# 但它不在「倍率/段数不变」的承诺里，必须让作者知道。要完全抵消，只能把那条 ``ACSkillDamage``
# 的持续帧数同步减 90-N —— 那是改数值，本方案没做。

#: live 第一段激光（S 段）的绝对帧。
FIRST_BEAM_FRAME = 90
#: 给作者对比的三档前摇。
WINDUP_TIERS = (24, 30, 36)
#: 推荐档：36 帧 ≥ 雷达盘自身动画 32 帧 ⇒ 雷达转完整整一圈才开火（30/24 档它还在转）；
#: 且蓄力提前量还有 16 帧，比 30 档的 10 帧、24 档的 4 帧都像样。
#: 与 24 档的差距只有 12 帧 ≈ 0.2 s，玩家分辨不出，但演出完整度差很多。
RECOMMENDED_WINDUP = 36
#: 前摇最短不允许低于这个值——再短雷达/蓄力就真被压没了（24 档已经是蓄力只剩 4 帧提前量）。
MIN_WINDUP_FRAMES = 24

#: live 两棵树里每一个 Wait 的**绝对帧** → 用途。集合对不上＝基线漂移，拒绝动手。
WINDUP_WAIT_BASELINE = {
    5: "radar_sector", 20: "charge", 23: "missile_cancel", 24: "missile_event",
    85: "missile_reference_point", 90: "beam_s", 94: "missile_damage",
    150: "beam_l", 210: "beam_ll", 270: "beam_lll", 332: "finale",
    362: "cooldown_gate", 372: "ext_1", 432: "ext_2", 492: "ext_3",
    552: "ext_4", 612: "ext_5", 682: "beam_end",
}
#: Wait 的事件名（``RemoveEventFromOwner`` 用它一次清掉整条链）。
WINDUP_WAIT_NAMES = {23: "missile_cancel", 24: "missile_event"}
WAIT_EVENT_DEFAULT = "tekuto_cannon"

AIM_LINE_LABEL, AIM_LINE_LIFETIME = "aim_line", 90
CHARGE_LABEL, CHARGE_FRAME, CHARGE_LIFETIME = "charge_S", 20, 70
#: ``super_robot_laser_100px.timeline`` 的 ``sounds[0].begin``：雷鸣钉死在特效自身第 67 帧。
CHARGE_SOUND_FRAME = 67
#: ``super_robot_radar.timeline``：雷达盘自身 1–32 帧、``once``。DSL 侧没有寿命参数可压。
RADAR_EFFECT_FRAMES = 32
SECTOR_LIFETIME, SECTOR_ROTATION = 30, 0.05236
#: 扇形整条寿命扫过的总角度 = 30 × 0.05236 = 1.5708 rad = 90°，与扇形开角同值。
SECTOR_SWEEP = round(SECTOR_LIFETIME * SECTOR_ROTATION, 5)
SECTOR_RADIUS, SECTOR_APERTURE = 500, 1.5708
SECTOR_BINDING = 20
REFERENCE_POINT_LIFETIME = 65
#: ``CreateHitArea`` 的自绑定 id 在第 19 位（p20 起是 on_create 块 / 另两个绑定 / on_hit 块）；
#: ``CreateReferencePoint`` 的寿命在第 9 位、绑定 id 在第 10 位。逐棵实读核对过（27 / 12 个参数）。
HIT_AREA_BINDING, HIT_AREA_LIFETIME_IDX = 19, 13
REF_POINT_LIFETIME_IDX = 9
#: ``missile_event`` 与 ``missile_cancel`` 之间必须保住的最小间隔（live 就是 1 帧）。
MISSILE_EVENT_MIN_GAP = 1
#: 根块 f0 的自增益族名；``params[1][0][1][0]["min"]`` 是持续帧数。
SELF_BUFF_COMMAND = "ACSkillDamage"


class WindupError(NoEndlagError):
    """方案 B 的基线漂移 / 参数非法。继承 :class:`NoEndlagError`，调用方可以只 catch 一个。"""


def _tag(node):
    return node[0] if isinstance(node, list) and node else None


def _visit(node, frame, out):
    """深度优先遍历，``out.append((kind, node, 绝对帧))``。``frame`` 是该节点执行的绝对帧。"""
    if not isinstance(node, list) or len(node) != 2:
        return
    kind, body = node
    if kind == "Block" and isinstance(body, list):
        for statement in body:
            _visit(statement, frame, out)
    elif kind == "Event" and isinstance(body, list) and body and body[0] == "Wait":
        out.append(("Wait", node, frame))
        _visit(body[3], frame + int(body[1]), out)
    elif kind == "Command" and isinstance(body, list) and body:
        out.append(("Command", node, frame))
        for value in body[1:]:
            _nested(value, frame, out)


def _nested(value, frame, out):
    """命令参数里任意深度的 ``Block`` / ``Command`` / ``Event`` 节点（条件分支、判定区 on_hit…）。"""
    if not isinstance(value, list):
        return
    if len(value) == 2 and value[0] in ("Block", "Command", "Event"):
        _visit(value, frame, out)
        return
    for item in value:
        _nested(item, frame, out)


def timeline(tree) -> list[dict]:
    """整棵树的绝对帧时间轴：每个 Wait / 命令一行。报告与测试都用它，不许各写一份。"""
    out: list[tuple] = []
    _visit(tree[11], 0, out)
    rows = []
    for kind, node, frame in out:
        if kind == "Wait":
            wait = node[1]
            rows.append(dict(frame=frame + int(wait[1]), kind="Wait", name=wait[2],
                             wait=int(wait[1]), base=frame))
        else:
            command = node[1]
            row = dict(frame=frame, kind="Command", name=command[0])
            if command[0] == "ShowEffect":
                row.update(label=command[1], lifetime=command[5])
            elif command[0] == "CreateHitArea":
                row.update(shape=_tag(command[9]), lifetime=command[13],
                           interval=command[14], cap=command[15], binding=command[HIT_AREA_BINDING])
            elif command[0] == "CreateReferencePoint":
                row.update(lifetime=command[REF_POINT_LIFETIME_IDX],
                           binding=command[REF_POINT_LIFETIME_IDX + 1])
            elif command[0] == "RotateHitArea":
                row.update(binding=command[1], radians_per_frame=command[2])
            elif command[0] == "CreateNormalAttack":
                row.update(binding=command[1], multiplier=command[6])
            rows.append(row)
    return rows


def wait_frames(tree) -> dict[int, str]:
    """``{绝对帧: 事件名}``。本树每个 Wait 的绝对帧互不相同，可以当主键用。"""
    out: dict[int, str] = {}
    for row in timeline(tree):
        if row["kind"] != "Wait":
            continue
        if row["frame"] in out:
            raise WindupError(f"两个 Wait 落在同一绝对帧 f{row['frame']}，帧号不能当主键")
        out[row["frame"]] = row["name"]
    return out


def _one(tree, name: str, predicate=None) -> list:
    hits = [c for c in commands(tree, name) if predicate is None or predicate(c)]
    if len(hits) != 1:
        raise WindupError(f"{name} 命中 {len(hits)} 条，期望恰好 1 条")
    return hits[0]


def _sector(command) -> bool:
    return _tag(command[9]) == "Sector"


def _effect(tree, label: str) -> list:
    return _one(tree, "ShowEffect", lambda c: c[1] == label)


def windup_drift(tree) -> list[str]:
    """本方案动手前必须成立的 live 基线。非空即拒绝——绝不在没核对过的树上改帧号。"""
    problems: list[str] = []
    try:
        frames = wait_frames(tree)
    except WindupError as exc:
        return [str(exc)]
    if set(frames) != set(WINDUP_WAIT_BASELINE):
        problems.append(f"Wait 绝对帧集合 {sorted(frames)} != 基线 {sorted(WINDUP_WAIT_BASELINE)}")
    for frame, name in WINDUP_WAIT_NAMES.items():
        if frames.get(frame) != name:
            problems.append(f"f{frame} 的 Wait 事件名 {frames.get(frame)!r} != {name!r}")
    for frame in frames:
        want = WINDUP_WAIT_NAMES.get(frame, WAIT_EVENT_DEFAULT)
        if frames[frame] != want:
            problems.append(f"f{frame} 的 Wait 事件名 {frames[frame]!r} != {want!r}")
    try:
        aim = _effect(tree, AIM_LINE_LABEL)
        if aim[5] != ["SpecifyEffectLifetimeDirectly", AIM_LINE_LIFETIME]:
            problems.append(f"{AIM_LINE_LABEL} 寿命 {aim[5]!r} != {AIM_LINE_LIFETIME}")
        charge = _effect(tree, CHARGE_LABEL)
        if charge[5] != ["SpecifyEffectLifetimeDirectly", CHARGE_LIFETIME]:
            problems.append(f"{CHARGE_LABEL} 寿命 {charge[5]!r} != {CHARGE_LIFETIME}")
        sector = _one(tree, "CreateHitArea", _sector)
        if sector[13] != ["SpecifyHitAreaLifetimeDirectly", SECTOR_LIFETIME]:
            problems.append(f"雷达扇形寿命 {sector[13]!r} != {SECTOR_LIFETIME}")
        if sector[9][1][0]["min"] != SECTOR_RADIUS or sector[9][2][0]["min"] != SECTOR_APERTURE:
            problems.append(f"雷达扇形几何 {sector[9]!r} != 半径 {SECTOR_RADIUS}/开角 {SECTOR_APERTURE}")
        rotate = _one(tree, "RotateHitArea")
        if rotate[1:] != [SECTOR_BINDING, SECTOR_ROTATION, ["None"]]:
            problems.append(f"RotateHitArea {rotate[1:]!r} != {[SECTOR_BINDING, SECTOR_ROTATION, ['None']]}")
        point = _one(tree, "CreateReferencePoint")
        if point[REF_POINT_LIFETIME_IDX] != REFERENCE_POINT_LIFETIME:
            problems.append(f"参照点寿命 {point[REF_POINT_LIFETIME_IDX]!r} != {REFERENCE_POINT_LIFETIME}")
    except WindupError as exc:
        problems.append(str(exc))
    return problems


def windup_plan(first_beam_frame: int = RECOMMENDED_WINDUP) -> dict:
    """给定目标前摇 N，算出每个 Wait 的新绝对帧与三个被改的参数。纯算术，不碰树。"""
    n = int(first_beam_frame)
    if not MIN_WINDUP_FRAMES <= n < FIRST_BEAM_FRAME:
        raise WindupError(f"前摇 {n} 必须落在 [{MIN_WINDUP_FRAMES}, {FIRST_BEAM_FRAME}) 内")
    if n <= CHARGE_FRAME:
        raise WindupError(f"前摇 {n} 必须 > 蓄力起始帧 {CHARGE_FRAME}，否则蓄力跑到第一段激光之后")
    shift = FIRST_BEAM_FRAME - n

    def remap(frame: int) -> int:
        """≤ 第一段激光的按比例压缩，之后的纯平移。两段在 f90 处连续（都落到 N）。"""
        return round(frame * n / FIRST_BEAM_FRAME) if frame <= FIRST_BEAM_FRAME else frame - shift

    frames = {frame: remap(frame) for frame in WINDUP_WAIT_BASELINE}
    # ① 蓄力整条钉住：它的雷鸣音钉在特效自身第 67 帧，压缩起始帧只会让这一声更早偏离激光。
    frames[CHARGE_FRAME] = CHARGE_FRAME
    # ③ missile_event 必须严格晚于 missile_cancel，否则当帧被 RemoveEvent 吃掉。
    frames[24] = max(frames[24], frames[23] + MISSILE_EVENT_MIN_GAP)
    sector_life = max(1, round(SECTOR_LIFETIME * n / FIRST_BEAM_FRAME))
    rotation = round(SECTOR_SWEEP / sector_life, 5)
    cancel_window = frames[23] - frames[5]
    return {
        "first_beam_frame": n,
        "shift_after_first_beam": shift,
        "wait_frames": frames,
        "wait_deltas": {f: frames[f] - f for f in frames},
        "aim_line_lifetime": n,
        "charge": {"frame": CHARGE_FRAME, "lifetime": CHARGE_LIFETIME, "pinned": True,
                   "sound_frame": CHARGE_FRAME + CHARGE_SOUND_FRAME - 1,
                   "lead_before_first_beam": n - CHARGE_FRAME,
                   "overlap_with_first_beam": CHARGE_FRAME + CHARGE_LIFETIME - n},
        "radar": {"frame": frames[5], "lifetime": sector_life,
                  "radians_per_frame": rotation,
                  "total_sweep_rad": round(rotation * sector_life, 5),
                  "sweep_before_missile_cancel_rad": round(rotation * cancel_window, 5),
                  "baseline_sweep_before_missile_cancel_rad":
                      round(SECTOR_ROTATION * (23 - 5), 5),
                  "frames_before_missile_cancel": cancel_window,
                  "step_degrees": round(rotation * 180 / 3.141592653589793, 3),
                  "effect_animation_frames": RADAR_EFFECT_FRAMES,
                  "effect_finishes_before_first_beam": RADAR_EFFECT_FRAMES <= n},
        "missile": {"cancel": frames[23], "launch": frames[24],
                    "reference_point": frames[85], "impact": frames[94],
                    "impact_after_first_beam": frames[94] - n},
        "total_tree_frames": {"before": max(WINDUP_WAIT_BASELINE), "after": frames[682]},
    }


def _rewrite(node, old_base: int, new_base: int, frames: dict[int, int]) -> None:
    """按 ``frames``（旧绝对帧 → 新绝对帧）就地重写 Wait 的相对帧数。自顶向下，父先于子。"""
    if not isinstance(node, list) or len(node) != 2:
        return
    kind, body = node
    if kind == "Block" and isinstance(body, list):
        for statement in body:
            _rewrite(statement, old_base, new_base, frames)
    elif kind == "Event" and isinstance(body, list) and body and body[0] == "Wait":
        old_abs = old_base + int(body[1])
        if old_abs not in frames:
            raise WindupError(f"Wait f{old_abs} 不在帧表里（基线漂移）")
        new_abs = frames[old_abs]
        wait = new_abs - new_base
        if wait < 1:
            raise WindupError(f"Wait f{old_abs} → f{new_abs} 的相对帧数 {wait} < 1")
        body[1] = wait
        _rewrite(body[3], old_abs, new_abs, frames)
    elif kind == "Command" and isinstance(body, list) and body:
        for value in body[1:]:
            _rewrite_nested(value, old_base, new_base, frames)


def _rewrite_nested(value, old_base: int, new_base: int, frames: dict[int, int]) -> None:
    if not isinstance(value, list):
        return
    if len(value) == 2 and value[0] in ("Block", "Command", "Event"):
        _rewrite(value, old_base, new_base, frames)
        return
    for item in value:
        _rewrite_nested(item, old_base, new_base, frames)


def compress_windup(tree, *, first_beam_frame: int = RECOMMENDED_WINDUP):
    """把「发动 → 第一段激光」的前摇从 90 帧压到 ``first_beam_frame`` 帧。纯函数，返回新树。

    * 第一段激光及其之后的一切（段数、倍率、判定区几何、特效资源、相对时序）整体平移，逐节点不变；
    * 前摇按比例压缩，三处耦合按本段开头 ①②③ 的规则处理；
    * 基线不符立即抛 :class:`WindupError`；
    * **幂等**：已经压到同一档的树原样返回（副本）。
    """
    plan = windup_plan(first_beam_frame)
    out = copy.deepcopy(tree)
    try:
        current = wait_frames(out)
    except WindupError as exc:
        raise WindupError(str(exc)) from None
    if set(current) == set(plan["wait_frames"].values()) and not _target_drift(out, plan):
        return out                                            # 已经是这一档，幂等返回
    problems = windup_drift(out)
    if problems:
        raise WindupError("windup baseline drift: " + "; ".join(problems))
    _rewrite(out[11], 0, 0, plan["wait_frames"])
    _effect(out, AIM_LINE_LABEL)[5] = ["SpecifyEffectLifetimeDirectly", plan["aim_line_lifetime"]]
    _one(out, "CreateHitArea", _sector)[13] = ["SpecifyHitAreaLifetimeDirectly",
                                               plan["radar"]["lifetime"]]
    _one(out, "RotateHitArea")[2] = plan["radar"]["radians_per_frame"]
    residual = _target_drift(out, plan)
    if residual:
        raise WindupError("compress_windup did not reach its own target: " + "; ".join(residual))
    return out


def _target_drift(tree, plan: dict) -> list[str]:
    """压完之后必须成立的后置条件（也是幂等判据）。"""
    problems: list[str] = []
    try:
        frames = wait_frames(tree)
    except WindupError as exc:
        return [str(exc)]
    want = {new: WINDUP_WAIT_NAMES.get(old, WAIT_EVENT_DEFAULT)
            for old, new in plan["wait_frames"].items()}
    if frames != want:
        problems.append(f"Wait 帧表 {sorted(frames)} != 目标 {sorted(want)}")
    try:
        if _effect(tree, AIM_LINE_LABEL)[5] != ["SpecifyEffectLifetimeDirectly",
                                                plan["aim_line_lifetime"]]:
            problems.append("aim_line 寿命未到目标")
        charge = _effect(tree, CHARGE_LABEL)
        if charge[5] != ["SpecifyEffectLifetimeDirectly", CHARGE_LIFETIME]:
            problems.append("charge_S 寿命被动过了（本方案要求整条钉住）")
        if _one(tree, "CreateHitArea", _sector)[13] != ["SpecifyHitAreaLifetimeDirectly",
                                                        plan["radar"]["lifetime"]]:
            problems.append("雷达扇形寿命未到目标")
        if _one(tree, "RotateHitArea")[2] != plan["radar"]["radians_per_frame"]:
            problems.append("雷达角速度未到目标")
    except WindupError as exc:
        problems.append(str(exc))
    return problems


# ---------------------------------------------------------------- 对账：伤害节点与自增益窗口

def damage_hits(tree) -> list[dict]:
    """每个 ``CreateNormalAttack`` 的命中帧序列（单体贴脸上界）。

    命中帧模型与 kit 的 ``hitarea_max_hits`` 同源：``SpecifyMinHitIntervalDirectly(iv)`` ⇒
    命中落在判定区创建帧起的 ``0, iv, 2iv, …``（再被最大命中数钳一次）；
    ``CalculatedUsingMaxNumOfHits(n)`` ⇒ 客户端把间隔算成 lifetime/n。
    这是**上界模型**，用来对账「哪几跳落在自增益窗口里」，不是真机伤害数。
    """
    hits: list[dict] = []
    out: list[tuple] = []
    _visit(tree[11], 0, out)
    areas = [(node[1], frame) for kind, node, frame in out
             if kind == "Command" and node[1][0] == "CreateHitArea"]
    for kind, node, frame in out:
        if kind != "Command" or node[1][0] != "CreateNormalAttack":
            continue
        attack = node[1]
        owner = next((a for a, af in areas
                      if af == frame and attack[1] in (a[HIT_AREA_BINDING], a[21], a[22])), None)
        if owner is None:
            hits.append(dict(frame=frame, hits=[frame], multiplier=attack[6][0]))
            continue
        lifetime = int(owner[13][1])
        interval = owner[14]
        cap = int(owner[15][1][0]["min"]) if _tag(owner[15]) == "Some" else 0
        count = K.hitarea_max_hits(lifetime, interval, cap)
        step = int(interval[1]) if _tag(interval) == "SpecifyMinHitIntervalDirectly" \
            else max(1, lifetime // max(1, int(interval[1])))
        hits.append(dict(frame=frame, hits=[frame + i * step for i in range(count)],
                         multiplier=attack[6][0]))
    return hits


def self_buff_window(tree) -> dict:
    """根块 f0 那条 ``ACSkillDamage`` 自增益的窗口，以及有多少跳落在窗口内。

    这条增益**从 f0 起算、不随激光平移**；方案 B 把整条序列提前 90-N 帧 ⇒ 原来掉在窗口外的
    延长段命中会挪进来。这是方案 B 唯一一处真实的数值外溢，必须算出来报给作者。
    """
    buff = _one(tree, "CreateCondition",
                lambda c: c[2] and c[2][0][0] == SELF_BUFF_COMMAND)
    frames = int(buff[2][0][1][0]["min"])
    ratio = buff[2][0][2][0]
    inside = outside = 0
    inside_mult = 0.0
    for entry in damage_hits(tree):
        per_hit = float(entry["multiplier"]["max"])
        for frame in entry["hits"]:
            if frame < frames:
                inside += 1
                inside_mult += per_hit
            else:
                outside += 1
    return {"buff_frames": frames, "ratio": ratio,
            "hits_inside": inside, "hits_outside": outside,
            "multiplier_inside": round(inside_mult, 4),
            "bonus_multiplier": round(inside_mult * float(ratio["max"]), 4)}


def windup_report(before, after, plan: dict) -> dict:
    """改前/改后对照——交付给作者的那张表。"""
    def stamps(tree):
        return {row["frame"]: row for row in timeline(tree) if row["kind"] == "Wait"}

    old, new = stamps(before), stamps(after)
    rows = []
    for frame, tag in sorted(WINDUP_WAIT_BASELINE.items()):
        target = plan["wait_frames"][frame]
        rows.append({"what": tag, "before": frame, "after": target,
                     "delta": target - frame,
                     "seconds_before": round(frame / 60, 3), "seconds_after": round(target / 60, 3)})
    buff_before, buff_after = self_buff_window(before), self_buff_window(after)
    return {
        "first_beam_frame": plan["first_beam_frame"],
        "perceived_wait_frames": {
            "before": SKILL_CUTIN_FRAMES + FIRST_BEAM_FRAME,
            "after": SKILL_CUTIN_FRAMES + plan["first_beam_frame"],
            "note": "玩家按下技能到看见第一段激光 = 客户端硬编码 60 帧 cut-in + 本树的前摇（串行相加）。",
        },
        "perceived_wait_seconds": {
            "before": round((SKILL_CUTIN_FRAMES + FIRST_BEAM_FRAME) / 60, 2),
            "after": round((SKILL_CUTIN_FRAMES + plan["first_beam_frame"]) / 60, 2),
            "saved": round((FIRST_BEAM_FRAME - plan["first_beam_frame"]) / 60, 2),
        },
        "timeline": rows,
        "radar": plan["radar"],
        "charge": plan["charge"],
        "missile": plan["missile"],
        "self_buff_window": {"before": buff_before, "after": buff_after,
                             "extra_hits_inside": buff_after["hits_inside"] - buff_before["hits_inside"],
                             "extra_multiplier": round(buff_after["bonus_multiplier"]
                                                       - buff_before["bonus_multiplier"], 4)},
        "unchanged": {
            "hit_areas": len(commands(after, "CreateHitArea")),
            "normal_attacks": len(commands(after, "CreateNormalAttack")),
            "show_effects": len(commands(after, "ShowEffect")),
            "multipliers": [c[6] for c in commands(after, "CreateNormalAttack")]
            == [c[6] for c in commands(before, "CreateNormalAttack")],
            "relative_timing_after_first_beam": all(
                plan["wait_frames"][f] - plan["first_beam_frame"] == f - FIRST_BEAM_FRAME
                for f in WINDUP_WAIT_BASELINE if f >= FIRST_BEAM_FRAME),
        },
    }


# ================================================================ 纯函数：文案

#: 与本批黑 ``outlaw_panther_moon`` 的 live 技能说明逐字同一句；本角色整条说明用「；」分隔，
#: 所以分隔符跟着本角色走（黑那边是「／」）。
SEPARATOR = "；"
NO_ENDLAG_CLAUSE = "释放技能后不再进入硬直，可立即行动"

#: live 1.4.920 的技能说明（action_skill c1 两档 / character_text c5/c7 三处逐字相同）。
#: 写死在这里、不从 kit 读——kit 的 ``TEXTS`` 已经同步成改完的文案，从那边读会自己叠自己。
SKILL_DESC_BEFORE = ("锁定周围的敌人，架起跟随自身移动的重炮，朝锁定方向发射逐段变粗的充能激光；"
                     "发动时「引擎启动」+1，威力随其层数提升；再次发动会以新的一发替换当前激光")
SKILL_DESC_AFTER = SKILL_DESC_BEFORE + SEPARATOR + NO_ENDLAG_CLAUSE


def _pinned(where: str, text: str, before: str, after: str) -> str:
    if text == after:
        return text
    if text != before:
        raise NoEndlagError(f"{where}: text baseline drift")
    return after


def skill_description(text: str) -> str:
    """技能说明末尾追加「；释放技能后不再进入硬直，可立即行动」；幂等；基线不符即抛错。"""
    return _pinned("skill description", text, SKILL_DESC_BEFORE, SKILL_DESC_AFTER)


def text_problems(where: str, text: str) -> list[str]:
    """玩家可见文案的硬门禁：分句只出现一次、分隔符不成对、不留在行首行尾，且过面板文案规则。"""
    problems = []
    if text.count(NO_ENDLAG_CLAUSE) != 1:
        problems.append(f"{where}: 「{NO_ENDLAG_CLAUSE}」出现 {text.count(NO_ENDLAG_CLAUSE)} 次")
    if SEPARATOR * 2 in text:
        problems.append(f"{where}: 出现连续分隔符「{SEPARATOR * 2}」")
    for line in text.split("\n"):
        if line.startswith(SEPARATOR) or line.endswith(SEPARATOR):
            problems.append(f"{where}: 行首/行尾遗留分隔符 {line[:16]!r}…")
    return problems + PH.text_rule_problems({where: text})


# ================================================================ 候选包

def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def apply_candidate(repo: Path, *, apply: bool = False, with_text: bool = True) -> dict:
    """在 workspace 候选上删掉技能树里的「固定」段并同步文案。``apply=False`` 只预演，不写任何文件。"""
    candidate = RevisionCandidate(
        repo, repo / WORKSPACE_REL,
        character_id=CID, code_name=CODE, package_version=PACKAGE_VERSION,
        snapshot_key=SNAPSHOT_KEY, evidence_name=EVIDENCE_NAME)
    dsl_plan: list[dict] = []
    for program in SKILL_PROGRAMS:
        logical = wf_dsl.dsl_logical(program)
        before = candidate.read("common", logical)
        tree = wf_dsl.parse_dsl(zlib.decompress(before, -15))["tree"]
        updated = strip_ball_hold(tree)
        gates = PH.dsl_gates(updated, element=ELEMENT)
        failures = PH.dsl_gate_failures(gates)
        if failures:
            raise NoEndlagError(f"{program}: {failures}")
        if strip_ball_hold(updated) != updated:
            raise NoEndlagError(f"{program}: strip is not idempotent")
        raw = encode_tree(updated)
        candidate.emit("common", logical, raw)
        # `before_sha256` / `lock_before` 一律记 **live 当前那一版**（主控要覆盖的就是它）；
        # 重跑本工具时它不会因为候选已经改过而退化成 after。候选侧改前的 sha 另记 candidate_before_sha256。
        live_path = core.table_path(candidate.store, logical)
        live_raw = live_path.read_bytes() if live_path.is_file() else before
        live_tree = wf_dsl.parse_dsl(zlib.decompress(live_raw, -15))["tree"]
        hashed = core.sha1_path(logical)
        dsl_plan.append(dict(
            kind="skill", program=program, logical_path=logical,
            store_path=hashed[:2] + "/" + hashed[2:],
            removed=[st[1] for st in hold_statements(live_tree)],
            lock_before=lock_report(live_tree), lock_after=lock_report(updated),
            beam_anchors=beam_anchors(updated),
            root_statements=[len(live_tree[11][1]), len(updated[11][1])],
            before_sha256=_sha(live_raw),
            candidate_before_sha256=_sha(before),
            after_sha256=_sha(raw),
            deflate_bytes=gates["deflate_bytes"]))

    table_plan: list[dict] = []
    checks: dict[str, str] = {}

    def live_table(logical: str) -> bytes | None:
        path = core.table_path(candidate.store, logical)
        return path.read_bytes() if path.is_file() else None

    if with_text:
        # 1) action_skill（嵌套表）两档 c1 —— 角色详情页技能说明的真源
        nested = core.load_nested_table_bytes(candidate.read("common", K.ACTION), K.ACTION)
        inner = nested.rows[CODE]
        live_action = live_table(K.ACTION)
        action_before = dict(core.load_nested_table_bytes(live_action, K.ACTION).rows[CODE].text_rows()
                             if live_action else inner.text_rows())
        for level, text in dict(inner.text_rows()).items():
            cells = core.read_csv_lines(text)
            cells[0][1] = skill_description(cells[0][1])
            checks[f"{K.ACTION}:{CODE}:lv{level}"] = cells[0][1]
            inner.set_text_rows({level: core.write_csv_lines(cells).rstrip("\n")})
        action_after = dict(inner.text_rows())
        candidate.splice(K.ACTION, {CODE: core.build_orderedmap(inner)}, codec="action_nested")
        table_plan.append(dict(logical_path=K.ACTION, outer_key=CODE, codec="action_nested",
                               inner_rows={lv: dict(before=action_before[lv], after=action_after[lv])
                                           for lv in action_after}))

        # 2) character_text c5/c7（抽卡页/图鉴技能说明）
        text_rows = core.read_csv_lines(
            core.read_orderedmap_file_from_bytes(candidate.read("common", K.TEXT))[CID])
        live_text = live_table(K.TEXT)
        text_before = (core.read_orderedmap_file_from_bytes(live_text)[CID] if live_text
                       else core.write_csv_lines(copy.deepcopy(text_rows)).rstrip("\n"))
        for row in text_rows:
            for index in (5, 7):
                row[index] = skill_description(row[index])
                checks[f"{K.TEXT}:{CID}:c{index}"] = row[index]
        candidate.splice(K.TEXT, {CID: text_rows})
        table_plan.append(dict(logical_path=K.TEXT, outer_key=CID, codec="flat",
                               before=text_before,
                               after=core.write_csv_lines(text_rows).rstrip("\n"),
                               columns=[5, 7]))

        problems = [p for where, text in checks.items() for p in text_problems(where, text)]
        if problems:
            raise NoEndlagError(str(problems))

        # 服务端镜像：character_text.json 与上面那张表同源
        candidate.server_character_row("cdndata/character_text.json", text_rows)

    metadata = dict(
        removed_commands=list(HOLD_COMMANDS),
        removed_stopball=STOPBALL_BASELINE,
        removed_per_tree=EXPECTED_HOLDS,
        skill_programs=list(SKILL_PROGRAMS),
        movement_priority=MOVEMENT_PRIORITY_NONE,
        dsl_stop_frames=dict(before=STOPBALL_BASELINE[1], after=0),
        client_cutin_frames=SKILL_CUTIN_FRAMES,
        # 交付要报的是这个数：作者手上感觉到的定住 = DSL 停球 + 客户端 cut-in（两段串行）。
        perceived_lock_frames=dict(before=STOPBALL_BASELINE[1] + SKILL_CUTIN_FRAMES,
                                   after=SKILL_CUTIN_FRAMES),
        damage_and_timing_unchanged=True,
        # 判定区主体是球 -18 且 trackingPos=True ⇒ 球不再被钉 10 帧，各段的发射原点会随球位移。
        # 这是「不定住球」的应有后果；交付时不可写成「位置不变」。
        beam_origin_follows_ball=True,
        ability_rows_unchanged=True,
        leader_rows_unchanged=True,
        unique_rows_unchanged=True,
        texts=dict(applied=with_text,
                   skill_description=SKILL_DESC_AFTER if with_text else SKILL_DESC_BEFORE))
    evidence = candidate.finish(metadata, apply=apply)
    evidence["plan"] = dict(dsl=dsl_plan, tables=table_plan, checks=checks)
    return evidence


def option_b_document(repo: Path, *, tiers=WINDUP_TIERS,
                      recommended: int = RECOMMENDED_WINDUP) -> dict:
    """方案 B 的备选产物（纯计算，返回文档＋每档的编码字节；写盘由 :func:`write_option_b` 做）。

    源树 = **live + 方案 A**（作者拍板 A＋B 时，B 是叠在 A 上发的）：
    优先读 workspace 候选（已含 A），候选缺了就读 live store 再当场 ``strip_ball_hold``。
    """
    store = core.resolve_profile("cn").store
    store = Path(store) if Path(store).is_absolute() else repo / store
    package = repo / WORKSPACE_REL / "package/roots/common"
    trees: dict[str, dict] = {}
    for program in SKILL_PROGRAMS:
        logical = wf_dsl.dsl_logical(program)
        live_path = core.table_path(store, logical)
        cand_path = package / logical
        if not live_path.is_file():
            raise WindupError(f"live store 里没有 {logical}")
        live_raw = live_path.read_bytes()
        live_tree = wf_dsl.parse_dsl(zlib.decompress(live_raw, -15))["tree"]
        if cand_path.is_file():
            source_raw = cand_path.read_bytes()
            source = wf_dsl.parse_dsl(zlib.decompress(source_raw, -15))["tree"]
        else:
            source_raw, source = live_raw, live_tree
        base = strip_ball_hold(source)          # 幂等：候选已经删过就原样返回
        trees[logical] = dict(program=program, live_raw=live_raw, live_tree=live_tree,
                              base=base, base_raw=encode_tree(base),
                              candidate_raw=source_raw)

    tier_docs = []
    files: dict[str, bytes] = {}
    for n in sorted(tiers):
        plan = windup_plan(n)
        entries = []
        for logical, info in trees.items():
            compressed = compress_windup(info["base"], first_beam_frame=n)
            failures = PH.dsl_gate_failures(PH.dsl_gates(compressed, element=ELEMENT))
            if failures:
                raise WindupError(f"{info['program']} @N={n}: {failures}")
            if compress_windup(compressed, first_beam_frame=n) != compressed:
                raise WindupError(f"{info['program']} @N={n}: compress is not idempotent")
            raw = encode_tree(compressed)
            name = f"windup-{n}/" + info["program"].rsplit("$", 1)[1] + ".action.dsl.amf3.deflate"
            files[name] = raw
            hashed = core.sha1_path(logical)
            entries.append(dict(
                program=info["program"], logical_path=logical,
                store_path=hashed[:2] + "/" + hashed[2:],
                file=name,
                before_sha256_live=_sha(info["live_raw"]),
                before_sha256_option_a=_sha(info["base_raw"]),
                after_sha256=_sha(raw), deflate_bytes=len(raw),
                report=windup_report(info["base"], compressed, plan)))
        first = entries[0]["report"]
        tier_docs.append(dict(
            first_beam_frame=n, recommended=(n == recommended), plan=plan,
            perceived_wait_seconds=first["perceived_wait_seconds"],
            radar_effect_finishes_before_first_beam=plan["radar"]["effect_finishes_before_first_beam"],
            charge_lead_frames=plan["charge"]["lead_before_first_beam"],
            # 技能两档各自的「自增益窗口多吃了几跳」（方案 B 唯一的数值外溢）
            self_buff_extra_hits={f"lv{e['program'][-1]}":
                                  e["report"]["self_buff_window"]["extra_hits_inside"]
                                  for e in entries},
            self_buff_extra_multiplier={f"lv{e['program'][-1]}":
                                        e["report"]["self_buff_window"]["extra_multiplier"]
                                        for e in entries},
            files=entries))
    return {"tiers": tier_docs, "recommended": recommended, "files": files}


def write_option_b(repo: Path, out_dir: Path, *, tiers=WINDUP_TIERS,
                   recommended: int = RECOMMENDED_WINDUP) -> dict:
    """把方案 B 的备选 DSL 与 plan-b.json 写到 ``out_dir``。**只写这个目录**，不碰候选包/live。"""
    document = option_b_document(repo, tiers=tiers, recommended=recommended)
    files = document.pop("files")
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, raw in sorted(files.items()):
        target = out_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        written.append(str(target.relative_to(repo)).replace("\\", "/"))
    document["written_files"] = written
    (out_dir / "plan-b.json").write_text(
        json.dumps(document, ensure_ascii=False, indent=1), encoding="utf-8")
    document["plan_b"] = str((out_dir / "plan-b.json").relative_to(repo)).replace("\\", "/")
    return document


def plan_document(evidence: dict) -> dict:
    """主控用的发布清单：逻辑路径 / 表键 / 推荐命令。"""
    plan = evidence["plan"]
    dsl_logicals = [item["logical_path"] for item in plan["dsl"]]
    table_logicals = [item["logical_path"] for item in plan["tables"]]
    return {
        "key": "tekuto",
        "character": {"id": CID, "code_name": CODE, "package": "s7-tekuto"},
        "author_request": "上次的特克托取消技能释放后的后摇 / 就是要去掉固定的这一段或者大幅缩短",
        "headline": f"玩家感知到的定住 {STOPBALL_BASELINE[1] + SKILL_CUTIN_FRAMES} 帧 → "
                    f"{SKILL_CUTIN_FRAMES} 帧（-14%）。"
                    f"数据层的停球确实从 {STOPBALL_BASELINE[1]} 帧清零，但它前面还压着客户端写死的 "
                    f"{SKILL_CUTIN_FRAMES} 帧技能 cut-in，两段串行 ⇒ 不要用「整段去掉固定」交差。",
        "change": f"技能两档删掉唯一一条 StopBall（DSL 侧停球 {STOPBALL_BASELINE[1]} 帧 → 0 帧；"
                  f"含客户端 cut-in 的总定住 {STOPBALL_BASELINE[1] + SKILL_CUTIN_FRAMES} → "
                  f"{SKILL_CUTIN_FRAMES} 帧）"
                  + ("；技能说明两处追加「释放技能后不再进入硬直，可立即行动」"
                     if plan["tables"] else "；本次未改文案"),
        "workspace_candidate": WORKSPACE_REL + "/package",
        "counts": {"dsl_files": len(dsl_logicals), "table_keys": len(table_logicals)},
        "dsl": plan["dsl"],
        "tables": [{k: v for k, v in item.items() if k != "inner_rows"} |
                   ({"inner_rows": item["inner_rows"]} if "inner_rows" in item else {})
                   for item in plan["tables"]],
        "server_mirror": ["cdndata/character_text.json"] if plan["tables"] else [],
        "author_question": "发布前请作者先回答一句：**你说的「固定」，是发动瞬间球被钉住（本轮改的就是它，"
                           "70→60 帧），还是发动后要等 1.5 秒才出激光（那是 f0–f90 的雷达扫描+瞄准线，"
                           "本轮没动，改它属于设计改动）？** 答案决定本包发不发、要不要再做一轮。",
        "findings": [
            "**【主假设：这次很可能改的不是作者说的那一段，建议作者拍板后再发】** "
            "特克托改前的停球是**全批最短的 10 帧**（黑/丝缇涅尔各 30 帧且作者已真机验收接受）。"
            "作者偏偏单独点名特克托 ⇒ 他感觉到的「固定」多半不是这 10 帧。"
            "特克托独有、且真的长的是**发动到第一段激光之间约 90 帧（1.5 s）的雷达扫描 + 瞄准线**："
            "f0 radar/aim_line → f5 Sector 判定 → f20 charge_S → f24 missile_launch → **f90 第一段激光**"
            "（之后 f150/210/270 三段、f332 终幕、f372–612 五个延长槽、f682 收炮）。"
            "黑/丝缇涅尔没有这段前摇。它**不定住球**（f70 之后球就能自由操作），但确实是"
            "「按下去之后等了一秒半才看见激光」。**缩短它会改伤害时序与段数窗口，属于设计改动，"
            "本轮没有授权、没有动**；要改请作者点头后按 STAGES 帧号整体前移。",
            f"**【交付口径：{STOPBALL_BASELINE[1] + SKILL_CUTIN_FRAMES} 帧 → {SKILL_CUTIN_FRAMES} 帧，"
            f"只少 14%】** 玩家感知到的定住 = dsl_stop_frames + client_cutin_frames。"
            f"数据层的停球确实 {STOPBALL_BASELINE[1]} → 0 清零了，但前面压着客户端写死的 "
            f"{SKILL_CUTIN_FRAMES} 帧 cut-in ⇒ 总数只从 {STOPBALL_BASELINE[1] + SKILL_CUTIN_FRAMES} 降到 "
            f"{SKILL_CUTIN_FRAMES}。按任务书的退路口径「≤原来约 1/4、约 12–15 帧以内」，"
            "**按感知帧数没有达到**（按数据层帧数则已清零）。结论不必回滚——数据层确实到底了，"
            "剩下的 60 帧已独立确认是客户端写死、数据层无杠杆——但给作者的第一句话必须是这个数，"
            "不能写成「整段去掉」。",
            "**live 改前的「固定」只有 10 帧**，不是任务书假设的长后摇：两棵树都是 "
            "movementPriority=1(NONE) + StopBall [-18, 10, RestoreToSpeedBeforeActionExecution, EF, 0]，"
            "且没有 SuppressBallActivity。对照（2026-09-21 从 live 逐棵实读）：官方母本 super_robot 是 "
            "tree[1]=2(STOP) + StopBall 140 帧 Stop（停住不恢复）；"
            "**同批黑 outlaw_panther_moon 与丝缇涅尔 still_obstinator_moon 至今 live 仍各带 "
            "StopBall [-18, 30, RestoreToSpeedBeforeActionExecution, AB, 0] + tree[1]=2(STOP)**，"
            "即它们是 60+30=90 帧。kit 首发时就已经做过一次「取消后摇」，这次是把最后 10 帧也清零。",
            "删完之后 DSL 侧一帧都不定住球，同时少掉 10 帧 suppressDirectAttack（直击不算数）"
            "与 10 帧「全队按不出技能」（BallImpl._canInvokeActionSkill 在 SkillMoving 期间恒 false）。",
            "**还剩下的那一段是客户端硬编码的 60 帧技能 cut-in**（引文 2026-09-21 复核更正）："
            "SquadManagerImpl.invokeActionSkill() 末尾 SquadManagerImpl.as:734-735 —— "
            "`stopForSkillCutin(60, Option.Some(primary));` 冻住除施法者以外的所有队，"
            "紧接着 `primary.invokeActionSkill(60, Option.Some(innovation));` → "
            "SquadImpl.invokeActionSkill → BallImpl.startToSkillCutin(60) 才是冻住施法者自己那颗球的出处。"
            "**上一版引的 MemberImpl.as:2593 是错的**：那句在 ActionKind.SummonsMultiball 分支，"
            "而且传 Option.Some(squad)，ActiveSquadManager.stopForSkillCutin(:119-141) 里 "
            "`_loc5_ = param2.params[0] == squad; if(!_loc5_)` 会**跳过施法者自己那一队** ⇒ 它冻的是别人的球。"
            "结论不变：字面量 60 对全角色一视同仁，数据层改不了（要改只能打 APK 补丁，本轮无授权）。",
            "**两段锁是串行的**（这是 70=60+10 的依据）：BallImpl 状态机 case 7（SkillCutin）"
            "要等 `stateFrame == 60` 才 `changeState(保存的状态)` 并 `innovation.invoke(this)` → "
            "ActionSkillInnovationData.invoke → invoker.startActionSkills(…) ⇒ **技能树是在 cut-in "
            "跑完的那一帧才开始执行的**，DSL f0 的 StopBall 排在 cut-in 之后。"
            "旁证：BallImpl.applyMovement 结尾若发现球正处在 SkillCutin(index 7)，"
            "会把新的 SkillMoving 塞进 cut-in 的「保存状态」槽等 cut-in 结束再生效，从不并行。",
            "**演出影响必须说准：伤害/段数/时序不变，但发射原点随球位移**（上一版写成"
            "「不改变任何一段的位置」，是事实性夸大，已更正）。这棵树 12 个 CreateHitArea 里 11 个"
            "主体是球 -18、第 7 参 trackingPos=True、坐标系 [\"GH\", 0]："
            "trackingPos=True ⇒ 判定区每帧重取球的位置；[\"GH\", 0] 走 ActionEffect.calcDir() case 3 ⇒ "
            "朝向 = atan2(锁定目标 − 球当前位置)，trackingDir=false 只冻住这个**数值**。"
            "球不再被钉 10 帧 ⇒ 此后每帧都比原来多飞 10 帧行程，f90/150/210/270/332 与 5 个延长槽的"
            "**发射原点（连带由原点算出的角度数值）都会落在不同位置**。"
            "不变的是伤害倍率、段数、帧号时序，以及「从球出发、指向 f0 锁定的那名敌人」这条语义"
            "（FindNearSubjects 在 f0 执行，两版球位置相同 ⇒ 锁的是同一个敌人）。"
            "这是「不定住球」的应有后果、不是缺陷，但不能当免检牌。"
            "唯一不受影响的是 f94 导弹落点（挂参照点 23，两个跟随位都 False，锚在锁定目标上）。",
        ],
        "device_checks": [
            "放技能，看球被钉住的时间：应当只剩客户端那 60 帧 cut-in（约 1 秒），"
            "cut-in 一结束球立刻恢复原来的速度和方向，不再多出一段 10 帧的停顿。",
            "**和黑（outlaw_panther_moon）对比时，特克托应当明显更跟手、比黑短约 30 帧（0.5 s）。**"
            "黑与丝缇涅尔 live 至今各带 StopBall 30 帧（movementPriority=2/STOP），即 60+30=90 帧；"
            "特克托改完 60 帧。**若两边手感完全一致，说明这次改动没生效，回头查**——"
            "绝不能拿「和黑一致」当通过。",
            "技能演出照常：雷达扫描 → 导弹 → f90 起四段逐级变粗的激光 → 终幕 → 5 个延长槽 → f682 收炮，"
            "段数、伤害、节奏与改前一致。允许的差异是**激光的发射原点会随球当时的位置不同**"
            "（球不再被钉住 ⇒ 位置对不上改前的录像），但每一段仍然指向被锁定的那名敌人。",
            "强化形态与 Codex 的半血重炮分支各放一次，确认两档技能树表现一致、没有掉段或空挥。",
            "**最关键的一条**：请作者确认他说的「固定」到底是哪一段——"
            "是发动瞬间球被钉住（本轮改的），还是发动后等 1.5 秒才出第一段激光（本轮没动）。"
            "如果是后者，本包即使真机没问题也解决不了他的问题，要再开一轮改 STAGES 帧号。",
        ],
        "caveats": [
            "本轮**没有动任何 ability / leader_ability / unique_condition 行**，"
            "Codex 的 wf_tekuto_low_hp.py / wf_tekuto_low_hp_candidate.py 两个文件也没有改。"
            "它们的断言只读行数据与 CreateBarrier，不读 StopBall ⇒ 本次改动不会把它们弄红"
            "（实测 test_tekuto_low_hp 全绿）。",
            "首发 kit ``wf_seasonal7_kit_tekuto.donor_tree`` 里那条 StopBall 已同步删掉，"
            "并新增门禁 ``ball_hold_problems()``（在 ``dsl_quick_problems`` 里调用）："
            "重跑 ``--step kit`` 再也带不回后摇。母本原形态仍然留在 ``TEMPLATE_STOPBALL`` 常量里，"
            "``template_stopball_drift()`` 会对官方母本逐值复核。",
            "技能说明加的那一句与本批黑 live 文案逐字一致。作者在 revision-20260916 说过"
            "「角色技能描述不再写太复杂省略一下」⇒ 如果主控判断这句话太啰嗦，"
            "用 ``--no-text`` 重跑本工具，只发两个 DSL 文件即可（plan 会自动只剩 dsl 段）。",
        ],
        "publish": {
            "gate": "**先问作者那句话再发**（见 author_question）。本包的改动只把感知定住从 "
                    f"{STOPBALL_BASELINE[1] + SKILL_CUTIN_FRAMES} 帧降到 {SKILL_CUTIN_FRAMES} 帧；"
                    "若作者说的「固定」其实是发动后 1.5 秒才出激光，发了也解决不了他的问题，"
                    "应当改成同一轮里一起动 STAGES 帧号（需作者授权）。"
                    "作者若确认就是球被钉住那一段，按下面几步直接发。",
            "note": "本代理不写 live、不登记 pending、不铸边。以下几步留给主控；"
                    "两个推送脚本都已在本机跑过 dry-run（不加 --apply 只预演）。",
            "steps": [
                "1) 2 个 DSL 文件：python -X utf8 " + REVISION_DIR + "/push_dsl_files.py   [--apply]",
                "2) 扁平表 character_text 的 139993 键："
                "python -X utf8 mod-tools/wf_pack_push_keys.py "
                "--workspace " + WORKSPACE_REL + " "
                "--key master/character/character_text.orderedmap:" + CID + "   [--apply]",
                "3) 嵌套表 action_skill 的 super_robot_tailcoat 键："
                "python -X utf8 " + REVISION_DIR + "/push_action_skill_key.py   [--apply]"
                "   —— wf_pack_push_keys 走不了嵌套表（实测 zlib incorrect header check），"
                "整表覆盖又会把别家角色的行退回包快照，所以用这个只搬一个外层键。",
                "4) 铸边：python -X utf8 mod-tools/wf_publish.py --tables "
                + ",".join(dsl_logicals + table_logicals),
                "5) 服务端镜像 assets/cdndata/character_text.json 的 139993 行："
                "python -X utf8 " + REVISION_DIR + "/push_server_mirror.py   [--apply]"
                "   —— 只改这一个键、其余字节原样保留（作者 WIP 单行大 JSON）；不进铸边。",
                "6) 生效并核对：./start-cn.bat -RestartOwned（或 reload_assets）→ "
                "python -X utf8 mod-tools/wf_publish.py --list（看版本边与键数："
                f"{len(dsl_logicals)} DSL / {len(table_logicals)} 表键）。",
            ],
            "wf_publish_tables": ",".join(dsl_logicals + table_logicals),
            "pending": "本代理没有登记 sync_pending（保持为空）。上面用 --tables 显式铸边，"
                       "不依赖 pending。",
            "flow_publish": "不做。整包 flow publish 需要作者当次明确授权；"
                            "本轮按 CLAUDE.md 走「键级改 live + wf_publish 裸表边 + 回写 workspace 候选」。",
            "server_mirror": "assets/cdndata/character_text.json 的 139993 行也要跟着改（候选包 "
                             "roots/server 已经是新文本）；它是作者 WIP 大 JSON，只做键级修改。",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--write-candidate", action="store_true",
                        help=f"把结果写进 {WORKSPACE_REL}/package（workspace 候选）")
    parser.add_argument("--plan-out", nargs="?", const=PLAN_REL, default=None,
                        help=f"把主控用的发布清单写到这里（默认 {PLAN_REL}）")
    parser.add_argument("--no-text", action="store_true",
                        help="只删 DSL 的固定段，不动技能说明文案")
    parser.add_argument("--windup-frames", type=int, nargs="*", default=None,
                        metavar="N",
                        help=f"【方案 B，默认关闭】把「发动→第一段激光」的前摇压到 N 帧并写备选产物；"
                             f"不给数字＝三档 {WINDUP_TIERS} 全出。**不会写候选包**。")
    parser.add_argument("--option-b-out", nargs="?", const=OPTION_B_REL, default=None,
                        help=f"方案 B 产物目录（默认 {OPTION_B_REL}）；给了 --windup-frames 就自动启用")
    args = parser.parse_args(argv)

    repo = TOOLS.parent

    if args.windup_frames is not None or args.option_b_out:
        if args.write_candidate:
            parser.error("--windup-frames（方案 B）不允许与 --write-candidate 同用："
                         "候选包永远只放方案 A，B 只写 option-b/ 备选目录")
        tiers = tuple(args.windup_frames) if args.windup_frames else WINDUP_TIERS
        out = Path(args.option_b_out or OPTION_B_REL)
        if not out.is_absolute():
            out = repo / out
        document = write_option_b(repo, out, tiers=tiers,
                                  recommended=(RECOMMENDED_WINDUP if RECOMMENDED_WINDUP in tiers
                                               else max(tiers)))
        print(json.dumps(document, ensure_ascii=False, indent=1))
        return 0

    evidence = apply_candidate(repo, apply=args.write_candidate, with_text=not args.no_text)
    document = plan_document(evidence)
    if args.plan_out:
        target = Path(args.plan_out)
        if not target.is_absolute():
            target = repo / target
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(document, ensure_ascii=False, indent=1), encoding="utf-8")
        document["written_to"] = str(target)
    document["applied"] = evidence["applied"]
    document["changed_files"] = evidence["changed_files"]
    print(json.dumps(document, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
