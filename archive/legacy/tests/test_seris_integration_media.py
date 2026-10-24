# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_TOOLS = REPO_ROOT / "mod-tools"
if str(MOD_TOOLS) not in sys.path:
    sys.path.insert(0, str(MOD_TOOLS))

import wf_assets
import wf_atf
import wf_mod_tool as core


BUILD_SCRIPT = REPO_ROOT / "work/seris_v2/integration/build_candidate.py"
SOURCE_PACKAGE = (
    REPO_ROOT
    / ".worktrees/seris-dual-form/work/sfix159/seris_dragon_king/package"
)
ROUTE_C_FULL = REPO_ROOT / "work/seris_v2/authoring/pixel_route_c/full"
EFFECTS = REPO_ROOT / "work/seris_v2/authoring/effects/_containers"
SKILL_DSL = REPO_ROOT / "work/seris_v2/authoring/skill_dsl"
VOICE = REPO_ROOT / "work/seris_v2/authoring/voice"
ICONS = REPO_ROOT / "work/seris_v2/authoring/icons_dragon"
SERIS = "seris_dragon_king"
TRIM_LOGICAL = "master/generated/trimmed_image.orderedmap"
TRIM_KEY = "character/seris_dragon_king/ui/skill_cutin_dragon"
TABLES = (
    "master/skill/action_skill.orderedmap",
    "master/skill/switched_action_skill.orderedmap",
)
UI = {
    "skill_cutin_dragon.png": (1024, 512),
    "battle_control_board_dragon.png": (104, 268),
    "battle_member_status_dragon.png": (58, 58),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _root_path(package: Path, root: str, logical: str) -> Path:
    return package / "roots" / root / Path(*logical.split("/"))


class TestSerisIntegrationMedia(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        spec = importlib.util.spec_from_file_location("seris_phase3_media", BUILD_SCRIPT)
        if spec is None or spec.loader is None:
            raise AssertionError(f"cannot load build script: {BUILD_SCRIPT}")
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)
        cls.temp = tempfile.TemporaryDirectory(prefix="seris-phase3-media-test-")
        cls.root = Path(cls.temp.name)
        cls.live_store = cls.root / "live-store"
        for logical in TABLES:
            source = _root_path(SOURCE_PACKAGE, "common", logical)
            target = core.table_path(cls.live_store, logical)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        cls.integration = cls.root / "integration"
        cls.output = cls.integration / SERIS
        cls.evidence = cls.integration / "evidence/phase3_ui_voice.json"
        cls.baseline = cls.module._snapshot(SOURCE_PACKAGE)
        cls.report = cls.module.build_candidate(
            SOURCE_PACKAGE,
            cls.output,
            cls.evidence,
            allowed_output_root=cls.integration,
            route_c_full=ROUTE_C_FULL,
            effects_source=EFFECTS,
            live_store=cls.live_store,
            skill_dsl_source=SKILL_DSL,
            voice_source=VOICE,
            icon_source=ICONS,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()

    def test_two_clean_builds_and_media_inventory(self) -> None:
        self.assertEqual("phase3_ui_voice", self.report["phase"])
        self.assertEqual(
            self.report["build_a"]["path_sha256"],
            self.report["build_b"]["path_sha256"],
        )
        self.assertEqual(
            self.report["build_b"]["path_sha256"],
            self.report["final"]["path_sha256"],
        )
        audit = self.report["media_audit"]
        self.assertEqual(22, audit["voice_count"])
        self.assertEqual(3, audit["png_count"])
        self.assertEqual(1, audit["atf_count"])
        self.assertTrue(audit["all_pass"])

    def test_twenty_two_voices_match_lines_card_and_candidate_bytes(self) -> None:
        lines = json.loads((VOICE / "lines.json").read_text(encoding="utf-8"))
        card = json.loads((VOICE / "voice_card.json").read_text(encoding="utf-8"))
        paths = {item["path"] for item in card["outputs"]}
        self.assertEqual(22, len(paths))
        self.assertEqual(set(lines), paths)
        for relative in paths:
            logical = f"character/{SERIS}/voice/{relative}"
            stored = _root_path(self.output, "common", logical).read_bytes()
            self.assertEqual((VOICE / relative).read_bytes(), wf_assets.mp3_decode(stored))
            probe = wf_assets.mp3_probe(stored, 1023)
            self.assertGreater(probe["frames"], 0)
            self.assertEqual(0, probe["tail"])
            self.assertEqual({96000}, probe["bitrates"])
            self.assertEqual({44100}, probe["srates"])

    def test_dragon_png_atf_and_trim_contract(self) -> None:
        for filename, dimensions in UI.items():
            logical = f"character/{SERIS}/ui/{filename}"
            stored = _root_path(self.output, "medium", logical).read_bytes()
            decoded = wf_assets.png_decode(stored)
            self.assertEqual(dimensions, wf_assets.png_dims(decoded))
            self.assertEqual((ICONS / filename).read_bytes(), decoded)
        atf_logical = f"character/{SERIS}/ui/skill_cutin_dragon.atf.deflate"
        raw = wf_atf.inflate(_root_path(self.output, "android", atf_logical).read_bytes())
        parsed = wf_atf.parse_atf(raw)
        self.assertEqual((1024, 512, 11), (parsed["w"], parsed["h"], parsed["mips"]))
        trim = core.read_orderedmap_file(
            _root_path(self.output, "common", TRIM_LOGICAL), TRIM_LOGICAL
        )
        self.assertEqual("0,0,1024,512", trim.text_rows()[TRIM_KEY])

    def test_manifest_entries_match_and_existing_ui_slots_are_unchanged(self) -> None:
        manifest = json.loads((self.output / "manifest.json").read_text(encoding="utf-8"))
        for root in ("common", "medium", "android"):
            by_path = {entry["logical_path"]: entry for entry in manifest["roots"][root]}
            for logical, entry in by_path.items():
                if logical.startswith(f"character/{SERIS}/voice/") or "_dragon" in logical or logical == TRIM_LOGICAL:
                    payload = _root_path(self.output, root, logical)
                    self.assertEqual(_sha256(payload), entry["sha256"])
                    self.assertEqual(payload.stat().st_size, entry["size"])
        for root, logical in (
            ("medium", f"character/{SERIS}/ui/skill_cutin_0.png"),
            ("medium", f"character/{SERIS}/ui/skill_cutin_1.png"),
            ("android", f"character/{SERIS}/ui/skill_cutin_0.atf.deflate"),
            ("android", f"character/{SERIS}/ui/skill_cutin_1.atf.deflate"),
        ):
            relative = f"roots/{root}/{logical}"
            self.assertEqual(self.baseline["path_sha256"][relative], _sha256(_root_path(self.output, root, logical)))

    def test_media_sources_are_read_only_and_evidence_is_exact(self) -> None:
        self.assertTrue(self.report["media_source_unchanged"])
        self.assertEqual(self.report, json.loads(self.evidence.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
