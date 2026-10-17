# -*- coding: utf-8 -*-
'墨斯伊克「自由之羽」（149997 mosiyike）：2026-09-27 平衡第三轮——强化弹射风刃倍率跟灰服降档，纯函数。\n\n作者决定（2026-09-27 本会话 AskUserQuestion，主会话转述）：问「灰服在 1.4.85 把风刃倍率从 12.5/8.28/6.44 降到\n7.5/6.0/4.5，我们有这一版的存档。要跟着降吗？削韧保持第二批的 10/20/25。」→ 作者选「跟着降到灰服倍率」。\n\n## 落点\nPF 覆盖树（leader 149997#0 kind 722 → power_flip_action ``mosiyike_pf`` → lv1/lv2/lv3）里每发自走风刃的\n``CreateNormalAttack`` 攻击倍率 args[6]（SLv ``{min,max}`` 同改，保持 float）：\n\n======  ====  =======================  ======================  ==========================\n档位    发数  每发倍率（现 → 灰服）     合计倍率                每发削韧 p13（第二批，不动）\n======  ====  =======================  ======================  ==========================\nLv1     2     12.5 → 7.5               25 → 15                 5（合计 10）\nLv2     5     8.28 → 6.0               41.4 → 30               4（合计 20）\nLv3     10    6.44 → 4.5               64.4 → 45               2.5（合计 25）\n======  ====  =======================  ======================  ==========================\n\n其余节点逐字保留；三档都返回（Lv1 这次也改）。整树 AMF3 往返一致（连 int/float 类型）并过四道 DSL 门禁。\n\n## 灰服来源与逐节点比对\n灰链归档 ``work/codex_out/gray-audit-20260830/gray/assets/asset-patch/active``（灰链 ≤1.4.93 快照）里，三档 PF 树只在\n``pinball-1.4.84-1.4.85-1-0821-mosiyike-balance-ios.zip`` 出现过一次（``GRAY_PF_DEFLATE_SHA256``，成员\n``production/upload/<sha1(逻辑路径)>``）。与我方第二批之前的树（``wf_balance_20260927b_mosiyike`` 夹具 = live 1.4.1049）\n逐叶比对：灰版只改了每发风刃的 args[6]（Lv1 4 叶、Lv2 10 叶、Lv3 20 叶，全是 min/max），p13 仍为 5，其余节点\n（官方辅助段、Wait 错开、扇形角、判定区、特效、音效、ShakeCamera 等）与我方逐字相同。所以本模块的输出 =\n灰版树 + 第二批 p13（5/4/2.5）：把输出里每发风刃 p13 换回 int 5 后，整树摘要必须等于 ``GRAY_PF_TREE_DIGEST``\n（``revise`` 内校验，fail closed）；Lv1 第二批没动，输出与灰版逐字节相同。\n灰方 1.4.93→1.4.121 之间是否又调过 PF 看不到（灰链归档止于 1.4.93；gray3 压缩包 1.4.121→1.4.131 不含 PF 树）；\n作者按「灰服 1.4.85 的值」拍板，按此执行。\n\n## 文案\nPF 覆盖文案 ``override_string_mosiyike``「追加「苍穹风刃」特殊强化弹射」不含数值；character_text / 服务端镜像的\n技能描述不写 PF 倍率 ⇒ PF 倍率无需同步（测试断言文案无数字）。\n\n## 面板覆盖（同一模块追加，避免同一候选包两次回写）\n作者原话（本会话，主会话逐字转述）：「墨斯伊克也存在面板描述臃肿」；此前「同一个条件的提升能不能写到一起来简化描述」\n「引擎点火的获取带火属性共鸣,引擎点火提供的效果就不用写火属性共鸣,其他角色类似」。\n\nlive 1.4.1054 没有任何 ``desc_override_mosiyike*`` 键：队长与六个能力面板都由客户端按行自动生成（string_id\n``mosiyike`` / ``mosiyike_1..6`` 只有本角色使用）。合并规则（主会话定稿，见 ``panel_merge/scan.json``）：只合并同一面板里\n**数据条件完全相同**的行（除效果列外逐格相同，与 ``wf_balance_20260927c_panels.EFFECT_COLS`` 同口径）；「战斗开始时」\n一次性效果与常驻效果文案条件不同不并（先例 ``wf_balance_20260927c_bai`` / ``_gerald_wolf`` / ``_rolfmoon`` 与 scan\n``skipped_groups``）。有可合并组的面板写整块覆盖（覆盖文案会替换整块面板，其余行逐行写全），其余面板保持自动生成：\n\n=========================  =====================================================  ===============================\n面板（新键）               合并的数据行（0 基）                                   不并 / 说明\n=========================  =====================================================  ===============================\n队长 desc_override_         #1/#2（龙族编成≥3：龙族攻击力 240% / 充能 30%）       #3（kind 200 常驻）与 #4（kind 226\nmosiyike                                                                          开战执行一次）文案条件不同\n能力1 …_1                  #1/#2（常驻：龙族生命值 15% / 队长攻击力 100%）       #0 开幕玛纳、#3 龙族编成≥3 另起\n能力4 …_4                  #4/#5/#6（每层「翔风」，限 5：龙族攻击 / 充能 /        #0–#3 触发各异；#7 前置 188 另起\n                           强化弹射伤害）\n能力2 / 3 / 5 / 6          —（保持自动生成，不新建覆盖）                           能力2 #0（211 战斗开始时）与 #1\n                                                                                  （55 常驻）文案条件不同；3/5/6\n                                                                                  无同条件行\n=========================  =====================================================  ===============================\n\n每行文案由 :func:`render_line` 从数据现算（数值 1000=1%、100000=1 次 / 1 层 / 1 连击，对象 = 目标列 + 角色组列），\nrevise() 核对与登记文字逐字相同（fail closed）。共鸣省略不适用：「翔风」149997 只由能力4 #0–#3（461，无前置）授予，\n「风蚀」1499970 只由能力6 #0/#2（413，无前置）授予，技能两档 / PF 覆盖三档 DSL 不引用这两个固有号，本角色没有 629；\n所有面板行都不带属性共鸣前置（龙族编成是种族条件，不是共鸣）⇒ 没有「X属性共鸣时，」可省（:func:`state_basis_problems`）。\n\n能力4 #7（作者 2026-09-27 拍板「改成按层数生效」）：原前置 c6=188 ConditionCountUnique 数的是固有**实例个数**（461 叠层的\n「翔风」恒为 1 个），阈值 c9/c10=500000（≥5）永远不成立 ⇒ 原行永不触发。本模块把前置改为 144\nConditionAccumulationCountUnique（按层数；c7 puller 0、阈值与固有号 c12 不变，先例 live seofon_wind 1499953#0），\n面板写「自身「翔风」达到5层以上期间，…」（:func:`apply_stack_fix`）。\n能力4 #2（强化弹射Lv3 → 翔风＋3层）无同类问题。队长 #4 kind 226 AddCombo 挂 Initial 触发全库仅此一例：客户端\n``resolveInitialKind``（InstantBattle.AddCombo → 1）⇒ ``executeBootUp`` 开战执行一次，面板照此写「战斗开始时，连击＋5」。\n\ncapability：新键 ``desc_override_mosiyike*`` 需要 ``panel-description-override-v2``（旧 APK 读不到覆盖行，惰性回落自动生成，\n不崩）。没有生成器写这些面板（build_kit.py 只写行，且 gray3 后禁止重跑）。\n\n## 生成器\n- ``work/character_packs/mosiyike/build_kit.py``（能力/队长行）：gray3 导入后灰版是新真源，不得重跑（见\n  ``wf_balance_20260927b_gray3.GENERATORS``）；本次不涉及。\n- ``work/character_packs/mosiyike/build_pf.py``（PF 三档树）：第二批已同步 ``DETOUGHNESS``；主会话已把 ``TOTALS``\n  同步为 ``{1: 15.0, 2: 30.0, 3: 45.0}``（``round(total / n, 4)`` 恰得 7.5/6.0/4.5），测试\n  ``test_generator_sync_is_one_constant`` 断言 ``build_level`` == 本模块输出；第二批测试在内存里换回旧倍率核对第二批输出。\n  ``main()`` 会写包，仍禁止运行。\n\n## 候选\n``work/character_packs/mosiyike``（active owner）。候选 manifest 现值 0.1.2（gray3 写入）→ 0.1.3，快照键由暂存脚本给\n（``revision_20260927d``）。打开时 29 条既有漂移与第二批 ``REVIEWED_DRIFT`` 逐条同哈希（2026-09-27 链尾 1.4.1054 只读\n核对），沿用；PF 三档在候选里 = live = 第二批输出。\n\n纯函数：只转换 ``read()`` 给出的 live 输入，不写任何文件（接口见 ${WF_ROOT}/out/平衡调整批次-20260927/module_contract.md）。\n'
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from typing import Any

