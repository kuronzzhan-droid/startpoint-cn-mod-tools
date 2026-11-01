"""Batch endpoints inherit the Studio token/origin guards; GET never writes."""
import re

from .batch import BatchEditor
from .balance_import import parse_table
from .server import json_response


class BatchRoutes:
    def __init__(self, app):
        self.service = BatchEditor(app.ops, server_dir=app.server_dir)

    def ids(self, query, action):
        from .clone_ids import linked_check, next_linked
        value = lambda name: query.get(name, [None])[0]
        kwargs = {"server_dir": self.service.server_dir}
        if action == "next":
            result = next_linked(self.service.ops, value("near"), donor=value("from"), **kwargs)
        else:
            cid = value("id")
            result = linked_check(self.service.ops, cid, code=f"variant_{value('from')}_{cid}", **kwargs)
        return json_response(result)

    def mapping(self, query):
        return json_response({"mapping": self.service.mapping()})

    def balance(self, query, body, action):
        if action == "parse":
            headers, rows = parse_table(body.get("text"))
            return json_response({"headers": headers, "rows": rows})
        if action == "mapping":
            return json_response({"mapping": self.service.mapping(body.get("mapping", {}))})
        method = self.service.balance_preview if action == "preview" else self.service.balance_apply
        return json_response(method(body))

    def variants(self, query, body, action):
        method = self.service.variants_preview if action == "preview" else self.service.variants_apply
        return json_response(method(body))

    def routes(self):
        base = r"^/api/studio/characters/"
        return [("GET", re.compile(base + r"balance/mapping$"), self.mapping),
                ("GET", re.compile(base + r"variants/ids/(?P<action>check|next)$"), self.ids),
                ("POST", re.compile(base + r"balance/(?P<action>parse|mapping|preview|apply)$"), self.balance),
                ("POST", re.compile(base + r"variants/(?P<action>preview|apply)$"), self.variants)]
