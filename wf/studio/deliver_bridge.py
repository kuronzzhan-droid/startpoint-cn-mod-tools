"""Compile a studio draft and run the existing, entirely local M1/M2 delivery."""
from __future__ import annotations

import json
import re
from pathlib import Path

from wf.deliver.baseline import resolve_baseline
from wf.deliver.build import build_delivery
from wf.deliver.changeset import member_name, sha256, validate_document, write_json
from wf.deliver.client_compatibility import compatibility_status, unknown_client_check
from wf.paths import path
from wf.view.safety import local_output

from .drafts import DraftError, DraftStore, verify
from .source import StudioSource

# 「生成」 stages reported to progress callbacks (label shown in the editor).
STAGES = (("media", "编译草稿（媒体与词条）"), ("deliver", "wf deliver（分包与清单）"),
          ("compat", "兼容检查（客户端能力）"), ("check", "wf check（交付检查）"))


class BuildCancelled(DraftError):
    """The user cancelled a background build between two stages."""


def _step(progress, cancel, name):
    if cancel is not None and cancel.is_set():
        raise BuildCancelled("已取消生成")
    if progress is not None:
        progress(name)


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
    if changeset.get("subjectKind") == "weapon":
        from .weapon_store import WeaponDraftStore, identity
        if not isinstance(store, WeaponDraftStore):
            raise DraftError("武器交付必须使用独立 WeaponDraftStore 命名空间")
        identity(changeset, cid, source.version)
        return changeset
    if changeset.get("subjectKind") == "boss":
        from .boss import _identity, BossDraftStore
        if not isinstance(store, BossDraftStore):
            raise DraftError("副本交付必须使用独立 BossDraftStore 命名空间")
        _identity(changeset, cid, source.version)
        return changeset
    if any(change["kind"] in {"boss", "weapon"} for change in changeset["changes"]):
        raise DraftError("副本或武器草稿必须使用独立命名空间")
    from .character_clone import clone_change, identity
    if clone_change(changeset):
        identity(source, changeset)
        return changeset
    rows = source.table("character").get(cid)
    if not rows or not rows[0] or rows[0][0] != changeset["code"]:
        raise DraftError("草稿代码名与来源视图角色不一致")
    return changeset


def compile_draft(source, store, changeset, *, server_dir=None, client_profile=None, provides=None,
                  apks=None, bundle_cache_dir=None):
    """Pure compilation: return stored client bytes and asserted server mirrors."""
    if changeset.get("subjectKind") == "weapon":
        from .weapon_editor import compile_weapon
        weapon = compile_weapon(source, store, changeset, server_dir=server_dir,
                                client_profile=client_profile, provides=provides)
        return ({("common", logical): raw for logical, raw in weapon["client"].items()},
                weapon["servers"], weapon["server_before"], weapon["changes"], weapon["checks"])
    if changeset.get("subjectKind") == "boss":
        from .boss import compile_boss
        evidence = {key: value for key, value in (("client_profile", client_profile), ("provides", provides))
                    if value is not None}
        boss = compile_boss(source, store, changeset, server_dir=server_dir, **evidence)
        return ({("common", logical): raw for logical, raw in boss["client"].items()},
                boss["servers"], boss["server_before"], boss["changes"], boss["checks"])
    from .character_clone import clone_change, compile_clone
    if clone_change(changeset):
        compiled = compile_clone(source, store, changeset, server_dir=server_dir,
                                 client_profile=client_profile, apks=apks, cache_dir=bundle_cache_dir)
        return compiled
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
    if any(c["kind"] == "pf_action_clone" for c in changeset["changes"]):
        from .pf_compile import extend_compiled
        members, servers, server_before, changes, checks = extend_compiled(
            (members, servers, server_before, changes, checks), source, store, changeset,
            client_profile=client_profile, apks=apks, cache_dir=bundle_cache_dir)
    if any(c["kind"] == "summon_clone" for c in changeset["changes"]):
        from .summon import compile_summons
        summons = compile_summons(source, store, changeset, members, server_dir=server_dir,
                                  client_profile=client_profile, apks=apks, cache_dir=bundle_cache_dir)
        members.update({("common", logical): raw for logical, raw in summons["client"].items()})
        changes.extend(summons["changes"])
        checks.extend(summons["checks"])
    if any(change["kind"] == "skill_template" for change in changeset["changes"]):
        from .character_clone import overlay_source
        from .skill_template_compile import compile_skill_template
        skill_members, skill_changes, skill_checks = compile_skill_template(
            overlay_source(source, members) if members else source, store, changeset,
            official_source=source, server_dir=server_dir)
        members.update(skill_members)
        changes.extend(skill_changes)
        checks.extend(skill_checks)
    if any(change["kind"] == "skill_template" for change in changeset["changes"]):
        from .skill_template_text import server_mirrors
        server_mirrors(members, changeset["characterId"], server_dir, servers, server_before)
    if not members:
        raise DraftError("草稿没有生成客户端成员")
    from wf.text.draft import check_compiled_text
    checks.extend(check_compiled_text(source, members))
    if any(c.get("level") == "error" or c.get("blocking") for c in checks):
        raise DraftError("草稿规则检查存在问题：" + json.dumps(checks, ensure_ascii=False))
    return members, servers, server_before, changes, checks


