"""Per-effect WFX parameter semantics recorded by the v35 build contracts."""
from __future__ import annotations


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
    for name in names:
        capability = catalog[name]
        if capability["status"] == "shipped":
            continue
        if capability["status"] != "local_candidate":
            problems.append(f"尚无客户端实现（status=planned）的 capability: {name}")
            continue
        expected = capability.get("integration_evidence", {})
        apks = expected.get("apk_sha256", {})
        if (expected.get("status") != "local_offline_verified"
                or not expected.get("swf_sha256")
                or evidence.get("swf_sha256") != expected["swf_sha256"]
                or not isinstance(apks, dict)
                or evidence.get("apk_sha256") not in apks.values()):
            problems.append(f"本地候选能力 {name} 缺少匹配的 SWF/APK 离线证据")
    return problems
