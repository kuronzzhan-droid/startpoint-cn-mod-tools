# -*- coding: utf-8 -*-
"""妮可拉 kit（119991 ``sorceress_teacher_moon``）：设计稿自查 + 行装配 + DSL 门禁。

三组用例：

1. **纯静态**（不需要 live / 官方基线）：模块常量与设计稿 JSON 的互锁、裁决 §8 的设计自查
   （队长表禁 422/724/713、c2 雕像组每键单值、前置 188/144 不许出现、13 条全瞬发、面板禁词、
   ``donor`` 地址 1 基→0 基换算），以及本模块的 DSL 小工具
   （``retarget_effects``／``donor_gate_problems``／``write_dsl_checked`` 的包装壳拦截）。
2. **官方基线**（缺 ``.cdn/cn`` 或 live store 时跳过）：6+13 行逐行装配并与设计登记的
   ``wf_describe``／``row_final`` 逐字比对；两棵技能树的装配、donor 闸门与往返自检。
3. **已构建的 workspace**（``work/character_packs/ma-nicola`` 不存在时跳过）：包内自有键、
   认领、kit-report 与 DSL 程序清单、语音路由、能量档、三层镜像。

不写 live store / ``assets/`` / ``.cdn``，不跑发布；官方基线只读。
"""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_dsl  # noqa: E402
import wf_midautumn_common as MC  # noqa: E402
import wf_midautumn_kit_nicola as K  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_midautumn_specs as MS  # noqa: E402
import wf_mod_tool as core  # noqa: E402
import wf_seasonal7_build as B  # noqa: E402

ROOT = core.project_root()
DESIGN = MS.load_design(ROOT, "nicola")
WORKSPACE = ROOT / "work/character_packs/ma-nicola"

LEADER_PLAN = DESIGN["plan"]["leader_ability"]
ABILITY_PLAN = DESIGN["plan"]["ability"]
SKILL_PLAN = DESIGN["plan"]["skills"]


def _baseline_available() -> bool:
    profile = core.resolve_profile()
    return profile is not None and profile.store.is_dir() and (ROOT / ".cdn" / "cn").is_dir()


_BASELINE = _baseline_available()
_CTX = None


def ctx():
    """只读上下文：``record_sources=False`` ⇒ 母本取数不写 workspace（框架 §10.2）。"""
    global _CTX
    if _CTX is None:
        _CTX = B.KitContext(MC.MAPack(MS.get_spec("nicola"), record_sources=False))
    return _CTX


def all_records():
    for key in K.ABILITY_KEYS:
        block = ABILITY_PLAN["keys"][key]
        for record in block["records"]:
            yield key, block, record


# ---------------------------------------------------------------- 1. 纯静态

