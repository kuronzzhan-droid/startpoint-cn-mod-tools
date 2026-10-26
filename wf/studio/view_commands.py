"""Shared view selection and store-export commands for the studio CLI."""
from pathlib import Path


def source_from_args(args):
    from .source import build_source
    return build_source(tip=getattr(args, "tip", None), manifest=getattr(args, "manifest", None),
                        view_name=getattr(args, "view_name", None), store=getattr(args, "store", None),
                        base_version=getattr(args, "view_base_version", None),
                        manifests=getattr(args, "manifest_extra", None),
                        extra_zips=getattr(args, "extra_zip", ()),
                        extra_lists=getattr(args, "extra_zips_file", ()),
                        search_dirs=getattr(args, "zip_dir", None),
                        use_default_chain=not getattr(args, "no_chain", False))


def add_commands(sub):
    parser = sub.add_parser("export-store", help="导出当前视图供构建器读取（新目录）")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--copy", action="store_true", help="复制基线文件；默认同盘硬链接")


def run(args, source=None):
    from wf.view.export import export_store
    source = source if source is not None else source_from_args(args)
    return {**export_store(source.view, args.out, copy=args.copy), "version": source.version}
