"""Stored media compilation, preimage drift and malformed-input counterexamples."""
from __future__ import annotations

from pathlib import Path

from PIL import Image
import pytest

import wf_assets
import wf_atf
import wf_mod_tool as core
import wf_ui_derive_gate as gate
from wf.studio.deliver_media import compile_media, encode_png, encode_tree, png, read_root
from wf.studio.deliver_portrait import TABLES, geometry_key, leaf_value, snapshot_geometry
from wf.studio.drafts import DraftError, DraftStore, sha256

CID, CODE = "139985", "demo"
PREFIX = f"character/{CODE}/"


class Source:
    version = "1.4.233"

    def __init__(self, files=None):
        self.files = files or {}

    def read_root(self, root, logical):
        return self.files.get((root, logical))

    def raw(self, logical):
        return next((self.files[r, logical] for r in ("common", "medium", "android")
                     if (r, logical) in self.files), None)


def changeset(changes):
    return {"characterId": CID, "code": CODE, "baseView": "1.4.233", "changes": changes}


def standard_png(image):
    return wf_assets.png_decode(encode_png(image))


def ordered(rows, nested=False):
    value = core.OrderedMap("test", list(rows), list(rows.values()), Path("test"))
    return core.build_orderedmap_raw_rows(value) if nested else core.build_orderedmap(value)


def file_entry(source, store, logical, data, root="medium", encoding="png", form="0"):
    relative = f"files/form{form}/{root}/{logical}"
    store.write_file(CID, relative, data)
    old = source.read_root(root, logical)
    entry = {"logical": logical, "root": root, "draft": relative, "sha256": sha256(data),
             "size": len(data), "encoding": encoding,
             "base": {"sha256": sha256(old) if old is not None else None, "layer": "test"}}
    if encoding == "png":
        entry["storeSha256"] = sha256(wf_assets.png_encode(data))
    elif encoding == "mp3":
        entry["storeSha256"] = sha256(wf_assets.mp3_encode(data))
    return entry


@pytest.fixture
def portrait(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "OFFICIAL_ICON_SIZES", {
        **{slot: (4, 4) for slot in gate.OFFICIAL_ICON_SIZES if slot != "skill_cutin"},
        "skill_cutin": (8, 4),
    })
    source, store = Source(), DraftStore(tmp_path / "drafts")
    for table, logical in TABLES.items():
        if table == "trimmed_image":
            rows = {geometry_key(table, CID, CODE, f)[0]: b"0,0,2000,2000" for f in ("0", "1")}
            rows["other"] = b"unaltered\r\nleaf"
            source.files["common", logical] = ordered(rows)
        else:
            row = b"0,0,8,8" if table == "character_image" else b"1000,1000,1,4,4"
            source.files["common", logical] = ordered({CID: ordered({"0": row, "1": row}),
                                                        "other": ordered({"0": b"unaltered\r\nleaf"})}, True)
    image = Image.new("RGBA", (8, 8), (40, 50, 60, 255))
    for form in ("0", "1"):
        source.files["medium", PREFIX + f"ui/full_shot_1440_1920_{form}.png"] = encode_png(image)
        for slot, size in gate.OFFICIAL_ICON_SIZES.items():
            source.files["medium", PREFIX + f"ui/{slot}_{form}.png"] = encode_png(Image.new("RGBA", size))
        source.files["android", PREFIX + f"ui/skill_cutin_{form}.atf.deflate"] = wf_atf.deflate(
            wf_atf.build_cutin_atf(standard_png(Image.new("RGBA", gate.OFFICIAL_ICON_SIZES["skill_cutin"]))))
    source.files["medium", PREFIX + "ui/illustration_setting_sprite_sheet.png"] = encode_png(
        Image.new("RGBA", (18, 8), (9, 8, 7, 255)))
    atlas = [{"n": "full_shot_illustration_setting_" + f, "x": int(f) * 9, "y": 0,
              "w": 8, "h": 8} for f in ("0", "1")]
    source.files["common", PREFIX + "ui/illustration_setting_sprite_sheet.atlas.amf3.deflate"] = encode_tree(atlas)

    def build(form="0", color=(255, 10, 20, 255)):
        entries = [file_entry(source, store, PREFIX + f"ui/{slot}_{form}.png",
                              standard_png(Image.new("RGBA", size, color)), form=form)
                   for slot, size in gate.OFFICIAL_ICON_SIZES.items()]
        entries.append(file_entry(source, store, PREFIX + f"ui/full_shot_1440_1920_{form}.png",
                                  standard_png(Image.new("RGBA", (8, 8), color)), form=form))
        return {"kind": "portrait", "target": {"form": form}, "files": entries,
                "params": {"source": "upload", "tableBefore": snapshot_geometry(source, CID, CODE, form),
                           "tableRows": {"character_image": "1,2,8,8", "trimmed_image": "1,2,2000,2000",
                                         "full_shot_image_attribute": "1000,1000,1,5,6"}},
                "pending": [], "checks": []}
    return source, store, build


