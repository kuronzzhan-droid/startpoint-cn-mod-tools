"""Use a real synthetic SWF to test native-template selection and hash binding."""
import hashlib
import json

import pytest
import wf_describe

from test_m23_apk_kinds import _code
from weapon_delivery_fixture import case
from wf.apk.bodies import label_map
from wf.apk.kind_branches import TABLE_CLASSES
from wf.apk.swfabc import PoolEditor, SwfAbc
from wf.boss import schema as s
from wf.boss.shop_model import SOUL
from wf.studio.drafts import DraftError
from wf.studio.weapon_editor import WeaponEditor, compile_weapon


def add_native_branch(fixture, *, invoke=False):
    document = json.loads(fixture["provides"].read_bytes())
    path = fixture["root"] / "fixture.swf"
    swf = SwfAbc.from_bytes(path.read_bytes(), source=path)
    pool = PoolEditor(swf.abc)
    values = [pool.string(str(value)) for value in (32, 34, 251, 318)]
    for index, label in label_map(swf.abc).items():
        if label == "AbilitySoulValues$/parseAt44":
            swf.abc.bodies[index][5] = _code(values)
        if invoke:
            for table, name in TABLE_CLASSES.items():
                if label == f"{name}$/parseAt{wf_describe.layout(table)['blocks']['instant_content']}":
                    swf.abc.bodies[index][5] = _code([*values, pool.string("629")])
            if label == "AbilityValues$/parseAt109":
                swf.abc.bodies[index][5] = _code([pool.string("424")])
    path.write_bytes(swf.serialize())
    document["source"]["swf_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    if invoke:
        document["provides"] = [{"id": cid, "title": "Synthetic parser evidence", "layer": layer,
            "patches": patches, "methods": [], "basis": "Synthetic fixture; no game runtime proof"}
            for cid, layer, patches in [("official.kind629.invoke_skill@1", "B", []),
                                       ("client.kind424.damage_convert@1", "A", [20])]]
        document["patches"] = [{"number": 20, "status": "recorded", "methods": [],
                                "basis": "Synthetic parser branch only; not a real damage patch"}]
    fixture["provides"].write_text(json.dumps(document), "utf-8")


@pytest.mark.parametrize("template,element,kind", [("pf_hit_ability_damage", 2, "318"),
                                                 ("pf_use_ability_damage", 0, "251")])
def test_native_clone_compiles_against_actual_target_swf(tmp_path, template, element, kind):
    fixture = case(tmp_path)
    add_native_branch(fixture)
    editor = WeaponEditor(fixture["source"], store=fixture["store"], server_dir=fixture["server_dir"],
                          provides=fixture["provides"])
    result = editor.apply("weapon_clone", {"sourceWeapon": fixture["source_id"], "code": "target_native",
        "soul_template": {"template": template, "element": element, "multiplier": 1}})
    built = compile_weapon(fixture["source"], fixture["store"], result["changeset"],
                            server_dir=fixture["server_dir"], provides=fixture["provides"])
    import wf_quest_lib as codec
    rows = s.parse_rows(codec.parse_node(built["client"][SOUL])[result["weaponId"]])
    assert len(rows) == 1 and rows[0][44] == kind
    assert not any(path.endswith(".action.dsl.amf3.deflate") for path in built["client"])


def test_native_template_rejected_when_actual_swf_lacks_branch(tmp_path):
    fixture = case(tmp_path)
    editor = WeaponEditor(fixture["source"], store=fixture["store"], server_dir=fixture["server_dir"],
                          provides=fixture["provides"])
    with pytest.raises(DraftError, match="unsupported by real SWF"):
        editor.apply("weapon_clone", {"sourceWeapon": fixture["source_id"],
            "soul_template": {"template": "pf_hit_ability_damage", "element": 2, "multiplier": 1}})
    assert fixture["store"].characters() == []


def test_invoke_clone_compiles_with_declared_patch_and_real_parser_branches(tmp_path):
    fixture = case(tmp_path)
    add_native_branch(fixture, invoke=True)
    editor = WeaponEditor(fixture["source"], store=fixture["store"], server_dir=fixture["server_dir"],
                          provides=fixture["provides"])
    result = editor.apply("weapon_clone", {"sourceWeapon": fixture["source_id"], "code": "target_invoke",
        "soul_template": {"template": "pf_hit_invoke_damage", "element": 1, "dsl_element": 2,
                          "hit_effect": "None", "multiplier": 1}})
    compiled = compile_weapon(fixture["source"], fixture["store"], result["changeset"],
                               server_dir=fixture["server_dir"], provides=fixture["provides"])
    import wf_quest_lib as codec
    row = s.parse_rows(codec.parse_node(compiled["client"][SOUL])[result["weaponId"]])[0]
    assert row[67] == "target_invoke_pf_damage"
    assert row[68] + ".action.dsl.amf3.deflate" in compiled["client"]
