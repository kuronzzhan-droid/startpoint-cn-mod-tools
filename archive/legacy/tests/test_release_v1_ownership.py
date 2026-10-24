"""Deterministic ownership projection from sealed character package manifests."""

from __future__ import annotations

import copy
import unittest

from wf_release_v1.errors import ReleaseError
from wf_release_v1.ownership import project_character_ownership


HEX_A = "a" * 64


def file_entry(logical_path: str) -> dict[str, object]:
    return {"logical_path": logical_path, "sha256": HEX_A, "size": 1}


def table_entry(logical_path: str, *keys: str, root: str = "common") -> dict[str, object]:
    return {
        "root": root,
        "logical_path": logical_path,
        "codec_id": "flat",
        "outer_keys": list(keys),
        "inner_keys": [],
        "semantic_claims": [],
    }


def package_manifest() -> dict[str, object]:
    return {
        "schema_version": 1,
        "package_id": "seris-dragon-king",
        "character_id": 129999,
        "code_name": "seris_dragon_king",
        "package_version": "1.0.0",
        "requires_client_base": "1.4.54",
        "required_capabilities": [],
        "roots": {
            "common": [
                file_entry("master/character/character.orderedmap"),
                file_entry("master/skill/action_skill.orderedmap"),
            ],
            "medium": [file_entry("character/éclair/ui/square_0.png")],
            "android": [file_entry("character/seris_dragon_king/pixelart/sprite_sheet.png")],
            "server": [file_entry("character.json")],
        },
        "tables": [
            table_entry(
                "master/skill/action_skill.orderedmap",
                "seris_dragon_king",
                "129999",
            ),
            table_entry("master/character/character.orderedmap", "129999"),
            table_entry("character.json", "129999", root="server"),
        ],
        "skills": {},
        "unique_condition": {},
        "qa": {"delivery_mode": "production", "release_ready": True},
        "snapshot": {},
    }


def declared_paths(manifest: dict[str, object]) -> tuple[list[str], list[str]]:
    roots = manifest["roots"]
    assert isinstance(roots, dict)
    server = [entry["logical_path"] for entry in roots["server"]]
    overlay = [
        entry["logical_path"]
        for root in ("common", "medium", "android")
        for entry in roots[root]
    ]
    return server, overlay


