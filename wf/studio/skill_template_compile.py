"""Compile official skill templates into the normal character draft delivery."""
from __future__ import annotations

import copy

import wf_quest_lib as codec
from wf.balance.rows import join_leaf, split_leaf
from wf.text.edit import _encode
from wf.rules.catalog import result

from .drafts import DraftError, sha256, validate
from .skill_template_inputs import ACTION, CHARACTER, Inputs, OfficialEffects, vacant


def template_change(draft):
    found = [c for c in (draft or {}).get("changes", []) if c["kind"] == "skill_template"]
    if len(found) > 1:
        raise DraftError("同一个角色只允许一个技能模板 change")
    return found[0] if found else None


def prepare(source, official, store, cid, request, *, previous=None, server_dir=None, verify_inputs=False):
    """All source and destination bytes stay in memory, including previews."""
    from .skill_template_catalog import resolve_key, template_detail
    from .skill_template_core import clone_tree, effect_paths, effect_families, rewrite_effects
    from .skill_template_effects import clone_effects
    validate(request, "skillTemplateRequest")
    inputs = Inputs(source, official)
    if previous and verify_inputs:
        inputs.verify(previous["params"]["inputs"])
        inputs.hashes.clear()
    char_raw = inputs.require(CHARACTER)
    chars = codec.parse_node(char_raw)
    if cid not in chars:
        raise DraftError(f"角色不存在：{cid}")
    rows = split_leaf(chars[cid], "character")
    if len(rows) != 1 or len(rows[0]) < 28:
        raise DraftError("角色表结构不足以确认技能归属")
    character = rows[0]
    code, new_key = character[0], request["newKey"]
    validate(code, "code")
    vacant(source, store, cid, new_key, previous, server_dir=server_dir)
    source_key = resolve_key(official, request["source"])
    target_element = int(request.get("element", character[3]))
    detail = template_detail(official, source_key, include_tree=True, previews=False,
                             context_element=target_element)
    if not detail:
        raise DraftError(f"官方母本技能不存在：{source_key}")
    # Catalogue reads are intentionally from the immutable official archive.
    inputs.require(ACTION, official=True)
    if request["source"].get("characterId"):
        official_chars = codec.parse_node(inputs.require(CHARACTER, official=True))
        selected = request["source"]["characterId"]
        if (selected not in official_chars or
                split_leaf(official_chars[selected], "character")[0][8] != source_key):
            raise DraftError("官方技能目录与角色主技能行不一致；请刷新来源视图")
    overrides = request.get("nodeCoefficients", {})
    tiers = detail["tiers"]
    if set(request.get("text", {})) - {tier["level"] for tier in tiers}:
        raise DraftError("text 包含不存在的技能档位")
    if set(overrides) - {tier["level"] for tier in tiers}:
        raise DraftError("nodeCoefficients 包含不存在的技能档位")
    prepared = {}
    context_element = target_element
    for tier in tiers:
        level = tier["level"]
        prepared[level] = clone_tree(
            tier["tree"], scale=request.get("scale", 1), node_coefficients=overrides.get(level),
            element=target_element, attribution=request.get("attribution"),
            summon=request.get("summon"), context_element=context_element)
    from .skill_template_colors import choose_effect_colors
    donor_detail = template_detail(official, source_key, include_tree=False, previews=False)
    inputs.require(CHARACTER, official=True)
    color_checks = choose_effect_colors(prepared, tiers, inputs, donor_detail["contextElement"], context_element)
    effects = sorted({value for cloned in prepared.values()
                      for value in effect_paths(cloned["tree"], context_element=context_element)})
    effect_result = clone_effects(OfficialEffects(inputs), effects, code, new_key, request.get("recolor"))
    members = dict(effect_result["members"])
    checks, levels = [*effect_result["checks"], *color_checks], []
    action_raw = inputs.require(ACTION)
    action = codec.parse_node(action_raw)
    from .skill_template_inputs import owned_clone_skill
    if new_key in action and not owned_clone_skill(store.load(cid), new_key):
        raise DraftError(f"action_skill 目标键已存在：{new_key}")
    donor_rows = codec.parse_node(inputs.require(ACTION, official=True))[source_key]
    new_rows = copy.deepcopy(donor_rows)
    node_count = 0
    for tier in tiers:
        level = tier["level"]
        if split_leaf(donor_rows[level], "action_skill") != [tier["row"]]:
            raise DraftError("官方技能目录与 action_skill 行不一致；请刷新来源视图")
        raw = inputs.require(tier["logical"], official=True)
        if sha256(raw) != tier["inputSha256"]:
            raise DraftError("官方技能目录与读取的 DSL 不一致")
        cloned = rewrite_effects(prepared[level]["tree"], effect_result["rewrite_map"],
                                 context_element=context_element)
        cloned["summary"] = prepared[level]["summary"]
        cloned["summary"]["effectFamilies"] = effect_families(cloned["tree"], context_element)
        if character[2] not in {"1", "2", "3", "4", "5"}:
            raise DraftError("目标角色星级无效")
        program = f"battle/action/skill/action/rare{character[2]}/{code}${new_key}_{level}"
        logical = program + ".action.dsl.amf3.deflate"
        if inputs.read(logical) is not None:
            raise DraftError(f"目标技能 DSL 路径已占用：{logical}")
        members["common", logical] = cloned["raw"]
        row = list(tier["row"])
        text = request.get("text", {}).get(level, {})
        row[0], row[1] = text.get("name", row[0]), text.get("description", row[1])
        row[7] = program
        from wf_client_skill_legality import action_skill_problems
        problems = action_skill_problems(row)
        if problems:
            raise DraftError("技能行校验失败：" + "；".join(problems))
        new_rows[level] = join_leaf(donor_rows[level], [row])
        checks.extend(cloned["checks"])
        node_count += len(cloned["damageNodes"])
        levels.append({"level": level, "logical": logical, "damageNodes": cloned["damageNodes"],
                       "summary": cloned["summary"]})
    if request.get("summon"):
        logical = "master/battle/multiball/multiball.orderedmap"
        balls = codec.parse_node(inputs.require(logical))
        if request["summon"]["multiballId"] not in balls:
            raise DraftError("召唤 ID 不在当前视图；请先生成召唤工坊草稿的依赖，再克隆技能")
    for root, logical in effect_result["members"]:
        if inputs.read(logical, root=root) is not None:
            raise DraftError(f"目标特效资源路径已占用：{logical}")
    after = {**action, new_key: new_rows}
    members["common", ACTION] = _encode(action_raw, action, after)
    character[8] = new_key
    new_chars = {**chars, cid: join_leaf(chars[cid], [character])}
    members["common", CHARACTER] = _encode(char_raw, chars, new_chars)
    from .skill_template_text import TEXT, client_text
    members["common", TEXT] = client_text(inputs, cid, new_rows)
    checks.extend([
        result("skill-template.tables", "满足", "新增压缩技能行并挂接目标角色；保留全部旧键与非目标行"),
        result("skill-template.text", "待验证", "技能与角色文案已同步；数值变化后的独立文案通过请求 text 各档 name/description 覆盖"),
        result("skill-template.device", "未执行", "静态编译不代表技能、协力与设备运行验证"),
    ])
    checks = [_check(check) for check in checks]
    return {"members": members, "inputs": inputs.hashes, "checks": checks,
            "code": code, "reservations": {"action_skill": [new_key]},
            "summary": {"sourceKey": source_key, "newKey": new_key, "levels": levels,
                        "damageNodeCount": node_count, "effectFamilies": effect_result["families"],
                        "files": [{"root": root, "logical": logical, "size": len(raw), "sha256": sha256(raw)}
                                  for (root, logical), raw in sorted(members.items())]}}


def _check(check):
    if "status" in check:
        return check
    level, code = check.get("level", "info"), check.get("code", "skill-template.check")
    state = ("未执行" if code.endswith("runtime") else "问题" if level == "error"
             else "待验证" if level == "warn" else "满足")
    return result(code, state, check["message"], blocking=level == "error")


def compile_skill_template(source, store, draft, *, official_source=None, server_dir=None):
    change = template_change(draft)
    if not change:
        return {}, [], []
    validate(draft)
    cid = draft["characterId"]
    if (draft["baseView"] != source.version or change["target"] != {"character": cid}):
        raise DraftError("技能模板草稿身份或基线不匹配")
    compiled = prepare(source, official_source or source, store, cid, change["params"]["request"],
                       previous=change, server_dir=server_dir, verify_inputs=True)
    if compiled["code"] != draft["code"] or compiled["reservations"] != change["params"]["reservations"]:
        raise DraftError("技能模板代码名或预留键与草稿不匹配")
    changes = [{"kind": "skill_template", "character": cid, "sourceKey": compiled["summary"]["sourceKey"],
                "newKey": change["params"]["request"]["newKey"]}]
    return compiled["members"], changes, compiled["checks"]
