"""Character clone table transforms built on the production character helpers."""
from __future__ import annotations

import re
import zlib
from types import SimpleNamespace

import wf_mod_tool as core
from wf.chars.support import tables as T
from .drafts import DraftError

REQUIRED = (T.CHAR, T.TEXT, T.STATUS, T.MANA_BOARD, T.MANA_NODE,
            T.CHAR_IMAGE, T.FULL_SHOT_ATTR, T.TRIMMED, T.SPEECH, T.SKILL_PREVIEW)
OPTIONAL = (T.GACHA_SOUND, T.AWAKE, T.UPSKILL, T.MANA_OPEN, T.STANCE_DETAIL)


def rows(raw, label="table"):
    table = core.read_orderedmap_raw_rows_from_bytes(raw, label)
    return dict(zip(table.keys, table.rows))


def leaf(cells):
    return zlib.compress(core.write_csv_lines(cells).rstrip("\n").encode("utf-8"))


def insert(raw, additions, logical):
    table = core.read_orderedmap_raw_rows_from_bytes(raw, logical)
    collisions = set(table.keys) & additions.keys()
    if collisions:
        raise DraftError(f"目标键已占用：{logical}: {sorted(collisions)}")
    table.keys.extend(additions)
    table.rows.extend(additions.values())
    return core.build_orderedmap_raw_rows(table)


def _node_ids(blob):
    result = []
    for board in rows(blob).values():
        for node in rows(board).values():
            values = core.read_csv_lines(zlib.decompress(node).decode("utf-8"))
            if len(values) != 1 or len(values[0]) != 7:
                raise DraftError("mana_node 必须是七列叶子行")
            result.append(values[0][0])
    if len(result) != len(set(result)):
        raise DraftError("母本 mana_node 节点号重复")
    return result


def _mana(source, old, new, old_id, new_id):
    original = rows(source[T.MANA_NODE])[old_id]
    ids = _node_ids(original)
    prefix = str(int(old_id) * 2)
    if any(not re.fullmatch(re.escape(prefix) + r"\d{3}", value) for value in ids):
        raise DraftError("母本 mana_node 编号不符合 characterId * 2 + 三位节点后缀，拒绝猜测")
    mapping = {value: str(int(new_id) * 2) + value[-3:] for value in ids}
    occupied = {value for blob in rows(source[T.MANA_NODE]).values() for value in _node_ids(blob)}
    if occupied & set(mapping.values()):
        raise DraftError(f"玛纳节点号已占用：{sorted(occupied & set(mapping.values()))}")
    def remap(value):
        # Prerequisite columns may contain several comma-separated node IDs.
        return ",".join(mapping.get(part, part) for part in value.split(","))
    additions = {}
    for logical in (T.MANA_NODE, T.MANA_BOARD):
        blob = T.clone_blob(rows(source[logical])[old_id], remap)
        # Reject every stale reference, including a board's parent node list (H400).
        text = str(T.decode_blob(blob))
        if any(re.search(r"(?<!\d)" + re.escape(value) + r"(?!\d)", text) for value in ids):
            raise DraftError(f"玛纳板仍引用母本节点：{logical}")
        additions[logical] = {new_id: blob}
    return additions, sorted(mapping.values(), key=int)


