"""Fever 箭头 → 随机道具（通用词条，任何角色的队长技都能靠数据挂上）。叠在 v32f（P1-P3）之上，单方法 P-code 拼接。

框架同 pflv4_patches：perf2_core.apply_patches（原 sha → 打补丁；after sha → 跳过；其他 → 整包拒绝），主 ABC 常量池零追加。
设计/调研：D:/WF/out/赛瑞斯重做-20261015/research/fever_arrows.md（本实现把「固定 uid + 固定候选」改成「uid 槽位 + 数据驱动候选表」）。

数据约定（详见 README「Fever 道具」节）：
  * 标记 = 本 Battle 的队长身上有 unique condition，uid ∈ [MARKER_UID_BASE, MARKER_UID_BASE + MARKER_SLOTS)，层数 > 0。
    查法 = 原版 ConditionSlot 计数（squadManager.getLeader().getConditionAccumulationCount(ConditionTargetKind.Unique(uid))）。
    多个槽位同时成立时取 uid 最小的那个。
  * 候选表 = 该 uid 的 unique_condition 行 string_id：  fever:items:<key1>|<key2>|...[:<任意标签>]
    key = master/battle/yakumono/direct_instant_item 的行键（不带 _fever 后缀）；不存在的键运行时自动丢弃。
    客户端在 key 后面拼 "_" + "fever" 再交给原版 resolveDirectInstantItem（两段字符串都是池里现成的）。

B1 YakumonoManagerImpl/activate（Fever 开始）
   PRE（播完 se_fever_time_yakumono_shine 之后）：找第一块 FEVER 箭头（DashPanelBase && values.availableTime.index==1），
   没有 → 原样；有 → 从它的 squadManager 取队长查标记槽位；无标记 → 原样（M=false）。
   有标记（M=true）：解析候选表；对每块 FEVER 箭头，若同坐标还没有 DirectInstantItemImpl，就抽一个键建道具：
     rng = gear.absorb(RandomSeedFactory).createSeparativeRandomNumberGenerator(uid + ((int(x)<<14) ^ int(y)))
     k   = keys[int(rng.randomFloat() * keys.length)]
     src = gear.absorb(BattleQuestLogic).resolveDirectInstantItem(k + "_" + "fever", ITEM_LV)
     it  = new DirectInstantItemImpl({x: p.x, y: p.y}, src, p.rotationPanelAnimation); yakumonoes.add(it); gear.addChild(it)
   原循环：M 时跳过 FEVER 箭头的 activate()（箭头保持关闭、不播 open/RotationPanelOpen）；新道具在同一个循环里被 activate → popItem。
   之后同一区再进 Fever：同坐标已有道具 → 不重抽，道具照官方 FEVER 道具规则重新出现。
B2 YakumonoManagerImpl/deactivate（Fever 结束）
   同一标记判定；M 且 FEVER 箭头且 state.index==1（Deactivated，从没开过）→ 跳过 deactivate()（不播 close / RotationPanelClose）。
B3 BattleQuestBaseImpl/resolvePathCollectionForDashPanel（视图层预载，不门控）
   原 addSoundEffect 之后：对每个槽位 uid 的有效候选键 resolveDirectInstantItem(k+"_fever", ITEM_LV).resolvePathCollection(builder)。
（v32g 的 B4 TerrainHandler/readHandler 已撤掉：进游戏时主表未加载，崩 8013；B3 已覆盖道具 DSL 预载，见文件末注释。）
v32h：所有读主表的注入代码都改用不抛异常的 getMasterTableMaybe，表未加载 → 候选表视为空。
"""
from __future__ import annotations

import sys

sys.path.insert(0, r"D:/WF/perf-v30-20261015/tools")
from common import asm, bodies  # noqa: E402
from perf2_core import MAIN, Refused, splice_with_exits  # noqa: E402

