# -*- coding: utf-8 -*-
"""白「盛夏的咆哮」149990 2026-09-27 平衡第三轮（c）：Fever 每 1.5 秒成长 5% → 35%（2/3 档）+ 面板同条件合并
+ 技能强化文案规范（旗号 1 条目与能力1 面板第 2 行官方格式、点名『盛夏咆哮』、同文；数据依据 fail closed）。

fixture（``fixtures/balance_20260927c_bai.json``）是 live 1.4.1053 的 revise() 输入快照
（``stage_batch.make_read(live_only=True)`` 只读；1.4.1054 复核逐字相同）；只有候选包检查需要本机工作区（skipUnless）。
面板合并校验器是仓库内的 ``mod-tools/wf_panel_merge_check.check``（硬依赖，不跳过）；
合并行逐字 / 数据条件逐列相同 / 共鸣省略依据另有独立断言。
不写 live store / assets / .cdn / 候选包。
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
pass  # Imports resolve from this checkout/package, not external source copies.
sys.setrecursionlimit(10000)

import wf_balance_20260927b_bai as B  # noqa: E402
import wf_balance_20260927c_bai as M  # noqa: E402
import wf_describe  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
from wf_panel_merge_check import check as check_merge  # noqa: E402
import wf_share_update_codec as X  # noqa: E402
from wf_client_legality import (ability_element_column_problems, client_legality_problems,  # noqa: E402
                                declared_block_field_problems, invoke_skill_string_problems,
                                required_client_capabilities)

FIXTURE = Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927c_bai.json'
B_FIXTURE = Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927b_bai.json'
WORKSPACE = ROOT / "work/character_packs" / M.PACKAGES[0]
#: 队长行依赖固有状态的列（前置 uid ×3、瞬发触发 uid、瞬发前置计数 uid、持续前置 uid、持续触发 uid）。
LEADER_STATE_COLS = (10, 17, 24, 35, 43, 93, 102)


def as_tuple(version: str) -> tuple[int, ...]:
    return tuple(int(x) for x in version.split("."))


class BaiBatch3Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(FIXTURE.read_bytes())
        cls.inputs = cls.data["inputs"]
        cls.out = M.revise(cls.read_from(cls.inputs))

    @staticmethod
    def read_from(inputs):
        return lambda kind, key: inputs[kind][key]

    def old(self, kind, key):
        return self.inputs[kind][key]

    # ------------------------------------------------------------ 契约

    def test_fixture_is_the_reviewed_baseline(self):
        self.assertEqual(7, len(M.BEFORE))
        for (kind, key), want in M.BEFORE.items():
            self.assertEqual(want, M.digest(self.old(kind, key)), (kind, key))
        self.assertEqual({(k, key) for k, keys in self.inputs.items() for key in keys}, set(M.BEFORE))
        self.assertEqual("1.4.1053", self.data["meta"]["live_tail"])
        self.assertEqual("1.4.1054", self.data["meta"]["live_tail_rechecked"])

    def test_live_baseline_is_exactly_the_batch2_output(self):
        b_inputs = json.loads(B_FIXTURE.read_bytes())["inputs"]
        key = lambda kind, k: "|".join(k) if kind == "table" else k     # noqa: E731
        b_out = B.revise(lambda kind, k: b_inputs[kind][key(kind, k)])
        self.assertEqual(self.old("leader", M.LEADER), b_out["leader"][M.LEADER])
        self.assertEqual(self.old("cas", M.CAS_LEADER), b_out["cas"][M.CAS_LEADER])

    def test_module_contract_constants(self):
        self.assertEqual(("149990", "white_tiger_summer"), (M.CID, M.CODE))
        self.assertEqual(["white_tiger_summer"], M.PACKAGES)
        self.assertEqual({"white_tiger_summer": "1.0.4"}, M.PACKAGE_VERSION)
        self.assertEqual(["panel-description-override-v2"], M.CAPABILITIES)   # 面板覆盖文案生效所需
        self.assertEqual({}, M.REVIEWED_DRIFT)
        self.assertGreater(as_tuple(M.PACKAGE_VERSION[M.PACKAGES[0]]), as_tuple(B.PACKAGE_VERSION[M.PACKAGES[0]]))
        self.assertFalse(self.out["notes"]["runtime_verified"])
        json.dumps(self.out["notes"], ensure_ascii=False)

    def test_output_shape_and_only_changed_keys(self):
        self.assertEqual({"ability", "leader", "cas", "text", "table", "action", "dsl",
                          "server_text", "new_programs", "notes"}, set(self.out))
        self.assertEqual([M.LEADER], list(self.out["leader"]))
        self.assertEqual({M.CAS_LEADER, M.CAS_SWITCH, M.CAS_A1}, set(self.out["cas"]))
        for kind in ("ability", "text", "table", "action", "dsl", "server_text"):
            self.assertEqual({}, self.out[kind], kind)
        self.assertEqual([], self.out["new_programs"])

    # ------------------------------------------------------------ 队长 #3/#4

    def test_leader_only_fever_tick_strength_changes(self):
        old, new = self.old("leader", M.LEADER), self.out["leader"][M.LEADER]
        self.assertEqual(6, len(new))
        seen = {i: {c: (x, y) for c, (x, y) in enumerate(zip(a, b)) if x != y}
                for i, (a, b) in enumerate(zip(old, new)) if a != b}
        self.assertEqual({3: {49: ("5000", "35000"), 50: ("5000", "35000")},
                          4: {49: ("5000", "35000"), 50: ("5000", "35000")}}, seen)
        for i in (3, 4):
            row = new[i]
            self.assertEqual(("248", "9000000", "9000000", "(None)", "0", "5", "Green"),
                             (row[25], row[28], row[29], row[32], row[33], row[46], row[47]))
        self.assertEqual(("32", "388"), (new[3][45], new[4][45]))
        for i in (0, 1, 2, 5):
            self.assertEqual(old[i], new[i], i)
        self.assertEqual(("8", "35", "5", "100000", "100000", "(None)"),
                         tuple(new[0][c] for c in (25, 45, 46, 49, 50, 32)))    # 充能行不动（口径 A.6）

    def test_growth_value_is_the_two_thirds_tier_rounded_up_to_five(self):
        """作者「可以砍到2/3」「数值尽量取5的倍数」：50×2/3=33.3 → 35（向上取、不低于下限）。"""
        original, batch2, new = (int(M.FEVER_TICK_TABLE[k]) for k in ("original", "batch2", "suggested"))
        self.assertEqual((original, batch2, new), (50_000, 5_000, 35_000))
        self.assertEqual(int(M.FEVER_TICK_NEW), new)
        self.assertGreaterEqual(new * 3, original * 2)
        self.assertLess((new - 5_000) * 3, original * 2)                # 30% 低于下限
        self.assertEqual(new % 5_000, 0)
        # 3 分钟 87 跳（72–102）：原 4350% / 批二 435% / 本轮 3045%。
        self.assertEqual([t * 87 // 1000 for t in (original, batch2, new)], [4350, 435, 3045])
        self.assertEqual((new * 72 // 1000, new * 102 // 1000), (2520, 3570))

    def test_leader_rows_read_back(self):
        rendered = wf_describe.describe_rows(self.out["leader"][M.LEADER][3:5], "leader_ability")
        self.assertEqual(rendered, ["风·编成≥6 时: FeverFrame≥90 → 赋予全队(风) 攻击力 35%",
                                    "风·编成≥6 时: FeverFrame≥90 → 赋予全队(风) 能力伤害 35%"])

    def test_panel_only_line_five_changes_and_passes_rules(self):
        old = self.old("cas", M.CAS_LEADER)[0][0].split("\n")
        text = self.out["cas"][M.CAS_LEADER]
        self.assertEqual((1, 1), (len(text), len(text[0])))
        self.assertEqual(tuple(old), M.PANEL_LINES_BEFORE)
        numeric = list(M.PANEL_LINES_NUMERIC)                            # 数值稿：只换第 5 行
        self.assertEqual(6, len(numeric))
        self.assertEqual({4}, {i for i, (a, b) in enumerate(zip(old, numeric)) if a != b})
        self.assertEqual("风属性共鸣时，FEVER模式中每持续1.5秒，风属性角色攻击力＋5%、能力伤害＋5%", old[4])
        self.assertEqual("风属性共鸣时，FEVER模式中每持续1.5秒，风属性角色攻击力＋35%、能力伤害＋35%", numeric[4])
        new = text[0][0].split("\n")
        self.assertEqual(5, len(new))                                    # 第 3/4 行同条件合并
        self.assertEqual(numeric[4], new[3])
        self.assertEqual([], KL.panel_problems(text[0][0]))
        for word in ("可无限", "无上限", "无限叠加", "不设上限", "自身为队长时", "／", "共鸣时：", "觉醒后", "生命值100%以下"):
            self.assertNotIn(word, text[0][0])

    # ------------------------------------------------------------ 面板同条件合并 / 共鸣省略

    def test_panel_merged_line_is_verbatim(self):
        new = self.out["cas"][M.CAS_LEADER][0][0].split("\n")
        self.assertEqual([
            "赋予专属强化弹射：格斗型＋特殊型强化弹射同时生效",
            "风属性共鸣时，风属性角色进入FEVER模式时技能槽充能速度＋100%",
            "风属性共鸣时，风属性角色技能槽最大值＋50%，FEVER时间＋50%",
            "风属性共鸣时，FEVER模式中每持续1.5秒，风属性角色攻击力＋35%、能力伤害＋35%",
            "每达成35连击，自身FEVER槽＋35%",
        ], new)
        # 合并行 = 两条原文共用条件 + 各自效果原措辞（只省略重复的「风属性共鸣时，」）。
        first, second = (M.PANEL_LINES_NUMERIC[i] for i in M.MERGE_LINES)
        prefix = "风属性共鸣时，"
        self.assertTrue(first.startswith(prefix) and second.startswith(prefix))
        self.assertEqual(first + "，" + second[len(prefix):], M.MERGED_LINE)
        # 未合并的行逐字保留、行序不变，合并行在组首行位置。
        self.assertEqual(new[:2], list(M.PANEL_LINES_NUMERIC[:2]))
        self.assertEqual(new[2], M.MERGED_LINE)
        self.assertEqual(new[3:], list(M.PANEL_LINES_NUMERIC[4:]))

    def test_panel_merge_follows_the_data_conditions(self):
        rows = self.out["leader"][M.LEADER]
        self.assertEqual([], M.merge_problems(rows))
        first, second = (rows[i] for i in M.MERGE_ROWS)
        differing = {c for c, (a, b) in enumerate(zip(first, second)) if a != b}
        self.assertEqual({45, 46, 47}, differing)                        # 只差效果 kind / 对象 / 属性组
        self.assertEqual(("0", "2", "600000", "600000", "Green", "0"),
                         (first[3], first[4], first[7], first[8], first[9], first[25]))
        rendered = wf_describe.describe_rows([first, second], "leader_ability")
        self.assertEqual(["风·编成≥6 时: 赋予全队(风) 2号位技能槽 50%", "风·编成≥6 时: 自身 Fever时间延长 50%"], rendered)
        # 其余行都不与它们同条件（不漏并）；FeverFrame 两行本就在同一行文案里。
        self.assertEqual([1, 2], [i for i, row in enumerate(rows) if M.same_condition(row, first)])
        self.assertTrue(M.same_condition(rows[3], rows[4]))
        # 数据条件不同就拒绝合并（负对照）。
        broken = deepcopy(rows)
        broken[2][4] = "0"
        self.assertTrue(M.merge_problems(broken))

    def test_resonance_omission_basis(self):
        """共鸣省略只在「固有状态全部获取来源带同一共鸣」时成立；本角色两个状态都有不带共鸣的来源，
        队长面板各行数据也不依赖任何固有状态 ⇒ 一处「风属性共鸣时，」都不省略（合并只省重复的一处）。"""
        self.assertEqual({}, M.RESONANCE_OMISSION)
        self.assertEqual({"1499900", "1499901"}, set(M.STATES_NOT_OMITTED))
        for i, row in enumerate(self.out["leader"][M.LEADER]):
            self.assertEqual([], [row[c] for c in LEADER_STATE_COLS if row[c] not in ("", "(None)", "0")], i)
        numeric = "\n".join(M.PANEL_LINES_NUMERIC)
        new = self.out["cas"][M.CAS_LEADER][0][0]
        self.assertEqual(numeric.count("风属性共鸣时，") - 1, new.count("风属性共鸣时，"))

    def test_panel_passes_check_merge(self):
        """仓库内校验器 wf_panel_merge_check（硬依赖）。原文没有「X属性共鸣时：」，无需口径 3 规范化。"""
        check = check_merge
        self.assertFalse(any("共鸣时：" in line for line in M.PANEL_LINES_NUMERIC))
        numeric = "\n".join(M.PANEL_LINES_NUMERIC)
        new = self.out["cas"][M.CAS_LEADER][0][0]
        result = check(numeric, new, [])
        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual([], result["warnings"])
        self.assertEqual({1: 1, 2: 2, 3: 3, 4: 3, 5: 4, 6: 5}, result["columns"][0]["mapping"])
        # 负对照：改数值、未授权删共鸣都会被拒。
        self.assertFalse(check(numeric, new.replace("＋50%，", "＋55%，"), [])["ok"])
        self.assertFalse(check(numeric, new.replace("风属性共鸣时，FEVER模式中", "FEVER模式中"), [])["ok"])

    def test_leader_rows_pass_client_gates(self):
        for i, row in enumerate(self.out["leader"][M.LEADER]):
            self.assertEqual([], client_legality_problems("leader_ability", row), i)
            self.assertEqual([], declared_block_field_problems("leader_ability", row), i)
            self.assertEqual([], invoke_skill_string_problems(row, set(), "leader_ability"), i)
            self.assertEqual([], ability_element_column_problems("leader_ability", row, M.ELEMENT), i)
            self.assertEqual([], required_client_capabilities("leader_ability", row), i)
            self.assertEqual([], M.row_problems(row), i)

    # ------------------------------------------------------------ 技能强化文案规范（R1–R4）

    def test_skill_flag_entry_texts(self):
        """旗号 1 条目官方格式、点名『盛夏咆哮』、不写数字；CAS 不带共鸣前缀，面板第 2 行 = 图标 +「风属性共鸣时，」+ CAS；
        能力1 面板第 1 / 3 行逐字。"""
        entry = ("强化『盛夏咆哮』：追加全队贯穿与最大速度固定效果，对最近的敌人追加能力伤害，"
                 "并强制赋予自身无法消除的「假日」")
        self.assertEqual([[entry]], self.out["cas"][M.CAS_SWITCH])
        self.assertEqual("风属性共鸣时，强化技能『盛夏咆哮』：追加效果与能力伤害，并强制赋予自身无法消除的「假日」",
                         self.old("cas", M.CAS_SWITCH)[0][0])
        old = self.old("cas", M.CAS_A1)[0][0].split("\n")
        new = self.out["cas"][M.CAS_A1][0][0].split("\n")
        self.assertEqual(3, len(new))
        self.assertEqual((old[0], old[2]), (new[0], new[2]))
        self.assertEqual(M.MAIN_ICON + "风属性共鸣时，" + entry, new[1])
        self.assertEqual(M.MAIN_ICON + self.old("cas", M.CAS_SWITCH)[0][0], old[1], "live 面板行 = 图标 + live 条目")
        self.assertTrue(all(line.startswith(M.MAIN_ICON) for line in new))
        for text in (entry, new[1]):
            self.assertEqual([], KL.panel_problems(text.replace(M.MAIN_ICON, ""), skill_flag=True))
            for word in ("强化技能", "强化自身技能", "不受此限", "强化后"):
                self.assertNotIn(word, text)
        self.assertEqual([], M.text_problems({k: v[0][0] for k, v in self.out["cas"].items()}))
        # 删判定反例：CAS 与面板不一致 / 泛称 / 带数字。
        texts = {k: v[0][0] for k, v in self.out["cas"].items()}
        self.assertTrue(any("panel entry of" in p for p in M.text_problems(dict(texts, **{M.CAS_SWITCH: entry + "效果"}))))
        self.assertTrue(any("must read" in p for p in M.text_problems(
            dict(texts, **{M.CAS_SWITCH: entry.replace("强化『盛夏咆哮』", "强化技能『盛夏咆哮』")}))))
        self.assertTrue(any("numbers" in p for p in M.text_problems(
            dict(texts, **{M.CAS_SWITCH: entry.replace("能力伤害", "30倍能力伤害")}))))

    def test_enhancement_basis_follows_the_data(self):
        """能力1 #1 = I536（前置 风 6 人共鸣，c70 = 条目键）；两档技能树唯一的旗号 1 分支：关支空，开支 = 33 贯穿 +
        82 最大速度固定 + 自身「假日」强制付与 + 最近敌人追加一击。删判定反例 ⇒ revise() 拒绝。"""
        ability1 = self.old("ability", M.ABILITY1_KEY)
        trees = {program: self.old("dsl", program) for program in M.PROGRAMS.values()}
        self.assertEqual([], M.enhancement_basis_problems(ability1, trees))
        rendered = wf_describe.describe_rows(ability1, "ability")
        self.assertEqual("风·编成≥6 时: 自身 切换技能形态[change_skill_white_tiger_summer]", rendered[1])
        self.assertEqual({}, self.out["ability"], "数据行只读")
        self.assertEqual({}, self.out["dsl"], "技能树只读")

        def flag(tree):
            return [a for a in M._commands(tree) if a[0] == "ConditionalsChangeSkillFlag"][0]

        def piercing_gone(data):
            for program in M.PROGRAMS.values():
                branch = flag(data["dsl"][program])[2][1]
                branch[:] = [c for c in branch if not (c[1][0] == "FindAllSubjects" and c[1][2] == 33)]

        def off_body(data):
            for program in M.PROGRAMS.values():
                flag(data["dsl"][program])[3][1].append(["Command", ["DoNothing"]])

        def holiday_not_forced(data):
            for program in M.PROGRAMS.values():
                unique = [c for c in M._commands(flag(data["dsl"][program])[2]) if c[0] == "CreateCondition"
                          and c[2][0][0] == "ACUnique"][0]
                unique[12] = False

        def resonance_gone(data):
            data["ability"][M.ABILITY1_KEY][1][6] = "0"

        for mutate in (piercing_gone, off_body, holiday_not_forced, resonance_gone):
            data = deepcopy(self.inputs)
            mutate(data)
            self.assertTrue(M.enhancement_basis_problems(
                data["ability"][M.ABILITY1_KEY], {p: data["dsl"][p] for p in M.PROGRAMS.values()}), mutate.__name__)
            patch = {(kind, key): M.digest(data[kind][key]) for kind, key in M.BEFORE}
            with mock.patch.dict(M.BEFORE, patch), self.assertRaisesRegex(ValueError, "enhancement basis"):
                M.revise(self.read_from(data))

    # ------------------------------------------------------------ 失败关闭

    def test_live_drift_is_rejected_and_inputs_are_not_mutated(self):
        original = deepcopy(self.inputs)
        out = M.revise(self.read_from(self.inputs))
        self.assertEqual(original, self.inputs)
        out["leader"][M.LEADER][3][49] = "mutated"
        out["cas"][M.CAS_LEADER][0][0] = "mutated"
        self.assertEqual(original, self.inputs)
        for kind, key in M.BEFORE:
            drifted = deepcopy(self.inputs)
            if kind == "dsl":
                drifted[kind][key][10] = 4
            else:
                drifted[kind][key][0][-1] += "x"
            with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
                M.revise(self.read_from(drifted))
            missing = deepcopy(self.inputs)
            missing[kind][key] = None
            with self.assertRaises(ValueError):
                M.revise(self.read_from(missing))

    def test_already_revised_live_is_not_revised_twice(self):
        live = deepcopy(self.inputs)
        live["leader"].update(deepcopy(self.out["leader"]))
        live["cas"].update(deepcopy(self.out["cas"]))
        with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
            M.revise(self.read_from(live))
        with self.assertRaisesRegex(ValueError, "preimage"):
            M.leader_rows(self.out["leader"][M.LEADER])
        with self.assertRaisesRegex(ValueError, "panel text layout"):
            M.leader_text(self.out["cas"][M.CAS_LEADER])
        with self.assertRaisesRegex(ValueError, "panel text layout"):
            M.leader_text([["\n".join(M.PANEL_LINES_NUMERIC)]])          # 数值稿同样拒绝（不重复套用）
        with self.assertRaisesRegex(ValueError, "unexpected text"):
            M.switch_text(self.out["cas"][M.CAS_SWITCH])
        with self.assertRaisesRegex(ValueError, "panel text layout"):
            M.a1_text(self.out["cas"][M.CAS_A1])

    def test_row_locators_are_content_based(self):
        rows = deepcopy(self.old("leader", M.LEADER))
        swapped = rows[:3] + [rows[4], rows[3]] + rows[5:]
        with self.assertRaises(ValueError):
            M.leader_rows(swapped)
        drifted = deepcopy(rows)
        drifted[3][32] = "10"                                           # 成长被加了次数上限
        with self.assertRaises(ValueError):
            M.leader_rows(drifted)

    # ------------------------------------------------------------ 候选

    @unittest.skipUnless((WORKSPACE / "package/manifest.json").is_file()
                         and (ROOT / "mod-tools/profiles.json").is_file(),
                         "local candidate workspace required")
    def test_candidate_matches_live_before_and_revise_output_after_writeback(self):
        from wf_character_revision import RevisionCandidate
        manifest_path = WORKSPACE / "package/manifest.json"
        before = manifest_path.read_bytes()
        current = json.loads(before)["package_version"]
        target = M.PACKAGE_VERSION[M.PACKAGES[0]]
        if as_tuple(current) > as_tuple(target):
            self.skipTest(f"candidate advanced past batch 3 ({current})")
        candidate = RevisionCandidate(ROOT, WORKSPACE, character_id=M.CID, code_name=M.CODE,
                                      snapshot_key="revision_20260927c", package_version=target,
                                      reviewed_input_drift=M.REVIEWED_DRIFT,
                                      baseline_factory=lambda *a, **k: None)
        want = self.out if current == target else self.inputs
        if current != target:
            self.assertLess(as_tuple(current), as_tuple(target))
        leader = X.unpack(candidate.read("common", "master/ability/leader_ability.orderedmap"))
        self.assertEqual(X.csv_read(leader[M.LEADER]), want["leader"][M.LEADER])
        cas = X.unpack(candidate.read("common", "master/string/custom_ability_string.orderedmap"))
        self.assertEqual(X.csv_read(cas[M.CAS_LEADER]), want["cas"][M.CAS_LEADER])
        self.assertEqual(X.csv_read(cas[M.CAS_SWITCH]), want["cas"][M.CAS_SWITCH])
        if current == target:
            self.assertEqual(X.csv_read(cas[M.CAS_A1]), self.out["cas"][M.CAS_A1])
        else:   # 既有漂移（notes.candidate_preexisting_drift）：候选能力1 面板是加主位图标前的文案
            self.assertEqual(X.csv_read(cas[M.CAS_A1])[0][0],
                             self.inputs["cas"][M.CAS_A1][0][0].replace(M.MAIN_ICON, ""))
        self.assertEqual(before, manifest_path.read_bytes())


if __name__ == "__main__":
    unittest.main()