import wf_balance_20260927b_mosiyike as B
import wf_client_legality as L
import wf_midautumn_kitlib as KL

CID = B.CID
CODE = B.CODE
PACKAGES = ["mosiyike"]
#: 候选 manifest 现值 0.1.2（gray3）→ 递增。
PACKAGE_VERSION = {"mosiyike": "0.1.3"}
#: 三个新 ``desc_override_mosiyike*`` 键需要的面板覆盖补丁（``required_client_capabilities`` 核算，revise() 复核）。
CAPABILITIES: list[str] = ["panel-description-override-v2"]
#: 候选既有漂移：与第二批审过的 29 条逐条同哈希（2026-09-27 链尾 1.4.1054 只读核对），PF 三档不在其中。
REVIEWED_DRIFT = dict(B.REVIEWED_DRIFT)
ELEMENT = B.ELEMENT

PF_ACTION = B.PF_ACTION
PF_LEVELS = B.PF_LEVELS
PF_PROGRAMS = B.PF_PROGRAMS
PF_CAP = B.PF_CAP
TOLERANCE = B.TOLERANCE

#: 每档：(风刃发数, 现每发倍率, 灰服 1.4.85 每发倍率)。
MULT_PLAN = {1: (2, 12.5, 7.5), 2: (5, 8.28, 6.0), 3: (10, 6.44, 4.5)}
#: 每发削韧 p13 = 第二批落值（本轮不动）。
P13 = {level: B.PF_PLAN[level][2] for level in PF_LEVELS}
#: 灰版树里每发风刃的 p13（灰服没动削韧）。
GRAY_P13 = 5

#: 面板覆盖的输入：队长 / 六个能力键（只读，面板从这些行现算）、PF 覆盖说明文案、两个固有状态行（名称 / 上限）、
#: 技能两档 DSL（共鸣省略依据：核对固有状态的 DSL 来源）。
LEADER_KEY = CID
ABILITY_KEYS = tuple(f"{CID}{slot}" for slot in range(1, 7))
UQ = "master/character/unique_condition.orderedmap"
#: 本角色的固有状态：号 → (名称 unique_condition c1, 上限 c4)。
UNIQUES = {"149997": ("翔风", 5), "1499970": ("风蚀", 5)}
PF_TEXT_KEY = f"override_string_{CODE}"          # 队长 722 行 c82 的说明文案键（自动面板第 1 行原文）
SKILL_PROGRAMS = tuple(f"battle/action/skill/action/rare5/{CODE}${CODE}_{n}" for n in (1, 2))

