"""角色超限 Lv120 · APK 方法补丁（可重放，叠在 v30-perf2 之上；框架 = perf-v30 的 perf2_core）。

规则（与服务端 src/lib/character-overlimit.ts 一致）：
  超限角色 = ★5 且 character_status 最高键等级 ≥ 120（数据驱动，不写死角色 ID）
  超限模式 = ★5 且 overLimitStep ≥ 4（官方 ★5 突破已用完）
  超限结晶 = 突破结晶里 target_character_rarity == 5 且 is_allow_below_rarity == true（10003 是 false）

O1 GeneralCharacterLogic/get_maxOverLimitStep
     ★5：非超限角色 → 4；超限角色且 overLimitStep < 4 → 4；否则取表值（内置表改为 8）。非 ★5 不变。
O2 OwnedOverLimitLogic/getOwnAwakingCrystalToOverLimit   结晶候选：是超限结晶 ⇔ 处于超限模式
O3 OwnedOverLimitLogic/getAwakingCrystalToOverLimit      同上（突破窗口按钮列表）
O4 OwnedOverLimitLogic/getOverLimitState                 超限模式下不提供「用重复角色突破」
全部只用主 ABC 已有的常量池项（不追加），与 v29-coop / perf2 的 P1 S1 S2 B1 C1 不是同一方法。
"""
from __future__ import annotations

import sys

sys.path.insert(0, r"D:/WF/perf-v30-20261015/tools")
from common import asm  # noqa: E402
from perf2_core import MAIN, Refused, mn_at, splice_with_exits  # noqa: E402

RARITY = 5
RETAIL_STEPS = 4
EXT_STEPS = 8
EXT_LEVEL = 120


def _code(body):
    return asm.decode(body[5])


def _require(cond, what):
    if not cond:
        raise Refused(what)


# --------------------------------------------------------------------------------------------- O1
def o1_apply(abc, index, pool):
    body = abc.bodies[index]
    _require(body[1:5] == [1, 1, 1, 2] and not body[6] and not body[7], "get_maxOverLimitStep header")
    code = _code(body)
    _require([c.name for c in code] == ["getlocal_0", "pushscope", "findproperty", "getproperty", "callproperty",
                                        "convert_i", "returnvalue"], "get_maxOverLimitStep shape")
    m_level = mn_at(abc, body, 3, "getproperty", "levelLogic")
    m_getmax = mn_at(abc, body, 4, "callproperty", "getMaxOverLimitStep")
    m_rarity = pool.find("get_rarity", 0x07)
    m_base = pool.find("baseStatusLogic", 0x07)
    m_keys = pool.find("keyLevels", 0x07)
    m_len = pool.find("length", 0x07)
    m_step = pool.find("overLimitStep", 0x07)
    s_step = pool.string("overLimitStep")          # 已存在（字段名），不追加
    mnl = _index_multiname_l(abc)
    src = [
        ("getlocal_0",), ("pushscope",),
        ("findproperty", code[2].args[0]), ("getproperty", m_level), ("callproperty", m_getmax, 0), ("convert_i",),
        ("setlocal_1",),
        ("getlocal_0",), ("callproperty", m_rarity, 0), ("convert_i",), ("pushbyte", RARITY), ("ifne", "RET_N"),
        # 超限角色：character_status 最高键等级 ≥ 120
        ("getlocal_0",), ("getproperty", m_base), ("getproperty", m_keys), ("dup",), ("getproperty", m_len),
        ("convert_i",), ("pushbyte", 1), ("subtract",), ("getproperty", mnl), ("convert_i",),
        ("pushbyte", EXT_LEVEL), ("iflt", "RET_RETAIL"),
        # 带突破次数的实例（持有/战斗角色）：官方 4 次未用完时仍按 4 次显示
        ("pushstring", s_step), ("getlocal_0",), ("in",), ("iffalse", "RET_N"),
        ("getlocal_0",), ("getproperty", m_step), ("convert_i",), ("pushbyte", RETAIL_STEPS), ("iflt", "RET_RETAIL"),
        ("label", "RET_N"),
        ("getlocal_1",), ("returnvalue",),
        ("label", "RET_RETAIL"),
        ("pushbyte", RETAIL_STEPS), ("returnvalue",),
    ]
    new, _ = asm.encode(asm.assemble(src))
    body[1:5] = [3, 2, 1, 2]
    body[5] = new
    return {"replaced": "whole body", "new_len": len(new)}


