# -*- coding: utf-8 -*-
"""Offline tests for the read-only World Flipper story exporter."""
from __future__ import annotations

import csv
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import wf_mod_tool as core  # noqa: E402
import wf_quest_lib as quest_core  # noqa: E402
import wf_story_export as story  # noqa: E402


def command_csv(kind: int, values: dict[int, str] | None = None) -> str:
    row = [""] * 43
    row[0] = str(kind)
    for index, value in (values or {}).items():
        row[index] = value
    out = io.StringIO()
    csv.writer(out, lineterminator="").writerow(row)
    return out.getvalue()


def scenario_bytes_with_keys(
    rows: list[str],
    keys: list[str],
    *,
    outer_key: str = "story/test/scenario",
    inner_trailer: bytes = b"",
) -> bytes:
    inner = core.OrderedMap(
        logical_path=f"{outer_key}.inner",
        keys=keys,
        rows=[row.encode("utf-8") for row in rows],
        source_path=Path("synthetic-inner.orderedmap"),
    )
    inner_raw = core.build_orderedmap(inner) + inner_trailer
    outer = core.OrderedMap(
        logical_path=f"master/{outer_key}.orderedmap",
        keys=[outer_key],
        rows=[inner_raw],
        source_path=Path("synthetic-outer.orderedmap"),
    )
    return core.build_orderedmap_raw_rows(outer)


def scenario_bytes(rows: list[str], *, outer_key: str = "story/test/scenario") -> bytes:
    return scenario_bytes_with_keys(
        rows,
        [str(index) for index in range(1, len(rows) + 1)],
        outer_key=outer_key,
    )


def add_orderedmap_index_trailer(raw: bytes, trailer: bytes) -> bytes:
    index_length = int.from_bytes(raw[:4], "little")
    return (
        (index_length + len(trailer)).to_bytes(4, "little")
        + raw[4:4 + index_length]
        + trailer
        + raw[4 + index_length:]
    )


def wide_csv(width: int, values: dict[int, str]) -> str:
    row = [""] * width
    for index, value in values.items():
        row[index] = value
    out = io.StringIO()
    csv.writer(out, lineterminator="").writerow(row)
    return out.getvalue()


def write_flat_table(store: Path, logical: str, rows: dict[str, str]) -> Path:
    ordered = core.OrderedMap(
        logical_path=logical,
        keys=list(rows),
        rows=[value.encode("utf-8") for value in rows.values()],
        source_path=Path("synthetic-flat.orderedmap"),
    )
    target = core.table_path(store, logical)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(core.build_orderedmap(ordered))
    return target


def write_tree_table(store: Path, logical: str, tree: dict) -> Path:
    target = core.table_path(store, logical)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(quest_core.build_node(tree))
    return target


def write_scenario(store: Path, logical: str, rows: list[str] | None = None) -> Path:
    outer_key = logical.removeprefix("master/").removesuffix(".orderedmap")
    target = core.table_path(store, logical)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(scenario_bytes(rows or [command_csv(22)], outer_key=outer_key))
    return target


