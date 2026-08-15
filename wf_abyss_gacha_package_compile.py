#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pure top-level compiler for the thunder-dragon abyss-gacha package."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Collection, Mapping

import wf_abyss_gacha_banner_compile as banner_compile
import wf_abyss_gacha_compile as gacha_compile
import wf_abyss_gacha_contract as gacha_contract
import wf_abyss_gacha_package_contract as contract
from wf_abyss_gacha_package_components import (
    ComponentResult,
    compile_drop_component,
    compile_shop_component,
    compile_ticket_component,
)
from wf_character_pack import windows_logical_path_key


@dataclass(frozen=True)
class AdditionSources:
    gacha_common: Mapping[str, bytes]
    gacha_server: Mapping[str, bytes]
    existing_common_paths: Collection[str]
    item_raw: bytes
    ticket_type_raw: bytes
    item_ids_raw: bytes
    item_sheet_raw: bytes
    item_atlas_raw: bytes
    shop_client_raw: bytes
    shop_server_raw: bytes
    shop_id_map_raw: bytes
    rogue_event_raw: bytes
    rush_event_quest_raw: bytes


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise contract.PackageAssemblyError(
            "addition source inventory is not strict JSON"
        ) from exc


def _gacha_component(sources: AdditionSources) -> ComponentResult:
    result = gacha_compile.compile_abyss_limited_gacha(
        sources.gacha_common,
        sources.gacha_server,
        existing_common_paths=sources.existing_common_paths,
    )
    if (
        result["report"].get("payload_count") != 11
        or result["report"].get("table_claim_count") != 10
        or result["report"].get("eight_character_closure") is not True
        or result["report"].get("ticket_only_contract") is not True
        or result["report"].get("writes_live") is not False
        or result["report"].get("unresolved_art_payloads") != [
            gacha_contract.LIST_BANNER_LOGICAL,
            gacha_contract.TOP_BANNER_LOGICAL,
        ]
    ):
        raise contract.PackageAssemblyError("gacha component report is not eligible")
    roots = {root: {} for root in contract.ROOT_NAMES}
    for logical, raw in result["files"].items():
        root = "server" if logical in gacha_contract.SERVER_OUTPUT_PATHS else "common"
        roots[root][logical] = raw
    inputs = {
        **{
            f"common:{logical}": _sha(raw)
            for logical, raw in sorted(sources.gacha_common.items())
        },
        **{
            f"server:{logical}": _sha(raw)
            for logical, raw in sorted(sources.gacha_server.items())
        },
        "existing_common_paths": _sha(_canonical(sorted(
            str(path) for path in sources.existing_common_paths
        ))),
    }
    report = dict(result["report"])
    report.update({
        "unresolved_art_payloads": [],
        "art_payloads_bound_by_banner_component": [
            gacha_contract.LIST_BANNER_LOGICAL,
            gacha_contract.TOP_BANNER_LOGICAL,
        ],
        "package_manifest_eligible": True,
    })
    return ComponentResult(
        roots, tuple(result["table_claims"]), inputs, report
    )


def _banner_component() -> ComponentResult:
    result = banner_compile.compile_locked_banners()
    if (
        set(result.files) != {
            gacha_contract.LIST_BANNER_LOGICAL,
            gacha_contract.TOP_BANNER_LOGICAL,
        }
        or result.report.get("payload_count") != 2
        or result.report.get("package_manifest_eligible") is not True
        or result.report.get("writes_live") is not False
    ):
        raise contract.PackageAssemblyError("banner component report is not eligible")
    roots = {root: {} for root in contract.ROOT_NAMES}
    roots["common"].update(result.files)
    source_hashes = result.report.get("source_sha256")
    if not isinstance(source_hashes, Mapping):
        raise contract.PackageAssemblyError("banner source hashes are absent")
    return ComponentResult(
        roots,
        (),
        {str(name): str(value) for name, value in source_hashes.items()},
        dict(result.report),
    )


