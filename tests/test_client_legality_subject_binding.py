"""ActionDsl 主体绑定门禁(C16103)的隔离测试。

新增于 2026-08-31,配套 `wf_client_legality.action_dsl_subject_binding_problems`
与 `action_dsl_hit_area_target_problems`。这两条门禁是三个精灵兽包的真机事故
换来的:CreateNormalAttack 的 params[0](主体列)被写成了元素码,元素列 255 合法,
既有的 `action_dsl_element_problems` 全绿,但战斗里第一次判定命中就 C16103。

测试用最小 DSL 骨架,不依赖 store / 官方基线。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path


MOD_TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MOD_TOOLS))

import wf_client_legality  # noqa: E402


def _cmd(node: list) -> list:
    return ["Command", node]


def _block(*commands: list) -> list:
    return ["Block", list(commands)]


def _hit_area(bind_create: int, bind_area: int, bind_target: int, on_hit: list) -> list:
    """CreateHitArea 的 26 个参数,只有绑定位与两个块位有意义,其余填官方常见值。"""
    return [
        "CreateHitArea", "*", -18, ["AB"], 0, 0, 0, True, False,
        ["Circle", [{"min": 200, "max": 200}]],
        ["Center"], ["Center"], ["Single"],
        ["SpecifyHitAreaLifetimeDirectly", 30],
        ["CalculatedUsingMaxNumOfHits", 1],
        ["Some", [{"min": 1, "max": 1}]],
        False, True, ["None"],
        bind_create, ["Block", []],
        bind_area, bind_target, on_hit,
        0, 0, ["None"],
    ]


def _normal_attack(subject: int, element: int = 255) -> list:
    return [
        "CreateNormalAttack", subject, element, [], [], 16,
        [{"min": 2.0, "max": 2.0}], [{"min": 0, "max": 0}],
        False, False, False, False, False,
        [{"min": 1, "max": 1}], [{"min": 1, "max": 1}], ["Fine"], True,
    ]


def _summon(ball: int, member: int, callback: list | None) -> list:
    return ["CreateSummonsMultiball", 1, 1611772, [{"min": 1200, "max": 1200}],
            ["E1", ["None"]], ["None"], ["None"], 0, False,
            "summon_ready", ball, member, callback, None]


def _dsl(*commands: list) -> list:
    return ["ActionDsl", 1, ["None"], False, False, False, False,
            False, False, False, 0, _block(*commands)]


class SubjectBindingTest(unittest.TestCase):
    def test_hit_area_target_subject_is_accepted(self) -> None:
        tree = _dsl(_cmd(_hit_area(0, 1, 2, _block(_cmd(_normal_attack(2))))))
        self.assertEqual(wf_client_legality.action_dsl_subject_binding_problems(tree), [])

    def test_unbound_subject_is_rejected(self) -> None:
        # 事故签名:主体列写成了元素码 3(雷),node[21]/node[22] 是 1/2
        tree = _dsl(_cmd(_hit_area(0, 1, 2, _block(_cmd(_normal_attack(3))))))
        problems = wf_client_legality.action_dsl_subject_binding_problems(tree)
        self.assertEqual(len(problems), 1)
        self.assertIn("16103", problems[0])
        self.assertIn("node[1]=3", problems[0])

    def test_create_hit_area_node19_is_not_visible_in_on_hit(self) -> None:
        """node[19] 只在 node[20] 块里绑定,onHit 里看不见 —— 这正是精灵兽雷的坑。"""
        tree = _dsl(_cmd(_hit_area(3, 4, 5, _block(_cmd(_normal_attack(3))))))
        self.assertEqual(len(wf_client_legality.action_dsl_subject_binding_problems(tree)), 1)

    def test_builtin_negative_subjects_are_accepted(self) -> None:
        for builtin in (-1, -2, -17, -18, -33):
            tree = _dsl(_cmd(_hit_area(0, 1, 2, _block(_cmd(_normal_attack(builtin))))))
            self.assertEqual(
                wf_client_legality.action_dsl_subject_binding_problems(tree), [],
                f"builtin subject {builtin} should be accepted",
            )

    def test_find_all_subjects_binds_node1_into_its_block(self) -> None:
        find = ["FindAllSubjects", 7, 33, [2], [], [], [], [], ["DoNothing"],
                _block(_cmd(_normal_attack(7)))]
        self.assertEqual(wf_client_legality.action_dsl_subject_binding_problems(_dsl(_cmd(find))), [])
        bad = ["FindAllSubjects", 7, 33, [2], [], [], [], [], ["DoNothing"],
               _block(_cmd(_normal_attack(8)))]
        self.assertEqual(len(wf_client_legality.action_dsl_subject_binding_problems(_dsl(_cmd(bad)))), 1)

    def test_find_near_subjects_binds_node5_not_node1(self) -> None:
        # 官方 sleep_puppy 写法:node[1] 是搜索源(-18 球),node[5] 才是绑定 id
        node = ["FindNearSubjects", -18, 1, 49, ["DoNothing"], 0,
                _block(_cmd(_normal_attack(0)))]
        self.assertEqual(wf_client_legality.action_dsl_subject_binding_problems(_dsl(_cmd(node))), [])

    def test_target_mate_binds_following_siblings(self) -> None:
        # 官方 flame_blessgirl 写法:TargetMate 9 之后的同级语句才能用 9
        good = _dsl(_cmd(["TargetMate", 9, [1], [], [], [], []]), _cmd(_normal_attack(9)))
        self.assertEqual(wf_client_legality.action_dsl_subject_binding_problems(good), [])
        bad = _dsl(_cmd(_normal_attack(9)), _cmd(["TargetMate", 9, [1], [], [], [], []]))
        self.assertEqual(len(wf_client_legality.action_dsl_subject_binding_problems(bad)), 1)

    def test_summon_activation_callback_binds_ball_and_member(self) -> None:
        callback = _block(_cmd(["StopBall", 74]), _cmd(["CreateCondition", 75]))
        tree = _dsl(_cmd(_summon(74, 75, callback)))
        self.assertEqual(wf_client_legality.action_dsl_subject_binding_problems(tree), [])

    def test_summon_activation_rejects_a_different_subject(self) -> None:
        callback = _block(_cmd(["CreateCondition", 76]))
        problems = wf_client_legality.action_dsl_subject_binding_problems(
            _dsl(_cmd(_summon(74, 75, callback))))
        self.assertEqual(len(problems), 1)
        self.assertIn("node[1]=76", problems[0])

    def test_summon_binding_does_not_escape_callback(self) -> None:
        tree = _dsl(_cmd(["CreateCondition", 74]),
                    _cmd(_summon(74, 75, _block(_cmd(["CreateCondition", 75])))),
                    _cmd(["CreateCondition", 75]))
        problems = wf_client_legality.action_dsl_subject_binding_problems(tree)
        self.assertEqual(len(problems), 2)
        self.assertIn("node[1]=74", problems[0])
        self.assertIn("node[1]=75", problems[1])

    def test_summon_callback_keeps_outer_scope_and_is_optional(self) -> None:
        callback = _block(_cmd(["CreateCondition", 9]), _cmd(["CreateCondition", 75]))
        tree = _dsl(_cmd(["TargetMate", 9, [1], [], [], [], []]),
                    _cmd(_summon(74, 75, callback)), _cmd(_summon(84, 85, None)))
        self.assertEqual(wf_client_legality.action_dsl_subject_binding_problems(tree), [])


class HitAreaTargetTest(unittest.TestCase):
    def test_node22_is_the_expected_target(self) -> None:
        tree = _dsl(_cmd(_hit_area(0, 1, 2, _block(_cmd(_normal_attack(2))))))
        self.assertEqual(wf_client_legality.action_dsl_hit_area_target_problems(tree), [])

    def test_node21_hits_the_area_itself(self) -> None:
        """挂 node[21] 不抛异常,但伤害落在判定区上 —— 官方 8220/8220 全用 node[22]。"""
        tree = _dsl(_cmd(_hit_area(0, 1, 2, _block(_cmd(_normal_attack(1))))))
        problems = wf_client_legality.action_dsl_hit_area_target_problems(tree)
        self.assertEqual(len(problems), 1)
        self.assertIn("node[21]=1", problems[0])
        self.assertIn("node[22]=2", problems[0])

    def test_create_condition_on_node21_is_also_reported(self) -> None:
        condition = ["CreateCondition", 1, [["ACAttackPoint", [{"min": 900, "max": 900}],
                                             [{"min": 0.3, "max": 0.3}], [{"min": 1, "max": 1}]]],
                     [{"min": 1, "max": 1}], ["GenericConditionHitEffect"],
                     True, False, "", None, False, 3, [{"min": 1, "max": 1}], False]
        tree = _dsl(_cmd(_hit_area(0, 1, 2, _block(_cmd(condition)))))
        self.assertEqual(len(wf_client_legality.action_dsl_hit_area_target_problems(tree)), 1)


if __name__ == "__main__":
    unittest.main()
