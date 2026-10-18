"""Bind declared requirements to the actual local archive members."""
from __future__ import annotations

from pathlib import Path
import zipfile

from wf.deliver.changeset import member_name, relative_path, sha256


def verify_scanned_members(dependencies, hashes):
    scanned = dependencies.get("scannedMembers", [])
    inferred = {member_name(m["root"], m["logical_path"]): m["sha256"] for m in scanned}
    if not scanned or len(scanned) != len(inferred) or inferred != hashes:
        raise ValueError("requires capability scan does not match delivered members")


def verify_declared_archives(requires, directory):
    if directory is None:
        raise ValueError("declared requires 必须提供归档目录并核对 scannedMembers")
    root = Path(directory).resolve()
    hashes = {}
    archives = requires["pack"]["archives"]
    if len(archives) != len(set(archives)):
        raise ValueError("declared requires repeats archives")
    for name in archives:
        target = (root / relative_path(name)).resolve()
        if not target.is_relative_to(root):
            raise ValueError("declared archive escapes delivery directory")
        try:
            with zipfile.ZipFile(target) as archive:
                for member in archive.infolist():
                    if member.is_dir():
                        continue
                    if member.filename in hashes:
                        raise ValueError("declared archives repeat members")
                    hashes[member.filename] = sha256(archive.read(member))
        except zipfile.BadZipFile as error:
            raise ValueError(f"invalid declared archive: {name}") from error
    verify_scanned_members(requires["requires"], hashes)
