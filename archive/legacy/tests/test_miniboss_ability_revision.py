"""真实列位的特色机制、隐藏乘区和两表最小维护边界。"""
from copy import deepcopy
from fractions import Fraction
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zlib

pass  # Imports resolve from this checkout/package, not external source copies.
import wf_dsl
import wf_mod_tool as core
import wf_miniboss_ability_revision as revision
from wf_miniboss_budget import audit, row_peak
from wf_miniboss_kits import build_abilities
from wf_miniboss_roster import ROSTER
from wf_miniboss_rows import make, ongoing
from wf_miniboss_text import ability_panel_rows, MAIN


def ordered(rows):
    return core.build_orderedmap_raw_rows(core.OrderedMap("test", list(rows),
        [zlib.compress(core.write_csv_lines(v).encode(), 1) for v in rows.values()], Path(".")))


def raw_rows(raw):
    value = core.read_orderedmap_raw_rows_from_bytes(raw)
    return dict(zip(value.keys, value.rows))


def helper_bytes(tree):
    compressor = zlib.compressobj(wbits=-15)
    return compressor.compress(wf_dsl.encode_amf3(tree)) + compressor.flush()


class MinibossMechanicsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kits = {c.cid: build_abilities(c.cid)[0] for c in ROSTER}

    def row(self, cid, slot, index):
        return self.kits[cid][cid + str(slot)][index]

    def test_blue_buff_acquisition_charges_only_actual_holder_with_own_cooldown(self):
        row = self.row("129994", 2, 1)
        self.assertEqual(row[27:30], ["30", "5", "Blue"])
        self.assertEqual((row[48], row[51:53], row[35]), ("7", ["5000", "5000"], "900"))
        # Native setupConditionForEachMember creates one handler per matching member.
        # Three simultaneous buffs on A give one refill; B has its own cooldown.
        cooldown, gauge = {}, {"A": 0, "B": 0, "red": 0}
        for frame, actor, element in [(0, "A", "Blue")] * 3 + [
                (0, "B", "Blue"), (0, "red", "Red"), (899, "A", "Blue"), (900, "A", "Blue")]:
            if element != row[29] or frame < cooldown.get(actor, -1):
                continue
            cooldown[actor] = frame + int(row[35])
            gauge[actor] += Fraction(int(row[51]), 1000)
        self.assertEqual(gauge, {"A": 10, "B": 5, "red": 0})
        for buff in self.kits["129994"]["1299943"]:
            self.assertEqual((buff[97], buff[98], buff[99], buff[102], buff[110]),
                             ("38", "5", "Blue", "6", "7"))

    def test_split_attacks_have_no_hidden_independent_damage(self):
        for cid, slot, index, count in [("129996", 3, 2, 3), ("119994", 3, 0, 3),
                                       ("149992", 3, 2, 2)]:
            row = self.row(cid, slot, index)
            self.assertEqual(int(row[47]), 201 if count == 2 else 202)
            self.assertEqual(row[51:53], ["0", "0"])
            # NormalAttackCalculator: (1 + additionalDamage + separatedDirect) / count.
            per_hit = Fraction(1 + Fraction(int(row[51]), 100000), count)
            self.assertEqual(count * per_hit, 1)
            self.assertEqual(row_peak(row), (0, False))
        bear = self.row("149991", 4, 0)
        self.assertEqual((bear[97], bear[100:103], bear[109], bear[113:115]),
                         ("134", ["700000", "700000", "1"], "45", ["0", "0"]))
        for layer in range(8):
            active = min(layer // 7, 1)
            self.assertEqual(2 if active else 1, 2 if layer == 7 else 1)
        armor = self.row("149992", 2, 0)
        self.assertEqual(armor[113:115], ["18500", "18500"])
        self.assertEqual(float(row_peak(armor)[0]), 185)

    def test_positive_split_damage_is_the_same_independent_bucket_and_rejected(self):
        rows = deepcopy(self.kits["149992"]["1499923"])
        rows[2][51:53] = ["35000", "35000"]
        with self.assertRaisesRegex(ValueError, "only one independent"):
            audit({3: rows})
        for instant_kind in (201, 202, 696):
            with self.assertRaisesRegex(ValueError, "only one independent"):
                audit({1: [make(instant_kind, 16)]})

    def test_heal_and_damage_responses_cannot_immediately_recurse(self):
        healed = []
        for kit in self.kits.values():
            for rows in kit.values():
                for row in rows:
                    if row[5] != "0":
                        continue
                    if row[27] == "19":
                        healed.append(row)
                        self.assertEqual((row[28], row[47], row[48]), ("0", "211", "0"))
                        self.assertGreater(int(row[35]), 0)
                    if row[47] == "206":
                        self.assertNotIn(row[27], ["19", "30", "185"])
                        if row[27] in ("21", "23"):
                            self.assertEqual(row[28], "0")
                            self.assertGreater(int(row[35]), 0)
                        if row[27] == "4":
                            self.assertEqual(row[28], "")  # native squad Dash has no member selector
                            self.assertGreater(int(row[35]), 0)
        self.assertEqual(len(healed), 1)
        counter = self.row("129995", 3, 0)
        self.assertEqual((counter[27], counter[28], counter[30:32], counter[35]),
                         ("21", "0", ["500000", "500000"], "300"))
        self.assertEqual((counter[47], counter[48], counter[51:53], counter[69]),
                         ("252", "0", ["800000", "800000"], "(None)"))

    def test_enemy_trigger_is_not_misused_with_global_stats(self):
        for kind in (0, 2, 4, 411):
            with self.assertRaisesRegex(ValueError, "target-aware"):
                audit({3: [make(kind, 15, during=ongoing(136, limit=1))]})
        whale = self.kits["129993"]
        self.assertEqual([r[47] for r in whale["1299933"]], ["538", "694", "226", "461"])
        self.assertEqual(whale["1299934"][0][47], "288")

    def test_each_role_has_six_native_panels_and_only_main_slot_three(self):
        for char in ROSTER:
            kit = self.kits[char.cid]
            panels = ability_panel_rows(char.cid, kit)
            self.assertEqual(len(panels), 6)
            self.assertEqual(sum(MAIN in rows[0][0] for rows in panels.values()), 1)
            for slot in range(1, 7):
                self.assertTrue(all(row[1] == ("false" if slot == 3 else "true")
                                    for row in kit[char.cid + str(slot)]))
            self.assertNotIn("desc_override_" + char.code, panels)

    def test_green_collision_counts_owner_instead_of_all_party_members(self):
        kit = self.kits["149993"]
        panels = ability_panel_rows("149993", kit)
        for slot in (2, 5):
            text = panels[f"desc_override_haniwa_green_playable_{slot}"][0][0]
            self.assertIn("自身与敌人每碰撞", text)
            self.assertNotIn("队伍与敌人", text)
            for row in kit["149993" + str(slot)]:
                if row[27] == "197":
                    self.assertEqual(row[28], "0")


class MinibossRevisionTests(unittest.TestCase):
    def fixture(self, root):
        store = root / "store"
        (root / "mod-tools").mkdir()
        (root / "mod-tools/profiles.json").write_text(json.dumps({"profiles": {"cn": {"store": "store"}}}))
        abilities, strings, uniques = {"foreign": [["protected, quoted", "rows"]]}, {"foreign": [["text"]]}, {}
        def put(logical, raw):
            path = core.table_path(store, logical)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        for char in ROSTER:
            kit, _ = build_abilities(char.cid)
            for key in kit:
                abilities[key] = [["old"]]
            for key in ability_panel_rows(char.cid, kit):
                strings[key] = [["旧能力"]]
            uniques[str(char.uid)] = [[char.code, "状态", "icon", "900", str(char.layers),
                                     "(None)", "(None)", "(None)", "(None)", "false",
                                     "false", "0", "0", "false", "(None)"]]
            for rows in kit.values():
                for row in rows:
                    if row[5] == "0" and row[47] == "629":
                        put(row[71] + ".action.dsl.amf3.deflate", helper_bytes(["Block", []]))
        for logical in revision.PROTECTED:
            put(logical, ordered(uniques) if logical == revision.UNIQUE else b"protected bytes")
        put(revision.ABILITY, ordered(abilities))
        put(revision.STRINGS, ordered(strings))
        return store

    def test_two_tables_ninety_each_preserve_all_foreign_compressed_rows_and_live(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = self.fixture(root)
            before = {p: p.read_bytes() for p in store.rglob("*") if p.is_file()}
            result = revision.plan(root, root / "work/codex_out/candidate")
            self.assertEqual(set(result.files), {("common", revision.ABILITY), ("common", revision.STRINGS)})
            for entry in result.report["tables"]:
                self.assertEqual(len(entry["authorized_keys"]), 90)
                self.assertEqual(len(entry["changed_keys"]), 90)
                logical = entry["logical_path"]
                self.assertEqual(raw_rows(result.files["common", logical])["foreign"],
                                 raw_rows(before[core.table_path(store, logical)])["foreign"])
            result.write()
            self.assertTrue(all(p.read_bytes() == raw for p, raw in before.items()))
            self.assertEqual(len(list((result.output / "roots").rglob("*.orderedmap"))), 2)
            with self.assertRaisesRegex(ValueError, "already exists"):
                result.write()

    def test_missing_keys_unique_drift_and_hidden_helper_buffs_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "missing installed"):
            revision.replace_existing(ordered({"other": [["keep"]]}), {"new": [["no"]]})
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = self.fixture(root)
            uid_path = core.table_path(store, revision.UNIQUE)
            old = uid_path.read_bytes()
            unique = core.read_orderedmap_file_from_bytes(old)
            rows = {k: core.read_csv_lines(v) for k, v in unique.items()}
            rows["1299980"][0][4] = "99"
            uid_path.write_bytes(ordered(rows))
            with self.assertRaisesRegex(ValueError, "unique accumulation drift"):
                revision.plan(root, root / "work/codex_out/candidate")
            uid_path.write_bytes(old)
            helper = build_abilities("129998")[0]["1299983"][0][71]
            core.table_path(store, helper + ".action.dsl.amf3.deflate").write_bytes(
                helper_bytes(["Block", [["ACAttackPoint", 100000]]]))
            with self.assertRaisesRegex(ValueError, "unbudgeted helper"):
                revision.plan(root, root / "work/codex_out/candidate")


if __name__ == "__main__":
    unittest.main()
