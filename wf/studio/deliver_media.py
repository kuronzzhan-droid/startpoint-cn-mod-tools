"""Compile studio media to stored client bytes without touching a filesystem."""
from __future__ import annotations

from dataclasses import dataclass, field
import io
import zlib

from PIL import Image

import wf_assets
import wf_atf
import wf_dsl
from wf.deliver.changeset import member_name

from .drafts import DraftError, sha256


@dataclass
class MediaResult:
    members: dict[tuple[str, str], bytes] = field(default_factory=dict)
    assertions: list[dict] = field(default_factory=list)
    checks: list[dict] = field(default_factory=list)


def read_root(source, root: str, logical: str) -> bytes | None:
    """Read the exact CDN root; never satisfy an Android input from medium."""
    if hasattr(source, "view") and hasattr(source.view, "read_member"):
        try:
            return source.view.read_member(member_name(root, logical))[0]
        except (FileNotFoundError, KeyError):
            return None
    # Small read-only sources used by callers/tests may expose this directly.
    if hasattr(source, "read_root"):
        return source.read_root(root, logical)
    return source.raw(logical)


def require_raw(source, root: str, logical: str) -> bytes:
    raw = read_root(source, root, logical)
    if raw is None:
        raise DraftError(f"问题：基线缺少 {root}/{logical}")
    return raw


def png(raw: bytes) -> Image.Image:
    try:
        opened = Image.open(io.BytesIO(wf_assets.png_decode(raw)))
        opened.load()
        if opened.format != "PNG":
            raise ValueError("需要 PNG")
        return opened.convert("RGBA")
    except (ValueError, OSError) as exc:
        raise DraftError(f"问题：PNG 无效：{exc}") from exc


def encode_png(image: Image.Image) -> bytes:
    out = io.BytesIO()
    image.save(out, "PNG", optimize=True)
    return wf_assets.png_encode(out.getvalue())


def tree(raw: bytes):
    inflater = zlib.decompressobj(-15)
    plain = inflater.decompress(raw) + inflater.flush()
    if not inflater.eof or inflater.unused_data or inflater.unconsumed_tail:
        raise DraftError("问题：AMF3 不是完整的单一 raw-deflate 流")
    return wf_dsl.parse_dsl(plain)["tree"]


def encode_tree(value) -> bytes:
    compressor = zlib.compressobj(level=9, wbits=-15)
    return compressor.compress(wf_dsl.encode_amf3(value)) + compressor.flush()


def draft_file(source, store, cid: str, entry: dict) -> bytes:
    raw = store.read_file(cid, entry["draft"])
    if raw is None or sha256(raw) != entry["sha256"] or len(raw) != entry["size"]:
        raise DraftError(f"问题：草稿文件大小或 SHA-256 不符：{entry['draft']}")
    before = read_root(source, entry["root"], entry["logical"])
    actual = sha256(before) if before is not None else None
    if actual != entry["base"]["sha256"]:
        raise DraftError(f"问题：素材旧值断言失败：{entry['logical']}")
    encoding = entry["encoding"]
    if encoding == "png":
        png(raw)
        stored = wf_assets.png_encode(raw)
    elif encoding == "mp3":
        stored = wf_assets.mp3_encode(raw)
        if wf_assets.mp3_decode(stored) != raw:
            raise DraftError("问题：语音存储态往返失败")
    elif encoding == "atf-deflate":
        wf_atf.parse_atf(wf_atf.inflate(raw))
        stored = raw
    else:
        raise DraftError(f"问题：不支持的草稿编码 {encoding}")
    if entry.get("storeSha256") and sha256(stored) != entry["storeSha256"]:
        raise DraftError(f"问题：存储态 SHA-256 不符：{entry['logical']}")
    return stored


def compile_media(source, store, changeset: dict) -> MediaResult:
    """Return stored members, leaf assertions, and five-state media checks."""
    from .deliver_pixel import compile_pixels
    from .deliver_portrait import compile_portraits
    from .deliver_voice import compile_voices

    if source.version != changeset["baseView"]:
        raise DraftError("问题：草稿基线版本与交付视图不一致，请重新保存草稿")
    targets = set()
    for change in changeset["changes"]:
        if change["kind"] not in {"portrait", "pixel_action", "voice_line"}:
            continue
        target = change["kind"], tuple(sorted(change["target"].items()))
        if target in targets:
            raise DraftError("问题：同一个媒体目标在草稿中出现多次")
        targets.add(target)
    result = MediaResult()
    for compile_part in (compile_portraits, compile_pixels, compile_voices):
        part = compile_part(source, store, changeset)
        duplicate = result.members.keys() & part.members.keys()
        if duplicate:
            raise DraftError(f"问题：多个草稿编译到同一成员：{sorted(duplicate)}")
        result.members.update(part.members)
        result.assertions.extend(part.assertions)
        result.checks.extend(part.checks)
    return result