#: live 输入基线（2026-09-27 本地链尾 1.4.1054 只读取数 = 第二批产物；Lv1 = 第二批输入）。任一不符 ⇒ 拒绝。
#: 面板相关各项 = gray3 导入后的 live 1.4.1054（能力 2/3/5 为灰版；队长、能力 1/4/6、两个固有状态、技能两档与
#: ``wf_balance_20260927b_gray3.BEFORE_BY_CID["149997"]`` 同项逐字相同，gray3 未改）。
BEFORE = {
    ("table", PF_ACTION): B.BEFORE["table", PF_ACTION],
    ("dsl", PF_PROGRAMS[1]): "0d48ffe946c1b15280777b1f334ff74fbb1fac084ad8d5e43d2ec5b37384bd0b",
    ("dsl", PF_PROGRAMS[2]): "a5db9c91eb1c8fec47274b67bf4ee4942d59f74c1afade10294ee9653381f0ee",
    ("dsl", PF_PROGRAMS[3]): "e3bbdd30609c7de850c1e23f1982af259ab884e57e2cf9bee6acbf0fcb1344e7",
    ("leader", LEADER_KEY): "fa27b1df32398053c67429e8e1f2cbe96c2cc79f5cd1657a2ee08ca1d2a16f1c",
    ("ability", ABILITY_KEYS[0]): "f310d6741ac6555cc44e9f7fee3739847b833e079f8365237e16571345fc8e6c",
    ("ability", ABILITY_KEYS[1]): "b78524997b255b1826de6bd21b191de3690cd8aa025f3c6aa4ec06991e5d8e90",
    ("ability", ABILITY_KEYS[2]): "11e2c122ffb0ac77b09de0ac7d67a025ed1e51bc31bcedbab4253c130391e0a0",
    ("ability", ABILITY_KEYS[3]): "c93412688ffbb5ca342555b0c429ebe493483fd0ee34ac7b73ab62329ccb0b3f",
    ("ability", ABILITY_KEYS[4]): "fb48beff1a4f98158874d8f52cb0c41d2f68fbe4f1e0eacf12cc7de558caa186",
    ("ability", ABILITY_KEYS[5]): "669b8e104f284eb75745797f91d628271d02693f2a5702131219d596739cbfa7",
    ("cas", PF_TEXT_KEY): "4ac5c3d2a3397b756bf92899f697ae641d6b859d3107cb7384553644db52a2f6",
    ("table", (UQ, "149997")): "a1a095dbc0dc908a31f0f4931e71f719899c0b28c5222fa5932055922845765e",
    ("table", (UQ, "1499970")): "1148be80be51e8317b857fae0517abb7235a4d4db4c23772a845369f1d9fe516",
    ("dsl", SKILL_PROGRAMS[0]): "8a21257d7e0b4844c18f7bb36e105633d5e983ea4a2c00d97afe61aae179b594",
    ("dsl", SKILL_PROGRAMS[1]): "cf8ecd48d87f6e9355ce1c0d825be99a52ad7e67eb04af712bfa8bf9e1fe08d7",
}
#: 面板覆盖键：live 必须全都不存在（read 抛 KeyError）——存在即说明面板已不是自动生成，本模块的前提失效。
PANEL_KEYS = {"leader": f"desc_override_{CODE}", **{slot: f"desc_override_{CODE}_{slot}" for slot in range(1, 7)}}
ABSENT = tuple(("cas", key) for key in PANEL_KEYS.values())
#: 本模块输出的树摘要（Lv1 = 灰版；其他测试据此判断 live / 候选是否已到本轮状态）。
AFTER = {
    PF_PROGRAMS[1]: "718934b910ad04a14b1c803245007fa4570061fcfdee376d15bf53347eef2e9f",
    PF_PROGRAMS[2]: "0e88719b07d76ed1eefde5cc7e7e0a629ff440680b8d0d44cbdbd17a620dce87",
    PF_PROGRAMS[3]: "9c97eb34307012a8746b61256847ba5422b38408012fc00ff5195ca5dd2239ba",
}

#: 灰链来源（相对仓库根）。
GRAY_CHAIN = "work/codex_out/gray-audit-20260830/gray/assets/asset-patch/active"
GRAY_ARCHIVE = "pinball-1.4.84-1.4.85-1-0821-mosiyike-balance-ios.zip"
GRAY_EDGE = ("1.4.84", "1.4.85")
#: 灰版三档成员原字节（raw deflate）的 sha256。
GRAY_PF_DEFLATE_SHA256 = {
    1: "9e29e4b420d7a8575897565e80cf98b1d42c356691db6b94226048f43e062aaa",
    2: "00d2d9b856dd24ec6d5f44f4d1b14f36136c20ce1489e1f9757cd03eef645015",
    3: "fb28451bbee81897099174f834009bc085fc2d847d5ba1643fd2b2516b15976a",
}
#: 灰版三档解析树的 digest()。
GRAY_PF_TREE_DIGEST = {
    1: "718934b910ad04a14b1c803245007fa4570061fcfdee376d15bf53347eef2e9f",
    2: "8f6ea6009ebefa5ea7e2752a8c6fd37e2348877d53249b1814890fc8240d1aaf",
    3: "720114922b08cfd30137a290b39574f5e739fcab5927989bef88d2b23c1f97c6",
}

digest = B.digest
detoughness = B.detoughness
hit_areas = B.hit_areas
dsl_problems = B.dsl_problems


def _baseline(read) -> dict:
    """读取并锁定全部输入；任何一项漂移都拒绝（fail closed）。"""
    inputs = {}
    for kind, key in BEFORE:
        value = read(kind, key)
        if value is None or digest(value) != BEFORE[kind, key]:
            raise ValueError(f"unreviewed live baseline: {kind}:{key}")
        inputs[kind, key] = deepcopy(value)
    if inputs["table", PF_ACTION] != [[PF_PROGRAMS[level] for level in PF_LEVELS]]:
        raise ValueError("power_flip_action no longer points at the reviewed PF trees")
    for kind, key in ABSENT:
        try:
            value = read(kind, key)
        except KeyError:
            continue
        if value is not None:
            raise ValueError(f"unreviewed live baseline: {kind}:{key} already exists (panel is no longer auto)")
    return inputs


def _slv(args, index: int, what: str):
    value = args[index]
    if (not isinstance(value, list) or len(value) != 1 or set(value[0]) != {"min", "max"}
            or value[0]["min"] != value[0]["max"] or type(value[0]["min"]) is not type(value[0]["max"])):
        raise ValueError(f"unreviewed CreateNormalAttack {what} shape: {value}")
    return value[0]["max"]


def multiplier(args):
    """CreateNormalAttack 攻击倍率 args[6]（wf_dsl_sig：攻击倍率(每段,SLv1→满级)）。"""
    return _slv(args, 6, "multiplier")


def wave_attacks(tree, level: int, mult: float, p13) -> list:
    """每发风刃判定区（球锚定 -18、坐标 EF、1 段、onHit 一条 CreateNormalAttack）的攻击参数；形状或数值不符即拒绝。"""
    waves = MULT_PLAN[level][0]
    areas = hit_areas(tree)
    shape = [(args[2], args[3], n, [(multiplier(a), type(multiplier(a)), B._p13(a)) for a in attacks])
             for args, n, attacks in areas]
    want = [(-18, ["EF"], 1, [(mult, float, p13)])] * waves
    if shape != want:
        raise ValueError(f"PF lv{level}: wind-blade preimage drift {shape}")
    return [attacks[0] for _, _, attacks in areas]


def gray_view(tree, level: int) -> list:
    """把本轮树的每发风刃 p13 换回灰版的 5：结果应与灰服 1.4.85 的树逐字相同。"""
    view = deepcopy(tree)
    for attack in wave_attacks(view, level, MULT_PLAN[level][2], P13[level]):
        attack[13] = [{"min": GRAY_P13, "max": GRAY_P13}]
    return view


def revise_pf_tree(tree, level: int) -> list:
    """PF 覆盖树第 level 档：每发风刃倍率改到灰服值，p13 与其余节点逐字保持；不改输入。"""
    what = f"PF lv{level}"
    result = deepcopy(tree)
    if result[:11] != ["ActionDsl", 1, ["None"], *[False] * 7, 0]:
        raise ValueError(f"{what}: root header drift")
    waves, before, after = MULT_PLAN[level]
    for attack in wave_attacks(result, level, before, P13[level]):
        attack[6] = [{"min": after, "max": after}]
    total = detoughness(result)
    if total > PF_CAP[level] + TOLERANCE or abs(total - waves * P13[level]) > TOLERANCE:
        raise ValueError(f"{what}: detoughness {total} moved or over cap {PF_CAP[level]}")
    if digest(gray_view(result, level)) != GRAY_PF_TREE_DIGEST[level]:
        raise ValueError(f"{what}: result differs from the gray 1.4.85 tree beyond the batch-2 p13")
    return result


