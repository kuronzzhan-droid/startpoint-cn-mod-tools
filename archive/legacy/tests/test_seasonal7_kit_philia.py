# -*- coding: utf-8 -*-
"""wf_seasonal7_kit_philia：纯函数门禁负向用例 + 与设计/包产物的只读集成用例（不写 workspace）。"""
from __future__ import annotations

import copy
import io
import json
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

pass  # Imports resolve from this checkout/package, not external source copies.
import wf_client_legality as L  # noqa: E402
import wf_dsl  # noqa: E402
import wf_seasonal7_common as C  # noqa: E402
import wf_seasonal7_kit_philia as K  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PROTO = ROOT / K.PROTO_REL          # 改版重建树（run_gates 每次刷新）；上一轮的在 design/_tmp/philia/proto
WORKSPACE = ROOT / "work/character_packs/s7-philia"
SKILL_PROTOS = ("skill_1.json", "skill_2.json")
PF_PROTOS = tuple(f"pf_lv{n}.json" for n in (1, 2, 3))


def _proto(name: str):
    return json.loads((PROTO / name).read_text(encoding="utf-8"))


class ReadOnlyCtx:
    """build_skill_tree / build_pf_tree / derive_rows 需要的最小只读上下文（不写 template_sources）。"""

    def __init__(self):
        import wf_seasonal7_specs as S
        self.pack = C.S7Pack(S.get_spec(K.KEY))
        self.root = self.pack.root

    def official_read(self, logical, root=None):
        return self.pack.official_read(logical, root)

    def live_read(self, logical):
        return self.pack.live_read(logical)

    def template_dsl(self, program):
        raw = self.pack.official_read(wf_dsl.dsl_logical(program), "common")
        return C.amf_parse(raw if raw is not None else self.pack.live_read(wf_dsl.dsl_logical(program)))

    def official_flat(self, logical):
        return C.core.read_orderedmap_file_from_bytes(self.pack.official_read(logical, "common"))

    def live_flat(self, logical):
        return self.pack.live_flat(logical)

    def rewrite_effect_refs(self, tree, family, *, strict=False):
        return C.rewrite_effect_refs(tree, family, strict=strict)


def _unwrap_conditionals(tree) -> int:
    """就地把 ["Command", ["Conditionals...", ...]] 还原成**缺壳**形，复现 2026-09-16 审查的 blocker 变异。

    缺壳节点直接躺在 CreateHitArea on-hit 的表达式数组里；客户端 ActionDslExpression
    只有 Block/Event/Command 三个构造，未知名 -> 索引 0（Block），Block 的第 1 参被当
    Array<ActionDslExpression> 取而这里是裸 int -> AS3 #1034。
    """
    n = 0

    def walk(node) -> None:
        nonlocal n
        if not isinstance(node, list):
            return
        for i, child in enumerate(node):
            if (isinstance(child, list) and child[:1] == ["Command"] and isinstance(child[1], list)
                    and isinstance(child[1][0], str) and child[1][0].startswith("Conditionals")):
                node[i] = child[1]
                n += 1
            else:
                walk(child)

    walk(tree)
    return n


