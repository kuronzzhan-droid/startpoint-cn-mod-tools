# -*- coding: utf-8 -*-
"""多段直击/凯尔 PF 追加结算的「只首段出表现」客户端补丁（hitfx-silence-v1）。

只做单方法指令级插入（author-merge 的 abcasm：splice + 逐字节可逆校验），不回编 AS3、不动常量池。
两个方法体按 sha256 + header 锁定，对不上即拒绝：

1. MemberImpl/scheduleDirectAttack：每段直击的 ImpactSource.hitEffect，第 2 段起（段下标 _loc11_ != 0）
   改为 Option.None。伤害、段数、计数、触发全部照旧（schedule() 的其余参数不动）。
2. EnemyImpl/applyAttack：在 `lastAttackResult = param1` 之后、伤害数字之前插入提前返回：
   a) 本机主战斗 && createdByDirectAttack && hitEffect == None   → 不弹伤害数字、不播命中特效/受击音效/受击闪烁
   b) hitEffect == Some 且 paths[0] == "battle/common/layer0/attack_to_hostile_hit" 且 randomRotation == false
      （凯尔 PF 追加判定区专用标记；原生直击该路径 randomRotation 恒为 true，全语料 DSL 0 处使用）→ 同上
   扣血、韧性、Fever、统计、词条计数都在插入点之前完成，不受影响。

用法：
  python wf_hitfx_silence.py --apk IN.apk --out OUT.apk --signer local|debug [--work DIR]
  local = 本机 com.leiting.wf（wf_new.keystore，口令取自本机既有构建脚本默认值，只进子进程环境变量）
  debug = 测试服 com.leiting.wt（~/.android/debug.keystore / androiddebugkey）
  每次构建轮换 AndroidManifest 里的 AIR uniqueappversionid（同长 UTF-16 替换），使 AIR 重新解包 SWF。
"""
from __future__ import annotations

import argparse, ast, hashlib, json, os, re, shutil, subprocess, sys, uuid, zipfile
from pathlib import Path

ABCASM = Path(r"D:/WF/startpoint-cn-kulo/client-patch/author-merge-20261001/abcasm")
sys.path.insert(0, str(ABCASM))
import asm, bodies  # noqa: E402
from swfabc import SwfAbc, PoolEditor  # noqa: E402

SWF_MEMBER = "assets/worldflipper_android_release.swf"
TOOLS = Path(r"D:/WF/runtimes/android-toolchain/sdk/build-tools/34.0.0")
JAVA_HOME = Path(r"D:/WF/runtimes/android-toolchain/jdk/jdk-17.0.19+10")
LOCAL_KS = Path(r"D:/WF/_archive/kept/弹国服-tools-and-decompile/instrument/wf_new.keystore")
LOCAL_KS_SRC = LOCAL_KS.with_name("build_instrumented_apk.py")
DEBUG_KS = Path(os.path.expanduser("~")) / ".android" / "debug.keystore"
MARKER = b"battle/common/layer0/attack_to_hostile_hit"
CAPABILITY = ["hitfx-silence-v1", "kyle-direct-params-v1", "charge-cap-unique-v1", "boss-stun-gauge-v1", "hidden-unique-icons-v1", "battle-score-x0.01-v1"]

LOCKS = {
    "MemberImpl/scheduleDirectAttack": {"sha": "fe24bf97e3da", "header": [110, 38, 1, 2]},
    "EnemyImpl/applyAttack": {"sha": "d3bbb8fbe858", "header": [23, 25, 1, 2]},
    "MemberImpl/getStatModifierSkillGaugeCharging": {"sha": "dc4a5916bb83", "header": [3, 22, 1, 2]},
    "EnemyImpl/isBattleDebugToughnessPointGaugeVisible": {"sha": "f22ed568b3d1", "header": [1, 1, 1, 2]},
    "ImpactManagerImpl/addDamageBattleScore": {"sha": "8a3e84ff4a51", "header": [2, 3, 1, 2]},
    "ImpactManagerImpl/addHealBattleScore": {"sha": "0f16d9bfb843", "header": [4, 6, 1, 2]},
    "MemberImpl/getConditionsIncludingOuterEnvironments": {"sha": "37257280c482", "header": [1, 1, 1, 2]},
}
HIDDEN_PREFIX = "hidden_"   # unique_condition string_id 以此开头 → 状态栏不画图标（状态本身照常生效、计数照常）
KYLE_CODE = "kyle_moon"          # character c0 / SquadMemberSource.mainCharacterStringId
KYLE_BASE_UNIQUE = 13999011      # 凯尔直击基础倍率：层数 = 倍数（0/无 → 不改）
KYLE_PERCOMBO_UNIQUE = 13999012  # 每连击加成：层数 × 0.01%
KYLE_COMBO_CAP = None            # 不设设计上限：引擎 MAX_COMBO=9999、单段伤害钳 MAX_DAMAGE=9,999,999,999（全程 Number，无 int32 截断）
CHARGE_CAP_UNIQUE = 13999010     # 「强化充能速度」固有状态：层数 n → 充能速度上限 n%（n/100；仅当 > 官方 100% 时生效）
CHARGE_CAP_DIV = 100
MERGE_MIN = 4                    # 直击段数 ≥ 4（只有 DSL ACAdditionalDirectAttack 能达到）才合并结算


