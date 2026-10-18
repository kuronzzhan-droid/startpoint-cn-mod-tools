"""Real binary fixtures for boss joins, wave semantics and leaf provenance."""
import copy
import csv
import io
import json
import zipfile
import zlib

import pytest

import wf_dsl
import wf_quest_lib as codec
from wf.boss import BossReader
from wf.boss import schema as s
from wf.boss.enemies import _level_path
from wf.boss.provenance import BossTables
from wf.view.base149 import member
from wf.view.manifest import ManifestView


def csv_row(cells):
    stream = io.StringIO(newline="")
    csv.writer(stream, lineterminator="").writerow(cells)
    return stream.getvalue()


def row(size, values):
    result = ["(None)"] * size
    for column, value in values.items():
        result[column] = str(value)
    return csv_row(result)


class Source:
    version = "test"

    def __init__(self, tables, files=None):
        self.files = {key: codec.build_node(value) for key, value in tables.items()} | (files or {})

    def raw_with_origin(self, logical):
        return self.files.get(logical), "fixture-table" if logical in self.files else None


def source():
    quest = row(130, {0: "2081001", 2: '丑王,奥格 ::quest_rank::', 5: "2000-01-01 00:00:00",
                      69: 4, 71: 501, 73: 5, 100: 1.5, 103: 1.3, 107: 80,
                      110: "org_hard", 111: "bgm"})
    boss = row(161, {0: 4, 1: "奥格", 41: "p0"})
    tree = {"layers": [{"name": "visual", "type": "tilelayer"},
                       {"name": "0", "type": "objectgroup", "objects": [
                           {"type": "CUSTOM_POSITION", "name": "p0"},
                           *[{"type": "COFFIN"} for _ in range(9)]]},
                       {"name": "1", "type": "objectgroup", "objects": []}]}
    compressor = zlib.compressobj(wbits=-15)
    encoded = compressor.compress(wf_dsl.encode_amf3(tree)) + compressor.flush()
    return Source({s.QUEST_TABLES["hard_multi"]: {"2081": {"1": quest}},
                   s.EVENT: {"2081": row(26, {2: "共同决战", 16: "coin"})},
                   s.EVENT_FOLDER_EVENTS: {"2": {"4": "13,2081,4"}},
                   s.EVENT_FOLDER: {"2": "终始之战"},
                   s.FIELD_DATA: {"org_hard": "field,battle/terrain/test,zone"},
                   s.FIELD: {"field": row(9, {0: "scene", 7: "gate", 8: "transit"})},
                   s.ZONE: {"zone": {"0": row(41, {0: 0, 2: "slime", 3: 999, 22: 0,
                                                    23: 1, 24: "org", 25: 1, 26: "org"}),
                                     "1": row(41, {0: 1, 22: 1, 23: 0, 24: "standard"})}},
                   s.GENERAL_BOSS: {"org": {"49": boss, "100": boss}},
                   s.GENERAL_ZAKO: {"slime": {"100": row(20, {0: 4})}},
                   s.STANDARD_BOSS: {"standard": {"100": "standard name,esdl/path"}},
                   s.BOSS_LEVEL: {"org": "0,hp_curve,20,1,1"},
                   s.SCORE_REWARD: {"501": {"1": "reward,1,,,,,701,0.2"}},
                   s.RARE_SCORE_REWARD: {"701": {"1": "rare,0,coin,10,1,false"}},
                   s.SHOP_CATEGORY: {"81": "org"},
                   s.SHOP: {"product": row(50, {0: 81, 17: "coin", 18: 10,
                                               32: 4, 33: 900, 34: 1})},
                   s.EQUIPMENT: {"900": "weapon"}},
                  {"battle/terrain/test.amf3.deflate": encoded})


