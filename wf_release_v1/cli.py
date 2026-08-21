"""Stable JSON command line interface for local wf-release-v1 operations."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
from typing import Sequence

from .canonical import canonical_json_bytes, load_json_strict_bytes
from ._cli_errors import release_exit as _release_exit
from ._cli_files import read_stable_metadata
from ._cli_target_commands import add_target_commands
from .errors import ReleaseError
from ._local_cli import (
    run_bootstrap as _run_bootstrap,
    run_install as _run_install,
    run_legacy_install as _run_legacy_install,
    run_legacy_rollback as _run_legacy_rollback,
    run_plan as _run_target_plan,
    run_probe as _run_probe,
    run_resume as _run_resume,
    run_rollback as _run_rollback,
)
from .legacy_share import inspect_legacy_share
from .legacy_import import import_legacy_share
from .legacy_character import adopt_legacy_character
from .character_edit import checkout_character_workspace, seal_edited_character_workspace
from .overlay_builder import build_character_overlay
from .planning import capture_target_requirements
from .producer import BuildReceipt, BuildRequest, build_character_release
from .schema import ReleaseRequirements, parse_requirements
from .verifier import VerificationReport, verify_release


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


def _load_requirements(path: Path) -> ReleaseRequirements:
    raw = read_stable_metadata(path, label="requirements")
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
            replaces=tuple(arguments.replaces),
        )
    )
    return _build_receipt_wire(receipt)


def _run_verify(arguments: argparse.Namespace) -> dict[str, object]:
    return _report_wire(verify_release(Path(arguments.release)))


def _run_inspect_share(arguments: argparse.Namespace) -> dict[str, object]:
    return inspect_legacy_share(Path(arguments.share)).to_wire()


def _run_import_share(arguments: argparse.Namespace) -> dict[str, object]:
    mapping = Path(arguments.mapping) if arguments.mapping is not None else None
    return import_legacy_share(
        Path(arguments.share), Path(arguments.output), mapping=mapping
    ).to_wire()


def _run_adopt_character(arguments: argparse.Namespace) -> dict[str, object]:
    return adopt_legacy_character(
        Path(arguments.imported), Path(arguments.config), Path(arguments.output)
    ).to_wire()


def _run_checkout_character(arguments: argparse.Namespace) -> dict[str, object]:
    return checkout_character_workspace(
        Path(arguments.workspace),
        Path(arguments.output),
        arguments.package_version,
    ).to_wire()


def _run_seal_character(arguments: argparse.Namespace) -> dict[str, object]:
    return seal_edited_character_workspace(Path(arguments.workspace)).to_wire()


def _run_build_overlay(arguments: argparse.Namespace) -> dict[str, object]:
    return build_character_overlay(
        Path(arguments.workspace),
        arguments.from_version,
        arguments.target_version,
        Path(arguments.output),
    ).to_wire()


def _run_capture_requirements(arguments: argparse.Namespace) -> dict[str, object]:
    from .target import ManagedTarget

    return capture_target_requirements(
        ManagedTarget.load(Path(arguments.target)),
        Path(arguments.workspace),
        Path(arguments.output),
    ).to_wire()


def _run_plan_install(arguments: argparse.Namespace) -> dict[str, object]:
    return _run_target_plan(arguments)


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
    build.add_argument("--replaces", action="append", default=[])
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

    share = commands.add_parser(
        "inspect-share", help="只读检查旧 wfshare 并输出迁移计划", output_context=context
    )
    share.add_argument("--share", required=True)
    share.add_argument("--json", action="store_true", required=True)
    share.set_defaults(handler=_run_inspect_share)

    import_share = commands.add_parser(
        "import-share", help="隔离导入已验证的旧 wfshare", output_context=context
    )
    import_share.add_argument("--share", required=True)
    import_share.add_argument("--output", required=True)
    import_share.add_argument("--mapping")
    import_share.add_argument("--json", action="store_true", required=True)
    import_share.set_defaults(handler=_run_import_share)

    adopt = commands.add_parser(
        "adopt-character", help="把完整旧包转换为封印角色工作区", output_context=context
    )
    adopt.add_argument("--imported", required=True)
    adopt.add_argument("--config", required=True)
    adopt.add_argument("--output", required=True)
    adopt.add_argument("--json", action="store_true", required=True)
    adopt.set_defaults(handler=_run_adopt_character)

    checkout = commands.add_parser(
        "checkout-character", help="从封印角色工作区创建隔离编辑副本", output_context=context
    )
    checkout.add_argument("--workspace", required=True)
    checkout.add_argument("--output", required=True)
    checkout.add_argument("--package-version", required=True)
    checkout.add_argument("--json", action="store_true", required=True)
    checkout.set_defaults(handler=_run_checkout_character)

    seal_character = commands.add_parser(
        "seal-character", help="验证并重新封印角色编辑副本", output_context=context
    )
    seal_character.add_argument("--workspace", required=True)
    seal_character.add_argument("--json", action="store_true", required=True)
    seal_character.set_defaults(handler=_run_seal_character)

    overlay = commands.add_parser(
        "build-overlay", help="从密封角色工作区生成 Patch Overlay", output_context=context
    )
    overlay.add_argument("--workspace", required=True)
    overlay.add_argument("--from-version", required=True)
    overlay.add_argument("--target-version", required=True)
    overlay.add_argument("--output", required=True)
    overlay.add_argument("--json", action="store_true", required=True)
    overlay.set_defaults(handler=_run_build_overlay)

    add_target_commands(commands, context, {
        "bootstrap": _run_bootstrap,
        "capture": _run_capture_requirements,
        "install": _run_install,
        "legacy": _run_legacy_install,
        "legacy_rollback": _run_legacy_rollback,
        "plan": _run_plan_install,
        "probe": _run_probe,
        "resume": _run_resume,
        "rollback": _run_rollback,
    })
    return parser


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