# ------------------------------------------------------------------ 可调常量（改了要重算 after sha）
MARKER_UID_BASE = 1299901        # 第一个标记槽位（赛瑞斯用这个）
MARKER_SLOTS = 9                 # 槽位 1299901..1299909，每个槽位一套候选表
ITEM_LV = 100                    # 道具等级（官方 = zone.enemyLevel；atk 曲线 atk_basic_normal 定义域 1..100）
SID_TAG = ("fever", "items")     # string_id 前两段（池里现成：#4768 / #5204）
SID_SEP = ":"                    # 段分隔（池 #217）
KEY_SEP = "|"                    # 候选键分隔（池 #36919；不用逗号，避免 CSV 转义）
FEVER_SUFFIX = ("_", "fever")    # 运行时拼成 "_fever"（两段都在池里）
SEED_SHIFT = 14                  # seed = uid + ((int(x) << 14) ^ int(y))
AVAILABLE_FEVER = 1              # YakumonoAvailableTime.OnlyFeverMode.index
DASH_DEACTIVATED = 1             # DashPanelState.Deactivated.index


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


def public(abc, name):
    """唯一的 QName(PackageNamespace "", name)。"""
    hits = [i for i in range(1, len(abc.multinames))
            if abc.multinames[i][0] == 0x07 and abc.mn_name(i) == name
            and abc.namespaces[abc.multinames[i][1]][0] == 0x16 and abc.ns_name(abc.multinames[i][1]) == ""]
    _require(len(hits) == 1, f"public multiname {name!r}: {len(hits)} hits")
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


def push_int(abc, value):
    """int 池里有就 pushint；小数用 pushbyte/pushshort；否则 (hi<<12)|lo 运行时算（不追加常量）。"""
    hits = [i for i in range(1, len(abc.ints)) if abc.ints[i] == value]
    if hits:
        return [("pushint", hits[0])]
    if 0 <= value <= 0x7F:
        return [("pushbyte", value)]
    if 0 <= value <= 0x7FFF:
        return [("pushshort", value)]
    _require(0 < value < (0x7FFF << 12), f"int {value} out of range")
    return [("pushshort", value >> 12), ("pushbyte", 12), ("lshift",), ("pushshort", value & 0xFFF), ("bitor",)]


def _fit_header(abc, body):
    code = asm.decode(body[5])
    _enc, offsets = asm.encode(code)
    index_of = {o: i for i, o in enumerate(offsets)}
    handlers = [index_of[e[2]] for e in body[6]]
    ms, _sc, _u = asm.simulate(code, body[3], abc.multinames, handlers)
    body[1] = max(body[1], ms)


def _splice(body, at_index, block, exits, incoming=asm.FORBID):
    old = body[5]
    new, exc, _merged, n = splice_with_exits(body, at_index, block, exits, incoming)
    _require(asm.unsplice(new, at_index, n) == old, f"inverse splice differs at #{at_index}")
    body[5], body[6] = new, exc
    return n


