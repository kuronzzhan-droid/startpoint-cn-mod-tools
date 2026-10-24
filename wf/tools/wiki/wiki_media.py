"""Read-only game media export for the standalone character wiki."""
from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from pathlib import Path

import wf_assets
import wf_mod_tool as core
from wf_enhancement_policy import BaselineUnavailable


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class WikiMedia:
    """Copy only referenced media, decode it and address output by content hash."""

    def __init__(self, store: Path, output: Path):
        self.store = store
        self.output = output
        self.entries: dict[str, dict] = {}
        self.errors: list[dict] = []
        self._sources: dict[Path, str] = {}
        try:
            self._previous = json.loads((output / "media-manifest.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self._previous = {}

    def _reuse(self, logical: str, raw: bytes) -> str | None:
        entry = self._previous.get(logical) if isinstance(self._previous, dict) else None
        if not isinstance(entry, dict) or entry.get("sourceSha256") != digest(raw):
            return None
        url = entry.get("url", "")
        if not isinstance(url, str) or not re.fullmatch(r"media/[0-9a-f]{64}\.(?:webp|mp3)", url):
            return None
        path = self.output / url
        if not path.is_file() or digest(path.read_bytes()) != entry.get("sha256"):
            return None
        self.entries[logical] = entry
        return url

    def _read(self, logical: str) -> bytes | None:
        found = wf_assets.locate(self.store, logical)
        if found is None:
            self.errors.append({"logical": logical, "reason": "资源缺失"})
            return None
        raw = found[1].read_bytes()
        self._sources[found[1]] = digest(raw)
        return raw

    def _save(self, logical: str, raw: bytes, decoded: bytes, suffix: str,
              **extra) -> str:
        checksum = digest(decoded)
        relative = f"media/{checksum}{suffix}"
        target = self.output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or digest(target.read_bytes()) != checksum:
            target.write_bytes(decoded)
        self.entries[logical] = {
            "url": relative, "sourceSha256": digest(raw), "sha256": checksum,
            "bytes": len(decoded), **extra,
        }
        return relative

    def has(self, logical: str) -> bool:
        """Check optional native variants without reporting missing forms as errors."""
        return wf_assets.locate(self.store, logical) is not None

    def image(self, logical: str) -> str | None:
        if logical in self.entries:
            return self.entries[logical]["url"]
        raw = self._read(logical)
        if raw is None:
            return None
        return self._render_image(logical, raw)

    def official_image(self, logical: str, baseline, root: str = "medium") -> str | None:
        """Use a trusted official image; never fall back to a known reskinned live file."""
        self.entries.pop(logical, None)
        hashed = core.sha1_path(logical)
        try:
            raw = baseline.get(root, hashed[:2] + "/" + hashed[2:])
        except (BaselineUnavailable, OSError, ValueError, KeyError, zipfile.BadZipFile):
            self.errors.append({"logical": logical, "reason": "官方归档不可用，未使用已知错误图片"})
            return None
        if raw is None:
            self.errors.append({"logical": logical, "reason": "官方图片缺失，未使用已知错误图片"})
            return None
        url = self._render_image(logical, raw)
        if url:
            # Copy reused entries so the previous manifest remains an immutable input.
            self.entries[logical] = {**self.entries[logical],
                                     "sourceKind": "official-baseline", "sourceRoot": root,
                                     "officialTail": baseline.official_tail}
        return url

    def _render_image(self, logical: str, raw: bytes) -> str | None:
        previous = self._reuse(logical, raw)
        if previous:
            return previous
        try:
            from PIL import Image

            decoded = wf_assets.png_decode(raw)
            with Image.open(io.BytesIO(decoded)) as original:
                original.load()
                picture = original.convert("RGBA")
                limit = (1100, 1440) if "full_shot" in logical else (384, 384)
                picture.thumbnail(limit, Image.Resampling.LANCZOS)
                stream = io.BytesIO()
                picture.save(stream, "WEBP", quality=90, method=4)
                return self._save(logical, raw, stream.getvalue(), ".webp",
                                  width=picture.width, height=picture.height)
        except (OSError, ValueError) as exc:
            self.errors.append({"logical": logical, "reason": f"图片无法解码: {exc}"})
            return None

    def audio(self, logical: str) -> str | None:
        if logical in self.entries:
            return self.entries[logical]["url"]
        raw = self._read(logical)
        if raw is None:
            return None
        previous = self._reuse(logical, raw)
        if previous:
            return previous
        decoded = wf_assets.mp3_decode(raw)
        probe = wf_assets.mp3_probe(decoded, 2047)
        # Reject truncated conversions instead of publishing a broken player.
        tail = decoded[probe["end"]:]
        leftover_sync = any(tail[i] in (0x7F, 0xFF) and tail[i + 1] >> 5 == 7
                            for i in range(max(0, len(tail) - 1)))
        if not probe["frames"] or probe["tail"] < 0 or probe["tail"] > 512 or leftover_sync:
            self.errors.append({"logical": logical, "reason": "音频帧解码不完整"})
            return None
        return self._save(logical, raw, decoded, ".mp3", frames=probe["frames"],
                          sampleRates=sorted(probe["srates"]))

    def verify_sources(self) -> None:
        changed = [p.name for p, checksum in self._sources.items()
                   if not p.is_file() or digest(p.read_bytes()) != checksum]
        if changed:
            raise RuntimeError(f"导出期间 {len(changed)} 个媒体源发生变化，请重新导出")

    def summary(self) -> dict:
        files = {entry["url"]: entry for entry in self.entries.values()}
        return {"references": len(self.entries), "files": len(files),
                "bytes": sum(entry["bytes"] for entry in files.values()),
                "errors": self.errors}
