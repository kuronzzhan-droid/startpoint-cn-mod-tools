"""Materialize an immutable input view into a new builder store directory."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil

from .manifest import CDN_ROOTS, ManifestView


def export_store(view, destination, *, copy=False):
    """Create destination/production/<root>; never overwrite existing output.

    Unmodified baseline files use hard links by default. Overlays are written
    as new files, so writing the ZIP members cannot mutate linked inputs.
    Builders that modify their inputs in place must request copy mode.
    """
    raw = os.fspath(destination)
    if raw.startswith(("\\\\", "//")):
        raise ValueError("export destination must be a local path")
    output = Path(raw).resolve()
    baseline = Path(view.store).resolve()
    inputs = [baseline, *(baseline.parent / root for root in CDN_ROOTS if root != "upload")]
    if output == baseline.parent or any(output.is_relative_to(root) for root in inputs):
        raise ValueError("export destination must be outside the baseline production directory")
    if output.exists():
        raise FileExistsError(f"export destination already exists: {output}")
    if hasattr(view, "verify"):
        view.verify()
    output.mkdir(parents=True)
    counts = {"linked": 0, "copied": 0, "overlaid": 0}
    for root in CDN_ROOTS:
        directory = baseline if root == "upload" else baseline.parent / root
        if not directory.is_dir():
            continue
        for source in sorted(directory.glob("*/*")):
            if not source.is_file():
                continue
            member = f"production/{root}/{source.relative_to(directory).as_posix()}"
            ManifestView._validate_member(member)
            if member in view.index:
                continue  # Do not create a hard link only to replace it later.
            if getattr(view, "store_member_sha256", None) is not None:
                view.read_store_member(member)
            target = output / member
            target.parent.mkdir(parents=True, exist_ok=True)
            if copy:
                shutil.copyfile(source, target)
                counts["copied"] += 1
            else:
                try:
                    os.link(source, target)
                except OSError as exc:
                    raise OSError("cannot hard-link baseline; use --copy for another volume") from exc
                counts["linked"] += 1
    for member in sorted(view.index):
        ManifestView._validate_member(member)
        target = output / member
        target.parent.mkdir(parents=True, exist_ok=True)
        data, _ = view.read_member(member)
        target.write_bytes(data)
        counts["overlaid"] += 1
    lock = view.verify() if hasattr(view, "verify") else None
    result = {"schema": "wf-export-store/1", "directory": str(output),
              "store": str(output / "production/upload"), "mode": "copy" if copy else "hardlink",
              "baseVersion": getattr(view, "base_version", "1.4.131"), "tip": view.tip,
              "zips": [str(p) for p in view.zips], **counts, "lock": lock}
    (output / "viewstore.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                                           encoding="utf-8")
    return result
