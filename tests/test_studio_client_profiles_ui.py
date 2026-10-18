"""编辑台「目标客户端」只读胶水：档案说明、按标记/行/程序/kind 查能力、全角色兼容报告。"""
from __future__ import annotations

import json

import pytest

from test_m1_balance import valid_row
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
    return StudioApp(_Source())


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
    assert kind["requiredClientProfiles"] == ["test-v34", "test-v35e"]
    _, hidden = call(app, "/api/studio/caps/lookup", {"unique": [HIDDEN]})
    assert {"client.direct.base@1", "client.wfx.hidden_unique_icons@1"} <= {c["id"] for c in hidden["capabilities"]}
    assert hidden["requiredClientProfiles"] == ["test-v35e"]
    missing = {m["id"]: m for m in hidden["profiles"]["test-v34"]["missing"]}
    assert missing["client.direct.base@1"]["patches"] == [112, 113, 124, 130]
    assert missing["client.wfx.hidden_unique_icons@1"]["missingPatches"] == [131]
    _, custom = call(app, "/api/studio/caps/lookup", {"customKey": ["wfx_pf4_139990"]})
    assert custom["requiredClientProfiles"] == ["test-v35e"]
    _, explicit = call(app, "/api/studio/caps/lookup", {"capability": ["client.direct.base@1"]})
    assert [c["id"] for c in explicit["capabilities"]] == ["client.direct.base@1"]
    assert explicit["requiredClientProfiles"] == ["test-v35e"]


def test_lookup_rejects_empty_and_unknown_capability(app):
    assert call(app, "/api/studio/caps/lookup")[0] == 400
    assert call(app, "/api/studio/caps/lookup", {"capability": ["client.nope@1"]})[0] == 400


def test_unknown_wfx_marker_is_never_compatible(app):
    _, body = call(app, "/api/studio/caps/lookup", {"unique": ["wfx:999:0:1:0:x"]})
    assert body["unsupported"] and not body["recognized"] and body["requiredClientProfiles"] == []


def test_rows_follow_unique_reference_to_v35e_string(app):
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


def test_rows_report_kind_placement_from_requires_derivation(app):
    row = valid_row("misplaced")
    row[col("ability", "instant_content", "kind")] = "422"
    _, body = call(app, "/api/drafts/169985/caps/rows", body={"rows": [{"id": "x", "table": "ability", "key": "1", "cells": row}]})
    assert "allowed_blocks" in body["rows"]["x"]["placement"][0]


def test_rows_reject_bad_requests(app):
    assert call(app, "/api/drafts/169985/caps/rows", body={"rows": [{"table": "character", "key": "1", "cells": []}]})[0] == 400
    assert call(app, "/api/drafts/169985/caps/rows", body={"rows": "x"})[0] == 400


def test_kind_catalog_per_table_and_block(app):
    _, during = call(app, "/api/studio/caps/kinds", {"table": ["ability"], "block": ["during_content"]})
    assert during["kinds"]["422"]["requiredClientProfiles"] == ["test-v34", "test-v35e"]
    assert not during["kinds"]["422"]["placement"]
    _, instant = call(app, "/api/studio/caps/kinds", {"table": ["ability"], "block": ["instant_content"]})
    assert instant["kinds"]["422"]["placement"] and instant["kinds"]["724"]["capabilities"]
    _, trigger = call(app, "/api/studio/caps/kinds", {"table": ["ability"], "block": ["instant_trigger"]})
    assert trigger["kinds"] == {}


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
