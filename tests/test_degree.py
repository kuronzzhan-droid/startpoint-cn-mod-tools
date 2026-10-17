from __future__ import annotations

import contextlib
import io
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


MOD_TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MOD_TOOLS))

import wf_assets  # noqa: E402
import wf_client_legality as legality  # noqa: E402
import wf_degree  # noqa: E402
import wf_mod_tool as core  # noqa: E402


CATEGORY_IDS = frozenset({"1", "2", "3", "4", "5", "6", "7", "8"})

BODY = (132, 193, 255, 255)
EDGE = (85, 133, 255, 255)
INK = (250, 250, 250, 255)
CLEAR = (255, 255, 255, 0)


def official_row(**overrides: str) -> list[str]:
    """一行合法的官方形态称号(取自 store 里 id=1 degree_default 的真实形状)。"""
    row = [
        "degree_default", "1", "周游世界之人", "せかいをわたるもの",
        "获得条件：从星见镇踏上旅途的证明", "1",
        legality.DEGREE_ICON_BASE_IMAGE, legality.DEGREE_ICON_DOT_IMAGE,
        "dynamic/degree/degree_default",
    ]
    for name, value in overrides.items():
        row[legality.DEGREE_COLUMNS[name]] = value
    return row


def synthetic_plate() -> bytes:
    """造一张与官方同构的 320×50 缎带:两端箭尾 + 纯色带 + 中间一段"文字"。"""
    from PIL import Image

    width, height = wf_degree.PLATE_SIZE
    image = Image.new("RGBA", (width, height), CLEAR)
    pixels = image.load()
    for x in range(width):
        for y in range(height):
            if y < 5 or y > 44:
                pixels[x, y] = CLEAR
            elif y > 39:
                pixels[x, y] = EDGE
            elif x < 14 or x > 305:
                pixels[x, y] = EDGE
            else:
                pixels[x, y] = BODY
    for x in range(100, 220):
        for y in range(15, 36):
            if (x + y) % 3:
                pixels[x, y] = INK
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def gradient_plate() -> bytes:
    """渐变缎带:没有可复制的纯色列,换字算法必须失败关闭而不是毁图。"""
    from PIL import Image

    width, height = wf_degree.PLATE_SIZE
    image = Image.new("RGBA", (width, height))
    pixels = image.load()
    for x in range(width):
        for y in range(height):
            pixels[x, y] = (x % 256, 128, 255 - (x % 256), 255)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def write_table(store: Path, logical: str, rows: dict[str, str]) -> None:
    ordered = core.OrderedMap(
        logical_path=logical,
        keys=list(rows),
        rows=[value.encode("utf-8") for value in rows.values()],
        source_path=Path("<memory>"),
    )
    target = core.table_path(store, logical)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(core.build_orderedmap(ordered))


def write_asset(store: Path, logical: str, data: bytes) -> None:
    target = core.table_path(store, logical)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(wf_assets.png_encode(data))


def make_store(root: Path, *, template: bytes | None = None) -> Path:
    store = root / "upload"
    store.mkdir(parents=True, exist_ok=True)
    write_table(store, wf_degree.DEGREE_LOGICAL, {
        "1": core.write_csv_lines([official_row()]),
        "1000": core.write_csv_lines([official_row(
            string_id="degree_player_rank_growth_1", display_order="100",
            name="渐入佳境", category_id="1",
            degree_image="dynamic/degree/degree_player_rank_growth_1",
        )]),
    })
    write_table(store, wf_degree.DEGREE_CATEGORY_LOGICAL, {
        "1": "player,玩家", "2": "character,角色", "3": "single_battle,角色",
        "4": "multi_battle,协力战斗", "5": "battle,战斗互通", "6": "equipment,装备",
        "7": "shop,商店", "8": "etc,其他",
    })
    write_asset(store, "dynamic/degree/degree_default.png",
                template if template is not None else synthetic_plate())
    write_asset(store, "dynamic/degree/degree_player_rank_growth_1.png", gradient_plate())
    return store


