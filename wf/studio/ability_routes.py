"""Thin HTTP routes for draft ability operations; the core is shared with CLI."""
from __future__ import annotations

import re

from .drafts import DraftError


def _value(query, key, default=None):
    return (query.get(key) or [default])[0]


class AbilityRoutes:
    def __init__(self, app, server_dir=None):
        import threading
        self.app, self.server_dir = app, server_dir
        self._editor = None
        self._lock = threading.Lock()

    def editor(self):
        """One AbilityEditor per app: its memo (replayed draft state, panel text, key index) is per process."""
        with self._lock:
            if self._editor is None:
                from .draft_commands import editor
                self._editor = editor(self.app.source, self.app.ops.store, self.server_dir)
            return self._editor

    def read(self, query, cid):
        from .server import json_response
        return json_response(self.editor().read(cid))

    def apply(self, query, body, cid):
        from .server import json_response
        return json_response(self.editor().apply(cid, body))

    def check(self, query, body, cid):
        """Dry-run an abilityRequest against the current draft; never writes."""
        from .server import json_response
        return json_response(self.editor().preview(cid, body))

    def preview(self, query, cid):
        from .server import json_response
        key = _value(query, "key")
        if not key:
            raise DraftError("预览需要 key")
        try:
            row = int(_value(query, "row", "0"))
        except ValueError:
            raise DraftError("row 必须是从 0 起的行号") from None
        return json_response(self.editor().row_preview(cid, _value(query, "table", "ability"), key,
                                                       row=row, level=_value(query, "level")))

    def templates(self, query):
        from .server import json_response
        try:
            kind = int(_value(query, "kind")) if _value(query, "kind") is not None else None
        except ValueError:
            raise DraftError("kind 必须是整数") from None
        return json_response(self.editor().templates(table=_value(query, "table", "ability"),
                                                     block=_value(query, "block", "instant_content"), kind=kind))

    def text(self, query, cid):
        from .server import json_response
        return json_response(self.editor().text_panel(cid))

    def text_lint(self, query, body, cid):
        """Project proposed text values onto the draft and run wf text rules; never writes."""
        from .server import json_response
        text = body.get("text") if isinstance(body, dict) else None
        if text is not None and not isinstance(text, dict):
            raise DraftError("text 必须是对象")
        return json_response(self.editor().text_panel(cid, text=text or None, light=True))

    def keys(self, query):
        from .server import json_response
        try:
            limit = max(1, min(100, int(_value(query, "limit", "40"))))
        except ValueError:
            raise DraftError("limit 必须是整数") from None
        names = {c["id"]: c["name"] for c in self.app.character_list()}
        return json_response(self.editor().key_search(_value(query, "table", "ability"), _value(query, "q", ""),
                                                      cid=_value(query, "cid"), limit=limit, names=names))

    def routes(self):
        return [("GET", re.compile(r"^/api/characters/(?P<cid>\d+)/ability$"), self.read),
                ("GET", re.compile(r"^/api/drafts/(?P<cid>\d+)/ability/preview$"), self.preview),
                ("GET", re.compile(r"^/api/studio/ability/templates$"), self.templates),
                ("GET", re.compile(r"^/api/studio/ability/keys$"), self.keys),
                ("GET", re.compile(r"^/api/characters/(?P<cid>\d+)/text$"), self.text),
                ("POST", re.compile(r"^/api/drafts/(?P<cid>\d+)/text/lint$"), self.text_lint),
                ("POST", re.compile(r"^/api/drafts/(?P<cid>\d+)/ability/check$"), self.check),
                ("POST", re.compile(r"^/api/drafts/(?P<cid>\d+)/ability$"), self.apply)]