class ConstantTests(unittest.TestCase):
    def test_identity_matches_the_registry(self):
        spec = MS.get_spec("nicola")
        self.assertEqual((spec.cid, spec.code), (K.CID, K.CODE))
        self.assertEqual((spec.template_id, spec.template_code), (K.TEMPLATE_ID, K.TEMPLATE_CODE))
        self.assertEqual(spec.element, K.ELEMENT)
        self.assertEqual(spec.pf_type, 4)
        self.assertEqual(spec.stance, "Supporter")
        self.assertEqual(spec.rarity, 5)             # 母本 211020 是 ★4，本角色升 ★5

    def test_design_identity_interlock(self):
        identity = DESIGN["identity"]
        self.assertEqual(identity["cid"], K.CID)
        self.assertEqual(identity["code"], K.CODE)
        self.assertEqual(identity["element"], K.ELEMENT)
        self.assertEqual(identity["template_character"]["id"], K.TEMPLATE_ID)
        self.assertEqual(DESIGN["schema"], "ma-design/1")

    def test_spec_declares_every_self_owned_key(self):
        keys = MS.get_spec("nicola").extra_keys
        self.assertEqual(sorted(keys[KL.CAS]), sorted((K.CAS_CHANGE_SKILL, K.CAS_OVERRIDE)))
        self.assertEqual(keys[KL.SWITCHED], (K.VOICE_KEY,))
        # rework1：新增固有状态「月讲」⇒ 键必须声明，且与设计稿登记的一致
        self.assertEqual(keys[MS.UNIQUE_CONDITION_LOGICAL], (K.UID,))
        add = DESIGN["plan"]["unique_conditions"]["add"]
        self.assertEqual([str(entry["key"]) for entry in add], [K.UID])

    def test_unique_condition_id_is_eight_digits(self):
        # 裁决 §1：cid*100+n；7 位撞过基诺维 1699901/02
        self.assertEqual(K.UID, str(K.CID * 100 + 1))
        self.assertEqual(len(K.UID), 8)
        self.assertTrue(K.UID.isdigit())

    def test_unique_condition_cells_are_unbounded_and_timeless(self):
        cells = DESIGN["plan"]["unique_conditions"]["add"][0]["cells"]
        # c3 = 无时间限制；c4 = 不设上限（写 (None) ＝上限 1，会把 461 叠层弄死）
        self.assertEqual(cells["3"], "99999999")
        self.assertEqual(cells["4"], "99")
        self.assertEqual(cells["1"], K.UNIQUE_NAME)
        self.assertEqual(cells["2"], K.UC_ICON_ROW)
        self.assertEqual(cells["14"], K.CODE)

    def test_panel_override_key_follows_the_client_rule(self):
        # 客户端查的键 = "desc_override_" + 该槽第 0 行的 string_id
        import wf_client_legality as L
        slot0 = ABILITY_PLAN["keys"][f"{K.CID}{K.OVERRIDE_SLOT}"]["records"][0]
        self.assertEqual(K.CAS_OVERRIDE,
                         L.PANEL_OVERRIDE_KEY_PREFIX + slot0["row_final"][0])
        self.assertEqual(L.panel_override_capability(K.CAS_OVERRIDE), L.PANEL_OVERRIDE_V2)
        self.assertIn(L.PANEL_OVERRIDE_V2, K.SPEC["required_capabilities"])

    def test_ability_keys_are_the_six_slots(self):
        self.assertEqual(K.ABILITY_KEYS, tuple(f"{K.CID}{n}" for n in range(1, 7)))
        self.assertEqual(tuple(sorted(ABILITY_PLAN["keys"])), tuple(sorted(K.ABILITY_KEYS)))

    def test_parse_donor_converts_one_based_to_zero_based(self):
        self.assertEqual(K._parse_donor("official:leader:151165#L1"),
                         ("official", "leader_ability", "151165#0"))
        self.assertEqual(K._parse_donor("official:ability:2110202#L2"),
                         ("official", "ability", "2110202#1"))
        self.assertEqual(K._parse_donor("live:ability:1599981#L2"),
                         ("live", "ability", "1599981#1"))
        for bad in ("o:L:151165:1", "official:ability:2110202", "official:mana:1#L1",
                    "official:ability:2110202#L0"):
            with self.assertRaises(K.KitError):
                K._parse_donor(bad)