def sha(b):
    return hashlib.sha256(b).hexdigest()


class Fail(SystemExit):
    pass


def expect(ins, i, op, name=None, abc=None, arg=None):
    x = ins[i]
    if x.op != asm.MNEMONICS[op]:
        raise Fail(f"anchor #{i}: expected {op}, got {x.name}")
    if name is not None and abc.mn_name(x.args[0]).split("::")[-1].split(":")[-1] != name:
        raise Fail(f"anchor #{i}: expected {op} {name}, got {abc.mn_name(x.args[0])}")
    if arg is not None and x.args[0] != arg:
        raise Fail(f"anchor #{i}: operand {x.args} != {arg}")
    return x.args[0] if x.args else None


def mn_from(abc, label, index, op, name):
    body = abc.bodies[bodies.resolve(abc, label)]
    ins = asm.decode(body[5])
    return expect(ins, index, op, name, abc)


def body_ins(abc, label):
    return asm.decode(abc.bodies[bodies.resolve(abc, label)][5])


def find_mn(abc, label, op, name):
    """在参考方法体里找唯一的 (op, 名字) 多名下标——不新建、不猜。"""
    hits = {x.args[0] for x in body_ins(abc, label)
            if x.op == asm.MNEMONICS[op] and x.args and abc.mn_name(x.args[0]).split("::")[-1].split(":")[-1] == name}
    if len(hits) != 1:
        raise Fail(f"multiname {name} via {op} in {label}: {sorted(hits)}")
    return hits.pop()


def trait_mn(abc, cls, name):
    k = [i for i, r in enumerate(abc.instances) if abc.mn_name(r[0]).endswith("::" + cls)]
    if len(k) != 1:
        raise Fail("class " + cls)
    t = [t for t in abc.instances[k[0]][6] if abc.mn_name(t.name).split(":")[-1] == name]
    if len(t) != 1:
        raise Fail(f"trait {cls}.{name}")
    return t[0].name


