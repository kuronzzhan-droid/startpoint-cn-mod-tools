"""Read configured view names and export the process's immutable selected view."""
import re

from wf.paths import profile_data
from wf.view.export import export_store
from .drafts import DraftError


class ViewRoutes:
    def __init__(self, app):
        self.app = app

    def routes(self):
        return [("GET", re.compile(r"^/api/studio/views$"), self.listing),
                ("POST", re.compile(r"^/api/studio/views/export-store$"), self.export)]

    def listing(self, query):
        from .server import json_response
        config, _ = profile_data()
        views = config.get("views", {})
        if not isinstance(views, dict):
            raise DraftError("profile views must be an object")
        return json_response({"views": sorted(views),
                              "current": getattr(self.app.source.view, "view_name", None),
                              "source": self.app.source.describe(),
                              "runtimeSwitching": False, "restartRequired": True})

    def export(self, query, body):
        from .server import json_response
        try:
            if set(body) - {"out", "copy"}:
                raise ValueError("export-store only accepts out and copy")
            destination = body.get("out")
            if not isinstance(destination, str) or not destination.strip():
                raise ValueError("export-store requires a nonempty out path")
            copy = body.get("copy", False)
            if not isinstance(copy, bool):
                raise ValueError("copy must be a boolean")
            result = export_store(self.app.source.view, destination, copy=copy)
            return json_response({"ok": True, **result, "version": self.app.source.version,
                                  "view": getattr(self.app.source.view, "view_name", None)})
        except (ValueError, OSError, TypeError) as exc:
            raise DraftError(str(exc)) from exc
