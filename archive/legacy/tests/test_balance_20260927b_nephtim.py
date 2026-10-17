"""校园奈芙提姆 2026-09-27 第二批：能力3 贯穿成长封顶 + 无上限部分搬队长、队长 Fever 获得量放缓、PF Lv3 削韧 26→25。"""

from wf.paths import root_path
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
import unittest
import zlib

pass  # Imports resolve from this checkout/package, not external source copies.

from test_bianca_dragon_abilities import official_sources
import wf_balance_20260927b_nephtim as B
import wf_client_legality as legality
import wf_describe
import wf_dsl
import wf_midautumn_kitlib as kitlib
import wf_mod_tool as core
import wf_nephtim_fever_abilities as abilities
import wf_nephtim_fever_leader as leader
import wf_nephtim_fever_powerflip as powerflip
import wf_nephtim_fever_text as text
from wf_character_revision import encode_tree

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).parent / "fixtures/balance_20260927b_nephtim.json"
MAIN = " <icon id='main'>  "
LEADER_KEY, A3_KEY = "169989", "1699893"
APK = Path(os.environ.get("WF_APK", ('${WF_ROOT}/out/newchars-pf-v9-20260906/wf_newchars_pf_v9.apk'.replace("${WF_ROOT}", str(root_path())))))
CDN = ROOT / ".cdn/cn"

PROPOSED = {
    "desc_override_ruin_girl_campus": (
        "暗属性共鸣时，强化弹射变为特殊型与辅助型组合。\n"
        "暗属性共鸣时，强化『午后星轨·甜蜜续杯』：额外赋予暗属性角色及协力球攻击力提升效果。\n"
        "暗属性共鸣时，Fever 模式中，强化后的技能发动时，自身获得或刷新「星夜茶会」，并赋予暗属性角色及协力球护盾。\n"
        "暗属性共鸣时，暗属性角色攻击力+200%、直接攻击伤害+400%。\n"
        "暗属性共鸣时，每达成35连击，暗属性角色获得的 Fever 槽上升量+2%。\n"
        "暗属性共鸣时，Fever 时间+100%。\n"
        "暗属性共鸣时，每有1个协力球消失时，暗属性角色技能槽+5%。\n"
        "暗属性共鸣时，每有1个协力球存在，自身直击判定次数+1。\n"
        "暗属性共鸣时，Fever 模式中，处于贯穿效果的时间每累计2秒，暗属性角色攻击力+1%、直接攻击伤害+1%。"),
    "desc_override_ruin_girl_campus_3": (
        MAIN + "暗属性共鸣时，Fever 模式中，当前每有1连击，暗属性角色直接攻击造成的伤害+2.5%（独立乘区）、攻击力+2.5%。\n"
        + MAIN + "暗属性共鸣时，Fever 模式中，处于贯穿效果的时间每累计2秒，暗属性角色攻击力+5%、直接攻击伤害+10%（最多10次）。\n"
        + MAIN + "暗属性共鸣时，暗属性角色合计每直接攻击45次，Fever 槽+15%。\n"
        + MAIN + "暗属性共鸣时，每有1个协力球存在时，全队及协力球对敌人造成的直接攻击伤害+25%（独立乘区）。"),
}


def nonempty(row):
    return {i: v for i, v in enumerate(row) if v != ""}


def changed(before, after):
    return [i for i in range(len(before)) if before[i] != after[i]]


