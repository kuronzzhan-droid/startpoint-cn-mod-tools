import json
from types import SimpleNamespace

from wf.studio.freshness import freshness
from wf.studio.server import StudioApp


def test_freshness_rereads_enabled_versions_without_zips(tmp_path):
    manifest = tmp_path / "manifest.json"
    source = SimpleNamespace(version="1.4.9", view=SimpleNamespace(manifest=manifest))
    def write(version):
        manifest.write_text(json.dumps({"patches": [
            {"version": version, "enabled": True}, {"version": "1.4.99", "enabled": False}]}))
    write("1.4.9")
    assert freshness(source) == {"loaded": "1.4.9", "latest": "1.4.9", "stale": False}
    write("1.4.10")
    assert freshness(source) == {"loaded": "1.4.9", "latest": "1.4.10", "stale": True}
    source.version = "1.4.11"  # Explicit overlays may be ahead of the manifest.
    assert not freshness(source)["stale"]


def test_no_manifest_and_read_failures_are_http_200(tmp_path):
    source = SimpleNamespace(version="1.4.9", view=SimpleNamespace())
    app = StudioApp(source)
    def read():
        response = app.dispatch("GET", "/api/studio/freshness", {})
        assert response.status == 200
        return json.loads(response.body)
    assert read() == {"loaded": "1.4.9", "latest": None, "stale": False}
    source.view.manifest = tmp_path / "missing.json"
    assert "error" in read()
    source.view.manifest.write_text("{invalid")
    assert "error" in read()
    source.view.manifest.write_text('{"patches":[{"version":"bad"}]}')
    assert "error" in read()


def test_supplemental_manifest(tmp_path):
    main, extra = tmp_path / "manifest.json", tmp_path / "extra.json"
    main.write_text('{"patches":[]}')
    extra.write_text('{"version":"1.4.12"}')
    source = SimpleNamespace(version="1.4.10", view=SimpleNamespace(manifest=main, manifests=[extra]))
    assert freshness(source)["latest"] == "1.4.12"
