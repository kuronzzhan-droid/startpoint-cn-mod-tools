# -*- coding: utf-8 -*-
"""灰服三角色导入（``wf_balance_20260927b_gray3``，作者 2026-09-27：用灰服版替换本地）。

夹具 ``fixtures/balance_20260927b_gray3.json``（只读取数：本地链尾 1.4.1053 + 灰服压缩包）：
- ``live``：BEFORE 覆盖的全部 live 输入（``"<kind>|<json key>"``；live 缺的为 null）；
- ``gray``：压缩包 11 张整表里三名角色自己的键值（``tables``/``owned_keys``）与技能 DSL 树（``dsl``）；
- ``other_character_diff``：压缩包整表 vs 我方 live 的「其他角色」差异键——整表替换会带入的行；
- ``png_dims``：压缩包 PNG 的实际尺寸。
本机专属用例（原始 zip、解出目录、灰链归档、live store、候选包）缺件时跳过。
希耶提美术：作者 2026-09-27 看过对比图后接受灰版美术（``ART_DECISION`` 三人均 accepted；核心导入已发布，美术由
``wf_balance_20260927c_seofonart`` 包装 ``ART_UNITS`` 另行暂存）。``self.out`` 是默认输出（= 作者决定），``self.full``
是三人都接受美术时的输出；pending 路径（延后机制）用 ``run(cid, art=M.ART_PENDING)`` 单独覆盖。
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import zipfile
import zlib

pass  # Imports resolve from this checkout/package, not external source copies.
sys.setrecursionlimit(10000)

import wf_balance_20260927b_gray3 as M  # noqa: E402
import wf_balance_20260927b_mosiyike as B2_MOSIYIKE  # noqa: E402
import wf_balance_20260927b_siete as B2_SIETE  # noqa: E402
import wf_balance_20260927b_swimceltie as B2_SWIM  # noqa: E402
import wf_client_legality as L  # noqa: E402
import wf_dsl  # noqa: E402
from wf_character_revision import encode_tree  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).parent / "fixtures/balance_20260927b_gray3.json"
DATA = json.loads(FIXTURE.read_text(encoding="utf-8"))
FAKE_ROOT = Path("Z:/gray3-fixture/production")
CIDS = ("149997", "149995", "149996")
CODE = {cid: M.SPECS[cid]["code"] for cid in CIDS}
GRAY_CHAIN = ROOT / M.GRAY_CHAIN
LOCAL_STORE = (ROOT / "mod-tools/profiles.json").is_file()


def live_key(kind, key) -> str:
    return f"{kind}|{json.dumps(list(key) if isinstance(key, tuple) else key, ensure_ascii=False)}"


def reader(live: dict):
    def read(kind, key):
        name = live_key(kind, key)
        if name not in live:
            raise KeyError(name)
        value = live[name]
        if value is None and kind in ("cas", "dsl"):
            raise KeyError(key)
        return deepcopy(value)
    return read


class FixtureSource:
    """与 ArchiveSource 同接口，数据取自夹具（灰服压缩包里三名角色的键值与 DSL）。"""

    def __init__(self, gray: dict):
        self.gray = gray

    def owned_keys(self, logical, cid, code):
        return list(self.gray["owned_keys"].get(logical, {}).get(cid, []))

    def value(self, logical, key):
        return deepcopy(self.gray["tables"][logical][key])

    def dsl(self, program):
        return deepcopy(self.gray["dsl"][program])

    def file_path(self, tier, logical):
        return str(M.ArchiveSource(FAKE_ROOT).path(tier, logical))


def run(cid, live=None, gray=None, art=None):
    return M.revise_unit(cid, reader(deepcopy(DATA["live"]) if live is None else live),
                         FixtureSource(DATA["gray"] if gray is None else gray), art=art)


def expected_signature(cid, art):
    if art == M.ART_PENDING:
        return M.REVIEWED_CHANGES[cid]
    return M.merge_signatures(M.REVIEWED_CHANGES[cid], M.REVIEWED_ART[cid])


def walk(node):
    yield node
    if isinstance(node, list):
        for child in node:
            yield from walk(child)
    elif isinstance(node, dict):
        for child in node.values():
            yield from walk(child)


def commands(tree, name):
    return [n for n in walk(tree) if isinstance(n, list) and n and n[0] == name]


def leaf_diff(a, b, path=()):
    if type(a) is not type(b):
        return [(path, a, b)]
    if isinstance(a, list):
        if len(a) != len(b):
            return [(path, "len", len(a), len(b))]
        return [d for i, (x, y) in enumerate(zip(a, b)) for d in leaf_diff(x, y, path + (i,))]
    if isinstance(a, dict):
        if set(a) != set(b):
            return [(path, "keys")]
        return [d for k in a for d in leaf_diff(a[k], b[k], path + (k,))]
    return [] if a == b else [(path, a, b)]


def at(tree, path):
    for step in path:
        tree = tree[step]
    return tree


class ImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = {cid: run(cid) for cid in CIDS}
        cls.full = {cid: run(cid, art=M.ART_ACCEPTED) for cid in CIDS}

    # ------------------------------------------------------------ 基线与接口

    def test_fixture_is_the_reviewed_baseline(self):
        seen = set()
        for cid in CIDS:
            for (kind, key), want in M.BEFORE_BY_CID[cid].items():
                name = live_key(kind, key)
                seen.add(name)
                self.assertEqual(M.digest(DATA["live"][name]), want, name)
        self.assertEqual(seen, set(DATA["live"]))
        self.assertEqual(DATA["_meta"]["archive_sha256"], M.ARCHIVE_SHA256)

    def test_units_contract(self):
        self.assertEqual([u["CID"] for u in M.UNITS], list(CIDS))
        self.assertEqual({u["CID"]: u["CODE"] for u in M.UNITS},
                         {"149997": "mosiyike", "149995": "seofon_wind", "149996": "wind_spgirl_swim"})
        by = {u["CID"]: u for u in M.UNITS}
        self.assertEqual((by["149997"]["PACKAGES"], by["149997"]["PACKAGE_VERSION"]), (["mosiyike"], {"mosiyike": "0.1.2"}))
        self.assertEqual((by["149995"]["PACKAGES"], by["149995"]["PACKAGE_VERSION"]),
                         (["seofon_wind"], {"seofon_wind": "1.0.3"}))
        self.assertEqual((by["149996"]["PACKAGES"], by["149996"]["PACKAGE_VERSION"]), ([], {}))
        self.assertIs(by["149997"]["REVIEWED_DRIFT"], B2_MOSIYIKE.REVIEWED_DRIFT)
        self.assertEqual(by["149995"]["REVIEWED_DRIFT"], {})
        for unit in M.UNITS:
            self.assertEqual(unit["CAPABILITIES"], [])
            self.assertTrue(callable(unit["revise"]))
            self.assertEqual(unit["ART_DECISION"], M.ART_DECISION[unit["CID"]])
            notes = self.out[unit["CID"]]["notes"]
            json.dumps(notes, ensure_ascii=False)
            self.assertFalse(notes["runtime_verified"])
        # 作者 2026-09-27 接受希耶提灰版美术（原话见模块 ART_DECISION 注释）；改回 pending 必红。
        self.assertEqual(M.ART_DECISION, {"149997": M.ART_ACCEPTED, "149995": M.ART_ACCEPTED,
                                          "149996": M.ART_ACCEPTED})
        (art,) = M.ART_UNITS                                       # 作者接受美术后才暂存，不在 UNITS 里
        self.assertEqual((art["CID"], art["CODE"], art["PACKAGES"], art["PACKAGE_VERSION"]),
                         ("149995", "seofon_wind", ["seofon_wind"], {"seofon_wind": "1.0.4"}))
        self.assertTrue(art["REQUIRES_AUTHOR_SIGNOFF"])
        self.assertEqual(art["BEFORE"], M.ART_BEFORE_BY_CID["149995"])
        self.assertTrue(set(art["BEFORE"]) < set(M.BEFORE_BY_CID["149995"]))

    def test_change_set_is_the_reviewed_one(self):
        for cid in CIDS:
            self.assertEqual(M.signature(self.out[cid]), expected_signature(cid, M.ART_DECISION[cid]), cid)
            self.assertEqual(M.signature(self.full[cid]), expected_signature(cid, M.ART_ACCEPTED), cid)
            for out in (self.out[cid], self.full[cid]):
                self.assertEqual(out["server_character"], {})
                self.assertEqual(out["table"], {})
                self.assertEqual(out["nested_table"], {})
        with self.assertRaisesRegex(ValueError, "unknown art decision"):
            run("149995", art="maybe")

    # ------------------------------------------------------------ 只取三名角色自己的键

    def test_only_own_keys_are_returned(self):
        for cid, out in [(c, self.out[c]) for c in CIDS] + [(c, self.full[c]) for c in CIDS]:
            code = CODE[cid]
            for kind in ("ability", "leader", "text", "action", "server_text"):
                for key in out[kind]:
                    self.assertTrue(M.owns(key, cid, code), (cid, kind, key))
            for key in out["cas"]:
                self.assertEqual(key, M.WHIRLWIND_KEY)
            for logical, key in out["presentation_table"]:
                self.assertIn(logical, M.PRESENTATION_TABLES)
                self.assertTrue(key == cid or key.startswith(f"character/{code}/"), key)
            for program in out["dsl"]:
                self.assertTrue(program.startswith(f"battle/action/skill/action/rare5/{code}$")
                                or program == M.WHIRLWIND_PROGRAM, program)
            for member in out["files"]:
                tier, logical = member.split(":", 1)
                self.assertIn(tier, M.IMPORT_TIERS)
                self.assertTrue(M.owns_file(logical, code), member)

    def test_other_characters_rows_are_not_imported(self):
        """压缩包是灰链整表：别的角色大量不同（整表替换就会带进来）；这些键一个都不在输出里。"""
        other = DATA["other_character_diff"]
        self.assertGreaterEqual(len(other[M.ABIL]["decoded_diff"]), 100)
        self.assertGreaterEqual(len(other[M.LEAD]["decoded_diff"]), 20)
        self.assertGreaterEqual(len(other[M.ACT]["decoded_diff"]), 15)
        self.assertIn("159991", other[M.CHAR]["only_gray"])          # 灰方独有角色
        self.assertIn("129986", other[M.CHAR]["only_live"])          # 我方独有角色
        std = {M.ABIL: "ability", M.LEAD: "leader", M.TXT: "text", M.ACT: "action"}
        for cid in CIDS:
            for logical in M.GRAY_TABLES:
                returned = set(self.out[cid].get(std.get(logical, ""), {}))
                foreign = set().union(*(other[logical][k] for k in ("decoded_diff", "only_gray", "only_live")))
                self.assertFalse(returned & foreign, (cid, logical))
                for key in foreign:
                    self.assertFalse(any(M.owns(key, c, CODE[c]) for c in CIDS), key)

    def test_returned_values_are_the_gray_values(self):
        gray = DATA["gray"]["tables"]
        std = {"ability": M.ABIL, "leader": M.LEAD, "text": M.TXT}
        for cid in CIDS:
            out = self.out[cid]
            for kind, logical in std.items():
                for key, rows in out[kind].items():
                    self.assertEqual(rows, gray[logical][key], (kind, key))
            for code, entries in out["action"].items():
                self.assertEqual([[k, list(v)] for k, v in entries], gray[M.ACT][code])
            for program, tree in out["dsl"].items():
                if program != M.WHIRLWIND_PROGRAM:
                    self.assertEqual(json.dumps(tree), json.dumps(DATA["gray"]["dsl"][program]))
            same = out["notes"]["same_as_live"]
            for item in same:
                logical, key = item.split("|", 1)
                if logical == "dsl":
                    self.assertEqual(M.digest(DATA["gray"]["dsl"][key]),
                                     M.digest(DATA["live"][live_key("dsl", key)]))
                else:
                    self.assertEqual(M.digest(gray[logical][key]),
                                     M.digest(DATA["live"][live_key(*M.before_key(logical, key))]))
        # 其余 7 张表（character/speech/status/unique/upskill/switched/preview）三人与灰版逐键相同。
        for cid in CIDS:
            same = {s.split("|", 1)[0] for s in self.out[cid]["notes"]["same_as_live"]}
            for logical in (M.CHAR, M.SPEECH, M.STATUS, M.PREVIEW):
                self.assertIn(logical, same, cid)

    # ------------------------------------------------------------ 逐角色改动

    def test_mosiyike_rows(self):
        out, live = self.out["149997"], DATA["live"]
        old = live[live_key("ability", "1499972")]
        new = out["ability"]["1499972"]
        self.assertEqual([(c, old[4][c], new[4][c]) for c in range(126) if old[4][c] != new[4][c]],
                         [(113, "50000", "15000"), (114, "50000", "15000")])
        self.assertEqual(old[:4], new[:4])
        old, new = live[live_key("ability", "1499973")], out["ability"]["1499973"]
        self.assertEqual([(c, old[0][c], new[0][c]) for c in range(126) if old[0][c] != new[0][c]], [(35, "0", "1800")])
        old, new = live[live_key("ability", "1499975")], out["ability"]["1499975"]
        self.assertEqual(len(old), 4)
        self.assertEqual(new, [old[0], old[1], old[3]])              # 删「技能发动 → 全队技能槽 +20%」
        self.assertEqual((old[2][47], old[2][51]), ("211", "20000"))
        self.assertEqual(out["files"], {})
        self.assertEqual(out["dsl"], {})

    def test_seofon_skill_multipliers(self):
        """只动 CreateNormalAttack 倍率（p6），按层数档：lv1 90/70/50/35→70/50/40/30，lv2 90/75/55/40→80/55/45/35。"""
        want = {1: {90.0: 70.0, 70.0: 50.0, 50.0: 40.0, 35.0: 30.0},
                2: {90.0: 80.0, 75.0: 55.0, 55.0: 45.0, 40.0: 35.0}}
        for level in (1, 2):
            program = f"battle/action/skill/action/rare5/seofon_wind$seofon_wind_{level}"
            old = DATA["live"][live_key("dsl", program)]
            new = self.out["149995"]["dsl"][program]
            diffs = leaf_diff(old, new)
            self.assertTrue(diffs)
            for path, a, b in diffs:
                self.assertIn(path[-1], ("min", "max"))
                parent = at(old, path[:-3])
                self.assertEqual((parent[0], path[-3], path[-2]), ("CreateNormalAttack", 6, 0), path)
                self.assertEqual(want[level].get(a), b, (level, a, b))
            mults = sorted({n[6][0]["max"] for n in commands(new, "CreateNormalAttack") if n[6][0]["max"] >= 25})
            self.assertEqual(mults, [25.0, 30.0, 40.0, 50.0, 70.0] if level == 1 else [30.0, 35.0, 45.0, 55.0, 80.0])
        text = self.out["149995"]["text"]["149995"][0]
        self.assertIn("12级70倍", text[5])
        self.assertIn("12级80倍", text[7])
        self.assertEqual(text[5], text[7])
        self.assertEqual(text[7], text[9])

    def test_swim_rows(self):
        out, live = self.out["149996"], DATA["live"]
        a4 = out["ability"]["1499964"][0]
        for col, value in B2_SWIM.BEFORE_CELLS.items():             # 回到第二批 B4 之前那一行
            self.assertEqual(a4[col], value, col)
        for col, value in B2_SWIM.AFTER_CELLS.items():              # live 仍是第二批的输出
            self.assertEqual(live[live_key("ability", "1499964")][0][col], value, col)
        a6 = out["ability"]["1499966"]
        self.assertEqual([r[47] for r in a6], ["211", "224", "31", "629"])
        self.assertEqual((a6[3][27], a6[3][35], a6[3][70], a6[3][71]),
                         ("23", "60", M.WHIRLWIND_KEY, M.WHIRLWIND_PROGRAM))
        a3 = out["ability"]["1499963"]
        self.assertEqual([(r[97], r[102], r[109], r[113]) for r in a3[:2]], [("2", "10", "411", "20000"), ("2", "10", "410", "20000")])
        self.assertEqual((a3[2][30], a3[2][47], a3[2][51]), ("77700000", "390", "0"))
        self.assertEqual([r[49] for r in out["ability"]["1499962"]], ["Green"] * 3)
        leader = out["leader"]["149996"]
        self.assertEqual([(r[25], r[45], r[46]) for r in leader],
                         [("12", "32", "0"), ("12", "33", "0"), ("12", "211", "5"), ("0", "245", "5"), ("65", "211", "5")])
        for level in (1, 2, 3):
            tree = self.out["149996"]["dsl"][f"battle/action/skill/action/rare5/wind_spgirl_swim$wind_spgirl_swim_{level}"]
            self.assertEqual([n[14] for n in commands(tree, "CreateNormalAttack")], [[{"min": 7, "max": 7}]])
            self.assertEqual([n[2][1] for n in commands(tree, "ShowEffect")],
                             ["battle/effect/skill_unique/wind_spgirl_swim/wind_spgirl_swim"])
            pierce = [c[2][0][1][0]["max"] for c in commands(tree, "CreateCondition") if c[2][0][0] == "ACPiercing"]
            self.assertEqual(pierce, [720])
        for _level, fields in out["action"]["wind_spgirl_swim"]:
            self.assertTrue(fields[1].startswith("以肉眼无法看清的闪击"))

    def test_whirlwind_supplement(self):
        out = self.out["149996"]
        tree = out["dsl"][M.WHIRLWIND_PROGRAM]
        self.assertEqual(hashlib.sha256(encode_tree(tree)).hexdigest(), M.WHIRLWIND_DEFLATE_SHA256)
        self.assertEqual(M.WHIRLWIND_DEFLATE_SHA256, M.SUPPLEMENT_PROVENANCE["whirlwind_program"]["sha256"])
        self.assertFalse(commands(tree, "StopBall"))
        self.assertEqual([n[2][1] for n in commands(tree, "ShowEffect")],
                         ["battle/effect/skill_unique/bigwing_shaman_smr21/bigwing_shaman_smr21_wind"])
        attack = commands(tree, "CreateNormalAttack")
        area = commands(tree, "CreateHitArea")
        self.assertEqual((len(attack), area[0][14]), (1, ["CalculatedUsingMaxNumOfHits", 24]))
        self.assertEqual(out["cas"], {M.WHIRLWIND_KEY: [["额外发动「旋风」"]]})
        self.assertEqual(out["new_programs"], [M.WHIRLWIND_PROGRAM])
        self.assertIsNone(DATA["live"][live_key("dsl", M.WHIRLWIND_PROGRAM)])
        self.assertIsNone(DATA["live"][live_key("cas", M.WHIRLWIND_KEY)])

    def test_presentation_rows_follow_the_new_art(self):
        dims = DATA["png_dims"]
        for cid in CIDS:
            code = CODE[cid]
            for evo in ("0", "1"):
                x, y, w, h = map(int, M.PRESENTATION_ROWS[M.CIMG, cid][evo][0])
                trim = M.PRESENTATION_ROWS[M.TRIM, f"character/{code}/ui/full_shot_1440_1920_{evo}"][0]
                self.assertEqual([w, h], dims[f"medium:character/{code}/ui/full_shot_1440_1920_{evo}.png"], (cid, evo))
                self.assertEqual((str(x), str(y), "2000", "2000"), tuple(trim))
                self.assertTrue(0 <= x and 0 <= y and x + w <= 2000 and y + h <= 2000)
                self.assertEqual(M.PRESENTATION_ROWS[M.FSA, cid][evo][0][:3], ["1000", "1000", "1"])
        self.assertEqual(sorted(k[1] for k in self.full["149995"]["presentation_table"] if k[0] != M.TRIM),
                         ["149995", "149995"])
        self.assertEqual(self.out["149995"]["presentation_table"],       # 作者 09-27 接受：定位行随美术导入
                         self.full["149995"]["presentation_table"])
        self.assertEqual(run("149995", art=M.ART_PENDING)["presentation_table"], {})   # pending：随美术一起延后
        self.assertEqual(self.full["149996"]["presentation_table"], {})
        self.assertEqual(self.full["149997"]["presentation_table"], {})
        live_cimg = DATA["live"][live_key("nested_table", (M.CIMG, "149995"))]
        self.assertEqual(live_cimg["0"][0][2:], ["1774", "1769"])   # 旧立绘尺寸，新 PNG 放进去会拉伸

    # ------------------------------------------------------------ 希耶提美术：作者 09-27 接受；pending 机制仍可用

    def test_seofon_art_follows_the_author_decision(self):
        """默认输出 = 作者决定（accepted，美术与定位行随导入）；pending 路径仍只延后、清单与接受时导入的相同。"""
        out, full = self.out["149995"], self.full["149995"]
        self.assertEqual(M.digest(out["files"]), M.digest(full["files"]))
        self.assertEqual(out["presentation_table"], full["presentation_table"])
        self.assertEqual(len(out["files"]), 27)
        art = out["notes"]["art"]
        self.assertEqual((art["decision"], art["status"]), (M.ART_ACCEPTED, "imported"))
        self.assertEqual(art["files"], sorted(full["files"]))
        self.assertIs(art["review"], M.ART_REVIEW["149995"])
        self.assertIn("2026-09-27", art["review"]["decision"])
        self.assertEqual(len(art["review"]["package_tests_red_if_accepted"]), 4)
        pending = run("149995", art=M.ART_PENDING)
        self.assertEqual(pending["files"], {})
        self.assertEqual(pending["presentation_table"], {})
        deferred = pending["notes"]["art"]
        self.assertEqual(deferred["decision"], M.ART_PENDING)
        self.assertIn("deferred", deferred["status"])
        self.assertEqual(deferred["files"], sorted(full["files"]))                 # 延后的正是接受时会导入的
        self.assertEqual(deferred["presentation_table"],
                         sorted(f"{a}|{b}" for a, b in full["presentation_table"]))
        self.assertTrue(all(M.is_art(member, "seofon_wind") for member in deferred["files"]))
        for key in ("text", "action", "dsl", "server_text"):                         # 非美术部分两条路径相同
            self.assertEqual(M.digest(pending[key]), M.digest(full[key]), key)
            self.assertEqual(M.digest(out[key]), M.digest(full[key]), key)
        # 泳装：新特效族是 DSL 依赖（不算美术），即使美术待定也必须随 DSL 导入。
        swim_pending = run("149996", art=M.ART_PENDING)
        self.assertEqual(sorted(swim_pending["files"]),
                         [f"common:battle/effect/skill_unique/wind_spgirl_swim/wind_spgirl_swim.{s}"
                          for s in ("atlas.amf3.deflate", "parts.amf3.deflate", "png", "timeline.amf3.deflate")])
        self.assertEqual(self.out["149996"]["notes"]["art"]["status"], "imported")

    def test_art_review_justifies_the_deferral(self):
        review = M.ART_REVIEW["149995"]
        low, high = review["official_face_y_p10_p90"]
        gray_fsa = M.PRESENTATION_ROWS[M.FSA, "149995"]
        live_fsa = DATA["live"][live_key("nested_table", (M.FSA, "149995"))]
        gray_face = {slot: [int(v) for v in rows[0][3:]] for slot, rows in gray_fsa.items()}
        live_face = {slot: [int(v) for v in rows[0][3:]] for slot, rows in live_fsa.items()}
        self.assertEqual(gray_face, review["face_anchor"]["gray"])
        self.assertEqual(live_face, review["face_anchor"]["ours"])
        self.assertFalse(low <= gray_face["1"][1] <= high)                            # 觉醒脸锚 874 出带
        self.assertNotEqual(gray_face["0"][1], gray_face["1"][1])                     # 两槽不同高
        self.assertTrue(all(low <= face[1] <= high for face in live_face.values()))
        self.assertEqual(live_face["0"][1], live_face["1"][1])
        edges = review["cutin_edges"]
        self.assertTrue(all(max(v[:3]) < 8 for v in edges["ours"].values()))
        self.assertTrue(all(max(v[:3]) >= 8 for v in edges["gray"].values()))
        # 泳装：定位行灰我相同、两槽脸锚在带内；cut-in 边缘我方同样不透明（不是回退）。
        swim = M.PRESENTATION_ROWS[M.FSA, "149996"]
        self.assertTrue(all(low <= int(rows[0][4]) <= high for rows in swim.values()))
        self.assertEqual(M.digest(swim), M.digest(DATA["live"][live_key("nested_table", (M.FSA, "149996"))]))
        swim_edges = M.ART_REVIEW["149996"]["cutin_edges"]
        self.assertEqual({s: max(v[:3]) >= 8 for s, v in swim_edges["ours"].items()},
                         {s: max(v[:3]) >= 8 for s, v in swim_edges["gray"].items()})

    def test_art_unit_runs_after_the_core_import(self):
        """ART_UNITS 只锁美术输入：核心导入（文案/DSL 变了）之后仍可跑；美术导入之后不可重放。"""
        live = deepcopy(DATA["live"])
        core = self.out["149995"]
        for kind in ("text", "server_text", "dsl"):
            for key, value in core[kind].items():
                live[live_key(kind, key)] = deepcopy(value)
        for code, value in core["action"].items():
            live[live_key("action", code)] = [[k, list(v)] for k, v in value]
        with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
            run("149995", live=live)                                                  # 核心导入不可重放
        (unit,) = M.ART_UNITS
        out = M.revise_art("149995", reader(live), FixtureSource(DATA["gray"]))
        self.assertEqual(M.signature(out), M.REVIEWED_ART["149995"])
        self.assertEqual(M.digest(out["files"]), M.digest(self.full["149995"]["files"]))
        self.assertEqual(out["presentation_table"], self.full["149995"]["presentation_table"])
        for key in ("ability", "leader", "cas", "text", "action", "dsl", "server_text"):
            self.assertEqual(out[key], {}, key)
        json.dumps(out["notes"], ensure_ascii=False)
        self.assertEqual(out["notes"]["art"]["decision"], M.ART_ACCEPTED)
        self.assertTrue(callable(unit["revise"]))
        after = deepcopy(live)                                                        # 美术导入之后
        for (logical, key), value in out["presentation_table"].items():
            after[live_key(*M.before_key(logical, key))] = deepcopy(value)
        for member in out["files"]:
            after[live_key("file_sha256", tuple(member.split(":", 1)))] = M.GRAY_FILES[member]
        with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
            M.revise_art("149995", reader(after), FixtureSource(DATA["gray"]))
        drift = deepcopy(DATA["live"])
        drift[live_key("file_sha256", ("medium", "character/seofon_wind/ui/square_0.png"))] = "0" * 64
        with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
            M.revise_art("149995", reader(drift), FixtureSource(DATA["gray"]))

    def test_encode_presentation_matches_the_live_row_format(self):
        """live 立绘定位行无尾换行；X.csv_write 会带 \\n（希耶提包测试 split(',') 读出 '2000\\n'）。"""
        for (logical, key), value in M.PRESENTATION_ROWS.items():
            raw = M.encode_presentation(logical, value)
            if logical in M.NESTED_TABLES:
                inner = M.X.unpack(raw)
                self.assertEqual(list(inner), list(value))
                texts = {k: zlib.decompress(v).decode() for k, v in inner.items()}
                self.assertEqual(texts, {k: ",".join(rows[0]) for k, rows in value.items()})
            else:
                self.assertEqual(zlib.decompress(raw).decode(), ",".join(value[0]))
            self.assertEqual(M.digest(M.decode_value(logical, raw)), M.digest(value), (logical, key))
        self.assertTrue(zlib.decompress(M.X.csv_write([["1", "2"]])).endswith(b"\n"))

    def test_server_text_mirrors_the_client_text(self):
        for cid in ("149995", "149996"):
            self.assertEqual(self.out[cid]["server_text"][cid], self.out[cid]["text"][cid])
            self.assertEqual(DATA["live"][live_key("server_text", cid)], DATA["live"][live_key("text", cid)])
        self.assertEqual(self.out["149997"]["server_text"], {})

    # ------------------------------------------------------------ 门禁

    def test_row_gates_are_empty(self):
        for cid in CIDS:
            out = self.out[cid]
            cas = set(out["cas"])
            for key, rows in out["ability"].items():
                for row in rows:
                    self.assertEqual(M.row_problems("ability", row, cas), [], key)
                    self.assertEqual(L.required_client_capabilities("ability", row), [])
            for key, rows in out["leader"].items():
                for row in rows:
                    self.assertEqual(M.row_problems("leader_ability", row, cas), [], key)
        row = self.out["149996"]["ability"]["1499966"][3]
        self.assertTrue(L.invoke_skill_string_problems(row, set(), kind="ability"))   # 缺文案键会被门禁拦住

    def test_dsl_gates_roundtrip_and_payload(self):
        for cid in CIDS:
            for program, tree in self.out[cid]["dsl"].items():
                self.assertEqual(M.dsl_problems(tree), [], program)
                if program in M.GRAY_DSL_AMF3_SHA256:
                    self.assertEqual(hashlib.sha256(wf_dsl.encode_amf3(tree)).hexdigest(),
                                     M.GRAY_DSL_AMF3_SHA256[program], program)

    def test_files_mapping(self):
        counts = {cid: {} for cid in CIDS}
        self.assertEqual(self.out["149995"]["files"], self.full["149995"]["files"])   # 作者 09-27 接受希耶提美术
        self.assertEqual(run("149995", art=M.ART_PENDING)["files"], {})               # pending：美术延后
        self.assertEqual(self.out["149996"]["files"], self.full["149996"]["files"])
        for cid in CIDS:
            for member, path in self.full[cid]["files"].items():
                tier, logical = member.split(":", 1)
                self.assertIn(member, M.GRAY_FILES)
                self.assertFalse(logical.startswith("master/") or logical.endswith(M.DSL_SUFFIX))
                self.assertEqual(path, str(M.ArchiveSource(FAKE_ROOT).path(tier, logical)))
                self.assertNotEqual(DATA["live"][live_key("file_sha256", (tier, logical))], M.GRAY_FILES[member])
                counts[cid][tier] = counts[cid].get(tier, 0) + 1
        swim = self.out["149996"]["files"]
        for suffix in ("parts.amf3.deflate", "timeline.amf3.deflate", "atlas.amf3.deflate", "png"):
            member = f"common:battle/effect/skill_unique/wind_spgirl_swim/wind_spgirl_swim.{suffix}"
            self.assertIn(member, swim)
            self.assertIsNone(DATA["live"][live_key("file_sha256", tuple(member.split(":", 1)))])
        self.assertEqual(sum(1 for m in M.GRAY_FILES if m.startswith("ios:")), 6)
        self.assertFalse(any(m.startswith("ios:") for cid in CIDS for m in self.full[cid]["files"]))
        self.assertEqual(len(M.GRAY_FILES), 161)
        self.assertEqual(counts, {"149997": {}, "149995": {"android": 2, "medium": 25},
                                  "149996": {"android": 2, "common": 8, "medium": 25}})

    # ------------------------------------------------------------ fail closed / 纯函数

    def test_live_drift_is_rejected(self):
        for cid in CIDS:
            for kind, key in M.BEFORE_BY_CID[cid]:
                live = deepcopy(DATA["live"])
                live[live_key(kind, key)] = "drifted"
                with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
                    run(cid, live=live)

    def test_gray_source_drift_is_rejected(self):
        gray = deepcopy(DATA["gray"])
        gray["owned_keys"][M.ABIL]["149997"].append("1499979")
        with self.assertRaisesRegex(ValueError, "gray key set drift"):
            run("149997", gray=gray)
        gray = deepcopy(DATA["gray"])
        gray["tables"][M.CHAR]["149995"][0][1] = "9"               # 本应相同的键变了 ⇒ 结果集合偏离审查
        with self.assertRaisesRegex(ValueError, "drifted from the reviewed change set"):
            run("149995", gray=gray)
        gray = deepcopy(DATA["gray"])
        gray["tables"][M.ABIL]["1499966"][3][70] = "ability_skill_wind_spgirl_swim_typo"
        with self.assertRaisesRegex(ValueError, "custom_ability_string"):
            run("149996", gray=gray)
        # 美术清单钉住：灰方定位行变了（这里让一行与 live 相同）即拒绝——接受路径如此，pending 路径哪怕输出不含美术也如此。
        key = (M.TRIM, "character/seofon_wind/ui/skill_cutin_0")
        live_rows = DATA["live"][live_key(*M.before_key(*key))]
        with mock.patch.dict(M.PRESENTATION_ROWS, {key: live_rows}):
            with self.assertRaisesRegex(ValueError, "art change set drifted"):
                run("149995")
            with self.assertRaisesRegex(ValueError, "art change set drifted"):
                run("149995", art=M.ART_PENDING)
            with self.assertRaisesRegex(ValueError, "art change set drifted"):
                M.revise_art("149995", reader(deepcopy(DATA["live"])), FixtureSource(DATA["gray"]))

    def test_archive_source_checks_member_bytes(self):
        logical = M.CHAR
        with tempfile.TemporaryDirectory() as tmp:
            src = M.ArchiveSource(tmp, archive=Path(tmp) / "no-such.zip")
            with self.assertRaisesRegex(ValueError, "archive member missing"):
                src.raw("common", logical)
            with self.assertRaisesRegex(ValueError, "extracted member missing"):
                src.file_path("common", logical)
            path = src.path("common", logical)
            self.assertEqual(path, Path(tmp) / M.member_name("common", logical).split("/", 1)[1])
            path.parent.mkdir(parents=True)
            path.write_bytes(b"not the gray table")
            with self.assertRaisesRegex(ValueError, "archive member changed"):
                src.raw("common", logical)
            with self.assertRaisesRegex(ValueError, "archive member changed"):
                src.file_path("common", logical)
            with self.assertRaisesRegex(ValueError, "not an archive member"):
                src.raw("common", "master/string/custom_ability_string.orderedmap")
            fake = Path(tmp) / "fake.zip"
            with zipfile.ZipFile(fake, "w") as zf:
                zf.writestr(M.member_name("common", M.LEAD), b"x")
            with self.assertRaisesRegex(ValueError, "archive sha256 mismatch"):   # 整包不符就不读成员
                M.ArchiveSource(Path(tmp) / "empty", archive=fake).raw("common", M.LEAD)
            with self.assertRaisesRegex(ValueError, "archive sha256 mismatch"):
                M.extract(Path(tmp) / "out", archive=fake)

    def test_default_root_is_durable_and_outside_the_session_scratchpad(self):
        if "WF_GRAY3_ROOT" not in os.environ:
            self.assertEqual(M.GRAY_ROOT, M.REPO / "work" / "gray3" / "production")   # /work/ 已 gitignore
        source = Path(M.__file__).read_text(encoding="utf-8")
        self.assertNotIn("scratchpad", source)
        self.assertNotIn("gettempdir", source)

    def test_batch2_swim_module_would_replay_after_the_import(self):
        """导入后 live 1499964 = 灰版行，其摘要恰好等于第二批泳装模块的 BEFORE：第二批模块在 gray3 之后
        不得重跑（会把 B4 静默叠回）；A4 归任务 B。"""
        gray_row = DATA["gray"]["tables"][M.ABIL][B2_SWIM.ABILITY_KEY]
        self.assertEqual(self.out["149996"]["ability"][B2_SWIM.ABILITY_KEY], gray_row)
        self.assertEqual(M.digest(gray_row), B2_SWIM.BEFORE[("ability", B2_SWIM.ABILITY_KEY)])
        self.assertIn("禁止重跑", M.OVERWRITES_BATCH2["149996"])
        self.assertTrue(any("swimceltie" in step for step in M.STAGE_INTEGRATION))

    def test_stage_reader_without_extension_is_rejected(self):
        live = deepcopy(DATA["live"])
        base = reader(live)

        def read(kind, key):
            if kind in ("nested_table", "file_sha256"):
                raise KeyError(kind)
            return base(kind, key)
        with self.assertRaisesRegex(ValueError, "stage reader extension"):
            M.revise_unit("149997", read, FixtureSource(DATA["gray"]))

    def test_inputs_not_mutated_and_output_detached(self):
        live, gray = deepcopy(DATA["live"]), deepcopy(DATA["gray"])
        out = run("149996", live=live, gray=gray)
        self.assertEqual(live, DATA["live"])
        self.assertEqual(gray, DATA["gray"])
        out["ability"]["1499966"][0][0] = "mutated"
        out["dsl"][M.WHIRLWIND_PROGRAM][0] = "mutated"
        self.assertEqual(gray, DATA["gray"])
        self.assertEqual(M.WHIRLWIND_TREE[0], "ActionDsl")
        self.assertEqual(json.dumps(run("149996")["ability"]), json.dumps(self.out["149996"]["ability"]))

    def test_not_reapplicable_after_import(self):
        live = deepcopy(DATA["live"])
        live[live_key("ability", "1499972")] = self.out["149997"]["ability"]["1499972"]
        with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
            run("149997", live=live)

    def test_batch2_results_outside_the_archive_survive(self):
        """压缩包不含 PF 覆盖树与回响树：第二批 B2/B3 不被覆盖；只有泳装 A4（B4）被灰版替换。"""
        programs = {p for cid in CIDS for p in self.out[cid]["dsl"]}
        for program in B2_MOSIYIKE.PF_PROGRAMS.values():
            self.assertNotIn(program, programs)
            self.assertNotIn(f"common:{wf_dsl.dsl_logical(program)}", M.GRAY_FILES)
        self.assertNotIn(B2_SIETE.ECHO_PROGRAM, programs)
        self.assertNotIn(f"common:{wf_dsl.dsl_logical(B2_SIETE.ECHO_PROGRAM)}", M.GRAY_FILES)
        self.assertIn(B2_SWIM.ABILITY_KEY, self.out["149996"]["ability"])
        self.assertIn("覆盖", self.out["149996"]["notes"]["overwrites_batch2"])

    # ------------------------------------------------------------ 本机：原始压缩包 / 解出目录 / 灰链归档

    @unittest.skipUnless(Path(M.ARCHIVE).is_file(), "原始压缩包不在本机")
    def test_zip_members_are_the_pinned_bytes(self):
        import wf_mod_tool as core
        raw = Path(M.ARCHIVE).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), M.ARCHIVE_SHA256)
        dirs = {v: k for k, v in M.TIER_DIRS.items()}
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            members = [n for n in zf.namelist() if not n.endswith("/")]
            self.assertEqual(len(members), len(M.GRAY_FILES))
            by_path = {}
            for member, sha in M.GRAY_FILES.items():
                tier, logical = member.split(":", 1)
                hashed = core.sha1_path(logical)
                by_path[f"production/{M.TIER_DIRS[tier]}/{hashed[:2]}/{hashed[2:]}"] = sha
            for name in members:
                self.assertEqual(hashlib.sha256(zf.read(name)).hexdigest(), by_path[name], name)
                self.assertIn(name.split("/")[1], dirs)

    @unittest.skipUnless(M.GRAY_ROOT.is_dir(), "压缩包解出目录不在本机")
    def test_extracted_root_matches_the_fixture(self):
        src = M.ArchiveSource()
        for member in M.GRAY_FILES:
            src.raw(*member.split(":", 1))
        gray = DATA["gray"]
        for logical, by_cid in gray["owned_keys"].items():
            for cid, keys in by_cid.items():
                self.assertEqual(src.owned_keys(logical, cid, CODE[cid]), keys, (logical, cid))
                for key in keys:
                    self.assertEqual(M.digest(src.value(logical, key)), M.digest(gray["tables"][logical][key]))
        for program, tree in gray["dsl"].items():
            self.assertEqual(json.dumps(src.dsl(program)), json.dumps(tree), program)
        for cid in CIDS:                                             # 真来源与夹具来源结果相同
            out = M.revise_unit(cid, reader(deepcopy(DATA["live"])), src)
            self.assertEqual(M.signature(out), M.signature(self.out[cid]))
            full = M.revise_unit(cid, reader(deepcopy(DATA["live"])), src, art=M.ART_ACCEPTED)
            self.assertEqual(M.signature(full), M.signature(self.full[cid]))
            for member, path in full["files"].items():
                self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(), M.GRAY_FILES[member])
                self.assertTrue(Path(path).is_relative_to(M.GRAY_ROOT), path)

    @unittest.skipUnless(Path(M.ARCHIVE).is_file(), "原始压缩包不在本机")
    def test_zip_fallback_and_extract(self):
        """解出目录缺了也能直接读钉哈希的压缩包；files 要落地路径，extract 解出后才给。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "production"
            src = M.ArchiveSource(root)
            for member in M.GRAY_FILES:
                src.raw(*member.split(":", 1))
            self.assertEqual(M.digest(src.value(M.ABIL, "1499964")),
                             M.digest(DATA["gray"]["tables"][M.ABIL]["1499964"]))
            with self.assertRaisesRegex(ValueError, "extract"):
                src.file_path("medium", "character/seofon_wind/ui/square_0.png")
            with self.assertRaisesRegex(ValueError, "extract"):
                M.revise_unit("149996", reader(deepcopy(DATA["live"])), src)
            self.assertEqual(M.extract(root), len(M.GRAY_FILES))
            self.assertEqual(M.extract(root), 0)                                       # 幂等
            out = M.revise_unit("149996", reader(deepcopy(DATA["live"])), M.ArchiveSource(root))
            self.assertEqual(M.signature(out), M.signature(self.out["149996"]))
            self.assertTrue(all(Path(p).is_relative_to(root) for p in out["files"].values()))

    @unittest.skipUnless(M.GRAY_ROOT.is_dir(), "压缩包解出目录不在本机")
    def test_extracted_assets_are_sane(self):
        from PIL import Image
        import wf_assets
        from wf_midautumn_kitlib import donor_code_leaks
        src = M.ArchiveSource()
        oob = []
        for member in M.GRAY_FILES:
            tier, logical = member.split(":", 1)
            if logical.startswith("master/"):
                continue
            data = src.raw(tier, logical)
            code = logical.split("/")[1] if logical.startswith("character/") else logical.split("/")[3]
            self.assertEqual(donor_code_leaks(data, code), [], member)
            if logical.endswith(".png"):
                self.assertEqual(data[:8], wf_assets.PNG_FAKE, member)
                if member in DATA["png_dims"]:
                    size = Image.open(io.BytesIO(wf_assets.png_decode(data))).size
                    self.assertEqual(list(size), DATA["png_dims"][member], member)
            if logical.endswith(".atlas.amf3.deflate"):
                png_member = f"{tier if '/ui/' not in logical else 'medium'}:{logical.replace('.atlas.amf3.deflate', '.png')}"
                w, h = DATA["png_dims"][png_member]
                atlas = wf_dsl.parse_dsl(zlib.decompress(data, -15))["tree"]
                oob += [(logical, r["n"]) for r in atlas if r["x"] + r["w"] > w or r["y"] + r["h"] > h]
        # 唯一越界：希耶提插画图集（灰我同字节，按 363×781 打包）配灰版 361×789 PNG——两个矩形宽 362/363 越出右缘 1-2 px，
        # PNG 又比图集高 8 px（y 781-788 不在任何矩形里）。下面钉住：这 8 行与 x≥361 全透明、两幅画内容都在矩形内，
        # 所以没有可见像素被裁（灰服自 1.4.90 起如此；作者 09-27 接受希耶提美术后随 seofonart 进 live，见 RISKS）。
        self.assertEqual(oob, [("character/seofon_wind/ui/illustration_setting_sprite_sheet.atlas.amf3.deflate",
                                "character/seofon_wind/ui/full_shot_illustration_setting_0"),
                               ("character/seofon_wind/ui/illustration_setting_sprite_sheet.atlas.amf3.deflate",
                                "character/seofon_wind/ui/full_shot_illustration_setting_1")])
        sheet = "character/seofon_wind/ui/illustration_setting_sprite_sheet"
        image = Image.open(io.BytesIO(wf_assets.png_decode(src.raw("medium", f"{sheet}.png")))).convert("RGBA")
        alpha = image.getchannel("A")
        atlas = wf_dsl.parse_dsl(zlib.decompress(src.raw("common", f"{sheet}.atlas.amf3.deflate"), -15))["tree"]
        self.assertEqual(image.size, (361, 789))
        self.assertEqual(max(r["y"] + r["h"] for r in atlas), 781)
        self.assertEqual(alpha.crop((0, 781, 361, 789)).getbbox(), None)             # 图集外的 8 行全透明
        for rect in atlas:                                                           # 每个矩形里的内容整块在矩形内
            inside = alpha.crop((rect["x"], rect["y"], min(rect["x"] + rect["w"], 361), rect["y"] + rect["h"]))
            self.assertIsNotNone(inside.getbbox(), rect["n"])
        self.assertEqual(alpha.getbbox(), (1, 31, 360, 781))
        # 泳装插画图集（尺寸灰我相同）：第一幅画下缘 y 426-428 越出矩形 0（到 y 425），其中 427-428 落进矩形 1 顶部。
        sheet = "character/wind_spgirl_swim/ui/illustration_setting_sprite_sheet"
        alpha = Image.open(io.BytesIO(wf_assets.png_decode(src.raw("medium", f"{sheet}.png")))).getchannel("A")
        atlas = {r["n"].rsplit("_", 1)[1]: r for r in
                 wf_dsl.parse_dsl(zlib.decompress(src.raw("common", f"{sheet}.atlas.amf3.deflate"), -15))["tree"]}
        self.assertEqual((atlas["0"]["y"] + atlas["0"]["h"], atlas["1"]["y"]), (426, 427))
        self.assertIsNotNone(alpha.crop((0, 427, 361, 429)).getbbox())               # 2 行碎边进了觉醒插画顶部
        self.assertIsNone(alpha.crop((0, 429, 361, 433)).getbbox())
        self.assertIsNone(alpha.crop((0, 794, 361, 798)).getbbox())

    @unittest.skipUnless(LOCAL_STORE and Path(M.ARCHIVE).is_file(), "local live store and gray zip required")
    def test_art_review_numbers_match_the_pixels(self):
        """ART_REVIEW 的 cut-in 边缘数值由真像素复算（我方 = live store，灰版 = 压缩包）。"""
        import wf_assets
        import wf_mod_tool as core
        store = Path(core.resolve_active_store())
        src = M.ArchiveSource()
        for cid, code in (("149995", "seofon_wind"), ("149996", "wind_spgirl_swim")):
            edges = M.ART_REVIEW[cid]["cutin_edges"]
            for slot in ("0", "1"):
                logical = f"character/{code}/ui/skill_cutin_{slot}.png"
                gray = M.cutin_edges(M._png(src.raw("medium", logical)))
                self.assertEqual(gray, edges["gray"][slot], (cid, slot))
                live = wf_assets.path_in_root(store, "medium", logical).read_bytes()
                if hashlib.sha256(live).hexdigest() == M.BEFORE_BY_CID[cid][("file_sha256", ("medium", logical))]:
                    self.assertEqual(M.cutin_edges(M._png(live)), edges["ours"][slot], (cid, slot))

    @unittest.skipUnless(GRAY_CHAIN.is_dir(), "灰链归档（gray-audit-20260830）不在本机")
    def test_supplement_matches_the_gray_chain_archive(self):
        import wf_mod_tool as core
        import wf_share_update_codec as X
        prov = M.SUPPLEMENT_PROVENANCE

        def member(archive, name):
            path = ROOT / archive
            with zipfile.ZipFile(path) as zf:
                return hashlib.sha256(path.read_bytes()).hexdigest(), zf.read(name)
        sha, raw = member(prov["whirlwind_program"]["archive"], prov["whirlwind_program"]["member"])
        self.assertEqual(sha, prov["whirlwind_program"]["archive_sha256"])
        self.assertEqual(hashlib.sha256(raw).hexdigest(), M.WHIRLWIND_DEFLATE_SHA256)
        self.assertEqual(raw, encode_tree(M.WHIRLWIND_TREE))
        self.assertTrue(prov["whirlwind_program"]["member"].endswith(core.sha1_path(wf_dsl.dsl_logical(M.WHIRLWIND_PROGRAM))[2:]))
        sha, raw = member(prov["whirlwind_cas"]["archive"], prov["whirlwind_cas"]["member"])
        self.assertEqual(hashlib.sha256(raw).hexdigest(), prov["whirlwind_cas"]["table_sha256"])
        self.assertEqual(X.csv_read(X.unpack(raw)[M.WHIRLWIND_KEY]), M.WHIRLWIND_CAS_ROWS)
        tables = {}
        for logical, (name, want) in prov["presentation_rows"]["members"].items():
            sha, raw = member(prov["presentation_rows"]["archive"], name)
            self.assertEqual(hashlib.sha256(raw).hexdigest(), want)
            tables[logical] = X.unpack(raw)
        for (logical, key), value in M.PRESENTATION_ROWS.items():
            self.assertEqual(M.digest(M.decode_value(logical, tables[logical][key])), M.digest(value), (logical, key))

    # ------------------------------------------------------------ 本机：live store / 候选包

    @unittest.skipUnless(LOCAL_STORE, "local live store required")
    def test_live_is_either_the_baseline_or_the_import(self):
        import wf_assets
        import wf_mod_tool as core
        import wf_share_update_codec as X
        store = Path(core.resolve_active_store())
        std = {"ability": M.ABIL, "leader": M.LEAD, "text": M.TXT}
        cas = X.unpack(core.table_path(store, M.CAS).read_bytes())
        server = json.loads((ROOT / "assets/cdndata/character_text.json").read_bytes())

        def table_path(logical):
            return core.table_path(store, logical)

        def live_value(kind, key):
            if kind in std or kind in ("table", "nested_table"):
                logical, outer = (std[kind], key) if kind in std else key
                return M.decode_value(logical, X.unpack(table_path(logical).read_bytes())[outer])
            if kind == "action":
                return M.decode_value(M.ACT, X.unpack(table_path(M.ACT).read_bytes())[key])
            if kind == "dsl":
                path = table_path(wf_dsl.dsl_logical(key))
                return wf_dsl.parse_dsl(zlib.decompress(path.read_bytes(), -15))["tree"] if path.is_file() else None
            if kind == "cas":
                return X.csv_read(cas[key]) if key in cas else None
            if kind == "server_text":
                return server[key]
            if kind == "file_sha256":
                tier, logical = key
                path = table_path(logical) if tier == "common" else wf_assets.path_in_root(store, tier, logical)
                return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
            raise KeyError(kind)

        def imported(cid, kind, key):
            out = self.full[cid]                                   # 美术接受与否，live 只能是基线或灰版
            if kind in ("ability", "leader", "text", "server_text", "cas", "dsl"):
                return out[kind].get(key)
            if kind == "action":
                value = out["action"].get(key)
                return None if value is None else [[k, list(v)] for k, v in value]
            if kind in ("table", "nested_table"):
                return out["presentation_table"].get(tuple(key))
            if kind == "file_sha256":
                return M.GRAY_FILES.get(":".join(key)) if ":".join(key) in out["files"] else None
            return None

        # gray3 之后，同一批次里又各自跑了一轮的两个角色（墨斯伊克、泳装希尔媞）：real live 已推进到那一轮的输出，
        # 这里从各自模块的 c 测试夹具重放同一 revise()，把结果也算作合法落点（不改变 self.out/self.full 本身）。
        import wf_balance_20260927c_mosiyike as C_MOSIYIKE
        import wf_balance_20260927c_swimceltie as C_SWIMCELTIE
        mosiyike_inputs = json.loads((Path(__file__).parent /
                                     "fixtures/balance_20260927c_mosiyike.json").read_bytes())["inputs"]
        mosiyike_layer = C_MOSIYIKE.revise(
            lambda kind, key: mosiyike_inputs[kind]["|".join(key) if kind == "table" else key])
        swim_reads = {(k, key): deepcopy(v) for k, key, v in json.loads(
            (Path(__file__).parent / "fixtures/balance_20260927c_swimceltie.json").read_bytes())["reads"]}
        swimceltie_layer = C_SWIMCELTIE.revise(lambda kind, key: swim_reads[kind, key])
        later_layers = {"149997": mosiyike_layer, "149996": swimceltie_layer}

        for cid in CIDS:
            layer = later_layers.get(cid, {})
            for (kind, key), want in M.BEFORE_BY_CID[cid].items():
                got = M.digest(live_value(kind, key))
                allowed = {want}
                after = imported(cid, kind, key)
                if after is not None:
                    allowed.add(M.digest(after))
                table = layer.get(kind)
                later = table.get(key) if isinstance(table, dict) else None
                if later is not None:
                    allowed.add(M.digest(later))
                self.assertIn(got, allowed, (cid, kind, key))

    @unittest.skipUnless(LOCAL_STORE and (ROOT / "work/character_packs/mosiyike/package/manifest.json").is_file()
                         and (ROOT / "work/character_packs/seofon_wind/package/manifest.json").is_file(),
                         "local candidate workspaces required")
    def test_candidates_open_with_the_reviewed_drift(self):
        from wf_character_revision import RevisionCandidate
        for unit in M.UNITS + M.ART_UNITS:
            for pkg in unit["PACKAGES"]:
                workspace = ROOT / "work/character_packs" / pkg
                before = (workspace / "package/manifest.json").read_bytes()
                meta = json.loads(before)
                RevisionCandidate(ROOT, workspace, reviewed_input_drift=unit["REVIEWED_DRIFT"],
                                  character_id=unit["CID"], code_name=unit["CODE"],
                                  snapshot_key="revision_20260927b",
                                  package_version=unit["PACKAGE_VERSION"][pkg],
                                  baseline_factory=lambda *a, **k: None)
                version = tuple(map(int, meta["package_version"].split(".")))
                # 不降级：候选现值不得高于 gray3 及其后续轮次为该包声明的最高版本（希耶提：UNITS 1.0.3 →
                # ART_UNITS / seofonart 1.0.4；墨斯伊克：UNITS 0.1.2 → wf_balance_20260927c_mosiyike 0.1.3）。
                import wf_balance_20260927c_mosiyike as C_MOSIYIKE
                import wf_balance_20260927c_seofonart as C_SEOFONART
                later = [dict(PACKAGE_VERSION=C_MOSIYIKE.PACKAGE_VERSION)] + list(C_SEOFONART.UNITS)
                declared = max(tuple(map(int, u["PACKAGE_VERSION"][pkg].split(".")))
                               for u in M.UNITS + M.ART_UNITS + later if pkg in u["PACKAGE_VERSION"])
                self.assertLessEqual(version, declared, pkg)
                self.assertEqual(before, (workspace / "package/manifest.json").read_bytes())

    @unittest.skipUnless(LOCAL_STORE, "local live store required")
    def test_referenced_effects_and_sounds_exist(self):
        import wf_assets
        import wf_mod_tool as core
        store = Path(core.resolve_active_store())
        imported = {m.split(":", 1)[1] for cid in CIDS for m in self.out[cid]["files"]}

        def present(logical):
            return logical in imported or wf_assets.locate(store, logical) is not None
        for cid in CIDS:
            for program, tree in self.out[cid]["dsl"].items():
                for node in commands(tree, "ShowEffect"):
                    path = node[2][1]
                    folder = path.rsplit("/", 1)[0]
                    for logical in (f"{path}.parts.amf3.deflate", f"{path}.timeline.amf3.deflate",
                                    f"{folder}/{folder.rsplit('/', 1)[1]}.png",
                                    f"{folder}/{folder.rsplit('/', 1)[1]}.atlas.amf3.deflate"):
                        self.assertTrue(present(logical), (program, logical))
        self.assertIsNotNone(wf_assets.locate(store, "sound_effect/wind/se_swift_tornado.mp3"))


class Batch2InterplayTests(unittest.TestCase):
    def test_batch2_modules_are_untouched_history(self):
        """第二批模块本身不改：它们的 BEFORE 仍是 1.4.1049 的输入，gray3 只在其后叠加。"""
        self.assertEqual(B2_MOSIYIKE.PACKAGE_VERSION, {"mosiyike": "0.1.1"})
        self.assertEqual(B2_SIETE.PACKAGE_VERSION, {"seofon_wind": "1.0.2"})
        self.assertEqual(M.SPECS["149997"]["version"]["mosiyike"], "0.1.2")
        self.assertEqual(M.SPECS["149995"]["version"]["seofon_wind"], "1.0.3")


if __name__ == "__main__":
    unittest.main()
