"""Review regressions use synthetic ownership and valid draft envelopes."""
import copy
import json

import pytest
import jsonschema
import wf_quest_lib as nodes

from wf.paths import REPOSITORY
from wf.studio.drafts import validate as validate_draft
from wf.studio.key_subject import ABILITY, CHARACTER, CUSTOM, SubjectKeys
from wf.studio.subject_evidence import EQUIPMENT, ITEM
from test_studio_deliver_bridge import case  # noqa: F401
from test_studio_key_diff import View, character, ordered


def test_studio_reservations_validate_at_top_and_change_params(case):
    draft = copy.deepcopy(case[1])
    draft["reservations"] = {"multiball": ["7"], "unique": ["8"]}
    draft["changes"][0]["params"]["reservations"] = {"soul": ["9"], "stringcode": ["desc"]}
    validate_draft(draft)
    owner = SubjectKeys(View(), draft)
    assert owner.ids["multiball"] == {"7"} and owner.ids["soul_item"] == {"9"}
    schema = json.loads((REPOSITORY / "schemas/studio-draft.schema.json").read_text("utf-8"))
    for branch in schema["$defs"]["change"]["allOf"]:
        assert branch["then"]["properties"]["params"]["properties"]["reservations"] == {
            "$ref": "#/$defs/reservations"}


@pytest.mark.parametrize("bad", [{"typo": ["7"]}, {"multiball": [7]}, {"soul": "9"}, {"soul": [""]}])
def test_studio_reservations_reject_untyped_or_malformed_values(case, bad):
    draft = copy.deepcopy(case[1])
    draft["reservations"] = bad
    with pytest.raises((ValueError, jsonschema.ValidationError)):
        validate_draft(draft)


def subject(requests, kind="character"):
    return {"characterId": "11", "code": "hero" if kind == "character" else "weapon_11",
            "subjectKind": kind, "changes": [{"kind": "ability_edit" if kind == "character" else "weapon",
                                               "params": {"requests": requests}}]}


@pytest.mark.parametrize("name", ["ability", "leader_ability", "action_skill"])
def test_studio_asserted_attach_creation_is_owned_but_shared_attach_is_not(name):
    from wf.studio.subject_evidence import ABILITY_TABLES
    logical = ABILITY_TABLES[name]
    row = [{"column": "c0", "old": None, "new": "new_description"}]
    op = {"op": "attach_key", "table": name, "key": "new_key",
          **({"levels": {"1": [row]}} if name == "action_skill" else {"rows": [row]})}
    owner = SubjectKeys(View(), subject([{"operations": [op]}]))
    assert owner.classify(logical, "new_key") == "owned"
    op = {"op": "attach_key", "table": name, "key": "existing", "shared_ok": True}
    view = View({logical: nodes.build_node({"existing": "text"})})
    assert SubjectKeys(view, subject([{"operations": [op]}])).classify(logical, "existing") == "unknown"
    shared = View({CHARACTER: ordered({"22": character("other", "existing")}),
                   ABILITY: nodes.build_node({"existing": "shared_description"})})
    op["table"] = "ability"
    assert SubjectKeys(shared, subject([{"operations": [op]}])).classify(ABILITY, "existing") == "foreign"


def test_studio_override_uses_all_c0_owners_including_shared_rows():
    view = View({CHARACTER: ordered({"11": character("hero", "a"), "22": character("other", "b")}),
                 ABILITY: nodes.build_node({"a": "own\nshared", "b": "shared"})})
    request = {"text": {"desc_override": {key: {"old": None, "new": "text"}
                 for key in ("desc_override_own", "desc_override_shared", "desc_override_arbitrary")}}}
    owner = SubjectKeys(view, subject([request]))
    assert owner.classify(CUSTOM, "desc_override_own") == "owned"
    assert owner.classify(CUSTOM, "desc_override_shared") == "foreign"
    assert owner.classify(CUSTOM, "desc_override_arbitrary") == "unknown"


def test_studio_weapon_clone_derived_text_has_exact_table_scoped_ownership():
    owner = SubjectKeys(View(), subject([{"operation": "weapon_clone", "weapon": {"id": "11", "code": "blade"}}], "weapon"))
    for key in ("awakening_material_11", "blade_pf_damage"):
        assert owner.classify(CUSTOM, key) == "owned"
        assert owner.classify(ABILITY, key) == "unknown"
    assert owner.classify(CUSTOM, "blade_unrelated") == "unknown"
    existing = View({CUSTOM: nodes.build_node({"blade_pf_damage": "someone else's key"})})
    draft = subject([{"operation": "weapon_clone", "weapon": {"id": "11", "code": "blade"}}], "weapon")
    assert SubjectKeys(existing, draft).classify(CUSTOM, "blade_pf_damage") == "unknown"


@pytest.mark.parametrize("shared", [False, True])
def test_studio_weapon_soul_uses_equipment_reference_but_material_is_unknown(shared):
    row = [""] * 16
    row[10] = "91"
    equipment = {"11": ",".join(row)}
    if shared:
        equipment["22"] = ",".join(row)
    owner = SubjectKeys(View({EQUIPMENT: nodes.build_node(equipment)}), subject([
        {"operation": "weapon_icon", "weapon": {"id": "11", "kind": "material", "item_id": "92"}}
    ], "weapon"))
    assert owner.classify(ITEM, "91") == ("foreign" if shared else "owned")
    assert owner.classify(ITEM, "92") == "unknown"


@pytest.mark.parametrize("kind", ["weapon", "boss"])
def test_studio_non_character_container_code_never_claims_character_prefix(kind):
    owner = SubjectKeys(View(), subject([], kind))
    assert owner.classify(CUSTOM, "weapon_11_unrelated") == "unknown"
    view = View({CHARACTER: ordered({"11": character("actual_character", "91")})})
    assert SubjectKeys(view, subject([], kind)).classify(CUSTOM, "actual_character_text") == "foreign"
    assert SubjectKeys(view, subject([], kind)).classify(ABILITY, "91") == "foreign"
