"""Authored rogue settings stay local and are read by the same builder."""
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
