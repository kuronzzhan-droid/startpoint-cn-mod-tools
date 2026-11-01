"""Wiki projection reuses catalog entries without writing or publishing."""
import pytest

from test_studio_character_clone import env as clone_env, OLD, NEW, request
from wf.studio.character_clone import clone
from wf.studio.wiki_preview import preview
from wf.studio.server import StudioApp
from wf.studio.scratch import create


@pytest.fixture
def env(clone_env):
    source, store, *_ = clone_env
    source.official_root = store.root / "no-official-input"
    return clone_env


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_clone_wiki_card_and_image_are_read_only(env):
    source, store, ops, server = env
    clone(ops, request(name="草稿名字"), server_dir=server)
    before = snapshot(store.root)
    original = dict(source.view.files)
    card = preview(ops, NEW, server_dir=server)
    assert card["readOnly"] and card["card"]["name"] == "草稿名字"
    assert card["card"]["origin"] == "草稿预览"
    assert len(card["card"]["abilities"]) == 6
    app = StudioApp(source, drafts=store, server_dir=server, screenshot_dirs=[])
    response = app.dispatch("GET", f"/api/drafts/{NEW}/wiki-card", {})
    assert response.status == 200, response.body
    from urllib.parse import urlsplit, parse_qs
    url = card["card"]["portraits"][0]["url"]
    parsed = urlsplit(url)
    response = app.dispatch("GET", parsed.path, parse_qs(parsed.query))
    assert response.status == 200 and response.body.startswith(b"\x89PNG")
    assert snapshot(store.root) == before and source.view.files == original
    bad = app.dispatch("GET", f"/api/drafts/{NEW}/wiki-image", {"path": ["character/mother/ui/a.png"]})
    assert bad.status == 400


def test_scratch_card_does_not_claim_mother_combat_data(env):
    _, store, ops, _ = env
    result = create(ops, {"name": "像素草稿", "element": "水", "base": OLD, "slug": "d3-card"})
    cid = result["characterId"]
    before = snapshot(store.root)
    data = preview(ops, cid)
    assert data["card"]["name"] == "像素草稿" and data["card"]["element"] == "水"
    assert not data["card"]["skills"] and not data["card"]["stats"]["levels"]
    assert snapshot(store.root) == before


def test_card_uses_draft_ability_rows_not_original_catalog(env):
    from wf.studio.ability import AbilityEditor
    source, store, ops, _ = env
    original = dict(source.view.files)
    AbilityEditor(source, store=store).apply(OLD, {"operations": [{
        "op": "set_cells", "table": "ability", "key": "100", "row": 0, "row_count": 1,
        "column_space": "native", "cells": [{"column": 51, "old": "10000", "new": "20000"}]}]})
    before = snapshot(store.root)
    data = preview(ops, OLD)
    assert data["card"]["abilities"][0]["rows"][0]["values"][51] == "20000"
    assert data["draftRevision"] == store.load(OLD)["revision"]
    assert snapshot(store.root) == before and source.view.files == original
