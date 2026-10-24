#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pure compilers for the ticket, shop, and drop package additions."""

from __future__ import annotations

import hashlib
import io
import json
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from PIL import Image, UnidentifiedImageError

import wf_abyss_gacha_package_contract as contract
import wf_abyss_gacha_drop_source as drop_source
import wf_abyss_ticket_compile as tickets
import wf_abyss_ticket_drop as ticket_drop
import wf_assets
import wf_character_pack as character_pack
import wf_dsl
import wf_mod_tool as core
import wf_rogue_shop as shop


@dataclass(frozen=True)
class ComponentResult:
    roots: Mapping[str, Mapping[str, bytes]]
    table_claims: tuple[Mapping[str, Any], ...]
    input_sha256: Mapping[str, str]
    report: Mapping[str, Any]


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-JSON constant {value}")


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _strict_json(raw: bytes, label: str) -> object:
    if not isinstance(raw, bytes):
        raise TypeError(f"{label} must be bytes")
    try:
        return json.loads(
            raw.decode("utf-8"),
            parse_constant=_reject_constant,
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"{label} is not strict JSON: {exc}") from exc


def _json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("compiled component is not strict JSON") from exc


def _canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("component value is not strict JSON") from exc


def _flat_table(raw: bytes, logical: str) -> dict[str, str]:
    try:
        keys, rows = core._strict_orderedmap_rows(  # type: ignore[attr-defined]
            raw, label=logical, compressed_rows=True
        )
        return {
            key: row.decode("utf-8")
            for key, row in zip(keys, rows)
        }
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError(f"invalid flat orderedmap {logical}: {exc}") from exc


def _flat_bytes(table: Mapping[str, object], logical: str) -> bytes:
    keys = list(table)
    rows: list[bytes] = []
    for key in keys:
        value = table[key]
        if isinstance(value, str):
            rows.append(value.encode("utf-8"))
        elif isinstance(value, bytes):
            rows.append(value)
        else:
            raise TypeError(f"{logical}[{key!r}] must be str/bytes")
    return core.build_orderedmap(core.OrderedMap(
        logical, keys, rows, Path(f"<compiled:{logical}>")
    ))


def _claim_for(logical: str) -> Mapping[str, Any]:
    matches = [
        claim for claim in contract.expected_new_claims()
        if claim["logical_path"] == logical
    ]
    if len(matches) != 1:
        raise RuntimeError(f"package contract claim is not unique: {logical}")
    return matches[0]


def _inspect(raw: bytes, claim: Mapping[str, Any]) -> character_pack.TableImage:
    parsed = character_pack.TableClaim(
        root=claim["root"],
        logical_path=claim["logical_path"],
        codec_id=claim["codec_id"],
        outer_keys=tuple(claim["outer_keys"]),
    )
    if parsed.codec_id == "json_object":
        value = _strict_json(raw, parsed.logical_path)
        if not isinstance(value, dict):
            raise TypeError(f"{parsed.logical_path} must be a JSON object")
        return character_pack.TableImage(tuple(
            (key, _canonical_json_bytes(item)) for key, item in value.items()
        ))
    codec = character_pack.DEFAULT_CODECS[parsed.codec_id]
    return codec.inspect(raw, parsed, ())


def _unchanged_rows(
    before: character_pack.TableImage,
    after: character_pack.TableImage,
    owned: Sequence[str],
    label: str,
) -> None:
    owned_set = set(owned)
    before_rows = {key: row for key, row in before.outer_rows if key not in owned_set}
    after_rows = {key: row for key, row in after.outer_rows if key not in owned_set}
    if before_rows != after_rows:
        raise ValueError(f"{label} changed an unclaimed row")
    if before.semantic_values != after.semantic_values:
        raise ValueError(f"{label} changed an unclaimed semantic sibling")


def _empty_roots() -> dict[str, dict[str, bytes]]:
    return {root: {} for root in contract.ROOT_NAMES}


