"""Synthetic clone contracts: nested rows, prerequisites, mirrors, special and scratch."""
import json
from pathlib import Path

import pytest
from PIL import Image

import wf_mod_tool as core
import wf_character_requirements as requirements
from wf.studio.character_clone import clone, clone_members, compile_clone, ops_for
from wf.studio.character_routes import promote
from wf.studio.clone_tables import T, leaf, rows, server_entries
from wf.studio.deliver_media import encode_png, encode_tree, tree
from wf.studio.drafts import DraftStore, DraftError, schema_errors
from wf.studio.operations import DraftOps
from wf.studio.source import StudioSource
from wf.studio.pixel_workshop import family_paths
from wf.deliver.changeset import member_name
from test_studio_pixel_workshop import family_files
from test_m1_balance import valid_row

OLD, NEW, CODE = "111007", "139988", "clone_demo"


def ordered(entries):
    return core.build_orderedmap_raw_rows(core.OrderedMap("fixture", list(entries), list(entries.values()), Path("fixture")))


class View:
    tip, zips, extra_zips = "1.4.233", [], []
    store = Path("/__no_fixture_store__")
    def __init__(self, files):
        self.files = files
        self.index = {member_name(root, logical): "fixture.zip" for root, logical in files}
    def read_member(self, name):
        for key, value in self.files.items():
            if member_name(*key) == name:
                return value, "fixture.zip"
        raise FileNotFoundError(name)
    def read_raw(self, logical):
        for root in ("common", "medium", "android"):
            if (root, logical) in self.files:
                return self.files[root, logical], "fixture.zip"
        raise FileNotFoundError(logical)


@pytest.fixture
def env(tmp_path):
    char = [""] * 37
    char[0], char[2], char[3], char[8], char[27] = "mother", "5", "0", "mother_skill", OLD
    char[17], char[18] = "3", "队长"
    char[19:25] = [str(100 + i) for i in range(6)]
    char[26] = "Attacker"
    node1, node2 = str(int(OLD) * 2000 + 1), str(int(OLD) * 2000 + 2)
    mana = ordered({"1": ordered({"1": leaf([[node1, "0", "10", "1", "5", "0", "0"]]),
                                  "2": leaf([[node2, "0", "10", "2", "9", node1, "0"]])})})
    board = ordered({"1": ordered({"1": leaf([[node1, "0", "0", "0", "0", ""]]),
                                   "2": leaf([[node2, "0", "0", "0", "0", node1]])})})
    tables = {T.CHAR: ordered({OLD: leaf([char])}), T.TEXT: ordered({OLD: leaf([["母本", "", "", "", "技能", "", "技能", "", "", "", "队长", "CV"]])}),
              T.STATUS: ordered({OLD: ordered({"1": leaf([["1", "2"]])})}),
              T.ACTION: ordered({"mother_skill": ordered({"1": leaf([["技能", "说明", "", "", "", "", "", "battle/action/skill/mother"]])})}),
              T.MANA_BOARD: ordered({OLD: board}), T.MANA_NODE: ordered({OLD: mana}),
              T.CHAR_IMAGE: ordered({OLD: ordered({"0": leaf([["0", "0", "4", "4"]]), "1": leaf([["0", "0", "4", "4"]])})}),
              T.FULL_SHOT_ATTR: ordered({OLD: ordered({"0": leaf([["1000", "1000", "1", "2", "2"]]), "1": leaf([["1000", "1000", "1", "2", "2"]])})}),
              T.SPEECH: ordered({OLD: leaf([["0", "2", "0", "你好", "home/home_0"]])}),
              T.SKILL_PREVIEW: ordered({OLD: leaf([["character/mother/battle/character_detail_skill_preview"]])}),
              T.TRIMMED: ordered({f"character/mother/ui/{stem}": leaf([["0", "0", "4", "4"]]) for stem in
                                 ("full_shot_1440_1920_0", "full_shot_1440_1920_1", "skill_cutin_0", "skill_cutin_1")})}
    tables[T.ABILITY] = ordered({str(100+i): leaf([valid_row("mother_" + str(i))]) for i in range(6)})
    tables[T.LEADER] = ordered({"3": leaf([valid_row()[:1] + valid_row()[3:]])})
    files = {("common", key): value for key, value in tables.items()}
    for item in requirements.char_asset_requirements("mother"):
        if item.category != "required":
            continue
        logical = item.logical_path
        if logical.endswith(".png"):
            root = "medium" if "/ui/" in logical else "common"
            files[root, logical] = encode_png(Image.new("RGBA", (4, 4), "red"))
        elif logical.endswith(".atf.deflate"):
            files["android", logical] = b"fixture-atf"
        else:
            files["common", logical] = encode_tree([])
    files.update(family_files("mother"))
    basic = family_paths("mother", "pixelart")
    special = family_paths("mother", "special")
    files["common", special[0]] = files["common", basic[0]]
    for index in (1, 2):
        value = tree(files["common", basic[index]])
        text = json.dumps(value).replace("pixelart/pixelart", "pixelart/special")
        files["common", special[index]] = encode_tree(json.loads(text))
    files["common", special[3]] = encode_tree({"sequences": [
        {"name": "special_land", "kind": "once", "begin": 1, "end": 30},
        {"name": "special_pose", "kind": "loop", "begin": 31, "end": 40}], "circles": [], "points": []})
    files["common", "battle/action/skill/mother.action.dsl.amf3.deflate"] = encode_tree(["ActionDsl"])
    source = StudioSource(View(files))
    store = DraftStore(tmp_path / "drafts")
    roster = [{"id": OLD, "code": "mother", "name": "母本", "element": "火", "origin": "official"}]
    ops = DraftOps(source, store=store, characters=lambda: roster)
    server = tmp_path / "server"
    server.mkdir()
    for name in ("character.json", "cdndata/character.json", "cdndata/character_text.json", "mana_node.json", "mana_board.json"):
        path = server / name
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps({"other": {"preserve": True}}), encoding="utf-8")
    return source, store, ops, server


