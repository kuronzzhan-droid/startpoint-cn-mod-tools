"""Version identity and delivery validation for explicitly ordered extra ZIPs."""
from pathlib import Path

from .chain import ARCHIVE, version


def effective_version(tip, archives):
    """Describe the highest named overlay version without changing the chain tip."""
    targets = [tip]
    for archive in archives:
        match = ARCHIVE.fullmatch(Path(archive).name)
        if match:
            targets.append(match[2])
    return max(targets, key=version)


def delivery_tip(tip, archives):
    """Require forward contiguous edges and ordered parts numbered from one.

    An explicit list defines each edge's parts, just as a manifest chain does;
    filenames cannot establish whether an unlisted final part exists elsewhere.
    Arbitrary overlays remain readable, but cannot claim delivery provenance.
    """
    current, edge, next_part = tip, None, 1
    for archive in archives:
        name = Path(archive).name
        match = ARCHIVE.fullmatch(name)
        if match is None:
            raise ValueError(f"extra ZIP requires a versioned pinball archive name: {name}")
        before, after, part = match[1], match[2], int(match[3])
        if (before, after) != edge:
            if before != current or version(after) <= version(before):
                raise ValueError(f"extra ZIP chain is not continuous after {current}: {name}")
            edge, current, next_part = (before, after), after, 1
        if part != next_part:
            raise ValueError(f"extra ZIP has duplicate, missing or unordered part {next_part}: {name}")
        next_part += 1
    return current


def locked_delivery_tip(lock):
    """Recover the effective endpoint from a portable lock, retaining its cutoff."""
    if not isinstance(lock, dict) or lock.get("schema") != "wf-view-lock/1":
        raise ValueError("invalid baseline view lock")
    base, cutoff = lock.get("base_version"), lock.get("tip")
    version(base)
    version(cutoff)
    records = lock.get("zips")
    if not isinstance(records, list) or any(not isinstance(row, dict) or not isinstance(row.get("name"), str)
                                            for row in records):
        raise ValueError("invalid baseline view lock ZIP list")
    names = [row["name"] for row in records]
    terminal = delivery_tip(base, names)
    endpoints = {base, *(ARCHIVE.fullmatch(Path(name).name)[2] for name in names)}
    if cutoff not in endpoints:
        raise ValueError("baseline lock tip is not on the locked ZIP chain")
    return terminal
