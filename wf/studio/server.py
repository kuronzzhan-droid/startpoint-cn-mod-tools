"""Stdlib HTTP server: explicit route table + static frontend.

GET routes read the layered view. POST routes only write the draft workspace
(``work/studio-drafts``) and are guarded by :class:`~wf.studio.guard.WriteGuard`.
"""
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

from .assets import AssetIndex
from .characters import BOARD_RULE, character_detail, list_characters
from .drafts import DraftError
from .guard import GuardError, WriteGuard
from .operations import DraftOps
from .patches import patch_chain, patch_members
from .pixels import SLOTS, PixelCache
from .source import StudioSource

REPOSITORY = Path(__file__).resolve().parents[2]
DEFAULT_STATIC = REPOSITORY / "studio" / "dist"
ASSET_PREFIXES = ("character/", "battle/", "bgm/", "dynamic/")


@dataclass
class Response:
    status: int
    body: bytes
    content_type: str = "application/json; charset=utf-8"
    cache: str | None = None  # explicit Cache-Control (e.g. draft-state images change under one URL)


def json_response(value, status: int = 200) -> Response:
    return Response(status, json.dumps(value, ensure_ascii=False).encode("utf-8"))


def error(status: int, message: str) -> Response:
    return json_response({"error": message}, status)


