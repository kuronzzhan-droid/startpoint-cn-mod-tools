"""Synthetic speech additions, candidate integrity, API and delivery compilation."""
import base64
import json

import pytest

import wf_mod_tool as core
from test_studio_character_clone import env as clone_env, OLD, NEW, request, ordered, View, SPEECH_EVENTS
from test_studio_deliver_media import mp3_frame
from wf.studio.character_clone import clone, compile_clone
from wf.studio.deliver_bridge import compile_draft
from wf.studio.drafts import DraftError
from wf.studio.server import StudioApp
from wf.studio.source import StudioSource
from wf.studio.speech import append, compile_speech, LOGICAL
from wf.studio.clone_tables import leaf, rows


@pytest.fixture
def env(clone_env):
    source, store, *_ = clone_env
    source.official_root = store.root / "no-official-input"
    return clone_env


def line(text="新台词\n下一行", voice="(None)", kind="0", constraint="2"):
    return [kind, constraint, "0", text, voice]


def test_append_roundtrip_preserves_other_leaf_and_source(env):
    source, store, ops, _ = env
    foreign = leaf([["0", "2", "0", "别人的台词", "(None)"]])
    baseline = [line("原文"), *SPEECH_EVENTS]
    source.view.files["common", LOGICAL] = ordered({OLD: leaf(baseline), "999": foreign})
    before = dict(source.view.files)
    draft = append(ops, OLD, {"rows": [line()]})["changeset"]
    members, servers, _, _, checks = compile_draft(source, store, draft)
    table = core.read_orderedmap_file_from_bytes(members["common", LOGICAL])
    assert core.read_csv_lines(table[OLD]) == [*baseline, line()]
    assert rows(members["common", LOGICAL])["999"] == foreign
    assert not servers and checks[-1]["code"] == "studio.speech.home_states"
    assert source.view.files == before
    assert ops.voice_lines(OLD)["lines"][-1]["subtitle"] == "新台词\n下一行"
    ops.revert(OLD, draft["changes"][0]["id"])
    assert len(ops.voice_lines(OLD)["lines"]) == 3


@pytest.mark.parametrize("bad", [line(voice="home/a\nhome/b"), line(voice="../a"),
    line(voice="home/a\n"), line(voice="home/a.mp3"), line(voice="home/a\r"), line(kind="9"), line(constraint="3"),
    ["0", "2", "0", "字幕"], ["0", "2", "-1", "字幕", "(None)"]])
def test_bad_rows_rejected_without_writes(env, bad):
    _, store, ops, _ = env
    with pytest.raises(DraftError):
        append(ops, OLD, {"rows": [bad]})
    assert store.load(OLD) is None


def test_home_coverage_only_counts_home_and_is_rechecked(env):
    source, store, ops, _ = env
    source.view.files["common", LOGICAL] = ordered({OLD: leaf([line("原文", constraint="0"), *SPEECH_EVENTS])})
    draft = append(ops, OLD, {"rows": [line(kind="1", constraint="1")]})["changeset"]
    assert draft["changes"][0]["checks"][0]["level"] == "error"
    with pytest.raises(DraftError, match="2265"):
        compile_draft(source, store, draft)
    repaired = append(ops, OLD, {"rows": [line("进化主页", constraint="1")]})["changeset"]
    assert not repaired["changes"][0]["checks"]
    compile_speech(source, store, repaired)


def test_new_voice_upload_missing_audio_and_orphan_rejection(env, monkeypatch):
    source, store, ops, _ = env
    draft = append(ops, OLD, {"rows": [line(voice="home/new_line")]})["changeset"]
    with pytest.raises(DraftError, match="缺少音频"):
        compile_draft(source, store, draft)
    audio = mp3_frame() * 3
    monkeypatch.setattr("wf.studio.voice.convert", lambda *args: (audio, {"sampleRate": 44100}))
    ops.voice_save(OLD, {"voice": "home/new_line", "audio": base64.b64encode(audio).decode(), "filename": "a.mp3"})
    compiled = compile_draft(source, store, store.load(OLD))
    assert ("common", "character/mother/voice/home/new_line.mp3") in compiled[0]
    before = store.load(OLD)
    with pytest.raises(DraftError, match="请先撤销.*音频"):
        ops.revert(OLD, draft["changes"][0]["id"])
    assert store.load(OLD) == before
    uploaded = next(c for c in before["changes"] if c["kind"] == "voice_line")
    ops.revert(OLD, uploaded["id"])
    assert store.read_file(OLD, uploaded["files"][0]["draft"]) is None
    assert store.read_file(OLD, uploaded["params"]["sourceFile"]) is None
    ops.revert(OLD, draft["changes"][0]["id"])
    assert not store.load(OLD)["changes"]


def test_speech_drift_and_foreign_target_rejected(env):
    source, store, ops, _ = env
    draft = append(ops, OLD, {"rows": [line()]})["changeset"]
    draft["changes"][0]["target"]["character"] = NEW
    with pytest.raises(DraftError, match="目标"):
        compile_speech(source, store, draft)
    draft["changes"][0]["target"]["character"] = OLD
    changed = dict(source.view.files)
    changed["common", LOGICAL] = ordered({OLD: leaf([line("新基线")])})
    with pytest.raises(DraftError, match="旧值断言"):
        compile_speech(StudioSource(View(changed)), store, draft)


def test_clone_addition_and_http_routes(env):
    source, store, ops, server = env
    clone(ops, request(), server_dir=server)
    app = StudioApp(source, drafts=store, server_dir=server, screenshot_dirs=[])
    response = app.dispatch("POST", f"/api/drafts/{NEW}/speech", {}, {"rows": [line()]})
    assert response.status == 200, response.body
    shown = app.dispatch("GET", f"/api/characters/{NEW}/voice", {})
    assert json.loads(shown.body)["lines"][-1]["subtitle"] == line()[3]
    members, *_ = compile_clone(source, store, store.load(NEW), server_dir=server)
    assert len(core.read_csv_lines(core.read_orderedmap_file_from_bytes(members["common", LOGICAL])[NEW])) == 4
    assert NEW not in source.table(LOGICAL)
