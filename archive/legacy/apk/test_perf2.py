"""Offline self-tests for the round-2 patch set (perf2_patches): readback, replay/refusal, instruction assertions,
stack/scope/locals, and execution of the REAL original vs patched bytecode in avm_mini against emulated objects."""
from __future__ import annotations

import json
import random
import zlib

import avm_mini as vm
from avm_mini import UNDEF, Dictionary, Env, run
from common import ABC, ROOT, abc_tags, asm, bodies, freeze, read_base_swf, sha
from patch_perf import COOP_AFTER_SHA, COOP_LABEL
from perf2_core import Refused, apply_patches, check_body
from perf2_patches import HELPER_SHOP, PATCHES

ROUND1 = ROOT / "work" / "build" / "patched.swf"
ROUND1_SHA = "1bc0ef24fbbc4d8adeb255f82f2befff6bf7d2fcf7c3a1547fb69031ba6a89f5"
A = {"n": 0}


def ok(cond, what):
    if not cond:
        raise AssertionError(what)
    A["n"] += 1


class M:
    """Generic stand-in object: attributes and callables given as keyword arguments."""

    def __init__(self, **kw):
        self.__dict__.update(kw)


def tags_of(swf):
    return {name: raw for name, *_r, raw in abc_tags(swf)}


def body_of(abc, label):
    return abc.bodies[bodies.resolve(abc, label)]


# ------------------------------------------------------------------------------------------- S1 productIds
class ByteArray:
    def __init__(self):
        self.data, self.position, self.utf_reads = bytearray(), 0, []

    @property
    def length(self):
        return len(self.data)

    def uncompress(self):
        self.data = bytearray(zlib.decompress(bytes(self.data)))
        self.position = 0

    def mnl_get(self, i):
        i = i if isinstance(i, int) and not isinstance(i, bool) else None
        return self.data[i] if i is not None and 0 <= i < len(self.data) else UNDEF

    def readUTFBytes(self, n):
        # strict: a truncated multi-byte sequence would raise here, proving the patch never cuts one
        n = vm.to_int(n)
        raw = bytes(self.data[self.position:self.position + n])
        self.position += n
        self.utf_reads.append(n)
        return raw.decode("utf-8").split("\x00")[0]


class Stream:
    """Shared master file stream (FileStream/ByteArray stand-in)."""

    def __init__(self):
        self.data, self.position, self.reads = bytearray(), 0, 0

    def readBytes(self, target, offset, length):
        length = vm.to_int(length)
        assert length > 0, "length 0 would read everything"
        chunk = self.data[self.position:self.position + length]
        self.position += length
        target.data[vm.to_int(offset):vm.to_int(offset) + len(chunk)] = chunk
        self.reads += 1


def js_parse_int(s):
    s = s.lstrip(" \t\n\r")
    sign = 1
    if s and s[0] in "+-":
        sign = -1 if s[0] == "-" else 1
        s = s[1:]
    if s[:2].lower() == "0x":
        digits = ""
        for ch in s[2:]:
            if ch.lower() in "0123456789abcdef":
                digits += ch
            else:
                break
        return sign * int(digits, 16) if digits else None
    digits = ""
    for ch in s:
        if ch.isdigit() and ch.isascii():
            digits += ch
        else:
            break
    return sign * int(digits) if digits else None


def csv_first_row(text):
    """format.csv.Reader semantics for the leading fields of one row (quotes, "" escapes, CR/LF)."""
    fields, cur, i, quoted = [], "", 0, False
    while i < len(text):
        ch = text[i]
        if quoted:
            if ch == '"':
                if i + 1 < len(text) and text[i + 1] == '"':
                    cur += '"'
                    i += 2
                    continue
                quoted = False
            else:
                cur += ch
        elif ch == '"' and cur == "":
            quoted = True
        elif ch == ",":
            fields.append(cur)
            cur = ""
        elif ch in "\r\n":
            break
        else:
            cur += ch
        i += 1
    fields.append(cur)
    return fields


class Kind:
    def __init__(self, index, param):
        self.index, self.params = index, [param]


