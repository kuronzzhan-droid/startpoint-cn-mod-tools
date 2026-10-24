# -*- coding: utf-8 -*-
"""斩铁·白梅 kit 的只读回归：改版行回放（第一轮 21 行 + 第二轮新增 1 条队长行 = 22 行）、
技能树拼装+改版 delta 与门禁、629 剑 PF 树、两轮文案改写与面板文案规则、作用域补充检查的阴性对照。

不写包、不写 live；需要本机 live store 与官方基线（.cdn/cn），缺失时跳过。
"""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
pass  # Imports resolve from this checkout/package, not external source copies.

import wf_seasonal7_kit_zantetsu as K  # noqa: E402

#: 泳装希尔媞灰服版（1.4.1054）发布前的 live 快照（平衡第三轮暂存 extra4/before）；本机没有时跳过对应测试。
PRE_1054_LIVE = HERE.parents[2] / "out" / "平衡调整批次-20260927" / "extra4" / "before" / "live" / "common"
PRE_1054_ABILITY = PRE_1054_LIVE / K.ABILITY
PRE_1054_LEADER = PRE_1054_LIVE / K.LEADER


def _context():
    import wf_seasonal7_build as B
    import wf_seasonal7_common as C
    import wf_seasonal7_specs as S
    spec = S.get_spec(K.KEY)
    pack = C.S7Pack(spec)
    if pack.official_read(K.ABILITY, "common") is None:
        raise unittest.SkipTest("official baseline unavailable")
    return B.KitContext(pack)


class ZantetsuKitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.ctx = _context()
        except unittest.SkipTest:
            raise
        except Exception as exc:                      # 没有 live profile 的机器
            raise unittest.SkipTest(f"live store unavailable: {exc}")
        cls.design, cls.plan = K.load_revised_design(cls.ctx.root)

    def test_spec_merges_texts_and_extra_keys(self):
        spec = self.ctx.spec
        self.assertEqual(spec.texts["title"], "白梅羽织的忍者武士")
        self.assertEqual(tuple(spec.required_capabilities), K.REQUIRED_CAPABILITIES)
        self.assertEqual(spec.extra_keys[K.CAS], K.CAS_KEYS)
        self.assertEqual(K.CAS_KEYS, (K.CAS_KEY, K.PF_CAS_KEY))
        self.assertEqual(spec.extra_keys[K.SWITCHED], (K.VOICE_READY,))

    def test_rows_replay_revision_plan(self):
        rows = K.revision_rows(self.ctx, self.plan)
        keys = self.plan["tables"][K.ABILITY]["keys"]
        self.assertEqual(len(rows["leader"]), 8)                      # = plan record_count_new（无客户端 6 行上限）
        self.assertLessEqual(len(rows["leader"]), K.RECORD_SANITY_CAP["leader_ability"])
        self.assertEqual(sum(len(v) for v in rows["abilities"].values()), 15)
        self.assertEqual({k: len(v) for k, v in rows["abilities"].items()},
                         {k: v["record_count_new"] for k, v in keys.items()})
        slot4 = rows["abilities"]["1599984"]                          # 上一轮的 F1/507 行，本轮不动
        self.assertEqual(slot4[0][47], "507")
        self.assertNotIn("112", [r[47] for r in slot4])
        for key, entry in keys.items():                               # 一键内 c1/c2 必须一致
            self.assertEqual({(r[1], r[2]) for r in rows["abilities"][key]},
                             {(entry["unisonable_c1"], entry["statue_group_c2"])})
        caps = set()
        for i, row in enumerate(rows["leader"]):
            gate = K.row_gate("leader_ability", row, set(K.CAS_KEYS))
            self.assertFalse(K._row_gate_failed(gate), gate)
            self.assertEqual(gate["describe"], self.plan["tables"][K.LEADER]["records"][i]["describe"])
            caps.update(gate["required_client_capabilities"])
        for key, lines in rows["abilities"].items():
            for i, row in enumerate(lines):
                gate = K.row_gate("ability", row, set(K.CAS_KEYS))
                self.assertFalse(K._row_gate_failed(gate), (key, gate))
                self.assertEqual(gate["describe"], keys[key]["records"][i]["describe"])
                caps.update(gate["required_client_capabilities"])
        self.assertEqual(sorted(caps), sorted(K.REQUIRED_CAPABILITIES))   # 本轮不新增补丁需求

    def test_revision_key_numbers(self):
        """作者点名的数值落在正确的列上（单位：1000=1%、100000=1 次/1 连击/1 帧）。"""
        rows = K.revision_rows(self.ctx, self.plan)
        lead = rows["leader"]
        blocks = K._block("leader_ability")
        it, ic = blocks["instant_trigger"], blocks["instant_content"]
        for row in lead[:2]:                                                   # L1/L2 成长形：每 30 连击，限 10 次
            self.assertEqual((row[3], row[it], row[it + 3], row[it + 4], row[it + 7]),
                             ("0", "12", "3000000", "3000000", "10"))
            self.assertEqual((row[ic + 1], row[ic + 2]), ("5", "White"))       # 赋予全队(光)
        self.assertEqual((lead[0][ic], lead[0][49], lead[0][50]), ("32", "25000", "33000"))   # 攻击力 25→33%
        self.assertEqual((lead[1][ic], lead[1][49], lead[1][50]), ("34", "30000", "40000"))   # 技能伤害 30→40%
        self.assertEqual((lead[2][49], lead[2][50]), ("22500", "30000"))       # L3 技能充能 22.5→30%
        self.assertEqual((lead[3][55], lead[3][56]), ("90000000", "90000000"))  # L4 贯穿 900 帧 = 15s
        self.assertEqual(lead[3][60], "(None)")                                # 弹射次数上限：不设
        self.assertEqual((lead[4][49], lead[4][50], lead[4][32]), ("5000", "10000", "(None)"))
        self.assertEqual((lead[5][49], lead[5][50]), ("25000", "50000"))
        # 第二轮新增的 L7：共鸣 + 技能槽因技能/能力上升（trigger 141，puller 0，阈值 ≥1）→ 自身技能伤害
        # 25%→50%，上限 20 次 ⇒ 满级累计 20×50% = 1000%（作者说的「最大 1000%」）
        self.assertEqual((lead[6][3], lead[6][it], lead[6][it + 1]), ("0", "141", "0"))
        self.assertEqual((lead[6][it + 3], lead[6][it + 4]), ("100000", "100000"))
        self.assertEqual((lead[6][it + 7], lead[6][it + 8]), ("20", "0"))          # 限 20 次、CT 0
        self.assertEqual((lead[6][ic], lead[6][ic + 1], lead[6][ic + 2]), ("34", "0", ""))   # 技能伤害 → 自身
        self.assertEqual((lead[6][49], lead[6][50]), ("25000", "50000"))
        self.assertEqual(int(lead[6][50]) * int(lead[6][it + 7]), 1000000)          # 50% × 20 = 1000%
        live_leader = self.ctx.csv_split(self.ctx.live_flat(K.LEADER)[K.CID])
        live_fever = [r for r in live_leader if r[3] == "1"]                        # L8 = live 上线的 Fever 行原样
        self.assertEqual(len(live_fever), 1)
        self.assertEqual(lead[7], live_fever[0])
        self.assertEqual((lead[7][3], lead[7][blocks["during_trigger"]]), ("1", "4"))
        a2 = rows["abilities"]["1599982"]
        self.assertEqual((a2[0][51], a2[0][52]), ("1000000", "1500000"))        # 连击 10→15
        self.assertEqual([r[34] for r in a2[1:]], ["5", "5"])                   # 攻击/技能伤害限 5 次
        a3 = rows["abilities"]["1599983"]
        self.assertEqual((a3[0][51], a3[0][52]), ("5000000", "10000000"))       # 连击 50→100
        self.assertEqual([r[34] for r in a3], ["(None)", "(None)", "(None)", "(None)"])   # 无上限
        for row in a3[1:]:
            self.assertEqual((row[30], row[31]), ("25000000", "25000000"))      # 每 250 连击
        self.assertEqual((a3[3][51], a3[3][52]), ("5000", "10000"))             # 694 独立乘区 5→10%
        a6 = rows["abilities"]["1599986"]
        self.assertEqual([(r[9], r[10], r[11]) for r in a6],                    # 都加了光共鸣前置
                         [("600000", "600000", "White")] * 2)
        self.assertEqual(a6[0][34], "(None)")

    def test_record_count_judge_is_plan_not_a_client_cap(self):
        """记录数判据是 plan 的 record_count_new，不是「客户端 6 行上限」（伪约束，已复审推翻）。

        live 队长表实测每键最多 15 条（169980）、词条最多 14 条（1699951），官方基线队长最多 8 条；
        杰拉德 149999 的 9 行队长技已真机验证。本测试锁住：7 行队长可以过，
        与 record_count_new 不一致才红。"""
        import copy
        plan = copy.deepcopy(self.plan)
        lead = plan["tables"][K.LEADER]
        self.assertEqual(lead["record_count_new"], 8)
        self.assertEqual(len(K.revision_rows(self.ctx, plan)["leader"]), 8)
        self.assertGreaterEqual(K.RECORD_SANITY_CAP["leader_ability"], 15)
        self.assertGreaterEqual(K.RECORD_SANITY_CAP["ability"], 14)
        lead["record_count_new"] = 7                      # 阴性对照：施工单与实际行数不一致必须红
        with self.assertRaises(K.KitError):
            K.revision_rows(self.ctx, plan)

    def test_revision_texts_applied(self):
        desc = self.plan["texts"][K.TEXT_PLAN_KEY]["new"]
        self.assertEqual(K.TEXTS["desc1"], desc)
        self.assertEqual(K.TEXTS["desc2"], desc)
        self.assertLess(len(desc), len(self.plan["texts"][K.TEXT_PLAN_KEY]["old"]))
        row = self.design["text"]["character_text_row"]
        self.assertEqual([row[5], row[7]], [desc, desc])
        for level in ("1", "2"):
            self.assertEqual(self.design["skills"]["action_skill_rows"][f"inner_{level}"]["1"], desc)
        cas = {c["key"]: c["value"] for c in self.design["custom_strings"] if c["table"] == K.CAS}
        self.assertEqual(sorted(cas), sorted(K.CAS_KEYS))
        cas2 = (self.plan["revision2"]["texts"] or {})["custom_ability_string"]
        for key in K.CAS_KEYS:
            want = cas2[key]["new"] if key in cas2 else self.plan["texts"]["custom_ability_string"][key]["new"]
            self.assertEqual(cas[key], want)
        for value in list(cas.values()) + [desc]:                # 面板禁恒真 HP 文案
            self.assertNotIn("生命值", value)

    def test_revision2_delta_anchors_and_negatives(self):
        """第二轮增量施工单：插入位置双锚定 + donor 重锚 + 计数一致，任一条漂了都必须红。"""
        plan1 = json.loads((self.ctx.root / K.REVISION_REL).read_text(encoding="utf-8"))
        plan2 = json.loads((self.ctx.root / K.REVISION2_REL).read_text(encoding="utf-8"))
        lead2 = plan2["tables"][K.LEADER]
        self.assertEqual((lead2["record_count_old"], lead2["record_count_new"]), (7, 8))
        self.assertEqual(len(lead2["inserts"]), 1)
        ins = lead2["inserts"][0]
        self.assertEqual((ins["position"], ins["after_id"], ins["before_id"]), (7, "L6", "L7"))
        self.assertEqual(ins["record"]["row_final"],
                         K.apply_revision2(plan1, plan2)["tables"][K.LEADER]["records"][6]["row_final"])
        # 阴性对照 1：插入锚点写错 → 必须红（不能默默插错位置）
        bad = copy.deepcopy(plan2)
        bad["tables"][K.LEADER]["inserts"][0]["after_id"] = "L5"
        with self.assertRaises(K.KitError):
            K.apply_revision2(plan1, bad)
        # 阴性对照 2：记录数对不上 → 必须红
        bad = copy.deepcopy(plan2)
        bad["tables"][K.LEADER]["record_count_new"] = 9
        with self.assertRaises(K.KitError):
            K.apply_revision2(plan1, bad)
        # 阴性对照 3：donor 重锚的 old 值写错 → 必须红
        bad = copy.deepcopy(plan2)
        bad["donor_retargets"][0]["row_index_old"] = 5
        with self.assertRaises(K.KitError):
            K.apply_revision2(plan1, bad)

    def test_donor_retargets_survive_round1_publish(self):
        """第一轮已在 1.4.878 发布，3 条自引用 live 的 donor 必须靠重锚才能回放。

        阴性对照：去掉重锚 → 这 3 条一定红（说明重锚不是摆设）。"""
        plan1 = json.loads((self.ctx.root / K.REVISION_REL).read_text(encoding="utf-8"))
        plan2 = json.loads((self.ctx.root / K.REVISION2_REL).read_text(encoding="utf-8"))
        self.assertEqual({(r["table"], r.get("key"), r["record_id"]) for r in plan2["donor_retargets"]},
                         {(K.LEADER, None, "L7"), (K.ABILITY, "1599986", "A6#1"), (K.ABILITY, "1599986", "A6#2")})
        self.assertEqual(plan2["donor_retargets"][0]["row_index_new"], K.MATCH_ROW_FINAL)
        no_retarget = copy.deepcopy(plan2)
        no_retarget["donor_retargets"] = []
        merged = K.apply_revision2(plan1, no_retarget)
        donors = K._Donors(self.ctx)
        fever = merged["tables"][K.LEADER]["records"][7]
        with self.assertRaises(K.KitError):
            K.replay_row(donors, K._revision_record(fever), "leader_ability")
        for rec in merged["tables"][K.ABILITY]["keys"]["1599986"]["records"]:
            with self.assertRaises(K.KitError):
                K.replay_row(donors, K._revision_record(rec), "ability")

    def test_frozen_donor_replays_without_reading_live(self):
        """泳装希尔媞 1.4.1054 换成灰服版后 live 1499963 第 1 行不再是 694 行：A3#4 的 donor 钉成冻结行，回放不随 live 变。"""
        abilities = self.plan["tables"][K.ABILITY]["keys"]
        frozen = [(key, rec["id"]) for key, entry in abilities.items() for rec in entry["records"]
                  if K.donor_pin(rec, "ability") in K.FROZEN_DONORS]
        frozen += [(K.CID, rec["id"]) for rec in self.plan["tables"][K.LEADER]["records"]
                   if K.donor_pin(rec, "leader_ability") in K.FROZEN_DONORS]
        self.assertEqual([("1599983", "A3#4")], frozen)
        rec = abilities["1599983"]["records"][3]
        self.assertEqual(rec["donor"], "live:ability:1499963#1")
        row = K.frozen_donor_row(K.FROZEN_DONORS[K.donor_pin(rec, "ability")], rec["donor"])
        for col, before in rec["edits_before_on_donor"].items():      # 冻结行就是 plan 记下的改前 donor
            self.assertEqual(row[int(col)], before, col)
        rows = K.revision_rows(self.ctx, self.plan)
        self.assertEqual(rows["abilities"]["1599983"][3], rec["row_final"])
        self.assertEqual([("1599983", 4)], [(r["key"], r["record"]) for r in rows["records"] if "donor_frozen" in r])
        self.assertFalse([r for r in rows["leader_records"] if "donor_frozen" in r])

        ctx = self.ctx

        class NoSwimLive:                                   # live 里干脆没有泳装希尔媞能力3：冻结 donor 不受影响
            def __getattr__(self, name):
                return getattr(ctx, name)

            def live_flat(self, logical):
                flat = dict(ctx.live_flat(logical))
                if logical == K.ABILITY:
                    flat.pop("1499963", None)
                return flat
        self.assertEqual({k: rows[k] for k in ("leader", "abilities")},
                         {k: K.revision_rows(NoSwimLive(), self.plan)[k] for k in ("leader", "abilities")})

        # 阴性对照：去掉冻结 → 按行号读当前 live（灰服版）必红；未冻结的 live donor 仍照常读表。
        saved = dict(K.FROZEN_DONORS)
        try:
            K.FROZEN_DONORS.clear()
            live = self.ctx.live_flat(K.ABILITY).get("1499963")
            if live is not None and self.ctx.csv_split(live)[0] != row:
                with self.assertRaises(K.KitError):
                    K.replay_row(K._Donors(self.ctx), K._revision_record(rec), "ability")
        finally:
            K.FROZEN_DONORS.update(saved)

    def test_frozen_donor_pin_rejects_a_tampered_row(self):
        for key, spec in K.FROZEN_DONORS.items():
            self.assertEqual(spec["width"], len(K.frozen_donor_row(spec, "pin")))
            self.assertEqual(spec["width"], 124 if key[1] == "leader_ability" else 126)
            bad = copy.deepcopy(spec)
            bad["cells"][27] = "13"
            with self.assertRaises(K.KitError):
                K.frozen_donor_row(bad, "tampered")

    @unittest.skipUnless(PRE_1054_ABILITY.is_file(), "1.4.1054 发布前 live 快照（extra4/before）不在本机")
    def test_frozen_donor_equals_pre_1054_live(self):
        """冻结行 == 1.4.1054 发布前 live 1499963 第 1 行；词条/队长表换成该快照回放，产物与当前逐字相同。"""
        import wf_mod_tool as core
        snapshot = {K.ABILITY: core.read_orderedmap_file_from_bytes(PRE_1054_ABILITY.read_bytes())}
        if PRE_1054_LEADER.is_file():
            snapshot[K.LEADER] = core.read_orderedmap_file_from_bytes(PRE_1054_LEADER.read_bytes())
        spec = K.FROZEN_DONORS[("live", "ability", "1499963", 1)]
        self.assertEqual(self.ctx.csv_split(snapshot[K.ABILITY]["1499963"])[0], K.frozen_donor_row(spec, "snapshot"))
        ctx = self.ctx

        class Pre1054Live:
            def __getattr__(self, name):
                return getattr(ctx, name)

            def live_flat(self, logical):
                return snapshot[logical] if logical in snapshot else ctx.live_flat(logical)
        before = K.revision_rows(Pre1054Live(), self.plan)
        now = K.revision_rows(self.ctx, self.plan)
        self.assertEqual(before["leader"], now["leader"])
        self.assertEqual(before["abilities"], now["abilities"])

    def test_panel_text_rules(self):
        """作者 2026-09-16 晚补充的两条面板文案规则，带阴性对照。"""
        texts = K.player_visible_texts(self.design)
        self.assertEqual(K.text_rule_problems(self.design), [])
        for where, value in texts.items():
            self.assertNotIn("无上限", str(value), where)
        boost = {c["key"]: c["value"] for c in self.design["custom_strings"]
                 if c["table"] == K.CAS}[K.CAS_KEY]
        self.assertFalse(any(ch.isdigit() for ch in boost), boost)     # 规则2：不写数字
        self.assertNotIn("秒", boost)                                   # 规则2：不写持续时间
        self.assertIn("强化『", boost)
        bad = copy.deepcopy(self.design)                                # 阴性对照 1：规则 1
        bad["text"]["skill1_desc"] += "（无上限）"
        self.assertTrue(K.text_rule_problems(bad))
        bad = copy.deepcopy(self.design)                                # 阴性对照 2：规则 2 数字
        for entry in bad["custom_strings"]:
            if entry["key"] == K.CAS_KEY:
                entry["value"] += "：威力 +50%"
        self.assertTrue(K.text_rule_problems(bad))
        bad = copy.deepcopy(self.design)                                # 阴性对照 3：规则 2 秒数
        for entry in bad["custom_strings"]:
            if entry["key"] == K.CAS_KEY:
                entry["value"] += "，持续十五秒"
        self.assertTrue(K.text_rule_problems(bad))

    def test_row_gate_catches_missing_string_and_puller_contract(self):
        rows = K.revision_rows(self.ctx, self.plan)
        for record in (1, 2):                                   # 536 / 629 的 string_id 未认领 → C8601
            self.assertTrue(K._row_gate_failed(K.row_gate("ability", rows["abilities"]["1599981"][record], set())))
        blocks = K._block("leader_ability")
        bad = list(rows["leader"][7])                            # during_trigger 4 的 puller 必须是空串
        bad[blocks["during_trigger"] + 1] = "0"
        self.assertTrue(K._row_gate_failed(K.row_gate("leader_ability", bad, set(K.CAS_KEYS))))
        banned = list(rows["leader"][7])                         # HpLow 恒真文案禁令
        banned[blocks["during_trigger"]] = "1"
        banned[blocks["during_trigger"] + 1] = "0"
        self.assertTrue(K._row_gate_failed(K.row_gate("leader_ability", banned, set(K.CAS_KEYS))))

    def _composed(self, level):
        import wf_dsl
        donors = {code: self.ctx.amf_parse(self.ctx.official_read(
            wf_dsl.dsl_logical(K.DONOR_PROGRAM.format(code=code, level=level)), "common"))
            for code in (K.D2_CODE, K.D1_CODE)}
        tree = K.revise_tree(K.compose_tree(donors[K.D2_CODE], donors[K.D1_CODE], level), level, self.plan)
        for fam in K.FAMILIES:                      # 与 build 同口径：只按已复制基名重定向（纯函数，不写包）
            donor = fam["src_dir"].rsplit("/", 1)[-1]
            dst = f"battle/effect/skill_unique/{K.CODE}_{fam['subdir']}"
            tree, _refs = self.ctx.rewrite_effect_refs(tree, {
                "src_dir": fam["src_dir"], "dst_dir": dst, "donor": donor, "dst_name": dst.rsplit("/", 1)[-1],
                "copied_bases": list(fam["fx"])}, strict=True)
        return tree

    def test_composed_trees_pass_gates(self):
        for level in (1, 2):
            tree = self._composed(level)
            gate = K.dsl_gates(tree, self.ctx.amf_bytes(tree), level, self.ctx.root)
            gate_view = {k: v for k, v in gate.items() if isinstance(v, list) and v}
            self.assertFalse(K._dsl_gate_failed(gate), gate_view)
            flags = K._find_cmds(tree, "ConditionalsChangeSkillFlag")
            self.assertEqual(len(flags), 3)                       # 改版：三段伤害各一个连击加成开关
            for flag in flags:
                self.assertEqual(flag[1], 1)                      # 536 的开关号被客户端写死为 1
                self.assertEqual([b[0] for b in flag[2:4]], ["Block", "Block"])
                self.assertEqual([[a[8] for a in K._find_cmds(flag[i], "CreateNormalAttack")] for i in (2, 3)],
                                 [[True], [False]])
            mult = self.plan["skill_dsl"]["programs"][K.DONOR_PROGRAM.format(code=K.CODE, level=level)]["multipliers"]
            for bind, name in K.REVISION_MULT_SLOTS:
                area = K._one(tree, "CreateHitArea", lambda a, b=bind: a[19] == b)
                for attack in K._find_cmds(area[23], "CreateNormalAttack"):
                    self.assertEqual([[p["min"], p["max"]] for p in attack[6]], [mult[name]["new"]])

    def test_composed_tree_gate_rejects_stale_flag_count(self):
        """阴性对照：少一个开关分支（回到改版前的 1 个）必须被门禁拦下。"""
        tree = copy.deepcopy(self._composed(1))
        area = K._one(tree, "CreateHitArea", lambda a: a[19] == 5)
        flag = K._one(area[23], "ConditionalsChangeSkillFlag")
        block = area[23][1]
        block[[i for i, n in enumerate(block) if n[1] is flag][0]] = flag[3][1][0]
        gate = K.dsl_gates(tree, self.ctx.amf_bytes(tree), 1, self.ctx.root)
        self.assertTrue(gate["kit_tree_problems"])
        self.assertTrue(K._dsl_gate_failed(gate))

    def test_pf_action_tree(self):
        """629 剑 PF 树：官方 knight_lv3 判定区，去 PF 上下文专用命令，光属性 + 连击加成。"""
        tree = K.build_pf_action_tree(self.ctx.root, self.plan)
        self.assertEqual(tree, self.plan["skill_dsl"]["new_program"]["tree"])
        self.assertEqual((tree[1], tree[10]), (1, 0))             # 自动档 → 629 按技能伤害结算
        for banned in ("SetPowerFilpSuppress", "NotifyPowerflipEnd"):
            self.assertEqual(K._find_cmds(tree, banned), [])
        self.assertEqual(K._find_cmds(tree, "ConditionalsChangeSkillFlag"), [])
        hit = K._one(tree, "CreateHitArea")
        self.assertEqual((hit[2], hit[9][0], hit[13], hit[14], hit[24]),
                         (-18, "Circle", ["SpecifyHitAreaLifetimeDirectly", 110],
                          ["CalculatedUsingMaxNumOfHits", 5], 0))
        attack = K._one(hit[23], "CreateNormalAttack")
        self.assertEqual((attack[2], attack[8]), (K.ELEMENT + 1, True))
        self.assertIn("battle/effect/powerflip/effect_powerflip_attack_spin/powerflip_attack_spin_three",
                      list(K._iter_strings(tree)))
        gate = K.dsl_gates(tree, self.ctx.amf_bytes(tree), K.PF_LEVEL, self.ctx.root)
        self.assertFalse(K._dsl_gate_failed(gate), {k: v for k, v in gate.items() if isinstance(v, list) and v})

    def test_reference_trees_match_package_after_unrewrite(self):
        """包内三棵树把特效引用还原成官方路径后，与改版探针 dsl_validated.json 逐节点相同。"""
        import wf_dsl
        reference = K.revision_reference_trees(self.ctx.root)
        if reference is None:
            self.skipTest("revision dsl_validated.json unavailable")
        pack = self.ctx.pack
        for level in (1, 2, K.PF_LEVEL):
            program = K.PF_PROGRAM if level == K.PF_LEVEL else self.ctx.program_path(str(level))
            logical = wf_dsl.dsl_logical(program)
            if not pack.pkg_has("common", logical):
                self.skipTest(f"package lacks {program}")
            tree = self.ctx.amf_parse(pack.pkg_path("common", logical).read_bytes())
            self.assertEqual(K.unrewrite_effect_refs(tree), reference[level])

    def test_lookup_scope_negative_controls(self):
        tree = self._composed(1)
        self.assertEqual(K.lookup_scope_problems(tree), [])
        broken = copy.deepcopy(tree)
        K._one(broken, "CreateHitArea", lambda a: a[19] == 9)[2] = 12
        self.assertTrue(K.lookup_scope_problems(broken))
        broken = copy.deepcopy(tree)
        [s for s in K._find_cmds(broken, "ShowEffect") if s[3] == 11][0][3] = 3
        self.assertTrue(K.lookup_scope_problems(broken))
        broken = copy.deepcopy(tree)
        K._find_cmds(broken, "ConditionalsChangeSkillFlag")[0][3] = ["DoNothing"]
        self.assertTrue(K.sig_problems(broken))