class CharacterOwnershipProjectionTests(unittest.TestCase):
    def test_projects_only_declared_identity_records_and_exact_paths(self) -> None:
        manifest = package_manifest()
        server, overlay = declared_paths(manifest)

        ownership = project_character_ownership(
            workspace_manifest=manifest,
            declared_server_paths=server,
            declared_overlay_paths=list(reversed(overlay)),
        )

        self.assertEqual(
            {
                "schemaVersion": 1,
                "entities": ["character:129999"],
                "records": [
                    "action_skill:129999",
                    "action_skill:seris_dragon_king",
                    "character:129999",
                ],
                "paths": [
                    "character.json",
                    "character/seris_dragon_king/pixelart/sprite_sheet.png",
                    "character/éclair/ui/square_0.png",
                    "master/character/character.orderedmap",
                    "master/skill/action_skill.orderedmap",
                ],
            },
            ownership.to_wire(),
        )
        self.assertFalse(any("*" in path for path in ownership.paths))

    def test_rejects_duplicate_paths_within_each_payload_channel(self) -> None:
        manifest = package_manifest()
        server, overlay = declared_paths(manifest)

        for channel, declared_server, declared_overlay in (
            ("server", [*server, server[0]], overlay),
            ("overlay", server, [*overlay, overlay[0]]),
        ):
            with self.subTest(channel=channel):
                with self.assertRaises(ReleaseError) as raised:
                    project_character_ownership(
                        workspace_manifest=manifest,
                        declared_server_paths=declared_server,
                        declared_overlay_paths=declared_overlay,
                    )

                self.assertEqual("WFREL_OWNERSHIP_INVALID", raised.exception.code)

    def test_rejects_manual_identity_or_ownership_fields(self) -> None:
        for field, value in (
            ("workspace_identity", {"character_id": 129999}),
            ("workspace_character_id", 129999),
            ("workspace_code_name", "seris_dragon_king"),
            ("ownership", {}),
            ("entities", ["character:129999"]),
            ("records", ["character:129999"]),
            ("paths", ["character.json"]),
        ):
            with self.subTest(field=field):
                manifest = package_manifest()
                manifest[field] = value
                server, overlay = declared_paths(manifest)

                with self.assertRaises(ReleaseError) as raised:
                    project_character_ownership(
                        workspace_manifest=manifest,
                        declared_server_paths=server,
                        declared_overlay_paths=overlay,
                    )

                self.assertEqual("WFREL_OWNERSHIP_INVALID", raised.exception.code)

    def test_rejects_invalid_authoritative_character_identity(self) -> None:
        for field, value in (
            ("character_id", True),
            ("character_id", 0),
            ("code_name", "Seris Dragon King"),
        ):
            with self.subTest(field=field, value=value):
                manifest = package_manifest()
                manifest[field] = value
                server, overlay = declared_paths(manifest)

                with self.assertRaises(ReleaseError) as raised:
                    project_character_ownership(
                        workspace_manifest=manifest,
                        declared_server_paths=server,
                        declared_overlay_paths=overlay,
                    )

                self.assertEqual("WFREL_OWNERSHIP_INVALID", raised.exception.code)

    def test_rejects_malformed_roots_tables_and_wildcards(self) -> None:
        mutations = []

        missing_root = package_manifest()
        del missing_root["roots"]["android"]  # type: ignore[index]
        mutations.append(missing_root)

        extra_table_field = package_manifest()
        extra_table_field["tables"][0]["records"] = ["manual:claim"]  # type: ignore[index]
        mutations.append(extra_table_field)

        empty_key = package_manifest()
        empty_key["tables"][0]["outer_keys"] = [""]  # type: ignore[index]
        mutations.append(empty_key)

        wildcard = package_manifest()
        wildcard["roots"]["common"][0]["logical_path"] = "master/**"  # type: ignore[index]
        mutations.append(wildcard)

        for manifest in mutations:
            with self.subTest(manifest=manifest):
                roots = manifest.get("roots")
                server = []
                overlay = []
                if isinstance(roots, dict):
                    server = [
                        entry.get("logical_path")
                        for entry in roots.get("server", [])
                        if isinstance(entry, dict)
                    ]
                    overlay = [
                        entry.get("logical_path")
                        for root in ("common", "medium", "android")
                        for entry in roots.get(root, [])
                        if isinstance(entry, dict)
                    ]
                with self.assertRaises(ReleaseError) as raised:
                    project_character_ownership(
                        workspace_manifest=manifest,
                        declared_server_paths=server,
                        declared_overlay_paths=overlay,
                    )
                self.assertEqual("WFREL_OWNERSHIP_INVALID", raised.exception.code)

    def test_fails_closed_when_payload_partitions_do_not_exactly_match_manifest(self) -> None:
        manifest = package_manifest()
        server, overlay = declared_paths(manifest)

        for mismatch, declared_server, declared_overlay in (
            ("server", [], overlay),
            ("overlay", server, overlay[1:]),
            ("extra-server", [*server, "unowned/server.json"], overlay),
            ("extra-overlay", server, [*overlay, "unowned/client.bin"]),
            ("swapped-channels", [overlay[0]], [server[0], *overlay[1:]]),
        ):
            with self.subTest(mismatch=mismatch):
                with self.assertRaises(ReleaseError) as raised:
                    project_character_ownership(
                        workspace_manifest=manifest,
                        declared_server_paths=declared_server,
                        declared_overlay_paths=declared_overlay,
                    )

                self.assertEqual("WFREL_OWNERSHIP_COVERAGE", raised.exception.code)

    def test_rejects_a_logical_path_declared_under_multiple_manifest_roots(self) -> None:
        manifest = package_manifest()
        roots = manifest["roots"]
        assert isinstance(roots, dict)
        duplicate = copy.deepcopy(roots["common"][0])
        roots["medium"].append(duplicate)
        server, overlay = declared_paths(manifest)

        with self.assertRaises(ReleaseError) as raised:
            project_character_ownership(
                workspace_manifest=manifest,
                declared_server_paths=server,
                declared_overlay_paths=list(dict.fromkeys(overlay)),
            )

        self.assertEqual("WFREL_OWNERSHIP_INVALID", raised.exception.code)

    def test_rejects_noncanonical_declared_payload_paths(self) -> None:
        manifest = package_manifest()
        server, overlay = declared_paths(manifest)

        for bad_path in ("/character.json", "character\\seris", "character/**"):
            with self.subTest(path=bad_path):
                with self.assertRaises(ReleaseError) as raised:
                    project_character_ownership(
                        workspace_manifest=copy.deepcopy(manifest),
                        declared_server_paths=[*server, bad_path],
                        declared_overlay_paths=overlay,
                    )

                self.assertEqual("WFREL_OWNERSHIP_INVALID", raised.exception.code)


if __name__ == "__main__":
    unittest.main()
