"""Vocabulary provenance, view isolation and units; never writes draft data."""
from types import SimpleNamespace
from pathlib import Path
import json

import pytest

import wf_describe
from scripts.ability_as3 import EnumValue, Reader, prune_ternaries
from scripts.generate_ability_official import generate
from wf.studio.ability_glossary import UI_STRING, build_glossary, clean_template, glossary, official_map
from wf.studio.ability_routes import AbilityRoutes
from wf.studio.ability_vocabulary import enum_groups, field_rules


class Source:
    version = "same-version"

    def __init__(self, frozen="迟缓效果"):
        self.calls = 0
        self.strings = {
            "ability_description_condition_target_enemy_frozen": frozen,
            "ability_description_condition_target_member_frozen": "疲惫效果",
            "ability_description_condition_content_enemy_frozen": "施加::if !withoutTarget::::target::::end::迟缓效果",
            "ability_description_condition_content_member_frozen": "施加::if !withoutTarget::::target::::end::疲惫效果",
            "ability_description_common_content_condition_slayer": "::if !withoutTarget::::target::::end::对::condition::中的敌人造成的伤害 ::percent_up_down::",
            "ability_description_common_content_stun_wince_slayer": "::if !withoutTarget::::target::的::end::追击伤害 ::percent_up_down::",
            "ability_description_target_member_at": "第::index::名角色",
        }

    def table(self, name):
        assert name == UI_STRING
        self.calls += 1
        return {k: [[v]] for k, v in self.strings.items()}


def entry(data, group, value):
    return next(e for e in data["groups"][group]["values"] if e["value"] == str(value))


@pytest.fixture(scope="module")
def full_glossary():
    source = Source()
    fixture = Path(__file__).parent / "fixtures/ability_glossary_strings.json"
    source.strings = json.loads(fixture.read_text(encoding="utf-8"))["strings"]
    return build_glossary(source)


def test_outer_effects_are_distinct_and_keep_fixed_conditions_and_elements(full_glossary):
    terms = [entry(full_glossary, "instant_content", n) for n in (119, 311, 410)]
    assert len({term["official"] for term in terms}) == 3
    assert all("迟缓" in term["official"] for term in terms)
    assert "造成的伤害" in terms[0]["official"] and "减少" in terms[1]["official"]
    assert terms[2]["official"].startswith("施加")
    binding = terms[0]["officialArguments"]["condition"]
    assert binding["sources"][0]["key"].endswith("condition_target_enemy_frozen")
    assert binding["sources"][0]["evidence"]
    for value, element in ((2, "全属性"), (3, "火"), (4, "水"), (5, "雷"), (6, "风"), (7, "光"), (8, "暗")):
        assert element in entry(full_glossary, "instant_content", value)["official"]
    assert "火" in entry(full_glossary, "during_content", 5)["official"]  # ResistanceRed
    assert "火抗性提升效果" in entry(full_glossary, "instant_content", 101)["official"]
    assert "火抗性提升效果" in entry(full_glossary, "instant_content", 234)["official"]
    assert "火" in entry(full_glossary, "instant_content", 251)["official"]
    # Condition element is fixed; the outer resistance element is a row field.
    nested = entry(full_glossary, "instant_content", 636)
    assert nested["officialArguments"]["condition"]["text"] == "火抗性提升效果"
    assert "element" not in nested["officialArguments"]


@pytest.mark.parametrize("group,min_unique,min_named,min_ratio", [
    ("precondition", 150, 200, 0.70),
    ("trigger", 230, 250, 0.85),
    ("during_trigger", 165, 225, 0.70),
    ("instant_content", 475, 705, 0.65),
    ("during_content", 390, 415, 0.90),
])
def test_large_group_name_diversity_cannot_regress(full_glossary, group, min_unique, min_named, min_ratio):
    names = [e["official"] for e in full_glossary["groups"][group]["values"] if e["official"]]
    # Coverage floor prevents passing by dropping difficult or repeated names.
    assert len(names) >= min_named
    assert len(set(names)) >= min_unique
    assert len(set(names)) / len(names) >= min_ratio


