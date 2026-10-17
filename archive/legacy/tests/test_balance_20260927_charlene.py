# -*- coding: utf-8 -*-
"""2026-09-27 平衡批次：夏琳 139992 修订模块 ``wf_balance_20260927_charlene`` 的单测。

fixture（``fixtures/balance_20260927_charlene.json``）存 revise() 的 live 输入快照与生成器用的官方 donor，
所以绝大多数用例离线可跑；只有「fixture 里的官方 donor 与 .cdn/cn 官方基线逐字一致」需要本机环境。
不写 live store / assets / .cdn / 候选包，不发布。
"""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_balance_20260927_charlene as M  # noqa: E402
import wf_client_legality as L  # noqa: E402
import wf_describe  # noqa: E402
import wf_dsl  # noqa: E402
import wf_midautumn_kit_charlene as KIT  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_mod_tool as core  # noqa: E402
from wf_character_revision import encode_tree  # noqa: E402
from wf_midautumn_kit_hibiki import dsl_problems  # noqa: E402

FIXTURE = Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927_charlene.json'
DATA = json.loads(FIXTURE.read_text(encoding="utf-8"))
PRE_REVISION_VERSION = (1, 0, 0)      # ma-charlene 候选在本批之前的 package_version


def live_values() -> dict:
    values = {}
    for entry in DATA["live"]:
        value = entry["value"]
        if entry["kind"] == "action":
            value = [(inner, fields) for inner, fields in value]   # contract：list[(inner_key, fields)]
        values[entry["kind"], entry["key"]] = value
    return values


def make_read(values: dict):
    def read(kind, key):
        return values[kind, key]
    return read


def revised(values: dict | None = None) -> dict:
    return M.revise(make_read(live_values() if values is None else values))


def _walk_commands(tree, name):
    return list(wf_dsl.iter_dsl_commands(tree, name))


def _roulettes(tree):
    return [args[1][1] for args in _walk_commands(tree, "ConditionalsProbability")]


def _branch_ac(branch):
    return branch[1][1][1][0][1][2][0][0]


class ContractTests(unittest.TestCase):
    def test_exports(self):
        self.assertEqual((M.CID, M.CODE), (KIT.CID_S, KIT.CODE))
        self.assertEqual(M.PACKAGES, ["ma-charlene"])
        self.assertEqual(M.CAPABILITIES, [])
        self.assertEqual(set(M.PACKAGE_VERSION), set(M.PACKAGES))
        self.assertEqual(set(M.BEFORE), {("ability", "1399921"), ("cas", M.CAS_KEY),
                                         ("text", "139992"), ("action", M.CODE),
                                         ("dsl", M.PROGRAMS["1"]), ("dsl", M.PROGRAMS["2"]),
                                         ("server_text", "139992")})
        for sha in M.BEFORE.values():
            self.assertRegex(sha, r"^[0-9a-f]{64}$")

    def test_package_version_moves_forward(self):
        version = tuple(int(x) for x in M.PACKAGE_VERSION["ma-charlene"].split("."))
        self.assertGreater(version, PRE_REVISION_VERSION)
        manifest = core.project_root() / "work/character_packs/ma-charlene/package/manifest.json"
        if manifest.is_file():
            data = json.loads(manifest.read_text(encoding="utf-8"))
            current = data["package_version"]
            # 第三轮（wf_balance_20260927c_panels，技能强化条目规范）暂存回写后候选再升一版，上限取那一版。
            import wf_balance_20260927c_panels as P3
            ceiling = P3.staged_version(data, "ma-charlene")
            if ceiling is not None:
                version = tuple(int(x) for x in ceiling.split("."))
            self.assertLessEqual(tuple(int(x) for x in current.split(".")), version)

    def test_fixture_matches_the_reviewed_digests(self):
        for (kind, key), value in live_values().items():
            self.assertEqual(M.digest(value), M.BEFORE[kind, key], f"{kind}:{key}")

    def test_output_shape_and_only_changed_keys(self):
        out = revised()
        self.assertEqual(set(out), {"ability", "leader", "cas", "text", "table", "action", "dsl",
                                    "server_text", "new_programs", "notes"})
        self.assertEqual(list(out["ability"]), ["1399921"])
        self.assertEqual(out["leader"], {})
        self.assertEqual(out["table"], {})
        self.assertEqual(list(out["cas"]), [M.CAS_KEY])
        self.assertEqual(list(out["text"]), ["139992"])
        self.assertEqual(list(out["action"]), [M.CODE])
        self.assertEqual(sorted(out["dsl"]), sorted(M.PROGRAMS.values()))
        self.assertEqual(list(out["server_text"]), ["139992"])
        self.assertEqual(out["new_programs"], [])
        json.dumps(out["notes"], ensure_ascii=False)

    def test_every_written_key_is_in_the_character_namespace(self):
        out = revised()
        for section in ("ability", "cas", "text", "server_text"):
            for key in out[section]:
                self.assertTrue(key.startswith((M.CID, M.CODE, "change_skill_" + M.CODE)), key)
        for program in out["dsl"]:
            self.assertIn(f"/{M.CODE}${M.CODE}_", program)


