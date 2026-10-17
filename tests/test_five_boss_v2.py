# -*- coding: utf-8 -*-
"""wf_five_boss_v2：纯函数单测 + live store 冒烟（store 不在时跳过）。"""
from __future__ import annotations

import sys
import unittest
import zlib
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import wf_dsl  # noqa: E402
import wf_five_boss_v2 as F  # noqa: E402
import wf_quest_lib as q  # noqa: E402


PARAMS = F.load_spec()["affix_params"]


class PureFunctionTests(unittest.TestCase):
    def test_num_never_uses_exponent(self):
        self.assertEqual(F.num(1319617.52), "1319617.52")
        self.assertEqual(F.num(2500.0), "2500")
        self.assertEqual(F.num(-0.3), "-0.3")
        self.assertEqual(F.num(1e9), "1000000000")
        self.assertNotIn("e", F.num(1.23456789e12))

    def test_affix_trees_whitelisted_and_roundtrip(self):
        for name, tree in F.affix_library(PARAMS).items():
            with self.subTest(affix=name):
                self.assertEqual(F.dsl_constructor_problems(tree), [])
                raw = F.encode_dsl(tree)
                self.assertEqual(wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"], tree)

    def test_whitelist_catches_typo(self):
        tree = F._root([F._cmd(["CreateConditon", 0, []])])
        self.assertEqual(F.dsl_constructor_problems(tree), ["CreateConditon"])

    def test_purge_uses_forced_dispel_and_gauge_clear(self):
        cmds = list(wf_dsl.iter_dsl_commands(F.affix_library(PARAMS)["purge_r1"]))
        deletes = [c for c in cmds if c[0] == "DeleteCondition"]
        self.assertTrue(deletes and all(c[2] == ["DCAll", 2] and c[4] == 2 for c in deletes))
        self.assertTrue(any(c[0] == "SubtractSkillPoint" and c[2] == [{"min": 1, "max": 1}] for c in cmds))

    def test_replace_in_chunk_keeps_sibling_bytes(self):
        tree = {"a": "1,2,3", "b": {"x": "4,5", "y": "6"}}
        raw = q.build_node(tree)
        new = F.replace_in_chunk(raw, ["b", "y"], "7")
        self.assertEqual(q.parse_node(new), {"a": "1,2,3", "b": {"x": "4,5", "y": "7"}})
        keys, chunks = q._try_parse_map(new)
        keys0, chunks0 = q._try_parse_map(raw)
        self.assertEqual(chunks[0], chunks0[0])          # 兄弟键 a 原字节
        added = F.replace_in_chunk(raw, ["c", "z"], "8")
        self.assertEqual(q.parse_node(added)["c"], {"z": "8"})
        removed = F.replace_in_chunk(raw, ["a"], None)
        self.assertNotIn("a", q.parse_node(removed))

    def test_write_rows_quotes_commas_without_trailing_newline(self):
        self.assertEqual(F.write_rows([["a,b", "c"]]), '"a,b",c')

    def test_watch_copies_self_and_partner(self):
        gew = {"1": {"m": {"m": {"2": {"f": {"f": "rows1"}}}}},
               "2": {"f": {"f": {"1": {"m": {"m": "rows2"}, "other": {"other": "rows3"}}}}}}
        got = dict((tuple(p), n) for p, n in F.watch_copies(gew, "m", "c"))
        self.assertEqual(got[("1", "c")], {"c": {"2": {"f": {"f": "rows1"}}}})
        self.assertEqual(got[("2", "f", "f", "1", "c")], {"c": "rows2"})
        self.assertEqual(len(got), 2)

    def test_extrude_replicates_edge_pixels(self):
        from PIL import Image
        im = Image.new("RGB", (3, 2))
        im.putdata([(1, 0, 0), (2, 0, 0), (3, 0, 0), (4, 0, 0), (5, 0, 0), (6, 0, 0)])
        out = F.extrude(im)
        self.assertEqual(out.size, (5, 4))
        self.assertEqual(out.crop((1, 1, 4, 3)).tobytes(), im.tobytes())
        self.assertEqual(out.getpixel((0, 0)), (1, 0, 0))
        self.assertEqual(out.getpixel((4, 3)), (6, 0, 0))
        self.assertEqual(out.getpixel((2, 0)), (2, 0, 0))
        self.assertEqual(out.getpixel((0, 2)), (4, 0, 0))

    def test_recolor_rules_first_match_and_hue_wrap(self):
        rules = [{"h": [340, 20], "s_min": 0.3, "to_h": 120},        # 跨 0° 的红 → 绿
                 {"h": [0, 360], "to_h": 240}]
        r, g, b = F.recolor_rgb((200, 20, 30), rules)
        self.assertTrue(g > r and g > b)
        self.assertEqual(F.recolor_rgb((0, 0, 0), rules[:1]), (0, 0, 0))   # 不命中保持原色
        r2, g2, b2 = F.recolor_rgb((30, 200, 30), rules)                   # 落到第二条
        self.assertTrue(b2 > r2 and b2 > g2)

    def test_rename_prefix_only_touches_matching_strings(self):
        tree = {"i": [{"p": "a/.gen/x/k"}, {"p": "b/other"}], "n": 3}
        self.assertEqual(F.rename_prefix(tree, "a/.gen/x/", "m/.gen/y/"),
                         {"i": [{"p": "m/.gen/y/k"}, {"p": "b/other"}], "n": 3})
        self.assertEqual(F.gen_prefix("battle/boss/mod/v/n/n"), "battle/boss/mod/v/n/.gen/n/")

    def test_pack_frames_trims_and_keeps_canvas(self):
        from PIL import Image
        a = Image.new("RGBA", (10, 8), (0, 0, 0, 0))
        a.paste(Image.new("RGBA", (3, 2), (255, 0, 0, 255)), (4, 5))
        empty = Image.new("RGBA", (6, 6), (0, 0, 0, 0))
        sheet, entries = F.pack_frames([("x/.gen/n/a", a), ("x/.gen/n/b", empty)])
        ea, eb = entries
        self.assertEqual((ea["w"], ea["h"], ea["fx"], ea["fy"], ea["fw"], ea["fh"]), (3, 2, -4, -5, 10, 8))
        self.assertEqual(sheet.crop((ea["x"], ea["y"], ea["x"] + 3, ea["y"] + 2)).tobytes(), Image.new("RGBA", (3, 2), (255, 0, 0, 255)).tobytes())
        self.assertEqual((eb["w"], eb["h"], eb["fw"], eb["fh"]), (1, 1, 6, 6))
        self.assertEqual(list(ea), ["n", "w", "h", "x", "y", "fx", "fy", "fw", "fh"])

    def test_signature_shapes_stay_whitelisted(self):
        tree = F.dsl_signature(1500, 999, "k", silence=360, drain=0.3, purge=99, on_entry=True)
        self.assertEqual(F.dsl_constructor_problems(tree), [])
        cmds = list(wf_dsl.iter_dsl_commands(tree))
        self.assertTrue(any(c[0] == "DeleteCondition" and c[2] == ["DCAll", 2] for c in cmds))
        self.assertTrue(any(c[0] == "CreateCondition" and c[2][0][0] == "ACSilence" and c[-1] is True for c in cmds))
        block = tree[-1][1]
        self.assertEqual(block[0][0], "Command")                       # 登场先执行一次
        self.assertEqual(block[1][1][0], "Repeat")

    def test_routine_trial_patch(self):
        def row(name, nxt, dur="180"):
            r = ["(None)"] * 53
            r[0], r[1], r[2], r[3] = name, "1", "shot_charge", name
            r[22], r[23], r[24], r[25], r[26] = "(None)", "", "", "", ""
            r[29], r[30], r[31], r[32] = "0", "", nxt, ""
            r[46], r[47] = "2", dur
            return F.write_rows([r])
        routine = {"1": {"charge": row("charge", "fire"), "fire": row("fire", "after"), "after": row("after", "charge")}}
        gb = {"mother": {"100": F.write_rows([["4"] + [""] * 41 + ["src_routine"] + [""] * 119])}}
        files = {F.T_GBS: q.build_node({"src_routine": routine}), F.T_GB: q.build_node(gb)}
        live = F.Live(lambda lg: files[lg] if lg in files else (_ for _ in ()).throw(FileNotFoundError(lg)))
        spec = {"bosses": {"k": {"mother": "mother", "routine": {"out": "mod_fb2_r", "trials": {"charge": {"kind": "skill", "count": 12, "frames": 600}}}}},
                "_variants": [F.Variant(1, "r1", "n", [[F.BossSlot("k", 1)]], 0)]}
        plan = F.Plan()
        F.plan_routines(live, spec, plan)
        (path, node), = plan.edits[F.T_GBS]
        self.assertEqual(path, ["mod_fb2_r"])
        r = F.one_row(node["1"]["charge"])
        self.assertEqual((r[22], r[23], r[24], r[25]), ("1", "12", "true", "true"))
        self.assertEqual((r[29], r[30], r[31], r[32]), ("12", "0", "after", "fire"))   # 达成跳过大招，未达成照放
        self.assertEqual((r[46], r[47]), ("2", "600"))
        self.assertEqual(node["1"]["fire"], routine["1"]["fire"])                     # 其余状态原样
        self.assertEqual(plan.routine_sources, {"mod_fb2_r": "src_routine"})

    def test_fired_slots_and_spawned_funnels(self):
        timeline = {"sequences": [], "sounds": [], "rectangles": [], "matrices": [], "circles": [],
                    "points": [{"path": "enemy_action03", "frames": [{"begin": 1, "data": []}, {"begin": 9, "data": [{"x": 0, "y": 0}]}]},
                               {"path": "enemy_action07", "frames": [{"begin": 1, "data": []}]},
                               {"path": "center", "frames": [{"begin": 1, "data": [{"x": 0, "y": 0}]}]}]}
        prog = "battle/action/enemy/action/x/y$z"
        dsl = F._root([F._cmd(["SpawnFunnel", ["Funnel", "dog"], 3, ["FunnelGroup", 1], []])])
        files = {"m.timeline.amf3.deflate": F.encode_amf(timeline), wf_dsl.dsl_logical(prog): F.encode_dsl(dsl)}
        live = F.Live(lambda lg: files[lg] if lg in files else (_ for _ in ()).throw(FileNotFoundError(lg)))
        self.assertEqual(F.fired_action_slots(live, "m"), {3})          # 只有带坐标数据的帧算触发
        self.assertEqual(F.fired_action_slots(live, "(None)"), set(range(1, 51)))
        self.assertEqual(F.spawned_funnels(live, [prog], {}), {"dog"})

    def test_endless_loop_needs_remover_in_kit(self):
        loop = F._root([F._repeat(120, 9999, "floor", [F._cmd(["DoNothing"])])])
        remover = F._root([F._cmd(["RemoveEventFromOwner", "floor"])])
        files = {wf_dsl.dsl_logical("a/x$loop"): F.encode_dsl(loop), wf_dsl.dsl_logical("a/x$rm"): F.encode_dsl(remover)}
        live = F.Live(lambda lg: files[lg] if lg in files else (_ for _ in ()).throw(FileNotFoundError(lg)))
        row = [""] * 162
        row[F.GB_ACTION_FIRST] = "a/x$loop"
        self.assertEqual(F.orphan_endless_loops(live, row, {}), ["floor"])       # 借来的循环没人撤
        row[F.GB_ACTION_FIRST + 5] = "a/x$rm"
        self.assertEqual(F.orphan_endless_loops(live, row, {}), [])               # 招式组里有撤除者就放行

    def test_resolve_action_passthrough_and_variant_path(self):
        self.assertEqual(F.resolve_action(None, "a/b$c"), "a/b$c")
        self.assertEqual(F.element_variant_anim("battle/effect/g/shot", "black"), "battle/effect/g/shot/shot_black/shot_black")

    def test_region_name_follows_flatomo_gen_layout(self):
        self.assertEqual(F.gen_region_name("battle/field/mod/x/background/background"),
                         "battle/field/mod/x/background/.gen/background/a")

    def test_atlas_slot_keeps_gap_and_grows_downward(self):
        from PIL import Image
        sheet = Image.new("RGBA", (20, 10), (0, 0, 0, 0))
        a = {"n": "a", "w": 8, "h": 8, "x": 1, "y": 1}
        x, y, same = F.find_atlas_slot([a], sheet, (8, 8))
        self.assertEqual((x, y, same.size), (1 + 8 + F.ATLAS_GAP, 1, (20, 10)))
        b = {"n": "b", "w": 8, "h": 8, "x": x, "y": y}
        x2, y2, grown = F.find_atlas_slot([a, b], sheet, (8, 8))
        self.assertEqual((x2, y2), (1, 9 + F.ATLAS_GAP))
        self.assertEqual(grown.size, (20, y2 + 8 + 1))
        self.assertEqual(grown.crop((0, 0, 20, 10)).tobytes(), sheet.tobytes())   # 既有像素不动
        # 画布里有非透明残留的位置不能用
        dirty = sheet.copy()
        dirty.putpixel((12, 3), (255, 0, 0, 255))
        x3, y3, _ = F.find_atlas_slot([a], dirty, (8, 8))
        self.assertNotEqual((x3, y3), (11, 1))

    def test_item_icon_row_waits_for_live_atlas(self):
        import io as _io
        import wf_assets
        from PIL import Image
        buf = _io.BytesIO()
        Image.new("RGBA", (16, 16), (0, 0, 0, 0)).save(buf, format="PNG")
        sheet = wf_assets.png_encode(buf.getvalue())
        spec = {"art": {"item_icons": {"10000143": {"thumbnail": "t/new", "small": "i/new"}}}}
        item_table = q.build_node({"10000143": "x,10000143,n,t/old,i/old,d"})

        def live_with(entries, thumb_exists):
            files = {F.ITEM_ATLAS_FILES[0]: sheet, F.ITEM_ATLAS_FILES[1]: F.encode_amf(entries), F.T_ITEM: item_table}
            if thumb_exists:
                files["t/new.png"] = sheet

            def loader(lg):
                if lg not in files:
                    raise FileNotFoundError(lg)
                return files[lg]
            return F.Live(loader)

        region = {"n": "i/new", "w": 4, "h": 4, "x": 1, "y": 1}
        for entries, thumb, expect_edit in (([], True, False), ([region], False, False), ([region], True, True)):
            with self.subTest(entries=len(entries), thumb=thumb):
                plan = F.Plan()
                F.plan_item_icons(live_with(entries, thumb), spec, plan)
                edits = plan.edits.get(F.T_ITEM, [])
                self.assertEqual(bool(edits), expect_edit)
                self.assertNotIn(F.ITEM_ATLAS_FILES[0], plan.files)
                if expect_edit:
                    row = F.one_row(edits[0][1])
                    self.assertEqual((row[F.ITEM_THUMB_COL], row[F.ITEM_SMALL_COL]), ("t/new", "i/new"))
                else:
                    self.assertTrue(plan.warnings)

    def test_shop_icon_waits_for_live_png(self):
        spec = {"art": {"shop_icons": {"990099002": {"col": 2, "value": "t/new"}}}}
        shop = q.build_node({"990099002": "99,(None),t/old,x", "990099003": "99,(None),t/old,y"})
        for exists in (False, True):
            files = {F.T_SHOP: shop}
            if exists:
                files["t/new.png"] = b"png"
            plan = F.Plan()
            F.plan_shop_icons(F.Live(lambda lg, files=files: files[lg] if lg in files else
                                     (_ for _ in ()).throw(FileNotFoundError(lg))), spec, plan)
            edits = plan.edits.get(F.T_SHOP, [])
            if exists:
                self.assertEqual([p for p, _ in edits], [["990099002"]])
                self.assertEqual(F.one_row(edits[0][1])[2], "t/new")
            else:
                self.assertEqual(edits, [])
                self.assertTrue(plan.warnings)


STORE_OK = True
try:
    q.store_path(F.T_BBQ).stat()
except Exception:  # noqa: BLE001
    STORE_OK = False


@unittest.skipUnless(STORE_OK, "live store not available")
class LiveBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = F.load_spec()
        cls.live = F.Live()
        cls.plan = F.build(cls.spec, cls.live)

    def edits(self, table):
        return {tuple(p): n for p, n in self.plan.edits.get(table, [])}

    def test_no_gate_problems(self):
        self.assertEqual(self.plan.problems, [])

    def test_budget_every_variant_within_fail_line(self):
        for qid, b in self.plan.report["budget"].items():
            self.assertLessEqual(b["mpx"], self.spec["budget"]["fail_mpx"], qid)

    def test_routes_cover_all_pairs_and_fallback_is_last(self):
        r0 = [v.quest for v in self.spec["_variants"] if v.round == "r0"]
        r1 = [v.quest for v in self.spec["_variants"] if v.round == "r1"]
        maps = self.edits(F.T_BBM)
        pairs = set()
        for (mid,), text in maps.items():
            row = F.one_row(text)
            if mid == str(self.spec["fallback_map_id"]):
                self.assertEqual(row[1], "(None)")
                continue
            self.assertEqual((row[1], row[2]), ("0", str(F.ALWAYS_TRUE_THRESHOLD)))
            pairs.add((int(row[11]), int(row[12])))
        self.assertEqual(pairs, {(a, b) for a in r0 for b in r1})
        group = F.one_row(self.edits(F.T_BBG)[(str(self.spec["entry_quest"]),)])
        ids = group[1].split(",")
        self.assertEqual(ids[-1], str(self.spec["fallback_map_id"]))
        self.assertEqual(len(ids), len(pairs) + 1)

    def test_quest_rows(self):
        quests = self.edits(F.T_BBQ)
        for v in self.spec["_variants"]:
            row = F.one_row(quests[("1", "99", str(v.quest - 1099000))])
            self.assertEqual(row[0], str(v.quest))
            self.assertEqual((row[F.Q_HP[2]], row[F.Q_TP[2]]), ("1", "1"))
            self.assertEqual(row[F.Q_TIME], str(self.spec["time_limit_frames"]))
            self.assertEqual((row[F.Q_IS_BOTH], row[F.Q_HIDDEN]), ("false", "true"))

    def test_clone_hp_and_tp_match_targets(self):
        bl = self.edits(F.T_BL)
        for code, info in self.plan.clones.items():
            row = F.one_row(bl[(code,)])
            unit = F.GENERAL_HP_K_LV80 * float(row[F.BL_HP_MUL]) * F.curve_hp_corr(row[F.BL_HP_CORR])
            self.assertAlmostEqual(float(row[F.BL_HP_HITS]) * unit / 1e8, info["hp_e8"], delta=info["hp_e8"] * 1e-4)
            self.assertEqual(row[F.BL_TP_CURVE], F.TP_CURVE)
            self.assertAlmostEqual(float(row[F.BL_TP_BASE]) * F.TP_NORMAL_LV80, info["tp"], delta=1)

    def test_carriers_and_entry_purge(self):
        purge = F.affix_program("purge_r1")
        gb = self.edits(F.T_GB)
        for code, info in self.plan.clones.items():
            tiers = gb[(code,)]
            row = F.one_row(tiers[F.tier_for_level(tiers)])
            pre = F.split_programs(row[F.GB_PRE])
            self.assertNotEqual(row[F.GB_PRE], "(None)", code)   # 官方写空串；(None) 会被当文件名加载
            self.assertFalse(any("/mod/five_boss/" in p for p in pre), code)   # v1 诅咒已剥离
            v = next(x for x in self.spec["_variants"] if x.quest == info["quest"])
            carrier = v.group_kind == 1 or info["slot"] == 0
            sigs = {F.affix_program(s) for s in self.spec["bosses"][info["alias"]].get("signature", [])}
            self.assertTrue(sigs <= set(pre), code)                         # 签名招式每只都挂
            has_affix = any(p.startswith(F.OWN_DSL_DIR) and p not in sigs for p in pre)
            self.assertEqual(has_affix, carrier and bool(v.affixes or v.entry_affixes), code)
            if purge in pre:
                self.assertEqual((info["wave"], row[F.GB_PRE_RERUN]), (0, "false"), code)

    def test_terrains(self):
        for rnd, t in self.spec["terrains"].items():
            tree, _ = F.build_terrain(self.live, t)
            for layer in F.object_layers(tree):
                self.assertFalse(any("ACCUMULATION" in str(o.get("type")) for o in layer["objects"]) and rnd == "r1")
                b = next(o for o in layer["objects"] if o.get("type") == "BOUNDS")
                for o in layer["objects"]:
                    if o.get("type") in ("FUNNEL_SPAWN6", "FUNNEL_SPAWN8"):
                        self.assertTrue(b["x"] <= o["x"] <= b["x"] + b["width"], (rnd, o))
                        self.assertTrue(b["y"] <= o["y"] <= b["y"] + b["height"], (rnd, o))

    def test_envy_revert_restores_official(self):
        node = self.edits(F.T_GBS).get(("devil_commander_evil_envy_80",))
        if self.plan.report.get("envy_revert") == "already official":
            self.skipTest("already reverted")
        self.assertIsNotNone(node)
        official = q.parse_node(F.official_table_loader(F.T_GBS)())["devil_commander_evil_envy_80"]
        self.assertEqual(node, official)

    def test_own_prefixes(self):
        for table in (F.T_ZONE, F.T_FD, F.T_GB, F.T_BL, F.T_FIELD):
            for (key, *_rest) in self.edits(table):
                self.assertTrue(key.startswith(F.OWN_CODE_PREFIX), (table, key))

    def test_recolored_bosses_keep_layout_and_point_clones_at_new_sheet(self):
        gb = self.edits(F.T_GB)
        recolored = {a: b["recolor"] for a, b in self.spec["bosses"].items() if "recolor" in b}
        used = {info["alias"] for info in self.plan.clones.values()}
        for alias, rc in recolored.items():
            if alias not in used:
                continue
            old = F.open_png(self.live.file(rc["from"] + ".png"))
            new = F.open_png(self.plan.files[rc["out"] + ".png"])
            self.assertEqual((new.mode, new.size), (old.mode, old.size), alias)
            self.assertEqual(new.tobytes(), old.tobytes(), alias)            # 调色板索引一个不动
            self.assertNotEqual(new.getpalette(), old.getpalette(), alias)
            names = [e["n"] for e in F.decode_amf(self.plan.files[rc["out"] + ".atlas.amf3.deflate"])]
            self.assertTrue(names and all(n.startswith(F.gen_prefix(rc["out"])) for n in names), alias)
            parts = F.decode_amf(self.plan.files[rc["out"] + ".parts.amf3.deflate"])
            self.assertEqual({i["p"] for i in parts["i"]} - set(names), set(), alias)
            for code, info in self.plan.clones.items():
                if info["alias"] == alias:
                    tiers = gb[(code,)]
                    self.assertEqual(F.one_row(tiers[F.tier_for_level(tiers)])[2], rc["out"], code)

    def test_fields_and_ui_art(self):
        art = self.spec["art"]
        fields = self.edits(F.T_FIELD)
        self.assertEqual({k for (k,) in fields}, set(art["fields"]))
        for fid, fdef in art["fields"].items():
            row = F.one_row(fields[(fid,)])
            base = fdef["background"]["out"]
            self.assertEqual(row[F.FIELD_BG_COL], base)
            self.assertTrue(base.startswith(F.OWN_FIELD_DIR))
            region = F.decode_amf(self.plan.files[base + ".atlas.amf3.deflate"])[0]
            sheet = F.open_png(self.plan.files[base + ".png"])
            self.assertEqual(sheet.size, (region["w"] + 2, region["h"] + 2))
            self.assertEqual(F.decode_amf(self.plan.files[base + ".parts.amf3.deflate"])["i"][0]["p"], region["n"])
        round_fields = {r["field"] for r in self.spec["rounds"].values()}
        for (_fd,), text in self.edits(F.T_FD).items():
            self.assertIn(F.one_row(text)[0], round_fields)
        for item in art["files"]:
            self.assertIn(item["logical"], self.plan.files)
        # 道具行只能指向 live 图集里已有的子纹理（C8004 顺序）
        names = {e["n"] for e in F.decode_amf(self.live.file(F.ITEM_ATLAS_FILES[1]))}
        for (_iid,), text in self.edits(F.T_ITEM).items():
            self.assertIn(F.one_row(text)[F.ITEM_SMALL_COL], names)


if __name__ == "__main__":
    unittest.main()
