"""The rogue compiler and table parser must share one injected input view."""
import pytest

from wf.tools.core import quest_lib as q


def test_load_table_uses_raw_reader(monkeypatch):
    expected = {"event": {"1": "quest,folder,round"}}
    calls = []

    def read(logical, path=None):
        calls.append((logical, path))
        return q.build_node(expected)

    monkeypatch.setattr(q, "read_raw", read)
    assert q.load_table("input.orderedmap") == expected
    assert calls == [("input.orderedmap", None)]


def test_explicit_raw_path_needs_no_store(tmp_path, monkeypatch):
    target = tmp_path / "resource"
    target.write_bytes(b"raw DSL bytes")
    monkeypatch.setattr(q, "store_path", lambda _: pytest.fail("unexpected store lookup"))
    assert q.read_raw("ignored", path=target) == b"raw DSL bytes"


@pytest.mark.parametrize("error,expected", [(None, True), (FileNotFoundError, False)])
def test_exists_uses_current_reader(monkeypatch, error, expected):
    def read(logical):
        if error:
            raise error(logical)
        return b""

    monkeypatch.setattr(q, "read_raw", read)
    assert q.exists_current("resource") is expected


def test_exists_preserves_access_errors(monkeypatch):
    def read(logical):
        raise PermissionError(logical)

    monkeypatch.setattr(q, "read_raw", read)
    with pytest.raises(PermissionError, match="resource"):
        q.exists_current("resource")
