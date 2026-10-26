"""Synthetic alpha crops catch accidental backdrops without changing production defaults."""
import json

import numpy as np
import pytest
from PIL import Image

import wf_ui_derive_gate as gate
from wf.chars.support import images
from wf.studio.icon_alpha import FILL_CODE, cached_masks, inspect_icons, report
from wf.studio.portrait import PortraitService, default_template


@pytest.fixture
def artwork():
    master = Image.new("RGBA", (160, 180))
    master.paste((120, 80, 50, 255), (60, 15, 100, 160))
    template = default_template(master, [80, 45])
    template["squareHeight"] = 120
    masks = {slot: np.full((gate.OFFICIAL_ICON_SIZES[slot][1], gate.OFFICIAL_ICON_SIZES[slot][0]),
                          255, np.uint8) for slot in gate.SHAPE_SLOTS}
    return master, template, masks


def render(artwork):
    master, template, masks = artwork
    return PortraitService(None, None, None).render(master, template, masks, "test-alpha")


def test_studio_transparent_icons_preserve_exact_alpha_and_exclude_cutin(artwork):
    master, template, masks = artwork
    checks = inspect_icons(master, template, render(artwork), masks, form="0")
    assert len(checks) == 10 and all(c["status"] == "ok" and c["ratio"] == 0 for c in checks)
    assert "skill_cutin" not in {c["slot"] for c in checks}


def test_unrequested_backdrop_warns_and_explicit_author_backdrop_is_info(artwork):
    master, template, masks = artwork
    template["backdrop"] = {"inner": [150, 100, 40], "outer": [30, 20, 50]}
    icons = render(artwork)
    chosen = inspect_icons(master, template, icons, masks)
    assert all(c["code"] == FILL_CODE and c["level"] == "info" for c in chosen)
    assert all("作者选择了底色" in c["message"] for c in chosen)
    template["backdrop"] = None
    accidental = inspect_icons(master, template, icons, masks)
    assert all(c["code"] == FILL_CODE and c["level"] == "warn" for c in accidental)
    assert all(c["ratio"] > .98 and not c["blocking"] for c in accidental)


def test_shape_mask_exterior_is_not_counted(artwork):
    master, template, masks = artwork
    slot = "battle_member_status"
    masks[slot][:] = 0
    icons = render(artwork)
    icons[slot] = Image.new("RGBA", icons[slot].size, (1, 2, 3, 255))
    row = next(c for c in inspect_icons(master, template, icons, masks) if c["slot"] == slot)
    assert row["sourceTransparentPixels"] == row["filledPixels"] == 0
    assert row["status"] == "ok"


def test_threshold_uses_transparent_region_not_whole_icon():
    master = Image.new("RGBA", (100, 100), (20, 30, 40, 255))
    master.paste((0, 0, 0, 0), (0, 0, 10, 100))
    template = {"face": [50, 50], "squareHeight": 100, "groups": {}, "backdrop": None}
    size = gate.OFFICIAL_ICON_SIZES["square"]
    icon = images.crop_at(master, template["face"], 100, size, (.5, .5))
    pixels = np.array(icon)
    ys, xs = np.where(pixels[:, :, 3] < 128)
    count = len(xs)
    pixels[ys[:count // 100], xs[:count // 100], 3] = 255
    first = inspect_icons(master, template, {"square": Image.fromarray(pixels)}, {})[0]
    assert 0 < first["ratio"] < .02 and first["status"] == "ok"
    pixels[ys[:count // 20], xs[:count // 20], 3] = 255
    second = inspect_icons(master, template, {"square": Image.fromarray(pixels)}, {})[0]
    assert .04 < second["ratio"] < .06 and second["code"] == FILL_CODE


def test_missing_shape_masks_are_not_reported_as_pass(artwork):
    master, template, masks = artwork
    checks = inspect_icons(master, template, render(artwork), {})
    assert any(c["status"] == "skipped" and c["ratio"] is None for c in checks)
    assert report(checks)["status"] == "partial"
    assert report([])["status"] == "skipped"


def test_all_skipped_slots_report_skipped_not_warning():
    skipped = [{"code": "ICON_ALPHA_NOT_CHECKED", "level": "warn", "status": "skipped", "slot": "square"}]
    assert report(skipped)["status"] == "skipped"
    filled = skipped + [{"code": FILL_CODE, "level": "warn", "status": "warning", "slot": "thumb"}]
    assert report(filled)["status"] == "warning"


def test_mask_cache_integrity_is_required(tmp_path):
    from types import SimpleNamespace
    cache = tmp_path / "_cache/official-shape-masks.npz"
    cache.parent.mkdir()
    cache.write_bytes(b"corrupt")
    cache.with_suffix(".json").write_text(json.dumps({"sha256": "0" * 64}), "utf-8")
    with pytest.raises(ValueError, match="SHA-256"):
        cached_masks(SimpleNamespace(root=tmp_path))


def test_shared_production_default_still_paints_backdrop(artwork):
    master, _, masks = artwork
    icons = images.make_icons(master, {"face": [80, 45], "square_height": 120}, masks, "bianca")
    assert np.asarray(icons["square"])[:, :, 3].min() == 255


def test_icon_warning_survives_delivery_five_state_readback(artwork):
    from wf.deliver.client_compatibility import readback_draft_checks
    master, template, masks = artwork
    template["backdrop"] = {"inner": [120, 80, 30], "outer": [20, 10, 40]}
    icons = render(artwork)
    template["backdrop"] = None
    checks = inspect_icons(master, template, icons, masks)
    result = readback_draft_checks({"draft_checks": "draft-checks.json"},
                                  lambda _: (None, json.dumps(checks)))
    assert len(result) == 10
    assert all(c["rule"] == FILL_CODE and c["status"] == "待验证" and not c["blocking"] for c in result)
