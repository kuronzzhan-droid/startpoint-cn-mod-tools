"""Raw ZIP-content validation preserves CRC checks while avoiding reinflation."""
from pathlib import Path
import struct
from types import SimpleNamespace
import zipfile

import pytest

from wf.studio.history_cache import HistoryInputs
from wf.view.base149 import member


def fixture(tmp_path):
    path = tmp_path / "history.zip"
    logical, raw = "master/example.orderedmap", b"actual input " * 500
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as package:
        package.writestr(member(logical), raw)
    source = SimpleNamespace(zips=[path])
    inputs = HistoryInputs(source)
    inputs.digest(logical)
    assert list(inputs.members(logical)) == [(path, raw)]
    inputs.close()
    return path, logical, source, inputs


def test_studio_history_hit_hashes_bytes_without_repeating_decode(tmp_path, monkeypatch):
    _, _, _, inputs = fixture(tmp_path)

    def forbidden(*_):
        raise AssertionError("unchanged input should not be decompressed again")

    monkeypatch.setattr(zipfile.ZipFile, "read", forbidden)
    assert inputs.current()


@pytest.mark.parametrize("damage", ["crc", "flags", "compression", "payload", "local_header"])
def test_studio_history_tampered_decode_inputs_never_hit(tmp_path, monkeypatch, damage):
    path, logical, source, inputs = fixture(tmp_path)
    data = bytearray(path.read_bytes())
    central = data.index(b"PK\x01\x02")
    name_size, extra_size = struct.unpack_from("<HH", data, 26)
    offsets = {"crc": central + 16, "flags": central + 8,
               "compression": central + 10, "payload": 30 + name_size + extra_size,
               "local_header": 6}
    data[offsets[damage]] ^= 1
    path.write_bytes(data)
    assert not inputs.current()
    calls, read = [], zipfile.ZipFile.read

    def checked_read(package, name, *args, **kwargs):
        calls.append(name)
        return read(package, name, *args, **kwargs)

    monkeypatch.setattr(zipfile.ZipFile, "read", checked_read)
    fresh = HistoryInputs(source)
    try:
        fresh.digest(logical)
        if damage in {"crc", "flags", "compression"}:
            with pytest.raises((zipfile.BadZipFile, RuntimeError, NotImplementedError)):
                list(fresh.members(logical))
        else:
            # This bit can change only an encoding flag/padding while leaving
            # decoded bytes intact; it still invalidates and runs the decoder.
            list(fresh.members(logical))
        assert calls == [member(logical)]
    finally:
        fresh.close()


def test_studio_history_new_member_invalidates_absence(tmp_path):
    path, _, _, inputs = fixture(tmp_path)
    with zipfile.ZipFile(path, "a") as package:
        package.writestr(member("new-table"), b"new")
    assert not inputs.current()


def test_studio_history_original_filename_nul_rejects_cached_success(tmp_path):
    path, logical, source, inputs = fixture(tmp_path)
    data = bytearray(path.read_bytes())
    central = data.index(b"PK\x01\x02")
    old_size = struct.unpack_from("<H", data, central + 28)[0]
    insertion = central + 46 + old_size
    data[insertion:insertion] = b"\x00x"
    struct.pack_into("<H", data, central + 28, old_size + 2)
    end = data.index(b"PK\x05\x06")
    directory_size = struct.unpack_from("<I", data, end + 12)[0]
    struct.pack_into("<I", data, end + 12, directory_size + 2)
    path.write_bytes(data)
    with zipfile.ZipFile(path) as package:
        info = package.getinfo(member(logical))
        assert info.filename == member(logical)
        assert info.orig_filename == member(logical) + "\x00x"
        with pytest.raises(zipfile.BadZipFile, match="differ"):
            package.read(member(logical))
    assert not inputs.current()
    fresh = HistoryInputs(source)
    try:
        fresh.digest(logical)
        with pytest.raises(zipfile.BadZipFile, match="differ"):
            list(fresh.members(logical))
    finally:
        fresh.close()


def test_studio_history_unrelated_entry_overlap_rejects_cached_success(tmp_path):
    path = tmp_path / "overlap.zip"
    logical = "master/checked.orderedmap"
    name = member(logical)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as package:
        package.writestr(name, b"decoded input " * 500)
        package.writestr(member("unrelated"), b"second member")
    source = SimpleNamespace(zips=[path])
    inputs = HistoryInputs(source)
    inputs.digest(logical)
    assert len(list(inputs.members(logical))) == 1
    inputs.close()
    data = bytearray(path.read_bytes())
    first_central = data.index(b"PK\x01\x02")
    next_central = data.index(b"PK\x01\x02", first_central + 4)
    name_size, extra_size = struct.unpack_from("<HH", data, 26)
    # The consumed entry's own fields and bytes stay identical. Moving an
    # unrelated entry changes the decoder's derived overlap bound instead.
    struct.pack_into("<I", data, next_central + 42, 30 + name_size + extra_size + 1)
    path.write_bytes(data)
    with zipfile.ZipFile(path) as package:
        assert package.namelist() == [name, member("unrelated")]
        with pytest.raises(zipfile.BadZipFile, match="Overlapped"):
            package.read(name)
    assert not inputs.current()
    fresh = HistoryInputs(source)
    try:
        fresh.digest(logical)
        with pytest.raises(zipfile.BadZipFile, match="Overlapped"):
            list(fresh.members(logical))
    finally:
        fresh.close()


def test_studio_history_each_archive_opens_once_per_build(tmp_path, monkeypatch):
    path = tmp_path / "history.zip"
    logicals = ["first", "second"]
    with zipfile.ZipFile(path, "w") as package:
        for logical in logicals:
            package.writestr(member(logical), logical.encode())
    original, opened = zipfile.ZipFile, []

    def counting(filename, *args, **kwargs):
        opened.append(Path(filename))
        return original(filename, *args, **kwargs)

    monkeypatch.setattr(zipfile, "ZipFile", counting)
    inputs = HistoryInputs(SimpleNamespace(zips=[path]))
    try:
        for logical in logicals:
            inputs.digest(logical)
            assert list(inputs.members(logical)) == [(path, logical.encode())]
        assert opened == [path]
    finally:
        inputs.close()
    assert not inputs._packages


def test_studio_history_repeated_archive_preserves_overlay_order(tmp_path):
    logical = "repeated-input"
    archives = [tmp_path / "a.zip", tmp_path / "b.zip"]
    for path, value in zip(archives, (b"A", b"B")):
        with zipfile.ZipFile(path, "w") as package:
            package.writestr(member(logical), value)
    view = SimpleNamespace(zips=[archives[0], archives[1], archives[0]])
    inputs = HistoryInputs(view)
    try:
        inputs.digest(logical)
        assert list(inputs.members(logical)) == [(archives[0], b"A"), (archives[1], b"B"),
                                                 (archives[0], b"A")]
        assert len(inputs._packages) == 2
        assert inputs.current()
        view.zips = [archives[0], archives[0], archives[1]]
        assert not inputs.current()
    finally:
        inputs.close()
