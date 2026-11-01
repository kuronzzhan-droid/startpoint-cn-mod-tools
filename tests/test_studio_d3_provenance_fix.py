"""D3 provenance regressions use independent synthetic official/live data."""
from copy import deepcopy
import json

import pytest

from wf.studio.ability_glossary import UI_STRING, build_glossary
from wf.studio.translation import annotate_catalog, annotate_panel
from test_studio_glossary import Source as GlossarySource, entry
from test_studio_character_clone import env as clone_env, OLD, NEW, request


class VerifiedGlossary(GlossarySource):
    baseline_error = None

    def __init__(self):
        super().__init__()
        self.strings["element_kind_red_full"] = "火属性"
        self.baseline = deepcopy(self.strings)

    def table(self, name, official=False):
        assert name == UI_STRING
        return {k: [[v]] for k, v in (self.baseline if official else self.strings).items()}


def test_glossary_original_requires_independent_matching_baseline():
    source = VerifiedGlossary()
    original = entry(build_glossary(source), "element", 1)
    assert original["translation"]["source"] == "官方原文"
    assert original["translation"]["uncertain"] is False
    source.strings["element_kind_red_full"] = "改写的火属性"
    changed = entry(build_glossary(source), "element", 1)
    assert changed["official"] == "改写的火属性"
    assert changed["translation"]["source"] == "人工"
    assert changed["translation"]["uncertain"] is True


@pytest.mark.parametrize("unavailable", ["missing", "error", "unsupported"])
def test_glossary_missing_baseline_never_claims_certain_official(unavailable):
    source = VerifiedGlossary()
    if unavailable == "missing":
        source.baseline = {}
    elif unavailable == "error":
        source.baseline_error = "fixture baseline read failed"
    else:
        source = GlossarySource()
        source.strings["element_kind_red_full"] = "火属性"
    term = entry(build_glossary(source), "element", 1)
    assert term["translation"]["uncertain"] is True
    assert term["translation"]["source"] != "官方原文"


def test_glossary_nested_argument_is_compared_with_official_baseline():
    source = VerifiedGlossary()
    before = entry(build_glossary(source), "instant_content", 119)
    source.strings["ability_description_condition_target_enemy_frozen"] = "MOD 冰冻"
    after = entry(build_glossary(source), "instant_content", 119)
    assert before["officialTemplate"] == after["officialTemplate"]
    assert "MOD 冰冻" in after["official"]
    assert before["officialBaselineMatch"] is True
    assert after["officialBaselineMatch"] is False
    assert after["translation"]["source"] == "人工"


class PanelSource:
    baseline_error = None

    def __init__(self):
        character = [""] * 37
        character[8], character[17], character[19] = "own", "leader", "ability"
        self.tables = {
            "character": {"1": [character]},
            "skill": {"own": {"1": [["技能", "官方说明"]]},
                      "borrowed": {"1": [["他人技能", "借用的原文"]]}},
            "leader": {"leader": [["leader_row"]]},
            "ability": {"ability": [["own_row"]], "other": [["borrowed_row"]]},
            "strings": {"desc_override_own_row": [["自身攻击力提升"]],
                        "desc_override_borrowed_row": [["借用的能力文案"]]},
        }

    def table(self, name, official=False):
        return self.tables.get(name, {})


def skill_field(key="own", value="官方说明"):
    return {"surface": "action_skill", "key": key, "tier": "1", "field": "c1",
            "location": "action_skill.1.c1", "value": value, "original": value}


@pytest.mark.parametrize("cid,key,value,is_official", [
    ("1", "own", "官方说明", True),
    ("2", "own", "官方说明", False),  # New MOD character reuses official skill.
    ("1", "borrowed", "借用的原文", False),  # Existing character reattaches another skill.
])
def test_panel_requires_official_character_and_original_skill_binding(cid, key, value, is_official):
    result = annotate_panel(PanelSource(), {"characterId": cid, "fields": [skill_field(key, value)]})
    assert (result["fields"][0]["translation"]["source"] == "官方原文") is is_official


@pytest.mark.parametrize("cid,row_name,is_official", [
    ("1", "own_row", True), ("1", "borrowed_row", False), ("2", "own_row", False),
])
def test_catalog_requires_official_ability_ownership(cid, row_name, is_official):
    source = PanelSource()
    group = {"descriptionSource": "游戏面板覆盖文案", "rows": [{"values": [row_name]}],
             "description": source.tables["strings"]["desc_override_" + row_name][0][0]}
    annotate_catalog(source, [group], [], "own", cid=cid)
    assert (group["translation"]["source"] == "官方原文") is is_official


def test_panel_baseline_error_cannot_be_hidden_by_cached_matching_rows():
    source = PanelSource()
    source.baseline_error = "read failed"
    result = annotate_panel(source, {"characterId": "1", "fields": [skill_field()]})
    assert result["fields"][0]["translation"]["source"] == "人工"
    assert result["fields"][0]["translation"]["uncertain"] is True


@pytest.mark.parametrize("key,reference", [("change_skill_hero", None),
                                          ("custom_token", "battle/action/custom$custom_token")])
