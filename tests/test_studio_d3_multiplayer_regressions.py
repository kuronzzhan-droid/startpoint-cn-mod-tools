"""Advisory scanning must preserve old drafts, five-state gates and replay costs."""
import copy
import json
import struct
from collections import Counter
from types import SimpleNamespace

import pytest

from test_boss_behavior import behavior_editor
from test_studio_boss_checks import fixture_editor
from test_studio_boss_drafts import five_tier_editor
from wf.boss.behavior_wire import compress, write_tree
from wf.boss.edit_state import BossEditState, digest
from wf.boss.reader import BossReader
from wf.rules.catalog import result, with_metadata
from wf.rules.multiplayer import MultiplayerScanner, check_multiplayer, scan_tree
from wf.studio.boss import BossEditor, compile_boss
from wf.studio.source import StudioSource


QUEST = "hard_multi:1006/1"
ACTION = "battle/action/one.action.dsl.amf3.deflate"
EDIT = {"operation": "edit", "parameters": {"hpMultiplier": 2}}
MARKER = "battle/marker/test.timeline.amf3.deflate"
RANDOM = ["Command", ["ConditionalsProbability", ["Block", [
    ["Block", [["Command", ["ProbabilityWeight", 1]], ["Block", []]]],
    ["Block", [["Command", ["ProbabilityWeight", 2]], ["Block", []]]],
]]]]


def test_scan_reads_candidate_without_enrolling_any_snapshot_input(tmp_path):
    editor = behavior_editor(tmp_path)
    state = BossEditState(editor.source)
    document = BossReader(editor.source).show(QUEST)
    state.client[ACTION] = compress(write_tree(RANDOM))
    before = copy.deepcopy(state.snapshot())
    checks = check_multiplayer(document, state)
    assert any(c["rule"] == "multiplayer.random" for c in checks)
    assert state.snapshot() == before == {"client": {}, "server": {}}
    assert editor.source.view.files[ACTION] != state.client[ACTION]


def test_pre_d3_saved_draft_opens_inspects_previews_applies_and_compiles(tmp_path, monkeypatch):
    editor = behavior_editor(tmp_path)
    editor.source.view.files[ACTION] = compress(write_tree(RANDOM))
    # Save a genuine pre-D3 snapshot: all original draft checks run, but the new
    # advisory scan did not exist and therefore cannot add behavior input locks.
    with monkeypatch.context() as legacy:
        legacy.setattr("wf.rules.multiplayer.check_multiplayer", lambda *args: [])
        editor.apply(QUEST, EDIT)
        saved = editor.store.save(QUEST)
    locked = saved["changes"][0]["params"]["inputs"]
    assert MARKER not in locked["client"]
    editor.source.view.files[MARKER] = compress(write_tree({"sequences": [], "points": []}))
    reopened = BossEditor(StudioSource(editor.source.view), store=editor.store, server_dir=editor.server_dir)
    assert reopened.read(QUEST)["changeset"] == saved
    assert reopened.inspect(QUEST, "behavior")["data"]["enemies"]
    followup = {"operation": "edit", "parameters": {"attackMultiplier": 2}}
    assert reopened.preview(QUEST, followup)["ok"]
    compiled = compile_boss(reopened.source, reopened.store, saved, server_dir=reopened.server_dir)
    assert compiled["client"] and any(c["category"] == "联机风险" for c in compiled["checks"] if "category" in c)
    updated = reopened.apply(QUEST, followup)["changeset"]
    assert MARKER not in updated["changes"][0]["params"]["inputs"]["client"]
    assert compile_boss(reopened.source, reopened.store, updated, server_dir=reopened.server_dir)["client"]
    assert reopened.store.load(QUEST)["revision"] == saved["revision"] + 1


def test_saved_d3_advisory_locks_still_open_and_all_saved_hashes_are_verified(tmp_path):
    editor = behavior_editor(tmp_path)
    saved = editor.apply(QUEST, EDIT)["changeset"]
    # This is the persisted shape produced by D3 before scan isolation: the
    # marker is recorded even though no edit or five-state rule consumes it.
    saved["changes"][0]["params"]["inputs"]["client"][MARKER] = digest(editor.source.view.files[MARKER])
    editor.store._write(QUEST, saved)
    assert editor.read(QUEST)["changeset"] == saved
    assert compile_boss(editor.source, editor.store, saved, server_dir=editor.server_dir)["client"]
    state, *_ = editor._state(QUEST)
    assert MARKER not in state.original
    editor.source.view.files[MARKER] = compress(write_tree({"sequences": [], "points": []}))
    with pytest.raises(ValueError, match="SHA-256 drift"):
        editor.read(QUEST)
    with pytest.raises(ValueError, match="SHA-256 drift"):
        compile_boss(editor.source, editor.store, saved, server_dir=editor.server_dir)


