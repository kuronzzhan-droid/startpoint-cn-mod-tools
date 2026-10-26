"""PF action workshop HTTP adapters; the server guards every POST."""
from __future__ import annotations

import re

from .drafts import DraftError


def _query(query, allowed):
    unknown = set(query) - set(allowed)
    if unknown:
        raise DraftError("不支持的查询参数：" + ", ".join(sorted(unknown)))
    if any(len(values) != 1 for values in query.values()):
        raise DraftError("每个查询参数只能出现一次")
    return {key: values[0] for key, values in query.items()}


def _checks(document):
    from wf.rules.catalog import result
    checks = []
    for check in document.get("checks", []):
        failed = check.get("level") == "error"
        state = "问题" if failed else "待验证" if check.get("level") == "warn" else "满足"
        if check["code"] == "pf.bundle-unchecked":
            state = "未执行"
        checks.append(result(check["code"], state, check["message"], blocking=failed))
    checks.append(result("pf.runtime", "未执行", "未执行目标客户端战斗与特效验证"))
    return checks


class PFActionsRoutes:
    def __init__(self, app):
        self.app = app

    def listing(self, query):
        from .pf_actions import listing
        from .server import json_response
        options = _query(query, ("q", "clientProfile"))
        return json_response(listing(self.app.source, options.get("q", ""),
                                     client_profile=options.get("clientProfile")))

    def check(self, query):
        from .ids import canonical, check_id, collect_occupancy
        from .pf_catalog import PfCatalog
        from .server import json_response
        options = _query(query, ("key", "clientProfile"))
        key = canonical("power_flip_action", options.get("key", ""))
        catalog = PfCatalog(self.app.source, client_profile=options.get("clientProfile"))
        occupied = collect_occupancy(self.app.source, self.app.ops.store.root, pf_catalog=catalog)
        info = check_id(self.app.source, "power_flip_action", key, occupancy=occupied)
        checked = catalog.bundled_available
        return json_response({**info, "key": key, "bundledAvailable": checked,
                              "available": info["available"] if checked or info["owners"] else None,
                              "status": "occupied" if info["owners"] else "available" if checked else "unchecked",
                              "warnings": catalog.warnings})

    def detail(self, query, key):
        from .pf_actions import detail
        from .server import error, json_response
        options = _query(query, ("clientProfile",))
        document = detail(self.app.source, key, client_profile=options.get("clientProfile"))
        return error(404, "当前视图和目标 APK 中没有这个 PF 动作") if document is None else json_response(document)

    def clone(self, query, body, cid):
        from .pf_actions import clone
        from .server import json_response
        from wf.rules.catalog import result
        try:
            options = _query(query, ("preview", "clientProfile"))
            preview = options.get("preview", "false")
            if preview not in ("true", "false"):
                raise DraftError("preview 只能是 true 或 false")
            document = clone(self.app.ops, cid, body, preview=preview == "true",
                             client_profile=options.get("clientProfile"))
            return json_response({**document, "checks": _checks(document)})
        except (ValueError, KeyError, OSError, TypeError) as exc:
            return json_response({"ok": False, "error": str(exc), "characterId": cid,
                "checks": [result("pf.inputs", "问题", str(exc), blocking=True)],
                "runtime": "未执行"}, 400)

    def keys(self, query, cid):
        from .pf_actions import draft_keys
        from .server import json_response
        _query(query, ())
        return json_response(draft_keys(self.app.ops.store, cid))

    def routes(self):
        return [
            ("GET", re.compile(r"^/api/studio/pf-actions$"), self.listing),
            ("GET", re.compile(r"^/api/studio/pf-actions/check$"), self.check),
            ("GET", re.compile(r"^/api/studio/pf-actions/(?P<key>[^/]+)$"), self.detail),
            ("POST", re.compile(r"^/api/drafts/(?P<cid>\d+)/pf-action$"), self.clone),
            ("GET", re.compile(r"^/api/drafts/(?P<cid>\d+)/pf-actions$"), self.keys),
        ]
