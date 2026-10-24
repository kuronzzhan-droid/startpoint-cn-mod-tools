"""Focused contracts for read-only wiki roster, source consistency and semantics."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wf_mod_tool as core
import wf_wiki_catalog as catalog
from wf_wiki_catalog_source import WikiSource, detect_roster, walk_commands
from wf_wiki_categories import (
    BOSS_IDS, EDITOR_NOTES, FURRY_WORLD_IDS, HIDDEN_CHARACTER_IDS, SMALL_ANIMAL_IDS, category_for,
)
from wf_wiki_catalog_tags import OFFICIAL_NON_PLAYABLE_IDS, character_tags


def character(code="example", leader="3"):
    row = [""] * 37
    for column, value in {0: code, 2: "5", 3: "3", 4: "Human,Beast", 6: "0", 7: "Male",
                          8: code, 9: "(None)", 17: leader, 18: "队长技", 26: "Attacker"}.items():
        row[column] = value
    row[19:25] = [str(i) for i in range(81, 87)]
    return row


class MemorySource:
    def __init__(self):
        self.live = {"character": {"10": [character()]}}
        self.base = {"character": {"10": [character()]}}
        self.trees = {}

    def table(self, key, official=False):
        return (self.base if official else self.live).get(key, {})

    def raw(self, logical, official=False):
        return (b"base" if official else b"live") if logical in self.trees else None

    def tree(self, logical, official=False):
        value = self.trees.get(logical)
        return value[1 if official else 0] if value else None

    def citation(self, logical):
        return {"logical": logical, "sha256": "example"}


class RosterTests(unittest.TestCase):
    def test_wiki_exclusions_filter_entries_media_and_counts_before_export(self):
        source = MemorySource()
        codes = {"119998": "resistance_princess_canary2", "119999": "kyle_wolf_knight",
                 "129990": "spheal_mascot", "129986": "soriz", "129987": "ghandagoza",
                 "139997": "resistance_princess_ex", "139990": "kyle_moon"}
        source.live["character"].update({cid: [character(code)] for cid, code in codes.items()})
        # Also exercise a hidden official entry: visible official counts must not
        # use the unfiltered difference set even if a future baseline changes.
        source.base["character"]["119998"] = [character(codes["119998"])]
        source.live["leader"] = {"3": [["changed"]]}
        source.base["leader"] = {"3": [["original"]]}
        source.fingerprints, source.live_hashes, source.missing = {}, {}, set()
        source.verify_unchanged = Mock()
        media = Mock(store=Path("unused"), image=Mock(return_value=None))
        with patch.object(catalog, "WikiSource", return_value=source), patch.object(
                catalog, "version_at", return_value="1.4.1111"):
            output = catalog.build_catalog(Path("unused"), media)
        self.assertEqual(HIDDEN_CHARACTER_IDS, {"119998", "119999", "129990", "129986", "129987"})
        self.assertEqual({entry["id"] for entry in output["characters"]}, {"10", "139997", "139990"})
        self.assertEqual(output["meta"]["counts"],
                         {"total": 3, "newMod": 2, "modifiedOfficial": 1, "officialOriginal": 0})
        self.assertEqual(output["meta"]["categoryCounts"],
                         {"原创与变体": 1, "毛茸异世界": 1, "Boss角色": 0, "小动物": 0,
                          "原版角色改动": 1, "官方原版": 0})
        requested = [call.args[0] for call in media.image.call_args_list]
        for cid in HIDDEN_CHARACTER_IDS:
            self.assertFalse(any(f"character/{codes[cid]}/" in path for path in requested))
        self.assertTrue(any("character/kyle_moon/" in path for path in requested))
        self.assertTrue(any("character/resistance_princess_ex/" in path for path in requested))
        self.assertNotIn("海豹球", output["meta"]["categoryNote"])

    def test_all_official_playables_are_included_but_audited_npcs_are_not(self):
        source = MemorySource()
        for cid in ("231003", "700013", "999999"):
            source.live["character"][cid] = source.base["character"][cid] = [character(cid)]
        source.fingerprints, source.live_hashes, source.missing = {}, {}, set()
        source.verify_unchanged = Mock()
        media = Mock(store=Path("unused"), image=Mock(return_value=None))
        with patch.object(catalog, "WikiSource", return_value=source), patch.object(
                catalog, "version_at", return_value="1.4.1111"):
            output = catalog.build_catalog(Path("unused"), media)
        self.assertEqual(len(OFFICIAL_NON_PLAYABLE_IDS), 21)
        self.assertEqual({entry["id"] for entry in output["characters"]}, {"10", "231003"})
        self.assertEqual(output["meta"]["counts"],
                         {"total": 2, "newMod": 0, "modifiedOfficial": 0, "officialOriginal": 2})
        self.assertTrue(all(entry["category"] == "官方原版" for entry in output["characters"]))
        self.assertTrue(all(entry["officialComparison"]["status"] == "unchanged"
                            for entry in output["characters"]))
        requested = [call.args[0] for call in media.image.call_args_list]
        self.assertFalse(any("character/700013/" in path or "character/999999/" in path for path in requested))

    def test_new_key_and_legacy_leader_id_are_detected(self):
        source = MemorySource()
        source.live["character"]["99"] = [character("new", "99")]
        source.live["leader"] = {"3": [["changed"]]}
        source.base["leader"] = {"3": [["original"]]}
        roster, modified = detect_roster(source)
        self.assertEqual(roster, ["10", "99"])
        self.assertEqual(modified, {"10": ["leader:3"]})

    def test_official_baseline_is_required(self):
        source = MemorySource()
        source.base = {}
        with self.assertRaisesRegex(ValueError, "官方角色基准为空"):
            detect_roster(source)

    def test_removed_ability_and_awake_changes_are_in_scope(self):
        source = MemorySource()
        source.base["ability"] = {"81": [["original"]]}
        source.live["awake"] = {"10": [["9", "18"]]}
        self.assertEqual(detect_roster(source)[1]["10"], ["awake:10", "ability:81"])

    def test_different_dsl_encoding_with_same_tree_is_not_mod(self):
        source = MemorySource()
        fields = ["", "", "", "", "", "", "", "battle/example"]
        source.live["skill"] = source.base["skill"] = {"example": {"1": [fields]}}
        source.trees["battle/example.action.dsl.amf3.deflate"] = (["same"], ["same"])
        self.assertEqual(detect_roster(source), ([], {}))
        source.trees["battle/example.action.dsl.amf3.deflate"] = (["new"], ["same"])
        self.assertEqual(detect_roster(source)[0], ["10"])


class SourceConsistencyTests(unittest.TestCase):
    def test_changed_live_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp, patch(
                "wf_wiki_catalog_source.OfficialBaseline", return_value=Mock()):
            root = Path(temp)
            logical = "example.orderedmap"
            path = core.table_path(root, logical)
            path.parent.mkdir(parents=True)
            path.write_bytes(b"before")
            source = WikiSource(root, root)
            self.assertEqual(source.raw(logical), b"before")
            source.verify_unchanged()
            path.write_bytes(b"after")
            with self.assertRaisesRegex(RuntimeError, "源文件发生变化"):
                source.verify_unchanged()

    def test_fallback_is_not_live_and_missing_path_creation_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp, patch(
                "wf_wiki_catalog_source.OfficialBaseline", return_value=Mock(get=Mock(return_value=b"official"))):
            root = Path(temp)
            source = WikiSource(root, root)
            self.assertEqual(source.raw("example"), b"official")
            self.assertEqual(source.live_hashes, {})
            self.assertEqual(source.missing, {"example"})
            path = core.table_path(root, "example")
            path.parent.mkdir(parents=True)
            path.write_bytes(b"newly arrived")
            with self.assertRaises(RuntimeError):
                source.verify_unchanged()


class PresentationSemanticsTests(unittest.TestCase):
    def test_theme_markers_do_not_guess_from_general_names(self):
        for code, theme in (("white_tiger_xm20", "圣诞"), ("rec_android_1anv", "周年"),
                            ("dimension_witch_smr20_ex", "泳装"), ("rec_android_seaside", "泳装"),
                            ("wolf_assassin_wt21", "白色情人节"), ("dryad_hw23", "万圣节")):
            tags = character_tags("1", character(code), "白", [])
            self.assertEqual(tags["themes"], [theme])
            self.assertIn(theme + "白", tags["aliases"])
        row = character("ordinary")
        row[27] = "1"
        self.assertEqual(character_tags("1", row, "夏日般热情的角色", ["既有别名"])["themes"], ["通常版"])
        self.assertEqual(character_tags("2", row, "普通名字", ["既有别名"])["themes"], ["其他变体"])

    def test_categories_follow_project_batches_not_beast_species(self):
        self.assertEqual(len(BOSS_IDS), 29)
        self.assertEqual(len(SMALL_ANIMAL_IDS), 16)
        self.assertFalse(BOSS_IDS & SMALL_ANIMAL_IDS)
        for cid in ("119990", "129992"):
            self.assertEqual(category_for(cid)[0], "原创与变体")
        for cid in ("10", "131020", "151159", "261089"):
            self.assertEqual(category_for(cid)[0], "原版角色改动")
        for cid in ("139996", "129990", "119994"):
            self.assertEqual(category_for(cid)[0], "小动物")
        for cid in ("169994", "179986", "149998"):
            self.assertEqual(category_for(cid)[0], "Boss角色")

    def test_author_furry_world_ids_do_not_conflate_gerald_and_gerard(self):
        self.assertEqual(FURRY_WORLD_IDS, {"129999", "149999", "169999", "139990"})
        for cid in FURRY_WORLD_IDS:
            self.assertEqual(category_for(cid)[0], "毛茸异世界")
        self.assertEqual(category_for("129992")[0], "原创与变体")
        self.assertIn("后续将重做", EDITOR_NOTES["129999"])
        self.assertEqual(set(EDITOR_NOTES), {"129999"})

    def test_conditions_use_only_verified_names_and_keep_unknown_ids(self):
        source = MemorySource()
        source.live["condition"] = {"22": [["internal", "龙王显现"]]}
        self.assertEqual(catalog.condition_names(source, "固有22 / 固有999"),
                         "龙王显现（固有22） / 固有999")

    def test_stats_sort_levels_and_keep_awake_atk_hp_separate(self):
        source = MemorySource()
        source.live["status"] = {"10": [("10", 100, 20), ("1", 50, 10), ("100", 500, 100)]}
        source.live["awake"] = {"10": [["12", "34"]]}
        media = Mock(image=Mock(return_value=None))
        entry = catalog.character_entry(source, "10", [], media)
        self.assertEqual([row["level"] for row in entry["stats"]["levels"]], [1, 10, 100])
        self.assertEqual(entry["stats"]["awakePerNode"], {"atk": 12, "hp": 34})
        self.assertEqual(entry["stats"]["levels"][-1], {"level": 100, "hp": 500, "atk": 100})

    def test_native_main_icon_forms_are_plain_text(self):
        self.assertEqual(catalog.plain("<icon id='main'> 技能"), "【主位】 技能")
        self.assertEqual(catalog.plain('<icon id="main" /> 技能'), "【主位】 技能")

    def test_unconfigured_low_rarity_ability_has_neutral_explanation(self):
        entry = catalog.ability_group(MemorySource(), "ability", "(None)", "能力 3")
        self.assertEqual(entry["description"], "此角色未配置该能力。")
        self.assertEqual(entry["rows"], [])

    def test_nested_commands_keep_numbers_without_recursive_duplication(self):
        child = ["Command", ["Damage", 25.5, {"min": 2, "max": 8}]]
        parent = ["Event", ["Sequence", [child]]]
        output = catalog.compact_commands(list(walk_commands(parent)))
        self.assertEqual(output[0]["arguments"], [[{"commandRef": 2}]])
        self.assertEqual(output[1]["arguments"], [25.5, {"min": 2, "max": 8}])

    def test_gauge_uses_max_and_real_form_without_voice_suffix_is_not_mislabeled(self):
        source = MemorySource()
        source.live["skill"] = {"example": {"2": [["技能＋", "描述", "", "", "600", "450", "", "battle/main"]]}}
        source.live["switched"] = {"real_form": {"2": [["battle/main"]]}}
        source.trees["battle/main.action.dsl.amf3.deflate"] = (["Command", ["Damage", 5]], None)
        row = character()
        row[9], row[14] = "1", "real_form"
        skills, switch = catalog.skills_for(source, row)
        self.assertEqual(skills[0]["gauge"], 450)
        self.assertEqual(skills[0]["gaugeMin"], 600)
        self.assertEqual(skills[0]["label"], "进化技能")
        self.assertNotIn("语音路由", skills[1]["label"])
        self.assertEqual(switch["key"], "real_form")

    def test_invoke_skill_uses_actual_program_column_and_not_caption_key(self):
        source = MemorySource()
        row = [""] * 126
        row[47], row[70], row[71] = "629", "text_key", "battle/actual/path"
        with patch.object(catalog, "skill_program", return_value={"commands": []}) as program:
            refs = catalog.related_programs(source, [row], "ability")
        program.assert_called_once_with(source, "battle/actual/path")
        self.assertEqual(refs[0]["key"], "text_key")

    def test_powerflip_only_reads_override_fields_not_category(self):
        source = MemorySource()
        source.live["power_flip"] = {"special": [["battle/special"]], "custom": [["battle/custom"]]}
        row = [""] * 126
        row[2] = "special"  # Ability category is not a PF override.
        row[82] = "custom"
        with patch.object(catalog, "skill_program", return_value={"commands": []}) as program:
            refs = catalog.related_programs(source, [row], "ability")
        program.assert_called_once_with(source, "battle/custom")
        self.assertEqual(len(refs), 1)


if __name__ == "__main__":
    unittest.main()