@unittest.skipUnless((PROTO / "skill_2.json").is_file(), "revision prototypes absent (run run_gates.py first)")
class DslGateNegatives(unittest.TestCase):
    def test_prototypes_are_clean(self):
        for name in (*SKILL_PROTOS, *PF_PROTOS):
            gates = K.dsl_gates(_proto(name))
            self.assertEqual(K.dsl_gate_failures(gates), [], name)

    def test_revision_shapes_landed(self):
        """本轮点名的形状：技能 tree[10]=3 / 10 把光剑 + 10 份剑雨 / PF 5 把 + 5 份剑雨 + special 底座。"""
        for name in SKILL_PROTOS:
            tree = _proto(name)
            self.assertEqual(tree[10], K.SKILL_BUFF_TARGET_AS, name)
            self.assertEqual(len(K.cmds(tree, "CreateNormalAttack")), 2 * K.SKILL_SWORDS, name)
            flags = [n for n in K.conditional_nodes(tree)]
            self.assertEqual(len(flags), K.SKILL_SWORDS, name)
            for node in flags:
                self.assertEqual(node[1], K.RESONANCE_FLAG_INDEX)
                self.assertEqual(node[3], ["Block", []])    # else 分支不能是 ["DoNothing"]（F1009）
            kinds = [c[2][0][0] for c in K.cmds(tree, "CreateCondition")]
            self.assertEqual(kinds.count(K.RESIST_KIND), K.SKILL_SWORDS, name)
        for name in PF_PROTOS:
            tree = _proto(name)
            self.assertEqual(tree[10], 0, name)
            self.assertEqual(len(K.cmds(tree, "CreateNormalAttack")), 2 + 2 * K.PF_SWORDS, name)
            self.assertTrue(any(c[1] == "特殊演出" for c in K.cmds(tree, "ShowEffect")), name)
            dirs = sorted({c[6] for c in K.cmds(tree, "CreateHitArea") if c[6]})
            self.assertEqual(dirs, sorted(K.PF_LAUNCH_DIRS), name)
            self.assertTrue(all(c[24] == 0 for c in K.cmds(tree, "CreateHitArea")), name)

    def test_scalar_in_array_param_is_f1034(self):
        tree = _proto("skill_2.json")
        hit = K.cmds(tree, "CreateHitArea")[0]
        self.assertEqual(hit[9][0], "Circle")
        hit[9] = ["Circle", 30]                          # 裸数值进 Array 参
        probs = K.signature_problems(tree)
        self.assertTrue(any("Circle#1" in p and "want Array" in p for p in probs), probs)

    def test_donothing_branch_is_f1009(self):
        tree = _proto("skill_2.json")
        tree[11][1].append(["ConditionalsFeverMode", ["DoNothing"], ["Block", []]])
        self.assertTrue(any("DoNothing" in p for p in K.signature_problems(tree)))

    def test_resonance_debuff_else_branch_must_not_be_donothing(self):
        tree = _proto("skill_2.json")
        node = K.conditional_nodes(tree)[0]
        node[3] = ["DoNothing"]
        self.assertTrue(any("DoNothing" in p for p in K.signature_problems(tree)))
        self.assertTrue(K.dsl_gate_failures(K.dsl_gates(tree)))

    def test_unbound_lookup_is_c16103(self):
        tree = _proto("skill_2.json")
        base = K.SKILL_RAIN_BASE_ID + 3                  # 第 0 把光剑的剑雨目标绑定
        rain = [c for c in K.cmds(tree, "CreateNormalAttack") if c[1] == base]
        self.assertEqual(len(rain), 1)
        rain[0][1] = base + 4                            # 串到隔壁光剑的剑雨绑定（作用域外）
        self.assertTrue(K.scope_problems(tree))
        self.assertTrue(K.dsl_gate_failures(K.dsl_gates(tree)))

    def test_pf_sword_unbound_lookup_is_c16103(self):
        tree = _proto("pf_lv3.json")
        move = [c for c in K.cmds(tree, "MoveHitArea") if c[2][0] == "GH"]
        self.assertTrue(move)
        move[0][2] = ["GH", 999]                         # 追踪参考点漏重映射
        self.assertTrue(K.scope_problems(tree))
        self.assertTrue(K.dsl_gate_failures(K.dsl_gates(tree)))

    def test_bare_conditionals_in_expression_slot_is_f1034(self):
        """审查 blocker 的钉子：去掉 ["Command", ...] 外壳必须变红（旧门禁一视同仁，恒绿）。"""
        for name in SKILL_PROTOS:
            clean = _proto(name)
            self.assertEqual(K.expr_tag_problems(clean), [], name)
            tree = _proto(name)
            self.assertEqual(_unwrap_conditionals(tree), K.SKILL_SWORDS, name)
            probs = K.expr_tag_problems(tree)
            self.assertEqual(len(probs), K.SKILL_SWORDS, (name, probs[:2]))
            self.assertTrue(all("ConditionalsChangeSkillFlag" in p for p in probs), probs[:2])
            self.assertTrue(any("expr_tags" in f for f in K.dsl_gate_failures(K.dsl_gates(tree))), name)

    def test_is_expr_rejects_bare_command_constructs(self):
        self.assertTrue(K._is_expr(["Block", []]))
        self.assertTrue(K._is_expr(["Command", ["ShakeCamera", 1]]))
        self.assertTrue(K._is_expr(["Event", ["Wait", 1, "*", ["Block", []]]]))
        self.assertFalse(K._is_expr(["ConditionalsChangeSkillFlag", 1, ["Block", []], ["Block", []]]))
        self.assertFalse(K._is_expr(["ConditionalsFeverMode", ["Block", []], ["Block", []]]))
        self.assertFalse(K._is_expr(1))

    def test_make_resonance_debuff_is_command_wrapped(self):
        template = ["CreateCondition", -17, [["ACPowerFlipDamage", K.slv(900, 900), K.slv(1.0, 1.0), K.slv(1, 1)]],
                    K.slv(1, 1), ["GenericConditionHitEffect"], True, False, "", None, False, 2, K.slv(1, 1)]
        node = K.make_resonance_debuff(7, template)
        self.assertEqual(node[0], "Command")
        self.assertEqual(node[1][0], "ConditionalsChangeSkillFlag")
        self.assertEqual(node[1][1], K.RESONANCE_FLAG_INDEX)
        self.assertEqual(node[1][3], ["Block", []])
        self.assertEqual(node[1][2][1][0][1][1], 7)                  # 付与对象 = 命中目标绑定
        self.assertEqual(node[1][2][1][0][1][2][0][0], K.RESIST_KIND)
        self.assertTrue(K._is_expr(node))

    def test_stopball_window_covers_the_last_sword(self):
        """审查 minor#3：间隔拉长后停球窗口必须盖住末发，否则后几把从已弹开的球位置飞出。"""
        last = 20 + K.SKILL_SWORD_WAIT_STEP * (K.SKILL_SWORDS - 1)   # 外层 Event Wait(20) + 子 Wait
        for name in SKILL_PROTOS:
            tree = _proto(name)
            stop = K.cmds(tree, "StopBall")
            self.assertEqual(len(stop), 1, name)
            self.assertEqual(stop[0][1], -18, name)
            self.assertEqual(stop[0][2], K.SKILL_STOPBALL_FRAMES, name)
            self.assertGreaterEqual(stop[0][2], last, (name, last))

    def test_swords_eliminate_after_one_hit_so_rain_count_is_bounded(self):
        """审查 minor#4：p14 maxNumOfHits 是**按目标**封顶，只有 p17 totalHitToEliminate 能钉死份数。"""
        for name in SKILL_PROTOS:
            tree = _proto(name)
            sword_chas = [c for c in K.cmds(tree, "CreateHitArea") if c[2] == -18]
            self.assertEqual(len(sword_chas), K.SKILL_SWORDS, name)
            for c in sword_chas:
                self.assertEqual(c[18], ["Some", K.SWORD_TOTAL_HIT_TO_ELIMINATE], name)
            rains = [c for c in K.cmds(tree, "CreateNormalAttack") if c[1] >= K.SKILL_RAIN_BASE_ID]
            self.assertEqual(len(rains), K.SKILL_SWORDS, name)
        for name in PF_PROTOS:
            tree = _proto(name)
            sword_chas = [c for c in K.cmds(tree, "CreateHitArea")
                          if K.PF_SUBJECT_OFFSET <= c[19] < K.PF_RAIN_BASE_ID]
            self.assertEqual(len(sword_chas), K.PF_SWORDS, name)
            for c in sword_chas:
                self.assertEqual(c[18], ["Some", K.SWORD_TOTAL_HIT_TO_ELIMINATE], name)

    def test_wrapper_is_rejected(self):
        with self.assertRaises(Exception):
            C.amf_bytes({"tree": _proto("skill_1.json"), "numbers": []})


