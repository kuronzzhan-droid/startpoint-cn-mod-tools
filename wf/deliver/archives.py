"""Deterministic ZIP construction with an actual compressed-size ceiling."""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

from .changeset import sha256
from wf.view.safety import local_output

MAX_ZIP = 5 * 1024 * 1024
PACK_BUDGET = MAX_ZIP - 64 * 1024


def zip_bytes(names, members) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(names):
            info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, members[name][0])
    return stream.getvalue()


def split_archives(members, *, cap=MAX_ZIP):
    # Keep the historical table-first, descending-uncompressed-size policy.
    order = sorted(members, key=lambda n: (not members[n][1].get("logical_path", "").endswith(".orderedmap"), -len(members[n][0])))
    groups, current, size = [], [], 0
    budget = min(PACK_BUDGET, cap)
    for name in order:
        length = len(members[name][0])
        if current and size + length > budget:
            groups.append(current)
            current, size = [], 0
        current.append(name)
        size += length
    if current:
        groups.append(current)
    result = []
    while groups:
        names = groups.pop(0)
        raw = zip_bytes(names, members)
        if len(raw) <= cap:
            result.append((names, raw))
        elif len(names) == 1:
            raise ValueError(f"single member cannot fit in {cap} byte ZIP: {names[0]}")
        else:
            # Size is checked on the real container, including ZIP overhead.
            midpoint = len(names) // 2
            groups[0:0] = [names[:midpoint], names[midpoint:]]
    return result


def write_archives(out: Path, members, naming):
    records = []
    for seq, (names, raw) in enumerate(split_archives(members), 1):
        filename = naming(seq)
        target = local_output(out / filename)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        records.append({"name": filename, "size": len(raw), "sha256": sha256(raw),
                        "installed_size": sum(len(members[n][0]) for n in names),
                        "members": len(names), "files": sorted(names), "seq": seq})
    return records