def make_db(path: Path) -> None:
    connection = sqlite3.connect(str(path))
    with connection:
        connection.execute("""
            CREATE TABLE players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                degree_id INTEGER NOT NULL
            )
        """)
        connection.execute("INSERT INTO players (id, name, degree_id) VALUES (8, 'zzhan', 1)")
        connection.execute("INSERT INTO players (id, name, degree_id) VALUES (9, 'alt', 1)")
    connection.close()


class DegreeRowLegalityTests(unittest.TestCase):
    def test_official_shaped_row_is_clean(self) -> None:
        self.assertEqual([], legality.degree_row_problems(
            official_row(), category_ids=CATEGORY_IDS))

    def test_short_row_is_rejected_before_any_other_check(self) -> None:
        problems = legality.degree_row_problems(
            official_row()[:8], category_ids=CATEGORY_IDS)
        self.assertEqual(1, len(problems))
        self.assertIn("列数=8", problems[0])
        self.assertIn("C8601", problems[0])

    def test_unknown_category_is_rejected(self) -> None:
        problems = legality.degree_row_problems(
            official_row(category_id="99"), category_ids=CATEGORY_IDS)
        self.assertTrue(any("F1009" in p for p in problems), problems)

    def test_non_numeric_category_is_rejected(self) -> None:
        problems = legality.degree_row_problems(
            official_row(category_id="etc"), category_ids=CATEGORY_IDS)
        self.assertTrue(any("c5" in p for p in problems), problems)

    def test_invented_icon_paths_are_rejected(self) -> None:
        problems = legality.degree_row_problems(
            official_row(icon_base_image="dynamic/degree/mod_background",
                         icon_dot_image="item/etc/mod_degree"),
            category_ids=CATEGORY_IDS)
        self.assertEqual(2, len(problems), problems)
        self.assertTrue(any(p.startswith("c6") for p in problems))
        self.assertTrue(any(p.startswith("c7") for p in problems))

    def test_degree_image_must_stay_under_the_official_prefix(self) -> None:
        for value in ("dynamic/mod_degree/x", "item/etc/x", "degree_x"):
            with self.subTest(value=value):
                problems = legality.degree_row_problems(
                    official_row(degree_image=value), category_ids=CATEGORY_IDS)
                self.assertTrue(any(p.startswith("c8") for p in problems), problems)

    def test_degree_image_must_not_carry_the_extension(self) -> None:
        problems = legality.degree_row_problems(
            official_row(degree_image="dynamic/degree/degree_x.png"),
            category_ids=CATEGORY_IDS)
        self.assertTrue(any("png.png" in p for p in problems), problems)

    def test_degree_image_must_stay_single_level(self) -> None:
        problems = legality.degree_row_problems(
            official_row(degree_image="dynamic/degree/mod/degree_x"),
            category_ids=CATEGORY_IDS)
        self.assertTrue(any("子目录" in p for p in problems), problems)

    def test_newline_in_a_cell_is_rejected(self) -> None:
        problems = legality.degree_row_problems(
            official_row(name="断轮的\n原勇者"), category_ids=CATEGORY_IDS)
        self.assertTrue(any("换行" in p for p in problems), problems)

    def test_display_order_and_name_are_required(self) -> None:
        problems = legality.degree_row_problems(
            official_row(display_order="", name=""), category_ids=CATEGORY_IDS)
        self.assertTrue(any(p.startswith("c1") for p in problems), problems)
        self.assertTrue(any(p.startswith("c2") for p in problems), problems)


