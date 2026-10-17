"""Receipt v2 target-protocol compatibility and immutability."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from wf_release_v1.canonical import canonical_json_bytes
from wf_release_v1.errors import ReleaseError
from wf_release_v1.receipts import OperationReceipt, write_phase_receipt


START = datetime(2026, 8, 13, 1, 2, 3, 456789, tzinfo=timezone.utc)
OPERATION = "20260813T010203.456789Z-00112233445566778899aabbccddeeff"
RELEASE = "sha256:" + "a" * 64


def _receipt(protocol: str, **changes: object) -> OperationReceipt:
    values: dict[str, object] = {
        "schema_version": 2,
        "operation_id": OPERATION,
        "release_id": RELEASE,
        "phase": "CREATED",
        "outcome": "in_progress",
        "started_at": START,
        "updated_at": START,
        "before_release_ids": (),
        "candidate_release_ids": (RELEASE,),
        "error_code": None,
        "recovery_outcome": None,
        "target_protocol": protocol,
    }
    values.update(changes)
    return OperationReceipt(**values)  # type: ignore[arg-type]


class ReceiptProtocolTests(unittest.TestCase):
    def test_writer_emits_v2_with_explicit_protocol(self) -> None:
        for protocol in ("capabilities-v1", "legacy"):
            with self.subTest(protocol=protocol), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                write_phase_receipt(root, _receipt(protocol))
                raw = (root / "receipts" / f"{OPERATION}.json").read_bytes()
                self.assertEqual(
                    canonical_json_bytes({
                        "beforeReleaseIds": [],
                        "candidateReleaseIds": [RELEASE],
                        "errorCode": None,
                        "operationId": OPERATION,
                        "outcome": "in_progress",
                        "phase": "CREATED",
                        "recoveryOutcome": None,
                        "releaseId": RELEASE,
                        "schemaVersion": 2,
                        "startedAt": "2026-08-13T01:02:03.456789Z",
                        "targetProtocol": protocol,
                        "updatedAt": "2026-08-13T01:02:03.456789Z",
                    }),
                    raw,
                )

    def test_reader_accepts_v1_as_implicit_modern_then_upgrades_without_switching_protocol(self) -> None:
        old = {
            "beforeReleaseIds": [],
            "candidateReleaseIds": [RELEASE],
            "errorCode": None,
            "operationId": OPERATION,
            "outcome": "in_progress",
            "phase": "CREATED",
            "recoveryOutcome": None,
            "releaseId": RELEASE,
            "schemaVersion": 1,
            "startedAt": "2026-08-13T01:02:03.456789Z",
            "updatedAt": "2026-08-13T01:02:03.456789Z",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipts = root / "receipts"
            receipts.mkdir()
            path = receipts / f"{OPERATION}.json"
            path.write_bytes(canonical_json_bytes(old))
            updated = _receipt(
                "capabilities-v1",
                phase="VERIFIED",
                updated_at=START + timedelta(seconds=1),
            )
            write_phase_receipt(root, updated)
            self.assertIn(b'"targetProtocol":"capabilities-v1"', path.read_bytes())

            path.write_bytes(canonical_json_bytes(old))
            with self.assertRaises(ReleaseError) as raised:
                write_phase_receipt(root, replace(updated, target_protocol="legacy"))
            self.assertEqual("WFREL_RECEIPT_CONFLICT", raised.exception.code)

    def test_update_cannot_change_protocol_or_default_unknown_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_phase_receipt(root, _receipt("legacy"))
            changed = _receipt(
                "capabilities-v1",
                phase="VERIFIED",
                updated_at=START + timedelta(seconds=1),
            )
            with self.assertRaises(ReleaseError) as raised:
                write_phase_receipt(root, changed)
            self.assertEqual("WFREL_RECEIPT_CONFLICT", raised.exception.code)
        for protocol in ("modern", "", None, 1):
            with self.subTest(protocol=protocol):
                with self.assertRaises(ReleaseError) as raised:
                    _receipt(protocol)  # type: ignore[arg-type]
                self.assertEqual("WFREL_RECEIPT_INVALID", raised.exception.code)


if __name__ == "__main__":
    unittest.main()
