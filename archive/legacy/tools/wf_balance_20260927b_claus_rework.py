"克劳斯「蚀水狩阵」（129997 claude_wolf_assassin_ex）：作者 2026-09-27 小重做（在第二批 live 1.4.1051 之上）。\n\n作者原话（聊天，已授权）：技能描述带「引爆」但实际没有，面板与效果不一致 → 小重做：\n技能给 5 个攻击力提升效果、每个 +100%；对范围内敌人 25 倍按直击计算并附加 2 层淬毒；敌方水耐性 -10%；\n队长特殊强化弹射保留辅助段、泡泡增多、每个泡泡打 15 次、按直击计算；淬毒上限仍 20；\n队长新增「敌人每 2 层淬毒，水属性角色直击判定 +1（满 20 层每人直击打 10 下）」；\n能力2 PF 淬毒写简单：发动强化弹射固定额外 3 层；能力3 强化弹射直击乘区 → 对中毒敌人 +15%，只写一行；\n能力面板写「强化中毒」。作者对方案问题的选择：①队长直击 +N 照原话做，接受首领更频繁虚弱与 Lv3 连发；\n②泡泡命中计入连击（incrementCombo 保持 true）；③能力3 用 PoisonSlayer 类（instant 117）只写一行。\n主会话确认的默认值：泡泡 2/4/6 个、每个 15 段、每级 PF 总倍率不变、削韧按 15/20/25 重摊；\n技能 _2 满级 25 倍、_1 按比例 16.67 倍、buffTargetAs=4、削韧每段 2；技能命中另写一条 ACUnique 2 层、删能力6 行3；\n水耐性 -0.15 → -0.10；5 个攻击 buff 给水属性主队（沿用现有选择器 113 [2]），用 5 个不同区分键；\n能力2 三行合一；能力面板「强化中毒：技能与强化弹射附加的中毒伤害大幅提升」；技能描述 8 处统一去掉「引爆」。\n\n施工依据：主会话调研与方案（research[]/design.claus.plan/critique.issues，按其中的节点路径施工并落实复核修正）；\n接口见 ${WF_ROOT}/out/平衡调整批次-20260927/module_contract.md（第二批 b 后缀，口径 D 节）。\n\n改动总表（所有预像按 live 1.4.1051 锁定，见 BEFORE；漂移一律拒绝）：\n\n1. 技能两档 DSL（rare5/claude_wolf_assassin_ex_1/_2）：\n   - 判定区（-18 跟球 Circle 200、600 帧、10 段、Some 10）tree[24] buffTargetAs 0 → 4（按直击乘区结算）。\n   - onHit CreateNormalAttack p6 每段倍率：_2 [1.5→1.75] → [15/7→2.5]（满级 10 段合计 25 倍）；\n     _1 [7/6] → [5/3]（按 _1/_2 原比例 ×25/17.5，合计 16.67 倍）。削韧 p13=2（10 段 20 ≤ 30）、Fever 2.5 不动。\n   - onHit 末尾追加一条 CreateCondition(命中对象, ACUnique(129997, 2 层))，照官方 ice_dragon_1/_2 的写法。\n     单独一条：unique 表的 cancelable/forceApply 会覆盖整条命令；「每个敌人每次施放只 +2 层」依赖\n     unique_condition 129997 c10 force_apply='false'（重付与闸门），revise() 对 c10 做 fail-closed 检查。\n   - 3 个 FindAllSubjects(3,113,[2]) 空键 ACAttackPoint(1200, 0.6) → 1 个 FindAllSubjects(3,113,[2]) 内 5 条\n     ACAttackPoint(1200, 1.0)，区分键 攻撃力アップ1..5（官方 ruin_lady_meteor23_1 同写法，2 键）。\n     条件 ID 规则（ConditionId_Impl_.as:23-69）：键非空时 ID = D//<来源>/<构造名>/<键>，5 键 → 5 个独立条件；\n     同次施放的去重哈希（ActionEvaluator.as:3285-3308/5251）也含区分键，所以 5 条不会被合并。\n   - FindAllSubjects(4,49) 的 ACToleranceOfElement 水 -0.15 → -0.1（forceApply 不改）。\n2. PF 三档 DSL（power_flip/…/claude_wolf_assassin_ex_pf_lv1/2/3）：辅助段、Lv3 开场全屏 1 段、Suppress 20 原样；\n   泡泡（爪击）1/3/5 → 2/4/6 个（深拷最后一个泡泡、嵌套 Wait 再加一层，间隔 7/7/6 帧），\n   NotifyPowerflipEnd 跟着后移到「最后一个泡泡 +18」：t19/33/43 → t26/40/49。\n   每个泡泡：寿命 20 → 72 帧，CalculatedUsingMaxNumOfHits 3 → 15，硬封顶 None → Some 15，buffTargetAs 4 不动；\n   onHit 的 ShakeCamera 1 移到 onCreate（每个泡泡震一次，免得每目标 90 段就震 90 次）；ACPoison 原样。\n   每段按「每级 PF 每目标总量守恒」重摊：倍率 11/60、0.1625、7/36（总 5.5/9.75/17.5 不变）；\n   削韧 0.5、0.3333、0.2666（总 15 / 19.998 / 23.994+开场 1=24.994，≤ 15/20/25）；Fever 0.6、0.9、1.0（总 18/54/90 不变）；\n   incrementCombo 保持 true（作者选择②）。Lv1/Lv2 辅助段 CreateCondition p5 的整数 6 → true（签名为 Boolean，\n   Lv3 与 wt26 母本都是 true；运行时 Boolean(6)=true，行为等价）。\n3. 队长 leader_ability 129997 追加第 10 行（下标 9）：形状照 live 校园奈芙 169989 下标 7\n   （T77 每 10 帧 → 629，09-27 卡顿修复后的参数），前置沿用本表水共鸣门（c4..c10 与本表下标 7 相同），\n   c68 = ``claude_wolf_assassin_ex_poison_hits``、c69 = 新 ability_skill DSL。\n   DSL：FindAllSubjects(10, 49 全体敌人) → BindConditionAccumulationVariable(10, vid1, DCUnique 129997, 除数 2, 上限 9)\n   → FindAllSubjects(11, 113 [2] 水属性主队) → CreateCondition(11, ACAdditionalDirectAttack(20 帧,\n   段数 1 + vlv(vid1), 直击伤害 +1.0, 1), 隐形, 强制付与, 每个敌人都付与(p6=true), 空键)。\n   段数 = floor(1 + min(层/2, 9))：0–1 层 1 段、2 层 2 段 …… 18 层起 10 段（作者括号「满 20 层每人直击打 10 下」）。\n   直击伤害 +1.0 与能力3 行4 DirectAttack2 的 +100% 相同：≥4 层顶替 DA2（先比段数）也不丢 +100%。\n4. 能力2 1299972：行1-3（trigger 63/64/65 → 413 淬毒 1/3/5 层）合成一行：以行1 为模板，trigger 63 → 2（发动强化弹射，\n   任意档），强度 → 300000（3 层）；行4（每层淬毒特攻 +50%，限 20）原样。4 行 → 2 行。\n5. 能力3 1299973：删行6-8（trigger 63/64/65 → 713 直击独立乘区 +15/45/75%）；新增一行＝行4 克隆\n   （常驻、前置 202 主位、对象水队）只改 c47 201 → 117（ConditionSlayer(Poison, All)）、c51/c52 → 15000（+15%）。8 行 → 6 行。\n6. 能力6 1299976：删行3（技能发动 → 413 淬毒 2 层；技能 DSL 自带 2 层后避免双倍）。行4/行5（技能发动时 100 倍/30 倍\n   能力伤害）保留。5 行 → 4 行。\n7. 面板与描述：新 CAS ``claude_wolf_assassin_ex_poison_hits``（队长 629 行文案）；\n   新 CAS ``desc_override_claude_wolf_assassin_ex_2``（整槽接管能力2 面板，3 行、换行分行、非主位不带图标）；\n   技能描述 8 处（action_skill 两档 c1、character_text c5/c7/c9、服务端 cdndata/character_text.json [5]/[7]/[9]）统一，\n   去掉「3 个」「引爆」。选择器仍是 113 [2]（只给主队水属性角色），描述按实际写「赋予水属性角色」而不是「全体队友」。\n\n候选：``work/character_packs/claude_wolf_assassin_ex``（manifest 0.1.1 → 0.1.2）。已审漂移同第二批（技能两档 DSL\n候选 == live、manifest 未重封；本次回写会把它们重封）。PF Lv1 与新 629 DSL 以新 root 进包。\n生成器：无可同步常量。包内 build_claw_pf.py / restore_pf_support.py / patch_* 等是 0818–0820 的一次性直写 live 脚本，\n输出早已不等于 live，禁止重跑；第二批 ``wf_balance_20260927b_klaus.py`` 锁的是 1.4.1049 预像，本次之后在新 live 上\n会 fail closed（设计如此，不要重跑、不要改）。本模块是这批数值的唯一真源。\n\n纯函数：只转换 ``read()`` 给出的 live 输入，不写任何文件。\n"
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math

