"""Small action mixin; every POST is dispatched through the existing WriteGuard."""
from .drafts import DraftError


class DeliveryActions:
    def _action(self, name, operation):
        from .server import json_response
        with self._lock:
            if name in self.running.values() or name in self._rehearsing:
                raise DraftError("交付正在生成或执行操作，请等待结束")
            self._rehearsing.add(name)
        try:
            result = operation(self._folder(name))
            return json_response({"name": name, **result})
        except (ValueError, OSError, KeyError, TypeError) as exc:
            raise DraftError(str(exc)) from exc
        finally:
            with self._lock:
                self._rehearsing.discard(name)

    def apply(self, query, body, name):
        from .apply_local import apply
        from .rehearsal_io import server_name
        if set(body) - {"server", "dryRun"} or type(body.get("dryRun", False)) is not bool:
            raise DraftError('应用请求只接受 {"server":"local", "dryRun":false}')
        server = server_name(body.get("server", "local"))
        return self._action(name, lambda folder: apply(folder, server,
                                                      dry_run=body.get("dryRun", False)))

    def unapply(self, query, body, name):
        from .apply_local import unapply
        from .rehearsal_io import server_name
        if set(body) - {"server"}:
            raise DraftError('撤销请求只接受 {"server":"local"}')
        server = server_name(body.get("server", "local"))
        return self._action(name, lambda folder: unapply(folder, server))

    def overlay(self, query, body, name):
        from .overlay_export import export_overlay
        if set(body) != {"compatibleClient"} or not isinstance(body["compatibleClient"], str):
            raise DraftError('Overlay 请求只接受 {"compatibleClient":"CN 1.8.1"}')
        return self._action(name, lambda folder: export_overlay(folder, body["compatibleClient"]))


def add_commands(sub):
    from pathlib import Path
    for command in ("apply", "unapply", "export-overlay"):
        parser = sub.add_parser(command)
        parser.add_argument("--delivery-dir", type=Path, required=True)
        if command == "export-overlay":
            parser.add_argument("--compatible-client", required=True)
            parser.add_argument("--out", type=Path)
        else:
            parser.add_argument("--server", default="local")
        if command == "apply":
            parser.add_argument("--dry-run", action="store_true")
