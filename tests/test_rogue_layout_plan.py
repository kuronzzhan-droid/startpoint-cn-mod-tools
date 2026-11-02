from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import wf_mod_tool as core
# Plan serialization uses no game tables. Keep the legacy GUI's eager import
# independent of an author's local store/profile when exercising that API.
with mock.patch.object(core, "resolve_active_store", return_value=Path("work/t/rogue-plan-fixture")):
    import wf_gui
from wf.tools.rogue import rogue_build as rogue


class RogueLayoutPlanRoundTripCase(unittest.TestCase):
    def test_gui_replaces_plan_and_builder_reads_the_replacement(self):
        with tempfile.TemporaryDirectory() as tmp:
            tool_dir = Path(tmp)
            first = {
                "stages": [{"from": 1, "to": 15, "tier": "hell"}],
                "floors": {
                    "5": {
                        "curses": ["绝对壁垒"],
                        "field": "battle/action/example/first",
                    }
                },
            }
            replacement = {
                "stages": [{"from": 1, "to": 30, "tier": "elite"}],
                "floors": {"12": {"curses": ["元素禁壁"]}},
            }

            with mock.patch.object(wf_gui, "MOD_DIR", tool_dir), mock.patch.object(
                rogue, "MOD_DIR", str(tool_dir)
            ):
                wf_gui.rogue_plan_save(first)
                self.assertEqual(first, wf_gui.rogue_plan_get())
                self.assertEqual(first, rogue.layout_plan())

                wf_gui.rogue_plan_save(replacement)
                self.assertEqual(replacement, wf_gui.rogue_plan_get())
                self.assertEqual(replacement, rogue.layout_plan())
                self.assertNotIn("5", rogue.layout_plan()["floors"])


if __name__ == "__main__":
    unittest.main()
