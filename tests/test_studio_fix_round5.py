"""2026-10-18 优化清单 C 组后端部分：调色板半透明标记、草稿角色改名/删除/名字校验、无草稿像素不再 404。"""
from __future__ import annotations

import json

import pytest

from wf.studio import scratch
from wf.studio.deliver_media import encode_png, png
from wf.studio.drafts import DraftError
from wf.studio.pixel_routes import PixelRoutes
from wf.studio.pixel_workshop import analyze, family_paths

from test_studio_deliver_media import CID, CODE
from test_studio_scratch import SID, env, new_scratch  # noqa: F401 - pytest fixture


def test_palette_marks_colours_seen_only_on_semi_transparent_pixels(env):
    source, _, _ = env
    paths = family_paths(CODE, "pixelart")
    sheet = png(source.files["common", paths[0]])
    sheet.putpixel((2, 3), (11, 22, 33, 120))      # only semi-transparent
    source.files["common", paths[0]] = encode_png(sheet)
    palette = {p["hex"]: p for p in analyze(source, CODE)["palette"]}
    assert palette["#0b1621"]["opaque"] == 0 and palette["#0b1621"]["count"] == 1
    assert palette["#a13b3b"]["opaque"] == palette["#a13b3b"]["count"] > 0


def test_scratch_names_rename_and_delete(env):
    _, store, ops = env
    for bad in ("1", "  ", "12", "!!"):
        with pytest.raises(DraftError, match="至少两个字"):
            scratch.create(ops, {"name": bad, "element": "水", "base": "mother", "slug": "x-" + str(len(bad))})
    new_scratch(ops)
    info = scratch.rename(ops, SID, {"name": "风杰拉德", "element": "风"})
    assert info["scratch"]["name"] == "风杰拉德" and info["scratch"]["element"] == "风"
    with pytest.raises(DraftError, match="没有要改"):
        scratch.rename(ops, SID, {"name": "风杰拉德"})
    with pytest.raises(DraftError):
        scratch.rename(ops, SID, {"element": "冰"})
    assert scratch.delete(ops, SID)["deleted"] == SID
    assert store.load(SID) is None and not store.directory(SID).exists()
    with pytest.raises(DraftError):
        scratch.delete(ops, SID)


def test_draft_without_pixel_changes_answers_empty_not_404(env):
    _, _, ops = env
    app = type("App", (), {"ops": ops})()
    routes = PixelRoutes(app)
    response = routes.draft_meta({}, CID)
    assert response.status == 200 and json.loads(response.body)["empty"] is True
    assert routes.draft_sheet({}, CID, "pixelart").status == 404  # the sheet itself still does not exist
