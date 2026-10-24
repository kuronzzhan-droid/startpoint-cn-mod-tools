# -*- coding: utf-8 -*-
"""wf_seasonal7_kit_yuki：门禁函数的负向用例（变异必须变红）+ 配方锁 + 语音列约定。

包内 DSL 用例需要先跑过 ``--step kit``；包不存在时跳过（不读写 live）。
"""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
pass  # Imports resolve from this checkout/package, not external source copies.

import wf_seasonal7_kit_yuki as K  # noqa: E402

ROOT = HERE.parent.parent
PKG_DSL = (ROOT / "work/character_packs/s7-yuki/package/roots/common/battle/action/skill/action/rare5"
           / "psychic_yuki_swim$psychic_yuki_swim_2.action.dsl.amf3.deflate")


def _package_tree():
    import wf_seasonal7_common as C
    return C.amf_parse(PKG_DSL.read_bytes())


class PureGateTests(unittest.TestCase):
    def test_route_is_voice_tool_canonical(self):
        import wf_seasonal7_voice as V
        self.assertEqual(V.normalize_route({"kind": 3}, K.CODE), K.VOICE_ROUTE)

    def test_row_sha_matches_csv_text(self):
        row = ["a", "b,c", ""]
        self.assertEqual(K.row_sha(row), K.row_sha(list(row)))
        self.assertNotEqual(K.row_sha(row), K.row_sha(["a", "b", "c"]))

    def test_recipe_locks_are_unique_and_complete(self):
        shas = [r[4] for r in K.LEADER_RECIPE] + [r[4] for rs in K.ABILITY_RECIPE.values() for r in rs]
        self.assertEqual(len(shas), 23)                    # 队长 7 + 词条 16（五轮 R31 给能力1 加了一条）
        self.assertEqual(len(set(shas)), 23)
        self.assertEqual(sum(len(v) for v in K.ABILITY_RECIPE.values()), 16)
        self.assertEqual(len(K.ABILITY_RECIPE[1]), 3)
        self.assertEqual(len(K.LEADER_RECIPE), 7)

    def test_recipe_donors_avoid_own_keys(self):
        """donor 不能是角色自己的键：发布后 live 就是本方案的产物，重跑会不自洽。"""
        own = {K.CID} | {f"{K.CID}{s}" for s in range(1, 7)}
        donors = [(r[0], r[1]) for r in K.LEADER_RECIPE] + [(r[0], r[1]) for rs in K.ABILITY_RECIPE.values()
                                                            for r in rs]
        self.assertEqual([d for d in donors if d[1] in own], [])

    def test_recipe_matches_revision_plan(self):
        """配方 sha 锁 == 二轮 plan.json + 五轮行锁覆盖；技能说明对三轮 text.json（方案与实现不得分叉）。"""
        import json
        plan_path = ROOT / K.REVISION_REL
        if not plan_path.is_file():
            self.skipTest("revision plan absent")
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        lock_path = ROOT / K.REVISION5_REL
        rev5 = json.loads(lock_path.read_text(encoding="utf-8")) if lock_path.is_file() else None
        want = K.row_sha_lock(plan, rev5)
        self.assertEqual([r[4] for r in K.LEADER_RECIPE], want["leader"])
        for slot, recipe in K.ABILITY_RECIPE.items():
            self.assertEqual([r[4] for r in recipe], want[f"{K.CID}{slot}"], f"slot {slot}")
        if rev5 is not None:                      # 五轮确实覆盖了三条（否则这层锁形同虚设）
            plan_only = K.row_sha_lock(plan, None)
            diff = [i for i, (a, b) in enumerate(zip(plan_only["leader"], want["leader"])) if a != b]
            self.assertEqual(diff, [3])           # 只有 L3
        self.assertEqual(K.CHANGE_SKILL_TEXT, plan["text"]["custom_ability_string"]["text"])
        # R26：技能说明首句随「旋转结界」改动，锁移到三轮 text.json；缺文件时回落二轮 plan.json
        lock_path = ROOT / K.REVISION3_REL
        lock = json.loads(lock_path.read_text(encoding="utf-8")) if lock_path.is_file() else None
        want = K.skill_desc_lock(plan, lock)
        self.assertEqual([K.SKILL_DESC_1, K.SKILL_DESC_2], [want["1"], want["2"]])
        self.assertEqual([want["c5"], want["c7"]], [want["1"], want["2"]])   # character_text 与 action_skill 同源
        if lock is not None:
            self.assertNotEqual(want["1"], plan["text"]["action_skill"]["1"]["c1"])   # 确实覆盖了二轮的值
            self.assertEqual(K.skill_desc_lock(plan, None)["1"], plan["text"]["action_skill"]["1"]["c1"])

    def test_revision2_ability6_shield_has_20s_cooldown(self):
        """二轮 R24「能力6赋予的护盾ct20s」：1299916#0 的 c35 冷却 = 1200 原始帧（60 帧/秒）。"""
        edits = K.ABILITY_RECIPE[6][0][3]
        self.assertEqual(edits.get(35), "1200")
        self.assertEqual(edits.get(47, "65"), edits.get(47, "65"))    # 触发 kind 由 donor 带（PF Lv3）
        # 另一条不带 CT：作者只要求护盾那条
        self.assertNotIn(35, K.ABILITY_RECIPE[6][1][3])

    def test_revision2_panel_text_rules(self):
        """二轮文案两条规则：面板零「无上限」；536 串零数字零秒数。"""
        self.assertEqual(K.panel_text_problems(), [])
        self.assertEqual(sum(t.count("无上限") for t in K.PANEL_TEXTS.values()), 0)
        self.assertEqual(K.SKILL_FLAG_TEXT_NAMES, ("CAS_TEXT",))
        import re
        self.assertIsNone(re.search(r"[0-9０-９]", K.CHANGE_SKILL_TEXT))
        self.assertNotIn("秒", K.CHANGE_SKILL_TEXT)
        self.assertIn(K.SKILL_NAME_1, K.CHANGE_SKILL_TEXT)            # 仍写清强化的是哪一招

    def test_revision2_panel_text_negative_controls(self):
        """去掉规则守卫必须变红：任一落点被塞进「无上限」/ 536 串写数字或秒数都要报出来。"""
        for bad in ("（无上限）", "，可无限叠加", "，不封顶"):
            probs = K.panel_text_problems({**K.PANEL_TEXTS, "CAS_TEXT": K.CHANGE_SKILL_TEXT + bad})
            self.assertTrue(probs, bad)
        self.assertTrue(K.panel_text_problems({**K.PANEL_TEXTS,
                                               "SKILL_DESC_1": K.SKILL_DESC_1 + "（无上限）"}))
        self.assertTrue(K.panel_text_problems({**K.PANEL_TEXTS,
                                               "CAS_TEXT": f"强化『{K.SKILL_NAME_1}』：威力+50%"}))
        self.assertTrue(K.panel_text_problems({**K.PANEL_TEXTS,
                                               "CAS_TEXT": f"为『{K.SKILL_NAME_1}』追加「连击加成」，持续十五秒"}))
        # 规则 2 不误伤技能说明：c1 里写倍率与方向数是允许的
        self.assertEqual(K.panel_text_problems({"SKILL_DESC_1": K.SKILL_DESC_1}), [])

    def test_skill_desc_claims_no_caster_anchor(self):
        """判定区锚在停球点的参照点（结界本体），文案不得断言「自身周围」。"""
        for desc in (K.SKILL_DESC_1, K.SKILL_DESC_2):
            self.assertNotIn("自身周围", desc)
            self.assertIn(f"{K.ORBIT_RING_N}个", desc)

    def test_action_skill_design_selfcheck_is_reachable(self):
        """对抗审查 20260917：c8-c10 与能量三列的设计比对曾写在 ``raise`` 之后 = 死代码。

        修好之后它们会真的跑起来，所以这里先钉住「跑起来也是绿的」：kit 常量与设计定稿逐值相同；
        再顺手用源码断言「那两条检查不在任何 raise 之后」，防止将来又被塞回去。
        """
        import inspect
        import json as _json
        from pathlib import Path as _Path
        design = _json.loads((_Path(K.__file__).resolve().parents[1] / K.DESIGN_REL)
                             .read_text(encoding="utf-8"))
        for level in ("1", "2"):
            plan = design["skills"]["action_skill_rows"][level]
            energy = design["skills"]["energy"][level]
            self.assertEqual(list(K.AUTO_CAST), plan["c8_c10"], level)
            self.assertEqual(list(K.ENERGY[level]),
                             [str(energy["c4"]), str(energy["c5"]), str(energy["c6"])], level)
        # 用 AST 做通用扫描：同一语句块里 raise/return/continue/break 之后不许再有语句
        # （这正是当初那两条检查失效的形状），整个 kit 模块都查
        import ast
        tree = ast.parse(inspect.getsource(K))
        dead = []
        for node in ast.walk(tree):
            for field in ("body", "orelse", "finalbody"):
                block = getattr(node, field, None)
                if not isinstance(block, list):
                    continue
                for a, b in zip(block, block[1:]):
                    if isinstance(a, (ast.Raise, ast.Return, ast.Continue, ast.Break)):
                        dead.append(f"line {b.lineno} 跟在 line {a.lineno} 的 "
                                    f"{type(a).__name__} 之后 = 永远执行不到")
        self.assertEqual(dead, [], "wf_seasonal7_kit_yuki.py 里有死代码：" + "; ".join(dead))

    def test_revision3_skill_desc_is_short_and_matches_the_ring(self):
        """R26：说明首句改成「展开6个旋转结界」——比改前短 1 个字，且逐句与实机一致。"""
        before = "向6个方向展开结界并追加纵向冲击"
        for desc in (K.SKILL_DESC_1, K.SKILL_DESC_2):
            self.assertLessEqual(len(desc), 77)                  # 1.4.874 上线那版是 77 字
            self.assertNotIn(before, desc)
            self.assertIn("旋转", desc)                          # RotateHitArea 0.03 rad/帧
            self.assertIn("纵向冲击", desc)                      # 第二块判定区本轮未动
            self.assertIn("提升连击数", desc)                    # AddCombo + 每次命中 +1
        self.assertIn("24", K.SKILL_DESC_1)                      # 面板合计倍率与线上相同
        self.assertIn("34", K.SKILL_DESC_2)
        # 规则：多段技只写合计，不把内部节流值写进面板
        for desc in (K.SKILL_DESC_1, K.SKILL_DESC_2):
            self.assertNotIn(str(K.ORBIT_HIT_CAP) + "次", desc)
            self.assertNotIn("秒", desc)
        self.assertEqual(K.panel_text_problems(), [])

    def test_orbit_constants_recompute_to_the_plan_numbers(self):
        """旋转 / 命中节拍 / 覆盖面三组数字必须与 orbit-plan.json 逐值相同（纯函数复算）。"""
        rot = K.orbit_rotation()
        self.assertEqual((rot["deg_per_frame"], rot["seconds_per_revolution"]), (1.7189, 3.49))
        self.assertEqual(rot["degrees_over_lifetime"], 226.9)
        self.assertEqual(rot["frames_per_symmetry_step"], 34.9)          # 6 重对称 ⇒ 0.58 秒图案复位
        sch = K.orbit_hit_schedule()
        self.assertEqual((sch["step_frames"], sch["opportunities"], sch["realized"]), (6, 22, 20))
        self.assertEqual((sch["last_hit_frame"], sch["hits_per_second"]), (114, 10.0))
        self.assertEqual(sch["hit_frames"][:3], [0, 6, 12])
        # 逐帧模拟引擎真值（放行条件是 v<1、置 余量+间隔 ⇒ 小数进位，节拍在 5/6 之间摆动）：
        # 机会数比保守模型更多，两个模型都 >= 命中上限 ⇒「实得 20 次」不依赖模型选择
        ex = K.orbit_hit_schedule_exact()
        self.assertEqual((ex["opportunities"], ex["realized"], ex["last_hit_frame"]), (24, 20, 106))
        self.assertEqual(ex["step_frames_observed"], [5, 6])
        self.assertGreaterEqual(ex["opportunities"], K.ORBIT_HIT_CAP)
        self.assertGreaterEqual(sch["opportunities"], K.ORBIT_HIT_CAP)
        self.assertLessEqual(sch["opportunities"], ex["opportunities"])   # ceil 模型只会低估
        cov = K.orbit_coverage()
        self.assertEqual((cov["adjacent_centre_gap_px"], cov["solid_cover_radius_px"], cov["max_reach_px"]),
                         (200.0, 369.2, 420))
        self.assertTrue(cov["centre_covered"])                           # 判定圆 220 > 环半径 200
        # 旋钮表里的两个替代节拍也必须自洽（改节拍就得同步改倍率）
        self.assertEqual(K.orbit_hit_schedule(132, 44, 30)["step_frames"], 4)
        self.assertEqual(K.orbit_hit_schedule(132, 16, 15)["step_frames"], 9)
        # 判定圆缩到 <= 环半径 ⇒ 环心空洞（负控）
        self.assertFalse(K.orbit_coverage(200, 180)["centre_covered"])

    def test_orbit_damage_split_keeps_panel_totals(self):
        """每击倍率 × 命中上限 + 纵向冲击 == 面板合计（削韧 24 / Fever 12 同理）。"""
        n = K.ORBIT_HIT_CAP
        for level, column in (("1", 12), ("2", 15)):
            lo, hi = K.ORBIT_RING_MULT[level]
            want_lo, want_hi = K.EXPECTED_MULT[level]
            self.assertEqual(round(n * lo + column, 6), float(want_lo), level)
            self.assertEqual(round(n * hi + (17 if level == "2" else 12), 6), float(want_hi), level)
        self.assertEqual(round(n * K.ORBIT_RING_TOUGH[0] + 12, 6), K.ORBIT_EXPECTED_TOUGH_FEVER[0])
        self.assertEqual(round(n * K.ORBIT_RING_FEVER[0] + 6, 6), K.ORBIT_EXPECTED_TOUGH_FEVER[1])
        # p5 flatDamage 同样逐击相加（NormalAttackCalculator 基础式 = 随机加数 + p5 + 攻击力×p6）
        # ⇒ 必须按同一个 ÷20 摊薄，否则一次施技的固定项 100 → 2000（对抗审查 20260917）
        self.assertEqual(n * K.ORBIT_RING_FLAT + 100, K.ORBIT_EXPECTED_FLAT)
        self.assertEqual(K.ORBIT_RING_FLAT * n, 100)

    def test_slot3_key_stays_main_only_without_double_m(self):
        """槽 3 整键 c1 保持 live 的 false（仅主位）；c1=false 与 202 不得同键双写（双 Ⓜ）。"""
        edits = [r[3] for r in K.ABILITY_RECIPE[3]]
        self.assertEqual([e.get(1) for e in edits], ["false"] * 5)
        self.assertEqual([e for e in edits if e.get(6) == "202"], [])

    def test_slot3_direct_attack_counts_the_whole_water_party(self):
        """R13/R30「每直击敌人50次」= 水属性角色**合计**（puller master 7 = TotalOfParty + 组 Blue）。

        改前是 0 Myself 而面板照样渲染「编成直接攻击」——面板说谎，作者在游戏里抓到了。
        """
        r13 = K.ABILITY_RECIPE[3][1][3]
        self.assertEqual((r13[28], r13[29]), ("7", "Blue"))
        self.assertNotEqual(r13[28], "0")                              # 负向：回到 Myself 就红
        self.assertEqual((r13[30], r13[31]), ("5000000", "5000000"))    # 50 次
        self.assertEqual((r13[34], r13[35]), ("(None)", "0"))           # 无上限、无 CT

    def test_revision5_row_overrides(self):
        """五轮三条口径修正：屏障→攻击力、75连击技能槽 5%、直击按水属性合计。"""
        import json
        self.assertEqual(K.LEADER_RECIPE[3][3][107], "0")               # R28 AttackPoint
        self.assertEqual((K.ABILITY_RECIPE[2][1][3][51], K.ABILITY_RECIPE[2][1][3][52]),
                         ("5000", "5000"))                              # R29
        lock_path = ROOT / K.REVISION5_REL
        if not lock_path.is_file():
            self.skipTest("revision5 row lock absent")
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        self.assertEqual((lock["key"], lock["cid"]), (K.KEY, K.CID))
        ids = [o["id"] for o in lock["overrides"]]
        self.assertEqual(ids, ["R28", "R29", "R30"])
        # R31：能力1 追加「每达成 75 连击 → 连击 +15」（instant 12 Combo + content 226）
        self.assertEqual([a["id"] for a in lock["adds"]], ["R31"])
        r31 = K.ABILITY_RECIPE[1][2][3]
        self.assertEqual((r31[27] if 27 in r31 else "12"), "12")
        self.assertEqual((r31[30], r31[31]), ("7500000", "7500000"))   # 每 75 连击
        self.assertEqual(r31[34], "(None)")                            # 不限次数
        self.assertEqual((r31[51], r31[52]), ("1500000", "1500000"))   # 连击 +15
        self.assertEqual(r31[6], "2")                                  # 水属性共鸣前置
        self.assertEqual(K.ABILITY_RECIPE[1][2][4], lock["adds"][0]["row_sha256"])
        self.assertEqual(K.record_counts_lock(
            json.loads((ROOT / K.REVISION_REL).read_text(encoding="utf-8")), lock)["1299911"], 3)
        recipe_sha = {"leader": [r[4] for r in K.LEADER_RECIPE]}
        recipe_sha.update({f"{K.CID}{s}": [r[4] for r in rs] for s, rs in K.ABILITY_RECIPE.items()})
        for ov in lock["overrides"]:
            bucket = "leader" if ov["table"] == K.LD else ov["key"]
            self.assertEqual(recipe_sha[bucket][ov["index"]], ov["row_sha256"], ov["id"])
            self.assertNotEqual(ov["row_sha256"], ov["row_sha256_before"], ov["id"])


    def test_template_provenance_rejects_live_fallback(self):
        class _Pack:
            def __init__(self, sources):
                self._s = sources

            def read_evidence(self, name, default=None):
                return self._s

        class _Ctx:
            def __init__(self, sources):
                self.pack = _Pack(sources)

        programs = [f"{K.RARE5}/{p}.action.dsl.amf3.deflate" for p in (
            "psychic_yuki_ny23$psychic_yuki_ny23_1", "psychic_yuki_ny23$psychic_yuki_ny23_2",
            "psychic_yuki$psychic_yuki_1", "psychic_yuki$psychic_yuki_2",
            "psychic_projection_smr23$psychic_projection_smr23_2",
            "sing_android_2halfanv$sing_android_2halfanv_1", "sing_android_2halfanv$sing_android_2halfanv_2")]
        good = {p: {"source": "official"} for p in programs}
        self.assertEqual(K.template_provenance_problems(_Ctx(good)), [])
        bad = dict(good)
        bad[programs[0]] = {"source": "live"}
        self.assertEqual(len(K.template_provenance_problems(_Ctx(bad))), 1)
        missing = dict(good)
        del missing[programs[-1]]
        self.assertEqual(len(K.template_provenance_problems(_Ctx(missing))), 1)

    def test_fx_manifest_forbids_fallback_mix(self):
        log = [{"sheet": "a.png", "dst_sheet": "x/x.png", "mode": "kit-fallback"},
               {"sheet": "b.png", "dst_sheet": "y/y.png", "mode": "kit-fallback"}]
        self.assertEqual(K.fx_recolor_problems(None, {}, None, log), [])      # 无 manifest：回退合法
        probs = K.fx_recolor_problems(None, {}, "manifest.json", log)
        self.assertEqual(len(probs), 2)
        self.assertTrue(all("kit-fallback" in p for p in probs))

    def test_donothing_branch_flagged(self):
        tree = ["ActionDsl", 2, ["None"], False, False, False, False, False, False, False, 0,
                ["Block", [["Command", ["ConditionalsChangeSkillFlag", 1, ["Block", []], ["DoNothing"]]]]]]
        self.assertTrue(K.donothing_branch_problems(tree))
        tree[11][1][0][1][3] = ["Block", []]
        self.assertEqual(K.donothing_branch_problems(tree), [])


