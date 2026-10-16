"""PF Lv4 补丁静态 + 离线执行验证。

usage: python verify_pflv4.py BASE.swf PATCHED.swf [--unrelated OTHER.swf ...] [--json OUT.json]

1. 重放：BASE→PATCHED 与给定 PATCHED 逐字节一致；PATCHED 再重放 = already_present、输出不变（幂等）
2. 拒绝：每个 --unrelated SWF 必须被拒（目标体 sha 不匹配）；另造一份「目标体被改 1 字节」的副本也必须被拒
3. 差分：只有 boot_ffc6 一个 DoABC2 变化；主 ABC 除 3 个目标体外所有方法体逐字节相同（计数）；常量池/表不变
4. 栈/作用域模拟：3 个体在 header 之内（框架 check_body 同口径）
5. 字段读者：prevPowerFlipChargeLv 只在 BattleFlipperImpl/* 与 BattleFlipperView/draw 出现；
   kyubiPowerFlipInitialCombo 写点仍只有 BallImpl/resolveCollisionForPrimaryOrSummons
6. 离线执行（avm_ext，跑真实字节码，对象模拟）：
   P1 全组合：非 Lv4 条件下与原版选中的 PowerFlipLogic 完全相同；Lv4 条件下换成 override(4)
   P2 多帧序列：无 forLevels=4 行时与原版逐帧日志完全相同；有行时 SE 只播一次、闪电按周期、prev=4
   P3：prev!=4 时与原版日志完全相同；进/出 Lv4 只在切换帧写颜色
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, r"D:/WF/perf-v30-20261015/tools")
from common import ABC, MAIN, abc_tags, asm, bodies, freeze, sha  # noqa: E402
from perf2_core import Refused, apply_patches, check_body  # noqa: E402
from pflv4_patches import PATCHES, LV4_COLOR, SE_PATH, FX_PATH, FX_EVERY, QUERY_EVERY  # noqa: E402
import avm_ext as vm  # noqa: E402
from avm_mini import UNDEF  # noqa: E402

MASK = 0x5A5A1234
RESULTS = {}


def ok(key, cond, detail=None):
    RESULTS[key] = {"ok": bool(cond), "detail": detail}
    print(("PASS " if cond else "FAIL ") + key + ("" if detail is None else f"  {detail}"))
    if not cond:
        raise SystemExit(f"verification failed: {key}")


def main_abc(swf):
    return ABC([t for t in abc_tags(swf) if t[0] == MAIN][0][4])


# ------------------------------------------------------------------ object model
class Obj:
    def __init__(self, label, **kw):
        self._label = label
        self.__dict__.update(kw)

    def __repr__(self):
        return f"<{self._label}>"


class Option(Obj):
    def __init__(self, value=None):
        some = value is not None
        super().__init__("Some" if some else "None", index=0 if some else 1, params=[value] if some else [])


class BallImplStub(Obj):
    pass


class FlipperImplStub(Obj):
    pass


class Env:
    def __init__(self, abc, lex=None):
        self.abc, self.log, self.lexmap = abc, [], dict(lex or {})

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
        if op == "astype" and name.endswith("::BallImpl"):
            return value if isinstance(value, BallImplStub) else None
        if op == "astype" and name.endswith("::BattleFlipperImpl"):
            return value if isinstance(value, FlipperImplStub) else None
        return value

    def mnl_get(self, obj, key):
        if isinstance(obj, list):
            return obj[key] if isinstance(key, int) and 0 <= key < len(obj) else UNDEF
        if isinstance(obj, Obj) and isinstance(key, str) and hasattr(obj, key):
            return getattr(obj, key)
        raise AssertionError(f"mnl {obj!r}[{key!r}]")

    def get(self, obj, name):
        short = name.split("::")[-1]
        if isinstance(obj, Obj) and short in obj.__dict__:
            return obj.__dict__[short]
        raise AssertionError(f"get {short} on {obj!r}")

    def set(self, obj, name, value):
        short = name.split("::")[-1]
        if getattr(obj, "_logset", False):
            self.log.append(("set", obj._label, short, repr(value) if isinstance(value, Obj) else value))
        setattr(obj, short, value)

    def call(self, obj, name, args):
        short = name.split("::")[-1]
        fn = obj.__dict__.get(short) if isinstance(obj, Obj) else None
        if fn is None or not callable(fn):
            raise AssertionError(f"call {short} on {obj!r}")
        return fn(*args)

    def construct(self, name, args):
        if name.endswith("::PowerFlipLogic"):
            return ("PowerFlipLogic", *args)
        raise AssertionError("construct " + name)


def body_of(abc, label):
    return abc.bodies[bodies.resolve(abc, label)]


# ------------------------------------------------------------------ P1
def p1_select(abc, body, leader, lv, ball, overrides):
    env = Env(abc)
    calls = []

    def gpo(level):
        calls.append(level)
        return overrides.get(level)

    total = Obj("total", getPowerFlipOverrides=gpo)
    this = Obj("member", isLeader=lambda: leader, battle=Obj("battle", abilityTotalizer=total), ball=ball,
               logicAssets="LA")
    env.lexmap["pinball.common.data.skill.powerFlip::PowerFlipLogic"] = Obj("PFLclass")
    code = asm.decode(body[5])
    stop = next(i for i in range(20, len(code) - 1)
                if code[i].name == "getlocal_1" and code[i + 1].name == "getproperty"
                and abc.mn_name(code[i + 1].args[0]) == "id")
    param1 = ("orig", "fire")
    pfl = Obj("pfl", id="orig", element="fire")
    try:
        vm.run(abc, body, env, this, [pfl, lv, Option(None)], stop_at=stop)
    except vm.Stop as s:
        sel = s.loc[1]
        return (sel if not isinstance(sel, Obj) else "orig"), calls, s.stack
    raise AssertionError("did not reach stop")


def verify_p1(abc0, abc1):
    b0, b1 = body_of(abc0, "MemberImpl/startPowerFlip"), body_of(abc1, "MemberImpl/startPowerFlip")
    balls = {"none": None, "other": Obj("otherBall"), "c99": BallImplStub("b", kyubiPowerFlipInitialCombo=99),
             "c100": BallImplStub("b", kyubiPowerFlipInitialCombo=100),
             "c250": BallImplStub("b", kyubiPowerFlipInitialCombo=250)}
    ovs = {"none": {}, "lv3": {3: "ov3"}, "lv4": {4: "ov4"}, "lv34": {3: "ov3", 4: "ov4"},
           "lv123": {1: "ov123", 2: "ov123", 3: "ov123"}, "lv4only_low": {4: "ov4", 1: "ov1"}}
    n = same = swapped = 0
    for leader in (True, False):
        for lv in (1, 2, 3):
            for bk, ball in balls.items():
                for ok_, ov in ovs.items():
                    s0, c0, st0 = p1_select(abc0, b0, leader, lv, ball, ov)
                    s1, c1, st1 = p1_select(abc1, b1, leader, lv, ball, ov)
                    assert not st0 and not st1
                    lv4 = leader and lv == 3 and isinstance(ball, BallImplStub) and \
                        ball.kyubiPowerFlipInitialCombo >= 100 and 4 in ov
                    n += 1
                    if lv4:
                        assert s1 == ("PowerFlipLogic", "ov4", "fire", "LA"), (leader, lv, bk, ok_, s1)
                        assert c1 == [4], c1
                        swapped += 1
                    else:
                        assert s1 == s0, (leader, lv, bk, ok_, s0, s1)
                        # 额外查询只在 lv3+队长+快照≥100 时发生，且无副作用
                        extra = leader and lv == 3 and isinstance(ball, BallImplStub) and \
                            ball.kyubiPowerFlipInitialCombo >= 100
                        assert c1 == ([4] + c0 if extra else c0), (c0, c1)
                        same += 1
    ok("P1 offline execution", True, f"{n} cases: {same} identical to original, {swapped} swapped to override(4)")


# ------------------------------------------------------------------ P2
def flipper_world(abc, lv_seq, combo_seq, override4, start_frame=0):
    env = Env(abc)
    log = env.log

    def ph(name):
        return Obj(name, advanceFrame=lambda: None,
                   gotoAndPlay=lambda seq: log.append(("gotoAndPlay", name, seq)))

    state = {"i": 0, "gpo": 0}
    cc = Obj("cc", getPowerFlipChargeLv=lambda: lv_seq[state["i"]],
             getCombo=lambda: MASK ^ combo_seq[state["i"]])

    def gpo(level):
        state["gpo"] += 1
        log.append(("getPowerFlipOverrides", level))
        return "ov4" if (override4 and level == 4) else None

    player = Obj("lazy", playSoundEffectWithRepeat=lambda p, r, v: log.append(("lazySE", p, r, v)))
    view = Obj("viewOrder", playSoundEffect=lambda mode, p: log.append(("SE", mode, p)),
               getLazySoundPlayer=lambda mode: Option(player))
    em = Obj("em", show=lambda k: log.append(("show", k)))
    battle = Obj("battle", abilityTotalizer=Obj("total", getPowerFlipOverrides=gpo), effectManager=em)
    fl = Obj("fl", flipper=Obj("body", x=200.0, y=1500.0))
    fr = Obj("fr", flipper=Obj("body", x=880.0, y=1500.0))
    this = FlipperImplStub(
        "flipperImpl", _logset=True, frameCount=start_frame, blinkState=False, prevPowerFlipChargeLv=0,
        playheadFixedAppearanceAnimation=ph("fixed"), playheadChargeAnimation=ph("charge"),
        playheadTwinkleAnimation=ph("twinkle"), playheadSparkAnimation=ph("spark"),
        playheadGuidePointAnimation=ph("guide"), playheadAdditionalAppearanceAnimation=Option(None),
        comboCalculator=cc, viewOrder=view, battle=battle, flipperLeft=fl, flipperRight=fr,
        processor=Obj("proc", flipFrame=1, state=0), guidePointState=Obj("gps", index=0, params=[]),
        playSoundEffect=lambda p: log.append(("SEflip", p)))
    env.lexmap.update({
        "pinball.common.mask::MaskGeneral": Obj("MaskGeneral", maskBit=MASK),
        "pinball.scene.battle.battle.sound::BattleSoundMode": Obj("BSM", Me="Me"),
        "pinball.scene.battle.battle.effect::EffectKind": Obj("EK", Simple=lambda k: ("Simple", k)),
        "pinball.scene.battle.battle.effect::SimpleEffectKind": Obj("SEK", HitEffect=lambda *a: ("HitEffect", *a)),
        "pinball.scene.battle.battle.effect::SimpleEffectPosition": Obj("SEP", FixedPosition=lambda x, y: ("Fixed", x, y)),
        "String": Obj("String", fromCharCode=lambda *c: "".join(chr(int(x)) for x in c)),
        "pinball.scene.battle.battle.flipper::BattleFlipperGuidePointState": Obj("GPS", Init="Init"),
    })
    return env, this, state


def run_frames(abc, body, lv_seq, combo_seq, override4, start_frame=0):
    env, this, state = flipper_world(abc, lv_seq, combo_seq, override4, start_frame)
    frames = []
    for i in range(len(lv_seq)):
        state["i"] = i
        env.log.clear()
        vm.run(abc, body, env, this, [])
        frames.append({"log": [e for e in env.log if not (e[0] == "set" and e[2] in ("frameCount", "blinkState",
                                                                                    "guidePointState", "prevPowerFlipChargeLv"))],
                       "prev": this.prevPowerFlipChargeLv, "frame": this.frameCount})
    return frames, state


def scenario(n_pre=12, n_ready=65, n_drop=6, n_post=8):
    """lv 0→1→2→3，连击爬到 ≥100 保持 n_ready 帧，然后 (a) override 丢失前不拍板 (b) 拍板回 0。"""
    lv, combo = [], []
    for i in range(n_pre):
        lv.append(min(3, i // 3)); combo.append(10 + i * 4)
    for i in range(n_ready):
        lv.append(3); combo.append(100 + i)
    for i in range(n_drop):
        lv.append(3); combo.append(99)       # 不可能自然发生，用来测「4→3 不打回 one」
    for i in range(n_post):
        lv.append(0 if i < 3 else 1); combo.append(0 if i < 3 else 9)
    return lv, combo


def verify_p2(abc0, abc1):
    b0, b1 = body_of(abc0, "BattleFlipperImpl/update"), body_of(abc1, "BattleFlipperImpl/update")
    lv, combo = scenario()
    # (1) 没有 forLevels=4 行：逐帧与原版一致（日志、prev）。查询次数受节流
    f0, _ = run_frames(abc0, b0, lv, combo, override4=False)
    f1, st1 = run_frames(abc1, b1, lv, combo, override4=False)
    strip = lambda fr: [[e for e in x["log"] if e[0] != "getPowerFlipOverrides"] for x in fr]  # noqa: E731
    ok("P2 no-Lv4-row: per-frame log identical to original", strip(f0) == strip(f1),
       f"{len(lv)} frames, queries={st1['gpo']} (only lv3&combo>=100 frames with frameCount%{QUERY_EVERY}==0)")
    ok("P2 no-Lv4-row: prevPowerFlipChargeLv identical", [x["prev"] for x in f0] == [x["prev"] for x in f1])
    expect_q = sum(1 for i in range(len(lv)) if lv[i] == 3 and combo[i] >= 100 and (i + 1) % QUERY_EVERY == 0)
    ok("P2 query throttle", st1["gpo"] == expect_q, f"{st1['gpo']} == {expect_q}")
    # (2) 有 forLevels=4 行
    g0, _ = run_frames(abc0, b0, lv, combo, override4=True)
    g1, _ = run_frames(abc1, b1, lv, combo, override4=True)
    ready = [x["prev"] == 4 for x in g1]
    first = ready.index(True)
    lazy = [(i, e) for i, x in enumerate(g1) for e in x["log"] if e[0] == "lazySE"]
    se0 = [i for i, x in enumerate(g0) for e in x["log"] if e == ("SE", "Me", SE_PATH)]
    se1 = [i for i, x in enumerate(g1) for e in x["log"] if e == ("SE", "Me", SE_PATH)]
    added = list(se1)
    for i in se0:
        added.remove(i)
    shows = [(i, e) for i, x in enumerate(g1) for e in x["log"] if e[0] == "show"]
    ok("P2 Lv4: enters ready on first query frame with combo>=100",
       g1[first]["frame"] % QUERY_EVERY == 0 and lv[first] == 3 and combo[first] >= 100, f"frame index {first}")
    ok("P2 Lv4: exactly one extra preloaded SE (same playSoundEffect call as original lv3) on entering ready, "
       "no lazy-load path", added == [first] and not lazy, {"original_lv3_SE_frames": se0, "patched": se1})
    exp_show = [i for i in range(len(lv)) if ready[i] and g1[i]["frame"] % FX_EVERY == 0]
    ok("P2 Lv4: lightning pairs every FX_EVERY frames while ready",
       [i for i, _ in shows][::2] == exp_show and len(shows) == 2 * len(exp_show)
       and all(e[1] == ("Simple", ("HitEffect", ("Fixed", px, 1480.0), False, FX_PATH, False, None))
               for (_, e), px in zip(shows, [320.0, 760.0] * len(exp_show))), f"{len(shows)} shows at {exp_show}")
    # 进入就绪之前与原版一致
    ok("P2 Lv4: frames before ready identical to original", [x["log"] for x in g0[:first]] ==
       [[e for e in x["log"] if e[0] != "getPowerFlipOverrides"] for x in g1[:first]])
    # 4→3（override 丢失/连击跌破）：不 gotoAndPlay one
    drop = [i for i in range(1, len(lv)) if g1[i - 1]["prev"] == 4 and g1[i]["prev"] == 3]
    ok("P2 Lv4→3 without flip: no charge/spark reset",
       drop and all(not any(e[0] == "gotoAndPlay" and e[1] in ("charge", "spark") for e in g1[i]["log"]) for i in drop), drop)
    # 拍板回 0：与原版同帧行为（charge/spark one）
    zero = next(i for i in range(len(lv)) if lv[i] == 0 and i > first)
    ok("P2 flip after Lv4: lv0 frame resets like original",
       [e for e in g1[zero]["log"] if e[0] == "gotoAndPlay"] == [e for e in g0[zero]["log"] if e[0] == "gotoAndPlay"])
    # 其余 Lv4 帧：非新增日志项与原版一致
    extra = {"lazySE", "show", "getPowerFlipOverrides"}
    def g1_minus_added(i):
        out = [e for e in g1[i]["log"] if e[0] not in extra and e[0] != "set"]
        if i == first:
            out.remove(("SE", "Me", SE_PATH))
        return out
    diff = [i for i in range(len(lv)) if [e for e in g0[i]["log"] if not (e[0] == "set")] != g1_minus_added(i)]
    ok("P2 Lv4: apart from SE/lightning/query, every frame identical to original", not diff, diff)


# ------------------------------------------------------------------ P3
def view_world(abc, prev, activated=True, combo_fixed=False, rate=1.0, lv=3):
    env = Env(abc)
    log = env.log

    def anim(name):
        return Obj(name, _logset=True, visible=True, x=0.0, y=0.0, rotation=0.0,
                   gotoAndStop=lambda f: None, set_color=lambda c: log.append(("set_color", name, c)),
                   red=lambda b: log.append(("red", name, b)))

    def clip(name):
        return Obj(name, _logset=True, visible=True, currentFrame=0, color=0xFFFFFF)

    flip = FlipperImplStub(
        "peek", prevPowerFlipChargeLv=prev,
        getCurrentFrameFixedAppearanceAnimation=lambda: 1, getCurrentFrameTwinkleAnimation=lambda: 1,
        getCurrentFrameGuidePointAnimation=lambda: 1, getCurrentFrameAdditionalAppearanceAnimation=lambda: 1,
        getCurrentFrameChargeAnimation=lambda: 1, getCurrentFrameSparkAnimation=lambda: 1,
        calcGuide=lambda: Obj("guide", guideLine=None, guidePoint=None),
        getPowerFlipChargeRate=lambda: rate, getRotationLvL=lambda: 1, getRotationLvR=lambda: 2,
        hasActivated=lambda: activated, hasComboFixed=lambda: combo_fixed,
        getPowerFlipChargeLv=lambda: lv, getBlinkState=lambda: 0)
    this = Obj("view", fixedAppearanceAnimationLeft=anim("faL"), fixedAppearanceAnimationRight=anim("faR"),
               twinkleAnimationLeft=anim("twL"), twinkleAnimationRight=anim("twR"),
               guideLeft=anim("guideL"), guidePoint=anim("guideP"),
               additionalAnimationLeft=Option(None), additionalAnimationRight=Option(None),
               flipper=flip, mask=Obj("mask", _logset=True, scaleX=1.0),
               flipperImageWidth=294, maskWidth=1000.0, positionL=Obj("pl", x=200.0, y=1500.0),
               positionR=Obj("pr", x=880.0, y=1500.0), flipperChargeIndicatorOffsetX=30,
               chargeAnimationLeft=anim("chL"), chargeAnimationRight=anim("chR"),
               sparkAnimationLeft=anim("spL"), sparkAnimationRight=anim("spR"),
               backgroundL=clip("bgL"), backgroundR=clip("bgR"), foregroundL=clip("fgL"), foregroundR=clip("fgR"),
               fixedBackground=Obj("fixedBg", _logset=True, mask=None))
    env.lexmap.update({
        "pinball.scene.battle.battle::BattleConstants": Obj(
            "BC", FLIPPER_ROTATION_LV0=0, FLIPPER_ROTATION_LV1=-36, FLIPPER_ROTATION_LV2=-72,
            FLIPPER_ROTATION_LV3=-108, FLIPPER_CHARGE_INDICATOR_OFFSET_Y=0),
        "pinball.scene.battle.battle.flipper::BattleFlipperView": Obj(
            "BFV", getCurrentFrame=lambda r, l, b, fg: r * 10 + l * 2 + b + (1 if fg else 0)),
    })
    return env, this


def run_draw(abc, body, env, this):
    env.log.clear()
    vm.run(abc, body, env, this, [])
    return list(env.log)


def verify_p3(abc0, abc1):
    b0, b1 = body_of(abc0, "BattleFlipperView/draw"), body_of(abc1, "BattleFlipperView/draw")
    n = 0
    for prev in (0, 1, 2, 3):
        for act in (True, False):
            for cf in (False, True):
                for rate, lv in ((0.0, 0), (0.5, 1), (1.0, 3)):
                    e0, t0 = view_world(abc0, prev, act, cf, rate, lv)
                    e1, t1 = view_world(abc1, prev, act, cf, rate, lv)
                    assert run_draw(abc0, b0, e0, t0) == run_draw(abc1, b1, e1, t1), (prev, act, cf, rate)
                    n += 1
    ok("P3 non-Lv4: draw log identical to original", True, f"{n} cases")
    # 进入 Lv4：一次性写色；第二帧不再写色但 spark 仍可见
    e1, t1 = view_world(abc1, 4)
    first = run_draw(abc1, b1, e1, t1)
    color_sets = [x for x in first if x[0] == "set" and x[2] == "color"]
    ok("P3 enter Lv4: 4 clips tinted + 2 spark set_color",
       sorted(x[1] for x in color_sets) == ["bgL", "bgR", "fgL", "fgR"] and all(x[3] == LV4_COLOR for x in color_sets)
       and [x for x in first if x[0] == "set_color"] == [("set_color", "spL", LV4_COLOR), ("set_color", "spR", LV4_COLOR)])
    ok("P3 Lv4: spark forced visible", t1.sparkAnimationLeft.visible is True and t1.sparkAnimationRight.visible is True)
    second = run_draw(abc1, b1, e1, t1)
    ok("P3 Lv4 steady: no colour writes", not [x for x in second if (x[0] == "set" and x[2] == "color")
                                               or x[0] == "set_color"])
    t1.flipper.prevPowerFlipChargeLv = 3
    third = run_draw(abc1, b1, e1, t1)
    restore = [x for x in third if (x[0] == "set" and x[2] == "color") or x[0] == "set_color"]
    ok("P3 leave Lv4: restored to white once", len(restore) == 6 and all(x[-1] == 0xFFFFFF for x in restore)
       and t1.sparkAnimationLeft.visible is False)
    fourth = run_draw(abc1, b1, e1, t1)
    e0, t0 = view_world(abc0, 3)
    ok("P3 after leave: identical to original", fourth == run_draw(abc0, b0, e0, t0))
    e1, t1 = view_world(abc1, 4, combo_fixed=True)
    run_draw(abc1, b1, e1, t1)
    ok("P3 Lv4 + comboFixed: tint but no forced spark", t1.sparkAnimationLeft.visible is False
       and t1.backgroundL.color == LV4_COLOR)


# ------------------------------------------------------------------ static checks
def field_users(abc, name):
    ids = {i for i in range(1, len(abc.multinames)) if abc.mn_name(i).split("::")[-1] == name}
    labels = bodies.label_map(abc)
    out = {}
    for bi, b in enumerate(abc.bodies):
        for ins in asm.decode(b[5]):
            if ins.args and ins.name in ("getproperty", "setproperty", "initproperty", "findproperty",
                                         "findpropstrict", "getlex", "callproperty", "callpropvoid") \
                    and ins.args[0] in ids:
                out.setdefault(labels.get(bi, f"<anon body {bi}>"), set()).add(ins.name)
    return {k: sorted(v) for k, v in sorted(out.items())}


def main():
    args = sys.argv[1:]
    unrelated, out_json = [], None
    while "--unrelated" in args:
        i = args.index("--unrelated"); unrelated.append(Path(args[i + 1])); del args[i:i + 2]
    if "--json" in args:
        i = args.index("--json"); out_json = Path(args[i + 1]); del args[i:i + 2]
    base_p, patched_p = Path(args[0]), Path(args[1])
    base, patched = base_p.read_bytes(), patched_p.read_bytes()
    out, report = apply_patches(base, PATCHES)
    ok("replay reproduces PATCHED byte-for-byte", out == patched, sha(out))
    again, rep2 = apply_patches(patched, PATCHES)
    ok("idempotent (re-apply on PATCHED)", again == patched and all(p["status"] == "already_present"
                                                                    for p in rep2["patches"]))
    for u in unrelated:
        try:
            apply_patches(u.read_bytes(), PATCHES)
            ok(f"refuse unrelated {u.name}", False)
        except Refused as e:
            ok(f"refuse unrelated {u.name}", True, str(e)[:140])
    # 目标体被改 1 字节的副本
    abc_t = main_abc(base)
    bi = bodies.resolve(abc_t, "BattleFlipperView/draw")
    code = bytearray(abc_t.bodies[bi][5]); code[-2] ^= 0x01  # 改末尾 initproperty 的操作数
    abc_t.bodies[bi][5] = bytes(code)
    from perf2_core import parse_swf, rebuild_swf
    data, tags = parse_swf(base)
    tampered = rebuild_swf(base, data, tags, {MAIN: abc_t})
    try:
        apply_patches(tampered, PATCHES)
        ok("refuse tampered target body", False)
    except Refused as e:
        ok("refuse tampered target body", True, str(e)[:140])
    # 差分
    t0, t1 = abc_tags(base), abc_tags(patched)
    ok("DoABC2 tag list unchanged", [t[0] for t in t0] == [t[0] for t in t1])
    changed = [t0[i][0].decode() for i in range(len(t0)) if t0[i][4] != t1[i][4]]
    ok("only boot_ffc6 changed", changed == ["boot_ffc6"], changed)
    a0, a1 = main_abc(base), main_abc(patched)
    targets = {bodies.resolve(a0, p["label"]) for p in PATCHES}
    diff = [i for i in range(len(a0.bodies)) if freeze(a0.bodies[i]) != freeze(a1.bodies[i])]
    ok("main ABC: only 3 target bodies differ", set(diff) == targets and len(a0.bodies) == len(a1.bodies),
       f"{len(a0.bodies) - len(diff)} of {len(a0.bodies)} bodies byte-identical; changed={sorted(diff)}")
    for field in ("strings", "multinames", "namespaces", "ns_sets", "methods", "metadata", "instances", "classes",
                  "scripts", "ints", "uints", "doubles"):
        assert freeze(getattr(a0, field)) == freeze(getattr(a1, field)), field
    ok("main ABC pools/tables identical (zero append)", True)
    ok("SWF header/version kept", base[:4] == patched[:4])
    sims = {}
    for p in PATCHES:
        b = body_of(a1, p["label"])
        sims[p["id"]] = check_body(a1, b)
        assert sha(b[5]) == p["after"]
    ok("stack/scope simulation within headers", True, sims)
    users = field_users(a1, "prevPowerFlipChargeLv")
    ok("prevPowerFlipChargeLv readers/writers", all(k.startswith("BattleFlipperImpl/") or k == "BattleFlipperView/draw" for k in users)
       and users.get("BattleFlipperView/draw") == ["getproperty"],
       users)
    users0 = field_users(a0, "prevPowerFlipChargeLv")
    ok("prevPowerFlipChargeLv in base: only BattleFlipperImpl", all(k.startswith("BattleFlipperImpl/") for k in users0),
       users0)
    kyubi = field_users(a1, "kyubiPowerFlipInitialCombo")
    writers = [k for k, v in kyubi.items() if "setproperty" in v or "initproperty" in v]
    ok("kyubiPowerFlipInitialCombo writer unchanged", writers == ["BallImpl/resolveCollisionForPrimaryOrSummons"], kyubi)
    p2b = asm.decode(body_of(a1, "BattleFlipperImpl/update")[5])
    names = {a1.mn_name(c.args[0]) for c in p2b if c.args and c.name in ("callproperty", "callpropvoid")}
    strs = sorted({a1.s(c.args[0]) for c in p2b if c.name == "pushstring" and "/" in a1.s(c.args[0])})
    ok("P2 static: no getLazySoundPlayer / playSoundEffectWithRepeat / fromCharCode",
       not any(n.endswith(("getLazySoundPlayer", "playSoundEffectWithRepeat")) for n in names)
       and not any(c.name == "pushstring" and a1.s(c.args[0]) == "fromCharCode" for c in p2b), strs)
    preload = Path(r"D:/WF/resources/game/wf-extracted/wf-extracted/orderedmap/asset/sound_effect_asset_iosbundled.json")
    if preload.exists():
        tab = json.loads(preload.read_text(encoding="utf8"))
        ses = [x for x in strs if x.startswith("sound_effect/")]
        ok("P2 static: every SE path is in loading=6 group (addCommonAssets bookSoundFromMaster(6))",
           all(tab.get(x, [[None] * 4])[0][3] == "6" for x in ses), ses)
    verify_p1(a0, a1)
    verify_p2(a0, a1)
    verify_p3(a0, a1)
    summary = {"base_swf_sha256": sha(base), "patched_swf_sha256": sha(patched),
               "bodies_total": len(a0.bodies), "bodies_changed": sorted(diff), "checks": RESULTS}
    if out_json:
        out_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf8")
    print("ALL PASS", len(RESULTS), "checks")


if __name__ == "__main__":
    main()
