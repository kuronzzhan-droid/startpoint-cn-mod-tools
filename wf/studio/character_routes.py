"""CLI and HTTP adapters for formal clone / scratch promotion."""
from __future__ import annotations

import re
from .character_clone import clone, clone_change, ops_for
from .drafts import DraftError, now


def promote(ops, sid, *, to, code=None, server_dir=None):
    from .scratch import bind, ELEMENTS
    scratch = ops.store.load(sid)
    if not sid.startswith("scratch-") or not scratch or "scratch" not in scratch:
        raise DraftError(f"不是 scratch 草稿：{sid}")
    meta = scratch["scratch"]
    if meta.get("boundTo"):
        raise DraftError("scratch 已经绑定或升级")
    if scratch["baseView"] != ops.source.version:
        raise DraftError("scratch 基线与当前视图不同")
    base = meta["base"].get("characterId")
    if not base:
        raise DraftError("scratch 母本只有像素代码，没有可克隆的角色 ID")
    request = {"from": base, "to": str(to), "code": code or scratch["code"].removeprefix("scratch_"),
               "name": meta["name"], "element": ELEMENTS.index(meta["element"])}
    with ops.store._lock:
        result = clone(ops, request, server_dir=server_dir)
        try:
            if scratch["changes"]:
                result["promotion"] = bind(ops_for(ops, str(to)), sid, {"characterId": str(to)})
            else:
                meta = {**meta, "boundTo": {"characterId": str(to), "code": request["code"], "at": now(),
                                          "changes": [clone_change(result["changeset"])["id"]]}}
                ops.store.update_scratch(sid, meta)
            result["changeset"] = ops.store.load(str(to))
            result["scratch"] = sid
            return result
        except Exception:
            ops.store.discard_all(str(to))
            ops.store.restore(sid, scratch)
            raise


def add_character_commands(sub):
    p = sub.add_parser("character", help="正式角色草稿")
    actions = p.add_subparsers(dest="character_command", required=True)
    c = actions.add_parser("clone", help="从母本克隆新 ID")
    c.add_argument("--from", dest="template", required=True)
    c.add_argument("--to", dest="character_id", required=True)
    c.add_argument("--code", required=True)
    c.add_argument("--skill", choices=("copy", "reuse"), default="copy")
    c.add_argument("--element", type=int, choices=range(6))
    c.add_argument("--name")
    c.add_argument("--preview", action="store_true", help="只检查与预览，不写草稿")
    p = sub.add_parser("scratch-promote", help="将 scratch 像素草稿升级为新 ID 正式角色")
    p.add_argument("scratch")
    p.add_argument("--to", dest="character_id", required=True)
    p.add_argument("--code")


def run_character_command(args, ops):
    if args.command == "scratch-promote":
        return promote(ops, args.scratch, to=args.character_id, code=args.code,
                       server_dir=getattr(args, "server_dir", None))
    request = {"from": args.template, "to": args.character_id, "code": args.code, "skill": args.skill}
    for key in ("element", "name"):
        if getattr(args, key, None) is not None:
            request[key] = getattr(args, key)
    return clone(ops, request, server_dir=getattr(args, "server_dir", None),
                 preview=getattr(args, "preview", False))


class CharacterRoutes:
    def __init__(self, app, server_dir=None):
        self.app, self.server_dir = app, server_dir

    def clone(self, query, body):
        from .server import json_response
        from .clone_checks import response_checks
        from wf.rules.catalog import result
        try:
            document = clone(self.app.ops, body, server_dir=self.server_dir,
                             preview=(query.get("preview") or ["false"])[0] == "true")
            return json_response({**document, "checks": response_checks(document)})
        except (ValueError, KeyError, OSError, TypeError) as exc:
            return json_response({"ok": False, "error": str(exc), "subjectKind": "character",
                "characterId": body.get("to") if isinstance(body, dict) else None,
                "checks": [result("character.inputs", "问题", str(exc), blocking=True)],
                "runtime": "未执行"}, 400)

    def promote(self, query, body, sid):
        from .server import json_response
        if set(body) - {"to", "code"} or "to" not in body:
            raise DraftError("升级请求只接受 to（必填）与 code")
        return json_response(promote(self.app.ops, sid, server_dir=self.server_dir, **body))

    def routes(self):
        from .scratch import SCRATCH_ID
        wiki_id = rf"(?P<cid>\d+|{SCRATCH_ID.pattern.removeprefix('^').removesuffix('$')})"
        return [("POST", re.compile(r"^/api/drafts/(?P<cid>\d+)/speech$"), self.speech),
                ("GET", re.compile(rf"^/api/drafts/{wiki_id}/wiki-image$"), self.wiki_image),
                ("GET", re.compile(rf"^/api/drafts/{wiki_id}/wiki-card$"), self.wiki_card),
                ("POST", re.compile(r"^/api/studio/characters/clone$"), self.clone),
                ("POST", re.compile(r"^/api/studio/characters/(?P<sid>scratch-[a-z0-9-]+)/promote$"), self.promote)]

    def speech(self, query, body, cid):
        from .server import json_response
        from .speech import append
        return json_response(append(self.app.ops, cid, body))

    def wiki_card(self, query, cid):
        from .server import json_response
        from .wiki_preview import preview
        return json_response(preview(self.app.ops, cid, server_dir=self.server_dir))

    def wiki_image(self, query, cid):
        from .server import Response
        from .wiki_preview import image
        return Response(200, image(self.app.ops, cid, (query.get("path") or [""])[0]), "image/png",
                        "no-store")
