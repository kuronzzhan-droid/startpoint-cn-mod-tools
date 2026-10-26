"""HTTP and CLI adapters for summons stored in character drafts."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from .drafts import DraftError
from .summon import SummonEditor


def _query_value(query, name, default):
    values = query.get(name)
    if values is None:
        return default
    if len(values) != 1 or not isinstance(values[0], str):
        raise DraftError(f"查询参数 {name} 只接受一个值")
    return values[0]


def _preview(query):
    value = _query_value(query, "preview", "false")
    if value not in {"true", "false"}:
        raise DraftError("preview 查询参数只接受 true 或 false")
    return value == "true"


def add_summon_commands(sub):
    command = sub.add_parser("summon", help="协力角色工坊：templates 查母本，角色 ID 读取或编辑草稿")
    command.add_argument("cid", help="templates 或宿主角色 ID")
    command.add_argument("--q", default="", help="母本名称、ID、代码名搜索")
    command.add_argument("--limit", type=int, default=100)
    command.add_argument("--offset", type=int, default=0)
    command.add_argument("--rarity", type=int, choices=range(1, 6))
    command.add_argument("--request", type=Path, help="summonCloneRequest UTF-8 JSON 文件")
    command.add_argument("--preview", action="store_true", help="预览将写入的行与检查，不写草稿")
    command.add_argument("--server-dir", type=Path, default=argparse.SUPPRESS,
                         help="只读服务端镜像目录，参与 ID 占用检查")


def run_summon(args, source, store):
    editor = SummonEditor(source, store=store, server_dir=getattr(args, "server_dir", None))
    if args.cid == "templates":
        if args.request or args.preview:
            raise DraftError("summon templates 不接受 --request 或 --preview")
        return editor.templates(args.q, limit=args.limit, offset=args.offset, rarity=args.rarity)
    if args.q:
        raise DraftError("--q 仅用于 summon templates")
    if args.request:
        request = json.loads(args.request.read_text("utf-8-sig"))
        return editor.apply(args.cid, request, preview=args.preview)
    if args.preview:
        raise DraftError("summon --preview 需要 --request")
    return editor.read(args.cid)


class SummonRoutes:
    def __init__(self, app, server_dir=None):
        self.editor = SummonEditor(app.source, store=app.ops.store, server_dir=server_dir)

    @staticmethod
    def _response(build, cid=None):
        from .server import json_response
        from wf.rules.catalog import result
        try:
            return json_response(build())
        except (ValueError, KeyError, OSError, TypeError) as exc:
            return json_response({"ok": False, "error": str(exc), "characterId": cid,
                "checks": [result("summon.inputs", "问题", str(exc), blocking=True)],
                "runtime": "未执行"}, 400)

    def templates(self, query):
        return self._response(lambda: self.editor.templates(_query_value(query, "q", ""),
            limit=int(_query_value(query, "limit", "100")), offset=int(_query_value(query, "offset", "0")),
            rarity=int(_query_value(query, "rarity", "0")) if "rarity" in query else None))

    def read(self, query, cid):
        return self._response(lambda: self.editor.read(cid), cid)

    def apply(self, query, body, cid):
        return self._response(lambda: self.editor.apply(cid, body, preview=_preview(query)), cid)

    def routes(self):
        return [("GET", re.compile(r"^/api/studio/summon/templates$"), self.templates),
                ("GET", re.compile(r"^/api/drafts/(?P<cid>\d+)/summon$"), self.read),
                ("POST", re.compile(r"^/api/drafts/(?P<cid>\d+)/summon$"), self.apply)]
