# -*- coding: utf-8 -*-
"""澄波响 169988 ``psychic_teleport_moon`` 2026-09-27 第二批平衡：回响无上限成长搬队长 + 629 追击削韧 25→1。

fixture = live 输入快照（``fixtures/balance_20260927b_hibiki.json``，make_read(live_only=True) 导出），
驱动 ``revise()``：每处改动的前后值、未改行/未改树节点逐字保留、BEFORE 漂移拒绝、不改输入、
对自身输出重跑拒绝、合法性门禁为空、DSL AMF3 往返与四道门禁、面板规则、生成器一致、跨角色 donor
（菲莉亚 159996#3）钉住、设计镜像已同步、候选 dry-run 回写。需要 ``.cdn/cn`` 官方基线与 live store 的用例缺时跳过。
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_balance_20260927b_hibiki as M  # noqa: E402
import wf_client_legality as L  # noqa: E402
import wf_describe as D  # noqa: E402
import wf_dsl  # noqa: E402
import wf_midautumn_kit_hibiki as K  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_mod_tool as core  # noqa: E402
from wf_character_revision import encode_tree  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).parent / "fixtures/balance_20260927b_hibiki.json"
WORKSPACE = ROOT / "work/character_packs" / M.PACKAGES[0]
#: 候选 ma-hibiki manifest 现有的 required_capabilities（改后不新增）。
CANDIDATE_CAPABILITIES = {"dash-parameter-v1", "panel-description-override-v2", "damage-type-rules-v1"}


def _key(kind, key):
    return "|".join(key) if kind == "table" else key


def load_fixture() -> dict:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return {kind: value for kind, value in data.items() if not kind.startswith("_")}


def reader(data: dict):
    def read(kind, key):
        return data[kind][_key(kind, key)]
    return read


def _baseline_available() -> bool:
    profile = core.resolve_profile()
    return profile is not None and profile.store.is_dir() and (ROOT / ".cdn" / "cn").is_dir()


C_FIXTURE = Path(__file__).parent / "fixtures/balance_20260927c_hibiki.json"
#: 第三轮（``wf_balance_20260927c_hibiki``，成长复核）已把生成器的队长成长推进到 c 值：生成器一致性按
#: 「第二批输出 + 第三轮覆盖」核对（b → c 两种状态都接受；逐格断言与设计镜像同步由 c 测试接管）。
GENERATOR_AT_C = K.ECHO_LEADER_STEP != M.ECHO_LEADER


def batch3_output(out: dict) -> dict:
    """第二批输出里被第三轮改写的键换成第三轮输出（c fixture == 第二批输出，见 c 测试），其余原样。"""
    import wf_balance_20260927c_hibiki as C
    data = {k: v for k, v in json.loads(C_FIXTURE.read_text(encoding="utf-8")).items() if not k.startswith("_")}
    c_out = C.revise(lambda kind, key: data[kind][key])
    merged = deepcopy(out)
    for kind, table in c_out.items():
        if kind != "notes" and isinstance(table, dict):
            merged.setdefault(kind, {}).update(deepcopy(table))
    return merged


def generator_target(out: dict) -> dict:
    return batch3_output(out) if GENERATOR_AT_C else out


_CTX = None


def _kit_ctx():
    global _CTX
    if _CTX is None:
        import wf_midautumn_common as MC
        import wf_midautumn_specs as MS
        import wf_seasonal7_build as B
        _CTX = B.KitContext(MC.MAPack(MS.get_spec("hibiki"), record_sources=False))
    return _CTX


def _diff(a: list[str], b: list[str]) -> dict[int, tuple[str, str]]:
    return {col: (x, y) for col, (x, y) in enumerate(zip(a, b)) if x != y}


def _mask_p13(tree):
    masked = deepcopy(tree)
    for cna in wf_dsl.iter_dsl_commands(masked, "CreateNormalAttack"):
        cna[13] = None
    return masked


class ReviseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))
        cls.old_leader = cls.live["leader"][M.LEADER_KEY]
        cls.new_leader = cls.out["leader"][M.LEADER_KEY]
        cls.old_tree = cls.live["dsl"][M.INVOKE_PROGRAM]
        cls.new_tree = cls.out["dsl"][M.INVOKE_PROGRAM]

    # ------------------------------------------------------------ 契约
    def test_fixture_is_the_reviewed_baseline(self):
        for (kind, key), want in M.BEFORE.items():
            self.assertEqual(M.digest(self.live[kind][_key(kind, key)]), want, f"{kind}:{key}")
        self.assertEqual({(kind, key) for kind, keys in self.live.items() for key in keys},
                         {(kind, _key(kind, key)) for kind, key in M.BEFORE})

    def test_module_contract_exports(self):
        self.assertEqual((M.CID, M.CODE), (str(K.CID), K.CODE))
        self.assertEqual(M.PACKAGES, ["ma-hibiki"])
        self.assertEqual(M.PACKAGE_VERSION, {"ma-hibiki": "1.0.1"})   # 候选现值 1.0.0，只升不降
        self.assertEqual(M.CAPABILITIES, [])
        self.assertEqual(M.REVIEWED_DRIFT, {})
        self.assertEqual((M.UID, M.UNIQUE_CAP, M.INVOKE_PROGRAM), (K.UID, K.UNIQUE_CAP, K.INVOKE_PROGRAM))
        self.assertEqual((M.CAS_LEADER, M.CAS_SLOT3, M.CAS_SLOT4),
                         (K.CAS_LEADER, K.CAS_ABILITY[3], K.CAS_ABILITY[4]))
        self.assertEqual(M.CAS_INVOKE, (K.CAS_INVOKE_SKILL, K.CAS_INVOKE_DASH))
        self.assertEqual((M.ELEMENT, M.MAIN_ICON, M.INVOKE_BTA), (K.ELEMENT, K.MAIN_ICON, K.INVOKE_BTA))

    def test_only_changed_keys_are_returned(self):
        out = self.out
        self.assertEqual(set(out["ability"]), {M.ABILITY3, M.ABILITY4})
        self.assertEqual(set(out["leader"]), {M.LEADER_KEY})
        self.assertEqual(set(out["cas"]), {M.CAS_LEADER, M.CAS_SLOT3, M.CAS_SLOT4})
        self.assertEqual(set(out["dsl"]), {M.INVOKE_PROGRAM})
        for kind in ("text", "table", "action", "server_text"):
            self.assertEqual(out[kind], {}, kind)
        self.assertEqual(out["new_programs"], [])        # 629 树已在候选 manifest skills.programs 里
        json.dumps(out["notes"], ensure_ascii=False)
        self.assertFalse(out["notes"]["runtime_verified"])
        for key in out["cas"]:                           # RevisionCandidate 命名空间
            self.assertTrue(key.startswith("desc_override_" + M.CODE), key)

    # ------------------------------------------------------------ 队长
    def test_leader_changes_only_row6_strength_and_appends_two_rows(self):
        old, new = self.old_leader, self.new_leader
        self.assertEqual((len(old), len(new)), (10, 12))
        self.assertTrue(all(len(r) == 124 for r in new))
        changed = {i: _diff(a, b) for i, (a, b) in enumerate(zip(old, new)) if a != b}
        self.assertEqual(changed, {6: {49: ("50000", "5000"), 50: ("50000", "5000")}})
        row = new[6]
        self.assertEqual((row[25], row[28], row[32], row[33], row[45], row[46]),
                         ("15", "400000", "(None)", "0", "32", "0"))   # 仍不限次、只给自身

    def test_moved_rows_are_the_ability_rows_shifted_by_two_columns(self):
        """口径 A.3：``[CODE, '0', ''] + 能力行[5:]``，只把强度 25% 降到 2.5%。"""
        sources = (self.live["ability"][M.ABILITY3][M.PFDMG_ROW],
                   self.live["ability"][M.ABILITY4][M.ATK_ROW])
        for moved, source, kind in zip(self.new_leader[10:], sources, ("23", "0")):
            self.assertEqual(moved[:3], [M.CODE, "0", ""])
            for col in range(5, 126):
                if col in (113, 114):
                    continue
                self.assertEqual(moved[col - 2], source[col], col)
            self.assertEqual((source[113], source[114]), ("25000", "25000"))
            self.assertEqual((moved[111], moved[112]), ("2500", "2500"))
            self.assertEqual(int(moved[111]) * 10, int(source[113]))   # ×1/10（≥30 次）
            self.assertEqual((moved[3], moved[95], moved[96], moved[98], moved[99]),
                             ("1", "134", "0", "100000", "100000"))
            self.assertEqual((moved[100], moved[102], moved[106], moved[107], moved[108]),
                             (M.UNIQUE_CAP, M.UID, "false", kind, "0"))
            self.assertEqual((moved[4], moved[11], moved[18], moved[83]), ("0", "0", "0", "(None)"))

    def test_no_merge_target_existed_in_the_leader(self):
        self.assertFalse([r for r in self.old_leader if r[3] == "1" and r[95] == "134"])
        self.assertEqual(len([r for r in self.new_leader if r[3] == "1" and r[95] == "134"]), 2)

    def test_leader_describe_readback(self):
        describe = D.describe_rows(self.new_leader, "leader_ability")
        self.assertEqual(describe[6], "强化弹射HitLv1≥4 → 自身 攻击力 5%")
        self.assertEqual(describe[10], "持续·状态累积计数固有≥1(限99次)[固有16998801] → 自身 强化弹射伤害 2.5%")
        self.assertEqual(describe[11], "持续·状态累积计数固有≥1(限99次)[固有16998801] → 自身 攻击力 2.5%")
        target = generator_target(self.out)["leader"][M.LEADER_KEY]       # 生成器跟随最新一轮
        self.assertEqual(D.describe_rows(target, "leader_ability"), [expect for _a, _s, _c, expect in K.LEADER])

    # ------------------------------------------------------------ 能力
    def test_ability3_caps_the_echo_pf_damage_row(self):
        old, new = self.live["ability"][M.ABILITY3], self.out["ability"][M.ABILITY3]
        self.assertEqual(len(new), 3)
        changed = {i: _diff(a, b) for i, (a, b) in enumerate(zip(old, new)) if a != b}
        self.assertEqual(changed, {1: {102: ("99", "10"), 113: ("25000", "10000"),
                                       114: ("25000", "10000")}})
        row = new[1]
        self.assertEqual((row[1], row[2], row[6], row[97], row[104], row[109]),
                         ("false", "power_flip", "0", "134", M.UID, "23"))   # 仅主位、无共鸣门保持

    def test_ability4_caps_the_echo_attack_row(self):
        old, new = self.live["ability"][M.ABILITY4], self.out["ability"][M.ABILITY4]
        self.assertEqual(len(new), 3)
        changed = {i: _diff(a, b) for i, (a, b) in enumerate(zip(old, new)) if a != b}
        self.assertEqual(changed, {2: {102: ("99", "10"), 113: ("25000", "5000"),
                                       114: ("25000", "5000")}})
        row = new[2]
        self.assertEqual((row[1], row[2], row[97], row[104], row[109], row[110]),
                         ("true", "attack_common", "134", M.UID, "0", "0"))

    def test_ability_describe_readback(self):
        self.assertEqual(D.describe_rows([self.out["ability"][M.ABILITY3][1]], "ability")[0],
                         "持续·状态累积计数固有≥1(限10次)[固有16998801] → 自身 强化弹射伤害 10%")
        self.assertEqual(D.describe_rows([self.out["ability"][M.ABILITY4][2]], "ability")[0],
                         "持续·状态累积计数固有≥1(限10次)[固有16998801] → 自身 攻击力 5%")

    def test_growth_math(self):
        """99 层：队长各 ＋247.5%；能力封顶 10 层 PF 伤害 ＋100%、攻击力 ＋50%；命中每 4 次 ＋5%。"""
        unique_cap = int(self.live["table"]["|".join(M.UNIQUE)][0][4])
        self.assertEqual(unique_cap, 99)
        for moved in self.new_leader[10:]:
            self.assertAlmostEqual(int(moved[111]) / 1000 * min(unique_cap, int(moved[100])), 247.5)
        pfdmg = self.out["ability"][M.ABILITY3][1]
        atk = self.out["ability"][M.ABILITY4][2]
        self.assertEqual(int(pfdmg[113]) // 1000 * int(pfdmg[102]), 100)
        self.assertEqual(int(atk[113]) // 1000 * int(atk[102]), 50)
        self.assertEqual(int(self.new_leader[6][49]) // 1000, 5)

    # ------------------------------------------------------------ 面板
    def test_panel_texts(self):
        leader = self.out["cas"][M.CAS_LEADER][0][0].split("\n")
        old = self.live["cas"][M.CAS_LEADER][0][0].split("\n")
        self.assertEqual(len(leader), 9)
        self.assertEqual(leader[6], "强化弹射每累计命中4次，自身攻击力＋5%")
        self.assertEqual(leader[7], "每1层“回响”，自身强化弹射伤害＋2.5%、攻击力＋2.5%")
        self.assertEqual(leader[:6] + leader[8:], old[:6] + old[7:])
        slot3 = self.out["cas"][M.CAS_SLOT3][0][0].split("\n")
        old3 = self.live["cas"][M.CAS_SLOT3][0][0].split("\n")
        self.assertEqual(slot3[1], M.MAIN_ICON + "每1层“回响”，自身强化弹射伤害＋10%（最多10层）")
        self.assertEqual(slot3[:1] + slot3[2:], old3[:1] + old3[2:])
        slot4 = self.out["cas"][M.CAS_SLOT4][0][0].split("\n")
        old4 = self.live["cas"][M.CAS_SLOT4][0][0].split("\n")
        self.assertEqual(slot4, old4 + ["每1层“回响”，自身攻击力＋5%（最多10层）"])

    def test_panel_agrees_with_the_data(self):
        leader = self.out["cas"][M.CAS_LEADER][0][0]
        hit = self.new_leader[6]
        self.assertIn(f"每累计命中{int(hit[28]) // 100000}次，自身攻击力＋{int(hit[49]) // 1000}%", leader)
        step = int(self.new_leader[10][111]) / 1000
        self.assertIn(f"强化弹射伤害＋{step:g}%、攻击力＋{step:g}%", leader)
        pfdmg, atk = self.out["ability"][M.ABILITY3][1], self.out["ability"][M.ABILITY4][2]
        self.assertIn(f"强化弹射伤害＋{int(pfdmg[113]) // 1000}%（最多{pfdmg[102]}层）",
                      self.out["cas"][M.CAS_SLOT3][0][0])
        self.assertIn(f"攻击力＋{int(atk[113]) // 1000}%（最多{atk[102]}层）",
                      self.out["cas"][M.CAS_SLOT4][0][0])

    def test_panel_texts_obey_the_project_rules(self):
        for key, main_only in ((M.CAS_LEADER, False), (M.CAS_SLOT3, True), (M.CAS_SLOT4, False)):
            text = self.out["cas"][key][0][0]
            self.assertNotIn("／", text)
            self.assertEqual(M.panel_problems(key, text, main_only), [], key)
            for line in text.split("\n"):
                self.assertEqual(line.startswith(M.MAIN_ICON), main_only, line)
                self.assertEqual(KL.panel_problems(line.replace(M.MAIN_ICON, "")), [], line)
            self.assertEqual(L.panel_override_capability(key), "panel-description-override-v2")
        for word in ("最多99层", "可无限", "无上限"):
            self.assertNotIn(word, self.out["cas"][M.CAS_LEADER][0][0])

    # ------------------------------------------------------------ 合法性
    def test_native_legality_gates_are_empty(self):
        cas_keys = set(self.out["cas"]) | set(M.CAS_INVOKE)
        tables = (("leader_ability", {M.LEADER_KEY: self.new_leader}), ("ability", self.out["ability"]))
        for kind, table in tables:
            for key, rows in table.items():
                for index, row in enumerate(rows):
                    label = f"{kind}:{key}#{index}"
                    self.assertEqual(L.client_legality_problems(kind, row), [], label)
                    self.assertEqual(L.declared_block_field_problems(kind, row), [], label)
                    self.assertEqual(L.invoke_skill_string_problems(row, cas_keys, kind), [], label)
                    self.assertEqual(KL.row_problems(kind, row, K.ELEMENT if kind == "ability" else None),
                                     {}, label)
                    self.assertLessEqual(set(L.required_client_capabilities(kind, row)),
                                         CANDIDATE_CAPABILITIES, label)
        for row in self.new_leader[10:]:
            self.assertEqual(L.required_client_capabilities("leader_ability", row), [])
            self.assertNotIn(row[107], K.FORBIDDEN_LEADER_KINDS)
        K._row_self_check("leader_ability", self.new_leader, "leader")
        for key, rows in self.out["ability"].items():
            K._row_self_check("ability", rows, key)

    def test_the_invoke_triggers_are_within_three_seconds(self):
        """口径 B.3 的前提：两行 629 的触发 CT 都 ≤3 秒（180 帧）⇒ 每次 ≤1。"""
        invokes = [r for r in self.new_leader if r[45] == "629"]
        self.assertEqual({r[25]: r[33] for r in invokes}, {"23": "0", "4": "90"})
        for row in invokes:
            self.assertEqual(row[69], M.INVOKE_PROGRAM)
            self.assertLessEqual(int(row[33]), 180)

    # ------------------------------------------------------------ DSL
    def test_dsl_only_p13_changes(self):
        self.assertEqual(_mask_p13(self.new_tree), _mask_p13(self.old_tree))
        old = [c[13] for c in wf_dsl.iter_dsl_commands(self.old_tree, "CreateNormalAttack")]
        new = [c[13] for c in wf_dsl.iter_dsl_commands(self.new_tree, "CreateNormalAttack")]
        self.assertEqual(old, [[{"min": 6.25, "max": 6.25}]] * 2)
        self.assertEqual(new, [[{"min": 0.25, "max": 0.25}]] * 2)
        self.assertEqual(self.new_tree[:11], ["ActionDsl", 1, ["None"], *[False] * 7, 133])

    def test_dsl_detoughness_per_call(self):
        areas = list(wf_dsl.iter_dsl_commands(self.new_tree, "CreateHitArea"))
        total_old = total_new = 0.0
        for cha in areas:
            self.assertEqual(cha[14][0], "CalculatedUsingMaxNumOfHits")
            self.assertEqual(cha[24], 0)
            (cna,) = list(wf_dsl.iter_dsl_commands(cha, "CreateNormalAttack"))
            total_new += cha[14][1] * cna[13][0]["max"]
        for cha in wf_dsl.iter_dsl_commands(self.old_tree, "CreateHitArea"):
            (cna,) = list(wf_dsl.iter_dsl_commands(cha, "CreateNormalAttack"))
            total_old += cha[14][1] * cna[13][0]["max"]
        self.assertEqual([c[14][1] for c in areas], [3, 1])
        self.assertAlmostEqual(total_old, 25.0)
        self.assertAlmostEqual(total_new, 1.0)
        self.assertLessEqual(total_new, M.DOWN_CAP_PER_CALL)
        mults = [c[6] for c in wf_dsl.iter_dsl_commands(self.new_tree, "CreateNormalAttack")]
        self.assertEqual(mults, [[{"min": 19.2, "max": 19.2}], [{"min": 43.2, "max": 43.2}]])

    def test_dsl_roundtrip_and_gates(self):
        tree = self.new_tree
        self.assertEqual(wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"], tree)
        encode_tree(tree)                                # 暂存脚本同一编码路径
        self.assertEqual(M.dsl_problems(tree), [])
        self.assertEqual(L.action_dsl_element_problems(tree, M.ELEMENT), [])
        self.assertEqual(L.action_dsl_subject_binding_problems(tree), [])
        self.assertEqual(L.action_dsl_lookup_scope_problems(tree), [])
        self.assertEqual(L.action_dsl_hit_area_target_problems(tree), [])
        self.assertEqual(K.dsl_problems(tree, element=None), [])

    # ------------------------------------------------------------ 失败闭合
    def test_input_is_not_mutated_and_output_is_detached(self):
        data = deepcopy(self.live)
        out = M.revise(reader(data))
        self.assertEqual(data, self.live)
        out["leader"][M.LEADER_KEY][6][49] = "mutated"
        out["ability"][M.ABILITY3][0][0] = "mutated"
        out["cas"][M.CAS_SLOT4][0][0] = "mutated"
        next(wf_dsl.iter_dsl_commands(out["dsl"][M.INVOKE_PROGRAM], "CreateNormalAttack"))[13] = None
        self.assertEqual(data, self.live)

    def test_baseline_drift_is_rejected(self):
        for kind, key in M.BEFORE:
            data = deepcopy(self.live)
            value = data[kind][_key(kind, key)]
            if kind == "dsl":
                value[10] = 3
            else:
                value[0][-1] = value[0][-1] + "x"
            with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
                M.revise(reader(data))
            data = deepcopy(self.live)
            data[kind][_key(kind, key)] = None
            with self.assertRaises(ValueError):
                M.revise(reader(data))

    def test_revise_is_not_reapplicable_to_its_own_output(self):
        data = deepcopy(self.live)
        for kind in ("ability", "leader", "cas", "dsl"):
            data[kind].update(deepcopy(self.out[kind]))
        with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
            M.revise(reader(data))
        with self.assertRaises(ValueError):
            M.ability3_rows(self.out["ability"][M.ABILITY3])
        with self.assertRaises(ValueError):
            M.ability4_rows(self.out["ability"][M.ABILITY4])
        with self.assertRaises(ValueError):
            M.leader_rows(self.new_leader, self.live["ability"][M.ABILITY3], self.live["ability"][M.ABILITY4])
        with self.assertRaises(ValueError):
            M.leader_text(self.out["cas"][M.CAS_LEADER])
        with self.assertRaises(ValueError):
            M.slot3_text(self.out["cas"][M.CAS_SLOT3])
        with self.assertRaises(ValueError):
            M.slot4_text(self.out["cas"][M.CAS_SLOT4])
        with self.assertRaises(ValueError):
            M.invoke_tree(self.new_tree)

    def test_row_locators_are_content_based(self):
        """绕过 BEFORE 直接调纯函数：目标行形状不对也要拒绝。"""
        a3, a4 = self.live["ability"][M.ABILITY3], self.live["ability"][M.ABILITY4]
        for mutate in (lambda r: r.__setitem__(slice(1, 3), [r[2], r[1]]),   # 目标行不在 #1
                       lambda r: r[1].__setitem__(102, "5"),                   # 已有上限
                       lambda r: r[1].__setitem__(6, "2"),                     # 多出共鸣门
                       lambda r: r[1].__setitem__(80, "x"),                    # 多出非空列
                       lambda r: r.pop()):                                     # 记录条数不对
            rows = deepcopy(a3)
            mutate(rows)
            with self.assertRaises(ValueError):
                M.ability3_rows(rows)
        rows = deepcopy(a4)
        rows[2][113] = "20000"
        with self.assertRaises(ValueError):
            M.ability4_rows(rows)
        for mutate in (lambda r: r[6].__setitem__(32, "10"),                   # 命中行已限次
                       lambda r: r[7].__setitem__(33, "300"),                  # 冲刺 629 CT 5 秒
                       lambda r: r.append(list(r[2])),                         # 行数漂移
                       lambda r: r[2].__setitem__(95, "134")):                 # 已有 during134（应合并）
            rows = deepcopy(self.old_leader)
            mutate(rows)
            with self.assertRaises(ValueError):
                M.leader_rows(rows, a3, a4)
        tree = deepcopy(self.old_tree)
        next(wf_dsl.iter_dsl_commands(tree, "CreateHitArea"))[14] = ["CalculatedUsingMaxNumOfHits", 5]
        with self.assertRaises(ValueError):
            M.invoke_tree(tree)
        tree = deepcopy(self.old_tree)
        next(wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack"))[13] = [{"min": 5, "max": 6.25}]
        with self.assertRaises(ValueError):
            M.invoke_tree(tree)


class GeneratorSyncTests(unittest.TestCase):
    """生成器 wf_midautumn_kit_hibiki 重跑不能把旧数值/旧面板/旧削韧带回来。"""

    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))

    def test_panel_constants_equal_revise_output(self):
        target = generator_target(self.out)
        for key in (M.CAS_LEADER, M.CAS_SLOT3, M.CAS_SLOT4):
            self.assertEqual([[K.CAS_TEXTS[key]]], target["cas"][key], key)
        self.assertEqual(K.PANEL_LEADER, target["cas"][M.CAS_LEADER][0][0])
        self.assertEqual(tuple(K.PANEL_ABILITY[3].split("\n")), M.NEW_SLOT3_LINES)
        # 第三轮（c）面板同条件合并把槽 4 前两行并成一行：生成器 = 目标输出（c 前 = 第二批 NEW_SLOT4_LINES）
        self.assertEqual(tuple(K.PANEL_ABILITY[4].split("\n")),
                         tuple(target["cas"][M.CAS_SLOT4][0][0].split("\n")))

    def test_plan_cells_carry_the_new_values(self):
        self.assertEqual(K.LEADER_ROWS, 12)
        hit = K.LEADER[M.HIT_ROW][2]
        target = generator_target(self.out)["leader"][M.LEADER_KEY]       # 第三轮后 = 第二批 + 第三轮覆盖
        self.assertEqual((hit[25], hit[32], hit[49], hit[50]),
                         ("15", "(None)", target[M.HIT_ROW][49], target[M.HIT_ROW][50]))
        for (_addr, _src, cells, _expect), kind, row in zip(K.LEADER[10:], ("23", "0"), target[10:]):
            self.assertEqual((cells[95], cells[100], cells[102], cells[107], cells[111], cells[112]),
                             ("134", K.UNIQUE_CAP, K.UID, kind, row[111], row[112]))
        pfdmg, atk = K.PLAN[3][M.PFDMG_ROW][2], K.PLAN[4][M.ATK_ROW][2]
        self.assertEqual((pfdmg[102], pfdmg[113], pfdmg[114]), ("10", "10000", "10000"))
        self.assertEqual((atk[102], atk[113], atk[114]), ("10", "5000", "5000"))
        self.assertEqual((K.INVOKE_DOWN_SOURCE, K.INVOKE_DOWN), (M.DOWN_OLD, M.DOWN_NEW))

    @unittest.skipUnless(_baseline_available(), "需要 .cdn/cn 官方基线与 live store")
    def test_generator_rows_equal_revise_output(self):
        rows = K.build_rows(_kit_ctx())
        self.assertEqual(rows["leader"], generator_target(self.out)["leader"][M.LEADER_KEY])
        for key in (M.ABILITY3, M.ABILITY4):
            self.assertEqual(rows["ability"][key], self.out["ability"][key], key)
        described = [ev["describe"] for ev in rows["evidence"] if ev["kind"] == "leader_ability"]
        self.assertEqual(described[10:], [e for *_x, e in K.LEADER[10:]])

    @unittest.skipUnless(_baseline_available(), "需要 .cdn/cn 官方基线与 live store")
    def test_generator_invoke_tree_equals_revise_output(self):
        tree, gates = K.build_invoke_tree(_kit_ctx())
        self.assertEqual(tree, self.out["dsl"][M.INVOKE_PROGRAM])
        self.assertEqual(gates["detoughness"], {"per_segment": 0.25, "segments": [3, 1],
                                                "per_call": 1.0, "official_per_segment": 6.25})


PHILIA_FIXTURE = Path(__file__).parent / "fixtures/balance_20260927b_philia.json"


class DonorPinTest(unittest.TestCase):
    """生成器 L0（722）以 live 菲莉亚 ``159996#3`` 为 donor，而菲莉亚第二批把这一行 c49/c50 50000 → 7000
    （``wf_balance_20260927b_philia``，复核 major）。L0 已把 donor 的全部非空列按 live 值钉死 ⇒
    菲莉亚暂存/发布前后，本生成器的产物都与 live（＝ revise 未改的 #0）逐字相同。"""

    @classmethod
    def setUpClass(cls):
        import wf_balance_20260927b_philia as P
        cls.P = P
        cls.addr, cls.source, cls.cells, cls.expect = K.LEADER[0]
        cls.pinned = {int(col) for col in cls.cells}
        cls.live_l0 = load_fixture()["leader"][M.LEADER_KEY][0]

    def _built(self, donor: list[str]) -> list[str]:
        return KL.apply_cells(donor, self.cells, M.LEADER_NCOLS)

    def test_pinned_cells_alone_reproduce_the_live_row(self):
        """钉住的格子 ＝ live L0 的全部非空列 ⇒ donor 只提供列宽，内容怎么变都带不进来（只要不新增非空列）。"""
        self.assertEqual((self.addr, self.source), (f"{self.P.CID}#{self.P.LEADER_PF_DAMAGE_ROW}", "live"))
        self.assertEqual(self._built([""] * M.LEADER_NCOLS), self.live_l0)
        self.assertEqual({col for col, value in enumerate(self.live_l0) if value}, self.pinned)
        self.assertEqual(D.describe_line(self.live_l0, "leader_ability"), self.expect)

    def test_philia_batch2_fingerprints_are_covered(self):
        """菲莉亚的行指纹 ＝ 该行全部非空列（其 _matches 要求其余列为空）⇒ 改前/改后 donor 的每一格都被钉住。"""
        P = self.P
        before = KL.apply_cells([], P.LEADER_PF_DAMAGE, P.LEADER_NCOLS)
        after = KL.apply_cells([], P.LEADER_PF_DAMAGE_AFTER, P.LEADER_NCOLS)
        changed = set(_diff(before, after))          # 写本测试时 = {49, 50}：50000 → 7000
        self.assertTrue(changed)
        self.assertLessEqual(changed, self.pinned)       # 菲莉亚复修改动值也不影响本行，只要仍在钉住的列里
        self.assertLessEqual(set(P.LEADER_PF_DAMAGE), self.pinned)
        self.assertLessEqual(set(P.LEADER_PF_DAMAGE_AFTER), self.pinned)
        for donor in (before, after):
            row = self._built(donor)
            self.assertEqual(row, self.live_l0)
            self.assertEqual(D.describe_line(row, "leader_ability"), self.expect)

    @unittest.skipUnless(PHILIA_FIXTURE.is_file(), "philia batch-2 fixture absent")
    def test_philia_revise_output_keeps_the_generator_row(self):
        """端到端：菲莉亚模块对其 live 快照的真实输出当 donor，L0 仍与 live 逐字相同。"""
        P = self.P
        fx = json.loads(PHILIA_FIXTURE.read_bytes())
        data = {(kind, tuple(key) if isinstance(key, list) else key): value for kind, key, value in fx["reads"]}
        out = P.revise(lambda kind, key: data[kind, key])
        old = data["leader", P.CID][P.LEADER_PF_DAMAGE_ROW]
        new = out["leader"][P.CID][P.LEADER_PF_DAMAGE_ROW]
        self.assertTrue(_diff(old, new))
        self.assertLessEqual(set(_diff(old, new)), self.pinned)
        self.assertEqual(self._built(old), self.live_l0)
        self.assertEqual(self._built(new), self.live_l0)

    @unittest.skipUnless(_baseline_available() and PHILIA_FIXTURE.is_file(),
                         "需要 .cdn/cn 官方基线、live store 与菲莉亚 fixture")
    def test_generator_rows_unchanged_when_philia_is_staged(self):
        """复核复现路径：把菲莉亚改后的 159996#3 喂给 donor_row，``K.build_rows`` 队长仍 == revise() 输出。"""
        from unittest import mock
        P = self.P
        fx = json.loads(PHILIA_FIXTURE.read_bytes())
        data = {(kind, tuple(key) if isinstance(key, list) else key): value for kind, key, value in fx["reads"]}
        staged = P.revise(lambda kind, key: data[kind, key])["leader"][P.CID][P.LEADER_PF_DAMAGE_ROW]
        original = KL.donor_row
        seen = []

        def donor_row(ctx, table, key, index=0, *, source="official"):
            if table == KL.LEADER and key == self.addr and source in ("live", "store"):
                seen.append(key)
                return list(staged)
            return original(ctx, table, key, index, source=source)

        with mock.patch.object(KL, "donor_row", donor_row):
            rows = K.build_rows(_kit_ctx())
        self.assertEqual(seen, [self.addr])
        out = generator_target(M.revise(reader(load_fixture())))
        self.assertEqual(rows["leader"], out["leader"][M.LEADER_KEY])
        self.assertEqual(rows["leader"][0], self.live_l0)


