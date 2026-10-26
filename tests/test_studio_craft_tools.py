"""交稿四件套：像素批量预检、场地比例、图集重排（等价校验）、稿主交接单。"""
from __future__ import annotations

import base64
import io
import zipfile
import zlib

from PIL import Image
import pytest

import wf_dsl
import wf_quest_lib as codec
from wf.boss import schema as s
from wf.studio import atlas_optimize, handoff, stage_scale
from wf.studio.deliver_media import encode_png, encode_tree, png, tree
from wf.studio.deliver_pixel import compile_pixels
from wf.studio.drafts import DraftError, DraftStore
from wf.studio.operations import DraftOps
from wf.studio.pixel_precheck import parse_name, precheck
from wf.studio.pixel_workshop import family_paths

from test_studio_deliver_media import CID, CODE, Source
from test_studio_pixel_workshop import family_files


class Ops(DraftOps):
    """Real DraftOps (pixel_save, _commit, file maker) over the in-memory fixture source."""

    def __init__(self, source, store):
        super().__init__(source, store=store, assets=type("A", (), {"locate": staticmethod(lambda logical: "test")})(),
                         characters=lambda: [])

    def character(self, cid):
        if cid != CID:
            raise DraftError("missing")
        return {"id": cid, "code": CODE, "element": "火", "name": "目标"}


@pytest.fixture
def ops(tmp_path):
    return Ops(Source(family_files(CODE)), DraftStore(tmp_path / "drafts"))


