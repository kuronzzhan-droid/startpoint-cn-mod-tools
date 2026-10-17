"""Read-back delivery checks, separated from schema dispatch."""
import hashlib
import json
import zipfile

from wf.rules.catalog import result


def check_delivery(document, directory):
    previous = tuple(map(int, document["from_version"].split(".")))
    target = tuple(map(int, document["to_version"].split(".")))
    if previous >= target:
        raise ValueError("delivery version must move forward")
    installed_size, download_size, seen = 0, 0, set()
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
    upstream = json.loads(raw)
    if (upstream.get("schema"), upstream.get("baseVersion"), upstream.get("targetVersion")) != (
            1, document["from_version"], document["to_version"]):
        raise ValueError("upstream patch-manifest version mismatch")
    if {entry["layer"] for entry in upstream["archives"]} != {"common", "medium", "android"}:
        raise ValueError("upstream manifest must provide all three layers")
    for entry in upstream["archives"]:
        target = (upstream_path.parent / entry["relativePath"]).resolve()
        if not target.is_relative_to(upstream_path.parent):
            raise ValueError("upstream archive escapes patch directory")
        raw = target.read_bytes()
        if len(raw) != entry["bytes"] or hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            raise ValueError(f"upstream archive integrity mismatch: {entry['relativePath']}")
    _, raw = local_read(document["requires"])
    from wf.deliver.changeset import validate_document
    validate_document(json.loads(raw), "requires.schema.json")
    legacy = json.loads(local_read(document["legacy_manifest"])[1])
    if legacy.get("chain") != [entry["name"] for entry in document["archives"]]:
        raise ValueError("legacy manifest archive chain mismatch")
    checks = [result("delivery.forward-edge", "满足", "双格式归档摘要、安装体积、CRC、成员清单及前进版本均已回读")]
    gate = document["prepush"]
    checks.append(result("delivery.prepush", gate["status"], "自动 prepush 的实际结果",
                         blocking=gate["status"] == "问题", exit_code=gate["exit_code"], limitations=gate["limitations"]))
    return checks
