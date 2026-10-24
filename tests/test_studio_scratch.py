"""草稿角色：新建、在母本上工作、导入现成像素集 + 映射表、绑定到角色 ID、未绑定拒绝生成。"""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

from PIL import Image
import pytest

from wf.studio import scratch
from wf.studio.deliver_media import compile_media, encode_png, png, tree
from wf.studio.drafts import DraftError, DraftStore, schema_errors
from wf.studio.operations import DraftOps
from wf.studio.pixel_workshop import decode_family, family_paths, normalize_mapping, remap_family
from wf.studio.pixel_workshop_ops import PixelWorkshop
from wf.studio.pixels import build_family
from wf_pixelart_vfx import frame_index, restore_frame

from test_studio_deliver_media import CID, CODE, Source
from test_studio_pixel_workshop import BASE_CID, BASE_CODE, family_files

SID = "scratch-gerald-water"
MAPPING = {"#a13b3b": "#2a5cc8", "#fc2c2b": "#39b8ff"}


class TableSource(Source):
    def table(self, name):
        if name != "character":
            return {}
        return {CID: [[CODE, "1", "5"]], BASE_CID: [[BASE_CODE, "1", "5"]]}


class Assets:
    @staticmethod
    def locate(logical):
        return "test"


@pytest.fixture
def env(tmp_path):
    source = TableSource({**family_files(BASE_CODE), **family_files(CODE)})
    store = DraftStore(tmp_path / "drafts")
    roster = [{"id": CID, "code": CODE, "name": "目标", "element": "水"},
              {"id": BASE_CID, "code": BASE_CODE, "name": "母本", "element": "火"}]
    ops = DraftOps(source, store=store, assets=Assets(), characters=lambda: roster)
    return source, store, ops


def new_scratch(ops, base=BASE_CODE):
    return scratch.create(ops, {"name": "水杰拉德", "element": "水", "base": base, "slug": "gerald-water"})


def bundle(source, *, hand_drawn=True, code="gerald_water_wip"):
    """What the offline thread hands over: exact remap of the base + hand-drawn skill_ready."""
    raws = [source.files["common", p] for p in family_paths(BASE_CODE, "pixelart")]
    stored = list(remap_family(raws, BASE_CODE, code, normalize_mapping(MAPPING))["stored"])
    if hand_drawn:
        sheet = png(stored[0])
        sheet.paste((255, 255, 255, 255), (17, 1, 21, 3))  # skill_ready-only region (x=16)
        stored[0] = encode_png(sheet)
    names = [Path(p).name for p in family_paths("x", "pixelart")]
    return dict(zip(names, stored))


def test_create_scratch_has_placeholder_code_no_rows_and_base_view(env):
    source, store, ops = env
    info = new_scratch(ops)
    assert info["characterId"] == SID and info["code"] == "scratch_gerald_water"
    assert info["scratch"]["base"] == {"characterId": BASE_CID, "code": BASE_CODE, "name": "母本"}
    assert not schema_errors(store.load(SID))
    assert SID not in source.table("character")
    with pytest.raises(DraftError, match="已存在"):
        new_scratch(ops)
    shop = PixelWorkshop(scratch.ScratchDraftOps(ops, SID))
    analysis = shop.analyze(SID)
    family = analysis["families"][0]
    assert family["frame"]["name"] == "character/scratch_gerald_water/pixelart/pixelart"
    assert family["frame"]["scale"] == 6
    assert [(a["name"], a["begin"], a["end"]) for a in family["actions"]] == [
        ("neutral", 1, 2), ("walk_back", 3, 26), ("skill_ready", 27, 30)]
    assert [s["characterId"] for s in scratch.listing(ops)] == [SID]


def test_scratch_workshop_remap_and_generate_then_build_refused(env, tmp_path):
    source, store, ops = env
    new_scratch(ops)
    shop = PixelWorkshop(scratch.ScratchDraftOps(ops, SID))
    shop.remap(SID, {"base": BASE_CODE, "mapping": [{"from": k, "to": v} for k, v in MAPPING.items()]})
    shop.generate(SID, {"action": "walk_back", "save": True})
    changeset = store.load(SID)
    assert [c["kind"] for c in changeset["changes"]] == ["pixel_family", "pixel_action"]
    compiled = compile_media(shop.source, store, changeset)
    combined = Source({**source.files, **compiled.members})
    combined.raw = lambda logical: compiled.members.get(("common", logical))
    meta, _ = build_family(combined, "scratch_gerald_water", "pixelart", "sprite_sheet")
    assert [a["name"] for a in meta["actions"]] == ["neutral", "walk_back", "skill_ready"]
    from wf.studio.deliver_bridge import build_draft
    with pytest.raises(DraftError, match="还没有绑定游戏角色 ID"):
        build_draft(SID, from_version="1.4.233", to_version="1.4.234", out=tmp_path / "out", store=store)
    assert not (tmp_path / "out").exists()


