"""CLI argument and routing helpers for ability editing and local delivery."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .drafts import DraftError


def source_arguments(parser):
    parser.add_argument("--manifest", type=Path, help="精确版本视图的只读 manifest")
    parser.add_argument("--store", type=Path, help="只读基线 store")
    parser.add_argument("--zip-dir", type=Path, action="append", default=None)
    parser.add_argument("--manifest-extra", type=Path, action="append", default=None)
    parser.add_argument("--server-dir", type=Path, help="只读服务端镜像根目录，文本编辑需要")


def add_commands(sub):
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
    p.add_argument("--allow-unknown-client", action="store_true",
                   help="显式允许缺少 provides 的本地交付；兼容性仍标未确认并在清单留痕")
    p.add_argument("--baseline-manifest", type=Path)
    p.add_argument("--baseline-manifest-extra", type=Path, action="append", default=[])
    p.add_argument("--baseline-zip-dir", type=Path, action="append", default=[])
    p.add_argument("--base-store", type=Path)
    p.add_argument("--base-version", default="1.4.131")
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
    from .deliver_bridge import build_draft
    if getattr(args, "boss", False):
        from .boss import BossDraftStore
        store = BossDraftStore(store.root / "boss")
    return build_draft(args.cid, from_version=args.from_version, to_version=args.to_version,
                       out=args.out, store=store, provides=args.provides,
                       client_profile=args.client_profile,
                       allow_unknown_client=args.allow_unknown_client,
                       baseline_manifest=args.baseline_manifest or args.manifest,
                       baseline_manifests=args.baseline_manifest_extra or args.manifest_extra,
                       baseline_zip_dirs=args.baseline_zip_dir or args.zip_dir,
                       base_store=args.base_store or args.store, base_version=args.base_version,
                       view_lock=args.view_lock, server_dir=args.server_dir, pathlist=args.pathlist)
