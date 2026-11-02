"""Offline regression tests for E-batch review fixes (defects 1-6 + date column validation).

No test in this module depends on local machine game data, real servers, or APKs.
"""
from __future__ import annotations

import copy
import json
from types import SimpleNamespace

import pytest
import wf_quest_lib as codec

from test_studio_deliver_bridge import case as bridge_case
from wf.boss.scene import compile_scene
from wf.boss.scene_allocate import allocate_scene, delivered_event_ids
from wf.boss.scene_clone import clone_scene
from wf.boss.scene_import import GBS, TABLES, import_hell_pumpkin
from wf.boss.scene_server import CONTINUE_COST, FILES, server_candidate
from wf.boss.scene_server_projection import RARE, SCORE
from wf.boss.scene_spec import materialize, validate_spec
from wf.boss.scene_types import AE, AQ, BGM_GROUP, CAS, CONTINUE_PREFIX, ITEM, SHOP
from wf.boss.schema import iter_leaves, parse_rows
from wf.deliver.changeset import member_name, sha256
from wf.deliver.key_guard import check_shared_keys
from wf.studio.drafts import DraftError, DraftStore
from wf.studio.opening_chain import source_edges
from wf.studio.scene_routes import SceneRoutes
from wf.studio.source import StudioSource
from wf.tools.boss.five_boss_v2 import encode_dsl


def _csv(cells) -> str:
    return ",".join(map(str, cells)) + "\n"


def _put_server(root, name: str, value) -> None:
    path = root / "assets" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _action_dsl(command: list) -> list:
    return ["ActionDsl", 1, ["None"], False, False, False, False, False, False, False, 0,
            ["Block", [["Command", command]]]]


