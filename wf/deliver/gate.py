"""Run the existing prepush checks against a checkout-local candidate snapshot."""
from __future__ import annotations

import contextlib
import io
import json
import shutil
from pathlib import Path

from .changeset import write_json
from .prepush_base import archive_key, vkey
from .chain_contract import chain_errors
from .assert_box import verify


def run_prepush(out, doc, records, server_changes, *, server_dir=None, base_store=None,
                baseline_active=None, baseline_zips=(), pathlist=None):
    snapshot = out / "validation"
    active = snapshot / "assets/asset-patch/active"
    active.mkdir(parents=True, exist_ok=True)
    before = []
    if baseline_active is not None:
        if not Path(baseline_active).is_dir():
            raise FileNotFoundError(f"baseline active not found: {baseline_active}")
        before.extend(p for p in Path(baseline_active).glob("*.zip")
                      if archive_key(p.name) and archive_key(p.name)[1] <= vkey(doc["from_version"]))
    before.extend(Path(p) for p in baseline_zips)
    unique = {}
    for source in before:
        key = archive_key(source.name)
        if key is None or key[1] > vkey(doc["from_version"]):
            raise ValueError(f"invalid baseline archive: {source.name}")
        if source.name in unique and source.resolve() != unique[source.name].resolve():
            if source.read_bytes() != unique[source.name].read_bytes():
                raise ValueError(f"conflicting baseline archive: {source.name}")
        unique[source.name] = source
    entries = []
    for name, source in sorted(unique.items(), key=lambda pair: archive_key(pair[0])):
        shutil.copyfile(source, active / name)
        frm, to, _ = archive_key(name)
        entries.append({"id": name, "type": "patch", "enabled": True, "archive": name,
                        "depends_on": ".".join(map(str, frm)), "version": ".".join(map(str, to))})
    legacy = json.loads((out / f"manifest-entry-{doc['to_version']}.json").read_text("utf-8"))
    for rec in records:
        shutil.copyfile(out / rec["name"], active / rec["name"])
    entries.append(legacy)
    manifest = snapshot / "assets/asset-patch/manifest.json"
    write_json(manifest, {"cdn_version": doc["to_version"], "patches": entries})
    if server_dir is not None:
        for rel in ("assets/item_ids.json", "assets/cdndata/character_text.json",
                    "assets/cdndata/character_text_rank_p5b.json"):
            source = Path(server_dir) / rel
            if source.is_file():
                target = snapshot / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
    for rel, raw in server_changes.items():
        target = snapshot / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    argv = ["--server-dir", str(snapshot), "--active", str(active), "--manifest", str(manifest),
            "--since", doc["from_version"], "--json", str(out / "prepush.json")]
    if base_store is not None:
        argv += ["--base-store", str(base_store)]
    if pathlist is not None:
        argv += ["--pathlist", str(pathlist)]
    from . import prepush
    output = io.StringIO()
    try:
        with contextlib.redirect_stdout(output):
            code = prepush.main(argv)
    except Exception:
        (out / "prepush.log").write_text(output.getvalue(), "utf-8")
        raise
    (out / "prepush.log").write_text(output.getvalue(), "utf-8")
    report_file = out / "prepush.json"
    if not report_file.is_file():
        write_json(report_file, {"findings": [], "notes": ["prepush did not create findings"], "since": doc["from_version"]})
    findings = json.loads(report_file.read_text("utf-8"))
    local_errors = chain_errors([*unique, *(r["name"] for r in records)], doc["to_version"])
    assertions = json.loads((out / "assert-box.json").read_text("utf-8"))
    if base_store is not None or unique:
        client_assertions = {**assertions, "files": [x for x in assertions["files"] if x["kind"] == "client"]}
        local_errors += verify(client_assertions, phase="pre", active=active, store=base_store,
                               manifest={"cdn_version": doc["from_version"], "patches": entries[:-1]})
        local_errors += verify(client_assertions, phase="post", active=active, store=base_store,
                               manifest={"cdn_version": doc["to_version"], "patches": entries})
    server_assertions = {**assertions, "files": [x for x in assertions["files"] if x["kind"] == "server"]}
    if server_assertions["files"]:
        if server_dir is not None:
            local_errors += verify(server_assertions, phase="pre", server_dir=server_dir,
                                   manifest={"cdn_version": doc["from_version"]})
        local_errors += verify(server_assertions, phase="post", server_dir=snapshot,
                               manifest={"cdn_version": doc["to_version"]})
    for index, error in enumerate(local_errors):
        findings.setdefault("findings", []).append({"level": "ERROR", "check": "chain",
            "fid": f"delivery.local:{index}", "msg": error, "detail": []})
    if local_errors:
        code = 1
    findings["local_contract"] = {"chain_checked": True, "pre_and_post_hashes_checked": bool(base_store or unique),
                                  "server_pre_hashes_checked": bool(server_dir and server_assertions["files"]),
                                  "server_post_hashes_checked": bool(server_assertions["files"]),
                                  "errors": local_errors}
    write_json(report_file, findings)
    limitations = [f["msg"] for f in findings.get("findings", [])
                  if any(token in f["fid"] for token in ("skipped", "missing", "failed", "view.broken"))]
    if not base_store:
        limitations.append("未提供基础 store，视图仅覆盖补丁成员")
    if server_assertions["files"] and server_dir is None:
        limitations.append("未提供服务端 JSON 基线，服务端前置摘要断言未执行")
    return {"status": "问题" if code else "待验证" if limitations else "满足", "exit_code": code,
            "since": doc["from_version"], "report": "prepush.json", "log": "prepush.log",
            "limitations": limitations}
