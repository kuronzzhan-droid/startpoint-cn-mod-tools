"""Atomic stopped-service Mode root switch and retained recovery facts."""

from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest

from wf_release_v1.canonical import FileIdentity
from wf_release_v1.errors import ReleaseError
from wf_release_v1.materialize import CandidateSet
from wf_release_v1.mode_candidates import ModeCandidate
from wf_release_v1.target import ComponentRoots, ManagedTarget, TargetCompatibility


OPERATION = "20260812T010203.000000Z-0123456789abcdef0123456789abcdef"


class ModeSwitchTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="wfrel-mode-switch-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        roots = {
            name: self.root / name
            for name in (
                "server", "runtime", "data", "state", "cdn", "active-modes",
                "candidate-content", "candidate-server", "candidate-modes",
            )
        }
        for root in roots.values():
            root.mkdir()
        staging = roots["state"] / "staging" / OPERATION
        staging.mkdir(parents=True)
        (roots["active-modes"] / "baseline.mjs").write_bytes(b"baseline")
        self.release_id = "sha256:" + "e" * 64
        candidate = roots["candidate-modes"] / self.release_id.replace(":", "-", 1)
        candidate.mkdir()
        (candidate / "fixture.mjs").write_bytes(b"candidate")
        mode = ModeCandidate(
            self.release_id,
            candidate,
            (FileIdentity(9, hashlib.sha256(b"candidate").hexdigest()),),
            ("fixture.mjs",),
        )
        self.candidates = CandidateSet(
            self.release_id,
            roots["candidate-content"] / "unused",
            None,
            candidate,
            (),
            (),
            mode,
        )
        self.target = ManagedTarget(
            roots["server"], roots["runtime"], roots["data"], roots["state"],
            roots["cdn"], roots["active-modes"],
            ComponentRoots(
                roots["candidate-content"], roots["candidate-server"], roots["candidate-modes"]
            ),
            TargetCompatibility("1.4.54", "1.4.53", True),
            "http://127.0.0.1:8001",
        )

    def test_switch_and_restore_preserve_both_exact_roots(self) -> None:
        from wf_release_v1._transaction_modes import (
            apply_mode_switch,
            prepare_mode_switch,
            restore_mode_switch,
        )

        switch = prepare_mode_switch(self.candidates, self.target, OPERATION)
        apply_mode_switch(switch)
        self.assertEqual(b"candidate", (self.target.modes_root / "fixture.mjs").read_bytes())
        self.assertFalse((self.target.modes_root / "baseline.mjs").exists())
        self.assertTrue((switch.staging_root / "modes-previous" / "baseline.mjs").is_file())

        restore_mode_switch(switch)
        self.assertEqual(b"baseline", (self.target.modes_root / "baseline.mjs").read_bytes())
        self.assertEqual(b"candidate", (self.candidates.modes_root / "fixture.mjs").read_bytes())
        self.assertFalse((switch.staging_root / "modes-previous").exists())

    def test_retained_switch_reconstructs_and_tampered_marker_fails_closed(self) -> None:
        from wf_release_v1._transaction_modes import (
            apply_mode_switch,
            load_mode_switch,
            prepare_mode_switch,
        )

        switch = prepare_mode_switch(self.candidates, self.target, OPERATION)
        apply_mode_switch(switch)
        retained = load_mode_switch(self.target, OPERATION, self.release_id)
        self.assertIsNotNone(retained)
        marker = switch.staging_root / "mode-release-id.txt"
        marker.write_text("sha256:" + "b" * 64 + "\n", encoding="ascii")

        with self.assertRaises(ReleaseError) as caught:
            load_mode_switch(self.target, OPERATION, self.release_id)
        self.assertEqual("WFREL_TRANSACTION_FAILED", caught.exception.code)


if __name__ == "__main__":
    unittest.main()
