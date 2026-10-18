"""Thin HTTP routes for draft ability operations; the core is shared with CLI."""
from __future__ import annotations

import re

from .drafts import DraftError


def _value(query, key, default=None):
    return (query.get(key) or [default])[0]


class AbilityRoutes:
    def __init__(self, app, server_dir=None):
        self.app, self.server_dir = app, server_dir

    def editor(self):
        from .draft_commands import editor
        return editor(self.app.source, self.app.ops.store, self.server_dir)

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

    def routes(self):
        return [("GET", re.compile(r"^/api/characters/(?P<cid>\d+)/ability$"), self.read),
                ("GET", re.compile(r"^/api/drafts/(?P<cid>\d+)/ability/preview$"), self.preview),
                ("GET", re.compile(r"^/api/studio/ability/templates$"), self.templates),
                ("POST", re.compile(r"^/api/drafts/(?P<cid>\d+)/ability/check$"), self.check),
                ("POST", re.compile(r"^/api/drafts/(?P<cid>\d+)/ability$"), self.apply)]