def test_complete_quest_joins_and_actual_wave_count():
    reader = BossReader(source())
    document = reader.show("2081001")
    quest = document["quest"]
    assert quest["name"] == "丑王,奥格"
    assert quest["fields"]["restriction"] == "4"
    assert quest["fields"]["recommended_element"] == "5"
    assert document["terrain"]["wave_count"] == 2
    assert document["terrain"]["waves"][0]["coffin_count"] == 9
    assert document["entrance"]["event_folder"][0]["path"] == ["2"]
    assert document["rewards"]["rare_score_reward"][0]["path"] == ["701", "1"]
    assert document["shops"][0]["weapons"][0]["equipment"]["row"] == ["weapon"]
    bosses = [enemy for enemy in document["enemies"] if enemy["code"] == "org"]
    assert [enemy["mode"] for enemy in bosses] == ["single", "multi"]
    assert bosses[0]["path"] == ["org", "100"]
    slime = next(enemy for enemy in document["enemies"] if enemy["kind"] == "zako")
    assert slime["level"] == 80 and slime["spawn_interval"] == "999"
    assert slime["path"] == ["slime", "100"]
    assert next(enemy for enemy in document["enemies"] if enemy["code"] == "standard")["element"] is None
    assert quest["source"]["scope"] == "table" and quest["source"]["layer"] is None
    # Returned documents cannot mutate later answers or cached table rows.
    document["quest"]["row"][2] = "changed"
    assert reader.show("2081001")["quest"]["row"][2].startswith("丑王")


def test_practice_id_is_leaf_key_and_ambiguous_ids_require_kind():
    original = source()
    practice = row(127, {0: 92, 2: "dummy", 107: 80, 110: "org_hard"})
    original.files[s.QUEST_TABLES["practice"]] = codec.build_node({"2081001": practice, "2": practice})
    reader = BossReader(original)
    with pytest.raises(ValueError, match="不唯一"):
        reader.find("2081001")
    assert reader.find("practice:2081001")["native_id"] == "92"
    assert reader.find("practice:2")["id"] == "2"
    assert len(reader.list()["groups"]) == 2


def test_native_level_band_order_and_missing_band():
    assert _level_path({"boss": {"100": "", "49": ""}}, "boss", 10) == ["boss", "100"]
    assert _level_path({"boss": {"80": ""}}, "boss", 100) is None


def test_missing_references_are_explicit_not_empty_success():
    original = source()
    del original.files[s.FIELD_DATA]
    result = BossReader(original).show("2081001")
    assert result["field_data"]["missing"] and result["zone"]["missing"]
    assert result["terrain"]["missing"] and result["terrain"]["wave_count"] is None


def test_leaf_origin_tracks_changed_leaf_not_latest_container(tmp_path, monkeypatch):
    profile = tmp_path / "profile.json"
    profile.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("WF_PATHS_PROFILE", str(profile))
    store, active = tmp_path / "store", tmp_path / "active"
    store.mkdir(); active.mkdir()
    logical = s.QUEST_TABLES["hard_multi"]
    original = {"2081": {"1": "quest,old"}, "2082": {"1": "other,old"}}
    target = store / member(logical).removeprefix("production/upload/")
    target.parent.mkdir(); target.write_bytes(codec.build_node(original))
    edges = []
    for number, tree in enumerate([{"2081": {"1": "quest,new"}, "2082": {"1": "other,old"}},
                                   {"2081": {"1": '"quest",new\n'}, "2082": {"1": "other,new"}}], 132):
        name = f"pinball-1.4.{number-1}-1.4.{number}-1-test.zip"
        with zipfile.ZipFile(active / name, "w") as package:
            package.writestr(member(logical), codec.build_node(tree))
        edges.append({"version": f"1.4.{number}", "depends_on": f"1.4.{number-1}",
                      "archive": name, "enabled": True})
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"patches": edges}), encoding="utf-8")
    view = ManifestView("1.4.133", store=store, manifest=manifest, search_dirs=[], manifests=[])
    tables = BossTables(view)
    origin = tables.citation(logical, ["2081", "1"])
    assert "131-1.4.132" in origin["layer"]
    assert "132-1.4.133" in origin["table_layer"]
    assert "132-1.4.133" in tables.citation(logical, ["2082", "1"])["layer"]
    assert view.verify()["store_members"]
