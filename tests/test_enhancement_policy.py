#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""去增强策略引擎的单元测试(全部用合成 orderedmap,不依赖真实 store/.cdn)。"""
from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

MOD_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MOD_DIR))

import wf_enhancement_policy as policy_mod  # noqa: E402
import wf_quest_lib as quest  # noqa: E402
from wf_enhancement_policy import (  # noqa: E402
    BaselineUnavailable, EntrySource, OfficialBaseline, Policy, judge_entry,
    plan_content_only, rebuild_table, verify_content_only,
)

ABILITY = "master/ability/ability.orderedmap"
SOUL = "master/ability/ability_soul.orderedmap"
WHITE_TIGER_DSL = policy_mod.DROP_LOGICALS[0]


def table(rows: dict) -> bytes:
    return quest.build_node(rows)


def crc_of(data: bytes) -> int:
    import zlib
    return zlib.crc32(data) & 0xFFFFFFFF


def source(root: str, logical: str, data: bytes) -> EntrySource:
    return EntrySource(root, quest.hashed_rel(logical), crc_of(data), len(data),
                       lambda: data, len(data))


class FakeCdn:
    """临时 CDN:官方全量包 + 可选官方增量包 + 我们自己的 mod 边。"""

    def __init__(self, root: Path) -> None:
        self.root = root
        (root / "archive-common-full").mkdir(parents=True, exist_ok=True)
        (root / "archive-common-diff").mkdir(parents=True, exist_ok=True)

    def write_full(self, payloads: dict[str, bytes], seq: int = 1) -> Path:
        path = self.root / "archive-common-full" / f"pinball-1.4.0-{seq}-abcdef01.zip"
        self._write(path, payloads)
        return path

    def write_diff(self, payloads: dict[str, bytes], *, frm: str, to: str,
                   tag: str = "a1b2c3d4", seq: int = 1) -> Path:
        path = (self.root / "archive-common-diff"
                / f"pinball-{frm}-{to}-{seq}-{tag}.zip")
        self._write(path, payloads)
        return path

    @staticmethod
    def _write(path: Path, payloads: dict[str, bytes]) -> None:
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            for logical, data in payloads.items():
                archive.writestr(f"production/upload/{quest.hashed_rel(logical)}", data)

    def baseline(self) -> OfficialBaseline:
        return OfficialBaseline(self.root, cache_dir=self.root / ".cache",
                                verify_pinned=False)


class RebuildTest(unittest.TestCase):
    def test_official_rows_revert_and_content_rows_survive(self):
        official = table({"111001": "官方值", "111002": "官方值2"})
        live = table({"111001": "被平衡总包改过", "111002": "官方值2",
                      "129999": "自制角色行"})
        rebuilt, detail = rebuild_table(official, live, logical=ABILITY)
        rows = quest.parse_node(rebuilt)
        self.assertEqual("官方值", rows["111001"])
        self.assertEqual("自制角色行", rows["129999"])
        self.assertEqual(["111001"], detail.reverted_rows)
        self.assertEqual(["129999"], detail.kept_rows)
        self.assertTrue(detail.changed)
        # 官方行在前、内容行追加在后
        self.assertEqual(["111001", "111002", "129999"], list(rows))

    def test_deleted_official_row_is_restored(self):
        official = table({"a": "1", "b": "2"})
        live = table({"a": "1"})
        rebuilt, detail = rebuild_table(official, live, logical=ABILITY)
        self.assertEqual({"a": "1", "b": "2"}, quest.parse_node(rebuilt))
        self.assertEqual(["b"], detail.restored_rows)

    def test_nested_additions_inside_official_row_are_kept(self):
        official = table({"zone_a": {"0": "官方子行"}})
        live = table({"zone_a": {"0": "官方子行", "1": "模式新增子行"}})
        rebuilt, detail = rebuild_table(
            official, live, logical="master/battle/zone.orderedmap")
        self.assertEqual({"zone_a": {"0": "官方子行", "1": "模式新增子行"}},
                         quest.parse_node(rebuilt))
        self.assertEqual(["zone_a"], detail.nested_extended_rows)
        self.assertEqual([], detail.reverted_rows)

    def test_nested_value_change_is_reverted(self):
        official = table({"700007": {"8": "官方关卡"}})
        live = table({"700007": {"8": "被改成塔关卡"}})
        rebuilt, detail = rebuild_table(
            official, live, logical="master/quest/event/rush_event_quest.orderedmap")
        self.assertEqual({"700007": {"8": "官方关卡"}}, quest.parse_node(rebuilt))
        self.assertEqual(["700007"], detail.reverted_rows)

    def test_unchanged_table_returns_original_bytes(self):
        official = table({"a": "1"})
        live = table({"a": "1", "mod_rogue_boss5": "模式行"})
        rebuilt, detail = rebuild_table(official, live, logical=ABILITY)
        self.assertIs(live, rebuilt)          # 没变就不重新序列化,避免无谓字节漂移
        self.assertFalse(detail.changed)

    def test_unrecognized_addition_is_kept_but_reported(self):
        official = table({"a": "1"})
        live = table({"a": "1", "1110691": "平衡总包新增的官方角色词条"})
        rebuilt, detail = rebuild_table(official, live, logical=ABILITY)
        self.assertIn("1110691", quest.parse_node(rebuilt))
        self.assertEqual(["1110691"], detail.unrecognized_rows)

    def test_recognized_content_keys_are_not_reported(self):
        official = table({"a": "1"})
        live = table({"a": "1", "8000101": "深渊武器", "mod_rogue_z5": "模式场地",
                      "seris_dragon_king": "自制角色技能"})
        _rebuilt, detail = rebuild_table(official, live, logical=SOUL)
        self.assertEqual([], detail.unrecognized_rows)

    def test_extra_content_keys_allowlist(self):
        logical = "master/character/unique_condition.orderedmap"
        official = table({"21": "官方"})
        live = table({"21": "官方", "22": "自制"})
        _rebuilt, detail = rebuild_table(official, live, logical=logical)
        self.assertEqual([], detail.unrecognized_rows)

    def test_non_table_payload_raises(self):
        with self.assertRaises(ValueError):
            rebuild_table(quest.build_node("官方一行"), quest.build_node("改过的一行"),
                          logical="battle/foo.dsl")


