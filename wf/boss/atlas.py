"""Collect a conservative, explicitly incomplete encounter sheet lower bound."""
from __future__ import annotations

from wf.rules.boss_common import CandidateView
from wf.rules.boss_preload import DslEvidence, walk

PREFIXES = ("battle/boss/", "battle/zako/", "battle/funnel/", "battle/effect/",
            "battle/field/", "battle/field_object/", "battle/uncommon/layer0/")


def _sheet(value):
    if value == "battle/common/layer0":
        return value + ".png"
    if value.startswith("character/") and "/pixelart/" in value:
        parent, name = value.rsplit("/", 1)
        return parent + ("/special_sprite_sheet.png" if name == "special" else "/sprite_sheet.png")
    if value.startswith(PREFIXES):
        if value.endswith(".png"):
            return value
        parent = value.rsplit("/", 1)[0]
        return parent + "/" + parent.rsplit("/", 1)[-1] + ".png"
    return None


def encounter_budget(view, document, *, source_quest=None, supplied=None):
    """Read actual candidate PNGs, without claiming a complete enemy closure.

    Animation -> sheet mapping follows AssetPathCollectionBuilder. Direct enemy,
    field and zone references plus action DSL references are a lower bound only;
    special enemy factories, summons and party dependencies remain unproven.
    Caller-supplied sheets augment this bound and cannot remove it.
    """
    source, values, roots = CandidateView(view), [], []
    active = {str(wave.get("name")) for wave in document.get("terrain", {}).get("waves", [])}
    for enemy in document.get("enemies", []):
        if enemy.get("mode") == "single" or str(enemy.get("wave")) not in active:
            continue
        for index, value in enumerate(enemy.get("row", [])):
            if index == 25 and enemy.get("table", "").endswith("/general_boss.orderedmap"):
                continue  # Timeline markers are not sprite sheets.
            values.append(value)
    values.extend(document.get("field", {}).get("row", []))
    for zone in document.get("zone", {}).get("rows", []):
        if str(zone.get("path", [""])[-1]) in active:
            values.extend(zone.get("row", [])[35:])
    animations = {"battle/common/layer0"}

    def collect(value):
        if not isinstance(value, str):
            return
        for part in value.split(","):
            part = part.strip()
            if part.startswith("battle/action/"):
                roots.append(part)
            elif part.startswith(("battle/", "character/")):
                animations.add(part)
                # Field/zone values can be folders rather than animation leaves.
                if part.startswith(("battle/field/", "battle/field_object/")):
                    animations.add(part + "/_")

    for value in values:
        collect(value)
    evidence = DslEvidence(view)
    for tree in evidence.closure(roots).values():
        for value in walk(tree):
            collect(value)
    candidates = {_sheet(value) for value in animations} - {None}
    sheets = sorted(logical for logical in candidates if source.raw(logical) is not None)
    given = supplied or {}
    return {"parties": given.get("parties", [[], [], []]),
            "enemy_sheets": sorted(set(sheets) | set(given.get("enemy_sheets", []))),
            "source_quest": source_quest or document.get("quest", {}).get("selector"),
            "enemy_lower_bound": True,
            "unresolved_programs": sorted(evidence.missing),
            "limitations": ["敌方仅计可解析直接资源与动作引用；特殊敌人、召唤和属性变体闭包未完整证明"]}
