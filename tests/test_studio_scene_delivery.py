"""Scene delivery integration: synthetic inputs, real archive/check pipeline."""
import copy
import json
import zipfile
from types import SimpleNamespace

import pytest

from test_studio_deliver_bridge import case as bridge_case
from wf.deliver.changeset import member_name, sha256
from wf.studio.drafts import DraftError, DraftStore
from wf.studio.scene_routes import SceneRoutes
from wf.studio.source import StudioSource


@pytest.fixture
def scene_delivery(tmp_path, monkeypatch):
    # No machine configuration, APK, source store or real service is required.
    profile = tmp_path / "profile.json"
    profile.write_text("{}", encoding="utf8")
    monkeypatch.setenv("WF_PATHS_PROFILE", str(profile))
    _, _, view, out = bridge_case.__wrapped__(tmp_path, monkeypatch)
    source = StudioSource(view)
    routes = SceneRoutes(SimpleNamespace(source=source, ops=SimpleNamespace(
        store=DraftStore(tmp_path / "scene-drafts"))))
    computed = {"ok": True, "canGenerate": True, "blockers": [],
                "files": {"test.bin": b"scene candidate"}, "servers": {}, "serverBefore": {},
                "changes": [{"table": "test.bin", "path": [], "resource": True,
                             "old": sha256(b"old"), "new": sha256(b"scene candidate")}],
                "checks": [{"rule": "scene.spec", "status": "满足", "message": "合成编译证据", "blocking": False}],
                "outputSha256": {"test.bin": sha256(b"scene candidate")}}
    inputs = SimpleNamespace(inputs={"common:test.bin": sha256(b"old")}, verify=view.verify)
    monkeypatch.setattr(routes, "compute", lambda *args: (copy.deepcopy(computed), inputs))
    routes.store.save("hell-pumpkin", source.version, {"fixture": True}, inputs.inputs,
                      routes.public(computed), 0)
    return routes, computed, inputs, out


def build(scene_delivery):
    routes, _, _, out = scene_delivery
    return routes.deliveries.compile_delivery("hell-pumpkin", from_version="1.4.132",
        to_version="1.4.133", out=out, apk=[])


def test_studio_scene_delivery_real_zip_checks_and_shared_root_preservation(scene_delivery):
    routes, _, _, out = scene_delivery
    report = build(scene_delivery)
    assert report["ok"] and report["prepush"]["exit_code"] == 0
    delivery = out / "delivery"
    manifest = json.loads((delivery / "delivery-manifest.json").read_text("utf8"))
    assert manifest["from_version"] == "1.4.132" and manifest["to_version"] == "1.4.133"
    with zipfile.ZipFile(next(delivery.glob("pinball-*.zip"))) as archive:
        assert archive.namelist() == [member_name("common", "test.bin")]
        assert archive.read(archive.namelist()[0]) == b"scene candidate"
    assert routes.app.source.view.read_member(member_name("common", "test.bin"))[0] == b"old"
    assert routes.app.source.view.read_member(member_name("medium", "test.bin"))[0] == b"untouched other layer"
    assert (delivery / "check.json").is_file() and (delivery / "key-diff.json").is_file()
    assert not any(check.get("blocking") for check in json.loads((delivery / "check.json").read_text("utf8"))["results"])


@pytest.mark.parametrize("mutate, message", [
    (lambda r, c, i: c.update(canGenerate=False, blockers=["真实阻断"]), "真实阻断"),
    (lambda r, c, i: c["outputSha256"].update({"test.bin": "0" * 64}), "构建结果变化"),
    (lambda r, c, i: i.inputs.update({"common:test.bin": "0" * 64}), "规格输入"),
    (lambda r, c, i: c["serverBefore"].update({"assets/example.json": "0" * 64}), "服务端镜像已变化"),
])
def test_studio_scene_delivery_rechecks_saved_evidence_before_writing(scene_delivery, mutate, message):
    routes, computed, inputs, out = scene_delivery
    mutate(routes, computed, inputs)
    with pytest.raises(DraftError, match=message):
        build(scene_delivery)
    assert not out.exists()


def test_studio_scene_delivery_does_not_add_server_write_aliases(scene_delivery):
    routes = scene_delivery[0].routes()
    for action in ("apply", "unapply"):
        path = "/api/scenes/deliveries/hell-pumpkin-1.4.132-to-1.4.133-20261102-120000/" + action
        assert not any(verb == "POST" and pattern.fullmatch(path) for verb, pattern, _ in routes)