class Table:
    """MasterIntMap stand-in: keys(), get(key) (decodes row, fills row cache), map: MasterBinaryMap stand-in."""

    def __init__(self, rows, cached=()):
        self.stream = Stream()
        self._keys, self.slices, self.cache, self.decodes = [], [], {}, 0
        for key, text in rows:
            comp = zlib.compress(text.encode("utf-8"))
            self.slices.append(M(stream=self.stream, offset=len(self.stream.data), length=len(comp)))
            self.stream.data += comp
            self._keys.append(key)
        self.map = M(hasCache=lambda i: vm.to_int(i) in self.cache,
                     getByIndex=lambda i: M(slice=self.slices[vm.to_int(i)]))
        for i in cached:
            self.cache[i] = self.decode(i)

    def keys(self):
        return self._keys

    def decode(self, i):
        self.decodes += 1
        s = self.slices[i]
        self.stream.position = s.offset
        row = csv_first_row(zlib.decompress(bytes(self.stream.data[s.offset:s.offset + s.length])).decode("utf-8"))
        if row[0] not in [str(k) for k in range(8)]:
            raise vm.Thrown("7050")
        p = js_parse_int(row[1]) if len(row) > 1 else None
        param = vm.to_int(p) if p is not None else 0   # int(Std.parseInt(null)) == 0
        return M(event=Kind(int(row[0]), param))

    def get(self, key):
        i = self._keys.index(key)
        if i not in self.cache:
            self.cache[i] = self.decode(i)
        return self.cache[i]


class ShopEnv(Env):
    def __init__(self, abc, helper_abc, eventkey_body):
        super().__init__(abc)
        self.by_table = Dictionary()
        self.eventkey_body = eventkey_body

    def lex(self, name):
        if name.endswith("::byTable"):
            return self.by_table
        if name == "Array":
            return "Array"
        raise AssertionError(name)

    def findprop(self, name, this):
        if name.endswith("::eventKey") or name == "flash.utils::ByteArray":
            return this
        raise AssertionError(name)

    def call(self, obj, name, args):
        if name.endswith("::eventKey"):
            return run(self.abc, self.eventkey_body, self, None, args)
        if name == "get" and isinstance(obj, Table):
            return obj.get(args[0])
        if name == "keys":
            return obj.keys()
        return super().call(obj, name, args)

    def construct(self, name, args):
        assert name == "flash.utils::ByteArray" and not args
        return ByteArray()

    def set(self, obj, name, value):
        setattr(obj, name, value)


def s1_rows(rnd):
    rows, key = [], 1
    # every row here is one the ORIGINAL decoder accepts (field0 parses to exactly "0".."7"); rows it rejects are
    # covered separately below. Several are crafted so the fast path must decline and fall back.
    weird = ['"1",5,x', "1,\"5\",x", "1, 5,x", "1,05,x", "1,+5,x", "1,0x1f,x", "1,1e3,x",
             "1,5", "1,5\n,x", "1,,x", "1,abc,x", "1,99999999999,x", "1,-7,x", "1,-0,x",
             "1,2147483647,x", "1,2147483648,x", "7,5,x", "0,0,x", "1,5,中文字符" * 3,
             "1,123456789012345678901234567890,x", '"7","9",x', "3,12345678901234567890123,x",
             "2,中,x", "1,5x,y", "1,5 ,y", "0,1001,(None),(None),(None),(None),中文名称",
             "1,5中,x", "1,77,中中中中中中中中中",
             "1,12345678901234567890123456789012345,x", "4,9," + "é" * 20]
    for text in weird:
        rows.append((key, text))
        key += 1
    for _ in range(1500):
        ev = rnd.randrange(8)
        eid = rnd.choice([1, 2, 3, 40, 41, 1001, 20231, 9700])
        tail = ",".join(rnd.choice(["(None)", "abc", "活动奖励", "12", '"q,uoted"']) for _ in range(12))
        rows.append((rnd.randrange(10 ** 7), f"{ev},{eid},{tail}"))
    keys = set()
    out = []
    for k, t in rows:
        while k in keys:
            k += 1
        keys.add(k)
        out.append((k, t))
    return out


