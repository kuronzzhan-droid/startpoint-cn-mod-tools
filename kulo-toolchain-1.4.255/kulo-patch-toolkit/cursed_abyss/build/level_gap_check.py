# -*- coding: utf-8 -*-
"""敌等级档缺口检查(U_3be147 / getSurjectivity「値 N に対応するキーが見つかりません」)。

客户端 GeneralEnemySourceHelper.getSurjectivity(map, lv) 取首个 key>=lv 的行, 否则抛。
本脚本按客户端的装载路径做可达性闭包:
  quest 表(battle_enemy_level 列) -> quest 行内所有 field_data 键 -> field_data c2 = zone
  -> zone 每行: zako01..10 (c2,4..20 -> general_zako), boss1..3(+_multi) (kind,id)=(c23..34)
  -> 等级表行(按 lv 选中行; 缺口时取最高行) 的所有单元格 / 逗号片段:
       * 等级表键 -> 递归 (orochi 头/张量体等跨表引用)
       * action DSL 路径 -> DSL
       * esdl 路径 -> ESDL (prefix bH + 每个字符串 -> DSL)
  -> DSL: SpawnFunnel(Funnel/Zako/StandardFunnel) / SpawnAlterEgo(general_boss) 精确;
          其余字符串若是 DSL/esdl 路径继续跟, 若是等级表键记为弱引用(同样检查)。
  -> general_enemy_watch[*][id] 子树中的 DSL 路径。
另外全局检查 EnemySourceBase 用到的等级曲线表(party_atk/party_hp/hp/atk/tp 曲线)。

分层: tier0 = 客户端真按等级查表的边(zone 槽 / SpawnFunnel / SpawnAlterEgo / 特种 boss 行内 id 列),
      缺口 = 必崩, 计入退出码; tier1 = DSL/ESDL 里按键名提到(EliminateFunnel / IfThisCharacterIsSpecific* /
      ESDL watch 伙伴), tier2 = 通用敌表行内同名(routine_id 复用) —— 都不查等级表, 只报告。
      实证: 官方 1.4.0 全量档里 hard_multi 1004/1005/2/100000 与 boss_battle 1/34/5 均为 lv100, 其 tier1
      条目(steampunk_*_core_multi、reine_rouge_funnel_big_bomb 等)最高只到 80, 官方可正常游玩。
伴生变量表(1.4.202 起): GeneralBossSource:96-99 / FunnelSource:89-92 / ZakoSource:58-61 用
      getInjectivelyWithDefault(var_table, id, 空) + getSurjectivityWithDefault(entry, lv, 空) 取变量子表;
      键存在但无 key>=lv => 拿到空 map, 状态的 Time/Loop/MoveVariable 终止条件 resolveVariable 失败即抛
      (GeneralEnemy.as ~4250-4295)。键整体不存在 = 该敌本来就无变量(官方常态), 不算缺口。
      standard_* / 特种 boss 走 StandardEnemySource.resolveVariable = "Not implemented", 无伴生表。
      对每个 tier0 可达的 general_boss/funnel/zako 条目按 quest 等级模拟首个 key>=lv。
      官方先例白名单: 若当前变量条目与官方 1.4.0 全量档某条目逐值相同(同键, 或自制克隆), 且官方该键
      变量表同样取不到 need 级、而官方等级表却 >= need(=官方确实这样跑), 记 NOTE 不计退出码
      (lich_wind_multi / guardian_golem_fire_multi 变量 79 < 等级表 100 即此类)。
视图: WF_TIP(默认 198) + WF_EXTRA_ZIPS(';' 分隔, 后者覆盖)。
用法: python level_gap_check.py [--json out.json] [--quiet]
退出码: 0 = 零缺口, 1 = 有缺口(等级表 tier0 / 曲线 / 无官方先例的变量表缺口)。
"""
import os, sys, re, json, zlib, functools, argparse
os.environ.setdefault("WF_TIP", "198")
from live149 import *  # noqa
import p192_common as pc
import wf_dsl