def _index_multiname_l(abc):
    """数组下标用的 MultinameL（kind 0x1B）：取 CharacterBaseStatusLogic/getParameterAt 里读 keyLevels[i] 的同一个。"""
    from common import bodies
    donor = abc.bodies[bodies.resolve(abc, "CharacterBaseStatusLogic/getParameterAt")]
    hits = {c.args[0] for c in asm.decode(donor[5])
            if c.name == "getproperty" and abc.multinames[c.args[0]][0] == 0x1B}
    if len(hits) != 1:
        raise Refused(f"MultinameL donor ambiguous: {hits}")
    return hits.pop()


# --------------------------------------------------------------------------------------------- O2/O3 结晶过滤
def _mode_and_ext_block(abc, pool, rarity_local, target_local, allow_local, mode_local, ext_local):
    m_char = pool.find("character", 0x07)
    m_step = pool.find("overLimitStep", 0x07)
    return [
        ("getlocal", rarity_local), ("pushbyte", RARITY), ("ifne", "M_FALSE"),
        ("findproperty", m_char), ("getproperty", m_char), ("getproperty", m_step), ("convert_i",),
        ("pushbyte", RETAIL_STEPS), ("iflt", "M_FALSE"),
        ("pushtrue",), ("setlocal", mode_local), ("jump", "M_DONE"),
        ("label", "M_FALSE"), ("pushfalse",), ("setlocal", mode_local),
        ("label", "M_DONE"),
        ("getlocal", target_local), ("pushbyte", RARITY), ("ifne", "E_FALSE"),
        ("getlocal", allow_local), ("iffalse", "E_FALSE"),
        ("pushtrue",), ("setlocal", ext_local), ("jump", "E_DONE"),
        ("label", "E_FALSE"), ("pushfalse",), ("setlocal", ext_local),
        ("label", "E_DONE"),
        ("getlocal", mode_local), ("getlocal", ext_local), ("ifstrictne", "SKIP"),
    ]


def _crystal_filter(abc, index, pool, *, header, push_at, skip_to, rarity_local, target_local, allow_local,
                    target_at, allow_at):
    body = abc.bodies[index]
    _require(body[1:5] == header and not body[6] and not body[7], "crystal header")
    code = _code(body)
    _require(code[target_at].name == "getproperty" and abc.mn_name(code[target_at].args[0]) == "target_character_rarity",
             "target anchor")
    _require(code[allow_at].name == "getproperty" and abc.mn_name(code[allow_at].args[0]) == "is_allow_below_rarity",
             "allow anchor")
    _require(code[push_at + 2].name == "callpropvoid" and abc.mn_name(code[push_at + 2].args[0]).endswith("::push"),
             "push anchor")
    _require(code[push_at - 1].name == "iffalse" and code[push_at - 1].target == skip_to, "condition anchor")
    _require(code[skip_to].name == "jump", "skip anchor")
    mode_local, ext_local = header[1], header[1] + 1
    block = _mode_and_ext_block(abc, pool, rarity_local, target_local, allow_local, mode_local, ext_local)
    old = body[5]
    new, exc, _merged, n = splice_with_exits(body, push_at, block, {"SKIP": skip_to})
    _require(asm.unsplice(new, push_at, n) == old, "inverse splice differs")
    body[1:5] = [max(header[0], 2), header[1] + 2, header[2], header[3]]
    body[5], body[6] = new, exc
    return {"inserted_at": push_at, "block_len": n, "new_locals": [mode_local, ext_local]}


def o2_apply(abc, index, pool):
    return _crystal_filter(abc, index, pool, header=[3, 10, 1, 2], push_at=86, skip_to=89,
                           rarity_local=2, target_local=8, allow_local=9, target_at=62, allow_at=67)


def o3_apply(abc, index, pool):
    return _crystal_filter(abc, index, pool, header=[3, 11, 1, 2], push_at=97, skip_to=100,
                           rarity_local=1, target_local=9, allow_local=10, target_at=73, allow_at=78)


