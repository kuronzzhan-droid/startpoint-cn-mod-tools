"""Read delivery bytes and verified logical names without extracting archives."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import zipfile

import wf_mod_tool as core
from wf.deliver.changeset import relative_path
from wf.deliver.logical_paths import logical_path_problem
from wf.paths import path as configured_path
from wf.view.chain import ARCHIVE
from wf.view.members import archive_members, canonical_member

ROOT_NAMES = {"upload": "common", "small_upload": "small", "medium_upload": "medium",
              "android_upload": "android", "ios_upload": "ios"}


@dataclass(frozen=True)
class DeliveryMember:
    logical: str | None
    root: str
    member: str
    data: bytes
    archive: str
    from_version: str | None = None
    to_version: str | None = None


def logical_candidates(extra=(), *, tables_only=False):
    """Use the existing recovered path list; explicit staged paths supplement it."""
    filename = configured_path("pathlist")
    recovered = set(filename.read_text("utf-8-sig").splitlines()) if filename.is_file() else set()
    # Historical recovery lists also contain failed guesses. They are candidates,
    # never authoritative mappings; an invalid unrelated guess cannot break reads.
    paths = {name for name in recovered if name and (not tables_only or name.endswith(".orderedmap"))
             and not logical_path_problem(name)}
    for logical in extra:
        if not isinstance(logical, str) or logical_path_problem(logical):
            raise ValueError(f"invalid explicit logical path: {logical!r}")
        paths.add(logical)
    result = set()
    for logical in paths:
        if not logical or logical.startswith("#"):
            continue
        if tables_only and not logical.endswith(".orderedmap"):
            continue
        if logical_path_problem(logical):
            raise ValueError(f"invalid logical path: {logical!r}")
        result.add(logical)
    return sorted(result)


def delivery_zip_paths(zips=(), *, delivery_dir=None):
    """Select only the top-level delivery archives, never their layered copies."""
    if delivery_dir is not None and zips:
        raise ValueError("provide zips or delivery_dir, not both")
    if delivery_dir is None:
        paths = [Path(filename) for filename in zips]
    else:
        directory = Path(delivery_dir).resolve()
        manifest = directory / "delivery-manifest.json"
        if manifest.is_file():
            document = json.loads(manifest.read_text("utf-8-sig"))
            paths = []
            for record in document["archives"]:
                target = (directory / relative_path(record["name"])).resolve()
                if not target.is_relative_to(directory):
                    raise ValueError("delivery archive escapes delivery directory")
                paths.append(target)
        else:
            paths = sorted(directory.glob("*.zip"))
    if not paths:
        raise ValueError("no delivery ZIP archives selected")
    if len({filename.resolve() for filename in paths}) != len(paths):
        raise ValueError("duplicate delivery ZIP input")
    return paths


def _sidecar(filename, raw):
    sidecar = filename.with_suffix(".integrity.json")
    if not sidecar.is_file():
        return {}
    document = json.loads(sidecar.read_text("utf-8-sig"))
    if not isinstance(document, dict):
        raise ValueError(f"integrity document must be an object: {sidecar.name}")
    if "sha256" in document and document["sha256"] != hashlib.sha256(raw).hexdigest():
        raise ValueError(f"delivery ZIP SHA-256 mismatch: {filename.name}")
    if "size" in document and document["size"] != len(raw):
        raise ValueError(f"delivery ZIP size mismatch: {filename.name}")
    for key in ("logical", "member_sha256"):
        if not isinstance(document.get(key, {}), dict):
            raise ValueError(f"integrity {key} must be an object: {sidecar.name}")
    return document


def _logical_map(document, names, candidates):
    mapped = {}
    for name, logical in document.get("logical", {}).items():
        canonical = canonical_member(name)
        if canonical not in names:
            raise ValueError(f"integrity logical mapping names absent member: {name}")
        if not isinstance(logical, str) or logical_path_problem(logical):
            raise ValueError(f"invalid integrity logical path for {name}")
        digest = "".join(canonical.split("/")[-2:])
        if core.sha1_path(logical) != digest:
            raise ValueError(f"integrity logical path hash mismatch: {logical}")
        if canonical in mapped:
            raise ValueError(f"duplicate integrity logical mapping: {canonical}")
        mapped[canonical] = logical
    for name in names:
        if name not in mapped:
            mapped[name] = candidates.get("".join(name.split("/")[-2:]))
    return mapped


def read_delivery_members(zips=(), *, delivery_dir=None, logical_paths=(), allow_overlays=False):
    """Read ZIPs in caller order; same-package duplicate names are always errors.

    ``logical=None`` preserves unidentified non-table assets for hash comparisons.
    Callers checking orderedmaps must reject unidentified common-root members.
    """
    import io
    candidates = {core.sha1_path(name): name for name in logical_candidates(logical_paths)}
    result, seen = [], set()
    for filename in delivery_zip_paths(zips, delivery_dir=delivery_dir):
        raw = filename.read_bytes()
        document = _sidecar(filename, raw)
        match = ARCHIVE.fullmatch(filename.name)
        before = document.get("applies_on", match[1] if match else None)
        after = document.get("version", match[2] if match else None)
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            names = archive_members(archive)
            logicals = _logical_map(document, names, candidates)
            if not allow_overlays and seen.intersection(names):
                raise ValueError("delivery repeats members across ZIP archives")
            seen.update(names)
            if "files" in document and {canonical_member(n) for n in document["files"]} != set(names):
                raise ValueError(f"integrity member list mismatch: {filename.name}")
            if "members" in document and document["members"] != len(names):
                raise ValueError(f"integrity member count mismatch: {filename.name}")
            hashes = document.get("member_sha256", {})
            for name, original in names.items():
                data = archive.read(original)  # zipfile checks each member's CRC.
                expected = hashes.get(original, hashes.get(name))
                if expected is not None and hashlib.sha256(data).hexdigest() != expected:
                    raise ValueError(f"delivery member SHA-256 mismatch: {name}")
                root = ROOT_NAMES[name.split("/")[1]]
                result.append(DeliveryMember(logicals[name], root, name, data, filename.name, before, after))
            if archive.testzip() is not None:
                raise ValueError(f"delivery ZIP CRC mismatch: {filename.name}")
    return result