LEVEL_TABLES = {
    "standard_boss": "master/battle/boss/standard_boss.orderedmap",
    "general_boss": "master/battle/boss/general_boss.orderedmap",
    "general_zako": "master/battle/zako/general_zako.orderedmap",
    "general_funnel": "master/battle/boss/funnel/general_funnel.orderedmap",
    "standard_funnel": "master/battle/boss/funnel/standard_funnel.orderedmap",
    "tentacle": "master/battle/boss/funnel/tentacle.orderedmap",
    "kraken": "master/battle/boss/kraken.orderedmap",
    "orochi": "master/battle/boss/orochi.orderedmap",
    "orochi_ex": "master/battle/boss/orochi_ex.orderedmap",
    "orochi_ex_head": "master/battle/boss/orochi_ex_head.orderedmap",
    "conductor": "master/battle/boss/conductor.orderedmap",
    "touyakiren_ceo": "master/battle/boss/touyakiren_ceo.orderedmap",
    "water_sphere": "master/battle/boss/water_sphere.orderedmap",
    "holy_sphere": "master/battle/boss/holy_sphere.orderedmap",
    "wind_sphere": "master/battle/boss/wind_sphere.orderedmap",
    "thunder_sphere": "master/battle/boss/thunder_sphere.orderedmap",
    "fire_sphere": "master/battle/boss/fire_sphere.orderedmap",
}
CURVE_TABLES = {  # EnemySourceBase: getSurjectivity(curve[id], lv) / flat curve(lv)
    "party_atk_curve": "master/battle/enemy/party/party_atk_curve.orderedmap",
    "party_hp_curve": "master/battle/enemy/party/party_hp_curve.orderedmap",
    "hit_hp_basic_curve": "master/battle/enemy/hp/hit_hp_basic_curve.orderedmap",
    "hit_hp_correction_curve": "master/battle/enemy/hp/hit_hp_correction_curve.orderedmap",
    "fix_hp_basic_curve": "master/battle/enemy/hp/fix_hp_basic_curve.orderedmap",
    "atk_basic_curve": "master/battle/enemy/atk/atk_basic_curve.orderedmap",
    "atk_correction_curve": "master/battle/enemy/atk/atk_correction_curve.orderedmap",
    "tp_basic_curve": "master/battle/enemy/tp/tp_basic_curve.orderedmap",
}
# (logical, battle_enemy_level 列) — 列号取自客户端 *QuestValues.as
QUEST_TABLES = [
    ("master/quest/event/advent_event_quest.orderedmap", 112),
    ("master/quest/boss_battle_quest.orderedmap", 106),
    ("master/quest/event/carnival_event_quest.orderedmap", 95),
    ("master/quest/event/challenge_dungeon_event_quest.orderedmap", 107),
    ("master/quest/character_quest.orderedmap", 108),
    ("master/quest/event/daily_exp_mana_event_quest_odds.orderedmap", 11),
    ("master/quest/event/daily_week_event_quest_odds.orderedmap", 11),
    ("master/quest/ex_quest.orderedmap", 106),
    ("master/quest/event/expert_single_event_quest.orderedmap", 109),
    ("master/quest/event/hard_multi_event_quest.orderedmap", 107),
    ("master/quest/main_quest.orderedmap", 106),
    ("master/quest/practice/practice_quest.orderedmap", 107),
    ("master/quest/event/raid_event_quest.orderedmap", 96),
    ("master/quest/event/ranking_event_single_quest.orderedmap", 89),
    ("master/quest/event/rush_event_quest.orderedmap", 95),
    ("master/quest/event/score_attack_event_quest.orderedmap", 99),
    ("master/skill_preview/skill_preview_quest.orderedmap", 27),
    ("master/quest/event/solo_time_attack_event_quest.orderedmap", 98),
    ("master/quest/event/story_event_single_quest.orderedmap", 108),
    ("master/quest/event/tower_dungeon_event_quest.orderedmap", 96),
    ("master/tutorial/tutorial_quest.orderedmap", 47),
    ("master/quest/event/world_story_event_boss_battle_quest.orderedmap", 106),
    ("master/quest/event/world_story_event_quest.orderedmap", 107),
]
BOSS_KIND = {"0": "standard_boss", "1": "general_boss", "2": "kraken", "3": "orochi", "4": "orochi_ex",
             "5": "orochi_ex_head", "6": "conductor", "7": "touyakiren_ceo", "8": "general_boss",  # Concerted -> GeneralBoss
             "9": "water_sphere", "10": "holy_sphere", "11": "wind_sphere", "12": "thunder_sphere", "13": "fire_sphere"}
