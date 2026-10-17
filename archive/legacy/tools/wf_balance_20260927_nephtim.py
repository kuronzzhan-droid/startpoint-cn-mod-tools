"""校园奈芙提姆 169989：2026-09-27 作者确认的平衡修订（方案B：只把 I536 技能强化搬进队长）。

纯函数模块：revise(read) 只经 read() 读取 live，返回有变化的键；不写 live store、
候选工作区、assets 或 .cdn（批次暂存脚本统一回写）。

规格：
1. 能力1（1699891，整键仍主位限制）：删除第2行 I536；召唤行（629/T232）
   threshold2 c32/c33 9000000 → 12000000（1.5 秒 → 2 秒）；召唤/清理三行留在能力1。
2. 队长 169989：删除「Fever 中技能槽上限+10%」（during 124）与「贯穿延长20%」（I190），
   在 I722 之后插入 I536（= [CODE,'0',''] + 原能力1第2行[5:]，与官方 121189#3 同形）；9 行 → 8 行。
3. 能力2（1699892，c1=true）：I190 20000 → 40000（并入队长那份）；追加队长搬来的 during 124 行。
4. 面板：desc_override 队长 / _1 / _2 同步改写；change_skill 与 fever_spawn 原生串不改。
5. 多人卡顿修复（方案1，K=10）：三条「经过时间 T77 → 629」行（队长 ball_hit_count、能力3 第6行
   multiball_direct、能力4 第2行 multiball_direct_a4）周期 100000 → 1000000（每 1 帧 → 每 10 帧）；
   对应三棵 DSL 的隐形状态持续帧 2 → 20（= 2 × 周期），其余节点逐格不动。面板文字不改。
生成器（wf_nephtim_fever_abilities/leader/text、wf_nephtim_ball_hit_count、
wf_nephtim_multiball_direct/fever）已同步，测试断言生成器输出 == revise()。
"""
from copy import deepcopy
import hashlib
import json

import wf_client_legality as legality
import wf_dsl

CID = "169989"
CODE = "ruin_girl_campus"
# 第一个是 active owner（canonical manifest 哈希 366a4fa0… 与 active.json 一致）；
# 第二个是 Codex 9/24-9/25 写回的同 package_id 副本，只镜像本次目标键。
PACKAGES = ["nephtim-summon-cap-20260916/ruin_girl_campus", "campus-nephtim-20260911"]
PACKAGE_VERSION = {
    "nephtim-summon-cap-20260916/ruin_girl_campus": "0.2.3",   # 现值 0.2.2
    "campus-nephtim-20260911": "0.20260927",                   # 现值 0.20260925（日期式版本）
}
# 三个 desc_override_* 覆盖行需要 V14 面板覆盖补丁；owner 已声明，副本 manifest 缺这一项。
# 能力3（1699893）整键回写含第5行 I724（只有比例版客户端解析）；owner 已声明，副本 manifest 缺这一项。
CAPABILITIES = ["kyubi-fever-ratio-v1", "panel-description-override-v2"]

