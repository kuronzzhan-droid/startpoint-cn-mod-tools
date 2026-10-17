"""perf-v30 round 2 patch set (replayable). See perf2_core for the matching rules.

P1  MasterBinaryMap/getIndex                (round 1, re-expressed here so the set can replay onto v29-coop)
S1  cn.shop.ShopFirstOpen$/productIds       (helper ABC) group EventItemShop rows by reading only the two leading CSV
                                            fields of each not-yet-decoded row; any row that does not validate takes the
                                            original `table.get(key).event` path
S2  ShopTopScene/listCellEnabledResolver    restore the original grey-out of the event-item-exchange entry (v28 forced
                                            it to Enabled with `pushtrue; iftrue`) - only meaningful together with S1
"""
from __future__ import annotations

from common import asm
from perf2_core import Refused, mn_at, splice_with_exits

HELPER_SHOP = b"cn.shop.ShopFirstOpen"


# --------------------------------------------------------------------------------------------- P1 (round 1)
def p1_apply(abc, index, pool):
    import patch_perf
    got, meta = patch_perf.p1_master_index(abc)
    if got != index:
        raise Refused("P1 resolved a different body")
    meta.pop("old_code", None)
    return {"inserted_at": meta["inserted_at"], "block_len": meta["block_len"], "new_locals": meta["new_locals"]}


