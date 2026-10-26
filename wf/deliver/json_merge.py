"""Key-scoped JSON merge preserving every unselected value byte.

Extracted from the C content-revision helper during M0 consolidation.
"""

import json


def _pairs(values):
    output = {}
    for key, value in values:
        if key in output:
            raise ValueError('duplicate JSON key: ' + key)
        output[key] = value
    return output


def _json_spans(raw):
    """解析顶层JSON对象的value字节文本片段；引号/转义/嵌套交给标准解码器。"""
    text = raw.decode('utf-8')

    def constant(value):
        raise ValueError('non-finite JSON value: ' + value)
    decoder = json.JSONDecoder(object_pairs_hook=_pairs, parse_constant=constant)
    value, end = decoder.raw_decode(text, len(text) - len(text.lstrip()))
    if not isinstance(value, dict) or text[end:].strip():
        raise ValueError('expected exactly one JSON object')
    spans, position = ({}, text.index('{') + 1)
    while True:
        while text[position].isspace():
            position += 1
        if text[position] == '}':
            break
        key, position = decoder.raw_decode(text, position)
        while text[position].isspace():
            position += 1
        if text[position] != ':':
            raise ValueError('invalid JSON member separator')
        position += 1
        while text[position].isspace():
            position += 1
        start = position
        _, position = decoder.raw_decode(text, position)
        spans[key] = (start, position)
        while text[position].isspace():
            position += 1
        if text[position] == ',':
            position += 1
        elif text[position] != '}':
            raise ValueError('invalid JSON item separator')
    return (text, value, spans)


def merge_json(live, candidate, keys):
    text, a, spans = _json_spans(live)
    _, b, _ = _json_spans(candidate)
    if set(keys) - a.keys() or set(keys) - b.keys():
        raise ValueError('JSON revision requires existing live and candidate keys')
    changed = {key for key in keys if a[key] != b[key]}
    for key in sorted(changed, key=lambda key: spans[key][0], reverse=True):
        begin, end = spans[key]
        text = text[:begin] + json.dumps(b[key], ensure_ascii=False, separators=(',', ':'), allow_nan=False) + text[end:]
    output = text.encode('utf-8') if changed else live
    original, _, _ = _json_spans(live)
    final, _, final_spans = _json_spans(output)
    assert all((original[s:e] == final[slice(*final_spans[key])] for key, (s, e) in spans.items() if key not in changed))
    return (output, dict(changed_keys=sorted(changed), preserved_row_count=len(a) - len(changed), excluded_candidate_differences=sorted((k for k in a.keys() | b.keys() if k not in keys and a.get(k) != b.get(k)))))