def total_multiplier(tree, level: int) -> float:
    return round(sum(multiplier(a) for a in wave_attacks(tree, level, MULT_PLAN[level][2], P13[level])), 6)


# ====================================================================== 面板覆盖（第三轮 c 追加）


class PanelError(ValueError):
    pass


MAIN_ICON = " <icon id='main'>  "
#: 表布局：触发方式列、前置块基址、瞬发触发 / 触发前置 / 延迟 / 内容基址、持续累积 / 触发 / 死亡 / 内容基址、开幕、行宽。
LAYOUT = {
    "leader": dict(trig=3, pre=(4, 11, 18), it=25, ipc=37, idelay=44, ic=45, dat=83, dt=95, dead=106, dc=107,
                   opening=121, unison=None, ncols=124),
    "ability": dict(trig=5, pre=(6, 13, 20), it=27, ipc=39, idelay=46, ic=47, dat=85, dt=97, dead=108, dc=109,
                    opening=123, unison=1, ncols=126),
}
#: 效果身份列（其余列逐格相同 = 数据条件相同）：瞬发内容 +0 种类 / +1 对象 / +2 对象组 / +4,+5 强度 / +21 固有号，
#: 持续内容 +0 / +1 / +2 / +4 / +5；能力表另加 c2 分类。与 ``wf_balance_20260927c_panels.EFFECT_COLS`` 同口径。
EFFECT_COLS = {
    table: frozenset({lay["ic"] + i for i in (0, 1, 2, 4, 5, 21)} | {lay["dc"] + i for i in (0, 1, 2, 4, 5)}
                     | ({2} if table == "ability" else set()))
    for table, lay in LAYOUT.items()
}
#: 瞬发 Initial（无触发）下只在开战执行一次的内容：面板写「战斗开始时，」，与常驻效果文案条件不同、不并。
#: 211 SkillGauge（先例 bai / gerald_wolf / rolfmoon）；226 AddCombo = InstantBattle，客户端
#: ``InstantAbilityTriggerMasterValueTools.resolveInitialKind`` → 1 ⇒ ``AbilitySlotImpl.executeBootUp`` 执行一次。
ONE_SHOT_INITIAL = frozenset({"211", "226"})
GRANT_KINDS = frozenset({"461", "413", "436", "459"})      # 瞬发内容授予固有状态（固有号在 +21）
PRE_UNIQUE = frozenset({"144", "187", "188", "199"})       # 前置块按固有状态判定（固有号在 +6）
DT_UNIQUE = frozenset({"134", "171", "192", "194", "207"})  # 持续触发按固有状态计数（固有号在 +7）
ELEMENT_TOKENS = ("Red", "Blue", "Yellow", "Green", "White", "Black")
#: 角色组 → 面板称呼（种族条件，不是属性共鸣）。其他组一律拒绝（新增须先定措辞）。
GROUP_CN = {"Dragon": "龙族"}
PF_OVERRIDE = (f"{CODE}_pf", "1,2,3")       # 队长 722 行 c80 / c81

#: 覆盖面板登记：面板 → (表, 外层键, ((数据行号…, 文案), …))。文案逐字 = :func:`render_line` 从数据现算。
PANELS: dict[Any, tuple[str, str, tuple[tuple[tuple[int, ...], str], ...]]] = {
    "leader": ("leader", LEADER_KEY, (
        ((0,), "追加「苍穹风刃」特殊强化弹射"),
        ((1, 2), "队伍中编入3名以上龙族角色时，龙族角色攻击力＋240%、技能充能速度＋30%"),
        ((3,), "强化弹射Lv3所需连击数－8"),
        ((4,), "战斗开始时，连击＋5"),
    )),
    1: ("ability", ABILITY_KEYS[0], (
        ((0,), "玛纳获得数量＋100%"),
        ((1, 2), "龙族角色生命值＋15%，队长攻击力＋100%"),
        ((3,), "队伍中编入3名以上龙族角色时，龙族角色攻击力＋240%"),
    )),
    4: ("ability", ABILITY_KEYS[3], (
        ((0,), "发动强化弹射Lv1时，自身「翔风」＋1层"),
        ((1,), "发动强化弹射Lv2时，自身「翔风」＋2层"),
        ((2,), "发动强化弹射Lv3时，自身「翔风」＋3层"),
        ((3,), "自身发动技能时，自身「翔风」＋2层"),
        ((4, 5, 6), "每1层「翔风」，龙族角色攻击力＋20%、技能充能速度＋3%，强化弹射伤害＋15%（最多5层）"),
        ((7,), "自身「翔风」达到5层以上期间，发动强化弹射时，队伍全体的最大速度固定效果持续时间＋30%"),
    )),
}
#: 保持自动生成的面板（无可合并组、无可省略共鸣）。
AUTO_PANELS = (2, 3, 5, 6)
#: 数据条件相同、文案条件不同而不并的行（:data:`ONE_SHOT_INITIAL`）。
NOT_MERGED = {
    "leader": ((3, 4), "#3 kind 200 常驻（强化弹射Lv3所需连击数）与 #4 kind 226 AddCombo（开战执行一次，"
                       "「战斗开始时」）文案条件不同"),
    2: ((0, 1), "#0 kind 211 战斗开始时一次性充能与 #1 kind 55 常驻强化弹射伤害文案条件不同 ⇒ 能力2 无可合并组"),
}
#: 已知潜伏问题（照数据写进面板，不改数据）。
LATENT = {
    "ability4#7": ("已修（作者 2026-09-27「改成按层数生效」）：原前置 188 ConditionCountUnique 数固有实例个数（461 叠层的"
                   "「翔风」恒为 1 个），阈值 ≥5 永远不成立；本模块改为前置 144（按层数，阈值/固有号不变）"),
    "ability4#2": "强化弹射Lv3 → 翔风＋3层（461，无前置），无同类问题",
    "leader#4": ("kind 226 AddCombo 挂 Initial 全库仅此一例：开战执行一次（连击＋5），不是每次弹射；"
                 "若设计意图是常驻加连击需改触发（作者决定）"),
}


