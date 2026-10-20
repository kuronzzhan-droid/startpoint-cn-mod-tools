# -*- coding: utf-8 -*-
import sys, json, re, collections
sys.path.insert(0, '.')
import v245 as V, psim as P
info = json.load(open('x245/info.json', encoding='utf8'))
AB, LE, CH, CAS, UQ = (V.load(x) for x in (V.AB, V.LE, V.CH, V.CAS, V.UQ))
BLK = {"ability": dict(V.D.layout("ability")["blocks"]), "leader_ability": dict(V.D.layout("leader_ability")["blocks"])}
UOFF = {"precondition1": 6, "precondition2": 6, "precondition3": 6, "instant_trigger": 10, "instant_precontent": 6,
        "instant_content": 21, "during_accumulation_trigger": 10, "during_trigger": 7, "during_content": 9}
THOFF = {"precondition1": 3, "precondition2": 3, "precondition3": 3, "instant_trigger": 3, "instant_precontent": 3,
         "during_accumulation_trigger": 3, "during_trigger": 3}
MBOFF = {"instant_trigger": 11, "during_accumulation_trigger": 11, "during_trigger": 10, "instant_content": 3, "during_content": 3}
GRANT_ROW = {"ConditionUnique", "CoffinNotRemoveConditionUnique"}
GRANT_ENEMY = {"EnemyConditionUnique", "NearestEnemyConditionUnique", "TriggerEnemyConditionUnique"}
ELT = {"0": "Red", "1": "Blue", "2": "Yellow", "3": "Green", "4": "White", "5": "Black"}
ELS = set(ELT.values())
def rws(t, k):
    v = t.get(k); return [r for r in V.rows(v) if r] if v else []
def urow(u):
    r = rws(UQ, str(u)); return r[0] if r else None
def cas(k):
    v = CAS.get(k); return None if v is None else V.rows(v)[0][0]
def dsltext(cid):
    return open(f"x245/dsl/{cid}.txt", encoding="utf8").read()

F = collections.defaultdict(list)
def add(cid, slot, kind, msg): F[cid].append((slot, kind, msg))

