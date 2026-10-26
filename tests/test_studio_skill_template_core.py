"""Synthetic official donors exercise safe skill cloning, never bundled game art."""
from __future__ import annotations

import copy
import zlib

import pytest
import wf_dsl

from wf.studio.skill_template_catalog import (
    OfficialSource, list_templates, public_detail, resolve_key, template_detail,
)
from wf.studio.skill_template_core import clone_tree, damage_nodes, effect_paths, rewrite_effects
from wf.studio.skill_template_validation import validate_tree, walk


def root(*children):
    return ["ActionDsl", 1, ["None"], False, False, False, False, False, False, False, 0,
            ["Block", list(children)]]


def cmd(name, *args):
    return ["Command", [name, *args]]


def attack(multiplier=2):
    return cmd("CreateNormalAttack", -17, 255, [], [], 0, [{"min": multiplier, "max": multiplier + 1}],
               [{"min": 0, "max": 0}], False, False, False, False, False,
               [{"min": 1, "max": 1}], [{"min": 1, "max": 1}], ["Fine"], True)


def area(coord=None, target=-18):
    damage = attack()
    damage[1][1] = 2
    return cmd("CreateHitArea", "box", target, coord or ["AB"], 0, 1, 0, False, False,
               ["Rectangle", [{"min": 12, "max": 12}], [{"min": 50, "max": 50}]],
               ["Center"], ["Bottom"], ["Single"], ["SpecifyHitAreaLifetimeDirectly", 30],
               ["CalculatedUsingMaxNumOfHits", 4], ["None"], False, True, ["None"],
               0, ["Block", []], 1, 2, ["Block", [damage]], 0, 0, ["None"])


def fixture():
    effect = cmd("ShowEffect", "shine", ["SpecifyEffectDirectly", "battle/effect/skill_unique/donor/shine"],
                 -18, ["ForesideOfCharacter"], ["PlayOnlyFirstSequence"], ["AB"],
                 0, 0, 0, True, False, ["None"])
    return root(effect, ["Event", ["Wait", 23, "delay", ["Block", [area()]]]], attack(5))


def stored(tree):
    compressor = zlib.compressobj(wbits=-15)
    return compressor.compress(wf_dsl.encode_amf3(tree)) + compressor.flush()


class Source:
    version = "1.4.999"

    def __init__(self):
        row = ["技能", "说明", "icon", "1", "100", "100", "0", "battle/action/skill/donor$donor_1"]
        self.official = {"character": {"151000": [["donor", "1", "5", "2", "", "", "1", "", "donor"]]},
                         "text": {"151000": [["官方角色"]]}, "skill": {"donor": {"1": [row]}}}
        self.live = copy.deepcopy(self.official)
        self.live["skill"]["mod_only"] = {"1": [row]}
        self.live["skill"]["donor"]["1"][0][0] = "改版技能"
        self.raws = {wf_dsl.dsl_logical(row[7]): stored(fixture())}
        self.live_raws = {wf_dsl.dsl_logical(row[7]): stored(root(attack(999)))}

    def table(self, name, official=False):
        return (self.official if official else self.live).get(name, {})

    def raw(self, logical, official=False):
        return (self.raws if official else self.live_raws).get(logical)


def test_scale_only_changes_damage_bounds_not_timing_shape_or_source():
    tree = fixture()
    before = copy.deepcopy(tree)
    changed = clone_tree(tree, scale=2, element=2, attribution=3)
    recovered = copy.deepcopy(changed["tree"])
    for path, node in walk(recovered):
        if isinstance(node, list) and node[:1] == ["CreateNormalAttack"]:
            original = next(entry for entry in damage_nodes(before) if entry["path"] == path)
            node[2], node[6] = original["elementCode"], original["coefficient"]
    recovered[10] = 0
    assert tree == before == recovered
    assert all(entry["elementCode"] == 3 and entry["attribution"] == 3 for entry in changed["damageNodes"])
    assert changed["damageNodes"][0]["coefficient"] == [{"min": 4, "max": 6}]
    assert wf_dsl.parse_dsl(zlib.decompress(changed["raw"], -15))["tree"] == changed["tree"]


def test_exact_node_override_preserves_runtime_variables_and_other_nodes():
    tree = fixture()
    tree[11][1][-1][1][6][0]["mul"] = 901
    path = damage_nodes(tree)[-1]["path"]
    changed = clone_tree(tree, scale=2, node_coefficients={path: 7})
    assert changed["damageNodes"][-1]["coefficient"] == [{"min": 7, "max": 7, "mul": 901}]
    assert changed["damageNodes"][0]["coefficient"] == [{"min": 4, "max": 6}]
    with pytest.raises(ValueError, match="运行时"):
        clone_tree(tree, node_coefficients={path: [{"min": 7, "max": 7, "mul": 902}]})
    with pytest.raises(ValueError, match="路径不存在"):
        clone_tree(tree, node_coefficients={"/11/2/0": 7})


