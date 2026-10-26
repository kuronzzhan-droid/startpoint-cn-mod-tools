"""敌人等级、生成闭包和变量表检查。"""
from __future__ import annotations

from .prepush_base import *
from .prepush_text import _empty

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
# general_* 键在客户端还会按同一等级再查 *_variable(FunnelSource.as:89-92 空表即抛)
VARIABLE_TABLES = {
    "general_boss": "master/battle/boss/general_boss_variable.orderedmap",
    "general_funnel": "master/battle/boss/funnel/general_funnel_variable.orderedmap",
    "general_zako": "master/battle/zako/general_zako_variable.orderedmap",
}
CURVE_TABLES = {
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
             "5": "orochi_ex_head", "6": "conductor", "7": "touyakiren_ceo", "8": "general_boss",
             "9": "water_sphere", "10": "holy_sphere", "11": "wind_sphere", "12": "thunder_sphere",
             "13": "fire_sphere"}
SPAWN_KIND = {"Funnel": "general_funnel", "Zako": "general_zako", "StandardFunnel": "standard_funnel"}
GENERIC = {"general_boss", "general_zako", "general_funnel", "standard_boss", "standard_funnel"}
TIER = {"zone": 0, "spawn": 0, "alter_ego": 0, "row": 0, "dslweak": 1, "esdlweak": 1, "rowweak": 2}


