"""Data-only replacement for an unsupported Unique precontent description."""
from copy import deepcopy
import hashlib
import zlib

import wf_dsl
import wf_mod_tool as core
from wf_client_legality import (
    action_dsl_element_problems, action_dsl_hit_area_target_problems,
    action_dsl_subject_binding_problems, client_legality_problems,
)
from wf_dsl_sig import COMMANDS

KEY = "ability_fox_oracle_autumn_fever_growth"
PROGRAM = f"battle/action/skill/action/ability_skill/{KEY}${KEY}"
DSL = PROGRAM + ".action.dsl.amf3.deflate"
ABILITY = "master/ability/ability.orderedmap"
LEADER = "master/ability/leader_ability.orderedmap"
OWNERS = {ABILITY: ("1399951", "1399956"), LEADER: ("139995",)}
STATE = 1399952
CAP = 1000000000
OLD = {
    "1399951": "96cb45b23797f0a6b1a01870bcfa13a63d39742fb206cd34ad63792c9d034b03",
    "1399956": "f088b705820ff63c7a3cfa4364df9c609d01b56a402ff9e21185506971ae9b5e",
    "139995": "683327e4ac60c325870fe23a7f7f9783a7ef4b5ee311380387ef33fbba4f978d",
}
NEW = {
    "1399951": "4423475dbcbd6f7ca7d6640b25927c7b916b327c4452dbb4b7272af25e432896",
    "1399956": "a209647cde5e14a714e07fba899ebb6414e30a415cc6235d072ce67dca10ff3c",
    "139995": "7fc9cdbc4258ff70449ce46412e35c2f64957ddf4d34d7291fbb9da085b228f9",
}


def sha(raw):
    return hashlib.sha256(raw.encode() if isinstance(raw, str) else raw).hexdigest()


def transform(texts):
    hashes = {key: sha(text) for key, text in texts.items()}
    if NEW and hashes == NEW:
        return dict(texts)
    if hashes != OLD:
        raise ValueError("unknown or partially changed Inaho detail baseline")
    rows = {key: core.read_csv_lines(text) for key, text in texts.items()}
    before = deepcopy(rows)
    row = rows["1399951"][4]
    if (row[1], row[27], row[39], row[47], row[68]) != ("true", "184", "3", "461", str(STATE)):
        raise ValueError("expected the original unisonable FeverEnd growth row")
    row[39:46] = ["(None)"] + [""] * 6
    row[47:85] = [""] * 38
    row[47], row[70], row[71] = "629", KEY, PROGRAM
    # These limits cannot constrain reachable S, and their displayed maxima fit int32.
    for key, index, column, divisor in (("1399951", 5, 44, 210),
                                       ("1399956", 0, 44, 120), ("139995", 1, 42, 280)):
        rows[key][index][column] = str(CAP // divisor)
    allowed = {"1399951": {(4, c) for c in range(39, 85) if c != 46} | {(5, 44)},
               "1399956": {(0, 44)}, "139995": {(1, 42)}}
    for key in rows:
        assert len(rows[key]) == len(before[key])
        for index, (old, new) in enumerate(zip(before[key], rows[key])):
            assert len(new) == len(old)
            changed = {(index, c) for c, (a, b) in enumerate(zip(old, new)) if a != b}
            if not changed <= allowed[key]:
                raise ValueError("a cell outside the exact fix scope changed")
            problems = client_legality_problems("leader_ability" if key == "139995" else "ability", new)
            if problems:
                raise ValueError("; ".join(problems))
    result = {key: core.write_csv_lines(group) for key, group in rows.items()}
    if NEW and {key: sha(text) for key, text in result.items()} != NEW:
        raise ValueError("unexpected fixed row output")
    return result


def asset():
    # The scalar term is resolved by native resolveSLvValueInt -> floor(S/4).
    bind = ["Command", ["BindConditionAccumulationVariable", -17, STATE,
                         ["DCUnique", STATE], 4, CAP]]
    create = ["Command", ["CreateCondition", -17,
                           [["ACUnique", STATE, [{"min": 1, "max": 1}]]],
                           [{"min": 1, "max": 1}], ["None"], False, False, "", None,
                           False, 1, [{"min": 1, "max": 1, "mul": STATE}], True]]
    expr = ["Command", ["ConditionalsConditionExist", -17, ["DCUnique", STATE],
                        ["Block", [bind, create]], ["Block", []]]]
    tree = ["ActionDsl", 1, ["None"], *([False] * 7), 3, ["Block", [expr]]]
    for command in wf_dsl.iter_dsl_commands(tree):
        if len(command) != len(COMMANDS[command[0]]) + 1:
            raise ValueError("invalid native DSL signature")
    problems = (action_dsl_element_problems(tree, character_element=3)
                + action_dsl_subject_binding_problems(tree)
                + action_dsl_hit_area_target_problems(tree))
    if problems:
        raise ValueError("; ".join(problems))
    encoder = zlib.compressobj(level=9, wbits=-15)
    payload = encoder.compress(wf_dsl.encode_amf3(tree)) + encoder.flush()
    if wf_dsl.parse_dsl(zlib.decompress(payload, -15))["tree"] != tree:
        raise ValueError("DSL AMF3 roundtrip failed")
    return payload, tree
