#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""资深玩家称号的深渊商店三侧生成器。

默认命令只做 dry-run；本工具不发布、不启动服务，也不操作设备。
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
pass  # Imports resolve from this checkout/package, not external source copies.
import wf_mod_tool as core  # noqa: E402
import wf_quest_lib as quest  # noqa: E402


SHOP_LOGICAL = "master/shop/event_item_shop.orderedmap"
SHOP_TEMPLATE = "310200"
SHOP_ITEM_ID = "9700118"
EVENT_TYPE = "11"
EVENT_ID = "700099"
DEGREE_ID = 9_900_006
CLIENT_COLUMNS = 51
AVAILABLE_FROM = "2000-01-01 00:00:00"
AVAILABLE_UNTIL = "2099-12-31 23:59:59"
THUMBNAIL_LOGICAL = "item/etc/degree"
DEGREE_IMAGE_LOGICAL = "dynamic/degree/degree_mod_veteran_player"
TASK1_PENDING = (
    "66/59fc2049f33c5982f2c9fb1a52e11154e7fbc4",
    "89/e5c25c791e2a9527422c186084a1793218c2ac",
    "5d/9856e7eb2dc4bee1f689a8e5c32da33cad5a0d",
    "ee/05d98ca8eaefaeb883eeb5c93422a6e7856a74",
    "c3/ffd5a3dbe7a6f75d928552aa59dad2c398c85f",
    "4c/bbe4e7208046d6445ee4572abe716dc0ed258f",
)


class DegreeShopError(RuntimeError):
    """输入、碰撞或写入门禁错误。"""


def _single_row(leaf: object, label: str) -> tuple[list[str], bytes | str]:
    if not isinstance(leaf, (bytes, str)):
        raise TypeError(f"{label} 必须是 str/bytes")
    text = leaf.decode("utf-8") if isinstance(leaf, bytes) else leaf
    rows = core.read_csv_lines(text)
    if len(rows) != 1:
        raise ValueError(f"{label} 必须恰好包含 1 行 CSV,实际 {len(rows)}")
    return list(rows[0]), leaf


def _join_like(row: list[str], template: bytes | str) -> bytes | str:
    text = core.write_csv_lines([row])
    return text.encode("utf-8") if isinstance(template, bytes) else text


def _client_leaf(client: dict[str, object]) -> object:
    if SHOP_TEMPLATE not in client:
        raise KeyError(f"客户端商店缺少模板 {SHOP_TEMPLATE}")
    row, template = _single_row(client[SHOP_TEMPLATE], f"client[{SHOP_TEMPLATE}]")
    if len(row) > CLIENT_COLUMNS:
        raise ValueError(
            f"客户端模板 {SHOP_TEMPLATE} 超过 {CLIENT_COLUMNS} 列: {len(row)}"
        )
    row = core.normalize_row_length(row, CLIENT_COLUMNS)
    if len(row) != CLIENT_COLUMNS:
        raise ValueError(f"客户端模板无法规范为 {CLIENT_COLUMNS} 列")

    row[0:7] = ["6", EVENT_ID, EVENT_TYPE, "(None)", "(None)", "(None)", "(None)"]
    row[7:17] = [
        "资深玩家",
        SHOP_ITEM_ID,
        "1",
        "18",
        "资深玩家专属称号。使用500万星导石兑换，每个存档限1次。",
        "(None)",
        THUMBNAIL_LOGICAL,
        "5",
        "0",
        "5000000",
    ]
    row[17:26] = ["(None)"] * 9
    row[26:35] = [
        AVAILABLE_FROM,
        AVAILABLE_UNTIL,
        "0",
        "1",
        "1",
        "(None)",
        "6",
        "(None)",
        "1",
    ]
    row[35:50] = ["(None)"] * 15
    row[50] = "false"
    return _join_like(row, template)


def _server_product() -> dict:
    return {
        "costs": [],
        "rewards": [{"type": 5, "id": DEGREE_ID, "count": 1}],
        "userCost": {"type": 0, "amount": 5_000_000},
        "availableFrom": AVAILABLE_FROM,
        "availableUntil": AVAILABLE_UNTIL,
        "stock": 1,
    }


