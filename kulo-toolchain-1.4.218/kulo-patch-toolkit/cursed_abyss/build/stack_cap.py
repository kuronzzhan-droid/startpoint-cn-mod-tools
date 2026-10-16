# -*- coding: utf-8 -*-
"""全体 MOD 角色（kulo 1.4.153 视图里不在官方 1.4.0 角色表中的 91 名 + 改造官方 151159/261089）的队长技 / 能力：
「无上限成长」行改为最多 3 次，每次数值 ×1.3（作者取整口径：≥10% 取 5 的倍数，<10% 取整数或 .5），单次 ≤100%（满层 ≤300%）。

无上限成长的判定（candidates.py）：
- 瞬发：有触发（≠开局）、内容是永久数值类（攻/直击/技能/PF/能力伤害、充能、槽上限、HP、独立乘区、合击白值），
  触发次数列 (None)；正值。→ 触发次数改 3。
- 持续：计数型持续触发（按固有层数 134/194/171、连击 2 …）倍乘上限 (None)；若按固有层数计且固有叠层上限÷阈值 ≤10 视为已封顶不动。
  → 倍乘上限改 3。
已有数字上限、触发次数空串（=0 次的死行）、负值、敌方弱体个数计数的行不动。
面板覆盖文案（desc_override_<code>[_slot]）按行内旧数值定点替换并注明上限，逐条人工复核（TEXT_FIX 手工修正）。

用法：WF_TIP=153 python stack_cap.py
"""
import hashlib
import json
import os
import re
import zipfile

os.environ.setdefault("WF_TIP", "153")
from candidates import *  # noqa
from stage_all import csv_text

OUT = Path(__file__).resolve().parent.parent
NAME = "pinball-1.4.153-1.4.154-1-modchar-stack-cap-local.zip"
CAP = 3
MUL = 1.3
PER_MAX = 100000          # 单次上限 100% ⇒ 满层 ≤300%
TABLES = {'ability': 'master/ability/ability.orderedmap', 'leader_ability': 'master/ability/leader_ability.orderedmap'}
CAS_LP = 'master/string/custom_ability_string.orderedmap'


def scale(v: int) -> int:
    """存储值（1000 = 1%）×1.3 后按作者取整口径，单次 ≤100%，且不低于原值（原值已超 100% 的降到 100%）。"""
    pct = v / 1000 * MUL
    if pct >= 10:
        pct = round(pct / 5) * 5
    else:
        pct = round(pct * 2) / 2
    out = int(round(pct * 1000))
    out = max(out, v)
    return min(out, PER_MAX)


def pct_text(v: int) -> str:
    return f"{v / 1000:g}"


def override_key(t: str, k: str) -> str:
    cid = k if t == 'leader_ability' else k[:-1]
    code = row(C[cid])[0]
    return f"desc_override_{code}" if t == 'leader_ability' else f"desc_override_{code}_{k[-1]}"


# 文案人工修正（自动替换后逐条复核；键 = 覆盖键，值 = [(旧行片段, 新行片段)]）
TEXT_FIX: dict[str, list[tuple[str, str]]] = json.loads((Path(__file__).with_name("text_fix.json")).read_text("utf-8"))
GROWTH_WORDS = ("每", "累积", "累计")