#: 能力4 #7 的按层数修正（作者 2026-09-27）：(能力槽, 行号, 审核过的原前置块, 新前置种类)。
STACK_FIX = (4, 7, ("188", "0", "500000", "500000", "149997"), "144")
STACK_FIX_DECISION = ("2026-09-27 AskUserQuestion：墨斯伊克能力4「持有5个以上翔风期间，发动强化弹射时，队伍全体的最大速度固定"
                      "效果持续时间+30%」永远不会触发（条件数的是状态个数），怎么处理？→「改成按层数生效」")


def apply_stack_fix(rows: list[list[str]]) -> list[list[str]]:
    """返回能力4 的新行：#7 前置 188 → 144（按「翔风」层数），其余逐字不变；原行形状不符就拒绝（fail closed）。"""
    _slot, index, reviewed, kind = STACK_FIX
    out = deepcopy(rows)
    row = out[index]
    if tuple(row[c] for c in (6, 7, 9, 10, 12)) != reviewed:
        raise ValueError(f"ability4#{index} is no longer the reviewed 188 row: {tuple(row[c] for c in (6, 7, 9, 10, 12))}")
    row[6] = kind
    problems = L.client_legality_problems("ability", row) + L.declared_block_field_problems("ability", row)
    if problems:
        raise ValueError(f"ability4#{index}: {problems}")
    return out


def panel_text(panel) -> str:
    return "\n".join(text for _rows, text in PANELS[panel][2])


def _table_of(panel) -> str:
    return "leader" if panel == "leader" else "ability"


def _n(value: str) -> str:
    value = (value or "").strip()
    return "" if value in ("(None)",) else value


def _pct(value: str) -> str:
    """强度（×1000 = 1%）→「x%」；只接受整百分数。"""
    number = int(value)
    if number <= 0 or number % 1000:
        raise PanelError(f"strength {value!r} is not a positive whole percent")
    return f"{number // 1000}%"


def _count(value: str) -> int:
    """次数 / 层数 / 连击（×100000 = 1）。"""
    number = int(value)
    if number <= 0 or number % 100000:
        raise PanelError(f"count {value!r} is not a positive whole number")
    return number // 100000


def _same(row: list[str], a: int, b: int, what: str) -> str:
    if row[a] != row[b]:
        raise PanelError(f"{what}: low {row[a]!r} != high {row[b]!r} (single-value panel only)")
    return row[a]


def _object(target: str, group: str) -> str:
    group = _n(group)
    if target == "5" and group in GROUP_CN:
        return f"{GROUP_CN[group]}角色"
    if target == "2" and not group:
        return "队长"
    if target == "0" and not group:
        return "自身"
    raise PanelError(f"unreviewed ability target {target!r}/{group!r}")


def unique_names(inputs: dict) -> dict[str, str]:
    """固有号 → 名称（unique_condition c1），并核对上限 c4 与登记值一致。"""
    names = {}
    for uid, (name, cap) in UNIQUES.items():
        rows = inputs["table", (UQ, uid)]
        if len(rows) != 1 or rows[0][1] != name or rows[0][4] != str(cap):
            raise PanelError(f"unique condition {uid} is not {name!r} with cap {cap}")
        names[uid] = name
    return names


def precondition_blocks(table: str, row: list[str]) -> list[tuple[str, ...]]:
    """非恒真的前置块（7 格：种类、puller、puller 组、下限、上限、角色组、固有号）。"""
    out = []
    for base in LAYOUT[table]["pre"]:
        kind = row[base].strip()
        if kind in ("", "0", "(None)"):
            continue
        out.append(tuple(row[base + i].strip() for i in range(7)))
    return out


def resonance_of(block: tuple[str, ...]) -> str | None:
    """前置块是「X 编成≥6」（属性共鸣）⇒ 属性组串，否则 None。"""
    kind, _puller, puller_group, low, high, group, _uid = block
    if (kind == "2" and low == "600000" and high in ("600000", "") and _n(group)
            and _n(puller_group) in ("", "0") and all(t in ELEMENT_TOKENS for t in group.split(","))):
        return group
    return None


def _main_icon(table: str, row: list[str]) -> bool:
    unison = LAYOUT[table]["unison"]
    return (unison is not None and row[unison] == "false") or any(b[0] == "202" for b in precondition_blocks(table, row))


def _precondition_text(table: str, row: list[str], names: dict[str, str]) -> str:
    parts = []
    for kind, puller, puller_group, low, high, group, uid in precondition_blocks(table, row):
        if kind == "202":
            continue                                   # 仅主位：由主位图标表达
        if kind == "2" and not _n(puller) and not _n(puller_group) and _n(group) in GROUP_CN and low == high:
            parts.append(f"队伍中编入{_count(low)}名以上{GROUP_CN[group]}角色时，")
        elif kind == "188" and puller == "0" and not _n(puller_group) and low == high and uid in names:
            parts.append(f"自身持有{_count(low)}个以上「{names[uid]}」期间，")
        elif kind == "144" and puller == "0" and not _n(puller_group) and low == high and uid in names:
            parts.append(f"自身「{names[uid]}」达到{_count(low)}层以上期间，")
        else:
            raise PanelError(f"unreviewed precondition block {(kind, puller, puller_group, low, high, group, uid)}")
    return "".join(parts)


def _instant_trigger_text(table: str, row: list[str]) -> str:
    lay = LAYOUT[table]
    it = lay["it"]
    kind = row[it]
    if _n(row[lay["ipc"]]) or row[lay["idelay"]] not in ("", "0"):
        raise PanelError("unreviewed instant precontent / delay")
    if kind == "0":
        return "战斗开始时，" if row[lay["ic"]] in ONE_SHOT_INITIAL else ""
    threshold = _same(row, it + 3, it + 4, "trigger threshold")
    if threshold != "100000" or _n(row[it + 7]) or row[it + 8] not in ("", "0"):
        raise PanelError(f"unreviewed trigger shape (threshold / limit / CT) on kind {kind}")
    if kind in ("63", "64", "65"):
        return f"发动强化弹射Lv{int(kind) - 62}时，"
    if kind == "23" and row[it + 1] == "0" and not _n(row[it + 2]):
        return "自身发动技能时，"
    if kind == "2":
        return "发动强化弹射时，"
    raise PanelError(f"unreviewed instant trigger kind {kind}")


