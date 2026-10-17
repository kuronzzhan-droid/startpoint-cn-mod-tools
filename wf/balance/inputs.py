"""Read-only manifest views or frozen M0 replay locks."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from wf.paths import root_path
from wf.view.base149 import HistoricalView
from wf.view.balance_inputs import verify_balance_view


def open_inputs(recipe: dict, recipe_path: Path):
    """Return (view, verification_callback); no target archive is consulted."""
    spec = recipe.get("input")
    if not spec:
        raise ValueError("balance CLI requires an input view specification")
    if spec["kind"] == "manifest":
        from wf.view import ManifestView
        lock = recipe_path.parent / spec["lock"] if spec.get("lock") else None
        view = ManifestView(tip=spec["tip"], lock=lock)
        return view, view.verify
    base = json.loads((recipe_path.parent / spec["base_lock"]).read_text("utf-8"))
    extra = json.loads((recipe_path.parent / spec["extra_lock"]).read_text("utf-8"))
    if extra["tip"] != base["tip"]:
        raise ValueError("historical base/extra tip mismatch")
    archives = [root_path(item["path"]) for item in extra["zips"]]

    def verify_extra():
        for item, archive in zip(extra["zips"], archives):
            if hashlib.sha256(archive.read_bytes()).hexdigest() != item["sha256"]:
                raise ValueError(f"balance extra ZIP digest drift: {archive.name}")

    verify_extra()
    view = HistoricalView(tip=base["tip"], extra_zips=archives,
                          store_member_sha256=base["store_members"])

    def verify():
        verify_extra()
        return verify_balance_view(view, base)

    verify()
    return view, verify
