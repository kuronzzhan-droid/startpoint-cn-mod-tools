"""python -m wf.studio — start the read-only 编辑台 backend on 127.0.0.1:8790."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .server import DEFAULT_STATIC, StudioApp, serve
from .source import build_source


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m wf.studio", description="编辑台只读后端")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8790)
    parser.add_argument("--tip", type=int, help="视图 TIP 小版本号（默认取 kulo active 中最新的补丁边）")
    parser.add_argument("--extra-zip", action="append", default=[], metavar="ZIP",
                        help="在 active 链之后按顺序叠加的补丁 ZIP，可重复")
    parser.add_argument("--extra-zips-file", action="append", default=[], metavar="TXT",
                        help="每行一个 ZIP 路径的清单文件，可重复；按出现顺序叠加")
    parser.add_argument("--static", type=Path, default=DEFAULT_STATIC, help="前端构建目录")
    parser.add_argument("--warm", action="store_true", help="启动时预先加载角色列表")
    args = parser.parse_args(argv)

    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    source = build_source(tip=args.tip, extra_zips=args.extra_zip, extra_lists=args.extra_zips_file)
    app = StudioApp(source)
    if args.warm:
        app.character_list()
    info = source.describe()
    server = serve(app, host=args.host, port=args.port, static_root=args.static)
    print(f"编辑台（只读）: http://{args.host}:{args.port}/  视图 {info['version']}  "
          f"ZIP {info['zipCount']} 个，额外叠加 {len(info['extraZips'])} 个", flush=True)
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