class AbilityTests(unittest.TestCase):
    def setUp(self):
        self.before = live_values()["ability", "1399921"]
        self.rows = revised()["ability"]["1399921"]

    def test_existing_records_are_kept_and_one_is_appended(self):
        self.assertEqual(len(self.rows), 3)
        self.assertEqual(self.rows[:2], self.before)
        self.assertEqual([r[47] for r in self.rows], ["211", "536", "53"])

    def test_new_record_is_party_thunder_stun_wince_slayer_behind_resonance(self):
        row = self.rows[2]
        self.assertEqual(len(row), 126)
        self.assertEqual(row[0:3], ["artificialeye_sniper_moon_1", "true", "attack_yellow"])
        self.assertEqual((row[6], row[9], row[10], row[11]), ("2", "600000", "600000", "Yellow"))
        self.assertEqual((row[27], row[39], row[46]), ("0", "(None)", "0"))     # 常驻
        self.assertEqual((row[47], row[48], row[49]), ("53", "5", "Yellow"))    # 全队(雷)
        self.assertEqual(row[51:53], ["20000", "20000"])
        self.assertEqual(row[70], "")                                           # 无面板覆盖键
        self.assertEqual(wf_describe.describe_rows([row], "ability")[0],
                         "雷·编成≥6 时: 赋予全队(雷) 眩晕畏缩特攻 20%")

    def test_new_record_shares_the_skill_flag_resonance_gate(self):
        flag = self.rows[1]
        self.assertEqual([flag[c] for c in (6, 9, 10, 11)], [self.rows[2][c] for c in (6, 9, 10, 11)])

    def test_new_record_is_the_official_donor_plus_cells(self):
        donor = DATA["official"]["ability"]["1310014"][0]
        self.assertEqual(M.DONOR_ROW, donor)
        changed = {i for i, (a, b) in enumerate(zip(donor, self.rows[2])) if a != b}
        self.assertEqual(changed, {0, 6, 9, 10, 11, 51, 52})

    def test_new_record_passes_every_gate(self):
        row = self.rows[2]
        self.assertEqual(L.client_legality_problems("ability", row), [])
        self.assertEqual(L.declared_block_field_problems("ability", row), [])
        self.assertEqual(L.ability_element_column_problems("ability", row, M.ELEMENT), [])
        self.assertEqual(L.invoke_skill_string_problems(row, {M.CAS_KEY}), [])
        self.assertEqual(L.required_client_capabilities("ability", row), [])
        self.assertEqual(M.row_gate_problems(row), [])
        KL.check_ability_key(self.rows, "1399921", M.CODE, 1)


