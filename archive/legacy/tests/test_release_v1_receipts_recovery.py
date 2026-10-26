from __future__ import annotations

from dataclasses import replace
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from wf_release_v1 import receipts as receipts_module
from wf_release_v1.errors import ReleaseError
from wf_release_v1.receipts import write_phase_receipt

from tests.test_release_v1_receipts import UPDATED, _receipt


class ReceiptRecoveryDurabilityTests(unittest.TestCase):
    def test_failed_restore_syncs_and_retains_the_receipt_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipt = _receipt()
            write_phase_receipt(root, receipt)
            receipts = root / "receipts"
            path = receipts / f"{receipt.operation_id}.json"
            old = path.read_bytes()
            real_replace = os.replace
            real_sync = receipts_module._sync_directory
            synced: list[Path] = []

            def fail_restore(source: Path, destination: Path) -> None:
                if source.suffix == ".tmp":
                    source.unlink()
                    source.write_bytes(b"not the synchronized receipt")
                elif source.suffix == ".rollback":
                    raise OSError("injected receipt restore failure")
                real_replace(source, destination)

            def trace_sync(directory_path: Path) -> None:
                synced.append(directory_path)
                real_sync(directory_path)

            updated = replace(receipt, phase="VERIFIED", updated_at=UPDATED)
            with mock.patch(
                "wf_release_v1.receipts.os.replace", side_effect=fail_restore
            ), mock.patch(
                "wf_release_v1.receipts._sync_directory", side_effect=trace_sync
            ):
                with self.assertRaises(ReleaseError) as caught:
                    write_phase_receipt(root, updated)
            self.assertEqual("WFREL_STATE_IO", caught.exception.code)
            self.assertIn(receipts, synced)
            self.assertEqual([old], [item.read_bytes() for item in receipts.glob("*.rollback")])


if __name__ == "__main__":
    unittest.main()
