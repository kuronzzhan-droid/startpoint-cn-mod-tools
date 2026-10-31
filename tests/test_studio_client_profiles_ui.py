"""编辑台「目标客户端」只读胶水：档案说明、按标记/行/程序/kind 查能力、全角色兼容报告。"""
from __future__ import annotations

import csv
import io
import json

import pytest

from test_m1_balance import valid_row
from test_m2_requirements import ability
from test_studio_deliver_routes import _FakeSource
from wf.caps.facts import UNIQUE
from wf.studio.client_profile_view import COMPAT_REPORT
from wf.studio.server import StudioApp
from wf.view.layout import col

HIDDEN = "wfx:24:0:10000:0:hidden_mo_direct_base"


class _Source(_FakeSource):
    tables = {UNIQUE: {"16998502": [[HIDDEN, "猎魔·直击基础倍率", "", "99999999", "1"]],
                       "13999010": [["hidden_kyle_moon_charge_cap", "强化充能速度"]]}}

    def table(self, name, official=False):
        return self.tables.get(name, {})

    def tree(self, logical):
        return None


@pytest.fixture(scope="module")
def app():
    # This regression suite describes the original v34/v35e/v35k3 comparison.
    # Keep its exact assertions stable as independently reviewed clients arrive.
    from wf.caps import profiles
    original = profiles.load_profiles
    with pytest.MonkeyPatch.context() as patch:
        def historical_profiles(filename=None):
            default, records = original(filename)
            return default, {name: records[name] for name in ("test-v34", "test-v35e", "local-v35k3")}
        patch.setattr(profiles, "load_profiles", historical_profiles)
        yield StudioApp(_Source())


@pytest.fixture
def actual_swf_evidence(app):
    from wf.apk.kinds import inspect_profile
    for name in app.client_profiles.clients():
        try:
            inspect_profile(name)
        except FileNotFoundError as exc:
            pytest.skip(f"真实 SWF 分支集成测试缺少本机 {name} 的摘要匹配 SWF/APK：{exc}")


def call(app, path, query=None, body=None):
    response = app.dispatch("POST" if body is not None else "GET", path, query or {}, body)
    return response.status, json.loads(response.body)


def test_profiles_name_default_and_extra_capabilities(app):
    status, body = call(app, "/api/studio/client-profiles")
    assert status == 200 and body["defaultClientProfile"] == "test-v34"
    profiles = {p["id"]: p for p in body["profiles"]}
    assert profiles["test-v34"]["default"] and profiles["test-v34"]["label"] == "v34"
    v35e = profiles["test-v35e"]
    assert v35e["label"] == "v35e" and v35e["versionCode"] == 1008003 and v35e["available"]
    assert v35e["extraCount"] > len(v35e["extra"]) > 0
    assert "client.direct.base@1" in {e["id"] for e in v35e["extra"]}
    assert not any(e["id"].startswith("client.apk.patch") for e in v35e["extra"])


def test_lookup_kind_unique_custom_and_explicit_capability(app):
    _, kind = call(app, "/api/studio/caps/lookup", {"kind": ["422"]})
    assert [c["id"] for c in kind["capabilities"]] == ["client.kind422.dash@1"]
    assert kind["requiredClientProfiles"] == ["test-v34", "test-v35e", "local-v35k3"]
    assert "仅检索能力目录" in kind["note"] and "不证明该 kind 在具体表/块受支持" in kind["note"]
    _, hidden = call(app, "/api/studio/caps/lookup", {"unique": [HIDDEN]})
    assert {"client.direct.base@1", "client.wfx.hidden_unique_icons@1"} <= {c["id"] for c in hidden["capabilities"]}
    assert hidden["requiredClientProfiles"] == ["test-v35e"]
    missing = {m["id"]: m for m in hidden["profiles"]["test-v34"]["missing"]}
    assert missing["client.direct.base@1"]["patches"] == [112, 113, 124, 130]
    assert missing["client.wfx.hidden_unique_icons@1"]["missingPatches"] == [131]
    _, custom = call(app, "/api/studio/caps/lookup", {"customKey": ["wfx_pf4_139990"]})
    assert custom["requiredClientProfiles"] == ["test-v35e", "local-v35k3"]
    _, explicit = call(app, "/api/studio/caps/lookup", {"capability": ["client.direct.base@1"]})
    assert [c["id"] for c in explicit["capabilities"]] == ["client.direct.base@1"]
    assert explicit["requiredClientProfiles"] == ["test-v35e"]


