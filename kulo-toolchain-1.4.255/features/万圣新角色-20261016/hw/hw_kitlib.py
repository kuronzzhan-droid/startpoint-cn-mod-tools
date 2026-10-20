# -*- coding: utf-8 -*-
"""万圣四角色 kit 公共库：按字段名装行、DSL 小构件、闸门。"""
from __future__ import annotations

import zlib

import hw_env  # noqa: F401
import wf_describe as D
import wf_midautumn_kitlib as KL
import wf_client_legality as L
import wf_dsl

EM = D.enum_map()
TOK = ("Red", "Blue", "Yellow", "Green", "White", "Black")
ELW = ("火", "水", "雷", "风", "光", "暗")
_COLS: dict = {}


def col(table: str, name: str) -> int:
    if table not in _COLS:
        lay = D.layout(table)
        m = {}
        for block, start in lay["blocks"].items():
            fb = EM["block_fields"]["precondition" if block.startswith("precondition") else block]
            for o, n, _ in fb:
                m[f"{block}.{n}"] = int(start) + int(o)
        _COLS[table] = m
    return _COLS[table][name]


DONOR = {  # (table, mode) -> 官方最简 donor
    ("leader_ability", "static"): "161004#0",
    ("leader_ability", "trig"): "151033#1",
    ("leader_ability", "during"): "161004#1",
    ("ability", "static"): "3410034#0",
    ("ability", "trig"): "1510331#0",
    ("ability", "during"): "1610041#0",
}

TARGET = {"self": 0, "except": 1, "leader": 2, "party": 5, "puller": 7, "multiball": 8}
PULLER = {"self": 0, "leader": 1, "except_one": 4, "party_one": 5, "except_total": 6, "party_total": 7}


def pct(x: float) -> str:          # 50 -> "50000"
    return str(int(round(x * 1000)))


def thr(x: float) -> str:          # 3 次 -> "300000"
    return str(int(round(x * 100000)))


def _grp(g):
    return TOK[g] if isinstance(g, int) else g


def row(ctx, table: str, mode: str, f: dict, *, base: dict | None = None, donor: str | None = None,
        source: str = "live", expect: str | None = None, label: str = ""):
    """f：字段名->值；特殊键 pre=[('res',el)|('leaderchar',el)|('kind',k)]。"""
    cells = dict(base or {})
    f = dict(f)
    pre = f.pop("pre", None)
    pres = pre if isinstance(pre, list) else ([pre] if pre else [])
    for i, p in enumerate(pres, start=1):
        b = f"precondition{i}"
        if p[0] == "res":
            cells[col(table, f"{b}.kind")] = "2"
            cells[col(table, f"{b}.threshold.power1")] = "600000"
            cells[col(table, f"{b}.threshold.first_max")] = "600000"
            cells[col(table, f"{b}.character_groups")] = TOK[p[1]]
        elif p[0] == "leaderchar":
            cells[col(table, f"{b}.kind")] = "43"
            cells[col(table, f"{b}.threshold.power1")] = ""
            cells[col(table, f"{b}.threshold.first_max")] = ""
            cells[col(table, f"{b}.character_groups")] = TOK[p[1]]
        elif p[0] == "none":
            for n in ("kind", "threshold.power1", "threshold.first_max", "character_groups"):
                cells[col(table, f"{b}.{n}")] = "0" if n == "kind" else ""
        else:
            cells[col(table, f"{b}.kind")] = str(p[1])
            if len(p) > 2:
                cells[col(table, f"{b}.threshold.power1")] = thr(p[2])
                cells[col(table, f"{b}.threshold.first_max")] = thr(p[2])
    for k, v in f.items():
        cells[col(table, k)] = "" if v is None else str(v)
    d = donor or DONOR[(table, mode)]
    return KL.build_row(ctx, table, d, cells, source=source, expect_describe=expect, label=label or d)