def attacks(tree):
    return list(wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack"))


class NephtimBalance20260927bTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = json.loads(FIXTURE.read_bytes())
        cls.data = {(r["kind"], tuple(r["key"]) if isinstance(r["key"], list) else r["key"]): r["value"]
                    for r in fixture["reads"]}
        cls.result = B.revise(cls.read_from(cls.data))

    @staticmethod
    def read_from(data):
        return lambda kind, key: data[kind, key]

    def live(self, kind, key):
        return deepcopy(self.data[kind, key])

    # ------------------------------------------------------------------ 基线

    def test_fixture_is_the_reviewed_before_baseline(self):
        self.assertEqual(set(B.BEFORE), set(self.data))
        for item, expected in B.BEFORE.items():
            self.assertEqual(expected, B.digest(self.data[item]), item)

    # ------------------------------------------------------------------ 能力3

    def test_ability3_caps_the_piercing_growth_in_place(self):
        old = self.live("ability", A3_KEY)
        rows = self.result["ability"][A3_KEY]
        self.assertEqual(6, len(rows))
        self.assertEqual({"false"}, {r[1] for r in rows})  # 整键仍主位限制
        attack, direct = rows[2:4]
        # 改前：T235 → 暗队攻击力/直击 各 +10%，限次 (None)。
        for before, content in zip(old[2:4], ("32", "33")):
            self.assertEqual(("235", "12000000", "(None)", "0", content, "10000", "10000"),
                             (before[27], before[32], before[34], before[35], before[47], before[51], before[52]))
        # 改后：攻击力 +5%、直击 +10%，各最多 10 次；其余格不动。
        self.assertEqual(("10", "5000", "5000"), (attack[34], attack[51], attack[52]))
        self.assertEqual(("10", "10000", "10000"), (direct[34], direct[51], direct[52]))
        self.assertEqual([34, 51, 52], changed(old[2], attack))
        self.assertEqual([34], changed(old[3], direct))
        self.assertEqual([old[i] for i in (0, 1, 4, 5)], [rows[i] for i in (0, 1, 4, 5)])
        self.assertEqual(["暗·编成≥6 且 Fever 时: 状态KeepFrame贯通≥1(限10次) → 赋予全队(暗) 攻击力 5%",
                          "暗·编成≥6 且 Fever 时: 状态KeepFrame贯通≥1(限10次) → 赋予全队(暗) Direct伤害 10%"],
                         wf_describe.describe_rows(rows[2:4], "ability"))

    # ------------------------------------------------------------------ 队长

    def test_leader_appends_two_slowed_piercing_rows_built_by_the_move_formula(self):
        old = self.live("leader", LEADER_KEY)
        a3 = self.live("ability", A3_KEY)
        rows = self.result["leader"][LEADER_KEY]
        self.assertEqual(10, len(rows))
        self.assertEqual(["722", "536", "33", "32", "50", "56", "211", "629", "32", "33"], [r[45] for r in rows])
        for moved, source in zip(rows[8:], a3[2:4]):
            formula = ["ruin_girl_campus", "0", ""] + source[5:]
            self.assertEqual(124, len(moved))
            self.assertEqual([49, 50], changed(formula, moved))  # 只改强度
            self.assertEqual(["10000", "10000"], formula[49:51])
            self.assertEqual(["1000", "1000"], moved[49:51])      # 1/10
            self.assertEqual(("(None)", "0"), (moved[32], moved[33]))  # 不限次、无 CT
            self.assertEqual(("235", "100000", "12000000"), (moved[25], moved[28], moved[30]))
            self.assertEqual(("2", "Black", "12", "0"), (moved[4], moved[9], moved[11], moved[18]))
        self.assertEqual(sorted(nonempty(rows[8])), sorted(nonempty(rows[9])))
        # 口径 A.3：队长原本没有同触发（T235）行 → 新起两行，不合并。
        self.assertNotIn("235", [r[25] for r in old])

    def test_leader_fever_gain_growth_is_slowed_in_place_and_other_rows_are_verbatim(self):
        old = self.live("leader", LEADER_KEY)
        rows = self.result["leader"][LEADER_KEY]
        growth = rows[4]
        self.assertEqual(("12", "3500000", "(None)", "50", "5", "20000", "20000"),
                         (old[4][25], old[4][28], old[4][32], old[4][45], old[4][46], old[4][49], old[4][50]))
        self.assertEqual(["2000", "2000"], growth[49:51])
        self.assertEqual([49, 50], changed(old[4], growth))
        self.assertEqual([old[i] for i in (0, 1, 2, 3, 5, 6, 7)], [rows[i] for i in (0, 1, 2, 3, 5, 6, 7)])
        self.assertEqual(B.NEW_FEVER_GAIN * 10, B.OLD_FEVER_GAIN)
        self.assertEqual(B.LEADER_PIERCING_STRENGTH * 10, B.OLD_PIERCING_STRENGTH)

    def test_leader_precedents_for_trigger_235_and_fever_precondition_exist_in_live(self):
        store = Path(core.resolve_active_store()) if hasattr(core, "resolve_active_store") else None
        path = core.table_path(store, "master/ability/leader_ability.orderedmap") if store else None
        if path is None or not path.is_file():
            self.skipTest("live store unavailable")
        import wf_share_update_codec as codec
        table = codec.unpack(path.read_bytes())
        t235, pre12 = [], []
        for key, value in table.items():
            if key == LEADER_KEY:
                continue
            for index, row in enumerate(codec.csv_read(value), 1):
                if len(row) == 124 and row[3] == "0":
                    if row[25] == "235":
                        t235.append((key, index, row[45]))
                    if "12" in (row[4], row[11], row[18]):
                        pre12.append((key, index))
        # 口径 A.4：进队长表前确认有 live 自制先例（官方与自制零先例的 kind 进队长表 = 角色页 C7050）。
        self.assertTrue(any(key == "169999" for key, _, _ in t235), t235)
        self.assertTrue({kind for _, _, kind in t235} & {"32", "33", "34"}, t235)
        self.assertTrue(any(key == "149989" for key, _ in pre12), pre12)

    # ------------------------------------------------------------------ 面板

    def test_panel_texts_are_exactly_the_confirmed_wording(self):
        self.assertEqual({k: [[v]] for k, v in PROPOSED.items()}, self.result["cas"])
        old_leader = self.live("cas", B.TEXT_LEADER)[0][0].split("\n")
        new_leader = PROPOSED[B.TEXT_LEADER].split("\n")
        self.assertEqual(old_leader[:4] + old_leader[5:], new_leader[:4] + new_leader[5:8])
        old_a3 = self.live("cas", B.TEXT_A3)[0][0].split("\n")
        new_a3 = PROPOSED[B.TEXT_A3].split("\n")
        self.assertEqual([old_a3[i] for i in (0, 2, 3)], [new_a3[i] for i in (0, 2, 3)])
        self.assertIn("攻击力+10%、直接攻击伤害+10%。", old_a3[1])
        for key, value in PROPOSED.items():
            with self.subTest(key=key):
                self.assertEqual([], B.panel_problems(key, value))
                self.assertEqual([], kitlib.panel_problems(value))
                for phrase in ("可无限", "可无限累积", "无上限", "无限叠加", "不设上限",
                               "自身为队长时", "觉醒后", "生命值100%以下", "／"):
                    self.assertNotIn(phrase, value)
                lines = value.split("\n")
                self.assertEqual(key == B.TEXT_A3, all(line.startswith(MAIN) for line in lines))
                self.assertEqual(key == B.TEXT_A3, any(line.startswith(MAIN) for line in lines))
                self.assertEqual([[value]], core.read_csv_lines(core.write_csv_lines([[value]])))

    # ------------------------------------------------------------------ Down（PF Lv3）

    def test_pf_lv3_only_the_supporter_toughness_drops_from_one_to_zero(self):
        old, new = self.live("dsl", B.PF_LV3), self.result["dsl"][B.PF_LV3]
        before, after = attacks(old), attacks(new)
        self.assertEqual([[{"min": 6.25, "max": 6.25}]] * 2 + [[{"min": 1, "max": 1}]], [a[13] for a in before])
        self.assertEqual([[{"min": 6.25, "max": 6.25}]] * 2 + [[{"min": 0, "max": 0}]], [a[13] for a in after])
        self.assertEqual(203, after[-1][1])  # 辅助型载荷（主体 3+200）
        self.assertEqual((26, 25), (B.pf_toughness(old), B.pf_toughness(new)))
        # 恢复这一格后与 live 逐节点相同：其余节点逐字保留（含 p14 Fever 点、伤害倍率）。
        restored = deepcopy(new)
        attacks(restored)[-1][13] = [{"min": 1, "max": 1}]
        self.assertEqual(B.digest(old), B.digest(restored))
        self.assertNotEqual(B.digest(old), B.digest(new))
        # AMF3 往返 + 四道 DSL 门禁。
        raw = encode_tree(new)
        self.assertEqual(new, wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"])
        self.assertEqual([], legality.action_dsl_element_problems(new, 5))
        self.assertEqual([], legality.action_dsl_subject_binding_problems(new))
        self.assertEqual([], legality.action_dsl_lookup_scope_problems(new))
        self.assertEqual([], legality.action_dsl_hit_area_target_problems(new))
        self.assertEqual([], B.dsl_problems(new))
        self.assertEqual([list(B.PF_PROGRAMS)], self.live("table", B.PF_ACTION))

    # ------------------------------------------------------------------ 合同

    def test_only_changed_keys_are_returned_in_the_contract_shape(self):
        result = self.result
        self.assertEqual({"ability", "leader", "cas", "text", "table", "action", "dsl",
                          "server_text", "new_programs", "notes"}, set(result))
        self.assertEqual({A3_KEY}, set(result["ability"]))
        self.assertEqual({LEADER_KEY}, set(result["leader"]))
        self.assertEqual(set(PROPOSED), set(result["cas"]))
        self.assertEqual({B.PF_LV3}, set(result["dsl"]))
        for kind in ("text", "table", "action", "server_text"):
            self.assertEqual({}, result[kind])
        self.assertEqual([], result["new_programs"])  # PF Lv3 程序在 live 已存在
        json.dumps(result["notes"], ensure_ascii=False)
        self.assertFalse(result["notes"]["runtime_verified"])
        for key in result["cas"]:
            self.assertTrue(key.startswith(("desc_override_" + B.CODE, "change_skill_" + B.CODE, B.CODE)))
        estimates = result["notes"]["frequency_estimates"]
        self.assertIn("≥30 次 → 1/10", estimates["piercing_growth_T235"])
        self.assertIn("≥30 次 → 1/10", estimates["fever_gain_T12"])

    def test_inputs_are_not_mutated_and_outputs_are_independent(self):
        data = deepcopy(self.data)
        before = deepcopy(data)
        result = B.revise(self.read_from(data))
        self.assertEqual(before, data)
        result["ability"][A3_KEY][2][34] = "changed"
        result["leader"][LEADER_KEY][8][49] = "changed"
        result["leader"][LEADER_KEY][4][49] = "changed"
        attacks(result["dsl"][B.PF_LV3])[-1][13] = "changed"
        self.assertEqual(before, data)
        self.assertEqual(self.result, B.revise(self.read_from(data)))

    def test_any_live_drift_fails_closed(self):
        for item in B.BEFORE:
            data = deepcopy(self.data)
            if item[0] == "dsl":  # DSL 树：改一格削韧
                attacks(data[item])[0][13] = [{"min": 7, "max": 7}]
            else:
                data[item][0][0] = data[item][0][0] + "x"
            with self.subTest(item=item), self.assertRaisesRegex(ValueError, "live drift"):
                B.revise(self.read_from(data))

    def test_rerunning_on_its_own_output_is_rejected(self):
        # 已发布后的新值同样拒绝：重跑不会把 10 次上限再砍一半、也不会再追加两行。
        data = deepcopy(self.data)
        for kind, group in (("ability", self.result["ability"]), ("leader", self.result["leader"]),
                            ("cas", self.result["cas"]), ("dsl", self.result["dsl"])):
            for key, value in group.items():
                data[kind, key] = deepcopy(value)
        with self.assertRaisesRegex(ValueError, "live drift"):
            B.revise(self.read_from(data))
        # 纯函数层同样拒绝自身输出（BEFORE 之外的第二道锁）。
        with self.assertRaisesRegex(ValueError, "ability3 row3"):
            B.ability3_rows(self.result["ability"][A3_KEY])
        with self.assertRaisesRegex(ValueError, "expected 8 rows"):
            B.leader_rows(self.result["leader"][LEADER_KEY], self.live("ability", A3_KEY))
        with self.assertRaisesRegex(ValueError, "leader row5"):  # 只取前 8 行也不会把 2% 再砍成 0.2%
            B.leader_rows(self.result["leader"][LEADER_KEY][:8], self.live("ability", A3_KEY))
        with self.assertRaisesRegex(ValueError, "move source"):
            B.moved_leader_rows(self.result["ability"][A3_KEY])
        with self.assertRaisesRegex(ValueError, "leader panel"):
            B.leader_text(PROPOSED[B.TEXT_LEADER])
        with self.assertRaisesRegex(ValueError, "ability3 panel"):
            B.ability3_text(PROPOSED[B.TEXT_A3])
        with self.assertRaisesRegex(ValueError, "toughness 1"):
            B.pf_lv3_tree(self.result["dsl"][B.PF_LV3])

    def test_leader_rows_refuse_to_duplicate_an_existing_same_trigger_row(self):
        # 若队长已有同触发/同 kind/同目标/同前置的行，必须合并而不是再追加一行。
        rows = self.live("leader", LEADER_KEY)
        moved = B.moved_leader_rows(self.live("ability", A3_KEY))
        rows[2] = deepcopy(moved[1])
        rows[2][45] = "33"
        with self.assertRaisesRegex(ValueError, "merge instead"):
            B.leader_rows(rows, self.live("ability", A3_KEY))

    def test_every_output_row_passes_the_client_gates(self):
        strings = {key for kind, key in self.data if kind == "cas"} | set(self.result["cas"])
        for table, group in (("ability", self.result["ability"]), ("leader_ability", self.result["leader"])):
            for key, rows in group.items():
                for index, row in enumerate(rows, 1):
                    with self.subTest(table=table, key=key, index=index):
                        self.assertEqual(126 if table == "ability" else 124, len(row))
                        self.assertEqual([], legality.client_legality_problems(table, row))
                        self.assertEqual([], legality.declared_block_field_problems(table, row))
                        self.assertEqual([], legality.ability_element_column_problems(table, row, 5))
                        self.assertEqual([], legality.invoke_skill_string_problems(row, strings, table))
                        needed = legality.required_client_capabilities(table, row)
                        # 只有能力3第5行 I724（比例版客户端）需要能力；本次原样回写。
                        expected = ["kyubi-fever-ratio-v1"] if (key, row[47]) == (A3_KEY, "724") else []
                        self.assertEqual(expected, needed)
        self.assertEqual([], B.validate(self.result, strings))
        self.assertEqual(["kyubi-fever-ratio-v1", "panel-description-override-v2"], B.CAPABILITIES)

    def test_validation_rejects_missing_native_strings_and_bad_panels(self):
        strings = {key for kind, key in self.data if kind == "cas"} | set(self.result["cas"])
        for missing in (B.CHANGE_SKILL_STRING_ID, B.PF_STRING_ID, B.BALL_HIT_STRING_ID, B.A3_STRING_ID):
            with self.subTest(missing=missing):
                self.assertTrue(B.validate(self.result, strings - {missing}))
        bad = deepcopy(self.result)
        bad["cas"][B.TEXT_LEADER] = [[PROPOSED[B.TEXT_LEADER] + "（可无限累积）"]]
        self.assertTrue(any("可无限" in p for p in B.validate(bad, strings)))
        bad = deepcopy(self.result)
        bad["cas"][B.TEXT_A3] = [[PROPOSED[B.TEXT_A3].replace(MAIN, "", 1)]]
        self.assertTrue(any("main icon" in p for p in B.validate(bad, strings)))

    # ------------------------------------------------------------------ 生成器一致性

    def test_generators_produce_exactly_the_revised_values(self):
        # 生成器已同步到第三轮（wf_balance_20260927c_nephtim）：队长三处成长强度与队长面板两句按 c 回调。
        # 期望 = 第二批输出 + 第三轮覆盖（c 的函数以第二批输出为原像，原像不符直接抛错）；能力3 与能力3 面板不变。
        import wf_balance_20260927c_nephtim as C3
        source, _ = official_sources()
        rows = abilities.ability_rows(source)
        leaders = leader.leader_rows(source)
        self.assertEqual(self.result["ability"][A3_KEY], rows[A3_KEY])
        self.assertEqual(C3.leader_rows(self.result["leader"][LEADER_KEY], self.result["ability"][A3_KEY]),
                         leaders)
        panels = text.panel_rows(rows, leaders, piercing_extension="dark_resonance")
        expected_cas = deepcopy(self.result["cas"])
        expected_cas[B.TEXT_LEADER] = [[C3.leader_text(self.result["cas"][B.TEXT_LEADER][0][0])]]
        for key, value in expected_cas.items():
            self.assertEqual(value, panels[key], key)
        self.assertEqual((5_000, 10_000, 10),
                         (abilities.PIERCING_CAPPED_ATTACK_STRENGTH, abilities.PIERCING_CAPPED_DIRECT_STRENGTH,
                          abilities.PIERCING_CAPPED_LIMIT))
        self.assertEqual({3: (1, 0)}, powerflip.SUPPORTER_TOUGHNESS)

    @unittest.skipUnless(APK.is_file() and CDN.is_dir(), "official CDN archive / native PF bundle unavailable")
    def test_power_flip_generator_produces_exactly_the_revised_lv3_tree(self):
        from wf_enhancement_policy import OfficialBaseline
        from wf_quest_lib import hashed_rel
        official = OfficialBaseline(CDN, write_cache=False)
        loader = powerflip.with_bundle_fallback(lambda logical: official.get("common", hashed_rel(logical)), APK)
        tree = powerflip.build_power_flip(3, loader)
        self.assertEqual(self.result["dsl"][B.PF_LV3], tree)
        self.assertEqual(encode_tree(self.result["dsl"][B.PF_LV3]), encode_tree(tree))
        self.assertEqual(B.PF_LV3, powerflip.PROGRAM_PATHS[2])

    # ------------------------------------------------------------------ 候选

    def test_package_targets_and_versions_only_move_forward(self):
        self.assertEqual(["nephtim-summon-cap-20260916/ruin_girl_campus", "campus-nephtim-20260911"], B.PACKAGES)
        self.assertEqual(set(B.PACKAGES), set(B.PACKAGE_VERSION))
        self.assertEqual({}, B.REVIEWED_DRIFT)
        previous = {"nephtim-summon-cap-20260916/ruin_girl_campus": "0.2.3",
                    "campus-nephtim-20260911": "0.20260927"}
        version = lambda value: tuple(int(part) for part in value.split("."))
        for package, new in B.PACKAGE_VERSION.items():
            self.assertGreater(version(new), version(previous[package]), package)
            manifest = ROOT / "work/character_packs" / package / "package/manifest.json"
            if manifest.is_file():
                meta = json.loads(manifest.read_bytes())
                current = meta["package_version"]
                # 候选不能领先于任何一批已知版本；第三轮（wf_balance_20260927c_nephtim）回写后候选现值可能已是
                # 它的 PACKAGE_VERSION（高于本批），取两批版本号的较大者作上限。
                import wf_balance_20260927c_nephtim as C3
                ceiling = max(version(new), version(C3.PACKAGE_VERSION[package]))
                self.assertGreaterEqual(ceiling, version(current), package)
                if meta.get("snapshot", {}).get("revision_20260927b") is not None:
                    # 已回写：候选现值 == 本模块版本；第三轮（wf_balance_20260927c_nephtim）回写后 == c 版本。
                    self.assertIn(current, {new, C3.PACKAGE_VERSION[package]}, package)


if __name__ == "__main__":
    unittest.main()
