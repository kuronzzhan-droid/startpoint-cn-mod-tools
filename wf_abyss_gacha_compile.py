#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pure compiler for the abyss limited ticket-only gacha.

All inputs are explicit isolated shadows.  The compiler returns candidate
payload bytes and exact table claims; it never resolves or writes a store,
server, package workspace, CDN, process, mail box, or device.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Collection, Mapping
from pathlib import Path, PureWindowsPath

import wf_abyss_gacha_contract as contract
import wf_abyss_gacha_pool as pool_contract
import wf_mod_tool as core
from wf_character_pack import logical_path_problem, windows_logical_path_key


COMMON_SOURCE_PATHS = (
    contract.CHARACTER_MASTER_LOGICAL,
    contract.GACHA_MASTER_LOGICAL,
    contract.FEATURE_LOGICAL,
    contract.RICH_TEXT_MASTER_LOGICAL,
)
SERVER_SOURCE_PATHS = (
    "character.json",
    *contract.SERVER_OUTPUT_PATHS,
)


def _strict_json_object(raw: bytes, label: str) -> dict:
    if not isinstance(raw, bytes):
        raise TypeError(f"server source must be bytes: {label}")

    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise ValueError(f"duplicate JSON key in {label}: {key}")
            result[key] = value
        return result

    def reject_constant(token):
        raise ValueError(f"non-finite JSON constant in {label}: {token}")

    try:
        value = json.loads(
            raw.decode("utf-8"), object_pairs_hook=pairs,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"invalid UTF-8 JSON in {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"server JSON root must be an object: {label}")
    return value


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, allow_nan=False, separators=(",", ":")
    ).encode("utf-8")


def _decode_flat(raw: bytes, logical: str) -> dict[str, bytes]:
    keys, rows = core._strict_orderedmap_rows(  # type: ignore[attr-defined]
        raw, label=logical, compressed_rows=True
    )
    return dict(zip(keys, rows))


def _decode_raw(raw: bytes, logical: str) -> dict[str, bytes]:
    keys, rows = core._strict_orderedmap_rows(  # type: ignore[attr-defined]
        raw, label=logical, compressed_rows=False
    )
    return dict(zip(keys, rows))


def _decode_inner(raw: bytes, label: str) -> dict[str, bytes]:
    keys, rows = core._strict_orderedmap_rows(  # type: ignore[attr-defined]
        raw, label=label, compressed_rows=True
    )
    return dict(zip(keys, rows))


def _build_flat(logical: str, rows: Mapping[str, bytes]) -> bytes:
    return core.build_orderedmap(core.OrderedMap(
        logical, list(rows), list(rows.values()), Path("<memory>")
    ))


def _build_raw(logical: str, rows: Mapping[str, bytes]) -> bytes:
    return core.build_orderedmap_raw_rows(core.OrderedMap(
        logical, list(rows), list(rows.values()), Path("<memory>")
    ))


def _build_inner(rows: Mapping[str, str]) -> bytes:
    return core.build_orderedmap(core.OrderedMap(
        "<inner>", list(rows), [value.encode("utf-8") for value in rows.values()],
        Path("<memory>"),
    ))


def _add_flat(raw: bytes, logical: str, key: str, row: str) -> bytes:
    rows = _decode_flat(raw, logical)
    if key in rows:
        raise ValueError(f"target key collision in {logical}: {key}")
    rows[key] = row.encode("utf-8")
    return _build_flat(logical, rows)


def _add_raw(raw: bytes, logical: str, key: str, row: bytes) -> bytes:
    rows = _decode_raw(raw, logical)
    if key in rows:
        raise ValueError(f"target key collision in {logical}: {key}")
    rows[key] = row
    return _build_raw(logical, rows)


def _new_nested(logical: str, outer_key: str, rows: Mapping[str, str]) -> bytes:
    return _build_raw(logical, {outer_key: _build_inner(rows)})


def _require_exact_sources(
    sources: Mapping[str, bytes], expected: Collection[str], label: str
) -> None:
    if not isinstance(sources, Mapping) or set(sources) != set(expected):
        actual = set(sources) if isinstance(sources, Mapping) else set()
        raise ValueError(
            f"{label} sources must match exact paths; "
            f"missing={sorted(set(expected) - actual)}, "
            f"extra={sorted(actual - set(expected))}"
        )
    for logical, raw in sources.items():
        if not isinstance(raw, bytes):
            raise TypeError(f"{label} source must be bytes: {logical}")


