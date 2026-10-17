"""从完整装配捕获原生描述依赖，防止角色详情缺字符串键而报 C8601。"""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

pass  # Imports resolve from this checkout/package, not external source copies.
from test_bianca_dragon_abilities import official_sources
import wf_bianca_dragon as build
import wf_mod_tool as core

ABILITY = "master/ability/ability.orderedmap"
LEADER = "master/ability/leader_ability.orderedmap"
FLAT = "master/string/custom_ability_string.orderedmap"
CUSTOM_CONTENTS = {"536", "629", "704", "705", "706", "707", "708"}


def description_sources():
    """补齐真实官方桥接 donor；所有能力及字符串生成器保持真实执行。"""
    ability, leader = official_sources()
    ability["1110211"].append(
        "lady_summoner_xm20_1,true,action_skill,0,,0,0,,,,,,,0,,,,,,,0,,,,,,,23,0,,100000,100000,,,(None),0,,,,(None),,,,,,,0,0,2,,,15000,30000,,,,,120000000,120000000,100000,100000,(None),(None),(None),(None),(None),,0,,,,,false,,1,0,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,".split(","))
    ability["1111773"] = [[],
        "wirfled_playable_3,false,attack_red,0,,0,2,,,600000,600000,Red,,0,,,,,,,0,,,,,,,0,,,,,,,,,,,,(None),,,,,,,0,536,,,,,,,,,,,,,,,,,,,,,,,change_skill_wirfled_playable,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,".split(",")]
    ability["1310202"] = [
        "rec_android_1anv_2,false,attack_yellow,0,,0,0,,,,,,,0,,,,,,,0,,,,,,,23,7,Yellow,100000,100000,,,(None),900,,,,(None),,,,,,,0,253,0,,,1500000,3000000,,,,,,,,,,,,,,,,,(None),,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,".split(",")]
    return ability, leader


class CapturedCandidate:
    """替代磁盘边界，捕获 assemble 真正交给 splice 的数据。"""
    def __init__(self):
        self.tables = {}
        self.manifest = {"snapshot": {"campus_bianca": {}}, "skills": {}}
        self.source, self.leaders = description_sources()

    def official_rows(self, logical):
        if logical == ABILITY:
            return copy.deepcopy(self.source)
        if logical == LEADER:
            return copy.deepcopy(self.leaders)
        # 本测试不渲染协力球，但真实的表装配仍需要 donor 容器。
        if logical.endswith("/multiball.orderedmap"):
            return {"1111711": [[""] * 28]}
        if logical.endswith("/multiball_level.orderedmap"):
            return {"1111711": [["curve", "304", "1", "curve", "455", "1"]]}
        raise AssertionError(f"unexpected official table: {logical}")

    def splice(self, logical, replacements, *, codec="flat"):
        self.tables.setdefault(logical, {}).update(copy.deepcopy(replacements))

    def read(self, tier, logical):
        if logical == "master/skill/action_skill.orderedmap":
            raw = core.encode_action_skill_row([("1", [""] * 8), ("2", [""] * 8)])
            return core.build_orderedmap_raw_rows(core.OrderedMap(
                logical_path=logical, source_path=Path("<memory>"),
                keys=[build.CODE], rows=[raw]))
        if logical == "master/character/character_text.orderedmap":
            return build.nested_blob(logical, {build.CID: [[""] * 8]})
        raise AssertionError(f"unexpected candidate read: {tier}:{logical}")

    def official(self, logical):
        return b"icon fixture"

    def emit(self, tier, logical, raw):
        pass

    def server_character_row(self, logical, value):
        pass

    def finish(self, metadata, *, apply=False):
        if apply:
            raise AssertionError("description regression must never write a package")
        return self.tables


class BiancaDragonDescriptionsTest(unittest.TestCase):
    def test_assembled_ability_and_leader_custom_descriptions_resolve_flat_rows(self):
        candidate = CapturedCandidate()
        with patch.object(build, "Candidate", return_value=candidate), \
                patch.object(build.pixels, "build_dragon_assets", return_value=({}, {})), \
                patch.object(build.skill, "build_effect_assets", return_value={}):
            tables = build.assemble(Path("unused-repo"), Path("unused-candidate"))

        # 原生 ChangeSkillFlag 和 InvokeSkill 都先读平表。嵌套 power_up 的同名键
        # 不能充当兜底；只检查生成器返回值会漏掉 assemble 忘记合入它的回归。
        flat = tables.get(FLAT, {})
        references = []
        for logical, content_column, string_column in ((ABILITY, 47, 70), (LEADER, 45, 68)):
            for key, rows in tables[logical].items():
                for index, row in enumerate(rows):
                    if row[content_column] in CUSTOM_CONTENTS:
                        references.append((logical, key, index, row[string_column]))
        self.assertEqual({"change_skill_lady_summoner_campus_dragon",
                          "lady_summoner_campus_fever_tick"}, {r[3] for r in references})
        for logical, key, index, string_id in references:
            with self.subTest(table=logical, key=key, row=index, string_id=string_id):
                self.assertIn(string_id, flat, f"C8601: flat custom ability string missing: {string_id}")
                self.assertTrue(flat[string_id] and flat[string_id][0]
                                and flat[string_id][0][0].strip(),
                                f"empty native CustomAbilityStringValues.string: {string_id}")


if __name__ == "__main__":
    unittest.main()
