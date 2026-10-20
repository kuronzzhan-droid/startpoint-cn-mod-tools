"""Fever 道具补丁 B1-B4 静态 + 离线执行验证。

usage: python verify_feveritems.py BASE.swf PATCHED.swf [--json OUT.json]

1. 重放：BASE→PATCHED 逐字节一致；PATCHED 再重放 = already_present（幂等）
2. 拒绝：目标体改 1 字节的副本被拒（四个目标体逐个测）
3. 差分：只有 boot_ffc6 变；主 ABC 只有 4 个目标体不同；常量池/各表零变化
4. 栈/作用域模拟在 header 内；B 体里没有 Math.random / fromCharCode / 新字符串
5. 离线执行（avm_fi 跑真实字节码，对象模拟）：
   B1 无标记（无箭头 / 队长无状态 / 槽位外 uid / 层数 0）→ 副作用日志与原版逐条相同
      有标记 → FEVER 箭头不 activate；每块箭头坐标上建一个道具（种类 = 独立重算的 Xorshift 结果）；
      第二次 Fever 不重抽；坏候选表 → 只停箭头不建道具；槽位按 uid 升序取第一个；同坐标已有道具不重复建
   B2 无标记 → 与原版相同；有标记 → 只跳过「FEVER 且 Deactivated」的箭头
   B3 无行 → 与原版相同；有行 → 原 addSoundEffect 后按槽位/键顺序预载 key_fever@ITEM_LV
   （v32h：B4 撤掉；所有主表读取改 getMasterTableMaybe，表未加载 = 候选表为空、不抛异常）
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, r"D:/WF/perf-v30-20261015/tools")
from common import ABC, MAIN, abc_tags, asm, bodies, freeze, sha  # noqa: E402
from perf2_core import Refused, apply_patches, check_body, parse_swf, rebuild_swf  # noqa: E402
import feveritems_patches as F  # noqa: E402
import avm_fi as vm  # noqa: E402
from avm_mini import UNDEF, PlainObject  # noqa: E402

RESULTS = {}
SEP_BASE = -1234567891 & 0xFFFFFFFF   # 模拟的 separativeBaseSeed（本 Battle id 的 sha 前 4 字节）
SEP_BASE = SEP_BASE - (1 << 32) if SEP_BASE >= 1 << 31 else SEP_BASE
POOL4 = ["hp_recovery_small", "skill_charge_middle", "accumulation_attack_power_up_25_500", "condition_piercing"]
DII_KEYS = set(POOL4) | {"hp_recovery_middle", "condition_speedup"}


def ok(key, cond, detail=None):
    RESULTS[key] = {"ok": bool(cond), "detail": detail}
    print(("PASS " if cond else "FAIL ") + key + ("" if detail is None else f"  {str(detail)[:300]}"))
    if not cond:
        raise SystemExit(f"verification failed: {key}")


def main_abc(swf):
    return ABC([t for t in abc_tags(swf) if t[0] == MAIN][0][4])


def body_of(abc, label):
    return abc.bodies[bodies.resolve(abc, label)]


def i32(v):
    v = int(v) & 0xFFFFFFFF
    return v - (1 << 32) if v >= 1 << 31 else v


class Xorshift:
    """pinball.common.random.Xorshift 的逐行移植（int32 语义）。"""

    def __init__(self, seed):
        self.r = i32(seed) or -1831433054
        self.u()

    def u(self):
        r = self.r
        r = i32(r ^ i32(r << 13))
        r = i32(r ^ ((r & 0xFFFFFFFF) >> 17))
        r = i32(r ^ i32(r << 15))
        self.r = r
        return r & 0xFFFFFFFF

    def randomFloat(self):
        return self.u() / 4294967296


def expected_key(pool, uid, x, y):
    seed = i32(uid + (i32(i32(int(x)) << F.SEED_SHIFT) ^ i32(int(y))))
    rng = Xorshift(i32(SEP_BASE + seed))
    i = int(rng.randomFloat() * len(pool))
    return pool[i if i < len(pool) else 0]


# ------------------------------------------------------------------ object model
class Obj:
    def __init__(self, label, **kw):
        self._label = label
        self.__dict__.update(kw)

    def __repr__(self):
        return f"<{self._label}>"


class DashStub(Obj):
    pass


class DIIStub(Obj):
    pass


class HList(Obj):
    """haxe.ds.List：h 头指针 + add 尾插。"""

    def __init__(self, items, log):
        super().__init__("yakumonoes", h=None)
        self._q = None
        self._log = log
        for it in items:
            self._append(it)
        self.add = self._add

    def _append(self, item):
        node = Obj("node", item=item, next=None)
        if self.h is None:
            self.h = node
        else:
            self._q.next = node
        self._q = node

    def _add(self, item):
        self._log.append(("list.add", item._label))
        self._append(item)

    def items(self):
        out, n = [], self.h
        while n is not None:
            out.append(n.item)
            n = n.next
        return out


TOK = {
    "pinball.scene.battle.battle.zone.yakumono.dashPanel::DashPanelBase": "DPB",
    "pinball.scene.battle.battle.zone.yakumono.directInstantItem::DirectInstantItemImpl": "DII",
    "pinball.master.generated::UniqueConditionTable": "UCT",
    "pinball.master.generated::DirectInstantItemTable": "DIT",
    "pinball.scene.battle.battle.random::RandomSeedFactory": "RSF",
    "pinball.common.data.quest.battle::BattleQuestLogic": "BQL",
}


class Env:
    def __init__(self, abc):
        self.abc, self.log, self.reads = abc, [], []
        self.lexmap = dict(TOK)
        self.lexmap.update({
            "pinball.scene.battle.battle.sound::BattleSoundMode": Obj("BSM", Me="Me"),
            "pinball.common.data.character.condition::ConditionTargetKind": Obj("CTK", Unique=lambda u: ("Unique", u)),
        })

    def trace_pc(self, pc):
        pass

    def lex(self, name):
        if name not in self.lexmap:
            raise AssertionError("lex " + name)
        return self.lexmap[name]

    def findprop(self, name, this):
        if name in self.lexmap:
            return self.lexmap[name]
        return this

    def globalscope(self):
        return "global"

    def coerce(self, op, name, value):
        if op == "astype" and value is not None:
            raise AssertionError("unexpected astype " + name)
        return value

    def astypelate(self, value, cls):
        if cls == "DPB":
            return value if isinstance(value, DashStub) else None
        if cls == "DII":
            return value if isinstance(value, DIIStub) else None
        raise AssertionError(f"astypelate {cls}")

    def mnl_get(self, obj, key):
        if isinstance(obj, list):
            return obj[int(key)] if 0 <= int(key) < len(obj) else UNDEF
        if isinstance(obj, dict):
            return obj.get(key, UNDEF)
        raise AssertionError(f"mnl {obj!r}[{key!r}]")

    def mnl_set(self, obj, key, value):
        if isinstance(obj, dict):
            obj[key] = value
            return
        raise AssertionError(f"mnl set {obj!r}[{key!r}]")

    def get(self, obj, name):
        short = name.split("::")[-1]
        if isinstance(obj, (list, str)) and short == "length":
            return len(obj)
        if isinstance(obj, PlainObject):
            return obj.get_(short)
        if isinstance(obj, Obj) and short in obj.__dict__:
            return obj.__dict__[short]
        raise AssertionError(f"get {short} on {obj!r}")

    def set(self, obj, name, value):
        setattr(obj, name.split("::")[-1], value)

    def call(self, obj, name, args):
        short = name.split("::")[-1]
        if isinstance(obj, str) and short == "split":
            return obj.split(args[0])
        if isinstance(obj, list) and short == "push":
            obj.append(args[0])
            return len(obj)
        fn = obj.__dict__.get(short) if isinstance(obj, Obj) else None
        if fn is None or not callable(fn):
            raise AssertionError(f"call {short} on {obj!r}")
        return fn(*args)

    def construct(self, name, args):
        if name.endswith("::DirectInstantItemImpl"):
            pos, src, rpa = args
            x, y = pos.get_("x"), pos.get_("y")
            it = DIIStub(f"new@{x:g},{y:g}", x=x, y=y, src=src, rpa=rpa)
            it.activate = lambda: self.log.append(("activate", it._label))
            it.deactivate = lambda: self.log.append(("deactivate", it._label))
            self.log.append(("construct", x, y, src, rpa))
            return it
        if name.endswith("::IntMap"):
            return Obj("IntMap", h={})
        if name.endswith("::IntMapKeysIterator"):
            keys = sorted(args[0].keys())
            st = {"i": 0}

            def has_next():
                return st["i"] < len(keys)

            def nxt():
                st["i"] += 1
                return keys[st["i"] - 1]
            return Obj("it", hasNext=has_next, next=nxt)
        raise AssertionError("construct " + name)


def master(rows):
    def _get(k):
        if k not in rows:   # 真机 MasterBinaryMap.getIndex 缺键抛 ClientError 8601（v32h 真机崩在这里）
            raise RuntimeError(f"8601 key not found {k}")
        return rows[k]
    return Obj("map", get=_get, exists=lambda k: k in rows)


def asset_for(env, sids, loaded=("UCT", "DIT")):
    """sids: {uid: string_id}。direct_instant_item 表固定 DII_KEYS。
    只提供 getMasterTableMaybe（未加载返回 null）；注入代码若调用会抛 8013 的 getMasterTable，这里直接报错。"""
    uct = master({u: Obj(f"ucv{u}", string_id=s) for u, s in sids.items()})
    dit = master({k: Obj("dii", kind=0) for k in DII_KEYS})

    def gmtm(t):
        env.reads.append(("getMasterTable", t))
        return Obj(t, get_data=lambda: {"UCT": uct, "DIT": dit}[t]) if t in loaded else None
    return Obj("asset", getMasterTableMaybe=gmtm)


# ------------------------------------------------------------------ B1 / B2 世界
def world(abc, layout, counts, sids, extra_official=(), loaded=("UCT", "DIT")):
    """layout: [(kind, x, y, availIndex, stateIndex)]；kind: dash / item / other。"""
    env = Env(abc)
    log = env.log
    leader = Obj("leader", getConditionAccumulationCount=lambda k: (env.reads.append(("cac", k)), counts.get(k[1], 0))[1])
    sm = Obj("sm", getLeader=lambda: (env.reads.append(("getLeader",)), leader)[1])
    asset = asset_for(env, sids, loaded)
    items = []
    for n, (kind, x, y, av, stt) in enumerate(list(layout) + list(extra_official)):
        label = f"{kind}{n}@{x:g},{y:g}"
        cls = {"dash": DashStub, "item": DIIStub, "other": Obj}[kind]
        o = cls(label, x=float(x), y=float(y), values=Obj("v", availableTime=Obj("at", index=av)),
                state=Obj("st", index=stt), squadManager=sm, asset=asset, rotationPanelAnimation=f"RPA{n}")
        o.activate = (lambda lab: lambda: log.append(("activate", lab)))(label)
        o.deactivate = (lambda lab: lambda: log.append(("deactivate", lab)))(label)
        items.append(o)
    yl = HList(items, log)
    seeds = []

    def create_sep(seed):
        seeds.append(seed)
        return Obj("rng", randomFloat=Xorshift(i32(SEP_BASE + seed)).randomFloat)
    rsf = Obj("rsf", createSeparativeRandomNumberGenerator=create_sep)
    quest = Obj("quest", resolveDirectInstantItem=lambda k, lv: ("SRC", k, lv))
    gear = Obj("gear", absorb=lambda c: {"RSF": rsf, "BQL": quest}[c],
               addChild=lambda it: log.append(("gear.addChild", it._label)))
    view = Obj("view", playSoundEffect=lambda mode, p: log.append(("SE", mode, p)))
    this = Obj("ymgr", yakumonoes=yl, viewOrder=view, gear=gear)
    return env, this, yl, seeds


def run_m(abc, body, env, this):
    env.log.clear()
    vm.run(abc, body, env, this, [])
    return list(env.log)


LAYOUT = [("dash", 540, 600, 1, 1), ("other", 100, 100, 0, 0), ("dash", 300, 900, 0, 0), ("dash", 780, 900, 1, 1),
          ("item", 200, 1200, 1, 1), ("dash", 900, 1400, 2, 0), ("dash", 160.5, 333.25, 1, 1)]
NOFEVER = [("dash", 300, 900, 0, 0), ("other", 1, 2, 0, 0), ("item", 5, 5, 1, 1)]
SID4 = "fever:items:" + "|".join(POOL4)


def verify_b1(a0, a1):
    b0, b1 = body_of(a0, "YakumonoManagerImpl/activate"), body_of(a1, "YakumonoManagerImpl/activate")
    base = F.MARKER_UID_BASE
    cases = {
        "no fever arrows, marker present": (NOFEVER, {base: 1}, {base: SID4}),
        "arrows, leader has nothing": (LAYOUT, {}, {base: SID4}),
        "arrows, uid below range": (LAYOUT, {base - 1: 2}, {base - 1: SID4}),
        "arrows, uid above range": (LAYOUT, {base + F.MARKER_SLOTS: 2}, {base + F.MARKER_SLOTS: SID4}),
        "arrows, marker count 0": (LAYOUT, {base: 0}, {base: SID4}),
        "empty list": ([], {base: 1}, {base: SID4}),
    }
    for name, (lay, cnt, sids) in cases.items():
        e0, t0, _y0, _ = world(a0, lay, cnt, sids)
        e1, t1, _y1, s1 = world(a1, lay, cnt, sids)
        l0, l1 = run_m(a0, b0, e0, t0), run_m(a1, b1, e1, t1)
        l0b, l1b = run_m(a0, b0, e0, t0), run_m(a1, b1, e1, t1)
        assert l0 == l1 and l0b == l1b and not s1, (name, l0, l1)
        assert not [r for r in e1.reads if r[0] == "getMasterTable"], name   # 无标记不读表
    ok("B1 marker absent: side-effect log identical to original (6 scenarios x 2 Fevers), no table reads, no RNG",
       True, list(cases))

    # 有标记
    e1, t1, y1, seeds = world(a1, LAYOUT, {base: 2}, {base: SID4 + ":seris"})
    first = run_m(a1, b1, e1, t1)
    fever_dash = [o for o in y1.items() if isinstance(o, DashStub) and o.values.availableTime.index == 1]
    exp = [("SE", "Me", "sound_effect/battle_common/se_fever_time_yakumono_shine")]
    news = []
    for p in fever_dash:
        k = expected_key(POOL4, base, p.x, p.y)
        lab = f"new@{p.x:g},{p.y:g}"
        exp += [("construct", p.x, p.y, ("SRC", k + "_fever", F.ITEM_LV), p.rotationPanelAnimation),
                ("list.add", lab), ("gear.addChild", lab)]
        news.append((lab, k))
    for o in y1.items():
        if not (isinstance(o, DashStub) and o.values.availableTime.index == 1):
            exp.append(("activate", o._label))
    ok("B1 marker: arrows skipped, one item per FEVER arrow at its coordinates, kinds = independent Xorshift replay, "
       "new items activated by the original loop", first == exp, news)
    kinds = sorted({k for _, k in news})
    second = run_m(a1, b1, e1, t1)
    exp2 = [exp[0]] + [("activate", o._label) for o in y1.items()
                       if not (isinstance(o, DashStub) and o.values.availableTime.index == 1)]
    ok("B1 marker, 2nd Fever in same zone: no re-draw, arrows still skipped, items re-activated", second == exp2)
    ok("B1 RNG = createSeparativeRandomNumberGenerator(uid + ((int(x)<<14) ^ int(y))) once per new item",
       seeds == [i32(base + (i32(i32(int(p.x)) << 14) ^ int(p.y))) for p in fever_dash], seeds)
    # 分布：大量坐标抽签，4 种都会出现
    cnt = {}
    for x in range(0, 1080, 37):
        for y in range(200, 1600, 53):
            k = expected_key(POOL4, base, x, y)
            cnt[k] = cnt.get(k, 0) + 1
    ok("B1 draw spreads over all 4 candidates (offline replay over 1140 positions)", len(cnt) == 4, cnt)

    # 槽位：uid 升序取第一个；候选表来自该槽位行
    e1, t1, y1, seeds = world(a1, LAYOUT, {base + 4: 1, base + 7: 1},
                              {base + 4: "fever:items:hp_recovery_middle|condition_speedup",
                               base + 7: SID4})
    lg = run_m(a1, b1, e1, t1)
    got = [c[3][1] for c in lg if c[0] == "construct"]
    exp_k = [expected_key(["hp_recovery_middle", "condition_speedup"], base + 4, p.x, p.y) + "_fever"
             for p in y1.items() if isinstance(p, DashStub) and p.values.availableTime.index == 1 and
             not p._label.startswith("new")]
    ok("B1 slot: lowest marked uid wins and its own pool is used", got == exp_k, got)

    # 坏候选表：箭头仍停，不建道具
    for name, sids in {"row missing": {}, "wrong tag": {base: "wfx:items:" + "|".join(POOL4)},
                       "too few segments": {base: "fever:items"}, "unknown keys": {base: "fever:items:nope|x_y"},
                       "empty pool": {base: "fever:items:"}}.items():
        e1, t1, y1, seeds = world(a1, LAYOUT, {base: 1}, sids)
        lg = run_m(a1, b1, e1, t1)
        assert not [c for c in lg if c[0] in ("construct", "list.add", "gear.addChild")] and not seeds, name
        assert [c for c in lg if c[0] == "activate"] == [("activate", o._label) for o in y1.items()
                                                         if not (isinstance(o, DashStub) and o.values.availableTime.index == 1)], name
    ok("B1 marker with unusable pool (missing row / wrong tag / too few segments / unknown keys / empty): "
       "arrows stay off, no items, no RNG", True)
    for ld in ((), ("UCT",), ("DIT",)):
        e1, t1, y1, seeds = world(a1, LAYOUT, {base: 1}, {base: SID4}, loaded=ld)
        lg = run_m(a1, b1, e1, t1)
        assert not [c for c in lg if c[0] in ("construct", "list.add", "gear.addChild")] and not seeds, ld
    ok("B1 master table not loaded (getMasterTableMaybe -> null): no throw, no items, arrows off", True)
    e1, t1, y1, _ = world(a1, LAYOUT, {base: 1}, {base: "fever:items:nope|condition_speedup||hp_recovery_middle:lbl"})
    lg = run_m(a1, b1, e1, t1)
    got = [c[3][1] for c in lg if c[0] == "construct"]
    ok("B1 pool filter: unknown/empty keys dropped, order kept",
       got == [expected_key(["condition_speedup", "hp_recovery_middle"], base, p.x, p.y) + "_fever"
               for p in y1.items() if isinstance(p, DashStub) and p.values.availableTime.index == 1 and not p._label.startswith("new")], got)
    # 同坐标已有官方 DirectInstantItemImpl → 该箭头不建
    e1, t1, y1, _ = world(a1, LAYOUT, {base: 1}, {base: SID4}, extra_official=[("item", 780, 900, 1, 1)])
    lg = run_m(a1, b1, e1, t1)
    pos = [(c[1], c[2]) for c in lg if c[0] == "construct"]
    ok("B1 arrow already covered by an item at the same coordinates: not duplicated",
       (780.0, 900.0) not in pos and len(pos) == 2, pos)


def verify_b2(a0, a1):
    b0, b1 = body_of(a0, "YakumonoManagerImpl/deactivate"), body_of(a1, "YakumonoManagerImpl/deactivate")
    base = F.MARKER_UID_BASE
    lay = [("dash", 540, 600, 1, 1), ("dash", 780, 900, 1, 0), ("dash", 160, 300, 1, 2), ("dash", 300, 900, 0, 0),
           ("item", 200, 1200, 1, 0), ("other", 1, 1, 0, 0), ("dash", 900, 1400, 2, 1)]
    for name, cnt in {"no marker": {}, "uid out of range": {base + F.MARKER_SLOTS: 1}, "count 0": {base: 0}}.items():
        e0, t0, _, _ = world(a0, lay, cnt, {base: SID4})
        e1, t1, _, _ = world(a1, lay, cnt, {base: SID4})
        assert run_m(a0, b0, e0, t0) == run_m(a1, b1, e1, t1), name
    e0, t0, _, _ = world(a0, NOFEVER, {base: 1}, {base: SID4})
    e1, t1, _, _ = world(a1, NOFEVER, {base: 1}, {base: SID4})
    assert run_m(a0, b0, e0, t0) == run_m(a1, b1, e1, t1)
    ok("B2 marker absent (or no FEVER arrows): log identical to original", True)
    e1, t1, y1, _ = world(a1, lay, {base: 1}, {})
    lg = run_m(a1, b1, e1, t1)
    exp = [("deactivate", o._label) for o in y1.items()
           if not (isinstance(o, DashStub) and o.values.availableTime.index == 1 and o.state.index == 1)]
    ok("B2 marker: only FEVER arrows still Deactivated (never opened) are skipped; opened/cooldown arrows, "
       "items, others deactivate as original (pool not needed)", lg == exp, lg)


# ------------------------------------------------------------------ B3
def verify_b3(a0, a1):
    b0, b1 = body_of(a0, "BattleQuestBaseImpl/resolvePathCollectionForDashPanel"), \
        body_of(a1, "BattleQuestBaseImpl/resolvePathCollectionForDashPanel")
    base = F.MARKER_UID_BASE

    def run(abc, body, sids, loaded=("UCT", "DIT")):
        env = Env(abc)
        log = env.log
        builder = Obj("builder", addSoundEffect=lambda p: log.append(("addSoundEffect", p)))

        def rdi(k, lv):
            log.append(("resolveDirectInstantItem", k, lv))
            return Obj("src", resolvePathCollection=lambda b: log.append(("resolvePathCollection", k, b._label)))
        this = Obj("quest", logicAssets=asset_for(env, sids, loaded), resolveDirectInstantItem=rdi)
        vm.run(abc, body, env, this, [builder])
        return log
    for sids in ({}, {base - 1: SID4}, {base: "x:y:z"}, {base: "fever:items:nope"}):
        assert run(a0, b0, sids) == run(a1, b1, sids), sids
    for ld in ((), ("UCT",), ("DIT",)):
        assert run(a0, b0, {base: SID4}, ld) == run(a1, b1, {base: SID4}, ld), ld
    ok("B3 no usable rows / master table not loaded: identical to original, no throw", True)
    sids = {base: SID4, base + 8: "fever:items:condition_speedup|nope", base + 9: "fever:items:hp_recovery_middle"}
    lg = run(a1, b1, sids)
    exp = [("addSoundEffect", "sound_effect/yakumono/se_dash_panel")]
    for k in POOL4 + ["condition_speedup"]:
        exp += [("resolveDirectInstantItem", k + "_fever", F.ITEM_LV), ("resolvePathCollection", k + "_fever", "builder")]
    ok("B3 rows: every valid key of every slot preloaded (uid order, out-of-range slot ignored)", lg == exp, lg)


# ------------------------------------------------------------------ main
def tamper(base, label):
    """目标体末尾多 1 字节（不可达的 returnvoid）：sha 既不是原体也不是补丁体 → 必须整包拒绝。"""
    abc_t = main_abc(base)
    bi = bodies.resolve(abc_t, label)
    abc_t.bodies[bi][5] = bytes(abc_t.bodies[bi][5]) + b"G"
    data, tags = parse_swf(base)
    return rebuild_swf(base, data, tags, {MAIN: abc_t})


def main():
    args = sys.argv[1:]
    out_json = None
    if "--json" in args:
        i = args.index("--json"); out_json = Path(args[i + 1]); del args[i:i + 2]
    base_p, patched_p = Path(args[0]), Path(args[1])
    base, patched = base_p.read_bytes(), patched_p.read_bytes()
    out, report = apply_patches(base, F.PATCHES)
    ok("replay reproduces PATCHED byte-for-byte", out == patched, sha(out))
    again, rep2 = apply_patches(patched, F.PATCHES)
    ok("idempotent (re-apply on PATCHED)", again == patched and all(p["status"] == "already_present"
                                                                    for p in rep2["patches"]))
    for p in F.PATCHES:
        try:
            apply_patches(tamper(base, p["label"]), F.PATCHES)
            ok(f"refuse tampered {p['id']} target body", False)
        except Refused as e:
            ok(f"refuse tampered {p['id']} target body", True, str(e)[:120])
    t0, t1 = abc_tags(base), abc_tags(patched)
    ok("DoABC2 tag list unchanged", [t[0] for t in t0] == [t[0] for t in t1])
    changed = [t0[i][0].decode() for i in range(len(t0)) if t0[i][4] != t1[i][4]]
    ok("only boot_ffc6 changed", changed == ["boot_ffc6"], changed)
    a0, a1 = main_abc(base), main_abc(patched)
    targets = {bodies.resolve(a0, p["label"]) for p in F.PATCHES}
    diff = [i for i in range(len(a0.bodies)) if freeze(a0.bodies[i]) != freeze(a1.bodies[i])]
    ok("main ABC: only the 3 target bodies differ", set(diff) == targets and len(a0.bodies) == len(a1.bodies),
       f"{len(a0.bodies) - len(diff)} of {len(a0.bodies)} bodies byte-identical; changed={sorted(diff)}")
    for field in ("strings", "multinames", "namespaces", "ns_sets", "methods", "metadata", "instances", "classes",
                  "scripts", "ints", "uints", "doubles"):
        assert freeze(getattr(a0, field)) == freeze(getattr(a1, field)), field
    ok("main ABC pools/tables identical (zero append)", True)
    ok("SWF header/version kept", base[:4] == patched[:4])
    sims, statics = {}, {}
    for p in F.PATCHES:
        b = body_of(a1, p["label"])
        sims[p["id"]] = check_body(a1, b)
        assert sha(b[5]) == p["after"]
        code = asm.decode(b[5])
        mns = {a1.mn_name(c.args[0]) for c in code if c.args and c.name in
               ("callproperty", "callpropvoid", "getlex", "findpropstrict", "constructprop")}
        strs = sorted({a1.s(c.args[0]) for c in code if c.name == "pushstring"})
        assert not any(n.split("::")[-1] in ("random", "fromCharCode", "getLazySoundPlayer") for n in mns), mns
        # 原体 + 补丁新增的字符串只允许 SID/KEY/后缀/坐标键
        s0 = {a0.s(c.args[0]) for c in asm.decode(body_of(a0, p["label"])[5]) if c.name == "pushstring"}
        statics[p["id"]] = sorted(set(strs) - s0)
        assert set(strs) - s0 <= {":", "|", "fever", "items", "_", "x", "y"}, strs
        # 回跳必须落在 avm_label 上（VerifyError #1021 纪律）
        for i, c in enumerate(code):
            if c.target is not None and c.target <= i:
                assert code[c.target].name == "avm_label", (p["id"], i, c.target)
    ok("stack/scope simulation within headers", True, sims)
    gmt = "pinball.asset.logic:ILogicAssetContainer::getMasterTable"
    for p in F.PATCHES:
        cnt = lambda abc: sum(1 for c in asm.decode(body_of(abc, p["label"])[5])  # noqa: E731
                              if c.args and c.name in ("callproperty", "callpropvoid")
                              and abc.mn_name(c.args[0]).split("::")[-1] == "getMasterTable")
        assert cnt(a1) == cnt(a0) == 0, (p["id"], cnt(a0), cnt(a1))
    ok("static (v32h): injected code never calls the throwing getMasterTable (8013); master reads only via "
       "getMasterTableMaybe + null check", True)
    th = "TerrainHandler/readHandler"
    ok("static (v32h): leading-load TerrainHandler/readHandler byte-identical to base (v32g B4 dropped)",
       freeze(body_of(a0, th)) == freeze(body_of(a1, th)) and
       sha(body_of(a1, th)[5]) == "72347789b25544029e8c89b4fd0fd8c0f5bc24b893d18db77062eee548911ef7")
    # 注入代码只在战斗期（B1/B2：Fever 开关）或战斗预载期（B3：BattleQuestBaseImpl.resolvePathCollection
    # ← BattleAssetPathCollectionBuilder.leadingLogicLoadedHandler）执行
    ok("static: patched methods = battle-time / battle-asset-collection only",
       sorted(p["label"] for p in F.PATCHES) == ["BattleQuestBaseImpl/resolvePathCollectionForDashPanel",
                                                  "YakumonoManagerImpl/activate", "YakumonoManagerImpl/deactivate"])
    ok("static: no Math.random/fromCharCode; only pooled strings ':' '|' 'fever' 'items' '_' 'x' 'y' added; "
       "every backward branch lands on avm_label", True, statics)
    verify_b1(a0, a1)
    verify_b2(a0, a1)
    verify_b3(a0, a1)
    summary = {"base_swf_sha256": sha(base), "patched_swf_sha256": sha(patched),
               "bodies_total": len(a0.bodies), "bodies_changed": sorted(diff),
               "constants": {"MARKER_UID_BASE": F.MARKER_UID_BASE, "MARKER_SLOTS": F.MARKER_SLOTS, "ITEM_LV": F.ITEM_LV,
                             "SID_FORMAT": "fever:items:<key>|<key>...[:label]"},
               "checks": RESULTS}
    if out_json:
        out_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf8")
    print("ALL PASS", len(RESULTS), "checks")


if __name__ == "__main__":
    main()
