from __future__ import annotations

import sys
import unittest
from pathlib import Path


MOD_TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MOD_TOOLS))

import wf_describe  # noqa: E402


class DescribeInstantDelayTests(unittest.TestCase):
    def test_instant_delay_cell_is_encoded_in_seconds(self) -> None:
        layout = wf_describe.layout("ability")
        blocks = {name: int(index) for name, index in layout["blocks"].items()}
        row = [""] * int(layout["ncols"])
        row[blocks["precondition1"] - 1] = "0"
        for name in ("precondition1", "precondition2", "precondition3"):
            row[blocks[name]] = "0"
        row[blocks["instant_trigger"]] = "0"
        row[blocks["instant_precontent"]] = "(None)"
        row[blocks["instant_delay"]] = "2"
        row[blocks["instant_content"]] = "211"

        description = wf_describe.describe_line(row, "ability")

        self.assertIn("延迟2秒", description)
        self.assertNotIn("0.0333333", description)


if __name__ == "__main__":
    unittest.main()
