# -*- coding: utf-8 -*-
"""基诺维 169999 ``ginovi`` 2026-09-27 平衡第四轮（d）：技能「掠影协奏」吞噬协力球。

作者原话「基诺维的技能能不能添加效果扣除协力球100%生命值,每消灭一个协力球自身攻击力+50%」；选择题四项：
只吃角色召唤球 / 每次施放覆盖上限 9 个 / 技能本体就有 / 保留奈芙联动（见模块 docstring）。

fixture = live 1.4.1055 输入快照（``fixtures/balance_20260927d_ginovi.json``，extra6 ``make_read(live_only=True)``），
驱动 ``revise()``：节点结构锁（先数后删、三处同一非空 ID 表、键串非空唯一、带 mul、-17/种类 3、不在 TargetMate
作用域、在旗号分支外两档都有、0 球空分支）、静态门禁（签名 / AMF3 往返 / subject_binding / lookup_scope / element /
hit_area / 血契）、六处技能说明一致、BEFORE 漂移拒绝、不改输入、对自身输出重跑拒绝、白名单 == live 重扫、
生成器输出 == revise() 输出、候选干跑。**不跑** ``build_workspace.py build``/``kit-v3``（会写包）。
"""
from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

pass  # Imports resolve from this checkout/package, not external source copies.
sys.setrecursionlimit(10000)

import wf_balance_20260927c_ginovi as C3  # noqa: E402
import wf_balance_20260927d_ginovi as M  # noqa: E402
import wf_dsl  # noqa: E402
import wf_mod_tool as core  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927d_ginovi.json'
WORKSPACE = ROOT / "work/character_packs" / M.PACKAGES[0]
BUILD_SCRIPT = WORKSPACE / "build_workspace.py"
P1, P2 = M.PROGRAMS["1"], M.PROGRAMS["2"]


def load_fixture() -> dict:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return {kind: value for kind, value in data.items() if not kind.startswith("_")}


def reader(data: dict):
    def read(kind, key):
        return data[kind][key if isinstance(key, str) else "|".join(key)]
    return read


def _store():
    profile = core.resolve_profile()
    return profile.store if profile is not None and profile.store.is_dir() else None


