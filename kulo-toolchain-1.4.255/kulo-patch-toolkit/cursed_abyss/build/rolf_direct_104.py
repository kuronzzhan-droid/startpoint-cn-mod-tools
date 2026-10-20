# -*- coding: utf-8 -*-
"""罗尔夫 149986 技能/629 命中改「完整直击」：CreateHitArea params[23] 4 → 104（damage-type-rules-v1）。

叠加在 kulo 1.4.203 视图上 → 1.4.204。默认 **dry run**（只核验 + 打印，不落盘）；--write 才写 zip。
- 4  = 原版「伤害量以直接攻击伤害判定」：只换通用池；显示/统计/技能独立乘区/技能耐性/试炼条仍按技能，直击独立乘区(410/693)吃不到。
- 104 = 客户端 MemberImpl.wfConvertNormalAttack 把来源标志改成独占的 createdByDirectAttack（buffTargetAs 归 0）
        ⇒ 通用池、独立乘区、敌方耐性、飘字样式、伤害统计、伤害类型计数、试炼条、Fever 来源全部按直击。
- 风巨蜥 149998：两档技能根头 + 25 个判定区早已是 102（1.4.198 balance-1014），本脚本只复核不改。
- 客户端要求：v29-coop / v30-perf / 本机 installed_base 均已含 damage-type-rules-v1（wf_damage_type_override.py --check 实测）。
  旧 APK（无该能力）读 104 = 0（自动档）⇒ 按普通技能伤害结算、不崩，但会丢掉现在 4 带来的直击通用池 ⇒ 数据只能随含该能力的 APK 发。
用法：WF_TIP=203 python rolf_direct_104.py [--write]
"""
import copy
import hashlib
import json
import os
import sys
import zipfile
import zlib

os.environ.setdefault("WF_TIP", "204")
from live149 import *  # noqa
import wf_dsl
from wf_character_revision import encode_tree
from dsltools import commands

sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/oldrepo_modtools")
import wf_cursed_weapons as W
import base149 as _B

assert TIP == 204, TIP
assert not os.environ.get("WF_EXTRA_ZIPS")
assert _B._ZIPS[-1].name == "pinball-1.4.203-1.4.204-1-soul-exchange-shop-local.zip", _B._ZIPS[-1].name

OUT = Path(__file__).resolve().parent.parent
NAME = "pinball-1.4.204-1.4.205-1-rolf-direct-104-local.zip"
ROLF = ("battle/action/skill/action/rare5/black_wolf_knight_moon$black_wolf_knight_moon_1",
        "battle/action/skill/action/rare5/black_wolf_knight_moon$black_wolf_knight_moon_2",
        "battle/action/skill/action/ability_skill/ability_skill_wolf_moon_encore$ability_skill_wolf_moon_encore")
LIZARD = ("battle/action/skill/action/rare5/land_dragon_wind_playable$land_dragon_wind_playable_1",
          "battle/action/skill/action/rare5/land_dragon_wind_playable$land_dragon_wind_playable_2")
LOG, files, report = [], {}, {}

for p in ROLF:
    t0 = dsl_tree(p)
    t = copy.deepcopy(t0)
    ha = list(commands(t, "CreateHitArea"))
    assert [c[24] for pp, c in ha] == [4, 4], (p, [c[24] for pp, c in ha])
    assert t[10] == 0, (p, t[10])
    assert W.dsl_capabilities(t0) == [], p
    for pp, c in ha:
        c[24] = 104
    # 只改了这几个标量
    def leaves(n, path=()):
        if isinstance(n, list):
            for i, x in enumerate(n):
                yield from leaves(x, path + (i,))
        else:
            yield path, n
    l1, l0 = list(leaves(t)), list(leaves(t0))
    assert [k for k, v in l1] == [k for k, v in l0]
    diff = [k for (k, v), (k0, v0) in zip(l1, l0) if v != v0 or type(v) is not type(v0)]
    assert diff == [pp + (1, 24) for pp, c in ha], diff
    probs = W.dsl_signature_problems(t)
    assert not probs, probs
    caps = W.dsl_capabilities(t)
    assert caps, "104 must be detected as a client-capability requirement"
    enc = encode_tree(t)
    assert wf_dsl.parse_dsl(zlib.decompress(enc, -15))["tree"] == t, p
    lp = wf_dsl.dsl_logical(p)
    raw0, src = read_raw(lp)
    files[lp] = enc
    report[p.split("$")[1]] = {"logical": lp, "member": member(lp), "source": src,
                               "hit_areas": len(ha), "params23": "4 -> 104", "requires": caps,
                               "before_sha256": hashlib.sha256(raw0).hexdigest(),
                               "after_sha256": hashlib.sha256(enc).hexdigest(), "after_size": len(enc)}
LOG.append("罗尔夫 149986：black_wolf_knight_moon_1/_2 与 629 ability_skill_wolf_moon_encore 的 CreateHitArea params[23] 4 → 104"
           "（各 2 个判定区，根头 tree[10] 仍 0；其余节点逐值不变）")

for p in LIZARD:
    t = dsl_tree(p)
    vals = [c[24] for pp, c in commands(t, "CreateHitArea")]
    assert t[10] == 102 and vals and set(vals) == {102}, (p, t[10], vals)
    report[p.split("$")[1]] = {"unchanged": True, "root_tree10": t[10], "hit_areas": len(vals), "params23": 102,
                               "requires": W.dsl_capabilities(t)}
LOG.append("风巨蜥 149998：land_dragon_wind_playable_1/_2 根头与 25 个判定区已是 102（完整能力伤害），不改")


def main():
    members = {member(lp): d for lp, d in files.items()}
    print(json.dumps(report, ensure_ascii=False, indent=1))
    print("\n".join(LOG))
    if "--write" not in sys.argv:
        print(f"DRY RUN: would write {NAME} with {len(members)} members (applies_on 1.4.204, requires_client damage-type-rules-v1)")
        return 0
    path = OUT / "patch" / NAME
    assert not path.exists(), path
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for m in sorted(members):
            zf.writestr(m, members[m])
    blob = path.read_bytes()
    integ = {"name": NAME, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(members),
             "member_sha256": {m: hashlib.sha256(members[m]).hexdigest() for m in sorted(members)},
             "logical_paths": {member(lp): lp for lp in sorted(files)}, "applies_on": "1.4.204", "version": "1.4.205",
             "requires_client": ["damage-type-rules-v1"], "report": report, "log": LOG}
    path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
