"""Stable JSON command line interface for local wf-release-v1 operations."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import stat
import sys
from typing import Final, Sequence

from .canonical import canonical_json_bytes, load_json_strict_bytes
from .errors import ReleaseError
from .producer import BuildReceipt, BuildRequest, build_character_release
from .schema import ReleaseRequirements, parse_requirements
from .verifier import VerificationReport, verify_release


_REPARSE_POINT: Final = 0x0400
_FORMAT_PREFIXES: Final = (
    "WFREL_ARCHIVE_",
    "WFREL_BUILD_LIMIT",
    "WFREL_BUILD_PATH_",
    "WFREL_BUILD_REQUEST_",
    "WFREL_HASH_",
    "WFREL_JSON_",
    "WFREL_OVERLAY_INVALID",
    "WFREL_OVERLAY_LIMIT",
    "WFREL_PATH_",
    "WFREL_SCHEMA_",
)
_INCOMPATIBLE_PREFIXES: Final = (
    "WFREL_BUILD_SOURCE_",
    "WFREL_CHARACTER_SOURCE_",
    "WFREL_COMPONENT_",
    "WFREL_OVERLAY_GRAPH",
    "WFREL_OWNERSHIP_",
    "WFREL_REQUIRE_",
)
_IO_PREFIXES: Final = (
    "WFREL_BUILD_IO",
    "WFREL_BUILD_OUTPUT_",
    "WFREL_CLI_IO",
)


def _write_json(stream: object, value: dict[str, object]) -> None:
    raw = canonical_json_bytes(value).decode("utf-8")
    stream.write(raw)  # type: ignore[attr-defined]


def _write_error(code: str, message: str) -> None:
    _write_json(sys.stderr, {"code": code, "message": message})


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        del message
        _write_error("WFREL_CLI_ARGUMENTS", "命令参数无效")
        raise SystemExit(2)


def _snapshot(value: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_size,
        value.st_mtime_ns,
        value.st_mode,
    )


def _is_reparse(value: os.stat_result) -> bool:
    return stat.S_ISLNK(value.st_mode) or bool(
        getattr(value, "st_file_attributes", 0) & _REPARSE_POINT
    )


def _read_stable_file(path: Path, *, label: str) -> bytes:
    descriptor = -1
    try:
        before_stat = os.lstat(path)
        if _is_reparse(before_stat) or not stat.S_ISREG(before_stat.st_mode):
            raise OSError("input is not a regular file")
        before = _snapshot(before_stat)
        descriptor = os.open(
            path,
            os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
        opened = os.fstat(descriptor)
        if _is_reparse(opened) or _snapshot(opened) != before:
            raise OSError("input identity changed before open")
        with os.fdopen(descriptor, "rb", closefd=True) as stream:
            descriptor = -1
            raw = stream.read()
            after_open = os.fstat(stream.fileno())
        after_path = os.lstat(path)
        if (
            _snapshot(after_open) != before
            or _snapshot(after_path) != before
            or _is_reparse(after_path)
        ):
            raise OSError("input identity changed while reading")
        return raw
    except OSError as error:
        raise ReleaseError(
            "WFREL_CLI_IO",
            "local input is unavailable or changed while being read",
            {"label": label},
        ) from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _load_requirements(path: Path) -> ReleaseRequirements:
    raw = _read_stable_file(path, label="requirements")
    value = load_json_strict_bytes(raw, label="requirements")
    return parse_requirements(value)


def _build_receipt_wire(receipt: BuildReceipt) -> dict[str, object]:
    return {
        "archiveSha256": receipt.archive_sha256,
        "bytesRead": receipt.bytes_read,
        "fileCount": receipt.file_count,
        "hashCount": receipt.hash_count,
        "releaseId": receipt.release_id,
    }


def _report_wire(report: VerificationReport) -> dict[str, object]:
    return {
        "components": list(report.components),
        "fileCount": report.file_count,
        "payloadBytes": report.payload_bytes,
        "releaseId": report.release_id,
    }


def _run_build(arguments: argparse.Namespace) -> dict[str, object]:
    requirements = _load_requirements(Path(arguments.requirements))
    receipt = build_character_release(
        BuildRequest(
            name=arguments.name,
            version=arguments.version,
            workspace=Path(arguments.workspace),
            overlay_archives=tuple(Path(item) for item in arguments.overlay),
            output=Path(arguments.output),
            requirements=requirements,
        )
    )
    return _build_receipt_wire(receipt)


def _run_verify(arguments: argparse.Namespace) -> dict[str, object]:
    return _report_wire(verify_release(Path(arguments.release)))


def _parser() -> _ArgumentParser:
    parser = _ArgumentParser(prog="wf-release")
    commands = parser.add_subparsers(dest="command", required=True)

    build = commands.add_parser("build", help="构建不可变发行物")
    build.add_argument("--workspace", required=True)
    build.add_argument("--overlay", action="append", required=True)
    build.add_argument("--requirements", required=True)
    build.add_argument("--name", required=True)
    build.add_argument("--version", required=True)
    build.add_argument("--output", required=True)
    build.set_defaults(handler=_run_build)

    for name, help_text in (
        ("verify", "独立校验发行物"),
        ("inspect", "输出已完整校验的发行物摘要"),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--release", required=True)
        command.add_argument("--json", action="store_true", required=True)
        command.set_defaults(handler=_run_verify)
    return parser


def _caused_by_os_error(error: BaseException) -> bool:
    current: BaseException | None = error
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        if isinstance(current, OSError):
            return True
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    return False


def _release_exit(error: ReleaseError) -> tuple[int, str]:
    if _caused_by_os_error(error):
        return 30, "本地文件操作失败"
    if error.code.startswith(_IO_PREFIXES):
        return 30, "本地文件操作失败"
    if error.code.startswith(_INCOMPATIBLE_PREFIXES):
        return 20, "发布源或依赖要求不兼容"
    if error.code.startswith(_FORMAT_PREFIXES):
        return 10, "发行物格式、路径或摘要无效"
    return 30, "本地执行失败"


def main(argv: Sequence[str] | None = None) -> int:
    try:
        arguments = _parser().parse_args(argv)
        result = arguments.handler(arguments)
    except ReleaseError as error:
        exit_code, message = _release_exit(error)
        _write_error(error.code, message)
        return exit_code
    except KeyboardInterrupt:
        _write_error("WFREL_CLI_IO", "本地执行失败")
        return 30
    except Exception:
        _write_error("WFREL_CLI_IO", "本地执行失败")
        return 30
    _write_json(sys.stdout, result)
    return 0


__all__ = ["main"]
