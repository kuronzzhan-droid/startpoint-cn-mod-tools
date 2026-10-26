"""Skill template CLI adapters sharing the draft editor with HTTP."""
from __future__ import annotations

import json
from pathlib import Path

from .drafts import DraftError


def add_skill_template_commands(sub):
    command = sub.add_parser("skill-templates", help="查询官方技能模板及伤害节点")
    actions = command.add_subparsers(dest="skill_template_command", required=True)
    listing = actions.add_parser("list", help="按角色、技能名或键查询母本")
    listing.add_argument("--q", default="")
    detail = actions.add_parser("detail", help="读取伤害节点与特效族")
    detail.add_argument("key")
    apply = sub.add_parser("skill-template", help="克隆、调整技能并保存到角色草稿")
    apply.add_argument("cid")
    apply.add_argument("--request", type=Path, required=True, help="skillTemplateRequest JSON 文件")
    apply.add_argument("--preview", action="store_true", help="只检查与预览，不写草稿或预留键")


def run_skill_template(args, source, store):
    from .skill_template import SkillTemplateEditor
    backend = SkillTemplateEditor(source, store=store, server_dir=getattr(args, "server_dir", None))
    if args.command == "skill-templates":
        if args.skill_template_command == "list":
            return backend.listing(q=args.q)
        document = backend.detail(args.key)
        if document is None:
            raise DraftError("当前视图中没有这个技能模板")
        return document
    request = json.loads(args.request.read_text("utf-8-sig"))
    if not isinstance(request, dict):
        raise DraftError("skill-template --request 必须是 JSON 对象")
    body_preview = request.pop("preview", False)
    if not isinstance(body_preview, bool):
        raise DraftError("preview 必须是布尔值")
    operation = backend.preview if args.preview or body_preview else backend.apply
    return operation(args.cid, request)
