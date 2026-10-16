# -*- coding: utf-8 -*-
"""1.4.198 -> 1.4.199: quest 的 battle_enemy_level 高于敌方等级表条目最高档 => getSurjectivity 抛 U_3be147
(「値 N に対応するキーが見つかりません」)。

缺口由 level_gap_check.Scan 按客户端装载路径求闭包得到(zone 槽 -> 等级表行 -> action DSL / esdl ->
SpawnFunnel/SpawnAlterEgo ...), 只取 tier0(客户端真按等级查表)的缺口; tier1(DSL/ESDL 按键名提到, 如 EliminateFunnel)
与 tier2(通用敌表行内 routine_id 同名)不查等级表, 不补(官方 1.4.0 档的 lv100 关卡即反例证据)。
修法: 给每个缺口条目补一行 key=所需等级(=原最高档行原样复制), 追加在末尾; 其余键/行不动。"""
import os, json, hashlib, zipfile
os.environ["WF_TIP"] = "198"
os.environ.pop("WF_EXTRA_ZIPS", None)
import level_gap_check as L
from live149 import *
import base149
assert base149._ZIPS[-1].name.startswith("pinball-1.4.197-1.4.198"), base149._ZIPS[-1]
OUT = Path(__file__).resolve().parent.parent / "patch"

scan = L.Scan().run()
need = {}  # (table,key) -> (level, old_max, quests)
for (tn, k), g in scan.gaps.items():
    if g["tier"] == 0:
        need[(tn, k)] = (g["need_t0"], g["old_max"], g["quests"])
assert not scan.curve_gaps, scan.curve_gaps

members, logical_paths, log, entries = {}, {}, [], []
for tn in sorted({t for t, _ in need}):
    lp = L.LEVEL_TABLES[tn]
    tab = load(lp); base = load(lp)
    touched = set()
    for (t2, k), (lv, old, qs) in sorted(need.items()):
        if t2 != tn: continue
        e = tab[k]; mx = max(e, key=int)
        assert int(mx) == old and str(lv) not in e and lv > old, (tn, k, mx, lv)
        d = dict(e); d[str(lv)] = e[mx]; tab[k] = d; touched.add(k)
        first = e[mx] if isinstance(e[mx], str) else str(e[mx])
        log.append(f"{tn}[{k}]: 最高 {mx} -> 补 {lv} 级 = 复制 {mx} 级行 ({first[:50]})")
        entries.append({"table": tn, "key": k, "old_max": int(mx), "added": lv, "quests": qs})
    data = q.build_node(tab); back = q.parse_node(data)
    assert back == tab and list(back) == list(base)
    assert all(back[k] == base[k] for k in base if k not in touched)
    for k in touched:
        assert all(back[k][x] == base[k][x] for x in base[k]) and list(back[k])[:-1] == list(base[k])
    members[member(lp)] = data; logical_paths[member(lp)] = lp

name = "pinball-1.4.198-1.4.199-1-hard-multi-boss-level-fix-local.zip"; path = OUT / name
with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
    for m in sorted(members): zf.writestr(m, members[m])
blob = path.read_bytes()
integ = {"name": name, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(members),
         "files": sorted(members), "member_sha256": {m: hashlib.sha256(b).hexdigest() for m, b in members.items()},
         "logical_paths": logical_paths, "applies_on": "1.4.198", "version": "1.4.199", "log": log,
         "level_fix_entries": entries}
path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
print("\n".join(log)); print(name, len(blob), integ["sha256"])
