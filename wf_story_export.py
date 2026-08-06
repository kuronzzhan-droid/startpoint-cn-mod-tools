# -*- coding: utf-8 -*-
"""Read-only World Flipper scenario exporter.

The scenario command schema is derived from the CN client's
``ScenarioCommandKind.as`` and ``ScenarioCommandValues.as``.  Store files are
never modified; the only writes are Markdown/JSONL files below ``--out``.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import zlib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import wf_mod_tool as core
import wf_quest_lib as quest_core


@dataclass(frozen=True)
class FieldSpec:
    """One typed field in the 43-column ScenarioCommandValues row."""

    name: str
    column: int
    value_type: str = "string"


@dataclass(frozen=True)
class OpcodeSpec:
    """AS3 enum name and its named CSV fields."""

    name: str
    fields: tuple[FieldSpec, ...] = ()


@dataclass(frozen=True)
class ScenarioCommand:
    """One decoded command while retaining its complete source row."""

    line: int
    kind: int
    op: str
    args: dict[str, Any]
    raw: list[str]


@dataclass(frozen=True)
class Speaker:
    """Authoritative display name for one story-character alias."""

    code: str
    name: str


@dataclass(frozen=True)
class StoryEntry:
    """One scenario and its best quest/character metadata."""

    category: str
    relative_dir: str
    logical_path: str
    quest_id: str | None = None
    title: str | None = None
    character_id: str | None = None
    character_code: str | None = None
    character_name: str | None = None
    episode: int | None = None
    order: tuple[int, ...] = ()


@dataclass(frozen=True)
class CharacterInfo:
    """Character identity used to group seasonal variants."""

    character_id: str
    code: str
    name: str
    identity_character_id: str


@dataclass(frozen=True)
class QuestSource:
    category: str
    logical_path: str
    scenario_column: int
    title_column: int | None
    quest_id_column: int | None
    character_column: int | None = None
    episode_column: int | None = None
    canonical_character_column: int | None = None


@dataclass(frozen=True)
class QuestReference:
    source: QuestSource
    scenario_logical: str
    quest_id: str | None
    title: str | None
    character_id: str | None
    episode: int | None
    order: tuple[int, ...]
    canonical: bool


@dataclass(frozen=True)
class ValidationReport:
    """Complete, serializable result of a no-write validation pass."""

    scenario_total: int
    decoded: int
    instruction_total: int
    dialogue_total: int
    category_counts: dict[str, int]
    manifest_contract_errors: tuple[str, ...]
    decode_failures: dict[str, str]
    unknown_opcodes: dict[int, int]
    unresolved_speakers: dict[str, int]
    title_association_missing: tuple[str, ...]
    referenced_not_in_pathlist: tuple[str, ...]
    unreferenced_pathlist: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.decode_failures and not self.manifest_contract_errors

    def summary(self) -> dict[str, Any]:
        return {
            "category_counts": dict(sorted(self.category_counts.items())),
            "decode_failures": len(self.decode_failures),
            "decoded": self.decoded,
            "dialogue_total": self.dialogue_total,
            "instruction_total": self.instruction_total,
            "manifest_contract_errors": len(self.manifest_contract_errors),
            "ok": self.ok,
            "referenced_not_in_pathlist": len(self.referenced_not_in_pathlist),
            "scenario_total": self.scenario_total,
            "title_association_missing": len(self.title_association_missing),
            "unknown_opcode_rows": sum(self.unknown_opcodes.values()),
            "unknown_opcodes": {
                str(kind): count for kind, count in sorted(self.unknown_opcodes.items())
            },
            "unreferenced_pathlist": len(self.unreferenced_pathlist),
            "unresolved_speaker_rows": sum(self.unresolved_speakers.values()),
            "unresolved_speakers": dict(sorted(self.unresolved_speakers.items())),
        }


def _f(name: str, column: int, value_type: str = "string") -> FieldSpec:
    return FieldSpec(name, column, value_type)


# Authoritative 0-based columns from ScenarioCommandValues.as.  The observed
# data only uses 22 kinds, but the client enum defines all 25 and the exporter
# must remain able to decode the currently-unused ScreenFade/Background kinds.
OPCODES: dict[int, OpcodeSpec] = {
    0: OpcodeSpec("Text", (
        _f("text_character_id", 4),
        _f("text_body", 5, "text"),
        _f("text_voice_path", 6, "optional_string"),
        _f("text_voice_immediately", 7, "bool"),
        _f("text_balloon_position", 8, "int"),
    )),
    1: OpcodeSpec("Bgm", (
        _f("bgm_channel", 35, "int"),
        _f("bgm_id", 36),
    )),
    2: OpcodeSpec("BgmStop", (
        _f("bgm_stop_channel", 37, "int"),
    )),
    3: OpcodeSpec("BgmFadeIn", (
        _f("bgm_fade_in_channel", 38, "int"),
        _f("bgm_fade_in_id", 39),
        _f("bgm_fade_in_time", 40, "nullable_int"),
    )),
    4: OpcodeSpec("BgmFadeOut", (
        _f("bgm_fade_out_channel", 41, "int"),
        _f("bgm_fade_out_time", 42, "nullable_int"),
    )),
    5: OpcodeSpec("MovieSequence", (
        _f("movie_sequence_section", 1),
        _f("movie_sequence_wait", 2, "bool"),
        _f("movie_sequence_skip_enable", 3, "bool"),
    )),
    6: OpcodeSpec("CharacterIn", (
        _f("character_in_id", 12),
        _f("character_in_position", 13, "int"),
        _f("character_in_face", 14, "string_list"),
        _f("character_in_reverse", 15, "bool"),
    )),
    7: OpcodeSpec("CharacterOut", (
        _f("character_out_id", 16),
        _f("character_out_kind", 17, "optional_int"),
    )),
    8: OpcodeSpec("CharacterOutAll", (
        _f("character_out_all_kind", 18, "optional_int"),
    )),
    9: OpcodeSpec("CharacterActive", (
        _f("character_active_id", 9),
    )),
    10: OpcodeSpec("CharacterActiveOnly", (
        _f("character_active_only_id", 10),
    )),
    11: OpcodeSpec("CharacterInactive", (
        _f("character_inactive_id", 11),
    )),
    12: OpcodeSpec("CharacterFace", (
        _f("character_face_id", 19),
        _f("character_face_face", 20, "string_list"),
    )),
    13: OpcodeSpec("CharacterAnimation", (
        _f("character_animation_id", 21),
        _f("character_animation_kind", 22, "int"),
    )),
    14: OpcodeSpec("ScreenShake", (
        _f("screen_shake_time", 27, "nullable_int"),
        _f("screen_shake_size", 28, "nullable_int"),
    )),
    15: OpcodeSpec("ScreenShakeStop"),
    16: OpcodeSpec("ScreenFadeIn", (
        _f("screen_fade_in_color", 23, "nullable_int"),
        _f("screen_fade_in_time", 24, "nullable_int"),
    )),
    17: OpcodeSpec("ScreenFadeOut", (
        _f("screen_fade_out_color", 25, "nullable_int"),
        _f("screen_fade_out_time", 26, "nullable_int"),
    )),
    18: OpcodeSpec("ScreenColorEffect", (
        _f("screen_color_effect_preset", 29),
        _f("screen_color_effect_time", 30, "nullable_int"),
    )),
    19: OpcodeSpec("ScreenColorEffectCustom", (
        _f("screen_color_effect_custom_matrix", 31, "float_list"),
        _f("screen_color_effect_custom_time", 32, "nullable_int"),
    )),
    20: OpcodeSpec("ScreenColorEffectDisable", (
        _f("screen_color_effect_disable_time", 33, "nullable_int"),
    )),
    21: OpcodeSpec("Background", (
        _f("background_path", 34, "optional_string"),
    )),
    22: OpcodeSpec("MessageWindowShow"),
    23: OpcodeSpec("MessageWindowHide"),
    24: OpcodeSpec("NextMovie"),
}


CATEGORIES = (
    "character_story_quest",
    "story_quest",
    "story_event_quest",
    "advent_event",
    "system_quest",
)

COMMAND_COLUMN_COUNT = 43
EXPECTED_CATEGORY_COUNTS = {
    "character_story_quest": 1312,
    "story_quest": 197,
    "story_event_quest": 157,
    "advent_event": 39,
    "system_quest": 3,
}


QUEST_SOURCES = (
    QuestSource(
        "character_story_quest",
        "master/quest/character_quest.orderedmap",
        scenario_column=126,
        title_column=3,
        quest_id_column=None,
        character_column=49,
        episode_column=50,
        canonical_character_column=0,
    ),
    QuestSource(
        "story_quest",
        "master/quest/main_quest.orderedmap",
        scenario_column=124,
        title_column=1,
        quest_id_column=0,
    ),
    QuestSource(
        "story_event_quest",
        "master/quest/event/story_event_single_quest.orderedmap",
        scenario_column=126,
        title_column=2,
        quest_id_column=0,
    ),
    QuestSource(
        "story_event_quest",
        "master/quest/event/world_story_event_quest.orderedmap",
        scenario_column=125,
        title_column=2,
        quest_id_column=0,
    ),
    QuestSource(
        "advent_event",
        "master/quest/event/advent_event_quest.orderedmap",
        scenario_column=130,
        title_column=2,
        quest_id_column=0,
    ),
    QuestSource(
        "system_quest",
        "master/tutorial/triggered_tutorial.orderedmap",
        scenario_column=26,
        title_column=22,
        quest_id_column=0,
    ),
)


CHARACTER_LOGICAL = "master/character/character.orderedmap"
CHARACTER_TEXT_LOGICAL = "master/character/character_text.orderedmap"
STORY_CHARACTER_LOGICAL = "master/story/story_character.orderedmap"

MOD_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = MOD_DIR.parent
DEFAULT_STORE = (
    PROJECT_ROOT
    / "弹国服"
    / "WorldFlipper"
    / "dummy"
    / "download"
    / "production"
    / "upload"
)
DEFAULT_PATHLIST = MOD_DIR / "WF_PATHLIST_recovered.txt"
DEFAULT_OUT = MOD_DIR / "work" / "story_export"


def normalize_story_text(value: str) -> str:
    """Normalize physical and escaped story line breaks without other escapes."""

    return value.replace("\r\n", "\n").replace("\r", "\n").replace("\\n", "\n")


def _parse_client_int(raw: str) -> int:
    """Parse the decimal/hex forms accepted by Haxe ``Std.parseInt``."""

    value = raw.strip()
    signless = value[1:] if value[:1] in {"+", "-"} else value
    base = 16 if signless.lower().startswith("0x") else 10
    return int(value, base)


def _convert_value(raw: str, value_type: str) -> Any:
    if value_type == "string":
        return raw
    if value_type == "text":
        return normalize_story_text(raw)
    if value_type == "optional_string":
        return None if raw == "(None)" else raw
    if value_type == "bool":
        lowered = raw.lower()
        if lowered not in {"true", "false"}:
            raise ValueError(f"invalid boolean {raw!r}")
        return lowered == "true"
    if value_type == "int":
        return _parse_client_int(raw)
    if value_type == "nullable_int":
        return None if raw.strip() in {"", "(None)"} else _parse_client_int(raw)
    if value_type == "optional_int":
        return None if raw == "(None)" else _parse_client_int(raw)
    if value_type == "string_list":
        return [] if raw == "" else raw.split(",")
    if value_type == "float_list":
        return [] if raw == "" else [float(item) for item in raw.split(",")]
    raise ValueError(f"unsupported ScenarioCommand field type {value_type!r}")


def parse_command(line: int, csv_text: str, logical_path: str) -> ScenarioCommand:
    """Parse one wide CSV command row according to the AS3 schema."""

    rows = core.read_csv_lines(csv_text)
    if len(rows) != 1:
        raise ValueError(
            f"{logical_path}: line {line} must contain exactly one CSV row, got {len(rows)}"
        )
    raw = rows[0]
    if len(raw) != COMMAND_COLUMN_COUNT:
        raise ValueError(
            f"{logical_path}: line {line} must contain exactly "
            f"{COMMAND_COLUMN_COUNT} columns, got {len(raw)}"
        )
    if not raw or raw[0] == "":
        raise ValueError(f"{logical_path}: line {line} has no opcode")
    try:
        kind = int(raw[0])
    except ValueError as exc:
        raise ValueError(
            f"{logical_path}: line {line} has non-integer opcode {raw[0]!r}"
        ) from exc

    spec = OPCODES.get(kind)
    if spec is None:
        args = {
            f"col_{column}": value
            for column, value in enumerate(raw[1:], start=1)
            if value != ""
        }
        return ScenarioCommand(line, kind, "unknown", args, raw)

    args: dict[str, Any] = {}
    for field in spec.fields:
        if field.column >= len(raw):
            raise ValueError(
                f"{logical_path}: line {line} kind={kind} lacks column {field.column} "
                f"for {field.name}"
            )
        try:
            args[field.name] = _convert_value(raw[field.column], field.value_type)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"{logical_path}: line {line} kind={kind} field={field.name} "
                f"has invalid value {raw[field.column]!r}"
            ) from exc
    return ScenarioCommand(line, kind, spec.name, args, raw)


def _validate_orderedmap_index_stream(raw: bytes, label: str) -> None:
    """Reject incomplete or concatenated data inside the indexed zlib segment."""

    if len(raw) < 4:
        raise ValueError(f"{label}: orderedmap is too small for an index")
    index_length = int.from_bytes(raw[:4], "little")
    if index_length <= 0 or 4 + index_length > len(raw):
        raise ValueError(f"{label}: invalid orderedmap index length {index_length}")
    try:
        inflater = zlib.decompressobj()
        inflater.decompress(raw[4:4 + index_length])
        inflater.flush()
    except zlib.error as exc:
        raise ValueError(f"{label}: invalid orderedmap index zlib stream") from exc
    if not inflater.eof or inflater.unused_data or inflater.unconsumed_tail:
        raise ValueError(
            f"{label}: orderedmap index contains trailing or incomplete zlib data"
        )


def decode_scenario_bytes(
    raw: bytes, logical_path: str
) -> tuple[str, list[ScenarioCommand]]:
    """Decode a raw-row outer map containing one compressed-row inner map."""

    try:
        _validate_orderedmap_index_stream(raw, f"{logical_path}:outer")
        outer = core.read_orderedmap_raw_rows_from_bytes(
            raw, f"{logical_path}:outer")
    except Exception as exc:
        raise ValueError(
            f"{logical_path}: invalid scenario outer orderedmap: {exc}"
        ) from exc
    if len(outer.keys) != 1 or len(outer.rows) != 1:
        raise ValueError(
            f"{logical_path}: scenario outer orderedmap must contain exactly one key"
        )
    blob = outer.rows[0]
    try:
        _validate_orderedmap_index_stream(blob, f"{logical_path}:inner")
        inner = core.read_orderedmap_raw_rows_from_bytes(
            blob, f"{logical_path}:inner")
    except Exception as exc:
        raise ValueError(
            f"{logical_path}: invalid scenario inner orderedmap "
            f"(outer row must be raw): {exc}"
        ) from exc
    expected_keys = [str(index) for index in range(1, len(inner.keys) + 1)]
    if inner.keys != expected_keys:
        raise ValueError(
            f"{logical_path}: scenario line keys must be continuous 1..N, "
            f"got {inner.keys[:8]!r}"
        )

    commands: list[ScenarioCommand] = []
    for line, chunk in zip(inner.keys, inner.rows, strict=True):
        try:
            inflater = zlib.decompressobj()
            decoded = inflater.decompress(chunk) + inflater.flush()
            if not inflater.eof or inflater.unused_data or inflater.unconsumed_tail:
                raise ValueError("compressed row has trailing or incomplete zlib data")
            csv_text = decoded.decode("utf-8")
        except (UnicodeError, ValueError, zlib.error) as exc:
            raise ValueError(
                f"{logical_path}: invalid compressed scenario row {line}: {exc}"
            ) from exc
        commands.append(parse_command(int(line), csv_text, logical_path))
    return outer.keys[0], commands


def _speaker_name(code: str, speakers: Mapping[str, Speaker]) -> str:
    if code == "":
        return "旁白"
    speaker = speakers.get(code)
    return speaker.name if speaker is not None else code


def _markdown_dialogue(
    command: ScenarioCommand, speakers: Mapping[str, Speaker]
) -> str:
    code = command.args["text_character_id"]
    name = _speaker_name(code, speakers)
    marker = "🔊" if command.args["text_voice_path"] else ""
    parts = command.args["text_body"].split("\n")
    first = f"**{name}**{marker}：{parts[0]}"
    if len(parts) == 1:
        return first
    continuation = "  \n".join(f"　{part}" for part in parts[1:])
    return f"{first}  \n{continuation}"


def _markdown_stage_note(
    command: ScenarioCommand, speakers: Mapping[str, Speaker]
) -> str | None:
    args = command.args
    if command.op == "Bgm":
        return f"*（BGM：{args['bgm_id']}）*"
    if command.op == "BgmStop":
        return f"*（停止 BGM：频道 {args['bgm_stop_channel']}）*"
    if command.op == "BgmFadeIn":
        return (
            f"*（BGM 淡入：{args['bgm_fade_in_id']}，"
            f"{args['bgm_fade_in_time']} 帧）*"
        )
    if command.op == "BgmFadeOut":
        return (
            f"*（BGM 淡出：频道 {args['bgm_fade_out_channel']}，"
            f"{args['bgm_fade_out_time']} 帧）*"
        )
    if command.op == "MovieSequence":
        return f"*（场景切换：{args['movie_sequence_section']}）*"
    if command.op == "CharacterIn":
        name = _speaker_name(args["character_in_id"], speakers)
        face = "+".join(args["character_in_face"])
        suffix = f"，表情 {face}" if face else ""
        return f"*（{name}入场：站位 {args['character_in_position']}{suffix}）*"
    if command.op == "CharacterOut":
        name = _speaker_name(args["character_out_id"], speakers)
        return f"*（{name}退场）*"
    if command.op == "CharacterOutAll":
        return "*（全员退场）*"
    if command.op == "CharacterFace":
        name = _speaker_name(args["character_face_id"], speakers)
        face = "+".join(args["character_face_face"])
        return f"*（{name}换表情：{face}）*"
    if command.op == "Background":
        path = args["background_path"]
        return f"*（背景：{path if path is not None else '清除'}）*"
    return None


def _unknown_markdown(command: ScenarioCommand) -> str:
    cols = {
        str(column): value
        for column, value in enumerate(command.raw[1:], start=1)
        if value != ""
    }
    return (
        f"<!-- kind={command.kind} cols="
        f"{json.dumps(cols, ensure_ascii=False)} -->"
    )


def render_markdown(
    entry: StoryEntry,
    commands: Sequence[ScenarioCommand],
    speakers: Mapping[str, Speaker],
) -> str:
    """Render dialogue plus the task's requested basic stage directions."""

    if entry.character_name and entry.episode is not None:
        title = entry.title or entry.relative_dir.rsplit("/", 1)[-1]
        heading = (
            f"# {entry.character_name} 个人剧情 第{entry.episode}话 「{title}」"
        )
    else:
        title = entry.title or entry.relative_dir.rsplit("/", 1)[-1]
        heading = f"# {entry.category} {entry.relative_dir} 「{title}」"

    blocks = [heading]
    for command in commands:
        if command.op == "Text":
            blocks.append(_markdown_dialogue(command, speakers))
        elif command.op == "unknown":
            blocks.append(_unknown_markdown(command))
        else:
            note = _markdown_stage_note(command, speakers)
            if note is not None:
                blocks.append(note)
    return "\n\n".join(blocks) + "\n"


