"""PF action CLI adapters sharing the HTTP workshop implementation."""
from __future__ import annotations

import json
from pathlib import Path

from .drafts import DraftError


def add_pf_commands(sub):
    command = sub.add_parser("pf-action", help="强化弹射动作 list/show/clone/keys；输出一行 JSON")
    actions = command.add_subparsers(dest="pf_command", required=True)
    listing = actions.add_parser("list", help="列出 CDN 与目标 APK 的三档母本")
    listing.add_argument("--q", default="")
    show = actions.add_parser("show", help="读取三档命中系数、属性与特效摘要")
    show.add_argument("key")
    clone = actions.add_parser("clone", help="克隆官方三档为新的 PF 动作草稿")
    clone.add_argument("cid")
    clone.add_argument("--request", type=Path, help="pfActionCloneRequest JSON，UTF-8")
    clone.add_argument("--key", help="新 power_flip_action 键")
    clone.add_argument("--source", help="母本 power_flip_action 键")
    clone.add_argument("--element", choices=("火", "水", "雷", "风", "光", "暗"))
    clone.add_argument("--scale", nargs="+", type=float, help="统一系数，或按 Lv1 Lv2 Lv3 给出三个系数")
    clone.add_argument("--effects", type=Path, help="旧特效族到新私有特效族的 JSON 映射")
    clone.add_argument("--preview", action="store_true", help="只检查与预览，不写草稿或预留键")
    keys = actions.add_parser("keys", help="列出角色草稿内供召唤工坊引用的 PF 键")
    keys.add_argument("cid")
    for parser in (listing, show, clone):
        parser.add_argument("--client-profile", help="目标客户端档案；默认使用编辑台默认档案")
        parser.add_argument("--apk", type=Path, action="append", help="显式目标 APK；可重复，覆盖本机配置")


def run_pf(args, ops):
    from . import pf_actions
    if args.pf_command == "keys":
        return pf_actions.draft_keys(ops.store, args.cid)
    options = {"client_profile": args.client_profile, "apks": args.apk}
    if args.pf_command == "list":
        return pf_actions.listing(ops.source, args.q, **options)
    if args.pf_command == "show":
        document = pf_actions.detail(ops.source, args.key, **options)
        if document is None:
            raise DraftError("当前视图和目标 APK 中没有这个 PF 动作")
        return document
    request = json.loads(args.request.read_text("utf-8-sig")) if args.request else {}
    if not isinstance(request, dict):
        raise DraftError("pf-action --request 必须是 JSON 对象")
    for key in ("key", "source", "element"):
        if getattr(args, key) is not None:
            request[key] = getattr(args, key)
    if args.scale is not None:
        if len(args.scale) not in (1, 3):
            raise DraftError("--scale 需要一个统一系数，或三个依次对应 Lv1/Lv2/Lv3 的系数")
        request["scale"] = args.scale[0] if len(args.scale) == 1 else args.scale
    if args.effects:
        request["effects"] = json.loads(args.effects.read_text("utf-8-sig"))
    return pf_actions.clone(ops, args.cid, request, preview=args.preview, **options)
