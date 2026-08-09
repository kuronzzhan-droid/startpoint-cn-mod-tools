"""Strict wire-contract coverage for the three release-v1 manifests."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import re
import unittest

from wf_release_v1.errors import ReleaseError
from wf_release_v1.schema import (
    compute_release_id,
    parse_ownership,
    parse_release_manifest,
    parse_requirements,
    verify_release_id,
)


ROOT = Path(__file__).resolve().parents[1]
HEX_A = "a" * 64
HEX_B = "b" * 64
HEX_C = "c" * 64
HEX_D = "d" * 64
HEX_E = "e" * 64
RELEASE_ID_E = f"sha256:{HEX_E}"

SHA256_PATTERN = r"^[0-9a-f]{64}$"
RELEASE_ID_PATTERN = r"^sha256:[0-9a-f]{64}$"
DOTTED_VERSION_PATTERN = r"^(?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*))+$"
CAPABILITY_PATTERN = r"^[a-z0-9][a-z0-9._-]*@[1-9][0-9]*$"
PAYLOAD_PATH_PATTERN = (
    r"^(?!.*\\)(?!.*\u0000)(?!.*//)(?!.*(?:^|/)(?:\.|\.\.)(?:/|$))"
    r"(?:content|server|modes)/[^/]+(?:/[^/]+)*$"
)


def release_without_id() -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "name": "seris-dragon-king",
        "version": "1.0.0",
        "producer": {"name": "wf-mod-tools", "version": "1"},
        "replaces": [],
        "sourceEvidence": {
            "kind": "character-workspace-v1",
            "workspaceInputSha256": HEX_A,
        },
        "components": [{"kind": "content", "root": "content"}],
        "expectedState": {
            "cdnTargetVersion": "1.4.54",
            "contentDigest": None,
            "modeDigest": None,
        },
        "metadataSha256": {"requires": HEX_B, "ownership": HEX_C},
        "files": [
            {
                "path": "content/worldflipper-overlay-1.4.53-to-1.4.54.zip",
                "size": 123,
                "sha256": HEX_D,
            }
        ],
    }


def release_wire(*, computed_id: bool = False) -> dict[str, object]:
    value = release_without_id()
    value["releaseId"] = compute_release_id(value) if computed_id else RELEASE_ID_E
    return value


def requirements_wire() -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "runtimeApi": 1,
        "serverCapabilities": ["content.sync@1", "mode.release-contract@1"],
        "clientVersions": ["1.4.54", "1.4.55"],
        "resourceBaselines": ["1.4.53", "1.4.54"],
        "contentDigests": [f"sha256:{HEX_A}", f"sha256:{HEX_B}"],
        "patchOverlaySchema": 1,
        "clientPatchProfile": True,
    }


def ownership_wire() -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "entities": ["character:310099"],
        "records": ["characters:310099", "skills:310099"],
        "paths": ["assets/character/310099/**", "content/character/310099.atf"],
    }


def replace_at_path(value: dict[str, object], path: tuple[object, ...], replacement: object) -> None:
    cursor: object = value
    for part in path[:-1]:
        cursor = cursor[part]  # type: ignore[index]
    cursor[path[-1]] = replacement  # type: ignore[index]


class ManifestHappyPathTests(unittest.TestCase):
    def test_parses_each_exact_wire_shape_into_frozen_detached_values(self) -> None:
        release_input = release_wire()
        requirements_input = requirements_wire()
        ownership_input = ownership_wire()

        release = parse_release_manifest(release_input)
        requirements = parse_requirements(requirements_input)
        ownership = parse_ownership(ownership_input)

        self.assertEqual(release_input, release.to_wire())
        self.assertEqual(requirements_input, requirements.to_wire())
        self.assertEqual(ownership_input, ownership.to_wire())

        release_input["producer"]["version"] = "changed"  # type: ignore[index]
        requirements_input["serverCapabilities"].append("other@1")  # type: ignore[union-attr]
        ownership_input["paths"].append("changed")  # type: ignore[union-attr]
        self.assertEqual("1", release.to_wire()["producer"]["version"])
        self.assertEqual(2, len(requirements.to_wire()["serverCapabilities"]))
        self.assertEqual(2, len(ownership.to_wire()["paths"]))

        with self.assertRaises(FrozenInstanceError):
            release.name = "changed"  # type: ignore[misc]

    def test_accepts_null_or_strict_prefixed_expected_digests(self) -> None:
        parse_release_manifest(release_wire())
        value = release_wire()
        expected_state = value["expectedState"]
        expected_state["contentDigest"] = f"sha256:{HEX_A}"  # type: ignore[index]
        expected_state["modeDigest"] = f"sha256:{HEX_B}"  # type: ignore[index]
        parsed = parse_release_manifest(value)
        self.assertEqual(expected_state, parsed.to_wire()["expectedState"])


class ExactKeyAndTypeTests(unittest.TestCase):
    def assert_rejected(self, parser, value: object) -> None:
        with self.assertRaises(ReleaseError):
            parser(value)

    def test_rejects_non_objects_and_unknown_or_missing_top_level_keys(self) -> None:
        for parser, fixture in (
            (parse_release_manifest, release_wire()),
            (parse_requirements, requirements_wire()),
            (parse_ownership, ownership_wire()),
        ):
            with self.subTest(parser=parser.__name__, case="non-object"):
                self.assert_rejected(parser, [])
            missing = deepcopy(fixture)
            del missing["schemaVersion"]
            with self.subTest(parser=parser.__name__, case="missing"):
                self.assert_rejected(parser, missing)
            unknown = deepcopy(fixture)
            unknown["unknown"] = None
            with self.subTest(parser=parser.__name__, case="unknown"):
                self.assert_rejected(parser, unknown)

    def test_rejects_unknown_or_missing_nested_release_keys(self) -> None:
        nested_paths = (
            ("producer",),
            ("sourceEvidence",),
            ("components", 0),
            ("expectedState",),
            ("metadataSha256",),
            ("files", 0),
        )
        for path in nested_paths:
            base = release_wire()
            nested: dict[str, object] = base
            for part in path:
                nested = nested[part]  # type: ignore[index,assignment]
            key = next(iter(nested))

            missing = deepcopy(base)
            missing_nested: dict[str, object] = missing
            for part in path:
                missing_nested = missing_nested[part]  # type: ignore[index,assignment]
            del missing_nested[key]
            with self.subTest(path=path, case="missing"):
                self.assert_rejected(parse_release_manifest, missing)

            unknown = deepcopy(base)
            unknown_nested: dict[str, object] = unknown
            for part in path:
                unknown_nested = unknown_nested[part]  # type: ignore[index,assignment]
            unknown_nested["unknown"] = None
            with self.subTest(path=path, case="unknown"):
                self.assert_rejected(parse_release_manifest, unknown)

    def test_rejects_bool_where_an_integer_is_required(self) -> None:
        cases = (
            (parse_release_manifest, release_wire(), ("schemaVersion",)),
            (parse_release_manifest, release_wire(), ("files", 0, "size")),
            (parse_requirements, requirements_wire(), ("schemaVersion",)),
            (parse_requirements, requirements_wire(), ("runtimeApi",)),
            (parse_requirements, requirements_wire(), ("patchOverlaySchema",)),
            (parse_ownership, ownership_wire(), ("schemaVersion",)),
        )
        for parser, value, path in cases:
            replace_at_path(value, path, True)
            with self.subTest(parser=parser.__name__, path=path):
                self.assert_rejected(parser, value)

    def test_client_patch_profile_is_a_strict_boolean(self) -> None:
        for invalid in (0, 1, "true", None):
            value = requirements_wire()
            value["clientPatchProfile"] = invalid
            with self.subTest(invalid=invalid):
                self.assert_rejected(parse_requirements, value)


class OrderedUniqueArrayTests(unittest.TestCase):
    def assert_rejected(self, parser, value: object) -> None:
        with self.assertRaises(ReleaseError):
            parser(value)

    def test_rejects_empty_required_arrays_but_allows_empty_replaces(self) -> None:
        for key in ("components", "files"):
            value = release_wire()
            value[key] = []
            with self.subTest(manifest="release", key=key):
                self.assert_rejected(parse_release_manifest, value)
        parse_release_manifest(release_wire())

        for key in (
            "serverCapabilities",
            "clientVersions",
            "resourceBaselines",
            "contentDigests",
        ):
            value = requirements_wire()
            value[key] = []
            with self.subTest(manifest="requires", key=key):
                self.assert_rejected(parse_requirements, value)

        for key in ("entities", "records", "paths"):
            value = ownership_wire()
            value[key] = []
            with self.subTest(manifest="ownership", key=key):
                self.assert_rejected(parse_ownership, value)

    def test_rejects_unsorted_or_duplicate_requirement_arrays(self) -> None:
        for key in (
            "serverCapabilities",
            "clientVersions",
            "resourceBaselines",
            "contentDigests",
        ):
            base = requirements_wire()
            original = base[key]

            unsorted = deepcopy(base)
            unsorted[key] = list(reversed(original))  # type: ignore[arg-type]
            with self.subTest(key=key, case="unsorted"):
                self.assert_rejected(parse_requirements, unsorted)

            duplicate = deepcopy(base)
            duplicate[key] = [original[0], original[0]]  # type: ignore[index]
            with self.subTest(key=key, case="duplicate"):
                self.assert_rejected(parse_requirements, duplicate)

    def test_rejects_unsorted_or_duplicate_ownership_arrays(self) -> None:
        for key in ("entities", "records", "paths"):
            base = ownership_wire()
            values = base[key]
            if len(values) == 1:  # type: ignore[arg-type]
                values.append(f"{values[0]}-z")  # type: ignore[union-attr,index]

            unsorted = deepcopy(base)
            unsorted[key] = list(reversed(values))  # type: ignore[arg-type]
            with self.subTest(key=key, case="unsorted"):
                self.assert_rejected(parse_ownership, unsorted)

            duplicate = deepcopy(base)
            duplicate[key] = [values[0], values[0]]  # type: ignore[index]
            with self.subTest(key=key, case="duplicate"):
                self.assert_rejected(parse_ownership, duplicate)


class ReleasePayloadAndReplacementTests(unittest.TestCase):
    def assert_rejected(self, value: object) -> None:
        with self.assertRaises(ReleaseError):
            parse_release_manifest(value)

    def test_components_are_unique_sorted_and_root_equals_kind(self) -> None:
        valid = release_wire()
        valid["components"] = [
            {"kind": "content", "root": "content"},
            {"kind": "server", "root": "server"},
        ]
        valid["files"].append(  # type: ignore[union-attr]
            {"path": "server/data.json", "size": 1, "sha256": HEX_A}
        )
        parse_release_manifest(valid)

        cases = []
        wrong_root = release_wire()
        wrong_root["components"][0]["root"] = "server"  # type: ignore[index]
        cases.append(("wrong-root", wrong_root))
        unknown_kind = release_wire()
        unknown_kind["components"][0]["kind"] = "scripts"  # type: ignore[index]
        cases.append(("unknown-kind", unknown_kind))
        duplicate = deepcopy(valid)
        duplicate["components"].append(  # type: ignore[union-attr]
            {"kind": "server", "root": "server"}
        )
        cases.append(("duplicate", duplicate))
        unsorted = deepcopy(valid)
        unsorted["components"] = list(reversed(unsorted["components"]))  # type: ignore[arg-type]
        cases.append(("unsorted", unsorted))

        for label, value in cases:
            with self.subTest(label=label):
                self.assert_rejected(value)

    def test_files_are_safe_unique_sorted_and_bound_to_declared_components(self) -> None:
        base = release_wire()
        second = {"path": "content/z.zip", "size": 1, "sha256": HEX_A}
        base["files"].append(second)  # type: ignore[union-attr]
        parse_release_manifest(base)

        unsorted = deepcopy(base)
        unsorted["files"] = list(reversed(unsorted["files"]))  # type: ignore[arg-type]
        duplicate = deepcopy(base)
        duplicate["files"].append(deepcopy(duplicate["files"][0]))  # type: ignore[index,union-attr]
        undeclared = release_wire()
        undeclared["files"][0]["path"] = "server/data.json"  # type: ignore[index]
        metadata = release_wire()
        metadata["files"][0]["path"] = "release-manifest.json"  # type: ignore[index]
        negative_size = release_wire()
        negative_size["files"][0]["size"] = -1  # type: ignore[index]

        for label, value in (
            ("unsorted", unsorted),
            ("duplicate", duplicate),
            ("undeclared", undeclared),
            ("metadata", metadata),
            ("negative-size", negative_size),
        ):
            with self.subTest(label=label):
                self.assert_rejected(value)

        for path in (
            "content/../escape.zip",
            "content\\backslash.zip",
            "/content/absolute.zip",
            "content/trailing/",
            "content/e\u0301.zip",
        ):
            value = release_wire()
            value["files"][0]["path"] = path  # type: ignore[index]
            with self.subTest(path=path):
                self.assert_rejected(value)

    def test_rejects_a_declared_component_without_payload_files(self) -> None:
        value = release_wire()
        value["components"] = [
            {"kind": "content", "root": "content"},
            {"kind": "server", "root": "server"},
        ]
        self.assert_rejected(value)

    def test_replaces_accepts_only_sorted_unique_release_ids_not_self(self) -> None:
        valid = release_wire()
        valid["replaces"] = [f"sha256:{HEX_A}", f"sha256:{HEX_B}"]
        parse_release_manifest(valid)

        for replacements in (
            [HEX_A],
            [f"sha256:{'A' * 64}"],
            [f"sha256:{HEX_A}", f"sha256:{HEX_A}"],
            [f"sha256:{HEX_B}", f"sha256:{HEX_A}"],
            [RELEASE_ID_E],
        ):
            value = release_wire()
            value["replaces"] = replacements
            with self.subTest(replacements=replacements):
                self.assert_rejected(value)

    def test_rejects_malformed_hashes_versions_names_and_capabilities(self) -> None:
        release_cases = (
            (("name",), "Seris Dragon"),
            (("version",), "v1"),
            (("sourceEvidence", "workspaceInputSha256"), f"sha256:{HEX_A}"),
            (("expectedState", "cdnTargetVersion"), "latest"),
            (("expectedState", "contentDigest"), HEX_A),
            (("metadataSha256", "requires"), f"sha256:{HEX_B}"),
            (("files", 0, "sha256"), f"sha256:{HEX_D}"),
            (("releaseId",), HEX_E),
        )
        for path, invalid in release_cases:
            value = release_wire()
            replace_at_path(value, path, invalid)
            with self.subTest(manifest="release", path=path):
                self.assert_rejected(value)

        requirement_cases = (
            ("serverCapabilities", ["unversioned"]),
            ("clientVersions", ["latest"]),
            ("resourceBaselines", [f"sha256:{HEX_A}"]),
            ("contentDigests", [HEX_A]),
        )
        for key, invalid in requirement_cases:
            value = requirements_wire()
            value[key] = invalid
            with self.subTest(manifest="requires", key=key):
                with self.assertRaises(ReleaseError):
                    parse_requirements(value)


class ReleaseIdTests(unittest.TestCase):
    def test_computes_release_id_from_the_complete_manifest_without_id(self) -> None:
        # Hand-derived once from the literal fixture using RFC-compatible canonical JSON.
        self.assertEqual(
            "sha256:c6aceb93ffc13e020ef7cbfec1d0f5c2205a1407c16bc76db677887d74f87f03",
            compute_release_id(release_without_id()),
        )
        with self.assertRaises(ReleaseError):
            compute_release_id(release_wire())

    def test_any_metadata_or_payload_identity_change_changes_release_id(self) -> None:
        base = release_without_id()
        original = compute_release_id(base)
        variants: list[dict[str, object]] = []
        changes = (
            (("name",), "seris-dragon-queen"),
            (("version",), "1.0.1"),
            (("producer", "version"), "2"),
            (("sourceEvidence", "workspaceInputSha256"), HEX_B),
            (("expectedState", "contentDigest"), f"sha256:{HEX_A}"),
            (("metadataSha256", "requires"), HEX_C),
            (("files", 0, "path"), "content/worldflipper-overlay-1.4.54.zip"),
            (("files", 0, "size"), 124),
            (("files", 0, "sha256"), HEX_A),
        )
        for path, replacement in changes:
            variant = deepcopy(base)
            replace_at_path(variant, path, replacement)
            variants.append(variant)
        replacement_variant = deepcopy(base)
        replacement_variant["replaces"] = [f"sha256:{HEX_A}"]
        variants.append(replacement_variant)

        for variant in variants:
            with self.subTest(variant=variant):
                self.assertNotEqual(original, compute_release_id(variant))

    def test_verify_release_id_accepts_exact_value_and_rejects_mismatch(self) -> None:
        verify_release_id(parse_release_manifest(release_wire(computed_id=True)))
        with self.assertRaises(ReleaseError) as raised:
            verify_release_id(parse_release_manifest(release_wire()))
        self.assertEqual("WFREL_HASH_MISMATCH", raised.exception.code)


class JsonSchemaLockTests(unittest.TestCase):
    def load_schema(self, name: str) -> dict[str, object]:
        return json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))

    def assert_all_object_nodes_are_closed(self, node: object) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object":
                self.assertIs(False, node.get("additionalProperties"), node)
            for child in node.values():
                self.assert_all_object_nodes_are_closed(child)
        elif isinstance(node, list):
            for child in node:
                self.assert_all_object_nodes_are_closed(child)

    def assert_exact_top_level(self, schema: dict[str, object], fixture: dict[str, object]) -> None:
        self.assertEqual(set(fixture), set(schema["required"]))
        self.assertEqual(set(fixture), set(schema["properties"]))
        self.assertEqual(1, schema["properties"]["schemaVersion"]["const"])
        self.assert_all_object_nodes_are_closed(schema)

    def assert_required(self, node: dict[str, object], *keys: str) -> None:
        self.assertEqual(set(keys), set(node["required"]))

    def test_json_schemas_lock_exact_shapes_versions_patterns_and_fixtures(self) -> None:
        release_schema = self.load_schema("wf-release-v1.schema.json")
        requirements_schema = self.load_schema("wf-release-requires-v1.schema.json")
        ownership_schema = self.load_schema("wf-release-ownership-v1.schema.json")

        self.assert_exact_top_level(release_schema, release_wire())
        self.assert_exact_top_level(requirements_schema, requirements_wire())
        self.assert_exact_top_level(ownership_schema, ownership_wire())

        release_properties = release_schema["properties"]
        self.assert_required(release_properties["producer"], "name", "version")
        self.assert_required(
            release_properties["sourceEvidence"], "kind", "workspaceInputSha256"
        )
        self.assert_required(
            release_properties["expectedState"],
            "cdnTargetVersion",
            "contentDigest",
            "modeDigest",
        )
        self.assert_required(
            release_properties["metadataSha256"], "requires", "ownership"
        )
        self.assert_required(
            release_properties["files"]["items"], "path", "size", "sha256"
        )
        for component in release_schema["$defs"]["component"]["oneOf"]:
            self.assert_required(component, "kind", "root")

        definitions = release_schema["$defs"]
        self.assertEqual(SHA256_PATTERN, definitions["sha256"]["pattern"])
        self.assertEqual(RELEASE_ID_PATTERN, definitions["releaseId"]["pattern"])
        self.assertEqual(DOTTED_VERSION_PATTERN, definitions["dottedVersion"]["pattern"])
        self.assertEqual(PAYLOAD_PATH_PATTERN, definitions["payloadPath"]["pattern"])
        self.assertEqual(
            CAPABILITY_PATTERN,
            requirements_schema["$defs"]["capability"]["pattern"],
        )
        self.assertEqual(
            DOTTED_VERSION_PATTERN,
            requirements_schema["$defs"]["dottedVersion"]["pattern"],
        )
        self.assertEqual(
            RELEASE_ID_PATTERN,
            requirements_schema["$defs"]["releaseId"]["pattern"],
        )

        for schema in (release_schema, requirements_schema, ownership_schema):
            self.assertEqual("https://json-schema.org/draft/2020-12/schema", schema["$schema"])

        for pattern, accepted, rejected in (
            (SHA256_PATTERN, HEX_A, f"sha256:{HEX_A}"),
            (RELEASE_ID_PATTERN, f"sha256:{HEX_A}", HEX_A),
            (DOTTED_VERSION_PATTERN, "1.4.54", "latest"),
            (CAPABILITY_PATTERN, "mode.release-contract@1", "mode.release-contract"),
            (PAYLOAD_PATH_PATTERN, "content/file.zip", "release-manifest.json"),
        ):
            self.assertIsNotNone(re.fullmatch(pattern, accepted))
            self.assertIsNone(re.fullmatch(pattern, rejected))

        self.assertEqual(release_wire(), parse_release_manifest(release_wire()).to_wire())
        self.assertEqual(
            requirements_wire(), parse_requirements(requirements_wire()).to_wire()
        )
        self.assertEqual(ownership_wire(), parse_ownership(ownership_wire()).to_wire())


if __name__ == "__main__":
    unittest.main()
