"""Small byte-preserving operations for boss resource and server overlays."""
from __future__ import annotations

import json

from wf.deliver.json_merge import _json_spans


def delete_keys(raw, keys):
    """Delete top-level JSON members while keeping every surviving value verbatim."""
    text, before, spans = _json_spans(raw)
    keys = set(keys)
    if keys - before.keys():
        raise ValueError(f"missing server keys: {sorted(keys - before.keys())}")
    if not keys:
        return raw
    # Slice original key/value pairs; the JSON decoder handles quoted key escapes.
    decoder = json.JSONDecoder()
    position, kept = text.index("{") + 1, []
    for key, (_, end) in spans.items():
        while text[position].isspace() or text[position] == ",":
            position += 1
        start = position
        parsed, _ = decoder.raw_decode(text, start)
        if parsed != key:
            raise ValueError("server JSON member order mismatch")
        if key not in keys:
            kept.append(text[start:end])
        position = end
    output = ("{\n" + ",\n".join(kept) + "\n}\n").encode("utf-8")
    final, document, after_spans = _json_spans(output)
    assert set(document) == set(before) - keys
    assert all(text[s:e] == final[slice(*after_spans[k])]
               for k, (s, e) in spans.items() if k not in keys)
    return output


def append_values(raw, values):
    """Append unique server IDs without serializing existing array values again."""
    before = json.loads(raw)
    if not isinstance(before, list):
        raise ValueError("server ID registry must be a JSON array")
    additions = []
    for value in values:
        if str(value) not in {str(v) for v in [*before, *additions]}:
            additions.append(value)
    if not additions:
        return raw
    text = raw.decode("utf-8")
    end = text.rfind("]")
    encoded = json.dumps(additions, ensure_ascii=False, allow_nan=False)[1:-1]
    output = (text[:end].rstrip() + ("," if before else "") + "\n" + encoded + "\n" + text[end:]).encode("utf-8")
    assert json.loads(output) == [*before, *additions]
    return output
