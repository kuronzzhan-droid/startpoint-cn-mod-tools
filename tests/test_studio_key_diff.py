"""Synthetic key-diff coverage: raw rows, ownership, archives and bounded handoff."""
import json
from pathlib import Path
import zipfile
import zlib

import pytest

import wf_mod_tool as core
from wf.deliver.changeset import member_name
from wf.studio.delivery_inputs import DeliveryMember
from wf.studio.key_diff import KEY_LISTS, compare_delivery, markdown, summarize, write_reports
from wf.studio.key_subject import ABILITY, CHARACTER, CUSTOM, SubjectKeys

PF = "master/skill/power_flip_action.orderedmap"
MULTIBALL = "master/battle/multiball/multiball.orderedmap"


def ordered(rows):
    return core.build_orderedmap_raw_rows(core.OrderedMap("fixture", list(rows), list(rows.values()), Path("fixture")))


def leaf(text, level=6):
    return zlib.compress(text.encode("utf-8"), level)


def character(code, ability=""):
    cells = [""] * 37
    cells[0], cells[19] = code, ability
    return leaf(",".join(cells))


class View:
    view_name, tip, effective_version = "fixture-chain", "1.4.290", "1.4.290"

    def __init__(self, files=None):
        self.files = {member_name("common", key): value for key, value in (files or {}).items()}

    def read_raw(self, logical):
        return self.read_member(member_name("common", logical))

    def read_member(self, name):
        if name not in self.files:
            raise FileNotFoundError(name)
        return self.files[name], "fixture-store"


def delivered(logical, raw, archive="fixture.zip", root="common"):
    return DeliveryMember(logical, root, member_name(root, logical), raw, archive, "1.4.290", "1.4.291")


def test_key_diff_compares_raw_row_bytes_and_blocks_every_removed_key():
    old = {"hero_skill": leaf("same", 1), "other_skill": leaf("before"), "gone": leaf("old")}
    new = {"hero_skill": leaf("same", 9), "other_skill": leaf("after"), "fresh": leaf("new")}
    view = View({PF: ordered(old), CHARACTER: ordered({"11": character("hero"), "22": character("other")})})
    report = compare_delivery(view, members=[delivered(PF, ordered(new))], subject="11")
    table = report["tables"][0]
    assert table["changed"] == ["hero_skill", "other_skill"]
    assert table["added"] == ["fresh"] and table["removed"] == ["gone"]
    assert table["owned"] == ["hero_skill"] and table["foreign"] == ["other_skill"]
    assert table["unknown"] == ["fresh", "gone"]
    assert report["status"] == "blocked" and not report["ok"]
    assert report["subject"]["code"] == "hero"


def test_key_diff_reordering_outer_index_is_not_changed():
    rows = {"a": leaf("x"), "b": leaf("y")}
    report = compare_delivery(View({PF: ordered(rows)}), members=[delivered(PF, ordered(dict(reversed(rows.items()))))])
    assert report["counts"] == dict.fromkeys(KEY_LISTS, 0)
    assert report["ok"]


def test_key_diff_foreign_is_warning_not_blocked():
    view = View({CHARACTER: ordered({"11": character("hero"), "22": character("other")})})
    report = compare_delivery(view, members=[delivered(CUSTOM, ordered({"other_desc": leaf("x")}))], subject="11")
    assert report["status"] == "warning" and report["ok"] and not report["blocking"]


def test_key_diff_subject_reservations_are_typed_and_missing_evidence_unknown():
    subject = {"characterId": "11", "code": "hero", "reservations": {
        "multiball": ["7001"], "weapon": ["9001"], "soul_item": ["9002"], "unique_condition": ["8001"]}}
    owner = SubjectKeys(View(), subject)
    cases = [(MULTIBALL, "7001"), ("master/item/item.orderedmap", "9001"),
             ("master/item/item.orderedmap", "9002"), ("master/character/unique_condition.orderedmap", "8001"),
             (CUSTOM, "wfx_summon_flip_pf_7001"), (CUSTOM, "wfx_ball_pf_action_7001")]
    assert all(owner.classify(logical, key) == "owned" for logical, key in cases)
    assert owner.classify(PF, "7001") == "unknown"
    assert owner.classify(CUSTOM, "wfx_ball_pf_action_7002") == "foreign"
    assert owner.classify(PF, "prefix11suffix") == "unknown"
    assert SubjectKeys(View(), "11").classify(MULTIBALL, "7001") == "unknown"
    assert SubjectKeys(View()).classify(CHARACTER, "11") == "unknown"


def test_key_diff_unknown_keys_warn_without_claiming_foreign_or_ownership():
    report = compare_delivery(View(), members=[delivered(CUSTOM, ordered({"unowned": leaf("x")}))])
    assert report["ok"] and report["status"] == "warning" and not report["blocking"]
    assert report["tables"][0]["unknown"] == ["unowned"]
    assert report["tables"][0]["owned"] == report["tables"][0]["foreign"] == []
    assert report["warnings"] == ["部分改动键归属未知，未视为自有键"]


