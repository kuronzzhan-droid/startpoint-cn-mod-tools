# -*- coding: utf-8 -*-
"""五重 layer0 图集门禁模拟器（只读）。

客户端口径（反编译 AS3，路径相对 D:/WF/_archive/kept/弹国服-tools-and-decompile/scripts）：
- 分层：BattleStartProductionViewService.autoDistribute —— image/dynamicTexture 全进 layer1；
  spriteSheet 按 LAYER0_RULES 的正则顺序判定（逐条照抄，含 layer1 分支的先后顺序）。
- 打包：pack(name, target, 4096, 4096) + StarlingAtlasBuilder(..., 4096, 4096, margin=2)；
  每张 sprite sheet 整张作为一个矩形（ceil(frameW) x ceil(frameH) = PNG 尺寸）。
- MaxRectsPacker 1:1 移植（pack / allocateRectangle / splitRectangle / pruneFreeRectangles）：
  pending 按 compareArea 升序排序后从尾部 pop（面积大者先放）；allocate 把长边竖放、两边 +margin，
  评分 min(free.w-pw, free.h-ph)，取最小非负；找不到即 throw "size exceeded"（U_1d93f4）。
  compareArea 同面积不同名时恒返回 -1（AS3 原 bug，排序不稳定），这里同面积按名字降序 pop，属近似。
- 精灵表推导：AssetPathCollectionBuilder.addAnimationLayout（battle/ 目录名写两遍；character/ 取 sprite_sheet；
  battle/common* 不推导）。
- boss：ZoneSourceValues.resolveGeneralBosssAction 预载 pre_action(c109) + enemy_action01..50(c111..c160)，
  属性 = toOppositeElementKind(fromBossElementKind(c0), recommended)；GeneralBossSource.resolvePathCollection
  动画列（c25 marker 只进 timeline，不推导表）+ 通用晕眩/死亡特效。
- DSL 闭包：遍历 DSL 树里所有字符串（battle/action/ 递归；其余 battle/ character/ 当动画），
  ResolveByElement(base, el) 按 resolveElement 展开属性变体；SpawnFunnel/Zako 按表取召唤物整行。
  这比 ActionDslAssetResolver 的逐构造解析略宽（可能多算，不会少算 boss 侧大表）。
- 角色：像素表(主位 3 人) + 技能 DSL 闭包(6 人) + 词条行里的 DSL + 队长的 PF（类型 PF + 队长词条 override）。
"""
from __future__ import annotations

import functools, os, re, struct, sys, zlib
os.environ.setdefault("WF_TIP", "195")
from p192_common import *  # noqa: F401,F403  (aread, base149, load, rows, row, SALT, Path ...)
import p192_common as P
import wf_dsl

MARGIN, ATLAS = 2, 4096
CAP = ATLAS * ATLAS

# ---------------------------------------------------------------- MaxRectsPacker port
class Overflow(Exception):
    pass


class _R:
    __slots__ = ("x", "y", "w", "h")

    def __init__(self, x, y, w, h):
        self.x, self.y, self.w, self.h = x, y, w, h


def _split(f, p, out):
    if p.x >= f.x + f.w or p.x + p.w <= f.x or p.y >= f.y + f.h or p.y + p.h <= f.y:
        return False
    if p.x < f.x + f.w and p.x + p.w > f.x:
        if f.y < p.y < f.y + f.h:
            out.append(_R(f.x, f.y, f.w, p.y - f.y))
        if f.y < p.y + p.h < f.y + f.h:
            out.append(_R(f.x, p.y + p.h, f.w, f.y + f.h - (p.y + p.h)))
    if p.y < f.y + f.h and p.y + p.h > f.y:
        if f.x < p.x < f.x + f.w:
            out.append(_R(f.x, f.y, p.x - f.x, f.h))
        if f.x < p.x + p.w < f.x + f.w:
            out.append(_R(p.x + p.w, f.y, f.x + f.w - (p.x + p.w), f.h))
    return True


