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
from wf_release_v1.target import ComponentRoots, ManagedTarget, TargetCompatibility


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
        cls.workspace = workspace
        overlay = make_patch_overlay(
            root / "source" / "worldflipper-overlay-1.4.54-to-1.4.55.zip",
            from_version="1.4.54",
            target_version="1.4.55",
        )
        cls.overlay_raw = overlay.read_bytes()
        with zipfile.ZipFile(io.BytesIO(cls.overlay_raw), "r") as bundle:
            cls.overlay_members = tuple(
                (item.filename, bundle.read(item)) for item in bundle.infolist()
            )
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
                "active-cdn", "active-modes", "content-components",
                "server-components", "mode-components",
            )
        }
        for path in paths.values():
            path.mkdir()
        self.target = ManagedTarget(
            server_bundle=paths["server-bundle"],
            runtime_pack=paths["runtime-pack"],
            data_root=paths["data"],
            state_root=paths["state"],
            cdn_root=paths["active-cdn"],
            modes_root=paths["active-modes"],
            component_roots=ComponentRoots(
                paths["content-components"], paths["server-components"], paths["mode-components"]
            ),
            compatibility=TargetCompatibility("1.4.54", "1.4.54", False),
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

    def test_content_candidate_unpacks_overlay_into_content_sync_receiver_layout_without_scanning_cn(self) -> None:
        import wf_release_v1.materialize as materialize_module

        sentinel = self.target.cdn_root / "cn" / "ten-gigabyte-sentinel.bin"
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
        receiver_root = expected_root / "patches" / "1.4.55"
        expected_paths = tuple(sorted(
            [
                f"patches/1.4.55/{name}"
                for name, _raw in self.overlay_members
            ] + [
                "patches/1.4.55/worldflipper-overlay-1.4.54-to-1.4.55.zip",
            ],
            key=lambda item: item.encode("utf-8"),
        ))
        for name, raw in self.overlay_members:
            self.assertEqual(raw, (receiver_root / Path(name)).read_bytes())
        self.assertEqual(
            self.overlay_raw,
            (receiver_root / "worldflipper-overlay-1.4.54-to-1.4.55.zip").read_bytes(),
        )
        self.assertEqual(b"official-baseline-must-not-be-read", sentinel.read_bytes())
        self.assertEqual(expected_paths, candidates.relative_paths)
        expected_raw = dict(self.overlay_members)
        expected_raw["worldflipper-overlay-1.4.54-to-1.4.55.zip"] = self.overlay_raw
        expected_identities = tuple(
            (len(raw), hashlib.sha256(raw).hexdigest())
            for name, raw in sorted(expected_raw.items(), key=lambda item: item[0].encode("utf-8"))
        )
        self.assertEqual(
            expected_identities,
            tuple((item.size, item.sha256) for item in candidates.identities),
        )

    def test_candidate_identity_rejects_a_different_but_valid_overlay(self) -> None:
        from wf_release_v1.materialize import verify_candidates

        candidates = self._materialize()
        outer_relative = next(
            relative
            for relative in candidates.relative_paths
            if len(Path(relative).parts) == 3
            and Path(relative).name
            not in {"README.md", "requires.json", "patch-manifest.json"}
        )
        candidate_file = candidates.content_root / Path(outer_relative)
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

    def test_candidate_verifier_cross_binds_receiver_members_to_retained_outer(self) -> None:
        from wf_release_v1.canonical import FileIdentity
        from wf_release_v1.materialize import verify_candidates

        candidates = self._materialize()
        outer_index = next(
            index
            for index, relative in enumerate(candidates.relative_paths)
            if len(Path(relative).parts) == 3
            and Path(relative).name
            not in {"README.md", "requires.json", "patch-manifest.json"}
        )
        outer = candidates.content_root / Path(candidates.relative_paths[outer_index])
        output = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(self.overlay_raw)) as source, zipfile.ZipFile(
            output, "w", compression=zipfile.ZIP_DEFLATED
        ) as changed:
            for item in source.infolist():
                raw = source.read(item)
                changed.writestr(
                    item.filename,
                    b"valid but unrelated readme\n" if item.filename == "README.md" else raw,
                )
        alternate = output.getvalue()
        outer.write_bytes(alternate)
        forged_identities = list(candidates.identities)
        forged_identities[outer_index] = FileIdentity(
            len(alternate), hashlib.sha256(alternate).hexdigest()
        )

        with self.assertRaises(ReleaseError) as raised:
            verify_candidates(replace(candidates, identities=tuple(forged_identities)))

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

    def test_partial_overlay_write_and_readback_failure_leave_no_candidate_residue(self) -> None:
        import wf_release_v1.overlay_candidates as overlay_candidates

        stored = self._import()
        real_copy = overlay_candidates._copy_member
        calls = 0

        def fail_after_first_write(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise ReleaseError("WFREL_CANDIDATE_IO", "injected partial write")
            return real_copy(*args, **kwargs)

        with patch.object(
            overlay_candidates, "_copy_member", side_effect=fail_after_first_write
        ):
            with self.assertRaises(ReleaseError) as raised:
                self._materialize(stored)
        self.assertEqual("WFREL_CANDIDATE_IO", raised.exception.code)
        self.assertEqual([], list(self.target.component_roots.content.iterdir()))

        with patch.object(
            overlay_candidates,
            "verify_materialized_overlay",
            side_effect=ReleaseError("WFREL_CANDIDATE_INVALID", "injected readback"),
        ):
            with self.assertRaises(ReleaseError) as raised:
                self._materialize(stored)
        self.assertEqual("WFREL_CANDIDATE_INVALID", raised.exception.code)
        self.assertEqual([], list(self.target.component_roots.content.iterdir()))

    def test_legacy_switch_uses_retained_outer_and_ignores_receiver_members(self) -> None:
        from wf_release_v1._legacy_files import prepare_legacy_switch
        from wf_release_v1.legacy_compatibility import LegacyInstallPlan
        from wf_release_v1.verifier_overlay import inspect_overlay_chain

        candidates = self._materialize()
        outer = self.root / "legacy-plan-overlay.zip"
        outer.write_bytes(self.overlay_raw)
        overlay = inspect_overlay_chain((outer,))
        plan = LegacyInstallPlan(
            candidates.release_id,
            False,
            True,
            False,
            (),
            overlay.from_version,
            overlay.target_version,
            overlay=overlay,
        )
        cn_root = self.target.cdn_root / "cn"
        for layer in ("common", "medium", "android"):
            (cn_root / f"archive-{layer}-diff").mkdir(parents=True, exist_ok=True)

        switch = prepare_legacy_switch(
            candidates,
            plan,
            self.target.state_root,
            self.target.cdn_root,
            OPERATION_ID,
        )

        self.assertEqual(3, len(switch.archives))
        self.assertEqual(
            {"android", "common", "medium"},
            {
                item.relative_path.split("/", 1)[0]
                .removeprefix("archive-")
                .removesuffix("-diff")
                for item in switch.archives
            },
        )

    def test_invalid_operation_id_and_root_device_drift_fail_before_candidate_write(self) -> None:
        from wf_release_v1.materialize import materialize_candidates

        stored = self._import()
        with self.assertRaises(ReleaseError) as raised:
            materialize_candidates(stored, self.target, "../bad-operation")
        self.assertEqual("WFREL_CANDIDATE_INVALID", raised.exception.code)
        self.assertEqual([], list(self.target.component_roots.content.iterdir()))

        import wf_release_v1.materialize as materialize_module
        from wf_release_v1._path_io import native_path

        original = materialize_module.os.lstat
        root = self.target.component_roots.content
        root_native = native_path(root)
        calls = 0

        def drifting(path):
            nonlocal calls
            item = original(path)
            if str(path) == root_native:
                calls += 1
                if calls > 1:
                    values = list(item)
                    values[2] = item.st_dev + 1
                    return type(item)(values)
            return item

        with patch.object(materialize_module.os, "lstat", side_effect=drifting):
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

    def test_multi_edge_release_fails_closed_before_content_candidate_write(self) -> None:
        first = make_patch_overlay(
            self.root / "source-overlays" / "edge-1.zip",
            from_version="1.4.54",
            target_version="1.4.55",
        )
        second = make_patch_overlay(
            self.root / "source-overlays" / "edge-2.zip",
            from_version="1.4.55",
            target_version="1.4.56",
        )
        release = self.root / "multi-edge-release.zip"
        build_character_release(
            BuildRequest(
                name="seris-dragon-king-multi-edge",
                version="1.0.0",
                workspace=self.workspace,
                overlay_archives=(first, second),
                output=release,
                requirements=parse_requirements(requirements_wire()),
            )
        )
        self.source.write_bytes(release.read_bytes())
        stored = self._import()

        with self.assertRaises(ReleaseError) as raised:
            self._materialize(stored)

        self.assertEqual("WFREL_INSTALL_UNSUPPORTED_COMPONENT", raised.exception.code)
        self.assertEqual([], list(self.target.component_roots.content.iterdir()))

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
