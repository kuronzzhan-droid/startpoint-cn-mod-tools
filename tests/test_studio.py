"""编辑台 backend: route table always; real-view checks only when data is configured."""
from __future__ import annotations

import json

import pytest

from wf.studio.server import StudioApp
from wf.studio.source import edge_versions


class _FakeView:
    tip = 1
    zips = ()
    index = {}
    active = "."


class _FakeSource:
    view = _FakeView()
    version = "1.4.1"

    def describe(self):
        return {"version": self.version, "extraZips": []}

    def table(self, name, official=False):
        return {}


def test_edge_versions():
    assert edge_versions("pinball-1.4.205-1.4.206-1-rolf-local.zip") == (205, 206)
    assert edge_versions("readme.txt") is None


def test_route_table_dispatch():
    app = StudioApp(_FakeSource())
    routes = [(verb, pattern.pattern) for verb, pattern, _ in app.routes]
    writes = ("^/api/drafts/", "^/api/boss/drafts/", "^/api/boss/drafts$", "^/api/studio/weapons/",
              "^/api/studio/characters/")
    delivery_actions = {rf"^/api/{prefix}deliveries/(?P<name>[^/]+)/{action}$"
                        for prefix in ("", "boss/", "modes/")
                        for action in ("rehearse", "apply", "unapply", "overlay")}
    mode_actions = {rf"^/api/modes/drafts/(?P<cid>five|rogue)/{suffix}$"
                    for suffix in ("build", "build/cancel",
                                   "deliveries/(?P<name>[^/]+)/device-result",
                                   "deliveries/(?P<name>[^/]+)/device-result/import")}
    mode_actions.add("^/api/modes/(?P<mode>five|rogue)/(?P<action>preview|save)$")
    scene_slot = r"hell-pumpkin|scene-[3-9][0-9]{5}"
    scene_actions = {rf"^/api/scenes/drafts/(?P<cid>{scene_slot})/{suffix}$"
                     for suffix in ("build", "build/cancel",
                                    "deliveries/(?P<name>[^/]+)/device-result",
                                    "deliveries/(?P<name>[^/]+)/device-result/import")}
    scene_actions.update({rf"^/api/scenes/deliveries/(?P<name>[^/]+)/{action}$"
                          for action in ("rehearse", "overlay")})
    scene_actions.update({"^/api/scenes/(?P<mode>hell-pumpkin)/clone$",
                          rf"^/api/scenes/(?P<mode>{scene_slot})/(?P<action>preview|save)$"})
    assert {("POST", pattern) for pattern in delivery_actions} <= set(routes)
    assert {("POST", pattern) for pattern in mode_actions} <= set(routes)
    assert {("POST", pattern) for pattern in scene_actions} <= set(routes)
    assert not any(pattern.startswith("^/api/scenes/") and
                   pattern.endswith(("/apply$", "/unapply$")) for _, pattern in routes)
    assert all(verb == "GET" or (verb == "POST" and (
        pattern.startswith(writes) or pattern in delivery_actions or pattern in mode_actions
        or pattern in scene_actions
        or pattern == "^/api/studio/views/export-store$")) for verb, pattern in routes)
    for expected in ("/api/studio/doctor", "/api/studio/freshness", "/api/meta", "/api/characters", "/api/lookup", "/api/patches", "/api/boss/drafts",
                     "/api/studio/weapons", "/api/studio/weapons/clone", "/api/studio/weapons/drafts",
                     "/api/studio/characters/clone", "/api/studio/characters/scratch-example/promote",
                     "/api/studio/views", "/api/studio/views/export-store"):
        assert any(pattern.match(expected) for _, pattern, _ in app.routes), expected
    assert len(routes) == len(set(routes))  # one handler per method/path
    assert app.dispatch("GET", "/api/health", {}).status == 200
    assert app.dispatch("POST", "/api/meta", {}).status == 405
    assert app.dispatch("GET", "/api/unknown", {}) is None
    assert app.dispatch("GET", "/api/characters/999/pixels/../x.png", {}) is None
    missing = app.dispatch("GET", "/api/characters/123", {})
    assert missing.status == 404 and "error" in json.loads(missing.body)


