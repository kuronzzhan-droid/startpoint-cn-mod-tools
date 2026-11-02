"""Content fingerprints for actual client artifacts used by kind checks.

The lightweight requirements query does not inspect SWFs. Kind checks do:
their cache must also bind the path profile and every possible artifact,
including absent candidates whose later appearance changes selection.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


def _read(path):
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None


def _document(raw):
    if raw is None:
        return {}
    try:
        value = json.loads(raw.decode("utf-8-sig"))
        return value if isinstance(value, dict) else {}
    except (ValueError, UnicodeError):
        # The digest still includes the invalid bytes; the real reader reports
        # their validation error instead of reusing a previously valid result.
        return {}


def _mapping(value):
    return value if isinstance(value, dict) else {}


def artifact_digest(root):
    """Hash live artifact bytes; never trust their size or modification time."""
    from wf.apk.local_registry import BUILTIN, REVIEWED, LOCAL

    root = Path(root)
    profile_value = os.environ.get("WF_PATHS_PROFILE")
    location = Path(os.path.expandvars(profile_value)).expanduser() if profile_value else root / "profiles/local.json"
    if not location.is_absolute():
        location = root / location
    profile_raw = _read(location)
    config = _document(profile_raw)
    raw_root = os.environ.get("WF_ROOT", config.get("wf_root", config.get("WF_ROOT")))
    if isinstance(raw_root, (str, Path)) and str(raw_root).strip():
        wf_root = Path(os.path.expandvars(str(raw_root))).expanduser()
        if not wf_root.is_absolute():
            wf_root = location.parent / wf_root
    else:
        wf_root = root / "work/external"

    def evidence_path(name):
        name = str(name)
        if name.startswith("${WF_ROOT}/"):
            return wf_root / name[len("${WF_ROOT}/"):]
        path = Path(name)
        return path if path.is_absolute() else root / path

    records = dict(_mapping(_document(_read(root / "client_profiles.json")).get("profiles")))
    registration_paths = [root / BUILTIN, root / REVIEWED, *sorted((root / LOCAL).glob("*/registration.json"))]
    for path in registration_paths:
        record = _document(_read(path))
        if isinstance(record.get("profile"), dict):
            records.setdefault(record.get("profile_id", str(path)), record["profile"])

    paths = set()
    apks = config.get("client_apks", {})
    for profile_id, record in records.items():
        record = _mapping(record)
        evidence = _mapping(record.get("evidence"))
        for key in ("swf_path", "swf"):
            if evidence.get(key):
                paths.add(evidence_path(evidence[key]))
        configured = apks.get(profile_id, []) if isinstance(apks, dict) else []
        for name in configured if isinstance(configured, list) else []:
            if not isinstance(name, str) or not name.strip():
                continue
            path = Path(os.path.expandvars(name)).expanduser()
            paths.add(path if path.is_absolute() else wf_root / path)
        for key in ("provides", "provides_fallback"):
            if not record.get(key):
                continue
            path = Path(record[key])
            source = _mapping(_document(_read(path if path.is_absolute() else root / path)).get("source"))
            name = source.get("path")
            if name and Path(str(name)).suffix.lower() in {".swf", ".apk"}:
                paths.add(evidence_path(name))

    digest = hashlib.sha256()
    digest.update(json.dumps([profile_value, os.environ.get("WF_ROOT"), str(location), str(wf_root)],
                             ensure_ascii=False).encode("utf-8"))
    digest.update(b"\0missing\0" if profile_raw is None else hashlib.sha256(profile_raw).digest())
    for path in sorted({p.resolve() for p in paths}, key=str):
        digest.update(str(path).encode("utf-8"))
        try:
            with path.open("rb") as stream:
                digest.update(b"\0" + hashlib.file_digest(stream, "sha256").digest())
        except FileNotFoundError:
            digest.update(b"\0missing\0")
        except OSError as exc:
            # A non-file or unreadable alternative must not hide an earlier
            # valid candidate. Becoming readable produces a new content key;
            # actual selection still reports errors for a required artifact.
            digest.update(f"\0unreadable:{type(exc).__name__}:{exc.errno}\0".encode())
    return digest.hexdigest()
