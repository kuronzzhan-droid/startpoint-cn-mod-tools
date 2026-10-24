#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Small strict-JSON reader shared by immutable release contracts."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, TypeVar


ErrorT = TypeVar("ErrorT", bound=Exception)


def _object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key {key!r}")
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise ValueError(f"non-JSON constant {value}")


def load_json_strict(
    path: Path, error_factory: Callable[[str], ErrorT], label: str
) -> object:
    try:
        raw = Path(path).read_bytes()
    except OSError as error:
        raise error_factory(f"cannot load {label} {path}: {error}") from error
    return parse_json_strict(raw, error_factory, f"{label} {path}")


def parse_json_strict(
    raw: bytes, error_factory: Callable[[str], ErrorT], label: str
) -> object:
    try:
        return json.loads(
            raw.decode("utf-8"), object_pairs_hook=_object,
            parse_constant=_constant,
        )
    except (UnicodeDecodeError, ValueError) as error:
        raise error_factory(f"cannot parse {label}: {error}") from error
