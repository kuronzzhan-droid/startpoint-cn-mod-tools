"""Shared matching for declared data surfaces, separate from SWF support."""
from wf.dsl.references import ABILITY_TABLES as DSL_ABILITY_TABLES

# Capability inspection covers all five SWF parsers. Keep this extension local
# to that inspection: historical DSL recipes pin their original four tables.
ABILITY_TABLES = {**DSL_ABILITY_TABLES, "master/ex_boost/ex_ability.orderedmap": "ex_ability"}


def kind_bindings(surface):
    """Explicit (block, kind) identities; numeric indexes never imply a block."""
    return [(entry["block"], str(entry["kind"])) for entry in surface.get("kind_bindings", [])]


def matches_kind(surface, site):
    return (site["table"] in surface.get("allowed_tables", [])
            and (site["block"], str(site["kind"])) in kind_bindings(surface))


def matches_signal(surface, signal, value):
    if signal == "kind_site":
        return matches_kind(surface, value)
    if signal == "unique_string":
        return any(str(value).startswith(prefix) for prefix in surface.get("unique_prefixes", []))
    # A bare `kinds` signal is a catalog search, not a concrete row or proof
    # that any table/block supports that number.
    return str(value) in {str(item) for item in surface.get(signal, [])}