import wf_balance_20260927b_klaus as batch2      # 只借第二批的单目标削韧度量（hit_areas / detoughness），不改它
import wf_client_legality as legality
import wf_dsl
import wf_midautumn_kitlib as kitlib

CID = "129997"
CODE = "claude_wolf_assassin_ex"
PACKAGES = [CODE]
#: 候选 manifest 现值 0.1.1（第二批回写后）→ 递增。
PACKAGE_VERSION = {CODE: "0.1.2"}
#: 新增 desc_override_* 面板覆盖行需要 V14 面板覆盖补丁才显示（没打补丁的客户端惰性不崩）。
CAPABILITIES = ["panel-description-override-v2"]
ELEMENT = 1  # master/character c3：水（0 基内部元素）

_R5 = "battle/action/skill/action/rare5/"
#: 候选既有漂移（与第二批相同：技能两档 DSL 候选文件 == live，manifest 哈希未重封）。
REVIEWED_DRIFT = {
    ("common", f"{_R5}{CODE}${CODE}_1.action.dsl.amf3.deflate"):
        "d440501bece36c789d7c09b28a364fe858a74b21f6ca991fce7f1019f244e41a",
    ("common", f"{_R5}{CODE}${CODE}_2.action.dsl.amf3.deflate"):
        "8e4910a78f9f909e9d22d59e74be7b958d5b4882af67178d7b3f95328f01d0bf",
}

SKILL_LEVELS = (1, 2)
SKILL_PROGRAMS = {level: f"{_R5}{CODE}${CODE}_{level}" for level in SKILL_LEVELS}
PF_LEVELS = (1, 2, 3)
PF_PROGRAMS = {level: f"battle/action/power_flip/action/override/{CODE}_pf${CODE}_pf_lv{level}"
               for level in PF_LEVELS}
PF_ACTION = ("master/skill/power_flip_action.orderedmap", f"{CODE}_pf")
UNIQUE = ("master/character/unique_condition.orderedmap", CID)
UNIQUE_ID = 129997
ABILITY = {2: "1299972", 3: "1299973", 6: "1299976"}

POISON_HITS_KEY = f"{CODE}_poison_hits"
POISON_HITS_PROGRAM = f"battle/action/skill/action/ability_skill/{CODE}${POISON_HITS_KEY}"
A2_OVERRIDE_KEY = f"desc_override_{CODE}_2"
NEW_KEYS = (("cas", POISON_HITS_KEY), ("cas", A2_OVERRIDE_KEY), ("dsl", POISON_HITS_PROGRAM))

BEFORE = {
    ("ability", ABILITY[2]): "1d2a5e2f7414814e59bdf7991f39aad92ae296752451d4754e8ccd4df65025d9",
    ("ability", ABILITY[3]): "451f04341f237799811a67e406c5de6a1885b05eb1d21273f6824acbe2fd587b",
    ("ability", ABILITY[6]): "05711161d27f436025f7eb11e24f60f50e3a08c71cdb46bf791696f1b2e25fd4",
    ("leader", CID): "7935043ebc1dce7fc6254d0317f66ec7bf4403f057ad796e80c188ca238d5392",
    ("text", CID): "e4d5e30632325c677f453562be2ca9cd4f1ea6af74f6f5fbe50f45a738b1040f",
    ("server_text", CID): "e4d5e30632325c677f453562be2ca9cd4f1ea6af74f6f5fbe50f45a738b1040f",
    ("action", CODE): "3c017fe5a36ee38a175683777483bf1fbf9c3840df0e9e9887f2b336cd149eea",
    ("dsl", SKILL_PROGRAMS[1]): "25572f31d1beecfd83bb05bfb471e23deb1af70cb459ee5b5dc90f6fab2465fb",
    ("dsl", SKILL_PROGRAMS[2]): "fcfc3be700b6aa5147427c23d45c56e412f1a2ff9e0b88004236393c5bbbb22d",
    ("dsl", PF_PROGRAMS[1]): "8ea4bb1d5008c1f41d1b4229bf9239dd981301dd4ae48302561cd3f27c944b01",
    ("dsl", PF_PROGRAMS[2]): "20702f749b2118847eadd8fcbd1723bff481940f04bd390c271ca7d5f32a11b8",
    ("dsl", PF_PROGRAMS[3]): "3d91eb57291c61563b9c65590c89fd3a2e2fe0319b19ede2f17b4830f3e487c6",
    ("table", UNIQUE): "4607c7f11a48ade0bb49b034200cdd4021037275174631571c58622bae7d8ecc",
    ("table", PF_ACTION): "aa5f7476ba53d6fd1b7deb754093753ef8384150e3aaa29f136a1eb620636968",
}

TOLERANCE = 1e-9


def slv(value) -> list:
    return [{"min": value, "max": value}]


# ================================================================ 技能

OLD_SKILL_DESC = ("赋予全体队友 3 个攻击力提升效果／对领域内的敌人造成水属性伤害并附加中毒／"
                  "施加 2 层「淬毒」并降低敌方水属性抗性／随即引爆「淬毒」，造成追加伤害")
