"""Read-only, hash-bound subtitle evidence for the static character Wiki.

Draft text never establishes a recording's contents. Only a recording digest in
an emitted manifest, or the actual audio next to an original voiceLines dump,
can bind text to a live recording. No synthesis or external service is used.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import re

import wf_assets

SLOT_RE = re.compile(r"(?:ally|battle|home|login|words(?:_[A-Za-z0-9]+)?)/[A-Za-z0-9_]+\Z")
LOGICAL_RE = re.compile(r"character/([A-Za-z0-9_]+)/voice/(.+)\.mp3\Z")
HASH_RE = re.compile(r"[0-9a-f]{64}\Z")
_META_NAMES = {
    "交付清单.json", "voice-manifest.json", "validation.json", "selection.json",
    "lines.json", "voice_lines.json", "voice-report.json", "voice_report.json",
    "selected.json", "qc-summary.json",
}
_SKIP_DIRS = {
    "package", "roots", "raw", "receipts", "attempts", "qc", "asr", "asr-ui",
    "references", "reference-study", "reference-clean", "node_modules", ".git",
    "__pycache__", "takes", "scout", "fixtures",
}


def _json(path: Path):
    try:
        # Refuse accidental huge unrelated reports; these documents are small.
        if path.stat().st_size > 20_000_000:
            return None
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def metadata_files(root: Path, max_depth: int = 5):
    """Bound traversal to the two designated source trees; ignore old takes."""
    if not root.is_dir():
        return
    for base, dirs, files in os.walk(root, followlinks=False):
        depth = len(Path(base).relative_to(root).parts)
        dirs[:] = sorted(d for d in dirs if depth < max_depth
                         and d not in _SKIP_DIRS and not d.startswith("_")
                         and not any(s in d.lower() for s in
                                     (".bak", "backup", "archive", "frozen", "before", "retake")))
        for name in sorted(files):
            if name in _META_NAMES or re.fullmatch(r"voice-\d{8}-lines\.json", name):
                yield Path(base) / name


def _rows(document, inherited_code: str = ""):
    if isinstance(document, list):
        for item in document:
            yield from _rows(item, inherited_code)
    elif isinstance(document, dict):
        code = document.get("code") or document.get("code_name") or inherited_code
        if "slot" in document and (document.get("ja") or document.get("zh")):
            yield document, code
        # Do not recurse into reference audio, before values or API receipts.
        for key in ("selection", "entries", "files", "lines", "voices", "items"):
            if isinstance(document.get(key), (list, dict)):
                yield from _rows(document[key], code)


def _recording_hashes(row: dict) -> set[str]:
    hashes = set()
    for key in ("storage_sha256", "game_sha256", "native_sha256", "standard_sha256", "sha256"):
        value = row.get(key)
        if isinstance(value, str) and HASH_RE.fullmatch(value):
            hashes.add(value)
    files = row.get("files")
    if isinstance(files, dict):
        for kind in ("native", "standard", "game"):
            item = files.get(kind)
            value = item.get("sha256") if isinstance(item, dict) else None
            if isinstance(value, str) and HASH_RE.fullmatch(value):
                hashes.add(value)
    # Deliberately exclude source_sha256, raw_sha256, old_storage_sha256,
    # before_sha256 and references: they may describe a different recording.
    return hashes


def _clean(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def _mpeg_header(data: bytes, offset: int) -> bool:
    header = data[offset:offset + 4]
    if len(header) != 4 or header[0] != 255 or header[1] >> 5 != 7:
        return False
    value = int.from_bytes(header, "big")
    return (value >> 19 & 3 != 1 and value >> 17 & 3 == 1
            and value >> 12 & 15 not in (0, 15) and value >> 10 & 3 != 3)


def frame_digest(data: bytes) -> str | None:
    """Hash identical MPEG frames despite differing dump ID3 text tags.

    Some datamine dumps have 2-63 extra ID3 bytes without an updated tag length.
    Only tagged files may search past the declared tag. Once the first plausible
    frame header is found, its entire stream must validate; never salvage a
    matching suffix after a corrupt frame. Untagged audio must start at offset 0.
    """
    start = 0
    tagged = data.startswith(b"ID3") and len(data) >= 10
    if tagged:
        start = 10 + sum((byte & 127) << shift
                         for byte, shift in zip(data[6:10], (21, 14, 7, 0)))
    stop = min(len(data) - 4, start + 4096) if tagged else 0
    while start <= stop:
        if _mpeg_header(data, start):
            body = data[start:]
            if len(body) >= 128 and body[-128:-125] == b"TAG":
                body = body[:-128]
            probe = wf_assets.mp3_probe(body, 2047)
            # A damaged trailing frame is not an ignorable metadata/padding tail.
            if probe["frames"] >= 2 and probe["tail"] == 0:
                return hashlib.sha256(body).hexdigest()
            return None
        if not tagged:
            return None
        start = data.find(b"\xff", start + 1, stop + 1)
        if start < 0:
            return None
    return None


class SubtitleIndex:
    def __init__(self):
        self.by_hash: dict[str, list[dict]] = defaultdict(list)
        self.slots: dict[str, set[str]] = defaultdict(set)
        self.documents = 0

    def add(self, digest: str, *, slot: str, code: str = "", ja: str = "",
            zh: str = "", source: str = "hash-matched-script"):
        if not HASH_RE.fullmatch(digest) or not SLOT_RE.fullmatch(slot):
            return
        entry = dict(ja=_clean(ja), zh=_clean(zh), textSource=source)
        if not entry["ja"] and not entry["zh"]:
            return
        if entry not in self.by_hash[digest]:
            self.by_hash[digest].append(entry)
        if code:
            self.slots[code].add(slot)

    def match(self, stored: bytes, standard: bytes) -> dict:
        evidence = []
        for raw in (stored, standard):
            evidence.extend(self.by_hash.get(hashlib.sha256(raw).hexdigest(), []))
        frames = frame_digest(standard)
        if frames:
            evidence.extend(self.by_hash.get(frames, []))
        result = dict(ja="", zh="", textSource="missing", conflict=False)
        if not evidence:
            return result
        # Whitespace varies between a wrapped client subtitle and a script.
        for language in ("ja", "zh"):
            variants = {}
            for entry in evidence:
                value = entry[language]
                if value:
                    variants.setdefault(re.sub(r"\s+", "", value), value)
            if len(variants) == 1:
                result[language] = next(iter(variants.values()))
            elif len(variants) > 1:
                result["conflict"] = True
        sources = {entry["textSource"] for entry in evidence}
        result["textSource"] = ("hash-matched-script" if "hash-matched-script" in sources
                                else "hash-matched-original")
        return result


def build_subtitle_index(repo: Path, voice_root: Path | None = None) -> SubtitleIndex:
    voice_root = voice_root or wf_assets.VOICE_DUMP
    index = SubtitleIndex()
    # Original dumps are direct children, and each text is bound to actual MP3
    # bytes. A MOD cloning that recording can inherit its verified original text.
    if voice_root.is_dir():
        for directory in sorted(voice_root.iterdir()):
            if not directory.is_dir():
                continue
            lines = _json(directory / "voiceLines.json")
            if not isinstance(lines, dict):
                continue
            for slot, ja in lines.items():
                if not SLOT_RE.fullmatch(str(slot)) or not isinstance(ja, str):
                    continue
                audio = directory / (slot + ".mp3")
                try:
                    raw = audio.read_bytes()
                except OSError:
                    continue
                index.add(hashlib.sha256(raw).hexdigest(), slot=slot, code=directory.name,
                          ja=ja, source="hash-matched-original")
                frames = frame_digest(wf_assets.mp3_decode(raw))
                if frames:
                    index.add(frames, slot=slot, code=directory.name,
                              ja=ja, source="hash-matched-original")
    for root in (repo / "work" / "character_packs", voice_root):
        for path in metadata_files(root):
            document = _json(path)
            if document is None:
                continue
            index.documents += 1
            if path.name in ("selected.json", "qc-summary.json"):
                from wf_wiki_voice_receipts import add_receipt_evidence
                add_receipt_evidence(index, path, document, root)
            for row, code in _rows(document):
                slot = str(row.get("slot", ""))
                logical = LOGICAL_RE.fullmatch(str(row.get("logical_path", "")))
                if logical:
                    code, slot = logical.groups()
                if not SLOT_RE.fullmatch(slot):
                    continue
                for digest in _recording_hashes(row):
                    index.add(digest, code=str(code), slot=slot,
                              ja=row.get("ja", ""), zh=row.get("zh", ""))
    return index
