"""Loopback-only, read-only web preview for local 2D animation sources."""

from __future__ import annotations

import argparse
from functools import partial
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit
import webbrowser

from wf_preview_2d_core import PreviewBundle, PreviewError, load_preview


_HTML_PATH = Path(__file__).with_name("wf_preview_2d.html")


class _PreviewServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False


class PreviewHandler(BaseHTTPRequestHandler):
    server_version = "WFPreview2D/1"

    def __init__(self, *args, bundle: PreviewBundle, html: bytes, **kwargs):
        self._bundle = bundle
        self._html = html
        self._manifest = json.dumps(
            bundle.manifest, ensure_ascii=False, separators=(",", ":"), sort_keys=True,
        ).encode("utf-8")
        super().__init__(*args, **kwargs)

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
            "default-src 'self'; img-src 'self' data:; "
            "style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; "
            "connect-src 'self'; object-src 'none'; frame-ancestors 'none'",
        )
        self.end_headers()

    def _reply(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
        self._headers(status, content_type, len(body))
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        parsed = urlsplit(self.path)
        if parsed.query or parsed.fragment:
            self._reply(HTTPStatus.NOT_FOUND, b"not found\n", "text/plain; charset=utf-8")
            return
        if parsed.path == "/":
            self._reply(HTTPStatus.OK, self._html, "text/html; charset=utf-8")
            return
        if parsed.path == "/manifest.json":
            self._reply(HTTPStatus.OK, self._manifest, "application/json; charset=utf-8")
            return
        if parsed.path.startswith("/asset/") and parsed.path.count("/") == 2:
            token = parsed.path.removeprefix("/asset/")
            try:
                body = self._bundle.read_asset(token)
            except PreviewError as error:
                status = HTTPStatus.NOT_FOUND if "unknown" in str(error) else HTTPStatus.CONFLICT
                self._reply(status, (str(error) + "\n").encode("utf-8"),
                            "text/plain; charset=utf-8")
                return
            self._reply(HTTPStatus.OK, body, "image/png")
            return
        self._reply(HTTPStatus.NOT_FOUND, b"not found\n", "text/plain; charset=utf-8")

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        self._reply(HTTPStatus.METHOD_NOT_ALLOWED, b"read-only preview\n",
                    "text/plain; charset=utf-8")

    def do_PUT(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        self.do_POST()

    def do_DELETE(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        self.do_POST()

    def do_PATCH(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        self.do_POST()


def build_server(bundle: PreviewBundle, *, port: int = 0) -> ThreadingHTTPServer:
    if isinstance(port, bool) or not isinstance(port, int) or not 0 <= port <= 65535:
        raise PreviewError("preview port must be an integer from 0 to 65535")
    try:
        html = _HTML_PATH.read_bytes()
    except OSError as error:
        raise PreviewError("preview HTML is unavailable") from error
    handler = partial(PreviewHandler, bundle=bundle, html=html)
    try:
        return _PreviewServer(("127.0.0.1", port), handler)
    except OSError as error:
        raise PreviewError("preview loopback port cannot be opened") from error


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only local preview for PNG sequences and WF pixel-art timelines.",
    )
    parser.add_argument("source", help="explicit local sequence directory or character package")
    parser.add_argument("--variant", choices=("auto", "normal", "special"), default="auto")
    parser.add_argument("--port", type=int, default=0, help="loopback port; 0 chooses a free port")
    parser.add_argument("--describe", action="store_true", help="print manifest and do not listen")
    parser.add_argument("--open", action="store_true", help="open the loopback page in a browser")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        bundle = load_preview(args.source, variant=args.variant)
        if args.describe:
            print(json.dumps(bundle.manifest, ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        server = build_server(bundle, port=args.port)
    except PreviewError as error:
        print(f"[ERR] {error}", file=sys.stderr)
        return 2
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"[READ-ONLY] 2D preview: {url}")
    print(bundle.manifest["renderingNote"])
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[STOP] preview closed")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