def request(**kwargs):
    return {"from": OLD, "to": NEW, "code": CODE, **kwargs}


def test_clone_full_tables_nested_mana_references_and_five_mirrors(env):
    source, store, ops, server = env
    before = dict(source.view.files)
    result = clone(ops, request(), server_dir=server)
    draft = result["changeset"]
    assert not schema_errors(draft) and len(result["assets"]) == 37
    assert result["buildable"]
    members, servers, preimages, assertions, checks = compile_clone(source, store, draft, server_dir=server)
    for logical in (T.CHAR, T.TEXT, T.STATUS, T.MANA_BOARD, T.MANA_NODE, T.CHAR_IMAGE, T.FULL_SHOT_ATTR, T.SPEECH, T.SKILL_PREVIEW):
        assert rows(members["common", logical])[OLD] == rows(before["common", logical])[OLD]
        assert NEW in rows(members["common", logical])
    crow = core.read_csv_lines(core.read_orderedmap_file_from_bytes(members["common", T.CHAR])[NEW])[0]
    assert crow[0] == CODE and crow[8] == CODE and crow[27] == NEW
    assert crow[17] == NEW and crow[19:25] == [NEW + str(i) for i in range(1, 7)]
    assert len(servers) == len(preimages) == 5
    nodes = json.loads(servers["mana_node.json"])[NEW]["1"]
    assert set(nodes) == {str(int(NEW)*2000+1), str(int(NEW)*2000+2)}
    assert nodes[str(int(NEW)*2000+2)]["field5"] == str(int(NEW)*2000+1)
    for raw in servers.values():
        assert json.loads(raw)["other"] == {"preserve": True}
    assert source.view.files == before and source.table("character").get(NEW) is None
    assert ops.character(NEW)["code"] == CODE
    assert ops.portrait_info(NEW, "0")["geometry"]["face"] == [2.0, 2.0]


def test_reuse_skill_keeps_original_key_without_new_action_row(env):
    source, store, ops, server = env
    clone(ops, request(skill="reuse"))
    members = clone_members(source, store, store.load(NEW))
    assert ("common", T.ACTION) not in members
    row = core.read_csv_lines(core.read_orderedmap_file_from_bytes(members["common", T.CHAR])[NEW])[0]
    assert row[8] == "mother_skill"


@pytest.mark.parametrize("element", [-1, 6, True])
def test_element_outside_zero_to_five_is_rejected(env, element):
    source, store, ops, _ = env
    with pytest.raises(DraftError):
        clone(ops, request(element=element))
    assert store.load(NEW) is None


def test_speech_visibility_and_duplicate_identity_fail_before_writes(env):
    source, store, ops, _ = env
    source.view.files["common", T.SPEECH] = ordered({OLD: leaf([["0", "0", "0", "你好", "home/home_0"]])})
    with pytest.raises(DraftError, match="2265"):
        clone(ops, request())
    assert not store.directory(NEW).exists()
    with pytest.raises(DraftError, match="占用"):
        clone(ops, request(code="mother"))


