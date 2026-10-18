"""Typed v35 configuration markers and their optional ownership references."""
import re

CUSTOM_PREFIXES = ("wfx_snapcombo_", "wfx_pf4_", "wfx_unlock_", "wfx_adaptive_",
                   "ability_visual_", "wfx_fever_voice_", "equipment_rule_")
STRINGS = "master/string/custom_ability_string.orderedmap"


def unique_signals(value, uid=None):
    yield "unique_string", value
    parts = value.split(":")
    # Icon hiding deliberately does not validate the numeric fields, matching
    # the two final v35e HUD methods rather than the effect evaluator.
    if value.startswith("wfx:") and len(parts) >= 6 and parts[5].startswith("hidden_"):
        yield "selectors", "wfx.hidden_unique_icons"
    if value.startswith("fever:items:") and (
            (len(parts) > 3 and re.fullmatch(r"lv\d+", parts[3]))
            or (uid is not None and str(uid) not in {str(n) for n in range(1299901, 1299910)})):
        yield "selectors", "fever.items.v2"
    problem = wfx_problem(value)
    if problem:
        yield "unsupported", problem


def wfx_problem(value):
    import wf_wfx
    import wfx_registry
    kind = wf_wfx.classify_sid(value)
    if kind is None:
        return None
    if kind != "effect":
        return f"未支持或写错的 WFX 标记：{value}"
    try:
        spec = wf_wfx.decode_sid(value)
    except wf_wfx.WfxError as exc:
        return str(exc)
    catalog = wfx_registry.capabilities()
    unavailable = [name for name in wf_wfx.required_capabilities(spec)
                   if catalog[name]["status"] == "planned"]
    return f"WFX 能力尚无客户端实现：{', '.join(unavailable)}" if unavailable else None


def custom_signals(key):
    for prefix in CUSTOM_PREFIXES:
        if key.startswith(prefix):
            yield "selectors", "custom_ability_string." + prefix


def character_signals(cid, row):
    if len(row) > 5:
        for tag in row[5].split(","):
            if tag.startswith("ModDualForm:"):
                yield "selectors", "character_tag.ModDualForm"
    for key in ("wfx_pf4_" + str(cid), "ability_visual_" + row[0], "wfx_fever_voice_" + row[0]):
        yield "optional_ref", (STRINGS, key)
    if len(row) > 17 and row[17] not in {"", "0", "(None)"}:
        yield "optional_ref", (STRINGS, "wfx_unlock_" + row[17])
    for ability in row[19:25]:
        if ability not in {"", "0", "(None)"}:
            yield "optional_ref", (STRINGS, "wfx_adaptive_" + ability)
