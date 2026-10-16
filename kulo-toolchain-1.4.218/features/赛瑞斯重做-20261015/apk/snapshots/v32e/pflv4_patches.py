"""赛瑞斯重做 · PF Lv4 客户端方法补丁（可重放，叠在 v31-overlimit120 之上；框架 = perf-v30 的 perf2_core）。

档位整数始终停在 3；「Lv4」= Lv3 + 换一棵 DSL（forLevels 含 4 的 override 行，DSL 放在 lv3 列）。

P1 MemberImpl/startPowerFlip
     队长分支：param2==3 且 (ball as BallImpl).kyubiPowerFlipInitialCombo >= 100（v28 写的拍板快照，原始 int）
     → 先查 getPowerFlipOverrides(4)，非 null 就用它（仍走 lv3 列）；否则落回原逻辑 getPowerFlipOverrides(param2)。
P2 BattleFlipperImpl/update（基线 = v29/v31 字节，newfunction 62995/62996 原样保留）
     Lv4 就绪 = 档位==3 && 当前连击>=100 && battle.abilityTotalizer.getPowerFlipOverrides(4)!=null。
     查询只在 frameCount%QUERY_EVERY==0 时做（getPowerFlipOverrides 每次调用都会 newactivation+闭包），
     其余帧沿用上一帧结果（prevPowerFlipChargeLv==4）。结果存进 prevPowerFlipChargeLv=4（只有本类与 P3 读）。
     跨入就绪：viewOrder.playSoundEffect(Me, SE_PATH)，与原码 Lv3 充能音同一调用（v32b；v32 的懒加载通路真机崩 8022）；
     就绪：只在进入那一帧重放一次官方 twinkle "three"（v32e；不再周期重放、不放任何 HitEffect）。
     4→3（未拍板、override 失效）时不把 charge/spark 打回 "one"。
P3 BattleFlipperView/draw（activated 分支末尾）
     prevPowerFlipChargeLv==4：spark 强制可见；bg/fg 四个 MovieClip .color 与 spark set_color 染 LV4_COLOR；
     离开 Lv4 写回 0xFFFFFF（spark 可见性由原逻辑每帧重置）。颜色只在「backgroundL.color != 目标」那一帧写。

主 ABC 常量池零追加：
  * SE_PATH 是池里现成字符串（#66230），addCommonAssets 无条件预载；"three" 复用原码 #119 的字符串。
  * LV4_COLOR 不在 int 池里：用 pushshort/lshift/bitor 运行时算（0xFFFFFF 在 int 池 #7，直接 pushint）。
"""
from __future__ import annotations

import sys

sys.path.insert(0, r"D:/WF/perf-v30-20261015/tools")
from common import asm, bodies  # noqa: E402
from perf2_core import MAIN, Refused, splice_with_exits  # noqa: E402

