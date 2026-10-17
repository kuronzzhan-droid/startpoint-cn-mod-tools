"""Build a 221 change set from rebuilt packages, never from expected ZIPs."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from wf.deliver.changeset import member_name, sha256, write_json, validate_document
from wf.paths import REPOSITORY
from wf.view.safety import local_output, restrict_writes


def create_changeset(package_root: Path, output: Path) -> Path:
    from wf.view import character_pack
    package_root = Path(package_root).resolve()
    report = package_root.parent / "build-report.json"
    import json
    metadata = json.loads(report.read_text("utf-8"))
    if metadata.get("historical_version") != "1.4.221":
        raise ValueError("requires the explicitly rebuilt 1.4.221 historical package")
    for key in character_pack.KEYS:
        if any(step not in metadata.get(key, {}) or isinstance(metadata[key][step], dict) and "error" in metadata[key][step]
               for step in ("init", "tables", "kit", "assets", "pixel", "art", "voice")):
            raise ValueError(f"incomplete rebuild: {key}")
    # pathlib.is_file() silently returns false for these deep Windows DSL paths
    # without the extended-length prefix used by the original full replay.
    previous_root = character_pack.hw_env.ROOT
    try:
        character_pack.hw_env.ROOT = (Path("\\\\?\\" + str(package_root))
                                      if os.name == "nt" and not str(package_root).startswith("\\\\?\\")
                                      else package_root)
        tables, files, report = character_pack.collect()
        inputs = [("common", logical, raw) for logical, raw in character_pack.merged_tables(tables).items()]
    finally:
        character_pack.hw_env.ROOT = previous_root
    inputs += [(root, logical, raw) for (root, logical), (raw, _) in files.items()]
    output = local_output(output)
    output.mkdir(parents=True, exist_ok=True)
    doc = {"schema": "wf-change-set/1", "id": "halloween4-characters-1.4.221",
           "name": "(测试服) 万圣四位新角色：露迪/莫弥亚/塞里奥尔/瑞西塔尔", "description": "",
           "from_version": "1.4.220", "to_version": "1.4.221", "slug": "halloween4-characters-local",
           "created_at": "2026-10-17", "local_test_only": True, "capabilities": [], "members": [],
           "changes": [{"source": "reconstructed historical221 packages", "tables": report["tables"]}]}
    for root, logical, raw in inputs:
        name = member_name(root, logical)
        source = "payload/" + name
        target = output / source
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        before = character_pack.base_bytes(root, logical)
        doc["members"].append({"root": root, "logical_path": logical, "source": source,
                               "sha256": sha256(raw), "before_sha256": sha256(before) if before is not None else None})
    validate_document(doc, "change-set.schema.json")
    filename = output / "changeset.json"
    write_json(filename, doc)
    return filename


def main(argv=None):
    parser = argparse.ArgumentParser(description="由完整重建的 221 package 生成变更集")
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=REPOSITORY / "work/m1/deliver/halloween221-source")
    args = parser.parse_args(argv)
    restrict_writes()
    print(create_changeset(args.package_root, args.out))


if __name__ == "__main__":
    main()
