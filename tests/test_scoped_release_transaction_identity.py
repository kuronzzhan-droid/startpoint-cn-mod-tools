# -*- coding: utf-8 -*-
"""Identity and canonical-byte regressions for scoped release transactions."""
from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from release_inventory_support import InventoryCase

import wf_scoped_release as scoped


FILE_LOGICAL = "character/fixture/identity.bin"
MANIFEST = b'{"cdn_version":"1.4.54","patches":[]}\n'


class ScopedTransactionIdentityTest(InventoryCase):
    def plan(self) -> scoped.EdgePlan:
        raw = b"identity fixture"
        contract = self.parse(self.payload([
            self.file_member("owner", raw, logical_path=FILE_LOGICAL)
        ]))
        spec = scoped.EdgeSpec(
            "1.4.311", "1.4.312", "identity0806", "identity-fixture",
            "identity fixture", "identity fixture", "2026-08-06",
        )
        return scoped.build_edge_plan(
            contract, {("common", FILE_LOGICAL): None}, lambda _member: raw, spec
        )

    @staticmethod
    def repository(root: Path) -> tuple[Path, Path]:
        active = root / "asset-patch" / "active"
        active.mkdir(parents=True)
        manifest = active.parent / "manifest.json"
        manifest.write_bytes(MANIFEST)
        return active, manifest

    def publish(self, plan: scoped.EdgePlan, active: Path, manifest: Path, checkpoint=None):
        return scoped.publish_archives_and_manifest(
            (plan,), active, manifest,
            expected_manifest_sha256=hashlib.sha256(MANIFEST).hexdigest(),
            checkpoint=checkpoint,
            client_profile="official",
        )

    def test_rollback_leaves_replacement_foreign_archive_and_retains_lock(self):
        plan = self.plan()
        with tempfile.TemporaryDirectory() as td:
            active, manifest = self.repository(Path(td))
            foreign = b"foreign replacement"

            def replace_archive(phase: str) -> None:
                if phase == "before_manifest":
                    target = next(active.glob("*.zip"))
                    target.unlink()
                    target.write_bytes(foreign)

            with self.assertRaisesRegex(scoped.ScopedReleaseError, "identity|rollback|lock"):
                self.publish(plan, active, manifest, replace_archive)
            target = active / plan.parts[0].name
            self.assertEqual(foreign, target.read_bytes())
            self.assertEqual(MANIFEST, manifest.read_bytes())
            self.assertTrue((active.parent / ".wf-scoped-release.lock").is_file())
            target.unlink()
            (active.parent / ".wf-scoped-release.lock").unlink()

    def test_link_success_followed_by_exception_is_discovered_and_cleaned(self):
        plan = self.plan()
        with tempfile.TemporaryDirectory() as td:
            active, manifest = self.repository(Path(td))
            real_link = scoped.transaction.os.link

            def link_then_raise(source, target, **kwargs):
                real_link(source, target, **kwargs)
                raise OSError("injected ambiguous link result")

            with mock.patch.object(
                scoped.transaction.os, "link", side_effect=link_then_raise
            ):
                with self.assertRaisesRegex(
                    scoped.ScopedReleaseError, "ambiguous|link"
                ):
                    self.publish(plan, active, manifest)
            self.assertEqual([], list(active.iterdir()))
            self.assertEqual(MANIFEST, manifest.read_bytes())
            self.assertFalse((active.parent / ".wf-scoped-release.lock").exists())

    def test_cleanup_leaves_a_preexisting_foreign_occupant_at_its_original_name(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "owned.bin"
            target.write_bytes(b"owned")
            owned = scoped.transaction._OwnedPath(
                target,
                scoped.transaction._object_identity(target.lstat()),
            )
            foreign = b"foreign present before cleanup"
            target.unlink()
            target.write_bytes(foreign)

            errors = scoped.transaction._remove_owned((owned,))

            self.assertTrue(errors)
            self.assertEqual(foreign, target.read_bytes())
            self.assertEqual([], list(Path(td).glob("*.wf-quarantine-*")))

    @unittest.skipUnless(sys.platform == "win32", "Windows handle cleanup contract")
    def test_cleanup_handle_blocks_replacement_after_identity_validation(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "owned.bin"
            target.write_bytes(b"owned")
            owned = scoped.transaction._OwnedPath(
                target,
                scoped.transaction._object_identity(target.lstat()),
            )
            api = scoped.transaction._windows_owned_api()
            real_dispose = api.dispose
            attempted = False
            replacement_blocked = False

            def replace_then_dispose(handle: int) -> None:
                nonlocal attempted, replacement_blocked
                attempted = True
                try:
                    target.unlink()
                except OSError:
                    replacement_blocked = True
                else:
                    target.write_bytes(b"foreign replacement")
                real_dispose(handle)

            with mock.patch.object(api, "dispose", side_effect=replace_then_dispose):
                errors = scoped.transaction._remove_owned((owned,))

            self.assertTrue(attempted)
            self.assertTrue(replacement_blocked)
            self.assertEqual([], errors)
            self.assertFalse(target.exists())

    def test_platform_without_exact_cleanup_fails_closed_and_keeps_the_path(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "owned.bin"
            target.write_bytes(b"owned")
            owned = scoped.transaction._OwnedPath(
                target,
                scoped.transaction._object_identity(target.lstat()),
            )

            errors = scoped.transaction._remove_owned_unsupported((owned,))

            self.assertTrue(errors)
            self.assertEqual(b"owned", target.read_bytes())
            self.assertEqual([target], list(Path(td).iterdir()))

    def test_every_platform_resolves_an_exact_cleanup_or_declares_none(self):
        # A platform must either provide an exact object-scoped cleanup or be
        # explicitly unsupported.  Silently degrading to a pathname unlink would
        # reintroduce the TOCTOU this module exists to prevent.
        strategy = scoped.transaction._remove_owned_strategy()
        self.assertIn(
            strategy,
            (
                scoped.transaction._remove_owned_windows,
                scoped.transaction._remove_owned_posix,
                scoped.transaction._remove_owned_unsupported,
            ),
        )
        if sys.platform == "win32":
            self.assertIs(strategy, scoped.transaction._remove_owned_windows)
        else:
            self.assertIsNot(
                strategy, scoped.transaction._remove_owned_unsupported,
                "POSIX exact cleanup must be available or publication cannot"
                " complete on this platform",
            )

    @staticmethod
    def owned_now(path: Path):
        """Build an owned path the way the transaction does: created and pinned."""
        created: list = []
        scoped.transaction._write_exclusive(path, path.name.encode(), created)
        return created[0]

    @unittest.skipIf(sys.platform == "win32", "POSIX dir_fd cleanup contract")
    def test_posix_cleanup_removes_only_the_owned_object(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "owned.bin"
            neighbour = Path(td) / "other.bin"
            neighbour.write_bytes(b"other")
            owned = self.owned_now(target)
            self.assertIsNotNone(owned.descriptor)

            errors = scoped.transaction._remove_owned_posix((owned,))

            self.assertEqual([], errors)
            self.assertFalse(target.exists())
            self.assertEqual(b"other", neighbour.read_bytes())

    @unittest.skipIf(sys.platform == "win32", "POSIX dir_fd cleanup contract")
    def test_posix_cleanup_refuses_a_replacement_that_reused_the_inode(self):
        # The kernel hands a freed inode number straight back to the next file
        # created in that filesystem, so a replacement at the same name usually
        # carries the identical (st_dev, st_ino).  Only the descriptor retained
        # since creation -- which keeps the original inode allocated -- can tell
        # the two apart.
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "owned.bin"
            owned = self.owned_now(target)
            foreign = b"foreign present before cleanup"
            target.unlink()
            target.write_bytes(foreign)

            errors = scoped.transaction._remove_owned_posix((owned,))

            self.assertTrue(errors)
            self.assertEqual(foreign, target.read_bytes())

    @unittest.skipIf(sys.platform == "win32", "POSIX dir_fd cleanup contract")
    def test_posix_cleanup_refuses_an_owned_path_that_was_never_pinned(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "owned.bin"
            target.write_bytes(b"owned")
            unpinned = scoped.transaction._OwnedPath(
                target,
                scoped.transaction._object_identity(target.lstat()),
            )

            errors = scoped.transaction._remove_owned_posix((unpinned,))

            self.assertTrue(errors)
            self.assertEqual(b"owned", target.read_bytes())

    @unittest.skipIf(sys.platform == "win32", "POSIX dir_fd cleanup contract")
    def test_posix_cleanup_refuses_a_symlinked_parent_directory(self):
        with tempfile.TemporaryDirectory() as td:
            real = Path(td) / "real"
            real.mkdir()
            target = real / "owned.bin"
            owned = self.owned_now(target)
            link = Path(td) / "link"
            link.symlink_to(real, target_is_directory=True)
            through_link = scoped.transaction._OwnedPath(
                link / "owned.bin", owned.object_id, owned.descriptor
            )

            errors = scoped.transaction._remove_owned_posix((through_link,))

            self.assertTrue(errors)
            self.assertEqual(target.name.encode(), target.read_bytes())

    def test_versions_reject_leading_zero_segments(self):
        with self.assertRaisesRegex(scoped.archive.ArchiveError, "version"):
            scoped.archive.build_parts(
                (), roots=("common",), from_version="1.04.311",
                to_version="1.4.312", tag="identity0806",
                max_zip_bytes=scoped.CI_ZIP_CAP,
            )

    def test_zip_prefix_or_suffix_junk_is_not_a_canonical_archive(self):
        plan = self.plan()
        for label, blob in (
            ("prefix", b"JUNK" + plan.parts[0].blob),
            ("suffix", plan.parts[0].blob + b"JUNK"),
        ):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as td:
                bad = scoped.EdgePlan(
                    plan.spec, plan.entries, (replace(plan.parts[0], blob=blob),)
                )
                with self.assertRaisesRegex(
                    scoped.ScopedReleaseError, "canonical|byte|ZIP"
                ):
                    scoped.stage_archives((bad,), Path(td) / "stage")


if __name__ == "__main__":
    unittest.main()
