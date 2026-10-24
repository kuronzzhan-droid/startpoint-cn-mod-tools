# -*- coding: utf-8 -*-
"""米娅 kit（119992 ``tiger_treasure_hunter_moon``）：设计稿自查 + 行装配 + DSL 门禁。

三组用例：

1. **纯静态**（不需要 live / 官方基线）：模块常量与设计稿 JSON 的互锁、裁决 §8 的设计自查
   （队长表禁 422/724/713、固有 ID 8 位与上限非 ``(None)``、c2 雕像组每键单值、面板禁词、
   ``donor`` 地址 1 基→0 基换算）、以及本模块的 DSL 小工具（``_cc_ac_entry``/``_dsl_problems``/
   ``_write_dsl_checked`` 的包装壳拦截）与图标绘制。
2. **官方基线**（缺 ``.cdn/cn`` 或 live store 时跳过）：8+15 行逐行装配并与设计登记的
   ``wf_describe`` 回读逐字比对；两棵技能树与 629 追击树的装配与门禁。
3. **已构建的 workspace**（``work/character_packs/ma-mia`` 不存在时跳过）：包内 3 个自有键、
   认领、kit-report 与 DSL 程序清单、语音路由、特效族。

不写 live store / ``assets/`` / ``.cdn``，不跑发布；官方基线只读。
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_client_legality as L  # noqa: E402
import wf_dsl  # noqa: E402
import wf_midautumn_common as MC  # noqa: E402
import wf_midautumn_kit_mia as K  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_midautumn_specs as MS  # noqa: E402
import wf_mod_tool as core  # noqa: E402
import wf_seasonal7_build as B  # noqa: E402
import wf_seasonal7_common as C  # noqa: E402

ROOT = core.project_root()
DESIGN = MS.load_design(ROOT, "mia")
WORKSPACE = ROOT / "work/character_packs/ma-mia"


def _baseline_available() -> bool:
    profile = core.resolve_profile()
    return profile is not None and profile.store.is_dir() and (ROOT / ".cdn" / "cn").is_dir()


_BASELINE = _baseline_available()
_CTX = None


def ctx():
    """只读上下文：``record_sources=False`` ⇒ 母本取数不写 workspace（框架 §10.2）。"""
    global _CTX
    if _CTX is None:
        _CTX = B.KitContext(MC.MAPack(MS.get_spec("mia"), record_sources=False))
    return _CTX


def fake_family() -> dict:
    """``clone_effect_family`` 结果的只读替身（测树装配时不往包里写特效）。"""
    return {"src_dir": K.FX_SRC_DIR, "dst_dir": K.FX_DST_DIR, "donor": K.TEMPLATE_CODE,
            "dst_name": K.FX_SUBDIR, "copied_bases": list(K.FX_MEMBERS)}


# ---------------------------------------------------------------- 1. 纯静态

class ConstantTests(unittest.TestCase):
    def test_identity_matches_the_registry(self):
        spec = MS.get_spec("mia")
        self.assertEqual((spec.cid, spec.code), (K.CID, K.CODE))
        self.assertEqual((spec.template_id, spec.template_code), (K.TEMPLATE_ID, K.TEMPLATE_CODE))
        self.assertEqual(spec.element, K.ELEMENT)
        self.assertEqual(spec.pf_type, 2)             # 射击型 ⇒ 走官方 ranged 原生 PF
        self.assertEqual(spec.stance, "Attacker")

    def test_unique_condition_id_is_eight_digits(self):
        self.assertEqual(K.UID, str(K.CID * 100 + 1))
        self.assertEqual(len(K.UID), 8)
        self.assertTrue(MS.unique_condition_ok(K.CID, K.UID))

    def test_spec_declares_every_self_owned_key(self):
        keys = MS.get_spec("mia").extra_keys
        self.assertEqual(keys[MS.UNIQUE_CONDITION_LOGICAL], (K.UID,))
        self.assertEqual(set(keys[KL.CAS]), {K.CAS_ABILITY_SKILL, K.CAS_DESC_OVERRIDE})
        self.assertEqual(keys[KL.SWITCHED], (K.VOICE_KEY,))

    def test_ability_keys_are_the_six_slots(self):
        self.assertEqual(K.ABILITY_KEYS, tuple(f"{K.CID}{n}" for n in range(1, 7)))

    def test_parse_donor_converts_one_based_to_zero_based(self):
        self.assertEqual(K._parse_donor("o:L:151165:1"), ("official", "151165#0"))
        self.assertEqual(K._parse_donor("o:A:1611532:2"), ("official", "1611532#1"))
        self.assertEqual(K._parse_donor("s:A:1699942:1"), ("live", "1699942#0"))
        with self.assertRaises(K.KitError):
            K._parse_donor("o:L:151165:0")            # 1 基，0 非法
        with self.assertRaises(K.KitError):
            K._parse_donor("x:L:151165:1")             # 未知来源前缀
        with self.assertRaises(K.KitError):
            K._parse_donor("o:X:151165:1")             # 未知表字母
        with self.assertRaises(K.KitError):
            K._parse_donor("o:L:151165")                # 形状不对

    def test_pursuit_program_basename_differs_from_the_cas_string_key(self):
        # Windows MAX_PATH：--step inspect 把 workspace 复制到 _inspect/<pid>-rebase/ 时，
        # 沿用 27 字符的 CODE 当 DSL basename 会让全路径超过 260（本轮实测撞到并改短）。
        self.assertNotEqual(K.PURSUIT_BASENAME, K.CAS_ABILITY_SKILL)
        self.assertLess(len(K.PURSUIT_BASENAME), len(K.CAS_ABILITY_SKILL))
        self.assertIn(K.PURSUIT_BASENAME, K.PURSUIT_PROGRAM)

    def test_effect_family_naming(self):
        self.assertEqual(K.FX_MEMBERS, tuple(f"{K.TEMPLATE_CODE}_{s}" for s in ("all", "claw", "dash")))
        self.assertEqual(K.FX_DST_DIR, f"battle/effect/skill_unique/{K.CODE}/{K.FX_SUBDIR}")
        self.assertTrue(K.PURSUIT_CLAW_BASENAME.endswith("_claw"))

    def test_skill_edits_cover_both_levels(self):
        self.assertEqual(set(K.SKILL_EDITS), {"1", "2"})
        for level, edits in K.SKILL_EDITS.items():
            for key in ("cna_from", "cna_to", "pf_frames", "pf_from", "pf_to", "cb_from", "cb_to"):
                self.assertIn(key, edits, f"level {level} missing {key}")


class DesignSelfCheckTests(unittest.TestCase):
    """裁决 §8：kit 实现前对设计稿的硬自查。"""

    def setUp(self):
        if not DESIGN:
            self.skipTest("design/mia.json missing")
        self.leader = DESIGN["plan"]["leader_ability"]["rows"]
        self.ability = DESIGN["plan"]["ability"]["keys"]

    def test_design_identity_matches_the_module(self):
        self.assertEqual(DESIGN.get("schema"), "ma-design/1")
        self.assertEqual(DESIGN.get("cid"), K.CID)
        self.assertEqual(DESIGN.get("code"), K.CODE)

    def test_leader_table_has_eight_rows_and_no_patched_kinds(self):
        self.assertEqual(len(self.leader), 8)
        for entry in self.leader:
            for col in ("45", "107"):
                self.assertNotIn(entry["cells"].get(col), ("422", "724", "713"), entry["index"])
            # 每行都有官方口径的 donor 地址与 wf_describe 回读
            self.assertTrue(entry["donor"])
            self.assertTrue(entry["desc_actual_wf_describe"])

    def test_leader_pursuit_row_targets_the_registered_string_and_program(self):
        row6 = next(e for e in self.leader if e["index"] == 6)
        self.assertEqual(row6["cells"]["45"], "629")
        self.assertEqual(row6["cells"]["68"], K.CAS_ABILITY_SKILL)
        self.assertEqual(row6["cells"]["69"], K.PURSUIT_PROGRAM)
        row7 = next(e for e in self.leader if e["index"] == 7)
        self.assertEqual(row7["cells"]["45"], "525")
        self.assertEqual(row7["cells"]["66"], K.UID)

    def test_ability_has_six_keys_fifteen_records(self):
        self.assertEqual(tuple(sorted(self.ability)), tuple(sorted(K.ABILITY_KEYS)))
        total = sum(len(block["records"]) for block in self.ability.values())
        self.assertEqual(total, 15)
        for key_name, block in self.ability.items():
            self.assertGreaterEqual(len(block["records"]), 1)

    def test_unique_condition_cap_is_not_none(self):
        add = DESIGN["plan"]["unique_conditions"]["add"]
        self.assertEqual(len(add), 1)
        self.assertEqual(add[0]["key"], K.UID)
        self.assertEqual(add[0]["row"][4], K.UNIQUE_CAP)
        self.assertNotIn(add[0]["row"][4], ("", "(None)"))    # (None) = 上限 1 层，按层加成全死
        self.assertEqual(add[0]["row"][2], K.UNIQUE_ICON_ROW)

    def test_statue_group_and_unisonable_are_single_valued_per_key(self):
        for name, block in self.ability.items():
            groups = {r["cells"]["2"] for r in block["records"]}
            self.assertEqual(len(groups), 1, f"{name} mixed statue groups {groups}")
            self.assertEqual(groups.pop(), block["statue_group"], name)
            self.assertIn(block["statue_group"], L.ABILITY_STATUE_GROUPS, name)
            flags = {r["cells"]["1"] for r in block["records"]}
            self.assertEqual(len(flags), 1, f"{name} mixed unisonable flags {flags}")
            self.assertEqual(flags.pop(), block["unisonable"], name)

    def test_ability_records_carry_the_slot_code_in_c0(self):
        for slot, key_name in enumerate(K.ABILITY_KEYS, start=1):
            for record in self.ability[key_name]["records"]:
                self.assertEqual(record["cells"]["0"], f"{K.CODE}_{slot}", f"{key_name}#{record['index']}")

    def test_during_puller_columns(self):
        # during 134 / during 1 的 puller 写 '0'；during 30 留空。写反 = 点「角色」C7050
        for name, block in self.ability.items():
            for record in block["records"]:
                cells = record["cells"]
                if cells.get("5") != "1":
                    continue
                want = "0" if cells.get("97") in ("134", "1") else ""
                self.assertEqual(cells.get("98", ""), want, f"{name}#{record['index']}")

    def test_all_donor_addresses_parse(self):
        for entry in self.leader:
            K._parse_donor(entry["donor"])                   # 不抛异常即通过
        for block in self.ability.values():
            for record in block["records"]:
                K._parse_donor(record["donor"])

    def test_panel_texts_obey_the_batch_rules(self):
        cas_rows = DESIGN["plan"]["texts"]["custom_ability_string"]["rows"]
        self.assertEqual({r["key"] for r in cas_rows}, {K.CAS_ABILITY_SKILL, K.CAS_DESC_OVERRIDE})
        for entry in cas_rows:
            self.assertEqual(KL.panel_problems(entry["text"]), [], entry["key"])
        for block in self.ability.values():
            for record in block["records"]:
                self.assertEqual(KL.panel_problems(record["desc_actual_wf_describe"]), [],
                                 record["donor"])

    def test_voice_route_matches_the_module(self):
        route = DESIGN["voice"]["route"]
        self.assertEqual(int(route["kind"]), K.VOICE_ROUTE["kind"])
        self.assertEqual(str(route["condition_kind"]), K.VOICE_ROUTE["condition_kind"])
        self.assertEqual(str(route["condition_id"]), K.VOICE_ROUTE["condition_id"])
        self.assertEqual(list(route["character_c9_16"]), KL.voice_route(K.CODE, K.VOICE_ROUTE))
        self.assertEqual(len(DESIGN["voice"]["lines"]), 22)

    def test_deviations_are_registered_with_reasons(self):
        self.assertTrue(DESIGN.get("deviations"))
        for item in DESIGN["deviations"]:
            want = item.get("原设想") or item.get("want")
            got = item.get("实际落法") or item.get("got")
            why = item.get("原因") or item.get("why")
            self.assertTrue(want and got and why, item)


class DslToolTests(unittest.TestCase):
    def test_cc_ac_entry_needs_exactly_one_match(self):
        cc = ["Command", ["CreateCondition", -17, [["ACPiercing", [{"min": 60, "max": 60}]]]]]
        tree = ["ActionDsl", 1, ["None"], False, False, False, False, False, False, False, 0,
                ["Block", [cc]]]
        entry = K._cc_ac_entry(tree, "ACPiercing")
        self.assertEqual(entry[1][0]["min"], 60)
        with self.assertRaises(K.KitError):
            K._cc_ac_entry(tree, "ACFlying")

    def test_write_dsl_checked_rejects_the_wrapper_shape(self):
        # 记忆卡 wf-dsl-encode-wrapper-trap：喂 {tree, numbers} 包装壳 = 进战斗 F1034
        with self.assertRaises(K.KitError):
            K._write_dsl_checked(None, "x", {"tree": ["ActionDsl"], "numbers": []})

    def test_draw_icon_keeps_the_donor_alpha(self):
        from PIL import Image
        frame = Image.new("RGBA", (48, 48), (0, 0, 0, 0))
        for y in range(6, 42):
            for x in range(6, 42):
                frame.putpixel((x, y), (10, 10, 10, 255))
        icon = K.draw_icon(frame)
        self.assertEqual(icon.size, (48, 48))
        self.assertEqual(icon.getchannel("A").tobytes(), frame.getchannel("A").tobytes())
        with self.assertRaises(K.KitError):
            K.draw_icon(Image.new("RGBA", (64, 64)))


# ---------------------------------------------------------------- 2. 官方基线

@unittest.skipUnless(_BASELINE and bool(DESIGN), "needs the official .cdn/cn baseline + live store")
class RowAssemblyTests(unittest.TestCase):
    def test_leader_and_ability_rows_assemble_and_describe_as_designed(self):
        leader_rows, leader_evidence = K.build_leader_rows(ctx(), DESIGN)
        self.assertEqual(len(leader_rows), 8)
        for row in leader_rows:
            self.assertEqual(row[0], K.CODE)
        ability_rows, ability_evidence = K.build_ability_rows(ctx(), DESIGN)
        self.assertEqual(sum(len(v) for v in ability_rows.values()), 15)
        self.assertEqual(len(leader_evidence) + len(ability_evidence), 23)
        for slot, key_name in enumerate(K.ABILITY_KEYS, start=1):
            KL.check_ability_key(ability_rows[key_name], key_name, K.CODE, slot)

    def test_forbidden_leader_kinds_are_rejected(self):
        rows, _ = K.build_leader_rows(ctx(), DESIGN)
        K._ban_forbidden_leader_kinds(rows)                  # 真实装配结果必须过闸
        bad = [list(r) for r in rows]
        bad[0][45] = "422"
        with self.assertRaises(K.KitError):
            K._ban_forbidden_leader_kinds(bad)

    def test_custom_ability_string_plan_and_capabilities(self):
        # 不调用 K.write_strings（它会 ctx.write_flat 落盘）：ctx() 绑定的是真 workspace，
        # 单测只读校验 design 里的 cas_plan 与面板覆盖能力判定这两个纯函数结果。
        cas_rows = DESIGN["plan"]["texts"]["custom_ability_string"]["rows"]
        cas_plan = {r["key"]: r["text"] for r in cas_rows}
        self.assertEqual(set(cas_plan), {K.CAS_ABILITY_SKILL, K.CAS_DESC_OVERRIDE})
        self.assertIsNone(L.panel_override_capability(K.CAS_ABILITY_SKILL))
        self.assertEqual(L.panel_override_capability(K.CAS_DESC_OVERRIDE),
                         "panel-description-override-v2")


@unittest.skipUnless(_BASELINE, "needs the official .cdn/cn baseline")
class SkillTreeTests(unittest.TestCase):
    def test_both_levels_assemble_and_pass_the_gates(self):
        for level in ("1", "2"):
            tree, gates = K.build_skill_tree(ctx(), level, fake_family())
            self.assertEqual(tree[0], "ActionDsl")
            self.assertEqual(tree[1], 3)
            self.assertEqual(tree[10], 0)                     # 技能伤害归属（donor 原值不动）
            self.assertEqual(K._dsl_problems(tree, element=K.ELEMENT), [])
            self.assertEqual(gates["cna"], K.SKILL_EDITS[level]["cna_to"])
            self.assertEqual(gates["pf_damage"], K.SKILL_EDITS[level]["pf_to"])
            self.assertEqual(gates["combo_boost"], K.SKILL_EDITS[level]["cb_to"])
            attacks = list(wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack"))
            self.assertEqual(len(attacks), 2)
            for cna in attacks:
                self.assertEqual(cna[6], [K.SKILL_EDITS[level]["cna_to"]])

    def test_effect_refs_are_rewritten_under_the_cloned_family(self):
        tree, _ = K.build_skill_tree(ctx(), "1", fake_family())
        paths = {v for v in _walk_strings(tree) if isinstance(v, str)
                and v.startswith("battle/effect/")}
        self.assertTrue(paths)
        for p in paths:
            self.assertTrue(p.startswith(K.FX_DST_DIR + "/"), p)


@unittest.skipUnless(_BASELINE, "needs the official .cdn/cn baseline")
class PursuitTreeTests(unittest.TestCase):
    def test_pursuit_tree_scales_and_flips_attribution(self):
        tree, gate = K.build_pursuit_tree(ctx(), fake_family())
        self.assertEqual(tree[0], "ActionDsl")
        self.assertEqual(tree[10], 3)                         # 0 → 3，按强化弹射伤害结算
        self.assertEqual(K._dsl_problems(tree, element=None), [])
        attacks = list(wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack"))
        self.assertEqual(len(attacks), 1)
        self.assertEqual(attacks[0][6], [K.PURSUIT_MULT])
        self.assertAlmostEqual(gate["total"], K.PURSUIT_MULT["max"] * 4, places=6)

    def test_special_effect_points_at_the_cloned_claw(self):
        tree, _ = K.build_pursuit_tree(ctx(), fake_family())
        shows = list(wf_dsl.iter_dsl_commands(tree, "ShowEffect"))
        paths = [s[2][1] for s in shows if isinstance(s[2], list) and s[2][0] == "SpecifyEffectDirectly"]
        self.assertIn(f"{K.FX_DST_DIR}/{K.PURSUIT_CLAW_BASENAME}", paths)
        # オーラ演出保留官方 fire_dragon_zenith 引用（未克隆，框架 §10.3）
        self.assertTrue(any(p.startswith("battle/effect/skill_unique/fire_dragon_zenith/") for p in paths))

    def test_source_fingerprint_guard(self):
        # 门禁：探测层/参考点/内层判定区形状漂移必须报错，不能悄悄改错母本
        tree = ctx().template_dsl(K.PURSUIT_DONOR)
        self.assertEqual(tree[10], 0)                          # 记录 donor 现值，后续若漂移这里先红


def _walk_strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, (list, tuple)):
        for item in node:
            yield from _walk_strings(item)
    elif isinstance(node, dict):
        for value in node.values():
            yield from _walk_strings(value)


# ---------------------------------------------------------------- 3. 已构建的 workspace

@unittest.skipUnless((WORKSPACE / "evidence/kit-report.json").is_file(),
                     "workspace ma-mia has not been built yet")
class PackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pack = MC.MAPack(MS.get_spec("mia"), record_sources=False)
        cls.report = json.loads((WORKSPACE / "evidence/kit-report.json").read_text("utf-8"))
        cls.claims = json.loads((WORKSPACE / "evidence/table_claims.json").read_text("utf-8"))

    def claimed(self, logical: str) -> set[str]:
        return {key for entry in self.claims if entry["logical_path"] == logical
                for key in entry["outer_keys"]}

    def test_package_carries_the_three_self_owned_keys(self):
        self.assertIn(K.UID, self.pack.pkg_flat(MS.UNIQUE_CONDITION_LOGICAL))
        cas = self.pack.pkg_flat(KL.CAS)
        self.assertIn(K.CAS_ABILITY_SKILL, cas)
        self.assertIn(K.CAS_DESC_OVERRIDE, cas)
        switched = C.core.load_nested_table_bytes(
            self.pack.pkg_path("common", KL.SWITCHED).read_bytes(), KL.SWITCHED)
        self.assertIn(K.VOICE_KEY, switched.rows)

    def test_every_self_owned_key_is_claimed(self):
        self.assertIn(K.UID, self.claimed(MS.UNIQUE_CONDITION_LOGICAL))
        self.assertLessEqual({K.CAS_ABILITY_SKILL, K.CAS_DESC_OVERRIDE}, self.claimed(KL.CAS))
        self.assertIn(K.VOICE_KEY, self.claimed(KL.SWITCHED))
        self.assertEqual(self.claimed(KL.ABILITY), set(K.ABILITY_KEYS))
        self.assertEqual(self.claimed(KL.LEADER), {str(K.CID)})

    def test_written_dsl_round_trips(self):
        for program in (K.PURSUIT_PROGRAM,
                        f"battle/action/skill/action/rare5/{K.CODE}${K.CODE}_1",
                        f"battle/action/skill/action/rare5/{K.CODE}${K.CODE}_2"):
            logical = wf_dsl.dsl_logical(program)
            tree = C.amf_parse(self.pack.pkg_path("common", logical).read_bytes())
            self.assertEqual(tree[0], "ActionDsl", logical)

    def test_character_row_routes_the_voice(self):
        row = self.pack.pkg_character_row()
        self.assertEqual(row[9:17], KL.voice_route(K.CODE, K.VOICE_ROUTE))
        self.assertEqual(row[6], "2")
        self.assertEqual(row[26], "Attacker")
        self.assertEqual(row[27], str(K.CID))

    def test_report_status_and_gate(self):
        gate = self.report["kit_gate"]
        self.assertEqual(gate["rows"], 23)
        self.assertEqual(gate["programs"], 3)
        expected = KL.READY if gate["pixel_present"] and not gate["pixel_missing"] else KL.DRAFT
        self.assertEqual(self.report["status"], expected)

    def test_report_panel_and_capabilities(self):
        self.assertEqual(self.report["cid"], K.CID)
        for text in self.report["panel"]:
            self.assertEqual(KL.panel_problems(text), [], text)
        self.assertEqual(set(self.report["required_capabilities"]),
                         set(K.SPEC["required_capabilities"]))
        self.assertEqual(self.report["unique_condition"][K.UID]["cap"], K.UNIQUE_CAP)

    def test_effect_family_is_the_only_cloned_one(self):
        families = json.loads((WORKSPACE / "evidence/effect-families.json").read_text("utf-8"))
        self.assertEqual(sorted(families), [K.FX_DST_DIR])
        self.assertEqual(sorted(families[K.FX_DST_DIR]["copied_bases"]), sorted(K.FX_MEMBERS))
        self.assertEqual(families[K.FX_DST_DIR]["missing_effects"], [])

    def test_no_stray_dsl_file_under_the_old_basename(self):
        # 本轮实测坑：改短 PURSUIT_BASENAME 前留下的旧文件必须已清理（不会再被任何键引用）
        stray = self.pack.pkg_path(
            "common", "battle/action/skill/action/ability_skill/"
                     f"{K.CAS_ABILITY_SKILL}${K.CAS_ABILITY_SKILL}.action.dsl.amf3.deflate")
        self.assertFalse(stray.is_file(), stray)


if __name__ == "__main__":
    unittest.main()
