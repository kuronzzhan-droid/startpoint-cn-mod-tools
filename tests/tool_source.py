"""Find the real source of a root ``wf_*.py`` tool, following its compatibility entry point."""
from __future__ import annotations

import re
from pathlib import Path

_TARGET = re.compile(r'run_as_main\("([\w.]+)"\)')


def tool_source(root: Path, name: str) -> Path:
    """``root / name`` itself, or the ``wf/tools/...`` file it forwards to."""
    path = Path(root) / name
    moved = _TARGET.search(path.read_text(encoding="utf-8"))
    return Path(root) / (moved.group(1).replace(".", "/") + ".py") if moved else path
