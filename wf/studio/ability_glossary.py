"""Read-only, per-view enum vocabulary sourced from the client's ui_string."""
from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
import threading
from weakref import WeakKeyDictionary

import wf_describe
import wf_quest_lib as codec

from .ability_vocabulary import GROUPS, enum_groups, field_rules, strength_count_kinds
from .ability_official import clean_template, render_official

UI_STRING = "master/string/ui_string.orderedmap"
_cache = WeakKeyDictionary()
_lock = threading.RLock()


@lru_cache(maxsize=1)
def official_map():
    path = Path(__file__).resolve().parents[2] / "ability_official_map.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _ui_strings(source):
    if hasattr(source, "table"):
        rows = source.table(UI_STRING)
        return {k: v[0][0] for k, v in rows.items() if v and v[0] and isinstance(v[0][0], str)}
    try:
        raw, _ = getattr(source, "view", source).read_raw(UI_STRING)
    except (KeyError, FileNotFoundError):
        return {}
    if raw is None:
        return {}
    # CLI views expose compressed CSV leaves rather than StudioSource.table().
    import wf_mod_tool as binary
    return {key: rows[0][0] for key, leaf in codec.parse_node(raw).items()
            if (rows := binary.read_csv_lines(leaf)) and rows[0]}


def build_glossary(source):
    strings = _ui_strings(source)
    mapping = official_map()["groups"]
    counts = wf_describe.enum_map()["usage_counts"]
    groups = {}
    for group, values in enum_groups().items():
        entries = []
        label, _, _, use_groups = GROUPS[group]
        for value, names in values.items():
            official = render_official(mapping[group][value], group, names["en"], strings)
            uses = sum(table.get(value, 0) for name in use_groups for table in counts.get(name, {}).values())
            entries.append({"value": value, **names, **official, "uses": uses})
        groups[group] = {"label": label, "values": sorted(entries, key=lambda e: (not e["value"].isdigit(),
                                      int(e["value"]) if e["value"].isdigit() else e["value"]))}
    return {"groups": groups, "fields": field_rules(), "strengthCountKinds": strength_count_kinds(),
            "formats": {
                "percent": {"divisor": 1000, "unit": "%"},
                "strength": {"divisor": 1000, "unit": "%", "countDivisor": 100000},
                "scaled_frames": {"divisor": 100000, "unit": "帧", "fps": 60},
                "scaled_count": {"divisor": 100000, "unit": "次"},
                "frames": {"divisor": 1, "unit": "帧", "fps": 60},
                "seconds": {"divisor": 1, "unit": "秒"},
                "count": {"divisor": 1, "unit": "次"},
                "threshold": {"divisor": 1000, "unit": "%", "countDivisor": 100000,
                              "note": "与描述器一致：正整数十万倍按次/层/个，其余按千分比；具体量纲取决于类型"},
            }, "note": "官方词来自当前视图 ui_string；直译是工具译名。名称推测不等于 AS3 证实。使用次数来自 ability_enum_map 快照，未统计的小枚举为 0。"}


def glossary(source):
    """StudioSource/view instances are immutable snapshots; never cache by version alone."""
    with _lock:
        if source not in _cache:
            _cache[source] = build_glossary(source)
        return _cache[source]
