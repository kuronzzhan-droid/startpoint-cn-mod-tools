"""深渊回廊内容编辑：导入/无损重建、校验正反例、命令、发布包、试验服应用与回滚（离线夹具）。"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from tests import corridor_fixtures as fx
from wf.studio.corridor import catalog, commands as C, effects, encounters, jsonio, release as R, validate as V
from wf.studio.corridor.layout import RUNTIME_FILES, CorridorConfig
from wf.studio.corridor.routes import CorridorService
from wf.studio.corridor.store import ConflictError, CorridorStore, StoreError
from wf.studio.corridor.trial import Trial, TrialError
from wf.studio.corridor.workspace import import_from_sources, option_key


@pytest.fixture
def env(tmp_path):
    paths = fx.build(tmp_path / "src")
    cfg = CorridorConfig(paths["data"], paths["proto"], tmp_path / "store")
    service = CorridorService(app=None, config=cfg)
    service.import_source({}, {})
    return {"cfg": cfg, "service": service, "store": CorridorStore(cfg.store), "root": tmp_path}


def master_of(cfg):
    return catalog.load_master(cfg.data_dir / "tier_table.json", cfg.data_dir / "rules_v3_metadata.json")


def run(env, *commands):
    service = env["service"]
    ws = service.workspace()
    return service.commands({}, {"revision": ws["revision"], "commands": list(commands)})


def codes(env):
    result = env["service"].validation(env["service"].workspace())
    return {f["code"] for f in result["findings"] if f["severity"] == "block"}, result


# ---------------------------------------------------------------- T-001 / import + rebuild
def test_import_then_compile_without_changes_is_byte_identical(env):
    ws = env["service"].workspace()
    files = R.compile_runtime(ws, env["store"].base_raw())
    for spec in RUNTIME_FILES:
        assert files[spec.release] == env["cfg"].source_path(spec).read_bytes(), spec.name
    blockers, result = codes(env)
    assert blockers == set(), result["findings"]


def test_number_shape_and_key_order_survive_a_round_trip_through_the_ui(env):
    # The browser turns 2.0 into 2 and may reorder keys; an unchanged value must not change bytes.
    run(env, {"op": "event.option.update", "event_id": "e004",
              "option_id": env["service"].workspace()["policy"]["event_option_ids"]["e004"][0],
              "effects": [{"type": "gamble_gold", "value": {"lose_multiplier": 0.5, "win_chance": 0.5, "win_multiplier": 2}}]},
        {"op": "relic.update", "relic_id": "r103",
         "effects": [{"type": "combo_recharge_pct", "value": 5, "combo_threshold": 50}]},
        {"op": "rules.set", "path": "/difficulty/profiles/formal/act_targets/0", "value": 1})
    files = R.compile_runtime(env["service"].workspace(), env["store"].base_raw())
    for spec in RUNTIME_FILES:
        assert files[spec.release] == env["cfg"].source_path(spec).read_bytes(), spec.name


def test_legacy_shapes_r006_r007_e002_e006_survive_and_normalize_like_the_server(env):
    ws = env["service"].workspace()
    aliases = effects.relic_aliases(ws["data"]["rules"])
    relics = {r["relic_id"]: r for r in ws["data"]["relics"]}
    assert "effect" in relics["r006"] and "effects" in relics["r007"]
    assert effects.server_relic(relics["r006"], aliases)["effects"] == [{"type": "first_fall_free", "value": 1},
                                                                         {"type": "rest_heal_bonus", "value": -1}]
    assert effects.server_relic(relics["r004"], aliases)["effects"] == [{"type": "shop_discount_pct", "value": 20}]
    events_ = {e["event_id"]: e for e in ws["data"]["events"]}
    settled = effects.server_event(events_["e002"], effects.event_aliases(ws["data"]["rules"]))
    assert settled["ok"] and settled["options"][1][1] == {"type": "gain_weapon", "tier": 2, "element": "preferred"}
    assert effects.server_event(events_["e006"], {})["options"][0][0] == {"type": "fight_elite"}


def test_truncated_master_table_is_a_blocker_not_a_full_table(env):
    path = env["cfg"].data_dir / "tier_table.json"
    path.write_bytes(path.read_bytes()[:-200])
    blockers, result = codes(env)
    assert "B-001" in blockers and any("tier_table.json 不是合法 JSON" in f["message"] for f in result["findings"])


# ---------------------------------------------------------------- schema / registry (T-003, T-010)
def test_effect_and_effects_together_fails_schema(env):
    ws = env["service"].workspace()
    ws["data"]["relics"][0]["effects"] = [{"type": "gold_on_pickup", "value": 1}]
    errors = V.schema_errors(ws)
    assert any(e["pointer"] == "/data/relics/0" for e in errors)


def test_arbitrary_effect_type_is_refused_by_command_and_schema(env):
    with pytest.raises(StoreError, match="未登记的遗物效果类型"):
        run(env, {"op": "relic.update", "relic_id": "r001", "effects": [{"type": "arbitrary_eval", "value": 1}]})
    ws = env["service"].workspace()
    ws["data"]["relics"][0]["effect"] = {"type": "arbitrary_eval", "value": "process.exit()"}
    assert V.schema_errors(ws)
    assert not effects.server_relic(ws["data"]["relics"][0], {})["ok"]


def test_event_effect_the_server_cannot_normalize_blocks(env):
    ws = env["service"].workspace()
    ws["data"]["events"][1]["options"][1]["effects"][1]["value"]["element"] = "any"   # schema allows, server does not
    assert not effects.server_event(ws["data"]["events"][1], {})["ok"]


# ---------------------------------------------------------------- events: reorder keeps meaning (T-005)
def test_option_reorder_follows_stable_ids_and_rebuilds_locale_keys(env):
    ws = env["service"].workspace()
    ids = list(ws["policy"]["event_option_ids"]["e002"])
    zh_before = {ids[i]: ws["data"]["locales"]["zh"][option_key("e002", i)] for i in range(4)}
    en_before = {ids[i]: ws["data"]["locales"]["en"][option_key("e002", i)] for i in range(4)}
    effects_before = {ids[i]: ws["data"]["events"][1]["options"][i]["effects"] for i in range(4)}
    run(env, {"op": "event.option.move", "event_id": "e002", "option_id": ids[3], "to": 0})
    ws = env["service"].workspace()
    new_ids = ws["policy"]["event_option_ids"]["e002"]
    assert new_ids == [ids[3], ids[0], ids[1], ids[2]]
    for i, oid in enumerate(new_ids):
        opt = ws["data"]["events"][1]["options"][i]
        assert opt["label_key"] == option_key("e002", i)
        assert ws["data"]["locales"]["zh"][opt["label_key"]] == zh_before[oid] == opt["label"]
        assert ws["data"]["locales"]["en"][opt["label_key"]] == en_before[oid]
        assert opt["effects"] == effects_before[oid]
    blockers, _ = codes(env)
    assert blockers == set()
    diff = env["service"].diff({}, )
    assert any("选项重排" in line["text"] for line in diff["readable"])


def test_missing_english_option_text_blocks(env):
    run(env, {"op": "locale.set", "key": option_key("e002", 3), "en": ""})
    blockers, result = codes(env)
    assert "B-005" in blockers
    assert any(option_key("e002", 3) in f["message"] for f in result["findings"])


def test_event_create_option_ops_and_delete(env):
    out = run(env, {"op": "event.create", "template": "pay_for_relic", "title_en": "Merchant", "text_en": "Sells relics."})
    eid = out["results"][0]["event_id"]
    assert eid == "e007"
    ws = env["service"].workspace()
    ev = next(e for e in ws["data"]["events"] if e["event_id"] == eid)
    ids = ws["policy"]["event_option_ids"][eid]
    assert len(ids) == len(ev["options"]) == 2
    blockers, _ = codes(env)
    assert "B-005" in blockers  # option English still empty
    run(env, *[{"op": "event.option.update", "event_id": eid, "option_id": oid, "label_en": f"Option {i}"} for i, oid in enumerate(ids)])
    assert codes(env)[0] == set()
    run(env, {"op": "event.option.add", "event_id": eid, "label": "再看看", "label_en": "Look again",
              "effects": [{"type": "gain_gold", "value": 5}], "index": 1})
    ws = env["service"].workspace()
    assert [o["label"] for o in next(e for e in ws["data"]["events"] if e["event_id"] == eid)["options"]][1] == "再看看"
    run(env, {"op": "event.delete", "event_id": eid, "reason": "测试"})
    ws = env["service"].workspace()
    assert eid not in {e["event_id"] for e in ws["data"]["events"]}
    assert not any(k.startswith(f"rogue.event.{eid}.") for k in ws["data"]["locales"]["zh"])
    assert ("event", eid) in {(t["kind"], t["id"]) for t in ws["lifecycle"]["tombstones"]}
    out = run(env, {"op": "event.create", "title_en": "x", "text_en": "y", "options": [{"label": "离开", "label_en": "Leave",
                                                                                       "effects": [{"type": "leave"}]}]})
    assert out["results"][0]["event_id"] == "e008"  # deleted IDs are never reused


def test_server_option_limit_is_enforced(env):
    eid = "e002"
    ws = env["service"].workspace()
    run(env, *[{"op": "event.option.add", "event_id": eid, "label": f"x{i}", "label_en": "x"} for i in range(2)])
    with pytest.raises(StoreError, match="1..6"):
        run(env, {"op": "event.option.add", "event_id": eid, "label": "x7", "label_en": "x"})
    assert len(env["service"].workspace()["data"]["events"][1]["options"]) == 6
    assert ws["revision"] + 1 == env["service"].workspace()["revision"]


# ---------------------------------------------------------------- relics
def test_relic_create_template_ids_and_english_gate(env):
    out = run(env, {"op": "relic.create", "template": "gold_on_pickup"})
    rid = out["results"][0]["relic_id"]
    assert rid == "r121"
    assert "B-005" in codes(env)[0]
    run(env, {"op": "relic.update", "relic_id": rid, "name_en": "Purse", "desc_en": "Gain 50 gold."})
    assert codes(env)[0] == set()
    run(env, {"op": "relic.delete", "relic_id": rid, "reason": "测试"})
    out = run(env, {"op": "relic.create", "template": "max_lives_up", "name_en": "a", "desc_en": "b"})
    assert out["results"][0]["relic_id"] == "r122"
    ws = env["service"].workspace()
    assert "rogue.relic.r121.name" not in ws["data"]["locales"]["zh"]
    assert {"r121", "r122"} <= set(ws["lifecycle"]["reserved_relic_ids"])


def test_relic_value_edit_changes_only_that_file_and_settles(env):
    run(env, {"op": "relic.update", "relic_id": "r001", "effects": [{"type": "max_lives_bonus", "value": 6}],
              "desc": "获得时，生命上限+6。", "desc_en": "Lives +6."})
    ws = env["service"].workspace()
    files = R.compile_runtime(ws, env["store"].base_raw())
    changed = {spec.name for spec in RUNTIME_FILES if files[spec.release] != env["cfg"].source_path(spec).read_bytes()}
    assert changed == {"relics.json", "locales_v3.json"}
    r001 = ws["data"]["relics"][0]
    assert r001["effect"] == {"type": "max_lives_bonus", "value": 6} and r001["desc"] == "获得时，生命上限+6。"
    assert ws["data"]["locales"]["zh"]["rogue.relic.r001.desc"] == r001["desc"]
    lines = env["service"].diff({}, )["readable"]
    assert any("r001" in line["text"] and "6" in line["text"] for line in lines)


def test_relic_referenced_by_event_cannot_be_deleted(env):
    ws = env["service"].workspace()
    ws["data"]["events"][0]["options"][0]["effects"][1]["value"]["relic_id"] = "r004"
    env["store"].save(ws, ws["revision"], "test")
    with pytest.raises(StoreError, match="仍被引用"):
        run(env, {"op": "relic.delete", "relic_id": "r004"})


def test_batch_is_all_or_nothing_and_revision_is_checked(env):
    before = env["service"].workspace()
    with pytest.raises(StoreError):
        run(env, {"op": "relic.update", "relic_id": "r001", "rarity": "rare"}, {"op": "relic.update", "relic_id": "r999"})
    assert env["service"].workspace() == before
    with pytest.raises(ConflictError):
        env["service"].commands({}, {"revision": before["revision"] - 1, "commands": [{"op": "relic.update", "relic_id": "r001"}]})


# ---------------------------------------------------------------- rules / encounters (B-006/B-008/B-009/B-010)
def test_excluding_the_boss_round_blocks_like_the_server(env):
    run(env, {"op": "rules.set", "path": "/encounters/exclude_rounds", "value": [27, 29, 30]})
    blockers, result = codes(env)
    assert "B-008" in blockers
    assert any("首领轮次不能被排除" in f["message"] for f in result["findings"])


def test_zero_tier_weights_block(env):
    run(env, {"op": "rules.set", "path": "/rewards/tier_weights_chest_boss", "value": [0, 0, 0, 0]})
    assert "B-008" in codes(env)[0]


def test_act_band_too_small_and_read_only_paths(env):
    run(env, {"op": "rules.set", "path": "/encounters/exclude_rounds", "value": [27, 30, *range(1, 11)]})
    blockers, result = codes(env)
    assert "B-010" in blockers  # act 3 ranks 19..28 now runs past the 18 remaining encounters
    with pytest.raises(StoreError, match="不可编辑"):
        run(env, {"op": "rules.set", "path": "/host/event_id", "value": 1})
    with pytest.raises(StoreError, match="不可编辑"):
        run(env, {"op": "rules.set", "path": "/data_dir", "value": "C:/elsewhere"})


def test_act1_boss_skips_encounters_ineffective_for_the_start_element(env):
    ws = env["service"].workspace()
    view = encounters.acts_view(ws["data"]["rules"], ws["data"]["encounter_pool"])
    act1 = view["acts"][0]
    assert act1["boss"] == "700110010"
    assert act1["boss_by_element"]["1"] == "700110009"  # fire is cut to 1/10 by round 10
    assert act1["boss_by_element"]["2"] == "700110010"


# ---------------------------------------------------------------- pool (B-003/B-011/B-014, T-007, T-011)
def test_character_tier_override_and_disable_write_the_v3f_overlay(env):
    run(env, {"op": "character.set", "ids": ["900200"], "tier": 2, "reason": "测试升档"},
        {"op": "character.set", "ids": ["900101"], "enabled": False})
    ws = env["service"].workspace()
    ov = ws["data"]["pool_overlay"]["tier_overrides"]["characters"]
    assert ov["900200"]["tier"] == 2 and ov["900200"]["from_tier"] == 1 and ov["900200"]["reason"] == "测试升档"
    assert ov["900101"]["tier"] is None
    chars = {c["id"]: c for c in env["service"].characters({"size": ["500"]})["items"]}
    assert chars["900200"]["effective_tier"] == 2 and not chars["900101"]["in_pool"]
    run(env, {"op": "character.set", "ids": ["900200"], "tier": "source"}, {"op": "character.set", "ids": ["900101"], "enabled": True})
    assert set(env["service"].workspace()["data"]["pool_overlay"]["tier_overrides"]["characters"]) == {"900103"}


def test_tier4_with_starter_flag_is_blocked_as_unsupported(env):
    run(env, {"op": "character.set", "ids": ["900100"], "tier": 4, "starter_eligible": True})
    blockers, result = codes(env)
    assert "B-014" in blockers
    chars = {c["id"]: c for c in env["service"].characters({"size": ["500"]})["items"]}
    assert chars["900100"]["starter_derived"] is False


def test_disabling_too_many_starters_blocks_start_packs(env):
    run(env, {"op": "character.set", "ids": ["900200", "900201", "900202"], "enabled": False})
    blockers, result = codes(env)
    assert "B-011" in blockers and any("开局选水属性" in f["message"] for f in result["findings"])


def test_boss_playable_can_be_blocked_but_not_retiered(env):
    with pytest.raises(StoreError, match="不在 tier_table 入池名单"):
        run(env, {"op": "character.set", "ids": ["990001"], "tier": 3})
    run(env, {"op": "character.set", "ids": ["990001"], "enabled": False})
    chars = {c["id"]: c for c in env["service"].characters({"size": ["500"]})["items"]}
    assert not chars["990001"]["in_pool"]
    run(env, {"op": "character.set", "ids": ["990002"], "enabled": True})  # excluded by master: candidate mark only
    blockers, _ = codes(env)
    assert "B-014" in blockers


def test_pending_element_weapon_cannot_enter_the_pool(env):
    run(env, {"op": "weapon.set", "ids": ["100001"], "enabled": True})
    blockers, _ = codes(env)
    assert {"B-003", "B-014"} <= blockers


def test_policy_notes_do_not_block(env):
    run(env, {"op": "relic.update", "relic_id": "r001", "policy": {"notes": "候选：再看数值"}},
        {"op": "weapon.set", "ids": ["8000100"], "notes": "后续考虑"})
    assert codes(env)[0] == set()


# ---------------------------------------------------------------- releases / snapshots
def test_build_release_versioning_reuse_and_tamper_detection(env):
    service, store = env["service"], env["store"]
    ws = service.workspace()
    first = service.build({}, {"revision": ws["revision"], "message": "baseline"})["release"]
    again = service.build({}, {"revision": ws["revision"], "message": "again"})["release"]
    assert first["content_version"] == again["content_version"] and again["reused"]
    path = R.release_dir(store, first["content_version"])
    files = R.read_files(path)
    for spec in RUNTIME_FILES:
        assert files[spec.release] == env["cfg"].source_path(spec).read_bytes()
    assert R.content_version(files) == first["content_version"]
    (path / "data" / "relics.json").write_bytes(b"[]")
    with pytest.raises(StoreError, match="摘要不符"):
        R.verify(path)


def test_build_refuses_blockers(env):
    run(env, {"op": "rules.set", "path": "/rewards/tier_weights_chest_boss", "value": [0, 0, 0, 0]})
    ws = env["service"].workspace()
    with pytest.raises(StoreError, match="阻断"):
        env["service"].build({}, {"revision": ws["revision"]})


def test_snapshot_restore_keeps_ids_retired(env):
    service = env["service"]
    snap = service.create_snapshot({}, {"message": "before"})["snapshot"]
    out = run(env, {"op": "relic.create", "template": "gold_on_pickup", "name_en": "a", "desc_en": "b"})
    rid = out["results"][0]["relic_id"]
    run(env, {"op": "relic.delete", "relic_id": rid})
    ws = service.workspace()
    service.restore_snapshot({}, {"revision": ws["revision"]}, sid=snap["id"])
    ws = service.workspace()
    assert rid in ws["lifecycle"]["reserved_relic_ids"]
    assert ("relic", rid) in {(t["kind"], t["id"]) for t in ws["lifecycle"]["tombstones"]}
    assert run(env, {"op": "relic.create", "name_en": "a", "desc_en": "b"})["results"][0]["relic_id"] != rid


def test_workspace_export_import_round_trip(env):
    service = env["service"]
    exported = json.loads(service.export({"format": ["workspace"]}).body)
    run(env, {"op": "rules.set", "path": "/shop/heal_price", "value": 10})
    ws = service.workspace()
    service.import_workspace({}, {"revision": ws["revision"], "workspace": exported})
    assert service.workspace()["data"]["rules"]["shop"]["heal_price"] == 75
    with pytest.raises(StoreError):
        service.import_workspace({}, {"revision": service.workspace()["revision"], "workspace": {"document_type": "x"}})


# ---------------------------------------------------------------- trial apply / rollback
class FakeTrialctl:
    def __init__(self, tree: Path):
        self.tree = tree
        self.running = False
        self.calls = []
        self.loaded = "[ROGUE-CORRIDOR] v1 config loaded: enabled=true host=700110/1 rounds=28 owned_only=false chars={c} weapons={w} relics={r} events={e} sources={{}}"
        self.counts = None
        self.fail_start = False

    def __call__(self, *args, timeout=180):
        cmd = args[0]
        self.calls.append(cmd)
        if cmd == "status":
            pid = [4242] if self.running else []
            rec = json.dumps({"pid": 4242, "entry": "out/cn-server.js", "port": 18011, "session_port": 18013}, indent=2) if self.running else "None"
            return 0, f"env ports: 18011 18013 listeners: {{18011: {pid}, 18013: {pid}}}\nrecorded: {rec}\n"
        if cmd == "stop":
            self.running = False
            return 0, "stopped\n"
        if cmd == "start":
            config = json.loads((self.tree / "assets" / "rogue_corridor_v1.json").read_text("utf-8"))
            data = Path(config["data_dir"])
            log = self.tree / ".logs" / f"trial-{len(self.calls)}.out.log"
            log.parent.mkdir(parents=True, exist_ok=True)
            if self.fail_start:
                log.write_text("[ROGUE-CORRIDOR] config/data unavailable (x); module inert: boom\n", "utf-8")
            else:
                relics = json.loads((data / "relics.json").read_text("utf-8"))
                events = json.loads((data / "events.json").read_text("utf-8"))
                log.write_text(self.loaded.format(c=1, w=1, r=len(relics), e=len(events)) + "\n", "utf-8")
            self.running = True
            return 0, f"started pid 4242\nlogs: {log} | {log.with_suffix('.err')}\n"
        return 1, "unknown"


def make_trial(env, runs=None):
    tree = env["cfg"].trial_tree
    (tree / "assets").mkdir(parents=True, exist_ok=True)
    (tree / "out" / "lib").mkdir(parents=True, exist_ok=True)
    (tree / "out" / "lib" / "rogue-corridor.js").write_text("// fixture", "utf-8")
    (tree / ".env").write_text('A=1\nCN_LISTEN_PORT="18011"\nSESSION_PORT="18013"\n', "utf-8")
    (env["cfg"].proto_server / "tools").mkdir(parents=True, exist_ok=True)
    (env["cfg"].trialctl).write_text("# fixture", "utf-8")
    for name in ("rogue_corridor_v1.json", "rogue_pool_v3f.json"):
        (tree / "assets" / name).write_bytes((env["cfg"].proto_server / "src" / name).read_bytes())
    if runs is not None:
        (tree / ".database").mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(tree / ".database" / "wdfp_data.db")
        con.execute("CREATE TABLE rogue_corridor_v1_runs (seq INTEGER PRIMARY KEY, run_id TEXT, player_id INTEGER, status TEXT, "
                    "revision INTEGER, seed INTEGER, run_json TEXT, meta_json TEXT, created_at INTEGER, updated_at INTEGER)")
        for i, run_ in enumerate(runs):
            con.execute("INSERT INTO rogue_corridor_v1_runs VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (i, f"run{i}", 1, "active", 3, 1, json.dumps(run_), "{}", 0, 0))
        con.commit()
        con.close()
    fake = FakeTrialctl(tree)
    trial = Trial(env["cfg"], env["store"], runner=fake)

    def preflight(config_path):
        config = json.loads(Path(config_path).read_text("utf-8"))
        data = Path(config["data_dir"])
        relics = json.loads((data / "relics.json").read_text("utf-8"))
        events = json.loads((data / "events.json").read_text("utf-8"))
        return {"ok": True, "counts": {"relics": len(relics), "events": len(events)}, "builtin": False, "issues": {}}
    trial.preflight = preflight
    env["service"].trial = lambda: trial
    return trial, fake


def build_release(env, *commands, message="m"):
    if commands:
        run(env, *commands)
    ws = env["service"].workspace()
    return env["service"].build({}, {"revision": ws["revision"], "message": message})["release"]["content_version"]


def test_trial_guard_refuses_other_ports_and_real_server_roots(env):
    trial, _ = make_trial(env)
    assert trial.guard() == []
    (env["cfg"].trial_tree / ".env").write_text('CN_LISTEN_PORT="8001"\nSESSION_PORT="8003"\n', "utf-8")
    assert any("只允许 18011/18013" in p for p in trial.guard())
    (env["cfg"].trial_tree / ".env").write_text('CN_LISTEN_PORT="18011"\nSESSION_PORT="18013"\n', "utf-8")
    real = Trial(env["cfg"], env["store"], forbidden_roots=[env["cfg"].proto_server], runner=trial.runner)
    assert any("真实服务端目录" in p for p in real.guard())


def test_apply_edit_restart_then_rollback(env):
    trial, fake = make_trial(env)
    base = build_release(env, message="基线")
    edited = build_release(env, {"op": "relic.update", "relic_id": "r001", "effects": [{"type": "max_lives_bonus", "value": 6}],
                                 "desc": "获得时，生命上限+6。", "desc_en": "Lives +6."}, message="r001 +6")
    assert trial.active()["label"] == "proto-install"
    plan = trial.plan(edited)
    assert not plan["blocked"] and plan["active"]["label"] == "proto-install"
    with pytest.raises(ConflictError):
        trial.apply(edited, "release:" + base)
    result = trial.apply(edited, "proto-install")
    assert result["result"] == "ok" and result["health"]["ok"] and fake.running
    assert trial.active()["label"] == "release:" + edited
    deployed = json.loads((env["cfg"].trial_tree / "assets" / "rogue_corridor_v1.json").read_text("utf-8"))
    data_dir = Path(deployed["data_dir"])
    assert data_dir.is_relative_to(env["cfg"].trial_tree / "assets" / "rogue-content")
    assert json.loads((data_dir / "relics.json").read_text("utf-8"))[0]["effect"]["value"] == 6
    original = json.loads((env["cfg"].proto_server / "src" / "rogue_corridor_v1.json").read_text("utf-8"))
    assert {**deployed, "data_dir": None} == {**original, "data_dir": None}
    back = trial.apply(base, "release:" + edited, action="rollback")
    assert back["result"] == "ok" and trial.active()["label"] == "release:" + base
    data_dir = Path(json.loads((env["cfg"].trial_tree / "assets" / "rogue_corridor_v1.json").read_text("utf-8"))["data_dir"])
    assert (data_dir / "relics.json").read_bytes() == (env["cfg"].data_dir / "relics.json").read_bytes()
    restored = trial.restore_original("release:" + base)
    assert restored["active"]["label"] == "proto-install"
    assert [d["action"] for d in trial.deploys()][:3] == ["restore_original", "rollback", "apply"]


def test_failed_health_check_restores_previous_files(env):
    trial, fake = make_trial(env)
    version = build_release(env, {"op": "rules.set", "path": "/shop/heal_price", "value": 70})
    before = (env["cfg"].trial_tree / "assets" / "rogue_corridor_v1.json").read_bytes()
    fake.fail_start = True
    with pytest.raises(TrialError, match="已恢复"):
        trial.apply(version, "proto-install")
    assert (env["cfg"].trial_tree / "assets" / "rogue_corridor_v1.json").read_bytes() == before
    assert trial.active()["label"] == "proto-install"
    assert trial.deploys()[0]["result"] == "failed_restored"


def test_open_runs_breaking_change_is_refused_and_numbers_need_ack(env):
    trial, _ = make_trial(env, runs=[{"rules_revision": 3, "floor": 7, "relics": [{"relic_id": "r004"}],
                                      "pending": {"kind": "event", "event_id": "e002", "node_id": 1}, "map": {"floors": []}}])
    ids = env["service"].workspace()["policy"]["event_option_ids"]["e002"]
    breaking = build_release(env, {"op": "event.option.move", "event_id": "e002", "option_id": ids[3], "to": 0})
    plan = trial.plan(breaking)
    assert plan["blocked"] and "选项" in plan["open_runs"][0]["breaking"][0]
    with pytest.raises(TrialError, match="进行中的局"):
        trial.apply(breaking, "proto-install")
    run(env, {"op": "event.option.move", "event_id": "e002", "option_id": ids[3], "to": 3})
    numbers = build_release(env, {"op": "rules.set", "path": "/shop/heal_price", "value": 60})
    plan = trial.plan(numbers)
    assert not plan["blocked"] and plan["needs_ack"]
    with pytest.raises(ConflictError, match="进行中的局"):
        trial.apply(numbers, "proto-install")
    assert trial.apply(numbers, "proto-install", acknowledge_open_runs=True)["result"] == "ok"
    deleting = build_release(env, {"op": "relic.delete", "relic_id": "r004"})
    assert trial.plan(deleting)["blocked"]


def test_routes_map_conflicts_to_409(env):
    from wf.studio.corridor.routes import CorridorRoutes
    routes = CorridorRoutes(app=None, service=env["service"])
    table = {(verb, pattern.pattern): handler for verb, pattern, handler in routes.routes()}
    handler = table[("POST", r"^/api/corridor/commands$")]
    response = handler(query={}, body={"revision": -5, "commands": [{"op": "relic.update", "relic_id": "r001"}]})
    assert response.status == 409
    response = table[("GET", r"^/api/corridor/status$")](query={})
    status = json.loads(response.body)
    assert status["workspace"]["revision"] >= 1 and status["validation"]["blockers"] == 0


# ---------------------------------------------------------------- real data (local only)
def _real_config():
    from wf.studio.corridor.layout import load_config
    try:
        cfg = load_config(Path("unused"))
    except (ValueError, OSError):
        return None
    if cfg is None or not all(cfg.source_path(s).is_file() for s in RUNTIME_FILES):
        return None
    return cfg


@pytest.mark.skipif(_real_config() is None, reason="本机未配置 profiles/local.json rogue_corridor（真实回廊数据不进仓库）")
def test_real_corridor_data_round_trips_byte_identical(tmp_path):
    cfg = _real_config()
    ws, raws = import_from_sources(cfg)
    files = R.compile_runtime(ws, raws)
    for spec in RUNTIME_FILES:
        assert files[spec.release] == raws[spec.name], spec.name
    result = V.validate(ws, master_of(cfg), ws)
    assert result["blockers"] == 0, [f for f in result["findings"] if f["severity"] == "block"]
    view = encounters.acts_view(ws["data"]["rules"], ws["data"]["encounter_pool"])
    assert all(a["size"] >= 4 and all(a["boss_by_element"].values()) for a in view["acts"])
