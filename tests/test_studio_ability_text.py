"""Text and skill tiers cannot bypass wf text or either server mirror."""
from copy import deepcopy
import json

import pytest

import wf_quest_lib as codec
from wf.balance.rows import TABLES, join_leaf, split_leaf
from wf.studio.ability import AbilityEditor, compile_ability_operations
from wf.studio.drafts import DraftError, DraftStore
from wf.text.model import CHARACTER, CHARACTER_TEXT, CUSTOM, SERVER_TARGETS
from test_studio_ability import Source, full


def setup(tmp_path, *, shared=False):
    source = Source(shared=shared)
    text = ["英雄", "LANG", "角色介绍", "白狼骑士", "斩击", "攻击敌人", "斩击+", "攻击敌人", "斩击++", "攻击敌人", "队长", "声优"]
    characters = codec.parse_node(source.raw[CHARACTER])
    source.raw[CHARACTER_TEXT] = codec.build_node({cid: join_leaf("\r\n", [text]) for cid in characters})
    source.raw[CUSTOM] = codec.build_node({"desc_override_first": "自身攻击力提升"})
    server = tmp_path / "server"
    for target in SERVER_TARGETS:
        path = server / target
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({cid: [text] for cid in characters}, ensure_ascii=False, indent=2), "utf-8")
    ed = AbilityEditor(source, store=DraftStore(tmp_path / "draft"), server_dir=server)
    return ed, server


def text_operations(value="对敌人造成伤害", *, shared_ok=False):
    return [{"op": "set_cells", "table": "action_skill", "key": "hero", "level": str(i),
             "row": 0, "row_count": 1, "shared_ok": shared_ok,
             "cells": [{"column": "c1", "old": "攻击敌人", "new": value}]} for i in (1, 2, 3)]


def compile_text(ed, server):
    return compile_ability_operations(ed.source, ed.store, ed.store.load("139985"), server)


def test_visible_columns_synchronize_client_and_both_mirrors(tmp_path):
    ed, server = setup(tmp_path)
    old = {target: (server / target).read_bytes() for target in SERVER_TARGETS}
    ed.apply("139985", {"operations": text_operations()})
    result = compile_text(ed, server)
    client = split_leaf(codec.parse_node(result["client"][CHARACTER_TEXT])["139985"], "character_text")[0]
    assert [client[c] for c in (5, 7, 9)] == ["对敌人造成伤害"] * 3
    for target in SERVER_TARGETS:
        row = json.loads(result["servers"][target])["139985"][0]
        assert row == client
        assert (server / target).read_bytes() == old[target]
    assert set(result["server_before"]) == set(SERVER_TARGETS)
    assert "\r\n" in codec.parse_node(result["client"][TABLES["action_skill"]])["hero"]["1"]


def test_visible_text_rules_missing_mirror_partial_tiers_and_misbound_key(tmp_path):
    ed, server = setup(tmp_path)
    for request, match in [({"operations": text_operations("生命值100%以下时攻击力提升")}, "text rules"),
                           ({"operations": text_operations()[:1]}, "every existing"),
                           ({"operations": [{**op, "key": "other"} for op in text_operations()]}, "not an owner")]:
        with pytest.raises(DraftError, match=match):
            ed.apply("139985", request)
        assert ed.store.load("139985") is None
    (server / SERVER_TARGETS[1]).unlink()
    with pytest.raises(DraftError):
        ed.apply("139985", {"operations": text_operations()})
    assert ed.store.load("139985") is None


def test_shared_visible_skill_requires_opt_in_and_updates_all_owners(tmp_path):
    ed, server = setup(tmp_path, shared=True)
    with pytest.raises(DraftError, match="owners=.*shared_ok"):
        ed.apply("139985", {"operations": text_operations()})
    ed.apply("139985", {"operations": text_operations(shared_ok=True)})
    result = compile_text(ed, server)
    for target in SERVER_TARGETS:
        document = json.loads(result["servers"][target])
        assert document["139985"][0][5] == document["100"][0][5] == "对敌人造成伤害"


