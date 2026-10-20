# -*- coding: utf-8 -*-
"""Fish 生成的 WAV → 游戏语音（44.1k 单声道 96k CBR、-14 LUFS、存储态 MP3）+ character_speech 字幕行。

台词稿节号 → 游戏槽：
  1 觉醒→ally/evolution  3 加入→ally/join  主页（按出现顺序）→home/home_0..9
  战斗开始→battle_start_0/1  强化弹射→power_flip_0/1  落下→outhole_0/1
  技能满充能→skill_ready（第 2 条无路由可放，不用）  发动技能→skill_0..3  战斗胜利→win_0/1（第 3 条不用）
母本克隆来的旧语音文件（home/kokoha 之类）一律删掉，只留新槽。
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import hw_env
import hw_common as HC
import wf_assets
import wf_seasonal7_voice as V

FAMILY = [("觉醒", "ally/evolution"), ("加入", "ally/join"), ("主页", "home/home_{i}"),
          ("战斗开始", "battle/battle_start_{i}"), ("强化弹射", "battle/power_flip_{i}"),
          ("落下", "battle/outhole_{i}"), ("技能满充能", "battle/skill_ready"),
          ("发动技能", "battle/skill_{i}"), ("战斗胜利", "battle/win_{i}")]
CAPS = {"home": 10, "battle_start": 2, "power_flip": 2, "outhole": 2, "skill": 4, "win": 2, "skill_ready": 1}


def script_sections(md: Path):
    secs, cur = [], None
    for line in md.read_text("utf-8").splitlines():
        m = re.match(r"^##\s*(\d+)\.\s*(\S+)", line)
        if m:
            cur = {"n": int(m.group(1)), "name": m.group(2)}
            secs.append(cur)
        elif cur is not None:
            m = re.match(r"^- \*\*中文翻译\*\*[:：]\s*(.+)$", line)
            if m:
                cur["zh"] = m.group(1).strip()
            m = re.match(r"^- \*\*日语原文\*\*[:：]\s*(.+)$", line)
            if m:
                cur["ja"] = m.group(1).strip()
    return secs


def assign(secs):
    count, out = {}, []
    for s in secs:
        fam = next((pat for name, pat in FAMILY if s["name"].startswith(name)), None)
        if fam is None:
            continue
        base = fam.split("/")[-1].replace("_{i}", "")
        i = count.get(base, 0)
        count[base] = i + 1
        if "{i}" in fam:
            if i >= CAPS.get(base, 1):
                continue
            slot = fam.format(i=i)
        else:
            if i >= 1:
                continue
            slot = fam
        out.append(s | {"slot": slot})
    return out


MAX_S = {"battle_start": 5.83, "outhole": 3.37, "power_flip": 3.13, "skill": 5.02, "skill_ready": 3.81, "win": 9.04}


def tempo_for(slot: str, wav: Path) -> float:
    """战斗槽超过官方最长时长时稍微加速（最多 1.3 倍，保音高）。"""
    import wave
    base = slot.split("/")[-1].rsplit("_", 1)[0] if slot[-1].isdigit() else slot.split("/")[-1]
    mx = MAX_S.get(base)
    if not slot.startswith("battle/") or mx is None:
        return 1.0
    with wave.open(str(wav)) as w:
        dur = w.getnframes() / w.getframerate()
    return max(1.0, min(1.3, dur / mx))


def to_mp3(wav: Path, tempo: float = 1.0) -> bytes:
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "o.mp3"
        meas = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(wav), "-af",
                               "loudnorm=I=-14:TP=-1.7:LRA=11:print_format=json", "-f", "null", "-"],
                              capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
        j = json.loads(meas[meas.rindex("{"):meas.rindex("}") + 1])
        pre = f"atempo={tempo:.3f}," if tempo > 1.001 else ""
        filt = pre + (f"loudnorm=I=-14:TP=-1.7:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:"
                f"measured_LRA={j['input_lra']}:measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true")
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(wav), "-af", filt,
                        "-ar", "44100", "-ac", "1", "-c:a", "libmp3lame", "-b:a", "96k", "-minrate", "96k",
                        "-maxrate", "96k", "-write_xing", "0", "-id3v2_version", "0", str(out)], check=True)
        return out.read_bytes()


SCRIPTS = {"ludi": "万圣第一的公主殿下-露迪_语音台词.md", "momiya": "猎魔人装束的魔法剑士-莫弥亚_语音台词.md",
           "seriol": "别扭的吸血鬼伯爵-塞里奥尔_语音台词.md", "recital": "奇怪的杰克南瓜灯-瑞西塔尔_语音台词.md"}


def install(key: str):
    pack = HC.pack_for(key)
    code, cid = pack.spec.code, pack.spec.cid_s
    secs = assign(script_sections(Path(r"~/Downloads") / SCRIPTS[key]))
    lines = json.loads((hw_env.OUT / "voice" / key / "lines.json").read_text("utf-8"))
    by_n = {int(x["n"]): x for x in lines if x.get("status") == "ok"}
    missing = [s["n"] for s in secs if s["n"] not in by_n]
    if missing:
        raise SystemExit(f"{key}: 缺 wav {missing}")
    vroot = pack.pkg_path("common", f"character/{code}/voice")
    for p in sorted(vroot.rglob("*.mp3")):          # 删母本克隆的旧语音
        p.unlink()
    rows, done = [], []
    for s in secs:
        wav = Path(by_n[s["n"]]["wav"])
        stored = wf_assets.mp3_encode(to_mp3(wav, tempo_for(s["slot"], wav)))
        pack.write_asset("common", f"character/{code}/voice/{s['slot']}.mp3", stored, owner="voice")
        done.append((s["slot"], s["n"]))
    home = [s for s in secs if s["slot"].startswith("home/")]
    by_slot = {s["slot"]: {"zh": s["zh"]} for s in secs}
    rows = V.speech_rows([{"slot": s["slot"], "zh": s["zh"]} for s in secs if s["slot"].startswith(("home/", "ally/"))])
    pack.write_flat("master/character/character_speech.orderedmap", {cid: rows})
    return {"slots": done, "home": len(home), "speech_rows": len(rows)}


if __name__ == "__main__":
    for k in sys.argv[1:]:
        print(k, json.dumps(install(k), ensure_ascii=False))
