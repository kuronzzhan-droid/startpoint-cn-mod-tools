# -*- coding: utf-8 -*-
"""Strict offline receipt coverage for the frozen local-live release."""
from __future__ import annotations

import hashlib
import io
import json
import stat
import sys
import unittest
import zipfile
from dataclasses import replace
from pathlib import Path


MOD_TOOLS = Path(__file__).resolve().parent.parent
CONTRACTS = MOD_TOOLS / "release-contracts"
sys.path.insert(0, str(MOD_TOOLS))

import wf_local_release_receipt as receipt  # noqa: E402
import wf_local_server_contract as server_contract  # noqa: E402
import wf_character_pack as character_pack  # noqa: E402
import wf_mod_tool as core  # noqa: E402
from wf_release_inventory_contract import (  # noqa: E402
    InventoryContract,
    InventoryMember,
    projection_sha256,
)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def manifest_blob(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=1) + "\n").encode("utf-8")


def zip_blob(
    member_payloads: list[tuple[str, bytes]], *, compresslevel: int = 9
) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for name, payload in member_payloads:
            info = zipfile.ZipInfo(name, (2026, 8, 6, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(
                info, payload,
                compress_type=zipfile.ZIP_DEFLATED, compresslevel=compresslevel,
            )
    return output.getvalue()


def reseal(value: dict[str, object]) -> bytes:
    value.pop("receipt_sha256", None)
    value["receipt_sha256"] = sha(receipt.canonical_receipt(value))
    return receipt.canonical_receipt(value)


class ReceiptFixture:
    def __init__(self, compresslevel: int = 9):
        self.compresslevel = compresslevel
        self.old_a, self.old_b = b"old-a", b"old-b"
        self.new_a, self.new_b = b"new-a", b"new-b"
        self.key_a = ("common", "fixture/a.bin")
        self.key_b = ("common", "fixture/b.bin")
        self.key_table = ("common", "fixture/table.orderedmap")
        self.table_claim = character_pack.TableClaim(
            "common", self.key_table[1], "flat", ("owned",)
        )

        def table(sentinel: bytes, owned: bytes) -> bytes:
            return core.build_orderedmap(core.OrderedMap(
                "fixture", ["sentinel", "owned"], [sentinel, owned], Path("<fixture>"),
            ))

        self.make_table = table
        self.table_terminal = table(b"terminal-wip", b"terminal-owned")
        self.table_277 = table(b"baseline-277", b"old-owned")
        self.table_311 = table(b"baseline-311", b"terminal-owned")
        self.table_output_277 = table(b"baseline-277", b"terminal-owned")
        terminal = InventoryContract(
            "terminal-fixture",
            (
                InventoryMember("owner-a", "file", *self.key_a, len(self.new_a), sha(self.new_a)),
                InventoryMember("owner-b", "file", *self.key_b, len(self.new_b), sha(self.new_b)),
                InventoryMember(
                    "owner-table", "table", *self.key_table,
                    claim=self.table_claim,
                    projection_sha256=projection_sha256(
                        self.table_terminal, self.table_claim
                    ),
                    source_size=len(self.table_terminal),
                    source_sha256=sha(self.table_terminal),
                ),
            ),
        )
        baselines = {
            "1.4.277": InventoryContract(
                "baseline-277",
                (
                    InventoryMember("owner-a", "file", *self.key_a, len(self.old_a), sha(self.old_a)),
                    InventoryMember(
                        "owner-table", "table", *self.key_table,
                        claim=self.table_claim,
                        projection_sha256=projection_sha256(
                            self.table_277, self.table_claim
                        ),
                        source_size=len(self.table_277),
                        source_sha256=sha(self.table_277),
                    ),
                ),
            ),
            "1.4.311": InventoryContract(
                "baseline-311",
                (
                    InventoryMember("owner-a", "file", *self.key_a, len(self.new_a), sha(self.new_a)),
                    InventoryMember("owner-b", "file", *self.key_b, len(self.old_b), sha(self.old_b)),
                    InventoryMember(
                        "owner-table", "table", *self.key_table,
                        claim=self.table_claim,
                        projection_sha256=projection_sha256(
                            self.table_311, self.table_claim
                        ),
                        source_size=len(self.table_311),
                        source_sha256=sha(self.table_311),
                    ),
                ),
            ),
        }
        projected = {"hero": {"name": "terminal"}}
        selector = server_contract.ServerSelector("object_keys", (), ("hero",))
        server_member = server_contract.ServerMember(
            "server-owner",
            "server.json",
            selector,
            sha(canonical({"hero": {"name": "preimage"}})),
            sha(canonical(projected)),
            {"hero": {"name": "preimage"}},
            projected,
        )
        migration = server_contract.MigrationContract(
            "migration-fixture", terminal.contract_id, (), (server_member,)
        )
        bindings = (
            receipt.ContractBinding("terminal", "contracts/terminal.json", terminal.contract_id, b"terminal"),
            receipt.ContractBinding("baseline_1_4_277", "contracts/277.json", baselines["1.4.277"].contract_id, b"277"),
            receipt.ContractBinding("baseline_1_4_311", "contracts/311.json", baselines["1.4.311"].contract_id, b"311"),
            receipt.ContractBinding("provenance", "contracts/provenance.json", "provenance-fixture", b"provenance"),
            receipt.ContractBinding("migration", "contracts/migration.json", migration.contract_id, b"migration"),
        )
        descriptors = {
            "1.4.277": {
                self.key_a: receipt.BaselineDescriptor(True, len(self.old_a), sha(self.old_a), "archive/277.zip", receipt.archive_member_name(*self.key_a)),
                self.key_b: receipt.BaselineDescriptor(False, None, None, None, None),
                self.key_table: receipt.BaselineDescriptor(
                    True, len(self.table_277), sha(self.table_277),
                    "archive/277.zip", receipt.archive_member_name(*self.key_table),
                    receipt._unclaimed_sha(
                        self.table_277, (terminal.members[2],)
                    ),
                ),
            },
            "1.4.311": {
                self.key_a: receipt.BaselineDescriptor(True, len(self.new_a), sha(self.new_a), "archive/311.zip", receipt.archive_member_name(*self.key_a)),
                self.key_b: receipt.BaselineDescriptor(True, len(self.old_b), sha(self.old_b), "archive/311.zip", receipt.archive_member_name(*self.key_b)),
                self.key_table: receipt.BaselineDescriptor(
                    True, len(self.table_311), sha(self.table_311),
                    "archive/311.zip", receipt.archive_member_name(*self.key_table),
                    receipt._unclaimed_sha(
                        self.table_311, (terminal.members[2],)
                    ),
                ),
            },
        }
        self.context = receipt.ReleaseContext(terminal, baselines, descriptors, migration, bindings)
        self.preimage = manifest_blob({"cdn_version": "1.4.54", "patches": []})
        self.policy = receipt.ReleasePolicy(
            release_id="local-live-1-4-312",
            terminal_contract_id=terminal.contract_id,
            baseline_versions=("1.4.277", "1.4.311"),
            terminal_member_count=3,
            unique_path_count=3,
            server_member_count=1,
            client_migration_count=0,
            contract_ids={binding.role: binding.contract_id for binding in bindings},
            manifest_preimage_sha256=sha(self.preimage),
            manifest_cdn_version="1.4.54",
            manifest_preimage_patch_count=0,
        )
        name277 = "pinball-1.4.277-1.4.312-1-fixture277.zip"
        name311 = "pinball-1.4.311-1.4.312-1-fixture311.zip"
        blob277 = zip_blob([
            (receipt.archive_member_name(*self.key_a), self.new_a),
            (receipt.archive_member_name(*self.key_b), self.new_b),
            (receipt.archive_member_name(*self.key_table), self.table_output_277),
        ], compresslevel=self.compresslevel)
        blob311 = zip_blob(
            [(receipt.archive_member_name(*self.key_b), self.new_b)],
            compresslevel=self.compresslevel,
        )
        self.edges = (
            receipt.EdgeEvidence(
                "1.4.277", "1.4.312", "fixture-277", "fixture277",
                {self.key_a: self.old_a, self.key_b: None, self.key_table: self.table_277},
                {
                    self.key_a: self.new_a, self.key_b: self.new_b,
                    self.key_table: self.table_output_277,
                },
                (receipt.ArchiveEvidence("common", name277, blob277),),
            ),
            receipt.EdgeEvidence(
                "1.4.311", "1.4.312", "fixture-311", "fixture311",
                {
                    self.key_a: self.new_a, self.key_b: self.old_b,
                    self.key_table: self.table_311,
                },
                {
                    self.key_a: self.new_a, self.key_b: self.new_b,
                    self.key_table: self.table_311,
                },
                (receipt.ArchiveEvidence("common", name311, blob311),),
            ),
        )
        patches = []
        for edge in self.edges:
            patches.append({
                "id": edge.patch_id,
                "type": "patch",
                "name": edge.patch_id,
                "description": "fixture edge",
                "version": edge.to_version,
                "depends_on": edge.from_version,
                "enabled": True,
                "chain": [part.name for part in edge.archives],
                "archive_integrity": [
                    {
                        "name": part.name,
                        "size": len(part.blob),
                        "sha256": sha(part.blob),
                    }
                    for part in edge.archives
                ],
                "created_at": "2026-08-06",
            })
        self.manifest = manifest_blob({"cdn_version": "1.4.54", "patches": patches})
        self.server_files = {"server.json": canonical(projected)}
        self.terminal_sources = {
            self.key_a: self.new_a,
            self.key_b: self.new_b,
            self.key_table: self.table_terminal,
        }

    def build(self) -> bytes:
        return receipt.build_receipt(
            self.context,
            self.policy,
            terminal_sources=self.terminal_sources,
            edges=self.edges,
            manifest_preimage=self.preimage,
            manifest_output=self.manifest,
            server_files=self.server_files,
        )

    def archive_blobs(self) -> dict[str, bytes]:
        return {
            f"active/{part.name}": part.blob
            for edge in self.edges for part in edge.archives
        }


class LocalReleaseReceiptTest(unittest.TestCase):
    def forge_table_payload(
        self,
        fx: ReceiptFixture,
        value: dict[str, object],
        replacement: bytes,
    ) -> tuple[bytes, dict[str, bytes], bytes]:
        edge = value["edges"][0]
        archive = edge["archives"][0]
        archive_path = archive["path"]
        original_blob = fx.archive_blobs()[archive_path]
        member_name = receipt.archive_member_name(*fx.key_table)
        with zipfile.ZipFile(io.BytesIO(original_blob)) as zipped:
            payloads = [
                (
                    info.filename,
                    replacement if info.filename == member_name else zipped.read(info),
                )
                for info in zipped.infolist()
            ]
        forged_blob = zip_blob(payloads)
        archive["size"] = len(forged_blob)
        archive["sha256"] = sha(forged_blob)
        member = next(
            item for item in archive["members"] if item["name"] == member_name
        )
        member["size"] = len(replacement)
        member["sha256"] = sha(replacement)
        path = next(
            item for item in edge["paths"]
            if item["logical_path"] == fx.key_table[1]
        )
        path["output_size"] = len(replacement)
        path["output_sha256"] = sha(replacement)
        unclaimed = receipt._unclaimed_sha(
            replacement, (fx.context.terminal.members[2],)
        )
        path["unclaimed_before_sha256"] = unclaimed
        path["unclaimed_after_sha256"] = unclaimed

        manifest = json.loads(fx.manifest)
        integrity = manifest["patches"][0]["archive_integrity"][0]
        integrity["size"] = len(forged_blob)
        integrity["sha256"] = sha(forged_blob)
        manifest_raw = manifest_blob(manifest)
        value["manifest"]["output_sha256"] = sha(manifest_raw)
        value["manifest"]["appended_patches"] = manifest["patches"]
        archives = {**fx.archive_blobs(), archive_path: forged_blob}
        return reseal(value), archives, manifest_raw

    def test_writer_and_offline_verifier_cover_both_edges_and_noop_omission(self):
        fx = ReceiptFixture()
        raw = fx.build()
        value = receipt.parse_receipt(raw)
        self.assertTrue(raw.endswith(b"\n"))
        self.assertEqual(["1.4.277", "1.4.311"], [edge["from_version"] for edge in value["edges"]])
        edge311 = value["edges"][1]
        path_a = next(item for item in edge311["paths"] if item["logical_path"] == "fixture/a.bin")
        self.assertEqual("omitted_equal", path_a["disposition"])
        self.assertIsNone(path_a["archive"])
        edge277 = value["edges"][0]
        table277 = next(
            item for item in edge277["paths"]
            if item["logical_path"] == fx.key_table[1]
        )
        self.assertEqual("included", table277["disposition"])
        self.assertEqual(
            projection_sha256(fx.table_terminal, fx.table_claim),
            table277["claims"][0]["projection_sha256"],
        )
        self.assertEqual(
            table277["unclaimed_before_sha256"],
            table277["unclaimed_after_sha256"],
        )
        table311 = next(
            item for item in edge311["paths"]
            if item["logical_path"] == fx.key_table[1]
        )
        self.assertEqual("omitted_equal", table311["disposition"])
        report = receipt.verify_receipt(
            fx.context,
            fx.policy,
            raw,
            archive_blobs=fx.archive_blobs(),
            manifest_raw=fx.manifest,
            server_files=fx.server_files,
        )
        self.assertEqual((2, 3, 3), (report.edge_count, report.path_count_per_edge, report.claim_count_per_edge))

    def test_verifier_does_not_depend_on_the_local_deflate_implementation(self):
        # The verifier used to re-deflate every member and demand the bytes
        # come back identical, which made a receipt verifiable only on a
        # machine whose zlib matched the publisher's -- green locally on
        # Python 3.14, red on CI's 3.11.  Archives compressed at a different
        # level are byte-different but structurally identical, and must verify.
        fx = ReceiptFixture(compresslevel=1)
        raw = receipt.build_receipt(
            fx.context, fx.policy,
            terminal_sources=fx.terminal_sources, edges=fx.edges,
            manifest_preimage=fx.preimage, manifest_output=fx.manifest,
            server_files=fx.server_files,
        )

        report = receipt.verify_receipt(
            fx.context, fx.policy, raw,
            archive_blobs=fx.archive_blobs(), manifest_raw=fx.manifest,
            server_files=fx.server_files,
        )

        self.assertEqual((2, 3, 3), (
            report.edge_count,
            report.path_count_per_edge,
            report.claim_count_per_edge,
        ))
        # Asserting that two compression levels produce different bytes would
        # itself be zlib-dependent -- small payloads come out identical at every
        # level on some builds, which is exactly how this test first failed on
        # CI.  Assert the property directly instead: the verifier compresses
        # nothing, so it has no opinion to disagree with.
        source = (MOD_TOOLS / "wf_local_release_verify.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("compresslevel", source)
        self.assertNotIn("writestr", source)

    def test_verifier_rejects_bytes_hidden_outside_the_declared_members(self):
        fx = ReceiptFixture()
        raw = receipt.build_receipt(
            fx.context, fx.policy,
            terminal_sources=fx.terminal_sources, edges=fx.edges,
            manifest_preimage=fx.preimage, manifest_output=fx.manifest,
            server_files=fx.server_files,
        )
        value = receipt.parse_receipt(raw)
        blobs = fx.archive_blobs()
        target = next(iter(blobs))
        padded = b"\x00" * 8 + blobs[target]
        record = next(
            archive
            for edge in value["edges"] for archive in edge["archives"]
            if archive["path"] == target
        )
        record["size"] = len(padded)
        record["sha256"] = sha(padded)

        with self.assertRaisesRegex(
            receipt.ReceiptError, "gap or overlap|trailing, hidden"
        ):
            receipt.verify_receipt(
                fx.context, fx.policy, reseal(value),
                archive_blobs={**blobs, target: padded},
                manifest_raw=fx.manifest, server_files=fx.server_files,
            )

    def test_noop_omission_uses_content_claim_not_baseline_owner_label(self):
        fx = ReceiptFixture()
        baseline = fx.context.baselines["1.4.311"]
        renamed = InventoryContract(
            baseline.contract_id,
            tuple(
                replace(member, owner="baseline-1-4-311")
                if member.key in {fx.key_a, fx.key_table}
                else member
                for member in baseline.members
            ),
        )
        context = replace(
            fx.context,
            baselines={**fx.context.baselines, "1.4.311": renamed},
        )

        raw = receipt.build_receipt(
            context,
            fx.policy,
            terminal_sources=fx.terminal_sources,
            edges=fx.edges,
            manifest_preimage=fx.preimage,
            manifest_output=fx.manifest,
            server_files=fx.server_files,
        )
        report = receipt.verify_receipt(
            context,
            fx.policy,
            raw,
            archive_blobs=fx.archive_blobs(),
            manifest_raw=fx.manifest,
            server_files=fx.server_files,
        )
        self.assertEqual((2, 3, 3), (
            report.edge_count,
            report.path_count_per_edge,
            report.claim_count_per_edge,
        ))

    def test_writer_rejects_table_output_that_overwrites_unclaimed_rows(self):
        fx = ReceiptFixture()
        bad_edge = replace(
            fx.edges[0],
            output={**fx.edges[0].output, fx.key_table: fx.table_terminal},
        )
        with self.assertRaisesRegex(receipt.ReceiptError, "unclaimed|output"):
            receipt.build_receipt(
                fx.context,
                fx.policy,
                terminal_sources=fx.terminal_sources,
                edges=(bad_edge, fx.edges[1]),
                manifest_preimage=fx.preimage,
                manifest_output=fx.manifest,
                server_files=fx.server_files,
            )

    def test_verifier_rejects_present_baseline_unclaimed_row_forgery(self):
        fx = ReceiptFixture()
        value = receipt.parse_receipt(fx.build())
        forged_table = fx.make_table(b"forged-unclaimed", b"terminal-owned")
        forged_receipt, archives, manifest = self.forge_table_payload(
            fx, value, forged_table
        )
        with self.assertRaisesRegex(receipt.ReceiptError, "baseline unclaimed"):
            receipt.verify_receipt(
                fx.context, fx.policy, forged_receipt,
                archive_blobs=archives, manifest_raw=manifest,
                server_files=fx.server_files,
            )

    def test_verifier_rejects_absent_baseline_nonterminal_whole_source(self):
        fx = ReceiptFixture()
        value = receipt.parse_receipt(fx.build())
        table_path = next(
            item for item in value["edges"][0]["paths"]
            if item["logical_path"] == fx.key_table[1]
        )
        table_path["baseline"] = None
        descriptors = {
            version: dict(items)
            for version, items in fx.context.baseline_descriptors.items()
        }
        descriptors["1.4.277"][fx.key_table] = receipt.BaselineDescriptor(
            False, None, None, None, None, None
        )
        baselines = dict(fx.context.baselines)
        baselines["1.4.277"] = InventoryContract(
            baselines["1.4.277"].contract_id,
            tuple(
                member for member in baselines["1.4.277"].members
                if member.key != fx.key_table
            ),
        )
        context = replace(
            fx.context,
            baselines=baselines,
            baseline_descriptors=descriptors,
        )
        forged_table = fx.make_table(b"forged-unclaimed", b"terminal-owned")
        forged_receipt, archives, manifest = self.forge_table_payload(
            fx, value, forged_table
        )
        with self.assertRaisesRegex(
            receipt.ReceiptError, "absent baseline.*terminal source"
        ):
            receipt.verify_receipt(
                context, fx.policy, forged_receipt,
                archive_blobs=archives, manifest_raw=manifest,
                server_files=fx.server_files,
            )

    def test_manifest_baseline_is_fixed_by_policy_for_writer_and_verifier(self):
        fx = ReceiptFixture()
        forged_old = {
            "id": "forged-old", "version": "1.4.277",
            "depends_on": "1.4.1", "enabled": False,
        }
        original_patches = json.loads(fx.manifest)["patches"]
        forged_preimage = manifest_blob({
            "cdn_version": "1.4.54", "patches": [forged_old]
        })
        forged_manifest = manifest_blob({
            "cdn_version": "1.4.54",
            "patches": [forged_old, *original_patches],
        })
        with self.assertRaisesRegex(receipt.ReceiptError, "manifest policy"):
            receipt.build_receipt(
                fx.context, fx.policy,
                terminal_sources=fx.terminal_sources, edges=fx.edges,
                manifest_preimage=forged_preimage,
                manifest_output=forged_manifest,
                server_files=fx.server_files,
            )

        value = receipt.parse_receipt(fx.build())
        value["manifest"]["preimage_sha256"] = sha(forged_preimage)
        value["manifest"]["preimage_patch_count"] = 1
        value["manifest"]["output_sha256"] = sha(forged_manifest)
        with self.assertRaisesRegex(receipt.ReceiptError, "manifest policy"):
            receipt.verify_receipt(
                fx.context, fx.policy, reseal(value),
                archive_blobs=fx.archive_blobs(),
                manifest_raw=forged_manifest, server_files=fx.server_files,
            )

    def test_archive_integrity_is_exactly_bound_for_writer_and_verifier(self):
        fx = ReceiptFixture()
        manifest = json.loads(fx.manifest)
        manifest["patches"][0]["archive_integrity"][0]["sha256"] = "0" * 64
        forged_manifest = manifest_blob(manifest)
        with self.assertRaisesRegex(receipt.ReceiptError, "archive_integrity"):
            receipt.build_receipt(
                fx.context, fx.policy,
                terminal_sources=fx.terminal_sources, edges=fx.edges,
                manifest_preimage=fx.preimage,
                manifest_output=forged_manifest,
                server_files=fx.server_files,
            )

        value = receipt.parse_receipt(fx.build())
        value["manifest"]["output_sha256"] = sha(forged_manifest)
        value["manifest"]["appended_patches"] = manifest["patches"]
        with self.assertRaisesRegex(receipt.ReceiptError, "archive_integrity"):
            receipt.verify_receipt(
                fx.context, fx.policy, reseal(value),
                archive_blobs=fx.archive_blobs(),
                manifest_raw=forged_manifest, server_files=fx.server_files,
            )

    def test_strict_json_rejects_duplicate_nan_absolute_and_runtime_paths(self):
        bad = (
            b'{"schema":"wf-local-release-receipt/v1",'
            b'"schema":"wf-local-release-receipt/v1"}'
        )
        with self.assertRaisesRegex(receipt.ReceiptError, "duplicate"):
            receipt.parse_receipt(bad)
        with self.assertRaisesRegex(receipt.ReceiptError, "non-JSON"):
            receipt.parse_receipt(b'{"value":NaN}')
        with self.assertRaisesRegex(receipt.ReceiptError, "absolute|runtime"):
            receipt.parse_receipt(b'{"path":"C:\\\\Temp\\\\leak"}')
        with self.assertRaisesRegex(receipt.ReceiptError, "runtime"):
            receipt.parse_receipt(b'{"mtime_ns":123}')

    def test_verifier_rejects_zip_manifest_and_path_coverage_tamper(self):
        fx = ReceiptFixture()
        raw = fx.build()
        archives = fx.archive_blobs()
        first = next(iter(archives))
        broken = dict(archives)
        broken[first] += b"tamper"
        with self.assertRaisesRegex(receipt.ReceiptError, "archive.*sha256|size"):
            receipt.verify_receipt(
                fx.context, fx.policy, raw, archive_blobs=broken,
                manifest_raw=fx.manifest, server_files=fx.server_files,
            )
        value = receipt.parse_receipt(raw)
        archive_record = value["edges"][0]["archives"][0]
        junk = archives[first] + b"JUNK"
        archive_record["size"] = len(junk)
        archive_record["sha256"] = sha(junk)
        value.pop("receipt_sha256")
        value["receipt_sha256"] = sha(receipt.canonical_receipt(value))
        with self.assertRaisesRegex(
            receipt.ReceiptError, "does not end with its central directory"
        ):
            receipt.verify_receipt(
                fx.context, fx.policy, receipt.canonical_receipt(value),
                archive_blobs={**archives, first: junk},
                manifest_raw=fx.manifest, server_files=fx.server_files,
            )
        with self.assertRaisesRegex(receipt.ReceiptError, "manifest"):
            receipt.verify_receipt(
                fx.context, fx.policy, raw, archive_blobs=archives,
                manifest_raw=fx.manifest + b" ", server_files=fx.server_files,
            )
        value = receipt.parse_receipt(raw)
        value["manifest"]["preimage_sha256"] = "0" * 64
        value.pop("receipt_sha256")
        value["receipt_sha256"] = sha(receipt.canonical_receipt(value))
        with self.assertRaisesRegex(receipt.ReceiptError, "manifest policy"):
            receipt.verify_receipt(
                fx.context, fx.policy, receipt.canonical_receipt(value),
                archive_blobs=archives, manifest_raw=fx.manifest,
                server_files=fx.server_files,
            )
        value = receipt.parse_receipt(raw)
        value["edges"][0]["paths"].pop()
        value.pop("receipt_sha256")
        value["receipt_sha256"] = sha(receipt.canonical_receipt(value))
        missing = receipt.canonical_receipt(value)
        with self.assertRaisesRegex(receipt.ReceiptError, "path coverage"):
            receipt.verify_receipt(
                fx.context, fx.policy, missing, archive_blobs=archives,
                manifest_raw=fx.manifest, server_files=fx.server_files,
            )

    def test_local_context_binds_exact_task3a_contracts(self):
        context = receipt.load_local_context(CONTRACTS)
        self.assertEqual(receipt.LOCAL_POLICY.terminal_contract_id, context.terminal.contract_id)
        self.assertEqual(257, len(context.terminal.members))
        self.assertEqual(233, len({member.key for member in context.terminal.members}))
        self.assertEqual(5, len(context.contract_bindings))


if __name__ == "__main__":
    unittest.main()
