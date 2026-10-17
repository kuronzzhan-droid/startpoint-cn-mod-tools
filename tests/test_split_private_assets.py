"""Author-selected asset relocation is reversible and preserves consumer paths."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.private_asset_refs import replace_links, rewrite_python
from scripts.split_private_assets import apply_plan, decisions, plan
import wf.local_assets as resources


def setup_assets(tmp_path):
    directory = tmp_path / "assets/demo"
    directory.mkdir(parents=True)
    asset = directory / "icon.bin"
    asset.write_bytes(b"original asset")
    inventory = {"files": [{"path": "assets/demo/icon.bin",
                             "sha256": hashlib.sha256(asset.read_bytes()).hexdigest()}]}
    return directory, asset, inventory


def row(directory, choice="[ ] 可公开 / [x] 移出"):
    return f"| `{directory}` <!-- asset-dir:{directory} --> | {choice} |"


def test_only_checked_private_rows_are_selected():
    text = "\n".join([row("assets/a"), row("assets/a/child"),
                       row("assets/b", "[x] 可公开 / [ ] 移出"),
                       row("assets/c", "[ ] 可公开 / [ ] 移出")])
    assert decisions(text, {"assets/a", "assets/a/child", "assets/b", "assets/c"}) == ["assets/a"]


@pytest.mark.parametrize("text", [row("assets/a", "[x] 可公开 / [x] 移出"), row("../outside")])
def test_invalid_author_decisions_are_rejected(text):
    with pytest.raises(ValueError):
        decisions(text, {"assets/a"})


def test_empty_decision_does_not_touch_sources(tmp_path):
    assert plan(tmp_path, [], [tmp_path / "missing.py"], {"files": []}) == {"moves": [], "edits": []}


def test_move_preserves_bytes_and_python_json_references(tmp_path, monkeypatch):
    directory, asset, inventory = setup_assets(tmp_path)
    consumer = tmp_path / "consumer.py"
    consumer.write_text('"""Consumer."""\nfrom __future__ import annotations\n'
                        'from pathlib import Path\nROOT = Path(__file__).resolve().parent\n'
                        'ICON = ROOT / "assets" / "demo" / "icon.bin"\n', encoding="utf-8")
    spec = tmp_path / "spec.json"
    spec.write_text('{"src":"assets/demo/icon.bin"}', encoding="utf-8")
    changes = plan(tmp_path, ["assets/demo"], [asset, consumer, spec], inventory)
    assert asset.read_bytes() == b"original asset"  # planning is read-only
    apply_plan(tmp_path, changes)
    assert not directory.exists()
    assert (tmp_path / "private-assets/assets/demo/icon.bin").read_bytes() == b"original asset"
    monkeypatch.setattr(resources, "REPOSITORY", tmp_path)
    namespace = {"__file__": str(consumer)}
    exec(consumer.read_text(encoding="utf-8"), namespace)
    assert namespace["ICON"].read_bytes() == b"original asset"
    assert '"private-assets/assets/demo/icon.bin"' in spec.read_text(encoding="utf-8")


def test_moved_builder_keeps_actual_repository_root(tmp_path, monkeypatch):
    directory, asset, inventory = setup_assets(tmp_path)
    builder = directory / "build.py"
    builder.write_text('from pathlib import Path\nHERE = Path(__file__).resolve().parent\n'
                       'TOOLS = HERE.parent.parent\nICON = HERE / "icon.bin"\n', encoding="utf-8")
    apply_plan(tmp_path, plan(tmp_path, ["assets/demo"], [asset, builder], inventory))
    relocated = tmp_path / "private-assets/assets/demo/build.py"
    monkeypatch.setattr(resources, "REPOSITORY", tmp_path)
    namespace = {"__file__": str(relocated)}
    exec(relocated.read_text(encoding="utf-8"), namespace)
    assert namespace["TOOLS"] == tmp_path
    assert namespace["HERE"] == relocated.parent
    assert namespace["ICON"].read_bytes() == b"original asset"


def test_unknown_root_is_not_assumed_to_be_repository_assets(tmp_path):
    text = 'ASSET = get_root() / "assets" / "demo" / "icon.bin"\n'
    updated = rewrite_python(text, tmp_path / "consumer.py", tmp_path, ["assets/demo"])
    namespace = {"get_root": lambda: tmp_path}
    exec(updated, namespace)
    assert namespace["ASSET"] == tmp_path / "assets/demo/icon.bin"


def test_bare_directory_names_and_store_paths_are_not_rewritten(tmp_path):
    text = 'LABEL = "wiki"\nOTHER = self.store / "wiki"\n'
    assert rewrite_python(text, tmp_path / "consumer.py", tmp_path, ["wiki"]) == text
    assert replace_links('category="wiki"; wiki help', ["wiki"]) == 'category="wiki"; wiki help'
    assert replace_links('path.join(__dirname, "wiki")', ["wiki"]) == 'path.join(__dirname, "private-assets/wiki")'


def test_moved_builder_runs_directly_and_creates_new_output(tmp_path):
    directory, asset, inventory = setup_assets(tmp_path)
    package = tmp_path / "wf"
    package.mkdir()
    (package / "local_assets.py").write_bytes(Path(resources.__file__).read_bytes())
    builder = directory / "build.py"
    builder.write_text('from pathlib import Path\nHERE = Path(__file__).resolve().parent\n'
                       'OUTPUT = HERE / "new-output.bin"\nOUTPUT.write_bytes(b"generated")\n', encoding="utf-8")
    apply_plan(tmp_path, plan(tmp_path, ["assets/demo"], [asset, builder], inventory))
    relocated = tmp_path / "private-assets/assets/demo/build.py"
    environment = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    result = subprocess.run([sys.executable, "-B", str(relocated)], cwd=tmp_path,
                            env=environment, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert (relocated.parent / "new-output.bin").read_bytes() == b"generated"


@pytest.mark.parametrize("component", ["private-assets", "private-assets/assets/demo"])
def test_private_target_or_parent_junction_is_rejected(tmp_path, monkeypatch, component):
    directory, asset, inventory = setup_assets(tmp_path)
    link = tmp_path / component
    monkeypatch.setattr(Path, "is_junction", lambda path: path == link, raising=False)
    with pytest.raises(ValueError, match="link"):
        plan(tmp_path, ["assets/demo"], [asset], inventory)
    assert directory.exists()


def test_apply_rechecks_target_links_after_planning(tmp_path, monkeypatch):
    directory, asset, inventory = setup_assets(tmp_path)
    changes = plan(tmp_path, ["assets/demo"], [asset], inventory)
    monkeypatch.setattr(Path, "is_junction", lambda path: path == tmp_path / "private-assets", raising=False)
    with pytest.raises(ValueError, match="link"):
        apply_plan(tmp_path, changes)
    assert directory.exists()


@pytest.mark.parametrize("failure", ["destination", "changed", "outside"])
def test_plan_rejects_unsafe_or_stale_input_before_moving(tmp_path, failure):
    directory, asset, inventory = setup_assets(tmp_path)
    selected = ["assets/demo"]
    if failure == "destination":
        collision = tmp_path / "private-assets/assets/demo/icon.bin"
        collision.parent.mkdir(parents=True)
        collision.write_bytes(b"existing private content")
    elif failure == "changed":
        asset.write_bytes(b"changed")
    else:
        selected = ["../escape"]
    with pytest.raises(ValueError):
        plan(tmp_path, selected, [asset], inventory)
    assert directory.is_dir()


def test_existing_private_fixture_directory_is_merged_without_overwrite(tmp_path):
    _, asset, inventory = setup_assets(tmp_path)
    existing = tmp_path / "private-assets/assets/demo/old.bin"
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b"previous private fixture")
    apply_plan(tmp_path, plan(tmp_path, ["assets/demo"], [asset], inventory))
    assert existing.read_bytes() == b"previous private fixture"
    assert (existing.parent / "icon.bin").read_bytes() == b"original asset"


def test_apply_failure_restores_moves_and_reference_bytes(tmp_path, monkeypatch):
    directory, asset, inventory = setup_assets(tmp_path)
    first, second = tmp_path / "first.json", tmp_path / "second.json"
    for source in (first, second):
        source.write_text('{"src":"assets/demo/icon.bin"}', encoding="utf-8")
    original = first.read_bytes()
    changes = plan(tmp_path, ["assets/demo"], [asset, first, second], inventory)
    write_bytes = Path.write_bytes
    failed = False

    def fail_once(path, value):
        nonlocal failed
        if path == second and not failed:
            failed = True
            raise OSError("synthetic write failure")
        return write_bytes(path, value)

    monkeypatch.setattr(Path, "write_bytes", fail_once)
    with pytest.raises(OSError):
        apply_plan(tmp_path, changes)
    assert directory.exists()
    assert first.read_bytes() == second.read_bytes() == original
    assert asset.read_bytes() == b"original asset"


def test_merge_rollback_restores_empty_source_directories(tmp_path):
    directory, asset, inventory = setup_assets(tmp_path)
    (directory / "empty").mkdir()
    (directory / "nested").mkdir()
    (directory / "nested/child.bin").write_bytes(b"child")
    private = tmp_path / "private-assets/assets/demo"
    private.mkdir(parents=True)
    (private / "old.bin").write_bytes(b"preserve")
    reference = tmp_path / "reference.json"
    reference.write_text('{"src":"assets/demo/icon.bin"}', encoding="utf-8")
    changes = plan(tmp_path, ["assets/demo"], [asset, reference], inventory)
    reference.write_text("modified after planning", encoding="utf-8")
    with pytest.raises(ValueError):
        apply_plan(tmp_path, changes)
    assert (directory / "empty").is_dir()
    assert (directory / "nested/child.bin").read_bytes() == b"child"
    assert (private / "old.bin").read_bytes() == b"preserve"
    assert not (private / "nested").exists()


def test_resource_lookup_rejects_escape_and_prefers_private(tmp_path, monkeypatch):
    _, asset, _ = setup_assets(tmp_path)
    monkeypatch.setattr(resources, "REPOSITORY", tmp_path)
    assert resources.asset_path("assets/demo/icon.bin") == asset
    private = tmp_path / "private-assets/assets/demo/icon.bin"
    private.parent.mkdir(parents=True)
    private.write_bytes(b"private version")
    assert resources.asset_path("assets/demo/icon.bin") == private
    with pytest.raises(ValueError):
        resources.asset_path("../outside")
