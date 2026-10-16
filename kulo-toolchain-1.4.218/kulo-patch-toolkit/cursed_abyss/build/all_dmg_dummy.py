# -*- coding: utf-8 -*-
"""练习关「结实假人」新增 1111「全伤害木人·无」：四类伤害都吃，HP≈90 万亿，永续不可驱散（全伤害 -50%、3 攻击、3 防御、
弱体抗性 +50%），另加 10 个可驱散「防御力提升 +100%」。叠加在 1.4.176 上。"""
import copy, hashlib, json, os, shutil, zipfile
os.environ.setdefault("WF_TIP", "177")
from live149 import *  # noqa
import wf_cursed_weapons_r4 as W
import wf_dsl
from wf_character_revision import encode_tree
from stage_all import detect_style, dump_like
import typed_dummies as V1
from typed_dummies import S, csv_text, LP, FRAMES, DSL_DIR
OUT = Path(__file__).resolve().parent.parent
NAME = "pinball-1.4.176-1.4.177-1-all-dmg-dummy-local.zip"
QID, KEY, CN = "1111", "practice_all_damage_dummy", "全伤害木人·无"
SRC_Q, SRC_KEY = "1103", "practice_typed_dummy_direct"
PROGRAM = f"{DSL_DIR}$all_damage"

def cond(ac, key, cancelable):
    return ["Command", ["CreateCondition", -17, [ac], S(1), ["GenericConditionHitEffect"], cancelable, False, key, None,
                        False, 3, S(1), False]]

cmds = [cond(["ACToleranceOfElement", S(FRAMES), 254, S(0.97), S(1)], "all_dummy_damage_down", False)]
cmds += [cond(["ACAttackPoint", S(FRAMES), S(0.1), S(1)], f"all_dummy_atk_{i}", False) for i in range(3)]
cmds += [cond(["ACToleranceOfElement", S(FRAMES), 254, S(0.01), S(1)], f"all_dummy_def_{i}", False) for i in range(3)]
cmds.append(cond(["ACToleranceOfDebuff", S(FRAMES), S(0.5), S(1)], "all_dummy_debuff_half", False))
cmds += [cond(["ACToleranceOfElement", S(FRAMES), 254, S(1.0), S(1)], f"all_dummy_def_dispellable_{i}", True) for i in range(10)]
tree = ["ActionDsl", 1, ["None"], False, False, False, False, False, False, False, 0, ["Block", cmds]]

T = {k: load(v) for k, v in LP.items()}; BASE = copy.deepcopy(T); files = {}
assert QID not in T["practice"]
for k in ("field", "zone", "boss", "level"): assert KEY not in T[k], k
src = row(T["practice"][SRC_Q]); assert src[0] == "100" and src[110] == SRC_KEY
orders = [int(row(v)[1]) for v in T["practice"].values() if row(v)[0] == src[0]]
r = list(src); r[1], r[2], r[110] = str(max(orders) + 1), CN, KEY
T["practice"][QID] = csv_text([r], T["practice"][SRC_Q])
f = row(T["field"][SRC_KEY]); assert f[2] == SRC_KEY; f[2] = KEY; T["field"][KEY] = csv_text([f], T["field"][SRC_KEY])
z = row(T["zone"][SRC_KEY]["0"]); assert z[24] == z[26] == SRC_KEY; z[24] = z[26] = KEY
T["zone"][KEY] = {"0": csv_text([z], T["zone"][SRC_KEY]["0"])}
b = row(T["boss"][SRC_KEY]["100"]); assert b[109].endswith("$direct") and b[110] == "true"
b[1], b[109] = "全伤害木人", PROGRAM; T["boss"][KEY] = {"100": csv_text([b], T["boss"][SRC_KEY]["100"])}
lv = row(T["level"][SRC_KEY]); assert lv[2] == "32938902" and lv[3] == "90"
T["level"][KEY] = csv_text([lv], T["level"][SRC_KEY])
probs = W.dsl_signature_problems(tree); assert not probs, probs
data = encode_tree(tree); import zlib; assert wf_dsl.parse_dsl(zlib.decompress(data, -15))["tree"] == tree
files[wf_dsl.dsl_logical(PROGRAM)] = data
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
         "logical_paths": {member(lp): lp for lp in sorted(files)}, "applies_on": "1.4.176", "version": "1.4.177",
         "quest": {"id": QID, "name": CN, "key": KEY, "program": PROGRAM, "order": r[1]}}
path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
# server
name = "practice_quest.json"; raw = (ASSETS / name).read_bytes(); crlf = b"\r\n" in raw
text = raw.decode("utf-8").replace("\r\n", "\n"); value = json.loads(text); assert QID not in value
e = copy.deepcopy(value[SRC_Q]); e["name"] = CN; value[QID] = e
style = detect_style(text)
if dump_like(json.loads(text), style) == text:
    out = dump_like(value, style)
else:
    end = len(text.rstrip()); prefix_end = len(text[:end - 1].rstrip())
    mem = json.dumps({QID: e}, ensure_ascii=False, indent=2).splitlines()[1:-1]
    out = text[:prefix_end] + ",\n" + "\n".join(mem) + text[prefix_end:]
assert json.loads(out) == value
s13 = OUT / "server13"; shutil.rmtree(s13, ignore_errors=True); s13.mkdir()
(s13 / name).write_bytes((out.replace("\n", "\r\n") if crlf else out).encode("utf-8"))
print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members", "quest")}, ensure_ascii=False))