def test_lookup_rejects_empty_and_unknown_capability(app):
    assert call(app, "/api/studio/caps/lookup")[0] == 400
    assert call(app, "/api/studio/caps/lookup", {"capability": ["client.nope@1"]})[0] == 400


def test_unknown_wfx_marker_is_never_compatible(app):
    _, body = call(app, "/api/studio/caps/lookup", {"unique": ["wfx:999:0:1:0:x"]})
    assert body["unsupported"] and not body["recognized"] and body["requiredClientProfiles"] == []


def test_rows_follow_unique_reference_to_v35e_string(actual_swf_evidence, app):
    plain = valid_row("plain")
    linked = valid_row("linked")
    linked[col("ability", "instant_content", "unique_condition_id")] = "16998502"
    status, body = call(app, "/api/drafts/169985/caps/rows", body={"rows": [
        {"id": "a", "table": "ability", "key": "1001", "cells": plain},
        {"id": "b", "table": "ability", "key": "1001", "cells": linked}]})
    assert status == 200
    a, b = body["rows"]["a"], body["rows"]["b"]
    assert not [c for c in a["capabilities"] if not c["official"]]
    assert b["requiredClientProfiles"] == ["test-v35e"]
    assert {"type": "unique", "id": "16998502", "stringId": HIDDEN, "name": "猎魔·直击基础倍率"} in b["references"]


@pytest.mark.parametrize("kind", [419, 422, 423, 424])
def test_rows_official_instant_collision_is_supported_without_patch_dependency(actual_swf_evidence, app, kind):
    row = valid_row("official")
    row[col("ability", "instant_content", "kind")] = str(kind)
    _, body = call(app, "/api/drafts/169985/caps/rows", body={"rows": [{"id": "x", "table": "ability", "key": "1", "cells": row}]})
    result = body["rows"]["x"]
    assert not result["capabilities"] and not result["placement"]
    assert result["requiredClientProfiles"] == ["test-v34", "test-v35e", "local-v35k3"]
    sites = [signal["value"] for signal in result["signals"] if signal["kind"] == "kind_site"]
    assert sites == [{"logical_path": "master/ability/ability.orderedmap", "key": "1", "row": 0,
                      "table": "ability", "block": "instant_content", "kind": str(kind)}]


@pytest.mark.parametrize("table,kind,expected", [
    ("ability", 422, "client.kind422.dash@1"),
    ("ability", 423, "client.kind423.gauge_source_limit@1"),
    ("ability_soul", 423, "client.equipment.gauge_gain_rules@1"),
    ("equipment_enhancement_ability", 423, "client.equipment.gauge_gain_rules@1"),
])
def test_rows_during_kind_dependency_is_table_scoped(actual_swf_evidence, app, table, kind, expected):
    cells = next(csv.reader(io.StringIO(ability(kind, table=table))))
    _, body = call(app, "/api/drafts/169985/caps/rows", body={"rows": [
        {"id": "x", "table": table, "key": "1", "cells": cells}]})
    result = body["rows"]["x"]
    assert [cap["id"] for cap in result["capabilities"]] == [expected]
    expected_profiles = ["test-v34", "test-v35e"]
    if expected == "client.kind422.dash@1":
        expected_profiles.append("local-v35k3")
    assert result["requiredClientProfiles"] == expected_profiles
    if expected == "client.equipment.gauge_gain_rules@1":
        assert not result["profiles"]["local-v35k3"]["compatible"]
        assert any(m["id"] == expected for m in result["profiles"]["local-v35k3"]["missing"])
    assert not result["placement"]


def test_rows_leader_during_423_reports_actual_swf_unsupported(app, actual_swf_evidence):
    cells = next(csv.reader(io.StringIO(ability(423, table="leader_ability"))))
    _, body = call(app, "/api/drafts/169985/caps/rows", body={"rows": [
        {"id": "x", "table": "leader_ability", "key": "1", "cells": cells}]})
    result = body["rows"]["x"]
    assert not result["requiredClientProfiles"] and not result["placement"]
    for profile in result["profiles"].values():
        assert any(m["rule"] == "capability.kind-unsupported" and m["status"] == "问题"
                   and m["site"]["table"] == "leader_ability" for m in profile["missing"])