def _merge_components(
    components: Mapping[str, ComponentResult],
) -> contract.AdditionBundle:
    expected_names = {"gacha", "tickets", "shop", "drop", "banners"}
    if set(components) != expected_names:
        raise contract.PackageAssemblyError("component set is not exact")
    roots: dict[str, dict[str, bytes]] = {
        root: {} for root in contract.ROOT_NAMES
    }
    seen: set[tuple[str, object]] = set()
    claims: list[Mapping[str, Any]] = []
    inputs: dict[str, str] = {}
    reports: dict[str, Mapping[str, Any]] = {}
    for name in ("gacha", "tickets", "shop", "drop", "banners"):
        component = components[name]
        if set(component.roots) != set(contract.ROOT_NAMES):
            raise contract.PackageAssemblyError(
                f"component roots are not exact: {name}"
            )
        for root in contract.ROOT_NAMES:
            for logical, raw in component.roots[root].items():
                key = (root, windows_logical_path_key(logical))
                if key in seen:
                    raise contract.PackageAssemblyError(
                        f"component output aliases another payload: {root}:{logical}"
                    )
                seen.add(key)
                roots[root][logical] = raw
        claims.extend(component.table_claims)
        for label, digest in component.input_sha256.items():
            qualified = f"{name}:{label}"
            if qualified in inputs:
                raise contract.PackageAssemblyError(
                    f"duplicate component input evidence: {qualified}"
                )
            inputs[qualified] = digest
        reports[name] = dict(component.report)

    actual_paths = {
        (root, logical)
        for root in contract.ROOT_NAMES for logical in roots[root]
    }
    if actual_paths != set(contract.NEW_PATHS):
        raise contract.PackageAssemblyError(
            "component payload set is not exact: "
            f"missing={sorted(set(contract.NEW_PATHS)-actual_paths)}, "
            f"extra={sorted(actual_paths-set(contract.NEW_PATHS))}"
        )
    if [dict(claim) for claim in claims] != contract.expected_new_claims():
        raise contract.PackageAssemblyError("component table claim set is not exact")
    if any(
        not isinstance(digest, str)
        or len(digest) != 64
        or any(ch not in "0123456789abcdef" for ch in digest)
        for digest in inputs.values()
    ):
        raise contract.PackageAssemblyError("component input hash evidence is invalid")

    acceptance = {
        "all_references_closed": False,
        "eight_character_closure": True,
        "ticket_contract_closed": True,
        "shop_contract_closed": True,
        "drop_contract_closed": False,
        "drop_source_sync_closed": False,
        "art_contract_closed": True,
        "unresolved_art_payloads": [],
        "package_manifest_eligible": False,
        "writes_live": False,
    }
    return contract.AdditionBundle(
        roots=roots,
        table_claims=tuple(claims),
        input_sha256=dict(sorted(inputs.items())),
        component_reports=reports,
        acceptance=acceptance,
    )


def compile_additions(sources: AdditionSources) -> contract.AdditionBundle:
    """Compile and close all 21 new payloads without filesystem writes."""

    if not isinstance(sources, AdditionSources):
        raise TypeError("sources must be AdditionSources")
    components = {
        "gacha": _gacha_component(sources),
        "tickets": compile_ticket_component(
            item_raw=sources.item_raw,
            ticket_type_raw=sources.ticket_type_raw,
            item_ids_raw=sources.item_ids_raw,
            sheet_raw=sources.item_sheet_raw,
            atlas_raw=sources.item_atlas_raw,
        ),
        "shop": compile_shop_component(
            client_raw=sources.shop_client_raw,
            server_shop_raw=sources.shop_server_raw,
            id_map_raw=sources.shop_id_map_raw,
        ),
        "drop": compile_drop_component(
            rogue_event_raw=sources.rogue_event_raw,
            rush_event_quest_raw=sources.rush_event_quest_raw,
        ),
        "banners": _banner_component(),
    }
    return _merge_components(components)


def compile_package_image(
    source: contract.SealedSourcePackage,
    sources: AdditionSources,
    *,
    generator_git_head: str,
) -> contract.PackageImage:
    """Compile and audit the complete 104-payload image in memory."""

    additions = compile_additions(sources)
    if additions.acceptance.get("drop_source_sync_closed") is not True:
        raise contract.PackageAssemblyError(
            "drop source sync closure is pending; package image is fail-closed"
        )
    return contract.build_package_image(
        source, additions, generator_git_head=generator_git_head
    )


__all__ = [
    "AdditionSources", "compile_additions", "compile_package_image",
]
