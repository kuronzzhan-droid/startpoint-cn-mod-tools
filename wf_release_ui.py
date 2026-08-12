"""Loopback-only preparation UI for the independent wf-release-v1 workflow."""

from __future__ import annotations

import argparse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import threading
from urllib.parse import unquote, urlsplit
import webbrowser

from wf_preview_2d_core import PreviewBundle, PreviewError
from wf_release_ui_actions import UIActionError, run_action
from wf_release_v1.canonical import canonical_json_bytes
from wf_release_v1.errors import ReleaseError


_MAX_REQUEST_BYTES = 64 * 1024
_UI_PATH = Path(__file__).with_name("wf_release_ui.html")
_PREVIEW_PATH = Path(__file__).with_name("wf_preview_2d.html")


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


class ReleaseUIState:
    def __init__(self, ui_html: bytes, preview_html: bytes) -> None:
        self.token = secrets.token_urlsafe(32)
        self.ui_html = ui_html.replace(b"__WF_RELEASE_UI_TOKEN__", self.token.encode("ascii"))
        self.preview_html = preview_html
        self.preview: PreviewBundle | None = None
        self.lock = threading.Lock()

    def action(self, name: str, value: object) -> dict[str, object]:
        with self.lock:
            result = run_action(name, value)
            if result.preview is not None:
                self.preview = result.preview
            return result.wire


class _ReleaseUIServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False
    ui_state: ReleaseUIState


class ReleaseUIHandler(BaseHTTPRequestHandler):
    server_version = "WFReleaseUI/1"

    @property
    def _state(self) -> ReleaseUIState:
        return self.server.ui_state  # type: ignore[attr-defined]

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def _headers(self, status: HTTPStatus, content_type: str, length: int) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline'; connect-src 'self'; object-src 'none'; "
            "frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
        )
        self.end_headers()

    def _reply(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
        self._headers(status, content_type, len(body))
        self.wfile.write(body)

    def _json(self, status: HTTPStatus, value: dict[str, object]) -> None:
        self._reply(status, canonical_json_bytes(value), "application/json; charset=utf-8")

    def _path(self) -> str | None:
        parsed = urlsplit(self.path)
        return parsed.path if not parsed.query and not parsed.fragment else None

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        path = self._path()
        if path == "/":
            self._reply(HTTPStatus.OK, self._state.ui_html, "text/html; charset=utf-8")
            return
        preview = self._state.preview
        if path == "/preview/":
            if preview is None:
                self._reply(HTTPStatus.NOT_FOUND, b"preview not loaded\n", "text/plain")
            else:
                self._reply(
                    HTTPStatus.OK, self._state.preview_html, "text/html; charset=utf-8"
                )
            return
        if path == "/preview/manifest.json" and preview is not None:
            self._json(HTTPStatus.OK, preview.manifest)
            return
        if path is not None and path.startswith("/preview/asset/") and preview is not None:
            token = unquote(path.removeprefix("/preview/asset/"))
            if not token or "/" in token or "\\" in token:
                self._reply(HTTPStatus.NOT_FOUND, b"not found\n", "text/plain")
                return
            try:
                body = preview.read_asset(token)
            except PreviewError:
                self._reply(HTTPStatus.CONFLICT, b"preview asset unavailable\n", "text/plain")
                return
            self._reply(HTTPStatus.OK, body, "image/png")
            return
        self._reply(HTTPStatus.NOT_FOUND, b"not found\n", "text/plain")

    def _request_json(self) -> object:
        if self.headers.get("Content-Type") != "application/json":
            raise UIActionError("请求必须使用 application/json")
        if self.headers.get("Transfer-Encoding") is not None:
            raise UIActionError("不支持流式请求体")
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            raise UIActionError("请求长度无效") from None
        if not 0 <= length <= _MAX_REQUEST_BYTES:
            raise UIActionError("请求超过大小上限")
        raw = self.rfile.read(length)
        if len(raw) != length:
            raise UIActionError("请求长度发生变化")
        try:
            return json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs)
        except (UnicodeError, json.JSONDecodeError, ValueError):
            raise UIActionError("请求不是严格 UTF-8 JSON") from None

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        path = self._path()
        if path is None or not path.startswith("/api/action/"):
            self._reply(HTTPStatus.NOT_FOUND, b"not found\n", "text/plain")
            return
        supplied = self.headers.get("X-WF-Release-UI-Token", "")
        if not secrets.compare_digest(supplied, self._state.token):
            self._json(
                HTTPStatus.FORBIDDEN,
                {"code": "WFREL_UI_FORBIDDEN", "message": "会话令牌无效", "ok": False},
            )
            return
        name = unquote(path.removeprefix("/api/action/"))
        try:
            request = self._request_json()
            result = self._state.action(name, request)
        except UIActionError as error:
            self._json(
                HTTPStatus.BAD_REQUEST,
                {"code": "WFREL_UI_REQUEST", "message": str(error), "ok": False},
            )
            return
        except PreviewError as error:
            self._json(
                HTTPStatus.CONFLICT,
                {"code": "WFREL_PREVIEW_INVALID", "message": str(error), "ok": False},
            )
            return
        except ReleaseError as error:
            self._json(
                HTTPStatus.CONFLICT,
                {"code": error.code, "message": error.message, "ok": False},
            )
            return
        except Exception:
            self._json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"code": "WFREL_UI_INTERNAL", "message": "本地操作失败", "ok": False},
            )
            return
        self._json(HTTPStatus.OK, {"action": name, "ok": True, "result": result})

    def _readonly(self) -> None:
        self._reply(
            HTTPStatus.METHOD_NOT_ALLOWED,
            b"unsupported method\n",
            "text/plain; charset=utf-8",
        )

    do_PUT = _readonly
    do_DELETE = _readonly
    do_PATCH = _readonly


def build_server(*, port: int = 0) -> _ReleaseUIServer:
    if isinstance(port, bool) or not isinstance(port, int) or not 0 <= port <= 65535:
        raise UIActionError("端口必须是 0 到 65535 的整数")
    try:
        ui_html = _UI_PATH.read_bytes()
        preview_html = _PREVIEW_PATH.read_bytes()
    except OSError as error:
        raise UIActionError("工作台页面不可用") from error
    server = _ReleaseUIServer(("127.0.0.1", port), ReleaseUIHandler)
    server.ui_state = ReleaseUIState(ui_html, preview_html)
    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="WF 独立发行工作台（不提供 live 安装）")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--open", action="store_true")
    args = parser.parse_args(argv)
    try:
        server = build_server(port=args.port)
    except UIActionError as error:
        print(f"[ERR] {error}")
        return 2
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"[PREPARATION-ONLY] {url}")
    print("不提供安装、回滚或发布按钮；Ctrl+C 关闭。")
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[STOP] 工作台已关闭")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
