"""Read-only manifest views or frozen M0 replay locks."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from wf.paths import root_path
from wf.view.base149 import HistoricalView
from wf.view.balance_inputs import verify_balance_view
from wf.view.chain import ARCHIVE, archive_names, version


def require_version(actual, expected):
    if isinstance(actual, int):
        actual = f"1.4.{actual}"
    if actual != expected:
        raise ValueError(f"balance input tip {actual!r} does not match from_version {expected!r}")


def historical_tip(base, extra):
    """Derive the effective tip from every locked edge, not its claimed label."""
    if extra["tip"] != base["tip"]:
        raise ValueError("historical base/extra tip mismatch")
    current = f"1.4.{base['tip']}"
    groups = []
    for item in extra["zips"]:
        name = Path(item["path"]).name
        match = ARCHIVE.fullmatch(name)
        if match is None:
            raise ValueError(f"invalid historical archive: {name}")
        start, end = match.group(1, 2)
        if not groups or (groups[-1]["depends_on"], groups[-1]["version"]) != (start, end):
            if start != current or version(end) <= version(start):
                raise ValueError(f"historical lock chain gap or rollback: {current} -> {start} -> {end}")
            groups.append({"depends_on": start, "version": end, "chain": []})
            current = end
        groups[-1]["chain"].append(name)
    for group in groups:
        if archive_names(group) != group["chain"]:
            raise ValueError("historical ZIP parts are not in seq order")
    require_version(extra.get("target_base", current), current)
    return current


def open_inputs(recipe: dict, recipe_path: Path):
    """Return (view, verification_callback); no target archive is consulted."""
    spec = recipe.get("input")
    if not spec:
        raise ValueError("balance CLI requires an input view specification")
    if spec["kind"] == "manifest":
        from wf.view import ManifestView
        require_version(spec["tip"], recipe["from_version"])
        lock = recipe_path.parent / spec["lock"] if spec.get("lock") else None
        view = ManifestView(tip=spec["tip"], lock=lock)
        return view, view.verify
    base = json.loads((recipe_path.parent / spec["base_lock"]).read_text("utf-8"))
    extra = json.loads((recipe_path.parent / spec["extra_lock"]).read_text("utf-8"))
    tip = historical_tip(base, extra)
    require_version(tip, recipe["from_version"])
    archives = [root_path(item["path"]) for item in extra["zips"]]

    def verify_extra():
        for item, archive in zip(extra["zips"], archives):
            if hashlib.sha256(archive.read_bytes()).hexdigest() != item["sha256"]:
                raise ValueError(f"balance extra ZIP digest drift: {archive.name}")

    verify_extra()
    view = HistoricalView(tip=base["tip"], extra_zips=archives,
                          store_member_sha256=base["store_members"])
    view.effective_tip = tip

    def verify():
        verify_extra()
        return verify_balance_view(view, base)

    verify()
    return view, verify
