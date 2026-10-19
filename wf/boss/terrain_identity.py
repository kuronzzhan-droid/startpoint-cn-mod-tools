"""Allocate terrain generations without overwriting a previously delivered copy."""
from __future__ import annotations

from itertools import count

import wf_quest_lib as codec

from . import schema as s
from .edit_state import leaf
from .identity import safe_id


def _available_row(state, logical, identity):
    if leaf(state.table(logical), (identity,)) is None:
        return True
    original = state.original.get(logical)
    if original is not None and leaf(codec.parse_node(original), (identity,)) is not None:
        return False
    return any(change["table"] == logical and change["path"] == [identity]
               and change["old"] is None for change in state.changes)


def terrain_identity(state, selector, current_path):
    """Reuse this draft's generation; skip every occupied baseline generation.

    Reserve field/zone IDs together even before an append needs them, so later
    operations in the same draft keep one deterministic resource generation.
    """
    stem = safe_id(selector)
    for sequence in count(1):
        suffix = "" if sequence == 1 else f"_v{sequence}"
        identity = "studio_terrain_" + stem + suffix
        target = f"battle/terrain/studio/{stem}{suffix}.amf3.deflate"
        existing = state.raw(target)
        if existing is not None and (target != current_path or state.original.get(target) is not None):
            continue
        if all(_available_row(state, logical, identity) for logical in (s.FIELD_DATA, s.FIELD, s.ZONE)):
            return identity, target