def _existing_common_path_keys(paths: Collection[str]) -> set[PureWindowsPath]:
    if isinstance(paths, (str, bytes)) or not isinstance(paths, Collection):
        raise TypeError("existing_common_paths must be a collection of logical paths")
    result = set()
    for index, logical in enumerate(paths):
        if not isinstance(logical, str) or not logical:
            raise TypeError(
                f"existing_common_paths[{index}] logical path must be a non-empty string"
            )
        problem = logical_path_problem(logical)
        if problem:
            raise ValueError(
                f"existing_common_paths[{index}] logical path {logical!r}: {problem}"
            )
        result.add(windows_logical_path_key(logical))
    return result


def _one_csv(raw: bytes, label: str, width: int | None = None) -> list[str]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{label} is not UTF-8") from exc
    rows = core.read_csv_lines(text)
    if len(rows) != 1 or (width is not None and len(rows[0]) != width):
        suffix = f" {width}-column" if width is not None else " one-row"
        raise ValueError(f"{label} must be a{suffix} CSV")
    return rows[0]


def _validate_official_57(common: Mapping[str, bytes], server: Mapping[str, bytes]) -> None:
    master = _decode_flat(
        common[contract.GACHA_MASTER_LOGICAL], contract.GACHA_MASTER_LOGICAL
    )
    try:
        row = _one_csv(master["57"], "official gacha 57", 47)
    except KeyError as exc:
        raise ValueError("official gacha 57 drift: client row is missing") from exc
    if row != list(contract.OFFICIAL_57_CLIENT_ROW):
        raise ValueError("official gacha 57 drift: ticket-only template fields changed")

    cdn = _strict_json_object(server["cdndata/gacha.json"], "cdndata/gacha.json")
    if cdn.get("57") != [row]:
        raise ValueError("official gacha 57 drift: client/server master mirrors differ")
    runtime = _strict_json_object(server["gacha.json"], "gacha.json").get("57")
    runtime_nonpool = (
        {key: value for key, value in runtime.items() if key != "pool"}
        if isinstance(runtime, dict) else None
    )
    if runtime_nonpool != contract.OFFICIAL_57_RUNTIME_NONPOOL:
        raise ValueError("official gacha 57 drift: runtime ticket contract changed")

    feature = _decode_raw(common[contract.FEATURE_LOGICAL], contract.FEATURE_LOGICAL)
    try:
        client_cells = _one_csv(
            _decode_inner(feature["57"], "official feature 57")["1"],
            "official feature 57/1", 9,
        )
    except KeyError as exc:
        raise ValueError("official gacha 57 drift: feature row is missing") from exc
    server_feature = _strict_json_object(
        server["cdndata/gacha_feature_content.json"],
        "cdndata/gacha_feature_content.json",
    )
    expected_client = [
        "1", "dynamic/gacha_banner/fukubukuro_gacha_ny2021", "",
        "", "", "", "(None)", "", "",
    ]
    expected_server = list(expected_client)
    # The current server cdndata carries a generic cells[2] fallback injected
    # by its historical feature-content repair.  A kind-1 row only consumes
    # cells[1] on the client, so this is a locked source-baseline exception,
    # not a rule used for the new pool.
    expected_server[2] = "gacha/feature_movie/release_gacha/top/feature"
    if client_cells != expected_client or server_feature.get("57") != {
        "1": [expected_server]
    }:
        raise ValueError("official gacha 57 drift: feature baseline changed")


