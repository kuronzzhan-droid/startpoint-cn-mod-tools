"""Add object keys while preserving untouched top-level JSON value bytes."""
import json

from wf.deliver.json_merge import _json_spans, merge_json


def merged_bytes(before, old, merged):
    if before is None:
        return (json.dumps(merged, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()
    bom = b"\xef\xbb\xbf" if before.startswith(b"\xef\xbb\xbf") else b""
    live = before[len(bom):]
    candidate = json.dumps(merged, ensure_ascii=False, allow_nan=False).encode()
    changed = [key for key in old if old[key] != merged[key]]
    output, _ = merge_json(live, candidate, changed)
    additions = [key for key in merged if key not in old]
    if additions:
        text, _, _ = _json_spans(output)
        end = text.rfind("}")
        newline = "\r\n" if "\r\n" in text else "\n" if "\n" in text else ""
        entries = ("," + newline).join(
            json.dumps(key, ensure_ascii=False) + ":" +
            json.dumps(merged[key], ensure_ascii=False, separators=(",", ":"), allow_nan=False)
            for key in additions)
        text = text[:end] + ("," if old else "") + newline + entries + newline + text[end:]
        output = text.encode()
    return bom + output
