# -*- coding: utf-8 -*-
import sys, json, re, collections, zlib
sys.path.insert(0, '.')
import v245 as V, psim as P
from pathlib import Path
OUT = Path('x245'); (OUT / 'chars').mkdir(parents=True, exist_ok=True); (OUT / 'dsl').mkdir(exist_ok=True)
idx = json.load(open(r'D:/WF/out/面板核对-1.4.227/audit/index.json', encoding='utf8'))
OFFI = {x['id']: x['official'] for x in idx}
SC = sorted({x['id'] for x in idx} | {'129989'})
AB, LE, CH, CAS, AS, TX, UQ = (V.load(x) for x in (V.AB, V.LE, V.CH, V.CAS, V.AS, V.TX, V.UQ))
BLK = {"ability": dict(V.D.layout("ability")["blocks"]), "leader_ability": dict(V.D.layout("leader_ability")["blocks"])}
UOFF = {"precondition1": 6, "precondition2": 6, "precondition3": 6, "instant_trigger": 10, "instant_precontent": 6,
        "instant_content": 21, "during_accumulation_trigger": 10, "during_trigger": 7, "during_content": 9}
def cas(k):
    v = CAS.get(k)
    return None if v is None else V.rows(v)[0][0]
def rws(t, k):
    v = t.get(k)
    return [r for r in V.rows(v) if r] if v else []
def raw(r):
    return " ".join(f"c{i}={x}" for i, x in enumerate(r) if x != "" and i)
_dsl = {}
def dsl(prog):
    if prog in _dsl: return _dsl[prog]
    try: t = V.dsl_tree(prog)
    except Exception as e: t = None
    _dsl[prog] = t; return t
def urow(u):
    r = rws(UQ, u)
    return r[0] if r else None

def analyze(tb, r):
    reads, iss, ct = P.simulate(tb, r)
    B = BLK[tb]
    uids = []
    for b, off in UOFF.items():
        c = B[b] + off
        if c in reads and r[c] not in ("", "(None)", "0"):
            uids.append((b, c, r[c]))
    ign = [c for c, x in enumerate(r) if x not in ("", "(None)", "0", "false") and c not in reads]
    progs = []
    ci = B["instant_content"] + 24
    if ci in reads and r[ci] not in ("", "(None)"): progs.append(r[ci])
    pf = []
    for b, off in (("instant_content", 35), ("during_content", 11)):
        c = B[b] + off
        if c in reads and r[c] not in ("", "(None)"):
            pf.append((r[c], r[c + 1], r[c + 2]))
    return reads, iss, ct, uids, ign, progs, pf

def main():
    allinfo = {}
    for cid in SC:
        ch = rws(CH, cid)[0]
        code = ch[0]
        tx = rws(TX, cid); name = tx[0][:2] if tx else []
        L = []; info = {"id": cid, "code": code, "element": ch[3], "groups": ch[4], "slots": {}, "progs": set(), "uids": set(), "pf": []}
        L.append(f"# 角色 {cid}  code={code}  名称={name}  元素c3={ch[3]}(0火1水2雷3风4光5暗)  种族c4={ch[4]}  官方={'是' if OFFI.get(cid) else '否/新'}")
        sk = AS.get(code)
        if sk:
            L.append(f"技能 action_skill[{code}]:")
            for lv in sorted(sk):
                s = V.rows(sk[lv])[0]
                L.append(f"  档{lv} 名称={s[0]} 能量c4/c5={s[4]}/{s[5]} DSL={s[7]}")
                L.append("    描述: " + s[1].replace("\n", " / "))
                info["progs"].add(s[7])
        slots = [("队长技", "leader_ability", LE, cid)] + [(f"能力{i}", "ability", AB, ch[18 + i]) for i in range(1, 7)]
        for nm, tb, T, key in slots:
            rs = rws(T, key)
            if not rs: L.append(f"\n## {nm} [{key}] 无行"); continue
            sid = rs[0][0]
            uni = "" if tb == "leader_ability" else (" 整键仅主位(c1=false)" if all(r[1] == "false" for r in rs) else (" 部分行c1=false" if any(r[1] == "false" for r in rs) else ""))
            L.append(f"\n## {nm} {tb}[{key}] 行数={len(rs)} string_id={sid}{uni}")
            ov = cas("desc_override_" + sid)
            if ov is not None:
                L.append(f"面板覆盖文案 desc_override_{sid}:")
                for ln in ov.split("\n"): L.append("  │ " + ln)
            else:
                L.append("面板: 无覆盖(客户端自动生成)")
            for i, r in enumerate(rs):
                reads, iss, ct, uids, ign, progs, pf = analyze(tb, r)
                try: d = V.D.describe_line(r, tb)
                except Exception as e: d = f"<describe失败 {e}>"
                L.append(f"  行{i}: {d}")
                L.append(f"     构造: " + " / ".join(f"c{c}={v}:{n}" for c, v, n in ct))
                L.append(f"     原始: {raw(r)}")
                if tb == "ability": L.append(f"     c1(可合击)={r[1]}")
                if iss: L.append(f"     ⚠解析: {iss}")
                if ign: L.append(f"     客户端不读的非空列: " + " ".join(f"c{c}={r[c]}" for c in ign))
                for b, c, u in uids:
                    ur = urow(u)
                    L.append(f"     固有引用 {b} c{c}={u} → " + (f"{ur[1]}({ur[0]}) 持续帧={ur[3]} 上限={ur[4]} 覆盖模式={ur[12]}" if ur else "⚠unique_condition 表无此 id"))
                    info["uids"].add(u)
                for p in progs:
                    sv = cas(p.split("/")[-1].split("$")[0]) if "/" in p else None
                    L.append(f"     629 程序={p}" + (f"  说明串={sv!r}" if sv else ""))
                    info["progs"].add(p)
                for pid, lv, did in pf:
                    L.append(f"     PF覆盖 id={pid} 等级={lv} 说明键={did} 说明={cas(did)!r}")
                    info["pf"].append((pid, lv))
        extra = [k for k in CAS if code in k and not k.startswith("desc_override_")]
        if extra:
            L.append("\n## 其他文案键(含 code)")
            for k in extra: L.append(f"  {k}: {cas(k)!r}")
        # pf override programs
        for pid, lv in info["pf"]:
            for n in (1, 2, 3, 4):
                p = f"battle/action/power_flip/action/override/{pid}${pid}_lv{n}"
                if dsl(p) is not None: info["progs"].add(p)
        if info["uids"]:
            L.append("\n## 引用的固有状态")
            for u in sorted(info["uids"]):
                ur = urow(u); L.append(f"  {u}: {ur}")
        D = []
        for p in sorted(info["progs"]):
            t = dsl(p)
            s = json.dumps(t, ensure_ascii=False, separators=(",", ":")) if t is not None else "<缺失:视图里没有这个 DSL>"
            D.append(f"=== {p}  ({len(s)} 字符)\n{s}\n")
        (OUT / "chars" / f"{cid}.md").write_text("\n".join(L), "utf-8")
        (OUT / "dsl" / f"{cid}.txt").write_text("\n".join(D), "utf-8")
        info["progs"] = sorted(info["progs"]); info["uids"] = sorted(info["uids"])
        allinfo[cid] = info
    json.dump(allinfo, open(OUT / "info.json", "w", encoding="utf8"), ensure_ascii=False, indent=0)
    print("done", len(allinfo))
main()
