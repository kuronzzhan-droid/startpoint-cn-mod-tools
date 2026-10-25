"""PF-triggered soul damage rows, with explicit optional InvokeSkill evidence."""
from __future__ import annotations

import math
import zlib

import wf_describe
import wf_dsl
from wf.view.base149 import join
from .weapon_rules import CUSTOM, check_ability_rows

TEMPLATES = {
    "pf_hit_ability_damage": (183, False), "pf_use_ability_damage": (2, False),
    "pf_hit_invoke_damage": (183, True), "pf_use_invoke_damage": (2, True),
}
INVOKE_CAPABILITIES = {"official.kind629.invoke_skill@1", "client.kind424.damage_convert@1"}


def _number(spec, name, default=None, *, integer=False, minimum=0, maximum=2147483647):
    value = spec.get(name, default)
    if (isinstance(value, bool) or not isinstance(value, int if integer else (int, float))
            or not math.isfinite(value) or not minimum <= value <= maximum):
        raise ValueError(f"soul_template {name} must be {'an integer' if integer else 'a number'} in {minimum}..{maximum}")
    return value


def _invoke_evidence(state):
    from wf.caps.profiles import read_client, resolve_client
    provides = getattr(state, "client_provides", None)
    profile = getattr(state, "client_profile", None)
    if provides is None and profile is None:
        raise ValueError("629 template requires explicit target provides or client_profile")
    path, _ = resolve_client(provides=provides, client_profile=profile)
    document = read_client(path)
    available = {entry["id"] for entry in document["provides"]}
    missing = INVOKE_CAPABILITIES - available
    if missing:
        raise ValueError("629 template target provides lacks " + ", ".join(sorted(missing)))
    damage = next(entry for entry in document["provides"] if entry["id"] == "client.kind424.damage_convert@1")
    if 20 not in damage.get("patches", []) or not any(
            entry["number"] == 20 and entry["status"] == "recorded" for entry in document.get("patches", [])):
        raise ValueError("629 template requires recorded patch 20 in target provides")


def _attack_tree(multiplier, element, effect):
    # Reuse the proven hit-area shape, never the cursed-weapon constants/IDs.
    from wf.tools.weapon.cursed_weapons import _full_screen_attack
    tree = _full_screen_attack(multiplier, buff_target_as=2)
    def replace(node):
        if not isinstance(node, list):
            return
        if node and node[0] == "Command" and node[1][0] == "CreateNormalAttack":
            node[1][2], node[1][15] = element, [effect]
        for child in node:
            replace(child)
    replace(tree)
    return tree


def template_row(spec):
    """Native rows do not use DSL; power units are attack multipliers ×100000."""
    name = spec.get("template")
    if name not in TEMPLATES:
        raise ValueError("unknown soul damage template")
    trigger, invoke = TEMPLATES[name]
    element = _number(spec, "element", integer=True, maximum=5)
    power = _number(spec, "multiplier", minimum=0.00001, maximum=21474)
    maximum = _number(spec, "max_multiplier", power, minimum=power, maximum=21474)
    cooldown = _number(spec, "cooldown_frames", 0, integer=True)
    limit = spec.get("trigger_limit")
    if limit is not None:
        limit = _number(spec, "trigger_limit", integer=True, minimum=1)
    target = spec.get("damage_target", "trigger_enemy" if trigger == 183 else "all_enemies")
    if target not in {"trigger_enemy", "all_enemies", "nearest_enemy"}:
        raise ValueError("unknown soul damage_target")
    if trigger == 2 and target == "trigger_enemy":
        raise ValueError("PF activation has no trigger enemy; use all_enemies or nearest_enemy")
    row = [""] * 123
    for column, value in {0: 0, 1: 1, 2: 0, 3: 0, 10: 0, 17: 0, 24: trigger,
                          27: 100000, 28: 100000, 31: "(None)" if limit is None else limit,
                          32: cooldown, 36: "(None)", 43: 0}.items():
        row[column] = str(value)
    if invoke:
        if maximum != power:
            raise ValueError("629 template has a fixed DSL multiplier; max_multiplier must equal multiplier")
        if "damage_target" in spec and target != "all_enemies":
            raise ValueError("629 damage template targets all_enemies")
        dsl_element = _number(spec, "dsl_element", integer=True, minimum=1, maximum=6)
        if dsl_element != element + 1:
            raise ValueError("dsl_element must equal internal element + 1")
        if spec.get("hit_effect") not in ("Explosion", "None"):
            raise ValueError("629 hit_effect must explicitly be Explosion or None (C10013 guard)")
        row[44] = "629"
    else:
        if any(key in spec for key in ("dsl_element", "hit_effect")):
            raise ValueError("native soul damage does not use DSL element/effect parameters")
        row[44] = str({"all_enemies": 251, "trigger_enemy": 316, "nearest_enemy": 352}[target] + element)
        row[45], row[48], row[49], row[66] = "0", str(round(power * 100000)), str(round(maximum * 100000)), "(None)"
    return row


def apply_template(state, spec, code):
    row = template_row(spec)
    if row[44] == "629":
        _invoke_evidence(state)
        if state.raw(CUSTOM) is None:
            raise ValueError("629 template requires the complete custom_ability_string baseline")
        # These are soul-table native columns, not ability c70/c71.
        layout = wf_describe.layout("ability_soul")
        if layout["ncols"] != 123 or layout["blocks"]["instant_content"] != 44:
            raise ValueError("ability_soul c67/c68 layout changed")
        string_id = code + "_pf_damage"
        action = "battle/action/skill/action/ability_skill/studio_weapon/" + code + "_pf_damage"
        row[67], row[68] = string_id, action
        tree = _attack_tree(spec["multiplier"], spec["dsl_element"], spec["hit_effect"])
        encoder = zlib.compressobj(9, zlib.DEFLATED, -15)
        payload = encoder.compress(wf_dsl.encode_amf3(tree)) + encoder.flush()
        state.set_raw(action + ".action.dsl.amf3.deflate", payload, new=True)
        state.set_leaf(CUSTOM, [string_id], "强化弹射追击", new=True)
    text = join(row)
    check_ability_rows("ability_soul", text, client_profile=getattr(state, "client_profile", None),
                       provides=getattr(state, "client_provides", None))
    return text