class ForeignShadowDriftTest(unittest.TestCase):
    """复核修复：``gates`` 把「批次级 live 漂移」和真红项分家的判据，全部带阴性对照。

    背景：角色上线后包内共享表全表载荷在**别家键**上落后于链尾，flow preflight 必报
    ``unclaimed_change``（记忆卡 wf-flow-serial-publish-order）。旧写法把它算进 ``failures`` ⇒
    ``all_pass=false`` ⇒ kit-report 被置 ``draft`` ⇒ 主控发布步序第一步的封存 preflight 会被
    ``wf_seasonal7_build.step_preflight`` 直接拒绝。分家只允许这一条延后，且必须机器判定为纯别家漂移。
    """

    @classmethod
    def setUpClass(cls):
        try:
            cls.ctx = _context()
        except unittest.SkipTest:
            raise
        except Exception as exc:
            raise unittest.SkipTest(f"live store unavailable: {exc}")
        evidence = cls.ctx.pack.read_evidence("flow-inspect.json", {}) or {}
        cls.summary = evidence.get("summary") or {}
        if not cls.summary:
            raise unittest.SkipTest("evidence/flow-inspect.json 不存在：先跑 kit 的 inspect 子命令")

    def _drift(self, summary):
        return K.foreign_shadow_conflicts(self.ctx.pack, summary)

    def _mutate(self, **preflight):
        bad = copy.deepcopy(self.summary)
        bad.setdefault("preflight", {}).update(preflight)
        return bad

    def test_real_evidence_is_foreign_only(self):
        drift = self._drift(self.summary)
        self.assertEqual(drift["own"], [], "有冲突落在本角色的键上，就不是批次级漂移")
        self.assertEqual(drift["total"], drift["foreign"])
        for name, ok in drift["checks"].items():
            self.assertTrue(ok, f"check {name} 未通过：{drift['checks']}")
        self.assertTrue(drift["batch_live_drift_only"])

    def test_conflict_touching_own_key_is_blocking(self):
        """阴性对照 1：任意一条冲突碰到自家键（159998 / samurai_robot_plum）→ 必须不再算漂移。"""
        for claim in (f"master/ability/leader_ability.orderedmap:{K.CID}",
                      f"master/string/custom_ability_string.orderedmap:{K.CAS_KEY}",
                      f"cdndata/character.json:{K.CID}"):
            conflicts = list((self.summary.get("preflight") or {}).get("conflicts") or [])
            conflicts.append({"claim": claim, "kind": "unclaimed_change", "reason": "injected"})
            drift = self._drift(self._mutate(conflicts=conflicts))
            self.assertTrue(drift["own"], claim)
            self.assertFalse(drift["batch_live_drift_only"], claim)
            self.assertFalse(drift["checks"]["no_conflict_touches_this_character"], claim)

    def test_claimed_key_without_cid_substring_still_counts_as_own(self):
        """阴性对照 2：认领里的键即使字面不含 159998/code，也必须算自家（认领集合那条分支）。"""
        class _FakePack:
            @staticmethod
            def load_claims():
                return [{"root": "common", "logical_path": "master/x/y.orderedmap",
                         "outer_keys": ["zzz_unrelated_key"], "inner_keys": []}]
        bad = self._mutate(conflicts=[{"claim": "master/x/y.orderedmap:zzz_unrelated_key",
                                       "kind": "unclaimed_change", "reason": "injected"}])
        drift = K.foreign_shadow_conflicts(_FakePack, bad)
        self.assertTrue(drift["own"])
        self.assertFalse(drift["batch_live_drift_only"])

    def test_other_conflict_kinds_and_errors_are_blocking(self):
        """阴性对照 3：冲突 kind 不是 unclaimed_change、或多出别的错误、或必需资产缺失 → 必须变红。"""
        conflicts = list((self.summary.get("preflight") or {}).get("conflicts") or [])
        other = conflicts + [{"claim": "cdndata/character_text.json:129991",
                              "kind": "hash_mismatch", "reason": "injected"}]
        self.assertFalse(self._drift(self._mutate(conflicts=other))["batch_live_drift_only"])

        bad = copy.deepcopy(self.summary)
        bad["errors"] = list(bad.get("errors") or []) + ["something else went wrong"]
        self.assertFalse(self._drift(bad)["batch_live_drift_only"])

        bad = copy.deepcopy(self.summary)
        bad["missing_required"] = ["character/samurai_robot_plum/pixelart/sprite_sheet.png"]
        self.assertFalse(self._drift(bad)["batch_live_drift_only"])

        bad = copy.deepcopy(self.summary)
        bad["master_reference"] = {"release_ready": True, "missing": [], "problems": ["injected"]}
        self.assertFalse(self._drift(bad)["batch_live_drift_only"])

        bad = copy.deepcopy(self.summary)
        bad["three_layer_claim_status"] = {"consistent": False}
        self.assertFalse(self._drift(bad)["batch_live_drift_only"])

    def test_not_ready_without_conflicts_is_blocking(self):
        """阴性对照 4：preflight 不就绪但冲突表为空（说明是别的原因）→ 不许延后。

        ``conflicts_is_nonempty_list`` 与 ``all_unclaimed_change`` 里的 ``bool(conflicts)`` 是冗余对
        （变异实验：单独把前者钉成 True 不会有测试变红），所以这里逐旗断言，而不是只看总判定。
        """
        for empty in ([], None):
            drift = self._drift(self._mutate(conflicts=empty))
            self.assertFalse(drift["batch_live_drift_only"], empty)
            self.assertFalse(drift["checks"]["conflicts_is_nonempty_list"], empty)
            self.assertFalse(drift["checks"]["all_unclaimed_change"], empty)

    def test_split_deferred_only_defers_the_inspect_line(self):
        """阴性对照 5：延后名单只认 inspect 这一条；同时存在真红项时它必须留在阻塞项里。"""
        benign = {"batch_live_drift_only": True}
        blocking, deferred = K.split_deferred([K.INSPECT_NOT_READY], benign)
        self.assertEqual((blocking, deferred), ([], [K.INSPECT_NOT_READY]))
        blocking, deferred = K.split_deferred(["panel text rules: 无上限", K.INSPECT_NOT_READY], benign)
        self.assertEqual(blocking, ["panel text rules: 无上限"])
        self.assertEqual(deferred, [K.INSPECT_NOT_READY])
        blocking, deferred = K.split_deferred([K.INSPECT_NOT_READY], {"batch_live_drift_only": False})
        self.assertEqual((blocking, deferred), ([K.INSPECT_NOT_READY], []))

    def test_inspect_raise_rule(self):
        """inspect 的抛错口径：rc=2 永远抛；rc=3 只在不是纯别家漂移时抛；rc=0 从不抛。"""
        benign, hostile = {"batch_live_drift_only": True}, {"batch_live_drift_only": False}
        self.assertTrue(K.inspect_should_raise(2, benign))      # 真错：即使冲突面干净也必须抛
        self.assertTrue(K.inspect_should_raise(3, hostile))     # 漂移碰到自家键 / 还有别的错
        self.assertFalse(K.inspect_should_raise(3, benign))     # 上线后的常态：延后给主控 rebase
        self.assertFalse(K.inspect_should_raise(0, hostile))

    def test_gates_json_matches_the_split(self):
        """落盘的 gates.json 与判据自洽：blocking 为空 ⇒ all_pass；deferred 非空 ⇒ 不是 publishable_now。"""
        gates = json.loads((self.ctx.root / K.IMPL_REL / "gates.json").read_text(encoding="utf-8"))
        self.assertEqual(gates["all_pass"], not gates["blocking_failures"])
        self.assertEqual(gates["publishable_now"], not gates["failures"])
        self.assertEqual(sorted(gates["blocking_failures"] + gates["deferred"]), sorted(gates["failures"]))
        for line in gates["deferred"]:
            self.assertEqual(line, K.INSPECT_NOT_READY)


