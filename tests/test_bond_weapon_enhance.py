# -*- coding: utf-8 -*-
"""官方羁绊武器 8 把强化 Lv0→120（wf_bond_weapon_enhance / wf_bond_weapon_banner）的离线测试。

锁定：作者 0929 刃值规则（一个统一倍率 400/280，封顶 400%，不足 280% 的不拉到 400%）逐把数值、Lv120 强化行与四段成长、
羁绊证恰 50 / 深渊币 1494、商店阶段连续到 120、行形状（EA 126 列 / ENH 9 列 / 商店 50 列 / 类目 10 列）、客户端合法性与能力闸门（纯数据）、
无英文文案、服务端镜像与客户端行一致；暂存合同（apply_gacha.py 的 plan.json）在合成 store 上验证「只有新键、其余逐字节不变」。
fixture 只有 live 模板行；与真 store 的对照在 LiveStoreTests（没有 store 时跳过）。
"""
from __future__ import annotations

import contextlib
import copy
import dataclasses
import hashlib
import io
import json
import re
import statistics
import sys
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import wf_bond_weapon_banner as BANNER  # noqa: E402
import wf_bond_weapon_enhance as B  # noqa: E402
import wf_cursed_weapons as W  # noqa: E402
import wf_share_update_codec as X  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures/bond_weapon_enhance_templates.json"

#: 独立于生成器的期望表（作者规则 + 官方本体值）：id → (名, 本体刃%, Lv120 刃%, [(kind, 本体存储值, Lv120 存储值)])
EXPECTED = {
    "5010005": ("杜兰德尔", 160.0, 228.571, [("32", 160000, 228571), ("205", 15000, 21429)]),
    "5030005": ("马尔特", 280.0, 400.0, [("0", 280000, 400000)]),
    "5040022": ("米斯特汀", 280.0, 400.0, [("0", 280000, 400000)]),
    "5020024": ("帕拉修", 280.0, 400.0, [("34", 280000, 400000)]),
    "5070027": ("波利克斯", 110.0, 157.143, [("55", 110000, 157143)]),
    "5050026": ("太平清领", 120.0, 171.428, [("32", 30000, 42857)]),
    "5020041": ("金刚镰", 160.0, 228.571, [("33", 160000, 228571)]),
    "5060044": ("酒神权杖", 140.0, 200.0, [("34", 140000, 200000)]),
}
ICON_STEMS = {"5010005": "sword_0005", "5030005": "spear_0005", "5040022": "bow_0022", "5020024": "axe_0024",
              "5070027": "fist_0027", "5050026": "book_0026", "5020041": "axe_0041", "5060044": "staff_0044"}
LATIN = re.compile(r"[A-Za-z]")


# ---------------------------------------------------------------------------
# 合成 store（把冻结基线 + live 模板 fixture 装成 orderedmap 字节；不碰真 store）
# ---------------------------------------------------------------------------

def fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def make_tables(baseline: dict, *, extra_shop: bool = True) -> dict[str, bytes]:
    data = fixture()
    filler = ["0"] * 126
    tables = {
        B.ENH: X.pack({"5900101": X.csv_write([["120", "1", "死亡使者·终式·改", "70", "p", "1", "d", "99", "2024-10-11 12:00:00"]]),
                       "8000101": X.csv_write([["120", "1", "深渊·灰烬巨剑·觉醒", "70", "q", "1", "d", "99", "2000-01-01 00:00:00"]])}),
        B.EA: X.pack({"5900101": X.csv_write([filler, filler[:125] + ["7"]]), "8000101": X.csv_write([filler])}),
        B.ENH_STATUS: X.pack({"5900101": B.build_nested_node(B.STATUS_ROWS), "8000101": B.build_nested_node(B.STATUS_ROWS)}),
        B.ENH_SHOP: X.pack({k: X.csv_write(rows) for k, rows in data["shop_template"].items()}),
        B.ENH_CATEGORY: X.pack({k: X.csv_write(rows) for k, rows in data["category"].items()}),
        B.SOUL: X.pack({w["soul_id"]: X.csv_write(w["soul"]) for w in baseline.values()}),
        B.EQUIPMENT: X.pack({wid: X.csv_write([w["equipment"]]) for wid, w in baseline.items()}),
        B.EQUIPMENT_STATUS: X.pack({wid: B.build_nested_node(w["status"]) for wid, w in baseline.items()}),
    }
    if extra_shop:
        rows = X.unpack(tables[B.ENH_SHOP])
        rows["2001"] = X.csv_write([data["shop_template"]["591010102"][0]])
        tables[B.ENH_SHOP] = X.pack(rows)
    return tables


def make_server() -> bytes:
    """与 assets/equipment_enhancement_shop.json 同格式：单行、", " / ": " 分隔、无结尾换行。"""
    tpl = fixture()["shop_template"]["591010102"][0]
    entries = {"2001": B.server_row_from_client(tpl), "591010102": B.server_row_from_client(tpl)}
    return json.dumps(entries, ensure_ascii=False).encode("utf-8")


class FakeLive:
    """stage_payloads / stage 需要的最小 live：raw / server_bytes / store / assets_dir / cdn_root。"""

    def __init__(self, tables: dict[str, bytes], files: dict[str, bytes] | None = None, server: bytes | None = None,
                 root: Path | None = None):
        self.tables = dict(tables)
        self.files = dict(files or {})
        self.server = server
        root = root or Path(tempfile.gettempdir()) / "wf-bond-fake-live"
        self.store, self.assets_dir, self.cdn_root = root / "store" / "upload", root / "assets", root / "cdn"

    def raw(self, logical: str, root: str = "upload"):
        return self.tables.get(logical, self.files.get(logical))

    def server_bytes(self, name: str):
        return self.server if name == B.SERVER_SHOP else None

    def rows(self, logical: str):
        return X.unpack(self.tables[logical])

    def reader(self) -> W.LiveReader:
        import wf_quest_lib as Q
        return W.LiveReader(lambda logical: {k: (X.csv_read(v) if v else []) for k, v in X.unpack(self.tables[logical]).items()},
                            lambda logical: Q.parse_node(self.tables[logical]), lambda name: {})

    def after(self, payloads: dict) -> "FakeLive":
        """把 stage_payloads 的结果落进一份新的合成 store（模拟发布后再暂存）。"""
        tables = dict(self.tables)
        for logical, (staged, _added, _raw) in payloads["tables"].items():
            tables[logical] = staged
        files = dict(self.files)
        for logical, info in payloads["files"].items():
            files[logical] = info["payload"]
        server = payloads["server"][B.SERVER_SHOP]["payload"] if B.SERVER_SHOP in payloads["server"] else self.server
        return FakeLive(tables, files, server, self.store.parent.parent)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def scale_ea(w: B.Weapon, factor: float) -> B.Weapon:
    """变异：把每条强化行的强度（p1/first_max）放大 factor 倍，用来证明数值门禁会咬人。"""
    rows = []
    for row in w.ea_rows:
        row = list(row)
        c1, c2 = B.strength_cols(B.EA_T, row[5])
        row[c1], row[c2] = str(round(int(row[c1]) * factor)), str(round(int(row[c2]) * factor))
        rows.append(row)
    return dataclasses.replace(w, ea_rows=rows)


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline = B.load_baseline()
        cls.tables = make_tables(cls.baseline)
        cls.live = FakeLive(cls.tables, server=make_server())
        cls.read = cls.live.reader()
        cls.out = B.build(cls.read, baseline=cls.baseline)
        cls.weapons = {w.id: w for w in cls.out["weapons"]}
        cls.template = fixture()["shop_template"]["591010102"][0]


