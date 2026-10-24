"""The generic per-pack verifier must BLOCK malformed equipment-enhanced-party-frame rows
(enhanced_party_frame_override_*), report their own capability (not the v1 look capability), and the
WFX gate must treat the key as cosmetic: clients with only equipment-enhanced-look-v1 get a warning."""
from __future__ import annotations

import csv
import io
import sys
import unittest
from pathlib import Path

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_client_legality as L  # noqa: E402
import wf_midautumn_verify as V  # noqa: E402
import wfx_gate as G  # noqa: E402

PARTY = "enhanced_party_frame_override_item/equipment/mod/paradox/paradox_lv200"
FRAME = "enhanced_frame_override_item/equipment/mod/paradox/paradox_lv200"
GOOD = {PARTY: "item/equipment/mod/paradox/paradox_party_frame_bluegold",
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


class PartyFramePackGateTest(unittest.TestCase):
    def _run(self, texts, declared=(L.EQUIPMENT_ENHANCED_LOOK, L.EQUIPMENT_ENHANCED_PARTY_FRAME)):
        rep = V.Report()
        V.check_capabilities(_Pack(texts, declared), rep)
        return rep, {c["name"]: c for c in rep.checks}

    def test_well_formed_rows_pass_and_need_both_capabilities(self):
        rep, checks = self._run({key: quoted(value) for key, value in GOOD.items()})
        self.assertTrue(checks[NAME]["pass"], checks[NAME])
        self.assertEqual(sorted(GOOD), checks[NAME]["evidence"]["enhanced_look_keys"])
        self.assertEqual(sorted([L.EQUIPMENT_ENHANCED_LOOK, L.EQUIPMENT_ENHANCED_PARTY_FRAME]),
                         checks["manifest/capability-covers-rows"]["evidence"]["needed"])
        self.assertEqual([], rep.blocking)

    def test_declaring_only_the_v1_look_capability_blocks(self):
        """编成槽框键归新 capability:manifest 只声明 v1 = 没覆盖到这一行。"""
        rep, checks = self._run({key: quoted(value) for key, value in GOOD.items()},
                                declared=(L.EQUIPMENT_ENHANCED_LOOK,))
        self.assertFalse(checks["manifest/capability-covers-rows"]["pass"])
        self.assertIn(L.EQUIPMENT_ENHANCED_PARTY_FRAME,
                      "\n".join(checks["manifest/capability-covers-rows"]["evidence"].get("problems", [])))
        self.assertTrue(checks[NAME]["pass"])

    def test_party_key_alone_needs_only_its_capability(self):
        rep, checks = self._run({PARTY: quoted(GOOD[PARTY])}, declared=(L.EQUIPMENT_ENHANCED_PARTY_FRAME,))
        self.assertEqual([L.EQUIPMENT_ENHANCED_PARTY_FRAME],
                         checks["manifest/capability-covers-rows"]["evidence"]["needed"])
        self.assertEqual([], rep.blocking)

    def test_malformed_values_and_keys_block(self):
        for texts in ({PARTY: quoted("")}, {PARTY: quoted("a,b")}, {PARTY: quoted("a.png")},
                      {PARTY + " ": quoted(GOOD[PARTY])}, {PARTY + "/": quoted(GOOD[PARTY])},
                      {PARTY: quoted("item/x") + "\n" + quoted("item/y")}):
            with self.subTest(texts=texts):
                rep, checks = self._run(texts)
                self.assertFalse(checks[NAME]["pass"])
                self.assertIn(NAME, [c["name"] for c in rep.blocking])


class PartyFrameWfxGateTest(unittest.TestCase):
    def test_party_key_is_cosmetic_and_names_its_own_capability(self):
        for profile in ("gray-1047", "official"):
            with self.subTest(profile=profile):
                report = G.check({}, {}, [PARTY], profile)
                self.assertTrue(report.ok, report.problems)
                self.assertEqual([L.EQUIPMENT_ENHANCED_PARTY_FRAME], report.required_capabilities())
                self.assertEqual(1, len(report.warnings))
                self.assertIn(L.EQUIPMENT_ENHANCED_PARTY_FRAME, report.warnings[0])

    def test_a_v1_only_client_is_warned_and_a_patched_client_is_quiet(self):
        base = G.load_profiles()["local-mumu"].capabilities
        v1_only = G.ClientProfile("v1-only", (base | {L.EQUIPMENT_ENHANCED_LOOK}) - {L.EQUIPMENT_ENHANCED_PARTY_FRAME})
        report = G.check({}, {}, [PARTY, FRAME], v1_only)
        self.assertTrue(report.ok)
        self.assertEqual(1, len(report.warnings))
        self.assertIn(L.EQUIPMENT_ENHANCED_PARTY_FRAME, report.warnings[0])
        patched = G.ClientProfile("party", v1_only.capabilities | {L.EQUIPMENT_ENHANCED_PARTY_FRAME})
        report = G.check({}, {}, [PARTY, FRAME], patched)
        self.assertTrue(report.ok)
        self.assertEqual([], report.warnings)


if __name__ == "__main__":
    unittest.main()