def build_contract(
    client: dict[str, object], server: dict, id_map: dict
) -> tuple[dict[str, object], dict, dict]:
    """Build all three mirrors without mutating the inputs."""
    if not isinstance(client, dict) or not isinstance(server, dict) or not isinstance(id_map, dict):
        raise TypeError("client/server/id_map 必须都是 dict")

    expected_leaf = _client_leaf(client)
    expected_product = _server_product()
    expected_map = {"eventType": int(EVENT_TYPE), "eventId": int(EVENT_ID)}

    if SHOP_ITEM_ID in client and client[SHOP_ITEM_ID] != expected_leaf:
        raise ValueError(f"客户端商店 ID {SHOP_ITEM_ID} 已被其他条目占用")
    for event_type, events in server.items():
        if not isinstance(events, dict):
            raise TypeError(f"server[{event_type!r}] 必须是 dict")
        for event_id, products in events.items():
            if not isinstance(products, dict):
                raise TypeError(f"server[{event_type!r}][{event_id!r}] 必须是 dict")
            if SHOP_ITEM_ID in products and not (
                str(event_type) == EVENT_TYPE
                and str(event_id) == EVENT_ID
                and products[SHOP_ITEM_ID] == expected_product
            ):
                raise ValueError(
                    f"服务端商店 ID {SHOP_ITEM_ID} 已在 {event_type}/{event_id} 被占用"
                )
    if SHOP_ITEM_ID in id_map and id_map[SHOP_ITEM_ID] != expected_map:
        raise ValueError(f"ID map {SHOP_ITEM_ID} 已被其他条目占用")

    built_client = copy.deepcopy(client)
    built_server = copy.deepcopy(server)
    built_map = copy.deepcopy(id_map)
    built_client[SHOP_ITEM_ID] = expected_leaf
    built_server.setdefault(EVENT_TYPE, {}).setdefault(EVENT_ID, {})[
        SHOP_ITEM_ID
    ] = expected_product
    built_map[SHOP_ITEM_ID] = expected_map
    return built_client, built_server, built_map


def validate_contract(
    client: dict[str, object], server: dict, id_map: dict, store: Path
) -> list[str]:
    """Return all three-side contract violations without writing."""
    problems: list[str] = []
    try:
        row, _ = _single_row(client.get(SHOP_ITEM_ID), f"client[{SHOP_ITEM_ID}]")
    except (TypeError, ValueError, UnicodeError) as exc:
        return [str(exc)]
    if len(row) != CLIENT_COLUMNS:
        return [f"客户端 {SHOP_ITEM_ID} 必须是 {CLIENT_COLUMNS} 列,实际 {len(row)}"]

    expected_row, _ = _single_row(
        _client_leaf({SHOP_TEMPLATE: client.get(SHOP_TEMPLATE)}),
        f"expected[{SHOP_ITEM_ID}]",
    )
    for column, (actual, expected) in enumerate(zip(row, expected_row)):
        if actual != expected:
            problems.append(
                f"客户端 {SHOP_ITEM_ID} c{column}: expected={expected!r}, actual={actual!r}"
            )
    if row[13].endswith(".png"):
        problems.append("客户端 c13 必须是不带 .png 的逻辑路径")
    if row[13].isdigit():
        problems.append("客户端 c13 不得是数字 degree id")
    if row[32] != "6":
        problems.append("客户端 c32 必须是 6(PassCardPoint 代理)")
    if row[33] != "(None)":
        problems.append("客户端 c33 不得发送 degree id")

    target = server.get(EVENT_TYPE, {}).get(EVENT_ID, {}).get(SHOP_ITEM_ID)
    if target != _server_product():
        problems.append("服务端商品与规范不一致: reward 必须 type=5/id=9900006/count=1")
    expected_map = {"eventType": int(EVENT_TYPE), "eventId": int(EVENT_ID)}
    if id_map.get(SHOP_ITEM_ID) != expected_map:
        problems.append(f"ID map {SHOP_ITEM_ID} 与规范不一致")

    store = Path(store)
    # item/etc/degree.png is a locked client/base texture key and deliberately
    # does not become an eighth pending entry. The later share-package gate owns
    # proof that the receiver has that baseline (or an explicit dependency).
    degree_image = DEGREE_IMAGE_LOGICAL + ".png"
    if not core.table_path(store, degree_image).is_file():
        problems.append(f"store 缺少完整图片路径 {degree_image}")
    return problems


def _read_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise DegreeShopError(f"JSON 顶层必须是 object: {path}")
    return data


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=4) + "\n").encode("utf-8")


def _compact_json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False).encode("utf-8")


def _atomic_write(path: Path, payload: bytes) -> None:
    path = Path(path).absolute()
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)


def verify_paths(store: Path, assets_dir: Path) -> list[str]:
    table_path = core.table_path(Path(store), SHOP_LOGICAL)
    try:
        client = quest.load_table(SHOP_LOGICAL, path=table_path)
        server = _read_json(Path(assets_dir) / "event_item_shop.json")
        id_map = _read_json(Path(assets_dir) / "event_item_shop_id_map.json")
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return [str(exc)]
    return validate_contract(client, server, id_map, Path(store))


