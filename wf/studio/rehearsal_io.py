"""Configuration and confined report IO for offline server rehearsals."""
from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path

from wf.paths import profile_data, root_path

from .drafts import DraftError

SERVER_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")


def server_name(value):
    if not isinstance(value, str) or not SERVER_NAME.fullmatch(value):
        raise DraftError("server 必须是 1–64 位字母、数字、下划线或连字符")
    return value


def server_root(name):
    server_name(name)
    config, _ = profile_data()
    servers = config.get("servers", {})
    if not isinstance(servers, dict) or not isinstance(servers.get(name), dict):
        raise DraftError(f"未配置 servers.{name}.root")
    raw = servers[name].get("root")
    if not isinstance(raw, str) or not raw.strip():
        raise DraftError(f"servers.{name}.root 必须是非空路径")
    root = Path(os.path.expandvars(raw)).expanduser()
    return (root if root.is_absolute() else root_path() / root).resolve()


def configured_server():
    config, _ = profile_data()
    name = config.get("rehearsal_server")
    return server_name(name) if name is not None else None


def read_json(filename):
    def finite(value):
        number = float(value)
        if not math.isfinite(number):
            raise DraftError(f"JSON 非有限数值：{filename}: {value}")
        return number
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise DraftError(f"JSON 重复键：{filename}: {key}")
            result[key] = value
        return result
    return json.loads(Path(filename).read_text("utf-8-sig"), object_pairs_hook=unique,
                      parse_constant=finite, parse_float=finite)


def inside(root, relative):
    """Reject traversal, alternate streams and symlink escapes on both platforms."""
    if (not isinstance(relative, str) or not relative or "\\" in relative
            or ":" in relative or relative.startswith("/")
            or any(p in {"", ".", ".."} for p in relative.split("/"))):
        raise DraftError(f"无效相对路径：{relative!r}")
    root = Path(root).resolve()
    result = (root / relative).resolve()
    if not result.is_relative_to(root):
        raise DraftError(f"路径越界：{relative}")
    return result


def delivery_folder(directory):
    root = Path(directory).resolve()
    if (root / "delivery").is_dir():
        return inside(root, "delivery")
    if not root.is_dir():
        raise DraftError("交付目录不存在")
    return root


def json_bytes(document):
    return (json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False).replace("\n", "\r\n") + "\r\n").encode("utf-8")


def apply_enabled(name):
    config, _ = profile_data()
    servers = config.get("servers") or {}
    entry = servers.get(name) if isinstance(servers, dict) else None
    return isinstance(entry, dict) and entry.get("apply_enabled") is True


def protected_roots():
    """All configured input trees, without importing the CDN catalog."""
    from wf.paths import configured_path
    from .config import server_directory
    roots = []
    configured = server_directory()
    if configured is not None:
        roots.append(configured.parent if configured.name.lower() == "assets" else configured)
    cdn = configured_path("cdn_dir")
    if cdn is not None:
        roots.append(cdn)
    config, _ = profile_data()
    servers = config.get("servers") or {}
    for name in servers if isinstance(servers, dict) else ():
        try:
            roots.append(server_root(name))
        except DraftError:
            continue
    return [p.resolve() for p in roots]


def save_reports(folder, result, markdown, protected):
    folder = Path(folder).resolve()
    # No report may land in any configured server, even through a junction.
    config, _ = profile_data()
    roots = [Path(protected).resolve()]
    from .config import server_directory
    configured = server_directory()
    if configured is not None:
        configured = configured.resolve()
        roots.append(configured.parent if configured.name.lower() == "assets" else configured)
    servers = config.get("servers")
    for name in servers if isinstance(servers, dict) else ():
        try:
            roots.append(server_root(name))
        except DraftError:
            continue  # An unconfigured sibling environment is not a target.
    targets = [inside(folder, f"rehearsal-{result['server']}{suffix}") for suffix in (".json", ".md")]
    for target in targets:
        if any(target.is_relative_to(root) for root in roots):
            raise DraftError("预演报告禁止写入服务端目录")
        if target.exists() and target.stat().st_nlink > 1:
            raise DraftError("预演报告禁止覆盖硬链接文件")
    targets[0].write_bytes(json_bytes(result))
    targets[1].write_bytes(markdown.encode("utf-8"))


def latest(directory):
    folder = delivery_folder(directory)
    reports = []
    for filename in folder.glob("rehearsal-*.json"):
        inside(folder, filename.name)
        try:
            data = read_json(filename)
            if isinstance(data, dict) and data.get("schema") == "wf-studio-rehearsal/1":
                reports.append(data)
        except (OSError, ValueError):
            continue
    return max(reports, key=lambda r: r.get("createdAt", "")) if reports else None
