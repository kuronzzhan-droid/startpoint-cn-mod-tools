"""Strict wire-contract coverage for the three release-v1 manifests."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import re
import unittest

from tests.release_v1_schema_support import (
    CAPABILITY_PATTERN,
    DOTTED_VERSION_PATTERN,
    Draft202012Subset,
    HEX_A,
    HEX_B,
    HEX_C,
    HEX_D,
    HEX_E,
    PAYLOAD_PATH_PATTERN,
    RELEASE_ID_E,
    RELEASE_ID_PATTERN,
    SHA256_PATTERN,
    SchemaDefinitionError,
    ownership_wire,
    release_wire,
    release_without_id,
    replace_at_path,
    requirements_wire,
)

from wf_release_v1.errors import ReleaseError
from wf_release_v1.schema import (
    compute_release_id,
    parse_ownership,
    parse_release_manifest,
    parse_requirements,
    verify_release_id,
)


ROOT = Path(__file__).resolve().parents[1]


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

    def schema_patterns(self, node: object):
        if isinstance(node, dict):
            if "pattern" in node:
                yield node["pattern"]
            for child in node.values():
                yield from self.schema_patterns(child)
        elif isinstance(node, list):
            for child in node:
                yield from self.schema_patterns(child)

    def assert_structural_rejection(self, evaluator, parser, value: object) -> None:
        self.assertFalse(evaluator.accepts(value))
        with self.assertRaises(ReleaseError):
            parser(value)

    def assert_parser_only_rejection(self, evaluator, parser, value: object) -> None:
        self.assertTrue(evaluator.accepts(value))
        with self.assertRaises(ReleaseError):
            parser(value)

    def test_evaluator_executes_every_used_keyword_and_fails_closed(self) -> None:
        schemas = (
            self.load_schema("wf-release-v1.schema.json"),
            self.load_schema("wf-release-requires-v1.schema.json"),
            self.load_schema("wf-release-ownership-v1.schema.json"),
        )
        evaluators = tuple(Draft202012Subset(schema) for schema in schemas)
        used = set().union(*(evaluator.used_keywords for evaluator in evaluators))
        self.assertEqual(Draft202012Subset.KEYWORDS, used)

        with self.assertRaises(SchemaDefinitionError):
            Draft202012Subset({"type": "string", "silentlyIgnored": True})
        with self.assertRaises(SchemaDefinitionError):
            Draft202012Subset({"$ref": "#/$defs/missing", "$defs": {}})

    def test_schema_and_parser_reject_the_same_structural_fixtures(self) -> None:
        release_schema = Draft202012Subset(
            self.load_schema("wf-release-v1.schema.json")
        )
        requirements_schema = Draft202012Subset(
            self.load_schema("wf-release-requires-v1.schema.json")
        )
        ownership_schema = Draft202012Subset(
            self.load_schema("wf-release-ownership-v1.schema.json")
        )
        self.assertTrue(release_schema.accepts(release_wire()))
        self.assertTrue(requirements_schema.accepts(requirements_wire()))
        self.assertTrue(ownership_schema.accepts(ownership_wire()))

        release_cases = []
        missing = release_wire()
        del missing["version"]
        release_cases.append(missing)
        unknown = release_wire()
        unknown["unknown"] = None
        release_cases.append(unknown)
        nested_unknown = release_wire()
        nested_unknown["producer"]["unknown"] = None  # type: ignore[index]
        release_cases.append(nested_unknown)
        empty_producer_name = release_wire()
        empty_producer_name["producer"]["name"] = ""  # type: ignore[index]
        release_cases.append(empty_producer_name)
        for path, replacement in (
            (("schemaVersion",), "1"),
            (("schemaVersion",), 2),
            (("name",), "Bad Name"),
            (("components",), []),
            (("expectedState", "contentDigest"), HEX_A),
            (("files", 0, "size"), -1),
            (("files", 0, "sha256"), f"sha256:{HEX_D}"),
            (("releaseId",), HEX_E),
        ):
            value = release_wire()
            replace_at_path(value, path, replacement)
            release_cases.append(value)
        duplicate_component = release_wire()
        duplicate_component["components"].append(  # type: ignore[union-attr]
            {"kind": "content", "root": "content"}
        )
        release_cases.append(duplicate_component)
        missing_file_key = release_wire()
        del missing_file_key["files"][0]["size"]  # type: ignore[index]
        release_cases.append(missing_file_key)
        for value in release_cases:
            with self.subTest(manifest="release", value=value):
                self.assert_structural_rejection(
                    release_schema, parse_release_manifest, value
                )

        requirement_cases = []
        for key in (
            "serverCapabilities",
            "clientVersions",
            "resourceBaselines",
            "contentDigests",
        ):
            empty = requirements_wire()
            empty[key] = []
            requirement_cases.append(empty)
        for key, replacement in (
            ("runtimeApi", 0),
            ("serverCapabilities", ["unversioned"]),
            ("clientPatchProfile", 1),
        ):
            value = requirements_wire()
            value[key] = replacement
            requirement_cases.append(value)
        duplicate_digest = requirements_wire()
        duplicate_digest["contentDigests"] = [f"sha256:{HEX_A}"] * 2
        requirement_cases.append(duplicate_digest)
        for value in requirement_cases:
            with self.subTest(manifest="requires", value=value):
                self.assert_structural_rejection(
                    requirements_schema, parse_requirements, value
                )

        ownership_cases = []
        for key in ("entities", "records", "paths"):
            empty = ownership_wire()
            empty[key] = []
            ownership_cases.append(empty)
        invalid_path = ownership_wire()
        invalid_path["paths"] = ["../escape"]
        ownership_cases.append(invalid_path)
        duplicate_path = ownership_wire()
        duplicate_path["paths"] = ["assets/same", "assets/same"]
        ownership_cases.append(duplicate_path)
        for value in ownership_cases:
            with self.subTest(manifest="ownership", value=value):
                self.assert_structural_rejection(
                    ownership_schema, parse_ownership, value
                )

    def test_asset_replacement_source_evidence_is_closed_canonical_and_portable(self) -> None:
        """Aliases, unknown fields, and reordered before claims must not verify."""
        evaluator = Draft202012Subset(self.load_schema("wf-release-v1.schema.json"))

        def value(entries: list[dict[str, object]]) -> dict[str, object]:
            manifest = release_without_id()
            manifest["sourceEvidence"] = {
                "kind": "character-workspace-v2",
                "workspaceInputSha256": HEX_A,
                "acceptedAssetReplacements": entries,
            }
            manifest["releaseId"] = RELEASE_ID_E
            return manifest

        valid_entries = [
            {
                "beforeSha256": HEX_B,
                "beforeSize": 15,
                "logicalPath": "item/sprite_sheet.atlas.amf3.deflate",
                "root": "common",
            },
            {
                "beforeSha256": HEX_C,
                "beforeSize": 482079,
                "logicalPath": "item/sprite_sheet.png",
                "root": "common",
            },
        ]
        valid = value(deepcopy(valid_entries))
        self.assertTrue(evaluator.accepts(valid))
        parsed = parse_release_manifest(valid)
        self.assertEqual(valid, parsed.to_wire())
        self.assertEqual(2, len(parsed.source_evidence.accepted_asset_replacements))

        unicode_near_match = value([
            {**valid_entries[0], "logicalPath": "item/ss.bin"},
            {**valid_entries[1], "logicalPath": "item/ß.bin"},
        ])
        self.assertEqual(
            unicode_near_match,
            parse_release_manifest(unicode_near_match).to_wire(),
        )

        unknown = deepcopy(valid_entries)
        unknown[0]["unexpected"] = True
        structural = value(unknown)
        self.assertFalse(evaluator.accepts(structural))
        with self.assertRaises(ReleaseError):
            parse_release_manifest(structural)

        parser_only = (
            list(reversed(deepcopy(valid_entries))),
            [
                {**valid_entries[0], "logicalPath": "item/SAME.png"},
                {**valid_entries[1], "logicalPath": "item/same.png"},
            ],
            [{**valid_entries[0], "logicalPath": "master/item/item.orderedmap"}],
            [{**valid_entries[0], "logicalPath": "item/CON.png"}],
            [{**valid_entries[0], "logicalPath": "item/COM¹.png"}],
            [{**valid_entries[0], "logicalPath": "item/com².png"}],
            [{**valid_entries[0], "logicalPath": "item/LPT³.png"}],
            [{**valid_entries[0], "beforeSize": 15.0}],
        )
        for entries in parser_only:
            candidate = value(entries)
            self.assertTrue(evaluator.accepts(candidate))
            with self.assertRaises(ReleaseError):
                parse_release_manifest(candidate)

    def test_parser_remains_authoritative_for_non_schema_semantics(self) -> None:
        release_document = self.load_schema("wf-release-v1.schema.json")
        requirements_document = self.load_schema(
            "wf-release-requires-v1.schema.json"
        )
        ownership_document = self.load_schema("wf-release-ownership-v1.schema.json")
        evaluators = (
            Draft202012Subset(release_document),
            Draft202012Subset(requirements_document),
            Draft202012Subset(ownership_document),
        )
        for schema in (release_document, requirements_document, ownership_document):
            comment = schema.get("$comment")
            self.assertIsInstance(comment, str)
            self.assertIn("authoritative", comment)
            self.assertIn("MUST NOT", comment)

        release_semantic_cases = []
        float_size = release_wire()
        float_size["files"][0]["size"] = 123.0  # type: ignore[index]
        release_semantic_cases.append(float_size)
        unsorted_files = release_wire()
        unsorted_files["files"].append(  # type: ignore[union-attr]
            {"path": "content/a.zip", "size": 1, "sha256": HEX_A}
        )
        release_semantic_cases.append(unsorted_files)
        decomposed_path = release_wire()
        decomposed_path["files"][0]["path"] = "content/e\u0301.zip"  # type: ignore[index]
        release_semantic_cases.append(decomposed_path)
        empty_component = release_wire()
        empty_component["components"].append(  # type: ignore[union-attr]
            {"kind": "server", "root": "server"}
        )
        release_semantic_cases.append(empty_component)
        undeclared_component = release_wire()
        undeclared_component["files"][0]["path"] = "server/data.json"  # type: ignore[index]
        release_semantic_cases.append(undeclared_component)
        duplicate_path = release_wire()
        duplicate_path["files"].append(  # type: ignore[union-attr]
            {
                "path": duplicate_path["files"][0]["path"],  # type: ignore[index]
                "size": 124,
                "sha256": HEX_A,
            }
        )
        release_semantic_cases.append(duplicate_path)
        self_replacement = release_wire()
        self_replacement["replaces"] = [RELEASE_ID_E]
        release_semantic_cases.append(self_replacement)
        for value in release_semantic_cases:
            with self.subTest(manifest="release", value=value):
                self.assert_parser_only_rejection(
                    evaluators[0], parse_release_manifest, value
                )

        float_runtime = requirements_wire()
        float_runtime["runtimeApi"] = 1.0
        unsorted_requirements = requirements_wire()
        unsorted_requirements["serverCapabilities"] = list(
            reversed(unsorted_requirements["serverCapabilities"])  # type: ignore[arg-type]
        )
        for value in (float_runtime, unsorted_requirements):
            with self.subTest(manifest="requires", value=value):
                self.assert_parser_only_rejection(
                    evaluators[1], parse_requirements, value
                )

        float_version = ownership_wire()
        float_version["schemaVersion"] = 1.0
        decomposed_ownership_path = ownership_wire()
        decomposed_ownership_path["paths"] = ["assets/e\u0301/**"]
        unsorted_ownership = ownership_wire()
        unsorted_ownership["paths"] = list(
            reversed(unsorted_ownership["paths"])  # type: ignore[arg-type]
        )
        for value in (float_version, decomposed_ownership_path, unsorted_ownership):
            with self.subTest(manifest="ownership", value=value):
                self.assert_parser_only_rejection(
                    evaluators[2], parse_ownership, value
                )

        mismatched = release_wire()
        self.assertTrue(evaluators[0].accepts(mismatched))
        parsed = parse_release_manifest(mismatched)
        with self.assertRaises(ReleaseError):
            verify_release_id(parsed)

    def test_schema_search_patterns_reject_trailing_control_characters(self) -> None:
        cases = (
            (
                Draft202012Subset(self.load_schema("wf-release-v1.schema.json")),
                parse_release_manifest,
                release_wire,
                (
                    ("name",),
                    ("version",),
                    ("sourceEvidence", "workspaceInputSha256"),
                    ("expectedState", "cdnTargetVersion"),
                    ("files", 0, "path"),
                    ("releaseId",),
                ),
            ),
            (
                Draft202012Subset(
                    self.load_schema("wf-release-requires-v1.schema.json")
                ),
                parse_requirements,
                requirements_wire,
                (
                    ("serverCapabilities", 0),
                    ("clientVersions", 0),
                    ("contentDigests", 0),
                ),
            ),
            (
                Draft202012Subset(
                    self.load_schema("wf-release-ownership-v1.schema.json")
                ),
                parse_ownership,
                ownership_wire,
                (("entities", 0), ("paths", 0)),
            ),
        )
        for evaluator, parser, fixture, paths in cases:
            for path in paths:
                is_path = path[-1] == "path" or path[0] == "paths"
                terminators = (
                    ("\n", "\r\n", "\t", "\x01", "\x7f")
                    if is_path
                    else ("\n", "\r\n")
                )
                for terminator in terminators:
                    value = fixture()
                    current: object = value
                    for part in path:
                        current = current[part]  # type: ignore[index]
                    replace_at_path(value, path, f"{current}{terminator}")
                    with self.subTest(
                        parser=parser.__name__, path=path, terminator=repr(terminator)
                    ):
                        self.assert_structural_rejection(evaluator, parser, value)

    def test_json_schemas_lock_exact_shapes_versions_patterns_and_fixtures(self) -> None:
        release_schema = self.load_schema("wf-release-v1.schema.json")
        requirements_schema = self.load_schema("wf-release-requires-v1.schema.json")
        ownership_schema = self.load_schema("wf-release-ownership-v1.schema.json")

        self.assert_exact_top_level(release_schema, release_wire())
        self.assert_exact_top_level(requirements_schema, requirements_wire())
        self.assert_exact_top_level(ownership_schema, ownership_wire())

        release_properties = release_schema["properties"]
        self.assert_required(release_properties["producer"], "name", "version")
        source_evidence_variants = release_properties["sourceEvidence"]["oneOf"]
        self.assertEqual(2, len(source_evidence_variants))
        self.assert_required(
            source_evidence_variants[0], "kind", "workspaceInputSha256"
        )
        self.assert_required(
            source_evidence_variants[1],
            "kind",
            "workspaceInputSha256",
            "acceptedAssetReplacements",
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
            for pattern in self.schema_patterns(schema):
                self.assertNotIn("$", pattern)

        for pattern, accepted, rejected in (
            (SHA256_PATTERN, HEX_A, f"sha256:{HEX_A}"),
            (RELEASE_ID_PATTERN, f"sha256:{HEX_A}", HEX_A),
            (DOTTED_VERSION_PATTERN, "1.4.54", "latest"),
            (CAPABILITY_PATTERN, "mode.release-contract@1", "mode.release-contract"),
            (PAYLOAD_PATH_PATTERN, "content/file.zip", "release-manifest.json"),
        ):
            self.assertNotIn("$", pattern)
            self.assertIsNotNone(re.search(pattern, accepted))
            self.assertIsNone(re.search(pattern, rejected))

        self.assertEqual(release_wire(), parse_release_manifest(release_wire()).to_wire())
        self.assertEqual(
            requirements_wire(), parse_requirements(requirements_wire()).to_wire()
        )
        self.assertEqual(ownership_wire(), parse_ownership(ownership_wire()).to_wire())


if __name__ == "__main__":
    unittest.main()
