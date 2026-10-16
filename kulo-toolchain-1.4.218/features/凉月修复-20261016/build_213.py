# -*- coding: utf-8 -*-
"""1.4.212 -> 1.4.213:凉月 159992 三条词条行补齐客户端必读列(纯数据)。
  ability[1599921] #2(kind 0 攻击力,每直击 1 次 +10% 累计):c67 cancelable ''→'0'、c74 initial_multiply ''→'1'
  ability[1599922] #2(kind 24):c67 cancelable ''→'0'
  leader_ability[159992] #5(kind 489 连击加成):c65 cancelable ''→'0'
c74 空串 = Std.parseInt('') = null → int 0,multiply_trigger 为 None 时倍率永远 0,该效果完全不生效;
cancelable 空串原本就按 0 读,补 '0' 行为不变,只为过「声明即必填」门禁。官方同 kind 行:c67 '0' 为多数、c74 全是 '1'。
视图:kulo active 1.4.131–1.4.206 + 1.4.207–1.4.212(WF_EXTRA_ZIPS)。用法:python build_213.py [--write]"""
import hashlib, json, os, sys, zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.environ["WF_TIP"] = "206"
os.environ["WF_EXTRA_ZIPS"] = (HERE / "extra_zips.txt").read_text("utf-8").strip()
BUILD = Path(r"D:/WF/out/kulo-patch-toolkit/cursed_abyss/build")
sys.path.insert(0, str(BUILD))
os.chdir(BUILD)
sys.path.insert(0, r"D:/WF/startpoint-cn-wiki/mod-tools")
from p192_common import *  # noqa
import base149
import wf_mod_tool as M
sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/oldrepo_modtools")
import wf_client_legality as L

assert base149._ZIPS[-1].name == "pinball-1.4.211-1.4.212-1-ten-items-local.zip", base149._ZIPS[-1]
NAME = "pinball-1.4.212-1.4.213-1-liangyue-ability-columns-local.zip"
PATCH = HERE / "patch"
NL = chr(10)
sha = lambda b: hashlib.sha256(b).hexdigest()
LOG, files, lps = [], {}, {}

AB_LP = "master/ability/ability.orderedmap"
LA_LP = "master/ability/leader_ability.orderedmap"
EDIT = {AB_LP: {}, LA_LP: {}}
T = {lp: load(lp) for lp in EDIT}


def leaf(v, rs):
    from stage_all import csv_text
    s = csv_text(rs)
    return s if v.endswith(NL) else s.rstrip(NL)


def raw_replace(lp, edits):
    """外层 raw rows 原样保留,只替换 edits 中的键 chunk(未动键逐字节相同)。"""
    raw, _ = read_raw(lp)
    om = M.read_orderedmap_raw_rows_from_bytes(raw, lp)
    keys0, rows0 = list(om.keys), list(om.rows)
    for k, node in edits.items():
        assert k in keys0, (lp, k)
        assert q.build_node(load(lp)[k]) == rows0[keys0.index(k)], (lp, k)
        om.rows[om.keys.index(k)] = q.build_node(node)
    out = M.build_orderedmap_raw_rows(om)
    back = M.read_orderedmap_raw_rows_from_bytes(out, lp)
    assert back.keys == keys0
    assert [i for i in range(len(rows0)) if back.rows[i] != rows0[i]] == sorted(keys0.index(k) for k in edits)
    return out


def fix(lp, kind_name, key, idx, kind_col, kind, sets):
    rs = [r for r in rows(T[lp][key]) if r]
    r = rs[idx]
    assert r[kind_col] == kind, (key, idx, r[kind_col])
    for col, new in sets:
        assert r[col] == "", (key, idx, col, r[col])
        r[col] = new
    EDIT[lp][key] = leaf(T[lp][key], rs)
    for i, x in enumerate(rs):
        p = L.client_legality_problems(kind_name, x) + [
            s for s in L.declared_block_field_problems(kind_name, x) if "instant_content.target_element" not in s]
        assert not p, (key, i, p)
    LOG.append(f"{kind_name}[{key}] #{idx} kind {kind}:" + "、".join(f"c{c} ''→'{v}'" for c, v in sets))


fix(AB_LP, "ability", "1599921", 2, 47, "0", [(67, "0"), (74, "1")])
fix(AB_LP, "ability", "1599922", 2, 47, "24", [(67, "0")])
fix(LA_LP, "leader_ability", "159992", 5, 45, "489", [(65, "0")])

for lp, ed in EDIT.items():
    b = raw_replace(lp, ed)
    back = q.parse_node(b)
    assert set(back) == set(T[lp]) and sorted(k for k in back if back.get(k) != T[lp].get(k)) == sorted(ed), lp
    files[member(lp)] = b; lps[member(lp)] = lp
    LOG.append(f"{lp}:改键 {sorted(ed)};其余键 chunk 逐字节保留")


def main():
    print("\n".join(LOG))
    if "--write" not in sys.argv:
        print("DRY RUN", len(files), "members"); return 0
    PATCH.mkdir(exist_ok=True)
    path = PATCH / NAME
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for m in sorted(files): zf.writestr(m, files[m])
    blob = path.read_bytes(); assert len(blob) <= 5 * 1024 * 1024
    with zipfile.ZipFile(path) as zf:
        assert zf.testzip() is None and all(zf.read(m) == files[m] for m in files)
    integ = {"name": NAME, "size": len(blob), "sha256": sha(blob), "members": len(files), "files": sorted(files),
             "member_sha256": {m: sha(files[m]) for m in sorted(files)}, "logical_paths": {m: lps[m] for m in sorted(files)},
             "new_files": [], "applies_on": "1.4.212", "version": "1.4.213",
             "requires_client": "纯数据", "log": LOG}
    path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
