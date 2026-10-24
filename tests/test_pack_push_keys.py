# -*- coding: utf-8 -*-
"""wf_pack_push_keys 的门禁：只搬点名的键，别家键逐字节不动，坏输入必须报错。

用临时 store + 临时包，不读 live。
"""
from __future__ import annotations

import sys
import unittest
import zlib
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import wf_mod_tool as core  # noqa: E402
import wf_pack_push_keys as P  # noqa: E402

LOGICAL = "master/ability/ability.orderedmap"


def table_bytes(rows: dict[str, str]) -> bytes:
    return core.build_orderedmap_raw_rows(core.OrderedMap(
        LOGICAL, list(rows), [zlib.compress(v.encode("utf-8")) for v in rows.values()], Path(LOGICAL)))


class ParseTargetsTest(unittest.TestCase):
    def test_parses_multiple_keys_and_tables(self):
        got = P.parse_targets([f"{LOGICAL}:1,2", "master/x/y.orderedmap:a"])
        self.assertEqual(got, {LOGICAL: ["1", "2"], "master/x/y.orderedmap": ["a"]})

    def test_merges_repeated_table(self):
        self.assertEqual(P.parse_targets([f"{LOGICAL}:1", f"{LOGICAL}:2"]), {LOGICAL: ["1", "2"]})

    def test_rejects_bad_input(self):
        for bad in (["no-colon"], [f"{LOGICAL}:"], [f"{LOGICAL}: , "]):
            with self.assertRaises(P.PushError, msg=bad):
                P.parse_targets(bad)

    def test_rejects_duplicate_key(self):
        with self.assertRaises(P.PushError):
            P.parse_targets([f"{LOGICAL}:1,1"])


class PlanTest(unittest.TestCase):
    def setUp(self) -> None:
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.store = self.root / "store"
        self.ws = self.root / "ws"
        self.live = {"1": "live-one", "2": "live-two", "3": "live-three"}
        self.pkg = {"1": "pkg-one", "2": "live-two", "3": "pkg-three"}
        path = core.table_path(self.store, LOGICAL)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(table_bytes(self.live))
        pkg_path = self.ws / "package" / "roots" / "common" / Path(*LOGICAL.split("/"))
        pkg_path.parent.mkdir(parents=True, exist_ok=True)
        pkg_path.write_bytes(table_bytes(self.pkg))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def plan(self, keys):
        return P.plan_one(self.store, self.ws, LOGICAL, keys)

    def test_only_named_keys_move(self):
        plan = self.plan(["1"])
        after = core.read_orderedmap_file_from_bytes(plan["updated"])
        self.assertEqual(after["1"], "pkg-one")
        self.assertEqual(after["2"], "live-two")
        self.assertEqual(after["3"], "live-three")     # 未点名 ⇒ 不动

    def test_untouched_keys_keep_original_bytes(self):
        plan = self.plan(["1"])
        before = core.read_orderedmap_raw_rows_from_bytes(plan["original"], LOGICAL)
        after = core.read_orderedmap_raw_rows_from_bytes(plan["updated"], LOGICAL)
        self.assertEqual(after.keys, before.keys)       # 键序不变
        for key, b, a in zip(before.keys, before.rows, after.rows):
            if key == "1":
                continue
            self.assertEqual(a, b, key)                 # 压缩字节逐字相同

    def test_reports_whether_each_key_changed(self):
        plan = self.plan(["1", "2"])
        self.assertEqual([(c["key"], c["changed"]) for c in plan["keys"]], [("1", True), ("2", False)])

    def test_rejects_key_missing_in_live(self):
        with self.assertRaises(P.PushError):
            self.plan(["9"])

    def test_rejects_key_missing_in_package(self):
        pkg_path = self.ws / "package" / "roots" / "common" / Path(*LOGICAL.split("/"))
        pkg_path.write_bytes(table_bytes({"2": "live-two"}))
        with self.assertRaises(P.PushError):
            self.plan(["1"])

    def test_rejects_missing_package_table(self):
        pkg_path = self.ws / "package" / "roots" / "common" / Path(*LOGICAL.split("/"))
        pkg_path.unlink()
        with self.assertRaises(P.PushError):
            self.plan(["1"])

    def test_rejects_missing_live_table(self):
        core.table_path(self.store, LOGICAL).unlink()
        with self.assertRaises(P.PushError):
            self.plan(["1"])

    def test_idempotent(self):
        plan = self.plan(["1", "3"])
        core.table_path(self.store, LOGICAL).write_bytes(plan["updated"])
        again = self.plan(["1", "3"])
        self.assertEqual(again["updated"], plan["updated"])
        self.assertEqual([c["changed"] for c in again["keys"]], [False, False])


if __name__ == "__main__":
    unittest.main()
