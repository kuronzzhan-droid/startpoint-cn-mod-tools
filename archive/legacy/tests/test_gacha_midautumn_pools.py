# -*- coding: utf-8 -*-
"""中秋 12 人以 0%／不可兑换入两池的门禁。

基线是**冻结**的改前两池快照（`fixtures/gacha_pools_before_midautumn.json.gz`，
取自 2026-09-21 本轮落盘前的 `assets/gacha.json`），并在用例里反过来证明
它就是上一轮 seasonal7 修订的产物 —— live 文件一旦被手改，这里立刻变红。

断言按显示概率与逐字段相等写：0 权重不该动官方那一档的任何一格，
所以「其余条目逐格不变」是严格的字典相等，不是近似。
"""
from __future__ import annotations

import gzip
import json
import sys
import unittest
from copy import deepcopy
from fractions import Fraction
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    pass  # Imports resolve from this checkout/package, not external source copies.

import wf_gacha_midautumn_pools as rev  # noqa: E402
import wf_gacha_odds_sync as odds_sync  # noqa: E402
import wf_gacha_seasonal7_pools as s7  # noqa: E402
import wf_midautumn_specs as specs  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
FIXTURE = FIXTURES / "gacha_pools_before_midautumn.json.gz"
S7_FIXTURE = FIXTURES / "gacha_pools_before_seasonal7.json.gz"
GACHA_JSON = TOOLS.parent / "assets" / "gacha.json"
SENTINEL = "999999"      # 哨兵键：证明改动不外溢到别的卡池
# 竞速池里现成的 0% 挂名行，本次新行的逐格先例
ZERO_PRECEDENT_ID = 119950


def load_pools(path: Path) -> dict:
    return json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))


def load_baseline() -> dict:
    return {**load_pools(FIXTURE), SENTINEL: {"name": "sentinel", "pool": {"1": []}}}


class MidautumnPoolRevisionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.before = load_baseline()
        cls.after = rev.revise(cls.before)

    def ids(self, pool_id: str, source: dict | None = None) -> list[int]:
        source = source or self.after
        return [int(e["id"]) for e in source[pool_id]["pool"]["1"]]

    def entry(self, pool_id: str, cid: int, source: dict | None = None) -> dict:
        source = source or self.after
        matches = [e for e in source[pool_id]["pool"]["1"] if int(e["id"]) == cid]
        self.assertEqual(len(matches), 1, f"{pool_id}/{cid} 行数不为 1")
        return matches[0]

    # --- 名单 ---

    def test_roster_matches_the_batch_spec_exactly(self):
        """名单与顺序都必须等于 wf_midautumn_specs.SPECS 的声明序。"""
        self.assertEqual(list(rev.MIDAUTUMN12),
                         [spec.cid for spec in specs.SPECS.values()])

    def test_roster_is_twelve_distinct_custom_ids(self):
        self.assertEqual(len(rev.MIDAUTUMN12), 12)
        self.assertEqual(len(set(rev.MIDAUTUMN12)), 12)
        for cid in rev.MIDAUTUMN12:
            self.assertTrue(rev.is_custom(cid), cid)

    def test_the_two_water_men_are_excluded(self):
        self.assertEqual(rev.WATER_PAIR, (129987, 129986))
        for cid in rev.WATER_PAIR:
            self.assertNotIn(cid, rev.MIDAUTUMN12)
            for pool_id in (rev.ABYSS, rev.RACING):
                self.assertNotIn(cid, self.ids(pool_id), (pool_id, cid))

    def test_baseline_really_lacked_the_twelve(self):
        """基线若已经有这 12 人，上面那些用例会变成空转 —— 这条先把它钉死。"""
        for pool_id in (rev.ABYSS, rev.RACING):
            before_ids = set(self.ids(pool_id, self.before))
            self.assertEqual(before_ids & set(rev.MIDAUTUMN12), set(), pool_id)

    def test_frozen_baseline_is_the_seasonal7_result(self):
        expected = s7.revise(load_pools(S7_FIXTURE))
        for pool_id in (rev.ABYSS, rev.RACING):
            self.assertEqual(self.before[pool_id], expected[pool_id], pool_id)

    # --- 概率 ---

    def test_twelve_are_zero_weight_in_both_pools(self):
        for pool_id in (rev.ABYSS, rev.RACING):
            for cid in rev.MIDAUTUMN12:
                self.assertEqual(int(self.entry(pool_id, cid)["odds"]), 0, (pool_id, cid))
                self.assertEqual(self.entry(pool_id, cid)["rarity"], 0.0, (pool_id, cid))

    def test_twelve_have_zero_actual_probability(self):
        for pool_id in (rev.ABYSS, rev.RACING):
            for cid in rev.MIDAUTUMN12:
                self.assertEqual(rev.probability(self.after[pool_id], cid),
                                 Fraction(0), (pool_id, cid))

    def test_displayed_percent_is_zero(self):
        for pool_id in (rev.ABYSS, rev.RACING):
            for cid in rev.MIDAUTUMN12:
                self.assertEqual(rev.display_percent(self.after[pool_id], cid),
                                 "0.000", (pool_id, cid))

    def test_display_formula_agrees_with_the_odds_sync_tool(self):
        """display_percent 与真正写 CDN 表的工具必须是同一套 floor 规则。"""
        for pool_id in (rev.ABYSS, rev.RACING):
            pool = self.after[pool_id]
            rows = pool["pool"]["1"]
            total = sum(int(e["odds"]) for e in rows)
            rank_pct = pool["rankRates"]["normal"][0] / 10.0
            for e in rows:
                self.assertEqual(rev.display_percent(pool, int(e["id"])),
                                 odds_sync.fmt_odds(rank_pct * int(e["odds"]) / total),
                                 (pool_id, e["id"]))

    def test_five_star_weight_total_is_unchanged(self):
        for pool_id, total in ((rev.ABYSS, rev.ABYSS_TOTAL), (rev.RACING, rev.RACING_TOTAL)):
            self.assertEqual(sum(int(e["odds"]) for e in self.before[pool_id]["pool"]["1"]),
                             total, pool_id)
            self.assertEqual(sum(int(e["odds"]) for e in self.after[pool_id]["pool"]["1"]),
                             total, pool_id)

    # --- 兑换 ---

    def test_twelve_are_not_exchangeable(self):
        for pool_id in (rev.ABYSS, rev.RACING):
            for cid in rev.MIDAUTUMN12:
                self.assertFalse(self.entry(pool_id, cid)["isExchangeable"], (pool_id, cid))

    def test_no_other_exchange_flag_flips(self):
        for pool_id in (rev.ABYSS, rev.RACING):
            for cid in self.ids(pool_id, self.before):
                self.assertEqual(self.entry(pool_id, cid)["isExchangeable"],
                                 self.entry(pool_id, cid, self.before)["isExchangeable"],
                                 f"{pool_id}/{cid}")

    # --- 逐格先例 ---

    def test_new_rows_copy_the_existing_zero_weight_listing(self):
        """字段集合、键序与每个布尔值都照抄竞速池现有的 0% 挂名行。"""
        precedent = self.entry(rev.RACING, ZERO_PRECEDENT_ID, self.before)
        self.assertEqual(int(precedent["odds"]), 0, "先例行本身必须是 0%")
        template = {k: v for k, v in precedent.items() if k != "id"}
        for pool_id in (rev.ABYSS, rev.RACING):
            for cid in rev.MIDAUTUMN12:
                entry = self.entry(pool_id, cid)
                self.assertEqual(list(entry), list(precedent), (pool_id, cid))
                self.assertEqual({k: v for k, v in entry.items() if k != "id"},
                                 template, (pool_id, cid))

    # --- 其余条目逐格不变 ---

    def test_every_pre_existing_row_is_byte_identical(self):
        for pool_id in (rev.ABYSS, rev.RACING):
            for cid in self.ids(pool_id, self.before):
                self.assertEqual(self.entry(pool_id, cid),
                                 self.entry(pool_id, cid, self.before), f"{pool_id}/{cid}")

    def test_official_rows_keep_their_exact_odds(self):
        """0 权重不占份额 ⇒ 官方那一档一格都不该重分。"""
        for pool_id in (rev.ABYSS, rev.RACING):
            official = [c for c in self.ids(pool_id, self.before) if not rev.is_custom(c)]
            self.assertTrue(official)
            for cid in official:
                self.assertEqual(rev.probability(self.after[pool_id], cid),
                                 rev.probability(self.before[pool_id], cid),
                                 f"{pool_id}/{cid}")

    def test_membership_only_grows_by_the_twelve(self):
        for pool_id in (rev.ABYSS, rev.RACING):
            self.assertEqual(set(self.ids(pool_id)) - set(self.ids(pool_id, self.before)),
                             set(rev.MIDAUTUMN12), pool_id)
            self.assertEqual(set(self.ids(pool_id, self.before)) - set(self.ids(pool_id)),
                             set(), pool_id)
            self.assertEqual(len(self.ids(pool_id)),
                             len(self.ids(pool_id, self.before)) + 12, pool_id)

    def test_other_pools_untouched(self):
        for key, value in self.before.items():
            if key in (rev.ABYSS, rev.RACING):
                continue
            self.assertEqual(self.after[key], value, key)

    def test_four_and_three_star_groups_untouched(self):
        for pool_id in (rev.ABYSS, rev.RACING):
            for group in ("2", "3"):
                self.assertEqual(self.after[pool_id]["pool"][group],
                                 self.before[pool_id]["pool"][group], (pool_id, group))

    def test_pool_header_fields_untouched(self):
        for pool_id in (rev.ABYSS, rev.RACING):
            for key, value in self.before[pool_id].items():
                if key == "pool":
                    continue
                self.assertEqual(self.after[pool_id][key], value, (pool_id, key))

    def test_input_is_not_mutated(self):
        self.assertEqual(self.before, load_baseline())

    # --- 排序 ---

    def test_twelve_are_pinned_to_the_top_of_both_pools(self):
        for pool_id in (rev.ABYSS, rev.RACING):
            self.assertEqual(self.ids(pool_id)[:12], list(rev.MIDAUTUMN12), pool_id)

    def test_seasonal7_stays_at_the_head_of_the_remaining_mod_block(self):
        for pool_id in (rev.ABYSS, rev.RACING):
            self.assertEqual(self.ids(pool_id)[12:12 + len(rev.SEASONAL7)],
                             list(rev.SEASONAL7), pool_id)

    def test_minibosses_still_sit_between_mod_and_official(self):
        for pool_id in (rev.ABYSS, rev.RACING):
            ids = self.ids(pool_id)
            index = {cid: i for i, cid in enumerate(ids)}
            last_mod = max(index[c] for c in ids
                           if rev.is_custom(c) and c not in rev.MINIBOSSES)
            first_mini = min(index[c] for c in rev.MINIBOSSES)
            last_mini = max(index[c] for c in rev.MINIBOSSES)
            first_official = min(index[c] for c in ids if not rev.is_custom(c))
            self.assertLess(last_mod, first_mini, pool_id)
            self.assertLess(last_mini, first_official, pool_id)

    def test_relative_order_inside_each_block_is_preserved(self):
        for pool_id in (rev.ABYSS, rev.RACING):
            before = self.ids(pool_id, self.before)
            after = self.ids(pool_id)
            for group in (lambda c: rev.is_custom(c) and c not in rev.MINIBOSSES
                          and c not in rev.MIDAUTUMN12,
                          lambda c: c in rev.MINIBOSSES,
                          lambda c: not rev.is_custom(c)):
                self.assertEqual([c for c in after if group(c) and c in before],
                                 [c for c in before if group(c)], pool_id)

    # --- 幂等 ---

    def test_running_twice_changes_nothing(self):
        self.assertEqual(rev.revise(self.after), self.after)

    def test_already_listed_character_is_rewritten_not_duplicated(self):
        """若有人先把某个中秋角色按 0.1% 写进了池子，本工具改成 0% 而不是再追加一行。"""
        seeded = deepcopy(self.before)
        victim = rev.MIDAUTUMN12[0]
        rows = seeded[rev.RACING]["pool"]["1"]
        donor = next(e for e in rows if int(e["id"]) == sorted(rev.MINIBOSSES)[0])
        donor["odds"] = int(donor["odds"]) - 1000
        donor["rarity"] = round(int(donor["odds"]) * 100 / rev.RACING_TOTAL, 6)
        rows.append({**rev._zero_entry(victim), "odds": 1000, "isExchangeable": True,
                     "rarity": round(1000 * 100 / rev.RACING_TOTAL, 6)})
        result = rev.revise(seeded)
        hits = [e for e in result[rev.RACING]["pool"]["1"] if int(e["id"]) == victim]
        self.assertEqual(len(hits), 1)
        self.assertEqual(int(hits[0]["odds"]), 0)
        self.assertFalse(hits[0]["isExchangeable"])
        self.assertEqual(sum(int(e["odds"]) for e in result[rev.RACING]["pool"]["1"]),
                         rev.RACING_TOTAL)

    # --- 基线门禁 ---

    def test_guard_rejects_wrong_rank_rates(self):
        broken = deepcopy(self.before)
        broken[rev.ABYSS]["rankRates"]["normal"] = [405, 245, 350]
        with self.assertRaises(rev.MidautumnPoolError):
            rev.revise(broken)

    def test_guard_rejects_missing_miniboss(self):
        broken = deepcopy(self.before)
        victim = sorted(rev.MINIBOSSES)[0]
        broken[rev.RACING]["pool"]["1"] = [e for e in broken[rev.RACING]["pool"]["1"]
                                           if int(e["id"]) != victim]
        with self.assertRaises(rev.MidautumnPoolError):
            rev.revise(broken)

    def test_guard_rejects_a_broken_weight_total(self):
        broken = deepcopy(self.before)
        broken[rev.ABYSS]["pool"]["1"][-1]["odds"] += 1
        with self.assertRaises(rev.MidautumnPoolError):
            rev.revise(broken)

    def test_guard_rejects_a_duplicated_row(self):
        broken = deepcopy(self.before)
        rows = broken[rev.RACING]["pool"]["1"]
        rows.append(deepcopy(rows[0]))
        with self.assertRaises(rev.MidautumnPoolError):
            rev.revise(broken)

    def test_guard_rejects_a_missing_pool(self):
        broken = {k: v for k, v in self.before.items() if k != rev.RACING}
        with self.assertRaises(rev.MidautumnPoolError):
            rev.revise(broken)


@unittest.skipUnless(GACHA_JSON.is_file(), "requires repo assets")
class LiveGachaStateTest(unittest.TestCase):
    """live `assets/gacha.json` 只允许处于两种状态之一：改前 == 冻结基线，改后 == revise(基线)。

    任何一次手改都会让这条红；主控跑完 `--apply` 之后它仍然绿，
    并且此后变成「已落盘」的证据。
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.baseline = load_pools(FIXTURE)
        cls.expected = rev.revise(cls.baseline)
        cls.live = json.loads(GACHA_JSON.read_text(encoding="utf-8"))

    def test_live_is_either_the_baseline_or_the_revision(self):
        live_ids = {int(e["id"]) for e in self.live[rev.ABYSS]["pool"]["1"]}
        applied = bool(live_ids & set(rev.MIDAUTUMN12))
        want = self.expected if applied else self.baseline
        for pool_id in (rev.ABYSS, rev.RACING):
            self.assertEqual(self.live[pool_id], want[pool_id],
                             f"{pool_id}: live 既不是冻结基线也不是本工具的产物"
                             f"（applied={applied}）")


if __name__ == "__main__":
    unittest.main()
