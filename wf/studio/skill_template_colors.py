"""Prefer the requested colour; report an explicit official-donor fallback."""
from .skill_template_core import _resolved_effect
from .skill_template_validation import walk
from wf.rules.catalog import result


def choose_effect_colors(prepared, tiers, inputs, donor_context, target_context):
    def available(effect):
        return any(inputs.read(effect + suffix, official=True) is not None
                   for suffix in (".parts.amf3.deflate", ".frame.amf3.deflate"))

    checks = []
    for tier in tiers:
        originals = dict(walk(tier["tree"]))
        for pointer, node in walk(prepared[tier["level"]]["tree"]):
            if not isinstance(node, list) or node[:1] != ["ResolveByElement"]:
                continue
            target = _resolved_effect(node, target_context)
            if available(target):
                continue
            try:
                original = _resolved_effect(originals[pointer], donor_context)
            except ValueError:
                continue  # Missing source context remains a missing-asset error.
            if original != target and available(original):
                node[:] = ["SpecifyEffectDirectly", original]
                checks.append(result("skill-template.effect-color", "待验证",
                    "目标分色缺失，保留官方母本分色，可用 recolor 调整：" + original))
    return checks
