from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from wf.tools.rogue import rogue_audit_diff as audit_diff
from wf.tools.rogue import rogue_build as rb


def thumbnail_pick_fields(field: str) -> dict:
    thumbnail = "quest/thumbnail/test/boss"
    return {
        "thumb": thumbnail,
        "thumbnail_field": field,
        "thumbnail_evidence": {
            "schema": rb.THUMBNAIL_EVIDENCE_SCHEMA,
            "field": field,
            "thumbnail": thumbnail,
            "asset_logical": thumbnail + ".png",
            "asset_exists": True,
            "source_match": "exact_field",
            "source_category": "test",
            "source_logical": "master/quest/test.orderedmap",
            "source_path": ["test"],
            "source_level": 100,
            "floor_key": None,
            "static_verified": True,
            "runtime_simulated": False,
            "gameplay_verified": False,
        },
    }


class RogueAuditDiffCase(unittest.TestCase):
    def make_document(self) -> dict:
        native = {
            "verified": True, "absolute_verified": True,
            "native_hp": 100.0,
            "components": [{
                "occurrence": 1, "boss_occurrence": 1,
                "code": "source_boss", "phase": "main", "kind": "general",
                "native_hp": 100.0, "evidence_kind": "absolute",
            }],
        }
        receipt = rb.build_hp_adaptation_audit(
            2, native, family="general", channel="boss_level",
            destination="boss_level.c2", baseline_target_hp=100.0,
            final_target_hp=100.0, baseline_c86=1.0, final_c86=1.0)
        damage_checks = {
            "source_boss": rb.general_damage_check_contract(
                {}, {}, {}, source_max_hp=100.0,
                baseline_max_hp=100.0, final_max_hp=100.0,
                source_routine_id="(None)", final_routine_id="(None)",
                materialized=True),
        }
        quest_row = ["(None)"] * 110
        quest_row[86] = quest_row[87] = quest_row[88] = "1"
        return rb.build_hp_audit_document(
            seed=20260826, rounds=2, difficulty="hell", enemy_level="ramp",
            hp_audits=[{
                "r": 2, "adapter_audit": receipt,
                "verified": True, "absolute_verified": True,
                "target_exempt": False,
                "damage_checks": damage_checks,
                "quest_hp_multipliers": rb.quest_hp_multiplier_plan(
                    baseline=1.0, final=1.0, has_boss=True),
            }],
            floor_records=[{
                "r": 2,
                "row": quest_row,
                "pick": {
                    "field": "source_field", "play_field": "mod_rogue_f2",
                    "level": 100, "bosses": ["source_boss"],
                    "runtime_bosses": ["mod_rogue_boss2"],
                    **thumbnail_pick_fields("source_field"),
                },
                "curse": {"picks": [], "desc": "", "combo": None},
            }],
            chain_reports=[
                {"round": "1", "ok": True},
                {"round": "2", "ok": True},
                {"round": "99", "ok": True},
            ],
        )

    def test_identical_receipts_have_no_semantic_diff(self):
        document = self.make_document()
        result = audit_diff.build_audit_diff(document, copy.deepcopy(document))
        self.assertFalse(result["changed"])
        self.assertEqual([], result["floor_changes"])
        self.assertIn("无语义变化", audit_diff.render_audit_diff(result))

    def test_floor_policy_and_tool_changes_are_explicit(self):
        before = self.make_document()
        after = copy.deepcopy(before)
        after["floors"][0]["curse_names"] = ["血肉高墙"]
        after["floors"][0]["curse_description"] = "血肉高墙"
        after["floors"][0]["adapter"]["damage_checks"][
            "source_boss"]["checks"] = [{"changed": True}]
        after["floors"][0]["thumbnail"] = "quest/thumbnail/test/other"
        after["floors"][0]["thumbnail_evidence"]["thumbnail"] = (
            "quest/thumbnail/test/other")
        after["floors"][0]["thumbnail_evidence"]["asset_logical"] = (
            "quest/thumbnail/test/other.png")
        after["selection_policy"]["boss_exclusions"][0]["reason"] = "changed"
        after["tool"]["sha256"] = "f" * 64
        after["document_sha256"] = rb.hp_audit_document_digest(after)

        result = audit_diff.build_audit_diff(before, after)

        self.assertTrue(result["changed"])
        self.assertEqual([2], [item["round"] for item in result["floor_changes"]])
        paths = {change["path"] for change in result["floor_changes"][0]["changes"]}
        self.assertIn("curse.names", paths)
        self.assertIn("thumbnail.value", paths)
        self.assertIn("adapter.damage_checks_sha256", paths)
        self.assertTrue(result["policy_changes"])
        self.assertIn("第 2 关", audit_diff.render_audit_diff(result))

    def test_corrupt_digest_is_rejected_and_cli_writes_only_requested_outputs(self):
        before = self.make_document()
        corrupt = copy.deepcopy(before)
        corrupt["document_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "integrity failed"):
            audit_diff.build_audit_diff(before, corrupt)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before_path = root / "before.json"
            after_path = root / "after.json"
            json_path = root / "diff.json"
            report_path = root / "diff.md"
            before_path.write_text(
                json.dumps(before, ensure_ascii=False), encoding="utf-8")
            after_path.write_text(
                json.dumps(before, ensure_ascii=False), encoding="utf-8")
            process = subprocess.run(
                [sys.executable, "-m", "wf.tools.rogue.rogue_audit_diff",
                 str(before_path), str(after_path),
                 "--json", str(json_path), "--report", str(report_path)],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=30)
            self.assertEqual(0, process.returncode, process.stderr)
            self.assertFalse(json.loads(
                json_path.read_text(encoding="utf-8"))["changed"])
            self.assertIn("无语义变化", report_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
