"""Warning explanations retain full differences and reject stale historical data."""
import json
from pathlib import Path

import wf_quest_lib as codec
from wf.text import TextWorkspace
from wf.text.audit import explain_warnings
from wf.text.model import ACTION_SKILL, CHARACTER, CHARACTER_TEXT, replace_cells


def test_audit_keeps_difference_beyond_legacy_120_character_excerpt(tmp_path):
    mirror, game = "相同内容" * 31 + "旧倍率", "相同内容" * 31 + "新倍率"
    character = ["wolf"] + [""] * 24
    character[8] = "wolf"
    text = [""] * 12
    text[5] = mirror
    tables = {CHARACTER: {"1": replace_cells("", character)},
              CHARACTER_TEXT: {"1": replace_cells("", text)},
              ACTION_SKILL: {"wolf": {"1": replace_cells("", ["技能", game])}}}
    class View:
        def read_raw(self, logical):
            return codec.build_node(tables[logical]), "fixture"
    warning = {"level": "WARN", "check": "text", "fid": "text.drift:客户端 character_text 表:1:1:技能描述",
               "msg": "不同步", "detail": ["此处: " + mirror[:120], "游戏: " + game[:120]]}
    log = tmp_path / "prepush.json"
    log.write_text(json.dumps({"findings": [warning], "since": "1.4.1"}, ensure_ascii=False), "utf-8")
    result = explain_warnings(log, TextWorkspace(View()), {})
    entry = result["entries"][0]
    assert result["historical_matches"] == 1
    assert entry["state"] == "问题"
    assert entry["mirror_text"] == mirror and entry["action_skill_text"] == game
    assert {"mirror": "旧", "action_skill": "新"} in entry["differences"]
    warning["detail"][0] = "历史值已变"
    log.write_text(json.dumps({"findings": [warning]}, ensure_ascii=False), "utf-8")
    result = explain_warnings(log, TextWorkspace(View()), {})
    assert result["entries"][0]["state"] == "待验证"
    assert result["historical_matches"] == 0


def test_all_78_historical_warnings_remain_individually_auditable():
    path = Path(__file__).resolve().parents[1] / "docs/m1/text-warnings.json"
    report = json.loads(path.read_text("utf-8"))
    assert report["warning_count"] == report["historical_matches"] == 78
    entries = report["entries"]
    assert len({e["fid"] for e in entries}) == len(entries) == 78
    assert all(e["state"] == "问题" and e["differences"] for e in entries)
    assert all(len(e["source_sha256"]) == len(e["action_skill_sha256"]) == 64 for e in entries)
    tokens = [e for e in entries if e["category"] == "客户端描述为内部标识符"]
    assert len(tokens) == 2
    assert all(e["character_id"] == "700007" and e["action_skill_text"] == "ruin_lady_no_piercing" for e in tokens)