def test_auxiliary_keys_are_never_effect_names_and_polarity_is_neutral(full_glossary):
    for value, fragment in ((0, "自身获得的经验"), (1, "队伍全体获得的经验"), (2, "玛纳")):
        opening = entry(full_glossary, "opening", value)
        assert fragment in opening["official"]
        assert "opening_kind_" in opening["officialKey"]
    assert entry(full_glossary, "instant_content", 629)["official"] is None
    for value in (0, 2, 3, 391, 393):
        effect = entry(full_glossary, "instant_content", value)
        assert "提升" not in effect["official"] and "降低" not in effect["official"]
        assert "condition_content_" in effect["officialKey"]
    assert entry(full_glossary, "instant_content", 470)["official"] is None
    for group in ("instant_content", "during_content", "opening"):
        for term in full_glossary["groups"][group]["values"]:
            assert not term["officialKey"] or not any(aux in term["officialKey"] for aux in
                ("condition_target_", "not_unisonable", "target_myself", "target_separator"))


def test_missing_outer_template_does_not_fall_back_to_a_noun():
    source = Source()
    source.strings = {"ability_description_condition_target_enemy_frozen": "迟缓效果"}
    data = build_glossary(source)
    assert all(entry(data, "instant_content", value)["official"] is None for value in (119, 311, 410))


def test_enemy_frozen_uses_slow_official_term_and_keeps_literal_translation():
    data = build_glossary(Source())
    # EnemyConditionFrozen / Nearest / Trigger variants resolve Frozen/ACFrozen
    # against the enemy-side template, not the member's fatigue template.
    for value in (410, 433, 456):
        frozen = entry(data, "instant_content", value)
        assert "迟缓" in frozen["official"]
        assert "冻结" in frozen["cn"]
        assert frozen["officialKey"] == "ability_description_condition_content_enemy_frozen"
        assert frozen["mappingStatus"] == "as3" and frozen["evidence"]
    assert entry(data, "instant_content", 20)["official"] == "施加…疲惫效果"
    assert entry(data, "during_content", 21)["official"] == "…的追击伤害…"
    assert entry(data, "target", 3)["official"] == "第2名角色"


def test_crosswalk_covers_every_value_and_preserves_provenance():
    groups = official_map()["groups"]
    for group, options in enum_groups().items():
        assert groups[group].keys() == options.keys()
        for record in groups[group].values():
            for mapping in record["keys"]:
                assert mapping["status"] in ("as3", "guess")
                assert bool(mapping["evidence"]) == (mapping["status"] == "as3")
                for evidence in mapping["evidence"]:
                    file, number = evidence.rsplit(":", 1)
                    assert file.endswith(".as") and int(number) > 0
    # These extensions are absent from the archived client's enum tree.
    assert not groups["instant_content"]["724"]["keys"]


@pytest.mark.parametrize(("text", "expected"), [
    ("施加::if !withoutTarget::::target::::end::迟缓效果", "施加…迟缓效果"),
    ("攻击力::if up::提升::if target::::target::::end::::else::降低::end::", "攻击力"),
    ("::if a::甲::elseif b::乙::else::丙::end::词条 ::power::%", "词条…%"),
    ("<icon id='red'> ::value::", None),
    ("::condition::期间", "…期间"),
    ("消耗「::name::」等级", "消耗「…」等级"),
    ("追击伤害提升::percent::%&nbsp;", "追击伤害提升…%"),
    ("（独立伤害乘区3）", "（独立伤害乘区3）"),
    ("技能槽在::percent::以上时", "技能槽在…以上时"),
    ("对敌人造成::times::威力的::element_short::伤害", "对敌人造成…威力的…伤害"),
])
def test_clean_template(text, expected):
    assert clean_template(text) == expected


