"""D1 offline contracts: view isolation, regression gates and delivery reuse."""
import copy
import json
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
import wf_quest_lib as q
from wf.studio import mode_five, mode_rogue
from wf.studio.mode_store import ModeStore, ViewInputs
from wf.studio.mode_routes import ModeRoutes
from wf.studio.drafts import DraftError
from wf.tools.boss import five_boss_v2 as five
from wf.tools.rogue import rogue_build as rogue
from wf.tools.rogue.rogue_candidate import isolated_builder, build_candidate


def test_spec_decoder_does_not_mutate_document_and_matches_file():
    doc = mode_five.document()
    saved = copy.deepcopy(doc)
    assert five.parse_spec(doc) == five.load_spec()
    assert doc == saved and "_variants" not in doc


@pytest.mark.parametrize("mutate", [
    lambda d: d["variants"][0]["waves"][0][0].update(hp_e8=-1),
    lambda d: d["variants"][0]["waves"][0][0].update(hp_e8=float("nan")),
    lambda d: d["variants"][0].update(quest=1),
    lambda d: next(iter(d["bosses"].values())).update(mother="other"),
    lambda d: d.update(time_limit_frames=123),
])
def test_structure_rejects_invalid_numeric_or_ownership_changes(mutate):
    doc = mode_five.document()
    mutate(doc)
    with pytest.raises(ValueError):
        mode_five.validate_document(doc)


def test_numeric_and_affix_changes_have_exact_diff():
    doc = mode_five.document()
    old = doc["variants"][0]["waves"][0][0]["hp_e8"]
    doc["variants"][0]["waves"][0][0]["hp_e8"] = old / 2
    _, diff = mode_five.validate_document(doc)
    assert diff == [{"path": "/variants/0/waves/0/0/hp_e8", "before": old, "after": old / 2}]


def test_affix_replacement_of_same_length_and_budget_order():
    doc = mode_five.document()
    doc["variants"][0]["affixes"][0] = "silence_waves"
    _, diff = mode_five.validate_document(doc)
    assert any(d["path"].endswith("/affixes/0") for d in diff)
    doc["budget"]["fail_mpx"] = doc["budget"]["pass_mpx"] / 2
    with pytest.raises(ValueError, match="预算"):
        mode_five.validate_document(doc)


def test_missing_input_becoming_present_is_drift():
    data = {}
    def read_member(name):
        if name not in data:
            raise FileNotFoundError(name)
        return data[name], "tip"
    inputs = ViewInputs(SimpleNamespace(view=SimpleNamespace(read_member=read_member)))
    with pytest.raises(FileNotFoundError):
        inputs.read("optional.png")
    inputs.verify()
    from wf.deliver.changeset import member_name
    data[member_name("common", "optional.png")] = b"new"
    with pytest.raises(DraftError, match="输入发生变化"):
        inputs.verify()


def test_current_view_png_budget_never_falls_back_to_store(monkeypatch):
    import struct
    def forbidden(*args):
        raise AssertionError("store fallback")
    monkeypatch.setattr(q, "store_path", forbidden)
    live = five.Live(lambda logical: b"\x89PNG\r\n\x1a\n" + b"\0\0\0\rIHDR" + struct.pack(">II", 64, 32))
    live.view_bound = True
    assert five.png_dims(live, "sheet.png") == (64, 32)
    live._loader = lambda logical: b""
    assert five.png_dims(live, "missing.png") is None


def test_input_loader_detects_drift_and_uses_view_members_only():
    raw = [b"chain tail"]
    view = SimpleNamespace(read_member=lambda name: (raw[0], "tip"), verify=lambda: None)
    inputs = ViewInputs(SimpleNamespace(view=view))
    assert inputs.read("one.bin") == b"chain tail"
    raw[0] = b"changed"
    with pytest.raises(DraftError, match="输入发生变化"):
        inputs.verify()


def test_concurrent_legacy_builders_have_separate_tables_and_dsl_caches(monkeypatch):
    from wf.tools.rogue import rogue_bundle
    original = rogue.q
    def forbidden(*args):
        raise AssertionError("legacy store read")
    monkeypatch.setattr(original, "store_path", forbidden)
    def run(number):
        raw = five.encode_dsl(["ActionDsl", str(number)])
        def loader(logical):
            return raw if logical.endswith("deflate") else q.build_node({"value": str(number)})
        with isolated_builder(loader) as builder:
            assert builder._tbl("table")["value"] == str(number)
            assert builder.rbb.load_store_action("action") == ["ActionDsl", str(number)]
            assert builder.wb._load("table")["value"] == str(number)
            assert not hasattr(builder.q, "save_table")
        return number
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(run, (1, 2))) == [1, 2]
    assert rogue.q is original and rogue.rbb is rogue_bundle


