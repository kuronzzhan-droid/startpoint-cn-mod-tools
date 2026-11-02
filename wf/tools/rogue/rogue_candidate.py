"""Request-isolated, read-only adapter for the online normal and EX builders."""
from __future__ import annotations

import copy
import io
import importlib.util
import re
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


def configure_builder_event(builder, event_id):
    """Bind a fresh private builder to a supported event for overlay checks."""
    event_id = str(event_id)
    if event_id not in ("700099", "700100"):
        raise ValueError("只支持深渊连战 700099 与深渊 EX 700100")
    builder.EVENT_ID = event_id
    builder.BUILD_MODE = "ex" if event_id == "700100" else "normal"
    builder.PRIVATE_PREFIX = "mod_abyss_ex_" if event_id == "700100" else "mod_rogue_"
    builder.EVENT_STRING_ID = builder.PRIVATE_PREFIX + "gauntlet"
    builder.EVENT_NAME = "深渊连战 EX" if event_id == "700100" else "深渊连战"


@contextmanager
def isolated_builder(loader, *, server_asset_reader=None):
    """Load trusted checkout code with private caches and the exact view reader.

    Server rewards are separate local JSON inputs. Callers may freeze them with
    ``server_asset_reader``; otherwise the profile resolves their read-only mirror.
    """
    from . import rogue_build, rogue_bundle
    from wf.tools.content import chain_build
    from wf.tools.boss import boss
    modules = []

    def raw(logical, path=None):
        return Path(path).read_bytes() if path is not None else loader(logical)

    def load(logical, path=None):
        tree = q.parse_node(raw(logical, path))
        if not isinstance(tree, dict):
            raise ValueError(f"{logical} 顶层不是 map")
        return tree

    reader = SimpleNamespace(load_table=load, read_raw=raw,
        exists_current=lambda logical: ReadMember(loader, logical).is_file(),
        store_path=lambda logical: ReadMember(loader, logical),
        hashed_rel=q.hashed_rel, parse_node=q.parse_node, build_node=q.build_node)
    try:
        for original in (rogue_bundle, chain_build, boss, rogue_build):
            name = "_wf_candidate_" + uuid.uuid4().hex
            spec = importlib.util.spec_from_file_location(name, original.__file__)
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            modules.append(module)
            # No pyc or store writes are needed for previews.
            exec(compile(Path(original.__file__).read_bytes(), original.__file__, "exec"), module.__dict__)
            module.q = reader
        builder = modules[-1]
        builder.rbb, builder.cb, builder.wb = modules[:3]
        builder.wb._load = reader.load_table
        if server_asset_reader is not None:
            builder.load_server_asset = server_asset_reader
        yield builder
    finally:
        for module in modules:
            sys.modules.pop(module.__name__, None)


