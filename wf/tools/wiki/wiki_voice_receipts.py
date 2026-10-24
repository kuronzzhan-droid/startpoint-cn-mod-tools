"""Bind generation-receipt dialogue to the exact mastered, currently live audio."""
from __future__ import annotations

import hashlib
from pathlib import Path
import re

from wf_wiki_voice_sources import SLOT_RE, _json


def _inside(path, root: Path) -> Path | None:
    if not isinstance(path, (str, Path)):
        return None
    path = Path(path).resolve()
    return path if path.is_relative_to(root.resolve()) else None


def _add(index, receipt_path: Path, qc_path: Path, root: Path):
    receipt_path, qc_path = _inside(receipt_path, root), _inside(qc_path, root)
    if not receipt_path or not qc_path:
        return
    receipt, qc = _json(receipt_path), _json(qc_path)
    if not isinstance(receipt, dict) or not isinstance(qc, dict):
        return
    slot = str(qc.get("slot", ""))
    if not SLOT_RE.fullmatch(slot) or receipt.get("slot") != slot:
        return
    # Text comes from the actual successful request, not today's editable plan.
    # QC's input digest must be that request's recorded output digest.
    raw_digest = receipt.get("sha256")
    if (not raw_digest or raw_digest != qc.get("source_sha256")
            or receipt.get("status") not in ("generated", "cached")
            or receipt.get("http_status", 200) != 200):
        return
    standard = _inside(qc.get("standard"), root)
    if standard is None:
        return
    try:
        digest = hashlib.sha256(standard.read_bytes()).hexdigest()
    except OSError:
        return
    if digest != qc.get("standard_sha256"):
        return
    index.add(digest, slot=slot, code=str(qc.get("code", "")),
              ja=receipt.get("ja", ""), zh=receipt.get("zh", ""))


def add_receipt_evidence(index, path: Path, document, root: Path):
    """Follow only explicit selected records or bounded role/slot QC summaries."""
    if not isinstance(document, dict):
        return
    if path.name == "selected.json":
        roles = document.get("roles", {})
        if not isinstance(roles, dict):
            return
        for selections in roles.values():
            if not isinstance(selections, dict):
                continue
            for item in selections.values():
                if isinstance(item, dict) and item.get("receipt") and item.get("qc"):
                    _add(index, Path(item["receipt"]), Path(item["qc"]), root)
    elif path.name == "qc-summary.json":
        items = document.get("items", [])
        if not isinstance(items, list):
            return
        for item in items:
            if not isinstance(item, dict):
                continue
            role, slot = str(item.get("role", "")), str(item.get("slot", ""))
            if not re.fullmatch(r"[A-Za-z0-9_-]+", role) or not SLOT_RE.fullmatch(slot):
                continue
            base = path.parent / role
            _add(index, base / "receipts" / (slot + ".json"),
                 base / "qc" / (slot + ".json"), root)
