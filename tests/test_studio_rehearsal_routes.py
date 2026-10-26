"""CLI, real guarded HTTP and automatic post-build rehearsal integration."""
import http.client
import json
import threading
from http.server import ThreadingHTTPServer

import pytest

from test_studio_rehearsal import case, put
from test_studio_deliver_routes import _FakeSource
from wf.studio.deliver_routes import DeliverRoutes
from wf.studio.draft import main
from wf.studio.drafts import DraftStore
from wf.studio.guard import WriteGuard
from wf.studio.server import StudioApp, make_handler


def test_cli_exit_and_json(case, capsys):
    _, folder, _ = case
    assert main(["rehearse", "--delivery-dir", str(folder), "--server", "local"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["result"]["status"] == "ready"
    assert main(["rehearse", "--delivery-dir", str(folder), "--server", "missing"]) == 1
    assert not json.loads(capsys.readouterr().out)["ok"]


def test_guarded_http_post_and_latest_detail(case, tmp_path):
    _, folder, profile = case
    name = "199000-1.4.9-to-1.4.10-20261026-120000"
    target = folder.parent.parent / name
    folder.parent.rename(target)
    app = StudioApp(_FakeSource(), drafts=DraftStore(tmp_path / "drafts"))
    routes = DeliverRoutes(app, root=target.parent)
    app.routes = routes.routes()
    guard = WriteGuard(0)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app, tmp_path, guard))
    port = httpd.server_address[1]
    guard.port = port
    guard.hosts = {f"127.0.0.1:{port}"}
    guard.origins = {f"http://127.0.0.1:{port}"}
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    connection = http.client.HTTPConnection("127.0.0.1", port)
    try:
        endpoint = f"/api/deliveries/{name}/rehearse"
        headers = {"Content-Type": "application/json"}
        connection.request("POST", endpoint, '{"server":"local"}', headers)
        response = connection.getresponse()
        assert response.status == 403
        response.read()
        headers["X-WF-Studio-Token"] = guard.token
        headers["Origin"] = "https://invalid.example"
        connection.request("POST", endpoint, '{"server":"local"}', headers)
        response = connection.getresponse()
        assert response.status == 403
        response.read()
        headers.pop("Origin")
        connection.request("GET", f"/api/deliveries/{name}")
        response = connection.getresponse()
        assert json.loads(response.read())["rehearsal"] is None
        connection.request("POST", endpoint, '{"server":"local"}', headers)
        response = connection.getresponse()
        assert response.status == 200
        posted = json.loads(response.read())["rehearsal"]
        assert posted["ok"]
        connection.request("GET", f"/api/deliveries/{name}")
        response = connection.getresponse()
        assert json.loads(response.read())["rehearsal"] == posted
        connection.request("POST", endpoint, '{"server":"local","root":"elsewhere"}', headers)
        response = connection.getresponse()
        assert response.status == 400
        response.read()
    finally:
        connection.close()
        httpd.shutdown()
        httpd.server_close()
        thread.join()


def test_auto_rehearsal_real_build(tmp_path, monkeypatch):
    # Reuse the small existing delivery fixture without stubbing the build pipeline.
    from test_studio_deliver_bridge import case as bridge_case, build
    case_data = bridge_case.__wrapped__(tmp_path, monkeypatch)
    root = tmp_path / "server"
    (root / "assets/asset-patch/active").mkdir(parents=True)
    put(root / "assets/asset-patch/manifest.json", {"cdn_version": "1.4.132", "patches": [
        {"version": "1.4.132", "depends_on": "1.4.131", "enabled": True}]})
    profile = tmp_path / "profile.json"
    put(profile, {"servers": {"local": {"root": str(root)}}, "rehearsal_server": "local"})
    monkeypatch.setenv("WF_PATHS_PROFILE", str(profile))
    result = build(case_data, allow_unknown_client=True)
    assert result["ok"]  # build success is independent from server applicability
    assert not result["rehearsal"]["ok"]  # current studio candidate carries local_test_only
    assert any(c["rule"] == "rehearsal.local-test-only" and c["blocking"]
               for c in result["rehearsal"]["checks"])
    folder = case_data[-1] / "delivery"
    assert (folder / "rehearsal-local.json").is_file()
    assert "rehearsal-" not in (folder / "SHA256SUMS").read_text("utf-8")
    assert json.loads((case_data[-1] / "build-report.json").read_text("utf-8"))["rehearsal"] == result["rehearsal"]
