"""Standalone, read-only verifier copied into every delivery."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile


def verify(assertions, *, phase, manifest, active=None, store=None, server_dir=None):
    errors = []
    if active is None and store is None and any(x["kind"] == "client" for x in assertions["files"]):
        errors.append("client assertions require an active archive directory or a base store")
    expected_version = assertions["from_version" if phase == "pre" else "to_version"]
    if manifest.get("cdn_version") != expected_version:
        errors.append(f"version: expected {expected_version}, got {manifest.get('cdn_version')}")
    index = {}
    if active is not None:
        names = []
        for patch in manifest.get("patches", []):
            if patch.get("type") == "patch" and patch.get("enabled") is True:
                names.extend(patch.get("chain") or [patch.get("archive")])
        def archive_order(name):
            match = re.fullmatch(r"pinball-(\d+\.\d+\.\d+)-(\d+\.\d+\.\d+)-(\d+)-.+\.zip", str(name))
            return (tuple(map(int, match[1].split("."))), tuple(map(int, match[2].split("."))), int(match[3])) if match else ((), (), 0)
        for name in sorted(names, key=archive_order):
            if not isinstance(name, str) or Path(name).name != name or "\\" in name or ":" in name:
                errors.append(f"unsafe archive name: {name!r}")
                continue
            archive = Path(active) / name
            if not archive.is_file():
                errors.append(f"missing archive: {name}")
                continue
            with zipfile.ZipFile(archive) as zf:
                for member in zf.namelist():
                    if re.fullmatch(r"[0-9a-f]{2}/[0-9a-f]{38}", member):
                        index["production/upload/" + member] = (archive, member)
                    elif member.startswith("production/"):
                        index[member] = (archive, member)
    for item in assertions["files"]:
        expected = item["before_sha256" if phase == "pre" else "sha256"]
        raw = None
        if item["kind"] == "client":
            member = item["member"]
            if member in index:
                archive, name = index[member]
                with zipfile.ZipFile(archive) as zf:
                    raw = zf.read(name)
            elif store is not None:
                root = Path(store)
                if root.name == "upload":
                    root = root.parent
                filename = root / member.removeprefix("production/")
                if filename.is_file():
                    raw = filename.read_bytes()
            label = member
        else:
            label = item["target"]
            if server_dir is None:
                errors.append(f"server root required for {label}")
                continue
            filename = Path(server_dir) / label
            if filename.is_file():
                raw = filename.read_bytes()
        actual = hashlib.sha256(raw).hexdigest() if raw is not None else None
        if actual != expected:
            errors.append(f"{label}: expected {expected}, got {actual}")
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description="只读核验交付前置/后置版本和成员 SHA-256")
    parser.add_argument("--phase", choices=("pre", "post"), required=True)
    parser.add_argument("--assertions", type=Path, default=Path(__file__).with_name("assert-box.json"))
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--active", type=Path)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--server-dir", type=Path)
    args = parser.parse_args(argv)
    errors = verify(json.loads(args.assertions.read_text("utf-8")), phase=args.phase,
                    manifest=json.loads(args.manifest.read_text("utf-8")), active=args.active,
                    store=args.store, server_dir=args.server_dir)
    print(json.dumps({"status": "问题" if errors else "满足", "errors": errors}, ensure_ascii=False))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
