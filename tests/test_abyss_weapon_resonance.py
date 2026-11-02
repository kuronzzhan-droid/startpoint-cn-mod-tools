"""Native condition regression tests independent of live store and client state."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wf_abyss_weapon_resonance as resonance
import wf_rogue_rewards as rewards
from test_rogue_rewards import fake_templates


class AbyssResonanceTests(unittest.TestCase):
    def row(self, kind):
        width, start = resonance.LAYOUTS[kind]
        row = [f"keep-{i}" for i in range(width)]
        for i in (start, start + 7, start + 14):
            row[i:i + 7] = resonance.EMPTY
        return row

    def test_all_twelve_elements_and_both_schemas(self):
        for kind, (_, start) in resonance.LAYOUTS.items():
            for index in range(12):
                key = str(8000101 + index)
                original = self.row(kind)
                result = resonance.gate_row(original, key, kind)
                group = ("Red", "Blue", "Yellow", "Green", "White", "Black")[index // 2]
                self.assertEqual(["2", "", "", "600000", "600000", group, ""], result[start:start + 7])
                result[start:start + 7] = resonance.EMPTY
                self.assertEqual(original, result)

    def test_existing_hp_gate_remains_and_resonance_uses_next_block(self):
        for kind, (_, start) in resonance.LAYOUTS.items():
            row = self.row(kind)
            hp = ["8", "0", "", "20000", "20000", "", ""]
            row[start:start + 7] = hp
            result = resonance.gate_row(row, "8000112", kind)
            self.assertEqual(hp, result[start:start + 7])
            self.assertEqual(["2", "", "", "600000", "600000", "Black", ""], result[start + 7:start + 14])
            self.assertEqual(result, resonance.gate_row(result, "8000112", kind))

    def test_universal_three_are_exactly_unchanged(self):
        for kind in resonance.LAYOUTS:
            for key in ("8000113", "8000114", "8000115"):
                row = self.row(kind)
                self.assertEqual(row, resonance.gate_row(row, key, kind))

    def test_no_free_block_fails_instead_of_dropping_conditions(self):
        row = self.row("ability_soul")
        for i in (3, 10, 17):
            row[i:i + 7] = ["42", "", "", "", "", "", ""]
        with self.assertRaisesRegex(ValueError, "no empty"):
            resonance.gate_row(row, "8000101", "ability_soul")

    def test_rejects_foreign_weapon_and_wrong_schema(self):
        with self.assertRaisesRegex(ValueError, "not one"):
            resonance.gate_row(self.row("ability_soul"), "5900101", "ability_soul")
        with self.assertRaisesRegex(ValueError, "columns"):
            resonance.gate_row(["0"], "8000101", "ability_soul")

    def test_generator_emits_gates_on_every_elemental_effect(self):
        templates = fake_templates()
        for spec in rewards.WEAPONS:
            rows = rewards.core.read_csv_lines(rewards.build_soul_leaf(templates, spec))
            for row in rows:
                gates = [row[i:i + 7] for i in (3, 10, 17) if row[i] == "2"]
                if spec.element < 0:
                    self.assertEqual([], gates)
                else:
                    self.assertEqual([["2", "", "", "600000", "600000", spec.group, ""]], gates)


if __name__ == "__main__":
    unittest.main()
