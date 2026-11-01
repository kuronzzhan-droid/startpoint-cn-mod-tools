"""E1 scene bindings, preservation and fail-closed draft contracts without local data."""
import copy
import json
from types import SimpleNamespace

import pytest
import wf_quest_lib as codec
import wf_share_update_codec as wire
from wf.tools.boss.five_boss_v2 import encode_dsl, decode_amf
from wf.boss.scene import compile_scene
from wf.boss.scene_spec import materialize, validate_spec
from wf.studio.scene_routes import SceneRoutes, SceneStore
from wf.studio.drafts import DraftError, DraftStore


@pytest.fixture
def scene():
    table, resource = "master/scene.orderedmap", "battle/scene.amf3.deflate"
    spec = {"schema": "wf-boss-scene/1", "id": "scene-demo", "name": "合成场景", "sourceVersion": "1.4.10",
        "event": {"id": "300001", "settings": []},
        "tiers": [{"id": str(i), "quest": str(300001000 + i), "settings": []} for i in range(1, 6)],
        "phases": [{"id": "p1", "settings": []}], "shops": [{"id": "1", "settings": []}],
        "drops": [{"id": "1", "settings": []}], "summons": [], "mechanisms": [], "trials": [],
        "tables": [{"logical": table, "entries": [{"path": ["owned"], "value": "name,1,2\n"}]}],
        "resources": [{"logical": resource, "encoding": "amf3", "value": {
            "bgm": "first", "field": "arena-a", "summon": "minion", "trial": 16}}], "requirements": []}
    def setting(key, kind, value):
        return {"id": key, "kind": kind, "value": value, "bindings": [{"resource": resource, "path": [key]}]}
    spec["phases"][0]["settings"] = [setting("bgm", "bgm", "first"), setting("field", "field", "arena-a")]
    spec["summons"] = [setting("summon", "summon", "minion")]
    spec["trials"] = [setting("trial", "threshold", 16)]
    data = {table: codec.build_node({"owned": "name,1,2\n", "foreign": {"unaltered": "keep,exact\r\n"}}),
            resource: encode_dsl(spec["resources"][0]["value"])}
    def load(logical):
        if logical not in data:
            raise FileNotFoundError(logical)
        return data[logical]
    return spec, data, load


def test_studio_scene_semantics_compile_bgm_arena_summons_trials(scene):
    spec, data, loader = scene
    spec["phases"][0]["settings"][0]["value"] = "second"
    spec["phases"][0]["settings"][1]["value"] = "arena-b"
    spec["summons"][0]["value"] = "new-minion"
    spec["trials"][0]["value"] = 66
    before = copy.deepcopy(data)
    result = compile_scene(loader, spec, check_encounters=False)
    actual = decode_amf(result["files"]["battle/scene.amf3.deflate"])
    assert actual == {"bgm": "second", "field": "arena-b", "summon": "new-minion", "trial": 66}
    assert data == before and result["audit"]["aligned"]
    assert not result["canGenerate"]  # No server mirror; full delivery must not pretend completeness.


def test_studio_scene_binding_csv_preserves_foreign_compressed_leaf(scene):
    spec, data, loader = scene
    table = "master/scene.orderedmap"
    spec["tiers"][0]["settings"] = [{"id": "hp", "kind": "hp", "value": "3.5",
        "bindings": [{"table": table, "path": ["owned"], "column": 1}]}]
    result = compile_scene(loader, spec, check_encounters=False)
    assert codec.parse_node(result["files"][table])["owned"] == "name,3.5,2\n"
    assert wire.unpack(data[table])["foreign"] == wire.unpack(result["files"][table])["foreign"]


