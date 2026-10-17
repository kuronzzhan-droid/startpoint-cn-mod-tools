"""Bounded lifecycle replay adapted from Ku1o/startpoint-cn-kulo 8f8cd498.

Exercises generated commands against the verified native Wait/impact order.
It does not emulate input, graphics or damage calculations; no device claim.
"""
from dataclasses import dataclass
import re

@dataclass(eq=False)
class Dragon:
    owner: str
    generation: int
    dead: bool = False
    disposed: bool = False


def bianca_replay(tree, casts, deaths=None, initial_owners=("A",), end=110):
    """Execute lookup, Wait, cancellation, condition targets and removal.

    Cast/event ticks are illustrative action-update ticks, not measured input
    intervals or real seconds. Damage calculation, animations and input gating
    are excluded; the actual unchanged damage-trigger payload is recorded.
    """
    dragons = [Dragon(owner, 1) for owner in initial_owners]
    generations = {owner: 1 for owner in initial_owners}
    listeners, impacts, trace = [], [], []
    event_serial = 0
    frame, error = 0, None

    def record(kind, **kw):
        trace.append({"frame": frame, "event": kind, **kw})

    def eval_expr(expr, env, cast_id, owner):
        nonlocal event_serial
        kind = expr[0]
        if kind == "Block":
            for child in expr[1]:
                eval_expr(child, env, cast_id, owner)
        elif kind == "Event":
            event = expr[1]
            if event[0] != "Wait":
                raise AssertionError("unmodeled event")
            event_serial += 1
            listeners.append({"counter": -1, "limit": event[1], "name": event[2], "body": event[3],
                              "env": env, "cast": cast_id, "owner": owner, "serial": event_serial})
        elif kind == "Command":
            cmd = expr[1]
            if cmd[0] == "FindMultiballSubjects":
                assert cmd[1:5] == [10, 11, True, [1199891]]
                targets = [x for x in dragons if x.owner == owner and not x.disposed]
                if not targets:
                    eval_expr(cmd[5], dict(env), cast_id, owner)
                for target in targets:
                    eval_expr(cmd[6], {**env, 11: target}, cast_id, owner)
            elif cmd[0] == "RemoveEventFromOwner":
                listeners[:] = [x for x in listeners if not (x["owner"] == owner and x["name"] == cmd[1])]
            elif cmd[0] == "CreateCondition" and cmd[1] == 11:
                impacts.append((env[11], cmd, cast_id))
            elif cmd[0] == "CreateCondition" and cmd[1] == -17:
                record("self_condition", owner=owner, cast=cast_id, condition=cmd[2])
            elif cmd[0] == "AddFeverPoint":
                record("fever", owner=owner, cast=cast_id, amount=cmd[1][0]["max"])
            elif cmd[0] == "RemoveMultiball":
                assert cmd[1:] == [True, [1199891]]
                for target in dragons:
                    if target.owner == owner and not target.disposed:
                        target.dead = True
                        record("depart", owner=owner, generation=target.generation, cast=cast_id)
            elif cmd[0] == "CreateSummonsMultiball":
                assert cmd[2] == 1199891
                generations[owner] = generations.get(owner, 0) + 1
                target = Dragon(owner, generations[owner])
                dragons.append(target)
                record("spawn", owner=owner, generation=target.generation, cast=cast_id)
                # Activation timing is out of scope; only the generation and
                # existing callback cleanup are needed for these regressions.

    for frame in range(end):
        for owner in (deaths or {}).get(frame, []):
            for target in dragons:
                if target.owner == owner and not target.disposed:
                    target.dead = target.disposed = True
                    record("external_death", owner=owner, generation=target.generation)
        for serial, (at, owner) in enumerate(casts, 1):
            if at == frame:
                eval_expr(tree[11], {}, serial, owner)
        # Haxe List.add inserts at the head. A cast's nested events start at -1
        # and are first updated in its next ActionEvaluator.update call.
        cast_ids = sorted({x["cast"] for x in listeners}, reverse=True)
        for cast_id in cast_ids:
            current = sorted([x for x in listeners if x["cast"] == cast_id], key=lambda x: -x["serial"])
            for event in current:
                event["counter"] += 1
            for event in current:
                if event not in listeners:
                    continue
                if event["counter"] == event["limit"]:
                    eval_expr(event["body"], event["env"], event["cast"], event["owner"])
                    listeners.remove(event)
        for target, cmd, cast_id in impacts:
            # Unique 11998902 overrides DSL p12 with master forceApply=true.
            forced = cmd[12] or cmd[2][0][0] == "ACUnique"
            if target.dead and not forced:
                continue
            if target.disposed:
                error = {"code": "G1008", "frame": frame, "cast": cast_id, "generation": target.generation}
                break
            record("dragon_condition", owner=target.owner, generation=target.generation,
                   cast=cast_id, condition=cmd[2])
        impacts.clear()
        if error:
            break
        for target in dragons:
            if target.dead:
                target.disposed = True
    return {"error": error, "trace": trace}


def breath_events(result):
    return [x for x in result["trace"] if x["event"] == "dragon_condition" and x["condition"][0][0] == "ACUnique"]


def neph_replay(conditions, modes, count=1, queued_while_live=True):
    """Replay a held impact batch across OnlySquad expiration with real flags."""
    age, lifetime, dead, disposed = 1498, 1500, False, False
    pending, trace, error = [], [], None
    for tick, mode in enumerate(modes):
        if not disposed:
            age += 1
            if age > lifetime:
                dead = True
        if mode == "AllEntities":
            current, pending = pending, []
            for condition in current:
                if dead and not condition[12]:
                    trace.append("skip_dead")
                elif disposed:
                    error = "G1008"
                    break
                else:
                    trace.append("apply")
            if error:
                break
        if dead:
            disposed = True
        # End-of-frame RunAction queues a Member reference for the next impact
        # pass. A selection-time alive check also passes at this exact point.
        if tick == 0 and (not queued_while_live or not dead):
            pending.extend(conditions * count)
    return {"error": error, "trace": trace, "summons": count}


def function_body(source, name):
    match = re.search(r"public (?:static )?function " + re.escape(name) + r"\(", source)
    assert match, name
    begin = source.index("{", match.end())
    depth, end = 1, begin + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[begin:end]
