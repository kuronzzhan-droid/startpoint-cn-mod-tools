"""小Boss原生行构造：按已逆向字段布局生成，禁止未声明参数。"""
from copy import deepcopy

import wf_describe as describe
from wf_client_legality import client_legality_problems

NONE = "(None)"


def _block(row, block, value, fields):
    schema = describe.enum_map()
    offsets = {name: int(offset) for offset, name, _ in schema["block_fields"][block]}
    base = int(describe.layout("ability")["blocks"]["precondition1" if block == "precondition" else block])
    case = schema["cases"][block][str(value)]
    declared = case["fields"]
    for field in fields:
        if field.split(".")[0] not in declared:
            raise ValueError(f"{block}:{value} does not declare {field}")
    row[base] = str(value)
    defaults = {"target": 0, "trigger_puller": 0, "initial_multiply": 1,
                "multiply_trigger": 0, "by_each_trigger_puller": "false",
                "trigger_limit": NONE, "cooltime": 0, "max_accumulation": "1",
                "cancelable": 0, "flip_limit": NONE, "power_flip_limit": NONE,
                "end_power_flip_limit": NONE, "end_power_flip_accepted_levels": NONE}
    values = {k: v for k, v in defaults.items() if k in declared}
    values.update(fields)
    for field, number in values.items():
        row[base + offsets[field]] = str(number)


def scaled(field, value, scale=100_000):
    n = str(round(value * scale))
    return {field + ".power1": n, field + ".first_max": n}


def condition(kind, **fields):
    return kind, fields


def event(kind=0, *, every=1, limit=None, ct=0, puller=0, group=None, held_seconds=None):
    if not kind:
        return 0, {}
    fields = {**scaled("threshold", every), "trigger_limit": NONE if limit is None else limit,
              "cooltime": round(ct * 60)}
    declared = describe.enum_map()["cases"]["instant_trigger"][str(kind)]["fields"]
    if held_seconds is not None:
        if "threshold2" not in declared:
            raise ValueError("trigger does not accept held-condition frames")
        fields.update(scaled("threshold2", held_seconds * 60))
    if "trigger_puller" in declared:
        fields["trigger_puller"] = puller
        if group:
            fields["trigger_puller.character_groups"] = group
    return kind, fields


def ongoing(kind, *, count=1, limit=None, uid=None, puller=0, group=None):
    fields = {}
    declared = describe.enum_map()["cases"]["during_trigger"][str(kind)]["fields"]
    if "threshold" in declared:
        fields.update(scaled("threshold", count))
    if "trigger_limit" in declared:
        fields["trigger_limit"] = NONE if limit is None else limit
    if "trigger_puller" in declared:
        fields["trigger_puller"] = puller
        if group:
            fields["trigger_puller.character_groups"] = group
    elif group:
        fields["character_groups"] = group
    if uid is not None:
        fields["unique_condition_id"] = uid
    return kind, fields


def make(content, percent=None, *, group=None, target=0, trigger=None, during=None,
         pre=(), extra=None, duration=None, stacks=1):
    row = [""] * 126
    row[:6] = ["miniboss", "true", "special", "0", "", "1" if during else "0"]
    for index in range(3):
        kind, fields = pre[index] if index < len(pre) else (0, {})
        # The three precondition blocks share the same field layout.
        temp = [""] * 126
        _block(temp, "precondition", kind, fields)
        row[6 + index * 7:13 + index * 7] = temp[6:13]
    block = "during_content" if during else "instant_content"
    fields = dict(extra or {})
    declared = describe.enum_map()["cases"][block][str(content)]["fields"]
    if "target" in declared:
        fields["target"] = target
        if target in (1, 5, 6):
            fields["target.character_groups"] = group or NONE
    if percent is not None:
        fields.update(scaled("strength", percent, 1000))
    if duration is not None:
        fields.update(scaled("frame", duration * 60))
    if "number" in declared:
        fields.update(scaled("number", 1))
    if "max_accumulation" in declared:
        fields["max_accumulation"] = stacks
    if during:
        row[85] = NONE
        row[108] = "false"
        _block(row, "during_trigger", *during)
    else:
        row[39] = NONE
        row[46] = "0"
        _block(row, "instant_trigger", *(trigger or event()))
    _block(row, block, content, fields)
    problems = client_legality_problems("ability", row)
    if problems:
        raise ValueError(problems)
    return row


class Kit:
    def __init__(self, code, group, uid, layers):
        self.code, self.group, self.uid, self.layers = code, group, uid, layers

    def i(self, kind, percent=None, **kwargs):
        return make(kind, percent, group=self.group, **kwargs)

    def team(self, kind, percent=None, **kwargs):
        return self.i(kind, percent, target=5, **kwargs)

    def d(self, kind, percent, when=None, *, target=5, **kwargs):
        return self.i(kind, percent, target=target,
                      during=when or ongoing(134, uid=self.uid, limit=self.layers), **kwargs)

    def gain(self, n=1, **kwargs):
        return self.i(461, n * 100, extra={"unique_condition_id": self.uid}, **kwargs)

    def has(self, count):
        return [(144, {"trigger_puller": 0, "unique_condition_id": self.uid,
                       **scaled("threshold", count)})]

    def helper(self, suffix, **kwargs):
        return self.i(629, extra={"string_id": "ability_skill_" + self.code + "_" + suffix,
                      "action_path": "battle/action/skill/action/rare5/" + self.code + "$" + self.code + "_" + suffix}, **kwargs)

    def finish(self, slots, leader):
        result = {}
        for slot, rows in enumerate(slots, 1):
            for row in rows:
                row[0] = f"{self.code}_{slot}"
                row[1] = "false" if slot == 3 else "true"
                row[2] = "action_skill" if slot == 3 else "attack_" + self.group.lower()
            result[slot] = rows
        leader = [[self.code, "0", "", *deepcopy(row[5:])] for row in leader]
        return result, leader