A1, A2, A3, A4 = (CID + str(slot) for slot in (1, 2, 3, 4))
TEXT_LEADER = "desc_override_" + CODE
TEXT_A1 = TEXT_LEADER + "_1"
TEXT_A2 = TEXT_LEADER + "_2"
CHANGE_SKILL_STRING_ID = "change_skill_" + CODE + "_fever"
SPAWN_STRING_ID = CODE + "_fever_spawn"
BALL_HIT_STRING_ID = CODE + "_ball_hit_count"
PF_STRING_ID = CODE + "_fever_powerflip"
A3_STRING_ID = CODE + "_multiball_direct"
A4_STRING_ID = CODE + "_multiball_direct_a4"
PROGRAM_PREFIX = "battle/action/skill/action/ability_skill/" + CODE + "$"
BALL_HIT_PROGRAM = PROGRAM_PREFIX + BALL_HIT_STRING_ID
A3_PROGRAM = PROGRAM_PREFIX + A3_STRING_ID
A4_PROGRAM = PROGRAM_PREFIX + A4_STRING_ID
# 多人卡顿修复（方案1）：T77 阈值列单位 帧×100000；K=10 帧，状态持续 2K 帧。
REFRESH_FRAMES = 10
OLD_REFRESH, NEW_REFRESH = "100000", str(REFRESH_FRAMES * 100_000)
OLD_TTL, NEW_TTL = 2, 2 * REFRESH_FRAMES
# 程序路径 -> (CreateCondition 键 = 串键, 条件节点数, AC 内容种类)
REFRESH_PROGRAMS = {
    BALL_HIT_PROGRAM: (BALL_HIT_STRING_ID, 2, "ACAdditionalDirectAttack"),
    A3_PROGRAM: (A3_STRING_ID, 2, "ACSeparatedTermDirectDamage"),
    A4_PROGRAM: (A4_STRING_ID, 1, "ACSeparatedTermDirectDamage"),
}
MAIN_ICON = " <icon id='main'>  "
DARK_ELEMENT = 5                      # master/character c3 内部 ElementKind（暗）
OLD_PERIOD, NEW_PERIOD = "9000000", "12000000"   # 帧×100000：90 帧 → 120 帧
OLD_PERIOD_TEXT, NEW_PERIOD_TEXT = "每经过1.5秒", "每经过2秒"
LEADER_PIERCING_STRENGTH = 20_000
A2_PIERCING_STRENGTH = 20_000
MERGED_PIERCING_STRENGTH = 40_000
OLD_PIERCING_LINE = "暗属性共鸣时，全队贯穿效果时间+20%。"
NEW_PIERCING_LINE = "暗属性共鸣时，全队贯穿效果时间+40%。"
GAUGE_MAXIMUM_LINE = "暗属性共鸣时，Fever 模式中，暗属性角色技能槽上限+10%。"
# 官方队长 121189#3（dryad_hw23）I536 行的非空列集合；搬来的行必须逐列同形。
OFFICIAL_LEADER_536_COLUMNS = (0, 1, 3, 4, 7, 8, 9, 11, 18, 25, 37, 44, 45, 68)
FORBIDDEN_PANEL_PHRASES = ("自身为队长时", "觉醒后", "生命值100%以下", "／")

BEFORE = {
    ("ability", A1): "f05ad1fe005811968bee3fdee84472a3547b21db48f4a5b3701e30257571cdd4",
    ("ability", A2): "682f9ddec1170dbdd0d87a9669b3064d66915088742ce982232ab0064fac65fc",
    ("leader", CID): "54b699b5b897684ebc4eccc32e5453e2d4f790dd4c9da185ceed0f74c895b035",
    ("cas", TEXT_LEADER): "17fb06e34a749bf2783e09ba62491f042ccd5de33de9e88d0780538f95b331a9",
    ("cas", TEXT_A1): "928c9ad2fc94a0f60b23d70224e772c3beb67c3ba6e44a88ae53b0d475e02a6d",
    ("cas", TEXT_A2): "3464fb72cbcc24b86c4cf75eb0178de423aee2be7df75b0433d3c9753981f112",
    # 下列原生串不改，只作存在性与未漂移校验（I536/I629/I722 行的文案键）。
    ("cas", CHANGE_SKILL_STRING_ID): "0d967429bc2adeef5ed12f67863d6492cfe7e08cd04968475d9ba56e7cbf4ed4",
    ("cas", SPAWN_STRING_ID): "af8858e225a79082d291e6f108fd6de11a446653669263a9ccb74363fe1db4d6",
    ("cas", BALL_HIT_STRING_ID): "ea0d1d398be6943e4e0d4b4a48a1bf7e2860a3b225649a51d6e29d035e18edc1",
    ("cas", PF_STRING_ID): "1e23cda7f5c6b06be276398ca7b52891ac751faa11ab75e276cdbe4e95ff05c0",
    # 多人卡顿修复：能力3/4 整键、两条 629 行的原生串（不改，存在性校验）与三棵 DSL。
    ("ability", A3): "b257c30fd11b755572c9d7ef739e9554fbc4aa804ba889fd3fef53a1f18cb58a",
    ("ability", A4): "96b4bc8907a7e720db50fa990758929300ae68e62c0bfa7bca9f3789ce4ab77a",
    ("cas", A3_STRING_ID): "279e6b6ca9ca6ce39e1f5a760e71cf7846e0b9aa450ca9e9084a009b2ae2239e",
    ("cas", A4_STRING_ID): "566cd31b35a76b0c223468f71203baf4dc74c2385b90f6d07880beec5c567604",
    ("dsl", BALL_HIT_PROGRAM): "f0929284829bf084ab797f11bc0e9eed4a4db9718a078600a04ee4f9caa7e4fa",
    ("dsl", A3_PROGRAM): "d625ff52296c1c73041ca69e71780db0e944c9c84f322bcf31137daf8b5c6085",
    ("dsl", A4_PROGRAM): "c54d75beaff8db5b724df47d21ab5ee23d0f601fecaa14591c6bb112eebb70d5",
}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _require(condition, message):
    if not condition:
        raise ValueError(f"{CID} balance 20260927: {message}")


