#!/usr/bin/env python3
"""Discover the offline Android build toolchain and manage its stable signer.

Discovery and the ``discover`` CLI are read-only.  A private key can only be
created by an explicit call to :func:`init_signer_interactive` with the exact
confirmation token.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import ntpath
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any


SIGNER_ALIAS = "wf-offline-release"
PASSWORD_ENV = "WF_OFFLINE_KEYSTORE_PASSWORD"
SIGNER_CONFIRMATION = "CREATE_WF_OFFLINE_RELEASE_SIGNER"
REQUIRED_FFDEC_VERSION = "26.2.1"
VERSION_PROBE_TIMEOUT_SECONDS = 15
NONINTERACTIVE_TIMEOUT_SECONDS = 120
SIGNER_LOCK_NAME = ".wf-offline-signer-init.lock"
KEYTOOL_ARGS = (
    "-genkeypair",
    "-alias",
    SIGNER_ALIAS,
    "-keyalg",
    "RSA",
    "-sigalg",
    "SHA256withRSA",
    "-keysize",
    "4096",
    "-validity",
    "9125",
    "-storetype",
    "JKS",
    "-dname",
    "CN=WF Offline Release, OU=Offline Build, O=Local, C=CN",
)

_REQUIRED_TOOLS = ("java", "ffdec", "aapt", "zipalign", "apksigner")
_OPTIONAL_TOOLS = ("adb", "mumu_manager")
_ANDROID_BUILD_TOOLS = ("aapt", "zipalign", "apksigner")
_ENV_NAMES = {
    "java": "WF_OFFLINE_JAVA",
    "ffdec": "WF_OFFLINE_FFDEC",
    "aapt": "WF_OFFLINE_AAPT",
    "zipalign": "WF_OFFLINE_ZIPALIGN",
    "apksigner": "WF_OFFLINE_APKSIGNER",
    "adb": "WF_OFFLINE_ADB",
    "mumu_manager": "WF_OFFLINE_MUMU_MANAGER",
}
_PATH_NAMES = {
    "java": ("java.exe", "java"),
    "ffdec": ("ffdec", "ffdec.jar"),
    "aapt": ("aapt.exe", "aapt"),
    "zipalign": ("zipalign.exe", "zipalign"),
    "apksigner": ("apksigner.bat", "apksigner"),
    "adb": ("adb.exe", "adb"),
    "mumu_manager": ("MuMuManager.exe", "MuMuManager"),
}
_FINGERPRINT_RE = re.compile(r"[0-9a-f]{64}")
_VERSION_RE = re.compile(r"(?<!\d)(\d+(?:\.\d+)+)(?!\d)")
_SCHEME_RE = re.compile(
    r"^Verified using v([123]) scheme\b.*?:\s*(true|false)\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_CERTIFICATE_RE = re.compile(
    r"^Signer\s+#(\d+)\s+certificate\s+SHA-256\s+digest:\s*(.+?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


class ToolchainError(RuntimeError):
    """A required tool or signing invariant could not be proven."""


@dataclass(frozen=True, slots=True)
class Toolchain:
    java: Path
    ffdec: Path
    aapt: Path
    zipalign: Path
    apksigner: Path
    adb: Path | None
    mumu_manager: Path | None
    versions: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class SigningConfig:
    keystore: Path
    expected_certificate_sha256: str
    alias: str = field(default=SIGNER_ALIAS, init=False)
    password_env: str = field(default=PASSWORD_ENV, init=False)


def _path_if_file(value: str | os.PathLike[str] | None) -> Path | None:
    if value is None or not str(value).strip():
        return None
    candidate = Path(value).expanduser()
    if not candidate.is_file():
        return None
    return candidate.resolve()


def _first_existing(paths: Iterable[Path]) -> Path | None:
    for path in paths:
        found = _path_if_file(path)
        if found is not None:
            return found
    return None


def _version_key(path: Path) -> tuple[tuple[int, Any], ...]:
    parts = re.split(r"([0-9]+)", path.name)
    return tuple((0, int(part)) if part.isdigit() else (1, part.lower()) for part in parts)


def _android_sdk_root(env: Mapping[str, str]) -> Path | None:
    configured: dict[str, Path] = {}
    for name in ("ANDROID_SDK_ROOT", "ANDROID_HOME"):
        value = env.get(name, "").strip()
        if not value:
            continue
        path = Path(value).expanduser().resolve()
        if not path.is_dir():
            raise ToolchainError(f"{name} does not name an Android SDK directory")
        configured[name] = path
    if len(configured) == 2:
        first = os.path.normcase(str(configured["ANDROID_SDK_ROOT"]))
        second = os.path.normcase(str(configured["ANDROID_HOME"]))
        if first != second:
            raise ToolchainError("ANDROID_SDK_ROOT and ANDROID_HOME conflict")
    return next(iter(configured.values()), None)


def _sdk_build_tools(root: Path) -> dict[str, Path]:
    build_root = root / "build-tools"
    if not build_root.is_dir():
        raise ToolchainError("Android SDK has no complete Android build-tools directory")
    versions = sorted(
        (child for child in build_root.iterdir() if child.is_dir()),
        key=_version_key,
        reverse=True,
    )
    for version in versions:
        selected: dict[str, Path] = {}
        for tool in _ANDROID_BUILD_TOOLS:
            found = _first_existing(version / name for name in _PATH_NAMES[tool])
            if found is None:
                break
            selected[tool] = found
        if len(selected) == len(_ANDROID_BUILD_TOOLS):
            return selected
    raise ToolchainError("Android SDK has no complete Android build-tools directory")


def _env_fallback(tool: str, env: Mapping[str, str]) -> Path | None:
    variable = _ENV_NAMES[tool]
    configured = env.get(variable, "")
    if configured.strip():
        direct = _path_if_file(configured)
        if direct is None:
            raise ToolchainError(f"{variable} does not name a file")
        return direct
    if tool == "java":
        java_home = env.get("JAVA_HOME", "").strip()
        if java_home:
            home = Path(java_home).expanduser().resolve()
            if not home.is_dir():
                raise ToolchainError("JAVA_HOME does not name a Java directory")
            found = _first_existing(home / "bin" / name for name in _PATH_NAMES[tool])
            if found is None:
                raise ToolchainError("JAVA_HOME has no Java executable")
            return found
    return None


def _path_fallback(
    tool: str, which: Callable[[str], str | None]
) -> Path | None:
    candidates: dict[tuple[Any, ...], Path] = {}
    for name in _PATH_NAMES[tool]:
        value = which(name)
        found = _path_if_file(value)
        if found is not None:
            try:
                stat = found.stat()
            except OSError:
                identity: tuple[Any, ...] = (
                    "path",
                    os.path.normcase(str(found)),
                )
            else:
                identity = (
                    ("file", stat.st_dev, stat.st_ino)
                    if stat.st_ino
                    else ("path", os.path.normcase(str(found)))
                )
            candidates.setdefault(identity, found)
    if len(candidates) > 1:
        raise ToolchainError(f"ambiguous {tool} PATH candidates")
    return next(iter(candidates.values()), None)


def _validated_android_group(paths: Mapping[str, Path]) -> dict[str, Path]:
    directories = {
        os.path.normcase(str(paths[name].parent.resolve()))
        for name in _ANDROID_BUILD_TOOLS
    }
    if len(directories) != 1:
        raise ToolchainError(
            "aapt, zipalign and apksigner must share the same build-tools directory"
        )
    identities: set[tuple[Any, ...]] = set()
    for name in _ANDROID_BUILD_TOOLS:
        path = paths[name]
        allowed_basenames = {
            basename.casefold() for basename in _PATH_NAMES[name]
        }
        if path.name.casefold() not in allowed_basenames:
            raise ToolchainError(
                f"Android build-tools {name} basename is invalid"
            )
        try:
            stat = path.stat()
        except OSError as exc:
            raise ToolchainError(
                f"could not identify Android build-tools {name}"
            ) from exc
        identity = (
            ("file", stat.st_dev, stat.st_ino)
            if stat.st_ino
            else ("path", os.path.normcase(str(path.resolve())))
        )
        if identity in identities:
            raise ToolchainError(
                "Android build-tools files must have distinct file identity"
            )
        identities.add(identity)
    return {name: paths[name] for name in _ANDROID_BUILD_TOOLS}


def _resolve_android_build_tools(
    overrides: Mapping[str, Path | str | None],
    env: Mapping[str, str],
    which: Callable[[str], str | None],
) -> tuple[dict[str, Path], Path | None]:
    explicit_names = {name for name in _ANDROID_BUILD_TOOLS if name in overrides}
    if explicit_names:
        if explicit_names != set(_ANDROID_BUILD_TOOLS):
            missing = ", ".join(
                name for name in _ANDROID_BUILD_TOOLS if name not in explicit_names
            )
            raise ToolchainError(
                f"missing required tool: {missing}; explicit Android build-tools "
                "must provide all three: aapt, zipalign, apksigner"
            )
        selected: dict[str, Path] = {}
        for name in _ANDROID_BUILD_TOOLS:
            found = _path_if_file(overrides[name])
            if found is None:
                raise ToolchainError(f"explicit {name} is not a file")
            selected[name] = found
        return _validated_android_group(selected), None

    env_names = {
        name for name in _ANDROID_BUILD_TOOLS if env.get(_ENV_NAMES[name], "").strip()
    }
    if env_names:
        if env_names != set(_ANDROID_BUILD_TOOLS):
            raise ToolchainError(
                "WF_OFFLINE Android build-tools overrides must set all three: "
                "WF_OFFLINE_AAPT, WF_OFFLINE_ZIPALIGN, WF_OFFLINE_APKSIGNER"
            )
        selected = {}
        for name in _ANDROID_BUILD_TOOLS:
            variable = _ENV_NAMES[name]
            found = _path_if_file(env[variable])
            if found is None:
                raise ToolchainError(f"{variable} does not name a file")
            selected[name] = found
        return _validated_android_group(selected), None

    sdk_root = _android_sdk_root(env)
    if sdk_root is not None:
        return _validated_android_group(_sdk_build_tools(sdk_root)), sdk_root

    selected = {}
    missing: list[str] = []
    for name in _ANDROID_BUILD_TOOLS:
        found = _path_fallback(name, which)
        if found is None:
            missing.append(name)
        else:
            selected[name] = found
    if missing:
        raise ToolchainError(f"missing required tool: {', '.join(missing)}")
    return _validated_android_group(selected), None


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _repo_ffdec(repo_root: Path) -> Path | None:
    if not repo_root.is_dir():
        return None
    candidates: set[Path] = set()
    # A FFDec distribution also contains ffdec-cli.jar and ffdec_lib.jar.  Only
    # the canonical launcher filename is eligible, and repo fallback is kept to
    # shallow tool directories so discovery never trawls user WIP/store trees.
    for pattern in ("ffdec.jar", "*/ffdec.jar", "*/*/ffdec.jar"):
        for candidate in repo_root.glob(pattern):
            found = _path_if_file(candidate)
            if found is not None:
                candidates.add(found)
    ordered = sorted(candidates, key=lambda path: os.path.normcase(str(path)))
    if len(ordered) > 1:
        names = ", ".join(path.name for path in ordered)
        raise ToolchainError(f"ambiguous ffdec repo fallback: {names}")
    return ordered[0] if ordered else None


def _decode_output(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        if value.startswith((b"\xff\xfe", b"\xfe\xff")):
            try:
                return value.decode("utf-16")
            except UnicodeError:
                pass
        if value and value.count(b"\x00") >= max(1, len(value) // 4):
            for encoding in ("utf-16-le", "utf-16-be"):
                try:
                    return value.decode(encoding)
                except UnicodeError:
                    continue
        return value.decode("utf-8", errors="replace")
    return str(value)


def _completed_text(completed: Any) -> str:
    return "\n".join(
        part for part in (_decode_output(getattr(completed, "stdout", "")), _decode_output(getattr(completed, "stderr", ""))) if part
    ).strip()


def _version_command(tool: str, paths: Mapping[str, Path]) -> list[str]:
    executable = paths[tool]
    if tool == "java":
        return [str(executable), "-version"]
    if tool == "ffdec":
        if executable.suffix.lower() == ".jar":
            return [str(paths["java"]), "-jar", str(executable), "-version"]
        return [str(executable), "-version"]
    if tool == "aapt":
        return [str(executable), "version"]
    if tool == "zipalign":
        return [str(executable), "-h"]
    if tool in {"apksigner", "adb"}:
        return [str(executable), "version"]
    return [str(executable), "--version"]


def _parse_version(tool: str, text: str) -> str:
    if tool == "java":
        match = re.search(r'(?:java|openjdk)\s+version\s+"([^"]+)"', text, re.IGNORECASE)
        if match:
            return match.group(1)
    matches = _VERSION_RE.findall(text)
    if not matches:
        raise ToolchainError(f"could not capture {tool} version")
    if tool in {"aapt", "zipalign"}:
        return matches[-1]
    return matches[0]


def _capture_version(
    tool: str,
    paths: Mapping[str, Path],
    runner: Callable[..., Any],
) -> str:
    if tool == "mumu_manager":
        # MuMuManager is a GUI program and many releases carry no PE version
        # metadata.  Never launch it merely to populate an optional report.
        return "unavailable"
    if tool in {"aapt", "zipalign", "apksigner"}:
        properties_path = paths[tool].parent / "source.properties"
        try:
            properties = properties_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            properties = ""
        matches = re.findall(
            r"^Pkg\.Revision\s*=\s*([^\r\n#]+)\r?$", properties, re.MULTILINE
        )
        if len(matches) == 1 and _VERSION_RE.fullmatch(matches[0].strip()):
            return matches[0].strip()
    if tool == "ffdec" and paths[tool].suffix.lower() == ".jar":
        try:
            with zipfile.ZipFile(paths[tool], "r") as archive:
                properties = archive.read("project.properties").decode("utf-8")
        except (OSError, KeyError, UnicodeError, zipfile.BadZipFile):
            properties = ""
        matches = re.findall(r"^version=([^\r\n]+)\r?$", properties, re.MULTILINE)
        if len(matches) == 1 and _VERSION_RE.fullmatch(matches[0].strip()):
            return matches[0].strip()
    argv = _version_command(tool, paths)
    try:
        completed = runner(
            argv,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=False,
            check=False,
            timeout=VERSION_PROBE_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ToolchainError(f"could not run {tool} version probe") from exc
    text = _completed_text(completed)
    if getattr(completed, "returncode", 0) != 0 and not text:
        raise ToolchainError(f"{tool} version probe failed")
    return _parse_version(tool, text)


def _java_major(version: str) -> int | None:
    match = re.match(r"^(\d+)(?:\.(\d+))?", version)
    if match is None:
        return None
    first = int(match.group(1))
    if first == 1 and match.group(2) is not None:
        return int(match.group(2))
    return first


def _require_java8(version: str) -> None:
    if _java_major(version) != 8:
        raise ToolchainError(f"offline toolchain requires Java 8, found {version}")


def _probe_java8(java: Path, runner: Callable[..., Any]) -> str:
    version = _capture_version("java", {"java": java}, runner)
    _require_java8(version)
    return version


def discover_toolchain(
    *,
    explicit: Mapping[str, Path | str | None] | None = None,
    env: Mapping[str, str] | None = None,
    which: Callable[[str], str | None] = shutil.which,
    runner: Callable[..., Any] = subprocess.run,
) -> Toolchain:
    """Discover tools in the strict explicit/env/PATH/repo priority order."""
    overrides = explicit or {}
    environment = os.environ if env is None else env
    unknown = sorted(set(overrides) - set(_REQUIRED_TOOLS) - set(_OPTIONAL_TOOLS))
    if unknown:
        raise ToolchainError(f"unknown explicit tool: {unknown[0]}")

    paths, sdk_root = _resolve_android_build_tools(overrides, environment, which)
    missing: list[str] = []
    for tool in ("java", "ffdec", "mumu_manager"):
        candidate: Path | None = None
        if tool in overrides:
            candidate = _path_if_file(overrides[tool])
            if candidate is None:
                raise ToolchainError(f"explicit {tool} is not a file")
        if candidate is None:
            candidate = _env_fallback(tool, environment)
        if candidate is None:
            candidate = _path_fallback(tool, which)
        if candidate is None and tool == "ffdec":
            candidate = _repo_ffdec(_repository_root())
        if candidate is None:
            if tool in _REQUIRED_TOOLS:
                missing.append(tool)
            continue
        paths[tool] = candidate

    adb: Path | None = None
    if "adb" in overrides:
        adb = _path_if_file(overrides["adb"])
        if adb is None:
            raise ToolchainError("explicit adb is not a file")
    if adb is None:
        adb = _env_fallback("adb", environment)
    if adb is None and sdk_root is not None:
        adb = _first_existing(
            sdk_root / "platform-tools" / name for name in _PATH_NAMES["adb"]
        )
    if adb is None:
        adb = _path_fallback("adb", which)
    if adb is not None:
        paths["adb"] = adb

    if missing:
        raise ToolchainError(f"missing required tool: {', '.join(missing)}")

    versions = {
        tool: _capture_version(tool, paths, runner)
        for tool in (*_REQUIRED_TOOLS, *_OPTIONAL_TOOLS)
        if tool in paths
    }
    _require_java8(versions["java"])
    if versions["ffdec"] != REQUIRED_FFDEC_VERSION:
        raise ToolchainError(
            f"offline toolchain requires FFDec {REQUIRED_FFDEC_VERSION}, "
            f"found {versions['ffdec']}"
        )
    return Toolchain(
        java=paths["java"],
        ffdec=paths["ffdec"],
        aapt=paths["aapt"],
        zipalign=paths["zipalign"],
        apksigner=paths["apksigner"],
        adb=paths.get("adb"),
        mumu_manager=paths.get("mumu_manager"),
        versions=MappingProxyType(versions),
    )


def toolchain_report(toolchain: Toolchain) -> dict[str, dict[str, str] | None]:
    """Return a manifest-safe report containing only basenames and versions."""
    report: dict[str, dict[str, str] | None] = {}
    for name in (*_REQUIRED_TOOLS, *_OPTIONAL_TOOLS):
        path = getattr(toolchain, name)
        report[name] = (
            None
            if path is None
            else {"name": path.name, "version": toolchain.versions[name]}
        )
    return report


def _normalize_fingerprint(value: Any) -> str:
    if not isinstance(value, str):
        raise ToolchainError("certificate fingerprint must be a string")
    normalized = re.sub(r"[\s:-]", "", value).lower()
    if _FINGERPRINT_RE.fullmatch(normalized) is None:
        raise ToolchainError("certificate fingerprint must be a SHA-256 digest")
    return normalized


def _strict_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ToolchainError(f"duplicate signer public config field: {key}")
        result[key] = value
    return result


def _load_public_signer(path: Path) -> tuple[str, str]:
    try:
        public = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_strict_json_object,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ToolchainError("invalid signer public config") from exc
    if not isinstance(public, Mapping):
        raise ToolchainError("invalid signer public config schema")
    required_fields = {"schema_version", "alias", "certificate_sha256"}
    unknown = sorted(set(public) - required_fields)
    if unknown:
        raise ToolchainError(f"unknown signer public config field: {unknown[0]}")
    if set(public) != required_fields:
        raise ToolchainError("invalid signer public config schema")
    if type(public["schema_version"]) is not int or public["schema_version"] != 1:
        raise ToolchainError("invalid signer public config schema")
    alias = public.get("alias")
    if alias != SIGNER_ALIAS:
        raise ToolchainError("stable signer alias drift")
    return alias, _normalize_fingerprint(public.get("certificate_sha256"))


def load_signing_config(
    release_home: Path | str, *, env: Mapping[str, str]
) -> SigningConfig:
    """Load the stable public signer identity without retaining its password."""
    home = Path(release_home).expanduser().resolve()
    keystore = home / "wf-offline-release.jks"
    public_path = home / "signer-public.json"
    if not keystore.is_file():
        raise ToolchainError("missing stable keystore")
    if not public_path.is_file():
        raise ToolchainError("missing signer public config")
    alias, fingerprint = _load_public_signer(public_path)
    password = env.get(PASSWORD_ENV, "")
    if not isinstance(password, str) or not password:
        raise ToolchainError(f"{PASSWORD_ENV} is not set")
    return SigningConfig(
        keystore=keystore,
        expected_certificate_sha256=fingerprint,
    )


def signing_report(config: SigningConfig) -> dict[str, str]:
    """Return only the stable public signing identity."""
    return {
        "alias": config.alias,
        "certificate_sha256": config.expected_certificate_sha256,
    }


def parse_apksigner_verify(
    output: str | bytes,
    *,
    expected_certificate_sha256: str | None = None,
) -> dict[str, Any]:
    """Parse and enforce v1/v2/v3 plus the unique signer certificate digest."""
    text = _decode_output(output)
    schemes: dict[str, bool] = {}
    for match in _SCHEME_RE.finditer(text):
        name = f"v{match.group(1)}"
        value = match.group(2).lower() == "true"
        if name in schemes:
            qualifier = "conflicting" if schemes[name] != value else "duplicate"
            raise ToolchainError(f"{qualifier} apksigner {name} verification")
        schemes[name] = value
    for name in ("v1", "v2", "v3"):
        if name not in schemes:
            raise ToolchainError(f"missing apksigner {name} verification")
        if not schemes[name]:
            raise ToolchainError(f"apksigner {name} verification failed")

    certificate_matches = list(_CERTIFICATE_RE.finditer(text))
    if not certificate_matches:
        raise ToolchainError("missing apksigner certificate fingerprint")
    if len(certificate_matches) != 1:
        raise ToolchainError("multiple apksigner signers are not allowed")
    if certificate_matches[0].group(1) != "1":
        raise ToolchainError("apksigner output must contain Signer #1 only")
    fingerprint = _normalize_fingerprint(certificate_matches[0].group(2))
    if expected_certificate_sha256 is not None:
        expected = _normalize_fingerprint(expected_certificate_sha256)
        if not hmac.compare_digest(fingerprint, expected):
            raise ToolchainError("signer certificate fingerprint drift")
    return {
        "verified": True,
        "signature_schemes": {name: schemes[name] for name in ("v1", "v2", "v3")},
        "certificate_sha256": fingerprint,
    }


def _secret_texts(secrets: Iterable[str | bytes]) -> tuple[str, ...]:
    values: set[str] = set()
    for secret in secrets:
        if isinstance(secret, bytes):
            for encoding in ("utf-8-sig", "utf-16", "utf-16-le", "utf-16-be"):
                try:
                    decoded = secret.decode(encoding)
                except UnicodeError:
                    continue
                if decoded:
                    values.add(decoded.lstrip("\ufeff"))
        elif secret:
            values.add(str(secret))
    return tuple(sorted(values, key=len, reverse=True))


def _secret_representations(secrets: Sequence[str]) -> tuple[str, ...]:
    values = set(secrets)
    for secret in secrets:
        values.add(secret.encode("unicode_escape").decode("ascii"))
        values.add(ascii(secret)[1:-1])
        values.add(json.dumps(secret, ensure_ascii=True)[1:-1])
        for encoding in ("utf-8", "utf-16", "utf-16-le", "utf-16-be"):
            encoded = secret.encode(encoding)
            values.add(repr(encoded)[2:-1])
            values.add(encoded.hex())
    return tuple(sorted((value for value in values if value), key=len, reverse=True))


def _case_insensitive_representation(value: str) -> bool:
    is_escaped = re.search(
        r"\\(?:x[0-9a-f]{2}|u[0-9a-f]{4}|U[0-9a-f]{8})",
        value,
        re.IGNORECASE,
    )
    is_hex = re.fullmatch(r"(?:[0-9a-f]{2}){2,}", value, re.IGNORECASE)
    is_artifact = ntpath.splitext(value)[1].lower() in {
        ".apk",
        ".cer",
        ".jar",
        ".jks",
    }
    return bool(is_escaped or is_hex or is_artifact)


def _decode_for_redaction(value: Any, secrets: Sequence[str]) -> str:
    if not isinstance(value, bytes):
        return _decode_output(value)
    candidates: list[str] = []
    for encoding in ("utf-8-sig", "utf-16", "utf-16-le", "utf-16-be"):
        try:
            decoded = value.decode(encoding)
        except UnicodeError:
            continue
        candidates.append(decoded.lstrip("\ufeff"))
    representations = _secret_representations(secrets)

    def contains(candidate: str, representation: str) -> bool:
        if representation in candidate:
            return True
        return (
            _case_insensitive_representation(representation)
            and representation.casefold() in candidate.casefold()
        )

    containing_secret = [
        candidate
        for candidate in candidates
        if any(contains(candidate, representation) for representation in representations)
    ]
    if containing_secret:
        return max(
            containing_secret,
            key=lambda candidate: sum(
                contains(candidate, representation)
                for representation in representations
            ),
        )
    return _decode_output(value)


def _redact_text(value: Any, secrets: Sequence[str]) -> str:
    text = _decode_for_redaction(value, secrets)
    for secret in _secret_representations(secrets):
        if _case_insensitive_representation(secret):
            text = re.sub(
                re.escape(secret),
                "[REDACTED]",
                text,
                flags=re.IGNORECASE,
            )
        else:
            text = text.replace(secret, "[REDACTED]")
    return text


def _safe_program_name(command: Any) -> str:
    if isinstance(command, Sequence) and not isinstance(command, (str, bytes)):
        first = str(command[0]) if command else ""
    elif isinstance(command, str):
        first = command.strip().split(maxsplit=1)[0].strip('"\'')
    else:
        first = ""
    name = ntpath.basename(first)
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", name):
        return name
    return "process"


def _command_sensitive_texts(command: Any) -> tuple[str, ...]:
    if isinstance(command, Sequence) and not isinstance(command, (str, bytes)):
        arguments = [str(value) for value in command]
        joined = " ".join(arguments)
    elif isinstance(command, str):
        arguments = [command]
        joined = command
    else:
        return ()
    sensitive: set[str] = {joined}
    for index, argument in enumerate(arguments):
        if index > 0 and Path(argument).suffix.lower() in {
            ".apk",
            ".cer",
            ".jar",
            ".jks",
        }:
            sensitive.add(argument)
            sensitive.add(ntpath.basename(argument))
        if Path(argument).is_absolute() or ntpath.isabs(argument):
            sensitive.add(argument)
            sensitive.add(argument.replace("\\", "\\\\"))
            sensitive.add(argument.replace("\\", "/"))
    return tuple(sorted((value for value in sensitive if value), key=len, reverse=True))


def _scrub_absolute_paths(text: str) -> str:
    text = re.sub(r"(?i)(?:[A-Z]:[\\/]|\\\\)[^\r\n;]+", "[REDACTED]", text)
    return re.sub(r"(?<![A-Za-z0-9.])/(?:[^\s;]+)", "[REDACTED]", text)


def redact_process_error(
    error: BaseException | str | bytes,
    *,
    secrets: Iterable[str | bytes] = (),
) -> str:
    """Render a process failure while removing secrets from all common fields."""
    secret_texts = _secret_texts(secrets)
    if isinstance(error, subprocess.TimeoutExpired):
        program = _safe_program_name(error.cmd)
        sensitive = (*secret_texts, *_command_sensitive_texts(error.cmd))
        pieces = [f"process {program} timed out"]
        for label, value in (("stdout", error.output), ("stderr", error.stderr)):
            rendered = _scrub_absolute_paths(_redact_text(value, sensitive)).strip()
            if rendered:
                pieces.append(f"{label}: {rendered}")
        return "; ".join(pieces)
    if isinstance(error, subprocess.CalledProcessError):
        program = _safe_program_name(error.cmd)
        sensitive = (*secret_texts, *_command_sensitive_texts(error.cmd))
        pieces = [f"process {program} exited with code {error.returncode}"]
        for label, value in (("stdout", error.output), ("stderr", error.stderr)):
            rendered = _scrub_absolute_paths(_redact_text(value, sensitive)).strip()
            if rendered:
                pieces.append(f"{label}: {rendered}")
        return "; ".join(pieces)
    return _scrub_absolute_paths(_redact_text(error, secret_texts))


def run_apksigner(
    config: SigningConfig,
    *,
    apksigner: Path | str,
    java: Path | str | None = None,
    input_apk: Path | str,
    output_apk: Path | str,
    env: Mapping[str, str] | None = None,
    runner: Callable[..., Any] = subprocess.run,
) -> Any:
    """Sign one APK without placing the password or absolute key path in argv."""
    environment = dict(os.environ)
    if env is not None:
        environment.update(env)
    secret = environment.get(config.password_env, "")
    if not secret:
        raise ToolchainError(f"{config.password_env} is not set")
    keystore = config.keystore.resolve()
    if not keystore.is_file():
        raise ToolchainError("missing stable keystore")
    apksigner_path = Path(apksigner).expanduser().resolve()
    if apksigner_path.suffix.lower() in {".bat", ".cmd"}:
        if java is None:
            raise ToolchainError(
                "batch apksigner requires the selected Java executable"
            )
        java_path = Path(java).expanduser().resolve()
        apksigner_jar = apksigner_path.parent / "lib" / "apksigner.jar"
        if not java_path.is_file():
            raise ToolchainError("selected Java executable is not a file")
        if not apksigner_jar.is_file():
            raise ToolchainError("batch apksigner lib/apksigner.jar is missing")
        command_prefix = [str(java_path), "-jar", str(apksigner_jar)]
    else:
        if not apksigner_path.is_file():
            raise ToolchainError("apksigner executable is not a file")
        command_prefix = [str(apksigner_path)]
    argv = [
        *command_prefix,
        "sign",
        "--ks",
        keystore.name,
        "--ks-key-alias",
        config.alias,
        "--ks-pass",
        f"env:{config.password_env}",
        "--key-pass",
        f"env:{config.password_env}",
        "--v4-signing-enabled",
        "false",
        "--out",
        str(Path(output_apk)),
        str(Path(input_apk)),
    ]
    try:
        completed = runner(
            argv,
            cwd=keystore.parent,
            env=environment,
            capture_output=True,
            text=False,
            check=False,
            timeout=NONINTERACTIVE_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        message = redact_process_error(exc, secrets=(secret,))
        raise ToolchainError(f"apksigner failed: {message}") from None
    if getattr(completed, "returncode", 0) != 0:
        failure = subprocess.CalledProcessError(
            int(completed.returncode),
            argv,
            output=getattr(completed, "stdout", None),
            stderr=getattr(completed, "stderr", None),
        )
        message = redact_process_error(failure, secrets=(secret,))
        raise ToolchainError(f"apksigner failed: {message}")
    return completed


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _keytool_sibling(java: Path) -> Path:
    suffix = java.suffix if java.suffix.lower() in {".exe", ".cmd", ".bat"} else ""
    return java.with_name("keytool" + suffix)


def _resolve_keytool_for_java(
    java: Path, *, runner: Callable[..., Any]
) -> Path:
    sibling = _keytool_sibling(java)
    if sibling.is_file():
        return sibling.resolve()
    argv = [str(java), "-XshowSettings:properties", "-version"]
    try:
        completed = runner(
            argv,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=False,
            check=False,
            timeout=VERSION_PROBE_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ToolchainError("could not resolve keytool from selected Java") from exc
    output = _completed_text(completed)
    if getattr(completed, "returncode", 0) != 0 and not output:
        raise ToolchainError("could not resolve keytool from selected Java")
    matches = re.findall(r"^\s*java\.home\s*=\s*(.+?)\s*$", output, re.MULTILINE)
    if len(matches) != 1:
        raise ToolchainError("selected Java did not report one java.home")
    java_home = Path(matches[0]).expanduser().resolve()
    names = ("keytool.exe", "keytool")
    direct = _first_existing(java_home / "bin" / name for name in names)
    if direct is not None:
        return direct
    # Some Java 8 launchers report a nested jre/ while keytool belongs to that
    # same selected JDK.  Only this parent is eligible; PATH is never consulted.
    if java_home.name.lower() == "jre":
        parent = _first_existing(java_home.parent / "bin" / name for name in names)
        if parent is not None:
            return parent
    raise ToolchainError("selected Java java.home has no keytool executable")


def verify_signing_config(
    config: SigningConfig,
    *,
    java: Path | str,
    env: Mapping[str, str],
    runner: Callable[..., Any] = subprocess.run,
) -> dict[str, Any]:
    """Export the configured certificate and prove its public fingerprint."""
    secret = env.get(config.password_env, "")
    if not isinstance(secret, str) or not secret:
        raise ToolchainError(f"{config.password_env} is not set")
    if "\n" in secret or "\r" in secret:
        raise ToolchainError("keystore password contains a line break")
    keystore = config.keystore.expanduser().resolve()
    if not keystore.is_file():
        raise ToolchainError("missing stable keystore")
    java_path = Path(java).expanduser().resolve()
    if not java_path.is_file():
        raise ToolchainError("selected Java executable is not a file")
    _probe_java8(java_path, runner)
    keytool_path = _resolve_keytool_for_java(java_path, runner=runner)
    if not keytool_path.is_file():
        raise ToolchainError("Java keytool executable is not a file")
    argv = [
        str(keytool_path),
        "-J-Dfile.encoding=UTF-8",
        "-exportcert",
        "-alias",
        config.alias,
        "-keystore",
        keystore.name,
    ]
    process_env = dict(os.environ)
    process_env.update(env)
    try:
        completed = runner(
            argv,
            cwd=keystore.parent,
            env=process_env,
            input=(secret + "\n").encode("utf-8"),
            capture_output=True,
            text=False,
            check=False,
            timeout=NONINTERACTIVE_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        message = redact_process_error(exc, secrets=(secret,))
        raise ToolchainError(f"keytool exportcert failed: {message}") from None
    if getattr(completed, "returncode", 0) != 0:
        failure = subprocess.CalledProcessError(
            int(completed.returncode),
            argv,
            output=getattr(completed, "stdout", None),
            stderr=getattr(completed, "stderr", None),
        )
        message = redact_process_error(failure, secrets=(secret,))
        raise ToolchainError(f"keytool exportcert failed: {message}")
    certificate = getattr(completed, "stdout", b"")
    if isinstance(certificate, str):
        certificate = certificate.encode("utf-8")
    if not isinstance(certificate, bytes) or not certificate:
        raise ToolchainError("keytool exportcert returned no certificate")
    fingerprint = hashlib.sha256(certificate).hexdigest()
    expected = _normalize_fingerprint(config.expected_certificate_sha256)
    if not hmac.compare_digest(fingerprint, expected):
        raise ToolchainError("signer certificate fingerprint drift")

    certreq = [
        str(keytool_path),
        "-J-Dfile.encoding=UTF-8",
        "-certreq",
        "-alias",
        config.alias,
        "-keystore",
        keystore.name,
    ]
    # Supplying the same secret for both possible prompts proves that the
    # private-key password was left equal to the store password at bootstrap.
    repeated_secret = (secret + "\n" + secret + "\n").encode("utf-8")
    try:
        private_key_check = runner(
            certreq,
            cwd=keystore.parent,
            env=process_env,
            input=repeated_secret,
            capture_output=True,
            text=False,
            check=False,
            timeout=NONINTERACTIVE_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        message = redact_process_error(exc, secrets=(secret,))
        raise ToolchainError(f"keytool private key check failed: {message}") from None
    if getattr(private_key_check, "returncode", 0) != 0:
        failure = subprocess.CalledProcessError(
            int(private_key_check.returncode),
            certreq,
            output=getattr(private_key_check, "stdout", None),
            stderr=getattr(private_key_check, "stderr", None),
        )
        message = redact_process_error(failure, secrets=(secret,))
        raise ToolchainError(f"keytool private key check failed: {message}")
    return {
        "alias": config.alias,
        "certificate_sha256": fingerprint,
        "fingerprint_verified": True,
        "signer_ready": True,
    }


def _run_keytool_interactive(
    runner: Callable[..., Any], argv: Sequence[str], *, cwd: Path, operation: str
) -> None:
    try:
        completed = runner(list(argv), cwd=cwd, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ToolchainError(f"keytool {operation} failed") from exc
    returncode = int(getattr(completed, "returncode", 0))
    if returncode != 0:
        raise ToolchainError(f"keytool {operation} failed with exit code {returncode}")


def _atomic_write_public_config(path: Path, payload: Mapping[str, Any]) -> None:
    if path.exists():
        raise ToolchainError("signer public config already exists")
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        _atomic_link_no_overwrite(
            temporary,
            path,
            description="signer public config",
        )
        temporary.unlink()
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _atomic_link_no_overwrite(
    source: Path, target: Path, *, description: str
) -> None:
    if target.exists():
        raise ToolchainError(f"{description} already exists")
    try:
        os.link(source, target)
    except FileExistsError as exc:
        raise ToolchainError(f"{description} already exists") from exc
    except OSError as exc:
        raise ToolchainError(f"could not publish {description}") from exc


def _console_streams_are_tty() -> bool:
    streams = (sys.stdin, sys.stdout, sys.stderr)
    try:
        return all(stream is not None and stream.isatty() for stream in streams)
    except (AttributeError, OSError):
        return False


def init_signer_interactive(
    release_home: Path | str,
    *,
    confirmation: str,
    java: Path | str,
    runner: Callable[..., Any] = subprocess.run,
) -> SigningConfig:
    """Create the dedicated signer only after an exact interactive confirmation.

    Password arguments are intentionally absent.  ``keytool`` inherits the real
    console and prompts for the keystore password itself.  At the second prompt,
    press Enter to reuse the store password for the key; verification proves
    that both passwords remain equal before reporting the signer ready.
    """
    if confirmation != SIGNER_CONFIRMATION:
        raise ToolchainError(f"exact confirmation required: {SIGNER_CONFIRMATION}")
    home = Path(release_home).expanduser().resolve()
    repository = _repository_root()
    if _is_within(home, repository):
        raise ToolchainError("release home must be outside the repository")

    if not _console_streams_are_tty():
        raise ToolchainError("signer bootstrap requires an interactive console")

    keystore = home / "wf-offline-release.jks"
    public_path = home / "signer-public.json"
    if keystore.exists() or public_path.exists():
        raise ToolchainError("stable signer keystore or public config already exists")

    java_path = Path(java).expanduser().resolve()
    if not java_path.is_file():
        raise ToolchainError("Java executable is not a file")
    _probe_java8(java_path, runner)
    keytool_path = _resolve_keytool_for_java(java_path, runner=runner)
    if not keytool_path.is_file():
        raise ToolchainError("Java keytool executable is not a file")

    home.mkdir(parents=True, exist_ok=True)
    lock_path = home / SIGNER_LOCK_NAME
    lock_descriptor: int | None = None
    lock_owned = False
    certificate_path: Path | None = None
    temporary_directory: Path | None = None
    temporary_keystore: Path | None = None
    try:
        try:
            lock_descriptor = os.open(
                lock_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
            lock_owned = True
        except FileExistsError as exc:
            raise ToolchainError("signer bootstrap already in progress") from exc
        os.close(lock_descriptor)
        lock_descriptor = None
        if keystore.exists() or public_path.exists():
            raise ToolchainError("stable signer keystore or public config already exists")

        temporary_directory = Path(
            tempfile.mkdtemp(
                dir=home,
                prefix=".wf-offline-release.",
                suffix=".tmp",
            )
        )
        temporary_keystore = temporary_directory / "wf-offline-release.jks"
        generation = [
            str(keytool_path),
            *KEYTOOL_ARGS,
            "-keystore",
            temporary_keystore.name,
        ]
        _run_keytool_interactive(
            runner, generation, cwd=temporary_directory, operation="genkeypair"
        )
        if not temporary_keystore.is_file():
            raise ToolchainError("keytool did not create the temporary keystore")

        descriptor, certificate_name = tempfile.mkstemp(
            dir=temporary_directory,
            prefix=".wf-offline-release-public-",
            suffix=".cer",
        )
        os.close(descriptor)
        certificate_path = Path(certificate_name)
        certificate_path.unlink()
        export = [
            str(keytool_path),
            "-exportcert",
            "-alias",
            SIGNER_ALIAS,
            "-keystore",
            temporary_keystore.name,
            "-file",
            certificate_path.name,
        ]
        _run_keytool_interactive(
            runner, export, cwd=temporary_directory, operation="exportcert"
        )
        if not certificate_path.is_file():
            raise ToolchainError("keytool did not export the public certificate")
        fingerprint = hashlib.sha256(certificate_path.read_bytes()).hexdigest()
        _atomic_link_no_overwrite(
            temporary_keystore,
            keystore,
            description="stable signer keystore",
        )
        _atomic_write_public_config(
            public_path,
            {
                "alias": SIGNER_ALIAS,
                "certificate_sha256": fingerprint,
                "schema_version": 1,
            },
        )
    finally:
        if lock_descriptor is not None:
            os.close(lock_descriptor)
        if certificate_path is not None:
            certificate_path.unlink(missing_ok=True)
        if temporary_keystore is not None:
            temporary_keystore.unlink(missing_ok=True)
        if temporary_directory is not None:
            temporary_directory.rmdir()
        if lock_owned:
            lock_path.unlink(missing_ok=True)

    return SigningConfig(
        keystore=keystore,
        expected_certificate_sha256=fingerprint,
    )


def _signer_discovery_status(
    release_home: Path,
) -> tuple[bool, bool, str | None]:
    keystore = release_home / "wf-offline-release.jks"
    public_path = release_home / "signer-public.json"
    if not keystore.is_file() or not public_path.is_file():
        return False, False, None
    try:
        _alias, fingerprint = _load_public_signer(public_path)
    except ToolchainError:
        return False, False, None
    # Discovery is read-only configuration inspection.  Only
    # verify_signing_config may claim signer readiness after exporting the
    # actual certificate from the keystore.
    return True, False, fingerprint


def _discover_cli(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    discover = subparsers.add_parser("discover", help="read-only tool discovery")
    discover.add_argument("--json", action="store_true", dest="as_json")
    discover.add_argument(
        "--release-home", type=Path, default=Path.home() / ".wf-offline-release"
    )
    for name in (*_REQUIRED_TOOLS, *_OPTIONAL_TOOLS):
        discover.add_argument("--" + name.replace("_", "-"), type=Path)
    args = parser.parse_args(argv)
    explicit = {
        name: getattr(args, name)
        for name in (*_REQUIRED_TOOLS, *_OPTIONAL_TOOLS)
        if getattr(args, name) is not None
    }
    try:
        toolchain = discover_toolchain(explicit=explicit)
        signer_configured, signer_ready, fingerprint = _signer_discovery_status(
            args.release_home.expanduser().resolve()
        )
        report: dict[str, Any] = {
            "status": "ok",
            "tools": toolchain_report(toolchain),
            "signer_configured": signer_configured,
            "signer_ready": signer_ready,
        }
        if fingerprint is not None:
            report["signer_certificate_sha256"] = fingerprint
        exit_code = 0
    except ToolchainError as exc:
        report = {"status": "error", "error": str(exc)}
        exit_code = 2
    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    else:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return exit_code


def main(argv: Sequence[str] | None = None) -> int:
    return _discover_cli(argv)


if __name__ == "__main__":
    raise SystemExit(main())
