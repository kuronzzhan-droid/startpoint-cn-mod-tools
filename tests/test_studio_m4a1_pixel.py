"""M4a.1: actual layer0 costs, reusable regions and chronological tail guards."""
from __future__ import annotations

import copy

from PIL import Image
import pytest

from wf.studio.deliver_media import compile_media, encode_png, encode_tree, png, tree
from wf.studio.deliver_pixel_pack import budget_check, repack
from wf.studio.drafts import DraftError, DraftStore, sha256
from wf_pixelart_vfx import frame_index, restore_frame

from test_studio_deliver_media import CID, Source, changeset, standard_png
from test_studio_deliver_media_pixel import BASE, pixel


@pytest.mark.parametrize("size,state,pixels", [
    ((247, 738), "满足", 184260), ((248, 738), "待验证", 185000),
    ((998, 998), "待验证", 1000000), ((999, 998), "问题", 1001000),
])
def test_layer0_budget_counts_margin_at_both_thresholds(size, state, pixels):
    check = budget_check("pixelart", Image.new("RGBA", size))
    assert check["layer0Pixels"] == pixels
    assert check["state"] == state
    assert check["blocking"] is (state == "问题")
    assert "(w+2)(h+2)" in check["message"]


def test_special_is_not_charged_to_battle_layer0():
    check = budget_check("special", Image.new("RGBA", (1200, 1200)))
    assert check["state"] == "满足"
    assert check["layer0Pixels"] == 0 and check["loadedInBattle"] is False


def test_repacking_clears_exclusive_pixels_and_reuses_the_hole():
    original = Image.new("RGBA", (80, 40))
    original.paste((20, 30, 40, 255), (0, 0, 32, 16))
    original.paste((50, 60, 70, 255), (64, 24, 72, 32))
    removed = {"x": 0, "y": 0, "w": 32, "h": 16}
    kept = {"x": 64, "y": 24, "w": 8, "h": 8}
    image = Image.new("RGBA", (8, 8), (200, 100, 30, 255))
    packed, positions = repack(original, [removed, kept], [kept], [image], 4094)
    assert positions == [(0, 0)]
    assert packed.width <= original.width and packed.height <= original.height
    assert packed.getpixel((20, 10)) == (0, 0, 0, 0)
    assert packed.crop((64, 24, 72, 32)).tobytes() == original.crop((64, 24, 72, 32)).tobytes()


def test_reclamation_protects_overlapping_retained_and_foreign_regions():
    original = Image.new("RGBA", (32, 16), (30, 40, 50, 255))
    removed = {"x": 0, "y": 0, "w": 24, "h": 16}
    retained = {"n": "foreign0001", "x": 16, "y": 0, "w": 16, "h": 16}
    packed, _ = repack(original, [removed, retained], [retained],
                       [Image.new("RGBA", (8, 8), (200, 10, 20, 255))], 4094)
    assert packed.crop((16, 0, 32, 16)).tobytes() == original.crop((16, 0, 32, 16)).tobytes()
    assert packed.getpixel((10, 10)) == (0, 0, 0, 0)


def test_replacing_an_inflated_tail_shrinks_the_actual_sheet():
    original = Image.new("RGBA", (1000, 1000))
    old = {"x": 0, "y": 0, "w": 1000, "h": 1000}
    original.paste((20, 30, 40, 255), (0, 0, 1000, 1000))
    packed, _ = repack(original, [old], [], [Image.new("RGBA", (16, 16))], 4094)
    assert packed.width <= 17 and packed.height <= 17
    assert budget_check("pixelart", packed)["state"] == "满足"


def _long_action(tmp_path, visible):
    source, store = Source(), DraftStore(tmp_path / "drafts")
    frame = {"name": "demo/pixelart", "x": 0, "y": 0, "scale": 1}
    atlas = [{"n": "demo/pixelart0161", "x": 0, "y": 0, "w": 1, "h": 1,
              "fw": 128, "fh": 128, "fx": 0, "fy": 0, "r": False}]
    timeline = {"sequences": [{"name": "ghost_neutral", "begin": 1, "end": 161}]}
    source.files = {("common", BASE + "sprite_sheet.png"): encode_png(Image.new("RGBA", (1, 1))),
                    ("common", BASE + "sprite_sheet.atlas.amf3.deflate"): encode_tree(atlas),
                    ("common", BASE + "pixelart.frame.amf3.deflate"): encode_tree(frame),
                    ("common", BASE + "pixelart.timeline.amf3.deflate"): encode_tree(timeline)}
    frames = []
    for index in range(161):
        image = Image.new("RGBA", (128, 128))
        image.paste((index, 30, 50, 255), (0, 0, visible, visible))
        raw = standard_png(image)
        relative = f"files/pixel/pixelart/ghost_neutral/frame_{index:03d}.png"
        store.write_file(CID, relative, raw)
        frames.append({"file": relative, "sha256": sha256(raw), "duration": 1,
                       "anchor": [0, 0], "width": 128, "height": 128})
    change = {"kind": "pixel_action", "target": {"family": "pixelart", "action": "ghost_neutral"},
              "files": [], "params": {"frames": frames, "totalFrames": 161, "originalTotalFrames": 161}}
    return source, store, change, frame


