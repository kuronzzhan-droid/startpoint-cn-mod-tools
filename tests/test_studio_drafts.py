"""编辑台 M3.2：写入守卫、草稿 schema、草稿往返、HTTP 接口。"""
from __future__ import annotations

import base64
import http.client
import io
import json
import shutil
import socket
import threading
import wave

import pytest
from PIL import Image

from wf.studio import drafts as D
from wf.studio.guard import GuardError, TOKEN_HEADER, WriteGuard
from wf.studio.server import StudioApp, serve

SHA = "a" * 64


class _FakeView:
    tip = 1
    zips = ()
    index = {}
    active = "."
    store = "."


class _FakeSource:
    view = _FakeView()
    version = "1.4.1"

    def describe(self):
        return {"version": self.version, "extraZips": []}

    def table(self, name, official=False):
        return {}

    def raw(self, logical, official=False):
        return None


def _headers(guard, **extra):
    base = {"Host": f"127.0.0.1:{guard.port}", TOKEN_HEADER: guard.token, "Content-Type": "application/json",
            "Content-Length": "2"}
    base.update(extra)
    return {k: v for k, v in base.items() if v is not None}


# -- guard ---------------------------------------------------------------
def test_guard_accepts_same_origin_with_token():
    guard = WriteGuard(8790)
    guard.check(_headers(guard))
    guard.check(_headers(guard, Origin="http://127.0.0.1:8790", **{"Sec-Fetch-Site": "same-origin"}))
    guard.check(_headers(guard, Host="localhost:8790", Origin="http://localhost:8790"))


@pytest.mark.parametrize("change, code", [
    ({"Host": "evil.example:8790"}, "studio_bad_host"),
    ({"Host": "127.0.0.1:9999"}, "studio_bad_host"),
    ({"Origin": "http://evil.example"}, "studio_cross_origin"),
    ({"Origin": "http://127.0.0.1:5173"}, "studio_cross_origin"),
    ({"Sec-Fetch-Site": "cross-site"}, "studio_cross_origin"),
    ({TOKEN_HEADER: "wrong"}, "studio_bad_token"),
    ({TOKEN_HEADER: None}, "studio_bad_token"),
    ({"Content-Type": "text/plain"}, "studio_bad_type"),
])
def test_guard_rejects(change, code):
    guard = WriteGuard(8790)
    with pytest.raises(GuardError) as caught:
        guard.check(_headers(guard, **change))
    assert caught.value.code == code


def test_guard_extra_origin_and_body_limits():
    guard = WriteGuard(8790, extra_origins=["http://127.0.0.1:5173"])
    guard.check(_headers(guard, Origin="http://127.0.0.1:5173"))
    with pytest.raises(GuardError):
        guard.body_length({"Content-Length": str(10 ** 9)})
    with pytest.raises(GuardError):
        guard.parse(b"\xff")
    assert b'name="wf-studio-token"' in guard.inject(b"<html><head></head></html>")


# -- schema --------------------------------------------------------------
def _template():
    groups = {name: {"anchor": [0.5, 0.5], "factor": 1.0} for name in
              ("square", "thumb_level_up", "battle_member_status", "battle_control_board", "cutin_skill_chain",
               "thumb_party_main")}
    return {"face": [100, 80], "squareHeight": 120, "groups": groups,
            "cutin": {"center": [100, 80], "height": 300, "anchor": [0.51, 0.44]}, "backdrop": None}


def _file(relative, data=b"x"):
    return {"logical": "character/demo_code/ui/square_0.png", "root": "medium", "draft": relative,
            "sha256": D.sha256(data), "size": len(data), "encoding": "png", "base": {"sha256": None, "layer": None},
            "approximate": True}


def _portrait_change(relative="files/medium/character/demo_code/ui/square_0.png", data=b"x"):
    return {"id": D.new_change_id(), "kind": "portrait", "title": "立绘 _0", "createdAt": D.now(),
            "target": {"form": "0"},
            "params": {"source": "current", "template": _template(), "sourceSize": [200, 300], "trim": [0, 0, 200, 300],
                       "tableRows": {}, "atf": False},
            "files": [_file(relative, data)], "pending": [], "checks": [{"level": "info", "code": "x", "message": "m"}]}


def test_schema_is_valid_and_machine_readable():
    import jsonschema
    document = D.schema()
    jsonschema.Draft202012Validator.check_schema(document)
    for name in ("change", "portraitRequest", "pixelRequest", "voiceRequest", "cropTemplate"):
        assert name in document["$defs"]


