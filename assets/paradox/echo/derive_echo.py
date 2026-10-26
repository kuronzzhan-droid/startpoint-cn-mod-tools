#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""PARADOX（5920001）「技能回响」：从 live 技能 DSL 机械推导 25% 复刻树（只读调研脚本）。

范围（作者 2026-09-28 口径）：基诺维 169999 / 杰拉德 149999 / 凯尔 139990。赛瑞斯 129999 已由作者移出本批。

用法（只读 live，不写 store / .cdn / assets / work / git）::

    python derive_echo.py            # 推导 → 校验 → 写 echo_dsl/<code>.json，打印改动日志与伤害预算
    python derive_echo.py --check    # 只推导 + 校验，并与磁盘上的 echo_dsl/<code>.json 比对（不写盘）
    python derive_echo.py --print    # 额外打印原树 / 回响树的可读形式

推导规则（依据见同目录 skill-echo.md「机制取证」）：

* 源：action_skill[<code>]["2"]（＋进化版）的 program_path；live 字节 sha256 钉死（漂移即停）。
  同时核对 character c9–c16 的形态切换：基诺维/凯尔的 switched 程序与本体同一路径（只为语音），杰拉德无切换。
* 保留树形：ConditionalsChangeSkillFlag 两支都保留（629 上下文的 abilityPower 取自装备者，与本体同一面板开关）。
* 删除（不按比例缩放，整条去掉）：
  - 演出与控球：ShowEffect / HideEffect / ShakeCamera / StopBall / MoveBall（629 不播语音/cut-in；
    装备 DSL 会给所有 PARADOX 持有者预载，带特效=把三个角色的特效图集塞进任何带 PARADOX 的队伍）。
  - 召唤/吞噬：ConditionalsMultiballNumber 整块（MultiballNumberVariable + RemoveMultiball + 吞噬攻击）。
  - 固有状态机：ACUnique 付与、以 DCUnique 为条件的 ConditionalsConditionAccumulationNumber 整块（基诺维首放血契）。
  - 自身/队伍扣血：打在己方主体上的 CreateRatioAttack（及只包着它的 HP 条件分支）。
  - 驱散：DeleteCondition（「消除 2 个强化」×25% = 0.5 个，取 0）。
  - 非加算型状态：ACPiercing / ACFlying（布尔状态，且会再触发队长「贯穿」增长/回槽链）、ACFixedSpeed（取优，模式量）、
    ACAdditionalDirectAttack（getBetter 取优）、ACSpeedup（本体 +100% 已顶到普通加速上限）、ACFrozen / ACParalysis
    （共享 gid「S//FROZEN」「S//PARALYSIS」+ 对敌递减计数，会缩短本体下一次冻结/麻痹）。
* 缩放 ×0.25：CreateNormalAttack 的 p4 固定伤害（取整）/ p5 攻击倍率 / p13 Fever 值；
  p12 削韧按 DETOUGHNESS_POLICY（默认 "zero"＝回响不削韧，依据作者平衡口径 B.3「629 每次 ≤3、CT≤3 秒 ≤1」）；
  CreateCondition 里 ACAttackPoint / ACSkillDamage / ACDirectDamage / ACToleranceOfElement 的强度；
  CreateBarrier 比例；打在敌方的 CreateRatioAttack 各项（含 mul 项）。
* 不缩放：持续帧、判定区尺寸/寿命/间隔/段数上限、命中率、层数上限、驱散外的一切形状参数。
* SLv 折叠：所有 {min,max} 取 max（SLv 满级）后写成 min==max —— 629 以 SLvALv.Alv(装备能力强度) 解析，
  min≠max 会随武器突破插值，在 learn==max 的强化行里更会抛 ClientError 14510。
* 属性：CreateNormalAttack 的 255 → 角色 1-based 元素码（暗 6 / 光 5 / 雷 3）。装备 629 预载时 owner 元素=6（无属性），
  255 + Fine/Coarse/Slash/CriticalSlash 在预载即抛 C10013；显式元素让预载与实战取同一套命中素材。
* 杰拉德冲刺斩：原判定区挂在球上（-18 / EF，半径 30，靠 MoveBall 撞上敌人）；回响不动球，改挂最近敌人
  （FindNearSubjects 绑定 12 + CreateHitArea(12, AB, Circle 1, 寿命 5, 1 hit)），照官方 black_wolf_knight_1 写法。
* 凯尔三段斩的参考点：原点=球、GH 系偏移 (0,-250)（= 球前方 250px 朝最近敌人，靠 MoveBall 冲过去）；
  回响不动球，改为以最近敌人为原点的 AB (0,0) 定点（官方 FindNear(49)+AB 参考点 89 例），三段判定区原样挂在该点上。
* 键串：每条 CreateCondition 写非空键 ``paradox_echo_<code>_<buff>``；同一逻辑 buff（含 TargetMate 复写）同键。
* 时机：根下 Event Wait(N 帧) 包住整棵回响；instant_delay 保持 0（该列单位是秒，×60 帧）。
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]                      # mod-tools/assets/paradox/echo → 仓库根
sys.path.insert(0, str(ROOT / "mod-tools"))