class DesignSelfCheckTests(unittest.TestCase):
    """裁决 §8：kit 实现前对设计稿的自查，这里钉死成回归用例。"""

    def test_leader_block_shape(self):
        self.assertEqual(LEADER_PLAN["key"], str(K.CID))
        self.assertEqual(int(LEADER_PLAN["layout"]["ncols"]), KL.LEADER_NCOLS)
        self.assertEqual(int(LEADER_PLAN["new_row_count"]), K.LEADER_ROWS)
        self.assertEqual(len(LEADER_PLAN["rows"]), K.LEADER_ROWS)

    def test_leader_table_carries_no_forbidden_kind(self):
        """422 冲刺参数 / 724 Fever 比例 / 713 只许写 ability 表；队长表写 = C7050。"""
        rows = [[str(x) for x in entry["row_final"]] for entry in LEADER_PLAN["rows"]]
        K.ban_forbidden_leader_kinds(rows)
        tampered = copy.deepcopy(rows)
        tampered[0][45] = "422"
        with self.assertRaises(K.KitError):
            K.ban_forbidden_leader_kinds(tampered)
        tampered = copy.deepcopy(rows)
        tampered[0][107] = "724"
        with self.assertRaises(K.KitError):
            K.ban_forbidden_leader_kinds(tampered)

    def test_ability_statue_group_and_unisonable_are_single_valued_per_key(self):
        """裁决 §8：c2 每键单值（官方 790 个多记录键 0 个混用）；c1 同样整键一致。"""
        total = 0
        for key in K.ABILITY_KEYS:
            block = ABILITY_PLAN["keys"][key]
            rows = [[str(x) for x in r["row_final"]] for r in block["records"]]
            total += len(rows)
            self.assertEqual({r[2] for r in rows}, {block["statue_group"]}, key)
            self.assertEqual([r[1] for r in rows],
                             [str(x) for x in block["unisonable_per_record"]], key)
            self.assertEqual(len({r[1] for r in rows}), 1, key)
            KL.check_ability_key(rows, key, K.CODE, int(key[-1]))
        self.assertEqual(total, K.ABILITY_RECORDS)
        self.assertEqual(int(ABILITY_PLAN["record_total"]), K.ABILITY_RECORDS)

    def test_no_precondition_kind_188_or_144(self):
        """188 数的是固有状态实例数（恒为 1），阈值 ≥2 永不成立；144 官方零先例。"""
        cols = [ABILITY_PLAN["layout"][name] for name in
                ("precondition1", "precondition2", "precondition3")]
        for key, _block, record in all_records():
            row = [str(x) for x in record["row_final"]]
            for col in cols:
                self.assertNotIn(row[col], ("188", "144"),
                                 f"{key}#{record['index']} precondition c{col}={row[col]}")

    def test_every_row_is_instant_no_during_block(self):
        """13 条 + 6 行全是瞬发行 ⇒ 绕开 c85 哨兵、during puller 契约与恒真文案三类坑。"""
        during = ABILITY_PLAN["layout"]["during_trigger"]
        for key, _block, record in all_records():
            row = [str(x) for x in record["row_final"]]
            self.assertIn(row[during], ("", "0"), f"{key}#{record['index']}")
        during = LEADER_PLAN["layout"]["during_trigger"]
        for entry in LEADER_PLAN["rows"]:
            row = [str(x) for x in entry["row_final"]]
            self.assertIn(row[during], ("", "0"), f"leader#{entry['index']}")

    def test_no_629_row(self):
        """本套件没有 629（能力发动技能）⇒ 也就没有「629 排在同触发消耗行之前」的排序约束。"""
        instant = ABILITY_PLAN["layout"]["instant_content"]
        for key, _block, record in all_records():
            row = [str(x) for x in record["row_final"]]
            self.assertNotEqual(row[instant], "629", f"{key}#{record['index']}")

    def test_536_string_key_is_declared_and_referenced(self):
        rows = DESIGN["plan"]["texts"]["custom_ability_string"]["rows"]
        self.assertEqual(sorted(r["key"] for r in rows),
                         sorted((K.CAS_CHANGE_SKILL, K.CAS_OVERRIDE)))
        referenced = {str(record["row_final"][70]) for _k, _b, record in all_records()
                      if str(record["row_final"][70])}
        self.assertIn(K.CAS_CHANGE_SKILL, referenced)

    def test_panel_override_text_matches_the_author_panel(self):
        """能力 3 的覆盖文案逐行 ＝ rework1/panel/nicola.json 的 4 行（作者已过目的目标面板）。"""
        panel = json.loads((ROOT / "work/character_packs/midautumn-20260920/rework1"
                            / "panel/nicola.json").read_text(encoding="utf-8"))
        want = [line["text"] for ability in panel["abilities"]
                if ability["index"] == K.OVERRIDE_SLOT for line in ability["lines"]]
        rows = {r["key"]: r["text"] for r in
                DESIGN["plan"]["texts"]["custom_ability_string"]["rows"]}
        self.assertEqual(rows[K.CAS_OVERRIDE].split("\n"), want)
        for line in want:
            self.assertEqual(KL.panel_problems(line), [], line)

    def test_panel_override_carries_the_main_position_icon(self):
        """09-21 真机反馈：能力 3 整键主位限制（c1 全键 "false"），覆盖串每行必须带
        ``<icon id='main'>`` 才会显示主位限制图标；不许用字面「Ⓜ」字符替代。

        设计稿 ``custom_ability_string`` 与 ``rework1/panel/nicola.json`` 只登记文案本身，
        图标前缀是 :func:`wf_midautumn_kit_nicola._apply_main_icon` 在生成覆盖串时才补上的
        格式细节（裁决：不改文案，只改格式）。
        """
        panel = json.loads((ROOT / "work/character_packs/midautumn-20260920/rework1"
                            / "panel/nicola.json").read_text(encoding="utf-8"))
        want_lines = [line["text"] for ability in panel["abilities"]
                      if ability["index"] == K.OVERRIDE_SLOT for line in ability["lines"]]
        raw_text = {r["key"]: r["text"] for r in
                    DESIGN["plan"]["texts"]["custom_ability_string"]["rows"]}[K.CAS_OVERRIDE]
        self.assertNotIn(K.MAIN_ICON, raw_text)          # 设计稿原文不带格式
        self.assertNotIn("Ⓜ", raw_text)
        rendered = K._apply_main_icon(raw_text).split("\n")
        # 多记录槽（9 条记录）的覆盖串行数＝面板行数（4 行，一行可以覆盖多条记录）。
        self.assertEqual(len(rendered), len(want_lines))
        for line in rendered:
            self.assertTrue(line.startswith(K.MAIN_ICON), line)
            self.assertIn("<icon id='main'>", line)
        self.assertNotIn("Ⓜ", "\n".join(rendered))

    def test_ability_slot3_consumes_after_the_beneficiaries(self):
        """行序契约：525 消耗行排在同触发的受益行之后，否则层数先被吃掉、前置 187 当场不成立。"""
        rows = [record["row_final"] for _k, _b, record in all_records()
                if _k == f"{K.CID}{K.OVERRIDE_SLOT}"]
        self.assertEqual(len(rows), 9)
        self.assertEqual(K.consume_order_problems(rows), [])
        # 打乱顺序必须变红（判据是真的在判，不是恒绿）
        swapped = list(rows)
        consume = [i for i, r in enumerate(swapped) if r[47] == K.CONSUME_KIND][0]
        benefit = [i for i, r in enumerate(swapped) if r[47] in K.BENEFIT_KINDS][-1]
        swapped[consume], swapped[benefit] = swapped[benefit], swapped[consume]
        self.assertNotEqual(K.consume_order_problems(swapped), [])

    def test_ability_slot3_unique_columns_point_at_the_new_state(self):
        rows = [record["row_final"] for _k, _b, record in all_records()
                if _k == f"{K.CID}{K.OVERRIDE_SLOT}"]
        add = [r for r in rows if r[47] == "461"]
        consume = [r for r in rows if r[47] == K.CONSUME_KIND]
        self.assertEqual(len(add), 1)
        self.assertEqual(len(consume), 1)
        self.assertEqual(add[0][68], K.UID)
        self.assertEqual(consume[0][68], K.UID)
        self.assertEqual(add[0][27], "24")            # 触发 24 SkillMax（自身技能槽充满）
        self.assertEqual(add[0][28], "0")             # 官方 9 行零例外：puller 自身
        self.assertEqual((add[0][51], add[0][52]), ("100000", "100000"))   # 1 层
        for row in rows:
            if row[47] in K.BENEFIT_KINDS or row[47] == K.CONSUME_KIND:
                # 前置2 = 187 ConditionUnique（自身持有月讲），固有列不许留空（留空 = C7050）
                self.assertEqual(row[13], "187")
                self.assertEqual(row[14], "0")
                self.assertEqual(row[19], K.UID)
                self.assertEqual(row[28], "4")        # puller 4 OneOfExceptMyself
                self.assertEqual(row[29], "Red")

    def test_no_trigger_row_carries_a_dead_limit(self):
        """平衡第二批（2026-09-27）：有瞬发触发的行 c34 写 "0"/空串 = 限 0 次、永不触发；
        能力 3 #1–#5 已按作者「让生效不限制次数」改成 (None)。"""
        rows = {key: [[str(x) for x in r["row_final"]] for r in ABILITY_PLAN["keys"][key]["records"]]
                for key in K.ABILITY_KEYS}
        self.assertEqual(K.dead_trigger_limit_problems(rows), [])
        slot3 = rows[f"{K.CID}{K.OVERRIDE_SLOT}"]
        self.assertEqual([r[34] for r in slot3[1:6]], ["(None)"] * 5)
        tampered = copy.deepcopy(rows)
        tampered[f"{K.CID}{K.OVERRIDE_SLOT}"][1][34] = "0"
        self.assertEqual(len(K.dead_trigger_limit_problems(tampered)), 1)

    def test_precondition_188_is_never_used(self):
        """前置 188 数的是实例数（恒为 1）；层数门只能走前置 187 或 during 134（裁决 §8）。"""
        for key, _block, record in all_records():
            row = record["row_final"]
            for slot, col in ((1, 6), (2, 13), (3, 20)):
                self.assertNotIn(row[col], ("188", "144"),
                                 f"{key}#{record['index']} precondition{slot}")

    def test_ability_slot6_first_record_carries_the_15s_cooldown(self):
        record = ABILITY_PLAN["keys"][f"{K.CID}6"]["records"][0]
        self.assertEqual(record["cells"]["35"], "900")          # 60 帧 = 1 秒
        self.assertIn("CT15秒", record["desc_expected"])
        self.assertEqual(record["row_final"][35], "900")

    def test_panel_texts_pass_the_batch_rules(self):
        for entry in LEADER_PLAN["rows"]:
            self.assertEqual(KL.panel_problems(entry["desc_expected"]), [], entry["desc_expected"])
        for key, _block, record in all_records():
            self.assertEqual(KL.panel_problems(record["desc_expected"]), [],
                             f"{key}#{record['index']}")
        # 「技能强化」条目不写数字与时间（裁决 §3）
        text = DESIGN["plan"]["texts"]["custom_ability_string"]["rows"][0]["text"]
        self.assertEqual(KL.panel_problems(text, skill_flag=True), [], text)

    def test_texts_have_no_placeholder_left(self):
        self.assertEqual(MS.text_placeholders(MS.get_spec("nicola")), [])
        self.assertEqual(DESIGN["texts"]["name"], "妮可拉")

    def test_voice_route_is_change_skill_flag(self):
        route = DESIGN["voice"]["route"]
        self.assertEqual(int(route["kind"]), K.VOICE_ROUTE["kind"])
        self.assertEqual([str(x) for x in route["character_c9_c16"]],
                         KL.voice_route(K.CODE, K.VOICE_ROUTE))
        self.assertEqual(route["switched_action_skill"]["key"], K.VOICE_KEY)
        self.assertEqual(len(DESIGN["voice"]["lines"]), 22)