def patch_swf(src: Path, dst: Path) -> dict:
    swf = SwfAbc(src)
    abc = swf.abc
    before_bodies = [bytes(b[5]) for b in abc.bodies]
    pool0 = (list(abc.strings), list(abc.multinames), list(abc.ints))
    pool = PoolEditor(abc)
    idx = {lab: bodies.resolve(abc, lab) for lab in LOCKS}
    for lab, bi in idx.items():
        b = abc.bodies[bi]
        got = sha(b[5])
        if b[1:5] != LOCKS[lab]["header"] or (LOCKS[lab]["sha"] and not got.startswith(LOCKS[lab]["sha"])):
            raise Fail(f"unknown method baseline for {lab}: sha {got[:12]} header {b[1:5]} (locked {LOCKS[lab]}); already patched or different client")
    # ---------------- 锚点
    sd = asm.decode(abc.bodies[idx["MemberImpl/scheduleDirectAttack"]][5])
    option = expect(sd, 461, "getlex", "Option", abc)
    expect(sd, 465, "pushstring", abc=abc, arg=abc.strings.index(MARKER))
    expect(sd, 475, "callproperty", "Some", abc)
    expect(sd, 476, "coerce", "Option", abc)
    if sd[477].op != asm.MNEMONICS["pushstring"] or abc.strings[sd[477].args[0]] != b"createdByCoopCommand":
        raise Fail("anchor 477 is not createdByCoopCommand")
    none_mn = expect(sd, 350, "getproperty", "None", abc)
    if sd[349].op != asm.MNEMONICS["getlex"] or sd[349].args[0] != option:
        raise Fail("anchor 349 is not getlex Option")
    coerce_option = sd[476].args[0]
    expect(sd, 165, "setlocal", arg=11); expect(sd, 163, "inclocal_i", arg=9)
    decimal = expect(sd, 239, "getlex", "Decimal_Impl_", abc)
    expect(sd, 240, "pushbyte", arg=1)
    from_float = expect(sd, 241, "callproperty", "fromFloat", abc)
    expect(sd, 244, "setlocal", arg=26)
    for at, key, val in ((412, b"enablesComboBonus", "pushfalse"), (426, b"currentCombos", "pushbyte")):
        if sd[at].op != asm.MNEMONICS["pushstring"] or abc.strings[sd[at].args[0]] != key:
            raise Fail(f"anchor {at} is not {key!r}")
        expect(sd, at + 1, val)
    if sd[427].args[0] != 0:
        raise Fail("currentCombos literal is not 0")
    expect(sd, 399, "pushstring"); expect(sd, 400, "getlocal", arg=26)
    if abc.strings[sd[399].args[0]] != b"multiplierOfAttackPoint":
        raise Fail("local 26 is not multiplierOfAttackPoint")
    ap = asm.decode(abc.bodies[idx["EnemyImpl/applyAttack"]][5])
    expect(ap, 596, "initproperty", "lastAttackResult", abc)
    expect(ap, 597, "getlocal_2"); expect(ap, 598, "getproperty", "shouldShowDamageFont", abc)
    hit_mn = expect(ap, 656, "getproperty", "hitEffect", abc)
    primary_mn = expect(ap, 662, "getproperty", "createdByPrimaryBattle", abc)
    direct_mn = {x.args[0] for x in ap if x.op == 0x66 and abc.mn_name(x.args[0]).endswith("createdByDirectAttack")}
    if len(direct_mn) != 1:
        raise Fail("createdByDirectAttack multiname not unique")
    direct_mn = direct_mn.pop()
    index_mn = mn_from(abc, "EnemyImpl/showHitEffect", 3, "getproperty", "index")
    params_mn = mn_from(abc, "EnemyImpl/showHitEffect", 11, "getproperty", "params")
    sh = body_ins(abc, "EnemyImpl/showHitEffect")
    expect(sh, 12, "pushbyte", arg=0)
    elem_mn = sh[13].args[0]
    if sh[13].op != 0x66 or abc.multinames[elem_mn][0] != 0x1B:
        raise Fail("element access multiname is not MultinameL")
    paths_mn = mn_from(abc, "ImpactHitEffectManager/show", 18, "getproperty", "paths")
    rot_mn = mn_from(abc, "ImpactHitEffectManager/show", 48, "getproperty", "randomRotation")
    marker_str = abc.strings.index(MARKER)
    gc = asm.decode(abc.bodies[idx["MemberImpl/getStatModifierSkillGaugeCharging"]][5])
    expect(gc, 179, "getlocal_1"); expect(gc, 180, "getlocal_2"); expect(gc, 181, "add"); expect(gc, 184, "setlocal", arg=8)
    bconst = expect(gc, 194, "getlex", "BattleConstants", abc)
    max_mn = expect(gc, 195, "getproperty", "MAX_STAT_MIDIFIER_SKILL_GAUGE_CHARGING", abc)
    expect(gc, 202, "setlocal", arg=8)
    expect(gc, 203, "findproperty", "stats", abc)
    # 其余多名：只取既有条目
    is_leader = trait_mn(abc, "MemberImpl", "isLeader")
    source_mn = trait_mn(abc, "MemberImpl", "source")
    combo_calc = trait_mn(abc, "MemberImpl", "comboCalculator")
    acc_mn = trait_mn(abc, "MemberImpl", "getConditionAccumulationCount")
    main_id = find_mn(abc, "MemberImpl/isExchangedPowerFlip", "getproperty", "mainCharacterStringId")
    mask_cls = find_mn(abc, "ActionEvaluator/evalCommand", "getlex", "MaskGeneral")
    mask_bit = find_mn(abc, "ActionEvaluator/evalCommand", "getproperty", "maskBit")
    get_combo = find_mn(abc, "ActionEvaluator/evalCommand", "callproperty", "getCombo")
    ctk = find_mn(abc, "GeneralEnemy/testUniqueCondition", "getlex", "ConditionTargetKind")
    unique_mn = find_mn(abc, "GeneralEnemy/testUniqueCondition", "callproperty", "Unique")
    kyle_str = pool.string(KYLE_CODE)
    iuniq = pool.integer(CHARGE_CAP_UNIQUE)
    i_base = pool.integer(KYLE_BASE_UNIQUE)
    i_per = pool.integer(KYLE_PERCOMBO_UNIQUE)
    i_10000 = pool.integer(10000)

    # ---------------- 块
    L_B, L_CC, L_P, L_C = 38, 39, 43, 44   # scheduleDirectAttack 新局部（原 localcount 38；40-42 给合并块）
    def acc(uid_idx, dst):
        return [("getlocal_0",), ("getlex", ctk), ("pushint", uid_idx), ("callproperty", unique_mn, 1),
                ("callproperty", acc_mn, 1), ("convert_i",), ("setlocal", dst)]
    kyle = [  # 原 #245：_loc26_ 初值之后。倍率全部由数据（固有层数）决定：
        # mult = B × (1 + P/10000 × combo)；B = 13999011 层数（0/无 → 不改），P = 13999012 层数（单位 0.01%/连击）
        ("getlocal_0",), ("callproperty", is_leader, 0), ("iffalse", "END"),
        ("getlocal_0",), ("getproperty", source_mn), ("getproperty", main_id),
        ("pushstring", kyle_str), ("ifne", "END"),
        *acc(i_base, L_B),
        ("getlocal", L_B), ("pushbyte", 0), ("ifngt", "END"),
        *acc(i_per, L_P),
        ("pushbyte", 0), ("setlocal", L_C),
        ("getlocal_0",), ("getproperty", combo_calc), ("setlocal", L_CC),
        ("getlocal", L_CC), ("iffalse", "NOC"),
        ("getlex", mask_cls), ("getproperty", mask_bit), ("getlocal", L_CC), ("callproperty", get_combo, 0),
        ("convert_i",), ("bitxor",), ("convert_i",), ("setlocal", L_C),
        ("label", "NOC"),
        ("getlex", decimal),
        ("getlocal", L_B), ("pushbyte", 1), ("getlocal", L_P), ("getlocal", L_C), ("multiply",),
        ("pushint", i_10000), ("divide",), ("add",), ("multiply",),
        ("callproperty", from_float, 1), ("convert_d",), ("setlocal", 26),
    ]
    block_a = [  # 原 #477：第 2 段起 hitEffect = None
        ("getlocal", 11), ("pushbyte", 0), ("ifeq", "END"),
        ("pop",), ("getlex", option), ("getproperty", none_mn), ("coerce", coerce_option),
    ]
    hit = [("getlocal_1",), ("getproperty", hit_mn)]
    some0 = hit + [("getproperty", params_mn), ("pushbyte", 0), ("getproperty", elem_mn)]
    block_b = [
        ("getlocal_1",), ("getproperty", primary_mn), ("iffalse", "R2"),
        ("getlocal_2",), ("getproperty", direct_mn), ("iffalse", "R2"),
        *hit, ("getproperty", index_mn), ("pushbyte", 1), ("ifne", "R2"),
        ("returnvoid",),
        ("label", "R2"),
        *hit, ("getproperty", index_mn), ("pushbyte", 0), ("ifne", "END"),
        *some0, ("getproperty", rot_mn), ("iftrue", "END"),
        *some0, ("getproperty", paths_mn), ("pushbyte", 0), ("getproperty", elem_mn),
        ("pushstring", marker_str), ("ifne", "END"),
        ("returnvoid",),
    ]
    L_N, L_SUM, L_CAP = 22, 23, 24   # getStatModifierSkillGaugeCharging 新局部（原 localcount 22）
    charge = [  # 原 #203：官方上限钳完之后；持有固有 n 层 → 上限 1+n/50，未钳前的和在上限内就恢复
        ("getlocal_0",), ("getlex", ctk), ("pushint", iuniq), ("callproperty", unique_mn, 1),
        ("callproperty", acc_mn, 1), ("convert_i",), ("setlocal", L_N),
        ("getlocal", L_N), ("pushbyte", 0), ("ifngt", "END"),
        ("getlocal_1",), ("getlocal_2",), ("add",), ("convert_d",), ("setlocal", L_SUM),
        ("getlocal", L_SUM), ("getlex", bconst), ("getproperty", max_mn), ("ifngt", "END"),
        ("getlex", decimal), ("getlocal", L_N), ("pushbyte", CHARGE_CAP_DIV), ("divide",),
        ("callproperty", from_float, 1), ("convert_d",), ("setlocal", L_CAP),
        ("getlocal", L_CAP), ("getlex", bconst), ("getproperty", max_mn), ("ifngt", "END"),
        ("getlocal", L_SUM), ("getlocal", L_CAP), ("ifngt", "USESUM"),
        ("getlocal", L_CAP), ("setlocal", 8), ("jump", "END"),
        ("label", "USESUM"),
        ("getlocal", L_SUM), ("setlocal", 8),
    ]
    # ---- 多段直击合并结算（段数 N ≥ MERGE_MIN）
    at_trig = trait_mn(abc, "MemberImpl", "abilityTrigger")
    stats_mn = trait_mn(abc, "MemberImpl", "stats")
    zm_mn = trait_mn(abc, "MemberImpl", "zoneManager")
    battle_mn = trait_mn(abc, "MemberImpl", "battle")
    mv = body_ins(abc, "DirectAttackScheduler/move")
    parent_mn = expect(mv, 33, "getproperty", "parent", abc)
    enemy_t = expect(mv, 34, "coerce", "Enemy", abc)
    count_up = expect(mv, 44, "callpropvoid", "countUp", abc)
    one_of = expect(mv, 51, "callpropvoid", "oneOfEnemyCountUp", abc)
    da_cnt = expect(mv, 86, "getproperty", "directAttackCount", abc)
    is_fever = expect(mv, 92, "callproperty", "isFeverMode", abc)
    da_fev = expect(mv, 100, "getproperty", "directAttackCountInFever", abc)
    is_my = find_mn(abc, "MemberImpl/update", "callproperty", "__isMyBattle__")
    create_combo = find_mn(abc, "EnemyImpl/applyAttack", "callpropvoid", "createCombo")
    from_int = expect(sd, 253, "callproperty", "fromInt", abc)
    expect(sd, 157, "getlocal", arg=5); expect(sd, 159, "setlocal", arg=10); expect(sd, 160, "jump")
    expect(sd, 406, "getlocal", arg=5); expect(sd, 408, "pushbyte", arg=1); expect(sd, 409, "convert_d")
    expect(sd, 411, "getlocal", arg=28)
    if abc.strings[sd[407].args[0]] != b"basicDetoughness" or abc.strings[sd[410].args[0]] != b"basicFeverPoint":
        raise Fail("source field anchors moved")
    L_N2, L_X, L_K = 40, 41, 42
    enemy = [("getlocal_2",), ("getproperty", parent_mn), ("coerce", enemy_t)]
    merge = [  # 原 #160：循环前。N ≥ 4 → 只排 1 段，伤害不再 ÷N（单段=原 N 段总和），其余 N-1 段的计数/连击在此一次补齐
        ("pushbyte", 0), ("setlocal", L_N2),
        ("getlocal", 5), ("pushbyte", MERGE_MIN), ("iflt", "END"),
        ("getlocal", 5), ("setlocal", L_N2),
        ("pushbyte", 1), ("setlocal", 5), ("pushbyte", 1), ("setlocal", 10),
        ("getlocal", L_N2), ("pushbyte", 1), ("subtract_i",), ("setlocal", L_X),
        ("getlocal_0",), ("getproperty", at_trig), *enemy, ("pushbyte", 3), ("getlocal", L_X), ("pushtrue",),
        ("callpropvoid", count_up, 4),
        ("getlocal_0",), ("getproperty", stats_mn), ("dup",), ("getproperty", da_cnt), ("getlocal", L_X), ("add_i",),
        ("initproperty", da_cnt),
        ("getlocal_0",), ("getproperty", zm_mn), ("callproperty", is_fever, 0), ("convert_b",), ("iffalse", "NOFEV"),
        ("getlocal_0",), ("getproperty", stats_mn), ("dup",), ("getproperty", da_fev), ("getlocal", L_X), ("add_i",),
        ("initproperty", da_fev),
        ("label", "NOFEV"),
        ("pushbyte", 0), ("setlocal", L_K), ("jump", "LCHK"),
        ("label", "LOOP"), ("avm_label",),
        ("getlocal_0",), ("getproperty", at_trig), *enemy, ("pushbyte", 2), ("callpropvoid", one_of, 2),
        ("getlocal_0",), ("getproperty", battle_mn), ("callproperty", is_my, 0), ("iffalse", "SKIPC"),
        ("getlocal_0",), ("getproperty", combo_calc), ("callpropvoid", create_combo, 0),
        ("label", "SKIPC"),
        ("inclocal_i", L_K),
        ("label", "LCHK"),
        ("getlocal", L_K), ("getlocal", L_X), ("iflt", "LOOP"),
    ]
    tough = [("getlocal", L_N2), ("pushbyte", MERGE_MIN), ("iflt", "END"), ("pop",), ("getlocal", L_N2)]   # 原 #409
    fever = [("getlocal", L_N2), ("pushbyte", MERGE_MIN), ("iflt", "END"), ("pop",),
             ("getlex", decimal), ("getlocal", L_N2), ("callproperty", from_int, 1), ("convert_d",)]       # 原 #412
    # ---- boss 韧性（击晕）调试条常显：kind == 3 → true
    kind_mn = expect(body_ins(abc, "EnemyImpl/hasBattleDebugToughnessPointProtected"), 5, "getproperty", "kind", abc)
    tv = asm.decode(abc.bodies[idx["EnemyImpl/isBattleDebugToughnessPointGaugeVisible"]][5])
    expect(tv, 4, "getproperty", "viewShowEnemyToughnessPointGauge", abc); expect(tv, 5, "returnvalue")
    stun = [("getlocal_0",), ("getproperty", kind_mn), ("pushbyte", 3), ("ifne", "END"), ("pushtrue",), ("returnvalue",)]
    # ---- 状态栏隐藏 hidden_* 固有状态
    gc2 = asm.decode(abc.bodies[idx["MemberImpl/getConditionsIncludingOuterEnvironments"]][5])
    if len(gc2) != 7:
        raise Fail("getConditionsIncludingOuterEnvironments body changed")
    expect(gc2, 4, "callproperty", "getConditionsIncludingOuterEnvironments", abc); expect(gc2, 6, "returnvalue")
    uc = asm.decode(abc.bodies[bodies.resolve(abc, "UniqueConditionLogic/<ctor>")][5])
    uct = expect(uc, 11, "getlex", "UniqueConditionTable", abc)
    get_mt = expect(uc, 12, "callproperty", "getMasterTable", abc)
    get_data = expect(uc, 14, "callproperty", "get_data", abc)
    mm_get = expect(uc, 17, "callproperty", "get", abc)
    la_mn = trait_mn(abc, "MemberImpl", "logicAssets")
    gi = body_ins(abc, "ConditionIcon/getIconIndex")
    content_mn = expect(gi, 13, "getproperty", "content", abc)
    sid_mn = find_mn(abc, "UniqueConditionLogic/get_stringId", "getproperty", "string_id") if any(
        v == "UniqueConditionLogic/get_stringId" for v in bodies.label_map(abc).values()) else None
    def any_mn(name):
        import collections
        c = collections.Counter()
        for b in abc.bodies:
            for x in asm.decode(b[5]):
                if x.args and x.op in (0x46, 0x4F, 0x66) and abc.multinames[x.args[0]][0] == 7 and abc.mn_name(x.args[0]) == name:
                    c[x.args[0]] += 1
            if c and sum(c.values()) > 20:
                break
        if not c:
            raise Fail("no public multiname " + name)
        return c.most_common(1)[0][0]
    if sid_mn is None:
        sid_mn = any_mn("string_id")
    push_mn, len_mn, indexof_mn = any_mn("push"), any_mn("length"), any_mn("indexOf")
    pfx = pool.string(HIDDEN_PREFIX)
    filt = [  # 原 #6（returnvalue 前，栈顶 = 原数组）
        ("setlocal_1",), ("newarray", 0), ("setlocal_2",),
        ("getlocal_0",), ("getproperty", la_mn), ("getlex", uct), ("callproperty", get_mt, 1),
        ("callproperty", get_data, 0), ("setlocal", 6),
        ("pushbyte", 0), ("setlocal_3",), ("jump", "CHK"),
        ("label", "LOOP"), ("avm_label",),
        ("getlocal_1",), ("getlocal_3",), ("getproperty", elem_mn), ("setlocal", 4),
        ("getlocal", 4), ("getproperty", content_mn), ("getproperty", index_mn), ("pushbyte", 31), ("ifne", "KEEP"),
        ("getlocal", 6), ("getlocal", 4), ("getproperty", content_mn), ("getproperty", params_mn), ("pushbyte", 0),
        ("getproperty", elem_mn), ("callproperty", mm_get, 1), ("setlocal", 5),
        ("getlocal", 5), ("iffalse", "KEEP"),
        ("getlocal", 5), ("getproperty", sid_mn), ("pushstring", pfx), ("callproperty", indexof_mn, 1),
        ("pushbyte", 0), ("ifeq", "SKIP"),
        ("label", "KEEP"),
        ("getlocal_2",), ("getlocal", 4), ("callpropvoid", push_mn, 1),
        ("label", "SKIP"),
        ("inclocal_i", 3),
        ("label", "CHK"),
        ("getlocal_3",), ("getlocal_1",), ("getproperty", len_mn), ("iflt", "LOOP"),
        ("getlocal_2",),
    ]
    # ---- 战斗分数 ×0.01（伤害、治疗计分入口；所有计分器都经这两处）
    sdm = body_ins(abc, "ImpactManagerImpl/addDamageBattleScore")
    expect(sdm, 13, "getlocal_2"); expect(sdm, 14, "callpropvoid", "addDamageBattleScore", abc)
    shl = body_ins(abc, "ImpactManagerImpl/addHealBattleScore")
    expect(shl, 14, "getlocal", arg=4); expect(shl, 15, "callpropvoid", "addHealBattleScore", abc)
    score_dmg = [("getlocal_2",), ("pushbyte", 100), ("divide",), ("setlocal_2",)]
    score_heal = [("getlocal", 4), ("pushbyte", 100), ("divide",), ("setlocal", 4)]
    plan = {
        "ImpactManagerImpl/addDamageBattleScore": [(2, score_dmg, asm.FORBID)],
        "ImpactManagerImpl/addHealBattleScore": [(2, score_heal, asm.FORBID)],
        "MemberImpl/getConditionsIncludingOuterEnvironments": [(6, filt, asm.FORBID)],
        "EnemyImpl/isBattleDebugToughnessPointGaugeVisible": [(2, stun, asm.FORBID)],
        "MemberImpl/scheduleDirectAttack": [(160, merge, asm.FORBID), (245, kyle, asm.FORBID), (409, tough, asm.FORBID),
                                            (412, fever, asm.FORBID), (477, block_a, asm.FORBID)],
        "EnemyImpl/applyAttack": [(597, block_b, asm.FORBID)],
        # #203 是官方 `if(MAX < x)` 假分支的落点 ⇒ ENTER：两条路径都要经过本块
        "MemberImpl/getStatModifierSkillGaugeCharging": [(203, charge, asm.ENTER)],
    }
    report = {}
    for lab, adds in plan.items():
        body = abc.bodies[idx[lab]]
        before = bytes(body[5]); header_before = list(body[1:5])
        code, exc, merged, placed = asm.splice_many(body, [(at, asm.assemble(bl), pol) for at, bl, pol in adds])
        if asm.unsplice_many(code, placed) != before:
            raise Fail("not reversible: " + lab)
        analysis = [asm.Instruction(0x02) if x.op in (0xEF, 0xF0, 0xF1) else x for x in merged]
        metrics = asm.simulate(analysis, body[3], abc.multinames)
        if metrics[1] != body[4] or metrics[2]:
            raise Fail(f"stack/scope check failed: {lab} {metrics}")
        body[1] = max(body[1], metrics[0])
        body[2] = max(body[2], asm.block_locals(merged))
        body[5], body[6] = code, exc
        report[lab] = {"body": idx[lab], "before": sha(before), "after": sha(code), "inserted_at": placed,
                       "header_before": header_before, "header_after": list(body[1:5]), "metrics": list(metrics)}
    changed = [i for i, b in enumerate(abc.bodies) if bytes(b[5]) != before_bodies[i]]
    if sorted(changed) != sorted(idx.values()):
        raise Fail(f"unexpected body changes: {changed}")
    # 常量池只追加：原有条目逐个不变
    if abc.strings[:len(pool0[0])] != pool0[0] or abc.multinames[:len(pool0[1])] != pool0[1] or abc.ints[:len(pool0[2])] != pool0[2]:
        raise Fail("existing constant pool entries changed")
    data = swf.serialize()
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(data)
    back = SwfAbc(dst)
    for lab, bi in idx.items():
        if sha(back.abc.bodies[bi][5]) != report[lab]["after"]:
            raise Fail("readback mismatch " + lab)
    return {"source_swf_sha256": sha(src.read_bytes()), "output_swf_sha256": sha(data),
            "source_abc_sha256": sha(SwfAbc(src).abc.serialize()), "output_abc_sha256": sha(back.abc.serialize()),
            "methods": report, "bodies_total": len(abc.bodies), "bodies_changed": len(changed),
            "constant_pool_appended": pool.report(),
            "constants": {"kyle_code": KYLE_CODE, "kyle_formula": "mult = n(13999011) * (1 + n(13999012)/10000 * combo), leader && kyle_moon only", "kyle_combo_cap": "none (engine MAX_COMBO 9999; MAX_DAMAGE clamp)",
                          "charge_cap_unique": CHARGE_CAP_UNIQUE, "charge_cap_formula": f"stacks/{CHARGE_CAP_DIV} (only if above engine max 1.0)", "merge_min_segments": MERGE_MIN}}