# --------------------------------------------------------------------------------------------- O4 重复角色
def o4_apply(abc, index, pool):
    body = abc.bodies[index]
    _require(body[1:5] == [3, 12, 1, 2] and not body[6] and not body[7], "getOverLimitState header")
    code = _code(body)
    _require([c.name for c in code[24:32]] == ["findproperty", "getproperty", "callproperty", "convert_i", "pushbyte",
                                               "greaterthan", "convert_b", "setlocal"] and code[31].args == [4],
             "stack anchor")
    _require(abc.mn_name(code[26].args[0]) == "get_stack", "get_stack anchor")
    m_char = pool.find("character", 0x07)
    m_rarity = pool.find("get_rarity", 0x07)
    m_step = pool.find("overLimitStep", 0x07)
    block = [
        ("getlocal", 4), ("iffalse", "DONE"),
        ("findproperty", m_char), ("getproperty", m_char), ("callproperty", m_rarity, 0), ("convert_i",),
        ("pushbyte", RARITY), ("ifne", "DONE"),
        ("findproperty", m_char), ("getproperty", m_char), ("getproperty", m_step), ("convert_i",),
        ("pushbyte", RETAIL_STEPS), ("iflt", "DONE"),
        ("pushfalse",), ("setlocal", 4),
        ("label", "DONE"),
    ]
    old = body[5]
    new, exc, _merged, n = splice_with_exits(body, 32, block, {})
    _require(asm.unsplice(new, 32, n) == old, "inverse splice differs")
    body[5], body[6] = new, exc
    return {"inserted_at": 32, "block_len": n}



# --------------------------------------------------------------------------------------------- O5 双道具（悖论之核）
PARADOX_CORE = (10000, 1000, 302)   # 10000*1000+302 = 10000302；主 ABC 不追加 int 常量，运行时算


def o5_apply(abc, index, pool):
    """超限模式下可突破次数 = min(超限结晶持有数, 悖论之核持有数, 剩余次数)。"""
    body = abc.bodies[index]
    _require(body[1:5] == [2, 5, 1, 2] and not body[6] and not body[7], "getPossibleOverLimitCountByItem header")
    code = _code(body)
    _require(code[17].name == "setlocal_3" and code[18].name == "findproperty"
             and abc.mn_name(code[18].args[0]) == "getRestOverLimitStep", "count anchor")
    m_items = mn_at(abc, body, 14, "callproperty", "getItemNumber")
    m_rarity = pool.find("get_rarity", 0x07)
    m_step = pool.find("overLimitStep", 0x07)
    a, b, c = PARADOX_CORE
    block = [
        ("getlocal_0",), ("callproperty", m_rarity, 0), ("convert_i",), ("pushbyte", RARITY), ("ifne", "DONE"),
        ("getlocal_0",), ("getproperty", m_step), ("convert_i",), ("pushbyte", RETAIL_STEPS), ("iflt", "DONE"),
        ("getlocal_1",), ("pushshort", a), ("pushshort", b), ("multiply",), ("pushshort", c), ("add",), ("convert_i",),
        ("callproperty", m_items, 1), ("convert_i",), ("setlocal", 5),
        ("getlocal", 5), ("getlocal_3",), ("ifnlt", "DONE"),
        ("getlocal", 5), ("setlocal_3",),
        ("label", "DONE"),
    ]
    old = body[5]
    new, exc, _merged, n = splice_with_exits(body, 18, block, {})
    _require(asm.unsplice(new, 18, n) == old, "inverse splice differs")
    body[1:5] = [3, 6, 1, 2]
    body[5], body[6] = new, exc
    return {"inserted_at": 18, "block_len": n}

PATCHES = [
    {"id": "O1", "tag": MAIN, "label": "GeneralCharacterLogic/get_maxOverLimitStep", "apply": o1_apply,
     "before": "3ffa287364fb8098635d7127b0dc3d66234cafbb658b4bed2b33fc355053a6ca",
     "after": "a1b57b4034b60def3d9b1a328b7ceb321157f45e5243c246353d733a7643ebab"},
    {"id": "O2", "tag": MAIN, "label": "OwnedOverLimitLogic/getOwnAwakingCrystalToOverLimit", "apply": o2_apply,
     "before": "e492781cdd1f0c121eb996d1c5ff69735f0912b2a2d4bad1f7c038e5cffc245f",
     "after": "2be9af1fa92ed8bb56a5ee90b9eb511f7f94c6941f38a223e406207e17be61b2"},
    {"id": "O3", "tag": MAIN, "label": "OwnedOverLimitLogic/getAwakingCrystalToOverLimit", "apply": o3_apply,
     "before": "6ff7cce512d71facbd7acf7aeef5a234bd5c70d8e3531d31369381f1a58b77ad",
     "after": "2e584914a2f67e60a268e62502f8e7af84a6a6e1e38af444b8de79c446470b34"},
    {"id": "O4", "tag": MAIN, "label": "OwnedOverLimitLogic/getOverLimitState", "apply": o4_apply,
     "before": "27f4d717747a8c567a3b1e8690c8a499a3811173489d222f8aff2db1a3b7a546",
     "after": "98f9c7121ac212729daaf7a0e9b740e2de275dcc26e2536ad4d8e1d63d023fd0"},
    {"id": "O5", "tag": MAIN, "label": "OwnedCharacterLogic/getPossibleOverLimitCountByItem", "apply": o5_apply,
     "before": "2dc44da607ffab595b1c44f2c257587ea699294f1636847cbee7ab33677a7991",
     "after": "7fa65be8a2181e01a0a17b400d74fecbd0565c2600be4e78a7be8d96a94e837e"},
]