# --------------------------------------------------------------------------------------------- S1 productIds
def s1_apply(abc, index, pool):
    body = abc.bodies[index]
    if body[1:5] != [4, 12, 0, 1] or body[6] or body[7]:
        raise Refused("productIds header")
    code = asm.decode(body[5])
    # anchor: the original loop body  key=int(keys[i]); row=table.get(key); gk=eventKey(row.event); ...
    want = ["getlocal_1", "getlocal", "callproperty", "coerce", "setlocal", "findpropstrict", "getlocal", "getproperty",
            "callproperty", "coerce_s", "setlocal", "getlocal"]
    if [c.name for c in code[50:62]] != want or code[51].args != [7] or code[54].args != [8] or code[60].args != [9]:
        raise Refused("productIds anchor")
    m_get = mn_at(abc, body, 52, "callproperty", "get")
    m_map = mn_at(abc, body, 30, "getproperty", "map")
    m_len = mn_at(abc, body, 84, "getproperty", "length")
    mnl = code[47].args[0]
    if abc.multinames[mnl][0] != 0x1B:
        raise Refused("MultinameL donor")
    nsset = abc.multinames[m_get][2]
    m_push = mn_at(abc, body, 80, "callpropvoid", "http://adobe.com/AS3/2006/builtin::push")
    ns_builtin = abc.multinames[m_push][1]
    m_dict = pool.find("flash.utils::Dictionary")
    ns_flash_utils = abc.multinames[m_dict][1]
    m_hascache = pool.multiname_nsset("hasCache", nsset)
    m_getbyindex = pool.multiname_nsset("getByIndex", nsset)
    m_slice = pool.multiname_nsset("slice", nsset)
    m_stream = pool.multiname_nsset("stream", nsset)
    m_offset = pool.multiname_nsset("offset", nsset)
    m_position = pool.multiname_nsset("position", nsset)
    m_readbytes = pool.multiname_nsset("readBytes", nsset)
    m_uncompress = pool.multiname_nsset("uncompress", nsset)
    m_readutf = pool.multiname_nsset("readUTFBytes", nsset)
    builtin_split = pool.qname("split", ns_builtin)
    m_bytearray = pool.qname("ByteArray", ns_flash_utils)
    s_comma = pool.string(",")
    s_colon = pool.string(":")
    M, S, ST, BA, N, P, A, X, C, CC, I = 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22
    block = [
        # M = table.map; a row already decoded in the row cache keeps the original (cheap, cached) path
        ("getlocal_1",), ("getproperty", m_map), ("setlocal", M),
        ("getlocal", M), ("getlocal", 6), ("callproperty", m_hascache, 1), ("iftrue", "FALLBACK"),
        # S = table.map.getByIndex(i).slice  (MasterBinaryMap.getByIndex -> new MasterBinary(slice))
        ("getlocal", M), ("getlocal", 6), ("callproperty", m_getbyindex, 1), ("getproperty", m_slice), ("setlocal", S),
        ("getlocal", S), ("getproperty", m_len), ("convert_i",), ("pushbyte", 1), ("iflt", "FALLBACK"),
        # same bytes as MasterBinarySlice.getRow: stream.position = offset; readBytes(len); uncompress (zlib)
        ("getlocal", S), ("getproperty", m_stream), ("setlocal", ST),
        ("getlocal", ST), ("getlocal", S), ("getproperty", m_offset), ("setproperty", m_position),
        ("findpropstrict", m_bytearray), ("constructprop", m_bytearray, 0), ("setlocal", BA),
        ("getlocal", ST), ("getlocal", BA), ("pushbyte", 0), ("getlocal", S), ("getproperty", m_len),
        ("callpropvoid", m_readbytes, 3),
        ("getlocal", BA), ("callpropvoid", m_uncompress, 0),
        ("getlocal", BA), ("pushbyte", 0), ("setproperty", m_position),
        # I = byte index of the 2nd ',' within the first min(len, 32) bytes (byte scan, no decoding); none -> fallback
        ("getlocal", BA), ("getproperty", m_len), ("convert_i",), ("setlocal", N),
        ("getlocal", N), ("pushbyte", 32), ("ifle", "SHORT"),
        ("pushbyte", 32), ("setlocal", N),
        ("label", "SHORT"),
        ("pushbyte", 0), ("setlocal", CC),
        ("pushbyte", 0), ("setlocal", I),
        ("jump", "SCOND"),
        ("label", "SLOOP"), ("avm_label",),
        ("getlocal", BA), ("getlocal", I), ("getproperty", mnl), ("pushbyte", 44), ("ifne", "SNEXT"),
        ("inclocal_i", CC), ("getlocal", CC), ("pushbyte", 2), ("ifeq", "SFOUND"),
        ("label", "SNEXT"),
        ("inclocal_i", I),
        ("label", "SCOND"),
        ("getlocal", I), ("getlocal", N), ("iflt", "SLOOP"),
        ("jump", "FALLBACK"),
        # P = readUTFBytes(I).split(",")  - the cut is at an ASCII ',' so no UTF-8 sequence can be truncated
        ("label", "SFOUND"),
        ("getlocal", BA), ("getlocal", I), ("callproperty", m_readutf, 1), ("pushstring", s_comma),
        ("callproperty", builtin_split, 1), ("setlocal", P),
        ("getlocal", P), ("getproperty", m_len), ("pushbyte", 2), ("ifne", "FALLBACK"),
        # field0 must be the canonical decimal "0".."7" (EventItemShopValues: "k" -> EventItemShopKind index k)
        ("getlocal", P), ("pushbyte", 0), ("getproperty", mnl), ("convert_s",), ("setlocal", A),
        ("getlocal", A), ("convert_i",), ("setlocal", X),
        ("getlocal", X), ("convert_s",), ("getlocal", A), ("ifstrictne", "FALLBACK"),
        ("getlocal", X), ("pushbyte", 0), ("iflt", "FALLBACK"),
        ("getlocal", X), ("pushbyte", 7), ("ifgt", "FALLBACK"),
        # field1 must be a canonical int32 decimal (ctor: int(Std.parseInt(field1)))
        ("getlocal", P), ("pushbyte", 1), ("getproperty", mnl), ("convert_s",), ("setlocal", C),
        ("getlocal", C), ("convert_i",), ("convert_s",), ("getlocal", C), ("ifstrictne", "FALLBACK"),
        # gk = eventKey(event) == index + ":" + params[0]
        ("getlocal", A), ("pushstring", s_colon), ("add",), ("getlocal", C), ("convert_i",), ("convert_s",), ("add",),
        ("coerce_s",), ("setlocal", 9),
        ("jump", "GROUP"),
        ("label", "FALLBACK"),
    ]
    old_code = body[5]
    code_bytes, exc, merged, n = splice_with_exits(body, 50, block, {"GROUP": 61})
    if asm.unsplice(code_bytes, 50, n) != old_code:
        raise Refused("S1 inverse splice differs")
    body[1:5] = [5, 23, 0, 1]
    body[5], body[6] = code_bytes, exc
    return {"inserted_at": [[50, n, "forbid"]], "exits": {"GROUP": "original #61"},
            "new_locals": {"map": M, "slice": S, "stream": ST, "bytes": BA, "n": N, "parts": P, "f0": A, "f0i": X, "f1": C,
                           "commas": CC, "i": I}}


