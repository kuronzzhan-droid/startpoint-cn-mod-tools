"""Tower read model and memory-only reroll, with explicit manual handoff."""
import hashlib
import json

import wf_quest_lib as q
from wf.tools.rogue import rogue_build as b, rogue_season as season
from wf.tools.rogue.rogue_candidate import build_candidate

EVENTS = {"700099": "深渊连战", "700100": "深渊连战 EX"}


def event_identity(event_id):
    if not isinstance(event_id, str) or event_id not in EVENTS:
        raise ValueError("深渊活动只接受 700099 或 700100")
    return event_id


def manual_steps(event_id):
    event_identity(event_id)
    return [
    {"title": "复核交付、应用后由作者停止正在进行的游戏，再清指定活动进度（数据库路径由作者填写）",
     "command": f'python -c "import sqlite3; from wf.tools.rogue.rogue_reroll import clear_progress; db=sqlite3.connect(r\'<存档数据库>\'); clear_progress(db, \'{event_id}\', None); db.close()"'},
    {"title": "由作者调用已配置服务端结算并换期；先结算发奖再换期，不直接改 SQL 期号",
     "command": f'python -c "from wf.tools.rogue.rogue_reroll import rollover_via_server; r=rollover_via_server(\'{event_id}\', \'studio-manual\'); print(r); raise SystemExit(0 if r[\'ok\'] else 3)"'},
    {"title": "由作者重启客户端下载新资源；有服务端 JSON 变更时由作者按原运维流程重启服务端",
     "command": 'adb -s <设备序列号> shell am force-stop <客户端包名>\nadb -s <设备序列号> shell am start -n <客户端Activity>'},
]


MANUAL_STEPS = manual_steps("700099")


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


def _activity(quests, events, event_id):
    quest = quests.get(event_id, {})
    rows = {k: b.cells(v) for k, v in quest.items()}
    event = events.get(event_id)
    digest = fingerprint(rows)
    available = bool(rows) and event is not None
    return {"event": event_id, "name": EVENTS[event_id], "available": available,
            "unavailableReason": None if available else "当前视图未包含完整活动表与楼层，不能重抽。",
            "eventRow": b.cells(event) if event is not None else [], "rounds": len(digest),
            "rows": rows_summary(rows), "fingerprint": hashlib.sha256(
                json.dumps(digest, sort_keys=True).encode()).hexdigest(),
            "season": None, "seasonNote": "当前视图只含活动内容，不含排行榜运行期号；期号未读取（不连接服务端或存档库）。",
            "manualSteps": manual_steps(event_id), "_digest": digest}


def current(loader, event_id="700099"):
    event_identity(event_id)
    quests, events = q.parse_node(loader(b.Q_QUEST)), q.parse_node(loader(b.Q_EVENT))
    activities = [_activity(quests, events, identity) for identity in EVENTS]
    selected = next(activity for activity in activities if activity["event"] == event_id)
    return {**selected, "activities": [{k: v for k, v in activity.items() if k != "_digest"}
                                       for activity in activities]}


def preview(loader, seed, event_id="700099", *, server_asset_reader=None):
    event_identity(event_id)
    if type(seed) is not int or not 0 <= seed <= 2**32 - 1:
        raise ValueError("种子必须是 0–4294967295 的整数")
    before = current(loader, event_id)
    if not before["available"]:
        raise ValueError(before["unavailableReason"])
    options = {"server_asset_reader": server_asset_reader} if server_asset_reader is not None else {}
    candidate = build_candidate(loader, seed=seed, rounds=before["rounds"], event_id=event_id, **options)
    old_identity = {(r["quest"], r["folder"], r["round"]) for r in before["rows"]}
    new_identity = {(r[0], r[1], r[2]) for r in candidate["rows"].values()}
    if old_identity != new_identity:
        raise ValueError("重抽改变了活动/楼层身份，需要服务端镜像变更，本页拒绝生成")
    # Reroll only: retain current season metadata, rewards and endless curve.
    for logical in (b.Q_EVENT, b.Q_FOLDER, b.Q_LIST, b.Q_CORR,
                    "master/reward/event/additional_reward.orderedmap"):
        candidate["files"].pop(logical, None)
    from .mode_rogue_overlay import retain_and_namespace
    candidate = retain_and_namespace(loader, {**candidate, "eventId": event_id})
    return {"ok": True, "canGenerate": True, "blockers": [], "seed": seed, "eventId": event_id,
            "rounds": candidate["rounds"], "rows": rows_summary(candidate["rows"], candidate["checks"]),
            "checks": candidate["checks"], "log": candidate["log"],
            "seasonChange": season.classify(before["_digest"], fingerprint(candidate["rows"])),
            "manualSteps": manual_steps(event_id), "files": candidate["files"],
            "cloneNamespace": candidate["cloneNamespace"], "retainedPreviousKeys": True}
