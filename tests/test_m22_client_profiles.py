"""Real registry/evidence gates for default delivery and editor selection."""
import hashlib
import json
from copy import deepcopy

import pytest
import wf_quest_lib as nodes

from wf.caps import profiles
from wf.caps.facts import CHARACTER
from wf.caps.query import query_requirements
from wf.deliver.cli import main as deliver_main
from wf.deliver.prepush_base import digest
from wf.studio.capability_routes import requirements
from test_m2_deliver_caps import changeset
from test_studio_deliver_routes import routes


def test_v35_unique_query_reports_profile_and_hidden_capability():
    report = query_requirements(unique_strings=["wfx:28:72:10000:3:hidden_test"])
    assert report["clientProfile"] == "test-v34" and not report["selectedCompatible"]
    assert {"client.direct.base@1", "client.wfx.hidden_unique_icons@1"} <= set(report["capabilities"])
    assert "test-v35e" in report["requiredClientProfiles"]
    response = requirements({"unique": ["wfx:29:72:2500:0:hidden_test"],
                             "clientProfile": ["test-v35e"]})
    assert response.status == 200 and json.loads(response.body)["selectedCompatible"]
    assert requirements({"clientProfile": ["typo"]}).status == 400


def test_unknown_wfx_query_cannot_claim_compatibility():
    report = query_requirements(unique_strings=["wfx:999:0:1:0:hidden_unknown"])
    assert not report["recognized"] and report["unsupported"]
    assert "client.wfx.hidden_unique_icons@1" in report["capabilities"]
    assert not report["requiredClientProfiles"] and not report["selectedCompatible"]


def test_kind_and_dsl_selectors_keep_v34_support():
    kind = query_requirements(kinds=[422])
    dsl = query_requirements(dsl_markers=["dsl.buffTargetAs.convert"])
    assert kind["selectedCompatible"] and dsl["selectedCompatible"]
    assert "client.kind422.dash@1" in kind["capabilities"]
    assert "client.kind424.damage_convert@1" in dsl["capabilities"]
    assert not query_requirements(dsl_markers=["not_registered"])["recognized"]


def test_explicit_provides_and_profile_must_agree(tmp_path, capsys):
    v34, _ = profiles.resolve_client(client_profile="test-v34")
    assert profiles.resolve_client(v34, "test-v34") == (v34, "test-v34")
    with pytest.raises(ValueError, match="冲突"):
        profiles.resolve_client(v34, "test-v35e")
    with pytest.raises(SystemExit) as failure:
        deliver_main([str(tmp_path / "unused.json"), "--provides", str(v34),
                      "--client-profile", "test-v35e"])
    assert failure.value.code == 2 and "冲突" in capsys.readouterr().err


def test_editor_selected_profile_overrides_server_default_and_rejects_conflict(routes, monkeypatch):
    from wf.studio import deliver_bridge
    from wf.studio.drafts import DraftError
    _, delivery = routes
    v34, _ = profiles.resolve_client(client_profile="test-v34")
    delivery.default_provides = v34
    seen = {}
    def build(cid, **options):
        seen.update(options)
        return {"ok": True}
    monkeypatch.setattr(deliver_bridge, "build_draft", build)
    response = delivery.build({}, {"clientProfile": "test-v35e"}, cid="139985")
    assert json.loads(response.body)["ok"] and seen["client_profile"] == "test-v35e"
    assert seen["provides"] is None
    with pytest.raises(DraftError, match="冲突"):
        delivery.build({}, {"clientProfile": "test-v35e", "provides": str(v34)}, cid="139985")


def profile_fixture(tmp_path, monkeypatch):
    default, records = profiles.load_profiles()
    record = deepcopy(records[default])
    source, _ = profiles.resolve_client(client_profile=default)
    record["provides"] = "work/not-generated/provides.json"
    record["provides_fallback"] = "data/provides.json"
    fallback = tmp_path / record["provides_fallback"]
    fallback.parent.mkdir()
    fallback.write_bytes(source.read_bytes())
    record["provides_fallback_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    monkeypatch.setattr(profiles, "REPOSITORY", tmp_path)
    monkeypatch.setattr(profiles, "load_profiles", lambda: (default, {default: record}))
    return default, record, fallback


def test_missing_work_artifacts_use_checked_in_evidence(tmp_path, monkeypatch):
    default, _, fallback = profile_fixture(tmp_path, monkeypatch)
    assert profiles.resolve_client() == (fallback, default)
    assert not (tmp_path / "work").exists()


@pytest.mark.parametrize("fault", ["file", "swf", "apk"])
def test_profile_cannot_silently_use_changed_or_other_client_evidence(tmp_path, monkeypatch, fault):
    _, record, fallback = profile_fixture(tmp_path, monkeypatch)
    document = json.loads(fallback.read_bytes())
    if fault == "swf":
        document["source"]["swf_sha256"] = "0" * 64
    elif fault == "apk":
        document["source"].update(kind="apk", sha256="0" * 64)
    else:
        document["limitations"].append("changed file")
    raw = json.dumps(document).encode()
    fallback.write_bytes(raw)
    if fault != "file":
        record["provides_fallback_sha256"] = hashlib.sha256(raw).hexdigest()
    with pytest.raises(ValueError, match="哈希"):
        profiles.resolve_client()


def test_v35_changeset_default_blocks_v34_and_selected_v35e_passes(tmp_path, capsys):
    source = changeset(tmp_path, nodes.build_node({"wfx_pf4_123": "80:40A0FF"}))
    store = tmp_path / "store"
    key = digest(CHARACTER)
    character = store / key[:2] / key[2:]
    character.parent.mkdir(parents=True)
    character.write_bytes(nodes.build_node({}))
    # Shared-table preservation requires the complete pre-change table, even
    # when this test explicitly disables the external baseline view.
    from wf.caps.facts import STRINGS
    strings_key = digest(STRINGS)
    strings = store / strings_key[:2] / strings_key[2:]
    strings.parent.mkdir(parents=True, exist_ok=True)
    strings.write_bytes(nodes.build_node({}))
    common = [str(source), "--no-baseline-i-know", "--base-store", str(store)]
    assert deliver_main([*common, "--out", str(tmp_path / "v34")]) == 1
    first = json.loads(capsys.readouterr().out)
    assert first["client_compatibility"]["client_profile"] == "test-v34"
    checks = json.loads((tmp_path / "v34/compat.json").read_text("utf-8"))["results"]
    assert any(r["rule"] == "capability.missing" and r["blocking"] for r in checks)
    assert deliver_main([*common, "--out", str(tmp_path / "v35e"),
                         "--client-profile", "test-v35e"]) == 0
    assert json.loads(capsys.readouterr().out)["client_compatibility"]["status"] == "满足"