def write_contract(*, store: Path, assets_dir: Path, pending_path: Path) -> dict:
    """Atomically stage the three data mirrors and the one allowed pending hash."""
    store = Path(store).resolve()
    assets_dir = Path(assets_dir).resolve()
    pending_path = Path(pending_path).resolve()
    try:
        pending_before = json.loads(pending_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DegreeShopError(f"无法读取 pending: {exc}") from exc
    if pending_before != list(TASK1_PENDING):
        raise DegreeShopError(
            f"pending 写前必须精确为 Task 1 六项,实际 {pending_before!r}"
        )

    table_path = core.table_path(store, SHOP_LOGICAL)
    server_path = assets_dir / "event_item_shop.json"
    id_map_path = assets_dir / "event_item_shop_id_map.json"
    try:
        client_before = quest.load_table(SHOP_LOGICAL, path=table_path)
        server_before = _read_json(server_path)
        id_map_before = _read_json(id_map_path)
        client_after, server_after, id_map_after = build_contract(
            client_before, server_before, id_map_before
        )
        problems = validate_contract(
            client_after, server_after, id_map_after, store
        )
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise DegreeShopError(str(exc)) from exc
    if problems:
        raise DegreeShopError("; ".join(problems))

    table_relative = table_path.relative_to(store).as_posix()
    if table_relative in TASK1_PENDING:
        raise DegreeShopError("event_item_shop hash 已混入 Task 1 pending")
    pending_after = [*TASK1_PENDING, table_relative]
    payloads = {
        table_path: quest.build_node(client_after),
        server_path: _compact_json_bytes(server_after),
        id_map_path: _compact_json_bytes(id_map_after),
        pending_path: _json_bytes(pending_after),
    }
    before_images = {
        path: path.read_bytes() if path.is_file() else None for path in payloads
    }
    try:
        for path, payload in payloads.items():
            _atomic_write(path, payload)
        if json.loads(pending_path.read_text(encoding="utf-8")) != pending_after:
            raise DegreeShopError("pending 写后复读不一致")
        readback_problems = verify_paths(store, assets_dir)
        if readback_problems:
            raise DegreeShopError("写后复读失败: " + "; ".join(readback_problems))
    except BaseException:
        for path, payload in reversed(list(before_images.items())):
            if payload is None:
                path.unlink(missing_ok=True)
            else:
                _atomic_write(path, payload)
        raise

    return {
        "shop_item_id": SHOP_ITEM_ID,
        "client_table": table_relative,
        "client_sha256": hashlib.sha256(table_path.read_bytes()).hexdigest(),
        "pending_before": pending_before,
        "pending_after": pending_after,
    }


def _default_store() -> Path:
    active = core.resolve_profile()
    cn = core.resolve_profile("cn")
    if active is None or cn is None or active.id != "cn" or cn.id != "cn":
        raise DegreeShopError("默认写入只允许 active=cn 且 cn profile 存在")
    if active.fallback is not None or cn.fallback is not None:
        raise DegreeShopError("CN profile 必须设置 fallback=null")
    if active.store.resolve() != cn.store.resolve():
        raise DegreeShopError("active/cn store 不一致")
    return active.store.resolve()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="资深玩家深渊商店三侧生成器")
    parser.add_argument("--store", type=Path, help="测试或显式 store 根")
    parser.add_argument("--assets-dir", type=Path, default=ROOT / "assets")
    parser.add_argument(
        "--pending", type=Path, default=ROOT / "mod-tools" / "work" / "sync_pending.json"
    )
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--write", action="store_true", help="通过六项 pending 门禁后写入")
    action.add_argument("--verify", action="store_true", help="只验证已写入的三侧契约")
    args = parser.parse_args(argv)

    try:
        store = args.store.resolve() if args.store else _default_store()
        assets_dir = args.assets_dir.resolve()
        pending_path = args.pending.resolve()
        if args.verify:
            problems = verify_paths(store, assets_dir)
            if problems:
                print("[FAIL] " + "; ".join(problems), file=sys.stderr)
                return 1
            print(f"[OK] {SHOP_ITEM_ID} 三侧契约通过；未发布。")
            return 0
        if args.write:
            result = write_contract(
                store=store, assets_dir=assets_dir, pending_path=pending_path
            )
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
            print("[OK] 已写入并复读；未发布。")
            return 0

        table_path = core.table_path(store, SHOP_LOGICAL)
        client = quest.load_table(SHOP_LOGICAL, path=table_path)
        server = _read_json(assets_dir / "event_item_shop.json")
        id_map = _read_json(assets_dir / "event_item_shop_id_map.json")
        planned = build_contract(client, server, id_map)
        problems = validate_contract(*planned, store)
        if problems:
            raise DegreeShopError("; ".join(problems))
        print(
            f"[DRY-RUN] 将新增 {SHOP_ITEM_ID}: client c32=6, "
            "server reward type=5, userCost.type=0/freeVmoney 5000000；未写入。"
        )
        return 0
    except (DegreeShopError, KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"[ERR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
