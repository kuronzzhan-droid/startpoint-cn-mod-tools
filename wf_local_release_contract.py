#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Load and read-only attest the frozen local-live 1.4.312 contract bundle."""
from __future__ import annotations

import hashlib
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import wf_mod_tool as core
import wf_release_inventory as inventory
import wf_store_materialize
from wf_local_release_provenance import (
    ProvenanceContract,
    load_provenance,
    parse_provenance,
)
from wf_local_server_contract import MigrationContract, load_contract as load_migrations
from wf_release_inventory_contract import InventoryContract, InventoryError


TERMINAL_NAME = "local-live-terminal-1.4.312.json"
PROVENANCE_NAME = "local-live-baseline-provenance.json"
MIGRATION_NAME = "local-live-migrations-1.4.312.json"
BASELINE_NAMES = {
    "1.4.277": "local-live-baseline-1.4.277.json",
    "1.4.311": "local-live-baseline-1.4.311.json",
}
FORBIDDEN_LOGICALS = frozenset({
    "master/battle/zako/general_zako.orderedmap",
    "master/battle/zako/zako_level.orderedmap",
    "master/battle/boss/general_enemy_watch.orderedmap",
    "master/battle/boss/orochi.orderedmap",
})


@dataclass(frozen=True, slots=True)
class ContractBundle:
    terminal: InventoryContract
    baselines: dict[str, InventoryContract]
    provenance: ProvenanceContract
    migrations: MigrationContract

    @property
    def baseline_versions(self) -> tuple[str, ...]:
        return tuple(self.baselines)

    @property
    def client_unique_path_count(self) -> int:
        return len({member.key for member in self.terminal.members})


def _member_source(member: inventory.InventoryMember) -> tuple[int, str]:
    if member.kind == "file":
        return member.size, member.sha256  # type: ignore[return-value]
    return member.source_size, member.source_sha256  # type: ignore[return-value]


def _expected_archive_member(root: str, logical: str) -> str:
    directory = {
        "common": "upload", "medium": "medium_upload", "android": "android_upload"
    }[root]
    digest = core.sha1_path(logical)
    return f"production/{directory}/{digest[:2]}/{digest[2:]}"


def _validate_server_scope(migrations: MigrationContract) -> None:
    weapon_keys = tuple(str(value) for value in range(8000101, 8000116))
    shop_keys = tuple(str(value) for value in range(9700101, 9700116))
    quest_keys = tuple(str(700099000 + value) for value in range(1, 31)) + (
        "700099099",
    )
    expected: set[tuple[object, ...]] = set()
    for owner, key in (("lafu_lunar_ny", "169998"), ("ginovi", "169999")):
        for logical in (
            "cdndata/character.json", "cdndata/character_text.json",
            "character.json", "mana_node.json",
        ):
            expected.add((owner, logical, "object_keys", (), (key,), ()))
    for logical in (
        "equipment_lookup.json", "equipment_max_level.json",
        "equipment_element.json",
    ):
        expected.add(("abyss_weapons", logical, "object_keys", (), weapon_keys, ()))
    expected.update({
        ("abyss_weapons", "equipment_ids.json", "array_subsequence", (), (),
         tuple(range(8000101, 8000116))),
        ("abyss_700099_core", "item_ids.json", "array_subsequence", (), (),
         (2370099,)),
        ("abyss_weapons", "event_item_shop.json", "object_keys",
         ("11", "700099"), shop_keys, ()),
        ("abyss_weapons", "event_item_shop_id_map.json", "object_keys", (),
         shop_keys, ()),
        ("abyss_tower", "rush_event_quest.json", "object_keys", (),
         quest_keys, ()),
        ("abyss_tower", "rush_event_quest_folder.json", "object_keys", (),
         ("700099",), ()),
        ("abyss_tower", "rogue_event.json", "object_keys", ("events",),
         ("700099",), ()),
    })
    actual = {
        (
            member.owner, member.logical_path, member.selector.kind,
            member.selector.path, member.selector.keys, member.selector.values,
        )
        for member in migrations.server_members
    }
    if actual != expected or len(migrations.server_members) != len(expected):
        raise InventoryError("migration server selector scope mismatch")


