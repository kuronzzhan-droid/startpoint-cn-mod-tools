"""Configuration precedence and a negative control for the path gate."""
import json
import os
from pathlib import Path
from unittest.mock import patch

from scripts.check_no_hardcoded_paths import scan, scan_text
from wf.paths import path, root_path


def test_profile_and_environment_precedence(tmp_path):
    profile = tmp_path / "paths.json"
    profile.write_text(json.dumps({"wf_root": "data", "paths": {"store": "store131"}}))
    with patch.dict(os.environ, {"WF_PROFILE": str(profile)}, clear=True):
        assert root_path() == tmp_path / "data"
        assert path("store", "aa") == tmp_path / "data/store131/aa"
        with patch.dict(os.environ, {"WF_ROOT": str(tmp_path / "other"),
                                     "WF_STORE": str(tmp_path / "explicit")}):
            assert root_path("x") == tmp_path / "other/x"
            assert path("store") == tmp_path / "explicit"
    assert not (tmp_path / "data").exists()  # Resolving never creates input stores.


def test_named_game_profile_does_not_override_explicit_path_profile(tmp_path):
    profile = tmp_path / "paths.json"
    profile.write_text(json.dumps({"wf_root": str(tmp_path / "inputs")}))
    with patch.dict(os.environ, {"WF_PROFILE": "cn", "WF_PATHS_PROFILE": str(profile)}, clear=True):
        assert root_path() == tmp_path / "inputs"


def test_path_gate_rejects_variants_and_absolute_imports():
    drive = "D" + ":"
    for separator in ("/", "\\", "\\\\"):
        assert scan_text("# " + drive + separator + "WF" + separator + "out", "x.py")
    assert scan_text("import sys\nsys.path.insert(0, '/machine/tools')", "x.py")
    assert scan_text("P='/machine/tools'\nsys.path.insert(0, P)", "x.py")
    assert scan_text("import sys\nsys.path.append('/machine/tools')", "x.py")
    assert scan_text("from sys import path\npath.insert(0, '/machine/tools')", "x.py")
    assert not scan_text("sys.path.insert(0, str(Path(__file__).parent))", "x.py")


def test_legacy_store_api_accepts_new_named_configuration(tmp_path):
    import wf_mod_tool as core
    store = tmp_path / "upload"
    store.mkdir()
    profile = tmp_path / "paths.json"
    profile.write_text(json.dumps({"wf_root": str(tmp_path), "paths": {"store": "upload"}}))
    with patch.dict(os.environ, {"WF_PATHS_PROFILE": str(profile)}, clear=True):
        assert core.resolve_active_store(profile=None) == store


def test_repository_has_no_machine_paths():
    assert scan()["findings"] == []