def test_rows_reject_bad_requests(app):
    assert call(app, "/api/drafts/169985/caps/rows", body={"rows": [{"table": "character", "key": "1", "cells": []}]})[0] == 400
    assert call(app, "/api/drafts/169985/caps/rows", body={"rows": "x"})[0] == 400


def test_kind_catalog_per_table_and_block(app, actual_swf_evidence):
    _, during = call(app, "/api/studio/caps/kinds", {"table": ["ability"], "block": ["during_content"]})
    assert during["kinds"]["422"]["requiredClientProfiles"] == ["test-v34", "test-v35e", "local-v35k3"]
    assert not during["kinds"]["422"]["placement"]
    _, instant = call(app, "/api/studio/caps/kinds", {"table": ["ability"], "block": ["instant_content"]})
    for kind in ("419", "422", "423", "424"):
        result = instant["kinds"][kind]
        assert not result["placement"] and not result["capabilities"]
        assert result["requiredClientProfiles"] == ["test-v34", "test-v35e", "local-v35k3"]
    assert instant["kinds"]["724"]["capabilities"]
    _, leader = call(app, "/api/studio/caps/kinds", {"table": ["leader_ability"], "block": ["during_content"]})
    assert not leader["kinds"]["423"]["requiredClientProfiles"]
    assert all(any(m["rule"] == "capability.kind-unsupported" for m in profile["missing"])
               for profile in leader["kinds"]["423"]["profiles"].values())
    _, trigger = call(app, "/api/studio/caps/kinds", {"table": ["ability"], "block": ["instant_trigger"]})
    assert trigger["kinds"] == {}


def test_lookup_preserves_context_and_explicit_capability_when_combined(actual_swf_evidence, app):
    _, official = call(app, "/api/studio/caps/lookup", {
        "kind": ["423", "423"], "table": ["leader_ability"], "block": ["instant_content"]})
    assert official["requiredClientProfiles"] == ["test-v34", "test-v35e", "local-v35k3"]
    assert not official["capabilities"] and len(official["signals"]) == 1
    assert "仅检索能力目录" not in official["note"]
    _, invalid = call(app, "/api/studio/caps/lookup", {
        "kind": ["423"], "table": ["leader_ability"], "block": ["during_content"],
        "capability": ["client.kind422.dash@1"]})
    assert not invalid["requiredClientProfiles"]
    assert any(m["rule"] == "capability.kind-unsupported"
               for m in invalid["profiles"]["test-v34"]["missing"])
    assert call(app, "/api/studio/caps/lookup", {"kind": ["423"], "table": ["ability"]})[0] == 400


def test_compat_cache_distinguishes_table_and_block_with_same_capability_set(app, actual_swf_evidence):
    view = app.client_profiles
    from wf.studio.client_profile_signals import kind_site
    official = kind_site("leader_ability", "instant_content", "423")
    unsupported = kind_site("leader_ability", "during_content", "423")
    weapon = kind_site("ability_soul", "during_content", "423")
    first = view.compat([], sites=[official])
    second = view.compat([], sites=[unsupported])
    third = view.compat([], sites=[weapon])
    assert all(profile["compatible"] for profile in first.values())
    assert all(not profile["compatible"] for profile in second.values())
    assert all(profile["compatible"] for profile in third.values())
    assert view.compat([], sites=[official]) is first


def test_character_compat_reads_the_checked_in_report(app):
    _, body = call(app, "/api/studio/character-compat")
    document = json.loads(COMPAT_REPORT.read_text("utf-8"))
    snapshot = document["snapshots"][-1]
    expected = {str(c["id"]) for c in snapshot["characters"] if c["profiles"]["test-v34"]["status"] == "缺能力"}
    needs = {cid for cid, c in body["characters"].items()
             if not c["profiles"]["test-v34"]["satisfied"] and c["profiles"]["test-v35e"]["satisfied"]}
    assert body["tip"] == snapshot["tip"] and needs == expected and expected
    assert len(body["characters"]) == snapshot["character_count"]
    missing = body["characters"][sorted(needs)[0]]["profiles"]["test-v34"]["missing"]
    assert all(m["title"] and m["patches"] for m in missing)
