"""The selected read-only server mirror is part of a reproducible mode draft."""
import json
from types import SimpleNamespace

import pytest
from wf.studio import config, mode_checks, mode_rogue, mode_routes
from wf.studio.drafts import DraftError, DraftStore, sha256
from wf.studio.mode_store import ViewInputs


def write_asset(root, name, payload):
    path = root / "assets" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(payload).encode("utf-8")
    path.write_bytes(raw)
    return raw


def source():
    return SimpleNamespace(version="1.4.10", view=SimpleNamespace(
        read_member=lambda name: pytest.fail("unexpected game input: " + name), verify=lambda: None))


@pytest.mark.parametrize("change", ["modify", "remove"])
def test_server_reader_freezes_raw_json_and_detects_changed_input(tmp_path, change):
    original = write_asset(tmp_path, "rogue_event.json", {"value": "initial"})
    inputs = ViewInputs(source(), server_dir=tmp_path)
    assert inputs.read_server_asset("rogue_event.json") == {"value": "initial"}
    assert inputs.inputs == {"server:rogue_event.json": sha256(original)}
    inputs.verify_read()
    if change == "modify":
        write_asset(tmp_path, "rogue_event.json", {"value": "changed"})
    else:
        (tmp_path / "assets" / "rogue_event.json").unlink()
    assert inputs.read_server_asset("rogue_event.json") == {"value": "initial"}
    with pytest.raises(DraftError, match="输入发生变化.*rogue_event.json"):
        inputs.verify()


def test_missing_server_json_is_cached_and_new_file_invalidates_inputs(tmp_path):
    inputs = ViewInputs(source(), server_dir=tmp_path)
    with pytest.raises(FileNotFoundError):
        inputs.read_server_asset("rogue_event_cnmod.json")
    assert inputs.inputs == {"server:rogue_event_cnmod.json": None}
    inputs.verify_read()
    write_asset(tmp_path, "rogue_event_cnmod.json", {"added": True})
    with pytest.raises(FileNotFoundError):
        inputs.read_server_asset("rogue_event_cnmod.json")
    with pytest.raises(DraftError, match="输入发生变化.*rogue_event_cnmod.json"):
        inputs.verify_read()


@pytest.mark.parametrize("name", ["../rogue_event.json", "assets/rogue_event.json", "/rogue_event.json",
                                  "C:\\rogue_event.json", "rogue_event.json:stream", "other.json", None])
def test_server_reader_refuses_unlisted_names_before_resolving_paths(monkeypatch, name):
    monkeypatch.setattr(config, "server_directory", lambda *_: pytest.fail("must not resolve paths"))
    inputs = ViewInputs(source())
    with pytest.raises(DraftError, match="不允许读取"):
        inputs.read_server_asset(name)
    inputs.inputs = {"server:" + str(name): None}
    with pytest.raises(DraftError, match="不允许读取"):
        inputs.verify()


def routes_fixture(tmp_path, monkeypatch, *, explicit):
    explicit_root, profile_root = tmp_path / "explicit", tmp_path / "profile"
    for root, marker in ((explicit_root, "explicit"), (profile_root, "profile")):
        write_asset(root, "rush_event_quest_folder.json", {"source": marker})
        write_asset(root, "rogue_event.json", {"source": marker})
    monkeypatch.setattr(config, "configured_path", lambda name: profile_root)
    app = SimpleNamespace(source=source(), ops=SimpleNamespace(store=DraftStore(tmp_path / "drafts")))
    routes = mode_routes.ModeRoutes(app, server_dir=explicit_root if explicit else None)
    monkeypatch.setattr(mode_routes, "freshness", lambda _: {"latest": app.source.version})
    monkeypatch.setattr(mode_checks, "freshness", lambda _: {"latest": app.source.version})
    monkeypatch.setattr(mode_rogue, "current", lambda _: {"_digest": {}, "rows": []})
    seen = []
    def preview(loader, seed, event_id, *, server_asset_reader):
        seen.append([server_asset_reader("rush_event_quest_folder.json"),
                     server_asset_reader("rogue_event.json")])
        try:
            server_asset_reader("rogue_event_cnmod.json")
        except FileNotFoundError:
            pass
        # Keep output identical: changed inputs must block on their own evidence.
        return {"ok": True, "canGenerate": True, "blockers": [], "files": {"fixture.bin": b"constant"}}
    monkeypatch.setattr(mode_rogue, "preview", preview)
    return routes, explicit_root if explicit else profile_root, seen


@pytest.mark.parametrize("explicit", [False, True])
def test_mode_routes_bind_explicit_mirror_before_profile_and_record_every_json(tmp_path, monkeypatch, explicit):
    routes, root, seen = routes_fixture(tmp_path, monkeypatch, explicit=explicit)
    _, inputs = routes.compute("rogue", {"seed": 1, "eventId": "700100"})
    assert seen == [[{"source": root.name}, {"source": root.name}]]
    assert set(inputs.inputs) == {"server:rush_event_quest_folder.json", "server:rogue_event.json",
                                  "server:rogue_event_cnmod.json"}
    assert inputs.inputs["server:rogue_event_cnmod.json"] is None


@pytest.mark.parametrize("change", ["folder", "reward", "new_extension"])
def test_json_drift_blocks_saved_preview_and_delivery_even_if_outputs_match(tmp_path, monkeypatch, change):
    routes, root, _ = routes_fixture(tmp_path, monkeypatch, explicit=True)
    routes.edit({}, {"payload": {"seed": 1, "eventId": "700100"}, "revision": 0}, "rogue", "save")
    before = json.loads(routes.read({}, "rogue").body)
    assert before["preview"]["canGenerate"]
    name = {"folder": "rush_event_quest_folder.json", "reward": "rogue_event.json",
            "new_extension": "rogue_event_cnmod.json"}[change]
    write_asset(root, name, {"changed": True})
    after = json.loads(routes.read({}, "rogue").body)
    assert not after["preview"]["canGenerate"]
    assert any(name in blocker for blocker in after["preview"]["blockers"])
    with pytest.raises(DraftError, match="草稿读取输入已变化"):
        routes.deliveries.compile_delivery("rogue", from_version=routes.app.source.version)