def test_schema_accepts_and_rejects_changes():
    assert D.schema_errors(_portrait_change(), "change") == []
    bad = _portrait_change()
    bad["id"] = "nope"
    assert D.schema_errors(bad, "change")
    bad = _portrait_change()
    bad["target"] = {"form": "2"}
    assert D.schema_errors(bad, "change")
    bad = _portrait_change()
    bad["files"][0]["logical"] = "master/character/character.orderedmap"
    assert D.schema_errors(bad, "change"), "drafts must not carry game table paths as files"
    assert D.schema_errors({"form": "0", "template": _template()}, "portraitRequest") == []
    assert D.schema_errors({"voice": "home/home_0", "audio": "", "filename": "a.wav"}, "voiceRequest") == []
    assert D.schema_errors({"voice": "../x", "audio": "", "filename": "a.wav"}, "voiceRequest")
    assert D.schema_errors({"family": "pixelart", "action": "neutral", "frames": []}, "pixelRequest")


# -- roundtrip -------------------------------------------------------------
def test_draft_roundtrip(tmp_path):
    store = D.DraftStore(tmp_path / "drafts")
    first = "files/medium/character/demo_code/ui/square_0.png"
    store.write_file("7", first, b"one")
    changeset = store.put_change("7", "demo_code", "1.4.1", _portrait_change(first, b"one"))
    assert D.status(changeset)["state"] == "dirty"
    assert D.schema_errors(store.load("7")) == []

    saved = store.save("7")
    assert saved["savedAt"] and D.status(saved)["state"] == "saved"

    # Same target replaces the earlier change and prunes its now-unreferenced file.
    second = "files/medium/character/demo_code/ui/square_0_v2.png"
    store.write_file("7", second, b"two")
    replacement = _portrait_change(second, b"two")
    changeset = store.put_change("7", "demo_code", "1.4.1", replacement)
    assert [c["id"] for c in changeset["changes"]] == [replacement["id"]]
    assert not (store.directory("7") / first).exists()
    assert D.status(changeset)["state"] == "dirty"

    # Tampering is caught by 保存.
    (store.directory("7") / second).write_bytes(b"tampered")
    with pytest.raises(D.DraftError):
        store.save("7")

    changeset = store.revert("7", replacement["id"])
    assert changeset["changes"] == [] and not (store.directory("7") / second).exists()
    with pytest.raises(D.DraftError):
        store.revert("7", replacement["id"])


def test_draft_paths_are_confined(tmp_path):
    store = D.DraftStore(tmp_path / "drafts")
    for bad in ("../x", "files/../../x", "/etc/passwd", "C:/x", "other/x"):
        with pytest.raises(D.DraftError):
            store.resolve("7", bad)
    with pytest.raises(D.DraftError):
        store.directory("../7")
    with pytest.raises(D.DraftError):
        store.put_change("7", "demo_code", "1.4.1", {"id": "bad"})


# -- HTTP ----------------------------------------------------------------
def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture()
def live(tmp_path):
    static = tmp_path / "dist"
    static.mkdir()
    (static / "index.html").write_text("<html><head></head><body></body></html>", "utf-8")
    app = StudioApp(_FakeSource(), drafts=D.DraftStore(tmp_path / "drafts"))
    port = _free_port()
    server = serve(app, port=port, static_root=static)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield port, server.guard, app
    server.shutdown()
    server.server_close()


def _request(port, method, path, body=None, headers=None):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    payload = json.dumps(body).encode("utf-8") if body is not None else None
    connection.request(method, path, body=payload, headers=headers or {})
    response = connection.getresponse()
    data = response.read()
    connection.close()
    return response.status, data


def test_http_guard_and_token_injection(live):
    port, guard, app = live
    status, page = _request(port, "GET", "/")
    assert status == 200 and guard.token.encode() in page
    ok_headers = {TOKEN_HEADER: guard.token, "Content-Type": "application/json"}
    assert _request(port, "POST", "/api/drafts/7/save", {}, {"Content-Type": "application/json"})[0] == 403
    assert _request(port, "POST", "/api/drafts/7/save", {},
                    {**ok_headers, "Origin": "http://evil.example"})[0] == 403
    assert _request(port, "POST", "/api/drafts/7/save", {},
                    {**ok_headers, "Host": "attacker.test"})[0] == 403
    status, body = _request(port, "POST", "/api/drafts/7/save", {}, ok_headers)
    assert status == 400 and "没有草稿" in json.loads(body)["error"]
    assert _request(port, "PUT", "/api/drafts/7/save", {}, ok_headers)[0] == 405
    assert _request(port, "GET", "/api/drafts/7/save")[0] == 405
    status, body = _request(port, "GET", "/api/drafts/7")
    assert status == 200 and json.loads(body)["status"]["state"] == "clean"
    assert json.loads(_request(port, "GET", "/api/studio/schema")[1])["$id"].endswith("studio-draft.schema.json")
    assert _request(port, "GET", "/api/drafts/7/file?path=../../x")[0] == 400