class live:  # noqa: N801  只读 shim（原调研脚本用诅咒武器批次的 live.py）
    import functools as _ft
    import wf_mod_tool as _C
    import wf_quest_lib as _Q
    S = Path(_C.resolve_active_store())

    @staticmethod
    @_ft.lru_cache(maxsize=None)
    def flat(logical: str) -> dict:
        C_ = live._C
        rows = C_.read_orderedmap_file(C_.table_path(live.S, logical), logical).text_rows()
        return {k: C_.read_csv_lines(v) for k, v in rows.items()}

    @staticmethod
    @_ft.lru_cache(maxsize=None)
    def nested(logical: str) -> dict:
        return live._Q.parse_node(live._C.table_path(live.S, logical).read_bytes())

import wf_client_legality as L  # noqa: E402
import wf_cursed_weapons as W  # noqa: E402
import wf_dsl  # noqa: E402
import wf_dsl_sig as SIG  # noqa: E402
import wf_mod_tool as C  # noqa: E402

SCALE = 0.25
#: 削韧（CreateNormalAttack p12 basicDetoughness）策略。作者平衡口径 B.3（平衡调整批次-20260927/batch2/第二批施工口径.md）：
#: 「能力调用技能（kind 629）每次 ≤3；触发 CT ≤3 秒的每次 ≤1」。回响本身就是 629、触发 CT=0，×0.25 后单目标
#: 仍有 7.5 / 18.375 / 7.5，全部超线 ⇒ 默认 "zero"（回响不削韧）；作者若放行改 "scale"。
DETOUGHNESS_POLICY = "zero"          # "zero" | "scale"
OUT_DIR = HERE
ECHO_DIR = "battle/action/skill/action/ability_skill/paradox"

#: code -> 施工参数。sha256 = live store 文件（deflate 后）字节，改动即停（fail closed）。
CHARACTERS: dict[str, dict] = {
    "ginovi": {
        "cid": "169999", "name": "基诺维", "evolution": "2",
        "program": "battle/action/skill/action/rare5/ginovi$ginovi_2",
        "sha256": "0c7b275ba0822e7a",           # 前 16 位；_1 与 _2 逐字节相同
        "switched": "ginovi_voice_ready",          # c9=3 ChangeSkillFlag → c14
        "wait": 60,
    },
    "white_wolf_gerald": {
        "cid": "149999", "name": "杰拉德", "evolution": "2",
        "program": "battle/action/skill/action/rare5/white_wolf_gerald$white_wolf_gerald_2",
        "sha256": "f27b8a14af3b",
        "switched": None,                          # c9=(None)
        "wait": 90,
        "dash_rebind": True,
    },
    "kyle_moon": {
        "cid": "139990", "name": "凯尔", "evolution": "2",
        "program": "battle/action/skill/action/rare5/kyle_moon$kyle_moon_2",
        "sha256": "930ade220459",
        "switched": "kyle_moon_voice_ready",       # c9=1 ConditionExist(c10=31 Piercing) → c14
        "wait": 100,
        "refpoint_rebind": True,
    },
}

PRESENTATION = {"ShowEffect", "HideEffect", "ShakeCamera", "StopBall", "MoveBall"}
DEVOUR = {"ConditionalsMultiballNumber", "MultiballNumberVariable", "RemoveMultiball"}
KEEP_AS_IS = {"BindConditionAccumulationVariable"}
#: MemberImpl 直接 throw 的玩家侧命令（MemberImpl.as createXxx / spawnXxx / cancelXxx），回响里必须为零。
MEMBER_THROWS = {"CreateTargetAttack", "CreateWindAttack", "CreateGravitationalField", "CancelGravitationalField",
                 "CreateFlood", "CancelFlood", "CreateShield", "CancelShield", "CreateTornado",
                 "CreateOneWayWallGimmick", "RemoveOneWayWallGimmick", "SpawnFunnel", "EliminateFunnel",
                 "EliminateAllFunnel", "SpawnAlterEgo", "EliminateAlterEgo"}
#: 629 上下文 executionCount=null，ConditionalsNumExecutions* 会抛 C16101。
NEEDS_EXECUTION_COUNT = {"ConditionalsNumExecutionsOddOrEven", "ConditionalsNumExecutions2",
                         "ConditionalsNumExecutions3", "ConditionalsNumExecutions4", "ConditionalsNumExecutions5"}

AC_REMOVE = {
    "ACUnique": "固有状态机（死印/黑翼加护/月狼·觉/时空侵蚀等由能力读取）",
    "ACPiercing": "布尔状态；会再触发「状态贯穿」类能力（凯尔队长永久+20%攻、能力3回槽；基诺维贯穿保持成长）",
    "ACFlying": "布尔状态，无强度可缩",
    "ACFixedSpeed": "球速模式量，getFixedSpeedValues 取优，弱版无意义",
    "ACAdditionalDirectAttack": "getAdditionalDirectAttack 用 getBetter 取优，弱版被本体压住",
    "ACSpeedup": "本体已给 +100%（普通加速上限），回响重叠期无效，只在尾巴改球速",
    "ACFrozen": "共享 gid S//FROZEN；对敌递减计数会缩短本体下一次冻结",
    "ACParalysis": "共享 gid S//PARALYSIS；同上",
}
#: AC 名 → (强度所在下标, 键缩写)。下标按 ["ACName", p0, p1, ...] 数组计。
AC_SCALE = {"ACAttackPoint": (2, "atk"), "ACSkillDamage": (2, "skd"), "ACDirectDamage": (2, "dd"),
            "ACToleranceOfElement": (3, "res"), "ACStun": (2, "stun")}

