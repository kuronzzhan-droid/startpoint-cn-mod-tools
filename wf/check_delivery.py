"""Read-back delivery checks, separated from schema dispatch."""
import hashlib
import zipfile

from wf.rules.catalog import result


def check_delivery(document, directory):
    previous = tuple(map(int, document["from_version"].split(".")))
    target = tuple(map(int, document["to_version"].split(".")))
    if previous >= target:
        raise ValueError("delivery version must move forward")
    for entry in document["archives"]:
        path = (directory / entry["name"]).resolve()
        if not path.is_relative_to(directory.resolve()):
            raise ValueError("archive escapes delivery directory")
        raw = path.read_bytes()
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
            if archive.testzip() is not None:
                raise ValueError(f"delivery ZIP CRC mismatch: {entry['name']}")
    return [result("delivery.forward-edge", "满足", "归档摘要、安装体积、CRC、成员清单及前进版本均已回读")]
