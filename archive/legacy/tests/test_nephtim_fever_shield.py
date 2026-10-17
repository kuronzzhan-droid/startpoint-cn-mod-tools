"""校奈芙原生护盾的目标、增强/Fever 接入边界与 DSL 编码回归。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
import zlib

pass  # Imports resolve from this checkout/package, not external source copies.
import wf_client_legality as legality
import wf_dsl
import wf_dsl_sig
import wf_nephtim_fever_shield as shield
import wf_nephtim_fever_skill as skill
import wf_nephtim_fever_abilities as abilities
import wf_nephtim_fever_leader as leader
from test_bianca_dragon_abilities import official_sources
from wf_character_revision import encode_tree


def nodes(tree, name):
    if not isinstance(tree, list):
        return []
    return ([tree] if tree and tree[0] == name else []) + [
        node for child in tree for node in nodes(child, name)]


def without_barriers(tree):
    """Support both the pre-integration fixture and the final real generator."""
    tree = deepcopy(tree)
    enhanced = nodes(tree, "ConditionalsChangeSkillFlag")[0]
    fever = nodes(enhanced, "ConditionalsFeverMode")[0]
    existing = nodes(tree, "CreateBarrier")
    if existing:
        if len(existing) != 2 or fever[1][1][-1] != shield.grant_barriers():
            raise AssertionError("shield must occur exactly once in the existing enhanced Fever branch")
        fever[1][1].pop()
    return tree


def integrate(tree):
    """Mirror the single agreed append in the real skill's existing true branch."""
    tree = without_barriers(tree)
    enhanced = nodes(tree, "ConditionalsChangeSkillFlag")[0]
    fever = nodes(enhanced, "ConditionalsFeverMode")[0]
    fever[1][1].append(shield.grant_barriers())
    return tree


def executed_barriers(tree, *, enhanced, fever):
    if not isinstance(tree, list) or not tree:
        return []
    if tree[0] == "ConditionalsChangeSkillFlag":
        return executed_barriers(tree[2 if enhanced else 3], enhanced=enhanced, fever=fever)
    if tree[0] == "ConditionalsFeverMode":
        return executed_barriers(tree[1 if fever else 2], enhanced=enhanced, fever=fever)
    if tree[0] == "CreateBarrier":
        return [tree]
    return [item for child in tree
            for item in executed_barriers(child, enhanced=enhanced, fever=fever)]


class NephtimFeverShieldTests(unittest.TestCase):
    def test_targets_are_dark_primary_and_all_balls_without_duplicate_dark_balls(self):
        finds = nodes(shield.grant_barriers(), "FindAllSubjects")
        self.assertEqual([(node[2], node[3]) for node in finds], [(82, [6]), (86, [])])
        self.assertEqual(len({node[1] for node in finds}), 2)
        for node in finds:
            self.assertEqual(node[4:8], [[], [], [], []])
            self.assertEqual(node[8], ["DoNothing"])
            self.assertEqual(nodes(node, "CreateBarrier"), [
                ["CreateBarrier", node[1], skill.value(0.1), ["GenericBarrierHitEffect"]]])
        self.assertFalse(nodes(shield.grant_barriers(), "TargetMate"))

    def test_real_skill_keeps_both_original_gates_for_both_levels(self):
        for level in (1, 2):
            tree = integrate(skill.build_skill(level))
            for enhanced, fever in ((False, False), (False, True), (True, False), (True, True)):
                self.assertEqual(len(executed_barriers(tree, enhanced=enhanced, fever=fever)),
                                 2 if enhanced and fever else 0)

    def test_append_preserves_all_existing_skill_nodes_and_unique_refresh(self):
        for level in (1, 2):
            before = without_barriers(skill.build_skill(level))
            integrated = integrate(before)
            enhanced = nodes(integrated, "ConditionalsChangeSkillFlag")[0]
            fever = nodes(enhanced, "ConditionalsFeverMode")[0]
            self.assertEqual(fever[1][1][-1], shield.grant_barriers())
            fever[1][1].pop()
            self.assertEqual(encode_tree(integrated), encode_tree(before))
            self.assertEqual(nodes(integrated, "ACUnique"), nodes(before, "ACUnique"))

    def test_integrated_dsl_roundtrip_registry_and_subject_binding(self):
        for level in (1, 2):
            tree = integrate(skill.build_skill(level))
            self.assertEqual(wf_dsl.parse_dsl(zlib.decompress(encode_tree(tree), -15))["tree"], tree)
            self.assertFalse(legality.action_dsl_subject_binding_problems(tree))
            self.assertFalse(legality.action_dsl_element_problems(tree, character_element=5))
            self.assertFalse(legality.action_dsl_hit_area_target_problems(tree))
            for wrapped in nodes(tree, "Command"):
                command = wrapped[1]
                self.assertEqual(len(command) - 1, len(wf_dsl_sig.COMMANDS[command[0]]))

    def test_no_new_state_timer_damage_or_client_capability(self):
        tree = shield.grant_barriers()
        for name in ("CreateCondition", "Event", "CreateNormalAttack", "CreateRatioAttack",
                     "ConsumeUniqueCondition", "ChangeSkillFlag", "CreateSummonsMultiball"):
            self.assertFalse(nodes(tree, name), name)
        meta = shield.metadata()
        self.assertEqual(meta["max_hp_reference"], "each_recipient")
        self.assertEqual(meta["ratio"], 0.1)
        self.assertEqual(meta["required_capabilities"], [])
        self.assertIsNone(meta["duration_frames"])
        tree[1].clear()
        self.assertEqual(len(shield.grant_barriers()[1]), 2)

    def test_gate_metadata_names_the_leader_flag_where_generators_place_it(self):
        # 作者 2026-09-27（方案B）：I536 强化开关由能力1搬入队长；护盾门的元数据须随之指向队长。
        source, _ = official_sources()
        leader_flags = [row for row in leader.leader_rows(source) if row[45] == "536"]
        ability_flags = [row for rows in abilities.ability_rows(source).values()
                         for row in rows if row[47] == "536"]
        self.assertEqual(1, len(leader_flags))
        self.assertEqual([], ability_flags)
        gates = shield.metadata()["gates"]
        self.assertTrue(gates.startswith("leader I536 flag"), gates)
        self.assertNotIn("A1", gates)
        self.assertEqual(gates, skill.metadata()["enhanced_fever_shield"]["gates"])


if __name__ == "__main__":
    unittest.main()
