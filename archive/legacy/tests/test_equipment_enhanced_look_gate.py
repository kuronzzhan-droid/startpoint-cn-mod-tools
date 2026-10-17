"""The generic per-pack verifier must BLOCK malformed equipment-enhanced-look rows
(enhanced_pixelart_tier2_* / enhanced_frame_override_*) and report their capability."""
from __future__ import annotations

import csv
import io
import sys
import unittest
from pathlib import Path

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_client_legality as L  # noqa: E402
import wf_midautumn_verify as V  # noqa: E402

TIER2 = "enhanced_pixelart_tier2_item/equipment/mod/paradox/paradox_lv120"
FRAME = "enhanced_frame_override_item/equipment/mod/paradox/paradox_lv200"
GOOD = {TIER2: "200,item/equipment/mod/paradox/paradox_lv200",
        FRAME: "item/equipment/mod/paradox/paradox_frame_bluegold"}
NAME = "cas/equipment-enhanced-look-shape"


def quoted(value: str) -> str:
    """wf_mod_tool.write_csv_lines 的写法:csv.writer,含逗号的格自动加引号。"""
    buf = io.StringIO()
    csv.writer(buf, lineterminator="").writerow([value])
    return buf.getvalue()


class _Pack:
    """check_capabilities reads manifest / owned_keys / rows only."""

    def __init__(self, texts, declared):
        self.manifest = {"required_capabilities": list(declared)}
        self._texts = dict(texts)

    def owned_keys(self, logical, root="common"):
        return list(self._texts) if logical == V.CAS else []

    def rows(self, logical, key):
        return V.split_rows(self._texts.get(key, "")) if logical == V.CAS else []


class EnhancedLookPackGateTest(unittest.TestCase):
    def _run(self, texts, declared=(L.EQUIPMENT_ENHANCED_LOOK,)):
        rep = V.Report()
        V.check_capabilities(_Pack(texts, declared), rep)
        return rep, {c["name"]: c for c in rep.checks}

    def test_well_formed_quoted_rows_pass_and_need_the_capability(self):
        rep, checks = self._run({key: quoted(value) for key, value in GOOD.items()})
        self.assertTrue(checks[NAME]["pass"], checks[NAME])
        self.assertEqual(sorted(GOOD), checks[NAME]["evidence"]["enhanced_look_keys"])
        self.assertEqual([L.EQUIPMENT_ENHANCED_LOOK], checks["manifest/capability-covers-rows"]["evidence"]["needed"])
        self.assertEqual([], rep.blocking)

    def test_missing_manifest_capability_blocks(self):
        rep, checks = self._run({key: quoted(value) for key, value in GOOD.items()}, declared=())
        self.assertFalse(checks["manifest/capability-covers-rows"]["pass"])
        self.assertTrue(checks[NAME]["pass"])

    def test_unquoted_tier2_row_blocks(self):
        """没加引号:CSV 拆成两格,客户端只读到 "200" → 静默不生效。"""
        rep, checks = self._run({TIER2: GOOD[TIER2], FRAME: quoted(GOOD[FRAME])})
        self.assertFalse(checks[NAME]["pass"])
        self.assertEqual(1, checks[NAME]["evidence"]["total"])
        self.assertIn("一行一格", checks[NAME]["evidence"]["problems"][0])
        self.assertEqual([NAME], [c["name"] for c in rep.blocking])

    def test_malformed_values_and_keys_block(self):
        for texts in ({TIER2: quoted("abc,item/x")}, {TIER2: quoted("200")}, {TIER2: quoted("0200,item/x")},
                      {FRAME: quoted("")}, {FRAME: quoted("a,b")}, {FRAME + " ": quoted(GOOD[FRAME])},
                      {TIER2: quoted("200,item/x") + "\n" + quoted("200,item/y")}):
            with self.subTest(texts=texts):
                rep, checks = self._run(texts)
                self.assertFalse(checks[NAME]["pass"])
                self.assertEqual([NAME], [c["name"] for c in rep.blocking])

    def test_no_look_keys_is_a_pass(self):
        rep, checks = self._run({"desc_override_equipment_5920001": "x"},
                                declared=(L.EQUIPMENT_DESC_OVERRIDE,))
        self.assertTrue(checks[NAME]["pass"])
        self.assertEqual([], checks[NAME]["evidence"]["enhanced_look_keys"])
        self.assertEqual([], rep.blocking)


if __name__ == "__main__":
    unittest.main()
