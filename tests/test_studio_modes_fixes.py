"""D1 review regressions: synthetic inputs, no author store or server required."""
import copy
import json
import struct
from types import SimpleNamespace

import pytest
import wf_quest_lib as q
from wf.deliver.changeset import member_name
from wf.studio import mode_five, mode_rogue_overlay as overlay
from wf.studio.mode_checks import delivery_checks, saved_preview
from wf.studio.mode_store import ViewInputs
from wf.studio.drafts import DraftError
from wf.tools.boss import five_boss_v2 as f
from wf.tools.boss import five_boss_tuning as tuning
from wf.tools.rogue import rogue_build as b


@pytest.mark.parametrize("root", ["common", "medium", "android"])
def test_multi_root_png_tracks_priority_and_missing_roots(root):
    logical = "image.png"
    png = b"\x89PNG\r\n\x1a\n" + b"\0\0\0\rIHDR" + struct.pack(">II", 2048, 1024)
    data = {member_name(root, logical): png}
    def read(name):
        if name not in data:
            raise FileNotFoundError(name)
        return data[name], "tip"
    inputs = ViewInputs(SimpleNamespace(view=SimpleNamespace(read_member=read)))
    live = f.Live(inputs.read)
    live.view_bound = True
    assert f.png_dims(live, logical) == (2048, 1024)
    roots = ("common", "medium", "android")
    assert set(inputs.inputs) == {r + ":" + logical for r in roots[:roots.index(root)+1]}
    inputs.verify()
    data[member_name("common", logical)] = png + b"new priority resource"
    with pytest.raises(DraftError, match="输入发生变化"):
        inputs.verify()


def fixture_overlay():
    row = [""] * 100
    row[:3] = ["700099001", "1", "1"]
    row[98] = "mod_rogue_f1"
    special = "mod_rogue_holy_sphere7"
    before = {
        b.BOSS_LEVEL: {special: "original", special + "_studio_old": "old clone"},
        b.GENERAL_BOSS: {"mod_rogue_boss1": {"80": "old"}, "native": {"80": "mod_rogue_boss1"}},
        b.FIELD_DATA_T: {"mod_rogue_f1": "field,terrain,mod_rogue_z1"},
        b.ZONE_T: {"mod_rogue_z1": {"0": "mod_rogue_boss1"}},
        b.ENEMY_WATCH: {"1": {"mod_rogue_boss1": "mod_rogue_boss1"},
                        "2": {special: "mod_rogue_boss1," + special}},
        b.Q_QUEST: {b.EVENT_ID: {"1": b.join(row, False)}},
    }
    return before


def test_overlay_repeated_rounds_never_namespace_retained_specials(monkeypatch):
    before = fixture_overlay()
    original = copy.deepcopy(before[b.BOSS_LEVEL])
    watch = copy.deepcopy(before[b.ENEMY_WATCH]["2"])
    monkeypatch.setattr(overlay, "validate_candidate_references", lambda *args: [])
    for iteration in range(3):
        trees = copy.deepcopy(before)
        # Mimic the builder's cleanup and recreation of owned generation keys.
        for logical in (b.GENERAL_BOSS, b.FIELD_DATA_T, b.ZONE_T):
            trees[logical] = {k: v for k, v in trees[logical].items() if "_studio_" not in k}
        trees[b.GENERAL_BOSS]["mod_rogue_boss1"] = {"80": str(iteration)}
        raw = {key: q.build_node(value) for key, value in before.items()}
        result = overlay.retain_and_namespace(raw.__getitem__, {"files": {
            key: q.build_node(value) for key, value in trees.items()}})
        assert b.BOSS_LEVEL not in result["files"]  # Zero semantic change is omitted.
        before.update({key: q.parse_node(value) for key, value in result["files"].items()})
        assert before[b.BOSS_LEVEL] == original
        assert before[b.ENEMY_WATCH]["2"] == watch
        assert before[b.GENERAL_BOSS]["native"] == {"80": "mod_rogue_boss1"}
    assert all("_studio_old_studio_" not in key for key in before[b.BOSS_LEVEL])


def test_nested_collision_refuses_and_identical_replay_is_safe():
    before = {"1": {"clone_studio_same": "old"}}
    with pytest.raises(ValueError, match="已占用"):
        overlay.merge_retained(before, {"1": {"clone_studio_same": "new"}}, {"clone_studio_same"})
    assert overlay.merge_retained(before, before, {"clone_studio_same"}) == before


def test_orochi_csv_list_renames_exact_tokens_with_csv_quoting():
    heads = [f"head{i}" for i in range(8)]
    row = [""] * 25
    row[3] = "head0_suffix"
    row[24] = ",".join(heads)
    result = overlay.rename_graph(b.join(row, False), {h: h + "_new" for h in heads})
    assert b.cells(result)[24].split(",") == [h + "_new" for h in heads]
    assert b.cells(result)[3] == "head0_suffix"