class TextTests(unittest.TestCase):
    def setUp(self):
        self.values = live_values()
        self.out = revised()

    def test_skill_flag_string_drops_down(self):
        text = self.out["cas"][M.CAS_KEY]
        self.assertEqual(text, [["雷属性共鸣时强化技能：命中敌人时赋予其累积全属性抗性降低与累积攻击力降低效果"
                                 "（无视弱体抗性），并随机追加赋予麻痹、中毒、迟缓中的两种效果"]])
        self.assertNotIn("DOWN", text[0][0])
        self.assertEqual(KL.panel_problems(text[0][0], skill_flag=True), [])

    def test_new_description_inserts_the_self_barrier_after_the_ally_barrier(self):
        self.assertEqual(M.NEW_DESC,
                         "抽取全体队伍成员生命值55%（若该成员当前生命值低于50%，则改为抽取其生命值20%），"
                         "并为除自身外的雷属性角色赋予护盾，护盾值为其最大生命值25%，"
                         "同时为自身赋予护盾，护盾值为自身最大生命值10% ＋ "
                         "瞄准敌人射出月华贯穿弹，命中后爆炸，对范围内的敌人造成雷属性伤害")
        self.assertEqual(KL.panel_problems(M.NEW_DESC), [])

    def test_character_text_only_touches_c5_and_c7(self):
        before = self.values["text", "139992"][0]
        after = self.out["text"]["139992"][0]
        self.assertEqual({i for i, (a, b) in enumerate(zip(before, after)) if a != b}, {5, 7})
        self.assertEqual((after[5], after[7]), (M.NEW_DESC, M.NEW_DESC))

    def test_server_mirror_only_touches_5_and_7(self):
        before = self.values["server_text", "139992"][0]
        after = self.out["server_text"]["139992"][0]
        self.assertEqual({i for i, (a, b) in enumerate(zip(before, after)) if a != b}, {5, 7})
        self.assertEqual(after, self.out["text"]["139992"][0])

    def test_action_skill_only_touches_c1_on_both_tiers(self):
        before = self.values["action", M.CODE]
        after = self.out["action"][M.CODE]
        self.assertEqual([inner for inner, _f in after], ["1", "2"])
        for (inner, old), (_inner, new) in zip(before, after):
            self.assertIsInstance(new, list)
            self.assertEqual({i for i, (a, b) in enumerate(zip(old, new)) if a != b}, {1}, inner)
            self.assertEqual(new[1], M.NEW_DESC)
            self.assertEqual(new[7], M.PROGRAMS[inner])
        # 编码器吃得下（stage 用 core.encode_action_skill_row 回写）
        self.assertEqual(core.decode_action_skill_row(core.encode_action_skill_row(after)), after)


