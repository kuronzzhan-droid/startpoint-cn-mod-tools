"""Read-back delivery checks, separated from schema dispatch."""
import hashlib
import json
import zipfile

from wf.rules.catalog import result


def _object(raw, label):
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def reward_results(report):
    evidence = report.get("companion_reward_keys", {})
    if not isinstance(evidence, dict):
        raise ValueError("prepush companion_reward_keys must be an object")
    findings = [f for f in report["findings"]
                if f.get("fid", "").startswith("companion.reward_key:")]
    errors = any(f.get("level") == "ERROR" for f in findings)
    warnings = any(f.get("level") == "WARN" for f in findings)
    if errors:
        state, message = "问题", "新增服务端奖励行缺少候选客户端奖励键"
    elif warnings:
        state, message = "待验证", "存量服务端奖励行缺少候选客户端奖励键"
    elif evidence.get("executed") is not True:
        state, message = "未执行", "缺少服务端奖励键对照的执行证据"
    elif evidence.get("server_baseline_complete") is not True:
        state, message = "待验证", "奖励键对照的服务端基线不完整"
    else:
        state, message = "满足", "本次服务端奖励行与候选客户端奖励键已核对"
    return result("delivery.reward-keys", state, message, blocking=errors,
                  findings=findings, evidence=evidence)


