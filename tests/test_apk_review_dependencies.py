"""Runtime closure and real-binary compatibility regression for reviewed clients."""
from copy import deepcopy
from pathlib import Path

import pytest

from wf.apk.local_registry import registrations
from wf.apk.register_local import provides_for, verified_evidence


@pytest.mark.parametrize("name", ["test-merge-1008094", "local-v35k3"])
def test_changed_runtime_cannot_be_granted_via_unchanged_parser(name):
    record = next(r for r in registrations() if r["profile_id"] == name)
    ids = {c["id"] for c in provides_for(record)["provides"]}
    withdrawn = {"client.equipment.gauge_gain_rules@1", "client.charge.cap@1",
                 "client.unique.sunburn@1", "client.equipment.rules_data@1", "client.overlimit.o8@1",
                 *[f"client.apk.patch{n:03d}@1" for n in (5, 53, 108, 115, 116, 129)]}
    if name == "test-merge-1008094":
        withdrawn |= {"client.dual_form.uid@1", "client.apk.patch128@1"}
    assert not ids & withdrawn
    evidence, withheld = verified_evidence(record["observations"])
    assert withheld == record["withheld"]
    assert any(x.get("id") == "client.equipment.gauge_gain_rules@1" and x["dependencies"] == [31]
               for x in withheld)


@pytest.mark.parametrize("runtime,dependents", [(21, {128}), (112, {5, 53, 115, 116}), (31, set())])
def test_one_changed_runtime_revokes_unchanged_dependents(runtime, dependents):
    from wf.apk.register_local import reference
    from wf.apk.evidence import v35e_evidence
    observations = deepcopy(reference()["methods"])
    target = next(p for p in v35e_evidence()["patches"] if p["number"] == runtime)["methods"][0]
    for m in observations:
        if (m["abc"], m["label"]) == (target["abc"], target["label"]):
            m["context_sha256"] = "0" * 64
    evidence, withheld = verified_evidence(observations)
    assert not ({runtime} | dependents) & {p["number"] for p in evidence["patches"]}
    if runtime == 31:
        assert "client.equipment.gauge_gain_rules@1" not in {c["id"] for c in evidence["method_capabilities"]}


@pytest.mark.parametrize("cid,dependency", [("client.charge.cap@1", 112),
    ("client.unique.sunburn@1", 112), ("client.dual_form.uid@1", 21),
    ("client.apk.patch005@1", 112)])
def test_old_provides_cannot_restore_withheld_runtime(cid, dependency):
    from wf.apk.evidence import v35e_evidence
    from wf.apk.provides import derive_provides
    from wf.caps.compat import check_compat
    from test_m2_compat import required
    stale = derive_provides(v35e_evidence())
    record = next(r for r in registrations() if r["profile_id"] == "test-merge-1008094")
    stale["source"]["swf_sha256"] = record["source"]["swf_sha256"]
    stale["patches"] = [p for p in stale["patches"] if p["number"] != dependency]
    stale["provides"] = [c for c in stale["provides"] if dependency not in c["patches"]]
    assert cid in {c["id"] for c in stale["provides"]}
    checks = check_compat(required([cid]), stale)
    assert any(c["blocking"] and c.get("id") == f"client.apk.patch{dependency:03d}@1" for c in checks)


@pytest.mark.parametrize("cid", ["client.equipment.rules_data@1", "client.overlimit.o8@1",
                                 "client.apk.patch108@1", "client.apk.patch129@1"])
def test_old_provides_cannot_restore_incomplete_method_or_asset_proof(cid):
    from wf.apk.evidence import v35e_evidence
    from wf.apk.provides import derive_provides
    from wf.caps.compat import check_compat
    from test_m2_compat import required
    stale = derive_provides(v35e_evidence())
    record = next(r for r in registrations() if r["profile_id"] == "test-merge-1008094")
    stale["source"]["swf_sha256"] = record["source"]["swf_sha256"]
    checks = check_compat(required([cid]), stale)
    assert any(c["rule"] == "capability.runtime-evidence" and c["blocking"] for c in checks)


