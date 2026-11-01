"""Encounter input regressions use client-shaped ESDL and native CSV tables."""
import copy
from collections import Counter

import wf_quest_lib as codec

from test_boss_model import row
from wf.boss import schema as s
from wf.boss.behavior_identity import GENERAL_FUNNEL, STANDARD_FUNNEL, WATCH
from wf.boss.behavior_model import STATES
from wf.boss.behavior_wire import compress, write_tree
from wf.boss.edit_state import BossEditState
from wf.boss.esdl import transform
from wf.rules.multiplayer_inputs import ACTION_SUFFIX, ESDL_SUFFIX, FUNNEL_STATES, MULTIBALL, ZAKO_STATES, collect_inputs


class View:
    def __init__(self, files):
        self.files, self.reads = files, Counter()

    def read_raw(self, logical):
        self.reads[logical] += 1
        return self.files.get(logical), "fixture"


def action(tree):
    return compress(write_tree(tree))


def command(node):
    return ["Command", node]


def target(path):
    return command(["CreateTargetAttack", -1, 0, 0, ["StateGroupChangedAndWait", 5], path])


def esdl(tree):
    return action(transform(tree, encode=True))


def enemy(table=s.GENERAL_BOSS, *, code="boss", level=10, cells=None):
    return {"kind": "boss", "table": table, "code": code, "level": level, "row": cells or []}


def general_files():
    return {
        STATES: codec.build_node({"routine": {"1": {"idle": row(53, {31: "a,b", 40: "c,d"})}},
                                  "unrelated": {"1": {"idle": row(53, {31: "x,y"})}}}),
        WATCH: codec.build_node({"1": {"boss": {"routine": {"2": {"funnel": {
            "0": row(22, {14: 5, 18: "battle/action/watch"})}}}}}}),
        "battle/action/watch" + ACTION_SUFFIX: action(["Block", []]),
    }


def general_document(*, slots=None):
    values = {25: "battle/marker/deliberately_absent", 42: "routine", **(slots or {})}
    return {"enemies": [enemy(cells=s.parse_rows(row(161, values))[0])]}


def test_standard_prefix_is_not_an_action_and_empty_file_paths_are_ignored():
    base = "battle/action/enemy/action/boss/boss$"
    logical = "battle/enemy/boss/boss" + ESDL_SUFFIX
    tree = {"action_base_path": base, "type": ["TBoss", {"pre_action_path": ["init"]}],
            "forms": [{"watches": [{"content": ["ExecuteAction", ["watch"], 0.0, 0.0]},
                                    {"content": ["ShowCutin", "battle/action/label", 0, 0.0, 0.0]}],
                       "states": [{"canonicalPath": 0, "actions": [
                {"filePath": ""}, {"filePath": "one"}]}]}]}
    view = View({logical: esdl(tree), base + "one" + ACTION_SUFFIX: action(["Wait", 1]),
                 base + "init" + ACTION_SUFFIX: action(["Wait", 2]),
                 base + "watch" + ACTION_SUFFIX: action(["Wait", 3])})
    files, missing = collect_inputs({"enemies": [enemy(s.STANDARD_BOSS, cells=["", logical])]}, view)
    assert set(files) == {logical, base + "one" + ACTION_SUFFIX, base + "init" + ACTION_SUFFIX,
                          base + "watch" + ACTION_SUFFIX}
    assert not missing
    assert base + ACTION_SUFFIX not in view.reads


def test_general_slots_watch_and_child_closure_do_not_depend_on_marker_firing():
    files = general_files()
    first, child = "battle/action/slot", "battle/action/child"
    files[first + ACTION_SUFFIX] = action(["Block", [target(child), target(child)]])
    files[child + ACTION_SUFFIX] = action(target(first))
    view = View(files)
    decoded, missing = collect_inputs(general_document(slots={111: first}), view)
    assert not missing
    assert set(decoded) == {STATES, WATCH, first + ACTION_SUFFIX, child + ACTION_SUFFIX,
                            "battle/action/watch" + ACTION_SUFFIX}
    assert set(decoded[STATES]) == {"routine"}
    assert decoded[STATES]["routine"]["1"]["idle"][0][31] == "a,b"
    assert decoded[WATCH]["1"]["boss"]["routine"]["2"]["funnel"]["0"][0][18] == "battle/action/watch"
    assert view.reads[first + ACTION_SUFFIX] == view.reads[child + ACTION_SUFFIX] == 1
    assert not any(path.endswith(".timeline.amf3.deflate") for path in view.reads)


def test_bad_or_missing_actions_preserve_other_decoded_inputs_and_reasons():
    files = general_files()
    files["battle/action/corrupt" + ACTION_SUFFIX] = compress(b"\x05\x00")
    view = View(files)
    decoded, missing = collect_inputs(general_document(slots={
        111: "battle/action/corrupt", 112: "battle/action/missing"}), view)
    assert "battle/action/watch" + ACTION_SUFFIX in decoded
    assert any("corrupt" in issue and "invalid AMF3" in issue for issue in missing)
    assert any("missing.action.dsl" in issue and "missing action" in issue for issue in missing)


