"""python -m wf.studio — start the 编辑台 backend on 127.0.0.1:8790 (reads the view, writes only drafts)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if argv[:1] == ["doctor"]:
        from .doctor import main as doctor_main
        return doctor_main(argv[1:])
    from .server import DEFAULT_STATIC, StudioApp, serve
    from .source import build_source
    parser = argparse.ArgumentParser(prog="python -m wf.studio", description="编辑台后端：读分层视图，只写草稿 work/studio-drafts")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8790)
    parser.add_argument("--tip", help="manifest 链终点（175 或 1.4.175）；默认清单最新启用版本")
    parser.add_argument("--view", dest="view_name", help="profiles/local.json 的命名视图")
    parser.add_argument("--store", type=Path, help="只读基线 upload store")
    parser.add_argument("--base-version", help="基线 store 版本；默认 1.4.131 或命名视图配置")
    parser.add_argument("--manifest", type=Path, help="独立 manifest，可与 --zip-dir 配合")
    parser.add_argument("--manifest-extra", type=Path, action="append")
    parser.add_argument("--extra-zip", action="append", default=[], metavar="ZIP",
                        help="在 active 链之后按顺序叠加的补丁 ZIP，可重复")
    parser.add_argument("--extra-zips-file", action="append", default=[], metavar="TXT",
                        help="每行一个 ZIP 路径的清单文件，可重复；按出现顺序叠加")
    parser.add_argument("--chain-manifest", type=Path, metavar="JSON",
                        help="补丁链清单 manifest.json（兼容旧参数名）；从基线叠到 --tip"
                             "（默认读 profile 的 paths.studio_chain_manifest）")
    parser.add_argument("--zip-dir", action="append", type=Path, metavar="DIR",
                        help="查找补丁 ZIP 的目录（可重复；默认 profile 的 studio_zip_dirs，否则 wf_root 下 rel* 与 out）")
    parser.add_argument("--no-chain", action="store_true", help="不按清单自动叠加，只用 active 与 --extra-zip")
    parser.add_argument("--static", type=Path, default=DEFAULT_STATIC, help="前端构建目录")
    parser.add_argument("--server-dir", type=Path, help="文本编辑所需的只读服务端镜像根目录")
    parser.add_argument("--provides", type=Path, metavar="JSON",
                        help="生成交付时默认使用的客户端能力清单（wf apk provides 的输出）")
    parser.add_argument("--screenshots-dir", action="append", type=Path, default=[], metavar="DIR",
                        help="实测截图白名单目录（可重复；与 profile 的 paths.studio_screenshots 合并）")
    parser.add_argument("--warm", action="store_true", help="启动时预先加载角色列表（同步）")
    parser.add_argument("--no-prewarm", action="store_true", help="不在后台预热词条/文案缓存")
    parser.add_argument("--allow-origin", action="append", default=[], metavar="URL",
                        help="额外允许写入的 Origin（例如 Vite 开发服务器 http://127.0.0.1:5173），可重复")
    args = parser.parse_args(argv)

    from .config import server_directory
    from .doctor import run_doctor, summary
    server_dir = server_directory(args.server_dir)
    print(summary(run_doctor(fast=True, server_dir=server_dir, static=args.static)), flush=True)

    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    source = build_source(tip=args.tip, extra_zips=args.extra_zip, extra_lists=args.extra_zips_file,
                          chain_manifest=args.chain_manifest, search_dirs=args.zip_dir,
                          use_default_chain=not args.no_chain, manifest=args.manifest, store=args.store,
                          base_version=args.base_version, manifests=args.manifest_extra, view_name=args.view_name)
    if args.provides is not None and not args.provides.is_file():
        parser.error(f"--provides 文件不存在：{args.provides}")
    from .device_result import configured_screenshot_dirs
    app = StudioApp(source, server_dir=server_dir, default_provides=args.provides,
                    screenshot_dirs=configured_screenshot_dirs(args.screenshots_dir))
    app.static_root = args.static
    if args.warm:
        app.character_list()
    if not args.no_prewarm:
        import threading

        def prewarm():
            try:
                app.prewarm()
            except Exception as exc:  # noqa: BLE001 - a cold cache is only slower, never wrong
                print(f"预热缓存失败（不影响使用，首次请求会慢一些）：{type(exc).__name__}: {exc}", flush=True)
        threading.Thread(target=prewarm, name="studio-prewarm", daemon=True).start()
    info = source.describe()
    if args.host not in ("127.0.0.1", "localhost", "::1"):
        parser.error("编辑台只监听本机回环地址")
    server = serve(app, host=args.host, port=args.port, static_root=args.static, extra_origins=args.allow_origin)
    session = server.guard.write_session(app.ops.store.root, args.host)
    print(f"编辑台（草稿可写）: http://{args.host}:{args.port}/  视图 {info['version']}  "
          f"ZIP {info['zipCount']} 个，额外叠加 {len(info['extraZips'])} 个", flush=True)
    if info.get("chain"):
        chain = info["chain"]
        print(f"补丁链清单 {chain['manifest']}：找到 {chain['resolved']} 个 ZIP，缺 {len(chain['missing'])} 个", flush=True)
        for item in chain["missing"]:
            print(f"  缺少 {item['version']} {item['name']}", flush=True)
    print(f"写入令牌已写到 {session}（agent 用 X-WF-Studio-Token 头调用 POST 接口）", flush=True)
    if not (args.static / "index.html").is_file():
        print(f"提示：前端未构建（{args.static}），请在 studio/ 下运行 npm run build", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
