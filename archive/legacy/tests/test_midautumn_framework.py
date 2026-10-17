# -*- coding: utf-8 -*-
"""中秋批次薄壳框架：规格静态校验、MAPack 批目录与 ★4 母本补洞、step_kit 加载、kitlib。

需要 live store / 官方基线的用例自动跳过（与 test_seasonal7_framework 同口径）。
不写 live store / assets / .cdn，也不跑发布。
"""
from __future__ import annotations

import dataclasses
import json
import sys
import tempfile
import types
import unittest
import zlib
from pathlib import Path
from unittest import mock

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_midautumn_build as MB  # noqa: E402
import wf_midautumn_common as MC  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_midautumn_specs as MS  # noqa: E402
import wf_mod_tool as core  # noqa: E402
import wf_seasonal7_common as C  # noqa: E402


def _live_available() -> bool:
    profile = core.resolve_profile()
    return (profile is not None and profile.store.is_dir()
            and (core.project_root() / "assets" / "mana_node.json").is_file()
            and (core.project_root() / ".cdn" / "cn").is_dir())


_LIVE = _live_available()
ROSTER = ("mia", "nicola", "magnus", "charlene", "kuro", "kyle",
          "fluffy", "rolf", "stinel", "thorn", "rebecca", "hibiki")


class SpecTests(unittest.TestCase):
    def test_roster_is_unique_and_legal(self):
        self.assertEqual(tuple(MS.all_keys()), ROSTER)
        for name in ("cid", "code", "pkg_id", "workspace", "key"):
            values = [getattr(spec, name) for spec in MS.SPECS.values()]
            self.assertEqual(len(values), len(set(values)), name)
        for spec in MS.SPECS.values():
            self.assertEqual(spec.rarity, 5)
            self.assertEqual(spec.identity, spec.cid)
            self.assertEqual(spec.pkg_id, f"ma-{spec.key}-20260920")
            self.assertEqual(spec.workspace, f"work/character_packs/ma-{spec.key}")
            self.assertEqual(spec.requires_client_base, "1.4.933")
            self.assertEqual(spec.element_token, MS.ELEMENT_TOKENS[spec.element])
            self.assertEqual(spec.cid // 10000,
                             {0: 11, 1: 12, 2: 13, 3: 14, 4: 15, 5: 16}[spec.element])
            self.assertNotEqual(spec.code, spec.template_code)

    def test_two_characters_may_share_one_template(self):
        self.assertEqual(MS.SPECS["kyle"].template_id, MS.SPECS["rolf"].template_id)

    def test_element_flip_roster(self):
        flipped = {k for k, s in MS.SPECS.items() if s.element_flip}
        self.assertEqual(flipped, {"kyle", "rebecca"})

    def test_validate_rejects_workspace_outside_ma_sandbox(self):
        bad = dataclasses.replace(MS.SPECS["mia"], workspace="work/character_packs/s7-mia")
        with self.assertRaisesRegex(AssertionError, "ma-\\* sandbox"):
            MS._validate((bad,))

    def test_validate_rejects_non_five_star(self):
        bad = dataclasses.replace(MS.SPECS["mia"], rarity=4)
        with self.assertRaisesRegex(AssertionError, "★5 only"):
            MS._validate((bad,))

    def test_validate_rejects_element_token_mismatch(self):
        bad = dataclasses.replace(MS.SPECS["mia"], element_token="Blue")
        with self.assertRaises(AssertionError):
            MS._validate((bad,))

    def test_validate_rejects_seven_digit_unique_condition_id(self):
        spec = MS.SPECS["hibiki"]
        seven = dataclasses.replace(
            spec, extra_keys={MS.UNIQUE_CONDITION_LOGICAL: ("1699881",)})
        with self.assertRaisesRegex(AssertionError, "8 digits"):
            MS._validate((seven,))
        other_cid = dataclasses.replace(
            spec, extra_keys={MS.UNIQUE_CONDITION_LOGICAL: ("11999201",)})
        with self.assertRaisesRegex(AssertionError, "8 digits"):
            MS._validate((other_cid,))
        good = dataclasses.replace(
            spec, extra_keys={MS.UNIQUE_CONDITION_LOGICAL: ("16998801", "16998802")})
        MS._validate((good,))

    def test_unique_condition_id_helper(self):
        self.assertEqual(MS.unique_condition_id(169988, 1), "16998801")
        self.assertEqual(MS.unique_condition_id(119992, 12), "11999212")
        self.assertTrue(MS.unique_condition_ok(119992, "11999201"))
        self.assertFalse(MS.unique_condition_ok(119992, "1199920"))
        self.assertFalse(MS.unique_condition_ok(119992, "11999200"))
        with self.assertRaises(ValueError):
            MS.unique_condition_id(119992, 0)

    def test_text_placeholders_reported_until_design_lands(self):
        self.assertEqual(MS.text_placeholders(MS.SPECS["mia"]), ["title", "profile", "leader"])
        filled = dataclasses.replace(MS.SPECS["mia"],
                                     texts={**MS.SPECS["mia"].texts, "title": "月下的宝藏猎人",
                                            "profile": "简介", "leader": "队长技名"})
        self.assertEqual(MS.text_placeholders(filled), [])

    def test_get_spec_merges_design_then_kit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / MS.BATCH_DIR / "design").mkdir(parents=True)
            MS.design_path(root, "mia").write_text(json.dumps({
                "spec": {"stance": "Supporter", "theme": "设计稿主题",
                         "required_capabilities": ["panel-description-override-v2"],
                         "extra_keys": {MS.UNIQUE_CONDITION_LOGICAL: ["11999201"]}},
                "texts": {"title": "设计稿称号", "profile": "设计稿简介", "leader": "设计稿队长技"},
            }, ensure_ascii=False), encoding="utf-8")
            module = types.SimpleNamespace(TEXTS={"leader": "kit 队长技"},
                                           SPEC={"backdrop_colors": ((1, 2, 3), (4, 5, 6))})
            with mock.patch.object(MS, "load_kit_module", return_value=module):
                spec = MS.get_spec("mia", root=root)
            self.assertEqual(spec.stance, "Supporter")
            self.assertEqual(spec.theme, "设计稿主题")
            self.assertEqual(spec.texts["title"], "设计稿称号")
            self.assertEqual(spec.texts["leader"], "kit 队长技")          # kit 覆盖 design
            self.assertEqual(spec.backdrop_colors, ((1, 2, 3), (4, 5, 6)))
            self.assertEqual(spec.required_capabilities, ("panel-description-override-v2",))
            self.assertEqual(spec.extra_keys, {MS.UNIQUE_CONDITION_LOGICAL: ("11999201",)})
            with mock.patch.object(MS, "load_kit_module", return_value=None):
                bare = MS.get_spec("mia", root=root, with_design=False)
            self.assertEqual(bare.stance, "Attacker")

    def test_design_json_may_not_override_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / MS.BATCH_DIR / "design").mkdir(parents=True)
            MS.design_path(root, "mia").write_text(json.dumps({"spec": {"cid": 111111}}),
                                                   encoding="utf-8")
            with mock.patch.object(MS, "load_kit_module", return_value=None):
                with self.assertRaisesRegex(ValueError, "identity/texts"):
                    MS.get_spec("mia", root=root)

    def test_kit_spec_may_not_override_template(self):
        module = types.SimpleNamespace(SPEC={"template_id": 1}, TEXTS={})
        with mock.patch.object(MS, "load_kit_module", return_value=module):
            with self.assertRaisesRegex(ValueError, "identity/texts"):
                MS.get_spec("mia", with_design=False)

    def test_resolve_keys(self):
        self.assertEqual(MS.resolve_keys("all"), list(ROSTER))
        self.assertEqual(MS.resolve_keys("mia,kyle"), ["mia", "kyle"])
        with self.assertRaises(KeyError):
            MS.resolve_keys("nobody")

    def test_kit_module_name(self):
        self.assertEqual(MS.kit_module_name("mia"), "wf_midautumn_kit_mia")