class StudioApp:
    """Request handlers bound to one :class:`StudioSource`."""

    def __init__(self, source: StudioSource, *, drafts=None, server_dir=None, default_provides=None,
                 screenshot_dirs=None):
        from .device_result import Screenshots, configured_screenshot_dirs
        self.source = source
        # 实测截图白名单：profile paths.studio_screenshots / WF_STUDIO_SCREENSHOTS / --screenshots-dir
        self.screenshots = Screenshots(configured_screenshot_dirs() if screenshot_dirs is None
                                       else screenshot_dirs)
        self.pixels = PixelCache(source)
        self.assets = AssetIndex(source)
        self.ops = DraftOps(source, store=drafts, assets=self.assets, characters=self.character_list)
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
            ("GET", re.compile(r"^/api/characters/(?P<cid>\d+)/assets$"), self.character_assets),
            ("GET", re.compile(r"^/api/characters/(?P<cid>\d+)/avatar/(?P<form>[01])\.png$"), self.avatar),
            ("GET", re.compile(r"^/api/asset$"), self.asset_file),
            ("GET", re.compile(r"^/api/lookup$"), self.lookup),
            ("GET", re.compile(r"^/api/patches$"), self.patches),
            ("GET", re.compile(r"^/api/patches/(?P<archive>[^/]+\.zip)/members$"), self.patch_files),
            # -- draft workspace (M3.2) --
            ("GET", re.compile(r"^/api/drafts$"), self.draft_index),
            ("GET", re.compile(r"^/api/drafts/(?P<cid>\d+|scratch-[a-z0-9][a-z0-9-]{0,47})$"), self.draft),
            ("GET", re.compile(r"^/api/drafts/(?P<cid>\d+|scratch-[a-z0-9][a-z0-9-]{0,47})/file$"), self.draft_file),
            ("GET", re.compile(r"^/api/characters/(?P<cid>\d+)/portrait/(?P<form>[01])$"), self.portrait_info),
            ("GET", re.compile(r"^/api/characters/(?P<cid>\d+)/voice$"), self.voice_lines),
            ("GET", re.compile(r"^/api/studio/masks/(?P<slot>[a-z0-9_]+)\.png$"), self.mask),
            ("GET", re.compile(r"^/api/studio/schema$"), self.schema),
            ("GET", re.compile(r"^/api/device-screenshots$"), self.device_screenshot),
            ("GET", re.compile(r"^/api/studio/device-result/schema$"), self.device_schema),
            ("POST", re.compile(r"^/api/drafts/(?P<cid>\d+)/portrait/(?P<form>[01])/source$"), self.portrait_upload),
            ("POST", re.compile(r"^/api/drafts/(?P<cid>\d+)/portrait$"), self.portrait_save),
            ("POST", re.compile(r"^/api/drafts/(?P<cid>\d+)/pixel$"), self.pixel_save),
            ("POST", re.compile(r"^/api/drafts/(?P<cid>\d+)/voice$"), self.voice_save),
            ("POST", re.compile(r"^/api/drafts/(?P<cid>\d+|scratch-[a-z0-9][a-z0-9-]{0,47})/changes/(?P<change>c-[0-9a-f]{12})/revert$"), self.revert),
            ("POST", re.compile(r"^/api/drafts/(?P<cid>\d+|scratch-[a-z0-9][a-z0-9-]{0,47})/save$"), self.save),
        ]
        from .ability_routes import AbilityRoutes
        from .capability_routes import routes as capability_routes
        self.routes.extend(capability_routes())
        from .client_profile_view import ClientProfileView
        self.client_profiles = ClientProfileView(self)
        self.routes.extend(self.client_profiles.routes())
        self.abilities = AbilityRoutes(self, server_dir)
        self.routes.extend(self.abilities.routes())
        from .pixel_routes import PixelRoutes
        self.pixel_workshop = PixelRoutes(self)
        self.routes.extend(self.pixel_workshop.routes())
        from .deliver_routes import DeliverRoutes
        self.deliveries = DeliverRoutes(self, server_dir, default_provides=default_provides)
        self.routes.extend(self.deliveries.routes())
        from .boss_routes import BossRoutes
        self.boss = BossRoutes(self, server_dir, default_provides)
        self.routes.extend(self.boss.routes())
        from .weapon_routes import WeaponRoutes
        self.weapons = WeaponRoutes(self, server_dir, default_provides)
        self.routes.extend(self.weapons.routes())
        from .discovery_commands import DiscoveryRoutes
        self.discovery = DiscoveryRoutes(self, server_dir)
        self.routes.extend(self.discovery.routes())
        from .character_routes import CharacterRoutes
        self.character_clones = CharacterRoutes(self, server_dir)
        self.routes.extend(self.character_clones.routes())
        from .pf_routes import PFActionsRoutes
        self.pf_actions = PFActionsRoutes(self)
        self.routes.extend(self.pf_actions.routes())
        from .view_routes import ViewRoutes
        self.views = ViewRoutes(self)
        self.routes.extend(self.views.routes())
        from .timeline_routes import TimelineRoutes
        self.timelines = TimelineRoutes(self)
        self.routes.extend(self.timelines.routes())
        from .craft_routes import CraftRoutes
        self.craft = CraftRoutes(self)
        self.routes.extend(self.craft.routes())

    # -- dispatch -------------------------------------------------------
    def dispatch(self, method: str, path: str, query: dict[str, list[str]], body=None) -> Response | None:
        matched = False
        for verb, pattern, handler in self.routes:
            match = pattern.match(path)
            if not match:
                continue
            matched = True
            if verb != method:
                continue
            groups = {k: unquote(v) for k, v in match.groupdict().items()}
            try:
                if verb == "POST":
                    return handler(query=query, body=body if isinstance(body, dict) else {}, **groups)
                return handler(query=query, **groups)
            except DraftError as exc:
                return error(400, str(exc))
        if matched:
            return error(405, "这个接口不支持 " + method)
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

    def prewarm(self) -> None:
        """Fill the per-process caches (registry, roster, parsed tables, key indexes, reference
        tokens) so the first 文案 / 换键 request does not pay for them. Safe to run in a thread."""
        from . import perf
        from .ability_engine import EditState
        perf.registry()
        self.client_profiles.prewarm()
        self.character_list()
        editor = self.abilities.editor()
        state = EditState(self.source)
        for logical in ("master/ability/ability.orderedmap", "master/ability/leader_ability.orderedmap"):
            for leaf in state.table(logical).values():
                if isinstance(leaf, str) and leaf:
                    perf.leaf_tokens(leaf)
        for table in ("ability", "leader_ability", "action_skill"):
            editor._key_index(table, None)

    # -- handlers -------------------------------------------------------
    def health(self, query) -> Response:
        return json_response({"ok": True})

    def meta(self, query) -> Response:
        return json_response({"source": self.source.describe(), "boardRule": BOARD_RULE,
                              "slots": [{"name": n, "label": l} for n, l in SLOTS],
                              "mode": "草稿可写", "writes": "draft-only"})

    def characters(self, query) -> Response:
        items = self.character_list()
        text = (query.get("q") or [""])[0].strip().lower()
        if text:
            items = [c for c in items if text in c["id"] or text in c["name"].lower()
                     or text in (c["title"] or "").lower() or text in c["code"].lower()]
        return json_response({"version": self.source.version, "count": len(items), "characters": items})

    def character(self, query, cid: str) -> Response:
        source, _, _ = self.character_context(cid)
        detail = character_detail(source, cid)
        return json_response(detail) if detail else error(404, f"角色 {cid} 不存在于当前视图")

    def character_context(self, cid):
        """Read a new clone through its candidate without changing the shared view."""
        if self.source.table("character").get(cid):
            return self.source, self.assets, self.pixels
        from .character_clone import ops_for
        ops = ops_for(self.ops, cid)
        if ops.source is self.source:
            return self.source, self.assets, self.pixels
        return ops.source, ops.assets, PixelCache(ops.source)

    def _code(self, cid: str, source=None) -> str | None:
        rows = (source or self.source).table("character").get(cid)
        return rows[0][0] if rows and rows[0] else None

    def pixel_meta(self, query, cid: str) -> Response:
        source, _, pixels = self.character_context(cid)
        code = self._code(cid, source)
        if not code:
            return error(404, f"角色 {cid} 不存在于当前视图")
        return json_response({"characterId": cid, **pixels.meta(code)})

    def pixel_sheet(self, query, cid: str, family: str) -> Response:
        source, _, pixels = self.character_context(cid)
        code = self._code(cid, source)
        png = pixels.sheet(code, family) if code else None
        if png is None:
            return error(404, "该角色没有这一组像素资源")
        return Response(200, png, "image/png")

    def character_assets(self, query, cid: str) -> Response:
        _, assets, _ = self.character_context(cid)
        result = assets.character(cid)
        if result is not None:
            from .character_clone import clone_change
            from .clone_assets import checklist
            draft = self.ops.store.load(cid)
            if clone_change(draft):
                result = {**result, "cloneAssets": checklist(draft)}
            from .asset_version import stamp_assets
            result = stamp_assets(result, source_version=self.source.version, draft=draft)
        return json_response(result) if result else error(404, f"角色 {cid} 不存在于当前视图")

    def avatar(self, query, cid: str, form: str) -> Response:
        _, assets, _ = self.character_context(cid)
        found = assets.avatar(cid, form)
        if found is None:
            return error(404, "没有头像资源")
        return Response(200, found[0], "image/png")

    def asset_file(self, query) -> Response:
        logical = (query.get("path") or [""])[0]
        if not logical.startswith(ASSET_PREFIXES) or ".." in logical.split("/"):
            return error(400, "只允许读取角色相关资源路径")
        found = self.assets.file(logical)
        if found is None:
            return error(404, "当前视图中没有这个资源")
        return Response(200, found[0], found[1])

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

    # -- drafts ----------------------------------------------------------
    def draft_index(self, query) -> Response:
        return json_response({"drafts": self.ops.store.characters()})

    def draft(self, query, cid: str) -> Response:
        return json_response(self.ops.draft(cid))

    def draft_file(self, query, cid: str) -> Response:
        relative = (query.get("path") or [""])[0]
        data = self.ops.store.read_file(cid, relative)
        if data is None:
            return error(404, "草稿里没有这个文件")
        kind = mimetypes.guess_type(relative)[0] or "application/octet-stream"
        return Response(200, data, kind)

    def portrait_info(self, query, cid: str, form: str) -> Response:
        return json_response(self.ops.portrait_info(cid, form))

    def voice_lines(self, query, cid: str) -> Response:
        return json_response(self.ops.voice_lines(cid))

    def mask(self, query, slot: str) -> Response:
        return Response(200, self.ops.mask_png(slot), "image/png")

    def schema(self, query) -> Response:
        from .drafts import schema
        return json_response(schema())

    def device_screenshot(self, query) -> Response:
        value = (query.get("path") or [""])[0]
        try:
            data, kind = self.screenshots.read(value)
        except PermissionError as exc:
            return error(403, str(exc))
        except FileNotFoundError as exc:
            return error(404, str(exc))
        return Response(200, data, kind, cache="no-store")

    def device_schema(self, query) -> Response:
        from .device_result import schema as device_schema
        return json_response({**device_schema(), "screenshotDirs": self.screenshots.public()})

    def portrait_upload(self, query, body, cid: str, form: str) -> Response:
        return json_response(self.ops.portrait_upload(cid, form, body.get("png", "")))

    def portrait_save(self, query, body, cid: str) -> Response:
        return json_response(self.ops.portrait_save(cid, body))

    def pixel_save(self, query, body, cid: str) -> Response:
        return json_response(self.ops.pixel_save(cid, body))

    def voice_save(self, query, body, cid: str) -> Response:
        return json_response(self.ops.voice_save(cid, body))

    def revert(self, query, body, cid: str, change: str) -> Response:
        return json_response(self.ops.revert(cid, change))

    def save(self, query, body, cid: str) -> Response:
        return json_response(self.ops.save(cid))

    def patches(self, query) -> Response:
        return json_response(patch_chain(self.source))

    def patch_files(self, query, archive: str) -> Response:
        result = patch_members(self.source, archive)
        return json_response(result) if result else error(404, "当前视图中没有这个补丁 ZIP")


