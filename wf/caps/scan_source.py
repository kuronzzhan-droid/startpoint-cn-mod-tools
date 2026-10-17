"""Read-only scanner source; no studio dependency and no external cache writes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import zlib

import wf_dsl
import wf_mod_tool as core
from wf_enhancement_policy import OfficialBaseline
from wf.paths import configured_path, path
from wf.view.base149 import member
from wf_wiki_catalog_source import TABLES


def decode_table(logical, raw, nested=False):
    if nested:
        outer = core.read_orderedmap_raw_rows_from_bytes(raw, logical)
        return {k: {lv: core.read_csv_lines(r) for lv, r in
                    core.read_orderedmap_file_from_bytes(v).items()}
                for k, v in zip(outer.keys, outer.rows)}
    return {k: core.read_csv_lines(v) for k, v in
            core.read_orderedmap_file_from_bytes(raw).items()}


def edge_versions(name):
    match = re.match(r"^pinball-1\.4\.(\d+)-1\.4\.(\d+)-", name)
    return tuple(map(int, match.groups())) if match else None


class ScanSource:
    def __init__(self, view, official_root=None):
        self.view = view
        root = official_root or configured_path("official_cdn") or path("kulo", ".cdn/cn")
        self.baseline = OfficialBaseline(Path(root), write_cache=False)
        self._tables, self._trees, self._server = {}, {}, {}
        self.official_reads, self.missing_dsl = {}, set()

    def table(self, name, official=False):
        logical = TABLES.get(name, name)
        key = (logical, official)
        if key not in self._tables:
            if official:
                digest = core.sha1_path(logical)
                raw = self.baseline.get("common", digest[:2] + "/" + digest[2:])
                self.official_reads[logical] = hashlib.sha256(raw).hexdigest() if raw else None
            else:
                raw = self.view.read_raw(logical)[0]
            nested = logical in (TABLES["skill"], TABLES["switched"])
            self._tables[key] = decode_table(logical, raw, nested) if raw else {}
        return self._tables[key]

    def tree(self, logical):
        if logical not in self._trees:
            try:
                raw = self.view.read_raw(logical)[0]
            except FileNotFoundError:
                raw = None
            self._trees[logical] = wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"] if raw else None
        return self._trees[logical]

    def locate(self, logical):
        archive = self.view.index.get(member(logical))
        if archive:
            return archive.name
        rel = member(logical).removeprefix("production/upload/")
        return "store131" if (self.view.store / rel).is_file() else None

    def server_table(self, filename):
        filename = Path(filename)
        raw = filename.read_bytes()  # Missing server policy cannot mean an empty whitelist.
        self._server[filename] = raw
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise ValueError(f"server mechanism table must be an object: {filename.name}")
        return result

    def characters(self):
        official = self.table("character", True)
        if not official:
            raise ValueError("official character baseline is empty; cannot classify mechanisms")
        result = []
        for cid, rows in self.table("character").items():
            row = rows[0]
            origin = "new" if cid not in official else "official"
            if origin == "official" and row != official[cid][0]:
                origin = "modified"
            for name, keys in (("ability", row[19:25]), ("leader", row[17:18]), ("skill", row[8:9])):
                live, base = self.table(name), self.table(name, True)
                if origin == "official" and any(live.get(k) != base.get(k) for k in keys if k not in ("", "(None)")):
                    origin = "modified"
            if origin == "official":
                continue
            text = self.table("text").get(cid, [[]])[0]
            result.append({"id": cid, "name": text[0] if text else row[0],
                           "title": text[3] if len(text) > 3 else "", "origin": origin})
        return sorted(result, key=lambda item: (not item["id"].isdigit(), int(item["id"]) if item["id"].isdigit() else item["id"]))

    def verify(self):
        for filename, raw in self._server.items():
            if filename.read_bytes() != raw:
                raise ValueError(f"server mechanism input changed: {filename.name}")
        for logical, expected in self.official_reads.items():
            digest = core.sha1_path(logical)
            raw = self.baseline.get("common", digest[:2] + "/" + digest[2:])
            actual = hashlib.sha256(raw).hexdigest() if raw else None
            if actual != expected:
                raise ValueError(f"official mechanism input changed: {logical}")
        return self.view.verify()

    def evidence(self):
        return {"official_tail": self.baseline.official_tail,
                "official_tables": dict(sorted(self.official_reads.items())),
                "server_inputs": {str(p): hashlib.sha256(raw).hexdigest()
                                  for p, raw in self._server.items()},
                "missing_dsl": sorted(self.missing_dsl)}
def provenance(src, core, cids, T) -> dict:
    """逐补丁边回放 character/ability/leader/skill 四表,记下每个角色首次出现与其行被改写的版本。

    store131 视为起点(≤1.4.131 的共用链内容,含官方与 1.4.55–130 的 MOD)。"""
    import zipfile
    from wf.view.base149 import member
    view = src.view
    names = {"character": False, "ability": False, "leader": False, "skill": True}
    snap = {}
    for n, nested in names.items():
        lg = TABLES[n]
        root, rel = member(lg).removeprefix("production/").split("/", 1)
        f = view.store / rel
        snap[n] = decode_table(lg, view.read_store_member(member(lg)), nested) if f.is_file() else {}
    keys = {}
    for cid in cids:
        row = T["character"][cid][0]
        keys[cid] = {"character": [cid], "ability": [k for k in row[19:25] if k and k != "(None)"],
                     "leader": [row[17]] if len(row) > 17 else [], "skill": [row[8]]}
    result = {cid: (["≤1.4.131"] if cid in snap["character"] else []) for cid in cids}
    for archive in view.zips:
        ver = edge_versions(Path(archive).name)
        label = f"1.4.{ver[1]}" if ver else Path(archive).stem
        tag = re.sub(r"^pinball-[\d.]+-[\d.]+-\d+-", "", Path(archive).stem).removesuffix("-local")
        with zipfile.ZipFile(archive) as z:
            present = set(z.namelist())
            new = {}
            for n, nested in names.items():
                m = member(TABLES[n])
                if m in present:
                    new[n] = decode_table(TABLES[n], z.read(m), nested)
        if not new:
            continue
        for cid in cids:
            touched = False
            for n, table in new.items():
                for k in keys[cid][n]:
                    if table.get(k) != snap[n].get(k):
                        touched = True
            if touched:
                stamp = f"{label}({tag})"
                if stamp not in result[cid]:
                    result[cid].append(stamp)
        snap.update(new)
    return result
