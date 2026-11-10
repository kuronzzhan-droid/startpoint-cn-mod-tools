"""Authored rogue settings stay local and are read by the same builder."""
import json
from pathlib import Path

from wf.tools.rogue import rogue_build as b


def test_default_authoring_does_not_overwrite_reviewed_package_data(tmp_path, monkeypatch):
    entrypoint = tmp_path / "wf/tools/rogue/rogue_build.py"
    entrypoint.parent.mkdir(parents=True)
    default = entrypoint.parent / "data/rogue_layout_plan.json"
    default.parent.mkdir()
    default.write_text('{"default": true}', encoding="utf-8")
    monkeypatch.setattr(b, "__file__", str(entrypoint))
    monkeypatch.setattr(b, "MOD_DIR", str(tmp_path))
    monkeypatch.setattr(b, "configured_path", lambda name: None)
    assert b.rogue_config_path(default.name) == default
    authored = b.rogue_config_output_path(default.name)
    assert authored == tmp_path / "work/rogue-config" / default.name
    authored.parent.mkdir(parents=True)
    authored.write_text('{"authored": true}', encoding="utf-8")
    assert b.rogue_config_path(default.name) == authored
    assert default.read_text("utf-8") == '{"default": true}'


def test_explicit_profile_destination_has_priority_over_defaults(tmp_path, monkeypatch):
    explicit = tmp_path / "custom-layout.json"
    monkeypatch.setattr(b, "configured_path", lambda name: explicit)
    assert b.rogue_config_path("rogue_layout_plan.json") == explicit
    assert b.rogue_config_output_path("rogue_layout_plan.json") == explicit


def test_reviewed_defaults_have_one_packaged_copy_and_keep_checkout_layout():
    checkout = Path(b.__file__).resolve().parents[3]
    packaged = checkout / "wf/tools/rogue/data"
    names = (
        "rogue_field_menu.json",
        "rogue_layout_plan.json",
        "rogue_special_bosses.json",
    )
    distribution = json.loads((checkout / "tool-distribution-v1.json").read_text("utf-8"))
    for name in names:
        assert not (checkout / name).exists()
        assert (packaged / name).is_file()
        assert f"wf/tools/rogue/data/{name}" in distribution["files"]
        assert name not in distribution["files"]
    layout = json.loads((packaged / "rogue_layout_plan.json").read_text("utf-8"))
    assert layout["floors"]["5"]["curses"] == ["元素禁壁"]
    assert layout["floors"]["12"]["curses"] == ["元素禁壁"]
    assert "field" not in layout["floors"]["5"]


def test_field_catalog_writes_the_packaged_default():
    from wf.tools.core import field_catalog

    checkout = Path(b.__file__).resolve().parents[3]
    assert field_catalog.OUT_JSON == checkout / "wf/tools/rogue/data/rogue_field_menu.json"