class DesignTreeStaticTests(unittest.TestCase):
    """两棵 composed_tree 的静态形状（不需要官方基线）。"""

    def trees(self):
        return {level: copy.deepcopy(SKILL_PLAN[f"tree_plan_{level}"]["composed_tree"])
                for level in K.SKILL_LEVELS}

    def test_root_header_keeps_skill_damage_attribution(self):
        for level, tree in self.trees().items():
            self.assertEqual(tree[0], "ActionDsl", level)
            # tree[10] = buffTargetAs：0 = 自动档 = 技能伤害（写 2/3/4 技伤加成全失效）
            self.assertEqual(tree[10], 0, level)

    def test_no_conditionals_and_no_bare_donothing_branch(self):
        """``Conditionals`` 空分支写 ``["DoNothing"]`` = F1009；本树根本没有 Conditionals。"""
        for level, tree in self.trees().items():
            self.assertEqual(list(wf_dsl.iter_dsl_commands(tree, "Conditionals")), [], level)
            for cmd in wf_dsl.iter_dsl_commands(tree, "FindAllSubjects"):
                self.assertEqual(cmd[8], ["DoNothing"], level)   # IfTargetNotFound 位，官方同形

    def test_retarget_effects_returns_official_paths(self):
        for level, tree in self.trees().items():
            K.retarget_effects(tree)
            refs = {str(c[2][1]) for c in wf_dsl.iter_dsl_commands(tree, "ShowEffect")}
            self.assertEqual(refs, set(K.EFFECT_RETARGET.values()), level)
            for cmd in wf_dsl.iter_dsl_commands(tree, "ShowEffect"):
                if cmd[1] == K.DUMMY_EFFECT_LABEL:
                    # 官方 donor 的 ダミー演出 这一位是 true（同树「全体演出」才是 false）
                    self.assertIs(cmd[K.DUMMY_EFFECT_FLAG_INDEX], True, level)

    def test_design_tree_already_carries_the_donor_boolean(self):
        """设计稿已按 kit 的实读更正回写；retarget 前后这一位都应是 true。"""
        for level, tree in self.trees().items():
            for cmd in wf_dsl.iter_dsl_commands(tree, "ShowEffect"):
                if cmd[1] == K.DUMMY_EFFECT_LABEL:
                    self.assertIs(cmd[K.DUMMY_EFFECT_FLAG_INDEX], True, level)

    def test_hit_area_params23_stays_zero(self):
        """判定区 params[23]（命令下标 24）写 4 = 按直击结算，技伤加成全失效。"""
        for level, tree in self.trees().items():
            for cmd in wf_dsl.iter_dsl_commands(tree, "CreateHitArea"):
                self.assertEqual(cmd[24], 0, level)

    def test_trees_roundtrip_through_amf3(self):
        for level, tree in self.trees().items():
            raw = wf_dsl.encode_amf3(tree)
            self.assertEqual(wf_dsl.parse_dsl(raw)["tree"], tree, level)

    def test_write_dsl_checked_rejects_the_wrapper_shell(self):
        """``write_dsl`` 只吃裸树；喂 ``{tree, numbers}`` 壳 = 进战斗 F1034。"""
        with self.assertRaises(K.KitError):
            K.write_dsl_checked(None, "x", {"tree": [], "numbers": []})
        with self.assertRaises(K.KitError):
            K.write_dsl_checked(None, "x", ["NotActionDsl"])


