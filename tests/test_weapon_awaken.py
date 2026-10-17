# -*- coding: utf-8 -*-
"""武器觉醒与新掉落构建器门禁（设计 ${WF_ROOT}/out/武器觉醒与新掉落-20260928/设计.md §5.6、§6.5、§6.6、§7、§8.3）。

live（store / assets）只读；暂存只写临时目录。图标用合成源图 + 合成 manifest/approved（真图由图标单元
画在 mod-tools/assets/weapon-awaken/，另有一组用例拿真交付件核对 manifest 与门禁）。live 已上线某条边后再跑，
断言按 live 状态分支，仍然成立；图集/嵌套表/门禁另有合成数据用例保证有牙。
"""
from __future__ import annotations

from external_sources import client_patch_path, require_external_source

import copy
import json
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from PIL import Image  # noqa: E402

import wf_share_update_codec as codec  # noqa: E402
import wf_weapon_awaken as A  # noqa: E402
import wf_weapon_gacha as G  # noqa: E402

LIVE: G.Live
ART: tempfile.TemporaryDirectory
WORK: tempfile.TemporaryDirectory
E1: dict
E2: dict
E3: dict
R1: dict
R2: dict
R3: dict

SIZES = {"king_coin": (20, 20), "forbidden_star_steel": (20, 17), "deathbringer_blueprint_v2": (16, 16),
         "deep_crystal_v2": (16, 18), "fivefold_clear_badge_v2": (16, 16), "five_king_core_v2": (19, 19),
         "contradiction_crystal": (12, 17), "paradox_core": (20, 20)}
ICON_BY_STEM = {i.stem: i for i in A.ICONS}


def good_icon(size=(20, 20), outline=(110, 70, 10), fill=(230, 180, 40), shade=(190, 140, 30)):
    """官方规范的合成图：1px 物件色压暗描边、左上 2 像素高光、右下暗部；只有 0/255 两档 alpha。"""
    w, h = size
    image = Image.new("RGBA", (20, 20), (0, 0, 0, 0))
    x0, y0 = (20 - w) // 2, (20 - h) // 2
    px = image.load()
    for y in range(y0, y0 + h):
        for x in range(x0, x0 + w):
            edge = x in (x0, x0 + w - 1) or y in (y0, y0 + h - 1)
            lower_right = (x - x0) + (y - y0) > (w + h) * 0.7
            px[x, y] = (*(outline if edge else shade if lower_right else fill), 255)
    px[x0 + 2, y0 + 2] = px[x0 + 3, y0 + 2] = (255, 255, 255, 255)
    return image


def write_art(root: Path, stems=None, overrides=None, approve=True) -> Path:
    """照图标单元的交付形状写合成件：icons/<stem>.png、<stem>_c4.png、manifest.json，另可登记 approved.json。"""
    icons = root / "icons"
    icons.mkdir(parents=True, exist_ok=True)
    entries, approved = [], {}
    for stem in SIZES if stems is None else stems:
        icon = ICON_BY_STEM[stem]
        image = (overrides or {}).get(stem) or good_icon(SIZES[stem])
        c4 = image.resize((40, 40), Image.NEAREST)
        image.save(icons / f"{stem}.png")
        c4.save(icons / f"{stem}_c4.png")
        entries.append({"key": stem, "item_id": icon.item_id, "c3_logical": icon.c3, "c4_logical": icon.c4,
                        "c3_rgba_sha256": A.rgba_sha256(image), "c4_rgba_sha256": A.rgba_sha256(c4),
                        "c3_file": f"icons/{stem}.png", "c4_file": f"icons/{stem}_c4.png"})
        approved[stem] = A.rgba_sha256(image)
    (root / A.MANIFEST_NAME).write_text(json.dumps({"icons": entries}, indent=1), encoding="utf-8")
    if approve:
        (root / A.APPROVAL_NAME).write_text(json.dumps(
            {"approved_by": "测试", "evidence": "合成", "c3_rgba_sha256": approved}), encoding="utf-8")
    return root


def edit_manifest(root: Path, item_id: str, **fields) -> None:
    path = root / A.MANIFEST_NAME
    data = json.loads(path.read_text(encoding="utf-8"))
    for entry in data["icons"]:
        if entry["item_id"] == item_id:
            entry.update(fields)
    path.write_text(json.dumps(data), encoding="utf-8")


class OverlayLive(G.Live):
    """live + 已暂存文件当作已上线（验证幂等用）。"""

    def __init__(self, extra: dict):
        super().__init__()
        self.extra = extra

    def raw(self, logical, root="upload"):
        if root == "upload" and logical in self.extra:
            return self.extra[logical]
        return super().raw(logical, root)


class MaterialLive(G.Live):
    """live，但服务端白名单文件换成合成文本（其余照读 live），可选追加装备行（稀有度门禁用）。"""

    def __init__(self, material_text: str | None, extra_equipment: dict | None = None):
        super().__init__()
        self.material_text = material_text
        self.extra_equipment = extra_equipment or {}

    def server_bytes(self, name):
        if name == A.SERVER_MATERIAL:
            return None if self.material_text is None else self.material_text.encode("utf-8")
        return super().server_bytes(name)

    def flat(self, logical):
        rows = super().flat(logical)
        return {**rows, **self.extra_equipment} if logical == A.EQUIPMENT_LOGICAL else rows


def material_text(material: dict) -> str:
    return json.dumps(material, ensure_ascii=False, indent=2) + "\n"


_LIVE_READY = False


def _prepare_live():
    global _LIVE_READY
    if _LIVE_READY:
        return
    from external_sources import require_live_store
    require_live_store()
    global LIVE, ART, WORK, E1, E2, E3, R1, R2, R3
    LIVE = G.Live()
    ART = tempfile.TemporaryDirectory()
    unittest.addModuleCleanup(ART.cleanup)
    WORK = tempfile.TemporaryDirectory()
    unittest.addModuleCleanup(WORK.cleanup)
    write_art(Path(ART.name))
    work = Path(WORK.name)
    E1 = A.build_e1(LIVE, Path(ART.name))
    R1 = A.write_stage(work / "e1", LIVE, E1)
    over1 = A.Overlay([work / "e1"])
    E2 = A.build_e2(LIVE, over1)
    R2 = A.write_stage(work / "e2", LIVE, E2, over1)
    over12 = A.Overlay([work / "e1", work / "e2"])
    E3 = A.build_e3(LIVE, over12, drop_live=True)          # 掉落门另有用例（EdgeE3Tests）
    R3 = A.write_stage(work / "e3", LIVE, E3, over12)
    _LIVE_READY = True


class _LiveCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _prepare_live()


def live_has_icons() -> bool:
    names = {e["n"] for e in A.decode_atlas(LIVE.raw(A.ATLAS_MAP))}
    return all(i.c4 in names and LIVE.raw(i.c3 + ".png") is not None for i in A.ICONS if i.required)


def live_has_items() -> bool:
    items = LIVE.flat(A.ITEM_LOGICAL)
    return "10000310" in items and "10000311" in items


def staged_rows(out: dict, logical: str) -> dict:
    return A.flat_rows(out["tables"][logical][0]) if logical in out["tables"] else LIVE.flat(logical)


# ---------------------------------------------------------------------------
# 合同
# ---------------------------------------------------------------------------

