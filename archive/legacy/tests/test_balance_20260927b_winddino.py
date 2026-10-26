# -*- coding: utf-8 -*-
"""风巨蜥 149998 ``land_dragon_wind_playable`` 2026-09-27 平衡第二批（作者请求 (1)）。

fixture = live 输入快照（``fixtures/balance_20260927b_winddino.json``，stage_batch.make_read(live_only=True)），
驱动 ``revise()``：删全面限制 7 行、去主位（能力1/4/5 的 202、能力6 整键 c1）、能力3 #4 213→724 +30%、
全部能力/队长行加风共鸣（能力2 #3 锁槽除外）、四条自身攻/能伤加成改全队(风)、能力2 面板加共鸣前缀；
逐格前后值、未改行/格逐字保留、BEFORE 漂移拒绝、自动面板键出现即拒绝、不改输入、对自身输出重跑拒绝、
合法性门禁为空、面板规则、生成器（wf_wind_dragon_revision.revision_20260927b / a2_panel）== revise() 且重跑空操作、
候选干跑（候选在 gitignore 的 work/ 下，缺时跳过）。本单元不改 DSL（``out["dsl"] == {}``），无 AMF3/DSL 门禁项。
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_balance_20260927b_winddino as M  # noqa: E402
import wf_client_legality as L  # noqa: E402
import wf_describe as D  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_wind_dragon_revision as W  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927b_winddino.json'
WORKSPACE = ROOT / "work/character_packs" / M.PACKAGES[0]
ABILITY_LOGICAL = "master/ability/ability.orderedmap"
LEADER_LOGICAL = "master/ability/leader_ability.orderedmap"
FLAT = "master/string/custom_ability_string.orderedmap"
#: 候选 land_dragon_wind_poc manifest 现有 required_capabilities + 本批补登。
CANDIDATE_CAPABILITIES = {"damage-type-rules-v1", "gauge-gain-rules-v1",
                          "panel-description-override-v2", *M.CAPABILITIES}
A1, A2, A3, A4, A5, A6 = (M.ABILITY[slot] for slot in range(1, 7))
RESONANCE = ("2", "600000", "600000", "Green")

DESCRIBE_AFTER = {
    M.LEADER: (
        "风·编成≥6 时: 赋予全队(风) 攻击力 100%→150%",
        "风·编成≥6 时: 赋予全队(风) 能力伤害 150%→200%",
        "风·编成≥6 时: 赋予全队 Fever点 100%→150%",
        "风·编成≥6 时: 自身 Fever时间延长 20%→30%",
        "风·编成≥6 时: Fever≥1 → 赋予全队(风) 技能槽 5%",
        "风·编成≥6 时: 持续·Fever → 赋予全队(风) 能力伤害 100%→150%",
        "风·编成≥6 时: 持续·Fever → 赋予全队(风) 技能槽充能 15%→30%",
        "风·编成≥6 时: 任一敌方强化弹射HitLv2≥1(CT0.6秒) → 自身 发动技能动作[ability_skill_land_dragon_wind_ring_lv2]",
        "风·编成≥6 时: 任一敌方强化弹射HitLv3≥1(CT0.6秒) → 自身 发动技能动作[ability_skill_land_dragon_wind_laser_lv3]",
        "风·编成≥6 时: 自身 强化弹射覆盖",
    ),
    A1: (
        "风·编成≥6 时: 赋予全队(风) 能力伤害 50%→100%",
        "风·编成≥6 时: 技能发动≥1 → 自身 状态Fever点 50%→100%(15秒)×1次",
    ),
    A2: (
        "非Fever 且 风·编成≥6 时: 连击≥10 → 自身 追加Fever点 7500%→15000%",
        "非Fever 且 风·编成≥6 时: 连击≥15 → 自身 追加Fever点 15000%→30000%",
        "风·编成≥6 时: 连击≥25 → 自身 技能槽 5%",
        "持有者为协力 时: 持续·HP≥ → 赋予全队 限制技能槽增加 0%",
    ),
    A3: (
        "风·编成≥6 时: Fever≥1 → 自身 技能槽 5%",
        "风·编成≥6 时: 持续·Fever → 赋予全队(风) 能力伤害 75%→150%",
        "风·编成≥6 时: 持续·Fever → 自身 技能槽充能 25%→50%",
        "风·编成≥6 且 Fever 时: 技能发动≥1(CT10秒) → 自身 技能槽 5%",
        "风·编成≥6 且 Fever 时: 技能发动≥1(CT10秒) → 自身 Fever槽增减(上限比例) 30%",
    ),
    A4: ("风·编成≥6 时: 自身 技能槽 50%→100%",),
    A5: (
        "风·编成≥6 时: 赋予全队(风) 能力伤害 25%→50%",
        "风·编成≥6 时: 自身 Fever时间延长 5%→10%",
        "风·编成≥6 时: 持续·Fever → 赋予全队(风) 攻击力 25%→50%",
    ),
    A6: (
        "风·编成≥6 时: 技能发动≥1(限5次) → 赋予全队(风) 能力伤害 15%→30%",
        "风·编成≥6 时: 技能发动≥2 → 自身 技能槽 5%",
        "风·编成≥6 时: 持续·Fever → 赋予全队(风) 独立乘区能力伤害 15%→30%",
    ),
}


def load_raw() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def load_fixture() -> dict:
    return {kind: value for kind, value in load_raw().items() if not kind.startswith("_")}


def fixture_key(kind, key):
    """夹具 JSON 不能存元组键：table 的 (logical, outer) 存成 "logical|outer"。"""
    return "|".join(key) if kind == "table" else key


def reader(data: dict):
    def read(kind, key):
        return data[kind][fixture_key(kind, key)]   # 缺键 ⇒ KeyError，与 stage_batch.make_read 同形
    return read


def table(key: str) -> str:
    return "leader_ability" if key == M.LEADER else "ability"


def pre_slots(key: str) -> tuple[int, ...]:
    return W.LEADER_PRE_SLOTS if key == M.LEADER else W.ABILITY_PRE_SLOTS


def resonance_slots(key: str, row: list[str]) -> list[int]:
    return [c for c in pre_slots(key) if (row[c], row[c + 3], row[c + 4], row[c + 5]) == RESONANCE]


def surviving(key: str) -> list[int]:
    """改后第 i 行对应的 live 行号（能力1 删去 #2–#8）。"""
    count = len(M.ROW_NAMES[key])
    return [i for i in range(count) if not (key == A1 and i in M.BOSS_LIMIT_ROWS)]


class ReviseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))
        cls.old = {**cls.live["ability"], M.LEADER: cls.live["leader"][M.LEADER]}
        cls.new = {**cls.out["ability"], M.LEADER: cls.out["leader"][M.LEADER]}

    # ---------------------------------------------------------------- 接口

    def test_fixture_is_the_reviewed_baseline(self):
        for (kind, key), want in M.BEFORE.items():
            self.assertEqual(M.digest(self.live[kind][fixture_key(kind, key)]), want, f"{kind}:{key}")
        self.assertEqual({(kind, key) for kind, keys in self.live.items() for key in keys},
                         {(kind, fixture_key(kind, key)) for kind, key in M.BEFORE})
        self.assertEqual(tuple(load_raw()["_absent_cas"]), M.AUTO_PANEL_KEYS)
        for key in M.AUTO_PANEL_KEYS:
            self.assertNotIn(key, self.live["cas"])

    def test_module_contract_exports(self):
        self.assertEqual((M.CID, M.CODE), (W.CID, W.CODE))
        self.assertEqual(M.PACKAGES, ["land_dragon_wind_poc"])
        self.assertEqual(M.PACKAGE_VERSION, {"land_dragon_wind_poc": "0.20260927.1"})   # 候选现值 0.20260925.1
        self.assertGreater((0, 20260927, 1), (0, 20260925, 1))
        self.assertEqual(M.CAPABILITIES, ["kyubi-fever-ratio-v1"])
        self.assertEqual(M.REVIEWED_DRIFT, {})
        self.assertFalse(hasattr(M, "UNITS"))

    def test_only_changed_keys_are_returned(self):
        out = self.out
        self.assertEqual(set(out["ability"]), set(M.ABILITY.values()))
        self.assertEqual(set(out["leader"]), {M.LEADER})
        self.assertEqual(set(out["cas"]), {M.PANEL_A2})
        self.assertEqual(set(out["table"]), {(M.CHAR_TABLE, M.CID)})
        self.assertEqual(set(out["server_character"]), {M.CID})
        for kind in ("text", "action", "dsl", "server_text"):
            self.assertEqual(out[kind], {}, kind)
        self.assertEqual(out["new_programs"], [])
        json.dumps(out["notes"], ensure_ascii=False)
        for key in (*out["ability"], *out["leader"]):
            self.assertTrue(key.startswith(M.CID), key)
            self.assertNotEqual(out["ability"].get(key, out["leader"].get(key)), self.old[key], key)
        for key in out["cas"]:
            self.assertTrue(key.startswith("desc_override_" + M.CODE), key)

    # ---------------------------------------------------------------- 逐格前后值

    def test_every_edit_matches_the_table_and_nothing_else_moves(self):
        for key, rows in self.new.items():
            live = self.old[key]
            self.assertEqual(len(rows), len(surviving(key)), key)
            for new_index, old_index in enumerate(surviving(key)):
                before, after = live[old_index], rows[new_index]
                self.assertEqual(len(after), len(before))
                changed = {c: (before[c], after[c]) for c in range(len(before)) if before[c] != after[c]}
                self.assertEqual(changed, M.EDITS.get((key, old_index), {}), f"{key}#{old_index}")

    def test_boss_limit_block_is_removed(self):
        self.assertEqual(len(self.old[A1]), 9)
        self.assertEqual(len(self.new[A1]), 2)
        self.assertEqual(self.new[A1], [M._edit(A1, i, self.old[A1][i]) for i in (0, 1)])
        removed = self.old[A1][2:]
        self.assertTrue(all(r[0] == M.BOSS_LIMIT and (r[6], r[9], r[11]) == ("2", "200000", "tag_boss")
                            for r in removed))
        self.assertEqual([(r[27], r[47]) for r in removed], list(M.BOSS_LIMIT_KINDS))
        self.assertEqual([r[68] for r in removed if r[47] == "461"], [M.BOSS_LIMIT_MARK])
        blob = json.dumps({part: self.out[part] for part in ("ability", "leader", "cas")}, ensure_ascii=False)
        for token in ('"' + M.BOSS_LIMIT + '"', '"tag_boss"', '"-999000"', '"9.999999E11"'):
            self.assertNotIn(token, blob)
        self.assertFalse([r for r in self.new[A1] if r[47] in ("219", "479", "461")])

    def test_main_slot_restrictions(self):
        for key in (A1, A2, A4, A5, A6):
            self.assertTrue(all(r[1] == "true" for r in self.new[key]), key)
        self.assertTrue(all(r[1] == "false" for r in self.new[A3]))                  # 能力3 保留主位
        self.assertTrue(all(r[1] == "false" for r in self.old[A6]))                  # 改前能力6 整键禁合击
        for key in M.ABILITY.values():
            self.assertTrue(all("202" not in (r[6], r[13], r[20]) for r in self.new[key]), key)
        self.assertEqual(sum(r[6] == "202" for key in M.ABILITY.values() for r in self.old[key]), 6)
        self.assertEqual(self.new[A2][3], self.old[A2][3])                           # 203 锁槽逐字保留
        self.assertEqual((self.new[A2][3][6], self.new[A2][3][109]), ("203", "423"))

    def test_wind_resonance_everywhere_except_the_unison_lock(self):
        for key, rows in self.new.items():
            for index, row in enumerate(rows):
                slots = resonance_slots(key, row)
                if key == A2 and index == 3:
                    self.assertEqual(slots, [], "unison lock must not be bypassable by non-wind teams")
                    continue
                self.assertEqual(len(slots), 1, f"{key}#{index}")
                expected = 13 if key == A2 and index in (0, 1) else pre_slots(key)[0]
                self.assertEqual(slots, [expected], f"{key}#{index}")
        self.assertEqual([r[6] for r in self.new[A2][:2]], ["186", "186"])          # 非 Fever 前置保留在 c6
        self.assertEqual([r[13] for r in self.new[A3][3:5]], ["12", "12"])          # Fever 前置保留在 c13
        override = self.new[M.LEADER][9]
        self.assertEqual((override[45], override[80], override[81], override[82]),
                         ("722", "land_dragon_wind_pf", "1,2,3", "override_string_wind_spgirl_4anv"))
        self.assertEqual(sum(len(r) == 126 and resonance_slots(A1, r) != []
                             for key in M.ABILITY.values() for r in self.new[key]), 17)   # 18 行 − 锁槽

    def test_party_wind_bonus_rows(self):
        expected = {(A1, 0): (48, "388"), (A6, 0): (48, "388"), (A3, 1): (110, "154"), (A6, 2): (110, "412")}
        for (key, index), (col, kind) in expected.items():
            row, old = self.new[key][index], self.old[key][surviving(key)[index]]
            self.assertEqual((row[col - 1], row[col], row[col + 1]), (kind, "5", "Green"), (key, index))
            self.assertEqual((old[col], old[col + 1]), ("0", ""), (key, index))
            value_cols = (51, 52) if col == 48 else (113, 114)
            self.assertEqual([row[c] for c in value_cols], [old[c] for c in value_cols])   # 数值不变
        self.assertEqual(self.new[A6][0][34], "5")                                     # 限 5 次不变
        # 非攻击/能伤的「自身」行保持自身。
        for key, index, col in ((A1, 1, 48), (A2, 0, 48), (A2, 1, 48), (A2, 2, 48), (A3, 0, 48),
                                (A3, 2, 110), (A3, 3, 48), (A4, 0, 48), (A5, 1, 48), (A6, 1, 48)):
            self.assertEqual(self.new[key][index][col], "0", (key, index))
        self.assertEqual(self.new[A3][4][48], "")                                      # 724 不带目标
        leader = self.new[M.LEADER]
        self.assertEqual([(r[46], r[47]) for r in leader[:5]],
                         [("5", "Green"), ("5", "Green"), ("5", "(None)"), ("0", ""), ("5", "Green")])

    def test_ability3_fever_gauge_ratio(self):
        old, row = self.old[A3][4], self.new[A3][4]
        self.assertEqual((old[47], old[51], old[52]), ("213", "22500000", "45000000"))
        self.assertEqual((row[47], row[48], row[49], row[51], row[52]), ("724", "", "", "30000", "30000"))
        self.assertEqual((row[27], row[28], row[30], row[31], row[34], row[35]),
                         ("23", "0", "100000", "100000", "(None)", "600"))            # 自身施技、CT 600 不变
        self.assertEqual((row[13], row[5], row[1]), ("12", "0", "false"))            # Fever 前置、瞬发、主位
        self.assertTrue(all(row[c] == "" for c in range(53, 85)))                     # 内容块其余格空（live 724 行形）
        self.assertEqual(L.required_client_capabilities("ability", row), ["kyubi-fever-ratio-v1"])
        self.assertEqual(self.new[A3][3][47], "211")                                  # 同触发技能槽行不动

    def test_auto_describe(self):
        for key, lines in DESCRIBE_AFTER.items():
            self.assertEqual(tuple(D.describe_line(r, table(key)) for r in self.new[key]), lines, key)

    # ---------------------------------------------------------------- 面板

    def test_panel_a2_before_and_after(self):
        old = self.live["cas"][M.PANEL_A2][0][0]
        new = self.out["cas"][M.PANEL_A2][0][0]
        self.assertEqual(tuple(old.split("\n")), M.PANEL_A2_BEFORE)
        self.assertEqual(new, "风属性共鸣时，非Fever状态下，每达成10连击，Fever槽+150；每达成15连击，Fever槽+300。\n"
                              "风属性共鸣时，每达成25连击，自身技能槽+5%。\n"
                              "作为合击角色编成时，全队无法因技能或能力效果增加技能槽（战斗开始时除外）。")
        self.assertEqual(len(self.out["cas"][M.PANEL_A2]), 1)
        self.assertEqual(len(self.out["cas"][M.PANEL_A2][0]), 1)

    def test_panel_agrees_with_the_data(self):
        lines = self.out["cas"][M.PANEL_A2][0][0].split("\n")
        rows = self.new[M.ABILITY[2]]
        self.assertIn(f"每达成{int(rows[0][31]) // 100000}连击，Fever槽+{int(rows[0][52]) // 100000}", lines[0])
        self.assertIn(f"每达成{int(rows[1][31]) // 100000}连击，Fever槽+{int(rows[1][52]) // 100000}", lines[0])
        self.assertIn(f"每达成{int(rows[2][31]) // 100000}连击，自身技能槽+{int(rows[2][51]) // 1000}%", lines[1])
        for line, gated in zip(lines, (resonance_slots(A2, rows[0]), resonance_slots(A2, rows[2]),
                                       resonance_slots(A2, rows[3]))):
            self.assertEqual(line.startswith(M.RESONANCE_TEXT), bool(gated), line)

    def test_panel_texts_obey_the_project_rules(self):
        text = self.out["cas"][M.PANEL_A2][0][0]
        self.assertNotIn("／", text)
        self.assertNotIn("<icon", text)                                              # 能力2 不限主位
        for line in text.split("\n"):
            self.assertEqual(KL.panel_problems(line), [], line)
            for phrase in ("自身为队长时", "觉醒后", "生命值100%以下", "无上限", "无限叠加", "不设上限", "可无限"):
                self.assertNotIn(phrase, line)
        self.assertEqual(L.panel_override_capability(M.PANEL_A2), "panel-description-override-v2")
        self.assertIn(L.panel_override_capability(M.PANEL_A2), CANDIDATE_CAPABILITIES)
        # 其余槽与队长技没有覆盖键：由客户端按行自动生成。
        self.assertEqual({M.ABILITY[s]: self.new[M.ABILITY[s]][0][0] for s in (1, 3, 4, 5, 6)},
                         {M.ABILITY[s]: f"wind_dragon_{s}" for s in (1, 3, 4, 5, 6)})
        self.assertEqual(self.new[M.LEADER][0][0], "wind_dragon")
        self.assertEqual({"desc_override_" + r[0] for r in (self.new[M.LEADER][0],
                          *(self.new[M.ABILITY[s]][0] for s in (1, 3, 4, 5, 6)))}, set(M.AUTO_PANEL_KEYS))

    # ---------------------------------------------------------------- 门禁

    def test_native_legality_gates_are_empty(self):
        cas_keys = set(M.INVOKE_SKILL_STRINGS) | set(self.out["cas"])
        for key, rows in self.new.items():
            kind = table(key)
            for index, row in enumerate(rows):
                label = f"{kind}:{key}#{index}"
                self.assertEqual(L.client_legality_problems(kind, row), [], label)
                self.assertEqual(L.declared_block_field_problems(kind, row), [], label)
                self.assertEqual(L.invoke_skill_string_problems(row, cas_keys, kind=kind), [], label)
                self.assertEqual(KL.row_problems(kind, row, M.ELEMENT if kind == "ability" else None), {}, label)
                if kind == "ability":
                    self.assertEqual(L.ability_element_column_problems(kind, row, M.ELEMENT), [], label)
                self.assertLessEqual(set(L.required_client_capabilities(kind, row)), CANDIDATE_CAPABILITIES, label)
        leader_629 = [r for r in self.new[M.LEADER] if r[45] == "629"]
        self.assertEqual({r[68] for r in leader_629}, set(M.INVOKE_SKILL_STRINGS))

    # ---------------------------------------------------------------- fail closed

    def test_input_is_not_mutated_and_output_is_detached(self):
        data = deepcopy(self.live)
        out = M.revise(reader(data))
        self.assertEqual(data, self.live)
        out["ability"][A1][0][48] = "mutated"
        out["leader"][M.LEADER][0][4] = "mutated"
        out["cas"][M.PANEL_A2][0][0] = "mutated"
        self.assertEqual(data, self.live)

    def test_baseline_drift_is_rejected(self):
        for kind, key in M.BEFORE:
            key = fixture_key(kind, key)
            data = deepcopy(self.live)
            if kind == "cas":
                data[kind][key][0][0] += "。"
            else:
                data[kind][key][0][35] = "60"
            with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
                M.revise(reader(data))
            data = deepcopy(self.live)
            data[kind][key] = data[kind][key] + [list(data[kind][key][0])]
            with self.assertRaises(ValueError):
                M.revise(reader(data))

    def test_tag_boss_is_removed_from_both_layers_and_nothing_else(self):
        """作者追加：tag_boss 标签两层都去掉；只动标签格。"""
        old = self.live["table"][fixture_key("table", (M.CHAR_TABLE, M.CID))]
        new = self.out["table"][(M.CHAR_TABLE, M.CID)]
        self.assertEqual(old[0][M.TAG_COL], "tag_boss")
        self.assertEqual(new[0][M.TAG_COL], "")
        self.assertEqual([i for i in range(len(old[0])) if old[0][i] != new[0][i]], [M.TAG_COL])
        old_s, new_s = self.live["server_character"][M.CID], self.out["server_character"][M.CID]
        self.assertEqual((old_s[0][M.TAG_COL], new_s[0][M.TAG_COL]), ("tag_boss", ""))
        self.assertEqual([i for i in range(len(old_s[0])) if old_s[0][i] != new_s[0][i]], [M.TAG_COL])
        self.assertEqual(len(new_s), len(old_s))
        self.assertEqual(M._drop_tag("OmniElement,tag_boss"), "OmniElement")
        with self.assertRaises(ValueError):
            M.character_rows(new)                      # 已去掉 ⇒ 重跑拒绝
        with self.assertRaises(ValueError):
            M.server_character(new_s)

    def test_new_auto_panel_key_is_rejected(self):
        for key in M.AUTO_PANEL_KEYS:
            data = deepcopy(self.live)
            data["cas"][key] = [["覆盖文案"]]
            with self.assertRaisesRegex(ValueError, "no longer auto-generated"):
                M.revise(reader(data))

    def test_revise_is_not_reapplicable_to_its_own_output(self):
        """重跑在已改的 live 上必须拒绝（fail closed）。"""
        for kind in ("ability", "leader", "cas"):
            data = deepcopy(self.live)
            data[kind].update(deepcopy(self.out[kind]))
            with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
                M.revise(reader(data))
        for key in M.ABILITY.values():
            with self.assertRaises(ValueError):
                M.ability_rows(key, self.new[key])
        with self.assertRaises(ValueError):
            M.leader_rows(self.new[M.LEADER])
        with self.assertRaises(ValueError):
            M.panel_a2(self.out["cas"][M.PANEL_A2])

    def test_row_locator_is_content_based(self):
        """绕过 BEFORE 直接调纯函数：目标行形状不对也要拒绝。"""
        cases = (
            (A1, lambda r: r[0].__setitem__(6, "0")),                     # 202 已被别人去掉
            (A1, lambda r: r[5].__setitem__(68, "180003")),               # 标记换了
            (A1, lambda r: r[3].__setitem__(11, "tag_other")),            # 限制门换了
            (A1, lambda r: r.pop()),                                      # 限制行少一条
            (A2, lambda r: r[3].__setitem__(6, "202")),                   # 锁槽变成主位
            (A2, lambda r: r[0].__setitem__(13, "12")),                   # 第二前置槽被占
            (A3, lambda r: r[4].__setitem__(47, "724")),                  # 已改过
            (A3, lambda r: r[4].__setitem__(51, "15000000")),             # Fever 点数值漂移
            (A3, lambda r: r[1].__setitem__(110, "5")),                   # 已是全队
            (A6, lambda r: r[0].__setitem__(1, "true")),                  # 已开放合击
            (A6, lambda r: r[0].__setitem__(49, "Green")),                # 目标组已有值
            (A5, lambda r: r[0].pop()),                                   # 列宽不对
            (A4, lambda r: r.append(list(r[0]))),                         # 记录条数不对
        )
        for n, (key, mutate) in enumerate(cases):
            rows = deepcopy(self.old[key])
            mutate(rows)
            with self.assertRaises(ValueError, msg=f"{n} {key}"):
                M.ability_rows(key, rows)
        for mutate in (lambda r: r[9].__setitem__(45, "419"), lambda r: r[0].__setitem__(4, "2"),
                       lambda r: r[3].__setitem__(9, "Red"), lambda r: r.pop()):
            rows = deepcopy(self.old[M.LEADER])
            mutate(rows)
            with self.assertRaises(ValueError):
                M.leader_rows(rows)
        old_panel = self.live["cas"][M.PANEL_A2][0][0]
        for bad in (old_panel.replace("+150", "+75"), old_panel + "\n多一行。", " <icon id='main'>  " + old_panel):
            with self.assertRaises(ValueError):
                M.panel_a2([[bad]])