class FxManifestHook(unittest.TestCase):
    def _root(self, tmp: Path, manifest: dict, images: dict):
        out = tmp / K.FX_MANIFEST_REL
        out.parent.mkdir(parents=True)
        for name, img in images.items():
            img.save(out.parent / name)
        out.write_text(json.dumps(manifest), encoding="utf-8")
        return tmp

    def test_formats_and_transform_gates(self):
        from PIL import Image
        src = Image.new("RGBA", (8, 4), (10, 200, 30, 255))
        src.putpixel((0, 0), (0, 0, 0, 0))
        same_alpha = src.copy()
        same_alpha.putpixel((1, 1), (200, 10, 30, 255))
        alpha_changed = same_alpha.copy()
        alpha_changed.putpixel((0, 0), (5, 5, 5, 128))
        sheet = "battle/effect/skill_unique/wind_oracle_1anv/wind_oracle_1anv.png"
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(Path(tmp), {"sheets": {"battle/effect/skill_unique/wind_oracle_1anv": "a.png"},
                                          "entries": []},
                              {"a.png": same_alpha, "b.png": alpha_changed, "c.png": Image.new("RGBA", (9, 4))})
            overrides, info = K.load_fx_manifest(root)
            self.assertEqual(list(overrides), [sheet])
            log: dict = {}
            got = K.make_png_transform(sheet, overrides[sheet], log)(src)
            self.assertEqual(got.getpixel((1, 1)), (200, 10, 30, 255))
            self.assertEqual(log[sheet]["alpha_changed_pixels"], 0)
            base = Path(tmp) / K.FX_MANIFEST_REL
            with self.assertRaises(K.KitError):
                K.make_png_transform(sheet, {"file": base.parent / "b.png", "allow_alpha_change": False}, {})(src)
            K.make_png_transform(sheet, {"file": base.parent / "b.png", "allow_alpha_change": True}, {})(src)
            with self.assertRaises(K.KitError):
                K.make_png_transform(sheet, {"file": base.parent / "c.png", "allow_alpha_change": True}, {})(src)
            self.assertIsNone(K.make_png_transform(sheet, None, {}))

    def test_effects_stage_fingerprints_are_enforced(self):
        import hashlib
        from PIL import Image
        src = Image.new("RGBA", (4, 4), (10, 200, 30, 255))
        new = src.copy()
        new.putpixel((2, 2), (120, 130, 255, 255))
        sheet = "battle/effect/skill_unique/wind_oracle/wind_oracle.png"
        good = {"source_rgba_sha256": hashlib.sha256(src.tobytes()).hexdigest(),
                "out_rgba_sha256": hashlib.sha256(new.tobytes()).hexdigest(), "gates_all_ok": True}
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(Path(tmp), {"sheets": {sheet: "n.png"}, "details": {sheet: good}}, {"n.png": new})
            overrides, _ = K.load_fx_manifest(root)
            K.make_png_transform(sheet, overrides[sheet], {})(src)
            drifted = src.copy()
            drifted.putpixel((0, 0), (1, 2, 3, 255))
            with self.assertRaises(K.KitError):
                K.make_png_transform(sheet, overrides[sheet], {})(drifted)
            manifest = Path(tmp) / K.FX_MANIFEST_REL
            manifest.write_text(json.dumps({"sheets": {sheet: "n.png"}, "all_gates_ok": False}), encoding="utf-8")
            with self.assertRaises(K.KitError):
                K.load_fx_manifest(root)

    def test_absent_manifest_means_official_colors(self):
        with tempfile.TemporaryDirectory() as tmp:
            overrides, info = K.load_fx_manifest(Path(tmp))
            self.assertEqual(overrides, {})
            self.assertFalse(info["present"])


def _live_available() -> bool:
    try:
        return ((ROOT / K.DESIGN_REL).is_file() and (ROOT / K.REVISION_REL).is_file()
                and ReadOnlyCtx().pack.official_read(K.ABILITY, "common") is not None)
    except Exception:                                       # noqa: BLE001
        return False