# ------------------------------------------------------------------ 共享 multiname（全部来自同 ABC 现有用法）
def names(abc):
    m = {}
    dc = _code(abc.bodies[bodies.resolve(abc, "UniqueConditionLogic/<ctor>")])
    m["UCT"] = at(abc, dc, 11, "getlex", "pinball.master.generated::UniqueConditionTable")
    _require(abc.mn_name(dc[12].args[0]) == "pinball.asset.logic:ILogicAssetContainer::getMasterTable", "UCL donor")
    dtr = _code(abc.bodies[bodies.resolve(abc, "TrimmedImageRepository/<ctor>")])
    m["getMasterTableMaybe"] = at(abc, dtr, 11, "callproperty", "pinball.asset.logic:ILogicAssetContainer::getMasterTableMaybe")
    m["get_data"] = at(abc, dc, 14, "callproperty", "get_data")
    m["MasterMap"] = at(abc, dc, 15, "coerce", "pinball.master.runtime::MasterMap")
    m["mm_get"] = at(abc, dc, 17, "callproperty", "pinball.master.runtime:MasterMap::get")
    m["mm_exists"] = uniq(abc, "pinball.master.runtime:MasterMap::exists")
    dt = _code(abc.bodies[bodies.resolve(abc, "TerrainHandler/resolveDirectInstantItem")])
    m["DIT"] = at(abc, dt, 23, "getlex", "pinball.master.generated::DirectInstantItemTable")
    m["string_id"] = public(abc, "string_id")
    da = _code(abc.bodies[bodies.resolve(abc, "ObjectTypeTools$/decodeAssist")])
    m["split"] = at(abc, da, 8, "callproperty", "http://adobe.com/AS3/2006/builtin::split")
    m["MNL"] = da[22].args[0]
    _require(da[22].name == "getproperty" and abc.multinames[m["MNL"]][0] == 0x1B, "MultinameL donor")
    m["push"] = at(abc, da, 32, "callpropvoid", "http://adobe.com/AS3/2006/builtin::push")
    m["length"] = at(abc, da, 35, "getproperty", "length")
    m["s_colon"] = string_index(abc, SID_SEP)
    m["s_bar"] = string_index(abc, KEY_SEP)
    m["s_tag0"] = string_index(abc, SID_TAG[0])
    m["s_tag1"] = string_index(abc, SID_TAG[1])
    m["s_us"] = string_index(abc, FEVER_SUFFIX[0])
    m["s_fever"] = string_index(abc, FEVER_SUFFIX[1])
    dp = _code(abc.bodies[bodies.resolve(abc, "DashPanelBase/activate")])
    m["values"] = at(abc, dp, 3, "getproperty", "values")
    m["availableTime"] = at(abc, dp, 4, "getproperty", "availableTime")
    m["YAT"] = at(abc, dp, 5, "coerce", "pinball.common.data.battle.yakumono::YakumonoAvailableTime")
    m["index"] = at(abc, dp, 6, "getproperty", "index")
    m["x"] = at(abc, dp, 28, "getproperty", "x")
    m["y"] = at(abc, dp, 30, "getproperty", "y")
    dm = _code(abc.bodies[bodies.resolve(abc, "YakumonoManagerImpl/changeAssets")])
    m["DPB"] = at(abc, dm, 142, "getlex", "pinball.scene.battle.battle.zone.yakumono.dashPanel::DashPanelBase")
    m["DII"] = at(abc, dm, 82, "getlex", "pinball.scene.battle.battle.zone.yakumono.directInstantItem::DirectInstantItemImpl")
    m["yakumonoes"] = at(abc, dm, 6, "getproperty", "yakumonoes")
    m["h"] = at(abc, dm, 7, "getproperty", "h")
    m["item"] = at(abc, dm, 13, "getproperty", "item")
    m["next"] = at(abc, dm, 18, "getproperty", "next")
    dr = _code(abc.bodies[bodies.resolve(abc, "YakumonoManagerImpl/run")])
    m["gear"] = at(abc, dr, 22, "getproperty", "gear")
    m["addChild"] = at(abc, dr, 33, "callpropvoid", "addChild")
    dg = _code(abc.bodies[bodies.resolve(abc, "ActionManagerImpl/preparation")])
    m["RSF"] = at(abc, dg, 71, "getlex", "pinball.scene.battle.battle.random::RandomSeedFactory")
    m["absorb"] = at(abc, dg, 81, "callproperty", "absorb")
    m["createSep"] = at(abc, dg, 84, "callproperty",
                        "pinball.scene.battle.battle.random:RandomSeedFactory::createSeparativeRandomNumberGenerator")
    m["randomFloat"] = uniq(abc, "pinball.common.random:RandomNumberGenerator::randomFloat")
    dz = _code(abc.bodies[bodies.resolve(abc, "TerrainParser$/createZone")])
    m["BQL_resolveDII"] = at(abc, dz, 1913, "callproperty",
                             "pinball.common.data.quest.battle:BattleQuestLogic::resolveDirectInstantItem")
    _require(dz[1918].name == "findpropstrict" and dz[1918].args[0] == m["DII"]
             and dz[1928].name == "constructprop" and dz[1928].args[0] == m["DII"] and dz[1928].args[1] == 3,
             "DirectInstantItemImpl construct donor")
    m["list_add"] = dz[1929].args[0]
    _require(dz[1929].name == "callpropvoid" and abc.mn_name(m["list_add"]) == "add", "List.add donor")
    m["BQL"] = uniq(abc, "pinball.common.data.quest.battle::BattleQuestLogic")
    m["rotationPanelAnimation"] = public(abc, "rotationPanelAnimation")
    m["squadManager"] = public(abc, "squadManager")
    m["asset"] = public(abc, "asset")
    m["state"] = public(abc, "state")
    m["getLeader"] = uniq(abc, "pinball.scene.battle.battle.squad:SquadManager::getLeader")
    m["getCAC"] = uniq(abc, "pinball.scene.battle.battle.squad.member:MemberForParameterCheck::getConditionAccumulationCount")
    m["CTK"] = uniq(abc, "pinball.common.data.character.condition::ConditionTargetKind")
    m["Unique"] = public(abc, "Unique")
    m["s_x"] = string_index(abc, "x")
    m["s_y"] = string_index(abc, "y")
    dq = _code(abc.bodies[bodies.resolve(abc, "BattleQuestBaseImpl/resolvePathCollection")])
    m["resolveDII"] = at(abc, dq, 378, "callproperty", "resolveDirectInstantItem")
    m["resolvePathCollection"] = at(abc, dq, 384, "callpropvoid", "resolvePathCollection")
    m["logicAssets"] = public(abc, "logicAssets")
    m["cache"] = public(abc, "cache")
    return m


