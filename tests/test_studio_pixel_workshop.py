"""像素工坊：拆解、母本映射确定性与交付回读、程序化动作几何（含 fy 编码）。"""
from __future__ import annotations

import base64
import io

from PIL import Image
import pytest

from wf.studio.deliver_media import compile_media, encode_png, encode_tree, png, tree
from wf.studio.drafts import DraftError, DraftStore, schema_errors, sha256
from wf.studio.pixel_generate import RECIPES, generate, ghostify, place, scaled_ends
from wf.studio.pixel_workshop import analyze, family_paths, normalize_mapping, recolor, remap_family
from wf.studio.pixel_workshop_ops import PixelWorkshop
from wf.studio.pixels import build_family
from wf_pixelart_vfx import frame_index, restore_frame

from test_studio_deliver_media import CID, CODE, Source, changeset

BASE_CID, BASE_CODE = "111007", "mother"
BODY, CAPE, FIRE, OUTLINE = (161, 59, 59), (75, 33, 31), (252, 44, 43), (0, 0, 0)


def sprite(colour, w=6, h=8):
    image = Image.new("RGBA", (w, h))
    image.paste(OUTLINE + (255,), (0, 0, w, h))
    image.paste(colour + (255,), (1, 1, w - 1, h - 1))
    return image


def family_files(code, *, timeline_extra=None):
    """A tiny pixelart family: neutral 1-2, walk_back 3-26 (2 imgs), skill_ready 27-30 (fire), sparse + reuse."""
    sheet = Image.new("RGBA", (32, 16))
    sheet.paste(sprite(BODY), (0, 0))
    sheet.paste(sprite(CAPE), (8, 0))
    fire = sprite(BODY)
    fire.paste(FIRE + (255,), (2, 2, 4, 4))
    sheet.paste(fire, (16, 0))
    sheet.paste(sprite((10, 200, 10)), (24, 0))  # never referenced by a sequence
    prefix = f"character/{code}/pixelart/pixelart"

    def entry(n, x, fy):
        return {"n": f"{prefix}{n:04d}", "x": x, "y": 0, "w": 6, "h": 8, "fx": -(128 - 3), "fy": fy, "fw": 256, "fh": 256}
    atlas = [entry(2, 0, -120), entry(14, 0, -120), entry(26, 8, -121), entry(30, 16, -120), entry(40, 24, -120)]
    frame = {"name": prefix, "x": -128, "y": -128, "scale": 6, "smoothing": False}
    timeline = {"sequences": [{"name": "neutral", "kind": "loop", "begin": 1, "end": 2},
                              {"name": "walk_back", "kind": "loop", "begin": 3, "end": 26},
                              {"name": "skill_ready", "kind": "once", "begin": 27, "end": 30}],
                "circles": [], "points": [], "sounds": timeline_extra or []}
    paths = family_paths(code, "pixelart")
    return {("common", p): raw for p, raw in zip(paths, [encode_png(sheet), encode_tree(atlas), encode_tree(frame),
                                                          encode_tree(timeline)])}


class Ops:
    """Minimal DraftOps stand-in: two characters, real draft store and file maker."""

    def __init__(self, source, store):
        from wf.studio.operations import DraftOps
        self.source = source
        self.store = store
        self._real = DraftOps.__new__(DraftOps)
        self._real.source, self._real.store = source, store
        self._real.assets = type("A", (), {"locate": staticmethod(lambda logical: "test")})()

    def character(self, cid):
        codes = {CID: CODE, BASE_CID: BASE_CODE}
        if cid not in codes:
            raise DraftError("missing")
        return {"id": cid, "code": codes[cid], "element": "火", "name": "母本" if cid == BASE_CID else "目标"}

    def _file_maker(self, cid):
        return self._real._file_maker(cid)

    def _commit(self, cid, code, kind, built):
        self._real.source = self.source
        return self._real._commit(cid, code, kind, built)


@pytest.fixture
def setup(tmp_path):
    source = Source({**family_files(BASE_CODE), **family_files(CODE)})
    store = DraftStore(tmp_path / "drafts")
    ops = Ops(source, store)
    return source, store, ops, PixelWorkshop(ops)


