"""L2 编排级 timeline: parser golden lists, unknown nodes, subprograms, loop cap, effect baking."""
from __future__ import annotations

import pytest

from wf.studio.effect_render import build_states, flatten
from wf.studio.timeline import REPEAT_CAP, build_timeline


def root(*children, bta=0):
    return ["ActionDsl", 1, ["None"], False, False, False, False, False, False, False, bta, ["Block", list(children)]]


def cmd(name, *params):
    return ["Command", [name, *params]]


def wait(frames, *children):
    return ["Event", ["Wait", frames, "*", ["Block", list(children)]]]


def show(name, path, subject, lifetime, scale=None):
    return cmd("ShowEffect", name, ["SpecifyEffectDirectly", path], subject, ["ForesideOfCharacter"], lifetime,
               ["AB"], 0, 0, 0, True, False, ["Some", [{"min": scale, "max": scale}]] if scale else ["None"])


def hit_area(subject, life, hits, on_create, on_hit, bta=0, shape=None):
    return cmd("CreateHitArea", "*", subject, ["AB"], 0, -125, 0, False, False,
               shape or ["Circle", [{"min": 250, "max": 250}]], ["Center"], ["Center"], ["Single"],
               ["SpecifyHitAreaLifetimeDirectly", life], ["CalculatedUsingMaxNumOfHits", hits], ["None"],
               False, True, ["None"], 0, ["Block", on_create], 1, 2, ["Block", on_hit], bta, 0, ["None"])


def attack(target, multiplier):
    return cmd("CreateNormalAttack", target, 255, [], [], 0, [{"min": multiplier, "max": multiplier}],
               [{"min": 0, "max": 0}], False, False, False, False, False, [{"min": 1, "max": 1}],
               [{"min": 1, "max": 1}], ["Fine"], True)


EFFECTS = {
    "battle/effect/a/boom": {"sequences": [{"name": "start", "kind": "pass", "begin": 1, "end": 5},
                                           {"name": "loop", "kind": "loop", "begin": 6, "end": 9},
                                           {"name": "end", "kind": "once", "begin": 10, "end": 13}],
                             "sounds": [{"path": "sound_effect/x/se_boom", "begin": 2}], "defaultScale": 1},
    "battle/effect/a/flash": {"sequences": [{"name": "neutral", "kind": "once", "begin": 1, "end": 20}],
                              "sounds": [], "defaultScale": 6},
}


def simple(events):
    return [(e["t"], e["lane"], e["kind"], e["label"]) for e in sorted(events, key=lambda e: (e["t"], e["id"]))]


def test_golden_skill_with_wait_hit_area_and_end_sequence():
    tree = root(
        cmd("StopBall", -18, 60, ["Stop"], ["AB"], 0),
        show("前置", "battle/effect/a/flash", -18, ["PlayOnlyFirstSequence"]),
        wait(60, hit_area(-18, 45, 8,
                          [show("爆炸", "battle/effect/a/boom", 0, ["UntilTargetTerminates"], 6)],
                          [cmd("ShakeCamera", 1), attack(2, 2.0875)])),
    )
    timeline = build_timeline(tree, kind="skill", path="battle/action/x$x_1", effects=EFFECTS.get)
    assert simple(timeline["events"]) == [
        (0, "action", "StopBall", "停球 60 帧"),
        (0, "effect", "effect", "前置"),
        (0, "wait", "wait", "等待 60 帧"),
        (60, "hit", "hitarea", "判定区 圆 r250"),
        (60, "effect", "effect", "爆炸"),
        (60, "action", "ShakeCamera", "震屏 小"),
        (60, "hit", "attack", "攻击 ×2.0875"),
        (61, "sound", "sound", "se_boom"),
    ]
    events = {e["label"]: e for e in timeline["events"]}
    flash, boom, area = events["前置"], events["爆炸"], events["判定区 圆 r250"]
    assert flash["dur"] == 20 and flash["scale"] == 6 and flash["scaleSource"] == "parts 默认 s"
    # Bound to the hit area (45 frames), then the 4-frame end sequence plays out.
    assert boom["life"] == 45 and boom["endLength"] == 4 and boom["dur"] == 49 and boom["scale"] == 6
    assert boom["subject"]["ref"] == f"hitarea:{area['id']}"
    frames = [base + (local - start) * step for start, base, length, step in boom["runs"]
              for local in range(start, start + length)]
    assert frames[:12] == [1, 2, 3, 4, 5, 6, 7, 8, 9, 6, 7, 8] and frames[45:] == [10, 11, 12, 13]
    assert area["hits"]["expected"] == 8 and area["hits"]["times"][:2] == [0, 6.0]
    assert area["attacks"] == [events["攻击 ×2.0875"]["id"]]
    assert events["攻击 ×2.0875"]["trigger"] == "命中时（示意时刻）"
    assert timeline["attribution"]["label"] == "技能" and timeline["unknown"] == [] and timeline["issues"] == []
    assert timeline["duration"] == 109