def test_legacy_extra_locks_never_allow_missing_required_write_inputs(tmp_path):
    editor = behavior_editor(tmp_path)
    saved = editor.apply(QUEST, EDIT)["changeset"]
    inputs = saved["changes"][0]["params"]["inputs"]["client"]
    inputs[MARKER] = digest(editor.source.view.files[MARKER])
    del inputs["master/quest/event/hard_multi_event_quest.orderedmap"]
    with pytest.raises(ValueError, match="SHA-256 drift"):
        compile_boss(editor.source, editor.store, saved, server_dir=editor.server_dir)


@pytest.mark.parametrize("error", [struct.error("truncated double"), RecursionError("too deep"),
                                  RuntimeError("decoder failed"), AssertionError("unexpected tree")])
def test_all_scan_exceptions_are_nonblocking_and_keep_drafts_usable(tmp_path, monkeypatch, error):
    editor = fixture_editor(tmp_path)

    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr("wf.rules.multiplayer_inputs.collect_inputs", fail)
    assert editor.read(QUEST)["checks"][0]["rule"] == "multiplayer.incomplete"
    assert editor.preview(QUEST, EDIT)["ok"]
    saved = editor.apply(QUEST, EDIT)["changeset"]
    checks = compile_boss(editor.source, editor.store, saved, server_dir=editor.server_dir)["checks"]
    incomplete = [c for c in checks if c["rule"] == "multiplayer.incomplete"]
    assert incomplete and all(c["blocking"] is False and c["category"] == "联机风险" for c in incomplete)
    assert not any(c["blocking"] for c in checks)


def test_truncated_amf_double_is_nonblocking_in_actual_decoder(tmp_path, monkeypatch):
    from wf.rules.multiplayer import _ReadOnlyCandidate
    editor = behavior_editor(tmp_path)
    original = _ReadOnlyCandidate.raw
    # Corrupt the advisory decoder's input only. The independent five-state
    # gates also parse actions and must retain their own rejection behavior.
    monkeypatch.setattr(_ReadOnlyCandidate, "raw", lambda self, logical:
                        compress(b"\x05\x00") if logical == ACTION else original(self, logical))
    checks = editor.read(QUEST)["checks"]
    assert any(c["rule"] == "multiplayer.incomplete" and "invalid AMF3" in c["message"] for c in checks)
    assert editor.preview(QUEST, EDIT)["ok"]


def test_five_tier_saved_read_and_preview_scan_one_equivalent_behavior(tmp_path, monkeypatch):
    import wf.rules.multiplayer as multiplayer
    editor = five_tier_editor(tmp_path)
    editor.apply("1080001", {"operation": "edit", "tiers": [{"hpMultiplier": i} for i in range(2, 7)]})
    editor.store.save("boss_battle:1/80/1")
    original, calls = multiplayer._scan, []

    def counted(document, view):
        calls.append(document["quest"]["selector"])
        return original(document, view)

    monkeypatch.setattr(multiplayer, "_scan", counted)
    read = editor.read("1080001")
    assert len({c["quest"] for c in read["checks"] if c.get("quest")}) == 5
    assert len(calls) == 1
    calls.clear()
    preview = editor.preview("1080001", {"operation": "edit", "parameters": {"attackMultiplier": 2}})
    assert preview["ok"] and len(calls) == 1


def test_request_cache_does_not_hide_distinct_behavior_or_new_candidate(tmp_path):
    editor = behavior_editor(tmp_path)
    document = BossReader(editor.source).show(QUEST)
    scanner = MultiplayerScanner(editor.source)
    assert not any(c["rule"] == "multiplayer.random" for c in scanner.check(document))
    changed = copy.deepcopy(document)
    changed["enemies"][0]["row"][111] = "battle/action/other"
    editor.source.view.files["battle/action/other.action.dsl.amf3.deflate"] = compress(write_tree(RANDOM))
    assert any(c["rule"] == "multiplayer.random" for c in scanner.check(changed))
    editor.source.view.files[ACTION] = compress(write_tree(RANDOM))
    assert any(c["rule"] == "multiplayer.random" for c in check_multiplayer(document, editor.source))


