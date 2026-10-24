"""Global weapon workshop API; server.Handler guards every mutation."""
import re
from types import SimpleNamespace

from .deliver_routes import DELIVERIES, DeliverRoutes
from .drafts import DraftError, status
from .weapon_editor import WeaponEditor
from .weapon_store import WeaponDraftStore


PREFIX = "/api/studio/weapons"


class WeaponDeliveries(DeliverRoutes):
    kind = "weapon"

    def baseline_options(self):
        options = super().baseline_options()
        view = self.app.source.view
        if hasattr(view, "verify") and hasattr(view, "manifest"):
            options.update(baseline_view=view, base_store=view.store)
        return options

    def routes(self):
        return [(verb, re.compile(pattern.pattern.replace("/api/drafts/", PREFIX + "/drafts/")
                                 .replace("/api/deliveries", PREFIX + "/deliveries")), handler)
                for verb, pattern, handler in super().routes()]


class WeaponRoutes:
    def __init__(self, app, server_dir=None, default_provides=None):
        self.app, self.server_dir = app, server_dir
        self.store = WeaponDraftStore(app.ops.store.root / "weapons")
        # Both authoring surfaces reserve the same IDs under the same process lock.
        self.store._lock = app.boss.store._lock
        self.editor = WeaponEditor(app.source, store=self.store, server_dir=server_dir)
        proxy = SimpleNamespace(source=app.source, ops=SimpleNamespace(store=self.store),
                                screenshots=getattr(app, "screenshots", None))
        self.deliveries = WeaponDeliveries(proxy, server_dir, root=DELIVERIES / "weapons",
                                          default_provides=default_provides)

    @staticmethod
    def _json(build):
        from .server import json_response
        try:
            return json_response(build())
        except (ValueError, KeyError, OSError, TypeError) as exc:
            raise DraftError(str(exc)) from exc

    def listing(self, query):
        from .weapon_catalog import listing
        return self._json(lambda: listing(self.app.source, query, server_dir=self.server_dir))

    def detail(self, query, wid):
        from .weapon_catalog import detail
        from .source import StudioSource
        from .server import error
        def read():
            state, draft = self.editor.state(wid)
            source = StudioSource(state, official_root=getattr(self.app.source, "official_root", None)) if draft else self.app.source
            document = detail(source, wid, server_dir=self.server_dir)
            if document is None:
                return None
            return {**document, "base_status": document.get("status", []), "weaponId": wid,
                    "subjectKind": "weapon", "changeset": draft, "status": status(draft),
                    "checks": getattr(state, "weapon_checks", []), "runtime": "未执行"}
        response = self._json(read)
        return error(404, "当前视图和武器草稿中没有这个武器") if response.body == b"null" else response

    def clone(self, query, body):
        return self._json(lambda: self.editor.apply("weapon_clone", body,
                         preview=(query.get("preview") or ["false"])[0] == "true"))

    def materials(self, query, body, wid):
        if "id" in body and body["id"] != wid:
            raise DraftError("请求中的武器 ID 与路径不一致")
        return self._json(lambda: self.editor.apply("weapon_materials", {**body, "id": wid}, wid=wid,
                         preview=(query.get("preview") or ["false"])[0] == "true"))

    def drafts(self, query):
        return self._json(lambda: {"drafts": self.store.characters(), "subjectKind": "weapon"})

    def draft(self, query, wid):
        from .operations import ACTIONS
        def read():
            draft = self.store.load(wid)
            return {"characterId": wid, "weaponId": wid, "subjectKind": "weapon",
                    "changeset": draft, "status": status(draft), "actions": ACTIONS}
        return self._json(read)

    def save(self, query, body, wid):
        return self._json(lambda: {"status": status(self.store.save(wid))})

    def revert(self, query, body, wid, change):
        return self._json(lambda: {"status": status(self.store.revert(wid, change))})

    def routes(self):
        routes = [("GET", "", self.listing), ("POST", "/clone", self.clone),
                  ("GET", "/drafts", self.drafts), ("GET", r"/drafts/(?P<wid>\d+)", self.draft),
                  ("POST", r"/drafts/(?P<wid>\d+)/save", self.save),
                  ("POST", r"/drafts/(?P<wid>\d+)/changes/(?P<change>c-[0-9a-f]{12})/revert", self.revert),
                  ("GET", r"/(?P<wid>\d+)", self.detail),
                  ("POST", r"/(?P<wid>\d+)/materials", self.materials)]
        return [(verb, re.compile("^" + PREFIX + path + "$"), handler) for verb, path, handler in routes] + self.deliveries.routes()
