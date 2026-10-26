"""Sparse atlas, untouched-slot and budget counterexamples for draft delivery."""
from __future__ import annotations

from PIL import Image
import pytest

from wf.studio.deliver_media import compile_media, encode_png, encode_tree, png, tree
from wf.studio.deliver_pixel import _append_pack, _verify_untouched
from wf.studio.drafts import DraftError, DraftStore, sha256
from wf.studio.pixels import build_family
from wf_pixelart_vfx import frame_index, restore_frame

from test_studio_deliver_media import CID, CODE, PREFIX, Source, changeset, standard_png

BASE = PREFIX + "pixelart/"


@pytest.fixture
def pixel(tmp_path):
    source, store = Source(), DraftStore(tmp_path / "drafts")
    sheet = Image.new("RGBA", (8, 4))
    sheet.paste(Image.new("RGBA", (2, 3), (10, 20, 30, 255)), (0, 0))
    sheet.paste(Image.new("RGBA", (3, 2), (50, 60, 70, 255)), (4, 0))
    atlas = [
        {"n": "demo/pixelart0004", "x": 0, "y": 0, "w": 2, "h": 3,
         "fx": -3, "fy": -4, "fw": 16, "fh": 16, "r": False, "custom": "preserved"},
        {"n": "demo/pixelart0008", "x": 4, "y": 0, "w": 3, "h": 2,
         "fx": -4, "fy": -5, "fw": 16, "fh": 16, "r": True},
    ]
    frame = {"name": "demo/pixelart", "x": -8, "y": -12, "scale": 0.5, "smoothing": False}
    timeline = {"sequences": [{"name": "neutral", "kind": "loop", "begin": 1, "end": 2},
                              {"name": "walk_front", "kind": "loop", "begin": 3, "end": 4},
                              {"name": "skill_ready", "kind": "once", "begin": 5, "end": 8}],
                "points": [{"path": "hp_gauge", "frames": []}], "sounds": []}
    source.files = {("common", BASE + "sprite_sheet.png"): encode_png(sheet),
                    ("common", BASE + "sprite_sheet.atlas.amf3.deflate"): encode_tree(atlas),
                    ("common", BASE + "pixelart.frame.amf3.deflate"): encode_tree(frame),
                    ("common", BASE + "pixelart.timeline.amf3.deflate"): encode_tree(timeline)}

    def change(action="neutral", duration=2, anchor=(8, 12)):
        image = Image.new("RGBA", (16, 16))
        image.paste(Image.new("RGBA", (2, 3), (200, 30, 50, 255)), (3, 4))
        raw = standard_png(image)
        relative = f"files/pixel/pixelart/{action}/frame_000.png"
        store.write_file(CID, relative, raw)
        old = next(s for s in timeline["sequences"] if s["name"] == action)
        return {"kind": "pixel_action", "target": {"family": "pixelart", "action": action}, "files": [],
                "params": {"frames": [{"file": relative, "sha256": sha256(raw), "duration": duration,
                                       "anchor": list(anchor), "width": 16, "height": 16}],
                           "totalFrames": duration, "originalTotalFrames": old["end"] - old["begin"] + 1}}
    return source, store, change, (sheet, atlas, frame, timeline)


def test_pixel_sparse_atlas_other_slots_and_frame_bytes_preserved(pixel):
    source, store, change, original = pixel
    result = compile_media(source, store, changeset([change()]))
    assert len(result.members) == 4
    frame_name = BASE + "pixelart.frame.amf3.deflate"
    assert result.members["common", frame_name] == source.files["common", frame_name]
    sheet = png(result.members["common", BASE + "sprite_sheet.png"])
    atlas = tree(result.members["common", BASE + "sprite_sheet.atlas.amf3.deflate"])
    keys, entries = frame_index(atlas, original[2]["name"])
    assert keys == [2, 4, 8]
    assert entries[4] == original[1][0] and entries[8] == original[1][1]
    assert sheet.crop((0, 0, 8, 4)).tobytes() == original[0].tobytes()
    new = restore_frame(sheet, entries[2])
    assert new.getpixel((3, 4)) == (200, 30, 50, 255)
    combined = Source({**source.files, **result.members})
    meta, preview = build_family(combined, CODE, "pixelart", "sprite_sheet")
    assert meta["scale"] == 0.5 and len(meta["actions"]) == 3
    assert [a["totalFrames"] for a in meta["actions"]] == [2, 2, 4]
    assert preview.startswith(b"\x89PNG")


