"""Read-only discovery of one verified local wf-release-v1 target."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import stat
from typing import Final

from ._loopback_http import read_loopback_json
from .canonical import canonical_json_bytes, load_json_strict_bytes, normalize_relative_path
from .errors import ReleaseError

_MAX_MANIFEST_BYTES: Final = 16 * 1024 * 1024
_REPARSE_POINT_ATTRIBUTE: Final = 0x0400
_DIGEST: Final = re.compile(r"sha256:[0-9a-f]{64}")
_SEMVER: Final = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")
_DOTTED_VERSION: Final = re.compile(r"(?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*))+")
_CAPABILITY: Final = re.compile(r"[a-z0-9][a-z0-9._-]*@[1-9][0-9]*")
_PLATFORM: Final = re.compile(r"[a-z][a-z0-9-]*"); _ARCH: Final = re.compile(r"[a-z0-9_-]+")
_ABI: Final = re.compile(r"[0-9]+")
_SERVER_ENTRY, _LOCAL_PREPARE_ENTRY, _RUNTIME_ENTRY = "out/cn-server.js", "out/content/sync/entry.js", "node/bin/node"
@dataclass(frozen=True)
class ServerBundleFacts:
    version: str; bundle_id: str
    runtime_api: int; node_requirement: str
    dependency_lock: str; entry: str; local_prepare_entry: str
@dataclass(frozen=True)
class RuntimeFacts:
    runtime_id: str; runtime_api: int
    node_version: str; node_abi: str
    platform: str; arch: str
    dependency_lock: str; entry: str
@dataclass(frozen=True)
class ContentFacts:
    content_digest: str; cdn_target_version: str
    release_digest: str | None = None
@dataclass(frozen=True)
class ModeFacts:
    server_capabilities: tuple[str, ...]; mode_digest: str
@dataclass(frozen=True)
class FeatureFacts:
    patch_overlay_schema: int
@dataclass(frozen=True)
class TargetFacts:
    bundle_id: str; server_version: str; runtime_id: str
    runtime_api: int; dependency_lock: str
    node_version: str; node_abi: str; platform: str; arch: str
    capabilities: tuple[str, ...]; content_digest: str; cdn_target_version: str
    mode_digest: str; patch_overlay_schema: int
    release_digest: str | None = None
def _schema(label: str, message: str) -> ReleaseError:
    return ReleaseError("WFREL_SCHEMA_INVALID", message, {"label": label})
def _incompatible(label: str, message: str) -> ReleaseError:
    return ReleaseError("WFREL_REQUIRE_TARGET", message, {"label": label})
def _exact_object(value: object, keys: frozenset[str], label: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise _schema(label, "target object keys do not match the contract")
    return value
def _string(value: object, label: str, pattern: re.Pattern[str] | None = None) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value.startswith(("/", "\\"))
        or re.match(r"^[A-Za-z]:[\\/]", value)
        or (pattern and not pattern.fullmatch(value))
    ):
        raise _schema(label, "target string is invalid")
    return value
def _integer(value: object, label: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise _schema(label, "target integer is invalid")
    return value
def _constant(value: object, expected: int, label: str) -> int:
    parsed = _integer(value, label)
    if parsed != expected:
        raise _schema(label, "target contract version is unsupported")
    return parsed
def _boolean(value: object, label: str) -> bool:
    if type(value) is not bool:
        raise _schema(label, "target boolean is invalid")
    return value
def _string_array(value: object, label: str, *, pattern: re.Pattern[str] | None = None, sorted_values: bool = False, allow_empty: bool = True) -> tuple[str, ...]:
    if not isinstance(value, list) or (not allow_empty and not value):
        raise _schema(label, "target array is invalid")
    parsed = tuple(_string(item, f"{label}[]", pattern) for item in value)
    if len(set(parsed)) != len(parsed):
        raise _schema(label, "target array values must be unique")
    if sorted_values and parsed != tuple(sorted(parsed)):
        raise _schema(label, "target array values are not in canonical order")
    return parsed
def _version_key(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split("."))
def _snapshot(value: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns,
            stat.S_IFMT(value.st_mode),
            getattr(value, "st_file_attributes", 0) & _REPARSE_POINT_ATTRIBUTE)
def _read_manifest(path: Path, label: str) -> object:
    try:
        before_stat = path.lstat()
        before = _snapshot(before_stat)
        if not stat.S_ISREG(before_stat.st_mode) or before[-1]:
            raise _schema(label, "manifest must be a non-reparse regular file")
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
        descriptor = os.open(path, flags)
        try:
            opened = _snapshot(os.fstat(descriptor))
            if opened != before:
                raise _schema(label, "manifest changed before it was opened")
            with os.fdopen(descriptor, "rb", closefd=False) as reader:
                raw = reader.read(_MAX_MANIFEST_BYTES + 1)
            opened_after = _snapshot(os.fstat(descriptor))
        finally:
            os.close(descriptor)
        after = _snapshot(path.lstat())
    except ReleaseError:
        raise
    except OSError as error:
        raise _incompatible(label, "target manifest is unavailable") from error
    if len(raw) > _MAX_MANIFEST_BYTES:
        raise _schema(label, "target manifest exceeds the size limit")
    if len(raw) != before[2] or opened_after != before or after != before:
        raise _schema(label, "target manifest changed while it was read")
    value = load_json_strict_bytes(raw, label=label)
    if canonical_json_bytes(value) != raw:
        raise _schema(label, "target manifest is not canonical JSON")
    return value
def _manifest_identity(value: dict[str, object], field: str) -> str:
    body = dict(value)
    del body[field]
    return f"sha256:{hashlib.sha256(canonical_json_bytes(body)).hexdigest()}"
def _declared_files(value: object, root: Path, label: str,
                    allowed: tuple[str, ...]) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise _schema(label, "manifest files must be a non-empty array")
    paths: list[str] = []
    for raw in value:
        entry = _exact_object(raw, frozenset({"path", "bytes", "sha256"}), f"{label}[]")
        path = _string(entry["path"], f"{label}[].path")
        try:
            normalize_relative_path(path)
        except ReleaseError as error:
            raise _schema(f"{label}[].path", "manifest file path is invalid") from error
        if not any(path == prefix or path.startswith(prefix + "/") for prefix in allowed):
            raise _schema(f"{label}[].path", "manifest file path is outside the allowed roots")
        expected_size = _integer(entry["bytes"], f"{label}[].bytes")
        expected_digest = _string(entry["sha256"], f"{label}[].sha256", re.compile(r"[0-9a-f]{64}"))
        file_path = root.joinpath(*path.split("/"))
        try:
            before_stat = file_path.lstat()
            before = _snapshot(before_stat)
            if not stat.S_ISREG(before_stat.st_mode) or before[-1]:
                raise OSError("declared target file is not regular")
            digest = hashlib.sha256()
            with file_path.open("rb") as reader:
                if _snapshot(os.fstat(reader.fileno())) != before:
                    raise OSError("declared target file changed before open")
                while chunk := reader.read(1024 * 1024):
                    digest.update(chunk)
                opened_after = _snapshot(os.fstat(reader.fileno()))
            after = _snapshot(file_path.lstat())
        except OSError as error:
            raise _schema(f"{label}[].path", "declared target file is unavailable") from error
        if opened_after != before or after != before:
            raise _schema(f"{label}[].path", "declared target file changed while read")
        if before[2] != expected_size or digest.hexdigest() != expected_digest:
            raise _schema(f"{label}[]", "declared target file identity does not match")
        paths.append(path)
    if len(set(paths)) != len(paths) or paths != sorted(paths, key=lambda item: item.encode("utf-8")):
        raise _schema(label, "manifest files must be unique and canonically ordered")
    manifest_name = "server-manifest.json" if label.startswith("server") else "runtime-pack-manifest.json"
    actual: set[str] = set()
    pending = [root]
    try:
        while pending:
            with os.scandir(pending.pop()) as entries:
                for entry in entries:
                    candidate = Path(entry.path)
                    metadata = entry.stat(follow_symlinks=False)
                    if _snapshot(metadata)[-1] or not (stat.S_ISDIR(metadata.st_mode) or stat.S_ISREG(metadata.st_mode)):
                        raise OSError("target tree contains a reparse point or special file")
                    if stat.S_ISDIR(metadata.st_mode):
                        pending.append(candidate)
                    else:
                        actual.add(candidate.relative_to(root).as_posix())
    except OSError as error:
        raise _schema(label, "target file collection is unavailable") from error
    if actual != set(paths) | {manifest_name}:
        raise _schema(label, "target file collection does not match the manifest")
    return tuple(paths)
def _read_capabilities(url: str, timeout_seconds: float) -> object:
    return read_loopback_json(
        url,
        timeout_seconds,
        expected_path="/api/server/capabilities",
        label="capabilities",
    )
def _parse_server_manifest(value: object, root: Path) -> ServerBundleFacts:
    item = _exact_object(value, frozenset({"schemaVersion", "name", "serverVersion", "bundleId",
        "entry", "startup", "requires", "admin", "assets", "ports", "files"}), "serverManifest")
    _constant(item["schemaVersion"], 3, "serverManifest.schemaVersion")
    if item["name"] != "starpoint-cn" or (entry := _string(item["entry"], "serverManifest.entry")) != _SERVER_ENTRY:
        raise _schema("serverManifest", "server manifest identity is invalid")
    startup = _exact_object(item["startup"], frozenset({"localPrepareEntry"}), "serverManifest.startup")
    if (prepare_entry := _string(startup["localPrepareEntry"],
                                 "serverManifest.startup.localPrepareEntry")) != _LOCAL_PREPARE_ENTRY:
        raise _schema("serverManifest.startup", "server startup entry is invalid")
    requires = _exact_object(item["requires"], frozenset({"runtimeApi", "node", "dependencyLock",
        "minDataSchema", "targetDataSchema"}), "serverManifest.requires")
    assets = _exact_object(item["assets"], frozenset({"supportedModes", "minClientAssetVersion"}),
                           "serverManifest.assets")
    admin = _exact_object(item["admin"], frozenset({"path", "required"}), "serverManifest.admin")
    ports = _exact_object(item["ports"], frozenset({"http", "tcp"}), "serverManifest.ports")
    if admin != {"path": "web/dist", "required": True}:
        raise _schema("serverManifest.admin", "server admin contract is invalid")
    for name in ("http", "tcp"):
        port = _integer(ports[name], f"serverManifest.ports.{name}", minimum=1)
        if port > 65535:
            raise _schema(f"serverManifest.ports.{name}", "server port is invalid")
    files = _declared_files(item["files"], root, "serverManifest.files", ("out", "assets", "web/dist", "LICENSE", "NOTICE"))
    if not {_SERVER_ENTRY, _LOCAL_PREPARE_ENTRY, "web/dist/index.html"}.issubset(files):
        raise _schema("serverManifest.files", "server manifest omits a required entry")
    if item["bundleId"] is None:
        raise _incompatible("serverManifest.bundleId", "managed target requires an embedded server bundle identity")
    if item["bundleId"] != _manifest_identity(item, "bundleId"):
        raise _schema("serverManifest.bundleId", "server bundle identity does not match")
    node_requirement = _string(requires["node"], "serverManifest.requires.node")
    if not re.fullmatch(r">=(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", node_requirement):
        raise _schema("serverManifest.requires.node", "Node requirement is invalid")
    _integer(requires["minDataSchema"], "serverManifest.requires.minDataSchema")
    _integer(requires["targetDataSchema"], "serverManifest.requires.targetDataSchema")
    _string_array(assets["supportedModes"], "serverManifest.assets.supportedModes", sorted_values=True, allow_empty=False)
    _string(assets["minClientAssetVersion"], "serverManifest.assets.minClientAssetVersion", _DOTTED_VERSION)
    return ServerBundleFacts(
        version=_string(item["serverVersion"], "serverManifest.serverVersion", _SEMVER),
        bundle_id=_string(item["bundleId"], "serverManifest.bundleId", _DIGEST),
        runtime_api=_constant(requires["runtimeApi"], 1, "serverManifest.requires.runtimeApi"),
        node_requirement=node_requirement,
        dependency_lock=_string(requires["dependencyLock"], "serverManifest.requires.dependencyLock", _DIGEST),
        entry=entry, local_prepare_entry=prepare_entry,
    )

def _parse_runtime_manifest(value: object, root: Path) -> RuntimeFacts:
    item = _exact_object(value, frozenset({"schemaVersion", "runtimeId", "runtimeApi", "node",
        "dependencyLock", "entry", "executables", "files"}), "runtimeManifest")
    _constant(item["schemaVersion"], 1, "runtimeManifest.schemaVersion")
    node = _exact_object(item["node"], frozenset({"version", "abi", "platform", "arch"}), "runtimeManifest.node")
    if (entry := _string(item["entry"], "runtimeManifest.entry")) != _RUNTIME_ENTRY:
        raise _schema("runtimeManifest", "runtime manifest layout is invalid")
    executables = _string_array(item["executables"], "runtimeManifest.executables", sorted_values=True, allow_empty=False)
    if _RUNTIME_ENTRY not in executables:
        raise _schema("runtimeManifest.executables", "runtime entry is not executable")
    _declared_files(item["files"], root, "runtimeManifest.files", ("node", "node_modules"))
    if item["runtimeId"] != _manifest_identity(item, "runtimeId"):
        raise _schema("runtimeManifest.runtimeId", "runtime pack identity does not match")
    return RuntimeFacts(
        runtime_id=_string(item["runtimeId"], "runtimeManifest.runtimeId", _DIGEST),
        runtime_api=_constant(item["runtimeApi"], 1, "runtimeManifest.runtimeApi"),
        node_version=_string(node["version"], "runtimeManifest.node.version", _SEMVER),
        node_abi=_string(node["abi"], "runtimeManifest.node.abi", _ABI),
        platform=_string(node["platform"], "runtimeManifest.node.platform", _PLATFORM),
        arch=_string(node["arch"], "runtimeManifest.node.arch", _ARCH),
        dependency_lock=_string(item["dependencyLock"], "runtimeManifest.dependencyLock", _DIGEST), entry=entry,
    )

def _parse_capabilities(value: object) -> tuple[
        str, str, int, str, str, str, str, tuple[str, ...], ContentFacts, ModeFacts, FeatureFacts]:
    item = _exact_object(value, frozenset({"contractVersion", "serverCapabilities", "serverBundle",
        "runtime", "content", "modes", "features"}), "capabilities")
    _constant(item["contractVersion"], 1, "capabilities.contractVersion")
    server_bundle = _exact_object(item["serverBundle"], frozenset({"version", "bundleId"}), "capabilities.serverBundle")
    runtime = _exact_object(item["runtime"], frozenset({"api", "node", "nodeAbi", "platform", "arch"}), "capabilities.runtime")
    content = _exact_object(item["content"], frozenset({"source", "assetVersion", "generatorVersion",
        "releaseDigest", "contentDigest", "cdnTargetVersion", "patchVersions"}), "capabilities.content")
    modes = _exact_object(item["modes"], frozenset({"api", "serverCapabilities", "loaded", "modeDigest"}), "capabilities.modes")
    features = _exact_object(item["features"], frozenset({"patchOverlaySchema",
        "modeChangesRequireRestart", "activeContentManagement"}), "capabilities.features")
    general = _string_array(item["serverCapabilities"], "capabilities.serverCapabilities", pattern=_CAPABILITY, sorted_values=True, allow_empty=False)
    _string(content["assetVersion"], "capabilities.content.assetVersion", _DOTTED_VERSION)
    _integer(content["generatorVersion"], "capabilities.content.generatorVersion", minimum=1)
    patch_versions = _string_array(content["patchVersions"], "capabilities.content.patchVersions", pattern=_DOTTED_VERSION)
    if patch_versions != tuple(sorted(patch_versions, key=_version_key)):
        raise _schema("capabilities.content.patchVersions", "patch versions are not in canonical order")
    loaded_raw = modes["loaded"]
    if not isinstance(loaded_raw, list):
        raise _schema("capabilities.modes.loaded", "loaded modes must be an array")
    _constant(modes["api"], 1, "capabilities.modes.api")
    for raw in loaded_raw:
        entry = _exact_object(raw, frozenset({"name", "capabilities", "sha256"}), "capabilities.modes.loaded[]")
        _string(entry["name"], "capabilities.modes.loaded[].name")
        _string_array(entry["capabilities"], "capabilities.modes.loaded[].capabilities", pattern=_CAPABILITY)
        _string(entry["sha256"], "capabilities.modes.loaded[].sha256", re.compile(r"[0-9a-f]{64}"))
    raw_release_digest = content["releaseDigest"]
    release_digest = None if raw_release_digest is None else _string(
        raw_release_digest, "capabilities.content.releaseDigest", _DIGEST
    )
    source = _string(content["source"], "capabilities.content.source")
    if source not in {"bundled", "release"}:
        raise _schema("capabilities.content.source", "content source is unsupported")
    if (source == "bundled") != (release_digest is None):
        raise _schema("capabilities.content.releaseDigest", "content source and release digest disagree")
    restart = _boolean(features["modeChangesRequireRestart"], "capabilities.features.modeChangesRequireRestart")
    active_management = _boolean(features["activeContentManagement"], "capabilities.features.activeContentManagement")
    if not restart or active_management:
        raise _schema("capabilities.features", "capabilities feature constants are unsupported")
    return (
        _string(server_bundle["version"], "capabilities.serverBundle.version", _SEMVER),
        _string(server_bundle["bundleId"], "capabilities.serverBundle.bundleId", _DIGEST),
        _constant(runtime["api"], 1, "capabilities.runtime.api"),
        _string(runtime["node"], "capabilities.runtime.node", _SEMVER),
        _string(runtime["nodeAbi"], "capabilities.runtime.nodeAbi", _ABI),
        _string(runtime["platform"], "capabilities.runtime.platform", _PLATFORM),
        _string(runtime["arch"], "capabilities.runtime.arch", _ARCH),
        general,
        ContentFacts(
            content_digest=_string(content["contentDigest"], "capabilities.content.contentDigest", _DIGEST),
            cdn_target_version=_string(content["cdnTargetVersion"], "capabilities.content.cdnTargetVersion", _DOTTED_VERSION),
            release_digest=release_digest,
        ),
        ModeFacts(
            server_capabilities=_string_array(modes["serverCapabilities"], "capabilities.modes.serverCapabilities", pattern=_CAPABILITY),
            mode_digest=_string(modes["modeDigest"], "capabilities.modes.modeDigest", _DIGEST),
        ),
        FeatureFacts(
            patch_overlay_schema=_constant(features["patchOverlaySchema"], 1, "capabilities.features.patchOverlaySchema"),
        ),
    )

def _node_tuple(value: str) -> tuple[int, int, int]:
    match = _SEMVER.fullmatch(value)
    if match is None:
        raise _schema("nodeVersion", "Node version is invalid")
    return tuple(int(part) for part in match.groups())

@dataclass(frozen=True)
class TargetProbe:
    server_manifest: Path
    runtime_manifest: Path
    capabilities_url: str
    timeout_seconds: float = 5.0

    def manifest_facts(self) -> tuple[ServerBundleFacts, RuntimeFacts]:
        paths = Path(self.server_manifest), Path(self.runtime_manifest)
        return (_parse_server_manifest(_read_manifest(paths[0], "serverManifest"), paths[0].parent), _parse_runtime_manifest(_read_manifest(paths[1], "runtimeManifest"), paths[1].parent))

    def _live_capabilities(self):
        live = _parse_capabilities(
            _read_capabilities(self.capabilities_url, self.timeout_seconds)
        )
        server_capabilities = live[7]
        modes = live[9]
        if not set(modes.server_capabilities).issubset(server_capabilities):
            raise _schema(
                "capabilities.serverCapabilities",
                "general capabilities omit Mode capabilities",
            )
        if "content.sync@1" not in server_capabilities:
            raise _schema(
                "capabilities.serverCapabilities",
                "general capabilities omit Content Sync",
            )
        return live

    def validate_live_capabilities(self) -> None:
        """Validate the live v1 contract without reading local bundle manifests."""
        self._live_capabilities()

    def run(self) -> TargetFacts:
        server, runtime = self.manifest_facts()
        live = self._live_capabilities()
        (
            live_version, live_bundle_id, live_runtime_api, live_node, live_abi,
            live_platform, live_arch, server_capabilities, content, modes, features,
        ) = live
        comparisons = (
            (server.version, live_version, "serverBundle.version"),
            (server.bundle_id, live_bundle_id, "serverBundle.bundleId"),
            (server.runtime_api, runtime.runtime_api, "runtime.runtimeApi"), (runtime.runtime_api, live_runtime_api, "runtime.api"),
            (server.dependency_lock, runtime.dependency_lock, "runtime.dependencyLock"),
            (runtime.node_version, live_node, "runtime.node"), (runtime.node_abi, live_abi, "runtime.nodeAbi"),
            (runtime.platform, live_platform, "runtime.platform"), (runtime.arch, live_arch, "runtime.arch"),
        )
        for expected, actual, label in comparisons:
            if expected != actual:
                raise _incompatible(label, "target authorities disagree")
        required_node = server.node_requirement.removeprefix(">=")
        if _node_tuple(runtime.node_version) < _node_tuple(required_node):
            raise _incompatible("runtime.node", "Runtime Pack does not meet the server requirement")
        return TargetFacts(
            bundle_id=server.bundle_id, server_version=server.version, runtime_id=runtime.runtime_id,
            runtime_api=runtime.runtime_api, dependency_lock=runtime.dependency_lock,
            node_version=runtime.node_version, node_abi=runtime.node_abi,
            platform=runtime.platform, arch=runtime.arch,
            capabilities=server_capabilities,
            content_digest=content.content_digest, cdn_target_version=content.cdn_target_version,
            mode_digest=modes.mode_digest, patch_overlay_schema=features.patch_overlay_schema,
            release_digest=content.release_digest,
        )