grants = collections.defaultdict(set)   # uid -> {(cid, where)}
reads = []                              # (cid, slot, uid, mode, threshold_layers, where)
mbids = collections.defaultdict(set)
flags_set = collections.defaultdict(set)
for cid, inf in info.items():
    ch = rws(CH, cid)[0]
    d = dsltext(cid)
    for m in re.finditer(r'"ACUnique",(\d+)', d): grants[m.group(1)].add((cid, "DSL"))
    for m in re.finditer(r'"Create(?:Summons|Bomb)Multiball",[^,]*,(\d+)', d): mbids[cid].add(m.group(1))
    for m in re.finditer(r'"ConditionalsConditionAccumulationNumber",\["DCUnique",(\d+)\],(-?\d+)', d):
        reads.append((cid, "DSL", m.group(1), "accum", int(m.group(2)), "ConditionalsConditionAccumulationNumber"))
    for m in re.finditer(r'"BindConditionAccumulationVariable",-?\d+,\d+,\["DCUnique",(\d+)\]', d):
        reads.append((cid, "DSL", m.group(1), "accum", 0, "BindConditionAccumulationVariable"))
    for m in re.finditer(r'"ConditionalsConditionExist",(-?\d+),\["DCUnique",(\d+)\]', d):
        reads.append((cid, "DSL", m.group(2), "exist", 0, "ConditionalsConditionExist"))
    for m in re.finditer(r'"ConsumeUniqueCondition",(-?\d+),(\d+)', d):
        reads.append((cid, "DSL", m.group(2), "consume", 0, "ConsumeUniqueCondition"))
    slots = [("队长技", "leader_ability", LE, cid)] + [(f"能力{i}", "ability", AB, ch[18 + i]) for i in range(1, 7)]
    for nm, tb, T, key in slots:
        for i, r in enumerate(rws(T, key)):
            rd, iss, ct = P.simulate(tb, r)
            B = BLK[tb]
            ctmap = {c: n for c, v, n in ct}
            for b in UOFF:
                kc = B[b]
                if kc not in ctmap: continue
                name = ctmap[kc]
                uc = kc + UOFF[b]
                if uc in rd and r[uc] not in ("", "(None)", "0") and not name.endswith("*"):
                    u = r[uc]
                    if b == "instant_content" and name in GRANT_ROW:
                        grants[u].add((cid, f"{nm}#{i}"))
                    elif b == "instant_content" and name in GRANT_ENEMY:
                        grants[u].add((cid, f"{nm}#{i}:enemy"))
                    else:
                        th = 0
                        if b in THOFF and (kc + THOFF[b]) in rd:
                            try: th = int(r[kc + THOFF[b] + 1]) / 100000  # first_max column
                            except: th = 0
                        mode = "accum" if ("Accumulation" in name and "Low" not in name) else ("low" if "Low" in name else "other")
                        reads.append((cid, f"{nm}#{i}", u, mode, th, f"{b}:{name}"))
                if name.startswith("ChangeSkillFlag"):
                    n = name[len("ChangeSkillFlag"):] or "1"
                    flags_set[cid].add(n)
                mc = kc + MBOFF.get(b, 999)
                if b in MBOFF and mc in rd and r[mc] not in ("", "(None)", "0"):
                    if r[mc] not in mbids[cid]:
                        add(cid, f"{nm}#{i}", "多球组", f"{b}:{name} 引用协力球组 {r[mc]}，本角色 DSL 没有召唤该组(召唤组={sorted(mbids[cid])})")
            for it in iss:
                add(cid, f"{nm}#{i}", "解析", str(it))
            # resonance element vs own
            for b in ("precondition1", "precondition2", "precondition3"):
                kc = B[b]
                if kc in ctmap and ctmap[kc] not in ("Always",):
                    gc = kc + 5
                    th = r[kc + 4]
                    if gc in rd:
                        gs = set(r[gc].split(",")) & ELS
                        own = ELT.get(ch[3])
                        if gs and own not in gs:
                            add(cid, f"{nm}#{i}", "元素门", f"{b}={ctmap[kc]} 组={r[gc]} 阈值={th}，角色本身元素={own}")
    # change skill flags in DSL
    for m in re.finditer(r'"ConditionalsChangeSkillFlag",(\d+)', d):
        n = m.group(1)
        if n not in flags_set[cid]:
            add(cid, "DSL", "技能旗", f"DSL 判 ChangeSkillFlag {n}，本角色行没有设置该旗(已设={sorted(flags_set[cid])})")
    if "<缺失:视图里没有这个 DSL>" in d:
        for m in re.finditer(r"=== (\S+)  \(\d+ 字符\)\n<缺失", d): add(cid, "DSL", "缺DSL", m.group(1))

for cid, slot, u, mode, th, where in reads:
    ur = urow(u)
    if ur is None:
        add(cid, slot, "固有缺行", f"{where} 引用 {u}，unique_condition 表无此行"); continue
    cap = ur[4]
    g = grants.get(u, set())
    if not g:
        add(cid, slot, "固有无来源", f"{where} 读 {u}「{ur[1]}」，扫描范围内没有任何行/DSL 赋予它")
    elif all(w.endswith(":enemy") for _, w in g) and not re.search("Enemy|Slayer", where):
        add(cid, slot, "固有对象", f"{where} 读自身侧 {u}「{ur[1]}」，但只被赋予给敌人 {sorted(g)}")
    if mode == "accum" and cap in ("(None)", "1"):
        add(cid, slot, "固有上限", f"{where} 按层数读 {u}「{ur[1]}」，上限={cap}")
    if th and cap.isdigit() and th > int(cap):
        add(cid, slot, "阈值>上限", f"{where} 需要 {th:g} 层，{u}「{ur[1]}」上限={cap}")
    for gc, gw in g:
        if gc != cid and not any(gc2 == cid for gc2, _ in g):
            add(cid, slot, "固有外来", f"{where} 读 {u}「{ur[1]}」，只由其他角色赋予 {sorted(g)}"); break

with open("lint.txt", "w", encoding="utf8") as f:
    for cid in sorted(F):
        inf = info[cid]
        f.write(f"\n## {cid} {inf['code']}\n")
        for s in sorted(set(F[cid])): f.write(f"  [{s[1]}] {s[0]}: {s[2]}\n")
print(sum(len(set(v)) for v in F.values()), "findings in", len(F), "chars")