@pytest.mark.parametrize("mutate", [
    lambda d: d["trials"][0].update(value="NaN"),
    lambda d: d["trials"][0].update(value="Infinity"),
    lambda d: d["trials"][0].update(value="1e999"),
    lambda d: d["trials"][0].update(value=1.5),
    lambda d: d["resources"][0].update(logical="../escape.amf3.deflate"),
    lambda d: d["trials"][0]["bindings"][0].update(path=["absent"]),
    lambda d: d["tiers"][1].update(quest=d["tiers"][0]["quest"]),
    lambda d: d["tables"].append(copy.deepcopy(d["tables"][0])),
])
def test_studio_scene_rejects_invalid_spec_and_dead_bindings(scene, mutate):
    spec, _, _ = scene
    mutate(spec)
    with pytest.raises(ValueError):
        materialize(spec)


def test_studio_scene_conflicting_bindings_and_stale_graph(scene):
    spec, data, loader = scene
    duplicate = copy.deepcopy(spec["trials"][0]); duplicate["value"] = 8
    spec["trials"].append(duplicate)
    with pytest.raises(ValueError, match="冲突"):
        materialize(spec)
    spec["trials"].pop()
    data["master/scene.orderedmap"] = codec.build_node({"owned": "live,1,2\n"})
    result = compile_scene(loader, spec, check_encounters=False)
    assert not result["audit"]["aligned"] and not result["canGenerate"]


def test_studio_scene_store_revision_and_preview_no_disk(tmp_path, monkeypatch):
    source = SimpleNamespace(version="1.4.10")
    app = SimpleNamespace(source=source, ops=SimpleNamespace(store=DraftStore(tmp_path / "drafts")))
    routes = SceneRoutes(app)
    monkeypatch.setattr(routes, "compute", lambda *args: ({"ok": True, "canGenerate": False,
        "blockers": ["缺镜像"], "files": {}, "servers": {}, "outputSha256": {}}, SimpleNamespace(inputs={})))
    result = json.loads(routes.edit({}, {"payload": {}}, "hell-pumpkin", "preview").body)
    assert "files" not in result and not (tmp_path / "drafts").exists()
    routes.edit({}, {"payload": {}, "revision": 0}, "hell-pumpkin", "save")
    with pytest.raises(DraftError, match="其他窗口"):
        routes.edit({}, {"payload": {}, "revision": 0}, "hell-pumpkin", "save")
    with pytest.raises(DraftError, match="未知场景"):
        routes.store.directory("../escape")


def test_studio_scene_schema_and_routes_match_delivery_prefix(tmp_path):
    app = SimpleNamespace(source=SimpleNamespace(version="1.4.10"),
        ops=SimpleNamespace(store=DraftStore(tmp_path / "drafts")))
    routes = SceneRoutes(app)
    assert any(pattern.fullmatch("/api/scenes/drafts/hell-pumpkin/build") for _, pattern, _ in routes.routes())
    assert json.loads(routes.schema({}).body)["$id"] == "wf-boss-scene/1"
    assert not any(pattern.fullmatch("/api/scenes/deliveries/test/" + action)
                   for _, pattern, _ in routes.routes() for action in ("apply", "unapply"))


def test_studio_scene_schema_failure_is_value_error(scene):
    spec, _, _ = scene
    spec["phases"] = "invalid"
    with pytest.raises(ValueError, match="schema"):
        validate_spec(spec)


def test_studio_scene_csv_binding_aliases_conflict(scene):
    spec, _, _ = scene
    one = {"id": "hp", "kind": "hp", "value": "1", "bindings": [
        {"table": "master/scene.orderedmap", "path": ["owned"], "column": 1}]}
    two = copy.deepcopy(one); two["value"] = "2"; two["bindings"][0]["row"] = 0
    spec["tiers"][0]["settings"] = [one, two]
    with pytest.raises(ValueError, match="冲突"):
        materialize(spec)


def test_studio_scene_parent_child_binding_and_unhandled_requirements_rejected(scene):
    spec, _, _ = scene
    spec["requirements"] = ["unhandled-capability"]
    with pytest.raises(ValueError, match="requirements"):
        materialize(spec)


