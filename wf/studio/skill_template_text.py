"""Keep the skill rows, client text and existing server mirrors consistent."""
import json
from pathlib import Path

import wf_quest_lib as codec
from wf.balance.rows import split_leaf, join_leaf
from wf.boss.edit_state import merge_keys
from wf.text.edit import _encode
from .drafts import DraftError, sha256

TEXT = "master/character/character_text.orderedmap"
CHAR = "master/character/character.orderedmap"


def client_text(inputs, cid, skills):
    raw = inputs.require(TEXT)
    table = codec.parse_node(raw)
    if cid not in table:
        raise DraftError("技能模板缺少角色文案行")
    rows = split_leaf(table[cid], "character_text")
    if len(rows) != 1 or len(rows[0]) < 10:
        raise DraftError("角色文案行不足 c0..c9")
    for level, text in skills.items():
        if int(level) not in (1, 2, 3):
            raise DraftError("技能文案镜像仅支持原生 1..3 档位")
        skill = split_leaf(text, "action_skill")[0]
        rows[0][2 + 2 * int(level):4 + 2 * int(level)] = skill[:2]
    return _encode(raw, table, {**table, cid: join_leaf(table[cid], rows)})


def server_mirrors(members, cid, server_dir, servers, before):
    if server_dir is None:
        raise DraftError("技能模板交付需要 server_dir 核对角色与两层文案镜像")
    root = Path(server_dir)
    prefix = "assets/" if (root / "assets").is_dir() else ""
    for name, logical in (("cdndata/character.json", CHAR), ("cdndata/character_text.json", TEXT),
                          ("cdndata/character_text_rank_p5b.json", TEXT)):
        target = prefix + name
        path = root / target
        if not path.is_file():
            raise DraftError("技能模板缺少服务端镜像基线：" + target)
        raw = path.read_bytes()
        current = servers.get(target, raw)
        document = json.loads(current)
        if not isinstance(document, dict):
            raise DraftError("服务端镜像必须是对象：" + target)
        row = split_leaf(codec.parse_node(members["common", logical])[cid], logical)
        servers[target] = merge_keys(current, {cid: row})
        before.setdefault(target, sha256(raw))
