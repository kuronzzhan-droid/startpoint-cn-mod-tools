"""Delivery uses the editor's full view and verifies extra dependency edges."""
import copy
import json
import zipfile

import pytest

from wf.studio import deliver_bridge
from wf.studio.drafts import DraftStore
from wf.studio.server import StudioApp
from wf.studio.source import StudioSource
from wf.view import ManifestView
from wf.view.base149 import member
from wf.view.overlays import locked_delivery_tip
from test_studio_chain_views import archive, chain, write_manifest


@pytest.fixture
def baseline(chain):
    store, manifest, zips, _ = chain
    _, edge = archive(zips, "1.4.150", "1.4.151", {member("data"): b"base"})
    write_manifest(manifest, [edge])

    def build(names):
        extras = []
        for index, name in enumerate(names):
            target = zips / name
            with zipfile.ZipFile(target, "w") as stream:
                stream.writestr(member("data"), f"extra-{index}".encode())
            extras.append(target)
        return ManifestView("1.4.151", store=store, manifest=manifest, search_dirs=[zips],
                            base_version="1.4.150", extra_zips=extras)
    return build


PARTS = ["pinball-1.4.151-1.4.155-1-first.zip", "pinball-1.4.151-1.4.155-2-second.zip"]


def test_delivery_effective_version_preserves_lock_cutoff(baseline):
    view = baseline(PARTS + ["pinball-1.4.155-1.4.158-1-third.zip"])
    assert StudioSource(view).version == view.effective_version == "1.4.158"
    assert view.tip == view.lock_data()["tip"] == "1.4.151"
    assert locked_delivery_tip(view.lock_data()) == "1.4.158"
    assert deliver_bridge.open_baseline("1.4.158", "1.4.159", baseline_view=view) is view
    assert view.read_raw("data")[0] == b"extra-2"


@pytest.mark.parametrize("names,error", [
    (["pinball-1.4.154-1.4.155-1-gap.zip"], "not continuous"),
    (["pinball-1.4.151-1.4.150-1-backward.zip"], "not continuous"),
    (["pinball-1.4.151-1.4.151-1-recast.zip"], "not continuous"),
    ([PARTS[1]], "missing or unordered"),
    ([PARTS[0], "pinball-1.4.151-1.4.155-3-gap.zip"], "missing or unordered"),
    ([PARTS[0], "pinball-1.4.151-1.4.155-1-duplicate.zip"], "missing or unordered"),
    (["unversioned.zip"], "versioned pinball"),
])
def test_delivery_rejects_unproven_extra_chain(baseline, names, error):
    view = baseline(names)
    with pytest.raises(ValueError, match=error):
        deliver_bridge.open_baseline(view.effective_version, "1.4.160", baseline_view=view)
    with pytest.raises(ValueError, match=error):
        locked_delivery_tip(view.lock_data())


def test_effective_from_and_portable_lock_endpoint_are_bound(baseline):
    view = baseline(PARTS)
    with pytest.raises(ValueError, match="tip must equal"):
        deliver_bridge.open_baseline("1.4.151", "1.4.156", baseline_view=view)
    lock = copy.deepcopy(view.lock_data())
    lock["tip"] = "1.4.153"
    with pytest.raises(ValueError, match="not on the locked ZIP chain"):
        locked_delivery_tip(lock)
    empty = {"schema": "wf-view-lock/1", "base_version": "1.4.155", "tip": "1.4.155", "zips": []}
    assert locked_delivery_tip(empty) == "1.4.155"


@pytest.mark.parametrize("fault,error", [("occupied", "already occupied"), ("stale", "is stale"),
                                         ("drift", "changed during use")])
def test_extra_views_retain_existing_manifest_and_sha_guards(baseline, fault, error):
    view = baseline(PARTS)
    if fault == "drift":
        with zipfile.ZipFile(view.extra_zips[-1], "w") as stream:
            stream.writestr(member("data"), b"drift")
    else:
        document = json.loads(view.manifest.read_text("utf-8"))
        document["patches"].append({"version": "1.4.160" if fault == "occupied" else "1.4.159",
                                    "depends_on": "1.4.155", "enabled": fault == "stale"})
        view.manifest.write_text(json.dumps(document), "utf-8")
    with pytest.raises(ValueError, match=error):
        deliver_bridge.open_baseline("1.4.155", "1.4.160", baseline_view=view)


@pytest.mark.parametrize("route", ["/api/drafts/139985/build", "/api/boss/drafts/139985/build",
                                   "/api/studio/weapons/drafts/139985/build"])
def test_http_build_passes_exact_view_store_base_and_extras(baseline, tmp_path, monkeypatch, route):
    view = baseline(PARTS)
    server = tmp_path / "server"
    app = StudioApp(StudioSource(view), drafts=DraftStore(tmp_path / "drafts"), server_dir=server)
    seen = []

    def build(cid, *, from_version, to_version, **options):
        assert options["baseline_view"] is view
        assert options["base_store"] == view.store
        assert options["base_version"] == "1.4.150"
        assert options["server_dir"] == server
        bound = deliver_bridge.open_baseline(from_version, to_version, **options)
        assert bound.read_raw("data")[0] == b"extra-1"
        seen.append(bound)
        return {"ok": True, "from": from_version, "to": to_version}

    monkeypatch.setattr(deliver_bridge, "build_draft", build)
    response = app.dispatch("POST", route, {}, {"to": "1.4.156"})
    assert response.status == 200
    result = json.loads(response.body)
    assert result["ok"] and result["from"] == "1.4.155"
    assert seen == [view]


def test_non_manifest_source_preserves_opaque_version():
    from types import SimpleNamespace
    assert StudioSource(SimpleNamespace(tip="test", zips=[])).version == "test"


def test_legacy_default_manifest_keeps_configured_supplemental_chain(chain, tmp_path, monkeypatch):
    from wf.studio.build_view import baseline_from_args
    from wf.studio.draft import build_parser
    store, manifest, zips, profile = chain
    _, first = archive(zips, "1.4.150", "1.4.151", {member("data"): b"first"})
    _, second = archive(zips, "1.4.151", "1.4.152", {member("data"): b"second"})
    write_manifest(manifest, [first])
    supplemental = tmp_path / "supplemental.json"
    write_manifest(supplemental, [second])
    profile.write_text(json.dumps({"view": {"manifests": [str(supplemental)]}}), "utf-8")
    monkeypatch.setattr("wf.studio.build_view.default_chain_settings", lambda: (manifest, [zips]))
    args = build_parser().parse_args(["--store", str(store), "--view-base-version", "1.4.150",
        "build", "139985", "--from", "1.4.152", "--to", "1.4.153", "--out", str(tmp_path / "build")])
    view = baseline_from_args(args)
    assert view.manifests == [supplemental] and view.effective_version == "1.4.152"
    assert view.read_raw("data")[0] == b"second"
