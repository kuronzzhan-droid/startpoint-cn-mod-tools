"""以现行夏白技能验证原生参考修正不改变追斩、倍率与其他动作。"""

from wf.paths import root_path
import os
from pathlib import Path
import sys
import unittest
import zlib

pass  # Imports resolve from this checkout/package, not external source copies.
import wf_dsl
import wf_summer_bai_ability as ability

FIXTURES = Path(os.environ.get("WF_SUMMER_BAI_FIXTURES",
    ('${WF_ROOT}/startpoint-cn/work/codex_out/summer-bai-ability-20260912/fixtures'.replace("${WF_ROOT}", str(root_path())))))


class NativeReferenceTest(unittest.TestCase):
    @unittest.skipUnless((FIXTURES / "skill-1.deflate").exists(), "requires local current skill fixture")
    def test_only_fever_area_reference_changes_and_roundtrip_is_exact(self):
        for level in (1, 2):
            with self.subTest(level=level):
                raw = (FIXTURES / f"skill-{level}.deflate").read_bytes()
                original = wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]
                revised = ability.native_reference(original)
                old_areas = [n for n in ability.walk(original) if n and n[0] == "CreateHitArea"]
                new_areas = [n for n in ability.walk(revised) if n and n[0] == "CreateHitArea"]
                self.assertEqual([n[24] for n in old_areas], [2, 2, 0])
                self.assertEqual([n[24] for n in new_areas], [2, 2, 2])
                self.assertEqual(old_areas[:2], new_areas[:2])
                encoded = ability.encode_tree(revised)
                self.assertEqual(wf_dsl.parse_dsl(zlib.decompress(encoded, -15))["tree"], revised)
                # 恢复唯一字段后完整树相同，覆盖形状、倍率、全部旗标、时序和特效。
                new_areas[2][24] = 0
                self.assertEqual(revised, original)

    def test_unknown_skill_shape_is_rejected(self):
        with self.assertRaises(ValueError):
            ability.native_reference(["ActionDsl"])

    def test_rerun_never_downgrades_candidate_version(self):
        # 2026-09-27b 平衡批次把候选写回 1.0.3；重跑本修订只保持现值，不回退到 1.0.2。
        self.assertEqual("1.0.2", ability.package_version("1.0.1"))
        self.assertEqual("1.0.2", ability.package_version("1.0.2"))
        self.assertEqual("1.0.3", ability.package_version("1.0.3"))
        self.assertEqual("1.0.10", ability.package_version("1.0.10"))


if __name__ == "__main__":
    unittest.main()
