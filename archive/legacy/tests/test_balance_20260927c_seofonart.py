# -*- coding: utf-8 -*-
"""希耶提灰版美术（``wf_balance_20260927c_seofonart``；作者 2026-09-27 选「换成灰版美术」）。

夹具 ``fixtures/balance_20260927c_seofonart.json``：BEFORE 覆盖的 43 个 live 输入（本地链尾 1.4.1054，gray3 核心导入后，
extra5 ``make_read(live_only=True)`` 只读取数；键 ``"<kind>|<json key>"``）。灰方来源用夹具桩（``file_path`` 给
``GRAY_ROOT`` 下的规范路径）；本机有解出目录 / live store / 候选包时另跑真来源用例。
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest
import zlib

pass  # Imports resolve from this checkout/package, not external source copies.
sys.setrecursionlimit(10000)

import wf_balance_20260927b_gray3 as G3  # noqa: E402
import wf_balance_20260927c_seofonart as M  # noqa: E402
import wf_share_update_codec as X  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927c_seofonart.json'
DATA = json.loads(FIXTURE.read_text(encoding="utf-8"))
FAKE_ROOT = Path("Z:/seofonart-fixture/production")
WORKSPACE = ROOT / "work/character_packs/seofon_wind"
REGISTRY = WORKSPACE / "gray_art_20260927.py"
LOCAL_STORE = (ROOT / "mod-tools/profiles.json").is_file()


def live_key(kind, key) -> str:
    return f"{kind}|{json.dumps(list(key) if isinstance(key, tuple) else key, ensure_ascii=False)}"


def reader(live: dict):
    def read(kind, key):
        name = live_key(kind, key)
        if name not in live:
            raise KeyError(name)
        return deepcopy(live[name])
    return read


class FixtureGray:
    """与 gray3.ArchiveSource 同接口（revise_art 只用 file_path）。"""

    def file_path(self, tier, logical):
        return str(G3.ArchiveSource(FAKE_ROOT).path(tier, logical))


def run(live=None, gray=None):
    return M.revise(reader(deepcopy(DATA["live"]) if live is None else live),
                    FixtureGray() if gray is None else gray)


def load_registry():
    spec = importlib.util.spec_from_file_location("seofon_gray_art_20260927_probe", REGISTRY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SeofonArtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = run()

    # ------------------------------------------------------------ 接口与作者决定

    def test_contract_constants(self):
        self.assertEqual((M.CID, M.CODE, M.PACKAGES), ("149995", "seofon_wind", ["seofon_wind"]))
        (art_unit,) = G3.ART_UNITS
        self.assertEqual(M.PACKAGE_VERSION, {"seofon_wind": "1.0.4"})               # 候选现值 1.0.3 → 递增
        self.assertEqual(M.PACKAGE_VERSION, art_unit["PACKAGE_VERSION"])
        self.assertEqual((M.CAPABILITIES, M.REVIEWED_DRIFT), ([], {}))
        self.assertIs(M.BEFORE, G3.ART_BEFORE_BY_CID["149995"])
        self.assertEqual(M.BEFORE, art_unit["BEFORE"])
        (unit,) = M.UNITS
        self.assertEqual((unit["CID"], unit["CODE"], unit["PACKAGES"], unit["PACKAGE_VERSION"]),
                         (M.CID, M.CODE, M.PACKAGES, M.PACKAGE_VERSION))
        self.assertEqual((unit["CAPABILITIES"], unit["REVIEWED_DRIFT"]), ([], {}))
        self.assertIs(unit["revise"], M.revise)
        self.assertTrue(unit["REQUIRES_AUTHOR_SIGNOFF"])

    def test_author_decision_is_recorded(self):
        self.assertEqual(G3.ART_DECISION["149995"], G3.ART_ACCEPTED)
        self.assertEqual(M.AUTHOR_DECISION["answer"], "换成灰版美术")
        self.assertEqual(M.AUTHOR_DECISION["date"], "2026-09-27")
        self.assertIn("1.4.447", M.AUTHOR_DECISION["question"])
        self.assertIn("4 条构图检查按作者决定放宽", M.AUTHOR_DECISION["scope"])
        notes = self.out["notes"]
        json.dumps(notes, ensure_ascii=False)
        self.assertEqual(notes["author_decision"], M.AUTHOR_DECISION)
        self.assertFalse(notes["runtime_verified"])
        self.assertEqual(notes["art"]["decision"], G3.ART_ACCEPTED)
        self.assertEqual(notes["art"]["status"], "imported")
        self.assertEqual((notes["package"]["version_from"], notes["package"]["version_to"]), ("1.0.3", "1.0.4"))
        red = G3.ART_REVIEW["149995"]["package_tests_red_if_accepted"]
        self.assertEqual(len(notes["package"]["test_exemptions"]), len(red))
        for exemption, test in zip(notes["package"]["test_exemptions"], red):
            self.assertEqual(exemption.split("（", 1)[0], test.split("（", 1)[0])

    # ------------------------------------------------------------ 基线

    def test_fixture_is_the_before_baseline(self):
        self.assertEqual(set(DATA["live"]), {live_key(kind, key) for kind, key in M.BEFORE})
        for (kind, key), want in M.BEFORE.items():
            self.assertEqual(M.digest(DATA["live"][live_key(kind, key)]), want, (kind, key))
        kinds = sorted({kind for kind, _ in M.BEFORE})
        self.assertEqual(kinds, ["file_sha256", "nested_table", "table"])           # 只锁美术输入

    def test_before_drift_is_rejected(self):
        for kind, key in M.BEFORE:
            live = deepcopy(DATA["live"])
            live[live_key(kind, key)] = "0" * 64 if kind == "file_sha256" else [["drifted"]]
            with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
                run(live=live)
        live = deepcopy(DATA["live"])
        del live[live_key("file_sha256", ("medium", "character/seofon_wind/ui/square_0.png"))]
        with self.assertRaisesRegex(ValueError, "live input unreadable"):
            run(live=live)

    def test_not_reapplicable_after_import(self):
        after = deepcopy(DATA["live"])
        for (logical, key), value in self.out["presentation_table"].items():
            after[live_key(*G3.before_key(logical, key))] = deepcopy(value)
        for member in self.out["files"]:
            after[live_key("file_sha256", tuple(member.split(":", 1)))] = G3.GRAY_FILES[member]
        with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
            run(live=after)

    def test_inputs_not_mutated_and_output_detached(self):
        live = deepcopy(DATA["live"])
        out = run(live=live)
        self.assertEqual(live, DATA["live"])
        key = (G3.CIMG, "149995")
        out["presentation_table"][key]["0"][0][0] = "mutated"
        out["notes"]["author_decision"]["answer"] = "mutated"
        out["notes"]["file_sha256"].clear()
        self.assertEqual(G3.PRESENTATION_ROWS[key]["0"][0][0], "283")
        self.assertEqual(M.AUTHOR_DECISION["answer"], "换成灰版美术")
        again = run()
        self.assertEqual(M.digest({"|".join(k): v for k, v in again["presentation_table"].items()}),
                         M.digest({"|".join(k): v for k, v in self.out["presentation_table"].items()}))
        self.assertNotEqual(M.digest({"|".join(k): v for k, v in out["presentation_table"].items()}),
                            M.digest({"|".join(k): v for k, v in self.out["presentation_table"].items()}))
        self.assertEqual(len(again["notes"]["file_sha256"]), 27)

    # ------------------------------------------------------------ 结果

    def test_change_set_is_the_reviewed_art(self):
        self.assertEqual(G3.signature(self.out), G3.REVIEWED_ART["149995"])
        for kind in ("ability", "leader", "cas", "text", "action", "dsl", "server_text", "server_character",
                     "table", "nested_table"):
            self.assertEqual(self.out[kind], {}, kind)
        self.assertEqual(self.out["new_programs"], [])

    def test_art_files_are_the_gray_bytes(self):
        files, pins = self.out["files"], self.out["notes"]["file_sha256"]
        self.assertEqual(len(files), 27)
        self.assertEqual(sorted(pins), sorted(files))
        tiers = sorted(member.split(":", 1)[0] for member in files)
        self.assertEqual((tiers.count("medium"), tiers.count("android")), (25, 2))
        for member, path in files.items():
            tier, logical = member.split(":", 1)
            self.assertEqual(pins[member], G3.GRAY_FILES[member], member)             # 钉灰版字节
            self.assertTrue(G3.is_art(member, "seofon_wind"), member)
            self.assertTrue(logical.startswith("character/seofon_wind/ui/"), member)
            self.assertNotEqual(DATA["live"][live_key("file_sha256", (tier, logical))], pins[member], member)
            self.assertEqual(path, str(G3.ArchiveSource(FAKE_ROOT).path(tier, logical)))
        # 压缩包里其余 10 个希耶提美术成员（common 像素小人/图集/详情预览）与 live 同字节，不导入。
        same = [m for m in G3.GRAY_FILES if G3.is_art(m, "seofon_wind") and m.split(":", 1)[0] in G3.IMPORT_TIERS
                and G3.owns_file(m.split(":", 1)[1], "seofon_wind") and m not in files]
        self.assertEqual(len(same), 10)
        for member in same:
            self.assertEqual(DATA["live"][live_key("file_sha256", tuple(member.split(":", 1)))], G3.GRAY_FILES[member])

    def test_presentation_rows_are_the_gray_rows(self):
        rows = self.out["presentation_table"]
        self.assertEqual(len(rows), 5)                                               # 5 条定位行
        for (logical, key), value in rows.items():
            self.assertEqual(M.digest(value), M.digest(G3.PRESENTATION_ROWS[logical, key]), (logical, key))
        cutin_1 = (G3.TRIM, "character/seofon_wind/ui/skill_cutin_1")
        self.assertNotIn(cutin_1, rows)                                               # 灰我相同，不返回
        self.assertEqual(DATA["live"][live_key("table", cutin_1)], G3.PRESENTATION_ROWS[cutin_1])
        for slot in ("0", "1"):                                                       # 两表 tx/ty 一致、2000 画布
            x, y, w, h = rows[G3.CIMG, "149995"][slot][0]
            trim = rows[G3.TRIM, f"character/seofon_wind/ui/full_shot_1440_1920_{slot}"][0]
            self.assertEqual(trim, [x, y, "2000", "2000"])
            self.assertTrue(int(x) + int(w) <= 2000 and int(y) + int(h) <= 2000)
            self.assertEqual(rows[G3.FSA, "149995"][slot][0][:3], ["1000", "1000", "1"])
        # 作者知情接受的构图（ART_REVIEW）：觉醒脸锚 874 出官方带、两槽不同高。
        faces = {slot: int(rows[G3.FSA, "149995"][slot][0][4]) for slot in ("0", "1")}
        self.assertEqual(faces, {"0": 545, "1": 874})

    def test_presentation_rows_encode_without_trailing_newline(self):
        """暂存字节 = gray3.encode_presentation：与 live 同格式，内层 CSV 无尾换行（X.csv_write 会带 \\n）。"""
        for (logical, key), value in self.out["presentation_table"].items():
            raw = G3.encode_presentation(logical, value)
            if logical in G3.NESTED_TABLES:
                inner = X.unpack(raw)
                self.assertEqual(list(inner), list(value))
                texts = [zlib.decompress(v).decode("utf-8") for v in inner.values()]
                self.assertEqual(texts, [",".join(rows[0]) for rows in value.values()])
            else:
                texts = [zlib.decompress(raw).decode("utf-8")]
                self.assertEqual(texts, [",".join(value[0])])
            self.assertFalse(any(text.endswith("\n") for text in texts), (logical, key))
            self.assertEqual(M.digest(G3.decode_value(logical, raw)), M.digest(value), (logical, key))
            self.assertEqual(texts[0].split(",")[-1].strip(), texts[0].split(",")[-1])
        self.assertTrue(zlib.decompress(X.csv_write([["283", "270", "2000", "2000"]])).endswith(b"\n"))
        # live 行本身也无尾换行（与夹具同源）。
        for (kind, key), _ in M.BEFORE.items():
            if kind == "nested_table":
                value = DATA["live"][live_key(kind, key)]
                raw = G3.encode_presentation(key[0], value)
                self.assertFalse(any(zlib.decompress(v).endswith(b"\n") for v in X.unpack(raw).values()))

    # ------------------------------------------------------------ 本机：灰方解出目录 / 包内豁免登记 / live / 候选

    @unittest.skipUnless(G3.GRAY_ROOT.is_dir(), "灰服压缩包解出目录不在本机")
    def test_extracted_gray_files_hash_to_the_pins(self):
        out = M.revise(reader(deepcopy(DATA["live"])))                                # 默认 ArchiveSource()
        self.assertEqual(G3.signature(out), G3.signature(self.out))
        for member, path in out["files"].items():
            self.assertTrue(Path(path).is_relative_to(G3.GRAY_ROOT), path)
            self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(), out["notes"]["file_sha256"][member])

    @unittest.skipUnless(REGISTRY.is_file(), "希耶提包工作区不在本机")
    def test_package_exemption_registry_is_exactly_the_gray_art(self):
        registry = load_registry()
        self.assertEqual(registry.GRAY_ART_SHA256, self.out["notes"]["file_sha256"])
        self.assertEqual(registry.DECISION, "作者 2026-09-27 选择灰版美术")
        member = "medium:character/seofon_wind/ui/skill_cutin_0.png"
        tier, logical = member.split(":", 1)
        self.assertFalse(registry.is_gray_art(tier, logical, b"regenerated bytes"))  # 字节变了 ⇒ 检查恢复
        self.assertFalse(registry.is_gray_art("medium", "character/seofon_wind/ui/other.png", b""))
        source = REGISTRY.read_text(encoding="utf-8")
        self.assertIn("换成灰版美术", source)

    @unittest.skipUnless(LOCAL_STORE, "local live store required")
    def test_live_is_either_the_baseline_or_the_import(self):
        import wf_assets
        import wf_mod_tool as core
        store = Path(core.resolve_active_store())

        def live_value(kind, key):
            if kind in ("table", "nested_table"):
                logical, outer = key
                return G3.decode_value(logical, X.unpack(core.table_path(store, logical).read_bytes())[outer])
            tier, logical = key
            path = core.table_path(store, logical) if tier == "common" else wf_assets.path_in_root(store, tier, logical)
            return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None

        for (kind, key), want in M.BEFORE.items():
            got = M.digest(live_value(kind, key))
            if kind == "file_sha256":
                member = ":".join(key)
                after = self.out["notes"]["file_sha256"].get(member)
            else:
                after = self.out["presentation_table"].get(tuple(key))
            allowed = {want} | ({M.digest(after)} if after is not None else set())
            self.assertIn(got, allowed, (kind, key))

    @unittest.skipUnless(LOCAL_STORE and (WORKSPACE / "package/manifest.json").is_file(),
                         "local candidate workspace required")
    def test_candidate_opens_clean_and_is_not_downgraded(self):
        from wf_character_revision import RevisionCandidate
        manifest = WORKSPACE / "package/manifest.json"
        before = manifest.read_bytes()
        RevisionCandidate(ROOT, WORKSPACE, reviewed_input_drift=M.REVIEWED_DRIFT, character_id=M.CID,
                          code_name=M.CODE, snapshot_key="revision_20260927d",
                          package_version=M.PACKAGE_VERSION["seofon_wind"], baseline_factory=lambda *a, **k: None)
        meta = json.loads(before)
        version = meta["package_version"]
        self.assertIn(version, {"1.0.3", "1.0.4"})                                  # 暂存前 / 暂存后
        self.assertEqual(before, manifest.read_bytes())
        if meta.get("snapshot", {}).get("revision_20260927d") is not None:
            # 已回写：包内这 27 个文件必须仍是灰版字节（作者 09-27 选择灰版美术），
            # 防止重跑 seofon_art.py / build_workspace.py 把旧图静默换回来。
            roots = {(tier, e["logical_path"]): e["sha256"]
                     for tier, entries in meta["roots"].items() for e in entries}
            for member, want in self.out["notes"]["file_sha256"].items():
                tier, logical = member.split(":", 1)
                self.assertEqual(want, roots.get((tier, logical)), member)
                self.assertEqual(want, hashlib.sha256((WORKSPACE / "package/roots" / tier / logical)
                                                      .read_bytes()).hexdigest(), member)


if __name__ == "__main__":
    unittest.main()