def test_missing_esdl_and_state_tables_are_explicit_diagnostics():
    document = general_document()
    document["enemies"].append(enemy(s.STANDARD_BOSS, cells=["", "battle/enemy/absent"]))
    _, missing = collect_inputs(document, View({}))
    assert any(STATES in issue and "missing table" in issue for issue in missing)
    assert any(WATCH in issue and "missing table" in issue for issue in missing)
    assert any("battle/enemy/absent" + ESDL_SUFFIX in issue for issue in missing)


def test_candidate_bytes_are_read_without_enrolling_original_or_mutating_baseline():
    files = general_files()
    logical = "battle/action/slot" + ACTION_SUFFIX
    files[logical] = action(["Wait", 1])
    view = View(files)
    candidate = BossEditState(view)
    candidate.client[logical] = action(["Wait", 2])
    before_files, before_snapshot = copy.deepcopy(files), copy.deepcopy(candidate.snapshot())
    decoded, missing = collect_inputs(general_document(slots={111: "battle/action/slot"}), candidate)
    assert not missing
    assert decoded[logical] == ["Wait", 2]
    assert candidate.snapshot() == before_snapshot == {"client": {}, "server": {}}
    assert files == before_files


def test_spawned_general_and_standard_funnels_extend_closure_at_requested_level():
    files = general_files()
    files["battle/action/root" + ACTION_SUFFIX] = action(["Block", [
        command(["SpawnFunnel", ["Funnel", "general"]]), command(["SpawnFunnel", ["StandardFunnel", "standard"]])]])
    files[GENERAL_FUNNEL] = codec.build_node({"general": {
        "1": row(139, {89: "battle/action/wrong_level"}),
        "100": row(139, {89: "battle/action/funnel", 37: "funnel_routine"})}})
    files[FUNNEL_STATES] = codec.build_node({"funnel_routine": {"1": {"idle": row(53, {29: 0, 31: "a,b"})}}})
    files[STANDARD_FUNNEL] = codec.build_node({"standard": {"100": "battle/enemy/funnel/standard"}})
    files["battle/enemy/funnel/standard" + ESDL_SUFFIX] = esdl({
        "action_base_path": "battle/action/funnel$", "forms": [{"states": [
            {"canonicalPath": 0, "actions": [{"filePath": "hit"}]}]}]})
    files["battle/action/funnel" + ACTION_SUFFIX] = action(["Wait", 1])
    files["battle/action/funnel$hit" + ACTION_SUFFIX] = action(["Wait", 1])
    view = View(files)
    decoded, missing = collect_inputs(general_document(slots={111: "battle/action/root"}), view)
    assert not missing
    assert "battle/action/funnel" + ACTION_SUFFIX in decoded
    assert "battle/action/funnel$hit" + ACTION_SUFFIX in decoded
    assert decoded[FUNNEL_STATES]["funnel_routine"]["1"]["idle"][0][31] == "a,b"
    assert "battle/action/wrong_level" + ACTION_SUFFIX not in view.reads


def test_invalid_esdl_does_not_hide_independent_general_boss_inputs():
    files = general_files()
    files["battle/enemy/bad" + ESDL_SUFFIX] = compress(b"\x05\x00")
    document = general_document()
    document["enemies"].insert(0, enemy(s.STANDARD_BOSS, code="bad", cells=["", "battle/enemy/bad"]))
    decoded, missing = collect_inputs(document, View(files))
    assert "battle/action/watch" + ACTION_SUFFIX in decoded
    assert any("bad" in issue and "invalid AMF3" in issue for issue in missing)


def test_spawned_zako_closes_actions_and_state_subtree_without_touching_other_routines():
    files = general_files()
    files["battle/action/root" + ACTION_SUFFIX] = action(command(["SpawnFunnel", ["Zako", "minion"]]))
    files[s.GENERAL_ZAKO] = codec.build_node({"minion": {"100": row(40, {
        17: "minion_routine", 30: "battle/action/minion", 39: "battle/action/last_slot"})}})
    files[ZAKO_STATES] = codec.build_node({
        "minion_routine": {"1": {"idle": row(53, {29: 0, 31: "a,b"})}},
        "unrelated": {"1": {"idle": row(53, {29: 0, 31: "c,d"})}}})
    files["battle/action/minion" + ACTION_SUFFIX] = action(["Wait", 1])
    files["battle/action/last_slot" + ACTION_SUFFIX] = action(["Wait", 2])
    decoded, missing = collect_inputs(general_document(slots={111: "battle/action/root"}), View(files))
    assert not missing
    assert set(decoded[ZAKO_STATES]) == {"minion_routine"}
    assert "battle/action/minion" + ACTION_SUFFIX in decoded
    assert "battle/action/last_slot" + ACTION_SUFFIX in decoded


