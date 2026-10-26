"""Production primitives extracted from wf_seasonal7_tables.py (C baseline)."""
from __future__ import annotations
import json


import re


import zlib


from datetime import datetime


from typing import Any, Callable


import wf_mod_tool as core


from wf.chars.support import common as C


from wf.chars.support import specs as S


CHAR = "master/character/character.orderedmap"


TEXT = "master/character/character_text.orderedmap"


AWAKE = "master/character/character_awake_status.orderedmap"


STATUS = "master/character/character_status.orderedmap"


GACHA_SOUND = "master/character/character_gacha_sound.orderedmap"


CHAR_IMAGE = "master/generated/character_image.orderedmap"


FULL_SHOT_ATTR = "master/character/full_shot_image_attribute.orderedmap"


TRIMMED = "master/generated/trimmed_image.orderedmap"


MANA_BOARD = "master/generated/mana_board.orderedmap"


MANA_NODE = "master/mana_board/mana_node.orderedmap"


UPSKILL = "master/mana_board/upskill.orderedmap"


MANA_OPEN = "master/mana_board/mana_board2_open_condition.orderedmap"


SKILL_PREVIEW = "master/skill_preview/skill_preview_character.orderedmap"


STANCE_DETAIL = "master/stance_detail/character_stance_detail.orderedmap"


SPEECH = "master/character/character_speech.orderedmap"


ABILITY = "master/ability/ability.orderedmap"


LEADER = "master/ability/leader_ability.orderedmap"


CAS = "master/string/custom_ability_string.orderedmap"


ITEM = "master/item/item.orderedmap"


STANCE_ROLLS = {"Attacker": "1", "Healer": "2", "Tank": "3", "Supporter": "4", "Jammer": "5"}


STANCE_ROLL_COLS = (2, 6)                  # character_stance_detail：主位 / 合击位 roll 列


STANCE_ROLL_MAX = 2                        # live 581 行 roll 列最多 2 个值（1 个 374 行，2 个 207 行）


ACTION = core.ACTION_SKILL_LOGICAL


SERVER_TIME_CUTOFF = datetime(2025, 8, 5, 0, 0, 0)


SAFE_OPEN_START = "2015-03-01 12:00:00"      # live 已有 4 个母本行的修正值


def program_path(spec: S.SeasonalSpec, level: str) -> str:
    return f"battle/action/skill/action/rare{spec.rarity}/{spec.code}${spec.code}_{level}"


def cell_remap(spec: S.SeasonalSpec) -> Callable[[str], str]:
    """整格/路径段边界的母本→新角色映射（前缀型 code 安全）。"""
    tid, cid = spec.template_id_s, spec.cid_s
    old_mana = re.compile(r"^" + re.escape(spec.template_mana_prefix) + r"(\d{3})$")
    exact_code = re.compile(r"^" + re.escape(spec.template_code) + r"(_\d+)?$")
    path_seg = re.compile(r"(?<![A-Za-z0-9_])character/" + re.escape(spec.template_code) + r"/")

    def remap(cell: str) -> str:
        if cell == tid:
            return cid
        m = old_mana.match(cell)
        if m:
            return spec.mana_prefix + m.group(1)
        m = exact_code.match(cell)
        if m:
            return spec.code + (m.group(1) or "")
        return path_seg.sub(f"character/{spec.code}/", cell)

    return remap


def _zlib_level(blob: bytes, text: str) -> int:
    raw = text.encode("utf-8")
    for level in (9, -1, 6, 8, 7, 5, 4, 3, 2, 1):
        if zlib.compress(raw, level) == blob:
            return level
    return -1


def clone_blob(blob: bytes, transform: Callable[[str], str]) -> bytes:
    """递归克隆 raw_outer 行：CSV 叶子逐格映射；未变化的层原字节返回，变化的叶子按原压缩档重压。"""
    try:
        text = zlib.decompress(blob).decode("utf-8")
    except (zlib.error, UnicodeDecodeError):
        inner = core.read_orderedmap_raw_rows_from_bytes(blob, "nested")
        keys = [transform(k) for k in inner.keys]
        rows = [clone_blob(r, transform) for r in inner.rows]
        if keys == list(inner.keys) and rows == list(inner.rows):
            return blob
        return core.build_orderedmap_raw_rows(core.OrderedMap("nested", keys, rows, inner.source_path))
    rows = core.read_csv_lines(text)
    mapped = [[transform(c) for c in row] for row in rows]
    new_text = core.write_csv_lines(mapped).rstrip("\n")
    if mapped == rows:
        return blob
    return zlib.compress(new_text.encode("utf-8"), _zlib_level(blob, text))