class BaselineTest(unittest.TestCase):
    def test_mod_edges_and_post_tail_edges_are_not_official(self):
        with tempfile.TemporaryDirectory() as tmp:
            cdn = FakeCdn(Path(tmp))
            cdn.write_full({ABILITY: table({"a": "官方"})})
            cdn.write_diff({ABILITY: table({"a": "官方修订"})},
                           frm="1.4.53", to="1.4.54")
            cdn.write_diff({ABILITY: table({"a": "我们改的"})},
                           frm="1.4.54", to="1.4.55", tag="mod07290101")
            cdn.write_diff({ABILITY: table({"a": "更晚的官方段?不算"})},
                           frm="1.4.55", to="1.4.56", tag="deadbeef")
            baseline = cdn.baseline()
            data = baseline.get("common", quest.hashed_rel(ABILITY))
            self.assertEqual({"a": "官方修订"}, quest.parse_node(data))

    def test_index_cache_is_reused(self):
        with tempfile.TemporaryDirectory() as tmp:
            cdn = FakeCdn(Path(tmp))
            cdn.write_full({ABILITY: table({"a": "官方"})})
            first = cdn.baseline()
            first.get("common", quest.hashed_rel(ABILITY))
            cached = list((Path(tmp) / ".cache").glob("index-common-*.json"))
            self.assertEqual(1, len(cached))
            second = cdn.baseline()
            rel = quest.hashed_rel(ABILITY)
            self.assertEqual(first.identity("common", rel),
                             second.identity("common", rel))

    def test_missing_archives_raise(self):
        with tempfile.TemporaryDirectory() as tmp:
            baseline = OfficialBaseline(Path(tmp) / "empty", verify_pinned=False)
            with self.assertRaises(BaselineUnavailable):
                baseline.identity("common", "00/" + "0" * 38)

    def test_pinned_baseline_mismatch_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            cdn = FakeCdn(Path(tmp))
            cdn.write_full({logical: table({"a": "冒牌官方表"})
                            for logical in policy_mod.PINNED_BASELINES})
            baseline = OfficialBaseline(cdn.root, cache_dir=cdn.root / ".cache")
            with self.assertRaises(BaselineUnavailable):
                baseline.identity("common", quest.hashed_rel(SOUL))


class JudgeEntryTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.cdn = FakeCdn(Path(self._tmp.name))
        self.official_ability = table({"111001": "官方", "10": "白虎官方行"})
        self.cdn.write_full({
            ABILITY: self.official_ability,
            WHITE_TIGER_DSL: b"official-dsl-bytes",
        })
        self.baseline = self.cdn.baseline()
        self.policy = Policy()

    def tearDown(self):
        self._tmp.cleanup()

    def test_white_tiger_dsl_is_dropped(self):
        entry = source("common", WHITE_TIGER_DSL, b"our-modified-dsl")
        verdict = judge_entry(entry, self.baseline, self.policy)
        self.assertEqual("drop", verdict.action)
        self.assertEqual(WHITE_TIGER_DSL, verdict.logical)

    def test_dropped_entry_can_be_reverted_instead(self):
        # official_file_action=revert 只影响非 drop-list 的官方文件
        official_png = "character/alice/ui/skill_cutin_0.png"
        self.cdn.write_full({official_png: b"official-png"}, seq=2)
        baseline = self.cdn.baseline()
        entry = source("common", official_png, b"our-skin")
        self.assertEqual("drop", judge_entry(entry, baseline, self.policy).action)
        reverted = judge_entry(entry, baseline, self.policy,
                              official_file_action="revert")
        self.assertEqual("rebuild", reverted.action)
        self.assertEqual(b"official-png", reverted.data)

    def test_custom_asset_is_kept(self):
        entry = source("common", "character/seris_dragon_king/ui/x.png", b"custom")
        verdict = judge_entry(entry, self.baseline, self.policy)
        self.assertEqual("keep", verdict.action)

    def test_untouched_official_entry_is_kept(self):
        entry = source("common", ABILITY, self.official_ability)
        self.assertEqual("keep", judge_entry(entry, self.baseline, self.policy).action)

    def test_modified_table_is_rebuilt(self):
        live = table({"111001": "被改过", "10": "白虎重做", "129999": "自制角色"})
        verdict = judge_entry(source("common", ABILITY, live),
                              self.baseline, self.policy)
        self.assertEqual("rebuild", verdict.action)
        rows = quest.parse_node(verdict.data)
        self.assertEqual("官方", rows["111001"])
        self.assertEqual("白虎官方行", rows["10"])
        self.assertEqual("自制角色", rows["129999"])

    def test_plan_summary_counts(self):
        live = table({"111001": "被改过", "10": "白虎重做", "129999": "自制角色"})
        sources = [
            source("common", ABILITY, live),
            source("common", WHITE_TIGER_DSL, b"our-modified-dsl"),
            source("common", "character/seris_dragon_king/ui/x.png", b"custom"),
        ]
        _verdicts, summary = plan_content_only(sources, self.baseline, self.policy)
        self.assertEqual({"entries": 3, "kept": 1, "dropped": 1, "rebuilt": 1},
                         {k: summary[k] for k in ("entries", "kept", "dropped", "rebuilt")})
        self.assertEqual(2, summary["revertedRows"])
        self.assertEqual([WHITE_TIGER_DSL], summary["droppedLogicals"])


class VerifyTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.cdn = FakeCdn(Path(self._tmp.name))
        self.cdn.write_full({
            ABILITY: table({"111001": "官方"}),
            WHITE_TIGER_DSL: b"official-dsl-bytes",
        })
        self.baseline = self.cdn.baseline()
        self.policy = Policy()

    def tearDown(self):
        self._tmp.cleanup()

    def test_clean_pack_passes(self):
        clean = table({"111001": "官方", "129999": "自制角色"})
        problems = verify_content_only(
            [source("common", ABILITY, clean)], self.baseline, self.policy,
            expect_content_keys={ABILITY: ["129999"]})
        self.assertEqual([], problems)

    def test_enhancement_residue_is_flagged(self):
        dirty = table({"111001": "被改过", "129999": "自制角色"})
        problems = verify_content_only(
            [source("common", ABILITY, dirty)], self.baseline, self.policy)
        self.assertEqual(1, len(problems))
        self.assertIn("增强残留", problems[0])

    def test_missing_content_row_is_flagged(self):
        clean = table({"111001": "官方"})
        problems = verify_content_only(
            [source("common", ABILITY, clean)], self.baseline, self.policy,
            expect_content_keys={ABILITY: ["129999"]})
        self.assertEqual(1, len(problems))
        self.assertIn("内容行缺失", problems[0])

    def test_missing_table_is_flagged(self):
        problems = verify_content_only(
            [], self.baseline, self.policy, expect_content_keys={ABILITY: ["129999"]})
        self.assertEqual(1, len(problems))
        self.assertIn("包里没有这张表", problems[0])

    def test_dropped_entry_still_present_is_flagged(self):
        problems = verify_content_only(
            [source("common", WHITE_TIGER_DSL, b"our-modified-dsl")],
            self.baseline, self.policy)
        self.assertEqual(1, len(problems))
        self.assertIn("drop-list", problems[0])

    def test_missing_official_row_is_flagged(self):
        stripped = table({"129999": "自制角色"})
        problems = verify_content_only(
            [source("common", ABILITY, stripped)], self.baseline, self.policy)
        self.assertTrue(any("官方行 111001 丢失" in problem for problem in problems))


class ContentContractTest(unittest.TestCase):
    """内容契约本身的自检:金样期望值别写错。"""

    def test_expected_rows_cover_three_characters_and_weapons(self):
        expected = policy_mod.EXPECTED_CONTENT_ROWS
        self.assertEqual(("129999", "139999", "149999"),
                         expected["master/character/character.orderedmap"])
        self.assertEqual(15, len(expected["master/ability/ability_soul.orderedmap"]))
        self.assertEqual("8000115",
                         expected["master/ability/ability_soul.orderedmap"][-1])
        self.assertIn("700099",
                      expected["master/quest/event/rush_event_quest.orderedmap"])

    def test_every_expected_row_is_recognised_as_content(self):
        policy = Policy()
        for logical, keys in policy_mod.EXPECTED_CONTENT_ROWS.items():
            for key in keys:
                self.assertTrue(policy.is_content_key(logical, key),
                                f"{logical}:{key} 没被内容规则识别")

    def test_drop_list_maps_to_stable_rel(self):
        rels = policy_mod.drop_rels()
        self.assertEqual({"06/5a08cd6477e519ce7a47847659bc65917112dd"}, set(rels))


if __name__ == "__main__":
    unittest.main()