SPAWN_KIND = {"Funnel": "general_funnel", "Zako": "general_zako", "StandardFunnel": "standard_funnel"}
# 等级表 -> 伴生变量表(客户端 *Source 构造里 getSurjectivityWithDefault 读取)。其余等级表无伴生表。
VARIABLE_TABLES = {
    "general_boss": "master/battle/boss/general_boss_variable.orderedmap",
    "general_funnel": "master/battle/boss/funnel/general_funnel_variable.orderedmap",
    "general_zako": "master/battle/zako/general_zako_variable.orderedmap",
}
# 官方 1.4.0 全量档(非 store: store 混有自制改动)。member 名 = 盐哈希, 找不到时全档搜索。
OFFICIAL_ARCHIVE = Path(r"D:/WF/startpoint-cn-kulo/.cdn/cn/archive-common-full")
OFFICIAL_SRC = {
    "master/battle/boss/general_boss_variable.orderedmap": "pinball-1.4.0-168-572fea1b.zip",
    "master/battle/boss/funnel/general_funnel_variable.orderedmap": "pinball-1.4.0-48-8be68ff1.zip",
    "master/battle/zako/general_zako_variable.orderedmap": "pinball-1.4.0-21-1c4fff7c.zip",
    "master/battle/boss/general_boss.orderedmap": "pinball-1.4.0-296-5ab17e92.zip",
    "master/battle/boss/funnel/general_funnel.orderedmap": "pinball-1.4.0-49-e9e98fe1.zip",
    "master/battle/zako/general_zako.orderedmap": "pinball-1.4.0-83-486bde64.zip",
}


@functools.lru_cache(maxsize=None)
def official(lp):
    """官方 1.4.0 全量档里的表; 档不在本机则返回 None(白名单失效 => 变量缺口全部按失败报)。"""
    import zipfile
    m = member(lp)
    cands = [OFFICIAL_ARCHIVE / OFFICIAL_SRC[lp]] if lp in OFFICIAL_SRC else []
    cands += sorted(OFFICIAL_ARCHIVE.glob("pinball-1.4.0-*.zip")) if OFFICIAL_ARCHIVE.exists() else []
    for z in cands:
        if not z.exists(): continue
        with zipfile.ZipFile(z) as zf:
            if m in zf.namelist(): return q.parse_node(zf.read(m))
    return None


def select_var(entry, lv):
    """FunnelSource/ZakoSource/GeneralBossSource: getSurjectivityWithDefault —— keys() 顺序首个 >= lv, 否则 None(=空 map)。"""
    for k in entry:
        if int(k) >= lv: return k
    return None


def tryload(lp):
    try: return load(lp)
    except Exception: return None


T = {n: tryload(lp) or {} for n, lp in LEVEL_TABLES.items()}
VT = {n: tryload(lp) or {} for n, lp in VARIABLE_TABLES.items()}
KEY_INDEX = {}
for n, t in T.items():
    for k in t: KEY_INDEX.setdefault(k, []).append(n)
FD = load("master/battle/field_data.orderedmap")
Z = load("master/battle/zone.orderedmap")
W = tryload("master/battle/boss/general_enemy_watch.orderedmap") or {}


@functools.lru_cache(maxsize=None)
def asset(lp):
    for r in pc.ROOTS:
        raw, _ = pc.aread(r, lp)
        if raw is not None: return raw
    return None


@functools.lru_cache(maxsize=None)
def dsl_tree(path):
    raw = asset(path + ".action.dsl.amf3.deflate")
    if raw is None: return None
    return wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]


@functools.lru_cache(maxsize=None)
def esdl_tree(path):
    p = path if path.endswith(".esdl.amf3.deflate") else path + ".esdl.amf3.deflate"
    raw = asset(p)
    if raw is None: return None
    return wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]


def strings(x):
    if isinstance(x, str): yield x
    elif isinstance(x, dict):
        for v in x.values(): yield from strings(v)
    elif isinstance(x, list):
        for v in x: yield from strings(v)


