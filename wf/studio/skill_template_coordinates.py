"""Subject-type-aware coordinate safety for skill templates."""

def coordinate_problems(tree):
    """Track callback subject types so CD cannot be attached to an enemy/ball."""
    problems = []
    sites = {"CreateHitArea": (2, 3), "CreateReferencePoint": (1, 2),
             "ShowEffect": (3, 6), "MoveHitArea": (1, 2), "CreateCollider": (1, 5),
             "CreateShockWaveAttack": (2, 3), "MoveBall": (1, 2), "StopBall": (1, 4)}
    bindings = {
        "CreateHitArea": {20: {19: "point"}, 23: {21: "point", 22: "enemy"}},
        "CreateReferencePoint": {11: {10: "point"}},
        "CreateReferencePointAtSpecifiedPosition": {5: {3: "point", 4: "point"}},
        "FindNearSubjects": {6: {5: "actor"}},
        "FindAllSubjects": {9: {1: "actor"}},
        "FindMultiballSubjects": {6: {1: "ball", 2: "member"}},
        "CreateSummonsMultiball": {12: {10: "ball", 11: "member"}},
        "ActivatedMultiballOfExecutorSelf": {4: {2: "ball", 3: "member"}},
        "CollisionOfBallAndEnemy": {5: {4: "enemy"}},
        "SetHitAreaSomeHitsWithSpecificTargetHandler": {4: {2: "point", 3: "enemy"}},
        "CreateShockWaveAttack": {13: {10: "point", 11: "point", 12: "enemy"}},
        "CollisionOfBallAndSpecificEnemy": {6: {5: "enemy"}, 7: {5: "enemy"}},
        "CollisionOfSpecificBallAndSpecificEnemy": {7: {6: "enemy"}, 8: {6: "enemy"}},
    }

    def visit(value, scope, path):
        if not isinstance(value, list):
            return
        if value and isinstance(value[0], str):
            tag = value[0]
            if tag == "Block":
                local = dict(scope)
                for i, statement in enumerate(value[1]):
                    visit(statement, local, f"{path}/1/{i}")
                    if statement[:1] == ["Command"] and statement[1][:1] == ["TargetMate"]:
                        local[statement[1][1]] = "member"
                return
            if tag in sites:
                subject_slot, coord_slot = sites[tag]
                if value[coord_slot] == ["CD"] and scope.get(value[subject_slot]) in {
                        "ball", "member", "enemy", "actor"}:
                    problems.append(f"{path}/{tag}: CD 坐标不能挂在球、角色或敌人主体上")
            scoped = bindings.get(tag, {})
            for index, child in enumerate(value[1:], 1):
                inner = dict(scope)
                for slot, kind in scoped.get(index, {}).items():
                    inner[value[slot]] = kind
                visit(child, inner, f"{path}/{index}")
        else:
            for index, child in enumerate(value):
                visit(child, scope, f"{path}/{index}")

    visit(tree, {-17: "member", -18: "ball"}, "")
    return problems

