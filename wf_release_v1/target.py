"""Strict host-local target configuration and validated launch entries."""

from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import os
from pathlib import Path
import re
import stat
from typing import Final
import unicodedata
from urllib.parse import urlsplit

from .canonical import load_json_strict_bytes
from .errors import ReleaseError
from .probe import TargetProbe


_MAX_TARGET_BYTES: Final = 64 * 1024
_REPARSE_POINT_ATTRIBUTE: Final = 0x0400
_TARGET_KEYS: Final = frozenset({
    "schemaVersion", "managedBy", "serverBundle", "runtimePack", "dataRoot",
    "stateRoot", "cdnRoot", "modesRoot", "componentRoots", "compatibility",
    "network", "serverUrl",
})
_COMPONENT_KEYS: Final = frozenset({"content", "server", "modes"})
_COMPATIBILITY_KEYS: Final = frozenset({
    "clientVersion", "resourceBaseline", "clientPatchProfile",
})
_NETWORK_KEYS: Final = frozenset({"publicHost"})
_DOTTED_VERSION: Final = re.compile(r"(?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*))+")
_TOOL_ROOT: Final = Path(__file__).resolve().parent.parent
_RFC1918: Final = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
)


def _invalid(message: str) -> ReleaseError:
    return ReleaseError("WFREL_REQUIRE_TARGET", message, {"label": "target"})


def _file_snapshot(item: os.stat_result) -> tuple[int, int, int, int, bool, bool]:
    return (
        item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns,
        stat.S_ISREG(item.st_mode),
        bool(getattr(item, "st_file_attributes", 0) & _REPARSE_POINT_ATTRIBUTE),
    )


def _read_target(source: Path) -> object:
    if not isinstance(source, Path):
        raise _invalid("target configuration path is invalid")
    try:
        before = _file_snapshot(source.lstat())
        if not before[4] or before[5] or before[2] > _MAX_TARGET_BYTES:
            raise _invalid("target configuration is unavailable")
        with source.open("rb") as reader:
            opened = _file_snapshot(os.fstat(reader.fileno()))
            if opened != before:
                raise _invalid("target configuration changed while it was opened")
            raw = reader.read(_MAX_TARGET_BYTES + 1)
            opened_after = _file_snapshot(os.fstat(reader.fileno()))
        after = _file_snapshot(source.lstat())
    except ReleaseError:
        raise
    except (OSError, ValueError):
        raise _invalid("target configuration is unavailable") from None
    if len(raw) > _MAX_TARGET_BYTES:
        raise _invalid("target configuration exceeds the size limit")
    if len(raw) != before[2] or opened_after != before or after != before:
        raise _invalid("target configuration changed while it was read")
    return load_json_strict_bytes(raw, label="target")


def _exact_object(value: object, keys: frozenset[str], label: str) -> dict[str, object]:
    if not isinstance(value, dict) or frozenset(value) != keys:
        raise _invalid(f"{label} keys do not match the contract")
    return value


def _reject_reparse_ancestor(path: Path) -> None:
    current = path
    while True:
        try:
            item = current.lstat()
        except FileNotFoundError:
            pass
        except OSError:
            raise _invalid("target path is unavailable") from None
        else:
            if stat.S_ISLNK(item.st_mode) or getattr(item, "st_file_attributes", 0) & _REPARSE_POINT_ATTRIBUTE:
                raise _invalid("target path must not traverse a reparse point")
        if current.parent == current:
            return
        current = current.parent


def _absolute_path(value: object, label: str) -> Path:
    if (
        not isinstance(value, str)
        or not value
        or unicodedata.normalize("NFC", value) != value
        or any(ord(character) <= 0x1F or ord(character) == 0x7F for character in value)
    ):
        raise _invalid(f"{label} must be an absolute canonical path")
    raw_parts = re.split(r"[\\/]", value)
    first = 1 if raw_parts and raw_parts[0] == "" else 0
    if any(part in ("", ".", "..") for part in raw_parts[first:]):
        raise _invalid(f"{label} must be an absolute canonical path")
    path = Path(value)
    if not path.is_absolute() or str(path.anchor).startswith("\\\\"):
        raise _invalid(f"{label} must be an absolute local path")
    canonical = Path(os.path.abspath(path))
    if path != canonical:
        raise _invalid(f"{label} must be an absolute canonical path")
    if canonical == Path(os.path.abspath(Path.home())) or canonical == _TOOL_ROOT:
        raise _invalid(f"{label} uses a protected root")
    if any(":" in part for part in canonical.parts[1:]):
        raise _invalid(f"{label} must not use an alternate data stream")
    _reject_reparse_ancestor(canonical)
    return canonical