def _decode_item_sheet(raw: bytes, label: str) -> Image.Image:
    try:
        decoded = wf_assets.png_decode(raw)
        with Image.open(io.BytesIO(decoded)) as image:
            image.load()
            return image.convert("RGBA")
    except (TypeError, ValueError, OSError, UnidentifiedImageError) as exc:
        raise ValueError(f"{label} is not a storage-ready item sheet") from exc


def _decode_item_atlas(raw: bytes, label: str) -> list[dict[str, object]]:
    try:
        tree = wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]
    except (TypeError, ValueError, zlib.error, EOFError) as exc:
        raise ValueError(f"{label} is not a raw-deflate AMF3 item atlas") from exc
    if not isinstance(tree, list) or not all(isinstance(item, dict) for item in tree):
        raise ValueError(f"{label} item atlas root must be an object array")
    return tree


def _shared_asset_evidence(
    sheet_before_raw: bytes,
    atlas_before_raw: bytes,
    sheet_after_raw: bytes,
    atlas_after_raw: bytes,
) -> tuple[dict[str, dict[str, object]], dict[str, object]]:
    sheet_before = _decode_item_sheet(sheet_before_raw, "before")
    sheet_after = _decode_item_sheet(sheet_after_raw, "after")
    expected_dimensions = (sheet_before.width, sheet_before.height + 22)
    if sheet_after.size != expected_dimensions:
        raise ValueError("shared item sheet did not append exactly one 22px row")
    prefix = sheet_after.crop((0, 0, sheet_before.width, sheet_before.height))
    before_pixels_sha = _sha(sheet_before.tobytes())
    after_prefix_sha = _sha(prefix.tobytes())
    if before_pixels_sha != after_prefix_sha:
        raise ValueError("shared item sheet changed existing prefix pixels")

    atlas_before = _decode_item_atlas(atlas_before_raw, "before")
    atlas_after = _decode_item_atlas(atlas_after_raw, "after")
    if (
        len(atlas_after) != len(atlas_before) + len(tickets.TICKETS)
        or atlas_after[:len(atlas_before)] != atlas_before
        or [entry.get("n") for entry in atlas_after[len(atlas_before):]]
        != [spec.icon_name for spec in tickets.TICKETS]
    ):
        raise ValueError("shared item atlas changed existing prefix entries")
    before_entries_sha = _sha(_canonical_json_bytes(atlas_before))
    after_prefix_entries_sha = _sha(
        _canonical_json_bytes(atlas_after[:len(atlas_before)])
    )
    if before_entries_sha != after_prefix_entries_sha:
        raise ValueError("shared item atlas prefix hash drifted")

    replacements = {
        tickets.ITEM_SHEET_LOGICAL: {
            "before_sha256": _sha(sheet_before_raw),
            "before_size": len(sheet_before_raw),
        },
        tickets.ITEM_ATLAS_LOGICAL: {
            "before_sha256": _sha(atlas_before_raw),
            "before_size": len(atlas_before_raw),
        },
    }
    preservation = {
        "sheet_prefix": {
            "before_dimensions": list(sheet_before.size),
            "after_dimensions": list(sheet_after.size),
            "before_rgba_sha256": before_pixels_sha,
            "after_prefix_rgba_sha256": after_prefix_sha,
        },
        "atlas_prefix": {
            "before_entry_count": len(atlas_before),
            "after_entry_count": len(atlas_after),
            "before_entries_sha256": before_entries_sha,
            "after_prefix_entries_sha256": after_prefix_entries_sha,
        },
    }
    return replacements, preservation


