"""Read-only, request-isolated adapter for the existing tower builder.

Legacy builders keep module caches. Private module instances avoid changing global
store configuration or leaking one view's caches into another concurrent request.
Only table/resource reads are exposed; no filesystem store is materialized.
"""
from __future__ import annotations

import copy
import importlib.util
import io
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import wf_quest_lib as q


class ReadMember:
    def __init__(self, loader, logical):
        self.loader, self.logical = loader, logical

    def read_bytes(self):
        return self.loader(self.logical)

    def is_file(self):
        try:
            self.read_bytes()
            return True
        except FileNotFoundError:
            return False


@contextmanager
def isolated_builder(loader):
    """Load only trusted checkout code, with private caches and read-only IO."""
    from . import rogue_build, rogue_bundle
    from wf.tools.content import chain_build
    from wf.tools.boss import boss
    modules = []
    reader = SimpleNamespace(load_table=lambda logical: q.parse_node(loader(logical)),
                             store_path=lambda logical: ReadMember(loader, logical),
                             hashed_rel=q.hashed_rel)
    try:
        for original in (rogue_bundle, chain_build, boss, rogue_build):
            name = "_wf_candidate_" + uuid.uuid4().hex
            spec = importlib.util.spec_from_file_location(name, original.__file__)
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            modules.append(module)
            # exec_module may write a pyc; previews deliberately perform no writes.
            exec(compile(Path(original.__file__).read_bytes(), original.__file__, "exec"), module.__dict__)
            module.q = reader
        builder = modules[-1]
        builder.rbb, builder.cb, builder.wb = modules[:3]
        builder.wb._load = reader.load_table
        yield builder
    finally:
        for module in modules:
            sys.modules.pop(module.__name__, None)


def collect_candidate(state):
    """Collect the already validated CLI memory state before its write branch."""
    from . import rogue_build as b
    tables = {b.GENERAL_ZAKO: state["gz_t"], b.ZAKO_LEVEL: state["zl_t"],
              b.GENERAL_BOSS: state["gb_t"], b.BOSS_LEVEL: state["bl_t"],
              b.GENERAL_BOSS_VARIABLE: state["gv_t"], b.ENEMY_WATCH: state["ew_t"],
              b.OROCHI: state["oro_t"], b.FIELD_DATA_T: state["fd_t"], b.ZONE_T: state["zone_t"]}
    plan = b.rogue_battle_write_plan(gimmick_dirty=state["gim_dirty"],
        caster_dirty=state["caster_dirty"], orochi_dirty=state["orochi_dirty"],
        enemy_watch_available=state["ew_t"] is not None)
    tables = {logical: tables[logical] for logical in plan}
    ev, fo, qt = (copy.deepcopy(state[key]) for key in ("ev", "fo", "qt"))
    ev[b.EVENT_ID] = b.join(state["ev_row"], state["ev_bytes"])
    fo[b.EVENT_ID] = {"1": b.join(state["fo_row"], state["fo_bytes"]),
                      "2": b.join(state["fo_endless"], state["fo_bytes"])}
    qt[b.EVENT_ID] = {k: b.join(v, state["qt_bytes"]) for k, v in state["quest_rows"].items()}
    tables.update({b.Q_EVENT: ev, b.Q_FOLDER: fo, b.Q_QUEST: qt})
    return {"tables": tables, "rows": state["quest_rows"], "checks": state["reports"],
            "floors": [{"round": f["r"], "pick": {k: f["pick"].get(k) for k in
                        ("field", "label", "bosses", "level", "elem")},
                        "effects": f["curse"].get("desc"), "hp": f["hp_audit"]}
                       for f in state["floor_recs"]],
            "programs": state["immunity_programs"], "dependencies": sorted(state["forged_pubs"])}


def build_candidate(loader, *, seed: int, rounds: int):
    """Pure candidate compiler. No save DB, HTTP, publish, history or device IO."""
    from wf.tools.core import field_catalog as fields
    from . import rogue_build as b
    if type(seed) is not int or not 0 <= seed <= 2**32 - 1:
        raise ValueError("种子必须是 0–4294967295 的整数")
    if type(rounds) is not int or not 2 <= rounds <= 98:
        raise ValueError("当前塔轮数必须在 2–98 之间")
    files, results, logs = {}, [], io.StringIO()

    def forge(program, factor):
        name, raw = fields.forge_bytes(program, loader(program + ".action.dsl.amf3.deflate"), scale=factor)
        files[name + ".action.dsl.amf3.deflate"] = raw
        return name

    with isolated_builder(loader) as builder:
        # Keep output local to this call, without process-global redirect_stdout.
        builder.print = lambda *args, **kw: print(*args, **{**kw, "file": logs})
        # Keep the existing layout, field tuning and history read semantics.
        # Studio never writes history; saved output hashes guard replay drift.
        rc = builder.main(["--seed", str(seed), "--rounds", str(rounds)],
                          candidate_sink=results.append, forge_candidate=forge)
        if not rc and results:
            from .rogue_validate import validate_candidate_references
            results[0]["checks"] = validate_candidate_references(
                results[0]["rows"], results[0]["tables"], builder)
    if rc or not results:
        raise ValueError("重抽构建门禁失败：\n" + logs.getvalue()[-14000:])
    result = results[0]
    tables = result.pop("tables")
    el, corr = q.parse_node(loader(b.Q_LIST)), q.parse_node(loader(b.Q_CORR))
    el[b.EVENT_ID] = b.join(["11", b.EVENT_ID, b.EVENT_ID], isinstance(el[b.TEMPLATE_EVENT], bytes))
    corr[b.EVENT_ID] = {"2": {b.ENDLESS_KEY: copy.deepcopy(corr[b.TEMPLATE_EVENT]["4"]["8"])}}
    tables.update({b.Q_LIST: el, b.Q_CORR: corr})
    files.update({logical: q.build_node(tree) for logical, tree in tables.items()})
    files.update({program + ".action.dsl.amf3.deflate": b.build_immunity_dsl_blob(tree)
                  for program, tree in result.pop("programs").items()})
    for logical in result.pop("dependencies"):
        if logical not in files:
            files[logical] = loader(logical)
    return {**result, "files": files, "log": logs.getvalue(), "seed": seed, "rounds": rounds}
