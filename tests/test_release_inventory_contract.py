# -*- coding: utf-8 -*-
"""Strict release inventory schema and orderedmap projection tests."""
from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import wf_character_pack as character_pack
import wf_mod_tool as core
from release_inventory_support import InventoryCase, LOGICAL, NESTED_LOGICAL, ordered


class ReleaseInventoryContractTest(InventoryCase):
    def test_contract_rejects_duplicate_json_keys_unknown_fields_and_schema(self):
        raw = (
            b'{"schema":"wf-release-inventory/v1",'
            b'"schema":"wf-release-inventory/v1",'
            b'"contract_id":"fixture","members":[]}'
        )
        with self.assertRaisesRegex(self.inventory.InventoryError, "duplicate JSON"):
            self.inventory.parse_contract(raw)
        table = ordered([("owned", b"row")])
        member = self.member("owner-a", table, self.flat_claim("owned"))
        for mutation, message in (
            (lambda value: value.update({"unexpected": True}), "unexpected.*field"),
            (lambda value: value.update({"schema": "future/v9"}), "unsupported schema"),
            (
                lambda value: value["members"][0]["claim"].update({"extra": 1}),
                "claim: unexpected",
            ),
        ):
            with self.subTest(message=message):
                payload = self.payload([copy.deepcopy(member)])
                mutation(payload)
                with self.assertRaisesRegex(self.inventory.InventoryError, message):
                    self.parse(payload)

    def test_contract_rejects_duplicate_logical_path_and_malformed_members(self):
        table = ordered([("owned", b"row")])
        member = self.member("owner-a", table, self.flat_claim("owned"))
        with self.assertRaisesRegex(self.inventory.InventoryError, "duplicate logical"):
            self.parse(self.payload([member, copy.deepcopy(member)]))
        table_mutations = (
            (lambda item: item.update({"root": "ios"}), "invalid root"),
            (lambda item: item.update({"logical_path": "../escape"}), "logical_path"),
            (lambda item: item["claim"].update({"outer_keys": []}), "outer_keys"),
        )
        for mutation, message in table_mutations:
            with self.subTest(message=message):
                item = copy.deepcopy(member)
                mutation(item)
                with self.assertRaisesRegex(self.inventory.InventoryError, message):
                    self.parse(self.payload([item]))
        for mutation, message in (
            (lambda item: item.update({"sha256": "A" * 64}), "sha256"),
            (lambda item: item.update({"size": -1}), "size"),
        ):
            with self.subTest(message=message):
                item = self.file_member("owner-a", b"png")
                mutation(item)
                with self.assertRaisesRegex(self.inventory.InventoryError, message):
                    self.parse(self.payload([item]))

    def test_contract_rejects_outer_inner_inconsistency(self):
        inner = ordered([("1", b"skill")])
        raw = ordered([("hero", inner)], raw_outer=True)
        claim = character_pack.TableClaim(
            "common", NESTED_LOGICAL, "action_nested",
            ("hero",), (("hero", ("1",)),),
        )
        member = self.member("owner-a", raw, claim)
        member["claim"]["inner_keys"] = {"other": ["1"]}
        with self.assertRaisesRegex(self.inventory.InventoryError, "inner_keys.*outer_keys"):
            self.parse(self.payload([member]))

    def test_file_and_table_contract_fields_are_strictly_disjoint(self):
        file_member = self.file_member("owner-a", b"png")
        self.assertEqual("file", self.parse(self.payload([file_member])).members[0].kind)
        with_claim = copy.deepcopy(file_member)
        with_claim["claim"] = {
            "codec_id": "flat", "outer_keys": ["x"], "inner_keys": {},
        }
        with self.assertRaisesRegex(self.inventory.InventoryError, "file.*claim"):
            self.parse(self.payload([with_claim]))
        table = ordered([("owned", b"row")])
        table_member = self.member("owner-a", table, self.flat_claim("owned"))
        del table_member["projection_sha256"]
        with self.assertRaisesRegex(
            self.inventory.InventoryError, "projection_sha256.*required"
        ):
            self.parse(self.payload([table_member]))
        for source_mutation, message in (
            (lambda source: source.update({"extra": 1}), "source: unexpected"),
            (lambda source: source.update({"size": True}), "source.size"),
            (lambda source: source.update({"sha256": "A" * 64}), "source.sha256"),
        ):
            with self.subTest(message=message):
                item = self.member("owner-a", table, self.flat_claim("owned"))
                source_mutation(item["source"])
                with self.assertRaisesRegex(self.inventory.InventoryError, message):
                    self.parse(self.payload([item]))

    def test_contract_rejects_mixed_codecs_and_unsafe_windows_paths(self):
        flat_raw = ordered([("owned", b"row")])
        flat = self.member("owner-a", flat_raw, self.flat_claim("owned"))
        raw_claim = character_pack.TableClaim("common", LOGICAL, "raw_outer", ("owned",))
        raw_outer = ordered([("owned", b"row")], raw_outer=True)
        with self.assertRaisesRegex(self.inventory.InventoryError, "codec.*conflict"):
            self.parse(self.payload([flat, self.member("owner-b", raw_outer, raw_claim)]))
        for bad_path in (
            "dir/file:stream", "dir/evil\x00name", "dir/evil\x1fname", "dir/del\x7fname",
        ):
            with self.subTest(path=repr(bad_path)):
                member = self.file_member("owner-a", b"opaque", logical_path=bad_path)
                with self.assertRaisesRegex(self.inventory.InventoryError, "logical_path"):
                    self.parse(self.payload([member]))

    def test_flat_projection_is_exact_and_key_order_sensitive(self):
        claim = self.flat_claim("a", "b")
        first = ordered([("sentinel", b"one"), ("a", b"A"), ("b", b"B")])
        sentinel_changed = ordered([
            ("sentinel", b"different"), ("a", b"A"), ("b", b"B")
        ])
        reordered = ordered([("b", b"B"), ("sentinel", b"one"), ("a", b"A")])
        self.assertEqual(
            (("a", None, b"A"), ("b", None, b"B")),
            self.inventory.project_claim(first, claim).rows,
        )
        self.assertEqual(
            self.inventory.projection_sha256(first, claim),
            self.inventory.projection_sha256(sentinel_changed, claim),
        )
        self.assertNotEqual(
            self.inventory.projection_sha256(first, claim),
            self.inventory.projection_sha256(reordered, claim),
        )

    def test_nested_projection_selects_only_declared_outer_and_inner_rows(self):
        hero = ordered([("0", b"ignored"), ("1", b"one"), ("2", b"two")])
        other = ordered([("1", b"other")])
        raw = ordered([("other", other), ("hero", hero)], raw_outer=True)
        claim = character_pack.TableClaim(
            "common", NESTED_LOGICAL, "action_nested",
            ("hero",), (("hero", ("1", "2")),),
        )
        self.assertEqual(
            (("hero", "1", b"one"), ("hero", "2", b"two")),
            self.inventory.project_claim(raw, claim).rows,
        )

    def test_raw_outer_switched_nested_and_server_json_projection(self):
        raw_outer = ordered([("skip", b"S"), ("owned", b"O")], raw_outer=True)
        raw_claim = character_pack.TableClaim(
            "common", "master/character/character_status.orderedmap",
            "raw_outer", ("owned",),
        )
        self.assertEqual(
            (("owned", None, b"O"),), self.inventory.project_claim(raw_outer, raw_claim).rows
        )
        inner = ordered([("skip", b"S"), ("owned", b"O")])
        switched = ordered([("hero", inner)], raw_outer=True)
        switched_claim = character_pack.TableClaim(
            "common", "master/skill/power_flip_action.orderedmap",
            "switched_nested", ("hero",), (("hero", ("owned",)),),
        )
        self.assertEqual(
            (("hero", "owned", b"O"),),
            self.inventory.project_claim(switched, switched_claim).rows,
        )
        server = b'{"skip":{"z":1},"owned":{"b":2,"a":1}}'
        json_claim = character_pack.TableClaim(
            "server", "character.json", "json_object", ("owned",)
        )
        self.assertEqual(
            (("owned", None, b'{"a":1,"b":2}'),),
            self.inventory.project_claim(server, json_claim).rows,
        )

    def test_merge_preserves_live_sentinel_and_rejects_stale_candidate(self):
        claim = self.flat_claim("owned")
        live = ordered([("sentinel", b"live"), ("owned", b"old")])
        candidate = ordered([("sentinel", b"stale"), ("owned", b"new")])
        member = self.parse(self.payload([
            self.member("owner-a", candidate, claim)
        ])).members[0]
        merged = self.inventory.merge_claimed_member(member, candidate, live)
        keys, rows = core._strict_orderedmap_rows(
            merged, label="merged", compressed_rows=True
        )
        self.assertEqual(["sentinel", "owned"], keys)
        self.assertEqual([b"live", b"new"], rows)
        stale = ordered([("sentinel", b"anything"), ("owned", b"wrong")])
        with self.assertRaisesRegex(self.inventory.InventoryError, "projection.*drift"):
            self.inventory.merge_claimed_member(member, stale, live)

    def test_json_merge_preserves_live_key_order_and_appends_new_claim(self):
        claim = character_pack.TableClaim(
            "server", "character.json", "json_object", ("owned", "new")
        )
        candidate = b'{"stale":0,"owned":{"v":2},"new":{"v":3}}'
        live = b'{"first":1,"owned":{"v":1},"last":9}'
        member = self.parse(self.payload([
            self.member("owner-a", candidate, claim)
        ])).members[0]
        self.assertEqual(
            b'{"first":1,"owned":{"v":2},"last":9,"new":{"v":3}}',
            self.inventory.merge_claimed_member(member, candidate, live),
        )

    def test_public_helpers_preserve_private_compatibility_aliases(self):
        import wf_release
        import wf_store_materialize

        self.assertIs(wf_release.merge_claimed_rows, wf_release._merge_claimed_rows)
        self.assertIs(
            wf_release.merge_claimed_table_bytes,
            wf_release._merge_claimed_table_bytes,
        )
        self.assertIs(
            wf_store_materialize.build_read_only_plan,
            wf_store_materialize._build_plan,
        )
