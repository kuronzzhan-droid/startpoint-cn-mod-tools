"""Read delivery metadata and ZIP bytes without extracting or modifying them."""
from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

from wf.view.chain import ARCHIVE, archive_names

from .drafts import DraftError
from .rehearsal_io import inside, read_json


def digest(filename):
    with Path(filename).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load_inputs(folder, zips=None):
    metadata = []
    delivery = inside(folder, "delivery-manifest.json")
    if delivery.is_file():
        doc = read_json(delivery)
        if not isinstance(doc, dict):
            raise DraftError("delivery-manifest 必须是对象")
        metadata.append(doc)
        legacy = doc.get("legacy_manifest")
        entries = [inside(folder, legacy)] if legacy else list(folder.glob("manifest-entry-*.json"))
    else:
        entries = list(folder.glob("manifest-entry-*.json"))
    if len(entries) > 1:
        raise DraftError("交付目录含多条 manifest 条目，无法唯一选择版本边")
    entry = read_json(inside(folder, entries[0].name)) if entries else {}
    if not isinstance(entry, dict):
        raise DraftError("manifest 条目必须是对象")
    metadata.append(entry)
    if zips is not None:
        paths = [Path(p).resolve() for p in zips]
    elif delivery.is_file():
        paths = [inside(folder, a["name"]) for a in doc.get("archives", [])]
    elif entry:
        paths = [inside(folder, n) for n in archive_names(entry)]
    else:
        paths = sorted(folder.glob("*.zip"))
    if not paths:
        raise DraftError("没有可预演的分包 ZIP")
    parsed = [ARCHIVE.fullmatch(p.name) for p in paths]
    if any(m is None for m in parsed):
        raise DraftError("分包命名必须是 pinball-<from>-<to>-<序号>-<名字>.zip")
    edges = {m.group(1, 2) for m in parsed}
    if len(edges) != 1:
        raise DraftError("ZIP 列表必须属于同一条版本边")
    start, end = edges.pop()
    names = archive_names({"depends_on": start, "version": end, "chain": [p.name for p in paths]})
    by_name = {p.name: p for p in paths}
    paths = [by_name[n] for n in names]
    for doc in metadata:
        if (doc.get("from_version", doc.get("depends_on", start)) != start
                or doc.get("to_version", doc.get("version", end)) != end):
            raise DraftError("交付元数据版本与 ZIP 文件名不一致")
        declared = doc.get("chain")
        if declared is not None and set(declared) != set(names):
            raise DraftError("ZIP 集合与 manifest chain 不一致")
        if "archives" in doc and {a["name"] for a in doc["archives"]} != set(names):
            raise DraftError("ZIP 集合与交付 archives 不一致")
    return paths, start, end, entry, metadata


def inspect_archives(paths, metadata):
    records, all_members = [], set()
    for path in paths:
        before = digest(path)
        with zipfile.ZipFile(path) as archive:
            members, hashes = [], {}
            for info in archive.infolist():
                if info.is_dir():
                    continue
                name = info.filename
                # No extraction occurs, but unsafe or duplicate members are invalid evidence.
                inside(Path.cwd(), name)
                if name in all_members:
                    raise DraftError(f"ZIP 成员重复（含跨分包）：{name}")
                all_members.add(name)
                members.append(name)
                hashes[name] = hashlib.sha256(archive.read(info)).hexdigest()
        if not members:
            raise DraftError(f"空 ZIP 分包：{path.name}")
        record = {"name": path.name, "size": path.stat().st_size, "sha256": before,
                  "members": len(members), "files": sorted(members), "member_sha256": hashes}
        if digest(path) != before:
            raise DraftError(f"读取期间 ZIP 变化：{path.name}")
        sidecar = path.with_suffix(".integrity.json")
        evidence = [read_json(sidecar)] if sidecar.is_file() else []
        for doc in metadata:
            evidence.extend(a for a in doc.get("archives", doc.get("archive_integrity", []))
                            if a.get("name") == path.name)
        for expected in evidence:
            for key in ("size", "sha256", "members"):
                if key in expected and expected[key] != record[key]:
                    raise DraftError(f"分包 {path.name} 的 {key} 与交付证据不一致")
            if "files" in expected and sorted(expected["files"]) != record["files"]:
                raise DraftError(f"分包 {path.name} 的 files 不一致")
            if "member_sha256" in expected and expected["member_sha256"] != hashes:
                raise DraftError(f"分包 {path.name} 的 member_sha256 不一致")
            logical = expected.get("logical", expected.get("logical_paths"))
            if isinstance(logical, dict):
                record["logical"] = {k: v for k, v in logical.items() if k in hashes}
        records.append(record)
    return records