class SkillTreeTests(unittest.TestCase):
    def setUp(self):
        self.values = live_values()
        self.out = revised()

    def test_self_barrier_follows_the_ally_barrier(self):
        for level, program in M.PROGRAMS.items():
            top = self.out["dsl"][program][11][1]
            self.assertEqual([c[1][0] for c in top],
                             ["FindAllSubjects", "FindAllSubjects", "CreateBarrier", "FindNearSubjects"])
            self.assertEqual(top[1], M.ALLY_BARRIER, level)
            self.assertEqual(top[2], ["Command", ["CreateBarrier", -17, [{"min": 0.1, "max": 0.1}],
                                                  ["GenericBarrierHitEffect"]]], level)

    def test_roulettes_lose_only_the_stun_branch(self):
        for level, program in M.PROGRAMS.items():
            tree = self.out["dsl"][program]
            self.assertNotIn("ACStun", json.dumps(tree))
            roulettes = _roulettes(tree)
            self.assertEqual(len(roulettes), 2, level)
            for branches in roulettes:
                self.assertEqual([_branch_ac(b) for b in branches], ["ACParalysis", "ACPoison", "ACFrozen"])
                for branch in branches:
                    self.assertEqual(branch[0], "Block")
                    self.assertEqual(len(branch[1]), 2)          # [ProbabilityWeight, Block]，否则 INTERNAL ERROR
                    self.assertEqual(branch[1][0], ["Command", ["ProbabilityWeight", 25]])

    def test_nothing_else_changes(self):
        """撤销两处改动后必须逐字回到 live 输入。"""
        for level, program in M.PROGRAMS.items():
            before = self.values["dsl", program]
            undo = copy.deepcopy(self.out["dsl"][program])
            self.assertEqual(undo[11][1].pop(2), M.SELF_BARRIER)
            for new, old in zip(_roulettes(undo), _roulettes(before)):
                self.assertEqual(_branch_ac(old[3]), "ACStun")
                new.append(copy.deepcopy(old[3]))
            self.assertEqual(undo, before, level)

    def test_command_counts(self):
        for program in M.PROGRAMS.values():
            counts = M.command_counts(self.out["dsl"][program])
            self.assertEqual(counts, M.COUNTS_AFTER)
            self.assertEqual((counts["CreateBarrier"], counts["CreateCondition"], counts["ProbabilityWeight"]),
                             (2, 8, 6))

    def test_trees_pass_the_dsl_gates_and_roundtrip(self):
        for level, program in M.PROGRAMS.items():
            tree = self.out["dsl"][program]
            self.assertEqual(M.dsl_gate_problems(tree), [], level)
            self.assertEqual(L.action_dsl_element_problems(tree, M.ELEMENT), [], level)
            self.assertEqual(L.action_dsl_subject_binding_problems(tree), [], level)
            self.assertEqual(L.action_dsl_lookup_scope_problems(tree), [], level)
            self.assertEqual(L.action_dsl_hit_area_target_problems(tree), [], level)
            self.assertEqual(dsl_problems(tree, element=M.ELEMENT), [], level)
            encode_tree(tree)                                    # AMF3 往返不一致会抛

    def test_structure_guard_rejects_a_tree_without_the_stun_branch(self):
        tree = copy.deepcopy(self.values["dsl", M.PROGRAMS["1"]])
        for branches in _roulettes(tree):
            branches.pop()
        with self.assertRaises(M.CharleneBalanceError):
            M.revise_tree(tree, "1")


class GuardTests(unittest.TestCase):
    def test_drift_on_any_input_is_rejected(self):
        for kind, key in M.BEFORE:
            values = copy.deepcopy(live_values())
            value = values[kind, key]
            if kind == "dsl":
                value[11][1].append(["Command", ["ShakeCamera", 1]])
            elif kind == "action":
                value[0][1][0] += "x"
            else:
                value[0][0] += "x"
            with self.assertRaises(M.CharleneBalanceError, msg=f"{kind}:{key}"):
                revised(values)

    def test_inputs_are_not_mutated(self):
        values = live_values()
        snapshot = copy.deepcopy(values)
        revised(values)
        self.assertEqual(values, snapshot)

    def test_revision_cannot_be_applied_twice(self):
        out = revised()
        values = live_values()
        values["ability", "1399921"] = out["ability"]["1399921"]
        with self.assertRaises(M.CharleneBalanceError):
            revised(values)

    def test_revise_is_deterministic(self):
        self.assertEqual(revised(), revised())


