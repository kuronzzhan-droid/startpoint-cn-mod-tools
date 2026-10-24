# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD_SCRIPT = REPO_ROOT / "work" / "seris_v2" / "integration" / "build_candidate.py"
SOURCE_PACKAGE = (
    REPO_ROOT
    / ".worktrees"
    / "seris-dual-form"
    / "work"
    / "sfix159"
    / "seris_dragon_king"
    / "package"
)
ROUTE_C_FULL = REPO_ROOT / "work" / "seris_v2" / "authoring" / "pixel_route_c" / "full"
PIXEL_ROOT = Path("roots/common/character/seris_dragon_king/pixelart")
FORMS = {
    "human": {
        "count": 68,
        "source_dir": "human",
        "sheet": "sprite_sheet.png",
        "atlas": "sprite_sheet.atlas.amf3.deflate",
        "frame": "pixelart.frame.amf3.deflate",
        "timeline": "pixelart.timeline.amf3.deflate",
    },
    "dragon": {
        "count": 92,
        "source_dir": "dragon",
        "sheet": "special_sprite_sheet.png",
        "atlas": "special_sprite_sheet.atlas.amf3.deflate",
        "frame": "special.frame.amf3.deflate",
        "timeline": "special.timeline.amf3.deflate",
    },
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestSerisIntegrationRouteC(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        spec = importlib.util.spec_from_file_location("seris_integration_route_c", BUILD_SCRIPT)
        if spec is None or spec.loader is None:
            raise AssertionError(f"cannot load build script: {BUILD_SCRIPT}")
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)
        cls.temp = tempfile.TemporaryDirectory(prefix="seris-phase2-step2-test-")
        integration = Path(cls.temp.name) / "integration"
        cls.output = integration / "seris_dragon_king"
        cls.evidence = integration / "evidence" / "phase2_step2.json"
        cls.report = cls.module.build_candidate(
            SOURCE_PACKAGE,
            cls.output,
            cls.evidence,
            allowed_output_root=integration,
            route_c_full=ROUTE_C_FULL,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()

    def test_two_clean_route_c_builds_are_identical_and_sources_are_read_only(self) -> None:
        report = self.report
        self.assertEqual("phase2_step2", report["phase"])
        self.assertTrue(report["reproducible"])
        self.assertTrue(report["source_unchanged"])
        self.assertTrue(report["route_c_source_unchanged"])
        self.assertEqual(report["build_a"]["path_sha256"], report["build_b"]["path_sha256"])
        self.assertEqual(report["build_b"]["path_sha256"], report["final"]["path_sha256"])
        self.assertEqual(report, json.loads(self.evidence.read_text(encoding="utf-8")))

    def test_timelines_are_byte_exact_to_the_installed_baseline(self) -> None:
        audit = self.report["route_c_audit"]
        for form, config in FORMS.items():
            timeline = audit["forms"][form]["timeline"]
            self.assertTrue(timeline["authoring_byte_exact_baseline"])
            self.assertTrue(timeline["candidate_byte_exact_baseline"])
            self.assertEqual(timeline["baseline_sha256"], timeline["authoring_sha256"])
            self.assertEqual(timeline["baseline_sha256"], timeline["candidate_sha256"])
            self.assertEqual(
                (SOURCE_PACKAGE / PIXEL_ROOT / config["timeline"]).read_bytes(),
                (self.output / PIXEL_ROOT / config["timeline"]).read_bytes(),
            )

    def test_atlas_and_frame_key_sets_match_the_real_baseline(self) -> None:
        for form, config in FORMS.items():
            form_audit = self.report["route_c_audit"]["forms"][form]
            atlas = form_audit["atlas"]
            frame = form_audit["frame"]
            self.assertEqual(config["count"], atlas["expected_count"])
            self.assertEqual(config["count"], atlas["baseline_count"])
            self.assertEqual(config["count"], atlas["authoring_count"])
            self.assertEqual(config["count"], atlas["candidate_count"])
            self.assertTrue(atlas["same_key_set"])
            self.assertEqual(atlas["baseline_keys"], atlas["authoring_keys"])
            self.assertEqual(atlas["baseline_keys"], atlas["candidate_keys"])
            self.assertTrue(frame["same_key_set"])
            self.assertEqual(frame["baseline_keys"], frame["authoring_keys"])
            self.assertEqual(frame["baseline_keys"], frame["candidate_keys"])
            self.assertEqual(6, frame["baseline_scale_storage_value"])
            self.assertEqual(1.26, frame["candidate_scale_semantic_value"])
            self.assertTrue(frame["scale_contract_ok"])

    def test_sprite_sheets_are_1024_square_and_all_eight_payloads_are_installed(self) -> None:
        audit = self.report["route_c_audit"]
        self.assertEqual(6, audit["container_count"])
        self.assertEqual(2, audit["sprite_sheet_count"])
        self.assertEqual(8, audit["payload_count"])
        for form, config in FORMS.items():
            self.assertEqual([1024, 1024], audit["forms"][form]["sprite_sheet"]["candidate_size"])
            self.assertTrue(audit["forms"][form]["sprite_sheet"]["size_contract_ok"])
            source_sheet = (ROUTE_C_FULL / config["source_dir"] / config["sheet"]).read_bytes()
            installed_sheet = (self.output / PIXEL_ROOT / config["sheet"]).read_bytes()
            self.assertTrue(installed_sheet.startswith(self.module.wf_assets.PNG_FAKE))
            self.assertEqual(source_sheet, self.module.wf_assets.png_decode(installed_sheet))
            for key in ("atlas", "frame", "timeline"):
                source = ROUTE_C_FULL / config["source_dir"] / config[key]
                installed = self.output / PIXEL_ROOT / config[key]
                self.assertEqual(source.read_bytes(), installed.read_bytes())

    def test_candidate_manifest_pixel_entries_match_installed_bytes(self) -> None:
        manifest = json.loads((self.output / "manifest.json").read_text(encoding="utf-8"))
        common = {entry["logical_path"]: entry for entry in manifest["roots"]["common"]}
        self.assertTrue(self.report["route_c_audit"]["manifest"]["all_match"])
        self.assertEqual(8, self.report["route_c_audit"]["manifest"]["updated_entries"])
        for config in FORMS.values():
            for key in ("sheet", "atlas", "frame", "timeline"):
                logical = f"character/seris_dragon_king/pixelart/{config[key]}"
                installed = self.output / "roots" / "common" / Path(logical)
                self.assertEqual(_sha256(installed), common[logical]["sha256"])
                self.assertEqual(installed.stat().st_size, common[logical]["size"])


if __name__ == "__main__":
    unittest.main()
