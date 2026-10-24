#!/usr/bin/env python3
"""Fix only Gerald's two published self-Flying subjects in an isolated package."""

from wf.paths import root_path
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import zlib

import wf_dsl

PACKAGE = Path(('${WF_ROOT}/startpoint-cn/work/character_packs/gerald-hotfix-20260906/unicorn_lancer_rose/package'.replace("${WF_ROOT}", str(root_path()))))
LOGICALS = tuple("battle/action/skill/action/rare5/unicorn_lancer_rose$"
                 f"unicorn_lancer_rose_{level}.action.dsl.amf3.deflate" for level in (1, 2))
TREE_HASHES = {
    1: ("583ecf37fcff7d25fe85b46404130546b447c767bee0b8f289abb199aed886b9",
        "2431d23bd2379d10ab97d6be303e289dd32361f05ca92c5db0a33eec1a4171a0"),
    2: ("0c19ce4f462b99eda65728f4e4ee9b59af728c90fbc689408a1f254993f49332",
        "64d2fc8c0c601ffc042db8f62209d4e00b9212ba34289786946e36bc86bbad68"),
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def tree_hash(tree):
    return sha(json.dumps(tree, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode())


def fix_tree(source, level):
    if level not in TREE_HASHES or tree_hash(source) not in TREE_HASHES[level]:
        raise ValueError("unknown Gerald 1.4.768 or fixed skill input")
    tree = deepcopy(source)
    nodes = [node for node in wf_dsl.iter_dsl_commands(tree, "CreateCondition")
             if any(kind[0] == "ACFlying" for kind in node[2])]
    if len(nodes) != 1 or nodes[0][1] not in (-18, -17):
        raise ValueError("expected exactly one known self-Flying condition")
    nodes[0][1] = -17
    if tree_hash(tree) != TREE_HASHES[level][1]:
        raise ValueError("unexpected extra skill change")
    if wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"] != tree:
        raise ValueError("skill AMF3 roundtrip failed")
    return tree


def _package(path):
    path = Path(path)
    if not (path / "manifest.json").is_file():
        path /= "package"
    package = path.resolve(strict=True)
    if package != PACKAGE:
        parts = {p.lower() for p in package.parts}
        if "codex_out" not in parts or parts & {"pkgarchive", "character_packs", "store", "asset-patch"}:
            raise ValueError("only the assigned hotfix clone or isolated codex_out fixture is accepted")
    manifest_path = (package / "manifest.json").resolve(strict=True)
    if not manifest_path.is_relative_to(package):
        raise ValueError("manifest escapes package")
    manifest = json.loads(manifest_path.read_bytes())
    if (manifest.get("character_id"), manifest.get("code_name")) != (129992, "unicorn_lancer_rose"):
        raise ValueError("package identity must be Gerald 129992")
    return package


def _atomic(path, raw):
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(raw)
    try:
        os.replace(temporary, path)
        if path.read_bytes() != raw:
            raise OSError("write readback failed")
    finally:
        temporary.unlink(missing_ok=True)


def revise(workspace=PACKAGE, *, dry_run=True):
    package = _package(workspace)
    outputs, report = [], []
    for level, logical in enumerate(LOGICALS, 1):
        path = (package / "roots/common" / logical).resolve(strict=True)
        if not path.is_relative_to(package):
            raise ValueError("skill input escapes package")
        raw = path.read_bytes()
        source = wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]
        fixed = fix_tree(source, level)
        compressed = raw
        if source != fixed:
            encoder = zlib.compressobj(level=9, wbits=-15)
            compressed = encoder.compress(wf_dsl.encode_amf3(fixed)) + encoder.flush()
        outputs.append((path, compressed))
        report.append({"root": "common", "logical_path": logical, "old_sha256": sha(raw),
                       "new_sha256": sha(compressed), "size": len(compressed),
                       "changed": raw != compressed, "changed_table_keys": [], "new_table_keys": []})
    # Both versions must pass before writing either; the publisher owns manifest.
    if not dry_run:
        for path, raw in outputs:
            if path.read_bytes() != raw:
                _atomic(path, raw)
    return {"dry_run": dry_run, "files": report, "manifest_updated": False,
            "self_flying_subject": -17, "duration_frames": 1200}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=PACKAGE)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = args.report.resolve() if args.report else None
    if report and "codex_out" not in {part.lower() for part in report.parts}:
        raise ValueError("report must stay in codex_out")
    result = revise(args.workspace, dry_run=not args.apply)
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if report:
        report.parent.mkdir(parents=True, exist_ok=True)
        _atomic(report, payload.encode())
    print(payload)


if __name__ == "__main__":
    main()
