"""A's explicit banner/ticket APIs remain independent of the old product locks."""
import hashlib
import io
import zlib

from PIL import Image
import pytest

import wf_assets
import wf_dsl
import wf_abyss_gacha_banner_compile as banners
import wf_abyss_ticket_compile as tickets


def _png(size, color):
    buffer = io.BytesIO()
    Image.new("RGBA", size, color).save(buffer, format="PNG")
    return buffer.getvalue()


def _deflate(tree):
    compressor = zlib.compressobj(level=9, wbits=-15)
    return compressor.compress(wf_dsl.encode_amf3(tree)) + compressor.flush()


def test_banner_specs_allow_unrelated_assets_and_detect_source_drift(tmp_path):
    raw = _png((7, 3), (1, 20, 90, 255))
    source = tmp_path / "custom.png"
    source.write_bytes(raw)
    spec = banners.BannerSpec(source.name, hashlib.sha256(raw).hexdigest(), "custom/banner.png", (7, 3))
    result = banners.compile_banners(tmp_path, [spec])
    assert result.files == {spec.logical_path: wf_assets.png_encode(raw)}
    assert result.report["payload_count"] == 1
    source.write_bytes(_png((7, 3), (10, 2, 9, 255)))
    with pytest.raises(ValueError, match="SHA-256 drift"):
        banners.compile_banners(tmp_path, [spec])


def test_explicit_ticket_specs_preserve_donors_and_append_idempotently(tmp_path):
    spec = tickets.TicketSpec("321123", "20065", "custom_ticket", "Custom", "Description", "1", "item/custom", "custom.png")
    donor = ",".join(["old"] * 13 + ["1"]) + "\n"
    source_table = {"20065": donor, "unrelated": b"preserve me"}
    table = tickets.build_item_table(source_table, (spec,))
    assert source_table == {"20065": donor, "unrelated": b"preserve me"}
    assert set(table) == {"20065", "321123", "unrelated"}
    assert table["20065"] == donor and table["unrelated"] == b"preserve me"
    assert tickets.build_item_table(table, (spec,)) == table
    with pytest.raises(ValueError, match="321123"):
        tickets.build_item_table({**source_table, "321123": "occupied"}, (spec,))

    icon = _png((20, 20), (11, 22, 33, 255))
    (tmp_path / spec.source_name).write_bytes(icon)
    source_hashes = {spec.source_name: hashlib.sha256(icon).hexdigest()}
    original_sheet = wf_assets.png_encode(_png((64, 24), (80, 90, 100, 255)))
    original_tree = [{"n": "item/prior", "w": 20, "h": 20, "x": 1, "y": 1}]
    original_atlas = _deflate(original_tree)
    result = tickets.compile_item_assets(original_sheet, original_atlas, tmp_path,
                                        expected_sha256=source_hashes, specs=(spec,))
    atlas = wf_dsl.parse_dsl(zlib.decompress(result.atlas_payload, -15))["tree"]
    assert atlas == original_tree + [{"n": spec.icon_name, "w": 20, "h": 20, "x": 1, "y": 25}]
    with Image.open(io.BytesIO(wf_assets.png_decode(result.sheet_payload))) as image:
        assert image.size == (64, 46)
        assert image.crop((1, 25, 21, 45)).tobytes() == Image.open(io.BytesIO(icon)).tobytes()
        assert image.crop((0, 0, 64, 24)).tobytes() == Image.open(io.BytesIO(wf_assets.png_decode(original_sheet))).tobytes()
    again = tickets.compile_item_assets(result.sheet_payload, result.atlas_payload, tmp_path,
                                       expected_sha256=source_hashes, specs=(spec,))
    assert again == result


def test_ticket_compilers_require_explicit_specs(tmp_path):
    with pytest.raises(TypeError, match="specs"):
        tickets.build_item_table({})
    with pytest.raises(TypeError, match="specs"):
        tickets.compile_item_assets(b"", b"", tmp_path, expected_sha256={})
    assert not hasattr(tickets, "TICKETS")
    assert not hasattr(banners, "LOCKED_BANNERS")
