# -*- coding: utf-8 -*-
"""1.4.232 → 1.4.233：终始之龙决战掉超限结晶时客户端报错（测试员 1017）。

根因：1.4.207 只在服务端 score_reward_cnmod / rare_score_reward_cnmod 给终始之龙掉落组 12100088 加了
位置 4 → 稀有组 12199320（超限结晶×1，25%），客户端两张表没加。掉落命中时服务端回
drop_rare_reward_ids={group_id:12199320,index:1}，客户端 RareScoreRewardLogic 查
RareScoreRewardTable[12199320][1] 为空 → 报错。
修：客户端 master/reward/score_reward 12100088 加位置 4、master/reward/rare_score_reward 加组 12199320，
与服务端逐字段对应（rare 行格式 = group_string_id,kind,id,count,?,usesRareEffect，照抄同组官方稀有行）。
用法：python overlimit120_droptable233.py [--write]
"""
import hashlib, json, os, sys, zipfile
from pathlib import Path

OUT = Path(r"D:/WF/out/角色超限-120")
CHAIN = os.environ.get("WF_CHAIN_FILE", os.path.join(os.environ["TEMP"], "claude", "chain206.txt"))
os.environ["WF_TIP"] = "206"
os.environ["WF_EXTRA_ZIPS"] = open(CHAIN).read()
sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/cursed_abyss/build")
from live149 import *  # noqa
import wf_mod_tool as M  # noqa

FROM, TO = "1.4.232", "1.4.233"
NAME = f"pinball-{FROM}-{TO}-1-overlimit-drop-table-local.zip"
NL = chr(10)
SR, RR = "master/reward/score_reward.orderedmap", "master/reward/rare_score_reward.orderedmap"
GROUP, POS, RARE, ITEM, RATE = "12100088", "4", "12199320", "10000320", "0.25"

sr, rr = load(SR), load(RR)
g = dict(sr[GROUP])
assert sorted(g) == ["1", "2", "3"], g
r3 = row(g["3"])
assert r3[1] == "1" and r3[6] == GROUP, r3              # 官方：位置 3 → 稀有组 12100088
r4 = list(r3)
r4[6], r4[7] = RARE, RATE
g[POS] = join(r4) + (NL if g["3"].endswith(NL) else "")
assert RARE not in rr
ref = rr[GROUP]["1"]
rref = row(ref)
assert rref[1] == "0" and rref[5] == "false", rref
rn = list(rref)
rn[2], rn[3] = ITEM, "1"
rr_node = {"1": join(rn) + (NL if ref.endswith(NL) else "")}


def raw_replace(lp, edits):
    raw, _ = read_raw(lp)
    om = M.read_orderedmap_raw_rows_from_bytes(raw, lp)
    keys0, rows0 = list(om.keys), list(om.rows)
    for k, node in edits.items():
        if k in keys0:
            om.rows[om.keys.index(k)] = q.build_node(node)
        else:
            om.keys.append(k)
            om.rows.append(q.build_node(node))
    out = M.build_orderedmap_raw_rows(om)
    back = M.read_orderedmap_raw_rows_from_bytes(out, lp)
    assert back.keys[:len(keys0)] == keys0
    changed = [keys0[i] for i in range(len(rows0)) if back.rows[i] != rows0[i]]
    assert sorted(changed + back.keys[len(keys0):]) == sorted(edits), (lp, changed)
    parsed = q.parse_node(out)
    for k, node in edits.items():
        assert parsed[k] == node, (lp, k)
    return out


files = {SR: raw_replace(SR, {GROUP: g}), RR: raw_replace(RR, {RARE: rr_node})}
LOG = [f"score_reward {GROUP} 加位置 {POS}：{r4}", f"rare_score_reward 加组 {RARE}：{rn}"]
print(NL.join(LOG))
if "--write" in sys.argv:
    path = OUT / "patch" / NAME
    assert not path.exists(), path
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for lp in sorted(files):
            zf.writestr(member(lp), files[lp])
    blob = path.read_bytes()
    integ = {"name": NAME, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(files),
             "applies_on": FROM, "version": TO, "logical_paths": {member(lp): lp for lp in files},
             "member_sha256": {member(lp): hashlib.sha256(files[lp]).hexdigest() for lp in files}, "log": LOG}
    path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + NL,
                                                             "utf-8")
    print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members")}))
