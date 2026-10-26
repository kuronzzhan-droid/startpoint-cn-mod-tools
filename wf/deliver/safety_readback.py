"""Cross-check the optional studio safety contract against its detail reports."""
from __future__ import annotations

import json

from wf.rules.catalog import STATES

SUMMARY_RULES = ("studio.bundle-keys", "studio.key-diff")
KEY_LISTS = ("added", "changed", "removed", "foreign", "unknown", "owned")


def _document(local_read, name):
    try:
        value = json.loads(local_read(name)[1])
    except (OSError, ValueError) as error:
        raise ValueError(f"invalid or missing safety detail {name}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"safety detail {name} must be an object")
    return value


def _objects(value, label):
    if not isinstance(value, list) or any(not isinstance(entry, dict) for entry in value):
        raise ValueError(f"{label} must be an array of objects")
    return value


def _strings(value, label):
    if not isinstance(value, list) or any(not isinstance(key, str) for key in value):
        raise ValueError(f"{label} must be an array of strings")
    return value


def _check(entry, label):
    if (not isinstance(entry.get("rule"), str) or not entry["rule"]
            or entry.get("status") not in STATES or type(entry.get("blocking")) is not bool
            or entry.get("state", entry["status"]) != entry["status"]
            or (entry["status"] == "问题") != entry["blocking"]
            or (entry.get("level") == "error" and not entry["blocking"])):
        raise ValueError(f"invalid {label} status or blocking result")


def _bundle(document):
    status = document.get("status")
    apks = _objects(document.get("apks"), "bundle-check apks")
    tables = _objects(document.get("tables"), "bundle-check tables")
    collision_lists = [_strings(table.get("collisions"), "bundle-check collisions") for table in tables]
    collisions = any(collision_lists)
    if not isinstance(status, str) or status not in {"ok", "collision", "skipped", "error"}:
        raise ValueError("invalid bundle-check status")
    if status in {"ok", "collision"} and (not apks or collisions != (status == "collision")):
        raise ValueError("bundle-check status contradicts APK or collision evidence")
    if status in {"skipped", "error"} and (
            not isinstance(document.get("reason"), str) or not document["reason"]):
        raise ValueError("bundle-check skipped/error requires a reason")
    if status == "skipped" and (apks or tables or not document["reason"]):
        raise ValueError("bundle-check skipped contradicts selected APK evidence")
    blocked = status in {"collision", "error"}
    return ("问题" if blocked else "未执行" if status == "skipped" else "满足",
            blocked, "error" if blocked else "warn" if status == "skipped" else "info")


def _key_diff(document):
    totals = dict.fromkeys(KEY_LISTS, 0)
    for table in _objects(document.get("tables"), "key-diff tables"):
        counts = table.get("counts")
        if not isinstance(counts, dict) or table.get("truncated") is not False:
            raise ValueError("key-diff requires full table counts and key lists")
        for field in KEY_LISTS:
            keys = _strings(table.get(field), f"key-diff {field}")
            if type(counts.get(field)) is not int or counts[field] != len(keys):
                raise ValueError(f"key-diff {field} count contradicts keys")
            totals[field] += len(keys)
    counts = document.get("counts")
    if not isinstance(counts, dict) or any(type(counts.get(key)) is not int or counts[key] != total
                                           for key, total in totals.items()):
        raise ValueError("key-diff total counts contradict table evidence")
    warnings = _strings(document.get("warnings"), "key-diff warnings")
    blocked = bool(totals["removed"])
    warning = bool(totals["foreign"] or totals["unknown"])
    status = "blocked" if blocked else "warning" if warning else "ok"
    if (document.get("status") != status or document.get("ok") is not (not blocked)
            or document.get("blocking") is not blocked or bool(warnings) != warning):
        raise ValueError("key-diff status contradicts removed/foreign/unknown evidence")
    return "问题" if blocked else "待验证" if warning else "满足", blocked, "error" if blocked else "warn" if warning else "info"


def validate_safety_checks(entries, local_read):
    """Require both summaries and exact extension findings; old drafts are separate."""
    entries = _objects(entries, "safety_checks")
    for entry in entries:
        _check(entry, "safety_checks entry")
    summaries = {}
    for rule in SUMMARY_RULES:
        matches = [entry for entry in entries if entry["rule"] == rule]
        if len(matches) != 1:
            raise ValueError(f"safety_checks requires exactly one {rule}")
        summaries[rule] = matches[0]
    expected = (_bundle(_document(local_read, "bundle-check.json")),
                _key_diff(_document(local_read, "key-diff.json")))
    for rule, (status, blocking, level) in zip(SUMMARY_RULES, expected):
        entry = summaries[rule]
        if (entry["status"], entry["blocking"], entry.get("level")) != (status, blocking, level):
            raise ValueError(f"safety_checks {rule} contradicts its detail report")
    extensions = _document(local_read, "client-extensions.json")
    findings = _objects(extensions.get("checks"), "client-extensions checks")
    for entry in findings:
        _check(entry, "client-extensions check")
        if entry["rule"] in SUMMARY_RULES:
            raise ValueError("client-extensions must not replace safety summary rules")
    status = "error" if any(entry["blocking"] for entry in findings) else "warning" if findings else "ok"
    if extensions.get("status") != status:
        raise ValueError("client-extensions status contradicts its checks")
    if [entry for entry in entries if entry["rule"] not in SUMMARY_RULES] != findings:
        raise ValueError("safety_checks extension findings contradict client-extensions detail")
