# -*- coding: utf-8 -*-
"""仅初始化原生模板候选的 manifest；不得用于已装配立绘/技能的候选重建。"""
from __future__ import annotations

import hashlib
import json

import wf_campus_nephtim_common as C
import wf_character_pack as pack
import wf_character_workspace as ws

ROOT_NAMES = ("common", "medium", "android", "server")
# 生产基线由当前818前的稳定链尾817开始，正式发布前root重查并rebase。
REQUIRES_CLIENT_BASE = "1.4.817"
PACKAGE_VERSION = "0.1.0"


def scan_roots():
    roots = {name: [] for name in ROOT_NAMES}
    for name in ROOT_NAMES:
        base = C.PKG / "roots" / name
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            data = path.read_bytes()
            roots[name].append({
                "logical_path": path.relative_to(base).as_posix(),
                "sha256": hashlib.sha256(data).hexdigest(),
                "size": len(data),
            })
    return roots


def build():
    """Bootstrap 模板资产声明；存在后续整合信息时，在任何写入前拒绝。"""
    manifest_path = C.PKG / "manifest.json"
    prior = json.loads(manifest_path.read_text("utf-8")) if manifest_path.exists() else {}
    enriched = [field for field in ("snapshot", "skills", "unique_condition") if prior.get(field)]
    if enriched:
        raise ValueError(
            "bootstrap-only manifest builder: refusing to overwrite integrated "
            + ", ".join(enriched)
            + "; use the candidate integration flow to preserve completed art and claims")
    claims = json.loads((C.EVIDENCE / "table_claims.json").read_text(encoding="utf-8"))
    claim_keys = {json.dumps(claim, sort_keys=True) for claim in claims}
    if any(json.dumps(claim, sort_keys=True) not in claim_keys for claim in prior.get("tables", [])):
        raise ValueError("bootstrap-only manifest builder: refusing to discard integrated table claims")
    roots = scan_roots()

    manifest = {
        "schema_version": 1,
        "package_id": C.PKG_ID,
        "character_id": C.CID,
        "code_name": C.CODE,
        "package_version": PACKAGE_VERSION,
        "requires_client_base": REQUIRES_CLIENT_BASE,
        "required_capabilities": [],
        "roots": roots,
        "tables": claims,
        "skills": {},
        "unique_condition": {},
        "qa": {
            "delivery_mode": "production",
            "missing_required": [],
            "release_ready": False,
            "required_assets_present": 0,
            "required_assets_total": 37,
            "workspace_input_sha256": "",
        },
        "snapshot": {},
    }
    (C.PKG / "manifest.json").write_bytes(pack.canonical_manifest_bytes(manifest))

    # 必需资产计数按磁盘真实状态回填；统一装配完成前保持未封存。
    st0 = ws.workspace_status(ws.load_workspace(C.WS))
    manifest["qa"]["required_assets_present"] = st0.requirement_report["required_present"]
    manifest["qa"]["required_assets_total"] = st0.requirement_report["required_total"]
    manifest["qa"]["missing_required"] = list(st0.requirement_report["missing_required"])
    (C.PKG / "manifest.json").write_bytes(pack.canonical_manifest_bytes(manifest))

    errors = pack.validate_manifest(manifest, C.PKG, require_referenced_assets=True)

    # ---- roots ↔ tables[] 逐一对账
    table_paths = {c["logical_path"] for c in claims}
    root_of = {c["logical_path"]: c["root"] for c in claims}
    recon = {"tables_not_in_roots": [], "root_tables_not_claimed": []}
    for c in claims:
        entry = C.pkg_path(c["root"], c["logical_path"])
        if not entry.is_file():
            recon["tables_not_in_roots"].append(c["logical_path"])
    for name in ROOT_NAMES:
        base = C.PKG / "roots" / name
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(base).as_posix()
            is_table = rel.endswith(".orderedmap") or (name == "server"
                                                       and rel.endswith(".json"))
            if is_table and (rel not in table_paths or root_of.get(rel) != name):
                recon["root_tables_not_claimed"].append("%s:%s" % (name, rel))

    status = ws.workspace_status(ws.load_workspace(C.WS))
    report = {
        "files": {k: len(v) for k, v in roots.items()},
        "tables": len(claims),
        "validate_manifest": errors or [],
        "reconcile": recon,
        "release_ready": status.release_ready,
        "required": "%s/%s" % (status.requirement_report["required_present"],
                               status.requirement_report["required_total"]),
        "missing_required_count": len(status.requirement_report["missing_required"]),
        "manifest_errors": list(status.manifest_errors),
        "three_layer_claim_status": status.three_layer_claim_status,
        "input_digest": status.input_digest,
    }
    (C.EVIDENCE / "manifest_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=1))