@pytest.fixture
def pumpkin_env(tmp_path):
    """Realistic 5-tier synthetic Hell Pumpkin view + server mirror, 100% offline."""
    ae_row = ["(None)"] * 28
    ae_row[0] = "mod_hell_pumpkin"
    ae_row[1] = "(None)"
    ae_row[2] = "地狱南瓜"
    ae_row[3] = ""
    ae_row[24] = "2000-01-01 00:00:00"
    ae_row[25] = "(None)"
    ae_row[26] = "(None)"

    other_ae = list(ae_row)
    other_ae[0] = "existing_advent_01"
    other_ae[2] = "既有活动"

    aq_tree = {}
    cas_tree = {"unrelated_ability_text": "keep\n"}
    server_quests = {}
    server_cc = {}
    for idx in range(1, 6):
        qid = f"30009700{idx}"
        row = ["(None)"] * 132
        for col, val in {
            0: qid, 2: f"南瓜第{idx}档", 4: 31,
            5: "2000-01-01 00:00:00", 6: "(None)",
            75: 0, 76: "3000971", 77: 32, 78: 0,
            90: 816, 91: 621, 92: 426, 93: 270,
            97: 3, 98: 4, 99: 47, 100: 117,
            105: 1, 108: 1, 112: 100, 113: 5,
            115: "mod_hp_fd", 116: "advent_hw20_battle", 117: 600,
        }.items():
            row[col] = str(val)
        aq_tree[str(idx)] = _csv(row)
        cas_tree[CONTINUE_PREFIX + qid] = "10000320:1\n"
        server_quests[qid] = {
            "name": f"南瓜第{idx}档", "clearRewardId": 31,
            "scoreRewardGroupId": 3000971, "element": 3000971, "sPlusRewardId": 32,
            "bRankTime": 816000, "aRankTime": 621000, "sRankTime": 426000, "sPlusRankTime": 270000,
            "rankPointReward": 3, "characterExpReward": 4, "manaReward": 47, "poolExpReward": 117,
        }
        server_cc[qid] = {"item_id": 10000320, "amount": 1}

    shop_row = ["(None)"] * 51
    for col, val in {
        0: 0, 1: 300097, 18: 10009701, 19: 50,
        26: "2000-01-01 00:00:00", 27: "(None)", 29: 5,
        32: 0, 33: 10009701, 34: 1,
    }.items():
        shop_row[col] = str(val)

    item_candy = ["(None)"] * 24
    item_candy[0], item_candy[1], item_candy[2] = "mod_hp_candy", "10009701", "万圣糖果"
    item_candy[19], item_candy[20] = "2000-01-01 00:00:00", "(None)"

    item_bead = list(item_candy)
    item_bead[0], item_bead[1], item_bead[2] = "continue_ticket", "10000320", "续战券"

    zone_row = ["(None)"] * 36
    zone_row[23], zone_row[24], zone_row[25], zone_row[26] = "1", "mod_hp_boss", "1", "mod_hp_boss"

    gb_row = ["(None)"] * 46
    gb_row[41], gb_row[42] = "p1", "mod_hp_routine"

    gbs_row = ["(None)"] * 53
    gbs_row[22], gbs_row[23], gbs_row[49] = "0", "12", "(None)"

    terrain_logical = "battle/terrain/mod/hell_pumpkin/hp_arena"
    action_logical = "battle/action/enemy/action/mod/hell_pumpkin/hp_bgm_p1.action.dsl.amf3.deflate"
    terrain_obj = {
        "layers": [{
            "type": "objectgroup", "name": "0",
            "objects": [
                {"id": 1, "type": "BOUNDS", "x": 0, "y": 0, "width": 160, "height": 280},
                {"id": 2, "type": "WALL", "x": 0, "y": 0, "width": 10, "height": 280},
                {"id": 3, "type": "RETURN_LANE_GUIDE", "x": 150, "y": 0, "width": 10, "height": 280},
                *[{"id": 10 + i, "type": "COFFIN", "x": 10 * i, "y": 200, "width": 10, "height": 10}
                  for i in range(9)],
                {"id": 99, "type": "CUSTOM_POSITION", "name": "p1", "x": 80, "y": 80, "width": 10, "height": 10},
            ],
        }]
    }

    tree_map = {logical: {"unrelated": "0\n"} for logical in TABLES}
    tree_map.update({
        AE: {"300097": _csv(ae_row), "300050": _csv(other_ae)},
        AQ: {"300097": aq_tree},
        CAS: cas_tree,
        BGM_GROUP: {
            "advent_hw20_battle": "advent_hw20_battle,bgm/hp_boss\n",
            "advent_alt_battle": "advent_alt_battle,bgm/hp_boss\n",
        },
        "master/asset/bgm_asset.orderedmap": {"bgm/hp_boss": "0.32,0\n", "bgm/hp_p1": "0.32,0\n"},
        SHOP: {"9730001": _csv(shop_row)},
        ITEM: {"10009701": _csv(item_candy), "10000320": _csv(item_bead)},
        SCORE: {"3000971": {"1": "pool,0,0,10009701,10,1000,,\n", "2": "pool,1,,,,,3000972,0.1\n"}},
        RARE: {"3000972": {"1": "rare,0,10009701,5,1,true\n"}},
        "master/battle/field_data.orderedmap": {
            "mod_hp_fd": _csv(["mod_hp_field", terrain_logical, "mod_hp_zone", f"'{action_logical}'"]),
        },
        "master/battle/field.orderedmap": {"mod_hp_field": "bg/pumpkin,0\n"},
        "master/battle/zone.orderedmap": {"mod_hp_zone": {"0": _csv(zone_row)}},
        "master/battle/boss/general_boss.orderedmap": {"mod_hp_boss": {"200": _csv(gb_row)}},
        GBS: {"mod_hp_routine": {"1": {"idle": _csv(gbs_row)}}},
    })

    raw_files = {logical: codec.build_node(tree) for logical, tree in tree_map.items()}
    raw_files[terrain_logical + ".amf3.deflate"] = encode_dsl(terrain_obj)
    raw_files[action_logical] = encode_dsl(_action_dsl(["ChangeBgm", "bgm/hp_p1", ["Immediate"]]))

    def loader(logical: str) -> bytes:
        if logical not in raw_files:
            raise FileNotFoundError(logical)
        return raw_files[logical]

    server_dir = tmp_path / "server"
    server_docs = {
        "advent_event_quest.json": server_quests,
        "score_reward_cnmod.json": {"3000971": [
            {"position": 1, "name": "", "type": 0, "reward_type": 0, "id": 10009701, "count": 10, "field5": 1000},
            {"position": 2, "name": "", "type": 1, "id": 3000972, "rarity": 0.095},
        ]},
        "rare_score_reward_cnmod.json": {"3000972": [{"name": "", "type": 0, "id": 10009701, "count": 5, "rarity": 1.0}]},
        "event_item_shop.json": {"0": {"300097": {"9730001": {
            "costs": [{"id": 10009701, "amount": 50}],
            "rewards": [{"type": 0, "id": 10009701, "count": 1}],
            "availableFrom": "2000-01-01 00:00:00", "availableUntil": None, "stock": 5,
        }}}},
        "event_item_shop_id_map.json": {"9730001": {"eventType": 0, "eventId": 300097}},
        "item_ids.json": [10000320, 10009701],
        "item_lookup_cnmod.json": {"10009701": "万圣糖果", "10000320": "续战券"},
    }
    for name, doc in server_docs.items():
        _put_server(server_dir, name, doc)

    return SimpleNamespace(
        version="1.4.351",
        raw_files=raw_files,
        tree_map=tree_map,
        loader=loader,
        server_dir=server_dir,
        server_cc=server_cc,
    )


