"""Native degree joins, missing resources and public-data boundaries."""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wf_wiki_nameplates as plates
from wf_wiki_public import public_catalog


def mission(cid, pattern="44"):
    row = [""] * 36
    row[3], row[15] = pattern, cid
    return row


def reward(*degrees):
    row = [""] * 29
    for slot, degree in enumerate(degrees):
        row[5 + slot * 6], row[10 + slot * 6] = "6", degree
    return ",".join(row)


def definition(name="真实称号", path="dynamic/degree/actual_plate"):
    return ["private_code", "1", name, "", "获得条件：角色达到100级", "2", "", "", path]


class Source:
    def __init__(self, data):
        self.data = data

    def table(self, logical):
        return self.data.get(logical, {})

    def raw(self, logical):
        return b"native reward bytes" if logical == plates.REWARDS else None


class NameplateTests(unittest.TestCase):
    def test_mission_join_reads_all_reward_slots_and_deduplicates_stages(self):
        source = Source({plates.MISSIONS: {"different_mission_id": [mission("10", "48")],
                         "not_a_character": [mission("(None)")], "hidden": [mission("119998")]}})
        rewards = {"different_mission_id": {"1": reward("31", "32", "33", "34"), "2": reward("31")},
                   "not_a_character": {"1": reward("50")}, "hidden": {"1": reward("60")}}
        before = copy.deepcopy((source.data, rewards))
        with patch.object(plates.wf_quest_lib, "parse_node", return_value=rewards):
            actual = plates.native_links(source)
        self.assertEqual(dict(actual), {"10": dict.fromkeys(("31", "32", "33", "34"), "第二玛纳板铭牌")})
        self.assertEqual((source.data, rewards), before)

    def test_only_visible_explicit_links_export_real_degree_images(self):
        source = Source({plates.DEGREES: {"31": [definition()], "32": [definition(path="dynamic/degree/second")],
                         "999": [definition(name="与角色同名")], "60": [definition(path="dynamic/degree/hidden")]}})
        chars = [{"id": "10"}, {"id": "11", "name": "与角色同名"}, {"id": "119998"}]
        media = Mock(image=Mock(side_effect=lambda logical: "media/" + str(len(logical)) + ".webp"))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            config = root / plates.MOD_LINKS
            config.parent.mkdir()
            config.write_text(json.dumps({"schema_version": 1, "enabled": True, "characters": [
                {"character_id": 10, "degree_ids": [31, 31, 32]},
                {"character_id": 119998, "degree_ids": [60]},
                {"character_id": 12, "degree_ids": [999]}]}), encoding="utf8")
            original = config.read_bytes()
            summary = plates.attach_nameplates(root, source, chars, media)
            self.assertEqual(config.read_bytes(), original)
        self.assertEqual([len(c["nameplates"]) for c in chars], [2, 0, 0])
        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["characters"], 1)
        self.assertEqual([c.args[0] for c in media.image.call_args_list], [
            "dynamic/degree/actual_plate.png", "dynamic/degree/second.png"])
        self.assertEqual(chars[0]["nameplates"][0]["acquisition"], "获得条件：角色达到100级")

    def test_missing_definitions_and_images_never_fall_back_to_portraits(self):
        source = Source({plates.DEGREES: {"1": [definition()], "2": [definition(path="character/portrait")]}})
        character = {"id": "10", "icon": "media/avatar.webp"}
        with tempfile.TemporaryDirectory() as folder, patch.object(
                plates, "native_links", return_value={"10": {"1": "信赖铭牌", "2": "铭牌", "3": "铭牌"}}):
            media = Mock(image=Mock(return_value=None))
            summary = plates.attach_nameplates(Path(folder), source, [character], media)
        self.assertEqual(character["nameplates"], [])
        self.assertEqual((summary["missingDefinitions"], summary["missingImages"]), (2, 1))
        media.image.assert_called_once_with("dynamic/degree/actual_plate.png")

    def test_public_payload_retains_acquisition_without_ids_or_logical_paths(self):
        source = Source({plates.DEGREES: {"9910001": [definition()]}})
        character = {"id": "119989"}
        with tempfile.TemporaryDirectory() as folder, patch.object(
                plates, "native_links", return_value={"119989": {"9910001": "专属铭牌"}}):
            summary = plates.attach_nameplates(Path(folder), source, [character], Mock(image=Mock(return_value="media/test.webp")))
        public = public_catalog({"meta": {"nameplates": summary}, "characters": [character]})
        serialized = json.dumps(public, ensure_ascii=False)
        for private in ("9910001", "119989", "private_code", "dynamic/degree", "sourceFiles"):
            self.assertNotIn(private, serialized)
        self.assertEqual(public["characters"][0]["nameplates"][0]["acquisition"], "获得条件：角色达到100级")

    def test_configuration_drift_is_rejected(self):
        source = Source({plates.DEGREES: {"31": [definition()]}})
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            config = root / plates.MOD_LINKS
            config.parent.mkdir()
            config.write_text(json.dumps({"schema_version": 1, "characters": [
                {"character_id": 10, "degree_ids": [31]}]}), encoding="utf8")

            def changed(_logical):
                config.write_text("{}", encoding="utf8")
                return "media/test.webp"

            with self.assertRaisesRegex(RuntimeError, "登记变化"):
                plates.attach_nameplates(root, source, [{"id": "10"}], Mock(image=Mock(side_effect=changed)))

    def test_missing_missions_and_unlinked_characters_are_empty(self):
        source = Source({})
        with patch.object(plates.wf_quest_lib, "parse_node") as parse:
            self.assertEqual(plates.native_links(source), {})
            parse.assert_not_called()
        with tempfile.TemporaryDirectory() as folder:
            media, character = Mock(), {"id": "10"}
            summary = plates.attach_nameplates(Path(folder), source, [character], media)
        self.assertEqual(summary["total"], 0)
        self.assertEqual(character["nameplates"], [])
        media.image.assert_not_called()


if __name__ == "__main__":
    unittest.main()
