"""Explicit pathlist selection preserves the fallback table names."""
import pytest


def test_prepush_pathlist_override_and_missing_file(tmp_path, monkeypatch):
    from wf.deliver import prepush
    supplied = tmp_path / "paths.txt"
    supplied.write_text("custom/specified.orderedmap\n", encoding="utf-8")
    monkeypatch.setattr(prepush, "configured_path", lambda _: pytest.fail("explicit path must win"))
    paths = prepush.load_pathlist(supplied)
    assert paths[prepush.digest("custom/specified.orderedmap")] == "custom/specified.orderedmap"
    assert paths[prepush.digest(prepush.ACTION_SKILL)] == prepush.ACTION_SKILL
    args = prepush.build_parser().parse_args(["--server-dir", str(tmp_path), "--pathlist", str(supplied)])
    assert args.pathlist == supplied
    with pytest.raises(FileNotFoundError, match="--pathlist"):
        prepush.load_pathlist(tmp_path / "missing.txt")