def render_jsonl(
    commands: Sequence[ScenarioCommand], speakers: Mapping[str, Speaker]
) -> str:
    """Render every command as exactly one physical JSONL record."""

    lines: list[str] = []
    for command in commands:
        record: dict[str, Any] = {
            "line": command.line,
            "kind": command.kind,
            "op": command.op,
            "args": command.args,
            "raw": command.raw,
        }
        if command.op == "Text":
            code = command.args["text_character_id"]
            record.update({
                "speaker_code": code,
                "speaker_name": _speaker_name(code, speakers),
                "text": command.args["text_body"],
                "voice": command.args["text_voice_path"],
            })
        lines.append(json.dumps(record, ensure_ascii=False))
    return "\n".join(lines) + ("\n" if lines else "")


def _single_csv_row(text: str, label: str) -> list[str]:
    rows = core.read_csv_lines(text)
    if len(rows) != 1:
        raise ValueError(f"{label}: expected exactly one CSV row, got {len(rows)}")
    return rows[0]


def _read_flat_rows(store: Path, logical_path: str) -> dict[str, list[str]]:
    path = core.table_path(store, logical_path)
    ordered = core.read_orderedmap_file(path, logical_path)
    return {
        key: _single_csv_row(text, f"{logical_path}:{key}")
        for key, text in ordered.text_rows().items()
    }


