"""2026-10-18 优化清单 A1–A4：草稿角色补整族、像素不经 canvas、档位锁、保存与编译同规则。"""
from __future__ import annotations

import base64
import io

from PIL import Image
import pytest

from wf.studio import scratch
from wf.studio.deliver_media import compile_media, encode_png, png, tree
from wf.studio.drafts import DraftError, schema_errors
from wf.studio.pixel_workshop import family_paths
from wf.studio.pixel_workshop_ops import PixelWorkshop
from wf_pixelart_vfx import frame_index, restore_frame

from test_studio_deliver_media import CID, CODE
from test_studio_pixel_workshop import BASE_CODE
from test_studio_scratch import SID, env, new_scratch  # noqa: F401 - pytest fixture

PATHS = family_paths(CODE, "pixelart")


def _restored(members, key):
    sheet, atlas, frame = png(members[0]), tree(members[1]), tree(members[2])
    keys, entries = frame_index(atlas, frame["name"])
    return restore_frame(sheet, entries[key])


def _compiled_family(source, compiled, code=CODE):
    paths = family_paths(code, "pixelart")
    return [compiled.members.get(("common", p)) or source.files["common", p] for p in paths]


# -- A1 ---------------------------------------------------------------------------

def test_bind_actions_only_scratch_adds_whole_base_family(env):
    source, store, ops = env
    # The target's own family differs from the base: without the automatic family
    # replacement its neutral would leak into the bound result.
    sheet = png(source.files["common", PATHS[0]])
    sheet.paste((9, 99, 199, 255), (1, 1, 5, 7))
    source.files["common", PATHS[0]] = encode_png(sheet)
    new_scratch(ops)
    PixelWorkshop(scratch.ScratchDraftOps(ops, SID)).generate(SID, {"action": "walk_back", "save": True})
    assert [c["kind"] for c in store.load(SID)["changes"]] == ["pixel_action"]

    dry = scratch.bind(ops, SID, {"characterId": CID, "dryRun": True})
    assert dry["changes"][0]["kind"] == "pixel_family" and dry["changes"][0]["auto"] is True
    assert dry["notes"] and "原色整族" in dry["notes"][0]
    assert store.load(CID) is None

    scratch.bind(ops, SID, {"characterId": CID})
    target = store.load(CID)
    assert [c["kind"] for c in target["changes"]] == ["pixel_family", "pixel_action"]
    family = target["changes"][0]["params"]
    assert family["mode"] == "remap" and family["mapping"] == [] and family["auto"] == "bind"
    assert family["base"]["code"] == BASE_CODE
    assert not schema_errors(target)

    compiled = compile_media(source, store, target)
    bound = _compiled_family(source, compiled)
    base = [source.files["common", p] for p in family_paths(BASE_CODE, "pixelart")]
    # Untouched action (neutral) = the base's pixels, not the target's own.
    assert _restored(bound, 2).tobytes() == _restored(base, 2).tobytes()
    assert _restored(bound, 2).tobytes() != _restored([source.files["common", p] for p in PATHS], 2).tobytes()


def test_bind_back_to_the_base_needs_no_extra_family(env):
    source, store, ops = env
    new_scratch(ops, base=CODE)  # base is the target itself
    PixelWorkshop(scratch.ScratchDraftOps(ops, SID)).generate(SID, {"action": "walk_back", "save": True})
    dry = scratch.bind(ops, SID, {"characterId": CID, "dryRun": True})
    assert [c["kind"] for c in dry["changes"]] == ["pixel_action"] and "不需要" in dry["notes"][0]


# -- A2 ---------------------------------------------------------------------------

def _with_soft_pixels(source):
    sheet = png(source.files["common", PATHS[0]])
    sheet.putpixel((2, 3), (250, 128, 3, 128))   # region x=0 (neutral / walk_back 14)
    sheet.putpixel((3, 5), (17, 220, 99, 1))
    sheet.putpixel((9, 4), (10, 200, 30, 90))    # region x=8 (walk_back 26)
    sheet.putpixel((10, 2), (77, 88, 99, 0))     # RGB under alpha 0 stays too
    source.files["common", PATHS[0]] = encode_png(sheet)


def _board_request(data, action):
    width, height = data["frameBox"]
    frames = []
    for f in data["frames"]:
        full = Image.new("RGBA", (width, height))
        if f["box"]:
            x0, y0, x1, y1 = f["box"]
            full.paste(Image.frombytes("RGBA", (x1 - x0, y1 - y0), base64.b64decode(f["rgba"])), (x0, y0))
        frames.append({"rgba": base64.b64encode(full.tobytes()).decode(), "width": width, "height": height,
                       "duration": f["duration"], "anchor": data["origin"]})
    return {"family": "pixelart", "action": action, "frames": frames}


