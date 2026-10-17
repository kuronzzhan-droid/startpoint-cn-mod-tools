# -*- coding: utf-8 -*-
"""Inaho V12 (package 1.0.9): the native Fever-growth contract, in the package itself.

V11 hid three ability/leader descriptions behind ``desc_override_*`` rows because the
counter was a hand-rolled ``S`` accumulator (I461 seed 4200 + two I629 DSLs + three
I213 per-stack rows) whose native panel text leaked ``每等级280`` / ``累计1000000000``.
V12 replaces that with the official primitives: the unique condition counts layers, a
leader DURING row (trigger 134 ``ConditionAccumulationCountUnique`` -> content 18
``FeverPoint``) scales the Fever rate per layer, and the panel needs no override.

This test pins the removal.  Deleting an assertion here must turn red -- it is the only
place that says the internal-counter machinery may not come back through a merge.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wf_dsl  # noqa: E402
import wf_mod_tool as core  # noqa: E402
from wf_client_description_legality import description_compatibility_problems  # noqa: E402
from wf_client_legality import (  # noqa: E402
    client_legality_problems, required_client_capabilities,
)

PACKAGE = Path(__file__).resolve().parents[2] / "work/character_packs/fox_oracle_autumn/package"
ABILITY = "master/ability/ability.orderedmap"
LEADER = "master/ability/leader_ability.orderedmap"
UNIQUE = "master/character/unique_condition.orderedmap"
STRINGS = "master/string/custom_ability_string.orderedmap"

STATE = "1399952"
LAYER_CAP = "99"   # 2026-09-09 作者:余辉无上限成长(99 = 客户端显示上限)
FEVER_RATIO_CAPABILITY = "kyubi-fever-ratio-v1"

# custom_ability_string keys the V12 build removed: two dead I629 描述键 plus the three
# V11 panel overrides.  They must be gone from the table *and* from the manifest claim --
# a key left in the claim is republished, a key left in the table is never deleted live.
REMOVED_STRING_KEYS = (
    "ability_fox_oracle_autumn_drain",
    "ability_fox_oracle_autumn_fever_growth",
    "desc_override_fox_oracle_autumn_1",
)
# 2026-09-09/10 回来的固定文案(队长技 + 词条6),内容由作者口径决定,这里只钉存在。
PRESENT_STRING_KEYS = (
    "desc_override_fox_oracle_autumn",
    "desc_override_fox_oracle_autumn_2",
    "desc_override_fox_oracle_autumn_6",
)
REMOVED_DSLS = (
    "battle/action/skill/action/ability_skill/"
    "ability_fox_oracle_autumn_drain$ability_fox_oracle_autumn_drain.action.dsl.amf3.deflate",
    "battle/action/skill/action/ability_skill/ability_fox_oracle_autumn_fever_growth$"
    "ability_fox_oracle_autumn_fever_growth.action.dsl.amf3.deflate",
)
SKILL_DSLS = {
    1: ("battle/action/skill/action/rare5/fox_oracle_autumn$"
        "fox_oracle_autumn_1.action.dsl.amf3.deflate", {"min": 35, "max": 35}),
    2: ("battle/action/skill/action/rare5/fox_oracle_autumn$"
        "fox_oracle_autumn_2.action.dsl.amf3.deflate", {"min": 45, "max": 50}),
}


#: 2026-09-27 平衡轮次回写候选时登记的 snapshot 键 → RevisionCandidate 写入的 package_version(由旧到新)。
PACKAGE_VERSIONS = {
    "revision_20260927": "0.20260927",      # 第一批 wf_balance_20260927_inaho
    "revision_20260927b": "0.20260927.1",   # 第二批 wf_balance_20260927b_inaho
    "revision_20260927c": "0.20260927.2",   # 第二批追加 wf_balance_20260927b_inaho2
    "revision_20260927d": "0.20260927.3",   # 第三轮 wf_balance_20260927c_inaho(extra5 stage_batch.SNAPSHOT)
}
BATCH2_SNAPSHOT, BATCH3_SNAPSHOT = "revision_20260927b", "revision_20260927d"
#: 余辉每层队长 #1(雷队 Fever 获得量)c111/c112:原 40%;第二批 ×1/5 = 8%;第三轮回调到 40% × 4/5 就近取 30%。
ORIGINAL_FEVER_GAIN, BATCH2_FEVER_GAIN, BATCH3_FEVER_GAIN = "40000", "8000", "30000"


def _records(logical: str, key: str) -> list[list[str]]:
    table = core.read_orderedmap_file_raw_rows(PACKAGE / "roots/common" / logical, logical)
    raw = table.rows[table.keys.index(key)]
    return core.read_csv_lines(zlib.decompress(raw).decode("utf-8"))


def _revision_rounds() -> tuple[bool, bool]:
    """(第二批已回写, 第三轮已回写)。第三轮按快照键或候选队长 #1 的值判定,任一成立即按第三轮核对
    (stage_batch 回写后二者同时成立;只认值是为了不依赖暂存脚本的快照键命名)。"""
    snapshot = json.loads((PACKAGE / "manifest.json").read_bytes()).get("snapshot", {})
    batch2 = BATCH2_SNAPSHOT in snapshot
    batch3 = batch2 and (BATCH3_SNAPSHOT in snapshot
                         or _records(LEADER, "139995")[1][111] == BATCH3_FEVER_GAIN)
    return batch2, batch3


class InahoV12PackageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (PACKAGE / "manifest.json").is_file():
            raise unittest.SkipTest("Inaho character package is unavailable")
        cls.manifest = json.loads((PACKAGE / "manifest.json").read_bytes())
        cls.strings = core.read_orderedmap_file(
            PACKAGE / "roots/common" / STRINGS, STRINGS
        ).text_rows()

    def test_unique_condition_counts_layers_not_a_raw_accumulator(self):
        row, = _records(UNIQUE, STATE)
        # c4 = UniqueConditionValues.max_accumulation (UniqueConditionValues.as:59);
        # "(None)" or 1 would make UniqueConditionLogic.get_maxAccumulation return 1 and
        # the DURING trigger 134 could never count past one layer.
        self.assertEqual(row[4], LAYER_CAP)
        self.assertEqual(row[1], "余辉")
        self.assertEqual((row[9], row[10]), ("false", "true"))  # cancelable / force_apply

    def test_ability_1_seeds_nothing_and_gains_one_layer_per_fever(self):
        rows = _records(ABILITY, "1399951")
        # 作者 09-27 追加(wf_balance_20260927b_inaho2)回写后:余辉 +1 行(原能力1 #3)逐格搬到能力3 末尾
        # (#8,c0/c1 跟能力3 整键仅主位),能力1 6 → 4 行;回写前仍是 6 行。
        moved = len(rows) == 4
        self.assertEqual(len(rows), 4 if moved else 6)
        seed = _records(ABILITY, "1399953")[8] if moved else rows[3]
        if moved:
            self.assertEqual((seed[0], seed[1]), ("fox_oracle_autumn_3", "false"))
            self.assertNotIn("461", [row[47] for row in rows])
        # trigger 8 Fever, content 461 ConditionUnique, initial_multiply 1:
        # +1 layer whenever Fever starts, and no battle-start seed at all.
        self.assertEqual((seed[27], seed[47], seed[68], seed[74]), ("8", "461", STATE, "1"))
        self.assertEqual((seed[51], seed[59]), ("100000", "100000"))
        self.assertNotIn("4200", seed)
        # No I629 program cell and no I213 per-stack row survive in this ability.
        for row in rows:
            self.assertNotEqual(row[47], "629")
            self.assertNotEqual(row[47], "213")
            self.assertEqual(row[70], "")
            self.assertEqual(row[71], "")

    def test_ability_1_fever_skill_ratio_and_ally_gauge_rows(self):
        rows = _records(ABILITY, "1399951")
        # 作者 09-27 追加(wf_balance_20260927b_inaho2)回写后:能力1 删原 #2/#3,drain/ally 前移到 #2/#3;
        # ally 整键取 live 5%(1.4.864 改的,回写前候选仍是 10%)并加 CT 5 秒(300 帧)。
        moved = len(rows) == 4
        drain, ally = rows[2:4] if moved else rows[4:6]
        # 1.1.1: Fever + own PowerFlip (trigger 2, every PF) -> 724 AddFeverPointRatio, -10% of cap.
        self.assertEqual((drain[6], drain[27], drain[28]), ("12", "2", "0"))
        self.assertEqual((drain[47], drain[51], drain[52]), ("724", "-10000", "-10000"))
        # Yellow resonance + Fever + own SkillInvoke -> 211 SkillGauge, ExceptMyself +10%.
        self.assertEqual((ally[6], ally[9], ally[11], ally[13]), ("2", "600000", "Yellow", "12"))
        self.assertEqual((ally[27], ally[28]), ("23", "0"))
        self.assertEqual((ally[47], ally[48], ally[51], ally[52]),
                         ("211", "1") + (("5000", "5000") if moved else ("10000", "10000")))
        self.assertEqual(ally[35], "300" if moved else "0")

    def test_ability_6_has_no_skill_fever_gain_row(self):
        # 1.1.0 (author, 2026-09-07): "去掉雷属性角色放技能获得fever的词条" -- the 213
        # Fever+350-on-skill record is gone; the Fever PF-damage during row stays, and
        # 2026-09-10 added the leader-gated 「余辉≥10 且非Fever,PF 时 FEVER 槽+15%」(724) row.
        rows = _records(ABILITY, "1399956")
        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertNotEqual(row[47], "213")
        self.assertNotIn(STATE, rows[0])
        gate = rows[1]
        self.assertEqual((gate[6], gate[13], gate[14], gate[16], gate[19], gate[20]),
                         ("186", "144", "0", "1000000", STATE, "42"))
        self.assertEqual((gate[27], gate[47], gate[51], gate[52]), ("2", "724", "15000", "15000"))

    def test_leader_scales_the_fever_rate_per_layer_and_keeps_the_i722_slot(self):
        rows = _records(LEADER, "139995")
        # 2026-09-27 第二批(wf_balance_20260927b_inaho)回写后:整键取 live 11 行(1.4.864 删了原行1
        # 「雷队员放技能→雷队技能槽4%」),余辉每层行 ×1/5(Fever 获得量 40%→8%)。回写前仍是旧候选 12 行。
        # 第三轮(wf_balance_20260927c_inaho)回写后:行数、行位不变,余辉每层 5 行回调(Fever 获得量 8%→30%)。
        batch2, batch3 = _revision_rounds()
        shift = 1 if batch2 else 0
        fever_gain = (BATCH3_FEVER_GAIN if batch3 else BATCH2_FEVER_GAIN if batch2
                      else ORIGINAL_FEVER_GAIN)
        self.assertEqual(len(rows), 12 - shift)   # 2026-09-09 +during 413 每层;2026-09-10 +Fever→461 余辉+1
        growth = rows[2 - shift]
        self.assertEqual(growth[3], "1")                       # During
        self.assertEqual(growth[83], "(None)")                 # accumulation trigger
        self.assertEqual((growth[95], growth[96]), ("134", "0"))
        self.assertEqual((growth[98], growth[99]), ("100000", "100000"))
        self.assertEqual((growth[100], growth[102]), ("(None)", STATE))   # 层数不封顶
        # 2026-09-10: target 自身→雷属性全队(引擎乘区只放大攻击者本人的 Fever 点),两列拉平 40%
        self.assertEqual((growth[106], growth[107], growth[108], growth[109]), ("false", "18", "5", "Yellow"))
        self.assertEqual((growth[111], growth[112]), (fever_gain, fever_gain))
        # wf_dual_pf_contract.bind_native_programs pins the I722 override to row index 8
        # (live 自 1.4.864 起在 index 7;第二批回写后候选同 live,契约待同步)。
        self.assertEqual(rows[8 - shift][45], "722")
        self.assertEqual(rows[8 - shift][80], "override_fox_oracle_autumn_dual_pf")
        # The 213 rows that produced 每等级280 / 余辉等级在0以下 are gone.
        for row in rows:
            self.assertNotEqual(row[45], "213")
            self.assertNotIn(row[11], ("187", "199"))

    def test_every_row_is_client_legal_and_only_724_needs_the_patch(self):
        gated = []
        for key, alias in ((f"13999{index}", "ability") for index in range(51, 57)):
            for index, row in enumerate(_records(ABILITY, key)):
                self.assertEqual(client_legality_problems(alias, row), [], f"{key}#{index}")
                self.assertEqual(description_compatibility_problems(alias, row), [])
                gated += [(f"{key}#{index}", cap)
                          for cap in required_client_capabilities(alias, row)]
        for index, row in enumerate(_records(LEADER, "139995")):
            self.assertEqual(client_legality_problems("leader_ability", row), [], index)
            self.assertEqual(description_compatibility_problems("leader_ability", row), [])
            gated += [(f"139995#{index}", cap)
                      for cap in required_client_capabilities("leader_ability", row)]
        # 作者 09-27 追加(wf_balance_20260927b_inaho2)回写后:能力1 删原 #2/#3,724 行由 #4 前移到 #2。
        drain_index = 2 if len(_records(ABILITY, "1399951")) == 4 else 4
        self.assertEqual(gated, [(f"1399951#{drain_index}", FEVER_RATIO_CAPABILITY),
                                 ("1399956#1", FEVER_RATIO_CAPABILITY)])

    def test_skill_dsls_are_plain_add_fever_point_again(self):
        for level, (logical, points) in SKILL_DSLS.items():
            with self.subTest(level=level):
                raw = (PACKAGE / "roots/common" / logical).read_bytes()
                tree = wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]
                # 2026-09-10: AddFeverPoint 只在非 Fever 执行(ConditionalsFeverMode 第一分支=Fever中)。
                self.assertEqual(tree[11][1][3],
                                 ["Command", ["ConditionalsFeverMode", ["Block", []],
                                              ["Block", [["Command", ["AddFeverPoint", [points]]]]]]])
                self.assertNotIn(STATE, json.dumps(tree))

    def test_dead_strings_and_dsls_left_the_package_and_the_manifest(self):
        # V12 = 1.1.1;2026-09-27 起每轮平衡修订(RevisionCandidate)把版本换成该轮的日期式版本并登记快照键。
        batch2, batch3 = _revision_rounds()
        snapshot = self.manifest.get("snapshot", {})
        dated = [version for key, version in PACKAGE_VERSIONS.items()
                 if key in snapshot or (batch3 and key == BATCH3_SNAPSHOT)]
        self.assertEqual(self.manifest["package_version"], dated[-1] if dated else "1.1.1")
        # V9 (kyubi-pf-damage) was dropped on 2026-09-07: the FFDec whole-class
        # recompile crashed evalCommand (F1069) and the author no longer wants
        # skills classified as PF damage.
        self.assertNotIn("kyubi-pf-damage-v1", self.manifest["required_capabilities"])
        claim, = [t for t in self.manifest["tables"] if t["logical_path"] == STRINGS]
        root_paths = {entry["logical_path"] for entry in self.manifest["roots"]["common"]}
        for key in REMOVED_STRING_KEYS:
            with self.subTest(key=key):
                self.assertNotIn(key, self.strings)
                self.assertNotIn(key, claim["outer_keys"])
        for key in PRESENT_STRING_KEYS:
            with self.subTest(key=key):
                self.assertIn(key, self.strings)
        claimed = {
            "ability_skill_fox_oracle_autumn_fever_pf",
            "override_string_fox_oracle_autumn_dual_pf",
            # 1.1.1: V11 panel override for ability 2 (「Fever模式中，无法获得Fever」).
            "desc_override_fox_oracle_autumn_2",
        }
        if batch2:   # 第二批 stage_batch.Plan.splice 认领队长面板(claim 按键排序)
            claimed.add("desc_override_fox_oracle_autumn")
        if batch3:   # 第三轮认领能力6 面板(共鸣冒号换行 → 一行)
            claimed.add("desc_override_fox_oracle_autumn_6")
        self.assertEqual(sorted(claim["outer_keys"]), sorted(claimed))
        for logical in REMOVED_DSLS:
            with self.subTest(logical=logical):
                self.assertNotIn(logical, root_paths)
                self.assertFalse((PACKAGE / "roots/common" / logical).exists())


if __name__ == "__main__":
    unittest.main()
