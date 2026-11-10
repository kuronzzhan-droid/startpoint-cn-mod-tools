"""EX selection stays within the existing read-only preview and delivery guards."""
import copy
import json
from types import SimpleNamespace

import pytest
import wf_quest_lib as q
from wf.studio import mode_rogue, mode_routes
from wf.studio.drafts import DraftError, DraftStore
from wf.tools.rogue import rogue_build as b


def tower(event, prefix):
    rows = {}
    for number in (1, 2, 99):
        row = [""] * 100
        row[:3] = [str(int(event) * 1000 + number), "2" if number == 99 else "1",
                   "0" if number == 99 else str(number)]
        row[4], row[98] = f"{event} floor {number}", prefix + str(number)
        rows[str(number)] = b.join(row, False)
    return rows


def view_tables():
    return {b.Q_QUEST: {"700099": tower("700099", "normal_"), "700100": tower("700100", "ex_")},
            b.Q_EVENT: {"700099": "normal,普通深渊", "700100": "ex,深渊EX"}}


def test_current_lists_both_events_without_reading_runtime_state():
    tables = view_tables()
    read = lambda logical: q.build_node(tables[logical])
    normal, ex = mode_rogue.current(read), mode_rogue.current(read, "700100")
    assert [a["event"] for a in normal["activities"]] == ["700099", "700100"]
    assert all(a["available"] for a in normal["activities"])
    assert normal["event"] == "700099" and ex["event"] == "700100"
    assert ex["rounds"] == normal["rounds"] == 2
    assert ex["rows"][0]["field"] == "ex_1" and normal["rows"][0]["field"] == "normal_1"
    assert ex["fingerprint"] != normal["fingerprint"]
    assert ex["season"] is None and "不连接" in ex["seasonNote"]
    assert all("_digest" not in activity for activity in normal["activities"])
    assert "700100" in ex["manualSteps"][0]["command"]
    assert "700100" in ex["manualSteps"][1]["command"]
    assert "700099" not in ex["manualSteps"][0]["command"]


def test_missing_ex_is_visible_but_cannot_reroll(monkeypatch):
    tables = view_tables()
    tables[b.Q_QUEST].pop("700100")
    read = lambda logical: q.build_node(tables[logical])
    ex = mode_rogue.current(read, "700100")
    assert not ex["available"] and ex["rows"] == [] and ex["unavailableReason"]
    monkeypatch.setattr(mode_rogue, "build_candidate", lambda *a, **kw: pytest.fail("must not build"))
    with pytest.raises(ValueError, match="未包含完整活动"):
        mode_rogue.preview(read, 7, "700100")


@pytest.mark.parametrize("event", [700100, "700101", "../700100", None, True])
def test_unknown_activity_rejected_before_read(event):
    with pytest.raises(ValueError, match="700099 或 700100"):
        mode_rogue.preview(lambda _: pytest.fail("must not read"), 7, event)


@pytest.mark.parametrize("seed", [True, -1, 2**32, 1.5, "7"])
def test_invalid_ex_seed_rejected_before_read(seed):
    with pytest.raises(ValueError, match="种子"):
        mode_rogue.preview(lambda _: pytest.fail("must not read"), seed, "700100")


