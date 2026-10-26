# -*- coding: utf-8 -*-
"""泽赫尔·灯火酒馆 kit 的只读回归：设计行回放与合法性、覆盖文案、两棵技能树 = 设计定稿、
第三轮改版（「灯火正旺」12 秒 / 四行 CT 5 秒）与第四轮改版（能力3 30% / 灯芯每层 3%）的名单扫描、行/固有/文案落点与负向对照，
三档 PF = 设计 + 主控覆盖（每段倍率恢复官方、寿命/命中/Notify ×3、suppress 官方、叠 blaze 层）与满命中预算，
DSL 校验器的阴性对照与移植等价核对，官方签名表 sha 锁定，PF 短程序路径的 MAX_PATH 余量，旧长路径产物清理，
fx manifest 钩子与门禁状态判定。

不写包、不写 live；需要本机 live store、官方基线（.cdn/cn）与带 bundle.zip 的 APK，缺失时跳过。
"""
from __future__ import annotations

import copy
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
pass  # Imports resolve from this checkout/package, not external source copies.

import wf_seasonal7_kit_zehr as K  # noqa: E402


def _context():
    import wf_seasonal7_build as B
    import wf_seasonal7_common as C
    import wf_seasonal7_specs as S
    pack = C.S7Pack(S.get_spec(K.KEY))
    if pack.official_read(K.ABILITY, "common") is None:
        raise unittest.SkipTest("official baseline unavailable")
    return B.KitContext(pack)


def _family(src_dir: str, sub: str, bases) -> dict:
    """与 clone_effect_family 返回值同形的纯数据（不复制文件）。"""
    donor = src_dir.rsplit("/", 1)[-1]
    return {"src_dir": src_dir, "dst_dir": f"battle/effect/skill_unique/{K.CODE}/{sub}", "donor": donor,
            "dst_name": sub, "copied_bases": list(bases)}


FAMILIES = {sub: _family(src, sub, bases) for src, sub, bases in K.EFFECT_FAMILIES}


class ZehrKitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.ctx = _context()
        except unittest.SkipTest:
            raise
        except Exception as exc:                      # 没有 live profile 的机器
            raise unittest.SkipTest(f"live store unavailable: {exc}")
        cls.design = K.load_design(cls.ctx.root)
        cls.plan = K.load_revision(cls.ctx.root)

    # ---- spec / 文本
    def test_spec_merges_texts_capabilities_extra_keys(self):
        spec = self.ctx.spec
        self.assertEqual(spec.texts["title"], "灯火酒馆的团长")
        self.assertEqual(sorted(spec.required_capabilities), sorted(K.CAPABILITIES))
        self.assertEqual(spec.extra_keys[K.PFA], (K.PF_KEY,))
        self.assertEqual(spec.extra_keys[K.SW], (K.VOICE_KEY,))
        self.assertEqual(sorted(spec.extra_keys[K.CAS]), sorted(K.CAS_KEYS))
        self.assertEqual(len(K.CAS_KEYS), 7)
        self.assertEqual(sorted(spec.extra_keys[K.UC]), sorted(K.UC_IDS))
        self.assertEqual(K.check_texts_constant(self.design, self.plan), [])

    def test_revised_skill_description_is_short_and_two_levels_identical(self):
        """作者「角色技能描述不再写太复杂省略一下」：两档同文，比上一轮短得多。

        阈值 0.75 是审查修复轮 R5 定的：补回「赋予自身攻击力提升效果」后是 70 字 / 上一轮 95 字 = 73.7%。
        能力1 面板写「攻击力提升效果＋250%、强化弹射伤害提升效果＋250%」，技能说明必须点名这两个效果。
        """
        self.assertEqual(K.TEXTS["desc1"], K.TEXTS["desc2"])
        self.assertEqual(K.TEXTS["desc1"], self.plan["texts"]["action_skill_desc"]["new"])
        self.assertLess(len(K.TEXTS["desc1"]), len(K.DESIGN_SKILL_DESC) * 0.75)
        for word in K.SKILL_DESC_REQUIRED:
            self.assertIn(word, K.TEXTS["desc1"])
        self.assertEqual(K.check_texts_constant(self.design, self.plan), [])
        row = K.character_text_row(self.design)
        self.assertEqual((row[5], row[7]), (K.TEXTS["desc1"], K.TEXTS["desc2"]))
        self.assertEqual(row[:5], self.design["text"]["character_text_row"][:5])
        self.assertEqual(row[8:], self.design["text"]["character_text_row"][8:])

    def test_texts_check_catches_revision_drift(self):
        bad = copy.deepcopy(self.plan)
        bad["texts"]["action_skill_desc"]["new"] = "别的文案"
        self.assertTrue(K.check_texts_constant(self.design, bad))
        bad2 = copy.deepcopy(self.plan)
        bad2["texts"]["action_skill_desc"]["old"] = "别的旧文案"
        self.assertTrue(K.check_texts_constant(self.design, bad2))

    def test_revision_plan_identity_is_pinned(self):
        bad = copy.deepcopy(self.plan)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / K.REVISION_REL
            target.parent.mkdir(parents=True)
            bad["cid"] = "159998"
            target.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(K.KitError):
                K.load_revision(root)
            bad["cid"], bad["schema"] = K.CID, "something-else"
            target.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(K.KitError):
                K.load_revision(root)

    def test_override_text_drops_segment_damage_phrase(self):
        design_value = self.design["leader_desc_override"]["value"]
        self.assertIn(K.TEXT_DROPPED_BY_OVERRIDE, design_value)
        text = K.apply_text_override(design_value, "leader")
        self.assertNotIn(K.TEXT_DROPPED_BY_OVERRIDE, text)
        self.assertIn("变为3倍", text)
        self.assertEqual(K.panel_text_problems(text), [])
        with self.assertRaises(K.KitError):
            K.apply_text_override(text, "leader")
        self.assertTrue(K.panel_text_problems("自身为队长时，攻击力＋10%"))

    # ---- 行
    def test_rows_replay_revision_plan_and_pass_client_legality(self):
        rows, evidence = K.build_rows(self.ctx, self.plan)
        self.assertEqual(len(rows["leader"]), 6)
        self.assertEqual(sum(len(v) for v in rows["ability"].values()), 20)
        caps = set()
        for item in evidence:
            for field in ("client_legality_problems", "declared_block_field_problems",
                          "ability_element_column_problems", "trigger_limit_problems"):
                self.assertEqual(item[field], [], (item["table"], item["key"], item["record"], field))
            caps.update(item["capabilities"])
        self.assertEqual(caps, {"dash-parameter-v1"})
        slot3 = rows["ability"][f"{K.CID}3"]
        self.assertEqual([r[109] for r in slot3[1:3]], ["422", "422"])          # 特殊冲刺两行不变
        self.assertEqual({r[1] for r in slot3}, {"false"})
        slot1 = rows["ability"][f"{K.CID}1"]
        self.assertEqual(slot1[2][70], K.CHANGE_SKILL_KEY)                      # 536 已从 slot6 搬到 slot1
        self.assertEqual(slot1[2][6], "2")                                      # 并加了光属性共鸣前置
        self.assertEqual([(r[47], r[68]) for r in slot1[3:5]],
                         [("461", K.UC_ID), ("461", K.UC_ID2)])                 # 灯火正旺 + 灯芯同触发
        self.assertEqual([r[35] for r in slot1[3:5]], [str(K.CT_LAMP_FRAMES)] * 2)
        self.assertEqual((slot1[5][97], slot1[5][102], slot1[5][104], slot1[5][109]),
                         ("134", "(None)", K.UC_ID2, "413"))                    # 每层灯芯 → 独立乘区
        slot6 = rows["ability"][f"{K.CID}6"]
        self.assertEqual([r[47] for r in slot6], ["35", "55"])                  # 能力6 整键重做，不再发固有
        self.assertNotIn("461", [r[47] for r in slot6])
        self.assertEqual(rows["leader"], [e["row"] for e in self.plan["tables"]["leader_ability"]["records"]])
        expected = K.rev4_expected_ability_rows(self.plan)   # plan 行 + 第二轮主位限制 + 第三轮 CT + 第四轮强度
        for slot in range(1, 7):
            key = f"{K.CID}{slot}"
            self.assertEqual(rows["ability"][key], expected[key])
            planned = [e["row"] for e in self.plan["tables"]["ability"]["keys"][key]]
            diff_cols = {c for built, want in zip(rows["ability"][key], planned)
                         for c, (a, b) in enumerate(zip(built, want)) if a != b}
            # 第二轮只碰 c1，第三轮只碰 c35，第四轮只碰声明的数值列（c51/c52 或 c113/c114）
            allowed = {1, 35} | {c for (k, _i), (cols, _o, _n) in K.REV4_VALUE_ROWS.items()
                                 if k == key for c in cols}
            self.assertLessEqual(diff_cols, allowed, key)
        self.assertIn(f"{K.CID}6", K.mixed_c1_c2(rows["ability"]))                     # 混写只是信息
        pf_row = rows["leader"][2]
        self.assertEqual((pf_row[45], pf_row[80], pf_row[81], pf_row[82]),
                         ("722", K.PF_KEY, "1,2,3", K.PF_STRING_KEY))
        self.assertTrue(all(r[0] == K.CODE for r in rows["leader"]))

    def test_unlimited_trigger_limit_is_literal_none(self):
        """「无上限」必须写 (None)：空串 → Std.parseInt → 0 次 → 永不触发。"""
        rows, _ = K.build_rows(self.ctx, self.plan)
        unlimited = [(k, i) for k, lines in rows["ability"].items() for i, r in enumerate(lines)
                     if r[34] == "(None)"] + [("leader", i) for i, r in enumerate(rows["leader"])
                                              if r[32] == "(None)"]
        self.assertGreaterEqual(len(unlimited), 8)
        for kind, cols in (("ability", (27, 34)), ("leader_ability", (25, 32))):
            src = rows["leader"] if kind == "leader_ability" else \
                [r for lines in rows["ability"].values() for r in lines]
            for row in src:
                self.assertEqual(K.trigger_limit_problems(kind, row), [], row[:3])
                if row[cols[0]] not in ("", "0"):
                    bad = list(row)
                    bad[cols[1]] = ""
                    self.assertTrue(K.trigger_limit_problems(kind, bad))      # 负向对照

    def test_leader_gate_only_on_the_two_rows_the_author_asked_for(self):
        """审查修复轮 R1：作者原文只在能力2 写了「自身为队长时」。

        50 连击触发的四行（能力1 的两条发放行、能力3 的两条受益行）不许带 pre42：
        面板文案不写队长条件，带门就是「面板承诺 ≠ 实际生效」；
        （上一轮还多一条理由：能力1 那时 c1=true 可上合击位，带门的话那三行在合击位上全是死行；
        第二轮把能力1 改成主位专用后这条理由消失，但面板一致性这条理由仍在，规则不变。）
        """
        rows, _ = K.build_rows(self.ctx, self.plan)
        self.assertEqual(K.leader_gate_problems(rows["ability"]), [])
        for key, idx in K.NO_LEADER_GATE_ROWS:
            self.assertEqual(rows["ability"][key][idx][6], "0", (key, idx))
        for key, idx in K.LEADER_GATE_ROWS:
            self.assertEqual(rows["ability"][key][idx][6], "42", (key, idx))
        # 负向对照：把门加回去 / 拆掉，都必须报出来
        bad = {k: [list(r) for r in lines] for k, lines in rows["ability"].items()}
        bad[K.NO_LEADER_GATE_ROWS[0][0]][K.NO_LEADER_GATE_ROWS[0][1]][6] = "42"
        self.assertTrue(K.leader_gate_problems(bad))
        bad2 = {k: [list(r) for r in lines] for k, lines in rows["ability"].items()}
        bad2[K.LEADER_GATE_ROWS[0][0]][K.LEADER_GATE_ROWS[0][1]][6] = "0"
        self.assertTrue(K.leader_gate_problems(bad2))
        # 计划里若把门写回来，build_rows 必须直接 KitError
        plan = copy.deepcopy(self.plan)
        key, idx = K.NO_LEADER_GATE_ROWS[0]
        plan["tables"]["ability"]["keys"][key][idx]["edits"]["6"] = "42"
        plan["tables"]["ability"]["keys"][key][idx]["row"][6] = "42"
        with self.assertRaises(K.KitError):
            K.build_rows(self.ctx, plan)

    def test_row_replay_rejects_donor_drift(self):
        plan = copy.deepcopy(self.plan)
        plan["tables"]["ability"]["keys"][f"{K.CID}2"][0]["old_values"]["51"] = "999999"
        with self.assertRaises(K.KitError):
            K.build_rows(self.ctx, plan)
        plan = copy.deepcopy(self.plan)
        plan["tables"]["leader_ability"]["records"][0]["row"][49] = "1"
        with self.assertRaises(K.KitError):
            K.build_rows(self.ctx, plan)

    def test_frozen_donor_replays_without_reading_live(self):
        """稻穗 inaho2 发布后 live 1399951 第 2 行换成 724 行：A5#1 的 donor 钉成冻结行，回放不随 live 变。"""
        plan_ability = self.plan["tables"]["ability"]["keys"]
        frozen = [(key, j) for key, records in plan_ability.items() for j, entry in enumerate(records)
                  if K.parse_donor(entry["donor"]) in K.FROZEN_DONORS]
        self.assertEqual([(f"{K.CID}5", 1)], frozen)
        donor = plan_ability[f"{K.CID}5"][1]["donor"]
        spec = K.FROZEN_DONORS[K.parse_donor(donor)]
        row = K.frozen_donor_row(spec, donor)
        # 发布前（live 仍是 6 行）冻结行必须就是 live 那一行。
        live = self.ctx.csv_split(self.ctx.live_flat(K.ABILITY)["1399951"])
        if len(live) == 6:
            self.assertEqual(live[2], row)
        rows, evidence = K.build_rows(self.ctx, self.plan)
        self.assertEqual([(f"{K.CID}5", 1)], [(e["key"], e["record"]) for e in evidence if "donor_frozen" in e])

        ctx = self.ctx

        class NoInahoLive:                                   # live 里干脆没有稻穗能力1/3：冻结 donor 不受影响
            def __getattr__(self, name):
                return getattr(ctx, name)

            def live_flat(self, logical):
                flat = dict(ctx.live_flat(logical))
                if logical == K.ABILITY:
                    flat.pop("1399951", None)
                    flat.pop("1399953", None)
                return flat
        self.assertEqual(rows, K.build_rows(NoInahoLive(), self.plan)[0])

    def test_frozen_donor_pin_rejects_a_tampered_row(self):
        for spec in K.FROZEN_DONORS.values():
            self.assertEqual(spec["width"], len(K.frozen_donor_row(spec, "pin")))
            bad = copy.deepcopy(spec)
            bad["cells"][52] = "9999"
            with self.assertRaises(K.KitError):
                K.frozen_donor_row(bad, "tampered")

    def test_legality_negative_control(self):
        import wf_client_legality as L
        import wf_describe
        rows, _ = K.build_rows(self.ctx, self.plan)
        bad = list(rows["ability"][f"{K.CID}2"][0])
        bad[int(wf_describe.layout("ability")["blocks"]["precondition2"])] = ""
        self.assertTrue(L.client_legality_problems("ability", bad))

    # ---- 固有状态 / 图标
    def test_two_unique_conditions_and_distinct_icons(self):
        rows = self.plan["tables"]["unique_condition"]["rows"]
        self.assertEqual(sorted(rows), sorted(K.UC_IDS))
        self.assertEqual(rows[K.UC_ID2]["row"][4], "99")                # (None) = 上限 1，叠层机制全死
        self.assertNotIn(rows[K.UC_ID2]["row"][4], ("", "(None)"))
        self.assertEqual(rows[K.UC_ID]["row"], self.design["unique_conditions"][0]["row"])   # 老状态不动
        for uid in K.UC_IDS:
            self.assertEqual(rows[uid]["row"][2] + ".png", K.UC_ICONS[uid])
        lamp, wick = K.draw_lamp_icon(), K.draw_wick_icon()
        for img in (lamp, wick):
            self.assertEqual((img.size, img.mode), ((48, 48), "RGBA"))
        self.assertNotEqual(lamp.tobytes(), wick.tobytes())
        # 右下角（客户端画层数数字的位置）必须留白：外框白边 x/y≥44 不算，只看内底 32-43
        for name, img in (("lamp", lamp), ("wick", wick)):
            px = img.load()
            bright = sum(1 for x in range(32, 44) for y in range(32, 44)
                         if min(px[x, y][:3]) > 230 and px[x, y][3] > 200)
            self.assertEqual(bright, 0, f"{name} icon paints into the stack-count corner")

    # ---- 技能 DSL
    def _sources(self):
        return {name: K.load_program(self.ctx, name)[0] for name in K.SKILL_SOURCES}

    def test_skill_trees_equal_design_final_and_pass_checks(self):
        sources = self._sources()
        for level in (1, 2):
            tree, info = K.compose_skill(self.ctx, level, sources)
            tree, refs = self.ctx.rewrite_effect_refs(tree, FAMILIES["skill"], strict=True)
            self.assertEqual(refs["kept_donor"], [])
            design_tree = json.loads((self.ctx.root / K.DESIGN_TMP_REL / f"final_skill_{level}.json")
                                     .read_text(encoding="utf-8"))
            self.assertIsNone(K.first_difference(tree, design_tree))
            checks = K.dsl_problems(self.ctx.root, tree)
            self.assertTrue(checks["all_empty"], checks["problems"])
            self.assertTrue(checks["roundtrip"])
            self.assertEqual(info["multiplier_estimate"], {1: (39.0, 39.0), 2: (46.0, 55.0)}[level])

    def test_skill_revision_alv_channels_reach_250_percent(self):
        sources = self._sources()
        for level in (1, 2):
            tree, _ = K.compose_skill(self.ctx, level, sources)
            tree, _ = self.ctx.rewrite_effect_refs(tree, FAMILIES["skill"], strict=True)
            before = K.skill_revision_state(tree)
            applied = K.apply_skill_revision(tree, level, self.plan)
            self.assertEqual([a["id"] for a in applied], ["atk_alv", "pfd_alv"])
            state = K.skill_revision_state(tree)
            for edit in self.plan["skill_dsl"]["edits"]:
                self.assertTrue(K.num_equal(before[edit["id"]], edit[f"lv{level}"]["old"]))
                self.assertTrue(K.num_equal(state[edit["id"]], edit[f"lv{level}"]["new"]))
                cell = state[edit["id"]][0]
                self.assertEqual(cell["min"] + cell["alv_min"], K.SKILL_ENHANCED_TOTAL)
                self.assertEqual(cell["max"] + cell["alv_max"], K.SKILL_ENHANCED_TOTAL)
            checks = K.dsl_problems(self.ctx.root, tree)
            self.assertTrue(checks["all_empty"], checks["problems"])
            self.assertTrue(checks["roundtrip"])
            with self.assertRaises(K.KitError):                   # 幂等保护：旧值已经不在，再落一次必须报错
                K.apply_skill_revision(tree, level, self.plan)

    def test_skill_revision_rejects_broken_totals_and_shapes(self):
        sources = self._sources()
        tree, _ = K.compose_skill(self.ctx, 1, sources)
        tree, _ = self.ctx.rewrite_effect_refs(tree, FAMILIES["skill"], strict=True)
        bad = copy.deepcopy(self.plan)
        bad["skill_dsl"]["edits"][0]["lv1"]["new"] = [{"min": 1.0, "max": 1.0, "alv_min": 0.5, "alv_max": 0.5}]
        with self.assertRaises(K.KitError):
            K.apply_skill_revision(copy.deepcopy(tree), 1, bad)
        bad = copy.deepcopy(self.plan)
        bad["skill_dsl"]["edits"][1]["lv1"]["new"] = [{"min": 0.65, "max": 0.65}]
        with self.assertRaises(K.KitError):
            K.apply_skill_revision(copy.deepcopy(tree), 1, bad)

    def test_slv_alv_kwargs(self):
        self.assertEqual(K.slv(1, 2), [{"min": 1, "max": 2}])
        self.assertEqual(list(K.slv(1.0, 1.0, alv_min=1.5, alv_max=1.5)[0]),
                         ["min", "max", "alv_min", "alv_max"])
        with self.assertRaises(K.KitError):
            K.slv(1.0, alv_min=1.5)

    # ---- 覆盖文案
    def test_panel_overrides_cover_every_slot_with_rows(self):
        rows, _ = K.build_rows(self.ctx, self.plan)
        plan_cas = self.plan["texts"]["custom_ability_string"]
        self.assertEqual(sorted(plan_cas), sorted(K.CAS_KEYS))
        string_ids = {rows["leader"][0][0]} | {lines[0][0] for lines in rows["ability"].values()}
        for key in (K.LEADER_OVERRIDE_KEY,) + K.SLOT_OVERRIDE_KEYS:
            self.assertIn(key[len("desc_override_"):], string_ids)
            value = K.rev4_panel_text(key, plan_cas[key]["value"])      # 第二轮文案变换后才送检
            self.assertEqual(K.panel_text_problems(value), [], key)
            self.assertNotIn(K.TEXT_DROPPED_BY_OVERRIDE, value)
        self.assertEqual(plan_cas[K.PF_STRING_KEY]["action"], "unchanged")   # 722 说明仍取设计值

    def test_panel_text_states_cooldown_cap_and_no_self_wording(self):
        """审查修复轮 R3/R6：CT 与 99 层封顶必须写在面板上；kind 55 是战斗级，不许写「自身强化弹射伤害」。"""
        plan_cas = self.plan["texts"]["custom_ability_string"]
        for key, phrases in K.PANEL_REQUIRED_PHRASES.items():
            value = K.rev4_panel_text(key, plan_cas[key]["value"])
            self.assertEqual(K.panel_text_problems(value, key), [], key)
            for phrase in phrases:
                self.assertIn(phrase, value)
            self.assertTrue(K.panel_text_problems(value.replace(phrases[0], ""), key))   # 负向对照
        lead = K.rev4_panel_text(K.LEADER_OVERRIDE_KEY, plan_cas[K.LEADER_OVERRIDE_KEY]["value"])
        self.assertEqual(K.panel_text_problems(lead, K.LEADER_OVERRIDE_KEY), [])
        self.assertIn("强化弹射伤害＋200%", lead)
        self.assertNotIn("自身强化弹射伤害", lead)
        self.assertTrue(K.panel_text_problems(
            lead.replace("强化弹射伤害＋200%", "自身强化弹射伤害＋200%"), K.LEADER_OVERRIDE_KEY))
        # 「灯芯」乘区那一行不许再写「无上限」（实际封顶 99 层）
        self.assertNotIn("额外乘区＋5%（无上限）", plan_cas[f"desc_override_{K.CODE}_1"]["value"])

    # ---- 第二轮作者改版（revision2-20260916）
    def test_revision2_main_slot_restriction_on_abilities_1_3_5(self):
        """作者原话「泽赫尔的能力1和3和5带上主位限制」：整键 c1='false'，其余槽保持可上合击位。

        不加前置 202（c1=false 与 202 同键双写 = 双 Ⓜ，记忆卡 wf-unison-slot-mechanics）。
        """
        rows, _ = K.build_rows(self.ctx, self.plan)
        self.assertEqual(K.REV2_MAIN_SLOT_SLOTS, (1, 3, 5))
        for slot in range(1, 7):
            key = f"{K.CID}{slot}"
            want = "false" if slot in K.REV2_MAIN_SLOT_SLOTS else "true"
            self.assertEqual({r[1] for r in rows["ability"][key]}, {want}, key)   # 同键一致
            # 不许双 Ⓜ：三个前置槽（c6/c13/c20）都不许写 202，不是只查 precondition1
            for block in K.ABILITY_PRECONDITION_BLOCKS:
                self.assertNotIn(K.PRE_OWNER_IS_MAIN, [r[block] for r in rows["ability"][key]],
                                 f"{key} c{block}")
        changes = K.rev4_row_changes(self.plan, rows["ability"])["c1"]
        self.assertEqual(K.rev4_row_changes(self.plan, rows["ability"])["problems"], [])
        self.assertEqual(sorted(changes), [f"{K.CID}1", f"{K.CID}5"])             # 能力3 上一轮就是 false
        self.assertEqual(changes[f"{K.CID}1"], [0, 1, 2, 3, 4, 5])
        # 负向对照：改到声明之外的列 / 把不该主位的键改成 false / 带着 202 都必须报出来
        bad = {k: [list(r) for r in lines] for k, lines in rows["ability"].items()}
        bad[f"{K.CID}1"][0][51] = "999999"
        self.assertTrue(K.rev4_row_changes(self.plan, bad)["problems"])
        with self.assertRaises(K.KitError):
            K.apply_main_slot_only(f"{K.CID}2", ["x", "false"] + [""] * 124, "neg")
        # 202 落在**任何一个**前置槽都必须报（precondition1/2/3 = c6/c13/c20；
        # live 全库确有 202 写在非首前置槽的先例，只查 c6 的护栏是漏的）
        self.assertEqual(K.ABILITY_PRECONDITION_BLOCKS, (6, 13, 20))
        for block in K.ABILITY_PRECONDITION_BLOCKS:
            pre202 = list(rows["ability"][f"{K.CID}1"][0])
            self.assertNotEqual(pre202[block], K.PRE_OWNER_IS_MAIN)                # 阴性对照前是干净的
            pre202[block] = K.PRE_OWNER_IS_MAIN
            with self.assertRaises(K.KitError, msg=f"c{block}"):
                K.apply_main_slot_only(f"{K.CID}1", pre202, "neg")

    def test_revision2_main_icon_matches_c1_and_texts_follow_the_new_rules(self):
        """面板 Ⓜ：有覆盖文案的主位键（能力1/3）逐行写 <icon id='main'>；能力5 无覆盖文案由客户端自动画。

        文案规则①：面板不出现「无上限」，没有上限就什么都不跟；有上限（CT、99 层）照写。
        文案规则②：技能强化条目只写强化了什么，不写数值与秒数。
        """
        rows, _ = K.build_rows(self.ctx, self.plan)
        plan_cas = self.plan["texts"]["custom_ability_string"]
        texts = {k: K.rev4_panel_text(k, v["value"]) for k, v in plan_cas.items() if "value" in v}
        self.assertEqual(K.main_slot_panel_problems(rows["ability"], texts), [])
        self.assertEqual(K.rev2_skill_flag_problems(rows["ability"], texts), [])
        self.assertEqual(K.REV2_MAIN_ICON_KEYS, (f"desc_override_{K.CODE}_1", f"desc_override_{K.CODE}_3"))
        for key in K.REV2_MAIN_ICON_KEYS:
            lines = texts[key].split("\n")
            self.assertTrue(all(ln.startswith(K.MAIN_ICON) for ln in lines), key)
            self.assertEqual(texts[key].count(K.MAIN_ICON), len(lines), key)      # 每行恰一个，不重复叠加
            self.assertNotIn(K.MAIN_ICON + K.MAIN_ICON, texts[key], key)      # 不重复叠加图标
        for key in (K.LEADER_OVERRIDE_KEY, f"desc_override_{K.CODE}_2", f"desc_override_{K.CODE}_6"):
            self.assertNotIn(K.MAIN_ICON, texts[key], key)                        # 非主位键不画 Ⓜ
        # 规则①：全部面板文案 + 技能说明 + 固有名 里「无上限」出现 0 次；机制（99 层 / (None)）没动
        visible = list(texts.values()) + [K.TEXTS["desc1"], K.TEXTS["desc2"], K.TEXTS["leader"],
                                          K.TEXTS["skill1"], K.TEXTS["skill2"], K.TEXTS["profile"]]
        self.assertEqual(sum(t.count("无上限") for t in visible), 0)
        for word in ("无限叠加", "不设上限", "可无限"):
            self.assertEqual(sum(t.count(word) for t in visible), 0, word)
        leader_before = plan_cas[K.LEADER_OVERRIDE_KEY]["value"]
        self.assertEqual(leader_before.count("（无上限）"), 2)                      # 上一轮确实写了
        self.assertIn("每达成35连击，强化弹射伤害＋50%\n", texts[K.LEADER_OVERRIDE_KEY])
        self.assertIn(f"（每{K.CT_SECONDS}秒1次）", texts[f"desc_override_{K.CODE}_1"])   # 有上限的照写
        self.assertIn("最多99层", texts[f"desc_override_{K.CODE}_1"])
        self.assertIn("（最多10次）", texts[f"desc_override_{K.CODE}_2"])
        self.assertEqual(self.plan["tables"]["unique_condition"]["rows"][K.UC_ID2]["row"][4], "99")
        # 规则②：技能强化条目不写数值与时间
        enhance = [ln for ln in texts[f"desc_override_{K.CODE}_1"].split("\n") if K.ENHANCE_TEXT_MARK in ln]
        self.assertEqual(len(enhance), 1)
        self.assertNotIn("250%", enhance[0])
        self.assertIn("「攻击力提升效果」", enhance[0])
        self.assertIn("「强化弹射伤害提升效果」", enhance[0])
        self.assertTrue(K.rev2_enhance_text_problems({"x": enhance[0] + "：威力＋50%、持续15秒"}))
        # 负向对照：改写源不在 / 出现两次都必须报
        with self.assertRaises(K.KitError):
            K.rev4_panel_text(f"desc_override_{K.CODE}_3", "没有那段话")
        bad_rows = {k: [list(r) for r in lines] for k, lines in rows["ability"].items()}
        bad_rows[f"{K.CID}1"][0][1] = "true"
        self.assertTrue(K.main_slot_panel_problems(bad_rows, texts))
        no_icon = dict(texts, **{f"desc_override_{K.CODE}_3": texts[f"desc_override_{K.CODE}_3"]
                                 .replace(K.MAIN_ICON, "")})
        self.assertTrue(K.main_slot_panel_problems(rows["ability"], no_icon))

    # ---- 第三轮作者改版（revision3-20260916）：「灯火正旺效果延长到12s,ct改为5s」
    def test_revision3_cooldown_rows_are_exactly_the_four_50combo_rows(self):
        """作者说的「那个每 10 秒 1 次」= 本角色全部 c35=600 的四行，改 300 帧；其余 CT 列不动。

        计划里 c35 的取值只有 '600'（这四行）、'0'（能力2 两行、能力3#5、能力5#1 = 无 CT）与空串；
        队长表 CT 列 c33/c91 没有 600。扫描与名单不符就红（将来加了新 CT 行必须重新逐条判断）。
        """
        scan = K.rev3_cooldown_scan(self.plan)
        self.assertEqual(scan["problems"], [])
        self.assertEqual(scan["ability_rows"], [f"{K.CID}1#3", f"{K.CID}1#4", f"{K.CID}3#0", f"{K.CID}3#3"])
        self.assertEqual(scan["leader_cells"], [])
        self.assertEqual(scan["other_ability_c35_values"], ["", "0"])            # 其余行没有 CT
        self.assertEqual((K.CT_LAMP_FRAMES_REV2, K.CT_LAMP_FRAMES, K.CT_SECONDS), (600, 300, 5))
        rows, _ = K.build_rows(self.ctx, self.plan)
        for key, idx in K.REV3_CT_ROWS:
            self.assertEqual(rows["ability"][key][idx][35], "300", (key, idx))
            self.assertEqual(rows["ability"][key][idx][27], "13")                # 同一个触发：弹射
            self.assertEqual(rows["ability"][key][idx][30], "5000000")           # 同一个门槛：连击 50
        stale = [(k, i) for k, lines in rows["ability"].items() for i, r in enumerate(lines) if r[35] == "600"]
        self.assertEqual(stale, [])
        changes = K.rev4_row_changes(self.plan, rows["ability"])
        self.assertEqual(changes["problems"], [])
        self.assertEqual(changes["ct"], {f"{K.CID}1": [3, 4], f"{K.CID}3": [0, 3]})
        # 负向对照：漏改一行 / 改到名单外的行 / 名单外冒出 600 都必须报
        half = {k: [list(r) for r in lines] for k, lines in rows["ability"].items()}
        half[f"{K.CID}3"][0][35] = "600"
        self.assertTrue(K.rev4_row_changes(self.plan, half)["problems"])
        stray = {k: [list(r) for r in lines] for k, lines in rows["ability"].items()}
        stray[f"{K.CID}2"][0][35] = "300"
        self.assertTrue(K.rev4_row_changes(self.plan, stray)["problems"])
        with self.assertRaises(K.KitError):                                      # 名单外写着旧 CT
            K.apply_rev3_cooldown(f"{K.CID}2", 0, ["x"] * 35 + ["600"] + ["y"] * 90, "neg")
        with self.assertRaises(K.KitError):                                      # 名单内不是旧 CT（plan 漂了）
            K.apply_rev3_cooldown(K.REV3_CT_ROWS[0][0], K.REV3_CT_ROWS[0][1],
                                  ["x"] * 35 + ["120"] + ["y"] * 90, "neg")
        bad_plan = copy.deepcopy(self.plan)
        bad_plan["tables"]["ability"]["keys"][f"{K.CID}2"][0]["row"][35] = "600"
        self.assertTrue(K.rev3_cooldown_scan(bad_plan)["problems"])
        with self.assertRaises(K.KitError):
            K.build_rows(self.ctx, bad_plan)

    def test_revision3_lamp_lasts_longer_than_the_cooldown(self):
        """固有 159997「灯火正旺」600 → 720 帧（12 秒）；「灯芯」永续行不动。

        12 秒 > CT 5 秒 是本轮的立意（状态可常驻），两个常量必须一起满足这个不等式。
        """
        plan_row = self.plan["tables"]["unique_condition"]["rows"][K.UC_ID]["row"]
        self.assertEqual(plan_row[3], str(K.UC_LAMP_FRAMES_REV2))
        built = K.rev3_unique_row(K.UC_ID, plan_row)
        self.assertEqual(built[3], "720")
        self.assertEqual(built[:3] + built[4:], plan_row[:3] + plan_row[4:])     # 只动 c3
        self.assertEqual(K.UC_LAMP_FRAMES // K.FPS, K.LAMP_SECONDS)
        self.assertGreater(K.UC_LAMP_FRAMES, K.CT_LAMP_FRAMES)                   # 可常驻
        wick = self.plan["tables"]["unique_condition"]["rows"][K.UC_ID2]["row"]
        self.assertEqual(K.rev3_unique_row(K.UC_ID2, wick), wick)                # 灯芯不动
        with self.assertRaises(K.KitError):                                      # plan 漂了要报
            K.rev3_unique_row(K.UC_ID, ["x", "y", "z", "480"] + ["w"] * 11)
        with self.assertRaises(K.KitError):                                      # 名单外也写着 600 帧
            K.rev3_unique_row(K.UC_ID2, ["x", "y", "z", "600"] + ["w"] * 11)

    def test_revision3_panel_text_follows_the_new_timing(self):
        """面板节奏跟着帧常量走：「灯火正旺」12 秒、（每 5 秒 1 次）；旧的 10 秒一个字都不许留。"""
        plan_cas = self.plan["texts"]["custom_ability_string"]
        texts = {k: K.rev4_panel_text(k, v["value"]) for k, v in plan_cas.items() if "value" in v}
        self.assertEqual(K.rev3_text_problems(texts), [])
        slot1, slot3 = texts[f"desc_override_{K.CODE}_1"], texts[K.SLOT3_OVERRIDE_KEY]
        self.assertIn(f"赋予自身「灯火正旺」{K.LAMP_SECONDS}秒", slot1)
        self.assertIn(f"（每{K.CT_SECONDS}秒1次）", slot1)
        self.assertIn(f"（每{K.CT_SECONDS}秒1次）", slot3)
        self.assertEqual(sum(t.count("10秒") for t in texts.values()), 0)
        self.assertEqual(sum(t.count("无上限") for t in texts.values()), 0)      # 第二轮规则①仍然成立
        for key in (f"desc_override_{K.CODE}_1", K.SLOT3_OVERRIDE_KEY):
            self.assertEqual(K.panel_text_problems(texts[key], key), [], key)
        # 上一轮的文案（只过 rev2）必须被判红：这条保证「面板忘了改」不会蒙混过关
        rev2_only = K._rewrite_once(f"desc_override_{K.CODE}_1", plan_cas[f"desc_override_{K.CODE}_1"]["value"],
                                    K.REV2_TEXT_REWRITES, "revision2")
        self.assertTrue(K.rev3_text_problems({f"desc_override_{K.CODE}_1": rev2_only}))
        self.assertTrue(K.panel_text_problems(rev2_only, f"desc_override_{K.CODE}_1"))
        # 改写源必须恰好命中一次
        with self.assertRaises(K.KitError):
            K.rev4_panel_text(K.SLOT3_OVERRIDE_KEY, "没有那段话")

    # ---- 第四轮作者改版（revision3-20260916 续）：「能力 3 的 50% 降到 30%、灯芯每层 5% 降到 3%」
    def test_revision4_value_rows_are_exactly_the_two_spots_the_author_named(self):
        """先把能力1/3 里含 50% / 5% 的格逐条列出来，再判断哪几条是作者说的那两处。

        扫两键（能力1 / 能力3）全部记录的四个数值列（瞬发 c51/c52、持续 c113/c114）：
        命中 50000 / 5000 的共四行——改三行（能力3#0 全队光攻、能力3#3 强化弹射伤害、
        能力1#5 灯芯乘区），留一行（能力1#1 开局技能槽 50%，不是作者说的那两处）。
        """
        scan = K.rev4_value_scan(self.plan)
        self.assertEqual(scan["problems"], [])
        self.assertEqual([c["row"] for c in scan["changed"]],
                         [f"{K.CID}1#5", f"{K.CID}3#0", f"{K.CID}3#3"])
        self.assertEqual([c["row"] for c in scan["kept"]], [f"{K.CID}1#1"])
        self.assertTrue(scan["kept"][0]["reason"])                               # 不动的行必须附理由
        self.assertEqual(scan["scanned_cols"], [51, 52, 113, 114])
        self.assertEqual(scan["magnitudes"], ["50000", "5000"])
        # 改的三行：kind 与列位对得上（32 全队光攻 / 55 强化弹射伤害 / during 413 独立乘区）
        by_row = {c["row"]: c for c in scan["changed"]}
        self.assertEqual(by_row[f"{K.CID}3#0"]["kind_instant"], "32")
        self.assertEqual(by_row[f"{K.CID}3#3"]["kind_instant"], "55")
        self.assertEqual(by_row[f"{K.CID}1#5"]["kind_during"], "413")
        self.assertEqual(scan["kept"][0]["kind_instant"], "211")                 # 开局技能槽，不是这两处
        # 成品行：新值落地，两列拉平（固定覆盖文案只写一个数字）
        rows, evidence = K.build_rows(self.ctx, self.plan)
        self.assertEqual([rows["ability"][f"{K.CID}3"][i][c] for i in (0, 3) for c in (51, 52)],
                         [str(K.A3_LAMP_GAIN)] * 4)
        self.assertEqual([rows["ability"][f"{K.CID}1"][5][c] for c in (113, 114)],
                         [str(K.A1_WICK_MULT)] * 2)
        self.assertEqual((K.A3_LAMP_GAIN_PCT, K.A1_WICK_MULT_PCT), (30, 3))
        self.assertEqual((K.A3_LAMP_GAIN_PCT_REV3, K.A1_WICK_MULT_PCT_REV3), (50, 5))
        changes = K.rev4_row_changes(self.plan, rows["ability"])
        self.assertEqual(changes["problems"], [])
        self.assertEqual(changes["values"], {f"{K.CID}1": [5], f"{K.CID}3": [0, 3]})
        marked = {f'{e["key"]}#{e["record"]}' for e in evidence if e.get("revision4")}
        self.assertEqual(marked, {f"{K.CID}1#5", f"{K.CID}3#0", f"{K.CID}3#3"})
        # 作者没点名的同量级行一格未动：能力1#1 开局技能槽、能力2 / 能力6 的强化弹射伤害、
        # 能力4 的贯通期间增伤、能力5#1 的技能槽 5%、队长 L3 每 35 连击 +50%
        self.assertEqual(rows["ability"][f"{K.CID}1"][1][51], "50000")
        self.assertEqual(rows["ability"][f"{K.CID}2"][0][51], "50000")
        self.assertEqual(rows["ability"][f"{K.CID}4"][0][113], "50000")
        self.assertEqual(rows["ability"][f"{K.CID}5"][1][51], "5000")
        self.assertEqual(rows["ability"][f"{K.CID}6"][1][51], "50000")
        self.assertEqual(rows["leader"][3][49], "50000")
        self.assertEqual(rows["leader"], [e["row"] for e in self.plan["tables"]["leader_ability"]["records"]])
        # 节奏与机制未动（第四轮只碰强度）
        self.assertEqual([rows["ability"][k][i][35] for k, i in K.REV3_CT_ROWS], [str(K.CT_LAMP_FRAMES)] * 4)
        self.assertEqual(rows["ability"][f"{K.CID}1"][5][102], "(None)")         # 灯芯触发上限仍无限
        # 负向对照
        with self.assertRaises(K.KitError):                                      # 名单内不是上一轮的值
            K.apply_rev4_values(f"{K.CID}3", 0, ["x"] * 51 + ["7", "7"] + ["y"] * 73, "neg")
        with self.assertRaises(K.KitError):                                      # 名单外冒出同量级的值
            K.apply_rev4_values(f"{K.CID}1", 0, ["x"] * 51 + ["50000", "50000"] + ["y"] * 73, "neg")
        with self.assertRaises(K.KitError):                                      # 比例除不尽 → 报错不取整
            K.rev4_scaled_pair(["50001", "50000"], K.A3_LAMP_GAIN_REV3, K.A3_LAMP_GAIN, "neg")
        self.assertEqual(K.rev4_scaled_pair(["25000", "50000"], 50000, 30000, "ok"), ["15000", "30000"])
        half = {k: [list(r) for r in lines] for k, lines in rows["ability"].items()}
        half[f"{K.CID}3"][0][51] = str(K.A3_LAMP_GAIN_REV3)                      # 漏改一列
        self.assertTrue(K.rev4_row_changes(self.plan, half)["problems"])
        stray = {k: [list(r) for r in lines] for k, lines in rows["ability"].items()}
        stray[f"{K.CID}2"][0][51] = "30000"                                      # 改到名单外的行
        self.assertTrue(K.rev4_row_changes(self.plan, stray)["problems"])
        bad_plan = copy.deepcopy(self.plan)                                      # plan 里冒出没判断过的 50000
        bad_plan["tables"]["ability"]["keys"][f"{K.CID}3"][4]["row"][113] = "50000"
        self.assertTrue(K.rev4_value_scan(bad_plan)["problems"])
        with self.assertRaises(K.KitError):
            K.build_rows(self.ctx, bad_plan)

    def test_revision4_panel_numbers_come_from_the_rows(self):
        """面板两处数字 = 装包那一行的数值列 ÷ 1000；旧数字一个不许留，别家键的 50% 不许误伤。"""
        rows, _ = K.build_rows(self.ctx, self.plan)
        plan_cas = self.plan["texts"]["custom_ability_string"]
        texts = {k: K.rev4_panel_text(k, v["value"]) for k, v in plan_cas.items() if "value" in v}
        self.assertEqual(K.rev4_text_problems(texts), [])
        self.assertEqual(K.panel_matches_row_values(rows["ability"], texts), [])
        slot1, slot3 = texts[f"desc_override_{K.CODE}_1"], texts[K.SLOT3_OVERRIDE_KEY]
        self.assertIn(f"光属性角色攻击力＋{K.A3_LAMP_GAIN_PCT}%、强化弹射伤害＋{K.A3_LAMP_GAIN_PCT}%", slot3)
        self.assertIn(f"强化弹射伤害额外乘区＋{K.A1_WICK_MULT_PCT}%（「灯芯」最多99层）", slot1)
        self.assertNotIn("＋50%、强化弹射伤害＋50%", slot3)
        self.assertNotIn("额外乘区＋5%", slot1)
        for key in (f"desc_override_{K.CODE}_1", K.SLOT3_OVERRIDE_KEY):
            self.assertEqual(K.panel_text_problems(texts[key], key), [], key)
        # 上一轮的节奏与上限写法仍然成立（第四轮只改数字）
        self.assertIn(f"「灯火正旺」{K.LAMP_SECONDS}秒", slot1)
        self.assertIn(f"（每{K.CT_SECONDS}秒1次）", slot3)
        # 别家键的 50% 没被误伤：能力1 开局技能槽、能力2、能力6、队长覆盖
        self.assertIn("战斗开始时，自身技能槽＋50%", slot1)
        self.assertIn("强化弹射伤害＋50%", texts[f"desc_override_{K.CODE}_2"])
        self.assertIn("强化弹射伤害＋50%", texts[f"desc_override_{K.CODE}_6"])
        self.assertIn("每达成35连击，强化弹射伤害＋50%", texts[K.LEADER_OVERRIDE_KEY])
        # 负向对照：面板留旧数字 / 行与面板对不上 / 两列不拉平
        stale = dict(texts, **{K.SLOT3_OVERRIDE_KEY: plan_cas[K.SLOT3_OVERRIDE_KEY]["value"]})
        self.assertTrue(K.rev4_text_problems(stale))
        self.assertTrue(K.panel_matches_row_values(rows["ability"], stale))
        moved = {k: [list(r) for r in lines] for k, lines in rows["ability"].items()}
        moved[f"{K.CID}1"][5][113] = moved[f"{K.CID}1"][5][114] = "20000"        # 行改了文案没改
        self.assertTrue(K.panel_matches_row_values(moved, texts))
        unflat = {k: [list(r) for r in lines] for k, lines in rows["ability"].items()}
        unflat[f"{K.CID}3"][0][51] = "10000"                                     # 两列不拉平
        self.assertTrue(K.panel_matches_row_values(unflat, texts))
        with self.assertRaises(K.KitError):                                      # 改写源必须恰好命中一次
            K.rev4_panel_text(K.SLOT3_OVERRIDE_KEY, "没有那段话")

    def test_power_up_string_is_rewritten_for_the_new_pf_buff(self):
        """审查修复轮 R4：536 的「强化」后缀来自 custom_ability_power_up_string，本轮必须同步。"""
        import wf_seasonal7_tables as T
        donor = self.ctx.pack.template_raw(K.CAPS)[f"change_skill_{K.TEMPLATE_CODE}"]
        self.assertEqual(T.decode_blob(donor), {str(lv): "攻击力提升效果强化" for lv in range(2, 7)})
        out = K.power_up_blob(donor, self.plan)
        text = T.decode_blob(out)
        self.assertEqual(sorted(text), [str(lv) for lv in range(2, 7)])
        for lv, value in text.items():
            self.assertIn("强化弹射伤害提升效果强化", value, lv)
            self.assertIn("攻击力提升效果强化", value, lv)
        self.assertEqual(text, self.plan["texts"]["custom_ability_power_up_string"]
                         [K.CHANGE_SKILL_KEY]["value"])
        # 负向对照：donor 漂移 / 计划写成逐档不同 / 空改 都必须报
        plan = copy.deepcopy(self.plan)
        plan["texts"]["custom_ability_power_up_string"][K.CHANGE_SKILL_KEY]["old"]["2"] = "别的"
        with self.assertRaises(K.KitError):
            K.power_up_blob(donor, plan)
        plan = copy.deepcopy(self.plan)
        plan["texts"]["custom_ability_power_up_string"][K.CHANGE_SKILL_KEY]["value"]["3"] = "另一档"
        with self.assertRaises(K.KitError):
            K.power_up_blob(donor, plan)
        plan = copy.deepcopy(self.plan)
        item = plan["texts"]["custom_ability_power_up_string"][K.CHANGE_SKILL_KEY]
        item["value"] = dict(item["old"])
        with self.assertRaises(K.KitError):
            K.power_up_blob(donor, plan)
        plan = copy.deepcopy(self.plan)
        plan["texts"]["custom_ability_power_up_string"][K.CHANGE_SKILL_KEY]["action"] = "unchanged"
        self.assertEqual(K.power_up_blob(donor, plan), donor)                  # 幂等/可回退

    # ---- PF
    def _pf_tree(self, level, sources):
        tree, info = K.compose_pf(level, sources)
        tree = K.add_blaze_layer(tree, level, FAMILIES["pf_blaze"])
        for sub in ("pf_spin", "pf_support", "pf_blaze"):
            tree, refs = self.ctx.rewrite_effect_refs(tree, FAMILIES[sub], strict=True)
            self.assertEqual(refs["kept_donor"], [])
        return tree, info

    def test_pf_trees_apply_controller_overrides(self):
        try:
            sources, _apk = K.apk_pf_sources(self.ctx.root)
        except K.KitError as exc:
            self.skipTest(str(exc))
        for level in (1, 2, 3):
            tree, _info = self._pf_tree(level, sources)
            expect = K.expected_pf_tree(self.ctx.root, level, FAMILIES["pf_blaze"]["dst_dir"])
            self.assertIsNone(K.first_difference(tree, expect))
            blk = tree[11][1]
            off = K.PF_OFFICIAL[level]
            hit = K.cmd(blk[1])
            cna = K.cmd(hit[23][1][0])
            self.assertEqual(K.cmd(blk[0])[1], off["supp"])                       # suppress 官方
            self.assertEqual((hit[13][1], hit[14][1]), (3 * off["life"], 3 * off["hits"]))
            self.assertEqual(blk[2][1][1], 3 * off["life"] - 1)                    # Wait → NotifyPowerflipEnd
            self.assertEqual(cna[6], K.slv(off["mult"]))                           # 每段倍率 = 官方
            self.assertEqual(hit[24], 0)                                           # PF 乘区归属保持
            layers = [K.cmd(n) for n in hit[20][1]]
            self.assertEqual([c[0] for c in layers], ["ShowEffect", "ShowEffect"])
            blaze, spin = layers
            self.assertTrue(blaze[2][1].endswith(f"/{K.CODE}/pf_blaze/{K.PF_BLAZE_BASE}"))
            self.assertIn(f"/{K.CODE}/pf_spin/powerflip_attack_spin_", spin[2][1])
            self.assertEqual((blaze[3], blaze[5], blaze[6]), (spin[3], ["UntilTargetTerminates"], ["AB"]))
            checks = K.dsl_problems(self.ctx.root, tree)
            self.assertTrue(checks["all_empty"], checks["problems"])
            self.assertTrue(checks["roundtrip"])
            regressed = copy.deepcopy(tree)                                         # 设计原倍率 = 覆盖回退
            K.cmd(K.cmd(regressed[11][1][1])[23][1][0])[6] = K.slv(K.DESIGN_PF_SEGMENT_MULTIPLIER[level])
            self.assertIsNotNone(K.first_difference(regressed, expect))
            with self.assertRaises(K.KitError):                                     # 预算断言：剑士段不再是 3 倍
                K.pf_budget_report(level, regressed, sources)

    def test_pf_budget_matches_review_arithmetic(self):
        try:
            sources, _apk = K.apk_pf_sources(self.ctx.root)
        except K.KitError as exc:
            self.skipTest(str(exc))
        want = {1: dict(knight=(29.25, 9.75), total=(29.25, 9.75), brk=(6.75, 4.5), fev=(18, 18)),
                2: dict(knight=(57.0, 19.0), total=(57.0, 19.0), brk=(12.0, 8.0), fev=(24, 24)),
                3: dict(knight=(94.5, 31.5), total=(98.5, 35.5), brk=(23.5, 16.0), fev=(46, 41))}
        budgets = {}
        for level in (1, 2, 3):
            tree, _ = self._pf_tree(level, sources)
            b = K.pf_budget_report(level, tree, sources)
            budgets[level] = b
            w = want[level]
            self.assertAlmostEqual(b["knight"]["new"]["damage"], w["knight"][0])
            self.assertAlmostEqual(b["knight"]["official"]["damage"], w["knight"][1])
            self.assertAlmostEqual(b["total"]["new"]["damage"], w["total"][0])
            self.assertAlmostEqual(b["total"]["official"]["damage"], w["total"][1])
            self.assertAlmostEqual(b["total"]["new"]["break"], w["brk"][0])
            self.assertAlmostEqual(b["total"]["official"]["break"], w["brk"][1])
            self.assertAlmostEqual(b["total"]["new"]["fever"], w["fev"][0])
            self.assertAlmostEqual(b["total"]["official"]["fever"], w["fev"][1])
            self.assertEqual(b["ratio"]["knight_damage"], 3.0)
        self.assertEqual(budgets[3]["ratio"]["total_damage"], 2.7746)
        note = K.pf_budget_note(budgets)
        self.assertIn("2.77", note)
        self.assertNotIn("3 倍总伤", note)

    def test_dsl_checker_negative_controls(self):
        tree, _ = K.compose_skill(self.ctx, 1, self._sources())
        bad = copy.deepcopy(tree)
        K.find_cmd(bad, "AddCombo")[1] = 15                                         # F1034：Array 参给标量
        self.assertTrue(K.dsl_problems(self.ctx.root, bad)["problems"]["typed_signature"])
        bad = copy.deepcopy(tree)                                                  # F1009：Block 内 DoNothing
        bad[11][1].append(["Command", ["ConditionalsFeverMode", ["Block", [["DoNothing"]]], ["Block", []]]])
        probs = K.dsl_problems(self.ctx.root, bad)["problems"]
        self.assertTrue(probs["donothing_in_block"] or probs["typed_signature"])
        bad = copy.deepcopy(tree)                                                  # C16103：未绑定 subject
        K.find_cmd(bad, "ShowEffect")[3] = 777
        probs = K.dsl_problems(self.ctx.root, bad)["problems"]
        self.assertTrue(probs["blueprint_check"] or probs["subject_binding"])


class PfBudgetSyntheticTest(unittest.TestCase):
    """纯数据：同一判定区多条攻击都要乘命中数；不建模的攻击种类与非 MaxNumOfHits 命中数直接报错。"""

    @staticmethod
    def _cna(mult, brk, fev):
        # wf_dsl_sig：p1 int, p2 int, p3/p4 Array, p5 int, p6 倍率, p7 Array, p8-12 Boolean, p13 削韧, p14 Fever
        return ["Command", ["CreateNormalAttack", 1, 0, [], [], 0, K.slv(mult), K.slv(1), False, False, False, False,
                            False, K.slv(brk), K.slv(fev), ["None"], False]]

    @staticmethod
    def _area(subject, hits, attacks, hit_form="CalculatedUsingMaxNumOfHits"):
        return ["Command", ["CreateHitArea", "*", subject, ["CD"], 0, 0, 0.0, True, False, ["Circle", K.slv(10)],
                            ["Center"], ["Bottom"], ["Single"], ["SpecifyHitAreaLifetimeDirectly", 30],
                            [hit_form, hits], ["None"], False, True, ["None"], 90, ["Block", []], 91, 92,
                            ["Block", attacks], 0, 0, ["None"]]]

    def test_multiple_attacks_and_areas(self):
        tree = ["ActionDsl", 1, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                ["Block", [self._area(-18, 4, [self._cna(2.0, 0.5, 1), self._cna(1.0, 0.25, 2)]),
                           self._area(-17, 1, [self._cna(4.0, 1, 1)]),
                           self._area(-17, 7, [])]]]
        got = K.pf_attack_budget(tree)
        self.assertEqual([(e["subject"], e["hits"], e["damage"], e["break"], e["fever"]) for e in got],
                         [(-18, 4, 12.0, 3.0, 12.0), (-17, 1, 4.0, 1.0, 1.0)])

    def test_unmodelled_forms_raise(self):
        bad_hits = ["ActionDsl", 1, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                    ["Block", [self._area(-18, 4, [self._cna(2.0, 0.5, 1)], hit_form="Unlimited")]]]
        with self.assertRaises(K.KitError):
            K.pf_attack_budget(bad_hits)
        ratio = ["ActionDsl", 1, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                 ["Block", [self._area(-18, 1, [["Command", ["CreateRatioAttack", 1, 2, 0.05]]])]]]
        with self.assertRaises(K.KitError):
            K.pf_attack_budget(ratio)


class PortedBlueprintCheckTest(unittest.TestCase):
    """移植版 blueprint_check_with_sig 与 research/_tmp/blueprint_build.check 逐字等价（原模块不在时跳过）。"""

    def test_ported_checker_matches_design_blueprint(self):
        root = HERE.parents[1]
        original = root / K.DESIGN_BLUEPRINT_REL
        if not original.is_file():
            self.skipTest("research/_tmp/blueprint_build.py not present")
        try:
            ctx = _context()
        except Exception as exc:
            self.skipTest(f"live store unavailable: {exc}")
        trees = []
        for logical in K.program_logicals(ctx):
            path = ctx.pack.pkg_path("common", logical)
            if path.is_file():
                trees.append(ctx.amf_parse(path.read_bytes()))
        for name in K.SKILL_SOURCES:
            trees.append(K.load_program(ctx, name)[0])
        base = copy.deepcopy(K.load_program(ctx, "guildknight_leader_1")[0])
        injected_hit_area = ["Command", ["CreateHitArea", "*", -18, ["CD"], 0, 0, 0.0, True, False,
                                         ["Rectangle", K.slv(10)], ["Center"], ["Bottom"], ["Single"],
                                         ["SpecifyHitAreaLifetimeDirectly", 5], ["CalculatedUsingMaxNumOfHits", 1],
                                         ["None"], False, True, ["None"], 90, ["Block", []], 91, 92, ["Block", []],
                                         0, 0, ["None"]]]
        for mutate in (lambda t: K.find_cmd(t, "ShowEffect").__setitem__(3, 777),
                       lambda t: K.find_cmd(t, "AddCombo").__setitem__(1, 15),
                       lambda t: t[11][1].append(copy.deepcopy(injected_hit_area))):
            bad = copy.deepcopy(base)
            mutate(bad)
            trees.append(bad)
        off, _src = K.load_official_sig(root)
        ported = [list(K.blueprint_check_with_sig(t, off)) for t in trees]
        self.assertTrue(all(p[0] for p in ported[-3:]), "negative injections must produce problems")
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "trees.json"
            dst = Path(tmp) / "out.json"
            src.write_text(json.dumps(trees, ensure_ascii=False), encoding="utf-8")
            script = ("import sys, json; sys.path.insert(0, %r); import blueprint_build as BP; "
                      "trees = json.load(open(%r, encoding='utf-8')); "
                      "json.dump([list(BP.check(t)) for t in trees], open(%r, 'w', encoding='utf-8'), ensure_ascii=False)"
                      % (str(original.parent), str(src), str(dst)))
            proc = subprocess.run([sys.executable, "-c", script], cwd=str(root), capture_output=True, timeout=300)
            self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace")[-800:])
            expect = json.loads(dst.read_text(encoding="utf-8"))
        self.assertEqual(len(expect), len(trees))
        for i, (a, b) in enumerate(zip(ported, expect)):
            self.assertEqual(a, b, f"tree #{i}")


class OfficialSigAndInputsTest(unittest.TestCase):
    def setUp(self):
        K._OFFICIAL_SIG_CACHE.clear()

    def tearDown(self):
        K._OFFICIAL_SIG_CACHE.clear()

    def test_missing_and_drifted_signature_table_is_reported(self):
        real_root = HERE.parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            probs = K.official_sig_problems(root)
            self.assertEqual(len(probs), 2)
            self.assertTrue(all("missing" in p for p in probs))
            with self.assertRaises(K.KitError) as cm:
                K.load_official_sig(root)
            self.assertIn("official_sig.py", str(cm.exception))
            inputs = K.required_input_problems(root)
            self.assertTrue(any("official_sig" in p for p in inputs))
            self.assertTrue(any(K.DESIGN_REL in p for p in inputs))
            drifted = root / K.OFFICIAL_SIG_CANDIDATES[0]
            drifted.parent.mkdir(parents=True)
            drifted.write_text("{}", encoding="utf-8")
            self.assertTrue(any("!= pin" in p for p in K.official_sig_problems(root)))
            with self.assertRaises(K.KitError):
                K.load_official_sig(root)
            fallback = real_root / K.OFFICIAL_SIG_CANDIDATES[1]
            if fallback.is_file() and K.sha256(fallback.read_bytes()) == K.OFFICIAL_SIG_PIN:
                good = root / K.OFFICIAL_SIG_CANDIDATES[1]
                good.parent.mkdir(parents=True, exist_ok=True)
                good.write_bytes(fallback.read_bytes())
                self.assertEqual(K.official_sig_problems(root), [])
                table, source = K.load_official_sig(root)
                self.assertEqual(source, K.OFFICIAL_SIG_CANDIDATES[1])
                self.assertIn("CreateHitArea#2", table)


class PfProgramPathTest(unittest.TestCase):
    def test_short_program_paths_fit_framework_inspect_copy(self):
        import wf_dsl
        import wf_seasonal7_common as C
        import wf_seasonal7_specs as S
        self.assertEqual(K.pf_program(1), "battle/action/power_flip/action/override/"
                                          "guildknight_leader_tavern_pf$guildknight_leader_tavern_pf_lv1")
        self.assertNotEqual(K.pf_program(1), K.design_pf_program(1))
        self.assertIn(K.PF_KEY, K.design_pf_program(3))
        pack = C.S7Pack(S.get_spec(K.KEY))
        short = tuple(f"package/roots/common/{wf_dsl.dsl_logical(K.pf_program(lv))}" for lv in (1, 2, 3))
        long = tuple(f"package/roots/common/{wf_dsl.dsl_logical(K.design_pf_program(lv))}" for lv in (1, 2, 3))
        with tempfile.TemporaryDirectory() as tmp:
            empty_ws = Path(tmp) / pack.workspace.name
            empty_ws.mkdir()
            ok = K.workspace_path_budget(empty_ws, pack.batch_dir, extra_rel=short)
            bad = K.workspace_path_budget(empty_ws, pack.batch_dir, extra_rel=long)
            excluded = K.workspace_path_budget(empty_ws, pack.batch_dir, extra_rel=short + long, exclude_rel=())
        # 同一副本前缀下估算：短路径有余量，设计长路径必然超限（负向对照，证明检查不空转）
        self.assertEqual(ok["copy_prefix"], bad["copy_prefix"])
        self.assertGreaterEqual(ok["headroom"], 0, ok)
        self.assertLess(bad["headroom"], 0, bad)
        self.assertLess(excluded["headroom"], 0, excluded)
        if pack.workspace.is_dir():
            real = K.workspace_path_budget(pack.workspace, pack.batch_dir,
                                           exclude_rel=long)
            self.assertGreaterEqual(real["headroom"], 0, real)

    def test_drop_stale_pf_programs_only_touches_kit_outputs(self):
        import wf_dsl

        class FakePack:
            def __init__(self, base: Path):
                self.base = base

            def pkg_path(self, root, logical):
                return self.base / "roots" / root / logical

            def _owned_raw(self):
                path = self.base / "owned_outputs.json"
                return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}

            def write_evidence(self, name, value):
                (self.base / name).write_text(json.dumps(value), encoding="utf-8")

        class FakeCtx:
            def __init__(self, pack):
                self.pack = pack

        with tempfile.TemporaryDirectory() as tmp:
            pack = FakePack(Path(tmp))
            owned = {}
            for lv in (1, 2, 3):
                old = wf_dsl.dsl_logical(K.design_pf_program(lv))
                path = pack.pkg_path("common", old)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"x")
                owned[f"common:{old}"] = {"owner": "kit", "sha256": None}
            owned["common:battle/other.png"] = {"owner": "art", "sha256": None}
            pack.write_evidence("owned_outputs.json", owned)
            removed = K.drop_stale_pf_programs(FakeCtx(pack))
            self.assertEqual(len(removed), 3)
            self.assertEqual(list(pack._owned_raw()), ["common:battle/other.png"])
            self.assertFalse(any(pack.pkg_path("common", r).exists() for r in removed))
            self.assertEqual(K.drop_stale_pf_programs(FakeCtx(pack)), [])             # 幂等
            old = wf_dsl.dsl_logical(K.design_pf_program(2))
            pack.pkg_path("common", old).write_bytes(b"y")
            pack.write_evidence("owned_outputs.json", {f"common:{old}": {"owner": "effects", "sha256": None}})
            with self.assertRaises(K.KitError):
                K.drop_stale_pf_programs(FakeCtx(pack))
            self.assertTrue(pack.pkg_path("common", old).exists())