def compile_ticket_component(
    *,
    item_raw: bytes,
    ticket_type_raw: bytes,
    item_ids_raw: bytes,
    sheet_raw: bytes,
    atlas_raw: bytes,
) -> ComponentResult:
    """Compile two ticket items plus their server mirror and shared icon atlas."""

    item_claim = _claim_for(tickets.ITEM_T)
    item_ids_claim = _claim_for(contract.ITEM_IDS_LOGICAL)
    owned = tuple(item_claim["outer_keys"])
    item_before_image = _inspect(item_raw, item_claim)
    if any(key in dict(item_before_image.outer_rows) for key in owned):
        raise ValueError("ticket item IDs already occupy the clean source")
    item_before = _flat_table(item_raw, tickets.ITEM_T)
    ticket_types = _flat_table(ticket_type_raw, tickets.GACHA_TICKET_TYPE_T)
    tickets.validate_ticket_type_table(ticket_types)
    item_after = tickets.build_item_table(item_before)
    item_payload = _flat_bytes(item_after, tickets.ITEM_T)
    item_after_image = _inspect(item_payload, item_claim)
    _unchanged_rows(item_before_image, item_after_image, owned, tickets.ITEM_T)
    if set(dict(item_after_image.outer_rows)) - set(dict(item_before_image.outer_rows)) != set(owned):
        raise ValueError("ticket item compiler did not add exactly the owned IDs")

    item_ids_before_image = _inspect(item_ids_raw, item_ids_claim)
    item_ids_before = _strict_json(item_ids_raw, contract.ITEM_IDS_LOGICAL)
    if not isinstance(item_ids_before, list):
        raise TypeError("item_ids.json must be an array")
    if any(key in dict(item_ids_before_image.outer_rows) for key in owned):
        raise ValueError("ticket IDs already occupy the clean item_ids source")
    item_ids_payload = _json_bytes(tickets.build_item_ids(item_ids_before))
    item_ids_after_image = _inspect(item_ids_payload, item_ids_claim)
    _unchanged_rows(
        item_ids_before_image, item_ids_after_image, owned, contract.ITEM_IDS_LOGICAL
    )

    assets = tickets.compile_locked_item_assets(sheet_raw, atlas_raw)
    replacements, preservation = _shared_asset_evidence(
        sheet_raw,
        atlas_raw,
        assets.sheet_payload,
        assets.atlas_payload,
    )
    roots = _empty_roots()
    roots["common"].update({
        tickets.ITEM_T: item_payload,
        tickets.ITEM_SHEET_LOGICAL: assets.sheet_payload,
        tickets.ITEM_ATLAS_LOGICAL: assets.atlas_payload,
    })
    roots["server"][contract.ITEM_IDS_LOGICAL] = item_ids_payload
    claims = (item_claim, item_ids_claim)
    inputs = {
        tickets.ITEM_T: _sha(item_raw),
        tickets.GACHA_TICKET_TYPE_T: _sha(ticket_type_raw),
        contract.ITEM_IDS_LOGICAL: _sha(item_ids_raw),
        tickets.ITEM_SHEET_LOGICAL: _sha(sheet_raw),
        tickets.ITEM_ATLAS_LOGICAL: _sha(atlas_raw),
    }
    return ComponentResult(roots, claims, inputs, {
        "payload_count": 4,
        "table_claim_count": 2,
        "ticket_contract_closed": True,
        "validation_only_sha256": {
            tickets.GACHA_TICKET_TYPE_T: _sha(ticket_type_raw),
        },
        "art_source_sha256": dict(assets.source_sha256),
        "shared_asset_replacements": replacements,
        "shared_asset_preservation": preservation,
        "writes_live": False,
    })


