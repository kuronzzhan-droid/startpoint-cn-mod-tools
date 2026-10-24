# -*- coding: utf-8 -*-
"""战斗图集预算预检(wf_atlas_budget_check)回归。

黄金值来自 2026-09-17 的资源体量审计
(`work/character_packs/seasonal7-20260916/audit-assets-20260917/report.md` §0 编队表,
 逐条落在 `scripts/_verify_scen.json` 里),两组都是**用客户端真打包器实跑过的**:

  * FITS     五重 round0 底座 + 最重 9 个自制主位 → 73 张 / 14.479722 Mpx / 86.31% / 4094×4087
  * OVERFLOW 上面那间房 + 本批 7 人上协力       → 92 张 / 16.191179 Mpx / 96.51%,
             卡在 battle/effect/skill_unique/unicorn_lancer_rose/unicorn_lancer_rose

这两组的逐张尺寸冻结在 `mod-tools/atlas_budget_roster.json` 的 `golden_formations` 里,
所以本文件**不依赖 store 现状**;打包器实现一改就红。

负向对照:每条正向断言都配一条「把它弄坏必须变红」的对照,
否则「测试通过」只能证明测试跑过,不能证明它在测东西。
"""
from __future__ import annotations

import contextlib
import io
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import wf_atlas_budget_check as G  # noqa: E402

GOLDEN_FITS = "audit-20260917-r0-heavy9-mains"
GOLDEN_OVERFLOW = "audit-20260917-r0-heavy9-plus-seasonal7-unison"


def png_stub(width: int, height: int, magic: bytes = b"\x89PNG\r\n\x1a\n") -> bytes:
    """够 png_dims_from_bytes 解的最小 PNG 头(store 里的魔数是小写 \\x89png)。"""
    return (magic + struct.pack(">I", 13) + b"IHDR"
            + struct.pack(">II", width, height) + b"\x08\x06\x00\x00\x00" + b"\x00" * 4)


def run_cli(argv: list[str]) -> tuple[int, dict, str]:
    """跑一次 CLI,返回 (退出码, 最后一行 JSON, 全部 stdout)。"""
    buf = io.StringIO()
    saved = sys.stdout
    try:
        with contextlib.redirect_stdout(buf):
            code = G.main(argv)
    finally:
        sys.stdout = saved
    text = buf.getvalue()
    last = json.loads(text.strip().splitlines()[-1])
    return code, last, text


def tiny_roster(char_sheet: list[int], boss_sheet: list[int] = None) -> dict:
    """一间可控的小房间:一个 boss 底座 + 三个自制角色,用来验归因与阈值分支。"""
    boss_sheet = boss_sheet or [1000, 1000]
    chars = {}
    for index, name in enumerate(("cust_a", "cust_b", "cust_c")):
        chars[name] = {
            "id": str(100000 + index), "group": "custom",
            "pixelart": {"character/%s/pixelart/sprite_sheet" % name: list(char_sheet)},
            "skill_sheets": {"battle/effect/skill_unique/%s/fx/fx" % name: [64, 64]},
            "pf_sheets": {"battle/effect/powerflip/%s_pf/pf/pf" % name: [32, 32]},
            "ui_layer1": {"character/%s/ui/square_0" % name: [212, 212]},
        }
    return {
        "schema": "wf-atlas-budget-roster/1", "generated": "test",
        "atlas": {"width": 4096, "height": 4096, "margin": 2},
        "shared": {"battle/common/layer0": [252, 2646]},
        "bosses": {"b1": {"base": {"battle/boss/b1/b1": boss_sheet}, "effects": {}}},
        "scenarios": {"solo": {"label": "测试场景", "bosses": ["b1"]}},
        "characters": chars,
        "golden_formations": [],
    }