class MirrorTests(unittest.TestCase):
    PATHS = (ROOT / M.DESIGN_REL, ROOT / M.PANEL_REL)

    def setUp(self):
        if not all(path.is_file() for path in self.PATHS):
            self.skipTest("midautumn design mirrors missing")
        self.docs = [json.loads(path.read_text(encoding="utf-8")) for path in self.PATHS]

    @unittest.skipIf(GENERATOR_AT_C, "生成器已前进到第三轮：设计镜像同步由 test_balance_20260927c_hibiki.MirrorTests 接管")
    def test_mirrors_are_already_synced(self):
        self.assertEqual(M.sync_mirrors(ROOT, write=False), [])
        design, panel = self.docs
        self.assertEqual(K.design_problems(design), [])
        self.assertEqual(design["plan_rework1"]["leader_rows"], 12)
        self.assertEqual([r["describe"] for r in design["plan_rework1"]["leader_records"]],
                         [e for *_x, e in K.LEADER])
        self.assertIn(M.MIRROR_TAG, design["rework1"])
        self.assertEqual([line["text"] for line in panel["leader"]["lines"]], K.PANEL_LEADER.split("\n"))
        for block in panel["abilities"]:
            self.assertEqual([line["text"] for line in block["lines"]],
                             K.PANEL_ABILITY[int(block["index"])].split("\n"))
        self.assertEqual(panel["notes"][-1], M.MIRROR_NOTE)

    def test_mirror_update_is_idempotent_and_pure(self):
        before = deepcopy(self.docs)
        once = M.mirror_updates(*self.docs)
        self.assertEqual(self.docs, before)
        self.assertEqual(M.mirror_updates(*once), once)


