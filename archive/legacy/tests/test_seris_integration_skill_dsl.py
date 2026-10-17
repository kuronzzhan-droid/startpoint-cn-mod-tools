# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
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
import wf_mod_tool as core


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
SKILL_DSL = REPO_ROOT / "work" / "seris_v2" / "authoring" / "skill_dsl"
TABLES = (
    "master/skill/action_skill.orderedmap",
    "master/skill/switched_action_skill.orderedmap",
)
SERIS = "seris_dragon_king"
EXPECTED = {
    "human": {
        "effect_ref": (
            "battle/effect/skill_unique/seris_human_royal_tide_ring/"
            "seris_human_royal_tide_ring"
        ),
        "offset": [0, 0],
        "lifetime_ticks": 32,
        "events": [
            (1, 4, 8, "water", 2, "inner_water_ring"),
            (2, 6, 12, "water", 2, "middle_water_ring"),
            (3, 8, 16, "water", 2, "outer_water_ring"),
            (4, 9, 18, "thunder", 3, "vertical_thunder_scythe"),
            (5, 10, 20, "thunder", 3, "double_diagonal_thunder_scythe"),
            (6, 11, 22, "thunder", 3, "six_axis_thunder_scythe_convergence"),
        ],
        "programs": (
            "battle/action/skill/seris_dragon_king/seris_dragon_king.action.dsl.amf3.deflate",
            "battle/action/skill/seris_dragon_king/seris_dragon_king_2.action.dsl.amf3.deflate",
        ),
        "table": "master/skill/action_skill.orderedmap",
    },
    "dragon": {
        "effect_ref": (
            "battle/effect/skill_unique/seris_dragon_frozen_thunder_breath/"
            "seris_dragon_frozen_thunder_breath"
        ),
        "offset": [0, 0],
        "lifetime_ticks": 36,
        "events": [
            (1, 3, 6, "thunder", 3, "dragon_spine_open_1"),
            (2, 4, 8, "thunder", 3, "dragon_spine_open_2"),
            (3, 6, 12, "water", 2, "ice_pressure_impact_1"),
            (4, 7, 14, "water", 2, "ice_pressure_impact_2"),
            (5, 8, 16, "water", 2, "ice_pressure_impact_3"),
            (6, 9, 18, "water", 2, "ice_pressure_impact_4"),
            (7, 11, 22, "thunder", 3, "terminal_thunder_implosion"),
            (8, 12, 24, "thunder", 3, "terminal_thunder_crown_flip"),
        ],
        "programs": (
            "battle/action/skill/seris_dragon_king/seris_dragon_king_matched.action.dsl.amf3.deflate",
            "battle/action/skill/seris_dragon_king/seris_dragon_king_matched_2.action.dsl.amf3.deflate",
        ),
        "table": "master/skill/switched_action_skill.orderedmap",
    },
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _package_path(package: Path, logical_path: str) -> Path:
    return package / "roots" / "common" / Path(*logical_path.split("/"))


def _commands(tree: object, name: str) -> list[list[object]]:
    found: list[list[object]] = []

    def visit(node: object) -> None:
        if isinstance(node, list):
            if node and node[0] == name:
                found.append(node)
            for child in node:
                visit(child)
        elif isinstance(node, dict):
            for child in node.values():
                visit(child)

    visit(tree)
    return found


def _tree(path: Path) -> tuple[bytes, object]:
    inflated = zlib.decompress(path.read_bytes(), -15)
    return inflated, wf_dsl.parse_dsl(inflated)["tree"]


class TestSerisIntegrationSkillDsl(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        spec = importlib.util.spec_from_file_location("seris_integration_step5", BUILD_SCRIPT)
        if spec is None or spec.loader is None:
            raise AssertionError(f"cannot load build script: {BUILD_SCRIPT}")
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

        cls.temp = tempfile.TemporaryDirectory(prefix="seris-phase2-step5-test-")
        cls.root = Path(cls.temp.name)
        cls.source = cls.root / "source-package"
        shutil.copytree(SOURCE_PACKAGE, cls.source)
        cls.live_store = cls.root / "live-store"
        for logical_path in TABLES:
            source_path = _package_path(cls.source, logical_path)
            live_path = core.table_path(cls.live_store, logical_path)
            live_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_path, live_path)

        cls.source_before = cls.module._snapshot(cls.source)
        cls.effects_before = cls.module._snapshot(EFFECTS)
        cls.skill_dsl_before = cls.module._snapshot(SKILL_DSL)
        cls.live_before = {
            logical_path: _sha256(core.table_path(cls.live_store, logical_path))
            for logical_path in TABLES
        }
        cls.integration = cls.root / "integration"
        cls.output = cls.integration / SERIS
        cls.evidence = cls.integration / "evidence" / "phase2_step5.json"
        cls.report = cls.module.build_candidate(
            cls.source,
            cls.output,
            cls.evidence,
            allowed_output_root=cls.integration,
            route_c_full=ROUTE_C_FULL,
            effects_source=EFFECTS,
            live_store=cls.live_store,
            skill_dsl_source=SKILL_DSL,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()

    def test_exact_six_and_eight_visual_damage_beat_contract(self) -> None:
        self.assertEqual("phase2_step5", self.report["phase"])
        audit = self.report["skill_dsl_audit"]
        self.assertEqual(14, audit["total_segment_count"])
        self.assertTrue(audit["key_completeness"])
        for form, expected in EXPECTED.items():
            actual = audit["forms"][form]
            events = [
                (
                    item["segment"], item["state"], item["tick"], item["element"],
                    item["element_id"], item["visual_accent"],
                )
                for item in actual["events"]
            ]
            self.assertEqual(expected["events"], events)
            self.assertEqual(len(expected["events"]), actual["segment_count"])
            self.assertEqual(len(expected["events"]), actual["visual_event_count"])
            self.assertEqual(len(expected["events"]), actual["damage_event_count"])
            self.assertTrue(actual["visual_damage_ticks_aligned"])

    def test_all_four_programs_roundtrip_and_schedule_the_expected_hits(self) -> None:
        for form, expected in EXPECTED.items():
            for logical_path in expected["programs"]:
                path = _package_path(self.output, logical_path)
                inflated, tree = _tree(path)
                self.assertEqual(inflated, wf_dsl.encode_amf3(tree))
                effects = _commands(tree, "ShowEffect")
                self.assertIn(expected["effect_ref"], [item[2][1] for item in effects])
                waits = _commands(tree, "Wait")
                self.assertEqual(
                    [event[2] for event in expected["events"]],
                    [item[1] for item in waits],
                )
                self.assertEqual(len(expected["events"]), len(waits))
                scheduled = []
                for wait in waits:
                    attacks = _commands(wait[3], "CreateNormalAttack")
                    self.assertEqual(1, len(attacks))
                    scheduled.append(attacks[0][2])
                self.assertEqual(
                    [event[4] for event in expected["events"]], scheduled
                )
                direct_attacks = _commands(tree, "CreateNormalAttack")
                self.assertEqual(len(expected["events"]), len(direct_attacks))

    def test_effect_container_and_table_references_are_consistent(self) -> None:
        audit = self.report["skill_dsl_audit"]
        self.assertTrue(audit["container_references_consistent"])
        self.assertTrue(audit["table_references_consistent"])
        for form, expected in EXPECTED.items():
            actual = audit["forms"][form]
            self.assertEqual(expected["effect_ref"], actual["effect_ref"])
            self.assertEqual(expected["offset"], actual["effect_offset"])
            self.assertEqual(expected["lifetime_ticks"], actual["effect_lifetime_ticks"])
            self.assertEqual(expected["table"], actual["table_logical_path"])
            self.assertTrue(actual["effect_parts_present"])
            self.assertTrue(actual["effect_timeline_present"])
            self.assertEqual(
                {str(event[1]): event[2] for event in expected["events"]},
                actual["effect_state_ticks"],
            )
            self.assertTrue(actual["effect_visual_states_resolve"])
            self.assertEqual(expected["lifetime_ticks"], actual["effect_timeline_end"])
            self.assertTrue(actual["effect_timeline_lifetime_match"])
            self.assertTrue(actual["table_program_paths_match"])

    def test_runtime_loader_atlas_resolves_every_skill_effect_texture(self) -> None:
        for form, actual in self.report["skill_dsl_audit"]["forms"].items():
            effect_ref = actual["effect_ref"]
            directory, _, _effect_name = effect_ref.rpartition("/")
            loader_family = directory.rsplit("/", 1)[-1]
            parts_path = _package_path(
                self.output, effect_ref + ".parts.amf3.deflate"
            )
            loader_atlas_path = _package_path(
                self.output,
                f"{directory}/{loader_family}.atlas.amf3.deflate",
            )
            loader_sheet_path = _package_path(
                self.output,
                f"{directory}/{loader_family}.png",
            )
            _parts_bytes, parts = _tree(parts_path)
            _atlas_bytes, loader_atlas = _tree(loader_atlas_path)
            texture_refs = {
                image["p"]
                for image in parts["i"]
                if isinstance(image, dict) and isinstance(image.get("p"), str)
            }
            loaded_textures = {
                image["n"]
                for image in loader_atlas
                if isinstance(image, dict) and isinstance(image.get("n"), str)
            }
            missing = sorted(texture_refs - loaded_textures)
            self.assertTrue(loader_sheet_path.is_file(), form)
            self.assertFalse(
                missing,
                f"{form} runtime loader atlas misses textures: {missing}",
            )

    def test_manifest_program_hashes_and_hit_metadata_match_installed_bytes(self) -> None:
        manifest = json.loads((self.output / "manifest.json").read_text(encoding="utf-8"))
        common = {item["logical_path"]: item for item in manifest["roots"]["common"]}
        skills = manifest["skills"][SERIS]
        self.assertEqual({"water": 3, "thunder": 3}, skills["human_hits"])
        self.assertEqual({"water": 4, "thunder": 4}, skills["dragon_hits"])
        programs = {item["logical_path"]: item for item in skills["programs"]}
        expected_paths = {
            path for form in EXPECTED.values() for path in form["programs"]
        }
        self.assertEqual(expected_paths, set(programs))
        for logical_path in expected_paths:
            payload = _package_path(self.output, logical_path)
            self.assertEqual(_sha256(payload), common[logical_path]["sha256"])
            self.assertEqual(payload.stat().st_size, common[logical_path]["size"])
            self.assertEqual(_sha256(payload), programs[logical_path]["sha256"])

    def test_structure_report_has_complete_program_and_reference_keys(self) -> None:
        audit = self.report["skill_dsl_audit"]
        self.assertTrue(audit["all_pass"])
        self.assertEqual(4, audit["program_count"])
        self.assertEqual(4, audit["manifest"]["updated_entries"])
        for form, expected in EXPECTED.items():
            actual = audit["forms"][form]
            self.assertEqual(list(expected["programs"]), actual["program_logical_paths"])
            self.assertEqual(len(expected["programs"]), len(actual["programs"]))
            self.assertTrue(all(item["roundtrip"] for item in actual["programs"]))
            self.assertTrue(all(item["key_complete"] for item in actual["programs"]))

    def test_two_clean_builds_match_and_all_inputs_remain_read_only(self) -> None:
        self.assertTrue(self.report["reproducible"])
        self.assertTrue(self.report["source_unchanged"])
        self.assertTrue(self.report["route_c_source_unchanged"])
        self.assertTrue(self.report["effects_source_unchanged"])
        self.assertTrue(self.report["live_nested_source_unchanged"])
        self.assertTrue(self.report["skill_dsl_source_unchanged"])
        self.assertEqual(self.source_before, self.module._snapshot(self.source))
        self.assertEqual(self.effects_before, self.module._snapshot(EFFECTS))
        self.assertEqual(self.skill_dsl_before, self.module._snapshot(SKILL_DSL))
        self.assertEqual(
            self.live_before,
            {
                logical_path: _sha256(core.table_path(self.live_store, logical_path))
                for logical_path in TABLES
            },
        )
        self.assertEqual(self.report["build_a"], self.report["build_b"])
        self.assertEqual(self.report["build_b"], self.report["final"])
        self.assertEqual(
            self.report,
            json.loads(self.evidence.read_text(encoding="utf-8")),
        )


if __name__ == "__main__":
    unittest.main()
