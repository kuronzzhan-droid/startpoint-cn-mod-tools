# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest
from pathlib import Path


MOD_TOOLS = Path(__file__).resolve().parent.parent


class BalanceStoreWiringTest(unittest.TestCase):
    def test_balance_writers_use_the_required_active_store_chain(self) -> None:
        for name in (
            "wf_all_analysis.py",
            "wf_balance_patch.py",
            "wf_balance_patch_v2.py",
            "wf_balance_suite.py",
            "wf_describe.py",
            "wf_dsl.py",
            "wf_fire_analysis.py",
            "wf_unique_mech.py",
        ):
            with self.subTest(name=name):
                source = (MOD_TOOLS / name).read_text(encoding="utf-8")
                self.assertIn("core.require_active_store()", source)
                self.assertNotIn("core.resolve_profile()", source)


if __name__ == "__main__":
    unittest.main()