def s1_test(old_helper, new_helper):
    rnd = random.Random(20261015)
    ob, nb = body_of(old_helper, "ShopFirstOpen$/productIds"), body_of(new_helper, "ShopFirstOpen$/productIds")
    ek_old, ek_new = body_of(old_helper, "ShopFirstOpen$/eventKey"), body_of(new_helper, "ShopFirstOpen$/eventKey")
    rows = s1_rows(rnd)
    cases = 0
    stats = {}
    for cached in ((), (0, 1, 5, 30, 31, 32), tuple(range(0, len(rows), 7))):
        t_old, t_new = Table(rows, cached), Table(rows, cached)
        base_old, base_new = t_old.decodes, t_new.decodes
        e_old, e_new = ShopEnv(old_helper, old_helper, ek_old), ShopEnv(new_helper, new_helper, ek_new)
        probes = [Kind(i, p) for i in range(8) for p in (0, 1, 2, 3, 5, 40, 41, 1001, 20231, 9700, -7, 2147483647,
                                                          -2147483648, 123456789)]
        for probe in probes * 2:
            def call(env, abc, body, table):
                try:
                    return run(abc, body, env, None, [table.__dict__["_self"] if False else table_map(table), probe])
                except vm.Thrown as error:
                    return ("throw", error.args[0])
            # productIds(table: MasterMap, kind) -> the table object itself is the MasterMap stand-in
            a = run_pid(old_helper, ob, e_old, t_old, probe)
            b = run_pid(new_helper, nb, e_new, t_new, probe)
            ok(a == b, f"S1 groups differ for {probe.index}:{probe.params[0]} cached={len(cached)}: {a[:5]} vs {b[:5]}")
            cases += 1
        stats[f"cached_{len(cached)}"] = {"rows": len(rows), "original_row_decodes": t_old.decodes - base_old,
                                          "patched_row_decodes": t_new.decodes - base_new,
                                          "patched_fast_reads": t_new.stream.reads}
    # rows the original cannot decode (bad kind) must still throw identically on both sides
    bad = [(1, "1,5,x"), (2, "9,5,x"), (3, "2,7,x")]
    for env_abc, body, ek in ((old_helper, ob, ek_old), (new_helper, nb, ek_new)):
        try:
            run_pid(env_abc, body, ShopEnv(env_abc, env_abc, ek), Table(bad), Kind(1, 5))
            raise AssertionError("bad row accepted")
        except vm.Thrown as error:
            ok(error.args[0] == "7050", "S1 bad row error")
    # empty table
    for env_abc, body, ek in ((old_helper, ob, ek_old), (new_helper, nb, ek_new)):
        ok(run_pid(env_abc, body, ShopEnv(env_abc, env_abc, ek), Table([]), Kind(1, 5)) == [], "S1 empty")
    return cases, stats


def table_map(t):
    return t


def run_pid(abc, body, env, table, kind):
    return list(run(abc, body, env, None, [table, kind]))


# ------------------------------------------------------------------------------------------- S2 entry grey-out
class CellEnv(Env):
    def __init__(self, abc, flags):
        super().__init__(abc)
        self.flags = flags

    def lex(self, name):
        if name == "pinball.ui.component.list.core.cell::CellEnabledState":
            return M(Enabled="Enabled", DisabledVisual="DisabledVisual")
        raise AssertionError(name)

    def findprop(self, name, this):
        return this

    def call(self, obj, name, args):
        if name == "isGameSystemUnlocked":
            return self.flags["unlocked"]
        if name in ("existsExchangeableEvents", "existsSpecialPackProducts"):
            self.bump(name)
            return self.flags[name]
        raise AssertionError(name)


