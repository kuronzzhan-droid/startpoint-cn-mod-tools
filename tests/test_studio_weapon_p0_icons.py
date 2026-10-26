"""P0 icon uploads preserve old atlas pixels and replay through local delivery."""
import base64
import copy
import io

from PIL import Image
import pytest

from test_boss_shop_weapon import state  # noqa: F401
from test_studio_weapon_routes import app, call  # noqa: F401
from wf.boss import schema as s
from wf.boss.shop_model import ITEM
from wf.studio.drafts import validate
from wf.studio.weapon_editor import compile_weapon
from wf.studio.weapon_icons import import_icon
from wf.tools.weapon.weapon_awaken import (ATLAS_MAP, ATLAS_PNG, decode_atlas, encode_atlas,
                                           open_png, store_png)


def png(size, color=(30, 80, 220, 255)):
    out = io.BytesIO()
    Image.new("RGBA", size, color).save(out, "PNG")
    return base64.b64encode(out.getvalue()).decode("ascii")


def atlas(files, size=(100, 100)):
    sheet = Image.new("RGBA", size, (0, 0, 0, 0))
    sheet.paste(Image.new("RGBA", (20, 20), (220, 30, 80, 255)), (1, 1))
    entries = [{"n": "existing", "w": 20, "h": 20, "x": 1, "y": 1}]
    files[ATLAS_PNG], files[ATLAS_MAP] = store_png(sheet), encode_atlas(entries)
    return sheet, entries


def test_weapon_standalone_import_keeps_donor_and_other_equipment(state):
    before = state.base.files["item/weapon.png"]
    report = import_icon(state, {"id": "5010005", "kind": "weapon", "png": png((20, 20))})
    row = s.parse_rows(state.table(s.EQUIPMENT)["5010005"])[0]
    assert row[6] + ".png" == report["logical"]
    assert open_png(state.client[report["logical"]]).size == (20, 20)
    assert state.base.files["item/weapon.png"] == before
    assert ATLAS_PNG not in state.client


@pytest.mark.parametrize("kind,item_id", [("soul", "5010005"), ("material", "1")])
def test_item_import_appends_atlas_without_changing_old_pixels(state, kind, item_id):
    sheet, entries = atlas(state.base.files)
    request = {"id": "5010005", "kind": kind, "png": png((40, 40))}
    if kind == "material":
        request["item_id"] = item_id
    report = import_icon(state, request)
    updated = open_png(state.client[ATLAS_PNG])
    added = decode_atlas(state.client[ATLAS_MAP])
    assert updated.size == sheet.size and added[:1] == entries and len(added) == 2
    assert updated.crop((1, 1, 21, 21)).tobytes() == sheet.crop((1, 1, 21, 21)).tobytes()
    entry = added[-1]
    masked = updated.copy()
    masked.paste(Image.new("RGBA", (40, 40)), (entry["x"], entry["y"]))
    assert masked.tobytes() == sheet.tobytes()
    item = s.parse_rows(state.table(ITEM)[item_id])[0]
    assert item[3] + ".png" == report["logical"] and item[4] == entry["n"]
    assert open_png(state.client[report["logical"]]).size == (20, 20)
    import_icon(state, request)
    assert len(decode_atlas(state.client[ATLAS_MAP])) == 2


@pytest.mark.parametrize("kind,size", [("weapon", (40, 40)), ("soul", (20, 20)), ("material", (20, 20))])
def test_icon_dimensions_fail_before_any_mutation(state, kind, size):
    before = copy.deepcopy(state.client)
    with pytest.raises(ValueError, match="single-frame"):
        import_icon(state, {"id": "5010005", "kind": kind, "png": png(size),
                            **({"item_id": "1"} if kind == "material" else {})})
    assert state.client == before


def test_atlas_full_rejects_without_expansion_or_writes(state):
    atlas(state.base.files, (30, 30))
    with pytest.raises(ValueError, match="no free 40x40"):
        import_icon(state, {"id": "5010005", "kind": "soul", "png": png((40, 40))})
    assert state.client == {}


def test_icon_http_preview_save_and_compile_replay_same_bytes(app):
    atlas(app.source.view.files)
    request = {"kind": "soul", "png": png((40, 40))}
    validate({"operation": "weapon_icon", "weapon": {"id": "5010005", **request}}, "weaponRequest")
    code, preview = call(app, "POST", "/5010005/icon", request, {"preview": ["true"]})
    assert code == 200 and preview["icons"][0]["preservedEntries"] == 1
    assert app.weapons.store.load("5010005") is None
    code, created = call(app, "POST", "/5010005/icon", request)
    assert code == 200 and created["subjectKind"] == "weapon"
    assert call(app, "POST", "/drafts/5010005/save", {})[0] == 200
    compiled = compile_weapon(app.source, app.weapons.store, created["changeset"],
                              server_dir=app.weapons.server_dir)
    assert ATLAS_PNG in compiled["client"] and ATLAS_MAP in compiled["client"]
    assert len(decode_atlas(compiled["client"][ATLAS_MAP])) == 2
    assert compiled["servers"] == {}


def test_icon_http_rejection_keeps_previous_draft(app):
    code, created = call(app, "POST", "/5010005/icon", {"kind": "weapon", "png": png((20, 20))})
    assert code == 200
    before = app.weapons.store.load("5010005")
    code, rejected = call(app, "POST", "/5010005/icon", {"kind": "weapon", "png": png((40, 40))})
    assert code == 400 and rejected["ok"] is False
    assert app.weapons.store.load("5010005") == before