class GeneratorConsistencyTests(unittest.TestCase):
    """生成器（kit）输出 == revise() 输出：重跑 kit 不会回退本次改动。"""

    def setUp(self):
        self.out = revised()

    def test_generator_trees_equal_the_revised_trees(self):
        for level, program in M.PROGRAMS.items():
            donor_program = program.replace(KIT.CODE, KIT.TEMPLATE_CODE)
            tree, ev = KIT.mutate_tree(copy.deepcopy(DATA["official"]["dsl"][donor_program]), level)
            self.assertEqual(tree, self.out["dsl"][program], level)
            self.assertEqual(ev["self_barrier"], {"subject": -17, "ratio": 0.1})

    def test_generator_ability_rows_equal_the_revised_rows(self):
        built = []
        for donor, cells, expect in KIT.ABILITY["1399921"]:
            key, _, index = donor.partition("#")
            row = KL.apply_cells(DATA["official"]["ability"][key][int(index)], cells, KL.ABILITY_NCOLS)
            self.assertEqual(KL.describe("ability", row), expect)
            self.assertEqual(KL.row_problems("ability", row, KIT.ELEMENT), {})
            built.append(row)
        self.assertEqual(built, self.out["ability"]["1399921"])
        self.assertEqual(KIT.ABILITY["1399921"][2][0], M.DONOR)
        self.assertEqual(KIT.ABILITY["1399921"][2][2], M.STUN_WINCE_DESCRIBE)

    def test_generator_texts_equal_the_revised_texts(self):
        # 第三轮（wf_balance_20260927c_panels FLAG_TEXT，主会话 R2）在本批输出上再改写强化条目：生成器 == 该改写稿，
        # 其改前 == 本批输出（链式一致）。
        import wf_balance_20260927c_panels as P3
        spec = P3.FLAG_TEXT[M.CID]
        self.assertEqual((spec["string"], spec["before"]), (M.CAS_KEY, self.out["cas"][M.CAS_KEY][0][0]))
        self.assertEqual(KIT.CAS_TEXTS[KIT.CAS_SWITCH], spec["after"])
        text = self.out["text"]["139992"][0]
        self.assertEqual((KIT.TEXTS["desc1"], KIT.TEXTS["desc2"]), (text[5], text[7]))
        self.assertEqual((KIT.TEXTS["skill1"], KIT.TEXTS["skill2"]), (text[4], text[6]))
        for inner, fields in self.out["action"][M.CODE]:
            self.assertEqual((fields[0], fields[1]), (KIT.TEXTS[f"skill{inner}"], KIT.TEXTS[f"desc{inner}"]))
            self.assertEqual((fields[4], fields[5]), KIT.SKILL_ENERGY[inner])

    def test_generator_constants_agree(self):
        self.assertEqual([ac[0] for _n, ac, _f, _w in KIT.ROULETTE], list(M.ROULETTE_KEPT))
        self.assertEqual({w for _n, _a, _f, w in KIT.ROULETTE}, {M.ROULETTE_WEIGHT})
        self.assertEqual((KIT.SELF_BARRIER_SUBJECT, KIT.SELF_BARRIER_RATIO),
                         (M.SELF_SUBJECT, M.SELF_BARRIER_RATIO))
        self.assertEqual(KIT.self_barrier_block(), M.SELF_BARRIER)
        self.assertEqual(KIT.PRE_RESONANCE, M.PRE_RESONANCE)
        self.assertEqual(tuple(KIT.SPEC["required_capabilities"]), tuple(M.CAPABILITIES))


def _mirror(rel: str):
    path = core.project_root() / rel
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def _pre_batch_design(design: dict) -> dict:
    """把当前设计稿退回本批之前的形状（只退本批动过的格）。"""
    pre = copy.deepcopy(design)
    pre["texts"]["desc1"] = pre["texts"]["desc2"] = M.OLD_DESC
    desc = pre["plan"]["texts"]["action_skill_desc"]
    desc["desc1"] = desc["desc2"] = M.OLD_DESC
    for row in pre["plan"]["texts"]["custom_ability_string"]["rows"]:
        if row["key"] == M.CAS_KEY:
            row["text"] = M.OLD_CAS_TEXT
    entry = pre["plan"]["ability"]["keys"][M.ABILITY_KEY]
    entry["role"] = M.DESIGN_ROLE_OLD
    entry["records"].pop()
    entry["unisonable_per_record"] = ["true", "true"]
    entry["record_count"] = {"old": 2, "new": 2}
    for item in pre["plan"]["skills"]["edits_rework1"]:
        if item.get("id") == "R3":
            item["shape"] = item["shape"].replace(M.R3_SHAPE_NEW, M.R3_SHAPE_OLD)
    pre["deviations"] = [item for item in pre["deviations"] if item.get("id") != "D18"]
    for item in pre["deviations"]:
        item.pop("superseded_by", None)
    for item in pre["engine_findings"]:
        if item.get("id") == "E5":
            item["claim"] = M.ROW_COUNT_E5_CLAIM[0]
            item["evidence"].remove(M.ROW_COUNT_E5_EVIDENCE)
    pre["plan"]["texts"]["desc_override"]["why"] = M.ROW_COUNT_OVERRIDE_WHY[0]
    pre["canary"] = [M.ROW_COUNT_CANARY_C2[0] if item == M.ROW_COUNT_CANARY_C2[1] else item
                     for item in pre["canary"] if item != M.CANARY_C10]
    pre["evidence_files"] = [M.ROW_COUNT_EVIDENCE_FILE[0] if item == M.ROW_COUNT_EVIDENCE_FILE[1] else item
                             for item in pre["evidence_files"]]
    pre.pop("balance_20260927")
    return pre


