"""Process-local write fence for historical recipe replay."""
import os
import sys
import tempfile
from pathlib import Path
from wf.paths import REPOSITORY

def local_output(value, root=REPOSITORY):
    """Resolve a local output and reject UNC paths before filesystem access."""
    raw = os.fsdecode(value)
    if raw.lower().startswith("\\\\?\\unc\\") or (raw.startswith("\\\\") and not raw.startswith("\\\\?\\")):
        raise PermissionError("recipe output cannot use a UNC path")
    if raw.startswith("\\\\?\\"):
        raw = raw[4:]
    actual = Path(raw).resolve()
    if not actual.is_relative_to(Path(root).resolve()):
        raise PermissionError(f"recipe write outside checkout: {actual}")
    return actual


def restrict_writes(root=REPOSITORY):
    """Reject Python filesystem writes outside this checkout, including symlinks."""
    allowed = Path(root).resolve()
    sys.dont_write_bytecode = True
    reads = set()
    def check(value):
        if isinstance(value, (str, bytes, os.PathLike)):
            local_output(value, allowed)
    def audit(event, args):
        if event == "open":
            target, mode, flags = args
            if (isinstance(mode, str) and any(c in mode for c in "wax+")) or (flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)):
                check(target)
            elif isinstance(target, (str, bytes, os.PathLike)):
                reads.add(Path(os.fsdecode(target)).resolve())
        elif event in {"os.mkdir", "os.remove", "os.rmdir", "os.chmod", "os.utime", "os.truncate"}:
            check(args[0])
        elif event in {"os.rename", "os.replace"}:
            check(args[0]); check(args[1])
        elif event in {"os.link", "os.symlink"}:
            # No links back to source inputs: output should remain independent.
            raise PermissionError("recipe replay does not create filesystem links")
    sys.addaudithook(audit)
    temp = local_output(allowed / "work/m0/recipe-tmp", allowed)
    temp.mkdir(parents=True, exist_ok=True)
    os.environ["TEMP"] = os.environ["TMP"] = str(temp)
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    tempfile.tempdir = str(temp)
    return reads
