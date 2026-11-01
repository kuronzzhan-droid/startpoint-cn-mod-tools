"""D3 speech lifecycle and the client kind-specific five-column contract."""
import base64

import pytest
import wf_assets

from test_studio_character_clone import env as clone_env, OLD, ordered, SPEECH_EVENTS
from test_studio_d3_speech import env, line
from test_studio_deliver_media import mp3_frame, voice as raw_voice
from wf.deliver.changeset import member_name
from wf.studio.clone_tables import leaf, validate_speech
from wf.studio.deliver_bridge import compile_draft
from wf.studio.drafts import DraftError, validate
from wf.studio.server import StudioApp
from wf.studio.speech import LOGICAL, append, compile_speech


@pytest.mark.parametrize("row", [
    ["0", "2", "", "主页", "(None)"],
    ["0", "2", "0", "主页旧写法", "(None)"],
    ["1", "", "1", "进化", "(None)"],
    ["1", "2", "1", "进化旧写法", "(None)"],
    ["2", "", "", "加入", "(None)"],
    ["2", "2", "0", "加入旧写法", "(None)"],
])
def test_kind_specific_empty_columns_and_compatible_ignored_values(row):
    # CharacterSpeechValues only reads c1 for Home, c2 for Evolution, neither for Join.
    validate(row, "speechRow")
    validate_speech([line("主页"), *SPEECH_EVENTS, row])


@pytest.mark.parametrize("row", [
    ["0", "", "", "主页缺有效条件", "(None)"],
    ["1", "", "", "进化缺有效等级", "(None)"],
    line("\r"), line("第一行\r\n第二行"), line("   \n\t"), line("　"),
])
def test_bad_consumed_fields_and_subtitles_rejected_before_writes(env, row):
    source, store, _, server = env
    app = StudioApp(source, drafts=store, server_dir=server, screenshot_dirs=[])
    response = app.dispatch("POST", f"/api/drafts/{OLD}/speech", {}, {"rows": [row]})
    assert response.status == 400, response.body
    assert store.load(OLD) is None
    assert not store.directory(OLD).exists()


@pytest.mark.parametrize("missing, message", [("2", "入队"), ("1", "进化")])
def test_complete_speech_requires_join_and_level_one_evolution(missing, message):
    rows = [line(), *(row for row in SPEECH_EVENTS if row[0] != missing)]
    with pytest.raises(DraftError, match=message + ".*2265"):
        validate_speech(rows)


def test_new_table_cannot_compile_until_all_three_2265_paths_are_covered(env):
    source, store, ops, _ = env
    source.view.files["common", LOGICAL] = ordered({})
    draft = append(ops, OLD, {"rows": [["0", "2", "", "主页", "(None)"]]})["changeset"]
    assert "入队" in draft["changes"][0]["checks"][0]["message"]
    with pytest.raises(DraftError, match="入队.*2265"):
        compile_speech(source, store, draft)
    draft = append(ops, OLD, {"rows": [["2", "", "", "加入", "(None)"],
                                      ["1", "", "0", "零级不是一级", "(None)"]]})["changeset"]
    assert "evo_level=1" in draft["changes"][0]["checks"][0]["message"]
    with pytest.raises(DraftError, match="evo_level=1"):
        compile_speech(source, store, draft)
    draft = append(ops, OLD, {"rows": [["1", "", "1", "进化", "(None)"]]})["changeset"]
    assert not draft["changes"][0]["checks"]
    assert ("common", LOGICAL) in compile_speech(source, store, draft).members


def upload(ops, monkeypatch, voice="home/new_1", filename="source.wav"):
    audio = mp3_frame() * 3
    monkeypatch.setattr("wf.studio.voice.convert", lambda *args: (audio, {"sampleRate": 44100}))
    return ops.voice_save(OLD, {"voice": voice, "filename": filename,
                               "audio": base64.b64encode(audio).decode()})["change"]


def test_offline_store_revert_refuses_to_orphan_dependent_audio(env, monkeypatch):
    _, store, ops, _ = env
    speech = append(ops, OLD, {"rows": [line(voice="home/new_1")]})["change"]
    voice = upload(ops, monkeypatch)
    before = store.load(OLD)
    with pytest.raises(DraftError, match="请先撤销.*home/new_1"):
        store.revert(OLD, speech["id"])
    assert store.load(OLD) == before
    assert store.read_file(OLD, voice["params"]["sourceFile"])
    assert store.read_file(OLD, voice["files"][0]["draft"])


def test_legacy_orphan_audio_remains_visible_and_revert_cleans_both_files(env, monkeypatch):
    source, store, ops, _ = env
    append(ops, OLD, {"rows": [line(voice="home/new_1")]})
    voice = upload(ops, monkeypatch)
    # Simulate an existing D3 draft saved after the old, non-cascading revert.
    legacy = store.load(OLD)
    legacy["changes"] = [voice]
    store.restore(OLD, legacy)
    shown = next(item for item in ops.voice_lines(OLD)["lines"] if item["voice"] == "home/new_1")
    assert "未登记" in shown["label"] and shown["draft"]["id"] == voice["id"]
    assert shown["subtitle"] == line()[3]
    with pytest.raises(DraftError, match="新增台词登记"):
        compile_draft(source, store, legacy)
    ops.revert(OLD, voice["id"])
    assert not store.load(OLD)["changes"]
    assert store.read_file(OLD, voice["params"]["sourceFile"]) is None
    assert store.read_file(OLD, voice["files"][0]["draft"]) is None


def test_replacing_audio_prunes_old_source_and_retains_current_source(env, monkeypatch):
    _, store, ops, _ = env
    append(ops, OLD, {"rows": [line(voice="home/new_1")]})
    first = upload(ops, monkeypatch, filename="first.wav")
    second = upload(ops, monkeypatch, filename="second.mp3")
    assert store.read_file(OLD, first["params"]["sourceFile"]) is None
    assert store.read_file(OLD, second["params"]["sourceFile"])
    assert store.read_file(OLD, second["files"][0]["draft"])


@pytest.mark.parametrize("voice", ["home/home_0", "battle/skill_0"])
def test_reverting_added_rows_preserves_baseline_and_fixed_voice_uploads(env, monkeypatch, voice):
    source, store, ops, _ = env
    if voice.startswith("battle/"):
        logical = "character/mother/voice/" + voice + ".mp3"
        source.view.files["common", logical] = wf_assets.mp3_encode(mp3_frame() * 3)
        source.view.index[member_name("common", logical)] = "fixture.zip"
    speech = append(ops, OLD, {"rows": [line("复用路径的字幕", voice=voice)]})["change"]
    saved = upload(ops, monkeypatch, voice)
    ops.revert(OLD, speech["id"])
    assert [c["id"] for c in store.load(OLD)["changes"]] == [saved["id"]]
    assert store.read_file(OLD, saved["params"]["sourceFile"])
    members, *_ = compile_draft(source, store, store.load(OLD))
    assert ("common", "character/mother/voice/" + voice + ".mp3") in members


def test_root_only_media_source_can_fill_registered_missing_audio(raw_voice):
    from test_studio_deliver_media import CID, changeset
    from wf.studio.deliver_media import compile_media
    source, store, change, raw = raw_voice
    source.files.clear()
    entry = change["files"][0]
    entry["base"]["sha256"] = None
    source.files["common", LOGICAL] = ordered({CID: leaf([line(voice="home/home_0"), *SPEECH_EVENTS])})
    before = dict(source.files)
    compiled = compile_media(source, store, changeset([change]))
    assert compiled.members["common", entry["logical"]] == wf_assets.mp3_encode(raw)
    assert source.files == before