def _this_batch_cas(doc: dict) -> dict:
    """第三轮（wf_balance_20260927c_panels FLAG_TEXT，主会话 R2）同步镜像后，强化条目是改写稿；本批的变换把改前
    收敛到本批文字、改写稿原样保留 ⇒ 从改前收敛的期望 = 当前镜像里改写稿换回本批文字。"""
    out = copy.deepcopy(doc)
    later = M.later_cas_text()

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "text" and value == later:
                    node[key] = M.NEW_CAS_TEXT
                else:
                    walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(out)
    return out


def _pre_batch_panel(panel: dict) -> dict:
    pre = copy.deepcopy(panel)
    pre["skill"]["lines"][0]["text"] = M.PANEL_SKILL_OLD
    lines = [a for a in pre["abilities"] if a["index"] == 1][0]["lines"]
    lines[1]["text"] = M.OLD_CAS_TEXT
    lines[1]["dev_why"] = lines[1]["dev_why"].replace(M.PANEL_DEV_WHY_NEW, M.PANEL_DEV_WHY_OLD)
    lines.pop()
    pre["notes"].remove(M.PANEL_NOTE)
    for item in pre["deviations"]:
        if item["原话"].startswith(M.STUN_DEVIATION_KEY):
            item["落法"] = "作者已定（09-21）：「气绝」这一格换成「使敌人更容易进入 DOWN」（ACStun＝Stunify 眩晕蓄积）。"
    return pre