def _shape(rows, count, width, string_id):
    _require(isinstance(rows, list) and len(rows) == count, f"{string_id}: expected {count} rows")
    for row in rows:
        _require(len(row) == width and row[0] == string_id,
                 f"{string_id}: expected {width}-column rows with c0={string_id}")


def _text(rows, key):
    _require(len(rows) == 1 and len(rows[0]) == 1 and isinstance(rows[0][0], str),
             f"{key}: expected one text cell")
    return rows[0][0]


def ability1_rows(rows):
    """返回 (新能力1四行, 被移出的 I536 行)；召唤行间隔改为 2 秒，其余格不动。"""
    _shape(rows, 5, 126, CODE + "_1")
    _require({row[1] for row in rows} == {"false"}, "ability1 must stay main-only")
    opening, enhance, summon, clear, reconcile = deepcopy(rows)
    _require(opening[47] == "211", "ability1 row1 must be the opening charge (I211)")
    _require((enhance[3], enhance[4], enhance[5], enhance[27], enhance[47], enhance[70])
             == ("0", "", "0", "0", "536", CHANGE_SKILL_STRING_ID),
             "ability1 row2 must be the I536 skill-enhancement flag")
    _require((summon[5], summon[27], summon[47], summon[70]) == ("0", "232", "629", SPAWN_STRING_ID)
             and summon[32:34] == [OLD_PERIOD] * 2,
             "ability1 row3 must be the 1.5-second T232 summon")
    _require((clear[27], clear[47]) == ("184", "528") and (reconcile[27], reconcile[47]) == ("77", "528"),
             "ability1 rows 4-5 must be the two I528 state clean-ups")
    summon[32:34] = [NEW_PERIOD] * 2
    return [opening, summon, clear, reconcile], enhance


def leader_rows(rows, enhance):
    """返回 (新队长八行, 被移出的 during124 行, 被移出的 I190 行)。"""
    _shape(rows, 9, 124, CODE)
    pf, direct, attack, maximum, piercing, growth, duration, removal, hits = deepcopy(rows)
    _require(pf[45] == "722", "leader row1 must be the special power flip (I722)")
    _require((maximum[3], maximum[11], maximum[95], maximum[107], maximum[108], maximum[109])
             == ("1", "12", "4", "124", "5", "Black") and maximum[111:113] == ["10000"] * 2,
             "leader row4 must be the Fever dark skill-gauge maximum +10% (during 124)")
    _require((piercing[3], piercing[25], piercing[45]) == ("0", "0", "190")
             and piercing[49:51] == [str(LEADER_PIERCING_STRENGTH)] * 2,
             "leader row5 must be the constant piercing extension +20% (I190)")
    _require((hits[45], hits[68]) == ("629", BALL_HIT_STRING_ID),
             "leader row9 must be the 9/25 ball-hit-count row")
    moved = [CODE, "0", ""] + deepcopy(enhance[5:])
    _require(len(moved) == 124, "relocated I536 row must have 124 columns")
    _require([i for i, v in enumerate(moved) if v != ""] == list(OFFICIAL_LEADER_536_COLUMNS),
             "relocated I536 row must match the official leader 121189#3 column shape")
    hits = slow_refresh(hits, "leader_ability", BALL_HIT_STRING_ID)
    return [pf, moved, direct, attack, growth, duration, removal, hits], maximum, piercing


def slow_refresh(row, table, string_id):
    """T77→629 行的周期 1 帧 → REFRESH_FRAMES 帧（能力表 c30/c31，队长表列−2），其余格不动。"""
    s = 0 if table == "ability" else 2
    _require((row[27 - s], row[47 - s], row[70 - s], row[71 - s])
             == ("77", "629", string_id, PROGRAM_PREFIX + string_id)
             and row[30 - s:32 - s] == [OLD_REFRESH] * 2,
             f"{table} {string_id}: expected the every-frame T77 invoke-skill row")
    row = deepcopy(row)
    row[30 - s:32 - s] = [NEW_REFRESH] * 2
    return row


