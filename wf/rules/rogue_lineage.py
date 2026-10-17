"""Read-only identity and terrain gates recovered from the B rogue builder."""
from __future__ import annotations

import wf_rogue_bundle as rbb


def standard_funnel_boss_references(table, decode_row, esdl_loader):
    """Find exact Boss IDs in Standard Funnel damage-share and watch links."""
    seen = set()
    result = set()

    def visit(node):
        if isinstance(node, dict):
            for value in node.values():
                visit(value)
            return
        row = decode_row(node)
        if not row or not row[0]:
            raise ValueError("empty Standard Funnel resource row")
        logical = row[0].removesuffix(".esdl.amf3.deflate") + ".esdl.amf3.deflate"
        if logical in seen:
            return
        seen.add(logical)
        tree = esdl_loader(logical)
        if not isinstance(tree, dict):
            raise ValueError("Standard Funnel ESDL must be an object")
        target = tree.get("bG")
        if target:
            if not isinstance(target, str):
                raise ValueError("dynamic damage-share target")
            result.add(("damage_share", target))
        for form in tree.get("au", []):
            for watch in form.get("h", []):
                key = watch.get("a")
                if isinstance(key, list) and key and key[0] in ("T1", "T3"):
                    if len(key) != 3 or not isinstance(key[2], str):
                        raise ValueError("malformed Boss watch key")
                    result.add(("enemy_watch_partner", key[2]))

    visit(table)
    return result


def native_bundle_field_index(catalog):
    """Index only post-gate source fields; reject ambiguous bundle evidence."""
    if catalog is None:
        return {}
    eligible = set(catalog.eligible_source_fields)
    out = {}
    for bundles in catalog.discovered_bundles.values():
        for bundle in bundles:
            field = str(bundle.source_field)
            if field not in eligible:
                continue
            if field in out and out[field] != bundle:
                raise RuntimeError(f"场地存在多个不一致的原生 bundle:{field}")
            out[field] = bundle
    return out


def checked_mix_terrain_compatibility(source_field, target_field, bundles_by_field,
                                     *, strict_transplant, transplant_safe):
    """Require source action closure and target terrain evidence before mixing."""
    source_field, target_field = str(source_field), str(target_field)
    source = bundles_by_field.get(source_field)
    target = bundles_by_field.get(target_field)
    if source is None or target is None:
        missing = [label + "=" + field for label, field, bundle in (
            ("source", source_field, source), ("target", target_field, target))
            if bundle is None]
        return rbb.CompatibilityResult(False, "BUNDLE_EVIDENCE_MISSING",
                                       ",".join(missing), source_field, target_field)
    if not source.portable or source.terrain_requirements is None:
        return rbb.CompatibilityResult(
            False, source.native_only_reason or "ACTION_CLOSURE_UNAUDITED",
            "Boss 来源缺可移植 ActionDSL/ESDL 闭包证明", source_field, target_field)
    return rbb.terrain_compatibility(
        source, target, source.terrain_requirements,
        strict_transplant=bool(strict_transplant), transplant_safe=transplant_safe)
