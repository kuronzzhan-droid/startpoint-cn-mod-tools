"""Shared frontend age check for doctor and the Windows launcher."""
from pathlib import Path

from wf.paths import REPOSITORY


def build_state(root=REPOSITORY, static=None):
    root = Path(root)
    frontend = root / "studio"
    index = Path(static) / "index.html" if static is not None else frontend / "dist/index.html"
    if not index.is_file():
        return {"built": False, "stale": True, "reason": "前端尚未构建"}
    inputs = [p for p in (frontend / "src").rglob("*") if p.is_file()]
    inputs += [p for p in frontend.iterdir() if p.is_file() and (
        p.name in {"index.html", "package.json", "package-lock.json"}
        or p.name.startswith(("vite.config.", "tsconfig")))]
    stale = any(p.stat().st_mtime_ns > index.stat().st_mtime_ns for p in inputs)
    return {"built": True, "stale": stale,
            "reason": "源文件或构建配置比前端产物新" if stale else "前端产物不早于源文件及构建配置"}


if __name__ == "__main__":
    try:
        state = build_state()
        print(state["reason"])
        raise SystemExit(1 if state["stale"] else 0)
    except OSError as exc:
        print(f"无法检查前端构建：{exc}")
        raise SystemExit(2)