@unittest.skipUnless(_live_available(), "design / official baseline unavailable")
class DesignIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ctx = ReadOnlyCtx()
        cls.design = K.load_design(ROOT)
        cls.plan = K.load_revision(ROOT)

    def _revised(self, plan=None, design=None):
        design = design or self.design
        cache: dict = {}
        base_leader, _ = K.derive_rows(self.ctx, design["leader"], "leader_ability", "leader", cache)
        base_ability = {design["ability_keys"][slot]: K.derive_rows(self.ctx, entries, "ability", slot, cache)[0]
                        for slot, entries in design["abilities"].items()}
        plan = plan or self.plan
        leader, _ = K.revise_leader(self.ctx, base_leader, plan, cache)
        ability, _ = K.revise_abilities(self.ctx, base_ability, plan, cache)
        return leader, ability

    def test_rows_derive_and_pass_legality(self):
        leader, ability = self._revised()
        caps = set()
        for row in leader:
            self.assertEqual(K.row_problems("leader_ability", row), [])
            self.assertEqual(len(row), 124)
            caps.update(L.required_client_capabilities("leader_ability", row))
        total = 0
        for rows in ability.values():
            total += len(rows)
            for row in rows:
                self.assertEqual(K.row_problems("ability", row), [])
                self.assertEqual(len(row), 126)
                caps.update(L.required_client_capabilities("ability", row))
        self.assertEqual(len(leader), 6)
        self.assertEqual(total, 16)                       # 上一轮 13 条 + A3 新增 3 条（536 行搬到 A1）
        self.assertEqual(sorted(caps), ["kyubi-fever-ratio-v1"])

    def test_revised_rows_render_the_author_sentences(self):
        import wf_describe
        leader, ability = self._revised()
        got = {f"L{i}": d for i, d in enumerate(wf_describe.describe_rows(leader, "leader_ability"))}
        for key, rows in ability.items():
            for i, d in enumerate(wf_describe.describe_rows(rows, "ability")):
                got[f"{key}#{i}"] = d
        for anchor, want in self.plan["describe_expected"].items():
            self.assertEqual(got.get(anchor), want, anchor)

    def test_revision_rejects_full_row_after_drift(self):
        plan = copy.deepcopy(self.plan)
        plan["leader"]["rows"][4]["full_row_after"][49] = "600000"
        with self.assertRaises(K.KitError):
            self._revised(plan=plan)
        plan = copy.deepcopy(self.plan)
        plan["abilities"]["keys"]["1599963"]["records"][3]["edits_from_donor"]["51"] = "1000000"
        with self.assertRaises(K.KitError):
            self._revised(plan=plan)

    def test_revision_rejects_orphaned_design_record(self):
        plan = copy.deepcopy(self.plan)
        plan["abilities"]["keys"]["1599963"]["removed"] = []     # 536 行既没搬走也没登记删除
        plan["abilities"]["keys"]["1599961"]["records"] = \
            [r for r in plan["abilities"]["keys"]["1599961"]["records"] if r["action"] != "move_in"]
        with self.assertRaises(K.KitError):
            self._revised(plan=plan)

    def test_revision_rejects_c1_c2_drift(self):
        plan = copy.deepcopy(self.plan)
        plan["abilities"]["keys"]["1599963"]["c1"] = "true"
        with self.assertRaises(K.KitError):
            self._revised(plan=plan)

    def test_kit_parameters_track_design_and_revision(self):
        self.assertEqual(K.skill_param_drift(self.design), [])
        self.assertEqual(K.pf_param_drift(self.design), [])
        self.assertEqual(K.revision_param_drift(self.plan), [])
        d1 = copy.deepcopy(self.design)                   # design 侧被取代的值也必须钉住
        [e for e in d1["skills"]["tree_plan_1"]["blocks"][10]["param_edits"] if "倍率" in e["param"]][0]["new"] = \
            [{"min": 0.66, "max": 0.66}]
        self.assertTrue(any(p.startswith("skill1.sword") for p in K.skill_param_drift(d1)))
        d2 = copy.deepcopy(self.design)
        d2["skills"]["tree_plan_1"]["blocks"][4]["param_edits"][0]["new"] = [4]
        self.assertTrue(any("heal_slayer" in p for p in K.skill_param_drift(d2)))
        d3 = copy.deepcopy(self.design)
        d3["pf_override"]["lv3"]["donor"]["locate"] = d3["pf_override"]["lv3"]["donor"]["locate"].replace("前 8 个", "前 7 个")
        self.assertTrue(any(p.startswith("pf lv3") for p in K.pf_param_drift(d3)))
        d4 = copy.deepcopy(self.design)
        d4["pf_override"]["lv1"]["donor"]["transform"] = [t for t in d4["pf_override"]["lv1"]["donor"]["transform"]
                                                          if "enablesBuffCountBonus" not in t]
        self.assertTrue(any("buff-count" in p for p in K.pf_param_drift(d4)))
        for mutate, needle in (
                (lambda p: p["skill_dsl"]["root_head"].__setitem__("after", 0), "tree[10]"),
                (lambda p: [b for b in p["skill_dsl"]["blocks"] if b["id"] == "block10_swords"][0]["changes"][0]
                 .__setitem__("after", 16), "skill.swords"),
                (lambda p: p["pf_dsl"]["levels"]["lv3"].__setitem__("sword_mult", 2.0), "pf.lv3.sword"),
                (lambda p: p["pf_dsl"]["appended"][1].__setitem__("launch_dirs", [0, 1, 2, 3, 4]), "launch_dirs"),
                (lambda p: [b for b in p["skill_dsl"]["blocks"] if b["id"] == "block0_stopball"][0]["changes"][0]
                 .__setitem__("after", 80), "stopball_frames"),
                (lambda p: [c for b in p["skill_dsl"]["blocks"] if b["id"] == "block10_swords"
                            for c in b["changes"] if c["field"] == "CreateHitArea p17 totalHitToEliminate"][0]
                 .__setitem__("after", ["None"]), "skill.sword_total_hit_to_eliminate"),
                (lambda p: [a for a in p["pf_dsl"]["appended"] if a["id"] == "P2_five_way_swords"][0]["per_unit"]
                 ["CreateHitArea"].__setitem__("p17", ["None"]), "pf.sword_total_hit_to_eliminate")):
            mutated = copy.deepcopy(self.plan)
            mutate(mutated)
            drift = K.revision_param_drift(mutated)
            self.assertTrue(any(needle in p for p in drift), (needle, drift))

    def test_revision_plan_carries_both_custom_ability_strings(self):
        """审查 minor#6：536 强化说明以前不在 plan/门禁覆盖面内，与 action_skill c1 对不上也永远不变红。"""
        keys = self.plan["strings"][K.CAS]["keys"]
        self.assertEqual(sorted(keys), sorted([K.CAS_PF_OVERRIDE, K.CAS_CHANGE_SKILL]))
        change = keys[K.CAS_CHANGE_SKILL]["value"]
        self.assertIn("强化弹射伤害抗性", change)            # R29 门控的那一半不能再漏
        self.assertIn("剑雨", change)
        self.assertNotEqual(C.sha256(change.encode("utf-8")), K.SUPERSEDED_DESIGN_CHANGE_SKILL_SHA256)
        for item in self.design["custom_strings"]:          # design 侧旧文案仍被钉死
            if item["key"] == K.CAS_CHANGE_SKILL:
                self.assertEqual(C.sha256(item["text"].encode("utf-8")),
                                 K.SUPERSEDED_DESIGN_CHANGE_SKILL_SHA256)

    def test_leader_L5_window_is_power_flip_not_ball_flip(self):
        """审查 major：作者要的是「接下来 7 次**强化弹射**」，必须落 c62/c63，不是 c60=flip_limit。"""
        leader, _ = self._revised()
        row = leader[5]
        self.assertEqual(row[45], "718")
        self.assertEqual(row[60], "(None)")                 # flip_limit（普通弹射）不设窗口
        self.assertEqual(row[61], "(None)")                 # power_flip_limit 官方全库 0 例，不用
        self.assertEqual(row[62], "7")                      # end_power_flip_limit
        self.assertEqual(row[63], "11")                     # accepted levels = [1,2,3]
        self.assertNotEqual(row[63], "(None)")              # (None) -> resolveEndPowerFlipLevels 返回 []，永不计数

    def test_edit_without_full_row_is_rejected(self):
        entries = copy.deepcopy(self.design["leader"][:1])
        entries[0]["edits"]["49"] = "150000"
        with self.assertRaises(K.KitError):
            K.derive_rows(self.ctx, entries, "leader_ability", "leader", {})

    @unittest.skipUnless((WORKSPACE / "evidence/effect-families.json").is_file(), "package not built")
    def test_trees_rebuild_equal_package(self):
        registry = json.loads((WORKSPACE / "evidence/effect-families.json").read_text(encoding="utf-8"))
        families = [registry[f"battle/effect/skill_unique/{K.CODE}/{sub}"] for sub in ("sword", "rain", "heal")]
        hashes = K.design_source_hashes(self.design)
        pkg = WORKSPACE / "package/roots/common"

        def package_tree(program):
            return wf_dsl.parse_dsl(zlib.decompress((pkg / wf_dsl.dsl_logical(program)).read_bytes(), -15))["tree"]

        import wf_balance_20260927b_philia as B2

        # 2026-09-27 平衡第二批：kit.build 在 build_skill_tree / random_pf 之后再叠
        # wf_balance_20260927b_philia（只改 CNA p13）。候选暂存前 = 此前产物，暂存后 = 再叠第二批，两者都算一致。
        for level in ("1", "2"):
            tree, _ = K.build_skill_tree(self.ctx, level, K.SKILL_PARAMS[level], families, hashes)
            self.assertEqual(K.dsl_gate_failures(K.dsl_gates(tree)), [])
            program = f"battle/action/skill/action/rare5/{K.CODE}${K.CODE}_{level}"
            package = package_tree(program)
            self.assertTrue(package == tree or package == B2.skill_tree(tree), level)
            self.assertEqual(tree[10], K.SKILL_BUFF_TARGET_AS)
        donor = K._source_tree(self.ctx, f"{K.SKILL_SRC}wind_oracle_1anv$wind_oracle_1anv_2",
                               hashes[f"{K.SKILL_SRC}wind_oracle_1anv$wind_oracle_1anv_2"])
        rain_donor = K.find_one(
            K._source_tree(self.ctx, f"{K.SKILL_SRC}wind_oracle_meteor23$wind_oracle_meteor23_2",
                           hashes[f"{K.SKILL_SRC}wind_oracle_meteor23$wind_oracle_meteor23_2"])[11][1],
            K.is_cmd("CreateReferencePoint"), "meteor23 rain donor")
        special = K.special_source_hashes(self.plan)
        for level in (1, 2, 3):
            tree, _ = K.build_pf_tree(self.ctx, level, donor, rain_donor, families, special)
            self.assertEqual(K.dsl_gate_failures(K.dsl_gates(tree)), [])
            from wf_philia_random_pf import revise_pf as random_pf
            volley = random_pf(tree)
            package = package_tree(K.PF_PROGRAMS[level - 1])
            self.assertTrue(package == volley or package == B2.pf_tree(volley), level)
            attacks = K.cmds(tree, "CreateNormalAttack")
            swords = [c for c in attacks if K.PF_SUBJECT_OFFSET <= c[1] < K.PF_RAIN_BASE_ID]
            self.assertEqual(len(swords), K.PF_SWORDS)
            self.assertTrue(all(c[10] is False for c in swords))
            self.assertTrue(all(c[6] == K.slv(K.PF_PARAMS[level]["sword"], K.PF_PARAMS[level]["sword"])
                                for c in swords))
            rains = [c for c in attacks if c[1] >= K.PF_RAIN_BASE_ID]
            self.assertEqual(len(rains), K.PF_SWORDS)

    def test_rebuilt_trees_grant_no_flying(self):
        """作者 2026-09-21「去掉浮游效果」：kit 重建的五棵树里一条 ACFlying 都不许剩。

        母本形态仍按官方校验（``fly block drift`` / ``supporter lv{n} ACFlying statement drift``），
        所以官方母本哪天变了还是会变红——变的只是「不产出」。
        """
        registry = json.loads((WORKSPACE / "evidence/effect-families.json").read_text(encoding="utf-8"))
        families = [registry[f"battle/effect/skill_unique/{K.CODE}/{sub}"] for sub in ("sword", "rain", "heal")]
        hashes = K.design_source_hashes(self.design)
        for level in ("1", "2"):
            tree, _ = K.build_skill_tree(self.ctx, level, K.SKILL_PARAMS[level], families, hashes)
            self.assertNotIn("ACFlying", json.dumps(tree, ensure_ascii=False), level)
            self.assertEqual([c for c in K.cmds(tree, "FindAllSubjects") if c[2] == 33], [], level)
        for level in (1, 2, 3):
            block = K.pf_support_block(self.ctx.root, level, keep_flying=False)
            self.assertEqual([c[2][0][0] for c in K.cmds(block, "CreateCondition")],
                             ["ACAttackPoint", "ACPiercing"], level)
            # 共享函数默认必须保留官方三件套：芙拉菲/丝缇涅尔的中秋 kit 借用它，作者没点名去掉她们的浮游
            shared = K.pf_support_block(self.ctx.root, level)
            self.assertEqual([c[2][0][0] for c in K.cmds(shared, "CreateCondition")],
                             ["ACAttackPoint", "ACPiercing", "ACFlying"], level)

    def test_special_source_hashes_reject_non_official_base(self):
        plan = copy.deepcopy(self.plan)
        plan["pf_dsl"]["base"]["sources"]["special_lv2"]["official_baseline_identical"] = False
        with self.assertRaises(K.KitError):
            K.special_source_hashes(plan)
        plan = copy.deepcopy(self.plan)
        plan["pf_dsl"]["base"]["sources"]["special_lv1"]["sha256"] = "0" * 64
        registry = json.loads((WORKSPACE / "evidence/effect-families.json").read_text(encoding="utf-8")) \
            if (WORKSPACE / "evidence/effect-families.json").is_file() else None
        if registry is None:
            self.skipTest("package not built")
        families = [registry[f"battle/effect/skill_unique/{K.CODE}/{sub}"] for sub in ("sword", "rain", "heal")]
        hashes = K.design_source_hashes(self.design)
        donor = K._source_tree(self.ctx, f"{K.SKILL_SRC}wind_oracle_1anv$wind_oracle_1anv_2",
                               hashes[f"{K.SKILL_SRC}wind_oracle_1anv$wind_oracle_1anv_2"])
        rain_donor = K.find_one(
            K._source_tree(self.ctx, f"{K.SKILL_SRC}wind_oracle_meteor23$wind_oracle_meteor23_2",
                           hashes[f"{K.SKILL_SRC}wind_oracle_meteor23$wind_oracle_meteor23_2"])[11][1],
            K.is_cmd("CreateReferencePoint"), "meteor23 rain donor")
        with self.assertRaises(K.KitError):
            K.build_pf_tree(self.ctx, 1, donor, rain_donor, families, K.special_source_hashes(plan))