NEW_SKILL_DESC = ("赋予水属性角色5个攻击力提升效果／在一段时间内对领域内的敌人造成水属性伤害"
                  "（伤害量以直接攻击伤害判定）＋ 赋予其中毒效果与2层「淬毒」／降低全体敌人的水属性抗性")
SKILL_NAMES = {1: "蚀刃终决", 2: "蚀刃终决＋"}
SKILL_HITS = 10
SKILL_P13 = 2
SKILL_FEVER = 2.5
SKILL_CAP = 30
#: 每段倍率 (改前 min, max) → (改后 min, max)；_2 满级 ×10 段 = 25，_1 按原比例 ×25/17.5。
SKILL_MULT = {1: ((7 / 6, 7 / 6), (5 / 3, 5 / 3)), 2: ((1.5, 1.75), (15 / 7, 2.5))}
SKILL_BTA = (0, 4)
ATK_KEYS = tuple(f"攻撃力アップ{i}" for i in range(1, 6))
ATK_FRAMES = 1200
ATK_VALUE = (0.6, 1.0)
ATK_SELECTOR = (113, [2])
POISON_STACKS = 2
WATER_RESIST = (-0.15, -0.1)


def _cmd(node):
    """["Command", [名称, ...]] → 参数数组（含名称）；其他 → None。"""
    if isinstance(node, list) and len(node) == 2 and node[0] == "Command" and isinstance(node[1], list):
        return node[1]
    return None


def _name(node) -> str | None:
    if isinstance(node, list) and len(node) == 2 and node[0] in ("Command", "Event") and isinstance(node[1], list):
        return node[1][0]
    return None


def _header_ok(tree) -> bool:
    return tree[:11] == ["ActionDsl", 1, ["None"], *[False] * 7, 0] and tree[11][0] == "Block"


def _atk_condition(template_args: list, key: str) -> list:
    args = deepcopy(template_args)
    args[2][0][2] = slv(ATK_VALUE[1])
    args[7] = key
    return ["Command", args]


def poison_stack_command(subject: int) -> list:
    """技能判定区 onHit：给命中对象 2 层淬毒（官方 ice_dragon_1/_2 的 ACUnique 挂敌写法，层数 = 第二参）。"""
    return ["Command", ["CreateCondition", subject, [["ACUnique", UNIQUE_ID, slv(POISON_STACKS)]], slv(1),
                        ["GenericConditionHitEffect"], True, False, "", None, False, 3, slv(1), False]]


def skill_parts(tree) -> dict:
    """按审过的形状取出技能树各部件（只读引用）；形状不符即拒绝。"""
    if not _header_ok(tree):
        raise ValueError("skill: root header drift")
    body = tree[11][1]
    names = [_name(n) for n in body]
    if names[:3] != ["ShowEffect", "ShakeCamera", "Wait"] or any(n != "FindAllSubjects" for n in names[3:]):
        raise ValueError(f"skill: body shape drift {names}")
    wait = body[2][1]
    if wait[1] != 3 or len(wait[3][1]) != 1 or _name(wait[3][1][0]) != "CreateHitArea":
        raise ValueError("skill: field wait shape drift")
    area = _cmd(wait[3][1][0])
    fas = [_cmd(n) for n in body[3:]]
    return {"body": body, "area": area, "on_hit": area[23][1], "fas": fas}


def _check_skill_preimage(parts: dict, level: int) -> None:
    what = f"skill _{level}"
    area, on_hit, fas = parts["area"], parts["on_hit"], parts["fas"]
    shape = (area[2], area[9], area[13], area[14], area[15], area[22], area[24])
    want = (-18, ["Circle", slv(200)], ["SpecifyHitAreaLifetimeDirectly", 600],
            ["CalculatedUsingMaxNumOfHits", SKILL_HITS], ["Some", slv(SKILL_HITS)], 2, SKILL_BTA[0])
    if shape != want:
        raise ValueError(f"{what}: field preimage drift {shape}")
    if [_name(n) for n in on_hit] != ["CreateNormalAttack", "CreateCondition", "ShakeCamera"]:
        raise ValueError(f"{what}: onHit preimage drift")
    attack, poison = _cmd(on_hit[0]), _cmd(on_hit[1])
    lo, hi = SKILL_MULT[level][0]
    if (attack[1], attack[6], attack[13], attack[14], attack[16]) != (
            area[22], [{"min": lo, "max": hi}], slv(SKILL_P13), slv(SKILL_FEVER), True):
        raise ValueError(f"{what}: attack preimage drift")
    if poison[2][0][0] != "ACPoison":
        raise ValueError(f"{what}: onHit poison drift")
    if len(fas) != 4:
        raise ValueError(f"{what}: FindAllSubjects count drift {len(fas)}")
    for block in fas[:3]:
        if block[1:9] != [3, ATK_SELECTOR[0], ATK_SELECTOR[1], [], [], [], [], ["DoNothing"]] or len(block[9][1]) != 1:
            raise ValueError(f"{what}: attack-buff block drift")
        cond = _cmd(block[9][1][0])
        if (cond[0], cond[1], cond[2], cond[7], cond[10]) != (
                "CreateCondition", 3, [["ACAttackPoint", slv(ATK_FRAMES), slv(ATK_VALUE[0]), slv(1)]], "", 1):
            raise ValueError(f"{what}: attack-buff condition drift")
    if json.dumps(fas[0]) != json.dumps(fas[1]) or json.dumps(fas[0]) != json.dumps(fas[2]):
        raise ValueError(f"{what}: the three attack-buff blocks are no longer identical")
    tol = fas[3]
    if tol[1:3] != [4, 49] or len(tol[9][1]) != 1:
        raise ValueError(f"{what}: resist block drift")
    tcond = _cmd(tol[9][1][0])
    if tcond[2] != [["ACToleranceOfElement", slv(ATK_FRAMES), 2, slv(WATER_RESIST[0]), slv(1)]]:
        raise ValueError(f"{what}: resist condition drift {tcond[2]}")


def revise_skill_tree(tree, level: int) -> list:
    """技能第 level 档：按直击结算 + 25 倍 + 2 层淬毒 + 5 个独立攻击 buff + 水耐性 -10%；不改输入。"""
    result = deepcopy(tree)
    parts = skill_parts(result)
    _check_skill_preimage(parts, level)
    area, on_hit, fas, body = parts["area"], parts["on_hit"], parts["fas"], parts["body"]
    area[24] = SKILL_BTA[1]
    lo, hi = SKILL_MULT[level][1]
    _cmd(on_hit[0])[6] = [{"min": lo, "max": hi}]
    on_hit.append(poison_stack_command(area[22]))
    _cmd(fas[3][9][1][0])[2][0][3] = slv(WATER_RESIST[1])
    template = _cmd(fas[0][9][1][0])
    fas[0][9] = ["Block", [_atk_condition(template, key) for key in ATK_KEYS]]
    del body[4:6]                                   # 另两个 FindAllSubjects(3,113,[2]) 并进第一个
    return result


