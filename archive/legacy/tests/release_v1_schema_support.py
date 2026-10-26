"""Zero-dependency fixtures and JSON Schema evaluator for release-v1 tests."""

from __future__ import annotations

import math
import re

from wf_release_v1.schema import compute_release_id


HEX_A = "a" * 64
HEX_B = "b" * 64
HEX_C = "c" * 64
HEX_D = "d" * 64
HEX_E = "e" * 64
RELEASE_ID_E = f"sha256:{HEX_E}"

SHA256_PATTERN = r"^[0-9a-f]{64}(?![\s\S])"
RELEASE_ID_PATTERN = r"^sha256:[0-9a-f]{64}(?![\s\S])"
DOTTED_VERSION_PATTERN = (
    r"^(?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*))+(?![\s\S])"
)
CAPABILITY_PATTERN = r"^[a-z0-9][a-z0-9._-]*@[1-9][0-9]*(?![\s\S])"
PAYLOAD_PATH_PATTERN = (
    r"^(?!.*\\)(?!.*[\u0000-\u001F\u007F])(?!.*//)"
    r"(?!.*(?:^|/)(?:\.|\.\.)(?:/|(?![\s\S])))"
    r"(?:content|server|modes)/[^/]+(?:/[^/]+)*(?![\s\S])"
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


def replace_at_path(
    value: dict[str, object],
    path: tuple[object, ...],
    replacement: object,
) -> None:
    cursor: object = value
    for part in path[:-1]:
        cursor = cursor[part]  # type: ignore[index]
    cursor[path[-1]] = replacement  # type: ignore[index]


class SchemaDefinitionError(AssertionError):
    """The evaluator encountered unsupported or malformed schema syntax."""


class Draft202012Subset:
    """Execute exactly the JSON Schema subset used by the Task 2 schemas."""

    KEYWORDS = frozenset(
        {
            "$schema",
            "$id",
            "$comment",
            "$defs",
            "title",
            "type",
            "additionalProperties",
            "required",
            "properties",
            "const",
            "pattern",
            "minLength",
            "minimum",
            "minItems",
            "uniqueItems",
            "items",
            "oneOf",
            "$ref",
        }
    )
    TYPES = frozenset({"object", "array", "string", "integer", "boolean", "null"})

    def __init__(self, schema: dict[str, object]) -> None:
        self.schema = schema
        self.used_keywords: set[str] = set()
        self._audit(schema)

    def _audit(self, node: object) -> None:
        if not isinstance(node, dict):
            raise SchemaDefinitionError("schema node must be an object")
        unknown = set(node) - self.KEYWORDS
        if unknown:
            raise SchemaDefinitionError(f"unsupported schema keywords: {sorted(unknown)}")
        self.used_keywords.update(node)
        if "$ref" in node:
            self._resolve(node["$ref"])
        if "type" in node and node["type"] not in self.TYPES:
            raise SchemaDefinitionError("unsupported schema type")
        if "pattern" in node:
            if not isinstance(node["pattern"], str):
                raise SchemaDefinitionError("pattern must be a string")
            re.compile(node["pattern"])
        for keyword in ("minLength", "minimum", "minItems"):
            if keyword in node and (
                type(node[keyword]) is not int or node[keyword] < 0
            ):
                raise SchemaDefinitionError(f"{keyword} must be a non-negative integer")
        if "additionalProperties" in node and type(node["additionalProperties"]) is not bool:
            raise SchemaDefinitionError("additionalProperties must be boolean")
        if "uniqueItems" in node and type(node["uniqueItems"]) is not bool:
            raise SchemaDefinitionError("uniqueItems must be boolean")
        if "required" in node and (
            not isinstance(node["required"], list)
            or any(not isinstance(key, str) for key in node["required"])
        ):
            raise SchemaDefinitionError("required must be a string array")
        for keyword in ("$defs", "properties"):
            if keyword in node:
                if not isinstance(node[keyword], dict):
                    raise SchemaDefinitionError(f"{keyword} must be an object")
                for child in node[keyword].values():
                    self._audit(child)
        if "items" in node:
            self._audit(node["items"])
        if "oneOf" in node:
            if not isinstance(node["oneOf"], list) or not node["oneOf"]:
                raise SchemaDefinitionError("oneOf must be a non-empty array")
            for child in node["oneOf"]:
                self._audit(child)

    def _resolve(self, reference: object) -> dict[str, object]:
        prefix = "#/$defs/"
        if not isinstance(reference, str) or not reference.startswith(prefix):
            raise SchemaDefinitionError("only local $defs references are supported")
        definitions = self.schema.get("$defs")
        name = reference[len(prefix) :]
        if not isinstance(definitions, dict) or name not in definitions:
            raise SchemaDefinitionError(f"unresolved schema reference: {reference}")
        target = definitions[name]
        if not isinstance(target, dict):
            raise SchemaDefinitionError("referenced schema must be an object")
        return target

    @staticmethod
    def _json_equal(left: object, right: object) -> bool:
        if isinstance(left, bool) or isinstance(right, bool):
            return type(left) is type(right) and left == right
        return left == right

    @staticmethod
    def _has_type(value: object, expected: str) -> bool:
        if expected == "object":
            return isinstance(value, dict)
        if expected == "array":
            return isinstance(value, list)
        if expected == "string":
            return isinstance(value, str)
        if expected == "integer":
            return (
                type(value) is int
                or type(value) is float
                and math.isfinite(value)
                and value.is_integer()
            )
        if expected == "boolean":
            return type(value) is bool
        return value is None

    def accepts(self, value: object) -> bool:
        return self._accept(self.schema, value)

    def _accept(self, node: dict[str, object], value: object) -> bool:
        if "$ref" in node and not self._accept(self._resolve(node["$ref"]), value):
            return False
        if "type" in node and not self._has_type(value, node["type"]):
            return False
        if "const" in node and not self._json_equal(value, node["const"]):
            return False
        if "pattern" in node and (
            not isinstance(value, str) or re.search(node["pattern"], value) is None
        ):
            return False
        if "minLength" in node and (
            not isinstance(value, str) or len(value) < node["minLength"]
        ):
            return False
        if "minimum" in node and (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or value < node["minimum"]
        ):
            return False
        if "oneOf" in node and sum(
            self._accept(child, value) for child in node["oneOf"]
        ) != 1:
            return False
        if isinstance(value, dict):
            required = node.get("required", [])
            if any(key not in value for key in required):
                return False
            properties = node.get("properties", {})
            if node.get("additionalProperties") is False and any(
                key not in properties for key in value
            ):
                return False
            if any(
                key in value and not self._accept(child, value[key])
                for key, child in properties.items()
            ):
                return False
        if isinstance(value, list):
            if "minItems" in node and len(value) < node["minItems"]:
                return False
            if node.get("uniqueItems") is True and any(
                self._json_equal(value[index], previous)
                for index in range(len(value))
                for previous in value[:index]
            ):
                return False
            if "items" in node and any(
                not self._accept(node["items"], item) for item in value
            ):
                return False
        return True
