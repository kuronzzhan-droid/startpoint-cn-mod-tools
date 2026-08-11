"""Deterministic content-plus-Mode Release fixture construction."""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path

from tests.test_release_v1_verifier import (
    OWNERSHIP,
    RELEASE,
    REQUIRES,
    ROOT,
    _classic_store,
    _members,
)
from wf_release_v1.canonical import canonical_json_bytes, load_json_strict_bytes
from wf_release_v1.schema import compute_release_id


MODE_FILE = "fixture-mode.mjs"
MODE_NAME = "fixture-mode"
MODE_CAPABILITY = "fixture.mode@1"
RESOURCE_PATH = "fixture-mode.resources/config/value.json"
RESOURCE_RAW = b'{"value":1}\n'


def _module(resource_digest: str, *, marker: str) -> bytes:
    return (
        "export const modeManifest = Object.freeze({\n"
        '  apiVersion: 1, name: "fixture-mode", capability: "fixture.mode@1",\n'
        '  requiresServerCapabilities: ["mode.release-contract@1"],\n'
        f'  resources: {{"config/value.json": "{resource_digest}"}},\n'
        "});\n"
        f"export const marker = {marker!r};\n"
        "export async function register() { return {}; }\n"
    ).encode("utf-8")


def mode_payloads(*, marker: str = "v1") -> tuple[dict[str, bytes], str]:
    resource_digest = hashlib.sha256(RESOURCE_RAW).hexdigest()
    module = _module(resource_digest, marker=marker)
    module_digest = hashlib.sha256(module).hexdigest()
    payloads = {
        MODE_FILE: module,
        RESOURCE_PATH: RESOURCE_RAW,
        "modes-allowlist.json": canonical_json_bytes({MODE_FILE: module_digest}),
        "modes-required.json": canonical_json_bytes({
            "required": [MODE_FILE],
            "schemaVersion": 1,
        }),
    }
    identity = [{
        "capabilities": [MODE_CAPABILITY],
        "fileName": MODE_FILE,
        "name": MODE_NAME,
        "sha256": module_digest,
    }]
    mode_digest = "sha256:" + hashlib.sha256(canonical_json_bytes(identity)).hexdigest()
    return payloads, mode_digest


def make_character_mode_release(source: Path, output: Path, *, marker: str = "v1") -> Path:
    members = dict(_members(source.read_bytes()))
    release = load_json_strict_bytes(members[RELEASE], label=RELEASE)
    if not isinstance(release, dict):
        raise AssertionError("release fixture manifest is not an object")
    release = copy.deepcopy(release)
    payloads, mode_digest = mode_payloads(marker=marker)
    release["components"] = [
        {"kind": "content", "root": "content"},
        {"kind": "modes", "root": "modes"},
    ]
    expected = release["expectedState"]
    if not isinstance(expected, dict):
        raise AssertionError("release fixture expectedState is not an object")
    expected["modeDigest"] = mode_digest
    files = release["files"]
    if not isinstance(files, list):
        raise AssertionError("release fixture files are not an array")
    for relative, raw in payloads.items():
        files.append({
            "path": f"modes/{relative}",
            "size": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        })
    files.sort(key=lambda item: item["path"].encode("utf-8"))
    body = copy.deepcopy(release)
    body.pop("releaseId", None)
    release["releaseId"] = compute_release_id(body)
    members[RELEASE] = canonical_json_bytes(release)
    for relative, raw in payloads.items():
        members[f"{ROOT}modes/{relative}"] = raw
    payload_names = sorted(
        (name for name in members if name not in {OWNERSHIP, REQUIRES, RELEASE}),
        key=lambda name: name.encode("utf-8"),
    )
    ordered = [(name, members[name]) for name in payload_names]
    ordered.extend((name, members[name]) for name in (OWNERSHIP, REQUIRES, RELEASE))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(_classic_store(ordered))
    return output


def rewrite_requirements_without_mode_capability(source: Path, output: Path) -> Path:
    members = dict(_members(source.read_bytes()))
    requirements = load_json_strict_bytes(members[REQUIRES], label=REQUIRES)
    release = load_json_strict_bytes(members[RELEASE], label=RELEASE)
    if not isinstance(requirements, dict) or not isinstance(release, dict):
        raise AssertionError("release fixture metadata is not an object")
    capabilities = requirements["serverCapabilities"]
    if not isinstance(capabilities, list):
        raise AssertionError("release fixture capabilities are not an array")
    requirements["serverCapabilities"] = [
        item for item in capabilities if item != "mode.release-contract@1"
    ]
    requirements_raw = canonical_json_bytes(requirements)
    metadata = release["metadataSha256"]
    if not isinstance(metadata, dict):
        raise AssertionError("release fixture metadata hashes are invalid")
    metadata["requires"] = hashlib.sha256(requirements_raw).hexdigest()
    body = copy.deepcopy(release)
    body.pop("releaseId", None)
    release["releaseId"] = compute_release_id(body)
    members[REQUIRES] = requirements_raw
    members[RELEASE] = canonical_json_bytes(release)
    names = [name for name, _raw in _members(source.read_bytes())]
    output.write_bytes(_classic_store([(name, members[name]) for name in names]))
    return output


__all__ = [
    "MODE_CAPABILITY",
    "MODE_FILE",
    "MODE_NAME",
    "RESOURCE_PATH",
    "make_character_mode_release",
    "mode_payloads",
    "rewrite_requirements_without_mode_capability",
]
