"""Record proven template -> env.push slot -> stringifier argument chains."""
import re


def merge_binding(target, binding):
    identity = tuple(binding.get(k) for k in ("key", "text", "element"))
    existing = next((b for b in target if tuple(b.get(k) for k in ("key", "text", "element")) == identity), None)
    if existing is None:
        target.append(dict(binding))
    else:
        existing["evidence"] = list(dict.fromkeys([*existing["evidence"], *binding["evidence"]]))


def record_binding(recipes, key, lines, index, helper, values, child_keys, chain, path):
    if recipes is None or not key:
        return
    # These helpers supply type-known nouns. Other helpers supply row data.
    condition = helper in ("stringfyConditionTarget", "stringfyCondtionTargetDuring", "stringfyConditionShareTarget")
    element = helper in ("stringfyElementTarget", "stringfyElementTargetShort")
    if not (condition or element):
        return
    # In this decompiler dialect the helper is assigned to a value closure,
    # immediately followed by its env.push wrapper. Stop at the next template.
    inline = re.search(r'"(\w+)":\s*AbilityDescriptionTools\.' + helper, lines[index][1])
    slot = inline[1] if inline else None
    push_line = lines[index][0]
    for number, text, _ in ([] if inline else lines[index + 1:index + 13]):
        if ".env.get(" in text:
            break
        match = re.search(r'\.env.push\("(\w+)",', text)
        if match:
            slot, push_line = match[1], number
            break
    if slot is None:
        return
    evidence = [*chain, f"{path}:{lines[index][0]}", f"{path}:{push_line}"]
    bindings = []
    if element and values and type(values[0]) is int and 0 <= values[0] <= 6:
        bindings = [{"text": ("全属性", "火", "水", "雷", "风", "光", "暗")[values[0]],
                     "element": values[0], "evidence": evidence}]
    if condition:
        bindings = [{"key": noun, "evidence": list(dict.fromkeys([*evidence, *source]))}
                    for noun, source in child_keys.items() if "condition_target_" in noun]
    if bindings:
        target = recipes.setdefault(key, {}).setdefault(slot, [])
        for binding in bindings:
            merge_binding(target, binding)
