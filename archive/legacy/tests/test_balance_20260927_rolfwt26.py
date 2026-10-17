# -*- coding: utf-8 -*-
"""2026-09-27 平衡批次：冰雪罗尔夫 179999 修订模块 ``wf_balance_20260927_rolfwt26`` 的单测。

fixture（``fixtures/balance_20260927_rolfwt26.json``）存 revise() 的 live 输入快照与官方先例片段，
所以绝大多数用例离线可跑；只有「fixture 里的官方先例与 .cdn/cn 官方基线逐字一致」需要本机环境。
不写 live store / assets / .cdn / 候选包，不发布。
"""
from __future__ import annotations

import copy
import json
import sys
import unittest
import zlib
from pathlib import Path

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_balance_20260927_rolfwt26 as M  # noqa: E402
import wf_client_legality as L  # noqa: E402
import wf_describe  # noqa: E402
import wf_dsl  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_mod_tool as core  # noqa: E402
import wf_seasonal7_kit_philia as PH  # noqa: E402
from wf_character_revision import encode_tree  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "balance_20260927_rolfwt26.json"
DATA = json.loads(FIXTURE.read_text(encoding="utf-8"))
PRE_REVISION_VERSION = (0, 1, 1)      # black_wolf_knight_wt26 候选在本批之前的 package_version


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


def executed(node, *, fever: bool, flag: bool, out: list | None = None) -> list[list]:
    """按 Fever / 技能旗号 1 的真假走一遍树，返回会执行的命令参数数组（分支只进被选中的一支）。"""
    out = [] if out is None else out
    if isinstance(node, list) and node and node[0] == "Block":
        for child in node[1]:
            executed(child, fever=fever, flag=flag, out=out)
    elif isinstance(node, list) and node and node[0] == "Command":
        args = node[1]
        if args[0] == "ConditionalsFeverMode":
            executed(args[1] if fever else args[2], fever=fever, flag=flag, out=out)
        elif args[0] == "ConditionalsChangeSkillFlag":
            if args[1] != M.SKILL_FLAG:
                raise AssertionError(f"unexpected skill flag {args[1]}")
            executed(args[2] if flag else args[3], fever=fever, flag=flag, out=out)
        else:
            out.append(args)
            for child in args[1:]:
                if isinstance(child, list) and child and child[0] in ("Block", "Command"):
                    executed(child, fever=fever, flag=flag, out=out)
    elif isinstance(node, list) and node and node[0] == "ActionDsl":
        executed(node[11], fever=fever, flag=flag, out=out)
    return out


def _ac_names(commands) -> list[str]:
    return [ac[0] for args in commands if args[0] == "CreateCondition" for ac in args[2]]


def _regen_values(commands) -> list[tuple]:
    return [(ac[1][0]["min"], ac[2][0]["min"]) for args in commands if args[0] == "CreateCondition"
            for ac in args[2] if ac[0] == "ACRegeneration"]


def _names(commands) -> set[str]:
    return {args[0] for args in commands}