@pytest.mark.parametrize("mutation", [
    lambda t: t[11][1].append(cmd("CreateNormlAttack")),
    lambda t: t[11][1].append(cmd("ConditionalsFeverMode", ["DoNothing"], ["Block", []])),
    lambda t: t[11][1][-1][1].__setitem__(6, 3),
    lambda t: t[11][1][-1][1].__setitem__(6, [3]),
    lambda t: t[11][1][-1][1].__setitem__(2, 0),
    lambda t: t[11][1][-1][1].__setitem__(2, 254),
    lambda t: t[2].__setitem__(0, "Nnoe"),
    lambda t: t.__setitem__(10, True),
])
def test_known_dsl_traps_block(mutation):
    tree = fixture()
    mutation(tree)
    with pytest.raises(ValueError):
        clone_tree(tree)


def test_wrapped_tree_scalar_enum_arrays_and_invalid_cd_subjects_block():
    with pytest.raises(ValueError, match="裸"):
        clone_tree({"tree": fixture()})
    with pytest.raises(ValueError, match="CD"):
        clone_tree(root(area(["CD"])))
    bad = cmd("FindNearSubjects", -18, 1, 49, ["DoNothing"], 41,
              ["Block", [area(["CD"], target=41)]])
    with pytest.raises(ValueError, match="CD"):
        clone_tree(root(bad))
    bad_condition = cmd("CreateCondition", -17, [["ACMadeUp", []]], True, ["None"], "key", True, ["None"], None)
    with pytest.raises(ValueError):
        validate_tree(root(bad_condition))


def test_opening_summon_is_first_preserves_nullable_power_and_original_body():
    tree = fixture()
    changed = clone_tree(tree, summon={"multiballId": "1990001", "maxCount": 1, "selfOnly": True})
    body = changed["tree"][11][1]
    assert body[1:] == tree[11][1]
    assert body[0][1][:5] == ["FindMultiballSubjects", 900, 901, True, [1990001]]
    summon = next(node for _, node in walk(body[0]) if isinstance(node, list) and node[:1] == ["CreateSummonsMultiball"])
    assert summon[12] == ["Block", []] and summon[13] is None
    assert changed["summary"]["summon"]["countMode"] == "live-including-pending"
    assert any(check["code"].endswith("summon_nullable") for check in changed["checks"])
    with pytest.raises(ValueError, match="仅自身"):
        clone_tree(tree, summon={"multiballId": "1990001", "maxCount": 2, "selfOnly": True})
    group = clone_tree(tree, summon={"multiballId": "1990001", "maxCount": 3, "selfOnly": False})
    assert group["tree"][11][1][0][1][:4] == ["ConditionalsMultiballNumber", [1990001], [], 3]


def test_summon_nullable_does_not_hide_later_invalid_commands():
    tree = clone_tree(fixture(), summon={"multiballId": "1990001"})["tree"]
    tree[11][1].append(cmd("TypoAfterSummon"))
    with pytest.raises(ValueError, match="TypoAfterSummon"):
        validate_tree(tree)


def test_official_catalog_never_uses_modified_view_or_mod_only_keys():
    source = Source()
    entries = list_templates(source, "官方")
    assert entries["count"] == 1 and entries["templates"][0]["key"] == "donor"
    assert entries["templates"][0]["damageNodeCount"] == 2
    detail = template_detail(source, "donor")
    assert detail["tiers"][0]["name"] == "技能"
    assert detail["tiers"][0]["tree"] == fixture()
    assert len(detail["tiers"][0]["inputSha256"]) == 64
    assert "tree" not in public_detail(source, "donor")["tiers"][0]
    assert resolve_key(source, {"characterId": "151000"}) == "donor"
    assert OfficialSource(source).raw(detail["tiers"][0]["logical"]) == detail["tiers"][0]["raw"]
    with pytest.raises(ValueError, match="不存在"):
        template_detail(source, "mod_only")
    source.official["skill"] = {}
    with pytest.raises(ValueError, match="不可用"):
        list_templates(source)


def test_effect_mapping_is_private_family_only():
    tree = fixture()
    old, new = "battle/effect/skill_unique/donor", "battle/effect/skill_unique/new_actor/fx"
    result = clone_tree(tree, effect_mapping={old: new})
    assert result["summary"]["effectFamilies"] == [new]
    assert tree[11][1][0][1][2][1] == old + "/shine"


def test_resolve_element_effects_use_character_context_and_become_private_direct_paths():
    tree = fixture()
    base = "battle/effect/generic/shine"
    tree[11][1][0][1][2] = ["ResolveByElement", base, 255]
    with pytest.raises(ValueError, match="元素上下文"):
        effect_paths(tree)
    path = base + "/shine_blue/shine_blue"
    assert effect_paths(tree, 1) == [path]
    first = clone_tree(tree, scale=2, element=2, context_element=1)
    target = base + "/shine_yellow/shine_yellow"
    assert effect_paths(first["tree"], 1) == [target]
    private = "battle/effect/skill_unique/new_actor/private/shine_yellow"
    second = rewrite_effects(first["tree"], {target: private}, context_element=1)
    assert second["tree"][11][1][0][1][2] == ["SpecifyEffectDirectly", private]
    assert second["damageNodes"] == first["damageNodes"]
    assert effect_paths(tree, 1) == [path]


