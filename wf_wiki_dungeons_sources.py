"""Bounded, read-only dungeon asset snapshots; never write to a game store."""
from __future__ import annotations

import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

import wf_assets
import wf_quest_lib as quests

MAX_TABLE_BYTES = 8 * 1024 * 1024
MAX_IMAGE_BYTES = 16 * 1024 * 1024


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def checksum(raw):
    return hashlib.sha256(raw).hexdigest()


def checked_logical(logical):
    if not isinstance(logical, str) or not re.fullmatch(r"(?:master/quest/[a-zA-Z0-9_/-]+\.orderedmap|quest/[a-zA-Z0-9_/-]+\.png)", logical):
        raise ValueError("只允许已解析的副本元表和图片逻辑路径")
    return logical


def checked_gray_url(value):
    parsed = urlsplit(value)
    if (parsed.scheme not in ("http", "https") or not parsed.hostname
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or not parsed.path.rstrip("/").endswith("/dummy/download/production/upload")):
        raise ValueError("灰服 URL 必须是不含凭据的游戏资源 upload 根目录")
    return value.rstrip("/")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def read_bounded(response, limit):
    size = response.headers.get("Content-Length")
    if size and int(size) > limit:
        raise ValueError("远端资源超过大小上限")
    raw = response.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("远端资源超过大小上限")
    if not raw:
        raise ValueError("远端资源为空")
    return raw


class DungeonSources:
    def __init__(self, store, *, snapshot=None, gray_url=None, timeout=15):
        self.store = Path(store).resolve()
        self.snapshot = Path(snapshot).resolve() if snapshot else None
        self.gray_url = checked_gray_url(gray_url) if gray_url else None
        if self.gray_url and self.snapshot is None:
            raise ValueError("读取灰服必须指定独立 snapshot 目录")
        if self.snapshot and (self.snapshot == self.store or self.snapshot.is_relative_to(self.store)):
            raise ValueError("快照不能位于游戏 store 内")
        self.timeout = timeout
        self.records = {}
        self.errors = {}
        self._raw = {}
        self.checked_at = timestamp()
        self._previous = {}
        if self.snapshot and (self.snapshot / "manifest.json").is_file():
            manifest = json.loads((self.snapshot / "manifest.json").read_text(encoding="utf-8"))
            if manifest.get("generator") != "wf_wiki_dungeons":
                raise ValueError("快照目录属于其他工具")
            self._previous = manifest.get("files", {})
            if not self.gray_url:
                self.errors = dict(manifest.get("errors", {}))

    def _remote(self, logical):
        relative = quests.hashed_rel(logical)
        request = Request(self.gray_url + "/" + relative, headers={"User-Agent": "WF-Wiki-Dungeon-Snapshot/1"})
        limit = MAX_TABLE_BYTES if logical.endswith(".orderedmap") else MAX_IMAGE_BYTES
        with build_opener(NoRedirect()).open(request, timeout=self.timeout) as response:
            raw = read_bounded(response, limit)
        if logical.endswith(".orderedmap") and not isinstance(quests.parse_node(raw), dict):
            raise ValueError("远端元表不是 orderedmap")
        if logical.endswith(".png") and not wf_assets.png_decode(raw).startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("远端图片不是 PNG")
        target = self.snapshot / "store" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        return raw, {"origin": "gray", "sha256": checksum(raw), "bytes": len(raw), "checkedAt": self.checked_at}

    def _cached(self, logical):
        entry = self._previous.get(logical)
        if not isinstance(entry, dict) or entry.get("origin") not in ("gray", "gray-snapshot"):
            return None
        path = self.snapshot / "store" / quests.hashed_rel(logical)
        limit = MAX_TABLE_BYTES if logical.endswith(".orderedmap") else MAX_IMAGE_BYTES
        if not path.is_file() or path.stat().st_size > limit:
            return None
        raw = path.read_bytes()
        if checksum(raw) != entry.get("sha256"):
            raise ValueError("灰服快照哈希不符，请重新采集")
        return raw, {**entry, "origin": "gray-snapshot"}

    def _load(self, logical):
        checked_logical(logical)
        error = None
        if self.gray_url:
            try:
                return logical, *self._remote(logical), None
            except (OSError, URLError, HTTPError, ValueError) as exc:
                error = f"{type(exc).__name__}: {exc}"
                # A failed refresh cannot silently present an old gray file as current.
        elif self.snapshot:
            cached = self._cached(logical)
            if cached:
                return logical, *cached, None
        found = wf_assets.locate(self.store, logical)
        if found:
            limit = MAX_TABLE_BYTES if logical.endswith(".orderedmap") else MAX_IMAGE_BYTES
            if found[1].stat().st_size > limit:
                raise ValueError("本地资源超过大小上限")
            raw = found[1].read_bytes()
            return logical, raw, {"origin": "local-fallback" if self.gray_url or self.snapshot else "local",
                                  "sha256": checksum(raw), "bytes": len(raw), "checkedAt": self.checked_at}, error
        return logical, None, {"origin": "missing", "checkedAt": self.checked_at}, error or "资源不可用"

    def prefetch(self, logicals):
        todo = sorted(set(checked_logical(x) for x in logicals) - self._raw.keys())
        with ThreadPoolExecutor(max_workers=4) as pool:
            for logical, raw, record, error in pool.map(self._load, todo):
                self._raw[logical] = raw
                self.records[logical] = record
                if error:
                    self.errors[logical] = error

    def raw(self, logical):
        self.prefetch([logical])
        return self._raw[logical]

    def table(self, logical):
        raw = self.raw(logical)
        if raw is None:
            return {}
        tree = quests.parse_node(raw)
        if not isinstance(tree, dict):
            raise ValueError("副本元表不是 orderedmap")
        return tree

    def source(self, logicals):
        records = [self.records[x] for x in set(logicals) if x in self.records]
        origins = {r["origin"] for r in records}
        gray = bool(origins & {"gray", "gray-snapshot"})
        local = bool(origins & {"local", "local-fallback"})
        if gray and local:
            status, label = "mixed-snapshot", "灰服资源快照，部分资料由本地补齐；开放状态未核验"
        elif gray:
            status, label = "gray-snapshot", "灰服资源快照；开放状态未核验"
        else:
            status, label = "local-snapshot", "本地资源快照；未核验灰服开放状态"
        dates = [r["checkedAt"] for r in records if r.get("checkedAt")]
        return {"label": label, "status": status, "checkedAt": min(dates) if dates else self.checked_at}

    def verify_local_unchanged(self):
        for logical, record in self.records.items():
            if record["origin"] not in ("local", "local-fallback"):
                continue
            found = wf_assets.locate(self.store, logical)
            if not found or checksum(found[1].read_bytes()) != record["sha256"]:
                raise RuntimeError("导出时本地回退资源发生变化，请重新生成")

    def write_manifest(self):
        if self.snapshot:
            self.snapshot.mkdir(parents=True, exist_ok=True)
            data = {"generator": "wf_wiki_dungeons", "checkedAt": self.checked_at,
                    "files": self.records, "errors": self.errors}
            (self.snapshot / "manifest.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
