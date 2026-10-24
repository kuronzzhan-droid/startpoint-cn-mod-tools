#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Freeze and finalize the five-file World Flipper offline Android bundle.

This module deliberately owns no live game data and imports no device module.  A
device receipt may be validated through an injected callable; the default
validator understands the stable JSON receipt contract without creating a
Task-12/Task-13 import cycle.
"""
from __future__ import annotations

import ctypes
import errno
import hashlib
import hmac
import io
import json
import math
import os
import re
import stat
import uuid
import zipfile
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO


APK_NAME = "WorldFlipper-离线整合版.apk"
DATA_ZIP_NAME = "WorldFlipper-数据-1.4.196.zip"
GUIDE_NAME = "导入说明.txt"
MANIFEST_NAME = "build-manifest.json"
SHA256SUMS_NAME = "SHA256SUMS.txt"
CANDIDATE_EVIDENCE_NAME = ".candidate-evidence.json"
FINAL_FILES = (APK_NAME, DATA_ZIP_NAME, GUIDE_NAME, MANIFEST_NAME, SHA256SUMS_NAME)
CANDIDATE_FILES = (APK_NAME, DATA_ZIP_NAME, GUIDE_NAME, CANDIDATE_EVIDENCE_NAME)
HASHED_FINAL_FILES = (APK_NAME, DATA_ZIP_NAME, GUIDE_NAME, MANIFEST_NAME)

SNAPSHOT_VERSION = "1.4.196"
SOURCE_RESOURCE_VERSION = "1.4.54"
PRODUCTION_ENTRY_COUNT = 138_291
PRODUCTION_ROOT_COUNTS: Mapping[str, int] = {
    "common": 113_822,
    "medium": 23_458,
    "android": 1_009,
}
_SOURCE_FINGERPRINT_STORE_COUNTS: Mapping[str, int] = dict(PRODUCTION_ROOT_COUNTS)
ROOT_PREFIXES: Mapping[str, str] = {
    "common": "WorldFlipper/dummy/download/production/upload/",
    "medium": "WorldFlipper/dummy/download/production/medium_upload/",
    "android": "WorldFlipper/dummy/download/production/android_upload/",
}
MARKER_PATHS = {
    "WorldFlipper/dummy/download/.empty",
    "WorldFlipper/dummy/info.json",
}
PATCH_ORDER = ("abyss-mode-equipment", "seris-phase4", "render-scale", "resource-version")
PASSWORD_ENV = "WF_OFFLINE_KEYSTORE_PASSWORD"
TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "offline-import-guide.zh-CN.txt"

REQUIRED_MANUAL_CHECKS = (
    "home_party_character_list_open",
    "original_character_1_and_129999_139999_149999_owned",
    "all_three_characters_enter_battle_and_use_skill",
    "seris_dual_form_skill_powerflip_results_stable",
    "gerald_scale_list_party_battle_correct",
    "rush_700099_round_reward_token_confirmed",
    "all_15_weapons_visible_one_obtained_and_equipped",
    "weapon_effect_whitelist_and_non_whitelist_confirmed",
    "save_button_force_stop_restart_restores_progress",
    "airplane_mode_held_no_companion_service",
)
REQUIRED_OFFLINE_PROBE_GATES = (
    "airplane_mode",
    "wifi_disabled",
    "mobile_disabled",
    "no_default_route",
    "no_active_network",
    "companion_ports_unused",
)

_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_BUILD_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_WINDOWS_ABSOLUTE_RE = re.compile(r"^[A-Za-z]:[\\/]")
_SENSITIVE_FIELD_NAMES = {
    "password",
    "passphrase",
    "key_password",
    "keystore_password",
    "private_key",
    "private_key_path",
    "key_path",
    "keystore_path",
    "receipt_path",
    "tool_path",
    "java_path",
    "ffdec_path",
    "aapt_path",
    "zipalign_path",
    "apksigner_path",
    "adb_path",
    "source_apk_path",
    "input_path",
}
_CREDENTIAL_SUFFIXES = (".jks", ".keystore", ".p12", ".pfx", ".pem", ".key")
_CREDENTIAL_BASENAMES = {"keystore-pass.txt"}
_PRIVATE_KEY_MARKERS = (
    b"-----BEGIN PRIVATE KEY-----",
    b"-----BEGIN ENCRYPTED PRIVATE KEY-----",
    b"-----BEGIN RSA PRIVATE KEY-----",
    b"-----BEGIN EC PRIVATE KEY-----",
    b"-----BEGIN OPENSSH PRIVATE KEY-----",
)
_PINNED_BASELINE_SECRET_FINDINGS = (
    (
        APK_NAME,
        "lib/arm64-v8a/libCore.so",
        "private-key-marker",
        "41b50823cbada646ced0999a724a5886fe2f48fc2f71a8ef26266064db3b0dfe",
        20_348_224,
    ),
)
_ARCHIVE_SUFFIXES = (".zip", ".apk")
MAX_ARCHIVE_MEMBERS = 150_000
MAX_ARCHIVE_TOTAL_UNCOMPRESSED_BYTES = 16 * 1024 * 1024 * 1024
_MAX_NESTED_ARCHIVE_BYTES = 128 * 1024 * 1024
_MAX_ARCHIVE_DEPTH = 4
_CHUNK_SIZE = 8 * 1024 * 1024
_FORBIDDEN_SELF_HASH_FIELDS = {
    "manifest_sha256",
    "build_manifest_sha256",
    "sha256sums_sha256",
}


class BundleError(RuntimeError):
    """Raised when a candidate or final release fails closed."""

    def __init__(self, message: object) -> None:
        scrubbed = str(message)
        configured = os.environ.get(PASSWORD_ENV)
        if configured:
            scrubbed = scrubbed.replace(configured, "<redacted>")
        super().__init__(scrubbed)


@dataclass(frozen=True, slots=True)
class CandidateIdentity:
    build_id: str
    apk_sha256: str
    data_zip_sha256: str
    guide_sha256: str
    evidence_sha256: str


@dataclass(frozen=True, slots=True)
class SecretFinding:
    relative_path: str
    container_member: str | None
    rule_id: str
    summary: str
    content_sha256: str | None = None
    content_size: int | None = None


@dataclass(slots=True)
class _OwnedDirectory:
    path: Path
    handle: int | None
    identity: tuple[int, int]


@dataclass(slots=True)
class _ArchiveBudget:
    members: int = 0
    declared_uncompressed_bytes: int = 0
    actual_uncompressed_bytes: int = 0


ReceiptValidator = Callable[[Path, CandidateIdentity], Any]


def _is_reparse(metadata: os.stat_result) -> bool:
    attributes = int(getattr(metadata, "st_file_attributes", 0))
    reparse_flag = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    return stat.S_ISLNK(metadata.st_mode) or bool(attributes & reparse_flag)


def _lexists(path: Path) -> bool:
    return os.path.lexists(os.fspath(path))


def _safe_label(value: str) -> str:
    cleaned = "".join(character if 32 <= ord(character) < 127 or ord(character) > 159 else "?" for character in value)
    return cleaned[:300]


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _require_hash(value: Any, label: str) -> str:
    if not isinstance(value, str) or _HASH_RE.fullmatch(value) is None:
        raise BundleError(f"{label} must be a lowercase SHA-256")
    return value


def _looks_absolute(value: str) -> bool:
    lowered = value.casefold()
    return (
        value.startswith("/")
        or value.startswith("\\")
        or _WINDOWS_ABSOLUTE_RE.match(value) is not None
        or lowered.startswith("file://")
    )


def _credential_name(value: str) -> bool:
    basename = value.replace("\\", "/").rsplit("/", 1)[-1].casefold()
    return basename in _CREDENTIAL_BASENAMES or basename.endswith(_CREDENTIAL_SUFFIXES)


def _normalise_json(value: Any, *, trail: tuple[str, ...] = ()) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        value = {field.name: getattr(value, field.name) for field in fields(value)}
    if isinstance(value, Mapping):
        output: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise BundleError("canonical JSON object keys must be strings")
            lowered = key.casefold()
            if lowered in _SENSITIVE_FIELD_NAMES:
                raise BundleError(f"sensitive field is forbidden: {key}")
            output[key] = _normalise_json(item, trail=trail + (key,))
        return output
    if isinstance(value, (list, tuple)):
        return [_normalise_json(item, trail=trail) for item in value]
    if isinstance(value, Path):
        raise BundleError("filesystem paths are not serializable in release evidence")
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise BundleError("canonical JSON numbers must be finite")
        return value
    if isinstance(value, str):
        if _looks_absolute(value):
            raise BundleError("absolute path is forbidden in release evidence")
        if _credential_name(value):
            raise BundleError("credential path is forbidden in release evidence")
        encoded = value.encode("utf-8", "strict")
        if any(marker in encoded for marker in _PRIVATE_KEY_MARKERS):
            raise BundleError("private-key material is forbidden in release evidence")
        return value
    raise BundleError(f"unsupported canonical JSON value type: {type(value).__name__}")


def canonical_json_bytes(value: Any) -> bytes:
    """Return stable UTF-8, sorted, compact JSON with exactly one LF."""

    normalised = _normalise_json(value)
    return (
        json.dumps(
            normalised,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise BundleError(f"duplicate JSON key is forbidden: {_safe_label(key)}")
        output[key] = value
    return output


def _reject_json_constant(value: str) -> None:
    raise BundleError(f"non-finite JSON constant is forbidden: {_safe_label(value)}")


def _strict_json(raw: bytes, *, label: str, require_canonical: bool = True) -> Mapping[str, Any]:
    try:
        text = raw.decode("utf-8", "strict")
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BundleError(f"{label} is not strict UTF-8 JSON") from exc
    if not isinstance(value, Mapping):
        raise BundleError(f"{label} must be a JSON object")
    if require_canonical and raw != canonical_json_bytes(value):
        raise BundleError(f"{label} is not canonical UTF-8/LF JSON")
    return value


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise BundleError(f"{label} must be an object")
    return value


def _require_true(value: Any, label: str) -> None:
    if value is not True:
        raise BundleError(f"{label} gate must be true")


def _contains_forbidden_self_hash(value: Any) -> bool:
    if isinstance(value, Mapping):
        if _FORBIDDEN_SELF_HASH_FIELDS & set(value):
            return True
        return any(_contains_forbidden_self_hash(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_forbidden_self_hash(item) for item in value)
    return False


def _entry_root(path: str) -> str | None:
    for root, prefix in ROOT_PREFIXES.items():
        if path.startswith(prefix):
            return root
    return None


def _validate_source_fingerprint(value: Any) -> dict[str, Any]:
    fingerprint = _require_mapping(value, "source_fingerprint")
    checkpoint_names = ("before", "scan", "after")
    if set(fingerprint) != {*checkpoint_names, "unchanged"}:
        raise BundleError("source_fingerprint schema must be exactly before, scan, after and unchanged")
    if fingerprint.get("unchanged") is not True:
        raise BundleError("source_fingerprint.unchanged must be true")

    checkpoint_fields = {
        "source_apk_sha256",
        "store_tree_sha256",
        "source_apk_size",
        "store_total_bytes",
        "store_counts",
    }
    checkpoints: dict[str, dict[str, Any]] = {}
    for name in checkpoint_names:
        checkpoint = _require_mapping(fingerprint.get(name), f"source_fingerprint.{name}")
        if set(checkpoint) != checkpoint_fields:
            raise BundleError(f"source_fingerprint.{name} checkpoint schema is invalid")
        source_hash = _require_hash(
            checkpoint.get("source_apk_sha256"),
            f"source_fingerprint.{name}.source_apk_sha256",
        )
        store_hash = _require_hash(
            checkpoint.get("store_tree_sha256"),
            f"source_fingerprint.{name}.store_tree_sha256",
        )
        source_size = checkpoint.get("source_apk_size")
        store_bytes = checkpoint.get("store_total_bytes")
        if type(source_size) is not int or source_size < 0:
            raise BundleError(f"source_fingerprint.{name}.source_apk_size must be nonnegative")
        if type(store_bytes) is not int or store_bytes < 0:
            raise BundleError(f"source_fingerprint.{name}.store_total_bytes must be nonnegative")
        store_counts = _require_mapping(
            checkpoint.get("store_counts"),
            f"source_fingerprint.{name}.store_counts",
        )
        if dict(store_counts) != dict(_SOURCE_FINGERPRINT_STORE_COUNTS):
            raise BundleError(
                f"source_fingerprint.{name}.store_counts must match the production three-root counts"
            )
        checkpoints[name] = {
            "source_apk_sha256": source_hash,
            "store_tree_sha256": store_hash,
            "source_apk_size": source_size,
            "store_total_bytes": store_bytes,
            "store_counts": dict(store_counts),
        }

    baseline = checkpoints["before"]
    for name in ("scan", "after"):
        checkpoint = checkpoints[name]
        hashes_equal = hmac.compare_digest(
            checkpoint["source_apk_sha256"], baseline["source_apk_sha256"]
        ) and hmac.compare_digest(
            checkpoint["store_tree_sha256"], baseline["store_tree_sha256"]
        )
        metadata_equal = (
            checkpoint["source_apk_size"] == baseline["source_apk_size"]
            and checkpoint["store_total_bytes"] == baseline["store_total_bytes"]
            and checkpoint["store_counts"] == baseline["store_counts"]
        )
        if not hashes_equal or not metadata_equal:
            raise BundleError(f"source fingerprint changed between before and {name}")
    return dict(fingerprint)


def validate_release_evidence(
    release_evidence: Mapping[str, Any],
    *,
    verify_entry_roots: bool = True,
) -> dict[str, Any]:
    """Validate and detach the evidence used to create the final manifest.

    ``verify_entry_roots=False`` exists for metadata-only validation of very
    large synthetic reports.  Candidate freezing always uses the strict default.
    """

    value = _normalise_json(release_evidence)
    assert isinstance(value, dict)
    if _contains_forbidden_self_hash(value):
        raise BundleError("release evidence must not contain a manifest self hash")
    required = {
        "source_fingerprint",
        "source_apk",
        "patches",
        "signer",
        "versions",
        "data",
        "player",
        "content",
        "apk",
        "gates",
        "git",
    }
    missing = sorted(required - set(value))
    if missing:
        raise BundleError(f"release evidence is missing fields: {', '.join(missing)}")
    unknown = sorted(set(value) - required)
    if unknown:
        raise BundleError(f"release evidence has unknown fields: {', '.join(unknown)}")

    source_fingerprint = _validate_source_fingerprint(value["source_fingerprint"])

    source_apk = _require_mapping(value["source_apk"], "source_apk")
    basename = source_apk.get("basename")
    if not isinstance(basename, str) or not basename or "/" in basename or "\\" in basename:
        raise BundleError("source_apk.basename must be a basename only")
    if not isinstance(source_apk.get("size"), int) or int(source_apk["size"]) < 0:
        raise BundleError("source_apk.size must be nonnegative")
    source_apk_hash = _require_hash(source_apk.get("sha256"), "source_apk.sha256")
    before_fingerprint = _require_mapping(source_fingerprint["before"], "source_fingerprint.before")
    if (
        not hmac.compare_digest(
            source_apk_hash,
            str(before_fingerprint["source_apk_sha256"]),
        )
        or source_apk["size"] != before_fingerprint["source_apk_size"]
    ):
        raise BundleError("source_apk evidence does not match the source fingerprint")

    patches = _require_mapping(value["patches"], "patches")
    _require_hash(patches.get("before_swf_sha256"), "patches.before_swf_sha256")
    _require_hash(patches.get("after_swf_sha256"), "patches.after_swf_sha256")
    if tuple(patches.get("order", ())) != PATCH_ORDER:
        raise BundleError("patch order must be abyss -> Seris -> render -> resource")

    signer = _require_mapping(value["signer"], "signer")
    signer_hash = _require_hash(signer.get("certificate_sha256"), "signer.certificate_sha256")

    versions = _require_mapping(value["versions"], "versions")
    expected_versions = {
        "source_resource_version": SOURCE_RESOURCE_VERSION,
        "output_resource_version": SNAPSHOT_VERSION,
        "snapshot_version": SNAPSHOT_VERSION,
    }
    if dict(versions) != expected_versions:
        raise BundleError("source/output/snapshot resource versions must remain distinct and locked")

    data = _require_mapping(value["data"], "data")
    _require_hash(data.get("archive_sha256"), "data.archive_sha256")
    entries = data.get("entries")
    if not isinstance(entries, list) or len(entries) != PRODUCTION_ENTRY_COUNT:
        raise BundleError(f"data manifest must contain exactly {PRODUCTION_ENTRY_COUNT} entries")
    if data.get("member_count") != PRODUCTION_ENTRY_COUNT:
        raise BundleError(f"data member_count must equal {PRODUCTION_ENTRY_COUNT}")
    if data.get("zip64") is not True:
        raise BundleError("data archive must have passed the Zip64 gate")
    if not isinstance(data.get("total_uncompressed_bytes"), int) or int(data["total_uncompressed_bytes"]) < 0:
        raise BundleError("data total_uncompressed_bytes must be nonnegative")
    roots = _require_mapping(data.get("roots"), "data.roots")
    if set(roots) != set(ROOT_PREFIXES):
        raise BundleError("data roots must be exactly common, medium and android")
    for root in ROOT_PREFIXES:
        root_report = _require_mapping(roots[root], f"data.roots.{root}")
        if root_report.get("count") != PRODUCTION_ROOT_COUNTS[root]:
            raise BundleError(f"data root count mismatch for {root}")
        if not isinstance(root_report.get("bytes"), int) or int(root_report["bytes"]) < 0:
            raise BundleError(f"data root bytes must be nonnegative for {root}")
        if root_report.get("archive_prefix") != ROOT_PREFIXES[root]:
            raise BundleError(f"data archive mapping mismatch for {root}")
    if sum(PRODUCTION_ROOT_COUNTS.values()) + len(MARKER_PATHS) != PRODUCTION_ENTRY_COUNT:
        raise BundleError("internal production root count contract is inconsistent")

    seen: set[str] = set()
    observed = {root: 0 for root in ROOT_PREFIXES}
    observed_bytes = {root: 0 for root in ROOT_PREFIXES}
    total_entry_bytes = 0
    markers: set[str] = set()
    for index, entry_value in enumerate(entries):
        entry = _require_mapping(entry_value, f"data.entries[{index}]")
        if set(entry) != {"path", "size", "sha256", "source"}:
            raise BundleError(f"data.entries[{index}] has an invalid schema")
        path = entry.get("path")
        if not isinstance(path, str) or not path.startswith("WorldFlipper/") or "\\" in path:
            raise BundleError(f"data.entries[{index}].path is not release-relative")
        pure = PurePosixPath(path)
        if pure.is_absolute() or ".." in pure.parts or "." in pure.parts:
            raise BundleError(f"data.entries[{index}].path is unsafe")
        folded = path.casefold()
        if folded in seen:
            raise BundleError(f"duplicate or casefold-colliding data entry: {_safe_label(path)}")
        seen.add(folded)
        if not isinstance(entry.get("size"), int) or int(entry["size"]) < 0:
            raise BundleError(f"data.entries[{index}].size must be nonnegative")
        total_entry_bytes += int(entry["size"])
        _require_hash(entry.get("sha256"), f"data.entries[{index}].sha256")
        source = entry.get("source")
        if path in MARKER_PATHS:
            if source != "generated-marker":
                raise BundleError(f"marker source mismatch: {_safe_label(path)}")
            markers.add(path)
        else:
            root = _entry_root(path)
            if root is None or source != root:
                raise BundleError(f"data entry root mapping mismatch: {_safe_label(path)}")
            observed[root] += 1
            observed_bytes[root] += int(entry["size"])
    if markers != MARKER_PATHS:
        raise BundleError("data manifest must contain both generated markers exactly once")
    if verify_entry_roots and observed != dict(PRODUCTION_ROOT_COUNTS):
        raise BundleError(f"data entry root counts do not match the three-root contract: {observed}")
    if verify_entry_roots:
        expected_root_bytes = {root: int(roots[root]["bytes"]) for root in ROOT_PREFIXES}
        if observed_bytes != expected_root_bytes:
            raise BundleError(f"data root byte totals do not match the three-root contract: {observed_bytes}")
        if total_entry_bytes != int(data["total_uncompressed_bytes"]):
            raise BundleError("data total uncompressed bytes do not match manifest entries")

    player = _require_mapping(value["player"], "player")
    if player.get("player_id") != "1000":
        raise BundleError("player overlay must bind Player 1000")
    if tuple(player.get("added_character_ids", ())) != ("129999", "139999", "149999"):
        raise BundleError("Player 1000 ID diff must add exactly 129999/139999/149999")
    if player.get("character_level") != 1:
        raise BundleError("initial character level must be 1")
    _require_hash(player.get("before_sha256"), "player.before_sha256")
    _require_hash(player.get("after_sha256"), "player.after_sha256")

    content = _require_mapping(value["content"], "content")
    _require_true(content.get("ready"), "content.ready")
    _require_true(content.get("client_gate_ready"), "content.client_gate_ready")
    rogue = _require_mapping(content.get("rogue"), "content.rogue")
    _require_true(rogue.get("ready"), "content.rogue.ready")
    if (rogue.get("event_id"), rogue.get("round_count"), rogue.get("token_id")) != (700099, 15, 2370099):
        raise BundleError("rogue content identity gate failed")
    characters = content.get("characters")
    expected_characters = {
        129999: "seris_dragon_king",
        139999: "stella_summer_goddess",
        149999: "white_wolf_gerald",
    }
    if not isinstance(characters, list) or len(characters) != len(expected_characters):
        raise BundleError("content must contain exactly the three release characters")
    observed_characters: dict[int, str] = {}
    for item in characters:
        report = _require_mapping(item, "content.characters[]")
        identity_report = _require_mapping(report.get("identity"), "content.characters[].identity")
        character_id = identity_report.get("character_id")
        code_name = identity_report.get("code_name")
        if not isinstance(character_id, int) or not isinstance(code_name, str):
            raise BundleError("character evidence identity is invalid")
        if character_id in observed_characters:
            raise BundleError("character evidence contains a duplicate identity")
        observed_characters[character_id] = code_name
        if (
            report.get("required_present"),
            report.get("required_total"),
            report.get("three_layer_consistent"),
            report.get("missing"),
        ) != (37, 37, True, []):
            raise BundleError("each character must be 37/37 and ready")
    if observed_characters != expected_characters:
        raise BundleError("content character identity mismatch")

    apk = _require_mapping(value["apk"], "apk")
    apk_hash = _require_hash(apk.get("output_sha256"), "apk.output_sha256")
    if _require_hash(apk.get("certificate_sha256"), "apk.certificate_sha256") != signer_hash:
        raise BundleError("APK signer certificate evidence mismatch")
    if apk.get("full_resource_version") != SNAPSHOT_VERSION:
        raise BundleError("APK full resource version mismatch")
    _require_true(apk.get("aligned"), "apk.aligned")
    _require_true(apk.get("verified"), "apk.verified")
    schemes = _require_mapping(apk.get("signature_schemes"), "apk.signature_schemes")
    for scheme in ("v1", "v2", "v3"):
        _require_true(schemes.get(scheme), f"apk.signature_schemes.{scheme}")
    if not apk_hash:
        raise BundleError("APK output hash is required")

    gates = _require_mapping(value["gates"], "gates")
    if not gates:
        raise BundleError("static gates cannot be empty")
    for name, gate in gates.items():
        _require_true(gate, f"gates.{name}")
    git = _require_mapping(value["git"], "git")
    if not isinstance(git.get("commit"), str) or not git["commit"]:
        raise BundleError("git.commit is required")
    if not isinstance(git.get("dirty"), bool):
        raise BundleError("git.dirty must record the worktree state")
    return value


def render_import_guide(*, snapshot_version: str = SNAPSHOT_VERSION) -> bytes:
    if snapshot_version != SNAPSHOT_VERSION:
        raise BundleError(f"the fixed import guide supports only {SNAPSHOT_VERSION}")
    try:
        metadata = TEMPLATE_PATH.lstat()
        if _is_reparse(metadata) or not stat.S_ISREG(metadata.st_mode):
            raise BundleError("import-guide template must be a regular non-reparse file")
        raw = TEMPLATE_PATH.read_bytes()
    except BundleError:
        raise
    except OSError as exc:
        raise BundleError("cannot read the tracked import-guide template") from exc
    try:
        raw.decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise BundleError("import-guide template is not UTF-8") from exc
    if b"\r" in raw or not raw.endswith(b"\n"):
        raise BundleError("import-guide template must use UTF-8 LF with a final newline")
    required = (
        "SHA256SUMS.txt",
        "WorldFlipper/save_haxe",
        APK_NAME,
        "所有文件访问权限",
        "直接解压到 /storage/emulated/0/",
        "/storage/emulated/0/WorldFlipper/dummy/download/production/upload/",
        "/storage/emulated/0/WorldFlipper/dummy/download/production/medium_upload/",
        "/storage/emulated/0/WorldFlipper/dummy/download/production/android_upload/",
        "/storage/emulated/0/WorldFlipper/dummy/info.json",
        "/storage/emulated/0/WorldFlipper/dummy/download/.empty",
        "禁止把 medium_upload 或 android_upload 扁平合并进 upload",
        "不能放在 Download 下",
        "不能多套一层 WorldFlipper",
        "飞行模式",
        "菜单点击“保存”",
        "129999/139999/149999",
        "ZIP 不覆盖个人进度",
    )
    text = raw.decode("utf-8")
    if not all(item in text for item in required):
        raise BundleError("import-guide template is missing a required operator instruction")
    return raw


def _path_identity(metadata: os.stat_result) -> tuple[int, int, int, int]:
    return (int(metadata.st_dev), int(metadata.st_ino), int(metadata.st_size), int(metadata.st_mtime_ns))


def _regular_metadata(path: Path, *, label: str) -> os.stat_result:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise BundleError(f"cannot inspect {label}: {_safe_label(path.name)}") from exc
    if _is_reparse(metadata):
        raise BundleError(f"{label} is a reparse point or symlink: {_safe_label(path.name)}")
    if not stat.S_ISREG(metadata.st_mode):
        raise BundleError(f"{label} is not a regular file: {_safe_label(path.name)}")
    return metadata


def _stream_hash(stream: BinaryIO) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    while True:
        chunk = stream.read(_CHUNK_SIZE)
        if not chunk:
            break
        size += len(chunk)
        digest.update(chunk)
    return size, digest.hexdigest()


def _hash_regular(path: Path, *, label: str) -> tuple[int, str]:
    before = _regular_metadata(path, label=label)
    try:
        with path.open("rb") as stream:
            opened = os.fstat(stream.fileno())
            if _is_reparse(opened) or not stat.S_ISREG(opened.st_mode):
                raise BundleError(f"{label} changed type while opening: {_safe_label(path.name)}")
            if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                raise BundleError(f"{label} identity drift while opening: {_safe_label(path.name)}")
            size, digest = _stream_hash(stream)
            after_open = os.fstat(stream.fileno())
    except BundleError:
        raise
    except OSError as exc:
        raise BundleError(f"cannot read {label}: {_safe_label(path.name)}") from exc
    after = _regular_metadata(path, label=label)
    if _path_identity(before) != _path_identity(after_open) or _path_identity(before) != _path_identity(after):
        raise BundleError(f"{label} drifted while hashing: {_safe_label(path.name)}")
    if size != before.st_size:
        raise BundleError(f"{label} size drift while hashing: {_safe_label(path.name)}")
    return size, digest


def _write_exclusive(path: Path, payload: bytes) -> None:
    try:
        with path.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as exc:
        raise BundleError(f"output already exists: {_safe_label(path.name)}") from exc
    except OSError as exc:
        raise BundleError(f"cannot write output: {_safe_label(path.name)}") from exc


def _copy_exclusive(source: Path, destination: Path, *, expected_hash: str | None = None) -> tuple[int, str]:
    before = _regular_metadata(source, label="release source")
    digest = hashlib.sha256()
    size = 0
    try:
        with source.open("rb") as reader:
            opened = os.fstat(reader.fileno())
            if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                raise BundleError(f"release source identity drift: {_safe_label(source.name)}")
            with destination.open("xb") as writer:
                while True:
                    chunk = reader.read(_CHUNK_SIZE)
                    if not chunk:
                        break
                    writer.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
                writer.flush()
                os.fsync(writer.fileno())
            after_open = os.fstat(reader.fileno())
    except BundleError:
        raise
    except FileExistsError as exc:
        raise BundleError(f"output already exists: {_safe_label(destination.name)}") from exc
    except OSError as exc:
        raise BundleError(f"cannot copy release source: {_safe_label(source.name)}") from exc
    after = _regular_metadata(source, label="release source")
    if _path_identity(before) != _path_identity(after_open) or _path_identity(before) != _path_identity(after):
        raise BundleError(f"release source drift while copying: {_safe_label(source.name)}")
    actual = digest.hexdigest()
    if size != before.st_size:
        raise BundleError(f"release source size drift while copying: {_safe_label(source.name)}")
    if expected_hash is not None and not hmac.compare_digest(actual, expected_hash):
        raise BundleError(f"release source hash drift: {_safe_label(source.name)}")
    return size, actual


def _directory_metadata(path: Path, *, label: str) -> os.stat_result:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise BundleError(f"cannot inspect {label}: {_safe_label(path.name)}") from exc
    if _is_reparse(metadata):
        raise BundleError(f"{label} is a reparse point or symlink: {_safe_label(path.name)}")
    if not stat.S_ISDIR(metadata.st_mode):
        raise BundleError(f"{label} is not a directory: {_safe_label(path.name)}")
    return metadata


def _windows_file_api():
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.GetFileInformationByHandle.argtypes = (
        wintypes.HANDLE,
        ctypes.c_void_p,
    )
    kernel32.GetFileInformationByHandle.restype = wintypes.BOOL
    kernel32.SetFileInformationByHandle.argtypes = (
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
    )
    kernel32.SetFileInformationByHandle.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    return wintypes, kernel32


def _directory_handle_info(raw_handle: int) -> tuple[int, tuple[int, int]]:
    from ctypes import wintypes

    class ByHandleFileInformation(ctypes.Structure):
        _fields_ = (
            ("dwFileAttributes", wintypes.DWORD),
            ("ftCreationTime", wintypes.FILETIME),
            ("ftLastAccessTime", wintypes.FILETIME),
            ("ftLastWriteTime", wintypes.FILETIME),
            ("dwVolumeSerialNumber", wintypes.DWORD),
            ("nFileSizeHigh", wintypes.DWORD),
            ("nFileSizeLow", wintypes.DWORD),
            ("nNumberOfLinks", wintypes.DWORD),
            ("nFileIndexHigh", wintypes.DWORD),
            ("nFileIndexLow", wintypes.DWORD),
        )

    _wintypes, kernel32 = _windows_file_api()
    info = ByHandleFileInformation()
    if not kernel32.GetFileInformationByHandle(raw_handle, ctypes.byref(info)):
        raise ctypes.WinError(ctypes.get_last_error())
    identity = (
        int(info.dwVolumeSerialNumber),
        (int(info.nFileIndexHigh) << 32) | int(info.nFileIndexLow),
    )
    if identity[0] == 0 or identity[1] == 0:
        raise BundleError("directory has no stable nonzero identity")
    return int(info.dwFileAttributes), identity


def _open_raw_directory(
    path: Path,
    *,
    deny_delete: bool,
    request_delete: bool,
) -> _OwnedDirectory:
    target = Path(path)
    if os.name != "nt":
        metadata = _directory_metadata(target, label="bound directory")
        return _OwnedDirectory(target, None, (int(metadata.st_dev), int(metadata.st_ino)))

    _wintypes, kernel32 = _windows_file_api()
    access = 0x0001 | 0x0080
    if request_delete:
        access |= 0x00010000
    share = 0x00000001 | 0x00000002
    if not deny_delete:
        share |= 0x00000004
    raw_handle = kernel32.CreateFileW(
        str(target),
        access,
        share,
        None,
        3,
        0x02000000 | 0x00200000,
        None,
    )
    if raw_handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        attributes, identity = _directory_handle_info(int(raw_handle))
        if not attributes & 0x10:
            raise BundleError("bound filesystem object is not a directory")
        if attributes & 0x400:
            raise BundleError("bound directory must not be a reparse point")
        return _OwnedDirectory(target, int(raw_handle), identity)
    except BaseException:
        kernel32.CloseHandle(raw_handle)
        raise


def _open_destination_directory(
    path: Path,
    *,
    deny_delete: bool,
    request_delete: bool = True,
) -> _OwnedDirectory:
    try:
        return _open_raw_directory(
            Path(path),
            deny_delete=deny_delete,
            request_delete=request_delete,
        )
    except BundleError:
        raise
    except OSError as exc:
        raise BundleError("cannot bind destination directory") from exc


def _close_owned_directory(owned: _OwnedDirectory) -> None:
    if owned.handle is None:
        return
    _wintypes, kernel32 = _windows_file_api()
    raw_handle = owned.handle
    owned.handle = None
    kernel32.CloseHandle(raw_handle)


def _directory_identity_at_path(path: Path) -> tuple[int, int]:
    opened = _open_raw_directory(
        Path(path),
        deny_delete=False,
        request_delete=False,
    )
    try:
        return opened.identity
    finally:
        _close_owned_directory(opened)


def _require_owned_directory_identity(owned: _OwnedDirectory, *, label: str) -> None:
    if os.name == "nt" and owned.handle is None:
        raise BundleError(f"{label} handle is closed")
    try:
        actual = _directory_identity_at_path(owned.path)
    except (BundleError, OSError) as exc:
        raise BundleError(f"{label} identity changed") from exc
    if actual != owned.identity:
        raise BundleError(f"{label} identity changed")


def _mark_directory_handle_for_delete(owned: _OwnedDirectory) -> None:
    from ctypes import wintypes

    class FileDispositionInfo(ctypes.Structure):
        _fields_ = (("DeleteFile", wintypes.BOOLEAN),)

    if os.name != "nt" or owned.handle is None:
        raise BundleError("directory delete handle is unavailable")
    _wintypes, kernel32 = _windows_file_api()
    disposition = FileDispositionInfo(True)
    if not kernel32.SetFileInformationByHandle(
        owned.handle,
        4,
        ctypes.byref(disposition),
        ctypes.sizeof(disposition),
    ):
        raise ctypes.WinError(ctypes.get_last_error())


def _create_owned_directory(path: Path) -> _OwnedDirectory:
    try:
        path.mkdir(mode=0o700)
    except FileExistsError as exc:
        raise BundleError(f"temporary output already exists: {_safe_label(path.name)}") from exc
    except OSError as exc:
        raise BundleError(f"cannot create temporary output: {_safe_label(path.name)}") from exc
    try:
        owned = _open_destination_directory(path, deny_delete=True)
        _require_owned_directory_identity(owned, label="owned temporary directory")
        return owned
    except BaseException as exc:
        error = BundleError("cannot bind owned temporary directory")
        error.add_note("unbound temporary path was preserved; recursive path cleanup is forbidden")
        raise error from exc


def _remove_owned_temp_tree(owned: _OwnedDirectory) -> None:
    expected_identity = owned.identity
    cleanup_error: BaseException | None = None
    try:
        _require_owned_directory_identity(owned, label="owned temporary directory")
        for child in tuple(owned.path.iterdir()):
            metadata = child.lstat()
            if _is_reparse(metadata) or not stat.S_ISREG(metadata.st_mode):
                raise BundleError("owned temporary directory contains a non-regular member")
            child.unlink()
        _require_owned_directory_identity(owned, label="owned temporary directory")
        if any(owned.path.iterdir()):
            raise BundleError("owned temporary directory is not empty after cleanup")
        if os.name == "nt":
            _mark_directory_handle_for_delete(owned)
        else:
            owned.path.rmdir()
    except FileNotFoundError:
        pass
    except BaseException as exc:
        cleanup_error = exc
    finally:
        _close_owned_directory(owned)
    if cleanup_error is not None:
        raise BundleError("cannot clean handle-bound temporary directory") from cleanup_error

    # Never remove the root by pathname.  A same-name competitor appearing
    # after the exact handle closes is not ours and must be preserved.
    if _lexists(owned.path):
        try:
            current_identity = _directory_identity_at_path(owned.path)
        except (BundleError, OSError):
            return
        if current_identity == expected_identity:
            raise BundleError("owned temporary directory remains after handle cleanup")


def _volume_identity(path: Path) -> int:
    metadata = _directory_metadata(path, label="volume anchor")
    return int(metadata.st_dev)


def _require_same_volume(candidate_dir: Path, final_parent: Path) -> None:
    if _volume_identity(candidate_dir) != _volume_identity(final_parent):
        raise BundleError("candidate and final directory must be on the same volume")


def _paths_overlap(first: Path, second: Path) -> bool:
    first_text = os.path.normcase(os.path.abspath(os.fspath(first)))
    second_text = os.path.normcase(os.path.abspath(os.fspath(second)))
    try:
        common = os.path.normcase(os.path.commonpath((first_text, second_text)))
    except ValueError:
        return False
    return common in {first_text, second_text}


def _publish_directory_no_replace(source: Path, destination: Path) -> None:
    """POSIX no-replace fallback; Windows publication must use a bound handle."""

    if os.name == "nt":
        raise BundleError("path-based Windows directory publication is forbidden")

    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is not None:
        renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        renameat2.restype = ctypes.c_int
        if renameat2(-100, os.fsencode(source), -100, os.fsencode(destination), 1) == 0:
            return
        error = ctypes.get_errno()
        if error == errno.EEXIST:
            raise BundleError(f"final output already exists: {_safe_label(destination.name)}")
        raise BundleError(f"atomic directory publication failed: {_safe_label(destination.name)}")
    renamex = getattr(libc, "renamex_np", None)
    if renamex is not None:
        renamex.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        renamex.restype = ctypes.c_int
        if renamex(os.fsencode(source), os.fsencode(destination), 0x4) == 0:
            return
        error = ctypes.get_errno()
        if error == errno.EEXIST:
            raise BundleError(f"final output already exists: {_safe_label(destination.name)}")
        raise BundleError(f"atomic directory publication failed: {_safe_label(destination.name)}")
    raise BundleError("atomic no-overwrite directory publication is unavailable")


def _publish_owned_directory_no_replace(
    owned: _OwnedDirectory,
    parent: _OwnedDirectory,
    destination: Path,
) -> None:
    """Publish the exact verified directory object, never a reused pathname."""

    target = Path(destination)
    if target.name in {"", ".", ".."}:
        raise BundleError("publication destination must have one directory name")
    if os.path.normcase(os.path.abspath(target.parent)) != os.path.normcase(
        os.path.abspath(parent.path)
    ):
        raise BundleError("publication destination parent mismatch")
    _require_owned_directory_identity(parent, label="publication parent")
    _require_owned_directory_identity(owned, label="verified temporary directory")

    if os.name != "nt":
        _publish_directory_no_replace(owned.path, target)
        owned.path = target
    else:
        from ctypes import wintypes

        class FileRenameInfo(ctypes.Structure):
            _fields_ = (
                ("ReplaceIfExists", wintypes.BOOLEAN),
                ("RootDirectory", wintypes.HANDLE),
                ("FileNameLength", wintypes.DWORD),
                ("FileName", wintypes.WCHAR * 1),
            )

        if owned.handle is None:
            raise BundleError("verified temporary directory handle is closed")
        _wintypes, kernel32 = _windows_file_api()
        encoded_name = str(target).encode("utf-16-le")
        buffer_size = FileRenameInfo.FileName.offset + len(encoded_name)
        buffer = ctypes.create_string_buffer(buffer_size + 2)
        rename = FileRenameInfo.from_buffer(buffer)
        rename.ReplaceIfExists = False
        rename.RootDirectory = None
        rename.FileNameLength = len(encoded_name)
        ctypes.memmove(
            ctypes.addressof(buffer) + FileRenameInfo.FileName.offset,
            encoded_name,
            len(encoded_name),
        )
        if not kernel32.SetFileInformationByHandle(
            owned.handle,
            3,
            buffer,
            buffer_size + 2,
        ):
            if _lexists(target):
                raise BundleError(f"final output already exists: {_safe_label(target.name)}")
            raise BundleError(f"handle-bound directory publication failed: {_safe_label(target.name)}")
        owned.path = target

    _require_owned_directory_identity(parent, label="publication parent")
    _require_owned_directory_identity(owned, label="published directory")


def _configured_secret_values() -> tuple[str, ...]:
    value = os.environ.get(PASSWORD_ENV)
    return (value,) if value else ()


def _secret_patterns(secret_values: Sequence[str]) -> tuple[tuple[str, bytes], ...]:
    output: list[tuple[str, bytes]] = []
    seen: set[bytes] = set()
    for value in secret_values:
        if not isinstance(value, str) or not value:
            continue
        for encoding in ("utf-8", "utf-16le", "utf-16be"):
            payload = value.encode(encoding)
            if payload and payload not in seen:
                seen.add(payload)
                output.append(("configured-secret", payload))
    for marker in _PRIVATE_KEY_MARKERS:
        if marker not in seen:
            seen.add(marker)
            output.append(("private-key-marker", marker))
    return tuple(output)


def _name_finding(relative: str, member: str | None) -> SecretFinding:
    return SecretFinding(relative, member, "credential-filename", "forbidden credential filename detected")


def _content_findings(
    stream: BinaryIO,
    *,
    relative: str,
    member: str | None,
    patterns: Sequence[tuple[str, bytes]],
    expected_size: int | None = None,
    archive_budget: _ArchiveBudget | None = None,
) -> list[SecretFinding]:
    found: set[str] = set()
    longest = max((len(payload) for _, payload in patterns), default=1)
    tail = b""
    total = 0
    digest = hashlib.sha256()
    while True:
        chunk = stream.read(_CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        digest.update(chunk)
        if archive_budget is not None:
            archive_budget.actual_uncompressed_bytes += len(chunk)
            if archive_budget.actual_uncompressed_bytes > MAX_ARCHIVE_TOTAL_UNCOMPRESSED_BYTES:
                raise BundleError("archive actual uncompressed byte budget exceeded")
        window = tail + chunk
        for rule, payload in patterns:
            if rule not in found and payload in window:
                found.add(rule)
        tail = window[-(longest - 1) :] if longest > 1 else b""
    if expected_size is not None and total != expected_size:
        raise BundleError("archive member declared size drift")
    content_sha256 = digest.hexdigest()
    return [
        SecretFinding(
            relative,
            member,
            rule,
            (
                "configured credential bytes detected"
                if rule == "configured-secret"
                else "private-key material detected"
            ),
            content_sha256,
            total,
        )
        for rule in sorted(found)
    ]


def _validate_archive_member_name(name: str) -> None:
    if not name or "\\" in name or "\x00" in name:
        raise BundleError("archive contains an unsafe member name")
    pure = PurePosixPath(name)
    if pure.is_absolute() or ".." in pure.parts or "." in pure.parts:
        raise BundleError("archive contains an unsafe member path")


def _zip_member_is_symlink(info: zipfile.ZipInfo) -> bool:
    return info.create_system == 3 and stat.S_ISLNK((info.external_attr >> 16) & 0xFFFF)


def _scan_archive(
    archive_source: Path | BinaryIO,
    *,
    relative: str,
    chain: str | None,
    patterns: Sequence[tuple[str, bytes]],
    depth: int,
    budget: _ArchiveBudget | None = None,
) -> list[SecretFinding]:
    if depth > _MAX_ARCHIVE_DEPTH:
        raise BundleError(f"nested archive depth exceeded: {_safe_label(relative)}")
    findings: list[SecretFinding] = []
    if budget is None:
        budget = _ArchiveBudget()
    try:
        with zipfile.ZipFile(archive_source, "r") as archive:
            infos = archive.infolist()
            budget.members += len(infos)
            if budget.members > MAX_ARCHIVE_MEMBERS:
                raise BundleError("archive member count budget exceeded")
            declared = 0
            for info in infos:
                if not isinstance(info.file_size, int) or info.file_size < 0:
                    raise BundleError("archive member has an invalid declared size")
                declared += info.file_size
            budget.declared_uncompressed_bytes += declared
            if budget.declared_uncompressed_bytes > MAX_ARCHIVE_TOTAL_UNCOMPRESSED_BYTES:
                raise BundleError("archive declared uncompressed byte budget exceeded")
            seen: set[str] = set()
            for info in infos:
                _validate_archive_member_name(info.filename)
                folded = info.filename.casefold()
                if folded in seen:
                    raise BundleError(f"archive contains duplicate members: {_safe_label(relative)}")
                seen.add(folded)
                member_chain = info.filename if chain is None else f"{chain}!{info.filename}"
                if _credential_name(info.filename):
                    findings.append(_name_finding(relative, member_chain))
                if info.is_dir():
                    continue
                if _zip_member_is_symlink(info):
                    raise BundleError(f"archive contains a symlink member: {_safe_label(relative)}")
                if info.flag_bits & 0x1:
                    raise BundleError(f"archive contains an encrypted member: {_safe_label(relative)}")
                nested = info.filename.casefold().endswith(_ARCHIVE_SUFFIXES)
                with archive.open(info, "r") as stream:
                    if nested:
                        if info.file_size > _MAX_NESTED_ARCHIVE_BYTES:
                            raise BundleError(f"nested archive is too large to scan: {_safe_label(relative)}")
                        payload = stream.read(_MAX_NESTED_ARCHIVE_BYTES + 1)
                        budget.actual_uncompressed_bytes += len(payload)
                        if budget.actual_uncompressed_bytes > MAX_ARCHIVE_TOTAL_UNCOMPRESSED_BYTES:
                            raise BundleError("archive actual uncompressed byte budget exceeded")
                        if len(payload) != info.file_size or len(payload) > _MAX_NESTED_ARCHIVE_BYTES:
                            raise BundleError(f"nested archive size drift: {_safe_label(relative)}")
                        findings.extend(
                            _content_findings(
                                io.BytesIO(payload),
                                relative=relative,
                                member=member_chain,
                                patterns=patterns,
                            )
                        )
                        findings.extend(
                            _scan_archive(
                                io.BytesIO(payload),
                                relative=relative,
                                chain=member_chain,
                                patterns=patterns,
                                depth=depth + 1,
                                budget=budget,
                            )
                        )
                    else:
                        findings.extend(
                            _content_findings(
                                stream,
                                relative=relative,
                                member=member_chain,
                                patterns=patterns,
                                expected_size=info.file_size,
                                archive_budget=budget,
                            )
                        )
    except BundleError:
        raise
    except (OSError, zipfile.BadZipFile, RuntimeError, EOFError) as exc:
        raise BundleError(f"cannot safely scan archive: {_safe_label(relative)}") from exc
    return findings


def _open_regular_for_scan(path: Path):
    return path.open("rb")


def _scan_regular_path(
    path: Path,
    *,
    relative: str,
    secret_patterns: Sequence[tuple[str, bytes]],
) -> list[SecretFinding]:
    before = _regular_metadata(path, label="secret-scan member")
    findings: list[SecretFinding] = []
    is_archive = relative.casefold().endswith(_ARCHIVE_SUFFIXES)
    if _credential_name(relative):
        findings.append(_name_finding(relative, None))
    try:
        with _open_regular_for_scan(path) as stream:
            opened = os.fstat(stream.fileno())
            if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                raise BundleError(f"secret-scan member identity drift: {_safe_label(relative)}")
            findings.extend(
                _content_findings(
                    stream,
                    relative=relative,
                    member=None,
                    patterns=secret_patterns,
                )
            )
            if is_archive:
                stream.seek(0)
                findings.extend(
                    _scan_archive(
                        stream,
                        relative=relative,
                        chain=None,
                        patterns=secret_patterns,
                        depth=0,
                    )
                )
            after_open = os.fstat(stream.fileno())
    except BundleError:
        raise
    except (OSError, PermissionError) as exc:
        raise BundleError(f"cannot read secret-scan member: {_safe_label(relative)}") from exc
    after = _regular_metadata(path, label="secret-scan member")
    if _path_identity(before) != _path_identity(after_open) or _path_identity(before) != _path_identity(after):
        raise BundleError(f"secret-scan member drift: {_safe_label(relative)}")
    return findings


def _walk_regular_files(root: Path) -> tuple[tuple[Path, str], ...]:
    root_metadata = _directory_metadata(root, label="secret-scan root")
    root_identity = (root_metadata.st_dev, root_metadata.st_ino)
    output: list[tuple[Path, str]] = []

    def visit(directory: Path, relative_parent: PurePosixPath) -> None:
        metadata = _directory_metadata(directory, label="secret-scan directory")
        try:
            with os.scandir(directory) as iterator:
                entries = sorted(iterator, key=lambda item: item.name.casefold())
        except OSError as exc:
            raise BundleError(f"cannot enumerate secret-scan directory: {_safe_label(directory.name)}") from exc
        seen: set[str] = set()
        for entry in entries:
            folded = entry.name.casefold()
            if folded in seen:
                raise BundleError("secret-scan tree contains casefold-colliding names")
            seen.add(folded)
            path = Path(entry.path)
            try:
                child = entry.stat(follow_symlinks=False)
            except OSError as exc:
                raise BundleError(f"cannot inspect secret-scan member: {_safe_label(entry.name)}") from exc
            relative = relative_parent / entry.name
            if _is_reparse(child):
                raise BundleError(f"secret-scan tree contains a reparse point or symlink: {_safe_label(entry.name)}")
            if stat.S_ISDIR(child.st_mode):
                visit(path, relative)
            elif stat.S_ISREG(child.st_mode):
                output.append((path, relative.as_posix()))
            else:
                raise BundleError(f"secret-scan tree contains a non-regular member: {_safe_label(entry.name)}")
        after = _directory_metadata(directory, label="secret-scan directory")
        if (metadata.st_dev, metadata.st_ino, metadata.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_mtime_ns):
            raise BundleError(f"secret-scan directory drift: {_safe_label(directory.name)}")

    visit(root, PurePosixPath())
    after_root = _directory_metadata(root, label="secret-scan root")
    if (after_root.st_dev, after_root.st_ino) != root_identity:
        raise BundleError("secret-scan root identity drift")
    return tuple(output)


def scan_release_for_secrets(
    release_root: Path,
    *,
    secret_values: Sequence[str] = (),
) -> tuple[SecretFinding, ...]:
    root = Path(release_root)
    patterns = _secret_patterns(tuple(secret_values))
    findings: list[SecretFinding] = []
    for path, relative in _walk_regular_files(root):
        findings.extend(_scan_regular_path(path, relative=relative, secret_patterns=patterns))
    return tuple(
        sorted(
            findings,
            key=lambda item: (item.relative_path, item.container_member or "", item.rule_id),
        )
    )


def _require_no_findings(findings: Sequence[SecretFinding]) -> None:
    if findings:
        first = findings[0]
        raise BundleError(
            f"release secret scan failed [{first.rule_id}]; finding_count={len(findings)}"
        )


def _secret_finding_key(
    finding: SecretFinding,
) -> tuple[str, str | None, str, str | None, int | None]:
    return (
        finding.relative_path,
        finding.container_member,
        finding.rule_id,
        finding.content_sha256,
        finding.content_size,
    )


def validate_release_secret_findings(
    findings: Sequence[SecretFinding],
) -> dict[str, int | bool]:
    """Require the one immutable encrypted-key marker already pinned in the base APK."""
    try:
        actual = Counter(_secret_finding_key(finding) for finding in findings)
    except (AttributeError, TypeError) as exc:
        raise BundleError(
            f"release secret scan failed [invalid-finding]; finding_count={len(findings)}"
        ) from exc
    expected = Counter(_PINNED_BASELINE_SECRET_FINDINGS)
    if actual != expected:
        first_rule = (
            findings[0].rule_id
            if findings and isinstance(findings[0], SecretFinding)
            else "baseline-mismatch"
        )
        raise BundleError(
            f"release secret scan failed [{first_rule}]; finding_count={len(findings)}"
        )
    return {
        "secret_finding_count": 0,
        "baseline_secret_finding_count": sum(expected.values()),
        "baseline_secret_verified": True,
        "raw_secret_finding_count": len(findings),
    }


def _identity_document(identity: CandidateIdentity) -> dict[str, str]:
    return {
        "build_id": identity.build_id,
        "apk_sha256": identity.apk_sha256,
        "data_zip_sha256": identity.data_zip_sha256,
        "guide_sha256": identity.guide_sha256,
        "evidence_sha256": identity.evidence_sha256,
    }


def _candidate_identity(value: Mapping[str, Any]) -> CandidateIdentity:
    build_id = value.get("build_id")
    if not isinstance(build_id, str) or _BUILD_ID_RE.fullmatch(build_id) is None:
        raise BundleError("candidate build_id is invalid")
    return CandidateIdentity(
        build_id,
        _require_hash(value.get("apk_sha256"), "candidate.apk_sha256"),
        _require_hash(value.get("data_zip_sha256"), "candidate.data_zip_sha256"),
        _require_hash(value.get("guide_sha256"), "candidate.guide_sha256"),
        _require_hash(value.get("evidence_sha256"), "candidate.evidence_sha256"),
    )


def _release_evidence_sha256(evidence: Mapping[str, Any]) -> str:
    """Hash only the canonical release-evidence payload, avoiding self-reference."""

    return _sha256_bytes(canonical_json_bytes(evidence))


def freeze_candidate(
    apk_path: Path,
    data_zip_path: Path,
    guide_bytes: bytes,
    candidate_dir: Path,
    *,
    build_id: str,
    release_evidence: Mapping[str, Any],
) -> CandidateIdentity:
    apk = Path(apk_path)
    data_zip = Path(data_zip_path)
    candidate = Path(candidate_dir)
    if not isinstance(guide_bytes, bytes):
        raise BundleError("the rendered import guide must be bytes")
    if guide_bytes != render_import_guide():
        raise BundleError("candidate import guide does not match the fixed tracked template")
    if not isinstance(build_id, str) or _BUILD_ID_RE.fullmatch(build_id) is None:
        raise BundleError("candidate build_id is invalid")
    if _lexists(candidate):
        raise BundleError(f"candidate already exists: {_safe_label(candidate.name)}")
    parent = candidate.parent
    _directory_metadata(parent, label="candidate parent")
    evidence = validate_release_evidence(release_evidence)
    apk_size, apk_hash = _hash_regular(apk, label="signed APK")
    zip_size, data_hash = _hash_regular(data_zip, label="data ZIP")
    if not hmac.compare_digest(str(evidence["apk"]["output_sha256"]), apk_hash):
        raise BundleError("APK report hash does not match the candidate APK")
    if not hmac.compare_digest(str(evidence["data"]["archive_sha256"]), data_hash):
        raise BundleError("ZIP report hash does not match the candidate data ZIP")
    identity = CandidateIdentity(
        build_id,
        apk_hash,
        data_hash,
        _sha256_bytes(guide_bytes),
        _release_evidence_sha256(evidence),
    )
    document = {
        "schema_version": 1,
        "identity": _identity_document(identity),
        "artifact_sizes": {"apk": apk_size, "data_zip": zip_size, "guide": len(guide_bytes)},
        "release_evidence": evidence,
    }
    temp = parent / f".{candidate.name}.freezing-{uuid.uuid4().hex}"
    parent_owned = _open_destination_directory(
        parent,
        deny_delete=True,
        request_delete=False,
    )
    owned: _OwnedDirectory | None = None
    try:
        owned = _create_owned_directory(temp)
        _copy_exclusive(apk, temp / APK_NAME, expected_hash=apk_hash)
        _copy_exclusive(data_zip, temp / DATA_ZIP_NAME, expected_hash=data_hash)
        _write_exclusive(temp / GUIDE_NAME, guide_bytes)
        _write_exclusive(temp / CANDIDATE_EVIDENCE_NAME, canonical_json_bytes(document))
        validate_release_secret_findings(
            scan_release_for_secrets(temp, secret_values=_configured_secret_values())
        )
        verified_identity, _verified_evidence = _rehash_frozen_candidate(temp)
        if verified_identity != identity:
            raise BundleError("frozen candidate identity changed before publication")
        _publish_owned_directory_no_replace(owned, parent_owned, candidate)
        published_identity, _published_evidence = _rehash_frozen_candidate(candidate)
        if published_identity != identity:
            raise BundleError("published candidate identity changed")
    except BaseException as original_error:
        if owned is not None:
            try:
                _remove_owned_temp_tree(owned)
            except BaseException as cleanup_error:
                original_error.add_note(
                    "handle-bound candidate rollback failed: "
                    f"{type(cleanup_error).__name__}"
                )
        raise
    else:
        if owned is not None:
            _close_owned_directory(owned)
    finally:
        _close_owned_directory(parent_owned)
    return identity


def _exact_regular_files(root: Path, expected: Sequence[str], *, label: str) -> None:
    _directory_metadata(root, label=label)
    try:
        with os.scandir(root) as iterator:
            entries = sorted(iterator, key=lambda item: item.name)
    except OSError as exc:
        raise BundleError(f"cannot enumerate {label}") from exc
    names = tuple(entry.name for entry in entries)
    if set(names) != set(expected) or len(names) != len(expected):
        wording = "exactly five files" if tuple(expected) == FINAL_FILES else "the exact frozen candidate files"
        raise BundleError(f"{label} must contain {wording}")
    for entry in entries:
        try:
            metadata = entry.stat(follow_symlinks=False)
        except OSError as exc:
            raise BundleError(f"cannot inspect {label} member: {_safe_label(entry.name)}") from exc
        if _is_reparse(metadata) or not stat.S_ISREG(metadata.st_mode):
            raise BundleError(f"{label} member is reparse or non-regular: {_safe_label(entry.name)}")


def _read_canonical_file(path: Path, *, label: str) -> Mapping[str, Any]:
    raw = _read_regular_snapshot(path, label=label)
    return _strict_json(raw, label=label, require_canonical=True)


def _read_regular_snapshot(path: Path, *, label: str) -> bytes:
    before = _regular_metadata(path, label=label)
    try:
        with path.open("rb") as stream:
            opened = os.fstat(stream.fileno())
            if _is_reparse(opened) or not stat.S_ISREG(opened.st_mode):
                raise BundleError(f"{label} changed type while opening: {_safe_label(path.name)}")
            if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                raise BundleError(f"{label} identity drift while opening: {_safe_label(path.name)}")
            raw = stream.read()
            after_open = os.fstat(stream.fileno())
    except BundleError:
        raise
    except OSError as exc:
        raise BundleError(f"cannot read {label}: {_safe_label(path.name)}") from exc
    after = _regular_metadata(path, label=label)
    if _path_identity(before) != _path_identity(after_open) or _path_identity(before) != _path_identity(after):
        raise BundleError(f"{label} drift while reading: {_safe_label(path.name)}")
    if len(raw) != before.st_size:
        raise BundleError(f"{label} size drift while reading: {_safe_label(path.name)}")
    return raw


def _rehash_frozen_candidate(candidate_dir: Path) -> tuple[CandidateIdentity, dict[str, Any]]:
    candidate = Path(candidate_dir)
    _exact_regular_files(candidate, CANDIDATE_FILES, label="candidate directory")
    document = _read_canonical_file(candidate / CANDIDATE_EVIDENCE_NAME, label="candidate evidence")
    if document.get("schema_version") != 1:
        raise BundleError("candidate evidence schema mismatch")
    identity = _candidate_identity(_require_mapping(document.get("identity"), "candidate identity"))
    evidence = validate_release_evidence(_require_mapping(document.get("release_evidence"), "release evidence"))
    if not hmac.compare_digest(identity.evidence_sha256, _release_evidence_sha256(evidence)):
        raise BundleError("candidate release evidence hash mismatch")
    sizes = _require_mapping(document.get("artifact_sizes"), "candidate artifact_sizes")
    observed: dict[str, tuple[int, str]] = {
        "apk": _hash_regular(candidate / APK_NAME, label="frozen APK"),
        "guide": _hash_regular(candidate / GUIDE_NAME, label="frozen guide"),
    }
    observed["data_zip"] = _verify_data_archive(
        candidate / DATA_ZIP_NAME,
        evidence["data"]["entries"],
        expected_archive_sha256=identity.data_zip_sha256,
        label="candidate",
    )
    expected = {
        "apk": (sizes.get("apk"), identity.apk_sha256),
        "data_zip": (sizes.get("data_zip"), identity.data_zip_sha256),
        "guide": (sizes.get("guide"), identity.guide_sha256),
    }
    for name in expected:
        if observed[name][0] != expected[name][0] or not hmac.compare_digest(observed[name][1], str(expected[name][1])):
            raise BundleError(f"candidate hash drift after device QA: {name}")
    if (candidate / GUIDE_NAME).read_bytes() != render_import_guide():
        raise BundleError("candidate guide drift after device QA")
    if evidence["apk"]["output_sha256"] != identity.apk_sha256:
        raise BundleError("candidate APK report binding mismatch")
    if evidence["data"]["archive_sha256"] != identity.data_zip_sha256:
        raise BundleError("candidate ZIP report binding mismatch")
    return identity, evidence


def verify_candidate(candidate_dir: Path) -> tuple[CandidateIdentity, dict[str, Any]]:
    """Rehash one frozen four-file candidate and return detached public evidence.

    Release orchestration commands run in separate processes.  This public
    boundary deliberately reuses the same strict, handle-aware candidate
    verification as finalization instead of teaching callers to trust or
    partially parse ``.candidate-evidence.json`` themselves.
    """

    return _rehash_frozen_candidate(Path(candidate_dir))


def _default_receipt_validator(path: Path, identity: CandidateIdentity) -> Mapping[str, Any]:
    return _read_canonical_file(Path(path), label="device acceptance receipt")


def _validated_receipt(value: Any, identity: CandidateIdentity) -> dict[str, Any]:
    receipt = _normalise_json(value)
    if not isinstance(receipt, dict):
        raise BundleError("device acceptance receipt must be an object")
    if receipt.get("schema_version") != 1:
        raise BundleError("device acceptance receipt schema mismatch")
    expected_receipt_fields = {
        "schema_version",
        "build_id",
        "apk_sha256",
        "data_zip_sha256",
        "evidence_sha256",
        "serial_digest",
        "probe",
        "checks",
        "accepted_at_utc",
    }
    if set(receipt) != expected_receipt_fields:
        raise BundleError("device acceptance receipt schema has unknown or missing fields")
    bindings = {
        "build_id": identity.build_id,
        "apk_sha256": identity.apk_sha256,
        "data_zip_sha256": identity.data_zip_sha256,
        "evidence_sha256": identity.evidence_sha256,
    }
    for key, expected in bindings.items():
        actual = receipt.get(key)
        matches = (
            hmac.compare_digest(actual, expected)
            if key.endswith("_sha256") and isinstance(actual, str)
            else actual == expected
        )
        if not matches:
            raise BundleError(f"device receipt {key} mismatch")
    _require_hash(receipt.get("serial_digest"), "device receipt serial_digest")
    probe = _require_mapping(receipt.get("probe"), "device receipt probe")
    expected_probe_fields = {
        "serial_digest",
        "package_name",
        "airplane_mode",
        "wifi_disabled",
        "mobile_disabled",
        "no_default_route",
        "no_active_network",
        "companion_ports_unused",
        "save_haxe_present_before",
        "dummy_data_present_before",
        "fatal_log_lines",
    }
    if set(probe) != expected_probe_fields:
        raise BundleError("device receipt probe schema has unknown or missing fields")
    if probe.get("serial_digest") != receipt.get("serial_digest"):
        raise BundleError("device receipt serial digest mismatch")
    if probe.get("package_name") != "com.leiting.wf":
        raise BundleError("device receipt package mismatch")
    for gate in REQUIRED_OFFLINE_PROBE_GATES:
        _require_true(probe.get(gate), f"device receipt probe.{gate}")
    if probe.get("save_haxe_present_before") is not False or probe.get("dummy_data_present_before") is not False:
        raise BundleError("device receipt does not prove a clean device before QA")
    if probe.get("fatal_log_lines") not in ([], ()):
        raise BundleError("device receipt contains fatal or crash log lines")
    checks = _require_mapping(receipt.get("checks"), "device receipt checks")
    if set(checks) != set(REQUIRED_MANUAL_CHECKS) or any(
        checks.get(name) is not True for name in REQUIRED_MANUAL_CHECKS
    ):
        raise BundleError("device receipt must contain every manual check exactly once and true")
    accepted = receipt.get("accepted_at_utc")
    if not isinstance(accepted, str) or not (
        accepted.endswith("Z") or accepted.endswith("+00:00")
    ):
        raise BundleError("device receipt accepted_at_utc must be UTC")
    try:
        parsed_accepted = datetime.fromisoformat(
            accepted[:-1] + "+00:00" if accepted.endswith("Z") else accepted
        )
    except ValueError as exc:
        raise BundleError("device receipt accepted_at_utc must be an ISO-8601 UTC time") from exc
    if parsed_accepted.utcoffset() != timedelta(0):
        raise BundleError("device receipt accepted_at_utc must be UTC")
    return receipt


def _manifest_document(identity: CandidateIdentity, evidence: Mapping[str, Any], receipt: Mapping[str, Any], candidate: Path) -> dict[str, Any]:
    payload = dict(_normalise_json(evidence))
    payload.update(
        {
            "schema_version": 1,
            "build_id": identity.build_id,
            "evidence_sha256": identity.evidence_sha256,
            "artifacts": {
                "apk": {
                    "name": APK_NAME,
                    "size": (candidate / APK_NAME).stat().st_size,
                    "sha256": identity.apk_sha256,
                },
                "data_zip": {
                    "name": DATA_ZIP_NAME,
                    "size": (candidate / DATA_ZIP_NAME).stat().st_size,
                    "sha256": identity.data_zip_sha256,
                },
                "guide": {
                    "name": GUIDE_NAME,
                    "size": (candidate / GUIDE_NAME).stat().st_size,
                    "sha256": identity.guide_sha256,
                },
            },
            "device_acceptance": {
                "accepted": True,
                "evidence_sha256": receipt["evidence_sha256"],
                "accepted_at_utc": receipt["accepted_at_utc"],
                "serial_digest": receipt["serial_digest"],
                "probe": receipt["probe"],
                "checks": receipt["checks"],
            },
        }
    )
    if _contains_forbidden_self_hash(payload):
        raise BundleError("build manifest must not contain a self hash")
    return payload


def build_sha256sums(root: Path) -> bytes:
    directory = Path(root)
    lines: list[str] = []
    for name in HASHED_FINAL_FILES:
        _, digest = _hash_regular(directory / name, label="checksum input")
        lines.append(f"{digest} *{name}\n")
    return "".join(lines).encode("utf-8")


def _write_five_files(temp: Path, candidate: Path, receipt: Mapping[str, Any], identity: CandidateIdentity, evidence: Mapping[str, Any]) -> None:
    _copy_exclusive(candidate / APK_NAME, temp / APK_NAME, expected_hash=identity.apk_sha256)
    _copy_exclusive(candidate / DATA_ZIP_NAME, temp / DATA_ZIP_NAME, expected_hash=identity.data_zip_sha256)
    _copy_exclusive(candidate / GUIDE_NAME, temp / GUIDE_NAME, expected_hash=identity.guide_sha256)
    manifest = _manifest_document(identity, evidence, receipt, candidate)
    _write_exclusive(temp / MANIFEST_NAME, canonical_json_bytes(manifest))
    _write_exclusive(temp / SHA256SUMS_NAME, build_sha256sums(temp))


def validate_release_layout(final_dir: Path) -> Path:
    final = Path(final_dir)
    _exact_regular_files(final, FINAL_FILES, label="final release directory")
    return final


def _parse_sha256sums(raw: bytes) -> dict[str, str]:
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise BundleError("SHA256SUMS.txt is not UTF-8") from exc
    if "\r" in text or not text.endswith("\n"):
        raise BundleError("SHA256SUMS.txt must use LF with a final newline")
    lines = text.splitlines()
    if len(lines) != len(HASHED_FINAL_FILES):
        raise BundleError("SHA256SUMS.txt must contain exactly four lines")
    values: dict[str, str] = {}
    for line in lines:
        if len(line) < 67 or line[64:66] != " *":
            raise BundleError("SHA256SUMS.txt has an invalid line")
        digest = _require_hash(line[:64], "SHA256SUMS digest")
        name = line[66:]
        if name not in HASHED_FINAL_FILES or name in values:
            raise BundleError("SHA256SUMS.txt has an invalid filename")
        values[name] = digest
    if tuple(values) != HASHED_FINAL_FILES:
        raise BundleError("SHA256SUMS.txt order is not canonical")
    return values


def _verify_data_archive(
    archive_path: Path,
    entries: Sequence[Mapping[str, Any]],
    *,
    expected_archive_sha256: str,
    label: str = "final",
) -> tuple[int, str]:
    expected = {str(entry["path"]): entry for entry in entries}
    before = _regular_metadata(archive_path, label=f"{label} data ZIP")
    try:
        with archive_path.open("rb") as source:
            opened = os.fstat(source.fileno())
            if _is_reparse(opened) or not stat.S_ISREG(opened.st_mode):
                raise BundleError(f"{label} data ZIP changed type while opening")
            if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                raise BundleError(f"{label} data ZIP identity drift while opening")
            archive_digest = hashlib.sha256()
            archive_size = 0
            while True:
                chunk = source.read(_CHUNK_SIZE)
                if not chunk:
                    break
                archive_digest.update(chunk)
                archive_size += len(chunk)
            archive_hash = archive_digest.hexdigest()
            if not hmac.compare_digest(archive_hash, expected_archive_sha256):
                raise BundleError(f"{label} data ZIP outer hash mismatch")
            source.seek(0)
            with zipfile.ZipFile(source, "r") as archive:
                infos = archive.infolist()
                if len(infos) != len(expected):
                    raise BundleError(f"{label} data ZIP member count mismatch")
                names = [info.filename for info in infos]
                if len(set(name.casefold() for name in names)) != len(names) or set(names) != set(expected):
                    raise BundleError(f"{label} data ZIP entry set mismatch")
                for info in infos:
                    if info.is_dir() or _zip_member_is_symlink(info):
                        raise BundleError(f"{label} data ZIP contains a directory or symlink")
                    if info.flag_bits & 0x1:
                        raise BundleError(f"{label} data ZIP contains an encrypted member")
                    record = expected[info.filename]
                    digest = hashlib.sha256()
                    size = 0
                    with archive.open(info, "r") as stream:
                        while True:
                            chunk = stream.read(_CHUNK_SIZE)
                            if not chunk:
                                break
                            digest.update(chunk)
                            size += len(chunk)
                    if size != record["size"] or not hmac.compare_digest(
                        digest.hexdigest(), str(record["sha256"])
                    ):
                        raise BundleError(
                            f"{label} data ZIP payload mismatch: {_safe_label(info.filename)}"
                        )
            after_open = os.fstat(source.fileno())
    except BundleError:
        raise
    except (OSError, zipfile.BadZipFile, RuntimeError, EOFError) as exc:
        raise BundleError(f"cannot verify {label} data ZIP") from exc
    after = _regular_metadata(archive_path, label=f"{label} data ZIP")
    if _path_identity(before) != _path_identity(after_open) or _path_identity(before) != _path_identity(after):
        raise BundleError(f"{label} data ZIP drift while verifying members")
    if archive_size != before.st_size:
        raise BundleError(f"{label} data ZIP outer size drift")
    return archive_size, archive_hash


def verify_final_bundle(final_dir: Path) -> CandidateIdentity:
    final = validate_release_layout(final_dir)
    checksums_path = final / SHA256SUMS_NAME
    checksums = _parse_sha256sums(
        _read_regular_snapshot(checksums_path, label="SHA256SUMS.txt")
    )
    for name in HASHED_FINAL_FILES:
        _, actual = _hash_regular(final / name, label="final checksum member")
        if not hmac.compare_digest(actual, checksums[name]):
            raise BundleError(f"final checksum mismatch: {_safe_label(name)}")
    manifest = _read_canonical_file(final / MANIFEST_NAME, label="build manifest")
    if _contains_forbidden_self_hash(manifest):
        raise BundleError("build manifest contains a forbidden self hash")
    evidence_fields = (
        "source_fingerprint",
        "source_apk",
        "patches",
        "signer",
        "versions",
        "data",
        "player",
        "content",
        "apk",
        "gates",
        "git",
    )
    missing_evidence = [key for key in evidence_fields if key not in manifest]
    if missing_evidence:
        raise BundleError(
            f"build manifest is missing evidence fields: {', '.join(missing_evidence)}"
        )
    evidence = {key: manifest[key] for key in evidence_fields}
    evidence = validate_release_evidence(evidence)
    build_id = manifest.get("build_id")
    if not isinstance(build_id, str) or _BUILD_ID_RE.fullmatch(build_id) is None:
        raise BundleError("build manifest build_id is invalid")
    artifacts = _require_mapping(manifest.get("artifacts"), "build manifest artifacts")
    apk_record = _require_mapping(artifacts.get("apk"), "build manifest APK artifact")
    data_record = _require_mapping(artifacts.get("data_zip"), "build manifest data artifact")
    guide_record = _require_mapping(artifacts.get("guide"), "build manifest guide artifact")
    identity = CandidateIdentity(
        build_id,
        _require_hash(apk_record.get("sha256"), "build manifest APK hash"),
        _require_hash(data_record.get("sha256"), "build manifest data hash"),
        _require_hash(guide_record.get("sha256"), "build manifest guide hash"),
        _require_hash(manifest.get("evidence_sha256"), "build manifest evidence hash"),
    )
    if not hmac.compare_digest(identity.evidence_sha256, _release_evidence_sha256(evidence)):
        raise BundleError("build manifest release evidence hash mismatch")
    expected_names = {"apk": APK_NAME, "data_zip": DATA_ZIP_NAME, "guide": GUIDE_NAME}
    for key, record, digest in (
        ("apk", apk_record, identity.apk_sha256),
        ("data_zip", data_record, identity.data_zip_sha256),
        ("guide", guide_record, identity.guide_sha256),
    ):
        name = expected_names[key]
        size, actual = _hash_regular(final / name, label="final artifact")
        if record.get("name") != name or record.get("size") != size or not hmac.compare_digest(actual, digest):
            raise BundleError(f"build manifest artifact binding mismatch: {key}")
    if evidence["apk"]["output_sha256"] != identity.apk_sha256 or evidence["data"]["archive_sha256"] != identity.data_zip_sha256:
        raise BundleError("build manifest report/artifact binding mismatch")
    if (final / GUIDE_NAME).read_bytes() != render_import_guide():
        raise BundleError("final import guide does not match the tracked template")
    device = _require_mapping(manifest.get("device_acceptance"), "device_acceptance")
    _require_true(device.get("accepted"), "device_acceptance.accepted")
    receipt_shape = {
        "schema_version": 1,
        "build_id": identity.build_id,
        "apk_sha256": identity.apk_sha256,
        "data_zip_sha256": identity.data_zip_sha256,
        "evidence_sha256": device.get("evidence_sha256"),
        "serial_digest": device.get("serial_digest"),
        "probe": device.get("probe"),
        "checks": device.get("checks"),
        "accepted_at_utc": device.get("accepted_at_utc"),
    }
    _validated_receipt(receipt_shape, identity)
    _verify_data_archive(
        final / DATA_ZIP_NAME,
        evidence["data"]["entries"],
        expected_archive_sha256=identity.data_zip_sha256,
        label="final",
    )
    validate_release_secret_findings(
        scan_release_for_secrets(final, secret_values=_configured_secret_values())
    )
    return identity


def finalize_candidate(
    candidate_dir: Path,
    receipt_path: Path,
    final_dir: Path,
    *,
    receipt_validator: ReceiptValidator | None = None,
) -> Path:
    candidate = Path(candidate_dir)
    receipt = Path(receipt_path)
    final = Path(final_dir)
    if _lexists(final):
        raise BundleError(f"final already exists: {_safe_label(final.name)}")
    if _paths_overlap(candidate, final):
        raise BundleError("candidate and final paths must not overlap")
    parent = final.parent
    _directory_metadata(parent, label="final parent")
    _require_same_volume(candidate, parent)
    identity, evidence = _rehash_frozen_candidate(candidate)
    validator = receipt_validator or _default_receipt_validator
    try:
        receipt_value = validator(receipt, identity)
    except BundleError:
        raise
    except BaseException as exc:
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        raise BundleError("device receipt validation failed") from exc
    validated_receipt = _validated_receipt(receipt_value, identity)
    temp = parent / f".{final.name}.finalizing-{uuid.uuid4().hex}"
    parent_owned = _open_destination_directory(
        parent,
        deny_delete=True,
        request_delete=False,
    )
    owned: _OwnedDirectory | None = None
    try:
        owned = _create_owned_directory(temp)
        _write_five_files(temp, candidate, validated_receipt, identity, evidence)
        validate_release_secret_findings(
            scan_release_for_secrets(temp, secret_values=_configured_secret_values())
        )
        if verify_final_bundle(temp) != identity:
            raise BundleError("verified final identity changed before publication")
        _publish_owned_directory_no_replace(owned, parent_owned, final)
        _exact_regular_files(final, FINAL_FILES, label="published final release directory")
        if verify_final_bundle(final) != identity:
            raise BundleError("published final identity changed")
    except BaseException as original_error:
        if owned is not None:
            try:
                _remove_owned_temp_tree(owned)
            except BaseException as cleanup_error:
                original_error.add_note(
                    "handle-bound final rollback failed: "
                    f"{type(cleanup_error).__name__}"
                )
        raise
    else:
        if owned is not None:
            _close_owned_directory(owned)
    finally:
        _close_owned_directory(parent_owned)
    return final


__all__ = [
    "APK_NAME",
    "DATA_ZIP_NAME",
    "GUIDE_NAME",
    "MANIFEST_NAME",
    "SHA256SUMS_NAME",
    "CANDIDATE_EVIDENCE_NAME",
    "FINAL_FILES",
    "PRODUCTION_ENTRY_COUNT",
    "PRODUCTION_ROOT_COUNTS",
    "ROOT_PREFIXES",
    "BundleError",
    "CandidateIdentity",
    "SecretFinding",
    "canonical_json_bytes",
    "render_import_guide",
    "validate_release_evidence",
    "freeze_candidate",
    "build_sha256sums",
    "scan_release_for_secrets",
    "validate_release_secret_findings",
    "validate_release_layout",
    "verify_candidate",
    "finalize_candidate",
    "verify_final_bundle",
]