@pytest.mark.parametrize("seed", [-1, 2**32, True, 1.5, "1"])
def test_rogue_bad_seed_rejected_before_any_read(seed):
    with pytest.raises(ValueError, match="种子"):
        build_candidate(lambda _: pytest.fail("must not read"), seed=seed, rounds=30)


def test_candidate_main_rejects_write_before_resolving_server():
    with pytest.raises(ValueError, match="cannot write"):
        rogue.main(["--write"], candidate_sink=lambda _: None)


def test_pure_forge_and_legacy_forge_produce_same_bytes(tmp_path, monkeypatch):
    from wf.tools.core import field_catalog as fields
    program = "battle/action/enemy/test"
    raw = fields.build_dsl(["ActionDsl", ["Block", []]])
    source = tmp_path / "source"
    source.write_bytes(raw)
    target = tmp_path / "output"
    monkeypatch.setattr(fields.q, "store_path", lambda logical: source if logical.startswith(program) else target)
    name, blob = fields.forge_bytes(program, raw, scale=.5)
    assert not target.exists()
    assert fields.forge(program, scale=.5) == name
    assert target.read_bytes() == blob


def test_regression_audit_detects_owned_change_without_foreign_sibling_noise():
    logical = "master/test.orderedmap"
    live = five.Live(lambda _: q.build_node({"owned": "new live", "foreign": "preserve"}))
    plan = five.Plan()
    plan.put(logical, ["owned"], "old spec")
    audit = mode_five.audit_current(None, {"plan": plan, "live": live})
    assert not audit["aligned"]
    assert [d["path"] for d in audit["differences"]] == ["owned"]
    assert q.parse_node(five.apply_edits(live, plan)[logical])["foreign"] == "preserve"


def test_spec_drift_disables_generation_even_when_candidate_valid(monkeypatch):
    plan = five.Plan()
    plan.put("table", ["key"], "spec")
    live = five.Live(lambda _: q.build_node({"key": "current"}))
    monkeypatch.setattr(mode_five, "compile_structure", lambda *args: {
        "plan": plan, "live": live, "diff": [], "files": {"table": b"candidate"}})
    result = mode_five.preview(None, mode_five.document())
    assert result["ok"] and not result["canGenerate"] and result["blockers"]
    plan.problems.append("budget exceeded")
    assert not mode_five.preview(None, mode_five.document())["ok"]


def test_mode_store_namespace_revision_and_path_guards(tmp_path):
    store = ModeStore(tmp_path / "modes")
    assert store.load("five") is None and not store.root.exists()
    data = store.save("five", "1.4.10", {}, {}, {}, 0)
    assert data["revision"] == 1 and store.load("rogue") is None
    with pytest.raises(DraftError, match="其他窗口"):
        store.save("five", "1.4.10", {}, {}, {}, 0)
    with pytest.raises(DraftError, match="未知模式"):
        store.directory("../five")


def test_routes_preview_no_writes_save_regression_and_build_refusal(tmp_path, monkeypatch):
    from wf.studio import mode_routes
    from wf.studio.drafts import DraftStore
    source = SimpleNamespace(version="1.4.10", view=SimpleNamespace(verify=lambda: None))
    app = SimpleNamespace(source=source, ops=SimpleNamespace(store=DraftStore(tmp_path / "drafts")))
    routes = ModeRoutes(app)
    monkeypatch.setattr(mode_five, "preview", lambda *args: {"ok": True, "canGenerate": False,
        "blockers": ["spec drift"], "files": {"a": b"b"}})
    monkeypatch.setattr(mode_routes, "freshness", lambda _: {"loaded": "1.4.10", "latest": "1.4.10", "stale": False})
    response = routes.edit({}, {"payload": {}}, "five", "preview")
    assert json.loads(response.body)["blockers"] == ["spec drift"]
    assert not routes.store.root.exists()
    routes.edit({}, {"payload": {}, "revision": 0}, "five", "save")
    assert routes.store.load("five")["preview"]["canGenerate"] is False
    with pytest.raises(DraftError, match="spec drift"):
        routes.deliveries.compile_delivery("five", from_version="1.4.10")


