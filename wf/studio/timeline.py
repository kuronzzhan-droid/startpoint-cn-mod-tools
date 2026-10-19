"""L2 编排级 preview: turn one ActionDsl tree into a 60 fps event timeline.

Only the *visual subset* is modelled — like the boundary drawn by Ku1o's studio:
effects, hit areas, character/ball actions, waits and loops are laid out on
frames; hits, target selection and branch conditions are **annotated, never
simulated**:

* every arm of a ``Conditionals*`` node is laid out, each tagged with an arm id;
* ``onHit`` blocks of ``CreateHitArea`` run once at a *sample* hit time;
* ``FindAllSubjects`` / ``FindNearSubjects`` bind one representative subject.

Timing follows the client evaluator: siblings of a Block start on the same
frame; ``Event Wait(n)`` fires its body ``n`` frames later; ``Event
Repeat(interval, count)`` fires every ``interval`` frames (expanded up to
``REPEAT_CAP`` times). Nodes are processed in frame order from a queue so
``HideEffect`` / ``RemoveEvent`` / ``EraseHitArea`` act on what exists then.

Nothing is dropped silently: constructs missing from the signature tables are
listed in ``unknown`` (the client would silently decode them as Trace/Wait),
legal commands without a visual model go to ``unmodeled`` and to the 其它 lane.
Strings naming another DSL program (multiball / target attack / tornado) are
resolved into ``subprograms`` (depth-capped, cycle-safe).
"""
from __future__ import annotations

import heapq
import itertools
import math

import wf_dsl_sig as sig
from wf_character_requirements import resolve_effect_by_element

FPS = 60
MAX_FRAME = 60 * FPS          # nothing is scheduled beyond one minute
REPEAT_CAP = 12               # expanded iterations per Repeat
EVENT_CAP = 4000
SUB_DEPTH = 2
DSL_SUFFIX = ".action.dsl.amf3.deflate"

LANES = [
    {"id": "effect", "label": "特效"}, {"id": "hit", "label": "判定"},
    {"id": "action", "label": "动作"}, {"id": "sound", "label": "声音"},
    {"id": "wait", "label": "等待"}, {"id": "state", "label": "状态"},
    {"id": "other", "label": "其它"},
]
NOT_SIMULATED = ["命中", "目标选择", "分支条件"]
ELEMENTS = ["火", "水", "雷", "风", "光", "暗", "无"]
BUILTIN = {
    -1: {"ref": "field_center", "label": "场地中心（-1）"},
    -2: {"ref": "field_lt", "label": "场地左上角（-2）"},
    -17: {"ref": "self", "label": "自身（-17）"},
    -18: {"ref": "ball", "label": "球（-18）"},
    -33: {"ref": "mate", "label": "协力伙伴（-33）"},
}
SELECTORS = {33: ("ally", "己方全体（含自身）"), 34: ("leader", "队长"), 35: ("ally", "除自身外的己方"),
             82: ("ally", "主小队"), 97: ("ball", "球"), 49: ("enemy", "全部敌人"),
             50: ("enemy", "杂兵"), 51: ("enemy", "boss"), 52: ("enemy", "浮游敌人")}
THROWS_ON_CD = {"ball", "self", "enemy", "ally", "leader", "mate"}
KIND_DEFAULT = {"skill": "技能", "pf": "强化弹射", "ability_skill": "技能", "subprogram": "技能"}
BTA = {1: "技能", 2: "能力", 3: "强化弹射", 4: "直击",
       101: "技能（转换）", 102: "能力（转换）", 104: "直击（转换）",
       131: "强化弹射 Lv1（转换）", 132: "强化弹射 Lv2（转换）", 133: "强化弹射 Lv3（转换）"}
ACTION_COMMANDS = {"StopBall", "MoveBall", "HideCharacter", "ShakeCamera", "SetPowerFilpSuppress",
                   "NotifyPowerflipEnd", "SuppressBallActivity", "StartPiercing", "StopPiercing"}
STATE_COMMANDS = {"CreateCondition", "DeleteCondition", "ExtendCondition", "CreateRatioHeal", "CreateNormalHeal",
                  "AddSkillPoint", "SubtractSkillPoint", "AddFeverPoint", "SubtractFeverPoint", "AddCombo",
                  "ConsumeUniqueCondition", "SuppressSkill", "TargetMate", "Revive", "DecreaseCoffinCount",
                  "StartBuffField", "StopBuffField", "StartModifierField", "StopModifierField",
                  "ChangeFieldAssets", "ChangeFieldAnimation", "ChangeBgm", "FadeOutBgm", "CreateBarrier",
                  "BindConditionAccumulationVariable", "BindCoffinRevivalCountVariable",
                  "BindCoffinRevivalCountVariableOf", "MultiballNumberVariable", "RecoveryHitCountCheck"}
ATTACKS = {"CreateNormalAttack", "CreateRatioAttack", "CreateFixedAttack", "CreateOnlyHitAttack"}
PROGRAM_PARAMS = {"CreateBombMultiball", "CreateSummonsMultiball", "CreateTargetAttack", "CreateTornado"}
LAYER = {"BacksideOfCharacter": 0, "SameAsCharacter": 1, "ForesideOfCharacter": 2,
         "SuperForesideOfCharacter": 3, "NonPixelArt": 3}
LAYER_CN = {"BacksideOfCharacter": "角色后", "SameAsCharacter": "与角色同层", "ForesideOfCharacter": "角色前",
            "SuperForesideOfCharacter": "最前", "NonPixelArt": "非像素层"}
ARMS = {"ConditionalsNumExecutionsOddOrEven": ["奇数次", "偶数次"]}


# -- small value helpers -------------------------------------------------
def slv(value):
    """[{min,max}] / {min,max} / number → (min, max) or None."""
    if isinstance(value, list) and len(value) == 1:
        value = value[0]
    if isinstance(value, dict) and "min" in value:
        return value.get("min"), value.get("max")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value, value
    return None


def fmt(value) -> str:
    pair = slv(value)
    if pair is None:
        return str(value)
    a, b = pair
    show = lambda v: f"{v:g}" if isinstance(v, (int, float)) else str(v)  # noqa: E731
    return show(a) if a == b else f"{show(a)}→{show(b)}"


