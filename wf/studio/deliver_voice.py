"""Existing-path voice replacement, including the strict stored MP3 gate."""
from __future__ import annotations

import wf_assets

from .deliver_media import MediaResult, draft_file, require_raw
from .drafts import DraftError, sha256


def compile_voices(source, store, changeset: dict) -> MediaResult:
    result = MediaResult()
    cid, code = changeset["characterId"], changeset["code"]
    for change in changeset["changes"]:
        if change["kind"] != "voice_line":
            continue
        logical = f"character/{code}/voice/{change['target']['voice']}.mp3"
        if len(change["files"]) != 1:
            raise DraftError("问题：语音草稿必须且只能含一个 MP3")
        entry = change["files"][0]
        if (entry["root"], entry["logical"], entry["encoding"]) != ("common", logical, "mp3"):
            raise DraftError("问题：语音草稿的路径、根或编码与目标不一致")
        before = require_raw(source, "common", logical)
        stored = draft_file(source, store, cid, entry)
        probe = wf_assets.mp3_probe(stored, 1023)
        if not probe["frames"] or probe["tail"] < 0:
            raise DraftError("问题：语音存储态音频帧不完整")
        result.members["common", logical] = stored
        result.assertions.append({"kind": "voice_line", "logical": logical,
                                  "before_sha256": sha256(before), "sha256": sha256(stored)})
        result.checks.append({"state": "满足", "code": "studio.voice.stored",
                              "message": f"{logical}：已有路径、CBR 存储态与逐字节往返通过"})
    return result
