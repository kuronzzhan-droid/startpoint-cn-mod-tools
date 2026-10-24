"""Run prepush using manifest-selected, read-only baseline archives."""
from __future__ import annotations

import contextlib
import io
import json
import shutil
from pathlib import Path

from .assert_box import verify
from .baseline import verify_client
from .chain_contract import chain_errors
from .changeset import write_json


def run_prepush(out, doc, records, server_changes, *, baseline=None, members=None,
                server_dir=None, base_store=None, no_baseline_i_know=False, pathlist=None, **_options):
    snapshot = out / "validation"
    active = snapshot / "assets/asset-patch/active"
    active.mkdir(parents=True, exist_ok=True)
    before = list(baseline.zips) if baseline is not None else []
    entries = [{"id": edge["version"], "type": "patch", "enabled": True,
                "chain": edge["names"], "depends_on": edge["depends_on"], "version": edge["version"]}
               for edge in baseline.edges] if baseline is not None else []
    legacy = json.loads((out / f"manifest-entry-{doc['to_version']}.json").read_text("utf-8"))
    candidates = [out / rec["name"] for rec in records]
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
    store = baseline.store if baseline is not None else base_store
    argv = ["--server-dir", str(snapshot), "--active", str(active), "--manifest", str(manifest),
            "--since", doc["from_version"], "--json", str(out / "prepush.json")]
    if store is not None:
        argv += ["--base-store", str(store)]
    if pathlist is not None:
        argv += ["--pathlist", str(pathlist)]
    from . import prepush
    output = io.StringIO()
    try:
        with contextlib.redirect_stdout(output):
            code = prepush.main(argv, archive_paths=[*before, *candidates])
    finally:
        (out / "prepush.log").write_text(output.getvalue(), "utf-8")
    report_file = out / "prepush.json"
    if not report_file.is_file():
        write_json(report_file, {"findings": [], "notes": ["prepush did not create findings"], "since": doc["from_version"]})
    findings = json.loads(report_file.read_text("utf-8"))
    from .prepush_base import Report, View
    from .prepush_companion import check_server_rewards
    from .prepush_rewards import SERVER_REWARD_PATHS
    server_before = {}
    if server_dir is not None:
        for rel in SERVER_REWARD_PATHS:
            source = Path(server_dir) / rel
            server_before[rel] = source.read_bytes() if source.is_file() else None
    rewards = Report(set())
    reward_view = View([*before, *candidates], store)
    try:
        findings["companion_reward_keys"] = check_server_rewards(
            reward_view, rewards, server_changes, server_before)
    finally:
        for archive in reward_view._zf.values():
            archive.close()
    findings.setdefault("findings", []).extend(f.__dict__ for f in rewards.items)
    if findings["companion_reward_keys"]["server_targets"]:
        with (out / "prepush.log").open("a", encoding="utf-8") as log:
            log.write(f"\n[服务端奖励键] ERROR {rewards.count('ERROR')} WARN {rewards.count('WARN')}\n")
            for finding in rewards.items:
                log.write(f"  {finding.level} {finding.msg}\n")
    if rewards.count("ERROR"):
        code = 1
    local_errors = chain_errors([p.name for p in [*before, *candidates]], doc["to_version"])
    local_errors += verify_client(doc, members or {}, baseline, base_store=base_store, archives=candidates)
    assertions = json.loads((out / "assert-box.json").read_text("utf-8"))
    server_assertions = {**assertions, "files": [x for x in assertions["files"] if x["kind"] == "server"]}
    if server_assertions["files"]:
        local_errors += verify(server_assertions, phase="pre", server_dir=server_dir,
                               manifest={"cdn_version": doc["from_version"]})
        local_errors += verify(server_assertions, phase="post", server_dir=snapshot,
                               manifest={"cdn_version": doc["to_version"]})
    for index, error in enumerate(local_errors):
        findings.setdefault("findings", []).append({"level": "ERROR", "check": "chain",
            "fid": f"delivery.local:{index}", "msg": error, "detail": []})
    if local_errors:
        code = 1
    waived = baseline is None and no_baseline_i_know
    findings["local_contract"] = {"chain_checked": True,
        "pre_and_post_hashes_checked": baseline is not None,
        "server_pre_hashes_checked": bool(server_dir and server_assertions["files"]),
        "server_post_hashes_checked": bool(server_assertions["files"]),
        "no_baseline_i_know": waived, "errors": local_errors}
    write_json(report_file, findings)
    limitations = [f["msg"] for f in findings.get("findings", [])
                  if any(token in f["fid"] for token in ("skipped", "missing", "failed", "view.broken"))]
    if waived:
        limitations.append("显式 --no-baseline-i-know：未核验客户端基线版本；缺失的前置摘要检查未执行")
    return {"status": "问题" if code else "待验证" if limitations else "满足", "exit_code": code,
            "since": doc["from_version"], "report": "prepush.json", "log": "prepush.log",
            "limitations": limitations}