def validate_bundle(bundle: ContractBundle) -> None:
    if bundle.terminal.contract_id != "local-live-terminal-1-4-312":
        raise InventoryError("terminal contract id mismatch")
    if len(bundle.terminal.members) != 257 or bundle.client_unique_path_count != 233:
        raise InventoryError("terminal contract must contain 257 members / 233 paths")
    if any(member.root == "server" for member in bundle.terminal.members):
        raise InventoryError("server members must use the independent migration contract")
    if FORBIDDEN_LOGICALS & {member.logical_path for member in bundle.terminal.members}:
        raise InventoryError("terminal contract expanded into forbidden tower ownership")
    if bundle.provenance.terminal_contract_id != bundle.terminal.contract_id:
        raise InventoryError("provenance terminal contract id mismatch")
    if bundle.provenance.contract_id != "local-live-baseline-provenance-1-4-312":
        raise InventoryError("provenance contract id mismatch")
    if bundle.migrations.terminal_contract_id != bundle.terminal.contract_id:
        raise InventoryError("migration terminal contract id mismatch")
    if bundle.migrations.contract_id != "local-live-migrations-1-4-312":
        raise InventoryError("migration contract id mismatch")
    _validate_server_scope(bundle.migrations)
    for version, baseline in bundle.baselines.items():
        expected_id = f"local-live-baseline-{version.replace('.', '-')}"
        if baseline.contract_id != expected_id:
            raise InventoryError(f"baseline {version} contract id mismatch")

    terminal_owners: dict[tuple[str, str], set[str]] = {}
    terminal_tables: dict[tuple[str, str], dict[str, inventory.InventoryMember]] = {}
    for member in bundle.terminal.members:
        terminal_owners.setdefault(member.key, set()).add(member.owner)
        if member.kind == "table":
            terminal_tables.setdefault(member.key, {})[member.owner] = member
    provenance_by_key = {member.key: member for member in bundle.provenance.members}
    if set(provenance_by_key) != set(terminal_owners):
        raise InventoryError("provenance path set differs from terminal contract")
    for key, owners in terminal_owners.items():
        if set(provenance_by_key[key].owners) != owners:
            raise InventoryError(f"provenance owner drift for {key[0]}:{key[1]}")

    for version, baseline in bundle.baselines.items():
        present = {
            member.key for member in bundle.provenance.members
            if member.versions[version] is not None
        }
        if {member.key for member in baseline.members} != present:
            raise InventoryError(f"baseline {version} path set differs from provenance")
        baseline_by_key: dict[
            tuple[str, str], list[inventory.InventoryMember]
        ] = {}
        for member in baseline.members:
            baseline_by_key.setdefault(member.key, []).append(member)
            evidence = provenance_by_key[member.key].versions[version]
            assert evidence is not None
            if _member_source(member) != (evidence.size, evidence.sha256):
                raise InventoryError(f"baseline {version} source drift for {member.key}")
            if evidence.archive_member != _expected_archive_member(*member.key):
                raise InventoryError(f"baseline {version} archive member drift")
            if member.key in terminal_tables:
                claims = {claim.owner: claim for claim in evidence.table_claims}
                if set(claims) != set(terminal_tables[member.key]):
                    raise InventoryError(f"baseline {version} table claim coverage drift")
                if member.kind == "table":
                    claim = claims.get(member.owner)
                    if (
                        claim is None or not claim.present
                        or claim.projection_sha256 != member.projection_sha256
                    ):
                        raise InventoryError(f"baseline {version} projection drift")
        for key in present:
            evidence = provenance_by_key[key].versions[version]
            assert evidence is not None
            members = baseline_by_key[key]
            if key not in terminal_tables:
                if evidence.table_claims or len(members) != 1 or members[0].kind != "file":
                    raise InventoryError(f"baseline {version} opaque/table claim conflict")
                continue
            claim_state = {claim.owner: claim for claim in evidence.table_claims}
            present_owners = {
                owner for owner, claim in claim_state.items() if claim.present
            }
            table_owners = {
                member.owner for member in members if member.kind == "table"
            }
            file_members = [member for member in members if member.kind == "file"]
            if present_owners:
                if table_owners != present_owners or file_members:
                    raise InventoryError(
                        f"baseline {version} present table claim/member mismatch"
                    )
            elif table_owners or len(file_members) != 1:
                raise InventoryError(
                    f"baseline {version} absent table claims need one exact source"
                )

    if len(bundle.migrations.client_tables) != 1:
        raise InventoryError("migration client table set must be exact")
    migration = bundle.migrations.client_tables[0]
    shop_key = ("common", "master/shop/event_item_shop.orderedmap")
    terminal_shop = terminal_tables.get(shop_key, {}).get("abyss_weapons")
    if terminal_shop is None:
        raise InventoryError("migration shop contract is missing its endpoint")
    if (
        migration.owner != "abyss_weapons"
        or migration.root != terminal_shop.root
        or migration.logical_path != terminal_shop.logical_path
        or migration.claim != terminal_shop.claim
        or migration.terminal.projection_sha256 != terminal_shop.projection_sha256
        or (migration.terminal.source_size, migration.terminal.source_sha256)
        != _member_source(terminal_shop)
    ):
        raise InventoryError("migration terminal does not match terminal shop claim")


