"""Small real filesystem fixtures for wf-release-v1 tests."""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import struct
import warnings
import zipfile
import zlib

import wf_character_workspace


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _write_package_file(
    package: Path,
    root: str,
    logical_path: str,
    raw: bytes,
) -> dict[str, object]:
    path = package / "roots" / root / Path(logical_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return {
        "logical_path": logical_path,
        "sha256": _sha256(raw),
        "size": len(raw),
    }


def make_sealed_character_workspace(
    root: Path,
    *,
    character_id: int = 129999,
    code_name: str = "seris_dragon_king",
) -> Path:
    """Create a real 37/37 production workspace sealed by its semantic digest."""
    workspace = wf_character_workspace.init_workspace(
        root,
        111165,
        character_id,
        code_name,
        code_name,
    )
    package = workspace.package_dir
    roots: dict[str, list[dict[str, object]]] = {
        name: [] for name in ("common", "medium", "android", "server")
    }
    table_path = "master/character/character.orderedmap"
    roots["common"].append(
        _write_package_file(package, "common", table_path, b"character-table")
    )
    for requirement in wf_character_workspace.char_asset_requirements(code_name):
        if requirement.category == "required":
            raw = requirement.logical_path.encode("utf-8")
            roots["medium"].append(
                _write_package_file(package, "medium", requirement.logical_path, raw)
            )
    for logical_path in (
        "cdndata/character.json",
        "cdndata/character_text.json",
        "character.json",
    ):
        roots["server"].append(
            _write_package_file(package, "server", logical_path, b"{}")
        )

    manifest_path = package / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "package_version": "1.0.0",
            "requires_client_base": "1.4.54",
            "roots": roots,
            "tables": [
                {
                    "root": "common",
                    "logical_path": table_path,
                    "codec_id": "flat",
                    "outer_keys": [str(character_id)],
                    "inner_keys": [],
                    "semantic_claims": [],
                }
            ],
        }
    )
    manifest["qa"].update(
        {
            "delivery_mode": "production",
            "release_ready": True,
            "required_assets_total": 37,
            "required_assets_present": 37,
            "workspace_input_sha256": "",
        }
    )
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    binding = wf_character_workspace.workspace_status(workspace, persist=False)
    manifest["qa"]["workspace_input_sha256"] = binding.input_digest
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    ready = wf_character_workspace.workspace_status(workspace, persist=False)
    if not ready.release_ready:
        raise AssertionError(ready.to_dict())
    return workspace.root


def _inner_zip_bytes(label: str) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr(f"production/{label}.txt", label.encode("ascii"))
    return output.getvalue()


def _stored_zip_members(members: list[tuple[str, bytes]]) -> bytes:
    """Build exact-name ZIP members without platform path sanitization."""
    locals_: list[bytes] = []
    centrals: list[bytes] = []
    offset = 0
    for name, raw in members:
        encoded_name = name.encode("utf-8")
        flags = 0x0800
        checksum = zlib.crc32(raw) & 0xFFFFFFFF
        local = struct.pack(
            "<IHHHHHIIIHH",
            0x04034B50,
            20,
            flags,
            0,
            0,
            0,
            checksum,
            len(raw),
            len(raw),
            len(encoded_name),
            0,
        ) + encoded_name + raw
        central = struct.pack(
            "<IHHHHHHIIIHHHHHII",
            0x02014B50,
            20,
            20,
            flags,
            0,
            0,
            0,
            checksum,
            len(raw),
            len(raw),
            len(encoded_name),
            0,
            0,
            0,
            0,
            0,
            offset,
        ) + encoded_name
        locals_.append(local)
        centrals.append(central)
        offset += len(local)

    local_bytes = b"".join(locals_)
    central_bytes = b"".join(centrals)
    end = struct.pack(
        "<IHHHHIIH",
        0x06054B50,
        0,
        0,
        len(members),
        len(members),
        len(central_bytes),
        len(local_bytes),
        0,
    )
    return local_bytes + central_bytes + end


def _stored_zip_bytes(names: list[str]) -> bytes:
    return _stored_zip_members(
        [(name, f"payload-{index}".encode("ascii")) for index, name in enumerate(names)]
    )


def rewrite_outer_member_raw_name(path: Path, member_name: str, raw_name: str) -> None:
    """Rewrite one outer member with an exact adversarial central-directory name."""
    with zipfile.ZipFile(path) as bundle:
        ordered = [
            (
                raw_name if item.filename == member_name else item.filename,
                bundle.read(item),
            )
            for item in bundle.infolist()
        ]
    if sum(name == raw_name for name, _ in ordered) != 1:
        raise AssertionError(f"member not found: {member_name}")
    path.write_bytes(_stored_zip_members(ordered))


