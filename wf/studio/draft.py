"""python -m wf.studio.draft — 编辑台草稿的命令行入口（给 agent 用，和界面走同一套操作）。

每条命令输出一行 JSON；请求体与 HTTP 接口相同，结构见
``schemas/studio-draft.schema.json``（``portraitRequest`` / ``pixelRequest`` /
``voiceRequest``）。只写 ``work/studio-drafts/<角色ID>/``，不写游戏表与服务器。

例::

    python -m wf.studio.draft schema --def pixelRequest
    python -m wf.studio.draft portrait-info 139985 --form 0 --upload new.png
    python -m wf.studio.draft portrait 139985 --form 0 --template-from upload
    python -m wf.studio.draft pixel 139985 --action skill_ready --sheet run.png --grid 4x2 --duration 6
    python -m wf.studio.draft voice 139985 --line home/home_0 --audio take3.wav
    python -m wf.studio.draft show 139985
    python -m wf.studio.draft revert 139985 c-0123456789ab
    python -m wf.studio.draft save 139985
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import sys
from pathlib import Path

from .drafts import DraftError, DraftStore, schema, schema_errors, status


def _b64(path: Path) -> str:
    return base64.b64encode(Path(path).read_bytes()).decode("ascii")


def _png_b64(image) -> str:
    out = io.BytesIO()
    image.save(out, "PNG")
    return base64.b64encode(out.getvalue()).decode("ascii")


def _ops(args):
    from .operations import DraftOps
    from .source import build_source
    if args.manifest:
        from wf.view import ManifestView
        from .source import StudioSource
        if not args.tip:
            raise DraftError("--manifest 需要 --tip 指定精确来源版本")
        if args.extra_zips_file:
            raise DraftError("manifest 视图不能叠加未经清单锁定的 --extra-zips-file")
        source = StudioSource(ManifestView(f"1.4.{args.tip}", store=args.store, manifest=args.manifest,
                                          search_dirs=args.zip_dir, manifests=args.manifest_extra))
    else:
        source = build_source(tip=args.tip, extra_lists=args.extra_zips_file, use_default_chain=not args.no_chain)
    return DraftOps(source, store=DraftStore(args.drafts) if args.drafts else None)


def _load_json(path: str):
    return json.loads(Path(path).read_text("utf-8-sig"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m wf.studio.draft", description="编辑台草稿与本地交付命令行")
    parser.add_argument("--drafts", type=Path, help="草稿根目录（默认 work/studio-drafts 或 WF_STUDIO_DRAFTS）")
    parser.add_argument("--tip", type=int, help="视图 TIP 小版本号")
    parser.add_argument("--extra-zips-file", action="append", default=[], metavar="TXT")
    parser.add_argument("--no-chain", action="store_true")
    from .draft_commands import source_arguments, add_commands
    source_arguments(parser)
    sub = parser.add_subparsers(dest="command", required=True)
    add_commands(sub)

    sub.add_parser("list", help="列出有草稿的角色")
    p = sub.add_parser("show", help="输出某角色的 changeset")
    p.add_argument("cid")
    p = sub.add_parser("schema", help="输出 JSON Schema（可只取一个 $defs）")
    p.add_argument("--def", dest="ref")
    p = sub.add_parser("validate", help="按 schema 校验一个 JSON 文件")
    p.add_argument("file")
    p.add_argument("--def", dest="ref", help="$defs 名，例如 portraitRequest；省略则按整份 changeset 校验")

    p = sub.add_parser("portrait-info", help="立绘槽信息与默认裁剪模板；--upload 先上传新立绘")
    p.add_argument("cid")
    p.add_argument("--form", choices=("0", "1"), required=True)
    p.add_argument("--upload", type=Path, help="新立绘 PNG（透明背景）")
    p = sub.add_parser("portrait", help="按裁剪模板派生全部 UI 图进草稿")
    p.add_argument("cid")
    p.add_argument("--form", choices=("0", "1"))
    p.add_argument("--request", help="完整 portraitRequest JSON 文件")
    p.add_argument("--template", help="cropTemplate JSON 文件")
    p.add_argument("--template-from", choices=("upload", "current"), help="用默认模板（上传立绘 / 当前立绘）")
    p.add_argument("--source", choices=("upload", "current"), default=None)
    p.add_argument("--no-atf", action="store_true", help="不重编 skill_cutin ATF（不推荐）")

    p = sub.add_parser("pixel", help="按动作槽导入像素帧进草稿")
    p.add_argument("cid")
    p.add_argument("--request", help="完整 pixelRequest JSON 文件（帧为 base64）")
    p.add_argument("--family", choices=("pixelart", "special"), default="pixelart")
    p.add_argument("--action")
    p.add_argument("--frames", nargs="+", type=Path, help="逐帧 PNG")
    p.add_argument("--sheet", type=Path, help="精灵图，配合 --grid 切分")
    p.add_argument("--grid", help="列x行，例如 4x2")
    p.add_argument("--count", type=int, help="只取前 N 格")
    p.add_argument("--duration", type=int, default=6, help="每帧停留帧数（60fps）")
    p.add_argument("--durations", help="逗号分隔逐帧停留帧数，覆盖 --duration")
    p.add_argument("--anchor", help="统一锚点 x,y；默认脚底中心（逐帧底边中位数）")
    p.add_argument("--dry-run", action="store_true", help="只检查不写草稿")

    p = sub.add_parser("voice-lines", help="列出可替换的语音台词")
    p.add_argument("cid")
    p = sub.add_parser("voice", help="上传音频替换一条语音")
    p.add_argument("cid")
    p.add_argument("--line", required=True, help="语音路径，例如 home/home_0")
    p.add_argument("--audio", type=Path, required=True)
    p.add_argument("--loudness", type=float)

    p = sub.add_parser("revert", help="撤销草稿里的一项改动")
    p.add_argument("cid")
    p.add_argument("change")
    p = sub.add_parser("save", help="保存：整体校验 + 文件哈希复核")
    p.add_argument("cid")
    return parser


def run(args) -> dict:
    store = DraftStore(args.drafts) if args.drafts else DraftStore()
    if args.command == "list":
        return {"drafts": store.characters()}
    if args.command == "show":
        changeset = store.load(args.cid)
        return {"changeset": changeset, "status": status(changeset)}
    if args.command == "schema":
        document = schema()
        return document["$defs"][args.ref] if args.ref else document
    if args.command == "validate":
        problems = schema_errors(_load_json(args.file), args.ref)
        return {"ok": not problems, "errors": problems}
    if args.command == "revert":
        changeset = store.revert(args.cid, args.change)
        return {"status": status(changeset)}
    if args.command == "save":
        changeset = store.save(args.cid)
        return {"status": status(changeset), "savedAt": changeset["savedAt"]}
    if args.command == "build":
        from .draft_commands import run_build
        return run_build(args, store)

    ops = _ops(args)
    if args.command.startswith("ability"):
        from .draft_commands import run_ability
        return run_ability(args, ops.source, store)
    if args.command == "portrait-info":
        if args.upload:
            return ops.portrait_upload(args.cid, args.form, _b64(args.upload))
        return ops.portrait_info(args.cid, args.form)
    if args.command == "portrait":
        if args.request:
            request = _load_json(args.request)
        else:
            if not args.form:
                raise DraftError("需要 --form 或 --request")
            if args.template:
                template = _load_json(args.template)
            elif args.template_from:
                info = ops.portrait_info(args.cid, args.form)
                picked = info.get(args.template_from)
                if not picked:
                    raise DraftError(f"没有 {args.template_from} 立绘可用")
                template = picked["template"]
            else:
                raise DraftError("需要 --template 或 --template-from")
            request = {"form": args.form, "template": template,
                       "source": args.source or args.template_from or "upload", "atf": not args.no_atf}
        result = ops.portrait_save(args.cid, request)
        return _brief(result)
    if args.command == "pixel":
        if args.request:
            request = _load_json(args.request)
        else:
            from PIL import Image
            from .pixel_import import default_anchor, split_sheet
            if not args.action:
                raise DraftError("需要 --action")
            if args.sheet:
                if not args.grid or "x" not in args.grid:
                    raise DraftError("--sheet 需要 --grid 列x行")
                columns, rows = (int(v) for v in args.grid.lower().split("x", 1))
                with Image.open(args.sheet) as sheet:
                    frames = split_sheet(sheet.convert("RGBA"), columns, rows, args.count)
            elif args.frames:
                frames = [Image.open(p).convert("RGBA") for p in args.frames]
            else:
                raise DraftError("需要 --frames 或 --sheet")
            durations = ([int(v) for v in args.durations.split(",")] if args.durations
                         else [args.duration] * len(frames))
            if len(durations) != len(frames):
                raise DraftError(f"--durations 有 {len(durations)} 个，帧有 {len(frames)} 个")
            anchor = [float(v) for v in args.anchor.split(",")] if args.anchor else default_anchor(frames)
            request = {"family": args.family, "action": args.action, "dryRun": args.dry_run,
                       "frames": [{"png": _png_b64(f), "duration": d, "anchor": anchor}
                                  for f, d in zip(frames, durations)],
                       "origin": {"mode": "sheet" if args.sheet else "frames", "grid": args.grid or ""}}
        result = ops.pixel_save(args.cid, request)
        return result if result.get("dryRun") else _brief(result)
    if args.command == "voice-lines":
        return ops.voice_lines(args.cid)
    if args.command == "voice":
        request = {"voice": args.line, "audio": _b64(args.audio), "filename": args.audio.name}
        if args.loudness is not None:
            request["loudness"] = args.loudness
        return _brief(ops.voice_save(args.cid, request))
    raise DraftError(f"未知命令 {args.command}")


def _brief(result: dict) -> dict:
    change = result["change"]
    return {"status": result["status"], "change": {
        "id": change["id"], "kind": change["kind"], "title": change["title"],
        "files": [{"logical": f["logical"], "draft": f["draft"], "sha256": f["sha256"]} for f in change["files"]],
        "pending": change["pending"], "checks": change["checks"]}}


def main(argv=None) -> int:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    try:
        result = run(args)
    except (DraftError, ValueError, OSError, KeyError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    ok = not (isinstance(result, dict) and result.get("ok") is False)
    print(json.dumps({"ok": ok, "result": result}, ensure_ascii=False, default=str))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
