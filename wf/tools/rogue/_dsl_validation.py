"""Reviewed nullable-enum normalization shared by generated action DSL."""
import copy
from typing import Any
import wf_dsl_sig

def _normalize_for_signature(tree: Any, logical: str) -> Any:
    """Normalize the one documented nullable enum slot for signature checks.

    The decompiled ``CreateCondition`` signature declares p8 as the
    ``HitCountCheckTargetKind`` enum, while the game serializes the omitted
    check as ``null``.  Normalize only that documented nullable slot to a
    valid enum constructor for the generated type checker; every other null
    or signature/type mismatch still fails closed.
    """
    normalized = copy.deepcopy(tree)

    def walk(value: Any) -> None:
        if isinstance(value, list):
            if (
                len(value) == 2
                and isinstance(value[0], str)
                and value[0] in {"Command", "Event"}
                and isinstance(value[1], list)
                and value[1]
            ):
                name = value[1][0]
                for index, parameter in enumerate(value[1][1:], start=1):
                    if parameter is None:
                        if name != "CreateCondition" or index != 8:
                            raise ValueError(
                                f"{logical}: {name} 参数{index}出现未审核 null"
                            )
                        # The concrete enum value is ignored when no hit
                        # count check is requested; this sentinel is only for
                        # validating the generated enum signature.
                        value[1][index] = ["Skill"]
            for child in value:
                walk(child)
        elif isinstance(value, dict):
            for child in value.values():
                walk(child)

    walk(normalized)
    return normalized

def _validate_official_dsl(tree: Any, logical: str) -> None:
    """Run the generated command/enum signature gate on a Siete DSL."""
    normalized = _normalize_for_signature(tree, logical)
    try:
        wf_dsl_sig.validate_action_dsl(normalized)
    except wf_dsl_sig.DslSignatureError as error:
        raise ValueError(f"{logical}: ActionDSL 官方签名/枚举校验失败: {error}") from error
