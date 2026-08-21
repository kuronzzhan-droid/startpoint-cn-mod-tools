#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import wf_abyss_ticket_drop as drop  # noqa: E402


LEGACY = {"type": 0, "id": 999001, "count": 1, "chance": 0.3}
TARGET = {"type": 0, "id": 999014, "count": 1, "chance": 0.05}
OTHER_REWARD = {"type": 0, "id": 11003, "count": 1, "chance": 0.5}


def rogue_fixture() -> dict[str, object]:
    return {
        "_readme": "preserve-exactly",
        "enabled": True,
        "events": {
            "700099": {
                "unlock_played_parties": True,
                "folder_clear_chance": [copy.deepcopy(LEGACY), copy.deepcopy(OTHER_REWARD)],
                "folder_clear_random": [{"pool": [52, 55], "pick": [1, 1]}],
            },
            "700007": {
                "folder_clear_chance": [
                    {"type": 0, "id": 999001, "count": 2, "chance": 0.9}
                ],
                "sentinel": [1, {"nested": True}],
            },
        },
    }


def quest_fixture() -> dict[str, object]:
    quests: dict[str, object] = {
        "42": {"rushEventId": 700007, "rushEventFolderId": 1, "rushEventRound": 1}
    }
    for round_number in range(1, 31):
        quest_id = str(700_099_000 + round_number)
        quests[quest_id] = {
            "name": f"normal-{round_number}",
            "rushEventId": 700099,
            "rushEventFolderId": 1,
            "rushEventRound": round_number,
        }
    quests["700099099"] = {
        "name": "endless",
        "rushEventId": 700099,
        "rushEventFolderId": 2,
        "rushEventRound": 0,
    }
    return quests


class TestFinalTicketDrop(unittest.TestCase):
    def test_replaces_only_the_legacy_reward_at_the_same_index(self):
        source = rogue_fixture()
        quests = quest_fixture()
        original_source = copy.deepcopy(source)
        original_quests = copy.deepcopy(quests)

        result = drop.build_final_ticket_drop(source, quests)

        self.assertEqual(original_source, source)
        self.assertEqual(original_quests, quests)
        self.assertEqual(
            [TARGET, OTHER_REWARD],
            result["events"]["700099"]["folder_clear_chance"],
        )
        expected = copy.deepcopy(original_source)
        expected["events"]["700099"]["folder_clear_chance"][0] = TARGET
        self.assertEqual(expected, result)
        self.assertEqual(original_source["events"]["700007"], result["events"]["700007"])

    def test_compiled_result_is_json_byte_idempotent(self):
        first = drop.build_final_ticket_drop(rogue_fixture(), quest_fixture())
        second = drop.build_final_ticket_drop(first, quest_fixture())

        first_bytes = json.dumps(first, ensure_ascii=False, separators=(",", ":"))
        second_bytes = json.dumps(second, ensure_ascii=False, separators=(",", ":"))
        self.assertEqual(first_bytes, second_bytes)
        drop.validate_final_ticket_drop(second, quest_fixture())

    def test_legacy_and_target_cannot_coexist(self):
        source = rogue_fixture()
        source["events"]["700099"]["folder_clear_chance"].append(copy.deepcopy(TARGET))

        with self.assertRaisesRegex(ValueError, "并存"):
            drop.build_final_ticket_drop(source, quest_fixture())

    def test_duplicate_legacy_reward_is_rejected(self):
        source = rogue_fixture()
        source["events"]["700099"]["folder_clear_chance"].append(copy.deepcopy(LEGACY))

        with self.assertRaisesRegex(ValueError, "999001"):
            drop.build_final_ticket_drop(source, quest_fixture())

    def test_mutated_legacy_reward_is_not_silently_adopted(self):
        for field, value in (("type", 4), ("count", 2), ("chance", 0.2)):
            with self.subTest(field=field):
                source = rogue_fixture()
                source["events"]["700099"]["folder_clear_chance"][0][field] = value

                with self.assertRaisesRegex(ValueError, "999001"):
                    drop.build_final_ticket_drop(source, quest_fixture())

    def test_mutated_target_reward_is_not_treated_as_idempotent(self):
        source = rogue_fixture()
        source["events"]["700099"]["folder_clear_chance"][0] = copy.deepcopy(TARGET)
        source["events"]["700099"]["folder_clear_chance"][0]["chance"] = 0.5

        with self.assertRaisesRegex(ValueError, "999014"):
            drop.build_final_ticket_drop(source, quest_fixture())

    def test_missing_legacy_and_target_is_rejected(self):
        source = rogue_fixture()
        source["events"]["700099"]["folder_clear_chance"].pop(0)

        with self.assertRaisesRegex(ValueError, "999001"):
            drop.build_final_ticket_drop(source, quest_fixture())

    def test_wrong_container_types_fail_closed(self):
        cases = (
            ([], "rogue_event"),
            ({"events": []}, "events"),
            ({"events": {"700099": []}}, "700099"),
            ({"events": {"700099": {"folder_clear_chance": {}}}}, "folder_clear_chance"),
        )
        for source, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex((TypeError, ValueError), message):
                    drop.build_final_ticket_drop(source, quest_fixture())


class TestQuestRuntimeBoundary(unittest.TestCase):
    def test_exact_quest_contract_is_accepted(self):
        drop.validate_final_normal_boundary(quest_fixture())

    def test_final_normal_quest_must_be_round_30_in_folder_1(self):
        for field, value in (
            ("rushEventId", 700007),
            ("rushEventFolderId", 2),
            ("rushEventRound", 29),
        ):
            with self.subTest(field=field):
                quests = quest_fixture()
                quests["700099030"][field] = value

                with self.assertRaisesRegex(ValueError, "700099030"):
                    drop.validate_final_normal_boundary(quests)

    def test_normal_folder_must_be_exact_contiguous_rounds_1_through_30(self):
        cases = (
            ("missing", lambda quests: quests.pop("700099017")),
            (
                "extra",
                lambda quests: quests.__setitem__(
                    "700099031",
                    {
                        "rushEventId": 700099,
                        "rushEventFolderId": 1,
                        "rushEventRound": 31,
                    },
                ),
            ),
        )
        for label, mutate in cases:
            with self.subTest(case=label):
                quests = quest_fixture()
                mutate(quests)

                with self.assertRaisesRegex(ValueError, r"1\.\.30"):
                    drop.validate_final_normal_boundary(quests)

    def test_endless_700099099_must_remain_folder_2_round_0(self):
        for field, value in (
            ("rushEventFolderId", 1),
            ("rushEventRound", 99),
        ):
            with self.subTest(field=field):
                quests = quest_fixture()
                quests["700099099"][field] = value

                with self.assertRaisesRegex(ValueError, "700099099"):
                    drop.validate_final_normal_boundary(quests)

    def test_no_second_normal_or_endless_folder_can_share_event_level_drop(self):
        quests = quest_fixture()
        quests["700099200"] = {
            "rushEventId": 700099,
            "rushEventFolderId": 3,
            "rushEventRound": 1,
        }

        with self.assertRaisesRegex(ValueError, "额外"):
            drop.validate_final_normal_boundary(quests)


if __name__ == "__main__":
    unittest.main()
