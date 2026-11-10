"""Workspace document (data + policy + lifecycle) and the lossless import from source files."""
from __future__ import annotations

import copy
import datetime as _dt
import json
import re
import uuid
from pathlib import Path

from . import jsonio
from .catalog import load_master
from .layout import CONTENT_ID, MASTER_FILES, RUNTIME_FILES, CorridorConfig

SCHEMA_PATH = Path(__file__).resolve().parents[3] / "schemas" / "rogue-corridor-content.schema.json"
RELIC_ID = re.compile(r"^r(\d{3,6})$")
EVENT_ID = re.compile(r"^e(\d{3,6})$")


def now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def empty_policy() -> dict:
    return {"characters": {}, "weapons": {}, "souls": {}, "relics": {}, "events": {}, "encounters": {},
            "acts": {"1": {}, "2": {}, "3": {}}, "event_option_ids": {},
            "shop": {"item_overrides": {}, "service_overrides": {}}}


def empty_lifecycle() -> dict:
    return {"reserved_relic_ids": [], "reserved_event_ids": [], "reserved_option_ids": [], "tombstones": []}


def new_option_id() -> str:
    return "opt_" + uuid.uuid4().hex


def option_signature(option: dict) -> str:
    return jsonio.canonical({"label": option.get("label"), "effects": option.get("effects"),
                             "requires": option.get("requires")})


def read_sources(cfg: CorridorConfig) -> tuple[dict, dict[str, bytes]]:
    data, raws = {}, {}
    for spec in RUNTIME_FILES:
        path = cfg.source_path(spec)
        if not path.is_file():
            raise FileNotFoundError(f"缺少运行时文件 {spec.name}（{spec.origin}:{spec.source}）")
        raw = path.read_bytes()
        try:
            data[spec.key] = jsonio.parse(raw)
        except ValueError as exc:
            raise ValueError(f"{spec.name} 不是合法 JSON：{exc}") from exc
        raws[spec.name] = raw
    return data, raws


def build_workspace(data: dict, raws: dict[str, bytes], master, previous: dict | None = None,
                    label: str = "source") -> dict:
    """Wrap parsed runtime files as a workspace; keep stable option IDs and lifecycle from ``previous``."""
    rules, pool = data["rules"], data["encounter_pool"]
    try:
        source_event = int(str((pool.get("meta") or {}).get("event_id")))
    except ValueError:
        source_event = 1
    source = {
        "game_data_version": str(((master.tier_table or {}).get("meta") or {}).get("source_version") or "unknown"),
        "tier_table_file": "tier_table.json",
        "tier_table_sha256": master.tier_sha or "0" * 64,
        "soul_catalog_file": "rules_v3_metadata.json",
        "soul_catalog_sha256": master.soul_sha,
        "runtime_files_sha256": {name: jsonio.sha256(raw) for name, raw in raws.items()},
        "runtime_host_event_id": int((rules.get("host") or {}).get("event_id") or 1),
        "encounter_source_event_id": source_event,
        "imported_at": now(),
        "import_label": label,
    }
    policy = copy.deepcopy(previous["policy"]) if previous else empty_policy()
    lifecycle = copy.deepcopy(previous["lifecycle"]) if previous else empty_lifecycle()
    old_ids = (previous or {}).get("policy", {}).get("event_option_ids", {})
    old_events = {e.get("event_id"): e for e in ((previous or {}).get("data", {}).get("events") or [])}
    option_ids = {}
    for ev in data["events"]:
        eid = ev.get("event_id")
        ids = []
        prior = old_events.get(eid)
        prior_ids = old_ids.get(eid) or []
        by_sig = {}
        if prior and len(prior_ids) == len(prior.get("options") or []):
            for opt, oid in zip(prior["options"], prior_ids):
                by_sig.setdefault(option_signature(opt), []).append(oid)
        for opt in ev.get("options") or []:
            matches = by_sig.get(option_signature(opt))
            ids.append(matches.pop(0) if matches else new_option_id())
        option_ids[eid] = ids
    policy["event_option_ids"] = option_ids
    for key, values in (("reserved_relic_ids", [r.get("relic_id") for r in data["relics"]]),
                        ("reserved_event_ids", [e.get("event_id") for e in data["events"]]),
                        ("reserved_option_ids", [i for ids in option_ids.values() for i in ids])):
        seen = set(lifecycle[key])
        lifecycle[key].extend(v for v in values if isinstance(v, str) and v not in seen and not seen.add(v))
    alive = {("relic", r.get("relic_id")) for r in data["relics"]} | {("event", e.get("event_id")) for e in data["events"]}
    lifecycle["tombstones"] = [t for t in lifecycle["tombstones"] if (t["kind"], t["id"]) not in alive]
    return {"document_type": "rogue_content_workspace", "schema_version": 1, "content_id": CONTENT_ID,
            "revision": (previous or {}).get("revision", 0), "source": source, "data": data, "policy": policy,
            "lifecycle": lifecycle}