def _set_setting(group_settings: list[dict], setting_id: str, value) -> None:
    target = next(item for item in group_settings if item["id"] == setting_id)
    target["value"] = value


# -- 缺陷 1：五档 BGM c116 校验 battle_bgm_group -----------------------------
def test_scene_tier_bgm_c116_must_exist_in_battle_bgm_group(pumpkin_env):
    spec = import_hell_pumpkin(pumpkin_env.loader, pumpkin_env.version)

    good = copy.deepcopy(spec)
    _set_setting(good["tiers"][0]["settings"], "bgm", "advent_alt_battle")
    compiled_ok = compile_scene(pumpkin_env.loader, good, server_dir=pumpkin_env.server_dir)
    assert compiled_ok["ok"] is True
    assert compiled_ok["canGenerate"] is True

    bad = copy.deepcopy(spec)
    _set_setting(bad["tiers"][0]["settings"], "bgm", "no_such_bgm_prefix")
    compiled_bad = compile_scene(pumpkin_env.loader, bad, server_dir=pumpkin_env.server_dir)
    assert compiled_bad["ok"] is False
    assert compiled_bad["canGenerate"] is False
    spec_check = next(check for check in compiled_bad["checks"] if check["rule"] == "scene.spec")
    assert spec_check["blocking"] is True
    assert any("battle_bgm_group" in issue and "no_such_bgm_prefix" in issue for issue in spec_check["issues"])


# -- 缺陷 2：continue_cost 导入、克隆、服务端同步与缺失待验证 ----------------
def test_scene_continue_cost_import_clone_and_server_sync_with_json(pumpkin_env):
    _put_server(pumpkin_env.server_dir, CONTINUE_COST, pumpkin_env.server_cc)
    spec = import_hell_pumpkin(pumpkin_env.loader, pumpkin_env.version)
    cas_table = next(table for table in spec["tables"] if table["logical"] == CAS)
    assert {tuple(entry["path"]) for entry in cas_table["entries"]} == {
        (f"continue_cost_30009700{i}",) for i in range(1, 6)
    }
    for tier in spec["tiers"]:
        cc_setting = next(item for item in tier["settings"] if item["id"] == "continue-cost")
        assert cc_setting["value"] == "10000320:1"

    cloned = clone_scene(spec, "300011", "万圣复刻")
    cloned_cas = next(table for table in cloned["tables"] if table["logical"] == CAS)
    assert {tuple(entry["path"]) for entry in cloned_cas["entries"]} == {
        (f"continue_cost_30001100{i}",) for i in range(1, 6)
    }
    declared = {(t["logical"], tuple(t["path"])) for t in cloned["creation"]["tableTargets"]}
    for i in range(1, 6):
        assert (CAS, (f"continue_cost_30001100{i}",)) in declared

    tampered = copy.deepcopy(cloned)
    tampered["creation"]["tableTargets"] = [
        t for t in tampered["creation"]["tableTargets"] if t["logical"] != CAS
    ]
    with pytest.raises(ValueError, match="表键防撞"):
        validate_spec(tampered)

    _set_setting(cloned["tiers"][0]["settings"], "continue-cost", "10000320:3")
    result = compile_scene(pumpkin_env.loader, cloned, server_dir=pumpkin_env.server_dir)
    assert result["ok"] is True and result["canGenerate"] is True
    cc_check = next(check for check in result["checks"] if check["rule"] == "scene.server-continue-cost")
    assert cc_check["status"] == "满足" and cc_check["blocking"] is False

    cc_json = json.loads(result["servers"]["assets/continue_cost.json"])
    assert cc_json["300097001"] == {"item_id": 10000320, "amount": 1}
    assert cc_json["300011001"] == {"item_id": 10000320, "amount": 3}
    for i in range(2, 6):
        assert cc_json[f"30001100{i}"] == {"item_id": 10000320, "amount": 1}

    guard_ok = check_shared_keys({}, {"assets/continue_cost.json": result["servers"]["assets/continue_cost.json"]},
                                 server_dir=pumpkin_env.server_dir, protected={})
    assert guard_ok["errors"] == []
    assert "assets/continue_cost.json" in guard_ok["server_targets"]
    guard_lost = check_shared_keys({}, {"assets/continue_cost.json": b'{"300011001":{"item_id":10000320,"amount":1}}'},
                                   server_dir=pumpkin_env.server_dir, protected={})
    assert any("lost baseline JSON keys" in err for err in guard_lost["errors"])


