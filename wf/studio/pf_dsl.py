"""Small, bounded edits to native PF trees; never rebuild their lifecycle."""
from __future__ import annotations

import copy
import math
import re

from wf.rules.dsl_signature import validate_action_dsl
from .drafts import DraftError

ELEMENTS = ("火", "水", "雷", "风", "光", "暗")
EFFECT = re.compile(r"^battle/effect/[A-Za-z0-9_/-]+$")


def nodes(value, name=None):
    if isinstance(value, list):
        if value and isinstance(value[0], str) and (name is None or value[0] == name):
            yield value
        for child in value:
            yield from nodes(child, name)
    elif isinstance(value, dict):
        for child in value.values():
            yield from nodes(child, name)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _terms(attack):
    if len(attack) < 7 or not isinstance(attack[6], list):
        raise DraftError("PF 命中项缺少倍率数组")
    for term in attack[6]:
        if not isinstance(term, dict) or not all(finite(term.get(k)) for k in ("min", "max")):
            raise DraftError("PF 命中项倍率必须包含有限的 min/max")
    return attack[6]


def effects_map(effects):
    result = {}
    for old, new in effects.items():
        old, new = old.rstrip("/"), new.rstrip("/")
        if (not EFFECT.fullmatch(old) or not EFFECT.fullmatch(new)
                or any(p in {"", ".", ".."} for p in (old + "/" + new).split("/"))):
            raise DraftError("特效族必须是安全的 battle/effect 相对目录")
        if not new.startswith("battle/effect/skill_unique/") or old == new:
            raise DraftError("替换目标必须是不同的 skill_unique 私有特效族")
        if old in result or any(old.startswith(k + "/") or k.startswith(old + "/") for k in result):
            raise DraftError("特效族映射不能重复或相互包含")
        result[old] = new
    return result


def remap(value, mapping, *, prefixes=False, matched=None):
    if isinstance(value, str):
        for old, new in mapping.items():
            if value == old or (prefixes and value.startswith(old + "/")):
                if matched is not None:
                    matched.add(old)
                return new + value[len(old):]
        return value
    if isinstance(value, list):
        return [remap(v, mapping, prefixes=prefixes, matched=matched) for v in value]
    if isinstance(value, dict):
        return {k: remap(v, mapping, prefixes=prefixes, matched=matched) for k, v in value.items()}
    return value


def transform(tree, element, scale, effects=None, matched=None):
    if element not in ELEMENTS or not finite(scale) or scale <= 0:
        raise DraftError("属性须为六属性名称，倍率须为有限正数")
    validate_action_dsl(tree)
    changed = copy.deepcopy(tree)
    # Ratio/fixed attacks use different numerical semantics. Refuse them rather
    # than silently leave unscaled damage in a purported complete clone.
    if any(list(nodes(tree, name)) for name in ("CreateRatioAttack", "CreateFixedAttack")):
        raise DraftError("该 PF 含比例或固定伤害，尚不支持按攻击倍率克隆")
    for attack in nodes(changed, "CreateNormalAttack"):
        attack[2] = ELEMENTS.index(element) + 1
        for term in _terms(attack):
            for bound in ("min", "max"):
                term[bound] *= scale
                if not finite(term[bound]):
                    raise DraftError("PF 缩放后的倍率超出有限数值范围")
    for node in nodes(changed):
        if node[0] not in {"SpecifyEffectDirectly", "ResolveByElement"}:
            continue
        family = node[1].rsplit("/", 1)[0] if node[0] == "SpecifyEffectDirectly" else node[1]
        if family in (effects or {}):
            node[1] = effects[family] + node[1][len(family):]
            if matched is not None:
                matched.add(family)
    validate_action_dsl(changed)
    return changed


def summary(tree):
    attacks = list(nodes(tree, "CreateNormalAttack"))
    areas = list(nodes(tree, "CreateHitArea"))
    coefficients = [{"index": i, "elementCode": attack[2],
                     "terms": copy.deepcopy(_terms(attack))} for i, attack in enumerate(attacks)]
    families = set()
    for name in ("SpecifyEffectDirectly", "ResolveByElement"):
        for effect in nodes(tree, name):
            if len(effect) > 1 and isinstance(effect[1], str):
                families.add(effect[1].rsplit("/", 1)[0] if name == "SpecifyEffectDirectly" else effect[1])
    # Only a statically understood single execution of each hit area is summed.
    # Branches, loops, dynamic terms and linked programs are not additive totals.
    static_commands = {"CreateNormalAttack", "CreateHitArea", "CreateReferencePoint",
                       "ShowEffect", "NotifyPowerflipEnd", "SetPowerFilpSuppress"}
    unknown = any(n[1][0] not in static_commands for n in nodes(tree, "Command"))
    unknown |= any(n[1][0] != "Wait" for n in nodes(tree, "Event"))
    unknown |= any(n[8] != ["Single"] for n in nodes(tree, "CreateReferencePoint"))
    nominal, covered = 0.0, set()
    for area in areas:
        if len(area) < 25:
            raise DraftError("PF 判定区参数不完整")
        formation, interval = area[12], area[14]
        if (not isinstance(interval, list) or len(interval) != 2
                or interval[0] != "CalculatedUsingMaxNumOfHits" or not finite(interval[1])):
            unknown = True
            continue
        if not isinstance(formation, list) or formation[:1] not in (["Single"], ["NWay"]):
            unknown = True
            continue
        ways = formation[1] if formation[:1] == ["NWay"] else 1
        if not finite(ways):
            unknown = True
            continue
        for attack in nodes(area[23], "CreateNormalAttack"):
            if id(attack) in covered:
                unknown = True
                continue
            covered.add(id(attack))
            terms = _terms(attack)
            if any("mul" in t or t["min"] != t["max"] for t in terms):
                unknown = True
            nominal += ways * interval[1] * sum(t["max"] for t in terms)
    from wf.dsl.references import linked_programs
    unknown |= bool(linked_programs(tree)) or len(covered) != len(attacks)
    return {"hitCount": len(attacks), "hitAreaCount": len(areas), "coefficients": coefficients,
            "elements": sorted({a[2] for a in attacks}), "effectFamilies": sorted(families),
            "markers": [a[24] for a in areas],
            "nominalMultiplier": None if unknown else round(nominal, 10),
            "nominalNote": "按静态分段、束数和最大命中次数估算；不代表实际命中伤害" if not unknown
                           else "含动态倍率、分支、子程序或未静态确定的命中次数，不能相加为单一倍率"}


def closure_summary(trees):
    """Static inventories include children; a call graph is never one total."""
    values = [summary(tree) for tree in trees]
    if len(values) == 1:
        return values[0]
    result = dict(values[0])
    for key in ("hitCount", "hitAreaCount"):
        result[key] = sum(v[key] for v in values)
    for key in ("coefficients", "markers"):
        result[key] = [item for v in values for item in v[key]]
    for i, item in enumerate(result["coefficients"]):
        item["index"] = i
    for key in ("elements", "effectFamilies"):
        result[key] = sorted({item for v in values for item in v[key]})
    result.update(nominalMultiplier=None, nominalNote="包含子程序；清单汇总不代表动态调用次数，不能求单一总倍率")
    return result
