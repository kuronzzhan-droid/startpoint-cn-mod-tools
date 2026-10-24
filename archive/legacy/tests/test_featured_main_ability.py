"""五角色A1主位范围、桥接全行、红M与原压缩行保护。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
import zlib

pass  # Imports resolve from this checkout/package, not external source copies.
import wf_featured_main_ability as patch
import wf_mod_tool as core
import wf_bianca_dragon_abilities as bianca
import wf_bianca_dragon_bridge as bridge
import wf_celtie_fever_abilities as celtie
import wf_nephtim_fever_abilities as nephtim
import wf_scutum_abilities as scutum
import wf_campus_panel_text as campus_text
import wf_nephtim_fever_text as nephtim_text
from test_bianca_dragon_descriptions import description_sources
from test_celtie_fever_abilities import official_sources as celtie_source
from test_scutum_abilities import official_source as scutum_source


def native_kits():
    source, _ = description_sources()
    rows = bianca.ability_rows(source)
    rows["1199891"].extend(bridge.a1_enhancement_rows(source))
    return {"119989": rows, "149989": celtie.ability_rows(celtie_source()),
            "169989": nephtim.ability_rows(source), "149988": scutum.ability_rows(scutum_source())}


def table(rows):
    return core.build_orderedmap_raw_rows(core.OrderedMap("test", list(rows),
        [zlib.compress(core.write_csv_lines(value).encode("utf-8"), 1) for value in rows.values()], Path(".")))


def raw_rows(raw):
    data = core.read_orderedmap_raw_rows_from_bytes(raw)
    return data.keys, dict(zip(data.keys, data.rows))


class FeaturedMainAbilityTests(unittest.TestCase):
    def test_exact_five_ids_and_all_builder_a1_rows_including_bianca_bridge(self):
        self.assertEqual(set(patch.CODES), {"149990", "119989", "149989", "169989", "149988"})
        kits = native_kits()
        # 奈芙 A1 自 2026-09-27 起 4 行（I536 强化开关移入队长）。
        # 希尔媞 A1 自 2026-09-27 第三轮起 3 行：末尾 I704 仅队长开关（前置42），c1 与键一致。
        self.assertEqual([len(kits[cid][cid + "1"]) for cid in kits], [4, 3, 4, 5])
        for cid, abilities in kits.items():
            for slot, rows in abilities.items():
                self.assertEqual({r[1] for r in rows},
                                 {"false" if slot.endswith(("1", "3")) else "true"})
        # Dragon support must keep working independently of the main-only A1.
        source, _ = description_sources()
        support = bridge.support_damage_rows(source)[bridge.SUPPORT_ABILITY_ID]
        self.assertEqual({r[1] for r in support}, {"true"})
        # Scutum's enhancement is located in A6; this request must not restrict it.
        flag = [r for r in kits["149988"]["1499886"] if r[47] == "536"]
        self.assertEqual(len(flag), 1)
        self.assertEqual(flag[0][1], "true")

    def test_only_column_one_changes_and_transform_is_nonmutating(self):
        for cid, abilities in native_kits().items():
            source = deepcopy(abilities[cid + "1"])
            for row in source:
                row[1] = "true"
            original = deepcopy(source)
            result = patch.main_only_rows(cid, source)
            self.assertEqual(source, original)
            for before, after in zip(source, result):
                self.assertEqual([i for i in range(126) if before[i] != after[i]], [1])
            self.assertEqual(result, patch.main_only_rows(cid, result))

    def test_wrong_character_slot_shape_or_boolean_are_rejected(self):
        rows = native_kits()["119989"]["1199891"]
        for cid, bad in [("999999", rows), ("149989", rows), ("119989", []),
                         ("119989", [rows[0][:-1]])]:
            with self.assertRaises(ValueError):
                patch.main_only_rows(cid, bad)
        for column, value in [(0, "lady_summoner_campus_3"), (1, "0")]:
            bad = deepcopy(rows)
            bad[0][column] = value
            with self.assertRaises(ValueError):
                patch.main_only_rows("119989", bad)

    def test_native_main_icons_keep_every_character_of_the_original_description(self):
        text = "战斗开始时，自身技能槽＋50%\n\n风属性共鸣时，强化技能\n"
        marked = patch.main_description(text)
        self.assertEqual(marked.replace(patch.MAIN, ""), text)
        self.assertEqual(marked.count("<icon id='main'>"), 2)
        self.assertEqual(patch.main_description(marked), marked)
        for cid in ("119989", "149989"):
            panels = campus_text.panel_descriptions(cid)
            self.assertTrue(all(line.startswith(patch.MAIN) for line in panels["a1"].splitlines()))
            self.assertNotIn("<icon id='main'>", panels["a2"])
        self.assertTrue(all(line.startswith(patch.MAIN) for line in nephtim_text.panel_descriptions()["a1"].splitlines()))
        scutum_text = scutum.flat_string_rows()
        self.assertTrue(all(line.startswith(patch.MAIN) for line in scutum_text["desc_override_scutum_valentine_1"][0][0].splitlines()))

    def test_summer_patch_changes_exactly_one_ability_and_one_description_key(self):
        cid, code = "149990", patch.CODES["149990"]
        # Three differently conditioned original rows stand for summer's existing
        # gauge, enhancement, and holiday damage entries; values must be retained.
        sample = native_kits()["119989"]["1199891"][:3]
        own = deepcopy(sample)
        for row in own:
            row[0], row[1] = code + "_1", "true"
        other = deepcopy(own[0]); other[0] = code + "_3"
        ability = table({cid + "1": own, cid + "3": [other], "1199893": [["protected"]]})
        key = "desc_override_" + code + "_1"
        strings = table({key: [["技能槽＋50%\n风属性共鸣时，强化技能"]], "unrelated": [["原样"]]})
        result, meta = patch.patch_tables(cid, ability, strings)
        self.assertEqual(meta["row_count"], 3)
        self.assertEqual(set(result), {patch.ABILITY, patch.STRINGS})
        for logical, before, expected in [(patch.ABILITY, ability, cid + "1"), (patch.STRINGS, strings, key)]:
            oldkeys, old = raw_rows(before); newkeys, new = raw_rows(result[logical])
            self.assertEqual(oldkeys, newkeys)
            self.assertEqual({k for k in old if old[k] != new[k]}, {expected})
        twice, _ = patch.patch_tables(cid, result[patch.ABILITY], result[patch.STRINGS])
        self.assertEqual(twice, result)
        with self.assertRaisesRegex(ValueError, "existing ability/description"):
            patch.patch_tables(cid, ability, table({"wrong": [["missing"]]}))


if __name__ == "__main__":
    unittest.main()
