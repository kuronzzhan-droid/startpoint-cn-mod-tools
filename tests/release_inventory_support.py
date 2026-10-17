# -*- coding: utf-8 -*-
"""Shared fixture helpers for release inventory tests."""
from __future__ import annotations

import hashlib
import importlib
import json
import sys
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import wf_character_pack as character_pack
import wf_mod_tool as core


LOGICAL = "master/character/character.orderedmap"
NESTED_LOGICAL = "master/skill/action_skill.orderedmap"


def ordered(rows: list[tuple[str, bytes]], *, raw_outer: bool = False) -> bytes:
    table = core.OrderedMap(
        "<fixture>",
        [key for key, _raw in rows],
        [raw for _key, raw in rows],
        Path("<memory>"),
    )
    return (
        core.build_orderedmap_raw_rows(table)
        if raw_outer
        else core.build_orderedmap(table)
    )


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def make_zip(path: Path, entries: dict[str, bytes]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, raw in entries.items():
            archive.writestr(name, raw)


def snapshot_tree(root: Path) -> dict[str, bytes | None]:
    if not root.exists():
        return {}
    result: dict[str, bytes | None] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        result[relative + ("/" if path.is_dir() else "")] = (
            None if path.is_dir() else path.read_bytes()
        )
    return result


class CdnFixture:
    def __init__(self, root: Path):
        self.cdn = root / "cdn" / "cn"
        self.repo = root / "repo"
        for root_name in ("common", "medium", "android"):
            (self.cdn / f"archive-{root_name}-full").mkdir(parents=True)
            (self.cdn / f"archive-{root_name}-diff").mkdir(parents=True)
        (self.repo / "assets" / "asset-patch" / "active").mkdir(parents=True)

    @staticmethod
    def member_name(root: str, logical_path: str) -> str:
        directory = {
            "common": "upload",
            "medium": "medium_upload",
            "android": "android_upload",
        }[root]
        digest = core.sha1_path(logical_path)
        return f"production/{directory}/{digest[:2]}/{digest[2:]}"

    def full(self, raw: bytes, *, seq: int, root: str = "common") -> Path:
        path = (
            self.cdn / f"archive-{root}-full"
            / f"pinball-1.4.0-{seq}-fixture.zip"
        )
        make_zip(path, {self.member_name(root, LOGICAL): raw})
        return path

    def diff(
        self,
        raw: bytes,
        *,
        frm: str,
        to: str,
        seq: int = 1,
        root: str = "common",
    ) -> Path:
        path = (
            self.cdn / f"archive-{root}-diff"
            / f"pinball-{frm}-{to}-{seq}-fixture.zip"
        )
        make_zip(path, {self.member_name(root, LOGICAL): raw})
        return path


class InventoryCase(unittest.TestCase):
    def setUp(self) -> None:
        self.inventory = importlib.import_module("wf_release_inventory")

    @staticmethod
    def flat_claim(*keys: str) -> character_pack.TableClaim:
        return character_pack.TableClaim("common", LOGICAL, "flat", tuple(keys))

    def member(
        self,
        owner: str,
        raw: bytes,
        claim: character_pack.TableClaim,
        *,
        root: str | None = None,
        logical_path: str | None = None,
    ) -> dict[str, object]:
        return {
            "owner": owner,
            "kind": "table",
            "root": root or claim.root,
            "logical_path": logical_path or claim.logical_path,
            "claim": {
                "codec_id": claim.codec_id,
                "outer_keys": list(claim.outer_keys),
                "inner_keys": {
                    outer: list(inner) for outer, inner in claim.inner_keys
                },
            },
            "projection_sha256": self.inventory.projection_sha256(raw, claim),
            "source": {"size": len(raw), "sha256": sha256(raw)},
        }

    @staticmethod
    def file_member(
        owner: str, raw: bytes, *, logical_path: str = "character/hero/icon.png"
    ) -> dict[str, object]:
        return {
            "owner": owner,
            "kind": "file",
            "root": "common",
            "logical_path": logical_path,
            "size": len(raw),
            "sha256": sha256(raw),
        }

    @staticmethod
    def payload(members: list[dict[str, object]]) -> dict[str, object]:
        return {
            "schema": "wf-release-inventory/v1",
            "contract_id": "fixture-contract",
            "members": members,
        }

    def parse(self, payload: dict[str, object]):
        return self.inventory.parse_contract(
            json.dumps(payload, separators=(",", ":")).encode("utf-8")
        )