@pytest.mark.parametrize("event", ["700099", "700100"])
@pytest.mark.parametrize("bind_server", [False, True])
def test_reroll_uses_selected_activity_and_keeps_metadata(monkeypatch, event, bind_server):
    from wf.studio import mode_rogue_overlay
    tables = view_tables()
    original = copy.deepcopy(tables)
    rows = {key: b.cells(value) for key, value in tables[b.Q_QUEST][event].items()}
    seen = []
    def build(loader, **kwargs):
        seen.append(kwargs)
        return {"rows": rows, "rounds": 2, "checks": [], "log": "selected event",
                "files": {b.Q_QUEST: q.build_node(tables[b.Q_QUEST]),
                          "master/reward/event/additional_reward.orderedmap": b"keep current rewards",
                          **{logical: b"must be removed" for logical in (b.Q_EVENT, b.Q_FOLDER, b.Q_LIST, b.Q_CORR)}}}
    def retain(loader, candidate):
        assert candidate["eventId"] == event
        assert set(candidate["files"]) == {b.Q_QUEST}
        return {**candidate, "cloneNamespace": "example"}
    monkeypatch.setattr(mode_rogue, "build_candidate", build)
    monkeypatch.setattr(mode_rogue_overlay, "retain_and_namespace", retain)
    reader = lambda name: {"source": name}
    options = {"server_asset_reader": reader} if bind_server else {}
    result = mode_rogue.preview(lambda logical: q.build_node(tables[logical]), 17, event, **options)
    assert seen == [{"seed": 17, "rounds": 2, "event_id": event, **options}]
    assert result["eventId"] == event and result["canGenerate"]
    assert all(row["quest"].startswith(event) for row in result["rows"])
    assert tables == original


def routes_fixture(tmp_path, monkeypatch):
    source = SimpleNamespace(version="1.4.10", view=SimpleNamespace(verify=lambda: None))
    routes = mode_routes.ModeRoutes(SimpleNamespace(source=source,
        ops=SimpleNamespace(store=DraftStore(tmp_path / "drafts"))))
    monkeypatch.setattr(mode_routes, "freshness", lambda _: {"latest": source.version})
    return routes


@pytest.mark.parametrize("payload,event", [({"seed": 7}, "700099"),
                                         ({"seed": 7, "eventId": "700100"}, "700100")])
def test_payload_compatibility_and_no_preview_writes(tmp_path, monkeypatch, payload, event):
    routes = routes_fixture(tmp_path, monkeypatch)
    calls = []
    def preview(loader, seed, event_id, **kwargs):
        calls.append((seed, event_id))
        return {"ok": True, "canGenerate": True, "blockers": [], "files": {"fixture.bin": b"new"}}
    monkeypatch.setattr(mode_rogue, "preview", preview)
    response = json.loads(routes.edit({}, {"payload": payload}, "rogue", "preview").body)
    assert calls == [(7, event)] and response["canGenerate"]
    assert not routes.store.root.exists()
    with pytest.raises(DraftError, match="只接受"):
        routes.compute("rogue", {**payload, "apply": True})


def test_ex_delivery_rechecks_freshness_and_saved_output(tmp_path, monkeypatch):
    routes = routes_fixture(tmp_path, monkeypatch)
    content = [b"first"]
    monkeypatch.setattr(mode_rogue, "preview", lambda *args, **kwargs: {
        "ok": True, "canGenerate": True, "blockers": [], "files": {"fixture.bin": content[0]}})
    payload = {"seed": 7, "eventId": "700100"}
    routes.edit({}, {"payload": payload, "revision": 0}, "rogue", "save")
    content[0] = b"changed compiler result"
    with pytest.raises(DraftError, match="构建结果与已保存预览不一致"):
        routes.deliveries.compile_delivery("rogue", from_version="1.4.10")
    monkeypatch.setattr(mode_routes, "freshness", lambda _: {"latest": "1.4.11"})
    with pytest.raises(DraftError, match="新鲜链尾"):
        routes.deliveries.compile_delivery("rogue", from_version="1.4.10")
    with pytest.raises(DraftError, match="来源版本必须"):
        routes.deliveries.compile_delivery("rogue", from_version="1.4.9")


