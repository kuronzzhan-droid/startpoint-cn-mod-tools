"""Recipe boundaries must reject unsafe writes before invoking the filesystem."""
import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from wf.paths import REPOSITORY
from wf.view import safety


def test_write_audit_blocks_truncate_and_unc_without_writing(monkeypatch, tmp_path):
    audits = []
    monkeypatch.setattr(sys, "addaudithook", audits.append)
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    monkeypatch.setattr(tempfile, "tempdir", tempfile.tempdir)
    for name in ("TEMP", "TMP", "PYTHONDONTWRITEBYTECODE"):
        monkeypatch.setenv(name, os.environ.get(name, ""))
    safety.restrict_writes(tmp_path)
    audit, = audits
    outside = tmp_path.parent / "never-created-by-recipe.txt"
    with pytest.raises(PermissionError, match="outside checkout"):
        audit("os.truncate", (outside, 0))
    with pytest.raises(PermissionError, match="UNC"):
        audit("open", (r"\\?\UNC\example.invalid\share\artifact.txt", "w", os.O_WRONLY | os.O_CREAT))
    assert not outside.exists()
    assert Path(os.environ["TEMP"]).is_relative_to(tmp_path)
    assert os.environ["TMP"] == os.environ["TEMP"]
    audit("os.truncate", (tmp_path / "valid-output", 0))


def test_ffmpeg_rejects_external_temp_before_start(monkeypatch):
    from wf.chars.halloween import voice
    monkeypatch.setattr(voice.hw_env, "TEMP", REPOSITORY.parent / "never-created-recipe-temp")
    monkeypatch.setattr(voice.subprocess, "run", lambda *a, **kw: pytest.fail("ffmpeg must not start"))
    with pytest.raises(PermissionError, match="outside checkout"):
        voice.to_mp3(Path("read-only-input.wav"))


def test_halloween_import_preserves_target_store(monkeypatch, tmp_path):
    import importlib
    from wf.chars.halloween import env
    target = str(tmp_path / "unrelated-fixture-store")
    monkeypatch.setenv("WF_TARGET_STORE", target)
    before = dict(os.environ)
    importlib.reload(env)
    from wf.chars.halloween import voice, kit_seriol  # noqa: F401
    assert dict(os.environ) == before


def test_ffmpeg_uses_checked_local_output_and_temp(monkeypatch, tmp_path):
    from wf.chars.halloween import voice
    monkeypatch.setattr(voice.hw_env, "TEMP", tmp_path)
    monkeypatch.setenv("FFREPORT", "file=outside-report.log:level=32")
    calls = []

    def run(command, **options):
        calls.append(command)
        assert Path(options["cwd"]) == tmp_path
        assert options["env"]["TEMP"] == options["env"]["TMP"] == str(tmp_path)
        assert not any(key.upper() == "FFREPORT" for key in options["env"])
        if command[-1] == "-":
            measurements = dict.fromkeys(("input_i", "input_tp", "input_lra", "input_thresh", "target_offset"), "0")
            return SimpleNamespace(stderr=json.dumps(measurements))
        output = Path(command[-1])
        assert output.is_relative_to(tmp_path)
        output.write_bytes(b"encoded-mp3")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(voice.subprocess, "run", run)
    assert voice.to_mp3(Path("read-only-input.wav")) == b"encoded-mp3"
    assert len(calls) == 2


@pytest.mark.parametrize("module_name,filename,error", [
    ("wf_external_probe", REPOSITORY.parent / "outside.py", "external WF API"),
    ("wf_archived_probe", REPOSITORY / "archive/legacy/probe.py", "archived code"),
    ("other_archived_alias", REPOSITORY / "archive/legacy/probe.py", "archived code"),
])
def test_api_origins_reject_external_and_archive_aliases(monkeypatch, module_name, filename, error):
    from wf.view.recipe_inputs import local_api_origins
    monkeypatch.setitem(sys.modules, module_name, SimpleNamespace(__file__=str(filename)))
    with pytest.raises(ImportError, match=error):
        local_api_origins()


def test_reconfigure_clears_live_table_caches(monkeypatch, tmp_path):
    from wf.view import base149, live149
    monkeypatch.setattr(base149, "_VIEW", base149._VIEW)
    monkeypatch.setattr(base149.q, "parse_node", lambda raw: json.loads(raw))
    active = tmp_path / "active"
    active.mkdir()
    logical = "master/cache-regression.orderedmap"
    for value in ("first", "second"):
        store = tmp_path / value
        resource = store / base149.member(logical).removeprefix("production/upload/")
        resource.parent.mkdir(parents=True)
        resource.write_text(json.dumps({"key": value}))
        base149.configure(store=store, active=active, tip=131)
        assert live149.flat(logical) == {"key": [[value]]}
        assert live149.nested(logical) == {"key": value}
    live149.flat.cache_clear()
    live149.nested.cache_clear()