def check_delivery(document, directory):
    previous = tuple(map(int, document["from_version"].split(".")))
    target = tuple(map(int, document["to_version"].split(".")))
    if previous >= target:
        raise ValueError("delivery version must move forward")
    installed_size, download_size, seen, hashes = 0, 0, set(), {}
    for entry in document["archives"]:
        path = (directory / entry["name"]).resolve()
        if not path.is_relative_to(directory.resolve()):
            raise ValueError("archive escapes delivery directory")
        raw = path.read_bytes()
        download_size += len(raw)
        if len(raw) != entry["size"] or hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            raise ValueError(f"delivery archive integrity mismatch: {entry['name']}")
        with zipfile.ZipFile(path) as archive:
            members = [item for item in archive.infolist() if not item.is_dir()]
            if len(members) != entry["members"] or sum(item.file_size for item in members) != entry["installed_size"]:
                raise ValueError(f"delivery installed size or count mismatch: {entry['name']}")
            if len(set(item.filename for item in members)) != len(members):
                raise ValueError(f"duplicate ZIP member: {entry['name']}")
            if set(item.filename for item in members) != set(entry["files"]):
                raise ValueError(f"delivery files list mismatch: {entry['name']}")
            names = {item.filename for item in members}
            if names & seen:
                raise ValueError("delivery repeats members across seq archives")
            seen.update(names)
            hashes.update({name: hashlib.sha256(archive.read(name)).hexdigest() for name in names})
            installed_size += sum(item.file_size for item in members)
            if archive.testzip() is not None:
                raise ValueError(f"delivery ZIP CRC mismatch: {entry['name']}")
    if installed_size != document["installed_size"] or download_size != document["download_size"]:
        raise ValueError("delivery total installed/download sizes mismatch")

    def local_read(name):
        target = (directory / name).resolve()
        if not target.is_relative_to(directory.resolve()):
            raise ValueError("metadata path escapes delivery directory")
        return target, target.read_bytes()

    upstream_path, raw = local_read(document["upstream_manifest"])
    upstream = _object(raw, "upstream manifest")
    if (upstream.get("schema"), upstream.get("baseVersion"), upstream.get("targetVersion")) != (
            1, document["from_version"], document["to_version"]):
        raise ValueError("upstream patch-manifest version mismatch")
    if {entry["layer"] for entry in upstream["archives"]} != {"common", "medium", "android"}:
        raise ValueError("upstream manifest must provide all three layers")
    layered_hashes, empty_layers = {}, set()
    roots = {"common": "upload", "medium": "medium_upload", "android": "android_upload"}
    for entry in upstream["archives"]:
        target = (upstream_path.parent / entry["relativePath"]).resolve()
        if not target.is_relative_to(upstream_path.parent):
            raise ValueError("upstream archive escapes patch directory")
        raw = target.read_bytes()
        if len(raw) != entry["bytes"] or hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            raise ValueError(f"upstream archive integrity mismatch: {entry['relativePath']}")
        with zipfile.ZipFile(target) as archive:
            names = [item.filename for item in archive.infolist() if not item.is_dir()]
            if len(names) != len(set(names)) or archive.testzip() is not None:
                raise ValueError("upstream duplicate member or CRC mismatch")
            if names == [".empty"] and archive.read(".empty") == b"":
                if entry["layer"] in empty_layers:
                    raise ValueError("upstream repeats empty layer marker")
                empty_layers.add(entry["layer"])
                continue
            prefix = "production/" + roots[entry["layer"]] + "/"
            for name in names:
                if not name.startswith(prefix) or name in layered_hashes:
                    raise ValueError("upstream member layer or duplication mismatch")
                layered_hashes[name] = hashlib.sha256(archive.read(name)).hexdigest()
    if layered_hashes != hashes or any(
            name.startswith("production/" + roots[layer] + "/")
            for layer in empty_layers for name in layered_hashes):
        raise ValueError("upstream members differ from legacy members")
    _, raw = local_read(document["requires"])
    from wf.deliver.changeset import validate_document
    requirements = _object(raw, "requires")
    validate_document(requirements, "requires.schema.json")
    pack, dependencies = requirements["pack"], requirements["requires"]
    if (pack["since"], pack["tail"], pack["archives"]) != (
            document["from_version"], document["to_version"], [a["name"] for a in document["archives"]]):
        raise ValueError("requires input versions or archives differ from delivery")
    if dependencies["capabilityResolution"] in {"resolved", "partial", "declared"}:
        from wf.caps.scan_binding import verify_scanned_members
        verify_scanned_members(dependencies, hashes)
    legacy = _object(local_read(document["legacy_manifest"])[1], "legacy manifest")
    if legacy.get("chain") != [entry["name"] for entry in document["archives"]]:
        raise ValueError("legacy manifest archive chain mismatch")
    checks = [result("delivery.forward-edge", "满足", "双格式归档摘要、安装体积、CRC、成员清单及前进版本均已回读")]
    incomplete = dependencies["capabilityResolution"] in {"partial", "pending-m2"} or bool(dependencies.get("unresolved"))
    checks.append(result("capability.resolution", "待验证" if incomplete else "满足",
                         "依赖引用尚未完整解析" if incomplete else "依赖声明及扫描成员摘要已核对；目标客户端兼容性需另行匹配",
                         unresolved=dependencies.get("unresolved", [])))
    gate = document["prepush"]
    assertions = _object(local_read(document["assertions"])[1], "assertions")
    if (assertions.get("from_version"), assertions.get("to_version")) != (
            document["from_version"], document["to_version"]):
        raise ValueError("assert_box version does not match delivery")
    client_assertions = [entry for entry in assertions["files"] if entry["kind"] == "client"]
    if len(client_assertions) != len(hashes) or {entry["member"]: entry["sha256"] for entry in client_assertions} != hashes:
        raise ValueError("assert_box client assertions do not match delivered members")
    for entry in assertions["files"]:
        if entry["kind"] == "server":
            raw = local_read("server/" + entry["target"])[1]
            if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
                raise ValueError("assert_box server assertion does not match staged bytes")
    report = _object(local_read(gate["report"])[1], "prepush report")
    local_read(gate["log"])
    baseline = document["baseline"]
    contract = report.get("local_contract", {})
    if not isinstance(contract, dict):
        raise ValueError("prepush local_contract must be an object")
    if gate["exit_code"] == 0 and any(entry["kind"] == "server" for entry in assertions["files"]):
        if not contract.get("server_pre_hashes_checked") or not contract.get("server_post_hashes_checked"):
            raise ValueError("server pre/post hashes were not checked")
    if baseline["no_baseline_i_know"]:
        if baseline["tip"] is not None or baseline["lock"] is not None or not contract.get("no_baseline_i_know"):
            raise ValueError("baseline waiver does not match prepush evidence")
    else:
        lock = json.loads(local_read(baseline["lock"])[1])
        if baseline["tip"] != document["from_version"] or lock.get("tip") != baseline["tip"]:
            raise ValueError("baseline tip does not match delivery")
        if gate["exit_code"] == 0 and not contract.get("pre_and_post_hashes_checked"):
            raise ValueError("baseline hashes were not checked")
    dsl = _object(local_read(document["dsl_gate"])[1], "DSL gate")
    if dsl.get("status") not in {"满足", "不适用", "待验证"}:
        raise ValueError("629 gate did not pass")
    if gate["since"] != document["from_version"] or report.get("since") != gate["since"]:
        raise ValueError("prepush since does not match delivery")
    findings = report.get("findings")
    if not isinstance(findings, list) or not all(isinstance(f, dict) for f in findings):
        raise ValueError("prepush report lacks findings")
    has_errors = any(f.get("level") == "ERROR" for f in findings) or contract.get("errors")
    if gate["status"] in {"满足", "待验证"} and (gate["exit_code"] != 0 or has_errors):
        raise ValueError("prepush status contradicts exit code or ERROR findings")
    skipped = any(any(token in f.get("fid", "") for token in ("skipped", "missing", "failed", "view.broken")) for f in findings)
    if gate["status"] == "满足" and (gate["limitations"] or skipped):
        raise ValueError("prepush status ignores unexecuted checks")
    checks.append(result("delivery.prepush", gate["status"], "自动 prepush 的实际结果",
                         blocking=gate["status"] == "问题", exit_code=gate["exit_code"], limitations=gate["limitations"]))
    checks.append(reward_results(report))
    from wf.deliver.client_compatibility import readback_compatibility, readback_draft_checks
    checks.extend(readback_compatibility(document, directory, local_read, requirements))
    checks.extend(readback_draft_checks(document, local_read))
    return checks
