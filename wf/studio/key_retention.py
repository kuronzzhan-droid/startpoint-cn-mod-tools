"""Describe inner-key loss and CSV record shrinkage without inventing row IDs."""
import csv
import io

from wf.caps.requirements import parse_table


def _records(value):
    return sum(bool(row) for row in csv.reader(io.StringIO(value, newline=""), strict=True))


def _walk(before, after, path):
    if isinstance(before, dict):
        if not isinstance(after, dict):
            yield {"kind": "nested_map_replaced", "path": path}
            return
        for key, value in before.items():
            if key not in after:
                yield {"kind": "nested_key_removed", "path": [*path, key]}
            else:
                yield from _walk(value, after[key], [*path, key])
    elif isinstance(before, str):
        old = _records(before)
        if not isinstance(after, str):
            yield {"kind": "csv_replaced", "path": path, "beforeRows": old}
        else:
            new = _records(after)
            if new < old:
                yield {"kind": "csv_rows_removed", "path": path, "beforeRows": old,
                       "afterRows": new, "removedRows": old - new}


def inner_deletions(before, after, logical, changed):
    if not changed:
        return []
    old, new = parse_table(before, logical), parse_table(after, logical)
    return [detail for key in sorted(changed) for detail in _walk(old[key], new[key], [key])]