def load_speakers(store: Path) -> dict[str, Speaker]:
    """Load the alias-level authoritative story-character names."""

    return {
        code: Speaker(code, row[0] if row else code)
        for code, row in _read_flat_rows(store, STORY_CHARACTER_LOGICAL).items()
    }


def _iter_leaf_texts(
    node: object, key_path: tuple[str, ...] = ()
):
    if isinstance(node, str):
        yield key_path, node
        return
    if not isinstance(node, dict):
        raise ValueError(f"quest orderedmap node has unsupported type {type(node)!r}")
    for key, child in node.items():
        yield from _iter_leaf_texts(child, key_path + (str(key),))


def _numeric_key_path(keys: tuple[str, ...]) -> tuple[int, ...]:
    result: list[int] = []
    for key in keys:
        if not key.isdigit():
            raise ValueError(f"quest orderedmap key is not numeric: {key!r}")
        result.append(int(key))
    return tuple(result)


def _scenario_logical(reference: str) -> str:
    normalized = reference.replace("\\", "/").strip().lstrip("/")
    if normalized.startswith("master/"):
        logical = normalized
    else:
        logical = f"master/{normalized}"
    if not logical.endswith(".orderedmap"):
        logical += ".orderedmap"
    return logical


def _manifest_parts(logical_path: str) -> tuple[str, str] | None:
    normalized = logical_path.replace("\\", "/").strip()
    prefix = "master/story/"
    suffix = "/scenario.orderedmap"
    if not normalized.startswith(prefix) or not normalized.endswith(suffix):
        return None
    middle = normalized[len(prefix):-len(suffix)]
    category, separator, relative = middle.partition("/")
    if not separator or category not in CATEGORIES or not relative:
        return None
    return category, relative