# ------------------------------------------------------------------ 可调常量（改了要重算 after sha）
LV4_COLOR = 0xFF4040            # P3 弹板与 spark 的乘法染色
WHITE = 0xFFFFFF
COMBO_THRESHOLD = 100           # P1/P2 共用
LV4_KEY = 4                     # override 行 forLevels 里的键
QUERY_EVERY = 10                # P2：每 N 帧查一次 getPowerFlipOverrides(4)
# v32e：twinkle（整根弹板大小的 Lv3 闪光）只在进入就绪时重放一次。
# 它的 Lv3 段是大块白/青辉光，red() 纯红偏移会把整块填成实心红（真机反馈：弹板上两大团糊红），
# 所以默认不给 twinkle 上红，只红 spark；想要红闪光把 TWINKLE_RED 改 True 重算 sha。
TWINKLE_RED = False
GRADIENT_STEPS = 8              # v32c：Lv3 阈值→100 之间的渐变档数（0..STEPS-1），就绪=满色
PREV_GRADIENT_BASE = 10         # prevPowerFlipChargeLv 编码：10+step = 有 Lv4 行、充能中；4 = 就绪
# v32 用的 sound_effect/thunder/se_charge_with_electricity 走懒加载，真机崩 ClientError 8022
# （SoundAssetContainer.getDelayLoadAssetCache：战斗里没有 index 99/100 的延迟加载缓存）。
# v32b 改播 loading=6 预载组里的音：sound_effect_asset_iosbundled 该行 loading=6，
# 由 BattleAssetPathCollectionBuilder.addCommonAssets :560 bookSoundFromMaster(6) 无条件预载（每场战斗
# addBattleAssets :773 都调用）；调用方式与原版 update() 的 Lv3 充能音完全相同。
# 作者要求「清脆」：解码实测（单声道 44.1k）候选——
#   se_player_skill_ready        1.19s 谱心 5.2kHz 主峰 5.5kHz >3k 占 65% 起音 6ms   ← 选用（池 #66230，MemberImpl:870 原生同调用）
#   se_boss_weakpoint_appearance 1.35s 谱心 5.3kHz 主峰 1.8kHz 平坦度 0.22（偏噪），boss 战语义冲突
#   se_fever_time_yakumono_shine 1.41s 谱心 2.8kHz 很纯（平坦度 0.04）但 Fever 中弹板物频繁播放，会被淹没
#   （se_player_charge_completed 也在 loading=6 组，但主 ABC 池里没有这条字符串）
SE_PATH = "sound_effect/battle_common/se_player_skill_ready"
# v32b thunder_small（自带 se_electric_attack）、v32c paralysis_ball（像 boss 被麻痹）都已撤掉：
# v32d 就绪视觉 = 弹板自带的官方 Lv3 充能件（twinkle/charge/spark 的 "three" 段）强制显示 + red() 纯红偏移。


def _require(cond, what):
    if not cond:
        raise Refused(what)


def _code(body):
    return asm.decode(body[5])


def uniq(abc, name, kind=0x07):
    hits = [i for i in range(1, len(abc.multinames))
            if abc.multinames[i][0] == kind and abc.mn_name(i) == name]
    _require(len(hits) == 1, f"multiname {name!r} kind {kind:#x}: {len(hits)} hits")
    return hits[0]


def at(abc, code, pos, opname, name):
    ins = code[pos]
    _require(ins.name == opname and abc.mn_name(ins.args[0]) == name,
             f"anchor #{pos}: {ins.name} {abc.mn_name(ins.args[0]) if ins.args else ''} != {opname} {name}")
    return ins.args[0]


def string_index(abc, text):
    raw = text.encode()
    hits = [i for i in range(1, len(abc.strings)) if abc.strings[i] == raw]
    _require(hits, f"string {text!r} not in main pool (append refused)")
    return hits[0]


def int_index(abc, value):
    hits = [i for i in range(1, len(abc.ints)) if abc.ints[i] == value]
    return hits[0] if hits else None


def push_small(value):
    _require(0 <= value <= 0x7FFF, f"constant {value} out of pushshort range")
    return ("pushbyte", value) if value <= 0x7F else ("pushshort", value)


