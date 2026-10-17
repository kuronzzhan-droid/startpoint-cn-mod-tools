# -*- coding: utf-8 -*-
"""杰拉德 149999 ``white_wolf_gerald`` 2026-09-27 第二批追加（作者 09-27 追加，``wf_balance_20260927b_gerald2``）。

fixture = live 1.4.1051 输入快照（``fixtures/balance_20260927b_gerald2.json``，第二批已发布），驱动 ``revise()``：
A 技能强化 536 已在队长 #11、能力里 0 条（核对，不返回 leader/ability）；B 技能两档 Bind 上限 10 → 2147483647.0，
与第二批改前（``fixtures/balance_20260927b_gerald_wolf.json`` 的输入）连类型逐字相同、重编码同哈希；C 斩杀分支已存在
且逐节点不动；D 技能强化文案无数字、称固定伤害，技能描述 5 处追加带数字的「强化后」段；BEFORE 漂移拒绝；不改输入；
对自身输出重跑拒绝；合法性门禁与四道 DSL 门禁为空；``wf_gerald_cast_growth`` 重跑 == 本模块输出；
候选工作区干跑拼接（需要本机工作区，缺时跳过）。
"""
from __future__ import annotations

from wf.paths import root_path

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[2]
pass  # Imports resolve from this checkout/package, not external source copies.

import wf_balance_20260927b_gerald2 as M  # noqa: E402
import wf_balance_20260927b_gerald_wolf as B2  # noqa: E402
import wf_client_legality as L  # noqa: E402
import wf_describe as D  # noqa: E402
import wf_dsl  # noqa: E402
import wf_gerald_cast_growth as G  # noqa: E402
import wf_gerald_percent_revision as PR  # noqa: E402
import wf_gerald_percent_skill as P  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
from wf_character_revision import encode_tree  # noqa: E402

FIXTURE = Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927b_gerald2.json'
BATCH2_FIXTURE = Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927b_gerald_wolf.json'
WORKSPACE = ROOT / "work/character_packs" / M.PACKAGES[0]
CAPTURED_0925 = Path(('${WF_ROOT}/out/风巨蜥与校园希尔媞调整-20260925/before/live/common'.replace("${WF_ROOT}", str(root_path()))))
SKILLS = M.SKILLS
BIND_CAP = M.BIND_PATH + (M.CAP_ARG,)


def _key(kind, key):
    return "|".join(key) if kind == "table" else key


def load():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    inputs = {kind: value for kind, value in data.items() if not kind.startswith("_")}
    return inputs, data["_context"], data["_dsl_raw_sha256"]


def reader(inputs, extra_cas=None):
    def read(kind, key):
        if kind == "cas" and extra_cas and key in extra_cas:
            return extra_cas[key]
        bucket = inputs.get(kind, {})
        if _key(kind, key) not in bucket:
            raise KeyError(key)
        return bucket[_key(kind, key)]
    return read


def tree_diff(old, new, path=()):
    """[(路径, 旧, 新)]：连类型一起比（2147483647.0 与 10 / 2147483647 视为不同）。"""
    if isinstance(old, list) and isinstance(new, list) and len(old) == len(new):
        return [d for i, (a, b) in enumerate(zip(old, new)) for d in tree_diff(a, b, path + (i,))]
    if isinstance(old, dict) and isinstance(new, dict) and old.keys() == new.keys():
        return [d for k in old for d in tree_diff(old[k], new[k], path + (k,))]
    return [] if (type(old) is type(new) and old == new) else [(path, old, new)]


def strip_cast_growth(tree):
    """技能树 → cast_growth 之前的形态：去掉强化分支首两条（Bind + 时空侵蚀 +1），比例伤害回到 5%。"""
    result = deepcopy(tree)
    enhanced = B2._at(result, M.BIND_PATH[:-4])[2]
    assert enhanced[1][0][1][0] == "BindConditionAccumulationVariable"
    assert enhanced[1][1][1][0] == "CreateCondition"
    del enhanced[1][0:2]
    strikes = [n for _p, n in B2._walk(result) if n and n[0] == "CreateRatioAttack" and len(n[3]) == 2]
    assert len(strikes) == 1
    strikes[0][3] = [{"min": 0.05, "max": 0.05}]
    return result