class StoryCatalog:
    """Read-only index joining the pathlist, quest tables, and characters."""

    def __init__(self, store: Path, pathlist: Path):
        self.store = Path(store).resolve()
        self.pathlist = Path(pathlist).resolve()
        if not self.store.is_dir():
            raise FileNotFoundError(f"story store does not exist: {self.store}")
        if not self.pathlist.is_file():
            raise FileNotFoundError(f"story pathlist does not exist: {self.pathlist}")

        self.pathlist_duplicates: tuple[str, ...] = ()
        self.pathlist_rejected_story_lines: tuple[str, ...] = ()
        self.characters = self._load_characters()
        manifest = self._load_manifest()
        references = self._load_quest_references()
        self.referenced_not_in_pathlist = tuple(sorted(set(references) - set(manifest)))
        self.unreferenced_pathlist = tuple(sorted(set(manifest) - set(references)))
        self.entries = tuple(self._build_entries(manifest, references))

    def _load_characters(self) -> dict[str, CharacterInfo]:
        character_path = core.table_path(self.store, CHARACTER_LOGICAL)
        text_path = core.table_path(self.store, CHARACTER_TEXT_LOGICAL)
        if not character_path.exists() or not text_path.exists():
            return {}
        characters = _read_flat_rows(self.store, CHARACTER_LOGICAL)
        texts = _read_flat_rows(self.store, CHARACTER_TEXT_LOGICAL)
        result: dict[str, CharacterInfo] = {}
        for character_id, row in characters.items():
            if not row:
                continue
            text_row = texts.get(character_id, [])
            identity = row[27] if len(row) > 27 else ""
            if identity in {"", "(None)"}:
                identity = character_id
            result[character_id] = CharacterInfo(
                character_id=character_id,
                code=row[0],
                name=text_row[0] if text_row else row[0],
                identity_character_id=identity,
            )
        return result

    def _load_manifest(self) -> dict[str, tuple[str, str]]:
        manifest: dict[str, tuple[str, str]] = {}
        duplicates: set[str] = set()
        rejected: set[str] = set()
        for raw_line in self.pathlist.read_text(encoding="utf-8").splitlines():
            logical = raw_line.strip().replace("\\", "/")
            if not logical:
                continue
            parts = _manifest_parts(logical)
            if parts is None:
                if (
                    logical.startswith("master/story/")
                    and logical.endswith("/scenario.orderedmap")
                ):
                    rejected.add(logical)
                continue
            if logical in manifest:
                duplicates.add(logical)
                continue
            manifest[logical] = parts
        self.pathlist_duplicates = tuple(sorted(duplicates))
        self.pathlist_rejected_story_lines = tuple(sorted(rejected))
        return manifest

    def _load_quest_references(self) -> dict[str, list[QuestReference]]:
        references: dict[str, list[QuestReference]] = {}
        for source in QUEST_SOURCES:
            path = core.table_path(self.store, source.logical_path)
            if not path.exists():
                continue
            tree = quest_core.parse_node(path.read_bytes())
            if not isinstance(tree, dict):
                raise ValueError(f"{source.logical_path}: top-level node is not a map")
            for key_path, text in _iter_leaf_texts(tree):
                if not text:
                    continue
                row = _single_csv_row(text, f"{source.logical_path}:{'/'.join(key_path)}")
                if source.scenario_column >= len(row):
                    continue
                scenario = row[source.scenario_column]
                if scenario in {"", "(None)"}:
                    continue
                logical = _scenario_logical(scenario)
                title = None
                if source.title_column is not None and source.title_column < len(row):
                    value = row[source.title_column]
                    title = None if value in {"", "(None)"} else value
                if source.quest_id_column is None:
                    quest_id = key_path[-1] if key_path else None
                elif source.quest_id_column < len(row):
                    quest_id = row[source.quest_id_column] or None
                else:
                    quest_id = None
                character_id = None
                if source.character_column is not None and source.character_column < len(row):
                    character_id = row[source.character_column] or None
                episode = None
                if source.episode_column is not None and source.episode_column < len(row):
                    raw_episode = row[source.episode_column]
                    episode = int(raw_episode) if raw_episode else None
                canonical = True
                if (
                    source.canonical_character_column is not None
                    and character_id is not None
                    and source.canonical_character_column < len(row)
                ):
                    canonical = row[source.canonical_character_column] == character_id
                order = _numeric_key_path(key_path)
                if source.category == "character_story_quest" and character_id and episode:
                    order = (int(character_id), episode)
                reference = QuestReference(
                    source=source,
                    scenario_logical=logical,
                    quest_id=quest_id,
                    title=title,
                    character_id=character_id,
                    episode=episode,
                    order=order,
                    canonical=canonical,
                )
                references.setdefault(logical, []).append(reference)
        return references

    @staticmethod
    def _choose_reference(
        category: str, candidates: Sequence[QuestReference]
    ) -> QuestReference | None:
        if not candidates:
            return None

        def sort_key(reference: QuestReference):
            title = reference.title or ""
            return (
                reference.source.category != category,
                not reference.canonical,
                "::quest_rank::" in title,
                reference.order,
                reference.quest_id or "",
            )

        return min(candidates, key=sort_key)

    def _build_entries(
        self,
        manifest: Mapping[str, tuple[str, str]],
        references: Mapping[str, Sequence[QuestReference]],
    ) -> list[StoryEntry]:
        entries: list[StoryEntry] = []
        for logical, (category, relative) in manifest.items():
            reference = self._choose_reference(category, references.get(logical, ()))
            character = (
                self.characters.get(reference.character_id)
                if reference is not None and reference.character_id is not None
                else None
            )
            entries.append(StoryEntry(
                category=category,
                relative_dir=relative,
                logical_path=logical,
                quest_id=reference.quest_id if reference else None,
                title=reference.title if reference else None,
                character_id=reference.character_id if reference else None,
                character_code=character.code if character else None,
                character_name=character.name if character else None,
                episode=reference.episode if reference else None,
                order=reference.order if reference else (),
            ))
        category_order = {name: index for index, name in enumerate(CATEGORIES)}
        entries.sort(key=lambda entry: (
            category_order[entry.category],
            0 if entry.order else 1,
            entry.order,
            entry.relative_dir,
        ))
        return entries

    def select_character(self, query: str) -> list[StoryEntry]:
        normalized = query.strip()
        exact_id = self.characters.get(normalized)
        if exact_id is not None:
            matches = [exact_id]
        else:
            code_matches = [
                info for info in self.characters.values()
                if info.code.casefold() == normalized.casefold()
            ]
            matches = code_matches or [
                info for info in self.characters.values() if info.name == normalized
            ]
        if not matches:
            raise LookupError(f"character not found: {query}")

        story_character_ids = {
            entry.character_id for entry in self.entries
            if entry.category == "character_story_quest" and entry.character_id
        }
        story_family_roots = {
            self.characters[character_id].identity_character_id
            for character_id in story_character_ids
            if character_id in self.characters
        }
        roots = {
            info.identity_character_id
            for info in matches
            if info.identity_character_id in story_family_roots
        }
        if not roots:
            raise LookupError(f"character has no personal stories: {query}")
        if len(roots) != 1:
            choices = ", ".join(sorted(roots))
            raise LookupError(f"character name is ambiguous: {query} (identity ids: {choices})")
        root = next(iter(roots))
        family_ids = {
            info.character_id for info in self.characters.values()
            if info.identity_character_id == root and info.character_id in story_character_ids
        }
        selected = [
            entry for entry in self.entries
            if entry.category == "character_story_quest"
            and entry.character_id in family_ids
        ]
        selected.sort(key=lambda entry: (
            int(entry.character_id) if entry.character_id and entry.character_id.isdigit() else 0,
            entry.episode or 0,
            entry.relative_dir,
        ))
        return selected

    def select_quest(self, query: str) -> StoryEntry:
        normalized = query.strip().replace("\\", "/").strip("/")
        exact: list[StoryEntry] = []
        for entry in self.entries:
            logical_no_master = entry.logical_path.removeprefix("master/")
            logical_no_suffix = logical_no_master.removesuffix("/scenario.orderedmap")
            forms = {
                entry.logical_path,
                logical_no_master,
                logical_no_suffix,
                f"{entry.category}/{entry.relative_dir}",
                entry.relative_dir,
            }
            if normalized in forms:
                exact.append(entry)
        if len(exact) == 1:
            return exact[0]
        if len(exact) > 1:
            raise LookupError(self._ambiguous_quest_message(query, exact))

        basename_matches = [
            entry for entry in self.entries
            if entry.relative_dir.rsplit("/", 1)[-1] == normalized
        ]
        if len(basename_matches) == 1:
            return basename_matches[0]
        if len(basename_matches) > 1:
            raise LookupError(self._ambiguous_quest_message(query, basename_matches))
        raise LookupError(f"scenario quest not found: {query}")

    @staticmethod
    def _ambiguous_quest_message(
        query: str, candidates: Sequence[StoryEntry]
    ) -> str:
        choices = ", ".join(
            f"{entry.category}/{entry.relative_dir}" for entry in candidates
        )
        return f"scenario quest is ambiguous: {query}; candidates: {choices}"

    def select_category(self, category: str) -> list[StoryEntry]:
        if category not in CATEGORIES:
            raise LookupError(
                f"unknown story category {category!r}; choose one of {', '.join(CATEGORIES)}"
            )
        return [entry for entry in self.entries if entry.category == category]


