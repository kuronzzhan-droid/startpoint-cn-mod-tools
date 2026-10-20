# -*- coding: utf-8 -*-
"""Static simulation of generated AbilityValues / LeaderAbilityValues row parse."""
import re
from pathlib import Path
GEN = Path(r"D:/WF/_archive/kept/弹国服-tools-and-decompile/scripts/pinball/master/generated")

def _match_brace(s, i):
    d = 0
    for j in range(i, len(s)):
        if s[j] == '{': d += 1
        elif s[j] == '}':
            d -= 1
            if d == 0: return j
    raise ValueError

CALL = re.compile(r"\w+Values\.(parseAt\d+)\(param1\)")
CTOR = re.compile(r"MasterValue\w*\.(\w+)\b")
class Fn:
    pass

def load(cls):
    src = (GEN / f"{cls}.as").read_text("utf-8")
    fns = {}
    for m in re.finditer(r"public static function (parseAt\d+)\(param1:Array\) : (\w+)\s*\{", src):
        b0 = m.end() - 1; b1 = _match_brace(src, b0)
        body = src[b0 + 1:b1]
        f = Fn(); f.name = m.group(1); f.ret = m.group(2); f.body = body
        rd = re.findall(r"param1\[(\d+)\]", body)
        f.col = int(rd[0]) if rd else None
        f.groups = "CharacterGroupId_Impl_" in body
        f.float = "parseFloat" in body
        f.reads = [int(x) for x in rd]
        f.throws = "ClientError(7050" in body
        cases = {}
        for cm in re.finditer(r'if\((_loc\d+_) (==|!=) "([^"]*)"\)\s*\{', body):
            v = cm.group(3)
            if v in ("FALSE", "False", "false", "TRUE", "True", "true"): continue
            s0 = cm.end() - 1; s1 = _match_brace(body, s0)
            if cm.group(2) == "==":
                seg = body[s0:s1]
            else:
                seg = body[s1:]
            calls = CALL.findall(seg)
            ct = CTOR.findall(seg)
            cases[v] = (calls, ct[0] if ct else ("None" if "Option.None" in seg else None))
        f.cases = cases
        f.calls = CALL.findall(body)
        fns[f.name] = f
    ctor_src = src[src.find(f"public function {cls}("):]
    return fns, ctor_src

AB_FNS, _ = load("AbilityValues")
LE_FNS, _ = load("LeaderAbilityValues")
ROOTS = {
 "ability": {"hdr": [0, 1, 2, 3, 5], "awake": (3, "parseAt4"),
    "trig": 5, "0": ["parseAt6", "parseAt13", "parseAt20", "parseAt27", "parseAt39", "parseAt46", "parseAt47"],
    "1": ["parseAt6", "parseAt13", "parseAt20", "parseAt85", "parseAt97", "parseAt108", "parseAt109"], "2": ["parseAt123"]},
}

def _roots_leader():
    # leader: c0 string_id, c1 awake kind, c2 level, c3 trigger; blocks shifted by -2
    r = {}
    for k in ("0", "1", "2"):
        r[k] = ["parseAt%d" % (int(x[7:]) - 2) for x in ROOTS["ability"][k]]
    return {"hdr": [0, 1, 3], "awake": (1, "parseAt2"), "trig": 3, **r}
ROOTS["leader_ability"] = _roots_leader()

def simulate(table, row):
    fns = AB_FNS if table == "ability" else LE_FNS
    R = ROOTS[table]
    reads, issues, ctors = set(R["hdr"]), [], []
    ac, af = R["awake"]
    if row[ac] in ("1", "2"):
        stack = [af]
    elif row[ac] == "0":
        stack = []
    else:
        issues.append(("C7050", ac, row[ac], "awake_kind")); stack = []
    t = row[R["trig"]]
    if t not in R:
        issues.append(("C7050", R["trig"], t, "trigger")); return reads, issues, ctors
    stack += list(R[t])
    seen = set()
    while stack:
        fn = stack.pop()
        if fn in seen: continue
        seen.add(fn)
        f = fns.get(fn)
        if f is None:
            issues.append(("nofn", fn)); continue
        if f.cases:
            v = row[f.col] if f.col < len(row) else ""
            reads.add(f.col)
            if v in f.cases:
                calls, ct = f.cases[v]
                if ct: ctors.append((f.col, v, ct))
                stack += calls
            elif f.throws:
                issues.append(("C7050", f.col, v, fn))
            else:
                stack += f.calls
        else:
            for c in set(f.reads):
                reads.add(c)
                v = row[c] if c < len(row) else ""
                if f.groups and c == f.col and v == "":
                    issues.append(("EMPTY_GROUPS", c, fn))
                if f.float and v == "":
                    issues.append(("NAN_FLOAT", c, fn))
                elif v == "" and not f.groups and "parseInt" in f.body:
                    issues.append(("EMPTY_INT_OPT" if f.ret == "Option" else "EMPTY_INT", c, fn))
            stack += f.calls
    return reads, issues, ctors

# v35-chain patched kinds (ability table only): 422 DashParameter / 423 GaugeGainRestriction / 424 DamageTypeConversion
for _v, _n in (("422", "DashParameter*"), ("423", "GaugeGainRestriction*"), ("424", "DamageTypeConversion*")):
    AB_FNS["parseAt109"].cases[_v] = (["parseAt110", "parseAt118"], _n)
AB_FNS["parseAt47"].cases["724"] = (["parseAt51"], "AddFeverPoint*")
