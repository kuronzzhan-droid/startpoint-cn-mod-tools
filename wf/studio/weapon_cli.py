"""Weapon CLI adapters; reuse the HTTP editor without opening an HTTP session."""
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path

from .drafts import DraftError, status
from .weapon_editor import WeaponEditor
from .weapon_store import WeaponDraftStore


def add_weapon_commands(sub):
    command = sub.add_parser("weapon", help="武器 list/show/clone/materials/icon；输出一行 JSON")
    actions = command.add_subparsers(dest="weapon_command", required=True)
    listing = actions.add_parser("list", help="查询当前武器目录")
    for name in ("q", "element", "rarity", "limit"):
        listing.add_argument("--" + name)
    show = actions.add_parser("show", help="读取武器与草稿候选")
    show.add_argument("wid")
    clone = actions.add_parser("clone", help="克隆武器为独立草稿")
    clone.add_argument("--from", dest="source_weapon")
    clone.add_argument("--to", dest="weapon_id")
    clone.add_argument("--code")
    clone.add_argument("--name")
    clone.add_argument("--exclusive-character")
    clone.add_argument("--soul-template", type=Path, help="soul_template JSON 文件")
    material = actions.add_parser("materials", help="编辑武器强化材料")
    material.add_argument("wid")
    icon = actions.add_parser("icon", help="导入武器20x20或魂珠/材料40x40 PNG")
    icon.add_argument("wid")
    icon.add_argument("--kind", choices=("weapon", "soul", "material"))
    icon.add_argument("--png", type=Path)
    icon.add_argument("--item-id")
    options = actions.add_parser("set-options", help="从当前视图读取专武类目与材料")
    weapon_set = actions.add_parser("set", help="配置专武强化、兑换与突破材料")
    weapon_set.add_argument("wid")
    for parser in (clone, material, icon, weapon_set):
        parser.add_argument("--request", type=Path, help="与对应 HTTP body 相同的 JSON 文件")
        parser.add_argument("--preview", action="store_true")
    for parser in (listing, show, clone, material, icon, options, weapon_set):
        parser.add_argument("--server-dir", type=Path, default=argparse.SUPPRESS)
        parser.add_argument("--provides", type=Path)
        parser.add_argument("--client-profile")


def _request(args):
    request = json.loads(args.request.read_text("utf-8-sig")) if args.request else {}
    if not isinstance(request, dict):
        raise DraftError("weapon --request must be a JSON object")
    return request


def run_weapon(args, source, store):
    from .source import StudioSource
    from .weapon_catalog import detail, listing
    backend = WeaponEditor(source, store=WeaponDraftStore(store.root / "weapons"),
        server_dir=getattr(args, "server_dir", None), provides=args.provides,
        client_profile=args.client_profile)
    if args.weapon_command == "set-options":
        from .weapon_set_options import options
        return options(source, backend.server_dir)
    if args.weapon_command == "list":
        query = {name: [value] for name in ("q", "element", "rarity", "limit")
                 if (value := getattr(args, name, None)) is not None}
        return listing(source, query, server_dir=backend.server_dir)
    if args.weapon_command == "show":
        state, draft = backend.state(args.wid)
        candidate = StudioSource(state, official_root=getattr(source, "official_root", None)) if draft else source
        document = detail(candidate, args.wid, server_dir=backend.server_dir)
        if document is None:
            raise DraftError("当前视图和武器草稿中没有这个武器")
        return {**document, "weaponId": args.wid, "subjectKind": "weapon", "changeset": draft,
                "draft_status": status(draft), "checks": getattr(state, "weapon_checks", []), "runtime": "未执行"}
    request = _request(args)
    if args.weapon_command == "clone":
        for attr, key in (("source_weapon", "sourceWeapon"), ("weapon_id", "id"), ("code", "code"),
                          ("name", "name"), ("exclusive_character", "exclusive_character")):
            if getattr(args, attr) is not None:
                request[key] = getattr(args, attr)
        if args.soul_template:
            request["soul_template"] = json.loads(args.soul_template.read_text("utf-8-sig"))
        return backend.apply("weapon_clone", request, preview=args.preview)
    if "id" in request and request["id"] != args.wid:
        raise DraftError("请求中的武器 ID 与命令行不一致")
    request["id"] = args.wid
    if args.weapon_command == "icon":
        if args.kind is not None:
            request["kind"] = args.kind
        if args.png:
            request["png"] = base64.b64encode(args.png.read_bytes()).decode("ascii")
        if args.item_id:
            request["item_id"] = args.item_id
    return backend.apply("weapon_" + args.weapon_command, request, wid=args.wid, preview=args.preview)