def test_studio_scene_clone_namespaces_logic_and_keeps_art(scene):
    from wf.boss.scene_clone import clone_scene
    spec, _, _ = scene
    spec["resources"] += [{"logical": "battle/boss/mod/hell_pumpkin/rage/rage.parts.amf3.deflate",
                           "encoding": "amf3", "value": {"art": "battle/boss/mod/hell_pumpkin/rage/rage"}},
                          {"logical": "battle/boss/mod/hell_pumpkin/hp_jack_marker.timeline.amf3.deflate",
                           "encoding": "amf3", "value": {"test": "xx30000112yy 130000112.25"}}]
    cloned = clone_scene(spec, "300099", "新活动")
    assert cloned["tiers"][0]["quest"] == "300099001"
    assert cloned["tiers"][0]["sourceQuest"] == "300001001"
    assert cloned["resources"][-2] == spec["resources"][-2]
    assert "/mod/studio_scene_300099/" in cloned["resources"][-1]["logical"]
    assert cloned["resources"][-1]["value"] == spec["resources"][-1]["value"]
    del cloned["creation"]
    cloned.pop("provenance")
    with pytest.raises(ValueError, match="防撞"):
        validate_spec(cloned)


def test_studio_scene_noop_never_enables_delivery(scene, monkeypatch):
    from wf.boss import scene_server
    spec, _, loader = scene
    monkeypatch.setattr(scene_server, "server_candidate", lambda *a: ({}, {}, []))
    result = compile_scene(loader, spec, check_encounters=False)
    assert result["ok"] and not result["canGenerate"]
    assert any("客户端变化" in message for message in result["blockers"])


def test_studio_scene_generated_table_key_requires_collision_declaration(scene):
    spec, _, _ = scene
    spec["event"]["id"] = "300099"
    spec["creation"] = {"sourceEvent": "300001", "tableTargets": [], "resourceTargets": []}
    spec["tables"].append({"logical": "master/probe.orderedmap", "entries": [
        {"path": ["mod_studio_scene_300099"], "value": "old,1\n"}]})
    spec["event"]["settings"] = [{"id": "new-value", "kind": "parameter", "value": "2", "bindings": [
        {"table": "master/probe.orderedmap", "path": ["mod_studio_scene_300099"], "column": 1}]}]
    with pytest.raises(ValueError, match="表键防撞"):
        materialize(spec)


def test_studio_scene_actual_namespace_requires_creation_without_ui_metadata(scene):
    spec, _, _ = scene
    spec["id"] = "edited-draft"
    spec["event"]["id"] = "300099"
    spec.pop("creation", None)
    spec.pop("provenance", None)
    logical = "battle/terrain/mod/studio_scene_300099/probe.amf3.deflate"
    spec["resources"] = [{"logical": logical, "encoding": "amf3", "value": {"value": 1}}]
    spec["phases"] = [{"id": "p1", "settings": [{"id": "change", "kind": "parameter", "value": 2,
        "bindings": [{"resource": logical, "path": ["value"]}]}]}]
    spec["summons"], spec["trials"] = [], []
    with pytest.raises(ValueError, match="命名空间.*防撞"):
        materialize(spec)


def test_studio_scene_dsl_uses_actual_command_slots_and_exact_bgm_keys():
    from wf.boss.scene_dsl import references, constructors
    def root(command):
        return ["ActionDsl", 1, ["None"], False, False, False, False, False, False, False, 0,
                ["Block", [["Command", command]]]]
    state = SimpleNamespace(table=lambda _: {"bgm/real": "0.32,0\n"},
                            raw=lambda p: pytest.fail("Trace text must not become a resource: " + p))
    assert references(state, {"battle/test.action.dsl.amf3.deflate": root(["Trace", "battle/action/not-a-program"])}) == []
    errors = references(state, {"battle/test.action.dsl.amf3.deflate": root(["ChangeBgm", "0", ["Immediate"]])})
    assert errors and "BGM" in errors[0]
    assert constructors(root(["SpawnFunnel"]))
