import unittest
import zlib

import wf_mod_tool as core

try:
    from wf_summer_thunder_skill_preview_compile import (
        LOGICAL_PATH,
        build_summer_thunder_skill_preview_tree,
        compile_summer_thunder_skill_preview,
    )
except ImportError:
    LOGICAL_PATH = None
    build_summer_thunder_skill_preview_tree = None
    compile_summer_thunder_skill_preview = None


class SummerThunderSkillPreviewCompileTests(unittest.TestCase):
    def _require_module(self):
        if build_summer_thunder_skill_preview_tree is None:
            self.fail("wf_summer_thunder_skill_preview_compile is missing")

    def test_tree_is_the_locked_official_preview_contract(self):
        self._require_module()
        self.assertEqual(
            "character/cnmod_thunder_dragon_ascendant/battle/"
            "character_detail_skill_preview.battle.amf3.deflate",
            LOGICAL_PATH,
        )
        self.assertEqual(
            {
                "config": {
                    "start_frame": 0,
                    "end_frame": 330,
                    "ball": {"x": -200, "y": -300, "vx": 0, "vy": 0},
                    "hp_ratio": 1,
                    "skill_gauge_ratio": 1,
                    "power_flip_level": 0,
                },
                "log_parts": [
                    {"f": 107, "c": [2, 0]},
                    {"f": 232, "c": [13, True]},
                ],
            },
            build_summer_thunder_skill_preview_tree(),
        )

    def test_compiler_emits_strict_raw_deflate_and_round_trips(self):
        self._require_module()
        result = compile_summer_thunder_skill_preview()
        self.assertEqual({LOGICAL_PATH}, set(result["files"]))
        payload = result["files"][LOGICAL_PATH]
        inflater = zlib.decompressobj(-15)
        plain = inflater.decompress(payload) + inflater.flush()
        self.assertEqual(b"", inflater.unused_data)
        self.assertTrue(inflater.eof)
        decoded = core.AMF3Reader(plain).read_value()
        self.assertEqual(build_summer_thunder_skill_preview_tree(), decoded)

        report = result["report"]
        self.assertEqual(330, report["end_frame"])
        self.assertEqual(107, report["skill_invoke_frame"])
        self.assertEqual(52, report["tail_frames_after_60_plus_111"])
        self.assertEqual("common", report["root"])
        self.assertFalse(report["writes_live"])
        self.assertTrue(report["package_manifest_eligible"])


if __name__ == "__main__":
    unittest.main()