def make_handler(app: StudioApp, static_root: Path, guard: WriteGuard):
    static_root = static_root.resolve()

    class Handler(BaseHTTPRequestHandler):
        server_version = "WFStudio/0.1"

        def log_message(self, format, *args):  # noqa: A002 - keep console quiet
            pass

        def _send(self, response: Response, head: bool = False):
            try:
                self.send_response(response.status)
                self.send_header("Content-Type", response.content_type)
                self.send_header("Content-Length", str(len(response.body)))
                self.send_header("Cache-Control", response.cache or (
                    "no-store" if response.content_type.startswith("application/json") else "max-age=600"))
                self.end_headers()
                if not head:
                    self.wfile.write(response.body)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                self.close_connection = True  # the browser navigated away; nothing to report

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
            body = target.read_bytes()
            if target.name == "index.html":
                body = guard.inject(body)
            return Response(200, body, kind)

        def _handle(self, method: str):
            parsed = urlparse(self.path)
            try:
                guard.check_host(self.headers)
                if parsed.path.startswith("/api/"):
                    body = None
                    if method == "POST":
                        guard.check(self.headers)
                        length = guard.body_length(self.headers)
                        raw = self.rfile.read(length)
                        if len(raw) != length:
                            raise GuardError(400, "studio_bad_body", "请求体长度不符")
                        body = guard.parse(raw)
                    elif method not in ("GET", "HEAD"):
                        raise GuardError(405, "studio_method", "不支持的方法")
                    response = app.dispatch(method if method != "HEAD" else "GET", parsed.path,
                                            parse_qs(parsed.query), body) or error(404, "未知接口")
                elif method in ("GET", "HEAD"):
                    response = self._static(parsed.path)
                else:
                    response = error(405, "静态资源只读")
            except GuardError as exc:
                response = json_response({"error": exc.message, "code": exc.code}, exc.status)
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


def serve(app: StudioApp, *, host: str = "127.0.0.1", port: int = 8790, static_root: Path = DEFAULT_STATIC,
          guard: WriteGuard | None = None, extra_origins=()):
    guard = guard or WriteGuard(port, extra_origins=extra_origins)
    server = ThreadingHTTPServer((host, port), make_handler(app, static_root, guard))
    server.guard = guard
    return server
