#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""深渊限定扭蛋券的纯内存数据与共享 item 图集编译器。"""
from __future__ import annotations

import copy
import hashlib
import io
import zlib
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from PIL import Image, UnidentifiedImageError

import wf_mod_tool as core
import wf_assets
import wf_dsl


ITEM_T = "master/item/item.orderedmap"
GACHA_TICKET_TYPE_T = "master/item/gacha_ticket_type.orderedmap"
ITEM_SHEET_LOGICAL = "item/sprite_sheet.png"
ITEM_ATLAS_LOGICAL = "item/sprite_sheet.atlas.amf3.deflate"
SOURCE_ASSET_DIR = Path(__file__).resolve().parent / "assets" / "abyss-gacha-tickets"
LOCKED_ICON_SHA256: Mapping[str, str] = MappingProxyType(
    {
        "abyss_once_gacha_character_ticket.png":
            "bf6be3234d530c7f206c92fcc4f04544f9e6e102dd10a470766207ef5d168c50",
        "abyss_ten_times_gacha_character_ticket.png":
            "f1a04683c0288783240064e65e5ff3c5f120bb6f89be4204774cd74645a7e454",
    }
)


@dataclass(frozen=True)
class TicketSpec:
    item_id: str
    donor_id: str
    marker: str
    name: str
    description: str
    kind: str
    icon_name: str
    source_name: str


@dataclass(frozen=True)
class ItemAssetChanges:
    sheet_payload: bytes
    atlas_payload: bytes
    source_sha256: dict[str, str]


TICKETS = (
    TicketSpec(
        item_id="999013",
        donor_id="999003",
        marker="abyss_once_gacha_character_ticket",
        name="深渊单抽券",
        description="可用于进行1次「深渊限定扭蛋」角色抽取的专用扭蛋券",
        kind="1",
        icon_name="item/spends/tickets/abyss_once_gacha_character_ticket",
        source_name="abyss_once_gacha_character_ticket.png",
    ),
    TicketSpec(
        item_id="999014",
        donor_id="999001",
        marker="abyss_ten_times_gacha_character_ticket",
        name="深渊十连券",
        description="可用于进行1次「深渊限定扭蛋」角色10连抽取的专用扭蛋券",
        kind="2",
        icon_name="item/spends/tickets/abyss_ten_times_gacha_character_ticket",
        source_name="abyss_ten_times_gacha_character_ticket.png",
    ),
)
TICKET_IDS = tuple(spec.item_id for spec in TICKETS)
_EXPECTED_TICKET_TYPES = {
    "1": ["one_time_character", "角色扭蛋1回", "2"],
    "2": ["ten_times_character", "角色扭蛋10回", "20"],
}


def validate_ticket_type_table(table: dict[str, object]) -> None:
    """Validate the unchanged official dependency used by ticket item kinds."""
    if not isinstance(table, dict):
        raise TypeError("gacha_ticket_type 表必须是 dict")
    for kind, expected in _EXPECTED_TICKET_TYPES.items():
        if kind not in table:
            raise ValueError(f"gacha_ticket_type 缺少角色券 kind {kind}")
        row, _leaf = _single_row(table[kind], f"gacha_ticket_type[{kind}]")
        if row != expected:
            raise ValueError(
                f"gacha_ticket_type 角色券 kind {kind} 漂移: "
                f"expected={expected!r}, actual={row!r}"
            )


def build_item_ids(values: list[object]) -> list[int]:
    """Return the server item-id mirror with the owned ticket range closed."""
    if not isinstance(values, list):
        raise TypeError("item_ids 镜像必须是 list")
    try:
        return sorted({*(int(value) for value in values), *(int(x) for x in TICKET_IDS)})
    except (TypeError, ValueError) as exc:
        raise ValueError("item_ids 镜像必须只含整数 ID") from exc


