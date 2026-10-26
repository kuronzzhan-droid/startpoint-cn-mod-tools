"""Skill template HTTP adapters; all writes use the studio's common guard."""
from __future__ import annotations

import re

from .drafts import DraftError


class SkillTemplateRoutes:
    def __init__(self, app, server_dir=None):
        self.app, self.server_dir = app, server_dir

    def editor(self):
        from .skill_template import SkillTemplateEditor
        return SkillTemplateEditor(self.app.source, store=self.app.ops.store, server_dir=self.server_dir)

    def listing(self, query):
        from .server import json_response
        try:
            return json_response(self.editor().listing(q=(query.get("q") or [""])[0]))
        except (ValueError, KeyError, OSError, TypeError) as exc:
            raise DraftError(str(exc)) from exc

    def detail(self, query, key):
        from .server import error, json_response
        try:
            document = self.editor().detail(key)
        except (ValueError, KeyError, OSError, TypeError) as exc:
            raise DraftError(str(exc)) from exc
        return error(404, "当前视图中没有这个技能模板") if document is None else json_response(document)

    def apply(self, query, body, cid):
        from wf.rules.catalog import result
        from .server import json_response
        try:
            request = dict(body)
            body_preview = request.pop("preview", False)
            query_preview = (query.get("preview") or ["false"])[0]
            if not isinstance(body_preview, bool) or query_preview not in {"true", "false"}:
                raise DraftError("preview 必须是布尔值，查询参数使用 true 或 false")
            backend = self.editor()
            operation = backend.preview if body_preview or query_preview == "true" else backend.apply
            return json_response(operation(cid, request))
        except (ValueError, KeyError, OSError, TypeError) as exc:
            return json_response({"ok": False, "error": str(exc), "characterId": cid,
                "subjectKind": "character", "checks": [
                    result("skill-template.inputs", "问题", str(exc), blocking=True),
                    *getattr(exc, "checks", [])], "runtime": "未执行"}, 400)

    def routes(self):
        return [
            ("GET", re.compile(r"^/api/studio/skill-templates$"), self.listing),
            ("GET", re.compile(r"^/api/studio/skill-templates/(?P<key>[^/]+)$"), self.detail),
            ("POST", re.compile(r"^/api/drafts/(?P<cid>\d+)/skill-template$"), self.apply),
        ]