def test_scene_continue_cost_missing_server_json_marks_pending_without_blocking(pumpkin_env):
    assert not (pumpkin_env.server_dir / "assets" / CONTINUE_COST).exists()
    spec = import_hell_pumpkin(pumpkin_env.loader, pumpkin_env.version)
    cloned = clone_scene(spec, "300011", "无续战JSON环境")
    result = compile_scene(pumpkin_env.loader, cloned, server_dir=pumpkin_env.server_dir)
    assert result["ok"] is True
    assert result["canGenerate"] is True
    assert "assets/continue_cost.json" not in result["servers"]
    cc_check = next(check for check in result["checks"] if check["rule"] == "scene.server-continue-cost")
    assert cc_check["status"] == "待验证"
    assert cc_check["blocking"] is False


@pytest.mark.parametrize("bad_value", ["invalid", "0:1", "10000320:0", "-1:1", "10000320:1:2"])
def test_scene_continue_cost_rejects_malformed_format_and_unknown_item(pumpkin_env, bad_value):
    spec = import_hell_pumpkin(pumpkin_env.loader, pumpkin_env.version)
    _set_setting(spec["tiers"][0]["settings"], "continue-cost", bad_value)
    with pytest.raises(ValueError, match="续战消耗"):
        validate_spec(spec)

    spec_unknown_item = import_hell_pumpkin(pumpkin_env.loader, pumpkin_env.version)
    _set_setting(spec_unknown_item["tiers"][0]["settings"], "continue-cost", "99999999:1")
    result = compile_scene(pumpkin_env.loader, spec_unknown_item, server_dir=pumpkin_env.server_dir)
    assert result["canGenerate"] is False
    server_check = next(check for check in result["checks"] if check["rule"] == "scene.server")
    assert server_check["blocking"] is True and "续战消耗道具" in server_check["message"]


# -- 缺陷 3 & 4：分槽草稿、旧单槽迁移、交付命名带 event ID 与扫描已出包 ------
def _routes_for_env(tmp_path, monkeypatch, pumpkin_env):
    profile = tmp_path / "profile.json"
    profile.write_text("{}", encoding="utf8")
    monkeypatch.setenv("WF_PATHS_PROFILE", str(profile))
    bridge_dir = tmp_path / "bridge"
    bridge_dir.mkdir(parents=True, exist_ok=True)
    _, _, view, _ = bridge_case.__wrapped__(bridge_dir, monkeypatch)
    view.tip = pumpkin_env.version
    view.base_version = pumpkin_env.version
    monkeypatch.setattr(view, "verify", lambda: None)
    members = {member_name("common", logical): raw for logical, raw in pumpkin_env.raw_files.items()}
    monkeypatch.setattr(view, "read_member", lambda name: (
        (members[name], "fixture") if name in members else (_ for _ in ()).throw(FileNotFoundError(name))
    ))
    monkeypatch.setattr("wf.studio.scene_routes.freshness",
                        lambda _source: {"latest": pumpkin_env.version, "stale": False})
    source = StudioSource(view)
    app = SimpleNamespace(source=source, ops=SimpleNamespace(store=DraftStore(tmp_path / "drafts")))
    routes = SceneRoutes(app, server_dir=pumpkin_env.server_dir)
    routes.deliveries.root = tmp_path / "deliveries" / "scenes"
    return routes


