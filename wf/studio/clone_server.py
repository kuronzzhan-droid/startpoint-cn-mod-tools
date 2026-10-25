"""Complete server baselines and byte-preserving character-key merge plans."""
from pathlib import Path

import wf_character_pack as pack
from wf.boss.edit_state import merge_keys
from .clone_tables import server_entries
from .drafts import DraftError, sha256

SERVER_FILES = ("character.json", "cdndata/character.json", "cdndata/character_text.json", "mana_node.json", "mana_board.json")


def server_root(server_dir):
    root = Path(server_dir)
    if not root.is_dir():
        raise DraftError(f"Server input directory does not exist: {root}")
    root = root / "assets" if (root / "assets").is_dir() else root
    missing = [name for name in SERVER_FILES if not (root / name).is_file()]
    if missing:
        raise DraftError("Required server mirrors are missing: " + ", ".join(missing))
    return root


def server_files(client, cid, server_dir):
    root = server_root(server_dir)
    servers, before = {}, {}
    for name, additions in server_entries(client, cid).items():
        path = root / name
        raw = path.read_bytes()
        if cid in pack.load_server_json_mirror(raw, str(path)):
            raise DraftError(f"服务端目标角色已占用：{path}/{cid}")
        target = ("assets/" if root != Path(server_dir) else "") + name
        servers[target] = merge_keys(raw, additions)
        before[target] = sha256(raw)
    return servers, before


def server_plan(client, cid, server_dir):
    if server_dir is None:
        return [{"target": name, "addedKeys": [cid], "baselineVerified": False} for name in SERVER_FILES]
    servers, before = server_files(client, cid, server_dir)
    return [{"target": target, "addedKeys": [cid], "baselineVerified": True,
             "beforeSha256": before[target], "sha256": sha256(raw), "size": len(raw)}
            for target, raw in servers.items()]