class ContractTests(unittest.TestCase):
    def test_exports(self):
        self.assertEqual((M.CID, M.CODE), ("179999", "black_wolf_knight_wt26"))
        self.assertEqual(M.PACKAGES, ["black_wolf_knight_wt26"])
        self.assertEqual(M.CAPABILITIES, [])
        self.assertEqual(set(M.PACKAGE_VERSION), set(M.PACKAGES))
        self.assertEqual(set(M.BEFORE), {("ability", "1799993"), ("cas", "superfever_desc_wt26"),
                                         ("text", "179999"), ("action", M.CODE),
                                         ("dsl", M.PROGRAMS["1"]), ("dsl", M.PROGRAMS["2"]),
                                         ("server_text", "179999")})
        for sha in M.BEFORE.values():
            self.assertRegex(sha, r"^[0-9a-f]{64}$")

    def test_package_version_moves_forward(self):
        version = tuple(int(x) for x in M.PACKAGE_VERSION["black_wolf_knight_wt26"].split("."))
        self.assertGreater(version, PRE_REVISION_VERSION)
        manifest = core.project_root() / "work/character_packs/black_wolf_knight_wt26/package/manifest.json"
        if manifest.is_file():
            data = json.loads(manifest.read_text(encoding="utf-8"))
            current = data["package_version"]
            # 第三轮（wf_balance_20260927c_panels，技能强化条目规范）暂存回写后候选再升一版，上限取那一版。
            import wf_balance_20260927c_panels as P3
            ceiling = P3.staged_version(data, "black_wolf_knight_wt26")
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
        self.assertEqual(list(out["ability"]), ["1799993"])
        self.assertEqual(out["leader"], {})
        self.assertEqual(out["table"], {})
        self.assertEqual(list(out["cas"]), ["change_skill_black_wolf_knight_wt26"])
        self.assertEqual(list(out["text"]), ["179999"])
        self.assertEqual(list(out["action"]), [M.CODE])
        self.assertEqual(sorted(out["dsl"]), sorted(M.PROGRAMS.values()))
        self.assertEqual(list(out["server_text"]), ["179999"])
        json.dumps(out["notes"], ensure_ascii=False)

    def test_both_skill_trees_are_new_programs_for_the_candidate(self):
        """候选 manifest skills={} 不含两档技能树 ⇒ 两棵都作为新程序交给暂存脚本。"""
        out = revised()
        self.assertEqual(out["new_programs"], [M.PROGRAMS["1"], M.PROGRAMS["2"]])
        self.assertEqual(set(out["new_programs"]), set(out["dsl"]))

    def test_stale_candidate_server_mirror_is_declared(self):
        """候选服务端镜像 179999 行是换皮前旧文；暂存整行替换会顺带收敛 [5]/[7] 以外 9 列，必须记进 open_points。"""
        stale = M.CANDIDATE_STALE_SERVER_MIRROR
        self.assertEqual((stale["file"], stale["key"]), ("cdndata/character_text.json", M.CID))
        self.assertEqual(set(stale["differing_columns"]), set(range(1, 12)))
        self.assertEqual(set(stale["overwritten_beyond_revision"]),
                         set(stale["differing_columns"]) - set(M.TEXT_DESC_COLUMNS))
        self.assertEqual({int(c) for c in stale["cells"]}, set(stale["differing_columns"]))
        # 记录的 live 侧必须与本批审过的 live 服务端行一致（长文列只记开头）。
        live_row = live_values()["server_text", M.CID][0]
        for col, (candidate_value, live_value) in stale["cells"].items():
            self.assertNotEqual(candidate_value, live_value, col)
            if live_value.endswith("…"):
                self.assertTrue(live_row[int(col)].startswith(live_value[:-1]), col)
            else:
                self.assertEqual(live_row[int(col)], live_value, col)
        notes = revised()["notes"]
        mirror = notes["candidate_preexisting_drift"]["server_mirror"]
        self.assertEqual(mirror["overwritten_beyond_revision"], list(stale["overwritten_beyond_revision"]))
        self.assertEqual(notes["candidate_preexisting_drift"]["ability"], M.CANDIDATE_PREEXISTING_DRIFT)
        entries = [p for p in notes["open_points"] if "roots/server/cdndata/character_text.json" in p]
        self.assertEqual(len(entries), 1)
        self.assertIn(",".join(str(c) for c in stale["overwritten_beyond_revision"]), entries[0])
        self.assertIn("整行替换", entries[0])

    def test_every_written_key_is_in_the_character_namespace(self):
        out = revised()
        for section in ("ability", "cas", "text", "server_text"):
            for key in out[section]:
                self.assertTrue(key.startswith((M.CID, M.CODE, "change_skill_" + M.CODE)), key)
        self.assertNotIn("superfever_desc_wt26", out["cas"])      # 旧键不在命名空间，不写
        for program in out["dsl"]:
            self.assertIn(f"/{M.CODE}${M.CODE}_", program)


