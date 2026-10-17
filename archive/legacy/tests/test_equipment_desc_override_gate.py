"""The generic per-pack verifier must BLOCK malformed
desc_override_equipment_* keys (it already reports the capability for them)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_client_legality as L
import wf_midautumn_verify as V

GOOD = ("desc_override_equipment_5920001",
        "desc_override_equipment_enhancement_5920001",
        "desc_override_equipment_enhancement_5920001_final")
BAD = ("desc_override_equipment_05920001",              # leading zero: int id never renders like this
       "desc_override_equipment_5920001_final",         # _final on the base key
       "desc_override_equipment_enhancement_",          # no id
       "desc_override_equipment_５９２",    # full-width digits
       "desc_override_equipment_enhancement_5920001_final\n",  # trailing newline
       " desc_override_equipment_5920001")              # leading space


class _CapPack:
    """check_capabilities reads manifest / owned_keys / rows only."""

    def __init__(self, cas_keys, declared):
        self.manifest = {"required_capabilities": list(declared)}
        self._cas = list(cas_keys)

    def owned_keys(self, logical, root="common"):
        return list(self._cas) if logical == V.CAS else []

    def rows(self, logical, key):
        return []


class EquipmentOverrideKeyShapeGateTest(unittest.TestCase):
    NAME = "cas/equipment-desc-override-key-shape"

    def _run(self, keys, declared=(L.EQUIPMENT_DESC_OVERRIDE,)):
        rep = V.Report()
        V.check_capabilities(_CapPack(keys, declared), rep)
        return rep, {c["name"]: c for c in rep.checks}

    def test_the_three_patch_key_shapes_pass(self):
        rep, checks = self._run(GOOD)
        self.assertIn(self.NAME, checks)
        self.assertTrue(checks[self.NAME]["pass"])
        self.assertEqual(sorted(GOOD), checks[self.NAME]["evidence"]["equipment_override_keys"])
        self.assertTrue(checks["manifest/capability-covers-rows"]["pass"])
        self.assertEqual([], rep.blocking)

    def test_every_malformed_equipment_key_blocks(self):
        for bad in BAD:
            with self.subTest(key=bad):
                rep, checks = self._run(GOOD + (bad,))
                self.assertIn(self.NAME, checks)
                check = checks[self.NAME]
                self.assertFalse(check["pass"])
                self.assertEqual(V.BLOCKING, check["level"])
                self.assertEqual(1, check["evidence"]["total"])
                self.assertIn(repr(bad), check["evidence"]["problems"][0])
                self.assertEqual([self.NAME], [c["name"] for c in rep.blocking])

    def test_non_equipment_override_keys_are_not_this_gates_business(self):
        keys = ("desc_override_tweyen_light_3", "desc_override_equipment", "desc_override_equipmentx_1",
                "desc_override_fox_oracle_autumn_1", "skill_description_1")
        rep, checks = self._run(keys, declared=(L.PANEL_OVERRIDE_V1, L.PANEL_OVERRIDE_V2))
        self.assertTrue(checks[self.NAME]["pass"])
        self.assertEqual([], checks[self.NAME]["evidence"]["equipment_override_keys"])
        self.assertEqual([], rep.blocking)


if __name__ == "__main__":
    unittest.main()