def is_sig(name):
    p = name.upper().split("/")
    return len(p) == 2 and p[0] == "META-INF" and (p[1] == "MANIFEST.MF" or p[1].endswith((".RSA", ".SF", ".DSA", ".EC")))


def run(args, env=None):
    r = subprocess.run([str(a) for a in args], capture_output=True, text=True, encoding="utf8", errors="replace", env=env)
    if r.returncode:
        raise Fail(f"{Path(str(args[0])).name} failed ({r.returncode}); output withheld (signing inputs)")
    return r.stdout


def signer_env(kind):
    env = os.environ.copy()
    env["JAVA_HOME"] = str(JAVA_HOME)
    env["PATH"] = str(JAVA_HOME / "bin") + os.pathsep + env.get("PATH", "")
    if kind == "debug":
        env["WF_HITFX_KS"] = env["WF_HITFX_KEY"] = "android"   # Android SDK 标准 debug 口令
        return env, ["--ks", DEBUG_KS, "--ks-key-alias", "androiddebugkey"]
    tree = ast.parse(LOCAL_KS_SRC.read_text(encoding="utf8"))
    vals = {}
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "add_argument"
                and node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value in ("--ks-pass", "--ks-key-pass")):
            vals[node.args[0].value] = ast.literal_eval(next(k.value for k in node.keywords if k.arg == "default"))
    ks = (vals.get("--ks-pass") or "").removeprefix("pass:")
    kp = (vals.get("--ks-key-pass") or vals.get("--ks-pass") or "").removeprefix("pass:")
    if not ks:
        raise Fail("local keystore password not found")
    env["WF_HITFX_KS"], env["WF_HITFX_KEY"] = ks, kp or ks
    return env, ["--ks", LOCAL_KS]


