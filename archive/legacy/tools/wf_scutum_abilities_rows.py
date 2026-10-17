"""盾牌座原生表行构造；列号采用 AbilityValues 的 126 列布局。"""
from copy import deepcopy

SCALE = 100_000
CODE = "scutum_valentine"
CID = "149988"
COLLECT_UID = 14998801
COLLECT_HIT_UID = 14998802
COLLECT_ICON = "battle/common/unique_condition/scutum_valentine_collect"
CHANGE_STRING = "change_skill_scutum_valentine"
HELPER_PREFIX = "battle/action/skill/action/ability_skill/scutum_valentine$"
DASH_STRING = "scutum_valentine_retaliation"
CHASE_STRING = "scutum_valentine_piercing_chase"
COLLECT_CHASE_STRING = "scutum_valentine_collect_chase"


def put(row, values):
    for index, value in values.items():
        row[index] = str(value)
    return row


def pre(row, kind, offset=6):
    row[offset:offset + 7] = ["0", "", "", "", "", "", ""]
    if kind == "wind_resonance":
        put(row, {offset: 2, offset + 3: 600000, offset + 4: 600000,
                  offset + 5: "Green"})
    elif kind == "self_wind":
        put(row, {offset: 3, offset + 5: "Green"})
    elif kind in ("flying", "piercing"):
        row[offset] = "39" if kind == "flying" else "38"
    elif kind == "barrier":
        put(row, {offset: 87, offset + 1: 0})
    elif kind == "collect":
        put(row, {offset: 187, offset + 1: 0, offset + 6: COLLECT_UID})
    elif kind is not None:
        raise ValueError(f"unknown Scutum precondition: {kind}")
    return row


def base(source, *, during=False, gates=()):
    donor = source["1511473"][0 if during else -1]
    if len(donor) != 126:
        raise ValueError("expected official 126-column ability source")
    row = deepcopy(donor)
    row[6:] = [""] * 120
    row[:6] = [CODE, "true", "attack_green", "0", "", "1" if during else "0"]
    for index in range(3):
        pre(row, gates[index] if index < len(gates) else None, 6 + index * 7)
    if len(gates) > 3:
        raise ValueError("native preconditions have only three slots")
    if during:
        put(row, {85: "(None)", 108: "false"})
    else:
        put(row, {27: 0, 39: "(None)", 46: 0})
    return row


def instant(source, content, strength=None, *, target=None, group="Green",
            gates=(), trigger=0, threshold=1, threshold2=None,
            puller=None, puller_group=None, limit=None, cooldown=0):
    row = base(source, gates=gates)
    put(row, {27: trigger, 47: content})
    if trigger:
        put(row, {30: threshold * SCALE, 31: threshold * SCALE,
                  34: "(None)" if limit is None else limit, 35: cooldown})
    if threshold2 is not None:
        put(row, {32: threshold2 * SCALE, 33: threshold2 * SCALE})
    if puller is not None:
        row[28] = str(puller)
    if puller_group is not None:
        row[29] = puller_group
    if target is not None:
        row[48] = str(target)
        if target in (1, 5, 6, 8, 14):
            row[49] = group
    if strength is not None:
        row[51:53] = [str(strength)] * 2
    return row


def during(source, content, strength, *, condition, target=5, group="Green", gates=()):
    row = base(source, during=True, gates=gates)
    put(row, {97: condition, 109: content, 110: target,
              113: strength, 114: strength})
    if target in (1, 5, 6, 8, 14):
        row[111] = group
    if condition == 72:
        row[98] = "0"
    return row


def timed(row, frames, *, maximum=None, strength=None):
    put(row, {57: frames * SCALE, 58: frames * SCALE,
              59: SCALE, 60: SCALE, 61: "(None)" if maximum is None else maximum,
              62: "(None)", 63: "(None)", 64: "(None)", 65: "(None)",
              67: 0, 72: "false", 74: 1, 75: 0})
    if strength is not None:
        row[51:53] = [str(strength)] * 2
    return row


def helper(source, string_id, **kwargs):
    row = instant(source, 629, **kwargs)
    return put(row, {70: string_id, 71: HELPER_PREFIX + string_id})
