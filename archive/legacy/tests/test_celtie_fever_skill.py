"""真实官方供体上的十字几何、时序、来源边界与资产回归。"""

from wf.paths import root_path
import math
import hashlib
from copy import deepcopy
import os
import sys
import tempfile
import unittest
from pathlib import Path

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_celtie_fever_skill as skill
import wf_character_pack as pack
from wf_enhancement_policy import OfficialBaseline
from wf_mod_tool import sha1_path


def landing(tree):
    if tree[0] == "ActionDsl":
        tree = skill.nodes(tree, "FindNearSubjects")[0]
    event = skill.one(tree, "CollisionOfBallAndSpecificEnemy")
    return event[6], event[7]


def ungrown_tree(tree):
    """四个互斥路线的动作必须一致；移除本轮成长后复核旧演出哈希。

    2026-09-27 第三轮（c）：共鸣∧Fever 路线按技能旗号 2 复制一份（队长不封顶 / 10 层），3 → 4。
    """
    result = deepcopy(tree)
    routes = skill.nodes(result, "FindNearSubjects")
    assert len(routes) == 4 and routes[0] == routes[1] == routes[2] == routes[3]
    result[11][1][1] = ["Command", routes[0]]
    for attack in skill.nodes(result, "CreateNormalAttack"):
        assert len(attack[6][0].pop("vlv")) == 1
    return result


def point_damage(area, point):
    """独立转录原生NWay双臂及同组max1语义，检查几何而非只比配置。"""
    width, height = (v[0]["max"] for v in area[9][1:])
    count, spacing = area[12][1:]
    assert count == 2
    hits = 0
    for angle in (area[6] - spacing/2, area[6] + spacing/2):
        x = point[0]*math.cos(angle) + point[1]*math.sin(angle)
        y = -point[0]*math.sin(angle) + point[1]*math.cos(angle)
        if abs(x) <= width/2 and abs(y) <= height/2:
            hits += 1
    hits = min(hits, area[15][1][0]["max"])
    return hits * skill.one(area, "CreateNormalAttack")[6][0]["max"]


class CeltieSkillMetadataTests(unittest.TestCase):
    def test_uses_existing_native_client_and_exact_programs(self):
        self.assertEqual(len(skill.PROGRAM_PATHS), 2)
        self.assertTrue(all(p.endswith(f"wind_spgirl_campus_{lv}")
                            for p, lv in zip(skill.PROGRAM_PATHS, (1, 2))))
        self.assertEqual(skill.REQUIRED_CAPABILITIES, ())
        with self.assertRaises(ValueError):
            skill.build_skill(3, lambda _: self.fail("invalid level must not read assets"))


class CeltieOfficialSkillTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cdn = Path(os.environ.get("WF_CELTIE_OFFICIAL_CDN", ('${WF_ROOT}/startpoint-cn/.cdn/cn'.replace("${WF_ROOT}", str(root_path())))))
        if not (cdn / "archive-common-full").is_dir():
            raise unittest.SkipTest("official CN archive required; set WF_CELTIE_OFFICIAL_CDN")
        cls.baseline = OfficialBaseline(cdn, write_cache=False)
        cls.cache = {}
        # Frozen donor/geometry contract; boss tracking is verified separately.
        cls.trees = {lv: skill.build_skill(lv, cls.read, boss_target=False) for lv in (1, 2)}

    @classmethod
    def read(cls, logical):
        if logical not in cls.cache:
            digest = sha1_path(logical)
            data = cls.baseline.get("common", digest[:2] + "/" + digest[2:])
            if data is None:
                raise AssertionError("missing official asset: " + logical)
            cls.cache[logical] = data
        return cls.cache[logical]

    def test_native_validity_roundtrip_and_donor_bytes_unchanged(self):
        before = dict(self.cache)
        for lv, tree in self.trees.items():
            skill.validate(tree)
            self.assertEqual(skill.parse(skill.encode(tree)), tree)
            self.assertEqual(tree[10], 2)
            self.assertEqual(skill.build_skill(lv, self.read, boss_target=False), tree)
        self.assertEqual(before, self.cache)

    def test_only_bonus_selectors_and_authorized_multiplier_differ_from_frozen_cross_skill(self):
        # 还原选择器和本次授权的75倍后，须逐字节回到859088dd原动作，
        # 防止改动命中、状态、时序或任何演出参数。
        original_sha = "c29e81396fd4f30542a0d01ec36ca08513313ff23e78ae284bdc397a23a26dad"
        for tree in self.trees.values():
            normalized = ungrown_tree(tree)
            normalized[10] = 0
            areas = skill.nodes(normalized, "CreateHitArea")
            self.assertEqual(4, len(areas))
            for area in areas:
                self.assertEqual(2, area[24])
                area[24] = 0
            untouched = deepcopy(normalized)
            self.assertEqual(ungrown_tree(tree), skill.ability_damage_reference(normalized))
            self.assertEqual(untouched, normalized)
            for attack, multiplier in zip(skill.nodes(normalized, "CreateNormalAttack"), (25, 45, 25, 45)):
                attack[6] = skill.value(multiplier)
            self.assertEqual(original_sha, hashlib.sha256(skill.encode(normalized)).hexdigest())

    def test_dash_collision_and_timeout_have_same_safe_landing(self):
        tree = ungrown_tree(self.trees[2])
        self.assertEqual(skill.one(tree, "MoveBall"),
            ["MoveBall", -18, ["GH", 0], 0, 60, 40, ["KeepGoing"], True])
        event = skill.one(tree, "CollisionOfBallAndSpecificEnemy")
        self.assertEqual(event[1:4], [0, 60, 1])
        success, timeout = landing(tree)
        self.assertEqual(success, timeout)
        self.assertIsNot(success, timeout)
        self.assertEqual(skill.one(timeout, "StopBall")[1:4],
                         [-18, 87, ["RestoreToSpeedBeforeActionExecution"]])
        self.assertEqual(skill.one(timeout, "CreateReferencePoint")[1:6],
                         [-18, ["AB"], 0, 0, 0])
        for result in (success, timeout):
            waits = skill.nodes(result, "Wait")
            self.assertEqual([w[1] for w in waits], [27, 30])
            self.assertEqual({n[1] for n in skill.nodes(result, "RemoveEvent")},
                             {"花びらAリピート", "花びらBスタート", "花びらBリピート"})

    def test_cross_center_and_each_arm_total_seventy_five_outside_zero(self):
        for original in self.trees.values():
            tree = ungrown_tree(original)
            for branch in landing(tree):
                areas = skill.nodes(branch, "CreateHitArea")
                self.assertEqual(len(areas), 2)
                self.assertEqual([skill.one(a, "CreateNormalAttack")[6] for a in areas],
                                 [skill.value(25 * 75 / 70), skill.value(45 * 75 / 70)])
                for point, expected in (((0, 0), 75), ((1100, 0), 75),
                                        ((0, 1100), 75), ((1100, 1100), 0)):
                    self.assertEqual(sum(point_damage(a, point) for a in areas), expected)
                for a in areas:
                    self.assertEqual(a[1], "*")
                    self.assertEqual(a[24], 2)
                    self.assertEqual(a[13:16], [["SpecifyHitAreaLifetimeDirectly", 30],
                        ["CalculatedUsingMaxNumOfHits", 1], ["Some", skill.value(1)]])
                    attack = skill.one(a, "CreateNormalAttack")
                    self.assertEqual(attack[2], 4)
                    self.assertEqual(attack[5], 0)
                    self.assertEqual(attack[8:13], [False]*5)

    def test_a1_only_applies_buff_and_hit_enemy_resist(self):
        tree = self.trees[2]
        root_flag = tree[11][1][0][1]
        self.assertEqual(root_flag[0:2], ["ConditionalsChangeSkillFlag", 1])
        self.assertEqual(root_flag[3], skill.block())
        targets = skill.nodes(root_flag, "FindAllSubjects")
        self.assertEqual([(c[2], c[3]) for c in targets], [(97, []), (33, [4])])
        statuses = skill.nodes(root_flag, "CreateCondition")
        self.assertEqual([c[2][0] for c in statuses], [
            ["ACPiercing", skill.value(900)],
            ["ACAbilityDamage", skill.value(900), skill.value(1), skill.value(1)]])
        for area in skill.nodes(tree, "CreateHitArea"):
            flag = area[23][1][0][1]
            self.assertEqual(flag[0:2], ["ConditionalsChangeSkillFlag", 1])
            self.assertEqual(flag[3], skill.block())
            resist = skill.one(flag, "CreateCondition")
            self.assertEqual(resist[1], area[22])
            self.assertEqual(resist[2], [["ACToleranceOfElement", skill.value(900),
                                         4, skill.value(-.25), skill.value(1)]])
        self.assertFalse(skill.nodes(tree, "ACUnique"))
        self.assertFalse(skill.nodes(tree, "ACSpeedup"))
        self.assertFalse(any(n[2] == 49 for n in skill.nodes(tree, "FindAllSubjects")))

    def test_two_visual_angles_and_only_one_audio_timeline(self):
        for branch in landing(self.trees[2]):
            reference = skill.one(branch, "CreateReferencePoint")
            shows = skill.nodes(reference, "ShowEffect")
            self.assertEqual([s[9] for s in shows], [0, math.pi/2])
        assets = skill.effect_assets(self.read)
        self.assertEqual(len(assets), 18)
        horizontal = skill.parse(assets["common", skill.HORIZONTAL_EFFECT + ".timeline.amf3.deflate"])
        vertical_path = skill.HORIZONTAL_EFFECT.removesuffix("_horizontal")
        vertical = skill.parse(assets["common", vertical_path + ".timeline.amf3.deflate"])
        self.assertEqual(horizontal["sounds"], [])
        self.assertEqual(len(vertical["sounds"]), 3)
        self.assertEqual(horizontal["sequences"], vertical["sequences"])
        for donor, own in skill.EFFECT_RENAMES.items():
            old = f"battle/effect/skill_unique/{donor}/{donor}.png"
            new = f"battle/effect/skill_unique/{own}/{own}.png"
            self.assertEqual(assets["common", new], self.read(old))
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory)
            declared = []
            for (tier, logical), raw in assets.items():
                path = package / "roots" / tier / logical
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
                declared.append((tier, logical, path))
            self.assertEqual(pack._client_asset_shape_errors({}, package, declared), [])


if __name__ == "__main__":
    unittest.main()
