# -*- coding: utf-8 -*-
"""Frozen bundle to scoped-plan adapter tests; all stores are temporary fixtures."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from release_inventory_support import (
    InventoryCase,
    LOGICAL,
    ordered,
    sha256,
    snapshot_tree,
)

import wf_character_pack as character_pack
import wf_local_release_contract as local_contract
import wf_local_release_provenance as provenance
import wf_mod_tool as core
import wf_release_inventory as inventory
import wf_local_scoped_release as adapter


FILE_LOGICAL = "character/fixture/terminal.bin"


class LocalScopedReleaseTest(InventoryCase):
    def setUp(self) -> None:
        super().setUp()
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.cdn = self.repo / ".cdn" / "cn"
        self.contract_dir = self.repo / "mod-tools" / "release-contracts"
        self.contract_dir.mkdir(parents=True)
        self.cdn.mkdir(parents=True)
        self.live = {
            root: self.root / "live" / root
            for root in ("common", "medium", "android")
        }
        for path in self.live.values():
            path.mkdir(parents=True)
        self._make_bundle()
        self._write_live()

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def archive_member(root: str, logical: str) -> str:
        prefix = character_pack.ARCHIVE_PREFIXES[root]
        digest = core.sha1_path(logical)
        return f"{prefix}{digest[:2]}/{digest[2:]}"

    def evidence(
        self,
        version: str,
        logical: str,
        raw: bytes,
        *,
        table_claims: tuple[provenance.ClaimEvidence, ...] = (),
    ) -> provenance.BaselineEvidence:
        return provenance.BaselineEvidence(
            writer=(
                f".cdn/cn/archive-common-diff/"
                f"pinball-1.4.0-{version}-1-fixture.zip"
            ),
            archive_member=self.archive_member("common", logical),
            size=len(raw),
            sha256=sha256(raw),
            table_claims=table_claims,
        )

    def _make_bundle(self) -> None:
        self.claim = self.flat_claim("owned")
        self.terminal_table = ordered([
            ("sentinel", b"terminal-only"), ("owned", b"terminal-row")
        ])
        self.baseline_tables = {
            "1.4.277": ordered([
                ("sentinel", b"base-277"), ("owned", b"old-277")
            ]),
            "1.4.311": ordered([
                ("sentinel", b"base-311"), ("owned", b"old-311")
            ]),
        }
        self.terminal_file = b"terminal-file"
        self.baseline_file = b"old-311-file"
        terminal = self.parse(self.payload([
            self.member("table-owner", self.terminal_table, self.claim),
            self.file_member("file-owner", self.terminal_file, logical_path=FILE_LOGICAL),
        ]))
        baselines = {
            "1.4.277": self.parse(self.payload([
                self.member(
                    "table-owner", self.baseline_tables["1.4.277"], self.claim
                ),
            ])),
            "1.4.311": self.parse(self.payload([
                self.member(
                    "table-owner", self.baseline_tables["1.4.311"], self.claim
                ),
                self.file_member(
                    "file-owner", self.baseline_file, logical_path=FILE_LOGICAL
                ),
            ])),
        }
        table_versions = {}
        for version, raw in self.baseline_tables.items():
            table_versions[version] = self.evidence(
                version,
                LOGICAL,
                raw,
                table_claims=(provenance.ClaimEvidence(
                    "table-owner",
                    True,
                    inventory.projection_sha256(raw, self.claim),
                ),),
            )
        file_versions = {
            "1.4.277": None,
            "1.4.311": self.evidence(
                "1.4.311", FILE_LOGICAL, self.baseline_file
            ),
        }
        provenance_contract = provenance.ProvenanceContract(
            contract_id="fixture-provenance",
            terminal_contract_id=terminal.contract_id,
            inventory_sha256="0" * 64,
            baselines=("1.4.277", "1.4.311"),
            members=(
                provenance.ProvenanceMember(
                    "common", LOGICAL, ("table-owner",), table_versions
                ),
                provenance.ProvenanceMember(
                    "common", FILE_LOGICAL, ("file-owner",), file_versions
                ),
            ),
        )
        self.bundle = local_contract.ContractBundle(
            terminal=terminal,
            baselines=baselines,
            provenance=provenance_contract,
            migrations=mock.sentinel.migrations,
        )
        self.resolved = {
            "1.4.277": {
                ("common", LOGICAL): self._resolved(
                    "1.4.277", LOGICAL, self.baseline_tables["1.4.277"]
                ),
            },
            "1.4.311": {
                ("common", LOGICAL): self._resolved(
                    "1.4.311", LOGICAL, self.baseline_tables["1.4.311"]
                ),
                ("common", FILE_LOGICAL): self._resolved(
                    "1.4.311", FILE_LOGICAL, self.baseline_file
                ),
            },
        }

    def _resolved(
        self, version: str, logical: str, raw: bytes
    ) -> inventory.ResolvedMember:
        evidence = next(
            member.versions[version]
            for member in self.bundle.provenance.members
            if member.logical_path == logical
        ) if hasattr(self, "bundle") else None
        if evidence is None:
            # During bundle construction, derive the same immutable path directly.
            evidence = self.evidence(version, logical, raw)
        return inventory.ResolvedMember(
            root="common",
            logical_path=logical,
            raw=raw,
            writer_archive=self.repo / evidence.writer,
            archive_member=self.archive_member("common", logical),
            tail=version,
        )

    def _write_live(self) -> None:
        for logical, raw in (
            (LOGICAL, self.terminal_table),
            (FILE_LOGICAL, self.terminal_file),
        ):
            path = core.table_path(self.live["common"], logical)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)

    def resolver(self, _cdn, _repo, allowlist, *, target_tail=None, **_kwargs):
        keys = set(allowlist)
        expected = set(self.resolved[target_tail])
        self.assertEqual(expected, keys)
        return dict(self.resolved[target_tail])

    def build(self):
        with mock.patch.object(
            adapter.local_contract, "load_bundle", return_value=self.bundle
        ) as loader, mock.patch.object(
            adapter.local_contract, "validate_bundle"
        ) as validator, mock.patch.object(
            adapter.local_contract, "attest_bundle_baselines"
        ) as attestor, mock.patch.object(
            adapter.inventory,
            "resolve_allowlisted_members",
            side_effect=self.resolver,
        ) as resolver:
            result = adapter.build_local_scoped_plans(
                self.contract_dir, self.cdn, self.repo, self.live
            )
        return result, loader, validator, attestor, resolver

    def test_strict_adapter_freezes_absence_and_exposes_fixed_edge_selections(self):
        before = snapshot_tree(self.root)
        result, loader, validator, attestor, resolver = self.build()
        self.assertEqual(before, snapshot_tree(self.root))
        loader.assert_called_once_with(self.contract_dir)
        validator.assert_called_once_with(self.bundle)
        attestor.assert_called_once_with(self.bundle, self.cdn, self.repo)
        self.assertEqual(2, resolver.call_count)

        snapshots = {item.version: item for item in result.baselines}
        self.assertEqual(2, len(snapshots["1.4.277"].values))
        self.assertIsNone(
            snapshots["1.4.277"].mapping[("common", FILE_LOGICAL)]
        )
        self.assertEqual(
            self.baseline_file,
            snapshots["1.4.311"].mapping[("common", FILE_LOGICAL)],
        )
        self.assertIsInstance(snapshots["1.4.277"].mapping, MappingProxyType)
        with self.assertRaises(TypeError):
            snapshots["1.4.277"].mapping[("common", FILE_LOGICAL)] = b"write"  # type: ignore[index]

        self.assertEqual(
            [("1.4.277", "1.4.312"), ("1.4.311", "1.4.312")],
            [
                (plan.spec.from_version, plan.spec.to_version)
                for plan in result.public_edges
            ],
        )
        self.assertEqual((result.compatibility,), result.local_311_edges)
        self.assertEqual(result.public_edges, result.select("public"))
        self.assertEqual(result.local_311_edges, result.select("local-311"))
        with self.assertRaisesRegex(adapter.AdapterError, "selection"):
            result.select("everything")

        allowed = {member.key for member in self.bundle.terminal.members}
        for evidence, plan in zip(result.edges, result.public_edges, strict=True):
            self.assertTrue(
                {(entry.root, entry.logical_path) for entry in plan.entries} <= allowed
            )
            self.assertEqual(allowed, set(evidence.output.mapping))
            self.assertTrue(all(raw is not None for raw in evidence.output.mapping.values()))

    def test_repeated_adaptation_has_deterministic_content_and_archive_digest(self):
        first, *_ = self.build()
        second, *_ = self.build()
        self.assertEqual(first.deterministic_digest, second.deterministic_digest)
        self.assertEqual(first.terminal_digest, second.terminal_digest)
        self.assertEqual(
            [baseline.digest for baseline in first.baselines],
            [baseline.digest for baseline in second.baselines],
        )
        self.assertEqual(
            [part.blob for plan in first.public_edges for part in plan.parts],
            [part.blob for plan in second.public_edges for part in plan.parts],
        )

    def test_provenance_baseline_and_terminal_source_drift_fail_closed(self):
        table_key = ("common", LOGICAL)
        original = self.resolved["1.4.277"][table_key]
        self.resolved["1.4.277"][table_key] = replace(original, raw=b"drift")
        with self.assertRaisesRegex(adapter.AdapterError, "baseline|provenance|size|sha"):
            self.build()
        self.resolved["1.4.277"][table_key] = original

        path = core.table_path(self.live["common"], FILE_LOGICAL)
        path.write_bytes(b"terminal drift")
        with self.assertRaisesRegex(adapter.AdapterError, "terminal|size|sha"):
            self.build()

    def test_provenance_attestation_error_is_preserved_as_adapter_failure(self):
        with mock.patch.object(
            adapter.local_contract,
            "load_bundle",
            return_value=self.bundle,
        ), mock.patch.object(
            adapter.local_contract, "validate_bundle"
        ), mock.patch.object(
            adapter.local_contract,
            "attest_bundle_baselines",
            side_effect=inventory.InventoryError("provenance source drift"),
        ):
            with self.assertRaisesRegex(adapter.AdapterError, "provenance source drift"):
                adapter.build_local_scoped_plans(
                    self.contract_dir, self.cdn, self.repo, self.live
                )

    def test_live_roots_reject_extra_keys_and_any_unsafe_ancestor(self):
        extra = {**self.live, "server": self.root / "server"}
        with self.assertRaisesRegex(adapter.AdapterError, "live root set"):
            adapter.build_local_scoped_plans(
                self.contract_dir, self.cdn, self.repo, extra
            )

        unsafe = self.live["common"].parent
        with mock.patch.object(
            adapter, "_is_reparse", side_effect=lambda path: Path(path) == unsafe
        ), mock.patch.object(
            adapter.local_contract, "load_bundle", return_value=self.bundle
        ), mock.patch.object(
            adapter.local_contract, "validate_bundle"
        ), mock.patch.object(
            adapter.local_contract, "attest_bundle_baselines"
        ), mock.patch.object(
            adapter.inventory,
            "resolve_allowlisted_members",
            side_effect=self.resolver,
        ):
            with self.assertRaisesRegex(adapter.AdapterError, "ancestor|reparse"):
                adapter.build_local_scoped_plans(
                    self.contract_dir, self.cdn, self.repo, self.live
                )

    def test_publish_api_requires_confirmation_and_honors_local_311_selection(self):
        result, *_ = self.build()
        output = self.root / "output-repo"
        active = output / "assets" / "asset-patch" / "active"
        active.mkdir(parents=True)
        manifest = active.parent / "manifest.json"
        preimage = b'{"cdn_version":"1.4.54","patches":[]}\n'
        manifest.write_bytes(preimage)
        before = snapshot_tree(output)

        with self.assertRaisesRegex(adapter.AdapterError, "PUBLISH_LOCAL"):
            adapter.publish_local_scoped_plans(
                result,
                output,
                selection="local-311",
                expected_manifest_sha256=hashlib.sha256(preimage).hexdigest(),
                confirmation="NO",
                client_profile="official",
            )
        self.assertEqual(before, snapshot_tree(output))

        published = adapter.publish_local_scoped_plans(
            result,
            output,
            selection="local-311",
            expected_manifest_sha256=hashlib.sha256(preimage).hexdigest(),
            confirmation=adapter.PUBLISH_CONFIRMATION,
            client_profile="official",
        )
        self.assertEqual(
            {part.name for part in result.compatibility.parts},
            {path.name for path in published},
        )
        patches = json.loads(manifest.read_bytes())["patches"]
        self.assertEqual(
            [("1.4.311", "1.4.312")],
            [(patch["depends_on"], patch["version"]) for patch in patches],
        )


if __name__ == "__main__":
    unittest.main()