def clone_blob_rows(blob: bytes, row_fn: Callable[[list[list[str]]], list[list[str]]]) -> bytes:
    """同 :func:`clone_blob`，但按整行（知道列号）变换 CSV 叶子。"""
    try:
        text = zlib.decompress(blob).decode("utf-8")
    except (zlib.error, UnicodeDecodeError):
        inner = core.read_orderedmap_raw_rows_from_bytes(blob, "nested")
        rows = [clone_blob_rows(r, row_fn) for r in inner.rows]
        if rows == list(inner.rows):
            return blob
        return core.build_orderedmap_raw_rows(core.OrderedMap("nested", list(inner.keys), rows,
                                                              inner.source_path))
    rows = core.read_csv_lines(text)
    mapped = row_fn([list(r) for r in rows])
    if mapped == rows:
        return blob
    return zlib.compress(core.write_csv_lines(mapped).rstrip("\n").encode("utf-8"), _zlib_level(blob, text))


def decode_blob(blob: bytes) -> Any:
    try:
        return zlib.decompress(blob).decode("utf-8")
    except (zlib.error, UnicodeDecodeError):
        inner = core.read_orderedmap_raw_rows_from_bytes(blob, "nested")
        return {k: decode_blob(r) for k, r in zip(inner.keys, inner.rows)}


def template_character_row(pack: C.S7Pack) -> list[str]:
    spec = pack.spec
    rows = pack.template_flat(CHAR)
    if spec.template_id_s not in rows:
        raise C.S7Error(f"template {spec.template_id} missing from character table")
    row = C.csv_split(rows[spec.template_id_s])[0]
    if len(row) != 37:
        raise C.S7Error(f"template character row length {len(row)} != 37")
    if row[0] != spec.template_code or int(row[3]) != spec.template_element:
        raise C.S7Error(f"template row identity mismatch: code={row[0]} element={row[3]}")
    return row


def character_row(pack: C.S7Pack, template: list[str]) -> list[str]:
    import wf_client_legality as legality
    spec = pack.spec
    row = list(template)
    row[0] = spec.code
    row[2] = str(spec.rarity)
    row[3] = str(spec.element)
    row[6] = str(spec.pf_type)
    row[8] = spec.code
    row[17] = spec.cid_s
    row[18] = spec.texts["leader"]
    row[19:25] = spec.ability_keys
    row[26] = spec.stance
    row[27] = str(spec.identity)
    problems = legality.character_stance_problems(row)
    if problems:
        raise C.S7Error(f"character stance illegal: {problems}")
    return row


def skill_texts(pack: C.S7Pack, template_inner: dict[str, str]) -> dict[str, tuple[str, str]]:
    spec = pack.spec
    out = {}
    for level, text in template_inner.items():
        cells = C.csv_split(text)[0]
        name = spec.texts.get(f"skill{level}") if level in ("1", "2") else None
        desc = spec.texts.get(f"desc{level}") if level in ("1", "2") else None
        out[level] = (name if name is not None else cells[0],
                      desc if desc is not None else C.replace_element_words(
                          cells[1], spec.template_element, spec.element))
    return out


def _existing_row(pack: C.S7Pack, logical: str, key: str) -> list[str] | None:
    if not pack.pkg_has("common", logical):
        return None
    rows = pack.pkg_flat(logical)
    if key not in rows:
        return None
    return C.csv_split(rows[key])[0]


def character_text_row(pack: C.S7Pack, template_text: list[str],
                       skills: dict[str, tuple[str, str]],
                       existing: list[str] | None = None) -> list[str]:
    spec = pack.spec
    t = spec.texts
    inherited = existing if existing is not None and len(existing) > 11 else template_text
    cv = t["cv"] if t.get("cv") is not None else (inherited[11] if len(inherited) > 11 else "--")
    s1 = skills.get("1", ("", ""))
    s2 = skills.get("2", s1)
    return [t["name"], t["furigana"], t["profile"], t["title"], s1[0], s1[1], s2[0], s2[1],
            "(None)", "(None)", t["leader"], cv]


