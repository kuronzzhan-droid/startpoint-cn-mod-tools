"""Validated quest selectors and reversible, filesystem-safe draft identities."""
from __future__ import annotations

import re

PATTERN = r"(?:[0-9]{1,9}|boss_battle:[0-9]{1,9}(?:/[0-9]{1,9}/[0-9]{1,9})?|hard_multi:[0-9]{1,9}(?:/[0-9]{1,9})?|practice:[0-9]{1,9})"
_SELECTOR = re.compile(PATTERN)


def safe_id(selector: str) -> str:
    if not isinstance(selector, str) or not _SELECTOR.fullmatch(selector):
        raise ValueError(f"副本 ID 无效：{selector!r}")
    return selector.replace(":", "_").replace("/", "_")


def from_directory(name: str) -> str:
    for kind in ("boss_battle", "hard_multi", "practice"):
        prefix = kind + "_"
        if name.startswith(prefix):
            selector = kind + ":" + name[len(prefix):].replace("_", "/")
            break
    else:
        selector = name
    if safe_id(selector) != name:
        raise ValueError("boss draft directory identity mismatch")
    return selector
