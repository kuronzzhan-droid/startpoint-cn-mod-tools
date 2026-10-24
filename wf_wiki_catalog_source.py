"""Read-only, fingerprinted source access and MOD roster detection for the wiki."""
from __future__ import annotations

import hashlib
import json
import re
import zlib
from pathlib import Path

import wf_dsl
import wf_mod_tool as core
from wf_enhancement_policy import OfficialBaseline
from wf_wiki_compare_refs import linked_changes

TABLES = {
    "character": core.CHARACTER_LOGICAL,
    "text": "master/character/character_text.orderedmap",
    "status": core.STATUS_LOGICAL,
    "awake": "master/character/character_awake_status.orderedmap",
    "ability": core.ABILITY_LOGICAL,
    "leader": "master/ability/leader_ability.orderedmap",
    "skill": core.ACTION_SKILL_LOGICAL,
    "switched": core.SWITCHED_ACTION_SKILL_LOGICAL,
    "strings": "master/string/custom_ability_string.orderedmap",
    "ability_skill": "master/skill/ability_skill.orderedmap",
    "power_flip": "master/skill/power_flip_action.orderedmap",
    "condition": "master/character/unique_condition.orderedmap",
}


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def version_at(repo: Path) -> str:
    """Same highest-version policy as wf_publish, scoped to the requested repo."""
    versions = [(1, 4, 54)]
    pattern = re.compile(r"pinball-\d+\.\d+\.\d+-(\d+\.\d+\.\d+)-\d+-")
    for root in ("common", "medium", "android"):
        for path in (repo / ".cdn/cn" / f"archive-{root}-diff").glob("*.zip"):
            match = pattern.match(path.name)
            if match:
                versions.append(tuple(map(int, match[1].split("."))))
    manifest = repo / "assets/asset-patch/manifest.json"
    if manifest.is_file():
        for patch in json.loads(manifest.read_text(encoding="utf-8")).get("patches", []):
            version = str(patch.get("version", ""))
            if patch.get("enabled") and re.fullmatch(r"\d+\.\d+\.\d+", version):
                versions.append(tuple(map(int, version.split("."))))
    return ".".join(map(str, max(versions)))


def walk_commands(value):
    if isinstance(value, list):
        if (len(value) == 2 and value[0] in ("Command", "Event")
                and isinstance(value[1], list)):
            yield value
        for child in value:
            yield from walk_commands(child)
    elif isinstance(value, dict):
        for child in value.values():
            yield from walk_commands(child)


class WikiSource:
    def __init__(self, repo: Path, store: Path):
        self.repo, self.store = Path(repo), Path(store)
        self.baseline = OfficialBaseline(
            self.repo / ".cdn/cn", write_cache=False,
            cache_dir=self.repo / "mod-tools/work/official-baseline")
        self.fingerprints: dict[str, str] = {}
        self.live_hashes: dict[str, str] = {}
        self.missing: set[str] = set()
        self._files: dict[Path, str | None] = {}
        self._raw: dict[tuple[str, bool], bytes | None] = {}
        self._tables: dict[tuple[str, bool, str], dict] = {}
        self._trees: dict[tuple[str, bool], object] = {}

    def raw(self, logical: str, official: bool = False) -> bytes | None:
        key = logical, official
        if key not in self._raw:
            path = core.table_path(self.store, logical)
            if not official and path.is_file():
                raw = path.read_bytes()
                digest = sha256(raw)
                self.fingerprints[logical] = digest
                self.live_hashes[logical] = digest
                self._files[path] = digest
            else:
                if not official:
                    self._files[path] = None
                    self.missing.add(logical)
                digest = core.sha1_path(logical)
                raw = self.baseline.get("common", digest[:2] + "/" + digest[2:])
                if not official and raw is not None:
                    self.fingerprints[logical] = sha256(raw)
            self._raw[key] = raw
        return self._raw[key]

    def table(self, name: str, official: bool = False) -> dict:
        logical = TABLES.get(name, name)
        codec = "nested" if logical in (TABLES["skill"], TABLES["switched"]) else "flat"
        if logical == TABLES["status"]:
            codec = "status"
        key = logical, official, codec
        if key not in self._tables:
            raw = self.raw(logical, official)
            if raw is None:
                result = {}
            elif codec == "flat":
                result = {k: core.read_csv_lines(v) for k, v in
                          core.read_orderedmap_file_from_bytes(raw).items()}
            else:
                outer = core.read_orderedmap_raw_rows_from_bytes(raw, logical)
                if codec == "status":
                    result = {k: core.decode_status_row(v) for k, v in zip(outer.keys, outer.rows)}
                else:
                    result = {k: {level: core.read_csv_lines(row) for level, row in
                              core.read_orderedmap_file_from_bytes(v).items()}
                              for k, v in zip(outer.keys, outer.rows)}
            self._tables[key] = result
        return self._tables[key]

    def tree(self, logical: str, official: bool = False):
        key = logical, official
        if key not in self._trees:
            raw = self.raw(logical, official)
            self._trees[key] = None if raw is None else wf_dsl.parse_dsl(
                zlib.decompress(raw, -15))["tree"]
        return self._trees[key]

    def verify_unchanged(self) -> None:
        changed = []
        for path, expected in self._files.items():
            actual = sha256(path.read_bytes()) if path.is_file() else None
            if actual != expected:
                changed.append(path.relative_to(self.store).as_posix())
        if changed:
            raise RuntimeError("导出时源文件发生变化，请重新导出：" + ", ".join(changed[:10]))

    def citation(self, name: str) -> dict:
        logical = TABLES.get(name, name)
        return {"logical": logical, "sha256": self.fingerprints.get(logical)}


def detect_roster(source: WikiSource) -> tuple[list[str], dict[str, list[str]]]:
    """New official-baseline keys plus changed official gameplay/identity rows."""
    characters = source.table("character")
    official = source.table("character", True)
    if not official:
        raise ValueError("官方角色基准为空，无法可靠区分新增 MOD 与改版官方")
    shared = set(characters) & set(official)
    changed: dict[str, list[str]] = {}
    for name, column in (("character", None), ("text", None), ("status", None),
                         ("awake", None), ("leader", 17), ("ability", 19), ("skill", 8)):
        live, base = source.table(name), source.table(name, True)
        for cid in shared:
            row = characters[cid][0]
            keys = row[19:25] if column == 19 else [row[column]] if column else [cid]
            for key in keys:
                if live.get(key) != base.get(key):
                    changed.setdefault(cid, []).append(name + ":" + key)
    for cid in shared:
        dependencies = linked_changes(source, official[cid][0], characters[cid][0])
        if dependencies:
            changed.setdefault(cid, []).extend(dependencies)
    new = set(characters) - set(official)
    return sorted(new | set(changed), key=int), changed
