"""Inspect real profile-bound SWFs and compare registered kind table surfaces."""
from __future__ import annotations

import copy
import hashlib
import io
from pathlib import Path
import struct
import zipfile
import zlib

from wf.paths import REPOSITORY, root_path
from .kind_branches import inspect_abc, registry_mismatches
from .swfabc import SwfAbc

# Cache only parsed reports keyed by the complete SWF bytes' digest. Every call
# still reads/hashes its selected artifact; mutations cannot reuse stale proof.
_TABLE_CACHE = {}


class SwfHashMismatch(ValueError):
    """A readable candidate belongs to another SWF; alternatives may match."""


def _path(value) -> Path:
    value = str(value)
    prefix = "${WF_ROOT}/"
    if value.startswith(prefix):
        return root_path(value[len(prefix):])
    path = Path(value)
    return path if path.is_absolute() else REPOSITORY / path


def _snapshot(path: Path) -> tuple[bytes, dict]:
    data = path.read_bytes()
    source = {"path": str(path), "sha256": hashlib.sha256(data).hexdigest(),
              "kind": path.suffix.lower().lstrip(".")}
    if source["kind"] == "apk":
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                raise ValueError("APK contains duplicate ZIP member names")
            preferred = "assets/worldflipper_android_release.swf"
            matches = [preferred] if preferred in names else [n for n in names if n.endswith(".swf")]
            if len(matches) != 1:
                raise ValueError("APK must identify exactly one main SWF")
            source["member"] = matches[0]
            data = archive.read(matches[0])
    elif source["kind"] != "swf":
        raise ValueError("real kind inspection requires a .swf or .apk artifact")
    source["swf_sha256"] = hashlib.sha256(data).hexdigest()
    return data, source


def inspect_swf(path, *, expected_sha256=None) -> dict:
    """Inspect a SWF or APK; optional expected hash always binds the inner SWF."""
    try:
        raw, source = _snapshot(_path(path))
    except zipfile.BadZipFile as error:
        raise ValueError(f"实际 APK ZIP 无法解析：{error}") from error
    digest = source["swf_sha256"]
    if expected_sha256 is not None and digest != expected_sha256:
        raise SwfHashMismatch("客户端档案 SWF 哈希与实际文件不符")
    if digest not in _TABLE_CACHE:
        try:
            swf = SwfAbc.from_bytes(raw, source=source["path"])
            _TABLE_CACHE[digest] = inspect_abc(swf.abc)
        except (IndexError, UnicodeError, struct.error, zlib.error, AssertionError) as error:
            raise ValueError(f"实际 SWF/ABC 无法解析：{error}") from error
    return {"schema": "wf-apk-kinds/1", "source": source,
            "tables": copy.deepcopy(_TABLE_CACHE[digest]), "mismatches": [],
            "basis": "实际 SWF 方法 code 字节中的可达 pushstring/相等比较分支；静态解析证据"}


def kind_supported(report, table, block, kind) -> bool:
    return str(kind) in report["tables"].get(table, {}).get(block, {}).get("kinds", [])


def _compare(report, provides, registry):
    if registry is None:
        from wf.caps.registry import load_registry
        registry = load_registry()
    available = {entry["id"] for entry in provides["provides"]}
    report["mismatches"] = registry_mismatches(report["tables"], registry, available)
    return report


def inspect_profile(profile, *, swf=None, registry=None) -> dict:
    from wf.caps.profiles import load_profiles, read_client, resolve_client

    _, profiles = load_profiles()
    if profile not in profiles:
        raise ValueError(f"未知客户端档案：{profile}")
    record = profiles[profile]
    provides_path, _ = resolve_client(client_profile=profile)
    provides = read_client(provides_path)
    evidence = record.get("evidence", {})
    filename = swf or evidence.get("swf_path") or evidence.get("swf")
    if filename is None:
        report = inspect_provides(provides, registry=registry)
    else:
        expected = evidence.get("swf_sha256")
        if not expected:
            raise ValueError(f"客户端档案 {profile} 缺少 SWF 哈希")
        report = _compare(inspect_swf(filename, expected_sha256=expected), provides, registry)
    report["profile"] = profile
    return report


def inspect_provides(provides, *, registry=None) -> dict:
    """Bind a real artifact to provides; profile fallback uses an exact SWF SHA."""
    from wf.caps.profiles import load_profiles

    source = provides["source"]
    expected = source.get("swf_sha256")
    if not expected:
        raise ValueError("provides 缺少可绑定实际 SWF 的 SHA-256")
    filename = source.get("path")
    if filename and Path(str(filename)).suffix.lower() in {".swf", ".apk"}:
        path = _path(filename)
        if path.is_file():
            return _compare(inspect_swf(path, expected_sha256=expected), provides, registry)
    _, profiles = load_profiles()
    mismatched = False
    for profile_id, record in profiles.items():
        evidence = record.get("evidence", {})
        if evidence.get("swf_sha256") == expected:
            from wf.studio.delivery_safety import resolve_apks
            for candidate in resolve_apks(profile_id):
                if candidate.is_file():
                    try:
                        return _compare(inspect_swf(candidate, expected_sha256=expected), provides, registry)
                    except SwfHashMismatch:
                        mismatched = True
        filename = evidence.get("swf_path") or evidence.get("swf")
        if evidence.get("swf_sha256") == expected and filename and _path(filename).is_file():
            try:
                return _compare(inspect_swf(filename, expected_sha256=expected), provides, registry)
            except SwfHashMismatch:
                mismatched = True
    if mismatched:
        raise SwfHashMismatch("所有可读候选 SWF/APK 均与 provides SHA-256 不符")
    raise FileNotFoundError("没有可读取且与 provides SHA-256 绑定的实际 SWF/APK；不能用反编译快照代替")