def first(value, default=0.0) -> float:
    pair = slv(value)
    return float(pair[0]) if pair and isinstance(pair[0], (int, float)) else default


def enum_name(value) -> str | None:
    return value[0] if isinstance(value, list) and value and isinstance(value[0], str) else None


def attribution(bta: int, kind: str) -> dict:
    if bta == 0:
        return {"value": 0, "label": KIND_DEFAULT.get(kind, "技能"), "auto": True,
                "note": "根头部 buffTargetAs=0：按动作来源自动选择乘区"
                        + ("；629 能力技按 AbilitySkill 结算 = 技能伤害" if kind == "ability_skill" else "")}
    label = BTA.get(bta, f"未知值 {bta}")
    note = "客户端伤害分类转换补丁（v28 起）才认得 101–133" if bta > 100 else "只切换通用乘区，不改来源标志"
    return {"value": bta, "label": label, "auto": False, "note": note}


def program_logical(value: str) -> str:
    return value if value.endswith(DSL_SUFFIX) else value + DSL_SUFFIX


class _Env:
    def __init__(self, parent=None, bindings=None, bta=None, area=None):
        self.parent, self.bindings = parent, bindings or {}
        self.bta = parent.bta if bta is None and parent else (bta or 0)
        self.area = area if area is not None else (parent.area if parent else None)

    def lookup(self, sid):
        env = self
        while env is not None:
            if sid in env.bindings:
                return env.bindings[sid]
            env = env.parent
        if sid in BUILTIN:
            return dict(BUILTIN[sid])
        return None

    def child(self, bindings=None, bta=None, area=None):
        return _Env(self, bindings, bta, area)


