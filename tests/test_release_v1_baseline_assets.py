"""Modern Content Snapshot resolution for shared-asset before identities."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import warnings
import zipfile

from tests.release_v1_schema_support import HEX_A, requirements_wire, release_without_id
from tests.test_release_v1_compatibility import _target
from wf_release_v1.canonical import canonical_json_bytes
from wf_release_v1.compatibility import VerifiedRelease
from wf_release_v1.schema import (
    compute_release_id,
    parse_ownership,
    parse_release_manifest,
    parse_requirements,
)
from wf_release_v1.target import ComponentRoots, ManagedTarget, TargetCompatibility
from wf_release_v1.verifier_overlay import VerifiedOverlayChain, VerifiedOverlayEdge


SHEET_LOGICAL = "item/sprite_sheet.png"
ATLAS_LOGICAL = "item/sprite_sheet.atlas.amf3.deflate"
SHEET_MEMBER = "production/upload/6d/4d576b424178c5b2b253a2dd5aa3d78fa74ef3"
ATLAS_MEMBER = "production/upload/7b/5e0efc0e0691038ca52fe282501dfd3a1b5ae3"
MEDIUM_SHEET_MEMBER = (
    "production/medium_upload/6d/4d576b424178c5b2b253a2dd5aa3d78fa74ef3"
)
SHEET_BEFORE = b"sheet-before"
ATLAS_BEFORE = b"atlas-before"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class ModernSnapshotFixture:
    def __init__(self, root: Path) -> None:
        roots = {
            name: root / name
            for name in (
                "server", "runtime", "data", "state", "cdn", "modes",
                "candidate-content", "candidate-server", "candidate-modes",
            )
        }
        for path in roots.values():
            path.mkdir()
        (roots["cdn"] / "cn").mkdir()
        (roots["cdn"] / "patches").mkdir()
        self.target = ManagedTarget(
            roots["server"], roots["runtime"], roots["data"], roots["state"],
            roots["cdn"], roots["modes"],
            ComponentRoots(
                roots["candidate-content"],
                roots["candidate-server"],
                roots["candidate-modes"],
            ),
            TargetCompatibility("1.4.54", "1.4.53", True),
            "http://127.0.0.1:8001",
        )
        self.release_digest = self.write_snapshot(SHEET_BEFORE)

    @staticmethod
    def _archive(path: Path, members: dict[str, bytes], *, layer: str, order: int):
        path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as bundle:
            for name, raw in members.items():
                bundle.writestr(name, raw)
        raw = path.read_bytes()
        return {
            "compressedBytes": len(raw),
            "layer": layer,
            "order": order,
            "relativePath": path.parent.name + "/" + path.name,
            "sha256": _sha(raw),
        }

    def _object(self, value: object) -> str:
        raw = canonical_json_bytes(value)
        digest = _sha(raw)
        objects = self.target.data_root / "content" / "store" / "objects"
        objects.mkdir(parents=True, exist_ok=True)
        (objects / f"{digest}.json").write_bytes(raw)
        return f"sha256:{digest}"

    def write_snapshot(self, sheet: bytes) -> str:
        baseline_relative = (
            "archive-common-full/pinball-1.4.0-1-baseline.zip"
        )
        patch_relative = (
            "archive-common-diff/pinball-1.4.53-1.4.54-1-patch.zip"
        )
        quality_relative = (
            "archive-quality-full/pinball-1.4.0-1-quality.zip"
        )
        baseline = self._archive(
            self.target.cdn_root / "cn" / Path(baseline_relative),
            {SHEET_MEMBER: b"older-sheet", ATLAS_MEMBER: ATLAS_BEFORE},
            layer="common",
            order=1,
        )
        patch = self._archive(
            self.target.cdn_root / "patches" / "1.4.54" / Path(patch_relative),
            {SHEET_MEMBER: sheet},
            layer="common",
            order=1,
        )
        quality = self._archive(
            self.target.cdn_root / "cn" / Path(quality_relative),
            {MEDIUM_SHEET_MEMBER: b"unrelated-medium-drift"},
            layer="quality",
            order=1,
        )
        catalog = {
            "edges": [
                {
                    "archives": [baseline, quality],
                    "assetSizeKind": "fulfill",
                    "fromVersion": None,
                    "platform": "android",
                    "toVersion": "1.4.53",
                },
                {
                    "archives": [patch],
                    "assetSizeKind": "fulfill",
                    "fromVersion": "1.4.53",
                    "platform": "android",
                    "toVersion": "1.4.54",
                },
            ],
            "entityListsRelativePath": "EntityLists/fixture.csv",
            "fullBaseVersion": "1.4.53",
            "installedBytes": (
                baseline["compressedBytes"]
                + quality["compressedBytes"]
                + patch["compressedBytes"]
            ),
            "schemaVersion": 1,
            "targetVersion": "1.4.54",
        }
        sources = {
            "schemaVersion": 1,
            "archives": [
                {"relativePath": baseline_relative, "source": {"kind": "baseline"}},
                {"relativePath": quality_relative, "source": {"kind": "baseline"}},
                {
                    "relativePath": patch_relative,
                    "source": {"kind": "patch", "targetVersion": "1.4.54"},
                },
            ],
        }
        summary = {
            "archiveSources": sources,
            "assetVersion": "1.4.54",
            "counts": {"archives": 3, "ignoredPaths": 0, "tables": 1},
            "entityListsRelativePath": "EntityLists/fixture.csv",
            "generatorVersion": 3,
            "patchSourceDigest": "sha256:" + "9" * 64,
            "schemaVersion": 1,
        }
        manifest_body = {
            "assetVersion": "1.4.54",
            "catalog": {"object": self._object(catalog)},
            "generatorVersion": 3,
            "runtimeSchemaVersion": 1,
            "schemaVersion": 1,
            "summary": {"object": self._object(summary)},
            "tables": {
                "fixture.json": {
                    "converterId": "fixture",
                    "converterVersion": 1,
                    "object": "sha256:" + "8" * 64,
                    "scope": "cdn",
                    "sources": ["master/fixture.orderedmap"],
                }
            },
        }
        release_digest = "sha256:" + _sha(canonical_json_bytes(manifest_body))
        manifest = {**manifest_body, "releaseDigest": release_digest}
        release_relative = (
            f"releases/1.4.54-{release_digest.removeprefix('sha256:')}/manifest.json"
        )
        release_path = (
            self.target.data_root / "content" / "store" / Path(release_relative)
        )
        release_path.parent.mkdir(parents=True, exist_ok=True)
        release_path.write_bytes(canonical_json_bytes(manifest))
        current = self.target.data_root / "state" / "content" / "current.json"
        current.parent.mkdir(parents=True, exist_ok=True)
        current.write_bytes(canonical_json_bytes({
            "assetVersion": "1.4.54",
            "release": release_relative,
            "schemaVersion": 1,
        }))
        self.release_digest = release_digest
        return release_digest


def _verified() -> VerifiedRelease:
    manifest = release_without_id()
    manifest["sourceEvidence"] = {
        "acceptedAssetReplacements": [
            {
                "beforeSha256": _sha(ATLAS_BEFORE),
                "beforeSize": len(ATLAS_BEFORE),
                "logicalPath": ATLAS_LOGICAL,
                "root": "common",
            },
            {
                "beforeSha256": _sha(SHEET_BEFORE),
                "beforeSize": len(SHEET_BEFORE),
                "logicalPath": SHEET_LOGICAL,
                "root": "common",
            },
        ],
        "kind": "character-workspace-v2",
        "workspaceInputSha256": "a" * 64,
    }
    manifest["expectedState"]["cdnTargetVersion"] = "1.4.55"  # type: ignore[index]
    manifest["releaseId"] = compute_release_id(manifest)
    ownership = parse_ownership({
        "schemaVersion": 1,
        "entities": ["character:129999"],
        "records": [
            "asset:common/item/sprite_sheet.atlas.amf3.deflate",
            "asset:common/item/sprite_sheet.png",
            "character:129999",
        ],
        "paths": [ATLAS_LOGICAL, SHEET_LOGICAL],
    })
    overlay = VerifiedOverlayChain(
        "1.4.54", "1.4.55", (VerifiedOverlayEdge("1.4.54", "1.4.55", ()),)
    )
    return VerifiedRelease(
        parse_release_manifest(manifest),
        parse_requirements(requirements_wire()),
        ownership,
        overlay,
    )


class BaselineAssetTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="wfrel-baseline-assets-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.snapshot = ModernSnapshotFixture(self.root)
        self.verified = _verified()

    def facts(self):
        return _target(
            cdn_target_version="1.4.54",
            release_digest=self.snapshot.release_digest,
        )

    def active_objects(self) -> tuple[dict[str, object], dict[str, object]]:
        store = self.snapshot.target.data_root / "content" / "store"
        current = json.loads((
            self.snapshot.target.data_root / "state" / "content" / "current.json"
        ).read_text(encoding="utf-8"))
        release = json.loads((store / Path(current["release"])).read_text(encoding="utf-8"))
        catalog = json.loads((
            store / "objects" / (release["catalog"]["object"][7:] + ".json")
        ).read_text(encoding="utf-8"))
        summary = json.loads((
            store / "objects" / (release["summary"]["object"][7:] + ".json")
        ).read_text(encoding="utf-8"))
        return catalog, summary

    def test_resolves_two_real_logical_members_with_patch_last_wins(self) -> None:
        from wf_release_v1.baseline_assets import verify_asset_replacement_baseline

        report = verify_asset_replacement_baseline(
            self.verified, self.snapshot.target, self.facts()
        )

        self.assertEqual(2, report.checked)
        self.assertEqual("1.4.54", report.asset_version)
        self.assertEqual(self.snapshot.release_digest, report.release_digest)

    def test_same_logical_path_in_quality_layer_does_not_override_common(self) -> None:
        from wf_release_v1.baseline_assets import verify_asset_replacement_baseline

        report = verify_asset_replacement_baseline(
            self.verified, self.snapshot.target, self.facts()
        )

        self.assertEqual(2, report.checked)

    def test_current_pointer_is_canonical_closed_and_release_digest_bound(self) -> None:
        from wf_release_v1.baseline_assets import verify_asset_replacement_baseline
        from wf_release_v1.errors import ReleaseError

        current = self.snapshot.target.data_root / "state" / "content" / "current.json"
        value = json.loads(current.read_text(encoding="utf-8"))
        value["unexpected"] = True
        current.write_bytes(canonical_json_bytes(value))
        with self.assertRaises(ReleaseError) as unknown:
            verify_asset_replacement_baseline(
                self.verified, self.snapshot.target, self.facts()
            )
        self.assertEqual("WFREL_ASSET_BASELINE_UNAVAILABLE", unknown.exception.code)

        self.snapshot.write_snapshot(SHEET_BEFORE)
        current.write_text(
            json.dumps(json.loads(current.read_text(encoding="utf-8")), indent=2) + "\n",
            encoding="utf-8",
        )
        with self.assertRaises(ReleaseError) as noncanonical:
            verify_asset_replacement_baseline(
                self.verified, self.snapshot.target, self.facts()
            )
        self.assertEqual(
            "WFREL_ASSET_BASELINE_UNAVAILABLE",
            noncanonical.exception.code,
        )

        self.snapshot.write_snapshot(SHEET_BEFORE)
        wrong_facts = _target(
            cdn_target_version="1.4.54",
            release_digest="sha256:" + "f" * 64,
        )
        with self.assertRaises(ReleaseError) as wrong_release:
            verify_asset_replacement_baseline(
                self.verified, self.snapshot.target, wrong_facts
            )
        self.assertEqual(
            "WFREL_ASSET_BASELINE_UNAVAILABLE",
            wrong_release.exception.code,
        )

        bundled_facts = _target(
            cdn_target_version="1.4.54",
            release_digest=None,
        )
        with self.assertRaises(ReleaseError) as missing_release:
            verify_asset_replacement_baseline(
                self.verified, self.snapshot.target, bundled_facts
            )
        self.assertEqual(
            "WFREL_ASSET_BASELINE_UNAVAILABLE",
            missing_release.exception.code,
        )

    def test_catalog_summary_and_archive_shapes_fail_closed(self) -> None:
        from wf_release_v1._baseline_snapshot import _archive_sources, _catalog
        from wf_release_v1.baseline_assets import _member_identity
        from wf_release_v1._baseline_snapshot import ArchiveDescriptor
        from wf_release_v1.errors import ReleaseError

        catalog, summary = self.active_objects()
        unknown_catalog = copy.deepcopy(catalog)
        unknown_catalog["unexpected"] = True
        with self.assertRaises(ReleaseError):
            _catalog(unknown_catalog, "1.4.54")

        aliased_catalog = copy.deepcopy(catalog)
        aliased_catalog["edges"][0]["archives"][0]["relativePath"] = (  # type: ignore[index]
            "archive-common-full/../aliased.zip"
        )
        with self.assertRaises(ReleaseError):
            _catalog(aliased_catalog, "1.4.54")

        parsed_catalog, _scoped, by_path = _catalog(catalog, "1.4.54")
        unknown_summary = copy.deepcopy(summary)
        unknown_summary["unexpected"] = True
        with self.assertRaises(ReleaseError):
            _archive_sources(
                unknown_summary,
                asset_version="1.4.54",
                catalog=parsed_catalog,
                by_path=by_path,
                release_generator_version=3,
                release_table_count=1,
            )

        summary_mutations = {
            "generator": lambda value: value.__setitem__("generatorVersion", 4),
            "archive count": lambda value: value["counts"].__setitem__(  # type: ignore[union-attr]
                "archives", 4
            ),
            "table count": lambda value: value["counts"].__setitem__(  # type: ignore[union-attr]
                "tables", 2
            ),
        }
        for label, mutate in summary_mutations.items():
            with self.subTest(summary_cross_binding=label):
                changed = copy.deepcopy(summary)
                mutate(changed)
                with self.assertRaises(ReleaseError):
                    _archive_sources(
                        changed,
                        asset_version="1.4.54",
                        catalog=parsed_catalog,
                        by_path=by_path,
                        release_generator_version=3,
                        release_table_count=1,
                    )

        duplicate = self.snapshot.target.cdn_root / "cn" / "duplicate.zip"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(
                duplicate, "w", compression=zipfile.ZIP_STORED
            ) as bundle:
                bundle.writestr(SHEET_MEMBER, SHEET_BEFORE)
                bundle.writestr(SHEET_MEMBER, SHEET_BEFORE)
        raw = duplicate.read_bytes()
        descriptor = ArchiveDescriptor(
            "duplicate.zip", len(raw), _sha(raw), "common", 1, "baseline", None
        )
        with self.assertRaises(ReleaseError) as duplicate_member:
            _member_identity(
                self.snapshot.target,
                descriptor,
                SHEET_MEMBER,
                expected_size=len(SHEET_BEFORE),
            )
        self.assertEqual(
            "WFREL_ASSET_BASELINE_UNAVAILABLE",
            duplicate_member.exception.code,
        )

    def test_selected_edges_handles_a_long_valid_chain_without_recursion(self) -> None:
        from wf_release_v1._baseline_snapshot import _selected_edges

        full = {"fromVersion": None, "toVersion": "1.0.0"}
        diffs = tuple(
            {
                "fromVersion": f"1.0.{index}",
                "toVersion": f"1.0.{index + 1}",
            }
            for index in range(1100)
        )

        selected = _selected_edges(
            {"targetVersion": "1.0.1100"},
            (full, *diffs),
        )

        self.assertEqual(1101, len(selected))
        self.assertIs(full, selected[0])
        self.assertIs(diffs[-1], selected[-1])

    def test_selected_edges_rejects_ambiguous_and_cyclic_graphs_closed(self) -> None:
        from wf_release_v1._baseline_snapshot import _selected_edges
        from wf_release_v1.errors import ReleaseError

        full = {"fromVersion": None, "toVersion": "1.0.0"}
        bad_graphs = {
            "ambiguous": (
                {"targetVersion": "1.0.2"},
                (
                    full,
                    {"fromVersion": "1.0.0", "toVersion": "1.0.1"},
                    {"fromVersion": "1.0.0", "toVersion": "1.0.2"},
                    {"fromVersion": "1.0.1", "toVersion": "1.0.2"},
                ),
            ),
            "cycle": (
                {"targetVersion": "1.0.9"},
                (
                    full,
                    {"fromVersion": "1.0.0", "toVersion": "1.0.1"},
                    {"fromVersion": "1.0.1", "toVersion": "1.0.0"},
                ),
            ),
        }
        for label, (catalog, scoped) in bad_graphs.items():
            with self.subTest(graph=label), self.assertRaises(ReleaseError) as caught:
                _selected_edges(catalog, scoped)
            self.assertEqual(
                "WFREL_ASSET_BASELINE_UNAVAILABLE",
                caught.exception.code,
            )

    def test_plan_rechecks_authoritative_snapshot_after_prior_success_without_writes(self) -> None:
        from wf_release_v1.planning import plan_verified_install

        before = tuple(sorted(
            (path.relative_to(self.root).as_posix(), path.read_bytes())
            for path in self.root.rglob("*") if path.is_file()
        ))
        accepted = plan_verified_install(
            self.verified, self.snapshot.target, self.facts()
        )
        self.assertTrue(accepted.compatible)
        self.assertFalse(accepted.writes_live)
        self.assertEqual(before, tuple(sorted(
            (path.relative_to(self.root).as_posix(), path.read_bytes())
            for path in self.root.rglob("*") if path.is_file()
        )))

        self.snapshot.write_snapshot(b"drifted-sheet")
        rejected = plan_verified_install(
            self.verified, self.snapshot.target, self.facts()
        )
        self.assertFalse(rejected.compatible)
        self.assertEqual(("WFREL_ASSET_BASELINE_MISMATCH",), rejected.codes)
        self.assertFalse(rejected.writes_live)


if __name__ == "__main__":
    unittest.main()
