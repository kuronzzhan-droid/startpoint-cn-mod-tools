"""官方特殊/辅助双PF的行为、主体隔离与私有资源闭包。"""

from wf.paths import root_path
from copy import deepcopy
import os
from pathlib import Path
import sys
import unittest
import zlib

pass  # Imports resolve from this checkout/package, not external source copies.
import wf_dsl
import wf_nephtim_fever_powerflip as mod
from wf_enhancement_policy import OfficialBaseline
from wf_quest_lib import hashed_rel

APK = Path(os.environ.get("WF_APK", ('${WF_ROOT}/out/newchars-pf-v9-20260906/wf_newchars_pf_v9.apk'.replace("${WF_ROOT}", str(root_path())))))
CDN = Path(os.environ.get("WF_CDN_ROOT", ('${WF_ROOT}/startpoint-cn/.cdn/cn'.replace("${WF_ROOT}", str(root_path())))))


def decode(raw):
    return wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]


def nodes(tree, name):
    result = []
    if isinstance(tree, list):
        if tree and tree[0] == name:
            result.append(tree)
        for child in tree:
            result.extend(nodes(child, name))
    return result


def unprivate(value):
    if isinstance(value, str):
        return value.replace("battle/effect/powerflip/" + mod.PF_ID + "/",
                             "battle/effect/powerflip/", 1)
    if isinstance(value, list):
        return [unprivate(x) for x in value]
    if isinstance(value, dict):
        return {k: unprivate(v) for k, v in value.items()}
    return value


class NephtimPowerFlipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not APK.is_file() or not CDN.is_dir():
            raise unittest.SkipTest("official native PF bundle fixture unavailable")
        official = OfficialBaseline(CDN, write_cache=False)
        cls.loader = staticmethod(mod.with_bundle_fallback(
            lambda logical: official.get("common", hashed_rel(logical)), APK))

    def source(self, kind, level):
        return decode(self.loader(mod.source_path(kind, level)))

    def test_special_tree_preserved_at_every_level(self):
        for level in (1, 2, 3):
            source = self.source("special", level)
            result = unprivate(mod.build_power_flip(level, self.loader))
            self.assertEqual(result[:11], source[:11])
            self.assertEqual(result[11][1][:len(source[11][1])], source[11][1])
            self.assertEqual(len(nodes(result, "CollisionOfBallAndEnemy")), 1)
            self.assertEqual(nodes(result, "NotifyPowerflipEnd"), nodes(source, "NotifyPowerflipEnd"))

    def test_supporter_buffs_and_third_level_attack_preserved(self):
        for level in (1, 2, 3):
            source = self.source("supporter", level)
            result = unprivate(mod.build_power_flip(level, self.loader))
            self.assertEqual(nodes(result, "ACAttackPoint"), nodes(source, "ACAttackPoint"))
            self.assertEqual(nodes(result, "ACPiercing"), nodes(source, "ACPiercing"))
            self.assertEqual(nodes(result, "ACFlying"), nodes(source, "ACFlying"))
            attacks = nodes(result, "CreateNormalAttack")
            if level == 3:
                donor_attack = deepcopy(nodes(source, "CreateNormalAttack")[0])
                donor_attack[1] += 200
                # 作者 2026-09-27 第二批 Down：辅助型末段削韧 p13 1 → 0（Lv3 26 → 25），其余参数不动。
                self.assertEqual([{"min": 1, "max": 1}], donor_attack[13])
                donor_attack[13] = [{"min": 0, "max": 0}]
                self.assertEqual(attacks[-1], donor_attack)
                donor_area = nodes(result, "CreateHitArea")[-1]
                self.assertEqual(donor_area[9], ["Rectangle", [{"min": 1500, "max": 1500}],
                                               [{"min": 2000, "max": 2000}]])
                self.assertEqual(donor_area[13:15], [["SpecifyHitAreaLifetimeDirectly", 30],
                                                   ["CalculatedUsingMaxNumOfHits", 1]])
            else:
                self.assertEqual(len(attacks), 2)

    def test_toughness_per_level_lands_on_the_down_cap(self):
        # 作者 2026-09-27 第二批 Down 口径 B.2：强化弹射每级单目标削韧上限 15/20/25。
        def toughness(tree):
            total = 0
            for area in nodes(tree, "CreateHitArea"):
                attack, = nodes(area, "CreateNormalAttack")
                self.assertEqual("CalculatedUsingMaxNumOfHits", area[14][0])
                total += area[14][1] * attack[13][0]["max"]
            return total
        for level, cap in ((1, 15), (2, 20), (3, 25)):
            self.assertEqual(cap, toughness(mod.build_power_flip(level, self.loader)), level)
        self.assertEqual({"1": 15, "2": 20, "3": 25}, mod.metadata()["toughness_per_level"])
        # 原生辅助型 Lv3 末段是 1（改前 26）；原像不符时拒绝，不静默改别的值。
        donor = deepcopy(self.source("supporter", 3)[11])
        mod._supporter_payload(donor)
        drifted = deepcopy(donor)
        nodes(drifted, "CreateNormalAttack")[0][13] = [{"min": 2, "max": 2}]
        with self.assertRaisesRegex(ValueError, "toughness preimage drift"):
            mod._supporter_toughness(drifted, 3)
        untouched = deepcopy(donor)
        mod._supporter_toughness(untouched, 2)  # 只有 Lv3 有覆盖
        self.assertEqual(donor, untouched)

    def test_donor_subjects_do_not_overwrite_special_collision_bindings(self):
        for level in (1, 2, 3):
            result = mod.build_power_flip(level, self.loader)
            donor = result[11][1][4:]
            self.assertFalse(nodes(donor, "NotifyPowerflipEnd"))
            self.assertFalse(nodes(donor, "Wait"))
            for name, indexes in {"FindAllSubjects": (1,), "CreateCondition": (1,),
                                  "ShowEffect": (3,), "CreateNormalAttack": (1,),
                                  "CreateHitArea": (19, 21, 22)}.items():
                for command in nodes(donor, name):
                    for index in indexes:
                        self.assertGreaterEqual(command[index], 200)

    def test_private_assets_have_complete_effect_and_texture_dependencies(self):
        assets = mod.action_assets(self.loader)
        self.assertEqual(len(assets), 25)
        for level, path in enumerate(mod.PROGRAM_PATHS, 1):
            tree = decode(assets["common", path + mod.SUFFIX])
            self.assertEqual(tree, mod.build_power_flip(level, self.loader))
            for effect in nodes(tree, "SpecifyEffectDirectly"):
                for suffix in (".parts.amf3.deflate", ".timeline.amf3.deflate"):
                    self.assertIn(("common", effect[1] + suffix), assets)
        for (tier, logical), raw in assets.items():
            self.assertEqual(tier, "common")
            self.assertIn(mod.PF_ID, logical)
            if logical.endswith(mod.SUFFIX):
                continue
            source = unprivate(logical)
            if logical.endswith(".png"):
                self.assertEqual(raw, self.loader(source))
            else:
                self.assertEqual(unprivate(decode(raw)), decode(self.loader(source)))

    def test_official_source_drift_is_rejected(self):
        original = self.loader(mod.source_path("supporter", 3))
        def corrupt(path):
            return original + b"x" if path == mod.source_path("supporter", 3) else self.loader(path)
        with self.assertRaisesRegex(ValueError, "fingerprint mismatch"):
            mod.build_power_flip(3, corrupt)
        with self.assertRaises(ValueError):
            mod.build_power_flip(4, self.loader)

    def test_private_table_and_string_rows_connect_all_three_programs(self):
        self.assertEqual(mod.power_flip_rows(), {mod.PF_ID: [list(mod.PROGRAM_PATHS)]})
        self.assertTrue(mod.flat_string_rows()[mod.PF_STRING_ID][0][0])
        self.assertFalse(mod.metadata()["requires_new_apk"])
        self.assertEqual(len(mod.metadata()["native_source_sha256"]), 6)


if __name__ == "__main__":
    unittest.main()
