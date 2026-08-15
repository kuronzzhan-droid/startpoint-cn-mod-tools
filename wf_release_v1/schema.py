"""Immutable models and strict parsers for the release-v1 wire contracts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import re
from typing import Final

from wf_character_pack import logical_path_problem, windows_logical_path_key

from .canonical import canonical_json_bytes, normalize_relative_path
from .errors import ReleaseError


_HEX_PATTERN: Final = re.compile(r"[0-9a-f]{64}")
_RELEASE_ID_PATTERN: Final = re.compile(r"sha256:[0-9a-f]{64}")
_DOTTED_VERSION_PATTERN: Final = re.compile(
    r"(?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*))+"
)
_SEMVER_PATTERN: Final = re.compile(
    r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
)
_NAME_PATTERN: Final = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_CAPABILITY_PATTERN: Final = re.compile(r"[a-z0-9][a-z0-9._-]*@[1-9][0-9]*")
_OWNERSHIP_KEY_PATTERN: Final = re.compile(r"[a-z][a-z0-9._-]*:[^\s:]+")
_COMPONENT_KINDS: Final = frozenset({"content", "server", "modes"})
_ASSET_ROOTS: Final = frozenset({"common", "medium", "android"})
_ASSET_REPLACEMENT_KEYS: Final = frozenset(
    {"root", "logicalPath", "beforeSha256", "beforeSize"}
)
_RELEASE_KEYS: Final = frozenset(
    {
        "schemaVersion",
        "name",
        "version",
        "producer",
        "replaces",
        "sourceEvidence",
        "components",
        "expectedState",
        "metadataSha256",
        "files",
        "releaseId",
    }
)
_RELEASE_BODY_KEYS: Final = _RELEASE_KEYS - {"releaseId"}
_REQUIREMENT_KEYS: Final = frozenset(
    {
        "schemaVersion",
        "runtimeApi",
        "serverCapabilities",
        "clientVersions",
        "resourceBaselines",
        "contentDigests",
        "patchOverlaySchema",
        "clientPatchProfile",
    }
)
_OWNERSHIP_KEYS: Final = frozenset({"schemaVersion", "entities", "records", "paths"})


def _invalid(label: str, message: str) -> ReleaseError:
    return ReleaseError("WFREL_SCHEMA_INVALID", message, {"label": label})


def _exact_object(value: object, keys: frozenset[str], label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value.keys()) != keys:
        raise _invalid(label, "object keys do not match the v1 contract")
    return value


def _integer(value: object, label: str, *, minimum: int | None = None) -> int:
    if type(value) is not int or (minimum is not None and value < minimum):
        raise _invalid(label, "value must be an integer in range")
    return value


def _constant_integer(value: object, expected: int, label: str) -> int:
    parsed = _integer(value, label)
    if parsed != expected:
        raise _invalid(label, "integer version is not supported")
    return parsed


def _string(
    value: object,
    label: str,
    *,
    pattern: re.Pattern[str] | None = None,
) -> str:
    if not isinstance(value, str) or not value or (pattern and not pattern.fullmatch(value)):
        raise _invalid(label, "value must be a valid non-empty string")
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeEncodeError as error:
        raise _invalid(label, "value must contain only Unicode scalar values") from error
    return value


def _boolean(value: object, label: str) -> bool:
    if type(value) is not bool:
        raise _invalid(label, "value must be a boolean")
    return value


def _ordered_unique_strings(
    value: object,
    label: str,
    *,
    pattern: re.Pattern[str] | None = None,
    allow_empty: bool = False,
) -> tuple[str, ...]:
    if not isinstance(value, list) or (not allow_empty and not value):
        raise _invalid(label, "value must be a non-empty array")
    parsed = tuple(
        _string(item, f"{label}[]", pattern=pattern)
        for item in value
    )
    if len(set(parsed)) != len(parsed):
        raise _invalid(label, "array values must be unique")
    if parsed != tuple(sorted(parsed, key=lambda item: item.encode("utf-8"))):
        raise _invalid(label, "array values must use UTF-8 byte order")
    return parsed


def _sha256(value: object, label: str) -> str:
    return _string(value, label, pattern=_HEX_PATTERN)


def _release_id(value: object, label: str) -> str:
    return _string(value, label, pattern=_RELEASE_ID_PATTERN)


@dataclass(frozen=True)
class ProducerIdentity:
    name: str
    version: str

    def to_wire(self) -> dict[str, object]:
        return {"name": self.name, "version": self.version}


@dataclass(frozen=True)
class AssetReplacement:
    root: str
    logical_path: str
    before_sha256: str
    before_size: int

    def to_wire(self) -> dict[str, object]:
        return {
            "root": self.root,
            "logicalPath": self.logical_path,
            "beforeSha256": self.before_sha256,
            "beforeSize": self.before_size,
        }


@dataclass(frozen=True)
class SourceEvidence:
    kind: str
    workspace_input_sha256: str
    accepted_asset_replacements: tuple[AssetReplacement, ...] = ()

    def to_wire(self) -> dict[str, object]:
        value: dict[str, object] = {
            "kind": self.kind,
            "workspaceInputSha256": self.workspace_input_sha256,
        }
        if self.kind == "character-workspace-v2":
            value["acceptedAssetReplacements"] = [
                item.to_wire() for item in self.accepted_asset_replacements
            ]
        return value


@dataclass(frozen=True)
class ReleaseComponent:
    kind: str
    root: str

    def to_wire(self) -> dict[str, object]:
        return {"kind": self.kind, "root": self.root}


@dataclass(frozen=True)
class ExpectedState:
    cdn_target_version: str
    content_digest: str | None
    mode_digest: str | None

    def to_wire(self) -> dict[str, object]:
        return {
            "cdnTargetVersion": self.cdn_target_version,
            "contentDigest": self.content_digest,
            "modeDigest": self.mode_digest,
        }


@dataclass(frozen=True)
class MetadataSha256:
    requires: str
    ownership: str

    def to_wire(self) -> dict[str, object]:
        return {"requires": self.requires, "ownership": self.ownership}


@dataclass(frozen=True)
class ReleaseFile:
    path: str
    size: int
    sha256: str

    def to_wire(self) -> dict[str, object]:
        return {"path": self.path, "size": self.size, "sha256": self.sha256}


@dataclass(frozen=True)
class ReleaseManifest:
    schema_version: int
    name: str
    version: str
    producer: ProducerIdentity
    replaces: tuple[str, ...]
    source_evidence: SourceEvidence
    components: tuple[ReleaseComponent, ...]
    expected_state: ExpectedState
    metadata_sha256: MetadataSha256
    files: tuple[ReleaseFile, ...]
    release_id: str

    def to_wire(self) -> dict[str, object]:
        value = _release_body_to_wire(self)
        value["releaseId"] = self.release_id
        return value


@dataclass(frozen=True)
class ReleaseRequirements:
    schema_version: int
    runtime_api: int
    server_capabilities: tuple[str, ...]
    client_versions: tuple[str, ...]
    resource_baselines: tuple[str, ...]
    content_digests: tuple[str, ...]
    patch_overlay_schema: int
    client_patch_profile: bool

    def to_wire(self) -> dict[str, object]:
        return {
            "schemaVersion": self.schema_version,
            "runtimeApi": self.runtime_api,
            "serverCapabilities": list(self.server_capabilities),
            "clientVersions": list(self.client_versions),
            "resourceBaselines": list(self.resource_baselines),
            "contentDigests": list(self.content_digests),
            "patchOverlaySchema": self.patch_overlay_schema,
            "clientPatchProfile": self.client_patch_profile,
        }


@dataclass(frozen=True)
class OwnershipManifest:
    schema_version: int
    entities: tuple[str, ...]
    records: tuple[str, ...]
    paths: tuple[str, ...]

    def to_wire(self) -> dict[str, object]:
        return {
            "schemaVersion": self.schema_version,
            "entities": list(self.entities),
            "records": list(self.records),
            "paths": list(self.paths),
        }


def _parse_producer(value: object) -> ProducerIdentity:
    item = _exact_object(value, frozenset({"name", "version"}), "producer")
    return ProducerIdentity(
        name=_string(item["name"], "producer.name"),
        version=_string(item["version"], "producer.version"),
    )


def _portable_asset_path(value: object, label: str) -> str:
    raw = _string(value, label)
    try:
        path = normalize_relative_path(raw)
    except ReleaseError as error:
        raise _invalid(label, "asset path is not canonical") from error
    if logical_path_problem(path) is not None:
        raise _invalid(label, "asset path is not portable")
    folded = path.casefold()
    if folded.startswith("master/") or folded.endswith((".orderedmap", ".json")):
        raise _invalid(label, "table paths cannot be accepted asset replacements")
    return path


def parse_asset_replacements(value: object) -> tuple[AssetReplacement, ...]:
    label = "sourceEvidence.acceptedAssetReplacements"
    if not isinstance(value, list) or not value:
        raise _invalid(label, "accepted asset replacements must be a non-empty array")
    parsed: list[AssetReplacement] = []
    windows_seen: set[tuple[str, str]] = set()
    for index, raw in enumerate(value):
        item_label = f"{label}[{index}]"
        item = _exact_object(raw, _ASSET_REPLACEMENT_KEYS, item_label)
        root = _string(item["root"], f"{item_label}.root")
        if root not in _ASSET_ROOTS:
            raise _invalid(f"{item_label}.root", "asset root is not supported")
        logical_path = _portable_asset_path(
            item["logicalPath"], f"{item_label}.logicalPath"
        )
        alias = (root, windows_logical_path_key(logical_path))
        if alias in windows_seen:
            raise _invalid(label, "asset paths contain a Windows-equivalent duplicate")
        windows_seen.add(alias)
        parsed.append(AssetReplacement(
            root=root,
            logical_path=logical_path,
            before_sha256=_sha256(
                item["beforeSha256"], f"{item_label}.beforeSha256"
            ),
            before_size=_integer(
                item["beforeSize"], f"{item_label}.beforeSize", minimum=0
            ),
        ))
    ordered = tuple(sorted(
        parsed,
        key=lambda item: (item.root.encode("utf-8"), item.logical_path.encode("utf-8")),
    ))
    if tuple(parsed) != ordered:
        raise _invalid(label, "accepted asset replacements are not canonically ordered")
    return ordered


def _parse_source_evidence(value: object) -> SourceEvidence:
    if not isinstance(value, Mapping):
        raise _invalid("sourceEvidence", "source evidence must be an object")
    kind = _string(value.get("kind"), "sourceEvidence.kind")
    if kind == "character-workspace-v1":
        item = _exact_object(
            value,
            frozenset({"kind", "workspaceInputSha256"}),
            "sourceEvidence",
        )
        replacements: tuple[AssetReplacement, ...] = ()
    elif kind == "character-workspace-v2":
        item = _exact_object(
            value,
            frozenset({
                "kind", "workspaceInputSha256", "acceptedAssetReplacements"
            }),
            "sourceEvidence",
        )
        replacements = parse_asset_replacements(item["acceptedAssetReplacements"])
    else:
        raise _invalid("sourceEvidence.kind", "source evidence kind is not supported")
    return SourceEvidence(
        kind=kind,
        workspace_input_sha256=_sha256(
            item["workspaceInputSha256"], "sourceEvidence.workspaceInputSha256"
        ),
        accepted_asset_replacements=replacements,
    )


def _parse_components(value: object) -> tuple[ReleaseComponent, ...]:
    if not isinstance(value, list) or not value:
        raise _invalid("components", "components must be a non-empty array")
    components: list[ReleaseComponent] = []
    for raw in value:
        item = _exact_object(raw, frozenset({"kind", "root"}), "components[]")
        kind = _string(item["kind"], "components[].kind")
        root = _string(item["root"], "components[].root")
        if kind not in _COMPONENT_KINDS or root != kind:
            raise _invalid("components[]", "component root must equal a supported kind")
        components.append(ReleaseComponent(kind=kind, root=root))
    kinds = tuple(component.kind for component in components)
    if len(set(kinds)) != len(kinds):
        raise _invalid("components", "component kinds must be unique")
    if kinds != tuple(sorted(kinds, key=lambda item: item.encode("utf-8"))):
        raise _invalid("components", "components must use UTF-8 byte order")
    return tuple(components)


def _optional_digest(value: object, label: str) -> str | None:
    if value is None:
        return None
    return _release_id(value, label)


def _parse_expected_state(value: object) -> ExpectedState:
    item = _exact_object(
        value,
        frozenset({"cdnTargetVersion", "contentDigest", "modeDigest"}),
        "expectedState",
    )
    return ExpectedState(
        cdn_target_version=_string(
            item["cdnTargetVersion"],
            "expectedState.cdnTargetVersion",
            pattern=_DOTTED_VERSION_PATTERN,
        ),
        content_digest=_optional_digest(
            item["contentDigest"], "expectedState.contentDigest"
        ),
        mode_digest=_optional_digest(item["modeDigest"], "expectedState.modeDigest"),
    )


def _parse_metadata_sha256(value: object) -> MetadataSha256:
    item = _exact_object(
        value, frozenset({"requires", "ownership"}), "metadataSha256"
    )
    return MetadataSha256(
        requires=_sha256(item["requires"], "metadataSha256.requires"),
        ownership=_sha256(item["ownership"], "metadataSha256.ownership"),
    )


def _parse_files(value: object, component_kinds: frozenset[str]) -> tuple[ReleaseFile, ...]:
    if not isinstance(value, list) or not value:
        raise _invalid("files", "files must be a non-empty array")
    files: list[ReleaseFile] = []
    for raw in value:
        item = _exact_object(raw, frozenset({"path", "size", "sha256"}), "files[]")
        raw_path = _string(item["path"], "files[].path")
        try:
            path = normalize_relative_path(raw_path)
        except ReleaseError as error:
            raise _invalid("files[].path", "file path is not canonical") from error
        parts = path.split("/", 1)
        if len(parts) != 2 or parts[0] not in _COMPONENT_KINDS:
            raise _invalid("files[].path", "file must be under a payload component")
        if parts[0] not in component_kinds:
            raise _invalid("files[].path", "file component is not declared")
        files.append(
            ReleaseFile(
                path=path,
                size=_integer(item["size"], "files[].size", minimum=0),
                sha256=_sha256(item["sha256"], "files[].sha256"),
            )
        )
    paths = tuple(item.path for item in files)
    if len(set(paths)) != len(paths):
        raise _invalid("files", "file paths must be unique")
    if paths != tuple(sorted(paths, key=lambda item: item.encode("utf-8"))):
        raise _invalid("files", "files must use UTF-8 byte path order")
    return tuple(files)


def _parse_release_body(value: object) -> dict[str, object]:
    item = _exact_object(value, _RELEASE_BODY_KEYS, "release-manifest")
    components = _parse_components(item["components"])
    component_kinds = frozenset(component.kind for component in components)
    files = _parse_files(item["files"], component_kinds)
    populated_kinds = frozenset(file.path.split("/", 1)[0] for file in files)
    if populated_kinds != component_kinds:
        raise _invalid("components", "each declared component must contain a payload file")
    return {
        "schema_version": _constant_integer(item["schemaVersion"], 1, "schemaVersion"),
        "name": _string(item["name"], "name", pattern=_NAME_PATTERN),
        "version": _string(item["version"], "version", pattern=_SEMVER_PATTERN),
        "producer": _parse_producer(item["producer"]),
        "replaces": _ordered_unique_strings(
            item["replaces"], "replaces", pattern=_RELEASE_ID_PATTERN, allow_empty=True
        ),
        "source_evidence": _parse_source_evidence(item["sourceEvidence"]),
        "components": components,
        "expected_state": _parse_expected_state(item["expectedState"]),
        "metadata_sha256": _parse_metadata_sha256(item["metadataSha256"]),
        "files": files,
    }


def _release_body_to_wire(manifest: ReleaseManifest) -> dict[str, object]:
    return {
        "schemaVersion": manifest.schema_version,
        "name": manifest.name,
        "version": manifest.version,
        "producer": manifest.producer.to_wire(),
        "replaces": list(manifest.replaces),
        "sourceEvidence": manifest.source_evidence.to_wire(),
        "components": [component.to_wire() for component in manifest.components],
        "expectedState": manifest.expected_state.to_wire(),
        "metadataSha256": manifest.metadata_sha256.to_wire(),
        "files": [item.to_wire() for item in manifest.files],
    }


def parse_release_manifest(value: object) -> ReleaseManifest:
    """Parse an exact release-manifest v1 object into detached frozen values."""
    item = _exact_object(value, _RELEASE_KEYS, "release-manifest")
    body_input = {key: item[key] for key in _RELEASE_BODY_KEYS}
    fields = _parse_release_body(body_input)
    release_id = _release_id(item["releaseId"], "releaseId")
    if release_id in fields["replaces"]:
        raise _invalid("replaces", "a release cannot replace itself")
    return ReleaseManifest(**fields, release_id=release_id)  # type: ignore[arg-type]


def parse_requirements(value: object) -> ReleaseRequirements:
    """Parse exact requires.json v1 values."""
    item = _exact_object(value, _REQUIREMENT_KEYS, "requires")
    return ReleaseRequirements(
        schema_version=_constant_integer(item["schemaVersion"], 1, "schemaVersion"),
        runtime_api=_integer(item["runtimeApi"], "runtimeApi", minimum=1),
        server_capabilities=_ordered_unique_strings(
            item["serverCapabilities"],
            "serverCapabilities",
            pattern=_CAPABILITY_PATTERN,
        ),
        client_versions=_ordered_unique_strings(
            item["clientVersions"], "clientVersions", pattern=_DOTTED_VERSION_PATTERN
        ),
        resource_baselines=_ordered_unique_strings(
            item["resourceBaselines"],
            "resourceBaselines",
            pattern=_DOTTED_VERSION_PATTERN,
        ),
        content_digests=_ordered_unique_strings(
            item["contentDigests"], "contentDigests", pattern=_RELEASE_ID_PATTERN
        ),
        patch_overlay_schema=_integer(
            item["patchOverlaySchema"], "patchOverlaySchema", minimum=1
        ),
        client_patch_profile=_boolean(
            item["clientPatchProfile"], "clientPatchProfile"
        ),
    )


def parse_ownership(value: object) -> OwnershipManifest:
    """Parse exact ownership.json v1 values."""
    item = _exact_object(value, _OWNERSHIP_KEYS, "ownership")
    raw_paths = _ordered_unique_strings(item["paths"], "paths")
    paths: list[str] = []
    for raw_path in raw_paths:
        try:
            paths.append(normalize_relative_path(raw_path))
        except ReleaseError as error:
            raise _invalid("paths", "ownership path is not canonical") from error
    return OwnershipManifest(
        schema_version=_constant_integer(item["schemaVersion"], 1, "schemaVersion"),
        entities=_ordered_unique_strings(
            item["entities"], "entities", pattern=_OWNERSHIP_KEY_PATTERN
        ),
        records=_ordered_unique_strings(
            item["records"], "records", pattern=_OWNERSHIP_KEY_PATTERN
        ),
        paths=tuple(paths),
    )


def compute_release_id(manifest_without_release_id: Mapping[str, object]) -> str:
    """Hash the complete validated canonical manifest with releaseId removed."""
    fields = _parse_release_body(manifest_without_release_id)
    temporary = ReleaseManifest(
        **fields,
        release_id="sha256:" + "0" * 64,
    )  # type: ignore[arg-type]
    digest = hashlib.sha256(canonical_json_bytes(_release_body_to_wire(temporary))).hexdigest()
    return f"sha256:{digest}"


def verify_release_id(manifest: ReleaseManifest) -> None:
    """Raise when a parsed manifest's declared releaseId is not its identity."""
    wire = manifest.to_wire()
    del wire["releaseId"]
    expected = compute_release_id(wire)
    if manifest.release_id != expected:
        raise ReleaseError(
            "WFREL_HASH_MISMATCH",
            "releaseId does not match the canonical release manifest",
            {"label": "releaseId"},
        )