class SkillTreeTests(unittest.TestCase):
    def setUp(self):
        self.values = live_values()
        self.out = revised()

    def test_live_tiers_are_identical_and_stay_identical(self):
        self.assertEqual(self.values["dsl", M.PROGRAMS["1"]], self.values["dsl", M.PROGRAMS["2"]])
        self.assertEqual(self.out["dsl"][M.PROGRAMS["1"]], self.out["dsl"][M.PROGRAMS["2"]])

    def test_fever_branch_is_wrapped_by_skill_flag_1(self):
        for level, program in M.PROGRAMS.items():
            fever = M.fever_node(self.out["dsl"][program])
            self.assertEqual(fever[0], "ConditionalsFeverMode")
            self.assertEqual(fever[2], ["Block", []], level)              # 非 Fever 分支仍为空
            then = fever[1][1]
            self.assertEqual(len(then), 1, level)
            flag = then[0][1]
            self.assertEqual(flag[0], "ConditionalsChangeSkillFlag")
            self.assertEqual(len(flag), 4)                                 # [名, 旗号, then, else]
            self.assertEqual(flag[1], 1)
            self.assertEqual(flag[3], ["Block", []])                       # else 空 Block，不是 DoNothing
            self.assertEqual(flag[2][0], "Block")
            self.assertEqual([c[1][0] for c in flag[2][1]],
                             ["AddFeverPoint", "FindAllSubjects", "ChangeFieldAssets", "FindAllSubjects"])

    def test_the_whole_super_fever_moves_under_the_flag_verbatim(self):
        for level, program in M.PROGRAMS.items():
            before = M.fever_node(self.values["dsl", program])[1][1]
            gated = M.fever_node(self.out["dsl"][program])[1][1][0][1][2][1]
            self.assertEqual(gated[:3], before, level)
            self.assertEqual(gated[3], M.TEAM_RECOVERY, level)

    def test_flag_false_in_fever_has_no_super_fever_and_no_recovery(self):
        tree = self.out["dsl"][M.PROGRAMS["1"]]
        run = executed(tree, fever=True, flag=False)
        names = _names(run)
        for absent in ("AddFeverPoint", "ChangeFieldAssets", "CreateRatioHeal"):
            self.assertNotIn(absent, names)
        self.assertNotIn("ACAttackPoint", _ac_names(run))
        self.assertNotIn("ACAbilityDamage", _ac_names(run))
        self.assertEqual(_regen_values(run), [(600.0, 100.0)])           # 只剩顶层体力最低者的再生
        # 非 Fever 部分照旧：护盾、再生、火风技伤/PF、贯通
        base = executed(self.values["dsl", M.PROGRAMS["1"]], fever=False, flag=False)
        self.assertEqual(run, base)

    def test_flag_true_outside_fever_changes_nothing(self):
        before = executed(self.values["dsl", M.PROGRAMS["1"]], fever=False, flag=True)
        after = executed(self.out["dsl"][M.PROGRAMS["1"]], fever=False, flag=True)
        self.assertEqual(after, before)
        self.assertNotIn("CreateRatioHeal", _names(after))

    def test_flag_true_in_fever_runs_super_fever_plus_recovery(self):
        before = executed(self.values["dsl", M.PROGRAMS["1"]], fever=True, flag=True)
        after = executed(self.out["dsl"][M.PROGRAMS["1"]], fever=True, flag=True)
        self.assertEqual(after[:len(before)], before)                     # 原超级Fever 全部照旧执行
        extra = after[len(before):]
        self.assertEqual([a[0] for a in extra], ["FindAllSubjects", "CreateRatioHeal", "CreateCondition"])
        self.assertEqual(_regen_values(after), [(600.0, 100.0), (600, 53)])
        self.assertIn("AddFeverPoint", _names(after))
        self.assertIn("ChangeFieldAssets", _names(after))

    def test_live_tree_never_read_the_flag(self):
        """修订前：Fever 中施放与旗号无关（DSL 没读 536 打开的旗号 1）。"""
        tree = self.values["dsl", M.PROGRAMS["1"]]
        self.assertEqual(executed(tree, fever=True, flag=False), executed(tree, fever=True, flag=True))
        self.assertNotIn("ConditionalsChangeSkillFlag", M.command_counts(tree))

    def test_ratio_heal_is_5_percent_of_max_hp_on_the_whole_team(self):
        for level, program in M.PROGRAMS.items():
            heals = list(wf_dsl.iter_dsl_commands(self.out["dsl"][program], "CreateRatioHeal"))
            self.assertEqual(len(heals), 1, level)
            heal = heals[0]
            self.assertEqual(heal, ["CreateRatioHeal", 0, 2, [{"min": 0.05, "max": 0.05}], [],
                                    [{"min": 0, "max": 0}], ["GenericHealHitEffect"]])
            self.assertEqual(heal[2], 2)          # RatioHealKind.UseHealeesMaximumHealthPoint（1 = 当前生命值）
            finder = M.TEAM_RECOVERY[1]
            self.assertEqual(finder[:3], ["FindAllSubjects", 0, 33])       # 技能现有的全队写法
            self.assertEqual(finder[1], heal[1])                           # 查找结果绑定 = 受疗者

    def test_regeneration_is_600_frames_53_per_tick(self):
        for level, program in M.PROGRAMS.items():
            tree = self.out["dsl"][program]
            regens = [args for args in wf_dsl.iter_dsl_commands(tree, "CreateCondition")
                      if args[2][0][0] == "ACRegeneration"]
            self.assertEqual(len(regens), 2, level)
            old, new = regens
            self.assertEqual(old[2][0], ["ACRegeneration", [{"min": 600.0, "max": 600.0}],
                                         [{"min": 100.0, "max": 100.0}]])   # 顶层体力最低者，不动
            self.assertEqual(new, M.REGENERATION[1])
            self.assertEqual(new[2], [["ACRegeneration", [{"min": 600, "max": 600}], [{"min": 53, "max": 53}]]])
            self.assertEqual(new[1], 0)
            self.assertEqual(new[10], 3)          # 付与对象种类：选择器 33 = Member ⇒ 3
            # 每 120 帧一跳、首跳第 30 帧 ⇒ 600 帧内 5 跳，合计 265 ≈ Lv100 生命 3295 的 8%
            ticks = [f for f in range(30, 600, 120)]
            self.assertEqual(len(ticks) * M.REGEN_PER_TICK, 265)
            self.assertAlmostEqual(265 / 3295, 0.08, places=2)

    def test_nothing_else_changes(self):
        """撤销改动后必须逐字回到 live 输入。"""
        for level, program in M.PROGRAMS.items():
            before = self.values["dsl", program]
            undo = copy.deepcopy(self.out["dsl"][program])
            fever = M.fever_node(undo)
            fever[1] = ["Block", fever[1][1][0][1][2][1][:3]]
            self.assertEqual(undo, before, level)

    def test_command_counts(self):
        for program in M.PROGRAMS.values():
            self.assertEqual(M.command_counts(self.values["dsl", program]), M.COUNTS_BEFORE)
            self.assertEqual(M.command_counts(self.out["dsl"][program]), M.COUNTS_AFTER)

    def test_trees_pass_the_dsl_gates_and_roundtrip(self):
        for level, program in M.PROGRAMS.items():
            tree = self.out["dsl"][program]
            self.assertEqual(M.dsl_gate_problems(tree), [], level)
            self.assertEqual(L.action_dsl_element_problems(tree, M.ELEMENT), [], level)
            self.assertEqual(L.action_dsl_subject_binding_problems(tree), [], level)
            self.assertEqual(L.action_dsl_lookup_scope_problems(tree), [], level)
            self.assertEqual(L.action_dsl_hit_area_target_problems(tree), [], level)
            self.assertEqual(PH.signature_problems(tree), [], level)      # 参数个数 = 官方签名
            self.assertEqual(PH.expr_tag_problems(tree), [], level)       # 表达式外壳
            self.assertEqual(PH.scope_problems(tree), [], level)
            raw = encode_tree(tree)                                      # AMF3 往返不一致会抛
            self.assertEqual(wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"], tree)

    def test_structure_guard_rejects_an_already_gated_tree(self):
        with self.assertRaises(M.RolfWt26BalanceError):
            M.revise_tree(self.out["dsl"][M.PROGRAMS["1"]], "1")

    def test_structure_guard_rejects_a_changed_super_fever(self):
        tree = copy.deepcopy(self.values["dsl", M.PROGRAMS["1"]])
        M.fever_node(tree)[1][1][0][1][1][0]["min"] = 100.0             # AddFeverPoint 200 → 100
        with self.assertRaises(M.RolfWt26BalanceError):
            M.revise_tree(tree, "1")

    def test_new_nodes_follow_the_official_precedents(self):
        official = DATA["official"]
        heal = official["team_heal_and_regen"]["ratio_heal"]
        regen = official["team_heal_and_regen"]["regeneration"]
        no_slayer = official["ratio_heal_without_slayer"]["ratio_heal"]
        ours_heal, ours_regen = M.RATIO_HEAL[1], M.REGENERATION[1]
        # asahina_mikuru_1：FindAllSubjects(0,33) 块内 CreateRatioHeal(0,2,…) + CreateCondition(0, ACRegeneration)
        self.assertEqual((heal[0], heal[1], heal[2]), (ours_heal[0], ours_heal[1], ours_heal[2]))
        self.assertEqual(len(heal), len(ours_heal))
        self.assertEqual(regen[0:2], ours_regen[0:2])
        self.assertEqual(regen[3:], ours_regen[3:])                      # 命中率/演出/旗标/付与对象种类逐字同
        self.assertEqual([ac[0] for ac in regen[2]], ["ACRegeneration"])
        self.assertEqual(len(regen[2][0]), len(ours_regen[2][0]))
        # alk_1anv_1：无特攻写法
        self.assertEqual(no_slayer[2:3] + no_slayer[4:], ours_heal[2:3] + ours_heal[4:])


class AbilityTests(unittest.TestCase):
    def setUp(self):
        self.before = live_values()["ability", "1799993"]
        self.rows = revised()["ability"]["1799993"]

    def test_only_the_536_row_string_id_changes(self):
        self.assertEqual(len(self.rows), 5)
        self.assertEqual(self.rows[:4], self.before[:4])
        changed = {i for i, (a, b) in enumerate(zip(self.before[4], self.rows[4])) if a != b}
        self.assertEqual(changed, {70})
        self.assertEqual((self.before[4][70], self.rows[4][70]),
                         ("superfever_desc_wt26", "change_skill_black_wolf_knight_wt26"))

    def test_the_flag_row_keeps_its_main_slot_and_fire_resonance_gate(self):
        row = self.rows[4]
        self.assertEqual(row[47], "536")                                  # ChangeSkillFlag ⇒ 旗号 1
        self.assertEqual(row[6], "202")                                   # 持有者为主位
        self.assertEqual((row[13], row[16], row[17], row[18]), ("2", "600000", "600000", "Red"))
        self.assertEqual(wf_describe.describe_rows([row], "ability")[0],
                         "持有者为主位 且 火·编成≥6 时: 自身 切换技能形态[change_skill_black_wolf_knight_wt26]")

    def test_changed_row_passes_every_gate(self):
        row = self.rows[4]
        self.assertEqual(L.client_legality_problems("ability", row), [])
        self.assertEqual(L.declared_block_field_problems("ability", row), [])
        self.assertEqual(L.ability_element_column_problems("ability", row, M.ELEMENT), [])
        self.assertEqual(L.invoke_skill_string_problems(row, {M.CAS_KEY}), [])
        self.assertEqual(L.required_client_capabilities("ability", row), [])
        self.assertEqual(M.row_gate_problems(row), [])

    def test_row_gate_catches_a_dangling_536_string(self):
        row = list(self.rows[4])
        row[70] = "superfever_desc_wt26"
        self.assertTrue(M.row_gate_problems(row))


class TextTests(unittest.TestCase):
    def setUp(self):
        self.values = live_values()
        self.out = revised()

    def test_skill_flag_string_keeps_the_super_fever_text_without_numbers(self):
        text = self.out["cas"][M.CAS_KEY]
        self.assertEqual(text, [["Fever状态中发动技能时，触发超级Fever：队伍全体的攻击力、强化弹射伤害、技能伤害、"
                                 "直接攻击伤害、能力伤害提升，同时为队伍全体回复生命值并赋予再生效果"]])
        self.assertEqual(KL.panel_problems(text[0][0], skill_flag=True), [])
        self.assertFalse(any(ch.isdigit() for ch in text[0][0]))
        self.assertEqual(self.values["cas", "superfever_desc_wt26"], [[M.OLD_CAS_TEXT]])

    def test_new_description(self):
        self.assertEqual(M.NEW_DESC,
                         "赋予队长护盾、体力最低角色再生／火属性和风属性角色的技能伤害与强化弹射伤害提升150%"
                         "／队伍全体贯通(12.5秒)／火属性共鸣时，自身在主位且于Fever状态中使用：Fever槽增加200，"
                         "并触发超级Fever（队伍全体的攻击力、强化弹射伤害、技能伤害、直接攻击伤害、能力伤害提升"
                         "350%(10秒)），同时为队伍全体回复最大生命值5%的生命值并赋予再生效果(10秒) ※技能无后摇")
        self.assertEqual(KL.panel_problems(M.NEW_DESC), [])

    def test_no_forbidden_panel_words(self):
        for text in (M.NEW_DESC, M.NEW_CAS_TEXT):
            for word in KL.FORBIDDEN_PANEL_WORDS:
                self.assertNotIn(word, text)
        # 自造的禁词样本必须被检查器抓到（检查器本身不是摆设）
        self.assertTrue(KL.panel_problems(M.NEW_CAS_TEXT + "，可无限叠加", skill_flag=True))
        self.assertTrue(KL.panel_problems(M.OLD_CAS_TEXT, skill_flag=True))   # 旧文案带数字，不合技能强化条目

    def test_character_text_only_touches_c5_and_c7(self):
        before = self.values["text", "179999"][0]
        after = self.out["text"]["179999"][0]
        self.assertEqual({i for i, (a, b) in enumerate(zip(before, after)) if a != b}, {5, 7})
        self.assertEqual((after[5], after[7]), (M.NEW_DESC, M.NEW_DESC))

    def test_server_mirror_only_touches_5_and_7(self):
        before = self.values["server_text", "179999"][0]
        after = self.out["server_text"]["179999"][0]
        self.assertEqual({i for i, (a, b) in enumerate(zip(before, after)) if a != b}, {5, 7})
        self.assertEqual(after, self.out["text"]["179999"][0])

    def test_action_skill_only_touches_c1_on_both_tiers(self):
        before = self.values["action", M.CODE]
        after = self.out["action"][M.CODE]
        self.assertEqual([inner for inner, _f in after], ["1", "2"])
        for (inner, old), (_inner, new) in zip(before, after):
            self.assertIsInstance(new, list)
            self.assertEqual({i for i, (a, b) in enumerate(zip(old, new)) if a != b}, {1}, inner)
            self.assertEqual(new[1], M.NEW_DESC)
            self.assertEqual(new[7], M.PROGRAMS[inner])
        self.assertEqual(core.decode_action_skill_row(core.encode_action_skill_row(after)), after)


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
            with self.assertRaises(M.RolfWt26BalanceError, msg=f"{kind}:{key}"):
                revised(values)

    def test_inputs_are_not_mutated(self):
        values = live_values()
        snapshot = copy.deepcopy(values)
        revised(values)
        self.assertEqual(values, snapshot)

    def test_existing_new_key_is_rejected(self):
        values = live_values()
        values["cas", M.CAS_KEY] = [["别人的文案"]]
        with self.assertRaises(M.RolfWt26BalanceError):
            revised(values)

    def test_revision_cannot_be_applied_twice(self):
        out = revised()
        values = live_values()
        values["ability", "1799993"] = out["ability"]["1799993"]
        with self.assertRaises(M.RolfWt26BalanceError):
            revised(values)

    def test_revise_is_deterministic(self):
        self.assertEqual(revised(), revised())


def _official_available() -> bool:
    return (core.project_root() / ".cdn" / "cn").is_dir()


@unittest.skipUnless(_official_available(), "需要 .cdn/cn 官方基线")
class OfficialBaselineTests(unittest.TestCase):
    """fixture 里的官方先例片段必须与 .cdn/cn 官方基线逐字一致。"""

    @classmethod
    def setUpClass(cls):
        from wf_enhancement_policy import OfficialBaseline
        root = core.project_root()
        cls.baseline = OfficialBaseline(root / ".cdn/cn", cache_dir=root / "mod-tools/work/official-baseline",
                                        write_cache=False)

    def tree(self, program):
        digest = core.sha1_path(wf_dsl.dsl_logical(program))
        raw = self.baseline.get("common", digest[:2] + "/" + digest[2:])
        self.assertIsNotNone(raw, program)
        return wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]

    def test_team_heal_and_regen_precedent_is_official(self):
        entry = DATA["official"]["team_heal_and_regen"]
        finders = [f for f in wf_dsl.iter_dsl_commands(self.tree(entry["program"]), "FindAllSubjects")
                   if f[1:3] == [0, 33]]
        self.assertEqual(len(finders), 1)
        body = [c[1] for c in finders[0][9][1]]
        self.assertIn(entry["ratio_heal"], body)
        self.assertIn(entry["regeneration"], body)

    def test_no_slayer_ratio_heal_precedent_is_official(self):
        entry = DATA["official"]["ratio_heal_without_slayer"]
        self.assertIn(entry["ratio_heal"], list(wf_dsl.iter_dsl_commands(self.tree(entry["program"]),
                                                                         "CreateRatioHeal")))


if __name__ == "__main__":
    unittest.main()
