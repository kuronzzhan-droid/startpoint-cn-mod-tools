# -*- coding: utf-8 -*-
"""碧安卡「女王的开放课堂」119989 ``lady_summoner_campus`` 2026-09-27 平衡第二批。

请求 (2) 吐息自充 50% → 20%；请求 (3) 能力5 去主位限制、能力1 开局自充 75% → 50%。

fixture = live 输入快照（``fixtures/balance_20260927b_bianca.json``，stage_batch.make_read(live_only=True)），
驱动 ``revise()``：只改能力1 #0/#2 的 c51/c52、能力5 的 c1 与两条面板覆盖，其余行/列/面板行逐字保留、
BEFORE 漂移拒绝、不改输入、对自身输出重跑拒绝、合法性门禁为空、面板规则（主位图标与 c1 同源）、
生成器（wf_bianca_dragon_abilities + wf_bianca_dragon_bridge + wf_campus_panel_text，经 wf_bianca_dragon.assemble）
输出 == revise() 输出、候选干跑。本单元不改 DSL（``out["dsl"] == {}``），故无 AMF3 往返/DSL 门禁项。
官方基线装配对比需要 ``.cdn/cn`` 与 profiles（缺时跳过）；候选在 gitignore 的 work/ 下（缺时跳过）。
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

pass  # Imports resolve from this checkout/package, not external source copies.
pass  # Imports resolve from this checkout/package, not external source copies.

import wf_balance_20260927b_bianca as M  # noqa: E402
import wf_bianca_dragon as build  # noqa: E402
import wf_bianca_dragon_abilities as kit  # noqa: E402
import wf_bianca_dragon_bridge as bridge  # noqa: E402
import wf_campus_panel_text as panel  # noqa: E402
import wf_client_legality as L  # noqa: E402
import wf_describe as D  # noqa: E402
import wf_featured_main_ability as featured  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
from test_bianca_dragon_descriptions import CapturedCandidate, description_sources  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927b_bianca.json'
WORKSPACE = ROOT / "work/character_packs" / M.PACKAGES[0]
ABILITY = "master/ability/ability.orderedmap"
FLAT = "master/string/custom_ability_string.orderedmap"
#: 候选 campus-bianca-20260911 manifest 现有 required_capabilities（[]）+ 本批补登。
CANDIDATE_CAPABILITIES = set(M.CAPABILITIES)
DESCRIBE_A1_BEFORE = (
    "自身 技能槽 75%",
    "火·编成≥6 时: 自身 切换技能形态[change_skill_lady_summoner_campus_dragon]",
    "火·编成≥6 时: 状态固有≥1[固有11998902] → 自身 技能槽 50%",
    "火·编成≥6 时: 状态固有≥1[固有11998902] → 赋予队长 状态攻击力 200%(15秒)×1次",
)
DESCRIBE_A1_AFTER = (
    "自身 技能槽 50%",
    DESCRIBE_A1_BEFORE[1],
    "火·编成≥6 时: 状态固有≥1[固有11998902] → 自身 技能槽 20%",
    DESCRIBE_A1_BEFORE[3],
)
DESCRIBE_A5 = ("火·编成≥6 时: 技能发动≥1 → 自身 Fever槽增减(上限比例) 15%",)


def load_raw() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def load_fixture() -> dict:
    return {kind: value for kind, value in load_raw().items() if not kind.startswith("_")}


def reader(data: dict):
    def read(kind, key):
        return data[kind][key]
    return read


def _baseline_available() -> bool:
    return (ROOT / ".cdn/cn").is_dir() and (ROOT / "mod-tools/profiles.json").is_file()


class ReviseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))
        cls.old = cls.live["ability"][M.ABILITY_KEY]
        cls.new = cls.out["ability"][M.ABILITY_KEY]
        cls.old5 = cls.live["ability"][M.A5_KEY]
        cls.new5 = cls.out["ability"][M.A5_KEY]
        cls.old_panel = cls.live["cas"][M.CAS_A1][0][0]
        cls.new_panel = cls.out["cas"][M.CAS_A1][0][0]
        cls.old_panel5 = cls.live["cas"][M.CAS_A5][0][0]
        cls.new_panel5 = cls.out["cas"][M.CAS_A5][0][0]

    def test_fixture_is_the_reviewed_baseline(self):
        for (kind, key), want in M.BEFORE.items():
            self.assertEqual(M.digest(self.live[kind][key]), want, f"{kind}:{key}")
        self.assertEqual({(kind, key) for kind, keys in self.live.items() for key in keys},
                         set(M.BEFORE))
        self.assertEqual(set(M.BEFORE), {("ability", "1199891"), ("ability", "1199895"),
                                         ("cas", "desc_override_lady_summoner_campus_1"),
                                         ("cas", "desc_override_lady_summoner_campus_5")})

    def test_module_contract_exports(self):
        self.assertEqual((M.CID, M.CODE), (kit.CID, kit.CODE))
        self.assertEqual((M.CID, M.CODE), (bridge.CID, bridge.CODE))
        self.assertEqual(M.BREATH_UID, str(bridge.BREATH_UNIQUE_ID))
        self.assertEqual(M.CHANGE_SKILL_STRING, bridge.CHANGE_SKILL_STRING_ID)
        self.assertEqual(M.MAIN_ICON, featured.MAIN)
        self.assertEqual(M.PACKAGES, ["campus-bianca-20260911"])
        self.assertEqual(M.PACKAGE_VERSION, {"campus-bianca-20260911": "0.1.1"})   # 候选现值 0.1.0，只升不降
        self.assertEqual(M.CAPABILITIES, ["kyubi-fever-ratio-v1", "panel-description-override-v2"])
        self.assertEqual(M.REVIEWED_DRIFT, {})
        self.assertFalse(hasattr(M, "UNITS"))                                        # 单角色模块

    def test_only_changed_keys_are_returned(self):
        out = self.out
        self.assertEqual(set(out["ability"]), {M.ABILITY_KEY, M.A5_KEY})
        self.assertEqual(set(out["cas"]), {M.CAS_A1, M.CAS_A5})
        for kind in ("leader", "text", "table", "action", "dsl", "server_text"):
            self.assertEqual(out[kind], {}, kind)
        self.assertEqual(out["new_programs"], [])
        json.dumps(out["notes"], ensure_ascii=False)
        for key in out["ability"]:
            self.assertTrue(key.startswith(M.CID), key)
        for key in out["cas"]:                                                       # RevisionCandidate 面板覆盖命名空间
            self.assertTrue(key.startswith("desc_override_" + M.CODE), key)

    # ------------------------------------------------------------ 能力1

    def test_ability1_only_c51_c52_of_rows_0_and_2_change(self):
        self.assertEqual((len(self.old), len(self.new)), (4, 4))
        self.assertEqual([i for i in range(4) if self.old[i] != self.new[i]], [0, 2])
        for i in (0, 2):
            self.assertEqual(len(self.new[i]), 126)
            self.assertEqual([c for c in range(126) if self.old[i][c] != self.new[i][c]], [51, 52], i)
        # 请求 (3)：战斗开始自身技能槽 75% → 50%
        self.assertEqual(self.old[0][51:53], ["75000", "75000"])
        self.assertEqual(self.new[0][51:53], ["50000", "50000"])
        # 请求 (2)：获得幼龙吐息自身技能槽 50% → 20%
        self.assertEqual(self.old[2][51:53], ["50000", "50000"])
        self.assertEqual(self.new[2][51:53], ["20000", "20000"])

    def test_ability1_untouched_rows_are_verbatim_and_still_main_only(self):
        for i in (1, 3):
            self.assertEqual(self.new[i], self.old[i], i)
        self.assertEqual((self.new[1][47], self.new[1][70]), ("536", M.CHANGE_SKILL_STRING))
        self.assertEqual((self.new[3][47], self.new[3][48], self.new[3][51], self.new[3][57]),
                         ("0", "2", "200000", "90000000"))                            # 队长攻击力 200% 15 秒
        self.assertEqual({row[1] for row in self.new}, {"false"})                    # 能力1 仍是整键主位

    def test_opening_row_keeps_its_unconditional_self_target(self):
        """作者只改开局数值：无触发（T0）、无前置、自身目标、I211 逐格不动。"""
        row = self.new[0]
        self.assertEqual((row[6], row[13], row[20], row[27]), ("0", "0", "0", "0"))
        self.assertEqual((row[47], row[48]), ("211", "0"))
        self.assertEqual(row[:5], [M.CODE + "_1", "false", "attack_red", "0", ""])

    def test_breath_row_trigger_gate_target_limit_and_cooldown_are_kept(self):
        """作者只改数值：火共鸣、触发 185 吐息、自身目标、不限次、CT 0 逐格不动。"""
        row = self.new[2]
        self.assertEqual((row[6], row[9], row[10], row[11]), ("2", "600000", "600000", "Red"))
        self.assertEqual((row[27], row[28], row[37]), ("185", "0", M.BREATH_UID))
        self.assertEqual((row[30], row[31], row[34], row[35]), ("100000", "100000", "(None)", "0"))
        self.assertEqual((row[47], row[48]), ("211", "0"))
        self.assertEqual(row[:5], [M.CODE + "_1", "false", "attack_red", "0", ""])   # 主位限制不变

    # ------------------------------------------------------------ 能力5

    def test_ability5_only_column_one_changes(self):
        self.assertEqual((len(self.old5), len(self.new5)), (1, 1))
        old, new = self.old5[0], self.new5[0]
        self.assertEqual(len(new), 126)
        self.assertEqual([c for c in range(126) if old[c] != new[c]], [1])
        self.assertEqual((old[1], new[1]), ("false", "true"))                        # 请求 (3)：去主位限制

    def test_ability5_has_no_main_gate_and_keeps_trigger_gate_and_value(self):
        row = self.new5[0]
        for col in M.PRE_KIND_COLS:                                                   # 行内无 202/203 仅主位/副位门
            self.assertNotIn(row[col], ("202", "203"), col)
        self.assertEqual(row[:5], [M.CODE + "_5", "true", "attack_red", "0", ""])
        self.assertEqual((row[6], row[9], row[10], row[11]), ("2", "600000", "600000", "Red"))
        self.assertEqual((row[27], row[28], row[29], row[34], row[35]), ("23", "7", "Red", "(None)", "0"))
        self.assertEqual((row[47], row[51], row[52]), ("724", "15000", "15000"))

    def test_main_slot_distribution_after_revision(self):
        self.assertEqual({row[1] for row in self.new}, {"false"})
        self.assertEqual({row[1] for row in self.new5}, {"true"})

    def test_auto_describe(self):
        self.assertEqual(tuple(D.describe_line(r, "ability") for r in self.old), DESCRIBE_A1_BEFORE)
        self.assertEqual(tuple(D.describe_line(r, "ability") for r in self.new), DESCRIBE_A1_AFTER)
        self.assertEqual(tuple(D.describe_line(r, "ability") for r in self.old5), DESCRIBE_A5)
        self.assertEqual(tuple(D.describe_line(r, "ability") for r in self.new5), DESCRIBE_A5)

    # ------------------------------------------------------------ 面板

    def test_panel_a1_changes_only_the_two_charge_values(self):
        old, new = self.old_panel.split("\n"), self.new_panel.split("\n")
        self.assertEqual(tuple(old), M.PANEL_A1_BEFORE)
        self.assertEqual(tuple(new), M.PANEL_A1_AFTER)
        self.assertEqual(new[1], old[1])
        self.assertEqual(new[0], old[0].replace("自身技能槽+75%", "自身技能槽+50%"))
        self.assertEqual(new[2], old[2].replace("自身技能槽+50%", "自身技能槽+20%"))
        self.assertEqual(new[0], " <icon id='main'>  战斗开始时：自身技能槽+50%。")
        self.assertEqual(new[2], " <icon id='main'>  火属性共鸣时，每次获得「幼龙吐息」，自身技能槽+20%，"
                                 "赋予队长攻击力提升200%效果，持续15秒。")
        self.assertNotIn("+75%", self.new_panel)
        self.assertEqual(len(self.out["cas"][M.CAS_A1]), 1)
        self.assertEqual(len(self.out["cas"][M.CAS_A1][0]), 1)

    def test_panel_a5_drops_only_the_main_icon(self):
        self.assertEqual(self.old_panel5, " <icon id='main'>  火属性共鸣时，火属性角色发动技能：Fever槽+15%。")
        self.assertEqual(self.new_panel5, "火属性共鸣时，火属性角色发动技能：Fever槽+15%。")
        self.assertEqual(self.new_panel5, self.old_panel5.replace(M.MAIN_ICON, "", 1))
        self.assertNotIn("<icon id='main'>", self.new_panel5)
        self.assertEqual(self.out["cas"][M.CAS_A5], [[self.new_panel5]])

    def test_panels_agree_with_the_data(self):
        lines = self.new_panel.split("\n")
        self.assertEqual(int(self.new[0][51]) // 1000, 50)
        self.assertIn(f"自身技能槽+{int(self.new[0][51]) // 1000}%", lines[0])
        self.assertIn("战斗开始时", lines[0])
        self.assertEqual(int(self.new[2][51]) // 1000, 20)
        self.assertIn(f"自身技能槽+{int(self.new[2][51]) // 1000}%", lines[2])
        self.assertIn("每次获得「幼龙吐息」", lines[2])                               # 触发 185 + 11998902
        self.assertIn("队长攻击力提升200%效果，持续15秒", lines[2])                   # 同触发 #3 不变
        self.assertIn(f"Fever槽+{int(self.new5[0][51]) // 1000}%", self.new_panel5)
        # 主位图标与 c1 同源：整键 c1=false ⇔ 每行带图标。
        for rows, text in ((self.new, self.new_panel), (self.new5, self.new_panel5)):
            main = {row[1] for row in rows} == {"false"}
            self.assertEqual([line.startswith(M.MAIN_ICON) for line in text.split("\n")],
                             [main] * len(text.split("\n")))

    def test_panel_texts_obey_the_project_rules(self):
        for text in (self.new_panel, self.new_panel5):
            self.assertNotIn("／", text)
            self.assertNotIn("觉醒后", text)                                          # 单一数值，无「(觉醒后X%)」
            for line in text.split("\n"):
                self.assertEqual(KL.panel_problems(line.replace(M.MAIN_ICON, "")), [], line)
        a1 = self.new_panel.split("\n")
        for changed in (a1[0], a1[2], self.new_panel5):                              # 改动行各只有一个槽位数值
            self.assertEqual(changed.count("槽+"), 1, changed)
        for line in self.new_panel.split("\n"):
            self.assertTrue(line.startswith(M.MAIN_ICON), line)                      # 主位限制槽每行带 Ⓜ
        self.assertNotIn("<icon id='main'>", self.new_panel5)                        # 不限主位槽不带 Ⓜ
        self.assertTrue(self.new_panel.split("\n")[2].replace(M.MAIN_ICON, "").startswith("火属性共鸣时，"))
        self.assertTrue(self.new_panel5.startswith("火属性共鸣时，"))
        for key in (M.CAS_A1, M.CAS_A5):
            self.assertEqual(L.panel_override_capability(key), "panel-description-override-v2")
            self.assertIn(L.panel_override_capability(key), M.CAPABILITIES)

    def test_native_legality_gates_are_empty(self):
        cas_keys = {M.CHANGE_SKILL_STRING}
        for key in (M.ABILITY_KEY, M.A5_KEY):
            for index, row in enumerate(self.out["ability"][key]):
                label = f"ability:{key}#{index}"
                self.assertEqual(L.client_legality_problems("ability", row), [], label)
                self.assertEqual(L.declared_block_field_problems("ability", row), [], label)
                self.assertEqual(L.invoke_skill_string_problems(row, cas_keys, kind="ability"), [], label)
                self.assertEqual(L.ability_element_column_problems("ability", row, M.ELEMENT), [], label)
                self.assertEqual(KL.row_problems("ability", row, M.ELEMENT), {}, label)
                self.assertLessEqual(set(L.required_client_capabilities("ability", row)),
                                     CANDIDATE_CAPABILITIES, label)
        self.assertEqual(L.required_client_capabilities("ability", self.new5[0]), ["kyubi-fever-ratio-v1"])

    # ------------------------------------------------------------ fail closed

    def test_input_is_not_mutated_and_output_is_detached(self):
        data = deepcopy(self.live)
        out = M.revise(reader(data))
        self.assertEqual(data, self.live)
        out["ability"][M.ABILITY_KEY][2][51] = "mutated"
        out["ability"][M.ABILITY_KEY][0][0] = "mutated"
        out["ability"][M.A5_KEY][0][1] = "mutated"
        out["cas"][M.CAS_A1][0][0] = "mutated"
        out["cas"][M.CAS_A5][0][0] = "mutated"
        self.assertEqual(data, self.live)

    def test_baseline_drift_is_rejected(self):
        for kind, key in M.BEFORE:
            data = deepcopy(self.live)
            if kind == "cas":
                data[kind][key][0][0] += "。"
            else:
                data[kind][key][0][35] = "60"
            with self.assertRaisesRegex(ValueError, "unreviewed live baseline", msg=key):
                M.revise(reader(data))
            data = deepcopy(self.live)
            data[kind][key] = data[kind][key] + [list(data[kind][key][0])]
            with self.assertRaises(ValueError, msg=key):
                M.revise(reader(data))

    def test_revise_is_not_reapplicable_to_its_own_output(self):
        """重跑在已改的 live 上必须拒绝（fail closed），逐键验证。"""
        for kind in ("ability", "cas"):
            for key, value in self.out[kind].items():
                data = deepcopy(self.live)
                data[kind][key] = deepcopy(value)
                with self.assertRaisesRegex(ValueError, "unreviewed live baseline", msg=key):
                    M.revise(reader(data))
        for function, value in ((M.ability1_rows, self.new), (M.ability5_rows, self.new5),
                                (M.panel_a1, self.out["cas"][M.CAS_A1]),
                                (M.panel_a5, self.out["cas"][M.CAS_A5])):
            with self.assertRaises(ValueError, msg=function.__name__):
                function(deepcopy(value))

    def test_row_locator_is_content_based(self):
        """绕过 BEFORE 直接调纯函数：目标行形状不对也要拒绝。"""
        mutations = (
            lambda r: r.__setitem__(slice(2, 4), [r[3], r[2]]),     # 行序换了
            lambda r: r[0].__setitem__(51, "60000"),                # 开局数值漂移
            lambda r: r[0].__setitem__(48, "5"),                    # 开局目标换成全队
            lambda r: r[2].__setitem__(51, "30000"),                # 吐息数值漂移
            lambda r: r[2].__setitem__(35, "600"),                  # 已有 CT
            lambda r: r[2].__setitem__(34, "5"),                    # 已有限次
            lambda r: r[2].__setitem__(37, "11998901"),             # 换成「幼龙回应」
            lambda r: r[2].__setitem__(48, "5"),                    # 目标换成全队
            lambda r: r[2].__setitem__(80, "x"),                    # 多出非空列
            lambda r: r[3].__setitem__(51, "100000"),               # 同键其他行漂移
            lambda r: r[1].__setitem__(1, "true"),                  # 能力1 已有行不限主位
            lambda r: r[0].pop(),                                   # 列宽不对
            lambda r: r.pop(),                                      # 记录条数不对
        )
        for n, mutate in enumerate(mutations):
            rows = deepcopy(self.old)
            mutate(rows)
            with self.assertRaises(ValueError, msg=str(n)):
                M.ability1_rows(rows)
        mutations5 = (
            lambda r: r[0].__setitem__(1, "true"),                  # 已去主位
            lambda r: r[0].__setitem__(20, "202"),                  # 额外的仅主位门
            lambda r: r[0].__setitem__(51, "20000"),                # 数值漂移
            lambda r: r[0].__setitem__(47, "213"),                  # 换成 Fever 点数
            lambda r: r[0].__setitem__(28, "0"),                    # 触发者换成自身
            lambda r: r[0].__setitem__(90, "x"),                    # 多出非空列
            lambda r: r[0].pop(),                                   # 列宽不对
            lambda r: r.append(list(r[0])),                         # 记录条数不对
        )
        for n, mutate in enumerate(mutations5):
            rows = deepcopy(self.old5)
            mutate(rows)
            with self.assertRaises(ValueError, msg=f"a5 {n}"):
                M.ability5_rows(rows)
        for bad in (self.old_panel.replace("+75%", "+50%"),
                    self.old_panel.replace("自身技能槽+50%", "自身技能槽+20%"),
                    self.old_panel + "\n" + M.MAIN_ICON + "多一行。",
                    self.old_panel.replace(M.MAIN_ICON, "")):
            with self.assertRaises(ValueError):
                M.panel_a1([[bad]])
        with self.assertRaises(ValueError):
            M.panel_a1([[self.old_panel, ""]])
        for bad in (self.old_panel5.replace("+15%", "+20%"),
                    self.old_panel5.replace(M.MAIN_ICON, ""),
                    self.old_panel5 + "\n" + M.MAIN_ICON + "多一行。"):
            with self.assertRaises(ValueError):
                M.panel_a5([[bad]])
        with self.assertRaises(ValueError):
            M.panel_a5([[self.old_panel5], [self.old_panel5]])


class GeneratorSyncTests(unittest.TestCase):
    """生成器重跑不能把 75% / 50% / 能力5 主位带回来：kit、桥与面板源码常量已同步。"""

    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))

    def _kit(self, source):
        rows = kit.ability_rows(source)
        return {M.ABILITY_KEY: rows[M.ABILITY_KEY] + bridge.a1_enhancement_rows(source),
                M.A5_KEY: rows[M.A5_KEY]}

    def test_generator_constants(self):
        source, _ = description_sources()
        opening = kit.ability_rows(source)[M.ABILITY_KEY][0]
        self.assertEqual(opening[51:53], ["50000", "50000"])
        flag, charge, attack = bridge.a1_enhancement_rows(source)
        self.assertEqual(charge[51:53], ["20000", "20000"])
        self.assertEqual(kit.MAIN_ONLY_SLOTS, (1, 3))
        self.assertEqual(kit.metadata()["main_only_slots"], [1, 3])

    def test_generator_main_slots_follow_main_only_slots(self):
        source, _ = description_sources()
        rows = kit.ability_rows(source)
        texts = panel.panel_descriptions(M.CID)
        for slot in range(1, 7):
            main = slot in kit.MAIN_ONLY_SLOTS
            self.assertEqual({row[1] for row in rows[f"{M.CID}{slot}"]}, {"false" if main else "true"}, slot)
            self.assertEqual(all(line.startswith(M.MAIN_ICON) for line in texts[f"a{slot}"].split("\n")),
                             main, slot)
            self.assertEqual("<icon id='main'>" in texts[f"a{slot}"], main, slot)

    def test_generator_equals_revise_output_with_embedded_donors(self):
        source, _ = description_sources()
        self.assertEqual(self._kit(source), self.out["ability"])

    @unittest.skipUnless(_baseline_available(), "需要 .cdn/cn 官方基线与 profiles.json")
    def test_generator_equals_revise_output_with_official_baseline(self):
        import wf_campus_bianca as campus
        source = campus.Builder().official_rows(ABILITY)
        self.assertEqual(self._kit(source), self.out["ability"])

    def _a1_allowed(self) -> tuple[str, str]:
        """能力1 面板：本批输出，或技能强化文案（wf_balance_20260927c_panels R2：第2行强化条目改官方格式）作用于本批输出
        之后的现稿；第三轮的改前 == 本批输出，R2 的一致性由 test_balance_20260927c_panels 断言。"""
        import wf_balance_20260927c_panels as P3
        a1 = self.out["cas"][M.CAS_A1][0][0]
        third = P3.PANELS_BY_CAS[M.CAS_A1]
        self.assertEqual("\n".join(third["before"]), a1)
        return a1, "\n".join(third["after"])

    def test_panel_generator_equals_revise_output(self):
        texts = panel.panel_descriptions(M.CID)
        allowed = self._a1_allowed()
        self.assertIn(texts["a1"], allowed)
        self.assertEqual(texts["a5"], self.out["cas"][M.CAS_A5][0][0])
        self.assertIn(tuple(texts["a1"].split("\n")), (M.PANEL_A1_AFTER, tuple(allowed[1].split("\n"))))
        self.assertEqual(tuple(texts["a5"].split("\n")), M.PANEL_A5_AFTER)

    def test_full_assemble_splices_the_revised_abilities_and_panels(self):
        """真实装配路径（wf_bianca_dragon.assemble），只替换磁盘边界与美术。"""
        candidate = CapturedCandidate()
        with patch.object(build, "Candidate", return_value=candidate), \
                patch.object(build.pixels, "build_dragon_assets", return_value=({}, {})), \
                patch.object(build.skill, "build_effect_assets", return_value={}):
            tables = build.assemble(Path("unused-repo"), Path("unused-candidate"))
        for key in (M.ABILITY_KEY, M.A5_KEY):
            self.assertEqual(tables[ABILITY][key], self.out["ability"][key], key)
        self.assertIn(tables[FLAT][M.CAS_A1], [[[text]] for text in self._a1_allowed()])
        self.assertEqual(tables[FLAT][M.CAS_A5], self.out["cas"][M.CAS_A5], M.CAS_A5)


@unittest.skipUnless((WORKSPACE / "package/manifest.json").is_file()
                     and (ROOT / "mod-tools/profiles.json").is_file(), "local candidate workspace required")
class CandidateTests(unittest.TestCase):
    def test_candidate_accepts_the_revision_dry(self):
        """候选文件与 manifest 一致（REVIEWED_DRIFT 为空）；dry-run 回写不落盘。回写后改为逐项比对。"""
        import wf_share_update_codec as X
        from wf_character_revision import RevisionCandidate
        out = M.revise(reader(load_fixture()))
        manifest = WORKSPACE / "package/manifest.json"
        before = manifest.read_bytes()
        current = json.loads(before)
        # 第三轮面板合并（wf_balance_20260927c_panels）暂存回写后，候选再升一版；本批改过的键不受其影响。
        import wf_balance_20260927c_panels as P3
        want = P3.staged_version(current, M.PACKAGES[0]) or M.PACKAGE_VERSION[M.PACKAGES[0]]
        self.assertGreaterEqual(tuple(map(int, want.split("."))),
                                tuple(map(int, current["package_version"].split("."))))
        candidate = RevisionCandidate(ROOT, WORKSPACE, character_id=M.CID, code_name=M.CODE,
                                      snapshot_key="revision_20260927b",
                                      package_version=M.PACKAGE_VERSION[M.PACKAGES[0]],
                                      baseline_factory=lambda *a, **k: None,
                                      reviewed_input_drift=M.REVIEWED_DRIFT)
        if current.get("snapshot", {}).get("revision_20260927b") is not None:
            # 主会话暂存回写后：候选 = 本批输出。
            self.assertEqual(current["package_version"], want)
            rows = X.unpack(candidate.read("common", ABILITY))
            for key, value in out["ability"].items():
                self.assertEqual(X.csv_read(rows[key]), value, key)
            strings = X.unpack(candidate.read("common", FLAT))
            staged_c = P3.staged_version(current, M.PACKAGES[0]) is not None
            for key, value in out["cas"].items():
                if staged_c and key in P3.PANELS_BY_CAS:     # 第三轮（技能强化文案 R2）改过能力1 第2行
                    self.assertEqual(value, [["\n".join(P3.PANELS_BY_CAS[key]["before"])]], key)
                    value = [["\n".join(P3.PANELS_BY_CAS[key]["after"])]]
                self.assertEqual(X.csv_read(strings[key]), value, key)
            self.assertLessEqual(set(M.CAPABILITIES), set(current["required_capabilities"]))
            return
        # 暂存脚本同形：ability 走候选 splice（1199891/1199895 是候选自有键）；面板串候选尚未声明
        # custom_ability_string（RevisionCandidate.splice 会拒绝 live 已有而候选未认领的键），
        # 按 stage_batch.Plan.splice 的键级合并 + emit 写入（desc_override_<code>_N 在面板覆盖命名空间内）。
        self.assertNotIn(("common", FLAT), candidate.original)
        candidate.splice(ABILITY, out["ability"])
        strings = X.unpack(candidate.read("common", FLAT))
        strings.update({key: X.csv_write(rows) for key, rows in out["cas"].items()})
        candidate.emit("common", FLAT, X.pack(strings))
        rows = X.unpack(candidate.read("common", ABILITY))
        for key, value in out["ability"].items():
            self.assertEqual(X.csv_read(rows[key]), value, key)
        strings = X.unpack(candidate.read("common", FLAT))
        for key, value in out["cas"].items():
            self.assertEqual(X.csv_read(strings[key]), value, key)
        evidence = candidate.finish({"dry_run": True}, apply=False)
        self.assertFalse(evidence["applied"])
        self.assertEqual({item["logical_path"] for item in evidence["changed_files"]}, {ABILITY, FLAT})
        self.assertEqual(before, manifest.read_bytes())


if __name__ == "__main__":
    unittest.main()