def test_missing_special_actions_mark_draft_and_block_build(env):
    source, store, ops, server = env
    source.view.files["common", family_paths("mother", "special")[3]] = encode_tree({"sequences": []})
    result = clone(ops, request())
    assert not result["buildable"]
    with pytest.raises(DraftError, match="special_land"):
        compile_clone(source, store, store.load(NEW), server_dir=server)


def test_donor_drift_and_server_collision_rejected(env):
    source, store, ops, server = env
    clone(ops, request())
    (server / "character.json").write_text(json.dumps({NEW: {}}), encoding="utf-8")
    with pytest.raises(DraftError, match="已占用"):
        compile_clone(source, store, store.load(NEW), server_dir=server)
    source.view.files["common", T.SPEECH] += b"drift"
    with pytest.raises(DraftError, match="输入已变化"):
        clone_members(source, store, store.load(NEW))


def test_empty_scratch_promotes_into_new_formal_draft(env):
    source, store, ops, server = env
    from wf.studio.scratch import create
    create(ops, {"base": OLD, "name": "新角色", "element": "火", "slug": "new-character"})
    result = promote(ops, "scratch-new-character", to=NEW, code=CODE, server_dir=server)
    assert result["characterId"] == NEW
    assert store.load("scratch-new-character")["scratch"]["boundTo"]["characterId"] == NEW
    assert "scratch" not in store.load(NEW)
    assert len(compile_clone(source, store, store.load(NEW), server_dir=server)[1]) == 5

def test_scratch_with_pixel_edits_promotes_and_compiles(env):
    source, store, ops, server = env
    from wf.studio.scratch import create, ScratchDraftOps
    from wf.studio.pixel_workshop_ops import PixelWorkshop
    create(ops, {"base": OLD, "name": "像素角色", "element": "火", "slug": "painted"})
    shop = PixelWorkshop(ScratchDraftOps(ops, "scratch-painted"))
    shop.remap("scratch-painted", {"base": OLD, "families": ["pixelart"],
        "mapping": [{"from": "#a13b3b", "to": "#2266cc"}]})
    promote(ops, "scratch-painted", to=NEW, code=CODE, server_dir=server)
    draft = store.load(NEW)
    assert {c["kind"] for c in draft["changes"]} == {"character_clone", "pixel_family"}
    compiled = compile_clone(source, store, draft, server_dir=server)
    assert compiled[0]["common", family_paths(CODE, "pixelart")[0]] != source.view.files["common", family_paths("mother", "pixelart")[0]]


def test_real_build_delivery_check_and_unknown_compat(env, tmp_path):
    import zipfile
    from wf.view import ManifestView
    from wf.studio.deliver_bridge import build_draft
    from wf.check import check_file
    source, store, ops, server = env
    active = tmp_path / "active"
    active.mkdir()
    archive = active / "pinball-1.4.131-1.4.233-1-fixture.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        for (root, logical), raw in source.view.files.items():
            bundle.writestr(member_name(root, logical), raw)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"cdn_version": "1.4.233", "patches": [
        {"version": "1.4.233", "depends_on": "1.4.131", "chain": [archive.name], "type": "patch"}]}), encoding="utf-8")
    base = tmp_path / "store"
    base.mkdir()
    view = ManifestView("1.4.233", store=base, manifest=manifest, search_dirs=[active])
    source = StudioSource(view)
    ops = DraftOps(source, store=store, characters=ops.character_list)
    clone(ops, request(), server_dir=server)
    pathlist = tmp_path / "paths.txt"
    logicals = set()
    for item in store.load(NEW)["changes"][0]["files"]:
        logicals.add(item["logical"])
    pathlist.write_text("\n".join(sorted(logicals)), encoding="utf-8")
    result = build_draft(NEW, from_version="1.4.233", to_version="1.4.234", out=tmp_path / "build",
                         store=store, baseline_view=view, server_dir=server, pathlist=pathlist,
                         allow_unknown_client=True)
    assert result["ok"], result
    delivery = Path(result["delivery"])
    assert result["compat"] == "未确认"
    assert not any(check.get("blocking") for check in check_file(delivery / "delivery-manifest.json"))
    server_delta = json.loads((tmp_path / "build" / "inputs" / "changeset.json").read_text(encoding="utf-8"))["server_changes"]
    assert len(server_delta) == 5
    assert (delivery / "compat.json").is_file() and (delivery / "check.json").is_file()
    assert OLD in ops.source.table("character") and NEW not in ops.source.table("character")