# ------------------------------------------------------------------ 片段
def frag_parse(abc, m, p, push_asset, U, OUT, T1, T2, T3, T4):
    """OUT = [有效候选键]（Array，可能为空）。uid 在 local U；asset 由 push_asset 压栈。标签前缀 p。
    v32h：两张表都走不抛异常的 ILogicAssetContainer.getMasterTableMaybe（LogicAssetContainer.as:473-484，
    未加载返回 null），任一张为 null → OUT 留空。
    v32i：槽位 uid 先 exists 再 get；MasterMap.get 遇缺键抛 8601（v32h 进任何战斗都崩，B3 遍历 9 槽而只有 1299901 有行）。注入代码里不再有会抛 8013 的 getMasterTable。"""
    def table_map(local, t):
        return [("getlocal", local), ("coerce", t), ("callproperty", m["get_data"], 0), ("coerce", m["MasterMap"])]
    return [
        ("newarray", 0), ("setlocal", OUT),
        *push_asset, ("getlex", m["UCT"]), ("callproperty", m["getMasterTableMaybe"], 1), ("setlocal", T3),
        ("getlocal", T3), ("iffalse", p + "END"),
        *push_asset, ("getlex", m["DIT"]), ("callproperty", m["getMasterTableMaybe"], 1), ("setlocal", T4),
        ("getlocal", T4), ("iffalse", p + "END"),
        *table_map(T3, m["UCT"]), ("getlocal", U), ("callproperty", m["mm_exists"], 1), ("iffalse", p + "END"),
        *table_map(T3, m["UCT"]), ("getlocal", U), ("callproperty", m["mm_get"], 1), ("setlocal", T1),
        ("getlocal", T1), ("iffalse", p + "END"),
        ("getlocal", T1), ("getproperty", m["string_id"]), ("pushstring", m["s_colon"]),
        ("callproperty", m["split"], 1), ("setlocal", T1),
        ("getlocal", T1), ("getproperty", m["length"]), ("pushbyte", 3), ("iflt", p + "END"),
        ("getlocal", T1), ("pushbyte", 0), ("getproperty", m["MNL"]), ("pushstring", m["s_tag0"]), ("ifne", p + "END"),
        ("getlocal", T1), ("pushbyte", 1), ("getproperty", m["MNL"]), ("pushstring", m["s_tag1"]), ("ifne", p + "END"),
        ("getlocal", T1), ("pushbyte", 2), ("getproperty", m["MNL"]), ("pushstring", m["s_bar"]),
        ("callproperty", m["split"], 1), ("setlocal", T1),
        ("pushbyte", 0), ("setlocal", T2),
        ("jump", p + "COND"),
        ("label", p + "LOOP"), ("avm_label",),
        ("getlocal", T1), ("getlocal", T2), ("getproperty", m["MNL"]), ("setlocal", T3),
        *table_map(T4, m["DIT"]), ("getlocal", T3), ("callproperty", m["mm_exists"], 1), ("iffalse", p + "NEXT"),
        ("getlocal", OUT), ("getlocal", T3), ("callpropvoid", m["push"], 1),
        ("label", p + "NEXT"),
        ("inclocal_i", T2),
        ("label", p + "COND"),
        ("getlocal", T2), ("getlocal", T1), ("getproperty", m["length"]), ("iflt", p + "LOOP"),
        ("label", p + "END"),
    ]