def test_pixel_last_slot_duration_changes_without_moving_any_other_slot(pixel):
    source, store, change, original = pixel
    result = compile_media(source, store, changeset([change("skill_ready", duration=6)]))
    timeline = tree(result.members["common", BASE + "pixelart.timeline.amf3.deflate"])
    assert timeline["sequences"][2]["begin"] == 5 and timeline["sequences"][2]["end"] == 10
    assert timeline["sequences"][:2] == original[3]["sequences"][:2]
    atlas = tree(result.members["common", BASE + "sprite_sheet.atlas.amf3.deflate"])
    assert atlas[0] == original[1][0]


def test_pixel_multiple_slots_and_anchor_alignment(pixel):
    source, store, change, original = pixel
    result = compile_media(source, store, changeset([change(), change("skill_ready", 4, (7, 10))]))
    atlas = tree(result.members["common", BASE + "sprite_sheet.atlas.amf3.deflate"])
    _, entries = frame_index(atlas, original[2]["name"])
    sheet = png(result.members["common", BASE + "sprite_sheet.png"])
    assert restore_frame(sheet, entries[8]).getpixel((4, 6)) == (200, 30, 50, 255)
    assert entries[4] == original[1][0]


@pytest.mark.parametrize("mutation, expected", [
    ("hash", "SHA-256"), ("old_duration", "旧时长"), ("total", "总时长"),
    ("anchor", "锚点"), ("size", "尺寸"), ("missing_slot", "已有动作槽"),
    ("opaque", "透明背景"), ("duration_change", "保持原总时长"),
])
def test_pixel_counterexamples(pixel, mutation, expected):
    source, store, make, original = pixel
    change = make()
    frame = change["params"]["frames"][0]
    if mutation == "hash":
        frame["sha256"] = "0" * 64
    elif mutation == "old_duration":
        change["params"]["originalTotalFrames"] = 5
    elif mutation == "total":
        change["params"]["totalFrames"] = 5
    elif mutation == "anchor":
        frame["anchor"] = [-30, -30]
    elif mutation == "size":
        frame["width"] = 7
    elif mutation == "missing_slot":
        change["target"]["action"] = "absent"
    elif mutation == "opaque":
        data = standard_png(Image.new("RGBA", (16, 16), (1, 2, 3, 255)))
        frame["sha256"] = sha256(data)
        store.write_file(CID, frame["file"], data)
    elif mutation == "duration_change":
        change = make(duration=6)
    with pytest.raises(DraftError, match=expected):
        compile_media(source, store, changeset([change]))


def test_pixel_budget_rejects_oversized_actual_sheet():
    with pytest.raises(DraftError, match="4096"):
        _append_pack(Image.new("RGBA", (4094, 4094)), [Image.new("RGBA", (2, 2))], 4094)


def test_pixel_untouched_guard_rejects_a_single_changed_pixel(pixel):
    _, _, _, (sheet, atlas, frame, timeline) = pixel
    changed = sheet.copy()
    changed.putpixel((4, 0), (255, 255, 255, 255))
    with pytest.raises(DraftError, match="逐字节"):
        _verify_untouched(sheet, atlas, frame, timeline, changed, atlas, timeline, {"neutral"})


def test_pixel_replaces_range_that_splits_preceding_sparse_endpoint(pixel):
    source, store, change, original = pixel
    result = compile_media(source, store, changeset([change("walk_front")]))
    atlas = tree(result.members["common", BASE + "sprite_sheet.atlas.amf3.deflate"])
    keys, entries = frame_index(atlas, original[2]["name"])
    assert keys == [2, 4, 8]
    expected = {**original[1][0], "n": "demo/pixelart0002"}
    assert entries[2] == expected


def test_pixel_duplicate_action_is_rejected(pixel):
    source, store, change, _ = pixel
    duplicate = change()
    with pytest.raises(DraftError, match="出现多次"):
        compile_media(source, store, changeset([duplicate, duplicate]))
