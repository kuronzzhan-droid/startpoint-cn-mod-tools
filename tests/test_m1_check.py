"""A schema pass must not disguise absent checks or unresolved capabilities."""
import json

from wf.check import check_file, main
from wf.rules.catalog import EVIDENCE, STATES, catalog, with_metadata


def write(tmp_path, name, value):
    path = tmp_path / name
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


def recipe():
    return {"schema": "wf-balance-recipe/1", "id": "test", "name": "测试", "slug": "test",
            "from_version": "1.4.131", "to_version": "1.4.132", "created_at": "2026-10-17",
            "local_test_only": True, "operations": [{"op": "set_cells", "character": "1", "table": "ability",
            "key": "1", "row": 0, "row_count": 1, "cells": [{"column": 5, "old": "0", "new": "1"}]}]}


def test_missing_old_value_fails_schema_before_rules(tmp_path):
    value = recipe()
    del value["operations"][0]["cells"][0]["old"]
    results = check_file(write(tmp_path, "bad.json", value))
    assert results[0]["status"] == "问题" and results[0]["blocking"]
    assert "old" in str(results[0]["errors"])


def test_missing_input_does_not_claim_old_values_verified(tmp_path):
    results = check_file(write(tmp_path, "recipe.json", recipe()))
    by_id = {entry["rule"]: entry for entry in results}
    assert by_id["schema"]["status"] == "满足"
    assert by_id["ability.old-values"]["status"] == "未执行"
    assert by_id["boss.multiwave-field"]["status"] == "不适用"


def test_pending_m2_empty_capabilities_are_not_a_pass(tmp_path):
    document = {"schemaVersion": 2, "pack": {"since": "1.4.131", "tail": "1.4.132",
        "anchor": {"from": "1.4.131", "to": "1.4.132"}, "archives": ["a.zip"]},
        "requires": {"clientCapabilities": [], "clientPatches": [], "serverFeatures": [],
        "serverRestart": False, "restartReasons": [], "minServerVersion": None,
        "capabilityResolution": "pending-m2"}}
    results = check_file(write(tmp_path, "requires.json", document))
    assert next(r for r in results if r["rule"] == "capability.unknown")["status"] == "待验证"


def test_unsupported_and_malformed_files_do_not_succeed(tmp_path, capsys):
    unknown = write(tmp_path, "unknown.json", {"schema": "something/99"})
    assert main([str(unknown)]) == 1
    bad = tmp_path / "bad.yml"
    bad.write_text("{", encoding="utf-8")
    assert check_file(bad)[0]["status"] == "问题"
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"a":1,"a":2}', encoding="utf-8")
    assert check_file(duplicate)[0]["status"] == "问题"


def test_catalog_evidence_and_every_five_state_are_preserved():
    entries = catalog()["rules"]
    assert 10 <= len(entries) <= 20
    assert len({r["id"] for r in entries}) == len(entries)
    for entry in entries:
        assert entry["evidence_nature"] in EVIDENCE
        assert all(entry[key] for key in ("scope", "source", "revision", "requirement"))
    results = with_metadata([{"rule": f"test.{state}", "status": state} for state in STATES], "boss")
    assert {r["status"] for r in results} == set(STATES)
    unknown = next(r for r in results if r["rule"] == "art.atlas-budget")
    assert unknown["status"] == "未执行" and not unknown["blocking"]


def test_dsl_cli_fails_for_629_and_accepts_clean_tree(tmp_path, capsys):
    source = ["ActionDsl"] + [None] * 10 + [["Block", [["Command", ["NotifyPowerflipEnd"]]]]]
    path = write(tmp_path, "tree.json", source)
    assert main(["dsl", str(path), "--kind", "629"]) == 1
    source[-1][1].clear()
    write(tmp_path, "tree.json", source)
    assert main(["dsl", str(path), "--kind", "629"]) == 0


def test_character_text_schema_routes_visible_wording_rules(tmp_path):
    document = {"schema": "wf-character-text/1", "character_id": "1", "code": "hero", "skill_key": "hero",
                "title": "勇士", "title_column": 3, "character_text": {"0": "角色", "3": "勇士"},
                "action_skill": {"1": {"c0": "技能", "c1": "生命值100%以下时攻击力提高"}},
                "custom_ability_string": {}, "desc_override": {}, "server_character_text": None,
                "sources": {}, "snapshot_sha256": "0" * 64}
    results = check_file(write(tmp_path, "text.json", document))
    assert results[0]["status"] == "满足"
    assert next(r for r in results if r["rule"] == "text.wording")["blocking"]
    assert next(r for r in results if r["rule"] == "text.visible-sources")["status"] == "未执行"