def import_from_sources(cfg: CorridorConfig, previous: dict | None = None) -> tuple[dict, dict[str, bytes]]:
    data, raws = read_sources(cfg)
    masters = {spec.key: cfg.source_path(spec) for spec in MASTER_FILES}
    master = load_master(masters["tier_table"], masters["soul_catalog"])
    return build_workspace(data, raws, master, previous), raws


# ---------------------------------------------------------------- ids
def next_id(prefix: str, workspace: dict) -> str:
    pattern = RELIC_ID if prefix == "r" else EVENT_ID
    life = workspace["lifecycle"]
    pool = ([r.get("relic_id") for r in workspace["data"]["relics"]] + life["reserved_relic_ids"]) if prefix == "r" else \
        ([e.get("event_id") for e in workspace["data"]["events"]] + life["reserved_event_ids"])
    pool += [t["id"] for t in life["tombstones"] if t["kind"] == ("relic" if prefix == "r" else "event")]
    numbers = [int(m.group(1)) for v in pool if isinstance(v, str) and (m := pattern.match(v))]
    return f"{prefix}{(max(numbers) + 1 if numbers else 1):03d}"


# ---------------------------------------------------------------- locales
def relic_keys(relic_id: str) -> tuple[str, str]:
    return f"rogue.relic.{relic_id}.name", f"rogue.relic.{relic_id}.desc"


def event_keys(event_id: str) -> tuple[str, str]:
    return f"rogue.event.{event_id}.title", f"rogue.event.{event_id}.text"


def option_key(event_id: str, index: int) -> str:
    return f"rogue.event.{event_id}.option.{index}"


def _group(key: str) -> str:
    parts = key.split(".")
    return ".".join(parts[:2]) if len(parts) > 2 else key


def set_locale(locales: dict, lang: str, key: str, text: str) -> None:
    """Update in place, or insert after the last key of the same group (keeps diffs local)."""
    table = locales.setdefault(lang, {})
    if key in table:
        table[key] = text
        return
    group = _group(key)
    items = list(table.items())
    at = max((i for i, (k, _) in enumerate(items) if _group(k) == group), default=len(items) - 1)
    items.insert(at + 1, (key, text))
    table.clear()
    table.update(items)


def remove_locale_keys(locales: dict, predicate) -> dict:
    removed = {}
    for lang in ("zh", "en"):
        table = locales.get(lang) or {}
        for key in [k for k in table if predicate(k)]:
            removed.setdefault(key, {})[lang] = table.pop(key)
    return removed


def replace_option_keys(locales: dict, event_id: str, texts: list[dict]) -> None:
    """Re-emit ``rogue.event.<id>.option.N`` in index order at the block's original position."""
    prefix = f"rogue.event.{event_id}.option."
    for lang in ("zh", "en"):
        table = locales.setdefault(lang, {})
        items = list(table.items())
        positions = [i for i, (k, _) in enumerate(items) if k.startswith(prefix)]
        rest = [(k, v) for k, v in items if not k.startswith(prefix)]
        block = [(option_key(event_id, i), t.get(lang, "")) for i, t in enumerate(texts)]
        if positions:
            at = positions[0]
        else:
            group = [i for i, (k, _) in enumerate(rest) if k.startswith(f"rogue.event.{event_id}.")]
            at = (group[-1] + 1) if group else len(rest)
        rest[at:at] = block
        table.clear()
        table.update(rest)


def dump(workspace: dict) -> bytes:
    return json.dumps(workspace, ensure_ascii=False, indent=1).encode("utf-8") + b"\n"