# ---------------------------------------------------------------- 2. 官方基线

@unittest.skipUnless(_BASELINE, "需要 .cdn/cn 官方归档与 live store")
class RowAssemblyTests(unittest.TestCase):
    def test_leader_rows_match_design_describe_and_row_final(self):
        rows, evidence = K.build_leader_rows(ctx(), DESIGN)
        self.assertEqual(len(rows), K.LEADER_ROWS)
        for entry, ev in zip(LEADER_PLAN["rows"], evidence):
            self.assertEqual(ev["describe"], entry["desc_expected"])
        K.ban_forbidden_leader_kinds(rows)

    def test_ability_rows_match_design_describe_and_row_final(self):
        rows_by_key, evidence = K.build_ability_rows(ctx(), DESIGN)
        self.assertEqual(sorted(rows_by_key), sorted(K.ABILITY_KEYS))
        self.assertEqual(sum(len(v) for v in rows_by_key.values()), K.ABILITY_RECORDS)
        self.assertEqual(len(evidence), K.ABILITY_RECORDS)

    def test_row_final_drift_is_caught(self):
        entry = copy.deepcopy(LEADER_PLAN["rows"][0])
        entry["row_final"][49] = "999999"
        with self.assertRaises(K.KitError):
            K._check_row_final("leader#1", [str(x) for x in LEADER_PLAN["rows"][0]["row_final"]],
                               entry)

    def test_describe_drift_is_caught(self):
        design = copy.deepcopy(DESIGN)
        design["plan"]["leader_ability"]["rows"][0]["desc_expected"] = "赋予全队(火) 攻击力 1%→2%"
        with self.assertRaises(K.KitError):
            K.build_leader_rows(ctx(), design)


