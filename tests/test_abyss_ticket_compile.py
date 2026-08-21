# -*- coding: utf-8 -*-
"""深渊扭蛋券数据与共享 item 图集编译器测试。"""
from __future__ import annotations

import copy
import hashlib
import io
import tempfile
import sys
import unittest
import zlib
from pathlib import Path
from unittest import mock

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import wf_mod_tool as core  # noqa: E402
import wf_assets  # noqa: E402
import wf_dsl  # noqa: E402

try:  # 首个 TDD 红灯要以断言失败表达“模块尚不存在”，而不是导入错误。
    import wf_abyss_ticket_compile as tickets  # noqa: E402
except ModuleNotFoundError:
    tickets = None


def _item_row(*, marker: str, item_id: str, name: str, icon: str, description: str,
              kind: str) -> list[str]:
    return [
        marker, item_id, name, icon, "(None)", description, "8", "", "", "", "",
        "", "", kind, "4", "(None)", "100", "5", "9999",
        "2015-12-31 23:59:59", "2199-12-31 23:59:59", "false", "",
    ]


def _item_fixture() -> dict[str, object]:
    single = _item_row(
        marker="wildcard_once_gacha_character_ticket",
        item_id="999003",
        name="通用角色单抽扭蛋券",
        icon="item/spends/tickets/wildcard_once_gacha_character_ticket",
        description="通用单抽券说明",
        kind="1",
    )
    multi = _item_row(
        marker="wildcard_ten_times_gacha_character_ticket",
        item_id="999001",
        name="通用角色十连扭蛋券",
        icon="item/spends/tickets/wildcard_ten_times_gacha_character_ticket",
        description="通用十连券说明",
        kind="2",
    )
    single[8] = "single-donor-sentinel"
    multi[8] = "multi-donor-sentinel"
    return {
        "7": "unrelated-low",
        "999003": core.write_csv_lines([single]),
        "999001": core.write_csv_lines([multi]).encode("utf-8"),
        "9000000": "unrelated-high",
    }


def _ticket_type_fixture() -> dict[str, object]:
    return {
        "1": core.write_csv_lines([["one_time_character", "角色扭蛋1回", "2"]]),
        "2": core.write_csv_lines([["ten_times_character", "角色扭蛋10回", "20"]]),
        "3": core.write_csv_lines([["one_time_equipment", "装备扭蛋1回", "3"]]),
    }


def _png_bytes(size: tuple[int, int], color: tuple[int, int, int, int]) -> bytes:
    output = io.BytesIO()
    Image.new("RGBA", size, color).save(output, format="PNG")
    return output.getvalue()


def _write_icon_sources(
    source_dir: Path,
    sizes: tuple[tuple[int, int], tuple[int, int]] = ((20, 20), (20, 20)),
) -> dict[str, str]:
    locks: dict[str, str] = {}
    colors = ((20, 220, 80, 255), (10, 140, 60, 255))
    for spec, size, color in zip(tickets.TICKETS, sizes, colors):
        payload = _png_bytes(size, color)
        (source_dir / spec.source_name).write_bytes(payload)
        locks[spec.source_name] = hashlib.sha256(payload).hexdigest()
    return locks


def _raw_deflate(payload: bytes) -> bytes:
    compressor = zlib.compressobj(level=9, wbits=-15)
    return compressor.compress(payload) + compressor.flush()


def _base_item_assets() -> tuple[bytes, bytes]:
    image = Image.new("RGBA", (60, 30), (0, 0, 0, 0))
    image.putpixel((1, 1), (240, 10, 20, 255))
    output = io.BytesIO()
    image.save(output, format="PNG")
    sheet = wf_assets.png_encode(output.getvalue())
    atlas = _raw_deflate(wf_dsl.encode_amf3([
        {"n": "item/base", "w": 2, "h": 2, "x": 1, "y": 1}
    ]))
    return sheet, atlas


def _decode_sheet(payload: bytes) -> Image.Image:
    with Image.open(io.BytesIO(wf_assets.png_decode(payload))) as image:
        image.load()
        return image.convert("RGBA")


def _decode_atlas(payload: bytes) -> list[dict]:
    tree = wf_dsl.parse_dsl(zlib.decompress(payload, -15))["tree"]
    if not isinstance(tree, list):
        raise AssertionError("atlas fixture did not decode to list")
    return tree