def test_attribution_root_and_hit_area_override():
    tree = root(hit_area(-1, 10, 1, [], [attack(2, 1.0)], bta=101), bta=133)
    timeline = build_timeline(tree, kind="ability_skill", effects=EFFECTS.get)
    area = next(e for e in timeline["events"] if e["kind"] == "hitarea")
    hit = next(e for e in timeline["events"] if e["kind"] == "attack")
    assert timeline["attribution"]["label"].startswith("强化弹射 Lv3")
    assert area["attribution"]["label"] == "技能（转换）" and hit["attribution"]["label"] == "技能（转换）"
    auto = build_timeline(root(attack(-1, 1.0)), kind="pf")
    assert auto["attribution"] == {**auto["attribution"], "label": "强化弹射", "auto": True}


def test_unknown_nodes_are_listed_not_dropped():
    tree = root(cmd("Wait", 30, "x", ["Block", []]), ["Event", ["NoSuchEvent", 1]], ["Weird", 1],
                cmd("CreateTornado", 1, 2, 3, 0.5, 4, 5, "battle/action/none/missing", False))
    timeline = build_timeline(tree, effects=EFFECTS.get, programs=lambda logical: None)
    names = [u["name"] for u in timeline["unknown"]]
    assert names == ["Wait", "NoSuchEvent", "Weird"]
    assert "Trace" in timeline["unknown"][0]["reason"]
    assert [e["kind"] for e in timeline["events"]].count("unknown") == 3
    assert timeline["unmodeled"] == [{"name": "CreateTornado", "label": "龙卷风", "count": 1}]
    assert timeline["subprograms"][0]["error"] == "当前视图里没有这个子程序"


def test_subprogram_resolution_and_cycle_guard():
    sub = root(show("子特效", "battle/effect/a/flash", -18, ["PlayOnlyFirstSequence"]),
               cmd("CreateBombMultiball", 1, "battle/action/s/bomb", ["E1", ["SpecifyEffectDirectly", "x"]],
                   ["SpecifyEffectDirectly", "x"], ["SpecifyEffectDirectly", "x"], "", 1, False))
    trees = {"battle/action/s/bomb.action.dsl.amf3.deflate": sub}
    tree = root(wait(10, cmd("CreateBombMultiball", 1, "battle/action/s/bomb", ["E1", ["SpecifyEffectDirectly", "x"]],
                             ["SpecifyEffectDirectly", "x"], ["SpecifyEffectDirectly", "x"], "", 1, False)))
    timeline = build_timeline(tree, path="battle/action/main$main", effects=EFFECTS.get, programs=trees.get)
    entry = timeline["subprograms"][0]
    assert entry["t"] == 10 and entry["timeline"]["events"][0]["label"] == "子特效"
    # The sub-program names itself again: the cycle is reported, not expanded.
    assert entry["timeline"]["subprograms"][0]["error"] == "循环引用，未展开"


def test_repeat_is_capped_and_branches_show_both_arms():
    body = cmd("ShakeCamera", 1)
    tree = root(["Event", ["Repeat", 1, 90, "*", ["Block", [body]]]],
                cmd("ConditionalsFeverMode", ["Block", [cmd("AddFeverPoint", [{"min": 1, "max": 1}])]], ["Block", []]))
    timeline = build_timeline(tree)
    shakes = [e for e in timeline["events"] if e["kind"] == "ShakeCamera"]
    assert len(shakes) == REPEAT_CAP and [e["t"] for e in shakes[:3]] == [0, 1, 2]
    repeat = next(e for e in timeline["events"] if e["kind"] == "repeat")
    assert repeat["count"] == 90 and repeat["expanded"] == REPEAT_CAP and "其余" in repeat["detail"]
    assert [a["label"] for a in timeline["arms"]] == ["条件:Fever中 · 条件成立", "条件:Fever中 · 条件不成立"]
    assert timeline["arms"][1]["empty"] is True
    fever = next(e for e in timeline["events"] if e["kind"] == "AddFeverPoint")
    assert fever["arms"] == [0]