def test_portrait_both_forms_and_geometry_preserve_unrelated_rows(portrait):
    source, store, build = portrait
    first, second = build(), build("1", (10, 250, 20, 255))
    result = compile_media(source, store, changeset([first, second]))
    assert len(result.members) == 30  # 2 * (full + 10 icons + cutin + ATF), sheet, 3 changed tables.
    assert ("common", PREFIX + "ui/illustration_setting_sprite_sheet.atlas.amf3.deflate") not in result.members
    sheet = png(result.members["medium", PREFIX + "ui/illustration_setting_sprite_sheet.png"])
    assert sheet.getpixel((0, 0)) == (255, 10, 20, 255)
    assert sheet.getpixel((9, 0)) == (10, 250, 20, 255)
    assert sheet.getpixel((8, 0)) == (9, 8, 7, 255)
    for form in ("0", "1"):
        atf = wf_atf.parse_atf(wf_atf.inflate(result.members["android", PREFIX + f"ui/skill_cutin_{form}.atf.deflate"]))
        assert (atf["w"], atf["h"]) == (8, 4)
        for table, logical in TABLES.items():
            assert leaf_value(result.members["common", logical], geometry_key(table, CID, CODE, form)) == first["params"]["tableRows"][table]
    for table, logical in TABLES.items():
        old = core.read_orderedmap_raw_rows_from_bytes(source.files["common", logical])
        new = core.read_orderedmap_raw_rows_from_bytes(result.members["common", logical])
        assert old.keys == new.keys
        assert old.rows[old.keys.index("other")] == new.rows[new.keys.index("other")]
    assert len(result.assertions) == 6


@pytest.mark.parametrize("mutation, expected", [
    ("table_drift", "旧值断言"), ("missing_before", "重新保存"), ("missing_icon", "缺少图标"),
    ("file_tamper", "SHA-256"), ("wrong_root", "错误根"), ("wrong_store_sha", "存储态 SHA"),
    ("missing_atlas", "基线缺少"), ("version", "基线版本"),
])
def test_portrait_rejects_counterexamples(portrait, mutation, expected):
    source, store, build = portrait
    change = build()
    doc = changeset([change])
    if mutation == "table_drift":
        logical = TABLES["character_image"]
        source.files["common", logical] = ordered({CID: ordered({"0": b"bad", "1": b"0,0,8,8"})}, True)
    elif mutation == "missing_before":
        change["params"].pop("tableBefore")
    elif mutation == "missing_icon":
        change["files"].pop(0)
    elif mutation == "file_tamper":
        store.write_file(CID, change["files"][0]["draft"], b"tampered")
    elif mutation == "wrong_root":
        change["files"][0]["root"] = "common"
    elif mutation == "wrong_store_sha":
        change["files"][0]["storeSha256"] = "0" * 64
    elif mutation == "missing_atlas":
        del source.files["common", PREFIX + "ui/illustration_setting_sprite_sheet.atlas.amf3.deflate"]
    elif mutation == "version":
        doc["baseView"] = "1.4.232"
    with pytest.raises((DraftError, ValueError), match=expected):
        compile_media(source, store, doc)


