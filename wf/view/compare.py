"""Byte-level ZIP member comparison, independent of container timestamps."""
from __future__ import annotations
import hashlib
import struct
import zipfile
from pathlib import Path


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def without_dos_timestamps(path):
    """Normalize only the four DOS date/time bytes in local/central headers."""
    data = bytearray(Path(path).read_bytes())
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            data[info.header_offset + 10:info.header_offset + 14] = bytes(4)
        offset = archive.start_dir
        for _ in archive.infolist():
            if data[offset:offset + 4] != b"PK\x01\x02":
                raise ValueError("unexpected central directory signature")
            data[offset + 12:offset + 16] = bytes(4)
            names, extra, comment = struct.unpack_from("<HHH", data, offset + 28)
            offset += 46 + names + extra + comment
    return bytes(data)


def compare_zip(expected, actual):
    expected, actual = Path(expected), Path(actual)
    result = {"name": expected.name, "expected_sha256": sha256(expected.read_bytes()),
              "actual_sha256": sha256(actual.read_bytes()), "members": []}
    with zipfile.ZipFile(expected) as old, zipfile.ZipFile(actual) as new:
        old_names, new_names = old.namelist(), new.namelist()
        if len(old_names) != len(set(old_names)) or len(new_names) != len(set(new_names)):
            raise ValueError("duplicate ZIP member names are not supported by this delivery format")
        result["member_order_equal"] = old_names == new_names
        for name in sorted(set(old_names) | set(new_names)):
            before = old.read(name) if name in old_names else None
            after = new.read(name) if name in new_names else None
            result["members"].append({"name": name, "equal": before == after,
                "expected_size": len(before) if before is not None else None,
                "actual_size": len(after) if after is not None else None,
                "expected_sha256": sha256(before) if before is not None else None,
                "actual_sha256": sha256(after) if after is not None else None})
        result["timestamp_changed_members"] = sum(old.getinfo(name).date_time != new.getinfo(name).date_time
                                                   for name in set(old_names) & set(new_names))
    result["equal_members"] = sum(m["equal"] for m in result["members"])
    result["different_members"] = sum(not m["equal"] for m in result["members"])
    result["container_equal"] = result["expected_sha256"] == result["actual_sha256"]
    result["container_equal_without_dos_timestamps"] = without_dos_timestamps(expected) == without_dos_timestamps(actual)
    return result


def compare_delivery(expected, actual, pattern="*.zip"):
    expected, actual = Path(expected), Path(actual)
    names = sorted(p.name for p in expected.glob(pattern))
    actual_names = sorted(p.name for p in actual.glob(pattern))
    if names != actual_names:
        raise ValueError(f"delivery ZIP names differ: expected={names}, actual={actual_names}")
    archives = [compare_zip(expected / name, actual / name) for name in names]
    return {"archives": archives, "zip_count": len(archives),
            "equal_members": sum(item["equal_members"] for item in archives),
            "different_members": sum(item["different_members"] for item in archives)}
