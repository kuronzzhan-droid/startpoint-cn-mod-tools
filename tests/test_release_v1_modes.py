"""Strict Mode component verification and candidate materialization."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tests.release_v1_fixtures import make_patch_overlay, make_sealed_character_workspace
from tests.release_v1_mode_fixture import (
    MODE_FILE,
    RESOURCE_PATH,
    make_character_mode_release,
    rewrite_requirements_without_mode_capability,
)
from tests.release_v1_schema_support import requirements_wire
from wf_release_v1.errors import ReleaseError
from wf_release_v1.materialize import (
    import_verified_object,
    load_verified_release,
    materialize_candidates,
    verify_candidates,
)
from wf_release_v1.producer import BuildRequest, build_character_release
from wf_release_v1.schema import parse_requirements
from wf_release_v1.target import ComponentRoots, ManagedTarget, TargetCompatibility
from wf_release_v1.verifier import verify_release


OPERATION = "20260812T010203.000000Z-0123456789abcdef0123456789abcdef"


class ModeComponentTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="wfrel-modes-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        workspace = make_sealed_character_workspace(self.root / "workspace")
        overlay = make_patch_overlay(
            self.root / "source" / "worldflipper-overlay-1.4.54-to-1.4.55.zip",
            from_version="1.4.54",
            target_version="1.4.55",
        )
        content = self.root / "content-release.zip"
        build_character_release(BuildRequest(
            name="seris-dragon-king",
            version="1.0.0",
            workspace=workspace,
            overlay_archives=(overlay,),
            output=content,
            requirements=parse_requirements(requirements_wire()),
        ))
        self.release = make_character_mode_release(
            content,
            self.root / "character-mode-release.zip",
        )
        roots = {
            name: self.root / name
            for name in (
                "server", "runtime", "data", "state", "cdn", "modes",
                "candidate-content", "candidate-server", "candidate-modes",
            )
        }
        for root in roots.values():
            root.mkdir()
        self.target = ManagedTarget(
            roots["server"],
            roots["runtime"],
            roots["data"],
            roots["state"],
            roots["cdn"],
            roots["modes"],
            ComponentRoots(
                roots["candidate-content"],
                roots["candidate-server"],
                roots["candidate-modes"],
            ),
            TargetCompatibility("1.4.54", "1.4.53", True),
            "http://127.0.0.1:8001",
        )

    def test_verifies_combined_release_and_mode_bytes_change_identity(self) -> None:
        first = verify_release(self.release)
        changed = make_character_mode_release(
            self.root / "content-release.zip",
            self.root / "changed-mode-release.zip",
            marker="v2",
        )
        second = verify_release(changed)

        self.assertEqual(("content", "modes"), first.components)
        self.assertNotEqual(first.release_id, second.release_id)

    def test_materializes_and_reverifies_exact_mode_candidate(self) -> None:
        stored = import_verified_object(self.release, self.target)
        verified = load_verified_release(stored, self.target)
        candidates = materialize_candidates(stored, self.target, OPERATION)
        verify_candidates(candidates)

        self.assertEqual(("content", "modes"), tuple(
            component.kind for component in verified.manifest.components
        ))
        self.assertIsNotNone(candidates.content_root)
        self.assertIsNotNone(candidates.modes_root)
        mode_root = candidates.modes_root
        if mode_root is None:
            raise AssertionError("mode candidate root is absent")
        self.assertTrue((mode_root / MODE_FILE).is_file())
        self.assertTrue((mode_root / RESOURCE_PATH).is_file())
        self.assertEqual(
            [MODE_FILE],
            json.loads((mode_root / "modes-required.json").read_text(encoding="utf-8"))[
                "required"
            ],
        )

    def test_candidate_rejects_unlisted_mode_bytes(self) -> None:
        stored = import_verified_object(self.release, self.target)
        candidates = materialize_candidates(stored, self.target, OPERATION)
        if candidates.modes_root is None:
            raise AssertionError("mode candidate root is absent")
        (candidates.modes_root / "undeclared.bin").write_bytes(b"undeclared")

        with self.assertRaises(ReleaseError) as caught:
            verify_candidates(candidates)
        self.assertEqual("WFREL_CANDIDATE_INVALID", caught.exception.code)

    def test_missing_release_contract_capability_is_rejected_before_object_write(self) -> None:
        incompatible = rewrite_requirements_without_mode_capability(
            self.release,
            self.root / "missing-mode-capability.zip",
        )

        with self.assertRaises(ReleaseError) as caught:
            import_verified_object(incompatible, self.target)
        self.assertEqual("WFREL_COMPONENT_INVALID", caught.exception.code)
        objects = self.target.state_root / "objects"
        self.assertFalse(objects.exists() and any(objects.iterdir()))


if __name__ == "__main__":
    unittest.main()
