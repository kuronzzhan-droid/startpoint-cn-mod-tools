"""校园奈芙提姆 2026-09-27 平衡修订：方案B（只搬 I536）、2秒召唤、能力2合并贯穿与技能槽上限、多人卡顿修复。"""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
import zlib

pass  # Imports resolve from this checkout/package, not external source copies.

from test_bianca_dragon_abilities import official_sources
import wf_balance_20260927_nephtim as B
import wf_balance_20260927b_nephtim as B2  # 第二批覆盖（生成器已同步到第二批）
import wf_balance_20260927c_nephtim as C3  # 第三轮覆盖（生成器已同步到第三轮）
import wf_client_legality as legality
import wf_dsl
import wf_mod_tool as core
import wf_nephtim_ball_hit_count as ball_hit_count
import wf_nephtim_fever_abilities as abilities
import wf_nephtim_fever_leader as leader
import wf_nephtim_fever_text as text
import wf_nephtim_multiball_direct as multiball_direct
import wf_nephtim_multiball_fever as multiball_fever
from wf_character_revision import encode_tree

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).parent / "fixtures/balance_20260927_nephtim.json"
MAIN = " <icon id='main'>  "
PREFIX = "battle/action/skill/action/ability_skill/ruin_girl_campus$"
PROGRAMS = {PREFIX + "ruin_girl_campus_ball_hit_count": 2,
            PREFIX + "ruin_girl_campus_multiball_direct": 2,
            PREFIX + "ruin_girl_campus_multiball_direct_a4": 1}

PROPOSED = {
    "desc_override_ruin_girl_campus": (
        "暗属性共鸣时，强化弹射变为特殊型与辅助型组合。\n"
        "暗属性共鸣时，强化『午后星轨·甜蜜续杯』：额外赋予暗属性角色及协力球攻击力提升效果。\n"
        "暗属性共鸣时，Fever 模式中，强化后的技能发动时，自身获得或刷新「星夜茶会」，并赋予暗属性角色及协力球护盾。\n"
        "暗属性共鸣时，暗属性角色攻击力+200%、直接攻击伤害+400%。\n"
        "暗属性共鸣时，每达成35连击，暗属性角色获得的 Fever 槽上升量+20%。\n"
        "暗属性共鸣时，Fever 时间+100%。\n"
        "暗属性共鸣时，每有1个协力球消失时，暗属性角色技能槽+5%。\n"
        "暗属性共鸣时，每有1个协力球存在，自身直击判定次数+1。"),
    "desc_override_ruin_girl_campus_1": (
        MAIN + "战斗开始时，自身技能槽+50%。\n"
        + MAIN + "暗属性共鸣时，Fever 模式中，持有「星夜茶会」时，每经过2秒交替召唤1个光、暗属性协力球，各持续25秒且无法回复生命值，协力球最多同时存在9个；再次发动技能不会延长已有协力球的存在时间。\n"
        + MAIN + "暗属性共鸣时，Fever 模式中，持有「星夜茶会」时，协力球已达9个时，该次召唤改为自身攻击力+25%，持续20秒，可叠加。\n"
        + MAIN + "Fever 结束或自身倒下时，「星夜茶会」解除。"),
    "desc_override_ruin_girl_campus_2": (
        "暗属性共鸣时，全队贯穿效果时间+40%。\n"
        "暗属性共鸣时，暗属性角色直接攻击伤害+250%。\n"
        "暗属性共鸣时，Fever 模式中，暗属性角色技能槽上限+10%。"),
}


def nonempty(row):
    return {i: v for i, v in enumerate(row) if v != ""}


