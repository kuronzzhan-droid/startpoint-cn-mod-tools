# -*- coding: utf-8 -*-
"""「结实假人们」新增 1112「全伤害木人们·无」：克隆 1107 链路（大木人 + 4 小木人），全部吃四类伤害，
小木人与大木人同 HP、同一组状态（永续不可驱散 -50%/3 攻/3 防/弱体抗性 +50%；可驱散 10×防御 +100%）。叠加在 1.4.177 上。"""
import copy, hashlib, json, os, shutil, zipfile, zlib
os.environ.setdefault("WF_TIP", "178")
from live149 import *  # noqa
import wf_cursed_weapons_r4 as W
import wf_dsl
from wf_character_revision import encode_tree
from stage_all import detect_style, dump_like
from typed_dummies import csv_text, DSL_DIR
import typed_dummies_v2 as V2
OUT = Path(__file__).resolve().parent.parent
NAME = "pinball-1.4.177-1.4.178-1-all-dmg-dummies-multi-local.zip"
LP = V2.LP
QID, CN = "1112", "全伤害木人们·无"
KEY, FKEY = "practice_all_damage_dummies", "funnel_all_damage_dummy"
SRC_Q, SRC_KEY, SRC_F = "1107", "practice_typed_dummies_direct", "funnel_typed_dummy_direct"
SINGLE_PROG = f"{DSL_DIR}$all_damage"
PROGRAM = f"{DSL_DIR}$multi_all_damage"
T = {k: load(v) for k, v in LP.items()}; BASE = copy.deepcopy(T); files = {}
assert QID not in T["practice"]
for k in ("field", "zone", "boss", "level"): assert KEY not in T[k], k
for k in ("funnel", "flevel"): assert FKEY not in T[k], k
src = row(T["practice"][SRC_Q]); assert src[110] == SRC_KEY
orders = [int(row(v)[1]) for v in T["practice"].values() if row(v)[0] == src[0]]
r = list(src); r[1], r[2], r[110] = str(max(orders) + 1), CN, KEY
T["practice"][QID] = csv_text([r], T["practice"][SRC_Q])
f = row(T["field"][SRC_KEY]); f[2] = KEY; T["field"][KEY] = csv_text([f], T["field"][SRC_KEY])
z = row(T["zone"][SRC_KEY]["0"]); assert z[24] == z[26] == SRC_KEY; z[24] = z[26] = KEY
T["zone"][KEY] = {"0": csv_text([z], T["zone"][SRC_KEY]["0"])}
b = row(T["boss"][SRC_KEY]["100"]); assert b[109].endswith("$multi_direct")
b[1], b[109] = "全伤害木人们", PROGRAM; T["boss"][KEY] = {"100": csv_text([b], T["boss"][SRC_KEY]["100"])}
T["level"][KEY] = T["level"][SRC_KEY]
T["funnel"][FKEY] = copy.deepcopy(T["funnel"][SRC_F]); T["flevel"][FKEY] = T["flevel"][SRC_F]
# 状态：完全复用单体 all_damage 脚本的那组 CreateCondition，主体改 0，挂到 FindAllSubjects(0, 51)
single = dsl_tree(SINGLE_PROG); body = copy.deepcopy(single[11][1])
assert len(body) == 18 and all(c[1][0] == "CreateCondition" and c[1][1] == -17 for c in body)
for c in body: c[1][1] = 0
src_tree = dsl_tree(f"{DSL_DIR}$multi_direct"); spawn = src_tree[11][1][0]
assert spawn[1][0] == "SpawnFunnel" and spawn[1][1] == ["Funnel", SRC_F] and spawn[1][2] == 4
tree = ["ActionDsl", 1, ["None"], False, False, False, False, False, False, False, 0, ["Block", [
    ["Command", ["SpawnFunnel", ["Funnel", FKEY], 4, ["FunnelGroup", 1], []]],
    ["Event", ["Wait", 2, "*", ["Block", [["Command", ["FindAllSubjects", 0, 51, [], [], [], [], [], ["DoNothing"], ["Block", body]]]]]]]]]]
assert src_tree[11][1][1][1][:3] == ["Wait", 2, "*"]
probs = W.dsl_signature_problems(tree); assert not probs, probs
data = encode_tree(tree); assert wf_dsl.parse_dsl(zlib.decompress(data, -15))["tree"] == tree
files[wf_dsl.dsl_logical(PROGRAM)] = data
bl, fl = row(T["level"][KEY]), row(T["flevel"][FKEY])
bh, fh = V2.hp(bl[2], bl[3], 13.491646245), V2.hp(fl[2], fl[3], 7.9464)
assert bh <= V2.LIMIT and fh <= V2.LIMIT
for k, lp in LP.items():
    d = q.build_node(T[k]); back = q.parse_node(d)
    assert back == T[k] and all(back[x] == v for x, v in BASE[k].items())
    files[lp] = d
members = {member(lp): d for lp, d in files.items()}
path = OUT / "patch" / NAME
with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
    for m in sorted(members): zf.writestr(m, members[m])
blob = path.read_bytes()
integ = {"name": NAME, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(members),
         "files": sorted(members), "member_sha256": {m: hashlib.sha256(members[m]).hexdigest() for m in sorted(members)},
         "logical_paths": {member(lp): lp for lp in sorted(files)}, "applies_on": "1.4.177", "version": "1.4.178",
         "quest": {"id": QID, "name": CN, "order": r[1], "key": KEY, "funnel": FKEY, "boss_hp": bh, "funnel_hp": fh, "program": PROGRAM}}
path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
name = "practice_quest.json"; raw = (ASSETS / name).read_bytes(); crlf = b"\r\n" in raw
text = raw.decode("utf-8").replace("\r\n", "\n"); value = json.loads(text)
base15 = OUT / "server13" / name   # 1111 尚未进 live 时以 server13 为底
if "1111" not in value:
    raw = base15.read_bytes(); crlf = b"\r\n" in raw; text = raw.decode("utf-8").replace("\r\n", "\n"); value = json.loads(text)
assert QID not in value and "1111" in value
e = copy.deepcopy(value[SRC_Q]); e["name"] = CN; value[QID] = e
style = detect_style(text)
if dump_like(json.loads(text), style) == text:
    out = dump_like(value, style)
else:
    end = len(text.rstrip()); prefix_end = len(text[:end - 1].rstrip())
    mem = json.dumps({QID: e}, ensure_ascii=False, indent=2).splitlines()[1:-1]
    out = text[:prefix_end] + ",\n" + "\n".join(mem) + text[prefix_end:]
assert json.loads(out) == value
s15 = OUT / "server15"; shutil.rmtree(s15, ignore_errors=True); s15.mkdir()
(s15 / name).write_bytes((out.replace("\n", "\r\n") if crlf else out).encode("utf-8"))
print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members", "quest")}, ensure_ascii=False))
