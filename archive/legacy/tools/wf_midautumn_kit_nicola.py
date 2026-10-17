# -*- coding: utf-8 -*-
"""中秋批次 kit：妮可拉·中秋 119991 ``sorceress_teacher_moon``（火属性技伤辅助）。

定位「月相夜课」：开局自补技能槽 85%（能力1 #0 + 能力5 #1），靠「自身技能槽充满」（触发 24）
点亮满月轴，把全队火属性角色的技能伤害／攻击力往上堆；技能『月相夜讲』分新月·上弦·满月
三相打满屏，末段挂敌方攻击力降低 + 火属性抗性降低 + 驱散 1 个强化，并给全体火属性角色
挂技能伤害提升。设计与数值以
``work/character_packs/midautumn-20260920/design/nicola.{md,json}`` 为准 —— 本模块是
「设计 JSON 驱动」的薄壳：队长 6 行、词条 6 键 13 条的 donor／逐格改／预期 ``wf_describe``
全部从 ``design/nicola.json`` 的 ``plan`` 块读出后交给 :func:`wf_midautumn_kitlib.build_row`
装配，两边漂移（donor 缺失、legality 不过、``wf_describe`` 对不上、与设计稿登记的 ``row_final``
逐格不等）当场报错，不在本文件里手抄 19 行的具体数值。

本模块自己负责的是设计 JSON 管不到的部分：
    - ``custom_ability_string``：536「切换技能形态」的 c70 字符串键（未注册 = C8601）
      与 rework1 的 ``desc_override_<code>_3``（能力 3 整槽面板覆盖，键名 = ``desc_override_``
      ＋ 该槽第 0 行的 ``string_id``；需要 V14 APK 的 ``panel-description-override-v2``，
      缺补丁不崩、只是回落到客户端自动文案）——能力 3 整键 c1（主位限制）＝``"false"``，
      覆盖串每行必须自带 :data:`MAIN_ICON` 前缀才会显示主位限制图标（09-21 真机反馈：
      4 行都没带这段前缀，看不到 Ⓜ；格式照抄玛格诺斯 ``desc_override_lion_swordman_moon_3``
      的实际写法，不许用字面「Ⓜ」字符）；
    - rework1 的固有状态「月讲」（8 位 ID ``cid*100+1``）与它的 48×48 图标（程序绘制，
      alpha 逐格取官方 frame donor）；
    - ``action_skill`` 两档能量 500/500、500/450（名称/描述由 ``tables`` 写 TEXTS）；
    - 技能 DSL 两档：设计稿的 ``composed_tree`` 逐命令回到官方 donor 树上核对
      （:data:`SHAPE_DONORS` 五棵官方树 + :data:`ALLOWED_CELL_DIFFS` 白名单），写后回读；
    - 技能特效：默认**直接引用官方路径**（零图集增量，裁决 §4／框架 §10.3）；
      只有 ``B/pixel/nicola/fx_lut.json`` 到位（要改色）才 ``clone_effect_family`` + LUT 染色，
      引用一律走 ``rewrite_effect_refs``；
    - 语音路由（kind 3 ChangeSkillFlag ← 能力1 #1 的 536）与 ``switched_action_skill``；
    - ``B/pixel/nicola/install.json`` 里的像素小人成品（缺文件静默跳过）。

不碰：live store / ``assets/`` / ``.cdn`` / 设备 / 存档。
由 ``python mod-tools/wf_midautumn_build.py --char nicola --step kit`` 调用 :func:`build`。

**rework1（2026-09-21，作者原话见 ``rework1/author-request.md`` 第 12 行「火老师」段）**：
能力 3 整槽重做（旧 3 条 → 新 9 条：461 加层 / 211·32 给触发者 / 245·35 给自身 / 525 消耗 /
503·550 对降抗敌特攻 / 694 独立乘区）、能力 6 #0 加 CT15s、新增固有状态「月讲」与图标、
能力 3 整槽 ``desc_override``。队长技 6 行、两档技能 DSL、能力 1/2/4/5、能力 6 #1 一格不动。
施工单：``rework1/impl/nicola.md``。

**平衡第二批（2026-09-27，作者：「妮可拉……让生效不限制次数」）**：能力 3 行 2–6（0 基 #1–#5，
四条受益行 + 525 消耗行）的限次 c34 由 ``"0"``（= 限 0 次、从未触发）改成 ``(None)``；数值与面板不动。
改动落在 ``design/nicola.json`` 的 ``cells["34"]``/``row_final``（由
``wf_balance_20260927b_nicola.sync_mirrors`` 同步），本模块加 :func:`dead_trigger_limit_problems`
门禁防止再写回 ``"0"``/空串。
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

KitError = KL.KitError

KEY = "nicola"
CID, CODE = 119991, "sorceress_teacher_moon"
ELEMENT = 0                                     # 火（0 基内部编号，Red）
TEMPLATE_ID, TEMPLATE_CODE = 211020, "sorceress_teacher"

ABILITY_KEYS = tuple(f"{CID}{slot}" for slot in range(1, 7))
LEADER_ROWS = 6
ABILITY_RECORDS = 19                            # rework1：能力 3 由 3 条扩到 9 条

CAS_CHANGE_SKILL = f"change_skill_{CODE}"       # 536 的 c70 字符串键（未注册 = C8601）
OVERRIDE_SLOT = 3                               # 能力 3 整槽走面板覆盖
CAS_OVERRIDE = f"desc_override_{CODE}_{OVERRIDE_SLOT}"
VOICE_KEY = f"{CODE}_voice_ready"
VOICE_ROUTE = {"kind": 3}                       # ChangeSkillFlag ← 能力1 #1 的 536

#: desc_override 会盖掉客户端逐行画的原生「Ⓜ」；主位限制槽（c1 全键 "false"）必须自带这段
#: 前缀才能在面板上显示主位限制图标——格式逐字照抄玛格诺斯（``lion_swordman_moon``）
#: ``desc_override_lion_swordman_moon_3`` 的实际写法：前面 1 个空格、``<icon id='main'>``、
#: 后面 2 个空格；不许出现字面「Ⓜ」字符（09-21 真机反馈：妮可拉能力 3 整键主位限制但覆盖串
#: 4 行都没带这段前缀，游戏里看不到 Ⓜ）。
MAIN_ICON = " <icon id='main'>  "


def _apply_main_icon(text: str) -> str:
    """给主位限制槽的覆盖串每一行补上 :data:`MAIN_ICON` 前缀，已带前缀的行不重复加。"""
    return "\n".join(MAIN_ICON + line if line.strip() and MAIN_ICON not in line else line
                     for line in text.split("\n"))

#: rework1 的固有状态「月讲」：8 位 ``cid*100+n``（裁决 §1；7 位撞过基诺维 1699901/02）。
UID = MS.unique_condition_id(CID, 1)
UNIQUE_DONOR = "11"                             # 官方 unique_condition[11] unique_blackflower_wiz_smr22
UNIQUE_NAME = "月讲"
UC_ICON_ROW = f"battle/common/unique_condition/unique_{CODE}_lecture"
UC_ICON_LOGICAL = UC_ICON_ROW + ".png"
UC_ICON_FRAME_DONOR = "battle/common/unique_condition/unique_fire_dragon_zenith.png"

#: 能力 3 的行序契约：525 消耗行必须排在同触发的受益行之后（层数先被吃掉 = 前置 187 当场不成立）。
CONSUME_KIND = "525"
BENEFIT_KINDS = ("211", "32", "245", "35")

TEXTS: dict[str, str] = {}                      # 10 个文本键在 design/nicola.json 的 texts 块里
SPEC = {
    # desc_override 行要生效需要 V14 APK（缺补丁不崩，只是面板回落到客户端自动文案）。
    "required_capabilities": (L.PANEL_OVERRIDE_V2,),
    "extra_keys": {
        KL.UNIQUE: (UID,),
        KL.CAS: (CAS_CHANGE_SKILL, CAS_OVERRIDE),
        KL.SWITCHED: (VOICE_KEY,),
    },
}

# ---------------------------------------------------------------- 技能 DSL

SKILL_LEVELS = ("1", "2")

#: 逐命令核对用的官方 donor 树（设计稿 plan.skills.donor_trees 的实际路径）。
#: ``pirates_gunner`` 提供 ``ShowEffect`` 的 ``scale=['Some',[slv]]`` 先例；设计稿
#: 原文写的是 ``rare5/``，官方实际只有 ``rare4/``（本轮实读更正，见 deviations）。
SHAPE_DONORS = {
    "mother_1": f"battle/action/skill/action/rare4/{TEMPLATE_CODE}${TEMPLATE_CODE}_1",
    "mother_2": f"battle/action/skill/action/rare4/{TEMPLATE_CODE}${TEMPLATE_CODE}_2",
    "wirfled_2": "battle/action/skill/action/rare5/wirfled_playable$wirfled_playable_2",
    "clarisse_2": "battle/action/skill/action/rare5/clarisse$clarisse_2",
    "pirates_1": "battle/action/skill/action/rare4/pirates_gunner$pirates_gunner_1",
}

#: 每条命令允许相对**某一条**官方 donor 同名命令改动的下标（0 = 命令名本身）。
#: 闸门语义：树里每条命令都必须能在 :data:`SHAPE_DONORS` 里找到一条同名同参数个数的官方命令，
#: 其差异下标是这里的子集 —— 参数形状写歪（记忆卡 wf-dsl-param-shape-f1034）、
#: 多写/少写一位、把枚举写成裸值，都会在这一步当场炸掉。
ALLOWED_CELL_DIFFS = {
    "HideCharacter": frozenset(),
    "ShowEffect": frozenset({1, 2, 12}),              # 演出名 / 特效引用 / 缩放
    "CreateHitArea": frozenset({13, 19, 21, 22}),     # 判定区寿命 + 三个 GID
    "CreateNormalAttack": frozenset({1, 6}),          # GID + 倍率
    "CreateCondition": frozenset({1, 2}),             # GID + AdditionalCondition 条目
    "DeleteCondition": frozenset({1}),                # GID
    "FindAllSubjects": frozenset({1}),                # GID
    "ShakeCamera": frozenset({1}),                    # 震幅
}

#: 设计稿 composed_tree 写的是「克隆后」的目标路径；kit 先把它退回官方源路径，
#: 需要换色时再由 ``clone_effect_family`` + ``rewrite_effect_refs`` 改写过去。
#: 直接把克隆后的路径写死在树里 = 未克隆时指向包内不存在的路径（进战斗数据不足 / C8003）。
EFFECT_RETARGET = {
    f"battle/effect/skill_unique/{CODE}/{CODE}_player_back":
        f"battle/effect/skill_unique/{TEMPLATE_CODE}/{TEMPLATE_CODE}_player_back",
    f"battle/effect/skill_unique/{CODE}/{CODE}_all":
        f"battle/effect/skill_unique/{TEMPLATE_CODE}/{TEMPLATE_CODE}_all",
    f"battle/effect/skill_unique/{CODE}/moon_phase/moon_phase_explosion":
        "battle/effect/skill_unique/megumin/megumin_explosion",
}

#: 官方 donor 的「ダミー演出」把第 10 位（``ShowEffect`` 参数 9）写 ``true``（自身挂载的
#: 立绘背景演出）；设计稿的 composed_tree 写成了 ``false``，本轮按 donor 原值恢复。
DUMMY_EFFECT_LABEL = "ダミー演出"
DUMMY_EFFECT_FLAG_INDEX = 10

#: 换色时才克隆的两族特效：(源目录, 目标子目录, 要复制的基名)
FX_FAMILIES = (
    (f"battle/effect/skill_unique/{TEMPLATE_CODE}", "lecture",
     (f"{TEMPLATE_CODE}_all", f"{TEMPLATE_CODE}_player_back")),
    ("battle/effect/skill_unique/megumin", "moon_phase", ("megumin_explosion",)),
)


# ---------------------------------------------------------------- 设计稿读取

def load_design(root: Path) -> dict[str, Any]:
    design = MS.load_design(Path(root), KEY)
    if not design:
        raise KitError(f"design/{KEY}.json missing (batch {MS.BATCH_DIR})")
    identity = design.get("identity") or {}
    if design.get("schema") != "ma-design/1" or design.get("key") != KEY:
        raise KitError(f"design schema/key drift: {design.get('schema')} {design.get('key')}")
    if (identity.get("cid"), identity.get("code"), identity.get("element")) != (CID, CODE, ELEMENT):
        raise KitError(f"design identity drift: {identity.get('cid')}/{identity.get('code')}"
                       f"/element {identity.get('element')}")
    template = identity.get("template_character") or {}
    if (template.get("id"), template.get("code")) != (TEMPLATE_ID, TEMPLATE_CODE):
        raise KitError(f"design template drift: {template.get('id')}/{template.get('code')}")
    return design


def _parse_donor(donor: str) -> tuple[str, str, str]:
    """设计稿的 donor 地址 ``"<official|live>:<ability|leader>:<键>#L<记录号(1基)>"``。

    → ``(source, kind, "键#记录号(0基)")``。``official`` = ``.cdn/cn`` 官方归档
    （``OfficialBaseline``，不是 store）；``live`` = 已上线的自制角色行，只读。
    """
    parts = str(donor).split(":")
    if len(parts) != 3:
        raise KitError(f"unexpected donor address shape: {donor!r}")
    src, table, rest = parts
    source = {"official": "official", "live": "live"}.get(src)
    kind = {"ability": "ability", "leader": "leader_ability"}.get(table)
    if source is None or kind is None:
        raise KitError(f"unrecognised donor address: {donor!r}")
    key, sep, record = rest.partition("#")
    if not sep:
        raise KitError(f"donor address lacks the #L<record> suffix: {donor!r}")
    index0 = int(record.lstrip("Ll")) - 1
    if index0 < 0:
        raise KitError(f"donor record number must be >= 1 (1-based): {donor!r}")
    return source, kind, f"{key}#{index0}"


def _check_row_final(label: str, row: list[str], entry: dict[str, Any]) -> None:
    """与设计稿登记的 ``row_final`` 逐格核对（设计稿是先算好的产物，这里抓转录/漂移）。"""
    expected = entry.get("row_final")
    if not expected:
        return
    expected = [str(x) for x in expected]
    if expected == row:
        return
    width = max(len(expected), len(row))
    diff = [(i, expected[i] if i < len(expected) else None, row[i] if i < len(row) else None)
            for i in range(width)
            if (expected[i] if i < len(expected) else None) != (row[i] if i < len(row) else None)]
    raise KitError(f"{label}: row differs from design row_final at {diff[:8]}")


def build_leader_rows(ctx, design: dict[str, Any]) -> tuple[list[list[str]], list[dict[str, Any]]]:
    plan = design["plan"]["leader_ability"]
    if plan["key"] != str(CID) or int(plan["layout"]["ncols"]) != KL.LEADER_NCOLS:
        raise KitError(f"design leader block drift: key={plan.get('key')} layout={plan.get('layout')}")
    rows: list[list[str]] = []
    evidence: list[dict[str, Any]] = []
    for entry in plan["rows"]:
        source, kind, donor = _parse_donor(entry["donor"])
        if kind != "leader_ability":
            raise KitError(f"leader#{entry['index']}: donor table is {kind}")
        label = f"leader#{entry['index']}"
        row, ev = KL.build_row(ctx, "leader_ability", donor, entry["cells"], source=source,
                               element=ELEMENT, expect_describe=entry["desc_expected"], label=label)
        if row[0] != CODE:
            raise KitError(f"{label}: c0 {row[0]!r} != {CODE}")
        _check_row_final(label, row, entry)
        rows.append(row)
        evidence.append(ev)
    if len(rows) != LEADER_ROWS or int(plan["new_row_count"]) != LEADER_ROWS:
        raise KitError(f"design leader_ability carries {len(rows)} rows, expected {LEADER_ROWS}")
    return rows, evidence


def ban_forbidden_leader_kinds(rows: list[list[str]]) -> None:
    """队长表禁 422/724/713（裁决 §2/§8：写进队长表 = C7050）。瞬发 kind 在 c45，during 在 c107。"""
    for n, row in enumerate(rows):
        if row[45] in ("422", "724", "713") or row[107] in ("422", "724", "713"):
            raise KitError(f"leader#{n}: forbidden kind in leader_ability "
                           f"(c45={row[45]!r} c107={row[107]!r})")


def build_ability_rows(ctx, design: dict[str, Any]) -> tuple[dict[str, list[list[str]]],
                                                             list[dict[str, Any]]]:
    plan = design["plan"]["ability"]
    if int(plan["layout"]["ncols"]) != KL.ABILITY_NCOLS:
        raise KitError(f"design ability ncols drift: {plan['layout'].get('ncols')}")
    if tuple(sorted(plan["keys"])) != tuple(sorted(ABILITY_KEYS)):
        raise KitError(f"design ability keys drift: {sorted(plan['keys'])}")
    rows_by_key: dict[str, list[list[str]]] = {}
    evidence: list[dict[str, Any]] = []
    total = 0
    for slot, key_name in enumerate(ABILITY_KEYS, start=1):
        block = plan["keys"][key_name]
        rows: list[list[str]] = []
        for entry in block["records"]:
            source, kind, donor = _parse_donor(entry["donor"])
            if kind != "ability":
                raise KitError(f"{key_name}#{entry['index']}: donor table is {kind}")
            label = f"{key_name}#{entry['index']}"
            row, ev = KL.build_row(ctx, "ability", donor, entry["cells"], source=source,
                                   element=ELEMENT, expect_describe=entry["desc_expected"],
                                   label=label)
            _check_row_final(label, row, entry)
            rows.append(row)
            evidence.append(ev)
        KL.check_ability_key(rows, key_name, CODE, slot)
        # 裁决 §8：c2 statue_group 每键单值；c1 主位限制同样整键一致（check_ability_key 已判
        # 「全键一致」，这里再对上设计稿登记的值，防止两边同时漂到别的值上）。
        wanted_c1 = [str(x) for x in block["unisonable_per_record"]]
        if [r[1] for r in rows] != wanted_c1 or rows[0][2] != block["statue_group"]:
            raise KitError(f"ability {key_name}: c1/c2 {[r[1] for r in rows]}/{rows[0][2]!r} "
                           f"!= design {wanted_c1}/{block['statue_group']!r}")
        if int(block["record_count"]["new"]) != len(rows):
            raise KitError(f"ability {key_name}: {len(rows)} records != design "
                           f"{block['record_count']['new']}")
        rows_by_key[key_name] = rows
        total += len(rows)
    if total != ABILITY_RECORDS or int(plan["record_total"]) != ABILITY_RECORDS:
        raise KitError(f"ability record total {total} != {ABILITY_RECORDS}")
    return rows_by_key, evidence


def write_strings(ctx, design: dict[str, Any], ability_rows: dict[str, list[list[str]]]) -> dict[str, str]:
    """``custom_ability_string``：536 的 c70 字符串键 + 能力 3 整槽的面板覆盖串。

    两个键的反查判据不同：536 的串必须被某条行的 c70 引用（否则是死串）；
    ``desc_override_*`` 的串按键名反查 —— 客户端查的是 ``desc_override_`` ＋ 该槽
    **第 0 行的 c0（string_id）**，所以只要对应槽真的以那个 string_id 开头就算接上。
    """
    rows = design["plan"]["texts"]["custom_ability_string"]["rows"]
    plan = {entry["key"]: entry["text"] for entry in rows}
    if set(plan) != {CAS_CHANGE_SKILL, CAS_OVERRIDE}:
        raise KitError(f"design custom_ability_string keys drift: {sorted(plan)}")
    declared = set(ctx.spec.extra_keys.get(KL.CAS, ()))
    missing = [k for k in plan if k not in declared]
    if missing:
        raise KitError(f"custom_ability_string keys not declared in SPEC['extra_keys']: {missing}")
    # 裁决 §3：能力里的「技能强化」条目不写数字与时间；覆盖串只过通用禁词
    # （按设计稿原文校验，此时还没有加主位图标前缀）。
    KL.check_panel(plan[CAS_CHANGE_SKILL], skill_flag=True, label=CAS_CHANGE_SKILL)
    for line in plan[CAS_OVERRIDE].split("\n"):
        KL.check_panel(line, label=CAS_OVERRIDE)
    # 反查 1：536 的串真的被某条行的 c70 引用。
    referenced = {row[70] for rows_ in ability_rows.values() for row in rows_ if row[70]}
    if CAS_CHANGE_SKILL not in referenced:
        raise KitError(f"custom_ability_string {CAS_CHANGE_SKILL} not referenced by any ability c70")
    # 反查 2：覆盖串的键名与能力 3 第 0 行的 string_id 对得上。
    slot_rows = ability_rows[f"{CID}{OVERRIDE_SLOT}"]
    want = L.PANEL_OVERRIDE_KEY_PREFIX + slot_rows[0][0]
    if want != CAS_OVERRIDE:
        raise KitError(f"panel override key {CAS_OVERRIDE!r} != desc_override_<string_id> {want!r}")

    # 整键 c1（主位限制）全键一致（check_ability_key 已判）；c1="false" ⇒ 主位限制槽，
    # 覆盖串每行必须自带 <icon id='main'> 前缀（09-21 真机反馈：4 行都没带，看不到 Ⓜ）。
    wants_icon = slot_rows[0][1] == "false"
    before_lines = plan[CAS_OVERRIDE].split("\n")
    if wants_icon:
        plan[CAS_OVERRIDE] = _apply_main_icon(plan[CAS_OVERRIDE])
    override_lines = plan[CAS_OVERRIDE].split("\n")
    if len(override_lines) != len(before_lines):
        raise KitError(f"{CAS_OVERRIDE}: main-position icon prefix changed the line count")
    if wants_icon and any(not line.startswith(MAIN_ICON) for line in override_lines):
        raise KitError(f"{CAS_OVERRIDE}: main-position icon prefix missing on some lines")
    if "Ⓜ" in plan[CAS_OVERRIDE]:
        raise KitError(f"{CAS_OVERRIDE}: literal 'Ⓜ' character forbidden")

    ctx.write_flat(KL.CAS, {k: [[v]] for k, v in plan.items()})
    return plan


def build_unique(ctx, design: dict[str, Any]) -> tuple[str, list[str]]:
    """rework1 的固有状态「月讲」：官方 donor + 逐格改，并与设计稿登记的整行逐格核对。"""
    add = design["plan"]["unique_conditions"]["add"]
    if len(add) != 1 or str(add[0].get("key")) != UID:
        raise KitError(f"design unique_conditions must carry exactly {UID}: "
                       f"{[a.get('key') for a in add]}")
    entry = add[0]
    key, row = KL.unique_row(ctx, ctx.spec, 1, UNIQUE_DONOR, entry["cells"])
    if key != UID:
        raise KitError(f"unique id {key} != {UID}")
    if row[1] != UNIQUE_NAME or row[2] != UC_ICON_ROW:
        raise KitError(f"unique name/icon drift: {row[1]!r} {row[2]!r}")
    if (row[3], row[4]) != ("99999999", "99"):
        # c3 = 无时间限制、c4 = 不设上限；c4 写 (None) 等于上限 1，会把 461 叠层弄死。
        raise KitError(f"unique duration/cap unexpected: c3={row[3]!r} c4={row[4]!r}")
    expected = [str(x) for x in entry.get("row") or []]
    if expected and expected != row:
        raise KitError(f"unique row differs from design row: {expected} vs {row}")
    KL.write_unique(ctx, ctx.spec, {key: row})
    return key, row


def draw_icon(frame):
    """48×48「月讲」：夜黑圆角底 + 金边，金色残月 + 摊开的讲义。

    与 magnus/普莉姆拉同工艺：8× 画布绘制 → LANCZOS 缩回 48×48 → 外框 alpha 逐格取官方图标
    （alpha 一格不改，避免图集 alpha 门禁变红）。
    """
    from PIL import Image, ImageDraw
    if frame.size != (48, 48):
        raise KitError(f"icon frame donor must be 48x48, got {frame.size}")
    K = 8
    N = 48 * K
    layer = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    inner = Image.new("L", (N, N), 0)
    ImageDraw.Draw(inner).rounded_rectangle((3 * K, 3 * K, 45 * K - 1, 45 * K - 1),
                                            radius=5 * K, fill=255)
    top, bot = (34, 28, 46), (16, 13, 24)
    grad = Image.new("RGBA", (1, N))
    for y in range(N):
        t = y / (N - 1)
        grad.putpixel((0, y), tuple(round(top[i] + (bot[i] - top[i]) * t) for i in range(3)) + (255,))
    layer.paste(grad.resize((N, N)), (0, 0), inner)

    gold, moon = (216, 150, 58, 255), (246, 224, 150, 255)
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle((4 * K, 4 * K, 44 * K - 1, 44 * K - 1), radius=4 * K,
                        outline=gold, width=2 * K)

    # 残月：大圆减去偏左下的小圆，凹侧朝左下，让出下方放讲义
    disc = Image.new("L", (N, N), 0)
    ImageDraw.Draw(disc).ellipse((16.0 * K, 6.0 * K, 40.0 * K, 30.0 * K), fill=255)
    cut = Image.new("L", (N, N), 0)
    ImageDraw.Draw(cut).ellipse((10.0 * K, 9.0 * K, 34.0 * K, 33.0 * K), fill=255)
    crescent = Image.composite(Image.new("L", (N, N), 0), disc, cut)
    layer.paste(Image.new("RGBA", (N, N), moon), (0, 0),
                Image.composite(crescent, Image.new("L", (N, N), 0), inner))

    # 讲义：摊开的书 —— 两页梯形 + 中缝 + 三道字行
    page = (238, 233, 220, 255)
    shade = (198, 190, 172, 255)
    left = [(8.0, 30.0), (23.0, 27.0), (23.0, 40.0), (8.0, 42.0)]
    right = [(40.0, 30.0), (25.0, 27.0), (25.0, 40.0), (40.0, 42.0)]
    for poly, fill in ((left, page), (right, shade)):
        d.polygon([(x * K, y * K) for x, y in poly], fill=fill, outline=gold, width=max(1, K // 2))
    d.line([(24.0 * K, 27.4 * K), (24.0 * K, 40.6 * K)], fill=gold, width=K)
    ink = (120, 112, 96, 255)
    for i, y in enumerate((31.6, 34.4, 37.2)):
        d.line([(10.6 * K, (y + 0.35 * i) * K), (21.4 * K, (y - 0.2 + 0.35 * i) * K)],
               fill=ink, width=max(1, K // 2))
        d.line([(26.6 * K, (y - 0.2 + 0.35 * i) * K), (37.4 * K, (y + 0.35 * i) * K)],
               fill=ink, width=max(1, K // 2))

    small = layer.resize((48, 48), Image.LANCZOS)
    out = Image.new("RGBA", (48, 48), (255, 255, 255, 0))
    fp, op, sp = frame.load(), out.load(), small.load()
    for y in range(48):
        for x in range(48):
            r, g, b, a = sp[x, y]
            fa = fp[x, y][3]
            if a:
                op[x, y] = (round((r * a + 255 * (255 - a)) / 255),
                            round((g * a + 255 * (255 - a)) / 255),
                            round((b * a + 255 * (255 - a)) / 255), fa)
            else:
                op[x, y] = (255, 255, 255, fa)
    return out


def install_unique_icon(ctx) -> dict[str, Any]:
    """画图标并装进包的 ``common`` 根；alpha 必须与官方 frame donor 逐字节一致。"""
    raw = ctx.official_read(UC_ICON_FRAME_DONOR)
    if raw is None:
        _root, raw, _how = ctx.pack.template_asset(UC_ICON_FRAME_DONOR)
    frame = ctx.png_open(raw)
    data = ctx.png_store_bytes(draw_icon(frame))
    ctx.write_asset("common", UC_ICON_LOGICAL, data)
    back = ctx.png_open(ctx.pack.pkg_path("common", UC_ICON_LOGICAL).read_bytes())
    if back.size != (48, 48):
        raise KitError(f"unique_condition icon must stay 48x48, got {back.size}")
    if back.getchannel("A").tobytes() != frame.getchannel("A").tobytes():
        raise KitError("unique_condition icon alpha differs from the official frame donor")
    import hashlib
    return {"logical": UC_ICON_LOGICAL, "frame_donor": UC_ICON_FRAME_DONOR,
            "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def dead_trigger_limit_problems(rows_by_key: dict[str, list[list[str]]]) -> list[str]:
    """有瞬发触发（c27 非空非 0）的行，限次 c34 写 ``""`` 或 ``"0"`` = 限 0 次 = 永不触发。

    ``AbilityValues.parseAt34`` 把 ``"0"`` 读成 ``Some(0)``，``AbilityTriggerHandler`` 在
    ``restTriggerLimit<=0`` 时直接 return；「不限次」只能写字面量 ``(None)``。能力 3 行 2–6 曾写 ``"0"``，
    面板写着生效、游戏里从未触发（2026-09-27 平衡第二批复核 C11，作者：「让生效不限制次数」）。
    """
    return [f"{key}#{index}: instant trigger {row[27]} has trigger_limit {row[34]!r} (= 0 次, never fires)"
            for key, rows in rows_by_key.items() for index, row in enumerate(rows)
            if row[27] not in ("", "0") and row[34] in ("", "0")]


def consume_order_problems(rows: list[list[str]]) -> list[str]:
    """能力 3 的行序契约：525 消耗行排在同触发的受益行之后，且两者前置/触发完全同形。

    顺序反了 ⇒ 同一次「队友发动技能」里层数先被吃掉，受益行的前置 187（自身持有月讲）
    当场不成立，四条加成全部静默失效。
    """
    kinds = [row[47] for row in rows]
    if CONSUME_KIND not in kinds:
        return [f"能力 {OVERRIDE_SLOT} 丢了 {CONSUME_KIND} 消耗行: {kinds}"]
    consume_at = kinds.index(CONSUME_KIND)
    consume = rows[consume_at]
    problems: list[str] = []
    seen = 0
    for index, row in enumerate(rows):
        if row[47] not in BENEFIT_KINDS or row[27] != consume[27]:
            continue
        seen += 1
        if index > consume_at:
            problems.append(f"受益行 #{index}(kind {row[47]}) 排在 {CONSUME_KIND} 消耗行 "
                            f"#{consume_at} 之后")
        if row[6:27] != consume[6:27] or row[27:35] != consume[27:35]:
            problems.append(f"受益行 #{index} 与消耗行的前置/触发块不同形，层数门会两边不一致")
    if not seen:
        problems.append(f"能力 {OVERRIDE_SLOT}: {CONSUME_KIND} 消耗行没有同触发的受益行")
    if consume[68] != UID:
        problems.append(f"{CONSUME_KIND} 消耗行的固有列 c68={consume[68]!r} != {UID}")
    return problems


def write_action_skill(ctx, design: dict[str, Any]) -> dict[str, list[str]]:
    """两档技能能量（名称/描述由 ``tables`` 写 TEXTS，这里只改 c4/c5）。"""
    spec = ctx.spec
    energy = design["plan"]["skills"]["energy"]
    if design["plan"]["skills"]["action_skill_outer_key"] != CODE:
        raise KitError(f"design action_skill outer key drift: "
                       f"{design['plan']['skills']['action_skill_outer_key']!r}")
    inner = ctx.pkg_nested(CODE)
    if set(inner) != set(SKILL_LEVELS):
        raise KitError(f"package action_skill inner keys {sorted(inner)}")
    out: dict[str, list[str]] = {}
    for level in SKILL_LEVELS:
        cells = list(inner[level])
        if cells[7] != ctx.program_path(level):
            raise KitError(f"action_skill {level} program path drift: {cells[7]!r}")
        if cells[0] != spec.texts[f"skill{level}"] or cells[1] != spec.texts[f"desc{level}"]:
            raise KitError(f"action_skill {level}: name/desc differ from design texts (rerun tables)")
        cells[4], cells[5] = str(energy[level]["c4"]), str(energy[level]["c5"])
        out[level] = cells
    ctx.write_nested(KL.ACTION, CODE, {lv: [cells] for lv, cells in out.items()}, replace_inner=True)
    return out


# ---------------------------------------------------------------- DSL

def _flat_command(cmd: list) -> list:
    """命令的顶层参数；嵌套 ``Block``（子命令表）折成哨兵，只比本命令自己这一层。"""
    return ["<block>" if isinstance(x, list) and x and x[0] == "Block" else x for x in cmd]


def _shape(node) -> str:
    """参数的结构指纹：枚举名保留、具体数值抹掉。

    用来判「这一位的**形状**跟官方 donor 是不是同一种」——裸数值进 Array 参
    （``[{'min':10,'max':10}]`` 写成 ``10``）这类写法在详情页炸 F1034，往返自检抓不到
    （记忆卡 wf-dsl-param-shape-f1034）。
    """
    if isinstance(node, bool):
        return "bool"
    if isinstance(node, (int, float)):
        return "num"
    if node is None:
        return "null"
    if isinstance(node, str):
        return "str"
    if isinstance(node, dict):
        keys = set(node)
        return "slv" if keys <= {"min", "max", "alv_min", "alv_max", "alv2_min", "alv2_max"} \
            else "dict:" + ",".join(sorted(keys))
    if isinstance(node, list):
        if not node:
            return "[]"
        if isinstance(node[0], str) and node[0] in ("Block", "Command", "Event"):
            return node[0].lower()
        if isinstance(node[0], str):
            return "[" + node[0] + "|" + ",".join(_shape(x) for x in node[1:]) + "]"
        return "[" + ",".join(_shape(x) for x in node) + "]"
    return type(node).__name__


def donor_command_index(ctx) -> dict[str, list[list]]:
    index: dict[str, list[list]] = {}
    for path in SHAPE_DONORS.values():
        tree = ctx.template_dsl(path)
        for cmd in wf_dsl.iter_dsl_commands(tree):
            index.setdefault(cmd[0], []).append(_flat_command(cmd))
    return index


def _donor_shapes_by_slot(commands: list[list]) -> dict[int, set[str]]:
    """同名 donor 命令按下标汇总出现过的形状（官方在这一位写过哪几种形状）。"""
    out: dict[int, set[str]] = {}
    for cmd in commands:
        for i, value in enumerate(cmd):
            out.setdefault(i, set()).add(_shape(value))
    return out


def donor_gate_problems(tree, donors: dict[str, list[list]]) -> list[str]:
    """每条命令都必须能在官方 donor 里找到一条同名命令，满足两个条件：

    1. **值锚**：存在一条同名同参数个数的官方命令，与本命令不相等的下标全部落在
       :data:`ALLOWED_CELL_DIFFS` 的白名单里；
    2. **形状先例**：本命令每一位的形状（:func:`_shape`）都在官方同名命令的同一位上出现过。

    第 2 条独立于第 1 条：白名单允许改值，但改出来的形状必须是官方在那一位真写过的。
    「裸数值进 Array 参」这类 F1034 写法即使发生在允许改动的那一位，也会在这里被抓。
    """
    problems: list[str] = []
    for cmd in wf_dsl.iter_dsl_commands(tree):
        name = cmd[0]
        allowed = ALLOWED_CELL_DIFFS.get(name)
        candidates = donors.get(name, ())
        if allowed is None:
            problems.append(f"{name}: 没有登记允许改动的下标（新命令必须先找官方先例）")
            continue
        mine = _flat_command(cmd)
        same_arity = [c for c in candidates if len(c) == len(mine)]
        if not same_arity:
            problems.append(f"{name}: 官方 donor 里没有同参数个数（{len(mine) - 1}）的同名命令")
            continue
        best: tuple[int, list[int]] | None = None
        anchored = False
        for other in same_arity:
            diff = sorted(i for i in range(len(mine)) if mine[i] != other[i])
            outside = [i for i in diff if i not in allowed]
            if best is None or len(outside) < best[0]:
                best = (len(outside), diff)
            if not outside:
                anchored = True
                break
        if not anchored:
            problems.append(f"{name}: 找不到只差 {sorted(allowed)} 的官方 donor 命令"
                            f"（最接近的差在 {best[1] if best else '?'}）")
        by_slot = _donor_shapes_by_slot(same_arity)
        for i, value in enumerate(mine):
            shape = _shape(value)
            if shape not in by_slot.get(i, set()):
                problems.append(f"{name}[{i}]: 形状 {shape} 在官方同名命令的这一位上零先例"
                                f"（官方写过 {sorted(by_slot.get(i, set()))}）")
    return problems


def dsl_gate_problems(tree, *, element: int | None = None) -> list[str]:
    problems: list[str] = []
    problems += [f"direction: {p}" for p in wf_dsl.player_side_dsl_problems(tree)]
    problems += [f"coord: {p}" for p in wf_dsl.coord_sys_source_problems(tree)]
    problems += [f"subject: {p}" for p in L.action_dsl_subject_binding_problems(tree)]
    problems += [f"hit_target: {p}" for p in L.action_dsl_hit_area_target_problems(tree)]
    if element is not None:
        problems += [f"element: {p}" for p in L.action_dsl_element_problems(tree, element)]
    return problems


def retarget_effects(tree) -> int:
    """把设计稿写的「克隆后目标路径」退回官方源路径，并恢复 donor 的 ダミー演出 布尔位。"""
    changed = 0
    for cmd in wf_dsl.iter_dsl_commands(tree, "ShowEffect"):
        ref = cmd[2]
        if isinstance(ref, list) and len(ref) == 2 and ref[0] == "SpecifyEffectDirectly":
            target = EFFECT_RETARGET.get(str(ref[1]))
            if target is not None:
                cmd[2] = ["SpecifyEffectDirectly", target]
                changed += 1
        if cmd[1] == DUMMY_EFFECT_LABEL and cmd[DUMMY_EFFECT_FLAG_INDEX] is not True:
            cmd[DUMMY_EFFECT_FLAG_INDEX] = True
            changed += 1
    return changed


def build_skill_tree(ctx, design: dict[str, Any], level: str, families: list[dict[str, Any]],
                     donors: dict[str, list[list]]) -> tuple[Any, dict[str, Any]]:
    plan = design["plan"]["skills"][f"tree_plan_{level}"]
    if plan["program"] != ctx.program_path(level):
        raise KitError(f"skill {level} program path drift: {plan['program']!r}")
    tree = copy.deepcopy(plan["composed_tree"])
    if not (isinstance(tree, list) and tree and tree[0] == "ActionDsl"):
        raise KitError(f"skill {level} design tree is not a bare ActionDsl tree")
    if tree[10] != 0:
        # tree[10] = buffTargetAs：0 = 自动档 = 技能伤害；写 2/3/4 会改乘区，
        # 全队技伤加成全部失效（记忆卡 wf-dsl-damage-attribution-bufftargetas）。
        raise KitError(f"skill {level}: buffTargetAs must stay 0, got {tree[10]}")
    retarget_effects(tree)

    rewrites = 0
    kept: list[str] = []
    for family in families:
        tree, info = ctx.rewrite_effect_refs(tree, family)
        rewrites += info["rewritten"]
        kept += list(info.get("kept_donor") or ())

    problems = donor_gate_problems(tree, donors) + dsl_gate_problems(tree, element=ELEMENT)
    if problems:
        raise KitError(f"skill {level} DSL gates failed: {problems}")
    refs = sorted({str(c[2][1]) for c in wf_dsl.iter_dsl_commands(tree, "ShowEffect")
                   if isinstance(c[2], list) and len(c[2]) == 2 and c[2][0] == "SpecifyEffectDirectly"})
    return tree, {"level": level, "effect_rewrites": rewrites, "effect_refs": refs,
                  "kept_official_refs": sorted(set(kept)),
                  "buff_target_as": tree[10], "values": plan.get("values")}


def write_dsl_checked(ctx, program: str, tree) -> str:
    """``write_dsl`` 只吃裸树；写后回读比对（记忆卡 wf-dsl-encode-wrapper-trap）。"""
    if not (isinstance(tree, list) and tree and tree[0] == "ActionDsl"):
        raise KitError(f"write_dsl needs a bare ActionDsl tree, got {type(tree).__name__}")
    logical = ctx.write_dsl(program, tree)
    back = ctx.amf_parse(ctx.pack.pkg_path("common", logical).read_bytes())
    if back != tree:
        raise KitError(f"DSL readback mismatch: {logical}")
    return logical


def clone_effect_families(ctx, transform) -> list[dict[str, Any]]:
    """只有要换色（``fx_lut.json`` 到位）才克隆；否则直接引用官方路径（零图集增量）。"""
    if transform is None:
        return []
    families = []
    for src_dir, subdir, members in FX_FAMILIES:
        family = ctx.clone_effect_family(src_dir, subdir, fx_names=list(members),
                                         png_transform=transform)
        if sorted(family["copied_bases"]) != sorted(members):
            raise KitError(f"effect family {src_dir}: copied {family['copied_bases']} != {list(members)}")
        families.append(family)
    return families


# ---------------------------------------------------------------- 入口

def build(ctx) -> dict[str, Any]:
    spec = ctx.spec
    if (spec.cid, spec.code, spec.element) != (CID, CODE, ELEMENT):
        raise KitError(f"identity drift: {spec.cid}/{spec.code}/element {spec.element}")
    if (spec.template_id, spec.template_code) != (TEMPLATE_ID, TEMPLATE_CODE):
        raise KitError(f"template drift: {spec.template_id}/{spec.template_code}")
    if spec.pf_type != 4 or spec.stance != "Supporter" or spec.rarity != 5:
        raise KitError(f"spec drift: pf_type={spec.pf_type} stance={spec.stance} rarity={spec.rarity}")
    if MS.text_placeholders(spec):
        raise KitError(f"design texts still placeholders: {MS.text_placeholders(spec)}")

    design = load_design(ctx.root)

    # ---- 0) rework1 的固有状态「月讲」+ 48×48 图标
    unique_key, unique_row = build_unique(ctx, design)
    icon = install_unique_icon(ctx)

    # ---- 1) 队长技 6 行（design.json 驱动）
    leader_rows, leader_evidence = build_leader_rows(ctx, design)
    ban_forbidden_leader_kinds(leader_rows)
    capabilities: set[str] = set()
    for ev in leader_evidence:
        capabilities.update(ev["capabilities"])
    ctx.write_flat(KL.LEADER, {str(CID): leader_rows})

    # ---- 2) 词条 6 键 13 条（design.json 驱动）
    ability_rows, ability_evidence = build_ability_rows(ctx, design)
    for ev in ability_evidence:
        capabilities.update(ev["capabilities"])
    order = consume_order_problems(ability_rows[f"{CID}{OVERRIDE_SLOT}"])
    if order:
        raise KitError(f"ability {CID}{OVERRIDE_SLOT} order contract failed: {order}")
    dead = dead_trigger_limit_problems(ability_rows)
    if dead:
        raise KitError(f"ability rows carry dead trigger limits: {dead}")
    referenced = {row[68] for rows in ability_rows.values() for row in rows
                  if row[47] in ("461", "525") and row[68]}
    if referenced != {unique_key}:
        raise KitError(f"461/525 rows reference unique ids {sorted(referenced)}, expected {unique_key}")
    ctx.write_flat(KL.ABILITY, ability_rows)

    # ---- 3) 536 的面板字符串
    cas_plan = write_strings(ctx, design, ability_rows)

    # ---- 4) action_skill 两档能量
    action_rows = write_action_skill(ctx, design)

    # ---- 5) 技能特效：默认直接引用官方路径；有 fx_lut.json 才克隆 + 染色
    lut_path = KL.pixel_dir(ctx) / "fx_lut.json"
    transform = KL.png_transform_from_lut(lut_path)
    families = clone_effect_families(ctx, transform)

    # ---- 6) 技能 DSL 两档
    donors = donor_command_index(ctx)
    programs: list[str] = []
    skill_gates: dict[str, Any] = {}
    for level in SKILL_LEVELS:
        tree, gates = build_skill_tree(ctx, design, level, families, donors)
        programs.append(write_dsl_checked(ctx, ctx.program_path(level), tree))
        skill_gates[level] = gates

    # ---- 7) 语音路由（kind 3 ChangeSkillFlag ← 能力1 #1 的 536）+ character 行
    route = KL.voice_route(CODE, VOICE_ROUTE)
    design_route = design["voice"]["route"]
    if int(design_route["kind"]) != VOICE_ROUTE["kind"] or \
            [str(x) for x in design_route["character_c9_c16"]] != route:
        raise KitError(f"design voice route drift: {design_route}")
    if not any(row[47] == "536" for rows in ability_rows.values() for row in rows):
        raise KitError("voice route kind 3 (ChangeSkillFlag) needs a 536 ability row in the kit")
    char_row = ctx.pack.pkg_character_row()
    char_row[9:17] = route
    if char_row[6] != str(spec.pf_type) or char_row[26] != "Supporter" or char_row[27] != str(CID):
        raise KitError(f"character row drift: c6={char_row[6]} c26={char_row[26]} c27={char_row[27]}")
    if char_row[18] != spec.texts["leader"] or list(char_row[19:25]) != list(ABILITY_KEYS):
        raise KitError(f"character row leader/ability columns drift: {char_row[17:25]}")
    ctx.write_flat(KL.CHARACTER, {str(CID): [char_row]})
    voice_ready = KL.write_voice_ready(ctx)

    # ---- 8) 像素成品（缺文件静默跳过）+ 三层镜像
    pixel = KL.install_staged_assets(ctx)
    mirrors = ctx.sync_character_mirrors()
    if mirrors["character"][9:17] != route:
        raise KitError("character mirror lost the voice route")

    # 面板：队长 6 行与能力 1/2/4/5/6 按 wf_describe 原文显示（本套件零 422/724/629/722、零 during 行）；
    # 能力 3 的 9 条记录整槽被 desc_override 覆盖（4 行，文字＝rework1/panel/nicola.json，
    # 每行已由 write_strings 加上主位限制图标前缀 MAIN_ICON）；536 条目的文字来自 custom_ability_string。
    override_slot = f"{CID}{OVERRIDE_SLOT}"
    panel = [ev["describe"] for ev in leader_evidence]
    panel += [ev["describe"] for ev in ability_evidence
              if not ev["label"].startswith(f"{override_slot}#")]
    panel += cas_plan[CAS_OVERRIDE].split("\n")
    panel.append(cas_plan[CAS_CHANGE_SKILL])

    ctx.evidence_write("kit-gates.json", {
        "leader": {"rows": leader_rows, "evidence": leader_evidence},
        "ability": {"rows": ability_rows, "evidence": ability_evidence},
        "unique_condition": {unique_key: unique_row, "icon": icon},
        "skills": skill_gates, "action_skill": action_rows,
        "custom_ability_string": cas_plan,
        "effect_families": [{k: fam[k] for k in ("src_dir", "dst_dir", "layout", "copied_bases",
                                                 "complete_family", "missing_effects")}
                            for fam in families],
        "fx_lut": {"path": str(lut_path), "present": transform is not None},
        "donor_trees": SHAPE_DONORS, "allowed_cell_diffs": {k: sorted(v) for k, v in
                                                            ALLOWED_CELL_DIFFS.items()},
        "voice_route": route, "voice_ready": voice_ready,
        "pixel": pixel, "mirrors": mirrors,
    })

    notes = [
        "队长 6 行：火共鸣（编成≥6）基座攻击 200% + 技伤 200%，招牌是 L3「开局除自身全员(火)"
        "技能槽 100%」与 L4「任一火属性角色技能槽充满 → 全队(火)技伤 +30%，限 5 次」；"
        "全队主轴合计 550%（裁决 §2 带 490–650）。",
        "词条 6 键 19 条：全部瞬发行（触发模式列全 0，零 during 行）——绕开 c85 哨兵、"
        "during puller 契约与「生命值100%以下」恒真文案三类坑。",
        "rework1 能力 3（9 条，整槽主位限定）：461 在「自身技能槽充满」(触发 24) 加 1 层「月讲」；"
        "211/32 在「除自身外的火属性角色发动技能」(puller 4 + 组 Red) 给**触发者**(target 7) "
        "技能槽 10%／攻击力 50%；245/35 同触发给自身 槽上限 5%／充能 5%（c34 写字面量 (None) ⇒ 不限次、"
        "可叠加；2026-09-27 前误写 \"0\" = 限 0 次、从未触发，平衡第二批按作者「让生效不限制次数」更正）；"
        "525 排在四条受益行之后消耗 1 层；503/550 对已挂火抗降低的敌人各 300% 特攻；694 独立乘区技伤 15%。",
        f"固有状态「月讲」{UID}：c3=99999999（无时间限制）、c4=99（不设上限，写 (None) 等于上限 1 会把 "
        "461 叠层弄死）；48×48 图标程序绘制，alpha 逐格取官方 unique_fire_dragon_zenith.png。",
        "引擎侧已知封顶（行里没有上限、但客户端有）：IC 35 技能槽充能速度游戏内上限 50%"
        "（记忆卡 wf-skill-gauge-max-exists 真机实测），所以「每消耗 1 层 +5%」叠到 10 层就不再涨；"
        "IC 245 技能槽最大值官方 soul 侧带到 40%，客户端是否另有封顶未验 —— 两条都只影响收益上限，"
        "不影响行是否生效，面板按裁决 §3 不写这类全局封顶。",
        "面板：能力 3 的 9 条记录整槽走 desc_override（4 行），其余槽与队长技保持客户端自渲染；"
        f"覆盖行需要 V14 APK 的 {L.PANEL_OVERRIDE_V2}（缺补丁不崩，只是回落到自动文案）。",
        "能力 6 #0：rework1 加 CT15s（c35=900）。这一行的触发方 puller c28='0' ＝**自身**发动技能，"
        "不是「队伍中任一角色」——作者本轮只要求加 CT，触发方保持原样，面板文案已按实改写。",
        f"技能 DSL：设计稿 composed_tree 逐命令回到 {len(SHAPE_DONORS)} 棵官方 donor 树上核对"
        f"（允许改动下标白名单见 evidence/kit-gates.json），两档 tree[10]=0 保持技能伤害归属；"
        "写后回读比对。三相各 10 倍（＋档 10.4~12 带 alv 0.5~1.0，官方 CNA 带 alv 有 22 处先例）。",
        ("技能特效：已套用 B/pixel/nicola/fx_lut.json 换色，克隆 "
         + "、".join(f["dst_dir"] for f in families)
         if families else
         "技能特效：无 fx_lut.json ⇒ 不克隆，直接引用官方路径 "
         f"battle/effect/skill_unique/{TEMPLATE_CODE}/* 与 battle/effect/skill_unique/megumin/"
         "megumin_explosion（零图集增量，裁决 §4／框架 §10.3）。像素代理交付 LUT 后重跑 "
         "--step kit 会自动改成克隆 + 染色。"),
        "语音：kind 3 ChangeSkillFlag ← 能力1 #1 的 536（主位 + 火共鸣时播 matched_skill_ready）。",
        {"pixel_install": pixel},
    ]

    deviations = [
        {"want": "design/nicola.json identity.status_donor：kit 里用 ★5 火属性 donor 111177 "
                 "覆盖 character_status（母本 211020 是 ★4，Lv100 会停在 3320/674）",
         "got": "kit 不碰 character_status —— 框架 `MAPack.template_raw` 已在 --step tables 自动把 "
                "★4 母本的 character_status 换成同 pf 类型的官方 ★5 donor 111153 flame_blessgirl"
                "（Lv100 4059/799，框架 §6/§11 实跑核对过）",
         "why": "同一张表两处改会互相覆盖；框架的 donor 选取规则可复算（median_donor）且被 "
                "--step check 的 rarity 字段持续复核，kit 再写一遍只会让两边漂移"},
        {"want": "design/nicola.json plan.skills.tree_plan_*：ダミー演出 ShowEffect 第 10 位写 false",
         "got": "按官方 donor 原值恢复成 true（母本 rare4/sorceress_teacher 的 _1/_2 两棵树都是 true；"
                "同树的「全体演出」才是 false）",
         "why": "设计稿没有给改动理由，两个演出的这一位在官方树里本来就不同值 ⇒ 判定为转录误差；"
                "「donor + 逐格改」只改有理由改的格（裁决 §6）。设计稿已同步改回"},
        {"want": "design/nicola.json plan.skills.effects_clone：目标目录直接是 "
                 f"battle/effect/skill_unique/{CODE}/，basename 改名成 {CODE}_* / moon_phase_*",
         "got": f"不改色时**不克隆**，DSL 直接引用官方 {TEMPLATE_CODE}/megumin 路径；要改色时 "
                "clone_effect_family(layout='codename') 落在 "
                f"battle/effect/skill_unique/{CODE}/<lecture|moon_phase>/，basename 保留官方前缀，"
                "引用统一由 rewrite_effect_refs 改写",
         "why": "裁决 §4／框架 §10.3「只引用不改色的官方特效直接引用官方路径，不要复制」；"
                "框架的 codename 布局不支持「目标即角色根目录、basename 改名」"
                "（同批 magnus/mia 已撞过同一限制）。只是路径命名差异，不影响引用正确性"},
        {"want": "design/nicola.json plan.skills.atlas_estimate：moon_phase 子集重打后 ≈0.14 Mpx",
         "got": "clone_effect_family 不重打图集 —— 它整张复制 donor sheet（megumin 247×853 ≈0.21 Mpx）"
                "并只改 atlas 的目录前缀；只有改色时才有这份增量，不改色时增量为 0",
         "why": "框架既有实现（wf_seasonal7_common.clone_effect_family）；即便克隆，单角色合计仍 "
                "≈0.43 Mpx ≈2.6%，低于裁决 §6 的 3.5% 通过线"},
        {"want": "design/nicola.json plan.skills.tree_plan_common.validation：ShowEffect(AB, Some) 的"
                 "官方样本是 pirates_gunner_1",
         "got": "官方实际路径是 battle/action/skill/action/rare4/pirates_gunner$pirates_gunner_1"
                "（rare5 下没有这个角色），本 kit 的 donor 闸门用的就是 rare4 这棵",
         "why": "实读 WF_PATHLIST_recovered.txt 与官方归档核实；设计稿已补上完整路径"},
        # ---- rework1（2026-09-21）
        {"want": "rework1 面板③「火属性角色对处于抗性降低状态的敌人技能伤害 +300%」",
         "got": f"IC 550 ResistanceRedDownSkillSlayer 300%（能力 3 #7），donor 取同族攻击版 "
                "1110816#L1 逐格改",
         "why": "官方 550/552/554 共 0 行（研究卡 B §6.6 零先例），攻击版 503/505/507 有 8 行。"
                "枚举在表里存在、行也过 wf_client_legality，但没有官方行证明客户端真的结算 ⇒ "
                "需真机对降抗敌人测技能伤害比；不生效就删这一行并把技伤并进 R6 的攻击特攻"},
        {"want": "rework1 面板②「除自身外的火属性角色发动技能时……使该角色……」",
         "got": "触发 puller 4(OneOfExceptMyself) + 组 Red，内容 target 7(TriggerPuller)；"
                "四条受益行 + 525 消耗行同形",
         "why": "puller4×t7 有 3 行官方先例（1510141#L1 就是 I23+White+puller4+t7），t7 侧 "
                "IC 211/32 各有先例；但 puller4 × t7 × 211/32/245/35/525 的具体组合是新的 ⇒ "
                "真机看只有放技能的那一个队友吃到 buff；不成立就退回 puller 5（含自身）并改面板"},
        {"want": "能力 3 整槽的面板文案逐行等于 rework1/panel/nicola.json",
         "got": f"整槽走 {CAS_OVERRIDE}（4 行），required_capabilities 多一项 "
                f"{L.PANEL_OVERRIDE_V2}",
         "why": "9 条记录的客户端自动文案会写成「状态固有 100%×1次」「2号位技能槽」这类引擎术语；"
                "覆盖行是惰性的，缺 V14 APK 不崩，只是回落到自动文案"},
        {"want": "IC 461 与本键的 c2 雕像组一致",
         "got": "整键 c2=action_skill（461 的官方 c2 只有 condition/attack_common/attack_yellow/special）",
         "why": "裁决 §8 要求 c2 每键单值，槽 3 其余 8 条（211/32/245/35/525/503/550/694）里 "
                "action_skill 都有先例；c2 只决定词条图标分类、不参与解析 ⇒ 最坏是图标分类别扭"},
        {"want": "能力 3 一键 9 条记录",
         "got": "照写（官方单键最多 6 条，live 最多 9 条 —— 杰拉德队长 9 行是先例）",
         "why": "四条受益 + 消耗 + 加层 + 两条特攻 + 独立乘区，kind 互不相同 ⇒ 无法合并；"
                "超了就把自身两条（245/35）挪到能力 1 或 5"},
        {"want": "rework1 面板②后半「自身技能槽上限 +5%」",
         "got": "照写（IC 245）",
         "why": "改版前的设计稿明确不做 245，理由是抬高自己的槽上限会拖慢触发 24 的满月节奏；"
                "作者本轮原话要求，按作者执行并在此登记这条设计张力"},
        # ---- rework1 第二轮（2026-09-21，真机反馈）
        {"want": "能力 3 整键主位限制（c1 全键 false），desc_override 4 行应显示主位限制图标",
         "got": f"write_strings 给 {CAS_OVERRIDE} 每行自动加 MAIN_ICON（{MAIN_ICON!r}）前缀，"
                "格式逐字照抄玛格诺斯 desc_override_lion_swordman_moon_3 的实际写法；不写字面「Ⓜ」字符",
         "why": "作者真机反馈：妮可拉能力 3 整键主位限制但覆盖串 4 行都没带这段前缀，游戏里看不到 Ⓜ；"
                "design/nicola.json 与 rework1/panel/nicola.json 的原文只登记文案本身，"
                "图标前缀是面板覆盖串的格式细节，按裁决只在生成覆盖串时补上，不改设计稿文案"},
    ]
    for entry in design.get("deviations", ()):
        deviations.append({"want": entry.get("item") or entry.get("want"),
                           "got": entry.get("actual") or entry.get("got"),
                           "why": entry.get("why")})

    gate = {"leader_rows": len(leader_evidence), "ability_records": len(ability_evidence),
            "programs": len(programs), "effect_families": [f["dst_dir"] for f in families],
            "fx_lut_present": transform is not None,
            "unique_condition": unique_key, "unique_icon": icon["logical"],
            "pixel_present": pixel["present"],
            "pixel_missing": [e["logical"] for e in pixel["skipped"]]}
    ready = pixel["present"] and not pixel["skipped"]
    gate["reason"] = "kit 自有产物全部过闸" if ready else \
        f"像素成品未就绪：{gate['pixel_missing'] or 'B/pixel/nicola/install.json 不存在'}"

    return KL.report(
        ctx, summary="妮可拉：火属性技伤辅助（满月轴——自身技能槽充满驱动的全队技伤/攻击增益 + "
                     "三相月技能，末段挂攻击降低·火抗降低·驱散 1；rework1 起能力 3 改成"
                     "「月讲」层数轴：自己充满槽攒层、队友放技能消耗层换取该队友的槽与攻击力）",
        status=KL.READY if ready else KL.DRAFT, panel=panel, notes=notes, programs=programs,
        required_capabilities=sorted(capabilities | set(SPEC["required_capabilities"])),
        deviations=deviations,
        unique_condition={unique_key: {"name": unique_row[1], "icon": UC_ICON_LOGICAL,
                                       "duration_frames": int(unique_row[3]),
                                       "cap": int(unique_row[4])}},
        extra={"custom_ability_string": sorted(cas_plan),
               "effect_families": [f["dst_dir"] for f in families],
               "kit_gate": gate, "voice_route": route,
               "unique_conditions": [unique_key],
               "unique_icon": icon})