class PackerCase(unittest.TestCase):
    """打包器本身:margin、旋转、容量、溢出。"""

    def test_margin_is_counted_in_area(self):
        self.assertEqual(G.rect_area((10, 20)), 12 * 22)

    def test_single_sheet_uses_short_side_as_width(self):
        # 客户端把长边竖过来:1000×100 放下去占 102 宽、1002 高。
        used = G.pack([("x", 1000, 100)])
        self.assertEqual(used, (100, 1000))

    def test_overflow_names_the_stuck_rect(self):
        with self.assertRaises(G.Overflow) as caught:
            G.pack([("too_wide", 5000, 100)])
        self.assertIn("too_wide", str(caught.exception))

    def test_pack_sheets_reports_fill(self):
        verdict = G.pack_sheets({"a": [4094, 4094]})
        self.assertTrue(verdict["fits"])
        self.assertEqual(verdict["px"], 4096 * 4096)
        self.assertEqual(verdict["fill_pct"], 100.0)

    def test_pack_is_order_independent(self):
        sheets = {"a": [100, 200], "b": [300, 40], "c": [50, 900]}
        forward = G.pack_sheets(sheets)
        backward = G.pack_sheets({k: sheets[k] for k in reversed(list(sheets))})
        self.assertEqual(forward["used"], backward["used"])


class LayerRuleCase(unittest.TestCase):
    """分层判据:autoDistribute 的两条流,逐条对应反编译里的 EReg。"""

    def test_layer0_families(self):
        for sheet in ("battle/common/layer0",
                      "battle/effect/skill_unique/x/x",
                      "battle/field_object/world_sand/a/b/b",
                      "battle/boss/abyss_cloud/abyss_cloud",
                      "battle/zako/a/a", "battle/funnel/a/a",
                      "character/ginovi/pixelart/sprite_sheet",
                      "battle/uncommon/layer0/a/a",
                      "quest/x/battle/field/a/a"):
            self.assertEqual(G.sprite_sheet_layer(sheet), "layer0", sheet)

    def test_layer1_families(self):
        for sheet in ("battle/common/layer1", "battle/common/boss_rush_layer1",
                      "battle/common/score_attack", "battle/common/score_attack2",
                      "battle/common/disguise_hp", "battle/common/attention",
                      "battle/tutorial/a/a", "item/sprite_sheet",
                      "battle/uncommon/layer1/a/a"):
            self.assertEqual(G.sprite_sheet_layer(sheet), "layer1", sheet)

    def test_unknown_sheet_has_no_layer(self):
        # 客户端在这里 throw "UNDEFINED LAYER";我们返回 None 并把它排除。
        self.assertIsNone(G.sprite_sheet_layer("master/character/character"))

    def test_character_ui_is_layer1_only_for_the_four_battle_slots(self):
        for slot in G.BATTLE_UI_SLOTS:
            self.assertTrue(G.battle_ui_image("character/x/ui/%s_0" % slot))
            self.assertTrue(G.battle_ui_image("character/x/ui/%s_1" % slot))
        for other in ("full_shot_1440_1920_0", "thumb_party_main_0",
                      "square_132_132_0", "skill_cutin_0"):
            self.assertFalse(G.battle_ui_image("character/x/ui/" + other), other)

    def test_special_sprite_sheet_is_not_loaded_in_battle(self):
        loaded, why = G.loaded_in_battle("character/x/pixelart/special_sprite_sheet")
        self.assertFalse(loaded)
        self.assertIn("special_sprite_sheet", why)
        self.assertTrue(G.loaded_in_battle("character/x/pixelart/sprite_sheet")[0])


