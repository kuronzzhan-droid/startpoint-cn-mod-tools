"""Clone media uses the candidate baseline and the client's single-voice speech rows."""
import base64
import json
import struct

import pytest
import wf_assets

from wf.deliver.changeset import member_name
from wf.studio.character_clone import clone, clone_members, compile_clone
from wf.studio.clone_tables import T, leaf, rows
from wf.studio.drafts import DraftError, sha256
from wf.studio.pixel_workshop import family_paths
from wf.studio.server import StudioApp
from test_studio_character_clone import env, request, ordered, OLD, NEW, CODE  # noqa: F401
from test_studio_deliver_media import mp3_frame


def application(env):
    source, store, _, server = env
    return StudioApp(source, drafts=store, server_dir=server, screenshot_dirs=[])


def response(app, method, suffix, body=None, *, query=None):
    path = f"/api/{'drafts' if method == 'POST' else 'characters'}/{NEW}/{suffix}"
    result = app.dispatch(method, path, query or {}, body)
    assert result.status == 200, result.body
    return result


def test_cloned_workshop_analysis_cells_action_frames_and_rgba_use_candidate(env):
    source, _, ops, _ = env
    clone(ops, request())
    app = application(env)
    analyzed = json.loads(response(app, "GET", "pixel-workshop").body)
    assert analyzed["code"] == CODE
    assert {f["family"] for f in analyzed["families"]} == {"pixelart", "special"}
    cell = response(app, "GET", "pixel-workshop/cell/pixelart/2.png")
    assert cell.body.startswith(b"\x89PNG") and cell.cache == "no-store"
    action = json.loads(response(app, "GET", "pixel-workshop/action/pixelart/neutral").body)
    assert action["frames"] and action["totalFrames"] == 2
    rgba = response(app, "GET", "pixels/pixelart.rgba")
    width, height = struct.unpack("<II", rgba.body[:8])
    assert len(rgba.body) == 8 + width * height * 4
    assert rgba.cache == "no-store"
    assert NEW not in source.table("character") and app.source is source


def test_cloned_remap_then_generated_action_preview_and_delivery(env):
    source, store, ops, server = env
    clone(ops, request())
    app = application(env)
    baseline = clone_members(source, store, store.load(NEW))
    remap = json.loads(response(app, "POST", "pixel-remap", {
        "base": OLD, "families": ["pixelart"], "mapping": [{"from": "#a13b3b", "to": "#2266cc"}]}).body)
    for entry in remap["changes"][0]["files"]:
        assert entry["base"]["sha256"] == sha256(baseline[entry["root"], entry["logical"]])
    # The painter's input sees the remap, and the generator saves through clone-bound DraftOps.
    painted = json.loads(response(app, "GET", "pixel-workshop/action/pixelart/neutral").body)
    assert bytes((34, 102, 204, 255)) in base64.b64decode(painted["frames"][0]["rgba"])
    generated = json.loads(response(app, "POST", "pixel-generate", {
        "action": "walk_back", "totalFrames": 24, "save": True}).body)
    assert generated["change"]["kind"] == "pixel_action"
    preview = app.dispatch("GET", f"/api/drafts/{NEW}/pixels/pixelart.rgba", {})
    assert preview.status == 200 and preview.cache == "no-store"
    members, _, _, _, _ = compile_clone(source, store, store.load(NEW), server_dir=server)
    sheet = family_paths(CODE, "pixelart")[0]
    assert members["common", sheet] != baseline["common", sheet]


def test_multiline_subtitle_keeps_one_editable_voice_and_speech_bytes(env, monkeypatch):
    source, store, ops, server = env
    subtitle = "第一行\n第二行，保留标点"
    speech = [["0", "2", "0", subtitle, "home/custom_name"]]
    source.view.files["common", T.SPEECH] = ordered({OLD: leaf(speech)})
    donor = "character/mother/voice/home/custom_name.mp3"
    source.view.files["common", donor] = wf_assets.mp3_encode(mp3_frame() * 3)
    source.view.index[member_name("common", donor)] = "fixture.zip"
    clone(ops, request())
    before = clone_members(source, store, store.load(NEW))["common", T.SPEECH]
    lines = ops.voice_lines(NEW)["lines"]
    assert len(lines) == 1 and lines[0]["voice"] == "home/custom_name"
    assert lines[0]["subtitle"] == subtitle and lines[0]["present"]
    replacement = mp3_frame() * 4
    monkeypatch.setattr("wf.studio.voice.convert", lambda *args: (replacement, {"channels": 1, "sampleRate": 44100}))
    edited = ops.voice_save(NEW, {"voice": "home/custom_name", "filename": "voice.wav",
                                "audio": base64.b64encode(b"fixture input").decode("ascii")})
    assert edited["change"]["params"]["subtitle"] == subtitle
    members, _, _, _, _ = compile_clone(source, store, store.load(NEW), server_dir=server)
    assert members["common", T.SPEECH] == before
    assert rows(before)[NEW] == leaf(speech)
    assert members["common", f"character/{CODE}/voice/home/custom_name.mp3"] == wf_assets.mp3_encode(replacement)


@pytest.mark.parametrize("path", ["home/home_0\nhome/home_1", "home/home_0\rhome/home_1"])
def test_multiline_voice_path_is_rejected_without_writing_a_clone(env, path):
    source, store, ops, _ = env
    source.view.files["common", T.SPEECH] = ordered({OLD: leaf([["0", "2", "0", "字幕", path]])})
    with pytest.raises(DraftError, match="单个语音路径"):
        clone(ops, request())
    assert not store.directory(NEW).exists()


def test_non_home_speech_cannot_satisfy_home_visibility(env):
    source, store, ops, _ = env
    source.view.files["common", T.SPEECH] = ordered({OLD: leaf([["2", "2", "0", "入队", "join/join_0"]])})
    with pytest.raises(DraftError, match="2265"):
        clone(ops, request())
    assert not store.directory(NEW).exists()


def test_existing_candidate_with_multiline_voice_path_is_blocked_at_delivery(env):
    source, store, ops, server = env
    draft = clone(ops, request())["changeset"]
    change = next(c for c in draft["changes"] if c["kind"] == "character_clone")
    entry = next(e for e in change["files"] if e["logical"] == T.SPEECH)
    table = rows(store.read_file(NEW, entry["draft"]))
    table[NEW] = leaf([["0", "2", "0", "字幕", "home/home_0\nhome/home_1"]])
    raw = ordered(table)
    store.write_file(NEW, entry["draft"], raw)
    entry.update(sha256=sha256(raw), size=len(raw))
    with pytest.raises(DraftError, match="单个语音路径"):
        compile_clone(source, store, draft, server_dir=server)