def _prune(free):
    drop = []
    n = len(free)
    for i in range(n):
        a = free[i]; aa = a.w * a.h
        for j in range(i + 1, n):
            b = free[j]; bb = b.w * b.h
            s, g = (a, b) if aa < bb else (b, a)
            if s.x >= g.x and s.x + s.w <= g.x + g.w and s.y >= g.y and s.y + s.h <= g.y + g.h:
                drop.append(s)
                if aa < bb:
                    break
    for r in drop:
        for k, f in enumerate(free):      # Array.remove = first identical element
            if f is r:
                del free[k]; break


def pack(items, max_w=ATLAS, max_h=ATLAS, margin=MARGIN):
    """items [(name,w,h)] -> (used_w, used_h, placements). Raises Overflow like allocateRectangle."""
    pending = sorted(items, key=lambda t: (t[1] * t[2], t[0]))
    free = [_R(0, 0, max_w, max_h)]
    placed = {}
    while pending:
        name, w, h = pending.pop()
        rot = w > h
        pw = (h if rot else w) + margin
        ph = (w if rot else h) + margin
        best, score = None, max(max_w, max_h) + 1
        for f in free:
            s = min(f.w - pw, f.h - ph)
            if 0 <= s < score:
                best, score = f, s
        if best is None:
            raise Overflow(f"{name} ({w}x{h}) after {len(placed)} rects")
        p = _R(best.x, best.y, pw, ph)
        rem, add = [], []
        for f in free:
            if _split(f, p, add):
                rem.append(f)
        for r in rem:
            for k, f in enumerate(free):
                if f is r:
                    del free[k]; break
        free.extend(add)
        _prune(free)
        placed[name] = (p.x, p.y, pw - margin, ph - margin, rot)
    uw = max((x + w for x, y, w, h, _ in placed.values()), default=0)
    uh = max((y + h for x, y, w, h, _ in placed.values()), default=0)
    return uw, uh, placed


# ---------------------------------------------------------------- autoDistribute (spriteSheet branch, in order)
LAYER0_RULES = [  # (regex, layer)
    (r"^battle/common/layer0$", 0), (r"^battle/common/layer1$", 1), (r"^battle/common/boss_rush_layer1$", 1),
    (r"^battle/common/disguise_hp$", 1), (r"^battle/common/score_attack$", 1), (r"^battle/common/attention$", 1),
    (r"^battle/effect/", 0), (r"^battle/field_object/", 0), (r"^battle/boss/", 0), (r"^battle/zako/", 0),
    (r"^battle/funnel/", 0), (r"^battle/tutorial/", 1), (r"^character/.+/pixelart/", 0), (r"^item/sprite_sheet$", 1),
    (r"battle/field/", 0), (r"^battle/uncommon/layer0/", 0), (r"^battle/uncommon/layer1/", 1),
    (r"^battle/common/score_attack2$", 1),
]
_RULES = [(re.compile(p), l) for p, l in LAYER0_RULES]


def layer_of(sheet):
    for rx, l in _RULES:
        if rx.search(sheet):
            return l
    raise ValueError("UNDEFINED LAYER : " + sheet)


def sheet_of(anim):
    if not (anim.startswith("character") or anim.startswith("battle")) or anim.startswith("battle/common"):
        return None
    parts = anim.split("/")
    if anim.startswith("character/"):
        return "/".join(parts[:-1] + ["special_sprite_sheet" if parts[-1] == "special" else "sprite_sheet"])
    parts = parts[:-1]
    if not parts:
        return None
    d = parts.pop()
    return "/".join(parts + [d, d])


ELEM = {0: "red", 1: "blue", 2: "yellow", 3: "green", 4: "white", 5: "black", 6: "colorless"}


def elem_variant(base, el):
    n = base.rsplit("/", 1)[-1]
    return f"{base}/{n}_{ELEM[el]}/{n}_{ELEM[el]}"


def resolve_element(code, own):
    if code == 255:
        return own
    if 1 <= code <= 7:
        return code - 1
    return None


