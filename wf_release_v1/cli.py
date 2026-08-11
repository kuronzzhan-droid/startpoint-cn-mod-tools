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
from ._local_cli import (
    run_install as _run_install,
    run_probe as _run_probe,
    run_rollback as _run_rollback,
)
from .producer import BuildReceipt, BuildRequest, build_character_release
from .schema import ReleaseRequirements, parse_requirements
from .verifier import VerificationReport, verify_release


_REPARSE_POINT: Final = 0x0400
_MAX_REQUIREMENTS_BYTES: Final = 1024 * 1024
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
_TRANSACTION_PREFIXES: Final = (
    "WFREL_RECOVERY_",
    "WFREL_TRANSACTION_",
)


def _flush_stream(stream: object) -> None:
    flush = getattr(stream, "flush", None)
    if not callable(flush):
        raise OSError("output cannot be flushed")
    flush()


def _write_text(stream: object, text: str) -> None:
    written = stream.write(text)  # type: ignore[attr-defined]
    if type(written) is not int or written != len(text):
        raise OSError("text output write was incomplete")
    _flush_stream(stream)


def _write_json(stream: object, value: dict[str, object]) -> None:
    raw = canonical_json_bytes(value)
    binary = getattr(stream, "buffer", None)
    if binary is not None and callable(getattr(binary, "write", None)):
        written = binary.write(raw)
        if type(written) is not int or written != len(raw):
            raise OSError("binary output write was incomplete")
        _flush_stream(binary)
        return
    _write_text(stream, raw.decode("utf-8"))


def _write_error(code: str, message: str) -> None:
    _write_json(sys.stderr, {"code": code, "message": message})


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="strict", newline="\n")


def _quarantine_standard_stream(stream: object, name: str) -> None:
    current = getattr(sys, name, None)
    original = getattr(sys, f"__{name}__", None)
    if stream is not current or stream is not original:
        return
    null_descriptor = -1
    try:
        descriptor = stream.fileno()  # type: ignore[attr-defined]
        null_descriptor = os.open(os.devnull, os.O_WRONLY)
        os.dup2(null_descriptor, descriptor)
        try:
            stream.flush()  # type: ignore[attr-defined]
        except Exception:
            pass
        return
    except Exception:
        try:
            replacement = open(
                os.devnull,
                "w",
                encoding="utf-8",
                errors="strict",
                newline="\n",
            )
            setattr(sys, name, replacement)
        except Exception:
            pass
    finally:
        if null_descriptor >= 0:
            try:
                os.close(null_descriptor)
            except OSError:
                pass


def _return_error(code: str, message: str, exit_code: int) -> int:
    stream = sys.stderr
    try:
        _write_error(code, message)
    except Exception:
        _quarantine_standard_stream(stream, "stderr")
        return 30
    return exit_code


class _ParseOutputContext:
    def __init__(self) -> None:
        self.stream: object | None = None


class _ArgumentParser(argparse.ArgumentParser):
    def __init__(
        self,
        *args: object,
        output_context: _ParseOutputContext | None = None,
        **kwargs: object,
    ) -> None:
        self._output_context = output_context or _ParseOutputContext()
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]

    def _print_message(self, message: str, file: object | None = None) -> None:
        if not message:
            return
        stream = file if file is not None else sys.stderr
        self._output_context.stream = stream
        _write_text(stream, message)

    def error(self, message: str) -> None:
        del message
        self._output_context.stream = sys.stderr
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
        opened_snapshot = _snapshot(opened)
        if _is_reparse(opened) or opened_snapshot != before:
            raise OSError("input identity changed before open")
        expected_size = opened.st_size
        with os.fdopen(descriptor, "rb", closefd=True) as stream:
            descriptor = -1
            raw = stream.read(_MAX_REQUIREMENTS_BYTES + 1)
            after_open = os.fstat(stream.fileno())
        after_path = os.lstat(path)
        if (
            _snapshot(after_open) != before
            or _snapshot(after_path) != before
            or _is_reparse(after_path)
        ):
            raise OSError("input identity changed while reading")
        if expected_size > _MAX_REQUIREMENTS_BYTES or len(raw) > _MAX_REQUIREMENTS_BYTES:
            raise ReleaseError(
                "WFREL_REQUIRE_LIMIT",
                "requirements metadata exceeds the supported limit",
                {"label": label},
            )
        if len(raw) != expected_size:
            raise OSError("input length does not match its stable identity")
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


