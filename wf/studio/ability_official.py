"""Select effect templates by string role and render type-known arguments only."""
from __future__ import annotations

from html import unescape
import re

PREFIX = "ability_description_"
ELEMENTS = {"AllElement": "全属性", "Red": "火", "Blue": "水", "Yellow": "雷",
            "Green": "风", "White": "光", "Black": "暗"}
ROLES = {
    "precondition": ("precondition_", "during_trigger_kind_", "instant_trigger_kind_"),
    "trigger": ("instant_trigger_kind_",),
    "during_trigger": ("during_trigger_kind_",),
    "instant_content": ("condition_content_", "common_content_", "instant_content_"),
    "during_content": ("common_content_",),
    "opening": ("opening_kind_",),
    "target": ("target_",),
    "instant_puller": ("instant_trigger_puller_", "target_"),
    "during_puller": ("during_trigger_puller_", "target_"),
    "precontent": ("precontent_",),
    "precontent_target": ("target_",),
    "multiply": ("instant_trigger_kind_",),
}
AUXILIARY = {
    "condition_content_initial_accumulation", "condition_content_number",
    "target_separator", "target_separator_or", "target_ally", "target_enemy",
    "target_by_each_trigger_puller",
}


def is_primary(key: str, group: str) -> bool:
    if group in ("element", "character_group"):
        return key.startswith("element_kind_")
    suffix = key.removeprefix(PREFIX)
    return (suffix.startswith(ROLES.get(group, ())) and suffix not in AUXILIARY
            and not suffix.startswith("common_content_fever_point_attack_kind_"))


def key_order(mapping, group, en):
    key = mapping["key"]
    targets = group in ("target", "instant_puller", "during_puller", "precontent_target")
    return (mapping["status"] != "as3", key.endswith("_summary"),
            targets and "constraint" in key,
            targets and "multiball" in key and "Multiball" not in en,
            "member_frozen" in key, "stun_paralysis" in key)


def clean_template(template: str, arguments: dict[str, str] | None = None) -> str | None:
    """Omit optional clauses; keep every unknown required argument as an ellipsis.

    Conditional clauses depend on row data, so neither branch is asserted at
    type level. Required numeric/object slots must not leave broken sentences.
    """
    arguments = arguments or {}
    result, stack, start = [], [], 0
    for token in re.finditer(r"::(.*?)::", template, re.S):
        if all(stack):
            result.append(template[start:token.start()])
        tag = token[1].strip()
        if tag.startswith(("if ", "foreach ")):
            # Retain target clauses with an unknown-object ellipsis. Omitting
            # them can leave connectors such as "敌人对造成的伤害" dangling.
            stack.append(tag in ("if !withoutTarget", "if !omittable"))
        elif tag == "end":
            if stack:
                stack.pop()
        elif tag.startswith(("else", "elseif ")):
            if stack:
                stack[-1] = False
        elif all(stack):
            result.append(arguments.get(tag, "…"))
        start = token.end()
    if all(stack):
        result.append(template[start:])
    text = unescape("".join(result))
    text = re.sub(r"<[^>]*>", "", text)
    text = re.sub(r"\s*…(?:\s*…)*\s*", "…", text)
    text = re.sub(r"\s+", " ", text).strip(" ，,；;：:。/·")
    return text if re.search(r"[\w\u3400-\u9fff]", text) else None


def _arguments(selected, by_key, strings, en, seen=()):
    key = selected["key"]
    if key in seen:
        return {}, {}
    arguments, sources = {}, {}
    template = strings.get(key, "")
    for slot, bindings in selected.get("bindings", {}).items():
        terms, resolved = [], []
        for binding in bindings:
            child_key = binding.get("key")
            child_args, child_sources = _arguments(by_key[child_key], by_key, strings, en, (*seen, key)) if child_key in by_key else ({}, {})
            text = binding.get("text") or clean_template(strings.get(child_key, ""), child_args)
            if text:
                if text not in terms:
                    terms.append(text)
                source = dict(binding)
                if child_sources:
                    source["arguments"] = child_sources
                    source["evidence"] = list(dict.fromkeys([*source.get("evidence", []),
                        *(e for refs in child_sources.values() for ref in refs for e in ref.get("evidence", []))]))
                resolved.append(source)
        if terms:
            arguments[slot] = "／".join(terms)
            sources[slot] = resolved
    for name, text in ELEMENTS.items():
        if en.endswith(name):
            for slot in ("element", "element_short"):
                if f"::{slot}::" in template and slot not in arguments:
                    arguments[slot] = text
                    sources[slot] = [{"text": text, "enumToken": name}]
            break
    return arguments, sources


def render_official(record, group, en, strings):
    candidates = sorted((k for k in record["keys"] if is_primary(k["key"], group)),
                        key=lambda k: key_order(k, group, en))
    keys = {k["key"] for k in candidates}
    # If even the outer template depends on sign, there is no single official
    # type name. Preserve the neutral literal fallback rather than assert one.
    candidates = [k for k in candidates if not
                  (k["key"].endswith(("_buff", "_debuff")) and
                   k["key"].removesuffix("_debuff").removesuffix("_buff") + "_buff" in keys and
                   k["key"].removesuffix("_debuff").removesuffix("_buff") + "_debuff" in keys)]
    by_key = {k["key"]: k for k in record["keys"]}
    for selected in candidates:
        key = selected["key"]
        template = strings.get(key, "")
        arguments, sources = _arguments(selected, by_key, strings, en)
        # Fixed enum attributes are available even when the archived AS3 uses
        # an indirect helper that the conservative reader cannot resolve.
        if key == PREFIX + "target_member_at" and en in ("Second", "Third"):
            arguments["index"] = "2" if en == "Second" else "3"
            sources["index"] = [{"text": arguments["index"], "enumToken": en}]
        if official := clean_template(template, arguments):
            evidence = list(dict.fromkeys([*selected["evidence"],
                *(e for bindings in sources.values() for binding in bindings for e in binding.get("evidence", []))]))
            return {"official": official, "officialKey": key, "officialTemplate": template,
                    "officialArguments": {slot: {"text": text, "sources": sources[slot]}
                                          for slot, text in arguments.items()},
                    "evidence": evidence, "mappingStatus": selected["status"]}
    return {"official": None, "officialKey": None, "officialTemplate": None,
            "officialArguments": {}, "evidence": [], "mappingStatus": "none"}
