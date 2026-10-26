# -*- coding: utf-8 -*-
"""Release inventory resolver and attestation tests (fixture trees only)."""
from __future__ import annotations

import sys
import tempfile
import warnings
import zipfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import wf_mod_tool as core
from release_inventory_support import (
    CdnFixture,
    InventoryCase,
    LOGICAL,
    ordered,
    snapshot_tree,
)


class ReleaseInventoryTest(InventoryCase):
    def test_shared_claims_merge_when_identical_and_fail_when_divergent(self):
        claim = self.flat_claim("shared")
        first = ordered([("shared", b"same")])
        second = ordered([("other", b"ignored"), ("shared", b"same")])
        members = [
            self.member("owner-a", first, claim),
            self.member("owner-b", second, claim),
        ]
        contract = self.parse(self.payload(members))
        by_owner = {"owner-a": first, "owner-b": second}
        report = self.inventory.attest_contract(
            contract, lambda member: by_owner[member.owner]
        )
        self.assertEqual((2, 1), (report.member_count, report.unique_claim_count))
        divergent = ordered([("shared", b"different")])
        members[1] = self.member("owner-b", divergent, claim)
        contract = self.parse(self.payload(members))
        by_owner["owner-b"] = divergent
        with self.assertRaisesRegex(self.inventory.InventoryError, "divergent overlap"):
            self.inventory.attest_contract(
                contract, lambda member: by_owner[member.owner]
            )

    def test_shared_files_require_identical_content_and_cannot_mix_with_table(self):
        same = b"opaque-png"
        contract = self.parse(self.payload([
            self.file_member("owner-a", same), self.file_member("owner-b", same),
        ]))
        self.assertEqual(
            1, self.inventory.attest_contract(contract, lambda _member: same).unique_claim_count
        )
        different = b"different-png"
        contract = self.parse(self.payload([
            self.file_member("owner-a", same),
            self.file_member("owner-b", different),
        ]))
        by_owner = {"owner-a": same, "owner-b": different}
        with self.assertRaisesRegex(self.inventory.InventoryError, "divergent overlap"):
            self.inventory.attest_contract(contract, lambda item: by_owner[item.owner])
        table = ordered([("owned", b"row")])
        mixed = self.member(
            "owner-b", table, self.flat_claim("owned"),
            logical_path="character/hero/icon.png",
        )
        with self.assertRaisesRegex(self.inventory.InventoryError, "file/table"):
            self.parse(self.payload([self.file_member("owner-a", same), mixed]))

    def test_attestation_rejects_missing_projection_and_file_hash_drift(self):
        raw = ordered([("owned", b"row")])
        contract = self.parse(self.payload([
            self.member("owner-a", raw, self.flat_claim("owned"))
        ]))

        def missing(_member):
            raise FileNotFoundError("fixture missing")

        with self.assertRaisesRegex(self.inventory.InventoryError, "missing member"):
            self.inventory.attest_contract(contract, missing)
        with self.assertRaisesRegex(self.inventory.InventoryError, "non-bytes"):
            self.inventory.attest_source_contract(contract, lambda _member: None)
        changed = ordered([("owned", b"changed")])
        with self.assertRaisesRegex(self.inventory.InventoryError, "projection.*drift"):
            self.inventory.attest_contract(contract, lambda _member: changed)
        file_contract = self.parse(self.payload([self.file_member("owner-a", b"opaque")]))
        with self.assertRaisesRegex(self.inventory.InventoryError, "size drift"):
            self.inventory.attest_contract(file_contract, lambda _member: b"longer!!")
        with self.assertRaisesRegex(self.inventory.InventoryError, "sha256 drift"):
            self.inventory.attest_contract(file_contract, lambda _member: b"change")

    def test_terminal_table_ignores_sentinel_but_source_attestation_is_exact(self):
        claim = self.flat_claim("owned")
        frozen = ordered([("sentinel", b"old"), ("owned", b"same")])
        live = ordered([
            ("new-before", b"added"), ("sentinel", b"changed"),
            ("owned", b"same"), ("new-after", b"added"),
        ])
        contract = self.parse(self.payload([self.member("owner-a", frozen, claim)]))
        self.assertEqual(
            1,
            self.inventory.attest_terminal_contract(
                contract, lambda _member: live
            ).unique_claim_count,
        )
        with self.assertRaisesRegex(self.inventory.InventoryError, "source size drift"):
            self.inventory.attest_source_contract(contract, lambda _member: live)
        same_size_drift = ordered([("sentinel", b"new"), ("owned", b"same")])
        self.inventory.attest_terminal_contract(contract, lambda _member: same_size_drift)
        with self.assertRaisesRegex(self.inventory.InventoryError, "source sha256 drift"):
            self.inventory.attest_source_contract(
                contract, lambda _member: same_size_drift
            )

    def test_baseline_resolver_explicitly_rejects_server_members(self):
        with tempfile.TemporaryDirectory() as td:
            fixture = CdnFixture(Path(td))
            with self.assertRaisesRegex(self.inventory.InventoryError, "server"):
                self.inventory.resolve_allowlisted_members(
                    fixture.cdn, fixture.repo, [("server", "character.json")],
                    target_tail="1.4.0",
                )

    def test_resolver_applies_full_archives_in_numeric_sequence_order(self):
        with tempfile.TemporaryDirectory() as td:
            fixture = CdnFixture(Path(td))
            paths = {
                seq: fixture.full(f"seq-{seq}".encode(), seq=seq)
                for seq in (1, 2, 10, 11)
            }
            resolved = self.inventory.resolve_allowlisted_members(
                fixture.cdn, fixture.repo, [("common", LOGICAL)], target_tail="1.4.0"
            )
            item = resolved[("common", LOGICAL)]
            self.assertEqual(b"seq-11", item.raw)
            self.assertEqual(paths[11], item.writer_archive)

    def test_resolver_combines_full_and_diff_and_reports_true_last_writer(self):
        with tempfile.TemporaryDirectory() as td:
            fixture = CdnFixture(Path(td))
            fixture.full(b"base", seq=1)
            fixture.diff(b"edge-one", frm="1.4.0", to="1.4.1")
            final_path = fixture.diff(b"edge-two", frm="1.4.1", to="1.4.2")
            resolved = self.inventory.resolve_allowlisted_members(
                fixture.cdn, fixture.repo, [("common", LOGICAL)], target_tail="1.4.2"
            )
            item = resolved[("common", LOGICAL)]
            self.assertEqual((b"edge-two", final_path, "1.4.2"), (
                item.raw, item.writer_archive, item.tail,
            ))

    def test_baseline_attestation_requires_an_independent_baseline_contract(self):
        current = ordered([("owned", b"current")])
        historical = ordered([("owned", b"history")])
        terminal = self.parse(self.payload([
            self.member("owner-a", current, self.flat_claim("owned"))
        ]))
        baseline = self.parse(self.payload([
            self.member("owner-a", historical, self.flat_claim("owned"))
        ]))
        with tempfile.TemporaryDirectory() as td:
            fixture = CdnFixture(Path(td))
            fixture.full(historical, seq=1)
            with self.assertRaisesRegex(
                self.inventory.InventoryError, "source|projection"
            ):
                self.inventory.attest_baseline(
                    terminal, fixture.cdn, fixture.repo, target_tail="1.4.0"
                )
            report = self.inventory.attest_baseline(
                baseline, fixture.cdn, fixture.repo, target_tail="1.4.0"
            )
            self.assertEqual(1, report.member_count)

    def test_resolver_fails_closed_for_missing_or_duplicate_zip_member(self):
        with tempfile.TemporaryDirectory() as td:
            fixture = CdnFixture(Path(td))
            with self.assertRaisesRegex(self.inventory.InventoryError, "missing baseline member"):
                self.inventory.resolve_allowlisted_members(
                    fixture.cdn, fixture.repo, [("common", LOGICAL)], target_tail="1.4.0"
                )
        with tempfile.TemporaryDirectory() as td:
            fixture = CdnFixture(Path(td))
            path = fixture.cdn / "archive-common-full" / "pinball-1.4.0-1-duplicate.zip"
            member_name = fixture.member_name("common", LOGICAL)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
                    archive.writestr(member_name, b"first")
                    archive.writestr(member_name, b"second")
            with self.assertRaisesRegex(self.inventory.InventoryError, "duplicate ZIP member"):
                self.inventory.resolve_allowlisted_members(
                    fixture.cdn, fixture.repo, [("common", LOGICAL)], target_tail="1.4.0"
                )

    def test_resolver_rejects_rejected_members_graph_issues_and_auto_tail_gap(self):
        with tempfile.TemporaryDirectory() as td:
            fixture = CdnFixture(Path(td))
            fixture.full(b"base", seq=1)
            invalid_member = "../escape"
            archive_path = (
                fixture.cdn / "archive-common-full" / "pinball-1.4.0-2-invalid.zip"
            )
            with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr(invalid_member, b"bad")
            with self.assertRaisesRegex(self.inventory.InventoryError, "rejected"):
                self.inventory.resolve_allowlisted_members(
                    fixture.cdn, fixture.repo, [("common", LOGICAL)], target_tail="1.4.0"
                )

        with tempfile.TemporaryDirectory() as td:
            fixture = CdnFixture(Path(td))
            fixture.full(b"base", seq=1)
            bad_name = fixture.cdn / "archive-common-diff" / "invalid.zip"
            with zipfile.ZipFile(bad_name, "w") as archive:
                archive.writestr(fixture.member_name("common", LOGICAL), b"bad")
            with self.assertRaisesRegex(self.inventory.InventoryError, "graph issue"):
                self.inventory.resolve_allowlisted_members(
                    fixture.cdn, fixture.repo, [("common", LOGICAL)], target_tail="1.4.0"
                )

        with tempfile.TemporaryDirectory() as td:
            fixture = CdnFixture(Path(td))
            fixture.full(b"base", seq=1)
            fixture.diff(b"stranded", frm="1.4.5", to="1.4.6")
            with self.assertRaisesRegex(self.inventory.InventoryError, "unreachable tail"):
                self.inventory.resolve_allowlisted_members(
                    fixture.cdn, fixture.repo, [("common", LOGICAL)]
                )

    def test_resolver_streams_member_and_rejects_archive_symlink(self):
        with tempfile.TemporaryDirectory() as td:
            fixture = CdnFixture(Path(td))
            archive_path = fixture.full(b"streamed", seq=1)
            with mock.patch.object(
                zipfile.ZipFile, "read", side_effect=AssertionError("whole read forbidden")
            ):
                resolved = self.inventory.resolve_allowlisted_members(
                    fixture.cdn, fixture.repo, [("common", LOGICAL)], target_tail="1.4.0"
                )
            self.assertEqual(b"streamed", resolved[("common", LOGICAL)].raw)
            path_type = type(archive_path)
            original = path_type.is_symlink

            def fake_is_symlink(path):
                return path == archive_path or original(path)

            with mock.patch.object(path_type, "is_symlink", fake_is_symlink):
                with self.assertRaisesRegex(self.inventory.InventoryError, "unsafe|plan"):
                    self.inventory.resolve_allowlisted_members(
                        fixture.cdn,
                        fixture.repo,
                        [("common", LOGICAL)],
                        target_tail="1.4.0",
                    )

    def test_live_and_baseline_attestation_leave_input_trees_unchanged(self):
        claim = self.flat_claim("owned")
        raw = ordered([("owned", b"current")])
        contract = self.parse(self.payload([self.member("owner-a", raw, claim)]))
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fixture = CdnFixture(root)
            fixture.full(raw, seq=1)
            live = {
                name: root / "live" / name
                for name in ("common", "medium", "android", "server")
            }
            for path in live.values():
                path.mkdir(parents=True)
            target = core.table_path(live["common"], LOGICAL)
            target.parent.mkdir(parents=True)
            target.write_bytes(raw)
            before = snapshot_tree(root)
            live_report = self.inventory.attest_live_roots(contract, live)
            baseline_report = self.inventory.attest_baseline(
                contract, fixture.cdn, fixture.repo, target_tail="1.4.0"
            )
            self.assertEqual((1, 1), (live_report.member_count, baseline_report.member_count))
            self.assertEqual(before, snapshot_tree(root))
