"""Compile a workspace into an immutable release package.

Release layout (also the deployed content layout, so the trial preflight reads it as-is)::

    content_manifest.json
    rogue_corridor_v1.json   rogue_pool_v3f.json   rogue_pool_policy.json
    data/relics.json  data/events.json  data/tier_overrides.json  data/locales_v3.json
    data/new-mode/encounter_pool.json
    data/tier_table.json  data/rules_v3_metadata.json      (locked master copies)

``content_version`` = "sha256:" + sha256 over ``name \\0 sha256 \\n`` of every file sorted by name
(manifest excluded) — the design-doc contract, so equal versions mean byte-identical content.
Unchanged runtime files reuse the imported bytes exactly; changed ones keep the detected style.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import zipfile
from pathlib import Path

from . import jsonio
from .layout import MANIFEST_FILE, MASTER_FILES, POLICY_FILE, RUNTIME_FILES, CorridorConfig
from .store import CorridorStore, StoreError
from .workspace import now


def compile_runtime(workspace: dict, base: dict[str, bytes]) -> dict[str, bytes]:
    out = {}
    for spec in RUNTIME_FILES:
        value = workspace["data"][spec.key]
        raw = base.get(spec.name)
        if raw is not None:
            parsed = jsonio.parse(raw)
            if jsonio.canonical(parsed) == jsonio.canonical(value):
                out[spec.release] = raw
                continue
            out[spec.release] = jsonio.dumps(value, jsonio.detect_style(raw, parsed))
        else:
            out[spec.release] = jsonio.dumps(value)
    policy = {"schema_version": 1, "content_id": workspace["content_id"], "server_reads": False,
              "note": "编辑层策略（服务端未接入；非默认的生效字段在发布前被 B-014 阻断）",
              "policy": workspace["policy"], "lifecycle": workspace["lifecycle"]}
    out[POLICY_FILE] = json.dumps(policy, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    return out


def content_version(files: dict[str, bytes]) -> str:
    lines = "".join(f"{name}\0{jsonio.sha256(files[name])}\n" for name in sorted(files) if name != MANIFEST_FILE)
    return "sha256:" + jsonio.sha256(lines.encode("utf-8"))


def short(version: str) -> str:
    return version.split(":", 1)[-1][:12]


def master_bytes(cfg: CorridorConfig, workspace: dict) -> dict[str, bytes]:
    out = {}
    locks = {"tier_table": workspace["source"]["tier_table_sha256"], "soul_catalog": workspace["source"]["soul_catalog_sha256"]}
    for spec in MASTER_FILES:
        raw = cfg.source_path(spec).read_bytes()
        if jsonio.sha256(raw) != locks[spec.key]:
            raise StoreError(f"{spec.name} 与工作区锁定的哈希不同，拒绝打包（先在总览页重新锁定主数据）")
        out[spec.release] = raw
    return out


def manifest_for(workspace: dict, files: dict[str, bytes], version: str, message: str, validation: dict) -> dict:
    rules = workspace["data"]["rules"]
    roles = {spec.release: ("runtime", spec.server_reads) for spec in RUNTIME_FILES}
    roles.update({spec.release: ("master", True) for spec in MASTER_FILES})
    roles[POLICY_FILE] = ("policy", False)
    return {
        "manifest_version": 1, "content_id": workspace["content_id"], "content_version": version,
        "workspace_revision": workspace["revision"], "source_version": workspace["source"]["game_data_version"],
        "protocol": rules.get("protocol"), "rules_revision": rules.get("rules_revision"),
        "host": rules.get("host"), "active_profile": (rules.get("difficulty") or {}).get("active_profile"),
        "files": [{"name": name, "sha256": jsonio.sha256(raw), "size": len(raw), "role": roles.get(name, ("other", False))[0],
                   "server_reads": roles.get(name, ("other", False))[1]} for name, raw in sorted(files.items())],
        "created_at": now(), "message": message,
        "validation_summary": {"blockers": validation["blockers"], "warnings": validation["warnings"],
                               "warning_codes": sorted({x["code"] for x in validation["findings"] if x["severity"] == "warning"})},
        "server_contract": {"reads_manifest": False, "content_version_pinning": False,
                            "note": "当前试验服不读 manifest/内容版本；应用=替换文件+受控重启"},
    }


def build(store: CorridorStore, cfg: CorridorConfig, workspace: dict, validation: dict, message: str) -> dict:
    if validation["blockers"]:
        raise StoreError(f"还有 {validation['blockers']} 个阻断项，不能打包发布")
    if validation.get("input_digest") != jsonio.digest(workspace):
        raise StoreError("校验结果不是针对当前工作区的，请重新校验")
    files = compile_runtime(workspace, store.base_raw())
    files.update(master_bytes(cfg, workspace))
    version = content_version(files)
    target = store.releases_dir / short(version)
    if target.is_dir():
        manifest = jsonio.read_json(target / MANIFEST_FILE)
        if manifest.get("content_version") != version:
            raise StoreError(f"发布目录 {target.name} 已存在但内容版本不同")
        return {**manifest, "reused": True}
    manifest = manifest_for(workspace, files, version, message, validation)
    tmp = store.releases_dir / f".tmp-{short(version)}-{os.getpid()}"
    if tmp.exists():
        shutil.rmtree(tmp)
    for name, raw in files.items():
        jsonio.atomic_write(tmp / name, raw)
    jsonio.write_json(tmp / MANIFEST_FILE, manifest)
    os.replace(tmp, target)
    return {**manifest, "reused": False}


def releases(store: CorridorStore) -> list[dict]:
    if not store.releases_dir.is_dir():
        return []
    out = []
    for p in store.releases_dir.iterdir():
        if p.is_dir() and not p.name.startswith(".") and (p / MANIFEST_FILE).is_file():
            m = jsonio.read_json(p / MANIFEST_FILE)
            out.append({k: m.get(k) for k in ("content_version", "workspace_revision", "created_at", "message",
                                               "active_profile", "validation_summary", "source_version")} | {"id": p.name})
    return sorted(out, key=lambda m: m.get("created_at") or "", reverse=True)


def release_dir(store: CorridorStore, version: str) -> Path:
    name = short(version or "")
    if len(name) != 12 or not all(c in "0123456789abcdef" for c in name):
        raise StoreError("版本号无效")
    path = store.releases_dir / name
    if not (path / MANIFEST_FILE).is_file():
        raise StoreError(f"没有发布包 {version}")
    return path


def verify(path: Path) -> dict:
    """Every file matches the manifest and the version recomputes; returns the manifest."""
    manifest = jsonio.read_json(path / MANIFEST_FILE)
    files = {}
    for item in manifest["files"]:
        target = path / item["name"]
        if not target.is_file():
            raise StoreError(f"发布包缺文件 {item['name']}")
        raw = target.read_bytes()
        if jsonio.sha256(raw) != item["sha256"]:
            raise StoreError(f"发布包文件 {item['name']} 摘要不符（被改动过）")
        files[item["name"]] = raw
    if content_version(files) != manifest["content_version"]:
        raise StoreError("发布包内容版本不符")
    return manifest


def read_files(path: Path) -> dict[str, bytes]:
    manifest = verify(path)
    return {item["name"]: (path / item["name"]).read_bytes() for item in manifest["files"]}


def export_zip(path: Path) -> bytes:
    verify(path)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for item in sorted(p for p in path.rglob("*") if p.is_file()):
            archive.write(item, item.relative_to(path).as_posix())
    return buffer.getvalue()


def workspace_from_release(path: Path) -> dict[str, object]:
    """Parsed runtime data of a release (for diffs against the trial's active content)."""
    files = read_files(path)
    return {spec.key: jsonio.parse(files[spec.release]) for spec in RUNTIME_FILES if spec.release in files}