def compile_item_assets(
    sheet_payload: bytes,
    atlas_payload: bytes,
    source_dir: Path,
    *,
    expected_sha256: Mapping[str, str],
    specs: tuple[TicketSpec, ...] = TICKETS,
) -> ItemAssetChanges:
    """Compile two SHA-locked 20x20 icons into the shared item atlas."""
    expected_names = {spec.source_name for spec in specs}
    if set(expected_sha256) != expected_names:
        raise ValueError("外部美术 SHA-256 门禁必须精确覆盖两张深渊券图标")
    source_dir = Path(source_dir)
    source_images: dict[str, Image.Image] = {}
    source_hashes: dict[str, str] = {}
    for spec in specs:
        source = source_dir / spec.source_name
        if not source.is_file():
            raise ValueError(f"外部美术缺失: {spec.source_name}")
        payload = source.read_bytes()
        actual = hashlib.sha256(payload).hexdigest()
        expected = str(expected_sha256[spec.source_name]).lower()
        if len(expected) != 64 or any(ch not in "0123456789abcdef" for ch in expected):
            raise ValueError(f"外部美术 SHA-256 锁格式非法: {spec.source_name}")
        if actual != expected:
            raise ValueError(
                f"外部美术 SHA-256 不匹配 {spec.source_name}: "
                f"expected={expected}, actual={actual}"
            )
        source_hashes[spec.source_name] = actual
        try:
            with Image.open(io.BytesIO(payload)) as image:
                image.load()
                if image.size != (20, 20) or image.mode != "RGBA":
                    raise ValueError(
                        f"外部美术必须是 20x20 RGBA PNG: {spec.source_name}; "
                        f"actual={image.size[0]}x{image.size[1]} {image.mode}"
                    )
                source_images[spec.source_name] = image.copy()
        except UnidentifiedImageError as exc:
            raise ValueError(f"外部美术不是有效 PNG: {spec.source_name}") from exc

    if not isinstance(sheet_payload, bytes) or not sheet_payload.startswith(
        wf_assets.PNG_FAKE
    ):
        raise ValueError("item/sprite_sheet.png 必须是客户端存储态 PNG")
    try:
        with Image.open(io.BytesIO(wf_assets.png_decode(sheet_payload))) as image:
            image.load()
            sheet = image.convert("RGBA")
    except UnidentifiedImageError as exc:
        raise ValueError("item/sprite_sheet.png 不是有效 PNG") from exc

    try:
        atlas = wf_dsl.parse_dsl(zlib.decompress(atlas_payload, -15))["tree"]
    except (TypeError, ValueError, zlib.error, EOFError) as exc:
        raise ValueError("item/sprite_sheet.atlas 不是有效 raw-deflate AMF3") from exc
    if not isinstance(atlas, list) or not all(isinstance(entry, dict) for entry in atlas):
        raise ValueError("item/sprite_sheet.atlas 根必须是对象数组")

    target_names = {spec.icon_name for spec in specs}
    target_entries = {
        name: [entry for entry in atlas if entry.get("n") == name]
        for name in target_names
    }
    present = {name for name, entries in target_entries.items() if entries}
    if present:
        if present != target_names:
            raise ValueError("item 图集只存在部分深渊券目标帧")
        expected_y = sheet.height - 21
        for index, spec in enumerate(specs):
            entries = target_entries[spec.icon_name]
            if len(entries) != 1:
                raise ValueError(f"item 图集目标帧重复: {spec.icon_name}")
            x = 1 + index * 21
            expected_entry = {
                "n": spec.icon_name,
                "w": 20,
                "h": 20,
                "x": x,
                "y": expected_y,
            }
            if entries[0] != expected_entry:
                raise ValueError(f"item 图集目标帧被外来数据占用: {spec.icon_name}")
            crop = sheet.crop((x, expected_y, x + 20, expected_y + 20))
            if crop.tobytes() != source_images[spec.source_name].tobytes():
                raise ValueError(f"item 图集目标帧像素漂移: {spec.icon_name}")
        return ItemAssetChanges(
            sheet_payload=sheet_payload,
            atlas_payload=atlas_payload,
            source_sha256=source_hashes,
        )

    new_y = sheet.height + 1
    x_positions = tuple(1 + index * 21 for index in range(len(specs)))
    if x_positions and x_positions[-1] + 20 > sheet.width:
        raise ValueError("item/sprite_sheet.png 宽度不足以追加两张 20x20 图标")
    compiled = Image.new("RGBA", (sheet.width, sheet.height + 22), (0, 0, 0, 0))
    compiled.paste(sheet, (0, 0))
    compiled_atlas = copy.deepcopy(atlas)
    for spec, x in zip(specs, x_positions):
        compiled.paste(source_images[spec.source_name], (x, new_y))
        compiled_atlas.append(
            {"n": spec.icon_name, "w": 20, "h": 20, "x": x, "y": new_y}
        )

    png_output = io.BytesIO()
    compiled.save(png_output, format="PNG", optimize=False, compress_level=9)
    encoded_sheet = wf_assets.png_encode(png_output.getvalue())
    compressor = zlib.compressobj(level=9, wbits=-15)
    atlas_plain = wf_dsl.encode_amf3(compiled_atlas)
    encoded_atlas = compressor.compress(atlas_plain) + compressor.flush()
    return ItemAssetChanges(
        sheet_payload=encoded_sheet,
        atlas_payload=encoded_atlas,
        source_sha256=source_hashes,
    )