def main() -> int:
    out, skipped = candidates()
    tabs = {t: load(lp) for t, lp in TABLES.items()}
    cas = load(CAS_LP)
    changes = []          # 报告
    by_key: dict[tuple[str, str], list[dict]] = {}
    for c in out:
        by_key.setdefault((c['t'], c['key']), []).append(c)
    for (t, key), cs in by_key.items():
        rs = [x for x in rows(tabs[t][key]) if x]
        nonempty = [i for i, x in enumerate(rows(tabs[t][key])) if x]
        for c in cs:
            r = rs[c['i']]
            blk = 'instant' if c['block'] == 'instant' else 'during'
            lim_c = col(t, f'{blk}_trigger', 'trigger_limit')
            lo_c, hi_c = col(t, f'{blk}_content', 'strength.power1'), col(t, f'{blk}_content', 'strength.first_max')
            assert r[lim_c] == '(None)', (key, c['i'], r[lim_c])
            lo, hi = int(r[lo_c]), int(r[hi_c])
            nlo, nhi = scale(lo), scale(hi)
            r[lim_c], r[lo_c], r[hi_c] = str(CAP), str(nlo), str(nhi)
            changes.append(dict(cid=c['cid'], name=row(C[c['cid']])[18], t=t, key=key, i=c['i'], block=blk,
                                trig=c['trig'], kind=c['kind'], old=(lo, hi), new=(nlo, nhi), ucap=c.get('ucap')))
        tabs[t][key] = csv_text(rs)
    # 文案
    text_changes = {}
    fixed_only = {k for k in TEXT_FIX} - {override_key(t, key) for (t, key) in by_key}
    for (t, key), cs in [*by_key.items(), *[((None, k), []) for k in sorted(fixed_only)]]:
        ok = override_key(t, key) if t else key
        if ok not in cas:
            continue
        text = rows(cas[ok])[0][0]
        lines = text.split("\n")
        olds = {}
        for ch in changes:
            if t and (ch['t'], ch['key']) == (t, key):
                olds[pct_text(ch['old'][1])] = pct_text(ch['new'][1])
        new_lines = []
        for line in lines:
            nl = line
            if any(w in line for w in GROWTH_WORDS):
                hit = False
                for o, n in olds.items():
                    pat = re.compile(r"([＋+])" + re.escape(o) + r"([%％])")
                    if pat.search(nl):
                        nl = pat.sub(lambda m: m.group(1) + n + m.group(2), nl)
                        hit = True
                nl = nl.replace("（均无上限）", "（最多3次）").replace("无上限", "最多3次")
                if hit and "最多3" not in nl and "最多计3" not in nl:
                    nl = nl.rstrip("。") + ("（最多计3层）" if "层" in nl else "（最多3次）")
            new_lines.append(nl)
        new = "\n".join(new_lines)
        for a, b in TEXT_FIX.get(ok, []):
            assert a in new, (ok, a)
            new = new.replace(a, b)
        if new != text:
            text_changes[ok] = (text, new)
            cas[ok] = csv_text([[new]])
    # 写包
    files = {}
    for t, lp in TABLES.items():
        base = load(lp)
        data = q.build_node(tabs[t])
        back = q.parse_node(data)
        assert back == tabs[t] and set(back) == set(base)
        assert all(back[k] == base[k] for k in base if (t, k) not in by_key)
        files[lp] = data
    if text_changes:
        base = load(CAS_LP)
        data = q.build_node(cas)
        back = q.parse_node(data)
        assert back == cas and set(back) == set(base) and all(back[k] == base[k] for k in base if k not in text_changes)
        files[CAS_LP] = data
    members = {member(lp): d for lp, d in files.items()}
    path = OUT / "patch" / NAME
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for n in sorted(members):
            z.writestr(n, members[n])
    blob = path.read_bytes()
    integ = {"name": NAME, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(members),
             "files": sorted(members), "member_sha256": {n: hashlib.sha256(members[n]).hexdigest() for n in sorted(members)},
             "logical_paths": {member(lp): lp for lp in sorted(files)}, "applies_on": "1.4.153", "version": "1.4.154"}
    path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
    rep = {"changes": changes, "skipped": [dict(r, why=w) for r, w in skipped],
           "text_changes": {k: {"old": a, "new": b} for k, (a, b) in text_changes.items()},
           "no_override": sorted({override_key(t, k) for (t, k) in by_key} - set(text_changes)),
           "zip": {k: integ[k] for k in ("name", "size", "sha256", "members")}}
    (OUT / "stack_cap_report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), "utf-8")
    print(json.dumps(rep["zip"], ensure_ascii=False), len(changes), "rows", len(text_changes), "texts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
