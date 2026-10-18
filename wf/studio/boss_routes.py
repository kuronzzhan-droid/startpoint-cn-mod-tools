"""Boss HTTP surface; the host/origin/token guard remains in server.Handler."""
from __future__ import annotations

import re
from types import SimpleNamespace

from .boss import BossEditor, BossDraftStore
from .deliver_routes import DeliverRoutes, DELIVERIES


class BossDeliveries(DeliverRoutes):
    def baseline_options(self):
        options = super().baseline_options()
        view = self.app.source.view
        if hasattr(view, "verify") and hasattr(view, "manifest"):
            options.update(baseline_view=view, base_store=view.store)
        return options

    def routes(self):
        return [(verb, re.compile(pattern.pattern.replace("/api/drafts/", "/api/boss/drafts/")
                                 .replace("/api/deliveries", "/api/boss/deliveries")), handler)
                for verb, pattern, handler in super().routes()]


class BossRoutes:
    def __init__(self, app, server_dir=None, default_provides=None):
        self.app = app
        self.store = BossDraftStore(app.ops.store.root / "boss")
        self.editor = BossEditor(app.source, store=self.store, server_dir=server_dir)
        proxy = SimpleNamespace(source=app.source, ops=SimpleNamespace(store=self.store))
        self.deliveries = BossDeliveries(proxy, server_dir, root=DELIVERIES / "boss",
                                        default_provides=default_provides)

    def listing(self, query):
        from wf.boss.reader import BossReader
        from .server import json_response
        from .drafts import DraftError
        try:
            return json_response(BossReader(self.app.source).list())
        except (ValueError, KeyError, OSError, TypeError) as exc:
            raise DraftError(str(exc)) from exc

    def show(self, query, quest):
        from .server import json_response
        return json_response(self.editor.read(quest))

    def drafts(self, query):
        from .server import json_response
        return json_response({"drafts": self.store.characters(), "subjectKind": "boss"})

    def edit(self, query, body, quest="new"):
        from .server import json_response
        preview = (query.get("preview") or ["false"])[0] == "true"
        result = self.editor.preview(quest, body) if preview else self.editor.apply(quest, body)
        return json_response(result, 200 if result.get("ok", True) else 400)

    def save(self, query, body, quest):
        from .drafts import status
        from .server import json_response
        return json_response({"status": status(self.store.save(quest))})

    def revert(self, query, body, quest, change):
        from .drafts import status
        from .server import json_response
        return json_response({"status": status(self.store.revert(quest, change))})

    def routes(self):
        return [
            ("GET", re.compile(r"^/api/boss$"), self.listing),
            ("GET", re.compile(r"^/api/boss/drafts$"), self.drafts),
            ("GET", re.compile(r"^/api/boss/(?P<quest>\d+)$"), self.show),
            ("POST", re.compile(r"^/api/boss/drafts$"), self.edit),
            ("POST", re.compile(r"^/api/boss/drafts/(?P<quest>\d+)$"), self.edit),
            ("POST", re.compile(r"^/api/boss/drafts/(?P<quest>\d+)/save$"), self.save),
            ("POST", re.compile(r"^/api/boss/drafts/(?P<quest>\d+)/changes/(?P<change>c-[0-9a-f]{12})/revert$"), self.revert),
            *self.deliveries.routes(),
        ]