@pytest.fixture()
def real_app(tmp_path):
    try:
        from wf.studio.source import build_source
        source = build_source()
    except (FileNotFoundError, OSError, KeyError) as exc:
        pytest.skip(f"real layered view unavailable: {exc}")
    if source.table("character").get("111183") is None:
        pytest.skip("111183 not in the configured real layered view")
    from wf.studio.drafts import DraftStore
    return StudioApp(source, drafts=DraftStore(tmp_path / "drafts"))


def test_real_app_missing_view_skips(tmp_path, monkeypatch):
    def missing():
        raise FileNotFoundError("missing fixture archive")
    monkeypatch.setattr("wf.studio.source.build_source", missing)
    with pytest.raises(pytest.skip.Exception, match="missing fixture archive"):
        real_app.__wrapped__(tmp_path)


def test_real_app_programming_error_is_not_skipped(tmp_path, monkeypatch):
    def broken():
        raise ImportError("broken source import")
    monkeypatch.setattr("wf.studio.source.build_source", broken)
    with pytest.raises(ImportError, match="broken source import"):
        real_app.__wrapped__(tmp_path)


def test_real_character_list_nonempty(real_app):
    body = json.loads(real_app.dispatch("GET", "/api/characters", {}).body)
    assert body["count"] > 100
    assert all({"id", "name", "element", "origin"} <= set(c) for c in body["characters"])


def test_real_character_detail_and_pixels(real_app):
    detail = json.loads(real_app.dispatch("GET", "/api/characters/111183", {}).body)
    assert [b["label"] for b in detail["boards"]][:2] == ["一板", "二板"]
    assert any(row["description"] for slot in detail["abilities"] for row in slot["rows"])
    meta = json.loads(real_app.dispatch("GET", "/api/characters/111183/pixels", {}).body)
    base = next(f for f in meta["families"] if f["family"] == "pixelart")
    assert {"neutral", "walk_front", "skill_ready"} <= {a["name"] for a in base["actions"]}
    for action in base["actions"]:
        assert sum(c["frames"] for c in action["cells"]) == action["totalFrames"]
        assert all(0 <= c["cell"] < base["cellCount"] for c in action["cells"])
    png = real_app.dispatch("GET", "/api/characters/111183/pixels/pixelart.png", {})
    assert png.status == 200 and png.body[:8] == b"\x89PNG\r\n\x1a\n"


def test_chain_resolution_picks_matching_hash(tmp_path):
    import hashlib
    from wf.studio.chain import resolve_chain
    name = "pinball-1.4.10-1.4.11-1-demo-local.zip"
    good, bad = tmp_path / "good", tmp_path / "bad"
    good.mkdir(); bad.mkdir()
    (bad / name).write_bytes(b"other-bytes")
    (good / name).write_bytes(b"right-bytes")
    manifest = tmp_path / "repo" / "manifest.json"
    manifest.parent.mkdir()
    entries = [
        {"version": "1.4.10", "enabled": True, "archive": "old.zip"},
        {"version": "1.4.11", "enabled": True, "archive": name, "archive_integrity": [
            {"name": name, "size": 11, "sha256": hashlib.sha256(b"right-bytes").hexdigest()}]},
        {"version": "1.4.12", "enabled": True, "archive": "pinball-1.4.11-1.4.12-1-x.zip"},
        {"version": "1.4.13", "enabled": False, "archive": "pinball-1.4.12-1.4.13-1-y.zip"},
    ]
    manifest.write_text(json.dumps({"patches": entries}), "utf-8")
    result = resolve_chain(manifest, [bad, good], after_tip=10)
    assert result.zips == [good / name]
    assert [m["name"] for m in result.missing] == ["pinball-1.4.11-1.4.12-1-x.zip"]


def test_real_assets_inventory(real_app):
    body = json.loads(real_app.dispatch("GET", "/api/characters/111183/assets", {}).body)
    groups = {g["id"]: g for g in body["groups"]}
    assert groups["portrait"]["present"] == 2
    assert groups["pixel"]["present"] >= 4
    assert any(line.get("present") for line in body["speech"])
    avatar = real_app.dispatch("GET", "/api/characters/111183/avatar/0.png", {})
    assert avatar.status == 200 and avatar.body[:8] == b"\x89PNG\r\n\x1a\n"
    assert real_app.dispatch("GET", "/api/asset", {"path": ["master/x"]}).status == 400