def _parser(output_context: _ParseOutputContext | None = None) -> _ArgumentParser:
    context = output_context or _ParseOutputContext()
    parser = _ArgumentParser(prog="wf-release", output_context=context)
    commands = parser.add_subparsers(dest="command", required=True)

    build = commands.add_parser(
        "build", help="构建不可变发行物", output_context=context
    )
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
        command = commands.add_parser(
            name, help=help_text, output_context=context
        )
        command.add_argument("--release", required=True)
        command.add_argument("--json", action="store_true", required=True)
        command.set_defaults(handler=_run_verify)

    probe = commands.add_parser(
        "probe", help="读取受管目标事实", output_context=context
    )
    probe.add_argument("--target", required=True)
    probe.add_argument("--json", action="store_true", required=True)
    probe.set_defaults(handler=_run_probe)

    install = commands.add_parser(
        "install", help="安装已验证的本地发行物", output_context=context
    )
    install.add_argument("--target", required=True)
    install.add_argument("--release", required=True)
    install.add_argument("--confirm", required=True, choices=("INSTALL_WF_RELEASE",))
    install.set_defaults(handler=_run_install)

    rollback = commands.add_parser(
        "rollback", help="恢复失败事务或显式回到 previous 状态", output_context=context
    )
    rollback.add_argument("--target", required=True)
    rollback_mode = rollback.add_mutually_exclusive_group(required=True)
    rollback_mode.add_argument("--operation")
    rollback_mode.add_argument("--to-release", dest="to_release")
    rollback.add_argument(
        "--confirm",
        required=True,
        choices=("RECOVER_FAILED_INSTALL", "I_UNDERSTAND_DATA_DOWNGRADE_RISK"),
    )
    rollback.set_defaults(handler=_run_rollback)
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
    if error.code == "WFREL_CLI_ARGUMENTS":
        return 2, "命令参数无效"
    if error.code.startswith(_TRANSACTION_PREFIXES):
        return 40, "安装事务未提交或恢复失败"
    if _caused_by_os_error(error):
        return 30, "本地文件操作失败"
    if error.code.startswith(_IO_PREFIXES):
        return 30, "本地文件操作失败"
    if error.code.startswith(_INCOMPATIBLE_PREFIXES):
        return 20, "发布源或依赖要求不兼容"
    if error.code.startswith(_FORMAT_PREFIXES):
        return 10, "发行物格式、路径或摘要无效"
    return 30, "本地执行失败"


def _quarantine_parse_output(context: _ParseOutputContext) -> None:
    stream = context.stream
    if stream is sys.stdout:
        _quarantine_standard_stream(stream, "stdout")
    elif stream is sys.stderr:
        _quarantine_standard_stream(stream, "stderr")


def main(argv: Sequence[str] | None = None) -> int:
    parse_output = _ParseOutputContext()
    output_stream: object | None = None
    try:
        _configure_stdio()
        parser = _parser(parse_output)
        try:
            arguments = parser.parse_args(argv)
        except SystemExit:
            if parse_output.stream is not None:
                try:
                    _flush_stream(parse_output.stream)
                except Exception:
                    _quarantine_parse_output(parse_output)
                    return _return_error("WFREL_CLI_IO", "本地执行失败", 30)
            raise
        result = arguments.handler(arguments)
        output_stream = sys.stdout
        _write_json(output_stream, result)
    except ReleaseError as error:
        if parse_output.stream is not None:
            _quarantine_parse_output(parse_output)
            return _return_error("WFREL_CLI_IO", "本地执行失败", 30)
        if output_stream is not None:
            _quarantine_standard_stream(output_stream, "stdout")
            return _return_error("WFREL_CLI_IO", "本地执行失败", 30)
        exit_code, message = _release_exit(error)
        return _return_error(error.code, message, exit_code)
    except KeyboardInterrupt:
        if parse_output.stream is not None:
            _quarantine_parse_output(parse_output)
        if output_stream is not None:
            _quarantine_standard_stream(output_stream, "stdout")
        return _return_error("WFREL_CLI_IO", "本地执行失败", 30)
    except Exception:
        if parse_output.stream is not None:
            _quarantine_parse_output(parse_output)
        if output_stream is not None:
            _quarantine_standard_stream(output_stream, "stdout")
        return _return_error("WFREL_CLI_IO", "本地执行失败", 30)
    return 0


__all__ = ["main"]
