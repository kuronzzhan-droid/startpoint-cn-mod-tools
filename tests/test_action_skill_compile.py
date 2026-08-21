import unittest
import zlib

import wf_dsl
import wf_dsl_sig

try:
    from wf_action_skill_compile import (
        CODE_NAME,
        build_summer_thunder_dragon_skill_tree,
        compile_summer_thunder_dragon_action_skills,
        patch_summer_thunder_dragon_action_skill_rows,
    )
except ImportError:
    CODE_NAME = None
    build_summer_thunder_dragon_skill_tree = None
    compile_summer_thunder_dragon_action_skills = None
    patch_summer_thunder_dragon_action_skill_rows = None


def _same_value_and_type(left, right):
    if type(left) is not type(right):
        return False
    if isinstance(left, list):
        return len(left) == len(right) and all(
            _same_value_and_type(a, b) for a, b in zip(left, right)
        )
    if isinstance(left, dict):
        return list(left) == list(right) and all(
            _same_value_and_type(left[key], right[key]) for key in left
        )
    return left == right


def _walk(value):
    yield value
    if isinstance(value, list):
        for item in value:
            yield from _walk(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from _walk(item)


class ActionSkillCompileTests(unittest.TestCase):
    def _require_module(self):
        if build_summer_thunder_dragon_skill_tree is None:
            self.fail("wf_action_skill_compile is missing")

    def test_skill_tree_has_locked_55_hit_contract(self):
        self._require_module()
        tree = build_summer_thunder_dragon_skill_tree()

        waits = [
            value[1]
            for value in _walk(tree)
            if isinstance(value, list)
            and len(value) == 2
            and value[0] == "Event"
            and isinstance(value[1], list)
            and value[1]
            and value[1][0] == "Wait"
        ]
        self.assertEqual(1, len(waits))
        self.assertEqual(12, waits[0][1])

        commands = [
            value[1]
            for value in _walk(tree)
            if isinstance(value, list)
            and len(value) == 2
            and value[0] == "Command"
            and isinstance(value[1], list)
            and value[1]
        ]
        self.assertEqual(
            ["CreateCondition", "ShowEffect", "CreateHitArea", "CreateNormalAttack"],
            [command[0] for command in commands],
        )

        condition, effect, hit_area, attack = commands
        self.assertEqual(-17, condition[1])
        self.assertEqual(
            [["ACUnique", 139998, [{"min": 1, "max": 1}]]],
            condition[2],
        )
        expected_effect_path = (
            "battle/effect/skill_unique/cnmod_thunder_dragon_ascendant/"
            "fan_lightning/fan_lightning_wave"
        )
        self.assertEqual(expected_effect_path, effect[2][1])
        self.assertEqual(-18, effect[3])
        self.assertEqual(["ForesideOfCharacter"], effect[4])
        self.assertEqual(["PlayOnlyFirstSequence"], effect[5])
        self.assertEqual(["AB"], effect[6])
        self.assertEqual((0, 0, -1.5707963267948966), tuple(effect[7:10]))
        self.assertIs(effect[10], True)
        self.assertIs(effect[11], False)
        self.assertEqual([{"min": 6.5, "max": 6.5}], effect[12][1])

        self.assertEqual(-18, hit_area[2])
        self.assertEqual(["AB"], hit_area[3])
        self.assertEqual((0, 0, 0.0), tuple(hit_area[4:7]))
        self.assertIs(hit_area[7], True)
        self.assertIs(hit_area[8], False)
        self.assertEqual(
            [
                "Sector",
                [{"min": 400, "max": 400}],
                [{"min": 1.5707963267948966, "max": 1.5707963267948966}],
            ],
            hit_area[9],
        )
        self.assertEqual(["SpecifyHitAreaLifetimeDirectly", 110], hit_area[13])
        self.assertEqual(["CalculatedUsingMaxNumOfHits", 55], hit_area[14])
        self.assertEqual(["Some", [{"min": 55, "max": 55}]], hit_area[15])

        self.assertEqual(2, attack[1])
        self.assertEqual(255, attack[2])
        self.assertEqual(0, attack[5])
        self.assertEqual([{"min": 1.0, "max": 1.0}], attack[6])
        self.assertEqual(0, hit_area[24])

        strings = [value for value in _walk(tree) if isinstance(value, str)]
        self.assertEqual(
            [expected_effect_path],
            [s for s in strings if s.startswith("battle/effect/")],
        )
        self.assertFalse(any("character/" in s or "powerflip" in s for s in strings))

    def test_skill_tree_uses_known_command_event_and_enum_shapes(self):
        self._require_module()
        tree = build_summer_thunder_dragon_skill_tree()
        for value in _walk(tree):
            if not isinstance(value, list) or not value:
                continue
            if isinstance(value[0], str) and value[0] in {"Command", "Event"}:
                kind = value[0]
                self.assertEqual(2, len(value))
                inner = value[1]
                table = wf_dsl_sig.COMMANDS if kind == "Command" else wf_dsl_sig.EVENTS
                self.assertIn(inner[0], table)
                self.assertEqual(len(table[inner[0]]), len(inner) - 1, inner[0])

        expected_enums = {
            "None": 0,
            "Some": 1,
            "ACUnique": 2,
            "GenericConditionHitEffect": 0,
            "SpecifyEffectDirectly": 1,
            "ForesideOfCharacter": 0,
            "PlayOnlyFirstSequence": 0,
            "AB": 0,
            "Sector": 2,
            "Center": 0,
            "Single": 0,
            "SpecifyHitAreaLifetimeDirectly": 1,
            "CalculatedUsingMaxNumOfHits": 1,
        }
        for name, argument_count in expected_enums.items():
            matches = [
                value for value in _walk(tree)
                if isinstance(value, list) and value and value[0] == name
            ]
            self.assertTrue(matches, name)
            self.assertTrue(all(len(value) - 1 == argument_count for value in matches), name)

    def test_compiled_skills_are_deterministic_strict_raw_deflate(self):
        self._require_module()
        files = compile_summer_thunder_dragon_action_skills()
        self.assertEqual(files, compile_summer_thunder_dragon_action_skills())
        expected_program_paths = {
            "1": (
                "battle/action/skill/action/rare5/"
                "cnmod_thunder_dragon_ascendant$cnmod_thunder_dragon_ascendant_1"
            ),
            "2": (
                "battle/action/skill/action/rare5/"
                "cnmod_thunder_dragon_ascendant$cnmod_thunder_dragon_ascendant_2"
            ),
        }
        self.assertEqual(
            {
                f"{path}.action.dsl.amf3.deflate"
                for path in expected_program_paths.values()
            },
            set(files),
        )
        expected_tree = build_summer_thunder_dragon_skill_tree()
        for logical, payload in files.items():
            decompressor = zlib.decompressobj(-15)
            plain = decompressor.decompress(payload) + decompressor.flush()
            self.assertTrue(decompressor.eof, logical)
            self.assertEqual(b"", decompressor.unused_data, logical)
            self.assertEqual(b"", decompressor.unconsumed_tail, logical)
            decoded = wf_dsl.parse_dsl(plain)["tree"]
            self.assertTrue(_same_value_and_type(expected_tree, decoded), logical)

    def test_action_skill_rows_keep_only_two_levels_and_600_cost(self):
        self._require_module()
        donor = [
            ("1", ["old", "old desc", "dynamic/skill/atk_nearest", "true", "440", "440", "0", "old/1"] + [""] * 16),
            ("2", ["old+", "old desc", "dynamic/skill/atk_nearest", "true", "440", "390", "0", "old/2"] + [""] * 16),
            ("3", ["old++", "old desc", "dynamic/skill/atk_nearest", "true", "390", "390", "0", "old/3"] + [""] * 16),
        ]
        patched = patch_summer_thunder_dragon_action_skill_rows(donor)
        expected_program_paths = {
            "1": (
                "battle/action/skill/action/rare5/"
                "cnmod_thunder_dragon_ascendant$cnmod_thunder_dragon_ascendant_1"
            ),
            "2": (
                "battle/action/skill/action/rare5/"
                "cnmod_thunder_dragon_ascendant$cnmod_thunder_dragon_ascendant_2"
            ),
        }
        self.assertEqual(["1", "2"], [key for key, _ in patched])
        expected_description = (
            "向前方释放由中心扩散的黄蓝雷波，对扇形范围内的敌人造成雷属性伤害"
            "（合计55倍／55段），并赋予自身「雷电增幅」效果（10秒）。"
        )
        for key, columns in patched:
            self.assertEqual(24, len(columns))
            self.assertEqual("dynamic/skill/atk_front", columns[2])
            self.assertEqual("true", columns[3])
            self.assertEqual("600", columns[4])
            self.assertEqual("600", columns[5])
            self.assertEqual(expected_program_paths[key], columns[7])
            self.assertEqual(expected_description, columns[1])
            self.assertNotIn("额外乘区", columns[1])
        self.assertEqual(CODE_NAME, "cnmod_thunder_dragon_ascendant")


if __name__ == "__main__":
    unittest.main()