class GoldenFormationCase(unittest.TestCase):
    """审计实测过的两组编队,逐位复算。"""

    @classmethod
    def setUpClass(cls):
        cls.roster = G.load_roster()
        cls.golden = {g["name"]: g for g in cls.roster["golden_formations"]}

    def test_known_fits_formation(self):
        golden = self.golden[GOLDEN_FITS]
        got = G.pack_sheets(golden["sheets"])
        self.assertTrue(got["fits"])
        self.assertEqual(got["sheets"], 73)
        self.assertAlmostEqual(got["mpx"], 14.479722, places=6)
        self.assertEqual(got["fill_pct"], 86.31)
        self.assertEqual(got["used"], [4094, 4087])
        self.assertEqual(got["used"], golden["expect"]["used"])

    def test_known_overflow_formation(self):
        golden = self.golden[GOLDEN_OVERFLOW]
        got = G.pack_sheets(golden["sheets"])
        self.assertFalse(got["fits"])
        self.assertEqual(got["sheets"], 92)
        self.assertAlmostEqual(got["mpx"], 16.191179, places=6)
        self.assertEqual(got["fill_pct"], 96.51)
        self.assertIn("unicorn_lancer_rose", got["overflow_at"])
        self.assertEqual(got["overflow_at"], golden["expect"]["overflow_at"])

    def test_overflow_formation_is_the_fits_one_plus_seven_unisons(self):
        """两组是包含关系 —— 差的正是本批 7 人的技能特效,不是两套无关数据。"""
        base = set(self.golden[GOLDEN_FITS]["sheets"])
        more = set(self.golden[GOLDEN_OVERFLOW]["sheets"])
        self.assertTrue(base.issubset(more))
        self.assertEqual(len(more - base), 19)

    def test_self_check_matches_frozen_expectations(self):
        report = G.self_check(self.roster)
        self.assertEqual(report["status"], "OK")
        self.assertEqual([c["match"] for c in report["checks"]], [True, True])

    # ---- 负向对照:断言必须会变红 ---------------------------------------
    def test_self_check_goes_red_when_a_sheet_grows(self):
        broken = json.loads(json.dumps(self.roster))
        sheets = broken["golden_formations"][0]["sheets"]
        victim = next(iter(sheets))
        sheets[victim] = [4096, 4096]
        report = G.self_check(broken)
        self.assertEqual(report["status"], "GOLDEN_MISMATCH")
        self.assertEqual(report["exit_code"], 1)

    def test_fits_formation_goes_red_if_margin_is_dropped(self):
        """margin=2 是判据的一部分:去掉它占用会明显变小,黄金值就不成立了。"""
        sheets = self.golden[GOLDEN_FITS]["sheets"]
        without_margin = sum(w * h for w, h in sheets.values())
        self.assertLess(without_margin / 1e6, 14.479722)