def _paths_overlap(first: Path, second: Path) -> bool:
    left, right = os.path.normcase(os.fspath(first)), os.path.normcase(os.fspath(second))
    try:
        common = os.path.commonpath((left, right))
    except ValueError:
        return False
    return common == left or common == right


def _validate_root_separation(
    data_root: Path,
    state_root: Path,
    cdn_root: Path,
    modes_root: Path,
    roots: ComponentRoots,
) -> None:
    protected = (
        data_root, state_root, cdn_root, modes_root,
        roots.content, roots.server, roots.modes,
    )
    if any(_paths_overlap(left, right) for index, left in enumerate(protected) for right in protected[index + 1:]):
        raise _invalid("managed roots must not overlap")


def _version(value: object, label: str) -> str:
    if not isinstance(value, str) or _DOTTED_VERSION.fullmatch(value) is None:
        raise _invalid(f"{label} must be a canonical dotted version")
    return value


def _base_origin(value: object) -> str:
    if not isinstance(value, str) or not value or not value.isascii():
        raise _invalid("serverUrl must be a canonical loopback base origin")
    parsed = urlsplit(value)
    try:
        port = parsed.port
    except ValueError:
        raise _invalid("serverUrl port is invalid") from None
    hostname = parsed.hostname
    if (
        parsed.scheme != "http"
        or hostname is None
        or port is None
        or not 0 < port <= 65535
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        raise _invalid("serverUrl must be a canonical loopback base origin")
    if hostname != "127.0.0.1":
        raise _invalid("serverUrl host must be the managed loopback address")
    if value != f"http://127.0.0.1:{port}":
        raise _invalid("serverUrl must be a canonical loopback base origin")
    return value


def _public_host(value: object) -> str:
    if not isinstance(value, str) or not value or not value.isascii():
        raise _invalid("network.publicHost must be a canonical local IPv4 address")
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        raise _invalid("network.publicHost must be a canonical local IPv4 address") from None
    private = isinstance(address, ipaddress.IPv4Address) and any(
        address in network for network in _RFC1918
    )
    if (
        not isinstance(address, ipaddress.IPv4Address)
        or value != address.compressed
        or not (address.is_loopback or private)
    ):
        raise _invalid("network.publicHost must be loopback or RFC1918 IPv4")
    return value


@dataclass(frozen=True)
class ComponentRoots:
    content: Path
    server: Path
    modes: Path


@dataclass(frozen=True)
class TargetCompatibility:
    client_version: str
    resource_baseline: str
    client_patch_profile: bool

    def __post_init__(self) -> None:
        _version(self.client_version, "compatibility.clientVersion")
        _version(self.resource_baseline, "compatibility.resourceBaseline")
        if type(self.client_patch_profile) is not bool:
            raise _invalid("compatibility.clientPatchProfile must be a boolean")


@dataclass(frozen=True)
class TargetNetwork:
    public_host: str

    def __post_init__(self) -> None:
        _public_host(self.public_host)


@dataclass(frozen=True)
class LaunchSpec:
    executable: Path
    prepare_entry: Path
    server_entry: Path
    cwd: Path


@dataclass(frozen=True)
class ManagedTarget:
    server_bundle: Path
    runtime_pack: Path
    data_root: Path
    state_root: Path
    cdn_root: Path
    modes_root: Path
    component_roots: ComponentRoots
    compatibility: TargetCompatibility
    server_url: str
    network: TargetNetwork = TargetNetwork("127.0.0.1")

    def __post_init__(self) -> None:
        if not isinstance(self.component_roots, ComponentRoots):
            raise _invalid("componentRoots is invalid")
        if not isinstance(self.compatibility, TargetCompatibility):
            raise _invalid("compatibility is invalid")
        if not isinstance(self.network, TargetNetwork):
            raise _invalid("network is invalid")
        paths = (
            ("serverBundle", self.server_bundle), ("runtimePack", self.runtime_pack),
            ("dataRoot", self.data_root), ("stateRoot", self.state_root),
            ("cdnRoot", self.cdn_root), ("modesRoot", self.modes_root),
            ("componentRoots.content", self.component_roots.content),
            ("componentRoots.server", self.component_roots.server),
            ("componentRoots.modes", self.component_roots.modes),
        )
        for label, value in paths:
            if not isinstance(value, Path) or _absolute_path(os.fspath(value), label) != value:
                raise _invalid(f"{label} must be an absolute canonical path")
        _validate_root_separation(
            self.data_root,
            self.state_root,
            self.cdn_root,
            self.modes_root,
            self.component_roots,
        )
        if _base_origin(self.server_url) != self.server_url:
            raise _invalid("serverUrl must be a canonical loopback base origin")
        if self.server_port == self.session_port:
            raise _invalid("serverUrl port conflicts with the fixed session port")

    @classmethod
    def load(cls, source: Path) -> ManagedTarget:
        item = _exact_object(_read_target(source), _TARGET_KEYS, "target")
        if type(item["schemaVersion"]) is not int or item["schemaVersion"] != 1:
            raise _invalid("target schema version is not supported")
        if item["managedBy"] != "wf-release-v1":
            raise _invalid("target manager identity is invalid")
        components = _exact_object(item["componentRoots"], _COMPONENT_KEYS, "componentRoots")
        roots = ComponentRoots(
            content=_absolute_path(components["content"], "componentRoots.content"),
            server=_absolute_path(components["server"], "componentRoots.server"),
            modes=_absolute_path(components["modes"], "componentRoots.modes"),
        )
        compatibility_item = _exact_object(
            item["compatibility"], _COMPATIBILITY_KEYS, "compatibility"
        )
        compatibility = TargetCompatibility(
            client_version=_version(
                compatibility_item["clientVersion"], "compatibility.clientVersion"
            ),
            resource_baseline=_version(
                compatibility_item["resourceBaseline"], "compatibility.resourceBaseline"
            ),
            client_patch_profile=compatibility_item["clientPatchProfile"],  # type: ignore[arg-type]
        )
        network_item = _exact_object(item["network"], _NETWORK_KEYS, "network")
        network = TargetNetwork(_public_host(network_item["publicHost"]))
        state_root = _absolute_path(item["stateRoot"], "stateRoot")
        return cls(
            server_bundle=_absolute_path(item["serverBundle"], "serverBundle"),
            runtime_pack=_absolute_path(item["runtimePack"], "runtimePack"),
            data_root=_absolute_path(item["dataRoot"], "dataRoot"),
            state_root=state_root,
            cdn_root=_absolute_path(item["cdnRoot"], "cdnRoot"),
            modes_root=_absolute_path(item["modesRoot"], "modesRoot"),
            component_roots=roots,
            compatibility=compatibility,
            server_url=_base_origin(item["serverUrl"]),
            network=network,
        )

    @property
    def capabilities_url(self) -> str:
        return self.server_url + "/api/server/capabilities"

    @property
    def health_url(self) -> str:
        return self.server_url + "/healthz"

    @property
    def server_host(self) -> str:
        host = urlsplit(self.server_url).hostname
        if host is None:  # pragma: no cover - guarded by the constructor
            raise _invalid("serverUrl host is unavailable")
        return "127.0.0.1" if host == "localhost" else host

    @property
    def server_port(self) -> int:
        port = urlsplit(self.server_url).port
        if port is None:  # pragma: no cover - guarded by the constructor
            raise _invalid("serverUrl port is unavailable")
        return port

    @property
    def session_bind_host(self) -> str:
        return "0.0.0.0"

    @property
    def session_port(self) -> int:
        return 8003

    @property
    def session_public_host(self) -> str:
        return self.network.public_host

    @property
    def http_bind_host(self) -> str:
        return "0.0.0.0"

    @property
    def public_host(self) -> str:
        return self.network.public_host

    @property
    def cdn_base_url(self) -> str:
        return f"http://{self.public_host}:{self.server_port}/patch/cn"

    def target_probe(self, *, timeout_seconds: float = 5.0) -> TargetProbe:
        return TargetProbe(
            server_manifest=self.server_bundle / "server-manifest.json",
            runtime_manifest=self.runtime_pack / "runtime-pack-manifest.json",
            capabilities_url=self.capabilities_url,
            timeout_seconds=timeout_seconds,
        )

    def launch_spec(self) -> LaunchSpec:
        server, runtime = self.target_probe().manifest_facts()
        return LaunchSpec(
            executable=self.runtime_pack / Path(runtime.entry),
            prepare_entry=self.server_bundle / Path(server.local_prepare_entry),
            server_entry=self.server_bundle / Path(server.entry),
            cwd=self.server_bundle,
        )