@unittest.skipUnless((WORKSPACE / "package/manifest.json").is_file()
                     and (ROOT / "mod-tools/profiles.json").is_file(), "local candidate workspace required")
class CandidateTests(unittest.TestCase):
    def test_candidate_accepts_the_revision_dry(self):
        """候选与 live 逐字相同（REVIEWED_DRIFT 为空）；dry-run 回写不落盘。回写后改为逐项比对。"""
        import zlib
        import wf_share_update_codec as X
        from wf_character_revision import RevisionCandidate
        out = M.revise(reader(load_fixture()))
        manifest = WORKSPACE / "package/manifest.json"
        before = manifest.read_bytes()
        current = json.loads(before)
        # 第三轮（wf_balance_20260927c_hibiki）回写后候选版本号可能已推进到它的 PACKAGE_VERSION（高于本批）；
        # 这里只是「候选不能领先于任何一批已知版本」的哨兵检查，取两批版本号的较大者作上限。
        import wf_balance_20260927c_hibiki as _C3
        ceiling = max(tuple(map(int, M.PACKAGE_VERSION[M.PACKAGES[0]].split("."))),
                     tuple(map(int, _C3.PACKAGE_VERSION[_C3.PACKAGES[0]].split("."))))
        self.assertGreaterEqual(ceiling, tuple(map(int, current["package_version"].split("."))))
        kwargs = dict(character_id=M.CID, code_name=M.CODE, snapshot_key="revision_20260927b",
                      package_version=M.PACKAGE_VERSION[M.PACKAGES[0]],
                      baseline_factory=lambda *a, **k: None, reviewed_input_drift=M.REVIEWED_DRIFT)
        candidate = RevisionCandidate(ROOT, WORKSPACE, **kwargs)
        if current.get("snapshot", {}).get("revision_20260927b") is not None:
            # 主会话暂存回写后：候选 = 本批输出（第三轮回写后 = 再加第三轮覆盖，版本号只升不降）。
            self.assertGreaterEqual(tuple(map(int, current["package_version"].split("."))),
                                    tuple(map(int, M.PACKAGE_VERSION[M.PACKAGES[0]].split("."))))
            later = batch3_output(out)
            for kind, logical in (("ability", "master/ability/ability.orderedmap"),
                                  ("leader", "master/ability/leader_ability.orderedmap"),
                                  ("cas", "master/string/custom_ability_string.orderedmap")):
                rows = X.unpack(candidate.read("common", logical))
                for key, value in out[kind].items():
                    self.assertIn(X.csv_read(rows[key]), (value, later[kind][key]), key)
            raw = candidate.read("common", wf_dsl.dsl_logical(M.INVOKE_PROGRAM))
            self.assertEqual(wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"], out["dsl"][M.INVOKE_PROGRAM])
            return
        candidate.splice("master/ability/ability.orderedmap", out["ability"])
        candidate.splice("master/ability/leader_ability.orderedmap", out["leader"])
        candidate.splice("master/string/custom_ability_string.orderedmap", out["cas"])
        candidate.emit("common", wf_dsl.dsl_logical(M.INVOKE_PROGRAM), encode_tree(out["dsl"][M.INVOKE_PROGRAM]))
        evidence = candidate.finish({"dry_run": True}, apply=False)
        self.assertFalse(evidence["applied"])
        self.assertEqual(len(evidence["changed_files"]), 4)
        self.assertEqual(before, manifest.read_bytes())


if __name__ == "__main__":
    unittest.main()