class ThresholdCase(unittest.TestCase):
    """阈值与归因:用可控的小房间,不碰 store。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def write_roster(self, roster) -> Path:
        path = self.dir / "roster.json"
        path.write_text(json.dumps(roster, ensure_ascii=False), encoding="utf-8")
        return path

    def evaluate(self, roster, subject_layer0, **kwargs):
        dims = G.DimSource(roster, "roster", overrides=subject_layer0)
        subject = {"path": None, "code": "subject", "character_id": None,
                   "package_id": None, "package_version": None, "roots": None,
                   "png_files_scanned": 0, "excluded": [],
                   "layer0": subject_layer0, "layer1": {}, "pixelart": {}}
        kwargs.setdefault("scenarios", ["solo"])
        kwargs.setdefault("heaviest", 3)
        return G.evaluate(subject, roster, dims, **kwargs)

    def test_small_room_passes(self):
        result = self.evaluate(tiny_roster([100, 100]), {"battle/effect/x/x": [64, 64]})
        self.assertEqual(result["status"], "OK")
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["attribution"], "none")

    def test_absurdly_low_threshold_always_reds(self):
        """负向对照:同一份输入,把阈值压到极低必须报红。"""
        sheets = {"battle/effect/x/x": [64, 64]}
        roster = tiny_roster([100, 100])
        self.assertEqual(self.evaluate(roster, sheets)["status"], "OK")
        low = self.evaluate(roster, sheets, threshold=0.1)
        self.assertEqual(low["status"], "OVER_THRESHOLD")
        self.assertEqual(low["exit_code"], 1)

    def test_attribution_blames_the_subject_when_baseline_is_clean(self):
        roster = tiny_roster([100, 100], boss_sheet=[2000, 2000])
        result = self.evaluate(roster, {"battle/effect/big/big": [3000, 2000]},
                               threshold=40.0)
        self.assertNotEqual(result["status"], "OK")
        self.assertEqual(result["attribution"], "caused-by-subject")
        self.assertFalse(result["scenarios"][0]["baseline_over"])

    def test_attribution_says_pre_existing_when_room_is_already_over(self):
        roster = tiny_roster([2000, 2000], boss_sheet=[3000, 3000])
        result = self.evaluate(roster, {"battle/effect/tiny/tiny": [8, 8]},
                               threshold=40.0)
        self.assertNotEqual(result["status"], "OK")
        self.assertEqual(result["attribution"], "pre-existing")
        self.assertTrue(result["scenarios"][0]["baseline_over"])

    def test_marginal_is_the_difference_between_the_two_rooms(self):
        roster = tiny_roster([100, 100])
        result = self.evaluate(roster, {"battle/effect/x/x": [98, 98]})
        row = result["scenarios"][0]
        self.assertEqual(row["marginal_px"], 100 * 100)
        self.assertEqual(row["px"] - row["baseline"]["px"], row["marginal_px"])

    def test_unison_role_drops_the_pixel_sheet(self):
        subject = {"path": None, "code": "subject", "layer0": {
            "character/subject/pixelart/sprite_sheet": [100, 100],
            "battle/effect/skill_unique/subject/fx/fx": [50, 50]},
            "pixelart": {"character/subject/pixelart/sprite_sheet": [100, 100]}}
        self.assertEqual(list(G.subject_layer0_for_role(subject, "unison")),
                         ["battle/effect/skill_unique/subject/fx/fx"])
        self.assertEqual(len(G.subject_layer0_for_role(subject, "main-leader")), 2)

    def test_room_excludes_the_subject_itself(self):
        roster = tiny_roster([100, 100])
        dims = G.DimSource(roster, "roster")
        _, codes = G.build_room(roster, dims, "solo", 3, {}, "main",
                                exclude_codes={"cust_a"})
        self.assertNotIn("cust_a", codes)
        self.assertEqual(codes, ["cust_b", "cust_c"])

    def test_leader_slots_are_every_third_seat(self):
        roster = tiny_roster([100, 100])
        dims = G.DimSource(roster, "roster")
        sheets, _ = G.build_room(roster, dims, "solo", 3, {}, "main")
        pf = [s for s in sheets if "/powerflip/" in s]
        self.assertEqual(pf, ["battle/effect/powerflip/cust_a_pf/pf/pf"])


class PackReadingCase(unittest.TestCase):
    """从角色包目录读纹理清单。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pack = Path(self.tmp.name) / "s7-demo"
        roots = self.pack / "package" / "roots"
        (self.pack / "package" / "manifest.json").parent.mkdir(parents=True, exist_ok=True)
        (self.pack / "package" / "manifest.json").write_text(json.dumps(
            {"code_name": "demo", "character_id": 199999, "package_id": "demo-pkg",
             "package_version": "1.0.0"}), encoding="utf-8")
        files = {
            "common/character/demo/pixelart/sprite_sheet.png": (240, 482),
            # store 态的 PNG 魔数是小写的,读图必须认得
            "common/battle/effect/skill_unique/demo/fx/fx.png": (245, 964),
            "common/character/demo/pixelart/special_sprite_sheet.png": (512, 512),
            "common/master/whatever.png": (10, 10),
            "medium/character/demo/ui/square_0.png": (212, 212),
            "medium/character/demo/ui/battle_member_status_0.png": (58, 58),
            "medium/character/demo/ui/full_shot_1440_1920_0.png": (1440, 1920),
        }
        for rel, (width, height) in files.items():
            path = roots / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            magic = b"\x89png\r\n\x1a\n" if "/battle/effect/" in rel else b"\x89PNG\r\n\x1a\n"
            path.write_bytes(png_stub(width, height, magic))

    def test_layer0_and_layer1_split(self):
        info = G.read_pack(self.pack)
        self.assertEqual(info["code"], "demo")
        self.assertEqual(info["character_id"], 199999)
        self.assertEqual(sorted(info["layer0"]),
                         ["battle/effect/skill_unique/demo/fx/fx",
                          "character/demo/pixelart/sprite_sheet"])
        self.assertEqual(sorted(info["layer1"]),
                         ["character/demo/ui/battle_member_status_0",
                          "character/demo/ui/square_0"])
        self.assertEqual(info["layer0"]["battle/effect/skill_unique/demo/fx/fx"],
                         [245, 964])

    def test_excluded_files_say_why(self):
        info = G.read_pack(self.pack)
        reasons = {row["sheet"]: row["reason"] for row in info["excluded"]}
        self.assertIn("character/demo/pixelart/special_sprite_sheet", reasons)
        self.assertIn("special_sprite_sheet",
                      reasons["character/demo/pixelart/special_sprite_sheet"])
        self.assertIn("character/demo/ui/full_shot_1440_1920_0", reasons)
        self.assertIn("master/whatever", reasons)

    def test_accepts_workspace_package_or_roots_dir(self):
        for candidate in (self.pack, self.pack / "package",
                          self.pack / "package" / "roots"):
            self.assertEqual(G.read_pack(candidate)["layer0"].keys().__len__(), 2)

    def test_pack_dims_win_over_the_roster_snapshot(self):
        """正要发布的是包里那一份 —— 尺寸必须以包为准,不能读 store 的旧版。"""
        info = G.read_pack(self.pack)
        roster = tiny_roster([100, 100])
        roster["characters"]["cust_a"]["skill_sheets"][
            "battle/effect/skill_unique/demo/fx/fx"] = [1, 1]
        dims = G.DimSource(roster, "roster", overrides=info["layer0"])
        self.assertEqual(dims.get("battle/effect/skill_unique/demo/fx/fx"), [245, 964])

    def test_not_a_pack_dir_raises(self):
        with self.assertRaises(G.RosterError):
            G.read_pack(Path(self.tmp.name))

    def test_roster_closure_adds_sheets_the_pack_does_not_ship(self):
        """官方公共特效不在包里,进战斗照样占 layer0 —— 不补就是系统性少算。"""
        info = G.read_pack(self.pack)
        roster = tiny_roster([100, 100])
        roster["characters"]["demo"] = {
            "id": "199999", "group": "custom",
            "pixelart": {"character/demo/pixelart/sprite_sheet": [1, 1]},
            "skill_sheets": {
                "battle/effect/skill_general/decoration/dummy_ball/w/w": [82, 82]},
            "pf_sheets": {}, "ui_layer1": {},
        }
        dims = G.DimSource(roster, "roster", overrides=dict(info["layer0"]))
        G.merge_roster_closure(info, roster, dims)
        self.assertEqual(info["roster_only_sheets"],
                         ["battle/effect/skill_general/decoration/dummy_ball/w/w"])
        # 包里那张的尺寸不许被名册快照顶掉
        self.assertEqual(info["layer0"]["character/demo/pixelart/sprite_sheet"], [240, 482])

    def test_roster_closure_is_a_noop_for_a_brand_new_character(self):
        info = G.read_pack(self.pack)
        before = dict(info["layer0"])
        roster = tiny_roster([100, 100])          # 名册里没有 demo
        dims = G.DimSource(roster, "roster", overrides=dict(info["layer0"]))
        G.merge_roster_closure(info, roster, dims)
        self.assertEqual(info["roster_only_sheets"], [])
        self.assertEqual(info["layer0"], before)