@unittest.skipUnless(_BASELINE, "需要 .cdn/cn 官方归档与 live store")
class SkillTreeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.donors = K.donor_command_index(ctx())

    def test_every_donor_tree_is_readable(self):
        self.assertEqual(sorted(K.SHAPE_DONORS), sorted(K.SHAPE_DONORS))
        for name, path in K.SHAPE_DONORS.items():
            tree = ctx().template_dsl(path)
            self.assertEqual(tree[0], "ActionDsl", name)

    def test_trees_pass_the_donor_and_dsl_gates(self):
        for level in K.SKILL_LEVELS:
            tree, gates = K.build_skill_tree(ctx(), DESIGN, level, [], self.donors)
            self.assertEqual(gates["buff_target_as"], 0)
            self.assertEqual(set(gates["effect_refs"]), set(K.EFFECT_RETARGET.values()))
            self.assertEqual(K.donor_gate_problems(tree, self.donors), [])
            self.assertEqual(K.dsl_gate_problems(tree, element=K.ELEMENT), [])

    def test_donor_gate_catches_a_tampered_parameter_shape(self):
        """裸数值进 Array 参 = 详情页 F1034；这条闸门必须当场抓住。"""
        tree, _ = K.build_skill_tree(ctx(), DESIGN, "1", [], self.donors)
        broken = copy.deepcopy(tree)
        cna = next(iter(wf_dsl.iter_dsl_commands(broken, "CreateNormalAttack")))
        cna[6] = 10                                   # [{'min':10,'max':10}] → 裸数值
        self.assertTrue(K.donor_gate_problems(broken, self.donors))

    def test_donor_gate_catches_an_unlisted_cell_change(self):
        tree, _ = K.build_skill_tree(ctx(), DESIGN, "1", [], self.donors)
        broken = copy.deepcopy(tree)
        hide = next(iter(wf_dsl.iter_dsl_commands(broken, "HideCharacter")))
        hide[2] = 999                                  # HideCharacter 不许改任何一位
        self.assertTrue(K.donor_gate_problems(broken, self.donors))

    def test_buff_target_as_drift_is_rejected(self):
        design = copy.deepcopy(DESIGN)
        design["plan"]["skills"]["tree_plan_1"]["composed_tree"][10] = 3
        with self.assertRaises(K.KitError):
            K.build_skill_tree(ctx(), design, "1", [], self.donors)


