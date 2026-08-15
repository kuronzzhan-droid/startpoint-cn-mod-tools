#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Custom client drop-source orderedmap contract tests."""

from __future__ import annotations

import unittest
from pathlib import Path

import wf_abyss_gacha_drop_source as module
import wf_mod_tool as core


class DropSourceTests(unittest.TestCase):
    def _server(self):
        return {"events": {"700099": {"folder_clear_chance": [
            {"type": 0, "id": 999014, "count": 1, "chance": 0.05},
            {"type": 0, "id": 11003, "count": 1, "chance": 0.5},
        ]}}}

    def test_builds_and_strictly_reads_the_single_owned_drop_row(self):
        payload = module.build_drop_source(self._server())

        self.assertEqual({
            "event_id": 700099,
            "rewards": [
                {"folder_id": 1, "type": 0, "id": 999014, "count": 1, "chance": 0.05},
                {"folder_id": 1, "type": 0, "id": 11003, "count": 1, "chance": 0.5},
            ],
        }, module.parse_drop_source(payload))
        self.assertEqual(
            {"700099": "1,0,999014,1,0.05\n1,0,11003,1,0.5"},
            core.read_orderedmap_file_from_bytes(payload),
        )

    def test_rejects_extra_rows_noncanonical_values_and_mirror_drift(self):
        valid = module.build_drop_source(self._server())
        rows = core.read_orderedmap_file_from_bytes(valid)
        rows["700098"] = rows["700099"]
        extra = core.build_orderedmap(core.OrderedMap(
            module.LOGICAL_PATH,
            list(rows),
            [value.encode() for value in rows.values()],
            Path("<fixture>"),
        ))
        with self.assertRaisesRegex(ValueError, "exactly one"):
            module.parse_drop_source(extra)

        missing = self._server()
        missing["events"]["700099"]["folder_clear_chance"].pop()
        with self.assertRaisesRegex(ValueError, "exactly two"):
            module.build_drop_source(missing)

        drifted = self._server()
        drifted["events"]["700099"]["folder_clear_chance"][1]["chance"] = 0.4
        with self.assertRaisesRegex(ValueError, "canonical"):
            module.validate_drop_mirror(
                valid,
                drifted,
            )


if __name__ == "__main__":
    unittest.main()