class IntegrateGuardTest(unittest.TestCase):
    """审查修复：stance_detail 被 tables 回写的诊断、指纹逐项差异、特效小人与像素小人同色核对（阴性对照）。

    对照组先用现有像素/fx 产物的同步副本跑一次，变异组只比对照组「多出」的问题，不依赖当前 live 产物全绿。
    """

    @classmethod
    def setUpClass(cls):
        try:
            cls.ctx = _context()
        except unittest.SkipTest:
            raise
        except Exception as exc:
            raise unittest.SkipTest(f"live store unavailable: {exc}")
        root = cls.ctx.root
        needed = [root / K.FX_REPORT_REL, root / K.FX_ANALYSIS_REL, root / K.PIXEL_REPORT_REL, root / K.FX_MANIFEST_REL]
        needed += [root / K.PIXEL_OUT_REL / f"{name}.png" for name in K.PIXEL_SHEETS]
        if not all(p.is_file() for p in needed):
            raise unittest.SkipTest("fx / pixel outputs not present")
        cls.templates = {name: K._rgba_array(cls.ctx.pack.template_asset(
            K.PIXEL_SHEET.format(code=K.D1_CODE, name=name))[1]) for name in K.PIXEL_SHEETS}

    def test_fingerprint_part_changes(self):
        before = ["a#1=x", "b=y", "c=<missing>"]
        self.assertEqual(K.fingerprint_part_changes(before, before), [])
        self.assertEqual(K.fingerprint_part_changes(before, ["a#1=x", "b=z", "d=w"]), ["b", "c", "d"])
        parts = K.kit_fingerprint_parts(self.ctx.pack)
        self.assertEqual(K.kit_fingerprint(self.ctx.pack), K._sha("\n".join(parts).encode("utf-8")))
        self.assertIn(f"{K.STANCE}#{K.CID}", [p.rpartition("=")[0] for p in parts])

    def test_stance_detail_distinguishes_tables_rewrite(self):
        check = K.stance_detail_check(self.ctx, K.load_design(self.ctx.root))
        self.assertEqual(check["design"], ',1,"1,5",1,,1,"1,5",1')
        self.assertEqual(check["tables_template_value"], ",1,1,1,,1,1,1")
        self.assertEqual(check["ok"], check["package"] == check["design"])
        self.assertEqual(check["reverted_by_tables"], check["package"] == check["tables_template_value"])
        design, tables = check["design"], check["tables_template_value"]
        self.assertEqual((K.classify_stance_detail(design, design, tables)["ok"],
                          K.classify_stance_detail(design, design, tables)["reverted_by_tables"]), (True, False))
        self.assertEqual((K.classify_stance_detail(tables, design, tables)["ok"],
                          K.classify_stance_detail(tables, design, tables)["reverted_by_tables"]), (False, True))
        self.assertEqual((K.classify_stance_detail(None, design, tables)["ok"],
                          K.classify_stance_detail(None, design, tables)["reverted_by_tables"]), (False, False))

    # ---- 小人同色
    def _fixture(self, tmp: Path, recolor: dict | None = None, sync_dependency: bool = True,
                 s1_provenance: dict | None = None) -> dict:
        """复制 pixel/out 与两份报告到临时目录；recolor={源色hex: 新目标RGB} 改像素小人里该源色的输出色。"""
        import io
        import json
        from PIL import Image
        root = self.ctx.root
        out = tmp / "out"
        out.mkdir()
        px_report = json.loads((root / K.PIXEL_REPORT_REL).read_text(encoding="utf-8"))
        fx_report = json.loads((root / K.FX_REPORT_REL).read_text(encoding="utf-8"))
        for name in K.PIXEL_SHEETS:
            raw = (root / K.PIXEL_OUT_REL / f"{name}.png").read_bytes()
            if recolor:
                arr = K._rgba_array(raw).copy()
                tpl = self.templates[name]
                for src, new in recolor.items():
                    rgb = [int(src[i:i + 2], 16) for i in (0, 2, 4)]
                    sel = (tpl[..., :3] == rgb).all(-1) & (tpl[..., 3] == 255)
                    arr[sel, :3] = new
                buf = io.BytesIO()
                Image.fromarray(arr, "RGBA").save(buf, format="PNG")
                raw = buf.getvalue()
            (out / f"{name}.png").write_bytes(raw)
            px_report["outputs"][name]["sha256"] = K._sha(raw)
        px_path = tmp / "pixel_report.json"
        px_path.write_text(json.dumps(px_report, ensure_ascii=False), encoding="utf-8")
        if sync_dependency:
            fx_report["pixel_dependency"]["sha256"] = K._sha(px_path.read_bytes())
        fx_report["sheets"]["S1_ittou"]["doll"]["provenance"].update(s1_provenance or {})
        fx_path = tmp / "fx_report.json"
        fx_path.write_text(json.dumps(fx_report, ensure_ascii=False), encoding="utf-8")
        return {"pixel_out": out, "pixel_report": px_path, "fx_report": fx_path}

    def _run(self, **kw) -> tuple[dict, set]:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            result = K.doll_color_checks(self.ctx.pack, self._fixture(Path(tmp), **kw))
        return result, set(result["problems"])

    def test_doll_colors_negative_controls(self):
        control, base = self._run()
        fams = {f["family"]: f for f in control["families"]}
        s1 = [r for r in fams["S1_ittou"]["colors"] if r["rule"] == "pixel_same_source" and r["source"] not in K.DOLL_KEEP]
        s1_analog = [r for r in fams["S1_ittou"]["colors"] if r["rule"] == "old_doll_analog"]
        s2_pixel = [r for r in fams["S2_kanbai"]["colors"] if r["rule"] == "pixel_mapping"]
        self.assertTrue(s1 and s1_analog and s2_pixel, control["families"])

        # 1) smr22 小人某源色在像素里改色，特效没跟 → S1 同色门禁报错
        victim = s1[0]["source"]
        _r, got = self._run(recolor={victim: (1, 2, 3)})
        self.assertTrue(any("S1_ittou" in p and f"#{victim}" in p for p in got - base), got - base)

        # 2) 旧小人同类源色在像素里改色 → 两族 analog 核对报错
        analog = s1_analog[0]["analog_source"]
        _r, got = self._run(recolor={analog: (4, 5, 6)})
        self.assertTrue(any(f"同类源色 #{analog}" in p for p in got - base), got - base)

        # 3) 旧小人 pixel_mapping 色在像素里改色 → S2 报错
        victim = s2_pixel[0]["source"]
        _r, got = self._run(recolor={victim: (7, 8, 9)})
        self.assertTrue(any("S2_kanbai" in p and f"#{victim}" in p for p in got - base), got - base)

        # 3b) smr22 族不认 fx 报告的「同类源色」说辞：像素里有的源色一律直接比像素
        by_target: dict = {}
        for r in s1:
            by_target.setdefault(r["fx"], []).append(r["source"])
        pair = next(v for v in by_target.values() if len(v) >= 2)
        victim, alibi = pair[0], pair[1]
        fx_target = next(r["fx"] for r in s1 if r["source"] == victim)
        _r, got = self._run(recolor={victim: (10, 11, 12)}, s1_provenance={victim: {
            "rule": "old_doll_analog", "analog_source": alibi, "analog_target": fx_target, "target": fx_target}})
        self.assertTrue(any("S1_ittou" in p and f"#{victim}" in p for p in got - base), got - base)

        # 4) 像素报告变了但 fx 没重跑（依赖 sha 不同步）→ 依赖链报错
        _r, got = self._run(sync_dependency=False)
        self.assertTrue(any("像素报告已变" in p for p in got - base), got - base)

    def test_doll_colors_missing_inputs_fail(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            result = K.doll_color_checks(self.ctx.pack, {"pixel_report": Path(tmp) / "absent.json"})
        self.assertTrue(result["problems"])


class FxManifestHookTest(unittest.TestCase):
    def test_manifest_shapes_and_transform(self):
        import io
        import json
        import tempfile
        from PIL import Image
        import wf_assets
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / Path(K.FX_MANIFEST_REL).parent
            out.mkdir(parents=True)
            template = Image.new("RGBA", (8, 4), (10, 20, 30, 128))
            dyed = Image.new("RGBA", (8, 4), (200, 100, 50, 128))
            buf = io.BytesIO()
            dyed.save(buf, format="PNG")
            (out / "kanbai.png").write_bytes(wf_assets.png_encode(buf.getvalue()))   # 店内小写魔数也要能读
            src = "battle/effect/skill_unique/samurai_robot/samurai_robot.png"
            for payload in ({src: "kanbai.png"}, {"sheets": [{"source": src, "png": "kanbai.png"}]}):
                (out / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")
                mapping, info = K.fx_manifest(root)
                self.assertEqual(list(mapping), [src])
                log = []
                transform = K._png_transform_for(src, "x/x.png", mapping, log)
                result = transform(template)
                self.assertEqual(result.getpixel((0, 0)), (200, 100, 50, 128))
                self.assertTrue(log[0]["alpha_identical"])
            self.assertIsNone(K._png_transform_for("other.png", "y/y.png", mapping, []))
            with self.assertRaises(K.KitError):
                K._png_transform_for(src, "x/x.png", mapping, [])(Image.new("RGBA", (9, 4)))
            with self.assertRaises(K.KitError):            # alpha 不等 = 几何漂移，硬失败
                K._png_transform_for(src, "x/x.png", mapping, [])(Image.new("RGBA", (8, 4), (10, 20, 30, 255)))


class MediaIntegrateTest(unittest.TestCase):
    """Integrate：特效 sheet 存储态原字节、像素复核判定、像素包内核对与语音状态（只读 + 阴性对照）。"""

    def test_store_bytes_forms(self):
        import io
        import tempfile
        from PIL import Image
        import wf_assets
        buf = io.BytesIO()
        Image.new("RGBA", (3, 2), (1, 2, 3, 255)).save(buf, format="PNG")
        real = buf.getvalue()
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "a.png"
            p.write_bytes(real)
            store = K.fx_store_bytes(p)
            self.assertEqual(store[:8], wf_assets.PNG_FAKE)
            self.assertEqual(store[8:], real[8:])                    # 只换魔数，不重编码
            p.write_bytes(store)
            self.assertEqual(K.fx_store_bytes(p), store)             # 已是存储态原样返回
            p.write_bytes(b"GIF89a....")
            with self.assertRaises(K.KitError):
                K.fx_store_bytes(p)

    def test_pixel_review_verdict(self):
        section = ("## 4. 初审\n| zantetsu 斩铁 | x | **PASS** |\n"
                   "## 5. 修复轮复核（04:0x）\n| 角色 | 改动 | 判定 |\n|---|---|---|\n"
                   "| zantetsu 斩铁 | 未改 | {verdict} |\n| yuki 见岛勇希 | 未改 | **PASS** |\n")
        self.assertTrue(K.pixel_review_verdict(section.format(verdict="**PASS**"))[0])
        self.assertFalse(K.pixel_review_verdict(section.format(verdict="**FAIL**（必修）"))[0])
        self.assertFalse(K.pixel_review_verdict("## 4. 初审\n| zantetsu 斩铁 | x | **PASS** |\n")[0])   # 只有初审段不算
        self.assertFalse(K.pixel_review_verdict(section.format(verdict="**PASS**").replace("| zantetsu 斩铁 | 未改", "| tekuto | 未改"))[0])


class MediaPackageStateTest(unittest.TestCase):
    """真实包只读核对：已装像素 = pixel/out 存储态；篡改字节 / alpha 的阴性对照必须报问题；语音状态已装包。"""

    @classmethod
    def setUpClass(cls):
        try:
            cls.ctx = _context()
        except unittest.SkipTest:
            raise
        except Exception as exc:
            raise unittest.SkipTest(f"live store unavailable: {exc}")
        cls.state = K.pixel_inputs(cls.ctx.root)
        if not cls.state["ready"]:
            raise unittest.SkipTest(f"pixel inputs pending: {cls.state['problems']}")

    def _store(self):
        return {K.PIXEL_SHEET.format(code=K.CODE, name=n): K.fx_store_bytes(Path(o["file"]))
                for n, o in self.state["outputs"].items()}

    def test_pixel_prewrite_control_and_mutations(self):
        import io
        import numpy as np
        from PIL import Image
        import wf_seasonal7_common as C
        store = self._store()
        self.assertEqual(K.pixel_package_problems(self.ctx.pack, store), [])
        logical = K.PIXEL_SHEET.format(code=K.CODE, name="sprite_sheet")
        arr = np.asarray(C.png_open(store[logical])).copy()
        ys, xs = np.nonzero(arr[..., 3] == 0)
        arr[ys[0], xs[0], 3] = 255                                  # 透明像素变不透明 = alpha 漂移
        mutated = C.png_store_bytes(Image.fromarray(arr, "RGBA"))
        problems = K.pixel_package_problems(self.ctx.pack, {**store, logical: mutated})
        self.assertTrue(any("bytes != store form" in p for p in problems))
        self.assertTrue(any("alpha differs" in p for p in problems))
        reenc = C.png_store_bytes(C.png_open(store[logical]))       # 像素相同但 PIL 重编码：字节门禁仍拦
        if reenc != store[logical]:
            self.assertTrue(any("bytes != store form" in p
                                for p in K.pixel_package_problems(self.ctx.pack, {**store, logical: reenc})))

    def test_voice_state_reports(self):
        state = K.voice_state(self.ctx.pack)
        self.assertIn("packed", state)
        if state["packed"]:
            self.assertEqual(state["extra_voice_files"], [])
            self.assertEqual(state["speech_refs"][:6], [f"home/home_{i}" for i in range(6)])


if __name__ == "__main__":
    unittest.main()