class _StoreCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.store = make_store(self.root)
        self.work = self.root / "work"
        self.work.mkdir(parents=True, exist_ok=True)
        self._saved = (wf_degree.WORK, wf_degree.PENDING, wf_degree.CHANGELOG)
        wf_degree.WORK = self.work
        wf_degree.PENDING = self.work / "sync_pending.json"
        wf_degree.CHANGELOG = self.work / "changelog.jsonl"
        self.addCleanup(self._restore)

    def _restore(self) -> None:
        wf_degree.WORK, wf_degree.PENDING, wf_degree.CHANGELOG = self._saved

    def run_tool(self, *argv: str) -> int:
        # 工具是给人看的,print 很多;测试里收进 buffer,失败时再打出来。
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            code = wf_degree.main(list(argv))
        self.last_output = buffer.getvalue()
        return code

    def degree_table(self) -> core.OrderedMap:
        return core.load_table(wf_degree.DEGREE_LOGICAL, self.store)

    def pending(self) -> list[str]:
        return json.loads(wf_degree.PENDING.read_text(encoding="utf-8"))


class AllocationTests(_StoreCase):
    def test_first_custom_id_and_order_come_from_the_custom_band(self) -> None:
        table = self.degree_table()
        self.assertEqual(str(wf_degree.CUSTOM_ID_MIN), wf_degree.next_free_id(table))
        self.assertEqual(str(wf_degree.CUSTOM_ORDER_MIN), wf_degree.next_free_order(table))

    def test_allocation_skips_ids_and_orders_already_in_the_table(self) -> None:
        write_table(self.store, wf_degree.DEGREE_LOGICAL, {
            "1": core.write_csv_lines([official_row()]),
            str(wf_degree.CUSTOM_ID_MIN): core.write_csv_lines([official_row(
                string_id="degree_mod_a", display_order=str(wf_degree.CUSTOM_ORDER_MIN),
                degree_image="dynamic/degree/degree_mod_a")]),
        })
        table = self.degree_table()
        self.assertEqual(str(wf_degree.CUSTOM_ID_MIN + 1), wf_degree.next_free_id(table))
        self.assertEqual(str(wf_degree.CUSTOM_ORDER_MIN + 1),
                         wf_degree.next_free_order(table))

    def test_find_key_accepts_id_or_string_id(self) -> None:
        table = self.degree_table()
        self.assertEqual("1", wf_degree.find_key(table, "1"))
        self.assertEqual("1", wf_degree.find_key(table, "degree_default"))
        with self.assertRaises(wf_degree.DegreeError):
            wf_degree.find_key(table, "degree_nope")


class PlateTests(_StoreCase):
    def setUp(self) -> None:
        super().setUp()
        try:
            self.font = wf_degree.resolve_font(None)
        except wf_degree.DegreeError as error:  # pragma: no cover - 取决于本机字体
            self.skipTest(str(error))

    def test_cloned_plate_keeps_official_geometry_and_loses_the_old_text(self) -> None:
        from PIL import Image

        data, report = wf_degree.build_plate(
            self.store, "断轮的原勇者", template="1", font_path=self.font,
            hue=0.0, saturation=1.0, value=1.0)
        self.assertEqual([], wf_degree.check_plate_bytes(data))
        self.assertEqual([14, 305], report["writable_span"])
        self.assertEqual([15, 35], report["text_band"])
        with Image.open(io.BytesIO(data)) as image:
            self.assertEqual(wf_degree.PLATE_SIZE, image.size)
            pixels = image.convert("RGBA").load()
            # 模板的"文字"是 (x+y)%3 的散点;抹字后可覆写区里不该再有它的痕迹
            stray = [
                (x, y)
                for y in range(15, 36) for x in range(230, 300)
                if pixels[x, y] != BODY
            ]
            self.assertEqual([], stray)

    def test_recolor_leaves_the_white_text_alone(self) -> None:
        from PIL import Image

        data, _ = wf_degree.build_plate(
            self.store, "测试", template="1", font_path=self.font,
            hue=120.0, saturation=1.0, value=1.0)
        with Image.open(io.BytesIO(data)) as image:
            colors = {c for _, c in image.convert("RGBA").getcolors(65536)}
        self.assertIn(INK, colors)          # 文字色 S≈0,色相旋转不动它
        self.assertNotIn(BODY, colors)      # 缎带确实换了颜色

    def test_gradient_template_fails_closed(self) -> None:
        with self.assertRaises(wf_degree.DegreeError) as caught:
            wf_degree.build_plate(
                self.store, "测试", template="1000", font_path=self.font,
                hue=0.0, saturation=1.0, value=1.0)
        self.assertIn("--image", str(caught.exception))

    def test_overlong_title_is_refused_rather_than_clipped(self) -> None:
        with self.assertRaises(wf_degree.DegreeError) as caught:
            wf_degree.build_plate(
                self.store, "断" * 60, template="1", font_path=self.font,
                hue=0.0, saturation=1.0, value=1.0)
        self.assertIn("塞不下", str(caught.exception))

    def test_plate_size_is_enforced(self) -> None:
        from PIL import Image

        buffer = io.BytesIO()
        Image.new("RGBA", (320, 64), BODY).save(buffer, format="PNG")
        problems = wf_degree.check_plate_bytes(buffer.getvalue())
        self.assertTrue(any("320×50" in p for p in problems), problems)

    def test_store_magic_bytes_are_not_accepted_as_input(self) -> None:
        problems = wf_degree.check_plate_bytes(wf_assets.png_encode(synthetic_plate()))
        self.assertTrue(any("魔数" in p for p in problems), problems)


