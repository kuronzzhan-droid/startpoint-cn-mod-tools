"""The public deliver entry point derives and binds requires to actual bytes."""
import json

import pytest
import wf_quest_lib as nodes
from wf.caps.facts import STRINGS
from wf.check_delivery import check_delivery
from wf.deliver.build import build_delivery
from wf.deliver.changeset import sha256


def changeset(tmp_path, raw):
    (tmp_path / "payload").write_bytes(raw)
    doc = {"schema": "wf-change-set/1", "id": "test", "name": "M2", "slug": "m2-test",
           "created_at": "2026-10-17", "from_version": "1.4.228", "to_version": "1.4.229",
           "local_test_only": True, "members": [{"root": "common", "logical_path": STRINGS,
           "source": "payload", "sha256": sha256(raw), "before_sha256": None}]}
    filename = tmp_path / "changeset.json"
    filename.write_text(json.dumps(doc), "utf-8")
    return filename


@pytest.mark.parametrize("resolution", ["resolved", "declared"])
def test_deliver_infers_override_and_readback_rejects_scan_digest_tampering(tmp_path, resolution):
    source = changeset(tmp_path, nodes.build_node({"desc_override_test": "攻击力提高10%"}))
    out = tmp_path / "delivery"
    delivery = build_delivery(source, out, no_baseline_i_know=True)
    required = json.loads((out / "requires.json").read_text("utf-8"))
    assert required["requires"]["clientCapabilities"] == ["client.text.desc_override@1"]
    assert required["requires"]["clientPatches"] == ["#2"]
    assert required["requires"]["capabilityResolution"] == "partial"
    assert required["requires"]["unresolved"]  # No character ownership baseline in this fixture.
    required["requires"]["capabilityResolution"] = resolution
    (out / "requires.json").write_text(json.dumps(required), "utf-8")
    check_delivery(delivery, out)
    required["requires"]["scannedMembers"][0]["sha256"] = "0" * 64
    (out / "requires.json").write_text(json.dumps(required), "utf-8")
    with pytest.raises(ValueError, match="capability scan"):
        check_delivery(delivery, out)


def test_invalid_table_blocks_before_any_archives(tmp_path):
    source = changeset(tmp_path, b"not an orderedmap")
    out = tmp_path / "blocked"
    with pytest.raises(ValueError):
        build_delivery(source, out, no_baseline_i_know=True)
    assert not list(out.rglob("*.zip"))


def test_readback_keeps_unresolved_pending_and_rejects_array_metadata(tmp_path):
    source = changeset(tmp_path, nodes.build_node({"ordinary": "text"}))
    out = tmp_path / "delivery"
    delivery = build_delivery(source, out, no_baseline_i_know=True)
    filename = out / "requires.json"
    required = json.loads(filename.read_text("utf-8"))
    required["requires"]["unresolved"] = [{"logical_path": "missing", "key": None,
                                          "referenced_by": {"logical_path": "caller"}}]
    filename.write_text(json.dumps(required), "utf-8")
    result = next(r for r in check_delivery(delivery, out) if r["rule"] == "capability.resolution")
    assert result["status"] == "待验证" and result["unresolved"]
    (out / delivery["upstream_manifest"]).write_text("[]", "utf-8")
    from wf.check import check_file
    results = check_file(out / "delivery-manifest.json")
    assert results[0]["status"] == "问题" and results[0]["blocking"]