def compile_locked_item_assets(
    sheet_payload: bytes, atlas_payload: bytes
) -> ItemAssetChanges:
    """Production entrypoint pinned to the reviewed external art bytes."""
    return compile_item_assets(
        sheet_payload,
        atlas_payload,
        SOURCE_ASSET_DIR,
        expected_sha256=LOCKED_ICON_SHA256,
    )


def _leaf_text(leaf: bytes | str) -> str:
    if isinstance(leaf, bytes):
        return leaf.decode("utf-8")
    if isinstance(leaf, str):
        return leaf
    raise TypeError(f"orderedmap 叶子必须是 str/bytes,得到 {type(leaf).__name__}")


def _single_row(leaf: object, label: str) -> tuple[list[str], bytes | str]:
    if not isinstance(leaf, (bytes, str)):
        raise TypeError(f"{label} 必须是 str/bytes")
    rows = core.read_csv_lines(_leaf_text(leaf))
    if len(rows) != 1:
        raise ValueError(f"{label} 必须恰好包含 1 行 CSV,实际 {len(rows)}")
    return list(rows[0]), leaf


def _join_like(row: list[str], template: bytes | str) -> bytes | str:
    text = core.write_csv_lines([row])
    return text.encode("utf-8") if isinstance(template, bytes) else text


def _expected_item_leaves(
    table: dict[str, object], specs: tuple[TicketSpec, ...]
) -> dict[str, object]:
    expected: dict[str, object] = {}
    for spec in specs:
        if spec.donor_id not in table:
            raise KeyError(f"item 缺少官方供体 {spec.donor_id}")
        row, donor_leaf = _single_row(
            table[spec.donor_id], f"item[{spec.donor_id}]"
        )
        if len(row) <= 13:
            raise ValueError(f"item[{spec.donor_id}] 必须至少 14 列")
        if row[13] != spec.kind:
            raise ValueError(
                f"item[{spec.donor_id}] kind 漂移: "
                f"expected={spec.kind}, actual={row[13]}"
            )
        row[0] = spec.marker
        row[1] = spec.item_id
        row[2] = spec.name
        row[3] = spec.icon_name
        row[5] = spec.description
        row[13] = spec.kind
        expected[spec.item_id] = _join_like(row, donor_leaf)
    return expected


def build_item_table(
    table: dict[str, object], specs: tuple[TicketSpec, ...] = TICKETS
) -> dict[str, object]:
    """克隆官方单抽/十连券供体，并只占用 999013..999014。"""
    if not isinstance(table, dict):
        raise TypeError("item 表必须是 dict")
    expected = _expected_item_leaves(table, specs)
    for item_id, leaf in expected.items():
        if item_id in table and table[item_id] != leaf:
            raise ValueError(f"保留道具 ID {item_id} 已被外来条目占用")
    result = copy.deepcopy(table)
    for item_id in expected:
        result.pop(item_id, None)
    result.update(expected)
    return result