def read_story(
    store: Path, entry: StoryEntry
) -> list[ScenarioCommand]:
    """Read and decode one catalog entry while checking its authoritative key."""

    path = core.table_path(store, entry.logical_path)
    if not path.is_file():
        raise FileNotFoundError(f"scenario store file does not exist: {entry.logical_path} ({path})")
    outer_key, commands = decode_scenario_bytes(path.read_bytes(), entry.logical_path)
    expected = entry.logical_path.removeprefix("master/").removesuffix(".orderedmap")
    if outer_key != expected:
        raise ValueError(
            f"{entry.logical_path}: outer key {outer_key!r} != expected {expected!r}"
        )
    return commands


def validate_catalog(
    catalog: StoryCatalog,
    speakers: Mapping[str, Speaker],
    *,
    expected_category_counts: Mapping[str, int] | None = None,
) -> ValidationReport:
    """Decode every manifest scenario without creating an output directory."""

    category_counts = Counter(entry.category for entry in catalog.entries)
    contract_errors: list[str] = []
    if expected_category_counts is not None:
        for category in CATEGORIES:
            expected = expected_category_counts.get(category, 0)
            actual = category_counts.get(category, 0)
            if actual != expected:
                contract_errors.append(
                    f"category {category}: expected {expected}, got {actual}"
                )
        expected_total = sum(expected_category_counts.values())
        if len(catalog.entries) != expected_total:
            contract_errors.append(
                f"scenario total: expected {expected_total}, got {len(catalog.entries)}"
            )
        for logical in getattr(catalog, "pathlist_duplicates", ()):
            contract_errors.append(f"duplicate pathlist scenario: {logical}")
        for logical in getattr(catalog, "pathlist_rejected_story_lines", ()):
            contract_errors.append(f"invalid pathlist scenario: {logical}")

    failures: dict[str, str] = {}
    unknown: Counter[int] = Counter()
    unresolved: Counter[str] = Counter()
    missing_titles = tuple(
        entry.logical_path for entry in catalog.entries if not entry.title
    )
    decoded = 0
    instruction_total = 0
    dialogue_total = 0
    for entry in catalog.entries:
        try:
            commands = read_story(catalog.store, entry)
        except Exception as exc:
            failures[entry.logical_path] = f"{type(exc).__name__}: {exc}"
            continue
        decoded += 1
        instruction_total += len(commands)
        for command in commands:
            if command.op == "unknown":
                unknown[command.kind] += 1
            if command.op == "Text":
                dialogue_total += 1
                code = command.args["text_character_id"]
                if code and code not in speakers:
                    unresolved[code] += 1

    return ValidationReport(
        scenario_total=len(catalog.entries),
        decoded=decoded,
        instruction_total=instruction_total,
        dialogue_total=dialogue_total,
        category_counts=dict(sorted(category_counts.items())),
        manifest_contract_errors=tuple(contract_errors),
        decode_failures=dict(sorted(failures.items())),
        unknown_opcodes=dict(sorted(unknown.items())),
        unresolved_speakers=dict(sorted(unresolved.items())),
        title_association_missing=missing_titles,
        referenced_not_in_pathlist=tuple(catalog.referenced_not_in_pathlist),
        unreferenced_pathlist=tuple(catalog.unreferenced_pathlist),
    )