class TestTicketItemTable(unittest.TestCase):
    def test_clones_official_single_and_ten_donors_without_mutating_input(self):
        self.assertIsNotNone(tickets, "wf_abyss_ticket_compile 模块尚未实现")
        source = _item_fixture()
        original = copy.deepcopy(source)

        result = tickets.build_item_table(source)

        self.assertEqual(original, source)
        self.assertEqual("unrelated-low", result["7"])
        self.assertEqual("unrelated-high", result["9000000"])
        self.assertEqual(original["999003"], result["999003"])
        self.assertEqual(original["999001"], result["999001"])
        self.assertEqual(("999013", "999014"), tuple(result)[-2:])

        single = core.read_csv_lines(result["999013"])[0]
        multi = core.read_csv_lines(result["999014"].decode("utf-8"))[0]
        self.assertEqual(
            [
                "abyss_once_gacha_character_ticket",
                "999013",
                "深渊单抽券",
                "item/spends/tickets/abyss_once_gacha_character_ticket",
                "(None)",
                "可用于进行1次「深渊限定扭蛋」角色抽取的专用扭蛋券",
                "8", "", "single-donor-sentinel", "", "", "", "", "1", "4",
                "(None)", "100", "5", "9999", "2015-12-31 23:59:59",
                "2199-12-31 23:59:59", "false", "",
            ],
            single,
        )
        self.assertEqual(
            [
                "abyss_ten_times_gacha_character_ticket",
                "999014",
                "深渊十连券",
                "item/spends/tickets/abyss_ten_times_gacha_character_ticket",
                "(None)",
                "可用于进行1次「深渊限定扭蛋」角色10连抽取的专用扭蛋券",
                "8", "", "multi-donor-sentinel", "", "", "", "", "2", "4",
                "(None)", "100", "5", "9999", "2015-12-31 23:59:59",
                "2199-12-31 23:59:59", "false", "",
            ],
            multi,
        )

    def test_rejects_foreign_reserved_item_before_mutating_input(self):
        source = _item_fixture()
        source["999013"] = core.write_csv_lines([["foreign"]])
        original = copy.deepcopy(source)

        with self.assertRaisesRegex(ValueError, "999013"):
            tickets.build_item_table(source)

        self.assertEqual(original, source)

    def test_rejects_donor_when_official_ticket_kind_has_drifted(self):
        source = _item_fixture()
        row = core.read_csv_lines(source["999003"])[0]
        row[13] = "2"
        source["999003"] = core.write_csv_lines([row])

        with self.assertRaisesRegex(ValueError, "999003.*kind"):
            tickets.build_item_table(source)


class TestTicketTypeDependency(unittest.TestCase):
    def test_accepts_the_official_character_single_and_ten_type_rows(self):
        validator = getattr(tickets, "validate_ticket_type_table", None)
        self.assertIsNotNone(validator, "gacha_ticket_type 依赖校验尚未实现")

        validator(_ticket_type_fixture())

    def test_rejects_missing_or_drifted_character_ticket_types(self):
        missing = _ticket_type_fixture()
        missing.pop("2")
        with self.assertRaisesRegex(ValueError, "kind 2"):
            tickets.validate_ticket_type_table(missing)

        drifted = _ticket_type_fixture()
        drifted["1"] = core.write_csv_lines(
            [["one_time_equipment", "装备扭蛋1回", "3"]]
        )
        with self.assertRaisesRegex(ValueError, "kind 1"):
            tickets.validate_ticket_type_table(drifted)


class TestItemIdMirror(unittest.TestCase):
    def test_adds_both_ticket_ids_as_sorted_unique_integers(self):
        builder = getattr(tickets, "build_item_ids", None)
        self.assertIsNotNone(builder, "item_ids 镜像编译尚未实现")

        self.assertEqual(
            [7, 999013, 999014, 1000000],
            builder([1000000, "7", 999013, 7]),
        )