class CreateTests(_StoreCase):
    def setUp(self) -> None:
        super().setUp()
        try:
            wf_degree.resolve_font(None)
        except wf_degree.DegreeError as error:  # pragma: no cover
            self.skipTest(str(error))

    def create(self, *extra: str) -> int:
        return self.run_tool(
            "create", "--store", str(self.store),
            "--name", "断轮的原勇者", "--slug", "broken_wheel_hero", *extra)

    def test_dry_run_touches_nothing(self) -> None:
        before = core.table_path(self.store, wf_degree.DEGREE_LOGICAL).read_bytes()
        self.assertEqual(0, self.create("--dry-run"))
        self.assertEqual(
            before, core.table_path(self.store, wf_degree.DEGREE_LOGICAL).read_bytes())
        self.assertFalse(wf_degree.PENDING.exists())
        self.assertFalse(wf_degree.CHANGELOG.exists())

    def test_create_writes_row_asset_and_pending(self) -> None:
        self.assertEqual(0, self.create())
        key = str(wf_degree.CUSTOM_ID_MIN)
        table = self.degree_table()
        self.assertIn(key, table.keys)
        row = wf_degree.row_of(table, key)
        self.assertEqual("断轮的原勇者", row[legality.DEGREE_COLUMNS["name"]])
        self.assertEqual("dynamic/degree/degree_mod_broken_wheel_hero",
                         row[legality.DEGREE_COLUMNS["degree_image"]])
        self.assertEqual([], legality.degree_row_problems(row, category_ids=CATEGORY_IDS))

        asset = core.table_path(
            self.store, "dynamic/degree/degree_mod_broken_wheel_hero.png")
        self.assertTrue(asset.is_file())
        # store 里的 PNG 魔数必须是小写 \x89png
        self.assertEqual(wf_assets.PNG_FAKE, asset.read_bytes()[:8])

        pending = self.pending()
        self.assertEqual(2, len(pending), pending)
        for logical in (wf_degree.DEGREE_LOGICAL,
                        "dynamic/degree/degree_mod_broken_wheel_hero.png"):
            digest = core.sha1_path(logical)
            self.assertIn(f"{digest[:2]}/{digest[2:]}", pending)

        entries = [json.loads(line) for line in
                   wf_degree.CHANGELOG.read_text(encoding="utf-8").splitlines() if line]
        self.assertEqual(1, len(entries))
        self.assertEqual("degree", entries[0]["table"])
        self.assertEqual([key], entries[0]["keys"])
        self.assertIsNone(entries[0]["version"])

    def test_create_does_not_disturb_the_existing_rows(self) -> None:
        before = self.degree_table().text_rows()
        self.assertEqual(0, self.create())
        after = self.degree_table().text_rows()
        for key, value in before.items():
            self.assertEqual(value, after[key])

    def test_verify_passes_on_what_create_made(self) -> None:
        self.assertEqual(0, self.create())
        self.assertEqual(0, self.run_tool("verify", "--store", str(self.store)))

    def test_verify_fails_when_the_plate_is_gone(self) -> None:
        self.assertEqual(0, self.create())
        core.table_path(
            self.store, "dynamic/degree/degree_mod_broken_wheel_hero.png").unlink()
        self.assertEqual(1, self.run_tool("verify", "--store", str(self.store)))

    def test_official_id_band_is_refused_without_the_explicit_flag(self) -> None:
        self.assertEqual(2, self.create("--id", "60000"))
        self.assertNotIn("60000", self.degree_table().keys)

    def test_duplicate_id_is_refused_without_replace(self) -> None:
        self.assertEqual(0, self.create())
        key = str(wf_degree.CUSTOM_ID_MIN)
        self.assertEqual(2, self.run_tool(
            "create", "--store", str(self.store), "--name", "另一个",
            "--slug", "other", "--id", key))

    def test_image_path_collision_is_refused(self) -> None:
        self.assertEqual(2, self.run_tool(
            "create", "--store", str(self.store), "--name", "撞图",
            "--slug", "x", "--image-name", "degree_default"))

    def test_supplied_image_must_be_the_official_size(self) -> None:
        from PIL import Image

        wrong = self.root / "wrong.png"
        Image.new("RGBA", (200, 40), BODY).save(wrong)
        self.assertEqual(2, self.run_tool(
            "create", "--store", str(self.store), "--name", "尺寸不对",
            "--slug", "bad", "--image", str(wrong)))
        self.assertNotIn(str(wf_degree.CUSTOM_ID_MIN), self.degree_table().keys)

    def test_supplied_image_is_used_verbatim(self) -> None:
        source = self.root / "custom.png"
        source.write_bytes(synthetic_plate())
        self.assertEqual(0, self.run_tool(
            "create", "--store", str(self.store), "--name", "自带整图",
            "--slug", "byo", "--image", str(source)))
        stored = core.table_path(self.store, "dynamic/degree/degree_mod_byo.png")
        self.assertEqual(source.read_bytes(), wf_assets.png_decode(stored.read_bytes()))


