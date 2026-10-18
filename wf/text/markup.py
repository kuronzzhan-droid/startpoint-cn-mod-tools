"""Deterministic author markup checks with explicit slot evidence."""
from __future__ import annotations

import re

MAIN_ICON = " <icon id='main'>  "


def main_icon(text, key, slots):
    wrong = []
    groups = {}
    for slot in slots:
        if slot.get("kind") == "ability":
            groups.setdefault((slot.get("table"), slot.get("key")), []).append(slot)
    # Mixed unrestricted/main-only rows are not an entirely main-only slot.
    # Mapping individual prose lines back to those rows remains a semantic check.
    required = any(all(slot.get("main_only") for slot in group) for group in groups.values())
    for line in text.splitlines():
        if not line.strip():
            continue
        has_icon = bool(re.search(r"<icon\b[^>]*\bid\s*=\s*['\"]main['\"]", line))
        if required or has_icon:
            # startswith alone accepts a third trailing space; the prefix is exact.
            if not line.startswith(MAIN_ICON) or line[len(MAIN_ICON):][:1].isspace():
                wrong.append(line)
    return wrong


def compressed_lines(text, key):
    # The six-element enumeration is explicitly required by the same standard.
    # Names and the documented six-element list are not two ability records.
    visible = re.sub(r"「[^」]*」|『[^』]*』", "", text)
    visible = visible.replace("（火／水／雷／风／光／暗各结算1次）", "")
    effect = re.compile(r"[+＋\-－]\s*\d|提升|提高|增加|降低|减少|发动|召唤|赋予|获得|变为|无效|强化")
    wrong = []
    for line in visible.splitlines():
        parts = line.split("／")
        if any(effect.search(left) and effect.search(right) for left, right in zip(parts, parts[1:])):
            wrong.append(line)
    return wrong
