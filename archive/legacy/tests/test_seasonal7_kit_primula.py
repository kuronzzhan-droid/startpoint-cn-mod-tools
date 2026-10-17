"""普莉姆拉·浴衣 kit：官方 donor 行 / 技能树拼装与设计一致，静态门禁负向用例，特效 sheet 钩子解析。

只读：不写 workspace（需要 live store 与官方基线时自动跳过对应用例）。
框架 ``S7Pack.template_dsl`` 读取时会顺手改写 ``evidence/template_sources.json``（框架问题，已上报），
本模块给共享 PACK 关掉来源登记，保证测试不改 workspace 证据；门禁负向用例的 gates.json 写到临时目录。
"""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_seasonal7_kit_primula as K  # noqa: E402


def _pack():
    import wf_seasonal7_common as C
    import wf_seasonal7_specs as S
    try:
        pack = C.S7Pack(S.get_spec("primula"))
        if pack.official_read(K.ABILITY, "common") is None:
            return None
        pack._record_source = lambda *a, **k: None     # 读接口不写 evidence/template_sources.json
        return pack
    except Exception:            # noqa: BLE001
        return None


PACK = _pack()
ROOT = Path(__file__).resolve().parents[2]


def _families():
    out = []
    for fam in K.EFFECT_FAMILIES:
        donor = fam["src_dir"].rsplit("/", 1)[-1]
        dst = f"battle/effect/skill_unique/{K.CODE}_{fam['dst_subdir']}"
        out.append({"src_dir": fam["src_dir"], "dst_dir": dst, "donor": donor,
                    "dst_name": dst.rsplit("/", 1)[-1], "copied_bases": sorted(fam["fx_names"])})
    return out


