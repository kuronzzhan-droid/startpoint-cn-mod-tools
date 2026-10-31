"""First-run diagnostics, usable even when optional studio imports fail."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys

from wf.paths import REPOSITORY


def run_doctor(*, fast=False, source=None, server_dir=None, static=None):
    items = []

    def add(name, check, fix):
        try:
            status, current = check()
        except Exception as exc:  # One bad configuration must not hide other checks.
            status, current = "fail", f"{type(exc).__name__}: {exc}"
        items.append({"id": name, "status": status, "current": current, "fix": fix})

    add("python", lambda: ("ok" if sys.version_info >= (3, 11) else "fail", sys.version.split()[0]),
        "使用 Python 3.11 或更新版本（视图摘要使用 hashlib.file_digest）")
    for module in ("PIL", "numpy", "yaml", "jsonschema", "scipy"):
        def dependency(module=module):
            found = importlib.util.find_spec(module) is not None
            optional = module == "scipy"
            note = "；仅白底立绘抠图工具需要，编辑台基本功能不需要" if optional else ""
            return "ok" if found else ("warn" if optional else "fail"), ("已安装 " if found else "未安装 ") + module + note
        add("dependency." + module, dependency, "python -m pip install scipy" if module == "scipy"
            else "python -m pip install -r requirements.txt")

    for executable in ("node", "ffmpeg"):
        def command(executable=executable):
            override = os.environ.get("WF_FFMPEG") if executable == "ffmpeg" else None
            location = shutil.which(override or executable)
            if not location:
                return "warn", f"未找到 {executable}；" + ("前端重建不可用" if executable == "node" else "语音处理不可用")
            if fast:
                return "ok", f"{'WF_FFMPEG' if override else 'PATH'} 可找到 {executable}（快速检查未启动进程）"
            result = subprocess.run([location, "--version" if executable == "node" else "-version"],
                capture_output=True, text=True, errors="replace", timeout=5,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            return ("ok" if result.returncode == 0 else "fail",
                    (result.stdout or result.stderr).splitlines()[0] if (result.stdout or result.stderr) else "无版本输出")
        add(executable, command, f"安装 {executable} 并加入 PATH 后重试")

    from .doctor_data import checks
    checks(add, fast=fast, source=source, server_dir=server_dir)
    from .frontend_build import build_state

    def frontend():
        state = build_state(REPOSITORY, static)
        return "warn" if state["stale"] else "ok", state["reason"]

    add("frontend", frontend, "在 studio 目录运行 npm ci 和 npm run build，或运行 studio.bat")
    counts = {status: sum(i["status"] == status for i in items) for status in ("ok", "warn", "fail")}
    return {"ok": counts["fail"] == 0, "mode": "fast" if fast else "full", "counts": counts, "items": items}


def summary(report):
    return "编辑台体检：" + " / ".join(f"{key} {value}" for key, value in report["counts"].items()) + "；详情：python -m wf.studio doctor"


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m wf.studio doctor")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = run_doctor()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for item in report["items"]:
            print(f"[{item['status']}] {item['id']}: {item['current']}\n  修复：{item['fix']}")
        print(summary(report))
    return 0 if report["ok"] else 1