# -- 拆解 ---------------------------------------------------------------------

def test_analyze_reports_dedup_unused_dy_and_palette_groups(setup):
    source, *_ = setup
    result = analyze(source, BASE_CODE)
    family = result["families"][0]
    actions = {a["name"]: a for a in family["actions"]}
    assert [c["key"] for c in actions["walk_back"]["cells"]] == [14, 26]
    assert [c["frames"] for c in actions["walk_back"]["cells"]] == [12, 12]
    # Endpoint 2 and 14 share one atlas region (x=0): a reuse.
    neutral_region = actions["neutral"]["cells"][0]["region"]
    assert actions["walk_back"]["cells"][0]["region"] == neutral_region
    assert family["regions"][neutral_region]["keys"] == [2, 14]
    # dy from fy: fy=-120, h=8 -> top 120, bottom 128 -> dy 0; fy=-121 -> top 121, sinks 1px.
    assert actions["neutral"]["cells"][0]["dy"] == 0
    assert actions["walk_back"]["cells"][1]["dy"] == 1
    assert family["unusedKeys"] == [40] and len(family["unusedRegions"]) == 1
    groups = {p["hex"]: p["group"] for p in result["palette"]}
    assert groups["#a13b3b"] == "body" and groups["#4b211f"] == "body"
    assert groups["#fc2c2b"] == "fx" and groups["#000000"] == "outline"
    assert "#0ac80a" not in groups  # unused region contributes no palette


def test_analyze_flags_teleport_walk_and_scale(setup):
    source, *_ = setup
    paths = family_paths(BASE_CODE, "pixelart")
    sheet = png(source.files["common", paths[0]])
    sheet.paste((0, 0, 0, 0), (8, 0, 14, 8))
    sheet.putpixel((8, 7), (0, 0, 0, 255))  # walk frame almost empty
    frame = tree(source.files["common", paths[2]])
    frame["scale"] = 3.36
    source.files["common", paths[0]] = encode_png(sheet)
    source.files["common", paths[2]] = encode_tree(frame)
    codes = {c["code"] for c in analyze(source, BASE_CODE)["families"][0]["checks"]}
    assert {"workshop.walk_teleport", "workshop.scale", "workshop.missing_sequence"} <= codes


# -- 母本映射 -------------------------------------------------------------------

def test_recolor_is_exact_and_keeps_alpha_and_hidden_rgb():
    image = Image.new("RGBA", (3, 1))
    image.putpixel((0, 0), BODY + (255,))
    image.putpixel((1, 0), BODY + (128,))
    image.putpixel((2, 0), BODY + (0,))
    out, changed = recolor(image, {BODY: (1, 2, 3)})
    assert changed == 2
    assert out.getpixel((0, 0)) == (1, 2, 3, 255) and out.getpixel((1, 0)) == (1, 2, 3, 128)
    assert out.getpixel((2, 0)) == BODY + (0,)


def test_remap_is_deterministic_and_renames_prefix(setup):
    source, *_ = setup
    raws = [source.files["common", p] for p in family_paths(BASE_CODE, "pixelart")]
    mapping = normalize_mapping([{"from": "#a13b3b", "to": "#2040c0"}, {"from": "#fc2c2b", "to": "#9666ff"}])
    first = remap_family(raws, BASE_CODE, CODE, mapping)
    second = remap_family(raws, BASE_CODE, CODE, dict(reversed(list(mapping.items()))))
    assert first["stored"] == second["stored"]
    atlas, frame = tree(first["stored"][1]), tree(first["stored"][2])
    assert all(e["n"].startswith(f"character/{CODE}/") for e in atlas)
    assert frame["name"] == f"character/{CODE}/pixelart/pixelart" and frame["scale"] == 6
    assert first["stored"][3] == raws[3]  # timeline byte-identical
    keys, entries = frame_index(atlas, frame["name"])
    assert keys == [2, 14, 26, 30, 40]
    restored = restore_frame(png(first["stored"][0]), entries[30])
    assert restored.getpixel((125 + 2, 120 + 2)) == (150, 102, 255, 255)  # fire mapped
    assert restored.getpixel((125 + 1, 120 + 1)) == (32, 64, 192, 255)  # body mapped
    assert restored.getpixel((125, 120)) == OUTLINE + (255,)  # outline kept
    with pytest.raises(DraftError):
        normalize_mapping([{"from": "#a13b3b", "to": "#000001"}, {"from": "#A13B3B", "to": "#000002"}])