# ---------------------------------------------------------------- view with overlay
class View:
    def __init__(self, overlay=None):
        self.overlay = dict(overlay or {})     # logical path -> bytes (any root)
        self._t, self._d, self._dims = {}, {}, {}

    def file(self, lp):
        if lp in self.overlay:
            return self.overlay[lp]
        for r in P.ROOTS:
            b = P.aread(r, lp)[0]
            if b is not None:
                return b
        return None

    def table(self, lp):
        if lp not in self._t:
            self._t[lp] = q.parse_node(self.file(lp))
        return self._t[lp]

    def dsl(self, prog):
        if prog not in self._d:
            raw = self.file(wf_dsl.dsl_logical(prog))
            self._d[prog] = None if raw is None else wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]
        return self._d[prog]

    def dims(self, sheet):
        if sheet not in self._dims:
            b = self.file(sheet + ".png")
            self._dims[sheet] = struct.unpack(">II", b[16:24]) if b and b[12:16] == b"IHDR" else None
        return self._dims[sheet]


def tier_row(node, level=80):
    """GeneralEnemySourceHelper.getSurjectivity：取 <= level 的最大档；没有则最小档。"""
    if not isinstance(node, dict):
        return row(node)
    ks = sorted(node, key=int)
    le = [k for k in ks if int(k) <= level]
    return row(node[(le[-1] if le else ks[0])])


T_GB = "master/battle/boss/general_boss.orderedmap"
T_FU = "master/battle/boss/funnel/general_funnel.orderedmap"
T_ZK = "master/battle/zako/general_zako.orderedmap"
T_GEW = "master/battle/boss/general_enemy_watch.orderedmap"


def walk_strings(n, out):
    if isinstance(n, str):
        out.append(n)
    elif isinstance(n, list):
        for x in n:
            walk_strings(x, out)
    elif isinstance(n, dict):
        for x in n.values():
            walk_strings(x, out)


def closure(v, roots, element, anims, summons, seen=None):
    """roots = DSL programs; fills anims (set of anim paths) and summons ({('Funnel'|'Zako', code)})."""
    seen = set() if seen is None else seen
    queue = [r.split(":")[0] for r in roots if r and r not in ("(None)",)]
    while queue:
        prog = queue.pop()
        if prog in seen:
            continue
        seen.add(prog)
        t = v.dsl(prog)
        if t is None:
            continue
        stack = [t]
        while stack:
            n = stack.pop()
            if isinstance(n, list):
                if n and n[0] == "ResolveByElement" and len(n) > 2 and isinstance(n[1], str):
                    el = resolve_element(int(n[2]), element)
                    if el is not None:
                        anims.add(elem_variant(n[1], el))
                if n and n[0] == "SpawnFunnel" and len(n) > 1 and isinstance(n[1], list) and len(n[1]) > 1 \
                        and n[1][0] in ("Funnel", "Zako") and isinstance(n[1][1], str):
                    summons.add((n[1][0], n[1][1]))
                stack.extend(n)
            elif isinstance(n, dict):
                stack.extend(n.values())
            elif isinstance(n, str):
                if n.startswith("battle/action/"):
                    if n not in seen:
                        queue.append(n)
                elif "/" in n and (n.startswith("battle/") or n.startswith("character/")):
                    anims.add(n)
    return seen


def cells_split(c):
    return [x.strip() for x in c.split(",") if x.strip()]


