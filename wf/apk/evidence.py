"""Read explicit patch records or recognize pinned artifacts without version guessing."""
from __future__ import annotations

import copy
import hashlib
import json
import re
import zipfile
from pathlib import Path


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def v34_evidence() -> dict:
    return json.loads((Path(__file__).parent / "data/v34-evidence.json").read_text("utf-8"))


def v35e_evidence() -> dict:
    """Apply only audited method changes to the immutable v34 evidence set."""
    delta = json.loads((Path(__file__).parent / "data/v35e-evidence.json").read_text("utf-8"))
    base = v34_evidence()
    if base["swf_sha256"] != delta["inherits_swf_sha256"]:
        raise ValueError("v35e evidence inherited SWF identity changed")
    methods = {(m["patch"], m["abc"], m["label"]): m
               for patch in base["patches"] for m in patch["methods"]}
    for update in delta["inherited_method_updates"]:
        method = methods[(update["patch"], update["abc"], update["label"])]
        if method["sha256"] != update["before"] or update["classification"] != "intentional":
            raise ValueError("v35e inherited method update has no matching audited baseline")
        method.update(sha256=update["after"], source=update["final_source"])
    return {**delta, "patches": base["patches"] + delta["patches"]}


def payload_digest(archive: zipfile.ZipFile) -> str:
    """Signature-independent digest of names and uncompressed member contents."""
    names = archive.namelist()
    if len(names) != len(set(names)):
        raise ValueError("APK contains duplicate ZIP member names")
    records = [[name, digest(archive.read(name))] for name in sorted(names)
               if not name.startswith("META-INF/") and not name.endswith("/")]
    return digest(json.dumps(records, separators=(",", ":"), ensure_ascii=False).encode())


def _binary_record(path: Path, data: bytes, known: dict) -> tuple[dict, dict]:
    source = {"path": str(path), "sha256": digest(data), "kind": path.suffix.lower().lstrip(".")}
    artifact = None
    if path.suffix.lower() == ".apk":
        with zipfile.ZipFile(path) as archive:
            primary = "assets/worldflipper_android_release.swf"
            matches = ([primary] if primary in archive.namelist() else
                       [n for n in archive.namelist() if n.endswith(".swf")])
            if len(matches) != 1:
                raise ValueError("APK must contain exactly one SWF for capability recognition")
            swf_sha = digest(archive.read(matches[0]))
            payload_sha = payload_digest(archive)
            source["payload_sha256"] = payload_sha
    else:
        swf_sha = source["sha256"]
    source["swf_sha256"] = swf_sha
    if swf_sha != known["swf_sha256"]:
        candidate = v35e_evidence()
        if swf_sha == candidate["swf_sha256"]:
            known = candidate
    if swf_sha != known["swf_sha256"]:
        raise ValueError("unknown APK/SWF digest; provide a method/patch summary record, not a version label")
    if path.suffix.lower() == ".apk":
        artifact = next((a for a in known["artifacts"] if a["payload_sha256"] == payload_sha), None)
    record = copy.deepcopy(known)
    if artifact:
        excluded = set(artifact["excluded_patches"])
        record["patches"] = [p for p in record["patches"] if p["number"] not in excluded]
        source["basis"] = f"APK 全部非签名成员摘要与已记录 {known['name']} 变体一致；SWF 摘要独立一致"
    else:
        record["patches"] = [p for p in record["patches"] if all(m["sha256"] for m in p["methods"])]
        source["basis"] = f"SWF 摘要与已记录 {known['name']} 一致；资源/原生/ANE 条目未由 SWF 证明，已排除"
    return record, source


def _pipeline_record(document: dict) -> dict:
    """A pipeline config proves only its explicitly enabled patches, never its base."""
    entries = {}
    for row in document["patches"]:
        if row.get("status") != "enabled":
            continue
        match = re.match(r"(\d+)\s*/", row.get("name", ""))
        if not match:
            raise ValueError("pipeline patch needs an explicit archive number in name")
        n = int(match[1])
        # Pipeline configuration pins a code hash but does not identify a stable method
        # label. Retain that limitation instead of inventing a resolved method name.
        entries[n] = {"number": n, "status": "declared", "methods": [],
                      "basis": "显式 enabled 管线记录；方法标签待补，配置不是执行结果"}
    return {"patches": list(entries.values()), "official_systems": False,
            "swf_sha256": None, "basis": "只读取显式管线补丁；不推断 base 的能力"}


def read_evidence(filename: str | Path) -> tuple[dict, dict]:
    path = Path(filename).resolve()
    if path.is_dir():
        path /= "build-report.json"
    data = path.read_bytes()
    known = v34_evidence()
    if path.suffix.lower() in {".apk", ".swf"}:
        try:
            return _binary_record(path, data, known)
        except zipfile.BadZipFile as error:
            raise ValueError(f"invalid APK ZIP: {error}") from error
    document = json.loads(data.decode("utf-8-sig"))
    if not isinstance(document, dict):
        raise ValueError("APK summary must be a JSON object")
    source = {"path": str(path), "sha256": digest(data), "kind": "patch-record"}
    pinned = any(s["sha256"] == source["sha256"] for s in known["sources"]
                 if s["name"].endswith("/build-report.json"))
    if pinned:
        document = known
        source["basis"] = "构建记录逐字节摘要与收录的 v34 证据一致；能力由归档方法记录推导"
    elif document.get("schema") == "wf-apk-summary/1":
        source["basis"] = "调用者显式提供的补丁/方法摘要；未重新读取 APK"
    elif "base" in document and isinstance(document.get("patches"), list):
        document = _pipeline_record(document)
        source["basis"] = document["basis"]
    else:
        raise ValueError("unsupported or modified APK record; expected wf-apk-summary/1 or a pinned build report")
    source["swf_sha256"] = document.get("swf_sha256")
    return document, source
