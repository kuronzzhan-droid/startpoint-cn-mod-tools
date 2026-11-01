"""CLI argument and routing helpers for ability editing and local delivery."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .drafts import DraftError


def source_arguments(parser):
    parser.add_argument("--view", dest="view_name", help="profiles/local.json 中的命名视图")
    parser.add_argument("--view-base-version", dest="view_base_version", help="视图基线版本，默认 1.4.131")
    parser.add_argument("--manifest", type=Path, help="精确版本视图的只读 manifest")
    parser.add_argument("--store", type=Path, help="只读基线 store")
    parser.add_argument("--zip-dir", type=Path, action="append", default=None)
    parser.add_argument("--manifest-extra", type=Path, action="append", default=None)
    parser.add_argument("--server-dir", type=Path, help="只读服务端镜像根目录，文本编辑需要")


def add_commands(sub):
    from .delivery_actions import add_commands as add_delivery_actions
    add_delivery_actions(sub)
    from .view_commands import add_commands as add_views
    from .discovery_commands import add_commands as add_discovery
    add_views(sub)
    add_discovery(sub)
    from .character_routes import add_character_commands
    from .weapon_cli import add_weapon_commands
    add_character_commands(sub)
    add_weapon_commands(sub)
    from .skill_template_cli import add_skill_template_commands
    add_skill_template_commands(sub)
    add_device_result(sub)
    p = sub.add_parser("rehearse", help="只读检查交付对目标服务端的适用性，生成手工上边清单")
    p.add_argument("--delivery-dir", type=Path, required=True)
    p.add_argument("--server", default="local")
    p.add_argument("--zip", type=Path, action="append", dest="rehearsal_zips",
                   help="显式 ZIP 列表，可重复；结果仍写入 delivery-dir")
    p = sub.add_parser("boss", help="读取、编辑副本草稿；new 按暗凛模板新建共同决战")
    p.add_argument("cid", help="副本 ID、kind:path 选择器或 new")
    p.add_argument("--request", type=Path, help="bossRequest JSON")
    p.add_argument("--preview", action="store_true")
    p.add_argument("--section", choices=("terrain", "shops", "weapons", "behavior", "timeline"), help="只读候选子模型")
    p = sub.add_parser("ability", help="读取或编辑词条草稿（与 HTTP API 使用相同请求）")
    p.add_argument("cid")
    p.add_argument("--request", type=Path, help="abilityRequest JSON")
    p.add_argument("--preview", action="store_true", help="只预览请求，不写草稿")
    p = sub.add_parser("ability-preview", help="某一词条行的前后中文描述与五态规则")
    p.add_argument("cid")
    p.add_argument("--table", default="ability")
    p.add_argument("--key", required=True)
    p.add_argument("--row", type=int, default=0)
    p.add_argument("--level")
    p = sub.add_parser("ability-templates", help="kind 枚举与先例模板；零先例标待验证")
    p.add_argument("--table", default="ability")
    p.add_argument("--block", default="instant_content")
    p.add_argument("--kind", type=int)
    p = sub.add_parser("build", help="将草稿编译到 --out 并运行 wf deliver / check / compat")
    p.add_argument("cid")
    p.add_argument("--boss", action="store_true", help="读取独立 boss 草稿命名空间")
    p.add_argument("--from", dest="from_version", required=True)
    p.add_argument("--to", dest="to_version", required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--provides", type=Path, help="目标客户端能力与方法摘要")
    p.add_argument("--client-profile", help="目标客户端档案；默认 test-v34")
    p.add_argument("--apk", type=Path, action="append", help="显式目标 APK；可重复，覆盖 client_apks 配置")
    p.add_argument("--allow-unknown-client", action="store_true",
                   help="显式允许缺少 provides 的本地交付；兼容性仍标未确认并在清单留痕")
    p.add_argument("--baseline-manifest", type=Path)
    p.add_argument("--baseline-manifest-extra", type=Path, action="append", default=[])
    p.add_argument("--baseline-zip-dir", type=Path, action="append", default=[])
    p.add_argument("--base-store", type=Path)
    p.add_argument("--base-version", help="交付基线版本；默认沿用所选视图")
    p.add_argument("--view-lock", type=Path)
    p.add_argument("--pathlist", type=Path)
    # Permit the convenient command-local spelling without losing global values.
    p.add_argument("--server-dir", type=Path, default=argparse.SUPPRESS)


def editor(source, store, server_dir=None):
    from .ability import AbilityEditor
    base = Path(server_dir) / "assets/cdndata" if server_dir is not None else None
    return AbilityEditor(source, store=store,
                         server_text=base / "character_text.json" if base else None,
                         server_rank=base / "character_text_rank_p5b.json" if base else None)


def run_ability(args, source, store):
    backend = editor(source, store, args.server_dir)
    if args.command == "ability-templates":
        return backend.templates(table=args.table, block=args.block, kind=args.kind)
    if args.command == "ability-preview":
        return backend.row_preview(args.cid, args.table, args.key, row=args.row, level=args.level)
    if args.request:
        request = json.loads(args.request.read_text("utf-8-sig"))
        result = backend.preview(args.cid, request) if args.preview else backend.apply(args.cid, request)
        return {**result, "ok": not any(c.get("blocking") for c in result.get("checks", []))}
    if args.preview:
        raise DraftError("--preview 需要 --request")
    return backend.read(args.cid)


def run_build(args, store):
    from .build_view import baseline_from_args
    from .deliver_bridge import build_draft
    baseline = baseline_from_args(args)
    if getattr(args, "boss", False):
        from .boss import BossDraftStore
        store = BossDraftStore(store.root / "boss")
    return build_draft(args.cid, from_version=args.from_version, to_version=args.to_version,
                       out=args.out, store=store, provides=args.provides,
                       client_profile=args.client_profile,
                       apk=args.apk,
                       allow_unknown_client=args.allow_unknown_client,
                       baseline_view=baseline, base_store=baseline.store,
                       base_version=baseline.base_version,
                       server_dir=args.server_dir, pathlist=args.pathlist)


def add_device_result(sub):
    p = sub.add_parser("device-result", help="交付的真机实测记录 device-result.json：show / write / import / schema")
    p.add_argument("action", choices=("show", "write", "import", "schema"))
    p.add_argument("target", nargs="?", help="show/write：交付目录名；import：来源 device-result.json 或其交付目录")
    p.add_argument("--boss", action="store_true", help="副本交付（work/studio-deliveries/boss）")
    p.add_argument("--deliveries", type=Path, help="交付根目录（默认 work/studio-deliveries[/boss]）")
    p.add_argument("--delivery", help="import：目标交付目录名（默认与来源目录同名）")
    p.add_argument("--file", type=Path, help="write：实测记录 JSON（结构见 schemas/device-result.schema.json）")
    p.add_argument("--status", choices=("通过", "失败", "未执行", "作废"), help="write：覆盖或直接给出结论")
    p.add_argument("--tester", help="write：测试人")
    p.add_argument("--tested-at", help="write：实测时间（默认现在）")
    p.add_argument("--notes", help="write：备注")
    p.add_argument("--allow-unverified", action="store_true",
                   help="import：来源目录没有 delivery-manifest.json 时仍导入（标 archivesMatch=null）")


def _delivery_folder(args, name):
    from . import device_result
    from .boss_routes import BossDeliveries
    from .deliver_routes import DELIVERIES, DeliverRoutes
    routes = BossDeliveries if args.boss else DeliverRoutes
    root = args.deliveries or (DELIVERIES / "boss" if args.boss else DELIVERIES)
    if not name or not routes.name_pattern.fullmatch(name):
        raise DraftError(f"交付目录名无效：{name!r}")
    folder = (Path(root) / name).resolve()
    if not folder.is_relative_to(Path(root).resolve()) or not folder.is_dir():
        raise DraftError(f"没有这个交付目录：{folder}")
    return folder, routes.kind, device_result


def run_device_result(args):
    from . import device_result
    if args.action == "schema":
        return device_result.schema()
    if args.action == "show":
        folder, kind, module = _delivery_folder(args, args.target)
        return {"name": folder.name, "deviceResult": module.read(folder, kind)}
    if args.action == "write":
        folder, kind, module = _delivery_folder(args, args.target)
        body = json.loads(args.file.read_text("utf-8-sig")) if args.file else {"checks": []}
        if not isinstance(body, dict):
            raise DraftError("--file 必须是 JSON 对象")
        overrides = {"status": args.status, "tester": args.tester, "notes": args.notes,
                     "testedAt": args.tested_at}
        body.update({k: v for k, v in overrides.items() if v is not None})
        body.setdefault("testedAt", module.now())
        if "status" not in body:
            raise DraftError("需要 --status 或 --file 里的 status")
        return {"name": folder.name, "result": module.write(folder, kind, body)}
    source = Path(args.target or "")
    if not args.target:
        raise DraftError("import 需要来源路径")
    name = args.delivery or (source.name if source.is_dir() else source.parent.name)
    folder, kind, module = _delivery_folder(args, name)
    return {"name": folder.name,
            "result": module.import_file(source, folder, kind, allow_unverified=args.allow_unverified)}
