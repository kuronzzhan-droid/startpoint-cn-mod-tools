# -*- coding: utf-8 -*-
"""七角色入池 + 小Boss/上批五人概率与兑换修订的门禁。

基线是**冻结**的改前两池快照（`fixtures/gacha_pools_before_seasonal7.json.gz`，
取自 2026-09-17 落盘前的 `assets/gacha.json`），因为 live 文件改完就不再是基线了。
断言全部按显示概率口径写，不依赖具体权重整数，官方余数怎么分都不影响判据。
最后一组用例反过来核对 live `assets/gacha.json` 确实等于 `revise(基线)` 的结果。
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
    sys.path.insert(0, str(TOOLS))

import wf_gacha_seasonal7_pools as rev  # noqa: E402

GACHA_JSON = TOOLS.parent / "assets" / "gacha.json"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "gacha_pools_before_seasonal7.json.gz"
# 哨兵键：证明改动不会外溢到别的卡池
SENTINEL = "999999"


def load_baseline() -> dict:
    pools = json.loads(gzip.decompress(FIXTURE.read_bytes()).decode("utf-8"))
    return {**pools, SENTINEL: {"name": "sentinel", "pool": {"1": []}}}


class SeasonalPoolRevisionTest(unittest.TestCase):
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

    # --- 概率 ---

    def test_seasonal7_abyss_rate_is_two_tenths_percent(self):
        for cid in rev.SEASONAL7:
            self.assertEqual(rev.probability(self.after[rev.ABYSS], cid),
                             Fraction(2, 1000), cid)

    def test_seasonal7_racing_rate_is_one_percent(self):
        for cid in rev.SEASONAL7:
            self.assertEqual(rev.probability(self.after[rev.RACING], cid),
                             Fraction(1, 100), cid)

    def test_prev_batch_and_minibosses_drop_to_one_tenth_percent(self):
        for cid in tuple(rev.PREV_BATCH) + tuple(sorted(rev.MINIBOSSES)):
            self.assertEqual(rev.probability(self.after[rev.ABYSS], cid),
                             Fraction(1, 1000), cid)

    def test_prev_batch_baseline_really_was_higher(self):
        """基线若已经是 0.1%，这条会红——防止把「没改」当成「改好了」。"""
        for cid in rev.PREV_BATCH:
            self.assertEqual(rev.probability(self.before[rev.ABYSS], cid),
                             Fraction(25, 10000), cid)
        for cid in sorted(rev.MINIBOSSES):
            self.assertEqual(rev.probability(self.before[rev.ABYSS], cid),
                             Fraction(2, 1000), cid)

    def test_other_mod_characters_keep_their_abyss_rate(self):
        keep = [cid for cid in self.ids(rev.ABYSS, self.before)
                if rev.is_custom(cid)
                and cid not in rev.MINIBOSSES and cid not in rev.PREV_BATCH]
        self.assertTrue(keep)
        for cid in keep:
            self.assertEqual(rev.probability(self.after[rev.ABYSS], cid),
                             rev.probability(self.before[rev.ABYSS], cid), cid)

    def test_minibosses_keep_one_percent_in_racing(self):
        for cid in sorted(rev.MINIBOSSES):
            self.assertEqual(rev.probability(self.after[rev.RACING], cid),
                             Fraction(1, 100), cid)

    def test_five_star_weight_total_is_unchanged(self):
        for pool_id, total in ((rev.ABYSS, rev.ABYSS_TOTAL), (rev.RACING, rev.RACING_TOTAL)):
            self.assertEqual(sum(int(e["odds"]) for e in self.after[pool_id]["pool"]["1"]),
                             total, pool_id)

    def test_zero_rate_bosses_stay_at_zero(self):
        for pool_id in (rev.ABYSS, rev.RACING):
            for cid in self.ids(pool_id, self.before):
                if not int(self.entry(pool_id, cid, self.before)["odds"]):
                    self.assertEqual(int(self.entry(pool_id, cid)["odds"]), 0,
                                     f"{pool_id}/{cid} 从 0% 变成可抽")

    def test_rarity_field_matches_weight(self):
        for pool_id, total in ((rev.ABYSS, rev.ABYSS_TOTAL), (rev.RACING, rev.RACING_TOTAL)):
            for e in self.after[pool_id]["pool"]["1"]:
                self.assertEqual(e["rarity"], round(int(e["odds"]) * 100 / total, 6),
                                 f"{pool_id}/{e['id']}")

    # --- 兑换 ---

    def test_seasonal7_abyss_is_not_exchangeable(self):
        for cid in rev.SEASONAL7:
            self.assertFalse(self.entry(rev.ABYSS, cid)["isExchangeable"], cid)

    def test_seasonal7_racing_is_exchangeable(self):
        for cid in rev.SEASONAL7:
            self.assertTrue(self.entry(rev.RACING, cid)["isExchangeable"], cid)

    def test_prev_batch_and_minibosses_become_exchangeable_in_abyss(self):
        for cid in tuple(rev.PREV_BATCH) + tuple(sorted(rev.MINIBOSSES)):
            self.assertFalse(self.entry(rev.ABYSS, cid, self.before)["isExchangeable"], cid)
            self.assertTrue(self.entry(rev.ABYSS, cid)["isExchangeable"], cid)

    def test_no_other_exchange_flag_flips(self):
        allowed = set(rev.PREV_BATCH) | set(rev.MINIBOSSES) | set(rev.SEASONAL7)
        for pool_id in (rev.ABYSS, rev.RACING):
            for cid in self.ids(pool_id, self.before):
                if cid in allowed:
                    continue
                self.assertEqual(self.entry(pool_id, cid)["isExchangeable"],
                                 self.entry(pool_id, cid, self.before)["isExchangeable"],
                                 f"{pool_id}/{cid}")

    # --- 排序 ---

    def test_seasonal7_is_pinned_to_the_top_of_both_pools(self):
        for pool_id in (rev.ABYSS, rev.RACING):
            self.assertEqual(self.ids(pool_id)[:7], list(rev.SEASONAL7), pool_id)

    def test_minibosses_sit_between_mod_and_official(self):
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

    def test_racing_minibosses_really_moved(self):
        """基线里小 Boss 在最前，若没挪动这条会红。"""
        self.assertEqual(self.ids(rev.RACING, self.before)[:15],
                         sorted(rev.MINIBOSSES, key=self.ids(rev.RACING, self.before).index))
        self.assertTrue(all(c in rev.MINIBOSSES
                            for c in self.ids(rev.RACING, self.before)[:15]))
        self.assertFalse(any(c in rev.MINIBOSSES for c in self.ids(rev.RACING)[:15]))

    def test_relative_order_inside_each_block_is_preserved(self):
        for pool_id in (rev.ABYSS, rev.RACING):
            before = self.ids(pool_id, self.before)
            after = self.ids(pool_id)
            for group in (lambda c: rev.is_custom(c) and c not in rev.MINIBOSSES
                          and c not in rev.SEASONAL7,
                          lambda c: c in rev.MINIBOSSES,
                          lambda c: not rev.is_custom(c)):
                self.assertEqual([c for c in after if group(c) and c in before],
                                 [c for c in before if group(c)], pool_id)

    # --- 不外溢 ---

    def test_membership_only_grows_by_the_seven(self):
        for pool_id in (rev.ABYSS, rev.RACING):
            self.assertEqual(set(self.ids(pool_id)) - set(self.ids(pool_id, self.before)),
                             set(rev.SEASONAL7), pool_id)
            self.assertEqual(set(self.ids(pool_id, self.before)) - set(self.ids(pool_id)),
                             set(), pool_id)

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

    def test_revise_is_idempotent_guarded(self):
        """七人已入池后再跑一次必须直接拒绝，避免重复追加。"""
        with self.assertRaises(rev.PoolRevisionError):
            rev.revise(self.after)

    def test_input_is_not_mutated(self):
        self.assertEqual(self.before, load_baseline())

    # --- 自制 ID 判据 ---

    def test_custom_id_floor_separates_the_two_families(self):
        for pool_id in (rev.ABYSS, rev.RACING):
            ids = self.ids(pool_id, self.before)
            custom = [c for c in ids if rev.is_custom(c)]
            official = [c for c in ids if not rev.is_custom(c)]
            self.assertTrue(custom and official)
            self.assertLess(max(c % 10000 for c in official),
                            min(c % 10000 for c in custom), pool_id)
        for cid in tuple(rev.SEASONAL7) + tuple(rev.PREV_BATCH) + tuple(rev.MINIBOSSES):
            self.assertTrue(rev.is_custom(cid), cid)

    def test_baseline_guards_reject_wrong_rank_rates(self):
        broken = deepcopy(self.before)
        broken[rev.ABYSS]["rankRates"]["normal"] = [405, 245, 350]
        with self.assertRaises(rev.PoolRevisionError):
            rev.revise(broken)

    def test_baseline_guards_reject_missing_miniboss(self):
        broken = deepcopy(self.before)
        rows = broken[rev.ABYSS]["pool"]["1"]
        victim = sorted(rev.MINIBOSSES)[0]
        broken[rev.ABYSS]["pool"]["1"] = [e for e in rows if int(e["id"]) != victim]
        with self.assertRaises(rev.PoolRevisionError):
            rev.revise(broken)


@unittest.skipUnless(GACHA_JSON.is_file(), "requires repo assets")
class LiveGachaMatchesRevisionTest(unittest.TestCase):
    """live `assets/gacha.json` 的两个卡池 == `revise(冻结基线)`。

    改前基线冻结在 fixture 里，所以这条既能证明「已经落盘」，
    也能在以后有人手改卡池时立刻变红。
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.expected = rev.revise(load_baseline())
        # 2026-09-21：live 已继续往前走（中秋 12 人以 0% 挂名入池，见 wf_gacha_midautumn_pools）。
        # 这里改为核对「中秋那一轮的冻结起点」＝七角色修订落盘后的状态；
        # live 文件本身的看门狗交给 test_gacha_midautumn_pools.LiveGachaStateTest。
        after_s7 = FIXTURE.with_name("gacha_pools_before_midautumn.json.gz")
        cls.live = json.loads(gzip.decompress(after_s7.read_bytes()).decode("utf-8"))

    def test_both_pools_match_the_expected_revision(self):
        for pool_id in (rev.ABYSS, rev.RACING):
            self.assertEqual(self.live[pool_id], self.expected[pool_id], pool_id)


if __name__ == "__main__":
    unittest.main()
