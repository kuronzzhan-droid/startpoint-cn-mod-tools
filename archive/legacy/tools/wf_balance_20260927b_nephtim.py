"""校园奈芙提姆 169989 ``ruin_girl_campus``：2026-09-27 平衡调整第二批（无上限成长 + Down）。

依据：作者口径 ``${WF_ROOT}/out/平衡调整批次-20260927/batch2/第二批施工口径.md`` A（无上限成长）、B.2（强化弹射
每级削韧上限 15/20/25，点名「奈芙提姆 PF Lv3 末段 1→0（26→25）」）；成长复核 growth critic C01（设计稿没有她的
条目，按 C01 的 fix 做，行号与数值按 live 1.4.1049 重推）。第一批（e0cdcc14，wf_balance_20260927_nephtim）
已改过队长/能力1/能力2 与每帧 629，本模块以其发布后的 live 为输入。

规格（行号 1 基）：
1. 能力3（1699893，整键仅主位 c1=false）行3/行4：T235「Fever 中自身每保持贯穿 120 帧」→ 暗队攻击力(I32)/
   直击伤害(I33) 各 +10%，c34 限次 (None) = 无上限永久成长 → 原位改成有上限的弱化版：
   c34 (None)→10；行3 强度 10000→5000（最多 +50%），行4 强度保持 10000（最多 +100%）。其余格与其余四行不动。
2. 队长 169989（8 行 → 10 行）：追加第9、10行 = [CODE,'0',''] + 能力3 行3/行4[5:]（能力列 c≥5 → 队长列 −2），
   强度 10000→1000（1/10），限次保持 (None)。队长里没有 T235 行 → 不合并，新起两行（口径 A.3）。
   先例（口径 A.4）：队长 T235 = live 169999#7-9（基诺维）；队长前置12（Fever）= live 149989#4-6（校园希尔媞）。
3. 队长第5行：每35连击 → 暗队 Fever 获得量(I50) +20%，c32 限次 (None) → 原位放缓 20000→2000（1/10）。
4. 面板：``desc_override_ruin_girl_campus`` 第5行 +20%→+2%，末尾追加一句贯穿成长（+1%，写到效果为止，
   不写「可无限累积」）；``desc_override_ruin_girl_campus_3`` 第2行改为「攻击力+5%、直接攻击伤害+10%（最多10次）」。
5. Down：强化弹射 Lv3 程序 ``ruin_girl_campus_fever_lv3`` 辅助型末段 CreateNormalAttack p13 1→0
   （6.25×3 + 6.25×1 + 1×1 = 26 → 25），其余节点逐字不动；Lv1/Lv2 已是 15/20，不改。

放缓倍率按 3 分钟实际触发次数（口径 A.2），估算见 :func:`notes` 的 ``frequency_estimates``：两项都 ≥30 次 → 1/10。
生成器（wf_nephtim_fever_abilities / _leader / _text / _powerflip）已同步，测试断言生成器输出 == revise()。

纯函数：revise(read) 只经 read() 读取 live，返回有变化的键；不写 live store、候选工作区、assets 或 .cdn。
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json

import wf_client_legality as legality
import wf_dsl
from wf_midautumn_kitlib import panel_problems as kit_panel_problems

CID = "169989"
CODE = "ruin_girl_campus"
# 同第一批：第一个是 active owner，第二个是同 package_id 的副本（只镜像目标键）。
PACKAGES = ["nephtim-summon-cap-20260916/ruin_girl_campus", "campus-nephtim-20260911"]
PACKAGE_VERSION = {
    "nephtim-summon-cap-20260916/ruin_girl_campus": "0.2.4",   # 现值 0.2.3（第一批）
    "campus-nephtim-20260911": "0.20260927.1",                 # 现值 0.20260927（日期式版本，同日第二次修订）
}
# 能力3 整键回写含第5行 I724（比例版客户端）；desc_override_* 需要 V14 面板覆盖补丁。两个候选都已声明。
CAPABILITIES = ["kyubi-fever-ratio-v1", "panel-description-override-v2"]
# 两个候选 manifest 与文件逐一一致（owner 174 条、副本 98 条，2026-09-27 只读核对），目标键与 live 逐字相同。
REVIEWED_DRIFT: dict = {}

A3 = CID + "3"
TEXT_LEADER = "desc_override_" + CODE
TEXT_A3 = TEXT_LEADER + "_3"
CHANGE_SKILL_STRING_ID = "change_skill_" + CODE + "_fever"
PF_ID = CODE + "_fever"
PF_STRING_ID = PF_ID + "_powerflip"
BALL_HIT_STRING_ID = CODE + "_ball_hit_count"
A3_STRING_ID = CODE + "_multiball_direct"
PF_ACTION = ("master/skill/power_flip_action.orderedmap", PF_ID)
PF_PROGRAMS = tuple(f"battle/action/power_flip/action/override/{PF_ID}${PF_ID}_lv{level}"
                    for level in (1, 2, 3))
PF_LV3 = PF_PROGRAMS[2]
MAIN_ICON = " <icon id='main'>  "
DARK_ELEMENT = 5                      # master/character c3 内部 ElementKind（暗）

# 能力3 行3/行4（0 基 2/3）：T235 贯穿成长。
PIERCING_INDEXES = (2, 3)
PIERCING_CONTENTS = ("32", "33")
OLD_PIERCING_STRENGTH = 10_000
CAPPED_STRENGTHS = (5_000, 10_000)    # 能力3 弱化版：攻击力 +5%、直击 +10%
CAPPED_LIMIT = 10                     # 能力3 两行 c34 限次
LEADER_PIERCING_STRENGTH = 1_000      # 队长：各 +1%（1/10），不限次
# 队长第5行（0 基 4）：每35连击 → 暗队 Fever 获得量。
FEVER_GAIN_INDEX = 4
OLD_FEVER_GAIN, NEW_FEVER_GAIN = 20_000, 2_000
# PF Lv3：辅助型末段（主体 3+200）削韧 1 → 0；特殊型两段 6.25 不动。
PF_SPECIAL_TOUGHNESS = 6.25
PF_SUPPORT_SUBJECT = 203
OLD_PF_TOUGHNESS, NEW_PF_TOUGHNESS = 1, 0
PF_TOUGHNESS_CAP = {1: 15, 2: 20, 3: 25}

PIERCING_ROW_CELLS = {   # 能力3 行3/行4 的共同原像（非内容列）
    1: "false", 3: "0", 5: "0", 6: "2", 9: "600000", 10: "600000", 11: "Black", 13: "12", 20: "0",
    27: "235", 30: "100000", 31: "100000", 32: "12000000", 33: "12000000", 34: "(None)", 35: "0",
    39: "(None)", 46: "0", 48: "5", 49: "Black",
    51: str(OLD_PIERCING_STRENGTH), 52: str(OLD_PIERCING_STRENGTH),
}
FEVER_GAIN_ROW_CELLS = {
    3: "0", 4: "2", 7: "600000", 8: "600000", 9: "Black", 11: "0", 18: "0",
    25: "12", 28: "3500000", 29: "3500000", 32: "(None)", 33: "0", 45: "50", 46: "5", 47: "Black",
    49: str(OLD_FEVER_GAIN), 50: str(OLD_FEVER_GAIN),
}

OLD_FEVER_GAIN_LINE = "暗属性共鸣时，每达成35连击，暗属性角色获得的 Fever 槽上升量+20%。"
NEW_FEVER_GAIN_LINE = "暗属性共鸣时，每达成35连击，暗属性角色获得的 Fever 槽上升量+2%。"
OLD_A3_PIERCING_LINE = (MAIN_ICON + "暗属性共鸣时，Fever 模式中，处于贯穿效果的时间每累计2秒，"
                        "暗属性角色攻击力+10%、直接攻击伤害+10%。")
NEW_A3_PIERCING_LINE = (MAIN_ICON + "暗属性共鸣时，Fever 模式中，处于贯穿效果的时间每累计2秒，"
                        "暗属性角色攻击力+5%、直接攻击伤害+10%（最多10次）。")
LEADER_PIERCING_LINE = ("暗属性共鸣时，Fever 模式中，处于贯穿效果的时间每累计2秒，"
                        "暗属性角色攻击力+1%、直接攻击伤害+1%。")
# 第一批禁语 + 第二批口径 D 节禁语（kitlib.panel_problems 另查一遍）。
FORBIDDEN_PANEL_PHRASES = ("自身为队长时", "觉醒后", "生命值100%以下", "／",
                           "无上限", "无限叠加", "不设上限", "可无限")

#: live 1.4.1049 输入基线（2026-09-27 只读导出，make_read(live_only=True)）；任一不符 ⇒ revise() 拒绝。
BEFORE = {
    ("ability", A3): "b3d7c3d83ed09eb4ea29a464ab16cf374b9bf9a5e94263e4aad9bc0ba9172f3e",
    ("leader", CID): "6a2724e985792ca50ee01ddd34f71a9b570e3e7015e957601a3beb78e84ea159",
    ("cas", TEXT_LEADER): "3e34d7547b564217a22da0242162e0ddf9198167754369148d007f35ec56855f",
    ("cas", TEXT_A3): "749132b462aecebac0b644614d14e1d482f979c1ce81954a5f363c87f9f69c38",
    ("dsl", PF_LV3): "a1b35524064960f2f65a05483f2369a5bf246e4c563a213fe9ea7a577e1ea16f",
    ("table", PF_ACTION): "ae9fcc9239a54018954b48e5189eb609df39776c1c065537652284efa49cf1da",
    # 下列原生串不改，只作存在性与未漂移校验（输出行 I536/I722/I629 的文案键）。
    ("cas", CHANGE_SKILL_STRING_ID): "0d967429bc2adeef5ed12f67863d6492cfe7e08cd04968475d9ba56e7cbf4ed4",
    ("cas", PF_STRING_ID): "1e23cda7f5c6b06be276398ca7b52891ac751faa11ab75e276cdbe4e95ff05c0",
    ("cas", BALL_HIT_STRING_ID): "ea0d1d398be6943e4e0d4b4a48a1bf7e2860a3b225649a51d6e29d035e18edc1",
    ("cas", A3_STRING_ID): "279e6b6ca9ca6ce39e1f5a760e71cf7846e0b9aa450ca9e9084a009b2ae2239e",
}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _require(condition, message):
    if not condition:
        raise ValueError(f"{CID} balance 20260927b: {message}")


def _shape(rows, count, width, string_id):
    _require(isinstance(rows, list) and len(rows) == count, f"{string_id}: expected {count} rows")
    for row in rows:
        _require(len(row) == width and row[0] == string_id,
                 f"{string_id}: expected {width}-column rows with c0={string_id}")


def _cells(row, cells, what):
    got = {column: row[column] for column in cells}
    _require(got == cells, f"unexpected preimage for {what}: {got}")


def _text(rows, key):
    _require(len(rows) == 1 and len(rows[0]) == 1 and isinstance(rows[0][0], str),
             f"{key}: expected one text cell")
    return rows[0][0]


def ability3_rows(rows):
    """能力3 行3/行4 原位改成有上限的弱化版；其余四行与这两行的其余格逐字不动。"""
    _shape(rows, 6, 126, CODE + "_3")
    _require({row[1] for row in rows} == {"false"}, "ability3 must stay main-only")
    _require([i for i, row in enumerate(rows) if row[27] == "235"] == list(PIERCING_INDEXES),
             "ability3 rows 3-4 must be its only T235 rows")
    result = deepcopy(rows)
    for index, content, strength in zip(PIERCING_INDEXES, PIERCING_CONTENTS, CAPPED_STRENGTHS):
        row = result[index]
        _cells(row, {**PIERCING_ROW_CELLS, 47: content}, f"ability3 row{index + 1}")
        row[34] = str(CAPPED_LIMIT)
        row[51:53] = [str(strength)] * 2
    return result


def _merge_key(row):
    """口径 A.3 合并判据：同前置、同触发（含阈值/限次/CT 块）、同 kind/目标/组。"""
    return tuple(row[3:34]), tuple(row[45:48])


def moved_leader_rows(a3_rows):
    """能力3 行3/行4 → 队长同形行（[CODE,'0',''] + row[5:]，列号 −2），强度 1/10、不限次。"""
    moved = []
    for index, content in zip(PIERCING_INDEXES, PIERCING_CONTENTS):
        source = a3_rows[index]
        _cells(source, {**PIERCING_ROW_CELLS, 47: content}, f"ability3 row{index + 1} (move source)")
        row = [CODE, "0", ""] + deepcopy(source[5:])
        _require(len(row) == 124, "moved row must have 124 columns")
        _require((row[25], row[28], row[30], row[32], row[33], row[45], row[46], row[47])
                 == ("235", "100000", "12000000", "(None)", "0", content, "5", "Black"),
                 "moved row must keep the T235 trigger, no limit and no cooldown")
        row[49:51] = [str(LEADER_PIERCING_STRENGTH)] * 2
        moved.append(row)
    return moved


def leader_rows(rows, a3_rows):
    """返回队长十行：第5行 Fever 获得量成长放缓；末尾追加两条贯穿成长（不合并，队长无 T235 行）。"""
    _shape(rows, 8, 124, CODE)
    _require([row[45] for row in rows] == ["722", "536", "33", "32", "50", "56", "211", "629"],
             "leader must be the batch-1 eight rows")
    _require(rows[7][68] == BALL_HIT_STRING_ID, "leader row8 must be the 9/25 ball-hit-count row")
    result = deepcopy(rows)
    growth = result[FEVER_GAIN_INDEX]
    _cells(growth, FEVER_GAIN_ROW_CELLS, "leader row5 (35-combo Fever gain growth)")
    growth[49:51] = [str(NEW_FEVER_GAIN)] * 2
    moved = moved_leader_rows(a3_rows)
    existing = {_merge_key(row) for row in rows}
    _require(not any(_merge_key(row) in existing for row in moved),
             "an existing leader row shares the moved rows' trigger/kind/target: merge instead")
    _require(not any(row[25] == "235" for row in rows), "leader must not already carry a T235 row")
    return result + moved


def leader_text(text):
    lines = text.split("\n")
    _require(len(lines) == 8 and lines[FEVER_GAIN_INDEX] == OLD_FEVER_GAIN_LINE,
             "unexpected leader panel lines")
    _require(not any(line.startswith(MAIN_ICON) for line in lines), "leader panel must not carry the main icon")
    lines[FEVER_GAIN_INDEX] = NEW_FEVER_GAIN_LINE
    return "\n".join(lines + [LEADER_PIERCING_LINE])


def ability3_text(text):
    lines = text.split("\n")
    _require(len(lines) == 4 and all(line.startswith(MAIN_ICON) for line in lines)
             and lines[1] == OLD_A3_PIERCING_LINE, "unexpected ability3 panel lines")
    lines[1] = NEW_A3_PIERCING_LINE
    return "\n".join(lines)


def _attacks(tree):
    return list(wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack"))


def pf_toughness(tree):
    """单目标每次 PF 的削韧：Σ 判定区最大命中数 × 该区 CreateNormalAttack 的 p13（SLv 取 max）。"""
    total = 0
    for area in wf_dsl.iter_dsl_commands(tree, "CreateHitArea"):
        attacks = _attacks(area)
        _require(len(attacks) == 1 and area[14][0] == "CalculatedUsingMaxNumOfHits",
                 "each PF hit area must carry one attack and a max-hit count")
        total += area[14][1] * attacks[0][13][0]["max"]
    return total


def pf_lv3_tree(tree):
    """Lv3 辅助型末段削韧 1 → 0；只改这一个 p13（按 SLv 的 {min,max} 都改），其余节点逐字不动。"""
    tree = deepcopy(tree)
    _require(tree[:11] == ["ActionDsl", 1, ["None"], *[False] * 7, 0], "PF lv3 root header drift")
    attacks = _attacks(tree)
    special = [{"min": PF_SPECIAL_TOUGHNESS, "max": PF_SPECIAL_TOUGHNESS}]
    _require([attack[13] for attack in attacks]
             == [special, special, [{"min": OLD_PF_TOUGHNESS, "max": OLD_PF_TOUGHNESS}]]
             and attacks[-1][1] == PF_SUPPORT_SUBJECT,
             "PF lv3 must be special 6.25 x2 + the supporter attack (subject 203) with toughness 1")
    attacks[-1][13] = [{"min": NEW_PF_TOUGHNESS, "max": NEW_PF_TOUGHNESS} for _ in attacks[-1][13]]
    _require(pf_toughness(tree) == PF_TOUGHNESS_CAP[3], "PF lv3 toughness must land on the cap 25")
    return tree


def dsl_problems(tree):
    problems = [f"element: {p}" for p in legality.action_dsl_element_problems(tree, DARK_ELEMENT)]
    problems += [f"subject: {p}" for p in legality.action_dsl_subject_binding_problems(tree)]
    problems += [f"scope: {p}" for p in legality.action_dsl_lookup_scope_problems(tree)]
    problems += [f"hit_target: {p}" for p in legality.action_dsl_hit_area_target_problems(tree)]
    if wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"] != tree:
        problems.append("AMF3 roundtrip mismatch")
    return problems


def _row_problems(table, row, strings):
    problems = (legality.client_legality_problems(table, row)
                + legality.declared_block_field_problems(table, row)
                + legality.ability_element_column_problems(table, row, DARK_ELEMENT)
                + legality.invoke_skill_string_problems(row, strings, table))
    shift = 0 if table == "ability" else 2
    kind = row[47 - shift]
    if kind in ("536", "722"):
        key = row[(84 if kind == "722" else 70) - shift]
        if key not in strings:
            problems.append(f"missing native ability description {key!r}")
    return problems


def panel_problems(key, text):
    problems = [f"{key}: forbidden phrase {p!r}" for p in FORBIDDEN_PANEL_PHRASES if p in text]
    problems += [f"{key}: {p}" for p in kit_panel_problems(text)]
    if "\\n" in text:
        problems.append(f"{key}: literal backslash-n")
    main = [line.startswith(MAIN_ICON) for line in text.split("\n")]
    if key == TEXT_A3 and not all(main):
        problems.append(f"{key}: every main-only line must start with the main icon")
    if key != TEXT_A3 and any(main):
        problems.append(f"{key}: unrestricted panel must not carry the main icon")
    return problems


def validate(result, strings):
    problems = []
    for table, group in (("ability", result["ability"]), ("leader_ability", result["leader"])):
        for key, rows in group.items():
            for index, row in enumerate(rows, 1):
                problems += [f"{table}:{key}#{index} {p}" for p in _row_problems(table, row, strings)]
    for key, rows in result["cas"].items():
        problems += panel_problems(key, _text(rows, key))
    for program, tree in result["dsl"].items():
        problems += [f"dsl:{program} {p}" for p in dsl_problems(tree)]
    needed = set()
    for table, group in (("ability", result["ability"]), ("leader_ability", result["leader"])):
        for rows in group.values():
            for row in rows:
                needed |= set(legality.required_client_capabilities(table, row))
    for key in result["cas"]:
        needed |= set(legality.required_client_capabilities(legality.CUSTOM_ABILITY_STRING_KIND, [key]))
    if needed != set(CAPABILITIES):
        problems.append(f"capabilities {sorted(needed)} != declared {CAPABILITIES}")
    return problems


def revise(read):
    inputs = {}
    for (kind, key), expected in BEFORE.items():
        value = deepcopy(read(kind, key))
        if digest(value) != expected:
            raise ValueError(f"{CID} balance 20260927b: live drift at {kind}:{key}; re-review before revising")
        inputs[kind, key] = value
    _require(inputs["table", PF_ACTION] == [list(PF_PROGRAMS)],
             "power_flip_action no longer points at the reviewed three PF programs")

    a3_live = inputs["ability", A3]
    a3 = ability3_rows(a3_live)
    leader = leader_rows(inputs["leader", CID], a3_live)
    cas = {
        TEXT_LEADER: [[leader_text(_text(inputs["cas", TEXT_LEADER], TEXT_LEADER))]],
        TEXT_A3: [[ability3_text(_text(inputs["cas", TEXT_A3], TEXT_A3))]],
    }
    trees = {PF_LV3: pf_lv3_tree(inputs["dsl", PF_LV3])}
    result = {"ability": {A3: a3}, "leader": {CID: leader}, "cas": cas,
              "text": {}, "table": {}, "action": {}, "dsl": trees, "server_text": {},
              "new_programs": []}
    strings = {key for kind, key in inputs if kind == "cas"} | set(cas)
    problems = validate(result, strings)
    if problems:
        raise ValueError("; ".join(problems))
    result["notes"] = notes()
    return result


def notes():
    return {
        "character": f"{CID} {CODE}（校园奈芙提姆）",
        "scope": "2026-09-27 第二批：无上限成长（口径 A，growth critic C01）+ Down PF Lv3（口径 B.2）",
        "changes": [
            {"where": "ability:1699893#3（能力3，整键仅主位）", "before": "T235 贯穿每累计2秒 → 暗队攻击力 +10%，c34 (None)",
             "after": "c34 10；c51/c52 10000→5000（最多 +50%）", "basis": "口径 A.3 能力栏换有上限弱化版；C01 fix (2)"},
            {"where": "ability:1699893#4", "before": "T235 贯穿每累计2秒 → 暗队直击伤害 +10%，c34 (None)",
             "after": "c34 10；强度保持 10000（最多 +100%）", "basis": "口径 A.3；C01 fix (2)"},
            {"where": "leader_ability:169989#9、#10（新增）", "before": "（无）",
             "after": "[CODE,'0',''] + 能力3 行3/行4[5:]；c49/c50 10000→1000（暗队攻击力/直击 各 +1%/次），c32 (None)",
             "basis": "口径 A.3 搬队长 + A.2 放缓 1/10；A.4 先例 T235=169999#7-9、前置12=149989#4-6；队长无 T235 行，不合并"},
            {"where": "leader_ability:169989#5", "before": "每35连击 → 暗队 Fever 获得量 +20%（c49/c50 20000），c32 (None)",
             "after": "c49/c50 2000（+2%）", "basis": "口径 A.3 已在队长原位放缓 + A.2 1/10；A.6 Fever 获得量不算充能"},
            {"where": "custom_ability_string:desc_override_ruin_girl_campus",
             "before": "第5行 Fever 槽上升量+20%", "after": "+2%；末尾追加「…每累计2秒，暗属性角色攻击力+1%、直接攻击伤害+1%。」",
             "basis": "口径 D 节面板规则（写到效果为止，不写「可无限累积」）"},
            {"where": "custom_ability_string:desc_override_ruin_girl_campus_3",
             "before": "第2行 攻击力+10%、直接攻击伤害+10%", "after": "攻击力+5%、直接攻击伤害+10%（最多10次）",
             "basis": "口径 D 节「（最多N次）」"},
            {"where": "dsl:" + PF_LV3 + " 辅助型末段 CreateNormalAttack（主体 203）p13",
             "before": "[{min:1,max:1}]（Lv3 削韧 26）", "after": "[{min:0,max:0}]（Lv3 削韧 25）",
             "basis": "口径 B.2「奈芙提姆 PF Lv3 末段 1→0（26→25）」；B.6 只改 p13"},
        ],
        "frequency_estimates": {
            "fever_minutes_basis": ("3 分钟战斗；Fever 基础 900 帧（15 秒），队长 Fever 时间 +100% → 30 秒/次；"
                                    "能力3 行5 每 45 次暗直击 Fever 槽 +15%（Fever 中延长），多球 + 直击分段使直击数很高，"
                                    "Fever 覆盖率按 50–70% 估，即 Fever 中 90–126 秒"),
            "piercing_growth_T235": ("贯穿覆盖：能力5 Fever 中每 5 秒给 3 秒贯穿 × 能力2 贯穿时间 +40% = 4.2/5 秒（84%），"
                                     "技能另给贯穿 → Fever 中贯穿约 85–100%；每 120 帧一跳 → 3 分钟约 38–63 次"
                                     "（Fever 覆盖只有 40% 时也约 30 次）；≥30 次 → 1/10：10%→1%"),
            "fever_gain_T12": ("每 35 连击一跳；多球（最多 9 个协力球）+ 队长「每个协力球 +1 直击判定」+ Fever 中直击分段，"
                               "3 分钟约 1200–3000 连击 → 约 34–85 次；≥30 次 → 1/10：20%→2%"),
            "precision": "两处都取 1/10；队长新行与能力3 同一强度精度（千分之一整数）",
        },
        "totals_3min_as_leader": {
            "dark_attack_from_piercing": "原 +380–630%（38–63 次 × 10%）→ 队长 +38–63% + 能力3 +50%（封顶）",
            "dark_direct_from_piercing": "原 +380–630% → 队长 +38–63% + 能力3 +100%（封顶）",
            "dark_fever_gain": "原 +680–1700% → +68–170%",
        },
        "down": {"pf_toughness_before": {"1": 15, "2": 20, "3": 26},
                 "pf_toughness_after": {"1": 15, "2": 20, "3": 25},
                 "cap": PF_TOUGHNESS_CAP, "levels_1_2": "已顶格，不改"},
        "precedents": {"leader_T235": "live leader 169999#7-9（基诺维，T235 → I32/I34/I388 目标5，c30/c31 阈值2）",
                       "leader_pre12": "live leader 149989#4-6（校园希尔媞，c11=12）",
                       "legality": "新行 client_legality / declared_block_field / element_column / invoke_skill_string 均为空"},
        "unchanged": ["ability 1699893 第1、2、5、6行", "leader 169989 第1-4、6-8行",
                      "ability 1699891/1699892/1699894..1699896", "PF Lv1/Lv2 程序", "PF Lv3 其余节点（伤害、判定区、增益）",
                      "change_skill / powerflip / ball_hit_count / multiball_direct 原生串",
                      "action_skill / character_text 主动说明（不含这些数值）",
                      "表二充能：队长第7行「协力球消失时暗队技能槽+5%」（作者：其他充能暂时不动）"],
        "gameplay_semantics": [
            "能力3 贯穿成长每场最多各 10 次（约 20 秒 Fever 中贯穿），之后只剩队长的 1%/次",
            "队长两行只在自身为队长、暗共鸣、Fever 中生效，永久累积（写到效果为止）",
            "非队长主位：只有能力3 的封顶部分（原来每次 10%/10% 不限次）",
            "队长 Fever 获得量成长 +20%→+2%/35连击：Fever 覆盖率会下降，Fever 系收益（能力3/4、召唤）随之减少",
            "PF Lv3：辅助型末段的伤害与增益不变，只去掉 1 点削韧",
        ],
        "generator_sync": ["mod-tools/wf_nephtim_fever_abilities.py（PIERCING_CAPPED_*、LEADER_PIERCING_GROWTH_STRENGTH、"
                           "piercing_growth_rows、_instant limit）",
                           "mod-tools/wf_nephtim_fever_leader.py（FEVER_GAIN_GROWTH_STRENGTH，第9、10行）",
                           "mod-tools/wf_nephtim_fever_text.py（队长/能力3 面板）",
                           "mod-tools/wf_nephtim_fever_powerflip.py（SUPPORTER_TOUGHNESS）"],
        "candidate_notes": [
            "两个候选的目标键（1699893、169989、两个 desc_override）与 live 逐字相同，manifest 零漂移",
            "PF Lv3 程序只在 owner 候选里；暂存脚本对每个包都 emit DSL，副本 campus-nephtim-20260911 会新增一个"
            "孤立的 lv3 程序条目（无 lv1/lv2 与私有特效族），与第一批三棵 DSL 两包都写的处理一致；副本不得作为 flow publish 源",
        ],
        "runtime_verified": False,
    }
