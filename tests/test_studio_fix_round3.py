"""2026-10-18 优化清单 A5–A10：队长名断言列、绑定比树不比字节、绑定原子性、胜利举手帧、越界区间。"""
from __future__ import annotations

import zlib

import pytest

from wf.studio import scratch
from wf.studio.deliver_media import compile_media, encode_tree, png, tree
from wf.studio.drafts import DraftError
from wf.studio.pixel_generate import KACHIDOKI_READ, generate
from wf.studio.pixel_workshop import analyze, family_paths
from wf.studio.pixel_workshop_ops import PixelWorkshop
from wf.studio.pixels import build_family
from wf_pixelart_vfx import frame_index, restore_frame

from test_studio_deliver_media import CID, CODE
from test_studio_scratch import SID, env, new_scratch  # noqa: F401 - pytest fixture

PATHS = family_paths(CODE, "pixelart")


# -- A5 -----------------------------------------------------------------------------

def test_read_exposes_the_leader_name_wf_text_asserts(tmp_path):
    from test_studio_ability_text import setup
    ed, _ = setup(tmp_path)
    slots = ed.read("139985")["slots"]
    assert slots["leaderNameText"] == "队长"   # character_text c10
    assert "leaderName" in slots             # character c18 (synced copy)


# -- A8 -----------------------------------------------------------------------------

def _reencode_atlas(source, code, level=1):
    """Same AMF3 tree, different deflate bytes (like an official file vs. our encoder)."""
    logical = family_paths(code, "pixelart")[1]
    plain = zlib.decompress(source.files["common", logical], -15)
    compressor = zlib.compressobj(level=level, wbits=-15)
    raw = compressor.compress(plain) + compressor.flush()
    assert raw != source.files["common", logical] and tree(raw) == tree(source.files["common", logical])
    source.files["common", logical] = raw


def test_remap_from_the_bind_target_binds_back(env):
    source, store, ops = env
    _reencode_atlas(source, CODE)
    new_scratch(ops, base=CODE)
    shop = PixelWorkshop(scratch.ScratchDraftOps(ops, SID))
    shop.remap(SID, {"base": CODE, "mapping": [{"from": "#a13b3b", "to": "#2a5cc8"}]})
    scratch.bind(ops, SID, {"characterId": CID})            # was: 「母本变了？」
    compiled = compile_media(source, store, store.load(CID))  # compile compares trees too
    sheet = png(compiled.members["common", PATHS[0]])
    atlas = tree(compiled.members["common", PATHS[1]])
    frame = tree(compiled.members["common", PATHS[2]])
    _, entries = frame_index(atlas, frame["name"])
    assert restore_frame(sheet, entries[2]).getpixel((128 - 3 + 2, 120 + 2)) == (42, 92, 200, 255)


# -- A9 -----------------------------------------------------------------------------

def test_bind_failure_rolls_everything_back_and_retry_succeeds(env, monkeypatch):
    source, store, ops = env
    new_scratch(ops)
    shop = PixelWorkshop(scratch.ScratchDraftOps(ops, SID))
    shop.remap(SID, {"base": "111007", "mapping": [{"from": "#a13b3b", "to": "#2a5cc8"}]})
    shop.generate(SID, {"action": "walk_back", "save": True})
    # The target already has its own walk_back: a failed bind must leave it intact.
    PixelWorkshop(ops).generate(CID, {"action": "walk_back", "save": True})
    before = store.load(CID)
    own_frames = {f["file"]: store.read_file(CID, f["file"]) for f in before["changes"][0]["params"]["frames"]}

    def broken(*args, **kwargs):
        raise OSError("disk full")
    monkeypatch.setattr(store, "update_scratch", broken)
    with pytest.raises(OSError):
        scratch.bind(ops, SID, {"characterId": CID})
    assert store.load(CID) == before
    assert {f: store.read_file(CID, f) for f in own_frames} == own_frames
    assert not list((store.directory(CID) / "files").rglob("*.atlas.amf3.deflate"))
    assert store.load(SID)["scratch"]["boundTo"] is None
    monkeypatch.undo()
    result = scratch.bind(ops, SID, {"characterId": CID})
    target = store.load(CID)
    assert [c["kind"] for c in target["changes"]] == ["pixel_family", "pixel_action"]
    assert result["created"] == [c["id"] for c in target["changes"]]
    assert all(SID in f["file"] for f in target["changes"][1]["params"]["frames"])
    for name in own_frames:  # the replaced own walk_back is pruned only after success
        assert store.read_file(CID, name) is None
    compile_media(source, store, target)


# -- A10 ----------------------------------------------------------------------------

@pytest.mark.parametrize("total", [20, 30, 100])
def test_generated_victory_keeps_the_raised_hand_on_the_apex(total):
    from PIL import Image
    sprite = Image.new("RGBA", (10, 20), (200, 40, 40, 255))
    frames = generate("kachidoki", {"front": sprite}, total)
    assert sum(f["duration"] for f in frames) == total
    position, held = 0, None
    for frame in frames:
        position += frame["duration"]
        if position >= KACHIDOKI_READ:
            held = frame
            break
    assert "最高点" in held["note"]


def test_victory_shorter_than_the_read_frame_is_refused():
    from PIL import Image
    with pytest.raises(DraftError, match="至少 20 帧"):
        generate("kachidoki", {"front": Image.new("RGBA", (4, 4), (1, 2, 3, 255))}, 19)


def test_range_past_the_last_endpoint_is_reported_everywhere(env):
    source, store, ops = env
    timeline = tree(source.files["common", PATHS[3]])
    timeline["sequences"][-1]["end"] = 45            # skill_ready 27..45, last endpoint is 40
    source.files["common", PATHS[3]] = encode_tree(timeline)
    family = next(f for f in analyze(source, CODE)["families"] if f["family"] == "pixelart")
    action = next(a for a in family["actions"] if a["name"] == "skill_ready")
    assert action["overflow"] == 5
    assert any(c["code"] == "workshop.range_overflow" and "多 5 帧" in c["message"] for c in family["checks"])
    meta, _ = build_family(source, CODE, "pixelart", "sprite_sheet")
    played = next(a for a in meta["actions"] if a["name"] == "skill_ready")  # was dropped entirely
    assert played["overflow"] == 5 and played["totalFrames"] == 19
