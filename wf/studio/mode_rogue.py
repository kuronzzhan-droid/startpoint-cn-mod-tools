"""Tower read model and memory-only reroll, with explicit manual handoff."""
import hashlib
import json

import wf_quest_lib as q
from wf.tools.rogue import rogue_build as b, rogue_season as season
from wf.tools.rogue.rogue_candidate import build_candidate

MANUAL_STEPS = [
    {"title": "复核交付、应用后由作者停止正在进行的游戏，再清指定活动进度（数据库路径由作者填写）",
     "command": 'python -c "import sqlite3; from wf.tools.rogue.rogue_reroll import clear_progress; db=sqlite3.connect(r\'<存档数据库>\'); clear_progress(db, \'700099\', None); db.close()"'},
    {"title": "由作者调用已配置服务端结算并换期；先结算发奖再换期，不直接改 SQL 期号",
     "command": 'python -c "from wf.tools.rogue.rogue_reroll import rollover_via_server; r=rollover_via_server(\'700099\', \'studio-manual\'); print(r); raise SystemExit(0 if r[\'ok\'] else 3)"'},
    {"title": "由作者重启客户端下载新资源；有服务端 JSON 变更时由作者按原运维流程重启服务端",
     "command": 'adb -s <设备序列号> shell am force-stop <客户端包名>\nadb -s <设备序列号> shell am start -n <客户端Activity>'},
]


def rows_summary(rows, checks=()):
    bosses = {str(check["round"]): check["bosses"] for check in checks}
    return [{"key": key, "quest": row[0], "folder": row[1], "round": row[2],
             "name": row[4], "description": row[3], "element": row[69], "level": row[95],
             "bosses": bosses.get(key, []),
             "field": row[98], "effects": [{"kind": row[i], "strength": row[i+1]}
                                            for i in range(71, 81, 2)]}
            for key, row in sorted(rows.items(), key=lambda item: int(item[0]))]


def fingerprint(rows):
    return {row[2]: "|".join(row[i] for i in season.DIGEST_COLUMNS)
            for row in rows.values() if row[2] != "0"}


def current(loader):
    quest = q.parse_node(loader(b.Q_QUEST))[b.EVENT_ID]
    rows = {k: b.cells(v) for k, v in quest.items()}
    event = q.parse_node(loader(b.Q_EVENT)).get(b.EVENT_ID)
    digest = fingerprint(rows)
    return {"event": b.EVENT_ID, "eventRow": b.cells(event), "rounds": len(digest),
            "rows": rows_summary(rows), "fingerprint": hashlib.sha256(
                json.dumps(digest, sort_keys=True).encode()).hexdigest(),
            "season": None, "seasonNote": "当前视图只含活动内容，不含排行榜运行期号；期号未读取（不连接服务端或存档库）。",
            "manualSteps": MANUAL_STEPS, "_digest": digest}


def preview(loader, seed):
    before = current(loader)
    candidate = build_candidate(loader, seed=seed, rounds=before["rounds"])
    old_identity = {(r["quest"], r["folder"], r["round"]) for r in before["rows"]}
    new_identity = {(r[0], r[1], r[2]) for r in candidate["rows"].values()}
    if old_identity != new_identity:
        raise ValueError("重抽改变了活动/楼层身份，需要服务端镜像变更，本页拒绝生成")
    # Reroll only: retain current season metadata, rewards and endless curve.
    for logical in (b.Q_EVENT, b.Q_FOLDER, b.Q_LIST, b.Q_CORR):
        candidate["files"].pop(logical, None)
    from .mode_rogue_overlay import retain_and_namespace
    candidate = retain_and_namespace(loader, candidate)
    return {"ok": True, "canGenerate": True, "blockers": [], "seed": seed,
            "rounds": candidate["rounds"], "rows": rows_summary(candidate["rows"], candidate["checks"]),
            "checks": candidate["checks"], "log": candidate["log"],
            "seasonChange": season.classify(before["_digest"], fingerprint(candidate["rows"])),
            "manualSteps": MANUAL_STEPS, "files": candidate["files"],
            "cloneNamespace": candidate["cloneNamespace"], "retainedPreviousKeys": True}
