"""The frozen 1.4.312 abyss_weapons scope stays the 15 weapon shop rows."""
from dataclasses import replace
from pathlib import Path

import pytest
import wf_local_release_contract as contract
from wf_local_server_contract import load_contract
from wf.tools.rogue import rogue_shop


SHOP_FILES = {"event_item_shop.json", "event_item_shop_id_map.json"}


def migration_with_shop_keys(keys, *, map_keys=None):
    directory = Path(__file__).resolve().parents[1] / "release-contracts"
    migration = load_contract(directory / contract.MIGRATION_NAME)
    members = tuple(
        replace(member, selector=replace(
            member.selector,
            keys=tuple(map_keys if map_keys is not None
                       and member.logical_path == "event_item_shop_id_map.json" else keys),
        )) if member.logical_path in SHOP_FILES else member
        for member in migration.server_members
    )
    return replace(migration, server_members=members)


def test_server_scope_accepts_the_frozen_weapon_rows():
    contract._validate_server_scope(migration_with_shop_keys(rogue_shop.RESERVED_SHOP_IDS))


def test_server_scope_rejects_ticket_rows_in_the_frozen_contract():
    with pytest.raises(contract.InventoryError, match="selector scope mismatch"):
        contract._validate_server_scope(migration_with_shop_keys(rogue_shop.OWNED_SHOP_IDS))


@pytest.mark.parametrize("keys", [
    rogue_shop.OWNED_SHOP_IDS + ("9700118",),
    rogue_shop.OWNED_SHOP_IDS[:-1],
    rogue_shop.RESERVED_SHOP_IDS + ("9700117",),
    tuple(reversed(rogue_shop.OWNED_SHOP_IDS)),
])
def test_server_scope_rejects_degree_partial_or_reordered_shop(keys):
    with pytest.raises(contract.InventoryError, match="selector scope mismatch"):
        contract._validate_server_scope(migration_with_shop_keys(keys))


def test_server_scope_rejects_mixed_shop_and_id_map_generations():
    with pytest.raises(contract.InventoryError, match="selector scope mismatch"):
        contract._validate_server_scope(migration_with_shop_keys(
            rogue_shop.RESERVED_SHOP_IDS, map_keys=rogue_shop.OWNED_SHOP_IDS,
        ))
