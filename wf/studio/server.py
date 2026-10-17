"""Stdlib HTTP server: explicit route table + static frontend. Read-only."""
from __future__ import annotations

import json
import mimetypes
import re
import threading
import traceback
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, unquote, urlparse

import wf_describe

from .characters import BOARD_RULE, character_detail, list_characters
from .patches import patch_chain, patch_members
from .pixels import SLOTS, PixelCache
from .source import StudioSource

REPOSITORY = Path(__file__).resolve().parents[2]
DEFAULT_STATIC = REPOSITORY / "studio" / "dist"


@dataclass
class Response:
    status: int
    body: bytes
    content_type: str = "application/json; charset=utf-8"


def json_response(value, status: int = 200) -> Response:
    return Response(status, json.dumps(value, ensure_ascii=False).encode("utf-8"))


def error(status: int, message: str) -> Response:
    return json_response({"error": message}, status)


class StudioApp:
    """Request handlers bound to one :class:`StudioSource`."""

    def __init__(self, source: StudioSource):
        self.source = source
        self.pixels = PixelCache(source)
        self._lock = threading.Lock()
        self._characters: list[dict] | None = None
        self._lookup: list[dict] | None = None
        self.routes: list[tuple[str, re.Pattern, Callable[..., Response]]] = [
            ("GET", re.compile(r"^/api/health$"), self.health),
            ("GET", re.compile(r"^/api/meta$"), self.meta),
            ("GET", re.compile(r"^/api/characters$"), self.characters),
            ("GET", re.compile(r"^/api/characters/(?P<cid>\d+)$"), self.character),
            ("GET", re.compile(r"^/api/characters/(?P<cid>\d+)/pixels$"), self.pixel_meta),
            ("GET", re.compile(r"^/api/characters/(?P<cid>\d+)/pixels/(?P<family>pixelart|special)\.png$"),
             self.pixel_sheet),
            ("GET", re.compile(r"^/api/lookup$"), self.lookup),
            ("GET", re.compile(r"^/api/patches$"), self.patches),
            ("GET", re.compile(r"^/api/patches/(?P<archive>[^/]+\.zip)/members$"), self.patch_files),
        ]

    # -- dispatch -------------------------------------------------------
    def dispatch(self, method: str, path: str, query: dict[str, list[str]]) -> Response | None:
        for verb, pattern, handler in self.routes:
            match = pattern.match(path)
            if match:
                if verb != method:
                    return error(405, "只读接口，仅支持 GET")
                return handler(query=query, **{k: unquote(v) for k, v in match.groupdict().items()})
        return None

    # -- cached lists ---------------------------------------------------
    def character_list(self) -> list[dict]:
        with self._lock:
            if self._characters is None:
                self._characters = list_characters(self.source)
            return self._characters

    def lookup_index(self) -> list[dict]:
        with self._lock:
            if self._lookup is not None:
                return self._lookup
        names = {c["id"]: c for c in self.character_list()}
        ability, leader = self.source.table("ability"), self.source.table("leader")
        index = []
        for cid, rows in self.source.table("character").items():
            if not rows or not rows[0] or cid not in names:
                continue
            row = rows[0]
            groups = [(f"能力 {i + 1}", "ability", key, ability.get(key, [])) for i, key in enumerate(row[19:25])]
            groups.append(("队长技", "leader_ability", row[17] if len(row) > 17 else "", leader.get(row[17], []) if len(row) > 17 else []))
            for label, kind, key, data in groups:
                for number, line in enumerate(wf_describe.describe_rows(data, kind), 1):
                    if line:
                        index.append({"characterId": cid, "characterName": names[cid]["name"],
                                      "characterTitle": names[cid]["title"], "slot": label, "key": key,
                                      "row": number, "table": kind, "description": line})
        with self._lock:
            self._lookup = index
        return index

    # -- handlers -------------------------------------------------------
    def health(self, query) -> Response:
        return json_response({"ok": True})

    def meta(self, query) -> Response:
        return json_response({"source": self.source.describe(), "boardRule": BOARD_RULE,
                              "slots": [{"name": n, "label": l} for n, l in SLOTS],
                              "mode": "只读", "writes": False})

    def characters(self, query) -> Response:
        items = self.character_list()
        text = (query.get("q") or [""])[0].strip().lower()
        if text:
            items = [c for c in items if text in c["id"] or text in c["name"].lower()
                     or text in (c["title"] or "").lower() or text in c["code"].lower()]
        return json_response({"version": self.source.version, "count": len(items), "characters": items})

    def character(self, query, cid: str) -> Response:
        detail = character_detail(self.source, cid)
        return json_response(detail) if detail else error(404, f"角色 {cid} 不存在于当前视图")

    def _code(self, cid: str) -> str | None:
        rows = self.source.table("character").get(cid)
        return rows[0][0] if rows and rows[0] else None

    def pixel_meta(self, query, cid: str) -> Response:
        code = self._code(cid)
        if not code:
            return error(404, f"角色 {cid} 不存在于当前视图")
        return json_response({"characterId": cid, **self.pixels.meta(code)})

    def pixel_sheet(self, query, cid: str, family: str) -> Response:
        code = self._code(cid)
        png = self.pixels.sheet(code, family) if code else None
        if png is None:
            return error(404, "该角色没有这一组像素资源")
        return Response(200, png, "image/png")

    def lookup(self, query) -> Response:
        text = (query.get("q") or [""])[0].strip()
        try:
            limit = max(1, min(200, int((query.get("limit") or ["60"])[0])))
        except ValueError:
            limit = 60
        index = self.lookup_index()
        if not text:
            return json_response({"total": len(index), "count": 0, "results": [],
                                  "note": "输入关键词，按中文描述、角色名或词条键检索。"})
        terms = text.lower().split()
        hits = [item for item in index
                if all(t in item["description"].lower() or t in item["characterName"].lower()
                       or t == item["key"] or t == item["characterId"] for t in terms)]
        return json_response({"total": len(index), "count": len(hits), "results": hits[:limit],
                              "note": "描述为 wf_describe 语义翻译，不是客户端原文。"})

    def patches(self, query) -> Response:
        return json_response(patch_chain(self.source))

    def patch_files(self, query, archive: str) -> Response:
        result = patch_members(self.source, archive)
        return json_response(result) if result else error(404, "当前视图中没有这个补丁 ZIP")


