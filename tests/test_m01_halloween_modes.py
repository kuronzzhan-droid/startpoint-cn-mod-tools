"""The full-source entry must not accidentally select the 221 historical branch."""
from types import SimpleNamespace
import runpy

import pytest


def test_halloween_build_selects_historical_mode_only_explicitly(monkeypatch):
    from wf.chars.halloween import replay
    module = SimpleNamespace(build=lambda context: context.historical_version)
    monkeypatch.setattr(replay.importlib, "import_module", lambda _: module)
    api = SimpleNamespace(KitContext=lambda pack: SimpleNamespace(pack=pack))
    assert replay.build_kit("seriol", object(), api) is None
    assert replay.build_kit("seriol", object(), api, "1.4.221") == "1.4.221"


def test_entry_points_select_distinct_modes(monkeypatch):
    from wf.chars.halloween import replay
    calls = []
    monkeypatch.setattr(replay, "main", lambda **kwargs: calls.append(kwargs))
    runpy.run_module("recipes.halloween_full", run_name="__main__")
    runpy.run_module("recipes.halloween221", run_name="__main__")
    assert calls == [{}, {"historical_version": "1.4.221"}]


def test_replay_refuses_to_recompute_missing_original_mask(monkeypatch, tmp_path):
    from wf.chars.halloween import art
    pack = SimpleNamespace(spec=SimpleNamespace(code="test", backdrop_colors=[(0, 0, 0)]),
                           evidence=tmp_path / "evidence")
    monkeypatch.setattr(art.HC, "pack_for", lambda _: pack)
    monkeypatch.setattr(art.hw_env, "INPUT", tmp_path / "missing-original-input")
    monkeypatch.setattr(art.images, "COLORS", {})
    monkeypatch.setattr(art.ART, "_load_masks", lambda *_: pytest.fail("must not regenerate original masks"))
    with pytest.raises(FileNotFoundError, match="original mask cache"):
        art.build("test")
    assert not (tmp_path / "missing-original-input").exists()
