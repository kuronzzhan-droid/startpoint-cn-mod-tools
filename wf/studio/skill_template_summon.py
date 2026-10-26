"""Native opening summon with explicit ownership/count semantics."""
from __future__ import annotations

from .skill_template_validation import walk

# An actual official E2 donor, including distinct left/right ready sequences.
# The older one-off builder used a private dark_call family absent from archives.
DEFAULT_EFFECT = "battle/effect/skill_unique/yamada_tae/multiball_yamada_tae_effect"


def _block(*children):
    return ["Block", list(children)]


def _command(*params):
    return ["Command", list(params)]


def opening_summon(tree, spec):
    """One new ball below the cap; never replace or refresh existing balls."""
    allowed = {"multiballId", "maxCount", "selfOnly", "durationFrames", "effectPrefix"}
    if not isinstance(spec, dict) or set(spec) - allowed:
        raise ValueError("开头召唤参数存在未知字段")
    raw_id = spec.get("multiballId")
    if isinstance(raw_id, str) and raw_id.isascii() and raw_id.isdigit():
        raw_id = int(raw_id)
    if type(raw_id) is not int or not 0 < raw_id <= 2147483647:
        raise ValueError("multiballId 必须是正整数 ID")
    cap, own, duration = spec.get("maxCount", 1), spec.get("selfOnly", True), spec.get("durationFrames", 2147483647)
    if type(cap) is not int or not 1 <= cap <= 99 or type(own) is not bool:
        raise ValueError("召唤 maxCount 需要 1..99，selfOnly 需要布尔值")
    if type(duration) is not int or not 0 < duration <= 2147483647:
        raise ValueError("召唤 durationFrames 必须是正整数帧数")
    if own and cap > 1:
        raise ValueError("原生计数不支持 selfOnly=true 且 maxCount>1；不能冒充仅自身计数")
    prefix = spec.get("effectPrefix", DEFAULT_EFFECT)
    if not isinstance(prefix, str) or not prefix.startswith("battle/effect/") or ".." in prefix or "\\" in prefix:
        raise ValueError("召唤 effectPrefix 必须是 battle/effect 下的逻辑路径")
    # Bound callback subjects are local, but avoid donor IDs for readable audits.
    occupied = {value for _, node in walk(tree) if isinstance(node, list)
                for value in node if type(value) is int and value >= 0}
    ball = 900
    while ball in occupied or ball + 1 in occupied:
        ball += 2
    member = ball + 1
    label = f"studio_summon_{raw_id}_activation"
    effect = lambda suffix: ["SpecifyEffectDirectly", prefix + suffix]
    fresh = _command("CreateSummonsMultiball", 1, raw_id,
                     [{"min": duration, "max": duration}],
                     ["E2", effect("_ready_generation"), effect("_ready_left"), effect("_ready_right")],
                     effect("_appear"), effect("_disappear"), 0, False,
                     label, ball, member, _block(), None)
    if cap == 1:
        absent = _block(_command("RemoveEventFromOwner", label), fresh)
        statement = _command("FindMultiballSubjects", ball, member, own, [raw_id], absent, _block())
    else:
        statement = _command("ConditionalsMultiballNumber", [raw_id], [], cap, _block(), _block(fresh))
    return statement, {"multiballId": str(raw_id), "maxCount": cap, "selfOnly": own,
                       "durationFrames": duration, "effectPrefix": prefix,
                       "countMode": "live-including-pending" if cap == 1 else "native-party-count"}
