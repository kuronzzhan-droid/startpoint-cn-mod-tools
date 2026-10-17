"""原生FindMultiballSubjects和ActivatedMultiball事件的独立作用域。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wf_client_legality import action_dsl_subject_binding_problems as problems


def block(*nodes):
    return ["Block", list(nodes)]


def consume(subject):
    return ["Command", ["AddSkillPoint", subject, [{"min": 1, "max": 1}]]]


def find(absent, present):
    return ["Command", ["FindMultiballSubjects", 10, 11, True, [1199891], absent, present]]


class MultiballBindingTests(unittest.TestCase):
    def test_present_branch_binds_both_ball_and_member(self):
        self.assertEqual(problems(find(block(), block(consume(10), consume(11)))), [])

    def test_absent_branch_has_neither_binding(self):
        errors = problems(find(block(consume(10), consume(11)), block()))
        self.assertEqual(len(errors), 2)

    def test_find_bindings_do_not_escape(self):
        errors = problems(block(find(block(), block(consume(10), consume(11))), consume(10), consume(11)))
        self.assertEqual(len(errors), 2)

    def test_activation_event_binds_both_and_does_not_escape(self):
        event = ["Event", ["ActivatedMultiballOfExecutorSelf", "activation", 10, 11,
                           block(consume(10), consume(11))]]
        self.assertEqual(problems(event), [])
        self.assertEqual(len(problems(block(event, consume(10), consume(11)))), 2)


if __name__ == "__main__":
    unittest.main()