class TestScenarioDecoding(unittest.TestCase):
    def test_decodes_raw_nested_orderedmap_and_typed_text_fields(self):
        raw = scenario_bytes([
            command_csv(0, {
                4: "white_tiger_known",
                5: "第一行\n第二行，带逗号",
                6: "(None)",
                7: "false",
                8: "3",
            }),
            command_csv(6, {
                12: "white_tiger",
                13: "1",
                14: "joy,smile",
                15: "true",
            }),
        ])

        outer_key, commands = story.decode_scenario_bytes(
            raw, "master/story/test/scenario.orderedmap")

        self.assertEqual(outer_key, "story/test/scenario")
        self.assertEqual([command.line for command in commands], [1, 2])
        text = commands[0]
        self.assertEqual(text.op, "Text")
        self.assertEqual(text.args["text_character_id"], "white_tiger_known")
        self.assertEqual(text.args["text_body"], "第一行\n第二行，带逗号")
        self.assertIsNone(text.args["text_voice_path"])
        self.assertIs(text.args["text_voice_immediately"], False)
        self.assertEqual(text.args["text_balloon_position"], 3)
        self.assertEqual(text.raw[6], "(None)")
        character_in = commands[1]
        self.assertEqual(character_in.args["character_in_face"], ["joy", "smile"])
        self.assertIs(character_in.args["character_in_reverse"], True)

    def test_normalizes_actual_and_literal_newlines_without_changing_raw(self):
        raw_text = "甲\r\n乙\r丙\\n丁"
        raw = scenario_bytes([
            command_csv(0, {4: "", 5: raw_text, 6: "(None)", 7: "false", 8: "0"}),
        ])

        _, commands = story.decode_scenario_bytes(raw, "master/story/test/scenario.orderedmap")

        self.assertEqual(commands[0].args["text_body"], "甲\n乙\n丙\n丁")
        self.assertEqual(commands[0].raw[5], raw_text)

    def test_preserves_unknown_opcode_and_all_nonempty_columns(self):
        raw = scenario_bytes([command_csv(99, {4: "mystery", 31: "1,2,3"})])

        _, commands = story.decode_scenario_bytes(raw, "master/story/test/scenario.orderedmap")

        command = commands[0]
        self.assertEqual(command.op, "unknown")
        self.assertEqual(command.args, {"col_4": "mystery", "col_31": "1,2,3"})
        self.assertEqual(command.raw[0], "99")
        self.assertEqual(len(command.raw), 43)

    def test_rejects_outer_rows_that_are_zlib_compressed_instead_of_raw(self):
        inner = scenario_bytes([command_csv(22)])
        broken_outer = core.OrderedMap(
            logical_path="broken",
            keys=["story/test/scenario"],
            rows=[inner],
            source_path=Path("broken.orderedmap"),
        )

        with self.assertRaisesRegex(ValueError, "outer|外层|scenario"):
            story.decode_scenario_bytes(
                core.build_orderedmap(broken_outer),
                "master/story/test/scenario.orderedmap",
            )

    def test_rejects_duplicate_inner_keys_before_they_can_collapse(self):
        raw = scenario_bytes_with_keys(
            [command_csv(22), command_csv(23)],
            ["1", "1"],
        )

        with self.assertRaisesRegex(ValueError, "duplicate|重复"):
            story.decode_scenario_bytes(
                raw, "master/story/test/scenario.orderedmap")

    def test_rejects_unindexed_trailing_bytes_in_the_inner_map(self):
        raw = scenario_bytes_with_keys(
            [command_csv(22)],
            ["1"],
            inner_trailer=b"not-indexed",
        )

        with self.assertRaisesRegex(ValueError, "length|长度|inner"):
            story.decode_scenario_bytes(
                raw, "master/story/test/scenario.orderedmap")

    def test_rejects_trailing_bytes_inside_outer_and_inner_index_segments(self):
        valid = scenario_bytes([command_csv(22)])
        outer_with_trailer = add_orderedmap_index_trailer(valid, b"outer-junk")

        inner = core.OrderedMap(
            logical_path="story/test/scenario.inner",
            keys=["1"],
            rows=[command_csv(22).encode("utf-8")],
            source_path=Path("synthetic-inner.orderedmap"),
        )
        inner_with_trailer = add_orderedmap_index_trailer(
            core.build_orderedmap(inner), b"inner-junk")
        outer = core.OrderedMap(
            logical_path="master/story/test/scenario.orderedmap",
            keys=["story/test/scenario"],
            rows=[inner_with_trailer],
            source_path=Path("synthetic-outer.orderedmap"),
        )
        inner_index_with_trailer = core.build_orderedmap_raw_rows(outer)

        for raw in (outer_with_trailer, inner_index_with_trailer):
            with self.subTest(raw_size=len(raw)):
                with self.assertRaisesRegex(ValueError, "index|trailing|尾随"):
                    story.decode_scenario_bytes(
                        raw, "master/story/test/scenario.orderedmap")

    def test_rejects_truncated_command_rows_even_for_no_arg_opcodes(self):
        raw = scenario_bytes(["22"])

        with self.assertRaisesRegex(ValueError, "43 columns|43 列"):
            story.decode_scenario_bytes(
                raw, "master/story/test/scenario.orderedmap")

    def test_as3_nullable_integer_fields_accept_empty_and_hex_values(self):
        raw = scenario_bytes([
            command_csv(3, {38: "0", 39: "bgm/test", 40: ""}),
            command_csv(4, {41: "2", 42: ""}),
            command_csv(14, {27: "", 28: ""}),
            command_csv(16, {23: "0xff000000", 24: ""}),
            command_csv(17, {25: "", 26: ""}),
            command_csv(18, {29: "sepia", 30: "0x10"}),
            command_csv(19, {31: "", 32: ""}),
            command_csv(20, {33: ""}),
        ])

        _, commands = story.decode_scenario_bytes(
            raw, "master/story/test/scenario.orderedmap")

        self.assertIsNone(commands[0].args["bgm_fade_in_time"])
        self.assertIsNone(commands[1].args["bgm_fade_out_time"])
        self.assertIsNone(commands[2].args["screen_shake_time"])
        self.assertIsNone(commands[2].args["screen_shake_size"])
        self.assertEqual(commands[3].args["screen_fade_in_color"], 0xFF000000)
        self.assertIsNone(commands[3].args["screen_fade_in_time"])
        self.assertIsNone(commands[4].args["screen_fade_out_color"])
        self.assertIsNone(commands[4].args["screen_fade_out_time"])
        self.assertEqual(commands[5].args["screen_color_effect_time"], 16)
        self.assertIsNone(commands[6].args["screen_color_effect_custom_time"])
        self.assertIsNone(commands[7].args["screen_color_effect_disable_time"])

    def test_official_opcode_schema_covers_every_as3_enum_kind(self):
        self.assertEqual(set(story.OPCODES), set(range(25)))
        self.assertEqual(story.OPCODES[4].name, "BgmFadeOut")
        self.assertEqual(story.OPCODES[7].name, "CharacterOut")
        self.assertEqual(story.OPCODES[11].name, "CharacterInactive")
        self.assertEqual(story.OPCODES[22].name, "MessageWindowShow")
        nullable_fields = {
            field.name
            for spec in story.OPCODES.values()
            for field in spec.fields
            if field.value_type == "nullable_int"
        }
        self.assertEqual(nullable_fields, {
            "bgm_fade_in_time",
            "bgm_fade_out_time",
            "screen_shake_time",
            "screen_shake_size",
            "screen_fade_in_color",
            "screen_fade_in_time",
            "screen_fade_out_color",
            "screen_fade_out_time",
            "screen_color_effect_time",
            "screen_color_effect_custom_time",
            "screen_color_effect_disable_time",
        })