ALLY_SELECTORS = {33, 34, 35, 82, 86, 87, 97, 113, 129, 130, 131, 145, 147}
ENEMY_SELECTORS = {49, 50, 51, 52}


class EchoError(RuntimeError):
    pass


def _require(ok: bool, msg: str) -> None:
    if not ok:
        raise EchoError(msg)


def num(v: float):
    v = round(float(v), 6)
    return int(v) if v == int(v) else v


def scale_slv(arr, factor: float = SCALE):
    """[{min,max[,mul]}...] 每项 ×factor（mul 变量保留）。"""
    _require(isinstance(arr, list) and all(isinstance(t, dict) and "min" in t for t in arr), f"不是 SLv 数组: {arr!r:.80}")
    out = []
    for t in arr:
        t2 = dict(t)
        t2["min"], t2["max"] = num(t["min"] * factor), num(t["max"] * factor)
        out.append(t2)
    return out


def slv_max(arr) -> float:
    return float(arr[0]["max"])


def pct_tag(v: float) -> str:
    p = int(round(v * 100))
    return f"m{-p}" if p < 0 else str(p)


class Deriver:
    def __init__(self, code: str, spec: dict, char_element: int):
        self.code = code
        self.spec = spec
        self.char_element = char_element          # 0 基内部元素（character c3）
        self.dsl_element = char_element + 1       # DSL 1-based
        self.log: list[dict] = []

    # ---------------------------------------------------------------- 日志
    def note(self, path: str, action: str, what: str, detail: str = "") -> None:
        self.log.append({"path": path, "action": action, "what": what, "detail": detail})

    # ---------------------------------------------------------------- 主入口
    def derive(self, tree: list) -> list:
        _require(isinstance(tree, list) and tree[0] == "ActionDsl" and len(tree) == 12, "源 DSL 根形状不对")
        _require(tree[10] == 0, f"源 buffTargetAs={tree[10]}，本脚本只处理 0")
        body = self.block(copy.deepcopy(tree[11]), {}, "root")
        _require(body[1], "回响树推导后为空")
        root = ["ActionDsl", 1, ["None"], False, False, False, False, False, False, False, 0,
                ["Block", [["Event", ["Wait", int(self.spec["wait"]), "*", body]]]]]
        self.note("root", "wrap", "Event Wait", f"{self.spec['wait']} 帧后执行；根头部改为 1/None/false×7/0")
        self.collapse_slv(root, "root")
        return root

    # ---------------------------------------------------------------- 表达式
    def block(self, blk: list, scope: dict, path: str) -> list:
        _require(isinstance(blk, list) and blk and blk[0] == "Block", f"{path}: 期望 Block，得到 {blk!r:.60}")
        out = []
        for i, child in enumerate(blk[1]):
            out += self.expr(child, scope, f"{path}/{i}")
        # TargetMate 只对后续兄弟生效；后面没人用它的绑定号就去掉
        pruned = []
        for i, child in enumerate(out):
            if child[0] == "Command" and child[1][0] == "TargetMate":
                bid = child[1][1]
                used = any(_uses_subject(sib, bid) for sib in out[i + 1:])
                if not used:
                    self.note(path, "remove", "TargetMate", f"绑定 {bid} 之后已无语句使用")
                    continue
            pruned.append(child)
        return ["Block", pruned]

    def expr(self, node: list, scope: dict, path: str) -> list:
        kind = node[0]
        if kind == "Block":
            b = self.block(node, scope, path)
            return [b] if b[1] else []
        if kind == "Event":
            name, params = node[1][0], node[1][1:]
            _require(name == "Wait", f"{path}: 未处理的事件 {name}")
            inner = self.block(params[2], scope, f"{path}.Wait")
            if not inner[1]:
                self.note(path, "remove", "Wait", "内部全部被删除")
                return []
            return [["Event", ["Wait", params[0], params[1], inner]]]
        _require(kind == "Command", f"{path}: 未知节点 {kind}")
        c = node[1]
        name = c[0]
        handler = getattr(self, "cmd_" + name, None)
        if name in PRESENTATION:
            self.note(path, "remove", name, "演出/控球")
            return []
        if name in DEVOUR:
            self.note(path, "remove", name, "召唤/吞噬协力球")
            return []
        if name in KEEP_AS_IS:
            self.note(path, "keep", name, "只读变量绑定")
            return [node]
        _require(handler is not None, f"{path}: 未覆盖的命令 {name}（fail closed，先补规则）")
        return handler(c, scope, path)

    # ---------------------------------------------------------------- 选择器 / 容器
    def cmd_FindAllSubjects(self, c, scope, path):
        bid, selector = c[1], c[2]
        inner = dict(scope)
        inner[bid] = "ally" if selector in ALLY_SELECTORS else "enemy" if selector in ENEMY_SELECTORS else f"sel{selector}"
        body = self.block(c[9], inner, f"{path}.FindAll({bid},{selector})")
        if not body[1]:
            self.note(path, "remove", "FindAllSubjects", f"选择器 {selector} 下已无语句")
            return []
        c2 = list(c)
        c2[9] = body
        return [["Command", c2]]

    def cmd_FindNearSubjects(self, c, scope, path):
        origin, count, selector, not_found, bid, body = c[1:7]
        if self.spec.get("dash_rebind") and self._is_ball_dash(body):
            return self._rebind_dash(c, scope, path)
        inner = dict(scope)
        inner[bid] = "ally" if selector in ALLY_SELECTORS else "enemy" if selector in ENEMY_SELECTORS else f"sel{selector}"
        new_body = self.block(body, inner, f"{path}.FindNear({bid},{selector})")
        if not new_body[1]:
            self.note(path, "remove", "FindNearSubjects", f"选择器 {selector} 下已无语句")
            return []
        c2 = list(c)
        c2[6] = new_body
        if isinstance(not_found, list) and not_found and not_found[0] == "CreateImaginaryTarget":
            c2[4] = ["DoNothing"]
            self.note(path, "change", "FindNearSubjects", "找不到敌人时 CreateImaginaryTarget → DoNothing（回响不控球，无需假目标）")
        return [["Command", c2]]

    def cmd_CreateReferencePoint(self, c, scope, path):
        bid = c[10]
        inner = dict(scope)
        inner[bid] = "refpoint"
        body = self.block(c[11], inner, f"{path}.RefPoint({bid})")
        if not body[1]:
            self.note(path, "remove", "CreateReferencePoint", "只承载特效，特效删除后为空")
            return []
        c2 = list(c)
        c2[11] = body
        coord = c[2]
        if (self.spec.get("refpoint_rebind") and c[1] == -18 and isinstance(coord, list) and coord[0] == "GH"
                and scope.get(coord[1]) == "enemy"):
            # 原点 = 球 + GH 系偏移（GH 旋转 = atan2(敌-球)+π/2，dy=-250 即「球前方 250px、朝敌」）；
            # 本体靠 MoveBall 冲过去，回响不控球 → 改为以最近敌人为原点的 AB 定点（官方 FindNear(49)+AB 89 例）。
            c2[1], c2[2], c2[3], c2[4], c2[5] = coord[1], ["AB"], 0, 0, 0
            self.note(path, "rebind", "CreateReferencePoint",
                      f"原点 球(-18)+GH({coord[1]}) 偏移 ({c[3]},{c[4]}) → 最近敌人 {coord[1]} 的 AB (0,0)；"
                      f"寿命 {c[9]} 帧、绑定 {bid} 不变")
        return [["Command", c2]]

    def cmd_CreateReferencePointAtSpecifiedPosition(self, c, scope, path):
        inner = dict(scope)
        inner[c[4]] = "refpoint"
        body = self.block(c[5], inner, f"{path}.RefPointAt({c[4]})")
        if not body[1]:
            self.note(path, "remove", "CreateReferencePointAtSpecifiedPosition", "只承载特效，特效删除后为空")
            return []
        c2 = list(c)
        c2[5] = body
        return [["Command", c2]]

    def cmd_TargetMate(self, c, scope, path):
        scope[c[1]] = "mate"          # 语句级绑定：对后续兄弟生效（scope 是本 Block 的可变副本）
        self.note(path, "keep", "TargetMate", "联机队友通道，只送状态")
        return [["Command", list(c)]]

    # ---------------------------------------------------------------- 条件分支
    def cmd_ConditionalsChangeSkillFlag(self, c, scope, path):
        then = self.block(c[2], dict(scope), f"{path}.Flag{c[1]}=on")
        other = self.block(c[3], dict(scope), f"{path}.Flag{c[1]}=off")
        if not then[1] and not other[1]:
            self.note(path, "remove", "ConditionalsChangeSkillFlag", "两支皆空")
            return []
        self.note(path, "keep", "ConditionalsChangeSkillFlag", f"flag {c[1]} 两支都保留（abilityPower 取自装备者）")
        return [["Command", [c[0], c[1], then, other]]]

    def cmd_ConditionalsHealthPointRatioOf(self, c, scope, path):
        then = self.block(c[3], dict(scope), f"{path}.HP>={c[2]}%")
        other = self.block(c[4], dict(scope), f"{path}.HP<{c[2]}%")
        if not then[1] and not other[1]:
            self.note(path, "remove", "ConditionalsHealthPointRatioOf", f"主体 {c[1]} 的两支皆空（扣血已删）")
            return []
        return [["Command", [c[0], c[1], c[2], then, other]]]

    def cmd_ConditionalsConditionAccumulationNumber(self, c, scope, path):
        kind = c[1]
        _require(isinstance(kind, list) and kind[0] == "DCUnique",
                 f"{path}: 非固有状态条件 {kind!r}，未定义规则")
        self.note(path, "remove", "ConditionalsConditionAccumulationNumber",
                  f"固有状态 {kind[1]} 门控整块（状态机；基诺维=首放血契：95% 扣血 + 60% 护盾 + 付与血契）")
        return []

    # ---------------------------------------------------------------- 效果
    def cmd_DeleteCondition(self, c, scope, path):
        self.note(path, "remove", "DeleteCondition", f"驱散 {c[2]!r}×{c[3]}：25% 取整为 0")
        return []

    def cmd_CreateRatioAttack(self, c, scope, path):
        subj = c[1]
        kind = scope.get(subj, "builtin" if subj < 0 else "unbound")
        if kind in ("ally", "mate") or subj in (-17,):
            self.note(path, "remove", "CreateRatioAttack", f"打在己方（{kind}）= 扣血代价")
            return []
        _require(kind in ("enemy", "hit"), f"{path}: CreateRatioAttack 主体 {subj} 种类 {kind} 未定义")
        before = c[3]
        c2 = list(c)
        c2[3] = scale_slv(before)
        self.note(path, "scale", "CreateRatioAttack", f"{_fmt(before)} ⇒ {_fmt(c2[3])}（{'当前' if c[2] == 1 else '最大'}HP 比例）")
        return [["Command", c2]]

    def cmd_CreateBarrier(self, c, scope, path):
        c2 = list(c)
        c2[2] = scale_slv(c[2])
        self.note(path, "scale", "CreateBarrier", f"{_fmt(c[2])} ⇒ {_fmt(c2[2])}（护盾取大，不叠加）")
        return [["Command", c2]]

    def cmd_CreateNormalAttack(self, c, scope, path):
        c2 = list(c)
        element = c[2]
        if element == 255:
            c2[2] = self.dsl_element
            self.note(path, "change", "CreateNormalAttack.element", f"255 → {self.dsl_element}（显式元素，避 C10013）")
        else:
            _require(element == self.dsl_element, f"{path}: 显式元素 {element} ≠ 角色元素 {self.dsl_element}")
        c2[5] = int(round(c[5] * SCALE))
        c2[6] = scale_slv(c[6])
        c2[13] = scale_slv(c[13], 0.0 if DETOUGHNESS_POLICY == "zero" else SCALE)
        c2[14] = scale_slv(c[14])
        self.note(path, "scale", "CreateNormalAttack",
                  f"倍率 {_fmt(c[6])} ⇒ {_fmt(c2[6])}，固定 {c[5]} ⇒ {c2[5]}，削韧 {_fmt(c[13])} ⇒ {_fmt(c2[13])}，"
                  f"Fever {_fmt(c[14])} ⇒ {_fmt(c2[14])}，命中特效 {c[15][0]}")
        return [["Command", c2]]

    def cmd_CreateCondition(self, c, scope, path):
        kept, tags = [], []
        for ac in c[2]:
            name = ac[0]
            if name in AC_REMOVE:
                self.note(path, "remove", name, AC_REMOVE[name])
                continue
            _require(name in AC_SCALE, f"{path}: 未定义规则的 AC {name}")
            idx, abbr = AC_SCALE[name]
            ac2 = list(ac)
            ac2[idx] = scale_slv(ac[idx])
            orig = slv_max(ac[idx])
            tag = f"{abbr}{ac[2]}_{pct_tag(orig)}" if name == "ACToleranceOfElement" else f"{abbr}{pct_tag(orig)}"
            tags.append(tag)
            kept.append(ac2)
            self.note(path, "scale", name, f"强度 {_fmt(ac[idx])} ⇒ {_fmt(ac2[idx])}，持续 {_fmt(ac[1])} 帧不变")
        if not kept:
            self.note(path, "remove", "CreateCondition", "AC 全部被删")
            return []
        c2 = list(c)
        c2[2] = kept
        old_key = c[7]
        c2[7] = f"paradox_echo_{self.code}_{'_'.join(tags)}"
        self.note(path, "change", "CreateCondition.key", f"{old_key!r} → {c2[7]!r}")
        return [["Command", c2]]

    def cmd_CreateHitArea(self, c, scope, path):
        on_create_scope = dict(scope)
        on_create_scope[c[19]] = "hitarea"
        on_hit_scope = dict(scope)
        on_hit_scope[c[21]] = "hitarea"
        on_hit_scope[c[22]] = "hit"
        on_create = self.block(c[20], on_create_scope, f"{path}.HA.onCreate")
        on_hit = self.block(c[23], on_hit_scope, f"{path}.HA.onHit")
        if not on_hit[1]:
            self.note(path, "remove", "CreateHitArea", "onHit 为空")
            return []
        c2 = list(c)
        c2[20], c2[23] = on_create, on_hit
        return [["Command", c2]]

    # ---------------------------------------------------------------- 杰拉德冲刺斩改挂最近敌人
    @staticmethod
    def _is_ball_dash(body) -> bool:
        names = [x[1][0] for x in body[1] if x[0] == "Command"]
        return "MoveBall" in names and any(
            x[0] == "Command" and x[1][0] == "CreateHitArea" and x[1][2] == -18 and x[1][3] == ["EF"]
            for x in body[1])

    def _rebind_dash(self, c, scope, path):
        bid = c[5]
        for x in c[6][1]:
            if x[0] == "Command" and x[1][0] in PRESENTATION:
                self.note(path, "remove", x[1][0], "冲刺演出/控球")
        area = next(x[1] for x in c[6][1] if x[0] == "Command" and x[1][0] == "CreateHitArea")
        hit_scope = dict(scope)
        hit_scope[area[21]] = "hitarea"
        hit_scope[area[22]] = "hit"
        on_hit = self.block(area[23], hit_scope, f"{path}.dash.onHit")
        _require(on_hit[1], f"{path}: 冲刺斩 onHit 推导后为空")
        # 官方 black_wolf_knight_1：FindNearSubjects(-18,100,50,…,3){CreateHitArea("*",3,AB,…,Circle 1,寿命5,1 hit)}
        new_area = ["CreateHitArea", "*", bid, ["AB"], 0, 0, 0, False, False,
                    ["Circle", [{"min": 1, "max": 1}]], ["Center"], ["Center"], ["Single"],
                    ["SpecifyHitAreaLifetimeDirectly", 5], ["CalculatedUsingMaxNumOfHits", 1], ["None"],
                    False, True, ["None"], area[19], ["Block", []], area[21], area[22], on_hit,
                    area[24], area[25], area[26]]
        c2 = list(c)
        c2[4] = ["DoNothing"]
        c2[6] = ["Block", [["Command", new_area]]]
        self.note(path, "rebind", "FindNearSubjects+CreateHitArea",
                  f"冲刺斩：球上 EF 半径 30（靠 MoveBall 撞敌）→ 挂最近敌人 {bid} 的 AB 半径 1、寿命 5、1 hit；"
                  f"buffTargetAs 覆盖 {area[24]} 保留")
        return [["Command", c2]]

    # ---------------------------------------------------------------- SLv 折叠
    def collapse_slv(self, node, path: str) -> None:
        if isinstance(node, dict):
            if "min" in node and "max" in node and node["min"] != node["max"]:
                self.note(path, "collapse", "SLv", f"{node['min']}→{node['max']} 取满级 {node['max']}")
                node["min"] = node["max"]
            for v in node.values():
                self.collapse_slv(v, path)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                self.collapse_slv(v, f"{path}/{i}" if len(path) < 60 else path)


