"""Local mechanism matrix CLI backed by the same manifest chain as wf view."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

from wf.paths import REPOSITORY, path
from wf.view.safety import local_output, restrict_writes


def json_value(value):
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(type(value).__name__)


def run_scan(args):
    from wf.view import ManifestView
    from .registry import load_registry
    from .scan import scan_characters
    from .scan_source import ScanSource
    from .scan_capabilities import compare_records, project_character
    from .scan_output import write_capability_matrix, write_matrix

    output = local_output(args.output)
    source = ScanSource(ManifestView(args.tip, store=args.store, manifest=args.manifest,
                                    search_dirs=args.zip_dir, lock=args.lock), args.official_cdn)
    server_assets = args.server_assets or path("kulo", "assets")
    names_raw = args.names.read_bytes()
    names = json.loads(names_raw)
    if not isinstance(names, dict):
        raise ValueError("C-layer names must be an object")
    for cid, entry in names.items():
        if cid.startswith("_"):
            continue
        if not isinstance(entry, dict) or any(
                not isinstance(entry.get(field, []), list) or
                any(not isinstance(item, str) for item in entry.get(field, []))
                for field in ("mech", "docs")):
            raise ValueError(f"invalid C-layer entry: {cid}")
    raw = scan_characters(source, server_assets)
    # Freeze sets before comparison and emitting either matrix format.
    raw = json.loads(json.dumps(raw, ensure_ascii=False, default=json_value))
    registry = load_registry()
    rows = [project_character(r, names, registry) for r in raw]
    capability_ids = sorted({c for r in rows for c in r["capabilities"]})
    evidence = source.evidence()
    comparison = None
    if args.reference:
        ref_raw = args.reference.read_bytes()
        comparison = compare_records(raw, json.loads(ref_raw))
        comparison["reference_sha256"] = hashlib.sha256(ref_raw).hexdigest()
    lock = source.verify()
    if args.names.read_bytes() != names_raw:
        raise ValueError("C-layer names changed while scanning")
    document = {"schema": "wf-capability-matrix/1", "tip": args.tip, "character_count": len(rows),
                "capability_ids": capability_ids, "characters": rows,
                "evidence": evidence, "names_sha256": hashlib.sha256(names_raw).hexdigest(),
                "scan_complete": not evidence["missing_dsl"] and not any(r["unregistered_mechanisms"] for r in rows),
                "scope": "非官方角色；官方身份与四张战斗表比较；服务端输入为显式当前快照，非历史回放"}
    output.mkdir(parents=True, exist_ok=True)
    for name, value in (("matrix.json", document), ("scan_raw.json", raw), ("view.lock.json", lock),
                        ("comparison.json", comparison)):
        if value is not None:
            local_output(output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", "utf-8")
    write_capability_matrix(rows, capability_ids, local_output(output / "matrix.csv"))
    write_matrix(raw, names, local_output(output / "角色机制矩阵.csv"))
    print(json.dumps({"tip": args.tip, "characters": len(rows), "capabilities": len(capability_ids),
                      "zip_count": len(source.view.zips), "output": str(output),
                      "scan_complete": document["scan_complete"],
                      "reference_differences": comparison["difference_count"] if comparison else None}, ensure_ascii=False))
    return 0 if document["scan_complete"] else 1


def main(argv=None):
    parser = argparse.ArgumentParser(prog="wf caps")
    commands = parser.add_subparsers(dest="command", required=True)
    scan = commands.add_parser("scan", help="导出角色 × 已注册能力 CSV/JSON")
    scan.add_argument("--tip", required=True)
    scan.add_argument("--output", "--out", type=Path, required=True)
    scan.add_argument("--store", type=Path)
    scan.add_argument("--manifest", type=Path)
    scan.add_argument("--zip-dir", type=Path, action="append")
    scan.add_argument("--lock", type=Path)
    scan.add_argument("--official-cdn", type=Path)
    scan.add_argument("--server-assets", "--kulo-assets", type=Path)
    scan.add_argument("--names", type=Path, default=REPOSITORY / "data/layer_c_names.json")
    scan.add_argument("--reference", type=Path, help="现有 scan_raw.json；逐字段比较并写 comparison.json")
    args = parser.parse_args(argv)
    try:
        restrict_writes()
        return run_scan(args)
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        print(f"wf caps: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