def s2_test(old, new):
    ob, nb = body_of(old, "ShopTopScene/listCellEnabledResolver"), body_of(new, "ShopTopScene/listCellEnabledResolver")
    cases = 0
    for kind in range(12):
        for exch in (True, False):
            for special in (True, False):
                for unlocked in (True, False):
                    flags = {"existsExchangeableEvents": exch, "existsSpecialPackProducts": special, "unlocked": unlocked}
                    this = M(globalLogic=M())
                    e_old, e_new = CellEnv(old, flags), CellEnv(new, flags)
                    item = M(kind=M(index=kind))
                    a, b = run(old, ob, e_old, this, [item]), run(new, nb, e_new, this, [item])
                    if kind == 3:
                        ok(a == "Enabled", "v29 forced Enabled")
                        ok(b == ("Enabled" if exch else "DisabledVisual"), "S2 grey-out")
                        ok(e_new.counts.get("existsExchangeableEvents") == 1, "S2 asks once")
                    else:
                        ok(a == b, f"S2 other kind {kind} changed")
                    cases += 1
    return cases


# ------------------------------------------------------------------------------------------- B1 saveBattleRestore
class RestoreEnv(Env):
    def __init__(self, abc, log):
        super().__init__(abc)
        self.log = log

    def lex(self, name):
        table = {
            "pinball.common.data.quest.id::BattleGroupKind": M(SingleOrRaid="SingleOrRaid"),
            "pinball.common.data.quest.id::MultiBattleIdKindTools": M(getBattleGroupKind=lambda k: "Multi:" + k),
            "pinball.context.restore::Restore": M(get_jsonPacker=lambda: M(
                printWithInfo=lambda t, v: f"JSON<{t}>({getattr(v, 'tag', v)})")),
            "typepacker.core::TypePacker": M(resolveType=lambda s: s),
            "haxe.crypto::Sha1": M(encode=lambda s: "sha1(" + s + ")"),
            "pinball.scene.battle.restore::BattleRestore": M(startWriteFileStream=self.stream),
            "pinball.common.data.battle.restore::BattleSnapshotKind": M(Initial="Initial"),
        }
        return table[name]

    def stream(self, d, play, floor, kind):
        self.log.append(("stream", d, play, floor, kind))
        return M(close=lambda: self.log.append(("close",)))

    def findprop(self, name, this):
        return this

    def call(self, obj, name, args):
        if name == "toFixed":
            return str(int(round(obj)))
        return super().call(obj, name, args)


def b1_test(old, new):
    ob, nb = body_of(old, "Restore/saveBattleRestore"), body_of(new, "Restore/saveBattleRestore")
    cases = 0
    for index in (0, 1):
        for floor in (0, 1, 3):
            for repro in (False, True):
                logs = []
                for abc, body in ((old, ob), (new, nb)):
                    log = []
                    this = M(saveFile=lambda d, n, c, log=log: log.append(("save", d, n, c)),
                             getBattleDirectory=lambda k: "dir(" + k + ")",
                             get_reproducePlaying=lambda repro=repro: repro, get_udid=lambda: "U",
                             get_viewerId=lambda: 123.0, logic=M(logicStatus=M(tag="STATUS")))
                    scene = M(playId="P", getFloor=lambda floor=floor: floor, getMultiBattleIdKind=lambda: "K")
                    header = M(index=index, params=[scene], tag="HDR")
                    ok(run(abc, body, RestoreEnv(abc, log), this, [header]) is UNDEF, "B1 returns void")
                    logs.append(log)
                status = [x for x in logs[0] if x[0] == "save" and x[2].endswith("_status.log")]
                ok(len(status) == (1 if floor == 0 else 0), "original writes status only on floor 0")
                ok([x for x in logs[0] if x not in status] == logs[1], "B1: everything except _status.log identical")
                ok(not any(x[0] == "save" and x[2].endswith("_status.log") for x in logs[1]), "B1 no status log")
                cases += 1
    return cases


# ------------------------------------------------------------------------------------------- C1 party flip
class Logic:
    def __init__(self, cid, stat):
        self.id, self.stat = cid, stat


class Party:
    def __init__(self, members):
        self.members = set(members)

    def contains(self, cid):
        return vm.to_int(cid) in self.members


class Option:
    def __init__(self, value=None, some=True):
        self.index, self.params = (0, [value]) if some else (1, [])