def ability3_rows(rows):
    """能力3 第6行 multiball_direct 改为每 10 帧；其余五行逐格不动。"""
    _shape(rows, 6, 126, CODE + "_3")
    _require({row[1] for row in rows} == {"false"}, "ability3 must stay main-only")
    _require([i for i, row in enumerate(rows) if row[27] == "77"] == [5],
             "ability3 row6 must be its only T77 row")
    return deepcopy(rows[:5]) + [slow_refresh(rows[5], "ability", A3_STRING_ID)]


def ability4_rows(rows):
    """能力4 第2行 multiball_direct_a4（Fever 中）改为每 10 帧；第1行 during 不动。"""
    _shape(rows, 2, 126, CODE + "_4")
    _require({row[1] for row in rows} == {"true"}, "ability4 must stay unrestricted")
    _require(rows[0][27] != "77", "ability4 row1 must stay the during row")
    return [deepcopy(rows[0]), slow_refresh(rows[1], "ability", A4_STRING_ID)]


def refresh_tree(tree, program):
    """隐形状态持续帧 2 → 20（= 2 × 周期）；只改各 CreateCondition 的 AC 内容第1参，其余节点逐格不动。"""
    key, count, content_kind = REFRESH_PROGRAMS[program]
    tree = deepcopy(tree)
    conditions = [node for node in wf_dsl.iter_dsl_commands(tree) if node[0] == "CreateCondition"]
    _require(len(conditions) == count, f"{program}: expected {count} CreateCondition nodes")
    for node in conditions:
        _require(node[7] == key and len(node[2]) == 1 and node[2][0][0] == content_kind
                 and node[2][0][1] == [{"min": OLD_TTL, "max": OLD_TTL}],
                 f"{program}: expected one {OLD_TTL}-frame {content_kind} keyed {key}")
        node[2][0][1] = [{"min": NEW_TTL, "max": NEW_TTL}]
    return tree


def dsl_problems(tree):
    problems = [f"element: {p}" for p in legality.action_dsl_element_problems(tree, DARK_ELEMENT)]
    problems += [f"subject: {p}" for p in legality.action_dsl_subject_binding_problems(tree)]
    problems += [f"scope: {p}" for p in legality.action_dsl_lookup_scope_problems(tree)]
    problems += [f"hit_target: {p}" for p in legality.action_dsl_hit_area_target_problems(tree)]
    if wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"] != tree:
        problems.append("AMF3 roundtrip mismatch")
    return problems


def ability2_rows(rows, maximum, piercing):
    """I190 合并为单行 40%；队长 during124 行按列+2 追加为第3行（c1=true 不加主位限制）。"""
    _shape(rows, 2, 126, CODE + "_2")
    _require({row[1] for row in rows} == {"true"}, "ability2 must stay unrestricted")
    extension, direct = deepcopy(rows)
    _require((extension[27], extension[47]) == ("0", "190")
             and extension[51:53] == [str(A2_PIERCING_STRENGTH)] * 2,
             "ability2 row1 must be the constant piercing extension +20% (I190)")
    # 队长那份与能力2这份除强度外逐列同形（能力[5:] == 队长[3:]），合并不改变条件。
    _require(extension[5:] == piercing[3:], "leader/ability2 I190 rows must share one form")
    _require((direct[47], direct[48], direct[51]) == ("33", "5", "250000"),
             "ability2 row2 must be the dark direct damage +250%")
    total = int(extension[51]) + int(piercing[49])
    _require(total == MERGED_PIERCING_STRENGTH, "merged piercing extension must total 40%")
    extension[51:53] = [str(total)] * 2
    gauge = [CODE + "_2", "true", "attack_black"] + deepcopy(maximum[1:])
    _require(len(gauge) == 126 and gauge[3:6] == ["0", "", "1"],
             "relocated during-124 row must be a 126-column during row")
    return [extension, direct, gauge]


def leader_text(text, a1_text):
    lines = text.split("\n")
    _require(len(lines) == 8 and lines[2] == GAUGE_MAXIMUM_LINE and lines[6] == OLD_PIERCING_LINE,
             "unexpected leader panel lines")
    enhancement = [line[len(MAIN_ICON):] for line in a1_text.split("\n")[1:3]]
    return "\n".join([lines[0], *enhancement, lines[1], *lines[3:6], lines[7]])


def ability1_text(text):
    lines = text.split("\n")
    _require(len(lines) == 6 and all(line.startswith(MAIN_ICON) for line in lines),
             "unexpected ability1 panel lines")
    _require(lines[1].startswith(MAIN_ICON + "暗属性共鸣时，强化『")
             and "强化后的技能发动时" in lines[2], "ability1 lines 2-3 must be the enhancement entry")
    _require(lines[3].count(OLD_PERIOD_TEXT) == 1, "ability1 summon line must state 1.5 seconds")
    return "\n".join([lines[0], lines[3].replace(OLD_PERIOD_TEXT, NEW_PERIOD_TEXT), *lines[4:]])


