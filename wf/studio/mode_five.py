"""Five-boss structure compilation and fail-closed spec/chain drift audit."""
import json
import math

from wf.tools.boss import five_boss_v2 as f
from wf.tools.rogue.rogue_candidate import isolated_builder

EDITABLE = ("rounds", "bosses", "affix_params", "variants", "budget")


def document():
    value = f.load_spec()
    value.pop("_variants")
    return value


def differences(before, after, path=""):
    if type(before) is type(after) and isinstance(before, dict):
        return [d for key in sorted(set(before) | set(after)) for d in
                differences(before.get(key), after.get(key), path + "/" + str(key))]
    if type(before) is type(after) and isinstance(before, list) and len(before) == len(after):
        return [d for i, (a, b) in enumerate(zip(before, after)) for d in differences(a, b, path + f"/{i}")]
    return [] if before == after else [{"path": path, "before": before, "after": after}]


def validate_document(value):
    base = document()
    if not isinstance(value, dict) or set(value) != set(base):
        raise ValueError("结构草稿必须保留完整 spec 字段")
    changes = differences(base, value)
    for change in changes:
        parts = change["path"].split("/")[1:]
        if parts[0] not in EDITABLE:
            raise ValueError("本页只编辑 rounds、bosses、affix_params、variants、budget")
        # Asset paths, source identities and output ownership are not editable here.
        if any(key in parts for key in ("mother", "from", "out", "src", "frames", "quest", "alias")):
            raise ValueError("不能在结构页修改素材来源、输出路径或身份：" + change["path"])
        old, new = change["before"], change["after"]
        affix = parts[0] == "affix_params" or bool(set(parts) & {"affixes", "entry_affixes", "signature"})
        if not affix and not (type(old) in (int, float) and type(new) in (int, float)):
            raise ValueError("本页只允许数值和词缀配置修改：" + change["path"])
    # Reject NaN/Infinity, even in nested affix parameters.
    json.dumps(value, allow_nan=False)
    spec = f.parse_spec(value)
    budget = spec["budget"]
    if not 0 < budget["pass_mpx"] <= budget["fail_mpx"]:
        raise ValueError("预算必须满足 0 < pass_mpx ≤ fail_mpx")
    for rnd in spec["rounds"].values():
        if any(type(v) not in (int, float) or v <= 0 for v in rnd["hp_mult"] + rnd["atk_mult"]):
            raise ValueError("HP 与攻击修正必须为正数")
    for v in spec["_variants"]:
        if len(v.enemy_states) > 5 or len({k for k, _ in v.enemy_states}) != len(v.enemy_states):
            # Existing duplicates must remain inspectable; unchanged legacy states
            # are handled by the drift gate, new duplicates are never saved.
            original = next(x for x in base["variants"] if int(x["quest"]) == v.quest)
            if next(x for x in value["variants"] if int(x["quest"]) == v.quest) != original:
                raise ValueError(f"{v.quest} 的状态槽重复或超过 5 项")
        for wave in v.waves:
            for boss in wave:
                if not math.isfinite(boss.hp_e8) or boss.hp_e8 <= 0:
                    raise ValueError("目标血量必须为有限正数")
    return spec, changes


def compile_structure(loader, value):
    spec, changes = validate_document(value)
    live = f.Live(loader)
    live.view_bound = True
    with isolated_builder(loader) as curves:
        def curve(name):
            result = curves.curve_value("hp", name, f.LEVEL)
            if not result:
                raise ValueError("当前视图缺 HP 曲线：" + name)
            return result
        live.hp_curve = curve
        plan = f.build(spec, live, with_envy_revert=False, with_art=False)
    files = {**f.apply_edits(live, plan), **plan.files}
    return {"files": files, "plan": plan, "live": live, "diff": changes}


def audit_current(loader, base, candidate=None):
    """Compare every builder-owned leaf/file, not whole shared table hashes."""
    drift, hp, quests = [], [], []
    plan, live = base["plan"], base["live"]
    for logical, edits in plan.edits.items():
        for path, wanted in edits:
            actual = f.get_path(live.table(logical), path)
            if actual != wanted:
                drift.append({"logical": logical, "path": "/".join(path),
                              "current": actual, "spec": wanted})
            if logical == f.T_BL and isinstance(actual, str) and isinstance(wanted, str):
                a, b = f.one_row(actual), f.one_row(wanted)
                if a[f.BL_HP_MUL:f.BL_HP_CORR+1] == b[f.BL_HP_MUL:f.BL_HP_CORR+1]:
                    ratio = float(a[f.BL_HP_HITS]) / float(b[f.BL_HP_HITS])
                    if abs(ratio - 1) > 1e-5:
                        hp.append({"clone": path[0], "currentToSpec": round(ratio, 6)})
            if logical == f.T_BBQ and isinstance(actual, str) and isinstance(wanted, str):
                a, b = f.one_row(actual), f.one_row(wanted)
                quests.append({"quest": a[0], "currentBossHpMultiplier": a[99],
                               "specBossHpMultiplier": b[99],
                               "statesMatch": a[74:84] == b[74:84]})
    audit_files = dict(plan.files)
    if loader is not None:
        # Dormant affixes can be enabled by a draft. Compare their repository
        # baseline, never the edited candidate, to any existing chain member.
        for name, tree in f.affix_library(document()["affix_params"]).items():
            logical = f.wf_dsl.dsl_logical(f.affix_program(name))
            if logical not in audit_files and live.file(logical) is not None:
                audit_files[logical] = f.encode_dsl(tree)
    for logical, wanted in audit_files.items():
        actual = live.file(logical)
        equal = actual == wanted
        if not equal and actual is not None and logical.endswith(".amf3.deflate"):
            # Compression/AMF map ordering alone is not evidence of a regression.
            try:
                equal = f.decode_amf(actual) == f.decode_amf(wanted)
            except (ValueError, TypeError, KeyError, OSError):
                pass
        if not equal:
            drift.append({"logical": logical, "path": "", "currentSha256": f.sha(actual) if actual else None,
                          "specSha256": f.sha(wanted)})
    if candidate is not None:
        for logical in candidate["plan"].files.keys() - audit_files.keys():
            if live.file(logical) is not None:
                drift.append({"logical": logical, "path": "", "reason": "草稿新增触及现有资源，但仓库基准未覆盖"})
        owned = {(logical, tuple(path)) for logical, edits in plan.edits.items() for path, _ in edits}
        for logical, edits in candidate["plan"].edits.items():
            for path, _ in edits:
                if (logical, tuple(path)) not in owned and f.get_path(live.table(logical), path) is not None:
                    drift.append({"logical": logical, "path": "/".join(path),
                                  "reason": "草稿新增触及现有表键，但仓库基准未覆盖"})
    return {"aligned": not drift, "differences": drift, "hpRatios": hp, "quests": quests,
            "note": "按当前链尾逐键/逐文件比较；结构生成保留当前美术，不执行旧嫉妒还原。"}


def preview(loader, value):
    base = compile_structure(loader, document())
    candidate = base if value == document() else compile_structure(loader, value)
    audit = audit_current(loader, base, candidate)
    problems = candidate["plan"].problems
    blockers = list(problems)
    if not audit["aligned"]:
        blockers.append("仓库 spec 落后或不同于当前链尾；重新生成会回退已有调整，已禁用生成。须先核对并回写规格。")
    return {"ok": not problems, "canGenerate": not blockers, "blockers": blockers,
            "diff": candidate["diff"], "audit": audit, "report": candidate["plan"].report,
            "warnings": candidate["plan"].warnings, "files": candidate["files"]}