# --------------------------------------------------------------------------------------------- S2 entry grey-out
def s2_apply(abc, index, pool):
    body = abc.bodies[index]
    code = asm.decode(body[5])
    if [code[38].name, code[39].name, code[40].name, code[41].name] != ["pushtrue", "iftrue", "findproperty", "callproperty"] \
            or abc.mn_name(code[41].args[0]) != "existsExchangeableEvents" or code[39].target != 44:
        raise Refused("listCellEnabledResolver anchor")
    # v28 forced `pushtrue; iftrue -> Enabled`; make the constant false so the original existsExchangeableEvents decides.
    code[38] = asm.Instruction(asm.MNEMONICS["pushfalse"], ())
    body[5] = asm.encode(code)[0]
    return {"replaced": [[38, "pushtrue", "pushfalse"]]}


# --------------------------------------------------------------------------------------------- B1 battle start
def b1_apply(abc, index, pool):
    body = abc.bodies[index]
    code = asm.decode(body[5])
    seq = [(c.name, c.args) for c in code[135:142]]
    if seq[:3] != [("getlocal", [4]), ("pushbyte", [0]), ("ifne", [])] or code[137].target != 158 \
            or abc.s(code[141].args[0]) != "_status.log" or abc.mn_name(code[157].args[0]) != "saveFile":
        raise Refused("saveBattleRestore anchor")
    # `if (floor == 0) saveFile(dir, playId + "_status.log", JsonPacker.printWithInfo(LogicStatus, logic.logicStatus))`
    # -> the compared value becomes the constant 1, so the reflective dump of the whole LogicStatus is skipped.
    # Header log, its .txt checksum and the Initial snapshot stream (what battle restore reads) are untouched.
    code[135] = asm.Instruction(asm.MNEMONICS["pushbyte"], (1,))
    body[5] = asm.encode(code)[0]
    return {"replaced": [[135, "getlocal 4", "pushbyte 1"]]}


# --------------------------------------------------------------------------------------------- C1 party page flip
def c1_apply(abc, index, pool):
    from common import bodies
    body = abc.bodies[index]
    code = asm.decode(body[5])
    if body[1:5] != [8, 12, 1, 2] or body[6] or [c.name for c in code[27:34]] != [
            "findproperty", "getproperty", "getlocal", "callproperty", "coerce", "coerce", "setlocal"] \
            or code[29].args != [6] or code[33].args != [7] or abc.mn_name(code[30].args[0]) != "find" \
            or code[34].name != "newarray":
        raise Refused("getListCharactersInParties anchor")
    find_body = abc.bodies[bodies.resolve(abc, "CharacterListCachedRepository/find")]
    async_body = abc.bodies[bodies.resolve(abc, "CharacterListCachedRepository/findAsync")]
    m_repo_holder = mn_at(abc, body, 28, "getproperty", "characterListCachedRepository")
    m_prev_setting = mn_at(abc, find_body, 22, "getproperty", "previousFilterSetting")
    m_index = mn_at(abc, find_body, 26, "getproperty", "index")
    m_tools = mn_at(abc, find_body, 29, "getlex", "pinball.context.character::CharacterListSettingTools")
    m_params = mn_at(abc, find_body, 31, "getproperty", "params")
    m_prev_ids = mn_at(abc, find_body, 40, "getproperty", "previousCharacterIds")
    m_char_repo = mn_at(abc, find_body, 44, "getproperty", "characterRepository")
    m_get = mn_at(abc, find_body, 45, "getproperty", "get")
    m_equals = mn_at(abc, async_body, 40, "callproperty", "equals")
    m_contains = mn_at(abc, body, 53, "callproperty", "contains")
    m_length = mn_at(abc, body, 69, "getproperty", "length")
    m_push = mn_at(abc, body, 66, "callpropvoid", "http://adobe.com/AS3/2006/builtin::push")
    mnl = code[44].args[0]
    if abc.multinames[mnl][0] != 0x1B:
        raise Refused("MultinameL donor")
    R, O, IDS, G, OUT, K, ID = 12, 13, 14, 15, 16, 17, 18
    block = [
        # R = characterListCachedRepository; only when its cache was produced under the IDENTICAL list setting
        ("getlocal_0",), ("getproperty", m_repo_holder), ("setlocal", R),
        ("getlocal", R), ("getproperty", m_prev_setting), ("setlocal", O),
        ("getlocal", O), ("getproperty", m_index), ("pushbyte", 0), ("ifne", "FALLBACK"),
        ("getlex", m_tools), ("getlocal", O), ("getproperty", m_params), ("pushbyte", 0), ("getproperty", mnl),
        ("getlocal", 6), ("callproperty", m_equals, 2), ("iffalse", "FALLBACK"),
        ("getlocal", R), ("getproperty", m_prev_ids), ("setlocal", IDS),
        ("getlocal", IDS), ("getproperty", m_length), ("convert_i",), ("pushbyte", 1), ("iflt", "FALLBACK"),
        # build only the party members (original find would build all N and re-sort them, then this method
        # discards everything that is not in the two parties)
        ("getlocal", R), ("getproperty", m_char_repo), ("setlocal", G),
        ("newarray", 0), ("setlocal", OUT),
        ("pushbyte", 0), ("setlocal", K),
        ("jump", "COND"),
        ("label", "LOOP"), ("avm_label",),
        ("getlocal", IDS), ("getlocal", K), ("getproperty", mnl), ("convert_i",), ("setlocal", ID),
        ("inclocal_i", K),
        ("getlocal", 4), ("getlocal", ID), ("callproperty", m_contains, 1), ("iftrue", "TAKE"),
        ("getlocal", 5), ("getlocal", ID), ("callproperty", m_contains, 1), ("iffalse", "COND"),
        ("label", "TAKE"),
        ("getlocal", OUT), ("getlocal", G), ("getlocal", ID), ("callproperty", m_get, 1), ("callpropvoid", m_push, 1),
        ("label", "COND"),
        ("getlocal", K), ("getlocal", IDS), ("getproperty", m_length), ("convert_i",), ("iflt", "LOOP"),
        ("getlocal", OUT), ("setlocal", 7),
        ("jump", "FILTER"),
        ("label", "FALLBACK"),
    ]
    old_code = body[5]
    code_bytes, exc, merged, n = splice_with_exits(body, 27, block, {"FILTER": 34})
    if asm.unsplice(code_bytes, 27, n) != old_code:
        raise Refused("C1 inverse splice differs")
    body[1:5] = [8, 19, 1, 2]
    body[5], body[6] = code_bytes, exc
    return {"inserted_at": [[27, n, "forbid"]], "exits": {"FILTER": "original #34"},
            "new_locals": {"repo": R, "prevSetting": O, "ids": IDS, "charRepo": G, "out": OUT, "k": K, "id": ID}}