def _instant_effect(table: str, row: list[str], names: dict[str, str], pf_text: str) -> tuple[str | None, str]:
    ic = LAYOUT[table]["ic"]
    kind = row[ic]
    if kind == "722":
        if (row[ic + 35], row[ic + 36], row[ic + 37]) != (*PF_OVERRIDE, PF_TEXT_KEY):
            raise PanelError("unreviewed 722 PF override cells")
        return None, pf_text
    value = _same(row, ic + 4, ic + 5, f"kind {kind} strength")
    if kind in ("32", "35", "205"):
        effect = {"32": "攻击力", "35": "技能充能速度", "205": "生命值"}[kind]
        return _object(row[ic + 1], row[ic + 2]), f"{effect}＋{_pct(value)}"
    if kind == "200":
        return None, f"强化弹射Lv3所需连击数－{_count(value)}"
    if kind == "226":
        return None, f"连击＋{_count(value)}"
    if kind == "690":                             # 客户端固定 Party 目标（InstantAbilitySource.as case 690）
        return None, f"队伍全体的最大速度固定效果持续时间＋{_pct(value)}"
    if kind == "461":
        uid = row[ic + 21]
        if (uid not in names or row[ic + 1] != "0" or _same(row, ic + 12, ic + 13, "461 number") != "100000"
                or (row[ic + 27], row[ic + 28]) != ("1", "0")):
            raise PanelError("unreviewed 461 grant shape")
        return "自身", f"「{names[uid]}」＋{_count(value)}层"
    raise PanelError(f"unreviewed instant content kind {kind}")


def _during(table: str, row: list[str], names: dict[str, str]) -> tuple[str, tuple[str | None, str], str]:
    lay = LAYOUT[table]
    dt, dc = lay["dt"], lay["dc"]
    if _n(row[lay["dat"]]) or row[lay["dead"]] != "false":
        raise PanelError("unreviewed during accumulation / owner-dead cells")
    if not (row[dt] == "134" and row[dt + 1] == "0" and not _n(row[dt + 2]) and row[dt + 7] in names
            and _same(row, dt + 3, dt + 4, "134 threshold") == "100000"):
        raise PanelError(f"unreviewed during trigger {row[dt:dt + 11]}")
    limit = int(row[dt + 5])
    prefix, suffix = f"每1层「{names[row[dt + 7]]}」，", f"（最多{limit}层）"
    kind, value = row[dc], _same(row, dc + 4, dc + 5, f"during {row[dc]} strength")
    if kind in ("0", "3"):
        effect = {"0": "攻击力", "3": "技能充能速度"}[kind]
        return prefix, (_object(row[dc + 1], row[dc + 2]), f"{effect}＋{_pct(value)}"), suffix
    if kind == "23":                              # PowerFlipDamage 只读强度（无目标列）
        return prefix, (None, f"强化弹射伤害＋{_pct(value)}"), suffix
    raise PanelError(f"unreviewed during content kind {kind}")


def _opening(table: str, row: list[str]) -> tuple[str | None, str]:
    base = LAYOUT[table]["opening"]
    if row[base] != "2":
        raise PanelError(f"unreviewed opening kind {row[base]!r}")
    value = Decimal(_same(row, base + 1, base + 2, "opening strength")) * 100
    if value <= 0 or value != value.to_integral_value():
        raise PanelError(f"opening strength {row[base + 1]!r} is not a whole percent")
    return None, f"玛纳获得数量＋{int(value)}%"


def row_parts(table: str, row: list[str], names: dict[str, str], pf_text: str):
    """一行 → (主位图标, 条件前缀, (对象, 效果), 后缀)。任何未审形状都拒绝（fail closed）。"""
    if len(row) != LAYOUT[table]["ncols"]:
        raise PanelError(f"{table} row width {len(row)}")
    mode = row[LAYOUT[table]["trig"]]
    icon = _main_icon(table, row)
    if mode == "2":
        return icon, "", _opening(table, row), ""
    pre = _precondition_text(table, row, names)
    if mode == "0":
        return icon, pre + _instant_trigger_text(table, row), _instant_effect(table, row, names, pf_text), ""
    if mode == "1":
        prefix, effect, suffix = _during(table, row, names)
        return icon, pre + prefix, effect, suffix
    raise PanelError(f"unreviewed trigger mode {mode!r}")


def text_condition(table: str, row: list[str]) -> tuple:
    """文案条件签名 = 数据条件（除效果列外逐格）+ 是否「战斗开始时」一次性效果。"""
    lay = LAYOUT[table]
    cells = tuple(value for col, value in enumerate(row) if col not in EFFECT_COLS[table])
    one_shot = row[lay["trig"]] == "0" and row[lay["it"]] == "0" and row[lay["ic"]] in ONE_SHOT_INITIAL
    return cells, one_shot


def condition_groups(table: str, rows: list[list[str]], *, text: bool = True) -> list[tuple[int, ...]]:
    """同条件行组（≥2 行）：``text=True`` 按文案条件，``False`` 只按数据条件。"""
    groups: dict[Any, list[int]] = {}
    for index, row in enumerate(rows):
        sig = text_condition(table, row) if text else text_condition(table, row)[0]
        groups.setdefault(sig, []).append(index)
    return [tuple(group) for group in groups.values() if len(group) > 1]


def render_line(table: str, rows: list[list[str]], indexes: tuple[int, ...], names: dict[str, str],
                pf_text: str) -> str:
    """同一文案条件的若干数据行 → 一行面板文案：「<条件>，<对象A><效果1>、<效果2>，<对象B><效果3><后缀>」。"""
    parts = [row_parts(table, rows[i], names, pf_text) for i in indexes]
    if len({text_condition(table, rows[i]) for i in indexes}) != 1:
        raise PanelError(f"{table} rows {indexes} differ in text conditions")
    icon, prefix, _effect, suffix = parts[0]
    if any((p[0], p[1], p[3]) != (icon, prefix, suffix) for p in parts):
        raise PanelError(f"{table} rows {indexes} render different conditions")
    chunks: list[tuple[str | None, list[str]]] = []
    for _i, _p, (obj, effect), _s in parts:
        if chunks and chunks[-1][0] == obj:
            chunks[-1][1].append(effect)
        else:
            chunks.append((obj, [effect]))
    body = "，".join((obj or "") + "、".join(effects) for obj, effects in chunks)
    return (MAIN_ICON if icon else "") + prefix + body + suffix


def render_panel(table: str, rows: list[list[str]], layout, names: dict[str, str], pf_text: str) -> list[str]:
    return [render_line(table, rows, indexes, names, pf_text) for indexes, _text in layout]


def unmerged_lines(table: str, rows: list[list[str]], names: dict[str, str], pf_text: str) -> list[str]:
    """合并前：每条数据行单独一行（同一措辞），供 check_merge 核对合并前后效果数值 / 效果名 / 行序。"""
    return [render_line(table, rows, (index,), names, pf_text) for index in range(len(rows))]