def collect_candidate(state, *, builder=None):
    """Collect exactly the CLI write plan before any output or server mutation."""
    if builder is None:
        from . import rogue_build as builder
    b = builder
    tables = {b.GENERAL_ZAKO: state["gz_t"], b.ZAKO_LEVEL: state["zl_t"],
              b.GENERAL_BOSS: state["gb_t"], b.GENERAL_BOSS_STATE: state["gbs_t"],
              b.BOSS_LEVEL: state["bl_t"], b.GENERAL_BOSS_VARIABLE: state["gv_t"],
              b.ENEMY_WATCH: state["ew_t"], b.OROCHI: state["oro_t"],
              b.OROCHI_EX_HEAD: state["oro_ex_head_t"], b.OROCHI_EX: state["oro_ex_t"],
              b.STANDARD_BOSS: state["sb_t"], b.FIELD_DATA_T: state["fd_t"],
              b.ZONE_T: state["zone_t"]}
    tables.update({str(b.SINGLE_BAR_SPECIAL_SPECS[family]["logical"]): tree
                   for family, tree in state["single_bar_special_tables"].items()})
    tables.update({str(b.SPHERE_SPECS[family]["logical"]): tree
                   for family, tree in state["sphere_tables"].items()})
    tables.update({str(b.SPHERE_AUX_LOGICALS[name]): tree
                   for name, tree in state["sphere_aux_tables"].items()})
    plan = b.rogue_battle_write_plan(
        gimmick_dirty=state["gim_dirty"], caster_dirty=state["caster_dirty"],
        orochi_dirty=state["orochi_dirty"], enemy_watch_available=state["ew_t"] is not None,
        general_state_dirty=state["general_state_dirty"], standard_dirty=state["standard_dirty"],
        orochi_ex_dirty=state["orochi_ex_dirty"],
        single_bar_special_dirty=tuple(sorted(state["single_bar_special_dirty"])),
        sphere_dirty=tuple(sorted(state["sphere_dirty"])))
    tables = {logical: copy.deepcopy(tables[logical]) for logical in plan}
    rebuilt = {}
    aux_logicals = set(b.SPHERE_AUX_LOGICALS.values())
    families = ("boss", "caster", "f", "z", "standard", "orochi", "orochi_ex",
                *b.SINGLE_BAR_SPECIAL_SPECS, *b.SPHERE_SPECS)
    generated = re.compile(re.escape(b.PRIVATE_PREFIX) +
        "(?:" + "|".join(re.escape(family) for family in families) +
        r")\d+(?:_(?:\d+|head\d+|state|g\d+c\d+))*$")
    for logical, tree in tables.items():
        if logical == b.ENEMY_WATCH:
            continue
        before = b.q.load_table(logical)
        keys = [str(key) for key, value in tree.items()
                if generated.fullmatch(str(key))
                or str(key) == b.PRIVATE_PREFIX + "final_pair"
                or logical in aux_logicals and before.get(key) != value]
        if keys:
            rebuilt[logical] = keys
    ev, fo, qt = (copy.deepcopy(state[key]) for key in ("ev", "fo", "qt"))
    ev[b.EVENT_ID] = b.join(state["ev_row"], state["ev_bytes"])
    fo[b.EVENT_ID] = {"1": state["folder_leaf"], "2": b.join(state["fo_endless"], state["fo_bytes"])}
    qt[b.EVENT_ID] = {key: b.join(row, state["qt_bytes"]) for key, row in state["quest_rows"].items()}
    tables.update({b.Q_EVENT: ev, b.Q_FOLDER: fo,
                   b.Q_QUEST: b.enforce_gauntlet_quest_table_player_rank(qt)})
    event_list = b.enforce_gauntlet_hub_event_list(b.q.load_table(b.Q_LIST))
    correction = b.q.load_table(b.Q_CORR)
    correction[b.EVENT_ID] = {"2": {b.ENDLESS_KEY: dict(correction[b.TEMPLATE_EVENT]["4"]["8"])}}
    tables.update({b.Q_LIST: event_list, b.Q_CORR: correction})
    if b.BUILD_MODE == "ex":
        config = b.load_server_asset("rogue_event.json")["events"][b.EVENT_ID]
        try:
            extension = b.load_server_asset("rogue_event_cnmod.json")
        except FileNotFoundError:
            extension = {}
        config = {**config, **extension.get("events", {}).get(b.EVENT_ID, {})}
        logical = "master/reward/event/additional_reward.orderedmap"
        reward_table = b.q.load_table(logical)
        reward_table.update(b.abyss_modes.additional_reward_rows(config))
        tables[logical] = reward_table
    return {"tables": tables, "rows": state["quest_rows"], "checks": state["reports"],
            "eventId": b.EVENT_ID, "rebuiltKeys": rebuilt,
            "floors": [{"round": f["r"], "pick": {key: f["pick"].get(key) for key in
                        ("field", "label", "bosses", "level", "elem")},
                        "effects": f["curse"].get("desc"), "hp": f["hp_audit"]}
                       for f in state["floor_recs"]],
            "programs": state["immunity_programs"], "resources": state["standard_resource_blobs"],
            "dependencies": sorted(state["forged_pubs"])}


def build_candidate(loader, *, seed: int, rounds: int, event_id="700099", server_asset_reader=None):
    """Compile normal/EX output with no store, DB, network or device writes."""
    from wf.tools.core import field_catalog as fields
    event_id = str(event_id)
    if event_id not in ("700099", "700100"):
        raise ValueError("只支持深渊连战 700099 与深渊 EX 700100")
    if type(seed) is not int or not 0 <= seed <= 2**32 - 1:
        raise ValueError("种子必须是 0–4294967295 的整数")
    if type(rounds) is not int or not 2 <= rounds <= 98:
        raise ValueError("当前塔轮数必须在 2–98 之间")
    if event_id == "700100" and rounds != 30:
        raise ValueError("深渊 EX 必须是 30 层")
    files, results, logs = {}, [], io.StringIO()

    def forge(program, factor):
        name, blob = fields.forge_bytes(program, loader(program + ".action.dsl.amf3.deflate"), scale=factor)
        files[name + ".action.dsl.amf3.deflate"] = blob
        return name

    mode = "ex" if event_id == "700100" else "normal" if rounds == 30 else "legacy"
    with isolated_builder(loader, server_asset_reader=server_asset_reader) as builder:
        builder.print = lambda *args, **kw: print(*args, **{**kw, "file": logs})
        rc = builder.main(["--seed", str(seed), "--rounds", str(rounds), "--mode", mode],
                          candidate_sink=results.append, forge_candidate=forge)
        if not rc and results:
            from .rogue_validate import validate_candidate_references
            results[0]["checks"] = validate_candidate_references(results[0]["rows"], results[0]["tables"], builder)
        if rc or not results:
            raise ValueError("重抽构建门禁失败：\n" + logs.getvalue()[-14000:])
        result = results[0]
        files.update({logical: q.build_node(tree) for logical, tree in result.pop("tables").items()})
        files.update({program + ".action.dsl.amf3.deflate": builder.build_immunity_dsl_blob(tree)
                      for program, tree in result.pop("programs").items()})
    files.update(result.pop("resources"))
    for logical in result.pop("dependencies"):
        if logical not in files:
            files[logical] = loader(logical)
    return {**result, "files": files, "log": logs.getvalue(), "seed": seed, "rounds": rounds}