def lists(x):
    if isinstance(x, list):
        yield x
        for v in x: yield from lists(v)
    elif isinstance(x, dict):
        for v in x.values(): yield from lists(v)


def pieces(cell):
    out = {cell.strip()}
    for p in re.split(r'[,\s]', cell): out.add(p.strip())
    for p in re.findall(r'"([^"]+)"', cell): out.add(p.strip())
    out.discard("")
    return out


GENERIC = {"general_boss", "general_zako", "general_funnel", "standard_boss", "standard_funnel"}
# 边强度: strong = 客户端确实按等级取行 (zone 槽 / DSL SpawnFunnel·SpawnAlterEgo / 特种 boss 行内 id 列)
#         family = DSL/ESDL 中按键名提到(EliminateFunnel、IfThisCharacterIsSpecific*、ESDL watch 伙伴等), 同一遭遇族
#         rowweak = 通用敌表行内碰巧等于另一键(多为 routine_id 复用), 不算查表
TIER = {"zone": 0, "spawn": 0, "alter_ego": 0, "row": 0, "dslweak": 1, "esdlweak": 1, "rowweak": 2}


def classify(s, refs, how, self_ref=None):
    """把一个字符串分到: 等级表键 / DSL / esdl。"""
    if s in KEY_INDEX and how:
        for tn in KEY_INDEX[s]:
            if (tn, s) != self_ref: refs.add(("key", tn, s, how))
    if "/" in s:
        if dsl_tree(s) is not None: refs.add(("dsl", s))
        elif esdl_tree(s) is not None: refs.add(("esdl", s))


def _dedupe(refs):
    best = {}
    for r in refs:
        if r[0] == "key":
            k = r[1:3]
            if k not in best or TIER[r[3]] < TIER[best[k][3]]: best[k] = r
    return frozenset([r for r in refs if r[0] != "key"] + list(best.values()))


@functools.lru_cache(maxsize=None)
def dsl_refs(path):
    refs = set(); t = dsl_tree(path)
    if t is None: return frozenset()
    for l in lists(t):
        if len(l) >= 2 and l[0] == "SpawnFunnel" and isinstance(l[1], list) and len(l[1]) >= 2 and l[1][0] in SPAWN_KIND:
            refs.add(("key", SPAWN_KIND[l[1][0]], l[1][1], "spawn"))
        if len(l) >= 2 and l[0] == "SpawnAlterEgo" and isinstance(l[1], str):
            refs.add(("key", "general_boss", l[1], "alter_ego"))
    for s in set(strings(t)):
        classify(s, refs, "dslweak")
    refs.discard(("dsl", path))
    return _dedupe(refs)


@functools.lru_cache(maxsize=None)
def esdl_refs(path):
    refs = set(); t = esdl_tree(path)
    if t is None: return frozenset()
    pre = t.get("bH") if isinstance(t, dict) and isinstance(t.get("bH"), str) else ""
    for s in set(strings(t)):
        classify(s, refs, "esdlweak")
        if pre and "/" not in s and dsl_tree(pre + s) is not None: refs.add(("dsl", pre + s))
    return _dedupe(refs)


@functools.lru_cache(maxsize=None)
def watch_refs(key):
    refs = set()
    for kind, sub in W.items():
        if isinstance(sub, dict) and key in sub:
            for s in set(strings(sub[key])):
                for p in pieces(s):
                    if "/" in p: classify(p, refs, None)
    return frozenset(refs)


def select_row(entry, lv):
    for k in entry:  # 客户端: keys() 顺序, 首个 >= lv
        if int(k) >= lv: return k
    return max(entry, key=int)


@functools.lru_cache(maxsize=None)
def row_refs(tn, key, lk):
    refs = set(); txt = T[tn][key][lk]
    if not isinstance(txt, str): return frozenset()
    for r in rows(txt):
        for cell in r:
            for p in pieces(cell): classify(p, refs, "rowweak" if tn in GENERIC else "row", self_ref=(tn, key))
    return _dedupe(refs)


