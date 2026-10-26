"""Keep offline regression writes inside this checkout, including temp files."""
from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TEMP = ROOT / "work/t"
TEMP.mkdir(parents=True, exist_ok=True)
os.environ["TEMP"] = os.environ["TMP"] = str(TEMP)
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
tempfile.tempdir = str(TEMP)


def _local(value) -> bool:
    if isinstance(value, int) or value is None:
        return True
    text = os.fsdecode(value)
    if text.lower() in {"nul", "\\\\.\\nul", os.devnull.lower()}:
        return True
    # Resolve junctions and Windows extended-length names before checking bounds.
    normalized = str(Path(text).resolve())
    if normalized.startswith("\\\\?\\"):
        normalized = normalized[4:]
    return Path(normalized).is_relative_to(ROOT)


def _audit(event, args):
    targets = ()
    if event == "open":
        name, mode, flags = args
        if (isinstance(mode, str) and any(c in mode for c in "wax+")) or (
                flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)):
            targets = (name,)
    elif event in {"os.remove", "os.rmdir", "os.mkdir", "os.chmod", "os.utime", "os.truncate"}:
        targets = args[:1]
    elif event in {"os.rename", "os.link"}:
        targets = args[:2]
    elif event == "os.symlink":
        targets = args[1:2]
    if any(not _local(target) for target in targets):
        raise PermissionError(f"Offline tests may only write inside the checkout ({event})")


sys.addaudithook(_audit)