class ContractTests(unittest.TestCase):
    def test_restricted_equipment_and_cas_keys(self):
        self.assertEqual(tuple(range(5910101, 5910130)) + (5920001,), A.RESTRICTED_EQUIPMENT)
        cas = A.cas_rows()
        self.assertEqual(30, len(cas))
        self.assertEqual({f"awakening_material_{i}" for i in A.RESTRICTED_EQUIPMENT}, set(cas))
        self.assertEqual({("10000311",)}, {tuple(v) for v in cas.values()})
        self.assertFalse({f"awakening_material_{i}" for i in (5921001, 5922001, 5923001)} & set(cas))
        self.assertEqual("10000311", G.core.write_csv_lines([cas["awakening_material_5920001"]]))
        self.assertEqual({str(i): 10000311 for i in A.RESTRICTED_EQUIPMENT}, A.material_map())

    def test_item_rows_exact(self):
        rows = A.item_rows()
        self.assertEqual({"10000310", "10000311"}, set(rows))
        self.assertEqual(
            "mod_five_boss_king_coin,10000310,深界王币,item/materials/mod/five_boss/king_coin,"
            "item_icon/materials/mod/five_boss/king_coin,镌刻着五王纹章的古币。可在五重决战商店兑换武器扭蛋券与禁忌星铁。"
            ",15,,,,,,,,6,(None),1,4,999999,2000-01-01 00:00:00,(None),false,",
            G.core.write_csv_lines([rows["10000310"]]))
        self.assertEqual(
            "mod_forbidden_star_steel,10000311,禁忌星铁,item/materials/mod/cursed/forbidden_star_steel,"
            "item_icon/materials/mod/cursed/forbidden_star_steel,只回应诅咒与悖论之力的星铁。可代替本体突破诅咒武器与悖论武器。"
            ",1,,,,,,,,2,(None),50,5,9999,2000-01-01 00:00:00,(None),false,",
            G.core.write_csv_lines([rows["10000311"]]))
        for row in rows.values():
            self.assertEqual(23, len(row))
            self.assertNotIn(",", row[5])
            self.assertNotIn("\n", row[5])
            self.assertEqual("item_icon/" + row[3][len("item/"):], row[4])
        steel = rows["10000311"]
        self.assertNotEqual("6", steel[6])
        self.assertEqual(("", ""), (steel[10], steel[11]))
        self.assertEqual({"category": 6, "sale_price": 1, "sellable": False}, A.server_item_sale(rows["10000310"]))
        self.assertEqual({"category": 2, "sale_price": 50, "sellable": False}, A.server_item_sale(rows["10000311"]))

    def test_icon_manifest(self):
        self.assertEqual(len(A.ICONS), len({i.c4 for i in A.ICONS}))
        self.assertEqual(len(A.ICONS), len({i.c3 for i in A.ICONS}))
        self.assertEqual(["10000310", "10000311"], [i.item_id for i in A.ICONS if i.required])
        self.assertEqual(G.STAR_STEEL_THUMB, A.ICON_BY_ITEM["10000311"].c3)
        self.assertEqual("item/materials/mod/cursed/forbidden_star_steel", G.STAR_STEEL_THUMB)   # 设计 §5.2/§6.4
        self.assertEqual("item/materials/mod/five_boss/king_coin", A.ICON_BY_ITEM["10000310"].c3)
        for icon in A.ICONS:
            self.assertTrue(icon.c4.startswith("item_icon/materials/mod/"))
            if icon.item_id in ("10000144", "10000145", "10000146", "10000147"):
                self.assertTrue(icon.c3.endswith("_v2") and "/five_boss/" in icon.c3)
        # PARADOX 重画版：c3 换 _v2 新名（旧名是 wf_paradox_weapon 的源图），c4 是 paradox 自有子纹理
        self.assertEqual(("item/materials/mod/paradox/contradiction_crystal_v2",
                          "item_icon/materials/mod/paradox/contradiction_crystal"),
                         (A.ICON_BY_ITEM["10000301"].c3, A.ICON_BY_ITEM["10000301"].c4))
        self.assertEqual(("item/materials/mod/paradox/paradox_core_v2", "item_icon/materials/mod/paradox/paradox_core"),
                         (A.ICON_BY_ITEM["10000302"].c3, A.ICON_BY_ITEM["10000302"].c4))

    def test_contract_matches_icon_unit_manifest(self):
        """构建器常量与图标单元交付的 manifest.json 逐项一致（两边任一改了路径都在这里变红）。"""
        manifest, problems = A.load_manifest(A.ART_DIR)
        if manifest is None:
            self.skipTest("图标单元的 manifest.json 不在本检出")
        self.assertEqual([], problems)
        for icon in A.ICONS:
            self.assertIn(icon.item_id, manifest)
            self.assertEqual([], A.manifest_problems(icon, manifest[icon.item_id]), icon.stem)
            self.assertIs(icon.rainbow, manifest[icon.item_id].get("rainbow"), icon.stem)   # 彩虹口径两边一致
        # 彩虹口径分叉（一边按彩虹豁免、另一边按全口径）必须报红；manifest 没写 rainbow 的旧合同不报
        steel = A.ICON_BY_ITEM["10000311"]
        self.assertFalse(steel.rainbow)             # 作者 0928 撤回彩虹重画：禁忌星铁回到紫灰锭，全口径门禁
        flipped = dict(manifest["10000311"], rainbow=True)
        self.assertTrue(any("rainbow" in p for p in A.manifest_problems(steel, flipped)))
        legacy = {k: v for k, v in manifest["10000311"].items() if k != "rainbow"}
        self.assertEqual([], A.manifest_problems(steel, legacy))

    def test_reward_row_and_ui_renames(self):
        self.assertEqual("five_boss_king_coin,0,10000310,1,1", G.core.write_csv_lines([A.REWARD_ROW]))
        self.assertEqual(("590010000", "5"), (A.REWARD_GROUP, A.REWARD_INDEX))
        self.assertEqual({"equipment_awaking_crystal": "觉醒素材",
                          "equipment_list_not_upgradable_reason_not_enough_awaking_items": "无可用于此装备的重复数或觉醒素材"},
                         {k: v[1] for k, v in A.UI_RENAMES.items()})


# ---------------------------------------------------------------------------
# 图标门禁
# ---------------------------------------------------------------------------