# ---------------------------------------------------------------------------
# 冻结基线
# ---------------------------------------------------------------------------

class BaselineTests(Base):
    def test_eight_weapons_in_general_shop_order(self):
        self.assertEqual(tuple(EXPECTED), B.WEAPON_IDS)
        self.assertEqual(list(EXPECTED), list(self.baseline))
        for wid, (name, *_rest) in EXPECTED.items():
            self.assertEqual(name, self.baseline[wid]["name"])
            self.assertEqual(ICON_STEMS[wid], self.baseline[wid]["stem"])

    def test_frozen_rows_are_the_official_bond_weapons(self):
        for wid, w in self.baseline.items():
            eq = w["equipment"]
            self.assertEqual((w["name"], "0", "1", wid, "5"), (eq[1], eq[2], eq[8], eq[10], eq[11]), wid)   # ★5、可觉醒上限 1
            self.assertTrue(eq[7].startswith("使用信赖之证兑换的绝品"), wid)
            self.assertTrue(all(len(r) == 123 for r in w["soul"]), wid)
            self.assertEqual({"1"}, set(w["status"]), wid)

    def test_no_enhancement_rows_exist_for_the_eight(self):
        for logical in (B.ENH, B.EA, B.ENH_STATUS):
            self.assertFalse(set(B.WEAPON_IDS) & set(X.unpack(self.tables[logical])), logical)

    def test_baseline_drift_detected(self):
        self.assertEqual([], B.baseline_problems(self.read, self.baseline))
        drifted = copy.deepcopy(self.baseline)
        drifted["5030005"]["soul"][0][B.strength_cols(B.SOUL_T, "1")[0]] = "281000"
        problems = B.baseline_problems(self.read, drifted)
        self.assertEqual(1, len(problems))
        self.assertIn("马尔特", problems[0])


# ---------------------------------------------------------------------------
# 刃值规则与逐把数值
# ---------------------------------------------------------------------------

class RuleTests(Base):
    def test_out_has_no_problems(self):
        self.assertEqual([], self.out["problems"])
        self.assertEqual([], self.out["icon_fallback"])
        self.assertEqual([], self.out["capabilities"])

    def test_constants_encode_the_author_rule(self):
        self.assertEqual((400, 280, Fraction(10, 7)), (B.RULE_NUM, B.RULE_DEN, B.RATIO))
        self.assertEqual(Fraction(400), B.BLADE_CAP)
        self.assertEqual(120, B.MAX_LEVEL)

    def test_per_weapon_numbers(self):
        for wid, (name, base_blade, final_blade, effects) in EXPECTED.items():
            w = self.weapons[wid]
            self.assertEqual(name, w.name)
            self.assertAlmostEqual(base_blade, w.base_blade, places=6, msg=name)
            self.assertAlmostEqual(final_blade, w.final_blade, places=6, msg=name)
            self.assertEqual([(e.kind, e.base, e.total) for e in w.effects], effects, name)
            self.assertFalse(w.capped, name)                                 # 现有 8 把没有高于 280% 的

    def test_one_uniform_multiplier(self):
        """每把 Lv120/本体 = 400/280（取整误差内），没有谁被单独拉高；不足 280% 的不到 400%。"""
        for w in self.weapons.values():
            self.assertLess(abs(w.final_blade / w.base_blade - 400 / 280), B.RATIO_TOLERANCE, w.name)
            self.assertLessEqual(w.final_blade, 400.0, w.name)
            if w.base_blade < 280:
                self.assertLess(w.final_blade, 400.0, w.name)
            else:
                self.assertEqual(400.0, w.final_blade, w.name)
        self.assertEqual({"马尔特", "米斯特汀", "帕拉修"}, {w.name for w in self.weapons.values() if w.final_blade == 400.0})
        self.assertEqual([], [w.name for w in self.weapons.values() if w.base_blade > 280])
        self.assertEqual([], [w.name for w in self.weapons.values() if w.capped])
        # 顺序不变：波利克斯 < 太平清领 < 酒神权杖 < 杜兰德尔 = 金刚镰 < 三把 400
        order = [w.name for w in sorted(self.weapons.values(), key=lambda w: (w.final_blade, w.name))]
        self.assertEqual(["波利克斯", "太平清领", "酒神权杖", "杜兰德尔", "金刚镰"], order[:5])

    def test_author_examples_280_210_140(self):
        """作者原话：280% → 400%，210% → 300%，140% → 200%（synthetic 本体行 = 帕拉修的技能伤害行改强度）。"""
        template = self.baseline["5020024"]
        col = B.strength_cols(B.SOUL_T, "0")[0]
        for base, want in ((280000, 400.0), (210000, 300.0), (140000, 200.0)):
            row = list(template["soul"][0])
            row[col], row[col + 1] = str(base), str(base)
            w = B.plan_weapon("9999999", "测试", "axe_0024", template["equipment"], [row], template["status"], "101")
            self.assertAlmostEqual(want, w.final_blade, places=6, msg=str(base))
            self.assertFalse(w.capped, str(base))
            self.assertEqual([], B.number_problems(w), str(base))

    def test_above_280_is_capped_at_400(self):
        """高于 280% 的按 400% 封顶（现有 8 把没有；生成器仍必须做对）。"""
        template = self.baseline["5020024"]
        col = B.strength_cols(B.SOUL_T, "0")[0]
        for base in (300000, 350000, 399000):
            row = list(template["soul"][0])
            row[col], row[col + 1] = str(base), str(base)
            w = B.plan_weapon("9999999", "测试", "axe_0024", template["equipment"], [row], template["status"], "101")
            self.assertTrue(w.capped, str(base))
            self.assertEqual(400.0, w.final_blade, str(base))
            self.assertEqual(400000, w.effects[0].total, str(base))
            self.assertEqual([], B.number_problems(w), str(base))
        for base in (400000, 500000):                                          # 本体已到/过封顶：拒绝生成（不出负增量）
            row = list(template["soul"][0])
            row[col], row[col + 1] = str(base), str(base)
            with self.assertRaises(B.BondError):
                B.plan_weapon("9999999", "测试", "axe_0024", template["equipment"], [row], template["status"], "101")

    def test_hp_uses_the_same_ratio_only_blade_is_capped(self):
        w = self.weapons["5010005"]
        hp = next(e for e in w.effects if e.kind == "205")
        self.assertFalse(hp.blade)
        self.assertEqual((15000, 21429), (hp.base, hp.total))
        self.assertEqual(round(15000 * 10 / 7), hp.total)

    def test_split_four_tiers(self):
        for w in self.weapons.values():
            for e in w.effects:
                a, b, c, d = (e.split[k] for k in "ABCD")
                self.assertEqual(a, c, w.name)
                self.assertEqual(e.delta, a + b + c + d, w.name)
                self.assertEqual(round(e.delta * 0.32), a, w.name)
                self.assertEqual(round(e.delta * 0.20), b, w.name)
                self.assertGreater(d, 0)
        e = self.weapons["5010005"].effects[0]
        self.assertEqual({"A": 21943, "B": 13714, "C": 21943, "D": 10971}, e.split)
        e = self.weapons["5030005"].effects[0]
        self.assertEqual({"A": 38400, "B": 24000, "C": 38400, "D": 19200}, e.split)

    def test_level_curve(self):
        w = self.weapons["5030005"]
        fractions = {lv: float(B.effect_fraction(w, 0, lv)) for lv in (0, 1, 30, 69, 70, 98, 99, 100, 110, 119, 120)}
        self.assertEqual(0.0, fractions[0])
        self.assertAlmostEqual(0.16, fractions[1], places=3)
        self.assertAlmostEqual(0.4528, fractions[70], places=3)           # B 节点
        self.assertAlmostEqual(0.8118, fractions[99], places=3)           # C 节点
        self.assertEqual(1.0, fractions[120])
        levels = sorted(fractions)
        self.assertTrue(all(fractions[a] <= fractions[b] for a, b in zip(levels, levels[1:])))
        self.assertEqual(280.0, B.blade_at(w, 0))
        self.assertEqual(400.0, B.blade_at(w, 120))
        self.assertAlmostEqual(299.2, B.blade_at(w, 1), places=1)
        self.assertAlmostEqual(334.34, B.blade_at(w, 70), places=1)
        self.assertAlmostEqual(377.42, B.blade_at(w, 99), places=1)

    def test_lv120_sum_is_exact_per_effect_at_every_level_step(self):
        for w in self.weapons.values():
            totals = B.ea_effect_totals(w.soul_rows, w.ea_rows)
            self.assertEqual([e.delta for e in w.effects], totals, w.name)
            for level in range(1, 121):                                    # 逐级：成长不会越过 Lv120 总值
                for i, e in enumerate(w.effects):
                    self.assertLessEqual(B.effect_fraction(w, i, level), 1, (w.name, level))

    def test_number_gate_bites_on_mutations(self):
        """反例必须失败：波利克斯拉到 400%、马尔特 401%、强度 ×3、HP 不缩放。"""
        for w in self.weapons.values():
            self.assertEqual([], B.number_problems(w), w.name)
        polyx = self.weapons["5070027"]
        pulled = scale_ea(polyx, (400 - 110) / 47.143)
        self.assertAlmostEqual(400.0, B.W.weapon_budget(pulled.soul_rows, pulled.ea_rows, {}, {})["blades"], delta=0.05)
        self.assertTrue(B.number_problems(pulled))
        malt = self.weapons["5030005"]
        over = scale_ea(malt, (401 - 280) / 120)
        problems = B.number_problems(over)
        self.assertTrue(any("超过封顶" in p for p in problems), problems)
        self.assertTrue(B.number_problems(scale_ea(self.weapons["5060044"], 3)))
        durandal = self.weapons["5010005"]
        rows = [list(r) for r in durandal.ea_rows]
        hp_col = B.strength_cols(B.EA_T, "0")
        for r in rows:
            if int(r[0]) % 2 == 1:                                          # HP 行不缩放：全部改回 0 → HP 总值 = 本体
                r[hp_col[0]] = r[hp_col[1]] = "0"
        self.assertTrue(any("效果#1" in p for p in B.number_problems(dataclasses.replace(durandal, ea_rows=rows))))
        rows = [r for r in durandal.ea_rows if int(r[0]) % 2 == 0]           # 少一半行
        self.assertTrue(B.number_problems(dataclasses.replace(durandal, ea_rows=rows)))

    def test_no_new_multiplier_and_no_unbounded(self):
        for w in self.weapons.values():
            full = B.W.weapon_budget(w.soul_rows, w.ea_rows, {}, {})
            self.assertEqual(0, full["multipliers"], w.name)
            self.assertEqual([], full["unbounded"], w.name)

    def test_table_report(self):
        rows = {r["id"]: r for r in B.weapon_table(self.out)}
        self.assertEqual(8, len(rows))
        self.assertEqual([577, 215], rows["5010005"]["hp_atk_before"])
        self.assertEqual([577, 215], rows["5010005"]["hp_atk_lv120"])          # 作者 0929「白值不加」
        self.assertEqual([709, 189], rows["5040022"]["hp_atk_before"])
        self.assertEqual([709, 189], rows["5040022"]["hp_atk_lv120"])
        for r in rows.values():
            self.assertEqual((1494, 50), (r["coin_total"], r["token_total"]))
        text = B.render_table(list(rows.values()))
        self.assertIn("| 波利克斯 | 5070027 | 110% | 157.143% | 157.143% | 否 |", text)