@unittest.skipUnless((WORKSPACE / "evidence/pixel-report.json").is_file()
                     and (ROOT / K.PIXEL_DIR_REL / "report.json").is_file(), "pixel not integrated")
class MediaIntegration(unittest.TestCase):
    """Integrate 阶段只读用例：像素 / 语音已装包的核对函数在真实包上为绿，篡改输入（进程内）必须变红。"""

    @classmethod
    def setUpClass(cls):
        import wf_seasonal7_build as B
        import wf_seasonal7_specs as S
        cls.pack = C.S7Pack(S.get_spec(K.KEY))
        cls.ctx = B.KitContext(cls.pack)

    def test_pixel_green_then_red_on_tamper(self):
        if K.pixel_inputs(self.ctx.root)[1]:
            self.skipTest("pixel inputs pending")
        self.assertEqual(K.pixel_problems(self.ctx), [])
        orig_inputs, orig_prefix = K.pixel_inputs, K._pixel_prefix
        try:
            def native_sheet(root):
                pngs, probs = orig_inputs(root)
                return dict(pngs, sprite_sheet=WORKSPACE / "evidence/native-sprite_sheet.png"), probs
            K.pixel_inputs = native_sheet
            self.assertTrue(any("store form" in p for p in K.pixel_problems(self.ctx)))
            K.pixel_inputs = orig_inputs
            K._pixel_prefix = lambda spec: {}
            self.assertTrue(any("donor metadata" in p for p in K.pixel_problems(self.ctx)))
        finally:
            K.pixel_inputs, K._pixel_prefix = orig_inputs, orig_prefix

    def test_voice_state_green_then_red_on_slot_drift(self):
        import wf_seasonal7_voice as V
        state = K.voice_state(self.ctx)
        if not state["packed"]:
            self.skipTest("voice not packed")
        slots = V.SLOTS
        try:
            V.SLOTS = (*slots, "battle/skill_9")
            self.assertEqual(K.voice_state(self.ctx)["missing_slots"], ["battle/skill_9"])
            V.SLOTS = tuple(s for s in slots if s != "battle/win_1")
            self.assertEqual(K.voice_state(self.ctx)["extra_voice_files"], ["battle/win_1"])
        finally:
            V.SLOTS = slots



