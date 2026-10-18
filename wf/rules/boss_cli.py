"""CLI input routing for saved boss snapshots or manifest-backed selectors."""
from __future__ import annotations

from pathlib import Path

from .boss import check_boss
from .catalog import result


def check_inputs(args):
    from wf.check import read_document
    context = read_document(args.context) if args.context else None
    baseline = read_document(args.baseline) if args.baseline else None
    view, reader = None, None
    files = []
    for value in args.files:
        try:
            if Path(value).is_file():
                document = read_document(value)
                if not isinstance(document, dict) or document.get("schema") != "wf-boss/1":
                    raise ValueError("wf check boss 文件必须是 wf-boss/1 快照")
                candidate = None
            else:
                if reader is None:
                    from wf.boss.reader import BossReader
                    from wf.view.manifest import ManifestView
                    view = ManifestView(args.tip, base_version=args.base_version,
                                        manifest=args.manifest, store=args.store, search_dirs=args.zip_dir,
                                        manifests=args.extra_manifest, lock=args.lock)
                    reader = BossReader(view)
                document = reader.show(str(value).replace("\\", "/"))
                candidate = view
            checks = check_boss(document, view=candidate, baseline=baseline, context=context)
        except (ValueError, OSError, TypeError, KeyError) as error:
            checks = [result("input", "问题", str(error), blocking=True)]
        files.append({"file": str(value), "results": checks})
    if view is not None:
        view.verify()
    return files