class TestStoryRendering(unittest.TestCase):
    def setUp(self):
        self.speakers = {
            "alk": story.Speaker("alk", "阿尔克"),
            "white_tiger_known": story.Speaker("white_tiger_known", "兽人"),
        }
        self.entry = story.StoryEntry(
            category="character_story_quest",
            relative_dir="white_tiger_001",
            logical_path=(
                "master/story/character_story_quest/"
                "white_tiger_001/scenario.orderedmap"
            ),
            quest_id="301",
            title="疑惑",
            character_id="10",
            character_code="white_tiger",
            character_name="白",
            episode=1,
        )

    def test_markdown_small_golden_resolves_alias_narration_and_stage_notes(self):
        raw = scenario_bytes([
            command_csv(22),
            command_csv(1, {35: "0", 36: "bgm/common/story/basic"}),
            command_csv(5, {1: "scene0", 2: "true", 3: "true"}),
            command_csv(6, {12: "alk", 13: "1", 14: "joy_b_right", 15: "false"}),
            command_csv(0, {
                4: "alk",
                5: "久等了。\\n今天吃西红柿炖鸡肉哦。",
                6: "character/alk/voice/words/omatase",
                7: "false",
                8: "1",
            }),
            command_csv(0, {4: "", 5: "夜深了。", 6: "(None)", 7: "false", 8: "0"}),
            command_csv(0, {
                4: "white_tiger_known",
                5: "俺不认识你。",
                6: "(None)",
                7: "false",
                8: "3",
            }),
            command_csv(12, {19: "alk", 20: "smile"}),
            command_csv(7, {16: "alk", 17: "(None)"}),
            command_csv(99, {4: "mystery"}),
        ])
        _, commands = story.decode_scenario_bytes(raw, self.entry.logical_path)

        markdown = story.render_markdown(self.entry, commands, self.speakers)

        self.assertEqual(markdown, """# 白 个人剧情 第1话 「疑惑」

*（BGM：bgm/common/story/basic）*

*（场景切换：scene0）*

*（阿尔克入场：站位 1，表情 joy_b_right）*

**阿尔克**🔊：久等了。  
　今天吃西红柿炖鸡肉哦。

**旁白**：夜深了。

**兽人**：俺不认识你。

*（阿尔克换表情：smile）*

*（阿尔克退场）*

<!-- kind=99 cols={"4": "mystery"} -->
""")
        self.assertNotIn("显示消息窗口", markdown)
        self.assertNotIn("**白**", markdown)

    def test_jsonl_keeps_one_physical_record_per_command_and_dialogue_fields(self):
        raw = scenario_bytes([
            command_csv(0, {
                4: "white_tiger_known",
                5: "第一行\n第二行",
                6: "(None)",
                7: "false",
                8: "3",
            }),
            command_csv(99, {31: "1,2,3"}),
        ])
        _, commands = story.decode_scenario_bytes(raw, self.entry.logical_path)

        rendered = story.render_jsonl(commands, self.speakers)
        physical_lines = rendered.splitlines()
        records = [json.loads(line) for line in physical_lines]

        self.assertEqual(len(physical_lines), 2)
        self.assertEqual(records[0]["line"], 1)
        self.assertEqual(records[0]["kind"], 0)
        self.assertEqual(records[0]["op"], "Text")
        self.assertEqual(records[0]["speaker_code"], "white_tiger_known")
        self.assertEqual(records[0]["speaker_name"], "兽人")
        self.assertEqual(records[0]["text"], "第一行\n第二行")
        self.assertIsNone(records[0]["voice"])
        self.assertEqual(records[0]["raw"][6], "(None)")
        self.assertEqual(records[1]["op"], "unknown")
        self.assertEqual(records[1]["args"], {"col_31": "1,2,3"})
        self.assertTrue(rendered.endswith("\n"))

    def test_unknown_speaker_falls_back_to_code_without_losing_text(self):
        raw = scenario_bytes([
            command_csv(0, {4: "future_npc", 5: "还在。", 6: "(None)", 7: "false", 8: "0"}),
        ])
        _, commands = story.decode_scenario_bytes(raw, self.entry.logical_path)

        markdown = story.render_markdown(self.entry, commands, self.speakers)
        record = json.loads(story.render_jsonl(commands, self.speakers))

        self.assertIn("**future_npc**：还在。", markdown)
        self.assertEqual(record["speaker_name"], "future_npc")


