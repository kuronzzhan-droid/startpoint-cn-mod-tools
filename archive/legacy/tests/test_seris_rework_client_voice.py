"""覆盖Seris普通/真龙完整语音池选择，并拒绝错误分支。"""
from pathlib import Path
import sys
import unittest

pass  # Imports resolve from this checkout/package, not external source copies.
import wf_seris_rework_client_voice as P


class Pool:
    def s(self, i):
        return {10: "ModDualForm", 11: "seris_dragon_king"}[i]

    def mn_name(self, i):
        return {1: "skillVoicePaths", 2: "switchedSkillVoicePaths"}[i]


def fixture():
    I, M = P.asm.Instruction, P.asm.MNEMONICS
    ins = [I(0x02) for _ in range(130)]
    ins[104] = I(M["pushstring"], [10]); ins[111] = I(M["pushstring"], [11])
    ins[113:121] = [I(M["getlocal_3"]), I(M["getproperty"], [1]),
                    I(M["getlocal"], [6]), I(M["convert_i"]), I(M["getproperty"], [14]),
                    I(M["coerce"], [11]), I(M["newarray"], [1]), I(M["jump"], target=128)]
    ins[124] = I(M["getproperty"], [2])
    return ins


def execute(ins, dragon):
    normal = [f"skill_{i}" for i in range(4)]
    switched = [f"matched_skill_{i}" for i in range(4)]
    character = {1: normal, 2: switched}
    pc, stack = 113, []
    while pc != 128:
        x = ins[pc]
        if x.name == "getlocal":
            stack.append(dragon)
        elif x.name == "getlocal_3":
            stack.append(character)
        elif x.name == "getproperty":
            stack.append(stack.pop()[x.args[0]])
        elif x.name == "iffalse":
            if not stack.pop():
                pc = x.target; continue
        elif x.name == "jump":
            pc = x.target; continue
        else:
            raise AssertionError(x.name)
        pc += 1
    return stack


class SerisClientVoiceTests(unittest.TestCase):
    def test_human_keeps_all_four_skill_voices(self):
        ins = P.replace_selection(fixture(), Pool())
        self.assertEqual([[f"skill_{i}" for i in range(4)]], execute(ins, False))

    def test_dragon_uses_all_four_matched_voices(self):
        ins = P.replace_selection(fixture(), Pool())
        self.assertEqual([[f"matched_skill_{i}" for i in range(4)]], execute(ins, True))

    def test_other_instructions_and_targets_are_unchanged(self):
        before = fixture(); after = P.replace_selection(before, Pool())
        self.assertEqual(len(before), len(after))
        for i in (*range(113), *range(121, len(before))):
            a, b = before[i], after[i]
            self.assertEqual((a.name, a.args, a.target), (b.name, b.args, b.target))

    def test_wrong_original_branch_is_rejected(self):
        ins = fixture(); ins[119] = P.asm.Instruction(0x02)
        with self.assertRaisesRegex(P.asm.AsmError, "branch differs"):
            P.replace_selection(ins, Pool())


if __name__ == "__main__":
    unittest.main()
