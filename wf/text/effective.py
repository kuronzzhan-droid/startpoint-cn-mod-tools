"""Compare the actual key-level server overlay with client skill text cells."""
from __future__ import annotations

from .model import RANK_TARGET, SERVER_TARGET, SERVER_TARGETS

DESCRIPTION_COLUMNS = (5, 7, 9)


def effective_rows(base_rows, rank_rows):
    """content-master.ts spreads maps: rank replaces the complete character row."""
    return (rank_rows, RANK_TARGET) if rank_rows is not None else (base_rows, SERVER_TARGET)


def compare_effective(cid, client_columns, base_rows, rank_rows, provided):
    location = f"server_effective.{cid}"
    common = {"rule": "text.server_effective", "location": location,
              "source": "content-master.ts: cdnCharacterTexts = {...base, ...rankP5b}",
              "evidence_nature": "源码推断"}
    missing = sorted(set(SERVER_TARGETS) - set(provided))
    if missing:
        return [{**common, "state": "待验证", "message": "缺少完整镜像，未判定服务端实际生效文本",
                 "evidence": {"missing_sources": missing}}]
    rows, target = effective_rows(base_rows, rank_rows)
    if rows is not None and (not isinstance(rows, list) or not rows or not isinstance(rows[0], list)):
        raise ValueError(f"malformed effective server mirror: {target}:{cid}")
    results = []
    for column in DESCRIPTION_COLUMNS:
        client = client_columns.get(str(column))
        server = rows[0][column] if rows and len(rows[0]) > column else None
        # A nonexistent tier on both sides has no text to compare.
        if not client and not server:
            continue
        if client is not None and not isinstance(client, str) or server is not None and not isinstance(server, str):
            raise ValueError(f"non-string skill description: {cid}:c{column}")
        same = client == server
        results.append({**common, "location": f"{location}.c{column}",
            "state": "满足" if same else "问题",
            "message": "生效服务端文本与客户端一致" if same else "生效服务端技能文本与客户端不一致",
            "evidence": {"text": server or "", "matches": [] if same else ["客户端与生效服务端文本不同"],
                         "client_text": client, "server_text": server, "column": column,
                         "effective_source": target, "rank_overrides_base": rank_rows is not None}})
    return results


def compare_document(document):
    if not document.get("character_text"):
        return []
    return compare_effective(document["character_id"], document["character_text"],
        document.get("server_character_text"), document.get("server_character_text_rank_p5b"),
        document.get("sources", {}))