def test_extra_parser_blocks_only_its_used_site(monkeypatch):
    from wf.caps.kind_compat import check_kind_sites
    from wf.studio.client_profile_signals import kind_site
    report = {"source": {"swf_sha256": "test"}, "tables": {
        t: {"instant_content": {"kinds": ["1", "724"]}} for t in ("ability", "leader_ability")},
        "mismatches": [{"kind": "724", "block": "instant_content", "missing_branches": [],
                        "unregistered_tables": ["leader_ability"]}]}
    monkeypatch.setattr("wf.apk.kinds.inspect_provides", lambda *a, **kw: report)
    def check(table, kind):
        return check_kind_sites({"kindSites": [kind_site(table, "instant_content", kind)]}, {}, {})
    assert not any(c["blocking"] for c in check("ability", "1"))
    assert not any(c["blocking"] for c in check("ability", "724"))
    assert any(c["blocking"] and c["rule"] == "capability.kind-registry" for c in check("leader_ability", "724"))
    report["mismatches"][0]["missing_branches"] = ["ability"]
    assert any(c["blocking"] for c in check("ability", "1"))


def test_reviewed_merge_real_binary_plain_row_and_unregistered_branch():
    from wf.apk.kinds import inspect_provides
    from wf.caps.profiles import resolve_client, read_client
    from wf.studio.client_profile_view import ClientProfileView
    from wf.studio.client_profile_signals import kind_site
    filename, _ = resolve_client(client_profile="test-merge-1008094")
    try:
        report = inspect_provides(read_client(filename))
    except FileNotFoundError as exc:
        pytest.skip(f"需要 client_apks.test-merge-1008094 的摘要匹配 APK/SWF：{exc}")
    assert any(x["kind"] == "724" and x["unregistered_tables"] == ["leader_ability"]
               for x in report["mismatches"])
    view = ClientProfileView(None)  # Full catalog: never hide the reviewed profile.
    assert view.compat([], sites=[kind_site("ability", "instant_content", "1")])["test-merge-1008094"]["compatible"]
    blocked = view.compat(["client.kind724.fever_ratio@1"], sites=[
        kind_site("leader_ability", "instant_content", "724")])["test-merge-1008094"]
    assert not blocked["compatible"]
    assert any(x["rule"] == "capability.kind-registry" for x in blocked["missing"])


@pytest.mark.parametrize("fallback", ["second", "swf", "none"])
def test_mismatching_apk_candidates_preserve_hash_binding(tmp_path, monkeypatch, fallback):
    from wf.apk import kinds
    from wf.caps import profiles
    first, second, swf = [tmp_path / n for n in ("first.apk", "second.apk", "client.swf")]
    for p in (first, second, swf):
        p.write_bytes(b"fixture")
    monkeypatch.setattr(profiles, "load_profiles", lambda: ("test", {
        "test": {"evidence": {"swf_sha256": "expected", "swf_path": str(swf)}}}))
    monkeypatch.setattr("wf.studio.delivery_safety.resolve_apks", lambda p: [first, second])
    seen = []
    def inspect(p, *, expected_sha256):
        p = Path(p)
        assert expected_sha256 == "expected"
        seen.append(p)
        if p == {"second": second, "swf": swf}.get(fallback):
            return {"matched": p.name}
        raise kinds.SwfHashMismatch("wrong SWF")
    monkeypatch.setattr(kinds, "inspect_swf", inspect)
    monkeypatch.setattr(kinds, "_compare", lambda report, *a: report)
    data = {"source": {"swf_sha256": "expected"}}
    if fallback == "none":
        with pytest.raises(kinds.SwfHashMismatch, match="所有可读候选"):
            kinds.inspect_provides(data)
    else:
        assert kinds.inspect_provides(data)["matched"] == (second if fallback == "second" else swf).name
    assert seen[:2] == [first, second]
