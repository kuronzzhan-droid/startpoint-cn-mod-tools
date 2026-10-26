"""ID evidence from real native shapes, replay requests and encoded payloads."""
import hashlib
import json
import zlib

import pytest
import wf_quest_lib as codec
from wf.studio.drafts import DraftError
from wf.studio.id_catalog import CHARACTER, MANA, TABLES
from wf.studio.ids import check_id


class Source:
    version = "1.4.282"

    def __init__(self, tables=None):
        self.tables = tables or {}

    def raw(self, logical):
        return codec.build_node(self.tables[logical]) if logical in self.tables else None


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_nested_native_status_owns_outer_character_not_level(tmp_path):
    source = Source({TABLES["character"][1]: {"199000": {"1": {"100": "1,2"}}}})
    assert not check_id(source, "character", "199000", drafts_root=tmp_path)["available"]
    assert check_id(source, "character", "100", drafts_root=tmp_path)["available"]


def test_mana_segment_does_not_include_neighboring_odd_prefix(tmp_path):
    source = Source({MANA: {"7": {"1": {"1": "398001001,x,1,1,0,x,x"}}}})
    assert check_id(source, "mana_node", "199000", drafts_root=tmp_path)["available"]
    server = tmp_path / "mirror"
    write(server / "mana_node.json", {"8": {"1": {"398000999": {}}}})
    result = check_id(source, "mana_node", "199000", drafts_root=tmp_path / "drafts", server_dir=server)
    assert not result["available"] and result["owners"][0]["owner"] == "8"


def test_server_awakening_nested_maps_and_foreign_shop_owner(tmp_path):
    write(tmp_path / "assets/equipment_awakening_material.json",
          {"materialByEquipment": {"5950001": 10000301}, "rarityOverrides": {"5950002": 5}})
    write(tmp_path / "assets/equipment_enhancement_shop.json", {"101": {"equipmentId": 5950003}})
    for identity in ("5950001", "5950002", "5950003"):
        assert not check_id(Source(), "weapon", identity, drafts_root=tmp_path / "drafts", server_dir=tmp_path)["available"]


@pytest.mark.parametrize("encoding", ["stored", "deflate"])
def test_draft_table_payload_supports_encoding_and_hash_checks(tmp_path, encoding):
    raw = codec.build_node({"1990011": "ball"})
    if encoding == "deflate":
        encoder = zlib.compressobj(wbits=-15)
        raw = encoder.compress(raw) + encoder.flush()
    folder = tmp_path / "199001"
    payload = folder / "balls.bin"
    write(folder / "changeset.json", {"characterId": "199001", "changes": [{"files": [{
        "logical": TABLES["multiball"][0], "draft": payload.name, "encoding": encoding,
        "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}]}]})
    payload.write_bytes(raw)
    assert not check_id(Source(), "multiball", "1990011", drafts_root=tmp_path)["available"]
    payload.write_bytes(b"wrong")
    with pytest.raises(DraftError, match="SHA-256"):
        check_id(Source(), "multiball", "1990011", drafts_root=tmp_path)


def test_empty_draft_top_level_reservations_and_server_node_payload(tmp_path):
    write(tmp_path / "scratch-a/changeset.json", {"characterId": "scratch-a", "changes": [],
          "reservations": {"string_id": ["empty_draft_key"]}})
    folder = tmp_path / "boss/quest"
    write(folder / "changeset.json", {"characterId": "quest", "subjectKind": "boss",
          "changes": [{"files": [{"logical": "assets/mana_node.json", "draft": "nodes.json"}]}]})
    write(folder / "nodes.json", {"7": {"1": {"398000001": {}}}})
    assert not check_id(Source(), "string_id", "empty_draft_key", drafts_root=tmp_path)["available"]
    assert not check_id(Source(), "mana_node", "199000", drafts_root=tmp_path)["available"]


@pytest.mark.parametrize("namespace,code", [("boss/quest", None), ("weapons/5950001", "new_soul")])
def test_weapon_replay_reserves_generated_strings_without_files(tmp_path, namespace, code):
    source = Source({TABLES["string_id"][0]: {"awakening_material_5910001": "10000301"}})
    spec = {"id": "5950001", "sourceWeapon": "5910001",
            "soul_template": {"template": "pf_hit_invoke_damage"}}
    if code:
        spec["code"] = code
    write(tmp_path / namespace / "changeset.json", {"characterId": "5950001", "subjectKind": "weapon",
          "changes": [{"files": [], "params": {"requests": [{"operation": "weapon_clone", "weapon": spec}]}}]})
    for key in ((code or "boss_workshop_5950001") + "_pf_damage", "awakening_material_5950001"):
        assert not check_id(source, "string_id", key, drafts_root=tmp_path)["available"]


def test_ability_text_replay_reserves_created_override(tmp_path):
    write(tmp_path / "199000/changeset.json", {"characterId": "199000", "changes": [{"files": [],
          "params": {"requests": [{"text": {"desc_override": {"desc_override_new": {"old": None, "new": "文案"}}}}]}}]})
    assert not check_id(Source(), "string_id", "desc_override_new", drafts_root=tmp_path)["available"]
