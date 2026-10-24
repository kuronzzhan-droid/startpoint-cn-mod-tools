"""Synthetic runtime proofs for B's reverse-link and mixed-terrain fixes."""
from __future__ import annotations

import ast
import copy
from pathlib import Path
from types import SimpleNamespace

import pytest

import wf_rogue_build as rb
from wf.rules.rogue_lineage import (
    checked_mix_terrain_compatibility, standard_funnel_boss_references,
)


def test_standard_funnel_links_block_cloning_and_relocation(monkeypatch):
    tables = {rb.GENERAL_BOSS: {"owner": ""}, rb.STANDARD_FUNNEL: {
        "core": {"100": "battle/enemy/core"}}}
    monkeypatch.setattr(rb, "_tbl", lambda name: tables.get(name, {}))
    monkeypatch.setattr(rb.rbb, "_decoded_store_tree", lambda path: {
        "bG": "owner", "au": [{"h": [{"a": ["T1", 0, "standard_owner"]}]}]})
    refs = rb.code_referenced_bosses(tables[rb.GENERAL_BOSS])
    assert not refs["degraded"]
    assert "owner" in refs["hard"]
    assert refs["standard_identity_references"] == {"owner", "standard_owner"}
    for code in ("owner", "standard_owner"):
        assert rb.identity_locked_boss_reason([code], code_references=refs)
        assert rb.identity_locked_mix_reason([code], "a", "b", code_references=refs)


def test_unreadable_standard_funnel_scan_fails_closed(monkeypatch):
    monkeypatch.setattr(rb, "_tbl", lambda name: {
        "core": "battle/enemy/core"} if name == rb.STANDARD_FUNNEL else {})

    def missing(path):
        raise FileNotFoundError(path)

    monkeypatch.setattr(rb.rbb, "_decoded_store_tree", missing)
    refs = rb.code_referenced_bosses({"owner": ""})
    assert refs["degraded"]
    assert "降级" in rb.identity_locked_boss_reason(["owner"], code_references=refs)


def test_standard_funnel_scan_reads_every_level_and_deduplicates_resources():
    calls = []

    def load(path):
        calls.append(path)
        return {"bG": path.split(".")[0]}

    result = standard_funnel_boss_references(
        {"core": {"20": "a", "40": "b", "100": "a"}}, lambda row: [row], load)
    assert result == {("damage_share", "a"), ("damage_share", "b")}
    assert calls == ["a.esdl.amf3.deflate", "b.esdl.amf3.deflate"]


@pytest.mark.parametrize("tree", ({"bG": ["dynamic"]}, {
    "au": [{"h": [{"a": ["T1", 0]}]}]}))
def test_dynamic_or_malformed_reverse_links_are_rejected(tree):
    with pytest.raises(ValueError):
        standard_funnel_boss_references({"core": "a"}, lambda row: [row], lambda path: tree)


def test_mix_requires_action_closure_even_for_whitelisted_bosses():
    source = SimpleNamespace(portable=False, terrain_requirements=None,
                             native_only_reason="ACTION_CLOSURE_UNAUDITED")
    result = checked_mix_terrain_compatibility("a", "b", {"a": source, "b": object()},
                                               strict_transplant=True, transplant_safe={"boss"})
    assert not result.ok
    assert result.reason == "ACTION_CLOSURE_UNAUDITED"


def test_mix_passes_proved_requirements_to_full_terrain_gate(monkeypatch):
    requirement = object()
    source = SimpleNamespace(portable=True, terrain_requirements=requirement)
    target = object()
    seen = []
    expected = rb.rbb.CompatibilityResult(False, "MISSING_NAMED_POINT", "p1", "a", "b")

    def check(*args, **kwargs):
        seen.append((args, kwargs))
        return expected

    monkeypatch.setattr(rb.rbb, "terrain_compatibility", check)
    assert checked_mix_terrain_compatibility("a", "b", {"a": source, "b": target},
        strict_transplant=True, transplant_safe={"boss"}) == expected
    assert seen == [((source, target, requirement), {
        "strict_transplant": True, "transplant_safe": {"boss"}})]


