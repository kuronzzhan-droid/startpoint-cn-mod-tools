"""Legacy CDN input semantics and the guarded view HTTP contract."""
import json
import zipfile

import pytest

from test_studio_chain_views import archive, chain, put, write_manifest  # noqa: F401
from test_studio_drafts import live, _request  # noqa: F401
from wf.studio.drafts import DraftStore
from wf.studio.guard import TOKEN_HEADER
from wf.studio.server import StudioApp
from wf.studio.source import StudioSource
from wf.view.base149 import HistoricalView, member
from wf.view.export import export_store
from wf.view.manifest import ManifestView


def make_view(chain, entries):
    store, manifest, zips, _ = chain
    _, edge = archive(zips, "1.4.131", "1.4.132", entries)
    write_manifest(manifest, [edge])
    return ManifestView(None, store=store, manifest=manifest, search_dirs=[zips])


def test_legacy_members_and_empty_placeholder_are_read_and_exported(chain, tmp_path):
    name = member("legacy")
    view = make_view(chain, {".empty": b"", name.removeprefix("production/upload/"): b"old-format"})
    assert set(view.index) == {name}
    assert view.read_raw("legacy")[0] == b"old-format"
    result = export_store(view, tmp_path / "export", copy=True)
    assert (tmp_path / "export" / name).read_bytes() == b"old-format"
    assert result["overlaid"] == 1 and view.verify()["tip"] == "1.4.132"


@pytest.mark.parametrize("bad", ["../.empty", "production/upload/../x", "xx/" + "f" * 38, "arbitrary.txt"])
def test_legacy_support_does_not_accept_invalid_members(chain, bad):
    with pytest.raises(ValueError, match="invalid CDN member"):
        make_view(chain, {bad: b"bad"})


def test_legacy_and_prefixed_alias_in_one_archive_is_rejected(chain):
    name = member("same")
    with pytest.raises(ValueError, match="duplicate ZIP member"):
        make_view(chain, {name: b"a", name.removeprefix("production/upload/"): b"b"})


def test_historical_numeric_parts_and_legacy_read(chain):
    store, _, zips, _ = chain
    name = member("same")
    for part in (1, 2, 10):
        with zipfile.ZipFile(zips / f"pinball-1.4.131-1.4.132-{part}-fixture.zip", "w") as stream:
            stream.writestr(name.removeprefix("production/upload/"), str(part))
            stream.writestr(".empty", "")
    view = HistoricalView(store=store, active=zips, tip=132)
    assert view.read_raw("same")[0] == b"10"
    assert [p.name.split("-")[3] for p in view.zips] == ["1", "2", "10"]


def test_view_listing_current_snapshot_and_copy_export(chain, tmp_path):
    view = make_view(chain, {member("a"): b"overlay"})
    put(chain[0], member("base"), b"baseline")
    chain[3].write_text(json.dumps({"default_view": "other", "views": {"selected": {}, "other": {}}}), "utf-8")
    view.view_name = "selected"
    app = StudioApp(StudioSource(view), drafts=DraftStore(tmp_path / "drafts"), screenshot_dirs=[])
    response = app.dispatch("GET", "/api/studio/views", {})
    listing = json.loads(response.body)
    assert listing["views"] == ["other", "selected"] and listing["current"] == "selected"
    assert listing["runtimeSwitching"] is False and listing["restartRequired"] is True
    output = tmp_path / "http-export"
    response = app.dispatch("POST", "/api/studio/views/export-store", {}, {"out": str(output), "copy": True})
    result = json.loads(response.body)
    assert response.status == 200 and result["mode"] == "copy" and result["version"] == "1.4.132"
    assert (output / member("a")).read_bytes() == b"overlay"
    assert (output / member("base")).read_bytes() == b"baseline"
    assert not app.ops.store.root.exists()
    assert app.dispatch("POST", "/api/studio/views/export-store", {}, {"out": str(output)}).status == 400
    for body in ({}, {"out": str(tmp_path / "bad"), "copy": "false"}, {"out": str(tmp_path / "bad"), "view": "other"}):
        assert app.dispatch("POST", "/api/studio/views/export-store", {}, body).status == 400
    assert not (tmp_path / "bad").exists()


@pytest.mark.parametrize("extra", [{TOKEN_HEADER: "bad"}, {"Origin": "https://evil.invalid"},
                                   {"Sec-Fetch-Site": "cross-site"}, {"Host": "evil.invalid"}])
def test_export_requires_existing_http_write_guard(live, tmp_path, extra):
    port, guard, _ = live
    output = tmp_path / "blocked-export"
    headers = {TOKEN_HEADER: guard.token, "Content-Type": "application/json", **extra}
    code, _ = _request(port, "POST", "/api/studio/views/export-store", {"out": str(output)}, headers)
    assert code == 403 and not output.exists()


def test_views_read_requires_host_guard(live):
    port, _, _ = live
    code, _ = _request(port, "GET", "/api/studio/views", headers={"Host": "evil.invalid"})
    assert code == 403
