"""M4a.1 strict voice format and API-safe MP3 failure counterexamples."""
from __future__ import annotations

import pytest

import wf_assets
from wf.studio.deliver_media import compile_media
from wf.studio.drafts import DraftError, sha256
from test_studio_deliver_media import CID, changeset, mp3_frame, voice


def _audio_frame(sample_rate=44100, mode=3):
    rate_index = {44100: 0, 48000: 1, 32000: 2}[sample_rate]
    header = bytes((255, 251, (7 << 4) | (rate_index << 2), mode << 6))
    return header + bytes(int(144 * 96000 / sample_rate) - 4)


def _replace_voice(voice, raw):
    source, store, change, _ = voice
    entry = change["files"][0]
    store.write_file(CID, entry["draft"], raw)
    entry.update(sha256=sha256(raw), size=len(raw))
    entry.pop("storeSha256", None)
    return compile_media(source, store, changeset([change]))


@pytest.mark.parametrize("raw", [
    _audio_frame(48000) * 3, _audio_frame(32000) * 3,
    _audio_frame(mode=0) * 3, _audio_frame(mode=1) * 3, _audio_frame(mode=2) * 3,
    _audio_frame() + _audio_frame(mode=0), _audio_frame() + _audio_frame(48000),
])
def test_voice_rejects_wrong_or_mixed_sample_rate_and_channels(voice, raw):
    with pytest.raises(DraftError, match="44.1 kHz 单声道"):
        _replace_voice(voice, raw)


def test_voice_accepts_mono_44100_with_id3_and_checks_every_frame(voice):
    raw = b"ID3\x04\x00\x00\x00\x00\x00\x00" + _audio_frame() * 3 + b"TAG" + bytes(125)
    result = _replace_voice(voice, raw)
    stored = next(iter(result.members.values()))
    assert wf_assets.mp3_decode(stored) == raw
    assert wf_assets.mp3_probe(stored, 1023)["channels"] == {1}


@pytest.mark.parametrize("raw", [b"broken mp3", mp3_frame() + mp3_frame(9)])
def test_mp3_encoder_value_error_is_exposed_as_draft_error(voice, raw):
    with pytest.raises(DraftError, match="语音 MP3 无效") as raised:
        _replace_voice(voice, raw)
    assert isinstance(raised.value.__cause__, ValueError)