class PackTests(unittest.TestCase):
    def test_batch_dir_points_at_this_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "store" / "upload").mkdir(parents=True)
            pack = MC.MAPack(MS.SPECS["mia"], root=root, store=root / "store" / "upload",
                             workspace=root / "ws", server_base=root / "assets",
                             use_official=False)
            self.assertEqual(pack.batch_dir, root / MS.BATCH_DIR)
            self.assertNotEqual(pack.batch_dir, root / "work/character_packs/seasonal7-20260916")

    def test_rarity_upgrades_target_the_registered_templates(self):
        for key, entry in MC.RARITY_UPGRADES.items():
            self.assertIn(key, MS.SPECS)
            self.assertEqual(entry.template_id, MS.SPECS[key].template_id)
            self.assertTrue(entry.status_donor.isdigit())
            self.assertIsNone(entry.mana_donor, "玛纳消耗实测与稀有度无关，默认不换 donor")

    def test_upgrade_rejects_template_drift(self):
        spec = dataclasses.replace(MS.SPECS["nicola"], template_id=111141,
                                   template_code="tiger_treasure_hunter_xm22",
                                   template_identity=241001)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "store" / "upload").mkdir(parents=True)
            pack = MC.MAPack(spec, root=root, store=root / "store" / "upload",
                             workspace=root / "ws", server_base=root / "assets",
                             use_official=False)
            with self.assertRaisesRegex(C.S7Error, "rarity upgrade targets template"):
                _ = pack.upgrade

    @unittest.skipUnless(_LIVE, "requires live store and official baseline archives")
    def test_four_star_template_status_row_is_replaced_by_five_star_donor(self):
        spec = MS.get_spec("nicola", with_kit=False, with_design=False)
        pack = MC.MAPack(spec)
        plain = C.S7Pack(spec)
        official = plain.template_raw(MC.STATUS)
        upgraded = pack.template_raw(MC.STATUS)
        donor = MC.RARITY_UPGRADES["nicola"].status_donor
        self.assertEqual(upgraded["211020"], official[donor])
        self.assertNotEqual(upgraded["211020"], official["211020"])
        self.assertEqual(self._lv100(upgraded["211020"]), self._lv100(official[donor]))
        self.assertGreater(int(self._lv100(upgraded["211020"])[1]),
                           int(self._lv100(official["211020"])[1]), "★5 donor 的 ATK 必须高于 ★4 母本")
        # 只动 character_status：gacha_sound / mana 两表保持母本字节
        for logical in (MC.GACHA_SOUND, MC.MANA_NODE, MC.MANA_BOARD):
            self.assertEqual(pack.template_raw(logical)["211020"],
                             plain.template_raw(logical)["211020"], logical)

    @unittest.skipUnless(_LIVE, "requires live store and official baseline archives")
    def test_five_star_template_is_untouched(self):
        pack = MC.MAPack(MS.get_spec("mia", with_kit=False, with_design=False))
        plain = C.S7Pack(pack.spec)
        self.assertIsNone(pack.upgrade)
        for logical in (MC.STATUS, MC.GACHA_SOUND, MC.MANA_NODE):
            self.assertEqual(pack.template_raw(logical)["111141"],
                             plain.template_raw(logical)["111141"])

    @unittest.skipUnless(_LIVE, "requires live store and official baseline archives")
    def test_mana_donor_is_remapped_onto_the_template_prefix(self):
        spec = MS.get_spec("nicola", with_kit=False, with_design=False)
        entry = dataclasses.replace(MC.RARITY_UPGRADES["nicola"], mana_donor="111153")
        pack = MC.MAPack(spec)
        with mock.patch.dict(MC.RARITY_UPGRADES, {"nicola": entry}):
            blob = pack.template_raw(MC.MANA_NODE)["211020"]
        ids = self._node_ids(blob)
        self.assertTrue(ids)
        # donor 前缀 222306 已改回母本前缀 422040，tables 后面那一步才改得到新角色前缀
        self.assertTrue(all(node.startswith(spec.template_mana_prefix) for node in ids), sorted(ids)[:4])

    @unittest.skipUnless(_LIVE, "requires live store and official baseline archives")
    def test_rarity_problems_and_median_donor_rule(self):
        for key in ("mia", "nicola", "kuro", "rebecca", "kyle"):
            pack = MC.MAPack(MS.get_spec(key, with_kit=False, with_design=False))
            self.assertEqual(MC.rarity_problems(pack), [], key)
        pack = MC.MAPack(MS.get_spec("nicola", with_kit=False, with_design=False))
        expected = MC.median_donor(pack, 0, 4)
        self.assertEqual(expected["cid"], MC.RARITY_UPGRADES["nicola"].status_donor)
        with mock.patch.dict(MC.RARITY_UPGRADES,
                             {"nicola": dataclasses.replace(MC.RARITY_UPGRADES["nicola"],
                                                            status_donor="111003")}):
            self.assertTrue(any("median" in p for p in MC.rarity_problems(pack)))

    @unittest.skipUnless(_LIVE, "requires live store and official baseline archives")
    def test_no_gacha_se_mapping_needed_for_the_two_flipped_characters(self):
        for key in ("kyle", "rebecca"):
            pack = MC.MAPack(MS.get_spec(key, with_kit=False, with_design=False))
            self.assertTrue(pack.spec.element_flip)
            self.assertEqual(MC.gacha_flip_gaps(pack), [], key)

    @staticmethod
    def _lv100(blob: bytes):
        inner = core.read_orderedmap_raw_rows_from_bytes(blob, "status")
        levels = dict(zip(inner.keys, inner.rows))
        return core.read_csv_lines(zlib.decompress(levels["100"]).decode("utf-8"))[0]

    @staticmethod
    def _node_ids(blob: bytes) -> set[str]:
        boards = core.read_orderedmap_raw_rows_from_bytes(blob, "n")
        found = set()
        for board in boards.rows:
            slots = core.read_orderedmap_raw_rows_from_bytes(board, "s")
            for raw in slots.rows:
                for row in core.read_csv_lines(zlib.decompress(raw).decode("utf-8")):
                    if row:
                        found.add(row[0])
        return found