def frag_fever_panel(m, local_value, P, fail):
    """P = local_value as DashPanelBase；不是 FEVER 箭头就跳 fail。"""
    return [
        *local_value, ("getlex", m["DPB"]), ("astypelate",), ("setlocal", P),
        ("getlocal", P), ("iffalse", fail),
        ("getlocal", P), ("getproperty", m["values"]), ("getproperty", m["availableTime"]), ("coerce", m["YAT"]),
        ("getproperty", m["index"]), ("pushbyte", AVAILABLE_FEVER), ("ifne", fail),
    ]


def frag_marker(abc, m, p, M, N, P, D, U, have, done):
    """M=false；找第一块 FEVER 箭头 P，用它的 squadManager 查队长标记 uid → U，成立跳 have，否则跳 done。"""
    return [
        ("pushfalse",), ("setlocal", M),
        ("getlocal_0",), ("getproperty", m["yakumonoes"]), ("getproperty", m["h"]), ("setlocal", N),
        ("jump", p + "FCOND"),
        ("label", p + "FLOOP"), ("avm_label",),
        ("getlocal", N), ("getproperty", m["next"]), ("getlocal", N), ("getproperty", m["item"]), ("swap",),
        ("setlocal", N),
        ("getlex", m["DPB"]), ("astypelate",), ("setlocal", P),
        ("getlocal", P), ("iffalse", p + "FCOND"),
        ("getlocal", P), ("getproperty", m["values"]), ("getproperty", m["availableTime"]), ("coerce", m["YAT"]),
        ("getproperty", m["index"]), ("pushbyte", AVAILABLE_FEVER), ("ifeq", p + "FOUND"),
        ("label", p + "FCOND"),
        ("getlocal", N), ("iftrue", p + "FLOOP"),
        ("jump", done),
        ("label", p + "FOUND"),
        ("getlocal", P), ("getproperty", m["squadManager"]), ("callproperty", m["getLeader"], 0), ("setlocal", D),
        *push_int(abc, MARKER_UID_BASE), ("setlocal", U),
        ("label", p + "ULOOP"), ("avm_label",),
        ("getlocal", D), ("getlex", m["CTK"]), ("getlocal", U), ("callproperty", m["Unique"], 1),
        ("callproperty", m["getCAC"], 1), ("pushbyte", 0), ("ifgt", p + "UHAVE"),
        ("inclocal_i", U),
        ("getlocal", U), *push_int(abc, MARKER_UID_BASE + MARKER_SLOTS), ("iflt", p + "ULOOP"),
        ("jump", done),
        ("label", p + "UHAVE"),
        ("pushtrue",), ("setlocal", M),
        ("jump", have),
    ]


def key_fever(m, KEYS, I):
    return [("getlocal", KEYS), ("getlocal", I), ("getproperty", m["MNL"]), ("pushstring", m["s_us"]), ("add",),
            ("pushstring", m["s_fever"]), ("add",)]


