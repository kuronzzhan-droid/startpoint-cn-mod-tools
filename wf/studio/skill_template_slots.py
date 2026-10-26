"""SLvValue Array slots (other DSL arrays contain IDs or expressions)."""
SLV_SLOTS = {
    "CreateNormalAttack": (6, 7, 13, 14), "CreateRatioAttack": (3,), "CreateFixedAttack": (2,),
    "CreateSummonsMultiball": (3,), "CreateCondition": (3, 11),
    "SpecifyHitAreaLifetimeSLv": (1,), "SpecifyEffectLifetimeSLv": (1,),
    "SpecifyMinHitIntervalSLv": (1,), "CalculatedUsingMaxNumOfHitsSLv": (1,),
    "SpecificFrameSLv": (1,), "Circle": (1,), "Rectangle": (1, 2),
    "AddCombo": (1,), "AddFeverPoint": (1,), "SubtractFeverPoint": (1,),
    "AddSkillPoint": (2,), "SubtractSkillPoint": (2,), "CreateBarrier": (2,),
    "CreateNormalHeal": (2, 3, 4), "CreateRatioHeal": (3, 4, 5),
    "CreateOnlyHitAttack": (2, 3), "CreatePointsDistanceDetector": (3, 4),
    "CreateWallDistanceDetector": (2,), "SpawnFunnel": (4,), "StartBuffField": (3,),
    "StartModifierField": (2,), "SuppressBallActivity": (2,), "SuppressSkill": (2,),
}