def build_tables(source, spec):
    """Return full cloned tables, source hashes inputs and the reserved node list."""
    old_id, new_id, code = spec["from"], spec["to"], spec["code"]
    raw_tables = {}
    for logical in (*REQUIRED, T.ACTION, *OPTIONAL):
        raw = source.raw(logical)
        if raw is None:
            if logical in OPTIONAL:
                continue
            raise DraftError(f"母本缺少必需表：{logical}")
        raw_tables[logical] = raw
    old_row = source.table("character").get(old_id)
    if not old_row or len(old_row[0]) != 37:
        raise DraftError(f"母本角色不存在或不是 37 列：{old_id}")
    old = old_row[0][0]
    for logical in REQUIRED:
        if logical != T.TRIMMED and old_id not in rows(raw_tables[logical]):
            raise DraftError(f"母本缺少必需行：{logical}/{old_id}")
    new_row = list(old_row[0])
    new_row[0], new_row[27] = code, new_id
    new_row[3] = str(spec.get("element", int(new_row[3])))
    if not 0 <= int(new_row[3]) <= 5:
        raise DraftError("角色元素只允许 0–5")
    skill_key = old_row[0][8]
    if skill_key not in rows(raw_tables[T.ACTION]):
        raise DraftError(f"母本技能键不存在：{skill_key}")
    additions = {T.CHAR: {new_id: leaf([new_row])}}
    if spec.get("skill", "copy") == "copy":
        new_row[8] = code
        additions[T.CHAR][new_id] = leaf([new_row])
        # Independent skill key; DSL program paths deliberately retain the proven donor program.
        additions[T.ACTION] = {code: rows(raw_tables[T.ACTION])[skill_key]}
    mapper = T.cell_remap(SimpleNamespace(template_id_s=old_id, cid_s=new_id,
        template_mana_prefix=str(int(old_id) * 2), mana_prefix=str(int(new_id) * 2),
        template_code=old, code=code))
    for logical in (T.TEXT, T.STATUS, T.CHAR_IMAGE, T.FULL_SHOT_ATTR, T.SPEECH, T.SKILL_PREVIEW, *OPTIONAL):
        if logical not in raw_tables or old_id not in rows(raw_tables[logical]):
            continue
        blob = rows(raw_tables[logical])[old_id]
        # All speech paths and status geometry remain valid; speech files copied separately.
        if logical not in (T.STATUS, T.GACHA_SOUND):
            blob = T.clone_blob(blob, mapper)
        additions[logical] = {new_id: blob}
    text = core.read_csv_lines(zlib.decompress(additions[T.TEXT][new_id]).decode("utf-8"))
    if spec.get("name"):
        text[0][0] = spec["name"]
        additions[T.TEXT][new_id] = leaf(text)
    speech = core.read_csv_lines(zlib.decompress(additions[T.SPEECH][new_id]).decode("utf-8"))
    if not speech or any(len(row) != 5 for row in speech):
        raise DraftError("character_speech 必须含五列字幕行")
    if not any(row[1] in ("0", "2") for row in speech) or not any(row[1] in ("1", "2") for row in speech):
        raise DraftError("character_speech 两态必须都有可见行（避免 2265）")
    trimmed = rows(raw_tables[T.TRIMMED])
    targets = {}
    for stem in ("full_shot_1440_1920_0", "full_shot_1440_1920_1", "skill_cutin_0", "skill_cutin_1"):
        key = f"character/{old}/ui/{stem}"
        if key not in trimmed:
            raise DraftError(f"母本缺少立绘定位键：{key}")
        targets[f"character/{code}/ui/{stem}"] = trimmed[key]
    additions[T.TRIMMED] = targets
    mana, ids = _mana(raw_tables, old, code, old_id, new_id)
    if int(new_row[3]) != int(old_row[0][3]):
        items = source.raw(T.ITEM)
        if items is None:
            raise DraftError("修改元素需要 item 表派生玛纳材料映射")
        raw_tables[T.ITEM] = items
        mapping = T.element_material_map(core.read_orderedmap_file_from_bytes(items), int(old_row[0][3]), int(new_row[3]))
        mana[T.MANA_NODE][new_id] = T.remap_mana_node_items(mana[T.MANA_NODE][new_id], mapping, [])
    additions.update(mana)
    return {logical: insert(raw_tables[logical], patch, logical) for logical, patch in additions.items()}, raw_tables, ids


def server_entries(client, cid):
    """Reuse the character flow's validated mana-board derivation and production mirror shape."""
    import wf_character_flow as flow
    char = core.read_csv_lines(core.read_orderedmap_file_from_bytes(client[T.CHAR])[cid])[0]
    text = core.read_csv_lines(core.read_orderedmap_file_from_bytes(client[T.TEXT])[cid])[0]
    node_table = rows(client[T.MANA_NODE])[cid]
    nodes = {}
    for board, blob in rows(node_table).items():
        nodes[board] = {}
        for raw in rows(blob).values():
            row, = core.read_csv_lines(zlib.decompress(raw).decode("utf-8"))
            item_ids, counts = row[2].split(","), row[3].split(",")
            if len(item_ids) != len(counts):
                raise DraftError("mana_node 材料数量与材料 ID 数量不同")
            nodes[board][row[0]] = {"field1": row[1], "field5": row[5], "field6": row[6],
                "items": dict(zip(item_ids, map(int, counts))), "manaCost": int(row[4])}
    return {"character.json": {cid: {"element": int(char[3]), "name": text[0], "rarity": int(char[2]), "skill_count": 6}},
            "cdndata/character.json": {cid: [char]}, "cdndata/character_text.json": {cid: [text]},
            "mana_node.json": {cid: nodes},
            "mana_board.json": flow.character_pack.derive_server_mana_board(client[T.MANA_BOARD], [cid])}
