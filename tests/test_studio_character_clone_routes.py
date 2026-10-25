"""Existing character read routes can inspect a new formal draft candidate."""
import json

from test_studio_character_clone import env, request, NEW, CODE  # noqa: F401
from wf.studio.character_clone import clone
from wf.studio.server import StudioApp


def test_existing_character_routes_read_clone_without_mutating_shared_view(env):
    source, store, ops, server = env
    clone(ops, request(), server_dir=server)
    application = StudioApp(source, drafts=store, server_dir=server, screenshot_dirs=[])
    response = application.dispatch("GET", "/api/characters/" + NEW, {})
    assert response.status == 200
    assert json.loads(response.body)["code"] == CODE
    pixels = application.dispatch("GET", f"/api/characters/{NEW}/pixels", {})
    assert pixels.status == 200 and json.loads(pixels.body)["characterId"] == NEW
    sheet = application.dispatch("GET", f"/api/characters/{NEW}/pixels/pixelart.png", {})
    assert sheet.status == 200 and sheet.body.startswith(b"\x89PNG")
    assets = application.dispatch("GET", f"/api/characters/{NEW}/assets", {})
    assert assets.status == 200 and len(json.loads(assets.body)["cloneAssets"]) == 37
    assert application.source is source and NEW not in source.table("character")
