"""Studio-only delivery checks over the exact changed staged members."""
from __future__ import annotations

import json
import os
from pathlib import Path

from wf.deliver.changeset import member_name, write_json
from wf.rules.catalog import result


def resolve_apks(client_profile, apk=None):
    """Explicit paths override client_apks; relative paths follow wf_root."""
    from wf.paths import profile_data, root_path
    if apk is None:
        config, _ = profile_data()
        configured = config.get("client_apks", {})
        if not isinstance(configured, dict):
            raise ValueError("client_apks 必须是客户端档案名到 APK 路径列表的对象")
        apk = configured.get(client_profile, [])
        if not isinstance(apk, list):
            raise ValueError("client_apks 档案项必须是 APK 路径列表")
    if isinstance(apk, (str, Path)):
        apk = [apk]
    if not isinstance(apk, (list, tuple)):
        raise ValueError("apk 必须是路径或路径列表")
    paths = []
    for value in apk:
        if not isinstance(value, (str, Path)) or not str(value).strip():
            raise ValueError("apk 包含空路径或非路径值")
        path = Path(os.path.expandvars(str(value))).expanduser()
        paths.append((path if path.is_absolute() else root_path() / path).resolve())
    return list(dict.fromkeys(paths))


def staged_members(filename):
    from .delivery_inputs import DeliveryMember
    doc = json.loads(filename.read_text("utf-8"))
    return [DeliveryMember(logical=e["logical_path"], root=e["root"],
                           member=member_name(e["root"], e["logical_path"]),
                           data=(filename.parent / e["source"]).read_bytes(), archive="staged",
                           from_version=doc["from_version"], to_version=doc["to_version"])
            for e in doc["members"]]


def inspect_output(members, baseline, changeset, *, apks, cache_dir=None):
    from .bundle_keys import bundled_keys, check_bundle_keys
    from .client_extensions import PF, check_client_extensions
    from .key_diff import compare_delivery
    outputs = {m.logical: m.data for m in members if m.root == "common"}
    indexes = []
    bundle = check_bundle_keys(apks, tables=outputs, cache_dir=cache_dir,
                               logical_paths=(PF,), loaded_indexes=indexes)
    keys = {PF: bundled_keys(indexes, PF)} if bundle["status"] in {"ok", "collision"} else None
    extensions = check_client_extensions(outputs, baseline, bundled_keys=keys,
        bundle_error=bundle.get("reason") if bundle["status"] == "error" else None)
    diff = compare_delivery(baseline, members=members, subject=changeset)
    checks = list(extensions["checks"])
    state = bundle["status"]
    checks.append(result("studio.bundle-keys", "问题" if state in {"collision", "error"} else
                         "未执行" if state == "skipped" else "满足",
                         bundle.get("reason") or ("APK 内置表键撞名" if state == "collision" else "APK 内置表键已核对"),
                         blocking=state in {"collision", "error"}, level="warn" if state == "skipped" else
                         "error" if state in {"collision", "error"} else "info"))
    checks.append(result("studio.key-diff", "问题" if not diff["ok"] else
                         "待验证" if diff["warnings"] else "满足",
                         "共享表存在删除键" if not diff["ok"] else
                         "；".join(diff["warnings"]) or "本次输出没有删除键或非主体改动",
                         blocking=not diff["ok"], level="error" if not diff["ok"] else
                         "warn" if diff["warnings"] else "info"))
    return {"bundleCheck": bundle, "keyDiff": diff, "clientExtensions": extensions}, checks


def write_reports(delivery, reports, draft_checks, manifest=None):
    from .icon_alpha import report
    from .key_diff import write_reports as write_diff
    reports["iconAlpha"] = report(draft_checks)
    if manifest:
        archives = {member: archive["name"] for archive in manifest["archives"] for member in archive["files"]}
        diff = reports["keyDiff"]
        for entry in diff["tables"] + diff["files"]:
            entry["archive"] = archives[entry["member"]]
        diff["delivery"]["archives"] = [a["name"] for a in manifest["archives"]]
    write_diff(reports["keyDiff"], delivery)
    for field, name in (("bundleCheck", "bundle-check"), ("iconAlpha", "icon-alpha"),
                        ("clientExtensions", "client-extensions")):
        write_json(delivery / (name + ".json"), reports[field])


def checksum_delivery(delivery):
    from wf.deliver.changeset import sha256
    # Rehearsals describe mutable server state and may be refreshed after export.
    sums = [f"{sha256(p.read_bytes())}  {p.relative_to(delivery).as_posix()}"
            for p in sorted(delivery.rglob("*")) if p.is_file() and p.name != "SHA256SUMS"
            and not (p.parent == delivery and p.name.startswith("rehearsal-") and p.suffix in {".json", ".md"})
            and "validation" not in p.relative_to(delivery).parts]
    (delivery / "SHA256SUMS").write_text("\n".join(sums) + "\n", "utf-8")