class PureTests(unittest.TestCase):
    def test_timeline_sound_report_flags_unresolved_and_malformed(self):
        have = {"sound_effect/element/se_resistance_quick.mp3"}
        tl = {"sounds": [{"path": "sound_effect/element/se_resistance_quick", "begin": 2},
                         {"path": "sound_effect/magic/se_resistance_quick", "begin": 5},   # 前缀写错
                         {"begin": 9}, "sound_effect/element/se_energy_inhalation"]}
        resolved, probs = K.timeline_sound_report(tl, have.__contains__)
        self.assertEqual(resolved, {"sound_effect/element/se_resistance_quick": True,
                                    "sound_effect/magic/se_resistance_quick": False})
        self.assertTrue(any("unresolved: sound_effect/magic/se_resistance_quick.mp3" in p for p in probs), probs)
        self.assertEqual(sum("has no path" in p for p in probs), 2, probs)
        self.assertEqual(K.timeline_sound_report({"sounds": []}, have.__contains__), ({}, []))
        self.assertEqual(K.timeline_sound_report({"sequences": []}, have.__contains__), ({}, []))
        self.assertTrue(K.timeline_sound_report({"sounds": {"path": "x"}}, have.__contains__)[1])
        self.assertTrue(K.timeline_sound_report(["not", "a", "timeline"], have.__contains__)[1])
        # 带扩展名的 path 会被拼成 .mp3.mp3，同样拦下
        self.assertTrue(K.timeline_sound_report({"sounds": [{"path": "sound_effect/element/se_resistance_quick.mp3"}]},
                                                have.__contains__)[1])

    def test_integration_pending_template_placeholders_vs_integrated(self):
        import wf_seasonal7_voice as V
        voice = {s: f"character/{K.CODE}/voice/{s}.mp3" for s in V.SLOTS}
        # 母本占位：13 条 battle/ally + 6 条母本 home 名，speech 指向母本名，全部 owner=assets
        template_home = [f"home/tpl_{i}" for i in range(6)]
        placeholder_files = {lg for s, lg in voice.items()
                             if not s.startswith("home/") and s not in ("battle/matched_skill_ready", "battle/skill_2",
                                                                         "battle/skill_3")}
        placeholder_files |= {f"character/{K.CODE}/voice/{h}.mp3" for h in template_home} | set(K.PIXEL_SHEETS)
        owners = {f"common:{lg}": "assets" for lg in placeholder_files}
        speech = [["0", "2", "", "泳装台词", h] for h in template_home] +                  [["2", "", "", "j", "ally/join"], ["1", "", "1", "e", "ally/evolution"]]
        got = K.integration_pending(speech, owners, placeholder_files)
        self.assertFalse(got["clear"])
        self.assertEqual(set(got["voice"]["slots_missing"]),
                         {*V.HOME_SLOTS, "battle/matched_skill_ready", "battle/skill_2", "battle/skill_3"})
        self.assertEqual(got["voice"]["speech_paths_outside_plan"], template_home)
        self.assertFalse(got["pixel"]["clear"])
        # 装好：22 条 owner=voice、speech 走规划槽、像素 owner=pixel
        files = set(voice.values()) | set(K.PIXEL_SHEETS) | {f"character/{K.CODE}/voice/{template_home[0]}.mp3"}
        owners = {f"common:{lg}": "voice" for lg in voice.values()}
        owners.update({f"common:{lg}": "pixel" for lg in K.PIXEL_SHEETS})
        speech = [["0", "2", "", "浴衣台词", h] for h in V.HOME_SLOTS] + speech[6:]
        got = K.integration_pending(speech, owners, files)
        # 母本旧语音残留：报告且 voice 不 clear（Integrate 必须删掉不再被 speech 引用的母本语音）
        self.assertFalse(got["voice"]["clear"], got)
        self.assertEqual(got["voice"]["template_voice_files_left"], [f"character/{K.CODE}/voice/{template_home[0]}.mp3"])
        files.discard(f"character/{K.CODE}/voice/{template_home[0]}.mp3")
        got = K.integration_pending(speech, owners, files)
        self.assertTrue(got["clear"], got)
        # 像素内容问题（pixel_problems 非空）→ 不 clear；空列表 → clear
        self.assertFalse(K.integration_pending(speech, owners, files, ["x != store form"])["pixel"]["clear"])
        self.assertTrue(K.integration_pending(speech, owners, files, [])["clear"])
        # 任一缺项都回到 not clear
        owners[f"common:{voice['battle/skill_3']}"] = "assets"
        self.assertFalse(K.integration_pending(speech, owners, files)["clear"])
        owners[f"common:{voice['battle/skill_3']}"] = "voice"
        owners[f"common:{K.PIXEL_SHEETS[1]}"] = "assets"
        self.assertFalse(K.integration_pending(speech, owners, files)["clear"])
        owners[f"common:{K.PIXEL_SHEETS[1]}"] = "pixel"
        self.assertFalse(K.integration_pending(speech[:7], owners, files)["clear"])

    def test_review_md_verdict_reads_fix_round_section_only(self):
        md = chr(10).join(["## 2. 逐角色", "### primula 普莉姆拉 — FAIL（待主控拍板）",
                           "## 5. 修复轮复核（独立复核）", "#### zehr — PASS",
                           "#### primula 普莉姆拉 — PASS（豁免条件成立）", ""])
        self.assertEqual(K._review_md_verdict(md), "PASS")
        self.assertIsNone(K._review_md_verdict(md.split("## 5.")[0]))           # 修复轮复核段还没出现 → pending
        self.assertEqual(K._review_md_verdict(md.replace("— PASS（豁免", "— FAIL（豁免")), "FAIL")

    def test_fx_store_bytes_is_magic_swap_not_reencode(self):
        import wf_assets
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "a.png"
            body = bytes([0]) + b"IHDR-not-really-decoded"
            f.write_bytes(wf_assets.PNG_REAL + body)
            self.assertEqual(K.fx_store_bytes(f), wf_assets.PNG_FAKE + body)
            f.write_bytes(wf_assets.PNG_FAKE + body)
            self.assertEqual(K.fx_store_bytes(f), wf_assets.PNG_FAKE + body)
            f.write_bytes(b"GIF89a")
            with self.assertRaises(K.KitError):
                K.fx_store_bytes(f)

    def test_apply_edits_asserts_old_value(self):
        with self.assertRaises(K.KitError):
            K._apply_edits(["a", "b"], {1: ("x", "y")}, "t")
        self.assertEqual(K._apply_edits(["a", "b"], {1: ("b", "y")}, "t"), ["a", "y"])

    def test_signature_flags_donothing_in_expression_slot(self):
        tree = ["ActionDsl", 1, ["None"], False, False, False, False, False, False, False, 0,
                ["Block", [["Command", ["ConditionalsConditionAccumulationNumber", ["DCUnique", 1], 5,
                                        ["Block", []], ["DoNothing"]]]]]]
        probs = K.signature_problems(tree, None)
        self.assertTrue(any("F1009" in p for p in probs), probs)

    def test_vlv_condition_without_key_fails(self):
        cc = ["Command", ["CreateCondition", 30, [["ACDirectDamage", [{"min": 1, "max": 1}],
                                                   [{"min": 1, "max": 1, "vlv": [{"vid": 1, "min": 0, "max": 1}]}],
                                                   [{"min": 1, "max": 1}]]],
                          [], ["None"], True, True, "", ["None"], False, 0, 3, False]]
        found = K.create_conditions(["Block", [cc]])
        self.assertEqual(found[0]["key"], "")
        self.assertTrue(found[0]["vlv"])

    def test_split_preflight_conflicts_only_own_claims_are_red(self):
        """改版：串行发布时别人角色的共享表漂移不算本角色缺陷，但自己认领的键必须照样判红。"""
        claims = [{"root": "common", "logical_path": K.ABILITY, "outer_keys": ["1699921", "1699923"]},
                  {"root": "common", "logical_path": K.CAS, "outer_keys": [K.CAS_KEY]}]
        conflicts = [{"claim": f"{K.ABILITY}:1299911", "kind": "unclaimed_change"},
                     {"claim": f"{K.ABILITY}:1699923", "kind": "unclaimed_change"},
                     {"claim": f"{K.CAS}:{K.CAS_KEY}", "kind": "unclaimed_change"},
                     {"claim": "master/skill/action_skill.orderedmap:psychic_yuki_swim/1", "kind": "x"}]
        own, foreign = K.split_preflight_conflicts(conflicts, claims)
        self.assertEqual([c["claim"] for c in own],
                         [f"{K.ABILITY}:1699923", f"{K.CAS}:{K.CAS_KEY}"])
        self.assertEqual([c["claim"] for c in foreign],
                         [f"{K.ABILITY}:1299911", "master/skill/action_skill.orderedmap:psychic_yuki_swim/1"])
        self.assertEqual(K.split_preflight_conflicts([], claims), ([], []))

    def test_foreign_live_drift_blocks_publish_readiness(self):
        """审查第 4 条：跨角色漂移不算本角色缺陷，但共享表是整文件投递，不能和「可发布」同屏。"""
        self.assertEqual(K.publish_blockers_for([]), [])
        foreign = [{"claim": f"{K.ABILITY}:1299911", "kind": "unclaimed_change"},
                   {"claim": "master/skill/action_skill.orderedmap:psychic_yuki_swim/1", "kind": "x"}]
        blockers = K.publish_blockers_for(foreign)
        self.assertEqual(len(blockers), 1)
        self.assertIn("flow rebase", blockers[0])
        self.assertIn("2 处", blockers[0])
        self.assertNotIn("force", blockers[0].split("禁止")[0])     # 只在「禁止用 force」里出现

    def test_skill_desc_is_short_and_uses_new_unique_name(self):
        """作者要求：技能描述不再写太复杂；固有状态统一叫「夜百合」。"""
        self.assertLess(len(K.SKILL_DESC), 100)
        self.assertNotIn("百合夜", K.SKILL_DESC)
        self.assertIn("夜百合", K.SKILL_DESC)
        for key in (K.KEY_DD, K.KEY_FS, K.KEY_PC, K.UNIQUE_NAME, K.CAS_TEXT):
            self.assertNotIn("百合夜", key)
        self.assertEqual(K.UNIQUE_EDITS[1][1], "夜百合")
        self.assertEqual(K.UNIQUE_EDITS[4], ("10", "20"))

    def test_panel_text_rules_reject_cap_wording_and_numbered_skill_enhance(self):
        """rev2 文案规则：① 面板不出现「无上限」且有上限就写上限；② 技能强化条目不写数字与时间。"""
        # 本角色全部玩家可见文案现状：两条规则都过，且「无上限」出现 0 次
        self.assertEqual(K.panel_text_problems(), [])
        self.assertEqual(sum(t.count("无上限") for t in K.PANEL_TEXTS.values()), 0)
        self.assertIn("CAS_TEXT", K.PANEL_TEXTS)
        self.assertIn("SKILL_DESC", K.PANEL_TEXTS)
        # 负向 ①：任何替代说法都要红（后三条是改版 2 审查第 3 条补的漏网写法）
        for bad in ("每层“夜百合”追加+10%伤害（无上限）", "每层“夜百合”追加+10%伤害，可无限叠加",
                    "每层追加+10%伤害，不设上限", "每层追加+10%伤害，没有上限", "每层追加+10%伤害，上限无"):
            self.assertTrue(K.panel_text_problems({"X": bad}), bad)
        # 负向 ②：「强化『技能名』」条目写了数字或秒数要红；倒装语序同样要红（审查第 3 条）
        self.assertTrue(K.panel_text_problems({"X": "强化『紫百合·烟花扇舞』：威力+50%"}))
        self.assertTrue(K.panel_text_problems({"X": "强化『紫百合·烟花扇舞』，持续十五秒"}))
        self.assertTrue(K.panel_text_problems({"X": "『紫百合·烟花扇舞』的效果得到强化：威力+50%、持续15秒"}))
        # 正向 ②：只写强化了什么 = 过；「强化弹射」不带引号，不许被误判
        self.assertEqual(K.panel_text_problems({"X": "强化『紫百合·烟花扇舞』的效果"}), [])
        self.assertEqual(K.panel_text_problems({"X": "每35连击，强化弹射伤害提升50%"}), [])

    def test_capped_growth_must_state_its_cap(self):
        """规则 1 第三条（审查第 2 条）：夜百合真上限 20 层，逐层成长的文案必须写出上限。"""
        self.assertEqual(K.CAP_PHRASE, f"最多{K.UNIQUE_MAX}层")
        self.assertEqual(K.UNIQUE_MAX, "20")
        self.assertEqual(K.UNIQUE_EDITS[4], ("10", K.UNIQUE_MAX))
        self.assertIn(K.CAP_PHRASE, K.CAS_TEXT)
        # 负向：把上限句删掉必须红（否则这条门禁是摆设）
        self.assertTrue(K.panel_text_problems({"CAS_TEXT": K.CAS_TEXT.replace(f"（{K.CAP_PHRASE}）", "")}))
        # 上限必须与固有状态的 max_accumulation 和 DSL 的钳位是同一个数
        self.assertEqual(int(K.UNIQUE_MAX), K.UNIQUE_CAP)

    def test_invoke_skill_row_must_be_main_slot_locked(self):
        """审查第 1 条：629 InvokeSkill 行必须主位绑定（共鸣是编成条件，挡不住副位装配）。"""
        edits = dict(K.ABILITY_PLAN[1][2][3])
        self.assertEqual(edits[6], ("0", "202"))             # precondition1 = OwnerIsMain
        self.assertEqual(edits[13], ("0", "2"))              # 暗共鸣退到 precondition2
        self.assertEqual(edits[16], ("", "600000"))
        self.assertEqual(edits[17], ("", "600000"))
        self.assertEqual(edits[18], ("", "Black"))
        self.assertEqual(edits[1], ("false", "true"))        # c1 保持 true，面板只画一个 Ⓜ
        self.assertNotIn(9, edits)                           # 旧的 precondition1 共鸣列必须腾空
        self.assertNotIn(11, edits)
        # 检查器本身：正形过、缺主位门红、values[0]=false 也算过
        def row(pre1, pre2_kind="0"):
            r = ["x"] * 126
            r[1], r[47], r[6], r[13], r[20] = "true", "629", pre1, pre2_kind, "0"
            return r
        self.assertEqual(K.unison_lock_problems({"1699921": [row("202")]}), [])
        self.assertTrue(K.unison_lock_problems({"1699921": [row("2")]}))
        off = row("2")
        off[1] = "false"
        self.assertEqual(K.unison_lock_problems({"1699921": [off]}), [])
        # 非 629 行不受管
        plain = row("2")
        plain[47] = "388"
        self.assertEqual(K.unison_lock_problems({"1699921": [plain]}), [])

    def test_lily_layer_bonuses_target_dark_party_and_assist_balls(self):
        """改版 3：每层夜百合的受益面 = 暗属性角色全体 + 协力球，协力球读不到的 kind 不准挂协力球目标。"""
        self.assertEqual((K.LILY_PARTY_TARGET, K.LILY_PARTY_GROUPS, K.LILY_ASSIST_TARGET), ("5", "Black", "8"))
        self.assertIn("0", K.LILY_MULTIBALL_READABLE)          # AttackPoint 走 multiball 合计器
        self.assertIn("410", K.LILY_MULTIBALL_UNREADABLE)      # 独立乘区直击只读自身 totalizer

        def row(kind, target, groups=""):
            r = ["" for _ in range(126)]
            r[5], r[97], r[104] = "1", K.LAYER_TRIGGER, K.UID
            r[109], r[110], r[111] = kind, target, groups
            return r

        good = {f"{K.CID}3": [row("0", "5", "Black"), row("0", "8"), row("410", "5", "Black")]}
        self.assertEqual(K.lily_layer_target_problems(good), [])
        # 负向 1：回到「自身」
        self.assertTrue(K.lily_layer_target_problems({f"{K.CID}3": [row("0", "5", "Black"), row("0", "8"),
                                                                    row("410", "0")]}))
        # 负向 2：漏掉协力球那条（只给暗属性全体）
        self.assertTrue(K.lily_layer_target_problems({f"{K.CID}3": [row("0", "5", "Black"), row("410", "5", "Black")]}))
        # 负向 3：把读不到的 410 发给协力球 —— 死行，面板却会写「协力球」
        self.assertTrue(K.lily_layer_target_problems({f"{K.CID}3": [row("0", "5", "Black"), row("0", "8"),
                                                                    row("410", "5", "Black"), row("410", "8")]}))
        # 负向 4：目标角色组写空串（谁都不匹配的死值）
        self.assertTrue(K.lily_layer_target_problems({f"{K.CID}3": [row("0", "5"), row("0", "8"),
                                                                    row("410", "5", "Black")]}))
        # 别人的固有 / 非 during 行不受管
        other = row("0", "0")
        other[104] = "11"
        instant = row("0", "0")
        instant[5] = "0"
        self.assertEqual(K.lily_layer_rows({f"{K.CID}3": [other, instant]}), [])

    def test_rev3_delta_registry_adds_the_assist_ball_row(self):
        """改版 3 的登记表本身：列 delta 与新行都必须按登记生效，源行下标写错要当场报错。"""
        base = [["a"] * 126 for _ in range(4)]
        base[2][109], base[2][110], base[2][111] = "0", "5", "Black"
        base[3][109], base[3][110], base[3][111] = "410", "0", ""
        got = K.rev3_design_rows(f"{K.CID}3", base)
        self.assertEqual(len(got), 5)
        self.assertEqual([(r[109], r[110], r[111]) for r in got[2:]],
                         [("0", "5", "Black"), ("0", "8", ""), ("410", "5", "Black")])
        self.assertEqual(K.rev3_design_rows(f"{K.CID}1", base), base)       # 别的槽不动
        with mock.patch.dict(K.REV3_ROW_INSERT, {(f"{K.CID}3", 1): (2, {})}, clear=True):
            with self.assertRaises(K.KitError):
                K.rev3_design_rows(f"{K.CID}3", base)

    def test_invoke_skill_row_plan_points_at_the_written_string_key(self):
        """629 行的 c70/c71 必须指向 kit 自己写的 CAS 键与 ability_skill 程序（缺键＝详情页 C8601）。"""
        edits = dict(K.ABILITY_PLAN[1][2][3])
        self.assertEqual(edits[70][1], K.CAS_KEY)
        self.assertEqual(edits[71][1], K.AS_PROGRAM)
        self.assertEqual(K.SPEC["extra_keys"][K.CAS], (K.CAS_KEY,))
        self.assertTrue(K.AS_PROGRAM.startswith("battle/action/skill/action/ability_skill/"))
        row = ["x"] * 126
        row[47], row[70] = "629", K.CAS_KEY
        import wf_client_legality as LG
        self.assertEqual(LG.invoke_skill_string_problems(row, frozenset({K.CAS_KEY}), "ability"), [])
        self.assertTrue(LG.invoke_skill_string_problems(row, frozenset(), "ability"))

    def test_fx_manifest_variants(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / K.FX_MANIFEST
            out.parent.mkdir(parents=True)
            (out.parent / "a.png").write_bytes(b"x")
            src = "battle/effect/skill_unique/blackflower_wiz/blackflower_wiz.png"
            for payload in ({"sheets": {src: "a.png"}}, {src: {"png": "a.png"}},
                            [{"source": src, "file": "a.png"}]):
                out.write_text(json.dumps(payload), encoding="utf-8")
                self.assertEqual(K.fx_sheet_overrides(root), {src: out.parent / "a.png"})
            out.write_text(json.dumps({"sheets": {src: "missing.png"}}), encoding="utf-8")
            with self.assertRaises(K.KitError):
                K.fx_sheet_overrides(root)
            out.unlink()
            self.assertEqual(K.fx_sheet_overrides(root), {})


@unittest.skipIf(PACK is None, "live store / official baseline unavailable")
class OfficialBaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / K.DESIGN_JSON
        cls.design = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None

    def test_rows_legal_and_match_design(self):
        leader = K.build_leader_rows(PACK)
        ability = K.build_ability_rows(PACK)
        self.assertTrue(K.row_gates("leader_ability", leader)["ok"])
        flat = [r for k in sorted(ability) for r in ability[k]]
        gate = K.row_gates("ability", flat)
        self.assertTrue(gate["ok"])
        self.assertEqual(gate["required_capabilities"], [])
        self.assertEqual((len(leader), len(flat)), (6, 14))          # 改版：A1 2→3、A3 3→4→5
        self.assertEqual([len(ability[f"{K.CID}{s}"]) for s in range(1, 7)], [3, 2, 5, 2, 1, 1])
        invoke = [r for r in flat if r[47] == "629"]
        self.assertEqual([(r[70], r[71]) for r in invoke], [(K.CAS_KEY, K.AS_PROGRAM)])
        # 共鸣前置：夜百合两个获取来源挂 precondition1 = kind 2 Member / 600000 / Black
        for row in (ability[f"{K.CID}3"][0], ability[f"{K.CID}3"][1]):
            self.assertEqual((row[6], row[9], row[10], row[11]), ("2", "600000", "600000", "Black"))
        # 629 行（审查第 1 条）：precondition1 让位给 202 主位门，暗共鸣退到 precondition2
        row629 = ability[f"{K.CID}1"][2]
        self.assertEqual((row629[6], row629[9], row629[10], row629[11]), ("202", "", "", ""))
        self.assertEqual((row629[13], row629[16], row629[17], row629[18]), ("2", "600000", "600000", "Black"))
        self.assertEqual(row629[1], "true")                          # c1 保持 true ⇒ 面板单个 Ⓜ
        self.assertEqual(K.unison_lock_problems(ability), [])
        # 按层的三条持续行：次上限必须跟随夜百合新上限
        self.assertEqual([r[102] for r in ability[f"{K.CID}3"][2:]], ["20", "20", "20"])
        # 改版 3：每层攻击力 = 暗属性角色全体 + 协力球两条；独立乘区直击从自身改成暗属性角色全体
        self.assertEqual([(r[109], r[110], r[111]) for r in ability[f"{K.CID}3"][2:]],
                         [("0", "5", "Black"), ("0", "8", ""), ("410", "5", "Black")])
        self.assertEqual([r[113] for r in ability[f"{K.CID}3"][2:]], ["50000", "50000", "10000"])
        self.assertEqual(K.lily_layer_target_problems(ability), [])
        self.assertEqual([leader[2][100], leader[5][100]], ["20", "20"])
        self.assertEqual(ability[f"{K.CID}1"][0][51], "50000")       # 开局技能槽 50%
        self.assertEqual(ability[f"{K.CID}3"][2][113], "50000")      # 每层全队暗攻击 50%
        if self.design is not None:
            self.assertEqual(leader, [r["row"] for r in self.design["leader"]])
            for slot in range(1, 7):
                key = f"{K.CID}{slot}"
                # 设计件是上一轮的只读证据；改版 2/3 的差异逐列登记在 REV2_ROW_DELTA / REV3_ROW_*，其余仍逐字比对
                want = K.design_rows_expected(key, [r["row"] for r in self.design["abilities"][f"slot{slot}"]])
                self.assertEqual(ability[key], want)
            design_cas = {c["key"]: c["text"] for c in self.design.get("custom_strings") or []}
            self.assertEqual(design_cas, {K.CAS_KEY: K.rev2_design_cas()})
            # 登记表必须真的在管事：去掉 delta 后设计件与成品行必然不同（否则这条交叉校验是摆设）
            raw = [r["row"] for r in self.design["abilities"][f"slot1"]]
            self.assertNotEqual(ability[f"{K.CID}1"], raw)
            raw3 = [r["row"] for r in self.design["abilities"][f"slot3"]]
            self.assertNotEqual(ability[f"{K.CID}3"], K.rev2_design_rows(f"{K.CID}3", raw3))
            self.assertEqual(K.build_unique_row(PACK), self.design["unique_conditions"][0]["row"])
            self.assertEqual(K.text_row(), self.design["text"]["character_text_row"])

    def test_shared_pack_reads_do_not_write_evidence(self):
        """审查 #3 规避：共享 PACK 读官方 DSL 不得改写 workspace 的 evidence（框架读接口带登记副作用）。"""
        with mock.patch.object(PACK, "write_evidence", side_effect=AssertionError("read wrote evidence")):
            tree = PACK.template_dsl("battle/action/skill/action/rare5/combat_soldier_smr22$combat_soldier_smr22_2")
        self.assertEqual(tree[0], "ActionDsl")

    def test_unique_cap_is_twenty(self):
        row = K.build_unique_row(PACK)
        self.assertEqual((row[1], row[4]), ("夜百合", "20"))          # 上限列不能是 "" / "(None)"
        self.assertNotIn(row[4], ("", "(None)"))

    def test_trees_match_prototype_and_pass_static_checks(self):
        sig_path = ROOT / K.OFFICIAL_SIG
        sig = json.loads(sig_path.read_text(encoding="utf-8")) if sig_path.is_file() else None
        import wf_seasonal7_common as C
        for level in ("1", "2"):
            tree, log = K.compose_tree(PACK, level)
            # 35 条改版编辑 + 2026-09-27 平衡第二批 1 条（烟花削韧 p12 20→14，wf_balance_20260927b_primula）
            self.assertEqual(len(log), 36)
            self.assertEqual([e for e in log if e["param"] == "p12"],
                             [dict(block="B3_hanabi.HA_F.CNA", command="CreateNormalAttack", param="p12",
                                   old=[{"min": 20, "max": 20}], new=[{"min": 14, "max": 14}])])
            self.assertEqual(len(tree[11][1]), 2)                    # 改版：根块只剩 [B0 扇舞, B2 花园]
            # 烟花倍率变量的 cap 必须跟随夜百合新上限
            bind2 = tree[11][1][1][1][6][1][0][1][11][1][-1][1][3][1][0][1]
            self.assertEqual(bind2[:3] + bind2[4:], ["BindConditionAccumulationVariable", -17, 2, 1, 20])
            for fam in _families():
                tree, refs = C.rewrite_effect_refs(tree, fam, strict=True)
            checks = K.tree_checks(tree, sig)
            if sig is not None:
                self.assertTrue(checks["ok"], {k: checks[k] for k in ("element", "subject_binding",
                                                                     "hit_area_target", "player_side", "signature")})
            proto = ROOT / K.DESIGN_TREES[level]
            if proto.is_file():
                self.assertEqual(json.loads(proto.read_text(encoding="utf-8")), tree)
            self.assertNotIn("百合夜", json.dumps(tree, ensure_ascii=False))

    def test_ability_skill_tree_matches_prototype_and_carries_the_layer_variable(self):
        """改版 R1/R3/R8/R13：能力1#3 的 629 调用的 DSL。"""
        sig_path = ROOT / K.OFFICIAL_SIG
        sig = json.loads(sig_path.read_text(encoding="utf-8")) if sig_path.is_file() else None
        tree, log = K.compose_ability_skill_tree(PACK)
        self.assertEqual(len(log), 24)
        root = tree[11][1]
        self.assertEqual(len(root), 4)
        self.assertEqual(root[0][1], ["BindConditionAccumulationVariable", -17, 1, ["DCUnique", K.UID_INT], 1, 20])
        # 暗属性角色（33+[6]）与协力球（145+[]）各一块
        self.assertEqual([(b[1][1], b[1][2], b[1][3]) for b in root[1:3]], [(0, 33, [6]), (1, 145, [])])
        checks = K.tree_checks(tree, sig)
        if sig is not None:
            self.assertTrue(checks["ok"], {k: checks[k] for k in ("element", "subject_binding", "hit_area_target",
                                                                  "player_side", "signature")})
        self.assertEqual(checks["effect_paths"], [])
        self.assertEqual(checks["vlv_without_key"], [])
        # 贯穿时长与直击增伤**都**带 vlv（逐层成长）且都必须有固定区分键
        pierce = [c for c in checks["create_conditions"] if c["ac"] == "ACPiercing"]
        self.assertEqual([(c["key"], c["vlv"]) for c in pierce], [(K.KEY_PC, True), (K.KEY_PC, True)])
        dd = [c for c in checks["create_conditions"] if c["ac"] == "ACDirectDamage"]
        self.assertEqual([(c["key"], c["vlv"]) for c in dd], [(K.KEY_DD, True), (K.KEY_DD, True)])
        acp = root[1][1][9][1][1][1][2][0]
        self.assertEqual(acp[1][0], {"min": 1200, "max": 1200, "vlv": [{"vid": 1, "min": 0, "max": 120}]})
        acd = root[1][1][9][1][0][1][2][0]
        self.assertEqual(acd[0], "ACDirectDamage")
        self.assertEqual(acd[2][0], {"min": 1.25, "max": 1.25, "vlv": [{"vid": 1, "min": 0, "max": 0.1}]})
        proto = ROOT / K.DESIGN_AS_TREE
        if proto.is_file():
            want = json.loads(proto.read_text(encoding="utf-8"))
            self.assertEqual(want, tree)
            self.assertEqual(K._typed(want), K._typed(tree))
        # 否分支写 ["DoNothing"] 必须被静态校验抓住（F1009）
        broken = copy.deepcopy(tree)
        broken[11][1][3][1][4] = ["DoNothing"]
        self.assertTrue(any("F1009" in p for p in K.signature_problems(broken, sig)))

    def test_ability_skill_values_match_migrated_live_block(self):
        """R1 是「移动」不是重新设计：新块参数必须与被迁移的原块逐项相等，差异只许出现在白名单里。

        审查第 1 条（直击增伤丢掉 vlv 逐层成长）与第 3 条（基础时长换档位）的负向用例都在这里。
        交叉校验源是**归档包里的原块**，不是 plan.json —— plan.json 与 kit 同源，对规格级错误免疫。
        """
        tree, _ = K.compose_ability_skill_tree(PACK)
        self.assertEqual(K.migration_problems(tree), [])
        self.assertEqual(K.migration_problems(), [])                     # AS_VALUES 口径
        def mutated(**kw):
            v = {k: copy.deepcopy(x) for k, x in K.AS_VALUES.items()}
            v.update(kw)
            return K.migration_problems(values=v)

        # 负向 1：直击增伤退回不带 vlv 的常量（= 上一轮的 bug，审查第 1 条）
        self.assertTrue(any("ACDirectDamage[1]" in p for p in mutated(dd=[{"min": 1.5, "max": 1.5}])))
        # 负向 2：直击增伤混用 lv1 档基数（vlv 还在，但基数不是白名单登记的值）
        self.assertTrue(any("ACDirectDamage[1]" in p for p in
                            mutated(dd=[{"min": 0.8, "max": 0.8, "vlv": [{"vid": 1, "min": 0, "max": 0.1}]}])))
        # 负向 3：速度固定时长换成 lv1 档（不在白名单 ⇒ 必须等于迁移源）
        self.assertTrue(any("ACFixedSpeed[0]" in p for p in mutated(fs_time=[{"min": 720, "max": 720}])))
        # 负向 4：直击的基础持续时间被悄悄调高（不在白名单）
        self.assertTrue(any("ACDirectDamage[0]" in p for p in mutated(dd_time=[{"min": 1800, "max": 1800}])))
        # 负向 5：贯穿丢掉 R8 的每层延长（白名单登记的是「必须改成的样子」，改少了也判红）
        self.assertTrue(any("ACPiercing[0]" in p for p in mutated(pierce=[{"min": 1200, "max": 1200}])))
        # 负向 6：贯穿基数被悄悄调高
        self.assertTrue(any("ACPiercing[0]" in p for p in mutated(
            pierce=[{"min": 1500, "max": 1500, "vlv": [{"vid": 1, "min": 0, "max": 120}]}])))

    def test_migration_source_snapshot_matches_the_published_archive(self):
        """MIGRATION_SOURCE 是归档包 1.4.873 的逐字快照 —— 归档在场时用实际字节复核。"""
        import zlib
        import wf_dsl
        arch = ROOT.parent / K.PKG_ARCHIVE_DIRNAME / K.MIGRATION_ARCHIVE / "roots"
        if not arch.is_dir():
            self.skipTest(f"archive not present: {arch}")
        names = set(K.MIGRATION_SOURCE[K.MIGRATION_LEVEL])
        for level, want in K.MIGRATION_SOURCE.items():
            rel = (f"common/battle/action/skill/action/rare5/{K.CODE}${K.CODE}_{level}"
                   ".action.dsl.amf3.deflate")
            tree = wf_dsl.parse_dsl(zlib.decompress((arch / rel).read_bytes(), -15))["tree"]
            got = K.ac_payloads(tree, names)
            self.assertEqual({ac: occ[0] for ac, occ in got.items()}, want, f"level {level}")
        # 归档里的「＋」档正是迁移基准，且它带着两条逐层成长的 vlv 之一
        src = K.MIGRATION_SOURCE[K.MIGRATION_LEVEL]
        self.assertIn("vlv", src["ACDirectDamage"][1][0])

    def test_cas_text_carries_no_precondition_or_trigger_wording(self):
        """详情页 = 合击标记 + 前置/触发串 + CAS 正文；正文再写一遍就重复了（审查第 2 条）。"""
        self.assertEqual(K.cas_text_problems(), [])
        self.assertEqual(K.cas_text_problems("赋予暗属性角色 直接攻击伤害提升125%"), [])
        for bad in ("暗属性共鸣时，自身发动技能时，赋予…", "暗·编成≥6 时赋予…", "自身为队长时，赋予…"):
            self.assertTrue(K.cas_text_problems(bad), bad)
        self.assertLess(len(K.CAS_TEXT), 120)

    def test_switched_rows_follow_voice_convention(self):
        import wf_seasonal7_voice as V
        rows = K.build_action_rows(PACK)
        self.assertEqual({lv: r[7:24] for lv, r in rows.items()}, V.switched_rows(rows))
        self.assertEqual(V.normalize_route(K.ROUTE_COLS, K.CODE), K.ROUTE_COLS)

    def test_gates_fail_when_effect_timeline_sound_unresolved(self):
        """审查 #1 负向：SE 解析不到时 run_gates 必须记失败（旧实现只写证据、all_pass 仍为 true）。"""
        import wf_seasonal7_common as C
        if not (PACK.read_evidence("effect-families.json", {}) or {}):
            self.skipTest("package has no cloned effect families (kit step not run)")
        orig = C.S7Pack.live_locate

        def no_se(self_, logical):
            return None if logical.startswith("sound_effect/") else orig(self_, logical)

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(K, "GATES_FILE", str(Path(tmp) / "neg.json")),                     mock.patch.object(C.S7Pack, "live_locate", no_se):
                neg = K.run_gates(write_status=False)
            gates = json.loads((Path(tmp) / "neg.json").read_text(encoding="utf-8"))
            with mock.patch.object(K, "GATES_FILE", str(Path(tmp) / "pos.json")):
                pos = K.run_gates(write_status=False)
        se_fail = [f for f in neg["failures"] if f.startswith("effect timeline:") and "sound unresolved" in f]
        self.assertFalse(neg["all_pass"])
        self.assertGreaterEqual(len(se_fail), 5, neg["failures"])
        self.assertTrue(gates["effect_timeline_problems"])
        self.assertFalse(gates["release_ready_after_integration"])
        self.assertEqual([f for f in pos["failures"] if f.startswith("effect timeline:")], [])

    def test_icon_keeps_official_frame_alpha(self):
        import wf_seasonal7_common as C
        frame = C.png_open(PACK.official_read(K.ICON_FRAME_DONOR))
        icon = K.draw_icon(frame)
        self.assertEqual(icon.size, (48, 48))
        self.assertEqual(icon.getchannel("A").tobytes(), frame.getchannel("A").tobytes())
        self.assertEqual(C.png_store_bytes(icon)[:4], b"\x89png")


if __name__ == "__main__":
    unittest.main()