class IconGateTests(unittest.TestCase):
    ICON = A.ICON_BY_ITEM["10000310"]

    def problems(self, image, icon=None):
        return A.icon_problems(icon or self.ICON, A.icon_metrics(image))

    def test_good_icon_passes(self):
        self.assertEqual([], self.problems(good_icon()))
        m = A.icon_metrics(good_icon())
        self.assertEqual(((20, 20), (20, 20), 1.0), (m["size"], m["bbox"], m["outline_top2"]))
        self.assertLessEqual(m["speckle"], 0.10)

    def test_each_violation_is_caught(self):
        semi = good_icon()
        semi.putpixel((10, 10), (230, 180, 40, 128))
        self.assertTrue(any("alpha" in p for p in self.problems(semi)))
        self.assertTrue(any("尺寸" in p for p in self.problems(good_icon().resize((40, 40)))))
        self.assertTrue(any("包围盒" in p for p in self.problems(good_icon((16, 16)))))   # 王币要撑满 19
        self.assertTrue(any("近纯黑" in p for p in self.problems(good_icon(outline=(8, 6, 30)))))
        speckled = good_icon()
        for x in range(3, 17, 2):
            for y in range(4, 16, 2):
                speckled.putpixel((x, y), (20, 250, 250, 255))
        self.assertTrue(any("孤立杂色" in p for p in self.problems(speckled)))
        noisy = good_icon()
        for i in range(20):
            noisy.putpixel((1 + i % 17, 1 + i // 17 * 16), (100 + i * 7, 60, 10, 255))
        self.assertTrue(any("色数" in p or "描边前两色" in p for p in self.problems(noisy)))
        self.assertTrue(any("全透明" in p for p in self.problems(Image.new("RGBA", (20, 20)))))

    def test_outline_must_be_a_darkened_object_hue(self):
        grey = self.problems(good_icon(outline=(70, 70, 70)))              # 中性灰：不近黑，但没有色相
        self.assertTrue(any("不是主色相压暗" in p for p in grey))
        self.assertFalse(any("近纯黑" in p for p in grey))
        self.assertTrue(any("不是主色相压暗" in p for p in self.problems(good_icon(outline=(24, 24, 42)))))  # 旧 PARADOX
        self.assertTrue(any("不是主色相压暗" in p for p in self.problems(good_icon(outline=(200, 150, 40)))))  # 太亮
        blue_on_gold = self.problems(good_icon(outline=(20, 36, 96)))
        self.assertTrue(any("描边色相与物件不符" in p for p in blue_on_gold))
        self.assertEqual([], self.problems(good_icon(outline=(20, 36, 96), fill=(90, 140, 230), shade=(60, 100, 190))))
        m = A.icon_metrics(good_icon())
        self.assertEqual((0.91, 0.43, 1.0), (m["outline_sat"], m["outline_val"], m["outline_hue_share"]))

    def test_corner_sparkle_is_not_outline(self):
        """设计 §6.2：特殊物件角上可加 1–3 个十字星点；描边只看主体（最大 8 连通块），同图标单元口径。"""
        image = good_icon((14, 14))                                       # 主体占 (3,3)–(16,16)
        for xy, color in (((0, 1), (255, 240, 120)), ((2, 1), (255, 240, 120)),   # 左上角独立的十字星点
                          ((1, 0), (255, 255, 200)), ((1, 2), (255, 255, 200)),   # （不与主体 8 连通）
                          ((1, 1), (255, 255, 255))):
            image.putpixel(xy, (*color, 255))
        m = A.icon_metrics(image)
        self.assertEqual(1.0, m["outline_top2"])
        self.assertEqual((110, 70, 10), m["outline_color"])
        self.assertEqual((17, 17), m["bbox"])                             # 包围盒仍算全部不透明像素
        image.putpixel((2, 2), (255, 255, 255, 255))                      # 星点连上主体 ⇒ 算描边
        self.assertLess(A.icon_metrics(image)["outline_top2"], 1.0)

    def test_rainbow_exemption_only_for_colors_and_outline_mix(self):
        rainbow = good_icon((20, 17))
        for x in range(20):
            rainbow.putpixel((x, 1 + 1), (40 + x * 9, 80, 200 - x * 5, 255))
        # 彩虹豁免只作用于 rainbow=True 的件：作者 0928 撤回彩虹重画（「禁忌星铁上版那个紫灰挺好的」），交付件里没有彩虹件
        self.assertFalse(A.ICON_BY_ITEM["10000311"].rainbow)
        self.assertEqual([], [i.item_id for i in A.ICONS if i.rainbow])
        steel = A.Icon("x", "x", "item/x", "item_icon/x", 19, True, rainbow=True)
        self.assertFalse(any("色数" in p or "描边前两色" in p for p in self.problems(rainbow, steel)))
        plain = A.Icon("x", "x", "item/x", "item_icon/x", 19, True)
        self.assertTrue(any("色数" in p or "描边前两色" in p for p in self.problems(rainbow, plain)))
        grey = good_icon((20, 17), outline=(70, 70, 70))
        self.assertTrue(any("不是主色相压暗" in p for p in self.problems(grey, steel)))   # 彩虹件也不能灰描边


# ---------------------------------------------------------------------------
# 图集（合成）
# ---------------------------------------------------------------------------

class AtlasSyntheticTests(unittest.TestCase):
    def sheet(self):
        sheet = Image.new("RGBA", (100, 60), (0, 0, 0, 0))
        entries = [{"n": "old/a", "w": 20, "h": 20, "x": 1, "y": 1},
                   {"n": "old/b", "w": 10, "h": 14, "x": 30, "y": 1, "r": True, "fx": -1, "fy": 0, "fw": 12, "fh": 14}]
        sheet.paste(Image.new("RGBA", (20, 20), (200, 0, 0, 255)), (1, 1))
        sheet.paste(Image.new("RGBA", (14, 10), (0, 200, 0, 255)), (30, 1))
        return entries, sheet

    def test_find_slot_respects_gap_and_never_grows(self):
        entries, sheet = self.sheet()
        x, y = A.find_slot(entries, sheet, (20, 20))
        new = (x, y, x + 20, y + 20)
        for e in entries:
            self.assertFalse(A._overlaps(new, A.atlas_rect(e), A.ATLAS_GAP))
        self.assertIsNone(A.find_slot(entries, sheet, (99, 59)))

    def test_append_adds_and_verifies(self):
        entries, sheet = self.sheet()
        name = A.ICON_BY_ITEM["10000310"].c4
        tile = Image.new("RGBA", (20, 20), (0, 0, 255, 255))
        result = A.append_to_atlas(entries, sheet, [(name, tile)])
        self.assertEqual(([name], [], []), (result["added"], result["updated"], result["problems"]))
        self.assertEqual(entries, result["entries"][:2])
        self.assertEqual({"n", "w", "h", "x", "y"}, set(result["entries"][2]))
        self.assertEqual([], A.verify_atlas(entries, sheet, result["entries"], result["sheet"], [name]))
        # 再加一次 = 已存在且像素一致 → 无改动；换像素 → 原位更新
        again = A.append_to_atlas(result["entries"], result["sheet"], [(name, tile)])
        self.assertEqual(([], []), (again["added"], again["updated"]))
        recolor = A.append_to_atlas(result["entries"], result["sheet"],
                                    [(name, Image.new("RGBA", (20, 20), (9, 9, 9, 255)))])
        self.assertEqual([name], recolor["updated"])
        self.assertEqual(result["entries"], recolor["entries"])

    def test_foreign_and_reshaped_entries_are_refused(self):
        entries, sheet = self.sheet()
        foreign = A.append_to_atlas(entries, sheet, [("old/a", Image.new("RGBA", (20, 20)))])
        self.assertTrue(foreign["problems"])
        self.assertEqual(entries, foreign["entries"])
        name = A.ICON_BY_ITEM["10000311"].c4
        added = A.append_to_atlas(entries, sheet, [(name, Image.new("RGBA", (20, 20), (1, 2, 3, 255)))])
        reshaped = A.append_to_atlas(added["entries"], added["sheet"], [(name, Image.new("RGBA", (22, 20)))])
        self.assertTrue(any("形状不同" in p for p in reshaped["problems"]))

    def test_verify_catches_edits_outside_new_rects(self):
        entries, sheet = self.sheet()
        name = A.ICON_BY_ITEM["10000310"].c4
        result = A.append_to_atlas(entries, sheet, [(name, Image.new("RGBA", (20, 20), (0, 0, 255, 255)))])
        dirty = result["sheet"].copy()
        dirty.putpixel((5, 5), (1, 1, 1, 255))
        self.assertTrue(any("像素" in p for p in A.verify_atlas(entries, sheet, result["entries"], dirty, [name])))
        moved = copy.deepcopy(result["entries"])
        moved[1]["x"] += 1
        self.assertTrue(any("旧条目" in p for p in A.verify_atlas(entries, sheet, moved, result["sheet"], [name])))
        overlap = copy.deepcopy(result["entries"])
        overlap[2]["x"], overlap[2]["y"] = 2, 2
        self.assertTrue(any("重叠" in p for p in A.verify_atlas(entries, sheet, overlap, result["sheet"], [name])))


class RepackInnerTests(unittest.TestCase):
    def test_only_one_inner_key_changes(self):
        inner = codec.pack({"1": zlib.compress(b"a,0,1,1,1"), "2": zlib.compress(b"b,0,2,5,1")})
        raw = codec.pack({"7": inner, "8": codec.pack({"1": zlib.compress(b"z")})})
        staged, changed = A.repack_inner(raw, "7", {"3": "c,0,3,1,1", "2": "b,0,2,5,1"})
        self.assertEqual(["7"], changed)
        outer_old, outer_new = codec.unpack(raw), codec.unpack(staged)
        self.assertEqual(outer_old["8"], outer_new["8"])
        old_i, new_i = codec.unpack(outer_old["7"]), codec.unpack(outer_new["7"])
        self.assertEqual(["1", "2", "3"], list(new_i))
        self.assertEqual((old_i["1"], old_i["2"]), (new_i["1"], new_i["2"]))
        self.assertEqual(b"c,0,3,1,1", zlib.decompress(new_i["3"]))
        self.assertEqual((raw, []), A.repack_inner(raw, "7", {"1": "a,0,1,1,1"}))
        with self.assertRaises(KeyError):
            A.repack_inner(raw, "9", {"1": "x"})


# ---------------------------------------------------------------------------
# 边 E1（真 live + 合成源图）
# ---------------------------------------------------------------------------

class EdgeE1Tests(_LiveCase):
    def test_no_problems_and_status(self):
        self.assertEqual([], E1["problems"])
        self.assertEqual([], E1["blocked"])
        self.assertFalse(R1["refused"])
        self.assertEqual("ready", R1["status"])
        self.assertEqual({A.ITEM_LOGICAL: G.sha256(LIVE.raw(A.ITEM_LOGICAL))}, R1["plan"]["requires"]["sha256"])

    def test_atlas_is_append_only(self):
        if A.ATLAS_MAP not in E1["files"]:
            self.skipTest("live 图集已含全部子纹理且像素一致")
        old = A.decode_atlas(LIVE.raw(A.ATLAS_MAP))
        new = A.decode_atlas(E1["files"][A.ATLAS_MAP]["payload"])
        self.assertIn(A.ATLAS_PNG, E1["files"])                        # 两个文件同一条边
        self.assertEqual(old, new[:len(old)])
        self.assertEqual([list(e) for e in old], [list(e) for e in new[:len(old)]])
        self.assertEqual(len(old) + len(E1["report"]["atlas"]["added"]), len(new))
        self.assertGreaterEqual(len(old), 79)
        for e in new[len(old):]:
            self.assertEqual({"n", "w", "h", "x", "y"}, set(e))
            self.assertIn(e["n"], A.OWNED_ATLAS_NAMES)
        rects = [A.atlas_rect(e) for e in new]
        for i in range(len(old), len(new)):
            for j in range(len(new)):
                if i != j:
                    self.assertFalse(A._overlaps(rects[i], rects[j], A.ATLAS_GAP), (new[i]["n"], new[j]["n"]))
        old_sheet, new_sheet = A.open_png(LIVE.raw(A.ATLAS_PNG)), A.open_png(E1["files"][A.ATLAS_PNG]["payload"])
        self.assertEqual(old_sheet.size, new_sheet.size)
        touched = E1["report"]["atlas"]["added"] + E1["report"]["atlas"]["updated"]
        self.assertEqual([], A.verify_atlas(old, old_sheet, new, new_sheet, touched))

    def test_c4_equals_c3_times_two(self):
        if A.ATLAS_MAP not in E1["files"]:
            self.skipTest("live 图集已含全部子纹理且像素一致")
        entries = {e["n"]: e for e in A.decode_atlas(E1["files"][A.ATLAS_MAP]["payload"])}
        sheet = A.open_png(E1["files"][A.ATLAS_PNG]["payload"])
        for icon in A.ICONS:
            e = entries[icon.c4]
            region = sheet.crop((e["x"], e["y"], e["x"] + e["w"], e["y"] + e["h"]))
            c3 = Image.open(Path(ART.name) / "icons" / f"{icon.stem}.png").convert("RGBA")
            staged = E1["files"].get(icon.c3 + ".png")
            if staged is not None:
                self.assertEqual(c3.tobytes(), A.open_png(staged["payload"]).tobytes())
                self.assertEqual(G.assets.PNG_FAKE, staged["payload"][:8])
            self.assertEqual((40, 40), region.size)
            self.assertEqual(c3.resize((40, 40), Image.NEAREST).tobytes(), region.tobytes(), icon.stem)

    def test_idempotent_once_live(self):
        extra = {k: v["payload"] for k, v in E1["files"].items()}
        again = A.build_e1(OverlayLive(extra), Path(ART.name))
        self.assertEqual(([], {}), (again["problems"], again["files"]))

    def test_missing_required_art_blocks_and_paradox_needs_its_redraw(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = A.build_e1(LIVE, write_art(Path(tmp), stems=["deep_crystal_v2"]))
            self.assertEqual([], out["problems"])
            self.assertEqual(2, len(out["blocked"]))
            self.assertTrue(all("king_coin" in b or "forbidden_star_steel" in b for b in out["blocked"]))
            # PARADOX 没有重画版就不发 c4（不再拿 live 旧 c3×2 顶替：旧图过不了门禁）
            self.assertNotIn(A.ICON_BY_ITEM["10000301"].c4, out["report"]["atlas"]["added"])
            self.assertNotIn(A.ICON_BY_ITEM["10000302"].c4, out["report"]["atlas"]["added"])
            self.assertEqual("missing", out["report"]["icons"]["paradox_core"])
            result = A.write_stage(Path(tmp) / "w", LIVE, out)
            self.assertEqual("blocked", result["status"])
            self.assertTrue((Path(tmp) / "w" / "plan.blocked.json").is_file())
            self.assertFalse((Path(tmp) / "w" / "plan.json").exists())

    def test_bad_art_is_refused_and_nothing_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            art = write_art(Path(tmp) / "art", overrides={"king_coin": good_icon(outline=(0, 0, 0))})
            out = A.build_e1(LIVE, art)
            self.assertTrue(any("king_coin" in p and "近纯黑" in p for p in out["problems"]))
            result = A.write_stage(Path(tmp) / "w", LIVE, out)
            self.assertTrue(result["refused"])
            self.assertFalse((Path(tmp) / "w").exists())

    def test_explicit_c4_must_equal_c3_times_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            art = write_art(Path(tmp))
            good_icon().resize((40, 40), Image.BILINEAR).save(art / "icons" / "king_coin_40.png")
            Image.new("RGBA", (40, 40)).save(art / "icons" / "forbidden_star_steel@2x.png")
            problems = A.build_e1(LIVE, art)["problems"]
            self.assertTrue(any("forbidden_star_steel@2x.png" in p for p in problems))
            good_icon().resize((40, 40), Image.NEAREST).save(art / "icons" / "king_coin_40.png")
            self.assertFalse(any("king_coin_40.png" in p for p in A.build_e1(LIVE, art)["problems"]))
            # 图标单元的交付名 <stem>_c4.png（manifest c4_file）同样要核
            good_icon(SIZES["deep_crystal_v2"]).resize((40, 40), Image.BILINEAR).save(art / "icons" / "deep_crystal_v2_c4.png")
            self.assertTrue(any("deep_crystal_v2_c4.png" in p for p in A.build_e1(LIVE, art)["problems"]))

    def test_manifest_contract_is_enforced(self):
        """图标单元 manifest 的逻辑路径 / 像素 sha 与构建器不一致 ⇒ 拒绝（审阅 0928：两边合同各自为政）。"""
        cases = {
            "c3_logical": ("10000310", {"c3_logical": "item/materials/mod/weapon_awaken/king_coin"}, "c3_logical"),
            "c4_logical": ("10000302", {"c4_logical": "item_icon/materials/mod/paradox/paradox_core_v2"}, "c4_logical"),
            "key": ("10000145", {"key": "deep_crystal"}, "key"),
            "c3 sha": ("10000311", {"c3_rgba_sha256": "0" * 64}, "c3_rgba_sha256"),
            "c4 sha": ("10000144", {"c4_rgba_sha256": "0" * 64}, "c4_rgba_sha256"),
            "c4 file": ("10000146", {"c4_file": "icons/nope.png"}, "c4_file"),
            "c3 file": ("10000147", {"c3_file": "icons/nope.png"}, "c3_file"),
        }
        for label, (item_id, fields, needle) in cases.items():
            with self.subTest(label), tempfile.TemporaryDirectory() as tmp:
                art = write_art(Path(tmp))
                edit_manifest(art, item_id, **fields)
                problems = A.build_e1(LIVE, art)["problems"]
                self.assertTrue(any(needle in p for p in problems), problems)
        with tempfile.TemporaryDirectory() as tmp:
            art = write_art(Path(tmp))
            good_icon(outline=(120, 80, 20)).save(art / "icons" / "king_coin.png")     # 改了图没重出 manifest
            self.assertTrue(any("c3_rgba_sha256" in p for p in A.build_e1(LIVE, art)["problems"]))
        with tempfile.TemporaryDirectory() as tmp:
            art = write_art(Path(tmp))
            (art / A.MANIFEST_NAME).unlink()                                            # 有图没 manifest
            problems = A.build_e1(LIVE, art)["problems"]
            self.assertTrue(any("没登记" in p and "king_coin" in p for p in problems))

    def test_author_preview_confirmation_gates_ready(self):
        """设计 §6.5 第 3 步 / §7 第 2 步：没登记作者确认、或确认后像素又变了 ⇒ blocked，不给 plan.json。"""
        with tempfile.TemporaryDirectory() as tmp:
            art = write_art(Path(tmp) / "art", approve=False)
            out = A.build_e1(LIVE, art)
            self.assertEqual([], out["problems"])
            if not out["files"]:
                self.skipTest("live 已含全部图")
            self.assertEqual("blocked", A.edge_status(out))
            self.assertTrue(any("待作者确认预览" in b for b in out["blocked"]))
            self.assertEqual(sorted(SIZES), out["report"]["approval"]["unapproved"])
            refused = A.approve(art, by="作者", evidence=" ")
            self.assertTrue(refused["refused"])
            self.assertFalse((art / A.APPROVAL_NAME).exists())
            done = A.approve(art, by="作者", evidence="2026-09-28 作者：图标可以", only=["king_coin"])
            self.assertFalse(done["refused"], done["problems"])
            out = A.build_e1(LIVE, art)
            self.assertNotIn("king_coin", out["report"]["approval"]["unapproved"])
            self.assertIn("paradox_core", out["report"]["approval"]["unapproved"])
            done = A.approve(art, by="作者", evidence="2026-09-28 作者：全部可以")
            self.assertEqual(set(SIZES), set(done["approved"]))
            record = json.loads((art / A.APPROVAL_NAME).read_text(encoding="utf-8"))
            self.assertEqual(2, len(record["history"]))
            out = A.build_e1(LIVE, art)
            self.assertEqual(([], []), (out["problems"], out["blocked"]))
            self.assertEqual("ready", A.edge_status(out))
            # 确认后又改图（并重出 manifest）：sha 对不上 ⇒ 这张回到待确认，其余不受影响
            full = write_art(Path(tmp) / "art2", overrides={"paradox_core": good_icon(outline=(120, 80, 20))},
                             approve=False)
            (full / A.APPROVAL_NAME).write_text((art / A.APPROVAL_NAME).read_text(encoding="utf-8"), encoding="utf-8")
            out = A.build_e1(LIVE, full)
            self.assertEqual([], out["problems"])
            self.assertEqual(["paradox_core"], out["report"]["approval"]["unapproved"])

    def test_approve_refuses_art_that_fails_gates(self):
        with tempfile.TemporaryDirectory() as tmp:
            art = write_art(Path(tmp), overrides={"king_coin": good_icon(outline=(70, 70, 70))}, approve=False)
            result = A.approve(art, by="作者", evidence="x")
            self.assertTrue(result["refused"])
            self.assertTrue(any("king_coin" in p for p in result["problems"]))
            self.assertFalse((art / A.APPROVAL_NAME).exists())
            self.assertTrue(A.approve(art, by="作者", evidence="x", only=["no_such"])["refused"])

    def test_delivered_art_passes_builder_gates(self):
        """图标单元真交付件（mod-tools/assets/weapon-awaken/）：manifest 合同、像素 sha、c4 = c3×2、门禁全过；
        PARADOX 用重画版（旧 live c3 过不了门禁）。"""
        manifest, _ = A.load_manifest(A.ART_DIR)
        if manifest is None:
            self.skipTest("图标单元交付件不在本检出")
        out = A.build_e1(LIVE, A.ART_DIR, approval_path=Path(WORK.name) / "no-approval.json")
        self.assertEqual([], out["problems"])
        self.assertEqual({i.stem for i in A.ICONS}, {k for k, v in out["report"]["icons"].items() if isinstance(v, dict)})
        old_c3 = {"10000301": "item/materials/mod/paradox/contradiction_crystal.png",
                  "10000302": "item/materials/mod/paradox/paradox_core.png"}
        for item_id, logical in old_c3.items():
            old = LIVE.raw(logical)
            if old is not None:
                icon = A.ICON_BY_ITEM[item_id]
                self.assertTrue(A.icon_problems(icon, A.icon_metrics(A.open_png(old))), icon.stem)


# ---------------------------------------------------------------------------
# 边 E2
# ---------------------------------------------------------------------------

class EdgeE2Tests(_LiveCase):
    def test_status_follows_e1(self):
        self.assertEqual([], E2["problems"])
        self.assertFalse(R2["refused"])
        if LIVE.server_json(A.SERVER_MATERIAL) is None:   # 服务端白名单（§7 第 1 步）未上线 ⇒ 只因它 blocked
            self.assertEqual("blocked", R2["status"])
            self.assertTrue(E2["blocked"])
            self.assertTrue(all(A.SERVER_MATERIAL in b for b in E2["blocked"]), E2["blocked"])
        elif live_has_icons():
            self.assertEqual("ready", R2["status"])
        else:
            self.assertEqual("pending", R2["status"])
            requires = R2["plan"]["requires"]["sha256"]
            if A.ATLAS_MAP in E1["files"]:
                self.assertEqual(G.sha256(E1["files"][A.ATLAS_MAP]["payload"]), requires[A.ATLAS_MAP])
            self.assertTrue((Path(WORK.name) / "e2" / "plan.pending.json").is_file())
            self.assertFalse((Path(WORK.name) / "e2" / "plan.json").exists())
            bare = A.build_e2(LIVE)
            self.assertEqual("blocked", A.edge_status(bare))
            self.assertTrue(any("10000310" in b for b in bare["blocked"]))

    def test_item_table_owned_keys_only(self):
        if A.ITEM_LOGICAL not in E2["tables"]:
            self.skipTest("live 道具行已是目标态")
        staged, changed, deleted = E2["tables"][A.ITEM_LOGICAL]
        owned = {i.item_id for i in A.ICONS}
        self.assertEqual([], deleted)
        self.assertLessEqual(set(changed), owned)
        old, new = codec.unpack(LIVE.raw(A.ITEM_LOGICAL)), codec.unpack(staged)
        self.assertEqual(list(old), [k for k in new if k in old])
        for key, blob in old.items():
            if key not in changed:
                self.assertEqual(blob, new[key], key)
        rows = A.item_rows()
        for key in changed:
            self.assertEqual(b"\x78\x9c", new[key][:2])
            if key in rows:
                self.assertEqual(G.core.write_csv_lines([rows[key]]), zlib.decompress(new[key]).decode("utf-8"))

    def test_repoints_only_c3_c4(self):
        live_items = LIVE.flat(A.ITEM_LOGICAL)
        items = staged_rows(E2, A.ITEM_LOGICAL)
        for item_id in E2["report"]["repointed"]:
            icon = A.ICON_BY_ITEM[item_id]
            before, after = live_items[item_id], items[item_id]
            self.assertEqual((icon.c3, icon.c4), (after[3], after[4]))   # c3/c4 同一条边一起改指
            self.assertEqual(before[:3] + before[5:], after[:3] + after[5:])
        if not live_has_icons():   # 合成 E1 带全部 8 张图 ⇒ 重画件与 PARADOX 全部改指
            self.assertEqual(["10000144", "10000145", "10000146", "10000147", "10000301", "10000302"],
                             E2["report"]["repointed"])

    def test_paradox_sync_warning_reads_the_paradox_tool(self):
        icon = A.ICON_BY_ITEM["10000301"]
        with tempfile.TemporaryDirectory() as tmp:
            stale = Path(tmp) / "stale.py"
            stale.write_text('MATERIALS = (("10000301", "item/materials/mod/paradox/contradiction_crystal", '
                             '"item_icon/materials/mod/five_boss/deep_crystal"),)', encoding="utf-8")
            synced = Path(tmp) / "synced.py"
            synced.write_text(f'MATERIALS = (("10000301", "{icon.c3}", "{icon.c4}"),)', encoding="utf-8")
            self.assertFalse(A.paradox_tool_synced(icon, stale))
            self.assertTrue(A.paradox_tool_synced(icon, synced))
            self.assertFalse(A.paradox_tool_synced(icon, Path(tmp) / "missing.py"))
        if {"10000301", "10000302"} & set(E2["report"]["repointed"]) and not A.paradox_tool_synced(icon):
            self.assertTrue(any("wf_paradox_weapon.py" in w for w in E2["warnings"]))
        # 真 PARADOX 生成器已同步到重画版（它下次暂存不会把道具行改回旧图）
        for item_id in ("10000301", "10000302"):
            self.assertTrue(A.paradox_tool_synced(A.ICON_BY_ITEM[item_id]), item_id)
        self.assertFalse(any("wf_paradox_weapon.py" in w for w in E2["warnings"]))

    def test_awakening_item_gates(self):
        items = staged_rows(E2, A.ITEM_LOGICAL)
        self.assertEqual(["12001", "12002"], sorted(k for k, r in items.items() if r[6:7] == ["6"]))
        for key, (value,) in A.cas_rows().items():
            self.assertIn(value, items, key)
            self.assertNotEqual("6", items[value][6])

    def test_cas_ui_and_reward_tables(self):
        cas = staged_rows(E2, A.CAS_LOGICAL)
        for key, row in A.cas_rows().items():
            self.assertEqual(row, cas[key])
        ui = staged_rows(E2, A.UI_LOGICAL)
        self.assertEqual(["觉醒素材"], ui["equipment_awaking_crystal"])
        self.assertEqual(["无可用于此装备的重复数或觉醒素材"],
                         ui["equipment_list_not_upgradable_reason_not_enough_awaking_items"])
        for logical in (A.CAS_LOGICAL, A.UI_LOGICAL):
            if logical in E2["tables"]:
                staged, changed, _ = E2["tables"][logical]
                old, new = codec.unpack(LIVE.raw(logical)), codec.unpack(staged)
                self.assertEqual({k for k in old if k not in changed}, {k for k in new if k in old and k not in changed})
                self.assertTrue(all(old[k] == new[k] for k in old if k not in changed))
        raw = E2["tables"][A.REWARD_LOGICAL][0] if A.REWARD_LOGICAL in E2["tables"] else LIVE.raw(A.REWARD_LOGICAL)
        old_outer, new_outer = codec.unpack(LIVE.raw(A.REWARD_LOGICAL)), codec.unpack(raw)
        self.assertEqual(list(old_outer), list(new_outer))
        for key in old_outer:
            if key != A.REWARD_GROUP:
                self.assertEqual(old_outer[key], new_outer[key], key)
        old_inner, new_inner = codec.unpack(old_outer[A.REWARD_GROUP]), codec.unpack(new_outer[A.REWARD_GROUP])
        self.assertEqual(["1", "2", "3", "4", "5"], list(new_inner))
        for key in ("1", "2", "3", "4"):
            self.assertEqual(old_inner[key], new_inner[key])
        self.assertEqual(b"five_boss_king_coin,0,10000310,1,1", zlib.decompress(new_inner["5"]))

    def test_server_splices(self):
        for name, (payload, added, deleted, updated) in E2["server"].items():
            old_text = LIVE.server_text(name)
            new_text = payload.decode("utf-8")
            old, new = json.loads(old_text), json.loads(new_text)
            self.assertEqual("\r\n" in old_text, "\r\n" in new_text, name)
            self.assertEqual([], [d for d in deleted if not d.startswith("rarityOverrides.")])
            if isinstance(old, list):
                self.assertEqual(old + [int(a) for a in added], new)
                self.assertEqual(["10000310", "10000311"], added)
                continue
            for key in set(old) | set(new):
                if key not in {"10000310", "10000311", "materialByEquipment", "rarityOverrides"}:
                    self.assertEqual(old.get(key), new.get(key), (name, key))
        lookup = json.loads(E2["server"][A.SERVER_ITEM_LOOKUP][0]) if A.SERVER_ITEM_LOOKUP in E2["server"] \
            else LIVE.server_json(A.SERVER_ITEM_LOOKUP)
        self.assertEqual(("深界王币", "禁忌星铁"), (lookup["10000310"], lookup["10000311"]))
        sale = json.loads(E2["server"][A.SERVER_ITEM_SALE][0]) if A.SERVER_ITEM_SALE in E2["server"] \
            else LIVE.server_json(A.SERVER_ITEM_SALE)
        self.assertEqual({"category": 2, "sale_price": 50, "sellable": False}, sale["10000311"])

    def test_server_material_json_equals_cas(self):
        material = LIVE.server_json(A.SERVER_MATERIAL)
        if material is None:
            self.assertTrue(any(A.SERVER_MATERIAL in b for b in E2["blocked"]))
            return
        final = json.loads(E2["server"][A.SERVER_MATERIAL][0]) if A.SERVER_MATERIAL in E2["server"] else material
        self.assertEqual({k[len(A.CAS_PREFIX):]: int(v[0]) for k, v in A.cas_rows().items()},
                         final["materialByEquipment"])
        owned = {"materialByEquipment", "rarityOverrides"}
        self.assertEqual({k: v for k, v in material.items() if k not in owned},
                         {k: v for k, v in final.items() if k not in owned})
        equipment = LIVE.flat(A.EQUIPMENT_LOGICAL)
        self.assertEqual({k: int(r[11]) for k, r in equipment.items() if int(r[11]) != int(k) // 1_000_000},
                         final["rarityOverrides"])

    def test_rarity_overrides_follow_live_c11(self):
        """独立重算：live 装备 c11 ≠ floor(id/1e6) 的行全部登记，不多不少（审阅 0928：快照原本无人维护）。"""
        equipment = LIVE.flat(A.EQUIPMENT_LOGICAL)
        want, problems = A.rarity_overrides(equipment)
        self.assertEqual([], problems)
        self.assertEqual({k: int(r[11]) for k, r in equipment.items() if int(r[11]) != int(k) // 1_000_000}, want)
        for eid in ("8000101", "8000115", "100013", "100023"):   # 深渊 80001xx / 幻想 1000xx 都是 ★5
            self.assertEqual(5, want[eid], eid)
        for eid in A.RESTRICTED_EQUIPMENT:
            self.assertNotIn(str(eid), want)
        self.assertEqual(len(want), E2["report"]["rarity_overrides"])
        self.assertFalse(any("rarityOverrides" in p for p in E2["problems"]))

    def test_rarity_overrides_synthetic(self):
        def row(c11):
            return ["x"] * 11 + [c11, "y"]

        want, problems = A.rarity_overrides({
            "8000116": row("5"),    # 新深渊武器：百万位 8 ≠ ★5 → 登记
            "5000001": row("5"),    # 百万位即稀有度 → 不登记
            "700001": row("5"),     # ID < 1e6 的 ★5 → 登记
            "4000001": row("4"),
            "3000009": row("9"),    # 须登记但服务端只收 1–5
            "6000001": row(""),     # c11 不是整数
            "abc": row("5"),        # 键不是整数
        })
        self.assertEqual(["700001", "8000116"], list(want))   # 数值序：暂存追加顺序稳定
        self.assertEqual({"700001": 5, "8000116": 5}, want)
        self.assertEqual(3, len(problems))
        self.assertTrue(any("3000009" in p and "1–5" in p for p in problems))
        self.assertTrue(any("6000001" in p for p in problems))
        self.assertTrue(any("abc" in p for p in problems))

    def test_rarity_overrides_resync_on_drift(self):
        material = LIVE.server_json(A.SERVER_MATERIAL)
        if material is None:
            self.skipTest("服务端白名单未上线")
        want, _ = A.rarity_overrides(LIVE.flat(A.EQUIPMENT_LOGICAL))
        drifted = copy.deepcopy(material)
        overrides = drifted["rarityOverrides"]
        missing, wrong = sorted(want, key=int)[-1], sorted(want, key=int)[0]
        del overrides[missing]         # 新武器上线没人登记
        overrides[wrong] = 4           # 值漂移
        overrides["4999999"] = 5       # 多余键
        out = A.build_e2(MaterialLive(material_text(drifted)))
        self.assertEqual([], out["problems"])
        payload, added, deleted, updated = out["server"][A.SERVER_MATERIAL]
        final = json.loads(payload)
        self.assertEqual(want, final["rarityOverrides"])
        self.assertEqual(A.material_map(), final["materialByEquipment"])
        self.assertEqual(drifted["officialCrystals"], final["officialCrystals"])
        self.assertIn(f"rarityOverrides.{missing}", added)
        self.assertEqual(["rarityOverrides.4999999"], deleted)
        self.assertIn(f"rarityOverrides.{wrong}", updated)
        self.assertTrue(any("rarityOverrides 与 live" in w for w in out["warnings"]))
        again = A.build_e2(MaterialLive(payload.decode("utf-8")))   # 对齐后再跑：该文件零改动
        self.assertEqual([], again["problems"])
        self.assertNotIn(A.SERVER_MATERIAL, again["server"])

    def test_rarity_gates_have_teeth(self):
        from unittest import mock

        material = LIVE.server_json(A.SERVER_MATERIAL)
        if material is None:
            self.skipTest("服务端白名单未上线")
        no_field = {k: v for k, v in material.items() if k != "rarityOverrides"}
        self.assertTrue(any("缺 rarityOverrides" in p for p in A.build_e2(MaterialLive(material_text(no_field)))["problems"]))

        drifted = copy.deepcopy(material)
        drifted["rarityOverrides"]["4999999"] = 5
        original = G.splice_json

        def skip_rarity(text, edit):
            return (text, [], [], []) if edit.path == ("rarityOverrides",) else original(text, edit)

        with mock.patch.object(G, "splice_json", skip_rarity):   # 拼接没生效 ⇒ 终态门禁拦下
            problems = A.build_e2(MaterialLive(material_text(drifted)))["problems"]
        self.assertTrue(any("rarityOverrides 与 live 装备" in p for p in problems))

        bad = list(LIVE.flat(A.EQUIPMENT_LOGICAL)["8000101"])
        bad[A.EQUIPMENT_RARITY_COL] = "9"
        problems = A.build_e2(MaterialLive(material_text(material), {"8000199": bad}))["problems"]
        self.assertTrue(any("8000199" in p and "1–5" in p for p in problems))

    def test_gates_have_teeth(self):
        from unittest import mock

        original = A.item_rows()

        def rows_with(key, col, value):
            rows = copy.deepcopy(original)
            rows[key][col] = value
            return rows

        with mock.patch.object(A, "item_rows", lambda: rows_with("10000311", 6, "6")):
            problems = A.build_e2(LIVE)["problems"]
        self.assertTrue(any("禁忌星铁 c6" in p for p in problems))
        self.assertTrue(any("c6=6 的觉醒道具应只有" in p for p in problems))
        self.assertTrue(any("指向 c6=6" in p for p in problems))
        with mock.patch.object(A, "item_rows", lambda: rows_with("10000310", 5, "含,逗号")):
            self.assertTrue(any("半角逗号" in p for p in A.build_e2(LIVE)["problems"]))
        with mock.patch.object(A, "cas_rows", lambda: {"awakening_material_5910101": ["99999999"]}):
            problems = A.build_e2(LIVE)["problems"]
        self.assertTrue(any("指向不存在的道具 99999999" in p for p in problems))
        self.assertTrue(any("materialByEquipment 与 CAS" in p for p in problems) or
                        LIVE.server_json(A.SERVER_MATERIAL) is None)
        with mock.patch.object(A, "RESTRICTED_EQUIPMENT", A.RESTRICTED_EQUIPMENT + (5999999,)):
            self.assertTrue(any("5999999" in p for p in A.build_e2(LIVE)["problems"]))
        with mock.patch.object(A, "REWARD_ROW", ["other", "0", "1", "1", "1"]), \
                mock.patch.object(A, "REWARD_INDEX", "1"):
            self.assertTrue(any("已被占用" in p for p in A.build_e2(LIVE)["problems"]))
        with mock.patch.dict(A.UI_RENAMES, {"equipment_awaking_crystal": ("不是这个", "觉醒素材")}):
            if LIVE.flat(A.UI_LOGICAL)["equipment_awaking_crystal"] != ["觉醒素材"]:
                self.assertTrue(any("ui_string" in p for p in A.build_e2(LIVE)["problems"]))

    def test_material_splice_on_synthetic_drift(self):
        text = ('{\n  "materialByEquipment": {\n    "5910101": 10000311,\n    "5910102": 12002\n  },\n'
                '  "officialCrystals": {\n    "12001": {\n      "maxRarity": 4\n    }\n  }\n}\n')
        edit = G.ServerEdit(path=("materialByEquipment",), upsert=A.material_map(), style="indent",
                            siblings=("5910101",))
        new, added, _, updated = G.splice_json(text, edit)
        self.assertEqual(["5910102"], updated)
        self.assertEqual(28, len(added))
        self.assertEqual(A.material_map(), json.loads(new)["materialByEquipment"])
        self.assertEqual({"12001": {"maxRarity": 4}}, json.loads(new)["officialCrystals"])


# ---------------------------------------------------------------------------
# 边 E3
# ---------------------------------------------------------------------------

class EdgeE3Tests(_LiveCase):
    def test_status_follows_e1_e2(self):
        self.assertEqual([], E3["problems"])
        self.assertFalse(R3["refused"])
        if live_has_items() and LIVE.raw(G.STAR_STEEL_THUMB + ".png") is not None:
            self.assertEqual("ready", R3["status"])
        elif R2["status"] == "blocked":               # 前一条边 blocked（如白名单未上线）⇒ 本边 blocked
            self.assertEqual("blocked", R3["status"])
            self.assertTrue(any("本身是 blocked" in b for b in E3["blocked"]))
        else:
            self.assertEqual("pending", R3["status"])
            self.assertIn(A.ITEM_LOGICAL, R3["plan"]["requires"]["sha256"])
            bare = A.build_e3(LIVE)
            self.assertEqual("blocked", A.edge_status(bare))
            self.assertIn("10000311", R3["plan"]["requires"]["table_keys"][A.ITEM_LOGICAL])

    def test_shop_rows_match_gacha_builder(self):
        template = LIVE.flat(G.SHOP_LOGICAL)[G.SHOP_TEMPLATE_KEY]
        rows, server, problems = G.shop_targets(template)
        self.assertEqual([], problems)
        shop = staged_rows(E3, G.SHOP_LOGICAL)
        for key, row in rows.items():
            self.assertEqual(row, shop[key])
        self.assertEqual(G.build(LIVE)["shop_target"]["rows"], rows)
        if G.SHOP_LOGICAL in E3["tables"]:
            staged, changed, deleted = E3["tables"][G.SHOP_LOGICAL]
            self.assertEqual([], deleted)
            self.assertLessEqual(set(changed), {"990099032", "990099033", "990099034", *A.SHOP_FRAME_FIXES})
            old, new = codec.unpack(LIVE.raw(G.SHOP_LOGICAL)), codec.unpack(staged)
            self.assertTrue(all(old[k] == new[k] for k in old if k not in changed))
        for key, (_old, want, _reward) in A.SHOP_FRAME_FIXES.items():     # 凭证底框：只动 c13
            live_row = LIVE.flat(G.SHOP_LOGICAL)[key]
            self.assertEqual(live_row[:A.SHOP_FRAME_COL] + [want] + live_row[A.SHOP_FRAME_COL + 1:], shop[key])
        server_shop = json.loads(E3["server"][A.SERVER_SHOP][0])["99"] if A.SERVER_SHOP in E3["server"] \
            else LIVE.server_json(A.SERVER_SHOP)["99"]
        self.assertEqual(server, {k: server_shop[k] for k in server})
        self.assertEqual({"990099001", "990099002", "990099032", "990099033", "990099034"}, set(server_shop))
        shop_map = json.loads(E3["server"][A.SERVER_SHOP_MAP][0]) if A.SERVER_SHOP_MAP in E3["server"] \
            else LIVE.server_json(A.SERVER_SHOP_MAP)
        self.assertEqual(99, shop_map["990099034"])
        for name, (payload, *_rest) in E3["server"].items():
            old, new = LIVE.server_json(name), json.loads(payload)
            for key in set(old) | set(new):
                if key not in ("99", "990099034"):
                    self.assertEqual(old.get(key), new.get(key), (name, key))

    def test_drop_detection_needs_source_and_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, out = Path(tmp) / "src", Path(tmp) / "out"
            src.mkdir()
            out.mkdir()
            (src / "rewards.ts").write_text("export const X = { deepCrystal: 10000145 }", encoding="utf-8")
            (out / "rewards.js").write_text("exports.X = { deepCrystal: 10000145 };", encoding="utf-8")
            self.assertFalse(G.five_boss_drop_live((src, out)))
            (src / "rewards.ts").write_text("export const X = { kingCoin: 10000310 }", encoding="utf-8")
            self.assertFalse(G.five_boss_drop_live((src, out)))                # 改了源码没 tsc：服务端仍跑旧 out/
            (out / "rewards.js").write_text("exports.X = { kingCoin: 100003101 };", encoding="utf-8")
            self.assertFalse(G.five_boss_drop_live((src, out)))                # 只认完整 ID
            (out / "rewards.js").write_text("exports.X = { kingCoin: 10000310 };", encoding="utf-8")
            self.assertTrue(G.five_boss_drop_live((src, out)))
            (src / "rewards.ts").write_text("export const X = {}", encoding="utf-8")
            (src / "rewards.test.ts").write_text("expect(10000310)", encoding="utf-8")
            self.assertFalse(G.five_boss_drop_live((src, out)))                # 测试文件不算
            self.assertFalse(G.five_boss_drop_live((Path(tmp) / "missing",)))

    def test_drop_not_live_blocks_even_with_after(self):
        """设计 §7 第 7 步：E3 排在五重掉落之后——没掉落时 --after 满足了道具与图也仍然 blocked。"""
        over12 = A.Overlay([Path(WORK.name) / "e1", Path(WORK.name) / "e2"])
        out = A.build_e3(LIVE, over12, drop_live=False)
        self.assertEqual([], out["problems"])
        self.assertEqual("blocked", A.edge_status(out))
        self.assertTrue(any("五重掉落" in b and "10000310" in b for b in out["blocked"]))
        self.assertFalse(out["report"]["five_boss_drop_live"])
        self.assertTrue(E3["report"]["five_boss_drop_live"])
        self.assertFalse(any("五重掉落" in b for b in E3["blocked"]))

    def test_stage_node_c9_is_opt_in(self):
        self.assertNotIn(A.NODE_LOGICAL, E3["tables"])
        out = A.build_e3(LIVE, stage_node_c9=True)
        self.assertEqual([], out["problems"])
        old = codec.unpack(LIVE.raw(A.NODE_LOGICAL))
        live_row = G.core.read_csv_lines(zlib.decompress(codec.unpack(old["1"])["99"]).decode("utf-8"))[0]
        if A.NODE_LOGICAL not in out["tables"]:
            self.assertEqual("10000310", live_row[9])
            return
        new = codec.unpack(out["tables"][A.NODE_LOGICAL][0])
        self.assertEqual(list(old), list(new))
        old_inner, new_inner = codec.unpack(old["1"]), codec.unpack(new["1"])
        self.assertTrue(all(old_inner[k] == new_inner[k] for k in old_inner if k != "99"))
        row = G.core.read_csv_lines(zlib.decompress(new_inner["99"]).decode("utf-8"))[0]
        self.assertEqual("10000310", row[9])
        self.assertEqual(live_row[:9] + live_row[10:], row[:9] + row[10:])
        self.assertTrue(any("五重线同意" in w for w in out["warnings"]))


# ---------------------------------------------------------------------------
# 暂存合同
# ---------------------------------------------------------------------------

class StageContractTests(_LiveCase):
    def test_plans_follow_the_apply_contract(self):
        for result, edge in ((R1, "e1"), (R2, "e2"), (R3, "e3")):
            work = Path(WORK.name) / edge
            plan = json.loads(Path(result["plan_path"]).read_text(encoding="utf-8"))
            self.assertLessEqual({"tables", "files", "server", "deleted", "requires", "status", "edge"}, set(plan))
            self.assertEqual(1, sum((work / n).is_file() for n in A.PLAN_NAMES.values()))
            for logical, info in plan["tables"].items():
                staged = (work / "stage" / "common" / logical).read_bytes()
                self.assertEqual(G.sha256(staged), info["staged_sha256"])
                self.assertEqual(G.sha256(LIVE.raw(logical)), info["live_sha256"])
                self.assertEqual(sorted(info["changed"]), info["changed"])
            for key, info in plan["files"].items():
                staged = (work / "stage" / "common" / key).read_bytes()
                self.assertEqual(G.sha256(staged), info["staged_sha256"])
                live = LIVE.raw(key)
                self.assertEqual(None if live is None else G.sha256(live), info["live_sha256"])
            for name, info in plan["server"].items():
                staged = (work / "stage" / "server" / name).read_bytes()
                self.assertEqual(G.sha256(staged), info["staged_sha256"])
                self.assertEqual(G.sha256(LIVE.server_bytes(name)), info["live_sha256"])
        atlas_files = {A.ATLAS_PNG, A.ATLAS_MAP} & set(R1["plan"]["files"])
        self.assertIn(atlas_files, (set(), {A.ATLAS_PNG, A.ATLAS_MAP}))          # 两个图集文件必须同一条边

    def test_edges_touch_disjoint_files(self):
        sets = [set(r["plan"]["tables"]) | set(r["plan"]["files"]) | {"server:" + s for s in r["plan"]["server"]}
                for r in (R1, R2, R3)]
        self.assertFalse(sets[0] & sets[1] or sets[0] & sets[2] or sets[1] & sets[2])
        out = dict(E2, problems=[], tables={A.ATLAS_MAP: (b"", [], [])})
        A._check_disjoint(out, A.Overlay([Path(WORK.name) / "e1"]))
        if A.ATLAS_MAP in R1["plan"]["files"]:
            self.assertTrue(out["problems"])

    def test_restage_replaces_stale_plan_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / "w"
            work.mkdir()
            (work / "plan.json").write_text("{}", encoding="utf-8")
            (work / "plan.blocked.json").write_text("{}", encoding="utf-8")
            result = A.write_stage(work, LIVE, A.build_e3(LIVE))
            self.assertEqual(1, sum((work / n).is_file() for n in A.PLAN_NAMES.values()))
            self.assertTrue(Path(result["plan_path"]).is_file())

    def test_refuses_live_directories(self):
        with self.assertRaises(SystemExit):
            A.write_stage(LIVE.assets_dir / "weapon-awaken-stage", LIVE, A.build_e3(LIVE))
        self.assertFalse((LIVE.assets_dir / "weapon-awaken-stage").exists())

    def test_overlay_integrity(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit):
                A.Overlay([Path(tmp)])                                  # 没有计划文件
            source = Path(WORK.name) / "e1"
            target = Path(tmp) / "e1"
            import shutil
            shutil.copytree(source, target)
            plan = json.loads(Path(R1["plan_path"]).read_text(encoding="utf-8"))
            if plan["files"]:
                key = next(iter(plan["files"]))
                (target / "stage" / "common" / key).write_bytes(b"tampered")
                with self.assertRaises(SystemExit):
                    A.Overlay([target])
            shutil.rmtree(target)
            shutil.copytree(source, target)
            (target / "plan.blocked.json").write_text(Path(R1["plan_path"]).read_text(encoding="utf-8"),
                                                      encoding="utf-8")
            with self.assertRaises(SystemExit):
                A.Overlay([target])                                     # 两个计划文件

    def test_blocked_predecessor_blocks_dependent(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = A.build_e1(LIVE, write_art(Path(tmp) / "art", stems=[]))
            A.write_stage(Path(tmp) / "e1", LIVE, out)
            overlay = A.Overlay([Path(tmp) / "e1"])
            self.assertEqual("blocked", overlay.sources[0]["status"])
            e2 = A.build_e2(LIVE, overlay)
            self.assertEqual("blocked", A.edge_status(e2))
            self.assertTrue(any("本身是 blocked" in b for b in e2["blocked"]))



# ---------------------------------------------------------------------------
# 边 E4：作者 0928 晚修订（紫灰星铁 + 底框换图键 + 悖论文案 + 034 改价限购 + 凭证彩框 + 扭蛋说明）
# ---------------------------------------------------------------------------

E4_CACHE: dict = {}


def e4() -> dict:
    """真交付件（mod-tools/assets/weapon-awaken）+ 真 approved.json 上的 E4；一个模块只算一次（G.build 读官方档）。"""
    if "out" not in E4_CACHE:
        E4_CACHE["gacha"] = G.build(LIVE, drop_live=True)
        E4_CACHE["out"] = A.build_e4(LIVE, A.ART_DIR, drop_live=True, gacha=E4_CACHE["gacha"])
    return E4_CACHE["out"]


def load_rarity_frame_rules():
    """client-patch/item-rarity-frame-override/rules.py（补丁线在途；不在本检出时返回 None）。"""
    import importlib.util
    path = client_patch_path('item-rarity-frame-override/rules.py')
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("item_rarity_frame_override_rules_for_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RarityFrameKeyTests(unittest.TestCase):
    def test_key_is_prefix_plus_displayed_icon_path(self):
        """补丁按缩略图显示的图标路径拼键：道具 c3 与五重商店 034 的商品图 c12 是同一路径，一键两处。"""
        self.assertEqual({"rarity_frame_override_item/materials/mod/cursed/forbidden_star_steel":
                          ["item/equipment/mod/paradox/paradox_frame_bluegold"]}, A.rarity_frame_rows())
        steel = A.item_rows()[str(A.STAR_STEEL_ID)]
        self.assertEqual({A.RARITY_FRAME_PREFIX + steel[3]}, set(A.RARITY_FRAME_KEYS))
        self.assertEqual(G.STAR_STEEL_PRODUCT.icon, steel[3])
        import wf_paradox_weapon as P
        self.assertEqual(P.FRAME_BLUEGOLD, A.RARITY_FRAME_BLUEGOLD)      # 与 PARADOX Lv200 同一张蓝金框
        for key, value in A.RARITY_FRAME_KEYS.items():
            self.assertNotIn(",", value)
            self.assertFalse(value.endswith(".png") or key.endswith(".png"))

    def test_key_format_matches_patch_rules(self):
        rules = load_rarity_frame_rules()
        if rules is None:
            self.skipTest("client-patch/item-rarity-frame-override 不在本检出")
        self.assertEqual(rules.PREFIX, A.RARITY_FRAME_PREFIX)
        self.assertEqual(rules.CAPABILITY, A.RARITY_FRAME_CAP)

    def test_e2_stages_the_key_and_requires_the_frame_png(self):
        _prepare_live()
        cas = staged_rows(E2, A.CAS_LOGICAL)
        for key, row in A.rarity_frame_rows().items():
            self.assertEqual(row, cas[key])
        self.assertLessEqual({v + ".png" for v in A.RARITY_FRAME_KEYS.values()}, E2["requires"].files_present)
        self.assertEqual({k: A.RARITY_FRAME_CAP for k in A.RARITY_FRAME_KEYS}, E2["report"]["capabilities"])

    def test_missing_frame_png_blocks(self):
        _prepare_live()
        class NoFrame(G.Live):
            def raw(self, logical, root="upload"):
                if logical == A.RARITY_FRAME_BLUEGOLD + ".png":
                    return None
                return super().raw(logical, root)
        out = A.build_e2(NoFrame())
        self.assertTrue(any("底框换图" in b for b in out["blocked"]))

    def test_e2_without_awakening_cas_keeps_only_the_frame_key(self):
        _prepare_live()
        out = A.build_e2(LIVE, awakening_cas=False)
        self.assertEqual([], out["problems"])
        if A.CAS_LOGICAL in out["tables"]:
            _staged, changed, deleted = out["tables"][A.CAS_LOGICAL]
            self.assertEqual([], deleted)
            self.assertLessEqual(set(changed), set(A.RARITY_FRAME_KEYS))


class ShopFrameFixTests(_LiveCase):
    def shop(self, c13="4", reward="10000143"):
        row = list(LIVE.flat(G.SHOP_LOGICAL)["990099002"])
        row[A.SHOP_FRAME_COL], row[33] = c13, reward
        return {"990099002": row}

    def items(self, c17="5"):
        row = list(LIVE.flat(A.ITEM_LOGICAL)["10000143"])
        row[A.ITEM_RARITY_COL] = c17
        return {"10000143": row}

    def test_ticket_frame_goes_rainbow_only_c13(self):
        self.assertEqual({"990099002": ("4", "5", "10000143")}, A.SHOP_FRAME_FIXES)
        for have in ("4", "5"):
            with self.subTest(live_c13=have):
                rows, problems = A.shop_frame_fixes(self.shop(have), self.items())
                self.assertEqual([], problems)
                live_row = self.shop(have)["990099002"]
                want = rows["990099002"]
                self.assertEqual("5", want[A.SHOP_FRAME_COL])
                self.assertEqual([i for i, (a, b) in enumerate(zip(live_row, want)) if a != b],
                                 [] if have == "5" else [A.SHOP_FRAME_COL])

    def test_drift_wrong_reward_and_item_rarity_mismatch_refused(self):
        self.assertTrue(A.shop_frame_fixes(self.shop("3"), self.items())[1])          # 别人改过 c13
        self.assertTrue(A.shop_frame_fixes(self.shop(reward="999019"), self.items())[1])
        self.assertTrue(A.shop_frame_fixes(self.shop(), self.items("4"))[1])          # 道具底框不是彩虹
        self.assertTrue(A.shop_frame_fixes({}, self.items())[1])

    def test_live_ticket_item_is_rainbow(self):
        """道具表里的凭证已经是 ★5 彩虹底框（c17=5）；只有商店缩略图 c13 是金框。"""
        self.assertEqual("5", LIVE.flat(A.ITEM_LOGICAL)["10000143"][A.ITEM_RARITY_COL])
        self.assertEqual("5", staged_rows(E3, G.SHOP_LOGICAL)["990099002"][A.SHOP_FRAME_COL])


class EdgeE4Tests(_LiveCase):
    def test_no_problems_and_only_revision_keys(self):
        out = e4()
        self.assertEqual([], out["problems"])
        self.assertEqual([], out["blocked"])
        allowed = {A.ITEM_LOGICAL: {"10000311"}, A.CAS_LOGICAL: set(A.RARITY_FRAME_KEYS),
                   G.SHOP_LOGICAL: {"990099032", "990099033", "990099034", *A.SHOP_FRAME_FIXES}}
        for logical, (_staged, changed, deleted) in out["tables"].items():
            self.assertIn(logical, allowed)
            self.assertLessEqual(set(changed), allowed[logical], logical)
            self.assertEqual([], deleted)
        self.assertFalse(any(k.startswith(A.CAS_PREFIX) for k in out["tables"].get(A.CAS_LOGICAL, (b"", [], []))[1]))
        self.assertLessEqual(set(out["files"]), {A.ATLAS_PNG, A.ATLAS_MAP, G.STAR_STEEL_THUMB + ".png",
                                                 G.RICH_TEXT_BODY_LOGICAL})
        self.assertIn(set(out["files"]) & {A.ATLAS_PNG, A.ATLAS_MAP}, (set(), {A.ATLAS_PNG, A.ATLAS_MAP}))
        self.assertLessEqual(set(out["server"]), {A.SERVER_SHOP})

    def test_staged_values(self):
        out = e4()
        items = staged_rows(out, A.ITEM_LOGICAL)
        self.assertEqual("只回应诅咒与悖论之力的星铁。可代替本体突破诅咒武器与悖论武器。", items["10000311"][5])
        shop = staged_rows(out, G.SHOP_LOGICAL)
        steel = shop["990099034"]
        self.assertEqual(["10000310", "500", "10000147", "5", "2370100", "10", "(None)", ""], steel[17:25])
        self.assertEqual(("60", "60"), (steel[28], steel[29]))                        # 单次上限 / 每人限购
        self.assertNotIn("PARADOX", steel[10])
        self.assertEqual("5", shop["990099002"][A.SHOP_FRAME_COL])
        cas = staged_rows(out, A.CAS_LOGICAL)
        for key, row in A.rarity_frame_rows().items():
            self.assertEqual(row, cas[key])
        server = json.loads(out["server"][A.SERVER_SHOP][0])["99"] if A.SERVER_SHOP in out["server"] \
            else LIVE.server_json(A.SERVER_SHOP)["99"]
        self.assertEqual(60, server["990099034"]["stock"])
        self.assertEqual([{"id": 10000310, "amount": 500}, {"id": 10000147, "amount": 5}, {"id": 2370100, "amount": 10}],
                         server["990099034"]["costs"])

    def test_star_steel_art_is_the_approved_purple_grey(self):
        out = e4()
        approved = json.loads((A.ART_DIR / A.APPROVAL_NAME).read_text(encoding="utf-8"))["c3_rgba_sha256"]
        self.assertEqual("11539376bdf9e4194967efb516171c1fed971c372341df080bd51c993396a7d5",
                         approved["forbidden_star_steel"])
        self.assertEqual([], out["report"]["E1"]["approval"]["unapproved"])
        thumb = G.STAR_STEEL_THUMB + ".png"
        image = A.open_png(out["files"][thumb]["payload"]) if thumb in out["files"] else A.open_png(LIVE.raw(thumb))
        self.assertEqual(approved["forbidden_star_steel"], A.rgba_sha256(image))

    def test_gacha_note_says_paradox_class(self):
        out = e4()
        html = E4_CACHE["gacha"]["html"]
        self.assertNotIn("PARADOX", html)
        self.assertIn(f"{G.PARADOX_CLASS}登记于本扭蛋但出现概率为0%", html)
        if G.RICH_TEXT_BODY_LOGICAL in out["files"]:
            self.assertEqual(html, G.inflate_raw(out["files"][G.RICH_TEXT_BODY_LOGICAL]["payload"]))

    def test_stage_writes_one_ready_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = A.write_stage(Path(tmp) / "e4", LIVE, e4())
            self.assertFalse(result["refused"])
            self.assertEqual("ready", result["status"])
            plan = result["plan"]
            self.assertEqual("E4", plan["edge"])
            for logical, info in plan["tables"].items():
                self.assertEqual(G.sha256(LIVE.raw(logical)), info["live_sha256"])

    def test_merge_refuses_two_edges_on_one_file(self):
        one = A._edge("X")
        one["tables"][A.ITEM_LOGICAL] = (b"", ["1"], [])
        two = A._edge("Y")
        two["tables"][A.ITEM_LOGICAL] = (b"", ["2"], [])
        merged = A.merge_edges("Z", [one, two])
        self.assertTrue(any("同一文件" in p for p in merged["problems"]))
        self.assertEqual({"X": {}, "Y": {}}, merged["report"])

if __name__ == "__main__":
    unittest.main()