def static(content_kind, target, value, *, group=None, pre=None, unique=None, raw=None, **extra):
    p = "instant_content"
    v = raw if raw is not None else pct(value)
    f = {f"{p}.kind": content_kind, f"{p}.target": TARGET.get(target, target),
         f"{p}.strength.power1": v, f"{p}.strength.first_max": v}
    if group is not None:
        f[f"{p}.target.character_groups"] = _grp(group)
    if unique is not None:
        f[f"{p}.unique_condition_id"] = unique
    if pre:
        f["pre"] = pre
    f.update(extra)
    return ("static", f)


def trig(trigger_kind, content_kind, target, value, *, puller="self", puller_group=None, threshold=1,
         limit="(None)", ct=0, group=None, pre=None, unique=None, raw=None, **extra):
    t, p = "instant_trigger", "instant_content"
    v = raw if raw is not None else pct(value)
    f = {f"{t}.kind": trigger_kind, f"{t}.trigger_puller": PULLER.get(puller, puller),
         f"{t}.threshold.power1": thr(threshold), f"{t}.threshold.first_max": thr(threshold),
         f"{t}.trigger_limit": limit, f"{t}.cooltime": ct,
         f"{p}.kind": content_kind, f"{p}.target": TARGET.get(target, target),
         f"{p}.strength.power1": v, f"{p}.strength.first_max": v}
    if puller_group is not None:
        f[f"{t}.trigger_puller.character_groups"] = _grp(puller_group)
    if group is not None:
        f[f"{p}.target.character_groups"] = _grp(group)
    if unique is not None:
        f[f"{p}.unique_condition_id"] = unique
    if pre:
        f["pre"] = pre
    f.update(extra)
    return ("trig", f)


def during(trigger_kind, content_kind, target, value, *, puller="self", threshold=None, limit=None,
           group=None, pre=None, unique=None, **extra):
    t, p = "during_trigger", "during_content"
    f = {f"{t}.kind": trigger_kind, f"{p}.kind": content_kind, f"{p}.target": TARGET.get(target, target),
         f"{p}.strength.power1": pct(value), f"{p}.strength.first_max": pct(value)}
    if threshold is not None:
        f[f"{t}.trigger_puller"] = PULLER.get(puller, puller)
        f[f"{t}.threshold.power1"] = thr(threshold)
        f[f"{t}.threshold.first_max"] = thr(threshold)
    if limit is not None:
        f[f"{t}.trigger_limit"] = limit
    if unique is not None:
        f[f"{t}.unique_condition_id"] = unique
    if group is not None:
        f[f"{p}.target.character_groups"] = _grp(group)
    if pre:
        f["pre"] = pre
    f.update(extra)
    return ("during", f)


def build_leader(ctx, plan):
    rows, evs = [], []
    for i, (label, (mode, f), *opt) in enumerate(plan):
        donor = opt[0] if opt else None
        r, ev = row(ctx, "leader_ability", mode, f, base={0: ctx.spec.code}, donor=donor, label=f"L{i}:{label}")
        rows.append(r)
        evs.append(ev | {"tag": label})
    return rows, evs


def build_abilities(ctx, plan: dict):
    """plan：slot -> (unisonable 'true'/'false', [(label,(mode,f)[,donor]),...])"""
    out, evs = {}, []
    code = ctx.spec.code
    for slot, (uni, recs) in plan.items():
        key = f"{ctx.spec.cid}{slot}"
        rows = []
        for i, (label, (mode, f), *opt) in enumerate(recs):
            donor = opt[0] if opt else None
            base = {0: f"{code}_{slot}", 1: uni}
            r, ev = row(ctx, "ability", mode, f, base=base, donor=donor, label=f"A{slot}.{i}:{label}")
            rows.append(r)
            evs.append(ev | {"tag": label, "key": key})
        for r in rows:
            r[2] = rows[0][2]
        KL.check_ability_key(rows, key, code, slot)
        out[key] = rows
    return out, evs