def corrupt_zip_member_crc(path: Path, member_name: str) -> None:
    """Corrupt one member CRC in both its local and central ZIP headers."""
    with zipfile.ZipFile(path) as bundle:
        info = bundle.getinfo(member_name)
        central_offset = bundle.start_dir
    raw = bytearray(path.read_bytes())
    bad_crc = info.CRC ^ 0xFFFFFFFF
    if raw[info.header_offset : info.header_offset + 4] != b"PK\x03\x04":
        raise AssertionError("local ZIP header not found")
    struct.pack_into("<I", raw, info.header_offset + 14, bad_crc)

    cursor = central_offset
    central_found = False
    while raw[cursor : cursor + 4] == b"PK\x01\x02":
        name_length, extra_length, comment_length = struct.unpack_from(
            "<HHH", raw, cursor + 28
        )
        local_offset = struct.unpack_from("<I", raw, cursor + 42)[0]
        if local_offset == info.header_offset:
            struct.pack_into("<I", raw, cursor + 16, bad_crc)
            central_found = True
            break
        cursor += 46 + name_length + extra_length + comment_length
    if not central_found:
        raise AssertionError("central ZIP header not found")
    path.write_bytes(raw)


def replace_first_inner_zip(path: Path, names: list[str]) -> None:
    """Replace the first manifest payload with an inner ZIP using exact names."""
    inner_raw = _stored_zip_bytes(names)

    with zipfile.ZipFile(path) as bundle:
        ordered = [(item.filename, bundle.read(item)) for item in bundle.infolist()]
    manifest = json.loads(dict(ordered)["patch-manifest.json"])
    target = manifest["archives"][0]
    target["bytes"] = len(inner_raw)
    target["sha256"] = _sha256(inner_raw)
    ordered = [
        (
            name,
            inner_raw
            if name == target["relativePath"]
            else json.dumps(manifest, separators=(",", ":")).encode("utf-8") + b"\n"
            if name == "patch-manifest.json"
            else raw,
        )
        for name, raw in ordered
    ]
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for name, raw in ordered:
            bundle.writestr(name, raw)


def make_patch_overlay(
    path: Path,
    *,
    from_version: str,
    target_version: str,
    manifest_updates: dict[str, object] | None = None,
    extra_members: dict[str, bytes] | None = None,
    duplicate_member: str | None = None,
    bomb_bytes: int = 0,
) -> Path:
    """Write one exporter-shaped outer Patch Overlay ZIP."""
    archives: list[dict[str, object]] = []
    payloads: dict[str, bytes] = {}
    for layer in ("common", "medium", "android"):
        raw = _inner_zip_bytes(layer)
        relative_path = (
            f"archive-{layer}-diff/"
            f"pinball-{from_version}-{target_version}-1-{_sha256(raw)[:12]}.zip"
        )
        payloads[relative_path] = raw
        archives.append(
            {
                "relativePath": relative_path,
                "layer": layer,
                "order": 1,
                "bytes": len(raw),
                "sha256": _sha256(raw),
            }
        )
    manifest: dict[str, object] = {
        "schema": 1,
        "targetVersion": target_version,
        "compatibleClient": "CN 1.8.1",
        "archives": archives,
    }
    if manifest_updates:
        manifest.update(manifest_updates)
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr("README.md", "fixture overlay\n")
        bundle.writestr("requires.json", '{"schemaVersion":2}\n')
        for name in sorted(payloads):
            bundle.writestr(name, payloads[name])
        for name, raw in (extra_members or {}).items():
            bundle.writestr(name, raw)
        if bomb_bytes:
            bundle.writestr("bomb.bin", b"0" * bomb_bytes)
        bundle.writestr(
            "patch-manifest.json",
            json.dumps(manifest, ensure_ascii=False, separators=(",", ":")) + "\n",
        )
        if duplicate_member:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                bundle.writestr(duplicate_member, b"duplicate")
    return path


def rewrite_overlay(
    path: Path,
    *,
    manifest_mutator=None,
    member_mutator=None,
) -> None:
    """Rewrite a fixture while preserving member order for adversarial cases."""
    with zipfile.ZipFile(path) as bundle:
        ordered = [(item.filename, bundle.read(item)) for item in bundle.infolist()]
    if manifest_mutator is not None:
        manifest = json.loads(dict(ordered)["patch-manifest.json"])
        manifest_mutator(manifest)
        ordered = [
            (
                name,
                json.dumps(manifest, separators=(",", ":")).encode("utf-8") + b"\n"
                if name == "patch-manifest.json"
                else raw,
            )
            for name, raw in ordered
        ]
    if member_mutator is not None:
        ordered = member_mutator(ordered)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for name, raw in ordered:
            bundle.writestr(name, raw)