def test_official_custom_string_preserves_text_workspace_ownership(key, reference):
    source = PanelSource()
    source.tables["character"]["1"][0][0] = "hero"
    source.tables["strings"][key] = [["官方强化说明"]]
    if reference:
        source.tables["ability"]["ability"][0].append(reference)
    field = {"surface": "custom_ability_string", "key": key, "location": key,
             "value": "官方强化说明", "original": "官方强化说明"}
    original = annotate_panel(source, {"characterId": "1", "fields": [field]})
    assert original["fields"][0]["translation"]["source"] == "官方原文"
    assert original["fields"][0]["translation"]["uncertain"] is False
    borrowed = annotate_panel(source, {"characterId": "2", "fields": [field]})
    assert borrowed["fields"][0]["translation"]["source"] == "人工"


def test_official_custom_string_does_not_claim_another_character_variant_prefix():
    source = PanelSource()
    source.tables["character"]["1"][0][0] = "hero"
    variant = deepcopy(source.tables["character"]["1"])
    variant[0][0] = "hero_summer"
    source.tables["character"]["2"] = variant
    key = "change_skill_hero_summer"
    source.tables["strings"][key] = [["官方夏日说明"]]
    field = {"surface": "custom_ability_string", "key": key, "location": key,
             "value": "官方夏日说明", "original": "官方夏日说明"}
    result = annotate_panel(source, {"characterId": "1", "fields": [field]})
    assert result["fields"][0]["translation"]["source"] == "人工"
    result = annotate_panel(source, {"characterId": "2", "fields": [field]})
    assert result["fields"][0]["translation"]["source"] == "官方原文"


def test_catalog_empty_slots_have_no_translation_but_valid_skill_keeps_it():
    empty = {"descriptionSource": "工具生成", "description": "未配置", "rows": []}
    skill = {"kind": "main", "level": "1", "description": "官方说明", "raw": ["技能", "官方说明"]}
    annotate_catalog(PanelSource(), [empty], [skill], "own", cid="1")
    assert "translation" not in empty
    assert skill["translation"]["source"] == "官方原文"
    annotate_catalog(PanelSource(), [], [skill], "", cid="scratch-empty")
    assert "translation" not in skill


def test_wiki_and_character_detail_clone_reused_official_skill_is_not_original(clone_env):
    from wf.studio.character_clone import clone
    from wf.studio.server import StudioApp
    from wf.studio.wiki_preview import preview
    from types import SimpleNamespace
    import wf_mod_tool as binary

    source, store, ops, _ = clone_env
    official_files = {}
    for (root, logical), raw in source.view.files.items():
        digest = binary.sha1_path(logical)
        official_files[root, digest[:2] + "/" + digest[2:]] = raw
    source._baseline = SimpleNamespace(get=lambda root, key: official_files.get((root, key)))
    official = preview(ops, OLD)["card"]["skills"][0]
    assert official["translation"]["source"] == "官方原文"
    clone(ops, request(skill="reuse"))
    borrowed = preview(ops, NEW)["card"]["skills"][0]
    assert borrowed["description"] == official["description"]
    assert borrowed["translation"]["source"] == "人工"
    assert borrowed["translation"]["uncertain"] is True
    app = StudioApp(source, drafts=store, screenshot_dirs=[])
    response = app.dispatch("GET", f"/api/characters/{NEW}", {})
    assert response.status == 200, response.body
    assert json.loads(response.body)["skills"][0]["translation"]["source"] == "人工"


def test_character_http_detail_refreshes_saved_draft_text_and_attribution(tmp_path):
    from test_studio_ability_text import setup, text_operations
    from wf.studio.server import StudioApp
    from wf.studio.source import StudioSource
    from wf_wiki_catalog_source import TABLES

    editor, server = setup(tmp_path)
    raw = editor.source
    raw.tip, raw.zips, raw.extra_zips = raw.version, [], []
    source = StudioSource(raw)
    # Materialize a separate official snapshot without loading any local CDN.
    for name in ("character", "ability", "leader", "skill", "strings"):
        source._tables[TABLES[name], True] = deepcopy(source.table(name))
    app = StudioApp(source, drafts=editor.store, server_dir=server, screenshot_dirs=[])
    editor = app.abilities.editor()
    url = "/api/characters/139985"
    before = json.loads(app.dispatch("GET", url, {}).body)
    assert before["skills"][0]["description"] == "攻击敌人"
    assert before["skills"][0]["translation"]["source"] == "官方原文"
    editor.apply("139985", {"operations": text_operations("对敌人造成伤害")})
    editor.store.save("139985")
    state = editor._base("139985")[0]
    inputs = dict(state.original)
    response = app.dispatch("GET", url, {})
    assert response.status == 200, response.body
    after = json.loads(response.body)
    assert {skill["description"] for skill in after["skills"]} == {"对敌人造成伤害"}
    assert all(s["translation"]["source"] == "人工" and not s["translation"]["uncertain"]
               for s in after["skills"])
    assert state.original == inputs  # Reading detail must not mutate cached draft inputs.
    assert source.table("skill")["hero"]["1"][0][1] == "攻击敌人"
    change = editor.store.load("139985")["changes"][0]["id"]
    editor.store.revert("139985", change)
    reverted = json.loads(app.dispatch("GET", url, {}).body)
    assert reverted["skills"][0]["description"] == "攻击敌人"
    assert reverted["skills"][0]["translation"]["source"] == "官方原文"