def test_scene_multislot_drafts_preserve_mother_and_clones_independently(tmp_path, monkeypatch, pumpkin_env):
    routes = _routes_for_env(tmp_path, monkeypatch, pumpkin_env)
    initial = json.loads(routes.read({}, "hell-pumpkin").body)
    mother = copy.deepcopy(initial["spec"])

    # Save mother 3 times (revisions 1 -> 2 -> 3) with edited trial thresholds.
    for rev, threshold in enumerate((15, 18, 21)):
        mother["trials"][0]["value"] = str(threshold)
        saved = json.loads(routes.edit({}, {"payload": mother, "revision": rev}, "hell-pumpkin", "save").body)
        assert saved["draft"]["revision"] == rev + 1
        assert saved["slot"] == "hell-pumpkin"

    # Clone 300001 and save to its own slot scene-300001 without touching mother rev 3.
    clone_1 = json.loads(routes.clone({}, {"payload": initial["spec"], "name": "克隆一"}, "hell-pumpkin").body)
    assert clone_1["slot"] == "scene-300001"
    saved_c1 = json.loads(routes.edit({}, {"payload": clone_1["payload"], "revision": 0}, "scene-300001", "save").body)
    assert saved_c1["draft"]["revision"] == 1

    # Clone again: must skip 300001 (saved in scene-300001) and allocate 300002.
    clone_2 = json.loads(routes.clone({}, {"payload": initial["spec"], "name": "克隆二"}, "hell-pumpkin").body)
    assert clone_2["allocation"]["eventId"] == "300002"
    assert clone_2["slot"] == "scene-300002"
    saved_c2 = json.loads(routes.edit({}, {"payload": clone_2["payload"], "revision": 0}, "scene-300002", "save").body)
    assert saved_c2["draft"]["revision"] == 1

    # Mother revision 3 and its trial edit (21) remain completely intact!
    mother_back = json.loads(routes.read({}, "hell-pumpkin").body)
    assert mother_back["draft"]["revision"] == 3
    assert mother_back["payload"]["trials"][0]["value"] == "21"
    assert [item["slot"] for item in mother_back["drafts"]] == ["hell-pumpkin", "scene-300001", "scene-300002"]

    # Cross-slot overwrite attempts are rejected fail-closed.
    with pytest.raises(DraftError, match="不一致"):
        routes.edit({}, {"payload": clone_1["payload"], "revision": 3}, "hell-pumpkin", "save")
    with pytest.raises(DraftError, match="不一致"):
        routes.edit({}, {"payload": mother, "revision": 1}, "scene-300001", "save")


