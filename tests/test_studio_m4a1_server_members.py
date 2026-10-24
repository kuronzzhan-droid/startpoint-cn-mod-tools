"""M2: reading mirror baselines must not turn unchanged files into delivery members."""
from copy import deepcopy
import json

import wf_quest_lib as codec
from wf.balance.rows import TABLES
from wf.text.model import SERVER_TARGETS
from test_studio_ability_text import compile_text, setup


def test_skill_attach_omits_byte_identical_mirrors_and_preserves_later_external_edits(tmp_path):
    ed, server = setup(tmp_path)
    skills = codec.parse_node(ed.source.raw[TABLES["action_skill"]])
    skills["new_skill"] = deepcopy(skills["hero"])
    ed.source.raw[TABLES["action_skill"]] = codec.build_node(skills)
    before = {target: (server / target).read_bytes() for target in SERVER_TARGETS}
    response = ed.apply("139985", {"operations": [{"op": "attach_key", "table": "action_skill",
                                   "key": "new_skill", "old_key": "hero", "slot": 0}]})
    output = compile_text(ed, server)
    assert output["servers"] == output["server_before"] == {}
    assert all(target in response["change"]["params"]["inputSha256"] for target in SERVER_TARGETS)
    for target in SERVER_TARGETS:
        intervening = json.loads(before[target])
        intervening["another_character"] = [["其它包的新文案"]]
        deployed = {target: json.dumps(intervening, ensure_ascii=False).encode("utf-8")}
        deployed.update(output["servers"])
        assert json.loads(deployed[target])["another_character"] == [["其它包的新文案"]]
        assert (server / target).read_bytes() == before[target]
