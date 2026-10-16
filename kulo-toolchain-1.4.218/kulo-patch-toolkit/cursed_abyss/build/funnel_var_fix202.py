# -*- coding: utf-8 -*-
"""1.4.201 -> 1.4.202: 1.4.199(sb_level_fix199) 把若干 funnel 等级表条目补到 lv100, 但伴生变量表没跟上。
FunnelSource.as:89-92 取变量表首个 key>=敌等级, 否则空 map; 状态 Time/Loop/MoveVariable 终止条件
resolveVariable 失败 => GeneralEnemy.as ~4250-4295 抛。

对象: 1.4.199 level_fix_entries 中 table ∈ {general_funnel, standard_funnel} 的条目。
  standard_funnel = StandardEnemySource, 无伴生变量表(resolveVariable "Not implemented") => 跳过;
  general_funnel 伴生 general_funnel_variable: 键不存在 = 无变量(空 map 常态) => 跳过;
  键存在且无 key>=added => 追加 key=added, 值 = 原最高档子表的原始字节块(逐字节复制)。
行级: 只重写外层索引与目标键的等级索引; 其余键 chunk、目标键既有等级 chunk 逐字节不动。"""
import os, json, hashlib, zipfile, struct, zlib
os.environ["WF_TIP"] = "201"
os.environ.pop("WF_EXTRA_ZIPS", None)
import level_gap_check as L
from live149 import *
import base149
assert base149._ZIPS[-1].name == "pinball-1.4.200-1.4.201-1-ginovi-text-c8601-local.zip", base149._ZIPS[-1]
HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "patch"
FIX199 = OUT / "pinball-1.4.198-1.4.199-1-hard-multi-boss-level-fix-local.integrity.json"


def split_map(raw):
    """[u32 ilen][zlib(index)][chunks] -> (keys, chunks) 原始字节, 严格校验。"""
    ilen = struct.unpack_from("<I", raw)[0]
    index = zlib.decompress(raw[4:4 + ilen]); n = struct.unpack_from("<I", index)[0]
    kb, blob = index[4 + 8 * n:], raw[4 + ilen:]
    keys, chunks, pk, pr = [], [], 0, 0
    for i in range(n):
        ke, re_ = struct.unpack_from("<II", index, 4 + 8 * i)
        assert pk <= ke <= len(kb) and pr <= re_ <= len(blob)
        keys.append(kb[pk:ke].decode("utf-8")); chunks.append(blob[pr:re_]); pk, pr = ke, re_
    assert pk == len(kb) and pr == len(blob) and len(set(keys)) == n
    return keys, chunks


def join_map(keys, chunks):
    kb = rb = b""; pairs = []
    for k, c in zip(keys, chunks):
        kb += k.encode("utf-8"); rb += c; pairs.append((len(kb), len(rb)))
    idx = struct.pack("<I", len(keys)) + b"".join(struct.pack("<II", *p) for p in pairs) + kb
    packed = zlib.compress(idx)
    return struct.pack("<I", len(packed)) + packed + rb


fix199 = json.loads(FIX199.read_text("utf-8"))
assert fix199["version"] == "1.4.199"
plan, log, entries, skipped = {}, [], [], []
for e in fix199["level_fix_entries"]:
    tn, k, lv = e["table"], e["key"], e["added"]
    if tn not in ("general_funnel", "standard_funnel"): continue
    lvl = load(L.LEVEL_TABLES[tn])[k]
    assert str(lv) in lvl, (tn, k, lv)  # 1.4.199 的补行仍在 live
    if tn not in L.VARIABLE_TABLES:
        skipped.append(f"{tn}[{k}]: 无伴生变量表(StandardEnemySource)"); continue
    vt = load(L.VARIABLE_TABLES[tn])
    if k not in vt:
        skipped.append(f"{tn}[{k}]: {tn}_variable 无此键(空 map 常态, 与补行前一致)"); continue
    if L.select_var(vt[k], lv) is not None:
        skipped.append(f"{tn}[{k}]: 变量表已能解析 lv{lv}"); continue
    plan.setdefault(tn, []).append((k, lv, e["quests"]))

members, logical_paths = {}, {}
for tn, items in sorted(plan.items()):
    lp = L.VARIABLE_TABLES[tn]
    raw, src = read_raw(lp)
    keys, chunks = split_map(raw)
    base = q.parse_node(raw); assert keys == list(base)
    touched = {}
    for k, lv, qs in items:
        i = keys.index(k)
        lks, lcs = split_map(chunks[i])
        mx = max(lks, key=int); assert lks[-1] == mx and str(lv) not in lks and lv > int(mx), (k, lks, lv)
        donor = lcs[lks.index(mx)]
        chunks[i] = join_map(lks + [str(lv)], lcs + [donor]); touched[k] = (mx, lv)
        log.append(f"{tn}_variable[{k}]: 等级 {lks} -> 补 {lv} = 复制 {mx} 级子表原始块 ({len(donor)} B) {base[k][mx]}")
        entries.append({"table": f"{tn}_variable", "level_table": tn, "key": k, "old_max": int(mx), "added": lv,
                        "quests": qs, "copied_chunk_sha256": hashlib.sha256(donor).hexdigest()})
    data = join_map(keys, chunks)
    # 校验: 结构读回; 未动键/既有等级逐字节; 新增级 == 原最高级
    back = q.parse_node(data); nk, nc = split_map(data); ok_, oc = split_map(raw)
    assert nk == ok_ and list(back) == list(base)
    for j, k in enumerate(nk):
        if k not in touched:
            assert nc[j] == oc[j], k
        else:
            mx, lv = touched[k]; a, ac = split_map(nc[j]); b, bc = split_map(oc[j])
            assert a == b + [str(lv)] and ac[:-1] == bc and ac[-1] == bc[b.index(mx)]
            assert back[k][str(lv)] == base[k][mx] and all(back[k][x] == base[k][x] for x in base[k])
    assert {k: v for k, v in back.items() if k not in touched} == {k: v for k, v in base.items() if k not in touched}
    members[member(lp)] = data; logical_paths[member(lp)] = lp
    log.append(f"base {lp}: {src} {len(raw)} B sha256 {hashlib.sha256(raw).hexdigest()}")

assert members, "nothing to patch"
name = "pinball-1.4.201-1.4.202-1-funnel-variable-lv100-local.zip"; path = OUT / name
with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
    for m in sorted(members): zf.writestr(m, members[m])
blob = path.read_bytes()
integ = {"name": name, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(members),
         "files": sorted(members), "member_sha256": {m: hashlib.sha256(b).hexdigest() for m, b in members.items()},
         "logical_paths": logical_paths, "applies_on": "1.4.201", "version": "1.4.202", "log": log,
         "skipped": skipped, "variable_fix_entries": entries}
path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
print("\n".join(log)); print("skipped:"); print("\n".join("  " + s for s in skipped))
print(name, len(blob), integ["sha256"])
for m, b in members.items(): print(" ", m, len(b), hashlib.sha256(b).hexdigest())
