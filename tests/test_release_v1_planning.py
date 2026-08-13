from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import wf_character_workspace
from wf_release_v1.compatibility import ActiveRelease, ActiveState
from wf_release_v1.errors import ReleaseError
from wf_release_v1.producer import BuildRequest, build_character_release
from wf_release_v1.receipts import commit_active_state
from wf_release_v1.schema import parse_requirements
from wf_release_v1.target import ComponentRoots, ManagedTarget, TargetCompatibility
from wf_release_v1.verifier import verify_release_contract
from tests.release_v1_fixtures import make_patch_overlay, make_sealed_character_workspace
from tests.release_v1_schema_support import requirements_wire
from tests.test_release_v1_compatibility import _target


@dataclass
class FakeProbe:
    value: object

    def run(self):
        return self.value


class ReleasePlanningTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        roots = {name: self.root / name for name in (
            "server", "runtime", "data", "state", "cdn", "modes",
            "candidate-content", "candidate-server", "candidate-modes",
        )}
        for path in roots.values():
            path.mkdir()
        self.target = ManagedTarget(
            roots["server"], roots["runtime"], roots["data"], roots["state"],
            roots["cdn"], roots["modes"],
            ComponentRoots(
                roots["candidate-content"], roots["candidate-server"], roots["candidate-modes"]
            ),
            TargetCompatibility("1.4.54", "1.4.54", True),
            "http://127.0.0.1:8001",
        )
        self.workspace = make_sealed_character_workspace(self.root / "workspaces")
        current = wf_character_workspace.load_workspace(self.workspace)
        manifest_path = current.package_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["required_capabilities"] = ["content.sync@1"]
        manifest["qa"]["workspace_input_sha256"] = ""
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        wf_character_workspace.seal_workspace(current)
        overlay = make_patch_overlay(
            self.root / "overlay.zip", from_version="1.4.54", target_version="1.4.55"
        )
        self.release = self.root / "release.zip"
        build_character_release(BuildRequest(
            name="seris-dragon-king",
            version="1.0.0",
            workspace=self.workspace,
            overlay_archives=(overlay,),
            output=self.release,
            requirements=parse_requirements(requirements_wire()),
        ))
        self.facts = _target(cdn_target_version="1.4.54")

    def _tree_snapshot(self) -> tuple[tuple[str, str, bytes], ...]:
        snapshot: list[tuple[str, str, bytes]] = []
        for path in self.root.rglob("*"):
            relative = path.relative_to(self.root).as_posix()
            if path.is_symlink():
                snapshot.append((relative, "symlink", str(path.readlink()).encode()))
            elif path.is_dir():
                snapshot.append((relative, "directory", b""))
            else:
                snapshot.append((relative, "file", path.read_bytes()))
        return tuple(sorted(snapshot))

    def test_captures_strict_requirements_from_workspace_and_live_facts_no_clobber(self) -> None:
        from wf_release_v1.planning import capture_target_requirements

        output = self.root / "requirements.json"
        with patch.object(ManagedTarget, "target_probe", return_value=FakeProbe(self.facts)):
            receipt = capture_target_requirements(self.target, self.workspace, output)
        value = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(["content.sync@1"], value["serverCapabilities"])
        self.assertEqual(["1.4.54"], value["clientVersions"])
        self.assertEqual(["1.4.54"], value["resourceBaselines"])
        self.assertEqual([self.facts.content_digest], value["contentDigests"])
        self.assertEqual(1, value["runtimeApi"])
        self.assertEqual(1, value["patchOverlaySchema"])
        self.assertTrue(value["clientPatchProfile"])
        self.assertEqual(1, receipt.requirements_capture_version)

        with self.assertRaisesRegex(ReleaseError, "new absolute path"):
            capture_target_requirements(self.target, self.workspace, output)

    def test_capture_rejects_missing_capability_and_unsealed_workspace(self) -> None:
        from wf_release_v1.planning import capture_target_requirements

        missing = _target(capabilities=("mode.release-contract@1",))
        with (
            patch.object(ManagedTarget, "target_probe", return_value=FakeProbe(missing)),
            self.assertRaisesRegex(ReleaseError, "capability"),
        ):
            capture_target_requirements(
                self.target, self.workspace, self.root / "missing.json"
            )
        self.assertFalse((self.root / "missing.json").exists())

        current = wf_character_workspace.load_workspace(self.workspace)
        asset = next((current.package_dir / "roots/medium").rglob("*.png"))
        asset.write_bytes(asset.read_bytes() + b"drift")
        with (
            patch.object(ManagedTarget, "target_probe", return_value=FakeProbe(self.facts)),
            self.assertRaisesRegex(ReleaseError, "sealed"),
        ):
            capture_target_requirements(
                self.target, self.workspace, self.root / "unsealed.json"
            )

    def test_plan_install_is_read_only_and_reports_compatibility_and_rollback(self) -> None:
        from wf_release_v1.planning import plan_install

        before = {path.relative_to(self.root).as_posix(): path.read_bytes()
                  for path in self.root.rglob("*") if path.is_file()}
        with patch.object(ManagedTarget, "target_probe", return_value=FakeProbe(self.facts)):
            plan = plan_install(self.release, self.target)
        after = {path.relative_to(self.root).as_posix(): path.read_bytes()
                 for path in self.root.rglob("*") if path.is_file()}
        self.assertEqual(before, after)
        self.assertTrue(plan.compatible)
        self.assertEqual((), plan.codes)
        self.assertEqual("1.4.55", plan.expected_cdn_target_version)
        self.assertEqual("1.4.54", plan.current_cdn_target_version)
        self.assertFalse(plan.rollback_available)
        self.assertFalse(plan.writes_live)

        incompatible = _target(
            cdn_target_version="1.4.54",
            content_digest="sha256:" + "f" * 64,
        )
        with patch.object(ManagedTarget, "target_probe", return_value=FakeProbe(incompatible)):
            rejected = plan_install(self.release, self.target)
        self.assertFalse(rejected.compatible)
        self.assertIn("WFREL_REQUIRE_CONTENT_DIGEST", rejected.codes)

    def test_plan_reports_an_occupied_target_version_without_reading_or_writing_it(self) -> None:
        from wf_release_v1.planning import plan_install

        occupied = self.target.cdn_root / "patches" / "1.4.55"
        occupied.mkdir(parents=True)
        (occupied / "foreign.zip").write_bytes(b"foreign release bytes")
        before = self._tree_snapshot()

        with patch.object(ManagedTarget, "target_probe", return_value=FakeProbe(self.facts)):
            plan = plan_install(self.release, self.target)

        self.assertFalse(plan.compatible)
        self.assertEqual(("WFREL_STATE_VERSION_CONFLICT",), plan.codes)
        self.assertFalse(plan.no_op)
        self.assertFalse(plan.writes_live)
        self.assertEqual(before, self._tree_snapshot())

    def test_plan_keeps_an_exact_active_release_as_no_op_when_version_exists(self) -> None:
        from wf_release_v1.planning import plan_install

        _report, verified = verify_release_contract(self.release)
        empty = ActiveState("1.4.54", "1.4.54", True, (), ())
        active = ActiveState(
            "1.4.54",
            "1.4.54",
            True,
            (ActiveRelease(verified.manifest.release_id, verified.ownership),),
            (verified.manifest.release_id,),
        )
        commit_active_state(self.target.state_root, previous=empty, active=active)
        (self.target.cdn_root / "patches" / "1.4.55").mkdir(parents=True)

        with patch.object(ManagedTarget, "target_probe", return_value=FakeProbe(self.facts)):
            plan = plan_install(self.release, self.target)

        self.assertTrue(plan.compatible)
        self.assertEqual(("WFREL_OWNERSHIP_NOOP",), plan.codes)
        self.assertTrue(plan.no_op)

    def test_plan_treats_a_broken_target_version_symlink_as_occupied(self) -> None:
        from wf_release_v1.planning import plan_install

        occupied = self.target.cdn_root / "patches" / "1.4.55"
        occupied.parent.mkdir(parents=True)
        original_is_symlink = Path.is_symlink
        try:
            occupied.symlink_to(self.root / "missing-version", target_is_directory=True)
        except OSError:
            symlink_boundary = patch.object(
                Path,
                "is_symlink",
                autospec=True,
                side_effect=lambda path: (
                    path == occupied or original_is_symlink(path)
                ),
            )
        else:
            symlink_boundary = nullcontext()

        with (
            symlink_boundary,
            patch.object(ManagedTarget, "target_probe", return_value=FakeProbe(self.facts)),
        ):
            plan = plan_install(self.release, self.target)

        self.assertFalse(plan.compatible)
        self.assertEqual(("WFREL_STATE_VERSION_CONFLICT",), plan.codes)


if __name__ == "__main__":
    unittest.main()
