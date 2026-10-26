"""Native, bounded Fever growth for Inaho; no client capability changes."""
from copy import deepcopy
import hashlib

import wf_mod_tool as core
from wf_inaho_fever_drain import make_row as drain_row

SEED = 4200
CAP = 1000000000
UNIQUE_ID = "1399952"
STATE = "unique_fox_oracle_autumn_fever_growth_v1"
ICON = "battle/common/unique_condition/" + STATE + ".png"
ICON_SOURCE = "battle/common/unique_condition/unique_fox_oracle_autumn_foxfire.png"
ABILITY = "master/ability/ability.orderedmap"
LEADER = "master/ability/leader_ability.orderedmap"
UNIQUE = "master/character/unique_condition.orderedmap"
OWNERS = {ABILITY: ("1399951", "1399956"), LEADER: ("139995",)}
OLD = {
    "1399951": "d81d7f6d603482c909cbdd6dbb9397619ce72ba7512ec1927d3ded306370ba5d",
    "1399956": "6cc580162c17777d271821620bd9e3eb9763809fc0e0e9d951ecacc9b889af48",
    "139995": "d597d9dd383e048197253ccf161162ab29049b6f31987b2185043ccc3a6c7d0f",
}
NEW = {
    "1399951": "96cb45b23797f0a6b1a01870bcfa13a63d39742fb206cd34ad63792c9d034b03",
    "1399956": "f088b705820ff63c7a3cfa4364df9c609d01b56a402ff9e21185506971ae9b5e",
    "139995": "683327e4ac60c325870fe23a7f7f9783a7ef4b5ee311380387ef33fbba4f978d",
}


def sha(value):
    return hashlib.sha256(value.encode("utf-8") if isinstance(value, str) else value).hexdigest()


def precontent(row, threshold, offset=0):
    """Read, without consumption, floor(self stacks / fixed threshold)."""
    for column in range(39, 46):
        row[column + offset] = ""
    values = {39: "3", 40: "0", 42: str(threshold * 100000),
              43: str(threshold * 100000), 44: str(CAP), 45: UNIQUE_ID}
    for column, value in values.items():
        row[column + offset] = value


def instant(template, kind, trigger=0, precondition=0):
    row = template[:6] + [""] * (len(template) - 6)
    row[1] = "true"
    row[5] = "0"
    row[6], row[13], row[20] = str(precondition), "0", "0"
    row[27], row[39], row[46], row[47] = str(trigger), "(None)", "0", str(kind)
    if trigger:
        row[30:32], row[34:36] = ["100000"] * 2, ["(None)", "0"]
    return row


def counter(template, initial=False):
    row = instant(template, 461, trigger=0 if initial else 184)
    row[48] = "0"  # Self on the fused main/unison Member, never a Ball.
    row[51:53] = ["100000"] * 2
    row[59:61] = ["100000"] * 2  # One Condition object; stacks use magnification.
    row[68], row[74], row[75] = UNIQUE_ID, str(SEED if initial else 1), "0"
    if not initial:
        precontent(row, 4)
    return row


def state_row():
    return [STATE, "余辉", ICON.removesuffix(".png"), "99999999", str(CAP),
            "(None)", "(None)", "(None)", "(None)", "false", "true", "0",
            "0", "false", "(None)"]


def has_state(row, present, offset=0):
    start = 13 + offset
    if row[start:start + 7] != ["0", "", "", "", "", "", ""]:
        raise ValueError("second precondition already in use")
    row[start:start + 7] = ["187" if present else "199", "0", "",
                            "" if present else "0", "" if present else "0", "", UNIQUE_ID]


def transform(texts):
    if set(texts) != set(OLD):
        raise ValueError("expected precisely Inaho ability 1/6 and leader")
    hashes = {key: sha(value) for key, value in texts.items()}
    if NEW and hashes == NEW:
        return dict(texts)
    if hashes != OLD:
        raise ValueError("unknown or partially changed Inaho growth baseline")
    rows = {key: core.read_csv_lines(value) for key, value in texts.items()}
    original = deepcopy(rows)
    first, sixth, leader = rows["1399951"], rows["1399956"], rows["139995"]
    if (len(first), len(sixth), len(leader)) != (3, 2, 10):
        raise ValueError("unexpected ability layout")
    # Ability power levels 1..6 resolve 5,6,7,8,9,10; leader has 2 levels.
    # The initial totals stay 75/150 and 175..350 at all reachable levels.
    for group, index, threshold, offset in ((sixth, 0, 120, 0), (leader, 1, 280, -2)):
        row = group[index]
        if row[47 + offset] != "213":
            raise ValueError("expected existing fixed Fever points")
        fallback = row.copy()
        has_state(fallback, False, offset)
        group.append(fallback)
        has_state(row, True, offset)
        precontent(row, threshold, offset)
        row[51 + offset:53 + offset] = ["500000", "1000000"]
    gain = instant(first[0], 213, trigger=65, precondition=186)
    gain[51:53] = ["500000", "1000000"]
    precontent(gain, 210)
    first.extend((counter(first[0], True), counter(first[0]), gain, drain_row()))
    if first[:3] != original["1399951"] or sixth[1] != original["1399956"][1]:
        raise ValueError("existing unrelated abilities changed")
    result = {key: core.write_csv_lines(value) for key, value in rows.items()}
    if NEW and {key: sha(value) for key, value in result.items()} != NEW:
        raise ValueError("unexpected growth output")
    return result


def simulate(rounds=64):
    result, stacks = [], SEED
    for n in range(rounds + 1):
        row = {"fever_ends": n, "stacks": stacks, "ideal_stacks": SEED * 1.25 ** n,
               "capped": stacks == CAP, "alv_1_to_6": {}}
        for name, threshold in (("leader", 280), ("ability6", 120), ("pf3", 210)):
            actual = [power * (stacks // threshold) for power in range(5, 11)]
            initial = [power * (SEED // threshold) for power in range(5, 11)]
            ideal = [value * 1.25 ** n for value in initial]
            row["alv_1_to_6"][name] = {"actual": actual, "ideal": ideal,
                "relative_error": [a / b - 1 for a, b in zip(actual, ideal)]}
        result.append(row)
        stacks = min(CAP, stacks + stacks // 4)
    return result
