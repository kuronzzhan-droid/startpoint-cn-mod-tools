"""Prepare immutable backups and keep transaction failure evidence recoverable."""
import os
import tempfile
import uuid
from pathlib import Path

from . import apply_io as io
from .drafts import DraftError
from .rehearsal_io import inside, json_bytes, read_json


def prepare(backup, receipt, changes):
    if backup.exists():
        previous = read_json(inside(backup, "receipt.json"))
        if previous.get("status") not in {"unapplied", "rolled-back"}:
            raise DraftError("该交付已有应用备份/回执，拒绝覆盖")
        history = backup.parent / ".history"
        history.mkdir(exist_ok=True)
        os.rename(backup, history / (backup.name + "-" + uuid.uuid4().hex))
    backup.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".studio-", dir=backup.parent) as temporary:
        staged = Path(temporary) / "receipt"
        staged.mkdir()
        for index, (relative, before, after) in enumerate(changes):
            name = f"before/{index:04d}.bin" if before is not None else None
            if name:
                io.atomic_write(inside(staged, name), before)
            receipt["files"].append({"path": relative, "beforeSha256": io.sha(before),
                                     "afterSha256": io.sha(after), "backup": name})
        io.atomic_write(staged / "receipt.json", json_bytes(receipt))
        os.rename(staged, backup)


def execute(root, changes, expected, steps, receipt, path, *, undo=False, before_manifest=None):
    """Commit files and receipt, or recover the pre-operation state and record it."""
    completed = False
    old_status = "applied" if undo else "rolled-back"
    try:
        io.transact(root, changes, dict(expected), steps, before_manifest)
        completed = True
        receipt["status"] = "unapplied" if undo else "applied"
        io.atomic_write(path, json_bytes(receipt))
    except Exception as exc:
        recovery = isinstance(exc, io.RecoveryRequired)
        if completed:
            try:
                io.transact(root, [(r, a, b) for r, b, a in reversed(changes)],
                            {**expected, **{r: io.sha(a) for r, _, a in changes}}, steps)
            except Exception as rollback_error:
                recovery = True
                steps.append({"step": "receipt-rollback", "status": "failed", "error": str(rollback_error)})
        receipt["status"] = "rollback-failed" if recovery else old_status
        receipt["error"] = str(exc)
        try:
            io.atomic_write(path, json_bytes(receipt))
        except Exception as receipt_error:
            recovery = True
            steps.append({"step": "failure-receipt", "status": "failed", "error": str(receipt_error)})
        if recovery:
            raise io.RecoveryRequired("事务或回执恢复未完成；已保留服务端锁，请核对备份人工恢复：" + str(exc)) from exc
        raise