def test_portrait_current_omits_unchanged_fullshot_and_compiles_draft_atf(portrait):
    source, store, build = portrait
    change = build()
    full = PREFIX + "ui/full_shot_1440_1920_0.png"
    change["files"] = [entry for entry in change["files"] if entry["logical"] != full]
    change["params"]["source"] = "current"
    result = compile_media(source, store, changeset([change]))
    assert ("medium", full) not in result.members
    assert ("android", PREFIX + "ui/skill_cutin_0.atf.deflate") in result.members


def test_portrait_current_stored_file_preserves_original_png_signature(portrait):
    source, store, build = portrait
    full = PREFIX + "ui/full_shot_1440_1920_0.png"
    original = wf_assets.png_decode(source.files["medium", full])
    source.files["medium", full] = original
    change = build()
    change["files"] = [entry for entry in change["files"] if entry["logical"] != full]
    change["files"].append(file_entry(source, store, full, original))
    change["params"]["source"] = "current"
    result = compile_media(source, store, changeset([change]))
    assert ("medium", full) not in result.members
    assert source.files["medium", full] == original


def mp3_frame(bitrate=7):
    # MPEG1 Layer III, 96kbps, 44100Hz, mono; no codec is needed for header validation.
    header = bytes([255, 251, bitrate << 4, 192])
    size = int(144 * ({7: 96000, 9: 128000}[bitrate]) / 44100)
    return header + bytes(size - 4)


@pytest.fixture
def voice(tmp_path):
    source, store = Source(), DraftStore(tmp_path / "drafts")
    logical = PREFIX + "voice/home/home_0.mp3"
    source.files["common", logical] = wf_assets.mp3_encode(mp3_frame() * 3)
    raw = mp3_frame() * 4
    entry = file_entry(source, store, logical, raw, "common", "mp3")
    change = {"kind": "voice_line", "target": {"voice": "home/home_0"}, "files": [entry]}
    return source, store, change, raw


def test_voice_stored_replacement(voice):
    source, store, change, raw = voice
    result = compile_media(source, store, changeset([change]))
    output = result.members["common", change["files"][0]["logical"]]
    assert output == wf_assets.mp3_encode(raw)
    assert wf_assets.mp3_decode(output) == raw


@pytest.mark.parametrize("mutation", ["new_path", "wrong_target", "vbr", "truncated", "tampered", "wrong_store_sha"])
def test_voice_counterexamples(voice, mutation):
    source, store, change, raw = voice
    entry = change["files"][0]
    if mutation == "new_path":
        source.files.clear()
        entry["base"]["sha256"] = None
    elif mutation == "wrong_target":
        change["target"]["voice"] = "home/home_1"
    elif mutation in ("vbr", "truncated"):
        data = mp3_frame() + mp3_frame(9) if mutation == "vbr" else mp3_frame()[:-8]
        store.write_file(CID, entry["draft"], data)
        entry.update(sha256=sha256(data), size=len(data))
        entry.pop("storeSha256")
    elif mutation == "wrong_store_sha":
        entry["storeSha256"] = "0" * 64
    else:
        store.write_file(CID, entry["draft"], b"tamper")
    with pytest.raises((DraftError, ValueError)):
        compile_media(source, store, changeset([change]))


def test_exact_root_read_does_not_fallback():
    class View:
        def read_member(self, member):
            raise FileNotFoundError(member)
    source = Source({("common", "same"): b"wrong-root"})
    source.view = View()
    assert read_root(source, "android", "same") is None


def test_draft_file_maker_locks_exact_root_when_paths_overlap(tmp_path):
    from wf.studio.operations import DraftOps
    logical = PREFIX + "ui/square_0.png"
    common = encode_png(Image.new("RGBA", (4, 4), (1, 2, 3, 255)))
    medium = encode_png(Image.new("RGBA", (4, 4), (4, 5, 6, 255)))
    source = Source({("common", logical): common, ("medium", logical): medium})
    class Assets:
        def locate(self, path):
            return "test"
        def read(self, path):
            return common
    ops = DraftOps(source, store=DraftStore(tmp_path / "drafts"), assets=Assets())
    entry = ops._file_maker(CID)(logical, "medium", wf_assets.png_decode(medium), "png", approximate=False)
    assert entry["base"]["sha256"] == sha256(medium)


