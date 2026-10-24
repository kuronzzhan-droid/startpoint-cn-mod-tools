"""稿主交接单：把「作者说了什么」「草稿里真有什么文件」「还没进游戏的部分」分三栏列清。

外部画师交稿时最容易混在一起的三件事：

1. **作者说明**——稿主自己写的：这一套是什么、每个动作的用途、是否带召唤物、
   要注意的地方。存在草稿目录 ``sources/handoff/notes.json``（``sources/`` 不随撤销
   改动被清掉），不进 changeset，不影响生成；
2. **真实文件**——草稿 changeset 里实际存着的文件（逻辑路径、大小、SHA-256），
   以及单动作替换存下的逐帧源 PNG：只列存在的，不按说明推断；
3. **还没接入游戏**——要等「生成」才编进游戏文件的部分（每条改动的 ``pending``）、
   草稿未保存、说明里提到但草稿里没有对应改动的动作。

只读接口给 JSON 和 Markdown（``?format=md``，可直接发给画师/作者）；写接口只改说明。
"""
from __future__ import annotations

import json

from .drafts import DraftError, now, status
from .pixels import SLOT_LABEL

NOTES = "sources/handoff/notes.json"
TEXT_LIMIT = 4000


def _text(value, limit=TEXT_LIMIT) -> str:
    return str(value or "").strip()[:limit]


def load_notes(store, cid: str) -> dict:
    raw = store.read_file(cid, NOTES) if store.directory(cid).is_dir() else None
    if not raw:
        return {"title": "", "author": "", "summary": "", "actions": {}, "notes": "", "updatedAt": None}
    return json.loads(raw.decode("utf-8"))


def save_notes(store, cid: str, body: dict) -> dict:
    actions = {}
    for name, item in (body.get("actions") or {}).items():
        if not isinstance(item, dict) or not isinstance(name, str) or not name.replace("_", "").isalpha():
            raise DraftError(f"动作说明格式不对：{name!r}")
        actions[name] = {"purpose": _text(item.get("purpose"), 200), "includesCompanion": bool(item.get("includesCompanion")),
                         "note": _text(item.get("note"), 1000)}
    notes = {"title": _text(body.get("title"), 120), "author": _text(body.get("author"), 120),
             "summary": _text(body.get("summary")), "actions": actions, "notes": _text(body.get("notes")),
             "updatedAt": now()}
    store.write_file(cid, NOTES, json.dumps(notes, ensure_ascii=False, indent=2).encode("utf-8"))
    return notes


