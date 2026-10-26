"""技能目标、原生DSL、限时轮转与普通协力球的回归检查。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
import zlib

pass  # Imports resolve from this checkout/package, not external source copies.
import wf_client_legality as legality
import wf_dsl
import wf_dsl_sig
import wf_nephtim_fever_skill as skill
from wf_character_revision import encode_tree


def nodes(tree, name):
    if not isinstance(tree, list):
        return []
    return ([tree] if tree and tree[0] == name else []) + [
        found for child in tree for found in nodes(child, name)]


class NativePhaseModel:
    """Transcribe only native control flow/ConditionSlot signed consumption.

    The expiry is external; native consume changes accumulation only, unlike
    adding an ACUnique which may refresh the existing time limit.
    """
    def __init__(self, count=1, fever=True, summons=()):
        self.count, self.fever = count, fever
        self.now = 0
        self.expiry = 1200
        self.summons = list(summons)
        self.conditions = []

    def run(self, node):
        if node[0] == "ActionDsl":
            return self.run(node[11])
        if node[0] == "Block":
            for child in node[1]:
                self.run(child)
        elif node[0] == "Command":
            self.run(node[1])
        elif node[0] == "ConditionalsFeverMode":
            self.run(node[1 if self.fever else 2])
        elif node[0] == "ConditionalsChangeSkillFlag":
            self.run(node[2])
        elif node[0] == "ConditionalsConditionExist":
            self.run(node[3 if self.count else 4])
        elif node[0] == "ConditionalsConditionAccumulationNumber":
            self.run(node[3 if self.count >= node[2] else 4])
        elif node[0] == "ConditionalsMultiballNumber":
            # Native counts only the listed ids; [] matches nothing, null would be "all".
            present = sum(1 for uid in self.summons if uid in node[1])
            self.run(node[4 if present >= node[3] else 5])
        elif node[0] == "ConsumeUniqueCondition":
            if self.count:
                self.count -= min(self.count, node[3][1])
        elif node[0] == "CreateSummonsMultiball":
            self.summons.extend([node[2]] * node[1])
            self.run(node[12])
        elif node[0] == "CreateCondition":
            self.conditions.append(node)
            for content in node[2]:
                if content[0] == "ACUnique":
                    added = content[2][0]["max"] * node[11][0]["max"]
                    if self.count or added > 0:
                        self.count = min(2, self.count + added)
                        self.expiry = max(self.expiry, self.now + 1200)


class NephtimSkillTests(unittest.TestCase):
    def test_only_existing_ball_plain_buffs_stop_forcing_dead_targets(self):
        for level in (1, 2):
            conditions = nodes(skill.build_skill(level), "CreateCondition")
            ball = [node for node in conditions if node[1] == 71]
            self.assertEqual(len(ball), 1)
            self.assertEqual({node[2][0][0] for node in ball},
                             {"ACAttackPoint"})
            self.assertTrue(all(node[12] is False for node in ball))
            self.assertTrue(all(node[12] is True for node in conditions if node[1] != 71))
        for kind in ("light", "dark"):
            born = nodes(skill.summon(kind), "CreateCondition")
            self.assertEqual(len(born), 1)
            self.assertIs(born[0][12], True)
            self.assertTrue(nodes(born[0], "ACHealRejection"))

    def test_three_programs_roundtrip_and_native_instruction_bindings(self):
        for tree in (skill.build_skill(1), skill.build_skill(2), skill.build_spawn()):
            self.assertEqual(wf_dsl.parse_dsl(zlib.decompress(encode_tree(tree), -15))["tree"], tree)
            problems = (legality.action_dsl_element_problems(tree, character_element=5)
                        + legality.action_dsl_subject_binding_problems(tree)
                        + legality.action_dsl_hit_area_target_problems(tree))
            self.assertFalse(problems, problems)
            for kind, registry in (("Command", wf_dsl_sig.COMMANDS), ("Event", wf_dsl_sig.EVENTS)):
                for wrapped in nodes(tree, kind):
                    command = wrapped[1]
                    self.assertIn(command[0], registry)
                    self.assertEqual(len(command)-1, len(registry[command[0]]), command[0])
        with self.assertRaises(ValueError):
            skill.build_skill(3)

    def test_base_covers_local_party_balls_and_remote_piercing(self):
        tree = skill.build_skill(2)
        finds = nodes(tree, "FindAllSubjects")
        base = next(node for node in finds if node[2] == 33)
        self.assertEqual(base[3], [])
        self.assertTrue(nodes(base, "ACDirectDamage"))
        self.assertTrue(nodes(base, "ACPiercing"))
        # 主动技能本体的数值不属能力1/能力3，2026-09-17 的减半不许碰到它们。
        self.assertEqual(nodes(base, "ACDirectDamage")[0][2], skill.value(2))
        attacks = nodes(tree, "ACAttackPoint")
        self.assertTrue(attacks)
        self.assertEqual([skill.value(2.5)] * len(attacks), [node[2] for node in attacks])
        self.assertEqual(nodes(tree, "TargetMate"), [["TargetMate", 73, [], [], [], [], []]])
        remote = next(node for node in nodes(tree, "CreateCondition") if node[1] == 73)
        self.assertEqual(remote[2], [["ACPiercing", skill.value(1200)]])
        for source in (82, 86):
            for find in (node for node in finds if node[2] == source):
                self.assertEqual(find[3], [6] if source == 82 else [])

    def test_double_hits_and_newborn_buffs_are_not_inherited_implicitly(self):
        for kind in ("light", "dark"):
            summon = skill.summon(kind)[1]
            self.assertEqual(summon[0], "CreateSummonsMultiball")
            self.assertEqual(summon[3], skill.value(1500))
            callback = summon[12]
            self.assertEqual(nodes(callback, "ACAttackPoint"),
                             [["ACAttackPoint", skill.value(1200), skill.value(2.5), skill.value(1)]])
            self.assertTrue(nodes(callback, "ACDirectDamage"))
            self.assertTrue(nodes(callback, "ACPiercing"))
            self.assertFalse(nodes(callback, "ACAdditionalDirectAttack"))
            self.assertFalse(nodes(callback, "ACUnique"), "callbacks must not extend tea expiry")
            self.assertEqual(nodes(callback, "ACHealRejection"),
                             [["ACHealRejection", skill.value(1500)]])
            for name in ("ACAttackPoint", "ACDirectDamage", "ACPiercing"):
                self.assertEqual(nodes(callback, name)[0][1], skill.value(1200),
                                 "25s ball lifetime must not extend the 20s newborn buffs")
        self.assertEqual(skill.metadata()["each_ball_lifetime_frames"], 1500)
        self.assertEqual(skill.metadata()["duration_frames"], 1200)

    def test_phase_alternates_until_the_cap_without_refreshing_expiry(self):
        model = NativePhaseModel()
        program = skill.build_spawn()
        for _ in range(99):
            model.run(program)
            self.assertIn(model.count, (1, 2))
        expected = ([skill.LIGHT_ID, skill.DARK_ID] * skill.MULTIBALL_CAP)[:skill.MULTIBALL_CAP]
        self.assertEqual(model.summons, expected)
        self.assertEqual(len(model.summons), skill.MULTIBALL_CAP)
        self.assertEqual(model.expiry, 1200)

    def test_repeated_callback_and_late_callback_do_not_grow_or_recreate_state(self):
        for count, kind, expected in ((1, "light", 2), (2, "dark", 1)):
            model = NativePhaseModel(count)
            callback = skill.summon(kind)[1][12]
            model.run(callback)
            model.run(callback)
            self.assertEqual(model.count, expected)
            model.count = 0
            model.run(callback)
            self.assertEqual(model.count, 0)
        for count, fever in ((0, True), (1, False), (2, False)):
            model = NativePhaseModel(count, fever)
            model.run(skill.build_spawn())
            self.assertEqual(model.summons, [])
            model.run(skill.summon("light")[1][12])
            self.assertEqual(model.count, count)

    def test_recasting_refreshes_duration_without_breaking_light_dark_alternation(self):
        model = NativePhaseModel()
        for index in range(99):
            model.run(skill.build_spawn())
            old_phase = model.count
            model.now = (index+1) * 120
            model.run(skill.build_skill(2))
            self.assertEqual(model.count, old_phase)
            self.assertEqual(model.expiry, model.now+1200)
        self.assertEqual(model.summons,
                         ([skill.LIGHT_ID, skill.DARK_ID] * skill.MULTIBALL_CAP)[:skill.MULTIBALL_CAP])
        zero_refresh = next(node for node in nodes(skill.build_skill(2), "CreateCondition")
                            if node[11] == skill.value(0))
        model.count = 0
        model.run(zero_refresh)
        self.assertEqual(model.count, 0, "late zero refresh must not recreate an expired state")

    def test_cap_gate_counts_only_her_own_balls_and_is_declared_explicitly(self):
        gates = nodes(skill.build_spawn(), "ConditionalsMultiballNumber")
        self.assertEqual(len(gates), 1)
        gate = gates[0]
        # [] would match no ball at all (only null means "every multiball"), so the
        # ids must be spelled out or the cap silently never fires.
        self.assertEqual(gate[1], [skill.LIGHT_ID, skill.DARK_ID])
        self.assertTrue(gate[1])
        self.assertEqual(gate[2], [])
        self.assertEqual(gate[3], skill.MULTIBALL_CAP)
        self.assertEqual(skill.MULTIBALL_CAP, 9)
        self.assertTrue(nodes(gate[4], "CreateCondition"))
        self.assertFalse(nodes(gate[4], "CreateSummonsMultiball"))
        self.assertTrue(nodes(gate[5], "CreateSummonsMultiball"))
        # The summon branch may still buff the newborn ball; it must not stack anything on self.
        self.assertFalse([node for node in nodes(gate[5], "CreateCondition") if node[1] == -17])
        self.assertFalse([content for content in nodes(gate[5], "ACAttackPoint")
                          if content[3] == skill.value(skill.OVERFLOW_ATTACK_STACKS)])

    def test_overflow_attack_replaces_the_summon_only_once_the_cap_is_reached(self):
        full = NativePhaseModel(summons=[skill.LIGHT_ID] * skill.MULTIBALL_CAP)
        full.run(skill.build_spawn())
        self.assertEqual(len(full.summons), skill.MULTIBALL_CAP, "no ball past the cap")
        self.assertEqual([content[0] for node in full.conditions for content in node[2]],
                         ["ACAttackPoint"])
        overflow = full.conditions[0]
        self.assertEqual(overflow[1], -17)
        self.assertEqual(overflow[2], [["ACAttackPoint", skill.value(skill.DURATION),
                                        skill.value(skill.OVERFLOW_ATTACK_STRENGTH),
                                        skill.value(skill.OVERFLOW_ATTACK_STACKS)]])
        # The third ACAttackPoint value is maxAccumulation; one layer is added per run
        # and native clamps the total, so magnification must stay 1 and forceApply true.
        self.assertEqual(overflow[2][0][3], skill.value(skill.OVERFLOW_ATTACK_STACKS))
        self.assertEqual(skill.OVERFLOW_ATTACK_STACKS, 99)
        # 作者 2026-09-17 减半：溢出攻击力 +50%/层 → +25%/层；层数上限与 20 秒时长不动。
        self.assertEqual(skill.OVERFLOW_ATTACK_STRENGTH, 0.25)
        self.assertEqual(skill.overflow_attack_percent(), 25)
        self.assertEqual(overflow[2][0][1], skill.value(1200))
        self.assertEqual(overflow[11], skill.value(1))
        self.assertIs(overflow[12], True)
        self.assertEqual(overflow[10], 3)
        self.assertEqual(overflow[4], ["GenericConditionHitEffect"])

        below = NativePhaseModel(summons=[skill.LIGHT_ID] * (skill.MULTIBALL_CAP - 1))
        below.run(skill.build_spawn())
        self.assertEqual(len(below.summons), skill.MULTIBALL_CAP, "the cap must not be off by one")
        # Below the cap only the newborn ball (subject 75) may be buffed; nothing lands on self.
        self.assertEqual([node[1] for node in below.conditions], [75])
        self.assertFalse([node for node in below.conditions if node[1] == -17],
                         "no attack stack while a ball can still be summoned")
        for gate in ("fever", "state"):
            blocked = NativePhaseModel(count=0 if gate == "state" else 1,
                                       fever=gate != "fever",
                                       summons=[skill.LIGHT_ID] * skill.MULTIBALL_CAP)
            blocked.run(skill.build_spawn())
            self.assertEqual(blocked.conditions, [], gate)

    def test_cap_and_overflow_are_reported_in_package_metadata(self):
        meta = skill.metadata()
        self.assertEqual(meta["multiball_cap"], skill.MULTIBALL_CAP)
        self.assertEqual(meta["overflow_attack_percent"], 25)
        self.assertEqual(meta["overflow_attack_max_stacks"], skill.OVERFLOW_ATTACK_STACKS)
        self.assertEqual(meta["overflow_attack_frames"], skill.DURATION)
        self.assertEqual(meta["overflow_counts_ids"], [skill.LIGHT_ID, skill.DARK_ID])
        self.assertIs(meta["overflow_count_includes_inactive_balls"], True)
        self.assertIs(meta["overflow_count_origin_filtered"], False)

    def test_active_buff_refresh_does_not_recreate_or_renew_existing_ball_lifetime(self):
        for level in (1, 2):
            active = skill.build_skill(level)
            self.assertFalse(nodes(active, "CreateSummonsMultiball"))
            self.assertFalse(nodes(active, "RemoveMultiball"))
            for name in ("ACAttackPoint", "ACDirectDamage", "ACPiercing", "ACAdditionalDirectAttack"):
                for content in nodes(active, name):
                    self.assertEqual(content[1], skill.value(1200))
        self.assertEqual([node[3] for node in nodes(skill.build_spawn(), "CreateSummonsMultiball")],
                         [skill.value(1500), skill.value(1500)])
        self.assertEqual(skill.unique_rows()[str(skill.STATE_UID)][0][3], "1200")

    def test_one_timed_hud_state_and_multiball_curves_supports_preserved(self):
        rows = skill.unique_rows()
        self.assertEqual(set(rows), {str(skill.STATE_UID)})
        self.assertEqual(rows[str(skill.STATE_UID)][0][3:5], ["1200", "2"])
        self.assertEqual(rows[str(skill.STATE_UID)][0][13], "true")
        donor = ["native_1", "native", "5", "5"] + [str(i) for i in range(4, 30)]
        multiballs, levels = {"1611772": [donor]}, {
            "1611772": [["native_hp_curve", "465", "1", "native_atk_curve", "680", "1"]]}
        before = deepcopy((multiballs, levels))
        result = skill.multiball_rows(multiballs, levels)
        for uid, element in ((skill.LIGHT_ID, "4"), (skill.DARK_ID, "5")):
            row = result["master/battle/multiball/multiball.orderedmap"][str(uid)][0]
            self.assertEqual(row[2], donor[2])
            self.assertEqual(row[3], element)
            self.assertEqual(row[4:], donor[4:])
            self.assertEqual(result["master/battle/multiball/multiball_level.orderedmap"][str(uid)],
                             [["native_hp_curve", "465", "1", "native_atk_curve", "680", "1"]])
        self.assertEqual((multiballs, levels), before)


if __name__ == "__main__":
    unittest.main()
