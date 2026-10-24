# -*- coding: utf-8 -*-
"""可重复运行的 manifest 整合器（替代校园 bootstrap-only 构建器）。

每次：磁盘重扫四根 sha/size；tables = ``evidence/table_claims.json``；skills /
unique_condition / required_capabilities 与旧 manifest 合并；snapshot 保留旧键并用 evidence
下 kit/art/pixel/voice/assets/tables 报告摘要刷新；qa 复位（release_ready=false、封存哈希清空），
随后用 workspace status 回填必需资产计数，并做 roots↔tables 对账。

门禁：``validate_manifest`` 非空、或对账任一列表非空（含「认领的键不在候选表里」）时，
写完 manifest 与 ``evidence/manifest_report.json`` 后抛 :class:`S7Error`（CLI 退出码 2）。
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

import wf_character_pack as pack_mod
import wf_character_workspace as ws
import wf_seasonal7_common as C

SNAPSHOT_KEY = "seasonal7"
REPORT_SOURCES = {
    "tables": "tables-report.json",
    "assets": "assets-report.json",
    "kit": "kit-report.json",
    "art": "art/applied.json",
    "pixel": "pixel-report.json",
    "voice": "voice-report.json",
}
SUMMARY_FIELDS = {
    "tables": ("claims", "element_flip", "server_mana_crosscheck"),
    "assets": ("assets", "required", "inherited_voices", "provenance"),
    "kit": ("summary", "skills", "panel", "notes", "status"),
    "art": ("applied", "gates", "geometry", "headshots"),
    "pixel": ("summary", "status"),
    "voice": ("summary", "status", "mode"),
}


def scan_roots(pack: C.S7Pack) -> dict[str, list[dict]]:
    roots: dict[str, list[dict]] = {name: [] for name in C.ROOT_NAMES}
    for name in C.ROOT_NAMES:
        base = pack.package / "roots" / name
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*"), key=lambda p: p.relative_to(base).as_posix()):
            if not path.is_file():
                continue
            data = path.read_bytes()
            roots[name].append({"logical_path": path.relative_to(base).as_posix(),
                                "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)})
    return roots


def _summary(kind: str, report: Any) -> Any:
    if not isinstance(report, dict):
        return None
    fields = SUMMARY_FIELDS.get(kind, ())
    picked = {k: report[k] for k in fields if k in report}
    if kind == "tables" and isinstance(picked.get("element_flip"), dict):
        flip = picked["element_flip"]
        picked["element_flip"] = {"from": flip.get("from"), "to": flip.get("to"),
                                  "cells": len(flip.get("cells", []))}
    if kind == "art" and "geometry" in picked:
        picked["geometry"] = [{k: g.get(k) for k in ("x", "y", "width", "height")}
                              for g in picked["geometry"]]
    return picked or {"present": True}


def claimed_keys_missing(pack: C.S7Pack, claim: dict) -> list[str]:
    """认领了但候选表里没有的键（flow PackTransaction 会判非法）。"""
    import wf_mod_tool as core
    root, logical, codec = claim["root"], claim["logical_path"], claim["codec_id"]
    raw = pack.pkg_path(root, logical).read_bytes()
    label = f"{root}:{logical}"
    missing: list[str] = []
    if codec == "json_object":
        present = set(json.loads(raw))
        missing += [f"{label}#{k}" for k in claim["outer_keys"] if k not in present]
    elif codec in ("action_nested", "switched_nested"):
        nested = core.load_nested_table_bytes(raw, logical)
        missing += [f"{label}#{k}" for k in claim["outer_keys"] if k not in nested.rows]
        for item in claim.get("inner_keys", []):
            inner = nested.rows.get(item["outer_key"])
            present = set(inner.keys) if inner is not None else set()
            missing += [f"{label}#{item['outer_key']}/{k}" for k in item["keys"] if k not in present]
    else:
        present = set(core.read_orderedmap_raw_rows_from_bytes(raw, logical).keys)
        missing += [f"{label}#{k}" for k in claim["outer_keys"] if k not in present]
    return missing


def reconcile(pack: C.S7Pack, claims: list[dict]) -> dict[str, list[str]]:
    table_roots = {(c["root"], c["logical_path"]) for c in claims}
    recon = {"tables_not_in_roots": [], "root_tables_not_claimed": [], "claim_codec_mismatch": [],
             "claimed_keys_missing": []}
    for claim in claims:
        if not pack.pkg_path(claim["root"], claim["logical_path"]).is_file():
            recon["tables_not_in_roots"].append(f"{claim['root']}:{claim['logical_path']}")
        else:
            recon["claimed_keys_missing"].extend(claimed_keys_missing(pack, claim))
        is_server = claim["root"] == "server"
        if is_server != (claim["codec_id"] == "json_object"):
            recon["claim_codec_mismatch"].append(f"{claim['root']}:{claim['logical_path']}")
    for name in C.ROOT_NAMES:
        base = pack.package / "roots" / name
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(base).as_posix()
            is_table = rel.endswith(".orderedmap") or (name == "server" and rel.endswith(".json"))
            if is_table and (name, rel) not in table_roots:
                recon["root_tables_not_claimed"].append(f"{name}:{rel}")
    return recon


def build(pack: C.S7Pack) -> dict[str, Any]:
    spec = pack.spec
    pack.check_identity()
    manifest_path = pack.package / "manifest.json"
    prior = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
    claims = C.merge_claims([], pack.load_claims())          # 规范化（幂等）
    roots = scan_roots(pack)

    # ---- skills：旧声明 ∪ 盘上 DSL ∪ kit 报告
    kit_report = pack.read_evidence(REPORT_SOURCES["kit"], None)
    skills = dict(prior.get("skills") or {})
    common_paths = {e["logical_path"] for e in roots["common"]}
    programs = [p for p in skills.get("programs", []) if p in common_paths]
    for program in pack.pkg_dsl_programs():
        if program not in programs:
            programs.append(program)
    if isinstance(kit_report, dict) and isinstance(kit_report.get("skills"), dict):
        for key, value in kit_report["skills"].items():
            if key == "programs":
                programs.extend(p for p in value if p not in programs)
            else:
                skills[key] = value
    skills["programs"] = sorted(programs)

    unique_condition = dict(prior.get("unique_condition") or {})
    if isinstance(kit_report, dict) and isinstance(kit_report.get("unique_condition"), dict):
        unique_condition.update(kit_report["unique_condition"])

    capabilities = list(prior.get("required_capabilities") or [])
    extra_caps = list(spec.required_capabilities)
    if isinstance(kit_report, dict):
        extra_caps += list(kit_report.get("required_capabilities") or [])
    for cap in extra_caps:
        if cap not in capabilities:
            capabilities.append(cap)

    snapshot = dict(prior.get("snapshot") or {})
    reports = {}
    for kind, name in REPORT_SOURCES.items():
        summary = _summary(kind, pack.read_evidence(name, None))
        if summary is not None:
            reports[kind] = summary
    snapshot[SNAPSHOT_KEY] = {
        "spec": {"key": spec.key, "template_id": spec.template_id, "template_code": spec.template_code,
                 "element": spec.element, "element_token": spec.element_token,
                 "template_element": spec.template_element, "pf_type": spec.pf_type,
                 "stance": spec.stance, "identity": spec.identity, "theme": spec.theme},
        "candidate_only": True,
        "runtime_verified": False,
        "reports": reports,
    }

    manifest = {
        "schema_version": 1,
        "package_id": spec.pkg_id,
        "character_id": spec.cid,
        "code_name": spec.code,
        "package_version": spec.package_version,
        "requires_client_base": spec.requires_client_base,
        "required_capabilities": capabilities,
        "roots": roots,
        "tables": claims,
        "skills": skills,
        "unique_condition": unique_condition,
        "qa": {"delivery_mode": "production", "missing_required": [], "release_ready": False,
               "required_assets_present": 0, "required_assets_total": 37,
               "workspace_input_sha256": ""},
        "snapshot": snapshot,
    }
    # requirement_report 只取决于 roots 文件，不依赖 manifest 内容 ⇒ 先算计数再一次写盘。
    pre = ws.workspace_status(ws.load_workspace(pack.workspace), persist=False)
    manifest["qa"]["required_assets_present"] = pre.requirement_report["required_present"]
    manifest["qa"]["required_assets_total"] = pre.requirement_report["required_total"]
    manifest["qa"]["missing_required"] = list(pre.requirement_report["missing_required"])
    final_bytes = pack_mod.canonical_manifest_bytes(manifest)
    if not manifest_path.is_file() or manifest_path.read_bytes() != final_bytes:
        manifest_path.write_bytes(final_bytes)

    errors = pack_mod.validate_manifest(manifest, pack.package, require_referenced_assets=True)
    recon = reconcile(pack, claims)
    status = ws.workspace_status(ws.load_workspace(pack.workspace))
    report = {
        "character": spec.key,
        "files": {k: len(v) for k, v in roots.items()},
        "tables": len(claims),
        "skills_programs": len(skills["programs"]),
        "validate_manifest": errors,
        "reconcile": recon,
        "required": f"{status.requirement_report['required_present']}/{status.requirement_report['required_total']}",
        "missing_required": list(status.requirement_report["missing_required"]),
        "manifest_errors": list(status.manifest_errors),
        "three_layer_claim_status": status.three_layer_claim_status,
        "release_ready": status.release_ready,
        "input_digest": status.input_digest,
        "manifest_sha256": hashlib.sha256(final_bytes).hexdigest(),
    }
    pack.write_evidence("manifest_report.json", report)
    problems = {k: v for k, v in recon.items() if v}
    if errors or problems:
        detail = {"validate_manifest": errors[:10]} if errors else {}
        detail.update({k: v[:10] for k, v in problems.items()})
        raise C.S7Error("manifest gate failed: " + json.dumps(detail, ensure_ascii=False))
    return report
