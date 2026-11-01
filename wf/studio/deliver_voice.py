"""Registered-path voice uploads, including the strict stored MP3 gate."""
from __future__ import annotations

import wf_assets

from .deliver_media import MediaResult, draft_file, read_root
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
        before = read_root(source, "common", logical)
        if before is None:
            from .speech import effective_rows
            from .voice import FIXED_LINES
            registered = {r[4] for r in effective_rows(source, cid, changeset) if len(r) == 5} | set(FIXED_LINES)
            if change["target"]["voice"] not in registered:
                raise DraftError("问题：新音频没有对应的新增台词登记")
        stored = draft_file(source, store, cid, entry)
        probe = wf_assets.mp3_probe(stored, 1023)
        if not probe["frames"] or probe["tail"] < 0:
            raise DraftError("问题：语音存储态音频帧不完整")
        if probe["srates"] != {44100} or probe["channels"] != {1}:
            raise DraftError("问题：语音必须为 44.1 kHz 单声道 MP3")
        result.members["common", logical] = stored
        result.assertions.append({"kind": "voice_line", "logical": logical,
                                  "before_sha256": sha256(before) if before is not None else None, "sha256": sha256(stored)})
        result.checks.append({"state": "满足", "code": "studio.voice.stored",
                              "message": f"{logical}：已登记路径、44.1 kHz 单声道、CBR 存储态与逐字节往返通过"})
    return result
