"""Pinned public evidence is portable; no APK or workstation profile required."""
import json
from copy import deepcopy

from wf.apk.evidence import digest
from wf.apk.local_registry import REVIEWED, registrations
from wf.apk.register_local import encode, provides_for
from wf.caps.profiles import REPOSITORY, load_profiles, resolve_client, read_client


def test_reviewed_merge_identity_and_reproducible_provides():
    record = json.loads((REPOSITORY / REVIEWED).read_text("utf-8"))
    assert record["schema"] == "wf-reviewed-client/1"
    assert record["package"]["package_name"] == "com.leiting.wt"
    assert record["package"]["versionCode"] == 1008094
    filename, selected = resolve_client(client_profile="test-merge-1008094")
    assert selected == record["profile_id"]
    document = read_client(filename, profile=record["profile"])
    assert provides_for(record) == document
    assert digest(encode(document)) == record["profile"]["provides_sha256"]
    assert record["withheld"] and document["provides"] and not document["unresolved"]
    assert load_profiles()[0] == "test-v34"  # Partial evidence is not a default upgrade.


def test_changed_method_context_cannot_grant_capability():
    record = next(r for r in registrations() if r["profile_id"] == "test-merge-1008094")
    before = provides_for(record)
    changed = deepcopy(record)
    for method in changed["observations"]:
        method["context_sha256"] = "0" * 64
    after = provides_for(changed)
    assert before["provides"] and not after["provides"]


def test_registered_swf_digest_recognized_without_binary(monkeypatch, tmp_path):
    from wf.apk import evidence
    record = next(r for r in registrations() if r["profile_id"] == "test-merge-1008094")
    monkeypatch.setattr(evidence, "digest", lambda _: record["source"]["swf_sha256"])
    summary, source = evidence._binary_record(tmp_path / "fixture.swf", b"fixture", {})
    assert summary["patches"] and summary["local_withheld"]
    assert source["swf_sha256"] == record["source"]["swf_sha256"]


def test_declared_profiles_never_claim_actual_kind_support():
    # The historical UI regressions use their original three binary profiles.
    # Cover the newer report-only profiles separately: no SWF means pending,
    # never a fabricated supported/unsupported branch result.
    from wf.studio.client_profile_view import ClientProfileView
    from wf.studio.client_profile_signals import kind_site
    view = ClientProfileView(None)
    clients = view.clients()
    view._clients = {key: clients[key] for key in ("p12b", "p13")}
    checks = view.compat([], sites=[kind_site("leader_ability", "instant_content", "423")])
    assert set(checks) == {"p12b", "p13"}
    for result in checks.values():
        assert not result["compatible"]
        assert any(row["rule"] == "capability.kind-evidence" and row["status"] == "待验证"
                   for row in result["missing"])


def test_kind_inspection_uses_configured_profile_apk(tmp_path, monkeypatch):
    from wf.apk import kinds
    from wf.caps import profiles
    fake_apk = tmp_path / "client.apk"
    fake_apk.write_bytes(b"fixture")
    monkeypatch.setattr(profiles, "load_profiles", lambda: ("fixture", {
        "fixture": {"evidence": {"swf_sha256": "expected"}}}))
    monkeypatch.setattr("wf.studio.delivery_safety.resolve_apks", lambda profile: [fake_apk])
    seen = []
    monkeypatch.setattr(kinds, "inspect_swf", lambda filename, **kw: seen.append((filename, kw)) or {})
    monkeypatch.setattr(kinds, "_compare", lambda report, *args: report)
    kinds.inspect_provides({"source": {"swf_sha256": "expected"}})
    assert seen == [(fake_apk, {"expected_sha256": "expected"})]
