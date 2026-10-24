"""Per-effect WFX parameter semantics recorded by the v35 build contracts."""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json


def flags_rule(registry, code):
    return registry.get("effect_flags_overrides", {}).get(str(code))


def uses_pin(registry, code):
    rule = flags_rule(registry, code)
    return rule is None or rule.get("pin", True)


def integer_problems(value, rule, name):
    if type(value) is not int:
        return [f"{name}={value!r} 须为整数"]
    low, high = rule.get("min", 0), rule.get("max", 2147483647)
    if not low <= value <= high:
        return [f"{name}={value} 须在 {low}–{high} 范围内"]
    return []


def effect_arg_problems(effect, arg):
    """Return None for legacy mask arguments handled by the original codec."""
    rule = effect.get("arg_schema")
    if isinstance(rule, dict):
        choices = {int(key) for key in rule if str(key).isdigit()}
        if choices:
            return [] if type(arg) is int and arg in choices else [f"arg={arg} 须为 {sorted(choices)}"]
        return integer_problems(arg, rule, "arg")
    if effect["arg"] == "S状态uid":
        return integer_problems(arg, {}, "arg")
    if effect["arg"] == "保留，写0":
        return integer_problems(arg, {"max": 0}, "arg")
    return None


def hidden_icon_capability(registry, sid):
    """Match the display filter independently of numeric WFX validity."""
    rule = registry.get("unique_icon_visibility", {})
    if not rule or not isinstance(sid, str) or not sid.startswith(rule["wfx_prefix"]):
        return None
    segments = sid.split(":")
    index = rule["label_segment_one_based"] - 1
    if len(segments) > index and segments[index].startswith(rule["hidden_label_prefix"]):
        return rule["capability"]
    return None


def candidate_profile_problems(entry, names, catalog):
    """Local candidates require the exact integrated SWF and recorded APK pair."""
    problems = []
    evidence = entry.get("evidence", {})
    if not isinstance(evidence, dict):
        evidence = {}
    local_ids = None
    for name in names:
        capability = catalog[name]
        if capability["status"] == "shipped":
            continue
        if capability["status"] != "local_candidate":
            problems.append(f"客户端不可声明（status={capability['status']}）的 capability: {name}")
            continue
        expected = capability.get("integration_evidence", {})
        apks = expected.get("apk_sha256", {})
        if (expected.get("status") != "local_offline_verified"
                or not expected.get("swf_sha256")
                or evidence.get("swf_sha256") != expected["swf_sha256"]
                or not isinstance(apks, dict)
                or evidence.get("apk_sha256") not in apks.values()):
            if local_ids is None:
                local_ids = _registered_local_capabilities(entry)
            if capability.get("capability_id") in local_ids:
                continue
            problems.append(f"本地候选能力 {name} 缺少匹配的 SWF/APK 离线证据")
    return problems


def _registered_local_capabilities(entry):
    """Bridge reviewed local method evidence without trusting claimed capability names."""
    from pathlib import Path
    from wf.apk.local_registry import find
    from wf.caps.profiles import read_client
    from wf.paths import REPOSITORY

    evidence = entry.get("evidence", {})
    record = find(evidence.get("swf_sha256"), apk_sha256=evidence.get("apk_sha256"))
    if record is None or evidence.get("apk_sha256") != record["source"]["sha256"]:
        return set()
    filename = entry.get("provides")
    if not filename:
        return set()
    path = Path(filename)
    if not path.is_absolute():
        path = REPOSITORY / path
    try:
        supplied = read_client(path, profile=entry)
        verified = _verified_local_ids(json.dumps(record, sort_keys=True), _evidence_token(REPOSITORY))
    except (OSError, ValueError):
        return set()
    return {row["id"] for row in supplied["provides"]} & verified


def _evidence_token(root):
    """Rehash every trusted input; cache only the expensive pure derivation."""
    files = sorted((root / "wf/caps").glob("*.yml"))
    files += [root / name for name in ("wf/apk/data/v34-evidence.json",
              "wf/apk/data/v35e-evidence.json", "wf/apk/data/v35e-method-contexts.json",
              "schemas/capability.schema.json")]
    digest = hashlib.sha256()
    for path in files:
        digest.update(str(path.relative_to(root)).encode())
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


@lru_cache(maxsize=8)
def _verified_local_ids(serialized, evidence_token):
    from wf.apk.register_local import provides_for
    return frozenset(row["id"] for row in provides_for(json.loads(serialized))["provides"])
