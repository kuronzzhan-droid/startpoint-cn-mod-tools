"""Check declared encounter ownership, state edges and semantic field references."""
from __future__ import annotations

from .schema import parse_rows, iter_leaves, get_leaf
from .scene_import import AE, AQ, GBS, GFS, walk
from .scene_spec import creation_targets
from .scene_types import (
    BGM_GROUP,
    CAS,
    CONTINUE_PREFIX,
    MIN_DATE_COLUMNS,
    parse_continue_cost,
    validate_event_code,
    validate_event_original,
    validate_row_dates,
)


def graph_problems(state, spec, tables):
    issues = []
    event = spec["event"]["id"]
    event_text = tables.get(AE, {}).get((event,))
    if event_text is None:
        issues.append("规格必须包含活动行 " + event)
    else:
        event_rows = parse_rows(event_text)
        event_row = event_rows[0] if event_rows else []
        if not event_row:
            issues.append("活动行缺少 CSV 内容：" + event)
        else:
            try:
                code = validate_event_code(event_row[0], f"{AE} {event}")
            except ValueError as exc:
                issues.append(str(exc))
                code = None
            if len(event_row) > 1:
                try:
                    validate_event_original(event_row[1], f"{AE} {event}")
                except ValueError as exc:
                    issues.append(str(exc))
            if code is not None:
                for other_path, other_text in iter_leaves(state.table(AE)):
                    if other_path == (event,):
                        continue
                    other_rows = parse_rows(other_text)
                    if other_rows and other_rows[0] and other_rows[0][0] == code:
                        issues.append(f"活动代号 c0 与已有活动 {'/'.join(other_path)} 冲突：{code!r}")
    quests = tables.get(AQ, {})
    if {path for path in quests if path[0] == event} != {(event, str(i)) for i in range(1, 6)}:
        issues.append("规格须完整包含当前活动的 1–5 档")
    bgm_groups = state.table(BGM_GROUP)
    for tier in spec["tiers"]:
        text = quests.get((event, tier["id"]))
        row = parse_rows(text)[0] if text else []
        if not row or row[0] != tier["quest"]:
            issues.append("五档身份与实际客户端行不一致：" + tier["id"])
            continue
        bgm = row[116] if len(row) > 116 else ""
        if not bgm or bgm == "(None)" or bgm not in bgm_groups:
            issues.append(f"五档第 {tier['id']} 档 BGM 组未在 battle_bgm_group 登记：{bgm!r}")
    expected_continue = {CONTINUE_PREFIX + tier["quest"] for tier in spec["tiers"]}
    for path, text in tables.get(CAS, {}).items():
        if len(path) == 1 and path[0].startswith(CONTINUE_PREFIX):
            if path[0] not in expected_continue:
                issues.append("续战消耗键不属于当前活动五档：" + path[0])
            try:
                parse_continue_cost(text, path[0])
            except ValueError as exc:
                issues.append(str(exc))
    for logical in MIN_DATE_COLUMNS:
        for path, text in tables.get(logical, {}).items():
            rows = parse_rows(text)
            if rows:
                issues.extend(validate_row_dates(logical, path, rows[0]))
    for item in spec["shops"]:
        if (item["id"],) not in tables.get("master/shop/event_item_shop.orderedmap", {}):
            issues.append("声明商店商品没有对应规格行：" + item["id"])
    new = spec.get("creation")
    if new:
        declared = {(t["logical"], tuple(t["path"])) for t in new["tableTargets"]}
        required, required_resources, _ = creation_targets(spec)
        if not required <= declared:
            issues.append("新场景缺少完整表键防撞声明")
        if not required_resources <= set(new["resourceTargets"]):
            issues.append("新场景缺少完整资源防撞声明")
    for logical in (GBS, GFS):
        tree = state.table(logical)
        selected = {path[0] for path in tables.get(logical, {})}
        for routine in selected:
            for group, nodes in tree.get(routine, {}).items():
                if not isinstance(nodes, dict):
                    issues.append("状态组格式错误：" + routine)
                    continue
                for path, text in iter_leaves(nodes):
                    row = parse_rows(text)[0]
                    if len(row) < 53:
                        issues.append("状态缺少原生列：" + routine + "/" + "/".join(path))
                        continue
                    for column in (26, 31, 32, 40):
                        for target in row[column].split(","):
                            if target and target != "(None)" and target not in nodes:
                                issues.append(f"状态边缺失 {routine}/{group}/{path[-1]} c{column} → {target}")
                    if row[22] in {"0", "1", "2", "3"}:
                        try:
                            count = int(row[23])
                            if count <= 0 or (row[22] == "3" and not 4 <= count <= 9):
                                raise ValueError
                        except ValueError:
                            issues.append("试炼计数阈值非法：" + routine + "/" + path[-1])
    return sorted(set(issues))