class CliCase(unittest.TestCase):
    """CLI 契约:最后一行稳定 JSON + 退出码。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def sheet_set_file(self, name: str) -> Path:
        roster = G.load_roster()
        golden = {g["name"]: g for g in roster["golden_formations"]}[name]
        path = self.dir / (name + ".json")
        path.write_text(json.dumps(golden["sheets"]), encoding="utf-8")
        return path

    def test_self_check_cli_exit_zero(self):
        code, last, _ = run_cli(["--self-check", "--quiet"])
        self.assertEqual(code, 0)
        self.assertEqual(last["status"], "OK")

    def test_known_fits_via_cli(self):
        path = self.sheet_set_file(GOLDEN_FITS)
        code, last, _ = run_cli(["--sheet-set", str(path), "--quiet"])
        self.assertEqual(code, 0)
        self.assertEqual(last["status"], "OK")
        self.assertTrue(last["sheet_set"]["fits"])
        self.assertEqual(last["sheet_set"]["fill_pct"], 86.31)

    def test_known_overflow_via_cli(self):
        path = self.sheet_set_file(GOLDEN_OVERFLOW)
        code, last, _ = run_cli(["--sheet-set", str(path), "--quiet"])
        self.assertEqual(code, 1)
        self.assertEqual(last["status"], "OVERFLOW")
        self.assertIn("unicorn_lancer_rose", last["sheet_set"]["overflow_at"])

    def test_threshold_negative_control_via_cli(self):
        """同一份 FITS 输入:阈值 86.31 以下必须红,以上必须绿。"""
        path = self.sheet_set_file(GOLDEN_FITS)
        self.assertEqual(run_cli(["--sheet-set", str(path), "--quiet",
                                  "--threshold", "1"])[0], 1)
        self.assertEqual(run_cli(["--sheet-set", str(path), "--quiet",
                                  "--threshold", "99"])[0], 0)

    def test_last_line_json_is_stable_and_sorted(self):
        path = self.sheet_set_file(GOLDEN_FITS)
        first = run_cli(["--sheet-set", str(path), "--quiet"])[2].strip().splitlines()[-1]
        second = run_cli(["--sheet-set", str(path), "--quiet"])[2].strip().splitlines()[-1]
        self.assertEqual(first, second)
        keys = list(json.loads(first))
        self.assertEqual(keys, sorted(keys))

    def test_quiet_prints_only_the_json_line(self):
        path = self.sheet_set_file(GOLDEN_FITS)
        text = run_cli(["--sheet-set", str(path), "--quiet"])[2]
        self.assertEqual(len(text.strip().splitlines()), 1)

    def test_unknown_character_exits_two(self):
        code, last, _ = run_cli(["--codes", "no_such_character", "--dims", "roster",
                                 "--quiet"])
        self.assertEqual(code, 2)
        self.assertEqual(last["status"], "ERROR")

    def test_json_out_carries_the_full_detail(self):
        out = self.dir / "full.json"
        path = self.sheet_set_file(GOLDEN_FITS)
        run_cli(["--sheet-set", str(path), "--quiet", "--json", str(out)])
        payload = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema"], G.SCHEMA)


class RosterCase(unittest.TestCase):
    """名册本身的完整性 —— 场景/boss/角色互相引用不许断。"""

    @classmethod
    def setUpClass(cls):
        cls.roster = G.load_roster()

    def test_schema_and_atlas_constants(self):
        self.assertEqual(self.roster["atlas"],
                         {"width": 4096, "height": 4096, "margin": 2})
        self.assertEqual(G.CAPACITY, 4096 * 4096)

    def test_every_scenario_boss_exists(self):
        for name, spec in self.roster["scenarios"].items():
            for key in spec["bosses"]:
                self.assertIn(key, self.roster["bosses"], "%s -> %s" % (name, key))

    def test_no_unresolved_sheets(self):
        self.assertEqual(self.roster["unresolved_sheets"], [])

    def test_every_roster_sheet_is_layer0_or_known_layer1(self):
        for code, rec in self.roster["characters"].items():
            for group in ("pixelart", "skill_sheets", "pf_sheets"):
                for sheet in rec[group]:
                    self.assertTrue(G.is_layer0_sheet(sheet), "%s %s" % (code, sheet))
            for sheet in rec["ui_layer1"]:
                self.assertTrue(G.battle_ui_image(sheet), "%s %s" % (code, sheet))

    def test_bad_schema_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "r.json"
            path.write_text(json.dumps({"schema": "nope"}), encoding="utf-8")
            with self.assertRaises(G.RosterError):
                G.load_roster(path)


if __name__ == "__main__":
    unittest.main()
