"""A data-only summon recipe plus an explicit DSL handoff for skill authors."""
from __future__ import annotations

import math

from wf.rules.catalog import result

from .client_extensions import check_client_extensions
from .drafts import DraftError
from .summon_panel import prepare_panel
from .summon_tables import CUSTOM, EMPTY, INT_MAX, PF, Tables, csv, native_row, number, single


def handoff(spec):
    life = spec.get("lifetime", {})
    seconds = number(life["seconds"], "寿命秒", 0) if "seconds" in life else None
    frames = int(life.get("frames", math.ceil(seconds * 60) if seconds is not None else INT_MAX))
    if not 1 <= frames <= INT_MAX:
        raise DraftError("寿命必须转换为 1..2147483647 帧（60fps）")
    identity = spec["id"]
    params = [1, int(identity), [{"min": frames, "max": frames}], ["E1", ["None"]],
              ["None"], ["None"], 0, False, f"summon_{identity}_activation", 900, 901, ["Block", []], None]
    return {"command": "CreateSummonsMultiball", "multiballId": identity,
            "lifetimeFrames": frames, "durationFrames": frames, "maxCount": 1, "selfOnly": True,
            "summon": {"multiballId": identity, "durationFrames": frames, "maxCount": 1, "selfOnly": True},
            "parameters": params,
            "node": ["Command", ["CreateSummonsMultiball", *params]],
            "inserted": False, "callbackSubjectIds": [900, 901],
            "instructions": ["把 node 插入技能 DSL 的 Block；本任务只生成表行，不改技能 DSL。",
                             "900/901 为回调主体示例 ID，嵌入现有技能时须分配未占用且互异的主体 ID。",
                             "末参数 null 表示继承召唤上下文 slv；面板使用上下文 clv，须落在 panel 定义域。",
                             "寿命只在召唤动作参数中生效；multiball 表没有寿命列。"]}


def recipe(source, spec):
    tables = Tables(source)
    row, active, preserved = native_row(tables, spec)
    from .summon_assets import validate_image
    validate_image(tables, row)
    panel = prepare_panel(tables, spec)
    extensions = spec.get("extensions", {})
    flip = extensions.get("flip_pf", {})
    if flip.get("enabled"):
        value = "1" + (":" + str(int(flip["min_interval_frames"])) if "min_interval_frames" in flip else "")
        tables.add(CUSTOM, "wfx_summon_flip_pf_" + spec["id"], csv([[value]]))
    if "ball_pf_action" in extensions:
        action = extensions["ball_pf_action"]
        paths = single(tables.get(PF, action), "power_flip_action", 3)
        if any(path in EMPTY or not path.strip() or path.strip() != path or "\n" in path or "\r" in path for path in paths):
            raise DraftError("power_flip_action 必须提供三档非空动作路径")
        tables.add(CUSTOM, "wfx_ball_pf_action_" + spec["id"], csv([[action]]))
    client = tables.compile()
    # This check is deliberately honest about APK evidence, unavailable in an
    # editing preview. build_draft performs the target APK and provides gates.
    tables.table(PF, required=False)
    baseline = {logical: raw for logical, raw in tables.original.items() if raw is not None}
    checks = check_client_extensions(client, baseline)
    if any(c["blocking"] for c in checks["checks"]):
        raise DraftError("召唤扩展检查失败：" + "; ".join(c["message"] for c in checks["checks"] if c["blocking"]))
    notes = [result("summon.data", "满足", "召唤表引用、曲线、扩展格式及新增键已检查", blocking=False),
             result("summon.runtime", "未执行", "技能召唤动作与设备运行未执行", blocking=False),
             result("summon.bundle", "未执行", "编辑预览未提供目标 APK；生成时执行 bundle-check", blocking=False)]
    notes.extend(checks["checks"])
    if "element" in spec:
        notes.append(result("summon.skill-element", "待验证", "属性只修改召唤球；沿用技能的 DSL 元素、效果及支持能力不改写", blocking=False))
    owned = {logical: list(additions) for logical, additions in tables.additions.items()}
    reservations = {"multiball": [spec["id"]], "string_id": owned[CUSTOM]}
    return tables, {"rows": tables.planned(), "checks": notes, "requires": checks["requires"],
                    "skillTemplate": handoff(spec), "skill": active, "panel": panel,
                    "preservedColumns": preserved, "ownedRows": owned, "reservations": reservations}