def ability2_text(text):
    lines = text.split("\n")
    _require(len(lines) == 2 and lines[0] == OLD_PIERCING_LINE, "unexpected ability2 panel lines")
    return "\n".join([NEW_PIERCING_LINE, lines[1], GAUGE_MAXIMUM_LINE])


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


def _panel_problems(key, text):
    problems = [f"{key}: forbidden phrase {p!r}" for p in FORBIDDEN_PANEL_PHRASES if p in text]
    if "\\n" in text:
        problems.append(f"{key}: literal backslash-n")
    main = [line.startswith(MAIN_ICON) for line in text.split("\n")]
    if key == TEXT_A1 and not all(main):
        problems.append(f"{key}: every main-only line must start with the main icon")
    if key != TEXT_A1 and any(main):
        problems.append(f"{key}: unrestricted panel must not carry the main icon")
    return problems


def validate(result, strings):
    problems = []
    for table, group in (("ability", result["ability"]), ("leader_ability", result["leader"])):
        for key, rows in group.items():
            for index, row in enumerate(rows, 1):
                problems += [f"{table}:{key}#{index} {p}" for p in _row_problems(table, row, strings)]
    for key, rows in result["cas"].items():
        problems += _panel_problems(key, _text(rows, key))
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
            raise ValueError(f"{CID} balance 20260927: live drift at {kind}:{key}; re-review before revising")
        inputs[kind, key] = value

    a1, enhance = ability1_rows(inputs["ability", A1])
    leader, maximum, piercing = leader_rows(inputs["leader", CID], enhance)
    a2 = ability2_rows(inputs["ability", A2], maximum, piercing)
    old_a1_text = _text(inputs["cas", TEXT_A1], TEXT_A1)
    cas = {
        TEXT_LEADER: [[leader_text(_text(inputs["cas", TEXT_LEADER], TEXT_LEADER), old_a1_text)]],
        TEXT_A1: [[ability1_text(old_a1_text)]],
        TEXT_A2: [[ability2_text(_text(inputs["cas", TEXT_A2], TEXT_A2))]],
    }
    a3 = ability3_rows(inputs["ability", A3])
    a4 = ability4_rows(inputs["ability", A4])
    trees = {program: refresh_tree(inputs["dsl", program], program) for program in REFRESH_PROGRAMS}
    result = {"ability": {A1: a1, A2: a2, A3: a3, A4: a4}, "leader": {CID: leader}, "cas": cas,
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
        "scheme": "B: only the I536 skill-enhancement flag moves to the leader; plus multiplayer lag fix scheme 1 (K=10)",
        "changes": [
            "ability:1699891 删除 I536 行（5→4 行，c1=false 不变）；召唤 T232 c32/c33 9000000→12000000（1.5秒→2秒）",
            "leader_ability:169989 删除 during124 技能槽上限+10% 与 I190 贯穿+20%；I722 之后插入 I536（121189#3 同形）；9→8 行，保留 9/25 的 629 ball_hit_count 行",
            "ability:1699892 I190 20000→40000；追加 during124 Fever 中暗属性技能槽上限+10%（c1=true，不加主位限制）",
            "custom_ability_string: desc_override_ruin_girl_campus / _1 / _2 同步改写",
            "多人卡顿修复：leader_ability:169989 第8行（ball_hit_count）c28/c29、ability:1699893 第6行（multiball_direct）"
            "与 ability:1699894 第2行（multiball_direct_a4）c30/c31 100000→1000000（T77 每 1 帧→每 10 帧），其余列不变",
            "多人卡顿修复：DSL ruin_girl_campus_ball_hit_count（2 个 CreateCondition）/ _multiball_direct（2 个）/"
            " _multiball_direct_a4（1 个）隐形状态持续帧 2→20，其余节点不变",
        ],
        "unchanged": ["unique_condition 16998901", "召唤 DSL（无周期常量）", "主动技能 DSL 1/2",
                      "ability 1699893 第1-5行、1699894 第1行、1699895..1699896",
                      "ability 1699891 第4行 T77 每帧 I528 清理行（不调 DSL，不在本次卡顿修复范围）",
                      "change_skill_ruin_girl_campus_fever / ruin_girl_campus_fever_spawn / "
                      "ruin_girl_campus_ball_hit_count / _multiball_direct / _multiball_direct_a4 原生串",
                      "面板文字（卡顿修复不改文案）", "action_skill / character_text 主动说明"],
        "gameplay_semantics": [
            "技能强化只在自身为队长（且暗共鸣）时生效；原来任意主位都生效",
            "当队长但能力1未解锁：有强化、星夜茶会与护盾，但不召唤",
            "非队长主位：能力1召唤/清理行拿不到星夜茶会，空转不误触发",
            "贯穿延长：唯一 I190 行在能力2；能力2已解锁时当队长仍 40%，非队长由 20% 升到 40%（超过官方能力 I190 满级 20%）",
            "Fever 中技能槽上限+10%：由仅队长扩大到任意位置（含合击副位），需能力2已解锁",
            "当队长但能力2未解锁（玛纳盘未点）：贯穿延长 20%→0%，Fever 中技能槽上限+10% 也不生效（旧队长两行不依赖能力解锁）",
            "召唤 2 秒：9 球上限由 13.5 秒推迟到 18 秒，仍在 20 秒星夜茶会窗口内",
            "卡顿修复：协力球数量变化后，直击判定次数与两份独立乘区直击加成最多晚 10 帧（1/6 秒）更新；新召唤的协力球最多 10 帧后才拿到加成",
            "卡顿修复：技能多段直击增益（DCAdditionalDirectAttack）开始/结束与队长直击判定次数的基数切换最多错位 10 帧",
            "卡顿修复：失去条件（离开主位/倒下/共鸣或 Fever 失效/能力未解锁）后隐形状态最多残留 20 帧（原 2 帧）",
        ],
        "performance_fix": {
            "request": "作者 2026-09-27：校园奈芙叫协力球在多人默认会导致帧数下降变卡",
            "cause": ("3 条 T77（经过时间，阈值 100000 = 每 1 帧）→ 629 行每帧执行一次 DSL，给自身/队员/协力球挂持续 2 帧的隐形状态；"
                      "联机时每台客户端本机模拟全部队友战斗，开销随带奈芙的人数放大"),
            "scheme": "方案1：K=10，周期 1 帧→10 帧，状态持续 2 帧→20 帧（= 2K，相邻两次刷新之间留一个周期余量不断档）",
            "rows": {"leader_ability:169989#8": BALL_HIT_STRING_ID, "ability:1699893#6": A3_STRING_ID,
                     "ability:1699894#2": A4_STRING_ID},
            "period_frames": {"before": 1, "after": REFRESH_FRAMES},
            "condition_duration_frames": {"before": OLD_TTL, "after": NEW_TTL},
            "helper_invocations_per_second_per_row": {"before": 60, "after": 60 // REFRESH_FRAMES},
            "native_basis": "ThresholdElapsedTimeListener：floor(rawFrame / thresholdFrame) 每跨一个边界 thresholdCountUp 一次；同周期 T77 行共用监听器",
        },
        "precedents": {"leader_I536": "official leader 121189#3 (dryad_hw23); live 149999#12",
                       "ability_during124_target5": "live 1199893#1 / 1199962#1 / 1399953#5 (official 0)"},
        "generator_sync": ["mod-tools/wf_nephtim_fever_abilities.py", "mod-tools/wf_nephtim_fever_leader.py",
                           "mod-tools/wf_nephtim_fever_text.py", "mod-tools/wf_nephtim_ball_hit_count.py",
                           "mod-tools/wf_nephtim_multiball_direct.py", "mod-tools/wf_nephtim_multiball_fever.py"],
        "candidate_notes": [
            "owner nephtim-summon-cap-20260916/ruin_girl_campus 落后 live 的 9/25 内容（leader 行9、ball_hit_count 串与 DSL、技能/召唤 DSL、action_skill/character_text）与 9/24 UI；本次 leader 整键按新 live 值替换，其余漂移不在本次范围",
            "campus-nephtim-20260911 的 ability 1699891..6 仍是 0.1.0 旧行；本次只镜像目标键（1699891..1699894 整键替换为新 live 值），manifest 缺 panel-description-override-v2 与 kyubi-fever-ratio-v1（1699893 第5行 I724）",
            "三棵 DSL 两包都写：owner 的 skills.programs 只列 multiball_direct/_a4（缺 ball_hit_count），副本只列 ball_hit_count；programs 列表仅为说明性字段，本次不改（new_programs 为空，这三棵在 live 已存在）",
        ],
        "runtime_verified": False,
    }