def layout_problems(panel, rows: list[list[str]]) -> list[str]:
    """登记的行分组：覆盖全部数据行、各一次、保持行序；合并组 = 文案同条件组（组内同条件、组外无同条件行）。"""
    table, _key, layout = PANELS[panel]
    problems = []
    flat = [i for indexes, _text in layout for i in indexes]
    if flat != list(range(len(rows))):
        problems.append(f"panel {panel}: rows {flat} do not cover 0..{len(rows) - 1} once in order")
    merged = sorted(indexes for indexes, _text in layout if len(indexes) > 1)
    if merged != sorted(condition_groups(table, rows)):
        problems.append(f"panel {panel}: merged {merged} != same-text-condition groups "
                        f"{condition_groups(table, rows)}")
    return problems


def census_problems(tables: dict[Any, list[list[str]]]) -> list[str]:
    """面板普查：有文案同条件组的面板 == 登记的覆盖面板；数据同条件而不并的只有 :data:`NOT_MERGED`。"""
    problems = []
    with_groups = {panel for panel, rows in tables.items() if condition_groups(_table_of(panel), rows)}
    if with_groups != set(PANELS):
        problems.append(f"panels with mergeable groups {sorted(map(str, with_groups))} != {sorted(map(str, PANELS))}")
    for panel, rows in tables.items():
        table = _table_of(panel)
        split = sorted(set(condition_groups(table, rows, text=False)) - set(condition_groups(table, rows)))
        want = [NOT_MERGED[panel][0]] if panel in NOT_MERGED else []
        if split != want:
            problems.append(f"panel {panel}: data-only groups {split} != reviewed {want}")
    if set(tables) - set(PANELS) != set(AUTO_PANELS):
        problems.append("auto panel list drifted")
    return problems


def uid_roles(table: str, row: list[str]) -> list[tuple[int, str, str]]:
    """行里每个写着本角色固有号的格：(列, 固有号, grant / depends / unknown)。"""
    lay = LAYOUT[table]
    roles = []
    for col, value in enumerate(row):
        if value.strip() not in UNIQUES:
            continue
        if any(col == base + 6 and row[base].strip() in PRE_UNIQUE for base in lay["pre"]):
            role = "depends"
        elif col == lay["dt"] + 7 and row[lay["dt"]].strip() in DT_UNIQUE:
            role = "depends"
        elif col == lay["ic"] + 21 and row[lay["ic"]].strip() in GRANT_KINDS:
            role = "grant"
        else:
            role = "unknown"
        roles.append((col, value.strip(), role))
    return roles


def dsl_uid_refs(tree) -> list[tuple]:
    """DSL 里出现本角色固有号的位置（任何形态：DCUnique / ACUnique / 裸数值）。"""
    found = []
    uids = {int(uid) for uid in UNIQUES}

    def walk(node, path):
        if isinstance(node, list):
            for i, child in enumerate(node):
                walk(child, (*path, i))
        elif isinstance(node, dict):
            for key, child in node.items():
                walk(child, (*path, key))
        elif not isinstance(node, bool) and (node in uids or node in UNIQUES):
            found.append(path)

    walk(tree, ())
    return found


#: 固有状态全部获取来源（改前 = 改后数据；逐条都不带属性共鸣）与依赖行。多一条 / 少一条 ⇒ 共鸣省略要重核。
STATE_SOURCES = {
    "149997": {"grant": ("ability:1499974#0", "ability:1499974#1", "ability:1499974#2", "ability:1499974#3"),
               "depends": ("ability:1499974#4", "ability:1499974#5", "ability:1499974#6", "ability:1499974#7")},
    "1499970": {"grant": ("ability:1499976#0", "ability:1499976#2"), "depends": ("ability:1499976#1",)},
}


def state_basis_problems(tables: dict[tuple[str, str], list[list[str]]], trees: dict[str, Any]) -> list[str]:
    """共鸣省略依据（作者「引擎点火的获取带火属性共鸣,……其他角色类似」）逐个状态核对全部来源：

    词条 / 队长行（授予 = 461/413… 的固有号格，依赖 = 前置 / 持续触发的固有号格）+ 技能两档与 PF 覆盖三档 DSL。
    本角色：两个状态都有不带共鸣的授予行、DSL 不引用 ⇒ 省略不适用；并且没有任何行带属性共鸣前置（面板里没有可省的
    「X属性共鸣时，」）。来源集合变化、认不出的固有号格、DSL 引用、行带共鸣、629 调起未读程序 ⇒ 报错（fail closed）。"""
    problems = []
    seen: dict[str, dict[str, list[str]]] = {uid: {"grant": [], "depends": []} for uid in UNIQUES}
    for (table, key), rows in tables.items():
        lay = LAYOUT[table]
        for index, row in enumerate(rows):
            label = f"{table}:{key}#{index}"
            resonances = {resonance_of(block) for block in precondition_blocks(table, row)} - {None}
            if resonances:
                problems.append(f"{label}: carries an element resonance precondition {sorted(resonances)}")
            if row[lay["ic"]] == "629" or row[lay["dc"]] == "629":
                problems.append(f"{label}: 629 invokes a program that is not read")
            for col, uid, role in uid_roles(table, row):
                if role == "unknown":
                    problems.append(f"{label} c{col}: unique id {uid} in an unrecognised column")
                else:
                    seen[uid][role].append(label)
    for uid, want in STATE_SOURCES.items():
        got = {role: tuple(labels) for role, labels in seen[uid].items()}
        if got != want:
            problems.append(f"unique {uid} sources {got} != reviewed {want}")
    for program, tree in trees.items():
        for path in dsl_uid_refs(tree):
            problems.append(f"{program} {path}: DSL references a mosiyike unique id (resonance omission needs review)")
    return problems


def panel_problems(key: str, text: str) -> list[str]:
    """面板规则：kitlib 禁写（不含技能强化条目，``skill_flag=False``）+ 不用「／」、共鸣写法、主位图标行首。"""
    problems = KL.panel_problems(text, skill_flag=False)
    for number, line in enumerate(text.split("\n"), 1):
        core = line[len(MAIN_ICON):] if line.startswith(MAIN_ICON) else line
        if "／" in core or "<icon" in core:
            problems.append(f"{key} L{number}: 「／」 or a misplaced icon")
        if "属性共鸣时" in core and "属性共鸣时，" not in core:
            problems.append(f"{key} L{number}: resonance must be written 「X属性共鸣时，」")
        if not core or core != core.strip():
            problems.append(f"{key} L{number}: empty line or stray spaces")
    return problems