# ---------------------------------------------------------------- DSL 构件
def S(a, b=None):
    return [{"min": a, "max": a if b is None else b}]


def C(*args):
    return ["Command", list(args)]


def Blk(*stmts):
    return ["Block", list(stmts)]


def wait(frames, *stmts):
    return ["Event", ["Wait", frames, "*", Blk(*stmts)]]


def cond(subject, ac, *, cancel=True, kind=3, key=""):
    return C("CreateCondition", subject, [ac], S(1), ["GenericConditionHitEffect"], cancel, False, key, None,
             False, kind, S(1), False)


def find_all(bind, selector, *stmts):
    return C("FindAllSubjects", bind, selector, [], [], [], [], [], ["DoNothing"], Blk(*stmts))


def dsl_gate(tree, element=None) -> list:
    probs = []
    probs += L.action_dsl_lookup_scope_problems(tree)
    probs += L.action_dsl_subject_binding_problems(tree)
    if element is not None:
        probs += L.action_dsl_element_problems(tree, element)
    enc = wf_dsl.encode_amf3(tree)
    if wf_dsl.parse_dsl(enc)["tree"] != tree:
        probs.append("amf roundtrip mismatch")
    return probs


def deflate(data: bytes) -> bytes:
    co = zlib.compressobj(9, zlib.DEFLATED, -15)
    return co.compress(data) + co.flush()


def write_dsl(ctx, program: str, tree, element=None) -> str:
    probs = dsl_gate(tree, element)
    if probs:
        raise KL.KitError(f"{program}: DSL gate {probs[:6]}")
    lg = wf_dsl.dsl_logical(program)
    ctx.pack.write_pkg("common", lg, deflate(wf_dsl.encode_amf3(tree)))
    back = wf_dsl.parse_dsl(zlib.decompress(ctx.pack.pkg_path("common", lg).read_bytes(), -15))["tree"]
    assert back == tree, program
    return lg


def load_tree(ctx, program: str, prefer_pkg: bool = False):
    import wf_assets
    lg = wf_dsl.dsl_logical(program)
    p = ctx.pack.pkg_path("common", lg)
    loc = wf_assets.locate(hw_env.STORE, lg)
    if prefer_pkg and p.is_file():
        raw = p.read_bytes()
    elif loc is not None:
        raw = loc[1].read_bytes()
    else:   # 标准弹射树只在 APK bundle(research/apk_pf 从 v33 APK 抽出)
        name = program.rsplit("$", 1)[-1]
        raw = (hw_env.OUT / "research" / "apk_pf" / f"{name}.deflate").read_bytes()
    return wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]


def walk(node, fn):
    """深度优先：fn(list_node) 可返回替换节点。"""
    if isinstance(node, list):
        for i, x in enumerate(node):
            if isinstance(x, list):
                y = fn(x)
                if y is not None:
                    node[i] = y
                else:
                    walk(x, fn)
            elif isinstance(x, dict):
                walk(list(x.values()), fn)
    return node


def find_nodes(node, name, out=None):
    out = [] if out is None else out
    if isinstance(node, list):
        if node and node[0] == name:
            out.append(node)
        for x in node:
            find_nodes(x, name, out)
    return out


def sync_skill_text(ctx):
    """character_text c4–c7（技能名/描述两档）跟 action_skill c0/c1 对齐，并重建服务端镜像。"""
    import wf_seasonal7_common as C7
    TEXT = "master/character/character_text.orderedmap"
    cid = ctx.spec.cid_s
    row = C7.csv_split(ctx.pkg_flat(TEXT)[cid])[0]
    inner = ctx.pkg_nested(ctx.spec.code)
    row[4], row[5] = inner["1"][0], inner["1"][1]
    row[6], row[7] = inner["2"][0], inner["2"][1]
    ctx.write_flat(TEXT, {cid: [row]})
    return ctx.sync_character_mirrors()
