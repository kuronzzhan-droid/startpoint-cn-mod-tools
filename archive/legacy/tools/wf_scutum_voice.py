"""盾牌座作者配音的原生槽位、字幕与无裁切转码。"""
import json
import re
import subprocess

import wf_assets
import wf_voice
import wf_voice_gate as gate
from wf_gerald_voice_audio import metadata, sha
from wf_scutum_seed import CID, CODE

MAPPING = {"加入": "ally/join", "进化": "ally/evolution", "技能准备完毕": "battle/skill_ready",
           **{f"日常{i+1}": f"home/home_{i}" for i in range(6)},
           **{f"{cn}{i+1}": f"battle/{en}_{i}" for cn, en in (
               ("技能发动", "skill"), ("战斗开始", "battle_start"), ("胜利", "win"),
               ("强化弹射", "power_flip"), ("落下", "outhole")) for i in range(2)}}


def build(seed, source_dir, output):
    ffmpeg = wf_voice.find_ffmpeg()
    if ffmpeg is None:
        raise ValueError("FFmpeg missing")
    ffprobe = ffmpeg.with_name("ffprobe.exe")
    transcript = (source_dir / "角色台词.txt").read_text(encoding="utf-8-sig")
    texts = {label: value.strip() for label, value in re.findall(r"【([^】]+)】\s*([^【]+)", transcript)}
    if set(texts) != set(MAPPING):
        raise ValueError("voice transcript labels mismatch")
    output.mkdir(parents=True, exist_ok=True)
    records, voices, speech = [], [], []
    for label, slot in MAPPING.items():
        source = source_dir / (label + ".mp3")
        source_hash = sha(source.read_bytes())
        target = output / (slot.replace("/", "-") + ".mp3")
        cache = target.with_suffix(".sha256")
        if not target.exists() or not cache.exists() or cache.read_text() != source_hash:
            subprocess.run([str(ffmpeg), "-y", "-v", "error", "-i", str(source), "-map", "0:a:0",
                            "-map_metadata", "-1", "-vn", "-ar", "44100", "-ac", "1", "-c:a", "libmp3lame",
                            "-b:a", "96k", "-write_xing", "1", "-id3v2_version", "0", str(target)],
                           check=True, capture_output=True)
            cache.write_text(source_hash)
        before, after = metadata(source, ffprobe), metadata(target, ffprobe)
        if abs(float(before["format"]["duration"]) - float(after["format"]["duration"])) > .1:
            raise ValueError("voice duration changed")
        stored = wf_assets.mp3_encode(target.read_bytes())
        if wf_assets.mp3_decode(stored) != target.read_bytes():
            raise ValueError("voice storage roundtrip mismatch")
        voice = gate.VoiceFile(CODE, slot, stored)
        failures = gate.check_container(voice, gate.probe(stored))
        if failures:
            raise ValueError(failures)
        voices.append(voice)
        seed.emit("common", f"character/{CODE}/voice/{slot}.mp3", stored)
        records.append(dict(slot=slot, source=str(source), source_sha256=source_hash,
                            duration=float(after["format"]["duration"]), sha256=sha(stored)))
        if slot.startswith("home/"):
            speech.append(["0", "1", "", texts[label], slot])
        elif slot == "ally/join":
            speech.append(["2", "", "", texts[label], slot])
        elif slot == "ally/evolution":
            speech.append(["1", "", "1", texts[label], slot])
    if len(records) != 19 or len(speech) != 8:
        raise ValueError("incomplete voice set")
    seed.table("master/character/character_speech.orderedmap", {CID: speech})
    report = dict(recordings=records, subtitles=8, source_text_sha256=sha(transcript.encode()),
                  codec="MP3 44.1kHz mono 96kbps", no_trim=True)
    (output / "manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