class Scan:
    def __init__(self):
        self.lookups = {}   # (tn,key) -> {lv: set(quest)}
        self.missing = {}   # (tn,key) -> set(quest)  键不存在(另一类错误)
        self.missing_assets = set()
        self.quest_nodes = {}  # quest -> set((tn,key))

    def closure(self, roots, lv, parents=None, tier=1):
        """roots: [(tn,key)]; 返回到达的 (tn,key) 集与缺失。parents: 可选 dict 记录来路。"""
        seen_k, seen_a, todo = set(), set(), [(("key", tn, k, "zone"), None) for tn, k in roots]
        miss = set()
        while todo:
            n, par = todo.pop()
            if n[0] == "key":
                tn, k = n[1], n[2]
                if TIER[n[3]] > tier or (tn, k) in seen_k: continue
                seen_k.add((tn, k))
                if parents is not None: parents[("key", tn, k)] = (par, n[3])
                if k not in T.get(tn, {}):
                    miss.add((tn, k)); continue
                lk = select_row(T[tn][k], lv)
                me = ("key", tn, k)
                todo.extend((x, me) for x in row_refs(tn, k, lk)); todo.extend((x, me) for x in watch_refs(k))
            else:
                if n[:2] in seen_a: continue
                seen_a.add(n[:2])
                if parents is not None: parents[n[:2]] = (par, n[0])
                todo.extend((x, n[:2]) for x in (dsl_refs(n[1]) if n[0] == "dsl" else esdl_refs(n[1])))
        return seen_k, miss

    def chain(self, qid, tk, tier=0):
        roots, lv = self.quest_roots[qid]
        par = {}; self.closure(roots, lv, par, tier)
        node, out = ("key",) + tuple(tk), []
        while node is not None:
            p, how = par.get(node, (None, "?"))
            out.append(f"{node[1] if node[0]=='key' else node[0]}:{node[-1]}" + (f"({how})" if node[0]=='key' else ""))
            node = p
        return " <- ".join(out)

    def zone_roots(self, zone):
        out = []
        for zk, zt in Z.get(zone, {}).items():
            if not isinstance(zt, str) or not zt: continue
            zr = row(zt)
            for c in range(2, 21, 2):
                if c < len(zr) and zr[c] not in ("(None)", ""): out.append(("general_zako", zr[c]))
            for c in range(23, 35, 2):
                if c + 1 < len(zr) and zr[c] not in ("(None)", ""):
                    tn = BOSS_KIND.get(zr[c])
                    if tn: out.append((tn, zr[c + 1]))
                    else: self.missing_assets.add(f"zone {zone}: boss kind {zr[c]} id {zr[c+1]} (未建模)")
        return out

    def run(self):
        self.quest_levels = {}; self.quest_roots = {}
        for lp, lc in QUEST_TABLES:
            Q = tryload(lp)
            if Q is None: continue
            def walk(node, path):
                if isinstance(node, dict):
                    for k, v in node.items(): yield from walk(v, path + (k,))
                elif isinstance(node, str) and node:
                    for i, r in enumerate(rows(node)):
                        if r: yield path + ((str(i),) if i else ()), r
            for path, r in walk(Q, ()):
                if lc >= len(r) or not r[lc].lstrip("-").isdigit(): continue
                lv = int(r[lc]); qid = lp.split("/")[-1].replace(".orderedmap", "") + ":" + "/".join(path)
                zones = {FD_ZONE[c] for c in r if c in FD_ZONE}
                if not zones: continue
                self.quest_levels[qid] = lv
                roots = [x for z in sorted(zones) for x in self.zone_roots(z)]
                self.quest_roots[qid] = (roots, lv)
                prev = set()
                for tier in (0, 1, 2):
                    nodes, miss = self.closure(roots, lv, tier=tier)
                    if tier == 0: self.quest_nodes[qid] = nodes
                    for tk in nodes - prev:
                        if tk[1] in T.get(tk[0], {}):
                            self.lookups.setdefault(tk, {}).setdefault(lv, {}).setdefault(qid, tier)
                    for m in miss: self.missing.setdefault(m, {}).setdefault(qid, tier)
                    prev = nodes
        # 缺口(按最小层级): tier0 强引用 / tier1 同族弱引用 / tier2 仅通用表行内同名
        self.gaps = {}
        for (tn, k), byl in self.lookups.items():
            mx = max(int(x) for x in T[tn][k])
            hit = {q: t for l, qs in byl.items() if l > mx for q, t in qs.items()}
            if hit:
                self.gaps[(tn, k)] = {"old_max": mx, "need": max(l for l in byl if l > mx) if min(hit.values()) <= 1 else
                                      max(l for l, qs in byl.items() if l > mx), "tier": min(hit.values()),
                                      "quests": sorted(q for q, t in hit.items() if t == min(hit.values())),
                                      "need_t0": max([l for l, qs in byl.items() if l > mx and min(qs.values()) == 0] or [0])}
        self.check_variables()
        # 曲线表
        top = max(self.quest_levels.values()) if self.quest_levels else 0
        self.curve_gaps = {}; self.curve_notes = []
        for cn, lp in CURVE_TABLES.items():
            c = tryload(lp)
            if not c:  # store 里只有 16 字节桩 = 打进 APK 的 bundled 表, 这里查不到
                self.curve_notes.append(f"{cn}: store 为桩(APK bundled), 未检查"); continue
            if all(k.lstrip("-").isdigit() for k in c):
                if max(map(int, c)) < top: self.curve_gaps[(cn, "")] = {"old_max": max(map(int, c)), "need": top}
            else:
                for k, v in c.items():
                    if isinstance(v, dict) and max(map(int, v)) < top:
                        self.curve_gaps[(cn, k)] = {"old_max": max(map(int, v)), "need": top}
        return self

    def check_variables(self):
        """伴生变量表: tier0 可达的 general_* 条目, 在每个 quest 等级下模拟 getSurjectivityWithDefault。"""
        self.var_gaps = {}    # (tn,key) -> 无官方先例, 计入退出码
        self.var_notes = {}   # (tn,key) -> 官方 1.4.0 同样缺口(先例), 只报告
        found = {}
        for (tn, k), byl in self.lookups.items():
            ve = VT.get(tn, {}).get(k)
            if not isinstance(ve, dict) or not ve: continue  # 键不在变量表 = 无变量, 客户端给空 map 是常态
            for lv, qs in byl.items():
                t0 = [qq for qq, t in qs.items() if t == 0]
                if not t0 or select_var(ve, lv) is not None: continue
                g = found.setdefault((tn, k), {"var_levels": list(ve), "var_max": max(int(x) for x in ve),
                                               "level_max": max(int(x) for x in T[tn][k]), "need": 0, "quests": set()})
                g["need"] = max(g["need"], lv); g["quests"].update(t0)
        for (tn, k), g in found.items():
            g["quests"] = sorted(g["quests"])
            ve = VT[tn][k]
            ov, ol = official(VARIABLE_TABLES[tn]), official(LEVEL_TABLES[tn])
            prec = None
            if ov is not None and ol is not None:
                same = ([k] if ov.get(k) == ve else []) + sorted(x for x, e in ov.items() if e == ve and x != k)
                for ok in same:
                    if select_var(ov[ok], g["need"]) is None and any(int(x) >= g["need"] for x in ol.get(ok, {})):
                        prec = ok; break
            g["official_precedent"] = prec
            (self.var_notes if prec else self.var_gaps)[(tn, k)] = g


