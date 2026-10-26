"""真实官方 donor 与反编译引擎约束验证；不修改 live。"""
from __future__ import annotations

from wf.paths import root_path

from copy import deepcopy
from pathlib import Path
import sys
import unittest

pass  # Imports resolve from this checkout/package, not external source copies.
import wf_bianca_dragon_bridge as bridge
import wf_campus_bianca as campus

AS3 = Path(('${WF_ROOT}/outputs/re-workspace/decompile/scripts/pinball'.replace("${WF_ROOT}", str(root_path()))))


class BiancaDragonDescriptionTests(unittest.TestCase):
    def test_skill_enhancement_text_keeps_effects_without_numbers(self):
        flat = bridge.flat_string_rows()[bridge.CHANGE_SKILL_STRING_ID][0][0]
        power = bridge.power_up_string_rows()[bridge.CHANGE_SKILL_STRING_ID]["1"][0][0]
        for description in (flat, power):
            self.assertIn("幼龙吐息", description)
            self.assertIn("全场敌人", description)
            self.assertIn("能力伤害抗性", description)
            self.assertNotRegex(description, r"[0-9%％]")
        self.assertIn("恢复自身技能槽", power)
        self.assertIn("队长攻击力", power)


class BiancaDragonBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (campus.ROOT / "mod-tools/profiles.json").is_file():
            raise unittest.SkipTest("official fixture unavailable")
        cls.source = campus.Builder().official_rows("master/ability/ability.orderedmap")

    def test_support_is_real_fire_ability_damage_from_triggering_member(self):
        before = deepcopy(self.source["1310202"])
        row = bridge.support_damage_rows(self.source)[bridge.SUPPORT_ABILITY_ID][0]
        self.assertEqual(row[6:8], ["187", "0"])
        self.assertEqual(row[12], str(bridge.BREATH_UNIQUE_ID))
        self.assertEqual(row[27:30], ["185", "5", "(None)"])
        self.assertEqual(row[34:36], ["(None)", "0"])
        self.assertEqual(row[37], str(bridge.BREATH_UNIQUE_ID))
        self.assertEqual(row[47:49], ["251", "7"])
        self.assertEqual(row[51:53], ["5000000", "5000000"])
        self.assertEqual(row[69], "(None)", "AllEnemyDamage, not timed nearest-order shots")
        self.assertEqual(self.source["1310202"], before)

    def test_enhancement_only_exists_in_learned_a1_and_fire_resonance(self):
        rows = bridge.a1_enhancement_rows(self.source)
        for row in rows:
            self.assertEqual(row[0:2], [bridge.CODE + "_1", "false"])
            self.assertEqual((row[6], row[9], row[10], row[11]),
                             ("2", "600000", "600000", "Red"))
        flag, charge, attack = rows
        self.assertEqual((flag[27], flag[47], flag[70]),
                         ("0", "536", bridge.CHANGE_SKILL_STRING_ID))
        self.assertEqual((charge[27], charge[28], charge[37], charge[47], charge[48]),
                         ("185", "0", str(bridge.BREATH_UNIQUE_ID), "211", "0"))
        # 2026-09-27 平衡第二批（wf_balance_20260927b_bianca）：吐息自充 50% → 20%。
        self.assertEqual(charge[51:53], ["20000", "20000"])
        self.assertEqual((attack[47], attack[48]), ("0", "2"))
        self.assertEqual(attack[51:53], ["200000", "200000"])
        self.assertEqual(attack[57:59], ["90000000", "90000000"])

    def test_unique_refresh_has_single_layer_and_forced_member_application(self):
        rows = bridge.unique_condition_rows()
        self.assertEqual(set(rows), {"11998901", "11998902"})
        for value in rows.values():
            self.assertEqual(len(value[0]), 15)
            self.assertEqual(value[0][3:5], ["900", "1"])
            self.assertEqual(value[0][9:14], ["false", "true", "0", "0", "true"])
        self.assertEqual(set(bridge.icon_reuse_paths().values()), {bridge.ICON_SOURCE})

    @unittest.skipUnless(AS3.is_dir(), "native source fixture unavailable")
    def test_native_bridge_contract(self):
        slot = (AS3 / "scene/battle/battle/ability/AbilitySlotImpl.as").read_text()
        start = slot.index("public function setupTriggerPullerHandler")
        stop = slot.index("public function setupDuringChecker", start)
        self.assertIn("squadManager.primary.members", slot[start:stop])
        target = slot[slot.index("public function forEachInstantContentTarget"):]
        self.assertIn("case 5:\n               if(param2 != null)", target)
        self.assertIn("param4(param2);", target)
        condition = (AS3 / "scene/battle/battle/condition/ConditionSlot.as").read_text()
        self.assertIn("_loc20_ = _loc25_.addedTime != frameCount;", condition)
        self.assertIn("_loc65_.executeIfMatch(ownerEnemy,param1.content);", condition)
        shot = (AS3 / "scene/battle/battle/ability/AbilityDamageShot.as").read_text()
        self.assertIn('"createdByAbility":true', shot)
        self.assertIn('"createdByMainSkillAction":false', shot)
        factory = (AS3 / "scene/battle/battle/squad/MultiballFactory.as").read_text()
        self.assertIn("_loc14_.support_skill1", factory)
        self.assertNotIn("isLearned", factory)


if __name__ == "__main__":
    unittest.main()
