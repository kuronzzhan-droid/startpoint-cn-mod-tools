"""Real 221 PF3 regression, 222 positive control and official corpus provenance."""
import hashlib
import json
import zipfile

import pytest

import wf_quest_lib as nodes
from wf.deliver.build import build_delivery
from wf.dsl.corpus import census_official_629
from wf.dsl.gate import check_629_actions
from wf.dsl.references import ability_references
from wf.paths import REPOSITORY, path, root_path
from wf.view.base149 import member

ABILITY = "master/ability/ability.orderedmap"
LEADER = "master/ability/leader_ability.orderedmap"
PF3 = ("battle/action/skill/action/ability_skill/ability_skill_crystal_swordman_halloween_pf3"
       "$ability_skill_crystal_swordman_halloween_pf3.action.dsl.amf3.deflate")
HASHES = {"221": "39d0013867105abb217bfc2fdab9308ddcfe1aaa9b9556b6ddc264ee443e85ed",
          "222": "9c305dfd2a8befc43c2fffeaa1014a036e6a096a1681ca70c40e24deeb08cec5"}


def historical_member(version, logical):
    directory = root_path("out/万圣新角色-20261016", f"delivery-1.4.{version}")
    if not directory.is_dir():
        pytest.skip("需要本机只读历史交付输入")
    for filename in sorted(directory.glob("*.zip")):
        with zipfile.ZipFile(filename) as archive:
            if member(logical) in archive.namelist():
                return archive.read(member(logical))
    pytest.fail(f"历史交付缺少 {logical}")


def pf3_inputs(version):
    table = nodes.parse_node(historical_member("221", ABILITY))
    reference, = [r for r in ability_references(ABILITY, table) if r["action"] + ".action.dsl.amf3.deflate" == PF3]
    assert reference["key"] == "1599855"
    raw = historical_member(version, PF3)
    assert hashlib.sha256(raw).hexdigest() == HASHES[version]
    # Keep the original leaf and tree, while isolating unrelated historical MODs.
    return {ABILITY: nodes.build_node({reference["key"]: table[reference["key"]]}),
            LEADER: nodes.build_node({}), PF3: raw}


def test_real_221_pf3_is_blocked_by_deliver_before_any_zip(tmp_path):
    inputs = pf3_inputs("221")
    source = tmp_path / "source"
    source.mkdir()
    doc = {"schema": "wf-change-set/1", "id": "real-pf3-221", "name": "真实 PF3 门禁反例",
           "from_version": "1.4.220", "to_version": "1.4.221", "slug": "real-pf3",
           "created_at": "2026-10-17", "local_test_only": True, "members": []}
    for index, (logical, raw) in enumerate(inputs.items()):
        filename = f"{index}.bin"
        (source / filename).write_bytes(raw)
        doc["members"].append({"root": "common", "logical_path": logical, "source": filename,
                               "sha256": hashlib.sha256(raw).hexdigest(), "before_sha256": None})
    changeset = source / "changeset.json"
    changeset.write_text(json.dumps(doc), "utf-8")
    out = tmp_path / "delivery"
    with pytest.raises(ValueError, match="629 gate blocked delivery"):
        build_delivery(changeset, out, no_baseline_i_know=True)
    report = json.loads((out / "dsl-629.json").read_text("utf-8"))
    assert report["checked_programs"] == [PF3]
    assert {f["command"] for f in report["findings"]} == {
        "SetPowerFilpSuppress", "Wait(NotifyPowerflipEnd only)"}
    assert not list(out.rglob("*.zip"))


def test_real_222_fix_passes_in_the_same_actual_629_context():
    inputs = pf3_inputs("222")
    report = check_629_actions(lambda logical: inputs[logical], changed_logicals={PF3})
    assert report["status"] == "满足"
    assert report["checked_programs"] == [PF3]
    assert report["findings"] == []


@pytest.mark.skipif(not (REPOSITORY / "profiles/local.json").is_file(), reason="需要本机官方归档 profile")
def test_official_corpus_reproduces_committed_member_evidence():
    expected = json.loads((REPOSITORY / "docs/m1/official-629-corpus.json").read_text("utf-8"))
    assert census_official_629(path("kulo") / ".cdn/cn") == expected