class Revision2PanelText(unittest.TestCase):
    """第二轮面板文案两条规则（作者 2026-09-16 晚补充）。

    规则1：面板不再出现「无上限」三个字，没有上限的成长写到效果为止，后面什么都不跟；
    规则2：能力里由 ChangeSkillFlag（536/704）驱动的「技能强化」条目不写具体数字和时间。
    """

    @classmethod
    def setUpClass(cls):
        cls.design = K.load_design(ROOT)
        cls.plan = K.load_revision(ROOT)
        cls.plan2 = K.load_revision2(ROOT)
        cls.texts = K._revision2_texts(cls.plan2)

    def test_round2_is_text_only(self):
        """第二轮只允许改字符串：真源自己声明 mechanism_change=false，且只有 strings 段。"""
        self.assertIs(self.plan2["mechanism_change"], False)
        self.assertEqual(sorted(self.plan2["strings"]), sorted([K.ACTION, K.TEXT, K.CAS]))

    def test_shipped_texts_pass_both_rules(self):
        self.assertEqual(K.text_rule_problems(self.texts), [])

    def test_no_forbidden_cap_wording_anywhere(self):
        """规则1：全集里「无上限」一类措辞出现次数必须是 0。"""
        for where, text in self.texts.items():
            for word in K.FORBIDDEN_TEXT_WORDS:
                self.assertNotIn(word, text, f"{where} 出现「{word}」")

    def test_rule1_negative_forbidden_word_turns_red(self):
        """去掉规则1 的守卫必须变红：任一落点被塞进「无上限」就要报出来。"""
        for where in self.texts:
            bad = dict(self.texts)
            bad[where] = bad[where] + "（无上限）"
            problems = K.text_rule_problems(bad)
            self.assertTrue(any(where in p and "规则1" in p for p in problems), (where, problems))

    def test_rule2_negative_numbers_and_seconds_turn_red(self):
        """规则2 负向：技能强化条目里写数字 / 写秒 / 不以「强化」开头，三种都必须变红。"""
        base = dict(self.texts)
        for suffix, needle in (("：威力 +50%", "数字"), ("，持续 15 秒", "数字"), ("，持续十五秒", "秒")):
            bad = dict(base)
            bad[K.CAS_CHANGE_SKILL] = base[K.CAS_CHANGE_SKILL] + suffix
            problems = K.text_rule_problems(bad)
            self.assertTrue(any(K.CAS_CHANGE_SKILL in p and "规则2" in p for p in problems), (suffix, problems))
        bad = dict(base)
        bad[K.CAS_CHANGE_SKILL] = "对『绣球光剑·夏夜花火』追加效果"
        self.assertTrue(any("句式" in p for p in K.text_rule_problems(bad)))

    def test_rule2_does_not_police_the_722_override_text(self):
        """规则2 只约束 536 技能强化条目；722 覆盖文案里的「5个方向」是形状口径，不得误伤。"""
        self.assertIn("5", self.texts[K.CAS_PF_OVERRIDE])
        self.assertEqual(K.text_rule_problems({K.CAS_PF_OVERRIDE: self.texts[K.CAS_PF_OVERRIDE]}), [])

    def test_change_skill_still_covers_both_gated_effects(self):
        """R32 不能被本轮的「省略」吃掉：536 门控的两件事（剑雨 + 强化弹射伤害抗性下降）都还在句子里。"""
        change = self.texts[K.CAS_CHANGE_SKILL]
        self.assertIn("剑雨", change)
        self.assertIn("强化弹射伤害抗性", change)
        self.assertIn("绣球光剑·夏夜花火", change)

    def test_superseded_revision1_baseline_is_pinned(self):
        """revision1 的旧文案必须逐字可复现，否则本轮 diff 不可信。"""
        plan_cas = self.plan["strings"][K.CAS]["keys"]
        for key, entry in self.plan2["strings"][K.CAS]["keys"].items():
            superseded = plan_cas[key]["value"]
            self.assertEqual(entry["changed"], entry["value"] != superseded)
            if entry["changed"]:
                self.assertEqual(C.sha256(superseded.encode("utf-8")), entry["superseded_revision1_sha256"])
        self.assertEqual(self.plan2["strings"][K.ACTION]["value"],
                         self.plan["strings"][K.ACTION]["c1_inner_1_and_2"])
        self.assertIs(self.plan2["strings"][K.ACTION]["changed"], False)

    def test_revision2_rejects_sha_drift(self):
        """真源自带的 sha256 是防手改的：值和 sha 对不上必须 KitError。"""
        import tempfile as _tf
        doc = json.loads((ROOT / K.REVISION2_REL).read_text(encoding="utf-8"))
        doc["strings"][K.CAS]["keys"][K.CAS_CHANGE_SKILL]["value"] += "。"
        with _tf.TemporaryDirectory() as td:
            fake = Path(td) / K.REVISION2_REL
            fake.parent.mkdir(parents=True, exist_ok=True)
            fake.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(K.KitError):
                K.load_revision2(Path(td))

    def test_revision2_rejects_mechanism_claim(self):
        import tempfile as _tf
        doc = json.loads((ROOT / K.REVISION2_REL).read_text(encoding="utf-8"))
        doc["mechanism_change"] = True
        with _tf.TemporaryDirectory() as td:
            fake = Path(td) / K.REVISION2_REL
            fake.parent.mkdir(parents=True, exist_ok=True)
            fake.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(K.KitError):
                K.load_revision2(Path(td))