def test_remap_draft_compiles_and_player_decodes(setup):
    source, store, ops, shop = setup
    request = {"base": BASE_CID, "mapping": [{"from": "#a13b3b", "to": "#2040c0"}], "families": ["pixelart"]}
    dry = shop.remap(CID, {**request, "dryRun": True})
    assert dry["dryRun"] and dry["families"][0]["changedPixels"] > 0 and store.load(CID) is None
    result = shop.remap(CID, request)
    change = result["changes"][0]
    assert change["kind"] == "pixel_family" and len(change["files"]) == 4
    assert not schema_errors(store.load(CID))
    compiled = compile_media(source, store, store.load(CID))
    sheet_path = family_paths(CODE, "pixelart")[0]
    assert ("common", sheet_path) in compiled.members
    combined = Source({**source.files, **compiled.members})
    meta, preview = build_family(combined, CODE, "pixelart", "sprite_sheet")
    assert [a["name"] for a in meta["actions"]] == ["neutral", "walk_back", "skill_ready"]
    assert meta["scale"] == 6 and preview.startswith(b"\x89PNG")
    # Determinism guard: tampering the draft sheet is caught at compile time.
    entry = next(f for f in change["files"] if f["logical"] == sheet_path)
    tampered = png(encode_png(png(compiled.members["common", sheet_path])))
    tampered.putpixel((1, 1), (9, 9, 9, 255))
    out = io.BytesIO()
    tampered.save(out, "PNG")
    store.write_file(CID, entry["draft"], out.getvalue())
    with pytest.raises(DraftError):
        compile_media(source, store, store.load(CID))


def test_remap_base_drift_is_rejected(setup):
    source, store, ops, shop = setup
    shop.remap(CID, {"base": BASE_CID, "mapping": [{"from": "#a13b3b", "to": "#2040c0"}], "families": ["pixelart"]})
    timeline_path = family_paths(BASE_CODE, "pixelart")[3]
    timeline = tree(source.files["common", timeline_path])
    timeline["sequences"][0]["end"] = 2
    timeline["circles"] = [{"x": 1}]
    source.files["common", timeline_path] = encode_tree(timeline)
    with pytest.raises(DraftError, match="母本文件已变化"):
        compile_media(source, store, store.load(CID))


# -- 程序化动作 -----------------------------------------------------------------