class MirrorTests(unittest.TestCase):
    """设计镜像（work/ 下，gitignore）：kit 的 design_crosscheck 逐字比对，必须与本批同步。"""

    def _require(self, rel):
        value = _mirror(rel)
        if value is None:
            self.skipTest(f"{rel} 不在（work/ 未恢复）")
        return value

    def test_mirrors_are_in_sync(self):
        self._require(M.DESIGN_REL)
        self.assertEqual(M.sync_mirrors(core.project_root(), write=False), [])

    def test_design_update_converges_and_is_idempotent(self):
        design = self._require(M.DESIGN_REL)
        self.assertEqual(M.design_update(_pre_batch_design(design)), _this_batch_cas(design))
        self.assertEqual(M.design_update(design), design)
        self.assertEqual((design["texts"]["desc1"], design["texts"]["desc2"]), (M.NEW_DESC, M.NEW_DESC))
        records = design["plan"]["ability"]["keys"][M.ABILITY_KEY]["records"]
        self.assertEqual([r["desc_expected"] for r in records],
                         [expect for _d, _c, expect in KIT.ABILITY[M.ABILITY_KEY]])
        self.assertEqual(records[2]["cells"], {str(i): v for i, v in enumerate(M.stun_wince_row()) if v})

    def test_design_row_count_is_12_and_canary_names_the_new_row(self):
        design = self._require(M.DESIGN_REL)
        total = sum(len(entry["records"]) for entry in design["plan"]["ability"]["keys"].values())
        self.assertEqual(total, 12)
        self.assertNotIn("11 条行", json.dumps(design, ensure_ascii=False))
        c2 = [item for item in design["canary"] if item.startswith("C2 ")]
        self.assertEqual(c2, [M.ROW_COUNT_CANARY_C2[1]])
        self.assertIn("12 条行", c2[0])
        self.assertIn("1399921#2", c2[0])
        self.assertIn("（独立乘区）", c2[0])
        self.assertEqual(design["canary"].count(M.CANARY_C10), 1)
        e5 = [item for item in design["engine_findings"] if item.get("id") == "E5"][0]
        self.assertIn("12 条行", e5["claim"])
        self.assertIn(M.ROW_COUNT_E5_EVIDENCE, e5["evidence"])
        self.assertIn("12 条行", design["plan"]["texts"]["desc_override"]["why"])

    def test_design_update_rejects_drifted_row_count_fields(self):
        design = self._require(M.DESIGN_REL)
        for mutate in (lambda d: d["canary"].append("C10 别的验收项"),
                       lambda d: d["plan"]["texts"]["desc_override"].__setitem__("why", "别的理由"),
                       lambda d: [e for e in d["engine_findings"] if e.get("id") == "E5"][0]
                       .__setitem__("claim", "别的结论")):
            broken = copy.deepcopy(design)
            mutate(broken)
            with self.assertRaises(M.CharleneBalanceError):
                M.design_update(broken)

    def test_panel_update_converges_and_is_idempotent(self):
        panel = self._require(M.PANEL_REL)
        self.assertEqual(M.panel_update(_pre_batch_panel(panel)), _this_batch_cas(panel))
        self.assertEqual(M.panel_update(panel), panel)
        lines = [a for a in panel["abilities"] if a["index"] == 1][0]["lines"]
        self.assertNotIn("DOWN", lines[1]["text"])
        self.assertEqual(KL.panel_problems(lines[2]["text"]), [])

    def test_deviations_update_touches_only_charlene(self):
        deviations = self._require(M.DEVIATIONS_REL)
        pre = copy.deepcopy(deviations)
        pre["charlene"][0]["落法"] = "作者已定（09-21）：「气绝」这一格换成「使敌人更容易进入 DOWN」。"
        after = M.deviations_update(pre)
        self.assertEqual(after, deviations)
        self.assertEqual({k: v for k, v in after.items() if k != "charlene"},
                         {k: v for k, v in pre.items() if k != "charlene"})

    def test_unknown_state_is_rejected(self):
        design = self._require(M.DESIGN_REL)
        broken = copy.deepcopy(design)
        broken["texts"]["desc1"] = "别的文案"
        with self.assertRaises(M.CharleneBalanceError):
            M.design_update(broken)


def _live_baseline_available() -> bool:
    profile = core.resolve_profile()
    return (profile is not None and profile.store.is_dir()
            and (core.project_root() / ".cdn" / "cn").is_dir())


@unittest.skipUnless(_live_baseline_available(), "需要 live store 与 .cdn/cn 官方基线")
class OfficialBaselineTests(unittest.TestCase):
    """fixture 里的官方 donor 必须与 .cdn/cn 官方基线逐字一致（官方基线不随本批发布变化）。"""

    @classmethod
    def setUpClass(cls):
        import wf_midautumn_common as MC
        import wf_midautumn_specs as MS
        import wf_seasonal7_build as B
        cls.ctx = B.KitContext(MC.MAPack(MS.get_spec(KIT.KEY), record_sources=False))

    def test_fixture_donor_trees_are_official(self):
        for program, tree in DATA["official"]["dsl"].items():
            self.assertEqual(self.ctx.template_dsl(program), tree, program)

    def test_fixture_donor_rows_are_official(self):
        for key, rows in DATA["official"]["ability"].items():
            self.assertEqual(self.ctx.official_rows("ability", key), rows, key)

    def test_kit_row_builder_agrees(self):
        built = [KL.build_row(self.ctx, "ability", donor, cells, element=KIT.ELEMENT,
                              expect_describe=expect)[0]
                 for donor, cells, expect in KIT.ABILITY["1399921"]]
        self.assertEqual(built, revised()["ability"]["1399921"])


if __name__ == "__main__":
    unittest.main()