def test_pinned_mix_does_not_mutate_tables_when_terrain_proof_is_missing():
    # Execute the production nested selection routine with a synthetic snapshot.
    # No store is installed or read, and no reimplementation of its branch exists.
    tree = ast.parse(Path(rb.__file__).read_text(encoding="utf-8"))
    node = copy.deepcopy(next(n for n in ast.walk(tree)
                              if isinstance(n, ast.FunctionDef) and n.name == "mix_pick"))
    for child in ast.walk(node):
        if isinstance(child, ast.Nonlocal):
            child.__class__ = ast.Global
    wave = [""] * 41
    wave[23:25] = ["1", "target_boss"]
    fields = {"target": "target,terrain,z"}
    zones = {"z": {"0": ",".join(wave)}}
    pool = [("source", None, ["boss"]), ("target", None, ["target_boss"])]
    before = copy.deepcopy((fields, zones, pool))
    scope = dict(vars(rb))
    scope.update(tower=pool, tower_master=list(pool), fd_t=fields, zone_t=zones,
                 gim_dirty=False, code_refs={"hard": set(), "degraded": False},
                 thumb_map={}, elem_map={"source": 0}, belem_map={},
                 kind_fixer=lambda code, old_kind: "1",
                 special_bosses=(set(), ()), src={},
                 mix_compatibility=lambda a, b, bosses, round_no: checked_mix_terrain_compatibility(
                     a, b, {}, strict_transplant=True, transplant_safe={"boss"}))
    compiled = ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[]))
    exec(compile(compiled, rb.__file__, "exec"), scope)
    assert scope["mix_pick"](5, "target", "boss") is None
    assert (fields, zones, pool) == before
    assert not scope["gim_dirty"]


def test_mix_proofs_follow_resolved_floor_level_and_cache_each_level():
    tree = ast.parse(Path(rb.__file__).read_text(encoding="utf-8"))
    node = next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "mix_compatibility")
    calls = []

    def catalog(level):
        calls.append(level)
        return {"proved_level": level}

    scope = dict(vars(rb))
    scope.update(mix_bundles_by_level={}, sb_t={}, gv_t={}, gb_t={}, want_max=False,
                 want_level=lambda r: 80 if r < 10 else 90,
                 resolve_level=lambda bosses, level, *args, **kwargs: level,
                 build_native_bundle_catalog=catalog, native_bundle_field_index=lambda value: value,
                 load_transplant_policy=lambda: (True, {"boss"}),
                 checked_mix_terrain_compatibility=lambda a, b, evidence, **kwargs: evidence)
    exec(compile(ast.Module(body=[node], type_ignores=[]), rb.__file__, "exec"), scope)
    check = scope["mix_compatibility"]
    assert check("source", "target", ["boss"], 5) == {"proved_level": 80}
    assert check("source", "target", ["boss"], 15) == {"proved_level": 90}
    assert check("source", "target", ["boss"], 5) == {"proved_level": 80}
    assert calls == [80, 90]


def test_hp_reorder_validates_existing_mix_against_original_donor():
    tree = ast.parse(Path(rb.__file__).read_text(encoding="utf-8"))
    hp_function = next(n for n in ast.walk(tree)
                       if isinstance(n, ast.FunctionDef) and n.name == "hp_curve_fit_pick")
    node = next(n for n in ast.walk(hp_function)
                if isinstance(n, ast.FunctionDef) and n.name == "reject_reason")
    current = {"field": "mod_rogue_f3", "bosses": ["boss"],
               "_mix_boss_entry": ("source", None, ["boss"]),
               "_mix_terrain_entry": ("target", None, ["other"]), "_mix_slot_count": 1}
    calls = []

    def compatibility(source, target, bosses, round_no):
        calls.append((source, target, bosses, round_no))
        return SimpleNamespace(ok=source == "source")

    scope = dict(vars(rb))
    scope.update(current=current, r=3, args=SimpleNamespace(rounds=30),
                 field_needed=False, carrier_required=False,
                 code_refs={"hard": set(), "degraded": False},
                 load_transplant_policy=lambda: (True, {"boss"}),
                 special_bosses=(set(), ()), mix_compatibility=compatibility)
    exec(compile(ast.Module(body=[node], type_ignores=[]), rb.__file__, "exec"), scope)
    assert scope["reject_reason"](current, {"level": 80}) is None
    assert calls == [("source", "target", ["boss"], 3)]
