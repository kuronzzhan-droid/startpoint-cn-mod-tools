"""Stable public exit families for wf-release command failures."""

from __future__ import annotations

from typing import Final

from .errors import ReleaseError


_FORMAT_PREFIXES: Final = (
    "WFREL_ARCHIVE_", "WFREL_BUILD_LIMIT", "WFREL_BUILD_PATH_",
    "WFREL_BUILD_REQUEST_", "WFREL_HASH_", "WFREL_JSON_",
    "WFREL_OVERLAY_INVALID", "WFREL_OVERLAY_LIMIT", "WFREL_OVERLAY_BUILD_",
    "WFREL_PATH_", "WFREL_SCHEMA_", "WFREL_SHARE_INVALID",
)
_INCOMPATIBLE_PREFIXES: Final = (
    "WFREL_BUILD_SOURCE_", "WFREL_CHARACTER_EDIT_", "WFREL_CHARACTER_SOURCE_",
    "WFREL_CHARACTER_ADOPTION_", "WFREL_COMPONENT_", "WFREL_OVERLAY_GRAPH",
    "WFREL_OWNERSHIP_", "WFREL_REQUIRE_", "WFREL_TARGET_PROTOCOL",
)
_IO_PREFIXES: Final = (
    "WFREL_BUILD_IO", "WFREL_BUILD_OUTPUT_", "WFREL_CLI_IO", "WFREL_SHARE_IO",
)
_TRANSACTION_PREFIXES: Final = ("WFREL_RECOVERY_", "WFREL_TRANSACTION_")


def _caused_by_os_error(error: BaseException) -> bool:
    current: BaseException | None = error
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        if isinstance(current, OSError):
            return True
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    return False


def release_exit(error: ReleaseError) -> tuple[int, str]:
    if error.code == "WFREL_CLI_ARGUMENTS":
        return 2, "命令参数无效"
    if error.code.startswith(_TRANSACTION_PREFIXES):
        return 40, "安装事务未提交或恢复失败"
    if _caused_by_os_error(error) or error.code.startswith(_IO_PREFIXES):
        return 30, "本地文件操作失败"
    if error.code.startswith(_INCOMPATIBLE_PREFIXES):
        return 20, "发布源或依赖要求不兼容"
    if error.code.startswith(_FORMAT_PREFIXES):
        return 10, "发行物格式、路径或摘要无效"
    return 30, "本地执行失败"


__all__ = ["release_exit"]
