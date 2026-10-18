"""Resolve selected client evidence; never infer compatibility from profile names."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from wf.deliver.changeset import validate_document
from wf.paths import REPOSITORY

DEFAULT_PROFILE = "test-v34"


def load_profiles(filename=None):
    filename = Path(filename) if filename else REPOSITORY / "client_profiles.json"
    document = json.loads(filename.read_text("utf-8-sig"))
    return document.get("default_client_profile", DEFAULT_PROFILE), document["profiles"]


def resolve_client(provides=None, client_profile=None, *, allow_unknown_client=False):
    """Explicit profile/evidence pairs must agree; no silent profile downgrade."""
    if provides is not None:
        if client_profile is not None:
            _, records = load_profiles()
            if client_profile not in records:
                raise ValueError(f"未知客户端档案：{client_profile}")
            record = records[client_profile]
            actual = hashlib.sha256(Path(provides).read_bytes()).hexdigest()
            expected = {record.get("provides_sha256"), record.get("provides_fallback_sha256")}
            if actual not in expected:
                raise ValueError("显式 provides 与所选客户端档案冲突")
            read_client(provides, profile=record, expected_digest=actual)
            return Path(provides), client_profile
        return Path(provides), None
    if allow_unknown_client and client_profile is None:
        return None, None
    default, profiles = load_profiles()
    selected = client_profile or default
    if selected not in profiles:
        raise ValueError(f"未知客户端档案：{selected}")
    filename = profiles[selected].get("provides")
    if not isinstance(filename, str) or not filename:
        raise ValueError(f"客户端档案 {selected} 没有 provides 证据")
    path = Path(filename)
    if not path.is_absolute():
        path = REPOSITORY / path
    expected_digest = profiles[selected].get("provides_sha256")
    if not path.is_file() and profiles[selected].get("provides_fallback"):
        path = REPOSITORY / profiles[selected]["provides_fallback"]
        expected_digest = profiles[selected].get("provides_fallback_sha256")
    read_client(path, profile=profiles[selected], expected_digest=expected_digest)
    return path, selected


def read_client(path, *, profile=None, expected_digest=None):
    raw = Path(path).read_bytes()
    document = json.loads(raw.decode("utf-8-sig"))
    validate_document(document, "provides.schema.json")
    if profile is not None:
        evidence = profile.get("evidence", {})
        source = document["source"]
        if not evidence.get("swf_sha256") or source.get("swf_sha256") != evidence["swf_sha256"]:
            raise ValueError("客户端档案 SWF 哈希与 provides 不符")
        expected = expected_digest or profile.get("provides_sha256")
        if not expected or hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError("客户端档案 provides 文件哈希不符")
        if source["kind"] == "apk":
            apk_hashes = set(evidence.get("apk_sha256_by_arch", {}).values())
            apk_hashes.add(evidence.get("apk_sha256"))
            if not source.get("sha256") or source["sha256"] not in apk_hashes:
                raise ValueError("客户端档案 APK 哈希与 provides 不符")
    return document


def profile_options():
    default, profiles = load_profiles()
    return {"defaultClientProfile": default,
            "clientProfiles": [{"id": key, "label": profile.get("label", key),
                                "provides": profile["provides"]}
                               for key, profile in profiles.items() if profile.get("provides")]}
