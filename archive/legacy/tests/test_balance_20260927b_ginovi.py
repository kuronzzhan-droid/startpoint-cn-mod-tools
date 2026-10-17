# -*- coding: utf-8 -*-
"""基诺维 169999 ``ginovi`` 2026-09-27 平衡第二批：贯穿成长 25%→2.5%、四类削韧 p13 下调。

fixture = live 1.4.1049 输入快照（``fixtures/balance_20260927b_ginovi.json``），驱动 ``revise()``：
每处改动前后值、未改行/未改节点逐字保留、BEFORE 漂移拒绝、不改输入、对自身输出重跑拒绝、
合法性门禁、DSL AMF3 往返与四道 DSL 门禁、面板规则、生成器输出 == revise() 输出、候选干跑。
生成器 DSL 对比需要候选包 roots（v3 特效族探测）；队长行对比另需 live store 与 ``.cdn/cn`` 官方基线（缺时跳过）。
**不跑** ``build_workspace.py build``/``kit-v3``（会写包；test_build_workspace.GinoviBuildContractTests 就会跑 build）。
"""
from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest import mock
import zlib

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_balance_20260927b_ginovi as M  # noqa: E402
import wf_client_legality as L  # noqa: E402
import wf_dsl  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_mod_tool as core  # noqa: E402
from wf_character_revision import encode_tree  # noqa: E402
from wf_midautumn_kit_hibiki import dsl_problems as kit_dsl_problems  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927b_ginovi.json'
WORKSPACE = ROOT / "work/character_packs" / M.PACKAGES[0]
BUILD_SCRIPT = WORKSPACE / "build_workspace.py"
#: 候选 ginovi manifest 现有的 required_capabilities（改后不新增）。
CANDIDATE_CAPABILITIES = {"dash-parameter-v1", "panel-description-override-v2"}
CHANGED_PROGRAMS = {*M.SKILL_PROGRAMS.values(), *M.PF_INVOKE_PROGRAMS.values(), M.DASH_PROGRAM,
                    M.PF_BODY_PROGRAMS[3]}
#: 生成器 write_m3_leader_rows 与 live 的既有差异（本批不动）：629 瞬发行 #1–#4 的 c111。
#: c111 = during_content+4（持续块强度），瞬发行（c3=0）客户端不读。生成器经 wf_gui.composer_blank
#: 取「live 队长表全部持续行（c3=1）c111 的众数」做模板填这一格，live 这 4 行冻结的是当初生成时的
#: "25000"。众数随 live 队长表内容漂移（本测试编写时为 "150000"，第二批 1.4.1051 发布后为 "20000"；
#: 前几名只差 1–2 行，任何改队长持续行的发布都可能换位），
#: 所以期望的生成器值按当前 live 表现算（:func:`live_during_c111_mode`），不写死快照值。
#: 09-27 kit-v3 重建（作者「不要影响他当前能力的效果」）：生成器已把这 4 格钉成 live 冻结值 "25000"，
#: 差异归零；众数仍随 live 漂移，只作断言消息。
KNOWN_GENERATOR_LEADER_DRIFT_CELLS = {(index, 111) for index in (1, 2, 3, 4)}
KNOWN_GENERATOR_LEADER_LIVE_VALUE = "25000"


def live_during_c111_mode(gen) -> str:
    """与 wf_gui._blank_template 同一规则独立重算：live 队长表按表序逐行统计 c3=="1" 行的 c111，
    取 Counter.most_common(1)（并列按首次出现，与模板一致）。"""
    from collections import Counter
    logical = "master/ability/leader_ability.orderedmap"
    table = gen.core.load_table(logical, gen.wf_gui.TARGET_STORE, gen.wf_gui.SOURCE_STORE)
    counts = Counter()
    for text in table.text_rows().values():
        for row in gen.core.read_csv_lines(text):
            if (row[3] if len(row) > 3 else "") == "1":
                counts[row[111] if len(row) > 111 else ""] += 1
    return counts.most_common(1)[0][0]


def _k(key) -> str:
    return key if isinstance(key, str) else "|".join(key)