def compile_shop_component(
    *, client_raw: bytes, server_shop_raw: bytes, id_map_raw: bytes
) -> ComponentResult:
    """Compile only the two ticket products into three existing shop mirrors."""

    client_claim = _claim_for(shop.SHOP_T)
    server_claim = _claim_for(shop.SHOP_JSON)
    map_claim = _claim_for(shop.SHOP_ID_MAP_JSON)
    owned = tuple(client_claim["outer_keys"])
    before_images = (
        _inspect(client_raw, client_claim),
        _inspect(server_shop_raw, server_claim),
        _inspect(id_map_raw, map_claim),
    )
    if any(set(owned) & set(dict(image.outer_rows)) for image in before_images):
        raise ValueError("ticket shop IDs already occupy a clean source mirror")

    client_before = _flat_table(client_raw, shop.SHOP_T)
    server_before = _strict_json(server_shop_raw, shop.SHOP_JSON)
    map_before = _strict_json(id_map_raw, shop.SHOP_ID_MAP_JSON)
    if not isinstance(server_before, dict) or not isinstance(map_before, dict):
        raise TypeError("server shop mirrors must be JSON objects")
    client_after = shop.build_client_shop(client_before, shop.WEAPONS)
    server_after, map_after = shop.build_server_shop(
        server_before, map_before, shop.WEAPONS
    )
    problems = shop.validate_shop(client_after, server_after, map_after)
    if problems:
        raise ValueError("shop contract failed: " + "; ".join(problems))

    payloads = (
        _flat_bytes(client_after, shop.SHOP_T),
        _json_bytes(server_after),
        _json_bytes(map_after),
    )
    claims = (client_claim, server_claim, map_claim)
    after_images = tuple(_inspect(raw, claim) for raw, claim in zip(payloads, claims))
    for before, after, logical in zip(
        before_images, after_images,
        (shop.SHOP_T, shop.SHOP_JSON, shop.SHOP_ID_MAP_JSON),
    ):
        _unchanged_rows(before, after, owned, logical)
        added = set(dict(after.outer_rows)) - set(dict(before.outer_rows))
        if added != set(owned):
            raise ValueError(f"{logical} did not add exactly the ticket products")

    roots = _empty_roots()
    roots["common"][shop.SHOP_T] = payloads[0]
    roots["server"].update({
        shop.SHOP_JSON: payloads[1],
        shop.SHOP_ID_MAP_JSON: payloads[2],
    })
    inputs = {
        shop.SHOP_T: _sha(client_raw),
        shop.SHOP_JSON: _sha(server_shop_raw),
        shop.SHOP_ID_MAP_JSON: _sha(id_map_raw),
    }
    return ComponentResult(roots, claims, inputs, {
        "payload_count": 3,
        "table_claim_count": 3,
        "shop_contract_closed": True,
        "writes_live": False,
    })


def compile_drop_component(
    *, rogue_event_raw: bytes, rush_event_quest_raw: bytes
) -> ComponentResult:
    """Replace the locked final-normal reward; quests remain validation-only."""

    claim = _claim_for(contract.ROGUE_EVENT_LOGICAL)
    owned = tuple(claim["outer_keys"])
    before_image = _inspect(rogue_event_raw, claim)
    rogue_before = _strict_json(rogue_event_raw, contract.ROGUE_EVENT_LOGICAL)
    quests = _strict_json(rush_event_quest_raw, "rush_event_quest.json")
    if not isinstance(rogue_before, dict) or not isinstance(quests, dict):
        raise TypeError("rogue_event and rush_event_quest must be JSON objects")
    rogue_after = ticket_drop.build_final_ticket_drop(rogue_before, quests)
    ticket_drop.validate_final_ticket_drop(rogue_after, quests)
    payload = _json_bytes(rogue_after)
    client_payload = drop_source.build_drop_source(rogue_after)
    drop_source.validate_drop_mirror(client_payload, rogue_after)
    after_image = _inspect(payload, claim)
    _unchanged_rows(before_image, after_image, owned, contract.ROGUE_EVENT_LOGICAL)
    if set(dict(after_image.outer_rows)) != set(dict(before_image.outer_rows)):
        raise ValueError("drop compiler changed the event ID set")

    roots = _empty_roots()
    roots["common"][drop_source.LOGICAL_PATH] = client_payload
    roots["server"][contract.ROGUE_EVENT_LOGICAL] = payload
    inputs = {
        contract.ROGUE_EVENT_LOGICAL: _sha(rogue_event_raw),
        "rush_event_quest.json": _sha(rush_event_quest_raw),
    }
    client_claim = _claim_for(drop_source.LOGICAL_PATH)
    _inspect(client_payload, client_claim)
    return ComponentResult(roots, (client_claim, claim), inputs, {
        "payload_count": 2,
        "table_claim_count": 2,
        "drop_contract_closed": True,
        "client_server_drop_mirror_exact": True,
        "validation_only_sha256": {
            "rush_event_quest.json": _sha(rush_event_quest_raw),
        },
        "writes_live": False,
    })


__all__ = [
    "ComponentResult", "compile_ticket_component", "compile_shop_component",
    "compile_drop_component",
]
