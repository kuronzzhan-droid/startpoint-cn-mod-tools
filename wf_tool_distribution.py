"""Build a deterministic, self-describing standalone WF mod-tools archive."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import fnmatch
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import tempfile
from typing import Any, NoReturn
import zipfile


class DistributionError(RuntimeError):
    """A stable, user-actionable distribution boundary failure."""


@dataclass(frozen=True)
class DistributionReceipt:
    sha256: str
    size: int
    file_count: int
    source_commit: str
    tool_version: str


@dataclass(frozen=True)
class _Config:
    tool_version: str
    archive_root: str
    files: tuple[str, ...]
    trees: tuple[str, ...]
    excluded_tracked: tuple[str, ...]


_CONFIG_KEYS = {
    "schemaVersion",
    "toolVersion",
    "archiveRoot",
    "files",
    "trees",
    "excludedTracked",
}
_SENSITIVE_BASENAMES = {
    ".env",
    "active.json",
    "profiles.json",
    "receipt.json",
    "target.json",
}
_SENSITIVE_PARTS = {".git", ".superpowers", "__pycache__", "tests", "work"}
_WINDOWS_DEVICES = {
    "aux",
    "clock$",
    "com1",
    "com2",
    "com3",
    "com4",
    "com5",
    "com6",
    "com7",
    "com8",
    "com9",
    "con",
    "lpt1",
    "lpt2",
    "lpt3",
    "lpt4",
    "lpt5",
    "lpt6",
    "lpt7",
    "lpt8",
    "lpt9",
    "nul",
    "prn",
}
_LOCAL_PATH = re.compile(
    rb"(?:[A-Za-z]:[\\/](?:Users|WF)[\\/]|"
    rb"(?<![A-Za-z0-9_.-])/(?:home|Users)/)[^\x00\r\n\t ]+"
)
_PRIVATE_IPV4 = re.compile(
    rb"(?<![0-9])(?:10(?:\.[0-9]{1,3}){3}|192\.168(?:\.[0-9]{1,3}){2}|"
    rb"172\.(?:1[6-9]|2[0-9]|3[01])(?:\.[0-9]{1,3}){2})(?![0-9])"
)


def _fail(message: str) -> NoReturn:
    raise DistributionError(message)


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            _fail(f"duplicate config key: {key}")
        value[key] = item
    return value


def _portable_path(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\0" in value:
        _fail(f"{label} must be a portable relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or value != path.as_posix() or any(part in {"", ".", ".."} for part in path.parts):
        _fail(f"{label} must be a portable relative path")
    for part in path.parts:
        if part.endswith((" ", ".")) or any(ord(character) < 32 for character in part):
            _fail(f"{label} must be a portable relative path")
        stem = part.split(".", 1)[0].casefold()
        if stem in _WINDOWS_DEVICES or ":" in part:
            _fail(f"{label} must be a portable relative path")
    return value


def _string_list(value: object, *, label: str, paths: bool = True) -> tuple[str, ...]:
    if not isinstance(value, list):
        _fail(f"{label} must be an array")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item:
            _fail(f"{label} entries must be non-empty strings")
        result.append(_portable_path(item, label=label) if paths else item)
    if len(result) != len(set(result)):
        _fail(f"{label} contains duplicate entries")
    return tuple(result)


def _load_config(path: Path) -> _Config:
    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_strict_object)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DistributionError("distribution config is not valid UTF-8 JSON") from error
    if not isinstance(value, dict) or set(value) != _CONFIG_KEYS:
        _fail("distribution config has an unsupported shape")
    if value["schemaVersion"] != 1:
        _fail("distribution config schemaVersion must be 1")
    tool_version = value["toolVersion"]
    if not isinstance(tool_version, str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", tool_version):
        _fail("distribution toolVersion must be semantic version text")
    archive_root = _portable_path(value["archiveRoot"], label="archiveRoot")
    if "/" in archive_root:
        _fail("archiveRoot must be one directory name")
    files = _string_list(value["files"], label="files")
    trees = _string_list(value["trees"], label="trees")
    declared = files + trees
    folded: dict[str, str] = {}
    for path in declared:
        key = path.casefold()
        if key in folded:
            _fail(f"case-insensitive path alias: {folded[key]} / {path}")
        folded[key] = path
    return _Config(
        tool_version=tool_version,
        archive_root=archive_root,
        files=files,
        trees=trees,
        excluded_tracked=_string_list(
            value["excludedTracked"], label="excludedTracked", paths=False
        ),
    )


def _git(source: Path, *arguments: str) -> bytes:
    result = subprocess.run(
        ["git", *arguments],
        cwd=source,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        _fail("source is not a readable Git checkout")
    return result.stdout


def _tracked_files(source: Path) -> tuple[str, ...]:
    raw = _git(source, "ls-files", "-z")
    try:
        paths = tuple(item.decode("utf-8") for item in raw.split(b"\0") if item)
    except UnicodeDecodeError as error:
        raise DistributionError("tracked paths are not UTF-8") from error
    for path in paths:
        _portable_path(path, label="tracked path")
    return paths


def _assert_clean(source: Path) -> None:
    status = _git(source, "status", "--porcelain=v1", "--untracked-files=all")
    if status:
        _fail("distribution requires a clean Git checkout")


def _is_excluded(path: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def _select_files(source: Path, config: _Config) -> tuple[str, ...]:
    tracked = _tracked_files(source)
    tracked_set = set(tracked)
    selected: set[str] = set()
    for path in config.files:
        if path not in tracked_set:
            _fail(f"declared distribution file is not tracked: {path}")
        selected.add(path)
    for tree in config.trees:
        prefix = tree.rstrip("/") + "/"
        matches = {path for path in tracked if path.startswith(prefix)}
        if not matches:
            _fail(f"declared distribution tree is empty: {tree}")
        selected.update(matches)
    excluded = {path for path in tracked if _is_excluded(path, config.excluded_tracked)}
    overlap = selected & excluded
    if overlap:
        _fail(f"distribution member is both included and excluded: {min(overlap)}")
    unclassified = tracked_set - selected - excluded
    if unclassified:
        _fail(f"unclassified tracked file: {min(unclassified)}")
    folded: dict[str, str] = {}
    for path in sorted(selected):
        key = path.casefold()
        if key in folded:
            _fail(f"case-insensitive path alias: {folded[key]} / {path}")
        folded[key] = path
    return tuple(sorted(selected))


def _assert_safe_member(path: str, absolute: Path) -> None:
    pure = PurePosixPath(path)
    folded_parts = {part.casefold() for part in pure.parts}
    if pure.name.casefold() in _SENSITIVE_BASENAMES or folded_parts & _SENSITIVE_PARTS:
        _fail(f"sensitive distribution member: {path}")
    if pure.suffix.casefold() in {".bak", ".pyc", ".pyo", ".zip"}:
        _fail(f"sensitive distribution member: {path}")
    try:
        details = absolute.lstat()
    except OSError as error:
        raise DistributionError(f"distribution member is unavailable: {path}") from error
    attributes = getattr(details, "st_file_attributes", 0)
    if stat.S_ISLNK(details.st_mode) or attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
        _fail(f"distribution member cannot be a link or reparse point: {path}")
    if not stat.S_ISREG(details.st_mode):
        _fail(f"distribution member must be a regular file: {path}")


def _read_stable(path: str, absolute: Path) -> bytes:
    before = absolute.stat()
    try:
        data = absolute.read_bytes()
    except OSError as error:
        raise DistributionError(f"distribution member is unreadable: {path}") from error
    after = absolute.stat()
    witness_before = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
    witness_after = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    if witness_before != witness_after or len(data) != after.st_size:
        _fail(f"distribution member changed while reading: {path}")
    if _LOCAL_PATH.search(data):
        _fail(f"distribution member contains a local absolute path: {path}")
    if _PRIVATE_IPV4.search(data):
        _fail(f"distribution member contains a private network address: {path}")
    return data


def _manifest_bytes(
    *, tool_version: str, source_commit: str, files: tuple[tuple[str, bytes], ...]
) -> bytes:
    value = {
        "schemaVersion": 1,
        "toolVersion": tool_version,
        "sourceCommit": source_commit,
        "files": [
            {
                "path": path,
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
            for path, data in files
        ],
    }
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def _write_member(archive: zipfile.ZipFile, name: str, data: bytes) -> None:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def build_tool_distribution(
    source_root: Path | str,
    output: Path | str,
    config_path: Path | str | None = None,
) -> DistributionReceipt:
    source = Path(source_root).resolve(strict=True)
    destination = Path(output).resolve(strict=False)
    config_file = (
        Path(config_path).resolve(strict=True)
        if config_path is not None
        else source / "tool-distribution-v1.json"
    )
    try:
        destination.relative_to(source)
    except ValueError:
        pass
    else:
        _fail("distribution output must be outside the source checkout")
    if destination.exists():
        _fail("distribution output already exists")
    try:
        config_file.relative_to(source)
    except ValueError:
        _fail("distribution config must be inside the source checkout")

    _assert_clean(source)
    config = _load_config(config_file)
    paths = _select_files(source, config)
    members: list[tuple[str, bytes]] = []
    for path in paths:
        absolute = source.joinpath(*PurePosixPath(path).parts)
        _assert_safe_member(path, absolute)
        members.append((path, _read_stable(path, absolute)))
    member_tuple = tuple(members)
    source_commit = _git(source, "rev-parse", "HEAD").decode("ascii").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        _fail("source commit is not a full SHA-1")
    manifest = _manifest_bytes(
        tool_version=config.tool_version,
        source_commit=source_commit,
        files=member_tuple,
    )

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        descriptor, raw_path = tempfile.mkstemp(
            prefix=destination.name + ".", suffix=".tmp", dir=destination.parent
        )
        os.close(descriptor)
        temporary = Path(raw_path)
        with zipfile.ZipFile(temporary, "w", allowZip64=True) as archive:
            root = config.archive_root
            _write_member(archive, f"{root}/MANIFEST.json", manifest)
            for path, data in member_tuple:
                _write_member(archive, f"{root}/{path}", data)
        os.replace(temporary, destination)
        temporary = None
    except OSError as error:
        raise DistributionError("distribution archive could not be written") from error
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)

    archive_bytes = destination.read_bytes()
    return DistributionReceipt(
        sha256=hashlib.sha256(archive_bytes).hexdigest(),
        size=len(archive_bytes),
        file_count=len(member_tuple),
        source_commit=source_commit,
        tool_version=config.tool_version,
    )


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    options = parser.parse_args(arguments)
    try:
        receipt = build_tool_distribution(options.source_root, options.output, options.config)
    except DistributionError as error:
        parser.error(str(error))
    print(json.dumps(receipt.__dict__, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