class TimelineBuilder:
    """Evaluate one tree. ``effects(path)`` returns the effect timeline dict (or None);
    ``programs(logical)`` returns a parsed sub-tree (or None)."""

    def __init__(self, tree, *, kind="skill", path="", element=None, effects=None, programs=None,
                 depth=0, seen=None):
        self.tree, self.kind, self.path, self.element = tree, kind, path, element
        self.effect_info = effects or (lambda p: None)
        self.program_tree = programs or (lambda p: None)
        self.depth, self.seen = depth, set(seen or ()) | {program_logical(path)} if path else set(seen or ())
        self.events: list[dict] = []
        self.unknown: list[dict] = []
        self.unmodeled: dict[str, int] = {}
        self.issues: list[dict] = []
        self.arms: list[dict] = []
        self.subprograms: list[dict] = []
        self.queue: list = []
        self.counter = itertools.count()
        self.removed: dict[str, int] = {}
        self.truncated = False

    # -- infrastructure --------------------------------------------------
    def add(self, lane: str, kind: str, t: int, ctx: dict, **fields) -> dict | None:
        if len(self.events) >= EVENT_CAP:
            self.truncated = True
            return None
        event = {"id": len(self.events), "lane": lane, "kind": kind, "t": t, "dur": fields.pop("dur", 0),
                 "label": fields.pop("label", kind), "node": ctx["node"], "arms": list(ctx["arms"]),
                 "scope": list(ctx["scope"]), "trigger": ctx.get("trigger"), **fields}
        self.events.append(event)
        return event

    def issue(self, level: str, ctx: dict, text: str) -> None:
        self.issues.append({"level": level, "node": ctx["node"], "text": text})

    def schedule(self, t: int, node, env: _Env, ctx: dict, name: str | None = None) -> None:
        if t > MAX_FRAME:
            self.truncated = True
            return
        heapq.heappush(self.queue, (t, next(self.counter), node, env, ctx, name))

    def lookup(self, env: _Env, sid, ctx: dict, role: str) -> dict:
        if not isinstance(sid, int) or isinstance(sid, bool):
            self.issue("问题", ctx, f"{role} 的主体 ID 不是整数：{sid!r}")
            return {"ref": "unknown", "label": f"无效主体 {sid!r}"}
        found = env.lookup(sid)
        if found is None:
            self.issue("问题", ctx, f"{role} 引用主体 {sid}，但它不在当前作用域：客户端会 C16103")
            return {"ref": "unknown", "label": f"未绑定主体 {sid}", "id": sid}
        return {**found, "id": sid}

    def coord(self, value, env, ctx, subject, role) -> dict:
        name = enum_name(value) or "AB"
        result = {"kind": name}
        if name == "GH" and len(value) > 1:
            result["toward"] = self.lookup(env, value[1], ctx, role + " 坐标系 GH")
        if name == "CD" and subject.get("ref") in THROWS_ON_CD:
            if subject.get("ref") == "self":
                # 作者 2026-10-19 确认：赛瑞斯 ability_skill_seris_revert 把 CD 挂在 -17（自身）上，测试服实际没崩。
                # 是否真能执行到/真会抛未经真机证实，只提示待验证，不判问题。
                self.issue("待验证", ctx, f"{role} 坐标系 CD 挂在「{subject['label']}」上：按旧经验可能抛 U_4f5401，"
                           "但赛瑞斯同样写法在测试服未崩，需真机确认")
            else:
                self.issue("问题", ctx, f"{role} 坐标系 CD 挂在「{subject['label']}」上：getDirCD 会抛错（U_4f5401）")
        if name == "EF" and subject.get("ref") not in ("ball", "self"):
            result["note"] = "EF 只在球/角色上跟随速度方向；其它主体返回常量（预览按朝上）"
        return result

    # -- entry ---------------------------------------------------------------
    def build(self) -> dict:
        tree = self.tree
        root_ctx = {"node": "ActionDsl", "arms": [], "scope": [], "trigger": None}
        header = {}
        body = None
        if isinstance(tree, list) and tree and tree[0] == "ActionDsl" and len(tree) >= 12:
            bta = tree[10] if isinstance(tree[10], int) and not isinstance(tree[10], bool) else 0
            header = {"version": tree[1], "flags": tree[3:10], "buffTargetAs": bta}
            body = tree[11]
        elif isinstance(tree, list) and tree and tree[0] == "Block":
            self.issue("问题", root_ctx, "根是裸 Block（缺 ActionDsl 头）：客户端会 F1009")
            header = {"buffTargetAs": 0}
            body = tree
        else:
            self.unknown.append({"node": "根", "name": str(tree)[:60], "reason": "不是 ActionDsl 树"})
        bta = header.get("buffTargetAs", 0)
        env = _Env(bta=bta)
        if body is not None:
            self.schedule(0, body, env, {**root_ctx, "node": "根"})
        while self.queue:
            t, _, node, env, ctx, name = heapq.heappop(self.queue)
            if name is not None and name in self.removed and self.removed[name] <= t:
                self.add("other", "cancelled", t, ctx, label=f"已被 RemoveEvent「{name}」取消")
                continue
            self.eval(node, t, env, ctx)
        duration = self.finish()
        return {
            "program": self.path, "kind": self.kind, "fps": FPS, "duration": duration,
            "header": header, "attribution": attribution(bta, self.kind),
            "lanes": LANES, "events": self.events, "arms": self.arms,
            "unknown": self.unknown,
            "unmodeled": [{"name": k, "label": sig.cn_cmd(k), "count": v} for k, v in sorted(self.unmodeled.items())],
            "issues": self.issues, "subprograms": self.subprograms,
            "notSimulated": NOT_SIMULATED, "truncated": self.truncated,
            "notes": self.notes(),
        }

    def notes(self) -> list[str]:
        notes = ["时间轴按 60 帧/秒；同一 Block 的兄弟节点同一帧开始，Wait n 帧后执行。",
                 "命中、目标选择、分支条件未模拟：两条分支都画出来（标「分支」），命中块只在示意时刻展开一次。"]
        if self.kind == "skill":
            notes.append("技能语音（skill_0..3 随机）与 cut-in 由客户端代码播放，DSL 不控制。")
        if self.kind == "pf":
            notes.append("强化弹射语音由客户端在每次触发时 100% 播放（power_flip_N 随机），DSL 不控制。")
        if self.kind == "ability_skill":
            notes.append("629 能力技不追加技能语音/cut-in；伤害按 AbilitySkill 结算。")
        return notes

    # -- evaluation ----------------------------------------------------------
    def eval(self, node, t: int, env: _Env, ctx: dict) -> None:
        if not isinstance(node, list) or not node:
            if node not in (None, []):
                self.unknown.append({"node": ctx["node"], "name": str(node)[:60], "reason": "不是表达式节点"})
            return
        head = node[0]
        if head == "Block":
            children = node[1] if len(node) > 1 and isinstance(node[1], list) else []
            for index, child in enumerate(children):
                self.eval(child, t, env, {**ctx, "node": f"{ctx['node']}/{index}"})
            return
        if head in ("Command", "Event") and len(node) == 2 and isinstance(node[1], list) and node[1] \
                and isinstance(node[1][0], str):
            name, params = node[1][0], node[1][1:]
            table = sig.COMMANDS if head == "Command" else sig.EVENTS
            label = f"{ctx['node']}:{name}"
            here = {**ctx, "node": label}
            if name not in table:
                fallback = "Trace（只取第 1 参）" if head == "Command" else "Wait"
                self.unknown.append({"node": label, "name": name, "kind": head,
                                     "reason": f"不在 {head} 构造表：客户端会静默解成 {fallback}，整段逻辑丢失"})
                self.add("other", "unknown", t, here, label=f"未知节点 {head} {name}")
                return
            signature = table[name]
            if len(params) != len(signature):
                self.issue("待验证", here, f"{name} 参数 {len(params)} 个，签名 {len(signature)} 个")
                params = list(params) + [None] * max(0, len(signature) - len(params))
            handler = getattr(self, "c_" + name, None)
            if handler is not None:
                handler(params, t, env, here)
            elif name in ATTACKS:
                self.attack(name, params, t, env, here)
            elif name in ACTION_COMMANDS:
                self.action(name, params, t, env, here)
            elif name in STATE_COMMANDS:
                self.state(name, params, t, env, here)
            elif name.startswith(("Conditionals", "IfThisCharacter")):
                self.branch(name, params, signature, t, env, here)
            else:
                self.generic(name, params, signature, t, env, here)
            return
        self.unknown.append({"node": ctx["node"], "name": str(head)[:60], "reason": "节点形状不是 Block/Command/Event"})
        self.add("other", "unknown", t, ctx, label=f"未知节点 {str(head)[:24]}")

    def nested(self, params, signature, t, env, ctx, scope=None, trigger=None):
        for index, kind in enumerate(signature):
            if kind == "ActionDslExpression" and index < len(params):
                inner = {**ctx, "node": f"{ctx['node']}[{index}]",
                         "scope": ctx["scope"] + ([scope] if scope else []),
                         "trigger": trigger or ctx.get("trigger")}
                self.eval(params[index], t, env, inner)

    # -- branches / scopes ---------------------------------------------------
    def branch(self, name, params, signature, t, env, ctx):
        slots = [i for i, kind in enumerate(signature) if kind == "ActionDslExpression"]
        labels = ARMS.get(name)
        if labels is None:
            if len(slots) == 2:
                labels = ["条件成立", "条件不成立"]
            elif name.startswith("ConditionalsNumExecutions"):
                labels = [f"第 {i + 1} 路（按发动次数）" for i in range(len(slots))]
            else:
                labels = [f"分支 {i + 1}" for i in range(len(slots))]
        title = sig.cn_cmd(name)
        detail = sig.brief_command([name, *params])
        self.add("other", "branch", t, ctx, label=f"分支：{title}", detail=detail)
        for slot, arm_label in zip(slots, labels):
            arm = {"id": len(self.arms), "label": f"{title} · {arm_label}", "condition": name, "node": ctx["node"],
                   "empty": params[slot] in (None, ["Block", []])}
            self.arms.append(arm)
            self.eval(params[slot], t, env, {**ctx, "node": f"{ctx['node']}[{slot}]", "arms": ctx["arms"] + [arm["id"]]})

    def c_ConditionalsProbability(self, params, t, env, ctx):
        # Arms are separated by ProbabilityWeight commands inside the single block.
        block = params[0]
        children = block[1] if isinstance(block, list) and block and block[0] == "Block" and len(block) > 1 else []
        self.add("other", "branch", t, ctx, label="分支：概率", detail="按 ProbabilityWeight 分段")
        arm = None
        for index, child in enumerate(children):
            inner = child[1] if isinstance(child, list) and len(child) == 2 and isinstance(child[1], list) else None
            if inner and inner[0] == "ProbabilityWeight":
                arm = {"id": len(self.arms), "label": f"概率 · 权重 {fmt(inner[1]) if len(inner) > 1 else '?'}",
                       "condition": "ConditionalsProbability", "node": ctx["node"], "empty": False}
                self.arms.append(arm)
                continue
            arms = ctx["arms"] + ([arm["id"]] if arm else [])
            self.eval(child, t, env, {**ctx, "node": f"{ctx['node']}/{index}", "arms": arms})

    def c_FindAllSubjects(self, params, t, env, ctx):
        ref, label = SELECTORS.get(params[1], ("unknown", f"选择器 {params[1]}"))
        bound = {"ref": ref, "label": label + "（示意 1 个）", "selector": params[1]}
        self.add("other", "select", t, ctx, label=f"选取：{label}", subject=bound,
                 detail="每个目标各执行一次；目标数量与选择未模拟")
        if isinstance(params[0], int):
            self.eval(params[8], t, env.child({params[0]: bound}), {**ctx, "node": ctx["node"] + "[8]",
                                                                   "scope": ctx["scope"] + [f"每个目标：{label}"]})

    def c_FindNearSubjects(self, params, t, env, ctx):
        origin = self.lookup(env, params[0], ctx, "FindNearSubjects 原点")
        ref, label = SELECTORS.get(params[2], ("unknown", f"选择器 {params[2]}"))
        bound = {"ref": ref, "label": f"离{origin['label']}最近的 {params[1]} 个{label}（示意）",
                 "selector": params[2]}
        self.add("other", "select", t, ctx, label=f"选取最近 {params[1]} 个：{label}", subject=bound,
                 detail="目标选择未模拟；找不到目标时：" + str(enum_name(params[3])))
        if isinstance(params[4], int):
            self.eval(params[5], t, env.child({params[4]: bound}), {**ctx, "node": ctx["node"] + "[5]",
                                                                   "scope": ctx["scope"] + [f"最近 {label}"]})

    # -- events --------------------------------------------------------------
    def c_Wait(self, params, t, env, ctx):
        frames, name = params[0], params[1]
        if not isinstance(frames, int) or frames < 0:
            self.issue("问题", ctx, f"Wait 帧数无效：{frames!r}")
            return
        self.add("wait", "wait", t, ctx, dur=frames, label=f"等待 {frames} 帧",
                 detail=f"事件名 {name}" if name not in ("*", None) else "")
        self.schedule(t + frames, params[2], env, {**ctx, "node": ctx["node"] + "[2]"},
                      name if name not in ("*", None) else None)

    def c_Repeat(self, params, t, env, ctx):
        interval, count, name = params[0], params[1], params[2]
        if not all(isinstance(v, int) and v > 0 for v in (interval, count)):
            self.issue("问题", ctx, f"Repeat 参数无效：{interval!r}, {count!r}")
            return
        shown = min(count, REPEAT_CAP)
        self.add("wait", "repeat", t, ctx, dur=interval * (count - 1) + 1,
                 label=f"循环 每 {interval} 帧 × {count} 次", interval=interval, count=count, expanded=shown,
                 detail=("" if shown == count else f"只展开前 {shown} 次，其余 {count - shown} 次未画出")
                 + "；首次在当帧（frameCount % interval == 0）")
        for k in range(shown):
            self.schedule(t + interval * k, params[3], env,
                          {**ctx, "node": f"{ctx['node']}[3]#{k + 1}", "scope": ctx["scope"] + [f"第 {k + 1}/{count} 次循环"]},
                          name if name not in ("*", None) else None)

    def c_RemoveEvent(self, params, t, env, ctx):
        name = params[0]
        if isinstance(name, str):
            self.removed[name] = min(self.removed.get(name, t), t)
        self.add("wait", "remove", t, ctx, label=f"取消事件「{name}」")

    def c_RemoveEventFromOwner(self, params, t, env, ctx):
        self.c_RemoveEvent(params, t, env, ctx)

    # Event layouts from ListeningEvent: (window, bind, hit body, timeout body) parameter slots.
    LISTEN = {
        "CollisionOfBallAndEnemy": ("球碰到敌人时", 0, 3, 4, None),
        "CollisionOfBallAndSpecificEnemy": ("球碰到指定敌人时", 1, 4, 5, 6),
        "CollisionOfSpecificBallAndSpecificEnemy": ("指定球碰到指定敌人时", 2, 5, 6, 7),
    }

    def c_CollisionOfBallAndEnemy(self, params, t, env, ctx):
        self.collision("CollisionOfBallAndEnemy", params, t, env, ctx)

    def c_CollisionOfBallAndSpecificEnemy(self, params, t, env, ctx):
        self.collision("CollisionOfBallAndSpecificEnemy", params, t, env, ctx)

    def c_CollisionOfSpecificBallAndSpecificEnemy(self, params, t, env, ctx):
        self.collision("CollisionOfSpecificBallAndSpecificEnemy", params, t, env, ctx)

    def collision(self, name, params, t, env, ctx):
        label, window_at, bind_at, body_at, timeout_at = self.LISTEN[name]
        window = params[window_at] if isinstance(params[window_at], int) else 0
        self.add("wait", "listen", t, ctx, dur=window, label=f"监听：{label}（{window} 帧内）",
                 detail="碰撞时刻未模拟：命中分支按监听开始 +1 帧示意展开")
        bind = {params[bind_at]: {"ref": "enemy", "label": "被撞的敌人（示意）"}} if isinstance(params[bind_at], int) else {}
        arms = [("命中", body_at, t + 1, env.child(bind))]
        if timeout_at is not None:
            arms.append(("超时未命中", timeout_at, t + window, env))
        for arm_label, slot, at, arm_env in arms:
            arm = {"id": len(self.arms), "label": f"{label} · {arm_label}", "condition": name, "node": ctx["node"],
                   "empty": params[slot] in (None, ["Block", []])}
            self.arms.append(arm)
            self.schedule(at, params[slot], arm_env, {**ctx, "node": f"{ctx['node']}[{slot}]",
                                                      "arms": ctx["arms"] + [arm["id"]], "trigger": label})

    def c_ActivatedMultiballOfExecutorSelf(self, params, t, env, ctx):
        bind = {k: {"ref": "ball", "label": "多球（示意）"} for k in params[1:3] if isinstance(k, int)}
        self.add("wait", "listen", t, ctx, label="监听：自身多球激活时", detail="触发时刻未模拟，按 +1 帧示意")
        self.schedule(t + 1, params[3], env.child(bind), {**ctx, "node": ctx["node"] + "[3]",
                                                          "trigger": "自身多球激活时"})

    # -- visual commands -----------------------------------------------------
    def resolve_effect(self, value, ctx) -> tuple[str | None, str]:
        name = enum_name(value)
        if name == "SpecifyEffectDirectly" and len(value) > 1 and isinstance(value[1], str):
            return value[1], "直接指定"
        if name == "ResolveByElement" and len(value) > 2:
            code = value[2]
            element = code - 1 if isinstance(code, int) and 1 <= code <= 7 else (
                self.element if code == 255 else None)
            if element is None or not 0 <= element <= 6:
                self.issue("待验证", ctx, f"ResolveByElement 属性码 {code} 无法确定（无角色属性上下文）")
                return None, f"按属性派生（码 {code}）"
            return resolve_effect_by_element(value[1], element), f"按属性派生：{ELEMENTS[element]}"
        self.unknown.append({"node": ctx["node"], "name": str(name), "reason": "未知特效指定方式"})
        return None, "未知"

    def c_ShowEffect(self, params, t, env, ctx):
        name, effect, sid, layer, lifetime, coord, x, y, rot, track_pos, track_dir, scale = params[:12]
        subject = self.lookup(env, sid, ctx, f"ShowEffect「{name}」")
        path, how = self.resolve_effect(effect, ctx)
        info = self.effect_info(path) if path else None
        life_kind = enum_name(lifetime) or "?"
        life, life_label = None, ""
        if life_kind == "SpecifyEffectLifetimeDirectly" and isinstance(lifetime[1], (int, float)):
            life, life_label = int(lifetime[1]), f"{lifetime[1]} 帧"
        elif life_kind == "SpecifyEffectLifetimeSLv":
            life, life_label = int(first(lifetime[1])), f"{fmt(lifetime[1])} 帧（SLv）"
        elif life_kind == "PlayOnlyFirstSequence":
            life_label = "播完第一段"
        elif life_kind == "UntilTargetTerminates":
            life_label = "直到挂载主体结束"
        elif life_kind == "RemainingStateGroup":
            life_label = "直到状态组结束（按程序结束估计）"
        scale_value = first(scale[1]) if enum_name(scale) == "Some" and len(scale) > 1 else None
        default_scale = info.get("defaultScale") if info else None
        event = self.add(
            "effect", "effect", t, ctx, label=str(name), path=path, how=how, subject=subject,
            layer=LAYER.get(enum_name(layer), 2), layerLabel=LAYER_CN.get(enum_name(layer), str(enum_name(layer))),
            lifetime={"kind": life_kind, "label": life_label}, life=life,
            coord=self.coord(coord, env, ctx, subject, f"ShowEffect「{name}」"),
            offset={"x": x or 0, "y": y or 0}, rot=float(rot or 0), tracking={"pos": bool(track_pos), "dir": bool(track_dir)},
            scale=scale_value if scale_value is not None else default_scale,
            scaleSource="DSL" if scale_value is not None else ("parts 默认 s" if default_scale is not None else "未知"),
            asset=bool(info), sequences=(info or {}).get("sequences", []),
        )
        if event is not None and not info:
            event["missing"] = "当前视图没有这个特效资源" if path else "特效路径无法解析"

    def c_HideEffect(self, params, t, env, ctx):
        name = params[0]
        hit = 0
        for event in self.events:
            if event["kind"] == "effect" and event["label"] == name and event["t"] <= t and not event.get("hiddenAt"):
                event["hiddenAt"] = t
                hit += 1
        self.add("effect", "hide", t, ctx, label=f"隐藏特效「{name}」",
                 detail=f"终止 {hit} 个同名特效（有 end 段则跳去播完）" if hit else "此刻没有同名特效")

    def c_HideEffectFromOwner(self, params, t, env, ctx):
        self.c_HideEffect(params, t, env, ctx)

    def c_CreateHitArea(self, params, t, env, ctx):
        p = list(params) + [None] * (26 - len(params))
        subject = self.lookup(env, p[1], ctx, "CreateHitArea")
        shape = self.shape(p[8], ctx)
        life_kind = enum_name(p[12])
        if life_kind == "SpecifyHitAreaLifetimeDirectly" and isinstance(p[12][1], (int, float)):
            life, life_label = int(p[12][1]), f"{p[12][1]} 帧"
        elif life_kind == "SpecifyHitAreaLifetimeSLv":
            life, life_label = int(first(p[12][1])), f"{fmt(p[12][1])} 帧（SLv）"
        else:
            life, life_label = None, "当前状态组剩余帧（按程序结束估计）"
        hits = self.hits(p[13], life, p[14], ctx)
        own_bta = p[23] if isinstance(p[23], int) and not isinstance(p[23], bool) else 0
        bta = own_bta or env.bta
        attr = attribution(bta, self.kind)
        attr["source"] = "判定区 params[23]" if own_bta else "继承根头部"
        formation = self.formation(p[11])
        event = self.add(
            "hit", "hitarea", t, ctx, label=f"判定区 {shape['label']}", name=p[0], subject=subject,
            coord=self.coord(p[2], env, ctx, subject, "CreateHitArea"),
            offset={"x": p[3] or 0, "y": p[4] or 0}, rot=float(p[5] or 0),
            tracking={"pos": bool(p[6]), "dir": bool(p[7])}, shape=shape,
            align={"h": enum_name(p[9]) or "Center", "v": enum_name(p[10]) or "Center"}, formation=formation,
            life=life, lifetime={"kind": life_kind, "label": life_label}, hits=hits, attribution=attr,
            attacks=[], motions=[], dur=life or 0,
        )
        if event is None:
            return
        me = {"ref": f"hitarea:{event['id']}", "label": f"判定区 #{event['id']}"}
        if isinstance(p[18], int):
            self.eval(p[19], t, env.child({p[18]: me}, area=event["id"]),
                      {**ctx, "node": ctx["node"] + "[19]", "scope": ctx["scope"] + ["判定区创建时"]})
        hit_env = env.child({k: v for k, v in ((p[20], me), (p[21], {"ref": "enemy", "label": "被命中的对象（示意）"}))
                             if isinstance(k, int)}, bta=bta, area=event["id"])
        # A collider riding the ball (tracking) hits whenever the ball reaches an enemy: show it
        # mid-life. Anything else overlaps its targets on creation.
        moving = subject.get("ref") in ("ball", "self") and bool(p[6])
        sample = t + (max(1, (life or 2) // 2) if moving else 0)
        event["sampleHit"] = sample
        if p[22] not in (None, ["Block", []]):
            self.schedule(sample, p[22], hit_env,
                          {**ctx, "node": ctx["node"] + "[22]", "scope": ctx["scope"] + ["命中时"],
                           "trigger": "命中时（示意时刻）"})

    def shape(self, value, ctx) -> dict:
        name = enum_name(value)
        if name == "Circle":
            r = first(value[1])
            if r <= 0:
                self.issue("问题", ctx, "圆形判定半径必须 > 0（客户端会抛错）")
            return {"type": "circle", "r": r, "label": f"圆 r{fmt(value[1])}"}
        if name == "Rectangle":
            w, h = first(value[1]), first(value[2])
            if w <= 0 or h <= 0:
                self.issue("问题", ctx, "矩形判定宽高必须 > 0")
            label = f"矩形 {fmt(value[1])}×{fmt(value[2])}"
            if w >= 3600 and h >= 3600:
                label += "（全屏惯用写法）"
            return {"type": "rect", "w": w, "h": h, "label": label}
        if name == "Sector":
            r, angle = first(value[1]), first(value[2])
            if r <= 0 or not 0 < angle < math.pi:
                self.issue("问题", ctx, "扇形要求半径 > 0 且 0 < 圆心角 < π")
            return {"type": "sector", "r": r, "angle": angle,
                    "label": f"扇形 r{fmt(value[1])} 圆心角 {math.degrees(angle):.0f}°"}
        if name in ("Donut", "Arc"):
            size = {1: 9.5, 2: 13.5, 3: 23.5}.get(value[1] if len(value) > 1 else None, 0)
            return {"type": name.lower(), "r": size, "label": f"{'冲击波环' if name == 'Donut' else '冲击波弧'}（官方 0 例）",
                    "approx": True}
        self.unknown.append({"node": ctx["node"], "name": str(name), "reason": "未知判定形状"})
        return {"type": "unknown", "label": f"未知形状 {name}"}

    def hits(self, interval, life, cap, ctx) -> dict:
        name = enum_name(interval)
        result = {"kind": name, "times": []}
        n, step = None, None
        if name in ("CalculatedUsingMaxNumOfHits", "CalculatedUsingMaxNumOfHitsSLv"):
            n = int(interval[1]) if name == "CalculatedUsingMaxNumOfHits" else int(first(interval[1]))
            if n <= 0:
                self.issue("问题", ctx, "CalculatedUsingMaxNumOfHits ≤ 0 会得到负间隔")
            result["expected"] = n
            if n > 1 and life:
                step = life / (n - 0.5)
            result["label"] = f"期望命中 {n} 次" + (f"，间隔 ≥ {step:.1f} 帧" if step else "（只算首次）")
        elif name in ("SpecifyMinHitIntervalDirectly", "SpecifyMinHitIntervalSLv"):
            step = float(interval[1]) if name == "SpecifyMinHitIntervalDirectly" else first(interval[1])
            result["label"] = f"最小间隔 {step:g} 帧"
        if step and step > 0 and life:
            k = 0
            while k * step < life and len(result["times"]) < 60:
                result["times"].append(round(k * step, 1))
                k += 1
        else:
            result["times"] = [0]
        if enum_name(cap) == "Some" and len(cap) > 1:
            result["cap"] = fmt(cap[1])
            result["label"] = result.get("label", "") + f"；每目标上限 {fmt(cap[1])}"
        result["note"] = "期望命中数不是硬上限；实际命中取决于目标与位置（未模拟）"
        return result

    def formation(self, value) -> dict:
        name = enum_name(value) or "Single"
        args = value[1:] if isinstance(value, list) else []
        result = {"type": name, "args": args}
        if name == "NWay" and len(args) >= 2:
            n, theta = int(args[0]), float(args[1])
            if n % 2 == 0:
                angles = [s * (theta / 2 + k * theta) for k in range(n // 2) for s in (1, -1)]
            else:
                angles = [0.0] + [s * (k + 1) * theta for k in range(n // 2) for s in (1, -1)]
            result.update(angles=angles, label=f"{n} 向散射，间隔 {math.degrees(theta):.0f}°")
        elif name in ("Line", "File") and len(args) >= 3:
            n, gap, center = int(args[0]), float(args[1]), bool(args[2])
            if n % 2 == 0:
                offs = [s * (k * gap + gap / 2) for k in range(n // 2) for s in (1, -1)]
            else:
                offs = ([0.0] if center else []) + [s * (k + 1) * gap for k in range((n - 1) // 2) for s in (1, -1)]
            axis = "x" if name == "Line" else "y"
            result.update(offsets=[{axis: o} for o in offs], label=f"{'横排' if name == 'Line' else '竖排'} {n} 个，间距 {gap:g}",
                          approx=name == "File")
        elif name == "Single":
            result["label"] = "单个"
        else:
            result.update(label=f"阵型 {name}{args}（未展开，只画中心一个）", approx=True)
        return result

    def c_MoveHitArea(self, params, t, env, ctx):
        target = self.lookup(env, params[0], ctx, "MoveHitArea")
        angle, speed = float(params[2] or 0), float(params[3] or 0)
        ref = target.get("ref", "")
        moved = None
        if ref.startswith("hitarea:"):
            moved = self.events[int(ref.split(":")[1])]
            moved["motions"].append({"t": t, "angle": angle, "speed": speed, "coord": enum_name(params[1])})
        elif ref.startswith("marker:"):
            moved = self.events[int(ref.split(":")[1])]
            moved.setdefault("motions", []).append({"t": t, "angle": angle, "speed": speed,
                                                    "coord": enum_name(params[1])})
        self.add("hit", "move", t, ctx, label=f"移动{target['label']}", subject=target,
                 detail=f"方向 {math.degrees(angle):.0f}° · 每帧 {speed:g}" + ("" if moved else "（目标不是判定区/参考点，未画移动）")
                 + ("；有缓动参数，预览按匀速" if enum_name(params[4]) == "Some" else ""))

    def c_RotateHitArea(self, params, t, env, ctx):
        target = self.lookup(env, params[0], ctx, "RotateHitArea")
        self.add("hit", "rotate", t, ctx, label=f"旋转{target['label']}", subject=target,
                 detail=f"角速度 {params[1]}（预览不画旋转）")

    def c_EraseHitArea(self, params, t, env, ctx):
        target = self.lookup(env, params[0], ctx, "EraseHitArea")
        ref = target.get("ref", "")
        if ref.startswith("hitarea:"):
            area = self.events[int(ref.split(":")[1])]
            if area["life"] is None or area["t"] + area["life"] > t:
                area["life"] = max(0, t - area["t"])
                area["dur"] = area["life"]
                area["erasedAt"] = t
        self.add("hit", "erase", t, ctx, label=f"删除{target['label']}", subject=target)

    def c_CreateReferencePoint(self, params, t, env, ctx):
        origin = self.lookup(env, params[0], ctx, "CreateReferencePoint 原点")
        life = params[8] if isinstance(params[8], int) else None
        event = self.add("other", "marker", t, ctx, label="参考点", subject=origin,
                         coord=self.coord(params[1], env, ctx, origin, "CreateReferencePoint"),
                         offset={"x": params[2] or 0, "y": params[3] or 0}, rot=float(params[4] or 0),
                         tracking={"pos": bool(params[5]), "dir": bool(params[6])},
                         formation=self.formation(params[7]), life=life, dur=life or 0,
                         detail=f"寿命 {life} 帧" if life is not None else "")
        if event is not None and isinstance(params[9], int):
            me = {"ref": f"marker:{event['id']}", "label": f"参考点 #{event['id']}"}
            self.eval(params[10], t, env.child({params[9]: me}), {**ctx, "node": ctx["node"] + "[10]"})

    def c_CreateReferencePointAtSpecifiedPosition(self, params, t, env, ctx):
        sx = self.lookup(env, params[0], ctx, "参考点 X 取自")
        sy = self.lookup(env, params[1], ctx, "参考点 Y 取自")
        life = params[2] if isinstance(params[2], int) else None
        event = self.add("other", "marker", t, ctx, label="参考点（X/Y 分别取自两个主体）", subject=sx, subjectY=sy,
                         offset={"x": 0, "y": 0}, rot=0.0, coord={"kind": "AB"}, tracking={"pos": False, "dir": False},
                         life=life, dur=life or 0, detail=f"X 取自{sx['label']}，Y 取自{sy['label']}")
        if event is not None and isinstance(params[3], int):
            me = {"ref": f"marker:{event['id']}", "label": f"参考点 #{event['id']}"}
            self.eval(params[4], t, env.child({params[3]: me}), {**ctx, "node": ctx["node"] + "[4]"})

    # -- damage / actions / state ------------------------------------------
    def attack(self, name, params, t, env, ctx):
        target = self.lookup(env, params[0], ctx, sig.cn_cmd(name))
        attr = attribution(env.bta, self.kind)
        fields = {"subject": target, "attribution": attr, "area": env.area}
        if name == "CreateNormalAttack":
            code = params[1]
            element = "继承施法者" if code == 255 else (ELEMENTS[code - 1] if isinstance(code, int) and 1 <= code <= 7 else f"码 {code}")
            fields.update(multiplier=fmt(params[5]), element=element,
                          extra={"固定伤害": params[4], "削韧": fmt(params[12]), "Fever": fmt(params[13])})
            label = f"攻击 ×{fmt(params[5])}"
        elif name == "CreateRatioAttack":
            label = f"比例攻击 {fmt(params[2])}"
        else:
            label = sig.brief_command([name, *params]) or sig.cn_cmd(name)
        event = self.add("hit", "attack", t, ctx, label=label, detail=f"伤害归属：{attr['label']}", **fields)
        if event is not None and env.area is not None:
            self.events[env.area]["attacks"].append(event["id"])

    def action(self, name, params, t, env, ctx):
        label = sig.brief_command([name, *params]) or sig.cn_cmd(name)
        dur, subject = 0, None
        if name == "StopBall":
            subject = self.lookup(env, params[0], ctx, "StopBall")
            dur = params[1] if isinstance(params[1], int) else 0
            label = f"停球 {dur} 帧"
        elif name == "HideCharacter":
            subject = self.lookup(env, params[0], ctx, "HideCharacter")
            dur = params[1] if isinstance(params[1], int) else 0
            label = f"隐藏角色 {dur} 帧"
        elif name == "MoveBall":
            subject = self.lookup(env, params[0], ctx, "MoveBall")
            dur = params[3] if isinstance(params[3], int) else 0
            label = f"移动球 {dur} 帧（坐标系 {enum_name(params[1])}，速度 {params[4]}）"
        elif name == "ShakeCamera":
            label = f"震屏 {({1: '小', 2: '中', 3: '大'}).get(params[0], params[0])}"
        elif name == "SetPowerFilpSuppress":
            dur = params[0] if isinstance(params[0], int) else 0
            label = f"抑制强化弹射 {dur} 帧"
        elif name == "NotifyPowerflipEnd":
            label = "通知强化弹射结束"
        self.add("action", name, t, ctx, label=label, dur=dur, subject=subject,
                 detail="球的移动未画出" if name == "MoveBall" else "")

    def state(self, name, params, t, env, ctx):
        subject = None
        if name in ("CreateCondition", "DeleteCondition", "ExtendCondition", "CreateRatioHeal", "AddSkillPoint",
                    "SubtractSkillPoint") and isinstance(params[0], int):
            subject = self.lookup(env, params[0], ctx, sig.cn_cmd(name))
        self.add("state", name, t, ctx, label=sig.brief_command([name, *params]) or sig.cn_cmd(name),
                 subject=subject)

    def generic(self, name, params, signature, t, env, ctx):
        self.unmodeled[name] = self.unmodeled.get(name, 0) + 1
        event = self.add("other", "generic", t, ctx, label=sig.brief_command([name, *params]) or sig.cn_cmd(name),
                         detail="这个命令没有画面模型，只在时间轴上标出")
        if name in PROGRAM_PARAMS and event is not None:
            self.linked(params, t, ctx, event)
        trigger = "触发时（未模拟）" if name.startswith("Set") and name.endswith("Handler") else None
        self.nested(params, signature, t, env, ctx, scope=sig.cn_cmd(name), trigger=trigger)

    def linked(self, params, t, ctx, event):
        for value in params:
            if not (isinstance(value, str) and value.startswith("battle/action/")):
                continue
            logical = program_logical(value)
            entry = {"path": value, "spawnedBy": event["id"], "t": t, "node": ctx["node"],
                     "note": "子程序在多球/弹体命中等时刻执行，触发时刻未模拟"}
            if logical in self.seen:
                entry["error"] = "循环引用，未展开"
            elif self.depth >= SUB_DEPTH:
                entry["error"] = f"嵌套超过 {SUB_DEPTH} 层，未展开"
            else:
                tree = self.program_tree(logical)
                if tree is None:
                    entry["error"] = "当前视图里没有这个子程序"
                else:
                    child = TimelineBuilder(tree, kind="subprogram", path=value, element=self.element,
                                            effects=self.effect_info, programs=self.program_tree,
                                            depth=self.depth + 1, seen=self.seen)
                    entry["timeline"] = child.build()
            event["subprogram"] = len(self.subprograms)
            self.subprograms.append(entry)

    # -- post pass -----------------------------------------------------------
    def finish(self) -> int:
        def end_of(event):
            return event["t"] + max(event.get("dur") or 0, event.get("life") or 0)
        horizon = max([end_of(e) for e in self.events] + [1])
        horizon = min(horizon, MAX_FRAME)
        by_ref = {}
        for event in self.events:
            if event["kind"] in ("hitarea", "marker"):
                by_ref[("hitarea:" if event["kind"] == "hitarea" else "marker:") + str(event["id"])] = event
        for event in self.events:
            if event["kind"] == "hitarea" and event["life"] is None:
                event["life"] = event["dur"] = max(1, horizon - event["t"])
                event["lifeEstimated"] = True
        for event in self.events:
            if event["kind"] != "effect":
                continue
            self.effect_runs(event, by_ref, horizon)
        return max([e["t"] + (e.get("dur") or 0) for e in self.events] + [horizon, 1])

    def effect_runs(self, event, by_ref, horizon):
        sequences = [s for s in event.get("sequences") or [] if isinstance(s.get("begin"), int)
                     and isinstance(s.get("end"), int)]
        kind = event["lifetime"]["kind"]
        life = event.get("life")
        if kind == "PlayOnlyFirstSequence":
            life = sequences[0]["end"] - sequences[0]["begin"] + 1 if sequences else 1
        elif kind == "UntilTargetTerminates":
            host = by_ref.get(event["subject"].get("ref", ""))
            if host is not None and host.get("life") is not None:
                life = max(1, host["t"] + host["life"] - event["t"])
                event["lifetime"]["label"] += f"（宿主寿命 → {life} 帧）"
            else:
                life = max(1, horizon - event["t"])
                event["lifetime"]["label"] += "（宿主无固定寿命，按程序结束估计）"
                event["lifeEstimated"] = True
        elif life is None:
            life = max(1, horizon - event["t"])
            event["lifeEstimated"] = True
        if event.get("hiddenAt") is not None:
            life = min(life, max(0, event["hiddenAt"] - event["t"]))
        end = next((s for s in sequences if s.get("name") == "end"), None)
        terminate_jump = kind != "PlayOnlyFirstSequence" and end is not None and end is not sequences[0]
        frames = self.playhead(sequences, life, kind == "PlayOnlyFirstSequence")
        end_frames = list(range(end["begin"], end["end"] + 1)) if terminate_jump else []
        event["life"] = life
        event["endLength"] = len(end_frames)
        event["dur"] = life + len(end_frames)
        event["endNote"] = ("终止后跳到 end 段播完" if terminate_jump else
                            "无 end 段：终止当帧直接删除" if kind != "PlayOnlyFirstSequence" else "播完第一段即结束")
        event["runs"] = self.compress(frames + end_frames)
        info = self.effect_info(event["path"]) if event.get("path") else None
        for sound in (info or {}).get("sounds", []) or []:
            begin = sound.get("begin")
            hits = [i for i, f in enumerate(frames + end_frames) if f == begin][:4]
            for local in hits:
                self.events.append({
                    "id": len(self.events), "lane": "sound", "kind": "sound", "t": event["t"] + local, "dur": 0,
                    "label": str(sound.get("path", "")).rsplit("/", 1)[-1], "path": sound.get("path"),
                    "node": event["node"], "arms": event["arms"], "scope": event["scope"],
                    "trigger": event.get("trigger"), "effect": event["id"],
                    "detail": f"特效「{event['label']}」时间轴第 {begin} 帧的音效"})

    @staticmethod
    def playhead(sequences, life, only_first) -> list[int]:
        if not sequences:
            return []
        frames, index, current = [], 0, sequences[0]["begin"]
        for _ in range(min(life, MAX_FRAME)):
            frames.append(current)
            seq = sequences[index]
            if current < seq["end"]:
                current += 1
            elif only_first:
                break
            elif seq.get("kind") == "loop":
                current = seq["begin"]
            elif seq.get("kind") == "pass" and index + 1 < len(sequences) and sequences[index + 1].get("name") != "end":
                index += 1
                current = sequences[index]["begin"]
        return frames

    @staticmethod
    def compress(frames: list[int]) -> list[list[int]]:
        """[[local start, first timeline frame, length, step]] with step 1 (advance) or 0 (hold)."""
        runs: list[list[int]] = []
        for local, frame in enumerate(frames):
            if runs:
                start, base, length, step = runs[-1]
                if length == 1 and frame in (base, base + 1):
                    runs[-1] = [start, base, 2, frame - base]
                    continue
                if length > 1 and frame == base + length * step:
                    runs[-1][2] += 1
                    continue
            runs.append([local, frame, 1, 1])
        return runs


def build_timeline(tree, **options) -> dict:
    return TimelineBuilder(tree, **options).build()
