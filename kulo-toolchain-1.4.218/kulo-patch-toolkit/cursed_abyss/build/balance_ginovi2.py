# -*- coding: utf-8 -*-
"""基诺维 抗性下降 ×0.8（表 2026.10.14 13:15「技能给的伤害抗性降低太多了」），叠加在 kulo 1.4.199 视图上 → 1.4.200。
该行替换了此前「×0.6」行（1.4.198 误落在灼原的狮王 119996）→ 本包同时把 119996 两档技能 DSL 原字节还原为 1.4.197 视图。
用法：WF_TIP=199 python balance_ginovi2.py
"""
import copy
import hashlib
import json
import os
import zipfile
import zlib

os.environ.setdefault("WF_TIP", "199")
from live149 import *  # noqa
import wf_dsl
from wf_character_revision import encode_tree
from dsltools import commands

import sys
sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/oldrepo_modtools")
import wf_cursed_weapons as W

assert TIP == 199, TIP
import base149 as _B
assert not os.environ.get("WF_EXTRA_ZIPS")
assert all(z.parent == ACTIVE for z in _B._ZIPS)
assert not any("five-boss-atlas-slim" in z.name for z in _B._ZIPS)
assert _B._ZIPS[-1].name == "pinball-1.4.198-1.4.199-1-hard-multi-boss-level-fix-local.zip", _B._ZIPS[-1].name

OUT = Path(__file__).resolve().parent.parent
NAME = "pinball-1.4.199-1.4.200-1-balance-ginovi2-local.zip"
TX_LP = "master/character/character_text.orderedmap"
SRV_SRC = KULO / "assets/cdndata/character_text.json"
SRV_DST = OUT / "server23/character_text.json"
LOG: list[str] = []
files: dict[str, bytes] = {}


def parse(raw):
    return wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]


# ---- 1.4.197 视图（剔除 197→198、198→199 两段 zip）
_I197 = {}
for z in _B._ZIPS:
    if z.name.startswith(("pinball-1.4.197-1.4.198-", "pinball-1.4.198-1.4.199-")):
        continue
    with zipfile.ZipFile(z) as zf:
        for n in zf.namelist():
            _I197[n] = z


def raw197(logical):
    m = member(logical)
    if m in _I197:
        with zipfile.ZipFile(_I197[m]) as zf:
            return zf.read(m), _I197[m].name
    return (STORE131 / m.split("production/upload/")[1]).read_bytes(), "store131"


def tol(tree):
    return [ac for pp, c in commands(tree, "CreateCondition") for ac in c[2] if ac[0] == "ACToleranceOfElement"]


# ============================================================ 1) 灼原的狮王 119996 回滚（逐字节取 1.4.197 视图）
for lv in ("1", "2"):
    p = "battle/action/skill/action/rare5/lion_swordman_reborn$lion_swordman_reborn_" + lv
    lp = wf_dsl.dsl_logical(p)
    now_raw, now_src = read_raw(lp)
    old_raw, old_src = raw197(lp)
    assert now_src == "pinball-1.4.197-1.4.198-1-balance-1014-local.zip", now_src
    now, old = parse(now_raw), parse(old_raw)
    a_now = [x for x in tol(now) if x[2] == 254]; a_old = [x for x in tol(old) if x[2] == 254]
    assert a_now[0][3] == [{"min": -0.15, "max": -0.15}] and a_old[0][3] == [{"min": -0.25, "max": -0.25}], (a_now, a_old)
    chk = copy.deepcopy(now)
    [x for x in tol(chk) if x[2] == 254][0][3] = [{"min": -0.25, "max": -0.25}]
    assert chk == old, "1.4.198 对该树的改动不止抗性一处"
    files[lp] = old_raw
    LOG.append(f"灼原的狮王 119996 lion_swordman_reborn_{lv}：全属性(254)抗性 -15% → -25%（回滚 1.4.198 的 ×0.6；原字节取自 1.4.197 视图来源 {old_src}）")

