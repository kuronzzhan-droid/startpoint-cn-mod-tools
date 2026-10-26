#!/usr/bin/env python3
"""Bind Inaho's existing skill Fever points to her native private growth state."""

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
from wf_dsl_sig import COMMANDS

PACKAGE = Path(('${WF_ROOT}/startpoint-cn/work/character_packs/inaho-fever-growth-20260906/fox_oracle_autumn/package'.replace("${WF_ROOT}", str(root_path()))))
STATE_ID = 1399952
SEED = 4200
FLOAT_ID = 1399952
# The unique-condition table caps S at 1,000,000,000. This binding ceiling must not
# impose an additional limit on S / SEED.
BIND_CEILING = 1_000_000.0
LOGICALS = tuple("battle/action/skill/action/rare5/fox_oracle_autumn$"
                 f"fox_oracle_autumn_{level}.action.dsl.amf3.deflate" for level in (1, 2))
SOURCE_TREES = {
    1: "ac54e61a3ebeed0c18610908bdae0484e99028cceb7c63a1f8b4bf71247ba76b",
    2: "843ee9184b0592faf4493badabeb316eaef03dc43b40653b2d06a21226e57428",
}
BASE_POINTS = {1: (35, 35), 2: (45, 50)}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def tree_hash(tree):
    return sha(json.dumps(tree, ensure_ascii=True, sort_keys=True,
                          separators=(",", ":")).encode())


def original_point(level):
    minimum, maximum = BASE_POINTS[level]
    return ["Command", ["AddFeverPoint", [{"min": minimum, "max": maximum}]]]


def growth_point(level):
    grown = original_point(level)
    grown[1][1][0]["mul"] = FLOAT_ID
    # Both branches run synchronously in the original command position. The
    # missing-state branch preserves skills before ability 1 has been learned.
    bind = ["Command", ["BindConditionAccumulationVariable", -17, FLOAT_ID,
                         ["DCUnique", STATE_ID], SEED, BIND_CEILING]]
    return ["Command", ["ConditionalsConditionExist", -17, ["DCUnique", STATE_ID],
                         ["Block", [bind, grown]], ["Block", [original_point(level)]]]]


def revise_tree(source, level):
    if level not in SOURCE_TREES:
        raise ValueError("unknown skill level")
    tree = deepcopy(source)
    try:
        block = tree[11]
        if block[0] != "Block":
            raise ValueError("skill must retain its existing root Block")
        current = block[1][3]
    except (IndexError, TypeError) as exc:
        raise ValueError("unexpected Inaho skill structure") from exc
    expected = growth_point(level)
    if current == expected:
        block[1][3] = original_point(level)
    elif current != original_point(level):
        raise ValueError("unexpected Fever command; refusing to overwrite")
    if tree_hash(tree) != SOURCE_TREES[level]:
        raise ValueError("skill differs outside the assigned Fever expression")
    block[1][3] = expected
    for command in wf_dsl.iter_dsl_commands(tree):
        if command[0] not in COMMANDS or len(command) != len(COMMANDS[command[0]]) + 1:
            raise ValueError(f"invalid native command signature: {command[0]}")
    if wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"] != tree:
        raise ValueError("AMF3 semantic roundtrip failed")
    return tree


def _package(path):
    path = Path(path)
    if not (path / "manifest.json").is_file():
        path /= "package"
    package = path.resolve(strict=True)
    if package != PACKAGE.resolve(strict=True):
        raise ValueError("only the assigned isolated Inaho growth clone is accepted")
    manifest_path = (package / "manifest.json").resolve(strict=True)
    if not manifest_path.is_relative_to(package):
        raise ValueError("manifest escapes package")
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    if (manifest.get("character_id"), manifest.get("code_name")) != (139995, "fox_oracle_autumn"):
        raise ValueError("package identity must be Inaho 139995")
    return package, manifest_bytes


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
    package, manifest_bytes = _package(workspace)
    outputs, files = [], []
    for level, logical in enumerate(LOGICALS, 1):
        path = (package / "roots/common" / logical).resolve(strict=True)
        if not path.is_relative_to(package / "roots/common"):
            raise ValueError("skill path escapes package common root")
        raw = path.read_bytes()
        source = wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]
        fixed = revise_tree(source, level)
        encoded = raw
        if source != fixed:
            encoder = zlib.compressobj(level=9, wbits=-15)
            encoded = encoder.compress(wf_dsl.encode_amf3(fixed)) + encoder.flush()
        if wf_dsl.parse_dsl(zlib.decompress(encoded, -15))["tree"] != fixed:
            raise ValueError("compressed skill roundtrip failed")
        outputs.append((path, raw, encoded))
        files.append({"root": "common", "logical_path": logical,
                      "old_sha256": sha(raw), "new_sha256": sha(encoded),
                      "old_size": len(raw), "size": len(encoded), "changed": raw != encoded,
                      "old_tree_sha256": tree_hash(source), "new_tree_sha256": tree_hash(fixed),
                      "changed_table_keys": [], "new_table_keys": [], "roundtrip": True})
    # All inputs must pass before either output is written. Manifest ownership
    # remains with the character-flow publisher.
    if not dry_run:
        for path, old, new in outputs:
            if path.read_bytes() != old:
                raise ValueError("skill changed during planning")
            if old != new:
                _atomic(path, new)
    if (package / "manifest.json").read_bytes() != manifest_bytes:
        raise ValueError("manifest changed during skill revision")
    return {"dry_run": dry_run, "files": files, "manifest_updated": False,
            "state_id": STATE_ID, "seed": SEED, "casting_subject": -17,
            "float_variable": FLOAT_ID, "absent_state_fallback": "original skill points",
            "replacement_path": [11, 1, 3], "all_other_tree_nodes_unchanged": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=PACKAGE)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report_path = args.report.resolve() if args.report else None
    if report_path and "codex_out" not in {part.lower() for part in report_path.parts}:
        raise ValueError("report must stay in codex_out")
    result = revise(args.workspace, dry_run=not args.apply)
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        _atomic(report_path, payload.encode())
    print(payload)


if __name__ == "__main__":
    main()