def batch2_inputs():
    return json.loads(BATCH2_FIXTURE.read_text(encoding="utf-8"))


class ReviseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs, cls.context, cls.raw_sha = load()
        cls.out = M.revise(reader(deepcopy(cls.inputs)))
        cls.leader = cls.inputs["leader"][M.CID]

    # ------------------------------------------------------------ 契约

    def test_fixture_is_the_reviewed_baseline(self):
        for (kind, key), want in M.BEFORE.items():
            self.assertEqual(M.digest(self.inputs[kind][_key(kind, key)]), want, (kind, key))
        self.assertEqual({(kind, key) for kind, keys in self.inputs.items() for key in keys},
                         {(kind, _key(kind, key)) for kind, key in M.BEFORE})
        self.assertIn(M.LEADER_PANEL_KEY, self.context["cas_absent"])
        # live 技能两档 = 第二批输出（Bind 上限 10）。
        b2 = batch2_inputs()
        b2_out = B2.revise(reader(deepcopy({k: v for k, v in b2.items() if not k.startswith("_")})))
        for program in SKILLS:
            self.assertEqual(tree_diff(self.inputs["dsl"][program], b2_out["dsl"][program]), [], program)
        self.assertEqual(self.inputs["leader"][M.CID], b2_out["leader"][M.CID])

    def test_module_contract_exports(self):
        self.assertEqual((M.CID, M.CODE), ("149999", "white_wolf_gerald"))
        self.assertEqual(M.PACKAGES, ["white_wolf_gerald"])
        self.assertEqual(M.PACKAGE_VERSION, {"white_wolf_gerald": "0.20260927.1"})   # 候选现值 0.20260927
        self.assertEqual((M.CAPABILITIES, M.REVIEWED_DRIFT), ([], {}))
        self.assertEqual(M.ELEMENT, 4)
        notes = self.out["notes"]
        json.dumps(notes, ensure_ascii=False)
        self.assertFalse(notes["runtime_verified"])
        self.assertIn("作者 2026-09-27 追加", notes["spec"])
        self.assertNotIn("blocked", notes)
        for key in (M.CAS_KEY,):
            self.assertTrue(key.startswith("change_skill_" + M.CODE))       # 候选命名空间

    def test_only_changed_keys_are_returned(self):
        out = self.out
        for kind in ("ability", "leader", "table"):
            self.assertEqual(out[kind], {}, kind)
        self.assertEqual(set(out["cas"]), {M.CAS_KEY})
        self.assertEqual(set(out["text"]), {M.CID})
        self.assertEqual(set(out["server_text"]), {M.CID})
        self.assertEqual(set(out["action"]), {M.CODE})
        self.assertEqual(set(out["dsl"]), set(SKILLS))
        self.assertEqual(out["new_programs"], [])

    # ------------------------------------------------------------ A：536 已在队长

    def test_a_skill_flag_is_only_in_the_leader(self):
        abilities = {key: self.inputs["ability"][key] for key in M.ABILITY_KEYS}
        self.assertEqual(M.skill_flag_rows(self.leader, abilities), [(f"leader:{M.CID}", 11)])
        row = self.leader[11]
        self.assertEqual({c: v for c, v in enumerate(row) if v}, {c: v for c, v in M.FLAG_CELLS.items() if v})
        self.assertEqual((row[4], row[7], row[9], row[45], row[68]),
                         ("2", "600000", "White", "536", "change_skill_white_wolf_gerald"))
        for key, rows in abilities.items():
            self.assertFalse([r for r in rows if r[47] in ("536", "704")], key)
        self.assertEqual(len(self.leader), 12)
        # 队长行 = [能力行 c0, "0", ""] + 能力行[5:]：由 09-25 relocate 生成，逆推回能力形态再搬一次得到同一行。
        a3 = [["black_wolf_knight_3", "false", "attack_red", "0", ""] + row[3:]]
        rift = self.leader[10]
        a2 = [["black_wolf_knight_2", "false", "attack_red", "0", ""] + rift[3:]]
        _a2, _a3, leaders = G.relocate(a2, a3, deepcopy(self.leader[:10]))
        self.assertEqual((_a2, _a3, leaders), ([], [], self.leader))
        self.assertIn("已在队长", self.out["notes"]["a_skill_flag_in_leader"]["status"])

    def test_a_guards_fail_closed(self):
        abilities = {key: deepcopy(self.inputs["ability"][key]) for key in M.ABILITY_KEYS}
        moved = deepcopy(abilities)
        moved[M.CID + "3"].append(["black_wolf_knight_3", "false", "attack_red", "0", ""] + self.leader[11][3:])
        with self.assertRaisesRegex(ValueError, "skill flag rows moved"):
            M.check_flag_in_leader(self.leader, moved)
        drifted = deepcopy(self.leader)
        drifted[11][9] = "Black"
        with self.assertRaisesRegex(ValueError, "536 row"):
            M.check_flag_in_leader(drifted, abilities)
        with self.assertRaises(ValueError):
            M.check_flag_in_leader(self.leader[:11], abilities)

    def test_leader_flag_row_panel_is_auto_generated_and_legal(self):
        row = self.leader[11]
        cas_keys = {M.CAS_KEY}
        self.assertEqual(L.client_legality_problems("leader_ability", row), [])
        self.assertEqual(L.declared_block_field_problems("leader_ability", row), [])
        self.assertEqual(L.invoke_skill_string_problems(row, cas_keys, "leader_ability"), [])
        self.assertEqual(L.required_client_capabilities("leader_ability", row), [])
        self.assertEqual(KL.row_problems("leader_ability", row), {})
        lines = D.describe_rows(self.leader, "leader_ability")
        self.assertEqual(lines[11], "光·编成≥6 时: 自身 切换技能形态[change_skill_white_wolf_gerald]")
        for line in lines:
            self.assertEqual(KL.panel_problems(line), [], line)

    # ------------------------------------------------------------ B：撤回封顶

    def test_b_bind_cap_is_the_only_dsl_change(self):
        for program in SKILLS:
            old, new = self.inputs["dsl"][program], self.out["dsl"][program]
            self.assertEqual(tree_diff(old, new), [(BIND_CAP, 10, 2147483647.0)], program)
            self.assertIs(type(B2._at(new, M.BIND_PATH)[5]), float)
            self.assertEqual(B2._at(new, M.BIND_PATH),
                             ["BindConditionAccumulationVariable", -17, 360, ["DCUnique", 14999903], 1, 2147483647.0])

    def test_b_restores_the_pre_batch2_tree_and_bytes(self):
        """与第二批改前逐字相同（连类型），重编码 == 第二批改前 live 原始字节（8d323968…/f27b8a14…）。"""
        b2 = batch2_inputs()
        for program in SKILLS:
            new = self.out["dsl"][program]
            self.assertEqual(tree_diff(new, b2["dsl"][program]), [], program)
            self.assertEqual(hashlib.sha256(encode_tree(new)).hexdigest(), b2["_dsl_raw_sha256"][program], program)
        self.assertEqual([b2["_dsl_raw_sha256"][p][:8] for p in SKILLS], ["8d323968", "f27b8a14"])
        # live（第二批后）原始字节与第二批输出重编码相同（fixture 记录的是 live 原始哈希）。
        for program in SKILLS:
            self.assertEqual(hashlib.sha256(encode_tree(self.inputs["dsl"][program])).hexdigest(),
                             self.raw_sha[program], program)

    def test_b_growth_is_uncapped(self):
        """case 101：v360 = min(层数/1, 上限) ⇒ 第 n 次强化施技 5%+1%×(n−1)，不再止于 15%。"""
        for program in SKILLS:
            old, new = self.inputs["dsl"][program], self.out["dsl"][program]
            for prior, before, after in ((0, .05, .05), (1, .06, .06), (2, .07, .07), (10, .15, .15),
                                         (20, .15, .25), (95, .15, 1.0)):
                self.assertAlmostEqual(B2.skill_ratio_at(old, prior), before, msg=(program, prior))
                self.assertAlmostEqual(B2.skill_ratio_at(new, prior), after, msg=(program, prior))
        notes = self.out["notes"]["b_growth_uncapped"]
        self.assertEqual(notes["examples"], {"1": .05, "2": .06, "3": .07, "11": .15, "21": .25})
        self.assertIn("不封顶", notes["before_after"])
        # 计数固有本身未封（c4 2147483647）、永久（c3 99999999 帧）。
        counter = self.inputs["table"]["|".join(M.COUNTER_TABLE)]
        self.assertEqual(counter, G.counter_row())
        self.assertEqual((counter[0][3], counter[0][4]), ("99999999", "2147483647"))

    # ------------------------------------------------------------ C：斩杀已存在

    def test_c_execute_branch_exists_and_is_untouched(self):
        for program in SKILLS:
            old, new = self.inputs["dsl"][program], self.out["dsl"][program]
            path, check = M.execute_branch(new)
            self.assertEqual(M.execute_branch(old), (path, check))
            self.assertEqual(check[1:3], [301, 5])                            # 最近敌人、最大生命值 5%
            self.assertEqual(check[4], ["Block", [["Command", ["CreateRatioAttack", 301, 1, [{"min": 1.0, "max": 1.0}]]]]])
            self.assertEqual(check[3][1][0][1], B2.RATIO_STRIKE)
            self.assertEqual(B2._at(new, path[:-4])[:6], ["FindNearSubjects", -18, 1, 49, ["DoNothing"], 301])
            self.assertEqual(M.skill_numbers(new), {"base": .05, "per_cast": .01, "execute_below": 5})
            # 普通分支（旗号关 = 非队长或非光共鸣）没有比例伤害、成长与斩杀。
            _flag, _enhanced, plain = M.enhanced_branches(new)
            for name in ("CreateRatioAttack", "ConditionalsHealthPointRatioOf", "BindConditionAccumulationVariable"):
                self.assertFalse(M._nodes(plain, name), (program, name))
        self.assertEqual(P.metadata()["execute_below_max_hp_percent"], 5)
        self.assertEqual(P.metadata()["threshold_comparison"], "strictly less than")
        self.assertIn("已存在", self.out["notes"]["c_execute"]["status"])

    def test_skill_guards_fail_closed(self):
        base = self.inputs["dsl"][SKILLS[0]]
        cases = []
        t = deepcopy(base); B2._at(t, M.BIND_PATH)[5] = 20; cases.append(t)                       # 别的上限
        t = deepcopy(base); B2._at(t, M.BIND_PATH)[5] = 2147483647; cases.append(t)               # 已撤回（int）
        t = deepcopy(base); B2._at(t, M.BIND_PATH)[5] = 2147483647.0; cases.append(t)             # 已撤回（float）
        t = deepcopy(base); B2._at(t, M.BIND_PATH)[5] = 10.0; cases.append(t)                     # 类型漂移
        t = deepcopy(base); B2._at(t, M.BIND_PATH)[2] = 361; cases.append(t)                      # 变量号漂移
        path, _check = M.execute_branch(base)
        t = deepcopy(base); B2._at(t, path)[2] = 4; cases.append(t)                               # 斩杀阈值漂移
        t = deepcopy(base); B2._at(t, path)[4][1][0][1][3][0]["min"] = 0.5; cases.append(t)        # 斩杀量漂移
        t = deepcopy(base); B2._at(t, path[:-4])[1] = -17; cases.append(t)                        # 选敌原点漂移
        t = deepcopy(base)
        _f, _e, plain = M.enhanced_branches(t)
        plain[1].append(["Command", deepcopy(M.EXECUTE_STRIKE)]); cases.append(t)                   # 普通分支漏出比例伤害
        for i, tree in enumerate(cases):
            with self.assertRaises(ValueError, msg=i):
                M.skill_tree(tree)

    # ------------------------------------------------------------ D：文案

    def test_d_skill_flag_text_has_no_numbers_and_says_fixed_damage(self):
        text = self.out["cas"][M.CAS_KEY]
        self.assertEqual(text, [[M.NEW_CAS_TEXT]])
        self.assertEqual(self.inputs["cas"][M.CAS_KEY], [[M.OLD_CAS_TEXT]])
        self.assertEqual(KL.panel_problems(M.NEW_CAS_TEXT, skill_flag=True), [])
        self.assertFalse(any(ch.isdigit() for ch in M.NEW_CAS_TEXT))
        for word in ("固定伤害", "当前生命值", "斩杀", "技能发动次数"):
            self.assertIn(word, M.NEW_CAS_TEXT)
        for word in ("共鸣", "队长", "%", "％", "秒", "无上限", "百分比", "比例"):
            self.assertNotIn(word, M.NEW_CAS_TEXT)

    def test_d_no_resonance_prefix_because_the_client_builds_it(self):
        """客户端按前置 kind 2 拼「::element_full::共鸣」；官方同形队长 536 行（dryad_hw23 121189#2）文案不带条件。"""
        ui = self.context["ui_string"]
        self.assertEqual(ui["ability_description_instant_trigger_kind_member_element_unified"], [["::element_full::共鸣"]])
        official = self.context["official_leader_121189"][2]
        self.assertEqual((official[4], official[7], official[9], official[45], official[68]),
                         ("2", "600000", "Blue", "536", "change_skill_dryad_hw23"))
        dryad = self.context["cas"]["change_skill_dryad_hw23"][0][0]
        for word in ("共鸣", "名以上", "时，"):
            self.assertNotIn(word, dryad)

    def test_d_skill_descriptions_carry_the_numbers(self):
        segment = "／强化后：对最近的敌人追加造成其当前生命值5%的固定伤害（每次发动技能提高1%），敌人生命值低于最大生命值5%时直接斩杀"
        self.assertEqual(M.DESC_SEGMENT, segment)
        old_action, new_action = self.inputs["action"][M.CODE], self.out["action"][M.CODE]
        self.assertEqual([k for k, _f in new_action], ["1", "2"])
        for (k_old, f_old), (k_new, f_new) in zip(old_action, new_action):
            self.assertEqual(k_old, k_new)
            self.assertEqual({i: (a, b) for i, (a, b) in enumerate(zip(f_old, f_new)) if a != b},
                             {1: (M.OLD_ACTION_DESC, M.OLD_ACTION_DESC + segment)})
        for kind in ("text", "server_text"):
            old, new = self.inputs[kind][M.CID], self.out[kind][M.CID]
            self.assertEqual(len(new), 1)
            self.assertEqual({i: (a, b) for i, (a, b) in enumerate(zip(old[0], new[0])) if a != b},
                             {5: (M.OLD_TEXT_DESC, M.OLD_TEXT_DESC + segment),
                              7: (M.OLD_TEXT_DESC, M.OLD_TEXT_DESC + segment)}, kind)
        self.assertEqual(self.out["text"][M.CID], self.out["server_text"][M.CID])
        for text in (M.NEW_ACTION_DESC, M.NEW_TEXT_DESC):
            self.assertEqual(KL.panel_problems(text), [], text)
            self.assertEqual(text.count("固定伤害"), 1)
        # 数字与技能树一致：起始 base、每次 +per（当前生命值）、低于最大生命值 5% 斩杀。
        numbers = M.skill_numbers(self.out["dsl"][SKILLS[0]])
        self.assertIn(f"当前生命值{numbers['base']:.0%}", segment)
        self.assertIn(f"提高{numbers['per_cast']:.0%}", segment)
        self.assertIn(f"最大生命值{numbers['execute_below']}%", segment)
        self.assertEqual(M.text_gate_problems(), [])

    def test_d_no_percent_damage_wording_remains(self):
        texts = [row[0] for rows in self.context["cas"].values() for row in rows]
        texts += [M.NEW_CAS_TEXT, M.NEW_ACTION_DESC, M.NEW_TEXT_DESC]
        for text in texts:
            for word in M.PERCENT_DAMAGE_WORDS:
                self.assertNotIn(word, text)

    def test_leader_panel_override_present_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "auto-generated"):
            M.revise(reader(deepcopy(self.inputs), extra_cas={M.LEADER_PANEL_KEY: [["x"]]}))

    def test_dsl_gates_and_amf3_roundtrip(self):
        for program in SKILLS:
            tree = self.out["dsl"][program]
            self.assertEqual(B2.dsl_problems(tree), [], program)
            self.assertEqual(L.action_dsl_element_problems(tree, M.ELEMENT), [], program)
            self.assertEqual(L.action_dsl_subject_binding_problems(tree), [], program)
            self.assertEqual(L.action_dsl_lookup_scope_problems(tree), [], program)
            self.assertEqual(L.action_dsl_hit_area_target_problems(tree), [], program)
            decoded = wf_dsl.parse_dsl(zlib.decompress(encode_tree(tree), -15))["tree"]
            self.assertEqual(tree_diff(tree, decoded), [], program)       # 连类型（2147483647.0）一起往返

    # ------------------------------------------------------------ fail closed

    def test_input_is_not_mutated_and_output_is_detached(self):
        data = deepcopy(self.inputs)
        out = M.revise(reader(data))
        self.assertEqual(json.dumps(data, sort_keys=True), json.dumps(self.inputs, sort_keys=True))
        B2._at(out["dsl"][SKILLS[0]], M.BIND_PATH)[5] = "mutated"
        out["action"][M.CODE][0][1][1] = "mutated"
        out["text"][M.CID][0][5] = "mutated"
        out["server_text"][M.CID][0][7] = "mutated"
        self.assertEqual(json.dumps(data, sort_keys=True), json.dumps(self.inputs, sort_keys=True))

    def test_baseline_drift_is_rejected(self):
        for kind, key in M.BEFORE:
            drifted = deepcopy(self.inputs)
            value = drifted[kind][_key(kind, key)]
            if kind == "dsl":
                value[10] = 4
            elif kind == "action":
                value[-1][1][-1] = value[-1][1][-1] + "x"
            else:
                value[-1][-1] = value[-1][-1] + "x"
            with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
                M.revise(reader(drifted))
            missing = deepcopy(self.inputs)
            missing[kind][_key(kind, key)] = None
            with self.assertRaises(ValueError):
                M.revise(reader(missing))

    def test_revise_is_not_reapplicable_to_its_own_output(self):
        live = deepcopy(self.inputs)
        for kind in ("dsl", "cas", "action", "text", "server_text"):
            live[kind].update(deepcopy(self.out[kind]))
        with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
            M.revise(reader(live))
        for program in SKILLS:
            with self.assertRaisesRegex(ValueError, "batch-2 capped preimage"):
                M.skill_tree(self.out["dsl"][program])
        with self.assertRaisesRegex(ValueError, "reviewed text"):
            M.revise_action(self.out["action"][M.CODE])
        with self.assertRaisesRegex(ValueError, "reviewed text"):
            M.revise_text_row(self.out["text"][M.CID], "text")


