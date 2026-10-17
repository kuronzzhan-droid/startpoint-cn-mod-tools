"""雷吉斯 139994 · 2026-09-27 平衡批次（能力相关换成技能伤害）的修订模块回归。

fixture = live 1.4.1047（s7-regis 1.0.6）只读快照；逐项断言改动、未改部分保持、BEFORE 漂移拒绝、
不改输入、合法性门禁为空，以及 kit（wf_seasonal7_kit_regis）按「浪涌 → 本批」顺序重跑与 revise() 一致。
"""
from __future__ import annotations

import inspect
import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_balance_20260927_regis as M  # noqa: E402
import wf_client_legality as L  # noqa: E402
import wf_dsl  # noqa: E402
import wf_regis_surge_stages as R  # noqa: E402
import wf_seasonal7_kit_regis as K  # noqa: E402
from wf_character_revision import encode_tree  # noqa: E402
from wf_seasonal7_kit_philia import dsl_gate_failures, dsl_gates  # noqa: E402

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixtures/balance_20260927_regis.json"
SURGE_FIXTURE = HERE / "fixtures/surge_anchor_before.json"
ROOT = HERE.parents[1]
L1, L2 = M.SKILL_PROGRAMS["1"], M.SKILL_PROGRAMS["2"]
MANIFEST_CAPS = {"kyubi-fever-ratio-v1", "panel-description-override-v2"}


def load():
    fx = json.loads(FIXTURE.read_bytes())
    data = {(kind, tuple(key) if isinstance(key, list) else key): value for kind, key, value in fx["reads"]}
    return data, fx["template_upskill_131020"]


def reader(data):
    return lambda kind, key: data[kind, key]


def cmds(tree, name):
    return list(M._commands(tree, name))


class ReviseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data, cls.template_up = load()
        cls.out = M.revise(reader(cls.data))

    def live(self, kind, key):
        return deepcopy(self.data[kind, key])

    # ---------------------------------------------------------------- DSL
    def test_skill_trees_now_use_skill_damage_everywhere(self):
        for program, (dur, value) in ((L1, (720, [{"min": 1.0, "max": 1.0}])),
                                      (L2, (900, [{"min": 1.25, "max": 1.5}]))):
            before, after = self.live("dsl", program), self.out["dsl"][program]
            self.assertEqual(2, before[10])
            self.assertEqual(0, after[10])
            areas = cmds(after, "CreateHitArea")
            self.assertEqual(3, len(areas))
            self.assertTrue(all(a[24] == 0 for a in areas))
            blob = json.dumps(after)
            self.assertNotIn('"ACAbilityDamage"', blob)
            buff, = [ac for c in cmds(after, "CreateCondition") for ac in c[2] if ac[0] == "ACSkillDamage"]
            self.assertEqual([{"min": dur, "max": dur}], buff[1])
            self.assertEqual(value, buff[2])
            # 只动了这三类位置：还原后与 live 逐节点相同（倍率、段数、vlv、特效都不变）
            restored = deepcopy(after)
            restored[10] = 2
            for area in cmds(restored, "CreateHitArea"):
                area[24] = 2
            for c in cmds(restored, "CreateCondition"):
                for ac in c[2]:
                    if ac[0] == "ACSkillDamage":
                        ac[0] = "ACAbilityDamage"
            self.assertEqual(before, restored)

    def test_strike_tree_is_all_enemies_20x_thunder_skill_damage(self):
        tree = self.out["dsl"][M.STRIKE_PROGRAM]
        self.assertEqual(M.strike_tree(), tree)
        self.assertEqual([M.STRIKE_PROGRAM], self.out["new_programs"])
        self.assertEqual(1, tree[1])
        self.assertEqual(0, tree[10])                         # 根 bta=0：629 来源 ActionSkill → 技能伤害
        find, = cmds(tree, "FindAllSubjects")
        self.assertEqual([0, 49], find[1:3])                  # 官方 psychic_tomboygirl_2 同写法：全体敌人
        area, = cmds(tree, "CreateHitArea")
        self.assertEqual(0, area[2])
        self.assertEqual(["Circle", [{"min": 10, "max": 10}]], area[9])
        self.assertEqual(["SpecifyHitAreaLifetimeDirectly", 2], area[13])
        self.assertEqual(["CalculatedUsingMaxNumOfHits", 1], area[14])
        self.assertEqual(["Some", [{"min": 1, "max": 1}]], area[15])
        self.assertEqual((2, 3, 0), (area[21], area[22], area[24]))
        attack, = cmds(tree, "CreateNormalAttack")
        self.assertEqual(area[22], attack[1])                 # 伤害挂在被击中的敌人上
        self.assertEqual(3, attack[2])                        # DSL 元素 1-based：雷
        self.assertEqual(0, attack[5])                        # 原生能力伤害固定项 0
        self.assertEqual([{"min": 20.0, "max": 20.0}], attack[6])
        self.assertFalse(attack[8])                           # 不吃连击加成（与 253 相同）
        self.assertEqual([[{"min": 1, "max": 1}]] * 2, attack[13:15])   # 削韧 / Fever = ABILITY_ATTACK_BASIC_*
        effect, = cmds(tree, "ShowEffect")
        self.assertEqual(["SpecifyEffectDirectly", M.HIT_EFFECT], effect[2])
        self.assertEqual(0, effect[3])

    def test_dsl_gates_are_clean(self):
        for program, tree in self.out["dsl"].items():
            encode_tree(tree)                                 # AMF3 往返
            self.assertEqual([], L.action_dsl_element_problems(tree, 2), program)
            self.assertEqual([], L.action_dsl_subject_binding_problems(tree), program)
            self.assertEqual([], L.action_dsl_lookup_scope_problems(tree), program)
            self.assertEqual([], L.action_dsl_hit_area_target_problems(tree), program)
            self.assertEqual([], dsl_gate_failures(dsl_gates(tree, element=2)), program)
            self.assertEqual([], M.dsl_problems(tree), program)

    # ---------------------------------------------------------------- 行
    def assertOnly(self, before, after, cells):
        restored = deepcopy(after)
        for col, value in cells.items():
            restored[col] = value
        self.assertEqual(before, restored)

    def test_leader_per_stack_and_skill_invoke_gauge(self):
        before, after = self.live("leader", M.CID), self.out["leader"][M.CID]
        self.assertEqual(len(before), len(after))
        self.assertEqual("2", after[0][107])
        self.assertEqual(["5", "Yellow", "", "150000", "150000"], after[0][108:113])
        self.assertOnly(before[0], after[0], {107: "154"})
        gauge = after[2]
        self.assertEqual(["23", "6", "Yellow", "100000", "100000"], gauge[25:30])
        self.assertEqual(("300", "211", "5000"), (gauge[33], gauge[45], gauge[49]))
        self.assertOnly(before[2], gauge, {25: "144", 28: "2000000", 29: "2000000"})
        self.assertEqual([before[i] for i in (1, 3, 4, 5, 6)], [after[i] for i in (1, 3, 4, 5, 6)])

    def test_ability2_invoke_keeps_trigger_resonance_and_unison_pool(self):
        before, after = self.live("ability", M.CID + "2"), self.out["ability"][M.CID + "2"]
        row = after[0]
        self.assertEqual(("true", "2", "600000", "Yellow"), (row[1], row[6], row[9], row[11]))
        self.assertNotIn("202", (row[6], row[13], row[20]))   # 不加主位门：保留副位效果
        self.assertEqual(["23", "7", "Yellow", "100000", "100000"], row[27:32])
        self.assertEqual("300", row[35])
        self.assertEqual(["629", "", "", "", "", ""], row[47:53])
        self.assertEqual(["", M.STRIKE_KEY, M.STRIKE_PROGRAM], row[69:72])
        self.assertOnly(before[0], row, {47: "253", 48: "0", 51: "2000000", 52: "2000000",
                                         69: "(None)", 70: "", 71: ""})
        self.assertEqual(before[1], after[1])

    def test_ability3_separated_term_trigger_stack_and_duplicate_removed(self):
        before, after = self.live("ability", M.CID + "3"), self.out["ability"][M.CID + "3"]
        self.assertEqual(6, len(before))
        self.assertEqual(5, len(after))
        self.assertEqual(["411", "5", "Yellow", "", "25000", "25000"], after[0][109:115])
        self.assertEqual("12", after[0][13])                  # Fever 前置不变
        self.assertOnly(before[0], after[0], {109: "412"})
        self.assertEqual(["23", "7", "Yellow", "100000", "100000"], after[1][27:32])
        self.assertEqual(("186", "300", "724"), (after[1][13], after[1][35], after[1][47]))
        self.assertOnly(before[1], after[1], {27: "144", 30: "1000000", 31: "1000000"})
        self.assertEqual(before[2:4], after[2:4])
        self.assertEqual("2", after[4][109])
        self.assertOnly(before[4], after[4], {109: "154"})
        removed = before[5]
        self.assertEqual(("411", "0", "12"), (removed[109], removed[110], removed[13]))
        self.assertEqual(1, sum(r[109] == "411" for r in after))   # 雷吉斯只在第 1 行拿 +25%

    def test_ability5_instant_skill_damage(self):
        before, after = self.live("ability", M.CID + "5"), self.out["ability"][M.CID + "5"]
        self.assertEqual("34", after[0][47])
        self.assertEqual("10", after[0][34])
        self.assertOnly(before[0], after[0], {47: "388"})
        self.assertEqual(before[1], after[1])

    def test_row_legality_and_capabilities(self):
        caps = set()
        keys = set(self.out["cas"])
        for kind, table in (("leader_ability", self.out["leader"]), ("ability", self.out["ability"])):
            for rows in table.values():
                for row in rows:
                    self.assertEqual([], L.client_legality_problems(kind, row))
                    self.assertEqual([], L.declared_block_field_problems(kind, row))
                    self.assertEqual([], L.invoke_skill_string_problems(row, keys, kind))
                    caps.update(L.required_client_capabilities(kind, row))
        for key in keys:
            caps.update(L.required_client_capabilities(L.CUSTOM_ABILITY_STRING_KIND, [key]))
        self.assertLessEqual(caps, MANIFEST_CAPS)
        self.assertEqual([], M.CAPABILITIES)

    def test_upskill_restores_template_skill_damage_tag(self):
        after = self.out["table"][(M.UPSKILL, M.CID)]
        self.assertEqual(self.template_up, after)
        self.assertEqual(2, after[0].count("skill_damage_up"))
        self.assertNotIn("ability_damage_up", after[0])

    # ---------------------------------------------------------------- 文案
    def test_descriptions_three_places(self):
        for value in (self.out["text"][M.CID], self.out["server_text"][M.CID]):
            self.assertEqual([M.DESCRIPTION] * 2, [value[0][5], value[0][7]])
        for inner, fields in self.out["action"][M.CODE]:
            self.assertEqual(M.DESCRIPTION, fields[1])
        self.assertNotIn("按能力伤害加成计算", M.DESCRIPTION)
        self.assertTrue(M.DESCRIPTION.endswith("提升雷属性角色技能伤害"))
        text_before = self.live("text", M.CID)
        text_before[0][5] = text_before[0][7] = M.DESCRIPTION
        self.assertEqual(text_before, self.out["text"][M.CID])
        action_before = [(k, list(v)) for k, v in self.live("action", M.CODE)]
        for _k, fields in action_before:
            fields[1] = M.DESCRIPTION
        self.assertEqual(action_before, [(k, list(v)) for k, v in self.out["action"][M.CODE]])

    def test_panel_texts(self):
        cas = self.out["cas"]
        self.assertEqual({*M.PANEL_KEYS.values(), M.STRIKE_KEY}, set(cas))
        self.assertEqual([[M.STRIKE_TEXT]], cas[M.STRIKE_KEY])
        changed_lines = {M.PANEL_KEYS["leader"]: {0, 1}, M.PANEL_KEYS["2"]: {0},
                         M.PANEL_KEYS["3"]: {0, 1, 3}, M.PANEL_KEYS["5"]: {0}}
        for key, lines in changed_lines.items():
            old = self.live("cas", key)[0][0].split("\n")
            new = cas[key][0][0].split("\n")
            self.assertEqual(len(old), len(new), key)
            self.assertEqual(lines, {i for i, (a, b) in enumerate(zip(old, new)) if a != b}, key)
            self.assertEqual(M.PANEL_AFTER[key], cas[key][0][0])
            self.assertNotIn("能力伤害", cas[key][0][0])
            self.assertNotIn("／", cas[key][0][0])
            self.assertEqual([], K.panel_text_problems(cas[key][0][0]), key)
        self.assertEqual("雷属性共鸣时，除自身外的雷属性角色发动技能时，除自身外的雷属性角色技能槽＋5%（CT：5秒）",
                         cas[M.PANEL_KEYS["leader"]][0][0].split("\n")[1])
        self.assertEqual("雷属性共鸣时，雷属性角色发动技能时，对全体敌人造成20倍雷属性技能伤害（CT：5秒）",
                         cas[M.PANEL_KEYS["2"]][0][0].split("\n")[0])
        third = cas[M.PANEL_KEYS["3"]][0][0].split("\n")
        self.assertEqual(M.MAIN_ICON + "雷属性共鸣时，FEVER模式中，雷属性角色技能伤害额外乘区＋25%", third[0])
        self.assertEqual(M.MAIN_ICON + "雷属性共鸣时，非FEVER模式中，雷属性角色发动技能时，FEVER槽＋10%（CT：5秒）",
                         third[1])
        self.assertTrue(all(line.startswith(M.MAIN_ICON) for line in third))
        self.assertNotIn("<icon", cas[M.PANEL_KEYS["2"]][0][0])  # 能力 2 仍是合击可用键

    def test_main_slot_markers_still_match_rows(self):
        rows = {key: self.out["ability"].get(key) or [["x", flag]] for key, flag in
                ((M.CID + "1", "false"), (M.CID + "2", None), (M.CID + "3", None),
                 (M.CID + "4", "true"), (M.CID + "5", None), (M.CID + "6", "true"))}
        cas = {key: [[K.MAIN_ICON + "x"]] if key == K.CAS_KEYS[1] else [["x"]] for key in K.CAS_KEYS}
        cas.update(self.out["cas"])
        self.assertEqual([], K.main_slot_panel_problems(rows, cas))

    # ---------------------------------------------------------------- 契约
    def test_only_changed_keys_are_returned(self):
        norm = lambda v: json.loads(json.dumps(v, ensure_ascii=False))   # tuple/list 归一后比较
        for kind in ("ability", "leader", "cas", "text", "action", "dsl", "server_text", "table"):
            for key, value in self.out[kind].items():
                if (kind, key) in self.data:
                    self.assertNotEqual(norm(self.data[kind, key]), norm(value), (kind, key))
                else:
                    self.assertIn((kind, key), (("cas", M.STRIKE_KEY), ("dsl", M.STRIKE_PROGRAM)))

    def test_baseline_drift_is_rejected_and_inputs_are_not_mutated(self):
        snapshot = deepcopy(self.data)
        M.revise(reader(self.data))
        self.assertEqual(snapshot, self.data)
        for (kind, key) in M.BEFORE:
            drifted = deepcopy(self.data)
            value = drifted[kind, key]
            if kind == "dsl":
                value[1] = 3
            elif kind == "action":
                value[0][1][4] = "601"
            else:
                value[0][0] = value[0][0] + "x"
            with self.assertRaisesRegex(ValueError, "drifted"):
                M.revise(reader(drifted))

    def test_transforms_are_idempotent_and_reject_unreviewed_shapes(self):
        out = self.out
        self.assertEqual(out["leader"][M.CID], M.leader_rows(out["leader"][M.CID]))
        self.assertEqual(out["ability"][M.CID + "2"], M.strike_rows(out["ability"][M.CID + "2"]))
        self.assertEqual(out["ability"][M.CID + "3"], M.third_rows(out["ability"][M.CID + "3"]))
        self.assertEqual(out["ability"][M.CID + "5"], M.fifth_rows(out["ability"][M.CID + "5"]))
        for program in (L1, L2):
            self.assertEqual(out["dsl"][program], M.skill_tree(out["dsl"][program]))
        for key in M.PANEL_KEYS.values():
            self.assertEqual(out["cas"][key][0][0], M.panel_text(key, out["cas"][key][0][0]))
        half = deepcopy(self.live("dsl", L1))
        half[10] = 0                                          # 半转换态：必须拒绝
        with self.assertRaisesRegex(ValueError, "unreviewed"):
            M.skill_tree(half)
        other = self.live("leader", M.CID)
        other[2][28] = other[2][29] = "3000000"
        with self.assertRaisesRegex(ValueError, "drift"):
            M.leader_rows(other)
        with self.assertRaisesRegex(ValueError, "drift"):
            M.panel_text(M.PANEL_KEYS["2"], "别的文案")
        with self.assertRaisesRegex(ValueError, "drift"):
            M.description("别的描述")


