"""Append-only speech drafts; preserve unrelated orderedmap leaves verbatim."""
from __future__ import annotations

import wf_mod_tool as core

from .clone_tables import leaf, validate_speech
from .deliver_media import MediaResult, read_root
from .drafts import DraftError, sha256, validate

LOGICAL = "master/character/character_speech.orderedmap"


def additions(draft):
    changes = [c for c in (draft or {}).get("changes", []) if c["kind"] == "speech_rows"]
    if len(changes) > 1:
        raise DraftError("新增台词草稿重复")
    return changes[0] if changes else None


def effective_rows(source, cid, draft):
    if hasattr(source, "table"):
        original = source.table(LOGICAL).get(cid, [])
    else:
        # Media compilers also accept root-only sources without a table cache.
        raw = read_root(source, "common", LOGICAL)
        entries = core.read_orderedmap_file_from_bytes(raw) if raw is not None else {}
        original = core.read_csv_lines(entries[cid]) if cid in entries else []
    rows = [list(row) for row in original]
    change = additions(draft)
    return rows + (change["params"]["rows"] if change else [])


def guard_revert(draft, removed, baseline=None):
    """Keep speech registrations while uploaded audio still depends on them.

    API callers provide baseline registrations. Offline CLI reverts have no
    source: without baseline audio bytes, conservatively require audio removal
    first instead of deleting potentially shared uploads.
    """
    from .voice import FIXED_LINES
    voices = {r[4] for c in removed if c["kind"] == "speech_rows" for r in c["params"]["rows"]}
    voices.difference_update(FIXED_LINES)
    if baseline is not None:
        voices.difference_update(baseline)
    dependent = [c["target"]["voice"] for c in draft["changes"] if c["kind"] == "voice_line"
                 and c["target"]["voice"] in voices
                 and (baseline is not None or not c["files"][0].get("base", {}).get("sha256"))]
    if dependent:
        raise DraftError("请先撤销依赖新增台词的音频，再撤销台词：" + "、".join(dependent))


def coverage(rows):
    try:
        validate_speech(rows)
    except DraftError as exc:
        return [{"level": "error", "code": "speech.home_states", "message": str(exc)}]
    return []


def append(ops, cid, request):
    from .character_clone import ops_for
    bound = ops_for(ops, cid)
    if bound is not ops:
        return append(bound, cid, request)
    validate(request, "speechRequest")
    info = ops.character(cid)
    with ops.store._lock:
        draft = ops.store.load(cid)
        previous = additions(draft)
        raw = read_root(ops.source, "common", LOGICAL)
        digest = sha256(raw) if raw is not None else None
        if previous and previous["params"]["beforeSha256"] != digest:
            raise DraftError("台词表旧值断言失败，请重建新增台词草稿")
        rows = [*(previous["params"]["rows"] if previous else []), *request["rows"]]
        all_rows = [*ops.source.table(LOGICAL).get(cid, []), *rows]
        if len({tuple(r) for r in all_rows}) != len(all_rows):
            raise DraftError("不能重复添加相同台词行")
        built = {"title": f"新增台词（{len(rows)} 行）", "target": {"character": cid},
                 "params": {"rows": rows, "beforeSha256": digest}, "files": [],
                 "pending": [{"logical": LOGICAL, "reason": "追加五列台词；交付时复核主页两态与音频"}],
                 "checks": coverage(all_rows)}
        return ops._commit(cid, info["code"], "speech_rows", built)


def compile_speech(source, store, draft):
    result = MediaResult()
    change = additions(draft)
    if not change:
        return result
    validate(change, "change")
    cid, code = draft["characterId"], draft["code"]
    if change["target"]["character"] != cid:
        raise DraftError("台词目标与角色不一致")
    raw = read_root(source, "common", LOGICAL)
    digest = sha256(raw) if raw is not None else None
    if digest != change["params"]["beforeSha256"]:
        raise DraftError("台词表旧值断言失败")
    rows = effective_rows(source, cid, draft)
    validate_speech(rows)
    # Audio additions must be provided by the ordinary voice compiler (same format gate).
    audio = {c["target"]["voice"] for c in draft["changes"] if c["kind"] == "voice_line"}
    for row in change["params"]["rows"]:
        voice = row[4]
        if voice != "(None)" and voice not in audio and read_root(source, "common", f"character/{code}/voice/{voice}.mp3") is None:
            raise DraftError(f"新增台词缺少音频：{voice}；请上传音频或使用 (None) 无声字幕")
    if raw is None:
        from pathlib import Path
        table = core.OrderedMap(LOGICAL, [], [], Path("speech"))
    else:
        table = core.read_orderedmap_raw_rows_from_bytes(raw, LOGICAL)
    if cid in table.keys:
        table.rows[table.keys.index(cid)] = leaf(rows)
    else:
        table.keys.append(cid)
        table.rows.append(leaf(rows))
    compiled = core.build_orderedmap_raw_rows(table)
    result.members["common", LOGICAL] = compiled
    result.assertions.append({"kind": "speech_rows", "character": cid,
                              "before_sha256": digest, "sha256": sha256(compiled)})
    result.checks.append({"state": "满足", "code": "studio.speech.home_states",
                          "message": "新增台词五列、单路径、主页两态、入队、一级进化台词及音频引用复核通过"})
    return result