def make_handler(app: StudioApp, static_root: Path):
    static_root = static_root.resolve()

    class Handler(BaseHTTPRequestHandler):
        server_version = "WFStudio/0.1"

        def log_message(self, format, *args):  # noqa: A002 - keep console quiet
            pass

        def _send(self, response: Response, head: bool = False):
            self.send_response(response.status)
            self.send_header("Content-Type", response.content_type)
            self.send_header("Content-Length", str(len(response.body)))
            self.send_header("Cache-Control", "no-store" if response.content_type.startswith("application/json") else "max-age=60")
            self.end_headers()
            if not head:
                self.wfile.write(response.body)

        def _static(self, path: str) -> Response:
            relative = path.lstrip("/") or "index.html"
            target = (static_root / relative).resolve()
            if not target.is_relative_to(static_root) or not target.is_file():
                target = static_root / "index.html"  # SPA fallback
            if not target.is_file():
                return Response(503, "前端尚未构建：请在 studio/ 下运行 npm run build".encode("utf-8"),
                                "text/plain; charset=utf-8")
            kind = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            if kind.startswith("text/") or kind in ("application/javascript",):
                kind += "; charset=utf-8"
            return Response(200, target.read_bytes(), kind)

        def _handle(self, method: str):
            parsed = urlparse(self.path)
            try:
                if parsed.path.startswith("/api/"):
                    response = app.dispatch(method if method != "HEAD" else "GET", parsed.path,
                                            parse_qs(parsed.query)) or error(404, "未知接口")
                elif method in ("GET", "HEAD"):
                    response = self._static(parsed.path)
                else:
                    response = error(405, "只读服务")
            except Exception as exc:  # noqa: BLE001 - report instead of dropping the connection
                traceback.print_exc()
                response = error(500, f"{type(exc).__name__}: {exc}")
            self._send(response, head=method == "HEAD")

        def do_GET(self):
            self._handle("GET")

        def do_HEAD(self):
            self._handle("HEAD")

        def do_POST(self):
            self._handle("POST")

        def do_PUT(self):
            self._handle("PUT")

        def do_DELETE(self):
            self._handle("DELETE")

    return Handler


def serve(app: StudioApp, *, host: str = "127.0.0.1", port: int = 8790, static_root: Path = DEFAULT_STATIC):
    server = ThreadingHTTPServer((host, port), make_handler(app, static_root))
    return server
