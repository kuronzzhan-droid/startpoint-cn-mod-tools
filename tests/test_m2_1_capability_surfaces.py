"""Select table/block dependencies; concrete parser support is a binary gate."""
from copy import deepcopy
import hashlib
import json

import pytest

from wf.caps.facts import UNIQUE
from wf.caps.registry import load_registry, validate_capability
from wf.caps.requirements import infer_requirements
from wf.dsl.references import ABILITY_TABLES
from test_m2_requirements import ABILITY, ability, payload


@pytest.mark.parametrize("logical,table", list(ABILITY_TABLES.items())[1:])
@pytest.mark.parametrize("kind,block", [(422, "during_content"), (423, "during_content"),
    (424, "during_content"), (724, "instant_content")])
def test_patch_kinds_only_select_dependencies_in_the_declared_table(logical, table, kind, block):
    if kind == 423 and table in {"ability_soul", "equipment_enhancement_ability"}:
        result = infer_requirements({"a": payload(logical, {"x": ability(kind, table=table, block=block)})})
        assert "client.equipment.gauge_gain_rules@1" in result["clientCapabilities"]
        assert "client.kind423.gauge_source_limit@1" not in result["clientCapabilities"]
        return
    result = infer_requirements({"a": payload(logical, {"x": ability(kind, table=table, block=block)})})
    assert result["clientCapabilities"] == []
    assert result["kindSites"][0]["table"] == table


@pytest.mark.parametrize("logical,table", [(p, t) for p, t in ABILITY_TABLES.items()
                                         if t in {"ability_soul", "equipment_enhancement_ability"}])
def test_weapon_layout_without_awake_kind_follows_unique(logical, table):
    members = {"a": payload(logical, {"x": ability(0, table=table, unique="99881")}),
               "u": payload(UNIQUE, {"99881": "hidden_weapon,0"})}
    result = infer_requirements(members)
    assert "client.unique.hidden@1" in result["clientCapabilities"]
    assert "official.awakening@1" not in result["clientCapabilities"]
    del members["u"]
    assert infer_requirements(members)["capabilityResolution"] == "partial"


def test_missing_baseline_note_and_423_excludes_performance_patch():
    members = {"a": payload(ABILITY, {"x": ability(423)})}
    result = infer_requirements(members)
    assert result["clientPatches"] == ["#31"]
    assert result["inferenceNotes"][0]["reason"] == "baseline-missing"
    unchanged = infer_requirements(members, read_raw=lambda _: members["a"][0])
    assert not unchanged["inferenceNotes"] and not unchanged["clientCapabilities"]


def test_selector_is_data_driven():
    registry = deepcopy(load_registry())
    cap = registry["client.kind424.damage_convert@1"]
    assert "dsl.buffTargetAs.convert" in cap["data_surface"]["selectors"]
    cap["data_surface"]["allowed_tables"] = ["ability_soul"]
    result = infer_requirements({"a": payload(ABILITY, {"x": ability(424)})}, registry=registry)
    assert result["clientCapabilities"] == []
    weapon = next(p for p, t in ABILITY_TABLES.items() if t == "ability_soul")
    result = infer_requirements({"a": payload(weapon, {"x": ability(424, table="ability_soul")})}, registry=registry)
    assert result["clientCapabilities"] == [cap["id"]]


def test_schema_rejects_untyped_surface_constraints():
    cap = deepcopy(load_registry()["client.kind424.damage_convert@1"])
    cap["data_surface"]["allowed_blocks"] = "during_content"
    with pytest.raises(ValueError, match="invalid capability"):
        validate_capability(cap)
    del cap["data_surface"]["allowed_blocks"]
    with pytest.raises(ValueError, match="allowed_blocks"):
        validate_capability(cap)


@pytest.mark.parametrize("table,block", [("leader_ability", "during_content"), ("ability", "during_content")])
def test_deliver_cli_reports_problem_for_invalid_kind_surface(tmp_path, capsys, table, block):
    from wf.deliver.cli import main
    logical = next(p for p, name in ABILITY_TABLES.items() if name == table)
    kind = 422 if table == "leader_ability" else 724
    raw, _ = payload(logical, {"x": ability(kind, table=table, block=block)})
    (tmp_path / "table.bin").write_bytes(raw)
    doc = {"schema": "wf-change-set/1", "id": "invalid-kind", "name": "invalid kind",
           "from_version": "1.4.150", "to_version": "1.4.151", "slug": "invalid-kind",
           "created_at": "2026-10-18", "local_test_only": True, "members": [
               {"root": "common", "logical_path": logical, "source": "table.bin",
                "sha256": hashlib.sha256(raw).hexdigest(), "before_sha256": None}]}
    source = tmp_path / "changeset.json"
    source.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        main([str(source), "--out", str(tmp_path / "delivery"), "--no-baseline-i-know"])
    assert error.value.code == 2
    assert "问题" in capsys.readouterr().err
    assert not list((tmp_path / "delivery").glob("*.zip"))