class NephtimBalance20260927Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = json.loads(FIXTURE.read_bytes())
        cls.data = {(r["kind"], r["key"]): r["value"] for r in fixture["reads"]}
        cls.result = B.revise(cls.read_from(cls.data))

    @staticmethod
    def read_from(data):
        return lambda kind, key: data[kind, key]

    def live(self, kind, key):
        return deepcopy(self.data[kind, key])

    def test_fixture_is_the_reviewed_before_baseline(self):
        self.assertEqual(set(B.BEFORE), set(self.data))
        for item, expected in B.BEFORE.items():
            self.assertEqual(expected, B.digest(self.data[item]), item)

    def test_ability1_drops_only_the_flag_and_summons_every_two_seconds(self):
        old = self.live("ability", "1699891")
        rows = self.result["ability"]["1699891"]
        self.assertEqual(4, len(rows))
        self.assertNotIn("536", [r[47] for r in rows])
        self.assertEqual(["211", "629", "528", "528"], [r[47] for r in rows])
        self.assertEqual({"false"}, {r[1] for r in rows})  # 整键仍主位限制
        summon = rows[1]
        self.assertEqual(["12000000", "12000000"], summon[32:34])
        self.assertEqual(["9000000", "9000000"], old[2][32:34])
        # 召唤行只改 threshold2 两格；开局充能与两条清理行逐格不变。
        self.assertEqual([32, 33], [i for i in range(126) if summon[i] != old[2][i]])
        self.assertEqual([old[0], old[3], old[4]], [rows[0], rows[2], rows[3]])
        self.assertEqual(("232", "100000", "(None)", "0", "16998901"),
                         (summon[27], summon[30], summon[34], summon[35], summon[37]))

    def test_leader_gains_the_flag_after_pf_and_loses_gauge_maximum_and_piercing(self):
        old = self.live("leader", "169989")
        rows = self.result["leader"]["169989"]
        self.assertEqual(8, len(rows))
        self.assertEqual(["722", "536", "33", "32", "50", "56", "211", "629"], [r[45] for r in rows])
        flag = rows[1]
        enhance = self.live("ability", "1699891")[1]
        self.assertEqual(["ruin_girl_campus", "0", ""] + enhance[5:], flag)
        self.assertEqual(list(B.OFFICIAL_LEADER_536_COLUMNS), sorted(nonempty(flag)))
        self.assertEqual(("0", "2", "600000", "Black", "0", "0", "change_skill_ruin_girl_campus_fever"),
                         (flag[3], flag[4], flag[7], flag[9], flag[11], flag[25], flag[68]))
        self.assertFalse(any(r[3] == "1" and r[107] == "124" for r in rows))
        self.assertFalse(any(r[45] == "190" for r in rows))
        self.assertNotIn("12", [r[c] for r in rows for c in (4, 11, 18)])  # 队长不再用前置12
        self.assertEqual([old[i] for i in (0, 1, 2, 5, 6, 7)],
                         [rows[i] for i in (0, 2, 3, 4, 5, 6)])
        self.assertEqual("ruin_girl_campus_ball_hit_count", rows[-1][68])  # 9/25 行保留
        # 多人卡顿修复：9/25 行只改周期两格（队长表 c28/c29）。
        self.assertEqual([28, 29], [i for i in range(124) if rows[-1][i] != old[8][i]])

    def test_ability2_merges_piercing_and_hosts_the_fever_gauge_maximum(self):
        old = self.live("ability", "1699892")
        rows = self.result["ability"]["1699892"]
        self.assertEqual(3, len(rows))
        self.assertEqual({"true"}, {r[1] for r in rows})  # 不加主位限制
        self.assertEqual([51, 52], [i for i in range(126) if rows[0][i] != old[0][i]])
        self.assertEqual(["40000", "40000"], rows[0][51:53])
        self.assertEqual(old[1], rows[1])
        gauge = rows[2]
        self.assertEqual({0: "ruin_girl_campus_2", 1: "true", 2: "attack_black", 3: "0", 5: "1",
                          6: "2", 9: "600000", 10: "600000", 11: "Black", 13: "12", 20: "0",
                          85: "(None)", 97: "4", 108: "false", 109: "124", 110: "5",
                          111: "Black", 113: "10000", 114: "10000"}, nonempty(gauge))
        moved = self.live("leader", "169989")[3]
        self.assertEqual(["ruin_girl_campus_2", "true", "attack_black"] + moved[1:], gauge)

    def test_panel_texts_are_exactly_the_confirmed_wording(self):
        self.assertEqual({k: [[v]] for k, v in PROPOSED.items()}, self.result["cas"])
        for key, value in PROPOSED.items():
            for phrase in B.FORBIDDEN_PANEL_PHRASES:
                self.assertNotIn(phrase, value)
            lines = value.split("\n")
            self.assertEqual(key.endswith("_1"), all(line.startswith(MAIN) for line in lines))
            self.assertEqual([[value]], core.read_csv_lines(core.write_csv_lines([[value]])))
        self.assertNotIn("1.5秒", PROPOSED["desc_override_ruin_girl_campus_1"])
        self.assertNotIn("强化『", PROPOSED["desc_override_ruin_girl_campus_1"])
        self.assertNotIn("技能槽上限", PROPOSED["desc_override_ruin_girl_campus"])
        self.assertNotIn("贯穿", PROPOSED["desc_override_ruin_girl_campus"])

    def test_only_changed_keys_are_returned_in_the_contract_shape(self):
        result = self.result
        self.assertEqual({"ability", "leader", "cas", "text", "table", "action", "dsl",
                          "server_text", "new_programs", "notes"}, set(result))
        self.assertEqual({"1699891", "1699892", "1699893", "1699894"}, set(result["ability"]))
        self.assertEqual({"169989"}, set(result["leader"]))
        self.assertEqual(set(PROPOSED), set(result["cas"]))
        self.assertEqual(set(PROGRAMS), set(result["dsl"]))
        for kind in ("text", "table", "action", "server_text"):
            self.assertEqual({}, result[kind])
        self.assertEqual([], result["new_programs"])  # 三棵 DSL 在 live 已存在
        json.dumps(result["notes"], ensure_ascii=False)
        self.assertFalse(result["notes"]["runtime_verified"])
        # 队长的贯穿与技能槽上限改由能力2承载：能力2未解锁时当队长是削弱，必须写进说明。
        semantics = result["notes"]["gameplay_semantics"]
        self.assertTrue(any("能力2未解锁" in line and "20%→0%" in line for line in semantics))
        for key in result["cas"]:
            self.assertTrue(key.startswith(("desc_override_" + B.CODE, "change_skill_" + B.CODE, B.CODE)))

    def test_inputs_are_not_mutated_and_outputs_are_independent(self):
        data = deepcopy(self.data)
        before = deepcopy(data)
        result = B.revise(self.read_from(data))
        self.assertEqual(before, data)
        result["ability"]["1699891"][0][0] = "changed"
        result["leader"]["169989"][1][0] = "changed"
        result["ability"]["1699892"][2][0] = "changed"
        result["ability"]["1699893"][5][30] = "changed"
        result["leader"]["169989"][7][28] = "changed"
        for tree in result["dsl"].values():
            next(n for n in wf_dsl.iter_dsl_commands(tree) if n[0] == "CreateCondition")[2][0][1] = "changed"
        self.assertEqual(before, data)

    def test_any_live_drift_fails_closed(self):
        for item in B.BEFORE:
            data = deepcopy(self.data)
            if item[0] == "dsl":  # DSL 树：改一个持续帧（2 → 3）
                next(n for n in wf_dsl.iter_dsl_commands(data[item])
                     if n[0] == "CreateCondition")[2][0][1] = [{"min": 3, "max": 3}]
            else:
                data[item][0][0] = data[item][0][0] + "x"
            with self.subTest(item=item), self.assertRaisesRegex(ValueError, "live drift"):
                B.revise(self.read_from(data))
        # 已发布后的新值同样拒绝：重跑不会把 40% 叠成 60%。
        data = deepcopy(self.data)
        for kind, group in (("ability", self.result["ability"]), ("leader", self.result["leader"]),
                            ("cas", self.result["cas"]), ("dsl", self.result["dsl"])):
            for key, rows in group.items():
                data[kind, key] = deepcopy(rows)
        with self.assertRaisesRegex(ValueError, "live drift"):
            B.revise(self.read_from(data))

    def test_every_output_row_passes_the_client_gates(self):
        strings = {key for kind, key in self.data if kind == "cas"} | set(self.result["cas"])
        for table, group in (("ability", self.result["ability"]), ("leader_ability", self.result["leader"])):
            for key, rows in group.items():
                for row in rows:
                    with self.subTest(table=table, key=key, kind=row[47 if table == "ability" else 45]):
                        self.assertEqual(126 if table == "ability" else 124, len(row))
                        self.assertEqual([], legality.client_legality_problems(table, row))
                        self.assertEqual([], legality.declared_block_field_problems(table, row))
                        self.assertEqual([], legality.ability_element_column_problems(table, row, 5))
                        self.assertEqual([], legality.invoke_skill_string_problems(row, strings, table))
                        needed = legality.required_client_capabilities(table, row)
                        # 只有能力3第5行 I724（比例版客户端）需要能力；本次原样回写。
                        expected = ["kyubi-fever-ratio-v1"] if (key, row[47]) == ("1699893", "724") else []
                        self.assertEqual(expected, needed)
        self.assertEqual([], B.validate(self.result, strings))
        self.assertEqual(["kyubi-fever-ratio-v1", "panel-description-override-v2"], B.CAPABILITIES)

    def test_validation_rejects_missing_native_strings(self):
        strings = {key for kind, key in self.data if kind == "cas"} | set(self.result["cas"])
        for missing in (B.SPAWN_STRING_ID, B.BALL_HIT_STRING_ID, B.CHANGE_SKILL_STRING_ID, B.PF_STRING_ID,
                        B.A3_STRING_ID, B.A4_STRING_ID):
            with self.subTest(missing=missing):
                self.assertTrue(B.validate(self.result, strings - {missing}))

    def test_generators_produce_exactly_the_revised_values(self):
        # 生成器已同步到 2026-09-27 第二批（wf_balance_20260927b_nephtim）：能力3 贯穿成长封顶、队长 Fever
        # 获得量放缓并追加两条贯穿成长、队长面板对应两句。期望 = 第一批输出 + 第二批覆盖（第二批函数以第一批
        # 发布后的值为原像，原像不符会直接抛错）；第二批未触及的键仍与第一批输出逐字相同。
        source, _ = official_sources()
        rows = abilities.ability_rows(source)
        leaders = leader.leader_rows(source)
        expected = deepcopy(self.result["ability"])
        expected["1699893"] = B2.ability3_rows(self.result["ability"]["1699893"])
        for key, value in expected.items():
            self.assertEqual(value, rows[key], key)
        second_a3 = B2.ability3_rows(self.result["ability"]["1699893"])
        self.assertEqual(C3.leader_rows(B2.leader_rows(self.result["leader"]["169989"],
                                                       self.result["ability"]["1699893"]), second_a3),
                         leaders)
        # 第一批 8 行中只有第5行（Fever 获得量成长）的强度两格被第二批（及第三轮）改。
        first = self.result["leader"]["169989"]
        self.assertEqual([(4, 49), (4, 50)], [(i, c) for i in range(8) for c in range(124)
                                              if leaders[i][c] != first[i][c]])
        panels = text.panel_rows(rows, leaders, piercing_extension="dark_resonance")
        expected_cas = deepcopy(self.result["cas"])
        expected_cas[B.TEXT_LEADER] = [[C3.leader_text(B2.leader_text(self.result["cas"][B.TEXT_LEADER][0][0]))]]
        # 第三轮面板同条件合并：能力2 第1/2行并成一行（C3.ability2_text 以第一批输出为原像）。
        expected_cas[B.TEXT_A2] = [[C3.ability2_text(self.result["cas"][B.TEXT_A2][0][0])]]
        # 第三轮共鸣省略（口径 6）：能力1 第2/3行删「暗属性共鸣时，」（C3.ability1_text 以第一批输出为原像）。
        expected_cas[C3.TEXT_A1] = [[C3.ability1_text(self.result["cas"][C3.TEXT_A1][0][0])]]
        for key, value in expected_cas.items():
            self.assertEqual(value, panels[key], key)
        self.assertEqual(120, abilities.SUMMON_PERIOD_FRAMES)
        self.assertEqual(120, abilities.metadata()["skill_enhancement"]["period_frames"])
        self.assertEqual(["ruin_girl_campus", "0", ""] + abilities.enhance_row(source)[5:], leaders[1])
        # 卡顿修复的三棵 DSL：生成器树与 revise() 树相同，编码字节也相同（live 解出的 2147483647.0 与 int 同编码）。
        for module in (ball_hit_count, multiball_direct, multiball_fever):
            tree = self.result["dsl"][module.ACTION_PATH]
            self.assertEqual(module.action_tree(), tree, module.__name__)
            self.assertEqual(encode_tree(module.action_tree()), encode_tree(tree), module.__name__)
        self.assertEqual({multiball_direct.LOGICAL_PATH, multiball_fever.LOGICAL_PATH,
                          ball_hit_count.ACTION_PATH + ".action.dsl.amf3.deflate"},
                         {wf_dsl.dsl_logical(program) for program in self.result["dsl"]})

    def test_multiplayer_lag_fix_slows_three_pulses_to_every_ten_frames(self):
        # 三条 T77→629 行：周期 100000 → 1000000（帧 × 100000，每 1 帧 → 每 10 帧），其余列不变。
        cases = (("ability", "1699893", 5, 5, 30, "ruin_girl_campus_multiball_direct"),
                 ("ability", "1699894", 1, 1, 30, "ruin_girl_campus_multiball_direct_a4"),
                 ("leader", "169989", 8, 7, 28, "ruin_girl_campus_ball_hit_count"))
        for kind, key, old_index, new_index, column, string_id in cases:
            with self.subTest(key=key):
                old = self.live(kind, key)
                new = self.result[kind][key]
                self.assertEqual(len(old) - (1 if kind == "leader" else 0), len(new))
                before, after = old[old_index], new[new_index]
                s = column - 30
                self.assertEqual(("77", "629", string_id, PREFIX + string_id),
                                 (after[27 + s], after[47 + s], after[70 + s], after[71 + s]))
                self.assertEqual(["100000"] * 2, before[column:column + 2])
                self.assertEqual(["1000000"] * 2, after[column:column + 2])
                self.assertEqual([column, column + 1],
                                 [i for i in range(len(after)) if after[i] != before[i]])
        a3, a4 = self.result["ability"]["1699893"], self.result["ability"]["1699894"]
        self.assertEqual(self.live("ability", "1699893")[:5], a3[:5])
        self.assertEqual(self.live("ability", "1699894")[0], a4[0])
        self.assertEqual({"false"}, {r[1] for r in a3})  # 能力3 仍主位限制
        self.assertEqual({"true"}, {r[1] for r in a4})
        # 输出里再没有每帧执行 DSL 的 T77→629 行（能力1 T77 I528 清理行不调 DSL，不在范围）。
        every_frame = [(key, i) for key, rows in self.result["ability"].items() for i, r in enumerate(rows)
                       if r[27] == "77" and r[47] == "629" and r[30] == "100000"]
        every_frame += [(key, i) for key, rows in self.result["leader"].items() for i, r in enumerate(rows)
                        if r[25] == "77" and r[45] == "629" and r[28] == "100000"]
        self.assertEqual([], every_frame)
        self.assertEqual(("77", "100000", "528"),
                         tuple(self.result["ability"]["1699891"][3][i] for i in (27, 30, 47)))
        self.assertEqual((10, 10, 10), (ball_hit_count.UPDATE_PERIOD_FRAMES, multiball_direct.UPDATE_PERIOD_FRAMES,
                                        multiball_fever.UPDATE_PERIOD_FRAMES))
        self.assertEqual(B.REFRESH_FRAMES * 100_000, int(B.NEW_REFRESH))

    def test_multiplayer_lag_fix_stretches_each_hidden_state_to_twenty_frames(self):
        for program, count in PROGRAMS.items():
            with self.subTest(program=program.rsplit("$", 1)[1]):
                old, new = self.live("dsl", program), self.result["dsl"][program]
                key = program.rsplit("$", 1)[1]
                conditions = [n for n in wf_dsl.iter_dsl_commands(new) if n[0] == "CreateCondition"]
                self.assertEqual(count, len(conditions))
                for node in conditions:
                    self.assertEqual(key, node[7])
                    self.assertIs(node[9], True)  # 隐形
                    self.assertEqual([{"min": 20, "max": 20}], node[2][0][1])
                # 恢复持续帧后与 live 逐节点相同：其余格不动。
                restored = deepcopy(new)
                for node in wf_dsl.iter_dsl_commands(restored):
                    if node[0] == "CreateCondition":
                        node[2][0][1] = [{"min": 2, "max": 2}]
                self.assertEqual(B.digest(old), B.digest(restored))
                self.assertNotEqual(B.digest(old), B.digest(new))
                # AMF3 往返一致 + 四道 DSL 门禁。
                raw = encode_tree(new)
                self.assertEqual(new, wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"])
                self.assertEqual([], legality.action_dsl_element_problems(new, 5))
                self.assertEqual([], legality.action_dsl_subject_binding_problems(new))
                self.assertEqual([], legality.action_dsl_lookup_scope_problems(new))
                self.assertEqual([], legality.action_dsl_hit_area_target_problems(new))
                self.assertEqual([], B.dsl_problems(new))
        # ball_hit_count 的判定次数基数（2/1）不是持续帧，不能跟着改。
        tree = self.result["dsl"][PREFIX + "ruin_girl_campus_ball_hit_count"]
        bases = [n[2][0][2][0] for n in wf_dsl.iter_dsl_commands(tree) if n[0] == "CreateCondition"]
        self.assertEqual([{"min": 2, "max": 2}, {"min": 1, "max": 1}], bases)

    def test_multiplayer_lag_fix_rejects_unexpected_shapes(self):
        program = PREFIX + "ruin_girl_campus_multiball_direct"
        tree = self.live("dsl", program)
        with self.assertRaisesRegex(ValueError, "2-frame"):
            B.refresh_tree(B.refresh_tree(tree, program), program)  # 已是 20 帧不会再乘
        row = self.live("ability", "1699893")[5]
        with self.assertRaisesRegex(ValueError, "every-frame T77"):
            B.slow_refresh(B.slow_refresh(row, "ability", B.A3_STRING_ID), "ability", B.A3_STRING_ID)
        with self.assertRaisesRegex(ValueError, "every-frame T77"):
            B.slow_refresh(row, "ability", B.A4_STRING_ID)  # 串键/程序错配

    def test_notes_state_the_performance_fix_and_its_gameplay_cost(self):
        notes = self.result["notes"]
        fix = notes["performance_fix"]
        self.assertEqual({"before": 1, "after": 10}, fix["period_frames"])
        self.assertEqual({"before": 2, "after": 20}, fix["condition_duration_frames"])
        self.assertEqual({"before": 60, "after": 6}, fix["helper_invocations_per_second_per_row"])
        semantics = notes["gameplay_semantics"]
        self.assertTrue(any("最多晚 10 帧" in line for line in semantics))
        self.assertTrue(any("错位 10 帧" in line for line in semantics))
        self.assertIn("面板文字（卡顿修复不改文案）", notes["unchanged"])

    def test_package_targets_and_versions_only_move_forward(self):
        self.assertEqual(["nephtim-summon-cap-20260916/ruin_girl_campus", "campus-nephtim-20260911"],
                         B.PACKAGES)
        self.assertEqual(set(B.PACKAGES), set(B.PACKAGE_VERSION))
        previous = {"nephtim-summon-cap-20260916/ruin_girl_campus": "0.2.2",
                    "campus-nephtim-20260911": "0.20260925"}
        version = lambda text: tuple(int(part) for part in text.split("."))
        # 第二批覆盖：wf_balance_20260927b_nephtim 对同两个候选再升一版并写 snapshot revision_20260927b；
        # 回写后候选现值 = 第二批版本（> 第一批版本），上限改取第二批版本。
        self.assertEqual(B.PACKAGES, B2.PACKAGES)
        for package, new in B.PACKAGE_VERSION.items():
            self.assertGreater(version(new), version(previous[package]), package)
            second = B2.PACKAGE_VERSION[package]
            self.assertGreater(version(second), version(new), package)
            manifest = ROOT / "work/character_packs" / package / "package/manifest.json"
            if manifest.is_file():
                meta = json.loads(manifest.read_bytes())
                current = meta["package_version"]
                if meta.get("snapshot", {}).get("revision_20260927b") is not None:
                    # 第三轮（wf_balance_20260927c_nephtim）回写后候选现值 = c 版本。
                    self.assertIn(current, {second, C3.PACKAGE_VERSION[package]}, package)
                else:
                    self.assertGreaterEqual(version(new), version(current), package)

    def test_relocated_flag_matches_the_official_leader_precedent(self):
        cdn = ROOT / ".cdn/cn"
        if not cdn.is_dir():
            self.skipTest("official CDN archive unavailable")
        from wf_enhancement_policy import OfficialBaseline
        baseline = OfficialBaseline(cdn, cache_dir=ROOT / "mod-tools/work/official-baseline",
                                    write_cache=False)
        digest = core.sha1_path("master/ability/leader_ability.orderedmap")
        official = core.read_orderedmap_file_from_bytes(baseline.get("common", digest[:2] + "/" + digest[2:]))
        precedents = [row for value in official.values() for row in core.read_csv_lines(value)
                      if len(row) > 45 and row[3] == "0" and row[45] == "536"]
        self.assertEqual(1, len(precedents))
        precedent = precedents[0]
        self.assertEqual("dryad_hw23", precedent[0])
        flag = self.result["leader"]["169989"][1]
        self.assertEqual(sorted(nonempty(precedent)), sorted(nonempty(flag)))
        differing = [i for i in range(124) if precedent[i] != flag[i]]
        self.assertEqual([0, 9, 68], differing)  # 角色键、共鸣属性组、强化串键


if __name__ == "__main__":
    unittest.main()
