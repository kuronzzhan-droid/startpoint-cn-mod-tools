# -*- coding: utf-8 -*-
"""1.4.234 → 1.4.235：深渊武器魂珠说明中文化（1018，接 1.4.234 魂珠修正）。

8000101 / 8000102 / 8000108 / 8000112 / 8000114 五件深渊魂珠的 item 行 c5 是 donor 行带来的日文「アビリティソウル」，
改成官方中文「能力魂珠」。可装备属性 c12 本来就按武器设计写对了，不动；其他列不动。
生成器 wf_rogue_rewards.build_ability_soul_item_leaf 已同步写 c5（mod-tools PR #7）。
视图 = rel233 链 + D:/WF/rel234/shipped 的 234 zip。用法：python abyss_soul_text235.py [--write]
"""
import hashlib, json, os, sys, zipfile
from pathlib import Path

OUT = Path(r"D:/WF/out/角色超限-120")
CHAIN = os.environ.get("WF_CHAIN_FILE", os.path.join(os.environ["TEMP"], "claude", "chain234.txt"))
os.environ["WF_TIP"] = "206"
os.environ["WF_EXTRA_ZIPS"] = open(CHAIN).read()
assert "rel234/shipped" in os.environ["WF_EXTRA_ZIPS"]
sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/cursed_abyss/build")
from live149 import *  # noqa
import wf_mod_tool as M  # noqa

FROM, TO = "1.4.234", "1.4.235"
NAME = f"pinball-{FROM}-{TO}-1-abyss-soul-text-local.zip"
NL = chr(10)
ITEM = "master/item/item.orderedmap"
JA, ZH = "アビリティソウル", "能力魂珠"
KEYS = ("8000101", "8000102", "8000108", "8000112", "8000114")

it = load(ITEM)
assert source(ITEM).startswith("pinball-1.4.233-1.4.234"), source(ITEM)
edits, log = {}, []
for k in KEYS:
    r = row(it[k])
    assert r[0] == f"mod_abyss_{k}" and r[6] == "11" and r[5] == JA, (k, r[:7])
    r2 = list(r)
    r2[5] = ZH
    edits[k] = join(r2) + (NL if it[k].endswith(NL) else "")
    log.append(f"{k} {r[2]} c5 {JA}→{ZH}（c12={r[12]} 不动）")
left = [k for k, v in it.items() if k.startswith(("80001", "591", "592")) and row(v)[6] == "11" and row(v)[5] == JA
        and k not in KEYS]
assert not left, left


def raw_replace(lp, edits):
    raw, _ = read_raw(lp)
    om = M.read_orderedmap_raw_rows_from_bytes(raw, lp)
    keys0, rows0 = list(om.keys), list(om.rows)
    for k, node in edits.items():
        om.rows[om.keys.index(k)] = q.build_node(node)
    out = M.build_orderedmap_raw_rows(om)
    back = M.read_orderedmap_raw_rows_from_bytes(out, lp)
    assert back.keys == keys0
    changed = [keys0[i] for i in range(len(rows0)) if back.rows[i] != rows0[i]]
    assert sorted(changed) == sorted(edits), (lp, changed)
    parsed = q.parse_node(out)
    for k, node in edits.items():
        assert parsed[k] == node, (lp, k)
    return out


files = {ITEM: raw_replace(ITEM, edits)}
print(NL.join(log))
if "--write" in sys.argv:
    path = OUT / "patch" / NAME
    assert not path.exists(), path
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for lp in sorted(files):
            zf.writestr(member(lp), files[lp])
    blob = path.read_bytes()
    integ = {"name": NAME, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(files),
             "applies_on": FROM, "version": TO, "logical_paths": {member(lp): lp for lp in files},
             "member_sha256": {member(lp): hashlib.sha256(files[lp]).hexdigest() for lp in files}, "log": log}
    path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + NL,
                                                             "utf-8")
    print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members")}))