def skill_damage_total(tree) -> float:
    """技能每次施放单目标满级总倍率 = 段数 × 每段倍率 max。"""
    area = skill_parts(tree)["area"]
    return round(SKILL_HITS * _cmd(area[23][1][0])[6][0]["max"], 9)


# ================================================================ 强化弹射（泡泡）

PF_CAP = {1: 15, 2: 20, 3: 25}
#: (改前个数, 改后个数, 新增泡泡与前一个的间隔帧)
PF_BUBBLES = {1: (1, 2, 7), 2: (3, 4, 7), 3: (5, 6, 6)}
PF_TIMES = {1: ([1], [1, 8]), 2: ([1, 8, 15], [1, 8, 15, 22]),
            3: ([1, 7, 13, 19, 25], [1, 7, 13, 19, 25, 31])}
PF_NOTIFY = {1: (19, 26), 2: (33, 40), 3: (43, 49)}
NOTIFY_AFTER_LAST = 18
BUBBLE_LIFETIME = (20, 72)
BUBBLE_HITS = (3, 15)
BUBBLE_SHAPE = ["Rectangle", slv(180), slv(4000)]
#: 每段 (倍率, 削韧 p13, Fever)：改前（live 1.4.1051，第二批后）→ 改后。
PF_SEG_BEFORE = {1: (1.8333333333333333, 3, 6), 2: (1.0833333333333333, 2.2, 6), 3: (1.1666666666666665, 1.6, 6)}
PF_SEG_AFTER = {1: (11 / 60, 0.5, 0.6), 2: (0.1625, 0.3333, 0.9), 3: (7 / 36, 0.2666, 1.0)}
#: 泡泡段合计（每目标）：倍率 / Fever 守恒；削韧为整棵树（Lv3 含开场全屏 1 段 × 1）。
PF_BUBBLE_TOTAL = {1: (5.5, 18), 2: (9.75, 54), 3: (17.5, 90)}
PF_DETOUGH = {1: (9, 15), 2: (19.8, 19.998), 3: (25, 24.994)}
LV3_OPENER = (-1, ["AB"], ["CalculatedUsingMaxNumOfHits", 1], 1)
SUPPORT_P5_INT = {1: 3, 2: 3, 3: 0}


def _is_wait(node) -> bool:
    return _name(node) == "Wait" and node[0] == "Event"


def pf_timeline(tree) -> dict:
    """PF 树的顶层结构与泡泡 Wait 链：{"body", "bubbles": [(t, CreateHitArea 参数, 所在 Block 列表)], "notify": t,
    "notify_block": 含 Notify 的 Wait 所在 Block 列表}；形状不符即拒绝。"""
    if not _header_ok(tree):
        raise ValueError("PF: root header drift")
    body = tree[11][1]
    waits = [n for n in body if _is_wait(n)]
    suppress = [_cmd(n) for n in body if _name(n) == "SetPowerFilpSuppress"]
    if len(waits) != 1 or body[-1] is not waits[0] or suppress != [["SetPowerFilpSuppress", 20]]:
        raise ValueError("PF: top-level wait/suppress shape drift")
    bubbles, node, t, parent = [], waits[0], 0, body
    while True:
        t += node[1][1]
        block = node[1][3][1]
        if len(block) == 1 and _name(block[0]) == "NotifyPowerflipEnd":
            if _cmd(block[0]) != ["NotifyPowerflipEnd", -18]:
                raise ValueError("PF: notify shape drift")
            return {"body": body, "bubbles": bubbles, "notify": t, "notify_block": parent}
        if len(block) != 2 or _name(block[0]) != "CreateHitArea" or not _is_wait(block[1]):
            raise ValueError("PF: bubble wait-chain shape drift")
        bubbles.append((t, _cmd(block[0]), block))
        parent, node = block, block[1]


def _bubble_shape(args) -> tuple:
    return (args[1], args[2], args[3], args[7], args[8], args[9], args[22], args[24])


BUBBLE_FIXED = ("*", -18, ["EF"], False, False, BUBBLE_SHAPE, 2, 4)


def _check_pf_preimage(tree, level: int) -> dict:
    what = f"PF lv{level}"
    line = pf_timeline(tree)
    times = [t for t, _, _ in line["bubbles"]]
    if times != PF_TIMES[level][0] or line["notify"] != PF_NOTIFY[level][0]:
        raise ValueError(f"{what}: timeline preimage drift {times} / {line['notify']}")
    mult, p13, fever = PF_SEG_BEFORE[level]
    for _, args, _ in line["bubbles"]:
        if (_bubble_shape(args) != BUBBLE_FIXED
                or args[13] != ["SpecifyHitAreaLifetimeDirectly", BUBBLE_LIFETIME[0]]
                or args[14] != ["CalculatedUsingMaxNumOfHits", BUBBLE_HITS[0]] or args[15] != ["None"]):
            raise ValueError(f"{what}: bubble preimage drift")
        if [_name(n) for n in args[20][1]] != ["ShowEffect"]:
            raise ValueError(f"{what}: bubble onCreate drift")
        if [_name(n) for n in args[23][1]] != ["CreateNormalAttack", "ShakeCamera", "CreateCondition"]:
            raise ValueError(f"{what}: bubble onHit drift")
        attack, shake, poison = (_cmd(n) for n in args[23][1])
        if (attack[1], attack[6], attack[13], attack[14], attack[16]) != (
                2, slv(mult), slv(p13), slv(fever), True):
            raise ValueError(f"{what}: bubble attack preimage drift")
        if shake != ["ShakeCamera", 1] or poison[2][0][0] != "ACPoison":
            raise ValueError(f"{what}: bubble shake/poison drift")
    areas = batch2.hit_areas(tree)
    if level == 3:
        opener = areas[0][0]
        if ((opener[2], opener[3], opener[14]), [batch2._p13(a) for a in areas[0][2]]) != (
                LV3_OPENER[:3], [LV3_OPENER[3]]):
            raise ValueError(f"{what}: opener drift")
    if abs(batch2.detoughness(tree) - PF_DETOUGH[level][0]) > TOLERANCE:
        raise ValueError(f"{what}: detoughness preimage {batch2.detoughness(tree)} != {PF_DETOUGH[level][0]}")
    return line


def _support_p5_ints(body) -> list:
    """辅助段 FindAllSubjects(6,33) 里 p5 写成整数的 CreateCondition 参数（Lv1/Lv2 为 6）。"""
    found = []
    for node in body:
        args = _cmd(node)
        if args and args[0] == "FindAllSubjects" and args[1:3] == [6, 33]:
            for cond in args[9][1]:
                c = _cmd(cond)
                if c and c[0] == "CreateCondition" and type(c[5]) is int:
                    found.append(c)
    return found