def _uses_subject(node, sid: int) -> bool:
    """粗查：节点树里是否有命令把 sid 当主体（第一个参数）。"""
    if isinstance(node, list):
        if node and node[0] == "Command" and isinstance(node[1], list) and len(node[1]) > 1 and node[1][1] == sid:
            return True
        return any(_uses_subject(x, sid) for x in node)
    if isinstance(node, dict):
        return any(_uses_subject(x, sid) for x in node.values())
    return False


def _fmt(v) -> str:
    if isinstance(v, list) and v and all(isinstance(t, dict) and "min" in t for t in v):
        parts = []
        for t in v:
            s = f"{t['min']:g}" if t["min"] == t["max"] else f"{t['min']:g}→{t['max']:g}"
            if "mul" in t:
                s += f"×var{t['mul']}"
            parts.append(s)
        return "+".join(parts)
    return json.dumps(v, ensure_ascii=False)


# ------------------------------------------------------------------------ 伤害预算
def damage_budget(tree: list, flag_on: bool) -> dict:
    """单目标满额：Σ(倍率 × 段数上限)、Σ(削韧 × 段数上限)、Σ(Fever × 段数上限)。
    ChangeSkillFlag 按 flag_on 取一支；HP 条件取「是」支。"""
    total = {"multiplier_hits": 0.0, "detoughness_hits": 0.0, "fever_hits": 0.0, "ratio_terms": []}

    def cna_hits(area) -> int:
        some = area[15]
        if isinstance(some, list) and some[0] == "Some":
            return int(some[1][0]["max"])
        calc = area[14]
        if isinstance(calc, list) and calc[0] == "CalculatedUsingMaxNumOfHits":
            return int(calc[1])
        return 1

    def walk(node, hits: int, scope: dict) -> None:
        if isinstance(node, list) and node:
            if node[0] == "Command":
                c = node[1]
                name = c[0]
                if name == "ConditionalsChangeSkillFlag":
                    walk(c[2] if flag_on else c[3], hits, scope)
                    return
                if name == "ConditionalsHealthPointRatioOf":
                    walk(c[3], hits, scope)
                    return
                if name == "ConditionalsConditionAccumulationNumber":
                    walk(c[3], hits, scope)   # 血契已有 → 空支（常态）
                    return
                if name == "ConditionalsMultiballNumber":
                    return                    # 吞噬按球数，另计
                if name == "FindAllSubjects":
                    walk(c[9], hits, {**scope, c[1]: "enemy" if c[2] in ENEMY_SELECTORS else "other"})
                    return
                if name == "FindNearSubjects":
                    walk(c[6], hits, {**scope, c[5]: "enemy" if c[3] in ENEMY_SELECTORS else "other"})
                    return
                if name == "CreateHitArea":
                    walk(c[23], cna_hits(c), scope)
                    return
                if name == "CreateNormalAttack":
                    total["multiplier_hits"] += float(c[6][0]["max"]) * hits
                    total["detoughness_hits"] += float(c[13][0]["max"]) * hits
                    total["fever_hits"] += float(c[14][0]["max"]) * hits
                    return
                if name == "CreateRatioAttack":
                    if scope.get(c[1]) == "enemy":
                        total["ratio_terms"].append(_fmt(c[3]))
                    return
                for x in c[1:]:
                    walk(x, hits, scope)
                return
            for x in node:
                walk(x, hits, scope)
        elif isinstance(node, dict):
            for x in node.values():
                walk(x, hits, scope)

    walk(tree[11], 1, {})
    for k in ("multiplier_hits", "detoughness_hits", "fever_hits"):
        total[k] = round(total[k], 6)
    return total


