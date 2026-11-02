# -*- coding: utf-8 -*-
"""Read-only native boss-bundle primitives for the rogue tower.

The terrain's active ``objectgroup`` layers are the source of truth.  Zone rows
that are not named by the terrain are deliberately invisible here: treating
them as live entities is how decorative/inactive bosses leaked into the old
pool and HP accounting.

This module is intentionally independent from :mod:`wf_rogue_build`.  Callers
inject already-loaded master tables (and, when needed, existing level/funnel
adapters), which keeps the immutable model usable by the builder, audit tools,
and tests without a circular import.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import unicodedata
import zlib
from collections import Counter
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Mapping

import wf_dsl
import wf_dsl_sig
import wf_quest_lib as q


SLOT_COLUMNS = ((23, 24, 25, 26),
                (27, 28, 29, 30),
                (31, 32, 33, 34))

KIND_TABLES = {
    0: "standard_boss",
    1: "general_boss",
    2: "kraken",
    3: "orochi",
    4: "orochi_ex",
    6: "conductor",
    7: "touyakiren_ceo",
    # ConcertedBoss uses the verified GeneralBoss source path.
    8: "general_boss",
    9: "water_sphere",
    10: "holy_sphere",
    11: "wind_sphere",
    12: "thunder_sphere",
    13: "fire_sphere",
}

MULTI_ONLY_REGRESSION = frozenset({
    "alter_sheep_materia_multi",
    "alter_sheep_materia_multi_80",
    "devil_commander_evil_envy_80",
    "discarded_dragon_wind",
    "mechanic_dragon_eater_multi",
    "mechanic_dragon_eater_multi_80",
})

OROCHI_PARENT_VARIANTS = {
    "orochi_all_head_single": "single",
    "orochi_all_head_multi": "multi",
    "orochi_all_head_multi_plus": "multi_plus",
}

# Only these schemas have an established numeric difficulty suffix contract in
# the existing tower tooling.  A global ``*_N`` heuristic destroys ordinary
# story scenes (valen_20_08/09/10, main_*), so unknown names never collapse.
GRADE_SUFFIX_PREFIXES = (
    "multi_normal_", "multi_variant_", "advent_event_discarded_dragon_",
)

TABLE_LOGICALS = {
    "standard_boss": "master/battle/boss/standard_boss.orderedmap",
    "general_boss": "master/battle/boss/general_boss.orderedmap",
    "kraken": "master/battle/boss/kraken.orderedmap",
    "orochi": "master/battle/boss/orochi.orderedmap",
    "orochi_ex": "master/battle/boss/orochi_ex.orderedmap",
    "conductor": "master/battle/boss/conductor.orderedmap",
    "touyakiren_ceo": "master/battle/boss/touyakiren_ceo.orderedmap",
    "water_sphere": "master/battle/boss/water_sphere.orderedmap",
    "holy_sphere": "master/battle/boss/holy_sphere.orderedmap",
    "wind_sphere": "master/battle/boss/wind_sphere.orderedmap",
    "thunder_sphere": "master/battle/boss/thunder_sphere.orderedmap",
    "fire_sphere": "master/battle/boss/fire_sphere.orderedmap",
}


@dataclass(frozen=True)
class BossRef:
    kind: int
    code: str


@dataclass(frozen=True)
class ActiveBossSlot:
    layer: str
    slot: int
    boss_group_kind: int
    single: BossRef | None
    multi: BossRef | None


@dataclass(frozen=True)
class TerrainLayerCaps:
    layer: str
    boss_slots: tuple[int, ...]
    boss_group_kinds: tuple[int, ...]
    funnel_groups: tuple[tuple[str, int], ...]
    custom_positions: tuple[tuple[str, int], ...]
    boss_groups: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class SpawnedRef:
    """One action-closure dependency which must exist at the enemy level."""

    source_kind: str
    code: str


@dataclass(frozen=True)
class FunnelRequirement:
    """Maximum proved simultaneous use of one terrain FUNNEL_SPAWN group."""

    group: str
    max_commands: int
    codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class LayerTerrainRequirements:
    layer: str
    funnels: tuple[FunnelRequirement, ...] = ()
    custom_positions: tuple[str, ...] = ()
    spawned_refs: tuple[SpawnedRef, ...] = ()


@dataclass(frozen=True)
class BossTerrainRequirements:
    layers: tuple[LayerTerrainRequirements, ...] = ()
    action_roots: tuple[str, ...] = ()
    action_closure: tuple[str, ...] = ()


@dataclass(frozen=True)
class RequirementResult:
    ok: bool
    requirements: BossTerrainRequirements | None = None
    reason: str | None = None
    detail: str = ""


@dataclass(frozen=True)
class CompatibilityResult:
    ok: bool
    reason: str | None = None
    detail: str = ""
    source_field: str = ""
    target_field: str = ""


@dataclass(frozen=True)
class NativeBossBundle:
    family_id: str
    family_name: str
    variant_id: str
    variant_name: str
    source_field: str
    source_zone: str
    terrain_logical: str
    active_layers: tuple[str, ...]
    slots: tuple[ActiveBossSlot, ...]
    bgm: str | None
    thumbnail: str
    source_category: str
    portable: bool = True
    native_only_reason: str | None = None
    terrain_caps: tuple[TerrainLayerCaps, ...] = ()
    active_zone_rows: tuple[tuple[str, tuple[str, ...]], ...] = ()
    selected_levels: tuple[tuple[str, int, int], ...] = ()
    metadata_aliases: tuple[tuple[str, str, str], ...] = ()
    source_level: int = 0
    terrain_requirements: BossTerrainRequirements | None = None


@dataclass(frozen=True)
class RealizedBundle:
    """Immutable realized snapshot; later tasks add validation fingerprints."""

    source: NativeBossBundle
    target_field: str
    target_zone: str
    terrain_logical: str
    active_layers: tuple[str, ...]
    slots: tuple[ActiveBossSlot, ...]
    enemy_level: int
    clone_map: tuple[tuple[str, str], ...] = ()
    dependency_rows: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class GateResult:
    ok: bool
    reason: str | None = None
    selected_level: int | None = None
    source_table: str | None = None
    detail: str = ""


@dataclass(frozen=True)
class BundleRejection:
    source_field: str
    source_zone: str | None
    reason: str
    detail: str = ""
    boss_refs: tuple[BossRef, ...] = ()
    family_id: str | None = None
    variant_id: str | None = None


@dataclass(frozen=True)
class BundleCatalog:
    """Post-gate selection index plus a separate discovered audit index."""

    family_ids: tuple[str, ...]
    variants: dict[str, tuple[str, ...]]
    bundles: dict[str, tuple[NativeBossBundle, ...]]
    family_names: dict[str, str]
    variant_names: dict[str, str]
    rejections: tuple[BundleRejection, ...]
    discovered_family_ids: tuple[str, ...]
    discovered_variants: dict[str, tuple[str, ...]]
    discovered_bundles: dict[str, tuple[NativeBossBundle, ...]]
    scanned_fields: int = 0
    scanned_active_fields: int = 0
    eligible_source_fields: tuple[str, ...] = ()
    scanned_single_refs: tuple[BossRef, ...] = ()
    multi_only_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class BundleSelection:
    family_id: str
    variant_id: str
    bundle: NativeBossBundle


class TerrainGateError(ValueError):
    """Fail-closed terrain/zone parse error with a stable reason code."""

    def __init__(self, reason: str, detail: str):
        super().__init__(f"{reason}: {detail}")
        self.reason = reason
        self.detail = detail


def _cells(leaf: Any) -> list[str]:
    if isinstance(leaf, (bytes, bytearray)):
        line = bytes(leaf).decode("utf-8")
    elif isinstance(leaf, str):
        line = leaf
    else:
        raise TerrainGateError(
            "TERRAIN_PARSE", f"row type is {type(leaf).__name__}, expected CSV leaf")
    try:
        return next(csv.reader(io.StringIO(line)))
    except (csv.Error, StopIteration) as exc:
        raise TerrainGateError("TERRAIN_PARSE", "malformed CSV row") from exc


@lru_cache(maxsize=2048)
def load_store_terrain(terrain_logical: str) -> dict:
    """Load one Tiled terrain tree from the configured store (read-only)."""

    logical = str(terrain_logical)
    if not logical.endswith(".amf3.deflate"):
        logical += ".amf3.deflate"
    packed = q.read_raw(logical)
    try:
        raw = zlib.decompress(packed, -15)
        parsed = wf_dsl.parse_dsl(raw)
    except (zlib.error, ValueError, TypeError, KeyError) as exc:
        raise TerrainGateError("TERRAIN_PARSE", f"cannot decode {logical}") from exc
    tree = parsed.get("tree") if isinstance(parsed, dict) else None
    if not isinstance(tree, dict):
        raise TerrainGateError("TERRAIN_PARSE", f"{logical} has no terrain tree")
    return tree


def _terrain_tree(value: Any) -> dict:
    """Normalize an injected loader result to the parsed Tiled root."""

    if isinstance(value, Path):
        value = value.read_bytes()
    if isinstance(value, (bytes, bytearray)):
        packed = bytes(value)
        try:
            raw = zlib.decompress(packed, -15)
        except zlib.error:
            raw = packed
        try:
            value = wf_dsl.parse_dsl(raw)
        except (ValueError, TypeError, KeyError) as exc:
            raise TerrainGateError("TERRAIN_PARSE", "terrain AMF3 is malformed") from exc
    if isinstance(value, dict) and isinstance(value.get("tree"), dict):
        value = value["tree"]
    if not isinstance(value, dict):
        raise TerrainGateError("TERRAIN_PARSE", "terrain loader returned no mapping")
    return value


def _field_context(field_id: str, field_data: Mapping[str, Any],
                   zone: Mapping[str, Any]) -> tuple[str, str, Mapping[str, Any]]:
    row = field_data.get(str(field_id))
    if row is None or isinstance(row, Mapping):
        raise TerrainGateError("TERRAIN_PARSE", f"field_data[{field_id}] missing or nested")
    cells = _cells(row)
    if len(cells) < 3 or not cells[1] or not cells[2]:
        raise TerrainGateError("TERRAIN_PARSE", f"field_data[{field_id}] lacks terrain/zone")
    terrain_logical, zone_id = cells[1], cells[2]
    zone_node = zone.get(zone_id)
    if not isinstance(zone_node, Mapping):
        raise TerrainGateError("TERRAIN_PARSE", f"zone[{zone_id}] missing or not nested")
    return terrain_logical, zone_id, zone_node


def _active_layers(tree: Mapping[str, Any], zone_node: Mapping[str, Any]) \
        -> tuple[tuple[str, tuple[Mapping[str, Any], ...]], ...]:
    layers = tree.get("layers")
    if not isinstance(layers, list):
        raise TerrainGateError("TERRAIN_PARSE", "terrain.layers is not a list")
    groups: list[tuple[str, tuple[Mapping[str, Any], ...]]] = []
    seen: set[str] = set()
    for raw_layer in layers:
        if not isinstance(raw_layer, Mapping):
            raise TerrainGateError("TERRAIN_PARSE", "terrain layer is not a mapping")
        if raw_layer.get("type") != "objectgroup":
            continue
        name = raw_layer.get("name")
        if not isinstance(name, str) or not name.isdigit() or int(name) < 0:
            raise TerrainGateError(
                "TERRAIN_PARSE", f"objectgroup.name must be a non-negative integer: {name!r}")
        if name in seen:
            raise TerrainGateError("TERRAIN_PARSE", f"duplicate objectgroup layer {name}")
        seen.add(name)
        # A terrain layer without a matching zone row is an incomplete native bundle.
        # Extra zone rows are intentionally ignored (treasure_cave_area regression).
        if name not in zone_node:
            raise TerrainGateError("TERRAIN_PARSE", f"terrain layer {name} has no zone row")
        objects = raw_layer.get("objects", [])
        if not isinstance(objects, list) or any(not isinstance(obj, Mapping) for obj in objects):
            raise TerrainGateError("TERRAIN_PARSE", f"layer {name} objects are malformed")
        groups.append((name, tuple(objects)))
    if not groups:
        raise TerrainGateError("NO_ACTIVE_LAYER", "terrain has no active objectgroup layer")
    return tuple(sorted(groups, key=lambda item: int(item[0])))


def _parse_int(value: Any, *, default: int | None = None,
               context: str) -> int:
    text = "" if value is None else str(value).strip()
    if text in ("", "(None)") and default is not None:
        return default
    try:
        return int(text)
    except (TypeError, ValueError) as exc:
        raise TerrainGateError("TERRAIN_PARSE", f"{context} is not an integer: {value!r}") from exc


def _ref(kind: Any, code: Any, *, context: str) -> BossRef | None:
    code_text = "" if code is None else str(code).strip()
    kind_text = "" if kind is None else str(kind).strip()
    if code_text in ("", "(None)"):
        if kind_text not in ("", "(None)"):
            raise TerrainGateError("TERRAIN_PARSE", f"{context} has kind but no code")
        return None
    if kind_text in ("", "(None)"):
        raise TerrainGateError("TERRAIN_PARSE", f"{context} has code but no BossKind")
    return BossRef(_parse_int(kind_text, context=f"{context}.kind"), code_text)


def _row_slots(layer: str, row: Any) -> tuple[ActiveBossSlot, ...]:
    cells = _cells(row)
    if len(cells) <= 34:
        raise TerrainGateError("TERRAIN_PARSE", f"zone layer {layer} has fewer than 35 columns")
    group_kind = _parse_int(cells[22], default=0, context=f"zone[{layer}].c22")
    out: list[ActiveBossSlot] = []
    for slot, (single_kind, single_code, multi_kind, multi_code) in enumerate(
            SLOT_COLUMNS, start=1):
        single = _ref(cells[single_kind], cells[single_code],
                      context=f"zone[{layer}].slot{slot}.single")
        multi = _ref(cells[multi_kind], cells[multi_code],
                     context=f"zone[{layer}].slot{slot}.multi")
        if single is not None or multi is not None:
            out.append(ActiveBossSlot(layer, slot, group_kind, single, multi))
    return tuple(out)


def _object_caps(objects: tuple[Mapping[str, Any], ...]) \
        -> tuple[tuple[tuple[str, int], ...], tuple[tuple[str, int], ...],
                 tuple[tuple[str, int], ...]]:
    funnels: Counter[str] = Counter()
    custom_positions: Counter[str] = Counter()
    for obj in objects:
        obj_type = obj.get("type", "")
        if not isinstance(obj_type, str):
            raise TerrainGateError("TERRAIN_PARSE", "terrain object.type is not a string")
        funnel = re.fullmatch(r"FUNNEL_SPAWN(\d+)", obj_type)
        if funnel:
            funnels[funnel.group(1)] += 1
        if obj_type == "CUSTOM_POSITION":
            name = obj.get("name")
            if not isinstance(name, str) or not name:
                raise TerrainGateError("TERRAIN_PARSE", "CUSTOM_POSITION has no name")
            custom_positions[name] += 1
    return (
        tuple(sorted(funnels.items(), key=lambda item: int(item[0]))),
        # Repeated named anchors are legal and materially different from one
        # anchor.  Preserve counts for later exact-one/count compatibility.
        tuple(sorted(custom_positions.items())),
        # The client derives BossGroup topology from zone c22 + active slots.
        # The official terrain corpus has no BOSS_GROUP object contract; never
        # invent one from similarly named custom objects.
        (),
    )


def load_terrain_layer_caps(field_id: str, field_data: Mapping[str, Any],
                            zone: Mapping[str, Any],
                            terrain_loader: Callable[[str], Any]) \
        -> tuple[TerrainLayerCaps, ...]:
    """Parse terrain capabilities for actual active layers only.

    ``terrain_loader`` receives field_data c1 without an added suffix.  The
    bundled :func:`load_store_terrain` handles the ``.amf3.deflate`` suffix and
    raw-deflate decoding; tests may inject an already parsed tree.
    """

    terrain_logical, _zone_id, zone_node = _field_context(field_id, field_data, zone)
    try:
        tree = _terrain_tree(terrain_loader(terrain_logical))
    except TerrainGateError:
        raise
    except Exception as exc:
        raise TerrainGateError(
            "TERRAIN_PARSE", f"terrain loader failed for {terrain_logical}") from exc
    out: list[TerrainLayerCaps] = []
    for layer, objects in _active_layers(tree, zone_node):
        slots = _row_slots(layer, zone_node[layer])
        funnels, positions, boss_groups = _object_caps(objects)
        occupied = tuple(slot.slot for slot in slots)
        group_kinds = tuple(sorted({slot.boss_group_kind for slot in slots}))
        out.append(TerrainLayerCaps(
            layer=layer,
            boss_slots=occupied,
            boss_group_kinds=group_kinds,
            funnel_groups=funnels,
            custom_positions=positions,
            boss_groups=boss_groups,
        ))
    return tuple(out)


def active_boss_slots(field_id: str, field_data: Mapping[str, Any],
                      zone: Mapping[str, Any],
                      terrain_loader: Callable[[str], Any]) \
        -> tuple[ActiveBossSlot, ...]:
    """Return complete single/multi BossKind references in active layer order."""

    _terrain_logical, _zone_id, zone_node = _field_context(field_id, field_data, zone)
    caps = load_terrain_layer_caps(field_id, field_data, zone, terrain_loader)
    out: list[ActiveBossSlot] = []
    for cap in caps:
        out.extend(_row_slots(cap.layer, zone_node[cap.layer]))
    return tuple(out)


@lru_cache(maxsize=8192)
def load_store_action(program: str) -> Any:
    """Read one enemy action DSL tree from store without mutating it."""

    logical = str(program)
    if not logical.endswith(".action.dsl.amf3.deflate"):
        logical += ".action.dsl.amf3.deflate"
    return _decoded_store_tree(logical)


@lru_cache(maxsize=512)
def load_store_esdl(logical: str) -> Any:
    """Read one StandardEnemy ESDL using its required double extension."""

    path = str(logical)
    if not path.endswith(".esdl.amf3.deflate"):
        path += ".esdl.amf3.deflate"
    return _decoded_store_tree(path)


def _decoded_store_tree(logical: str) -> Any:
    packed = q.read_raw(logical)
    try:
        raw = zlib.decompress(packed, -15)
        parsed = wf_dsl.parse_dsl(raw)
    except (zlib.error, ValueError, TypeError, KeyError) as exc:
        raise ValueError(f"cannot decode DSL resource {logical}") from exc
    return parsed.get("tree") if isinstance(parsed, Mapping) else None


def _loaded_tree(value: Any) -> Any:
    """Normalize injected parsed trees and raw-deflate AMF3 resources."""

    if isinstance(value, Path):
        value = value.read_bytes()
    if isinstance(value, (bytes, bytearray)):
        raw = bytes(value)
        try:
            raw = zlib.decompress(raw, -15)
        except zlib.error:
            pass
        value = wf_dsl.parse_dsl(raw)
    if isinstance(value, Mapping) and "tree" in value:
        value = value["tree"]
    return value


class _ClosureError(ValueError):
    pass


@dataclass
class _ActionSummary:
    funnels: Counter[str]
    funnel_codes: dict[str, set[str]]
    positions: set[str]
    spawned_refs: set[SpawnedRef]
    nested_actions: Counter[str]
    action_closure: list[str]

    @classmethod
    def empty(cls) -> "_ActionSummary":
        return cls(Counter(), {}, set(), set(), Counter(), [])

    def has_runtime_requirements(self) -> bool:
        return bool(self.funnels or self.positions or self.spawned_refs
                    or self.nested_actions)


def _extend_action_closure(target: list[str], values: list[str]) -> None:
    seen = set(target)
    for path in values:
        if path not in seen:
            target.append(path)
            seen.add(path)


def _summary_add(left: _ActionSummary, right: _ActionSummary) -> _ActionSummary:
    out = _ActionSummary.empty()
    out.funnels = left.funnels + right.funnels
    out.positions = set(left.positions) | set(right.positions)
    out.spawned_refs = set(left.spawned_refs) | set(right.spawned_refs)
    out.nested_actions = left.nested_actions + right.nested_actions
    _extend_action_closure(out.action_closure, left.action_closure)
    _extend_action_closure(out.action_closure, right.action_closure)
    for source in (left.funnel_codes, right.funnel_codes):
        for group, values in source.items():
            out.funnel_codes.setdefault(group, set()).update(values)
    return out


def _summary_sum(values: list[_ActionSummary]) -> _ActionSummary:
    out = _ActionSummary.empty()
    for value in values:
        out = _summary_add(out, value)
    return out


def _summary_max(values: list[_ActionSummary]) -> _ActionSummary:
    """Conservative union with a per-group/path maximum for exclusive arms."""

    out = _ActionSummary.empty()
    for value in values:
        for group, count in value.funnels.items():
            out.funnels[group] = max(out.funnels[group], count)
        for group, codes in value.funnel_codes.items():
            out.funnel_codes.setdefault(group, set()).update(codes)
        for path, count in value.nested_actions.items():
            out.nested_actions[path] = max(out.nested_actions[path], count)
        out.positions.update(value.positions)
        out.spawned_refs.update(value.spawned_refs)
        _extend_action_closure(out.action_closure, value.action_closure)
    return out


def _summary_scale(value: _ActionSummary, count: int) -> _ActionSummary:
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise _ClosureError(f"Repeat count is not a finite literal: {count!r}")
    out = _ActionSummary.empty()
    out.funnels = Counter({key: amount * count
                           for key, amount in value.funnels.items()})
    out.funnel_codes = {key: set(codes)
                        for key, codes in value.funnel_codes.items()}
    out.positions = set(value.positions)
    out.spawned_refs = set(value.spawned_refs)
    out.nested_actions = Counter({key: amount * count
                                  for key, amount in value.nested_actions.items()})
    out.action_closure = list(value.action_closure)
    return out


def _action_path(value: Any, *, command: str) -> str | None:
    text = "" if value is None else str(value).strip()
    if text in ("", "(None)"):
        return None
    if not text.startswith("battle/action/"):
        raise _ClosureError(f"{command} uses a dynamic/relative action path: {text!r}")
    return text.removesuffix(".action.dsl.amf3.deflate")


def _analyze_expression(node: Any) -> _ActionSummary:
    if not isinstance(node, list) or not node or not isinstance(node[0], str):
        raise _ClosureError(f"unknown ActionDsl expression: {node!r}")
    tag = node[0]
    if tag == "Block":
        if len(node) != 2 or not isinstance(node[1], list):
            raise _ClosureError("malformed Block")
        # Commands in a block and sibling event callbacks can overlap; summing
        # is the conservative finite upper bound required by the transplant gate.
        return _summary_sum([_analyze_expression(item) for item in node[1]])
    if tag not in ("Command", "Event") or len(node) != 2:
        raise _ClosureError(f"unknown ActionDsl expression constructor: {tag}")
    body = node[1]
    if not isinstance(body, list) or not body or not isinstance(body[0], str):
        raise _ClosureError(f"malformed {tag}")
    name, args = body[0], body[1:]
    signatures = wf_dsl_sig.COMMANDS if tag == "Command" else wf_dsl_sig.EVENTS
    signature = signatures.get(name)
    if signature is None or len(signature) != len(args):
        raise _ClosureError(
            f"unknown or mismatched {tag} constructor {name}/{len(args)}")
    expression_summaries = [
        _analyze_expression(value)
        for value, value_type in zip(args, signature)
        if value_type == "ActionDslExpression"
    ]
    if tag == "Event":
        if name == "Repeat":
            if len(expression_summaries) != 1:
                raise _ClosureError("Repeat has no single callback")
            # ListeningEvent.as constructor case 1: params[0] is the frame
            # interval, while params[1] becomes evalLimit (the callback count).
            return _summary_scale(expression_summaries[0], args[1])
        if name == "Wait":
            return _summary_sum(expression_summaries)  # callback executes once
        summary = _summary_sum(expression_summaries)
        if summary.has_runtime_requirements():
            # Collision/activation callbacks may fire without a statically
            # bounded count.  Native execution is valid; transplantation is not.
            raise _ClosureError(f"unbounded event callback: {name}")
        return summary

    if name == "CreateSummonsMultiball":
        # ActionEvaluator loops args[0] summons and registers args[11] as an
        # ActivatedMultiball callback.  args[8] is only that event's ID; the
        # summon body's real action comes from MultiballTable[args[1]].action.
        # Until that master-table edge is injected and traversed, this command
        # is not a complete action closure even when its inline callback is empty.
        raise _ClosureError(
            "CreateSummonsMultiball requires unaudited MultiballTable action")

    if name.startswith("Conditionals"):
        summary = _summary_max(expression_summaries)
    else:
        # A command-owned ActionDslExpression is generally a runtime callback,
        # not an exactly-once inline block.  For example CreateReferencePoint
        # iterates over getSubjects and CreateHitArea may invoke on-hit blocks
        # repeatedly.  Until a command-specific finite cardinality is proved,
        # any terrain/spawn requirement inside such a callback is unaudited.
        if any(value.has_runtime_requirements()
               for value in expression_summaries):
            raise _ClosureError(f"unbounded command callback: {name}")
        summary = _summary_sum(expression_summaries)

    if name == "SpawnFunnel":
        kind, amount, point = args[0], args[1], args[2]
        if (not isinstance(kind, list) or len(kind) != 2
                or kind[0] not in ("Funnel", "StandardFunnel", "Zako")
                or not isinstance(kind[1], str) or not kind[1]):
            raise _ClosureError(f"malformed SpawnFunnel kind: {kind!r}")
        if not isinstance(amount, int) or isinstance(amount, bool) or amount < 0:
            raise _ClosureError(f"dynamic SpawnFunnel amount: {amount!r}")
        spawned = SpawnedRef(str(kind[0]), str(kind[1]))
        summary.spawned_refs.add(spawned)
        if not isinstance(point, list) or not point:
            raise _ClosureError(f"malformed SpawnFunnel point: {point!r}")
        if point[0] == "FunnelGroup" and len(point) == 2:
            try:
                group = str(int(point[1]))
            except (TypeError, ValueError) as exc:
                raise _ClosureError(f"dynamic FUNNEL group: {point[1]!r}") from exc
            summary.funnels[group] += amount
            summary.funnel_codes.setdefault(group, set()).add(spawned.code)
        elif point[0] != "Specific":
            raise _ClosureError(f"unknown SpawnFunnel point: {point!r}")
    elif name == "SpawnAlterEgo":
        code, point = args[0], args[1]
        if not isinstance(code, str) or not code:
            raise _ClosureError(f"dynamic SpawnAlterEgo code: {code!r}")
        summary.spawned_refs.add(SpawnedRef("AlterEgo", code))
        if isinstance(point, list) and point:
            if point[0] == "CustomPosition" and len(point) == 2 \
                    and isinstance(point[1], str) and point[1]:
                summary.positions.add(point[1])
            elif point[0] != "UseMasterValue":
                raise _ClosureError(f"unknown SpawnAlterEgo point: {point!r}")
        else:
            raise _ClosureError(f"malformed SpawnAlterEgo point: {point!r}")

    indirect_index = {
        "CreateBombMultiball": 5,
        "CreateTornado": 6,
        "CreateTargetAttack": 4,
    }.get(name)
    if indirect_index is not None:
        path = _action_path(args[indirect_index], command=name)
        if path is not None:
            if name == "CreateBombMultiball":
                count = args[0]
                if (not isinstance(count, int) or isinstance(count, bool)
                        or count < 0):
                    raise _ClosureError(
                        f"dynamic CreateBombMultiball count:{count!r}")
                # One BombMultiball is created for every literal args[0]
                # iteration; each instance receives and can execute args[5].
                summary.nested_actions[path] += count
            elif name == "CreateTornado":
                total_frames, interval = args[4], args[5]
                if (not isinstance(total_frames, int)
                        or isinstance(total_frames, bool)
                        or total_frames < 0
                        or not isinstance(interval, int)
                        or isinstance(interval, bool)
                        or interval <= 0):
                    raise _ClosureError(
                        "dynamic/invalid CreateTornado lifetime:"
                        f"{total_frames!r}/{interval!r}")
                # GeneralBossTornado executes on each interval until its
                # literal totalFrames expires.
                summary.nested_actions[path] += total_frames // interval
            else:  # CreateTargetAttack
                # GeneralBossTarget enters End once and executes the child on
                # End frame 6, giving a proved exactly-once bound.
                summary.nested_actions[path] += 1
    return summary


def _analyze_action_tree(tree: Any) -> _ActionSummary:
    value = _loaded_tree(tree)
    if not isinstance(value, list) or not value or value[0] != "ActionDsl":
        raise _ClosureError("resource is not an ActionDsl root")
    blocks = [item for item in value[1:]
              if isinstance(item, list) and item and item[0] == "Block"]
    if not blocks:
        raise _ClosureError("ActionDsl root has no Block")
    return _summary_sum([_analyze_expression(block) for block in blocks])


def _analyze_action_program(program: str, loader: Callable[[str], Any],
                            visiting: set[str]) -> _ActionSummary:
    clean = str(program).removesuffix(".action.dsl.amf3.deflate")
    if clean in visiting:
        raise _ClosureError(f"cyclic nested action reference: {clean}")
    visiting.add(clean)
    try:
        summary = _analyze_action_tree(loader(clean))
        nested = Counter(summary.nested_actions)
        summary.nested_actions.clear()
        for path, count in sorted(nested.items()):
            child = _analyze_action_program(path, loader, visiting)
            summary = _summary_add(summary, _summary_scale(child, count))
        _extend_action_closure(summary.action_closure, [clean])
        return summary
    except (FileNotFoundError, KeyError, TypeError, ValueError, zlib.error) as exc:
        if isinstance(exc, _ClosureError):
            raise
        raise _ClosureError(f"cannot load action {clean}: {exc}") from exc
    finally:
        visiting.remove(clean)


def audit_action_identity_closure(
        action_roots: tuple[str, ...] | list[str], identifier: str,
        loader: Callable[[str], Any], *, enemy_level: int,
        spawned_ref_gate: Callable[[str, str, int], Any] | None = None) \
        -> GateResult:
    """Prove that a static action closure is independent of one master id.

    Dedicated constructors such as Conductor and TouyakirenCeo keep their
    official field and action resources when the parent table key is cloned.
    That rename is safe only when every action is parseable, every recursively
    referenced action is finite, every spawned enemy resolves at the selected
    level, and no action argument names the old parent id.  Exact string
    matching is intentional: resource paths can share a descriptive stem with
    a boss without being a runtime master-id reference.
    """

    target = str(identifier).strip()
    roots = tuple(dict.fromkeys(
        str(root).removesuffix(".action.dsl.amf3.deflate").strip()
        for root in action_roots if str(root).strip()))
    if not target:
        return GateResult(False, "ACTION_CLOSURE_UNAUDITED",
                          detail="empty identity identifier")
    if not roots:
        return GateResult(False, "ACTION_CLOSURE_UNAUDITED",
                          detail="dedicated boss row has no action roots")
    if not callable(loader):
        return GateResult(False, "ACTION_CLOSURE_UNAUDITED",
                          detail="missing action loader")

    closure: list[str] = []
    spawned: set[SpawnedRef] = set()
    try:
        for root in roots:
            summary = _analyze_action_program(root, loader, set())
            _extend_action_closure(closure, summary.action_closure)
            spawned.update(summary.spawned_refs)

        def walk(value: Any, logical: str) -> None:
            value = _loaded_tree(value)
            if isinstance(value, Mapping):
                for child in value.values():
                    walk(child, logical)
                return
            if isinstance(value, (list, tuple)):
                for child in value:
                    walk(child, logical)
                return
            if isinstance(value, str) and value == target:
                raise _ClosureError(
                    f"action {logical} contains parent master id:{target}")

        for logical in closure:
            walk(loader(logical), logical)
        if spawned and not callable(spawned_ref_gate):
            raise _ClosureError("missing spawned-reference gate")
        for ref in sorted(spawned,
                          key=lambda item: (item.source_kind, item.code)):
            verdict = spawned_ref_gate(
                ref.source_kind, ref.code, int(enemy_level))
            gate = _gate_value(verdict, "REFERENCE")
            if not gate.ok:
                raise _ClosureError(
                    "spawned reference rejected:"
                    f"{ref.source_kind}/{ref.code}:"
                    f"{gate.reason or 'REFERENCE'} {gate.detail}".strip())
    except (TerrainGateError, _ClosureError, FileNotFoundError, KeyError,
            TypeError, ValueError, zlib.error) as exc:
        return GateResult(False, "ACTION_CLOSURE_UNAUDITED", detail=str(exc))
    return GateResult(True, detail=(
        f"actions={len(closure)},spawned={len(spawned)},identity={target}"))


def _selected_level_for_slot(bundle: NativeBossBundle,
                             slot: ActiveBossSlot) -> int | None:
    selected = {(layer, index): level
                for layer, index, level in bundle.selected_levels}
    return selected.get((slot.layer, slot.slot))


def _selected_leaf(table: Mapping[str, Any], ref: BossRef,
                   selected_level: int | None) -> Any:
    node = table.get(ref.code)
    if isinstance(node, Mapping):
        if selected_level is None or str(selected_level) not in node:
            raise _ClosureError(
                f"selected source row missing:{ref.code}@{selected_level}")
        return node[str(selected_level)]
    if selected_level is not None:
        raise _ClosureError(f"selected source is not level-indexed:{ref.code}")
    if node is None:
        raise _ClosureError(f"source row missing:{ref.code}")
    return node


def _state_requirements(routine_id: str, states: Mapping[str, Any]) \
        -> tuple[set[str], set[SpawnedRef]]:
    node = states.get(routine_id)
    if not isinstance(node, Mapping):
        raise _ClosureError(f"general_boss_state routine missing:{routine_id}")
    positions: set[str] = set()
    references: set[SpawnedRef] = set()

    def walk(value: Any) -> None:
        if isinstance(value, Mapping):
            for child in value.values():
                walk(child)
            return
        row = _cells(value)
        if len(row) < 53:
            raise _ClosureError(f"short general_boss_state row:{routine_id}")
        # GeneralBossStateValues: c49 movement kind 0 = Absolute(c50 name).
        if row[49] == "0":
            if row[50] in ("", "(None)"):
                raise _ClosureError(f"absolute movement lacks position:{routine_id}")
            positions.add(row[50])
        # GeneralBossStateValues next_state test kind 15 is
        # GeneralBossAlive(bossId); it is a real string-code dependency.
        if len(row) > 30 and row[29] == "15" and row[30] not in ("", "(None)"):
            references.add(SpawnedRef("GeneralBoss", row[30]))

    walk(node)
    return positions, references


def _standard_esdl_roots(tree: Any) -> tuple[set[str], set[str]]:
    """Harvest proved standard action paths and initial named positions.

    CN ESDL stores the action prefix in ``bH`` and state callbacks as ``i``
    records whose ``b`` member is the suffix.  We intentionally do not guess
    arbitrary strings outside that schema.
    """

    root = _loaded_tree(tree)
    if not isinstance(root, Mapping):
        raise _ClosureError("standard ESDL root is not a mapping")
    prefix = root.get("bH")
    if prefix is not None and (not isinstance(prefix, str)
                               or not prefix.startswith("battle/action/")
                               or not prefix.endswith("$")):
        raise _ClosureError(f"dynamic standard action prefix:{prefix!r}")
    roots: set[str] = set()
    positions: set[str] = set()

    def option_string(value: Any) -> str | None:
        if (isinstance(value, list) and len(value) == 2
                and value[0] == "T1" and isinstance(value[1], str)):
            return value[1]
        return None

    initial = option_string(root.get("ae"))
    if initial:
        positions.add(initial)
    parts = root.get("au")
    if isinstance(parts, list):
        for part in parts:
            if isinstance(part, Mapping):
                position = option_string(part.get("c"))
                if position:
                    positions.add(position)

    def walk(value: Any) -> None:
        if isinstance(value, Mapping):
            callbacks = value.get("i")
            if isinstance(callbacks, list):
                for callback in callbacks:
                    if not isinstance(callback, Mapping):
                        raise _ClosureError("malformed standard action callback")
                    name = callback.get("b")
                    if not isinstance(name, str) or not name:
                        raise _ClosureError("dynamic standard action callback")
                    if name.startswith("battle/action/"):
                        roots.add(name)
                    elif isinstance(prefix, str):
                        roots.add(prefix + name)
                    else:
                        raise _ClosureError(f"callback {name!r} has no action prefix")
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(root)
    return roots, positions


def boss_terrain_requirements(bundle: NativeBossBundle, enemy_level: int,
                              loaders: Mapping[str, Any]) -> RequirementResult:
    """Extract a finite, per-active-layer action/terrain requirement closure.

    Any unknown constructor, resource, dynamic edge, cycle, unbounded event or
    spawned reference becomes ``ACTION_CLOSURE_UNAUDITED``.  This result is a
    portability verdict only; catalog callers must keep the native bundle.
    """

    action_loader = loaders.get("action_loader") or load_store_action
    esdl_loader = loaders.get("esdl_loader") or load_store_esdl
    spawn_gate = loaders.get("spawned_ref_gate")
    general = loaders.get("general_boss")
    standard = loaders.get("standard_boss")
    states = loaders.get("general_boss_state")
    general = general if isinstance(general, Mapping) else {}
    standard = standard if isinstance(standard, Mapping) else {}
    states = states if isinstance(states, Mapping) else {}
    if not callable(action_loader) or not callable(esdl_loader):
        return RequirementResult(False, reason="ACTION_CLOSURE_UNAUDITED",
                                 detail="missing DSL loader")

    layer_summaries: dict[str, _ActionSummary] = {
        layer: _ActionSummary.empty() for layer in bundle.active_layers}
    all_roots: set[str] = set()
    try:
        for slot in bundle.slots:
            ref = slot.single
            if ref is None:
                continue
            if slot.layer not in layer_summaries:
                raise _ClosureError(f"slot belongs to inactive layer:{slot.layer}")
            selected = _selected_level_for_slot(bundle, slot)
            summary = _ActionSummary.empty()
            roots: set[str] = set()
            if ref.kind in (1, 8):
                row = _cells(_selected_leaf(general, ref, selected))
                if len(row) < 161:
                    raise _ClosureError(f"short general_boss row:{ref.code}@{selected}")
                if row[41] not in ("", "(None)"):
                    summary.positions.add(row[41])
                routine = row[42]
                if routine in ("", "(None)"):
                    raise _ClosureError(f"general boss has no routine:{ref.code}")
                state_positions, state_refs = _state_requirements(routine, states)
                summary.positions.update(state_positions)
                summary.spawned_refs.update(state_refs)
                # c109 is always the pre-action path. c110 only says whether it
                # reruns after continue and must never suppress this root.
                for index in (109, *range(111, 161)):
                    value = row[index]
                    if value not in ("", "(None)"):
                        roots.update(item.strip() for item in value.split(",")
                                     if item.strip())
            elif ref.kind == 0:
                row = _cells(_selected_leaf(standard, ref, selected))
                if len(row) < 2 or row[1] in ("", "(None)"):
                    raise _ClosureError(f"standard ESDL path missing:{ref.code}")
                logical = row[1]
                if not logical.endswith(".esdl.amf3.deflate"):
                    logical += ".esdl.amf3.deflate"
                # Task3 v1 cannot claim the full StandardEnemy ESDL schema:
                # root bx carries pre-actions, au[*].g[*].k carries absolute
                # state movement, and form revival positions add another
                # placement channel.  Load the exact double-extension resource
                # to prove it exists, then keep every kind0 bundle native-only
                # until all three channels have a complete schema parser.
                _loaded_tree(esdl_loader(logical))
                raise _ClosureError(
                    "Standard ESDL pre-action/state/revival placement schema unaudited")
            else:
                raise _ClosureError(
                    f"BossKind {ref.kind} action roots are not audited")

            for root in sorted(roots):
                if not root.startswith("battle/action/") and root.startswith("action/"):
                    # Synthetic tests use a short but still static namespace.
                    pass
                elif not root.startswith("battle/action/"):
                    raise _ClosureError(f"dynamic action root:{root!r}")
                summary = _summary_add(
                    summary, _analyze_action_program(root, action_loader, set()))
                all_roots.add(root)
            layer_summaries[slot.layer] = _summary_add(
                layer_summaries[slot.layer], summary)

        refs = {ref for summary in layer_summaries.values()
                for ref in summary.spawned_refs}
        if refs and not callable(spawn_gate):
            raise _ClosureError("missing spawned-reference gate")
        for layer, summary in layer_summaries.items():
            same_layer_general = {
                slot.single.code for slot in bundle.slots
                if slot.layer == layer and slot.single is not None
                and slot.single.kind in (1, 8)}
            same_layer_alter_egos = {
                ref.code for ref in summary.spawned_refs
                if ref.source_kind == "AlterEgo"}
            for ref in sorted(
                    summary.spawned_refs,
                    key=lambda item: (item.source_kind, item.code)):
                if (ref.source_kind == "GeneralBoss"
                        and ref.code not in same_layer_general
                        and ref.code not in same_layer_alter_egos):
                    raise _ClosureError(
                        f"GeneralBossAlive target is not a same-layer member:"
                        f"{layer}/{ref.code}")
                verdict = spawn_gate(ref.source_kind, ref.code, int(enemy_level))
                gate = _gate_value(verdict, "REFERENCE")
                if not gate.ok:
                    raise _ClosureError(
                        f"spawned reference rejected:{ref.source_kind}/{ref.code}:"
                        f"{gate.reason or 'REFERENCE'} {gate.detail}".strip())

        layers: list[LayerTerrainRequirements] = []
        for layer in bundle.active_layers:
            summary = layer_summaries[layer]
            funnels = tuple(FunnelRequirement(
                group, int(summary.funnels[group]),
                tuple(sorted(summary.funnel_codes.get(group, ()))))
                for group in sorted(summary.funnels, key=lambda value: int(value)))
            layers.append(LayerTerrainRequirements(
                layer=layer, funnels=funnels,
                custom_positions=tuple(sorted(summary.positions)),
                spawned_refs=tuple(sorted(
                    summary.spawned_refs,
                    key=lambda item: (item.source_kind, item.code))),
            ))
        action_closure: list[str] = []
        for layer in bundle.active_layers:
            _extend_action_closure(
                action_closure, layer_summaries[layer].action_closure)
        return RequirementResult(
            True, BossTerrainRequirements(
                tuple(layers), tuple(sorted(all_roots)),
                tuple(action_closure)))
    except (TerrainGateError, _ClosureError, FileNotFoundError, KeyError,
            TypeError, ValueError, zlib.error) as exc:
        return RequirementResult(False, reason="ACTION_CLOSURE_UNAUDITED",
                                 detail=str(exc))


def _slots_by_layer(bundle: NativeBossBundle) -> dict[str, tuple[ActiveBossSlot, ...]]:
    return {layer: tuple(sorted(
        (slot for slot in bundle.slots if slot.layer == layer),
        key=lambda slot: slot.slot)) for layer in bundle.active_layers}


def _boss_group_topology(slots: tuple[ActiveBossSlot, ...]) \
        -> tuple[tuple[int, ...], ...]:
    if not slots:
        return ()
    kinds = {slot.boss_group_kind for slot in slots}
    if len(kinds) != 1:
        raise _ClosureError("one zone layer contains multiple c22 values")
    kind = next(iter(kinds))
    occupied = tuple(slot.slot for slot in slots)
    if kind == 0:
        return (occupied,)
    if kind == 1:
        return tuple((slot,) for slot in occupied)
    raise _ClosureError(f"unsupported zone c22 boss_group_kind:{kind}")


def terrain_compatibility(
        source: NativeBossBundle, target: NativeBossBundle,
        requirements: BossTerrainRequirements | RequirementResult,
        *, strict_transplant: bool = False,
        transplant_safe: set[str] | frozenset[str] | tuple[str, ...] = (),
        ) -> CompatibilityResult:
    """Compare transplant safety per aligned active layer, fail closed."""

    def result(ok: bool, reason: str | None = None,
               detail: str = "") -> CompatibilityResult:
        return CompatibilityResult(ok, reason, detail,
                                   source.source_field, target.source_field)

    if isinstance(requirements, RequirementResult):
        if not requirements.ok or requirements.requirements is None:
            return result(False, requirements.reason or "ACTION_CLOSURE_UNAUDITED",
                          requirements.detail)
        requirements = requirements.requirements
    if not isinstance(requirements, BossTerrainRequirements):
        return result(False, "ACTION_CLOSURE_UNAUDITED",
                      "missing BossTerrainRequirements")
    if source.native_only_reason and source.terrain_requirements is None:
        return result(False, source.native_only_reason)
    safe = set(map(str, transplant_safe))
    if strict_transplant:
        codes = [slot.single.code for slot in source.slots
                 if slot.single is not None]
        blocked = sorted(code for code in codes if code not in safe)
        if blocked:
            return result(False, "TRANSPLANT_POLICY",
                          "not in transplant_safe: " + ",".join(blocked))

    source_caps = tuple(sorted(source.terrain_caps, key=lambda cap: int(cap.layer)))
    target_caps = tuple(sorted(target.terrain_caps, key=lambda cap: int(cap.layer)))
    source_layers = tuple(sorted(source.active_layers, key=int))
    target_layers = tuple(sorted(target.active_layers, key=int))
    if (len(source_layers) != len(target_layers)
            or len(source_caps) != len(source_layers)
            or len(target_caps) != len(target_layers)):
        return result(False, "SLOT_SHAPE_MISMATCH",
                      "active layer/capability counts differ")
    source_slots = _slots_by_layer(source)
    target_slots = _slots_by_layer(target)
    req_by_layer = {item.layer: item for item in requirements.layers}

    for index, (source_layer, target_layer) in enumerate(
            zip(source_layers, target_layers)):
        source_layer_slots = source_slots.get(source_layer, ())
        target_layer_slots = target_slots.get(target_layer, ())
        source_shape = tuple(slot.slot for slot in source_layer_slots)
        target_shape = tuple(slot.slot for slot in target_layer_slots)
        if source_shape != target_shape:
            return result(
                False, "SLOT_SHAPE_MISMATCH",
                f"layer {source_layer}->{target_layer}:"
                f" source slots {source_shape}, target slots {target_shape}")
        source_kinds = {slot.boss_group_kind for slot in source_layer_slots}
        target_kinds = {slot.boss_group_kind for slot in target_layer_slots}
        if source_kinds != target_kinds:
            return result(
                False, "BOSS_GROUP_MISMATCH",
                f"layer {source_layer}->{target_layer}:"
                f" source c22={sorted(source_kinds)},"
                f" target c22={sorted(target_kinds)}")
        try:
            source_topology = _boss_group_topology(source_layer_slots)
            target_topology = _boss_group_topology(target_layer_slots)
        except _ClosureError as exc:
            return result(False, "BOSS_GROUP_MISMATCH", str(exc))
        if source_topology != target_topology:
            return result(
                False, "BOSS_GROUP_MISMATCH",
                f"layer {source_layer}->{target_layer}:"
                f" source {source_topology}, target {target_topology}")

        source_cap, target_cap = source_caps[index], target_caps[index]
        requirement = req_by_layer.get(source_layer)
        if requirement is None:
            return result(False, "ACTION_CLOSURE_UNAUDITED",
                          f"requirements missing source layer {source_layer}")
        source_positions = dict(source_cap.custom_positions)
        target_positions = dict(target_cap.custom_positions)
        for name in requirement.custom_positions:
            source_count = int(source_positions.get(name, 0))
            target_count = int(target_positions.get(name, 0))
            # A named movement/spawn must resolve to exactly one target.  The
            # source is checked too: ambiguous native anchors cannot prove an
            # equivalent transplant even though the native field may run.
            if source_count != 1 or target_count != 1:
                return result(
                    False, "CUSTOM_POSITION_MISSING",
                    f"layer {source_layer}->{target_layer} position {name}:"
                    f" source={source_count}, target={target_count}")

        source_funnels = dict(source_cap.funnel_groups)
        target_funnels = dict(target_cap.funnel_groups)
        for funnel in requirement.funnels:
            source_count = int(source_funnels.get(funnel.group, 0))
            target_count = int(target_funnels.get(funnel.group, 0))
            if (min(funnel.max_commands, target_count)
                    != min(funnel.max_commands, source_count)):
                return result(
                    False, "FUNNEL_ANCHOR_MISMATCH",
                    f"layer {source_layer}->{target_layer} FUNNEL_SPAWN"
                    f"{funnel.group}: max={funnel.max_commands},"
                    f" source={source_count}, target={target_count}")
    return result(True)


def _table(tables: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    value = tables.get(name)
    if value is None:
        value = tables.get(TABLE_LOGICALS[name])
    return value if isinstance(value, Mapping) else {}


def _numeric_levels(node: Any) -> tuple[int, ...]:
    if not isinstance(node, Mapping):
        return ()
    return tuple(sorted(int(key) for key in node if str(key).isdigit()))


def _first_at_or_above(levels: tuple[int, ...], enemy_level: int) -> int | None:
    return next((level for level in levels if level >= enemy_level), None)


def validate_boss_ref(ref: BossRef, enemy_level: int,
                      tables: Mapping[str, Any]) -> GateResult:
    """Validate a BossKind/code pair against that constructor's exact table.

    Kinds 14/15 use numeric constructor parameters rather than string codes and
    therefore fail closed in this first implementation.  Orochi (kind 3) has a
    verified ``getSurjectivity`` rule: select the first level >= enemy level.
    Other already-audited special tables keep the pre-existing floor rule; this
    function intentionally does not reverse them globally.

    Injected callbacks ``__level_validator__`` and ``__funnel_ok__`` are
    mandatory for kinds 0/1/8, so the builder reuses its established
    general/standard and funnel gates and returns the selected numeric tier.
    """

    try:
        level = int(enemy_level)
    except (TypeError, ValueError):
        return GateResult(False, "LEVEL", detail=f"invalid enemy level {enemy_level!r}")
    if ref.kind in (5, 14, 15) or ref.kind not in KIND_TABLES:
        return GateResult(False, "SPECIAL_TABLE_UNAUDITED",
                          detail=f"BossKind {ref.kind} is not string-code audited")
    table_name = KIND_TABLES[ref.kind]
    table = _table(tables, table_name)
    if ref.code not in table:
        return GateResult(False, "KIND_CODE_MISMATCH", source_table=table_name,
                          detail=f"BossKind {ref.kind} requires {table_name}[{ref.code}]")

    level_validator = tables.get("__level_validator__")
    funnel_ok = tables.get("__funnel_ok__")
    if ref.kind in (0, 1, 8) and not callable(level_validator):
        return GateResult(False, "LEVEL", source_table=table_name,
                          detail="missing level adapter for general/standard constructor")
    if ref.kind in (0, 1, 8) and not callable(funnel_ok):
        return GateResult(False, "FUNNEL_LEVEL", source_table=table_name,
                          detail="missing funnel adapter for general/standard constructor")
    if callable(funnel_ok) and not funnel_ok(ref.code, level):
        return GateResult(False, "FUNNEL_LEVEL", source_table=table_name)

    if ref.kind in (0, 1, 8):
        try:
            selected = level_validator(ref, level, tables)
        except Exception as exc:
            return GateResult(False, "LEVEL", source_table=table_name,
                              detail=f"level adapter failed: {exc}")
        if selected is False or selected is None:
            return GateResult(False, "LEVEL", source_table=table_name)
        if selected is True:
            return GateResult(False, "LEVEL", source_table=table_name,
                              detail="level adapter returned bool instead of selected tier")
        try:
            selected = int(selected)
        except (TypeError, ValueError):
            return GateResult(False, "LEVEL", source_table=table_name,
                              detail="level adapter returned no numeric selected tier")
        return GateResult(True, selected_level=selected, source_table=table_name)

    levels = _numeric_levels(table[ref.code])
    if not levels:
        return GateResult(True, source_table=table_name)
    if ref.kind == 3:
        selected = _first_at_or_above(levels, level)
    else:
        usable = tuple(candidate for candidate in levels if candidate <= level)
        selected = usable[-1] if usable else None
    if selected is None:
        return GateResult(False, "LEVEL", source_table=table_name,
                          detail=f"no usable tier for enemy level {level}")
    return GateResult(True, selected_level=selected, source_table=table_name)


def _canonical_value(value: Any) -> Any:
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, Mapping):
        return {_canonical_value(str(key)): _canonical_value(item)
                for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        items = [_canonical_value(item) for item in value]
        if isinstance(value, (set, frozenset)):
            items.sort(key=lambda item: json.dumps(
                item, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                allow_nan=False))
        return items
    return value


def stable_id(prefix: str, payload: Any) -> str:
    """Canonical NFC JSON + full SHA-256; never Python's process-local hash."""

    raw = json.dumps(
        _canonical_value(payload), ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    return f"{unicodedata.normalize('NFC', prefix)}_{hashlib.sha256(raw).hexdigest()}"


def _ref_payload(ref: BossRef | None) -> Any:
    return None if ref is None else {"kind": ref.kind, "code": ref.code}


def _caps_payload(cap: TerrainLayerCaps) -> dict:
    return {
        "layer": cap.layer,
        "boss_slots": cap.boss_slots,
        "boss_group_kinds": cap.boss_group_kinds,
        "funnel_groups": cap.funnel_groups,
        "custom_positions": cap.custom_positions,
        "boss_groups": cap.boss_groups,
    }


def _bundle_payload(bundle: NativeBossBundle) -> dict:
    return {
        "schema": "native-bundle-v1",
        "field": bundle.source_field,
        "zone": bundle.source_zone,
        "terrain": bundle.terrain_logical,
        "active_layers": bundle.active_layers,
        "slots": [{
            "layer": slot.layer,
            "slot": slot.slot,
            "boss_group_kind": slot.boss_group_kind,
            "single": _ref_payload(slot.single),
            "multi": _ref_payload(slot.multi),
        } for slot in bundle.slots],
        "active_zone_rows": bundle.active_zone_rows,
        "caps": [_caps_payload(cap) for cap in bundle.terrain_caps],
    }


def _dedupe_bundles(bundles: tuple[NativeBossBundle, ...] | list[NativeBossBundle]) \
        -> tuple[NativeBossBundle, ...]:
    by_id: dict[str, NativeBossBundle] = {}
    for bundle in bundles:
        bundle_id = stable_id("bundle", _bundle_payload(bundle))
        by_id.setdefault(bundle_id, bundle)
    return tuple(by_id[key] for key in sorted(by_id))


def _collapse_variant_grades(bundles: list[NativeBossBundle]) \
        -> tuple[NativeBossBundle, ...]:
    """Keep the highest official grade within one numbered field series.

    This is called only after variant grouping.  Different mechanics therefore
    never collapse together, while ``series_1/_2/_3`` aliases of the same
    variant contribute one bundle ticket.  Non-numbered fields remain distinct.
    """

    candidates: dict[tuple[str, str], list[NativeBossBundle]] = {}
    unnumbered: list[NativeBossBundle] = []
    for bundle in _dedupe_bundles(bundles):
        match = re.fullmatch(r"(.*)_(\d+)", bundle.source_field)
        if not match:
            unnumbered.append(bundle)
            continue
        shape = _bundle_payload(bundle)
        shape.pop("field", None)
        shape.pop("zone", None)
        key = (match.group(1), stable_id("grade-shape", shape))
        candidates.setdefault(key, []).append(bundle)

    kept: list[NativeBossBundle] = list(unnumbered)
    for key in sorted(candidates):
        values = candidates[key]
        suffix_contract = all(
            bundle.source_field.startswith(GRADE_SUFFIX_PREFIXES)
            for bundle in values)
        advent_evidence = (
            all(bundle.source_field.startswith("advent_") for bundle in values)
            and any(
                bundle.source_category == "advent"
                or any(alias[0] == "advent" for alias in bundle.metadata_aliases)
                for bundle in values))
        if not suffix_contract and not advent_evidence:
            # Unknown *_N names are ordinary scenes until an official schema or
            # quest-category proof says otherwise.
            kept.extend(values)
            continue

        def rank(bundle: NativeBossBundle) -> tuple[int, int, str]:
            match = re.fullmatch(r".*_(\d+)", bundle.source_field)
            suffix = int(match.group(1)) if match else 0
            if suffix_contract:
                # These schemas define suffix order; higher aliases may lack a
                # quest row, so source_level is only a tiebreaker.
                return suffix, int(bundle.source_level), bundle.source_field
            # Other advent series are proved by quest metadata; some use _1 as
            # the lv100 form, so level must win over the suffix.
            return int(bundle.source_level), suffix, bundle.source_field

        kept.append(max(values, key=rank))
    return _dedupe_bundles(kept)


def _assemble_catalog(*, eligible: list[NativeBossBundle],
                      discovered: list[NativeBossBundle],
                      rejections: list[BundleRejection],
                      scanned_fields: int = 0,
                      scanned_active_fields: int = 0,
                      scanned_single_refs: tuple[BossRef, ...] = (),
                      multi_only_codes: tuple[str, ...] = ()) -> BundleCatalog:
    def index(items: list[NativeBossBundle], *, collapse_grades: bool):
        by_variant: dict[str, list[NativeBossBundle]] = {}
        family_variants: dict[str, set[str]] = {}
        for bundle in items:
            by_variant.setdefault(bundle.variant_id, []).append(bundle)
            family_variants.setdefault(bundle.family_id, set()).add(bundle.variant_id)
        variants = {family_id: tuple(sorted(values))
                    for family_id, values in family_variants.items()}
        bundles = {variant_id: (_collapse_variant_grades(values)
                                if collapse_grades else _dedupe_bundles(values))
                   for variant_id, values in by_variant.items()}
        return tuple(sorted(variants)), variants, bundles

    family_ids, variants, bundles = index(eligible, collapse_grades=True)
    discovered_family_ids, discovered_variants, discovered_bundles = index(
        discovered, collapse_grades=False)
    family_names: dict[str, str] = {}
    variant_names: dict[str, str] = {}
    for bundle in discovered:
        family_names.setdefault(bundle.family_id, bundle.family_name)
        variant_names.setdefault(bundle.variant_id, bundle.variant_name)
    return BundleCatalog(
        family_ids=family_ids,
        variants=variants,
        bundles=bundles,
        family_names=family_names,
        variant_names=variant_names,
        rejections=tuple(rejections),
        discovered_family_ids=discovered_family_ids,
        discovered_variants=discovered_variants,
        discovered_bundles=discovered_bundles,
        scanned_fields=int(scanned_fields),
        scanned_active_fields=int(scanned_active_fields),
        eligible_source_fields=tuple(sorted({bundle.source_field for bundle in eligible})),
        scanned_single_refs=tuple(scanned_single_refs),
        multi_only_codes=tuple(multi_only_codes),
    )


def catalog_from_bundles(bundles: tuple[NativeBossBundle, ...] | list[NativeBossBundle]) \
        -> BundleCatalog:
    """Build a post-gate catalog from already eligible bundles (test/tool API)."""

    values = list(_dedupe_bundles(list(bundles)))
    return _assemble_catalog(eligible=values, discovered=values, rejections=[])


def _pick_index(rng: Any, size: int) -> int:
    if size <= 0:
        raise ValueError("cannot choose from an empty catalog level")
    index = int(rng.randrange(size))
    if not 0 <= index < size:
        raise ValueError(f"rng.randrange({size}) returned {index}")
    return index


def choose_family_variant_bundle(catalog: BundleCatalog, rng: Any,
                                 policy: Mapping[str, Any] | Callable[[str], bool] | None) \
        -> BundleSelection:
    """Choose in exactly three stages: family, then variant, then bundle."""

    families = list(catalog.family_ids)
    if callable(policy):
        families = [family_id for family_id in families if policy(family_id)]
    elif isinstance(policy, Mapping):
        allowed = policy.get("family_ids")
        if allowed is not None:
            allowed_set = set(map(str, allowed))
            families = [family_id for family_id in families if family_id in allowed_set]
        excluded = set(map(str, policy.get("exclude_family_ids", ())))
        families = [family_id for family_id in families if family_id not in excluded]
        predicate = policy.get("family_filter")
        if callable(predicate):
            families = [family_id for family_id in families if predicate(family_id)]
    families = sorted(set(families))
    family_id = families[_pick_index(rng, len(families))]

    variants = tuple(sorted(set(catalog.variants[family_id])))
    variant_id = variants[_pick_index(rng, len(variants))]
    bundles = _dedupe_bundles(list(catalog.bundles[variant_id]))
    bundle = bundles[_pick_index(rng, len(bundles))]
    return BundleSelection(family_id, variant_id, bundle)


def _identity(identity_of: Callable[[BossRef, int | None], Mapping[str, Any]] | None,
              ref: BossRef, selected_level: int | None,
              display_names: Mapping[str, str]) -> dict:
    raw = identity_of(ref, selected_level) if callable(identity_of) else {}
    raw = raw if isinstance(raw, Mapping) else {}
    named_display = raw.get("display") or display_names.get(ref.code)
    display = str(named_display or ref.code).strip()
    model = str(raw.get("model") or ref.code).strip()
    actions = raw.get("actions") or ()
    return {
        "display": unicodedata.normalize("NFC", display),
        "has_display": bool(str(named_display or "").strip()),
        "model": unicodedata.normalize("NFC", model),
        "actions": tuple(sorted({unicodedata.normalize("NFC", str(item).strip())
                                 for item in actions if str(item).strip()})),
    }


def _gate_value(value: Any, default_reason: str) -> GateResult:
    if isinstance(value, GateResult):
        return value
    if value is True:
        return GateResult(True)
    if value is False or value is None:
        return GateResult(False, default_reason)
    if isinstance(value, tuple):
        ok = bool(value[0]) if value else False
        reason = (str(value[1]) if len(value) > 1 and value[1]
                  else (None if ok else default_reason))
        detail = str(value[2]) if len(value) > 2 and value[2] else ""
        return GateResult(ok, reason, detail=detail)
    return GateResult(False, default_reason, detail=f"invalid gate result {value!r}")


def build_native_bundle_catalog(
        field_data: Mapping[str, Any], zone: Mapping[str, Any],
        terrain_loader: Callable[[str], Any], *, enemy_level: int,
        validation_tables: Mapping[str, Any],
        display_names: Mapping[str, str] | None = None,
        identity_of: Callable[[BossRef, int | None], Mapping[str, Any]] | None = None,
        hp_gate: Callable[[tuple[ActiveBossSlot, ...], int], Any] | None = None,
        bundle_hp_gate: Callable[[NativeBossBundle, int], Any] | None = None,
        reference_gate: Callable[[str, tuple[ActiveBossSlot, ...],
                                  tuple[tuple[str, int, int], ...], int], Any] | None = None,
        zako_codes: set[str] | frozenset[str] | None = None,
        official_field: Callable[[str], bool] | None = None,
        metadata_of: Callable[[str], Mapping[str, Any]] | None = None,
        portability_gate: Callable[[NativeBossBundle], RequirementResult] | None = None,
        c8016_prefixes: tuple[str, ...] = ("arch_evil",),
        ) -> BundleCatalog:
    """Scan every official field and build separate discovered/eligible indexes.

    Eligibility is decided before the selection index is grouped, so invalid
    variants never add family tickets.  Action-closure uncertainty is a
    portability verdict only: otherwise-valid native bundles stay eligible
    and are marked native-only.
    """

    names = display_names or {}
    is_official = official_field or (lambda field_id: not str(field_id).startswith("mod_rogue"))
    official_ids = tuple(sorted(str(field_id) for field_id in field_data
                                if is_official(str(field_id))))
    discovered: list[NativeBossBundle] = []
    eligible: list[NativeBossBundle] = []
    rejections: list[BundleRejection] = []
    single_refs: set[BossRef] = set()
    multi_refs: dict[str, tuple[BossRef, str, str]] = {}
    active_fields = 0

    for field_id in official_ids:
        try:
            terrain_logical, zone_id, zone_node = _field_context(field_id, field_data, zone)
            caps = load_terrain_layer_caps(field_id, field_data, zone, terrain_loader)
            slots = active_boss_slots(field_id, field_data, zone, terrain_loader)
        except TerrainGateError as exc:
            rejections.append(BundleRejection(
                field_id, None, exc.reason, exc.detail))
            continue
        except FileNotFoundError as exc:
            rejections.append(BundleRejection(
                field_id, None, "TERRAIN_PARSE", str(exc)))
            continue
        if not slots:
            continue
        active_fields += 1
        for slot in slots:
            if slot.single is not None:
                single_refs.add(slot.single)
            if slot.multi is not None:
                multi_refs.setdefault(slot.multi.code, (slot.multi, field_id, zone_id))

        actual_slots = tuple(slot for slot in slots if slot.single is not None)
        if not actual_slots:
            continue
        actual_refs = tuple(slot.single for slot in actual_slots if slot.single is not None)

        gate: GateResult | None = None
        selected: list[tuple[str, int, int]] = []
        ref_results: dict[BossRef, GateResult] = {}
        for slot, ref in zip(actual_slots, actual_refs):
            result = validate_boss_ref(ref, enemy_level, validation_tables)
            ref_results[ref] = result
            if not result.ok and gate is None:
                gate = result
            if result.ok and result.selected_level is not None:
                selected.append((slot.layer, slot.slot, int(result.selected_level)))

        all_codes = tuple(ref.code for ref in actual_refs)
        # Explicit crash/phase policy wins over incidental level failures so the
        # same data always reports the actionable primary reason.
        if any(code.startswith(c8016_prefixes) for code in all_codes):
            gate = GateResult(False, "C8016", detail="element recolor preload is unsafe")
        if gate is None and callable(reference_gate):
            reference_result = _gate_value(
                reference_gate(field_id, actual_slots, tuple(selected), enemy_level),
                "REFERENCE")
            # A successful stage is not a terminal eligibility verdict.  Keep
            # ``gate`` empty so the active-zako, special-HP and HP-proof stages
            # still run; only failures short-circuit the remaining pipeline.
            if not reference_result.ok:
                gate = reference_result
        elif gate is None and reference_gate is None:
            gate = GateResult(False, "REFERENCE",
                              detail="missing exact-slot reference gate")

        if gate is None and zako_codes is not None:
            for cap in caps:
                row = _cells(zone_node[cap.layer])
                for index in range(2, min(22, len(row)), 2):
                    code = row[index]
                    if code not in ("", "(None)") and code not in zako_codes:
                        gate = GateResult(False, "REFERENCE",
                                          detail=f"active layer {cap.layer} zako missing:{code}")
                        break
                if gate is not None:
                    break

        identities = [_identity(identity_of, ref, ref_results.get(ref, GateResult(False)).selected_level,
                                names) for ref in actual_refs]
        orochi_codes = tuple(ref.code for ref in actual_refs)
        is_orochi_parent = (len(orochi_codes) == 1
                            and orochi_codes[0] in OROCHI_PARENT_VARIANTS)
        is_orochi_ex_parent = (
            len(actual_refs) == 1
            and actual_refs[0].kind == 4
            and actual_refs[0].code == "orochi_ex"
        )
        has_special_constructor = any(
            ref.kind not in (0, 1, 8) for ref in actual_refs)
        if is_orochi_parent:
            family_name = "八岐大蛇"
            family_atoms = ({"display": family_name},)
            variant_name = OROCHI_PARENT_VARIANTS[orochi_codes[0]]
        elif is_orochi_ex_parent:
            family_name = "八岐大蛇 EX"
            family_atoms = ({"display": family_name},)
            variant_name = "official_three_phase"
        else:
            family_values = []
            for ref, info in zip(actual_refs, identities):
                family_values.append(
                    {"display": info["display"]} if info["has_display"] else
                    {"fallback": {"kind": ref.kind, "code": ref.code}})
            atom_map = {
                json.dumps(_canonical_value(atom),
                           ensure_ascii=False, sort_keys=True,
                           separators=(",", ":"), allow_nan=False):
                atom for atom in family_values
            }
            family_atoms = tuple(atom_map[key] for key in sorted(atom_map))
            family_name = " + ".join(
                atom.get("display") or atom["fallback"]["code"] for atom in family_atoms)
            variant_name = " + ".join(orochi_codes)
        family_id = stable_id("family", {"schema": "family-v1", "atoms": family_atoms})

        variant_entities = []
        identity_by_ref = {ref: info for ref, info in zip(actual_refs, identities)}
        for slot in actual_slots:
            info = identity_by_ref[slot.single]
            variant_entities.append({
                "single": _ref_payload(slot.single),
                "model": info["model"],
                "actions": info["actions"],
            })
        # A variant is the canonical multiset of mechanics/entities, not its
        # placement in one source field.  Sorting makes layer/slot swaps share
        # one ticket while preserving duplicate occurrences; placement and c22
        # remain in the bundle identity for terrain compatibility.
        variant_entities.sort(key=lambda item: json.dumps(
            _canonical_value(item), ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False))
        variant_id = stable_id("variant", {
            "schema": "variant-v1",
            "family": family_id,
            "active_single": variant_entities,
        })
        metadata = metadata_of(field_id) if callable(metadata_of) else {}
        metadata = metadata if isinstance(metadata, Mapping) else {}
        bundle = NativeBossBundle(
            family_id=family_id,
            family_name=family_name,
            variant_id=variant_id,
            variant_name=variant_name,
            source_field=field_id,
            source_zone=zone_id,
            terrain_logical=terrain_logical,
            active_layers=tuple(cap.layer for cap in caps),
            slots=slots,
            bgm=(str(metadata["bgm"]) if metadata.get("bgm") else None),
            thumbnail=str(metadata.get("thumbnail") or ""),
            source_category=str(metadata.get("category") or "official"),
            portable=False,
            native_only_reason=None,
            terrain_caps=caps,
            active_zone_rows=tuple(
                (cap.layer, tuple(_cells(zone_node[cap.layer]))) for cap in caps),
            selected_levels=tuple(selected),
            metadata_aliases=tuple(sorted({
                tuple(map(str, alias)) for alias in metadata.get("aliases", ())
                if isinstance(alias, (list, tuple)) and len(alias) == 3
            }, key=lambda alias: (alias[0] == "floor", alias))),
            source_level=(int(metadata.get("level") or 0)
                          if str(metadata.get("level") or "0").isdigit() else 0),
        )

        if gate is None and has_special_constructor:
            gate = _gate_value(
                bundle_hp_gate(bundle, enemy_level)
                if callable(bundle_hp_gate) else None,
                "SPECIAL_HP_CHANNEL_UNSUPPORTED")
        if gate is None and has_special_constructor:
            gate = GateResult(False, "SPECIAL_HP_CHANNEL_UNSUPPORTED",
                              detail="special constructor has no proved whole-bundle HP adapter")
        if gate is None:
            gate = _gate_value(
                hp_gate(actual_slots, enemy_level) if callable(hp_gate) else None,
                "HP_UNVERIFIED")
        if gate.ok:
            if callable(portability_gate):
                try:
                    requirement_result = portability_gate(bundle)
                except Exception as exc:
                    requirement_result = RequirementResult(
                        False, reason="ACTION_CLOSURE_UNAUDITED", detail=str(exc))
                if (isinstance(requirement_result, RequirementResult)
                        and requirement_result.ok
                        and requirement_result.requirements is not None):
                    self_check = terrain_compatibility(
                        bundle, bundle, requirement_result.requirements)
                    if self_check.ok:
                        bundle = replace(
                            bundle, portable=True, native_only_reason=None,
                            terrain_requirements=requirement_result.requirements)
                    else:
                        bundle = replace(
                            bundle, portable=False,
                            native_only_reason=(self_check.reason
                                                or "ACTION_CLOSURE_UNAUDITED"),
                            terrain_requirements=None)
                else:
                    reason = (requirement_result.reason
                              if isinstance(requirement_result, RequirementResult)
                              else "ACTION_CLOSURE_UNAUDITED")
                    bundle = replace(
                        bundle, portable=False,
                        native_only_reason=reason or "ACTION_CLOSURE_UNAUDITED",
                        terrain_requirements=None)
            else:
                bundle = replace(
                    bundle, portable=False,
                    native_only_reason="ACTION_CLOSURE_UNAUDITED",
                    terrain_requirements=None)
            eligible.append(bundle)
        discovered.append(bundle)
        if not gate.ok:
            rejections.append(BundleRejection(
                field_id, zone_id, gate.reason or "HP_UNVERIFIED", gate.detail,
                actual_refs, family_id, variant_id))

    single_codes = {ref.code for ref in single_refs}
    multi_only = tuple(sorted(code for code in multi_refs if code not in single_codes))
    for code in sorted(set(multi_only) & set(MULTI_ONLY_REGRESSION)):
        ref, field_id, zone_id = multi_refs[code]
        rejections.append(BundleRejection(
            field_id, zone_id, "NO_SINGLE_FIELD",
            "code appears only in active multi-side slots", (ref,)))

    return _assemble_catalog(
        eligible=eligible,
        discovered=discovered,
        rejections=rejections,
        scanned_fields=len(official_ids),
        scanned_active_fields=active_fields,
        scanned_single_refs=tuple(sorted(single_refs, key=lambda ref: (ref.kind, ref.code))),
        multi_only_codes=multi_only,
    )


def audit_bundle_coverage(catalog: BundleCatalog) -> dict:
    """Return a deterministic JSON-serializable post-gate coverage report."""

    eligible_bundles = [bundle for values in catalog.bundles.values() for bundle in values]
    eligible_codes = sorted({slot.single.code for bundle in eligible_bundles
                             for slot in bundle.slots if slot.single is not None})
    discovered_bundles = [bundle for values in catalog.discovered_bundles.values()
                          for bundle in values]
    discovered_codes = sorted({slot.single.code for bundle in discovered_bundles
                               for slot in bundle.slots if slot.single is not None})
    reasons: Counter[str] = Counter(rejection.reason for rejection in catalog.rejections)
    rejected_fields = {rejection.source_field for rejection in catalog.rejections}
    rejected_families = {rejection.family_id for rejection in catalog.rejections
                         if rejection.family_id is not None}
    rejected_variants = {rejection.variant_id for rejection in catalog.rejections
                         if rejection.variant_id is not None}
    rejected_bundles = {
        (rejection.source_field, rejection.source_zone,
         rejection.family_id, rejection.variant_id)
        for rejection in catalog.rejections
        if rejection.family_id is not None and rejection.variant_id is not None
    }
    rejected_codes = {ref.code for rejection in catalog.rejections
                      for ref in rejection.boss_refs}
    examples: dict[str, list[str]] = {}
    for rejection in catalog.rejections:
        values = examples.setdefault(rejection.reason, [])
        for ref in rejection.boss_refs:
            if ref.code not in values and len(values) < 5:
                values.append(ref.code)
        if not rejection.boss_refs and rejection.source_field not in values and len(values) < 5:
            values.append(rejection.source_field)
    native_only: Counter[str] = Counter(
        bundle.native_only_reason for bundle in eligible_bundles
        if not bundle.portable and bundle.native_only_reason)
    family_status_counts: Counter[str] = Counter()
    blocked_families: dict[str, dict] = {}
    reasons_by_family: dict[str, set[str]] = {}
    for rejection in catalog.rejections:
        if rejection.family_id is not None:
            reasons_by_family.setdefault(rejection.family_id, set()).add(rejection.reason)
    for family_id in catalog.discovered_family_ids:
        discovered_set = set(catalog.discovered_variants.get(family_id, ()))
        eligible_set = set(catalog.variants.get(family_id, ()))
        if discovered_set and discovered_set <= eligible_set:
            status = "complete"
        elif eligible_set:
            status = "partial"
        else:
            status = "rejected"
        family_status_counts[status] += 1
        if status != "complete":
            blocked_families[family_id] = {
                "name": catalog.family_names.get(family_id, family_id),
                "status": status,
                "discovered_variants": len(discovered_set),
                "eligible_variants": len(eligible_set),
                "reasons": sorted(reasons_by_family.get(family_id, ())),
            }
    return {
        "scanned": {
            "fields": catalog.scanned_fields,
            "active_boss_fields": catalog.scanned_active_fields,
            "single_refs": len(catalog.scanned_single_refs),
            "single_codes": len({ref.code for ref in catalog.scanned_single_refs}),
        },
        "discovered": {
            "families": len(catalog.discovered_family_ids),
            "variants": len(catalog.discovered_bundles),
            "bundles": len(discovered_bundles),
            "codes": len(discovered_codes),
        },
        "eligible": {
            "fields": len(catalog.eligible_source_fields),
            "families": len(catalog.family_ids),
            "variants": len(catalog.bundles),
            "bundles": len(eligible_bundles),
            "codes": len(eligible_codes),
        },
        "family_coverage": {
            "complete": family_status_counts["complete"],
            "partial": family_status_counts["partial"],
            "rejected": family_status_counts["rejected"],
            "blocked": {key: blocked_families[key]
                        for key in sorted(blocked_families)},
        },
        "rejected": {
            "entries": len(catalog.rejections),
            "fields": len(rejected_fields),
            "families": len(rejected_families),
            "variants": len(rejected_variants),
            "bundles": len(rejected_bundles),
            "codes": len(rejected_codes),
            "by_reason": dict(sorted(reasons.items())),
            "examples": {key: values for key, values in sorted(examples.items())},
        },
        "native_only": dict(sorted(native_only.items())),
        "multi_only_codes": list(catalog.multi_only_codes),
        "theoretical_pre_gate": {
            "families": 114,
            "complete_families": 60,
            "label": "pre-gate ceiling only; not eligible coverage",
        },
    }
