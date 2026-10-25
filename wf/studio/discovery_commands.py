"""CLI and HTTP contracts for read-only ID/version discovery."""
import argparse
import re
from pathlib import Path

from .drafts import DraftError
from .id_catalog import TABLES
from .ids import check_id, next_id
from .versions import next_version


def add_commands(sub):
    ids = sub.add_parser("ids", help="查询视图、服务端镜像和全部草稿的 ID 占用")
    actions = ids.add_subparsers(dest="id_action", required=True)
    for action in ("check", "next"):
        parser = actions.add_parser(action)
        parser.add_argument("kind", choices=tuple(TABLES))
        if action == "check":
            parser.add_argument("identity")
        else:
            parser.add_argument("--near")
        parser.add_argument("--server-dir", type=Path, default=argparse.SUPPRESS)
    versions = sub.add_parser("versions", help="查询视图的下一可用资源版本")
    parser = versions.add_subparsers(dest="version_action", required=True).add_parser("next")
    parser.add_argument("--view", dest="view_name", default=argparse.SUPPRESS)
    parser.add_argument("--reservations-file", type=Path)


def run(args, source, store):
    if args.command == "versions":
        return next_version(source, view_name=getattr(args, "view_name", None),
                            reservations_file=args.reservations_file)
    options = {"drafts_root": store.root, "server_dir": args.server_dir}
    if args.id_action == "check":
        return check_id(source, args.kind, args.identity, **options)
    return next_id(source, args.kind, args.near, **options)


class DiscoveryRoutes:
    def __init__(self, app, server_dir=None):
        self.app, self.server_dir = app, server_dir

    def routes(self):
        return [("GET", re.compile(r"^/api/studio/ids/check$"), self.check),
                ("GET", re.compile(r"^/api/studio/ids/next$"), self.next),
                ("GET", re.compile(r"^/api/studio/versions/next$"), self.version)]

    @staticmethod
    def value(query, name, required=False):
        values = query.get(name, [])
        if len(values) > 1 or (values and not values[0]) or (required and not values):
            raise DraftError(f"参数 {name} 需要单个非空值")
        return values[0] if values else None

    def check(self, query):
        from .server import json_response
        return json_response(check_id(self.app.source, self.value(query, "kind", True),
                                      self.value(query, "id", True), drafts_root=self.app.ops.store.root,
                                      server_dir=self.server_dir))

    def next(self, query):
        from .server import json_response
        return json_response(next_id(self.app.source, self.value(query, "kind", True),
                                     self.value(query, "near"), drafts_root=self.app.ops.store.root,
                                     server_dir=self.server_dir))

    def version(self, query):
        from .server import json_response
        from .source import build_source
        name = self.value(query, "view")
        source = None
        try:
            source = build_source(view_name=name) if name else self.app.source
            result = next_version(source, view_name=name)
        except (ValueError, KeyError, OSError) as exc:
            raise DraftError(f"无法查询视图版本: {exc}") from exc
        finally:
            if name and source is not None and hasattr(source.view, "close"):
                source.view.close()
        return json_response(result)