# ------------------------------------------------------------------------ 校验
def custom_problems(tree: list, code: str, dsl_element: int, wait: int) -> list[str]:
    probs: list[str] = []
    _require(tree[0] == "ActionDsl" and len(tree) == 12, "根形状")
    top = tree[11][1]
    if not (len(top) == 1 and top[0][0] == "Event" and top[0][1][0] == "Wait" and top[0][1][1] == wait):
        probs.append("根不是单个 Event Wait")

    def walk(node) -> None:
        if isinstance(node, dict):
            if "min" in node and "max" in node and node["min"] != node["max"]:
                probs.append(f"SLv 未折叠 {node}")
            for v in node.values():
                walk(v)
            return
        if not isinstance(node, list) or not node:
            return
        if node[0] in ("Command", "Event") and isinstance(node[1], list):
            c = node[1]
            name = c[0]
            if name in MEMBER_THROWS:
                probs.append(f"玩家侧 throw 命令 {name}")
            if name in NEEDS_EXECUTION_COUNT:
                probs.append(f"{name} 在 629 上下文 executionCount=null → C16101")
            if name in PRESENTATION or name in DEVOUR or name == "DeleteCondition":
                probs.append(f"残留应删命令 {name}")
            if name == "CreateNormalAttack" and c[2] != dsl_element:
                probs.append(f"CreateNormalAttack 元素 {c[2]} ≠ {dsl_element}")
            if name == "CreateCondition":
                if not (isinstance(c[7], str) and c[7].startswith(f"paradox_echo_{code}_")):
                    probs.append(f"CreateCondition 键串 {c[7]!r} 不合规")
                for ac in c[2]:
                    if ac[0] in AC_REMOVE:
                        probs.append(f"残留应删 AC {ac[0]}")
        for v in node:
            walk(v)

    walk(tree)
    return probs


