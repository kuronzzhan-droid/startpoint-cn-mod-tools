"""Read visible character text from the same immutable client view."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from pathlib import Path

CHARACTER = "master/character/character.orderedmap"
CHARACTER_TEXT = "master/character/character_text.orderedmap"
ACTION_SKILL = "master/skill/action_skill.orderedmap"
CUSTOM = "master/string/custom_ability_string.orderedmap"
ABILITY = "master/ability/ability.orderedmap"
LEADER = "master/ability/leader_ability.orderedmap"
TITLE_COLUMN = 3  # zero-based c3; c2 is the biography, not the title.
SERVER_TARGET = "assets/cdndata/character_text.json"


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

    def __init__(self, view, server_path: Path | None = None):
        self.view = view
        self.raw = {}
        self.tables = {}
        self.server_path = Path(server_path) if server_path else None
        self.server_raw = self.server_path.read_bytes() if self.server_path else None
        self.server = json.loads(self.server_raw) if self.server_raw is not None else None
        if self.server is not None and not isinstance(self.server, dict):
            raise ValueError("character_text.json must be an object")

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
        if self.server_path and self.server_path.read_bytes() != self.server_raw:
            raise ValueError("server character_text.json changed during edit")

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
        if self.server_raw is not None:
            sources[SERVER_TARGET] = sha256(self.server_raw)
        snapshot = sha256(json.dumps(sources, sort_keys=True).encode())
        server_rows = self.server.get(cid) if self.server is not None else None
        return {"schema": "wf-character-text/1", "character_id": cid, "code": char[0], "skill_key": char[8],
                "title": text[TITLE_COLUMN], "title_column": TITLE_COLUMN,
                "character_text": {str(i): v for i, v in enumerate(text)},
                "action_skill": tiers,
                "custom_ability_string": {k: v for k, v in customs.items() if not k.startswith("desc_override_")},
                "desc_override": {k: v for k, v in customs.items() if k.startswith("desc_override_")},
                "server_character_text": server_rows,
                "sources": sources, "snapshot_sha256": snapshot}
