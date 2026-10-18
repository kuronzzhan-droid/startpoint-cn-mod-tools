"""Compile a studio draft and run the existing, entirely local M1/M2 delivery."""
from __future__ import annotations

import json
import re
from pathlib import Path

from wf.deliver.baseline import resolve_baseline
from wf.deliver.build import build_delivery
from wf.deliver.changeset import member_name, sha256, validate_document, write_json
from wf.paths import path
from wf.view.safety import local_output

from .drafts import DraftError, DraftStore, verify
from .source import StudioSource


def open_baseline(from_version: str, to_version: str, **options):
    """Bind all compilation and prepush reads to the same manifest view."""
    for value in (from_version, to_version):
        if not re.fullmatch(r"\d+\.\d+\.\d+", value):
            raise DraftError(f"版本无效：{value}")
    if tuple(map(int, from_version.split("."))) >= tuple(map(int, to_version.split("."))):
        raise DraftError("交付目标版本必须高于来源版本")
    if not options.get("baseline_view") and not options.get("baseline_manifest"):
        options["baseline_manifest"] = path("kulo", "assets/asset-patch/manifest.json")
    if not options.get("baseline_view"):
        from wf.view import ManifestView
        store = options.get("base_store")
        if store is not None and (Path(store) / "upload").is_dir():
            store = Path(store) / "upload"
        options["baseline_view"] = ManifestView(
            from_version, store=store, manifest=options.get("baseline_manifest"),
            search_dirs=options.get("baseline_zip_dirs"), manifests=options.get("baseline_manifests"),
            base_version=options.get("base_version", "1.4.131"), lock=options.get("view_lock"))
    return resolve_baseline({"from_version": from_version, "to_version": to_version}, **options)


def _draft(store, cid, source):
    changeset = store.load(cid)
    if changeset is None or not changeset.get("changes"):
        raise DraftError("这个角色没有可交付的草稿改动")
    errors = verify(store, cid, changeset)
    if errors:
        raise DraftError("草稿复核失败：" + "；".join(errors[:8]))
    if changeset["characterId"] != cid or changeset["baseView"] != source.version:
        raise DraftError("草稿角色或基线版本与 --from 不一致，请在目标视图重建草稿")
    rows = source.table("character").get(cid)
    if not rows or not rows[0] or rows[0][0] != changeset["code"]:
        raise DraftError("草稿代码名与来源视图角色不一致")
    return changeset


def compile_draft(source, store, changeset, *, server_dir=None):
    """Pure compilation: return stored client bytes and asserted server mirrors."""
    from .deliver_media import compile_media
    media = compile_media(source, store, changeset)
    members = dict(media.members)
    changes = list(media.assertions)
    checks = list(media.checks)
    servers, server_before = {}, {}
    if any(change["kind"] == "ability_edit" for change in changeset["changes"]):
        from .ability import compile_ability_operations
        ability = compile_ability_operations(source, store, changeset, server_dir=server_dir)
        for logical, raw in ability["client"].items():
            key = ("common", logical)
            if key in members:
                raise DraftError(f"重复编译目标：{logical}")
            members[key] = raw
        servers.update(ability["servers"])
        server_before.update(ability["server_before"])
        changes.extend(ability["changes"])
        checks.extend(ability["checks"])
    if not members:
        raise DraftError("草稿没有生成客户端成员")
    if any(c.get("level") == "error" or c.get("blocking") for c in checks):
        raise DraftError("草稿规则检查存在问题：" + json.dumps(checks, ensure_ascii=False))
    return members, servers, server_before, changes, checks


