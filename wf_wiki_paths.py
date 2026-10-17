"""Filesystem link checks compatible with the project's Python 3.11 baseline."""
from pathlib import Path
import stat


def is_junction(path: Path) -> bool:
    """Inspect the entry itself; never follow a junction or require Path 3.12 APIs.

    Windows lstat exposes the reparse tag on Python 3.8+. Other platforms do
    not have mount-point reparse tags. Missing paths can be checked before
    creation, but permission and other unexpected I/O errors must propagate.
    """
    try:
        metadata = Path(path).lstat()
    except (FileNotFoundError, NotADirectoryError):
        return False
    return getattr(metadata, "st_reparse_tag", 0) == getattr(
        stat, "IO_REPARSE_TAG_MOUNT_POINT", 0xA0000003)