def revise_pf_tree(tree, level: int) -> list:
    """PF 覆盖树第 level 档：泡泡 +1、每泡 15 段、总量守恒重摊、削韧顶到上限内；不改输入。"""
    what = f"PF lv{level}"
    result = deepcopy(tree)
    line = _check_pf_preimage(result, level)
    ints = _support_p5_ints(line["body"])
    if len(ints) != SUPPORT_P5_INT[level] or any(c[5] != 6 for c in ints):
        raise ValueError(f"{what}: support p5 preimage drift")
    for cond in ints:
        cond[5] = True
    # 深拷最后一个泡泡，再嵌一层 Wait；Notify 跟着下移。
    _, last_area, last_block = line["bubbles"][-1]
    notify_wait = last_block[1]
    last_block[1] = ["Event", ["Wait", PF_BUBBLES[level][2], "*",
                               ["Block", [["Command", deepcopy(last_area)], notify_wait]]]]
    line = pf_timeline(result)
    mult, p13, fever = PF_SEG_AFTER[level]
    for _, args, _ in line["bubbles"]:
        args[13] = ["SpecifyHitAreaLifetimeDirectly", BUBBLE_LIFETIME[1]]
        args[14] = ["CalculatedUsingMaxNumOfHits", BUBBLE_HITS[1]]
        args[15] = ["Some", slv(BUBBLE_HITS[1])]
        on_create, on_hit = args[20][1], args[23][1]
        on_create.append(on_hit.pop(1))             # ShakeCamera 1：每个泡泡生成时震一次
        attack = _cmd(on_hit[0])
        attack[6], attack[13], attack[14] = slv(mult), slv(p13), slv(fever)
    times = [t for t, _, _ in line["bubbles"]]
    if (times != PF_TIMES[level][1] or line["notify"] != PF_NOTIFY[level][1]
            or line["notify"] != times[-1] + NOTIFY_AFTER_LAST):
        raise ValueError(f"{what}: timeline {times} / {line['notify']}")
    total = batch2.detoughness(result)
    if total > PF_CAP[level] + TOLERANCE or abs(total - PF_DETOUGH[level][1]) > 1e-6:
        raise ValueError(f"{what}: detoughness {total} (want {PF_DETOUGH[level][1]}, cap {PF_CAP[level]})")
    got = pf_bubble_totals(result)
    if any(abs(a - b) > 1e-6 for a, b in zip(got, PF_BUBBLE_TOTAL[level])):
        raise ValueError(f"{what}: bubble totals {got} != {PF_BUBBLE_TOTAL[level]}")
    return result


def pf_bubble_totals(tree) -> tuple[float, float]:
    """泡泡段每目标合计（倍率, Fever）：Σ 泡泡命中数 × onHit CreateNormalAttack 的 p6 / p14（max 端）。"""
    mult = fever = 0.0
    for _, args, _ in pf_timeline(tree)["bubbles"]:
        hits = batch2._area_hits(args)
        for attack in wf_dsl.iter_dsl_commands(args[23], "CreateNormalAttack"):
            mult += hits * attack[6][0]["max"]
            fever += hits * attack[14][0]["max"]
    return round(mult, 9), round(fever, 9)


# ================================================================ 队长：每 2 层淬毒直击判定 +1

POISON_HITS_PERIOD = 10          # T77 每 10 帧执行一次（奈芙 169989 09-27 卡顿修复后的参数）
POISON_HITS_TTL = 2 * POISON_HITS_PERIOD
POISON_HITS_DIVISOR = 2
POISON_HITS_CAP = 9              # 段数 = floor(1 + min(层/2, 9))：18 层起 10 段
POISON_HITS_DAMAGE = 1.0         # 与能力3 行4 DirectAttack2 的 +100% 相同
# 不写「水属性共鸣时，」：客户端画队长面板时会先拼本行前置（kind 2 →「水共鸣」）再接文案，写了会重复。
POISON_HITS_TEXT = ("敌人身上每有2层「淬毒」，水属性角色的直击判定次数+1"
                    "（按层数最多的敌人计算，直击判定最多10次）")
#: 新队长行的非空列（形状 = live 169989 下标 7，前置 c4..c10 = 本表下标 7 的水共鸣门）。
POISON_HITS_ROW = {0: CODE, 1: "0", 3: "0", 4: "2", 5: "0", 7: "600000", 8: "600000", 9: "Blue", 11: "0",
                   18: "0", 25: "77", 28: str(POISON_HITS_PERIOD * 100000), 29: str(POISON_HITS_PERIOD * 100000),
                   32: "(None)", 33: "0", 37: "(None)", 44: "0", 45: "629",
                   68: POISON_HITS_KEY, 69: POISON_HITS_PROGRAM}
LEADER_COLUMNS = 124


def poison_hits_tree() -> list:
    """队长 629 裸树（编码器只吃裸树）。"""
    times = [{"min": 1, "max": 1, "vlv": [{"vid": 1, "min": 0, "max": 1}]}]
    grant = ["Command", ["CreateCondition", 11,
                         [["ACAdditionalDirectAttack", slv(POISON_HITS_TTL), times, slv(POISON_HITS_DAMAGE), slv(1)]],
                         slv(1), ["None"], False, True, "", None, True, 3, slv(1), True]]
    water = ["Command", ["FindAllSubjects", 11, 113, [2], [], [], [], [], ["DoNothing"], ["Block", [grant]]]]
    bind = ["Command", ["BindConditionAccumulationVariable", 10, 1, ["DCUnique", UNIQUE_ID],
                        POISON_HITS_DIVISOR, POISON_HITS_CAP]]
    enemies = ["Command", ["FindAllSubjects", 10, 49, [], [], [], [], [], ["DoNothing"], ["Block", [bind, water]]]]
    return ["ActionDsl", 1, ["None"], False, False, False, False, False, False, False, 0, ["Block", [enemies]]]


def poison_hits_segments(stacks: int) -> int:
    """段数 = floor(基数 1 + vlv(min(层/除数, 上限)))（AdditionalConditionKindTools case 27 取 floor(值+2e-10)）。"""
    return int(math.floor(1 + min(stacks / POISON_HITS_DIVISOR, POISON_HITS_CAP) + 2e-10))


def poison_hits_leader_row() -> list[str]:
    row = [""] * LEADER_COLUMNS
    for col, value in POISON_HITS_ROW.items():
        row[col] = value
    return row


# ================================================================ 能力

A2_TRIGGERS = ("63", "64", "65")
A2_STACKS_BEFORE = ("100000", "300000", "500000")
A2_TRIGGER_AFTER = "2"            # PowerFlip（任意档）
A2_STACKS_AFTER = "300000"        # 3 层
A3_REMOVED_TRIGGERS = ("63", "64", "65")
A3_TEMPLATE_INDEX = 3             # 行4：常驻 201 DirectAttack2、前置 202、对象水队
A3_KIND = ("201", "117")          # → ConditionSlayer(Poison, All)
A3_STRENGTH = ("100000", "15000")
A2_OVERRIDE_TEXT = "\n".join((
    "发动强化弹射时，对全体敌人施加3层「淬毒」（最多20层）",
    "敌人每有1层「淬毒」，全队对其造成的伤害+50%（最多20层）",
    "强化中毒：技能与强化弹射附加的中毒伤害大幅提升",
))