def _validate_character_closure(
    common: Mapping[str, bytes],
    server: Mapping[str, bytes],
    runtime_pool: Mapping[str, list[dict[str, object]]],
) -> None:
    client = _decode_flat(
        common[contract.CHARACTER_MASTER_LOGICAL], contract.CHARACTER_MASTER_LOGICAL
    )
    missing = [str(value) for value in contract.CHARACTER_IDS if str(value) not in client]
    wrong_client = []
    for character_id in contract.CHARACTER_IDS:
        key = str(character_id)
        if key in client:
            row = _one_csv(client[key], f"client character {key}")
            if len(row) < 18 or row[2] != "5" or row[17] != key:
                wrong_client.append(key)
    if missing or wrong_client:
        raise ValueError(
            f"client character closure failed: missing={missing}, not_five_star={wrong_client}"
        )

    characters = _strict_json_object(server["character.json"], "character.json")
    missing_server = [
        str(value) for value in contract.CHARACTER_IDS if str(value) not in characters
    ]
    wrong_server = [
        str(value) for value in contract.CHARACTER_IDS
        if isinstance(characters.get(str(value)), dict)
        and characters[str(value)].get("rarity") != 5
    ]
    invalid_server = [
        str(value) for value in contract.CHARACTER_IDS
        if str(value) in characters and not isinstance(characters[str(value)], dict)
    ]
    if missing_server or wrong_server or invalid_server:
        raise ValueError(
            "server five-star closure failed: "
            f"missing={missing_server}, wrong={wrong_server + invalid_server}"
        )

    expected_ranks = {
        str(entry["id"]): int(entry["rank"])
        for entries in runtime_pool.values()
        for entry in entries
    }
    pool_client_problems = []
    pool_server_problems = []
    for key, rank in expected_ranks.items():
        raw = client.get(key)
        if raw is None:
            pool_client_problems.append(f"{key}:missing")
        else:
            row = _one_csv(raw, f"client gacha pool character {key}")
            if len(row) < 18 or row[2] != str(rank) or row[17] != key:
                pool_client_problems.append(f"{key}:rank-or-identity")
        value = characters.get(key)
        if not isinstance(value, dict):
            pool_server_problems.append(f"{key}:missing-or-invalid")
        elif value.get("rarity") != rank:
            pool_server_problems.append(f"{key}:rank")
    if pool_client_problems or pool_server_problems:
        raise ValueError(
            "gacha pool character closure failed: "
            f"client={pool_client_problems}, server={pool_server_problems}"
        )


def _find_character_pool_leaks(gachas: Mapping[str, object]) -> list[tuple[int, str]]:
    targets = set(contract.CHARACTER_IDS)
    leaks: list[tuple[int, str]] = []
    for gacha_id, value in gachas.items():
        if not isinstance(value, dict):
            continue
        pools = value.get("pool")
        if not isinstance(pools, dict):
            continue
        for entries in pools.values():
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if isinstance(entry, dict) and entry.get("id") in targets:
                    leaks.append((entry["id"], gacha_id))
    return leaks


def _claims() -> list[dict[str, object]]:
    common = (
        (contract.GACHA_MASTER_LOGICAL, "flat", contract.GACHA_KEY),
        (contract.FEATURE_LOGICAL, "raw_outer", contract.GACHA_KEY),
        (contract.RARITY_ODDS_LOGICAL, "raw_outer", contract.RARITY_ODDS_ID),
        (contract.CHARACTER_3_ODDS_LOGICAL, "raw_outer", contract.CHARACTER_3_ODDS_ID),
        (contract.CHARACTER_4_ODDS_LOGICAL, "raw_outer", contract.CHARACTER_4_ODDS_ID),
        (contract.CHARACTER_5_ODDS_LOGICAL, "raw_outer", contract.CHARACTER_5_ODDS_ID),
        (contract.RICH_TEXT_MASTER_LOGICAL, "flat", contract.RICH_TEXT_ID),
    )
    claims = [
        {
            "root": "common", "logical_path": logical, "codec_id": codec,
            "outer_keys": [key], "inner_keys": [], "semantic_claims": [],
        }
        for logical, codec, key in common
    ]
    claims.extend({
        "root": "server", "logical_path": logical, "codec_id": "json_object",
        "outer_keys": [contract.GACHA_KEY], "inner_keys": [], "semantic_claims": [],
    } for logical in contract.SERVER_OUTPUT_PATHS)
    return claims