# --------------------------------------------------------------------------------------------- O6/O7 超限台座
def _pedestal_apply(abc, index, pool, resolver_method):
    """★5 台座两档（bundle.zip 台座图集已追加 _6/_7 帧）：
    超限（第 5 次突破起）→ <color>_6[_half]；突破 8 次、Lv120 且第一张盘全部觉醒 → <color>_7[_half]。"""
    body = abc.bodies[index]
    _require(body[1:5] == [2, 1, 1, 2] and not body[6] and not body[7], "pedestal getter header")
    code = _code(body)
    _require([c.name for c in code] == ["getlocal_0", "pushscope", "getlex", "getlocal_0", "callproperty", "coerce",
                                        "returnvalue"], "pedestal getter shape")
    _require(abc.mn_name(code[4].args[0]) == resolver_method, "resolver anchor")
    m_rarity = pool.find("get_rarity", 0x07)
    m_step = pool.find("overLimitStep", 0x07)
    s_step = pool.string("overLimitStep")
    m_split = pool.find("http://adobe.com/AS3/2006/builtin::split", 0x07)
    m_join = pool.find("http://adobe.com/AS3/2006/builtin::join", 0x07)
    m_level = pool.find("get_level", 0x07)
    m_awaked = pool.find("hasAwakedAllManaNodeOfManaBoard", 0x07)
    src = [
        ("getlocal_0",), ("pushscope",),
        ("getlex", code[2].args[0]), ("getlocal_0",), ("callproperty", code[4].args[0], 1), ("coerce", code[5].args[0]),
        ("setlocal_1",),
        ("getlocal_0",), ("callproperty", m_rarity, 0), ("convert_i",), ("pushbyte", RARITY), ("ifne", "RET"),
        ("pushstring", s_step), ("getlocal_0",), ("in",), ("iffalse", "RET"),
        ("getlocal_0",), ("getproperty", m_step), ("convert_i",), ("pushbyte", RETAIL_STEPS), ("ifle", "RET"),
        ("pushbyte", RARITY + 1), ("setlocal_2",),
        ("getlocal_0",), ("getproperty", m_step), ("convert_i",), ("pushbyte", EXT_STEPS), ("iflt", "SWAP"),
        ("getlocal_0",), ("callproperty", m_level, 0), ("convert_i",), ("pushbyte", EXT_LEVEL), ("iflt", "SWAP"),
        ("getlocal_0",), ("pushbyte", 1), ("callproperty", m_awaked, 1), ("iffalse", "SWAP"),
        ("pushbyte", RARITY + 2), ("setlocal_2",),
        ("label", "SWAP"),
        ("getlocal_1",), ("pushbyte", RARITY), ("convert_s",), ("callproperty", m_split, 1),
        ("getlocal_2",), ("convert_s",), ("callproperty", m_join, 1), ("coerce", code[5].args[0]),
        ("setlocal_1",),
        ("label", "RET"),
        ("getlocal_1",), ("returnvalue",),
    ]
    new, _ = asm.encode(asm.assemble(src))
    body[1:5] = [3, 3, 1, 2]
    body[5] = new
    return {"replaced": "whole body", "new_len": len(new)}


def o6_apply(abc, index, pool):
    return _pedestal_apply(abc, index, pool, "resolveFull")


def o7_apply(abc, index, pool):
    return _pedestal_apply(abc, index, pool, "resolveHalf")


PATCHES += [
    {"id": "O6", "tag": MAIN, "label": "GeneralCharacterLogic/getPedestalImagePath", "apply": o6_apply,
     "before": "9713b7437a4eddaf978f704d4b6721ca65a63f6d24138b05817c32b97cbe9ce2",
     "after": "1c5905b65f624a24c01cf58adeeb90c300a9e9ae965577c4b295c093f0be117d"},
    {"id": "O7", "tag": MAIN, "label": "GeneralCharacterLogic/getHalfPedestalImagePath", "apply": o7_apply,
     "before": "3c050c660a915c1f8c18f16f2fad519ffba84f42d6661c86fcaa64f9af9b16bd",
     "after": "0dc8e515702c2c3c77cca60549da8e063eec0785f89a57e503b5ddf41be6a28a"},
]
