"""Write-request guard for the studio (same idea as the release UI token).

* a random per-process token, injected into the served ``index.html`` and
  written to ``work/studio-drafts/.session.json`` for local agents;
* ``Host`` must be the loopback address the server listens on (DNS rebinding);
* ``Origin`` (when a browser sends one) must be that same origin;
  ``Sec-Fetch-Site: cross-site`` is rejected outright;
* JSON bodies only, bounded size.
"""
from __future__ import annotations

import json
import secrets
from pathlib import Path

TOKEN_HEADER = "X-WF-Studio-Token"
MAX_BODY = 96 * 1024 * 1024
LOOPBACK_NAMES = ("127.0.0.1", "localhost", "[::1]")


class GuardError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


class WriteGuard:
    def __init__(self, port: int, *, token: str | None = None, extra_origins=()):
        self.port = port
        self.token = token or secrets.token_urlsafe(32)
        self.hosts = {f"{name}:{port}" for name in LOOPBACK_NAMES}
        self.origins = {f"http://{host}" for host in self.hosts} | set(extra_origins)

    def check(self, headers) -> None:
        host = (headers.get("Host") or "").strip().lower()
        if host not in self.hosts:
            raise GuardError(403, "studio_bad_host", f"拒绝：Host {host or '(空)'} 不是本机回环地址")
        origin = headers.get("Origin")
        if origin is not None and origin.lower() not in self.origins:
            raise GuardError(403, "studio_cross_origin", f"拒绝跨源写入：{origin}")
        if (headers.get("Sec-Fetch-Site") or "").lower() == "cross-site":
            raise GuardError(403, "studio_cross_origin", "拒绝跨站写入")
        supplied = headers.get(TOKEN_HEADER) or ""
        if not secrets.compare_digest(supplied, self.token):
            raise GuardError(403, "studio_bad_token", "会话令牌无效（刷新页面或读取 work/studio-drafts/.session.json）")
        kind = (headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if kind != "application/json":
            raise GuardError(415, "studio_bad_type", "写入请求必须是 application/json")
        if headers.get("Transfer-Encoding") is not None:
            raise GuardError(400, "studio_bad_body", "不支持分块请求体")

    @staticmethod
    def body_length(headers) -> int:
        try:
            length = int(headers.get("Content-Length", ""))
        except ValueError:
            raise GuardError(411, "studio_bad_body", "缺少 Content-Length") from None
        if not 0 <= length <= MAX_BODY:
            raise GuardError(413, "studio_too_large", f"请求体超过 {MAX_BODY // 1024 // 1024} MB 上限")
        return length

    @staticmethod
    def parse(raw: bytes):
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeError, ValueError):
            raise GuardError(400, "studio_bad_body", "请求体不是 UTF-8 JSON") from None

    def inject(self, html: bytes) -> bytes:
        meta = f'<meta name="wf-studio-token" content="{self.token}">'.encode("ascii")
        return html.replace(b"</head>", meta + b"</head>", 1)

    def write_session(self, directory: Path, host: str) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / ".session.json"
        path.write_text(json.dumps({"url": f"http://{host}:{self.port}", "header": TOKEN_HEADER,
                                    "token": self.token}, ensure_ascii=False), "utf-8")
        return path