def compile_abyss_limited_gacha(
    common_sources: Mapping[str, bytes],
    server_sources: Mapping[str, bytes],
    *,
    existing_common_paths: Collection[str],
) -> dict:
    """Compile eleven isolated payloads and ten key-level ownership claims."""
    _require_exact_sources(common_sources, COMMON_SOURCE_PATHS, "common")
    _require_exact_sources(server_sources, SERVER_SOURCE_PATHS, "server")
    occupied = _existing_common_path_keys(existing_common_paths)
    collisions = sorted(
        logical for logical in contract.NEW_COMMON_PATHS
        if windows_logical_path_key(logical) in occupied
    )
    if collisions:
        raise ValueError(f"new common logical path collision: {collisions}")
    _validate_official_57(common_sources, server_sources)

    server_decoded = {
        path: _strict_json_object(server_sources[path], path)
        for path in SERVER_SOURCE_PATHS
    }
    runtime_pool = contract.build_runtime_pool(
        server_decoded["gacha.json"].get(contract.STANDARD_POOL_DONOR_ID)
    )
    _validate_character_closure(common_sources, server_sources, runtime_pool)
    for path in contract.SERVER_OUTPUT_PATHS:
        if contract.GACHA_KEY in server_decoded[path]:
            raise ValueError(f"target key collision in {path}: {contract.GACHA_KEY}")
    leaks = _find_character_pool_leaks(server_decoded["gacha.json"])
    if leaks:
        character_id, gacha_id = leaks[0]
        raise ValueError(f"character {character_id} already appears in gacha {gacha_id}")

    master_row = contract.build_gacha_master_row()
    feature_cells = contract.build_feature_cells()
    if len(master_row) != 47 or len(feature_cells) != 9:
        raise AssertionError("abyss gacha contract row width drift")
    files = {
        contract.GACHA_MASTER_LOGICAL: _add_flat(
            common_sources[contract.GACHA_MASTER_LOGICAL],
            contract.GACHA_MASTER_LOGICAL, contract.GACHA_KEY,
            core.write_csv_lines([master_row]),
        ),
        contract.FEATURE_LOGICAL: _add_raw(
            common_sources[contract.FEATURE_LOGICAL], contract.FEATURE_LOGICAL,
            contract.GACHA_KEY,
            _build_inner({"1": core.write_csv_lines([feature_cells])}),
        ),
        contract.RARITY_ODDS_LOGICAL: _new_nested(
            contract.RARITY_ODDS_LOGICAL, contract.RARITY_ODDS_ID,
            contract.build_rarity_odds_rows(),
        ),
        contract.CHARACTER_3_ODDS_LOGICAL: _new_nested(
            contract.CHARACTER_3_ODDS_LOGICAL, contract.CHARACTER_3_ODDS_ID,
            contract.build_character_odds_rows(3, runtime_pool),
        ),
        contract.CHARACTER_4_ODDS_LOGICAL: _new_nested(
            contract.CHARACTER_4_ODDS_LOGICAL, contract.CHARACTER_4_ODDS_ID,
            contract.build_character_odds_rows(4, runtime_pool),
        ),
        contract.CHARACTER_5_ODDS_LOGICAL: _new_nested(
            contract.CHARACTER_5_ODDS_LOGICAL, contract.CHARACTER_5_ODDS_ID,
            contract.build_character_odds_rows(5, runtime_pool),
        ),
        contract.RICH_TEXT_MASTER_LOGICAL: _add_flat(
            common_sources[contract.RICH_TEXT_MASTER_LOGICAL],
            contract.RICH_TEXT_MASTER_LOGICAL, contract.RICH_TEXT_ID, "",
        ),
        contract.RICH_TEXT_BODY_LOGICAL: contract.build_rich_text_body(),
    }

    server_decoded["gacha.json"][contract.GACHA_KEY] = contract.build_server_runtime(
        runtime_pool
    )
    server_decoded["cdndata/gacha.json"][contract.GACHA_KEY] = [master_row]
    server_decoded["cdndata/gacha_feature_content.json"][contract.GACHA_KEY] = {
        "1": [feature_cells]
    }
    files.update({
        path: _canonical_json(server_decoded[path])
        for path in contract.SERVER_OUTPUT_PATHS
    })

    # Full readback and preservation checks precede eligibility reporting.
    for logical in (
        contract.GACHA_MASTER_LOGICAL,
        contract.RICH_TEXT_MASTER_LOGICAL,
    ):
        before = _decode_flat(common_sources[logical], logical)
        after = _decode_flat(files[logical], logical)
        if any(after.get(key) != row for key, row in before.items()):
            raise AssertionError(f"nonowned client rows changed: {logical}")
    before_feature = _decode_raw(common_sources[contract.FEATURE_LOGICAL], contract.FEATURE_LOGICAL)
    after_feature = _decode_raw(files[contract.FEATURE_LOGICAL], contract.FEATURE_LOGICAL)
    if any(after_feature.get(key) != row for key, row in before_feature.items()):
        raise AssertionError("nonowned client rows changed: feature")

    readback_server = {
        path: _strict_json_object(files[path], path)
        for path in contract.SERVER_OUTPUT_PATHS
    }
    for path in contract.SERVER_OUTPUT_PATHS:
        before = _strict_json_object(server_sources[path], path)
        if any(readback_server[path].get(key) != value for key, value in before.items()):
            raise AssertionError(f"nonowned server rows changed: {path}")
    if readback_server["cdndata/gacha.json"][contract.GACHA_KEY] != [master_row]:
        raise AssertionError("gacha master mirror readback mismatch")
    if readback_server["cdndata/gacha_feature_content.json"][contract.GACHA_KEY] != {
        "1": [feature_cells]
    }:
        raise AssertionError("gacha feature mirror readback mismatch")

    all_leaks = _find_character_pool_leaks(readback_server["gacha.json"])
    expected_locations = sorted((value, contract.GACHA_KEY) for value in contract.CHARACTER_IDS)
    if sorted(all_leaks) != expected_locations:
        raise AssertionError("limited pickup pool readback mismatch")
    runtime = readback_server["gacha.json"][contract.GACHA_KEY]
    pickup_total, pickup_each = pool_contract.pickup_rates(runtime["pool"])
    locked_exchange = sorted(
        entry["id"] for entry in runtime["pool"]["1"]
        if entry["isLimited"] and not entry["isExchangeable"]
    )
    if locked_exchange != sorted(contract.NON_EXCHANGEABLE_CHARACTER_IDS):
        raise AssertionError("limited pickup exchange lock readback mismatch")
    if (
        runtime["pageKind"] != 2
        or runtime["onceTicketItemId"] != contract.SINGLE_TICKET_ID
        or runtime["tenTicketItemId"] != contract.TEN_TICKET_ID
        or runtime["wildcardTicketAvailable"] is not False
    ):
        raise AssertionError("ticket-only runtime readback mismatch")
    note = contract.build_rich_text_body()
    if files[contract.RICH_TEXT_BODY_LOGICAL] != note:
        raise AssertionError("rich-text body readback mismatch")

    claims = _claims()
    return {
        "files": files,
        "table_claims": claims,
        "report": {
            "schema_version": 1,
            "status": "compiled_isolated_abyss_gacha",
            "gacha_id": contract.GACHA_ID,
            "code_name": contract.CODE_NAME,
            "character_ids": list(contract.CHARACTER_IDS),
            "non_exchangeable_character_ids": list(
                contract.NON_EXCHANGEABLE_CHARACTER_IDS
            ),
            "standard_exchange_character_ids": list(
                contract.STANDARD_EXCHANGE_CHARACTER_IDS
            ),
            "single_ticket_id": contract.SINGLE_TICKET_ID,
            "ten_ticket_id": contract.TEN_TICKET_ID,
            "payload_count": len(files),
            "table_claim_count": len(claims),
            "nonowned_client_changes": 0,
            "nonowned_server_changes": 0,
            "eight_character_closure": True,
            "standard_pool_contract": True,
            "rank_rates": runtime["rankRates"],
            "limited_character_rate_total_percent": float(pickup_total * 100),
            "limited_character_rate_each_percent": float(pickup_each * 100),
            "limited_character_rate_total_ratio": [
                pickup_total.numerator, pickup_total.denominator
            ],
            "limited_character_rate_each_ratio": [
                pickup_each.numerator, pickup_each.denominator
            ],
            "normal_page_contract": True,
            "exchange_points": {
                "limited": 250,
                "standard": 250,
            },
            "execution_contract": {
                "single": {
                    "exec_type": 3,
                    "ticket_id": contract.SINGLE_TICKET_ID,
                    "pulls_per_ticket": 1,
                },
                "ten": {
                    "exec_type": 4,
                    "ticket_id": contract.TEN_TICKET_ID,
                    "pulls_per_ticket": 10,
                },
            },
            "global_ball_animation_unchanged": (
                master_row[17:19] == ["normal", "normal_guarantee"]
                and runtime["movieName"] == "normal"
                and runtime["guaranteeMovieName"] == "normal_guarantee"
            ),
            "start_date": contract.START_DATE,
            "end_date": contract.END_DATE,
            "unresolved_art_payloads": [
                contract.LIST_BANNER_PAYLOAD_LOGICAL,
                contract.TOP_BANNER_PAYLOAD_LOGICAL,
            ],
            "feature_contract": "static_kind_1_top_banner",
            "output_sha256": {
                path: hashlib.sha256(raw).hexdigest()
                for path, raw in sorted(files.items())
            },
            "writes_live": False,
            "formal_workspace_written": False,
            "table_claims_eligible": True,
            "package_manifest_eligible": False,
        },
    }


__all__ = [
    "COMMON_SOURCE_PATHS", "SERVER_SOURCE_PATHS",
    "compile_abyss_limited_gacha",
]
