# -*- coding: utf-8 -*-
"""噬龙者 179986：补 5 个空追击 DSL（取主技能同层数招式，倍率 x0.5，去掉改层数的命令）。
视图 = 1.4.245 + WF_MORE(246..249)。用法 python hotfix3.py [--write VER]"""
import sys, os, json, hashlib, zipfile, copy, zlib
sys.path.insert(0, '.')
import v245 as V
_cwd = os.getcwd(); os.chdir(V.BUILD)
import wf_mod_tool as M
from stage_all import csv_text
from wf_character_revision import encode_tree
sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/oldrepo_modtools")
import wf_cursed_weapons as W
os.chdir(_cwd)
NL = "\n"
RATIO = 0.5
UID = 1799860
MAIN = "battle/action/skill/action/rare5/mechanic_dragon_eater_playable$mechanic_dragon_eater_playable_1"
AS = "battle/action/skill/action/ability_skill/mechanic_dragon_eater_{0}$mechanic_dragon_eater_{0}"
TARGETS = {2: "reactor_burst", 5: "reverse_ring", 6: "divine_ray", 7: "meteor", 8: "terminal_meteor"}
NAMES = {2: "反应堆爆裂追击", 5: "逆相环冲", 6: "神圣射线", 7: "坠星", 8: "终端坠星"}
LOG = []


def leaf(v, rs):
    s = csv_text(rs)
    return s if v.endswith(NL) else s.rstrip(NL)


def raw_replace(lp, edits):
    raw, _ = V.read_raw(lp)
    om = M.read_orderedmap_raw_rows_from_bytes(raw, lp)
    keys0, rows0 = list(om.keys), list(om.rows)
    for k, node in edits.items():
        assert V.q.build_node(V.load(lp)[k]) == rows0[keys0.index(k)], (lp, k)
        om.rows[om.keys.index(k)] = V.q.build_node(node)
    out = M.build_orderedmap_raw_rows(om)
    back = M.read_orderedmap_raw_rows_from_bytes(out, lp)
    assert back.keys == keys0
    assert [i for i in range(len(rows0)) if back.rows[i] != rows0[i]] == sorted(keys0.index(k) for k in edits)
    return out


def is_cmd(n, name):
    return isinstance(n, list) and len(n) == 2 and n[0] == "Command" and isinstance(n[1], list) and n[1] and n[1][0] == name


main = V.dsl_tree(MAIN)


def branch(n, N):
    """在主技能的 Accum 链里找 >=N 的 THEN 分支。"""
    if isinstance(n, list):
        if is_cmd(n, "ConditionalsConditionAccumulationNumber") and n[1][1] == ["DCUnique", UID] and n[1][2] == N:
            return n[1][3]
        for a in n:
            r = branch(a, N)
            if r is not None:
                return r
    return None


def strip(n, stats):
    """去掉改层数的命令，倍率 ×RATIO。返回新节点或 None(删除)。"""
    if not isinstance(n, list):
        return n
    if is_cmd(n, "ConsumeUniqueCondition") and n[1][2] == UID:
        stats["consume"] += 1
        return None
    if is_cmd(n, "CreateCondition") and f'"ACUnique",{UID}' in json.dumps(n, separators=(",", ":")):
        stats["grant"] += 1
        return None
    if is_cmd(n, "CreateNormalAttack"):
        n = copy.deepcopy(n)
        for v in n[1][6]:
            v["min"] = round(v["min"] * RATIO, 6)
            v["max"] = round(v["max"] * RATIO, 6)
        stats["atk"] += 1
        return n
    out = []
    for a in n:
        r = strip(a, stats)
        if r is not None or not isinstance(a, list):
            out.append(r)
    return out


files, probs, trees = {}, [], {}
for N, nm in TARGETS.items():
    b = copy.deepcopy(branch(main, N))
    assert b is not None, N
    if is_cmd(b, "ConditionalsMainOrUnison"):
        b = b[1][1]                               # 主位分支（追击行本身仅主位）
    body = b[1] if b[0] == "Block" else [b]
    stats = {"atk": 0, "grant": 0, "consume": 0}
    body = [x for x in (strip(x, stats) for x in body) if x is not None]
    assert stats["atk"] > 0, (N, stats)
    p = AS.format(nm)
    old = V.dsl_tree(p)
    assert old[11] == ["Block", []], p
    new = copy.deepcopy(old)
    new[11] = ["Block", body]
    assert "ConditionalsConditionAccumulationNumber" not in json.dumps(new) or N in (2, 5), N
    probs += [f"{p}: {x}" for x in W.dsl_signature_problems(new)]
    enc = encode_tree(new)
    assert V.wf_dsl.parse_dsl(zlib.decompress(enc, -15))["tree"] == new
    files[V.member(V.wf_dsl.dsl_logical(p))] = enc
    trees[p] = new
    LOG.append(f"DSL {nm}: 取主技能『反应堆』>={N} 层分支，攻击 {stats['atk']} 次倍率 ×{RATIO}，去掉加层 {stats['grant']} / 消耗 {stats['consume']}")

# 说明串
CAS = V.load(V.CAS)
edits = {}
for N, nm in TARGETS.items():
    k = f"mechanic_dragon_eater_{nm}"
    v = CAS[k]
    t = V.rows(v)[0][0]
    o = f"发动「{NAMES[N]}」（CT：1秒）"
    assert t == o, (k, t)
    n = f"发动「{NAMES[N]}」（造成技能伤害，威力为技能中同名招式的50%，CT：1秒）"
    edits[k] = leaf(v, [[n]])
    LOG.append(f"custom_ability_string[{k}]: 补写伤害类型与威力")

print("\n".join(LOG))
print("problems:", probs)
if "--write" in sys.argv:
    VER = sys.argv[sys.argv.index("--write") + 1]
    BASE = os.environ["WF_BASE"]
    assert not probs
    b = raw_replace(V.CAS, edits)
    back = V.q.parse_node(b)
    assert sorted(k for k in back if back[k] != CAS[k]) == sorted(edits)
    files[V.member(V.CAS)] = b
    name = f"pinball-{BASE}-{VER}-1-dragon-eater-followups-local.zip"
    os.makedirs("patch3", exist_ok=True)
    with zipfile.ZipFile(f"patch3/{name}", "w", zipfile.ZIP_DEFLATED) as zf:
        for m in sorted(files):
            zf.writestr(m, files[m])
    blob = open(f"patch3/{name}", "rb").read()
    with zipfile.ZipFile(f"patch3/{name}") as zf:
        assert zf.testzip() is None and all(zf.read(m) == files[m] for m in files)
    integ = {"name": name, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(files),
             "files": sorted(files), "member_sha256": {m: hashlib.sha256(files[m]).hexdigest() for m in sorted(files)},
             "applies_on": BASE, "version": VER, "log": LOG}
    open(f"patch3/{name[:-4]}.integrity.json", "w", encoding="utf8").write(json.dumps(integ, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members")}))
