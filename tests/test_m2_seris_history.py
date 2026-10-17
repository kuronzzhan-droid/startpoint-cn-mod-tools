"""The actual 1.4.209 Seris data needs PF4, independent of client version labels."""
import json

import pytest

from wf.apk.provides import build_provides, derive_provides
from wf.caps.compat import check_compat
from wf.caps.requirements import requirements_document
from wf.paths import REPOSITORY
from wf.view.base149 import member
from wf.view.manifest import ManifestView
from wf_wiki_catalog_source import TABLES


def seris_requirements():
    before, after = ManifestView("1.4.208"), ManifestView("1.4.209")
    members = {}
    for logical in sorted(set(TABLES.values())):
        archive = after.index.get(member(logical))
        if archive and "1.4.208-1.4.209-" in archive.name:
            raw, _ = after.read_raw(logical)
            members[member(logical)] = (raw, {"root": "common", "logical_path": logical})
    doc = {"from_version": "1.4.208", "to_version": "1.4.209"}
    archives = [p.name for p in after.zips if "1.4.208-1.4.209-" in p.name]
    # Add the actual newly delivered DSL closure, rather than allowing the
    # pre-209 baseline to stand in for the post-209 skill bodies.
    for _ in range(32):
        result = requirements_document(doc, members, archives, read_raw=before.read_raw)
        if not result["requires"]["unresolved"]:
            break
        for missing in result["requires"]["unresolved"]:
            logical = missing["logical_path"]
            assert logical.endswith(".action.dsl.amf3.deflate"), missing
            assert member(logical) not in members, missing
            raw, _ = after.read_raw(logical)
            members[member(logical)] = (raw, {"root": "common", "logical_path": logical})
    else:
        raise AssertionError("Seris dependency closure did not converge")
    before.verify()
    after.verify()
    return result


@pytest.mark.skipif(not (REPOSITORY / "profiles/local.json").exists(), reason="requires local read-only history")
def test_real_seris209_fails_when_v34_loses_patches87_to89():
    requirements = seris_requirements()
    assert "client.pf.level4@1" in requirements["requires"]["clientCapabilities"]
    record = json.loads((REPOSITORY / "wf/apk/data/v34-evidence.json").read_text("utf-8"))
    # The checked-in summary is an auditable record of the real v34 sources.
    full = build_provides(REPOSITORY / "wf/apk/data/v34-evidence.json")
    good = check_compat(requirements, full)
    assert not any(r["blocking"] for r in good), good
    stripped = {**record, "patches": [p for p in record["patches"] if p["number"] not in {87, 88, 89}]}
    bad = check_compat(requirements, derive_provides(stripped))
    pf = next(r for r in bad if r.get("id") == "client.pf.level4@1")
    assert pf["status"] == "问题" and pf["blocking"] and "缺 PF Lv4" in pf["message"]
