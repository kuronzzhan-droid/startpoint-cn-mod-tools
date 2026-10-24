"""L6: changing a leader key must expose the separate display-name fields."""
import wf_quest_lib as codec
from wf.balance.ownership import CHARACTER
from wf.balance.rows import TABLES, split_leaf
from test_studio_ability import compiled, editor


def test_attach_leader_warns_about_both_name_columns_without_changing_them(tmp_path):
    ed = editor(tmp_path)
    leaders = codec.parse_node(ed.source.raw[TABLES["leader_ability"]])
    leaders["new_leader"] = leaders["100"]
    ed.source.raw[TABLES["leader_ability"]] = codec.build_node(leaders)
    old_name = split_leaf(ed.source.tables[CHARACTER]["139985"], "character")[0][18]
    response = ed.apply("139985", {"operations": [{"op": "attach_key", "table": "leader_ability",
                        "slot": 0, "key": "new_leader", "old_key": "100"}]})
    check = next(c for c in response["checks"] if c["rule"] == "ability.leader-name-sync")
    assert check["status"] == "待验证"
    assert "character c18" in check["message"] and "character_text c10" in check["message"]
    assert check["targets"] == [{"table": "character", "key": "139985", "column": 18},
                                {"table": "character_text", "key": "139985", "column": 10}]
    output = compiled(ed)
    row = split_leaf(codec.parse_node(output["client"][CHARACTER])["139985"], "character")[0]
    assert row[17] == "new_leader" and row[18] == old_name
    assert set(output["client"]) == {CHARACTER}
    assert any(c["code"] == "ability.leader-name-sync" for c in response["change"]["checks"])
