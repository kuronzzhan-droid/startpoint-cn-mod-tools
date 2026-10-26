"""M4a.1 media counterexamples: existing slots, matching ATF, lean output and MP3."""
from __future__ import annotations

import pytest
from PIL import Image

import wf_assets
import wf_atf
from wf.studio.deliver_media import compile_media
from wf.studio.deliver_portrait import ATLAS, TABLES, geometry_key, leaf_value, replace_leaf
from wf.studio.drafts import DraftError, sha256

from test_studio_deliver_media import (
    CID, CODE, PREFIX, changeset, file_entry, portrait, standard_png,
)


def _atf_with_mips(raw, count):
    pairs = wf_atf.parse_atf(raw)["pairs"][:count]
    body = b"".join(bytes(8) + len(pair).to_bytes(4, "big") + pair + bytes(4) for pair in pairs)
    return raw[:8] + (4 + len(body)).to_bytes(4, "big") + raw[12:15] + bytes((count,)) + body


@pytest.mark.parametrize("suffix,root", [
    ("square_0.png", "medium"), ("skill_cutin_0.png", "medium"),
    ("full_shot_1440_1920_0.png", "medium"), ("skill_cutin_0.atf.deflate", "android"),
])
def test_portrait_rejects_missing_baseline_slot_even_with_null_preimage(portrait, suffix, root):
    source, store, build = portrait
    logical = PREFIX + "ui/" + suffix
    original = source.files.pop((root, logical))
    # A same-logical copy in another root cannot satisfy the missing slot.
    source.files["common", logical] = original
    change = build()
    with pytest.raises(DraftError, match="基线缺少"):
        compile_media(source, store, changeset([change]))


@pytest.mark.parametrize("difference", ["mips", "format"])
def test_portrait_rejects_draft_atf_that_differs_from_reference(portrait, difference):
    source, store, build = portrait
    change = build()
    logical = PREFIX + "ui/skill_cutin_0.atf.deflate"
    reference = bytearray(wf_atf.inflate(source.files["android", logical]))
    pixels = standard_png(Image.new("RGBA", (8, 4), (30, 50, 60, 255)))
    if difference == "mips":
        reference = _atf_with_mips(bytes(reference), reference[15] - 1)
        candidate = wf_atf.build_cutin_atf(pixels, reference)
    else:
        candidate = bytearray(wf_atf.build_cutin_atf(pixels, bytes(reference)))
        candidate[12] = 0x85  # Parser accepts the flag; delivery must still match it exactly.
        candidate = bytes(candidate)
    change["files"].append(file_entry(source, store, logical, wf_atf.deflate(candidate),
                                      "android", "atf-deflate"))
    with pytest.raises(DraftError, match="mip 数或格式"):
        compile_media(source, store, changeset([change]))


def test_portrait_accepts_matching_draft_atf_and_reference_mip_count(portrait):
    source, store, build = portrait
    logical = PREFIX + "ui/skill_cutin_0.atf.deflate"
    reference = bytearray(wf_atf.inflate(source.files["android", logical]))
    reference = _atf_with_mips(bytes(reference), 2)
    source.files["android", logical] = wf_atf.deflate(reference)
    change = build()
    candidate = wf_atf.deflate(wf_atf.build_cutin_atf(
        standard_png(Image.new("RGBA", (8, 4), (30, 50, 60, 255))), reference))
    change["files"].append(file_entry(source, store, logical, candidate, "android", "atf-deflate"))
    result = compile_media(source, store, changeset([change]))
    assert result.members["android", logical] == candidate
    change["files"].pop()
    generated = compile_media(source, store, changeset([change])).members["android", logical]
    assert wf_atf.parse_atf(wf_atf.inflate(generated))["mips"] == 2


@pytest.mark.parametrize("rewrite_length", [False, True])
def test_portrait_rejects_truncated_atf_even_when_metadata_matches(portrait, rewrite_length):
    source, store, build = portrait
    logical = PREFIX + "ui/skill_cutin_0.atf.deflate"
    raw = bytearray(wf_atf.inflate(source.files["android", logical])[:16])
    if rewrite_length:
        raw[8:12] = (4).to_bytes(4, "big")
    change = build()
    change["files"].append(file_entry(source, store, logical, wf_atf.deflate(bytes(raw)),
                                      "android", "atf-deflate"))
    with pytest.raises(DraftError, match="ATF"):
        compile_media(source, store, changeset([change]))


def test_portrait_unchanged_tables_do_not_rollback_intermediate_other_character(portrait):
    source, store, build = portrait
    change = build()
    change["params"]["tableRows"] = {
        table: leaf_value(source.files["common", logical], geometry_key(table, CID, CODE, "0"))
        for table, logical in TABLES.items()
    }
    result = compile_media(source, store, changeset([change]))
    assert all(("common", logical) not in result.members for logical in TABLES.values())
    assert ("common", PREFIX + ATLAS) not in result.members
    assert not any("_1." in logical for _, logical in result.members)
    assert all(raw != source.read_root(*key) for key, raw in result.members.items())

    intermediate = dict(source.files)
    logical = TABLES["character_image"]
    intermediate["common", logical] = replace_leaf(
        intermediate["common", logical], ("other", "0"), "unaltered\r\nleaf", "new other pivot")
    intermediate.update(result.members)
    assert leaf_value(intermediate["common", logical], ("other", "0")) == "new other pivot"


def test_portrait_unchanged_second_form_does_not_add_geometry_or_form_members(portrait):
    source, store, build = portrait
    first, second = build(), build("1")
    for entry in second["files"]:
        raw = wf_assets.png_decode(source.read_root(entry["root"], entry["logical"]))
        store.write_file(CID, entry["draft"], raw)
        entry.update(sha256=sha256(raw), size=len(raw), storeSha256=sha256(wf_assets.png_encode(raw)))
    second["params"]["tableRows"] = {}
    result = compile_media(source, store, changeset([first, second]))
    for table, logical in TABLES.items():
        assert leaf_value(result.members["common", logical], geometry_key(table, CID, CODE, "1")) == (
            leaf_value(source.files["common", logical], geometry_key(table, CID, CODE, "1")))
    assert not any("_1." in logical for _, logical in result.members)