def _stage(out, changeset, source, compiled, to_version):
    members, servers, server_before, changes, checks = compiled
    identity = changeset["characterId"]
    if changeset.get("subjectKind") == "weapon":
        identity = "weapon-" + identity
    if changeset.get("subjectKind") == "boss":
        from wf.boss.identity import safe_id
        identity = "boss-" + safe_id(identity).replace("_", "-")
    doc = {"schema": "wf-change-set/1", "id": f"studio-{identity}-{to_version}",
           "name": f"编辑台草稿 {changeset['characterId']}", "slug": f"studio-{identity}",
           "from_version": source.version, "to_version": to_version,
           "created_at": changeset["updatedAt"][:10], "local_test_only": True,
           "members": [], "server_changes": [], "changes": changes}
    staged = {}
    for (root, logical), raw in sorted(members.items()):
        try:
            before = source.view.read_member(member_name(root, logical))[0]
        except FileNotFoundError:
            before = None
        if raw == before:
            continue
        digest = sha256(raw)
        rel = f"blobs/{digest}"
        staged[rel] = raw
        doc["members"].append({"root": root, "logical_path": logical, "source": rel,
                               "sha256": digest, "before_sha256": sha256(before) if before is not None else None})
    for target, raw in sorted(servers.items()):
        digest = sha256(raw)
        if digest == server_before[target]:
            continue
        rel = f"blobs/{digest}"
        staged[rel] = raw
        doc["server_changes"].append({"target": target, "source": rel, "sha256": digest,
                                     "before_sha256": server_before[target]})
    if not doc["members"]:
        raise DraftError("草稿没有与基线不同的客户端成员")
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


def _checks(delivery, provides, allow_unknown_client=False, progress=None, cancel=None):
    from wf.check import check_file
    _step(progress, cancel, "compat")
    if provides is None:
        compat = [unknown_client_check(allow_unknown_client)]
    else:
        from wf.caps.compat import check_compat
        evidence = Path(provides).read_bytes()
        write_json(delivery / "provides.json", json.loads(evidence))
        compat = check_compat(json.loads((delivery / "requires.json").read_text("utf-8")),
                              json.loads(evidence), delivery_dir=delivery)
    write_json(delivery / "compat.json", {"schema": "wf-check-results/1", "results": compat})
    manifest = json.loads((delivery / "delivery-manifest.json").read_text("utf-8"))
    selected = manifest.get("client_compatibility", {}).get("client_profile")
    manifest["client_compatibility"] = {"status": compatibility_status(provides, compat),
        "allow_unknown_client": allow_unknown_client, "report": "compat.json"}
    if selected is not None:
        manifest["client_compatibility"]["client_profile"] = selected
    validate_document(manifest, "delivery-manifest.schema.json")
    write_json(delivery / "delivery-manifest.json", manifest)
    _step(progress, cancel, "check")
    results = check_file(delivery / "delivery-manifest.json")
    write_json(delivery / "check.json", {"schema": "wf-check-results/1", "results": results})
    return results, compat


