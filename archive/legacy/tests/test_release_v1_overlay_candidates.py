"""Safe expansion of verified Patch Overlays into receiver directories."""

from __future__ import annotations

import io
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from tests.release_v1_fixtures import make_patch_overlay
from wf_release_v1.errors import ReleaseError


class OverlayCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temporary.cleanup)
        root = Path(temporary.name)
        outer = make_patch_overlay(
            root / "worldflipper-overlay-1.4.54-to-1.4.55.zip",
            from_version="1.4.54",
            target_version="1.4.55",
        )
        cls.overlay_raw = outer.read_bytes()
        with zipfile.ZipFile(io.BytesIO(cls.overlay_raw), "r") as bundle:
            cls.overlay_members = tuple(
                (item.filename, bundle.read(item)) for item in bundle.infolist()
            )

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def test_rejects_reparse_member_metadata_before_writing(self) -> None:
        from wf_release_v1.overlay_candidates import materialize_verified_overlay
        from wf_release_v1.verifier_overlay import verify_overlay_chain

        outer = self.root / "reparse-overlay.zip"
        output = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(self.overlay_raw), "r") as source, zipfile.ZipFile(
            output, "w", compression=zipfile.ZIP_DEFLATED
        ) as changed:
            for item in source.infolist():
                if item.filename == "README.md":
                    replacement = zipfile.ZipInfo(item.filename)
                    replacement.create_system = 3
                    replacement.external_attr = (stat.S_IFLNK | 0o777) << 16
                    replacement.compress_type = zipfile.ZIP_DEFLATED
                    changed.writestr(replacement, source.read(item))
                else:
                    changed.writestr(item.filename, source.read(item))
        outer.write_bytes(output.getvalue())
        self.assertEqual("1.4.55", verify_overlay_chain((outer,)))
        receiver = self.root / "receiver" / "1.4.55"
        receiver.mkdir(parents=True)

        with self.assertRaises(ReleaseError) as raised:
            materialize_verified_overlay(outer, receiver)

        self.assertEqual("WFREL_CANDIDATE_INVALID", raised.exception.code)
        self.assertEqual([], list(receiver.iterdir()))

    def test_rejects_source_replacement_after_semantic_verification(self) -> None:
        import wf_release_v1.overlay_candidates as overlay_candidates
        from wf_release_v1.overlay_candidates import materialize_verified_overlay
        from wf_release_v1.verifier_overlay import inspect_overlay_chain

        outer = self.root / "replace-after-verify.zip"
        outer.write_bytes(self.overlay_raw)
        alternate = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(self.overlay_raw), "r") as source, zipfile.ZipFile(
            alternate, "w", compression=zipfile.ZIP_DEFLATED
        ) as changed:
            for item in source.infolist():
                raw = source.read(item)
                changed.writestr(
                    item.filename,
                    b"alternate readme\n" if item.filename == "README.md" else raw,
                )
        alternate_raw = alternate.getvalue()
        self.assertEqual("1.4.55", inspect_overlay_chain((outer,)).target_version)
        calls = 0

        def verify_then_replace(paths):
            nonlocal calls
            facts = inspect_overlay_chain(paths)
            calls += 1
            if calls == 1:
                outer.write_bytes(alternate_raw)
            return facts

        receiver = self.root / "receiver-replaced" / "1.4.55"
        receiver.mkdir(parents=True)
        with patch.object(
            overlay_candidates, "inspect_overlay_chain", side_effect=verify_then_replace
        ):
            with self.assertRaises(ReleaseError) as raised:
                materialize_verified_overlay(outer, receiver)

        self.assertEqual("WFREL_CANDIDATE_INVALID", raised.exception.code)

    @unittest.skipUnless(__import__("os").name == "nt", "Windows handle contract")
    def test_nested_parent_cannot_be_replaced_between_validation_and_output_open(self) -> None:
        import wf_release_v1.overlay_candidates as overlay_candidates
        from wf_release_v1.overlay_candidates import materialize_verified_overlay

        outer = self.root / "parent-race-overlay.zip"
        outer.write_bytes(self.overlay_raw)
        receiver = self.root / "receiver-parent-race" / "1.4.55"
        receiver.mkdir(parents=True)
        attempted = False
        blocked = False

        def replace_parent(destination: Path) -> None:
            nonlocal attempted, blocked
            if attempted or destination.parent == receiver:
                return
            attempted = True
            parked = destination.parent.with_name(destination.parent.name + "-parked")
            try:
                destination.parent.rename(parked)
            except OSError:
                blocked = True
                return
            destination.parent.mkdir()
            (destination.parent / "foreign.keep").write_bytes(b"foreign")

        with patch.object(
            overlay_candidates, "_before_member_open", side_effect=replace_parent
        ):
            materialize_verified_overlay(outer, receiver)

        self.assertTrue(attempted)
        self.assertTrue(blocked)
        self.assertFalse(any(receiver.rglob("foreign.keep")))

    def test_partial_handle_write_is_disposed_and_foreign_same_name_is_preserved(self) -> None:
        import wf_release_v1._owned_receiver as owned_receiver
        from wf_release_v1.overlay_candidates import materialize_verified_overlay

        outer = self.root / "owned-cleanup-overlay.zip"
        outer.write_bytes(self.overlay_raw)
        receiver = self.root / "receiver-owned-cleanup" / "1.4.55"
        receiver.mkdir(parents=True)
        real_write = owned_receiver.OwnedReceiver._write
        injected = False

        def partial_then_fail(authority, handle: int, raw: bytes) -> int:
            nonlocal injected
            if not injected:
                injected = True
                real_write(authority, handle, raw[: max(1, len(raw) // 2)])
                raise OSError("injected partial handle write")
            return real_write(authority, handle, raw)

        with patch.object(
            owned_receiver.OwnedReceiver, "_write", new=partial_then_fail
        ):
            with self.assertRaises(ReleaseError):
                materialize_verified_overlay(outer, receiver)
        self.assertTrue(injected)
        self.assertEqual([], list(receiver.iterdir()))

        def fail_nested_create(authority, relative: str, write, *, before_open=None):
            def wrapped(writer) -> None:
                if "/" not in relative:
                    write(writer)
                    return

                class PartialWriter:
                    def write(self, raw: bytes) -> int:
                        writer.write(raw[: max(1, len(raw) // 2)])
                        raise OSError("injected nested partial write")

                write(PartialWriter())

            return real_create(
                authority, relative, wrapped, before_open=before_open
            )

        real_create = owned_receiver.OwnedReceiver.create_file
        with patch.object(
            owned_receiver.OwnedReceiver, "create_file", new=fail_nested_create
        ):
            with self.assertRaises(ReleaseError):
                materialize_verified_overlay(outer, receiver)
        self.assertEqual([], list(receiver.iterdir()))

        foreign = receiver / "README.md"
        foreign.write_bytes(b"foreign-must-survive")
        with self.assertRaises(ReleaseError):
            materialize_verified_overlay(outer, receiver)
        self.assertEqual(b"foreign-must-survive", foreign.read_bytes())

    @unittest.skipUnless(__import__("os").name == "nt", "Windows handle contract")
    def test_root_identity_failure_closes_the_opened_windows_handle(self) -> None:
        import wf_release_v1._owned_receiver as owned_receiver

        receiver = self.root / "receiver-root-close"
        receiver.mkdir()
        assert owned_receiver._WIN_API is not None
        real_close = owned_receiver._WIN_API.close
        closed: list[int] = []

        def recording_close(handle: int) -> None:
            closed.append(handle)
            real_close(handle)

        with patch.object(
            owned_receiver._WIN_API, "identity", side_effect=OSError("root drift")
        ), patch.object(
            owned_receiver._WIN_API, "close", side_effect=recording_close
        ):
            with self.assertRaises(OSError):
                owned_receiver.OwnedReceiver(receiver)

        self.assertEqual(1, len(closed))

    def test_receiver_root_replacement_is_rejected_before_member_write(self) -> None:
        import wf_release_v1._owned_receiver as owned_receiver
        from wf_release_v1.overlay_candidates import materialize_verified_overlay

        outer = self.root / "root-replacement-overlay.zip"
        outer.write_bytes(self.overlay_raw)
        receiver = self.root / "receiver-root-replacement" / "1.4.55"
        receiver.mkdir(parents=True)
        parked = receiver.with_name("1.4.55-parked")

        def replace_root(root: Path) -> None:
            root.rename(parked)
            root.mkdir()

        with patch.object(
            owned_receiver, "_before_root_open", side_effect=replace_root
        ):
            with self.assertRaises(ReleaseError):
                materialize_verified_overlay(outer, receiver)

        self.assertEqual([], list(receiver.iterdir()))
        self.assertEqual([], list(parked.iterdir()))

    @unittest.skipUnless(__import__("os").name == "nt", "Windows long path contract")
    def test_nested_receiver_member_beyond_max_path_materializes_by_handle(self) -> None:
        import os
        import shutil
        import wf_release_v1.overlay_candidates as overlay_candidates
        from wf_release_v1._path_io import native_path
        from wf_release_v1.overlay_candidates import materialize_verified_overlay

        outer = self.root / "long-path-overlay.zip"
        outer.write_bytes(self.overlay_raw)
        long_base = self.root / ("a" * 90)
        self.addCleanup(shutil.rmtree, native_path(long_base))
        receiver = long_base / ("b" * 90) / "1.4.55"
        receiver.mkdir(parents=True)

        opened: list[Path] = []
        with patch.object(
            overlay_candidates,
            "_before_member_open",
            side_effect=lambda path: opened.append(path),
        ):
            materialize_verified_overlay(outer, receiver)

        archive_name = next(
            name for name, _raw in self.overlay_members
            if name.startswith("archive-common-diff/")
        )
        output = receiver / Path(archive_name)
        self.assertGreater(len(str(output)), 260)
        self.assertGreater(os.lstat(native_path(output)).st_size, 0)
        self.assertEqual("patch-manifest.json", opened[-1].name)

    def test_keeps_independent_verifier_as_unsafe_zip_gate(self) -> None:
        from wf_release_v1.overlay_candidates import materialize_verified_overlay

        variants = {
            "zip-slip": {"extra_members": {"../escape.bin": b"x"}},
            "duplicate": {"duplicate_member": "README.md"},
            "case-collision": {"extra_members": {"readme.md": b"x"}},
            "extra": {"extra_members": {"extra.bin": b"x"}},
        }
        for label, options in variants.items():
            with self.subTest(label=label):
                outer = make_patch_overlay(
                    self.root / f"unsafe-{label}.zip",
                    from_version="1.4.54",
                    target_version="1.4.55",
                    **options,
                )
                receiver = self.root / f"receiver-{label}" / "1.4.55"
                receiver.mkdir(parents=True)
                with self.assertRaises(ReleaseError) as raised:
                    materialize_verified_overlay(outer, receiver)
                self.assertEqual("WFREL_OVERLAY_INVALID", raised.exception.code)
                self.assertEqual([], list(receiver.iterdir()))


if __name__ == "__main__":
    unittest.main()