def panels(inputs: dict) -> dict[str, list[list[str]]]:
    """从 live 行现算三块覆盖面板，核对登记文字 / 分组 / 普查 / 共鸣依据 / 面板规则 / capability（fail closed）。"""
    names = unique_names(inputs)
    pf_rows = inputs["cas", PF_TEXT_KEY]
    if len(pf_rows) != 1 or len(pf_rows[0]) != 1:
        raise PanelError("unexpected override_string row shape")
    pf_text = pf_rows[0][0]
    tables = {"leader": inputs["leader", LEADER_KEY],
              **{slot: inputs["ability", key] for slot, key in enumerate(ABILITY_KEYS, 1)}}
    problems = census_problems(tables)
    cas = {}
    for panel, (table, key, layout) in PANELS.items():
        rows = tables[panel]
        problems += layout_problems(panel, rows)
        rendered = render_panel(table, rows, layout, names, pf_text)
        registered = [text for _indexes, text in layout]
        if rendered != registered:
            problems.append(f"panel {panel}: rendered {rendered} != registered {registered}")
        text = "\n".join(registered)
        problems += panel_problems(PANEL_KEYS[panel], text)
        cas[PANEL_KEYS[panel]] = [[text]]
    by_key = {("leader", LEADER_KEY): tables["leader"],
              **{("ability", key): tables[slot] for slot, key in enumerate(ABILITY_KEYS, 1)}}
    trees = {**{program: inputs["dsl", program] for program in SKILL_PROGRAMS},
             **{PF_PROGRAMS[level]: inputs["dsl", PF_PROGRAMS[level]] for level in PF_LEVELS}}
    problems += state_basis_problems(by_key, trees)
    caps = sorted({cap for key in cas for cap in L.required_client_capabilities("custom_ability_string", [key])})
    if caps != sorted(CAPABILITIES):
        problems.append(f"capabilities {caps} != {CAPABILITIES}")
    if problems:
        raise PanelError("; ".join(problems))
    return cas


def revise(read) -> dict:
    inputs = _baseline(read)
    fix_key = ABILITY_KEYS[STACK_FIX[0] - 1]
    inputs["ability", fix_key] = apply_stack_fix(inputs["ability", fix_key])     # 面板按修正后的行渲染
    dsl = {PF_PROGRAMS[level]: revise_pf_tree(inputs["dsl", PF_PROGRAMS[level]], level) for level in PF_LEVELS}
    problems = [f"dsl {program}: {p}" for program, tree in dsl.items() for p in dsl_problems(tree)]
    if problems:
        raise ValueError("; ".join(problems))
    cas = panels(inputs)
    return {
        "ability": {fix_key: inputs["ability", fix_key]}, "leader": {}, "cas": cas, "text": {}, "table": {},
        "action": {}, "dsl": dsl, "server_text": {}, "new_programs": [],
        "notes": {
            "source": "wf_balance_20260927c_mosiyike.py",
            "author_decision": ("2026-09-27 AskUserQuestion：灰服 1.4.85 风刃倍率 12.5/8.28/6.44 → 7.5/6.0/4.5，"
                                "要跟着降吗（削韧保持第二批 10/20/25）→「跟着降到灰服倍率」"),
            "pf_wave_multiplier": {f"lv{level}": [MULT_PLAN[level][1], MULT_PLAN[level][2]] for level in PF_LEVELS},
            "pf_total_multiplier": {f"lv{level}": [round(MULT_PLAN[level][0] * MULT_PLAN[level][1], 6),
                                                   total_multiplier(dsl[PF_PROGRAMS[level]], level)]
                                    for level in PF_LEVELS},
            "pf_detoughness_unchanged": {f"lv{level}": detoughness(dsl[PF_PROGRAMS[level]]) for level in PF_LEVELS},
            "gray_source": {"chain": GRAY_CHAIN, "archive": GRAY_ARCHIVE, "edge": list(GRAY_EDGE),
                            "deflate_sha256": {f"lv{k}": v for k, v in GRAY_PF_DEFLATE_SHA256.items()},
                            "tree_digest": {f"lv{k}": v for k, v in GRAY_PF_TREE_DIGEST.items()}},
            "gray_diff": ("灰版 vs 我方第二批之前：只差每发风刃 CreateNormalAttack args[6]（Lv1 4 叶 / Lv2 10 叶 / Lv3 20 叶）；"
                          "本轮输出 = 灰版 + 第二批 p13 5/4/2.5（Lv1 与灰版逐字节相同）"),
            "gray_unknown": "灰链归档止于 1.4.93，gray3 压缩包不含 PF 树：灰方 1.4.93 之后是否再调 PF 未知",
            "text_sync": ("override_string_mosiyike「追加「苍穹风刃」特殊强化弹射」不含数值，不改；它原样作为新队长覆盖面板"
                          "第 1 行（722 行的自动描述）"),
            "generators": ("build_kit.py：gray3 后不得重跑（能力4 #7 的 144 修正只在本模块）；build_pf.py：TOTALS 已同步为 "
                           "{1: 15.0, 2: 30.0, 3: 45.0}（main() 会写包，仍禁止运行）；面板覆盖没有生成器"),
            "panel_request": ("作者「墨斯伊克也存在面板描述臃肿」；「同一个条件的提升能不能写到一起来简化描述」"
                              "「引擎点火的获取带火属性共鸣,引擎点火提供的效果就不用写火属性共鸣,其他角色类似」"),
            "panel_overrides": {PANEL_KEYS[panel]: {"table": table, "key": key,
                                                    "lines": [{"rows": list(indexes), "text": text}
                                                              for indexes, text in layout]}
                                for panel, (table, key, layout) in PANELS.items()},
            "panel_auto_kept": {PANEL_KEYS[panel]: "无可合并组、无可省略共鸣 ⇒ 保持客户端自动生成" for panel in AUTO_PANELS},
            "panel_not_merged": {str(panel): {"rows": list(rows), "reason": reason}
                                 for panel, (rows, reason) in NOT_MERGED.items()},
            "resonance_omission": ("不适用：翔风 149997 = 能力4 #0–#3（461 无前置）、风蚀 1499970 = 能力6 #0/#2（413 无前置），"
                                   "技能两档 / PF 覆盖三档 DSL 不引用，无 629；所有面板行都不带属性共鸣前置"),
            "latent_issues": dict(LATENT),
            "stack_fix": {"row": f"ability:{fix_key}#{STACK_FIX[1]}", "precondition": "188 → 144 ConditionAccumulationCountUnique",
                          "author_decision": STACK_FIX_DECISION,
                          "precedent": "live seofon_wind 1499953#0（144，c7=0，c12=固有号）"},
            "capabilities": list(CAPABILITIES),
            "runtime_verified": False,
        },
    }