class GeneratorTests(unittest.TestCase):
    """生成器同步：cast_growth 常量与 rewrite() == 本模块输出；percent 两个生成器重跑 fail closed。"""

    @classmethod
    def setUpClass(cls):
        cls.inputs, cls.context, _ = load()
        cls.out = M.revise(reader(deepcopy(cls.inputs)))

    def test_cast_growth_constants_match_the_revision(self):
        self.assertEqual(G.COUNTER_CAP, M.CAP_RESTORED)
        self.assertIs(type(G.COUNTER_CAP), float)
        self.assertEqual((G.COUNTER_UID, G.COUNTER_VARIABLE, G.CONDITION_KEY),
                         (B2.COUNTER_UID, B2.COUNTER_VARIABLE, B2.COUNTER_KEY))
        # 第三轮（wf_balance_20260927c_gerald_wolf，作者「技能里面不要重复描述强化后的效果」）以本模块的强化条目为输入
        # 点明技能名；生成器常量跟第三轮走。
        import wf_balance_20260927c_gerald_wolf as M3
        self.assertEqual(M3.OLD_CAS_FLAG_TEXT, M.NEW_CAS_TEXT)
        self.assertEqual(G.ENHANCEMENT_TEXT, M3.NEW_CAS_FLAG_TEXT)
        self.assertEqual(G.counter_row(), M.COUNTER_ROW)

    def test_cast_growth_rewrite_equals_revise_output(self):
        for program in SKILLS:
            pre = strip_cast_growth(self.inputs["dsl"][program])
            regenerated = G.rewrite(pre)
            self.assertEqual(tree_diff(regenerated, self.out["dsl"][program]), [], program)
            self.assertEqual(encode_tree(regenerated), encode_tree(self.out["dsl"][program]), program)

    @unittest.skipUnless(CAPTURED_0925.is_dir(), "local 2026-09-25 captured live resources required")
    def test_cast_growth_rewrite_on_captured_input_equals_revise_output(self):
        for level, program in zip((1, 2), SKILLS):
            raw = (CAPTURED_0925 / P.ACTIVE_PATHS[level]).read_bytes()
            captured = wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]
            self.assertEqual(tree_diff(G.rewrite(captured), self.out["dsl"][program]), [], program)
            self.assertEqual(strip_cast_growth(self.inputs["dsl"][program]), captured)

    def test_generators_refuse_revised_inputs(self):
        for level, program in zip((1, 2), SKILLS):
            with self.assertRaisesRegex(ValueError, "ratio baseline changed|unexpected existing variable binding"):
                G.rewrite(self.out["dsl"][program])
            for tree in (self.inputs["dsl"][program], self.out["dsl"][program]):
                with self.assertRaises(ValueError):
                    P.patch_skill_bytes(encode_tree(tree), level)
        self.assertEqual(PR.STRING_KEY, M.CAS_KEY)
        for text in (M.OLD_CAS_TEXT, M.NEW_CAS_TEXT):
            with self.assertRaises(ValueError):
                PR.description(text)