def test_glossary_http_shape_and_view_cache():
    source = Source()
    routes = AbilityRoutes(SimpleNamespace(source=source))
    handler = next(h for verb, pattern, h in routes.routes()
                   if verb == "GET" and pattern.fullmatch("/api/studio/ability/glossary"))
    response = handler({})
    assert response.status == 200
    data = json.loads(response.body)
    assert set(wf_describe._BIG_ENUMS) <= data["groups"].keys()
    sample = entry(data, "instant_content", 410)
    assert {"value", "en", "cn", "official", "officialTemplate", "officialKey", "evidence", "uses"} <= sample.keys()
    assert isinstance(sample["uses"], int)
    assert data["formats"]["scaled_frames"] == {"divisor": 100000, "unit": "帧", "fps": 60}
    assert handler({}).body == response.body and source.calls == 1
    other = Source("不同视图的迟缓效果")
    assert "不同视图的迟缓效果" in entry(glossary(other), "instant_content", 119)["official"]
    assert "不同视图" not in entry(glossary(source), "instant_content", 119)["official"]


def test_missing_official_words_do_not_turn_literal_translation_into_official():
    source = Source()
    source.strings = {}
    data = build_glossary(source)
    assert all(e["official"] is None for g in data["groups"].values() for e in g["values"])
    assert entry(data, "instant_content", 410)["cn"]
    assert entry(data, "instant_content", 32)["uses"] > 0


def test_field_units_and_distinct_enum_tables_in_both_native_layouts():
    rules = field_rules()
    assert "action_skill" not in rules
    for table in ("ability", "leader_ability"):
        b = wf_describe.layout(table)["blocks"]
        rule = lambda block, offset: rules[table][str(b[block] + offset)]
        assert rule("precondition1", 1)["enum"] == "during_puller"
        assert rule("instant_trigger", 1)["enum"] == "instant_puller"
        assert rule("during_accumulation_trigger", 1)["enum"] == "instant_puller"
        assert rule("during_trigger", 1)["enum"] == "during_puller"
        assert rule("instant_content", 30)["enum"] == "instant_puller"
        assert rule("instant_precontent", 1)["enum"] == "precontent_target"
        assert rule("instant_content", 10)["format"] == "scaled_frames"
        assert rule("instant_trigger", 8)["format"] == "frames"
        assert rule("instant_delay", 0)["format"] == "seconds"
        assert str(b["instant_content"] + 22) not in rules[table]  # time is kind-dependent.


def test_generator_proves_switch_chain_but_labels_name_fallback_as_guess(tmp_path):
    root = tmp_path / "pinball/common/data/ability"
    root.mkdir(parents=True)
    enum = root / "ConditionTargetKind.as"
    enum.write_text('new ConditionTargetKind("Frozen",11,null);', encoding="utf-8")
    (root / "InstantAbilityContentMasterValue.as").write_text(
        'new InstantAbilityContentMasterValue("EnemyConditionFrozen",410,null);', encoding="utf-8")
    (root / "TestResolver.as").write_text('''
      public static function resolve(param1:InstantAbilityContentMasterValue) : Object
      {
         switch(param1.index)
         {
            case 410:
               return ConditionTargetKind.Frozen;
         }
      }
''', encoding="utf-8")
    desc = root / "description"
    desc.mkdir()
    (desc / "TestDescription.as").write_text('''
      public static function stringfyConditionTarget(param1:ConditionTargetKind) : String
      {
         switch(param1.index)
         {
            case 11:
               return env.get("ability_description_condition_target_enemy_frozen");
         }
      }
      public static function unrelated() : String
      {
         return env.get("ability_description_during_trigger_kind_stunify_up");
      }
''', encoding="utf-8")
    result = generate(tmp_path)
    frozen = result["groups"]["instant_content"]["410"]["keys"][0]
    assert frozen["status"] == "as3" and len(frozen["evidence"]) == 2
    stun = next(e for e in result["groups"]["during_trigger"].values() if e["en"] == "StunifyUp")
    assert stun["keys"][0]["status"] == "guess"
    assert stun["keys"][0]["evidence"] == []