class TestStoryCatalog(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.store = root / "upload"
        self.store.mkdir()
        self.pathlist = root / "WF_PATHLIST_recovered.txt"

        self.logicals = [
            "master/story/character_story_quest/white_tiger_001/scenario.orderedmap",
            "master/story/character_story_quest/white_tiger_2anv_001/scenario.orderedmap",
            "master/story/character_story_quest/white_tiger_xm20_001/scenario.orderedmap",
            "master/story/story_quest/main_chapter_01/main_chapter_01_01/scenario.orderedmap",
            "master/story/story_event_quest/event_a/event_chapter_00_01/scenario.orderedmap",
            "master/story/story_event_quest/event_b/event_chapter_00_01/scenario.orderedmap",
            "master/story/advent_event/advent_001/prologue/scenario.orderedmap",
            "master/story/system_quest/treasure_shop/scenario.orderedmap",
        ]
        self.pathlist.write_text("\n".join(self.logicals) + "\n", encoding="utf-8")
        for logical in self.logicals:
            write_scenario(self.store, logical)

        character_rows = {
            "10": wide_csv(37, {0: "white_tiger", 27: "10"}),
            "131086": wide_csv(37, {0: "white_tiger_2anv", 27: "10"}),
            "243013": wide_csv(37, {0: "white_tiger_xm20", 27: "10"}),
            "700010": wide_csv(37, {0: "white_tiger_storyless", 27: "10"}),
            "700015": wide_csv(37, {0: "white_tiger_chapter12", 27: "700015"}),
        }
        text_rows = {
            character_id: wide_csv(12, {0: "白"})
            for character_id in character_rows
        }
        write_flat_table(
            self.store, "master/character/character.orderedmap", character_rows)
        write_flat_table(
            self.store, "master/character/character_text.orderedmap", text_rows)
        write_flat_table(
            self.store,
            "master/story/story_character.orderedmap",
            {
                "alk": wide_csv(6, {0: "阿尔克"}),
                "white_tiger_known": wide_csv(6, {0: "兽人"}),
            },
        )

        character_quests = {
            "301": wide_csv(128, {
                0: "10", 3: "疑惑", 49: "10", 50: "1",
                126: "story/character_story_quest/white_tiger_001/scenario",
            }),
            "13108601": wide_csv(128, {
                0: "131086", 3: "同样的伤痕", 49: "131086", 50: "1",
                126: "story/character_story_quest/white_tiger_2anv_001/scenario",
            }),
            "24301301": wide_csv(128, {
                0: "243013", 3: "圣诞老人驯鹿白虎", 49: "243013", 50: "1",
                126: "story/character_story_quest/white_tiger_xm20_001/scenario",
            }),
        }
        write_flat_table(
            self.store, "master/quest/character_quest.orderedmap", character_quests)

        write_tree_table(
            self.store,
            "master/quest/main_quest.orderedmap",
            {"1": {"1": {"1": wide_csv(126, {
                0: "1001001", 1: "降落于世界",
                124: "story/story_quest/main_chapter_01/main_chapter_01_01/scenario",
            })}}},
        )
        write_tree_table(
            self.store,
            "master/quest/event/story_event_single_quest.orderedmap",
            {"100": {"1": wide_csv(129, {
                0: "100001", 2: "活动甲",
                126: "story/story_event_quest/event_a/event_chapter_00_01/scenario",
            })}},
        )
        write_tree_table(
            self.store,
            "master/quest/event/world_story_event_quest.orderedmap",
            {"200": {"1": wide_csv(130, {
                0: "200001", 2: "活动乙",
                125: "story/story_event_quest/event_b/event_chapter_00_01/scenario",
            })}},
        )
        write_tree_table(
            self.store,
            "master/quest/event/advent_event_quest.orderedmap",
            {"1": {
                "1": wide_csv(132, {
                    0: "1001", 2: "序章",
                    130: "story/advent_event/advent_001/prologue/scenario",
                }),
                "2": wide_csv(132, {
                    0: "1002", 2: "清单外",
                    130: "story/advent_event/unlisted/extra/scenario",
                }),
            }},
        )
        write_scenario(
            self.store,
            "master/story/advent_event/unlisted/extra/scenario.orderedmap",
        )
        write_tree_table(
            self.store,
            "master/tutorial/triggered_tutorial.orderedmap",
            {"2": {"1": wide_csv(36, {
                0: "treasure_shop_unlocked", 22: "万事屋一号店开张",
                26: "story/system_quest/treasure_shop/scenario",
            })}},
        )

        self.catalog = story.StoryCatalog(self.store, self.pathlist)

    def test_character_query_uses_identity_family_and_excludes_same_name_npc(self):
        expected = [
            "white_tiger_001",
            "white_tiger_2anv_001",
            "white_tiger_xm20_001",
        ]
        for query in (
            "白",
            "10",
            "white_tiger",
            "700010",
            "white_tiger_storyless",
        ):
            with self.subTest(query=query):
                entries = self.catalog.select_character(query)
                self.assertEqual([entry.relative_dir for entry in entries], expected)
                self.assertNotIn(
                    "white_tiger_chapter12",
                    {entry.character_code for entry in entries},
                )

    def test_quest_sources_attach_titles_ids_and_stable_order(self):
        by_relative = {entry.relative_dir: entry for entry in self.catalog.entries}

        self.assertEqual(by_relative["white_tiger_001"].quest_id, "301")
        self.assertEqual(by_relative["white_tiger_001"].title, "疑惑")
        self.assertEqual(by_relative["white_tiger_001"].episode, 1)
        self.assertEqual(
            by_relative["main_chapter_01/main_chapter_01_01"].title,
            "降落于世界",
        )
        self.assertEqual(
            by_relative["event_a/event_chapter_00_01"].title,
            "活动甲",
        )
        self.assertEqual(
            by_relative["event_b/event_chapter_00_01"].title,
            "活动乙",
        )
        self.assertEqual(by_relative["advent_001/prologue"].title, "序章")
        self.assertEqual(by_relative["treasure_shop"].title, "万事屋一号店开张")

    def test_quest_basename_ambiguity_is_reported_instead_of_guessed(self):
        with self.assertRaisesRegex(LookupError, "event_a/event_chapter_00_01"):
            self.catalog.select_quest("event_chapter_00_01")

        selected = self.catalog.select_quest(
            "story_event_quest/event_b/event_chapter_00_01")
        self.assertEqual(selected.relative_dir, "event_b/event_chapter_00_01")

    def test_pathlist_is_the_export_contract_and_reports_extra_references(self):
        self.assertEqual(len(self.catalog.entries), len(self.logicals))
        self.assertEqual(
            self.catalog.referenced_not_in_pathlist,
            ("master/story/advent_event/unlisted/extra/scenario.orderedmap",),
        )
        self.assertNotIn(
            "unlisted/extra",
            {entry.relative_dir for entry in self.catalog.entries},
        )

    def test_story_character_alias_table_is_authoritative(self):
        speakers = story.load_speakers(self.store)

        self.assertEqual(speakers["alk"].name, "阿尔克")
        self.assertEqual(speakers["white_tiger_known"].name, "兽人")


class TestStoryCli(unittest.TestCase):
    setUp = TestStoryCatalog.setUp

    def test_list_and_validate_are_read_only_and_validate_ends_with_stable_json(self):
        output = Path(self.temp.name) / "must-not-exist"
        list_stdout = io.StringIO()
        with redirect_stdout(list_stdout):
            list_code = story.main(
                ["--store", str(self.store), "--list", "character_story_quest",
                 "--out", str(output)],
                pathlist=self.pathlist,
            )

        self.assertEqual(list_code, 0)
        self.assertIn("quest_id\ttitle\tcharacter_name\tscenario", list_stdout.getvalue())
        self.assertIn("301\t疑惑\t白\twhite_tiger_001", list_stdout.getvalue())
        self.assertFalse(output.exists())

        validate_stdout = io.StringIO()
        with redirect_stdout(validate_stdout):
            validate_code = story.main(
                ["--store", str(self.store), "--validate", "--out", str(output)],
                pathlist=self.pathlist,
            )

        self.assertEqual(validate_code, 0)
        self.assertFalse(output.exists())
        last_line = validate_stdout.getvalue().splitlines()[-1]
        summary = json.loads(last_line)
        self.assertEqual(summary["scenario_total"], len(self.logicals))
        self.assertEqual(summary["decoded"], len(self.logicals))
        self.assertEqual(summary["decode_failures"], 0)
        self.assertEqual(summary["referenced_not_in_pathlist"], 1)
        self.assertEqual(
            last_line,
            json.dumps(summary, ensure_ascii=False, sort_keys=True),
        )

    def test_character_export_defaults_to_both_formats_and_family_variants(self):
        output = Path(self.temp.name) / "export"
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            code = story.main(
                ["--store", str(self.store), "--character", "白", "--out", str(output)],
                pathlist=self.pathlist,
            )

        self.assertEqual(code, 0)
        for relative in (
            "white_tiger_001",
            "white_tiger_2anv_001",
            "white_tiger_xm20_001",
        ):
            target = output / "character_story_quest" / relative
            self.assertTrue((target / "scenario.md").is_file())
            self.assertTrue((target / "scenario.jsonl").is_file())
        self.assertIn('"stories": 3', stdout.getvalue())
        self.assertIn('"files": 6', stdout.getvalue())

    def test_single_quest_format_writes_only_requested_file(self):
        output = Path(self.temp.name) / "single"

        with redirect_stdout(io.StringIO()):
            code = story.main(
                ["--store", str(self.store), "--quest", "white_tiger_001",
                 "--format", "md", "--out", str(output)],
                pathlist=self.pathlist,
            )

        target = output / "character_story_quest" / "white_tiger_001"
        self.assertEqual(code, 0)
        self.assertTrue((target / "scenario.md").is_file())
        self.assertFalse((target / "scenario.jsonl").exists())

    def test_export_rejects_output_inside_the_store(self):
        stderr = io.StringIO()

        with redirect_stderr(stderr):
            code = story.main(
                ["--store", str(self.store), "--quest", "white_tiger_001",
                 "--out", str(self.store)],
                pathlist=self.pathlist,
            )

        self.assertEqual(code, 2)
        self.assertIn("store", stderr.getvalue().lower())
        self.assertFalse((self.store / "character_story_quest").exists())

    def test_output_rejects_cross_category_parent_traversal(self):
        entry = story.StoryEntry(
            category="character_story_quest",
            relative_dir="../escape",
            logical_path=self.logicals[0],
        )

        with self.assertRaisesRegex(ValueError, r"traversal|escape|\.\."):
            story.export_entries(
                [entry], self.store, story.load_speakers(self.store),
                Path(self.temp.name) / "traversal",
            )

    def test_export_replaces_a_hardlink_leaf_without_mutating_its_peer(self):
        output = Path(self.temp.name) / "hardlink-output"
        target_dir = output / "character_story_quest" / "white_tiger_001"
        target_dir.mkdir(parents=True)
        peer = Path(self.temp.name) / "must-stay.txt"
        peer.write_text("must stay", encoding="utf-8")
        os.link(peer, target_dir / "scenario.md")

        with redirect_stdout(io.StringIO()):
            code = story.main(
                ["--store", str(self.store), "--quest", "white_tiger_001",
                 "--format", "md", "--out", str(output)],
                pathlist=self.pathlist,
            )

        self.assertEqual(code, 0)
        self.assertEqual(peer.read_text(encoding="utf-8"), "must stay")
        self.assertNotEqual(
            (target_dir / "scenario.md").read_text(encoding="utf-8"),
            "must stay",
        )

    def test_export_rejects_a_symlink_output_leaf_when_supported(self):
        output = Path(self.temp.name) / "symlink-output"
        target_dir = output / "character_story_quest" / "white_tiger_001"
        target_dir.mkdir(parents=True)
        peer = Path(self.temp.name) / "symlink-peer.txt"
        peer.write_text("must stay", encoding="utf-8")
        try:
            os.symlink(peer, target_dir / "scenario.md")
        except OSError as exc:
            self.skipTest(f"symlink creation is unavailable: {exc}")

        stderr = io.StringIO()
        with redirect_stderr(stderr):
            code = story.main(
                ["--store", str(self.store), "--quest", "white_tiger_001",
                 "--format", "md", "--out", str(output)],
                pathlist=self.pathlist,
            )

        self.assertEqual(code, 2)
        self.assertIn("link", stderr.getvalue().lower())
        self.assertEqual(peer.read_text(encoding="utf-8"), "must stay")

    def test_batch_decode_failure_does_not_leave_earlier_story_outputs(self):
        output = Path(self.temp.name) / "batch-output"
        good = self.catalog.select_quest("white_tiger_001")
        bad = story.StoryEntry(
            category="character_story_quest",
            relative_dir="missing_story",
            logical_path=(
                "master/story/character_story_quest/"
                "missing_story/scenario.orderedmap"
            ),
        )

        with self.assertRaises(FileNotFoundError):
            story.export_entries(
                [good, bad], self.store, story.load_speakers(self.store), output)

        self.assertFalse(output.exists())

    def test_commit_failure_rolls_back_all_preexisting_output_files(self):
        output = Path(self.temp.name) / "rollback-output"
        target_dir = output / "character_story_quest" / "white_tiger_001"
        target_dir.mkdir(parents=True)
        markdown = target_dir / "scenario.md"
        jsonl = target_dir / "scenario.jsonl"
        markdown.write_text("old markdown", encoding="utf-8")
        jsonl.write_text("old jsonl", encoding="utf-8")
        real_replace = os.replace
        failed = False

        def fail_second_commit(source, target):
            nonlocal failed
            target_path = Path(target)
            if target_path == jsonl and not failed:
                failed = True
                raise OSError("injected second replace failure")
            return real_replace(source, target)

        with patch.object(story.os, "replace", side_effect=fail_second_commit):
            with self.assertRaisesRegex(OSError, "injected"):
                story.export_entries(
                    [self.catalog.select_quest("white_tiger_001")],
                    self.store,
                    story.load_speakers(self.store),
                    output,
                )

        self.assertEqual(markdown.read_text(encoding="utf-8"), "old markdown")
        self.assertEqual(jsonl.read_text(encoding="utf-8"), "old jsonl")
        self.assertFalse(list(target_dir.glob(".*.tmp")))

    def test_failed_rollback_retains_the_only_recovery_backup(self):
        output = Path(self.temp.name) / "rollback-recovery-output"
        target_dir = output / "character_story_quest" / "white_tiger_001"
        target_dir.mkdir(parents=True)
        markdown = target_dir / "scenario.md"
        jsonl = target_dir / "scenario.jsonl"
        markdown.write_text("old markdown", encoding="utf-8")
        jsonl.write_text("old jsonl", encoding="utf-8")
        real_replace = os.replace
        commit_failed = False

        def fail_commit_and_rollback(source, target):
            nonlocal commit_failed
            source_path = Path(source)
            target_path = Path(target)
            if target_path == jsonl and not commit_failed:
                commit_failed = True
                raise OSError("injected commit failure")
            if target_path == markdown and source_path.suffix == ".backup":
                raise OSError("injected rollback failure")
            return real_replace(source, target)

        with patch.object(
            story.os, "replace", side_effect=fail_commit_and_rollback
        ):
            with self.assertRaisesRegex(
                RuntimeError, "rollback was incomplete"
            ) as caught:
                story.export_entries(
                    [self.catalog.select_quest("white_tiger_001")],
                    self.store,
                    story.load_speakers(self.store),
                    output,
                )

        recovery_backups = list(target_dir.glob(".scenario.md.*.backup"))
        self.assertEqual(len(recovery_backups), 1)
        self.assertEqual(
            recovery_backups[0].read_text(encoding="utf-8"), "old markdown")
        self.assertIn(str(recovery_backups[0]), str(caught.exception))

    def test_missing_store_reports_error_without_silent_fallback(self):
        missing = Path(self.temp.name) / "missing-store"
        stderr = io.StringIO()

        with redirect_stderr(stderr):
            code = story.main(
                ["--store", str(missing), "--list"],
                pathlist=self.pathlist,
            )

        self.assertEqual(code, 2)
        self.assertIn(str(missing), stderr.getvalue())

    def test_validate_counts_failures_unknowns_speakers_and_missing_titles(self):
        good_logical = (
            "master/story/character_story_quest/"
            "validation_good/scenario.orderedmap"
        )
        bad_logical = (
            "master/story/character_story_quest/"
            "validation_bad/scenario.orderedmap"
        )
        write_scenario(self.store, good_logical, [
            command_csv(0, {
                4: "future_npc", 5: "未来。", 6: "(None)", 7: "false", 8: "0",
            }),
            command_csv(99, {4: "kept"}),
        ])
        bad_path = core.table_path(self.store, bad_logical)
        bad_path.parent.mkdir(parents=True, exist_ok=True)
        bad_path.write_bytes(b"broken")
        entries = (
            story.StoryEntry(
                "character_story_quest", "validation_good", good_logical,
                character_name="白", episode=1,
            ),
            story.StoryEntry(
                "character_story_quest", "validation_bad", bad_logical,
                character_name="白", episode=2,
            ),
        )
        catalog = SimpleNamespace(
            store=self.store,
            entries=entries,
            referenced_not_in_pathlist=(),
            unreferenced_pathlist=(),
        )

        report = story.validate_catalog(catalog, story.load_speakers(self.store))

        self.assertEqual(report.scenario_total, 2)
        self.assertEqual(report.decoded, 1)
        self.assertEqual(len(report.decode_failures), 1)
        self.assertEqual(report.unknown_opcodes, {99: 1})
        self.assertEqual(report.unresolved_speakers, {"future_npc": 1})
        self.assertEqual(report.title_association_missing, (
            good_logical,
            bad_logical,
        ))
        self.assertFalse(report.ok)

    def test_default_validate_rejects_a_truncated_manifest_contract(self):
        truncated = Path(self.temp.name) / "truncated-pathlist.txt"
        truncated.write_text(self.logicals[0] + "\n", encoding="utf-8")
        stdout = io.StringIO()

        with patch.object(story, "DEFAULT_PATHLIST", truncated):
            with redirect_stdout(stdout):
                code = story.main(["--store", str(self.store), "--validate"])

        self.assertEqual(code, 1)
        summary = json.loads(stdout.getvalue().splitlines()[-1])
        self.assertFalse(summary["ok"])
        self.assertGreater(summary["manifest_contract_errors"], 0)


class TestStoryCliStreams(unittest.TestCase):
    def test_cli_entrypoint_configures_stdout_and_stderr_as_utf8(self):
        stdout = SimpleNamespace(reconfigure=Mock())
        stderr = SimpleNamespace(reconfigure=Mock())

        with patch.object(story.sys, "stdout", stdout):
            with patch.object(story.sys, "stderr", stderr):
                story.configure_cli_streams()

        stdout.reconfigure.assert_called_once_with(
            encoding="utf-8", errors="replace")
        stderr.reconfigure.assert_called_once_with(
            encoding="utf-8", errors="replace")


if __name__ == "__main__":
    unittest.main(verbosity=2)