def print_validation_report(report: ValidationReport) -> None:
    print(f"scenario: {report.decoded}/{report.scenario_total} decoded")
    print("category counts:")
    for category in CATEGORIES:
        print(f"- {category}: {report.category_counts.get(category, 0)}")
    print(f"instructions: {report.instruction_total}")
    print(f"dialogue: {report.dialogue_total}")
    print(f"manifest contract errors ({len(report.manifest_contract_errors)}):")
    for error in report.manifest_contract_errors:
        print(f"- {error}")
    print(f"decode failures ({len(report.decode_failures)}):")
    for logical, error in report.decode_failures.items():
        print(f"- {logical}: {error}")
    print(f"unknown opcodes ({sum(report.unknown_opcodes.values())} rows):")
    for kind, count in report.unknown_opcodes.items():
        print(f"- kind={kind}: {count}")
    print(f"unresolved speakers ({sum(report.unresolved_speakers.values())} rows):")
    for code, count in report.unresolved_speakers.items():
        print(f"- {code}: {count}")
    print(f"title association missing ({len(report.title_association_missing)}):")
    for logical in report.title_association_missing:
        print(f"- {logical}")
    print(
        f"referenced but not in pathlist "
        f"({len(report.referenced_not_in_pathlist)}):"
    )
    for logical in report.referenced_not_in_pathlist:
        print(f"- {logical}")
    print(f"pathlist without reference ({len(report.unreferenced_pathlist)}):")
    for logical in report.unreferenced_pathlist:
        print(f"- {logical}")
    print(json.dumps(report.summary(), ensure_ascii=False, sort_keys=True))


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _is_reparse_path(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    return bool(is_junction and is_junction())


def _safe_output_dir(root: Path, entry: StoryEntry, store: Path) -> Path:
    resolved_root = root.resolve()
    resolved_store = store.resolve()
    if _is_within(resolved_root, resolved_store):
        raise ValueError(
            f"--out must not equal or be inside the read-only store: {resolved_root}"
        )
    if entry.category not in CATEGORIES:
        raise ValueError(f"unsafe story output category: {entry.category!r}")

    relative = Path(entry.relative_dir.replace("\\", "/"))
    if (
        relative.is_absolute()
        or not relative.parts
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        raise ValueError(
            f"scenario output traversal is not allowed: {entry.relative_dir!r}"
        )

    lexical_target = resolved_root / entry.category / relative
    current = resolved_root
    for part in (Path(entry.category) / relative).parts:
        current /= part
        if (current.exists() or current.is_symlink()) and _is_reparse_path(current):
            raise ValueError(f"scenario output path contains a link/reparse point: {current}")

    target = lexical_target.resolve()
    if not _is_within(target, resolved_root):
        raise ValueError(
            f"scenario output escapes --out: {entry.relative_dir!r}"
        )
    if _is_within(target, resolved_store):
        raise ValueError(f"scenario output would write inside the read-only store: {target}")
    return target


def _safe_output_file(root: Path, target: Path, store: Path) -> Path:
    resolved_root = root.resolve()
    resolved_store = store.resolve()
    if (target.exists() or target.is_symlink()) and _is_reparse_path(target):
        raise ValueError(f"scenario output file is a link/reparse point: {target}")
    if target.exists() and not target.is_file():
        raise ValueError(f"scenario output target is not a regular file: {target}")
    resolved_target = target.resolve()
    if not _is_within(resolved_target, resolved_root):
        raise ValueError(f"scenario output file escapes --out: {target}")
    if _is_within(resolved_target, resolved_store):
        raise ValueError(
            f"scenario output file would overwrite the read-only store: {target}"
        )
    return target


def export_entries(
    entries: Sequence[StoryEntry],
    store: Path,
    speakers: Mapping[str, Speaker],
    out: Path,
    output_format: str = "both",
) -> list[Path]:
    """Write selected exports; never writes to ``store``."""

    if output_format not in {"md", "jsonl", "both"}:
        raise ValueError(f"unsupported story output format: {output_format}")
    out = Path(out)
    store = Path(store).resolve()
    prepared: list[tuple[Path, str]] = []
    for entry in entries:
        target_dir = _safe_output_dir(out, entry, store)
        commands = read_story(store, entry)
        if output_format in {"md", "both"}:
            target = _safe_output_file(
                out, target_dir / "scenario.md", store
            )
            prepared.append((target, render_markdown(entry, commands, speakers)))
        if output_format in {"jsonl", "both"}:
            target = _safe_output_file(
                out, target_dir / "scenario.jsonl", store
            )
            prepared.append((target, render_jsonl(commands, speakers)))

    staged: list[tuple[Path, Path]] = []
    backups: dict[Path, Path | None] = {}
    retained_backups: set[Path] = set()
    try:
        for target, content in prepared:
            target.parent.mkdir(parents=True, exist_ok=True)
            _safe_output_file(out, target, store)
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
            )
            temporary = Path(temporary_name)
            staged.append((temporary, target))
            with os.fdopen(
                descriptor, "w", encoding="utf-8", newline="\n"
            ) as stream:
                stream.write(content)
        for _, target in staged:
            if target in backups:
                raise ValueError(f"duplicate scenario output target: {target}")
            if not target.exists():
                backups[target] = None
                continue
            descriptor, backup_name = tempfile.mkstemp(
                prefix=f".{target.name}.", suffix=".backup", dir=target.parent
            )
            os.close(descriptor)
            backup = Path(backup_name)
            backups[target] = backup
            shutil.copy2(target, backup)

        committed: list[Path] = []
        try:
            for temporary, target in staged:
                os.replace(temporary, target)
                committed.append(target)
        except Exception as commit_error:
            rollback_errors: list[str] = []
            for target in reversed(committed):
                backup = backups[target]
                try:
                    if backup is None:
                        target.unlink(missing_ok=True)
                    else:
                        os.replace(backup, target)
                except OSError as rollback_error:
                    if backup is not None and backup.exists():
                        retained_backups.add(backup)
                        recovery = f"; recovery backup retained at {backup}"
                    else:
                        recovery = "; no recovery backup is available"
                    rollback_errors.append(
                        f"{target}: {rollback_error}{recovery}"
                    )
            if rollback_errors:
                raise RuntimeError(
                    "scenario export commit failed and rollback was incomplete: "
                    + "; ".join(rollback_errors)
                ) from commit_error
            raise
        return [target for _, target in staged]
    finally:
        for temporary, _ in staged:
            temporary.unlink(missing_ok=True)
        for backup in backups.values():
            if backup is not None and backup not in retained_backups:
                backup.unlink(missing_ok=True)


def _print_story_list(entries: Sequence[StoryEntry]) -> None:
    print("quest_id\ttitle\tcharacter_name\tscenario")
    for entry in entries:
        print("\t".join((
            entry.quest_id or "",
            entry.title or entry.relative_dir.rsplit("/", 1)[-1],
            entry.character_name or "",
            entry.relative_dir,
        )))


def configure_cli_streams() -> None:
    """Make Unicode CLI output deterministic on Windows and redirected pipes."""

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError, ValueError):
            # StringIO/test adapters and already-detached streams may not allow it.
            continue


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export World Flipper CN story scenarios (read-only store access)."
    )
    selectors = parser.add_mutually_exclusive_group(required=True)
    selectors.add_argument(
        "--list",
        nargs="?",
        const="all",
        metavar="CATEGORY",
        help="list stories, optionally limited to one category",
    )
    selectors.add_argument("--character", metavar="CODE|ID|CN_NAME")
    selectors.add_argument("--quest", metavar="SCENARIO_DIR")
    selectors.add_argument("--category", choices=CATEGORIES)
    selectors.add_argument("--all", dest="all_stories", action="store_true")
    selectors.add_argument("--validate", action="store_true")
    parser.add_argument("--format", choices=("md", "jsonl", "both"), default="both")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--store", type=Path, default=DEFAULT_STORE)
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    pathlist: Path | None = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        selected_pathlist = pathlist if pathlist is not None else DEFAULT_PATHLIST
        catalog = StoryCatalog(args.store, selected_pathlist)
        if args.list is not None:
            entries = (
                catalog.entries
                if args.list == "all"
                else catalog.select_category(args.list)
            )
            _print_story_list(entries)
            return 0

        speakers = load_speakers(catalog.store)
        if args.validate:
            expected_counts = (
                EXPECTED_CATEGORY_COUNTS
                if catalog.pathlist == Path(DEFAULT_PATHLIST).resolve()
                else None
            )
            report = validate_catalog(
                catalog,
                speakers,
                expected_category_counts=expected_counts,
            )
            print_validation_report(report)
            return 0 if report.ok else 1

        if args.character is not None:
            entries = catalog.select_character(args.character)
        elif args.quest is not None:
            entries = [catalog.select_quest(args.quest)]
        elif args.category is not None:
            entries = catalog.select_category(args.category)
        elif args.all_stories:
            entries = list(catalog.entries)
        else:  # pragma: no cover - argparse's required group makes this unreachable.
            raise ValueError("no story selector was provided")

        written = export_entries(
            entries,
            catalog.store,
            speakers,
            args.out,
            args.format,
        )
        print(json.dumps({
            "files": len(written),
            "out": str(args.out.resolve()),
            "stories": len(entries),
        }, ensure_ascii=False, sort_keys=True))
        return 0
    except (LookupError, OSError, RuntimeError, UnicodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    configure_cli_streams()
    raise SystemExit(main())