def build_draft(cid: str, *, from_version: str, to_version: str, out: Path,
                store: DraftStore | None = None, provides: Path | None = None,
                allow_unknown_client: bool = False, client_profile=None,
                apk=None, bundle_cache_dir=None, progress=None, cancel=None, **options) -> dict:
    """Everything generated lives under out/{inputs,delivery}; inputs stay read-only.

    ``progress(stage)`` is called when a stage of :data:`STAGES` starts; ``cancel`` (an Event)
    is checked between stages and raises :class:`BuildCancelled`.
    """
    store = store or DraftStore()
    from .scratch import build_refusal, is_scratch
    if is_scratch(cid) or "scratch" in (store.load(cid) or {}):
        raise DraftError(build_refusal(store, cid))
    from wf.caps.profiles import resolve_client
    provides, selected_profile = resolve_client(provides, client_profile,
                                               allow_unknown_client=allow_unknown_client)
    from .delivery_safety import (checksum_delivery, inspect_output, resolve_apks,
                                  staged_members, write_reports)
    apks = resolve_apks(selected_profile, apk)
    out = local_output(out)
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise DraftError(f"交付输出目录必须为空：{out}")
    draft_dir = store.directory(cid).resolve()
    if out.is_relative_to(draft_dir) or draft_dir.is_relative_to(out):
        raise DraftError("交付目录与草稿目录不能互相包含")
    _step(progress, cancel, "media")
    baseline = open_baseline(from_version, to_version, **options)
    source = StudioSource(baseline)
    changeset = _draft(store, cid, source)
    pf_options = ({"apks": apks, "bundle_cache_dir": bundle_cache_dir}
                  if any(c["kind"] == "pf_action_clone" for c in changeset["changes"]) else {})
    compiled = compile_draft(source, store, changeset, server_dir=options.get("server_dir"),
                             client_profile=selected_profile if provides is not None else False,
                             provides=provides, **pf_options)
    baseline.verify()
    filename = _stage(out, changeset, source, compiled, to_version)
    from .overlay_export import source_view, availability
    _step(progress, cancel, "deliver")
    options["baseline_view"] = baseline
    members = staged_members(filename)
    reports = safety_checks = None
    build_error = None
    try:
        manifest = build_delivery(filename, out / "delivery", provides=provides,
                                  client_profile=selected_profile,
                                  allow_unknown_client=allow_unknown_client, **options)
    except ValueError as error:
        # Persist the original gate failure even if secondary inspection fails.
        build_error = {"type": type(error).__name__, "message": str(error), "stage": "deliver"}
        failure = {"ok": False, **availability(out), "characterId": cid, "from": from_version, "to": to_version,
                   "buildError": build_error, "delivery": str(out / "delivery")}
        write_json(out / "build-report.json", failure)
        try:
            reports, safety_checks = inspect_output(members, baseline, changeset, apks=apks,
                                                    cache_dir=bundle_cache_dir)
        except (ValueError, OSError) as inspection_error:
            failure["inspectionError"] = {"type": type(inspection_error).__name__,
                                          "message": str(inspection_error)}
            write_json(out / "build-report.json", failure)
            return failure
        manifest = None
    if manifest is not None:
        write_json(out / "delivery/source-view.json", source_view(baseline))
    if reports is None:
        reports, safety_checks = inspect_output(members, baseline, changeset, apks=apks,
                                                cache_dir=bundle_cache_dir)
    baseline.verify()
    write_reports(out / "delivery", reports, compiled[4], manifest)
    write_json(out / "delivery/draft-checks.json", compiled[4])
    write_json(out / "delivery/safety-checks.json", safety_checks)
    if manifest is not None:
        if selected_profile is not None:
            manifest["client_compatibility"]["client_profile"] = selected_profile
        requirements_path = out / "delivery/requires.json"
        requirements = json.loads(requirements_path.read_text("utf-8"))
        requirements["requires"]["clientCapabilities"] = sorted(set(
            requirements["requires"]["clientCapabilities"]) | set(reports["clientExtensions"]["requires"]))
        write_json(requirements_path, requirements)
        manifest["draft_checks"] = "draft-checks.json"
        manifest["safety_checks"] = "safety-checks.json"
        write_json(out / "delivery/delivery-manifest.json", manifest)
        checks, compat = _checks(out / "delivery", provides, allow_unknown_client, progress, cancel)
        compat_status = compatibility_status(provides, compat)
        prepush = manifest["prepush"]
    else:
        from wf.rules.catalog import result as check_result
        checks = [*safety_checks, check_result("studio.build-delivery", "问题",
                  build_error["message"], blocking=True, level="error")]
        compat, compat_status = [], "未执行"
        prepush = {"status": "未执行", "exit_code": None, "limitations": [build_error["message"]]}
        write_json(out / "delivery/check.json", {"schema": "wf-check-results/1", "results": checks})
    failed = (manifest is None or bool(prepush["exit_code"]) or any(r.get("blocking") for r in checks + compat)
              or any(r.get("blocking") for r in safety_checks)
              or any(r.get("blocking") or r.get("level") == "error" for r in compiled[4])
              or (provides is None and not allow_unknown_client))
    result = {"ok": not failed, **availability(out), "characterId": cid, "from": from_version, "to": to_version,
              "draftRevision": changeset["revision"], "changeset": str(filename),
              "delivery": str(out / "delivery"), "prepush": prepush,
              "checks": checks, "compat": compat_status, "compatChecks": compat,
              "draftChecks": compiled[4], "safetyChecks": safety_checks, **reports,
              "clientProfile": selected_profile, "buildError": build_error,
              "allowUnknownClient": allow_unknown_client, "deviceValidation": "未执行"}
    from .rehearsal import auto_rehearse
    result["rehearsal"] = None
    if not failed:
        try:
            result["rehearsal"] = auto_rehearse(out)
        except (ValueError, OSError) as exc:
            result["rehearsal"] = {"ok": False, "status": "blocked", "error": str(exc)}
    write_json(out / "build-report.json", result)
    # The extra check/compat artifacts are included in the final delivery checksum list.
    checksum_delivery(out / "delivery")
    return result
