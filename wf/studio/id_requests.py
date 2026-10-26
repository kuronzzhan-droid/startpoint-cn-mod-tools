"""Typed IDs introduced by uncompiled ability requests."""
from wf.balance.rows import TABLES, WIDTHS, column_index
from wf.boss.schema import parse_rows
from wf.view.layout import EM, col, mode_col
from wfx_registry import patch_kinds_borrowing_uid_column

from .id_catalog import table


def ability_ids(operations, source=None, table_rows=None):
    """Read the native layout; c2 is an ability category, never a unique ID."""
    documents = {}
    for operation in operations:
        name, action = operation.get("table"), operation.get("op")
        if name not in WIDTHS:
            continue
        if name not in documents:
            raw_rows = (table_rows or {}).get(TABLES[name])
            if raw_rows is None:
                raw_rows = table(source, TABLES[name]) if source is not None else {}
            documents[name] = {key: parse_rows(leaf) for key, leaf in raw_rows.items() if isinstance(leaf, str)}
        records = documents[name].setdefault(operation["key"], [])
        index = operation.get("row", 0)
        if action in {"delete_row", "move_row"}:
            if 0 <= index < len(records):
                removed = records.pop(index)
                if action == "move_row":
                    records.insert(operation["to_row"], removed)
            continue
        if action not in {"set_cells", "insert_row", "attach_key"}:
            continue
        groups = operation.get("rows", []) if action == "attach_key" else [operation.get("cells", [])]
        base = records[index] if action == "set_cells" and 0 <= index < len(records) else []
        if action == "attach_key" and groups:
            records.clear()
        for cells in groups:
            row = list(base) if base else [""] * WIDTHS[name]
            changed = set()
            for cell in cells:
                column = column_index(name, cell["column"], operation.get("column_space", "ability"))
                row[column] = cell["new"] or ""
                if cell["new"] != cell.get("old"):
                    changed.add(column)
            if 0 in changed and row[0] not in {"", "(None)"}:
                yield "string_id", row[0]
            for block, start in EM["layouts"][name]["blocks"].items():
                if (block, row[int(start)]) in patch_kinds_borrowing_uid_column():
                    continue
                fields = EM["block_fields"]["precondition" if block.startswith("precondition") else block]
                for offset, field, _ in fields:
                    position = int(start) + int(offset)
                    if field == "unique_condition_id" and position in changed:
                        value = row[position]
                        if value.isdigit() and int(value) > 0:
                            yield "unique_condition", value
            position = col(name, "instant_content", "string_id")
            if (position in changed and row[mode_col(name)] == "0"
                    and row[col(name, "instant_content", "kind")] == "629"
                    and row[position] not in {"", "(None)"}):
                yield "string_id", row[position]
            if action == "attach_key":
                records.append(row)
            elif action == "insert_row":
                records.insert(index, row)
            elif 0 <= index < len(records):
                records[index] = row
