"""Read-only glue behind the BOSS工坊 pages: overview modes, template whitelist,
options, the boss draft view, blocked previews that keep every five-state result,
and the shared leaf-history cache of immutable views."""
from __future__ import annotations

import json

from wf.boss import provenance
from wf.boss.reader import BossReader
from wf.studio.boss_catalog import DEFAULT_TEMPLATE, draft_summary, enrich_listing, options, template_sources
from wf.studio.drafts import DraftStore
from wf.studio.server import StudioApp
from test_studio_boss_checks import fixture_editor, request


def test_listing_adds_mode_element_and_both_boss_flags(tmp_path):
    editor = fixture_editor(tmp_path)
    reader = BossReader(editor.source)
    listing = enrich_listing(reader, reader.list())
    item = next(i for i in listing["items"] if i["selector"] == DEFAULT_TEMPLATE)
    assert item["mode"] == "shared" and item["bothBoss"] is False
    assert item["recommendedElement"] == item["recommendedElement"].strip() and item["fieldData"]
    assert all("mode" in group for group in listing["groups"])
    assert {m["id"] for m in listing["modes"]} >= {"main_lord", "lord", "shared", "five", "practice", "other"}
    # Same selectors as the plain read model: modes never rename anything.
    assert [i["selector"] for i in listing["items"]] == [i["selector"] for i in reader.list()["items"]]


def test_template_whitelist_offers_default_and_reasons(tmp_path):
    editor = fixture_editor(tmp_path)
    result = template_sources(BossReader(editor.source))
    assert result["default"] == DEFAULT_TEMPLATE
    default = [s for s in result["sources"] if s["default"]]
    assert [s["selector"] for s in default] == [DEFAULT_TEMPLATE]
    assert all(s["mode"] in {"main_lord", "lord", "shared"} for s in result["sources"])
    assert all(isinstance(x["reason"], str) and x["count"] > 0 for x in result["excluded"])


def test_options_list_view_bgm_groups_and_scenes(tmp_path):
    editor = fixture_editor(tmp_path)
    result = options(BossReader(editor.source))
    assert result["bgm"] and all("id" in b and isinstance(b["tracks"], list) for b in result["bgm"])
    assert result["scenes"] and all("id" in s for s in result["scenes"])


def test_blocked_preview_keeps_summary_first_and_every_rule_result(tmp_path):
    editor = fixture_editor(tmp_path)
    preview = editor.preview("new", request(parameters={"level": 999}))
    assert not preview["ok"]
    summary, *rules = preview["checks"]
    assert summary["rule"] == "boss.inputs" and summary["blocking"] and "U_3be147" in summary["message"]
    level = next(c for c in rules if c["rule"] == "boss.enemy-level")
    assert level["status"] == "问题" and level["blocking"] and level["quest"]
    assert any(not c["blocking"] for c in rules)


def test_passing_preview_names_the_quest_of_each_result(tmp_path):
    editor = fixture_editor(tmp_path)
    preview = editor.preview("new", request())
    assert preview["ok"]
    quests = {c["quest"] for c in preview["checks"]}
    assert quests == {f"hard_multi:{preview['allocation']['event']}/1"}


def test_boss_draft_view_and_summary_follow_the_character_shape(tmp_path):
    editor = fixture_editor(tmp_path)
    app = StudioApp(editor.source, drafts=DraftStore(tmp_path / "drafts"), server_dir=editor.server_dir)
    app.boss.editor.server_dir = editor.server_dir
    created = app.boss.editor.apply("new", request(name="演示"))
    quest = created["questId"]
    response = app.dispatch("GET", "/api/boss/drafts/" + quest, {})
    view = json.loads(response.body)
    assert response.status == 200 and view["questId"] == quest and view["subjectKind"] == "boss"
    assert view["status"]["state"] == "dirty" and [a["id"] for a in view["actions"]][:3] == ["save", "generate", "export"]
    listing = json.loads(app.dispatch("GET", "/api/boss/drafts", {}).body)["drafts"]
    entry = next(d for d in listing if d["characterId"] == quest)
    assert entry["created"]["name"] == "演示" and entry["created"]["sourceQuest"] == DEFAULT_TEMPLATE
    assert entry["status"]["state"] == "dirty" and entry["requestCount"] == 1
    assert draft_summary({"characterId": "x"}, None)["status"]["state"] == "clean"


class _View:
    def __init__(self, zips):
        self.zips, self.store = list(zips), "store"


class _Overlay(_View):
    changes = []


def test_leaf_histories_are_shared_only_for_the_same_immutable_view():
    view = _View(["a.zip", "b.zip"])
    first = provenance._histories_for(view)
    first["x"] = {"leaf": "a.zip"}
    assert provenance._histories_for(view) is first
    assert provenance.BossTables(view).histories is first
    view.zips.append("c.zip")  # a different ZIP list never reuses the old histories
    assert provenance._histories_for(view) is not first
    assert provenance._histories_for(_View(["a.zip", "b.zip"])) is not first
    overlay = _Overlay([])
    assert provenance._histories_for(overlay) is not provenance._histories_for(overlay)
