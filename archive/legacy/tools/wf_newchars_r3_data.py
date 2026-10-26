"""Known-input R3 balance changes, independent of package I/O and manifests."""
from copy import deepcopy
import hashlib
import json

import wf_dsl
import wf_mod_tool as core

GERALD_HASHES = (
    "09047a7935954c6b7845fad7b355f5ca07bc6a9d0480d2d6941aac1ad6919eb7",
    "1207e9deee2b68820e5fd3e5a48afbe1cbb957ccd4d12b2f056c818646f0861a")
LEADER_HASHES = (
    "ab55a4cddbaea1f5bca222111c64ff1d73e1fdf17e9a2298fe3c8b7207fb23ee",
    "d597d9dd383e048197253ccf161162ab29049b6f31987b2185043ccc3a6c7d0f")
TREE_HASHES = {
    1: ("f86b2cfa64fcf7471f0a3050bbeff18ce1976dfdec1e658ddbd8257ffe2b00aa",
        "8cf49531a37e4cefa305b706600b8a796aeb7761d258065e0031d97e935d96e1"),
    2: ("8cba8ed44c20888ff599c3e8c0664fdffdded2e8a62b07de9f4d6c94eeab24e6",
        "bf2eed4245d58df7a7e256d3732ec473fd7151ac46203f4d101f20f2260049bb"),
    3: ("1b0a673b5ab99208e3edc8badedda008dfedbb3935b12e0d1270570a68d09ffd",
        "e059cad7ac5071ff97701754b107f6b4cfaef79e677784b8061dfceca683c035"),
}


def sha(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode()).hexdigest()


def tree_hash(tree):
    return sha(json.dumps(tree, ensure_ascii=True, sort_keys=True, separators=(",", ":")))


def _already_done(digest, hashes):
    if digest not in hashes:
        raise ValueError("unrecognized published R2 or completed R3 input")
    return digest == hashes[1]


def gerald_ability6(text):
    if _already_done(sha(text), GERALD_HASHES):
        return text
    rows = core.read_csv_lines(text)
    row = rows[0]
    # Keep native MemberDirectAttack and Leader conditions; remove the old
    # all-enemy Unique payload and cooldown. The second row stays untouched.
    row[35], row[47], row[51], row[52], row[68] = "0", "226", "500000", "500000", ""
    result = core.write_csv_lines(rows)
    if sha(result) != GERALD_HASHES[1]:
        raise ValueError("unexpected Gerald output")
    return result


def inaho_leader(text):
    if _already_done(sha(text), LEADER_HASHES):
        return text
    rows = core.read_csv_lines(text)
    # Native I200 is the Lv3-only combo-count reduction. Its signed strength
    # is subtracted by ComboCalculatorImpl.getPowerFlipNumComboChargeLv3.
    # Thus -9 increases Lv3 by 9 and stacks additively with existing reductions.
    # ui_string's count_down template explicitly renders negative values as +N.
    row = [""] * 124
    fields = {0: "fox_oracle_autumn", 1: "0", 3: "0", 4: "0", 11: "0", 18: "0",
              25: "0", 37: "(None)", 44: "0", 45: "200", 49: "-900000", 50: "-900000"}
    for column, value in fields.items():
        row[column] = value
    result = core.write_csv_lines(rows + [row])
    if sha(result) != LEADER_HASHES[1]:
        raise ValueError("unexpected Inaho leader output")
    return result


def inaho_power_flip(source, level):
    if level not in TREE_HASHES:
        raise ValueError("only the three private native PF levels are supported")
    if _already_done(tree_hash(source), TREE_HASHES[level]):
        return deepcopy(source)
    tree = deepcopy(source)
    special = tree[11][1][3]
    if special[:1] != ["Command"] or special[1][0] != "ConditionalsFeverMode":
        raise ValueError("native special branch boundary drift")
    # Every mutually exclusive special collision branch is modified. The root
    # player aura, ranged donor, lifecycle and additional-hit counts stay exact.
    areas = list(wf_dsl.iter_dsl_commands(special, "CreateHitArea"))
    effects = list(wf_dsl.iter_dsl_commands(special, "ShowEffect"))
    attacks = list(wf_dsl.iter_dsl_commands(special, "CreateNormalAttack"))
    if (len(areas), len(effects), len(attacks)) != (8, 4, 8):
        raise ValueError("unexpected native special branch counts")
    for area in areas:
        if area[9][0] != "Circle":
            raise ValueError("non-spherical attack in special branch")
        for term in area[9][1]:
            for endpoint in ("min", "max"):
                term[endpoint] = term[endpoint] * 1.25 / 1.6
    for effect in effects:
        if "effect_powerflip_attack_special/powerflip_attack_special_" not in effect[2][1]:
            raise ValueError("unexpected effect in special branch")
        for term in effect[12][1]:
            for endpoint in ("min", "max"):
                term[endpoint] = term[endpoint] * 1.25 / 1.6
    for attack in attacks:
        for term in attack[6]:
            for endpoint in ("min", "max"):
                term[endpoint] *= 0.75
    if tree_hash(tree) != TREE_HASHES[level][1]:
        raise ValueError("unexpected native special output")
    if wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"] != tree:
        raise ValueError("native PF AMF3 roundtrip failed")
    return tree