def test_scene_migrates_legacy_single_slot_clone_draft_without_data_loss(tmp_path, monkeypatch, pumpkin_env):
    routes = _routes_for_env(tmp_path, monkeypatch, pumpkin_env)
    mother_spec = import_hell_pumpkin(pumpkin_env.loader, pumpkin_env.version)
    legacy_clone = clone_scene(mother_spec, "300011", "旧单槽克隆")
    legacy_folder = routes.store.root / "hell-pumpkin"
    legacy_folder.mkdir(parents=True, exist_ok=True)
    legacy_doc = {
        "schema": "wf-studio-mode/1", "subjectKind": "mode",
        "characterId": "hell-pumpkin", "code": "hell-pumpkin",
        "baseView": pumpkin_env.version, "createdAt": "2026-11-01T00:00:00Z",
        "updatedAt": "2026-11-01T00:00:00Z", "savedAt": "2026-11-01T00:00:00Z",
        "revision": 4, "savedRevision": 4,
        "payload": legacy_clone, "inputs": {}, "preview": {"ok": True}, "changes": [],
    }
    (legacy_folder / "changeset.json").write_text(json.dumps(legacy_doc, ensure_ascii=False), encoding="utf-8")

    # Reading hell-pumpkin migrates legacy clone to scene-300011 without losing revision 4.
    mother_read = json.loads(routes.read({}, "hell-pumpkin").body)
    assert mother_read["migratedSlot"] == "scene-300011"
    assert mother_read["draft"] is None
    assert mother_read["payload"]["id"] == "hell-pumpkin"
    assert not (legacy_folder / "changeset.json").exists()

    migrated_read = json.loads(routes.read({}, "scene-300011").body)
    assert migrated_read["draft"]["revision"] == 4
    assert migrated_read["draft"]["characterId"] == "scene-300011"
    assert migrated_read["payload"]["name"] == "旧单槽克隆"
    assert migrated_read["payload"]["event"]["id"] == "300011"

    # Edge case: if target slot already had a newer draft, legacy file is backed up and neither is lost.
    (legacy_folder / "changeset.json").write_text(
        json.dumps({**legacy_doc, "revision": 2, "payload": {**legacy_clone, "name": "早期单槽副本"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    again = routes.store.load("scene-300011")
    assert again["revision"] == 4 and again["payload"]["name"] == "旧单槽克隆"
    backup = json.loads((routes.store.root / "scene-300011" / "legacy-hell-pumpkin-rev2.json").read_text("utf-8"))
    assert backup["payload"]["name"] == "早期单槽副本"


def test_scene_allocate_scans_deliveries_and_delivery_name_includes_event_id(tmp_path, monkeypatch, pumpkin_env):
    routes = _routes_for_env(tmp_path, monkeypatch, pumpkin_env)
    assert routes.deliveries.output_identity("hell-pumpkin") == "hell-pumpkin-300097"
    assert routes.deliveries.output_identity("scene-300011") == "scene-300011"

    # Simulate build naming via DeliverRoutes.build (with compile_delivery stubbed to verify exact output directory).
    built_dirs = []
    monkeypatch.setattr(routes.deliveries, "compile_delivery", lambda cid, **kw: (
        built_dirs.append(kw["out"]), {"ok": True, "characterId": cid, "from": kw["from_version"], "to": kw["to_version"]}
    )[1])
    monkeypatch.setattr("wf.caps.profiles.resolve_client", lambda *a, **k: (None, "default"))
    monkeypatch.setattr("wf.studio.delivery_safety.resolve_apks", lambda *a, **k: [])

    mother_job = json.loads(routes.deliveries.build({}, {"from": "1.4.351", "to": "1.4.352"}, "hell-pumpkin").body)
    assert mother_job["name"].startswith("hell-pumpkin-300097-1.4.351-to-1.4.352-")
    clone_job = json.loads(routes.deliveries.build({}, {"from": "1.4.351", "to": "1.4.352"}, "scene-300001").body)
    assert clone_job["name"].startswith("scene-300001-1.4.351-to-1.4.352-")

    # Materialize unchained delivery directories (one new-format scene-300001-..., one legacy hell-pumpkin-... for 300002).
    d1 = routes.deliveries.root / clone_job["name"] / "inputs"
    d1.mkdir(parents=True, exist_ok=True)
    d2 = routes.deliveries.root / "hell-pumpkin-1.4.351-to-1.4.352-20261101-120000" / "inputs"
    d2.mkdir(parents=True, exist_ok=True)
    (d2 / "draft.json").write_text(json.dumps({
        "payload": {"id": "scene-300002", "event": {"id": "300002"}, "creation": {"sourceEvent": "300097"}},
    }), encoding="utf-8")

    assert delivered_event_ids(routes.deliveries.root) == {"300001", "300002"}

    # Even with NO saved clone drafts in SceneStore and after saving a mother edit, clone skips 300001 & 300002 -> 300003!
    mother_spec = import_hell_pumpkin(pumpkin_env.loader, pumpkin_env.version)
    mother_spec["trials"][0]["value"] = "16"
    routes.edit({}, {"payload": mother_spec, "revision": 0}, "hell-pumpkin", "save")
    allocated = json.loads(routes.clone({}, {"payload": mother_spec, "name": "跳过已出包"}, "hell-pumpkin").body)
    assert allocated["allocation"]["eventId"] == "300003"
    assert allocated["slot"] == "scene-300003"


# -- 缺陷 5：opening_chain local_test_only: false 不误标 ----------------------
def test_opening_source_edges_distinguishes_false_from_true(tmp_path):
    archive = tmp_path / "pinball-1.4.8-1.4.9-1-a.zip"
    archive.write_bytes(b"zip-a")
    archive_b = tmp_path / "pinball-1.4.9-1.4.10-1-b.zip"
    archive_b.write_bytes(b"zip-b")
    view = SimpleNamespace(
        base_version="1.4.8",
        edges=[
            {"depends_on": "1.4.8", "version": "1.4.9", "names": [archive.name], "local_test_only": False},
            {"depends_on": "1.4.9", "version": "1.4.10", "names": [archive_b.name], "local_test_only": True},
        ],
        zips=[archive, archive_b],
        zip_records=[
            {"name": archive.name, "sha256": sha256(b"zip-a")},
            {"name": archive_b.name, "sha256": sha256(b"zip-b")},
        ],
        extra_zips=[],
    )
    edges, _ = source_edges(SimpleNamespace(view=view, version="1.4.10"))
    assert edges[0]["localTestOnly"] is False
    assert edges[1]["localTestOnly"] is True


# -- 缺陷 6：event-code 绑定 c0，校验 c1 int 并同步 c0 防撞 --------------------
def test_scene_event_code_binds_c0_validates_c1_and_blocks_c0_collision(pumpkin_env):
    spec = import_hell_pumpkin(pumpkin_env.loader, pumpkin_env.version)
    code_setting = next(item for item in spec["event"]["settings"] if item["id"] == "event-code")
    assert code_setting["value"] == "mod_hell_pumpkin"
    assert code_setting["bindings"] == [{"table": AE, "path": ["300097"], "column": 0}]

    edited = copy.deepcopy(spec)
    _set_setting(edited["event"]["settings"], "event-code", "mod_hell_pumpkin_v2")
    tables, _ = materialize(edited)
    ae_cells = parse_rows(tables[AE][("300097",)])[0]
    assert ae_cells[0] == "mod_hell_pumpkin_v2"
    assert ae_cells[1] == "(None)"  # c1 (original) is untouched!

    for bad_code in ("(None)", "", "has space", "bad/slash"):
        broken = copy.deepcopy(spec)
        _set_setting(broken["event"]["settings"], "event-code", bad_code)
        with pytest.raises(ValueError, match="活动代号"):
            validate_spec(broken)

    # Colliding c0 with another existing advent_event row blocks compilation.
    colliding = clone_scene(spec, "300011", "代号冲突测试")
    _set_setting(colliding["event"]["settings"], "event-code", "existing_advent_01")
    compiled_collision = compile_scene(pumpkin_env.loader, colliding, server_dir=pumpkin_env.server_dir)
    assert compiled_collision["ok"] is False and compiled_collision["canGenerate"] is False
    spec_issues = next(c for c in compiled_collision["checks"] if c["rule"] == "scene.spec")["issues"]
    assert any("冲突" in issue and "existing_advent_01" in issue for issue in spec_issues)

    # Non-int c1 (original) blocks both via binding and via raw CSV table mutation.
    bad_c1_raw = copy.deepcopy(spec)
    ae_table = next(t for t in bad_c1_raw["tables"] if t["logical"] == AE)
    row = parse_rows(ae_table["entries"][0]["value"])[0]
    row[1] = "not_an_integer"
    ae_table["entries"][0]["value"] = _csv(row)
    compiled_bad_c1 = compile_scene(pumpkin_env.loader, bad_c1_raw, server_dir=pumpkin_env.server_dir)
    assert compiled_bad_c1["ok"] is False and compiled_bad_c1["canGenerate"] is False
    assert any("original" in issue for issue in next(c for c in compiled_bad_c1["checks"] if c["rule"] == "scene.spec")["issues"])

    # allocate_scene also skips candidate event IDs whose generated c0 is already used by another event row.
    occupied_ae = copy.deepcopy(pumpkin_env.tree_map[AE])
    clash_row = parse_rows(occupied_ae["300050"])[0]
    clash_row[0] = "mod_studio_scene_300001"
    occupied_ae["300050"] = _csv(clash_row)
    custom_raw = {**pumpkin_env.raw_files, AE: codec.build_node(occupied_ae)}
    allocated = allocate_scene(spec, lambda p: custom_raw[p] if p in custom_raw else (_ for _ in ()).throw(FileNotFoundError(p)))
    assert allocated["event"]["id"] == "300002"


# -- 存疑 1：日期列类型校验（非法日期与倒置时间窗阻断） ------------------------
@pytest.mark.parametrize("bad_date", [
    "not-a-date",
    "2000-01-01",
    "2026/10/31 00:00:00",
    "2026-02-29 00:00:00",
    "1969-12-31 23:59:59",
    "(None)",
])
def test_scene_shop_date_columns_block_invalid_dates_before_client_or_server(pumpkin_env, bad_date):
    spec = import_hell_pumpkin(pumpkin_env.loader, pumpkin_env.version)
    _set_setting(spec["shops"][0]["settings"], "c26", bad_date)
    with pytest.raises(ValueError, match="日期|年份"):
        validate_spec(spec)

    # Also verify server_candidate directly rejects raw shop table mutations so bad dates never enter availableFrom.
    raw_spec = import_hell_pumpkin(pumpkin_env.loader, pumpkin_env.version)
    raw_spec["shops"][0]["settings"] = []
    shop_table = next(t for t in raw_spec["tables"] if t["logical"] == SHOP)
    cells = parse_rows(shop_table["entries"][0]["value"])[0]
    cells[26] = bad_date
    shop_table["entries"][0]["value"] = _csv(cells)
    result = compile_scene(pumpkin_env.loader, raw_spec, server_dir=pumpkin_env.server_dir)
    assert result["ok"] is False and result["canGenerate"] is False
    assert result["servers"] == {}


def test_scene_date_columns_validate_windows_and_all_advent_tables(pumpkin_env):
    spec = import_hell_pumpkin(pumpkin_env.loader, pumpkin_env.version)

    # Reversed shop window (end_time c27 < start_time c26) is rejected.
    reversed_shop = copy.deepcopy(spec)
    _set_setting(reversed_shop["shops"][0]["settings"], "c26", "2026-11-10 00:00:00")
    _set_setting(reversed_shop["shops"][0]["settings"], "c27", "2026-11-01 00:00:00")
    with pytest.raises(ValueError, match="结束时间早于开始时间"):
        validate_spec(reversed_shop)

    # Valid explicit shop window compiles cleanly and populates server availableUntil.
    valid_shop = copy.deepcopy(spec)
    _set_setting(valid_shop["shops"][0]["settings"], "c26", "2026-11-01 00:00:00")
    _set_setting(valid_shop["shops"][0]["settings"], "c27", "2026-11-10 23:59:59")
    ok_res = compile_scene(pumpkin_env.loader, valid_shop, server_dir=pumpkin_env.server_dir)
    assert ok_res["ok"] is True and ok_res["canGenerate"] is True
    projected = json.loads(ok_res["servers"]["assets/event_item_shop.json"])["0"]["300097"]["9730001"]
    assert projected["availableFrom"] == "2026-11-01 00:00:00"
    assert projected["availableUntil"] == "2026-11-10 23:59:59"

    # Raw table date corruption in AQ (c5), AE (c3 schedule / c24), and ITEM (c19) all block compile_scene.
    for logical, col, corrupt in (
        (AQ, 5, "bad-quest-start"),
        (AE, 3, "2026-10-31 00:00:00,invalid-schedule-slot"),
        (AE, 24, "2026-13-01 00:00:00"),
        (ITEM, 19, "not-an-item-date"),
    ):
        mutated = copy.deepcopy(spec)
        target_table = next(t for t in mutated["tables"] if t["logical"] == logical)
        cells = parse_rows(target_table["entries"][0]["value"])[0]
        cells[col] = corrupt
        target_table["entries"][0]["value"] = _csv(cells)
        res = compile_scene(pumpkin_env.loader, mutated, server_dir=pumpkin_env.server_dir)
        assert res["ok"] is False and res["canGenerate"] is False, f"{logical} c{col}={corrupt!r} must block"