FD_ZONE = {}
for _k, _v in FD.items():
    if isinstance(_v, str) and _v:
        _r = row(_v)
        if len(_r) > 2 and _r[2] in Z: FD_ZONE[_k] = _r[2]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--json"); ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    s = Scan().run()
    print(f"view: WF_TIP={os.environ.get('WF_TIP')} extra={os.environ.get('WF_EXTRA_ZIPS','')}")
    print(f"quests scanned: {len(s.quest_levels)}, level range {min(s.quest_levels.values())}..{max(s.quest_levels.values())}")
    print(f"level-table lookups: {len(s.lookups)} entries")
    real = {k: g for k, g in s.gaps.items() if g["tier"] == 0}
    weak = {k: g for k, g in s.gaps.items() if g["tier"] >= 1}
    print(f"GAPS (tier0 真查表, 需补): {len(real)}  name-only refs tier1/2 (非查表, 不补): {len(weak)}  curve gaps: {len(s.curve_gaps)}  missing keys: {len(s.missing)}")
    for (tn, k), g in sorted(real.items()):
        print(f"  GAP {tn}[{k}] max {g['old_max']} < need {g['need_t0']}  quests={len(g['quests'])} {g['quests'][:8]}")
        if not a.quiet: print(f"      via {s.chain(g['quests'][0], (tn, k), 0)}")
    for (tn, k), g in sorted(weak.items(), key=lambda x: (x[1]['tier'], x[0])):
        print(f"  name-only[t{g['tier']}] {tn}[{k}] max {g['old_max']} quests={g['quests'][:4]}")
        if not a.quiet: print(f"      via {s.chain(g['quests'][0], (tn, k), g['tier'])}")
    for k, g in sorted(s.curve_gaps.items()): print(f"  CURVE GAP {k}: {g}")
    print(f"VARIABLE GAPS (伴生变量表取不到 quest 等级, 需补): {len(s.var_gaps)}  official-precedent notes: {len(s.var_notes)}")
    for (tn, k), g in sorted(s.var_gaps.items()):
        print(f"  VAR GAP {tn}_variable[{k}] levels {g['var_levels']} (max {g['var_max']}) < need {g['need']}"
              f"  level-table max {g['level_max']}  quests={len(g['quests'])} {g['quests'][:8]}")
        if not a.quiet: print(f"      via {s.chain(g['quests'][0], (tn, k), 0)}")
    for (tn, k), g in sorted(s.var_notes.items()):
        src = "same key" if g["official_precedent"] == k else f"clone of official {g['official_precedent']}"
        print(f"  NOTE var-gap official precedent ({src}): {tn}_variable[{k}] max {g['var_max']} < need {g['need']}"
              f"  quests={g['quests'][:4]}")
    if official(VARIABLE_TABLES["general_funnel"]) is None:
        print("  NOTE 官方 1.4.0 全量档不可读: 变量缺口白名单失效, 全部按失败计")
    for (tn, k), qs in sorted(s.missing.items()):
        print(f"  MISSING KEY {tn}[{k}] tier{min(qs.values())} quests={len(qs)} e.g. {sorted(qs)[:3]}")
    for m in sorted(s.missing_assets): print("  NOTE", m)
    for m in s.curve_notes: print("  NOTE", m)
    # 受影响 quest: 补丁新增了等级行、且本 quest 等级超过该条目原最高级 => 装载路径改走新增行
    ents = {}
    for z in filter(None, os.environ.get("WF_EXTRA_ZIPS", "").split(";")):
        ij = Path(z).with_name(Path(z).stem + ".integrity.json")
        if ij.exists():
            for e in json.loads(ij.read_text("utf-8")).get("level_fix_entries", []):
                ents[(e["table"], e["key"])] = e["old_max"]
    if ents:
        hit = {}
        for qid, nodes in s.quest_nodes.items():
            for tk in nodes:
                if tk in ents and s.quest_levels[qid] > ents[tk]: hit.setdefault(qid, set()).add(tk)
        print(f"AFFECTED QUESTS (load path now reads an added level row): {len(hit)}")
        for qid in sorted(hit): print(f"  {qid} lv={s.quest_levels[qid]} via {sorted('%s[%s]' % x for x in hit[qid])}")
    if a.json:
        Path(a.json).write_text(json.dumps({
            "gaps": {f"{tn}|{k}": g for (tn, k), g in s.gaps.items()},
            "curve_gaps": {f"{a_}|{b}": g for (a_, b), g in s.curve_gaps.items()},
            "missing": {f"{tn}|{k}": qs for (tn, k), qs in s.missing.items()},
            "var_gaps": {f"{tn}|{k}": g for (tn, k), g in s.var_gaps.items()},
            "var_notes": {f"{tn}|{k}": g for (tn, k), g in s.var_notes.items()},
        }, ensure_ascii=False, indent=1), "utf-8")
    return 1 if (real or s.curve_gaps or s.var_gaps) else 0


def s_orig_max(tk, s):
    """补丁视图下: 新增行之前的最高等级 = 次高键(新增键为最高)。"""
    ks = sorted(int(x) for x in T[tk[0]][tk[1]])
    return ks[-2] if len(ks) > 1 else ks[-1]


if __name__ == "__main__":
    sys.exit(main())