def test_mirror_drift_and_foreign_draft_identity_rejected(tmp_path):
    ed, server = setup(tmp_path)
    ed.apply("139985", {"operations": text_operations()})
    target = server / SERVER_TARGETS[1]
    target.write_text(target.read_text("utf-8") + "\n", "utf-8")
    with pytest.raises(ValueError, match="输入已变化"):
        compile_text(ed, server)
    source_version = ed.source.version
    ed.source.version = "1.4.234"
    with pytest.raises(DraftError, match="baseView"):
        ed.read("139985")
    ed.source.version = source_version
    draft = ed.store.load("139985")
    draft["code"] = "wrong"
    with pytest.raises(ValueError, match="code"):
        compile_ability_operations(ed.source, ed.store, draft, server)


def test_skill_tier_delete_insert_move_preserves_one_row_per_tier(tmp_path):
    ed, server = setup(tmp_path)
    rows = [["斩击" + "+" * (i - 1), "攻击敌人", "100"] for i in (1, 2, 3)]
    delete = {"op": "delete_row", "table": "action_skill", "key": "hero", "level": "2",
              "row": 0, "row_count": 3, "cells": full(rows[1], "delete_row")}
    ed.apply("139985", {"operations": [delete]})
    removed = compile_text(ed, server)
    assert json.loads(removed["servers"][SERVER_TARGETS[0]])["139985"][0][8:10] == ["", ""]
    preview = ed.row_preview("139985", "action_skill", "hero", level="3")
    assert preview["before"]["cells"] == rows[2] and preview["after"]["cells"] is None
    new = ["斩击+", "攻击敌人", "150"]
    insert = {**delete, "op": "insert_row", "row_count": 2, "cells": full(new, "insert_row")}
    ed.apply("139985", {"operations": [insert]})
    move = {**delete, "op": "move_row", "to_row": 2, "cells": full(new, "move_row")}
    ed.apply("139985", {"operations": [move]})
    result = compile_text(ed, server)
    table = codec.parse_node(result["client"][TABLES["action_skill"]])["hero"]
    assert set(table) == {"1", "2", "3"}
    assert [split_leaf(table[level], "action_skill")[0] for level in ("1", "2", "3")] == [rows[0], rows[2], new]
    assert all(len(split_leaf(leaf, "action_skill")) == 1 for leaf in table.values())
    snapshot = deepcopy(ed.store.load("139985"))
    with pytest.raises(DraftError, match="三档上限"):
        ed.apply("139985", {"operations": [{**insert, "row_count": 3}]})
    assert ed.store.load("139985") == snapshot


def test_text_request_cannot_edit_previous_key_after_attach(tmp_path):
    ed, server = setup(tmp_path)
    skill = codec.parse_node(ed.source.raw[TABLES["action_skill"]])
    skill["new_skill"] = deepcopy(skill["hero"])
    ed.source.raw[TABLES["action_skill"]] = codec.build_node(skill)
    request = {"operations": [
        {"op": "attach_key", "table": "action_skill", "key": "new_skill", "old_key": "hero", "slot": 0},
        *text_operations()]}
    with pytest.raises(DraftError, match="key.*不同"):
        ed.apply("139985", request)
    assert ed.store.load("139985") is None


@pytest.mark.parametrize("levels,match", [
    ({"2": [full(["技能", "攻击敌人", "100"], "insert_row")]}, "contiguous"),
    ({"1": [full(["技能", "攻击敌人", "100"], "insert_row")] * 2}, "单行"),
    ({"1": [full(["技能", "攻击敌人"], "insert_row")]}, "列数"),
])
def test_new_skill_key_rejects_missing_tier_multiline_and_truncated_row(tmp_path, levels, match):
    ed, _ = setup(tmp_path)
    request = {"operations": [{"op": "attach_key", "table": "action_skill", "slot": 0,
                               "key": "new_skill", "old_key": "hero", "levels": levels}]}
    with pytest.raises(DraftError, match=match):
        ed.apply("139985", request)
    assert ed.store.load("139985") is None
