"""Choose a scene identity against read-only client/server inputs; do not reserve it."""
from __future__ import annotations

import json
from pathlib import Path
import re

import wf_quest_lib as codec

from .edit_state import leaf
from .schema import iter_leaves, parse_rows
from .scene_clone import clone_scene
from .scene_server import _load
from .scene_server_projection import ITEM, RARE, SCORE, SHOP
from .scene_spec import validate_spec

EVENTS = "master/quest/event/advent_event.orderedmap"
SERVER_ID_TABLES = {ITEM, RARE, SCORE, SHOP}
DELIVERY_EVENT = re.compile(r"^(?:scene|hell-pumpkin)-([3-9][0-9]{5})-[0-9.]+-to-[0-9.]+-[0-9]{8}-[0-9]{6}$")
EVENT_ID_RE = re.compile(r"^[3-9][0-9]{5}$")


def delivered_event_ids(deliveries_dir) -> set[str]:
    if deliveries_dir is None:
        return set()
    root = Path(deliveries_dir)
    if not root.is_dir():
        return set()
    found: set[str] = set()
    for folder in root.iterdir():
        if not folder.is_dir():
            continue
        match = DELIVERY_EVENT.fullmatch(folder.name)
        if match and match[1] != "300097":
            found.add(match[1])
        draft_file = folder / "inputs" / "draft.json"
        if draft_file.is_file():
            try:
                draft = json.loads(draft_file.read_text("utf-8"))
                payload = draft.get("payload") if isinstance(draft, dict) else None
                event_id = ((payload.get("event") or {}).get("id")
                            if isinstance(payload, dict) and isinstance(payload.get("event"), dict) else None)
                if isinstance(event_id, str) and EVENT_ID_RE.fullmatch(event_id) and (
                        payload.get("creation") or event_id != "300097"):
                    found.add(event_id)
            except (OSError, ValueError):
                pass
        cs_file = folder / "inputs" / "changeset.json"
        if cs_file.is_file():
            try:
                cs = json.loads(cs_file.read_text("utf-8"))
                for change in (cs.get("changes") or []) if isinstance(cs, dict) else ():
                    if (isinstance(change, dict) and change.get("table") == EVENTS
                            and isinstance(change.get("path"), list) and len(change["path"]) == 1
                            and isinstance(change["path"][0], str) and EVENT_ID_RE.fullmatch(change["path"][0])
                            and change["path"][0] != "300097"):
                        found.add(change["path"][0])
            except (OSError, ValueError):
                pass
    return found


def _numeric_ids(value):
    """Server keys and ID lists only; reward counts are not identifiers."""
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).isdigit():
                yield str(key)
            yield from _numeric_ids(child)
    elif isinstance(value, list):
        for child in value:
            if type(child) is int or isinstance(child, str) and child.isdigit():
                yield str(child)
            else:
                yield from _numeric_ids(child)


def allocate_scene(spec, loader, *, server_dir=None, reserved=(), deliveries_dir=None, name=None):
    """Return a cloned payload. Preview/save/build must still repeat collision checks."""
    validate_spec(spec)
    if spec.get("creation"):
        raise ValueError("自动分配须从已有活动母本开始")
    if isinstance(reserved, (str, bytes)):
        raise ValueError("reserved 必须是活动 ID 列表")
    reserved_ids = {str(value) for value in reserved}
    if any(not value.isdigit() or not 300000 <= int(value) <= 999999 for value in reserved_ids):
        raise ValueError("保留活动 ID 必须在 300000–999999 范围内")
    delivered_ids = delivered_event_ids(deliveries_dir)
    reserved_ids |= delivered_ids
    tables = {}
    for logical in {EVENTS, *(table["logical"] for table in spec["tables"])}:
        try:
            raw = loader(logical)
            if raw is None:
                raise FileNotFoundError(logical)
            tables[logical] = codec.parse_node(raw)
        except (FileNotFoundError, KeyError) as exc:
            raise ValueError("当前视图缺少活动占用表，无法证明新 ID 未占用：" + logical) from exc
        if not isinstance(tables[logical], dict):
            raise ValueError("只读活动占用表不是 orderedmap")
    occupied_codes = set()
    for _, text in iter_leaves(tables[EVENTS]):
        if isinstance(text, str):
            parsed = parse_rows(text)
            if parsed and parsed[0]:
                occupied_codes.add(parsed[0][0])
    server_ids = set()
    if server_dir is not None:
        try:
            _, server = _load(Path(server_dir).resolve())
            server_ids.update(_numeric_ids(server))
        except (OSError, ValueError, TypeError) as exc:
            raise ValueError("只读服务端占用镜像不完整，未分配新活动 ID") from exc
    occupied_events = set(tables[EVENTS]) | reserved_ids | server_ids | {spec["event"]["id"]}
    existence = {}

    def exists(logical):
        if logical not in existence:
            try:
                existence[logical] = loader(logical) is not None
            except (FileNotFoundError, KeyError):
                existence[logical] = False
        return existence[logical]

    for number in range(300001, 1000000):
        event = str(number)
        if event in occupied_events:
            continue
        cloned = clone_scene(spec, event, name)
        cloned_event_entries = [entry["value"] for table in cloned["tables"]
                                if table["logical"] == EVENTS for entry in table["entries"]
                                if entry["path"] == [event]]
        cloned_rows = parse_rows(cloned_event_entries[0]) if cloned_event_entries else []
        if cloned_rows and cloned_rows[0] and cloned_rows[0][0] in occupied_codes:
            continue
        targets = cloned["creation"]["tableTargets"]
        # Only economic row identities map to server IDs. Battle tables also
        # contain fixed numeric grouping keys (e.g. watch root "1").
        derived = {event, *(tier["quest"] for tier in cloned["tiers"]),
                   *(target["path"][0] for target in targets
                     if target["logical"] in SERVER_ID_TABLES
                     and target["path"][0].isdigit() and target["path"][0].startswith(event))}
        if derived & server_ids:
            continue
        if any(leaf(tables[target["logical"]], target["path"]) is not None for target in targets):
            continue
        if any(exists(logical) for logical in cloned["creation"]["resourceTargets"]):
            continue
        cloned["provenance"]["allocation"] = {
            "eventId": event, "clientTablesChecked": len(tables),
            "serverSnapshotChecked": server_dir is not None,
            "deliveriesChecked": len(delivered_ids), "reserved": False,
            "note": "只读占用检查后的候选 ID，未预留；保存与生成时仍须重新防撞。"}
        return cloned
    raise ValueError("没有可用的新场景活动 ID；未预留或写入任何编号")