def test_route_verbs():
    app = StudioApp(_FakeSource())
    verbs = {verb for verb, _, _ in app.routes}
    assert verbs == {"GET", "POST"}
    assert all(pattern.pattern.startswith(("^/api/drafts/", "^/api/boss/drafts", "^/api/studio/weapons/"))
               for verb, pattern, _ in app.routes if verb == "POST")


# -- conversions -----------------------------------------------------------
def test_voice_convert_is_game_cbr(tmp_path):
    from wf.studio import voice
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not installed")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(48000)
        import math
        frames = b"".join(int(8000 * math.sin(i / 20)).to_bytes(2, "little", signed=True) * 2 for i in range(48000))
        handle.writeframes(frames)
    mp3, info = voice.convert(buffer.getvalue(), "take.wav", -14.0)
    assert info["sampleRate"] == 44100 and info["bitrates"] == [96]
    assert 0.9 < voice.mp3_duration(mp3) < 1.2
    assert voice.duration_checks("battle/skill_ready", 5.0)
    assert not voice.duration_checks("battle/skill_ready", 2.0)


def test_sheet_split_and_anchor():
    from wf.studio.pixel_import import default_anchor, split_sheet
    sheet = Image.new("RGBA", (80, 40))
    for i in range(4):
        sheet.paste((255, 0, 0, 255), (i * 20 + 5, 10, i * 20 + 15, 30 + (i % 2)))
    frames = split_sheet(sheet, 4, 1)
    assert len(frames) == 4 and frames[0].size == (20, 40)
    assert default_anchor(frames) == [10, 31]
    from wf.studio.drafts import DraftError
    with pytest.raises(DraftError):
        split_sheet(sheet, 3, 1)


# -- real view (skipped when the layered view is not configured) ------------
@pytest.fixture()
def real_ops(tmp_path):
    try:
        from wf.studio.source import build_source
        source = build_source()
    except (FileNotFoundError, OSError, KeyError) as exc:
        pytest.skip(f"real layered view unavailable: {exc}")
    from wf.studio.operations import DraftOps
    if source.table("character").get("139985") is None:
        pytest.skip("139985 not in view")
    return DraftOps(source, store=D.DraftStore(tmp_path / "drafts"))


def test_real_ops_missing_character_skips(tmp_path, monkeypatch):
    monkeypatch.setattr("wf.studio.source.build_source", _FakeSource)
    with pytest.raises(pytest.skip.Exception, match="139985 not in view"):
        real_ops.__wrapped__(tmp_path)


def _png_b64(image):
    out = io.BytesIO()
    image.save(out, "PNG")
    return base64.b64encode(out.getvalue()).decode()


def test_real_portrait_info_and_pixel_roundtrip(real_ops):
    info = real_ops.portrait_info("139985", "0")
    assert info["current"]["template"]["face"] == [559.0, 226.0]  # character_image x,y + face attr
    assert D.schema_errors(info["current"]["template"], "cropTemplate") == []
    frame = Image.new("RGBA", (24, 30))
    frame.paste((200, 90, 40, 255), (6, 4, 18, 28))
    request = {"family": "pixelart", "action": "neutral",
               "frames": [{"png": _png_b64(frame), "duration": 1, "anchor": [12, 28]},
                          {"png": _png_b64(frame), "duration": 1, "anchor": [12, 28]}]}
    dry = real_ops.pixel_save("139985", {**request, "dryRun": True})
    assert dry["budget"]["estimate"]["share"] > 0 and dry["originalTotalFrames"] == 2
    result = real_ops.pixel_save("139985", request)
    change = result["change"]
    assert change["kind"] == "pixel_action" and len(change["params"]["frames"]) == 2
    assert real_ops.store.save("139985")["savedAt"]
    assert real_ops.revert("139985", change["id"])["status"]["state"] == "clean"
    too_big = Image.new("RGBA", (300, 300), (0, 0, 0, 0))
    too_big.paste((1, 2, 3, 255), (10, 10, 20, 20))
    with pytest.raises(D.DraftError):
        real_ops.pixel_save("139985", {"family": "pixelart", "action": "neutral",
                                       "frames": [{"png": _png_b64(too_big), "duration": 2, "anchor": [0, 0]}]})