def certs(apk, env):
    out = run([TOOLS / "apksigner.bat", "verify", "--verbose", "--print-certs", apk], env)
    d = sorted(set(re.findall(r"certificate SHA-256 digest: ([0-9a-f]{64})", out)))
    if not d:
        raise Fail("no verified certificate")
    return d, {"v1": "Verified using v1 scheme (JAR signing): true" in out,
               "v2": "Verified using v2 scheme (APK Signature Scheme v2): true" in out}


def build(a):
    work = Path(a.work)
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    out = Path(a.out)
    if out.exists():
        raise Fail("output exists: " + str(out))
    base = Path(a.apk)
    base_bytes_sha = sha(base.read_bytes())
    env, ksargs = signer_env(a.signer)
    base_certs, _ = certs(base, env)
    src_swf = work / "base.swf"
    with zipfile.ZipFile(base) as z:
        names = z.namelist()
        if names.count(SWF_MEMBER) != 1 or len(set(names)) != len(names):
            raise Fail("missing/duplicate members")
        src_swf.write_bytes(z.read(SWF_MEMBER))
        manifest = z.read("AndroidManifest.xml")
    swf_report = patch_swf(src_swf, work / "patched.swf")
    swf = (work / "patched.swf").read_bytes()
    # AIR uniqueappversionid：清单里同长 UTF-16 替换
    text = manifest.decode("utf-16le", "ignore")
    olds = sorted(set(re.findall(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", text)))
    if len(olds) != 1 or manifest.count(olds[0].encode("utf-16le")) != 1:
        raise Fail(f"manifest uniqueappversionid not unique: {olds}")
    new_uid = str(uuid.uuid4())
    manifest2 = manifest.replace(olds[0].encode("utf-16le"), new_uid.encode("utf-16le"))
    unsigned, aligned = work / "unsigned.apk", work / "aligned.apk"
    kept = {}
    with zipfile.ZipFile(base) as s, zipfile.ZipFile(unsigned, "w") as d:
        d.comment = s.comment
        for m in s.infolist():
            if is_sig(m.filename):
                continue
            data = swf if m.filename == SWF_MEMBER else manifest2 if m.filename == "AndroidManifest.xml" else s.read(m)
            d.writestr(m, data)
            kept[m.filename] = (sha(data), m.compress_type)
    run([TOOLS / "zipalign.exe", "-p", "-f", "4", unsigned, aligned])
    out.parent.mkdir(parents=True, exist_ok=True)
    run([TOOLS / "apksigner.bat", "sign", "--v4-signing-enabled", "false", *ksargs,
         "--ks-pass", "env:WF_HITFX_KS", "--key-pass", "env:WF_HITFX_KEY", "--out", out, aligned], env)
    out_certs, schemes = certs(out, env)
    if out_certs != base_certs:
        raise Fail("signer certificate differs from base — would not install over it")
    run([TOOLS / "zipalign.exe", "-c", "-p", "4", out])
    with zipfile.ZipFile(out) as r:
        if {n for n in r.namelist() if not is_sig(n)} != set(kept) or r.testzip() is not None:
            raise Fail("member inventory/CRC differs")
        for n, exp in kept.items():
            if (sha(r.read(n)), r.getinfo(n).compress_type) != exp:
                raise Fail("member changed: " + n)
    if sha(base.read_bytes()) != base_bytes_sha:
        raise Fail("base APK changed during build")
    for p in (unsigned, aligned):
        p.unlink()
    rep = {"capability": CAPABILITY, "status": "signed_static_candidate", "installed": False, "runtime_verified": False,
           "base_apk": str(base), "base_apk_sha256": base_bytes_sha, "apk": str(out), "apk_sha256": sha(out.read_bytes()),
           "signer": a.signer, "certificate_sha256": out_certs, "signature_schemes": schemes,
           "uniqueappversionid": {"before": olds[0], "after": new_uid},
           "changed_members": ["AndroidManifest.xml", SWF_MEMBER, "META-INF signature"],
           "preserved_members": len(kept) - 2, **swf_report}
    out.with_suffix(".build-report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=2) + "\n", "utf8")
    print(json.dumps({k: rep[k] for k in ("apk", "apk_sha256", "output_swf_sha256", "certificate_sha256", "uniqueappversionid")}, ensure_ascii=False))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--apk", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--signer", choices=("local", "debug"), required=True)
    p.add_argument("--work", default=None)
    a = p.parse_args()
    a.work = a.work or str(Path(a.out).with_suffix(".work"))
    build(a)


if __name__ == "__main__":
    main()
