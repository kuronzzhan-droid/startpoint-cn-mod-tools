"""Immutable object import and private component candidate materialization."""

from __future__ import annotations

import hashlib
from dataclasses import replace
import io
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from tests.release_v1_fixtures import make_patch_overlay, make_sealed_character_workspace
from tests.release_v1_schema_support import requirements_wire
from tests.test_release_v1_verifier import _classic_store, _members, _replace_release
from wf_release_v1.errors import ReleaseError
from wf_release_v1.producer import BuildRequest, build_character_release
from wf_release_v1.schema import parse_requirements
from wf_release_v1.target import ComponentRoots, ManagedTarget


OPERATION_ID = "20260812T010203.000000Z-0123456789abcdef0123456789abcdef"
ROOT = "wf-release-v1/"
RELEASE = ROOT + "release-manifest.json"


def _release_directory(release_id: str) -> str:
    return release_id.replace(":", "-")


def _server_release(raw: bytes) -> bytes:
    members = _members(raw)
    payload_name = next(name for name, _raw in members if "/content/" in name)
    server_name = payload_name.replace("/content/", "/server/")
    renamed = [
        (server_name if name == payload_name else name, value)
        for name, value in members
    ]

    def mutate(manifest: dict[str, object]) -> None:
        manifest["components"] = [{"kind": "server", "root": "server"}]
        files = manifest["files"]
        if not isinstance(files, list) or not isinstance(files[0], dict):
            raise AssertionError("fixture release files are invalid")
        files[0]["path"] = server_name.removeprefix(ROOT)

    changed = _replace_release(renamed, mutate)
    release_member = next(item for item in changed if item[0] == RELEASE)
    payload_members = sorted(
        (item for item in changed if item[0] != RELEASE), key=lambda item: item[0].encode("utf-8")
    )
    return _classic_store(payload_members + [release_member])


class MaterializeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temporary.cleanup)
        root = Path(temporary.name)
        workspace = make_sealed_character_workspace(root / "workspace")
        overlay = make_patch_overlay(
            root / "source" / "worldflipper-overlay-1.4.54-to-1.4.55.zip",
            from_version="1.4.54",
            target_version="1.4.55",
        )
        cls.overlay_raw = overlay.read_bytes()
        cls.release = root / "valid-release.zip"
        build_character_release(
            BuildRequest(
                name="seris-dragon-king",
                version="1.0.0",
                workspace=workspace,
                overlay_archives=(overlay,),
                output=cls.release,
                requirements=parse_requirements(requirements_wire()),
            )
        )
        cls.release_raw = cls.release.read_bytes()

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        paths = {
            name: self.root / name
            for name in (
                "server-bundle", "runtime-pack", "data", "state",
                "content-components", "server-components", "mode-components",
            )
        }
        for path in paths.values():
            path.mkdir()
        self.target = ManagedTarget(
            server_bundle=paths["server-bundle"],
            runtime_pack=paths["runtime-pack"],
            data_root=paths["data"],
            state_root=paths["state"],
            component_roots=ComponentRoots(
                paths["content-components"], paths["server-components"], paths["mode-components"]
            ),
            server_url="http://127.0.0.1:8001",
        )
        self.source = self.root / "shared-name-must-not-be-authority.zip"
        self.source.write_bytes(self.release_raw)

    def _import(self):
        from wf_release_v1.materialize import import_verified_object

        return import_verified_object(self.source, self.target)

    def _materialize(self, stored=None):
        from wf_release_v1.materialize import materialize_candidates

        return materialize_candidates(stored or self._import(), self.target, OPERATION_ID)

    def test_import_uses_verified_release_identity_and_identical_bytes_are_noop(self) -> None:
        stored = self._import()
        expected_root = self.target.state_root / "objects" / _release_directory(stored.release_id)
        self.assertEqual(expected_root / "release.wf-release.zip", stored.archive)
        self.assertEqual(hashlib.sha256(self.release_raw).hexdigest(), stored.identity.sha256)
        self.assertEqual(len(self.release_raw), stored.identity.size)
        self.assertNotIn(self.source.name, str(stored.archive))
        before = stored.archive.stat()
        second = self._import()
        self.assertEqual(stored, second)
        self.assertEqual((before.st_ino, before.st_mtime_ns), (second.archive.stat().st_ino, second.archive.stat().st_mtime_ns))

    def test_stored_object_exposes_all_detached_verified_metadata(self) -> None:
        from wf_release_v1.materialize import load_verified_release

        stored = self._import()
        verified = load_verified_release(stored, self.target)

        self.assertEqual(stored.release_id, verified.manifest.release_id)
        self.assertEqual(("content",), tuple(item.kind for item in verified.manifest.components))
        self.assertEqual(1, verified.requirements.patch_overlay_schema)
        self.assertEqual(("character:129999",), verified.ownership.entities)
        self.assertNotIn(str(self.source), repr(verified))
        self.assertNotIn(str(self.target.state_root), repr(verified))

    def test_existing_object_with_different_bytes_is_corruption_and_is_not_overwritten(self) -> None:
        stored = self._import()
        stored.archive.write_bytes(b"corrupt-existing-object")
        corrupt = stored.archive.read_bytes()
        with self.assertRaises(ReleaseError) as raised:
            self._import()
        self.assertEqual("WFREL_OBJECT_CORRUPT", raised.exception.code)
        self.assertEqual(corrupt, stored.archive.read_bytes())

    def test_content_candidate_contains_only_declared_overlay_and_never_scans_cn(self) -> None:
        import wf_release_v1.materialize as materialize_module

        sentinel = self.target.component_roots.content / "cn" / "ten-gigabyte-sentinel.bin"
        sentinel.parent.mkdir()
        sentinel.write_bytes(b"official-baseline-must-not-be-read")
        stored = self._import()
        real_scandir = materialize_module.os.scandir

        def poison_official_baseline(path):
            if Path(path) == sentinel.parent:
                raise AssertionError("official cn baseline was scanned")
            return real_scandir(path)

        with patch.object(materialize_module.os, "scandir", side_effect=poison_official_baseline):
            candidates = self._materialize(stored)
        expected_root = self.target.component_roots.content / _release_directory(stored.release_id)
        self.assertEqual(expected_root, candidates.content_root)
        self.assertIsNone(candidates.server_root)
        self.assertIsNone(candidates.modes_root)
        materialized = expected_root / "patches" / "1.4.55" / "worldflipper-overlay-1.4.54-to-1.4.55.zip"
        self.assertEqual(self.overlay_raw, materialized.read_bytes())
        self.assertEqual(b"official-baseline-must-not-be-read", sentinel.read_bytes())
        self.assertEqual(("patches/1.4.55/worldflipper-overlay-1.4.54-to-1.4.55.zip",), candidates.relative_paths)
        self.assertEqual((len(self.overlay_raw),), tuple(item.size for item in candidates.identities))

    def test_candidate_identity_rejects_a_different_but_valid_overlay(self) -> None:
        from wf_release_v1.materialize import verify_candidates

        candidates = self._materialize()
        candidate_file = candidates.content_root / Path(candidates.relative_paths[0])
        output = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(self.overlay_raw)) as source, zipfile.ZipFile(
            output, "w", compression=zipfile.ZIP_DEFLATED
        ) as changed:
            for item in source.infolist():
                raw = source.read(item)
                changed.writestr(item.filename, b"different readme\n" if item.filename == "README.md" else raw)
        candidate_file.write_bytes(output.getvalue())
        # The alternate Overlay has the same valid edge and member set.
        from wf_release_v1.verifier_overlay import verify_overlay_chain

        self.assertEqual("1.4.55", verify_overlay_chain((candidate_file,)))
        with self.assertRaises(ReleaseError) as raised:
            verify_candidates(candidates)
        self.assertEqual("WFREL_CANDIDATE_INVALID", raised.exception.code)

    def test_materialize_same_release_is_noop_but_conflicting_candidate_is_rejected(self) -> None:
        stored = self._import()
        first = self._materialize(stored)
        candidate_file = first.content_root / Path(first.relative_paths[0])
        before = candidate_file.stat()
        second = self._materialize(stored)
        self.assertEqual(first, second)
        self.assertEqual(before.st_mtime_ns, candidate_file.stat().st_mtime_ns)
        candidate_file.write_bytes(b"changed")
        with self.assertRaises(ReleaseError) as raised:
            self._materialize(stored)
        self.assertEqual("WFREL_CANDIDATE_INVALID", raised.exception.code)
        self.assertEqual(b"changed", candidate_file.read_bytes())

    def test_candidate_verifier_rejects_extra_missing_renamed_and_changed_files(self) -> None:
        from wf_release_v1.materialize import verify_candidates

        for attack in ("extra-file", "extra-directory", "missing", "renamed", "changed"):
            with self.subTest(attack=attack):
                candidates = self._materialize()
                candidate_file = candidates.content_root / Path(candidates.relative_paths[0])
                if attack == "extra-file":
                    (candidates.content_root / "extra.bin").write_bytes(b"extra")
                elif attack == "extra-directory":
                    (candidates.content_root / "unlisted-empty-directory").mkdir()
                elif attack == "missing":
                    candidate_file.unlink()
                elif attack == "renamed":
                    candidate_file.rename(candidate_file.with_name("renamed.zip"))
                else:
                    candidate_file.write_bytes(b"changed")
                with self.assertRaises(ReleaseError) as raised:
                    verify_candidates(candidates)
                self.assertEqual("WFREL_CANDIDATE_INVALID", raised.exception.code)
                shutil.rmtree(candidates.content_root)

    def test_candidate_root_name_is_bound_to_release_identity(self) -> None:
        from wf_release_v1.materialize import verify_candidates

        candidates = self._materialize()
        renamed = candidates.content_root.with_name("wrong-release-name")
        candidates.content_root.rename(renamed)
        with self.assertRaises(ReleaseError) as raised:
            verify_candidates(replace(candidates, content_root=renamed))
        self.assertEqual("WFREL_CANDIDATE_INVALID", raised.exception.code)

    def test_invalid_operation_id_and_root_device_drift_fail_before_candidate_write(self) -> None:
        from wf_release_v1.materialize import materialize_candidates

        stored = self._import()
        with self.assertRaises(ReleaseError) as raised:
            materialize_candidates(stored, self.target, "../bad-operation")
        self.assertEqual("WFREL_CANDIDATE_INVALID", raised.exception.code)
        self.assertEqual([], list(self.target.component_roots.content.iterdir()))

        original = Path.lstat
        root = self.target.component_roots.content
        calls = 0

        def drifting(path: Path):
            nonlocal calls
            item = original(path)
            if path == root:
                calls += 1
                if calls > 1:
                    values = list(item)
                    values[2] = item.st_dev + 1
                    return type(item)(values)
            return item

        with patch.object(Path, "lstat", drifting):
            with self.assertRaises(ReleaseError) as raised:
                self._materialize(stored)
        self.assertEqual("WFREL_CANDIDATE_INVALID", raised.exception.code)
        self.assertEqual([], list(root.iterdir()))

    def test_unsupported_server_component_fails_with_install_code_before_object_commit(self) -> None:
        self.source.write_bytes(_server_release(self.release_raw))
        with self.assertRaises(ReleaseError) as raised:
            self._import()
        self.assertEqual("WFREL_INSTALL_UNSUPPORTED_COMPONENT", raised.exception.code)
        objects = self.target.state_root / "objects"
        self.assertFalse(objects.exists() and any(objects.iterdir()))

    def test_stored_object_and_candidate_do_not_retain_source_or_target_paths_in_repr(self) -> None:
        stored = self._import()
        candidates = self._materialize(stored)
        self.assertNotIn(str(self.source), repr(stored))
        self.assertNotIn(str(self.target.state_root), repr(stored))
        # Candidate roots are host-local return values, but identities remain path-free.
        self.assertNotIn(str(self.source), repr(candidates))
        self.assertNotIn(str(self.target.state_root), repr(candidates.identities))


if __name__ == "__main__":
    unittest.main()