def all_checks(tree: list, code: str, char_element: int, wait: int) -> dict[str, list[str]]:
    return {
        "dsl_signature_problems": W.dsl_signature_problems(tree),
        "colorless_hit_effect_problems": W.colorless_hit_effect_problems(tree),
        "action_dsl_element_problems": L.action_dsl_element_problems(tree, char_element),
        "action_dsl_subject_binding_problems": L.action_dsl_subject_binding_problems(tree),
        "action_dsl_lookup_scope_problems": L.action_dsl_lookup_scope_problems(tree),
        "action_dsl_hit_area_target_problems": L.action_dsl_hit_area_target_problems(tree),
        "player_side_dsl_problems": wf_dsl.player_side_dsl_problems(tree),
        "custom": custom_problems(tree, code, char_element + 1, wait),
    }


def roundtrip(tree: list) -> tuple[bool, str]:
    """encode_amf3 → parse_dsl 等价；再走发布链同款 wf_character_revision.encode_tree（raw deflate -15）解回等价。
    返回 (是否通过, 落盘字节 sha256 前 16 位)。"""
    import wf_character_revision as REV       # 只用其 encode_tree（纯函数）
    data = wf_dsl.encode_amf3(tree)
    ok = wf_dsl.parse_dsl(data)["tree"] == tree and wf_dsl.encode_amf3(wf_dsl.parse_dsl(data)["tree"]) == data
    stored = REV.encode_tree(tree)
    ok = ok and wf_dsl.parse_dsl(zlib.decompress(stored, -15))["tree"] == tree
    return ok, hashlib.sha256(stored).hexdigest()[:16]