def sheet(ops, cid: str) -> dict:
    info = ops.character(cid)
    store = ops.store
    notes = load_notes(store, cid)
    changeset = store.load(cid) or {"changes": []}
    files, frames, pending, changes = [], [], [], []
    touched_actions: dict[str, dict] = {}
    for change in changeset["changes"]:
        changes.append({"id": change["id"], "kind": change["kind"], "title": change["title"],
                        "errors": sum(1 for c in change.get("checks", []) if c["level"] == "error"),
                        "warnings": sum(1 for c in change.get("checks", []) if c["level"] == "warn")})
        for f in change["files"]:
            files.append({"logical": f["logical"], "size": f["size"], "sha256": f["sha256"], "change": change["title"],
                          "approximate": bool(f.get("approximate"))})
        params = change.get("params", {})
        for index, frame in enumerate(params.get("frames") or []):
            if isinstance(frame, dict) and frame.get("file"):
                frames.append({"file": frame["file"], "sha256": frame.get("sha256"), "change": change["title"],
                               "index": index + 1, "size": [frame.get("width"), frame.get("height")]})
        for item in change.get("pending", []):
            pending.append({"logical": item["logical"], "reason": item.get("reason", ""), "change": change["title"]})
        if change["kind"] == "pixel_action":
            origin = params.get("origin") or {}
            touched_actions[change["target"]["action"]] = {
                "family": change["target"]["family"], "frames": len(params.get("frames") or []),
                "includesCompanion": origin.get("includesCompanion"), "purpose": origin.get("purpose")}
    state = status(changeset if changeset.get("changes") else None)
    not_in_game = [{"kind": "pending", "text": f"{p['logical']}：{p['reason']}", "change": p["change"]} for p in pending]
    if state["state"] == "dirty":
        not_in_game.append({"kind": "unsaved", "text": "草稿有未保存的改动：先在「本次修改」里保存，再生成"})
    for action, note in notes["actions"].items():
        if action not in touched_actions:
            label = SLOT_LABEL.get(action, action)
            not_in_game.append({"kind": "described_only",
                                "text": f"说明里写了 {label}（{action}），但草稿里还没有这个动作的替换"})
    for action, item in touched_actions.items():
        note = notes["actions"].get(action)
        if note and item["includesCompanion"] is not None and bool(item["includesCompanion"]) != note["includesCompanion"]:
            not_in_game.append({"kind": "mismatch",
                                "text": f"{SLOT_LABEL.get(action, action)}：说明写「{'带' if note['includesCompanion'] else '不带'}召唤物」，"
                                        f"导入时标的是「{'带' if item['includesCompanion'] else '不带'}」"})
    actions = []
    for action in sorted(set(notes["actions"]) | set(touched_actions),
                         key=lambda a: (list(SLOT_LABEL).index(a) if a in SLOT_LABEL else 99, a)):
        note, item = notes["actions"].get(action, {}), touched_actions.get(action)
        actions.append({"action": action, "label": SLOT_LABEL.get(action), "purpose": note.get("purpose") or (item or {}).get("purpose") or "",
                        "includesCompanion": note.get("includesCompanion", bool((item or {}).get("includesCompanion"))),
                        "note": note.get("note", ""), "inDraft": item is not None,
                        "frames": item["frames"] if item else 0})
    return {"characterId": cid, "code": info["code"], "name": info.get("name"), "generatedAt": now(),
            "status": state, "notes": notes, "actions": actions, "files": files, "frames": frames,
            "changes": changes, "notInGame": not_in_game}


def _cell(value) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


def markdown(doc: dict) -> str:
    notes = doc["notes"]
    lines = [f"# 交接单：{notes['title'] or doc['name'] or doc['code']}", "",
             f"角色 {doc['characterId']}（{doc['code']}）· {doc['status']['label']} · 生成于 {doc['generatedAt']}", ""]
    lines += ["## 一、作者说明", "", f"- 作者：{notes['author'] or '（未填）'}"]
    if notes["summary"]:
        lines += ["", notes["summary"]]
    if doc["actions"]:
        lines += ["", "| 动作 | 用途 | 带召唤物 | 草稿里 | 备注 |", "|---|---|---|---|---|"]
        for a in doc["actions"]:
            in_draft = f"{a['frames']} 帧" if a["inDraft"] else "没有"
            lines.append(f"| {_cell(a['label'] or a['action'])}（{a['action']}） | {_cell(a['purpose'] or '—')} | "
                         f"{'是' if a['includesCompanion'] else '否'} | {in_draft} | {_cell(a['note'])} |")
    if notes["notes"]:
        lines += ["", notes["notes"]]
    lines += ["", "## 二、草稿里的真实文件", ""]
    if not doc["files"] and not doc["frames"]:
        lines.append("（草稿里没有文件）")
    for f in doc["files"]:
        lines.append(f"- `{f['logical']}` · {f['size']} 字节 · sha256 `{f['sha256'][:16]}…` · {f['change']}"
                     + ("（近似）" if f["approximate"] else ""))
    for f in doc["frames"]:
        lines.append(f"- 源帧 `{f['file']}` · {f['size'][0]}×{f['size'][1]} · sha256 `{(f['sha256'] or '')[:16]}…` · {f['change']}")
    lines += ["", "## 三、还没接入游戏的部分", ""]
    if not doc["notInGame"]:
        lines.append("（没有：草稿里的改动都已是游戏文件，生成后即可测试）")
    for item in doc["notInGame"]:
        lines.append(f"- {item['text']}" + (f"（{item['change']}）" if item.get("change") else ""))
    lines.append("")
    return "\n".join(lines)