def test_five_tier_scanner_decodes_each_shared_behavior_resource_once(tmp_path, monkeypatch):
    import wf.boss.behavior_model as model
    import wf.rules.multiplayer as multiplayer
    editor = five_tier_editor(tmp_path)
    behavior_root = tmp_path / "behavior"
    behavior_root.mkdir()
    donor = behavior_editor(behavior_root)
    for logical, raw in donor.source.view.files.items():
        if logical.startswith("master/battle/boss/") or logical.endswith((
                ".timeline.amf3.deflate", ".action.dsl.amf3.deflate")):
            editor.source.view.files[logical] = raw
    edit = {"operation": "edit", "tiers": [{"hpMultiplier": i} for i in range(2, 7)]}
    editor.apply("1080001", edit)
    editor.store.save("boss_battle:1/80/1")
    original, scan, decoded = model.decode_wire, multiplayer._scan, []
    scanning = False

    def advisory(document, view):
        nonlocal scanning
        scanning = True
        try:
            return scan(document, view)
        finally:
            scanning = False

    def counted(raw):
        if scanning:
            decoded.append(raw)
        return original(raw)

    monkeypatch.setattr(multiplayer, "_scan", advisory)
    monkeypatch.setattr(model, "decode_wire", counted)
    assert editor.read("1080001")["checks"]
    # Two action paths; marker decoding is not needed for static scanning. Payloads are equal,
    # so count paths via their expected multiplicity instead of distinct bytes.
    assert Counter(decoded) == Counter(donor.source.view.files[path] for path in (
        ACTION, "battle/action/two.action.dsl.amf3.deflate"))


def test_advisories_do_not_change_draft_warning_count_or_five_state_results(tmp_path, monkeypatch):
    editor = fixture_editor(tmp_path)
    with monkeypatch.context() as baseline:
        baseline.setattr("wf.rules.multiplayer.check_multiplayer", lambda *args: [])
        expected = editor.preview(QUEST, EDIT)["checks"]
    hints = scan_tree(RANDOM, "battle/action/risk")
    monkeypatch.setattr("wf.rules.multiplayer.check_multiplayer", lambda *args: hints)
    actual = editor.apply(QUEST, EDIT)
    normal = [c for c in actual["checks"] if c.get("category") != "联机风险"]
    assert normal == expected
    stored = actual["change"]["checks"]
    assert [c["level"] for c in stored if c["code"].startswith("multiplayer.")] == ["info"]
    assert sum(c["level"] == "warn" for c in stored) == sum(c["status"] in {"待验证", "问题"} for c in expected)


def test_delivery_readback_keeps_advisories_out_of_five_state_metadata():
    from wf.deliver.client_compatibility import readback_draft_checks
    normal = [result("studio.example", "满足", "checked")]
    hints = scan_tree(["Block", [RANDOM, RANDOM]], "battle/action/risk")

    def read(entries):
        raw = json.dumps(entries).encode()
        return readback_draft_checks({"draft_checks": "draft-checks.json"}, lambda path: (path, raw))

    baseline = with_metadata(read(normal), "delivery")
    actual = with_metadata(read(normal + hints), "delivery")
    assert actual == baseline
    assert Counter(c["status"] for c in actual) == Counter(c["status"] for c in baseline)
    assert sum(c["blocking"] for c in actual) == sum(c["blocking"] for c in baseline)
    assert len(hints) == 2  # The full, separate draftChecks list retains both locations.


@pytest.mark.parametrize("kind", ["character", "boss"])
def test_delivery_listing_counts_only_five_state_results(tmp_path, kind):
    from wf.studio.boss_routes import BossDeliveries
    from wf.studio.deliver_routes import DeliverRoutes
    cls = BossDeliveries if kind == "boss" else DeliverRoutes
    root = tmp_path / "deliveries"
    folder = root / "7-1.4.1-to-1.4.2-20261102-120000"
    folder.mkdir(parents=True)
    hints = scan_tree(RANDOM, "battle/action/risk")
    report = {"ok": True, "checks": [result("normal", "满足", "checked"), *hints],
              "compatChecks": [result("compat", "待验证", "unconfirmed")], "draftChecks": hints}
    (folder / "build-report.json").write_text(json.dumps(report), encoding="utf-8")
    routes = cls(SimpleNamespace(), root=root)
    item = json.loads(routes.listing({}).body)["deliveries"][0]
    assert item["ok"] and item["counts"] == {"满足": 1, "待验证": 1}