def known_gacha_ses(pack: C.S7Pack) -> set[str]:
    """母本来源 gacha_sound 全表里出现过的 SE（APK 内置 SE 不在 store，但被官方行引用即可解析）。"""
    found: set[str] = set()

    def collect(node: Any) -> None:
        if isinstance(node, dict):
            for value in node.values():
                collect(value)
        elif isinstance(node, str):
            for row in C.csv_split(node):
                found.update(cell for cell in row if cell.startswith("sound_effect/"))

    for blob in pack.template_raw(GACHA_SOUND).values():
        try:
            collect(decode_blob(blob))
        except Exception:
            continue
    return found


def _gacha_transform(pack: C.S7Pack, report: list[dict]) -> Callable[[str], str]:
    spec = pack.spec
    old_dir = S.ELEMENT_SE_DIRS[spec.template_element]
    known = known_gacha_ses(pack) if spec.element_flip else set()

    def transform(cell: str) -> str:
        if not spec.element_flip:
            return cell
        parts = cell.split(",")
        out = []
        for part in parts:
            if part.startswith(f"sound_effect/{old_dir}/"):
                if part not in spec.gacha_se_map:
                    raise C.S7Error(f"element flip needs gacha SE mapping for {part}")
                new = spec.gacha_se_map[part]
                in_store = pack.live_locate(new + ".mp3") is not None
                if not in_store and new not in known:
                    raise C.S7Error(f"mapped gacha SE neither in live store nor used by official rows: {new}")
                report.append({"table": GACHA_SOUND, "before": part, "after": new,
                               "basis": "live store mp3" if in_store else "official gacha_sound usage"})
                out.append(new)
            else:
                out.append(part)
        return ",".join(out)

    return transform


def open_condition_row(text: str, report: list[dict]) -> str:
    rows = C.csv_split(text)
    for row in rows:
        if not row:
            continue
        try:
            start = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
        if start > SERVER_TIME_CUTOFF:
            report.append({"table": MANA_OPEN, "before": row[0], "after": SAFE_OPEN_START,
                           "reason": "server clock pinned at 2025-08-05"})
            row[0] = SAFE_OPEN_START
    return C.csv_join(rows)


def stance_detail_rows(rows: list[list[str]], template_stance: str, new_stance: str,
                       notes: list[dict]) -> list[list[str]]:
    """stance 改变时重写 character_stance_detail 的主位/合击位 roll（c2/c6）。

    新 stance 的 roll 放首位，母本 stance 的 roll 去掉，其余副 roll 保留顺序；空格保持空。
    官方 489 行全是单行 8 列。新 stance 为 Balance（无单一 roll）时保留母本并记 note。
    每格最多 STANCE_ROLL_MAX 个 roll：live 581 行里没有超过 2 个的先例；母本是 Balance
    （没有可去掉的主 roll）时会多出一个，按顺序截掉末尾的副 roll。
    """
    if template_stance == new_stance:
        return rows
    if new_stance not in STANCE_ROLLS:
        notes.append({"table": STANCE_DETAIL, "kept_template": True,
                      "reason": f"stance {new_stance} has no single roll"})
        return rows
    new_roll, old_roll = STANCE_ROLLS[new_stance], STANCE_ROLLS.get(template_stance)
    out = []
    for row in rows:
        if len(row) != 8:
            raise C.S7Error(f"character_stance_detail row must have 8 cells: {row}")
        row = list(row)
        for col in STANCE_ROLL_COLS:
            before = row[col]
            if not before:
                continue
            rest = [r for r in before.split(",") if r not in (new_roll, old_roll)]
            row[col] = ",".join([new_roll, *rest][:STANCE_ROLL_MAX])
            if row[col] != before:
                notes.append({"table": STANCE_DETAIL, "col": col, "before": before, "after": row[col],
                              "reason": f"stance {template_stance} -> {new_stance}"})
        out.append(row)
    return out


def element_material_items(item_rows: dict[str, str]) -> dict[str, tuple[str, str, str]]:
    """``ability_material_*`` 道具：item id -> (element c12, 种类 c15, 档位 c17)。无元素（如 99 梦境纹章）不列。"""
    found: dict[str, tuple[str, str, str]] = {}
    for iid, text in item_rows.items():
        rows = C.csv_split(text)
        if not rows or not rows[0] or not rows[0][0].startswith("ability_material_"):
            continue
        row = rows[0]
        if len(row) < 18 or row[12] == "":
            continue
        found[iid] = (row[12], row[15], row[17])
    return found