@unittest.skipUnless((WORKSPACE / "package/manifest.json").is_file()
                     and (ROOT / "mod-tools/profiles.json").is_file(),
                     "local candidate workspace required")
class CandidateTests(unittest.TestCase):
    """候选 white_wolf_gerald：零漂移；本模块读取的键与 live 相同（服务端镜像旧文除外），干跑拼接只动这些文件。"""

    TABLES = {"cas": "master/string/custom_ability_string.orderedmap",
              "text": "master/character/character_text.orderedmap"}
    ACTION = "master/skill/action_skill.orderedmap"
    SERVER = "cdndata/character_text.json"

    @classmethod
    def setUpClass(cls):
        cls.inputs, cls.context, _ = load()
        cls.out = M.revise(reader(deepcopy(cls.inputs)))

    def _candidate(self):
        from wf_character_revision import RevisionCandidate
        return RevisionCandidate(ROOT, WORKSPACE, character_id=M.CID, code_name=M.CODE,
                                 snapshot_key="revision_20260927b", reviewed_input_drift=M.REVIEWED_DRIFT,
                                 package_version=M.PACKAGE_VERSION[M.PACKAGES[0]],
                                 baseline_factory=lambda *a, **k: None)

    def _tree(self, candidate, program):
        return wf_dsl.parse_dsl(zlib.decompress(candidate.read("common", wf_dsl.dsl_logical(program)), -15))["tree"]

    def test_candidate_splices_only_the_reviewed_files_dry(self):
        import wf_mod_tool as C
        import wf_share_update_codec as X
        manifest = WORKSPACE / "package/manifest.json"
        before = manifest.read_bytes()
        version = lambda text: tuple(map(int, text.split(".")))
        current = json.loads(before)["package_version"]
        mine = M.PACKAGE_VERSION[M.PACKAGES[0]]
        candidate = self._candidate()
        state = "inputs" if version(mine) > version(current) else "out"
        want = self.inputs if state == "inputs" else self.out
        # 第三轮（wf_balance_20260927c_gerald_wolf）回写后：强化条目与技能说明 = 第三轮以本模块输出为输入的结果。
        import wf_balance_20260927c_gerald_wolf as M3
        if version(current) >= version(M3.PACKAGE_VERSION[M3.PACKAGES[0]]):
            state = "c"
            want = dict(self.out, **M3.skill_text_outputs({
                ("cas", M.CAS_KEY): self.out["cas"][M.CAS_KEY], ("action", M.CODE): self.out["action"][M.CODE],
                ("text", M.CID): self.out["text"][M.CID], ("server_text", M.CID): self.out["server_text"][M.CID]}))
        for program in SKILLS:
            self.assertEqual(tree_diff(self._tree(candidate, program), want["dsl"][program]), [], (state, program))
        cas = X.unpack(candidate.read("common", self.TABLES["cas"]))
        self.assertEqual(X.csv_read(cas[M.CAS_KEY]), want["cas"][M.CAS_KEY])
        text = X.unpack(candidate.read("common", self.TABLES["text"]))
        self.assertEqual(X.csv_read(text[M.CID]), want["text"][M.CID])
        action = C.decode_action_skill_row(X.unpack(candidate.read("common", self.ACTION))[M.CODE])
        self.assertEqual(json.dumps(action, ensure_ascii=False), json.dumps(want["action"][M.CODE], ensure_ascii=False))
        server = json.loads(candidate.read("server", self.SERVER))[M.CID]
        if state == "inputs":
            # 服务端镜像旧文：只有 [5]/[6]/[7] 与 live 不同（见 CANDIDATE_STALE_SERVER_MIRROR）。
            live = self.inputs["server_text"][M.CID][0]
            self.assertEqual([i for i, (a, b) in enumerate(zip(server[0], live)) if a != b],
                             list(M.CANDIDATE_STALE_SERVER_MIRROR["differing_columns"]))
            self.assertEqual(server[0][6], M.CANDIDATE_STALE_SERVER_MIRROR["cells"]["6"][0])
        else:
            self.assertEqual(server, want["server_text"][M.CID])
        # 干跑拼接：只动这 5 个文件，manifest 不落盘。
        candidate = self._candidate()
        for kind, logical in self.TABLES.items():
            candidate.splice(logical, self.out[kind])
        candidate.splice(self.ACTION, {M.CODE: C.encode_action_skill_row(self.out["action"][M.CODE])},
                         codec="action_nested")
        for program in SKILLS:
            candidate.emit("common", wf_dsl.dsl_logical(program), encode_tree(self.out["dsl"][program]))
        candidate.server_character_row(self.SERVER, self.out["server_text"][M.CID])
        evidence = candidate.finish({"dry_run": True}, apply=False)
        self.assertFalse(evidence["applied"])
        self.assertEqual(sorted((f["root"], f["logical_path"]) for f in evidence["changed_files"]),
                         sorted([("common", self.TABLES["cas"]), ("common", self.TABLES["text"]),
                                 ("common", self.ACTION), ("server", self.SERVER),
                                 *(("common", wf_dsl.dsl_logical(p)) for p in SKILLS)]))
        self.assertEqual(before, manifest.read_bytes())


if __name__ == "__main__":
    unittest.main()
