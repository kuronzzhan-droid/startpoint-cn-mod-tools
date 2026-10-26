import json
from types import SimpleNamespace

import pytest
import wf_quest_lib as codec
from wf.boss.shop_model import ENH_SHOP
from wf.studio.drafts import DraftError, DraftStore
from wf.studio.id_catalog import CHARACTER, MANA, TABLES
from wf.studio.ids import check_id, next_id
from wf.studio.versions import next_version


class Source:
    version = "1.4.282"

    def __init__(self, tables=None):
        self.tables = tables or {}

    def raw(self, logical):
        return codec.build_node(self.tables[logical]) if logical in self.tables else None


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


@pytest.mark.parametrize("kind", tuple(TABLES))
def test_all_kinds_use_current_view_keys_and_report_sources(tmp_path, kind):
    value = "key" if kind in {"string_id", "power_flip_action"} else "199000"
    source = Source({TABLES[kind][0]: {value: "native"}})
    result = check_id(source, kind, value, drafts_root=tmp_path)
    assert not result["available"] and result["owners"][0]["source"] == "view"
    assert next_id(source, kind, value, drafts_root=tmp_path)["id"] != value


def test_check_merges_view_server_and_all_draft_namespaces(tmp_path):
    source = Source({CHARACTER: {"199000": "donor"}})
    server, drafts = tmp_path / "server", tmp_path / "drafts"
    write(server / "assets/character.json", {"199000": {}})
    write(drafts / "199000/changeset.json", {"characterId": "199000", "changes": []})
    result = check_id(source, "character", "199000", drafts_root=drafts, server_dir=server)
    assert {e["source"] for e in result["owners"]} == {"view", "server", "draft"}
    for namespace, wid in (("boss/quest", "5950001"), ("weapons/5950002", "5950002")):
        write(drafts / namespace / "changeset.json", {"subjectKind": "boss", "characterId": "quest",
              "changes": [{"params": {"requests": [{"operation": "weapon_clone", "weapon": {
                  "id": wid, "enhancementProducts": [str(int(wid) * 100 + 1)]}}]}}]})
    assert next_id(source, "weapon", "5950001", drafts_root=drafts, server_dir=server)["id"] == "5950003"
    assert not check_id(source, "soul_item", "5950001", drafts_root=drafts)["available"]
    assert not check_id(source, "enhancement_shop", "595000201", drafts_root=drafts)["available"]


def test_mana_segment_detects_foreign_owner_and_reports_full_range(tmp_path):
    source = Source({MANA: {"7": {"1": {"1": "398000001,x,1,1,0,x,x"}}}})
    result = check_id(source, "mana_node", "199000", drafts_root=tmp_path)
    assert result["owners"][0]["owner"] == "7" and not result["available"]
    assert result["segment"] == {"characterId": "199000", "start": "398000000", "end": "398000999"}


def test_native_enhancement_stage_reserves_weapon_parent(tmp_path):
    source = Source({ENH_SHOP: {"595000177": "stage"}})
    assert next_id(source, "weapon", "5950001", drafts_root=tmp_path)["id"] == "5950002"


def test_draft_declared_table_payload_reserves_multiball_and_string(tmp_path):
    folder = tmp_path / "199001"
    logical = TABLES["multiball"][0]
    write(folder / "changeset.json", {"characterId": "199001", "changes": [{
        "params": {"reservations": {"string_id": ["new_text"]}},
        "files": [{"logical": logical, "draft": "files/balls.bin"}]}]})
    (folder / "files").mkdir()
    (folder / "files/balls.bin").write_bytes(codec.build_node({"1990011": "ball"}))
    assert not check_id(Source(), "multiball", "1990011", drafts_root=tmp_path)["available"]
    assert not check_id(Source(), "string_id", "new_text", drafts_root=tmp_path)["available"]


def test_corrupt_reservation_sources_fail_instead_of_returning_free(tmp_path):
    write(tmp_path / "1/changeset.json", {})
    with pytest.raises(DraftError, match="结构无效"):
        next_id(Source(), "character", drafts_root=tmp_path)
    with pytest.raises(DraftError, match="目录不存在"):
        check_id(Source(), "character", "1", drafts_root=tmp_path / "absent", server_dir=tmp_path / "missing")


@pytest.mark.parametrize("kind,identity", [("weapon", "21474836"), ("mana_node", "1073742"),
                                          ("character", "01"), ("string_id", "../oops"), ("bad", "1")])
def test_id_invalid_input_is_rejected(kind, identity, tmp_path):
    with pytest.raises(DraftError):
        check_id(Source(), kind, identity, drafts_root=tmp_path)


def test_next_versions_skip_reservations_and_do_not_write(tmp_path):
    filename = tmp_path / "versions.json"
    reservations = {f"1.4.{p}": {"purpose": "深渊之兽", "owner": "fixture", "date": "2026-10-25"}
                    for p in (283, 284)}
    write(filename, reservations)
    before = filename.read_bytes()
    result = next_version(Source(), view_name="test175", reservations_file=filename)
    assert result["next"] == "1.4.285" and len(result["skipped"]) == 2
    assert result["view"] == "test175" and result["reserved"] is False
    assert filename.read_bytes() == before
    reservations["1.4.283"]["date"] = "2026-02-30"
    write(filename, reservations)
    with pytest.raises(DraftError, match="登记无效"):
        next_version(Source(), reservations_file=filename)


def test_discovery_routes_use_configured_mirror_and_reject_duplicate_params(tmp_path):
    from wf.studio.discovery_commands import DiscoveryRoutes
    app = SimpleNamespace(source=Source(), ops=SimpleNamespace(store=DraftStore(tmp_path / "drafts")))
    routes = DiscoveryRoutes(app)
    response = routes.check({"kind": ["character"], "id": ["199000"]})
    assert response.status == 200 and json.loads(response.body)["available"]
    assert len(routes.routes()) == 3
    with pytest.raises(DraftError):
        routes.check({"kind": ["character", "weapon"], "id": ["1"]})
