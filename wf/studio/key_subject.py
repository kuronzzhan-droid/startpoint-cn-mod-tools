"""Conservative ownership evidence for a delivery's changed orderedmap keys."""
from __future__ import annotations

import zlib
from collections import defaultdict

import wf_mod_tool as core

from .id_catalog import CHARACTER, TABLES

ABILITY = "master/ability/ability.orderedmap"
LEADER = "master/ability/leader_ability.orderedmap"
SKILL = "master/skill/action_skill.orderedmap"
CUSTOM = "master/string/custom_ability_string.orderedmap"
ALIASES = {"soul": "soul_item", "unique": "unique_condition", "stringcode": "string_id"}


def _read(view, logical):
    try:
        return view.read_raw(logical)[0]
    except (FileNotFoundError, KeyError):
        return None


def _characters(view):
    raw = _read(view, CHARACTER)
    if raw is None:
        return {}
    table = core.read_orderedmap_raw_rows_from_bytes(raw, CHARACTER)
    result = {}
    for key, row in zip(table.keys, table.rows):
        cells = core.read_csv_lines(zlib.decompress(row).decode("utf-8"))
        if cells:
            result[key] = cells[0]
    return result


class SubjectKeys:
    """Known IDs, explicit reservations and character references; no substring IDs.

    A draft's arbitrary edits are not ownership declarations. In particular,
    editing another character's text does not turn that text into owned content.
    """

    def __init__(self, view, subject=None):
        draft = subject if isinstance(subject, dict) else {"characterId": str(subject)} if subject else {}
        self.identity = str(draft.get("characterId") or "")
        self.kind = draft.get("subjectKind", "character")
        self.code = str(draft.get("code") or "")
        self.ids = defaultdict(set)
        self.explicit = defaultdict(set)
        self.unknown = defaultdict(set)
        self.references = defaultdict(set)
        characters = _characters(view)
        own_row = characters.get(self.identity, []) if self.kind == "character" else []
        if not self.code and own_row:
            self.code = own_row[0]
        self.codes = {row[0]: cid for cid, row in characters.items() if row and row[0]}
        if self.code and self.kind == "character":
            self.codes[self.code] = self.identity or "subject"
        if self.identity and self.kind == "character":
            self.ids["character"].add(self.identity)
            self.ids["mana_node"].add(self.identity)
        elif self.identity and self.kind == "weapon":
            self.ids["weapon"].add(self.identity)
        self._reservations(draft.get("reservations", {}))
        for cid, row in characters.items():
            for logical, columns in ((SKILL, (8,)), (LEADER, (17,)), (ABILITY, range(19, 25))):
                for column in columns:
                    if len(row) > column and row[column] not in ("", "0", "(None)"):
                        self.references[logical, row[column]].add(cid)
        for change in draft.get("changes", []):
            params = change.get("params", {})
            self._reservations(params.get("reservations", {}))
            if change.get("kind") == "character_clone":
                for logical, keys in params.get("ownedRows", {}).items():
                    self.explicit[logical].update(map(str, keys))
            for request in params.get("requests", []):
                self._weapon(request, view)
        from .subject_evidence import ability_evidence, weapon_icon_evidence
        ability_evidence(self, view, draft.get("changes", []))
        if self.kind == "weapon":
            weapon_icon_evidence(self, view, draft.get("changes", []))

    def _reservations(self, registrations):
        if not isinstance(registrations, dict):
            raise ValueError("主体 reservations 必须是对象")
        for kind, values in registrations.items():
            kind = ALIASES.get(kind, kind)
            if kind not in TABLES:
                continue
            if not isinstance(values, list):
                raise ValueError(f"主体 reservations/{kind} 必须是数组")
            self.ids[kind].update(map(str, values))

    def _weapon(self, request, view):
        if not str(request.get("operation", "")).startswith("weapon_"):
            return
        spec = request.get("weapon", {})
        if "id" not in spec:
            return
        self.ids["weapon"].add(str(spec["id"]))
        # The editor's weapon clone contract explicitly allocates the soul ID.
        # Other weapon operations can reference pre-existing, differently owned souls.
        if request.get("operation") == "weapon_clone":
            self.ids["soul_item"].add(str(spec["id"]))
            code = spec.get("code", "boss_workshop_" + str(spec["id"]))
            soul = code + "_soul" if "code" in spec else "boss_workshop_soul_" + str(spec["id"])
            self.ids["string_id"].update((code, soul))
            from .subject_evidence import table
            existing = table(view, CUSTOM)
            self.explicit[CUSTOM].update(key for key in
                ("awakening_material_" + str(spec["id"]), code + "_pf_damage") if key not in existing)
        self.ids["enhancement_shop"].update(map(str, spec.get("enhancementProducts", [])))
        self.ids["enhancement_shop"].update(str(s["productId"]) for s in spec.get("stages", [])
                                             if "productId" in s)

    def classify(self, logical, key):
        if not self.identity and not self.code and not self.ids and not self.explicit:
            return "unknown"
        if key in self.explicit.get(logical, ()):
            return "owned"
        owners = self.references.get((logical, key), set())
        if owners:
            if logical in (ABILITY, LEADER, SKILL) and self.kind != "character":
                return "foreign"
            return "owned" if owners == {self.identity} else "foreign"
        kinds = [kind for kind, paths in TABLES.items() if logical in paths]
        if any(key in self.ids.get(kind, ()) for kind in kinds):
            return "owned"
        if key in self.unknown.get(logical, ()):
            return "unknown"
        # Longest known character-code match prevents hero_alt from being
        # attributed to hero. Bare numeric substrings are never evidence.
        codes = [code for code in self.codes if key == code or key.startswith(code + "_")
                 or key.startswith("character/" + code + "/")]
        if codes:
            owner = self.codes[max(codes, key=len)]
            return "owned" if self.kind == "character" and owner in {self.identity, "subject"} else "foreign"
        if logical == CUSTOM:
            for prefix in ("wfx_summon_flip_pf_", "wfx_ball_pf_action_"):
                if key.startswith(prefix):
                    identity = key.removeprefix(prefix)
                    known = self.ids.get("multiball", set())
                    if known and identity.isdigit():
                        return "owned" if identity in known else "foreign"
        # Only typed tables with an explicitly known ID namespace permit a
        # negative ownership decision. Absent registration remains unknown.
        if key.isdigit() and any(self.ids.get(kind) for kind in kinds if kind != "string_id"):
            return "foreign"
        return "unknown"

    def describe(self):
        return {"characterId": self.identity or None, "code": self.code or None,
                "subjectKind": self.kind,
                "reservations": {kind: sorted(values) for kind, values in sorted(self.ids.items()) if values}}
