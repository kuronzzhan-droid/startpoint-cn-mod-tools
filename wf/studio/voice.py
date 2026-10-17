"""语音：上传 WAV/MP3 → 游戏规格 MP3（44.1kHz 单声道 96kbps CBR）→ 草稿。

转码沿用万圣批次（``wf.chars.halloween.voice.to_mp3``）的 ffmpeg 两遍 loudnorm
配方，再用 ``wf_assets.mp3_encode`` 做存储态转换校验（VBR / 半转换会被拒绝）。
草稿里存标准 MP3（浏览器可直接 A/B 试听），存储态哈希另记。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import wf_assets

from .drafts import DraftError

# 官方 R128 积分响度中位（memory: wf-character-speech-voice-system）。
LOUDNESS = {"home": -14.0, "ally": -14.1, "battle": -12.8, "skill": -13.1, "login": -14.0}
# 战斗短句官方最长（秒）；超了战斗里会叠播成「电音」。
BATTLE_MAX = {"battle_start": 5.83, "outhole": 3.37, "power_flip": 3.13, "skill": 5.02,
              "skill_ready": 3.81, "win": 9.04}
HOME_MAX = 26.3
FIXED_LINES = (
    "ally/join", "ally/evolution", "battle/battle_start_0", "battle/battle_start_1",
    "battle/power_flip_0", "battle/power_flip_1", "battle/outhole_0", "battle/outhole_1",
    "battle/skill_ready", "battle/skill_0", "battle/skill_1", "battle/skill_2", "battle/skill_3",
    "battle/win_0", "battle/win_1", "login/login_0", "login/login_1", "login/login_2",
)
LINE_LABEL = {"ally/join": "入队", "ally/evolution": "觉醒", "battle/skill_ready": "技能准备"}


def label_for(voice: str) -> str:
    if voice in LINE_LABEL:
        return LINE_LABEL[voice]
    name = voice.split("/")[-1]
    base, _, index = name.rpartition("_")
    stem = base if index.isdigit() else name
    names = {"home": "主页", "battle_start": "战斗开始", "power_flip": "强化弹射", "outhole": "落洞",
             "skill": "发动技能", "win": "胜利", "login": "登录"}
    label = names.get(stem, stem)
    return f"{label} {int(index) + 1}" if index.isdigit() else label


def category(voice: str) -> str:
    top, _, name = voice.partition("/")
    if top == "battle" and name.startswith("skill"):
        return "skill"
    return top if top in LOUDNESS else "home"


def ffmpeg_path() -> str:
    found = os.environ.get("WF_FFMPEG") or shutil.which("ffmpeg")
    if not found:
        raise DraftError("找不到 ffmpeg：安装后加入 PATH，或设置环境变量 WF_FFMPEG")
    return found


def mp3_duration(data: bytes) -> float:
    probe = wf_assets.mp3_probe(data, 2047)
    if not probe["frames"] or not probe["srates"]:
        probe = wf_assets.mp3_probe(data, 1023)
    if not probe["frames"] or not probe["srates"]:
        return 0.0
    return probe["frames"] * 1152 / min(probe["srates"])


def convert(audio: bytes, filename: str, loudness: float) -> tuple[bytes, dict]:
    """Any ffmpeg-readable audio → standard CBR 96k mono 44.1k MP3 (two-pass loudnorm)."""
    ffmpeg = ffmpeg_path()
    suffix = Path(filename).suffix.lower() or ".bin"
    if not suffix.replace(".", "").isalnum():
        suffix = ".bin"
    env = {k: v for k, v in os.environ.items() if k.upper() != "FFREPORT"}
    with tempfile.TemporaryDirectory(prefix="wf-studio-voice-") as temp:
        source = Path(temp) / ("in" + suffix)
        target = Path(temp) / "out.mp3"
        source.write_bytes(audio)
        measure = subprocess.run([ffmpeg, "-hide_banner", "-nostdin", "-i", str(source), "-af",
                                  f"loudnorm=I={loudness}:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                                 capture_output=True, text=True, encoding="utf-8", errors="replace",
                                 env=env, cwd=temp, timeout=300)
        text = measure.stderr
        if measure.returncode != 0 or "{" not in text:
            tail = text.strip().splitlines()[-1:] or ["无输出"]
            raise DraftError(f"ffmpeg 读不了这个音频：{tail[0]}")
        stats = json.loads(text[text.rindex("{"):text.rindex("}") + 1])
        filt = (f"loudnorm=I={loudness}:TP=-1.5:LRA=11:measured_I={stats['input_i']}:"
                f"measured_TP={stats['input_tp']}:measured_LRA={stats['input_lra']}:"
                f"measured_thresh={stats['input_thresh']}:offset={stats['target_offset']}:linear=true")
        run = subprocess.run([ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "error", "-y", "-i", str(source),
                              "-af", filt, "-ar", "44100", "-ac", "1", "-c:a", "libmp3lame", "-b:a", "96k",
                              "-minrate", "96k", "-maxrate", "96k", "-write_xing", "0", "-id3v2_version", "0",
                              str(target)], capture_output=True, text=True, encoding="utf-8", errors="replace",
                             env=env, cwd=temp, timeout=300)
        if run.returncode != 0 or not target.is_file():
            raise DraftError(f"ffmpeg 转码失败：{run.stderr.strip()[:200]}")
        mp3 = target.read_bytes()
    stored = wf_assets.mp3_encode(mp3)  # raises on VBR / partial conversion
    probe = wf_assets.mp3_probe(stored, 1023)
    info = {"sampleRate": min(probe["srates"]), "bitrates": sorted(b // 1000 for b in probe["bitrates"]),
            "frames": probe["frames"], "channels": 1, "measuredInputLufs": float(stats["input_i"])}
    return mp3, info


def duration_checks(voice: str, seconds: float) -> list[dict]:
    checks = []
    name = voice.split("/")[-1]
    base = name.rsplit("_", 1)[0] if name[-1:].isdigit() else name
    if voice.startswith("battle/") and base in BATTLE_MAX and seconds > BATTLE_MAX[base]:
        checks.append({"level": "warn", "code": "voice.battle_too_long",
                       "message": f"{seconds:.2f}s 超过官方同类最长 {BATTLE_MAX[base]}s：战斗里高频触发会叠播成「电音」"})
    if voice.startswith("home/") and seconds > HOME_MAX:
        checks.append({"level": "warn", "code": "voice.home_too_long",
                       "message": f"{seconds:.1f}s 超过官方主页语音最长 {HOME_MAX}s"})
    return checks
