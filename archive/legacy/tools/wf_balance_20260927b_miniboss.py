"""五名小动物 2026-09-27 第二批（Down / 削韧）修订：Sec-2600Li、机枪魔块·雷、水灵幽魂、风暴恶魔拉比、炎枪见习兵。

口径：${WF_ROOT}/out/平衡调整批次-20260927/batch2/第二批施工口径.md（作者 2026-09-27 拍板），设计稿 growth/down_design.json
（基于 live 1.4.1048；本模块按 live 1.4.1049 重读、重算）。

1. 技能每次施放单目标总削韧 ≤30（B1）：只改 CreateNormalAttack 的 p13（node[13]，SLv 的 {min,max} 同改），其余节点逐字保留。
   - Sec-2600Li lv2：p13 1→0.75、1.5→1.1，40→29.8（复核 B1-P95 给定值；lv1 31.5 口径未点名，不动）。
   - 机枪魔块·雷 lv2：两段冲击波 p13 5→3，42→30（复核 C3，漏列补上）；弹幕 p13=1 与 lv1（21）不动。
   - 水灵幽魂 lv1/lv2：p13 1→0.5、10→5，51/60→25.5/30。
   - 风暴恶魔拉比 lv2：p13 1→0.65，46→29.9（复核 C4）；lv1（24）不动。
   - 炎枪见习兵 lv1/lv2：p13 1→0.6，48→28.8。
2. 能力调用技能（kind 629）每次 ≤3，触发 CT ≤3 秒的每次 ≤1（B3「按当前 live 的实际触发 CT 核对，
   CT ≤3 秒的一律 ≤1」）。live 触发核对：两名 629 行都是 PowerFlipLv1/2/3（trigger 63/64/65，阈值 1），
   CT c35=0 帧、限次 (None) ⇒ CT ≤3 秒 ⇒ 每次 ≤1。设计稿 p13 0.15 / 0.25（1.05/2.7/2.7、1/2/3）只满足 ≤3，
   这里按基诺维夜鸦裂空同法（设计稿同一比例再收，三级比例不变）：
   - 水灵幽魂人魂 7/18/18 → 0.35/0.9/0.9（p13 1→0.05，设计稿 0.15 的 1/3）；
   - 拉比爪刃 4/8/12 → 0.32/0.64/0.96（p13 1→0.08，设计稿 0.25 的约 1/3，取两位小数且 ≤1）。
   revise 按 live CT 现算每次上限（≤180 帧＝3 秒 → 1，否则 3）并核对改后值；触发列、CT、限次或程序路径
   一旦变动即拒绝（fail closed）。
3. 眩晕蓄积（B4）：Sec 能力1 行1 自身 150%→100%（c51/c52 150000→100000）；面板保持小动物单行格式。
   拉比能力5 行2 自身 50% 保留（本模块不读不改）。

单目标削韧口径（detoughness，与设计稿官方基线同一口径）：Repeat 乘次数；判定区命中数取 CalculatedUsingMaxNumOfHits，
或「寿命÷最小间隔+1」，再与 Some 上限取小；NWay/AShaped 扇面对单目标按 1 个判定区计；只认判定区 onHit（node[23]）
内的 CreateNormalAttack。遇到条件分支或其他未审形状即拒绝（fail closed）。
这个口径不看 CreateHitArea p16 eliminatedOnHit（命中即移除，ActionHitArea.as:496-518）：水灵幽魂的人魂判定区
（Single、p16=true）实际对单目标只命中 1 次，引擎实值低于口径值（见 :func:`engine_detoughness` 与 notes）。
口径值是上界，按它封顶保证实值也不超。

纯函数：只转换 ``read()`` 给出的 live 输入，不写任何文件；候选回写、发布由批次暂存脚本统一做
（接口见 ${WF_ROOT}/out/平衡调整批次-20260927/module_contract.md，第二批 b 后缀）。
生成器：能力与面板由 wf_miniboss_other.security / wf_miniboss_text.TEXTS 生成，已同步（revise 运行时核对
``build_abilities`` / ``ability_panel_rows`` 与本次输出逐键相同，不一致即拒绝）。技能与 629 DSL 在 wf_miniboss_* 里
没有生成器（kit 声明「retain installed DSL bytes」），本模块是这批 DSL 数值的唯一真源。
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from functools import partial
import hashlib
import json

import wf_client_legality as legality
import wf_dsl
from wf_midautumn_kitlib import panel_problems
from wf_miniboss_kits import build_abilities
from wf_miniboss_roster import BY_ID
from wf_miniboss_text import ability_panel_rows

SOURCE = "wf_balance_20260927b_miniboss.py"
SPEC = ("作者 2026-09-27 第二批口径 B：技能单目标总削韧 ≤30；629 每次 ≤3、触发 CT ≤3 秒的每次 ≤1；"
        "自身眩晕蓄积 ≤100%。只改 CreateNormalAttack p13 与 Sec 能力1 行1，其余逐字保留")
PACKAGE_VERSION = "1.0.2"   # 顶层候选 manifest 现值 1.0.1（第一批写入），本次 +1
R5 = "battle/action/skill/action/rare5/"
#: master/character c3（0 基内部元素）；DSL 元素门禁用。
ELEMENT = {"Red": 0, "Blue": 1, "Yellow": 2, "Green": 3, "White": 4, "Black": 5}
TOLERANCE = 1e-9

#: 技能 / 629 DSL：{角色: {程序后缀: (p13 旧→新, 改前 p13 普查 {值: CNA 数}, 改前总削韧, 改后总削韧)}}
DSL_PLAN = {
    "129998": {
        "1": ({1: 0.5, 10: 5}, {10: 3, 1: 3}, 51, 25.5),
        "2": ({1: 0.5, 10: 5}, {10: 3, 1: 5}, 60, 30),
        "hitodama_lv1": ({1: 0.05}, {1: 1}, 7, 0.35),
        "hitodama_lv2": ({1: 0.05}, {1: 2}, 18, 0.9),
        "hitodama_lv3": ({1: 0.05}, {1: 3}, 18, 0.9),
    },
    "139996": {
        "2": ({5: 3}, {1: 1, 5: 2}, 42, 30),
    },
    "149994": {
        "2": ({1: 0.65}, {1: 14}, 46, 29.9),
        "claw_lv1": ({1: 0.08}, {1: 2}, 4, 0.32),
        "claw_lv2": ({1: 0.08}, {1: 4}, 8, 0.64),
        "claw_lv3": ({1: 0.08}, {1: 6}, 12, 0.96),
    },
    "159999": {
        "2": ({1: 0.75, 1.5: 1.1}, {1: 4, 1.5: 1}, 40, 29.8),
    },
    "119995": {
        "1": ({1: 0.6}, {1: 6}, 48, 28.8),
        "2": ({1: 0.6}, {1: 6}, 48, 28.8),
    },
}

#: 629 行核对：{角色: (能力键, [(行下标 0 基, 触发 c27, 程序后缀)])}；CT c35 必须 0、限次 c34 必须 (None)。
INVOKE_ROWS = {
    "129998": ("1299983", [(0, "63", "hitodama_lv1"), (1, "64", "hitodama_lv2"), (2, "65", "hitodama_lv3")]),
    "149994": ("1499943", [(0, "63", "claw_lv1"), (1, "64", "claw_lv2"), (2, "65", "claw_lv3")]),
}
INVOKE_CT_FRAMES = "0"
#: 每次施放单目标削韧上限（口径 B1 / B3）：技能 30；629 按触发 CT 分档，CT ≤180 帧（60 fps 下 3 秒）→ 1，否则 3。
SKILL_CAP = 30
SHORT_CT_FRAMES = 180
INVOKE_CAP_SHORT_CT, INVOKE_CAP = 1, 3


def invoke_cap(ct_frames: str) -> int:
    return INVOKE_CAP_SHORT_CT if int(ct_frames) <= SHORT_CT_FRAMES else INVOKE_CAP

#: 能力：{能力键: {行下标 0 基: {列: (旧, 新)}}}
ABILITY_PLAN = {
    "1599991": {0: {51: ("150000", "100000"), 52: ("150000", "100000")}},
}
#: 面板：只改数字，沿用小动物单行「；」格式与半角「+」（复核 T2）。
PANELS = {
    "desc_override_security_robot_playable_1": (
        "自身眩晕积蓄+150%；光属性角色对眩晕敌人的伤害+60%。",
        "自身眩晕积蓄+100%；光属性角色对眩晕敌人的伤害+60%。"),
}

#: 按口径保留、易被误认为漏改的项（写进 notes）。
KEPT = {
    "159999": ["技能 lv1 security_robot_playable_1 单目标 31.5（口径 B1 与方案 30–40 表只点名 lv2）未改；"
               "31.5 略高于 ≤30，但低于官方★5 基础技 P95 35.8——是否也收到 ≤30 待作者确认（见 open_points）",
               "能力1 行2 光属性角色对眩晕敌人伤害 +60% 不动"],
    "139996": ["技能 lv1 cube_boss_playable_1 单目标 21 与 lv2 弹幕段 p13=1 不动（复核 C3：只改 lv2 冲击波 5→3）"],
    "129998": ["ghost_girl_playable_hitodama_ex / suisou_finisher 两个程序 live 无任何能力/队长行调用（只有文案键），不在本批"],
    "149994": ["技能 lv1 one_eyed_rabbit_playable_1 单目标 24 不动（复核 C4）",
               "能力5 行2 自身眩晕蓄积 50% 保留（口径 B4）",
               "one_eyed_rabbit_playable_claw_ex live 无任何能力/队长行调用（只有文案键），不在本批"],
    "119995": [],
}

#: 待作者确认、本模块不自行改动的项（数值按口径已落地；这里给现成的备选）。
OPEN_POINTS = {
    "159999": [
        "Sec 技能 lv1（security_robot_playable_1）口径值 31.5 > 30。口径 B1 只点名 lv2，故未改。若作者要 lv1 也 ≤30："
        "(a) 同 lv2 映射 1→0.75、1.5→1.1（31.5→23.45）；(b) 只改光束 1.5→1.2（31.5→29.4）。"
        "只需在 DSL_PLAN['159999'] 加 '1' 条目并把 lv1 树加进 BEFORE/夹具 inputs。",
        "Sec lv2 弹幕（NWay 12 颗、p16 eliminatedOnHit、无 Some 上限）按口径每波计 7 次；实机单目标每波 1–12 颗不等，"
        "29.8 是口径估计值。",
    ],
    "129998": [
        "人魂判定区（Single、CreateHitArea p16 eliminatedOnHit=true）命中即移除，对单目标实际只命中 1 次；"
        "设计稿/本模块口径按「寿命÷间隔+1 与 Some 取小」计，是上界。引擎实值：技能 33/35 → 16.5/17.5，"
        "629 人魂 1/2/3 → 0.05/0.1/0.15（作者看到的口径值是 51/60 → 25.5/30、7/18/18 → 0.35/0.9/0.9）。",
        "若作者按引擎实值定上限：629 可回到设计稿 p13 0.15（实值 0.15/0.3/0.45，仍 ≤1；口径值 1.05/2.7/2.7 则 >1）；"
        "技能可放轻为彼岸 10→8、人魂 1 不动（实值 27/29，口径值 45/54 超 30）。两者都要作者明确按实值口径拍板。",
    ],
}

#: 更严的 kit DSL 门禁（wf_midautumn_kit_hibiki.dsl_problems）在 live 上已有、本次既不新增也不处理的提示。
PREEXISTING = {
    "129998": ["ghost_girl_playable_1/_2/hitodama_lv2/lv3：兄弟判定区复用绑定 id 0/1/2（live 既有，四道客户端门禁为空）"],
    "139996": ["cube_boss_playable_2：CreateSummonsMultiball p11 为 null（live 既有，四道客户端门禁为空）"],
}

CANDIDATE_NOTE = ("回写顶层候选 work/character_packs/<package_id>：本次改动的 DSL 与 Sec 能力1/面板1。候选 DSL 与 live 逐树相同"
                  "（2026-09-27 核对），无已审漂移；候选其余能力/队长键仍是 2026-09-12 前 v0 内容，"
                  "禁止从这些候选整包 flow publish")


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def program(cid: str, suffix: str) -> str:
    code = BY_ID[cid].code
    return f"{R5}{code}${code}_{suffix}"


# ---------------------------------------------------------------- 单目标削韧


def _tag(node):
    return node[0] if isinstance(node, list) and node and isinstance(node[0], str) else None


def _area_hits(args, eliminated_single_hit: bool = False) -> int:
    lifetime, count, cap = args[13], args[14], args[15]
    if eliminated_single_hit and args[16] is True:
        # p16 eliminatedOnHit：命中即移除。Single 区对单目标恰好 1 次；NWay/AShaped 逐颗消除，命中数随几何 1–N，不估。
        if args[12][0] != "Single":
            raise ValueError(f"geometry-dependent eliminatedOnHit shape: {args[12][0]}")
        return 1
    if count[0] == "CalculatedUsingMaxNumOfHits":
        hits = count[1]
    elif count[0] == "SpecifyMinHitIntervalDirectly" and lifetime[0] == "SpecifyHitAreaLifetimeDirectly":
        hits = lifetime[1] // count[1] + 1
    else:
        raise ValueError(f"unreviewed hit-area count shape: {lifetime} / {count}")
    if cap[0] == "Some":
        hits = min(hits, cap[1][0]["max"])
    elif cap != ["None"]:
        raise ValueError(f"unreviewed hit-area cap shape: {cap}")
    return hits


def _p13(args) -> float:
    value = args[13]
    if (not isinstance(value, list) or len(value) != 1 or set(value[0]) != {"min", "max"}
            or value[0]["min"] != value[0]["max"]):
        raise ValueError(f"unreviewed CreateNormalAttack p13 shape: {value}")
    return value[0]["max"]


def detoughness(tree, eliminated_single_hit: bool = False) -> float:
    """技能/629 程序每次施放对单一目标的总削韧（p13 × 命中数，Repeat 乘次数）。

    默认是设计稿口径（不看 p16）；``eliminated_single_hit=True`` 时 p16 eliminatedOnHit 的 Single 区只计 1 次
    （引擎实值，仅供 notes 对照）。"""
    total = 0.0

    def walk(node, times):
        nonlocal total
        if not isinstance(node, list):
            return
        tag = _tag(node)
        if tag and tag.startswith("Conditionals"):
            raise ValueError(f"unreviewed branch node: {tag}")
        if tag == "Repeat":
            for child in node[3:]:
                walk(child, times * node[2])
            return
        if tag == "Command":
            args = node[1]
            if args[0] == "CreateNormalAttack":
                raise ValueError("CreateNormalAttack outside a hit area")
            if args[0] == "CreateHitArea":
                if (list(wf_dsl.iter_dsl_commands(args[20], "CreateNormalAttack"))
                        or list(wf_dsl.iter_dsl_commands(args[20], "CreateHitArea"))
                        or list(wf_dsl.iter_dsl_commands(args[23], "CreateHitArea"))):
                    raise ValueError("unreviewed nested hit-area shape")
                hits = _area_hits(args, eliminated_single_hit)
                total += times * hits * sum(_p13(a) for a in
                                            wf_dsl.iter_dsl_commands(args[23], "CreateNormalAttack"))
                return
            for child in args[1:]:
                walk(child, times)
            return
        for child in node:
            walk(child, times)

    walk(tree, 1)
    return total


def engine_detoughness(tree):
    """引擎实值（p16 eliminatedOnHit 的 Single 区只命中 1 次）；有逐颗消除的 NWay/AShaped 时返回 None。"""
    try:
        return round(detoughness(tree, eliminated_single_hit=True), 9)
    except ValueError as exc:
        if "geometry-dependent" in str(exc):
            return None
        raise


# ---------------------------------------------------------------- DSL 改写


def p13_census(tree) -> dict:
    return dict(Counter(_p13(a) for a in wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack")))


def revise_tree(tree, mapping: dict, census: dict) -> list:
    """只把 CreateNormalAttack p13 按 mapping 换值（SLv 的 min/max 同改），其余节点不动；不改输入。"""
    seen = p13_census(tree)
    if seen != census:
        raise ValueError(f"p13 preimage drift: {seen} != {census}")
    result = deepcopy(tree)
    for args in wf_dsl.iter_dsl_commands(result, "CreateNormalAttack"):
        old = _p13(args)
        if old in mapping:
            args[13] = [{"min": mapping[old], "max": mapping[old]}]
    return result


def dsl_problems(tree, element: int) -> list[str]:
    problems = []
    back = wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"]
    if json.dumps(back) != json.dumps(tree):   # 连 int/float 类型一起比
        problems.append("AMF3 roundtrip mismatch")
    problems += [f"element: {p}" for p in legality.action_dsl_element_problems(tree, element)]
    problems += [f"subject: {p}" for p in legality.action_dsl_subject_binding_problems(tree)]
    problems += [f"scope: {p}" for p in legality.action_dsl_lookup_scope_problems(tree)]
    problems += [f"hit_target: {p}" for p in legality.action_dsl_hit_area_target_problems(tree)]
    return problems


def row_problems(row: list[str], cas_keys) -> list[str]:
    return (legality.client_legality_problems("ability", row)
            + legality.declared_block_field_problems("ability", row)
            + legality.invoke_skill_string_problems(row, cas_keys, "ability"))


# ---------------------------------------------------------------- 单元


def _unit_before(cid: str) -> tuple:
    items = [("ability", k) for k in ABILITY_PLAN if k[:6] == cid]
    items += [("ability", INVOKE_ROWS[cid][0])] if cid in INVOKE_ROWS else []
    items += [("cas", k) for k in PANELS if k.startswith(f"desc_override_{BY_ID[cid].code}_")]
    items += [("dsl", program(cid, suffix)) for suffix in DSL_PLAN[cid]]
    return tuple(items)


#: 输入基线（digest(read(kind, key))，2026-09-27 live 1.4.1049 快照 tests/fixtures/balance_20260927b_miniboss.json）。
BEFORE = {
    ("ability", "1599991"): "e217331f0c17acbbbfc2b6e94e1f31a209b2e0fa235321d3d0c75abda3cbfc89",
    ("ability", "1299983"): "d1452ba7ae91c1a166af29c8a367b85c18e608b36c60834d28008c510809f07b",
    ("ability", "1499943"): "8ec0e91df9a9b7c1233ae08cf3392eb345e5e0ecb98442ba24e4577b81269373",
    ("cas", "desc_override_security_robot_playable_1"):
        "0ea60f936ee82e3ecf7cc0748fee84d324c7cbe07801d8d53bf9431c58889fba",
    ("dsl", program("129998", "1")): "bcf5d2ed6169e23ca0b8abd438aaabbb25029522122fff25468ce4cb50e1cf05",
    ("dsl", program("129998", "2")): "5d3e656a1831a46cf3de69eefb8c973913416232fae62efa19a5eede60cbcf13",
    ("dsl", program("129998", "hitodama_lv1")): "ecaf59b7aa3a07f29cedb729ac42391b4f2fba3bf566066e4dce18c0087dcc0a",
    ("dsl", program("129998", "hitodama_lv2")): "a7ae9914a8e83f22ff70e19ae08e5755fc0055862f324b232996c06b410f9f59",
    ("dsl", program("129998", "hitodama_lv3")): "39b2d1a6ae9b1a3da5f44214b667283c5e57319bf83761c3508bdb993a27dd95",
    ("dsl", program("139996", "2")): "e54ed7a880ed372fa0da69139e85116d9dd546df85c4f73539cf3acca34c3ed1",
    ("dsl", program("149994", "2")): "fc386a61c3a9425959e8a3ed4d0be04854ba3b2ac12a068c4a3a781380581db3",
    ("dsl", program("149994", "claw_lv1")): "9c67d67253be765a1f869d97aaeb3f6b385eee05d939993fa2835840a9d56be1",
    ("dsl", program("149994", "claw_lv2")): "bdf83a9b9813ec986fd38d2ef6246ebfa20c9199588516fcc06ae7ca9670da8f",
    ("dsl", program("149994", "claw_lv3")): "0b8a15444b113ea18f6dcff3ca2db4ae2bc9ecdde2cf87af82a36de0de9b882b",
    ("dsl", program("159999", "2")): "cd640f85c0f5632fa5c45e37a6ed29daa6cd420300fbac21ae1c341d3f51b365",
    ("dsl", program("119995", "1")): "a8629402983449534a19002977c3805ca7ab12c94a3b79223a79ba717be65218",
    ("dsl", program("119995", "2")): "44469398311dd7c25d188a314011e16c9dee7f435e5d786aeb7d5270b5796257",
}


def _baseline(cid: str, read) -> dict:
    """读取并锁定本角色全部输入；任何一项漂移都拒绝（fail closed）。"""
    inputs = {}
    for kind, key in UNIT_BEFORE[cid]:
        value = read(kind, key)
        if value is None or digest(value) != BEFORE[kind, key]:
            raise ValueError(f"unreviewed live baseline: {kind}:{key}")
        inputs[kind, key] = deepcopy(value)
    return inputs


def _check_invoke_rows(cid: str, inputs) -> list[dict]:
    """629 行的触发、CT、限次、程序路径与审查时一致（否则「CT≤3 秒每次≤1」要重新判定），并按 live CT 给出每次上限。"""
    if cid not in INVOKE_ROWS:
        return []
    key, spec = INVOKE_ROWS[cid]
    rows = inputs["ability", key]
    checked = []
    for index, trigger, suffix in spec:
        row = rows[index]
        got = (row[5], row[27], row[30], row[34], row[35], row[47], row[71])
        want = ("0", trigger, "100000", "(None)", INVOKE_CT_FRAMES, "629", program(cid, suffix))
        if got != want:
            raise ValueError(f"629 invoke row drift (re-check CT rule): {key}#{index + 1}: {got}")
        checked.append({"key": key, "row": index + 1, "trigger": f"PowerFlipLv{int(trigger) - 62}",
                        "cooltime_frames": int(row[35]), "limit": row[34], "program": suffix,
                        "per_call_cap": invoke_cap(row[35])})
    return checked


def _revise_ability(cid: str, inputs) -> dict:
    out = {}
    for key, plan in ABILITY_PLAN.items():
        if key[:6] != cid:
            continue
        rows = deepcopy(inputs["ability", key])
        for index, cells in plan.items():
            got = {col: rows[index][col] for col in cells}
            if got != {col: old for col, (old, _) in cells.items()}:
                raise ValueError(f"unexpected preimage for {key}#{index + 1}: {got}")
            for col, (_, new) in cells.items():
                rows[index][col] = new
        out[key] = rows
    return out


def _revise_panels(cid: str, inputs) -> dict:
    out = {}
    for key, (old, new) in PANELS.items():
        if not key.startswith(f"desc_override_{BY_ID[cid].code}_"):
            continue
        if inputs["cas", key] != [[old]]:
            raise ValueError(f"unexpected panel preimage: {key}")
        out[key] = [[new]]
    return out


def revise_character(cid: str, read) -> dict:
    char = BY_ID[cid]
    inputs = _baseline(cid, read)
    element = ELEMENT[char.group]
    invoke = _check_invoke_rows(cid, inputs)
    caps = {c["program"]: c["per_call_cap"] for c in invoke}

    dsl, dsl_notes = {}, []
    for suffix, (mapping, census, before, after) in DSL_PLAN[cid].items():
        path = program(cid, suffix)
        if suffix in ("1", "2"):
            cap = SKILL_CAP
        elif suffix in caps:
            cap = caps[suffix]
        else:
            raise ValueError(f"program is neither a skill level nor a checked 629 target: {path}")
        old = inputs["dsl", path]
        new = revise_tree(old, mapping, census)
        was, now = detoughness(old), detoughness(new)
        if abs(was - before) > TOLERANCE or abs(now - after) > TOLERANCE:
            raise ValueError(f"detoughness drift: {path}: {was}->{now} != {before}->{after}")
        if round(now, 9) > cap:
            raise ValueError(f"per-call detoughness cap exceeded: {path}: {now} > {cap}")
        dsl[path] = new
        dsl_notes.append({"program": path, "p13": {str(k): v for k, v in mapping.items()},
                          "p13_census_before": {str(k): v for k, v in census.items()},
                          "single_target_detoughness": [before, after], "cap": cap,
                          "engine_eliminated_on_hit": [engine_detoughness(old), engine_detoughness(new)]})

    ability = _revise_ability(cid, inputs)
    cas = _revise_panels(cid, inputs)

    # 生成器一致性：重跑 wf_miniboss_kits / wf_miniboss_text 必须得到同样的行与面板。
    if ability or cas:
        kit, _ = build_abilities(cid)
        panels = ability_panel_rows(cid, kit)
        drift = sorted([k for k, rows in ability.items() if kit[k] != rows]
                       + [k for k, rows in cas.items() if panels[k] != rows])
        if drift:
            raise ValueError(f"generator differs from the revision: {drift}")

    problems = [f"ability {key}#{i}: {p}" for key, rows in ability.items()
                for i, row in enumerate(rows) for p in row_problems(row, set(cas))]
    problems += [f"panel {key}: {p}" for key, rows in cas.items() for p in panel_problems(rows[0][0])]
    problems += [f"dsl {path}: {p}" for path, tree in dsl.items() for p in dsl_problems(tree, element)]
    if problems:
        raise ValueError("; ".join(problems))
    return {
        "ability": ability, "leader": {}, "cas": cas, "text": {}, "table": {},
        "action": {}, "dsl": dsl, "server_text": {}, "new_programs": [],
        "notes": {
            "source": SOURCE, "spec": SPEC, "character": char.name,
            "dsl": dsl_notes,
            "ability": [{"key": key, "row": i + 1, "cells": {str(c): list(v) for c, v in cells.items()}}
                        for key, plan in ABILITY_PLAN.items() if key[:6] == cid
                        for i, cells in plan.items()],
            "panel": {key: list(PANELS[key]) for key in cas},
            "invoke_629_ct_check": invoke,
            "kept": KEPT[cid],
            "open_points": OPEN_POINTS.get(cid, []),
            "preexisting_strict_gate": PREEXISTING.get(cid, []),
            "texts": "技能描述/character_text/服务端文本不含削韧或眩晕蓄积数值，不改",
            "generator": ("wf_miniboss_other.security + wf_miniboss_text.TEXTS == revise()" if ability or cas
                          else "无能力/面板改动；DSL 在 wf_miniboss_* 无生成器"),
            "candidate": CANDIDATE_NOTE,
            "runtime_verified": False,
        },
    }


UNIT_ORDER = ("129998", "139996", "149994", "159999", "119995")
UNIT_BEFORE = {cid: _unit_before(cid) for cid in UNIT_ORDER}
if set(BEFORE) != {item for items in UNIT_BEFORE.values() for item in items}:
    raise ImportError("BEFORE / plan are out of sync")

UNITS = [dict(CID=cid, CODE=BY_ID[cid].code, NAME=BY_ID[cid].name,
              PACKAGES=[BY_ID[cid].package_id],
              PACKAGE_VERSION={BY_ID[cid].package_id: PACKAGE_VERSION},
              CAPABILITIES=[], REVIEWED_DRIFT={},
              BEFORE={item: BEFORE[item] for item in UNIT_BEFORE[cid]},
              revise=partial(revise_character, cid))
         for cid in UNIT_ORDER]
