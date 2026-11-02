"""Repository reward regressions with shared synthetic fixtures."""
from __future__ import annotations

from rogue_rewards_support import *  # noqa: F403

class TestApiSurface(unittest.TestCase):
    def test_canonical_builder_api_exists(self):
        self.assertEqual((), MISSING_API)

    def test_task2_writer_api_exists(self):
        self.assertEqual((), MISSING_TASK2_API)

    def test_task3_asset_api_exists(self):
        self.assertEqual((), MISSING_TASK3_API)


class TestSourceAssets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._fixture_temp = tempfile.TemporaryDirectory()
        cls._fixture_dir = Path(cls._fixture_temp.name) / "valid-assets"
        write_valid_asset_set(cls._fixture_dir)

    @classmethod
    def tearDownClass(cls):
        cls._fixture_temp.cleanup()

    def setUp(self):
        self._test_temp = tempfile.TemporaryDirectory()
        self.asset_dir = Path(self._test_temp.name) / "assets"
        shutil.copytree(self._fixture_dir, self.asset_dir)

    def tearDown(self):
        self._test_temp.cleanup()

    def validate(self) -> dict[str, Path]:
        return require_task3("validate_source_assets")(
            self.asset_dir, rewards.WEAPONS
        )

    def test_valid_rgba_sources_are_returned_by_fixed_slug(self):
        sources = self.validate()

        self.assertEqual(
            [spec.image_slug for spec in rewards.WEAPONS], list(sources)
        )
        self.assertEqual(
            {
                spec.image_slug: self.asset_dir / f"{spec.image_slug}.png"
                for spec in rewards.WEAPONS
            },
            sources,
        )

    def test_client_native_20px_sources_are_accepted(self):
        for index, spec in enumerate(rewards.WEAPONS):
            color = (
                20 + (index * 37) % 220,
                20 + (index * 67) % 220,
                20 + (index * 97) % 220,
                255,
            )
            write_rgba_fixture(
                self.asset_dir / f"{spec.image_slug}.png",
                color=color,
                size=(20, 20),
                visible_box=(1, 1, 19, 19),
            )

        sources = self.validate()

        self.assertEqual(15, len(sources))

    def test_wrong_dimensions_are_rejected(self):
        spec = rewards.WEAPONS[0]
        write_rgba_fixture(
            self.asset_dir / f"{spec.image_slug}.png", size=(21, 20)
        )

        with self.assertRaises(ValueError):
            self.validate()

    def test_rgb_without_alpha_is_rejected(self):
        spec = rewards.WEAPONS[0]
        Image.new("RGB", (20, 20), (20, 40, 60)).save(
            self.asset_dir / f"{spec.image_slug}.png", format="PNG"
        )

        with self.assertRaises(ValueError):
            self.validate()

    def test_fully_opaque_image_is_rejected(self):
        spec = rewards.WEAPONS[0]
        write_rgba_fixture(
            self.asset_dir / f"{spec.image_slug}.png",
            visible_box=None,
            background=(20, 40, 60, 255),
        )

        with self.assertRaises(ValueError):
            self.validate()

    def test_fully_transparent_image_is_rejected(self):
        spec = rewards.WEAPONS[0]
        write_rgba_fixture(
            self.asset_dir / f"{spec.image_slug}.png", visible_box=None
        )

        with self.assertRaises(ValueError):
            self.validate()

    def test_edge_touching_visible_bounds_match_official_atlas_contract(self):
        spec = rewards.WEAPONS[0]
        write_rgba_fixture(
            self.asset_dir / f"{spec.image_slug}.png",
            visible_box=(0, 0, 20, 19),
        )

        sources = self.validate()

        self.assertIn(spec.image_slug, sources)

    def test_duplicate_sha256_content_is_rejected(self):
        first, second = rewards.WEAPONS[:2]
        shutil.copyfile(
            self.asset_dir / f"{first.image_slug}.png",
            self.asset_dir / f"{second.image_slug}.png",
        )

        with self.assertRaises(ValueError):
            self.validate()

    def test_missing_source_name_is_rejected(self):
        spec = rewards.WEAPONS[0]
        (self.asset_dir / f"{spec.image_slug}.png").unlink()

        with self.assertRaises(ValueError):
            self.validate()

    def test_unexpected_source_name_is_rejected(self):
        write_rgba_fixture(self.asset_dir / "unexpected.png")

        with self.assertRaises(ValueError):
            self.validate()

    def test_unexpected_non_png_file_is_rejected(self):
        (self.asset_dir / "unexpected.jpg").write_bytes(b"not an allowed asset")

        with self.assertRaisesRegex(ValueError, "unexpected"):
            self.validate()

    def test_unexpected_subdirectory_is_rejected(self):
        (self.asset_dir / "nested").mkdir()

        with self.assertRaisesRegex(ValueError, "unexpected"):
            self.validate()

    def test_non_png_bytes_are_rejected(self):
        spec = rewards.WEAPONS[0]
        (self.asset_dir / f"{spec.image_slug}.png").write_bytes(b"not a png")

        with self.assertRaises(ValueError):
            self.validate()

    def test_install_uses_only_png_magic_encoding_and_exact_hashed_paths(self):
        sources = self.validate()
        original = {slug: path.read_bytes() for slug, path in sources.items()}
        store = Path(self._test_temp.name) / "upload"

        installed = require_task3("install_source_assets")(
            store, sources, rewards.WEAPONS
        )

        expected = [
            rewards.q.hashed_rel(
                f"{rewards.IMAGE_PREFIX}/{spec.image_slug}.png"
            )
            for spec in rewards.WEAPONS
        ]
        self.assertEqual(expected, installed)
        self.assertEqual(
            len(rewards.WEAPONS),
            sum(1 for path in store.rglob("*") if path.is_file()),
        )
        for spec, relative in zip(rewards.WEAPONS, installed):
            with self.subTest(asset=spec.image_slug):
                source_bytes = original[spec.image_slug]
                stored_bytes = (store / relative).read_bytes()
                self.assertEqual(source_bytes, sources[spec.image_slug].read_bytes())
                self.assertEqual(wf_assets.png_encode(source_bytes), stored_bytes)
                self.assertEqual(source_bytes, wf_assets.png_decode(stored_bytes))

    def test_validate_assets_flag_reports_fixed_paths_without_touching_profile(self):
        output = io.StringIO()
        with (
            mock.patch.object(rewards, "SOURCE_ASSET_DIR", self.asset_dir),
            mock.patch.object(rewards, "require_cn_profile") as require_profile,
            mock.patch.object(rewards.q, "load_table") as load_table,
            mock.patch.object(sys, "argv", ["wf_rogue_rewards.py", "--validate-assets"]),
            contextlib.redirect_stdout(output),
        ):
            result = rewards.main()

        self.assertEqual(0, result)
        require_profile.assert_not_called()
        load_table.assert_not_called()
        report = output.getvalue()
        self.assertIn("15/15 valid", report)
        self.assertIn("15 distinct SHA-256", report)
        self.assertIn("item/equipment/mod/abyss/fire_01.png", report)
        self.assertIn("item/equipment/mod/abyss/universal_03.png", report)
