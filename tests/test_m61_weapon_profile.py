"""Delivery selection reaches weapon validation without a default-profile fallback."""
from pathlib import Path

import pytest

from test_boss_shop_weapon import state  # noqa: F401
from test_studio_deliver_bridge import case  # noqa: F401
from wf.boss.shop_model import SOUL
from wf.boss.weapon_edit import check_ability_rows
from wf.studio import deliver_bridge as bridge


def test_build_passes_resolved_profile_and_evidence_to_compiler(case, monkeypatch):
    evidence = Path("selected-provides.json")
    monkeypatch.setattr("wf.caps.profiles.resolve_client", lambda *a, **kw: (evidence, "selected-v35"))
    seen = {}
    class Compiled(Exception):
        pass
    def compile_draft(*args, **options):
        seen.update(options)
        raise Compiled()
    monkeypatch.setattr(bridge, "compile_draft", compile_draft)
    store, _, view, out = case
    with pytest.raises(Compiled):
        bridge.build_draft("139985", from_version="1.4.132", to_version="1.4.133",
                           store=store, baseline_view=view, out=out, client_profile="selected-v35")
    assert seen["client_profile"] == "selected-v35" and seen["provides"] == evidence
    assert not out.exists()


def test_explicit_provides_uses_its_bound_swf_not_default_profile(state, monkeypatch):
    seen = []
    monkeypatch.setattr("wf.caps.profiles.read_client", lambda path: {"selected": str(path)})
    def inspect(provides):
        seen.append(provides)
        return {"mismatches": [], "tables": {"ability_soul": {
            "instant_content": {"kinds": ["32", "34"]}}}}
    monkeypatch.setattr("wf.apk.kinds.inspect_provides", inspect)
    monkeypatch.setattr("wf.apk.kinds.inspect_profile", lambda _: pytest.fail("unexpected default profile"))
    check_ability_rows("ability_soul", state.table(SOUL)["5010005"], provides="explicit.json")
    assert seen == [{"selected": "explicit.json"}]


def test_explicit_unknown_client_cannot_bypass_weapon_kind_evidence(state):
    with pytest.raises(ValueError, match="requires a selected client"):
        check_ability_rows("ability_soul", state.table(SOUL)["5010005"], client_profile=False)