class GeneratorSyncTests(unittest.TestCase):
    """生成器（wf_wind_dragon_revision）输出 == revise()；对自身输出重跑是空操作，不会回退本批改动。"""

    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))
        cls.gen_abilities, cls.gen_leader = W.revision_20260927b(deepcopy(cls.live["ability"]),
                                                                 deepcopy(cls.live["leader"][M.LEADER]))

    def test_generator_equals_revise_output(self):
        self.assertEqual(self.gen_abilities, self.out["ability"])
        self.assertEqual(self.gen_leader, self.out["leader"][M.LEADER])
        self.assertEqual(W.a2_panel(), self.out["cas"][M.PANEL_A2])
        self.assertEqual(W.A2_PANEL_KEY, M.PANEL_A2)
        self.assertEqual(W.RESONANCE, RESONANCE)
        self.assertEqual(W.RESONANCE_TEXT, M.RESONANCE_TEXT)

    def test_generator_rerun_is_a_no_op(self):
        again = W.revision_20260927b(deepcopy(self.gen_abilities), deepcopy(self.gen_leader))
        self.assertEqual(again, (self.gen_abilities, self.gen_leader))

    def test_generator_does_not_mutate_its_input(self):
        abilities, leader = deepcopy(self.live["ability"]), deepcopy(self.live["leader"][M.LEADER])
        W.revision_20260927b(abilities, leader)
        self.assertEqual((abilities, leader), (self.live["ability"], self.live["leader"][M.LEADER]))

    def test_boss_limit_never_comes_back(self):
        self.assertEqual(W.BOSS_LIMIT_STRING_ID, M.BOSS_LIMIT)
        self.assertEqual(W.BOSS_LIMIT_KEY, A1)
        rows = W.drop_boss_limit(self.live["ability"][A1])
        self.assertEqual(rows, self.live["ability"][A1][:2])
        for key, rows in self.gen_abilities.items():
            self.assertFalse([r for r in rows if r[0] == W.BOSS_LIMIT_STRING_ID], key)

    def test_main_only_keys_are_synced(self):
        self.assertEqual(W.MAIN_ONLY_KEYS, tuple(M.ABILITY[s] for s in sorted(M.MAIN_ONLY_SLOTS)))
        self.assertEqual(W.MAIN_ONLY_KEYS, (A3,))

    def test_helper_contracts(self):
        lock = self.live["ability"][A2][3]
        self.assertTrue(W.is_unison_lock(lock))
        self.assertFalse(any(W.is_unison_lock(r) for r in self.live["ability"][A2][:3]))
        full = deepcopy(self.live["ability"][A4])
        for col in W.ABILITY_PRE_SLOTS:
            full[0][col] = "186"
        with self.assertRaisesRegex(ValueError, "no free precondition slot"):
            W.add_wind_resonance(full)
        slot_args = deepcopy(self.live["ability"][A4])
        slot_args[0][7] = "0"
        with self.assertRaisesRegex(ValueError, "slot precondition arguments"):
            W.open_slot(slot_args)
        grouped = deepcopy(self.live["ability"][A6])
        grouped[0][49] = "Red"
        with self.assertRaisesRegex(ValueError, "target group"):
            W.party_bonus(grouped)
        with self.assertRaisesRegex(ValueError, "ability keys"):
            W.revision_20260927b({A1: self.live["ability"][A1]}, self.live["leader"][M.LEADER])


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
        version = M.PACKAGE_VERSION[M.PACKAGES[0]]
        self.assertGreaterEqual(tuple(map(int, version.split("."))),
                                tuple(map(int, current["package_version"].split("."))))
        candidate = RevisionCandidate(ROOT, WORKSPACE, character_id=M.CID, code_name=M.CODE,
                                      snapshot_key="revision_20260927b", package_version=version,
                                      baseline_factory=lambda *a, **k: None,
                                      reviewed_input_drift=M.REVIEWED_DRIFT)
        if current.get("snapshot", {}).get("revision_20260927b") is not None:
            # 主会话暂存回写后：候选 = 本批输出。
            self.assertEqual(current["package_version"], version)
            for logical, part in ((ABILITY_LOGICAL, "ability"), (LEADER_LOGICAL, "leader"), (FLAT, "cas")):
                rows = X.unpack(candidate.read("common", logical))
                for key, value in out[part].items():
                    self.assertEqual(X.csv_read(rows[key]), value, key)
            # tag_boss 两层同步也已回写：角色表 c5 与服务端 cdndata/character.json [0][5]。
            for (logical, key), value in out["table"].items():
                self.assertEqual(X.csv_read(X.unpack(candidate.read("common", logical))[key]), value, key)
            server = json.loads(candidate.read("server", "cdndata/character.json"))
            for key, value in out["server_character"].items():
                self.assertEqual(server[key], value, key)
            self.assertLessEqual(set(M.CAPABILITIES), set(current["required_capabilities"]))
            self.assertEqual(before, manifest.read_bytes())
            return
        claims = {t["logical_path"]: set(t["outer_keys"]) for t in current["tables"]}
        self.assertLessEqual(set(out["ability"]), claims[ABILITY_LOGICAL])
        self.assertLessEqual(set(out["leader"]), claims[LEADER_LOGICAL])
        self.assertLessEqual(set(out["cas"]), claims[FLAT])
        # 回写前：候选这些键与 live 快照逐字一致（REVIEWED_DRIFT 为空的依据）。
        live = load_fixture()
        for logical, part in ((ABILITY_LOGICAL, "ability"), (LEADER_LOGICAL, "leader"), (FLAT, "cas")):
            rows = X.unpack(candidate.read("common", logical))
            for key, value in live[part].items():
                self.assertEqual(X.csv_read(rows[key]), value, key)
        candidate.splice(ABILITY_LOGICAL, out["ability"])
        candidate.splice(LEADER_LOGICAL, out["leader"])
        candidate.splice(FLAT, out["cas"])
        for logical, part in ((ABILITY_LOGICAL, "ability"), (LEADER_LOGICAL, "leader"), (FLAT, "cas")):
            rows = X.unpack(candidate.read("common", logical))
            for key, value in out[part].items():
                self.assertEqual(X.csv_read(rows[key]), value, key)
        evidence = candidate.finish({"dry_run": True}, apply=False)
        self.assertFalse(evidence["applied"])
        self.assertEqual({item["logical_path"] for item in evidence["changed_files"]},
                         {ABILITY_LOGICAL, LEADER_LOGICAL, FLAT})
        self.assertEqual(before, manifest.read_bytes())


if __name__ == "__main__":
    unittest.main()
