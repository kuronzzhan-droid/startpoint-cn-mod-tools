"""Rapid casts and queued buffs on removed summons; bounded native lifecycle only."""

from wf.paths import root_path
from pathlib import Path
import sys
import unittest

pass  # Imports resolve from this checkout/package, not external source copies.
import wf_bianca_dragon_skill as bianca
import wf_nephtim_fever_skill as neph
import wf_nephtim_multiball_direct as a3
import wf_nephtim_multiball_fever as a4
import wf_dsl
import wf_dsl_sig
from campus_summon_lifecycle import bianca_replay, breath_events, neph_replay, function_body

AS3 = Path(('${WF_ROOT}/outputs/re-workspace/decompile/scripts'.replace("${WF_ROOT}", str(root_path()))))


def ball_conditions(tree, target):
    return [node for node in wf_dsl.iter_dsl_commands(tree)
            if node[0] == "CreateCondition" and node[1] == target]


class CampusSummonReentryTests(unittest.TestCase):
    def test_single_breath_keeps_original_effective_departure_tick(self):
        for level in (1, 2):
            result = bianca_replay(bianca.build_skill(level), [(0, "A")])
            self.assertIsNone(result["error"])
            self.assertEqual([x["frame"] for x in result["trace"] if x["event"] == "depart"], [29])
            self.assertEqual(len(breath_events(result)), 1)
            self.assertEqual(sum(x.get("amount", 0) for x in result["trace"]), 250)

    def test_each_overlap_interval_retains_both_casts_and_refreshes_only_departure(self):
        for level in (1, 2):
            for gap in range(30):
                with self.subTest(level=level, gap=gap):
                    result = bianca_replay(bianca.build_skill(level), [(0, "A"), (gap, "A")])
                    self.assertIsNone(result["error"])
                    self.assertEqual(len(breath_events(result)), 2)
                    self.assertEqual(sum(x.get("amount", 0) for x in result["trace"]), 500)
                    self.assertEqual([x["frame"] for x in result["trace"] if x["event"] == "depart"], [gap+29])

    def test_three_casts_and_another_owner_remain_independent(self):
        result = bianca_replay(bianca.build_skill(2), [(0, "A"), (0, "B"), (12, "A"), (24, "A")],
                               initial_owners=("A", "B"))
        self.assertIsNone(result["error"])
        self.assertEqual(len(breath_events(result)), 4)
        self.assertEqual(sum(x.get("amount", 0) for x in result["trace"]), 1000)
        self.assertEqual([(x["owner"], x["frame"]) for x in result["trace"] if x["event"] == "depart"],
                         [("B", 29), ("A", 53)])

    def test_old_callbacks_do_not_touch_a_new_generation_after_death(self):
        for death, recast in ((10, 12), (25, 25)):
            result = bianca_replay(bianca.build_skill(2), [(0, "A"), (recast, "A")], {death: ["A"]})
            self.assertIsNone(result["error"])
            spawn = next(x for x in result["trace"] if x["event"] == "spawn")
            self.assertFalse(any(x["event"] in ("depart", "dragon_condition", "self_condition", "fever")
                                 for x in result["trace"] if x["frame"] >= spawn["frame"]))

    def test_delayed_breath_omits_a_dead_dragon_without_respawn(self):
        result = bianca_replay(bianca.build_skill(1), [(0, "A")], {10: ["A"]})
        self.assertIsNone(result["error"])
        self.assertEqual(breath_events(result), [])

    def test_only_summon_buffs_skip_death_during_cutin_and_keep_live_behavior(self):
        for tree, target in [(neph.build_skill(level), 71) for level in (1, 2)] + [
                (a3.action_tree(), 71), (a4.action_tree(), 81)]:
            current = ball_conditions(tree, target)
            previous = [node[:-1] + [True] for node in current]
            for count in (1, 9):
                modes = ["AllEntities", "OnlySquad", "OnlySquad", "AllEntities"]
                self.assertEqual(neph_replay(previous, modes, count)["error"], "G1008")
                result = neph_replay(current, modes, count)
                self.assertIsNone(result["error"])
                self.assertEqual(result["trace"].count("skip_dead"), len(current)*count)
                self.assertEqual(neph_replay(current, ["AllEntities"]*4, count),
                                 neph_replay(previous, ["AllEntities"]*4, count))

    def test_find_all_missing_policy_is_native_enum_not_empty_expression(self):
        trees = [bianca.build_skill(1), neph.build_skill(1), a3.action_tree(), a4.action_tree()]
        for tree in trees:
            for node in wf_dsl.iter_dsl_commands(tree):
                if node[0] == "FindAllSubjects":
                    policy = node[8]
                    constructors = wf_dsl_sig.ENUMS["IfTargetNotFound"]
                    self.assertIn(policy[0], constructors)
                    self.assertEqual(len(policy)-1, len(constructors[policy[0]]))

    @unittest.skipUnless(AS3.is_dir(), "optional native decompile evidence unavailable")
    def test_native_lifecycle_and_unique_override_match_replay(self):
        def read(path):
            return (AS3 / path).read_text(encoding="utf-8-sig")
        prefix = "pinball/scene/battle/battle/"
        evaluator = read(prefix + "action/ActionEvaluator.as")
        update = function_body(evaluator, "update")
        self.assertLess(update.index("_loc2_.updatePhase()"),
                        update.index("_loc2_.evaluationPhase(dispatchedEvents)"))
        self.assertIn("new UniqueConditionLogic(_loc24_,get_zone().asset).get_forceApply()", evaluator)
        self.assertIn("manager.removeEvent(_loc8_,get_executor())", evaluator)
        wait = read(prefix + "action/ListeningEvent.as")
        self.assertIn("frameCount = -1;", wait)
        self.assertIn("frameCount == int(_loc4_.params[0])", wait)
        manager = read(prefix + "action/ActionEvaluatorManager.as")
        self.assertIn("_loc4_.get_executor() == param2", function_body(manager, "removeEvent"))
        battle = read(prefix + "Battle.as")
        full = function_body(battle, "stepLifeCycleAsAllEntitiesMode")
        only = function_body(battle, "stepLifeCycleAsOnlySquadMode")
        self.assertLess(full.index("zoneManager.updatePhase()"), full.index("zoneManager.impactPhase()"))
        self.assertLess(full.index("zoneManager.impactPhase()"), full.index("squadManager.removalPhase"))
        self.assertIn("squadManager.removalPhase", only)
        self.assertNotIn("zoneManager", only)
        member = read(prefix + "squad/member/MemberImpl.as")
        self.assertIn("if((!isDead() || _loc4_) && _loc3_)", function_body(member, "applyImpact"))
        self.assertIn("gear.absorbWithKey(BattleDiffuseKey.KBattleId", function_body(member, "internalApplyConditionChanges"))
        self.assertIn("throw new SipoError(1008,", function_body(read("jp/sipo/gipo/core/Gear.as"), "absorbWithKey"))


if __name__ == "__main__":
    unittest.main()