def test_scope_and_coordinate_checks():
    tree = root(show("坏锚点", "battle/effect/a/flash", 7, ["PlayOnlyFirstSequence"]),
                cmd("ShowEffect", "CD挂球", ["SpecifyEffectDirectly", "battle/effect/a/flash"], -18,
                    ["ForesideOfCharacter"], ["PlayOnlyFirstSequence"], ["CD"], 0, 0, 0, True, True, ["None"]))
    texts = [i["text"] for i in build_timeline(tree, effects=EFFECTS.get)["issues"]]
    assert any("C16103" in t for t in texts) and any("U_4f5401" in t for t in texts)
    bare = build_timeline(["Block", [cmd("ShakeCamera", 1)]])
    assert any("F1009" in i["text"] for i in bare["issues"])


def test_hide_effect_and_collision_arms():
    tree = root(show("光环", "battle/effect/a/boom", -18, ["SpecifyEffectLifetimeDirectly", 100]),
                ["Event", ["CollisionOfBallAndEnemy", 90, 1, "*", 5, ["Block", [cmd("HideEffect", "光环"), attack(5, 3.0)]]]])
    timeline = build_timeline(tree, effects=EFFECTS.get)
    aura = next(e for e in timeline["events"] if e["label"] == "光环")
    assert aura["hiddenAt"] == 1 and aura["life"] == 1 and aura["endLength"] == 4
    hit = next(e for e in timeline["events"] if e["kind"] == "attack")
    assert hit["subject"]["ref"] == "enemy" and hit["arms"] == [0] and hit["trigger"] == "球碰到敌人时"


def test_effect_bake_uses_frame_box_top_left_and_mirrors():
    parts = {"t": [{"a": 4096, "b": 0, "c": 0, "d": 4096, "x": 0, "y": 0},
                   {"a": -4096, "b": 0, "c": 0, "d": 4096, "x": 0, "y": 0}],
             "g": [{"t": 2, "s": [{"s": 0, "i": 0, "l": [{"m": 255, "t": 2}]},
                                  {"s": 0, "i": 0, "l": [{"m": (1 << 12) | (1 << 8) | 128, "t": 2}]}]}],
             "i": [{"p": ".gen/x/a"}], "c": [], "s": 1}
    frames, partial = build_states(parts)
    commands = flatten(frames, 0, 1)
    assert not partial and len(commands) == 2
    (item, plain, alpha, blend), (_, mirrored, half, add) = commands
    assert plain == (1.0, 0.0, 0.0, 1.0, 0.0, 0.0) and alpha == 1.0 and blend == 0
    assert mirrored[0] == -1.0 and add == 1 and half == pytest.approx(128 / 255)


@pytest.fixture(scope="module")
def real_routes():
    try:
        from wf.studio.source import build_source
        source = build_source()
    except (FileNotFoundError, OSError, KeyError) as exc:
        pytest.skip(f"real layered view unavailable: {exc}")
    if source.table("character").get("111183") is None:
        pytest.skip("111183 not in the configured real layered view")
    from types import SimpleNamespace
    from wf.studio.timeline_routes import TimelineRoutes
    return SimpleNamespace(source=source, routes=TimelineRoutes(SimpleNamespace(source=source)))


def test_real_programs_and_timelines(real_routes):
    from wf.studio.timeline_routes import character_programs
    listing = character_programs(real_routes.source, "111183")
    groups = {p["group"] for p in listing["programs"]}
    assert {"技能", "强化弹射", "能力技（629）"} <= groups
    for program in listing["programs"]:
        if not program["exists"]:
            continue
        timeline = real_routes.routes.build(program["path"], program["kind"], 0)
        assert timeline["unknown"] == [] and timeline["events"]
    skill = next(p for p in listing["programs"] if p["kind"] == "skill")
    timeline = real_routes.routes.build(skill["path"], "skill", 0)
    assert any(e["kind"] == "hitarea" for e in timeline["events"])
    effect = next(e for e in timeline["events"] if e["kind"] == "effect" and e["asset"])
    meta, png = real_routes.routes._baked(effect["path"])
    assert meta["ok"] and png and meta["frames"]
