from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import wf_mod_tool as core  # noqa: E402
from wf.tools.rogue import rogue_reward_schedule as rewards  # noqa: E402
from wf.tools.rogue import rogue_token_result as token_result  # noqa: E402


class TestRewardCurve(unittest.TestCase):
    def test_token_curve_and_totals_match_the_final_design(self):
        self.assertEqual(0.12, rewards.token_optional_chance(2))
        self.assertEqual(0.48, rewards.token_optional_chance(14))
        self.assertEqual(0.50, rewards.token_optional_chance(15))
        self.assertEqual(0.51, rewards.token_optional_chance(16))
        self.assertEqual(0.64, rewards.token_optional_chance(29))

        report = rewards.probability_report()
        self.assertEqual(113, report["token_before_final_guaranteed"])
        self.assertAlmostEqual(30.3, report["token_before_final_optional_expected"])
        self.assertEqual(213, report["token_full_run_minimum"])
        self.assertEqual(278, report["token_full_run_maximum"])
        self.assertAlmostEqual(243.3, report["token_full_run_expected"])
        self.assertAlmostEqual(1.92, report["single_ticket_expected"])
        self.assertAlmostEqual(0.25, report["ten_ticket_expected"])

    def test_ticket_floors_are_mutually_exclusive(self):
        for floor in range(1, 30):
            if floor % 5 == 0:
                self.assertEqual(0, rewards.single_ticket_chance(floor))
                self.assertEqual(floor / 500, rewards.ten_ticket_chance(floor))
            else:
                self.assertEqual(0, rewards.ten_ticket_chance(floor))
                self.assertAlmostEqual(
                    0.01 + (floor - 1) * 0.005,
                    rewards.single_ticket_chance(floor),
                )

    def test_server_json_builders_preserve_non_targets(self):
        rogue = {
            "sentinel": {"keep": True},
            "events": {
                "700099": {"per_round_drops": [], "folder_clear_chance": [], "other": 7},
                "700007": {"unchanged": [1, 2, 3]},
            },
        }
        built = rewards.build_rogue_event(rogue)
        self.assertEqual({"keep": True}, built["sentinel"])
        self.assertEqual(rogue["events"]["700007"], built["events"]["700007"])
        self.assertEqual(7, built["events"]["700099"]["other"])
        rewards.validate_rogue_event(built)

        folder = {"700099": {"1": [{"old": True}], "2": []}, "700007": {"1": [1]}}
        folder_built = rewards.build_server_folder(folder)
        self.assertEqual(folder["700099"]["2"], folder_built["700099"]["2"])
        self.assertEqual(folder["700007"], folder_built["700007"])
        rewards.validate_server_folder(folder_built)

    def test_cn_extension_matches_the_final_ten_ticket_chance(self):
        extension = {
            "events": {
                "700099": {
                    "folder_clear_chance": [
                        {"type": 0, "id": 999014, "count": 1, "chance": 0.10},
                    ],
                },
            },
        }
        rewards.validate_rogue_event_extension(extension)
        extension["events"]["700099"]["folder_clear_chance"][0]["chance"] = 0.05
        with self.assertRaisesRegex(ValueError, "10%"):
            rewards.validate_rogue_event_extension(extension)


class TestClientTables(unittest.TestCase):
    @staticmethod
    def _ordered(label: str, rows: dict[str, bytes]) -> bytes:
        table = core.OrderedMap(label, list(rows), list(rows.values()), Path("<memory>"))
        return core.build_orderedmap(table)

    def test_folder_preview_changes_only_700099_floor_1_rewards(self):
        row = ",".join([
            "1", "1", "深渊连战", "(None)", "thumb", "background", "20001",
            *(["(None)", "", "(None)"] * 10),
        ]).encode("utf-8")
        self.assertEqual(37, len(row.decode("utf-8").split(",")))
        inner = self._ordered("inner", {"1": row, "2": b"sentinel"})
        other = self._ordered("other", {"1": b"other"})
        outer = core.OrderedMap(
            "outer", ["700007", "700099"], [other, inner], Path("<memory>")
        )
        raw = core.build_orderedmap_raw_rows(outer)
        built = rewards.build_client_folder_payload(raw)
        rewards.validate_client_folder_payload(built)
        before = core.read_orderedmap_raw_rows_from_bytes(raw, rewards.FOLDER_LOGICAL)
        after = core.read_orderedmap_raw_rows_from_bytes(built, rewards.FOLDER_LOGICAL)
        self.assertEqual(before.rows[0], after.rows[0])

    def test_additional_reward_group_has_8_token_slots_and_2_ticket_slots(self):
        existing = self._ordered("existing", {"1": b"existing,0,1,1,1"})
        outer = core.OrderedMap("outer", ["42"], [existing], Path("<memory>"))
        raw = core.build_orderedmap_raw_rows(outer)
        built = rewards.build_additional_reward_payload(raw)
        rewards.validate_additional_reward_payload(built)
        before = core.read_orderedmap_raw_rows_from_bytes(raw, rewards.ADDITIONAL_LOGICAL)
        after = core.read_orderedmap_raw_rows_from_bytes(built, rewards.ADDITIONAL_LOGICAL)
        self.assertEqual(before.rows[0], after.rows[0])
        self.assertEqual(list(map(str, range(1, 11))), list(rewards.additional_reward_rows()))

    def test_legacy_decoded_token_group_upgrades_idempotently(self):
        legacy = {
            "42": {"1": "existing,0,1,1,1"},
            str(rewards.ADDITIONAL_GROUP_ID): {
                "1": "abyss_token_result,0,2370099,5,1",
            },
        }
        built = token_result.build_table(legacy)
        token_result.validate_table(built)
        self.assertEqual(rewards.additional_reward_rows(), built[str(rewards.ADDITIONAL_GROUP_ID)])
        self.assertEqual(built, token_result.build_table(built))


if __name__ == "__main__":
    unittest.main()