def test_key_diff_numeric_ability_keys_use_character_references_and_shared_warns():
    view = View({CHARACTER: ordered({"11": character("hero", "91"), "22": character("other", "92"),
                                    "33": character("hero_alt", "91")})})
    owner = SubjectKeys(view, "11")
    assert owner.classify(ABILITY, "91") == "foreign"  # shared row affects another character
    assert owner.classify(ABILITY, "92") == "foreign"
    assert owner.classify(ABILITY, "93") == "unknown"
    assert owner.classify(CUSTOM, "hero_alt_desc") == "foreign"
    assert owner.classify(CUSTOM, "hero_desc") == "owned"


def test_key_diff_draft_explicit_clone_ownership_and_registrations():
    subject = {"characterId": "11", "code": "hero", "changes": [
        {"kind": "character_clone", "params": {"ownedRows": {ABILITY: ["93"]},
                                               "reservations": {"multiball": ["7001"]}}},
        {"kind": "ability_edit", "params": {"requests": [{"text": {"custom_ability_string": {"someone_else": "new"}}}]}},
        {"kind": "weapon", "params": {"requests": [{"operation": "weapon_clone", "weapon": {"id": "9001", "code": "blade"}}]}}]}
    owner = SubjectKeys(View(), subject)
    assert owner.classify(ABILITY, "93") == "owned"
    assert owner.classify(MULTIBALL, "7001") == "owned"
    assert owner.classify("master/item/item.orderedmap", "9001") == "owned"
    assert owner.classify(CUSTOM, "blade_soul") == "owned"
    assert owner.classify(CUSTOM, "someone_else") == "unknown"


def test_key_diff_binary_members_sha_only_and_no_unchanged_member():
    view = View({"character/demo/a.png": b"before", "character/demo/b.png": b"same"})
    report = compare_delivery(view, members=[delivered("character/demo/a.png", b"after"),
                                            delivered("character/demo/b.png", b"same"),
                                            delivered("character/demo/c.png", b"new")])
    assert not report["tables"]
    assert [item["change"] for item in report["files"]] == ["changed", "added"]
    assert report["files"][0]["beforeSha256"] != report["files"][0]["sha256"]


def archive(tmp_path, name, logical, raw):
    path = tmp_path / name
    member = member_name("common", logical)
    with zipfile.ZipFile(path, "w") as output:
        output.writestr(member, raw)
    path.with_suffix(".integrity.json").write_text(json.dumps({"logical": {member: logical}}), "utf-8")
    return path


def test_key_diff_multiple_zips_preserve_input_order_and_original_baseline(tmp_path, monkeypatch):
    monkeypatch.setattr("wf.studio.delivery_inputs.configured_path", lambda _: tmp_path / "no-pathlist")
    old = ordered({"base": leaf("x")})
    a = archive(tmp_path, "pinball-1.4.290-1.4.291-1-fixture.zip", PF, ordered({"first": leaf("1")}))
    b = archive(tmp_path, "pinball-1.4.291-1.4.292-1-fixture.zip", PF, ordered({"base": leaf("x"), "second": leaf("2")}))
    report = compare_delivery(View({PF: old}), [a, b])
    assert [item["archive"] for item in report["tables"]] == [a.name, b.name]
    assert report["tables"][0]["removed"] == ["base"]
    assert report["tables"][1]["added"] == ["second"]
    assert report["tables"][1]["removed"] == []
    assert report["delivery"] == {"from": "1.4.290", "to": "1.4.292", "archives": [a.name, b.name]}
    assert report["blocking"]


def test_key_diff_api_key_budget_is_total_per_table_and_markdown_complete(tmp_path):
    keys = {f"key_{n:04}": leaf("x") for n in range(500)}
    report = compare_delivery(View(), members=[delivered(PF, ordered(keys))])
    bounded = summarize(report)
    table = bounded["tables"][0]
    assert sum(len(table[name]) for name in KEY_LISTS) == 200
    assert table["truncated"] and table["counts"]["added"] == 500 and table["counts"]["unknown"] == 500
    assert len(report["tables"][0]["added"]) == 500
    text = markdown(report)
    assert "fixture-chain" in text and "1.4.290" in text and "1.4.291" in text
    assert "truncated=true" not in text and text.count("`key_") == 1000
    write_reports(report, tmp_path)
    assert json.loads((tmp_path / "key-diff.json").read_text("utf-8"))["tables"][0]["counts"]["added"] == 500
    assert (tmp_path / "key-diff.md").read_text("utf-8") == text


def test_key_diff_unknown_common_logical_path_fails_closed():
    member = DeliveryMember(None, "common", member_name("common", PF), ordered({}), "fixture.zip")
    with pytest.raises(ValueError, match="无法恢复 common"):
        compare_delivery(View(), members=[member])
    image = DeliveryMember(None, "medium", member_name("medium", "unknown.png"), b"image", "fixture.zip")
    report = compare_delivery(View(), members=[image])
    assert report["files"][0]["logical"] is None


@pytest.mark.parametrize("raw", [b"broken", ordered({"x": leaf("1")}) + b"trailing"])
def test_key_diff_rejects_corrupt_output_and_baseline(raw):
    with pytest.raises(ValueError):
        compare_delivery(View(), members=[delivered(PF, raw)])
    with pytest.raises(ValueError):
        compare_delivery(View({PF: raw}), members=[delivered(PF, ordered({}))])
