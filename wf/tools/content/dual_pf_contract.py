"""Native leader PF references for the two September character revisions."""
from __future__ import annotations

import zlib

import wf_mod_tool as core

POWER_FLIP_MASTER = "master/skill/power_flip_action.orderedmap"
DUAL_PF_KEYS = {
    (129992, "unicorn_lancer_rose"): "override_unicorn_lancer_rose_dual_pf",
    (139995, "fox_oracle_autumn"): "override_fox_oracle_autumn_dual_pf",
}
DUAL_PF_PROGRAMS = {
    identity: tuple(
        f"battle/action/power_flip/action/override/{key}${key}_lv{level}"
        for level in range(1, 4)
    )
    for identity, key in DUAL_PF_KEYS.items()
}
_EFFECT = "battle/effect/powerflip/"
DUAL_PF_EFFECTS = {
    program: frozenset({
        f"{_EFFECT}effect_powerflip_attack_spin/powerflip_attack_spin_{word}",
        f"{_EFFECT}effect_powerflip_attack_support/powerflip_enhancing_support_{'one' if level == 1 else 'two'}",
        *({f"{_EFFECT}effect_powerflip_attack_support/powerflip_attack_support_three"}
          if level == 3 else set()),
    })
    for level, (word, program) in enumerate(zip(
        ("one", "two", "three"), DUAL_PF_PROGRAMS[(129992, "unicorn_lancer_rose")]
    ), 1)
}
for level, (word, program) in enumerate(zip(
    ("one", "two", "three"), DUAL_PF_PROGRAMS[(139995, "fox_oracle_autumn")]
), 1):
    beam_suffixes = ("",) if level == 1 else ("_small", "_medium")
    if level == 3:
        beam_suffixes += ("_large",)
    private_effect = _EFFECT + "fox_oracle_autumn_native/"
    DUAL_PF_EFFECTS[program] = frozenset({
        f"{private_effect}effect_powerflip_attack_special/powerflip_attack_special_{word}",
        f"{private_effect}effect_powerflip_attack_special/powerflip_attack_special_player_{word}",
        *(f"{private_effect}effect_powerflip_attack_beam/powerflip_attack_beam_{word}{suffix}"
          for suffix in beam_suffixes),
    })


def bind_native_programs(identity, leader_rows, evidence, bind_common, error):
    """Require a real I722 leader override and its three exact native programs."""
    key = DUAL_PF_KEYS.get(identity)
    if key is None:
        return ()
    locations = tuple(
        (index, column)
        for index, row in enumerate(leader_rows)
        for column, value in enumerate(row)
        if value == key
    )
    if locations != ((8, 80),) or leader_rows[8][45] != "722":
        raise error(f"native dual-PF leader override mismatch: {identity[1]}")
    bind_common(POWER_FLIP_MASTER)
    raw = evidence.ordered(POWER_FLIP_MASTER).get(key)
    if raw is None:
        raise error(f"native dual-PF master key missing: {key}")
    try:
        rows = core.read_csv_lines(zlib.decompress(raw).decode("utf-8"))
    except Exception as exc:
        raise error(f"native dual-PF row is unreadable: {key}: {exc}") from exc
    expected = DUAL_PF_PROGRAMS[identity]
    if len(rows) != 1 or tuple(rows[0]) != expected:
        raise error(f"native dual-PF three-level program closure mismatch: {key}")
    return expected