def enemy_assets(v, kind, code, element, level=80, drop_slots=()):
    """kind 'boss'|'Funnel'|'Zako' -> (anims, programs, summons). drop_slots: boss slot numbers (1..50) to ignore."""
    tbl = {"boss": T_GB, "Funnel": T_FU, "Zako": T_ZK}[kind]
    node = v.table(tbl).get(code)
    anims, summons, roots = set(), set(), []
    if node is None:
        return anims, set(), summons, None
    r = tier_row(node, level)
    own = element
    if kind == "boss":
        try:
            ek = int(r[0])
            own = ek - 1 if 1 <= ek <= 7 else element
        except ValueError:
            pass
        for i, c in enumerate(r):
            if i == 25:          # marker_timeline_path: timeline only
                continue
            if 111 <= i <= 160 and (i - 110) in drop_slots:
                continue
            for x in cells_split(c) if i in (109,) or 111 <= i <= 160 else [c]:
                if x.startswith("battle/action/"):
                    roots.append(x)
                elif "/" in x and (x.startswith("battle/") or x.startswith("character/")):
                    anims.add(x)
        anims |= {"battle/boss/general_16dots/common/general_16dots_stun",
                  "battle/boss/common/big_boss_death/big_boss_death_back",
                  "battle/boss/common/big_boss_death/big_boss_death_center",
                  "battle/boss/common/big_boss_death/big_boss_death_front"}
        gew = v.table(T_GEW)
        w = gew.get("1", {}).get(code) if isinstance(gew.get("1"), dict) else None
        if w is not None:
            ss = []
            walk_strings(w, ss)
            for s in ss:
                for x in re.findall(r"battle/action/[^,\"\s]+", s):
                    roots.append(x)
    else:
        # ActionDslHandler case 47 (SpawnFunnel): 召唤物招式按「施法者」属性预载（_loc2_.element），不读召唤物 c0
        for c in r:
            for x in cells_split(c):
                if x.startswith("battle/action/"):
                    roots.append(x)
                elif "/" in x and (x.startswith("battle/") or x.startswith("character/")) and "marker" not in x.rsplit("/", 1)[-1]:
                    anims.add(x)
    progs = closure(v, roots, own, anims, summons)
    return anims, progs, summons, own


def round_assets(v, quest_id, drop=None):
    """quest -> {anim: owner}. drop = {boss_code: set(slots)} (simulate slot removals)."""
    drop = drop or {}
    bbq = v.table("master/quest/boss_battle_quest.orderedmap")
    qrow = None
    for f in bbq.values():
        for fo in (f.values() if isinstance(f, dict) else []):
            if isinstance(fo, dict):
                for k, t in fo.items():
                    rr = rows(t)
                    if rr and rr[0] and rr[0][0] == str(quest_id):
                        qrow = rr[0]
    assert qrow, quest_id
    level = int(qrow[106] or 80)
    fd = row(v.table("master/battle/field_data.orderedmap")[qrow[109]])
    field_id, terrain, zone_ids = fd[0], fd[1], cells_split(fd[2])
    out = {}

    def add(a, owner):
        out.setdefault(a, owner)
    frow = row(v.table("master/battle/field.orderedmap")[field_id])
    for c in frow:
        if "/" in c:
            add(c, "field")
            add(c + "/x", "field")      # field_object dirs referenced without leaf
    zt = v.table("master/battle/zone.orderedmap")
    bosses = []
    for zid in zone_ids:
        zn = zt[zid]
        for zk in (sorted(zn, key=int) if isinstance(zn, dict) else [None]):
            zr = row(zn[zk] if zk is not None else zn)
            for kc, ic in ((23, 24), (25, 26), (27, 28), (29, 30), (31, 32), (33, 34)):
                if zr[kc] == "1" and zr[ic] not in ("", "(None)") and zr[ic] not in bosses:
                    bosses.append(zr[ic])
            for c in zr[35:]:
                if "/" in c:
                    add(c, "zone")
                    add(c + "/x", "zone")
            # zakos c0..c21: (kind, id) pairs
            for i in range(0, 22, 2):
                if zr[i] not in ("", "(None)", "0") and zr[i + 1] not in ("", "(None)"):
                    za, zp, zs, _ = enemy_assets(v, "Zako", zr[i + 1], 0, level)
                    for a in za:
                        add(a, "zako:" + zr[i + 1])
    rec = 0
    done = set()
    for b in bosses:
        anims, progs, summons, own = enemy_assets(v, "boss", b, rec, level, drop.get(b, ()))
        for a in anims:
            add(a, b)
        todo = list(summons)
        while todo:
            k, c = todo.pop()
            if (k, c) in done:
                continue
            done.add((k, c))
            sa, sp, ss, _ = enemy_assets(v, k, c, own, level)
            for a in sa:
                add(a, f"{b}>{k}:{c}")
            todo += list(ss)
    add("battle/common/layer0", "common")
    return out, bosses