def load_fixture() -> dict:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return {kind: value for kind, value in data.items() if not kind.startswith("_")}


def reader(data: dict):
    def read(kind, key):
        return data[kind][_k(key)]
    return read


def leaf_diff(a, b, path=()):
    """两棵 JSON 值的叶子差异路径列表（类型/长度变化记在该层）。"""
    if type(a) is not type(b):
        return [path]
    if isinstance(a, list):
        if len(a) != len(b):
            return [path]
        return [p for i, (x, y) in enumerate(zip(a, b)) for p in leaf_diff(x, y, path + (i,))]
    if isinstance(a, dict):
        if a.keys() != b.keys():
            return [path]
        return [p for k in a for p in leaf_diff(a[k], b[k], path + (k,))]
    return [] if a == b else [path]


def at(tree, path):
    for step in path:
        tree = tree[step]
    return tree


def p13_values(tree) -> list:
    return [attack[13] for attack in wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack")]


def _baseline_available() -> bool:
    profile = core.resolve_profile()
    return profile is not None and profile.store.is_dir() and (ROOT / ".cdn" / "cn").is_dir()


def load_generator():
    spec = importlib.util.spec_from_file_location("ginovi_build_workspace_b2", BUILD_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


C_FIXTURE = Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927c_ginovi.json'


def batch3_output(out: dict) -> dict:
    """第三轮（``wf_balance_20260927c_ginovi``，成长复核）在第二批输出上继续改的结果（b → c 链；c fixture ==
    第二批输出，见 c 测试）：被第三轮改写的键换成第三轮输出，其余原样。"""
    import wf_balance_20260927c_ginovi as C
    data = {k: v for k, v in json.loads(C_FIXTURE.read_text(encoding="utf-8")).items() if not k.startswith("_")}
    c_out = C.revise(lambda kind, key: data[kind][key])
    merged = deepcopy(out)
    for kind, table in c_out.items():
        if kind != "notes" and isinstance(table, dict):
            merged.setdefault(kind, {}).update(deepcopy(table))
    return merged


def generator_target(gen, out: dict) -> dict:
    """生成器当前应等于的输出：第三轮已把 PIERCING_BUFF 推进到 c 值时 = 第二批输出 + 第三轮覆盖
    （b → c 两种状态都接受；逐格断言由 c 测试接管）。"""
    return out if gen.PIERCING_BUFF == M.NEW_TICK else batch3_output(out)


class ReviseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))
        cls.old_leader = cls.live["leader"][M.LEADER]
        cls.new_leader = cls.out["leader"][M.LEADER]

    def old_tree(self, program):
        return self.live["dsl"][program]

    # ---------------------------------------------------------------- 契约

    def test_fixture_is_the_reviewed_baseline(self):
        for (kind, key), want in M.BEFORE.items():
            self.assertEqual(M.digest(self.live[kind][_k(key)]), want, f"{kind}:{key}")
        self.assertEqual({(kind, key) for kind, keys in self.live.items() for key in keys},
                         {(kind, _k(key)) for kind, key in M.BEFORE})

    def test_module_contract_exports(self):
        self.assertEqual((M.CID, M.CODE), ("169999", "ginovi"))
        self.assertEqual(M.PACKAGES, ["ginovi"])
        self.assertEqual(M.PACKAGE_VERSION, {"ginovi": "0.3.1"})   # 候选现值 0.3.0，只升不降
        self.assertEqual(M.CAPABILITIES, [])
        self.assertEqual(M.REVIEWED_DRIFT, {})
        self.assertEqual(M.ELEMENT, 5)
        self.assertFalse(self.out["notes"]["runtime_verified"])
        json.dumps(self.out["notes"], ensure_ascii=False)

    def test_only_changed_keys_are_returned(self):
        out = self.out
        self.assertEqual(set(out["leader"]), {M.LEADER})
        self.assertEqual(set(out["cas"]), {M.CAS_LEADER})
        self.assertEqual(set(out["dsl"]), CHANGED_PROGRAMS)
        self.assertNotIn(M.PF_BODY_PROGRAMS[1], out["dsl"])
        self.assertNotIn(M.PF_BODY_PROGRAMS[2], out["dsl"])
        for kind in ("ability", "text", "table", "action", "server_text"):
            self.assertEqual(out[kind], {}, kind)
        self.assertEqual(out["new_programs"], [])   # 七棵树都已在候选 manifest roots 里
        for key in out["cas"]:                     # RevisionCandidate 命名空间
            self.assertTrue(key.startswith("desc_override_" + M.CODE), key)
        for key in out["leader"]:
            self.assertTrue(key.startswith(M.CID), key)

    # ---------------------------------------------------------------- 一、成长

    def test_leader_only_tick_cells_change(self):
        self.assertEqual((len(self.old_leader), len(self.new_leader)), (11, 11))
        changed = {(i, c): (a, b)
                   for i, (old, new) in enumerate(zip(self.old_leader, self.new_leader))
                   for c, (a, b) in enumerate(zip(old, new)) if a != b}
        self.assertEqual(changed, {(i, c): ("25000", "2500") for i in (6, 7, 8) for c in (49, 50)})
        self.assertTrue(all(len(r) == 124 for r in self.new_leader))

    def test_tick_rows_keep_trigger_gate_and_stay_unlimited(self):
        for index, kind in ((6, "32"), (7, "34"), (8, "388")):
            row = self.new_leader[index]
            with self.subTest(row=index):
                self.assertEqual((row[4], row[7], row[9]), ("2", "600000", "Black"))    # 暗共鸣
                self.assertEqual((row[25], row[26]), ("235", "0"))                      # 保持贯穿
                self.assertEqual((row[28], row[30]), ("100000", "9000000"))             # 每 90 帧一跳
                self.assertEqual(row[32], "(None)")                                     # 仍不限次
                self.assertEqual(row[33], "0")                                          # 无 CT
                self.assertEqual((row[45], row[46], row[47]), (kind, "5", "Black"))     # 暗队
                self.assertEqual(int(row[49]) / 100000, 0.025)                          # +2.5%
                self.assertEqual(int(row[49]) * 10, int(self.old_leader[index][49]))    # ×1/10

    def test_panel_changes_only_the_piercing_line(self):
        old = self.live["cas"][M.CAS_LEADER][0][0].split("\n")
        new = self.out["cas"][M.CAS_LEADER][0][0].split("\n")
        self.assertEqual((len(old), len(new)), (6, 6))
        self.assertEqual([i for i in range(6) if old[i] != new[i]], [3])
        self.assertEqual(old[3], M.OLD_PANEL_LINE)
        self.assertEqual(new[3], "暗属性共鸣时，自身每保持贯穿效果1.5秒，暗属性角色攻击力＋2.5%、技能伤害＋2.5%、能力伤害＋2.5%")
        self.assertEqual(len(self.out["cas"][M.CAS_LEADER]), 1)
        self.assertEqual(len(self.out["cas"][M.CAS_LEADER][0]), 1)

    def test_panel_agrees_with_the_data(self):
        line = self.out["cas"][M.CAS_LEADER][0][0].split("\n")[3]
        self.assertEqual(line.count("＋2.5%"), 3)
        self.assertEqual(M.panel_percent(line), int(self.new_leader[6][49]) / 1000)
        self.assertIn("1.5秒", line)                       # 90 帧
        self.assertEqual(int(self.new_leader[6][30]) // 100000, 90)

    def test_panel_text_obeys_the_project_rules(self):
        text = self.out["cas"][M.CAS_LEADER][0][0]
        self.assertEqual(KL.panel_problems(text), [])
        for word in ("可无限", "无上限", "无限叠加", "不设上限", "自身为队长时", "生命值100%以下", "／"):
            self.assertNotIn(word, text, word)
        self.assertEqual(L.required_client_capabilities("custom_ability_string", [M.CAS_LEADER, text]),
                         ["panel-description-override-v2"])
        self.assertLessEqual({"panel-description-override-v2"}, CANDIDATE_CAPABILITIES)

    # ---------------------------------------------------------------- 二、Down

    def test_each_dsl_change_touches_only_createnormalattack_p13(self):
        for program in CHANGED_PROGRAMS:
            old, new = self.old_tree(program), self.out["dsl"][program]
            paths = leaf_diff(old, new)
            with self.subTest(program=program.rsplit("$", 1)[-1]):
                self.assertTrue(paths)
                self.assertEqual(old[:11], new[:11])                           # 根头不动
                for path in paths:
                    self.assertEqual(path[-3:-1], (13, 0), path)
                    self.assertIn(path[-1], ("min", "max"))
                    self.assertEqual(at(new, path[:-3])[0], "CreateNormalAttack", path)

    def test_p13_values_before_and_after(self):
        expected = {M.SKILL_PROGRAMS[1]: (20, 2.5, 1), M.SKILL_PROGRAMS[2]: (20, 2.5, 1),
                    M.PF_INVOKE_PROGRAMS[1]: (20, 0.1, 1), M.PF_INVOKE_PROGRAMS[2]: (20, 0.1, 1),
                    M.PF_INVOKE_PROGRAMS[3]: (20, 0.1, 1), M.DASH_PROGRAM: (20, 0.25, 1),
                    M.PF_BODY_PROGRAMS[3]: (3, 2.5, 10)}
        for program, (old, new, count) in expected.items():
            with self.subTest(program=program.rsplit("$", 1)[-1]):
                self.assertEqual(p13_values(self.old_tree(program)), [[{"min": old, "max": old}]] * count)
                self.assertEqual(p13_values(self.out["dsl"][program]), [[{"min": new, "max": new}]] * count)
        for level in (1, 2):   # PF 本体 Lv1/Lv2 不动
            self.assertEqual(p13_values(self.old_tree(M.PF_BODY_PROGRAMS[level])),
                             [[{"min": 3, "max": 3}]] * (4 if level == 1 else 6))

    def test_hit_counts_follow_hit_area_parameters(self):
        skill = list(wf_dsl.iter_dsl_commands(self.out["dsl"][M.SKILL_PROGRAMS[1]], "CreateHitArea"))
        self.assertEqual(len(skill), 1)
        area = skill[0]
        self.assertEqual(area[13], ["SpecifyHitAreaLifetimeDirectly", 750])
        self.assertEqual(area[14], ["SpecifyMinHitIntervalDirectly", 60])
        self.assertEqual(area[15], ["Some", [{"min": 12, "max": 12}]])       # 每目标硬帽 12
        self.assertEqual(M.area_hits(area), 12)                                 # 13 次机会封顶 12
        for level, hits in ((1, 5), (2, 7), (3, 9)):
            areas = list(wf_dsl.iter_dsl_commands(self.out["dsl"][M.PF_INVOKE_PROGRAMS[level]], "CreateHitArea"))
            self.assertEqual([a[14] for a in areas], [["CalculatedUsingMaxNumOfHits", hits]])
            self.assertEqual([a[15] for a in areas], [["None"]])
        body = list(wf_dsl.iter_dsl_commands(self.out["dsl"][M.PF_BODY_PROGRAMS[3]], "CreateHitArea"))
        self.assertEqual([a[14] for a in body], [["CalculatedUsingMaxNumOfHits", 1]] * 10)

    def test_detoughness_totals_before_and_after(self):
        cases = {M.SKILL_PROGRAMS[1]: (240, 30), M.SKILL_PROGRAMS[2]: (240, 30),
                 M.PF_INVOKE_PROGRAMS[1]: (100, 0.5), M.PF_INVOKE_PROGRAMS[2]: (140, 0.7),
                 M.PF_INVOKE_PROGRAMS[3]: (180, 0.9), M.DASH_PROGRAM: (20, 0.25),
                 M.PF_BODY_PROGRAMS[3]: (30, 25)}
        for program, (before, after) in cases.items():
            with self.subTest(program=program.rsplit("$", 1)[-1]):
                self.assertAlmostEqual(M.detoughness(self.old_tree(program)), before)
                self.assertAlmostEqual(M.detoughness(self.out["dsl"][program]), after)
        self.assertEqual(M.detoughness(self.old_tree(M.PF_BODY_PROGRAMS[1])), 12)
        self.assertEqual(M.detoughness(self.old_tree(M.PF_BODY_PROGRAMS[2])), 18)
        notes = self.out["notes"]["detoughness"]
        self.assertEqual(notes["skill lv1"]["detoughness"], [240, 30])
        self.assertEqual(notes["PF 本体 lv3"]["detoughness"], [30, 25])

    def test_caps_follow_the_batch_rules(self):
        # B.1 技能每次 ≤30
        self.assertLessEqual(M.detoughness(self.out["dsl"][M.SKILL_PROGRAMS[1]]), 30)
        # B.2 PF 每级 15/20/25，Lv3 正好顶格（R6）
        body = {level: M.detoughness(self.out["dsl"].get(M.PF_BODY_PROGRAMS[level],
                                                           self.old_tree(M.PF_BODY_PROGRAMS[level])))
                for level in (1, 2, 3)}
        self.assertEqual(body, {1: 12, 2: 18, 3: 25})
        for level, cap in {1: 15, 2: 20, 3: 25}.items():
            self.assertLessEqual(body[level], cap)
        # B.3 629：按 live 队长行 c33 的 CT；≤180 帧 ⇒ 每次 ≤1
        for index, program in ((1, M.PF_INVOKE_PROGRAMS[1]), (2, M.PF_INVOKE_PROGRAMS[2]),
                               (3, M.PF_INVOKE_PROGRAMS[3]), (4, M.DASH_PROGRAM)):
            row = self.old_leader[index]
            self.assertEqual((row[45], row[69]), ("629", program))
            ct = int(row[33])
            self.assertLessEqual(ct, 180, "夜鸦裂空 36 帧 / 黑羽斩 20 帧，都 ≤3 秒")
            self.assertEqual(M.invoke_cap(row), 1)
            self.assertLessEqual(M.detoughness(self.out["dsl"][program]), 1)

    def test_invoke_cap_threshold_is_three_seconds(self):
        row = list(self.old_leader[1])
        for ct, cap in (("180", 1), ("181", 3), ("0", 1), ("600", 3)):
            row[33] = ct
            self.assertEqual(M.invoke_cap(row), cap, ct)
        row[33] = "(None)"
        with self.assertRaises(M.GinoviBalanceError):
            M.invoke_cap(row)

    def test_skill_tiers_stay_identical(self):
        self.assertEqual(self.out["dsl"][M.SKILL_PROGRAMS[1]], self.out["dsl"][M.SKILL_PROGRAMS[2]])

    def test_dsl_gates_and_amf3_roundtrip(self):
        for program in CHANGED_PROGRAMS:
            tree = self.out["dsl"][program]
            with self.subTest(program=program.rsplit("$", 1)[-1]):
                self.assertEqual(L.action_dsl_element_problems(tree, M.ELEMENT), [])
                self.assertEqual(L.action_dsl_subject_binding_problems(tree), [])
                self.assertEqual(L.action_dsl_lookup_scope_problems(tree), [])
                self.assertEqual(L.action_dsl_hit_area_target_problems(tree), [])
                self.assertEqual(wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"], tree)
                self.assertEqual(M.dsl_gate_problems(tree), [])
                raw = encode_tree(tree)                     # 暂存脚本同一编码路径（整树重编码）
                self.assertEqual(wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"], tree)
                # 更严的套件门禁（作用域/签名）：不新增问题（技能树 TargetMate 41/42 等既有写法照旧）
                self.assertEqual(kit_dsl_problems(tree, element=None),
                                 kit_dsl_problems(self.old_tree(program), element=None))

    def test_every_leader_row_passes_client_gates(self):
        cas_keys = {key for kind, key in M.BEFORE if kind == "cas"}
        for index, row in enumerate(self.new_leader):
            with self.subTest(row=index):
                self.assertEqual(L.client_legality_problems("leader_ability", row), [])
                self.assertEqual(L.declared_block_field_problems("leader_ability", row), [])
                self.assertEqual(L.ability_element_column_problems("leader_ability", row, M.ELEMENT), [])
                self.assertEqual(L.invoke_skill_string_problems(row, cas_keys, "leader_ability"), [])
                self.assertEqual(L.required_client_capabilities("leader_ability", row), [])
                self.assertEqual(M.leader_row_problems(row, cas_keys), [])

    # ---------------------------------------------------------------- fail closed

    def test_input_is_not_mutated_and_output_is_detached(self):
        live = deepcopy(self.live)
        out = M.revise(reader(live))
        self.assertEqual(live, self.live)
        out["leader"][M.LEADER][6][49] = "x"
        out["dsl"][M.DASH_PROGRAM][11] = None
        self.assertEqual(live, self.live)
        self.assertEqual(M.revise(reader(deepcopy(self.live)))["leader"], self.out["leader"])

    def test_baseline_drift_is_rejected(self):
        for kind, key in M.BEFORE:
            drifted = deepcopy(self.live)
            value = drifted[kind][_k(key)]
            if kind == "dsl":
                value[10] = 4
            else:
                value[0][-1] = value[0][-1] + "x"
            with self.subTest(kind=kind, key=_k(key)), \
                    self.assertRaisesRegex(M.GinoviBalanceError, "live drift"):
                M.revise(reader(drifted))
            missing = deepcopy(self.live)
            missing[kind][_k(key)] = None
            with self.assertRaises(M.GinoviBalanceError):
                M.revise(reader(missing))

    def test_revise_is_not_reapplicable_to_its_own_output(self):
        live = deepcopy(self.live)
        live["leader"].update(deepcopy(self.out["leader"]))
        live["cas"].update(deepcopy(self.out["cas"]))
        live["dsl"].update(deepcopy(self.out["dsl"]))
        with self.assertRaisesRegex(M.GinoviBalanceError, "live drift"):
            M.revise(reader(live))
        # 结构锁（BEFORE 之外的第二道）：改后的值不是可再改的原像
        with self.assertRaises(M.GinoviBalanceError):
            M.revise_leader(self.new_leader)
        with self.assertRaises(M.GinoviBalanceError):
            M.revise_panel(self.out["cas"][M.CAS_LEADER])
        with self.assertRaises(M.GinoviBalanceError):
            M.revise_p13(self.out["dsl"][M.DASH_PROGRAM], M.DASH_SPEC, "dash")
        with self.assertRaises(M.GinoviBalanceError):
            M.revise_p13(self.out["dsl"][M.PF_BODY_PROGRAMS[3]], M.PF_BODY_SPEC[3], "body3")

    def test_structure_guards(self):
        with self.assertRaisesRegex(M.GinoviBalanceError, "hit layout"):
            M.revise_p13(self.old_tree(M.PF_INVOKE_PROGRAMS[1]), M.PF_INVOKE_SPEC[2], "wrong level")
        rows = deepcopy(self.old_leader)
        rows[6][32] = "10"
        with self.assertRaisesRegex(M.GinoviBalanceError, "235 piercing tick"):
            M.revise_leader(rows)
        rows = deepcopy(self.old_leader)
        rows[2][33] = "600"
        with self.assertRaisesRegex(M.GinoviBalanceError, "629"):
            M.revise_leader(rows)


@unittest.skipUnless(BUILD_SCRIPT.is_file() and (WORKSPACE / "package/roots").is_dir(),
                     "需要基诺维生成器与候选包 roots")
class GeneratorTests(unittest.TestCase):
    """生成器 build_workspace.py 重跑不能把 25%/p13 20/3 带回来：纯函数输出 == revise() 输出。"""

    @classmethod
    def setUpClass(cls):
        cls.gen = load_generator()
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))

    def test_generator_constants_equal_revise_output(self):
        gen = self.gen
        target = generator_target(gen, self.out)["leader"][M.LEADER]
        self.assertEqual({gen.PIERCING_BUFF}, {target[i][c] for i in M.PIERCING_ROWS for c in M.TICK_COLS})
        self.assertEqual(gen.PIERCING_TICK_FRAMES, M.TICK_FRAMES)
        self.assertEqual(gen.PIERCING_STACK_LIMIT, "(None)")
        self.assertEqual(gen.SKILL_AURA_DETOUGHNESS, M.SKILL_SPEC[2])
        self.assertEqual(gen.DASH_BLADE_DETOUGHNESS, M.DASH_SPEC[2])
        self.assertEqual({gen.BLACKFEATHER_DETOUGHNESS}, {M.PF_INVOKE_SPEC[l][2] for l in (1, 2, 3)})
        self.assertEqual(gen.PF_BODY_DETOUGHNESS, {l: M.PF_BODY_SPEC[l][2] for l in (1, 2, 3)})

    def test_generator_panel_equals_revise_output(self):
        text = "\n".join(self.gen.DESC_OVERRIDE_LINES[M.CAS_LEADER])
        self.assertEqual([[text]], generator_target(self.gen, self.out)["cas"][M.CAS_LEADER])

    def test_generator_dsl_bodies_equal_revise_output(self):
        import wf_balance_20260927d_ginovi as D
        gen, dsl = self.gen, self.out["dsl"]
        # 第四轮（d）在两档技能根上插入吞噬协力球节点；生成器 == 本修订 + d 插入。
        self.assertEqual(gen.m4_skill_root(), D.insert_devour(dsl[M.SKILL_PROGRAMS[1]])[11])
        self.assertEqual(gen.m4_skill_root(), D.insert_devour(dsl[M.SKILL_PROGRAMS[2]])[11])
        self.assertEqual(gen.m5_dash_root(), dsl[M.DASH_PROGRAM][11])
        for level in (1, 2, 3):
            self.assertEqual(gen.blackfeather_root(level), dsl[M.PF_INVOKE_PROGRAMS[level]][11], level)
        self.assertEqual(gen.pf_body_root(3), dsl[M.PF_BODY_PROGRAMS[3]][11])
        for level in (1, 2):   # 未改档：生成器 == live
            self.assertEqual(gen.pf_body_root(level), self.live["dsl"][M.PF_BODY_PROGRAMS[level]][11], level)
        for root in (gen.m4_skill_root(), gen.m5_dash_root(), gen.pf_body_root(3),
                     *(gen.blackfeather_root(level) for level in (1, 2, 3))):
            self.assertEqual(gen.validate_dsl_signatures(root), [])

    @unittest.skipUnless(_baseline_available(), "需要 .cdn/cn 官方基线与 live store")
    def test_generator_leader_rows_equal_revise_output(self):
        """write_m3_leader_rows 的写表调用被拦截（不落影子表），只取它装配出的 11 行。"""
        gen = self.gen
        with mock.patch.object(gen.core, "write_table") as write_table:
            result = gen.write_m3_leader_rows()
        self.assertEqual(write_table.call_count, 1)
        self.assertEqual(Path(write_table.call_args[0][1]), Path(gen.SHADOW_STORE))
        rows, want = result["rows"], generator_target(gen, self.out)["leader"][M.LEADER]
        self.assertEqual(len(rows), len(want))
        for index in range(5, 11):            # 疾走 / 贯穿×3（本批）/ 开局技能槽 / 死印乘区
            self.assertEqual(rows[index], want[index], index)
        # 629 瞬发行的 c111（持续块、瞬发行不读）：composer 模板 = 当前 live 持续行众数（会漂移）；
        # 09-27 kit-v3 重建时生成器已把 c111/c112 钉成 live 冻结值（LEADER_629_INERT_DURING），
        # 所以不论众数是多少，#1–#4 都与 live/revise 输出逐格相同。
        self.assertEqual(Path(gen.wf_gui.TARGET_STORE), Path(gen.ACTIVE_STORE))   # 模板读的是 live 而非影子表
        mode = live_during_c111_mode(gen)
        for index in (1, 2, 3, 4):
            self.assertEqual(("0", "629"), (want[index][3], want[index][45]), index)
            self.assertEqual(KNOWN_GENERATOR_LEADER_LIVE_VALUE, want[index][111], index)
        self.assertEqual(gen.LEADER_629_INERT_DURING, (KNOWN_GENERATOR_LEADER_LIVE_VALUE, "100000"))
        for index, col in KNOWN_GENERATOR_LEADER_DRIFT_CELLS:
            self.assertEqual(rows[index][col], KNOWN_GENERATOR_LEADER_LIVE_VALUE, (index, col, mode))
        drift = {(i, c): (a, b) for i in (1, 2, 3, 4)
                 for c, (a, b) in enumerate(zip(rows[i], want[i])) if a != b}
        self.assertEqual({}, drift, f"composer 众数={mode}")


@unittest.skipUnless((WORKSPACE / "package/manifest.json").is_file()
                     and (ROOT / "mod-tools/profiles.json").is_file(),
                     "local candidate workspace required")
class CandidateTests(unittest.TestCase):
    def test_candidate_accepts_the_revision_dry(self):
        from wf_character_revision import RevisionCandidate
        out = M.revise(reader(load_fixture()))
        manifest = WORKSPACE / "package/manifest.json"
        before = manifest.read_bytes()
        data = json.loads(before)
        self.assertEqual(set(data["required_capabilities"]), CANDIDATE_CAPABILITIES)
        kwargs = dict(character_id=M.CID, code_name=M.CODE, snapshot_key="revision_20260927b",
                      package_version=M.PACKAGE_VERSION[M.PACKAGES[0]],
                      baseline_factory=lambda *a, **k: None, reviewed_input_drift=M.REVIEWED_DRIFT)
        version = tuple(map(int, M.PACKAGE_VERSION[M.PACKAGES[0]].split(".")))
        current = tuple(map(int, data["package_version"].split(".")))
        candidate = RevisionCandidate(ROOT, WORKSPACE, **kwargs)
        if data.get("snapshot", {}).get("revision_20260927b") is not None:
            # 主会话暂存回写后：候选 = live + 本修订（第三轮回写后 = 再加第三轮覆盖，版本号只升不降）。
            self.assertLessEqual(version, current)
            import wf_share_update_codec as X
            later = batch3_output(out)
            leader = X.unpack(candidate.read("common", "master/ability/leader_ability.orderedmap"))
            self.assertIn(X.csv_read(leader[M.LEADER]), (out["leader"][M.LEADER], later["leader"][M.LEADER]))
            cas = X.unpack(candidate.read("common", "master/string/custom_ability_string.orderedmap"))
            self.assertIn(X.csv_read(cas[M.CAS_LEADER]), (out["cas"][M.CAS_LEADER], later["cas"][M.CAS_LEADER]))
            import wf_balance_20260927d_ginovi as D
            devoured = {M.SKILL_PROGRAMS[1], M.SKILL_PROGRAMS[2]}
            for program, tree in out["dsl"].items():
                raw = candidate.read("common", wf_dsl.dsl_logical(program))
                accepted = [tree] + ([D.insert_devour(tree)] if program in devoured else [])   # d 回写后技能两档带吞噬
                self.assertIn(wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"], accepted, program)
            self.assertEqual(before, manifest.read_bytes())
            return
        self.assertGreater(version, current)
        for program in out["dsl"]:            # 七棵树都已被候选认领（无需 new_programs）
            self.assertIn(("common", wf_dsl.dsl_logical(program)), candidate.index)
        candidate.splice("master/ability/leader_ability.orderedmap", out["leader"])
        candidate.splice("master/string/custom_ability_string.orderedmap", out["cas"])
        for program, tree in out["dsl"].items():
            candidate.emit("common", wf_dsl.dsl_logical(program), encode_tree(tree))
        evidence = candidate.finish({"dry_run": True}, apply=False)
        self.assertFalse(evidence["applied"])
        self.assertEqual(len(evidence["changed_files"]), 2 + len(out["dsl"]))
        self.assertEqual(before, manifest.read_bytes())


if __name__ == "__main__":
    unittest.main()