@pytest.mark.parametrize("failure", [None, "missing_general", "missing_level", "unusable_tier", "short_list"])
def test_candidate_orochi_head_gate(failure):
    from wf.tools.rogue.rogue_candidate_heads import validate_heads
    from wf.tools.rogue import rogue_bundle
    heads = [f"head{i}" for i in range(8)]
    row = [""] * 25
    row[24] = ",".join(heads[:-1] if failure == "short_list" else heads)
    gb = {h: {"80": "body"} for h in heads}
    bl = {h: "0,10,1" for h in heads}
    if failure == "missing_general": gb.pop("head0")
    if failure == "missing_level": bl.pop("head0")
    validation = {"orochi": {"parent": {"80": b.join(row, False)}}, "general_boss": gb,
                  "__level_validator__": lambda ref, level, tables: None if failure == "unusable_tier" else 80,
                  "__funnel_ok__": lambda *args: True}
    quest = [""] * 100
    quest[95] = "80"
    reports = [{"round": "1", "bosses": ["parent"], "errors": [], "ok": True}]
    builder = SimpleNamespace(BOSS_LEVEL="bl", rbb=rogue_bundle, cells=b.cells)
    validate_heads({"1": quest}, reports, lambda _: bl, builder, validation)
    assert reports[0]["ok"] == (failure is None)


def test_dormant_affix_drift_blocks_even_when_base_plan_is_empty(monkeypatch):
    tree = ["ActionDsl", "repository"]
    logical = f.wf_dsl.dsl_logical(f.affix_program("dormant"))
    def loader(path):
        if path != logical: raise FileNotFoundError(path)
        return f.encode_dsl(["ActionDsl", "chain hotfix"])
    monkeypatch.setattr(f, "affix_library", lambda _: {"dormant": tree})
    base = {"plan": f.Plan(), "live": f.Live(loader), "files": {}, "diff": []}
    monkeypatch.setattr(mode_five, "compile_structure", lambda *args: base)
    result = mode_five.preview(loader, mode_five.document())
    assert not result["canGenerate"]
    assert [d["logical"] for d in result["audit"]["differences"]] == [logical]


def test_new_candidate_existing_resource_or_key_is_fail_closed():
    loader = lambda _: q.build_node({"other": "chain hotfix"})
    base = {"plan": f.Plan(), "live": f.Live(loader)}
    candidate = {"plan": f.Plan()}
    candidate["plan"].files["new.bin"] = b"candidate"
    candidate["plan"].put("table", ["other"], "candidate")
    result = mode_five.audit_current(None, base, candidate)
    assert not result["aligned"] and len(result["differences"]) == 2


def test_delivery_uncertainties_remain_pending():
    checks = delivery_checks("five", {"warnings": ["WARN 5.8 Mpx"],
                                     "report": {"element_variants_in_apk": ["effect_fire"]}})
    assert checks[0]["status"] == "满足"
    assert len(checks) == 5 and all(c["status"] == "待验证" for c in checks[1:])
    assert all(not c["blocking"] for c in checks)


@pytest.mark.parametrize("failure", [None, "version", "input", "freshness"])
def test_saved_rogue_preview_recovered_only_with_current_evidence(monkeypatch, failure):
    from wf.studio import mode_checks
    source = SimpleNamespace(version="1.4.10", view=SimpleNamespace(read_member=lambda _: (b"new", "tip")))
    draft = {"baseView": "1.4.9" if failure == "version" else "1.4.10", "inputs": {},
             "preview": {"ok": True, "canGenerate": True, "blockers": []}}
    if failure == "input": draft["inputs"] = {"common:test": "old hash"}
    original = copy.deepcopy(draft)
    monkeypatch.setattr(mode_checks, "freshness", lambda _: {"latest": "1.4.11" if failure == "freshness" else "1.4.10"})
    result = saved_preview(source, draft)
    assert result["canGenerate"] == (failure is None)
    assert draft == original


def test_five_chain_tuning_preserves_order_scope_and_force_flags():
    spec = f.load_spec()
    r0 = f.affix_library(spec["affix_params"])["enrage_r0"]
    assert "ACToleranceOfElement" not in json.dumps(r0)
    assert "FindAllSubjects" not in json.dumps(r0)
    assert r0[11][1][0][1][4][1][0][1][1] == -17
    for name in ("silence_waves", "sig_king_seal"):
        tree = f.affix_library(spec["affix_params"])[name]
        def walk(v):
            if isinstance(v, list):
                if v and v[0] == "CreateCondition": yield v
                for x in v: yield from walk(x)
        assert all(not node[-1] for node in walk(tree))
    for variant in spec["_variants"]:
        for wave, bosses in enumerate(variant.waves):
            for slot, _ in enumerate(bosses):
                programs = tuning.wave_programs(spec, variant, wave, slot)
                if variant.round == "r0" and slot:
                    assert programs == [f.affix_program("enrage_r0")]
                pre = tuning.clone_pre(spec, [tuning.entrance_program(True), "native"], [], [], programs, slot)
                assert pre[0] == "native" and pre[-1] == tuning.entrance_program(slot != 0)
    lib = tuning.entrance_library(spec["entrance"])
    block = lib[tuning.entrance_program(True)][11][1]
    assert len(block) == 6  # debuff resistance + five separately dispellable layers
    assert [node[1][2][0][3][0]["min"] for node in block[1:]] == [0.2346, 0.4048, 0.7997, 2.3229, 95.2381]
    assert all(not f.dsl_constructor_problems(tree) for tree in lib.values())
    assert spec["rounds"]["r0"]["hp_mult"] == [40, 6, 0.04375]