PATCHES = [
    {"id": "P1", "tag": b"boot_ffc6", "label": "MasterBinaryMap/getIndex",
     "before": "ec54f93d80b11c38480c43bb87966d0cf3ed05bf8bb3da7d47b0d11190517d1c",
     "after": "c0afa6d54379daa2b32406e40218f4f556b7569179fe39db5146f2b710f4cfbe", "apply": p1_apply},
    {"id": "S1", "tag": HELPER_SHOP, "label": "ShopFirstOpen$/productIds",
     "before": "3c3847b01d6f8f47869bfd44c58b62a27b0a0593b30dd72be50416000ef1d942",
     "after": "a7bdffc161992fc7829e8b467685a35db8bc3c4d998c569c5eee56185e4d8b2a", "apply": s1_apply},
    {"id": "S2", "tag": b"boot_ffc6", "label": "ShopTopScene/listCellEnabledResolver",
     "before": "7eb2dd7aedcb694baf3ba4247e63f62e06449d19f6c9cbf46cb4efd515bb2a52",
     "after": "4c1d46648cfb44800021200cdf2a52e3d477919380f0c475544103f888ee73f1", "apply": s2_apply},
    {"id": "B1", "tag": b"boot_ffc6", "label": "Restore/saveBattleRestore",
     "before": "58364a5b5296c8229931993183cd8fb405a5d5e3c21fecd396c811a228b64443",
     "after": "3dfc4482e515bf04da80ded65dab05ffda5a5c6e086a908b27b236f557d832fb", "apply": b1_apply},
    {"id": "C1", "tag": b"boot_ffc6", "label": "CharacterUseCaseBase/getListCharactersInParties",
     "before": "f604d50a4a392d8689867569b5543224328fd9addb45bd3a80e0095455ef6254",
     "after": "11161e17fbe198e02a7d2757ed4a72ecc37f65355895b5023da8af94c5f924d1", "apply": c1_apply},
]
