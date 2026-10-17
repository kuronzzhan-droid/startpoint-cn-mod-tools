"""Read visible character text from the same immutable client view."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from pathlib import Path

from .json_patch import parse_mirror

CHARACTER = "master/character/character.orderedmap"
CHARACTER_TEXT = "master/character/character_text.orderedmap"
ACTION_SKILL = "master/skill/action_skill.orderedmap"
CUSTOM = "master/string/custom_ability_string.orderedmap"
ABILITY = "master/ability/ability.orderedmap"
LEADER = "master/ability/leader_ability.orderedmap"
TITLE_COLUMN = 3  # zero-based c3; c2 is the biography, not the title.
SERVER_TARGET = "assets/cdndata/character_text.json"
RANK_TARGET = "assets/cdndata/character_text_rank_p5b.json"
SERVER_TARGETS = (SERVER_TARGET, RANK_TARGET)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def cells(leaf: str) -> list[str]:
    rows = list(csv.reader(io.StringIO(leaf, newline="")))
    if len(rows) != 1:
        raise ValueError("expected one CSV row")
    return rows[0]


def replace_cells(original: str, row: list[str]) -> str:
    out = io.StringIO(newline="")
    csv.writer(out, lineterminator="\n").writerow(row)
    return out.getvalue() if original.endswith("\n") else out.getvalue()[:-1]


def custom_text(leaf: str) -> str:
    row = cells(leaf)
    if len(row) != 1:
        raise ValueError("custom_ability_string must contain one CSV cell")
    return row[0]


class TextWorkspace:
    """Cache inputs; external paths are read-only and edits produce new payloads."""

    def __init__(self, view, server_path: Path | None = None, rank_path: Path | None = None):
        self.view = view
        self.raw = {}
        self.tables = {}
        self.server_path = Path(server_path) if server_path else None
        self.rank_path = Path(rank_path) if rank_path else None
        self.server_paths = {target: path for target, path in
                             zip(SERVER_TARGETS, (self.server_path, self.rank_path)) if path}
        if len({path.resolve() for path in self.server_paths.values()}) != len(self.server_paths):
            raise ValueError("server text mirrors must use distinct input paths")
        self.server_raws = {target: path.read_bytes() for target, path in self.server_paths.items()}
        self.server_docs = {target: parse_mirror(raw) for target, raw in self.server_raws.items()}
        self.server_raw = self.server_raws.get(SERVER_TARGET)
        self.server = self.server_docs.get(SERVER_TARGET)

    def table(self, logical: str):
        if logical not in self.tables:
            import wf_quest_lib as codec
            raw, _ = self.view.read_raw(logical)
            parsed = codec.parse_node(raw)
            if not isinstance(parsed, dict):
                raise ValueError(f"text table is not an orderedmap: {logical}")
            self.raw[logical], self.tables[logical] = raw, parsed
        return self.tables[logical]

    def verify(self):
        """Recheck inputs at the staging boundary, including the server mirror."""
        if hasattr(self.view, "verify"):
            self.view.verify()
        for logical, original in self.raw.items():
            if self.view.read_raw(logical)[0] != original:
                raise ValueError(f"text input changed during edit: {logical}")
        for target, path in self.server_paths.items():
            if path.read_bytes() != self.server_raws[target]:
                raise ValueError(f"server {Path(target).name} changed during edit")

    def custom_keys(self, cid: str) -> list[str]:
        row = cells(self.table(CHARACTER)[cid])
        names = {row[0], row[8]}
        references = set()
        for logical, keys in ((LEADER, row[17:18]), (ABILITY, row[19:25])):
            for key in keys:
                leaf = self.table(logical).get(key, "")
                if isinstance(leaf, str) and leaf:
                    for record in csv.reader(io.StringIO(leaf, newline="")):
                        references.update(record)
                        # Kind 629 names also occur inside path$program cells.
                        for value in record:
                            references.update(re.findall(r"[A-Za-z0-9_]+", value))
                        if record:
                            names.add(record[0])
        # Name-bound prefixes cover client conventions; exact references cover
        # a shared key whose spelling is unrelated to the character code.
        prefixes = ("change_skill_", "change_skill_2_", "override_string_", "desc_override_", "paradox_echo_")
        codes = {cells(leaf)[0] for leaf in self.table(CHARACTER).values()}
        def belongs(key, prefix, name):
            if not (key == prefix + name or key.startswith(prefix + name + "_")):
                return False
            # A short official code must not claim another character's variant.
            return not any(other != name and other.startswith(name + "_")
                           and (key == prefix + other or key.startswith(prefix + other + "_"))
                           for other in codes)
        return sorted(key for key in self.table(CUSTOM)
                      if key in references or any(belongs(key, p, n)
                                                 for p in prefixes for n in names if n))

    def read(self, cid: str) -> dict:
        cid = str(cid)
        char = cells(self.table(CHARACTER)[cid])
        text = cells(self.table(CHARACTER_TEXT)[cid])
        skill = self.table(ACTION_SKILL).get(char[8])
        if not isinstance(skill, dict):
            raise ValueError(f"missing action_skill for character {cid}: {char[8]}")
        tiers = {}
        for tier in ("1", "2", "3"):
            if tier in skill and skill[tier]:
                fields = cells(skill[tier])
                if len(fields) < 2:
                    raise ValueError(f"action_skill[{char[8]}][{tier}] lacks c0/c1")
                tiers[tier] = {"c0": fields[0], "c1": fields[1]}
        customs = {key: custom_text(self.table(CUSTOM)[key]) for key in self.custom_keys(cid)}
        sources = {logical: sha256(raw) for logical, raw in sorted(self.raw.items())}
        sources.update({target: sha256(raw) for target, raw in self.server_raws.items()})
        snapshot = sha256(json.dumps(sources, sort_keys=True).encode())
        server_rows = self.server.get(cid) if self.server is not None else None
        return {"schema": "wf-character-text/1", "character_id": cid, "code": char[0], "skill_key": char[8],
                "title": text[TITLE_COLUMN], "title_column": TITLE_COLUMN,
                "character_text": {str(i): v for i, v in enumerate(text)},
                "action_skill": tiers,
                "custom_ability_string": {k: v for k, v in customs.items() if not k.startswith("desc_override_")},
                "desc_override": {k: v for k, v in customs.items() if k.startswith("desc_override_")},
                "server_character_text": server_rows,
                "server_character_text_rank_p5b": self.server_docs.get(RANK_TARGET, {}).get(cid),
                "sources": sources, "snapshot_sha256": snapshot}