# ============================================================================================ B1
def b1_apply(abc, index, pool):
    body = abc.bodies[index]
    _require(body[1:5] == [3, 3, 1, 2] and not body[6] and not body[7], "activate header")
    code = _code(body)
    _require(len(code) == 34 and code[33].name == "returnvoid", "activate shape")
    _require(abc.s(code[9].args[0]) == "sound_effect/battle_common/se_fever_time_yakumono_shine"
             and code[10].name == "callpropvoid", "fever SE anchor")
    _require(code[11].name == "findproperty" and abc.mn_name(code[11].args[0]) == "yakumonoes", "loop init anchor")
    _require(code[16].name == "jump" and code[16].target == 29 and code[17].name == "avm_label", "loop anchor")
    _require(code[27].name == "getlocal_2" and code[28].name == "callpropvoid"
             and abc.mn_name(code[28].args[0]) == "pinball.scene.battle.battle.zone.yakumono:Yakumono::activate"
             and code[28].args[1] == 0, "activate call anchor")
    _require(code[32].name == "ifne" and code[32].target == 17, "loop tail anchor")
    m = names(abc)
    M, KEYS, N, P, D, U, I, T1, T2, T3, N2, T4 = range(3, 15)
    # 原循环：M 且 FEVER 箭头 → 跳过 activate（落到 #29 循环条件）
    skip = [("getlocal", M), ("iffalse", "DO"),
            *frag_fever_panel(m, [("getlocal_2",)], P, "DO"),
            ("jump", "SKIP"),
            ("label", "DO")]
    pre = [
        *frag_marker(abc, m, "MK_", M, N, P, D, U, "HAVE", "END"),
        ("label", "HAVE"),
        *frag_parse(abc, m, "PA_", [("getlocal", P), ("getproperty", m["asset"])], U, KEYS, T1, T2, T3, T4),
        ("getlocal", KEYS), ("getproperty", m["length"]), ("iffalse", "END"),
        ("getlocal_0",), ("getproperty", m["yakumonoes"]), ("getproperty", m["h"]), ("setlocal", N),
        ("jump", "CCOND"),
        ("label", "CLOOP"), ("avm_label",),
        ("getlocal", N), ("getproperty", m["next"]), ("getlocal", N), ("getproperty", m["item"]), ("swap",),
        ("setlocal", N), ("setlocal", D),
        *frag_fever_panel(m, [("getlocal", D)], P, "CCOND"),
        # 同坐标已有 DirectInstantItemImpl → 本区已经抽过（或官方同位道具），不重抽
        ("getlocal_0",), ("getproperty", m["yakumonoes"]), ("getproperty", m["h"]), ("setlocal", N2),
        ("jump", "SCOND"),
        ("label", "SLOOP"), ("avm_label",),
        ("getlocal", N2), ("getproperty", m["next"]), ("getlocal", N2), ("getproperty", m["item"]), ("swap",),
        ("setlocal", N2),
        ("getlex", m["DII"]), ("astypelate",), ("setlocal", D),
        ("getlocal", D), ("iffalse", "SCOND"),
        ("getlocal", D), ("getproperty", m["x"]), ("getlocal", P), ("getproperty", m["x"]), ("ifne", "SCOND"),
        ("getlocal", D), ("getproperty", m["y"]), ("getlocal", P), ("getproperty", m["y"]), ("ifeq", "CCOND"),
        ("label", "SCOND"),
        ("getlocal", N2), ("iftrue", "SLOOP"),
        # 抽签：本 Battle 的 separative 种子 + uid + 坐标（不碰掉落/DSL 随机流，联机各副本一致）
        ("getlocal_0",), ("getproperty", m["gear"]), ("getlex", m["RSF"]), ("callproperty", m["absorb"], 1),
        ("coerce", m["RSF"]),
        ("getlocal", U), ("getlocal", P), ("getproperty", m["x"]), ("convert_i",), ("pushbyte", SEED_SHIFT), ("lshift",),
        ("getlocal", P), ("getproperty", m["y"]), ("convert_i",), ("bitxor",), ("add",), ("convert_i",),
        ("callproperty", m["createSep"], 1), ("callproperty", m["randomFloat"], 0),
        ("getlocal", KEYS), ("getproperty", m["length"]), ("multiply",), ("convert_i",), ("setlocal", I),
        ("getlocal", I), ("getlocal", KEYS), ("getproperty", m["length"]), ("iflt", "IOK"),
        ("pushbyte", 0), ("setlocal", I),
        ("label", "IOK"),
        ("findpropstrict", m["DII"]),
        ("pushstring", m["s_x"]), ("getlocal", P), ("getproperty", m["x"]),
        ("pushstring", m["s_y"]), ("getlocal", P), ("getproperty", m["y"]), ("newobject", 2),
        ("getlocal_0",), ("getproperty", m["gear"]), ("getlex", m["BQL"]), ("callproperty", m["absorb"], 1),
        ("coerce", m["BQL"]),
        *key_fever(m, KEYS, I), *push_int(abc, ITEM_LV), ("callproperty", m["BQL_resolveDII"], 2),
        ("getlocal", P), ("getproperty", m["rotationPanelAnimation"]),
        ("constructprop", m["DII"], 3), ("setlocal", D),
        ("getlocal_0",), ("getproperty", m["yakumonoes"]), ("getlocal", D), ("callpropvoid", m["list_add"], 1),
        ("getlocal_0",), ("getproperty", m["gear"]), ("getlocal", D), ("callpropvoid", m["addChild"], 1),
        ("label", "CCOND"),
        ("getlocal", N), ("iftrue", "CLOOP"),
        ("label", "END"),
    ]
    placed = [("SKIP", 27, _splice(body, 27, skip, {"SKIP": 29})),
              ("PRE", 11, _splice(body, 11, pre, {}))]
    body[2] = T4 + 1
    _fit_header(abc, body)
    return {"blocks": [{"id": i, "inserted_at_original": p, "block_len": n} for i, p, n in placed],
            "new_locals": list(range(3, T4 + 1))}


