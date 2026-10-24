# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
import zlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_TOOLS = REPO_ROOT / "mod-tools"
if str(MOD_TOOLS) not in sys.path:
    sys.path.insert(0, str(MOD_TOOLS))

import wf_dsl


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
EFFECTS = REPO_ROOT / "work" / "seris_v2" / "authoring" / "effects" / "_containers"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestSerisIntegrationEffects(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        spec = importlib.util.spec_from_file_location("seris_integration_effects", BUILD_SCRIPT)
        if spec is None or spec.loader is None:
            raise AssertionError(f"cannot load build script: {BUILD_SCRIPT}")
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)
        cls.temp = tempfile.TemporaryDirectory(prefix="seris-phase2-step3-test-")
        integration = Path(cls.temp.name) / "integration"
        cls.output = integration / "seris_dragon_king"
        cls.evidence = integration / "evidence" / "phase2_step3.json"
        cls.report = cls.module.build_candidate(
            SOURCE_PACKAGE,
            cls.output,
            cls.evidence,
            allowed_output_root=integration,
            route_c_full=ROUTE_C_FULL,
            effects_source=EFFECTS,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()

    def test_two_clean_builds_match_and_all_sources_remain_read_only(self) -> None:
        report = self.report
        self.assertEqual("phase2_step3", report["phase"])
        self.assertTrue(report["reproducible"])
        self.assertTrue(report["source_unchanged"])
        self.assertTrue(report["route_c_source_unchanged"])
        self.assertTrue(report["effects_source_unchanged"])
        self.assertEqual(report["build_a"]["path_sha256"], report["build_b"]["path_sha256"])
        self.assertEqual(report["build_b"]["path_sha256"], report["final"]["path_sha256"])
        self.assertEqual(report, json.loads(self.evidence.read_text(encoding="utf-8")))

    def test_exactly_six_pf_and_two_skill_containers_are_installed(self) -> None:
        audit = self.report["effects_audit"]
        self.assertEqual(8, audit["container_count"])
        self.assertEqual(6, audit["pf_container_count"])
        self.assertEqual(2, audit["skill_container_count"])
        self.assertEqual(24, audit["unique_payload_count"])
        self.assertEqual(20, audit["amf3_payload_count"])
        self.assertEqual(4, audit["sheet_payload_count"])
        self.assertEqual(8, len(audit["containers"]))
        self.assertTrue(audit["all_pass"])

    def test_pf_timelines_use_packaged_seris_sounds(self) -> None:
        expected = {
            "human": (
                "seris_human_shooting_powerflip",
                "sound_effect/unique/se_seris_water_rise",
            ),
            "dragon": (
                "seris_dragon_special_powerflip",
                "sound_effect/unique/se_seris_dragon_breath",
            ),
        }
        for name, (container, sound_path) in expected.items():
            for level in (1, 2, 3):
                with self.subTest(form=name, level=level):
                    timeline_path = (
                        EFFECTS
                        / "battle"
                        / "effect"
                        / "powerflip"
                        / container
                        / f"{container}_lv{level}.timeline.amf3.deflate"
                    )
                    tree = wf_dsl.parse_dsl(
                        zlib.decompress(timeline_path.read_bytes(), -15)
                    )["tree"]
                    self.assertEqual(
                        [sound_path],
                        [sound["path"] for sound in tree["sounds"]],
                    )

    def test_amf3_semantic_and_byte_roundtrip_and_sheet_roundtrip(self) -> None:
        audit = self.report["effects_audit"]
        for relative, item in audit["payloads"].items():
            source = EFFECTS / Path(*item["source_logical_path"].split("/"))
            candidate = self.output / "roots" / "common" / Path(*relative.split("/"))
            self.assertEqual(source.read_bytes(), candidate.read_bytes())
            self.assertTrue(item["source_candidate_byte_exact"])
            self.assertTrue(item["semantic_equal"])
            if item["payload_kind"] == "sheet":
                self.assertTrue(item["source_codec_byte_roundtrip"])
                self.assertTrue(item["candidate_codec_byte_roundtrip"])
                self.assertEqual([512, 512], item["decoded_size"])
            else:
                self.assertTrue(item["source_amf3_byte_roundtrip"])
                self.assertTrue(item["candidate_amf3_byte_roundtrip"])

    def test_all_eight_container_anchors_are_exactly_centered(self) -> None:
        for item in self.report["effects_audit"]["containers"].values():
            anchor = item["anchor"]
            self.assertTrue(anchor["all_references_in_atlas"])
            self.assertTrue(anchor["atlas_dimensions_match_canvas"])
            self.assertTrue(anchor["exact_centered"])
            self.assertEqual([0.0, 0.0], anchor["center_delta_px"])
            matrix = anchor["matrix"]
            width, height = item["expected_canvas"]
            self.assertEqual(0, matrix["b"])
            self.assertEqual(0, matrix["c"])
            self.assertEqual(-(width // 2) * matrix["a"], matrix["x"])
            self.assertEqual(-(height // 2) * matrix["d"], matrix["y"])

    def test_manifest_registers_all_24_payloads_with_exact_hashes(self) -> None:
        audit = self.report["effects_audit"]["manifest"]
        self.assertEqual(24, len(audit["entries"]))
        self.assertEqual(24, audit["added_entries"])
        self.assertEqual(0, audit["updated_entries"])
        self.assertTrue(audit["all_match"])
        manifest = json.loads((self.output / "manifest.json").read_text(encoding="utf-8"))
        common = {entry["logical_path"]: entry for entry in manifest["roots"]["common"]}
        for relative in self.report["effects_audit"]["payloads"]:
            candidate = self.output / "roots" / "common" / Path(*relative.split("/"))
            self.assertEqual(_sha256(candidate), common[relative]["sha256"])
            self.assertEqual(candidate.stat().st_size, common[relative]["size"])


if __name__ == "__main__":
    unittest.main()