def _stage(out, changeset, source, compiled, to_version):
    members, servers, server_before, changes, checks = compiled
    doc = {"schema": "wf-change-set/1", "id": f"studio-{changeset['characterId']}-{to_version}",
           "name": f"编辑台草稿 {changeset['characterId']}", "slug": f"studio-{changeset['characterId']}",
           "from_version": source.version, "to_version": to_version,
           "created_at": changeset["updatedAt"][:10], "local_test_only": True,
           "members": [], "server_changes": [], "changes": changes}
    staged = {}
    for (root, logical), raw in sorted(members.items()):
        try:
            before = source.view.read_member(member_name(root, logical))[0]
        except FileNotFoundError:
            before = None
        digest = sha256(raw)
        rel = f"blobs/{digest}"
        staged[rel] = raw
        doc["members"].append({"root": root, "logical_path": logical, "source": rel,
                               "sha256": digest, "before_sha256": sha256(before) if before is not None else None})
    for target, raw in sorted(servers.items()):
        digest = sha256(raw)
        rel = f"blobs/{digest}"
        staged[rel] = raw
        doc["server_changes"].append({"target": target, "source": rel, "sha256": digest,
                                     "before_sha256": server_before[target]})
    validate_document(doc, "change-set.schema.json")
    inputs = out / "inputs"
    for rel, raw in staged.items():
        destination = local_output(inputs / rel)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
    write_json(inputs / "changeset.json", doc)
    write_json(inputs / "draft.json", changeset)
    write_json(inputs / "checks.json", checks)
    return inputs / "changeset.json"


def _checks(delivery, provides):
    from wf.check import check_file
    from wf.rules.catalog import result
    results = check_file(delivery / "delivery-manifest.json")
    write_json(delivery / "check.json", {"schema": "wf-check-results/1", "results": results})
    if provides is None:
        compat = [result("capability.unknown", "未执行", "未提供目标客户端 provides.json，未确认兼容")]
    else:
        from wf.caps.compat import check_compat
        evidence = Path(provides).read_bytes()
        write_json(delivery / "provides.json", json.loads(evidence))
        compat = check_compat(json.loads((delivery / "requires.json").read_text("utf-8")),
                              json.loads(evidence), delivery_dir=delivery)
    write_json(delivery / "compat.json", {"schema": "wf-check-results/1", "results": compat})
    return results, compat


def build_draft(cid: str, *, from_version: str, to_version: str, out: Path,
                store: DraftStore | None = None, provides: Path | None = None, **options) -> dict:
    """Everything generated lives under out/{inputs,delivery}; inputs stay read-only."""
    out = local_output(out)
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise DraftError(f"交付输出目录必须为空：{out}")
    store = store or DraftStore()
    draft_dir = store.directory(cid).resolve()
    if out.is_relative_to(draft_dir) or draft_dir.is_relative_to(out):
        raise DraftError("交付目录与草稿目录不能互相包含")
    baseline = open_baseline(from_version, to_version, **options)
    source = StudioSource(baseline)
    changeset = _draft(store, cid, source)
    compiled = compile_draft(source, store, changeset, server_dir=options.get("server_dir"))
    baseline.verify()
    filename = _stage(out, changeset, source, compiled, to_version)
    options["baseline_view"] = baseline
    manifest = build_delivery(filename, out / "delivery", **options)
    checks, compat = _checks(out / "delivery", provides)
    failed = bool(manifest["prepush"]["exit_code"]) or any(r["blocking"] for r in checks + compat)
    result = {"ok": not failed, "characterId": cid, "from": from_version, "to": to_version,
              "draftRevision": changeset["revision"], "changeset": str(filename),
              "delivery": str(out / "delivery"), "prepush": manifest["prepush"],
              "checks": checks, "compat": compat, "deviceValidation": "未执行"}
    write_json(out / "build-report.json", result)
    # The extra check/compat artifacts are included in the final delivery checksum list.
    sums = [f"{sha256(p.read_bytes())}  {p.relative_to(out / 'delivery').as_posix()}"
            for p in sorted((out / "delivery").rglob("*"))
            if p.is_file() and p.name != "SHA256SUMS" and "validation" not in p.relative_to(out / "delivery").parts]
    (out / "delivery/SHA256SUMS").write_text("\n".join(sums) + "\n", "utf-8")
    return result
