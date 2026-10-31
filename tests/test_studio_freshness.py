import json
from types import SimpleNamespace

import pytest

from wf.studio.freshness import freshness
from wf.studio.server import StudioApp


def test_freshness_rereads_enabled_versions_without_zips(tmp_path):
    manifest = tmp_path / "manifest.json"
    source = SimpleNamespace(version="1.4.9", view=SimpleNamespace(manifest=manifest, base_version="1.4.8"))
    def write(version):
        manifest.write_text(json.dumps({"patches": [
            {"version": version, "enabled": True, "depends_on": "1.4.8",
             "archive": f"pinball-1.4.8-{version}-1-test.zip"},
            {"version": "1.4.99", "enabled": False}]}))
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
    extra.write_text('{"version":"1.4.12", "depends_on":"1.4.10", "archive":"pinball-1.4.10-1.4.12-1-test.zip"}')
    source = SimpleNamespace(version="1.4.10", view=SimpleNamespace(manifest=main, manifests=[extra], base_version="1.4.10"))
    assert freshness(source)["latest"] == "1.4.12"


@pytest.mark.parametrize("enabled", [0, None, "true"])
def test_invalid_enabled_is_error_without_partial_result(tmp_path, enabled):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"patches": [{"version": "1.4.132", "enabled": enabled}]}))
    result = freshness(SimpleNamespace(version="1.4.131", view=SimpleNamespace(manifest=manifest)))
    assert "error" in result and result["latest"] is None and not result["stale"]


def test_conflicting_disabled_version_is_error(tmp_path):
    main, extra = tmp_path / "main.json", tmp_path / "extra.json"
    main.write_text('{"patches":[{"version":"1.4.132", "enabled":false}]}')
    extra.write_text('{"version":"1.4.132", "enabled":true, "depends_on":"1.4.131", "archive":"pinball-1.4.131-1.4.132-1-test.zip"}')
    result = freshness(SimpleNamespace(version="1.4.131", view=SimpleNamespace(manifest=main, manifests=[extra])))
    assert "conflicting manifest enabled state" in result["error"]
    assert result["latest"] is None and not result["stale"]


def test_cdn_header_and_opaque_loaded_version(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text('{"cdn_version":"1.4.140", "patches":[]}')
    source = SimpleNamespace(version="1.4.131", view=SimpleNamespace(manifest=manifest))
    assert freshness(source) == {"loaded": "1.4.131", "latest": "1.4.140", "stale": True}
    source.version = "overlay"
    result = freshness(source)
    assert "error" in result and result["latest"] is None and not result["stale"]