def sheets_from_anims(v, anims):
    """{anim: owner} -> {sheet: ((w,h), owner)} for layer0 sheets that exist."""
    out = {}
    for a, owner in sorted(anims.items()):
        s = "battle/common/layer0" if a == "battle/common/layer0" else sheet_of(a)
        if not s or s in out:
            continue
        try:
            if layer_of(s) != 0:
                continue
        except ValueError:
            continue
        d = v.dims(s)
        if d:
            out[s] = (d, owner)
    return out


# ---------------------------------------------------------------- characters
T_CH = "master/character/character.orderedmap"
T_AS = "master/skill/action_skill.orderedmap"
T_PF = "master/skill/power_flip_action.orderedmap"
T_AB = "master/ability/ability.orderedmap"
T_LA = "master/ability/leader_ability.orderedmap"
PF_TYPE = {0: "knight", 1: "fighter", 2: "ranged", 3: "supporter", 4: "special"}


def char_assets(v, cid):
    """-> dict(main=set anims (pixelart), skill=set, leader=set)"""
    r = row(v.table(T_CH)[cid])
    code = r[0]
    el = int(r[3]) if r[3].isdigit() else 0
    res = {"code": code, "main": {f"character/{code}/pixelart/pixelart"}, "skill": set(), "leader": set()}
    ask = r[8] or code
    node = v.table(T_AS).get(ask)
    roots = []
    if node is not None:
        for t in (node.values() if isinstance(node, dict) else [node]):
            rr = row(t)
            if len(rr) > 7:
                roots += cells_split(rr[7])
    abt = v.table(T_AB)
    for aid in r[19:25]:
        n = abt.get(aid)
        if n is None:
            continue
        ss = []
        walk_strings(n, ss)
        for s in ss:
            roots += re.findall(r"battle/action/[^,\"\s]+", s)
    anims, sm = set(), set()
    closure(v, roots, el, anims, sm)
    res["skill"] = anims
    # leader: PF type + overrides named in leader ability row
    pft = v.table(T_PF)
    keys = set()
    try:
        keys.add(PF_TYPE[int(r[6])])
    except (ValueError, KeyError):
        pass
    la = v.table(T_LA).get(r[17])
    if la is not None:
        ss = []
        walk_strings(la, ss)
        cells = set()
        for s in ss:
            cells.update(x.strip() for x in s.replace("\n", ",").split(","))
        keys |= {k for k in pft if k in cells}
        lroots = []
        for s in ss:
            lroots += re.findall(r"battle/action/[^,\"\s]+", s)
    else:
        lroots = []
    proots = list(lroots)
    for k in keys:
        if k in pft:
            proots += cells_split(row(pft[k])[0]) if False else re.findall(r"battle/action/[^,\"\s]+", pft[k])
        else:
            proots += [f"battle/action/power_flip/action/{k}${k}_lv{i}" for i in (1, 2, 3)]
    la_anims = set()
    closure(v, proots, el, la_anims, set())
    res["leader"] = la_anims
    return res


def char_sheets(v, ca, part):
    return {s: d for s, (d, _) in sheets_from_anims(v, {a: ca["code"] for a in ca[part]}).items()}


def area(d):
    return (d[0] + MARGIN) * (d[1] + MARGIN)


def run_pack(sheets):
    items = [(k, d[0], d[1]) for k, d in sheets.items()]
    tot = sum(area(d) for d in sheets.values())
    try:
        w, h, _ = pack(items)
        return dict(ok=True, rects=len(items), area=tot, w=w, h=h, fill=tot / CAP)
    except Overflow as e:
        return dict(ok=False, rects=len(items), area=tot, w=None, h=None, fill=tot / CAP, err=str(e))
