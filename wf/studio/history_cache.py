"""Content-check BOSS provenance without repeatedly inflating identical ZIP members."""
import hashlib
import json
from pathlib import Path
import struct
import zipfile

from wf.view.members import archive_members


def _wire_digest(package, name):
    """Hash exact bytes/metadata whose previously validated decode we reuse.

    Unchanged compressed bytes and decoding fields imply the same bytes that
    ZipFile.read already decoded and CRC-checked. Never use mtime or CRC alone.
    """
    info = package.getinfo(name)
    stream = package.fp
    stream.seek(info.header_offset)
    header = stream.read(30)
    if len(header) != 30 or header[:4] != b"PK\x03\x04":
        raise zipfile.BadZipFile("invalid historical member header")
    name_size, extra_size = struct.unpack_from("<HH", header, 26)
    size = name_size + extra_size + info.compress_size
    payload = stream.read(size)
    if len(payload) != size:
        raise zipfile.BadZipFile("truncated historical member")
    metadata = (info.filename, info.orig_filename, info.compress_type, info.flag_bits, info.CRC,
                info.file_size, info.compress_size, info.header_offset, info._end_offset,
                info.extract_version)
    digest = hashlib.sha256(json.dumps(metadata).encode("utf-8"))
    digest.update(header)
    digest.update(payload)
    return digest.hexdigest()


class HistoryInputs:
    def __init__(self, view):
        self.view = view
        self.archive_order = tuple(map(Path, getattr(view, "zips", ())))
        self.archives, self.logicals = {}, {}
        self._packages, self._raws = {}, {}

    def _package(self, filename):
        if filename not in self._packages:
            self._packages[filename] = zipfile.ZipFile(filename)
        return self._packages[filename]

    def close(self):
        for package in self._packages.values():
            package.close()
        self._packages.clear()
        self._raws.clear()

    def digest(self, logical):
        from wf.view.base149 import member
        if logical in self.logicals:
            return self.logicals[logical]
        name, records = member(logical), []
        for filename in self.archive_order:
            package = self._package(filename)
            if filename not in self.archives:
                self.archives[filename] = (archive_members(package), {})
            names, reads = self.archives[filename]
            if name not in names:
                continue
            if name not in reads:
                reads[name] = _wire_digest(package, names[name])
            records.append((str(filename), reads[name]))
        result = hashlib.sha256(json.dumps(records).encode("utf-8")).hexdigest()
        self.logicals[logical] = result
        return result

    def members(self, logical):
        from wf.view.base149 import member
        self.digest(logical)
        name = member(logical)
        for filename in self.archive_order:
            names, reads = self.archives[filename]
            if name not in reads:
                continue
            key = filename, name
            if key not in self._raws:
                package = self._package(filename)
                # New input still goes through normal decompression/CRC checks.
                raw = package.read(names[name])
                if _wire_digest(package, names[name]) != reads[name]:
                    raise ValueError("historical member changed while reading")
                self._raws[key] = raw
            yield filename, self._raws[key]

    def current(self):
        if tuple(map(Path, getattr(self.view, "zips", ()))) != self.archive_order:
            return not self.archives
        fresh = HistoryInputs(self.view)
        try:
            for filename, (names, reads) in self.archives.items():
                package = fresh._package(filename)
                current_names = archive_members(package)
                if current_names != names:
                    return False
                if any(_wire_digest(package, current_names[name]) != expected
                       for name, expected in reads.items()):
                    return False
            return True
        finally:
            fresh.close()
