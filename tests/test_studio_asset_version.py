"""Asset inventories provide stable content and candidate cache identities."""
import copy
import json

from wf.studio.asset_version import stamp_assets
from wf.studio.assets import AssetIndex
from wf.studio.character_clone import clone, ops_for
from wf.studio.pixel_workshop_ops import PixelWorkshop
from wf.studio.server import StudioApp
from test_studio_character_clone import env, request, NEW  # noqa: F401


def test_asset_version_changes_for_content_view_and_recreated_draft():
    item = {"path": "character/demo/voice/home/home_0.mp3", "size": 3, "sha256": "a" * 64}
    inventory = {"groups": [{"items": [item]}]}
    draft = {"revision": 1, "createdAt": "first", "changes": [{"sha256": "c" * 64}]}
    first = stamp_assets(inventory, source_version="1.4.233", draft=draft)
    assert first == stamp_assets(copy.deepcopy(inventory), source_version="1.4.233", draft=copy.deepcopy(draft))
    assert first["etag"] == '"' + first["assetsVersion"] + '"'
    assert len(first["assetsVersion"]) == 64
    assert "assetsVersion" not in inventory
    assert stamp_assets(inventory, source_version="1.4.234", draft=draft)["etag"] != first["etag"]
    assert stamp_assets(inventory, source_version="1.4.233", draft={**draft, "createdAt": "second"})["etag"] != first["etag"]
    item["sha256"] = "b" * 64
    assert stamp_assets(inventory, source_version="1.4.233", draft=draft)["etag"] != first["etag"]


def test_asset_inventory_contains_raw_content_fingerprint(env):
    import hashlib
    source, _, _, _ = env
    logical = "character/mother/ui/square_0.png"
    index = AssetIndex(source)
    item = index.describe_item(logical, index.locate(logical))
    assert item["sha256"] == hashlib.sha256(source.view.files["medium", logical]).hexdigest()


def test_assets_endpoint_cache_version_tracks_clone_edit_and_revert(env):
    source, store, ops, server = env
    clone(ops, request())
    app = StudioApp(source, drafts=store, server_dir=server, screenshot_dirs=[])

    def inventory():
        response = app.dispatch("GET", f"/api/characters/{NEW}/assets", {})
        assert response.status == 200
        return json.loads(response.body)

    initial = inventory()
    assert initial["sourceVersion"] == source.version
    assert initial["draftRevision"] == store.load(NEW)["revision"]
    assert inventory()["assetsVersion"] == initial["assetsVersion"]
    changed_draft = PixelWorkshop(ops_for(ops, NEW)).remap(NEW, {
        "base": "111007", "families": ["pixelart"], "mapping": [{"from": "#a13b3b", "to": "#2266cc"}]})
    changed = inventory()
    assert changed["etag"] != initial["etag"]
    assert changed["draftRevision"] > initial["draftRevision"]
    change = changed_draft["changes"][0]["id"]
    ops.revert(NEW, change)
    assert inventory()["etag"] != changed["etag"]
