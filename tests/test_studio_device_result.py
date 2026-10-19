"""编辑台：交付的真机实测记录（device-result.json）读写、导入、过期判定与截图白名单。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from test_studio_drafts import _request, live  # noqa: F401 - fixture
from wf.studio import device_result as R
from wf.studio import draft
from wf.studio import drafts as D
from wf.studio.guard import TOKEN_HEADER

NAME = "139985-1.4.251-to-1.4.252-20261019-182403"
BOSS = "hard_multi_1001_1-1.4.252-to-1.4.253-20261019-183035"
SHA = "4" * 64

LEGACY = {
    "schema": "wf-device-result/1",
    "target": {"server": "本机服", "device": "MuMu 实例 1「MuMu安卓设备-1」com.leiting.wf",
               "apk": "local.apk", "apk_sha256": "6" * 64, "client_res_version_before": "1.4.251",
               "client_profile_used": "test-v35e", "extra_key": 1},
    "recordedAt": "2026-10-19T18:55+11:00", "error_codes": [], "error_scan": "无 [CRASH]",
    "status": "通过", "edge": "1.4.252（本地 local_test_only）",
    "checks": [{"what": "能力 5 文案", "expect": "+30%", "result": "通过：显示 +30%", "screenshot": "SHOT"},
               {"what": "数值", "expect": "+30%/层", "result": "未单独验证"}],
    "screenshots": ["SHOT"],
}


def make_delivery(root: Path, name=NAME, revision=1, sha=SHA) -> Path:
    folder = root / name
    (folder / "delivery").mkdir(parents=True)
    (folder / "build-report.json").write_text(json.dumps(
        {"ok": True, "from": "1.4.251", "to": "1.4.252", "draftRevision": revision}), "utf-8")
    (folder / "delivery" / "delivery-manifest.json").write_text(json.dumps(
        {"archives": [{"name": "a.zip", "size": 3, "sha256": sha, "members": 1, "files": ["m"]}]}), "utf-8")
    return folder


def record(**extra):
    return {"status": "通过", "testedAt": "2026-10-19T19:00", "tester": "作者",
            "device": {"id": "MuMu-1", "emulator": True, "package": "com.leiting.wf"},
            "client": {"versionBefore": "1.4.251", "versionAfter": "1.4.252"},
            "chainEdges": [{"version": "1.4.252"}],
            "checks": [{"item": "面板文案", "expected": "+30%", "observed": "+30%", "status": "通过"}],
            "restore": {"method": "恢复边", "edges": ["1.4.254"], "verified": True}, **extra}


def test_schema_is_valid_and_lists_four_statuses():
    import jsonschema
    jsonschema.Draft202012Validator.check_schema(R.schema())
    assert R.schema()["$defs"]["status"]["enum"] == ["通过", "失败", "未执行", "作废"]


def test_legacy_v1_is_normalized_without_losing_fields():
    result, legacy = R.normalize(LEGACY)
    assert legacy and result["schema"] == R.SCHEMA_ID and result["status"] == "通过"
    assert result["testedAt"] == "2026-10-19T18:55+11:00"
    assert result["device"]["package"] == "com.leiting.wf" and result["device"]["emulator"] is True
    assert result["client"] == {"versionBefore": "1.4.251", "profile": "test-v35e"}
    assert result["chainEdges"][0]["version"] == "1.4.252"
    first, second = result["checks"]
    assert (first["item"], first["expected"], first["status"], first["screenshot"]) == ("能力 5 文案", "+30%", "通过", "SHOT")
    assert second["status"] == "未执行"
    assert result["extra"] == {"target.extra_key": 1}
    voided, _ = R.normalize({**LEGACY, "status": "未执行", "reason": "已作废：改为重新生成"})
    assert voided["status"] == "作废"
    with pytest.raises(D.DraftError):
        R.normalize({"schema": "wf-device-result/9"})


def test_write_binds_to_delivery_and_keeps_history(tmp_path):
    folder = make_delivery(tmp_path)
    forged = record(delivery={"name": "other", "kind": "boss", "draftRevision": 99})
    result = R.write(folder, "character", forged)
    assert result["delivery"]["name"] == NAME and result["delivery"]["draftRevision"] == 1
    assert result["delivery"]["archives"] == [{"name": "a.zip", "sha256": SHA}] and result["recordedAt"]
    R.write(folder, "character", record(status="失败"))
    entry = R.read(folder, "character")
    assert entry["result"]["status"] == "失败" and entry["history"] == 1 and not entry["errors"]
    with pytest.raises(D.DraftError, match="schema"):
        R.write(folder, "character", record(status="大概通过"))
    with pytest.raises(D.DraftError, match="schema"):
        R.write(folder, "character", {**record(), "checks": [{"item": "x", "unknown": 1}]})


def test_write_refuses_unfinished_delivery(tmp_path):
    folder = tmp_path / NAME
    folder.mkdir()
    with pytest.raises(D.DraftError, match="build-report"):
        R.write(folder, "character", record())


def test_import_checks_archive_identity(tmp_path):
    source = make_delivery(tmp_path / "other-worktree")
    (source / "device-result.json").write_text(json.dumps(LEGACY, ensure_ascii=False), "utf-8")
    target = make_delivery(tmp_path / "here")
    result = R.import_file(source, target, "character")
    assert result["importedFrom"]["archivesMatch"] is True and result["importedFrom"]["schema"] == R.LEGACY_ID
    assert result["checks"][0]["item"] == "能力 5 文案"
    assert R.read(target, "character")["legacy"] is False
    different = make_delivery(tmp_path / "there", sha="5" * 64)
    with pytest.raises(D.DraftError, match="不一致"):
        R.import_file(source / "device-result.json", different, "character")
    loose = tmp_path / "loose"
    loose.mkdir()
    (loose / "device-result.json").write_text(json.dumps(LEGACY), "utf-8")
    with pytest.raises(D.DraftError, match="allowUnverified"):
        R.import_file(loose, target, "character")
    assert R.import_file(loose, target, "character", allow_unverified=True)["importedFrom"]["archivesMatch"] is None


def test_recreated_draft_with_same_revision_is_stale(tmp_path):
    folder = make_delivery(tmp_path)
    (folder / "inputs").mkdir()
    (folder / "inputs" / "draft.json").write_text(json.dumps({"createdAt": "2026-10-19T18:23:19+11:00", "revision": 1}), "utf-8")
    result = R.write(folder, "character", record())
    assert result["delivery"]["draftCreatedAt"] == "2026-10-19T18:23:19+11:00"
    assert R.stale(result, {"revision": 1, "createdAt": "2026-10-19T18:23:19+11:00"}) is False
    assert R.stale(result, {"revision": 2, "createdAt": "2026-10-19T18:23:19+11:00"}) is True
    assert R.stale(result, {"revision": 1, "createdAt": "2026-10-20T09:00:00+11:00"}) is True
    assert R.stale(result, None) is False


def test_read_reports_corrupt_and_copied_files(tmp_path):
    folder = make_delivery(tmp_path)
    (folder / "device-result.json").write_text("{", "utf-8")
    entry = R.read(folder, "character")
    assert entry["result"] is None and entry["errors"]
    assert R.summary(entry)["status"] == "无效"
    other = make_delivery(tmp_path / "x", sha="7" * 64)
    R.write(other, "character", record())
    (folder / "device-result.json").write_bytes((other / "device-result.json").read_bytes())
    assert R.read(folder, "character")["bindingMismatch"] is True


def test_screenshot_whitelist(tmp_path):
    allowed = tmp_path / "Pictures"
    allowed.mkdir()
    (allowed / "a.png").write_bytes(b"\x89PNG")
    (tmp_path / "secret.png").write_bytes(b"x")
    (allowed / "notes.txt").write_text("x")
    shots = R.Screenshots([allowed])
    assert shots.read(str(allowed / "a.png")) == (b"\x89PNG", "image/png")
    for bad in (str(tmp_path / "secret.png"), str(allowed / ".." / "secret.png"), str(allowed / "notes.txt"), ""):
        with pytest.raises(PermissionError):
            shots.read(bad)
    with pytest.raises(FileNotFoundError):
        shots.read(str(allowed / "missing.png"))
    items = shots.annotate({"screenshots": [str(allowed / "a.png")],
                            "checks": [{"item": "x", "screenshot": str(tmp_path / "secret.png")}]})
    assert [(i["allowed"], i["exists"]) for i in items] == [(True, True), (False, False)]


def test_screenshot_dirs_from_profile_and_env(tmp_path, monkeypatch):
    profile = tmp_path / "local.json"
    profile.write_text(json.dumps({"wf_root": str(tmp_path), "paths": {"studio_screenshots": ["shots", str(tmp_path / "abs")]}}), "utf-8")
    monkeypatch.setenv("WF_PATHS_PROFILE", str(profile))
    monkeypatch.setenv("WF_STUDIO_SCREENSHOTS", str(tmp_path / "env"))
    dirs = R.configured_screenshot_dirs([tmp_path / "cli"])
    assert dirs == [(tmp_path / n).resolve() for n in ("env", "shots", "abs", "cli")]


def _headers(guard):
    return {TOKEN_HEADER: guard.token, "Content-Type": "application/json"}


def test_http_write_read_import_and_stale(live, tmp_path):  # noqa: F811
    port, guard, app = live
    app.deliveries.root = tmp_path / "deliveries"
    folder = make_delivery(app.deliveries.root)
    shots = tmp_path / "Pictures"
    shots.mkdir()
    (shots / "s.png").write_bytes(b"\x89PNGdata")
    app.screenshots = R.Screenshots([shots])
    url = f"/api/drafts/139985/deliveries/{NAME}/device-result"
    assert _request(port, "POST", url, record(), {"Content-Type": "application/json"})[0] == 403
    status, body = _request(port, "POST", url, record(screenshots=[str(shots / "s.png")]), _headers(guard))
    assert status == 200, body
    entry = json.loads(body)["deviceResult"]
    assert entry["result"]["status"] == "通过" and entry["screenshots"][0]["allowed"]
    assert entry["stale"] is False and entry["currentRevision"] is None
    # Ownership: a delivery of another character cannot be written through this draft id.
    status, body = _request(port, "POST", f"/api/drafts/139986/deliveries/{NAME}/device-result", record(), _headers(guard))
    assert status == 400 and "不属于" in json.loads(body)["error"]
    status, body = _request(port, "GET", f"/api/deliveries/{NAME}/device-result")
    assert status == 200 and json.loads(body)["deviceResult"]["result"]["tester"] == "作者"
    detail = json.loads(_request(port, "GET", f"/api/deliveries/{NAME}")[1])
    assert detail["deviceValidation"] == "通过" and detail["deviceResult"]["result"]["checks"]
    status, data = _request(port, "GET", "/api/device-screenshots?path=" + str(shots / "s.png"))
    assert status == 200 and data == b"\x89PNGdata"
    assert _request(port, "GET", "/api/device-screenshots?path=" + str(folder / "build-report.json"))[0] == 403
    # The draft moved on after the test: the result is reported as expired.
    store = app.ops.store
    (store.root / "139985").mkdir(parents=True)
    (store.root / "139985" / "changeset.json").write_text(json.dumps({"revision": 4, "changes": []}), "utf-8")
    listing = json.loads(_request(port, "GET", "/api/deliveries?cid=139985")[1])
    assert listing["currentRevision"] == 4
    assert listing["deliveries"][0]["device"]["status"] == "通过" and listing["deliveries"][0]["device"]["draftRevision"] == 1
    assert listing["deliveries"][0]["device"]["stale"] is True
    assert json.loads(_request(port, "GET", f"/api/deliveries/{NAME}/device-result")[1])["deviceResult"]["stale"] is True
    # Import by path from a sibling worktree.
    source = make_delivery(tmp_path / "elsewhere")
    (source / "device-result.json").write_text(json.dumps(LEGACY, ensure_ascii=False), "utf-8")
    status, body = _request(port, "POST", url + "/import", {"path": str(source)}, _headers(guard))
    assert status == 200, body
    assert json.loads(body)["deviceResult"]["result"]["importedFrom"]["delivery"] == NAME
    status, body = _request(port, "POST", url + "/import", {}, _headers(guard))
    assert status == 400


def test_http_boss_namespace(live, tmp_path):  # noqa: F811
    port, guard, app = live
    root = app.boss.deliveries.root = tmp_path / "boss"
    make_delivery(root, BOSS)
    url = f"/api/boss/drafts/hard_multi:1001%2F1/deliveries/{BOSS}/device-result"
    status, body = _request(port, "POST", url, record(), _headers(guard))
    assert status == 200, body
    assert json.loads(body)["deviceResult"]["result"]["delivery"]["kind"] == "boss"
    status, body = _request(port, "GET", f"/api/boss/deliveries/{BOSS}/device-result")
    assert status == 200 and json.loads(body)["deviceResult"]["result"]["status"] == "通过"
    listing = json.loads(_request(port, "GET", "/api/boss/deliveries?cid=hard_multi:1001%2F1")[1])
    assert listing["deliveries"][0]["device"]["status"] == "通过"


def _cli(argv, capsys):
    code = draft.main(argv)
    return code, json.loads(capsys.readouterr().out)


def test_cli_show_write_import(tmp_path, capsys):
    root = tmp_path / "deliveries"
    folder = make_delivery(root)
    code, out = _cli(["device-result", "show", NAME, "--deliveries", str(root)], capsys)
    assert code == 0 and out["result"]["deviceResult"] is None
    request = tmp_path / "r.json"
    request.write_text(json.dumps(record()), "utf-8")
    code, out = _cli(["device-result", "write", NAME, "--deliveries", str(root), "--file", str(request),
                      "--status", "失败", "--notes", "面板没变"], capsys)
    assert code == 0 and out["result"]["result"]["status"] == "失败"
    code, out = _cli(["device-result", "write", NAME, "--deliveries", str(root)], capsys)
    assert code == 1 and "status" in out["error"]
    source = make_delivery(tmp_path / "dr1")
    (source / "device-result.json").write_text(json.dumps(LEGACY, ensure_ascii=False), "utf-8")
    code, out = _cli(["device-result", "import", str(source / "device-result.json"), "--deliveries", str(root)], capsys)
    assert code == 0 and out["result"]["name"] == NAME and out["result"]["result"]["status"] == "通过"
    assert R.read(folder, "character")["history"] == 1
    code, out = _cli(["device-result", "show", "../x", "--deliveries", str(root)], capsys)
    assert code == 1
    code, out = _cli(["device-result", "schema"], capsys)
    assert code == 0 and out["result"]["$id"] == "urn:wf:device-result:2"
