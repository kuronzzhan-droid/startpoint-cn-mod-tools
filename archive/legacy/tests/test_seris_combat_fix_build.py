# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib.util
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
import wf_mod_tool


BUILD_SCRIPT = REPO_ROOT / "work" / "seris_v2" / "integration" / "build_candidate.py"
BASELINE = (
    REPO_ROOT
    / "work"
    / "cf2"
    / "seris_dragon_king_skill_texture_hotfix_20260719"
    / "seris_dragon_king"
    / "package"
)
PF_BINDING = REPO_ROOT / "work" / "seris_v2" / "authoring" / "powerflip_dsl"
SKILL_DSL = REPO_ROOT / "work" / "seris_v2" / "authoring" / "skill_dsl"
EFFECTS = REPO_ROOT / "work" / "seris_v2" / "authoring" / "effects" / "_containers"
SKILL_PROGRAMS = {
    "battle/action/skill/seris_dragon_king/seris_dragon_king.action.dsl.amf3.deflate": "human",
    "battle/action/skill/seris_dragon_king/seris_dragon_king_2.action.dsl.amf3.deflate": "human",
    "battle/action/skill/seris_dragon_king/seris_dragon_king_matched.action.dsl.amf3.deflate": "dragon",
    "battle/action/skill/seris_dragon_king/seris_dragon_king_matched_2.action.dsl.amf3.deflate": "dragon",
}
PF_LEVEL_POWERS = {
    "override_seris_human_powerflip": {1: 20.0, 2: 35.0, 3: 55.0},
    "override_seris_dragon_special": {1: 25.0, 2: 45.0, 3: 70.0},
}
TRANSFORM_TIMELINE = (
    "battle/effect/skill_unique/seris_dragon_king/"
    "seris_dragon_king_transform.timeline.amf3.deflate"
)


def _tree(path: Path) -> object:
    return wf_dsl.parse_dsl(zlib.decompress(path.read_bytes(), -15))["tree"]


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


class TestSerisCombatFixBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        spec = importlib.util.spec_from_file_location("seris_combat_fix", BUILD_SCRIPT)
        if spec is None or spec.loader is None:
            raise AssertionError(f"cannot load build script: {BUILD_SCRIPT}")
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)
        cls.temp = tempfile.TemporaryDirectory(prefix="seris-combat-fix-test-")
        root = Path(cls.temp.name)
        cls.output = root / "candidate"
        cls.baseline_before = cls.module._snapshot(BASELINE)
        cls.report = cls.module.build_combat_fix_candidate(
            BASELINE,
            cls.output,
            root / "evidence.json",
            pf_binding_source=PF_BINDING,
            skill_dsl_source=SKILL_DSL,
            effects_source=EFFECTS,
            allowed_output_root=root,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()

    def test_build_is_reproducible_and_baseline_untouched(self) -> None:
        self.assertEqual("combat_fix", self.report["phase"])
        self.assertTrue(self.report["reproducible"])
        self.assertEqual(self.baseline_before, self.module._snapshot(BASELINE))
        beam_added = {
            f"roots/common/{logical}"
            for logical in self.module.PF_BEAM_PAYLOAD_FILES
        }
        self.assertEqual(beam_added, set(self.report["added_paths"]))
        expected_changed = {
            *beam_added,
            "manifest.json",
            f"roots/common/{TRANSFORM_TIMELINE}",
            "roots/common/master/ability/leader_ability.orderedmap",
            *(f"roots/common/{path}" for path in SKILL_PROGRAMS),
            *(
                "roots/common/battle/action/power_flip/action/override/"
                f"{action_id}${action_id}_lv{level}.action.dsl.amf3.deflate"
                for action_id in PF_LEVEL_POWERS
                for level in (1, 2, 3)
            ),
            # regenerated PF containers: two-segment .gen frame renames
            *(
                f"roots/common/battle/effect/powerflip/{family}/{family}{suffix}"
                for family in (
                    "seris_human_shooting_powerflip",
                    "seris_dragon_special_powerflip",
                )
                for suffix in (
                    ".atlas.amf3.deflate",
                    "_lv1.parts.amf3.deflate",
                    "_lv2.parts.amf3.deflate",
                    "_lv3.parts.amf3.deflate",
                )
            ),
        }
        self.assertEqual(expected_changed, set(self.report["changed_paths"]))

    def test_pf_container_frames_use_two_segment_file_base_names(self) -> None:
        for family in ("seris_human_shooting_powerflip", "seris_dragon_special_powerflip"):
            base = self.output / "roots" / "common" / "battle" / "effect" / "powerflip" / family
            atlas = _tree(base / f"{family}.atlas.amf3.deflate")
            names = {entry["n"] for entry in atlas}
            for name in names:
                tail = name.split(".gen/")[1]
                self.assertEqual(2, len(tail.split("/")), name)
            for level in (1, 2, 3):
                parts = _tree(base / f"{family}_lv{level}.parts.amf3.deflate")
                refs = [item["p"] for item in parts["i"]]
                prefix = (
                    f"battle/effect/powerflip/{family}/.gen/{family}_lv{level}/"
                )
                for ref in refs:
                    self.assertTrue(ref.startswith(prefix), ref)
                    self.assertIn(ref, names, ref)

    def test_pf_actions_transform_the_official_trees(self) -> None:
        expected_area_counts = {"override_seris_human_powerflip": {1: 1, 2: 2, 3: 3},
                                "override_seris_dragon_special": {1: 2, 2: 2, 3: 2}}
        official_prefix = "battle/effect/powerflip/effect_powerflip_attack_"
        for action_id, powers in PF_LEVEL_POWERS.items():
            human = action_id == "override_seris_human_powerflip"
            for level, total in powers.items():
                path = (
                    self.output
                    / "roots"
                    / "common"
                    / "battle"
                    / "action"
                    / "power_flip"
                    / "action"
                    / "override"
                    / f"{action_id}${action_id}_lv{level}.action.dsl.amf3.deflate"
                )
                tree = _tree(path)
                self.assertGreaterEqual(len(_commands(tree, "SetPowerFilpSuppress")), 1, path.name)
                self.assertGreaterEqual(len(_commands(tree, "NotifyPowerflipEnd")), 1, path.name)
                hit_areas = _commands(tree, "CreateHitArea")
                self.assertEqual(
                    expected_area_counts[action_id][level], len(hit_areas), path.name
                )
                effects = _commands(tree, "ShowEffect")
                accent_paths = [e[2][1] for e in effects if e[1] == "赛瑞斯强化弹射点缀"]
                own = (
                    "battle/effect/powerflip/"
                    + ("seris_human_shooting_powerflip" if human else "seris_dragon_special_powerflip")
                )
                self.assertEqual(1, len(accent_paths), path.name)
                self.assertTrue(accent_paths[0].startswith(own), path.name)
                self.assertTrue(accent_paths[0].endswith(f"_lv{level}"), path.name)
                for effect in effects:
                    if effect[1] == "赛瑞斯强化弹射点缀":
                        continue
                    self.assertTrue(effect[2][1].startswith(official_prefix), path.name)
                if human:
                    self.assertEqual([], _commands(tree, "CollisionOfBallAndEnemy"), path.name)
                    for area in hit_areas:
                        self.assertEqual("Rectangle", area[9][0], path.name)
                        self.assertEqual(["EF"], area[3], path.name)
                else:
                    # official special semantic: flight aura, then contact burst
                    self.assertEqual(1, len(_commands(tree, "CollisionOfBallAndEnemy")), path.name)
                    self.assertEqual(1, len(_commands(tree, "CreateReferencePoint")), path.name)
                    for area in hit_areas:
                        self.assertEqual("Circle", area[9][0], path.name)
                        self.assertEqual(["AB"], area[3], path.name)
                attacks = _commands(tree, "CreateNormalAttack")
                self.assertEqual(len(hit_areas), len(attacks), path.name)
                elements = {"override_seris_human_powerflip": {1: 2, 2: 2, 3: 3},
                            "override_seris_dragon_special": {1: 2, 2: 3, 3: 3}}
                worst_case = 0.0
                for area in hit_areas:
                    ways = int(area[12][1]) if area[12][0] == "NWay" else 1
                    hits = int(area[14][1])
                    attack = _commands(area, "CreateNormalAttack")[0]
                    self.assertEqual(elements[action_id][level], attack[2], path.name)
                    worst_case += attack[6][0]["min"] * hits * ways
                self.assertAlmostEqual(total, worst_case, places=6, msg=path.name)

    def test_leader_rows_bind_dragon_then_human_during_419(self) -> None:
        leader_path = (
            self.output / "roots" / "common" / "master" / "ability" / "leader_ability.orderedmap"
        )
        rows = wf_mod_tool.read_csv_lines(
            wf_mod_tool.read_orderedmap_file_from_bytes(leader_path.read_bytes())["129999"]
        )
        overrides = [row for row in rows if len(row) == 124 and row[107] == "419"]
        self.assertEqual(2, len(overrides))
        dragon, human = overrides
        self.assertEqual("194", dragon[95])
        self.assertEqual("22", dragon[102])
        self.assertEqual("5", dragon[100])
        self.assertEqual("override_seris_dragon_special", dragon[118])
        self.assertEqual("1,2,3", dragon[119])
        self.assertEqual("1", human[95])
        self.assertEqual("(None)", human[97])
        self.assertEqual("100000", human[98])
        self.assertEqual("100000", human[99])
        self.assertEqual("override_seris_human_powerflip", human[118])
        self.assertEqual("1,2,3", human[119])
        for row in overrides:
            for column in (45, 108, 109, 111, 112, 121):
                self.assertEqual("", row[column])
        self.assertFalse([row for row in rows if len(row) == 124 and row[45] == "722"])

    def test_skill_effects_gain_field_scale_tracking_and_breath_rotation(self) -> None:
        for logical, form in SKILL_PROGRAMS.items():
            tree = _tree(self.output / "roots" / "common" / Path(*logical.split("/")))
            primary = next(
                command
                for command in _commands(tree, "ShowEffect")
                if command[1] == "全体演出"
            )
            self.assertEqual(0, primary[7], logical)
            self.assertEqual(0, primary[8], logical)
            self.assertTrue(primary[10], logical)
            self.assertTrue(primary[11], logical)
            # containers bake the design world scale (12x/9x) into the parts
            # matrices, so the DSL multiplier must stay at 1.0
            scale = primary[12][1][0]["min"]
            self.assertEqual(1.0, scale, logical)
            if form == "human":
                self.assertEqual(0, primary[9], logical)
            else:
                self.assertAlmostEqual(3.141592653589793, primary[9], msg=logical)

    def test_transform_timeline_keeps_only_the_transform_sound(self) -> None:
        tree = _tree(self.output / "roots" / "common" / Path(*TRANSFORM_TIMELINE.split("/")))
        self.assertEqual(
            ["sound_effect/unique/se_seris_transform"],
            [entry["path"] for entry in tree["sounds"]],
        )
        audit = self.report["transform_sound_audit"]
        self.assertTrue(audit["removed"])
        self.assertEqual("sound_effect/unique/se_seris_dragon_roar", audit["dropped_sound"])


if __name__ == "__main__":
    unittest.main()
