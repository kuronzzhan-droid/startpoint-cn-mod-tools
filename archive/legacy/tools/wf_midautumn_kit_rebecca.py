# -*- coding: utf-8 -*-
"""中秋批次 kit：蕾贝卡·中秋 169991 ``bearish_darkwitch_moon``（暗属性 PF 辅助）。

定位「强化弹射节奏辅助」：常驻降低 PF 所需连击（−c），每次强化弹射把连击补回来（+c），
抬高队长那一下 PF 的伤害；技能是一场影戏——点亮影灯，按下敌人的暗属性／全属性抗性并挂迟缓，
同时给全队贯通与强化弹射伤害。设计与数值以
``work/character_packs/midautumn-20260920/design/rebecca.{md,json}`` 为准 —— 本模块是
「设计 JSON 驱动」的薄壳：队长 6 行、词条 6 键 14 条记录的 donor／逐格改／预期 ``wf_describe``
全部从 ``design/rebecca.json`` 的 ``plan`` 块读出后交给 :func:`wf_midautumn_kitlib.build_row`
装配，两边漂移（donor 缺失、legality 不过、``wf_describe`` 对不上）当场报错，不在本文件里
手抄 20 行的具体数值（那是设计代理已实读核实过的产物，抄一遍只会引入新的转录错误）。

本模块自己负责的是设计 JSON 管不到的部分：

    - ``action_skill`` 两档：整行改用血脉母本 361007 ``bearish_darkwitch`` 的行形状
      （动作预设 ``dynamic/skill/atk_surround``），只覆盖 c0/c1（TEXTS）、c4/c5（能量）、c7（程序路径）；
    - 技能 DSL 两档：**官方 donor 树改参数**为主——主干＝她 ★3 自己的
      ``bearish_darkwitch_2``；从 ``blackflower_wiz_2`` 整块移植判定区节流三格与
      ``CreateNormalAttack``；从 ``herbalist_xm22_2``（荷莉·圣诞）整块移植
      ``FindAllSubjects(97)`` 全队增益块并把绑定 id 统一 +4；从
      ``psychic_teleport_playable_2`` 整块移植 ``ConditionalsHealthPointRatioOf`` ＋
      ``CreateRatioHeal``，装进主干自带的 ``FindAllSubjects(3, 35)``（rework1）；
    - 特效**零克隆**：主干自带的 ``battle/effect/skill_general/area/miasma`` 是通用共享件，
      直接引用官方路径（裁决 §4）；``B/pixel/rebecca/fx_lut.json`` 存在时才会被读到，
      本角色不克隆特效族 ⇒ LUT 只作记录、不参与装配；
    - 语音路由（kind 0 HpHigh 0.5）与 ``switched_action_skill`` 的 ``<code>_voice_ready``；
    - ``B/pixel/rebecca/install.json`` 里的像素小人成品（缺文件静默跳过）。

**不做**：722 专属 PF（裁决 §2「蕾贝卡：不做 722」）、固有状态、``custom_ability_string``
面板覆盖、422／724 补丁 kind —— 自有共享表键只有一个 ``<code>_voice_ready``。
不碰 live store / ``assets/`` / ``.cdn`` / 设备 / 存档。

**rework1（2026-09-21，作者原话见 ``rework1/author-request.md`` 第 32 行，施工单
``rework1/impl/rebecca.md``）**：技能里删掉「增加除自身外的队友的技能槽」，换成
「回复生命值低于 40% 的队友最大生命值 35% 的生命值」；词条 3 第 4 条的触发限制由
「限 5 次」改成「CT 15 秒」（c34 → ``(None)``、c35 → 900 帧）。其余 20 行与技能的其他三段不动。

由 ``python mod-tools/wf_midautumn_build.py --char rebecca --step kit`` 调用 :func:`build`。
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    pass  # Imports resolve from this checkout/package, not external source copies.

import wf_client_legality as L  # noqa: E402
import wf_dsl  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_midautumn_specs as MS  # noqa: E402
import wf_seasonal7_common as C  # noqa: E402

KitError = KL.KitError

KEY = "rebecca"
CID, CODE = 169991, "bearish_darkwitch_moon"
ELEMENT = 5                                      # 暗（0 基内部编号，Black）
TEMPLATE_ID, TEMPLATE_CODE = 241006, "bearish_darkwitch_ny20"   # 表/资产母本（★4 风）
LINEAGE_ID, LINEAGE_CODE = 361007, "bearish_darkwitch"          # 血脉母本（★3 暗，取行形状与技能主干）

ABILITY_KEYS = tuple(f"{CID}{slot}" for slot in range(1, 7))
LEADER_ROW_COUNT = 6
ABILITY_RECORD_COUNT = 14

VOICE_KEY = f"{CODE}_voice_ready"
VOICE_ROUTE = {"kind": 0, "threshold": "0.5"}     # 偏离 D6：套件没有 536 行也没有固有状态

TEXTS: dict[str, str] = {}        # 10 个文本键在 design/rebecca.json 的 texts 块里（build 里核验）
SPEC = {
    "required_capabilities": (),                  # 不写 422/724/desc_override ⇒ 不依赖任何客户端补丁
    "extra_keys": {KL.SWITCHED: (VOICE_KEY,)},
}

# ---------------------------------------------------------------- DSL donor 与数值

SPINE_DONOR = f"battle/action/skill/action/rare3/{LINEAGE_CODE}${LINEAGE_CODE}_2"
CNA_DONOR = "battle/action/skill/action/rare5/blackflower_wiz$blackflower_wiz_2"
BUFF_DONOR = "battle/action/skill/action/rare4/herbalist_xm22$herbalist_xm22_2"
# rework1：条件治疗的唯一官方蓝本（3 棵树里唯一一棵把 ConditionalsHealthPointRatioOf 用在治疗上的）
HEAL_DONOR = ("battle/action/skill/action/rare5/psychic_teleport_playable"
              "$psychic_teleport_playable_2")

# 主干 donor 的原值（逐格改之前先断言，donor 漂移当场炸）
SPINE_RADIUS = 200
SPINE_LIFETIME = 300
SPINE_TOLERANCE_FRAMES = 900
SPINE_TOLERANCE_VALUE = {"min": -0.16, "max": -0.2}
SPINE_FROZEN = {"min": 600, "max": 720}
SPINE_SKILL_POINT = {"min": 0.125, "max": 0.15}   # rework1 删掉的那条 AddSkillPoint 的 donor 原值
CNA_DONOR_MULT = {"min": 1.73875, "max": 2}
BUFF_DONOR_PF_FRAMES = 900
BUFF_DONOR_PF_VALUE = {"min": 0.4, "max": 0.5}
BUFF_DONOR_PIERCING = {"min": 570, "max": 660}
HEAL_DONOR_SUBJECT = -17                          # donor 里是「自身」内置主体，移植后换成绑定 id
HEAL_DONOR_RATIO = {"min": 0.2, "max": 0.2}
HEAL_DONOR_WAIT_FRAMES = 300                      # donor 自带的 5 秒延迟包装，本角色去掉（偏离 D13）
HEAL_BASIS = 2                                    # CreateRatioHeal p1：全库 172 例恒为 2 ＝ 按最大生命值
HEAL_HP_THRESHOLD = 40                            # ConditionalsHealthPointRatioOf p1：按百分数整数写
HEAL_HIT_EFFECT = ["GenericHealHitEffect"]        # 官方枚举，零资产依赖

# 两档共用的几何与形状（design/rebecca.json plan.skills.level_tiers.shared）
HIT_RADIUS = 240
HIT_LIFETIME = 240
MIN_HIT_INTERVAL = 20
TOTAL_HITS = 8
TOLERANCE_ELEMENT_SELF = 255      # 继承持有者＝暗
TOLERANCE_ELEMENT_ALL = 254       # 全属性：带抗性旗 boss 的白名单只放行 254（wf-force-apply-and-damage-floors）
HIT_EFFECT = ["Fine"]             # 偏离 D10：AttackHitEffect 官方枚举，零资产依赖

# 主干判定区的绑定 id（CreateHitArea p18/p20/p21 = args[19]/args[21]/args[22]）。
SPINE_HIT_BINDING = 2             # 命中目标绑定，移植进来的 CNA/CreateCondition 的 p0 要指它
SPINE_ALLY_BINDING = 3            # FindAllSubjects(3, 35) ⇒ 除自身外队友（rework1 起装条件治疗）
SPINE_ALLY_SELECTOR = 35          # 面板里的「队友」＝除自身外的队友（偏离 V4）
BUFF_BINDING_SHIFT = 4            # herbalist 块的 0/1/2 → 4/5/6，避开主干已用的 0/1/2/3

# 两档数值：`2` ＝设计稿数值（成品），`1` ＝ ×0.8（比例取自 ★3 母本自己的官方 _1/_2 比，偏离 D9）
SKILL_TIERS = {
    "1": {"cna": {"min": 4.0, "max": 4.0},
          "tolerance_self": {"min": -0.28, "max": -0.28},
          "tolerance_all": {"min": -0.12, "max": -0.12},
          "frozen": 576,
          "heal_ratio": {"min": 0.28, "max": 0.28},
          "pf_frames": 960, "pf_value": {"min": 1.2, "max": 1.2},
          "piercing": 648},
    "2": {"cna": {"min": 5.0, "max": 5.0},
          "tolerance_self": {"min": -0.35, "max": -0.35},
          "tolerance_all": {"min": -0.15, "max": -0.15},
          "frozen": 720,
          "heal_ratio": {"min": 0.35, "max": 0.35},
          "pf_frames": 1200, "pf_value": {"min": 1.5, "max": 1.5},
          "piercing": 810},
}

# 技能主特效：通用共享件，不在任何角色专属目录下 ⇒ 零下载增量、零 code_name 耦合。
SHARED_EFFECT = "battle/effect/skill_general/area/miasma"

FORBIDDEN_LEADER_KINDS = ("422", "724", "713")   # 写进队长表 = C7050（裁决 §2/§8）


# ---------------------------------------------------------------- 设计稿读取

def load_design(root: Path) -> dict[str, Any]:
    design = MS.load_design(Path(root), KEY)
    if not design:
        raise KitError(f"design/{KEY}.json missing (batch {MS.BATCH_DIR})")
    if design.get("schema") != "ma-design/1" or design.get("cid") != CID or design.get("code") != CODE:
        raise KitError(f"design identity drift: {design.get('schema')} {design.get('cid')} {design.get('code')}")
    return design


def _parse_donor(donor: str) -> tuple[str, str, str]:
    """设计稿的 donor 地址 → ``(source, table_letter, "键#记录号(0基)")``。

    本稿两种形状：``"A:1111413:1"`` / ``"L:261083:1"``（官方基线）与 ``"s:A:1599963:3"``
    （live store 只读，已在线的自制角色）。**记录号是 1 基**（``rebecca.md`` 的 ``#L1``/``#L3``
    写法），``kitlib.donor_row`` 要 0 基下标，这里统一减 1。
    """
    parts = str(donor).split(":")
    if len(parts) == 4:
        prefix, table, key, index = parts
        source = {"o": "official", "s": "live"}.get(prefix)
        if source is None:
            raise KitError(f"unrecognised donor source prefix: {donor!r}")
    elif len(parts) == 3:
        table, key, index = parts
        source = "official"
    else:
        raise KitError(f"unexpected donor address shape: {donor!r}")
    if table not in ("A", "L"):
        raise KitError(f"unrecognised donor table letter: {donor!r}")
    index0 = int(index) - 1
    if index0 < 0:
        raise KitError(f"donor record number must be >= 1 (1-based): {donor!r}")
    return source, table, f"{key}#{index0}"


def build_leader_rows(ctx, design: dict[str, Any]) -> tuple[list[list[str]], list[dict[str, Any]]]:
    plan = design["plan"]["leader_ability"]
    if str(plan["key"]) != str(CID) or int(plan["layout"]["ncols"]) != KL.LEADER_NCOLS:
        raise KitError(f"design leader block drift: key={plan.get('key')} layout={plan.get('layout')}")
    rows: list[list[str]] = []
    evidence: list[dict[str, Any]] = []
    for entry in plan["rows"]:
        source, table, donor = _parse_donor(entry["donor"])
        if table != "L":
            raise KitError(f"leader#{entry['index']}: donor {entry['donor']!r} is not a leader_ability row")
        label = f"leader#{entry['index']}({entry.get('label', '')})"
        row, ev = KL.build_row(ctx, "leader_ability", donor, entry["cells"], source=source,
                               element=ELEMENT, expect_describe=entry["desc_expected"], label=label)
        if row[0] != CODE:
            raise KitError(f"{label}: c0 {row[0]!r} != {CODE}")
        rows.append(row)
        evidence.append(ev)
    if len(rows) != LEADER_ROW_COUNT:
        raise KitError(f"design leader_ability carries {len(rows)} rows, expected {LEADER_ROW_COUNT}")
    _ban_forbidden_leader_kinds(rows)
    return rows, evidence


def _ban_forbidden_leader_kinds(rows: list[list[str]]) -> None:
    """队长表禁 422/724/713（裁决 §2/§8）。瞬发内容 kind 在 c45，持续内容 kind 在 c107。"""
    for n, row in enumerate(rows):
        if row[45] in FORBIDDEN_LEADER_KINDS or row[107] in FORBIDDEN_LEADER_KINDS:
            raise KitError(f"leader#{n}: forbidden kind in leader_ability "
                           f"(c45={row[45]!r} c107={row[107]!r}) —— 写进队长表 = C7050")


def build_ability_rows(ctx, design: dict[str, Any]) -> tuple[dict[str, list[list[str]]], list[dict[str, Any]]]:
    plan = design["plan"]["ability"]
    if int(plan["layout"]["ncols"]) != KL.ABILITY_NCOLS:
        raise KitError(f"design ability ncols drift: {plan['layout'].get('ncols')}")
    if tuple(sorted(plan["keys"])) != tuple(sorted(ABILITY_KEYS)):
        raise KitError(f"design ability keys drift: {sorted(plan['keys'])}")
    rows_by_key: dict[str, list[list[str]]] = {}
    evidence: list[dict[str, Any]] = []
    for slot, key_name in enumerate(ABILITY_KEYS, start=1):
        block = plan["keys"][key_name]
        if int(block["slot"]) != slot:
            raise KitError(f"ability {key_name}: slot {block['slot']} != {slot}")
        rows: list[list[str]] = []
        for entry in block["records"]:
            source, table, donor = _parse_donor(entry["donor"])
            if table != "A":
                raise KitError(f"{key_name}#{entry['index']}: donor {entry['donor']!r} is not an ability row")
            label = f"{key_name}#{entry['index']}"
            row, ev = KL.build_row(ctx, "ability", donor, entry["cells"], source=source,
                                   element=ELEMENT, expect_describe=entry["desc_expected"], label=label)
            rows.append(row)
            evidence.append(ev)
        KL.check_ability_key(rows, key_name, CODE, slot)
        if rows[0][1] != block["unisonable_c1"] or rows[0][2] != block["statue_group_c2"]:
            raise KitError(f"ability {key_name}: c1/c2 {rows[0][1]}/{rows[0][2]} != design "
                           f"{block['unisonable_c1']}/{block['statue_group_c2']}")
        rows_by_key[key_name] = rows
    if sum(len(v) for v in rows_by_key.values()) != ABILITY_RECORD_COUNT:
        raise KitError(f"design ability carries {sum(len(v) for v in rows_by_key.values())} records, "
                       f"expected {ABILITY_RECORD_COUNT}")
    return rows_by_key, evidence


# ---------------------------------------------------------------- action_skill 两档

def write_action_skill(ctx, design: dict[str, Any]) -> dict[str, list[str]]:
    """整行改用血脉母本 361007 的行形状，只覆盖 c0/c1（TEXTS）、c4/c5（能量）、c7（程序路径）。

    包里现有的两行来自表母本 241006（``dynamic/skill/fever`` 抽签演出），与「在自身周围施放
    影魔法」的技能形态不符；设计稿 ``plan.skills.action_skill_row`` 指定沿用 361007 的整行。
    """
    spec = ctx.spec
    plan = design["plan"]["skills"]
    energy = plan["energy"]
    want = plan["action_skill_row"]
    lineage = _official_action_rows(ctx, LINEAGE_CODE)
    if set(lineage) != {"1", "2"}:
        raise KitError(f"official action_skill[{LINEAGE_CODE}] inner keys {sorted(lineage)}")
    pkg = ctx.pkg_nested(CODE)
    if set(pkg) != {"1", "2"}:
        raise KitError(f"package action_skill inner keys {sorted(pkg)} (rerun --step tables)")

    out: dict[str, list[str]] = {}
    for level in ("1", "2"):
        cells = list(lineage[level])
        if len(cells) != len(pkg[level]):
            raise KitError(f"action_skill {level}: lineage row has {len(cells)} columns, "
                           f"package row has {len(pkg[level])}")
        cells[0] = spec.texts[f"skill{level}"]
        cells[1] = spec.texts[f"desc{level}"]
        cells[4], cells[5] = str(energy[level][0]), str(energy[level][1])
        cells[7] = ctx.program_path(level)
        if cells[2] != want["c2_motion"]:
            raise KitError(f"action_skill {level}: motion {cells[2]!r} != design {want['c2_motion']!r}")
        for col in ("c3", "c6", "c8", "c9", "c10", "c12", "c13", "c16"):
            if cells[int(col[1:])] != want[col]:
                raise KitError(f"action_skill {level}: {col}={cells[int(col[1:])]!r} != design {want[col]!r}")
        if not cells[0] or not cells[1]:
            raise KitError(f"action_skill {level}: name/desc empty (rerun --step tables)")
        out[level] = cells
    ctx.write_nested(KL.ACTION, CODE, {lv: [cells] for lv, cells in out.items()}, replace_inner=True)
    return out


def _official_action_rows(ctx, code: str) -> dict[str, list[str]]:
    """官方基线 ``action_skill`` 某 code 的内层行（嵌套表，``official_flat`` 解不了）。"""
    logical = C.core.ACTION_SKILL_LOGICAL
    raw = ctx.official_read(logical, "common")
    if raw is None:
        raise KitError(f"official baseline lacks {logical}")
    table = C.core.load_nested_table_bytes(raw, logical)
    if code not in table.rows:
        raise KitError(f"official action_skill lacks {code}")
    return {k: C.csv_split(v)[0] for k, v in table.rows[code].text_rows().items()}


# ---------------------------------------------------------------- DSL 工具

def _only(tree, name: str, *, where: str):
    hits = list(wf_dsl.iter_dsl_commands(tree, name))
    if len(hits) != 1:
        raise KitError(f"{where}: expected exactly 1 {name}, got {len(hits)}")
    return hits[0]


def _dsl_events(node, name: str) -> list[list]:
    """``["Event", [名称, …]]`` 节点（``wf_dsl`` 只提供 Command 迭代器，Event 要自己走）。"""
    out: list[list] = []
    if isinstance(node, list):
        if node and node[0] == "Event" and len(node) > 1 and isinstance(node[1], list) \
                and node[1] and node[1][0] == name:
            out.append(node[1])
        for child in node:
            out.extend(_dsl_events(child, name))
    return out


def _ac_entries(tree, kind: str) -> list[list]:
    """所有携带该 AdditionalCondition kind 的 ``CreateCondition`` 的 AC 条目。"""
    return [c[2][0] for c in wf_dsl.iter_dsl_commands(tree, "CreateCondition")
            if c[2] and isinstance(c[2][0], list) and c[2][0][0] == kind]


def _cc_commands(tree, kind: str) -> list[list]:
    """所有携带该 AC kind 的 ``CreateCondition`` 命令本体（要改 forceApply/付与种类时用）。"""
    return [c for c in wf_dsl.iter_dsl_commands(tree, "CreateCondition")
            if c[2] and isinstance(c[2][0], list) and c[2][0][0] == kind]


def _dsl_problems(tree, *, element: int | None = None) -> list[str]:
    problems: list[str] = []
    problems += [f"direction: {p}" for p in wf_dsl.player_side_dsl_problems(tree)]
    problems += [f"subject: {p}" for p in L.action_dsl_subject_binding_problems(tree)]
    problems += [f"hit_target: {p}" for p in L.action_dsl_hit_area_target_problems(tree)]
    if element is not None:
        problems += [f"element: {p}" for p in L.action_dsl_element_problems(tree, element)]
    return problems


def _write_dsl_checked(ctx, program: str, tree) -> str:
    """``write_dsl`` 只吃裸树；写后解包回读比对（记忆卡 wf-dsl-encode-wrapper-trap）。"""
    if not (isinstance(tree, list) and tree and tree[0] == "ActionDsl"):
        raise KitError(f"write_dsl needs a bare ActionDsl tree, got {type(tree).__name__}")
    logical = ctx.write_dsl(program, tree)
    back = ctx.amf_parse(ctx.pack.pkg_path("common", logical).read_bytes())
    if back != tree:
        raise KitError(f"DSL readback mismatch: {logical}")
    return logical


def _remap_binding(node, shift: int) -> None:
    """把移植块里的绑定 id 与 lookup 位整体平移 ``shift``（记忆卡 wf-dsl-subject-lookup-map）。

    本块用到的位：``FindAllSubjects p0``（绑定）＝ ``args[1]``、``CreateCondition p0``（lookup）
    ＝ ``args[1]``、``DeleteCondition p0``（lookup）＝ ``args[1]``。块内没有 CreateHitArea /
    CreateReferencePoint / 坐标系 ``["GH", n]``，所以没有别的 lookup 位要动。
    """
    if isinstance(node, list):
        if node and node[0] == "Command" and isinstance(node[1], list) and node[1]:
            args = node[1]
            if args[0] in ("FindAllSubjects", "CreateCondition", "DeleteCondition"):
                if not isinstance(args[1], int):
                    raise KitError(f"{args[0]}: subject slot is not an int: {args[1]!r}")
                args[1] += shift
            elif args[0] in ("CreateHitArea", "CreateReferencePoint", "FindNearSubjects",
                             "CreateNormalAttack", "ShowEffect", "AddSkillPoint", "StopBall",
                             "CreateRatioHeal", "ConditionalsHealthPointRatioOf"):
                raise KitError(f"{args[0]} inside the transplanted buff block needs its own "
                               f"lookup remap (wf-dsl-subject-lookup-map); refusing to guess")
        for child in node:
            _remap_binding(child, shift)


def build_skill_tree(ctx, level: str) -> tuple[Any, dict[str, Any]]:
    """从三棵官方 donor 树装出一档技能树（主干改参数 ＋ 两处整块移植）。"""
    tier = SKILL_TIERS[level]
    tree = copy.deepcopy(ctx.template_dsl(SPINE_DONOR))
    if tree[0] != "ActionDsl" or tree[10] != 0:
        raise KitError(f"skill {level} spine head drift: {tree[:2]} bta={tree[10]}")

    # ---- 1) 判定区：半径/寿命 + 节流三格（三格形状整块取自 CNA donor 的判定区）
    area = _only(tree, "CreateHitArea", where=f"skill {level} spine")
    if area[9] != ["Circle", [{"min": SPINE_RADIUS, "max": SPINE_RADIUS}]]:
        raise KitError(f"skill {level} spine hit-area shape drift: {area[9]}")
    if area[13] != ["SpecifyHitAreaLifetimeDirectly", SPINE_LIFETIME]:
        raise KitError(f"skill {level} spine hit-area lifetime drift: {area[13]}")
    if area[14] != ["CalculatedUsingMaxNumOfHits", 1] or area[15] != ["None"]:
        raise KitError(f"skill {level} spine hit-area throttle drift: {area[14]} {area[15]}")
    if area[22] != SPINE_HIT_BINDING:
        raise KitError(f"skill {level} spine hit-area target binding drift: {area[22]}")

    cna_donor_tree = ctx.template_dsl(CNA_DONOR)
    donor_area = next((a for a in wf_dsl.iter_dsl_commands(cna_donor_tree, "CreateHitArea")
                       if a[14][0] == "SpecifyMinHitIntervalDirectly"
                       and a[15] == ["Some", [{"min": TOTAL_HITS, "max": TOTAL_HITS}]]), None)
    if donor_area is None:
        raise KitError("CNA donor lacks the throttled multi-hit CreateHitArea")
    if donor_area[14] != ["SpecifyMinHitIntervalDirectly", MIN_HIT_INTERVAL]:
        raise KitError(f"CNA donor interval drift: {donor_area[14]}")

    area[9] = ["Circle", [{"min": HIT_RADIUS, "max": HIT_RADIUS}]]
    area[13] = ["SpecifyHitAreaLifetimeDirectly", HIT_LIFETIME]
    area[14] = copy.deepcopy(donor_area[14])
    area[15] = copy.deepcopy(donor_area[15])

    # ---- 2) 移植 CreateNormalAttack 进主干判定区的命中 Block（排在两条 CreateCondition 之前）
    donor_cna = _only(donor_area[23], "CreateNormalAttack", where="CNA donor hit block")
    if donor_cna[6] != [CNA_DONOR_MULT]:
        raise KitError(f"CNA donor multiplier drift: {donor_cna[6]}")
    if donor_cna[2] != 255:
        raise KitError(f"CNA donor element drift: {donor_cna[2]} (255 = 继承持有者，不可写 5/6)")
    cna = copy.deepcopy(donor_cna)
    cna[1] = SPINE_HIT_BINDING                    # p0：指主干判定区的命中目标绑定
    cna[6] = [dict(tier["cna"])]
    cna[15] = list(HIT_EFFECT)                    # 偏离 D10：官方枚举，不引用 blackflower_wiz 专属目录
    hit_block = area[23]
    if not (isinstance(hit_block, list) and hit_block and hit_block[0] == "Block"):
        raise KitError(f"skill {level} spine hit block shape drift: {type(hit_block)}")
    hit_block[1].insert(0, ["Command", cna])

    # ---- 3) 抗性↓两条：主干那条改值并开强制付与，再整块克隆一份改成元素码 254
    tol_cmds = _cc_commands(tree, "ACToleranceOfElement")
    if len(tol_cmds) != 1:
        raise KitError(f"skill {level}: expected 1 ACToleranceOfElement in the spine, got {len(tol_cmds)}")
    tol = tol_cmds[0]
    ac = tol[2][0]
    if ac[1] != [{"min": SPINE_TOLERANCE_FRAMES, "max": SPINE_TOLERANCE_FRAMES}]:
        raise KitError(f"skill {level} tolerance frames drift: {ac[1]}")
    if ac[2] != TOLERANCE_ELEMENT_SELF or ac[3] != [SPINE_TOLERANCE_VALUE]:
        raise KitError(f"skill {level} tolerance donor drift: element={ac[2]} value={ac[3]}")
    if tol[12] is not False:
        raise KitError(f"skill {level} tolerance forceApply donor drift: {tol[12]}")
    ac[3] = [dict(tier["tolerance_self"])]
    tol[12] = True                                # CreateCondition 第 12 位 = forceApply（无视弱体耐性）
    tol_all = copy.deepcopy(tol)
    tol_all[2][0][2] = TOLERANCE_ELEMENT_ALL
    tol_all[2][0][3] = [dict(tier["tolerance_all"])]
    index = hit_block[1].index(["Command", tol])
    hit_block[1].insert(index + 1, ["Command", tol_all])

    # ---- 4) 迟缓：时长拉平，forceApply 保持 false（boss 对冻结本来就常抵抗，强开越界）
    frozen_cmds = _cc_commands(tree, "ACFrozen")
    if len(frozen_cmds) != 1:
        raise KitError(f"skill {level}: expected 1 ACFrozen, got {len(frozen_cmds)}")
    frozen = frozen_cmds[0]
    if frozen[2][0][1] != [SPINE_FROZEN]:
        raise KitError(f"skill {level} frozen donor drift: {frozen[2][0][1]}")
    frozen[2][0][1] = [{"min": tier["frozen"], "max": tier["frozen"]}]
    if frozen[12] is not False:
        raise KitError(f"skill {level} frozen forceApply must stay false, got {frozen[12]}")

    # ---- 5) rework1：队友块整块换成条件治疗（选择器 35 ＝ 除自身外队友，不动）
    #         作者原话「不要增加队友技能槽的效果」⇒ donor 自带的 AddSkillPoint 整条删掉。
    ally = next((f for f in wf_dsl.iter_dsl_commands(tree, "FindAllSubjects")
                 if f[1] == SPINE_ALLY_BINDING and f[2] == SPINE_ALLY_SELECTOR), None)
    if ally is None:
        raise KitError(f"skill {level}: spine FindAllSubjects({SPINE_ALLY_BINDING}, "
                       f"{SPINE_ALLY_SELECTOR}) not found")
    add = _only(ally[9], "AddSkillPoint", where=f"skill {level} ally block")
    if add[1] != SPINE_ALLY_BINDING or add[2] != [SPINE_SKILL_POINT]:
        raise KitError(f"skill {level} AddSkillPoint donor drift: lookup={add[1]} value={add[2]}")
    if ally[9] != ["Block", [["Command", add]]]:
        raise KitError(f"skill {level}: spine ally block carries more than the AddSkillPoint "
                       f"that rework1 removes —— refusing to drop anything else")
    ally[9] = ["Block", [["Command", _build_heal_block(ctx, tier)]]]
    if list(wf_dsl.iter_dsl_commands(tree, "AddSkillPoint")):
        raise KitError(f"skill {level}: AddSkillPoint survived the rework1 removal")

    # ---- 6) 移植全队增益块（荷莉·圣诞）：绑定 id 0/1/2 统一 +4，避开主干已用的 0/1/2/3
    buff = _build_buff_block(ctx, tier)
    tree[11][1].append(["Command", buff])

    # ---- 7) 门禁 + 特效来源核对
    _assert_effects_are_shared(tree, level)
    problems = _dsl_problems(tree, element=ELEMENT)
    if problems:
        raise KitError(f"skill {level} DSL gates failed: {problems}")
    gates = {
        "level": level, "cna": dict(tier["cna"]),
        "cna_total": round(tier["cna"]["max"] * TOTAL_HITS, 3),
        "hits": TOTAL_HITS, "min_hit_interval": MIN_HIT_INTERVAL,
        "radius": HIT_RADIUS, "lifetime": HIT_LIFETIME,
        "tolerance": [{"element": TOLERANCE_ELEMENT_SELF, "value": dict(tier["tolerance_self"]),
                       "force_apply": True},
                      {"element": TOLERANCE_ELEMENT_ALL, "value": dict(tier["tolerance_all"]),
                       "force_apply": True}],
        "frozen_frames": tier["frozen"], "frozen_force_apply": False,
        "heal": {"selector": SPINE_ALLY_SELECTOR, "binding": SPINE_ALLY_BINDING,
                 "hp_threshold_pct": HEAL_HP_THRESHOLD, "basis": HEAL_BASIS,
                 "ratio": dict(tier["heal_ratio"]), "branch": "else (HP < threshold)",
                 "hit_effect": list(HEAL_HIT_EFFECT), "wait_frames": 0},
        "add_skill_point": None,                  # rework1：作者要求删除，树里必须一条都不剩
        "pf_damage": {"frames": tier["pf_frames"], "value": dict(tier["pf_value"])},
        "piercing_frames": tier["piercing"],
        "bta_tree10": tree[10],
        "buff_binding_shift": BUFF_BINDING_SHIFT,
    }
    return tree, gates


def _build_heal_block(ctx, tier: dict[str, Any]) -> list:
    """``psychic_teleport_playable_2`` 的条件治疗整块，改 subject／比例并去掉 ``Wait`` 包装。

    形状 ``ConditionalsHealthPointRatioOf(subject, 40, then=["Block",[]], else=["Block",[heal]])``：
    **else 分支 ＝ HP 低于阈值**（判据：同一角色的词条行 ``1611831#0`` 面板写「HP≤…≥40% 时 →
    比例治疗 20%(延迟5秒)」，与这棵树的 40／0.2／300 帧三项逐一对得上）。空分支写
    ``["Block", []]``，不写 ``["DoNothing"]``（记忆卡 wf-dsl-donothing-enum-trap：那是
    ``IfTargetNotFound`` 的枚举，塞进表达式位 ⇒ 进游戏 F1009，往返自检抓不到）。
    """
    donor_tree = ctx.template_dsl(HEAL_DONOR)
    donor = _only(donor_tree, "ConditionalsHealthPointRatioOf", where="heal donor")
    if donor[1] != HEAL_DONOR_SUBJECT or donor[2] != HEAL_HP_THRESHOLD:
        raise KitError(f"heal donor gate drift: subject={donor[1]} threshold={donor[2]}")
    if donor[3] != ["Block", []]:
        raise KitError(f"heal donor then-branch drift: {donor[3]} —— 期望空分支 ['Block', []]")

    heal_donor = _only(donor[4], "CreateRatioHeal", where="heal donor else-branch")
    waits = _dsl_events(donor[4], "Wait")
    if len(waits) != 1 or waits[0][1] != HEAL_DONOR_WAIT_FRAMES:
        raise KitError(f"heal donor Wait drift: {[w[1:2] for w in waits]} "
                       f"（期望恰好一层 Wait {HEAL_DONOR_WAIT_FRAMES}；本角色把它去掉，偏离 D13）")
    if heal_donor[1] != HEAL_DONOR_SUBJECT or heal_donor[2] != HEAL_BASIS:
        raise KitError(f"heal donor drift: subject={heal_donor[1]} basis={heal_donor[2]}")
    if heal_donor[3] != [HEAL_DONOR_RATIO]:
        raise KitError(f"heal donor ratio drift: {heal_donor[3]}")
    if heal_donor[6] != HEAL_HIT_EFFECT:
        raise KitError(f"heal donor HealHitEffect drift: {heal_donor[6]} != {HEAL_HIT_EFFECT}")

    heal = copy.deepcopy(heal_donor)
    heal[1] = SPINE_ALLY_BINDING                  # lookup 位：所在 FindAllSubjects 的绑定 id
    heal[3] = [dict(tier["heal_ratio"])]
    # 偏离 D13：去掉 donor 的 Event Wait 300（那 5 秒是 teleport 自己的设计，面板没写就不能留）
    block = ["ConditionalsHealthPointRatioOf", SPINE_ALLY_BINDING, HEAL_HP_THRESHOLD,
             ["Block", []], ["Block", [["Command", heal]]]]
    if list(wf_dsl.iter_dsl_commands(block, "CreateRatioHeal"))[0][1] != SPINE_ALLY_BINDING:
        raise KitError("heal block lookup remap failed")
    return block


def _build_buff_block(ctx, tier: dict[str, Any]) -> list:
    """荷莉·圣诞 ``herbalist_xm22_2`` 的 ``FindAllSubjects(0, 97)`` 整块，改值并重映射绑定 id。"""
    donor_tree = ctx.template_dsl(BUFF_DONOR)
    donor = next((f for f in wf_dsl.iter_dsl_commands(donor_tree, "FindAllSubjects")
                  if f[1] == 0 and f[2] == 97), None)
    if donor is None:
        raise KitError("buff donor lacks FindAllSubjects(0, 97)")
    block = copy.deepcopy(donor)

    pf_cmds = _cc_commands(block, "ACPowerFlipDamage")
    pierce_cmds = _cc_commands(block, "ACPiercing")
    if len(pf_cmds) != 1 or len(pierce_cmds) != 1:
        raise KitError(f"buff donor drift: ACPowerFlipDamage×{len(pf_cmds)} ACPiercing×{len(pierce_cmds)}")
    pf, pierce = pf_cmds[0], pierce_cmds[0]
    if pf[2][0][1] != [{"min": BUFF_DONOR_PF_FRAMES, "max": BUFF_DONOR_PF_FRAMES}] \
            or pf[2][0][2] != [BUFF_DONOR_PF_VALUE]:
        raise KitError(f"buff donor ACPowerFlipDamage drift: {pf[2][0][1]} {pf[2][0][2]}")
    if pierce[2][0][1] != [BUFF_DONOR_PIERCING]:
        raise KitError(f"buff donor ACPiercing drift: {pierce[2][0][1]}")
    for cmd, what in ((pf, "ACPowerFlipDamage"), (pierce, "ACPiercing")):
        if cmd[10] != 2:
            raise KitError(f"buff donor {what}: 付与对象种类 {cmd[10]} != 2（配选择器 97，"
                           f"错配 = 施法 C16102，记忆卡 wf-createcondition-target-kind）")
    pf[2][0][1] = [{"min": tier["pf_frames"], "max": tier["pf_frames"]}]
    pf[2][0][2] = [dict(tier["pf_value"])]
    pierce[2][0][1] = [{"min": tier["piercing"], "max": tier["piercing"]}]

    deletes = list(wf_dsl.iter_dsl_commands(block, "DeleteCondition"))
    if len(deletes) != 2 or any(d[2] != ["DCAll", 3] for d in deletes):
        raise KitError(f"buff donor DeleteCondition drift: {[d[2] for d in deletes]}")

    _remap_binding(["Block", [["Command", block]]], BUFF_BINDING_SHIFT)
    if block[1] != BUFF_BINDING_SHIFT:
        raise KitError(f"buff block outer binding remap failed: {block[1]}")
    return block


def _assert_effects_are_shared(tree, level: str) -> None:
    """技能树里的特效引用必须全是官方通用共享件（裁决 §4：零图集增量、零 code_name 耦合）。"""
    for show in wf_dsl.iter_dsl_commands(tree, "ShowEffect"):
        spec = show[2]
        path = spec[1] if isinstance(spec, list) and len(spec) > 1 and isinstance(spec[1], str) else None
        if path != SHARED_EFFECT:
            raise KitError(f"skill {level}: ShowEffect references {path!r}, expected the shared "
                           f"{SHARED_EFFECT!r}（角色专属目录不在队伍里就不预载 ⇒ 数据不足/C8003）")
    for cna in wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack"):
        if isinstance(cna[15], list) and cna[15] and cna[15][0] == "SpecifyHitEffectDirectly":
            raise KitError(f"skill {level}: CreateNormalAttack still carries a donor-specific hit effect")
    for heal in wf_dsl.iter_dsl_commands(tree, "CreateRatioHeal"):
        if heal[6] != HEAL_HIT_EFFECT:
            raise KitError(f"skill {level}: CreateRatioHeal HealHitEffect {heal[6]!r} != "
                           f"{HEAL_HIT_EFFECT}（SpecifyHealEffectDirectly 会引用别人的专属目录）")


# ---------------------------------------------------------------- 入口

def build(ctx) -> dict[str, Any]:
    spec = ctx.spec
    if (spec.cid, spec.code, spec.element) != (CID, CODE, ELEMENT):
        raise KitError(f"identity drift: {spec.cid}/{spec.code}/element {spec.element}")
    if (spec.template_id, spec.template_code) != (TEMPLATE_ID, TEMPLATE_CODE):
        raise KitError(f"template drift: {spec.template_id}/{spec.template_code}")
    if spec.pf_type != 3 or spec.stance != "Supporter":
        raise KitError(f"spec drift: pf_type={spec.pf_type} stance={spec.stance}")
    if MS.text_placeholders(spec):
        raise KitError(f"design texts still placeholders: {MS.text_placeholders(spec)}")

    design = load_design(ctx.root)
    if design["plan"]["unique_conditions"]["add"]:
        raise KitError("design now asks for unique_condition rows, but SPEC declares none "
                       "(固有状态 ID 必须 8 位并写进 SPEC['extra_keys'])")

    # ---- 1) 队长技 6 行（design.json 驱动）
    leader_rows, leader_evidence = build_leader_rows(ctx, design)
    capabilities: set[str] = set()
    for ev in leader_evidence:
        capabilities.update(ev["capabilities"])
    ctx.write_flat(KL.LEADER, {str(CID): leader_rows})

    # ---- 2) 词条 6 键 14 条记录（design.json 驱动）
    ability_rows, ability_evidence = build_ability_rows(ctx, design)
    for ev in ability_evidence:
        capabilities.update(ev["capabilities"])
    ctx.write_flat(KL.ABILITY, ability_rows)

    # ---- 3) action_skill 两档（行形状换成血脉母本 361007，只覆盖 5 格）
    action_rows = write_action_skill(ctx, design)

    # ---- 4) 技能 DSL 两档
    programs: list[str] = []
    skill_gates: dict[str, Any] = {}
    for level in ("1", "2"):
        tree, gates = build_skill_tree(ctx, level)
        programs.append(_write_dsl_checked(ctx, ctx.program_path(level), tree))
        skill_gates[level] = gates

    # ---- 5) 语音路由（kind 0 HpHigh 0.5）+ character 行
    route = KL.voice_route(CODE, VOICE_ROUTE)
    design_route = design["voice"]["route"]
    if int(design_route["kind"]) != VOICE_ROUTE["kind"] \
            or str(design_route.get("threshold")) != VOICE_ROUTE["threshold"]:
        raise KitError(f"design voice route drift: {design_route}")
    char_row = ctx.pack.pkg_character_row()
    char_row[9:17] = route
    if char_row[6] != "3" or char_row[26] != "Supporter" or char_row[27] != str(CID):
        raise KitError(f"character row drift: c6={char_row[6]} c26={char_row[26]} c27={char_row[27]}")
    ctx.write_flat(KL.CHARACTER, {str(CID): [char_row]})
    voice_ready = KL.write_voice_ready(ctx)

    # ---- 6) 像素成品（缺文件静默跳过）+ 三层镜像
    lut_path = KL.pixel_dir(ctx) / "fx_lut.json"
    lut = KL.png_transform_from_lut(lut_path)     # 本角色零特效克隆 ⇒ 只作记录，不参与装配
    pixel = KL.install_staged_assets(ctx)
    mirrors = ctx.sync_character_mirrors()
    if mirrors["character"][9:17] != route:
        raise KitError("character mirror lost the voice route")

    # 面板：本角色不写 desc_override，词条 6 键 14 条按 wf_describe 原文逐条显示。
    panel = [ev["describe"] for ev in ability_evidence]

    ctx.evidence_write("kit-gates.json", {
        "leader": {"rows": leader_rows, "evidence": leader_evidence},
        "ability": {"rows": ability_rows, "evidence": ability_evidence},
        "skills": skill_gates, "action_skill": action_rows,
        "effects": {"policy": "reference-only", "shared": [SHARED_EFFECT], "cloned": []},
        "fx_lut": {"path": str(lut_path), "present": bool(lut), "applied": False},
        "voice_route": route, "voice_ready": voice_ready,
        "pixel": pixel, "mirrors": mirrors,
        "leader_panel": [ev["describe"] for ev in leader_evidence],
    })

    notes = [
        f"技能两档：主干＝她 ★3 自己的 {LINEAGE_CODE}_2 只改参数；从 blackflower_wiz_2 整块移植"
        f"判定区节流三格（interval {MIN_HIT_INTERVAL} / 总段数 {TOTAL_HITS}）与 CreateNormalAttack；"
        f"强化档 {TOTAL_HITS} 段 × {SKILL_TIERS['2']['cna']['max']} = "
        f"{TOTAL_HITS * SKILL_TIERS['2']['cna']['max']:g}×（裁决 §2 带 36–50 ✓），"
        f"未强化档 {TOTAL_HITS} 段 × {SKILL_TIERS['1']['cna']['max']} = "
        f"{TOTAL_HITS * SKILL_TIERS['1']['cna']['max']:g}×（偏离 D9）；"
        "根头 tree[10]=0 保持（技能伤害归属，donor 原值不动，不写 3）",
        f"抗性↓两条：元素码 {TOLERANCE_ELEMENT_SELF}（继承＝暗）"
        f"{SKILL_TIERS['2']['tolerance_self']['max']:+g} 与元素码 {TOLERANCE_ELEMENT_ALL}（全属性）"
        f"{SKILL_TIERS['2']['tolerance_all']['max']:+g}，两条都开 forceApply（无视弱体耐性）；"
        "254 那条是带抗性旗 boss（官方 484 只里 85 只）上的保底——单元素码在那类 boss 上被静默硬拒。"
        "迟缓 ACFrozen 的 forceApply 保持 false（不越界）",
        f"全队增益块：herbalist_xm22_2（荷莉·圣诞）的 FindAllSubjects(97) 整块移植，绑定 id "
        f"0/1/2 → {BUFF_BINDING_SHIFT}/{BUFF_BINDING_SHIFT + 1}/{BUFF_BINDING_SHIFT + 2}"
        "（避开主干已用的 0/1/2/3；CreateCondition/DeleteCondition 的 lookup 位同步平移）；"
        f"强化档 PF 伤害 {SKILL_TIERS['2']['pf_frames']} 帧 +150%、贯通 {SKILL_TIERS['2']['piercing']} 帧"
        f"（{SKILL_TIERS['2']['piercing'] / 60:g} 秒）；付与对象种类保持 2（配选择器 97）",
        f"rework1（作者 09-21）：主干自带的 FindAllSubjects({SPINE_ALLY_BINDING}, "
        f"{SPINE_ALLY_SELECTOR}) 块里那条 AddSkillPoint（「增加除自身外的队友的技能槽」）整条删除，"
        f"换成 psychic_teleport_playable_2 移植来的条件治疗："
        f"ConditionalsHealthPointRatioOf(绑定 {SPINE_ALLY_BINDING}, {HEAL_HP_THRESHOLD}) 的 "
        f"else 分支（＝HP 低于 {HEAL_HP_THRESHOLD}%）里 CreateRatioHeal 基准 {HEAL_BASIS}"
        f"（按最大生命值）强化档 {SKILL_TIERS['2']['heal_ratio']['max']:.0%}／未觉醒档 "
        f"{SKILL_TIERS['1']['heal_ratio']['max']:.0%}；donor 自带的 Event Wait "
        f"{HEAL_DONOR_WAIT_FRAMES} 帧延迟去掉（偏离 D13），HealHitEffect 用官方枚举 "
        f"{HEAL_HIT_EFFECT}（零资产依赖）。面板的「队友」＝选择器 {SPINE_ALLY_SELECTOR} 除自身外队友",
        "rework1（作者 09-21）：词条 3 第 4 条的触发限制由「限 5 次」（c34=5）改成「CT 15 秒」"
        "（c34=(None)、c35=900 帧）——官方触发 kind 23 配 c35=900 有 3 条先例，且 14 条"
        "「kind 23 带冷却」的官方行 c34 全是 (None)（限次与冷却不同时写）",
        f"特效零克隆：技能主特效沿用主干自带的 {SHARED_EFFECT}（skill_general 通用共享件，"
        "不在任何角色专属目录下 ⇒ 零下载增量、零 code_name 耦合）；移植进来的 CNA 把 donor 的 "
        f"SpecifyHitEffectDirectly 换成官方枚举 {HIT_EFFECT}（偏离 D10）",
        f"action_skill 两档整行换成血脉母本 {LINEAGE_ID} {LINEAGE_CODE} 的行形状"
        f"（动作预设 {design['plan']['skills']['action_skill_row']['c2_motion']}），"
        "只覆盖 c0/c1（TEXTS）、c4/c5（能量 500/500 与 500/450）、c7（程序路径）",
        "自有共享表键只有一个 <code>_voice_ready；不做 722、不做固有状态、不写 "
        "custom_ability_string/desc_override，required_capabilities 为空",
        {"pixel_install": pixel},
    ]
    deviations = []
    for entry in design.get("deviations", ()):
        deviations.append({"id": entry.get("id"),
                           "want": entry.get("planned") or entry.get("原设想") or entry.get("want"),
                           "got": entry.get("actual") or entry.get("实际落法") or entry.get("got"),
                           "why": entry.get("reason") or entry.get("原因") or entry.get("why")})

    gate = {"rows": len(leader_evidence) + len(ability_evidence), "programs": len(programs),
            "pixel_present": pixel["present"], "pixel_missing": [e["logical"] for e in pixel["skipped"]]}
    ready = pixel["present"] and not pixel["skipped"]
    gate["reason"] = "kit 自有产物全部过闸" if ready else \
        f"像素成品未就绪：{gate['pixel_missing'] or f'B/pixel/{KEY}/install.json 不存在'}"

    return KL.report(
        ctx, summary="蕾贝卡：暗属性强化弹射节奏辅助（−c ＋ 追加连击 ＋ PF 伤害；技能给全队贯通与双抗性↓）",
        status=KL.READY if ready else KL.DRAFT, panel=panel, notes=notes, programs=programs,
        required_capabilities=sorted(capabilities | set(SPEC["required_capabilities"])),
        deviations=deviations,
        extra={"custom_ability_string": [], "effect_families": [], "unique_condition": {},
               "kit_gate": gate, "voice_route": route,
               "skill_multipliers": {lv: TOTAL_HITS * SKILL_TIERS[lv]["cna"]["max"] for lv in ("1", "2")}})