def test_place_encodes_dy_in_fy():
    body = sprite(BODY, 5, 9)
    for dy in (0, 1, -12):
        frame = place(body, dy)
        left, top, right, bottom = frame.getbbox()
        assert (left, right) == (128 - 5 // 2, 128 - 5 // 2 + 5)
        assert top == 128 - 9 + dy and bottom == 128 + dy  # fy = -(128 - h + dy)


def test_walk_recipe_geometry_and_official_endpoints():
    body = sprite(BODY, 6, 8)
    frames = generate("walk_front", {"front": body})
    assert [f["duration"] for f in frames] == [6, 6, 6, 6]
    assert [f["dy"] for f in frames] == [0, 1, 0, 1]
    tops = [f["image"].getbbox()[1] for f in frames]
    assert tops == [120, 121, 120, 121]
    assert frames[0]["image"].tobytes() == frames[2]["image"].tobytes()
    assert frames[1]["image"].tobytes() != frames[3]["image"].tobytes()  # skirt sways opposite ways


@pytest.mark.parametrize("action", sorted(RECIPES))
def test_every_recipe_sums_to_requested_total_and_stays_in_box(action):
    bases = {"front": sprite(BODY), "back": sprite(CAPE), "liedown": sprite(BODY, 10, 4)}
    for total in (RECIPES[action]["total"], RECIPES[action]["total"] + 7):
        frames = generate(action, bases, total)
        assert sum(f["duration"] for f in frames) == total
        assert all(f["image"].size == (256, 256) and f["image"].getbbox() for f in frames)
    again = generate(action, bases)
    assert [f["image"].tobytes() for f in again] == [f["image"].tobytes() for f in generate(action, bases)]


def test_kachidoki_apex_is_the_begin_plus_18_frame_and_ghost_hovers():
    bases = {"front": sprite(BODY)}
    frames = generate("kachidoki", bases)
    ends, cursor = [], 0
    for f in frames:
        cursor += f["duration"]
        ends.append(cursor)
    apex = next(i for i, end in enumerate(ends) if end >= 19)  # begin+18 -> 19th frame
    assert frames[apex]["dy"] < 0 and "火花" in frames[apex]["note"]
    ghost = generate("ghost_neutral", bases)
    assert all(f["dy"] <= -11 for f in ghost)
    assert ghost[0]["image"].getbbox()[3] <= 128 - 11
    ghost_pixels = ghostify(sprite(BODY))
    colours = {ghost_pixels.getpixel((x, y))[:3] for x in range(ghost_pixels.width) for y in range(ghost_pixels.height)
               if ghost_pixels.getpixel((x, y))[3]}
    assert colours <= {(255, 255, 255), (196, 208, 232), (112, 128, 168)}


def test_scaled_ends_keep_order():
    assert scaled_ends([6, 12, 42, 48], 48, 48) == [6, 12, 42, 48]
    assert scaled_ends([6, 12, 42, 48], 48, 24) == [3, 6, 21, 24]
    with pytest.raises(DraftError):
        scaled_ends([1, 2, 3, 4], 4, 3)


def test_generated_frames_feed_existing_pixel_slot_compile(setup, tmp_path):
    source, store, ops, shop = setup
    frames = generate("walk_back", {"back": sprite(CAPE)}, 24)
    stored = []
    for index, frame in enumerate(frames):
        out = io.BytesIO()
        frame["image"].save(out, "PNG")
        relative = f"files/pixel/pixelart/walk_back/frame_{index:03d}.png"
        store.write_file(CID, relative, out.getvalue())
        stored.append({"file": relative, "sha256": sha256(out.getvalue()), "duration": frame["duration"],
                       "anchor": [128, 128], "width": 256, "height": 256})
    change = {"kind": "pixel_action", "target": {"family": "pixelart", "action": "walk_back"}, "files": [],
              "params": {"frames": stored, "totalFrames": 24, "originalTotalFrames": 24}}
    result = compile_media(source, store, changeset([change]))
    paths = family_paths(CODE, "pixelart")
    atlas = tree(result.members["common", paths[1]])
    frame = tree(source.files["common", paths[2]])
    keys, entries = frame_index(atlas, frame["name"])
    assert {8, 14, 20, 26} <= set(keys)
    assert entries[8]["fy"] == -(128 - 8 + 0) and entries[14]["fy"] == -(128 - 8 + 1)
    assert entries[8]["fx"] == -(128 - 6 // 2)
    # Frames 1 and 3 of the walk are identical: one shared atlas region.
    region = lambda e: (e["x"], e["y"], e["w"], e["h"])
    assert region(entries[8]) == region(entries[20]) and region(entries[14]) != region(entries[26])


def test_ground_offset_moves_whole_action():
    plain = generate("walk_front", {"front": sprite(BODY)})
    lowered = generate("walk_front", {"front": sprite(BODY)}, ground=1)
    assert [f["dy"] for f in lowered] == [1, 2, 1, 2]
    assert [f["image"].getbbox()[1] for f in lowered] == [f["image"].getbbox()[1] + 1 for f in plain]


def test_request_schemas_accept_and_reject():
    assert not schema_errors({"base": "111007", "mapping": [{"from": "#a13b3b", "to": "#2040C0"}]}, "pixelRemapRequest")
    assert schema_errors({"base": "111007", "mapping": [{"from": "red", "to": "#2040c0"}]}, "pixelRemapRequest")
    png_b64 = base64.b64encode(b"x").decode()
    assert not schema_errors({"action": "walk_front", "bases": {"front": {"png": png_b64}}}, "pixelGenerateRequest")
    assert schema_errors({"action": "dance"}, "pixelGenerateRequest")
    assert schema_errors({"action": "walk_front", "bases": {"front": {}}}, "pixelGenerateRequest")
