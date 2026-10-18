"""M4c glue: panel-text view, key search and slots never write and match wf text."""
import pytest

from wf.studio.ability_routes import AbilityRoutes
from wf.studio.ability_text import load_mirrors, workspace_for
from wf.studio.ability_engine import EditState
from wf.studio.drafts import DraftError
from wf.studio.text_panel import custom_owners
from wf.text.model import CHARACTER
from test_studio_ability_text import setup


def field(panel, location):
    return next(f for f in panel["fields"] if f["location"] == location)


def test_panel_lists_fields_rules_and_effective_server(tmp_path):
    ed, _ = setup(tmp_path)
    panel = ed.text_panel("139985")
    override = field(panel, "desc_override.desc_override_first")
    assert override["owners"] == ["139985"] and override["base"] == "自身攻击力提升"
    assert {h["id"] for h in override["house"]} == {"house.tautology", "house.leader-self", "house.core-name"}
    assert all(r["requirement"] for r in override["rules"])
    assert {"action_skill.1.c0", "action_skill.3.c1"} <= {f["location"] for f in panel["fields"]}
    assert panel["server"]["effectiveSource"].endswith("character_text_rank_p5b.json")
    assert all(c["match"] for c in panel["server"]["columns"])
    assert ed.store.load("139985") is None


def test_lint_projects_proposed_text_and_flags_house_rules(tmp_path):
    ed, _ = setup(tmp_path)
    text = {"desc_override": {"desc_override_first": {"old": "自身攻击力提升", "new": "自身为队长时，生命值100%以下时攻击力+10%"}},
            "action_skill": {"1": {"c0": {"old": "斩击", "new": "力量之核"}}}}
    panel = ed.text_panel("139985", text=text, light=True)
    house = {h["id"]: h["state"] for h in field(panel, "desc_override.desc_override_first")["house"]}
    assert house["house.tautology"] == "问题"
    # Key has no _leader/_1 suffix, so only the editor-side check sees it.
    assert house["house.leader-self"] == "问题"
    name = {h["id"]: h["state"] for h in field(panel, "action_skill.1.c0")["house"]}
    assert name["house.core-name"] == "问题"
    # Mirrors follow the projected skill text, as wf text would sync them.
    assert panel["server"]["columns"][0]["server"] == "力量之核"
    assert ed.store.load("139985") is None
    with pytest.raises(DraftError):
        ed.text_panel("139985", text={"desc_override": {"missing": {"old": "", "new": "x"}}}, light=True)


def test_cross_tier_wording_finding_reaches_each_description(tmp_path):
    ed, _ = setup(tmp_path)
    panel = ed.text_panel("139985", text={"action_skill": {"2": {"c1": {"old": "攻击敌人", "new": "攻击全体敌人并提升自身攻击"}}}},
                          light=True)
    rules = {f["rule"] for f in field(panel, "action_skill.1.c1")["findings"]}
    assert "text.standard.skill-tier-wording" in rules


@pytest.mark.parametrize("shared", [False, True])
def test_custom_owner_prefilter_equals_full_scan(tmp_path, shared):
    ed, _ = setup(tmp_path, shared=shared)
    state = EditState(ed.source)
    load_mirrors(state, **ed.inputs)
    workspace = workspace_for(state)
    keys = list(workspace.table("master/string/custom_ability_string.orderedmap"))
    full = {key: [o for o in workspace.table(CHARACTER) if key in workspace.custom_keys(o)] for key in keys}
    assert custom_owners(workspace, keys) == full
    assert full["desc_override_first"] == (["139985", "100"] if shared else ["139985"])


def test_slots_and_key_search(tmp_path):
    ed, _ = setup(tmp_path, shared=True)
    slots = ed.read("139985")["slots"]
    assert slots["ability"][0] == "1001" and slots["leader_ability"] == "100" and slots["action_skill"] == "hero"
    found = ed.key_search("ability", "1001", cid="139985", names={"139985": "英雄"})
    assert found["results"][0]["key"] == "1001"
    assert [o["id"] for o in found["results"][0]["owners"]] == ["100", "139985"]
    assert ed.key_search("ability", "英雄", names={"139985": "英雄"})["total"] == 1
    assert ed.key_search("action_skill", "hero")["results"][0]["levels"] == ["1", "2", "3"]
    with pytest.raises(DraftError):
        ed.key_search("custom_ability_string", "")


def test_new_routes_are_registered_and_lint_is_post_only():
    routes = {(verb, pattern.pattern) for verb, pattern, _ in AbilityRoutes(app=None).routes()}
    assert ("GET", r"^/api/studio/ability/keys$") in routes
    assert ("GET", r"^/api/characters/(?P<cid>\d+)/text$") in routes
    assert ("POST", r"^/api/drafts/(?P<cid>\d+)/text/lint$") in routes