def load_generator():
    spec = importlib.util.spec_from_file_location("ginovi_build_workspace_d", BUILD_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def devour(tree):
    return M.commands(tree, "ConditionalsMultiballNumber")[0]


class ReviseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))

    # ---------------------------------------------------------------- 契约

    def test_fixture_is_the_reviewed_baseline(self):
        for (kind, key), want in M.BEFORE.items():
            self.assertEqual(M.digest(self.live[kind][key]), want, f"{kind}:{key}")
        self.assertEqual({(kind, key) for kind, keys in self.live.items() for key in keys}, set(M.BEFORE))

    def test_module_contract_exports(self):
        self.assertEqual((M.CID, M.CODE), ("169999", "ginovi"))
        self.assertEqual(M.PACKAGES, ["ginovi"])
        self.assertEqual(M.PACKAGE_VERSION, {"ginovi": "0.3.3"})
        before = tuple(map(int, C3.PACKAGE_VERSION["ginovi"].split(".")))
        self.assertGreater(tuple(map(int, M.PACKAGE_VERSION["ginovi"].split("."))), before)   # 只升不降
        self.assertEqual(M.CAPABILITIES, [])
        self.assertEqual(M.REVIEWED_DRIFT, {})
        self.assertFalse(self.out["notes"]["runtime_verified"])
        json.dumps(self.out["notes"], ensure_ascii=False)

    def test_only_changed_keys_are_returned(self):
        out = self.out
        self.assertEqual(set(out["dsl"]), {P1, P2})
        self.assertEqual(set(out["action"]), {M.CODE})
        self.assertEqual(set(out["text"]), {M.CID})
        self.assertEqual(set(out["server_text"]), {M.CID})
        for kind in ("ability", "leader", "cas", "table"):
            self.assertEqual(out[kind], {}, kind)
        self.assertEqual(out["new_programs"], [])

    # ---------------------------------------------------------------- DSL

    def test_only_the_devour_node_is_inserted_before_the_flag(self):
        for program in (P1, P2):
            old, new = self.live["dsl"][program], self.out["dsl"][program]
            with self.subTest(program=program):
                self.assertEqual(new[:11], old[:11])
                body_old, body_new = old[11][1], new[11][1]
                index = M.flag_index(old)
                self.assertEqual(len(body_new), len(body_old) + 1)
                self.assertEqual(body_new[:index] + body_new[index + 1:], body_old)
                self.assertEqual(body_new[index], M.devour_node())
                self.assertTrue(M.is_command(body_new[index + 1], "ConditionalsChangeSkillFlag"))
        self.assertEqual(self.out["dsl"][P1][11], self.out["dsl"][P2][11])       # 两档同一棵根

    def test_devour_is_outside_the_flag_branches(self):
        """技能本体：节点在旗号分支之外 ⇒ 技能 / 技能＋、强化 / 非强化都执行；两支里都没有吞噬命令。"""
        tree = self.out["dsl"][P1]
        flag = M.commands(tree, "ConditionalsChangeSkillFlag")[0]
        for branch in (flag[1][2], flag[1][3]):
            for name in M.DEVOUR_COMMANDS:
                self.assertEqual(M.commands(branch, name), [], name)
        self.assertIn(devour(tree), tree[11][1])

    def test_count_then_remove_then_buff(self):
        """陷阱 3：先数后删（删后待发/入场中的球已销毁，计数不全）。"""
        gate = devour(self.out["dsl"][P1])[1]
        names = [node[1][0] for node in gate[4][1]]
        self.assertEqual(names, ["MultiballNumberVariable", "RemoveMultiball", "CreateCondition"])
        self.assertEqual(gate[5], ["Block", []])                                 # 0 球：不执行、不覆盖已有加成
        self.assertEqual((gate[2], gate[3]), ([], 1))                             # ≥1 个才进
        swapped = deepcopy(self.out["dsl"][P1])
        inner = devour(swapped)[1][4][1]
        inner[0], inner[1] = inner[1], inner[0]
        self.assertTrue(M.devour_problems(swapped))

    def test_three_id_lists_are_the_same_non_empty_whitelist(self):
        """陷阱 2：RemoveMultiball 的 [] = 全部；另两处 [] = 一个都不匹配 ⇒ 三处同一非空表。"""
        gate = devour(self.out["dsl"][P1])[1]
        variable, remover = gate[4][1][0][1], gate[4][1][1][1]
        lists = (gate[1], variable[3], remover[2])
        for ids in lists:
            self.assertEqual(ids, list(M.DEVOUR_IDS))
        self.assertTrue(M.DEVOUR_IDS)
        self.assertEqual((variable[2], remover[1]), (False, False))              # 基诺维自己不召球
        self.assertEqual(variable[4:], [[], 1, 9])                               # V = min(个数/1, 9)
        for index, mutate in ((0, lambda g: g.__setitem__(1, [])),
                              (1, lambda g: g[4][1][1][1].__setitem__(2, [])),
                              (2, lambda g: g[4][1][0][1].__setitem__(3, list(M.DEVOUR_IDS[:-1]))),
                              (3, lambda g: g[4][1][1][1].__setitem__(1, True)),
                              (4, lambda g: g[4][1][0][1].__setitem__(6, 99))):
            broken = deepcopy(self.out["dsl"][P1])
            mutate(devour(broken)[1])
            with self.subTest(mutation=index):
                self.assertTrue(M.devour_problems(broken))

    def test_condition_key_is_non_empty_unique_and_the_buff_reads_the_variable(self):
        """陷阱 1：键串空 ⇒ 与强化支固定 +50%（750 帧、键串空）同 gid，被整条覆盖成 +50%。"""
        tree = self.out["dsl"][P1]
        buff = devour(tree)[1][4][1][2][1]
        key = buff[7]
        self.assertEqual(key, "ginovi_devour")
        keys = M.condition_keys(tree)
        self.assertEqual(keys.count(key), 1)
        self.assertEqual(set(keys) - {key}, {""})                                 # 树内其他键串都是空串
        self.assertEqual(buff[1:3], [-17, [["ACAttackPoint", [{"min": 750, "max": 750}],
                                            [{"min": 0.5, "max": 0.5, "mul": 1}], [{"min": 1, "max": 1}]]]])
        self.assertEqual(buff[10], 3)                                             # 付与种类 3（角色）
        # 同形对照：强化支固定 +50% 与本节点只差键串与 mul（所以键串必须把两者分开）。
        flag = M.commands(tree, "ConditionalsChangeSkillFlag")[0]
        extra = [node[1] for node in M.commands(flag[1][2], "CreateCondition")
                 if node[1][2][0][0] == "ACAttackPoint" and node[1][2][0][2][0]["max"] == M.SKILL_ATTACK_UP_EXTRA]
        self.assertTrue(extra)
        self.assertEqual({node[7] for node in extra}, {""})
        self.assertEqual(extra[0][2][0][1], buff[2][0][1])                        # 同为 750 帧
        for mutate in (lambda b: b.__setitem__(7, ""), lambda b: b.__setitem__(7, None),
                       lambda b: b[2][0][2][0].pop("mul"), lambda b: b.__setitem__(1, 0),
                       lambda b: b.__setitem__(10, 2), lambda b: b[2][0][1][0].update(min=600, max=600)):
            broken = deepcopy(tree)
            mutate(devour(broken)[1][4][1][2][1])
            with self.subTest(mutate=mutate):
                self.assertTrue(M.devour_problems(broken))
        clash = deepcopy(tree)
        flag = M.commands(clash, "ConditionalsChangeSkillFlag")[0]
        next(node for node in M.commands(flag[1][2], "CreateCondition"))[1][7] = key
        self.assertTrue(M.devour_problems(clash))

    def test_not_in_target_mate_scope(self):
        """陷阱 4：联机跨机只许治疗/状态；吞噬 buff 打自身 -17，节点不在含 TargetMate 的块里。"""
        tree = self.out["dsl"][P1]
        mate_binds = {node[1][1] for node in M.commands(tree, "TargetMate")}
        self.assertTrue(mate_binds)
        self.assertNotIn(-17, mate_binds)
        self.assertFalse(any(M.is_command(x, "TargetMate") for x in tree[11][1]))
        broken = deepcopy(tree)
        broken[11][1].insert(0, ["Command", ["TargetMate", 41, [], [], [], [], []]])
        self.assertIn("devour node sits in a block with TargetMate", M.devour_problems(broken))

    def test_static_gates_pass(self):
        for program in (P1, P2):
            tree = self.out["dsl"][program]
            with self.subTest(program=program):
                self.assertEqual(M.devour_problems(tree), [])
                self.assertEqual(M.tree_gate_problems(tree), [])
                self.assertEqual(wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"], tree)

    # ---------------------------------------------------------------- 白名单

    def test_whitelist_rule(self):
        ids = M.DEVOUR_IDS
        self.assertEqual(list(ids), sorted(set(ids)))
        self.assertEqual(len(ids), 48)
        for ball in (1199891, 1001, 1002, 1003, 1004, 1005, 1006, 202001, 0,
                     3110021, 3110022, 3110023, 3310101, 3310102):
            self.assertNotIn(ball, ids)                                           # 幼龙 / 炸弹 / 敌方 / NPC / kind=1
        for ball in M.NEPHTIM_BALLS + (1399961, 1611051, 1610511, 1610512):
            self.assertIn(ball, ids)                                              # 奈芙联动 / 暗系召唤者 / 能力召唤

    @unittest.skipUnless(_store() is not None, "需要 live store")
    def test_whitelist_equals_a_fresh_live_scan(self):
        scan = M.scan_devour_ids(_store())
        self.assertEqual(scan["ids"], M.DEVOUR_IDS)
        self.assertEqual({ball for ball, kind in scan["kinds"].items() if kind != M.LIVING_KIND},
                         {3110021, 3110022, 3110023, 3310101, 3310102})
        self.assertIn(1199891, scan["summoned"])                                  # 在扫描里、被规则排除
        self.assertEqual(set(scan["summoned"]) - set(M.DEVOUR_IDS),
                         {1199891, 3110021, 3110022, 3110023, 3310101, 3310102})
        for ball, programs in scan["summoned"].items():
            self.assertTrue(programs, ball)

    # ---------------------------------------------------------------- 技能说明

    def test_six_descriptions_agree_and_only_append_the_devour_sentence(self):
        descs = ([fields[1] for _inner, fields in self.out["action"][M.CODE]]
                 + [rows[0][c] for kind in ("text", "server_text") for rows in self.out[kind].values() for c in (5, 7)])
        self.assertEqual(descs, [M.NEW_DESC] * 6)
        self.assertEqual(M.NEW_DESC, M.OLD_DESC + "；吞噬场上被召唤的协力球，赋予自身攻击力提升效果【效果随吞噬数量提升[最大9个]】")
        self.assertIn(f"[最大{M.DEVOUR_CAP}个]", M.DEVOUR_DESC)                   # 本体上限照写
        self.assertFalse(any(ch.isdigit() for ch in M.DEVOUR_DESC.replace(f"[最大{M.DEVOUR_CAP}个]", "")))
        self.assertEqual(M.desc_problems(M.NEW_DESC), [])

    def test_other_text_cells_are_unchanged(self):
        for (inner, old), (inner2, new) in zip(self.live["action"][M.CODE], self.out["action"][M.CODE]):
            self.assertEqual(inner, inner2)
            self.assertEqual([c for i, c in enumerate(new) if i != 1], [c for i, c in enumerate(old) if i != 1])
        for kind in ("text", "server_text"):
            old, new = self.live[kind][M.CID][0], self.out[kind][M.CID][0]
            self.assertEqual([c for i, c in enumerate(new) if i not in (5, 7)],
                             [c for i, c in enumerate(old) if i not in (5, 7)])

    # ---------------------------------------------------------------- fail closed

    def test_input_is_not_mutated_and_output_is_detached(self):
        live = deepcopy(self.live)
        out = M.revise(reader(live))
        self.assertEqual(live, self.live)
        out["dsl"][P1][11][1].clear()
        out["action"][M.CODE][0][1][1] = "x"
        out["text"][M.CID][0][5] = "x"
        self.assertEqual(live, self.live)
        self.assertEqual(M.revise(reader(deepcopy(self.live)))["dsl"], self.out["dsl"])

    def test_baseline_drift_is_rejected(self):
        for kind, key in M.BEFORE:
            drifted = deepcopy(self.live)
            value = drifted[kind][key]
            if kind == "dsl":
                value[11][1].append(["Command", ["ShakeCamera", 1]])
            elif kind == "action":
                value[0][1][1] += "x"
            else:
                value[0][5] += "x"
            with self.subTest(kind=kind, key=key), self.assertRaisesRegex(M.GinoviDevourError, "live drift"):
                M.revise(reader(drifted))
            missing = deepcopy(self.live)
            missing[kind][key] = None
            with self.assertRaises(M.GinoviDevourError):
                M.revise(reader(missing))

    def test_revise_is_not_reapplicable_to_its_own_output(self):
        live = deepcopy(self.live)
        for kind in ("dsl", "text", "server_text"):
            live[kind].update(deepcopy(self.out[kind]))
        live["action"][M.CODE] = [list(x) for x in deepcopy(self.out["action"][M.CODE])]
        with self.assertRaisesRegex(M.GinoviDevourError, "live drift"):
            M.revise(reader(live))
        self.assertTrue(M.preimage_problems(self.out["dsl"][P1]))
        with self.assertRaises(M.GinoviDevourError):
            M.revise_texts({("action", M.CODE): self.out["action"][M.CODE], ("text", M.CID): self.live["text"][M.CID],
                            ("server_text", M.CID): self.live["server_text"][M.CID]})


@unittest.skipUnless(BUILD_SCRIPT.is_file(), "需要基诺维生成器 build_workspace.py")
class GeneratorTests(unittest.TestCase):
    """生成器 build_workspace.py 重跑不能丢掉吞噬：纯函数输出 == revise() 输出。"""

    @classmethod
    def setUpClass(cls):
        cls.gen = load_generator()
        cls.out = M.revise(reader(load_fixture()))

    def test_generator_constants_equal_module_constants(self):
        gen = self.gen
        self.assertEqual(gen.DEVOUR_IDS, M.DEVOUR_IDS)
        self.assertEqual(gen.DEVOUR_EXCLUDED_IDS, M.DEVOUR_EXCLUDED_IDS)
        self.assertEqual((gen.DEVOUR_VARIABLE, gen.DEVOUR_CAP, gen.DEVOUR_ATTACK, gen.DEVOUR_FRAMES,
                          gen.DEVOUR_CONDITION_KEY),
                         (M.DEVOUR_VARIABLE, M.DEVOUR_CAP, M.DEVOUR_ATTACK, M.DEVOUR_FRAMES, M.DEVOUR_CONDITION_KEY))
        self.assertEqual(gen.DEVOUR_FRAMES, gen.SKILL_BUFF_FRAMES)
        self.assertEqual(gen.SKILL_ATTACK_UP_EXTRA, M.SKILL_ATTACK_UP_EXTRA)
        self.assertEqual(gen.skill_devour_multiballs(), M.devour_node())

    def test_generator_root_equals_revise_output(self):
        root = self.gen.m4_skill_root()
        for program in (P1, P2):
            self.assertEqual(root, self.out["dsl"][program][11], program)

    def test_generator_descriptions_equal_revise_output(self):
        gen = self.gen
        self.assertEqual(gen.CT_SKILL_DESC, M.NEW_DESC)
        self.assertEqual((gen.CHARACTER_TEXT_COLUMNS[5], gen.CHARACTER_TEXT_COLUMNS[7]), (M.NEW_DESC, M.NEW_DESC))
        self.assertNotIn("吞噬", gen.CHANGE_SKILL_TEXT)                           # 不写进强化条目
        self.assertFalse(any("吞噬" in line for lines in gen.DESC_OVERRIDE_LINES.values() for line in lines))

    def test_generator_gates_on_the_new_root(self):
        gen = self.gen
        root = self.out["dsl"][P1][11]
        self.assertEqual(gen.validate_dsl_signatures(root), [])
        self.assertEqual(gen.verify_first_cast_pact(root)["drain_ratio"], 0.95)


@unittest.skipUnless((WORKSPACE / "package/manifest.json").is_file()
                     and (ROOT / "mod-tools/profiles.json").is_file(),
                     "local candidate workspace required")
class CandidateTests(unittest.TestCase):
    def test_candidate_accepts_the_revision_dry(self):
        import wf_share_update_codec as X
        from wf_character_revision import RevisionCandidate, encode_tree
        out = M.revise(reader(load_fixture()))
        manifest = WORKSPACE / "package/manifest.json"
        before = manifest.read_bytes()
        data = json.loads(before)
        version = tuple(map(int, M.PACKAGE_VERSION[M.PACKAGES[0]].split(".")))
        current = tuple(map(int, data["package_version"].split(".")))
        candidate = RevisionCandidate(ROOT, WORKSPACE, character_id=M.CID, code_name=M.CODE,
                                      snapshot_key="revision_20260927e",
                                      package_version=M.PACKAGE_VERSION[M.PACKAGES[0]],
                                      baseline_factory=lambda *a, **k: None, reviewed_input_drift=M.REVIEWED_DRIFT)
        if current >= version:
            # 主会话暂存回写后：候选 = live + 本修订。
            for program, tree in out["dsl"].items():
                self.assertEqual(candidate.read("common", wf_dsl.dsl_logical(program)), encode_tree(tree), program)
            text = X.unpack(candidate.read("common", "master/character/character_text.orderedmap"))
            self.assertEqual(X.csv_read(text[M.CID]), out["text"][M.CID])
            self.assertEqual(before, manifest.read_bytes())
            return
        candidate.splice("master/character/character_text.orderedmap", out["text"])
        candidate.splice("master/skill/action_skill.orderedmap",
                         {M.CODE: core.encode_action_skill_row(out["action"][M.CODE])}, codec="action_nested")
        for program, tree in out["dsl"].items():
            candidate.emit("common", wf_dsl.dsl_logical(program), encode_tree(tree))
        candidate.server_character_row("cdndata/character_text.json", out["server_text"][M.CID])
        evidence = candidate.finish({"dry_run": True}, apply=False)
        self.assertFalse(evidence["applied"])
        self.assertEqual(len(evidence["changed_files"]), 5)
        self.assertEqual(before, manifest.read_bytes())


if __name__ == "__main__":
    unittest.main()
