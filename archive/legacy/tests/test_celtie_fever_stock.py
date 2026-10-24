"""快门消费原生数据合同；阶段模型不代表真机或战斗运行验收。"""

from wf.paths import root_path
from copy import deepcopy
from pathlib import Path
import sys
import unittest

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_celtie_fever_abilities as abilities
import wf_celtie_fever_leader as leader
import wf_celtie_fever_stock as stock
import wf_client_legality as legality
from test_bianca_dragon_abilities import official_sources as leader_sources
from test_celtie_fever_abilities import official_sources

AS3 = Path(('${WF_ROOT}/outputs/re-workspace/decompile/scripts/pinball'.replace("${WF_ROOT}", str(root_path()))))


def simulate_flip(rows, leader_row, inventory, *, main=True, is_leader=True,
                  a2=True, a3=True, wind=True, fever=True):
    """按原生 precontent→DSL→impact(8在9前)解读实际生成数据。"""
    conditions = {stock.STOCK_UID: inventory, stock.GAIN_UID: 21}
    combo, fever_percent = 0, 0
    consumers = []
    if main and is_leader:
        consumers.append([leader_row[0], "false", "special", "0", ""] + leader_row[3:])
    if main and a3:
        consumers.append(rows["1499893"][5])
    pending = []
    paths = {path: stock.spend_action_tree(uid) for uid, _, path in stock.SPEND_MARKERS}
    for row in consumers:
        if not (wind and fever):
            continue
        uid, requested = int(row[45]), int(row[42]) // 100000
        consumed = min(conditions[uid], requested)
        conditions[uid] -= consumed
        if not consumed:
            continue
        for _, command in paths[row[71]][11][1]:
            if command[0] == "AddCombo":
                combo += command[1][0]["min"]
            else:
                pending.append(command)
    # Native ImpactManagerImpl processes all ConditionChanges before cancels.
    for command in pending:
        if command[0] != "CreateCondition":
            continue
        for _, uid, amounts in command[2]:
            conditions[uid] = conditions.get(uid, 0) + amounts[0]["min"]
            if a2 and wind and fever:
                for listener in rows["1499892"][2:]:
                    if int(listener[37]) == uid:
                        fever_percent += int(listener[51]) / 1000
    for command in pending:
        if command[0] == "DeleteCondition":
            conditions.pop(command[2][1], None)
    return combo, fever_percent, conditions


class CeltieFeverStockTest(unittest.TestCase):
    def setUp(self):
        self.rows = abilities.ability_rows(official_sources())
        ability_source, leaders = leader_sources()
        donor = deepcopy(leaders["151001"][0])
        donor[45] = "722"
        donor[46:80] = [""] * 34
        donor[80:83] = ["override_wind_spgirl_4anv", "1,2,3", "native_pf"]
        self.leader = leader.leader_rows(ability_source, {"141201": [donor]})[5]

    def test_zero_one_two_three_layers_reward_only_actual_spending(self):
        for initial, left, combo, fever in ((0, 0, 0, 0), (1, 0, 7, 5),
                                           (2, 0, 14, 10), (3, 1, 14, 10)):
            with self.subTest(initial=initial):
                actual_combo, actual_fever, state = simulate_flip(self.rows, self.leader, initial)
                self.assertEqual((combo, fever), (actual_combo, actual_fever))
                self.assertEqual({stock.STOCK_UID: left, stock.GAIN_UID: 21}, state)

    def test_main_nonleader_and_leader_without_a3_each_consume_once(self):
        for options in ({"is_leader": False}, {"a3": False}):
            with self.subTest(options=options):
                combo, fever, state = simulate_flip(self.rows, self.leader, 3, **options)
                self.assertEqual((7, 5, 2), (combo, fever, state[stock.STOCK_UID]))
        self.assertEqual((0, 0, {stock.STOCK_UID: 3, stock.GAIN_UID: 21}),
                         simulate_flip(self.rows, self.leader, 3, main=False))

    def test_unlearned_a2_retains_combo_but_has_no_fever_reward(self):
        combo, fever, state = simulate_flip(self.rows, self.leader, 3, a2=False)
        self.assertEqual((14, 0, 1, 21),
                         (combo, fever, state[stock.STOCK_UID], state[stock.GAIN_UID]))
        self.assertEqual(2, len(state), "cleanup must also work when A2 is unlearned")

    def test_each_missing_resonance_or_fever_gate_preserves_inventory(self):
        for wind, fever in ((False, False), (False, True), (True, False)):
            with self.subTest(wind=wind, fever=fever):
                self.assertEqual((0, 0, {stock.STOCK_UID: 3, stock.GAIN_UID: 21}),
                                 simulate_flip(self.rows, self.leader, 3, wind=wind, fever=fever))

    def test_micro_actions_have_no_wait_attack_skill_charge_or_inventory_mutation(self):
        for uid, _, _ in stock.SPEND_MARKERS:
            with self.subTest(uid=uid):
                tree = stock.spend_action_tree(uid)
                self.assertEqual(tree, leader._decoded(leader._encoded(tree)))
                self.assertEqual([], legality.action_dsl_subject_binding_problems(tree))
                combo, mark, clear = [c[1] for c in tree[11][1]]
                self.assertEqual(["AddCombo", [{"min": 7, "max": 7}]], combo)
                self.assertEqual(("CreateCondition", -17, [["ACUnique", uid, [{"min": 1, "max": 1}]]]),
                                 (mark[0], mark[1], mark[2]))
                self.assertEqual(["None"], mark[4], "marker application has no hit effect")
                self.assertFalse(mark[9], "T185 requires the ordinary condition slot")
                self.assertEqual(["DeleteCondition", -17, ["DCUnique", uid], 1, 2, "", ["Default"]], clear)
                self.assertNotIn(uid, (stock.STOCK_UID, stock.GAIN_UID))
        with self.assertRaises(ValueError):
            stock.spend_action_tree(stock.STOCK_UID)

    @unittest.skipUnless(AS3.is_dir(), "native decompile fixture unavailable")
    def test_native_phase_order_supports_same_frame_cleanup_and_exact_skill_charge(self):
        manager = (AS3 / "scene/battle/battle/impact/ImpactManagerImpl.as").read_text()
        phase = manager[manager.index("public function proceed()"):]
        self.assertLess(phase.index("if(_loc7_.index == 13)"), phase.index("case 8:"))
        self.assertLess(phase.index("case 8:"), phase.index("if(_loc7_.index == 9)"))
        slot = (AS3 / "scene/battle/battle/condition/ConditionSlot.as").read_text()
        self.assertIn("case 2:\n                     _loc11_ = true;", slot)
        view = (AS3 / "scene/battle/battle/condition/ConditionIconView.as").read_text()
        draw = view[view.index("public function draw("):]
        self.assertIn("object.getConditionsIncludingOuterEnvironments()", draw)
        evaluator = (AS3 / "scene/battle/battle/action/ActionEvaluator.as").read_text()
        deletion = evaluator[evaluator.index("            case 22:", evaluator.index("public function evalCommand")):]
        self.assertIn("ImpactSourceContent.ConditionCancels", deletion[:1200])
        source = (AS3 / "common/data/ability/instant/InstantAbilitySource.as").read_text()
        speed = source[source.index("if(_loc5_ == 688)"):]
        self.assertIn("FixedSpeed(param2.resolveDecimal(_loc6_.strength),Decimal_Impl_.fromInt(0))", speed[:1500])


if __name__ == "__main__":
    unittest.main()