class FxManifestHookTest(unittest.TestCase):
    def test_manifest_shapes_and_missing_png(self):
        from PIL import Image
        import wf_assets
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / Path(K.FX_MANIFEST_REL).parent
            out.mkdir(parents=True)
            buf = io.BytesIO()
            Image.new("RGBA", (4, 4), (200, 100, 50, 128)).save(buf, format="PNG")
            (out / "blaze.png").write_bytes(wf_assets.png_encode(buf.getvalue()))
            src = "battle/effect/skill_unique/master_knight/master_knight.png"
            self.assertEqual(K.load_fx_manifest(root), ({}, None))
            for payload in ({src: "blaze.png", "not/an/effect.png": "blaze.png"},
                            {"sheets": {src: str(out / "blaze.png")}},
                            {"sheets": [{"source": src, "png": "blaze.png"}]}):
                (out / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")
                mapping, info = K.load_fx_manifest(root)
                self.assertEqual(list(mapping), [src])
                self.assertEqual(mapping[src].read_bytes()[:8], b"\x89png\r\n\x1a\n")
                self.assertEqual(info["entries"], 1)
            (out / "manifest.json").write_text(json.dumps({src: "gone.png"}), encoding="utf-8")
            with self.assertRaises(K.KitError):
                K.load_fx_manifest(root)


class GatesStatusTest(unittest.TestCase):
    def test_ready_only_with_passing_gates_and_matching_fingerprint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(K.gates_status(root, "abc")[0], "draft")
            path = root / K.GATES_REL
            path.parent.mkdir(parents=True)
            for payload, want in (({"all_pass": False, "kit_fingerprint": "abc"}, "draft"),
                                  ({"all_pass": True, "kit_fingerprint": "zzz"}, "draft"),
                                  ({"all_pass": True, "kit_fingerprint": "abc"}, "ready-for-review")):
                path.write_text(json.dumps(payload), encoding="utf-8")
                self.assertEqual(K.gates_status(root, "abc")[0], want)
            path.write_text("{not json", encoding="utf-8")
            self.assertEqual(K.gates_status(root, "abc")[0], "draft")


class PixelInputsTest(unittest.TestCase):
    """像素装包闸门：产物缺失 / report 门禁不过 / 复核缺失 / sha 漂移都判 pending（不写包）。"""

    def _write(self, root: Path, *, gates_ok=True, review_pass=True, drift=None):
        import hashlib
        base = root / K.PIXEL_DIR_REL
        (base / "out").mkdir(parents=True)
        outputs, detail = {}, {}
        for name in K.PIXEL_SHEETS:
            data = f"png-{name}".encode()
            (base / "out" / f"{name}.png").write_bytes(data)
            digest = hashlib.sha256(data).hexdigest()
            outputs[name] = {"sha256": digest}
            detail[name] = {"sha256": digest}
        if drift:
            (base / "out" / f"{drift}.png").write_bytes(b"changed")
        (base / "report.json").write_text(json.dumps({
            "key": K.KEY, "gates_passed": gates_ok, "gates": {"G1": {"ok": gates_ok}}, "outputs": outputs}),
            encoding="utf-8")
        verify = root / K.PIXEL_VERIFY_REL
        verify.parent.mkdir(parents=True, exist_ok=True)
        verify.write_text(json.dumps({K.KEY: {"pass": review_pass, "hard": {
            "H1": {"ok": review_pass}, "H8_png_roundtrip": {"ok": True, "detail": detail}}}}), encoding="utf-8")

    def test_ready_and_pending_cases(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertTrue(K.pixel_inputs(root)[1])                      # 缺 report
        for kwargs, ready in (({}, True), ({"gates_ok": False}, False), ({"review_pass": False}, False),
                              ({"drift": "special_sprite_sheet"}, False)):
            with self.subTest(**kwargs), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self._write(root, **kwargs)
                pngs, probs = K.pixel_inputs(root)
                self.assertEqual(not probs, ready, probs)
                if ready:
                    self.assertEqual(sorted(pngs), sorted(K.PIXEL_SHEETS))

    def test_install_pending_does_not_write(self):
        class Ctx:
            root = Path(tempfile.gettempdir()) / "zehr-pixel-absent-root"

            def write_asset(self, *a, **k):
                raise AssertionError("pending install must not write")
        self.assertEqual(K.install_pixel(Ctx())["status"], "pending")


if __name__ == "__main__":
    unittest.main()