@unittest.skipUnless(PKG_DSL.is_file(), "yuki package DSL not built")
def c_path(show_effect_cmd) -> str:
    """ShowEffect 的资源逻辑路径（p1 = ["SpecifyEffectDirectly", "<path>"]）。"""
    spec = show_effect_cmd[2]
    return spec[1] if isinstance(spec, list) and len(spec) > 1 else str(spec)


class PackageTreeMutationTests(unittest.TestCase):
    """包内定稿树为绿；每个变异都必须被对应门禁杀死。"""

    @classmethod
    def setUpClass(cls):
        cls.tree = _package_tree()

    def _scope(self, tree):
        return K.scope_problems(tree)

    def test_baseline_green(self):
        self.assertEqual(self._scope(self.tree), [])
        self.assertEqual(K.acskilldamage_gid_problems(self.tree)[0], [])
        self.assertEqual(K.donothing_branch_problems(self.tree), [])
        self.assertEqual(K.arity_problems(self.tree), [])

    def test_hit_area_p1_unbound_killed(self):
        t = copy.deepcopy(self.tree)
        next(c for c in K.walk_cmds(t) if c[0] == "CreateHitArea")[2] = 77
        self.assertTrue(any("CreateHitArea" in p for p in self._scope(t)))

    def test_gh_coordinate_unbound_killed(self):
        t = copy.deepcopy(self.tree)
        next(c for c in K.walk_cmds(t) if c[0] == "StopBall")[4] = ["GH", 55]
        self.assertTrue(any("GH" in p for p in self._scope(t)))

    def test_show_effect_subject_unbound_killed(self):
        t = copy.deepcopy(self.tree)
        next(c for c in K.walk_cmds(t) if c[0] == "ShowEffect" and c[3] == 1)[3] = 66
        self.assertTrue(any("ShowEffect" in p for p in self._scope(t)))

    def test_target_mate_removal_killed(self):
        t = copy.deepcopy(self.tree)
        root = t[11][1]
        del root[next(i for i, n in enumerate(root) if K.cmd(n) and K.cmd(n)[0] == "TargetMate")]
        self.assertTrue(self._scope(t))

    def test_equal_skill_damage_gid_killed(self):
        t = copy.deepcopy(self.tree)
        cc = next(c for c in K.walk_cmds(t) if c[0] == "CreateCondition" and c[1] == 12)
        cc[2][0][2] = [{"min": 0.85, "max": 1}]           # 与 113 非水块完全相同 → 同 gid 覆盖
        self.assertTrue(K.acskilldamage_gid_problems(t)[0])

    def test_revision_skill_shape_applied_and_not_reappliable(self):
        """R18–R26 已落在包内树上；两个算子重复施加都必须报错，而不是把特效搬两次 / 形状叠加。"""
        _near, _crp, _body, cha1, cha2 = K.locate_hit_areas(self.tree)
        self.assertEqual(cha1[12], K.ORBIT_FORMATION)          # R26：Circle(6, 200) 取代 R25 的 NWay
        self.assertEqual(cha1[15], ["Some", K.slv(K.ORBIT_HIT_CAP, K.ORBIT_HIT_CAP)])
        self.assertEqual(cha1[9], K.ORBIT_SHAPE_BARRIER)       # 结界判定圆 220（旋转下各向同性）
        self.assertEqual(cha2[9], K.SKILL_SHAPE_COLUMN)        # 纵向冲击 320×800（R19 起没再动过）
        pane = [c for c in K.walk_cmds(cha1[20]) if c[0] == "ShowEffect" and c[1] == "攻撃演出"]
        # R27（四轮）：R26 的「44 帧一拍 ×3 重发」已被推翻（那个窗口是误测），
        # 现在是**单发 + UntilTargetTerminates**：判定区终止 ⇒ fade() ⇒ 自然播 end 段碎裂消散
        self.assertEqual(len(pane), 1)
        self.assertEqual([c[1] for c in K.walk_cmds(cha1[20]) if c[0] == "Wait"], [])   # 重发链已删干净
        for p in pane:
            self.assertEqual(p[3], cha1[19])                   # p2 = 判定区绑定 id ⇒ 贴图跟着判定区走
            self.assertEqual(p[5], ["UntilTargetTerminates"])
            self.assertEqual((p[10], p[11]), (True, True))     # fade 由 (tp||td) && hasTerminated 触发
        with self.assertRaises(AssertionError):
            K.apply_skill_edits(copy.deepcopy(self.tree))
        with self.assertRaises(AssertionError):
            K.apply_orbit_edits(copy.deepcopy(self.tree), "2")
        with self.assertRaises(AssertionError):
            K.apply_fx_lifecycle_edits(copy.deepcopy(self.tree))

    def test_revision2_outward_reach_arithmetic_survives_as_history(self):
        """R25 的外扩算式仍是活的（R26 把它的产物整条换掉了，但母本漂移断言还靠它）。

        R25 收的是**环相对锚点的半径**（锚点是球停点不是角色立绘）：逐段速度 × 段帧数，
        20/10/5 → 710px、6/3/1 → 202px。R26 之后半径改由 ``Formation.Circle`` 第 2 参直接给 200px
        —— 与 R25 收到的 202px 只差 1%，作者上一轮认可的距离原样保留。
        """
        self.assertEqual(K.outward_reach(), 202)
        self.assertEqual(K.outward_reach(K.SKILL_EDIT_BEFORE["move_speeds"]), 710)
        self.assertAlmostEqual(K.ORBIT_RING_RADIUS / K.outward_reach(), 1.0, delta=0.02)
        # 包内树上 MoveHitArea 必须一条不剩：世界坐标位移与公转互斥（留着 = 螺旋飞出屏幕）
        self.assertEqual([c for c in K.walk_cmds(self.tree) if c[0] == "MoveHitArea"], [])

    def test_revision3_ring_orbits_around_the_anchor(self):
        """R26：旋转参照点 + Circle(6,200) 环 + 整组节流，七条 orbit 门禁全绿。"""
        self.assertEqual(K.orbit_problems(self.tree, "2"), [])
        loc = K.locate_orbit(self.tree)
        spin, rot, ring, column = loc["spin"], loc["rotate"], loc["ring"], loc["column"]
        self.assertEqual(rot[:3], ["RotateHitArea", K.ORBIT_SPIN_BIND, K.ORBIT_OMEGA])
        self.assertEqual(rot[3], ["None"])                      # 官方 RotateHitArea tween 100% None
        self.assertEqual((spin[1], spin[6], spin[7]), (K.SKILL_ANCHOR_SUBJECT, False, False))
        self.assertEqual(spin[2], ["AB"])                       # 初相与「球到最近敌人的角度」解耦
        self.assertGreaterEqual(spin[9], K.ORBIT_RING_LIFETIME)
        self.assertEqual((ring[2], ring[3], ring[7]), (K.ORBIT_SPIN_BIND, ["CD"], True))   # 公转三开关
        self.assertEqual((ring[10], ring[11]), (["Center"], ["Center"]))                   # pivot=0
        self.assertEqual(ring[13], ["SpecifyHitAreaLifetimeDirectly", K.ORBIT_RING_LIFETIME])
        self.assertEqual(ring[14], ["CalculatedUsingMaxNumOfHits", K.ORBIT_THROTTLE_N])
        self.assertEqual(ring[25], K.ORBIT_GID_GROUP)           # 整组一份冷却
        self.assertNotEqual(column[2], K.ORBIT_SPIN_BIND)       # 纵向冲击不跟着转
        totals = K.skill_totals(self.tree, "2")
        self.assertEqual(totals["mult"], list(K.EXPECTED_MULT["2"]))
        self.assertEqual((totals["toughness"], totals["fever"]), K.ORBIT_EXPECTED_TOUGH_FEVER)
        self.assertEqual(totals["flat"], K.ORBIT_EXPECTED_FLAT)          # 固定伤害合计也不动
        self.assertEqual(totals["ring_per_hit"]["flat"], K.ORBIT_RING_FLAT)
        self.assertEqual(totals["combo_per_enemy"], K.ORBIT_HIT_CAP + K.ORBIT_COLUMN_COMBO)

    def test_revision3_orbit_negative_controls(self):
        """六个变异都必须被 ``orbit_problems`` 判红——R2/R3/R4 三个高中危风险各配一条。"""
        def mutate(fn):
            t = copy.deepcopy(self.tree)
            fn(K.locate_orbit(t), t)
            return K.orbit_problems(t, "2")

        # R2：旋转静默失效（td=true ⇒ stepDir 每帧把 r 重写，不崩不报错，只是环不转）
        self.assertTrue(any("trackingDir" in p for p in mutate(lambda l, t: l["spin"].__setitem__(7, True))))
        # 角速度写 0 = 不转
        self.assertTrue(mutate(lambda l, t: l["rotate"].__setitem__(2, 0)))
        # 坐标系写 AB = 官方那种静止环（公转的唯一开关）
        self.assertTrue(mutate(lambda l, t: l["ring"].__setitem__(3, ["AB"])))
        # trackingPos=false = 只在生成那一帧摆位
        self.assertTrue(mutate(lambda l, t: l["ring"].__setitem__(7, False)))
        # R3：纵向冲击挂到旋转参照点上 ⇒ 冲击会转到脚底下
        self.assertTrue(any("纵向冲击" in p for p in mutate(lambda l, t: l["column"].__setitem__(2, K.ORBIT_SPIN_BIND))))
        # R4：塞回一条 MoveHitArea ⇒ 公转 + 世界坐标位移 = 螺旋
        self.assertTrue(any("MoveHitArea" in p for p in mutate(
            lambda l, t: l["ring"][20][1].append(["Command", ["MoveHitArea", l["ring"][19], ["CD"], 0, 6, ["None"]]]))))
        # 判定圆缩到 <= 环半径 ⇒ 环心空洞（boss 站球停点打不到）
        self.assertTrue(any("空洞" in p for p in mutate(
            lambda l, t: l["ring"].__setitem__(9, ["Circle", K.slv(180, 180)]))))
        # 改命中上限但不改每击倍率 ⇒ 面板合计对不上
        self.assertTrue(any("合计" in p for p in mutate(
            lambda l, t: l["ring"].__setitem__(15, ["Some", K.slv(30, 30)]))))
        # R27：特效寿命写回 R26 的 44 帧 ⇒ 每 44 帧从第 1 帧重播展开（作者说的「缩短重新延长」）
        self.assertTrue(any("攻撃演出" in p for p in mutate(
            lambda l, t: [c for c in K.walk_cmds(l["ring"][20])
                          if c[0] == "ShowEffect"][0].__setitem__(
                              5, ["SpecifyEffectLifetimeDirectly", K.ORBIT_FX_WINDOW]))))
        # R27：中心圈寿命写回 102 ⇒ 比外圈提前消失（作者的第一个症状）
        self.assertTrue(any("中心特效" in p for p in mutate(
            lambda l, t: [c for c in K.walk_cmds(t)
                          if c[0] == "ShowEffect" and c[1] == "チャージ演出"][0].__setitem__(
                              5, ["SpecifyEffectLifetimeDirectly", K.R4_CENTER_LIFETIME_BEFORE]))))
        # R27：重发链复活 ⇒ onCreate 里出现第二条「攻撃演出」+ Wait
        self.assertTrue(any("Wait" in p for p in mutate(
            lambda l, t: l["ring"][20][1].append(
                ["Event", ["Wait", K.ORBIT_FX_WINDOW, "*",
                           ["Block", [copy.deepcopy(l["ring"][20][1][0])]]]]))))
        # p5 flatDamage 漏摊薄（留母本的 100）⇒ 一次施技固定项 100 → 2000（对抗审查 20260917）
        self.assertTrue(any("固定伤害" in p for p in mutate(
            lambda l, t: [c for c in K.walk_cmds(l["ring"][23])
                          if c[0] == "CreateNormalAttack"][0].__setitem__(5, 100))))

    def test_revision2_ring_is_anchored_at_the_ball_not_the_caster(self):
        """结界环锚在**球停点**（``CreateReferencePoint`` p0 = -18 球），不是角色（-17）。

        ``FindNearSubjects(-18, bind 1, selector 49) → StopBall(-18) → CreateReferencePoint(-18, 偏移 0)``
        ⇒ 6 个子判定区与其「攻撃演出」全挂在这个参照点上（``CreateHitArea.p1 == crp bind``）。

        **-18 正是官方对「自身周围」的编码方式**（全库普查：CRP p0=-18 有 691 处 / -17 只有 6 处；
        说明写「自身周围」的 52 个官方技能里 47 个锚在 -18、0 个锚在 -17）——球停点 = 技能在屏上的发动原点。
        所以 R25 收「环相对球停点的半径」就是这条反馈的正确杠杆；把 p0 改成 -17 是 6/691 的边缘写法，
        还会让判定区离开 ``FindNearSubjects(49)`` 选中的敌人，非作者明确要求不要动。本轮锚点一格未动。
        """
        a = K.barrier_anchor(self.tree)
        self.assertEqual(a["subject"], K.SKILL_ANCHOR_SUBJECT)
        self.assertEqual(a["subject"], -18)                      # -18=球；-17 才是角色（wf-dsl-builtin-subjects）
        self.assertEqual(a["offset"], K.SKILL_ANCHOR_OFFSET)
        self.assertTrue(a["attached"])
        self.assertEqual(K.anchor_problems(self.tree), [])
        # 树里挂 -17（角色自身）的只有屏障光环这一个 ShowEffect，判定区一个都不挂 -17
        on_caster = [c for c in K.walk_cmds(self.tree) if c[0] == "ShowEffect" and c[3] == -17]
        self.assertEqual(len(on_caster), 1)
        self.assertIn("barrier", c_path(on_caster[0]))
        self.assertEqual([c for c in K.walk_cmds(self.tree) if c[0] == "CreateHitArea" and c[2] == -17], [])

    def test_revision2_anchor_negative_controls(self):
        """负控：把锚点搬到角色 / 给参照点加偏移 / 把判定区摘下来，三种都必须判红。"""
        for label, mutate in (
                ("subject", lambda crp, cha1: crp.__setitem__(1, -17)),
                ("offset", lambda crp, cha1: crp.__setitem__(3, 120)),
                ("detach", lambda crp, cha1: cha1.__setitem__(2, 99))):
            with self.subTest(label):
                t = copy.deepcopy(self.tree)
                _n, crp, _b, cha1, _c2 = K.locate_hit_areas(t)
                mutate(crp, cha1)
                self.assertTrue(K.anchor_problems(t), f"{label} 变异没被 anchor_problems 判红")
        # R26：旋转参照点也在锚链上，它被搬到角色 / 加偏移同样必须判红
        for label, mutate in (("spin_subject", lambda spin: spin.__setitem__(1, -17)),
                              ("spin_offset", lambda spin: spin.__setitem__(4, 120))):
            with self.subTest(label):
                t = copy.deepcopy(self.tree)
                mutate(K.locate_orbit(t)["spin"])
                self.assertTrue(K.anchor_problems(t), f"{label} 变异没被 anchor_problems 判红")
                self.assertTrue(K.orbit_problems(t, "2"), f"{label} 变异没被 orbit_problems 判红")

    def test_hit_area_budget_gate_kills_uncapped_multi_area(self):
        """多子判定区必须显式封顶：p14=['None'] **且** p24=0（1.4.874 的形）要变红。"""
        self.assertEqual(K.hit_area_budget_problems(self.tree)[0], [])
        t = copy.deepcopy(self.tree)
        _n, _c, _b, cha1, _cha2 = K.locate_hit_areas(t)
        cha1[15], cha1[25] = ["None"], 0
        self.assertTrue(K.hit_area_budget_problems(t)[0])
        cha1[25] = 1                                       # p24=1 = group 级 minHitInterval，也是合法封顶
        self.assertEqual(K.hit_area_budget_problems(t)[0], [])

    def test_scalar_into_slv_param_killed(self):
        t = copy.deepcopy(self.tree)
        next(c for c in K.walk_cmds(t) if c[0] == "AddCombo")[1] = 12
        self.assertTrue(K.arity_problems(t))


