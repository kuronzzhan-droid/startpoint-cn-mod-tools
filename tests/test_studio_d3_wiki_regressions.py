"""Root-aware Wiki portraits and scratch routes, using only synthetic assets."""
import json
from urllib.parse import parse_qs, urlsplit

import pytest
from PIL import Image

import wf_assets
from test_studio_d3_wiki import env, snapshot
from test_studio_character_clone import OLD, env as clone_env
from test_studio_drafts import _portrait_change
from wf.studio.ability import AbilityEditor
from wf.studio.deliver_media import encode_png, encode_tree
from wf.studio.scratch import create
from wf.studio.server import StudioApp
from wf.studio.wiki_preview import CardSource, image, preview
from wf.view.base149 import HistoricalView


@pytest.mark.parametrize("root", ["medium", "android", "common"])
@pytest.mark.parametrize("ability_draft", [False, True])
def test_existing_portraits_use_real_common_only_view_contract(env, monkeypatch, root, ability_draft):
    source, store, ops, _ = env
    # The original fixture searched every root, unlike HistoricalView.read_raw.
    monkeypatch.setattr(type(source.view), "read_raw", HistoricalView.read_raw)
    for form in ("0", "1"):
        logical = f"character/mother/ui/full_shot_1440_1920_{form}.png"
        source.view.files[root, logical] = source.view.files.pop(("medium", logical))
    if ability_draft:
        AbilityEditor(source, store=store).apply(OLD, {"operations": [{
            "op": "set_cells", "table": "ability", "key": "100", "row": 0, "row_count": 1,
            "column_space": "native", "cells": [{"column": 51, "old": "10000", "new": "20000"}]}]})
    before, original = snapshot(store.root), dict(source.view.files)
    app = StudioApp(source, drafts=store, screenshot_dirs=[])
    response = app.dispatch("GET", f"/api/drafts/{OLD}/wiki-card", {})
    assert response.status == 200, response.body
    card = json.loads(response.body)["card"]
    assert len(card["portraits"]) == 2
    for portrait in card["portraits"]:
        url = urlsplit(portrait["url"])
        response = app.dispatch("GET", url.path, parse_qs(url.query))
        assert response.status == 200, response.body
        assert response.body.startswith(b"\x89PNG")
    assert snapshot(store.root) == before and source.view.files == original


def test_wiki_portrait_root_priority(env, monkeypatch):
    source, _, ops, _ = env
    monkeypatch.setattr(type(source.view), "read_raw", HistoricalView.read_raw)
    logical = "character/mother/ui/full_shot_1440_1920_0.png"
    for root, color in (("medium", "red"), ("android", "blue"), ("common", "green")):
        source.view.files[root, logical] = encode_png(Image.new("RGBA", (4, 4), color))
    for root in ("medium", "android", "common"):
        assert image(ops, OLD, logical) == wf_assets.png_decode(source.view.files[root, logical])
        del source.view.files[root, logical]


def test_scratch_portrait_image_route_and_empty_slot_attribution(env):
    source, store, ops, _ = env
    cid = create(ops, {"name": "像素草稿", "element": "水", "base": OLD, "slug": "d3-image"})["characterId"]
    draft = store.load(cid)
    logical = f"character/{draft['code']}/ui/full_shot_1440_1920_0.png"
    relative = f"files/medium/{logical}"
    encoded = encode_png(Image.new("RGBA", (4, 4), "blue"))
    plain = wf_assets.png_decode(encoded)
    change = _portrait_change(relative, plain)
    change["files"][0].update(logical=logical)
    store.write_file(cid, relative, plain)
    store.put_change(cid, draft["code"], source.version, change)
    before = snapshot(store.root)
    card = preview(ops, cid)["card"]
    assert len(card["portraits"]) == 1
    assert all("translation" not in g for g in [card["leader"], *card["abilities"]])
    app = StudioApp(source, drafts=store, screenshot_dirs=[])
    response = app.dispatch("GET", f"/api/drafts/{cid}/wiki-image", {"path": [logical]})
    assert response.status == 200 and response.body == plain
    response = app.dispatch("GET", f"/api/drafts/{cid}/wiki-image", {
        "path": ["character/mother/ui/full_shot_1440_1920_0.png"]})
    assert response.status == 400
    assert snapshot(store.root) == before


@pytest.mark.parametrize("cid", ["scratch--", "scratch-", "scratch-" + "a" * 49])
def test_wiki_routes_share_scratch_id_validation(env, cid):
    source, store, _, _ = env
    app = StudioApp(source, drafts=store, screenshot_dirs=[])
    for route in ("wiki-card", "wiki-image"):
        # None means no route matched; the HTTP handler supplies the 404.
        assert app.dispatch("GET", f"/api/drafts/{cid}/{route}", {}) is None


@pytest.mark.parametrize("official_first", [False, True])
def test_card_official_programs_never_reuse_current_tree_cache(env, official_first):
    source, _, _, _ = env
    logical = "battle/action/skill/mother.action.dsl.amf3.deflate"
    current, official = ["ActionDsl", ["Wait", 20]], ["ActionDsl", ["Wait", 10]]
    source.view.files["common", logical] = encode_tree(current)
    source._raw[logical, True] = (encode_tree(official), "official")
    card_source = CardSource(source)
    for flag in (official_first, not official_first, official_first):
        assert card_source.tree(logical, flag) == (official if flag else current)
        assert card_source.raw(logical, flag) == encode_tree(official if flag else current)