class BuildTests(unittest.TestCase):
    def _pack(self, root: Path, key: str = "mia") -> MC.MAPack:
        (root / "store" / "upload").mkdir(parents=True, exist_ok=True)
        (root / "assets").mkdir(exist_ok=True)
        return MC.MAPack(MS.SPECS[key], root=root, store=root / "store" / "upload",
                         workspace=root / "ws" / f"ma-{key}", server_base=root / "assets",
                         use_official=False)

    def test_step_kit_skips_when_module_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack = self._pack(Path(tmp))
            with mock.patch.object(MS, "load_kit_module", return_value=None):
                result = MB.step_kit(pack)
            self.assertTrue(result["skipped"])
            self.assertIn("wf_midautumn_kit_mia", result["reason"])

    def test_step_kit_calls_the_batch_module(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack = self._pack(Path(tmp))
            seen = {}

            def build(ctx):
                seen["cid"] = ctx.spec.cid
                seen["batch_dir"] = ctx.pack.batch_dir
                return {"ok": True}

            with mock.patch.object(MS, "load_kit_module",
                                   return_value=types.SimpleNamespace(build=build)):
                result = MB.step_kit(pack)
            self.assertEqual(result, {"skipped": False, "result": {"ok": True}})
            self.assertEqual(seen["cid"], 119992)
            self.assertEqual(seen["batch_dir"], Path(tmp) / MS.BATCH_DIR)

    def test_step_kit_rejects_module_without_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack = self._pack(Path(tmp))
            with mock.patch.object(MS, "load_kit_module", return_value=types.SimpleNamespace()):
                with self.assertRaisesRegex(C.S7Error, "has no build"):
                    MB.step_kit(pack)

    def test_load_landmarks_accepts_both_shapes(self):
        entries = [{"face": [1, 2]}, {"face": [3, 4]}]
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "mia.json").write_text(json.dumps(entries), encoding="utf-8")
            (folder / "combined.json").write_text(json.dumps({"mia": entries}), encoding="utf-8")
            self.assertEqual(MB.load_landmarks(folder / "mia.json", "mia"), entries)
            self.assertEqual(MB.load_landmarks(folder, "mia"), entries)
            self.assertEqual(MB.load_landmarks(folder / "combined.json", "mia"), entries)
            with self.assertRaises(C.S7Error):
                MB.load_landmarks(folder / "combined.json", "kyle")

    def test_resolve_masters_accepts_underscore_naming(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pack = self._pack(root)
            pack.evidence.mkdir(parents=True, exist_ok=True)
            masters = root / "masters"
            masters.mkdir()
            for level in (0, 1):
                (masters / f"mia_{level}.png").write_bytes(b"png" + bytes([level]))
            resolved = MB.resolve_masters(pack, masters)
            self.assertEqual(resolved, pack.evidence / "art" / "_masters")
            self.assertEqual((resolved / "mia-0.png").read_bytes(), b"png\x00")
            # 连字符命名直接用原目录，不复制
            hyphen = root / "masters2"
            hyphen.mkdir()
            for level in (0, 1):
                (hyphen / f"mia-{level}.png").write_bytes(b"x")
            self.assertEqual(MB.resolve_masters(pack, hyphen), hyphen)

    def test_resolve_masters_reports_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pack = self._pack(root)
            pack.evidence.mkdir(parents=True, exist_ok=True)
            masters = root / "masters"
            masters.mkdir()
            (masters / "mia_0.png").write_bytes(b"x")
            with self.assertRaisesRegex(C.S7Error, "master art missing"):
                MB.resolve_masters(pack, masters)

    def test_default_paths_point_at_this_batch(self):
        root = Path("D:/nowhere")
        self.assertEqual(MB.default_masters(root), root / MS.BATCH_DIR / "art" / "masters")
        self.assertEqual(MB.default_landmarks(root, "mia"),
                         root / MS.BATCH_DIR / "art" / "landmarks" / "mia.json")
        self.assertEqual(MB.default_mask_cache(root),
                         root / MS.BATCH_DIR / "art" / "official-shape-masks.npz")

    def test_ledger_tail_prefers_the_last_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            active = root / ".cdn" / "cn" / "character-releases" / "active.json"
            active.parent.mkdir(parents=True)
            active.write_text(json.dumps({"base_version": "1.4.927", "releases": [
                {"from_version": "1.4.927", "version": "1.4.928"}]}), encoding="utf-8")
            self.assertEqual(MB.ledger_tail(root), "1.4.928")
            active.write_text(json.dumps({"base_version": "1.4.927", "releases": []}),
                              encoding="utf-8")
            self.assertEqual(MB.ledger_tail(root), "1.4.927")
            active.unlink()
            self.assertIsNone(MB.ledger_tail(root))

    def test_spec_warnings_tolerate_hand_written_design_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / MS.BATCH_DIR / "design").mkdir(parents=True)
            MS.design_path(root, "mia").write_text(json.dumps({
                "spec": {"cid": 119992,                       # 与注册表一致的重复声明：接受
                         "pf_type": None,                     # None = 沿用
                         "race": "Beast",                     # 不认识 → 警告
                         "stance_why": "注释字段",              # 注释 → 忽略
                         "backdrop_colors": {"hair": "#fff"}},  # 形状不对 → 警告并忽略
                "texts": {"title": "月下的宝藏猎人", "profile": "简介", "leader": "队长技",
                          "profile_len": 42,      # 注释后缀 → 静默忽略
                          "subtitle": "x",        # 真的不认识 → 警告
                          "cv": None},
            }, ensure_ascii=False), encoding="utf-8")
            warnings: list[str] = []
            with mock.patch.object(MS, "load_kit_module", return_value=None):
                spec = MS.get_spec("mia", root=root, warnings=warnings)
            self.assertEqual(spec.pf_type, 2)
            self.assertEqual(spec.backdrop_colors, MS.SPECS["mia"].backdrop_colors)
            self.assertEqual(spec.texts["title"], "月下的宝藏猎人")
            self.assertIsNone(spec.texts["cv"])
            self.assertEqual(len(warnings), 3, warnings)
            self.assertTrue(any("race" in w for w in warnings))
            self.assertTrue(any("backdrop_colors" in w for w in warnings))
            self.assertTrue(any("subtitle" in w for w in warnings))
            self.assertFalse(any("profile_len" in w for w in warnings))

    def test_design_conflicting_identity_is_a_hard_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / MS.BATCH_DIR / "design").mkdir(parents=True)
            MS.design_path(root, "mia").write_text(json.dumps({"spec": {"cid": 119993}}),
                                                   encoding="utf-8")
            with mock.patch.object(MS, "load_kit_module", return_value=None):
                with self.assertRaisesRegex(ValueError, "may not override"):
                    MS.get_spec("mia", root=root)

    def test_steps_cover_the_documented_set(self):
        self.assertEqual(set(MB.STEPS), {"check", "init", "tables", "kit", "assets", "manifest",
                                         "art", "status", "inspect", "preflight"})