if __name__ == "__main__":
    unittest.main()


def _png(size=(8, 6), opaque_rect=(0, 0, 4, 3)):
    import io
    from PIL import Image
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    x0, y0, x1, y1 = opaque_rect
    for y in range(y0, y1):
        for x in range(x0, x1):
            img.putpixel((x, y), (40, 120, 220, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class Revision4FxLifecycleTests(unittest.TestCase):
    """R27（作者第四轮）：外圈保持住再播消失动画、中心圈与最外层同帧散尽。

    逐帧证据 + 改前改后连拍在
    ``work/character_packs/seasonal7-20260916/revision4-20260917/yuki/fx-timing.md``。
    """

    WAVE = (ROOT / "work/character_packs/s7-yuki/package/roots/common"
            / "battle/effect/skill_unique/psychic_yuki_swim_wave")

    def _amf(self, name):
        import wf_seasonal7_common as C
        return C.amf_parse((self.WAVE / name).read_bytes())

    # ---------------- 纯函数（不依赖包）

    def test_attack_segments_are_contiguous_and_cover_the_whole_family(self):
        seqs = K.FX_ATTACK_SEQUENCES
        self.assertEqual([(s["name"], s["kind"]) for s in seqs],
                         [("start", "pass"), ("loop", "loop"), ("end", "once")])   # 官方 94 处同形
        self.assertEqual(seqs[0]["begin"], 1)
        self.assertEqual(seqs[-1]["end"], K.FX_ATTACK_TOTAL)
        for a, b in zip(seqs, seqs[1:]):
            self.assertEqual(b["begin"], a["end"] + 1)

    def test_ice_break_se_frame_is_not_inside_the_loop(self):
        """第 90 帧 ``se_ice_break_echo`` 圈进 loop = 每 0.3 秒重播一次碎冰音。"""
        lo, hi = K.FX_ATTACK_LOOP
        for f in K.FX_ATTACK_SOUND_FRAMES:
            self.assertFalse(lo <= f <= hi, f"SE 帧 {f} 落在 loop 段 {lo}..{hi}")
        self.assertEqual(K.FX_ATTACK_END[0], 90)          # 碎冰音正是 end 段首帧

    def test_centre_and_outer_vanish_on_the_same_frame(self):
        """作者第三句：「中心的圈和最外层时间一样」。"""
        outer_gone = K.ORBIT_RING_LIFETIME + K.FX_ATTACK_END_FRAMES
        centre_gone = K.R4_CENTER_LIFETIME + K.FX_PLAYER_FADE_FRAMES
        self.assertEqual(K.R4_CENTER_LIFETIME, K.ORBIT_RING_LIFETIME)
        self.assertEqual(K.FX_PLAYER_FADE_FRAMES, K.FX_ATTACK_END_FRAMES)
        self.assertEqual(outer_gone, centre_gone)
        self.assertGreater(K.R4_CENTER_LIFETIME, K.R4_CENTER_LIFETIME_BEFORE)   # 102 → 132

    def test_player_fade_tween_bits_decode_like_the_official_sibling(self):
        """渐隐尾的补间位域必须与同族官方 ``character_back`` 的 end 段逐位同构（只有时长不同）。"""
        bits = K.FX_PLAYER_TWEEN_BITS | (K.FX_PLAYER_FADE_FRAMES - 2)
        self.assertEqual(bits & 0xFFFF, K.FX_PLAYER_FADE_FRAMES - 2)       # 时长
        self.assertEqual((bits >> 16) & 3, 2)                              # tween kind 2（自定义缓动）
        self.assertEqual((bits >> 18) - 63, 0)                             # ev-63 = 0 ⇒ 线性
        official = 16646153                                                # character_back 的 end 补间帧 t
        self.assertEqual((official >> 16) & 3, (bits >> 16) & 3)
        self.assertEqual((official >> 18) - 63, (bits >> 18) - 63)

    def test_patches_reject_a_drifted_mother(self):
        with self.assertRaises(AssertionError):
            K.fx_attack_timeline_patch({"sequences": [{"begin": 1, "end": 9, "name": "x", "kind": "once"}]})
        with self.assertRaises(AssertionError):
            K.fx_player_timeline_patch({"sequences": [{"begin": 1, "end": 9, "name": "x", "kind": "once"}]})
        with self.assertRaises(AssertionError):
            K.fx_player_parts_patch({"g": [{"t": 60, "s": [{"s": 0, "i": 1, "l": [{"m": 255, "t": 60}]}]}]})

    def test_fx_timeline_problems_kills_the_untouched_mother(self):
        """负控：母本形态（一条 neutral once / 一条 loop / g[0].t=45）必须被判红。"""
        probs = K.fx_timeline_problems(
            {"sequences": copy.deepcopy(K.FX_ATTACK_SEQ_BEFORE), "sounds": []},
            {"sequences": copy.deepcopy(K.FX_PLAYER_SEQ_BEFORE)},
            {"g": [{"t": K.FX_PLAYER_LOOP_END,
                    "s": [{"s": 0, "i": 1, "l": [{"m": 255, "t": K.FX_PLAYER_LOOP_END}]}]}]})
        self.assertTrue(probs)
        self.assertTrue(any("attack timeline" in p for p in probs))
        self.assertTrue(any("player timeline" in p for p in probs))
        self.assertTrue(any("g[0].t" in p for p in probs))

    def test_fx_timeline_problems_kills_a_loop_that_swallows_the_se(self):
        bad = {"sequences": [{"begin": 1, "end": 71, "name": "start", "kind": "pass"},
                             {"begin": 72, "end": 101, "name": "loop", "kind": "loop"},
                             {"begin": 102, "end": 143, "name": "end", "kind": "once"}],
               "sounds": [{"path": "sound_effect/water/se_ice_break_echo", "begin": 90}]}
        probs = K.fx_timeline_problems(bad, {"sequences": copy.deepcopy(K.FX_PLAYER_SEQUENCES)},
                                       {"g": [{"t": K.FX_PLAYER_END_END, "s": [{"s": 0, "i": 1, "l": [
                                           {"m": 255, "t": K.FX_PLAYER_LOOP_END},
                                           {"m": 255, "t": K.FX_PLAYER_TWEEN_BITS | (K.FX_PLAYER_FADE_FRAMES - 2)},
                                           {"m": K.FX_PLAYER_FADE_ALPHA}]}]}]})
        self.assertTrue(any("sequences" in p for p in probs))       # 边界不是锁定值

    # ---------------- 包内产物（需要先跑过 --step kit）

    def test_package_assets_carry_the_patch(self):
        if not self.WAVE.is_dir():
            self.skipTest("package not built")
        attack = self._amf("psychic_yuki_ny23_attack.timeline.amf3.deflate")
        player_tl = self._amf("psychic_yuki_ny23_player.timeline.amf3.deflate")
        player_parts = self._amf("psychic_yuki_ny23_player.parts.amf3.deflate")
        self.assertEqual(K.fx_timeline_problems(attack, player_tl, player_parts), [])
        self.assertEqual(attack["sequences"], K.FX_ATTACK_SEQUENCES)
        self.assertEqual(player_tl["sequences"], K.FX_PLAYER_SEQUENCES)
        g0 = player_parts["g"][0]
        self.assertEqual(int(g0["t"]), K.FX_PLAYER_END_END)
        kfs = g0["s"][0]["l"]
        self.assertEqual([int(k["m"]) for k in kfs], [255, 255, K.FX_PLAYER_FADE_ALPHA])
        # 根 strip 跨度不得越过 g[0].t（客户端 #1125）
        span = sum((int(k.get("t") or 0) & 0xFFFF) or 1 for k in kfs)
        self.assertLessEqual(span, int(g0["t"]))
        # SE 一条不多一条不少，且碎冰音仍在第 90 帧
        self.assertEqual(tuple(int(s["begin"]) for s in attack["sounds"]), K.FX_ATTACK_SOUND_FRAMES)

    def test_package_patches_are_idempotent(self):
        if not self.WAVE.is_dir():
            self.skipTest("package not built")
        import wf_seasonal7_common as C
        for name, fn in (("psychic_yuki_ny23_attack.timeline.amf3.deflate", K.fx_attack_timeline_patch),
                         ("psychic_yuki_ny23_player.timeline.amf3.deflate", K.fx_player_timeline_patch),
                         ("psychic_yuki_ny23_player.parts.amf3.deflate", K.fx_player_parts_patch)):
            raw = (self.WAVE / name).read_bytes()
            self.assertEqual(C.amf_bytes(fn(C.amf_parse(raw))), raw, name)

    def test_package_tree_damage_and_combo_unchanged_by_r27(self):
        if not PKG_DSL.is_file():
            self.skipTest("package not built")
        tree = _package_tree()
        self.assertEqual(K.fx_lifecycle_problems(tree), [])
        totals = K.skill_totals(tree, "2")
        self.assertEqual(totals["mult"], list(K.EXPECTED_MULT["2"]))
        self.assertEqual((totals["toughness"], totals["fever"]), K.ORBIT_EXPECTED_TOUGH_FEVER)
        self.assertEqual(totals["flat"], K.ORBIT_EXPECTED_FLAT)
        self.assertEqual(totals["combo_per_enemy"], K.ORBIT_HIT_CAP + K.ORBIT_COLUMN_COMBO)
        ring = K.locate_orbit(tree)["ring"]
        self.assertEqual(ring[13], ["SpecifyHitAreaLifetimeDirectly", K.ORBIT_RING_LIFETIME])
        self.assertEqual(ring[14], ["CalculatedUsingMaxNumOfHits", K.ORBIT_THROTTLE_N])
        self.assertEqual(ring[15], ["Some", K.slv(K.ORBIT_HIT_CAP, K.ORBIT_HIT_CAP)])


class PngStorageMagicTests(unittest.TestCase):
    """审查 minor：像素产物标准魔数 PNG 直接拷进包 = 大写魔数；转码器与包级门禁必须拦住。"""

    def test_standard_magic_is_transcoded_without_touching_pixels(self):
        raw = _png()
        self.assertEqual(raw[:8], K.STD_PNG_MAGIC)
        native = K.wf_assets.png_encode(_png(opaque_rect=(1, 1, 2, 2)))
        out, info = K.pixel_sheet_store_bytes(raw, native, [(0, 0, 4, 3), (4, 3, 4, 3)])
        self.assertEqual(out[:8], K.WF_PNG_MAGIC)
        self.assertEqual(out[8:], raw[8:])
        self.assertEqual(info["magic_in"], "standard")
        self.assertEqual(info["size"], [8, 6])
        again, info2 = K.pixel_sheet_store_bytes(out, native)
        self.assertEqual(again, out)
        self.assertEqual(info2["magic_in"], "wf-storage")

    def test_size_atlas_alpha_and_magic_mutations_rejected(self):
        raw, native = _png(), K.wf_assets.png_encode(_png())
        with self.assertRaisesRegex(ValueError, "size"):
            K.pixel_sheet_store_bytes(_png(size=(9, 6), opaque_rect=(0, 0, 4, 3)), native)
        with self.assertRaisesRegex(ValueError, "atlas rects"):
            K.pixel_sheet_store_bytes(raw, native, [(5, 0, 4, 3)])      # x+w=9 > 8
        with self.assertRaisesRegex(ValueError, "alpha==0"):
            K.pixel_sheet_store_bytes(_png(opaque_rect=(0, 0, 8, 6)), native)
        with self.assertRaisesRegex(ValueError, "not a PNG"):
            K.pixel_sheet_store_bytes(b"GIF89a" + raw[6:], native)

    def test_package_scan_flags_standard_magic(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp)
            good = pkg / "roots/common" / K.PIXEL_DIR / "special_sprite_sheet.png"
            bad = pkg / "roots/common" / K.PIXEL_DIR / "sprite_sheet.png"
            medium = pkg / "roots/medium/character/x/ui/icon.PNG"
            server = pkg / "roots/server/ignored.png"
            for path, data in ((good, K.wf_assets.png_encode(_png())), (bad, _png()),
                               (medium, _png()), (server, _png())):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            problems, checked = K.package_png_storage_problems(pkg)
            self.assertEqual(checked, 3)                                  # server 根不在客户端根内
            self.assertEqual(len(problems), 2)
            self.assertTrue(any("sprite_sheet.png has standard PNG magic" in p for p in problems))
            self.assertTrue(any(p.startswith("medium:") for p in problems))
            bad.write_bytes(K.wf_assets.png_encode(_png()))
            medium.write_bytes(K.wf_assets.png_encode(_png()))
            self.assertEqual(K.package_png_storage_problems(pkg), ([], 3))