def load_bundle(directory: Path) -> ContractBundle:
    root = Path(directory)
    bundle = ContractBundle(
        inventory.load_contract(root / TERMINAL_NAME),
        {
            version: inventory.load_contract(root / name)
            for version, name in BASELINE_NAMES.items()
        },
        load_provenance(root / PROVENANCE_NAME),
        load_migrations(root / MIGRATION_NAME),
    )
    validate_bundle(bundle)
    return bundle


def _attest_provenance_version(
    provenance: ProvenanceContract,
    version: str,
    cdn_root: Path,
    repo_root: Path,
) -> None:
    present = [member for member in provenance.members if member.versions[version]]
    resolved = inventory.resolve_allowlisted_members(
        cdn_root, repo_root, (member.key for member in present), target_tail=version
    )
    for member in present:
        expected = member.versions[version]
        assert expected is not None
        actual = resolved[member.key]
        try:
            writer = actual.writer_archive.resolve().relative_to(Path(repo_root).resolve()).as_posix()
        except ValueError as error:
            raise InventoryError(f"baseline writer escapes repo: {actual.writer_archive}") from error
        if (
            writer != expected.writer
            or actual.archive_member != expected.archive_member
            or len(actual.raw) != expected.size
            or hashlib.sha256(actual.raw).hexdigest() != expected.sha256
        ):
            raise InventoryError(f"baseline provenance drift for {version}:{member.key}")
    plan = wf_store_materialize.build_read_only_plan(
        Path(cdn_root), Path(repo_root), version, False
    )
    for member in provenance.members:
        if member.versions[version] is not None:
            continue
        digest = core.sha1_path(member.logical_path)
        if (member.root, f"{digest[:2]}/{digest[2:]}") in plan.entries:
            raise InventoryError(f"baseline absence drift for {version}:{member.key}")


def attest_bundle_baselines(
    bundle: ContractBundle, cdn_root: Path, repo_root: Path
) -> tuple[inventory.AttestationReport, ...]:
    reports: list[inventory.AttestationReport] = []
    for version, contract in bundle.baselines.items():
        reports.append(inventory.attest_baseline(
            contract, cdn_root, repo_root, target_tail=version
        ))
        _attest_provenance_version(bundle.provenance, version, cdn_root, repo_root)
    return tuple(reports)


def require_release_artifacts(cdn_root: Path, version: str) -> tuple[Path, ...]:
    parts = version.split(".")
    if len(parts) < 2 or any(not part.isdigit() for part in parts):
        raise InventoryError(f"invalid release version {version!r}")
    predecessor = ".".join([*parts[:-1], str(int(parts[-1]) - 1)])
    pattern = re.compile(
        rf"^pinball-{re.escape(predecessor)}-{re.escape(version)}-"
        rf"([1-9][0-9]*)-[a-z0-9][a-z0-9_.-]*\.zip$"
    )
    matches: list[Path] = []
    malformed: list[Path] = []
    for root in ("common", "medium", "android"):
        directory = Path(cdn_root) / f"archive-{root}-diff"
        for path in directory.glob(f"pinball-*-{version}-*.zip"):
            if pattern.fullmatch(path.name) is None or not zipfile.is_zipfile(path):
                malformed.append(path)
            else:
                matches.append(path)
    if malformed:
        raise InventoryError(
            f"non-canonical or invalid ZIP for {predecessor}->{version}: {malformed[0]}"
        )
    if not matches:
        raise InventoryError(
            f"missing required release artifacts for {predecessor}->{version}"
        )
    return tuple(sorted(matches))


def snapshot_metadata(roots: Iterable[Path]) -> tuple[tuple[str, int, int], ...]:
    snapshot: list[tuple[str, int, int]] = []
    for raw_root in roots:
        root = Path(raw_root)
        if not root.exists():
            snapshot.append((str(root.resolve()), -1, -1))
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file():
                stat = path.stat()
                snapshot.append((str(path.resolve()), stat.st_size, stat.st_mtime_ns))
    return tuple(snapshot)