# ------------------------------------------------------------------------ 读 live
def load_source(code: str, spec: dict) -> tuple[list, int, bytes]:
    ch = live.flat("master/character/character.orderedmap")[spec["cid"]][0]
    _require(ch[0] == code, f"{spec['cid']} code_name {ch[0]} ≠ {code}")
    _require(ch[8] == code, f"{code} action_skill 列 {ch[8]}")
    char_element = int(ch[3])
    # 技能表：＋进化版 program_path
    rows = live.nested("master/skill/action_skill.orderedmap")[code]
    prog = C.read_csv_lines(rows[spec["evolution"]])[0][7]
    _require(prog == spec["program"], f"{code} action_skill[{spec['evolution']}] program {prog} ≠ {spec['program']}")
    # 形态切换：c9..c16
    switching = ch[9]
    if spec["switched"] is None:
        _require(switching == "(None)", f"{code} c9={switching}，出现了新的技能切换，须重审")
    else:
        _require(ch[14] == spec["switched"], f"{code} c14={ch[14]}")
        srows = live.nested("master/skill/switched_action_skill.orderedmap")[spec["switched"]]
        sprog = C.read_csv_lines(srows[spec["evolution"]])[0][0]
        _require(sprog == spec["program"], f"{code} 切换后程序 {sprog} ≠ 本体 {spec['program']}（出现真正的第二套技能，须重审）")
    fp = C.table_path(live.S, wf_dsl.dsl_logical(spec["program"]))
    raw = fp.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    _require(digest.startswith(spec["sha256"]),
             f"{code} live DSL 漂移：sha256 {digest[:16]} 不以 {spec['sha256']} 开头 —— 先重读源树再改规则")
    tree = wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]
    return tree, char_element, raw


