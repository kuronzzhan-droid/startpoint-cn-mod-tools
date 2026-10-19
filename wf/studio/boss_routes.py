"""Boss HTTP surface; the host/origin/token guard remains in server.Handler."""
from __future__ import annotations

import re
from types import SimpleNamespace

from wf.boss.identity import safe_id

from .boss import BossEditor, BossDraftStore
from .boss_catalog import (draft_summary, enrich_listing, options, template_sources, terrain_preview,
                           weapon_icons)
from .deliver_routes import DeliverRoutes, DELIVERIES


ICON_PATH = re.compile(r"^item/[A-Za-z0-9_./-]+$")


class BossDeliveries(DeliverRoutes):
    name_pattern = re.compile(r"^(?:[0-9]{1,9}|(?:boss_battle|hard_multi|practice)_[0-9_]+)-[0-9.]+-to-[0-9.]+-[0-9]{8}-[0-9]{6}$")

    def output_identity(self, cid):
        self.app.ops.store.directory(cid)
        return safe_id(cid)

    def baseline_options(self):
        options = super().baseline_options()
        view = self.app.source.view
        if hasattr(view, "verify") and hasattr(view, "manifest"):
            options.update(baseline_view=view, base_store=view.store)
        return options

    def routes(self):
        return [(verb, re.compile(pattern.pattern.replace("/api/drafts/", "/api/boss/drafts/")
                                 .replace("/api/deliveries", "/api/boss/deliveries")
                                 .replace(r"(?P<cid>\d+)", r"(?P<cid>[^/]+)")), handler)
                for verb, pattern, handler in super().routes()]


class BossRoutes:
    def __init__(self, app, server_dir=None, default_provides=None):
        self.app = app
        self.store = BossDraftStore(app.ops.store.root / "boss")
        self.editor = BossEditor(app.source, store=self.store, server_dir=server_dir)
        proxy = SimpleNamespace(source=app.source, ops=SimpleNamespace(store=self.store))
        self.deliveries = BossDeliveries(proxy, server_dir, root=DELIVERIES / "boss",
                                        default_provides=default_provides)

    def _read_only(self, build):
        from wf.boss.reader import BossReader
        from .server import json_response
        from .drafts import DraftError
        try:
            return json_response(build(BossReader(self.app.source)))
        except (ValueError, KeyError, OSError, TypeError) as exc:
            raise DraftError(str(exc)) from exc

    def listing(self, query):
        return self._read_only(lambda reader: enrich_listing(reader, reader.list()))

    def templates(self, query):
        return self._read_only(template_sources)

    def options(self, query):
        return self._read_only(options)

    def terrain(self, query):
        return self._read_only(lambda reader: terrain_preview(reader, (query.get("path") or [""])[0]))

    def icons(self, query):
        return self._read_only(weapon_icons)

    def icon(self, query):
        from .server import Response, error
        logical = (query.get("path") or [""])[0].strip()
        if not ICON_PATH.match(logical) or ".." in logical.split("/"):
            return error(400, "只允许读取 item/ 下的图标")
        import wf_assets
        from wf.boss.reader import BossReader
        # Same resolution as the weapon/shop icon gate (state.raw of the logical PNG).
        logical = logical if logical.endswith(".png") else logical + ".png"
        raw = BossReader(self.app.source).raw(logical)
        if raw is not None:
            return Response(200, wf_assets.png_decode(raw), "image/png")
        try:  # official images live under the store's resolution roots (medium / android)
            found = self.app.assets.file(logical)
        except (AttributeError, OSError, ValueError):
            found = None
        if found is None:
            return error(404, "当前视图中没有这个图标")
        return Response(200, found[0], found[1])

    def show(self, query, quest):
        from .server import json_response
        return json_response(self.editor.read(quest))

    def section(self, query, quest, section):
        from .server import json_response
        return json_response(self.editor.inspect(quest, section))

    def timeline_summary(self, query, quest):
        from .server import json_response
        result = self.editor.inspect(quest, "timeline-summary")
        return json_response({**result["data"], "questId": result["questId"], "checks": result["checks"]})

    def drafts(self, query):
        from .server import json_response
        entries = [draft_summary(entry, self.store.load(entry["characterId"])) for entry in self.store.characters()]
        return json_response({"drafts": entries, "subjectKind": "boss"})

    def draft(self, query, quest):
        """Same shape as a character draft view (保存 / 生成 / 导出 actions)."""
        from .drafts import DraftError, status
        from .operations import ACTIONS
        from .server import json_response
        try:
            identity = self.editor.canonical(quest)
        except ValueError as exc:
            raise DraftError(str(exc)) from exc
        changeset = self.store.load(identity)
        return json_response({"characterId": identity, "questId": identity, "subjectKind": "boss",
                              "changeset": changeset, "status": status(changeset), "actions": ACTIONS})

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
            ("GET", re.compile(r"^/api/boss/templates$"), self.templates),
            ("GET", re.compile(r"^/api/boss/options$"), self.options),
            ("GET", re.compile(r"^/api/boss/drafts/(?P<quest>[^/]+)$"), self.draft),
            ("GET", re.compile(r"^/api/boss/terrain-preview$"), self.terrain),
            ("GET", re.compile(r"^/api/boss/weapon-icons$"), self.icons),
            ("GET", re.compile(r"^/api/boss/icon\.png$"), self.icon),
            *self.deliveries.routes(),
            ("GET", re.compile(r"^/api/boss/(?P<quest>[^/]+)/timeline-summary$"), self.timeline_summary),
            ("GET", re.compile(r"^/api/boss/(?P<quest>[^/]+)/(?P<section>terrain|shops|weapons|behavior|timeline)$"), self.section),
            ("GET", re.compile(r"^/api/boss/(?P<quest>[^/]+)$"), self.show),
            ("POST", re.compile(r"^/api/boss/drafts$"), self.edit),
            ("POST", re.compile(r"^/api/boss/drafts/(?P<quest>[^/]+)$"), self.edit),
            ("POST", re.compile(r"^/api/boss/drafts/(?P<quest>[^/]+)/save$"), self.save),
            ("POST", re.compile(r"^/api/boss/drafts/(?P<quest>[^/]+)/changes/(?P<change>c-[0-9a-f]{12})/revert$"), self.revert),
        ]
