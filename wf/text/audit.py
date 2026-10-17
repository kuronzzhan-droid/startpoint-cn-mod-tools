"""Explain every prepush text warning against complete, hashed input values."""
from __future__ import annotations

from collections import Counter
from difflib import SequenceMatcher
import json
import re
from pathlib import Path

from .model import ACTION_SKILL, CHARACTER, CHARACTER_TEXT, TextWorkspace, cells, sha256


def _differences(mirror: str, game: str) -> list[dict]:
    return [{"mirror": mirror[a:b], "action_skill": game[c:d]}
            for tag, a, b, c, d in SequenceMatcher(a=mirror, b=game, autojunk=False).get_opcodes()
            if tag != "equal"]


def _conclusion(cid, tier, field, mirror, game):
    if re.fullmatch(r"[a-z][a-z0-9_]+", game):
        return ("问题", "客户端描述为内部标识符", "action_skill c1 是内部英文键；不能把此值复制成玩家文案。须先核对真实技能及中文描述，再同步两端。")
    if mirror == game:
        return ("满足", "输入中已同步", "本次完整回读已一致；历史警告保留作追溯。")
    punctuation = lambda s: re.sub(r"[\W_]", "", s, flags=re.UNICODE)
    if punctuation(mirror) == punctuation(game):
        return ("问题", "标点或空白不一致", "完整文字内容一致，仅标点或空白不同；精确同步仍未完成。")
    if field == "技能名":
        category = "旧日文技能名" if re.search(r"[ァ-ヶー]", mirror) else "技能名档位标记不一致"
        return ("问题", category, "镜像名称与该档 action_skill c0 不同；客户端读取 action_skill 名称，需按该档名称同步镜像。")
    if cid == "149995":
        return ("问题", "镜像混写两档倍率", "镜像同时写入进化前后倍率，action_skill 按当前档仅显示一组；应按档同步，不能把两组重新堆回技能描述。")
    if cid == "129992":
        return ("问题", "倍率仍是旧值", "镜像写60/75倍，当前 action_skill 两档为40/50倍；应连同该档实际配置核对后同步镜像。")
    if cid == "261089" and tier in ("1", "2"):
        return ("问题", "高档强化文字写入低档镜像", "该档 action_skill 保留普通效果，客户端 character_text 提前写入强化版；不能因高档存在强化而覆盖低档技能。")
    if cid == "169995" and field == "技能描述":
        return ("问题", "镜像仅保留强化摘要", "镜像只写进一步增强，action_skill 已有完整技能说明；应同步完整该档描述。")
    return ("问题", "效果或参数描述不同步", "完整差异含效果范围、对象、数值、时间或具体动作变化；不是仅改了展示表就能影响游戏。按差异片段核对设计后同步该档镜像，保留 action_skill 的实际读取优先级。")


def explain_warnings(log_path: Path, workspace: TextWorkspace,
                     server_sources: dict[str, Path]) -> dict:
    raw_log = Path(log_path).read_bytes()
    report = json.loads(raw_log)
    server_docs, hashes = {}, {}
    for target, source in server_sources.items():
        raw = Path(source).read_bytes()
        server_docs[target], hashes[target] = json.loads(raw), sha256(raw)
    findings = [f for f in report["findings"] if f["check"] == "text" and f["level"] == "WARN"]
    entries = []
    for index, finding in enumerate(findings, 1):
        fid = finding["fid"]
        if not fid.startswith("text.drift:"):
            entries.append({"number": index, "fid": fid, "state": "待验证",
                            "category": "非字段漂移警告", "conclusion": finding["msg"],
                            "historical_evidence": finding.get("detail", [])})
            continue
        _, label, cid, tier, field = fid.split(":")
        col = 0 if field == "技能名" else 1
        mirror_column = 2 + 2 * int(tier) + col
        character = cells(workspace.table(CHARACTER)[cid])
        skill = character[8]
        game = cells(workspace.table(ACTION_SKILL)[skill][tier])[col]
        if label == "客户端 character_text 表":
            target = CHARACTER_TEXT
            mirror = cells(workspace.table(target)[cid])[mirror_column]
            source_sha = sha256(workspace.raw[target])
        elif label.startswith("服务端 "):
            target = label.removeprefix("服务端 ")
            if target not in server_docs:
                raise ValueError(f"missing explicit read-only server input: {target}")
            mirror = server_docs[target][cid][0][mirror_column]
            source_sha = hashes[target]
        else:
            raise ValueError(f"unknown warning text source: {label}")
        matches = finding["detail"] == [f"此处: {mirror[:120]}", f"游戏: {game[:120]}"]
        state, category, conclusion = _conclusion(cid, tier, field, mirror, game)
        if not matches:
            state, category, conclusion = ("待验证", "历史输入已漂移", "当前全文与历史日志前120字不一致；不能用当前值冒充历史原因。" )
        entries.append({"number": index, "fid": fid, "character_id": cid, "tier": tier,
                        "field": field, "mirror_source": target, "mirror_column": mirror_column,
                        "source_sha256": source_sha, "action_skill_key": skill,
                        "action_skill_column": col, "action_skill_sha256": sha256(workspace.raw[ACTION_SKILL]),
                        "historical_evidence_matches": matches, "state": state,
                        "category": category, "conclusion": conclusion,
                        "mirror_text": mirror, "action_skill_text": game,
                        "differences": _differences(mirror, game), "basis": "源码推断",
                        "basis_reference": "wf/deliver/prepush_text.py:_skill_tiers,check_text"})
    return {"schema": "wf-text-warning-audit/1", "log_sha256": sha256(raw_log),
            "since": report.get("since"), "warning_count": len(entries),
            "historical_matches": sum(e.get("historical_evidence_matches", False) for e in entries),
            "states": dict(Counter(e["state"] for e in entries)),
            "categories": dict(Counter(e["category"] for e in entries)), "entries": entries}


def markdown_audit(document: dict) -> str:
    lines = ["# M1 文本警告逐条核验", "",
             f"历史 prepush --since {document['since']}：{document['warning_count']} 条 text WARN；完整输入回读与历史摘要一致 {document['historical_matches']} 条。",
             "", "所有结论只覆盖本地数据与读取路径。‘问题’表示仍存在文本不一致，不代表已部署修复；本任务未改玩家文案。", "",
             "称号字段是零基 c3（第四个 CSV 单元格），c2 是角色介绍；依据 wf_wiki_catalog.py:character_entry 与 wf/chars/support/table_rows.py:character_text_row。", "",
             "JSON 附件保存每条完整文本、SHA-256、最小差异片段与稳定 fid。以下逐条显示位置、归因和处理原则。", "",
             "| # | 角色 / 档 | 文本源 / 字段 | 状态 / 归因 | 结论 |", "|---|---|---|---|---|"]
    for e in document["entries"]:
        source = e.get("mirror_source", "")
        label = "客户端" if source == CHARACTER_TEXT else Path(source).name
        lines.append(f"| {e['number']} | {e.get('character_id', '')} / {e.get('tier', '')} | {label} / {e.get('field', '')} | {e['state']}：{e['category']} | {e['conclusion']} |")
    return "\n".join(lines) + "\n"
