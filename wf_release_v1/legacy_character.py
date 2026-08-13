"""Adopt one fully mapped legacy share as an inert character workspace."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
from typing import Final, Iterator, Mapping

import wf_character_pack
import wf_character_workspace
import wf_mod_tool

from .canonical import canonical_json_bytes, load_json_strict_bytes, normalize_relative_path
from .errors import ReleaseError


_REPARSE_POINT: Final = 0x0400
_ROOTS: Final = ("common", "medium", "android")
_SERVER_TABLES: Final = {
    "assets/character.json": "character.json",
    "assets/cdndata/character.json": "cdndata/character.json",
    "assets/cdndata/character_text.json": "cdndata/character_text.json",
    "assets/mana_node.json": "mana_node.json",
}
_CONFIG_KEYS: Final = frozenset({
    "clientTables",
    "codeName",
    "legacyCharacterAdoptionVersion",
    "packageId",
    "packageVersion",
    "requiredCapabilities",
    "requiresClientBase",
    "serverRows",
    "skills",
    "targetCharacterId",
    "templateCharacterId",
    "uniqueCondition",
})
_TABLE_KEYS: Final = frozenset({
    "codecId", "innerKeys", "logicalPath", "outerKeys", "root", "semanticClaims",
})


@dataclass(frozen=True)
class LegacyCharacterReceipt:
    archive_sha256: str
    character_id: int
    code_name: str
    mapping_status: str
    workspace_file_count: int
    workspace_input_sha256: str

    def to_wire(self) -> dict[str, object]:
        return {
            "archiveSha256": self.archive_sha256,
            "characterId": self.character_id,
            "codeName": self.code_name,
            "legacyCharacterAdoptionVersion": 1,
            "mappingStatus": self.mapping_status,
            "releaseReady": True,
            "workspaceFileCount": self.workspace_file_count,
            "workspaceInputSha256": self.workspace_input_sha256,
        }


def _fail(message: str) -> ReleaseError:
    return ReleaseError("WFREL_CHARACTER_ADOPTION_INVALID", message)


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise _fail(f"{label} must be an object")
    return value


def _positive_int(value: object, label: str) -> int:
    if type(value) is not int or value <= 0:
        raise _fail(f"{label} must be a positive integer")
    return value


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise _fail(f"{label} must be a non-empty string")
    return value


def _sha(value: object, label: str) -> str:
    text = _string(value, label)
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise _fail(f"{label} must be a lowercase SHA-256")
    return text


def _is_reparse(value: os.stat_result) -> bool:
    return stat.S_ISLNK(value.st_mode) or bool(
        getattr(value, "st_file_attributes", 0) & _REPARSE_POINT
    )


def _regular_bytes(path: Path, expected_sha: str, expected_size: int) -> bytes:
    try:
        before = path.lstat()
        if _is_reparse(before) or not stat.S_ISREG(before.st_mode):
            raise OSError("not a regular file")
        raw = path.read_bytes()
        after = path.lstat()
    except OSError as error:
        raise _fail("legacy import source is unavailable or changed") from error
    identity = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
    after_identity = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    if identity != after_identity or len(raw) != expected_size:
        raise _fail("legacy import source changed while being read")
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        raise _fail("legacy import source changed or has a mismatched digest")
    return raw


def _load_config(path: Path) -> Mapping[str, object]:
    try:
        value = _mapping(
            load_json_strict_bytes(path.read_bytes(), label="legacy character adoption"),
            "legacy character adoption",
        )
    except OSError as error:
        raise _fail("legacy character adoption config is unavailable") from error
    if set(value) != _CONFIG_KEYS or value["legacyCharacterAdoptionVersion"] != 1:
        raise _fail("legacy character adoption config fields are invalid")
    return value


def _load_import(root: Path) -> tuple[Mapping[str, object], dict[str, bytes]]:
    inventory_path = root / "legacy-import.json"
    try:
        inventory = _mapping(
            load_json_strict_bytes(inventory_path.read_bytes(), label="legacy import"),
            "legacy import",
        )
    except OSError as error:
        raise _fail("legacy import inventory is unavailable") from error
    if (
        inventory.get("legacyImportVersion") != 1
        or inventory.get("mappingStatus") != "complete"
        or inventory.get("clientPayloadEditable") is not True
    ):
        raise _fail("legacy import must have one complete editable path mapping")
    source = _mapping(inventory.get("sourceArchive"), "sourceArchive")
    source_path = normalize_relative_path(_string(source.get("path"), "sourceArchive.path"))
    source_raw = _regular_bytes(
        root / Path(source_path),
        _sha(source.get("sha256"), "sourceArchive.sha256"),
        _positive_int(source.get("size"), "sourceArchive.size"),
    )
    if _sha(inventory.get("archiveSha256"), "archiveSha256") != hashlib.sha256(source_raw).hexdigest():
        raise _fail("legacy import archive identity is inconsistent")

    items = inventory.get("payloadFiles")
    if not isinstance(items, list) or len(items) != inventory.get("payloadFileCount"):
        raise _fail("legacy import payload inventory is inconsistent")
    selected: dict[str, tuple[str, bytes]] = {}
    for index, raw_item in enumerate(items):
        item = _mapping(raw_item, f"payloadFiles[{index}]")
        root_name = _string(item.get("root"), f"payloadFiles[{index}].root")
        if root_name not in _ROOTS:
            raise _fail("legacy import payload root is invalid")
        logical = normalize_relative_path(
            _string(item.get("logicalPath"), f"payloadFiles[{index}].logicalPath")
        )
        relative = normalize_relative_path(
            _string(item.get("path"), f"payloadFiles[{index}].path")
        )
        expected_relative = f"roots/{root_name}/{logical}"
        if relative != expected_relative:
            raise _fail("legacy import payload path does not match its logical mapping")
        size = item.get("size")
        if type(size) is not int or size < 0:
            raise _fail("legacy import payload size is invalid")
        payload = _regular_bytes(
            root / Path(relative), _sha(item.get("sha256"), "payload sha256"), size
        )
        previous = selected.get(logical)
        if previous is not None and previous[1] != payload:
            raise _fail("legacy import has conflicting cross-root bytes for one logical path")
        # A common declaration is the most portable source-semantic representative.
        if previous is None or (previous[0] != "common" and root_name == "common"):
            selected[logical] = (root_name, payload)
    return inventory, {f"{root_name}\0{logical}": raw for logical, (root_name, raw) in selected.items()}


def _table_claims(config: Mapping[str, object], payloads: Mapping[str, bytes]) -> list[dict[str, object]]:
    values = config["clientTables"]
    if not isinstance(values, list) or not values:
        raise _fail("clientTables must be a non-empty array")
    result: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for index, raw_value in enumerate(values):
        value = _mapping(raw_value, f"clientTables[{index}]")
        if set(value) != _TABLE_KEYS:
            raise _fail("client table fields are invalid")
        root = _string(value["root"], "client table root")
        logical = normalize_relative_path(_string(value["logicalPath"], "client table path"))
        codec = _string(value["codecId"], "client table codec")
        marker = (root, logical)
        if root not in _ROOTS or marker in seen:
            raise _fail("client table root or identity is invalid")
        seen.add(marker)
        raw = payloads.get(f"{root}\0{logical}")
        if raw is None:
            raise _fail("client table claim has no matching imported payload")
        outer = value["outerKeys"]
        inner = value["innerKeys"]
        semantics = value["semanticClaims"]
        if (
            not isinstance(outer, list) or not outer
            or any(not isinstance(item, str) or not item for item in outer)
            or len(set(outer)) != len(outer)
            or not isinstance(inner, list)
            or not isinstance(semantics, list)
        ):
            raise _fail("client table claim fields are invalid")
        try:
            if codec in {"flat", "raw_outer"}:
                keys, _rows = wf_mod_tool._strict_orderedmap_rows(  # type: ignore[attr-defined]
                    raw, label=logical, compressed_rows=codec == "flat"
                )
                if not set(outer).issubset(keys):
                    raise _fail("client table claim is not present in imported table bytes")
                if inner:
                    raise _fail("flat client table cannot claim inner keys")
            elif codec in {"action_nested", "switched_nested"}:
                table = wf_mod_tool.load_nested_table_bytes(raw, logical)
                if not set(outer).issubset(table.rows):
                    raise _fail("client table outer claim is not present")
                expected_inner: dict[str, set[str]] = {}
                for entry in inner:
                    item = _mapping(entry, "client table inner claim")
                    if set(item) != {"outer_key", "keys"}:
                        raise _fail("client table inner claim fields are invalid")
                    outer_key = _string(item["outer_key"], "inner outer key")
                    keys = item["keys"]
                    if not isinstance(keys, list) or not keys:
                        raise _fail("client table inner keys are invalid")
                    expected_inner[outer_key] = set(keys)
                for outer_key, keys in expected_inner.items():
                    if outer_key not in table.rows or not keys.issubset(table.rows[outer_key].keys):
                        raise _fail("client table inner claim is not present")
            else:
                raise _fail("client table codec is unsupported")
        except ReleaseError:
            raise
        except (UnicodeError, ValueError, TypeError, KeyError) as error:
            raise _fail("client table bytes do not satisfy their declared codec") from error
        result.append({
            "root": root,
            "logical_path": logical,
            "codec_id": codec,
            "outer_keys": list(outer),
            "inner_keys": list(inner),
            "semantic_claims": list(semantics),
        })
    return result


def _server_payloads(
    imported: Path,
    config: Mapping[str, object],
    character_id: int,
) -> dict[str, bytes]:
    server = _mapping(config["serverRows"], "serverRows")
    if set(server) != {"path", "sha256"}:
        raise _fail("serverRows fields are invalid")
    relative = normalize_relative_path(_string(server["path"], "serverRows.path"))
    if not relative.startswith("quarantine/server-data/"):
        raise _fail("serverRows must point to quarantined server-data")
    path = imported / Path(relative)
    try:
        size = path.lstat().st_size
    except OSError as error:
        raise _fail("serverRows input is unavailable") from error
    raw = _regular_bytes(path, _sha(server["sha256"], "serverRows.sha256"), size)
    rows = _mapping(load_json_strict_bytes(raw, label="serverRows"), "serverRows")
    if set(rows) != set(_SERVER_TABLES):
        raise _fail("serverRows must contain exactly the four character server tables")
    expected = str(character_id)
    result: dict[str, bytes] = {}
    for source, logical in _SERVER_TABLES.items():
        table = _mapping(rows[source], source)
        if set(table) != {expected}:
            raise _fail("serverRows table must contain exactly the target character row")
        result[logical] = canonical_json_bytes(table)
    return result


def _copy_payloads(package: Path, payloads: Mapping[str, bytes]) -> dict[str, list[dict[str, object]]]:
    roots: dict[str, list[dict[str, object]]] = {
        name: [] for name in ("common", "medium", "android", "server")
    }
    for marker in sorted(payloads, key=lambda value: value.encode("utf-8")):
        root, logical = marker.split("\0", 1)
        raw = payloads[marker]
        destination = package / "roots" / root / Path(logical)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
        roots[root].append({
            "logical_path": logical,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size": len(raw),
        })
    return roots


@contextmanager
def _owned_staging(parent: Path) -> Iterator[Path]:
    raw = Path(tempfile.mkdtemp(prefix=".legacy-character-", dir=parent))
    # Workspace paths use the Windows extended-path namespace so both writes
    # and failure cleanup can reach original CDN resource names beyond MAX_PATH.
    staging = wf_character_workspace._absolute(raw)  # type: ignore[attr-defined]
    try:
        yield staging
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def adopt_legacy_character(imported: Path, config_path: Path, output: Path) -> LegacyCharacterReceipt:
    """Create one sealed workspace without executing or installing imported bytes."""
    imported = wf_character_workspace._absolute(Path(imported)).resolve()  # type: ignore[attr-defined]
    destination = Path(output)
    if not destination.is_absolute() or destination.exists():
        raise _fail("legacy character output must be a new absolute path")
    parent = destination.parent
    if not parent.is_dir() or _is_reparse(parent.lstat()):
        raise _fail("legacy character output parent is unsafe")
    config = _load_config(Path(config_path))
    character_id = _positive_int(config["targetCharacterId"], "targetCharacterId")
    template_id = _positive_int(config["templateCharacterId"], "templateCharacterId")
    code_name = _string(config["codeName"], "codeName")
    package_id = _string(config["packageId"], "packageId")
    inventory, client_payloads = _load_import(imported)
    client_claims = _table_claims(config, client_payloads)
    server_payloads = _server_payloads(imported, config, character_id)
    all_payloads = dict(client_payloads)
    all_payloads.update({f"server\0{logical}": raw for logical, raw in server_payloads.items()})

    with _owned_staging(parent) as temporary_root:
        workspace = wf_character_workspace.init_workspace(
            temporary_root, template_id, character_id, code_name, package_id
        )
        roots = _copy_payloads(workspace.package_dir, all_payloads)
        server_claims = [{
            "root": "server",
            "logical_path": logical,
            "codec_id": "json_object",
            "outer_keys": [str(character_id)],
            "inner_keys": [],
            "semantic_claims": [],
        } for logical in sorted(server_payloads, key=lambda value: value.encode("utf-8"))]
        manifest_path = workspace.package_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        capabilities = config["requiredCapabilities"]
        if (
            not isinstance(capabilities, list)
            or any(not isinstance(item, str) or not item for item in capabilities)
            or len(set(capabilities)) != len(capabilities)
        ):
            raise _fail("requiredCapabilities must be a unique string array")
        manifest.update({
            "package_version": _string(config["packageVersion"], "packageVersion"),
            "requires_client_base": _string(config["requiresClientBase"], "requiresClientBase"),
            "required_capabilities": list(capabilities),
            "roots": roots,
            "tables": [*client_claims, *server_claims],
            "skills": dict(_mapping(config["skills"], "skills")),
            "unique_condition": dict(_mapping(config["uniqueCondition"], "uniqueCondition")),
        })
        manifest["qa"].update({
            "delivery_mode": "production",
            "release_ready": False,
            "required_assets_total": 37,
            "required_assets_present": 37,
            "workspace_input_sha256": "",
        })
        manifest_path.write_bytes(canonical_json_bytes(manifest))
        errors = wf_character_pack.validate_manifest(manifest, workspace.package_dir)
        if errors:
            raise _fail("adopted character manifest is invalid: " + "; ".join(errors))
        sealed = wf_character_workspace.seal_workspace(workspace)
        source = _mapping(inventory["sourceArchive"], "sourceArchive")
        final = temporary_root / package_id
        if destination.exists():
            raise _fail("legacy character output appeared during commit")
        os.rename(final, destination)
        try:
            descriptor = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        except OSError:
            if os.name != "nt":
                shutil.rmtree(destination, ignore_errors=True)
                raise
        return LegacyCharacterReceipt(
            _sha(source["sha256"], "sourceArchive.sha256"),
            character_id,
            code_name,
            "complete",
            sealed.file_count,
            sealed.input_digest,
        )


__all__ = ["LegacyCharacterReceipt", "adopt_legacy_character"]