def test_explicit_zone_zako_is_scanned_and_missing_state_is_not_silently_complete():
    logical = "battle/action/minion" + ACTION_SUFFIX
    view = View({logical: action(["Wait", 1])})
    entry = enemy(s.GENERAL_ZAKO, code="minion", cells=s.parse_rows(row(40, {
        17: "minion_routine", 30: "battle/action/minion"}))[0])
    entry["kind"] = "zako"
    decoded, missing = collect_inputs({"enemies": [entry]}, view)
    assert logical in decoded
    assert any(ZAKO_STATES in issue and "missing" in issue for issue in missing)


def test_action_prefix_in_cutins_states_watch_cutins_and_effects_is_not_an_action():
    files = general_files()
    fake = "battle/action/this_is_a_cutin_or_label"
    files[WATCH] = codec.build_node({"1": {"boss": {"routine": {"2": {"funnel": {
        "0": row(22, {14: 5, 18: "battle/action/watch"}),
        "1": row(22, {14: 6, 18: fake})}}}}}})
    files[STATES] = codec.build_node({"routine": {"1": {"idle": row(53, {29: 0, 31: fake})}}})
    files[GENERAL_FUNNEL] = codec.build_node({"general": {"100": row(139, {
        37: "funnel_routine", 59: fake, 89: "battle/action/funnel"})}})
    files[FUNNEL_STATES] = codec.build_node({"funnel_routine": {"1": {"idle": row(53, {})}}})
    files[s.GENERAL_ZAKO] = codec.build_node({"minion": {"100": row(40, {
        1: fake, 17: "minion_routine", 30: "battle/action/minion"})}})
    files[ZAKO_STATES] = codec.build_node({"minion_routine": {"1": {"idle": row(53, {})}}})
    files["battle/action/root" + ACTION_SUFFIX] = action(["Block", [
        command(["SpawnFunnel", ["Funnel", "general"]]),
        command(["SpawnFunnel", ["Zako", "minion"]]),
        command(["Trace", fake]),
        command(["ShowEffect", "label", ["SpecifyEffectDirectly", fake]]),
        command(["CreateBombMultiball", -1, "pixel", ["None"], ["None"], ["None"],
                 "battle/action/bomb", 1, False]),
        command(["CreateTornado", -1, 0, 0, 1.0, 1, 1, "battle/action/tornado", False]),
        target("battle/action/target")]])
    for name in ("funnel", "minion", "bomb", "tornado", "target", "init"):
        files[f"battle/action/{name}" + ACTION_SUFFIX] = action(["Wait", 1])
    view = View(files)
    document = general_document(slots={69: fake, 109: "battle/action/init", 111: "battle/action/root"})
    document["label"] = fake
    decoded, missing = collect_inputs(document, view)
    assert not missing
    assert fake + ACTION_SUFFIX not in view.reads
    assert all(f"battle/action/{name}" + ACTION_SUFFIX in decoded
               for name in ("funnel", "minion", "bomb", "tornado", "target", "init"))


def test_spawn_alter_ego_selects_general_boss_tier_and_closes_recursive_actions():
    files = general_files()
    spawn = command(["SpawnAlterEgo", "clone", ["CustomPosition", "position"], False, False])
    files["battle/action/root" + ACTION_SUFFIX] = action(spawn)
    files[s.GENERAL_BOSS] = codec.build_node({"clone": {
        "1": row(161, {42: "wrong", 111: "battle/action/wrong_level"}),
        "100": row(161, {42: "clone_routine", 111: "battle/action/clone"})}})
    states = codec.parse_node(files[STATES])
    states["clone_routine"] = {"1": {"idle": row(53, {29: 0, 31: "a,b"})}}
    files[STATES] = codec.build_node(states)
    files["battle/action/clone" + ACTION_SUFFIX] = action(spawn)
    view = View(files)
    decoded, missing = collect_inputs(general_document(slots={111: "battle/action/root"}), view)
    assert not missing
    assert "battle/action/clone" + ACTION_SUFFIX in decoded
    assert set(decoded[STATES]) == {"routine", "clone_routine"}
    assert "battle/action/wrong_level" + ACTION_SUFFIX not in view.reads
    assert view.reads["battle/action/clone" + ACTION_SUFFIX] == 1


def test_summoned_multiball_follows_action_and_reports_unexpanded_support_dependencies():
    files = general_files()
    files["battle/action/root" + ACTION_SUFFIX] = action(command(["CreateSummonsMultiball", -1, 7]))
    files[MULTIBALL] = codec.build_node({"7": row(24, {9: "battle/action/multiball", 20: 629})})
    files["battle/action/multiball" + ACTION_SUFFIX] = action(["Wait", 1])
    decoded, missing = collect_inputs(general_document(slots={111: "battle/action/root"}), View(files))
    assert "battle/action/multiball" + ACTION_SUFFIX in decoded
    assert len(missing) == 1 and "support ability dependencies not expanded" in missing[0]
    assert MULTIBALL + "#/7" in missing[0] and "c20" in missing[0]
    files[MULTIBALL] = codec.build_node({"7": row(24, {9: "battle/action/multiball"})})
    _, missing = collect_inputs(general_document(slots={111: "battle/action/root"}), View(files))
    assert not missing
