"""Combine the exact V9 knight/supporter trees without duplicating PF lifecycle."""
from __future__ import annotations

import copy
import hashlib
import zlib

import wf_dsl

SUFFIX = ".action.dsl.amf3.deflate"
SOURCE_HASHES = {
    "knight_lv1": "792edbe5e401654cd6ba2733c1ae55739ab330bb6f6da09f4f2212b72dc5abd8",
    "knight_lv2": "7d54c04e0bee6f47a8f4403e8cc31fda296cbceb4705c5317a6e11fa6b8bf439",
    "knight_lv3": "7e2b90947e9302feeebfad44bbf6fb60aaf862242f86b3cde6925f017cbfb150",
    "supporter_lv1": "810c651c45d59324d435ec335d4071b779d6dc1ef2f80545eb9a6a98ae622a1b",
    "supporter_lv2": "a12e7b71ce3036a80d85550623665180caaf96a2c0ca30d48f6d4669a13dc4a5",
    "supporter_lv3": "ea73c6a5d745b582fc6419b49dd7ceaca0b2919ea7612a4224f9bb676bd61fff",
}
SPIN = "battle/effect/powerflip/effect_powerflip_attack_spin/"
SUPPORT = "battle/effect/powerflip/effect_powerflip_attack_support/"
EFFECTS = {
    1: (SPIN + "powerflip_attack_spin_one", SUPPORT + "powerflip_enhancing_support_one"),
    2: (SPIN + "powerflip_attack_spin_two", SUPPORT + "powerflip_enhancing_support_two"),
    3: (SPIN + "powerflip_attack_spin_three", SUPPORT + "powerflip_enhancing_support_two",
        SUPPORT + "powerflip_attack_support_three"),
}
# Integer subject slots only: preserve radii, search flags, durations and damage.
SUBJECT_SLOTS = {"FindAllSubjects": (1,), "ShowEffect": (3,), "CreateCondition": (1,),
                 "CreateNormalAttack": (1,), "CreateHitArea": (2, 19, 21, 22)}


def _donor(node: list) -> None:
    if not isinstance(node, list) or not node:
        return
    if node[0] == "Block":
        kept = []
        for entry in node[1]:
            if entry[0] == "Command" and entry[1][0] == "NotifyPowerflipEnd":
                continue
            _donor(entry)
            if entry[0] == "Event" and entry[1][0] == "Wait" and not entry[1][3][1]:
                continue
            kept.append(entry)
        node[1] = kept
        return
    if node[0] in ("Command", "Event"):
        command = node[1]
        for index in SUBJECT_SLOTS.get(command[0], ()):
            if command[index] >= 0:
                command[index] += 200
        if command[0] == "ShowEffect":
            command[1] += "_support"
    for child in node:
        if isinstance(child, list):
            _donor(child)


def compose(knight: bytes, supporter: bytes, level: int) -> list:
    if level not in (1, 2, 3):
        raise ValueError("PF level must be 1, 2 or 3")
    trees = []
    for kind, raw in (("knight", knight), ("supporter", supporter)):
        if hashlib.sha256(raw).hexdigest() != SOURCE_HASHES[f"{kind}_lv{level}"]:
            raise ValueError(f"official {kind} level {level} input fingerprint drift")
        trees.append(wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"])
    base, donor = copy.deepcopy(trees)
    _donor(donor[11])
    base[11][1].extend(donor[11][1])
    if wf_dsl.parse_dsl(wf_dsl.encode_amf3(base))["tree"] != base:
        raise ValueError("combined PF AMF3 round-trip mismatch")
    return base


def encode(tree: list) -> bytes:
    encoder = zlib.compressobj(level=9, wbits=-15)
    return encoder.compress(wf_dsl.encode_amf3(tree)) + encoder.flush()
