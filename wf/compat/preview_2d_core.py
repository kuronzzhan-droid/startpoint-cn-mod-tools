"""Read-only loaders for local 2D frame and World Flipper pixel-art previews."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import struct
from typing import Any
import unicodedata
import zlib

from wf_mod_tool import AMF3Reader


MAX_METADATA_BYTES = 8 * 1024 * 1024
MAX_PNG_BYTES = 64 * 1024 * 1024
MAX_FRAMES = 4096
MAX_DIMENSION = 16384
MAX_FRAME_NUMBER = 2_147_483_647
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_STORED_PNG_SIGNATURE = b"\x89png\r\n\x1a\n"
_REPARSE_POINT = 0x400
_NUMBERED_STEM = re.compile(r"^(.*?)(\d+)$")
_FRAME_NUMBER = re.compile(r"(\d+)$")


class PreviewError(ValueError):
    pass


@dataclass(frozen=True)
class FileIdentity:
    size: int
    mtime_ns: int
    device: int
    inode: int
    mode: int
    digest: str


@dataclass(frozen=True)
class AssetRef:
    path: Path
    identity: FileIdentity


@dataclass(frozen=True)
class PreviewBundle:
    manifest: dict[str, Any]
    assets: dict[str, AssetRef]

    def read_asset(self, token: str) -> bytes:
        ref = self.assets.get(token)
        if ref is None:
            raise PreviewError("unknown preview asset token")
        data, identity = _read_stable(ref.path, MAX_PNG_BYTES)
        if identity != ref.identity:
            raise PreviewError("preview asset changed after preview load")
        if data.startswith(_STORED_PNG_SIGNATURE):
            return _PNG_SIGNATURE + data[len(_PNG_SIGNATURE):]
        return data


def _is_reparse(info: os.stat_result) -> bool:
    return bool(getattr(info, "st_file_attributes", 0) & _REPARSE_POINT)


def _regular_lstat(path: Path) -> os.stat_result:
    try:
        info = path.lstat()
    except OSError as error:
        raise PreviewError(f"preview input is unavailable: {path.name}") from error
    if _is_reparse(info) or not stat.S_ISREG(info.st_mode):
        raise PreviewError(f"preview input must be a regular non-reparse file: {path.name}")
    return info


def _directory(path: Path) -> Path:
    try:
        info = path.lstat()
    except OSError as error:
        raise PreviewError("preview source directory is unavailable") from error
    if _is_reparse(info) or not stat.S_ISDIR(info.st_mode):
        raise PreviewError("preview source must be a non-reparse directory")
    return path.resolve(strict=True)


def _identity(info: os.stat_result, data: bytes) -> FileIdentity:
    return FileIdentity(
        size=info.st_size,
        mtime_ns=info.st_mtime_ns,
        device=info.st_dev,
        inode=info.st_ino,
        mode=info.st_mode,
        digest=hashlib.sha256(data).hexdigest(),
    )


def _read_stable(path: Path, limit: int) -> tuple[bytes, FileIdentity]:
    before_path = _regular_lstat(path)
    if before_path.st_size > limit:
        raise PreviewError(f"preview input exceeds {limit} bytes: {path.name}")
    try:
        with path.open("rb") as stream:
            before_fd = os.fstat(stream.fileno())
            data = stream.read(limit + 1)
            after_fd = os.fstat(stream.fileno())
    except OSError as error:
        raise PreviewError(f"preview input cannot be read: {path.name}") from error
    after_path = _regular_lstat(path)
    if len(data) > limit:
        raise PreviewError(f"preview input exceeds {limit} bytes: {path.name}")
    fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_mode")
    if any(getattr(before_path, key) != getattr(before_fd, key) for key in fields):
        raise PreviewError(f"preview input identity changed while opening: {path.name}")
    if any(getattr(before_fd, key) != getattr(after_fd, key) for key in fields):
        raise PreviewError(f"preview input changed while reading: {path.name}")
    if any(getattr(after_fd, key) != getattr(after_path, key) for key in fields):
        raise PreviewError(f"preview input changed after reading: {path.name}")
    return data, _identity(after_fd, data)


def _png(path: Path) -> tuple[int, int, FileIdentity]:
    data, identity = _read_stable(path, MAX_PNG_BYTES)
    if (
        len(data) < 24
        or data[:8] not in (_PNG_SIGNATURE, _STORED_PNG_SIGNATURE)
        or data[12:16] != b"IHDR"
    ):
        raise PreviewError(f"invalid PNG header: {path.name}")
    width, height = struct.unpack(">II", data[16:24])
    if not (0 < width <= MAX_DIMENSION and 0 < height <= MAX_DIMENSION):
        raise PreviewError(f"invalid PNG dimensions: {path.name}")
    return width, height, identity


def _json_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PreviewError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _inflate(data: bytes, name: str) -> bytes:
    candidates = (data, data[4:]) if len(data) > 4 else (data,)
    for candidate in candidates:
        for window in (-15, 15):
            try:
                inflater = zlib.decompressobj(window)
                plain = inflater.decompress(candidate, MAX_METADATA_BYTES + 1)
                if len(plain) > MAX_METADATA_BYTES or inflater.unconsumed_tail:
                    continue
                plain += inflater.flush()
                if (inflater.eof and not inflater.unused_data and not inflater.unconsumed_tail
                        and len(plain) <= MAX_METADATA_BYTES):
                    return plain
            except zlib.error:
                pass
    raise PreviewError(f"invalid deflate metadata: {name}")


def _tree(path: Path) -> Any:
    data, _identity_value = _read_stable(path, MAX_METADATA_BYTES)
    if path.suffix == ".json":
        try:
            return json.loads(data.decode("utf-8"), object_pairs_hook=_json_pairs)
        except PreviewError:
            raise
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise PreviewError(f"invalid JSON metadata: {path.name}") from error
    plain = _inflate(data, path.name)
    try:
        reader = AMF3Reader(plain)
        value = reader.read_value()
    except (IndexError, KeyError, struct.error, UnicodeDecodeError, ValueError) as error:
        raise PreviewError(f"invalid AMF3 metadata: {path.name}") from error
    if reader.pos != len(plain):
        raise PreviewError(f"trailing AMF3 bytes: {path.name}")
    return value


def _metadata(root: Path, stem: str, required: bool = True) -> Any:
    candidates = (root / f"{stem}.amf3.deflate", root / f"{stem}.json")
    found = [path for path in candidates if path.exists()]
    if len(found) > 1:
        raise PreviewError(f"ambiguous metadata formats: {stem}")
    if not found:
        if required:
            raise PreviewError(f"required preview metadata is missing: {stem}")
        return {}
    return _tree(found[0])


def _integer(value: Any, label: str, *, minimum: int = 0,
             maximum: int = MAX_FRAME_NUMBER) -> int:
    if (isinstance(value, bool) or not isinstance(value, int)
            or value < minimum or value > maximum):
        raise PreviewError(f"{label} must be an integer from {minimum} to {maximum}")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or any(ord(ch) < 0x20 for ch in value):
        raise PreviewError(f"{label} must be non-empty text without controls")
    return value


def _asset_token(number: int) -> str:
    return f"asset-{number:04d}"


def _sequence_preview(root: Path) -> PreviewBundle:
    try:
        pngs = sorted((path for path in root.iterdir() if path.suffix.lower() == ".png"),
                      key=lambda path: path.name)
    except OSError as error:
        raise PreviewError("preview source directory cannot be enumerated") from error
    if not pngs:
        raise PreviewError("no PNG frames found in preview source")
    if len(pngs) > MAX_FRAMES:
        raise PreviewError(f"preview contains more than {MAX_FRAMES} frames")
    assets: dict[str, AssetRef] = {}
    groups: dict[str, list[tuple[int, str, int, int]]] = {}
    fallback = 0
    max_width = max_height = 0
    for index, path in enumerate(pngs, 1):
        width, height, identity = _png(path)
        token = _asset_token(index)
        assets[token] = AssetRef(path, identity)
        match = _NUMBERED_STEM.fullmatch(path.stem)
        if match:
            name = match.group(1).rstrip(" _-.") or "default"
            frame_number = int(match.group(2))
            if frame_number > MAX_FRAME_NUMBER:
                raise PreviewError(f"PNG frame number exceeds {MAX_FRAME_NUMBER}: {path.name}")
        else:
            name, frame_number = "default", fallback
            fallback += 1
        groups.setdefault(name, []).append((frame_number, token, width, height))
        max_width, max_height = max(max_width, width), max(max_height, height)
    sequences = []
    for name in sorted(groups):
        rows = sorted(groups[name], key=lambda row: (row[0], row[1]))
        if len({row[0] for row in rows}) != len(rows):
            raise PreviewError(f"duplicate frame number in PNG sequence: {name}")
        sequences.append({
            "name": name, "kind": "loop", "frameRate": 60,
            "frames": [{
                "frameNumber": number, "asset": token,
                "source": {"x": 0, "y": 0, "w": width, "h": height},
                "destination": {"x": (max_width - width) // 2,
                                "y": (max_height - height) // 2,
                                "w": width, "h": height},
                "rotated": False,
            } for number, token, width, height in rows],
        })
    return PreviewBundle(_manifest("png-sequence", max_width, max_height, sequences), assets)


def _variant_files(root: Path, variant: str) -> tuple[Path, str, str]:
    choices = {
        "normal": ("sprite_sheet.png", "sprite_sheet.atlas", "pixelart"),
        "special": ("special_sprite_sheet.png", "special_sprite_sheet.atlas", "special"),
    }
    if variant == "auto":
        variant = "normal" if (root / choices["normal"][0]).exists() else "special"
    if variant not in choices:
        raise PreviewError("preview variant must be auto, normal, or special")
    sheet_name, atlas_stem, data_stem = choices[variant]
    sheet = root / sheet_name
    if not sheet.exists():
        raise PreviewError(f"sprite sheet is missing for {variant} variant")
    return sheet, atlas_stem, data_stem


def _sheet_preview(root: Path, variant: str) -> PreviewBundle:
    sheet, atlas_stem, data_stem = _variant_files(root, variant)
    sheet_width, sheet_height, identity = _png(sheet)
    atlas = _metadata(root, atlas_stem)
    timeline = _metadata(root, f"{data_stem}.timeline")
    frame = _metadata(root, f"{data_stem}.frame", required=False)
    if not isinstance(atlas, list) or not atlas:
        raise PreviewError("atlas metadata must be a non-empty array")
    if not isinstance(timeline, dict) or not isinstance(timeline.get("sequences"), list):
        raise PreviewError("timeline sequences must be an array")
    if not isinstance(frame, dict):
        raise PreviewError("frame metadata must be an object")
    entries: dict[int, dict[str, Any]] = {}
    canvas_width = canvas_height = 0
    for offset, raw in enumerate(atlas):
        if not isinstance(raw, dict):
            raise PreviewError(f"atlas entry {offset} must be an object")
        name = _text(raw.get("n"), f"atlas entry {offset} name")
        match = _FRAME_NUMBER.search(name)
        if not match:
            continue
        number = int(match.group(1))
        if number in entries:
            raise PreviewError(f"duplicate atlas frame number: {number}")
        x = _integer(raw.get("x"), "atlas x", maximum=MAX_DIMENSION)
        y = _integer(raw.get("y"), "atlas y", maximum=MAX_DIMENSION)
        width = _integer(raw.get("w"), "atlas width", minimum=1, maximum=MAX_DIMENSION)
        height = _integer(raw.get("h"), "atlas height", minimum=1, maximum=MAX_DIMENSION)
        rotated = raw.get("r", False)
        if not isinstance(rotated, bool):
            raise PreviewError("atlas rotation flag must be boolean")
        # Atlas w/h describe the rectangle as stored in the sheet.  ``r`` tells
        # the renderer how to rotate that crop; swapping the bounds here rejects
        # legitimate edge-packed frames such as Rolf special0132.
        if x + width > sheet_width or y + height > sheet_height:
            raise PreviewError(f"atlas frame is outside sprite sheet: {name}")
        fx = _integer(raw.get("fx", 0), "atlas fx", minimum=-MAX_DIMENSION,
                      maximum=MAX_DIMENSION)
        fy = _integer(raw.get("fy", 0), "atlas fy", minimum=-MAX_DIMENSION,
                      maximum=MAX_DIMENSION)
        fw = _integer(raw.get("fw", width), "atlas frame width", minimum=1,
                      maximum=MAX_DIMENSION)
        fh = _integer(raw.get("fh", height), "atlas frame height", minimum=1,
                      maximum=MAX_DIMENSION)
        canvas_width, canvas_height = max(canvas_width, fw), max(canvas_height, fh)
        entries[number] = {
            "atlasName": name,
            "source": {"x": x, "y": y, "w": width, "h": height},
            "destination": {"x": -fx, "y": -fy, "w": width, "h": height},
            "rotated": rotated,
        }
    if not entries:
        raise PreviewError("atlas contains no numbered frames")
    keys = sorted(entries)
    sequences = []
    names: set[str] = set()
    total = 0
    for offset, raw in enumerate(timeline["sequences"]):
        if not isinstance(raw, dict):
            raise PreviewError(f"timeline sequence {offset} must be an object")
        name = _text(raw.get("name"), f"timeline sequence {offset} name")
        if name in names:
            raise PreviewError(f"duplicate timeline sequence: {name}")
        names.add(name)
        kind = raw.get("kind")
        if kind not in ("loop", "once", "pass"):
            raise PreviewError(f"invalid timeline sequence kind: {kind}")
        begin = _integer(raw.get("begin"), "timeline begin")
        end = _integer(raw.get("end"), "timeline end")
        if begin > end:
            raise PreviewError("timeline begin must not exceed end")
        total += end - begin + 1
        if total > MAX_FRAMES:
            raise PreviewError(f"preview contains more than {MAX_FRAMES} timeline frames")
        rendered = []
        for number in range(begin, end + 1):
            available = [key for key in keys if key <= number]
            entry = entries[available[-1] if available else keys[0]]
            rendered.append({"frameNumber": number, "asset": "asset-0001", **entry})
        sequences.append({"name": name, "kind": kind, "frameRate": 60, "frames": rendered})
    if not sequences:
        raise PreviewError("timeline contains no sequences")
    origin_x = _integer(frame.get("originX", canvas_width // 2), "frame originX",
                        minimum=-MAX_DIMENSION, maximum=MAX_DIMENSION)
    origin_y = _integer(frame.get("originY", canvas_height // 2), "frame originY",
                        minimum=-MAX_DIMENSION, maximum=MAX_DIMENSION)
    assets = {"asset-0001": AssetRef(sheet, identity)}
    manifest = _manifest("sprite-sheet", canvas_width, canvas_height, sequences,
                         origin_x=origin_x, origin_y=origin_y)
    return PreviewBundle(manifest, assets)


def _manifest(mode: str, width: int, height: int, sequences: list[dict[str, Any]],
              *, origin_x: int | None = None, origin_y: int | None = None) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "mode": mode,
        "canvas": {
            "width": width, "height": height,
            "originX": width // 2 if origin_x is None else origin_x,
            "originY": height // 2 if origin_y is None else origin_y,
        },
        "sequences": sequences,
        "readOnly": True,
        "renderingNote": (
            "逐帧 PNG 与 sprite-sheet 动画按 atlas/timeline 预览；战斗特效仅能作为帧墙，"
            "未复刻 parts 骨架矩阵补间，因此不是游戏内最终表现。"
        ),
    }


def _logical_path(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value.startswith("/")
        or "\\" in value
        or unicodedata.normalize("NFC", value) != value
        or any(ord(character) <= 0x1F or ord(character) == 0x7F for character in value)
    ):
        raise PreviewError("character manifest contains an invalid logical path")
    parts = value.split("/")
    if any(part in ("", ".", "..") or ":" in part for part in parts):
        raise PreviewError("character manifest contains an invalid logical path")
    return value


def _declared_package_pixelart(source: Path) -> tuple[Path, str] | None:
    package = source
    nested = source / "package"
    if nested.exists():
        package = _directory(nested)
    manifest_path = package / "manifest.json"
    if not manifest_path.exists():
        return None
    manifest = _tree(manifest_path)
    roots = manifest.get("roots") if isinstance(manifest, dict) else None
    common = roots.get("common") if isinstance(roots, dict) else None
    if not isinstance(common, list):
        raise PreviewError("character manifest common root must be an array")
    candidates: set[str] = set()
    for offset, raw in enumerate(common):
        if not isinstance(raw, dict):
            raise PreviewError(f"character manifest common entry {offset} must be an object")
        logical = _logical_path(raw.get("logical_path"))
        parts = logical.split("/")
        if len(parts) >= 2 and parts[-1] in (
            "sprite_sheet.png", "special_sprite_sheet.png",
        ) and parts[-2] == "pixelart":
            candidates.add("/".join(parts[:-1]))
    if not candidates:
        raise PreviewError("character manifest declares no pixelart sprite sheet")
    if len(candidates) != 1:
        raise PreviewError("character manifest has ambiguous pixelart roots")
    logical_root = next(iter(candidates))
    pixelart = package / "roots" / "common" / Path(logical_root)
    return _directory(pixelart), logical_root


def load_preview(source: str | Path, *, variant: str = "auto") -> PreviewBundle:
    root = _directory(Path(source))
    declared = _declared_package_pixelart(root)
    logical_root: str | None = None
    if declared is not None:
        root, logical_root = declared
    else:
        pixelart = root / "pixelart"
        if pixelart.exists():
            root = _directory(pixelart)
    has_sheet = (root / "sprite_sheet.png").exists() or (root / "special_sprite_sheet.png").exists()
    bundle = _sheet_preview(root, variant) if has_sheet else _sequence_preview(root)
    if logical_root is None:
        return bundle
    return PreviewBundle({**bundle.manifest, "sourceLogicalRoot": logical_root}, bundle.assets)