# ------------------------------------------------------------------------ 可读打印
def render(tree: list) -> str:
    out: list[str] = [f"ROOT {json.dumps(tree[:11], ensure_ascii=False)}"]

    def fmt(v):
        if isinstance(v, list) and v and all(isinstance(t, dict) and "min" in t for t in v):
            return "<" + _fmt(v) + ">"
        return json.dumps(v, ensure_ascii=False)

    def is_expr(v):
        return isinstance(v, list) and v and v[0] in ("Block", "Command", "Event")

    def pp(node, ind):
        pad = "  " * ind
        if node[0] == "Block":
            if not node[1]:
                out.append(pad + "{}")
            for ch in node[1]:
                pp(ch, ind)
            return
        name, params = node[1][0], node[1][1:]
        subs, simple = [], []
        for i, p in enumerate(params):
            if is_expr(p):
                subs.append((i, p))
                simple.append(f"p{i}:<#{len(subs)}>")
            else:
                simple.append(f"p{i}={fmt(p)}")
        out.append(f"{pad}{'EVENT ' if node[0] == 'Event' else ''}{name}(" + ", ".join(simple) + ")")
        for n, (i, p) in enumerate(subs, 1):
            out.append(f"{pad}  #{n} p{i}:")
            pp(p, ind + 2)

    pp(tree[11], 0)
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只推导+校验并与磁盘比对，不写盘")
    ap.add_argument("--print", action="store_true", help="打印原树与回响树")
    args = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print(f"store = {live.S}")
    failed = False
    for code, spec in CHARACTERS.items():
        tree, char_element, raw = load_source(code, spec)
        d = Deriver(code, spec, char_element)
        echo = d.derive(tree)
        checks = all_checks(echo, code, char_element, spec["wait"])
        ok_rt, stored_sha = roundtrip(echo)
        # 正向对照：原树在装备（无属性 owner）上下文里应被 colorless 检查抓到（证明检查器有效）
        control = W.colorless_hit_effect_problems(tree)
        budgets = {flag: (damage_budget(tree, flag), damage_budget(echo, flag)) for flag in (True, False)}
        print(f"\n=== {spec['name']} {spec['cid']} {code}  源 {spec['program']}  sha256 {hashlib.sha256(raw).hexdigest()[:16]}")
        print(f"    回响 program = {ECHO_DIR}$echo_{code}   Wait {spec['wait']} 帧   DSL 元素 {char_element + 1}")
        for e in d.log:
            if e["action"] != "collapse":
                print(f"    [{e['action']:8s}] {e['what']:40s} {e['detail']}  @{e['path']}")
        ncol = sum(1 for e in d.log if e["action"] == "collapse")
        print(f"    [collapse] SLv min≠max 折叠为满级：{ncol} 处")
        for flag, (b0, b1) in budgets.items():
            ratio = (b1["multiplier_hits"] / b0["multiplier_hits"]) if b0["multiplier_hits"] else 0
            print(f"    伤害预算 flag={'on ' if flag else 'off'}: 原 {b0['multiplier_hits']:g}× → 回响 {b1['multiplier_hits']:g}×"
                  f"（{ratio:.3f}）  削韧 {b0['detoughness_hits']:g} → {b1['detoughness_hits']:g}"
                  f"（策略 {DETOUGHNESS_POLICY}；×0.25 应为 {b0['detoughness_hits'] * SCALE:g}）"
                  f"  Fever {b0['fever_hits']:g} → {b1['fever_hits']:g}"
                  f"  比例攻击 原{b0['ratio_terms']} → 回响{b1['ratio_terms']}")
        print(f"    往返 encode_amf3→parse_dsl + encode_tree(deflate -15): {'OK' if ok_rt else 'FAIL'}"
              f"  落盘字节 sha256 {stored_sha}  → {wf_dsl.dsl_logical(ECHO_DIR + '$echo_' + code)}")
        for k, v in checks.items():
            print(f"    {k}: {'0' if not v else v}")
        print(f"    正向对照（原树 colorless_hit_effect_problems）: {len(control)} 条")
        if not ok_rt or any(checks.values()):
            failed = True
        if args.print:
            print("\n--- 原树（live）\n" + render(tree))
            print("\n--- 回响树\n" + render(echo))
        path = OUT_DIR / f"{code}.json"
        text = json.dumps(echo, ensure_ascii=False) + "\n"
        if args.check:
            same = path.exists() and path.read_text("utf8") == text
            print(f"    磁盘比对 {path.name}: {'一致' if same else '不一致/缺失'}")
            failed |= not same
        else:
            OUT_DIR.mkdir(parents=True, exist_ok=True)
            path.write_bytes(text.encode("utf8"))      # 仓库全 LF：Windows 文本模式会写成 CRLF
            print(f"    写出 {path}  ({len(wf_dsl.encode_amf3(echo))} 字节 AMF3)")
    print("\n结果:", "FAIL" if failed else "全部通过")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