class GeneratorConsistencyTest(unittest.TestCase):
    """kit 走「浪涌 → 本批」同一组函数，产物必须 == revise()。"""

    @classmethod
    def setUpClass(cls):
        cls.data, cls.template_up = load()
        cls.out = M.revise(reader(cls.data))
        cls.surge = json.loads(SURGE_FIXTURE.read_bytes())

    def test_kit_rows_after_surge_match_revise(self):
        leader, third = R.revise_rows(self.surge["139994"], self.surge["1399943"], self.surge["1399941"])
        ability = {M.CID + s: deepcopy(self.data["ability", M.CID + s]) for s in ("2", "5")}
        ability[M.CID + "3"] = third
        leader, ability = K.balance_rows(leader, ability)
        self.assertEqual(self.out["leader"][M.CID], leader)
        self.assertEqual(self.out["ability"], ability)

    def test_kit_skill_trees_after_surge_match_revise(self):
        matched = set()
        for source in self.surge["regis"]:
            surged = R.revise_skill(source)
            for level, program in M.SKILL_PROGRAMS.items():
                if surged == self.data["dsl", program]:
                    self.assertEqual(self.out["dsl"][program], M.skill_tree(surged))
                    matched.add(level)
        self.assertEqual({"1", "2"}, matched)

    def test_kit_panel_description_upskill_match_revise(self):
        cas = {key: deepcopy(self.data["cas", key]) for key in M.PANEL_KEYS.values()}
        cas[K.CAS_KEYS[4]] = [["雷属性角色攻击力＋100%"]]      # 不相关键原样透传
        panel = K.balance_panel(cas)
        self.assertEqual(cas[K.CAS_KEYS[4]], panel.pop(K.CAS_KEYS[4]))
        self.assertEqual(self.out["cas"], panel)
        self.assertEqual(self.out["text"][M.CID][0][5], M.description(R.DESCRIPTION))
        old_up = [["ability_damage_up" if c == "skill_damage_up" else c for c in self.template_up[0]]]
        self.assertEqual(self.data["table", (M.UPSKILL, M.CID)], old_up)   # kit 接受的旧形态 = live
        self.assertEqual(self.out["table"][(M.UPSKILL, M.CID)], M.upskill_rows(old_up))

    def test_kit_desc_coverage_and_spec_claims(self):
        trees = [self.out["dsl"][p] for p in (L1, L2)]
        up = self.out["table"][(M.UPSKILL, M.CID)][0]
        self.assertEqual([], K.skill_desc_coverage_problems(trees, M.DESCRIPTION, up))
        self.assertTrue(K.skill_desc_coverage_problems(trees, R.DESCRIPTION, up))   # 旧说明不再对得上
        self.assertEqual(("技能伤害", "skill_damage_up"), K.SKILL_DESC_EFFECTS["ACSkillDamage"])
        self.assertEqual(("能力伤害", "ability_damage_up"), K.SKILL_DESC_EFFECTS["ACAbilityDamage"])
        self.assertIn(M.STRIKE_KEY, K.SPEC["extra_keys"][K.CAS])
        self.assertEqual((K.CID, K.CODE), (M.CID, M.CODE))

    def test_kit_build_applies_balance_after_surge(self):
        src = inspect.getsource(K.build)
        self.assertLess(src.index("surge.revise_rows("), src.index("balance_rows("))
        self.assertLess(src.index("surge.revise_skill("), src.index("balance.skill_tree("))
        self.assertLess(src.index("surge.revise_text("), src.index("balance_panel("))
        self.assertIn("balance.description(surge.DESCRIPTION)", src)
        self.assertIn("ctx.write_dsl(balance.STRIKE_PROGRAM", src)
        self.assertIn("balance.upskill_rows(", src)

    @unittest.skipUnless((ROOT / K.REVISION_REL).is_file(), "seasonal7 revision plan (gitignored work/) absent")
    def test_kit_chain_from_plan_matches_revise(self):
        revision = K.revision_rows(K.load_revision(ROOT))
        leader = [e["row_built"] for e in revision["leader"]]
        ability = {f"{K.CID}{slot[4:]}": [e["row_built"] for e in entries]
                   for slot, entries in revision["abilities"].items()}
        leader, ability[K.CID + "3"] = R.revise_rows(leader, ability[K.CID + "3"], ability[K.CID + "1"])
        leader, ability = K.balance_rows(leader, ability)
        self.assertEqual(self.out["leader"][M.CID], leader)
        for key, rows in self.out["ability"].items():
            self.assertEqual(rows, ability[key], key)
        cas = {item["key"]: [[item["text"]]] for item in revision["custom_strings"]}
        for slot, key in ((0, K.CAS_KEYS[0]), (3, K.CAS_KEYS[3])):
            cas[key][0][0] = R.revise_text(slot, cas[key][0][0])
        cas = K.balance_panel(cas)
        for key, cells in self.out["cas"].items():
            self.assertEqual(cells, cas[key], key)
        self.assertEqual([], K.main_slot_panel_problems(ability, cas))


if __name__ == "__main__":
    unittest.main()
