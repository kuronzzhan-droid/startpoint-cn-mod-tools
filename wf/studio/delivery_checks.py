"""Read the saved build gates with their original report contracts."""
from .drafts import DraftError
from .rehearsal_io import inside, read_json


def delivery_checks(folder):
    manifest_path = inside(folder, "delivery-manifest.json")
    manifest = read_json(manifest_path) if manifest_path.is_file() else {}
    if not isinstance(manifest, dict):
        raise DraftError("交付清单必须是对象")
    build = folder.parent / "build-report.json"
    if folder.name == "delivery" and build.is_file() and read_json(build).get("ok") is not True:
        raise DraftError("构建报告未通过")
    prepush = manifest.get("prepush", {})
    if prepush.get("exit_code") or prepush.get("status") == "问题":
        raise DraftError("prepush 检查未通过")
    compat = manifest.get("client_compatibility") or {}
    if compat.get("status") == "问题" or (compat.get("status") == "未确认"
                                          and compat.get("allow_unknown_client") is not True):
        raise DraftError("客户端兼容性未通过")
    reports = {"check.json": (True, False), "compat.json": (False, False),
               "draft-checks.json": (False, True), "safety-checks.json": (False, False)}
    for name, draft in ((compat.get("report"), False), (manifest.get("draft_checks"), True),
                        (manifest.get("safety_checks"), False)):
        if name is not None:
            reports[name] = (True, draft)
    checks = []
    for name, (required, draft) in reports.items():
        path = inside(folder, name)
        if not required and not path.exists():
            continue
        doc = read_json(path)
        rows = doc.get("results") if isinstance(doc, dict) else doc
        if not isinstance(rows, list) or (name == "check.json" and not rows):
            raise DraftError("缺少有效交付检查结果：" + name)
        for row in rows:
            if (not isinstance(row, dict) or row.get("level") == "error"
                    or row.get("state") == "问题" or row.get("status") == "问题"
                    or (bool(row.get("blocking")) if draft else row.get("blocking") is not False)):
                raise DraftError("交付检查存在阻断项：" + name)
        checks.extend(rows)
    return checks