def frame(w=6, h=8, colour=(161, 59, 59)):
    """A 256×256 frame box (the fixture's) with a body standing on the anchor (128, 128)."""
    image = Image.new("RGBA", (256, 256))
    image.paste(colour + (255,), (128 - w // 2, 128 - h, 128 - w // 2 + w, 128))
    return image


def b64png(image):
    out = io.BytesIO()
    image.save(out, "PNG")
    return base64.b64encode(out.getvalue()).decode("ascii")


# -- 像素批量预检 ---------------------------------------------------------------

@pytest.mark.parametrize("name,expected", [
    ("neutral_01.png", ("neutral", 1, False)),
    ("walk_front-3.png", ("walk_front", 3, False)),
    ("pack/walk_back/02.png", ("walk_back", 2, False)),
    ("neutral_sp_01.png", ("neutral", 1, True)),
    ("neutral_01_sp.png", ("neutral", 1, True)),
    ("neutral_sp/01.png", ("neutral", 1, True)),
    ("skill_ready.png", ("skill_ready", None, False)),
    ("special_land_04.png", ("special_land", 4, False)),
])
def test_parse_name(name, expected):
    parsed = parse_name(name)
    assert (parsed["action"], parsed["index"], parsed["composite"]) == expected


def test_parse_name_rejects_non_png_and_odd_names():
    assert parse_name("neutral_01.jpg") is None
    assert parse_name("01.png") is None
    assert parse_name("Neutral 01 final!.png") is None


def test_precheck_groups_flags_composites_and_unknowns(ops):
    files = {"neutral_02.png": b64png(frame()), "neutral_01.png": b64png(frame()),
             "neutral_sp_01.png": b64png(frame(40)),
             "walk_back/01.png": b64png(frame()), "walk_back/02.png": b64png(frame()),
             "kachidoki_01.png": b64png(frame()), "foo bar.png": b64png(frame()),
             "readme.txt": base64.b64encode(b"hi").decode()}
    result = precheck(ops, CID, {"family": "pixelart", "files": files})
    actions = {a["action"]: a for a in result["actions"]}
    assert actions["neutral"]["files"] == ["neutral_01.png", "neutral_02.png"]
    assert "neutral_sp_01.png" not in actions["neutral"]["files"]
    assert [c["file"] for c in result["composite"]] == ["neutral_sp_01.png"]
    assert any(c["code"] == "precheck.composite" for c in result["checks"])
    assert result["unmatched"] == ["foo bar.png"] and result["ignored"] == ["readme.txt"]
    assert actions["neutral"]["ok"] and actions["walk_back"]["ok"]
    # Durations keep the original total (neutral 1-2 = 2 frames, walk_back 3-26 = 24).
    assert actions["neutral"]["durations"] == [1, 1] and sum(actions["walk_back"]["durations"]) == 24
    assert not actions["kachidoki"]["ok"]
    assert any(c["code"] == "precheck.missing_slot" for c in actions["kachidoki"]["checks"])
    assert set(result["ready"]) == {"neutral", "walk_back"}


def test_precheck_companion_mark(ops):
    files = {"skill_ready_01.png": b64png(frame(40)), "skill_ready_02.png": b64png(frame(40))}
    plain = precheck(ops, CID, {"files": files})
    codes = {c["code"] for c in plain["actions"][0]["checks"]}
    assert "precheck.companion_suspect" in codes
    marked = precheck(ops, CID, {"files": files, "actions": {"skill_ready": {"includesCompanion": True, "purpose": "放召唤兽"}}})
    codes = {c["code"] for c in marked["actions"][0]["checks"]}
    assert "precheck.companion" in codes and "precheck.companion_suspect" not in codes and "pixel.scale" not in codes
    assert marked["actions"][0]["purpose"] == "放召唤兽"


def test_precheck_reads_zip_and_applies_clean_actions(ops):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for name in ("neutral/01.png", "neutral/02.png", "__MACOSX/neutral/._01.png"):
            data = io.BytesIO()
            frame().save(data, "PNG")
            archive.writestr(name, data.getvalue())
    body = {"zip": base64.b64encode(stream.getvalue()).decode(), "apply": True,
            "actions": {"neutral": {"includesCompanion": False, "purpose": "待机"}}}
    result = precheck(ops, CID, body)
    assert result["applied"] and [s["action"] for s in result["saved"]] == ["neutral"]
    change = ops.store.load(CID)["changes"][0]
    assert change["kind"] == "pixel_action" and change["target"] == {"family": "pixelart", "action": "neutral"}
    assert change["params"]["origin"] == {"mode": "batch", "files": ["neutral/01.png", "neutral/02.png"],
                                          "includesCompanion": False, "purpose": "待机"}


def test_precheck_apply_refuses_when_nothing_is_clean(ops):
    with pytest.raises(DraftError, match="没有可写入"):
        precheck(ops, CID, {"files": {"kachidoki_01.png": b64png(frame())}, "apply": True})


# -- 图集重排 -------------------------------------------------------------------

def sparse_family(ops):
    """Rewrite the fixture sheet so the same four regions sit far apart in a 200×120 sheet."""
    paths = family_paths(CODE, "pixelart")
    files = ops.source.files
    old_sheet, atlas = png(files["common", paths[0]]), tree(files["common", paths[1]])
    sheet = Image.new("RGBA", (200, 120))
    moved = {}
    for index, region in enumerate(sorted({(e["x"], e["y"], e["w"], e["h"]) for e in atlas})):
        x, y, w, h = region
        target = (10 + index * 50, 10 + index * 25)
        sheet.paste(old_sheet.crop((x, y, x + w, y + h)), target)
        moved[region] = target
    for entry in atlas:
        entry["x"], entry["y"] = moved[(entry["x"], entry["y"], entry["w"], entry["h"])]
    files["common", paths[0]] = encode_png(sheet)
    files["common", paths[1]] = encode_tree(atlas)
    return sheet, atlas


def test_repack_shrinks_and_proves_equivalence(ops):
    sparse_family(ops)
    done = atlas_optimize.preview(ops, CID, "pixelart")
    report = done["report"]
    assert report["worthIt"] and report["output"]["area"] < report["source"]["area"]
    assert report["equivalence"]["framesCompared"] == 5  # every endpoint, reused regions included
    assert report["regions"] == 4 and report["records"] == 5


def test_repack_rejects_pixels_outside_regions(ops):
    sheet, _ = sparse_family(ops)
    sheet.putpixel((199, 119), (1, 2, 3, 255))
    ops.source.files["common", family_paths(CODE, "pixelart")[0]] = encode_png(sheet)
    with pytest.raises(DraftError, match="不能安全重排"):
        atlas_optimize.preview(ops, CID, "pixelart")


def test_repack_apply_writes_a_family_import_that_compiles(ops):
    sparse_family(ops)
    result = atlas_optimize.apply(ops, CID, "pixelart")
    changeset = ops.store.load(CID)
    change = changeset["changes"][0]
    assert change["kind"] == "pixel_family" and change["params"]["mode"] == "import"
    assert change["params"]["source"]["kind"] == "atlas_repack"
    built = compile_pixels(ops.source, ops.store, changeset)
    sheet = png(built.members["common", family_paths(CODE, "pixelart")[0]])
    assert sheet.size == (result["report"]["output"]["width"], result["report"]["output"]["height"])
    with pytest.raises(DraftError, match="已经有"):
        atlas_optimize.apply(ops, CID, "pixelart")


# -- 交接单 ---------------------------------------------------------------------

def test_handoff_separates_notes_files_and_not_in_game(ops):
    handoff.save_notes(ops.store, CID, {"title": "火焰少女", "author": "画师A", "summary": "整套待机+技能",
                                        "actions": {"neutral": {"purpose": "待机", "includesCompanion": True},
                                                    "skill_ready": {"purpose": "技能准备"}}})
    precheck(ops, CID, {"files": {"neutral_01.png": b64png(frame()), "neutral_02.png": b64png(frame())},
                        "apply": True})
    doc = handoff.sheet(ops, CID)
    assert doc["notes"]["author"] == "画师A"
    assert any(f["file"].endswith("frame_000.png") for f in doc["frames"])
    kinds = {i["kind"] for i in doc["notInGame"]}
    assert {"pending", "unsaved", "described_only", "mismatch"} <= kinds
    neutral = next(a for a in doc["actions"] if a["action"] == "neutral")
    assert neutral["inDraft"] and neutral["frames"] == 2
    text = handoff.markdown(doc)
    assert "## 一、作者说明" in text and "## 二、草稿里的真实文件" in text and "## 三、还没接入游戏的部分" in text
    assert "技能准备" in text


def test_handoff_without_draft_or_notes(ops):
    doc = handoff.sheet(ops, CID)
    assert doc["files"] == [] and doc["notInGame"] == [] and doc["status"]["state"] == "clean"
    assert "（草稿里没有文件）" in handoff.markdown(doc)


def test_handoff_notes_reject_bad_action_names(ops):
    with pytest.raises(DraftError):
        handoff.save_notes(ops.store, CID, {"actions": {"../x": {}}})


# -- 场地比例 -------------------------------------------------------------------

def _row(size, values):
    cells = ["(None)"] * size
    for column, value in values.items():
        cells[column] = str(value)
    return ",".join(cells)


class TableSource:
    version = "test"

    def __init__(self, tables, files):
        self.files = {key: codec.build_node(value) for key, value in tables.items()} | files

    def raw_with_origin(self, logical):
        return self.files.get(logical), "fixture" if logical in self.files else None


def stage_source():
    terrain = {"layers": [{"name": "visual", "type": "tilelayer"},
                          {"name": "0", "type": "objectgroup", "objects": [
                              {"type": "BOUNDS", "x": 0, "y": 0, "width": 180, "height": 320},
                              {"type": "WALL", "x": 0, "y": 300, "width": 180, "height": 20},
                              {"type": "CUSTOM_POSITION", "name": "p0", "x": 85, "y": 100, "width": 10, "height": 10},
                              *[{"type": "COFFIN", "x": 30 + 20 * i, "y": 250, "width": 10, "height": 10} for i in range(3)]]}]}
    compressor = zlib.compressobj(wbits=-15)
    raw = compressor.compress(wf_dsl.encode_amf3(terrain)) + compressor.flush()
    tables = {"master/quest/main_quest.orderedmap": {"1": {"2": {"1": _row(130, {0: "1002001", 2: "1-2-1", 109: "fd121"})}}},
              "master/quest/event/hard_multi_event_quest.orderedmap": {"9": {"1": _row(130, {0: "9001", 110: "fd121"})}},
              s.FIELD_DATA: {"fd121": "field,battle/terrain/main/1_2_1,zone"}}
    return TableSource(tables, {"battle/terrain/main/1_2_1.amf3.deflate": raw})


def test_stage_reads_real_bounds_and_coffins():
    result = stage_scale.stage(stage_source())
    assert result["quest"]["id"] == "1002001" and result["quest"]["fieldData"] == "fd121"
    assert result["bounds"] == {"x": 0, "y": 0, "width": 1080, "height": 1920}
    assert [(c["x"], c["y"]) for c in result["coffins"]] == [(210, 1530), (330, 1530), (450, 1530)]
    assert result["positions"][0]["name"] == "p0"
    assert any(o["type"] == "WALL" for o in result["objects"])


def test_stage_finds_shifted_field_data_column_and_reports_missing():
    assert stage_scale.stage(stage_source(), "9001")["quest"]["kind"] == "hard_multi"
    with pytest.raises(DraftError, match="找不到关卡"):
        stage_scale.stage(stage_source(), "123")
    assert stage_scale.stage(stage_source(), terrain="battle/terrain/main/1_2_1")["bounds"]["height"] == 1920


# -- routes ---------------------------------------------------------------------

class AppSource(Source):
    """Fixture view the whole StudioApp can sit on: one character, its pixel family, a 1-2-1 stage."""
    view = None

    def __init__(self):
        stage = stage_source()
        super().__init__(family_files(CODE) | {("common", k): v for k, v in stage.files.items()})

    def describe(self):
        return {"version": self.version, "extraZips": []}

    def table(self, name, official=False):
        return {CID: [[CODE]]} if name == "character" else {}

    def raw(self, logical, official=False):
        return super().raw(logical)

    def raw_with_origin(self, logical, official=False):
        value = self.raw(logical)
        return value, "fixture" if value is not None else None

    def citation(self, name):
        return {"logical": name}


def test_routes_end_to_end(tmp_path):
    import json
    from wf.studio.server import StudioApp
    app = StudioApp(AppSource(), drafts=DraftStore(tmp_path / "drafts"))
    app.ops.character = lambda cid: Ops.character(None, cid)
    call = lambda method, path, query=None, body=None: app.dispatch(method, path, query or {}, body)
    sparse = Ops(app.source, app.ops.store)
    sparse_family(sparse)
    report = json.loads(call("GET", f"/api/characters/{CID}/atlas-repack", {"family": ["pixelart"]}).body)
    assert report["worthIt"] and report["equivalence"]["framesCompared"] == 5
    image = call("GET", f"/api/characters/{CID}/atlas-repack/pixelart.png")
    assert image.content_type == "image/png" and Image.open(io.BytesIO(image.body)).size == (
        report["output"]["width"], report["output"]["height"])
    checked = json.loads(call("POST", f"/api/drafts/{CID}/pixel-precheck",
                              body={"files": {"neutral_01.png": b64png(frame())}}).body)
    assert checked["ready"] == ["neutral"]
    assert call("POST", f"/api/drafts/{CID}/handoff-notes", body={"title": "测试", "author": "画师"}).status == 200
    md = call("GET", f"/api/drafts/{CID}/handoff", {"format": ["md"]})
    assert md.content_type.startswith("text/markdown") and "交接单：测试" in md.body.decode("utf-8")
    stage = json.loads(call("GET", "/api/stage-scale", {"quest": ["1002001"]}).body)
    assert stage["bounds"]["height"] == 1920
    assert call("GET", "/api/stage-scale", {"quest": ["../x"]}).status == 400