def test_import_folder_with_remap_table_marks_hand_drawn_actions(env, tmp_path):
    source, store, ops = env
    new_scratch(ops)
    folder = tmp_path / "offline"
    folder.mkdir()
    for name, data in bundle(source).items():
        (folder / name).write_bytes(data)
    (folder / "gerald_remap.json").write_text(json.dumps({"base": BASE_CODE, "mapping": MAPPING}), "utf-8")
    found = scratch.read_bundle(directory=folder)
    dry = scratch.import_set(ops, SID, {"files": {}, "dryRun": True}, found=found)
    prov = dry["families"][0]["provenance"]
    assert prov["comparable"] and prov["differingByAction"] == {"skill_ready": 1}
    assert prov["matchingEndpoints"] == prov["endpoints"] - 1
    assert store.load(SID)["changes"] == []
    result = scratch.import_set(ops, SID, {"files": {}, "name": "离线 v1"}, found=found)
    change = result["changes"][0]
    assert change["params"]["mode"] == "import" and change["params"]["source"]["code"] == "gerald_water_wip"
    assert change["params"]["mapping"] == [{"from": "#a13b3b", "to": "#2a5cc8"}, {"from": "#fc2c2b", "to": "#39b8ff"}]
    assert not schema_errors(store.load(SID))
    atlas = tree(store.read_file(SID, next(f["draft"] for f in change["files"] if f["logical"].endswith(".atlas.amf3.deflate"))))
    assert all(e["n"].startswith("character/scratch_gerald_water/") for e in atlas)


def test_import_zip_and_bad_inputs(env):
    source, store, ops = env
    new_scratch(ops)
    files = bundle(source, hand_drawn=False)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in files.items():
            archive.writestr("export/pixelart/" + name, data)
    found = scratch.read_bundle(zip_bytes=buffer.getvalue())
    assert set(found) == set(files)
    with pytest.raises(DraftError, match="四件不全"):
        scratch.family_sets({k: v for k, v in files.items() if not k.endswith(".timeline.amf3.deflate")})
    broken = dict(files)
    frame = tree(broken["pixelart.frame.amf3.deflate"])
    frame["name"] = "pixelart"
    from wf.studio.deliver_media import encode_tree
    broken["pixelart.frame.amf3.deflate"] = encode_tree(frame)
    with pytest.raises(DraftError, match="frame.name"):
        scratch.import_set(ops, SID, {"files": {}}, found=broken)


def test_bind_reprefixes_to_character_code_and_target_compiles(env, tmp_path):
    source, store, ops = env
    new_scratch(ops)
    found = bundle(source)
    scratch.import_set(ops, SID, {"files": {}, "remap": {"base": BASE_CODE, "mapping": MAPPING}}, found=found)
    shop = PixelWorkshop(scratch.ScratchDraftOps(ops, SID))
    shop.generate(SID, {"action": "walk_back", "save": True})
    with pytest.raises(DraftError):
        scratch.bind(ops, SID, {"characterId": "999999"})  # not in the view
    dry = scratch.bind(ops, SID, {"characterId": CID, "dryRun": True})
    assert dry["code"] == CODE and store.load(CID) is None
    result = scratch.bind(ops, SID, {"characterId": CID})
    assert len(result["created"]) == 2
    target = store.load(CID)
    assert [c["kind"] for c in target["changes"]] == ["pixel_family", "pixel_action"]
    assert not schema_errors(target)
    compiled = compile_media(source, store, target)
    paths = family_paths(CODE, "pixelart")
    atlas = tree(compiled.members["common", paths[1]])
    assert all(e["n"].startswith(f"character/{CODE}/") for e in atlas)
    frame = tree(compiled.members["common", paths[2]])
    keys, entries = frame_index(atlas, frame["name"])
    sheet = png(compiled.members["common", paths[0]])
    hand = restore_frame(sheet, entries[30])  # skill_ready endpoint keeps the hand-drawn pixels
    assert hand.getpixel((125 + 1, 120 + 1)) == (255, 255, 255, 255)
    assert store.load(SID)["scratch"]["boundTo"]["characterId"] == CID
    with pytest.raises(DraftError, match="已绑定"):
        scratch.bind(ops, SID, {"characterId": CID})
    from wf.studio.deliver_bridge import build_draft
    with pytest.raises(DraftError, match="已绑定到 " + CID):
        build_draft(SID, from_version="1.4.233", to_version="1.4.234", out=tmp_path / "out", store=store)


def test_scratch_remap_change_rebinds_deterministically(env):
    source, store, ops = env
    new_scratch(ops)
    shop = PixelWorkshop(scratch.ScratchDraftOps(ops, SID))
    shop.remap(SID, {"base": BASE_CID, "mapping": [{"from": k, "to": v} for k, v in MAPPING.items()]})
    scratch.bind(ops, SID, {"characterId": CID})
    target = store.load(CID)
    assert target["changes"][0]["params"]["mode"] == "remap"
    compiled = compile_media(source, store, target)  # rebuilds from base + mapping with the real code
    sheet = png(compiled.members["common", family_paths(CODE, "pixelart")[0]])
    expected = remap_family([source.files["common", p] for p in family_paths(BASE_CODE, "pixelart")],
                            BASE_CODE, CODE, normalize_mapping(MAPPING))
    assert sheet.tobytes() == png(expected["stored"][0]).tobytes()


def test_scratch_schemas():
    assert not schema_errors({"name": "水杰拉德", "element": "水", "base": "black_wolf_knight_wt23"}, "scratchCreateRequest")
    assert schema_errors({"name": "水杰拉德", "element": "冰", "base": "black_wolf_knight_wt23"}, "scratchCreateRequest")
    assert not schema_errors({"characterId": "139985"}, "scratchBindRequest")
    assert schema_errors({"characterId": "scratch-x"}, "scratchBindRequest")
    assert not schema_errors({"zip": "UEsF", "remap": {"base": "x", "mapping": {}}}, "pixelImportRequest")
    assert schema_errors({"remap": {}}, "pixelImportRequest")
    assert scratch.is_scratch(SID) and not scratch.is_scratch("139985") and not scratch.is_scratch("scratch-")
    assert scratch.slugify("水杰拉德", "black_wolf_knight_wt23").startswith("black-wolf-knight-wt23-")