# ============================================================ 2) 基诺维 169999 技能两档 抗性下降 ×0.8
for i in (1, 2):
    p = f"battle/action/skill/action/rare5/ginovi$ginovi_{i}"
    t = copy.deepcopy(dsl_tree(p))
    ts = tol(t); assert len(ts) == 3, ts
    allel = [x for x in ts if x[2] == 254]; dark = [x for x in ts if x[2] == 6]
    assert len(allel) == 2 and len(dark) == 1, ts
    for x in allel:
        assert x[1] == [{"min": 750, "max": 750}] and x[3] == [{"min": -0.5, "max": -0.5}] and x[4] == [{"min": 1, "max": 1}], x
        x[3] = [{"min": -0.4, "max": -0.4}]
    x = dark[0]
    assert x[1] == [{"min": 750, "max": 750}] and x[3] == [{"min": -0.25, "max": -0.25}] and x[4] == [{"min": 1, "max": 1}], x
    x[3] = [{"min": -0.2, "max": -0.2}]
    probs = W.dsl_signature_problems(t)
    assert not probs, probs
    enc = encode_tree(t)
    assert parse(enc) == t
    files[wf_dsl.dsl_logical(p)] = enc
LOG.append("基诺维 169999 技能『掠影协奏』/『掠影协奏＋』：全场敌人 全属性(254)抗性 -50% → -40%（两个分支同改）；技能命中附加 暗属性抗性 -25% → -20%；持续 750 帧(12.5秒)与参数[4]=1 不变")

# ============================================================ 3) 技能文本（客户端 character_text + 服务端 cdndata）
OLD_S = "对全场敌人附加全属性抗性下降效果；"
NEW_S = "对全场敌人附加全属性抗性下降效果；赋予命中的敌人暗属性抗性降低效果；"
TX = load(TX_LP); BASE_TX = copy.deepcopy(TX)
s = TX["169999"]
assert s.count(OLD_S) == 2, s.count(OLD_S)
r = rows(s)[0]; assert r[4] == "掠影协奏" and r[6] == "掠影协奏＋" and OLD_S in r[5] and OLD_S in r[7]
TX["169999"] = s.replace(OLD_S, NEW_S)
r2 = rows(TX["169999"])[0]
assert len(r2) == len(r) and [j for j in range(len(r)) if r[j] != r2[j]] == [5, 7]
data = q.build_node(TX); back = q.parse_node(data)
assert back == TX and set(back) == set(BASE_TX)
assert [k for k in BASE_TX if back[k] != BASE_TX[k]] == ["169999"]
files[TX_LP] = data
LOG.append(f"技能文本（{TX_LP} 169999 两档）：「{OLD_S}」后追加「赋予命中的敌人暗属性抗性降低效果；」（官方措辞不写数值），其余文字不变")

txt = SRV_SRC.read_text("utf-8")
assert txt.count(OLD_S) == 2
new_txt = txt.replace(OLD_S, NEW_S)
jo, jn = json.loads(txt), json.loads(new_txt)
assert [k for k in jo if jo[k] != jn[k]] == ["169999"] and set(jo) == set(jn)
assert jn["169999"][0][5] == r2[5] and jn["169999"][0][7] == r2[7]
SRV_DST.parent.mkdir(exist_ok=True)
SRV_DST.write_bytes(new_txt.encode("utf-8"))
LOG.append("服务端 assets/cdndata/character_text.json 169999 同步（整文件副本 server23/character_text.json，仅该两处字符串替换）")


def main():
    members = {member(lp): d for lp, d in files.items()}
    path = OUT / "patch" / NAME
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for m in sorted(members):
            zf.writestr(m, members[m])
    blob = path.read_bytes()
    assert len(blob) <= 5 * 1024 * 1024
    integ = {"name": NAME, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(members),
             "files": sorted(members), "member_sha256": {m: hashlib.sha256(members[m]).hexdigest() for m in sorted(members)},
             "logical_paths": {member(lp): lp for lp in sorted(files)}, "new_files": [],
             "server_files": {"assets/cdndata/character_text.json": {"copy": "server23/character_text.json",
                                                                      "sha256": hashlib.sha256(SRV_DST.read_bytes()).hexdigest()}},
             "applies_on": "1.4.199", "version": "1.4.200", "requires_client": "纯数据", "log": LOG}
    path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members")}, ensure_ascii=False))
    print(json.dumps(integ["logical_paths"], ensure_ascii=False, indent=1))
    print(integ["server_files"])
    print("\n".join(LOG))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
