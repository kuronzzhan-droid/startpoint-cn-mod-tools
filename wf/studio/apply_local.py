"""Apply one rehearsed edge to an explicitly enabled machine-configured server."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from . import apply_io as io
from .drafts import DraftError
from .delivery_checks import delivery_checks
from .apply_json import merged_bytes
from .apply_receipts import prepare, execute
from .rehearsal import rehearse
from .rehearsal_inputs import load_inputs
from .rehearsal_io import delivery_folder, inside, json_bytes, read_json
from .rehearsal_server import chain_tail


def merge_keys(before, candidate, pointer=""):
    if not isinstance(before, dict) or not isinstance(candidate, dict):
        raise DraftError("服务端 JSON 必须是对象，列表和整文件替换不支持自动应用")
    result = dict(before)
    for key, value in candidate.items():
        location = pointer + "/" + key.replace("~", "~0").replace("/", "~1")
        if key not in before:
            result[key] = value
        elif isinstance(before[key], dict) and isinstance(value, dict):
            result[key] = merge_keys(before[key], value, location)
        elif type(before[key]) is not type(value) or before[key] != value:
            raise DraftError("服务端 JSON 键值冲突：" + location)
    return result


def _plan(folder, root, rehearsal):
    changes = []
    paths, _, _, _, _ = load_inputs(folder)
    by_name = {p.name: p for p in paths}
    for archive in rehearsal["archives"]:
        relative = "assets/asset-patch/active/" + archive["name"]
        raw = by_name[archive["name"]].read_bytes()
        if io.sha(raw) != archive["sha256"]:
            raise DraftError("交付 ZIP 在预演后变化")
        before = io.content(io.target(root, relative))
        if before is None:
            changes.append((relative, None, raw))
        elif before != raw:
            raise DraftError("active 同名不同内容：" + archive["name"])
    for item in rehearsal["serverChanges"]:
        if (item["kind"] != "json" or not item["target"].startswith("assets/")
                or item["target"].startswith("assets/asset-patch/")):
            raise DraftError("应用只支持服务端 JSON 按键合并；代码需要独立人工流程")
        source = inside(folder, Path(item["source"]).relative_to(folder).as_posix())
        if io.sha(source.read_bytes()) != item["sha256"]:
            raise DraftError("服务端候选在预演后变化")
        destination = io.target(root, item["target"])
        before = io.content(destination)
        old = read_json(destination) if before is not None else {}
        candidate = read_json(source)
        if io.sha(source.read_bytes()) != item["sha256"]:
            raise DraftError("服务端候选读取期间变化")
        merged = merge_keys(old, candidate)
        if merged != old or before is None:
            changes.append((item["target"], before, merged_bytes(before, old, merged)))
    before = io.content(io.target(root, io.MANIFEST))
    manifest = read_json(io.target(root, io.MANIFEST))
    if chain_tail(manifest) != rehearsal["from"]:
        raise DraftError("服务端链尾与交付 from 不符")
    manifest["patches"].append(rehearsal["manifestEntry"])
    manifest["cdn_version"] = rehearsal["to"]
    changes.append((io.MANIFEST, before, json_bytes(manifest)))
    io.verify(root, rehearsal["serverSnapshot"])
    return changes


def apply(delivery_dir, server="local", *, dry_run=False):
    steps = []
    result = {"ok": False, "status": "blocked", "server": server, "dryRun": dry_run,
              "steps": steps, "restartRequired": False, "restartReason": "尚未应用"}
    try:
        root = io.enabled_root(server)
        folder = delivery_folder(delivery_dir)
        backup = io.receipt_folder(folder, root, server)
        with io.server_lock(root):
            preview = rehearse(folder, server, write=False)
            steps.append({"step": "rehearse", "status": preview["status"], "checks": preview["checks"]})
            if not preview["ok"] or any(c["blocking"] for c in preview["checks"]):
                raise DraftError("重新预演存在阻断项")
            delivery_checks(folder)
            steps.append({"step": "delivery-check", "status": "done"})
            changes = _plan(folder, root, preview)
            result.update({"from": preview["from"], "to": preview["to"],
                           "restartRequired": preview["restartRequired"], "restartReason": preview["restartReason"]})
            if dry_run:
                result.update(ok=True, status="dry-run", files=[c[0] for c in changes])
                return result
            receipt = {"schema": "wf-studio-applied/1", "server": server, "serverRoot": str(root),
                       "deliveryDir": str(folder), "createdAt": datetime.now(timezone.utc).isoformat(),
                       "from": preview["from"], "to": preview["to"], "manifestEntry": preview["manifestEntry"],
                       "restartRequired": result["restartRequired"], "restartReason": result["restartReason"],
                       "files": [], "placedFiles": [c[0] for c in changes if c[1] is None],
                       "status": "prepared", "steps": steps}
            receipt["afterSnapshot"] = {**preview["serverSnapshot"],
                                        **{rel: io.sha(after) for rel, _, after in changes}}
            receipt_path = inside(backup, "receipt.json")
            prepare(backup, receipt, changes)
            execute(root, changes, preview["serverSnapshot"], steps, receipt, receipt_path,
                    before_manifest=preview["from"])
            result.update(ok=True, status="applied", receipt=str(receipt_path), files=receipt["files"])
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        result["error"] = str(exc)
        result["status"] = "failed" if any(s["step"] == "write" for s in steps) else "blocked"
    return result


def unapply(delivery_dir, server="local"):
    steps = []
    result = {"ok": False, "status": "blocked", "server": server, "steps": steps, "clientRisk": io.CLIENT_RISK}
    try:
        root = io.enabled_root(server)
        folder = delivery_folder(delivery_dir)
        backup = io.receipt_folder(folder, root, server)
        with io.server_lock(root):
            receipt_path = inside(backup, "receipt.json")
            receipt = read_json(receipt_path)
            if (receipt.get("status") != "applied" or receipt.get("serverRoot") != str(root)
                    or receipt.get("server") != server or receipt.get("deliveryDir") != str(folder)):
                raise DraftError("回执不是本服务端、本交付的已应用事务")
            manifest = read_json(io.target(root, io.MANIFEST))
            if chain_tail(manifest) != receipt["to"] or manifest["patches"][-1] != receipt["manifestEntry"]:
                raise DraftError("只能撤销仍是链尾的交付")
            io.verify(root, receipt["afterSnapshot"])
            changes = []
            for item in reversed(receipt["files"]):
                before = inside(backup, item["backup"]).read_bytes() if item["backup"] else None
                if io.sha(before) != item["beforeSha256"]:
                    raise DraftError("备份摘要不符")
                changes.append((item["path"], io.content(io.target(root, item["path"])), before))
            receipt["unappliedAt"] = datetime.now(timezone.utc).isoformat()
            receipt["unapplySteps"] = steps
            execute(root, changes, receipt["afterSnapshot"], steps, receipt, receipt_path, undo=True)
            result.update(ok=True, status="unapplied", receipt=str(receipt_path),
                          restartRequired=receipt["restartRequired"],
                          restartReason=("撤销服务端 JSON 后需要人工重启" if receipt["restartRequired"]
                                         else "仅撤销客户端资源边，manifest 热加载，无需重启"))
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        result["error"] = str(exc)
        result["status"] = "failed" if any(s["step"] == "write" for s in steps) else "blocked"
    return result