def test_current_tower_reports_content_without_claiming_runtime_season():
    rows = {}
    for number in (1, 2, 99):
        row = [""] * 100
        row[:3] = [str(700099000 + number), "2" if number == 99 else "1", "0" if number == 99 else str(number)]
        rows[str(number)] = rogue.join(row, False)
    data = {rogue.Q_QUEST: {rogue.EVENT_ID: rows}, rogue.Q_EVENT: {rogue.EVENT_ID: "demo"}}
    current = mode_rogue.current(lambda logical: q.build_node(data[logical]))
    assert current["rounds"] == 2 and current["season"] is None
    assert len(current["rows"]) == 3
    assert current["manualSteps"] and "不连接" in current["seasonNote"]


def test_mode_clone_overlay_preserves_old_graph_and_exact_siblings(monkeypatch):
    from wf.studio import mode_rogue_overlay as overlay
    import wf_share_update_codec as codec
    def quest(field):
        row = [""] * 100
        row[0:3] = ["700099001", "1", "1"]
        row[98] = field
        return rogue.join(row, False)
    before = {rogue.GENERAL_BOSS: {"official": {"80": "untouched"}, "mod_rogue_boss1": {"20": "old"}},
              rogue.FIELD_DATA_T: {"mod_rogue_f1": "field,terrain,mod_rogue_z1"},
              rogue.ZONE_T: {"mod_rogue_z1": {"0": "mod_rogue_boss1"}},
              rogue.Q_QUEST: {rogue.EVENT_ID: {"1": quest("mod_rogue_f1")}}}
    tables = copy.deepcopy(before)
    tables[rogue.GENERAL_BOSS]["mod_rogue_boss1"] = {"100": "new"}
    raw = {key: q.build_node(value) for key, value in before.items()}
    candidate = {"files": {key: q.build_node(value) for key, value in tables.items()}}
    seen = []
    monkeypatch.setattr(overlay, "validate_candidate_references", lambda rows, final, builder:
                        seen.append((rows, final)) or [])
    result = overlay.retain_and_namespace(raw.__getitem__, candidate)
    after = q.parse_node(result["files"][rogue.GENERAL_BOSS])
    name = "mod_rogue_boss1_studio_" + result["cloneNamespace"]
    assert after["mod_rogue_boss1"] == {"20": "old"}
    assert after[name] == {"100": "new"}  # Old levels never contaminate new clone.
    assert seen[0][0]["1"][98].endswith(result["cloneNamespace"])
    assert codec.unpack(raw[rogue.GENERAL_BOSS])["official"] == codec.unpack(
        result["files"][rogue.GENERAL_BOSS])["official"]


def test_reference_gate_rejects_broken_candidate():
    from wf.tools.rogue.rogue_validate import validate_candidate_references
    builder = SimpleNamespace(GENERAL_BOSS="gb", STANDARD_BOSS="sb", GENERAL_ZAKO="gz",
        GENERAL_BOSS_VARIABLE="gv", FIELD_DATA_T="fd", ZONE_T="zone", SPECIAL_BOSS_TABLES=(),
        boss_ref_validation_tables=lambda **kwargs: {},
        validate_built_rows=lambda *args, **kwargs: [{"ok": False, "errors": ["missing boss"]}])
    with pytest.raises(ValueError, match="引用门禁失败"):
        validate_candidate_references({}, {key: {} for key in ("gb", "sb", "gz", "gv", "fd", "zone")}, builder)


def test_compiled_mode_uses_real_delivery_checks(tmp_path, monkeypatch):
    from wf.studio.deliver_bridge import deliver_compiled
    from wf.studio.source import StudioSource
    from wf.view import ManifestView
    from wf.deliver.changeset import member_name
    import zipfile
    active, store = tmp_path / "active", tmp_path / "store"
    active.mkdir(); store.mkdir()
    archive = active / "pinball-1.4.131-1.4.132-1-test.zip"
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr(member_name("common", "test.bin"), b"old")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"cdn_version": "1.4.132", "patches": [{"version": "1.4.132",
        "depends_on": "1.4.131", "chain": [archive.name], "type": "patch"}]}))
    baseline = ManifestView("1.4.132", store=store, manifest=manifest, search_dirs=[])
    draft = ModeStore(tmp_path / "drafts").save("rogue", "1.4.132", {"seed": 1}, {}, {}, 0)
    result = deliver_compiled(draft, ({("common", "test.bin"): b"new"}, {}, {}, [], []),
        source=StudioSource(baseline), baseline=baseline, from_version="1.4.132", to_version="1.4.133",
        out=tmp_path / "delivery", provides=None, selected_profile=None, apks=[], allow_unknown_client=True)
    assert result["ok"] and result["checks"] and result["keyDiff"]["ok"]
    assert result["deviceValidation"] == "未执行"
    assert (tmp_path / "delivery/delivery/SHA256SUMS").is_file()