def test_as3_known_branch_and_ternary_do_not_leak_other_target_names(tmp_path):
    (tmp_path / "pinball/common/data/ability").mkdir(parents=True)
    reader = Reader(tmp_path)
    reader.enums["AbilityTargetKind", "ExceptMyself"] = 1
    assert reader.evaluate("AbilityTargetKind.ExceptMyself(OrCharacterGroup_Impl_.resolveOptional(x,y))", {}).type == "AbilityTargetKind"
    body = '''
         switch(param1.index)
         {
            case 1:
               n = int(param1.params[0]);
               if(n == 0)
               {
                  return "leader";
               }
               return "member";
         }
'''
    lines = list(reader.select(body, 1, {"param1": EnumValue("Member", 1, (1,))}))
    assert '"leader"' not in "\n".join(line for _, line, _ in lines)
    assert prune_ternaries('flag ? "others" : (mode ? "party_a" : "party_b")', reader, {"flag": False}) == '(mode ? "party_a" : "party_b")'


def test_as3_records_outer_template_push_and_nested_element_without_target_hijack(tmp_path):
    root = tmp_path / "pinball/common/data/ability/description"
    root.mkdir(parents=True)
    (root / "Fixture.as").write_text('''
      public static function stringfyCommonCharacterContent(param1:CommonAbilityCharacterContent) : String
      {
         switch(param1.index)
         {
            case 0:
               condition = param1.params[0];
               value = env.get("ability_description_common_content_condition_slayer");
               target = env.get("ability_description_target_party");
               extra = env.get("ability_description_condition_content_initial_accumulation");
               noun = AbilityDescriptionTools.stringfyConditionTarget(condition);
               env.push("condition",noun);
               return value;
         }
      }
'''.replace("env.push", "param1.env.push"), encoding="utf-8")
    (root / "AbilityDescriptionTools.as").write_text('''
      public static function stringfyConditionTarget(param1:ConditionTargetKind) : String
      {
         switch(param1.index)
         {
            case 4:
               element = int(param1.params[0]);
               return container.getUiStringWithContext("ability_description_condition_target_good_resistance",{"element":AbilityDescriptionTools.stringfyElementTarget(element)});
         }
      }
      public static function stringfyElementTarget(param1:int) : String
      {
         return "element name";
      }
''', encoding="utf-8")
    reader = Reader(tmp_path)
    trace = reader.trace_for(EnumValue("CommonAbilityCharacterContent", 0, (EnumValue("ConditionTargetKind", 4, (1,)),)))
    bindings = trace["bindings"]
    outer = bindings["ability_description_common_content_condition_slayer"]["condition"][0]
    assert outer["key"] == "ability_description_condition_target_good_resistance"
    assert any("Fixture.as:" in e for e in outer["evidence"])
    assert bindings[outer["key"]]["element"][0]["text"] == "火"
    assert "ability_description_target_party" not in bindings
    assert "ability_description_condition_content_initial_accumulation" not in bindings


def test_templates_receive_official_names_without_changing_defaults(tmp_path):
    from test_studio_ability import Source as RawSource, editor
    import wf_quest_lib as codec
    source = RawSource()
    original = editor(tmp_path / "before", source).templates(kind=53)["options"][0]
    source.raw[UI_STRING] = codec.build_node({"ability_description_common_content_stun_wince_slayer": "追击伤害提升"})
    # A fresh source instance is a different immutable view/cache identity.
    updated = RawSource()
    updated.raw = source.raw
    translated = editor(tmp_path / "after", updated).templates(kind=53)["options"][0]
    assert translated["official"] == "追击伤害提升"
    assert translated["defaults"] == original["defaults"]
