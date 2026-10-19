"""交付的真机实测记录（device-result.json）：读、写、导入与截图白名单。

一份交付目录（``work/studio-deliveries/<name>/`` 或 ``.../boss/<name>/``）根下最多一个
``device-result.json``，结构见 ``schemas/device-result.schema.json``（``wf-device-result/2``）。
编辑台写入时：

* ``delivery`` 绑定（交付名、草稿修订、来源/目标版本、ZIP sha256）一律按交付目录自己的
  ``build-report.json`` 与 ``delivery/delivery-manifest.json`` 重新填写，请求体里的值不算数；
* 旧文件先移到 ``device-results/<时间>.json`` 再写新文件（不覆盖历史）；
* 旧版 ``wf-device-result/1``（device-round-1 手写，checks 用 what/expect/result）读取与导入时
  按 :func:`normalize` 转换，原文件不改。

截图只从配置的白名单目录读取（profiles/local.json 的 ``paths.studio_screenshots``，
字符串或字符串数组；或环境变量 ``WF_STUDIO_SCREENSHOTS``，多个用系统路径分隔符；或
``python -m wf.studio --screenshots-dir``）。不在白名单里的路径只显示文字，不读文件。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path

from wf.paths import REPOSITORY

from .drafts import DraftError

SCHEMA_PATH = REPOSITORY / "schemas" / "device-result.schema.json"
SCHEMA_ID = "wf-device-result/2"
LEGACY_ID = "wf-device-result/1"
FILENAME = "device-result.json"
HISTORY = "device-results"
MAX_BYTES = 1024 * 1024
MAX_IMAGE = 32 * 1024 * 1024
IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
STATUSES = ("通过", "失败", "未执行", "作废")
SUBJECT = re.compile(r"^(?P<subject>.+?)-\d+\.\d+\.\d+-to-\d+\.\d+\.\d+-\d{8}-\d{6}$")
VERSION = re.compile(r"\d+\.\d+\.\d+")
PACKAGE = re.compile(r"\b(?:com|net|org|jp|cn)\.[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+\b")

_schema: dict | None = None


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def schema() -> dict:
    global _schema
    if _schema is None:
        _schema = json.loads(SCHEMA_PATH.read_text("utf-8"))
    return _schema


def schema_errors(value) -> list[str]:
    import jsonschema
    validator = jsonschema.Draft202012Validator(schema())
    errors = sorted(validator.iter_errors(value), key=lambda e: list(e.absolute_path))
    return [f"{'/'.join(map(str, e.absolute_path)) or '(根)'}: {e.message}" for e in errors]


def _json_file(path: Path):
    path = Path(path)
    if not path.is_file():
        raise DraftError(f"没有这个文件：{path}")
    if path.stat().st_size > MAX_BYTES:
        raise DraftError(f"实测记录超过 {MAX_BYTES // 1024} KB：{path}")
    raw = path.read_bytes()
    try:
        value = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeError, ValueError) as exc:
        raise DraftError(f"不是 UTF-8 JSON：{path}（{exc}）") from exc
    if not isinstance(value, dict):
        raise DraftError(f"实测记录必须是 JSON 对象：{path}")
    return value, hashlib.sha256(raw).hexdigest()


def _read_json(path: Path):
    try:
        return json.loads(Path(path).read_text("utf-8"))
    except (OSError, ValueError):
        return None


# -- legacy wf-device-result/1 -------------------------------------------------
def _check_status(text: str) -> str | None:
    text = (text or "").strip()
    for status in ("通过", "失败"):
        if text.startswith(status):
            return status
    if text.startswith("未"):
        return "未执行"
    return None


def _legacy(raw: dict) -> dict:
    target = raw.get("target") if isinstance(raw.get("target"), dict) else {}
    label = str(target.get("device") or "")
    device = {k: v for k, v in {
        "label": label, "apk": str(target.get("apk") or ""),
        "apkSha256": str(target.get("apk_sha256") or "").lower(),
    }.items() if v}
    found = PACKAGE.search(label)
    if found:
        device["package"] = found.group(0)
    if "mumu" in label.lower() or "模拟器" in label:
        device["emulator"] = True
    checks = []
    for item in raw.get("checks") or []:
        if not isinstance(item, dict):
            continue
        check = {"item": str(item.get("what") or item.get("item") or "（未命名）"),
                 "expected": str(item.get("expect") or item.get("expected") or ""),
                 "observed": str(item.get("result") or item.get("observed") or "")}
        status = item.get("status") if item.get("status") in ("通过", "失败", "未执行") else _check_status(check["observed"])
        if status:
            check["status"] = status
        if item.get("screenshot"):
            check["screenshot"] = str(item["screenshot"])
        checks.append(check)
    status = raw.get("status") if raw.get("status") in STATUSES else "未执行"
    reason = str(raw.get("reason") or "")
    if status == "未执行" and reason.startswith("已作废"):
        status = "作废"
    edges = []
    if raw.get("edge"):
        match = VERSION.search(str(raw["edge"]))
        if match:
            edges.append({"version": match.group(0), "note": str(raw["edge"])})
    client = {k: v for k, v in {"versionBefore": str(target.get("client_res_version_before") or ""),
                                "profile": str(target.get("client_profile_used") or "")}.items() if v}
    known = {"schema", "target", "recordedAt", "error_codes", "error_scan", "status", "edge", "checks",
             "screenshots", "reason", "notes", "tester"}
    result = {"schema": SCHEMA_ID, "status": status, "testedAt": str(raw.get("recordedAt") or raw.get("testedAt") or ""),
              "checks": checks, "screenshots": [str(s) for s in raw.get("screenshots") or [] if s],
              "errorCodes": [str(c) for c in raw.get("error_codes") or []]}
    optional = {"reason": reason, "server": str(target.get("server") or ""),
                "errorScan": str(raw.get("error_scan") or ""), "notes": str(raw.get("notes") or ""),
                "tester": str(raw.get("tester") or "")}
    result.update({k: v for k, v in optional.items() if v})
    if device:
        result["device"] = device
    if client:
        result["client"] = client
    if edges:
        result["chainEdges"] = edges
    extra = {k: v for k, v in raw.items() if k not in known}
    extra.update({f"target.{k}": v for k, v in target.items()
                  if k not in ("server", "device", "apk", "apk_sha256", "client_res_version_before", "client_profile_used")})
    if extra:
        result["extra"] = extra
    return result


def normalize(raw: dict) -> tuple[dict, bool]:
    """Any known version → canonical (without trusting its ``delivery``); ``True`` when legacy."""
    if not isinstance(raw, dict):
        raise DraftError("实测记录必须是 JSON 对象")
    kind = raw.get("schema")
    if kind == LEGACY_ID or (kind is None and ("target" in raw or "recordedAt" in raw)):
        return _legacy(raw), True
    if kind not in (SCHEMA_ID, None):
        raise DraftError(f"不认识的实测记录版本：{kind}")
    return {**raw, "schema": SCHEMA_ID}, False


# -- delivery binding ---------------------------------------------------------
def subject_of(name: str) -> str | None:
    match = SUBJECT.match(name)
    return match.group("subject") if match else None


def archives_of(folder: Path) -> list[dict]:
    manifest = _read_json(Path(folder) / "delivery" / "delivery-manifest.json") or {}
    return [{"name": str(a["name"]), "sha256": str(a["sha256"])} for a in manifest.get("archives", [])
            if isinstance(a, dict) and a.get("name") and re.fullmatch(r"[0-9a-f]{64}", str(a.get("sha256") or ""))]


def binding(folder: Path, kind: str) -> dict:
    folder = Path(folder)
    report = _read_json(folder / "build-report.json") or {}
    revision = report.get("draftRevision")
    created = (_read_json(folder / "inputs" / "draft.json") or {}).get("createdAt")
    return {"name": folder.name, "kind": kind, "subject": subject_of(folder.name),
            "draftRevision": revision if isinstance(revision, int) else None,
            "draftCreatedAt": created if isinstance(created, str) else None,
            "from": report.get("from") if isinstance(report.get("from"), str) else None,
            "to": report.get("to") if isinstance(report.get("to"), str) else None,
            "archives": archives_of(folder)}


def _finish(result: dict, folder: Path, kind: str) -> dict:
    result = {k: v for k, v in result.items() if k != "delivery"}
    result["delivery"] = binding(folder, kind)
    result.setdefault("checks", [])
    result["recordedAt"] = now()
    problems = schema_errors(result)
    if problems:
        raise DraftError("实测记录不符合 device-result.schema.json：" + "；".join(problems[:6]))
    return result


def _store(folder: Path, result: dict) -> Path:
    path = Path(folder) / FILENAME
    if path.is_file():
        history = Path(folder) / HISTORY
        history.mkdir(exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        target, n = history / f"{stamp}.json", 1
        while target.exists():
            n += 1
            target = history / f"{stamp}-{n}.json"
        path.replace(target)
    temporary = path.with_name(FILENAME + ".tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", "utf-8")
    temporary.replace(path)
    return path


def write(folder: Path, kind: str, payload: dict) -> dict:
    """Record (or replace) the device result of one delivery folder."""
    if not isinstance(payload, dict):
        raise DraftError("请求体必须是实测记录对象")
    if not (Path(folder) / "build-report.json").is_file():
        raise DraftError("交付目录没有 build-report.json（生成未完成），不能记录实测")
    body = payload.get("result", payload)
    result, _ = normalize({k: v for k, v in body.items() if k not in ("recordedAt", "importedFrom")})
    result = _finish(result, folder, kind)
    _store(folder, result)
    return result


def import_file(source: Path, folder: Path, kind: str, *, allow_unverified: bool = False) -> dict:
    """Import an existing device-result.json (any version) into ``folder``.

    ``source`` is the JSON file or the delivery folder holding it. The source delivery's ZIP
    sha256 set must equal the target's; without a source manifest the import needs
    ``allow_unverified`` and is marked ``archivesMatch: null``."""
    source = Path(source)
    if source.is_dir():
        source = source / FILENAME
    raw, digest = _json_file(source)
    result, legacy = normalize(raw)
    theirs = archives_of(source.parent) if (source.parent / "delivery" / "delivery-manifest.json").is_file() else None
    ours = archives_of(folder)
    if theirs is None:
        if not allow_unverified:
            raise DraftError("来源目录没有 delivery/delivery-manifest.json，无法确认是同一份交付；确认无误再加 allowUnverified")
        match = None
    else:
        match = sorted(a["sha256"] for a in theirs) == sorted(a["sha256"] for a in ours)
        if not match:
            raise DraftError(f"来源交付 {source.parent.name} 的 ZIP 与目标交付 {Path(folder).name} 不一致，拒绝导入")
    result.pop("importedFrom", None)
    result["importedFrom"] = {"path": str(source.resolve()), "sha256": digest,
                              "schema": str(raw.get("schema") or (LEGACY_ID if legacy else SCHEMA_ID)),
                              "delivery": source.parent.name, "archivesMatch": match, "at": now()}
    result = _finish(result, folder, kind)
    _store(folder, result)
    return result


def read(folder: Path, kind: str) -> dict | None:
    """The stored result (normalized for display), or None when the delivery has none."""
    path = Path(folder) / FILENAME
    if not path.is_file():
        return None
    try:
        raw, _ = _json_file(path)
        result, legacy = normalize(raw)
    except DraftError as exc:
        return {"path": str(path), "result": None, "legacy": False, "errors": [str(exc)], "history": 0}
    stored = result.get("delivery") if isinstance(result.get("delivery"), dict) else None
    current = binding(folder, kind)
    if stored is None:
        result["delivery"] = current  # legacy: it sits in this folder, bind to it for display
    problems = schema_errors(result)
    history = Path(folder) / HISTORY
    count = len([p for p in history.glob("*.json")]) if history.is_dir() else 0
    mismatch = bool(stored) and (stored.get("name") != current["name"]
                                 or sorted(a["sha256"] for a in stored.get("archives") or [])
                                 != sorted(a["sha256"] for a in current["archives"]))
    return {"path": str(path), "result": result, "legacy": legacy, "errors": problems, "history": count,
            "bindingMismatch": mismatch}


def stale(result: dict | None, draft: dict | None) -> bool:
    """The draft changed after this delivery was built (and so after it was tested)."""
    if not result or not draft:
        return False
    bound = result.get("delivery") or {}
    if bound.get("draftRevision") is not None and bound["draftRevision"] != draft.get("revision"):
        return True
    created = bound.get("draftCreatedAt")
    return bool(created and draft.get("createdAt") and created != draft["createdAt"])


def summary(entry: dict | None, draft: dict | None = None) -> dict | None:
    if not entry or not entry.get("result"):
        return {"status": "无效", "errors": entry.get("errors", [])} if entry else None
    result = entry["result"]
    return {"status": result.get("status"), "testedAt": result.get("testedAt"), "tester": result.get("tester") or "",
            "draftRevision": (result.get("delivery") or {}).get("draftRevision"),
            "checks": len(result.get("checks") or []), "legacy": entry.get("legacy", False),
            "imported": "importedFrom" in result, "stale": stale(result, draft)}


# -- screenshots --------------------------------------------------------------
def configured_screenshot_dirs(extra=()) -> list[Path]:
    from wf.paths import profile_data, root_path
    values: list[str] = []
    env = os.environ.get("WF_STUDIO_SCREENSHOTS")
    if env:
        values.extend(v for v in env.split(os.pathsep) if v.strip())
    try:
        config, _ = profile_data()
    except (ValueError, OSError):
        config = {}
    raw = (config.get("paths") or {}).get("studio_screenshots")
    if isinstance(raw, str):
        values.append(raw)
    elif isinstance(raw, list):
        values.extend(str(v) for v in raw if isinstance(v, str) and v.strip())
    values.extend(str(v) for v in extra)
    dirs: list[Path] = []
    for value in values:
        path = Path(os.path.expandvars(value)).expanduser()
        if not path.is_absolute():
            path = root_path() / path
        path = path.resolve()
        if path not in dirs:
            dirs.append(path)
    return dirs


class Screenshots:
    def __init__(self, dirs):
        self.dirs = [Path(d).resolve() for d in dirs]

    def allowed(self, value: str) -> Path | None:
        if not value or "\0" in value:
            return None
        try:
            path = Path(value).resolve()
        except (OSError, ValueError):
            return None
        if path.suffix.lower() not in IMAGE_TYPES:
            return None
        if not any(path.is_relative_to(d) for d in self.dirs):
            return None
        return path

    def describe(self, value: str) -> dict:
        path = self.allowed(value)
        return {"path": value, "name": Path(value.replace("\\", "/")).name, "allowed": path is not None,
                "exists": bool(path and path.is_file())}

    def annotate(self, result: dict | None) -> list[dict]:
        if not result:
            return []
        seen, items = set(), []
        for value in [*(result.get("screenshots") or []),
                      *(c.get("screenshot") for c in result.get("checks") or [] if c.get("screenshot"))]:
            if value not in seen:
                seen.add(value)
                items.append(self.describe(value))
        return items

    def read(self, value: str) -> tuple[bytes, str]:
        path = self.allowed(value)
        if path is None:
            raise PermissionError("截图不在白名单目录里（profiles/local.json 的 paths.studio_screenshots）")
        if not path.is_file():
            raise FileNotFoundError("截图文件不存在")
        if path.stat().st_size > MAX_IMAGE:
            raise PermissionError("截图超过 32 MB")
        return path.read_bytes(), IMAGE_TYPES[path.suffix.lower()]

    def public(self) -> list[str]:
        return [str(d) for d in self.dirs]