class GrantTests(_StoreCase):
    def setUp(self) -> None:
        super().setUp()
        self.db = self.root / "wdfp_data.db"
        make_db(self.db)
        # 默认让"是否已发布"检查处于"读不到链、无法判断"状态,单测不依赖本机 CDN
        self._saved_published = wf_degree.published_degree_keys
        wf_degree.published_degree_keys = lambda: None
        self.addCleanup(setattr, wf_degree, "published_degree_keys",
                        self._saved_published)
        write_table(self.store, wf_degree.DEGREE_LOGICAL, {
            "1": core.write_csv_lines([official_row()]),
            "9900001": core.write_csv_lines([official_row(
                string_id="degree_mod_broken_wheel_hero", display_order="990000",
                name="断轮的原勇者", category_id="8",
                degree_image="dynamic/degree/degree_mod_broken_wheel_hero")]),
            "9900002": core.write_csv_lines([official_row(
                string_id="degree_mod_broken", display_order="990001",
                name="坏行", category_id="404",
                degree_image="dynamic/degree/degree_mod_broken")]),
        })

    def owned(self, player_id: int) -> list[int]:
        connection = wf_degree.open_db(self.db)
        try:
            return wf_degree.owned_degrees(connection, player_id)
        finally:
            connection.close()

    def worn(self, player_id: int) -> int:
        connection = sqlite3.connect(str(self.db))
        try:
            return connection.execute(
                "SELECT degree_id FROM players WHERE id = ?", (player_id,)).fetchone()[0]
        finally:
            connection.close()

    def grant(self, *extra: str) -> int:
        return self.run_tool(
            "grant", "--store", str(self.store), "--db", str(self.db),
            "--player", "8", "--degree", "9900001", *extra)

    def test_dry_run_writes_nothing(self) -> None:
        self.assertEqual(0, self.grant("--wear", "--dry-run"))
        self.assertEqual([], self.owned(8))
        self.assertEqual(1, self.worn(8))

    def test_grant_records_ownership_without_forcing_it_on(self) -> None:
        self.assertEqual(0, self.grant())
        self.assertEqual([9900001], self.owned(8))
        self.assertEqual(1, self.worn(8))

    def test_wear_updates_the_player_row(self) -> None:
        self.assertEqual(0, self.grant("--wear"))
        self.assertEqual([9900001], self.owned(8))
        self.assertEqual(9900001, self.worn(8))

    def test_grant_is_idempotent(self) -> None:
        self.assertEqual(0, self.grant())
        self.assertEqual(0, self.grant())
        self.assertEqual([9900001], self.owned(8))

    def test_grant_accepts_a_string_id_and_a_player_name(self) -> None:
        self.assertEqual(0, self.run_tool(
            "grant", "--store", str(self.store), "--db", str(self.db),
            "--player", "zzhan", "--degree", "degree_mod_broken_wheel_hero"))
        self.assertEqual([9900001], self.owned(8))

    def test_grant_refuses_a_row_that_would_crash_the_client(self) -> None:
        self.assertEqual(2, self.run_tool(
            "grant", "--store", str(self.store), "--db", str(self.db),
            "--player", "8", "--degree", "9900002"))
        self.assertEqual([], self.owned(8))

    def test_grant_refuses_a_degree_that_is_not_on_the_chain_yet(self) -> None:
        wf_degree.published_degree_keys = lambda: {"1", "1000"}
        self.assertEqual(2, self.grant())
        self.assertIn("还没发布", self.last_output)
        self.assertEqual([], self.owned(8))

    def test_allow_unpublished_overrides_the_chain_gate(self) -> None:
        wf_degree.published_degree_keys = lambda: {"1", "1000"}
        self.assertEqual(0, self.grant("--allow-unpublished"))
        self.assertEqual([9900001], self.owned(8))

    def test_grant_proceeds_once_the_degree_is_on_the_chain(self) -> None:
        wf_degree.published_degree_keys = lambda: {"1", "9900001"}
        self.assertEqual(0, self.grant())
        self.assertEqual([9900001], self.owned(8))

    def test_unknown_player_is_refused(self) -> None:
        self.assertEqual(2, self.run_tool(
            "grant", "--store", str(self.store), "--db", str(self.db),
            "--player", "nobody", "--degree", "9900001"))

    def test_revoke_removes_ownership_and_falls_back_to_the_default_title(self) -> None:
        self.assertEqual(0, self.grant("--wear"))
        self.assertEqual(0, self.run_tool(
            "revoke", "--db", str(self.db), "--player", "8", "--degree", "9900001"))
        self.assertEqual([], self.owned(8))
        self.assertEqual(1, self.worn(8))

    def test_revoke_leaves_other_players_alone(self) -> None:
        self.assertEqual(0, self.grant())
        self.assertEqual(0, self.run_tool(
            "grant", "--store", str(self.store), "--db", str(self.db),
            "--player", "9", "--degree", "9900001"))
        self.assertEqual(0, self.run_tool(
            "revoke", "--db", str(self.db), "--player", "8", "--degree", "9900001"))
        self.assertEqual([], self.owned(8))
        self.assertEqual([9900001], self.owned(9))


if __name__ == "__main__":
    unittest.main()
