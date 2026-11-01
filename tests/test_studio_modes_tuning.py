"""Offline exact alignment and retained CLI defaults for the D1 tuning changes."""
import copy
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from wf.tools.boss import five_boss_v2 as f
from wf.studio import mode_five


def test_terrain_rebuild_reuses_removed_anchor_id_range_without_ignoring_ids():
    tree = {"nextobjectid": 99, "layers": [{"type": "objectgroup", "name": "0", "objects": [
        {"id": 1, "type": "BOUNDS", "x": 10, "y": 20},
        {"id": 2, "type": "FUNNEL_SPAWN1", "x": 0, "y": 0},
        {"id": 3, "type": "FUNNEL_SPAWN6", "x": 11, "y": 22, "width": 3, "height": 4},
        {"id": 4, "type": "FUNNEL_SPAWN7", "x": 0, "y": 0},
    ]}]}
    live = f.Live(lambda _: f.encode_terrain(tree))
    cfg = {"base": "synthetic", "remove_types": ["FUNNEL_SPAWN7"],
           "object_overrides": {"FUNNEL_SPAWN6": [[1, 2, 3, 4]]}}
    built, _ = f.build_terrain(live, cfg)
    expected = copy.deepcopy(tree)
    expected["layers"][0]["objects"].pop()
    assert built == expected
    assert f.decode_amf(f.encode_terrain(built)) == expected
    plan = f.Plan()
    plan.files["terrain.amf3.deflate"] = f.encode_terrain(expected)
    assert mode_five.audit_current(None, {"plan": plan, "live": f.Live(lambda _: f.encode_terrain(built))})["aligned"]
    built["layers"][0]["objects"][-1]["id"] = 50
    assert not mode_five.audit_current(None, {"plan": plan, "live": f.Live(lambda _: f.encode_terrain(built))})["aligned"]


def test_legacy_dsl_call_defaults_preserved_and_spec_opts_in_to_tuning():
    assert "ACToleranceOfElement" in json.dumps(f.dsl_enrage(480, .15, 8, .1, 5, 999))
    assert "FindAllSubjects" in json.dumps(f.dsl_enrage(480, .15, 8, .1, 5, 999))
    assert f.dsl_silence_waves(2400, 300, 999) == f.dsl_silence_waves(2400, 300, 999, force=True)
    assert f.dsl_signature(1000, 999, "k", silence=360) == f.dsl_signature(1000, 999, "k", silence=360, silence_force=True)
    assert f.load_spec()["rounds"]["r1"]["hp_mult"] == [40, 6, .04375]


def test_five_variant_writes_correct_hp_and_stamina_columns(monkeypatch):
    spec = f.load_spec()
    variant = spec["_variants"][0]
    rnd = spec["rounds"][variant.round]
    zone = [""] * 40
    quest = [""] * 124
    tables = {f.T_ZONE: {rnd["zone_template"][0]: {rnd["zone_template"][1]: f.write_rows([zone])}},
              f.T_BBQ: {"1": {"99": {rnd["quest_template"]: f.write_rows([quest])}}}}
    live = f.Live()
    monkeypatch.setattr(live, "table", tables.__getitem__)
    monkeypatch.setattr(f, "plan_clone", lambda live, spec, plan, variant, w, s, bs, programs, rerun: f"clone_{w}_{s}")
    plan = f.Plan()
    f.plan_variant(live, spec, plan, variant, spec["terrains"])
    row = f.one_row(plan.edits[f.T_BBQ][0][1])
    assert row[69] == "18" and row[97:100] == ["40", "6", "0.04375"]
    assert row[100:103] == ["1", "1", "1.5"]


def test_frontend_mode_input_and_restore_handlers():
    root = Path(__file__).resolve().parents[1]
    node = shutil.which("node")
    if not node or not (root / "studio/node_modules/typescript").exists():
        pytest.skip("requires Node and studio TypeScript/Preact dependencies")
    result = subprocess.run([node, str(root / "tests/studio_modes_frontend.cjs")], cwd=root,
                            capture_output=True, text=True, encoding="utf8")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "8 scenarios passed" in result.stdout


def test_rogue_get_returns_saved_preview_and_rejects_legacy_input_snapshot(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from wf.studio import mode_rogue, mode_checks
    from wf.studio.drafts import DraftStore
    from wf.studio.mode_routes import ModeRoutes
    source = SimpleNamespace(version="1.4.10", view=SimpleNamespace())
    routes = ModeRoutes(SimpleNamespace(source=source, ops=SimpleNamespace(store=DraftStore(tmp_path))))
    monkeypatch.setattr(mode_rogue, "current", lambda _: {"_digest": {}, "rows": []})
    monkeypatch.setattr(mode_checks, "freshness", lambda _: {"latest": source.version})
    routes.store.save("rogue", source.version, {"seed": 7}, {},
                      {"ok": True, "canGenerate": True, "blockers": []}, 0)
    response = json.loads(routes.read({}, "rogue").body)
    assert response["preview"]["canGenerate"] and response["payload"] == {"seed": 7}
    routes.store.save("rogue", source.version, {"seed": 7}, {"legacy.bin": "hash"},
                      {"ok": True, "canGenerate": True, "blockers": []}, 1)
    response = json.loads(routes.read({}, "rogue").body)
    assert not response["preview"]["canGenerate"]
    assert "多 CDN" in response["preview"]["blockers"][0]
