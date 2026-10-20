# -*- coding: utf-8 -*-
"""水杰拉德语音装包：voice/成品（豆包录制、已母带）→ 包内 character/<code>/voice/，删母本克隆的旧语音，写 character_speech。
槽位：home_0..11、skill_ready（+alt_1..3，轮换需客户端补丁）、skill_0..5、power_flip_0..5、battle_start/win/outhole 各 2、ally join/evolution。"""
from __future__ import annotations

import json
import sys

import wg_env
import wg_common as HC
import wf_assets
import wf_seasonal7_voice as V

SRC = wg_env.OUT / "voice" / "成品"


def install(key: str = "aqua"):
    pack = HC.pack_for(key)
    code, cid = pack.spec.code, pack.spec.cid_s
    lines = json.loads((SRC / "台词清单.json").read_text(encoding="utf-8"))
    assert all(x.get("subtitle_match") for x in lines), [x["slot"] for x in lines if not x.get("subtitle_match")]
    vroot = pack.pkg_path("common", f"character/{code}/voice")
    removed = 0
    for p in sorted(vroot.rglob("*.mp3")) if vroot.is_dir() else []:
        p.unlink(); removed += 1
    done = []
    for x in lines:
        raw = (SRC / (x["slot"] + ".mp3")).read_bytes()
        pack.write_asset("common", f"character/{code}/voice/{x['slot']}.mp3", wf_assets.mp3_encode(raw), owner="voice")
        done.append(x["slot"])
    # 能力 6 学会后整场处于「技能切换」状态，准备语音改读 matched_skill_ready（_alt_N 同样轮换，run3 127 号）；
    # 同内容各放一份，切换前后都是这 4 句。技能语音 matched_skill_N 缺省时客户端原生回落 skill_N，不放。
    for x in lines:
        if x["slot"].startswith("battle/skill_ready"):
            twin = x["slot"].replace("battle/skill_ready", "battle/matched_skill_ready", 1)
            raw = (SRC / (x["slot"] + ".mp3")).read_bytes()
            pack.write_asset("common", f"character/{code}/voice/{twin}.mp3", wf_assets.mp3_encode(raw), owner="voice")
            done.append(twin)
    rows = V.speech_rows([{"slot": x["slot"], "zh": x["zh"]} for x in lines if x["slot"].startswith(("home/", "ally/"))])
    pack.write_flat("master/character/character_speech.orderedmap", {cid: rows})
    return {"installed": len(done), "removed_template": removed, "speech_rows": len(rows)}


if __name__ == "__main__":
    print(json.dumps(install(*(sys.argv[1:] or ["aqua"])), ensure_ascii=False))