def test_ratio_and_fixed_damage_are_reported_and_scaled_by_their_own_numeric_slots():
    tree = root(cmd("CreateRatioAttack", -17, 2, [{"min": .1, "max": .2}]),
                cmd("CreateFixedAttack", -17, [{"min": 100, "max": 120}], ["Generic"]))
    result = clone_tree(tree, scale=2)
    assert [item["coefficientKind"] for item in result["damageNodes"]] == ["hp_ratio", "fixed_damage"]
    assert result["tree"][11][1][0][1][2] == 2
    assert result["damageNodes"][0]["coefficient"] == [{"min": .2, "max": .4}]
    assert result["damageNodes"][1]["coefficient"] == [{"min": 200, "max": 240}]


def test_shape_slv_array_cannot_contain_bare_numbers():
    box = area()
    box[1][9][1] = [20]
    with pytest.raises(ValueError, match="SLvValue"):
        clone_tree(root(box))


def test_all_ability_level_and_variable_coefficient_bounds_scale_without_changing_bindings():
    node = attack()
    term = node[1][6][0]
    for level in ("alv", "alv2", "alv3", "alv4", "alv5", "alv6"):
        term[level + "_min"], term[level + "_max"] = 4, 6
    term["vlv"] = [{"min": 7, "max": 9, "vid": 901}]
    tree = root(node)
    changed = clone_tree(tree, scale=2)
    coefficient = changed["damageNodes"][0]["coefficient"][0]
    assert coefficient["min"] == 4 and coefficient["max"] == 6
    assert all(coefficient[name + "_min"] == 8 and coefficient[name + "_max"] == 12
               for name in ("alv", "alv2", "alv3", "alv4", "alv5", "alv6"))
    assert coefficient["vlv"] == [{"min": 14, "max": 18, "vid": 901}]
    path = changed["damageNodes"][0]["path"]
    with pytest.raises(ValueError, match="多项运行时"):
        clone_tree(tree, node_coefficients={path: 7})
    exact = clone_tree(tree, node_coefficients={path: [{"alv2_min": 20, "alv2_max": 30}]})
    assert exact["damageNodes"][0]["coefficient"][0] == {**term, "alv2_min": 20, "alv2_max": 30}
    with pytest.raises(ValueError, match="运行时倍率变量"):
        clone_tree(tree, node_coefficients={path: [{"vlv": [{"min": 4, "max": 5, "vid": 902}]}]})


def test_official_alv_only_terms_nullable_summon_callback_and_integer_power_binding():
    tree = clone_tree(root(attack()), summon={"multiballId": "1990001"})["tree"]
    summon = next(node for _, node in walk(tree) if isinstance(node, list) and node[:1] == ["CreateSummonsMultiball"])
    summon[12], summon[13] = None, 1
    tree[11][1][-1][1][6] = [{"alv_min": 2, "alv_max": 4}]
    result = clone_tree(tree, scale=3)
    assert result["damageNodes"][0]["coefficient"] == [{"alv_min": 6, "alv_max": 12}]
    assert summon[12] is None and summon[13] == 1
    summon[13] = {}
    with pytest.raises(ValueError, match="整数能力绑定"):
        clone_tree(tree)


def test_preview_url_requires_successful_render_with_cells(monkeypatch):
    import wf.studio.effect_render as render
    source = Source()
    ref = "battle/effect/skill_unique/donor/shine"
    for name, logical in render.effect_files(ref).items():
        if name != "name":
            source.raws[logical] = source.live_raws[logical] = b"synthetic"
    monkeypatch.setattr(render, "bake", lambda *args: ({"ok": False, "issues": ["bad frame"]}, None))
    assert public_detail(source, "donor")["effects"][0]["previewUrl"] is None
    monkeypatch.setattr(render, "bake", lambda *args: ({"ok": True, "cells": [{"w": 1}], "issues": []}, b"png"))
    assert public_detail(source, "donor")["effects"][0]["previewUrl"].startswith("/api/studio/effect.png?path=")


def test_catalog_excludes_unsafe_readable_donor_and_detail_explains_failure():
    source = Source()
    logical = next(iter(source.raws))
    source.raws[logical] = stored(root(cmd("ConstructorTypo")))
    result = list_templates(source)
    assert result["count"] == 0 and "ConstructorTypo" in result["unavailable"][0]["reason"]
    assert not template_detail(source, "donor", previews=False)["cloneable"]


@pytest.mark.parametrize("options", [{"scale": float("nan")}, {"scale": -1}, {"element": 6},
                                    {"element": True}, {"attribution": True}])
def test_invalid_numeric_requests_block(options):
    with pytest.raises(ValueError):
        clone_tree(fixture(), **options)