def test_board_save_without_edits_is_byte_identical(env):
    source, store, ops = env
    _with_soft_pixels(source)
    shop = PixelWorkshop(ops)
    data = shop.action_frames(CID, "pixelart", "walk_back", draft=False)
    original = [source.files["common", p] for p in PATHS]
    assert [f["key"] for f in data["frames"]] == [14, 26] and data["origin"] == [128, 128]
    for f in data["frames"]:  # raw bytes exactly as the backend decodes the sheet
        x0, y0, x1, y1 = f["box"]
        assert base64.b64decode(f["rgba"]) == _restored(original, f["key"]).crop((x0, y0, x1, y1)).tobytes()

    request = _board_request(data, "walk_back")
    dry = ops.pixel_save(CID, {**request, "dryRun": True})
    assert not [c for c in dry["checks"] if c["level"] == "error"]
    change = ops.pixel_save(CID, request)["change"]
    for stored, sent in zip(change["params"]["frames"], request["frames"]):
        image = Image.open(io.BytesIO(store.read_file(CID, stored["file"])))
        assert image.convert("RGBA").tobytes() == base64.b64decode(sent["rgba"])
    compiled = compile_media(source, store, store.load(CID))
    after = _compiled_family(source, compiled)
    for key in (14, 26):
        assert _restored(after, key).tobytes() == _restored(original, key).tobytes()


def test_sheet_split_runs_on_the_backend(env):
    source, store, ops = env
    cell = Image.new("RGBA", (12, 12))
    cell.paste((10, 20, 30, 255), (3, 2, 9, 11))
    cell.putpixel((4, 4), (200, 100, 50, 60))
    sheet = Image.new("RGBA", (24, 12))
    sheet.paste(cell, (0, 0))
    sheet.paste(cell, (12, 0))
    out = io.BytesIO()
    sheet.save(out, "PNG")
    request = {"family": "pixelart", "action": "skill_ready",
               "sheet": {"png": base64.b64encode(out.getvalue()).decode(), "columns": 2, "rows": 1},
               "frames": [{"duration": 2, "anchor": [6, 11]}, {"duration": 2, "anchor": [6, 11]}]}
    assert not schema_errors(request, "pixelRequest")
    change = ops.pixel_save(CID, request)["change"]
    stored = Image.open(io.BytesIO(store.read_file(CID, change["params"]["frames"][1]["file"]))).convert("RGBA")
    assert stored.tobytes() == cell.tobytes()
    with pytest.raises(DraftError, match="切出 2 帧"):
        ops.pixel_save(CID, {**request, "frames": request["frames"][:1]})


# -- A4 ---------------------------------------------------------------------------

def _png_frame():
    frame = Image.new("RGBA", (12, 14))
    frame.paste((200, 90, 40, 255), (2, 2, 10, 14))
    out = io.BytesIO()
    frame.save(out, "PNG")
    return base64.b64encode(out.getvalue()).decode()


@pytest.mark.parametrize("action,durations,message", [
    ("attack_fire", [2], "不能新增动作槽"),
    ("neutral", [1, 2], "非末尾动作 neutral"),          # neutral is 2 frames, not the last action
])
def test_save_and_dry_run_block_what_compile_rejects(env, action, durations, message):
    source, store, ops = env
    request = {"family": "pixelart", "action": action,
               "frames": [{"png": _png_frame(), "duration": d, "anchor": [6, 14]} for d in durations]}
    dry = ops.pixel_save(CID, {**request, "dryRun": True})
    errors = [c for c in dry["checks"] if c["level"] == "error"]
    assert errors and message in errors[0]["message"]
    with pytest.raises(DraftError, match=message):
        ops.pixel_save(CID, request)
    assert store.load(CID) is None


def test_last_action_may_change_length_and_anchor_out_of_box_is_blocked(env):
    source, store, ops = env
    ok = {"family": "pixelart", "action": "skill_ready",
          "frames": [{"png": _png_frame(), "duration": 3, "anchor": [6, 14]} for _ in range(3)]}
    assert not [c for c in ops.pixel_save(CID, {**ok, "dryRun": True})["checks"] if c["level"] == "error"]
    far = {**ok, "frames": [{**ok["frames"][0], "anchor": [400, 14], "duration": 4}]}
    errors = [c for c in ops.pixel_save(CID, {**far, "dryRun": True})["checks"] if c["level"] == "error"]
    assert errors and "超出帧框" in errors[0]["message"]


# -- A3 ---------------------------------------------------------------------------

def test_tier_structure_and_skill_cells_cannot_share_a_request(tmp_path):
    from test_studio_ability import full, skill_row
    from test_studio_ability_text import setup
    ed, _ = setup(tmp_path)
    rows = [skill_row("斩击" + "+" * (i - 1)) for i in (1, 2, 3)]
    delete = {"op": "delete_row", "table": "action_skill", "key": "hero", "level": "1",
              "row": 0, "row_count": 3, "cells": full(rows[0], "delete_row")}
    cell = {"op": "set_cells", "table": "action_skill", "key": "hero", "level": "2", "row": 0, "row_count": 1,
            "cells": [{"column": "c4", "old": "100", "new": "120"}]}
    with pytest.raises(DraftError, match="必须单独写入"):
        ed.apply("139985", {"operations": [delete, cell]})
    assert ed.store.load("139985") is None
