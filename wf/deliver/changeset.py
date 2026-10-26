"""Validated, content-addressed inputs for an entirely local delivery."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath

from wf.paths import REPOSITORY
from wf.view.safety import local_output

ROOTS = {"common": "upload", "medium": "medium_upload", "android": "android_upload"}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def relative_path(value: str) -> str:
    p = PurePosixPath(value)
    if not value or "\\" in value or ":" in value or p.is_absolute() or any(x in (".", "..", "") for x in value.split("/")):
        raise ValueError(f"unsafe relative path: {value!r}")
    return value


def member_name(root: str, logical: str) -> str:
    import wf_mod_tool as core
    relative_path(logical)
    digest = core.sha1_path(logical)
    return f"production/{ROOTS[root]}/{digest[:2]}/{digest[2:]}"


def validate_document(document: dict, schema: str) -> None:
    from jsonschema import Draft202012Validator
    definition = json.loads((REPOSITORY / "schemas" / schema).read_text("utf-8"))
    errors = sorted(Draft202012Validator(definition).iter_errors(document), key=lambda e: str(e.path))
    if errors:
        raise ValueError("; ".join(f"{'/'.join(map(str, e.path)) or '$'}: {e.message}" for e in errors))


def load_changeset(filename: Path) -> tuple[dict, dict[str, tuple[bytes, dict]], dict[str, bytes]]:
    filename = Path(filename).resolve()
    doc = json.loads(filename.read_text("utf-8-sig"))
    validate_document(doc, "change-set.schema.json")
    if tuple(map(int, doc["from_version"].split("."))) >= tuple(map(int, doc["to_version"].split("."))):
        raise ValueError("delivery version must move forward")
    if doc.get("experimental") and not doc["local_test_only"]:
        raise ValueError("experimental changes require local_test_only")
    members, server = {}, {}
    for ent in [*doc["members"], *doc.get("server_changes", [])]:
        # Sources are local staged inputs, never arbitrary files outside the changeset.
        source = (filename.parent / relative_path(ent["source"])).resolve()
        if not source.is_relative_to(filename.parent):
            raise ValueError(f"source escapes changeset directory: {source}")
        raw = source.read_bytes()
        if sha256(raw) != ent["sha256"]:
            raise ValueError(f"source SHA-256 mismatch: {ent['source']}")
        if "root" in ent:
            name = member_name(ent["root"], ent["logical_path"])
            if name in members:
                raise ValueError(f"duplicate member: {name}")
            members[name] = (raw, ent)
        else:
            target = relative_path(ent["target"])
            if target in server:
                raise ValueError(f"duplicate server target: {target}")
            server[target] = raw
    if not members:
        raise ValueError("delivery requires at least one client member")
    return doc, members, server


def write_json(path: Path, document: dict) -> None:
    path = local_output(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", "utf-8")