def test_portrait_saving_two_forms_has_no_shared_file_collision(portrait, monkeypatch):
    from wf.studio.operations import DraftOps
    from wf.studio.portrait import PortraitService, default_template
    source, store, _ = portrait
    class Assets:
        def read(self, logical):
            return source.raw(logical)
        def locate(self, logical):
            return "test"
    service = PortraitService(source, Assets(), store)
    monkeypatch.setattr(service, "masks", lambda _: {})
    monkeypatch.setattr(service, "render", lambda master, template, masks, role:
                        {slot: Image.new("RGBA", size, (1, 2, 3, 255))
                         for slot, size in gate.OFFICIAL_ICON_SIZES.items()})
    monkeypatch.setattr(gate, "derived_icon_problems", lambda *a, **k: [])
    ops = DraftOps(source, store=store, assets=Assets())
    built = []
    for form in ("0", "1"):
        image = png(source.raw(PREFIX + f"ui/full_shot_1440_1920_{form}.png"))
        built.append(service.build_change(cid=CID, code=CODE, element="", request={
            "form": form, "source": "current", "atf": False,
            "template": default_template(image, [4, 4])}, official_codes=[], make_file=ops._file_maker(CID)))
    assert set(f["draft"] for f in built[0]["files"]).isdisjoint(f["draft"] for f in built[1]["files"])
    for item in built:
        assert set(item["params"]["tableBefore"]) == set(TABLES)
        assert all(sha256(store.read_file(CID, f["draft"])) == f["sha256"] for f in item["files"])


def test_portrait_source_uses_exact_roots_despite_shadow_assets(portrait, monkeypatch):
    from wf.studio.operations import DraftOps
    from wf.studio.portrait import PortraitService, default_template
    source, store, _ = portrait
    full = PREFIX + "ui/full_shot_1440_1920_0.png"
    sheet = PREFIX + "ui/illustration_setting_sprite_sheet.png"
    atlas = PREFIX + "ui/illustration_setting_sprite_sheet.atlas.amf3.deflate"
    atf = PREFIX + "ui/skill_cutin_0.atf.deflate"
    # All four same-logical wrong-root copies would previously shadow the
    # production roots or make reference parsing fail.
    source.files["common", full] = encode_png(Image.new("RGBA", (4, 4)))
    source.files["common", sheet] = encode_png(Image.new("RGBA", (2, 2)))
    source.files["medium", atlas] = b"wrong-atlas-root"
    source.files["common", atf] = b"wrong-atf-root"
    source.files["android", atf] = wf_atf.deflate(wf_atf.build_cutin_atf(
        standard_png(Image.new("RGBA", (8, 4)))))
    class Assets:
        def read(self, logical):
            return source.raw(logical)
        def locate(self, logical):
            return "test"
    service = PortraitService(source, Assets(), store)
    assert service.view_full_shot(CODE, "0")[0].size == (8, 8)
    assert service.rebuild_sheet(CODE, "0", Image.new("RGBA", (8, 8))).size == (18, 8)
    monkeypatch.setattr(service, "masks", lambda _: {})
    monkeypatch.setattr(service, "render", lambda master, template, masks, role:
                        {slot: Image.new("RGBA", size, (1, 2, 3, 255))
                         for slot, size in gate.OFFICIAL_ICON_SIZES.items()})
    monkeypatch.setattr(gate, "derived_icon_problems", lambda *a, **k: [])
    ops = DraftOps(source, store=store, assets=Assets())
    built = service.build_change(cid=CID, code=CODE, element="", request={
        "form": "0", "source": "current", "atf": True,
        "template": default_template(Image.new("RGBA", (8, 8)), [4, 4])},
        official_codes=[], make_file=ops._file_maker(CID))
    assert not [c for c in built["checks"] if c["level"] == "error"]
    assert any(f["logical"] == atf and f["root"] == "android" for f in built["files"])
    result = compile_media(source, store, changeset([{**built, "kind": "portrait"}]))
    assert ("medium", full) not in result.members