def revise_ability2(rows: list[list[str]]) -> list[list[str]]:
    rows = deepcopy(rows)
    if len(rows) != 4 or [r[27] for r in rows[:3]] != list(A2_TRIGGERS) or \
            [r[51] for r in rows[:3]] != list(A2_STACKS_BEFORE) or {r[47] for r in rows[:3]} != {"413"}:
        raise ValueError("ability 2: PF poison rows drift")
    for r in rows[:3]:
        if r[51] != r[52] or r[68] != str(UNIQUE_ID) or r[28] != "" or (r[30], r[31], r[34]) != ("100000", "100000", "(None)"):
            raise ValueError("ability 2: PF poison row shape drift")
    if (rows[3][97], rows[3][102], rows[3][104], rows[3][109]) != ("171", "20", str(UNIQUE_ID), "158"):
        raise ValueError("ability 2: per-stack slayer row drift")
    merged = rows[0]
    merged[27] = A2_TRIGGER_AFTER
    merged[51] = merged[52] = A2_STACKS_AFTER
    return [merged, rows[3]]


def revise_ability3(rows: list[list[str]]) -> list[list[str]]:
    rows = deepcopy(rows)
    if len(rows) != 8 or [r[27] for r in rows[5:]] != list(A3_REMOVED_TRIGGERS) or {r[47] for r in rows[5:]} != {"713"}:
        raise ValueError("ability 3: PF separated-term rows drift")
    template = rows[A3_TEMPLATE_INDEX]
    if (template[5], template[6], template[47], template[48], template[49], template[51], template[52]) != (
            "0", "202", A3_KIND[0], "5", "Blue", A3_STRENGTH[0], A3_STRENGTH[0]):
        raise ValueError("ability 3: template row drift")
    new = deepcopy(template)
    new[47] = A3_KIND[1]
    new[51] = new[52] = A3_STRENGTH[1]
    return rows[:5] + [new]


def revise_ability6(rows: list[list[str]]) -> list[list[str]]:
    rows = deepcopy(rows)
    if len(rows) != 5 or (rows[2][27], rows[2][47], rows[2][51], rows[2][68]) != ("23", "413", "200000", str(UNIQUE_ID)):
        raise ValueError("ability 6: skill poison row drift")
    if [(r[27], r[47]) for r in rows[3:]] != [("23", "252"), ("23", "264")]:
        raise ValueError("ability 6: skill follow-up damage rows drift")
    return rows[:2] + rows[3:]


def revise_leader(rows: list[list[str]]) -> list[list[str]]:
    rows = deepcopy(rows)
    if len(rows) != 9 or any(r[45] == "629" or r[68] for r in rows):
        raise ValueError("leader: row count / existing 629 drift")
    if (rows[0][45], rows[0][80]) != ("722", PF_ACTION[1]):
        raise ValueError("leader: PF override row drift")
    gate = rows[7][4:11]
    if gate != ["2", "0", "", "600000", "600000", "Blue", ""]:
        raise ValueError("leader: water-resonance gate drift")
    new = poison_hits_leader_row()
    if new[4:11] != gate:
        raise AssertionError("new leader row gate must equal the table's water-resonance gate")
    return rows + [new]


# ================================================================ 文案

def _revise_text_row(row: list[str], what: str) -> list[str]:
    row = list(row)
    if [row[i] for i in (5, 7, 9)] != [OLD_SKILL_DESC] * 3 or row[4] != SKILL_NAMES[1]:
        raise ValueError(f"{what}: skill description drift")
    for i in (5, 7, 9):
        row[i] = NEW_SKILL_DESC
    return row


def revise_action(actions) -> list:
    out = []
    for inner, fields in actions:
        fields = list(fields)
        if inner not in ("1", "2") or fields[0] != SKILL_NAMES[int(inner)] or fields[1] != OLD_SKILL_DESC \
                or fields[7] != SKILL_PROGRAMS[int(inner)]:
            raise ValueError(f"action_skill {inner}: drift")
        fields[1] = NEW_SKILL_DESC
        out.append((inner, fields))
    if [i for i, _ in out] != ["1", "2"]:
        raise ValueError("action_skill: inner keys drift")
    return out


def panel_problems(key: str, text: str) -> list[str]:
    """面板规则：kitlib 禁语；换行分行不用「／」；非主位槽不带主位图标；不写字面「Ⓜ」。"""
    problems = [f"{key}: {p}" for p in kitlib.panel_problems(text)]
    for line in text.split("\n"):
        if "／" in line:
            problems.append(f"{key}: line uses 「／」 instead of a line break")
        if "<icon id='main'>" in line or "Ⓜ" in line:
            problems.append(f"{key}: main-slot icon on a non-main ability")
    return problems


# ================================================================ 门禁 / 入口


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _baseline(read) -> dict:
    """读取并锁定全部输入；任何一项漂移、或新键已被占用，都拒绝（fail closed）。"""
    inputs = {}
    for kind, key in BEFORE:
        value = read(kind, key)
        if value is None or digest(value) != BEFORE[kind, key]:
            raise ValueError(f"unreviewed live baseline: {kind}:{key}")
        inputs[kind, key] = deepcopy(value)
    for kind, key in NEW_KEYS:
        try:
            value = read(kind, key)
        except (KeyError, FileNotFoundError):
            continue
        if value is not None:
            raise ValueError(f"new key already exists in live: {kind}:{key}")
    if inputs["table", PF_ACTION] != [[PF_PROGRAMS[level] for level in PF_LEVELS]]:
        raise ValueError("power_flip_action no longer points at the reviewed PF trees")
    unique = inputs["table", UNIQUE][0]
    # 技能 onHit 的 ACUnique「每个敌人每次施放只 +2 层」依赖 force_apply=false 的重付与闸门：
    # c10 改 true 会让 10 段命中每段都 +2（一次施放叠满 20 层）。上限 c4=20 是作者要求。
    if (unique[0], unique[4], unique[9], unique[10]) != ("unique_claude_wolf_poison", "20", "false", "false"):
        raise ValueError(f"unique_condition {UNIQUE_ID}: c0/c4/c9/c10 drift {unique[:11]}")
    return inputs


def dsl_problems(tree) -> list[str]:
    problems = []
    back = wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"]
    if json.dumps(back) != json.dumps(tree):   # 连 int/float 类型一起比
        problems.append("AMF3 roundtrip mismatch")
    problems += [f"element: {p}" for p in legality.action_dsl_element_problems(tree, ELEMENT)]
    problems += [f"subject: {p}" for p in legality.action_dsl_subject_binding_problems(tree)]
    problems += [f"scope: {p}" for p in legality.action_dsl_lookup_scope_problems(tree)]
    problems += [f"hit_target: {p}" for p in legality.action_dsl_hit_area_target_problems(tree)]
    problems += [f"player_side: {p}" for p in wf_dsl.player_side_dsl_problems(tree)]
    return problems