def test_ex_overlay_preserves_normal_graph_numeric_phases_and_standard_resources(monkeypatch):
    import wf_share_update_codec as codec
    from wf.studio import mode_rogue_overlay as overlay
    auxiliary = "master/battle/test_phase.orderedmap"
    sphere = b.SPHERE_SPECS["thunder_sphere"]["logical"]
    parent = [""] * 221
    parent[123] = "1234000000"
    resource = "battle/enemy/boss/mod_abyss_ex/standard_r2_1.esdl.amf3.deflate"
    base = resource.removesuffix(".esdl.amf3.deflate")
    normal, ex = tower("700099", "normal_"), tower("700100", "mod_abyss_ex_f")
    before = {b.Q_QUEST: {"700099": normal, "700100": ex},
              b.FIELD_DATA_T: {"normal_1": "normal terrain", "mod_abyss_ex_f1": "old EX terrain"},
              b.STANDARD_BOSS: {"normal_boss": "unchanged", "mod_abyss_ex_standard2": base},
              b.GENERAL_BOSS: {"mod_rogue_boss1": "normal boss", "mod_abyss_ex_boss1": "old EX boss"},
              auxiliary: {"1234000000": "old phase"},
              sphere: {"mod_abyss_ex_thunder_sphere1": {"80": b.join(parent, False)}}}
    tables = copy.deepcopy(before)
    tables[b.Q_QUEST]["700099"]["1"] = "must not reach ordinary tower"
    tables[b.FIELD_DATA_T]["mod_abyss_ex_f1"] = "mod_abyss_ex_boss1,mod_abyss_ex_thunder_sphere1"
    tables[b.GENERAL_BOSS]["mod_abyss_ex_boss1"] = "new EX boss,1234000000"
    tables[auxiliary]["1234000000"] = "new phase"
    raw = {key: q.build_node(value) for key, value in before.items()}
    raw[resource] = b"old standard DSL"
    def read(logical):
        if logical not in raw:
            raise FileNotFoundError(logical)
        return raw[logical]
    observed = []
    def validate(rows, final, builder):
        assert builder.EVENT_ID == "700100" and builder.BUILD_MODE == "ex"
        pointer = next(v for k, v in final[b.STANDARD_BOSS].items() if "_studio_" in k)
        assert builder.q.store_path(pointer + ".esdl.amf3.deflate").read_bytes() == b"new standard DSL"
        observed.append(rows)
        return []
    monkeypatch.setattr(overlay, "validate_candidate_references", validate)
    result = overlay.retain_and_namespace(read, {"eventId": "700100",
        "rebuiltKeys": {b.FIELD_DATA_T: ["mod_abyss_ex_f1"],
                        b.GENERAL_BOSS: ["mod_abyss_ex_boss1"],
                        b.STANDARD_BOSS: ["mod_abyss_ex_standard2"], auxiliary: ["1234000000"],
                        sphere: ["mod_abyss_ex_thunder_sphere1"]},
        "files": {**{key: q.build_node(value) for key, value in tables.items()}, resource: b"new standard DSL"}})
    built = {logical: q.parse_node(value) for logical, value in result["files"].items()
             if logical.endswith(".orderedmap")}
    assert built[b.Q_QUEST]["700099"] == normal
    assert codec.unpack(result["files"][b.Q_QUEST])["700099"] == codec.unpack(raw[b.Q_QUEST])["700099"]
    assert built[b.GENERAL_BOSS]["mod_rogue_boss1"] == "normal boss"
    assert built[b.GENERAL_BOSS]["mod_abyss_ex_boss1"] == "old EX boss"
    assert built[auxiliary]["1234000000"] == "old phase"
    fresh_id = next(key for key in built[auxiliary] if key != "1234000000")
    assert fresh_id.isdigit() and 0 < int(fresh_id) <= 2**31 - 1
    fresh_parent = next(value for key, value in built[sphere].items() if "_studio_" in key)
    assert b.cells(fresh_parent["80"])[123] == fresh_id
    # A coincidentally equal HP/stat value is not a phase reference.
    assert any(value == "new EX boss,1234000000" for value in built[b.GENERAL_BOSS].values())
    assert resource not in result["files"]
    assert any(logical.startswith(base + "_studio_") for logical in result["files"])
    assert raw[resource] == b"old standard DSL" and observed
