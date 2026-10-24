"""Re-read compiled client tables before a draft can produce a delivery."""
from __future__ import annotations

import json

from .model import ABILITY, CHARACTER, CUSTOM, LEADER, TextWorkspace, custom_text
from .slots import override_slots
from .standard import check_entry


def check_compiled_text(source, members):
    """Check changed overrides and rules newly activated by compiled slot rows.

    Historical unrelated violations stay visible and nonblocking. No stored
    editor result is trusted: both the strings and slot c0/c1 are decoded from
    the actual compiled bytes, falling back to the same baseline view.
    """
    relevant = {ABILITY, CHARACTER, CUSTOM, LEADER}
    if not any(root == "common" and logical in relevant for root, logical in members):
        return []

    class CompiledView:
        def read_raw(self, logical):
            key = ("common", logical)
            return (members[key], "compiled-draft") if key in members else source.view.read_raw(logical)

    before, after = TextWorkspace(source.view), TextWorkspace(CompiledView())
    old_strings, strings = before.table(CUSTOM), after.table(CUSTOM)
    old_slots, slots = override_slots(before), override_slots(after)
    results = []
    for key, leaf in strings.items():
        if not key.startswith("desc_override_"):
            continue
        found = check_entry(key, custom_text(leaf), slots=slots.get(key, ()))
        prior = (check_entry(key, custom_text(old_strings[key]), slots=old_slots.get(key, ()))
                 if key in old_strings else [])
        identity = lambda item: json.dumps([item["rule"], item["evidence"]["matches"]], ensure_ascii=False)
        previous = {identity(item) for item in prior}
        changed = leaf != old_strings.get(key)
        for item in found:
            blocking = changed or identity(item) not in previous
            results.append({**item, "status": item["state"], "blocking": blocking,
                            "level": "error" if blocking else "warn", "compiled_readback": True})
    return results