def _strings(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for v in x.values():
            yield from _strings(v)
    elif isinstance(x, list):
        for v in x:
            yield from _strings(v)


def _lists(x):
    if isinstance(x, list):
        yield x
        for v in x:
            yield from _lists(v)
    elif isinstance(x, dict):
        for v in x.values():
            yield from _lists(v)


def _pieces(cell):
    out = {cell.strip()}
    for p in re.split(r"[,\s]", cell):
        out.add(p.strip())
    for p in re.findall(r'"([^"]+)"', cell):
        out.add(p.strip())
    out.discard("")
    return out


def _numeric_keys(entry) -> list[int]:
    return [int(k) for k in entry if str(k).lstrip("-").isdigit()]


class LevelScan:
    def __init__(self, view: View):
        import wf_dsl  # 延迟导入:只有 level 检查需要 AMF3 解析
        self.wf_dsl = wf_dsl
        self.view = view
        self.T = {n: view.table(lp) or {} for n, lp in LEVEL_TABLES.items()}
        self.missing_tables = [lp for n, lp in LEVEL_TABLES.items() if view.table(lp) is None]
        self.KEY_INDEX: dict[str, list[str]] = {}
        for n, t in self.T.items():
            for k in t:
                self.KEY_INDEX.setdefault(k, []).append(n)
        self.FD = view.table("master/battle/field_data.orderedmap") or {}
        self.Z = view.table("master/battle/zone.orderedmap") or {}
        self.W = view.table("master/battle/boss/general_enemy_watch.orderedmap") or {}
        self.FD_ZONE = {}
        for k, v in self.FD.items():
            if isinstance(v, str) and v:
                r = row(v)
                if len(r) > 2 and r[2] in self.Z:
                    self.FD_ZONE[k] = r[2]
        self.dsl_tree = functools.lru_cache(maxsize=None)(self._dsl_tree)
        self.esdl_tree = functools.lru_cache(maxsize=None)(self._esdl_tree)
        self.dsl_refs = functools.lru_cache(maxsize=None)(self._dsl_refs)
        self.esdl_refs = functools.lru_cache(maxsize=None)(self._esdl_refs)
        self.watch_refs = functools.lru_cache(maxsize=None)(self._watch_refs)
        self.row_refs = functools.lru_cache(maxsize=None)(self._row_refs)

    def _parse_amf(self, logical):
        raw = self.view.raw(logical)
        if raw is None:
            return None
        try:
            return self.wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]
        except Exception:  # noqa: BLE001
            return None

    def _dsl_tree(self, path):
        return self._parse_amf(path + ".action.dsl.amf3.deflate")

    def _esdl_tree(self, path):
        p = path if path.endswith(".esdl.amf3.deflate") else path + ".esdl.amf3.deflate"
        return self._parse_amf(p)

    def classify(self, s, refs, how, self_ref=None):
        if s in self.KEY_INDEX and how:
            for tn in self.KEY_INDEX[s]:
                if (tn, s) != self_ref:
                    refs.add(("key", tn, s, how))
        if "/" in s:
            if self.dsl_tree(s) is not None:
                refs.add(("dsl", s))
            elif self.esdl_tree(s) is not None:
                refs.add(("esdl", s))

    @staticmethod
    def _dedupe(refs):
        best = {}
        for r in refs:
            if r[0] == "key":
                k = r[1:3]
                if k not in best or TIER[r[3]] < TIER[best[k][3]]:
                    best[k] = r
        return frozenset([r for r in refs if r[0] != "key"] + list(best.values()))

    def _dsl_refs(self, path):
        refs = set()
        t = self.dsl_tree(path)
        if t is None:
            return frozenset()
        for lst in _lists(t):
            if len(lst) >= 2 and lst[0] == "SpawnFunnel" and isinstance(lst[1], list) \
                    and len(lst[1]) >= 2 and lst[1][0] in SPAWN_KIND:
                refs.add(("key", SPAWN_KIND[lst[1][0]], lst[1][1], "spawn"))
            if len(lst) >= 2 and lst[0] == "SpawnAlterEgo" and isinstance(lst[1], str):
                refs.add(("key", "general_boss", lst[1], "alter_ego"))
        for s in set(_strings(t)):
            self.classify(s, refs, "dslweak")
        refs.discard(("dsl", path))
        return self._dedupe(refs)

    def _esdl_refs(self, path):
        refs = set()
        t = self.esdl_tree(path)
        if t is None:
            return frozenset()
        pre = t.get("bH") if isinstance(t, dict) and isinstance(t.get("bH"), str) else ""
        for s in set(_strings(t)):
            self.classify(s, refs, "esdlweak")
            if pre and "/" not in s and self.dsl_tree(pre + s) is not None:
                refs.add(("dsl", pre + s))
        return self._dedupe(refs)

    def _watch_refs(self, key):
        refs = set()
        for sub in self.W.values():
            if isinstance(sub, dict) and key in sub:
                for s in set(_strings(sub[key])):
                    for p in _pieces(s):
                        if "/" in p:
                            self.classify(p, refs, None)
        return frozenset(refs)

    @staticmethod
    def select_row(entry, lv):
        for k in entry:            # 客户端:按键序取首个 >= lv
            if str(k).lstrip("-").isdigit() and int(k) >= lv:
                return k
        nums = [k for k in entry if str(k).lstrip("-").isdigit()]
        return max(nums, key=int) if nums else None

    def _row_refs(self, tn, key, lk):
        refs = set()
        txt = self.T[tn][key].get(lk) if isinstance(self.T[tn][key], dict) else None
        if not isinstance(txt, str):
            return frozenset()
        for r in rows(txt):
            for cell in r:
                for p in _pieces(cell):
                    self.classify(p, refs, "rowweak" if tn in GENERIC else "row", self_ref=(tn, key))
        return self._dedupe(refs)

    def closure(self, roots, lv, parents=None, tier=1):
        seen_k, seen_a = set(), set()
        todo = [(("key", tn, k, "zone"), None) for tn, k in roots]
        miss = set()
        while todo:
            n, par = todo.pop()
            if n[0] == "key":
                tn, k = n[1], n[2]
                if TIER[n[3]] > tier or (tn, k) in seen_k:
                    continue
                seen_k.add((tn, k))
                if parents is not None:
                    parents[("key", tn, k)] = (par, n[3])
                if k not in self.T.get(tn, {}) or not isinstance(self.T[tn][k], dict):
                    miss.add((tn, k))
                    continue
                lk = self.select_row(self.T[tn][k], lv)
                me = ("key", tn, k)
                if lk is not None:
                    todo.extend((x, me) for x in self.row_refs(tn, k, lk))
                todo.extend((x, me) for x in self.watch_refs(k))
            else:
                if n[:2] in seen_a:
                    continue
                seen_a.add(n[:2])
                if parents is not None:
                    parents[n[:2]] = (par, n[0])
                todo.extend((x, n[:2]) for x in (self.dsl_refs(n[1]) if n[0] == "dsl" else self.esdl_refs(n[1])))
        return seen_k, miss

    def chain(self, qid, tk, tier=0):
        roots, lv = self.quest_roots[qid]
        par = {}
        self.closure(roots, lv, par, tier)
        node, out = ("key",) + tuple(tk), []
        guard = 0
        while node is not None and guard < 64:
            guard += 1
            p, how = par.get(node, (None, "?"))
            out.append(f"{node[1] if node[0] == 'key' else node[0]}:{node[-1]}"
                       + (f"({how})" if node[0] == "key" else ""))
            node = p
        return " <- ".join(out)

    def zone_roots(self, zone):
        out = []
        zt_all = self.Z.get(zone, {})
        items = zt_all.items() if isinstance(zt_all, dict) else [("0", zt_all)]
        for _, zt in items:
            if not isinstance(zt, str) or not zt:
                continue
            zr = row(zt)
            for c in range(2, 21, 2):
                if c < len(zr) and zr[c] not in ("(None)", ""):
                    out.append(("general_zako", zr[c]))
            for c in range(23, 35, 2):
                if c + 1 < len(zr) and zr[c] not in ("(None)", ""):
                    tn = BOSS_KIND.get(zr[c])
                    if tn:
                        out.append((tn, zr[c + 1]))
                    else:
                        self.notes.add(f"zone {zone}: boss kind {zr[c]} id {zr[c + 1]} 未建模")
        return out

    def run(self):
        self.notes = set()
        self.quest_levels, self.quest_roots, self.lookups, self.missing = {}, {}, {}, {}
        self.quest_tables_seen = 0
        for lp, lc in QUEST_TABLES:
            Q = self.view.table(lp)
            if Q is None:
                continue
            self.quest_tables_seen += 1
            name = lp.split("/")[-1].replace(".orderedmap", "")

            def walk(node, path):
                if isinstance(node, dict):
                    for k, v in node.items():
                        yield from walk(v, path + (k,))
                elif isinstance(node, str) and node:
                    for i, r in enumerate(rows(node)):
                        if r:
                            yield path + ((str(i),) if i else ()), r
            for path, r in walk(Q, ()):
                if lc >= len(r) or not r[lc].lstrip("-").isdigit():
                    continue
                lv = int(r[lc])
                qid = name + ":" + "/".join(path)
                zones = {self.FD_ZONE[c] for c in r if c in self.FD_ZONE}
                if not zones:
                    continue
                self.quest_levels[qid] = lv
                roots = [x for z in sorted(zones) for x in self.zone_roots(z)]
                self.quest_roots[qid] = (roots, lv)
                prev = set()
                for tier in (0, 1, 2):
                    nodes, miss = self.closure(roots, lv, tier=tier)
                    for tk in nodes - prev:
                        if tk[1] in self.T.get(tk[0], {}):
                            self.lookups.setdefault(tk, {}).setdefault(lv, {}).setdefault(qid, tier)
                    for m in miss:
                        self.missing.setdefault(m, {}).setdefault(qid, tier)
                    prev = nodes
        self.gaps = {}
        for (tn, k), byl in self.lookups.items():
            nums = _numeric_keys(self.T[tn][k])
            if not nums:
                continue
            mx = max(nums)
            hit = {qq: t for lv, qs in byl.items() if lv > mx for qq, t in qs.items()}
            if hit:
                tmin = min(hit.values())
                self.gaps[(tn, k)] = {
                    "max": mx, "tier": tmin,
                    "need": max(lv for lv, qs in byl.items() if lv > mx and min(qs.values()) == tmin),
                    "quests": sorted(qq for qq, t in hit.items() if t == tmin)}
        # *_variable:tier0 查到的 general_* 键,variable 表里有该键时同等级也必须有行
        self.var_gaps = {}
        for tn, lp in VARIABLE_TABLES.items():
            V = self.view.table(lp)
            if V is None:
                self.notes.add(f"{lp} 不在视图里,variable 缺口未检查")
                continue
            for (t, k), byl in self.lookups.items():
                if t != tn or not isinstance(V.get(k), dict):
                    continue
                nums = _numeric_keys(V[k])
                vmax = max(nums) if nums else -1
                for lv, qs in byl.items():
                    t0 = [qq for qq, tier in qs.items() if tier == 0]
                    if t0 and lv > vmax:
                        g = self.var_gaps.setdefault((lp, k), {"max": vmax, "need": lv, "quests": set()})
                        g["need"] = max(g["need"], lv)
                        g["quests"].update(t0)
        top = max(self.quest_levels.values()) if self.quest_levels else 0
        self.curve_gaps = {}
        for cn, lp in CURVE_TABLES.items():
            c = self.view.table(lp)
            if not c:
                self.notes.add(f"{cn} 不在视图里(多为 APK 内置表),未检查")
                continue
            if all(str(k).lstrip("-").isdigit() for k in c):
                if max(map(int, c)) < top:
                    self.curve_gaps[(cn, "")] = {"max": max(map(int, c)), "need": top}
            else:
                for k, v in c.items():
                    nums = _numeric_keys(v) if isinstance(v, dict) else []
                    if nums and max(nums) < top:
                        self.curve_gaps[(cn, k)] = {"max": max(nums), "need": top}
        return self