@pytest.mark.parametrize("visible,state", [(64, "待验证"), (100, "问题")])
def test_161_distinct_frames_are_flagged_by_actual_sheet_cost(tmp_path, visible, state):
    source, store, change, frame = _long_action(tmp_path, visible)
    result = compile_media(source, store, changeset([change]))
    check = next(c for c in result.checks if c["code"] == "studio.pixel.budget")
    sheet = png(result.members["common", BASE + "sprite_sheet.png"])
    atlas = tree(result.members["common", BASE + "sprite_sheet.atlas.amf3.deflate"])
    keys, entries = frame_index(atlas, frame["name"])
    assert keys == list(range(1, 162))
    assert check["layer0Pixels"] == (sheet.width + 2) * (sheet.height + 2)
    assert check["state"] == state and check["blocking"] is (state == "问题")
    for index, key in enumerate(keys):
        assert restore_frame(sheet, entries[key]).getpixel((0, 0)) == (index, 30, 50, 255)
    if state == "问题":
        from wf.studio.deliver_bridge import compile_draft
        with pytest.raises(DraftError, match="草稿规则检查存在问题"):
            compile_draft(source, store, changeset([change]))


def test_replacing_a_slot_repeatedly_does_not_append_dead_rectangles(pixel):
    source, store, change, _ = pixel
    first = compile_media(source, store, changeset([change("skill_ready", 4)]))
    logical = ("common", BASE + "sprite_sheet.png")
    first_size = png(first.members[logical]).size
    source.files.update(first.members)
    second = compile_media(source, store, changeset([change("skill_ready", 4)]))
    assert png(second.members.get(logical, source.files[logical])).size == first_size


def _write_timeline(source, timeline):
    source.files["common", BASE + "pixelart.timeline.amf3.deflate"] = encode_tree(timeline)


def test_last_slot_is_chronological_even_when_sequence_list_is_unsorted(pixel):
    source, store, change, original = pixel
    timeline = copy.deepcopy(original[3])
    timeline["sequences"].reverse()
    _write_timeline(source, timeline)
    result = compile_media(source, store, changeset([change("skill_ready", 6)]))
    after = tree(result.members["common", BASE + "pixelart.timeline.amf3.deflate"])
    assert after["sequences"][0]["end"] == 10
    assert after["sequences"][1:] == timeline["sequences"][1:]


def test_list_last_slot_cannot_change_duration_if_earlier_in_time(pixel):
    source, store, change, original = pixel
    timeline = copy.deepcopy(original[3])
    timeline["sequences"].reverse()
    _write_timeline(source, timeline)
    with pytest.raises(DraftError, match="非末尾动作"):
        compile_media(source, store, changeset([change("neutral", 1)]))


@pytest.mark.parametrize("duration", [6, 7])
def test_tail_extension_cannot_cross_an_outside_endpoint(pixel, duration):
    source, store, change, original = pixel
    atlas = original[1] + [{**original[1][-1], "n": "demo/pixelart0010"}]
    source.files["common", BASE + "sprite_sheet.atlas.amf3.deflate"] = encode_tree(atlas)
    with pytest.raises(DraftError, match="序列外.*10"):
        compile_media(source, store, changeset([change("skill_ready", duration)]))


def test_tail_extension_before_an_outside_endpoint_preserves_that_entry(pixel):
    source, store, change, original = pixel
    external = {**original[1][-1], "n": "demo/pixelart0010"}
    source.files["common", BASE + "sprite_sheet.atlas.amf3.deflate"] = encode_tree(original[1] + [external])
    result = compile_media(source, store, changeset([change("skill_ready", 5)]))
    atlas = tree(result.members["common", BASE + "sprite_sheet.atlas.amf3.deflate"])
    assert next(entry for entry in atlas if entry["n"] == external["n"]) == external