class KitLibTests(unittest.TestCase):
    def test_apply_cells_extends_and_stringifies(self):
        row = ["a", "b"]
        self.assertEqual(KL.apply_cells(row, {1: "B", 4: 7}),
                         ["a", "B", "", "", "7"])
        self.assertEqual(row, ["a", "b"], "输入行不得被改")
        self.assertEqual(KL.apply_cells(["a"], {"2": None}, 4), ["a", "", "", ""])
        self.assertEqual(len(KL.apply_cells(["a"], {}, KL.ABILITY_NCOLS)), 126)
        with self.assertRaises(KL.KitError):
            KL.apply_cells(["a"] * 130, {}, KL.ABILITY_NCOLS)
        with self.assertRaises(KL.KitError):
            KL.apply_cells(["a"], {-1: "x"})

    def test_panel_rules(self):
        self.assertEqual(KL.panel_problems("攻击力提升"), [])
        self.assertTrue(KL.panel_problems("自身为队长时攻击力提升"))
        self.assertTrue(KL.panel_problems("生命值100%以下时攻击力提升"))
        self.assertTrue(KL.panel_problems("攻击力提升（无上限）"))
        self.assertTrue(KL.panel_problems("攻击力提升（觉醒后30%）"))
        self.assertEqual(KL.panel_problems("技能强化", skill_flag=True), [])
        self.assertTrue(KL.panel_problems("技能强化 10 秒", skill_flag=True))
        with self.assertRaises(KL.KitError):
            KL.check_panel("自身为队长时……")

    def test_check_ability_key(self):
        row = ["code_1", "true", "attack_red"] + [""] * 123
        KL.check_ability_key([row, list(row)], "1199921", "code", 1)
        with self.assertRaisesRegex(KL.KitError, "mixed c1/c2"):
            KL.check_ability_key([row, KL.apply_cells(row, {1: "false"})], "1199921", "code", 1)
        with self.assertRaisesRegex(KL.KitError, "!= code_2"):
            KL.check_ability_key([row], "1199922", "code", 2)
        with self.assertRaisesRegex(KL.KitError, "statue group"):
            KL.check_ability_key([KL.apply_cells(row, {2: "attack_pink"})],
                                 "1199921", "code", 1)

    def test_lut_missing_file_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(KL.png_transform_from_lut(Path(tmp) / "fx_lut.json"))

    def test_lut_rejects_unknown_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fx_lut.json"
            path.write_text(json.dumps({"schema": "nope"}), encoding="utf-8")
            with self.assertRaisesRegex(KL.KitError, "schema"):
                KL.png_transform_from_lut(path)

    def test_lut_exact_mapping_preserves_alpha(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fx_lut.json"
            path.write_text(json.dumps({"schema": KL.LUT_SCHEMA, "mode": "exact",
                                        "exact": {"#3f8fe0": "#e0c23f"}}), encoding="utf-8")
            transform = KL.png_transform_from_lut(path)
            image = Image.new("RGBA", (2, 1))
            image.putpixel((0, 0), (0x3F, 0x8F, 0xE0, 200))
            image.putpixel((1, 0), (0x3F, 0x8F, 0xE0, 0))      # 全透明：连 RGB 都不动
            out = transform(image)
            self.assertEqual(out.getpixel((0, 0)), (0xE0, 0xC2, 0x3F, 200))
            self.assertEqual(out.getpixel((1, 0)), (0x3F, 0x8F, 0xE0, 0))
            self.assertEqual(out.mode, "RGBA")

    def test_lut_hue_range_mapping(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fx_lut.json"
            path.write_text(json.dumps({
                "schema": KL.LUT_SCHEMA, "mode": "hue",
                "hue": [{"from": [90, 170], "sat_min": 0.2, "val_min": 0.05, "hue_set": 52}],
            }), encoding="utf-8")
            transform = KL.png_transform_from_lut(path)
            image = Image.new("RGBA", (3, 1))
            image.putpixel((0, 0), (0, 255, 64, 255))       # 绿（色相约 135）→ 黄
            image.putpixel((1, 0), (255, 0, 0, 255))        # 红（色相 0）→ 不动
            image.putpixel((2, 0), (250, 250, 250, 255))    # 近白低饱和 → 不动
            out = transform(image)
            r, g, b, a = out.getpixel((0, 0))
            self.assertEqual(a, 255)
            self.assertGreater(r, 200)
            self.assertGreater(g, 200)
            self.assertLess(b, 80)
            self.assertEqual(out.getpixel((1, 0)), (255, 0, 0, 255))
            self.assertEqual(out.getpixel((2, 0)), (250, 250, 250, 255))

    def test_lut_both_modes_run_exact_first(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fx_lut.json"
            path.write_text(json.dumps({
                "schema": KL.LUT_SCHEMA, "mode": "both",
                "exact": {"#00ff40": "#112233"},
                "hue": [{"from": [90, 170], "hue_set": 52}],
            }), encoding="utf-8")
            transform = KL.png_transform_from_lut(path)
            image = Image.new("RGBA", (1, 1))
            image.putpixel((0, 0), (0, 255, 64, 255))
            self.assertEqual(transform(image).getpixel((0, 0)), (0x11, 0x22, 0x33, 255))

    def test_install_staged_assets_skips_missing_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "store" / "upload").mkdir(parents=True)
            (root / "assets").mkdir()
            pack = MC.MAPack(MS.SPECS["mia"], root=root, store=root / "store" / "upload",
                             workspace=root / "ws" / "ma-mia", server_base=root / "assets",
                             use_official=False)
            import wf_seasonal7_build as B
            B.step_init(pack)
            ctx = B.KitContext(pack)
            staged = pack.batch_dir / "pixel" / "mia"
            staged.mkdir(parents=True)
            (staged / "sheet.png").write_bytes(b"\x89png-ish")
            (staged / "install.json").write_text(json.dumps([
                {"root": "common", "logical": "character/x/pixelart/sheet.png",
                 "file": "sheet.png", "owner": "pixel"},
                {"root": "common", "logical": "character/x/pixelart/absent.png",
                 "file": "absent.png"},
            ]), encoding="utf-8")
            report = KL.install_staged_assets(ctx)
            self.assertTrue(report["present"])
            self.assertEqual(len(report["installed"]), 1)
            self.assertEqual(report["skipped"][0]["reason"], "missing")
            self.assertEqual(pack.owner_of("common", "character/x/pixelart/sheet.png"), "pixel")
            self.assertEqual(KL.install_staged_assets(ctx, staged / "nothere.json")["present"], False)

    def test_install_staged_assets_rejects_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "store" / "upload").mkdir(parents=True)
            (root / "assets").mkdir()
            pack = MC.MAPack(MS.SPECS["mia"], root=root, store=root / "store" / "upload",
                             workspace=root / "ws" / "ma-mia", server_base=root / "assets",
                             use_official=False)
            import wf_seasonal7_build as B
            B.step_init(pack)
            outside = root / "outside.png"
            outside.write_bytes(b"x")
            staged = pack.batch_dir / "pixel" / "mia"
            staged.mkdir(parents=True)
            (staged / "install.json").write_text(json.dumps([
                {"root": "common", "logical": "a/b.png", "file": str(outside)}]), encoding="utf-8")
            with self.assertRaisesRegex(KL.KitError, "escapes the batch directory"):
                KL.install_staged_assets(B.KitContext(pack))

    def _staged_pack(self, tmp: str):
        root = Path(tmp)
        (root / "store" / "upload").mkdir(parents=True)
        (root / "assets").mkdir()
        pack = MC.MAPack(MS.SPECS["nicola"], root=root, store=root / "store" / "upload",
                         workspace=root / "ws" / "ma-nicola", server_base=root / "assets",
                         use_official=False)
        import wf_seasonal7_build as B
        B.step_init(pack)
        staged = pack.batch_dir / "pixel" / "nicola"
        staged.mkdir(parents=True)
        return pack, staged, B

    def _stage_metadata(self, staged: Path, payload: bytes) -> None:
        (staged / "meta.amf3.deflate").write_bytes(payload)
        (staged / "install.json").write_text(json.dumps([
            {"root": "common",
             "logical": "character/sorceress_teacher_moon/pixelart/pixelart.frame.amf3.deflate",
             "file": "meta.amf3.deflate", "owner": "pixel"}]), encoding="utf-8")

    def test_install_staged_assets_rejects_donor_texture_paths(self):
        """20260920 真机事故：母本元数据「字节不动」交付 → 客户端取母本图集 → 领取演出 C8003。

        母本 ``sorceress_teacher`` 正好是新 code ``sorceress_teacher_moon`` 的前缀，
        这条用例同时钉住「按路径段匹配、前缀不漏判」。
        """
        with tempfile.TemporaryDirectory() as tmp:
            pack, staged, B = self._staged_pack(tmp)
            self._stage_metadata(staged, zlib.compress(
                b"character/sorceress_teacher/pixelart/sprite_sheet"))
            with self.assertRaisesRegex(KL.KitError, "embeds another character's texture paths"):
                KL.install_staged_assets(B.KitContext(pack))
            self.assertFalse(pack.pkg_has(
                "common", "character/sorceress_teacher_moon/pixelart/pixelart.frame.amf3.deflate"),
                "被拒绝的交付件不许留在包里")

    def test_install_staged_assets_accepts_rewritten_metadata(self):
        """像素母本 ≠ kit 表母本时元数据必须自带（米娅先例），改写干净就该放行。"""
        with tempfile.TemporaryDirectory() as tmp:
            pack, staged, B = self._staged_pack(tmp)
            self._stage_metadata(staged, zlib.compress(
                b"character/sorceress_teacher_moon/pixelart/sprite_sheet"))
            report = KL.install_staged_assets(B.KitContext(pack))
            self.assertEqual(len(report["installed"]), 1)
            self.assertEqual(pack.owner_of(
                "common", "character/sorceress_teacher_moon/pixelart/pixelart.frame.amf3.deflate"),
                "pixel")

    def test_install_staged_assets_allows_official_effect_references(self):
        """裁决 §4：只引用不改色的官方特效直接写官方路径，不许被这道闸误杀。"""
        with tempfile.TemporaryDirectory() as tmp:
            pack, staged, B = self._staged_pack(tmp)
            self._stage_metadata(staged, zlib.compress(
                b"battle/effect/skill_unique/sorceress_teacher/fire_01"))
            self.assertEqual(len(KL.install_staged_assets(B.KitContext(pack))["installed"]), 1)

    def test_report_rejects_forbidden_panel_text_and_bad_status(self):
        ctx = _StubCtx()
        with self.assertRaisesRegex(KL.KitError, "panel text"):
            KL.report(ctx, summary="x", panel=["自身为队长时攻击力提升"])
        with self.assertRaisesRegex(KL.KitError, "kit status"):
            KL.report(ctx, summary="x", status="done")

    def test_report_writes_fingerprint(self):
        ctx = _StubCtx()
        value = KL.report(ctx, summary="draft", panel=["攻击力提升"], notes=["n"],
                          programs=["battle/action/skill/x.action.dsl.amf3.deflate"],
                          required_capabilities=["panel-description-override-v2"],
                          deviations=[{"want": "a", "got": "b", "why": "c"}])
        self.assertEqual(value["status"], KL.DRAFT)
        self.assertEqual(ctx.reported, value)
        self.assertEqual(len(value["kit_fingerprint"]), 64)
        self.assertEqual(value["deviations"][0]["why"], "c")
        again = KL.report(ctx, summary="draft", panel=["攻击力提升"], notes=["n"],
                          programs=["battle/action/skill/x.action.dsl.amf3.deflate"],
                          required_capabilities=["panel-description-override-v2"],
                          deviations=[{"want": "a", "got": "b", "why": "c"}])
        self.assertEqual(again["kit_fingerprint"], value["kit_fingerprint"])


class _StubPack:
    def __init__(self):
        self._claims = [{"root": "common", "logical_path": "t", "codec_id": "flat",
                         "outer_keys": ["1"], "inner_keys": [], "semantic_claims": []}]

    def load_claims(self):
        return list(self._claims)

    def owned_outputs(self):
        return {"common:a.png": "kit"}

    def owned_record(self, root, logical):
        return {"owner": "kit", "sha256": "0" * 64}

    def pkg_dsl_programs(self):
        return []


class _StubCtx:
    def __init__(self):
        self.pack = _StubPack()
        self.spec = MS.SPECS["mia"]
        self.reported = None

    def report(self, value):
        self.reported = value


@unittest.skipUnless(_LIVE, "requires live store, repo assets and official baseline archives")
def _published_keys(root):
    """已由 flow 发布的角色：其键被自己占用是预期，不再参与「未占用」断言。"""
    import json
    ledger = root / ".cdn" / "cn" / "character-releases" / "active.json"
    if not ledger.is_file():
        return set()
    data = json.loads(ledger.read_text(encoding="utf-8"))
    owned = {r.get("package_id") for r in data.get("releases", [])}
    # base_package_owners 的形状随账本版本变过（dict / list[dict] / list[list]），只取字符串
    text = json.dumps(data.get("base_package_owners", []), ensure_ascii=False)
    owned |= {MS.SPECS[k].pkg_id for k in MS.all_keys() if f'"{MS.SPECS[k].pkg_id}"' in text}
    return {k for k in MS.all_keys() if MS.SPECS[k].pkg_id in owned}


class LiveCheckTests(unittest.TestCase):
    def test_whole_roster_is_unoccupied(self):
        probe = MC.MAPack(MS.SPECS[MS.all_keys()[0]])
        published = _published_keys(probe.root)
        specs = [MS.SPECS[k] for k in MS.all_keys() if k not in published]
        if not specs:
            self.skipTest("whole roster already published")
        problems = MS.occupancy_problems(specs, repo_root=probe.root, store=probe.store)
        self.assertEqual({k: v for k, v in problems.items() if v}, {})

    def test_check_step_is_clean_for_every_character(self):
        published = _published_keys(MC.MAPack(MS.SPECS[MS.all_keys()[0]]).root)
        for key in MS.all_keys():
            if key in published:
                continue
            pack = MC.MAPack(MS.get_spec(key, with_kit=False, with_design=False))
            result = MB.step_check(pack)
            self.assertEqual(result["occupancy"], [], key)
            self.assertEqual(result["rarity"], [], key)
            self.assertEqual(result["gacha_flip_gaps"], [], key)


if __name__ == "__main__":
    unittest.main()
