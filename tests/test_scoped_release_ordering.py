# -*- coding: utf-8 -*-
"""Claim-order regressions for scoped full-table rebasing."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from release_inventory_support import InventoryCase, LOGICAL, ordered

import wf_character_pack as character_pack
import wf_mod_tool as core
import wf_local_release_receipt as receipt
import wf_scoped_release as scoped


class ScopedReleaseOrderingTest(InventoryCase):
    @staticmethod
    def spec() -> scoped.EdgeSpec:
        return scoped.EdgeSpec(
            from_version="1.4.311",
            to_version="1.4.312",
            tag="order0806",
            patch_id="ordering-regression",
            name="ordering regression",
            description="preserve terminal claim order on a historical baseline",
            created_at="2026-08-06",
        )

    @staticmethod
    def payload(plan: scoped.EdgePlan) -> bytes:
        return next(entry.payload for entry in plan.entries if entry.logical_path == LOGICAL)

    def test_flat_claims_follow_terminal_order_when_some_keys_already_exist(self):
        terminal = ordered([
            ("terminal-unclaimed", b"never-copy"),
            ("boss2", b"terminal-2"),
            ("boss3", b"terminal-3"),
            ("boss4", b"terminal-4"),
        ])
        baseline = ordered([
            ("sentinel-head", b"base-head"),
            ("boss3", b"old-3"),
            ("sentinel-tail", b"base-tail"),
            ("boss4", b"old-4"),
        ])
        claim = character_pack.TableClaim(
            "common", LOGICAL, "flat", ("boss2", "boss3", "boss4")
        )
        contract = self.parse(self.payload_contract([
            self.member("abyss-tower", terminal, claim)
        ]))

        plan = scoped.build_edge_plan(
            contract,
            {("common", LOGICAL): baseline},
            lambda _member: terminal,
            self.spec(),
        )
        keys, rows = core._strict_orderedmap_rows(
            self.payload(plan), label="flat-output", compressed_rows=True
        )
        self.assertEqual(
            ["sentinel-head", "boss2", "boss3", "boss4", "sentinel-tail"],
            keys,
        )
        self.assertEqual(
            [
                b"base-head",
                b"terminal-2",
                b"terminal-3",
                b"terminal-4",
                b"base-tail",
            ],
            rows,
        )

    def test_disjoint_nested_owners_share_outer_and_keep_terminal_inner_order(self):
        terminal_inner = ordered([
            ("terminal-unclaimed", b"never-copy"),
            ("a1", b"terminal-a1"),
            ("b1", b"terminal-b1"),
            ("a2", b"terminal-a2"),
            ("b2", b"terminal-b2"),
        ])
        baseline_inner = ordered([
            ("sentinel-head", b"base-head"),
            ("b1", b"old-b1"),
            ("sentinel-tail", b"base-tail"),
            ("a2", b"old-a2"),
        ])
        terminal = ordered([("shared", terminal_inner)], raw_outer=True)
        baseline = ordered([("shared", baseline_inner)], raw_outer=True)
        claim_a = character_pack.TableClaim(
            "common",
            LOGICAL,
            "action_nested",
            ("shared",),
            (("shared", ("a1", "a2")),),
        )
        claim_b = character_pack.TableClaim(
            "common",
            LOGICAL,
            "action_nested",
            ("shared",),
            (("shared", ("b1", "b2")),),
        )
        contract = self.parse(self.payload_contract([
            self.member("owner-a", terminal, claim_a),
            self.member("owner-b", terminal, claim_b),
        ]))

        plan = scoped.build_edge_plan(
            contract,
            {("common", LOGICAL): baseline},
            lambda _member: terminal,
            self.spec(),
        )
        outer_keys, outer_rows = core._strict_orderedmap_rows(
            self.payload(plan), label="nested-outer", compressed_rows=False
        )
        self.assertEqual(["shared"], outer_keys)
        inner_keys, inner_rows = core._strict_orderedmap_rows(
            outer_rows[0], label="nested-inner", compressed_rows=True
        )
        self.assertEqual(
            ["sentinel-head", "a1", "b1", "a2", "b2", "sentinel-tail"],
            inner_keys,
        )
        self.assertEqual(
            [
                b"base-head",
                b"terminal-a1",
                b"terminal-b1",
                b"terminal-a2",
                b"terminal-b2",
                b"base-tail",
            ],
            inner_rows,
        )

    def test_nested_claimed_outers_follow_terminal_order_as_one_block(self):
        terminal_a = ordered([("1", b"terminal-a")])
        terminal_b = ordered([("1", b"terminal-b")])
        terminal = ordered(
            [
                ("terminal-unclaimed", b"never-copy"),
                ("outer-a", terminal_a),
                ("outer-b", terminal_b),
            ],
            raw_outer=True,
        )
        baseline = ordered(
            [
                ("sentinel-head", b"base-head"),
                ("outer-b", ordered([("1", b"old-b")])),
                ("sentinel-tail", b"base-tail"),
                ("outer-a", ordered([("1", b"old-a")])),
            ],
            raw_outer=True,
        )
        claim_a = character_pack.TableClaim(
            "common", LOGICAL, "action_nested", ("outer-a",), (("outer-a", ("1",)),)
        )
        claim_b = character_pack.TableClaim(
            "common", LOGICAL, "action_nested", ("outer-b",), (("outer-b", ("1",)),)
        )
        contract = self.parse(self.payload_contract([
            self.member("owner-a", terminal, claim_a),
            self.member("owner-b", terminal, claim_b),
        ]))

        plan = scoped.build_edge_plan(
            contract,
            {("common", LOGICAL): baseline},
            lambda _member: terminal,
            self.spec(),
        )
        keys, rows = core._strict_orderedmap_rows(
            self.payload(plan), label="nested-outer-order", compressed_rows=False
        )
        self.assertEqual(
            ["sentinel-head", "outer-a", "outer-b", "sentinel-tail"], keys
        )
        self.assertEqual(b"base-head", rows[0])
        self.assertEqual(b"base-tail", rows[-1])

    def test_json_claims_follow_terminal_order_and_keep_baseline_unclaimed_items(self):
        terminal = b'{"terminal-unclaimed":"never-copy","owned-a":{"v":1},"owned-b":2}'
        baseline = b'{"sentinel-head":"base-head","owned-b":0,"sentinel-tail":{"keep":true},"owned-a":{"v":0}}'
        claim = character_pack.TableClaim(
            "common", LOGICAL, "json_object", ("owned-a", "owned-b")
        )
        contract = self.parse(self.payload_contract([
            self.member("json-owner", terminal, claim)
        ]))

        plan = scoped.build_edge_plan(
            contract,
            {("common", LOGICAL): baseline},
            lambda _member: terminal,
            self.spec(),
        )
        payload = self.payload(plan)
        self.assertEqual(
            b'{"sentinel-head":"base-head","owned-a":{"v":1},'
            b'"owned-b":2,"sentinel-tail":{"keep":true}}',
            payload,
        )
        self.assertEqual(
            ["sentinel-head", "owned-a", "owned-b", "sentinel-tail"],
            list(json.loads(payload)),
        )

    @staticmethod
    def payload_contract(members: list[dict[str, object]]) -> dict[str, object]:
        return {
            "schema": "wf-release-inventory/v1",
            "contract_id": "ordering-contract",
            "members": members,
        }


class ReceiptDerivationAgreementTest(InventoryCase):
    """The receipt must re-derive exactly what the publisher writes.

    The receipt is the only build-time cross-check on the published payload,
    so a derivation that disagrees with the publisher is not a conservative
    failure: it rejects correct releases, and if the two ever drifted the other
    way it would sign off on a payload nobody re-derived.
    """

    spec = staticmethod(ScopedReleaseOrderingTest.spec)
    payload = staticmethod(ScopedReleaseOrderingTest.payload)
    payload_contract = staticmethod(ScopedReleaseOrderingTest.payload_contract)

    def derive(self, contract, terminal: bytes, baseline: bytes) -> tuple[bytes, bytes]:
        plan = scoped.build_edge_plan(
            contract,
            {("common", LOGICAL): baseline},
            lambda _member: terminal,
            self.spec(),
        )
        members = receipt._members_by_path(contract)[("common", LOGICAL)]
        return self.payload(plan), receipt._expected_output(terminal, baseline, members)

    def test_scattered_claims_derive_identically_for_publisher_and_receipt(self):
        terminal = ordered([
            ("terminal-unclaimed", b"never-copy"),
            ("boss2", b"terminal-2"),
            ("boss3", b"terminal-3"),
            ("boss4", b"terminal-4"),
        ])
        baseline = ordered([
            ("sentinel-head", b"base-head"),
            ("boss3", b"old-3"),
            ("sentinel-tail", b"base-tail"),
            ("boss4", b"old-4"),
        ])
        claim = character_pack.TableClaim(
            "common", LOGICAL, "flat", ("boss2", "boss3", "boss4")
        )
        contract = self.parse(self.payload_contract([
            self.member("abyss-tower", terminal, claim)
        ]))

        published, expected = self.derive(contract, terminal, baseline)

        self.assertEqual(published, expected)

    def test_three_owners_on_one_table_derive_identically(self):
        terminal = ordered([
            ("unclaimed-head", b"never-copy"),
            ("c1", b"terminal-c1"),
            ("a1", b"terminal-a1"),
            ("b1", b"terminal-b1"),
            ("unclaimed-tail", b"also-never"),
        ])
        baseline = ordered([
            ("sentinel-head", b"base-head"),
            ("b1", b"old-b1"),
            ("sentinel-mid", b"base-mid"),
            ("a1", b"old-a1"),
            ("sentinel-tail", b"base-tail"),
        ])
        contract = self.parse(self.payload_contract([
            self.member(
                owner, terminal,
                character_pack.TableClaim("common", LOGICAL, "flat", (key,)),
            )
            for owner, key in (("ginovi", "a1"), ("lafu", "b1"), ("dragons", "c1"))
        ]))

        published, expected = self.derive(contract, terminal, baseline)

        self.assertEqual(published, expected)

    def test_identical_baseline_and_terminal_agree_on_both_sides(self):
        # Grouping claimed rows at the first claimed position is deliberate, so
        # rebasing a table onto itself is not a byte-level no-op when the claims
        # were scattered.  Both derivations must land on the same regrouping.
        terminal = ordered([
            ("head", b"h"),
            ("owned-a", b"a"),
            ("middle", b"m"),
            ("owned-b", b"b"),
            ("tail", b"t"),
        ])
        contract = self.parse(self.payload_contract([
            self.member(
                "owner", terminal,
                character_pack.TableClaim(
                    "common", LOGICAL, "flat", ("owned-a", "owned-b")
                ),
            )
        ]))

        published, expected = self.derive(contract, terminal, terminal)

        self.assertEqual(published, expected)
        keys, rows = core._strict_orderedmap_rows(
            published, label="regrouped", compressed_rows=True
        )
        self.assertEqual(["head", "owned-a", "owned-b", "middle", "tail"], keys)
        self.assertEqual([b"h", b"a", b"b", b"m", b"t"], rows)

    def test_receipt_refuses_a_table_without_a_baseline(self):
        terminal = ordered([("head", b"h"), ("owned", b"o")])
        contract = self.parse(self.payload_contract([
            self.member(
                "owner", terminal,
                character_pack.TableClaim("common", LOGICAL, "flat", ("owned",)),
            )
        ]))
        members = receipt._members_by_path(contract)[("common", LOGICAL)]

        with self.assertRaisesRegex(receipt.ReceiptError, "baseline is absent"):
            receipt._expected_output(terminal, None, members)


if __name__ == "__main__":
    unittest.main()
