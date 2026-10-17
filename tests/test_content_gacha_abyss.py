"""深渊840后规格：实际概率、排序、红标、兑换与外池保护。"""
from copy import deepcopy
from fractions import Fraction
from pathlib import Path
import sys
import unittest
import tempfile

sys.path.insert(0, str(Path(__file__).parents[1]))
import wf_content_gacha as common
import wf_content_gacha_abyss as rules
import wf_content_gacha_candidate as candidate
import wf_gacha_odds_sync as odds


def source():
    ids = [149990, 129992, 139995, *rules.LEGACY_22, 10, 111001]
    ids += sorted(common.MINIBOSSES)
    ids += [cid for cid in rules.FEATURED if cid not in ids]
    ids += sorted(common.BIG_BOSS_ZERO - set(ids))
    weights = {cid: 906 for cid in rules.LEGACY_22}
    weights.update({cid: 3443 for cid in (129992, 139995)})
    weights.update({cid: 1000 for cid in common.MINIBOSSES})
    weights.update({cid: 0 for cid in common.BIG_BOSS_ZERO | set(rules.FEATURED)})
    weights.update({10: 10001, 111001: 150000 - sum(weights.values()) - 10001})
    entries = [dict(id=cid, rank=5, odds=weights[cid], isRateUp=False,
                    isLimited=cid in rules.LEGACY_22, isExchangeable=True,
                    trialReadingForced=False) for cid in ids]
    abyss = dict(rankRates=dict(normal=[150, 350, 500], multiGuarantee=[150, 850]),
                 pool={"1": entries, "2": [dict(id=200, odds=11)],
                       "3": [dict(id=300, odds=19)]})
    return {"990001": abyss, "990002": {"sentinel": "entire racing payload"}, "foreign": [1, 2]}


class AbyssRevisionTests(unittest.TestCase):
    def test_native_nested_client_bytes_match_server_order_probability_and_flags(self):
        abyss = rules.revise_abyss(source())["990001"]
        pointer = [""] * 17
        pointer[11], pointer[14], pointer[15], pointer[16] = "rarity", "rank3", "rank4", "rank5"
        definitions = dict(candidate.odds_definitions(pointer, abyss))
        self.assertEqual(["5,150", "4,350", "3,500"], definitions["rarity"])
        lines = definitions["rank5"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rank5.orderedmap"
            path.write_bytes(odds.build_nested("rank5", [str(i) for i in range(len(lines))], lines))
            _, keys, decoded = odds.read_nested(path, "master/gacha_odds/rank5.orderedmap")
        self.assertEqual([str(i) for i in range(len(lines))], keys)
        parsed = [line.split(",") for line in decoded]
        self.assertEqual([e["id"] for e in abyss["pool"]["1"]], [int(row[0]) for row in parsed])
        for entry, row in zip(abyss["pool"]["1"], parsed):
            if entry['id'] in rules.FEATURED:
                self.assertEqual('true', row[3])
            self.assertEqual(common.probability(abyss, entry["id"]),
                             Fraction(150, 1000) * Fraction(int(row[2]), sum(int(r[2]) for r in parsed)))
            self.assertEqual([bool(entry.get(f)) for f in odds.BOOL_FIELDS], [v == "true" for v in row[3:7]])

    def test_all_fixed_actual_probabilities_flags_order_and_other_pools(self):
        data = source()
        before = deepcopy(data)
        result = rules.revise_abyss(data)
        self.assertEqual(before, data)
        self.assertEqual(result, rules.revise_abyss(result))
        self.assertEqual(before["990002"], result["990002"])
        self.assertEqual(before["foreign"], result["foreign"])
        abyss = result["990001"]
        entries = abyss["pool"]["1"]
        by_id = {e["id"]: e for e in entries}
        ids = list(by_id)
        self.assertEqual(list(rules.FEATURED), ids[:5])
        anchor = ids.index(169997)
        self.assertEqual(sorted(common.MINIBOSSES), ids[anchor + 1:anchor + 16])
        self.assertEqual(150000, sum(e["odds"] for e in entries))
        for cid in common.MINIBOSSES:
            self.assertEqual(Fraction(1, 500), common.probability(abyss, cid))
            self.assertTrue(by_id[cid]["isRateUp"])
            self.assertFalse(by_id[cid]["isExchangeable"])
        for cid in rules.FEATURED:
            self.assertEqual(Fraction(1, 400), common.probability(abyss, cid))
            self.assertTrue(by_id[cid]["isRateUp"])
            self.assertFalse(by_id[cid]["isExchangeable"])
        for cid in set(rules.LEGACY_22) | rules.EXCHANGEABLE:
            self.assertEqual(0 if cid in common.BIG_BOSS_ZERO else Fraction(1, 1000),
                             common.probability(abyss, cid))
        for cid in rules.EXCHANGEABLE:
            self.assertTrue(by_id[cid]["isExchangeable"])
        for cid in common.BIG_BOSS_ZERO:
            self.assertEqual(0, common.probability(abyss, cid))
        self.assertEqual(84500, by_id[10]["odds"] + by_id[111001]["odds"])
        for group in ("2", "3"):
            self.assertEqual(before["990001"]["pool"][group], abyss["pool"][group])
        for old in before["990001"]["pool"]["1"]:
            for flag in ("isLimited", "trialReadingForced"):
                self.assertEqual(old[flag], by_id[old["id"]][flag])
        flexible = {e["id"]: e["odds"] for e in before["990001"]["pool"]["1"] if e["id"] in (10, 111001)}
        for cid, weight in flexible.items():
            self.assertLess(abs(Fraction(weight * 84500, sum(flexible.values())) - by_id[cid]["odds"]), 1)

    def test_missing_duplicate_rank_and_unreviewed_legacy_order_fail_closed(self):
        cases = []
        missing = source(); missing["990001"]["pool"]["1"].pop(0); cases.append(missing)
        duplicate = source(); duplicate["990001"]["pool"]["1"].append(duplicate["990001"]["pool"]["1"][0]); cases.append(duplicate)
        order = source(); order["990001"]["pool"]["1"][3:5] = reversed(order["990001"]["pool"]["1"][3:5]); cases.append(order)
        rates = source(); rates["990001"]["rankRates"]["normal"] = [160, 340, 500]; cases.append(rates)
        for data in cases:
            with self.assertRaises(ValueError):
                rules.revise_abyss(data)

    def test_installed_highlight_fix_changes_only_five_booleans(self):
        data = rules.revise_abyss(source())
        for entry in data['990001']['pool']['1'][:5]:
            entry['isRateUp'] = False
        before = deepcopy(data)
        result = rules.highlight_featured(data)
        self.assertEqual(before, data)
        self.assertEqual(result, rules.highlight_featured(result))
        for entry in result['990001']['pool']['1'][:5]:
            self.assertTrue(entry['isRateUp'])
            entry['isRateUp'] = False
        self.assertEqual(before, result)


if __name__ == "__main__":
    unittest.main()