# ---------------------------------------------------------------------------
# 强化行 / ENH / STATUS 形状
# ---------------------------------------------------------------------------

class RowShapeTests(Base):
    def test_ea_rows_are_clones_of_the_soul_rows(self):
        for w in self.weapons.values():
            n = len(w.soul_rows)
            self.assertEqual(4 * n, len(w.ea_rows), w.name)
            self.assertEqual(list(range(4 * n)), [int(r[0]) for r in w.ea_rows], w.name)
            for r in w.ea_rows:
                self.assertEqual(126, len(r), w.name)
                soul = w.soul_rows[int(r[0]) % n]
                c1, c2 = B.strength_cols(B.EA_T, r[5])
                s1, s2 = B.strength_cols(B.SOUL_T, soul[2])
                self.assertEqual((c1, c2), (s1 + 3, s2 + 3))
                self.assertEqual(soul[2:s1] + soul[s2 + 1:], r[5:c1] + r[c2 + 1:], w.name)   # 除强度两格外逐格 = 本体行
                self.assertEqual(soul[2], r[5])                                       # 瞬发/持续模式保持

    def test_tier_rules(self):
        tiers = {"A": (1, 120, "24", "48"), "B": (70, 120, "24", "24"), "C": (99, 120, "48", "48"), "D": (100, 120, "2", "24")}
        for w in self.weapons.values():
            n = len(w.soul_rows)
            for t, (name, learn_max_bp) in enumerate(tiers.items()):
                for i in range(n):
                    r = w.ea_rows[t * n + i]
                    c1, c2 = B.strength_cols(B.EA_T, r[5])
                    self.assertEqual((str(learn_max_bp[0]), str(learn_max_bp[1]), learn_max_bp[2], learn_max_bp[3]),
                                     (r[1], r[2], r[3], r[4]), (w.name, name))
                    fm = w.effects[i].split[name]
                    self.assertEqual(str(fm), r[c2])
                    want_p1 = {"A": (fm + 1) // 2, "B": fm, "C": fm, "D": (2 * fm + 10) // 20}[name]     # 半值 / 恒值 / 十分之一（四舍五入）
                    self.assertEqual(want_p1, int(r[c1]), (w.name, name))
                    if name in "BC":                                   # 恒值节点：learn < max 时 p1 == first_max 才是常数
                        self.assertEqual(r[c1], r[c2])

    def test_ea_rule_c14510_c14511_c14512(self):
        for w in self.weapons.values():
            for r in w.ea_rows:
                c1, c2 = B.strength_cols(B.EA_T, r[5])
                learn, mx = int(r[1]), int(r[2])
                self.assertGreaterEqual(learn, 1)                                # C14512
                self.assertLessEqual(learn, mx)                                  # C14511
                if learn == mx:
                    self.assertEqual(r[c1], r[c2])                                # C14510
                self.assertEqual(120, mx)

    def test_during_weapons_keep_during_layout(self):
        """马尔特/米斯特汀的效果是持续行（触发 30/31）：强度在持续块，瞬发块为空。"""
        for wid in ("5030005", "5040022"):
            for r in self.weapons[wid].ea_rows:
                self.assertEqual("1", r[5])
                self.assertEqual(B.strength_cols(B.EA_T, "1"), (113, 114))
        for wid in ("5010005", "5020024", "5070027", "5050026", "5020041", "5060044"):
            for r in self.weapons[wid].ea_rows:
                self.assertEqual("0", r[5])
                self.assertEqual(B.strength_cols(B.EA_T, "0"), (51, 52))

    def test_taiping_trigger_and_limit_untouched(self):
        w = self.weapons["5050026"]
        for r in w.ea_rows:
            self.assertEqual(w.soul_rows[0][24:32], r[27:35])                         # 触发块（技能发动≥1 + 次数上限 4）逐格 = 本体行
            self.assertEqual(("23", "4"), (r[27], r[34]))                             # 触发「技能发动」、次数上限 4 不动
        full = B.W.weapon_budget(w.soul_rows, w.ea_rows, {}, {})
        self.assertAlmostEqual(171.428, full["blades"], places=3)

    def test_legality_and_no_capability(self):
        import wf_client_legality as L
        for w in self.weapons.values():
            for i, r in enumerate(w.ea_rows):
                self.assertEqual([], L.client_legality_problems(B.EA_T, r), (w.name, i))
                self.assertEqual([], L.required_client_capabilities(B.EA_T, r), (w.name, i))

    def test_kinds_are_plain_stat_kinds(self):
        allowed = {"0", "32", "33", "34", "55", "205"}
        for w in self.weapons.values():
            for r in w.ea_rows:
                self.assertIn(B.row_kind(B.EA_T, r), allowed, w.name)

    def test_enh_row(self):
        for wid, w in self.weapons.items():
            row = self.out["flat"][B.ENH][wid][0]
            eq = self.baseline[wid]["equipment"]
            self.assertEqual(9, len(row))
            self.assertEqual(["120", "1", eq[1] + "·改", "70", f"item/equipment/mod/bond/{ICON_STEMS[wid]}_lv120", "1", eq[7], "99",
                              "2000-01-01 00:00:00"], row)
            self.assertLessEqual(len(row[6]), W.DESC_LIMITS["enhancement"])
            self.assertNotIn(",", row[6])
            self.assertNotIn("\n", row[6])
            self.assertEqual(eq[7], row[6])                                       # 官方：强化前后说明原文不变

    def test_status_rows(self):
        for wid in EXPECTED:
            status = self.out["nested"][B.ENH_STATUS][wid]
            self.assertEqual({"98": "0,0", "99": "0,0", "120": "0,0"}, status)
            self.assertEqual(int(self.out["flat"][B.ENH][wid][0][0]), max(map(int, status)))   # 末键 == ENH c0（Lv121+ 空引用崩）
            self.assertEqual(list(status), sorted(status, key=int))

    def test_white_stats_are_not_raised(self):
        """作者 0929「白值不加」：Lv120 的 HP/ATK 等于本体（只强化词条）。"""
        for r in B.weapon_table(self.out):
            self.assertEqual(r["hp_atk_before"], r["hp_atk_lv120"], r["id"])

    def test_status_alternatives_cover_flat_and_ratio(self):
        alts = {a["id"]: a for a in B.status_alternatives(self.out)}
        self.assertEqual(set(EXPECTED), set(alts))
        self.assertEqual([709, 189], alts["5040022"]["base"])
        self.assertEqual([709, 189], alts["5040022"]["flat"])             # 白值不加：现行 = 本体
        self.assertEqual([1013, 270], alts["5040022"]["ratio"])          # 709 × 10/7、189 × 10/7
        self.assertEqual([754, 321], alts["5020024"]["ratio"])            # 528 × 10/7、225 × 10/7
        self.assertEqual([0.0, 0.0], alts["5020024"]["flat_pct"])
        self.assertTrue(all(a["ratio"][1] > B.ATK_REDLINE for a in alts.values()))
        self.assertTrue(all(a["flat"][1] <= B.ATK_REDLINE for a in alts.values()))

    def test_require_awakening_is_one(self):
        self.assertEqual("1", B.REQUIRE_AWAKENING)
        for key, rows in self.out["flat"][B.ENH_SHOP].items():
            self.assertEqual("1", rows[0][31], key)
        for key, row in self.out["server"][B.SERVER_SHOP].items():
            self.assertEqual(1, row["requireAwakeningLevel"], key)


# ---------------------------------------------------------------------------
# 成本 / 商店 / 类目 / 服务端
# ---------------------------------------------------------------------------

class CostAndShopTests(Base):
    def test_stage_caps_contiguous_to_120(self):
        stages = self.out["stages"]
        self.assertEqual((69, 70, 98, 99, 119, 120), tuple(s["cap"] for s in stages))
        self.assertEqual([69, 1, 28, 1, 20, 1], [s["levels"] for s in stages])
        self.assertEqual(120, sum(s["levels"] for s in stages))
        self.assertEqual([1, 70, 71, 99, 100, 120], [s["from"] for s in stages])
        self.assertEqual([], B.cost_problems(stages))

    def test_token_total_is_fifty_and_only_on_single_level_nodes(self):
        stages = self.out["stages"]
        self.assertEqual(50, sum(s["token_total"] for s in stages))
        self.assertEqual({70: 10, 99: 15, 120: 25}, {s["cap"]: s["token_per_unit"] for s in stages if s["token_per_unit"]})
        self.assertTrue(all(s["levels"] == 1 for s in stages if s["token_per_unit"]))

    def test_coin_total(self):
        stages = self.out["stages"]
        self.assertEqual(1494, sum(s["coin_total"] for s in stages))
        self.assertEqual([828, 30, 336, 30, 240, 30], [s["coin_total"] for s in stages])
        self.assertEqual((12, 30), (B.COIN_PER_LEVEL, B.COIN_PER_NODE))
        self.assertEqual(round(B.ABYSS_WEAPON_COIN * 0.4), B.COIN_TOTAL)          # 深渊武装每把 3735 的 40%
        self.assertAlmostEqual(9.64, B.COIN_TOTAL / B.FULL_CLEAR_COIN, places=2)

    def test_cost_gate_bites(self):
        stages = B.stage_costs()
        bad = copy.deepcopy(stages)
        bad[2]["token_per_unit"], bad[2]["token_total"] = 1, 28
        self.assertTrue(B.cost_problems(bad))                                     # 多级阶段放羁绊证
        bad = copy.deepcopy(stages)
        bad[1]["token_total"] = 9
        self.assertTrue(any("羁绊证合计" in p for p in B.cost_problems(bad)))
        bad = copy.deepcopy(stages)
        bad[1]["from"] = 71
        self.assertTrue(any("空档" in p for p in B.cost_problems(bad)))
        bad = copy.deepcopy(stages)
        bad[-1]["cap"] = 121
        self.assertTrue(B.cost_problems(bad))

    def test_shop_rows_per_weapon(self):
        shop = self.out["flat"][B.ENH_SHOP]
        self.assertEqual(48, len(shop))
        for i, (wid, w) in enumerate(self.weapons.items(), start=1):
            keys = [f"{wid}{s:02d}" for s in range(1, 7)]
            self.assertEqual(keys, w.shop_ids)
            self.assertEqual(str(100 + i), w.list_order)
            coin_total = token_total = 0
            prev = 0
            for stage, key in enumerate(keys, start=1):
                row = shop[key][0]
                self.assertEqual(50, len(row))
                self.assertEqual(("7", wid, str(stage), "1", w.list_order), (row[0], row[2], row[3], row[4], row[5]))
                self.assertEqual((wid, str(B.STAGE_CAPS[stage - 1]), "1"), (row[29], row[30], row[31]))
                self.assertEqual(("2000-01-01 00:00:00", "(None)", "90"), (row[22], row[23], row[24]))
                self.assertEqual(B.ABYSS_COIN, row[14])
                self.assertEqual(["(None)", ""] * 3, row[16:22])                    # 只收深渊币一种材料
                levels = B.STAGE_CAPS[stage - 1] - prev
                prev = B.STAGE_CAPS[stage - 1]
                coin_total += int(row[15]) * levels
                if row[11] != "(None)":
                    self.assertEqual("2", row[11])                                # PriceKind.BondToken
                    token_total += int(row[12]) * levels
                else:
                    self.assertEqual("", row[12])
            self.assertEqual((1494, 50), (coin_total, token_total), w.name)
            self.assertLess(int(keys[-1]), 2 ** 31)

    def test_shop_rows_only_differ_from_the_template_in_builder_columns(self):
        for key, rows in self.out["flat"][B.ENH_SHOP].items():
            same = [i for i in range(50) if i not in B.SHOP_TEMPLATE_FILLED and i not in (11, 12)]
            self.assertEqual([self.template[i] for i in same], [rows[0][i] for i in same], key)

    def test_template_gate_bites(self):
        self.assertEqual([], B.template_problems(self.template))
        dirty = list(self.template)
        dirty[26] = "leak"
        self.assertTrue(B.template_problems(dirty))
        self.assertTrue(B.template_problems(self.template[:-1]))

    def test_shop_keys_do_not_collide_with_live_shop(self):
        live = set(X.unpack(self.tables[B.ENH_SHOP]))
        self.assertFalse(live & set(self.out["flat"][B.ENH_SHOP]))

    def test_server_rows_mirror_client_rows(self):
        server = self.out["server"][B.SERVER_SHOP]
        shop = self.out["flat"][B.ENH_SHOP]
        self.assertEqual(set(shop), set(server))
        for key, rows in shop.items():
            row, srv = rows[0], server[key]
            self.assertEqual(int(row[29]), srv["equipmentId"])
            self.assertEqual(int(row[2]), srv["groupId"])                           # group = 武器 ID（服务端只按 groupId 分组）
            self.assertEqual(int(row[30]), srv["enhancementMaxLevel"])
            self.assertEqual(int(row[3]), srv["stage"])
            self.assertEqual(7, srv["shopCategoryId"])
            self.assertEqual([{"id": 2370099, "amount": int(row[15])}], srv["costs"])
            self.assertEqual(("2000-01-01 00:00:00", None, -1, []), (srv["availableFrom"], srv["availableUntil"], srv["stock"], srv["rewards"]))
            if row[11] == "2":
                self.assertEqual({"type": 2, "amount": int(row[12])}, srv["userCost"])
            else:
                self.assertNotIn("userCost", srv)

    def test_server_totals(self):
        server = self.out["server"][B.SERVER_SHOP]
        for wid in EXPECTED:
            prev = coin = token = 0
            for stage in range(1, 7):
                s = server[f"{wid}{stage:02d}"]
                levels = s["enhancementMaxLevel"] - prev
                prev = s["enhancementMaxLevel"]
                coin += s["costs"][0]["amount"] * levels
                token += s.get("userCost", {}).get("amount", 0) * levels
            self.assertEqual((1494, 50), (coin, token), wid)
            self.assertEqual(120, prev)

    def test_server_row_key_order_matches_live_style(self):
        """服务端行键序 = 字母序（与 live 里诅咒线一致），userCost 在末尾（先例 general_shop 100001–100008 的写法）。"""
        for srv in self.out["server"][B.SERVER_SHOP].values():
            keys = [k for k in srv if k != "userCost"]
            self.assertEqual(sorted(keys), keys)
            if "userCost" in srv:
                self.assertEqual("userCost", list(srv)[-1])

    def test_category_row(self):
        row = self.out["flat"][B.ENH_CATEGORY]["7"][0]
        tpl = fixture()["category"]["6"][0]
        self.assertEqual(10, len(row))
        self.assertEqual(["bond_weapon", "0", "(None)", "羁绊武器·觉醒", "dynamic/equipment_enhancement/bond_weapon_banner",
                          "dynamic/equipment_enhancement/bond_weapon_header", tpl[6], tpl[7], "2000-01-01 00:00:00", "(None)"], row)
        self.assertEqual(fixture()["category"]["2"][0][6:8], row[6:8])                 # c6/c7 = 官方歼灭类目已验证存在的值（自造 = C8601）

    def test_category_order_is_distinct_integers_and_sequence(self):
        orders = {k: int(v[0][1]) for k, v in fixture()["category"].items()}
        orders["7"] = int(self.out["flat"][B.ENH_CATEGORY]["7"][0][1])
        self.assertEqual(len(orders), len(set(orders.values())))
        self.assertEqual(["6", "5", "7", "1", "2", "3", "4"], sorted(orders, key=orders.get))

    def test_category_order_module_is_consistent(self):
        import wf_enhancement_category_order as CO
        self.assertEqual((B.CATEGORY_C0, B.CATEGORY_ORDER), CO.ORDER[B.CATEGORY_KEY])
        self.assertEqual(("6", "5", "7", "1", "2", "3", "4"), CO.EXPECTED_SEQUENCE)
        live = {k: v[0] for k, v in fixture()["category"].items()}
        staged = {**live, "7": self.out["flat"][B.ENH_CATEGORY]["7"][0]}
        upsert, problems = CO.target_rows(staged)
        self.assertEqual([], problems)
        self.assertEqual({}, upsert)                                              # live 的 5/6 已在目标位，7 由本生成器直接写 c1 = 0

    def test_category_collision_refused(self):
        tables = dict(self.tables)
        rows = X.unpack(tables[B.ENH_CATEGORY])
        rows["7"] = X.csv_write([["something_else", "7", "(None)", "x", "a", "b", "c", "d", "2000-01-01 00:00:00", "(None)"]])
        tables[B.ENH_CATEGORY] = X.pack(rows)
        out = B.build(FakeLive(tables).reader(), baseline=self.baseline)
        self.assertTrue(any("类目 7 已存在" in p for p in out["problems"]), out["problems"])

    def test_category_order_collision_refused(self):
        tables = dict(self.tables)
        rows = X.unpack(tables[B.ENH_CATEGORY])
        five = X.csv_read(rows["1"])[0]
        five[1] = "0"                                                             # 官方类目 1 占了 0：羁绊会撞值
        rows["1"] = X.csv_write([five])
        tables[B.ENH_CATEGORY] = X.pack(rows)
        out = B.build(FakeLive(tables).reader(), baseline=self.baseline)
        self.assertTrue(any("重复" in p for p in out["problems"]), out["problems"])


# ---------------------------------------------------------------------------
# 文案：没有英文
# ---------------------------------------------------------------------------

class TextTests(Base):
    def test_no_latin_letters_in_player_visible_text(self):
        texts = []
        for row in (r[0] for r in self.out["flat"][B.ENH].values()):
            texts += [row[2], row[6]]                                             # 强化名 / 说明
        texts += [self.out["flat"][B.ENH_CATEGORY]["7"][0][3], BANNER.TITLE, BANNER.SUBTITLE]
        for text in texts:
            self.assertIsNone(LATIN.search(text), text)
        self.assertEqual("羁绊武器·觉醒", BANNER.TITLE)

    def test_names_have_the_suffix_and_the_base_name(self):
        for wid, (name, *_r) in EXPECTED.items():
            self.assertEqual(name + "·改", self.out["flat"][B.ENH][wid][0][2])
        self.assertEqual("\u00b7", B.NAME_SUFFIX[0])                              # 机兵「·改」，半角中点 U+00B7


# ---------------------------------------------------------------------------
# 图标 / 横幅
# ---------------------------------------------------------------------------

class IconTests(Base):
    def test_committed_icons_pass_the_hard_gate(self):
        for stem in ICON_STEMS.values():
            self.assertEqual([], B.icon_problems(stem), stem)
        self.assertEqual({f"{stem}_lv120.png" for stem in ICON_STEMS.values()}, {p.name for p in B.ART.glob("*_lv120.png")})
        self.assertEqual({f"{stem}.png" for stem in ICON_STEMS.values()},
                         {p.name for p in B.ART.glob("*.png") if p.stem in set(ICON_STEMS.values())})      # 官方原图 8 张（门禁的对照物）

    def test_icon_files_are_staged_at_the_logical_paths(self):
        files = self.out["files"]
        want = {f"item/equipment/mod/bond/{stem}_lv120.png" for stem in ICON_STEMS.values()}
        want |= {B.BANNER + ".png", B.HEADER + ".png"}
        self.assertEqual(want, set(files))
        for wid, stem in ICON_STEMS.items():
            self.assertEqual(f"{self.out['flat'][B.ENH][wid][0][4]}.png", f"{B.ICON_DIR}/{stem}_lv120.png")

    def test_gate_rejects_bad_icons(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            art = Path(tmp)
            for name in list(B.ART.glob("*.png")):
                (art / name.name).write_bytes(name.read_bytes())
            self.assertEqual([], B.icon_problems("axe_0024", art))
            (art / "axe_0024_lv120.png").unlink()                                          # 缺图
            self.assertTrue(any("缺失" in p for p in B.icon_problems("axe_0024", art)))
            Image.new("RGBA", (21, 20), (255, 0, 0, 255)).save(art / "axe_0024_lv120.png")   # 尺寸
            self.assertTrue(any("20×20" in p for p in B.icon_problems("axe_0024", art)))
            Image.new("RGB", (20, 20), (255, 0, 0)).save(art / "axe_0024_lv120.png")         # 模式
            self.assertTrue(B.icon_problems("axe_0024", art))
            im = Image.new("RGBA", (20, 20), (0, 0, 0, 0))
            im.putpixel((0, 0), (255, 255, 255, 255))
            im.putpixel((1, 0), (255, 255, 255, 100))                                        # 原图没有的半透明值
            im.save(art / "axe_0024_lv120.png")
            self.assertTrue(any("半透明" in p for p in B.icon_problems("axe_0024", art)))
            Image.new("RGBA", (20, 20), (9, 9, 9, 255)).save(art / "axe_0024_lv120.png")     # 没有 0 alpha
            self.assertTrue(any("alpha 极值" in p for p in B.icon_problems("axe_0024", art)))
            (art / "axe_0024_lv120.png").write_bytes((art / "axe_0024.png").read_bytes())    # 与原图相同 = 没改图
            self.assertTrue(any("没有改图" in p for p in B.icon_problems("axe_0024", art)))

    def test_any_bad_icon_falls_the_whole_batch_back_to_base_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            art = Path(tmp)
            for name in list(B.ART.glob("*.png")):
                (art / name.name).write_bytes(name.read_bytes())
            (art / "staff_0044_lv120.png").unlink()
            out = B.build(self.read, baseline=self.baseline, art_dir=art)
            self.assertEqual([], out["problems"])
            self.assertTrue(out["icon_fallback"])
            for wid, w in self.baseline.items():
                self.assertEqual(w["equipment"][6], out["flat"][B.ENH][wid][0][4])        # 退回本体图标路径
            self.assertEqual({B.BANNER + ".png", B.HEADER + ".png"}, set(out["files"]))    # 不出 8 张 Lv120 图
            # 其余数据不变
            self.assertEqual(self.out["flat"][B.ENH_SHOP], out["flat"][B.ENH_SHOP])
            self.assertEqual(self.out["flat"][B.EA], out["flat"][B.EA])

    def test_base_icon_mode_keeps_base_paths_and_ships_no_icon_png(self):
        """--icons base（分享包退路）：c4 = 本体图标路径、不出 8 张独立 PNG；图标门照常检查，横幅照常出，其余数据逐格不变。"""
        out = B.build(self.read, baseline=self.baseline, icon_mode="base")
        self.assertEqual([], out["problems"])
        self.assertEqual([], out["icon_fallback"])                                # 没有图标问题：是主动选的
        self.assertEqual("base", out["icon_mode"])
        self.assertEqual("new", self.out["icon_mode"])
        self.assertEqual({B.BANNER + ".png", B.HEADER + ".png"}, set(out["files"]))
        for wid, w in self.baseline.items():
            new_row, base_row = self.out["flat"][B.ENH][wid][0], out["flat"][B.ENH][wid][0]
            self.assertEqual(w["equipment"][6], base_row[4])
            self.assertEqual(new_row[:4] + new_row[5:], base_row[:4] + base_row[5:])   # 只有 c4 不同
        for logical in (B.EA, B.ENH_STATUS, B.ENH_SHOP, B.ENH_CATEGORY):
            self.assertEqual(self.out["flat"].get(logical), out["flat"].get(logical))
        self.assertEqual(self.out["nested"], out["nested"])
        self.assertEqual(self.out["server"], out["server"])
        with self.assertRaises(B.BondError):
            B.build(self.read, baseline=self.baseline, icon_mode="none")

    def test_base_icon_mode_still_checks_the_icon_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            art = Path(tmp)
            for name in list(B.ART.glob("*.png")):
                (art / name.name).write_bytes(name.read_bytes())
            (art / "staff_0044_lv120.png").unlink()
            out = B.build(self.read, baseline=self.baseline, art_dir=art, icon_mode="base")
            self.assertTrue(out["icon_fallback"])                                     # 门禁问题照报
            self.assertEqual("base", out["icon_mode"])

    def test_cli_icons_flag(self):
        for cmd in ("check", "table", "stage"):
            argv = [cmd, "wd"] if cmd == "stage" else [cmd]
            self.assertEqual("new", B.build_parser().parse_args(argv).icons)
            self.assertEqual("base", B.build_parser().parse_args(argv + ["--icons", "base"]).icons)
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            B.build_parser().parse_args(["check", "--icons", "old"])

    def test_missing_banner_is_a_problem(self):
        with tempfile.TemporaryDirectory() as tmp:
            art = Path(tmp)
            for name in list(B.ART.glob("*_lv120.png")) + list(B.ART.glob("[a-z]*_[0-9]*.png")):
                (art / name.name).write_bytes(name.read_bytes())
            out = B.build(self.read, baseline=self.baseline, art_dir=art)
            self.assertTrue(any("缺横幅图" in p for p in out["problems"]), out["problems"])

    def test_banner_sizes_and_committed_images(self):
        for logical, size in ((B.BANNER, (1000, 184)), (B.HEADER, (1440, 556))):
            self.assertEqual([], B.banner_problems())
            from PIL import Image
            with Image.open(B.ART / (logical.rsplit("/", 1)[-1] + ".png")) as im:
                self.assertEqual((size, "RGBA"), (im.size, im.mode))

    def test_committed_banner_matches_a_fresh_render(self):
        if not Path(BANNER.abyss.FONT_BOLD).is_file() or not Path(BANNER.abyss.FONT).is_file():
            self.skipTest("本机没有横幅字体")
        banner, header = BANNER.render()
        from PIL import Image
        for image, name in ((banner, BANNER.BANNER_FILE), (header, BANNER.HEADER_FILE)):
            with Image.open(B.ART / name) as committed:
                self.assertEqual(image.size, committed.size)
                self.assertEqual(image.convert("RGBA").tobytes(), committed.convert("RGBA").tobytes(), name)

    def test_stale_banner_is_refused(self):
        """图标改了而横幅没重出：暂存前必须拦下（画图单元评审发现：暂存目录曾有旧版图，没有门禁拦）。"""
        if not Path(BANNER.abyss.FONT_BOLD).is_file() or not Path(BANNER.abyss.FONT).is_file():
            self.skipTest("本机没有横幅字体")
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            art = Path(tmp)
            for name in list(B.ART.glob("*.png")):
                (art / name.name).write_bytes(name.read_bytes())
            self.assertEqual([], B.banner_stale_problems(art))
            im = Image.open(art / "bow_0022_lv120.png").convert("RGBA")
            im.putpixel((10, 10), (1, 2, 3, 255))                                         # 改一个像素 = 图标换了版
            im.save(art / "bow_0022_lv120.png")
            problems = B.banner_stale_problems(art)
            self.assertEqual(2, len(problems), problems)
            self.assertTrue(all("重跑" in p for p in problems))
            live = FakeLive(self.tables, server=make_server())
            result = B.stage(art / "work", live, live.reader(), baseline=self.baseline, art_dir=art)
            self.assertTrue(result["refused"])
            self.assertFalse((art / "work").exists())

    def test_source_hashes_cover_every_staged_png(self):
        hashes = B.source_hashes()
        self.assertEqual(8 * 2 + 2, len(hashes))
        for logical in self.out["files"]:
            name = logical.rsplit("/", 1)[-1]
            self.assertEqual(hashlib.sha256((B.ART / name).read_bytes()).hexdigest(), hashes[name])

    def test_banner_text_is_chinese_only(self):
        self.assertIsNone(LATIN.search(BANNER.TITLE + BANNER.SUBTITLE))


# ---------------------------------------------------------------------------
# 暂存合同（apply_gacha.py 的 plan.json）
# ---------------------------------------------------------------------------

class StageTests(Base):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.payloads = B.stage_payloads(cls.live, cls.out)

    def test_no_problems_and_expected_scope(self):
        self.assertEqual([], self.payloads["problems"])
        self.assertEqual(set(B.CLIENT_TABLES), set(self.payloads["tables"]))
        self.assertEqual(10, len(self.payloads["files"]))
        self.assertEqual({B.SERVER_SHOP}, set(self.payloads["server"]))

    def test_only_new_keys_and_old_bytes_identical(self):
        for logical, (staged, added, raw) in self.payloads["tables"].items():
            old, new = X.unpack(raw), X.unpack(staged)
            self.assertEqual(list(old), list(new)[:len(old)], logical)              # 既有键顺序不变
            self.assertTrue(all(new[k] == v for k, v in old.items()), logical)      # 既有键逐字节不变
            self.assertEqual(added, list(new)[len(old):], logical)
            self.assertFalse(set(added) & set(old), logical)
        counts = {logical.rsplit("/", 1)[-1]: len(v[1]) for logical, v in self.payloads["tables"].items()}
        self.assertEqual({"equipment_enhancement.orderedmap": 8, "equipment_enhancement_ability.orderedmap": 8,
                          "equipment_enhancement_status.orderedmap": 8, "equipment_enhancement_shop.orderedmap": 48,
                          "equipment_enhancement_shop_category.orderedmap": 1}, counts)

    def test_staged_rows_decode_to_the_target_rows(self):
        import wf_quest_lib as Q
        for logical, (staged, added, _raw) in self.payloads["tables"].items():
            rows = X.unpack(staged)
            for key in added:
                if logical in self.out["nested"]:
                    self.assertEqual(self.out["nested"][logical][key], Q.parse_node(rows[key]))
                else:
                    self.assertEqual(self.out["flat"][logical][key], X.csv_read(rows[key]))

    def test_nested_rows_are_byte_identical_to_live_convention(self):
        """内层 map 全用 zlib 最高压缩级（live 现有行如此）：同内容 → 同字节。"""
        raw = X.unpack(self.tables[B.ENH_STATUS])["5900101"]
        import wf_quest_lib as Q
        self.assertEqual(raw, B.build_nested_node(Q.parse_node(raw)))
        self.assertEqual(B.build_nested_node(B.STATUS_ROWS), X.unpack(self.payloads["tables"][B.ENH_STATUS][0])["5010005"])

    def test_png_payloads(self):
        import wf_assets as A
        from PIL import Image
        import io
        for logical, info in self.payloads["files"].items():
            self.assertIsNone(info["live_sha256"], logical)                          # 全是新文件
            with Image.open(io.BytesIO(A.png_decode(info["payload"]))) as im:
                expected = (20, 20) if "/bond/" in logical else B.BANNER_SIZE if logical.endswith("banner.png") else B.HEADER_SIZE
                self.assertEqual((expected, "RGBA"), (im.size, im.mode), logical)
            self.assertEqual(b"png", info["payload"][1:4])                            # store 里 PNG 魔数小写

    def test_server_splice_keeps_existing_text(self):
        old = self.live.server.decode("utf-8")
        new = self.payloads["server"][B.SERVER_SHOP]["payload"].decode("utf-8")
        self.assertTrue(new.startswith(old[:-1]))                                    # 既有条目原文逐字节不变
        self.assertTrue(new.endswith("}"))
        merged = json.loads(new)
        self.assertEqual(2 + 48, len(merged))
        self.assertEqual(self.out["server"][B.SERVER_SHOP], {k: v for k, v in merged.items() if k in self.out["server"][B.SERVER_SHOP]})
        self.assertEqual(sorted(self.out["server"][B.SERVER_SHOP]), sorted(self.payloads["server"][B.SERVER_SHOP]["added"]))
        self.assertEqual(json.loads(old), {k: merged[k] for k in json.loads(old)})

    def test_restaging_after_publish_is_empty(self):
        live2 = self.live.after(self.payloads)
        out2 = B.build(live2.reader(), baseline=self.baseline)
        self.assertEqual([], out2["problems"])
        again = B.stage_payloads(live2, out2)
        self.assertEqual({"problems": [], "tables": {}, "files": {}, "server": {}}, again)

    def test_own_key_drift_is_refused(self):
        live2 = self.live.after(self.payloads)
        rows = X.unpack(live2.tables[B.ENH_SHOP])
        row = X.csv_read(rows["501000502"])
        row[0][12] = "11"                                                             # 有人改了羁绊证价格
        rows["501000502"] = X.csv_write(row)
        live2.tables[B.ENH_SHOP] = X.pack(rows)
        out2 = B.build(live2.reader(), baseline=self.baseline)
        again = B.stage_payloads(live2, out2)
        self.assertTrue(any("501000502" in p and "内容不同" in p for p in again["problems"]), again["problems"])
        server = json.loads(live2.server.decode("utf-8"))
        server["501000502"]["stock"] = 5
        live3 = FakeLive(live2.tables, live2.files, json.dumps(server, ensure_ascii=False).encode("utf-8"))
        again = B.stage_payloads(live3, B.build(live3.reader(), baseline=self.baseline))
        self.assertTrue(any("501000502" in p and "内容不同" in p for p in again["problems"]), again["problems"])

    def test_stage_writes_apply_gacha_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / "bond"
            result = B.stage(work, self.live, self.read, baseline=self.baseline)
            self.assertFalse(result["refused"], result)
            plan = json.loads((work / "plan.json").read_text(encoding="utf-8"))
            self.assertEqual({"tables", "files", "server", "deleted"}, set(plan))
            self.assertEqual({}, plan["deleted"])
            self.assertEqual(set(B.CLIENT_TABLES), set(plan["tables"]))
            for logical, info in plan["tables"].items():
                staged = (work / "stage/common" / logical).read_bytes()
                self.assertEqual(sha(staged), info["staged_sha256"])
                self.assertEqual(sha(self.live.raw(logical)), info["live_sha256"])
                self.assertEqual(sorted(info["changed"]), sorted(set(X.unpack(staged)) - set(X.unpack(self.live.raw(logical)))))
            self.assertEqual(10, len(plan["files"]))
            for logical, info in plan["files"].items():
                self.assertIsNone(info["live_sha256"])
                self.assertEqual(sha((work / "stage/common" / logical).read_bytes()), info["staged_sha256"])
            self.assertEqual({B.SERVER_SHOP}, set(plan["server"]))
            info = plan["server"][B.SERVER_SHOP]
            self.assertEqual(sha(self.live.server), info["live_sha256"])
            self.assertEqual(sha((work / "stage/server" / B.SERVER_SHOP).read_bytes()), info["staged_sha256"])
            self.assertEqual(48, len(info["added"]))
            report = json.loads((work / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(8, len(report["weapons"]))
            self.assertFalse((work / "stage/medium").exists())

    def test_stage_base_icon_mode_writes_no_icon_png(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / "bond"
            result = B.stage(work, self.live, self.read, baseline=self.baseline, icon_mode="base")
            self.assertFalse(result["refused"], result)
            self.assertEqual("base", result["icon_mode"])
            plan = json.loads((work / "plan.json").read_text(encoding="utf-8"))
            self.assertEqual({B.BANNER + ".png", B.HEADER + ".png"}, set(plan["files"]))
            self.assertFalse((work / "stage/common/item/equipment/mod/bond").exists())
            staged = X.unpack((work / "stage/common" / B.ENH).read_bytes())
            for wid, w in self.baseline.items():
                self.assertEqual(w["equipment"][6], X.csv_read(staged[wid])[0][4])
            report = json.loads((work / "report.json").read_text(encoding="utf-8"))
            self.assertEqual("base", report["icon_mode"])

    def test_report_carries_the_decisions_that_need_a_human(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / "bond"
            B.stage(work, self.live, self.read, baseline=self.baseline)
            report = json.loads((work / "report.json").read_text(encoding="utf-8"))
        self.assertEqual("new", report["icon_mode"])
        items = {i["id"]: i for i in report["needs_attention"]}
        self.assertEqual({"C3", "C7", "ICON_B", "SMOKE"}, set(items))
        self.assertEqual({"作者", "接收方", "发布前"}, {i["who"] for i in items.values()})
        self.assertIn("白值不加", items["C3"]["text"])
        self.assertIn("1013", items["C3"]["text"])                                # ×10/7 的备选口径带数字
        self.assertIn("587–1494", items["C7"]["text"])
        self.assertIn("--icons base", items["ICON_B"]["text"])
        self.assertIn("equipment-enhanced-party-frame-v1", items["ICON_B"]["text"])
        self.assertEqual(8, len(report["status_alternatives"]))

    def test_stage_refuses_problems_and_live_workdirs(self):
        drifted = copy.deepcopy(self.baseline)
        c1, c2 = B.strength_cols(B.SOUL_T, "0")
        drifted["5060044"]["soul"][0][c1] = drifted["5060044"]["soul"][0][c2] = "141000"
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / "bond"
            result = B.stage(work, self.live, self.read, baseline=drifted)
            self.assertTrue(result["refused"])
            self.assertFalse(work.exists())                                            # 拒绝时不写任何东西
            with self.assertRaises(SystemExit):
                B.stage(self.live.assets_dir / "sub", self.live, self.read, baseline=self.baseline)
            with self.assertRaises(SystemExit):
                B.stage(self.live.store.parent / "sub", self.live, self.read, baseline=self.baseline)

    def test_stage_does_not_write_live(self):
        before = {k: sha(v) for k, v in self.live.tables.items()}
        with tempfile.TemporaryDirectory() as tmp:
            B.stage(Path(tmp) / "w", self.live, self.read, baseline=self.baseline)
        self.assertEqual(before, {k: sha(v) for k, v in self.live.tables.items()})


class WfxGateTests(Base):
    def test_staged_ea_table_needs_no_capability_on_any_profile(self):
        import wfx_gate
        only_new = X.pack({wid: X.csv_write(rows) for wid, rows in self.out["flat"][B.EA].items()})     # 只看本批 8 个键（live 里别人的 423 行另算）
        entry = wfx_gate.PayloadEntry(label="ea", logical=B.EA, read=lambda: only_new)
        profiles = wfx_gate.load_profiles()
        self.assertIn("official", profiles)                                            # 官方原版客户端也不缺任何能力
        for name in profiles:
            report = wfx_gate.check_entries([entry], name)
            self.assertTrue(report.ok, (name, report.problems))
            self.assertEqual([], report.required_capabilities(), name)


# ---------------------------------------------------------------------------
# 真 store（只读；没有就跳过）
# ---------------------------------------------------------------------------

class LiveStoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import wf_weapon_gacha as G
            cls.live = G.Live()
            cls.read = B.live_reader(cls.live)
            cls.read.flat(B.ENH_SHOP)
        except (SystemExit, FileNotFoundError, KeyError, ValueError):
            raise unittest.SkipTest("本检出没有 live store")
        cls.baseline = B.load_baseline()

    def test_live_matches_the_frozen_official_baseline(self):
        self.assertEqual([], B.baseline_problems(self.read, self.baseline))

    def test_live_build_has_no_problems_and_stage_is_all_new_or_all_published(self):
        out = B.build(self.read, baseline=self.baseline)
        out["problems"] += B.baseline_problems(self.read, self.baseline)
        self.assertEqual([], out["problems"])
        payloads = B.stage_payloads(self.live, out)
        self.assertEqual([], payloads["problems"])
        if payloads["tables"]:                                                           # 发布前：5 张表全是新键
            self.assertEqual(set(B.CLIENT_TABLES), set(payloads["tables"]))
            self.assertEqual({B.SERVER_SHOP}, set(payloads["server"]))
        else:                                                                            # 发布后：暂存为空（幂等）
            self.assertEqual({}, payloads["files"])

    def test_nested_builder_reproduces_live_bytes(self):
        import wf_quest_lib as Q
        rows = X.unpack(self.live.raw(B.ENH_STATUS))
        for key in ("5900101", "5910101", "5010073"):
            self.assertEqual(rows[key], B.build_nested_node(Q.parse_node(rows[key])), key)

    def test_abyss_reference_matches_the_pricing_anchor(self):
        ref = B.abyss_reference(self.read)
        self.assertEqual(15, len(ref))
        self.assertEqual(B.ABYSS_WEAPON_COIN, statistics.median(ref.values()))         # 深渊武装每把 3735（币量锚点）


if __name__ == "__main__":
    unittest.main()