class TestItemAtlasCompiler(unittest.TestCase):
    def test_production_entrypoint_cannot_bypass_an_unset_source_lock(self):
        compiler = getattr(tickets, "compile_locked_item_assets", None)
        self.assertIsNotNone(compiler, "生产美术锁入口尚未实现")
        with mock.patch.object(tickets, "LOCKED_ICON_SHA256", {}):
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                compiler(b"not-reached", b"not-reached")

    def test_production_entrypoint_compiles_the_reviewed_ticket_art(self):
        sheet, atlas = _base_item_assets()

        try:
            result = tickets.compile_locked_item_assets(sheet, atlas)
        except ValueError as exc:
            self.fail(f"已验收票券美术尚未锁入生产入口: {exc}")

        self.assertEqual(
            {
                "abyss_once_gacha_character_ticket.png":
                    "bf6be3234d530c7f206c92fcc4f04544f9e6e102dd10a470766207ef5d168c50",
                "abyss_ten_times_gacha_character_ticket.png":
                    "f1a04683c0288783240064e65e5ff3c5f120bb6f89be4204774cd74645a7e454",
            },
            result.source_sha256,
        )

    def test_rejects_external_art_without_exact_sha256_locks(self):
        compiler = getattr(tickets, "compile_item_assets", None)
        self.assertIsNotNone(compiler, "共享 item 图集编译尚未实现")
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(ValueError, "SHA-256.*两张"):
                compiler(
                    b"not-read-before-lock-gate",
                    b"not-read-before-lock-gate",
                    Path(temp_dir),
                    expected_sha256={},
                )

    def test_rejects_a_source_whose_bytes_do_not_match_its_lock(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_dir = Path(temp_dir)
            for spec in tickets.TICKETS:
                (source_dir / spec.source_name).write_bytes(b"foreign-art")
            locks = {spec.source_name: "0" * 64 for spec in tickets.TICKETS}

            try:
                tickets.compile_item_assets(
                    b"base-sheet-not-reached",
                    b"base-atlas-not-reached",
                    source_dir,
                    expected_sha256=locks,
                )
            except Exception as exc:
                self.assertIsInstance(exc, ValueError)
                self.assertRegex(str(exc), "SHA-256.*abyss_once")
            else:
                self.fail("错误 SHA-256 锁未被拒绝")

    def test_rejects_external_art_that_is_not_exactly_20_by_20_rgba(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_dir = Path(temp_dir)
            locks = _write_icon_sources(source_dir, sizes=((21, 20), (20, 20)))

            try:
                tickets.compile_item_assets(
                    b"base-sheet-not-reached",
                    b"base-atlas-not-reached",
                    source_dir,
                    expected_sha256=locks,
                )
            except Exception as exc:
                self.assertIsInstance(exc, ValueError)
                self.assertRegex(str(exc), "20x20 RGBA.*abyss_once")
            else:
                self.fail("错误尺寸的券图标未被拒绝")

    def test_appends_two_exact_icons_without_rescaling_or_moving_existing_frames(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_dir = Path(temp_dir)
            locks = _write_icon_sources(source_dir)
            sheet_before, atlas_before = _base_item_assets()

            try:
                result = tickets.compile_item_assets(
                    sheet_before,
                    atlas_before,
                    source_dir,
                    expected_sha256=locks,
                )
            except NotImplementedError:
                self.fail("共享 item 图集成功路径尚未实现")

            self.assertEqual(locks, result.source_sha256)
            self.assertTrue(result.sheet_payload.startswith(wf_assets.PNG_FAKE))
            sheet = _decode_sheet(result.sheet_payload)
            self.assertEqual((60, 52), sheet.size)
            self.assertEqual((240, 10, 20, 255), sheet.getpixel((1, 1)))
            self.assertEqual((20, 220, 80, 255), sheet.getpixel((1, 31)))
            self.assertEqual((10, 140, 60, 255), sheet.getpixel((22, 31)))
            self.assertEqual((0, 0, 0, 0), sheet.getpixel((0, 30)))

            self.assertEqual(
                [
                    {"n": "item/base", "w": 2, "h": 2, "x": 1, "y": 1},
                    {
                        "n": "item/spends/tickets/abyss_once_gacha_character_ticket",
                        "w": 20, "h": 20, "x": 1, "y": 31,
                    },
                    {
                        "n": "item/spends/tickets/abyss_ten_times_gacha_character_ticket",
                        "w": 20, "h": 20, "x": 22, "y": 31,
                    },
                ],
                _decode_atlas(result.atlas_payload),
            )

    def test_second_compile_is_byte_idempotent_for_owned_frames(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_dir = Path(temp_dir)
            locks = _write_icon_sources(source_dir)
            sheet, atlas = _base_item_assets()
            first = tickets.compile_item_assets(
                sheet, atlas, source_dir, expected_sha256=locks
            )

            try:
                second = tickets.compile_item_assets(
                    first.sheet_payload,
                    first.atlas_payload,
                    source_dir,
                    expected_sha256=locks,
                )
            except ValueError as exc:
                self.fail(f"已拥有的规范图集帧未被识别为幂等状态: {exc}")

            self.assertEqual(first.sheet_payload, second.sheet_payload)
            self.assertEqual(first.atlas_payload, second.atlas_payload)
            self.assertEqual(first.source_sha256, second.source_sha256)

    def test_rejects_a_partial_owned_frame_set(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_dir = Path(temp_dir)
            locks = _write_icon_sources(source_dir)
            sheet, atlas = _base_item_assets()
            first = tickets.compile_item_assets(
                sheet, atlas, source_dir, expected_sha256=locks
            )
            partial_tree = _decode_atlas(first.atlas_payload)[:-1]
            partial_atlas = _raw_deflate(wf_dsl.encode_amf3(partial_tree))

            with self.assertRaisesRegex(ValueError, "部分"):
                tickets.compile_item_assets(
                    first.sheet_payload,
                    partial_atlas,
                    source_dir,
                    expected_sha256=locks,
                )

    def test_rejects_owned_frame_pixel_drift_instead_of_blessing_it(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_dir = Path(temp_dir)
            locks = _write_icon_sources(source_dir)
            sheet, atlas = _base_item_assets()
            first = tickets.compile_item_assets(
                sheet, atlas, source_dir, expected_sha256=locks
            )
            drifted = _decode_sheet(first.sheet_payload)
            drifted.putpixel((1, 31), (255, 0, 255, 255))
            output = io.BytesIO()
            drifted.save(output, format="PNG")
            drifted_payload = wf_assets.png_encode(output.getvalue())

            with self.assertRaisesRegex(ValueError, "像素漂移"):
                tickets.compile_item_assets(
                    drifted_payload,
                    first.atlas_payload,
                    source_dir,
                    expected_sha256=locks,
                )


if __name__ == "__main__":
    unittest.main()