# ============================================================================================ B2
def b2_apply(abc, index, pool):
    body = abc.bodies[index]
    _require(body[1:5] == [2, 3, 1, 2] and not body[6] and not body[7], "deactivate header")
    code = _code(body)
    _require(len(code) == 28 and code[27].name == "returnvoid", "deactivate shape")
    _require(code[10].name == "jump" and code[10].target == 23 and code[11].name == "avm_label", "loop anchor")
    _require(code[21].name == "getlocal_2" and code[22].name == "callpropvoid"
             and abc.mn_name(code[22].args[0]) == "pinball.scene.battle.battle.zone.yakumono:Yakumono::deactivate"
             and code[22].args[1] == 0, "deactivate call anchor")
    m = names(abc)
    M, N, P, D, U = range(3, 8)
    skip = [("getlocal", M), ("iffalse", "DO"),
            *frag_fever_panel(m, [("getlocal_2",)], P, "DO"),
            ("getlocal", P), ("getproperty", m["state"]), ("getproperty", m["index"]),
            ("pushbyte", DASH_DEACTIVATED), ("ifne", "DO"),
            ("jump", "SKIP"),
            ("label", "DO")]
    pre = [*frag_marker(abc, m, "MK_", M, N, P, D, U, "END", "END"), ("label", "END")]
    placed = [("SKIP", 21, _splice(body, 21, skip, {"SKIP": 23})),
              ("PRE", 10, _splice(body, 10, pre, {}))]
    body[2] = U + 1
    _fit_header(abc, body)
    return {"blocks": [{"id": i, "inserted_at_original": p, "block_len": n} for i, p, n in placed],
            "new_locals": list(range(3, U + 1))}


def frag_preload(abc, m, push_asset, per_key, U, KEYS, I, T1, T2, T3, T4):
    return [
        *push_int(abc, MARKER_UID_BASE), ("setlocal", U),
        ("label", "ULOOP"), ("avm_label",),
        *frag_parse(abc, m, "PA_", push_asset, U, KEYS, T1, T2, T3, T4),
        ("pushbyte", 0), ("setlocal", I),
        ("jump", "KCOND"),
        ("label", "KLOOP"), ("avm_label",),
        *per_key,
        ("inclocal_i", I),
        ("label", "KCOND"),
        ("getlocal", I), ("getlocal", KEYS), ("getproperty", m["length"]), ("iflt", "KLOOP"),
        ("inclocal_i", U),
        ("getlocal", U), *push_int(abc, MARKER_UID_BASE + MARKER_SLOTS), ("iflt", "ULOOP"),
    ]


