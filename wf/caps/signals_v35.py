"""Typed v35 configuration markers and their optional ownership references."""
import re

CUSTOM_PREFIXES = ("wfx_snapcombo_", "wfx_pf4_", "wfx_unlock_", "wfx_adaptive_",
                   "ability_visual_", "wfx_fever_voice_", "equipment_rule_", "awakening_material_",
                   "wfx_summon_flip_pf_", "wfx_ball_pf_action_")
STRINGS = "master/string/custom_ability_string.orderedmap"


def unique_signals(value, uid=None):
    # p12/p13's dedicated handlers have their own report-based capability.
    # Do not substitute the earlier v35 effect-query/hidden-icon method hashes.
    if value.startswith(("wfx:41:", "wfx:42:")):
        yield "selectors", "unique_condition." + ":".join(value.split(":")[:2])
        problem = wfx_problem(value)
        if problem:
            yield "unsupported", problem
        return
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
                   if catalog[name]["status"] in {"planned", "withdrawn"}]
    if unavailable:
        return f"WFX 能力尚无客户端实现或已撤回：{', '.join(unavailable)}"
    return catalog_gap(wf_wfx.required_capabilities(spec))


def catalog_gap(names):
    """Shipping facts do not manufacture method evidence for the M2 catalog."""
    import wfx_registry
    catalog = wfx_registry.capabilities()
    missing = [name for name in names if not catalog[name].get("capability_id")]
    return f"TODO：已登记WFX能力尚缺客户端方法证据目录：{', '.join(missing)}" if missing else None


def custom_signals(key, value=None):
    for prefix in CUSTOM_PREFIXES:
        if key.startswith(prefix):
            yield "selectors", "custom_ability_string." + prefix
    if key.startswith("awakening_material_"):
        import wfx_registry
        rule = wfx_registry.load()["string_keys"]["awakening_material_"]
        gap = catalog_gap(wfx_registry.capability_closure([rule["capability"]]))
        if gap:
            yield "unsupported", gap
    if value is not None:
        if key.startswith(("wfx_summon_flip_pf_", "wfx_ball_pf_action_")):
            import csv
            from .p13 import decode_config_row
            try:
                value = decode_config_row(value)
            except (ValueError, csv.Error) as error:
                yield "unsupported", str(error)
                return
        yield from configuration_signals("custom_ability_string", key, value)
        if key.startswith("wfx_ball_pf_action_"):
            from .p13 import config_problems
            if not config_problems(key, value):
                yield "ref", ("master/skill/power_flip_action.orderedmap", value)


def configuration_signals(table, key, value):
    from wf.wfx_config import configuration_checks
    names, problems, _warnings = configuration_checks(table, key, value)
    gap = catalog_gap(names)
    for problem in [*problems, *([gap] if gap else [])]:
        yield "unsupported", problem


def character_signals(cid, row):
    from wf.wfx_tags import tag_tokens
    if len(row) > 5:
        for tag in tag_tokens(row[5]):
            yield from configuration_signals("character_tag", tag, None)
            if tag.startswith("ModDualForm:"):
                yield "selectors", "character_tag.ModDualForm"
    for key in ("wfx_pf4_" + str(cid), "ability_visual_" + row[0], "wfx_fever_voice_" + row[0]):
        yield "optional_ref", (STRINGS, key)
    if len(row) > 17 and row[17] not in {"", "0", "(None)"}:
        yield "optional_ref", (STRINGS, "wfx_unlock_" + row[17])
    for ability in row[19:25]:
        if ability not in {"", "0", "(None)"}:
            yield "optional_ref", (STRINGS, "wfx_adaptive_" + ability)