class ForeignKeyDelta(unittest.TestCase):
    """共享表键集合比对：``preflight`` 把「内容变了/键多了/键少了」一律标成 unclaimed_change，
    ``foreign_key_delta`` 必须把**键少了**（删除语义 —— 整文件投递会把那一行从 live 删掉）单独拎出来。"""

    CAS = K.CAS

    class _StubPack:
        """最小只读 pack：只提供 foreign_key_delta 用到的四个成员。"""

        def __init__(self, tmp: Path, pkg: dict[str, str], live: dict[str, str],
                     claimed: list[str]):
            self.root = tmp
            self.server_base = tmp / "assets"
            self._claims = [{"root": "common", "logical_path": K.CAS,
                             "codec_id": "flat", "outer_keys": list(claimed)}]
            self._pkg = tmp / "package/roots/common" / Path(*K.CAS.split("/"))
            self._pkg.parent.mkdir(parents=True, exist_ok=True)
            self._pkg.write_bytes(self._build(pkg))
            self._live = tmp / "live.orderedmap"
            self._live.write_bytes(self._build(live))

        @staticmethod
        def _build(rows: dict[str, str]) -> bytes:
            table = C.core.OrderedMap(K.CAS, list(rows), [v.encode("utf-8") for v in rows.values()],
                                      Path("<test>"))
            return C.core.build_orderedmap(table)

        def load_claims(self):
            return self._claims

        def pkg_path(self, root, logical):
            return self._pkg

        def live_table_bytes(self, logical):
            return self._live.read_bytes()

    def _delta(self, pkg, live, claimed=("change_skill_wind_oracle_yukata",)):
        with tempfile.TemporaryDirectory() as td:
            pack = self._StubPack(Path(td), pkg, live, list(claimed))
            return K.foreign_key_delta(pack)

    def test_missing_foreign_key_is_reported_as_deletion(self):
        """别家键在 live 有、包里没有 → 必须进 missing_in_package / deletion_semantics。"""
        delta = self._delta(pkg={"change_skill_wind_oracle_yukata": "a", "other": "b"},
                            live={"change_skill_wind_oracle_yukata": "A", "other": "b",
                                  "ability_skill_blackflower_wiz_yukata": "c"})
        table = delta["tables"][0]
        self.assertEqual(table["missing_in_package"], ["ability_skill_blackflower_wiz_yukata"])
        self.assertEqual(delta["missing_in_package_total"], 1)
        self.assertEqual(delta["deletion_semantics"],
                         [f"{K.CAS}:ability_skill_blackflower_wiz_yukata"])
        self.assertEqual(delta["own_key_missing"], [])      # 本包声明键在，不是本包缺陷

    def test_extra_unclaimed_key_is_reported(self):
        delta = self._delta(pkg={"change_skill_wind_oracle_yukata": "a", "ghost": "x"},
                            live={"change_skill_wind_oracle_yukata": "A"})
        self.assertEqual(delta["tables"][0]["extra_in_package"], ["ghost"])
        self.assertEqual(delta["extra_in_package_total"], 1)

    def test_own_claimed_key_missing_is_own_defect(self):
        """自家声明键没写进包 = 本包缺陷，必须与「别家影子漂移」分开报。"""
        delta = self._delta(pkg={"other": "b"}, live={"other": "b"})
        self.assertEqual(delta["own_key_missing"],
                         [f"{K.CAS}:change_skill_wind_oracle_yukata"])

    def test_clean_package_reports_nothing(self):
        """键集合完全一致时三档都必须是空的（防止本门禁恒红/恒绿）。"""
        delta = self._delta(pkg={"change_skill_wind_oracle_yukata": "a", "other": "b"},
                            live={"change_skill_wind_oracle_yukata": "A", "other": "b"})
        self.assertEqual(delta["missing_in_package_total"], 0)
        self.assertEqual(delta["extra_in_package_total"], 0)
        self.assertEqual(delta["own_key_missing"], [])
        self.assertEqual(delta["errors"], [])


@unittest.skipUnless(_live_available(), "live store unavailable")
class ForeignKeyDeltaLive(unittest.TestCase):
    """真包 × 真 live：自家声明键一个都不能少（别家键的漂移由主控 rebase 处理，不在这里判死）。"""

    def test_own_claimed_keys_all_present_in_package(self):
        delta = K.foreign_key_delta(ReadOnlyCtx().pack)
        self.assertEqual(delta["own_key_missing"], [])
        self.assertEqual(delta["errors"], [])
        self.assertTrue(delta["tables"], "共享表一张都没比到，说明 SHARED_TABLE_CLAIMS 与认领对不上")


if __name__ == "__main__":
    unittest.main()