class CharEnv(Env):
    def __init__(self, abc, world):
        super().__init__(abc)
        self.w = world

    def lex(self, name):
        if name == "pinball.context.character::CharacterListSettingTools":
            return M(equals=lambda a, b: self.w["equals"](a, b))
        raise AssertionError(name)

    def findprop(self, name, this):
        return this

    def call(self, obj, name, args):
        if name == "pinball.common.data.party:PartyHolder::getParty":
            return self.w["parties"][vm.to_int(args[0])]
        if name == "charactersToInventoryData":
            self.w["translated"].append([c.id for c in args[3]])
            return ["DATA"] + [c.id for c in args[3]]
        return super().call(obj, name, args)


def c1_world(rnd, n, prev_some, eq, empty_ids):
    stats = {i: rnd.randrange(1000) for i in range(1, n + 1)}
    counts = {"get": 0, "find": 0}

    def get(cid):
        counts["get"] += 1
        return Logic(vm.to_int(cid), stats[vm.to_int(cid)])

    ids = [] if empty_ids else sorted(stats, key=lambda c: (stats[c], c))
    repo = M(previousFilterSetting=Option("SETTING_PREV", prev_some), previousCharacterIds=list(ids),
             characterRepository=M(get=get))

    def find(setting):
        # CharacterListCachedRepository.find stand-in: (cache hit or full) build N logics, re-sort, setPrevious
        counts["find"] += 1
        source = repo.previousCharacterIds if (prev_some and repo.previousCharacterIds) else list(stats)
        out = [get(c) for c in source]
        out.sort(key=lambda o: (-o.stat, o.id))
        repo.previousCharacterIds = [o.id for o in out]
        repo.previousFilterSetting = Option(setting)
        return out

    repo.find = find
    members = rnd.sample(range(1, n + 1), min(n, 6)) + [n + 50]
    parties = {1: Party(members[:3]), 2: Party(members[3:])}
    world = {"parties": parties, "translated": [], "equals": lambda a, b: eq}
    return world, repo, counts


def c1_test(old, new):
    rnd = random.Random(7)
    ob = body_of(old, "CharacterUseCaseBase/getListCharactersInParties")
    nb = body_of(new, "CharacterUseCaseBase/getListCharactersInParties")
    cases, probe = 0, {}
    for n in (0, 1, 5, 40, 500):
        for prev_some in (True, False):
            for eq in (True, False):
                for empty_ids in (False, True):
                    results = []
                    for abc, body in ((old, ob), (new, nb)):
                        world, repo, counts = c1_world(random.Random(n * 7 + prev_some * 3 + eq), n, prev_some, eq, empty_ids)
                        this = M(partyGroupHolder=M(), globalLogic=M(getMiscData=lambda: M(
                            getCharacterListSetting=lambda: "SETTING")), characterListCachedRepository=repo,
                                 characterTranslator=M(), player="PLAYER", resolveBadgeReasonFromState=lambda s: "BADGE")
                        out = run(abc, body, CharEnv(abc, world), this, ["STATE", 1, 2])
                        results.append((out, world["translated"], dict(counts), list(repo.previousCharacterIds)))
                    (oo, ot, oc, oids), (no, nt, nc, nids) = results
                    fast = prev_some and eq and not empty_ids and n > 0
                    ok(sorted(ot[0]) == sorted(nt[0]), "C1 same party members passed to translator")
                    ok(sorted(oo[1:]) == sorted(no[1:]) and oo[0] == no[0] == "DATA", "C1 same result set")
                    if fast:
                        ok(nc["find"] == 0 and nc["get"] == len(nt[0]), "C1 fast path builds party members only")
                        ok(nids == oids or sorted(nids) == sorted(oids), "C1 cached ids preserved (same membership)")
                        if n == 500:
                            probe = {"N": n, "original_gets": oc["get"], "patched_gets": nc["get"],
                                     "original_find_calls": oc["find"], "patched_find_calls": nc["find"]}
                    else:
                        ok(nc == oc and no == oo, "C1 fallback identical")
                    cases += 1
    return cases, probe


