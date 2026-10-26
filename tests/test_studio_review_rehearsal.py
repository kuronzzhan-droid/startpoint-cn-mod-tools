"""Regression cases for unsafe rehearsal evidence and path boundaries."""
import json
import pytest

from test_studio_rehearsal import case, put, snapshot  # noqa: F401
from wf.studio.rehearsal import rehearse
from wf.studio.rehearsal_server import chain_tail
from wf.studio.drafts import DraftError


def test_legacy_targets_require_explicit_mapping_and_check_all_mirrors(case):
    root, folder, _ = case
    put(folder / "server-entries/cdndata/character.json", {"199001": "same"})
    put(root / "assets/cdndata/character_cnmod.json", {"199001": "same", "keep": 3})
    before = snapshot(root)
    blocked = rehearse(folder)
    assert not blocked["ok"] and blocked["manifestEntry"] is None
    put(folder / "server-entries/merge-manifest.json", {
        "targets": {"cdndata/character.json": ["assets/cdndata/character_cnmod.json"]},
        "operations": [{"file": "cdndata/character.json", "operation": "append_object_keys",
                        "object_pointer": "", "keys": ["199001"]}]})
    result = rehearse(folder)
    assert not result["ok"] and not result["manifestEntryJson"]
    change = result["serverChanges"][0]
    assert change["target"].endswith("character_cnmod.json")
    assert change["unchangedKeys"] == ["/199001"]
    assert change["existingClaimedKeys"] == ["/199001"]
    assert not change["changed"] and snapshot(root) == before


def test_unrelated_invalid_server_profile_does_not_abort_report(case):
    _, folder, profile = case
    data = json.loads(profile.read_text("utf-8"))
    data["servers"].update(broken="not an object", missing={})
    put(profile, data)
    result = rehearse(folder)
    assert result["ok"] and (folder / "rehearsal-local.json").is_file()


@pytest.mark.parametrize("mutation", ["implicit", "string", "type", "backward", "order"])
def test_chain_does_not_sort_or_coerce_enabled_entries(mutation):
    patches = [{"version": "1.4.9", "depends_on": "1.4.8", "enabled": True, "type": "patch"},
               {"version": "1.4.10", "depends_on": "1.4.9", "enabled": True, "type": "patch"}]
    if mutation == "implicit":
        del patches[1]["enabled"]
    elif mutation == "string":
        patches[1]["enabled"] = "false"
    elif mutation == "type":
        patches[1]["type"] = "notice"
    elif mutation == "backward":
        patches[0]["depends_on"] = "1.4.9"
    else:
        patches.reverse()
    with pytest.raises(DraftError):
        chain_tail({"cdn_version": "1.4.10", "patches": patches})


def test_nested_metadata_outside_zip_and_sidecar_flags(case, tmp_path):
    _, folder, _ = case
    names = [p.name for p in sorted(folder.glob("*.zip"))]
    put(folder / "meta/entry.json", {"id": "nested", "name": "Nested", "chain": names,
                                    "version": "1.4.10", "depends_on": "1.4.9"})
    put(folder / "delivery-manifest.json", {"legacy_manifest": "meta/entry.json",
                                          "archives": [{"name": n} for n in names]})
    result = rehearse(folder)
    assert result["ok"] and result["manifestEntry"]["id"] == "nested"
    external = tmp_path / names[0]
    external.write_bytes((folder / names[0]).read_bytes())
    assert not rehearse(folder, zips=[external])["ok"]
    put((folder / names[0]).with_suffix(".integrity.json"), {"local_test_only": True})
    result = rehearse(folder)
    assert not result["ok"] and result["manifestEntry"] is None


def test_array_report_is_append_only_and_blocked_manual_uses_current_tail(case):
    root, folder, _ = case
    put(root / "assets/ids.json", [1, 2])
    put(folder / "server-entries/ids.json", [2, 3])
    result = rehearse(folder)
    change = result["serverChanges"][0]
    assert change["appendValues"] == [3] and change["omittedValues"] == [1]
    assert change["replacedKeys"] == []
    put(root / "assets/asset-patch/manifest.json", {"cdn_version": "1.4.11", "patches": [
        {"version": "1.4.11", "depends_on": "1.4.9", "enabled": True, "type": "patch"}]})
    result = rehearse(folder)
    assert result["manifestEntry"] is None and not result["manifestEntryJson"]
    assert "1.4.11" in (folder / "rehearsal-local.md").read_text("utf-8")


@pytest.mark.parametrize("failed", [False, True])
def test_automatic_rehearsal_cannot_hide_build_reports(tmp_path, monkeypatch, failed):
    from test_studio_deliver_bridge import case as bridge_case, build
    from wf.studio import deliver_bridge
    fixture = bridge_case.__wrapped__(tmp_path, monkeypatch)
    calls = []

    def broken(*args):
        calls.append(True)
        raise ValueError("rehearsal fixture failure")

    monkeypatch.setattr("wf.studio.rehearsal.auto_rehearse", broken)
    if failed:
        monkeypatch.setattr(deliver_bridge, "build_delivery", lambda *a, **kw: (_ for _ in ()).throw(ValueError("build gate failed")))
    result = build(fixture, allow_unknown_client=True)
    assert bool(calls) is not failed
    assert result["ok"] is not failed
    assert (fixture[-1] / "build-report.json").is_file()
    assert (fixture[-1] / "delivery/SHA256SUMS").is_file()
    assert result["rehearsal"] is None if failed else result["rehearsal"]["status"] == "blocked"


def test_rehearsal_io_does_not_hold_global_route_lock(tmp_path, monkeypatch):
    import threading
    from types import SimpleNamespace
    from wf.studio.deliver_routes import DeliverRoutes
    routes = DeliverRoutes(SimpleNamespace(), root=tmp_path)
    entered, release = threading.Event(), threading.Event()
    monkeypatch.setattr(routes, "_folder", lambda _: tmp_path)

    def slow(*args):
        entered.set()
        assert release.wait(5)
        return {"ok": True}

    monkeypatch.setattr("wf.studio.rehearsal.rehearse", slow)
    worker = threading.Thread(target=lambda: routes.rehearse({}, {"server": "local"}, "fixture"))
    worker.start()
    try:
        assert entered.wait(5)
        assert routes._lock.acquire(timeout=1)
        routes._lock.release()
        with pytest.raises(DraftError):
            routes.rehearse({}, {"server": "local"}, "fixture")
    finally:
        release.set()
        worker.join(5)
    assert not worker.is_alive() and not routes._rehearsing