def test_portrait_replacement_uses_existing_thirty_output_derivation(env, monkeypatch):
    import base64
    import io
    import numpy as np
    import wf_atf
    import wf_ui_derive_gate as gate
    from wf.studio.portrait import PortraitService
    from wf.studio.deliver_media import compile_media
    from wf.studio.clone_assets import checklist
    source, store, ops, server = env
    atlas = [{"n": "full_shot_illustration_setting_" + form, "x": int(form) * 2, "y": 0,
              "w": 2, "h": 4} for form in ("0", "1")]
    source.view.files["common", "character/mother/ui/illustration_setting_sprite_sheet.atlas.amf3.deflate"] = encode_tree(atlas)
    buf = io.BytesIO()
    Image.new("RGBA", (1024, 512)).save(buf, format="PNG")
    reference_atf = wf_atf.deflate(wf_atf.build_cutin_atf(buf.getvalue()))
    for form in ("0", "1"):
        source.view.files["android", f"character/mother/ui/skill_cutin_{form}.atf.deflate"] = reference_atf
    monkeypatch.setattr(PortraitService, "masks", lambda self, codes: {
        slot: np.full(tuple(reversed(gate.OFFICIAL_ICON_SIZES[slot])), 255, dtype=np.uint8)
        for slot in gate.SHAPE_SLOTS})
    clone(ops, request())
    image = Image.new("RGBA", (128, 256))
    image.paste((20, 180, 200, 255), (32, 16, 96, 240))
    output = io.BytesIO()
    image.save(output, format="PNG")
    for form in ("0", "1"):
        uploaded = ops.portrait_upload(NEW, form, base64.b64encode(output.getvalue()).decode("ascii"))
        template = uploaded["info"]["upload"]["template"]
        ops.portrait_save(NEW, {"form": form, "source": "upload", "template": template})
    draft = store.load(NEW)
    bound = ops_for(ops, NEW)
    media = compile_media(bound.source, store, draft)
    assert len(media.members) == 30
    assert {T.CHAR_IMAGE, T.TRIMMED, T.FULL_SHOT_ATTR} <= {logical for root, logical in media.members}
    assert sum(item["status"] == "derived" for item in checklist(draft)) >= 27
    compiled = compile_clone(source, store, draft, server_dir=server)
    assert all(compiled[0][key] == raw for key, raw in media.members.items())

def test_scratch_promote_default_code_and_missing_server_guard(env, tmp_path):
    from wf.studio.scratch import create
    source, store, ops, server = env
    create(ops, {"base": OLD, "name": "未命名角色", "element": "火", "slug": "default-code"})
    result = promote(ops, "scratch-default-code", to=NEW, server_dir=server)
    assert result["code"] == "default_code"
    with pytest.raises(DraftError, match="does not exist"):
        compile_clone(source, store, store.load(NEW), server_dir=tmp_path / "absent")


def test_missing_required_asset_is_pending_and_blocks_delivery(env):
    source, store, ops, server = env
    del source.view.files["medium", "character/mother/ui/square_0.png"]
    result = clone(ops, request())
    assert any(item["status"] == "pending" and item["logical"].endswith("square_0.png") for item in result["assets"])
    with pytest.raises(DraftError, match="square_0"):
        compile_clone(source, store, store.load(NEW), server_dir=server)


def test_foreign_mana_segment_in_other_draft_is_reserved(env):
    source, store, ops, _ = env
    from wf.studio.ids import check_id
    clone(ops, request())
    assert not check_id(source, "mana_node", NEW, drafts_root=store.root)["available"]
    # A second fresh ID cannot adopt the already reserved code.
    with pytest.raises(DraftError, match="占用"):
        clone(ops, {**request(), "to": "139989"})

@pytest.mark.parametrize("target", ["999999999", "00123"])
def test_node_overflow_and_leading_zero_ids_fail_without_write(env, target):
    source, store, ops, _ = env
    with pytest.raises(DraftError):
        clone(ops, {**request(), "to": target})
    assert not store.directory(target).exists()


def test_partial_special_family_is_pending_not_server_error(env):
    source, store, ops, server = env
    del source.view.files["common", family_paths("mother", "special")[2]]
    result = clone(ops, request())
    assert not result["buildable"]
    assert any(item["status"] == "pending" and "/special.frame" in item["logical"] for item in result["assets"])
    with pytest.raises(DraftError):
        compile_clone(source, store, store.load(NEW), server_dir=server)