def element_material_map(item_rows: dict[str, str], old_el: int, new_el: int) -> dict[str, str]:
    """旧元素玛纳材料 -> 新元素同种类同档位材料（从 item 表推导，不写死 ID）。"""
    materials = element_material_items(item_rows)
    by_slot: dict[tuple[str, str, str], list[str]] = {}
    for iid, key in materials.items():
        by_slot.setdefault(key, []).append(iid)
    mapping: dict[str, str] = {}
    for (element, kind, tier), ids in sorted(by_slot.items()):
        if element != str(old_el):
            continue
        targets = by_slot.get((str(new_el), kind, tier), [])
        if len(ids) != 1 or len(targets) != 1:
            raise C.S7Error(f"ambiguous element material slot kind={kind} tier={tier}: "
                            f"{element}->{ids}, {new_el}->{targets}")
        mapping[ids[0]] = targets[0]
    if not mapping:
        raise C.S7Error(f"no element materials found for element {old_el}")
    return mapping


def remap_mana_node_items(blob: bytes, mapping: dict[str, str], changes: list[dict]) -> bytes:
    """mana_node 叶子行 c2（逗号分隔材料 id）按映射改写；其余列不动。"""
    def row_fn(rows: list[list[str]]) -> list[list[str]]:
        out = []
        for row in rows:
            if len(row) != 7:
                raise C.S7Error(f"mana_node row must have 7 cells: {row}")
            items = row[2].split(",")
            new_items = [mapping.get(i, i) for i in items]
            if new_items != items:
                changes.append({"table": MANA_NODE, "node": row[0], "col": 2,
                                "before": row[2], "after": ",".join(new_items)})
                row = [*row[:2], ",".join(new_items), *row[3:]]
            out.append(row)
        return out
    return clone_blob_rows(blob, row_fn)


def mana_node_item_elements(blob: bytes, materials: dict[str, tuple[str, str, str]]) -> dict[str, set[str]]:
    """包内 mana_node 行用到的带元素材料：element -> {item id}。"""
    found: dict[str, set[str]] = {}

    def walk_blob(b: bytes) -> None:
        try:
            text = zlib.decompress(b).decode("utf-8")
        except (zlib.error, UnicodeDecodeError):
            for r in core.read_orderedmap_raw_rows_from_bytes(b, "nested").rows:
                walk_blob(r)
            return
        for row in C.csv_split(text):
            for iid in (row[2].split(",") if len(row) > 2 else []):
                if iid in materials:
                    found.setdefault(materials[iid][0], set()).add(iid)
    walk_blob(blob)
    return found


def custom_string_key_map(spec: S.SeasonalSpec) -> Callable[[str], str | None]:
    """``change_skill[_N]_<母本>[_N]`` / ``desc_override_<母本>[_N]`` -> 新 code 同形键；不匹配返回 None。"""
    pattern = re.compile(r"^((?:change_skill(?:_\d+)?|desc_override)_)" + re.escape(spec.template_code)
                         + r"((?:_\d+)?)$")

    def mapper(cell: str) -> str | None:
        m = pattern.match(cell)
        return None if m is None else f"{m.group(1)}{spec.code}{m.group(2)}"
    return mapper


def server_mana_node(pack: C.S7Pack) -> dict[str, Any]:
    """从包内客户端 mana_node 表派生服务端行（celtie server_mana）。"""
    spec = pack.spec
    outer = core.read_orderedmap_raw_rows_from_bytes(pack.pkg_path("common", MANA_NODE).read_bytes(), MANA_NODE)
    boards = core.read_orderedmap_raw_rows_from_bytes(dict(zip(outer.keys, outer.rows))[spec.cid_s], "boards")
    result: dict[str, Any] = {}
    for board, blob in zip(boards.keys, boards.rows):
        slots = core.read_orderedmap_raw_rows_from_bytes(blob, "slots")
        entries = {}
        for raw in slots.rows:
            row, = core.read_csv_lines(zlib.decompress(raw).decode("utf-8"))
            if len(row) != 7 or not re.fullmatch(re.escape(spec.mana_prefix) + r"\d{3}", row[0]):
                raise C.S7Error(f"invalid remapped mana node row {row}")
            entries[row[0]] = {"field1": row[1], "field5": row[5], "field6": row[6],
                               "items": dict(zip(row[2].split(","), map(int, row[3].split(",")))),
                               "manaCost": int(row[4])}
        result[board] = entries
    return result



__all__ = [name for name in globals() if not name.startswith("__")]