# ------------------------------------------------------------------------------------------- main
def main():
    round1 = ROUND1.read_bytes()
    ok(sha(round1) == ROUND1_SHA, "round-1 SWF hash")
    out, rep = apply_patches(round1, PATCHES)
    statuses = {p["id"]: p["status"] for p in rep["patches"]}
    ok(statuses == {"P1": "already_present", "S1": "applied", "S2": "applied", "B1": "applied", "C1": "applied"}, statuses)
    # 1. readback: only the two tags changed; bodies changed exactly as declared
    t_in, t_out = tags_of(round1), tags_of(out)
    ok(set(t_in) == set(t_out), "tag names")
    changed_tags = sorted(n.decode() for n in t_in if t_in[n] != t_out[n])
    ok(changed_tags == ["boot_ffc6", "cn.shop.ShopFirstOpen"], changed_tags)
    old_main, new_main = ABC(t_in[b"boot_ffc6"]), ABC(t_out[b"boot_ffc6"])
    old_help, new_help = ABC(t_in[HELPER_SHOP]), ABC(t_out[HELPER_SHOP])
    for a in (new_main, new_help):
        ok(ABC(a.serialize()).serialize() == a.serialize(), "re-serialize")
    ok(new_main.serialize() == t_out[b"boot_ffc6"] and new_help.serialize() == t_out[HELPER_SHOP], "roundtrip")
    labels = bodies.label_map(new_main)
    diff = sorted(labels.get(i, "?") for i in range(len(old_main.bodies)) if freeze(old_main.bodies[i]) != freeze(new_main.bodies[i]))
    ok(diff == sorted(["ShopTopScene/listCellEnabledResolver", "Restore/saveBattleRestore",
                       "CharacterUseCaseBase/getListCharactersInParties"]), diff)
    hdiff = [i for i in range(len(old_help.bodies)) if freeze(old_help.bodies[i]) != freeze(new_help.bodies[i])]
    ok(hdiff == [bodies.resolve(new_help, "ShopFirstOpen$/productIds")], hdiff)
    for f in ("strings", "multinames", "ints", "uints", "doubles", "namespaces", "ns_sets"):
        ok(freeze(getattr(old_main, f)) == freeze(getattr(new_main, f)), f"main pool {f} unchanged")
    ok(new_help.strings[:len(old_help.strings)] == old_help.strings, "helper strings append-only")
    ok(new_help.multinames[:len(old_help.multinames)] == old_help.multinames, "helper multinames append-only")
    added_mn = [new_help.mn_name(i) for i in range(len(old_help.multinames), len(new_help.multinames))]
    ok(sha(body_of(new_main, COOP_LABEL)[5]) == COOP_AFTER_SHA, "coop getDeferralLevel kept")
    ok(sha(body_of(new_main, "MasterBinaryMap/getIndex")[5]) == PATCHES[0]["after"], "P1 kept")
    # 2. replay onto v29-coop gives the byte-identical SWF; reapplying is a no-op; unknown bodies are refused
    out2, rep2 = apply_patches(read_base_swf(), PATCHES)
    ok(out2 == out, "replay on v29-coop == stacked on round-1")
    out3, rep3 = apply_patches(out, PATCHES)
    ok(out3 == out and all(p["status"] == "already_present" for p in rep3["patches"]), "idempotent")
    tampered = bytearray(round1)
    import struct
    from common import swf_data
    data = bytearray(swf_data(round1))
    raw = t_in[b"boot_ffc6"]
    pos = bytes(data).find(raw)
    victim = old_main.bodies[bodies.resolve(old_main, "Restore/saveBattleRestore")][5]
    at = bytes(data).find(victim, pos)
    ok(at > 0, "locate victim")
    data[at + 0x14e] ^= 0  # keep length; flip the pushbyte operand of #136 (0 -> 2)
    data[at + 0x14f] = 2
    bad = bytes(round1[:4]) + struct.pack("<I", len(data) + 8) + zlib.compress(bytes(data))
    try:
        apply_patches(bad, PATCHES)
        raise AssertionError("tampered SWF accepted")
    except Refused as error:
        ok("B1" in str(error), "tamper refused by B1 hash")
    # selecting a subset only touches that subset
    out4, rep4 = apply_patches(round1, PATCHES, {"B1"})
    ok([p["id"] for p in rep4["patches"]] == ["B1"] and tags_of(out4)[HELPER_SHOP] == t_in[HELPER_SHOP], "subset")
    # 3. instruction-level assertions
    for label, idx in (("ShopTopScene/listCellEnabledResolver", 38), ("Restore/saveBattleRestore", 135)):
        oc, nc = asm.decode(body_of(old_main, label)[5]), asm.decode(body_of(new_main, label)[5])
        ok(len(oc) == len(nc), label + " count")
        d = [i for i in range(len(oc)) if (oc[i].name, oc[i].args, oc[i].target) != (nc[i].name, nc[i].args, nc[i].target)]
        ok(d == [idx], f"{label} differs only at #{idx}: {d}")
    meta = {p["id"]: p for p in rep["patches"]}
    for pid, label, abc_old, abc_new in (("S1", "ShopFirstOpen$/productIds", old_help, new_help),
                                         ("C1", "CharacterUseCaseBase/getListCharactersInParties", old_main, new_main)):
        at, n, _pol = meta[pid]["inserted_at"][0]
        ok(asm.unsplice(body_of(abc_new, label)[5], at, n) == body_of(abc_old, label)[5], pid + " unsplice")
        nc = asm.decode(body_of(abc_new, label)[5])
        oc = asm.decode(body_of(abc_old, label)[5])
        ok([x.name for x in nc[:at]] == [x.name for x in oc[:at]], pid + " prefix")
        ok([(x.name, x.args) for x in nc[at + n:]] == [(x.name, x.args) for x in oc[at:]], pid + " suffix")
        for x in nc[at:at + n]:
            if x.name in ("getproperty", "setproperty", "callproperty", "callpropvoid", "findpropstrict", "constructprop", "getlex"):
                ok(0 < x.args[0] < len(abc_new.multinames), pid + " multiname range")
            ok(x.name not in ("getlex",) or abc_new.mn_name(x.args[0]) in (
                "pinball.context.character::CharacterListSettingTools",), pid + " getlex only of existing client class")
    # 4. stack/scope/locals on every changed body, before and after
    sims = {}
    for pid, label, abc_old, abc_new in (("S1", "ShopFirstOpen$/productIds", old_help, new_help),
                                         ("S2", "ShopTopScene/listCellEnabledResolver", old_main, new_main),
                                         ("B1", "Restore/saveBattleRestore", old_main, new_main),
                                         ("C1", "CharacterUseCaseBase/getListCharactersInParties", old_main, new_main)):
        before, after = check_body(abc_old, body_of(abc_old, label)), check_body(abc_new, body_of(abc_new, label))
        ok(after["unreachable"] == before["unreachable"], pid + " no new unreachable code")
        sims[pid] = {"before": before, "after": after}
        A["n"] += 1
    # 5. execution equivalence on the real bytecode
    s1_cases, s1_stats = s1_test(old_help, new_help)
    s2_cases = s2_test(old_main, new_main)
    b1_cases = b1_test(old_main, new_main)
    c1_cases, c1_probe = c1_test(old_main, new_main)
    result = {
        "passed": True, "assertions": A["n"], "real_bytecode_executed": True, "runtime_verified": False,
        "input_round1_swf_sha256": ROUND1_SHA, "output_swf_sha256": rep["output_swf_sha256"],
        "replay_from_v29_coop_identical": True, "idempotent": True, "tamper_refused": True,
        "patches": {p["id"]: {k: p.get(k) for k in ("label", "tag", "status", "before", "after", "header_before", "header",
                                                     "inserted_at", "replaced", "pool_added")} for p in rep["patches"]},
        "helper_multinames_added": added_mn, "stack_sim": sims,
        "execution": {"S1_cases": s1_cases, "S1_decode_probe": s1_stats, "S2_cases": s2_cases, "B1_cases": b1_cases,
                      "C1_cases": c1_cases, "C1_probe": c1_probe},
        "note": "avm_mini emulates only what these bodies use (Array/Dictionary/Object/String.split/ByteArray/zlib/"
                "CSV first-row rules/=== and int/String conversion); AIR JIT/runtime behaviour is not verified.",
    }
    (ROOT / "analysis" / "test-perf2-results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print(json.dumps({k: result[k] for k in ("passed", "assertions", "output_swf_sha256", "execution")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
