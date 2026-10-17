"""Client description compatibility, including the observed 1.4.777 C10010 row."""
from __future__ import annotations

import sys
import unittest
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wf_client_legality as legality
import wf_describe
import wf_mod_tool as core

# Immutable actual row: archive fox_oracle_autumn-1.4.777, ability 1399951, row 4.
BAD_777 = "789c4bcbaf88cf2f4a4cce498d4f2c2d29cdcd8b37d429292a4dd5492c29494cce8eaf4ccdc9c92fd731d0d131001160804e1b5a988048031080513a3a1a7ef979a99a1045c620ca042203a520ea204c634b4b4b53231d031d133343b00674b3c0b66011836b8570e02e22010000cc663793"
# Official 1.4.0 archive 42-a2353958, ability 1111652, row 0 (ConditionUnique).
OFFICIAL_UNIQUE = "789c2b4a2dce2c2e49cc4b4e8d2f28cacc4b4e2d2e8e37ce48cc494bcc2b8b37d2494bcc294ed549cecf4bc92cc9cccfd331d0d131001160804e1b19839886062000a3747434fcf2f35235218aa06c9836133343b0b831442d94820074632082a6501a6e270900006c36354c"
# Actual sealed candidate 1.0.7 replacement, same ability key and row index.
FIXED_I629 = "789c9d4e410a02310cfc8c0785c07645443fe11742b6a45a36b65053d7fdbd54dbcb7a599cc3cc242493b8f8c298c80a2365cdf7803d68ca0ca44a76c49945e20406c014fa60a9fde950d8143401d85e62e0dd77a8fab676dc9fab5f82062f5e67743f6f397e72c26b8a93de602055e18eacfa18bac7e8455ad1126a7355de66e5d9bff006d51a6c8a"


def fixture(raw=BAD_777, kind="ability"):
    row = core.read_csv_lines(zlib.decompress(bytes.fromhex(raw)).decode())[0]
    # Retain the common trigger/content columns at each table's actual offset.
    prefix = int(wf_describe.layout(kind)["blocks"]["precondition1"])
    return row if prefix == 6 else [row[0]] + row[7 - prefix:]


class DescriptionLegalityTest(unittest.TestCase):
    def test_observed_777_row_is_rejected_at_existing_public_gate(self):
        row = fixture()
        self.assertEqual((row[39], row[44], row[47]), ("3", "1000000000", "461"))
        errors = legality.client_legality_problems("ability", row)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("C10010", errors[0])
        self.assertIn("Unique", errors[0])

    def test_all_four_unique_content_targets_and_three_table_offsets(self):
        for kind in ("ability", "leader_ability", "ability_soul"):
            b = wf_describe.layout(kind)["blocks"]
            for content in ("413", "436", "459", "461"):
                for precontent, limit in (("0", "1"), ("1", "1"), ("3", "2")):
                    with self.subTest(kind=kind, content=content, precontent=precontent):
                        row = fixture(kind=kind)
                        row[b["instant_content"]] = content
                        row[b["instant_precontent"]] = precontent
                        row[b["instant_precontent"] + 5] = limit
                        errors = legality.client_legality_problems(kind, row)
                        self.assertTrue(any("C10010" in e for e in errors), errors)

    def test_source_suffix_none_exceptions_are_allowed(self):
        for precontent, limit in (("(None)", "1000000000"), ("2", "1000000000"),
                                  ("3", "1"), ("3", "01")):
            with self.subTest(precontent=precontent, limit=limit):
                row = fixture()
                row[39], row[44] = precontent, limit
                self.assertEqual(legality.client_legality_problems("ability", row), [])

    def test_zero_or_empty_limit_does_not_mean_no_suffix(self):
        for limit in ("0", "", "(None)", "-1"):
            with self.subTest(limit=limit):
                row = fixture()
                row[44] = limit
                self.assertTrue(any("C10010" in e for e in
                                    legality.client_legality_problems("ability", row)))

    def test_official_unique_row_and_supported_fever_gain_stay_legal(self):
        self.assertEqual(legality.client_legality_problems("ability", fixture(OFFICIAL_UNIQUE)), [])
        row = fixture()
        row[47] = "213"  # AddFeverPoint has its own supported precontent renderer.
        self.assertEqual(legality.client_legality_problems("ability", row), [])

    def test_invoke_skill_replacement_without_precontent_stays_legal(self):
        row = fixture(FIXED_I629)
        self.assertEqual((row[39], row[47]), ("(None)", "629"))
        self.assertEqual(row[40:46], [""] * 6)
        self.assertEqual(legality.client_legality_problems("ability", row), [])

    def test_inactive_instant_columns_are_not_rejected(self):
        for mode in ("1", "2"):
            row = fixture()
            row[5] = mode
            self.assertFalse(any("C10010" in e for e in
                                 legality.client_legality_problems("ability", row)))


if __name__ == "__main__":
    unittest.main()
