"""No local data: source attribution and multiplayer-result round trips."""
from copy import deepcopy

import pytest

from wf.studio.translation import glossary_attribution, annotate_panel
from wf.studio import device_result
from test_studio_device_result import make_delivery, record


@pytest.mark.parametrize("entry,source,uncertain", [
    ({"official": None}, "直译", True),
    ({"official": "火", "officialTemplate": "火", "officialKey": "element", "mappingStatus": "as3"}, "官方原文", False),
    ({"official": "火", "officialTemplate": "火", "officialKey": "element", "mappingStatus": "guess"}, "官方原文", True),
    ({"official": "第2名角色", "officialTemplate": "第::index::名角色", "officialKey": "target", "mappingStatus": "as3"}, "ui_string 拼接", False),
    ({"official": "造成…伤害", "officialTemplate": "造成::amount::伤害", "officialKey": "damage", "mappingStatus": "as3"}, "ui_string 拼接", True),
])
def test_translation_categories(entry, source, uncertain):
    result = glossary_attribution({**entry, "officialBaselineMatch": True})
    assert (result["source"], result["uncertain"]) == (source, uncertain)


def test_text_original_requires_actual_official_match():
    class Source:
        def table(self, name, official=False):
            assert official
            if name == "character":
                return {"1": [[""] * 8 + ["s"]]}
            return {"s": {"1": [["技能", "官方说明"]]}}
    field = {"surface": "action_skill", "key": "s", "tier": "1", "field": "c1",
             "location": "action_skill.1.c1", "value": "官方说明", "original": "官方说明"}
    panel = {"characterId": "1", "fields": [field]}
    assert annotate_panel(Source(), panel)["fields"][0]["translation"]["source"] == "官方原文"
    field["value"] = "我改的说明"
    result = annotate_panel(Source(), panel)["fields"][0]["translation"]
    assert result["source"] == "人工" and not result["uncertain"]
    field["original"] = field["value"]
    assert annotate_panel(Source(), panel)["fields"][0]["translation"]["uncertain"]
    assert "translation" not in field


def test_three_client_record_write_read_import_summary_and_legacy(tmp_path):
    folder = make_delivery(tmp_path / "source")
    payload = record(testType="三开联机")
    written = device_result.write(folder, "boss", payload)
    entry = device_result.read(folder, "boss")
    assert entry["result"]["testType"] == "三开联机"
    assert device_result.summary(entry)["testType"] == "三开联机"
    target = make_delivery(tmp_path / "target")
    imported = device_result.import_file(folder, target, "boss")
    assert imported["testType"] == "三开联机"
    bad = deepcopy(written); bad["testType"] = "已证明同步"
    assert device_result.schema_errors(bad)
    old = record(); old["schema"] = device_result.SCHEMA_ID
    assert "testType" not in device_result.normalize(old)[0]