def push_rgb(abc, value):
    """24 位颜色：int 池里有就 pushint，否则 (r<<16)|(g<<8)|b 运行时算（不追加常量）。"""
    idx = int_index(abc, value)
    if idx is not None:
        return [("pushint", idx)]
    r, g, b = (value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF
    return [push_small(r), ("pushbyte", 16), ("lshift",), push_small(g), ("pushbyte", 8), ("lshift",), ("bitor",),
            push_small(b), ("bitor",)]


def _fit_header(abc, body, initial_scope=None):
    """按模拟结果抬高 max_stack（只升不降）。"""
    code = asm.decode(body[5])
    _enc, offsets = asm.encode(code)
    index_of = {o: i for i, o in enumerate(offsets)}
    handlers = [index_of[e[2]] for e in body[6]]
    ms, _sc, _u = asm.simulate(code, body[3] if initial_scope is None else initial_scope, abc.multinames, handlers)
    body[1] = max(body[1], ms)


def _splice(body, at_index, block, exits, incoming=asm.FORBID):
    old = body[5]
    new, exc, _merged, n = splice_with_exits(body, at_index, block, exits, incoming)
    _require(asm.unsplice(new, at_index, n) == old, f"inverse splice differs at #{at_index}")
    body[5], body[6] = new, exc
    return n


# ============================================================================================ P1
def p1_apply(abc, index, pool):
    body = abc.bodies[index]
    _require(body[1:5] == [27, 19, 1, 2] and not body[6] and not body[7], "startPowerFlip header")
    code = _code(body)
    _require(code[17].name == "callproperty" and abc.mn_name(code[17].args[0]) == "isLeader", "isLeader anchor")
    _require(code[19].name == "iffalse" and code[19].target == 41, "isLeader branch anchor")
    m_battle = at(abc, code, 21, "getproperty", "battle")
    m_total = at(abc, code, 22, "getproperty", "abilityTotalizer")
    m_get = at(abc, code, 24, "callproperty", "getPowerFlipOverrides")
    m_str = at(abc, code, 25, "coerce", "String")
    _require(code[23].name == "getlocal_2" and code[27].name == "setlocal" and code[27].args == [4], "override local")
    _require([c.name for c in code[28:32]] == ["getlocal", "pushnull", "coerce", "ifeq"] and code[31].target == 41,
             "null-check anchor")
    m_ball = at(abc, code, 124, "getproperty", "ball")
    m_ballimpl = uniq(abc, "pinball.scene.battle.battle.squad.ball::BallImpl")
    m_kyubi = uniq(abc, "kyubiPowerFlipInitialCombo")
    ball_local = body[2]                       # 19：新局部变量
    block = [
        ("getlocal_2",), ("pushbyte", 3), ("ifne", "ORIG"),
        ("getlocal_0",), ("getproperty", m_ball), ("astype", m_ballimpl), ("setlocal", ball_local),
        ("getlocal", ball_local), ("iffalse", "ORIG"),
        ("getlocal", ball_local), ("getproperty", m_kyubi), push_small(COMBO_THRESHOLD), ("iflt", "ORIG"),
        ("getlocal_0",), ("getproperty", m_battle), ("getproperty", m_total), ("pushbyte", LV4_KEY),
        ("callproperty", m_get, 1), ("coerce", m_str), ("setlocal", 4),
        ("getlocal", 4), ("pushnull",), ("ifeq", "ORIG"),
        ("jump", "HAVE"),
    ]
    n = _splice(body, 20, block, {"ORIG": 20, "HAVE": 28})
    body[2] = ball_local + 1
    _fit_header(abc, body)
    return {"inserted_at": 20, "block_len": n, "new_locals": [ball_local]}


# ============================================================================================ P2
def p2_apply(abc, index, pool):
    body = abc.bodies[index]
    _require(body[1:5] == [5, 7, 1, 2] and not body[6] and not body[7], "update header")
    code = _code(body)
    # v29/v31 闭包编号必须原样（v28 噪声：63455/63456 → 62995/62996）
    _require(code[182].name == "newfunction" and code[202].name == "newfunction", "newfunction anchors")
    closures = (code[182].args[0], code[202].args[0])
    m_cc = at(abc, code, 64, "getproperty", "comboCalculator")
    _require(abc.mn_name(code[65].args[0]).endswith("ComboCalculator::getPowerFlipChargeLv")
             and code[68].name == "setlocal_3", "charge-lv anchor")
    m_prev = at(abc, code, 71, "getproperty", "prevPowerFlipChargeLv")
    _require(code[72].name == "lessthan" and code[73].name == "iffalse" and code[73].target == 82, "lessthan anchor")
    _require(code[85].name == "greaterthan" and code[86].target == 153, "greaterthan anchor")
    _require(code[153].name == "findproperty" and abc.mn_name(code[153].args[0]) == "prevPowerFlipChargeLv"
             and code[158].name == "initproperty" and abc.mn_name(code[158].args[0]) == "prevPowerFlipChargeLv",
             "prev write anchor")
    m_frame = at(abc, code, 52, "getproperty", "frameCount")
    m_view = at(abc, code, 134, "getproperty", "viewOrder")
    m_mode = at(abc, code, 135, "getlex", "pinball.scene.battle.battle.sound::BattleSoundMode")
    m_me = at(abc, code, 136, "getproperty", "Me")
    m_index = at(abc, code, 41, "getproperty", "index")
    m_params = at(abc, code, 45, "getproperty", "params")
    mnl = code[47].args[0]
    _require(code[47].name == "getproperty" and abc.multinames[mnl][0] == 0x1B, "MultinameL anchor")
    # 外部 donor（同 ABC 已有用法）
    d_bfi = abc.bodies[bodies.resolve(abc, "BattleFlipperImpl/getPositionL")]
    dc = _code(d_bfi)
    m_fl = at(abc, dc, 4, "getproperty", "flipperLeft")
    m_flipper = at(abc, dc, 5, "getproperty", "flipper")
    m_x = at(abc, dc, 6, "getproperty", "x")
    m_y = at(abc, dc, 11, "getproperty", "y")
    m_fr = uniq(abc, "flipperRight")
    d_ball = _code(abc.bodies[bodies.resolve(abc, "BallImpl/resolveCollisionForPrimaryOrSummons")])
    m_mask = at(abc, d_ball, 145, "getlex", "pinball.common.mask::MaskGeneral")
    m_maskbit = at(abc, d_ball, 146, "getproperty", "maskBit")
    m_getcombo = at(abc, d_ball, 140, "callproperty", "pinball.scene.battle.battle:ComboCalculator::getCombo")
    # MemberImpl/startPowerFlip 可能已被 P1 改过（同一 ABC 顺序应用），这里不用它当 donor
    m_battle = uniq(abc, "battle")
    m_total = uniq(abc, "abilityTotalizer")
    m_get = uniq(abc, "getPowerFlipOverrides")
    d_rdy = _code(abc.bodies[bodies.resolve(abc, "Battle/updateReadyState")])
    m_em = at(abc, d_rdy, 27, "getproperty", "effectManager")
    m_show = at(abc, d_rdy, 36, "callpropvoid", "show")
    d_hit = _code(abc.bodies[bodies.resolve(abc, "ImpactHitEffectManager/showImmediately")])
    m_ek = at(abc, d_hit, 60, "getlex", "pinball.scene.battle.battle.effect::EffectKind")
    m_sek = at(abc, d_hit, 61, "getlex", "pinball.scene.battle.battle.effect::SimpleEffectKind")
    m_hit = at(abc, d_hit, 67, "callproperty", "HitEffect")
    m_simple = at(abc, d_hit, 69, "callproperty", "Simple")
    m_sep = uniq(abc, "pinball.scene.battle.battle.effect::SimpleEffectPosition")
    m_fixed = uniq(abc, "FixedPosition")
    m_pse = at(abc, code, 152, "callpropvoid", "pinball.scene.battle.view:BattleViewOrder::playSoundEffect")
    _require(code[151].name == "pushstring" and abc.s(code[151].args[0]) ==
             "sound_effect/battle_common/se_combo_power_flip_max_lv3", "lv3 SE anchor")
    s_se = string_index(abc, SE_PATH)
    m_tw = at(abc, code, 118, "getproperty", "playheadTwinkleAnimation")
    _require(code[119].name == "pushstring" and abc.s(code[119].args[0]) == "three", "twinkle three anchor")
    s_three = code[119].args[0]
    m_goto = at(abc, code, 120, "callpropvoid", "gotoAndPlay")

    st, tmp, thr = body[2], body[2] + 1, body[2] + 2   # 7/8/9：本帧状态、raw/step、raw 阈值
    m_lv3 = uniq(abc, "getPowerFlipNumComboChargeLv3")   # ComboCalculatorImpl 唯一实现，公有方法
    # D @159：prevPowerFlipChargeLv = st（无 Lv4 行时 st==lv，与原码写入值相同）
    block_d = [("getlocal_0",), ("getlocal", st), ("setproperty", m_prev)]
    # C @153（ENTER：所有路径都先过这一块，读到的是旧 prev）
    block_c = [
        ("getlocal", st), ("pushbyte", 4), ("ifne", "C_END"),
        ("getlocal_0",), ("getproperty", m_prev), ("pushbyte", 4), ("ifeq", "C_END"),
        # 与原码 #147-#152（Lv3 充能音）完全同一调用：viewOrder.playSoundEffect(Me, <loading=6 预载音>)
        ("getlocal_0",), ("getproperty", m_view), ("getlex", m_mode), ("getproperty", m_me),
        ("pushstring", s_se), ("callpropvoid", m_pse, 2),
        # 与原码 #117-#120（升到 Lv3 时）同一调用：playheadTwinkleAnimation.gotoAndPlay("three")，时间轴无声
        ("getlocal_0",), ("getproperty", m_tw), ("pushstring", s_three), ("callpropvoid", m_goto, 1),
        ("label", "C_END"),
    ]
    # B @74（「<」分支内）：lv==3 且 prev>=4（只可能是本补丁写的 4 / 10+step）时不打回 "one"。
    # 原版 prev<=3，lv==3 时「<」不可能成立，所以无 Lv4 行时与原版等价。
    block_b = [
        ("getlocal_3",), ("pushbyte", 3), ("ifne", "B_END"),
        ("getlocal_0",), ("getproperty", m_prev), ("pushbyte", 4), ("ifge", "SKIP"),
        ("label", "B_END"),
    ]
    # A @69：st = lv；lv==3 且队长有 forLevels=4 行时 st = 4（连击>=100）或 10+step（渐变档）。
    #        查询每 QUERY_EVERY 帧一次，其余帧由旧 prev（4 或 >=10）推出「有行」。local3 不改。
    block_a = [
        ("getlocal_3",), ("setlocal", st),
        ("getlocal_3",), ("pushbyte", 3), ("ifne", "A_END"),
        ("getlocal_0",), ("getproperty", m_frame), push_small(QUERY_EVERY), ("modulo",), ("convert_i",),
        ("pushbyte", 0), ("ifne", "A_KEEP"),
        ("getlocal_0",), ("getproperty", m_battle), ("getproperty", m_total), ("pushbyte", LV4_KEY),
        ("callproperty", m_get, 1), ("pushnull",), ("ifeq", "A_END"),
        ("jump", "A_HAS"),
        ("label", "A_KEEP"),
        ("getlocal_0",), ("getproperty", m_prev), ("pushbyte", 4), ("ifeq", "A_HAS"),
        ("getlocal_0",), ("getproperty", m_prev), push_small(PREV_GRADIENT_BASE), ("iflt", "A_END"),
        ("label", "A_HAS"),
        ("getlex", m_mask), ("getproperty", m_maskbit), ("getlocal_0",), ("getproperty", m_cc),
        ("callproperty", m_getcombo, 0), ("bitxor",), ("convert_i",), ("setlocal", tmp),
        ("getlocal", tmp), push_small(COMBO_THRESHOLD), ("iflt", "A_STEP"),
        ("pushbyte", 4), ("setlocal", st), ("jump", "A_END"),
        ("label", "A_STEP"),
        ("getlex", m_mask), ("getproperty", m_maskbit), ("getlocal_0",), ("getproperty", m_cc),
        ("callproperty", m_lv3, 0), ("bitxor",), ("convert_i",), ("setlocal", thr),
        ("getlocal", thr), push_small(COMBO_THRESHOLD), ("ifge", "A_ZERO"),
        ("getlocal", tmp), ("getlocal", thr), ("subtract",), push_small(GRADIENT_STEPS), ("multiply",),
        push_small(COMBO_THRESHOLD), ("getlocal", thr), ("subtract",), ("divide",), ("convert_i",), ("setlocal", tmp),
        ("getlocal", tmp), ("pushbyte", 0), ("iflt", "A_ZERO"),
        ("getlocal", tmp), push_small(GRADIENT_STEPS - 1), ("ifle", "A_SET"),
        push_small(GRADIENT_STEPS - 1), ("setlocal", tmp), ("jump", "A_SET"),
        ("label", "A_ZERO"),
        ("pushbyte", 0), ("setlocal", tmp),
        ("label", "A_SET"),
        push_small(PREV_GRADIENT_BASE), ("getlocal", tmp), ("add",), ("convert_i",), ("setlocal", st),
        ("label", "A_END"),
    ]
    placed = []
    placed.append(("D", 159, _splice(body, 159, block_d, {})))
    placed.append(("C", 153, _splice(body, 153, block_c, {}, incoming=asm.ENTER)))
    placed.append(("B", 74, _splice(body, 74, block_b, {"SKIP": 82})))
    placed.append(("A", 69, _splice(body, 69, block_a, {})))
    body[2] = thr + 1
    _fit_header(abc, body)
    after = _code(body)
    _require(sorted(c.args[0] for c in after if c.name == "newfunction") == sorted(closures), "closure ids changed")
    return {"blocks": [{"id": i, "inserted_at_original": p, "block_len": n} for i, p, n in placed],
            "new_locals": [st, tmp, thr], "closures_preserved": list(closures)}


# ============================================================================================ P3
def p3_apply(abc, index, pool):
    body = abc.bodies[index]
    _require(body[1:5] == [6, 23, 1, 2] and not body[6] and not body[7], "draw header")
    code = _code(body)
    n_ins = len(code)
    _require(code[n_ins - 1].name == "returnvoid" and n_ins - 1 == 769, "draw tail anchor")
    _require(code[515].name == "jump" and code[515].target == 769, "inactive-branch exit anchor")
    _require(code[436].name == "iffalse" and code[436].target == 516, "activated anchor")
    _require(code[766].name == "callproperty" and abc.mn_name(code[766].args[0]) == "getCurrentFrame"
             and code[768].name == "initproperty" and abc.mn_name(code[768].args[0]) == "currentFrame", "fg frame anchor")
    m_flipper = at(abc, code, 432, "getproperty", "flipper")
    m_bgL = at(abc, code, 446, "getproperty", "backgroundL")
    m_fgL = at(abc, code, 448, "getproperty", "foregroundL")
    m_bgR = at(abc, code, 457, "getproperty", "backgroundR")
    m_fgR = at(abc, code, 459, "getproperty", "foregroundR")
    m_spL = at(abc, code, 476, "getproperty", "sparkAnimationLeft")
    m_spR = at(abc, code, 480, "getproperty", "sparkAnimationRight")
    m_vis = at(abc, code, 478, "initproperty", "visible")
    m_chL = at(abc, code, 468, "getproperty", "chargeAnimationLeft")
    m_chR = at(abc, code, 472, "getproperty", "chargeAnimationRight")
    m_twL = at(abc, code, 49, "getproperty", "twinkleAnimationLeft")
    m_twR = at(abc, code, 56, "getproperty", "twinkleAnimationRight")
    m_red = uniq(abc, "red")
    m_bfi = uniq(abc, "pinball.scene.battle.battle.flipper::BattleFlipperImpl")
    m_prev = uniq(abc, "prevPowerFlipChargeLv")
    m_color = uniq(abc, "color")
    m_setcolor = uniq(abc, "set_color")
    # activated 分支里 local12 = hasComboFixed()（原码 :447 `_loc12_ = flipper.hasComboFixed()`）
    _require(abc.mn_name(code[566].args[0]).endswith("BattleFlipperPeek::hasComboFixed")
             and code[569].name == "setlocal" and code[569].args == [12], "comboFixed local anchor")
    impl, c_local, rdy = body[2], body[2] + 1, body[2] + 2      # 23 / 24 / 25

    def channel(shift):
        t = (LV4_COLOR >> shift) & 0xFF
        d = 0xFF - t
        if d == 0:
            return [push_small(0xFF)]
        return [push_small(0xFF), push_small(d), ("getlocal", c_local), ("multiply",), push_small(GRADIENT_STEPS + 1),
                ("divide",), ("convert_i",), ("subtract",), ("convert_i",)]

    block = [
        ("getlocal_0",), ("getproperty", m_flipper), ("astype", m_bfi), ("setlocal", impl),
        ("pushfalse",), ("setlocal", rdy),
        ("getlocal", impl), ("iffalse", "WHITE"),
        ("getlocal", impl), ("getproperty", m_prev), ("convert_i",), ("setlocal", c_local),
        ("getlocal", c_local), ("pushbyte", 4), ("ifne", "GRAD"),
        # 就绪：满色 + 官方 Lv3 spark 强制可见（comboFixed 时不强制）。charge（涨条件）保持官方逻辑：满了就隐藏
        ("pushtrue",), ("setlocal", rdy),
        ("getlocal", 12), ("iftrue", "RED"),
        ("getlocal_0",), ("getproperty", m_spL), ("pushtrue",), ("setproperty", m_vis),
        ("getlocal_0",), ("getproperty", m_spR), ("pushtrue",), ("setproperty", m_vis),
        ("label", "RED"),
        *push_rgb(abc, LV4_COLOR), ("setlocal", c_local), ("jump", "APPLY"),
        # 充能中（prev = 10+step）：k = step+1 ∈ [1, STEPS]，每通道 255 - (255-t)*k/(STEPS+1)
        ("label", "GRAD"),
        ("getlocal", c_local), push_small(PREV_GRADIENT_BASE), ("iflt", "WHITE"),
        ("getlocal", c_local), push_small(PREV_GRADIENT_BASE + GRADIENT_STEPS - 1), ("ifgt", "WHITE"),
        ("getlocal", c_local), push_small(PREV_GRADIENT_BASE - 1), ("subtract",), ("convert_i",), ("setlocal", c_local),
        *channel(16), ("pushbyte", 16), ("lshift",),
        *channel(8), ("pushbyte", 8), ("lshift",), ("bitor",),
        *channel(0), ("bitor",),
        ("setlocal", c_local), ("jump", "APPLY"),
        ("label", "WHITE"),
        *push_rgb(abc, WHITE), ("setlocal", c_local),
        ("label", "APPLY"),
        ("getlocal_0",), ("getproperty", m_bgL), ("getproperty", m_color), ("getlocal", c_local), ("ifeq", "DONE"),
        ("getlocal_0",), ("getproperty", m_bgL), ("getlocal", c_local), ("setproperty", m_color),
        ("getlocal_0",), ("getproperty", m_bgR), ("getlocal", c_local), ("setproperty", m_color),
        ("getlocal_0",), ("getproperty", m_fgL), ("getlocal", c_local), ("setproperty", m_color),
        ("getlocal_0",), ("getproperty", m_fgR), ("getlocal", c_local), ("setproperty", m_color),
        # 官方 Lv3 件（青/黄/白）用 red() 纯红偏移：乘法 tint 会把 R≈0 的青色压成黑
        *[x for m in ((m_twL, m_twR, m_spL, m_spR) if TWINKLE_RED else (m_spL, m_spR))
          for x in (("getlocal_0",), ("getproperty", m), ("getlocal", rdy), ("callpropvoid", m_red, 1))],
        ("label", "DONE"),
    ]
    # SKIP：非 activated 分支 #515 的 jump 落到块之后，块只在 activated 分支末尾执行
    n = _splice(body, 769, block, {}, incoming=asm.SKIP)
    body[2] = rdy + 1
    _fit_header(abc, body)
    return {"inserted_at": 769, "block_len": n, "new_locals": [impl, c_local, rdy], "incoming": "skip(#515 inactive branch)"}


PATCHES = [
    # P1 原体与 vanilla 相同；依赖 v28 九尾补丁写的 kyubiPowerFlipInitialCombo，用写点方法的 sha 当守卫
    {"id": "P1", "tag": MAIN, "label": "MemberImpl/startPowerFlip", "apply": p1_apply,
     "guards": {"BallImpl/resolveCollisionForPrimaryOrSummons":
                "fde02ea9a9645500b28a7990bb0404d300dc4ee3184fd7bab10f3942fdd1bf52"},
     "before": "675b4a9e5874e5bba8502ea998963a20ab198d3553e0159a5f8422b7c9987f51",
     "after": "0aaa43db85c048dda9784925de22fccc38068f638449fcb59938420f12fc2d6b"},
    {"id": "P2", "tag": MAIN, "label": "BattleFlipperImpl/update", "apply": p2_apply,
     "before": "24a82efac221d89329538f22aef48a3fc108ff14e686d7ebfbc5298c41df9679",
     "after": "e5e9189070daef3c66d91e55a6e86b044095cb4c9113ae92ef8509d31d4246fb"},
    {"id": "P3", "tag": MAIN, "label": "BattleFlipperView/draw", "apply": p3_apply,
     "before": "f41af0aac1af319b772ce53153f26cd9e1979cbeb4d98276c7b1c5deaccecf11",
     "after": "0c8a88ca7016a9325dd99ee1ec8c4ca5405f0032b16bd2e80cd1f438c0713994"},
]