def row_problems(kind: str, rows: list[list[str]], cas_keys) -> list[str]:
    problems = []
    for i, row in enumerate(rows):
        problems += [f"#{i} legality: {p}" for p in legality.client_legality_problems(kind, row)]
        problems += [f"#{i} declared: {p}" for p in legality.declared_block_field_problems(kind, row)]
        problems += [f"#{i} invoke: {p}" for p in legality.invoke_skill_string_problems(row, cas_keys, kind)]
    return problems


def required_capabilities(out: dict) -> list[str]:
    caps = set()
    for kind, table in (("ability", "ability"), ("leader", "leader_ability")):
        for rows in out[kind].values():
            for row in rows:
                caps.update(legality.required_client_capabilities(table, row))
    caps.update(filter(None, (legality.panel_override_capability(key) for key in out["cas"])))
    return sorted(caps)


def revise(read) -> dict:
    inputs = _baseline(read)
    skill = {SKILL_PROGRAMS[level]: revise_skill_tree(inputs["dsl", SKILL_PROGRAMS[level]], level)
             for level in SKILL_LEVELS}
    pf = {PF_PROGRAMS[level]: revise_pf_tree(inputs["dsl", PF_PROGRAMS[level]], level) for level in PF_LEVELS}
    dsl = {**skill, **pf, POISON_HITS_PROGRAM: poison_hits_tree()}
    ability = {ABILITY[2]: revise_ability2(inputs["ability", ABILITY[2]]),
               ABILITY[3]: revise_ability3(inputs["ability", ABILITY[3]]),
               ABILITY[6]: revise_ability6(inputs["ability", ABILITY[6]])}
    leader = {CID: revise_leader(inputs["leader", CID])}
    cas = {POISON_HITS_KEY: [[POISON_HITS_TEXT]], A2_OVERRIDE_KEY: [[A2_OVERRIDE_TEXT]]}
    text = {CID: [_revise_text_row(inputs["text", CID][0], "character_text")] + deepcopy(inputs["text", CID][1:])}
    server = deepcopy(inputs["server_text", CID])
    server[0] = _revise_text_row(server[0], "server character_text")
    action = {CODE: revise_action(inputs["action", CODE])}
    out = {"ability": ability, "leader": leader, "cas": cas, "text": text, "table": {}, "action": action,
           "dsl": dsl, "server_text": {CID: server}, "new_programs": [POISON_HITS_PROGRAM]}

    problems = [f"dsl {program}: {p}" for program, tree in dsl.items() for p in dsl_problems(tree)]
    cas_keys = set(cas)
    problems += [f"ability {key}: {p}" for key, rows in ability.items() for p in row_problems("ability", rows, cas_keys)]
    problems += [f"leader {key}: {p}" for key, rows in leader.items()
                 for p in row_problems("leader_ability", rows, cas_keys)]
    problems += [p for key, rows in cas.items() for p in panel_problems(key, rows[0][0])]
    for key in cas:
        if not key.startswith((CODE, f"desc_override_{CODE}")):
            problems.append(f"cas {key}: outside the character namespace")
    if required_capabilities(out) != sorted(CAPABILITIES):
        problems.append(f"capabilities {required_capabilities(out)} != {CAPABILITIES}")
    for program, tree in skill.items():
        if skill_damage_total(tree) > 25 + TOLERANCE or batch2.detoughness(tree) > SKILL_CAP:
            problems.append(f"skill {program}: damage/detoughness over the plan")
    if problems:
        raise ValueError("; ".join(problems))
    out["notes"] = notes(out)
    return out