def check_level(args, view: View, old: View | None, rep: Report):
    s = LevelScan(view).run()
    if s.quest_tables_seen == 0 or not s.FD or not s.Z:
        rep.add("WARN", "level", "level.skipped", "视图里缺 quest/field_data/zone 表,等级缺口检查跳过")
        return
    rep.notes.append(f"等级检查: {s.quest_tables_seen} 张 quest 表, {len(s.quest_levels)} 个关卡, "
                     f"等级 {min(s.quest_levels.values(), default=0)}..{max(s.quest_levels.values(), default=0)}, "
                     f"{len(s.lookups)} 个等级表条目被引用")
    if s.missing_tables:
        rep.notes.append("不在视图里的等级表(相关引用按缺键处理): " + ", ".join(
            Path(x).stem for x in s.missing_tables))
    old_gaps = None
    if old is not None:
        try:
            o = LevelScan(old).run()
            old_gaps = set(o.gaps) | {("var",) + k for k in o.var_gaps}
        except Exception as exc:  # noqa: BLE001
            rep.notes.append(f"--since 视图的等级扫描失败,不区分新旧: {exc}")
    for (tn, k), g in sorted(s.gaps.items()):
        if g["tier"] == 0:
            pre = old_gaps is not None and (tn, k) in old_gaps
            rep.add("WARN" if pre else "ERROR", "level", f"level.gap:{tn}:{k}",
                    f"等级缺口 {tn}[{k}] 最高 {g['max']} < 关卡等级 {g['need']}(U_3be147 必崩)"
                    + (",--since 之前就有" if pre else ""),
                    [f"关卡({len(g['quests'])}): {', '.join(g['quests'][:6])}",
                     "路径: " + s.chain(g["quests"][0], (tn, k), 0)])
        else:
            rep.add("INFO", "level", f"level.nameonly:{tn}:{k}",
                    f"仅按名引用(tier{g['tier']},客户端不按等级查) {tn}[{k}] 最高 {g['max']} < {g['need']}",
                    [f"关卡: {', '.join(g['quests'][:4])}"])
    # variable 表走 getSurjectivityWithDefault:没有 >=lv 的键时给空表,不立刻抛;
    # 状态机按变量取值(GeneralEnemy.as resolveVariable,如「指定回数再生(变数)」)时才崩
    # (1.4.202 funnel_discarded_dragon_fire_RE)。官方数据里也有不崩的此类缺口,
    # 所以只有本次推送新引入的(需 --since)记 ERROR,其余记 WARN。
    for (lp, k), g in sorted(s.var_gaps.items()):
        new = old_gaps is not None and ("var", lp, k) not in old_gaps
        qs = sorted(g["quests"])
        rep.add("ERROR" if new else "WARN", "level", f"level.var_gap:{Path(lp).stem}:{k}",
                f"variable 缺口 {Path(lp).stem}[{k}] 最高 {g['max']} < 关卡等级 {g['need']}"
                f"(变量表取空,状态机用到变量时崩)" + (",本次新引入" if new else ""),
                [f"关卡({len(qs)}): {', '.join(qs[:6])}"])
    for (cn, k), g in sorted(s.curve_gaps.items()):
        rep.add("ERROR", "level", f"level.curve:{cn}:{k}",
                f"曲线表 {cn}{'[' + k + ']' if k else ''} 最高 {g['max']} < 最高关卡等级 {g['need']}")
    for (tn, k), qs in sorted(s.missing.items()):
        if min(qs.values()) != 0 or view.table(LEVEL_TABLES[tn]) is None:
            continue
        rep.add("WARN", "level", f"level.missing_key:{tn}:{k}",
                f"zone/DSL 引用了不存在的 {tn}[{k}]", [f"关卡: {', '.join(sorted(qs)[:4])}"])
    for n in sorted(s.notes):
        rep.notes.append(n)