# ============================================================================================ B3
def b3_apply(abc, index, pool):
    body = abc.bodies[index]
    _require(body[1:5] == [2, 2, 1, 1] and not body[6] and not body[7], "resolvePathCollectionForDashPanel header")
    code = _code(body)
    _require(len(code) == 4 and code[0].name == "getlocal_1"
             and abc.s(code[1].args[0]) == "sound_effect/yakumono/se_dash_panel"
             and abc.mn_name(code[2].args[0]) == "pinball.asset.logic:IAssetPathCollectionBuilder::addSoundEffect"
             and code[3].name == "returnvoid", "resolvePathCollectionForDashPanel shape")
    m = names(abc)
    U, KEYS, I, T1, T2, T3, T4 = range(2, 9)
    per_key = [("getlocal_0",), *key_fever(m, KEYS, I), *push_int(abc, ITEM_LV), ("callproperty", m["resolveDII"], 2),
               ("getlocal_1",), ("callpropvoid", m["resolvePathCollection"], 1)]
    block = frag_preload(abc, m, [("getlocal_0",), ("getproperty", m["logicAssets"])], per_key,
                         U, KEYS, I, T1, T2, T3, T4)
    n = _splice(body, 3, block, {})
    body[2] = T4 + 1
    _fit_header(abc, body)
    return {"inserted_at": 3, "block_len": n, "new_locals": list(range(2, T4 + 1))}


# ============================================================================================ B4（v32h 撤掉）
# v32g 的 B4（TerrainHandler/readHandler 里读 UniqueConditionTable）真机进游戏即崩 ClientError 8013：
# LeadingLogicAssetCacheLoadingManager 把 master 和 terrain 放进同一个 MultiTask 并行读（LeadingLogicAssetCacheLoadingManager.as:62-85），
# 进游戏的全局预载里 terrain 先到时 unique_condition 主表还没加载。B4 也是多余的：B3 走
# DirectInstantItemSource.resolvePathCollection → ExecutableInstantItemSource.resolvePathCollection
# （addAnimationLayout(animation_path) + addActionDsl(program_path:元素)，ExecutableInstantItemSource.as），
# 与官方「敌人/可破坏物掉落道具」唯一的预载通路相同（ZoneSource.resolvePathCollection → InstantItemOdds.resolvePathCollection，
# 这类道具没有任何 TerrainHandler 预载），所以 B3 单独就保证道具动画和道具 DSL 在战斗前载入。

PATCHES = [
    {"id": "B1", "tag": MAIN, "label": "YakumonoManagerImpl/activate", "apply": b1_apply,
     "before": "28ed405103c6de85437f46916eb272a4f2731cde68e9a117ac8df5b1abd00ab5",
     "after": "a056544a701573b2922a8640a5be0175ec5403f82916863bf53e1084cd2726bb"},
    {"id": "B2", "tag": MAIN, "label": "YakumonoManagerImpl/deactivate", "apply": b2_apply,
     "before": "997dbf34a325f5142c5892bd15e458c9ca36f408a75b0bf0a6529f14e06e5309",
     "after": "be565848a5c9bccb1030b57a98799a4fde637418f8601d76009fc45aa3422e9b"},
    {"id": "B3", "tag": MAIN, "label": "BattleQuestBaseImpl/resolvePathCollectionForDashPanel", "apply": b3_apply,
     "before": "e3ccc6d9ff72f1cd35c336806e50ae75cbf499b607ec66795c86fec03d3747e6",
     "after": "684ea0eae0a906f5c2018f7e46a0853c8e9907b690e70c1eea980244afcbba5a"},
]