# ---------------------------------------------------------------- 3. 已构建的 workspace

@unittest.skipUnless(WORKSPACE.is_dir(), "workspace work/character_packs/ma-nicola 尚未构建")
class PackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ctx = ctx()
        report = WORKSPACE / "evidence/kit-report.json"
        cls.report = json.loads(report.read_text("utf-8")) if report.is_file() else None

    def test_kit_report_exists_and_is_this_character(self):
        self.assertIsNotNone(self.report, "先跑 --step kit")
        self.assertEqual(self.report["cid"], K.CID)
        self.assertEqual(self.report["code"], K.CODE)
        self.assertEqual(self.report["batch"], "midautumn-20260920")
        self.assertIn(self.report["status"], (KL.DRAFT, KL.READY))
        self.assertEqual(self.report["unique_conditions"], [K.UID])
        self.assertEqual(sorted(self.report["unique_condition"]), [K.UID])
        self.assertIn("panel-description-override-v2", self.report["required_capabilities"])

    def test_report_programs_are_the_two_skill_levels(self):
        programs = self.report["skills"]["programs"]
        self.assertEqual(len(programs), len(K.SKILL_LEVELS))
        for level in K.SKILL_LEVELS:
            path = self.ctx.program_path(level)
            self.assertTrue(any(p == path or p == wf_dsl.dsl_logical(path) for p in programs),
                            f"{level} missing from {programs}")

    def test_package_carries_six_ability_keys_and_the_leader_key(self):
        ability = self.ctx.pkg_flat(KL.ABILITY)
        for key in K.ABILITY_KEYS:
            self.assertIn(key, ability)
            rows = self.ctx.csv_split(ability[key])
            KL.check_ability_key(rows, key, K.CODE, int(key[-1]))
        leader = self.ctx.pkg_flat(KL.LEADER)
        self.assertEqual(len(self.ctx.csv_split(leader[str(K.CID)])), K.LEADER_ROWS)

    def test_package_carries_the_custom_ability_string(self):
        cas = self.ctx.pkg_flat(KL.CAS)
        self.assertIn(K.CAS_CHANGE_SKILL, cas)
        self.assertEqual(KL.panel_problems(self.ctx.csv_split(cas[K.CAS_CHANGE_SKILL])[0][0],
                                           skill_flag=True), [])
        self.assertIn(K.CAS_OVERRIDE, cas)
        override = self.ctx.csv_split(cas[K.CAS_OVERRIDE])[0][0]
        panel = json.loads((ROOT / "work/character_packs/midautumn-20260920/rework1"
                            / "panel/nicola.json").read_text(encoding="utf-8"))
        want_lines = [line["text"] for ability in panel["abilities"]
                      if ability["index"] == K.OVERRIDE_SLOT for line in ability["lines"]]
        # 第三轮面板合并（2026-09-27，wf_balance_20260927c_panels）：面板镜像已是合并稿（3 行）；主会话暂存回写候选
        # （manifest.snapshot.revision_20260927d.source == 该模块）之前，包里仍是改前 4 行。
        import wf_balance_20260927c_panels as P3
        slot = P3.PANELS_BY_CAS[K.CAS_OVERRIDE]
        manifest = json.loads((WORKSPACE / "package/manifest.json").read_text(encoding="utf-8"))
        pending_c = (manifest.get("snapshot", {}).get("revision_20260927d") or {}).get("source") != P3.SOURCE
        self.assertEqual(want_lines, [P3._strip_icon(line) for line in slot["after"]])
        self.assertEqual(override, "\n".join(slot["before"] if pending_c else slot["after"]))
        if pending_c:
            want_lines = [P3._strip_icon(line) for line in slot["before"]]
        # 多记录槽（9 条记录）的覆盖串行数＝面板行数。
        self.assertEqual(len(override.split("\n")), len(want_lines))
        # 能力 3 整键主位限制 ⇒ 已构建包里的覆盖串每行都必须带主位限制图标，不许用字面「Ⓜ」。
        for line in override.split("\n"):
            self.assertEqual(KL.panel_problems(line), [], line)
            self.assertTrue(line.startswith(K.MAIN_ICON), line)
        self.assertNotIn("Ⓜ", override)

    def test_package_carries_the_unique_condition_and_its_icon(self):
        unique = self.ctx.pkg_flat(KL.UNIQUE)
        self.assertIn(K.UID, unique)
        row = self.ctx.csv_split(unique[K.UID])[0]
        self.assertEqual(len(row), KL.UNIQUE_NCOLS)
        self.assertEqual(row[1], K.UNIQUE_NAME)
        self.assertEqual(row[2], K.UC_ICON_ROW)
        self.assertEqual((row[3], row[4]), ("99999999", "99"))
        icon = self.ctx.pack.pkg_path("common", K.UC_ICON_LOGICAL)
        self.assertTrue(icon.is_file(), icon)
        image = self.ctx.png_open(icon.read_bytes())
        self.assertEqual(image.size, (48, 48))
        # alpha 必须与官方 frame donor 逐字节一致（图集 alpha 门禁）
        raw = self.ctx.official_read(K.UC_ICON_FRAME_DONOR)
        if raw is not None:
            frame = self.ctx.png_open(raw)
            self.assertEqual(image.getchannel("A").tobytes(), frame.getchannel("A").tobytes())

    def test_action_skill_energy_matches_the_design(self):
        energy = DESIGN["plan"]["skills"]["energy"]
        inner = self.ctx.pkg_nested(K.CODE)
        self.assertEqual(sorted(inner), sorted(K.SKILL_LEVELS))
        for level in K.SKILL_LEVELS:
            self.assertEqual(inner[level][4], str(energy[level]["c4"]), level)
            self.assertEqual(inner[level][5], str(energy[level]["c5"]), level)
            self.assertEqual(inner[level][7], self.ctx.program_path(level), level)

    def test_character_row_carries_the_voice_route(self):
        row = self.ctx.csv_split(self.ctx.pkg_flat(KL.CHARACTER)[str(K.CID)])[0]
        self.assertEqual(row[9:17], KL.voice_route(K.CODE, K.VOICE_ROUTE))
        self.assertEqual(row[27], str(K.CID))         # c27 identity 写自身 cid（上批口径）
        self.assertEqual(row[26], "Supporter")
        self.assertEqual(list(row[19:25]), list(K.ABILITY_KEYS))

    def test_switched_action_skill_key_is_present(self):
        # 嵌套表：外层键下是 {档位: 内层行}，不能按平表解（会 zlib 解压失败）
        raw = (WORKSPACE / "package/roots/common" / KL.SWITCHED).read_bytes()
        keys = core.read_orderedmap_raw_rows_from_bytes(raw, KL.SWITCHED).keys
        self.assertIn(K.VOICE_KEY, keys)
        inner = self.ctx.pkg_nested(K.VOICE_KEY, KL.SWITCHED)
        self.assertEqual(sorted(inner), sorted(K.SKILL_LEVELS))

    def test_skill_dsl_readback_matches_the_gates(self):
        for level in K.SKILL_LEVELS:
            logical = wf_dsl.dsl_logical(self.ctx.program_path(level))
            raw = (WORKSPACE / "package/roots/common" / logical).read_bytes()
            tree = self.ctx.amf_parse(raw)
            self.assertEqual(tree[0], "ActionDsl", level)
            self.assertEqual(tree[10], 0, level)
            self.assertEqual(K.dsl_gate_problems(tree, element=K.ELEMENT), [], level)
            refs = {str(c[2][1]) for c in wf_dsl.iter_dsl_commands(tree, "ShowEffect")}
            families = self.report.get("effect_families") or []
            if not families:
                # 未克隆 ⇒ 直接引用官方路径（零图集增量）
                self.assertEqual(refs, set(K.EFFECT_RETARGET.values()), level)
            else:
                for ref in refs:
                    self.assertTrue(any(ref.startswith(d + "/") for d in families)
                                    or ref in K.EFFECT_RETARGET.values(), ref)

    def test_claims_cover_every_self_owned_key(self):
        claims = json.loads((WORKSPACE / "evidence/table_claims.json").read_text("utf-8"))
        blob = json.dumps(claims, ensure_ascii=False)
        for key in (*K.ABILITY_KEYS, str(K.CID), K.CAS_CHANGE_SKILL, K.VOICE_KEY):
            self.assertIn(key, blob, key)


if __name__ == "__main__":
    unittest.main()
