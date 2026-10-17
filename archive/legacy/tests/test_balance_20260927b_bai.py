# -*- coding: utf-8 -*-
"""白「盛夏的咆哮」149990 2026-09-27 第二批修订：Fever 每 1.5 秒成长放缓、技能与强化弹射 Down 压到上限内。

fixture（``fixtures/balance_20260927b_bai.json``）是 live 1.4.1049 的 revise() 输入快照；
只有候选包干跑用例需要本机工作区（skipUnless）。不写 live store / assets / .cdn / 候选包。
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[2]
pass  # Imports resolve from this checkout/package, not external source copies.
sys.setrecursionlimit(10000)

import wf_balance_20260927b_bai as M  # noqa: E402
import wf_dsl  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_share_update_codec as X  # noqa: E402
import wf_summer_bai_ability as GEN_ABILITY  # noqa: E402
import wf_summer_bai_fever_damage as GEN_FEVER  # noqa: E402
from wf_character_revision import encode_tree  # noqa: E402
from wf_client_legality import (client_legality_problems, declared_block_field_problems,  # noqa: E402
                                invoke_skill_string_problems, required_client_capabilities)
from wf_midautumn_kit_hibiki import dsl_problems as kit_dsl_problems  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures/balance_20260927b_bai.json"
WORKSPACE = ROOT / "work/character_packs" / M.PACKAGES[0]
PRE_REVISION_VERSION = (1, 0, 2)      # white_tiger_summer 候选在本批之前的 package_version
SNAPSHOT_KEY = "revision_20260927b"

SKILL1, SKILL2 = M.SKILL_PROGRAMS[1], M.SKILL_PROGRAMS[2]
#: 两档技能里 p13=1.625 的两处攻击（750 帧领域斩击、技能旗分支斩击）。
SKILL_SLASH_PATHS = ((11, 1, 8, 1, 23, 1, 0, 1),
                     (11, 1, 9, 1, 2, 1, 3, 1, 6, 1, 0, 1, 23, 1, 1, 1))
#: PF 碰撞块爆裂参考点内两处攻击。
PF_BURST_PATHS = ((11, 1, 4, 1, 5, 1, 4, 1, 11, 1, 1, 1, 23, 1, 0, 1),
                  (11, 1, 4, 1, 5, 1, 4, 1, 11, 1, 2, 1, 3, 1, 0, 1, 23, 1, 0, 1))


def _key(kind, key):
    return "|".join(key) if kind == "table" else key


def differences(left, right, path=()):
    if isinstance(left, list) and isinstance(right, list) and len(left) == len(right):
        return [change for i, (a, b) in enumerate(zip(left, right))
                for change in differences(a, b, path + (i,))]
    if isinstance(left, dict) and isinstance(right, dict) and left.keys() == right.keys():
        return [change for key in left for change in differences(left[key], right[key], path + (key,))]
    return [] if left == right else [(path, left, right)]


def at(tree, path):
    for index in path:
        tree = tree[index]
    return tree


class BaiBalanceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = json.loads(FIXTURE.read_bytes())["inputs"]
        cls.out = M.revise(cls.read_from(cls.inputs))

    @staticmethod
    def read_from(inputs):
        return lambda kind, key: inputs[kind][_key(kind, key)]

    def old(self, kind, key):
        return self.inputs[kind][_key(kind, key)]

    # ------------------------------------------------------------ 契约

    def test_fixture_is_the_reviewed_baseline(self):
        self.assertEqual(9, len(M.BEFORE))
        for (kind, key), want in M.BEFORE.items():
            self.assertEqual(want, M.digest(self.old(kind, key)), (kind, key))

    def test_module_contract_constants(self):
        self.assertEqual(("149990", "white_tiger_summer"), (M.CID, M.CODE))
        self.assertEqual(["white_tiger_summer"], M.PACKAGES)
        self.assertEqual({"white_tiger_summer": "1.0.3"}, M.PACKAGE_VERSION)
        self.assertEqual([], M.CAPABILITIES)
        self.assertEqual({}, M.REVIEWED_DRIFT)
        version = tuple(int(x) for x in M.PACKAGE_VERSION["white_tiger_summer"].split("."))
        self.assertGreater(version, PRE_REVISION_VERSION)
        manifest = WORKSPACE / "package/manifest.json"
        if manifest.is_file():
            current = json.loads(manifest.read_bytes())["package_version"]
            # 第三轮（c）回写后候选前进到 wf_balance_20260927c_bai 声明值；第二批 / 第三轮两种状态都合法。
            import wf_balance_20260927c_bai as C3
            batch3 = tuple(int(x) for x in C3.PACKAGE_VERSION[M.PACKAGES[0]].split("."))
            self.assertLessEqual(tuple(int(x) for x in current.split(".")), max(version, batch3))
        self.assertFalse(self.out["notes"]["runtime_verified"])
        json.dumps(self.out["notes"], ensure_ascii=False)

    def test_output_shape_and_only_changed_keys(self):
        self.assertEqual({"ability", "leader", "cas", "text", "table", "action", "dsl",
                          "server_text", "new_programs", "notes"}, set(self.out))
        self.assertEqual([M.LEADER], list(self.out["leader"]))
        self.assertEqual([M.CAS_LEADER], list(self.out["cas"]))
        self.assertEqual({SKILL1, SKILL2, *M.PF_PROGRAMS.values()}, set(self.out["dsl"]))
        for kind in ("ability", "text", "table", "action", "server_text"):
            self.assertEqual({}, self.out[kind], kind)
        self.assertEqual([], self.out["new_programs"])
        for key in self.out["cas"]:
            self.assertTrue(key.startswith("desc_override_" + M.CODE))

    # ------------------------------------------------------------ 成长：队长 #3/#4

    def test_leader_only_fever_tick_strength_changes(self):
        old, new = self.old("leader", M.LEADER), self.out["leader"][M.LEADER]
        self.assertEqual(6, len(new))
        seen = {i: {c: (x, y) for c, (x, y) in enumerate(zip(a, b)) if x != y}
                for i, (a, b) in enumerate(zip(old, new)) if a != b}
        self.assertEqual({3: {49: ("50000", "5000"), 50: ("50000", "5000")},
                          4: {49: ("50000", "5000"), 50: ("50000", "5000")}}, seen)
        for i in (3, 4):
            row = new[i]
            self.assertEqual(124, len(row))
            self.assertEqual(("248", "9000000", "9000000", "(None)", "0", "5", "Green"),
                             (row[25], row[28], row[29], row[32], row[33], row[46], row[47]))
        self.assertEqual(("32", "388"), (new[3][45], new[4][45]))

    def test_charge_and_other_leader_rows_stay_verbatim(self):
        old, new = self.old("leader", M.LEADER), self.out["leader"][M.LEADER]
        for i in (0, 1, 2, 5):
            self.assertEqual(old[i], new[i], i)
        # 口径 A.6：进 Fever 风队技能槽充能 +100%（kind 35）属于充能，本批不动。
        self.assertEqual(("8", "35", "5", "100000", "100000", "(None)"),
                         tuple(new[0][c] for c in (25, 45, 46, 49, 50, 32)))
        self.assertEqual(("722", "white_tiger_summer_pf"), (new[5][45], new[5][80]))

    def test_growth_step_is_one_tenth_for_thirty_plus_ticks(self):
        # 下限：两次 Fever（900 帧 ×1.5）不计 724 续时 = 30 跳 ⇒ ≥30 档 ×1/10。
        self.assertEqual(30, 2 * 900 * 3 // 2 // 90)
        self.assertEqual(int(M.FEVER_TICK_OLD) // 10, int(M.FEVER_TICK_NEW))

    def test_panel_only_line_five_changes_and_passes_rules(self):
        old = self.old("cas", M.CAS_LEADER)[0][0].split("\n")
        text = self.out["cas"][M.CAS_LEADER]
        self.assertEqual(1, len(text))
        self.assertEqual(1, len(text[0]))
        new = text[0][0].split("\n")
        self.assertEqual(6, len(new))
        self.assertEqual({4}, {i for i, (a, b) in enumerate(zip(old, new)) if a != b})
        self.assertEqual("风属性共鸣时，FEVER模式中每持续1.5秒，风属性角色攻击力＋5%、能力伤害＋5%", new[4])
        self.assertEqual("风属性共鸣时，风属性角色进入FEVER模式时技能槽充能速度＋100%", new[1])
        self.assertEqual([], KL.panel_problems(text[0][0]))
        for word in ("可无限", "无上限", "无限叠加", "不设上限", "自身为队长时", "／"):
            self.assertNotIn(word, text[0][0])

    def test_leader_rows_pass_client_gates(self):
        for i, row in enumerate(self.out["leader"][M.LEADER]):
            self.assertEqual([], client_legality_problems("leader_ability", row), i)
            self.assertEqual([], declared_block_field_problems("leader_ability", row), i)
            self.assertEqual([], invoke_skill_string_problems(row, set(), "leader_ability"), i)
            self.assertEqual([], required_client_capabilities("leader_ability", row), i)

    # ------------------------------------------------------------ Down：技能

    def test_skill_only_slash_p13_changes_in_both_levels(self):
        for program in (SKILL1, SKILL2):
            old, new = self.old("dsl", program), self.out["dsl"][program]
            expected = [(path + (13, 0, bound), 1.625, 0.75)
                        for path in SKILL_SLASH_PATHS for bound in ("min", "max")]
            self.assertEqual(expected, differences(old, new), program)
            for path in SKILL_SLASH_PATHS:
                self.assertEqual("CreateNormalAttack", at(new, path)[0])
            fever = [n for _, b in M._nodes(new, "ConditionalsFeverMode")
                     for _, n in M._nodes(b[1], "CreateNormalAttack")]
            self.assertEqual([[{"min": 8, "max": 8}]], [a[13] for a in fever])
            self.assertEqual([{"min": 75.0, "max": 75.0}], fever[0][6])

    def test_skill_single_target_down_is_within_cap(self):
        for program in (SKILL1, SKILL2):
            self.assertEqual(51.875, M.single_target_down(self.old("dsl", program)))
            after = M.single_target_down(self.out["dsl"][program])
            self.assertEqual(28.25, after)
            self.assertLessEqual(after, 30)
        area = at(self.out["dsl"][SKILL1], (11, 1, 8, 1))
        self.assertEqual(["SpecifyHitAreaLifetimeDirectly", 750], area[13])
        self.assertEqual(["SpecifyMinHitIntervalDirectly", 30], area[14])
        self.assertEqual(26, M.area_hits(area))

    # ------------------------------------------------------------ Down：强化弹射

    def test_pf_only_burst_p13_changes(self):
        for level, program in M.PF_PROGRAMS.items():
            old, new = self.old("dsl", program), self.out["dsl"][program]
            before, after = M.PF_BURST_DOWN[level]
            expected = [(path + (13, 0, bound), before, after)
                        for path in PF_BURST_PATHS for bound in ("min", "max")]
            self.assertEqual(expected, differences(old, new), program)
            ref = at(new, (11, 1, 4, 1, 5, 1, 4, 1))
            self.assertEqual(("CreateReferencePoint", -18, 101), (ref[0], ref[1], ref[10]))

    def test_pf_down_totals_hit_the_caps_exactly(self):
        for level, program in M.PF_PROGRAMS.items():
            old_total, new_total = {1: (27, 15), 2: (35, 20), 3: (45, 25)}[level]
            self.assertEqual(old_total, M.single_target_down(self.old("dsl", program)), level)
            self.assertEqual(new_total, M.single_target_down(self.out["dsl"][program]), level)
            downs = [a[13][0]["max"] for _, a in M._nodes(self.out["dsl"][program], "CreateNormalAttack")]
            fighter = {1: 3, 2: 4, 3: 6}[level]
            finish = {1: 10.5, 2: 13, 3: 17}[level]
            burst = {1: 1, 2: 1.25, 3: 1.25}[level]
            self.assertEqual([burst, burst] + [0.5] * fighter + [finish], downs, level)

    # ------------------------------------------------------------ DSL 门禁

    def test_dsl_roundtrip_and_four_gates(self):
        for program, tree in self.out["dsl"].items():
            self.assertEqual([], M.dsl_problems(tree), program)
            decoded = wf_dsl.parse_dsl(zlib.decompress(encode_tree(tree), -15))["tree"]
            self.assertEqual(tree, decoded, program)
            # 更严的套件门禁：不得新增问题（技能树 live 既有「绑定号 0 重复」与本次无关）。
            self.assertEqual(kit_dsl_problems(self.old("dsl", program), element=M.ELEMENT),
                             kit_dsl_problems(tree, element=M.ELEMENT), program)

    # ------------------------------------------------------------ 失败关闭

    def test_live_drift_is_rejected_and_inputs_are_not_mutated(self):
        original = deepcopy(self.inputs)
        M.revise(self.read_from(self.inputs))
        self.assertEqual(original, self.inputs)
        for kind, key in M.BEFORE:
            drifted = deepcopy(self.inputs)
            value = drifted[kind][_key(kind, key)]
            if kind == "dsl":
                value[1] = value[1] + 1
            elif kind == "action":
                value[0][1][0] += "x"
            else:
                value[0][-1] = value[0][-1] + "x"
            with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
                M.revise(self.read_from(drifted))
            missing = deepcopy(self.inputs)
            missing[kind][_key(kind, key)] = None
            with self.assertRaises(ValueError):
                M.revise(self.read_from(missing))

    def test_already_revised_live_is_not_revised_twice(self):
        live = deepcopy(self.inputs)
        live["leader"].update(deepcopy(self.out["leader"]))
        live["cas"].update(deepcopy(self.out["cas"]))
        live["dsl"].update(deepcopy(self.out["dsl"]))
        with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
            M.revise(self.read_from(live))
        # 纯函数层也拒绝自身输出（第二道锁）。
        with self.assertRaisesRegex(ValueError, "preimage"):
            M.leader_rows(self.out["leader"][M.LEADER])
        with self.assertRaisesRegex(ValueError, "panel text layout"):
            M.leader_text(self.out["cas"][M.CAS_LEADER])
        for program in (SKILL1, SKILL2):
            with self.assertRaisesRegex(ValueError, "Down preimage drift"):
                M.skill_tree(self.out["dsl"][program])
        for level, program in M.PF_PROGRAMS.items():
            with self.assertRaisesRegex(ValueError, "burst preimage drift"):
                M.pf_tree(self.out["dsl"][program], level)

    # ------------------------------------------------------------ 生成器同步

    def test_summer_generators_are_idempotent_on_revised_skills(self):
        """两个增量修订脚本不碰 p13；重跑它们得到的就是本模块输出（不回退本批 Down）。"""
        for level, program in M.SKILL_PROGRAMS.items():
            tree = self.out["dsl"][program]
            self.assertEqual(tree, GEN_ABILITY.native_reference(tree), program)
            self.assertEqual(tree, GEN_FEVER.fever_damage(tree, level), program)
        self.assertEqual("1.0.3", GEN_ABILITY.package_version(M.PACKAGE_VERSION[M.PACKAGES[0]]))

    def test_descriptions_carry_no_changed_numbers(self):
        for level, row in self.old("action", M.ACTION):
            for word in ("Down", "虚弱", "眩晕", "削韧", "50%", "1.5秒"):
                self.assertNotIn(word, row[1], (level, word))

    # ------------------------------------------------------------ 候选干跑

    @unittest.skipUnless((WORKSPACE / "package/manifest.json").is_file()
                         and (ROOT / "mod-tools/profiles.json").is_file(),
                         "local candidate workspace required")
    def test_candidate_opens_clean_and_splices_dry(self):
        from wf_character_revision import RevisionCandidate
        manifest_path = WORKSPACE / "package/manifest.json"
        before = manifest_path.read_bytes()
        manifest = json.loads(before)
        current = manifest["package_version"]
        as_tuple = lambda v: tuple(int(x) for x in v.split("."))        # noqa: E731
        if as_tuple(current) > as_tuple(M.PACKAGE_VERSION[M.PACKAGES[0]]):
            self.skipTest("候选已前进到第三轮（c）；回写一致性见 test_balance_20260927c_bai")
        kwargs = dict(character_id=M.CID, code_name=M.CODE, snapshot_key=SNAPSHOT_KEY,
                      package_version=M.PACKAGE_VERSION[M.PACKAGES[0]],
                      baseline_factory=lambda *a, **k: None)
        candidate = RevisionCandidate(ROOT, WORKSPACE, reviewed_input_drift=M.REVIEWED_DRIFT, **kwargs)
        leader_logical = "master/ability/leader_ability.orderedmap"
        cas_logical = "master/string/custom_ability_string.orderedmap"
        if manifest.get("snapshot", {}).get(SNAPSHOT_KEY) is not None:
            # 回写后：候选与本模块输出逐项一致。
            self.assertEqual(M.PACKAGE_VERSION[M.PACKAGES[0]], current)
            leader = X.unpack(candidate.read("common", leader_logical))
            self.assertEqual(X.csv_write(self.out["leader"][M.LEADER]), leader[M.LEADER])
            cas = X.unpack(candidate.read("common", cas_logical))
            self.assertEqual(X.csv_write(self.out["cas"][M.CAS_LEADER]), cas[M.CAS_LEADER])
            for program, tree in self.out["dsl"].items():
                raw = candidate.read("common", wf_dsl.dsl_logical(program))
                self.assertEqual(tree, wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"], program)
            self.assertEqual(before, manifest_path.read_bytes())
            return
        self.assertEqual("1.0.2", current)
        # 暂存脚本同形：leader 走候选 splice；面板串按 stage_batch.Plan.splice 的键级合并。
        candidate.splice(leader_logical, self.out["leader"])
        cas = X.unpack(candidate.read("common", cas_logical))
        cas.update({key: X.csv_write(rows) for key, rows in self.out["cas"].items()})
        candidate.emit("common", cas_logical, X.pack(cas))
        for program, tree in self.out["dsl"].items():
            logical = wf_dsl.dsl_logical(program)
            self.assertIn(("common", logical), candidate.original, program)
            candidate.emit("common", logical, encode_tree(tree))
        evidence = candidate.finish({"dry_run": True}, apply=False)
        self.assertFalse(evidence["applied"])
        self.assertEqual(7, len(evidence["changed_files"]))
        self.assertEqual(before, manifest_path.read_bytes())


if __name__ == "__main__":
    unittest.main()