def notes(out: dict) -> dict:
    pf = {f"lv{level}": {
        "bubbles": list(PF_BUBBLES[level][:2]), "spawn_frames": PF_TIMES[level][1],
        "notify_frame": list(PF_NOTIFY[level]),
        "per_segment_before": list(PF_SEG_BEFORE[level]), "per_segment_after": list(PF_SEG_AFTER[level]),
        "bubble_totals_mult_fever": list(PF_BUBBLE_TOTAL[level]),
        "detoughness_before_after": list(PF_DETOUGH[level]), "cap": PF_CAP[level],
        "combo_per_target_before_after": [PF_BUBBLES[level][0] * BUBBLE_HITS[0], PF_BUBBLES[level][1] * BUBBLE_HITS[1]],
    } for level in PF_LEVELS}
    return {
        "source": "wf_balance_20260927b_claus_rework.py",
        "spec": ("作者 2026-09-27 聊天原话 + 方案问题选择①②③；主会话默认值；research/design.claus/critique"
                 "（按其节点路径施工并落实复核修正）；第二批口径 B.1/B.2/D"),
        "skill": {
            "field_buffTargetAs": list(SKILL_BTA),
            "per_hit_mult": {f"_{lv}": [list(SKILL_MULT[lv][0]), list(SKILL_MULT[lv][1])] for lv in SKILL_LEVELS},
            "total_mult_max": {f"_{lv}": skill_damage_total(out["dsl"][SKILL_PROGRAMS[lv]]) for lv in SKILL_LEVELS},
            "detoughness": SKILL_HITS * SKILL_P13,
            "attack_buffs": {"selector": "FindAllSubjects(3,113,[2]) 水属性主队（沿用现值，不含协力球）",
                             "keys": list(ATK_KEYS), "value": ATK_VALUE[1], "frames": ATK_FRAMES,
                             "before": "3 个空键 +60%（同次施放按去重哈希推断只生效 1 个）"},
            "poison_stacks_on_hit": POISON_STACKS, "water_resist": list(WATER_RESIST),
        },
        "pf": pf,
        "leader_poison_hits": {
            "row_index": 9, "trigger": "T77 每 10 帧", "ttl_frames": POISON_HITS_TTL,
            "segments_by_stacks": {n: poison_hits_segments(n) for n in (0, 1, 2, 4, 10, 18, 20)},
            "damage_bonus": POISON_HITS_DAMAGE, "selector": "49 全体敌人取最大层数 → 113 [2] 水属性主队",
            "shape_precedent": "live leader 169989 下标 7（奈芙 T77→629，09-27 卡顿修复参数）",
            "bind_precedent": "live ability_skill_kyle_moon_pierce：Bind(-17,1,DCUnique,1,10) + vlv 段数",
            "per_run_cost": ("每次执行 = 敌人数 ×（1 次 Bind + 1 次 FindAllSubjects + ≤3 次 CreateCondition），每秒 6 次；"
                             "boss 战 1–3 个敌人 ≈ 每支克劳斯队伍 ≤54 次 CreateCondition/秒，联机每端模拟全部队伍最多 ×3"
                             "（奈芙修复前是 3 行每帧执行）"),
        },
        "ability": {
            "1299972": "行1-3（63/64/65 → 413 1/3/5 层）合一：trigger 2 任意档 PF → 3 层；行4 保留（4 → 2 行）",
            "1299973": "删行6-8（713 +15/45/75%）；新增行4 克隆 c47 201→117、c51/c52 100000→15000（8 → 6 行）",
            "1299976": "删行3（技能发动 → 413 2 层，改由技能 DSL 附加）；行4/行5 追加能力伤害保留（5 → 4 行）",
        },
        "panel": {
            POISON_HITS_KEY: POISON_HITS_TEXT, A2_OVERRIDE_KEY: A2_OVERRIDE_TEXT,
            "skill_description": NEW_SKILL_DESC,
            "skill_description_places": ["action_skill 1/2 c1", "character_text c5/c7/c9",
                                         "server cdndata/character_text.json [5]/[7]/[9]"],
            "auto_generated": "能力3（对中毒敌人伤害+15%，带主位前置图标）、能力6（少一行淬毒）、队长（629 行引用 CAS）",
            "override_string_unchanged": "override_string_claude_wolf_assassin_ex「追加「淬毒爪击」特殊强化弹射」不含数值，仍属实",
        },
        "deviations_and_choices": [
            "技能描述写「赋予水属性角色5个攻击力提升效果」：主会话定选择器沿用 113 [2]（只给主队水属性角色），"
            "作者原话/设计稿的「全体队友」与实际不符，按实际写",
            "队长段数封顶 10（Bind 上限 9）：按作者括号「满20层每个水属性角色直击都能打10下」；若要 1+10=11 段，只改 "
            "POISON_HITS_CAP=10 与面板「最多11次」",
            "desc_override 用单列（live 199 个 desc_override_*_N 全是 1 行 1 列），设计稿的「两列」不采用",
            "新 CAS/DSL 键用 CODE 前缀 claude_wolf_assassin_ex_poison_hits（接口约定与暂存脚本的命名空间断言），"
            "不用设计稿的 claude_wolf_ex_poison_hits；候选内最长路径 210 字符，package-pre-rebase 改名后 254 < 259",
            "PF 每段削韧取设计稿 4 位小数 0.3333/0.2666（19.998/24.994，不越上限）；倍率取精确分数保持总量守恒",
            "泡泡 onHit 的 ShakeCamera 1 移到 onCreate（复核修正：否则每目标 90 段震 90 次）",
            "PF Lv1/Lv2 辅助段 CreateCondition p5 整数 6 → true（复核修正：签名 Boolean，行为等价）",
            "技能 ACUnique 追加在 onHit 末尾（原节点下标不动）",
        ],
        "risks": [
            "+500% 攻击（5 × 100% 加算）约为官方单技能最高的 2 倍；点灯类增益计数 +5（作者原话，照做）",
            "技能按直击结算后吃直击通用池（队长 33 +200%、能力1 33 +100%、159 每层 +50%）：满层时实际输出约为改前的 34 倍；"
            "吃不到 410/713 独立直击乘区，也不计入直击次数（ActionEvaluator.as:2843-2844）",
            "泡泡与技能领域都不计入「直击次数」、不吃队长直击判定 +N（数据层做不到，作者已知）",
            "泡泡是静止的 180×4000 光束，敌人移出光束吃不满 15 段；特效 48 帧、判定 72 帧",
            "泡泡连击：每次 PF 每目标最多 +30/60/90 连击（改前 3/9/15），基本每次拍板都是 PF3（作者选择②已接受）",
            "队长 +N：满层每名水属性成员每次直击 10 段，削韧/Fever/连击 ×10，与 PF3 连发互相维持满层（作者选择①已接受）",
            "队长状态 D=1.0：能力3 未解锁时，0–1 层也相当于水属性角色直击伤害 +100%（隐形）；自带更高 D、段数更少的直击段数"
            "效果的水属性搭档会被整体顶替（先比段数）",
            "Bind 读敌方主体、除数 2、p6=true 配空键刷新：官方与 live 均无先例，只有反编译依据",
            "能力3 117 进状态特攻加算项，与能力2 淬毒特攻（满层 +1000%）相加，满层时实际只多约 1.4%；判定的是官方中毒不是淬毒",
            "水降抗只对火属性或无属性耐性抗性的 boss 生效（forceApply 未改，作者未要求）",
        ],
        "zero_precedent_needs_device": [
            "5 个不同区分键的同型 ACAttackPoint（官方最多 2 个，live 3 个）",
            "技能 onHit 一次给敌人叠 2 层 ACUnique（官方挂敌只有 1 层）",
            "队长 DSL：BindConditionAccumulationVariable 读敌方主体（官方/live 全是 -17）、除数 2",
            "队长 DSL：CreateCondition p6=true + 空键按段数分条目、取最大",
            "泡泡寿命 72 帧 × 15 段的静止光束（官方 15 段先例为领域）",
        ],
        "candidate": {
            "reviewed_drift": "技能两档 DSL（同第二批，候选 == live、manifest 未重封；本次输出会重封）",
            "new_roots": ["PF lv1 DSL（第二批未进包）", POISON_HITS_PROGRAM],
            "preexisting_drift_not_touched": ("ability 1299974 候选（≥2 次/+2%/CT0）≠ live（≥15 次/+5%/CT120），不在本次范围、"
                                               "未返回；主会话如需对齐候选，另行把 live 行写进候选"),
        },
        "generators": ("无可同步常量：包内 build_claw_pf.py / restore_pf_support.py / patch_* / fix_* 都是 0818–0820 "
                       "一次性直写 live 脚本、输出早已≠live，禁止重跑；本模块是唯一真源"),
        "batch2_modules": ("wf_balance_20260927b_klaus.py 的 BEFORE 锁 1.4.1049 预像，本次发布后在新 live 上 fail closed，"
                           "设计如此；其测试读夹具，仅 live/候选两条本机断言按「作者 09-27 小重做」放宽"),
        "needed_edits_elsewhere": [
            "batch2/stage_batch.py 的 SNAPSHOT='revision_20260927b' 与 evidence_name 固定：本单元回写同一候选会覆盖第二批"
            " klaus 的 snapshot/evidence，建议本单元改用 'revision_20260927b_claus_rework' / 'revision-20260927b-claus-rework.json'",
            "batch2/stage_batch.py 的 Plan 只在 before/packages/<pkg> 不存在时备份候选；claude_wolf_assassin_ex 已有第二批前的备份，"
            "本单元回写前的候选（0.1.1）不会被再备份，需要的话另存",
        ],
        "device_checklist": [
            "技能：5 个攻击图标同时存在、水属性角色攻击约 +500%、刷新不叠到 10 个；领域伤害字体/乘区按直击",
            "技能：每次施放每个敌人淬毒 +2 层（不是 +20），水耐性 -10%；能力6 不再额外 +2",
            "PF：泡泡 2/4/6 个、每个对 boss 打满 15 段；特效 48 帧 vs 判定 72 帧的观感；震屏只在泡泡生成时；联机帧率",
            "队长：0/4/10/18/20 层时直击段数 1/3/6/10/10；≥4 层顶替能力3 DA2 不丢 +100%；continuous_attacks_ball 光效；boss Down 频率",
            "面板：能力2 覆盖三行（V14 面板补丁 APK）、能力3「对中毒状态的敌人伤害+15%」带主位图标、队长 629 行文案、技能描述",
        ],
        "runtime_verified": False,
    }
