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
    paths = [pattern.pattern for _, pattern, _ in app.routes]
    assert all(verb == "GET" for verb, _, _ in app.routes)
    for expected in ("/api/meta", "/api/characters", "/api/lookup", "/api/patches"):
        assert any(pattern.match(expected) for _, pattern, _ in app.routes), expected
    assert len(paths) == len(set(paths))
    assert app.dispatch("GET", "/api/health", {}).status == 200
    assert app.dispatch("POST", "/api/meta", {}).status == 405
    assert app.dispatch("GET", "/api/unknown", {}) is None
    assert app.dispatch("GET", "/api/characters/999/pixels/../x.png", {}) is None
    missing = app.dispatch("GET", "/api/characters/123", {})
    assert missing.status == 404 and "error" in json.loads(missing.body)


@pytest.fixture(scope="module")
def real_app():
    try:
        from wf.studio.source import build_source
        source = build_source()
    except (FileNotFoundError, OSError, KeyError) as exc:
        pytest.skip(f"real layered view unavailable: {exc}")
    return StudioApp(source)


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
