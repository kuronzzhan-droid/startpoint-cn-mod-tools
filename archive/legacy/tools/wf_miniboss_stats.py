"""按定位重设Lv100基础面板，统一使用官方111001的四断点成长比例。"""
from fractions import Fraction

import wf_mod_tool as core

CURVE_DONOR = "111001"
TARGETS = {
    "129998": (3800, 900), "139996": (4300, 860), "129996": (4700, 710),
    "149994": (3800, 960), "159999": (4800, 760), "129995": (4800, 780),
    "149993": (4700, 730), "119995": (3900, 900), "149992": (4200, 850),
    "129994": (4100, 760), "119993": (3900, 830), "129993": (4400, 850),
    "169993": (3600, 980), "149991": (4500, 940), "119994": (4000, 900),
}


def status_row(cid, official_status):
    table = core.read_orderedmap_raw_rows_from_bytes(official_status)
    donor = core.decode_status_row(table.rows[table.keys.index(CURVE_DONOR)])
    if [level for level, _, _ in donor] != ["1", "10", "80", "100"]:
        raise ValueError("official growth donor breakpoint drift")
    baseline_hp, baseline_atk = donor[-1][1:]
    hp, atk = TARGETS[str(cid)]
    scaled = [(level, round(Fraction(value_hp * hp, baseline_hp)),
               round(Fraction(value_atk * atk, baseline_atk)))
              for level, value_hp, value_atk in donor]
    if scaled[-1][1:] != (hp, atk):
        raise AssertionError("Lv100 target drift")
    return core.encode_status_row(scaled)


def metadata(cid):
    hp, atk = TARGETS[str(cid)]
    return {"level_100_hp": hp, "level_100_attack": atk,
            "official_growth_donor": CURVE_DONOR, "breakpoints": [1, 10, 80, 100],
            "damage_bonus_budget_offset": 0,
            "policy": "new role-based base stats; never offset six-ability damage bonuses"}
