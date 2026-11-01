"""Review-bound batch orchestration; all mutations are local draft transactions."""
from __future__ import annotations

import json
from pathlib import Path

from .ability import AbilityEditor
from .balance_import import preview_rows, validate_mapping, parse_table
from .clone_checks import response_checks
from .drafts import DraftError, sha256
from .variant_clone import run_variant


def digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def roster(source):
    texts = source.table("text")
    return [{"id": cid, "code": rows[0][0], "name": texts[cid][0][0] if texts.get(cid) else ""}
            for cid, rows in source.table("character").items() if rows]


def selected_rows(body, rows):
    selected = body.get("selected", [])
    if not isinstance(selected, list) or not selected or any(type(i) is not int for i in selected):
        raise DraftError("写草稿前必须逐行勾选（selected 为非空行号数组），默认不写")
    by_id = {row["id"]: row for row in rows}
    if len(selected) != len(set(selected)) or any(i not in by_id for i in selected):
        raise DraftError("勾选行号重复或不存在")
    result = [by_id[i] for i in selected]
    if any(r["status"] not in {"可写草稿", "含需人工（仅存草稿，阻断交付）"} for r in result):
        raise DraftError("需人工的导入行或预检失败的变体不能写入")
    return result


class BatchEditor:
    def __init__(self, ops, mapping_path=None, *, server_dir=None):
        self.ops = ops
        self.server_dir = server_dir
        if mapping_path is None:
            from .drafts import REPOSITORY
            mapping_path = REPOSITORY / "work/studio-batch/balance-mapping.json"
        self.mapping_path = Path(mapping_path)

    def mapping(self, value=None):
        if value is not None:
            validate_mapping(value)
            self.mapping_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.mapping_path.with_suffix(".tmp")
            with self.ops.store._lock:
                temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
                temporary.replace(self.mapping_path)
        return json.loads(self.mapping_path.read_text("utf-8")) if self.mapping_path.exists() else {}

    def balance_preview(self, body):
        # Fresh editor per request so external input changes cannot reuse a stale per-draft memo.
        editor = AbilityEditor(self.ops.source, store=self.ops.store, cache=False, server_dir=self.server_dir)
        document = preview_rows(editor, body.get("text"), body.get("mapping"), roster(self.ops.source))
        versions = {r["characterId"]: self.ops.store.load(r["characterId"])
                    for r in document["rows"] if r["characterId"]}
        document["review"] = digest({"text": body["text"], "mapping": body["mapping"], "result": document,
                                     "drafts": versions, "version": self.ops.source.version})
        return document

    def balance_apply(self, body):
        with self.ops.store._lock:
            document = self.balance_preview(body)
            if body.get("review") != document["review"]:
                raise DraftError("预览已变化或缺少预览凭据，请重新预览并勾选")
            selected = selected_rows(body, document["rows"])
            grouped = {}
            for row in selected:
                grouped.setdefault(row["characterId"], []).extend(row["request"]["operations"])
            editor = AbilityEditor(self.ops.source, store=self.ops.store, cache=False, server_dir=self.server_dir)
            for cid, operations in grouped.items():
                check = editor.preview(cid, {"operations": operations})
                if any(c.get("blocking") or c.get("status") == "问题" for c in check["checks"]):
                    raise DraftError("选中行组合后预检失败：" + json.dumps(check["checks"], ensure_ascii=False))
            before = {cid: self.ops.store.load(cid) for cid in grouped}
            try:
                written = [{"characterId": cid, **editor.apply(cid, {"operations": operations})}
                           for cid, operations in grouped.items()]
            except Exception:
                for cid, draft in before.items():
                    self.ops.store.restore(cid, draft)
                raise
        return {"ok": True, "written": written, "selected": body["selected"], "runtime": "未执行"}

    def variants_preview(self, body):
        targets = body.get("targets")
        if not isinstance(targets, list) or not 1 <= len(targets) <= 20:
            raise DraftError("请选择 1–20 个目标变体")
        if any(not isinstance(t, dict) or not isinstance(t.get("to"), str) or
               ("code" in t and not isinstance(t["code"], str)) for t in targets):
            raise DraftError("目标必须为对象，ID / 代码名必须是字符串")
        ids = [t.get("to") for t in targets if isinstance(t, dict)]
        codes = [t.get("code") or f"variant_{body.get('from')}_{t.get('to')}" for t in targets if isinstance(t, dict)]
        if len(ids) != len(targets) or len(ids) != len(set(ids)) or len(codes) != len(set(codes)):
            raise DraftError("目标 ID / 代码名不能重复，目标必须为对象")
        rows = []
        for i, target in enumerate(targets, 1):
            item = {"id": i, "target": target, "status": "需人工", "selected": False, "reason": "", "checks": []}
            try:
                document = run_variant(self.ops, body, target, server_dir=self.server_dir)
                state = "可写草稿" if document["buildable"] else "含需人工（仅存草稿，阻断交付）"
                item.update(status=state, result=document, checks=response_checks(document))
            except (ValueError, KeyError, OSError, TypeError) as exc:
                item["reason"] = str(exc)
            rows.append(item)
        result = {"rows": rows, "runtime": "未执行", "version": self.ops.source.version}
        result["review"] = digest({"request": {k: body.get(k) for k in ("from", "rule", "targets")}, "result": result})
        return result

    def variants_apply(self, body):
        with self.ops.store._lock:
            document = self.variants_preview(body)
            if body.get("review") != document["review"]:
                raise DraftError("预览已变化或缺少预览凭据，请重新预览并勾选")
            selected = selected_rows(body, document["rows"])
            created, written = [], []
            try:
                for row in selected:
                    result = run_variant(self.ops, body, row["target"], preview=False, server_dir=self.server_dir)
                    created.append(result["characterId"])
                    written.append(result)
            except Exception:
                for cid in created:
                    self.ops.store.discard_all(cid)
                raise
        return {"ok": True, "written": written, "runtime": "未执行"}


def add_commands(sub):
    p = sub.add_parser("balance-import", help="本地 TSV/CSV 平衡表：默认只预览，显式选择后写草稿")
    p.add_argument("--file", type=Path, required=True)
    p.add_argument("--mapping", type=Path, help="字段到表头的 JSON 映射；省略则读上次映射")
    p.add_argument("--remember-mapping", action="store_true")
    p.add_argument("--select", type=int, action="append", default=[], help="逐行勾选，可重复；行号取预览 id")
    p.add_argument("--review", help="上次预览返回的 review 摘要；写入必须提供")


def run_command(args, ops):
    service = BatchEditor(ops, server_dir=args.server_dir)
    mapping = json.loads(args.mapping.read_text("utf-8-sig")) if args.mapping else service.mapping()
    text = args.file.read_text("utf-8-sig")
    if not args.mapping:
        headers, _ = parse_table(text)
        mapping = {k: "" if k in {"row", "column"} and v not in headers else v for k, v in mapping.items()}
    if args.remember_mapping:
        service.mapping(mapping)
    body = {"text": text, "mapping": mapping,
            "selected": args.select, "review": args.review}
    return service.balance_apply(body) if args.select else service.balance_preview(body)
