# -*- coding: utf-8 -*-
"""季节换装 kit：斩铁·白梅（159998 ``samurai_robot_plum``，光/剑士/Attacker，表母本 151117）。

设计真源：``work/character_packs/seasonal7-20260916/design/zantetsu.json``（status=final）；
**行清单与技能 DSL 的现行真源是改版施工单** ``…/revision-20260916/zantetsu/plan.json``
（作者 2026-09-16 真机试玩后的一轮要求），design 只再提供 identity / text 骨架 / effects / energy。
本模块按设计逐行回放 donor 行 + 列级 edits（donor 取官方基线 1.4.54，live 自制行取 live；
live 行被别的单元改掉的钉成冻结行，见 :data:`FROZEN_DONORS`），
逐格断言与设计 ``row_final`` 相同后落包；两棵技能树从官方 131044 + 151117 两棵树重新拼装
（不直接吃设计里的 composed_tree，只拿它做逐节点对照），并自行复跑静态门禁。

主控拍板覆盖（优先于设计文件）：
- 词条槽 4 第 1 条的 112（全表零先例）不上，改用设计预置退路 F1：507「自身 光属性抗性降低中的
  敌人 攻击特攻 60%→120%」（``fallbacks.slot4_rec1_if_112_fails__F1_507``），面板文案随之调整。
- 设计里「需要作者拍板」的项一律取设计默认值（c27=自身、语音路由 kind3、旧版小人造型照用）。

写入边界：只写 ``work/character_packs/s7-zantetsu/`` 与 ``seasonal7-20260916/impl/zantetsu/``；
不发布、不重锚、不写 live store / assets / .cdn / src。

用法（Integrate / 发布前固定顺序）::

    python mod-tools/wf_seasonal7_build.py --char zantetsu --step tables,kit,assets,manifest,status,inspect
    python mod-tools/wf_seasonal7_kit_zantetsu.py gates     # 离线门禁 → impl/zantetsu/gates.json；
                                                           # 全过才把 kit-report 置 ready-for-review
    python mod-tools/wf_seasonal7_build.py --char zantetsu --step manifest,status   # 刷新 manifest 快照
    python mod-tools/wf_seasonal7_kit_zantetsu.py gates     # preflight/publish 前最后一次，必须 all_pass

``gates`` 的三个结论字段（角色上线后才会分家，见 ``foreign_shadow_conflicts``）::

    blocking_failures  本角色自己的红项；必须为空。``all_pass`` 就是它为空。
    deferred           唯一可延后的一类：批次级 live 漂移（包内共享表全表载荷在**别家键**上
                       落后于链尾）。主控发布步序 preflight → rebase → preflight → publish
                       的 rebase 一步清零；只要有一条冲突碰到自家键就不会进这里，仍然是阻塞项。
    publishable_now    连 deferred 也为空才为真（即 rebase 之后）。别拿 all_pass 当"可以直接发"。

- ``kit`` 必须排在 ``tables`` 之后：框架 tables 每次都按母本 151117 重写 character_stance_detail
  （``,1,1,1,,1,1,1``），kit 才能写回设计值 ``,1,"1,5",1,,1,"1,5",1``。单独重跑 tables 后必须再跑 kit；
  manifest/status/inspect 看不出这一行，只有本模块 ``gates`` 能拦（stance_detail + 指纹逐项差异）。
- 像素或特效任一重跑：像素定稿 → ``fx/zantetsu`` 下 ``python fx_recolor_zantetsu.py gate`` → ``--step kit`` → ``gates``。
  ``gates`` 的 doll_colors 门禁逐色核对特效 sheet 小人帧与像素小人（pixel/out 与包内已装像素）同色。

Integrate（媒体整合，幂等）：
- 特效：fx manifest 存在时经 ``png_transform`` 克隆，再把 sheet 改写为染色 PNG 的**存储态原字节**
  （框架 ``png_store_bytes`` 会 PIL 重编码，像素相同但 sha 不同），包内 sha = 染色产物存储态 sha。
- 像素：``pixel/REVIEW.md`` 修复轮复核 PASS + verify/report 门禁全过 + sha 一致时，``build`` 把
  ``pixel/zantetsu/out`` 两张 sheet 以存储态写入 ``character/<code>/pixelart/``（owner=pixel），元数据保持母本。
- 语音：kit 不写。主控 ``wf_seasonal7_voice.py pack … --write --apply-tables --replace`` 后跑
  ``python work/character_packs/seasonal7-20260916/impl/zantetsu/voice_merge.py``（并认领 / 登记 / 删母本旧语音 / CV / 镜像）。
  ``--step assets`` 会按母本清单把旧 home 语音补回，之后须再跑 voice_merge。``gates`` 要求像素已装、语音已装。
  固定顺序：``tables → kit → assets → (voice pack → voice_merge) → manifest → status → inspect → gates``。
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import sys
import zlib
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    pass  # Imports resolve from this checkout/package, not external source copies.

KEY = "zantetsu"
CID = "159998"
CODE = "samurai_robot_plum"
ELEMENT = 4                                   # 光（character c3，0 基）
BATCH_REL = "work/character_packs/seasonal7-20260916"
DESIGN_REL = f"{BATCH_REL}/design/zantetsu.json"
IMPL_REL = f"{BATCH_REL}/impl/zantetsu"
FX_MANIFEST_REL = f"{BATCH_REL}/fx/zantetsu/out/manifest.json"
FX_REPORT_REL = f"{BATCH_REL}/fx/zantetsu/out/report.json"        # Effects 阶段报告：小人 LUT 来源 + 像素依赖 sha
FX_ANALYSIS_REL = f"{BATCH_REL}/fx/zantetsu/analysis.json"         # Effects 阶段 rect 分类（doll / group / keep）
PIXEL_REPORT_REL = f"{BATCH_REL}/pixel/zantetsu/report.json"
PIXEL_OUT_REL = f"{BATCH_REL}/pixel/zantetsu/out"
PIXEL_SHEETS = ("sprite_sheet", "special_sprite_sheet")
PIXEL_SHEET = "character/{code}/pixelart/{name}.png"
PIXEL_REVIEW_REL = f"{BATCH_REL}/pixel/REVIEW.md"                  # 末尾「修复轮复核」段为现行结论
PIXEL_REVIEW_HEADING = "修复轮复核"
PIXEL_VERIFY_REL = f"{BATCH_REL}/pixel/zantetsu/verify.json"
PIXEL_VERIFY_ALL_REL = f"{BATCH_REL}/pixel/_review/verify_all.json"
# sheet 基名 → 同组元数据（atlas / frame / timeline）：元数据保持母本（assets 只改 character/<code>/ 前缀）
PIXEL_METADATA = {
    "sprite_sheet": ("sprite_sheet.atlas.amf3.deflate", "pixelart.frame.amf3.deflate", "pixelart.timeline.amf3.deflate"),
    "special_sprite_sheet": ("special_sprite_sheet.atlas.amf3.deflate", "special.frame.amf3.deflate",
                             "special.timeline.amf3.deflate"),
}
SPEECH = "master/character/character_speech.orderedmap"
DOLL_KEEP = frozenset({"000000", "FFFFFF", "252525"})             # 像素管线 protected / fx DOLL_KEEP：保持原色
OFFICIAL_SIG_REL = f"{BATCH_REL}/research/_tmp/official_sig.json"
PROPOSAL_REL = f"{BATCH_REL}/design/_tmp/zantetsu/proposal_tree_{{level}}.json"

ABILITY = "master/ability/ability.orderedmap"
LEADER = "master/ability/leader_ability.orderedmap"
CHAR = "master/character/character.orderedmap"
TEXT = "master/character/character_text.orderedmap"
ACTION = "master/skill/action_skill.orderedmap"
SWITCHED = "master/skill/switched_action_skill.orderedmap"
CAS = "master/string/custom_ability_string.orderedmap"
UPSKILL = "master/mana_board/upskill.orderedmap"
STANCE = "master/stance_detail/character_stance_detail.orderedmap"
PREVIEW = f"character/{CODE}/battle/character_detail_skill_preview.battle.amf3.deflate"
TEMPLATE_PREVIEW = "character/samurai_robot_smr22/battle/character_detail_skill_preview.battle.amf3.deflate"
PREVIEW_END_FRAME = 420                       # 设计：新技能起跳→归还约 130 帧 + 60 帧 cutin；官方带内（420 有 3 例）

CAS_KEY = f"change_skill_{CODE}"
VOICE_READY = f"{CODE}_voice_ready"
ROUTE_COLS = ["3", "", "", "", "", VOICE_READY, "false", "false"]   # character c9–c16（kind 3 ChangeSkillFlag）
SLOT4_OVERRIDE = "slot4_rec1_if_112_fails__F1_507"
PF_CAS_KEY = f"ability_skill_{CODE}_pf"       # 改版：能力1#3 的 629 行 string_id（缺键=详情页 C8601）
CAS_KEYS = (CAS_KEY, PF_CAS_KEY)
REQUIRED_CAPABILITIES = ("kyubi-fever-ratio-v1",)

# ---- 改版 20260916（作者真机试玩后的一轮要求）：词条/队长行清单与技能 DSL 方案的真源是 revision plan，
# 不再是 design/zantetsu.json 的 leader/abilities/fallbacks 段（design 仍提供 identity/text/effects/energy）。
REVISION_REL = f"{BATCH_REL}/revision-20260916/zantetsu/plan.json"
REVISION_DSL_REL = f"{BATCH_REL}/revision-20260916/zantetsu/dsl_validated.json"   # 设计阶段探针的三棵树（特效改写前）
# ---- 改版 20260916 第二轮（作者第二次真机反馈）：只是对第一轮施工单的**增量**——新增 1 条队长行 +
# 两条面板文案规则的文案改写。第一轮的 plan.json 是只读历史证据，不改；这里单独放 plan2.json。
REVISION2_REL = f"{BATCH_REL}/revision2-20260916/zantetsu/plan2.json"
PF_DONOR_REL = f"{BATCH_REL}/research/_tmp/zehr_pf/knight_lv3.json"               # 官方剑士 PF Lv3（629 树母本）
PF_PROGRAM = f"battle/action/skill/action/rare5/{CODE}${CODE}_pf"
PF_LEVEL = "pf"                               # dsl_gates / EXPECTED_ENCODED_BYTES 里 PF 树的档位标识
# 三处 CreateNormalAttack 的定位：CreateHitArea 的 bind id → plan multipliers 的键名
REVISION_MULT_SLOTS = ((2, "落地连斩(每段,共4段)"), (5, "横斩"), (9, "一刀两断"))

DONOR_PROGRAM = "battle/action/skill/action/rare5/{code}${code}_{level}"
D2_CODE, D1_CODE = "samurai_robot", "samurai_robot_smr22"      # 131044 骨架 / 151117 一刀两断子树
SE_FROM = "sound_effect/water/se_water_stamp_heavy"
SE_TO = "sound_effect/slash/se_heavy_aura_critical"
HIT_TIMELINE_BASE = "samurai_robot_smr22_hit"
EXPECTED_ENCODED_BYTES = {1: 3542, 2: 3570, PF_LEVEL: 664}    # 改版后重算（落地时以实际编码长度为准）

# doll_lut：设计风险 8——smr22 族小人与像素小人是同一精灵，必须同一张映射（"pixel"）；
# 131044 族是旧版小人造型，单独一张 LUT（"separate"，按 fx 报告逐色来源核对）。
FAMILIES = (
    {"id": "S2_kanbai", "src_dir": "battle/effect/skill_unique/samurai_robot", "subdir": "kanbai", "doll_lut": "separate",
     "fx": ("samurai_robot_jump", "samurai_robot_land", "samurai_robot_land_slash", "samurai_robot_slash_finish")},
    {"id": "S1_ittou", "src_dir": "battle/effect/skill_unique/samurai_robot_smr22", "subdir": "ittou", "doll_lut": "pixel",
     "fx": ("samurai_robot_smr22_dot_front", "samurai_robot_smr22_dot_back", "samurai_robot_smr22_slash",
            HIT_TIMELINE_BASE)},
)

# ---- 框架 spec 覆盖（tables 重跑时生效；值与设计 text 段逐字一致，build 时断言）
TEXTS = {
    "name": "斩铁",
    "furigana": "ZHANTIE",
    "title": "白梅羽织的忍者武士",
    "profile": "早春时节，斩铁换上绣满白梅的羽织，系好青绿围巾，手里还拿着一串三色团子。"
               "他最爱坐在石栏上陪同伴赏梅，把落在机体上的花瓣当作勋章。寒梅傲然绽放——在下之剑，亦为守护这份温暖而鸣！",
    "leader": "寒梅武士道、比肩忍道",
    # 改版：作者要求「角色技能描述不再写太复杂省略一下」（80 字 → 41 字，两档同文）
    "skill1": "超振动斩铁剑·寒梅一闪",
    "desc1": "跃向敌人连斩，对周围的敌人造成光属性伤害并赋予光属性抗性降低效果，最后以一刀两断收尾",
    "skill2": "超振动斩铁剑·寒梅一闪＋",
    "desc2": "跃向敌人连斩，对周围的敌人造成光属性伤害并赋予光属性抗性降低效果，最后以一刀两断收尾",
    "cv": "AI 合成配音",
}
SPEC = {
    "required_capabilities": REQUIRED_CAPABILITIES,
    "extra_keys": {CAS: CAS_KEYS, SWITCHED: (VOICE_READY,)},
}

KIT_TABLE_KEYS = {           # kit 拥有的表键（指纹与认领核对用）
    ABILITY: tuple(f"{CID}{i}" for i in range(1, 7)),
    LEADER: (CID,), CHAR: (CID,), TEXT: (CID,), CAS: CAS_KEYS, UPSKILL: (CID,), STANCE: (CID,),
}
KIT_NESTED_KEYS = {ACTION: CODE, SWITCHED: VOICE_READY}


class KitError(RuntimeError):
    pass


def kit_source_sha256() -> str:
    """门禁结果绑定 kit 源码：改了门禁/拼装逻辑后旧 gates.json 不能继续放行。"""
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


# ======================================================================== 通用小工具

def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=1, sort_keys=False) + "\n"


def load_design(root: Path) -> dict:
    design = json.loads((root / DESIGN_REL).read_text(encoding="utf-8"))
    ident = design.get("identity") or {}
    if design.get("status") != "final" or design.get("key") != KEY:
        raise KitError(f"design not final or wrong key: {design.get('status')} {design.get('key')}")
    if (str(ident.get("cid")), ident.get("code"), ident.get("element")) != (CID, CODE, ELEMENT):
        raise KitError(f"design identity mismatch: {ident.get('cid')} {ident.get('code')} {ident.get('element')}")
    if design.get("pf_override") is not None or design.get("dash") is not None:
        raise KitError("design now carries a PF/dash override that this kit does not implement")
    return design


TEXT_PLAN_KEY = "action_skill c1 / character_text c5,c7"


def load_revision(root: Path) -> dict:
    """改版施工单（本轮真源）：词条/队长逐行 donor+edits+row_final、技能 DSL delta、新 629 PF 树、文案改写。"""
    plan = json.loads((root / REVISION_REL).read_text(encoding="utf-8"))
    if plan.get("schema") != "seasonal7-revision-plan/1":
        raise KitError(f"unknown revision plan schema {plan.get('schema')!r}")
    if (plan.get("key"), str(plan.get("cid")), plan.get("code"), plan.get("element")) != (KEY, CID, CODE, ELEMENT):
        raise KitError(f"revision plan identity mismatch: {plan.get('key')} {plan.get('cid')} {plan.get('code')}")
    for table in (LEADER, ABILITY):
        if table not in plan["tables"]:
            raise KitError(f"revision plan lacks {table}")
    if plan["skill_dsl"]["new_program"]["path"] != PF_PROGRAM:
        raise KitError("revision plan PF program path differs from kit constant")
    return apply_revision2(plan, load_revision2(root))


def load_revision2(root: Path) -> dict:
    """第二轮增量施工单。第一轮的 plan.json 只读，新增/改写全部走这里。"""
    plan2 = json.loads((root / REVISION2_REL).read_text(encoding="utf-8"))
    if plan2.get("schema") != "seasonal7-revision2-plan/1":
        raise KitError(f"unknown revision2 plan schema {plan2.get('schema')!r}")
    if (plan2.get("key"), str(plan2.get("cid")), plan2.get("code"), plan2.get("element")) != (KEY, CID, CODE, ELEMENT):
        raise KitError(f"revision2 plan identity mismatch: {plan2.get('key')} {plan2.get('cid')} {plan2.get('code')}")
    if LEADER not in plan2["tables"]:
        raise KitError(f"revision2 plan lacks {LEADER}")
    return plan2


def apply_revision2(plan: dict, plan2: dict) -> dict:
    """把第二轮的队长新增行插进第一轮施工单（就地改副本），并把第二轮文案挂到 ``plan['revision2']``。

    插入位置用 ``after_id``/``before_id`` 双锚定：第一轮的记录顺序漂了立刻停，而不是默默插错地方。"""
    plan = copy.deepcopy(plan)
    lead, lead2 = plan["tables"][LEADER], plan2["tables"][LEADER]
    if lead["key"] != lead2["key"]:
        raise KitError(f"revision2 leader key {lead2['key']} != revision1 {lead['key']}")
    if lead["record_count_new"] != lead2["record_count_old"]:
        raise KitError(f"revision2 record_count_old {lead2['record_count_old']} "
                       f"!= revision1 record_count_new {lead['record_count_new']}")
    apply_donor_retargets(plan, plan2.get("donor_retargets") or [])
    for ins in lead2["inserts"]:
        pos = int(ins["position"])                       # 1-based：新行插完后所处的名次
        records = lead["records"]
        if not 1 <= pos <= len(records) + 1:
            raise KitError(f"revision2 insert position {pos} out of range (1..{len(records) + 1})")
        before = records[pos - 2]["id"] if pos >= 2 else None
        after = records[pos - 1]["id"] if pos - 1 < len(records) else None
        if (before, after) != (ins.get("after_id"), ins.get("before_id")):
            raise KitError(f"revision2 insert anchors drifted: got ({before}, {after}), "
                           f"plan says ({ins.get('after_id')}, {ins.get('before_id')})")
        if ins["record"]["id"] in {r["id"] for r in records}:
            raise KitError(f"revision2 insert id {ins['record']['id']} already in revision1 records")
        records.insert(pos - 1, ins["record"])
    lead["record_count_new"] = lead2["record_count_new"]
    if len(lead["records"]) != lead["record_count_new"]:
        raise KitError(f"revision2 leader records {len(lead['records'])} != record_count_new "
                       f"{lead['record_count_new']}")
    plan["revision2"] = plan2
    return plan


def apply_revision_texts(design: dict, plan: dict) -> dict:
    """把改版的文案改写盖到设计上（就地改副本）：技能说明简化 + 两个 custom_ability_string。

    设计文件属于上一轮、本轮不改，所以 build/gates 都先做这一步再往下走；每处都断言旧值与
    plan 的 ``old`` 一致，设计漂了立刻停。"""
    design = copy.deepcopy(design)
    desc = plan["texts"][TEXT_PLAN_KEY]
    text = design["text"]
    for field in ("skill1_desc", "skill2_desc"):
        if text[field] != desc["old"]:
            raise KitError(f"design {field} != revision plan old text")
        text[field] = desc["new"]
    row = list(text["character_text_row"])
    for col in (5, 7):
        if row[col] != desc["old"]:
            raise KitError(f"design character_text c{col} != revision plan old text")
        row[col] = desc["new"]
    text["character_text_row"] = row
    for level in ("1", "2"):
        inner = design["skills"]["action_skill_rows"][f"inner_{level}"]
        if inner["1"] != desc["old"]:
            raise KitError(f"design action_skill inner_{level} c1 != revision plan old text")
        inner["1"] = desc["new"]
    cas_plan = plan["texts"]["custom_ability_string"]
    if sorted(cas_plan) != sorted(CAS_KEYS):
        raise KitError(f"revision plan custom strings {sorted(cas_plan)} != {sorted(CAS_KEYS)}")
    existing = {c["key"]: c for c in design["custom_strings"] if c["table"] == CAS}
    if sorted(existing) != [CAS_KEY]:
        raise KitError(f"design custom strings {sorted(existing)} != [{CAS_KEY}]")
    if existing[CAS_KEY]["value"] != cas_plan[CAS_KEY]["old"]:
        raise KitError("design custom_ability_string value != revision plan old text")
    existing[CAS_KEY]["value"] = cas_plan[CAS_KEY]["new"]
    if cas_plan[PF_CAS_KEY]["old"] is not None:
        raise KitError("revision plan marks the PF string as pre-existing")
    design["custom_strings"].append({"table": CAS, "key": PF_CAS_KEY, "value": cas_plan[PF_CAS_KEY]["new"],
                                     "why": cas_plan[PF_CAS_KEY]["reason"]})
    apply_revision2_texts(design, plan.get("revision2") or {})
    problems = text_rule_problems(design)
    if problems:
        raise KitError("面板文案规则（作者 2026-09-16 晚补充）不通过：" + "；".join(problems))
    return design


def apply_revision2_texts(design: dict, plan2: dict) -> None:
    """第二轮文案改写（就地改 design 副本）：每处都断言旧值＝第一轮改完的值，漂了立刻停。"""
    for key, spec in ((plan2.get("texts") or {}).get("custom_ability_string") or {}).items():
        entry = next((c for c in design["custom_strings"] if c["table"] == CAS and c["key"] == key), None)
        if entry is None:
            raise KitError(f"revision2 rewrites unknown custom_ability_string {key!r}")
        if entry["value"] != spec["old"]:
            raise KitError(f"custom_ability_string {key} = {entry['value']!r} != revision2 old text")
        entry["value"] = spec["new"]
        entry["why"] = spec["reason"]


# ---- 面板文案规则（作者 2026-09-16 晚补充件，优先级高于此前任何写法）
#   规则 1：没有上限就什么都不写——面板禁止出现「无上限」及其替代说法；有上限的才写上限。
#   规则 2：能力里由 ChangeSkillFlag(536/704) 驱动的「强化技能效果」条目只写强化了什么，不写数值、不写秒数。
# 客户端侧佐证：ui_string 里唯一的上限串是 ability_description_instant_trigger_limit_n_times
#   =「（上限 ::count:: 次）」，trigger_limit 写 (None) 时什么都不渲染 ⇒ 规则 1 只约束我们自己写的文案。
TEXT_RULE_BANNED = ("无上限", "无限叠加", "可无限", "上不封顶")
SKILL_BOOST_CAS_KEYS = (CAS_KEY,)          # 536 ChangeSkillFlag 条目的文案键（629 的不算「技能强化」条目）


def player_visible_texts(design: dict) -> dict[str, str]:
    """玩家在客户端能看到的本角色文案全集（文案规则的检查面）。"""
    text = design["text"]
    out = {f"text.{k}": text[k] for k in ("name", "nickname", "profile", "leader_name",
                                          "skill1_name", "skill1_desc", "skill2_name", "skill2_desc")}
    for i, cell in enumerate(text["character_text_row"]):
        out[f"character_text.c{i}"] = cell
    for level in ("1", "2"):
        out[f"action_skill.inner_{level}.c1"] = design["skills"]["action_skill_rows"][f"inner_{level}"]["1"]
    for entry in design["custom_strings"]:
        if entry["table"] == CAS:
            out[f"custom_ability_string.{entry['key']}"] = entry["value"]
    return out


def text_rule_problems(design: dict) -> list[str]:
    problems: list[str] = []
    for where, value in player_visible_texts(design).items():
        for banned in TEXT_RULE_BANNED:
            if banned in str(value):
                problems.append(f"规则1：{where} 含禁用词 {banned!r}（没有上限就写到效果为止）")
    strings = {e["key"]: e["value"] for e in design["custom_strings"] if e["table"] == CAS}
    for key in SKILL_BOOST_CAS_KEYS:
        value = strings.get(key)
        if value is None:
            problems.append(f"规则2：缺少技能强化文案键 {key}")
            continue
        if any(ch.isdigit() for ch in value):
            problems.append(f"规则2：{key} 含数字（技能强化条目只写强化了什么）：{value!r}")
        if "秒" in value:
            problems.append(f"规则2：{key} 含「秒」（技能强化条目不写持续时间）：{value!r}")
    return problems


def load_revised_design(root: Path) -> tuple[dict, dict]:
    plan = load_revision(root)
    return apply_revision_texts(load_design(root), plan), plan


def _slv(a, b=None):
    return [{"min": a, "max": a if b is None else b}]


def _find_cmds(tree, name=None) -> list[list]:
    out: list[list] = []

    def walk(node):
        if isinstance(node, list):
            if (node and node[0] in ("Command", "Event") and len(node) > 1 and isinstance(node[1], list)
                    and node[1] and (name is None or node[1][0] == name)):
                out.append(node[1])
            for child in node:
                walk(child)
    walk(tree)
    return out


def _one(tree, name, pred=lambda a: True) -> list:
    found = [a for a in _find_cmds(tree, name) if pred(a)]
    if len(found) != 1:
        raise KitError(f"expected exactly one {name}, found {len(found)}")
    return found[0]


def _cmd(node: list) -> list:
    if not (isinstance(node, list) and node and node[0] in ("Command", "Event")):
        raise KitError(f"not a Command/Event node: {str(node)[:80]}")
    return node[1]


# ======================================================================== 行（词条/队长）

class _Donors:
    """donor 表缓存：official=官方基线（1.4.54），live=live store 只读。"""

    def __init__(self, ctx) -> None:
        self.ctx = ctx
        self._cache: dict[tuple[str, str], dict[str, str]] = {}

    def rows(self, source: str, kind: str, key: str) -> list[list[str]]:
        logical = LEADER if kind == "leader_ability" else ABILITY
        cache_key = (source, logical)
        if cache_key not in self._cache:
            if source == "official":
                self._cache[cache_key] = self.ctx.official_flat(logical)
            elif source == "live":
                self._cache[cache_key] = self.ctx.live_flat(logical)
            else:
                raise KitError(f"unknown donor source {source}")
        return self.ctx.csv_split(self._cache[cache_key][key])


# 2026-09-27 冻结 donor（泳装希尔媞 149996 在 1.4.1054 换成灰服版）：plan.json
# /tables/ability/keys/1599983/records[3]（A3#4「光共鸣：每 250 连击 → 自身技能伤害独立乘区 5%→10%」）
# 的 donor 是泳装希尔媞能力3 在 live 的第 1 行（694 行）。灰服版换掉了整个 1499963：第 1 行不再是
# 694 行，c27 等列都变了 ⇒ 按行号取，edits_before 对不上（KitError）。plan.json 是第一轮证据（只读），
# 所以在 kit 里把这个 donor 钉成 1.4.1054 发布前的 live 行（extra4/before 快照，= live 1.4.1053）：
# 回放不读 live，按下表还原整行并核对 sha256（= csv 单行文本），发布前后回放结果逐字相同。
# 键 = (donor_source, 表, donor_key, row_index)，即 plan 记录的四个 donor 字段；值只列非空格。
FROZEN_DONORS: dict[tuple[str, str, str, int], dict[str, Any]] = {
    ("live", "ability", "1499963", 1): {
        "frozen_from": "live 1.4.1053，泳装希尔媞灰服版（1.4.1054）替换前",
        "width": 126,
        "cells": {0: "wind_spgirl_swim_3", 1: "true", 2: "attack_green", 3: "0", 5: "0", 6: "202",
                  13: "0", 20: "0", 27: "12", 30: "7700000", 31: "7700000", 34: "5", 35: "0",
                  39: "(None)", 46: "0", 47: "694", 48: "0", 51: "2500", 52: "2500"},
        "sha256": "4ef336b15ba8241f51f8c5676568d664865f43d73f4ac91c49f067d228ea78ac",
    },
}


def donor_pin(rec: dict, kind: str) -> tuple[str, str, str, Any]:
    """plan 记录的 donor 定位四元组（:data:`FROZEN_DONORS` 的键形）。"""
    return rec["donor_source"], kind, rec["donor_key"], rec["row_index"]


def frozen_donor_row(spec: dict[str, Any], donor: str) -> list[str]:
    """由 :data:`FROZEN_DONORS` 的一项还原整行；sha256 不符即 KitError（冻结行被改动）。"""
    import wf_mod_tool as core
    row = [""] * spec["width"]
    for col, value in spec["cells"].items():
        row[col] = value
    got = _sha(core.write_csv_lines([row]).rstrip("\n").encode("utf-8"))
    if got != spec["sha256"]:
        raise KitError(f"frozen donor {donor} sha256 {got} != pin {spec['sha256']}")
    return row


def donor_evidence(rec: dict, kind: str) -> dict[str, str]:
    """证据里标明冻结 donor（donor 字符串仍写 plan 原文）。"""
    spec = FROZEN_DONORS.get(donor_pin(rec, kind))
    return {"donor_frozen": f"{spec['frozen_from']}，sha256 {spec['sha256']}"} if spec else {}


def replay_row(donors: _Donors, rec: dict, kind: str) -> list[str]:
    """donor 行 + edits + copy_cells；断言 donor 原值（edits_before）与最终行（row_final）都和设计一致。

    ``row_index`` 写 ``"match_row_final"`` 时按内容在 donor 表里唯一定位（第一轮发布后自引用 donor 的
    行序会随每次发布顺延，序号写死会越发越错；这类记录 edits 为空，donor 本就等于 row_final）。
    :data:`FROZEN_DONORS` 里登记的 donor 不读表，用冻结行（edits_before / row_final 照样逐格核对）。"""
    frozen = FROZEN_DONORS.get(donor_pin(rec, kind))
    if frozen is not None:
        donor = frozen_donor_row(frozen, rec["donor"])
    elif rec["row_index"] == MATCH_ROW_FINAL:
        table = donors.rows(rec["donor_source"], kind, rec["donor_key"])
        matches = [r for r in table if r == rec["row_final"]]
        if len(matches) != 1:
            raise KitError(f"{rec['donor']}: match_row_final found {len(matches)} rows in "
                           f"{rec['donor_source']} {rec['donor_key']} (need exactly 1)")
        donor = matches[0]
    else:
        donor = donors.rows(rec["donor_source"], kind, rec["donor_key"])[rec["row_index"] - 1]
    row = list(donor)
    width = 124 if kind == "leader_ability" else 126
    if len(row) != width:
        raise KitError(f"{rec['donor']}: donor width {len(row)} != {width}")
    for col, before in (rec.get("edits_before") or {}).items():
        if row[int(col)] != before:
            raise KitError(f"{rec['donor']}: donor c{col}={row[int(col)]!r} drifted from design {before!r}")
    for mapping in (rec.get("edits") or {}, rec.get("copy_cells") or {}):
        for col, value in mapping.items():
            row[int(col)] = value
    if row != rec["row_final"]:
        diff = [i for i, (a, b) in enumerate(zip(row, rec["row_final"])) if a != b]
        raise KitError(f"{rec['donor']}: replayed row differs from design row_final at cols {diff[:10]}")
    return row


MATCH_ROW_FINAL = "match_row_final"


def _revision_record(rec: dict) -> dict:
    """plan 的记录形状 → ``replay_row`` 认的形状（plan 用 ``*_on_donor`` 后缀强调这是「对 donor 的改」）。"""
    return dict(rec, edits_before=rec.get("edits_before_on_donor") or {},
                edits=rec.get("edits_on_donor") or {})


def apply_donor_retargets(plan: dict, retargets: list[dict]) -> None:
    """就地重锚第一轮施工单里指向 **live 上本角色自己** 的 donor。

    第一轮已在 1.4.878 发布，那些 donor 现在读到的是第一轮的产物：行序顺延、``edits_before``
    （改动前的值）必然对不上。这里只改「去哪儿取 donor / donor 当前长什么样」，不改 ``row_final``；
    ``replay_row`` 仍然逐格比对 ``row_final``，锚错照样红。"""
    for spec in retargets:
        table = spec["table"]
        if table == LEADER:
            records = plan["tables"][LEADER]["records"]
        elif table == ABILITY:
            records = plan["tables"][ABILITY]["keys"][spec["key"]]["records"]
        else:
            raise KitError(f"donor retarget on unknown table {table!r}")
        rec = next((r for r in records if r["id"] == spec["record_id"]), None)
        if rec is None:
            raise KitError(f"donor retarget names unknown record {spec['record_id']!r}")
        if "row_index_new" in spec:
            if rec["row_index"] != spec["row_index_old"]:
                raise KitError(f"{spec['record_id']}: row_index {rec['row_index']} != retarget old "
                               f"{spec['row_index_old']}")
            rec["row_index"] = spec["row_index_new"]
        if "edits_before_on_donor_new" in spec:
            if rec.get("edits_before_on_donor") != spec["edits_before_on_donor_old"]:
                raise KitError(f"{spec['record_id']}: edits_before drifted from retarget old value")
            rec["edits_before_on_donor"] = spec["edits_before_on_donor_new"]


def revision_rows(ctx, plan: dict) -> dict[str, Any]:
    """按改版施工单回放 21 行（队长 6 + 词条 15）：donor 行 + 列级 edits，逐格对齐 plan 的 ``row_final``。

    与上一轮 ``design_rows`` 的差别：真源换成 revision plan；槽 4 第 1 条已经是 live 上线的 F1/507 行
    （donor 就是它自己），不再需要 ``SLOT4_OVERRIDE`` 分支。"""
    donors = _Donors(ctx)
    lead = plan["tables"][LEADER]
    if lead["key"] != CID or not lead["replace_whole_key"]:
        raise KitError("revision plan leader table does not replace the whole key")
    leader = [replay_row(donors, _revision_record(rec), "leader_ability") for rec in lead["records"]]
    if len(leader) != lead["record_count_new"] or len(leader) > RECORD_SANITY_CAP["leader_ability"]:
        raise KitError(f"leader record count {len(leader)} != plan record_count_new "
                       f"{lead['record_count_new']}（或超出安全上限 "
                       f"{RECORD_SANITY_CAP['leader_ability']}）")
    keys = plan["tables"][ABILITY]["keys"]
    if sorted(keys) != list(KIT_TABLE_KEYS[ABILITY]):
        raise KitError(f"revision plan ability keys {sorted(keys)} != {list(KIT_TABLE_KEYS[ABILITY])}")
    abilities: dict[str, list[list[str]]] = {}
    records: list[dict] = []
    for slot in range(1, 7):
        key = f"{CID}{slot}"
        entry = keys[key]
        rows = [replay_row(donors, _revision_record(rec), "ability") for rec in entry["records"]]
        if len(rows) != entry["record_count_new"] or not 1 <= len(rows) <= RECORD_SANITY_CAP["ability"]:
            raise KitError(f"{key}: record count {len(rows)} != plan record_count_new "
                           f"{entry['record_count_new']}（或超出安全上限 "
                           f"{RECORD_SANITY_CAP['ability']}）")
        if (rows[0][1], rows[0][2]) != (entry["unisonable_c1"], entry["statue_group_c2"]):
            raise KitError(f"{key} record1 unisonable/statue group != plan "
                           f"({rows[0][1]}/{rows[0][2]} vs {entry['unisonable_c1']}/{entry['statue_group_c2']})")
        for i, row in enumerate(rows[1:], 2):      # 一键内 c1/c2 必须一致，否则客户端按首条读、其余静默失效
            if (row[1], row[2]) != (rows[0][1], rows[0][2]):
                raise KitError(f"{key} record{i} c1/c2 {row[1]}/{row[2]} differs from record1")
        abilities[key] = rows
        records += [{"key": key, "record": i, "id": rec["id"], "donor": rec["donor"], "intent": rec["intent"],
                     **donor_evidence(rec, "ability")}
                    for i, rec in enumerate(entry["records"], 1)]
    if sum(len(v) for v in abilities.values()) != sum(k["record_count_new"] for k in keys.values()):
        raise KitError("ability record count differs from revision plan")
    return {"leader": leader, "abilities": abilities, "records": records,
            "leader_records": [{"record": i, "id": r["id"], "donor": r["donor"], "intent": r["intent"],
                                **donor_evidence(r, "leader_ability")}
                               for i, r in enumerate(lead["records"], 1)]}


def _block(kind: str) -> dict[str, int]:
    import wf_describe
    return {k: int(v) for k, v in wf_describe.layout(kind)["blocks"].items()}


# 记录数安全上限：**不是客户端上限**。客户端 MasterArray/AbilityLogic 全量遍历一键内所有记录，
# 没有行数硬上限（记忆卡 wf-ability-multirecord-rows 2026-08-26 纠偏；杰拉德 149999 的 9 行队长技已真机验证）。
# live 实测每键最大记录数：leader 15（169980）、ability 14（1699951/1499501）；官方基线 leader 最大 8。
# 这里只作「施工单写出离谱行数」的兜底，真正的记录数判据是 plan 的 record_count_new。
RECORD_SANITY_CAP = {"leader_ability": 20, "ability": 20}


PULLER_EMPTY_DURING = frozenset({"4", "30", "31", "136", "209"})
PULLER_ZERO_DURING = frozenset({"1", "9", "72"})


def row_gate(kind: str, row: list[str], cas_keys: set[str]) -> dict[str, Any]:
    import wf_client_legality as L
    import wf_describe
    blocks = _block(kind)
    mode = row[blocks["precondition1"] - 1]
    extra: list[str] = []
    if mode == "1":                           # 持续行：during puller 契约 + HP 恒真文案禁令
        trig = row[blocks["during_trigger"]]
        puller = row[blocks["during_trigger"] + 1]
        if trig in PULLER_EMPTY_DURING and puller != "":
            extra.append(f"during_trigger {trig} puller must be '' (got {puller!r})")
        if trig in PULLER_ZERO_DURING and puller != "0":
            extra.append(f"during_trigger {trig} puller must be '0' (got {puller!r})")
        if trig == "1":
            extra.append("during_trigger 1 (HpLow) is the banned constant-true HP text for this kit")
    else:
        content = row[blocks["instant_content"]]
        sid = row[blocks["instant_content"] + 23]
        if content in ("536", "629") and sid not in cas_keys:
            extra.append(f"instant {content} string id {sid!r} not in custom_ability_string (C8601)")
    return {
        "describe": wf_describe.describe_line(row, kind),
        "client_legality_problems": L.client_legality_problems(kind, row),
        "declared_block_field_problems": L.declared_block_field_problems(kind, row),
        "ability_element_column_problems": L.ability_element_column_problems(kind, row, ELEMENT),
        "invoke_skill_string_problems": L.invoke_skill_string_problems(row, frozenset(cas_keys), kind),
        "kit_row_problems": extra,
        "required_client_capabilities": L.required_client_capabilities(kind, row),
    }


def _row_gate_failed(entry: dict) -> bool:
    return any(entry[k] for k in ("client_legality_problems", "declared_block_field_problems",
                                  "ability_element_column_problems", "invoke_skill_string_problems",
                                  "kit_row_problems"))


# ======================================================================== 技能树

def compose_tree(A: list, B: list, level: int) -> list:
    """131044（A，骨架）+ 151117（B，一刀两断子树）→ 新技能树（特效路径仍指官方目录，
    之后统一走 rewrite_effect_refs）。步骤逐条对应 design skills.tree_plan_<level>.steps。"""
    T = copy.deepcopy(A)
    if not (T[0] == "ActionDsl" and T[1] == 1 and T[10] == 0):
        raise KitError("D2 root header drifted")
    T[1] = 2                                             # movementPriority 1→2（含 StopBall，与 smr22 一致）
    root = T[11][1]
    hide = _cmd(root[0])                                 # step 2
    if not (hide[0] == "HideCharacter" and hide[1] == -17 and hide[2] == 61):
        raise KitError(f"D2 HideCharacter drifted: {hide}")
    hide[2] = 130
    dummy = _cmd(root[1])                                # step 3
    if dummy[0] != "ShowEffect" or dummy[2] != ["ResolveByElement", "battle/effect/skill_general/decoration/dummy_ball", 3]:
        raise KitError("D2 dummy ball effect drifted")
    dummy[2][2] = 5
    if dummy[5] != ["SpecifyEffectLifetimeDirectly", 61]:
        raise KitError("D2 dummy ball lifetime drifted")
    dummy[5][1] = 130
    jump = _cmd(root[2])
    if not str(jump[2][1]).endswith(f"/{D2_CODE}/samurai_robot_jump"):
        raise KitError("D2 jump effect drifted")
    stop = copy.deepcopy(B[11][1][0])                    # step 1
    if not (_cmd(stop)[0] == "StopBall" and _cmd(stop)[1] == -18 and _cmd(stop)[2] == 45):
        raise KitError("D1 StopBall drifted")
    _cmd(stop)[2] = 93
    root.insert(0, stop)
    crp1 = _one(T, "CreateReferencePoint", lambda a: a[10] == 1)   # step 4
    if not (crp1[1] == 0 and crp1[9] == 60):
        raise KitError("D2 RP1 drifted")
    crp1[9] = 90
    land = _one(T, "CreateHitArea", lambda a: a[19] == 2)          # step 5
    if not (land[9] == ["Circle", _slv(100)] and land[14] == ["CalculatedUsingMaxNumOfHits", 4] and land[24] == 0):
        raise KitError("D2 landing hit area drifted")
    cna_land = _one(land[23], "CreateNormalAttack")
    if not (cna_land[1] == 4 and cna_land[2] == 255):
        raise KitError("D2 landing attack drifted")
    cna_land[6] = _slv(0.85) if level == 1 else _slv(1.08, 1.25)
    cc = _one(land[23], "CreateCondition")
    if not (cc[1] == 4 and cc[10] == 3 and cc[12] is False):
        raise KitError("D2 landing CreateCondition drifted")
    tol = cc[2][0]
    if not (tol[0] == "ACToleranceOfElement" and tol[2] == 3):
        raise KitError("D2 tolerance condition drifted")
    tol[2] = 5                                                      # 雷→光（DSL 码=内部+1）
    if tol[3] != (_slv(-0.1) if level == 1 else _slv(-0.15, -0.2)):
        raise KitError(f"D2 tolerance strength drifted: {tol[3]}")
    onhit = land[23][1]
    idx = [i for i, n in enumerate(onhit) if n[0] == "Command" and n[1] is cc]
    if len(idx) != 1:
        raise KitError("landing onHit CreateCondition not found as direct child")
    cc_on = copy.deepcopy(cc)
    cc_on[2][0][3] = _slv(-0.15) if level == 1 else _slv(-0.25, -0.3)
    # 光共鸣开关分支（蓝本 devil_clown_xm21）；两支都是非空 Block，禁 DoNothing
    onhit[idx[0]] = ["Command", ["ConditionalsChangeSkillFlag", 1,
                                 ["Block", [["Command", cc_on]]], ["Block", [["Command", cc]]]]]
    fin = _one(T, "CreateHitArea", lambda a: a[19] == 5)           # step 6
    if not (fin[9][0] == "Rectangle" and fin[24] == 0):
        raise KitError("D2 horizontal slash drifted")
    cna_fin = _one(fin[23], "CreateNormalAttack")
    if cna_fin[1] != 7:
        raise KitError("D2 horizontal slash attack drifted")
    cna_fin[6] = _slv(17) if level == 1 else _slv(21.6, 25)
    waits = [w for w in _find_cmds(T, "Wait") if w[1] == 19]       # step 7
    if len(waits) != 1:
        raise KitError("D2 Wait(19) not unique")
    w19 = waits[0]
    ret = w19[3][1][0]
    if not (_cmd(ret)[0] == "ShowEffect" and str(_cmd(ret)[2][1]).endswith(f"/{D2_CODE}/samurai_robot_land")):
        raise KitError("D2 return effect drifted")
    sub = copy.deepcopy(B[11][1][1])                                # step 8
    c = _cmd(sub)
    if not (c[0] == "CreateReferencePoint" and c[1] == -18 and c[10] == 0 and c[3] == 0 and c[4] == 0):
        raise KitError("D1 CreateReferencePoint drifted")
    remap = {0: 8, 1: 9, 2: 10, 3: 11}
    c[1] = 1                                   # 原点：球 → RP1（锁定敌人落点；敌人可能已死，不 lookup 绑定 0）
    c[4] = 300                                 # 敌人我方一侧 300px 起步，前冲 225 + 判定 v-75 → 圆心=锁定目标
    c[10] = remap[0]
    for se in _find_cmds(sub, "ShowEffect"):
        if se[3] in remap:
            se[3] = remap[se[3]]
    moves = _find_cmds(sub, "MoveHitArea")
    if len(moves) != 2 or any(m[1] != 0 for m in moves) or (moves[0][4], moves[1][4]) != (15, 0):
        raise KitError("D1 MoveHitArea drifted")
    for m in moves:
        m[1] = remap[0]
    big = _one(sub, "CreateHitArea")
    if not (big[2] == 0 and (big[19], big[21], big[22]) == (1, 2, 3)):
        raise KitError("D1 big slash hit area drifted")
    big[2] = remap[0]
    big[19], big[21], big[22] = remap[1], remap[2], remap[3]
    cna_big = _one(big[23], "CreateNormalAttack")
    if cna_big[1] != 3:
        raise KitError("D1 big slash attack drifted")
    cna_big[1] = remap[3]
    cna_big[6] = _slv(33) if level == 1 else _slv(43.2, 50)
    w28 = [w for w in _find_cmds(sub, "Wait") if w[1] == 28]
    if len(w28) != 1:
        raise KitError("D1 Wait(28) not unique")
    w28[0][3][1].append(["Event", ["Wait", 25, "*", ["Block", [ret]]]])   # 归还演出挪到 t=116
    w19[3][1][0] = sub
    return T


def _combo_branch(cna: list) -> list:
    """把一条 ``CreateNormalAttack`` 包进 ``ConditionalsChangeSkillFlag(1)``：
    then 支是开了 ``#8 enablesComboBonus`` 的副本（伤害 ×(1+连击×0.005)，NormalAttackCalculator.as:42/319-321），
    else 支是原件。两支都是非空 Block，禁裸 ``["DoNothing"]``（F1009）。"""
    boosted = copy.deepcopy(cna)
    if boosted[8] is not False:
        raise KitError(f"CreateNormalAttack#8 already {boosted[8]!r}, expected False")
    boosted[8] = True
    return ["Command", ["ConditionalsChangeSkillFlag", 1,
                        ["Block", [["Command", boosted]]],
                        ["Block", [["Command", cna]]]]]


def revise_tree(tree: list, level: int, plan: dict) -> list:
    """改版 delta（plan ``skill_dsl.delta_steps`` 1–4）：三处新倍率 + 三处连击加成开关分支。

    落地连斩那处已经有一个 ``ConditionalsChangeSkillFlag(1)``（抗性降低强化），把伤害并进同一分支，
    保持「先伤害、后挂减益」顺序；横斩与一刀两断各自新包一层。改完全树共 3 个开关分支。"""
    program = DONOR_PROGRAM.format(code=CODE, level=level)
    mult = plan["skill_dsl"]["programs"][program]["multipliers"]
    if sorted(mult) != sorted(name for _bind, name in REVISION_MULT_SLOTS):
        raise KitError(f"revision multipliers {sorted(mult)} unexpected")
    areas = {}
    for bind, name in REVISION_MULT_SLOTS:
        area = _one(tree, "CreateHitArea", lambda a, b=bind: a[19] == b)
        cna = _one(area[23], "CreateNormalAttack")
        want_old = _slv(*mult[name]["old"])
        if cna[6] != want_old:
            raise KitError(f"{name}: composed multiplier {cna[6]} != plan old {want_old}")
        cna[6] = _slv(*mult[name]["new"])
        areas[name] = (area, cna)

    # 落地连斩：与既有抗性降低分支合并
    land, cna_land = areas["落地连斩(每段,共4段)"]
    onhit = land[23][1]
    idx_cna = [i for i, n in enumerate(onhit) if n[0] == "Command" and n[1] is cna_land]
    idx_flag = [i for i, n in enumerate(onhit) if n[0] == "Command" and isinstance(n[1], list)
                and n[1][0] == "ConditionalsChangeSkillFlag"]
    if len(idx_cna) != 1 or len(idx_flag) != 1 or idx_cna[0] >= idx_flag[0]:
        raise KitError(f"landing onHit layout unexpected: attack@{idx_cna} flag@{idx_flag}")
    flag = onhit[idx_flag[0]][1]
    boosted = copy.deepcopy(cna_land)
    if boosted[8] is not False:
        raise KitError("landing CreateNormalAttack#8 already true")
    boosted[8] = True
    flag[2][1].insert(0, ["Command", boosted])       # then：先打（带连击加成的）伤害，再挂强化减益
    flag[3][1].insert(0, ["Command", cna_land])      # else：原伤害 + 原减益
    onhit.pop(idx_cna[0])

    # 横斩 / 一刀两断：各自新包一层
    for name in ("横斩", "一刀两断"):
        area, cna = areas[name]
        block = area[23][1]
        hits = [i for i, n in enumerate(block) if n[0] == "Command" and n[1] is cna]
        if len(hits) != 1:
            raise KitError(f"{name}: CreateNormalAttack not a direct child of onHit block")
        block[hits[0]] = _combo_branch(cna)
    return tree


def build_pf_action_tree(root: Path, plan: dict) -> list:
    """能力1#3 的 629 ``InvokeSkill`` 动作树：官方剑士 PF Lv3 判定区整块。

    去掉两条 PF 上下文专用命令（``SetPowerFilpSuppress`` 会压掉玩家真正的拍板；
    ``NotifyPowerflipEnd`` 在非 PF 上下文不计数，ActionEvaluator.as:5064-5078），
    元素 255→光、开 ``#8 enablesComboBonus``；根头 ``tree[10]=0`` 保持自动档
    （629 的 ActionKind=AbilitySkill(4)，自动档即技能伤害）。母本缺席时退回 plan 里的成树。"""
    spec = plan["skill_dsl"]["new_program"]
    donor = root / PF_DONOR_REL
    if donor.is_file():
        knight = json.loads(donor.read_text(encoding="utf-8"))
        body = copy.deepcopy(knight[11][1])
        if _cmd(body[0])[0] != "SetPowerFilpSuppress":
            raise KitError("knight_lv3 body[0] is not SetPowerFilpSuppress")
        tail = _cmd(body[2])
        if not (tail[0] == "Wait" and _cmd(tail[3][1][0])[0] == "NotifyPowerflipEnd"):
            raise KitError("knight_lv3 body[2] is not Wait→NotifyPowerflipEnd")
        hit = copy.deepcopy(body[1])                 # 只留 CreateHitArea 整块
        cna = _one(hit[1][23], "CreateNormalAttack")
        if not (cna[2] == 255 and cna[8] is False):
            raise KitError(f"knight_lv3 attack drifted: element={cna[2]} comboBonus={cna[8]}")
        cna[2] = ELEMENT + 1                         # 光（DSL 元素码 = 内部 + 1）
        cna[8] = True
        tree = ["ActionDsl", 1, ["None"], False, False, False, False, False, False, False, 0, ["Block", [hit]]]
    else:
        tree = copy.deepcopy(spec["tree"])
    if tree != spec["tree"]:
        raise KitError("PF tree rebuilt from knight_lv3 differs from revision plan new_program.tree")
    return tree


def revision_reference_trees(root: Path) -> dict[Any, Any] | None:
    """设计阶段探针 ``dsl_validated.json`` 里的三棵树（特效改写前），用作逐节点回归基准。"""
    path = root / REVISION_DSL_REL
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    trees = {entry["level"]: entry["tree"] for entry in data["skill"]}
    trees[PF_LEVEL] = data["pf"]["tree"]
    return trees


def official_effect_dir_map() -> dict[str, str]:
    """包内克隆特效目录 → 官方源目录（``rewrite_effect_refs`` 是纯路径段替换，可逐字还原）。"""
    return {f"battle/effect/skill_unique/{CODE}_{fam['subdir']}/": fam["src_dir"] + "/" for fam in FAMILIES}


def unrewrite_effect_refs(tree):
    """把包内树的特效引用还原成官方路径，便于与 ``dsl_validated.json`` 的改版树逐节点比对。"""
    mapping = official_effect_dir_map()

    def rec(node):
        if isinstance(node, str):
            for dst, src in mapping.items():
                if node.startswith(dst):
                    return src + node[len(dst):]
            return node
        if isinstance(node, list):
            return [rec(x) for x in node]
        if isinstance(node, dict):
            return {k: rec(v) for k, v in node.items()}
        return node
    return rec(tree)


def _kind_of(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, (int, float)):
        return "num"
    if isinstance(v, str):
        return "str"
    if isinstance(v, dict):
        return "dict"
    if isinstance(v, list):
        if v and all(isinstance(x, dict) for x in v):
            return "slv"
        if v and isinstance(v[0], str):
            return "expr" if v[0] in ("Block", "Command", "Event") else "enum:" + v[0]
        return "list"
    return type(v).__name__


def official_shape_problems(tree, official_sig: dict) -> list[str]:
    """设计 _tmp compose_skill_proposal.shape_problems 的移植：逐命令参数形状与官方全库签名差分。"""
    probs = []
    for a in _find_cmds(tree, None):
        for i, p in enumerate(a[1:], 1):
            key = f"{a[0]}#{i}"
            k = _kind_of(p)
            ok = official_sig.get(key)
            if ok is None:
                probs.append(f"{key} no official signature")
            elif k not in ok and not (k in ("list", "slv") and ({"list", "slv"} & set(ok))):
                probs.append(f"{key} kind {k} not in official {ok}")
    return probs


def _type_problems(value, typ: str, where: str, enums: dict) -> list[str]:
    if typ in ("Dynamic",):
        return []
    if typ in ("int", "Number"):
        return [] if isinstance(value, (int, float)) and not isinstance(value, bool) else [f"{where}: {typ} got {_kind_of(value)}"]
    if typ == "Boolean":
        return [] if isinstance(value, bool) else [f"{where}: Boolean got {_kind_of(value)}"]
    if typ == "String":
        return [] if isinstance(value, str) else [f"{where}: String got {_kind_of(value)}"]
    if typ == "Array":
        return [] if isinstance(value, list) and _kind_of(value) != "expr" else [f"{where}: Array got {_kind_of(value)} (F1034)"]
    if typ == "Object":
        return [] if isinstance(value, (dict, list, str, int, float)) else [f"{where}: Object got {_kind_of(value)}"]
    if typ == "ActionDslExpression":
        if not (isinstance(value, list) and value and value[0] in ("Block", "Command", "Event")):
            return [f"{where}: ActionDslExpression got {str(value)[:40]} (DoNothing/F1009)"]
        return []
    ctors = enums.get(typ)
    if ctors is None:
        return []
    if value is None:
        # haxe 枚举可空（官方 CreateCondition#8 HitCountCheckTargetKind 多为 null）；
        # 具体哪个位置允许 null 由 official_shape_problems（官方全库 kind 集合）把关。
        return []
    if not (isinstance(value, list) and value and isinstance(value[0], str)):
        return [f"{where}: enum {typ} got {_kind_of(value)}"]
    if value[0] not in ctors:
        return [f"{where}: {value[0]!r} is not a {typ} constructor"]
    params = ctors[value[0]]
    if len(value) - 1 != len(params):
        return [f"{where}: {typ}.{value[0]} arity {len(value) - 1} != {len(params)}"]
    out = []
    for j, (item, sub) in enumerate(zip(value[1:], params), 1):
        out += _type_problems(item, sub, f"{where}.{value[0]}#{j}", enums)
    return out


def sig_problems(tree) -> list[str]:
    """wf_dsl_sig（反编译命令/枚举签名）逐命令参数个数与类型；ActionDslExpression 槽禁非表达式。"""
    import wf_dsl_sig as SIG
    probs: list[str] = []

    def walk(node):
        if isinstance(node, list):
            if node and node[0] in ("Command", "Event") and len(node) > 1 and isinstance(node[1], list) and node[1]:
                cmd = node[1]
                table = SIG.COMMANDS if node[0] == "Command" else SIG.EVENTS
                sig = table.get(cmd[0])
                if sig is None:
                    probs.append(f"{node[0]} {cmd[0]} unknown to wf_dsl_sig")
                elif len(cmd) - 1 != len(sig):
                    probs.append(f"{cmd[0]} arity {len(cmd) - 1} != {len(sig)}")
                else:
                    for i, (value, typ) in enumerate(zip(cmd[1:], sig), 1):
                        probs.extend(_type_problems(value, typ, f"{cmd[0]}#{i}", SIG.ENUMS))
            for child in node:
                walk(child)
    walk(tree)
    return probs


# wf_client_legality.DSL_SUBJECT_CONSUMERS 只列了攻击/状态类主体位，漏了评估器真正 lookup 的
# ShowEffect node[3] / CreateHitArea node[2] / FindNearSubjects node[1] / CreateReferencePoint node[1]
# 与坐标系 ["GH", n]（记忆卡 wf-dsl-subject-lookup-map，C16103）。本树 151117 子树整体重映射到 8–11，
# 恰好落在这些位上，所以 kit 内补一层作用域检查（框架/工具缺口已在返回中报告）。
EXTRA_LOOKUP_CONSUMERS = {"ShowEffect": (3,), "CreateHitArea": (2,), "FindNearSubjects": (1,),
                          "CreateReferencePoint": (1,), "GH": (1,)}


def lookup_scope_problems(tree) -> list[str]:
    import wf_client_legality as L
    consumers = {name: tuple(sorted(set(L.DSL_SUBJECT_CONSUMERS.get(name, ())) | set(extra)))
                 for name, extra in EXTRA_LOOKUP_CONSUMERS.items()}
    consumers = {**L.DSL_SUBJECT_CONSUMERS, **consumers}
    probs: list[str] = []

    def is_node(v) -> bool:
        return isinstance(v, list) and bool(v) and isinstance(v[0], str)

    def walk(node, bound: frozenset) -> None:
        if is_node(node):
            name = node[0]
            for index in consumers.get(name, ()):
                if index < len(node):
                    subject = node[index]
                    if (isinstance(subject, int) and not isinstance(subject, bool)
                            and subject not in bound and subject not in L.DSL_BUILTIN_SUBJECTS):
                        probs.append(f"{name} lookup node[{index}]={subject} unbound (scope {sorted(bound)}) → C16103")
            binders = L.DSL_SUBJECT_BINDERS.get(name)
            if binders:
                handled = {block for _, block in binders}
                for ids, block in binders:
                    if block < len(node):
                        inner = set(bound) | {node[s] for s in ids if s < len(node) and isinstance(node[s], int)}
                        walk(node[block], frozenset(inner))
                for index, child in enumerate(node[1:], 1):
                    if index not in handled:
                        walk(child, bound)
                return
            for child in node[1:]:
                walk(child, bound)
            return
        if isinstance(node, list):
            scope = set(bound)
            for child in node:
                walk(child, frozenset(scope))
                if (isinstance(child, list) and len(child) == 2 and child[0] == "Command" and is_node(child[1])
                        and child[1][0] in L.DSL_STATEMENT_BINDERS):
                    slot = L.DSL_STATEMENT_BINDERS[child[1][0]]
                    if slot < len(child[1]) and isinstance(child[1][slot], int):
                        scope.add(child[1][slot])
        elif isinstance(node, dict):
            for child in node.values():
                walk(child, bound)

    walk(tree, frozenset())
    return probs


# 改版后各树的根头与开关分支数：技能两档 movementPriority=2（含 StopBall）、3 个连击加成分支；
# 629 PF 树沿用官方 knight_lv3 的 movementPriority=1，没有开关分支。buffTargetAs（tree[10]）一律 0=自动档。
TREE_SHAPE = {1: {"movement_priority": 2, "flags": 3}, 2: {"movement_priority": 2, "flags": 3},
              PF_LEVEL: {"movement_priority": 1, "flags": 0}}


def dsl_gates(tree, raw: bytes, level, root: Path) -> dict[str, Any]:
    import wf_client_legality as L
    import wf_dsl
    shape = TREE_SHAPE[level]
    enc = wf_dsl.encode_amf3(tree)
    back = wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]
    sig_path = root / OFFICIAL_SIG_REL
    official_sig = json.loads(sig_path.read_text(encoding="utf-8")) if sig_path.is_file() else None
    strings = [s for s in _iter_strings(tree)]
    extra = []
    if not (tree[0] == "ActionDsl" and tree[1] == shape["movement_priority"] and tree[10] == 0):
        extra.append(f"root header movementPriority/buffTargetAs = {tree[1]}/{tree[10]} "
                     f"(want {shape['movement_priority']}/0)")
    if isinstance(tree, dict):
        extra.append("wrapper dict instead of bare tree")
    if any(s.startswith("battle/effect/enemy") for s in strings):
        extra.append("enemy effect path in player skill tree")
    if any(isinstance(n, list) and n == ["DoNothing"] for n in _iter_nodes(tree)
           if not _is_iftargetnotfound_slot(tree, n)):
        extra.append("bare ['DoNothing'] outside IfTargetNotFound slot (F1009)")
    flags = _find_cmds(tree, "ConditionalsChangeSkillFlag")
    if len(flags) != shape["flags"] or any(f[1] != 1 for f in flags):
        extra.append(f"expected {shape['flags']} ConditionalsChangeSkillFlag(1), got "
                     f"{[f[1] for f in flags]}")
    for i, flag in enumerate(flags):               # 每支都得是非空 Block；then 开连击加成、else 不开
        if [b[0] for b in flag[2:4]] != ["Block", "Block"] or not (flag[2][1] and flag[3][1]):
            extra.append(f"ConditionalsChangeSkillFlag#{i} branch is not a non-empty Block")
            continue
        combo = [[a[8] for a in _find_cmds(branch, "CreateNormalAttack")] for branch in flag[2:4]]
        if combo != [[True], [False]]:
            extra.append(f"ConditionalsChangeSkillFlag#{i} enablesComboBonus then/else = {combo} (want [[True],[False]])")
    return {
        "level": level,
        "roundtrip_equal": back == tree and wf_dsl.parse_dsl(enc)["tree"] == tree,
        "encoded_bytes": len(enc),
        "encoded_bytes_expected": EXPECTED_ENCODED_BYTES[level],
        "deflate_bytes": len(raw),
        "subject_binding_problems": L.action_dsl_subject_binding_problems(tree),
        "lookup_scope_problems": lookup_scope_problems(tree),
        "hit_area_target_problems": L.action_dsl_hit_area_target_problems(tree),
        "element_problems": L.action_dsl_element_problems(tree, ELEMENT),
        "player_side_problems": wf_dsl.player_side_dsl_problems(tree),
        "official_shape_problems": (official_shape_problems(tree, official_sig)
                                    if official_sig is not None else [f"missing {OFFICIAL_SIG_REL}"]),
        "sig_problems": sig_problems(tree),
        "kit_tree_problems": extra,
    }


def _dsl_gate_failed(entry: dict) -> bool:
    return (not entry["roundtrip_equal"] or entry["encoded_bytes"] != entry["encoded_bytes_expected"]
            or any(entry[k] for k in ("subject_binding_problems", "lookup_scope_problems",
                                      "hit_area_target_problems", "element_problems",
                                      "player_side_problems", "official_shape_problems", "sig_problems",
                                      "kit_tree_problems")))


def _iter_nodes(node):
    yield node
    if isinstance(node, list):
        for child in node:
            yield from _iter_nodes(child)
    elif isinstance(node, dict):
        for child in node.values():
            yield from _iter_nodes(child)


def _iter_strings(node):
    for n in _iter_nodes(node):
        if isinstance(n, str):
            yield n


def _is_iftargetnotfound_slot(tree, candidate) -> bool:
    for cmd in _find_cmds(tree, "FindNearSubjects"):
        if len(cmd) > 4 and cmd[4] is candidate:
            return True
    return False


# ======================================================================== 特效

def fx_manifest(root: Path) -> tuple[dict[str, Path], dict | None]:
    """Effects 阶段产物钩子：``fx/zantetsu/out/manifest.json`` = {源（或目标）sheet 逻辑路径: 染色 PNG 文件}。

    兼容三种形状：扁平 dict；{"sheets": dict|list}；list[{source|src|logical: …, png|file|path|output: …}]。
    文件路径可为绝对、相对 manifest 目录或相对仓库根。"""
    path = root / FX_MANIFEST_REL
    if not path.is_file():
        return {}, None
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data.get("sheets", data) if isinstance(data, dict) else data
    pairs: list[tuple[str, str]] = []
    if isinstance(entries, dict):
        pairs = [(k, v if isinstance(v, str) else (v or {}).get("png") or (v or {}).get("file") or (v or {}).get("path"))
                 for k, v in entries.items() if str(k).endswith(".png")]
    elif isinstance(entries, list):
        for item in entries:
            if not isinstance(item, dict):
                continue
            src = item.get("source") or item.get("src") or item.get("logical") or item.get("source_logical")
            dst = item.get("png") or item.get("file") or item.get("path") or item.get("output")
            if src and dst:
                pairs.append((src, dst))
    out: dict[str, Path] = {}
    for logical, file in pairs:
        if not file:
            continue
        candidate = Path(file)
        for base in (None, path.parent, root):
            p = candidate if base is None else base / candidate
            if p.is_file():
                out[str(logical).lstrip("/")] = p.resolve()
                break
        else:
            raise KitError(f"fx manifest PNG not found for {logical}: {file}")
    return out, {"path": str(path), "sha256": _sha(path.read_bytes())}


def _png_transform_for(src_sheet: str, dst_sheet: str, dyed: dict[str, Path], log: list[dict]):
    target = dyed.get(src_sheet) or dyed.get(dst_sheet)
    if target is None:
        return None

    def transform(img):
        import wf_assets
        from PIL import Image
        import io
        raw = target.read_bytes()
        new = Image.open(io.BytesIO(wf_assets.png_decode(raw))).convert("RGBA")
        entry = {"source_sheet": src_sheet, "target_sheet": dst_sheet, "file": str(target),
                 "file_sha256": _sha(raw), "size": list(new.size), "template_size": list(img.size),
                 "size_match": new.size == img.size,
                 "alpha_identical": new.size == img.size and new.getchannel("A").tobytes() == img.getchannel("A").tobytes()}
        log.append(entry)
        if not entry["size_match"]:
            raise KitError(f"dyed sheet size {new.size} != template {img.size}: {target}")
        if not entry["alpha_identical"]:                 # 设计 effects.clone[*].method：alpha 逐字节不变
            raise KitError(f"dyed sheet alpha differs from template (geometry/atlas would drift): {target}")
        return new
    return transform


def timeline_se_problems(ctx, family: dict) -> list[dict]:
    """克隆 timeline 的 sounds：mp3 必须在 live store，或与官方源 timeline 原文一致（APK 内置 SE）。"""
    out = []
    for base in family["copied_bases"]:
        logical = f"{family['dst_dir']}/{base}.timeline.amf3.deflate"
        src_logical = f"{family['src_dir']}/{base}.timeline.amf3.deflate"
        tree = ctx.amf_parse(ctx.pack.pkg_path(_family_root(family), logical).read_bytes())
        src_tree = ctx.amf_parse(ctx.pack.template_asset(src_logical)[1])
        src_paths = {s.get("path") for s in (src_tree.get("sounds") or []) if isinstance(s, dict)}
        for sound in tree.get("sounds") or []:
            se = sound.get("path") if isinstance(sound, dict) else None
            in_store = bool(se) and ctx.pack.live_locate(se + ".mp3") is not None
            verbatim = se in src_paths
            out.append({"timeline": logical, "se": se, "in_live_store": in_store,
                        "verbatim_official": verbatim, "ok": bool(se) and (in_store or verbatim)})
    return out


def fx_sheet_checks(pack) -> dict[str, Any]:
    """包内两族 sheet：尺寸/alpha 与官方母本逐字节一致；fx manifest 存在时像素必须等于染色产物
    （Effects 阶段重跑后包内仍是旧色 = 需重跑 --step kit），不存在时必须仍是官方原色。"""
    import io
    import wf_assets
    from PIL import Image
    dyed, info = fx_manifest(pack.root)
    sheets = []
    for fam in FAMILIES:
        donor = fam["src_dir"].rsplit("/", 1)[-1]
        dst = f"battle/effect/skill_unique/{CODE}_{fam['subdir']}"
        src_sheet = f"{fam['src_dir']}/{donor}.png"
        dst_sheet = f"{dst}/{dst.rsplit('/', 1)[-1]}.png"
        entry: dict[str, Any] = {"sheet": dst_sheet, "source_sheet": src_sheet, "problems": []}
        path = pack.pkg_path("common", dst_sheet)
        if not path.is_file():
            entry["problems"].append("sheet missing from package")
            sheets.append(entry)
            continue
        raw = path.read_bytes()
        _root, tpl_raw, _src = pack.template_asset(src_sheet)
        tpl = Image.open(io.BytesIO(wf_assets.png_decode(tpl_raw))).convert("RGBA")
        img = Image.open(io.BytesIO(wf_assets.png_decode(raw))).convert("RGBA")
        entry.update({"package_sha256": _sha(raw), "store_magic_lowercase": raw[:4] == b"\x89png",
                      "size": list(img.size), "size_equal_template": img.size == tpl.size})
        if not entry["size_equal_template"]:
            entry["problems"].append(f"size {img.size} != template {tpl.size}")
        else:
            entry["alpha_equal_template"] = img.getchannel("A").tobytes() == tpl.getchannel("A").tobytes()
            if not entry["alpha_equal_template"]:
                entry["problems"].append("alpha differs from official template sheet")
        if not entry["store_magic_lowercase"]:
            entry["problems"].append("package PNG not in store form (lowercase magic)")
        target = dyed.get(src_sheet) or dyed.get(dst_sheet)
        if target is not None:
            dyed_raw = target.read_bytes()
            new = Image.open(io.BytesIO(wf_assets.png_decode(dyed_raw))).convert("RGBA")
            store = fx_store_bytes(target)
            entry.update({"dyed_file": str(target), "dyed_sha256": _sha(dyed_raw),
                          "dyed_store_sha256": _sha(store),
                          "pixels_equal_dyed": new.size == img.size and new.tobytes() == img.tobytes(),
                          "bytes_equal_dyed_store_form": raw == store,
                          "owner": pack.owner_of("common", dst_sheet)})
            if not entry["pixels_equal_dyed"]:
                entry["problems"].append("package sheet != current fx manifest PNG (rerun --step kit)")
            elif not entry["bytes_equal_dyed_store_form"]:
                entry["problems"].append("package sheet bytes != store form of fx manifest PNG "
                                         "(pixels equal: framework PIL re-encode; rerun --step kit)")
            if entry["owner"] != "effects":
                entry["problems"].append(f"package sheet owner={entry['owner']} (expected effects)")
        else:
            entry["dyed_file"] = None
            entry["pixels_equal_template"] = img.size == tpl.size and img.tobytes() == tpl.tobytes()
            if not entry["pixels_equal_template"]:
                entry["problems"].append("sheet recoloured but no fx manifest entry backs it")
        sheets.append(entry)
    return {"fx_manifest": info, "sheets": sheets}


def _rgba_array(raw: bytes):
    import io
    import numpy as np
    import wf_assets
    from PIL import Image
    return np.asarray(Image.open(io.BytesIO(wf_assets.png_decode(raw))).convert("RGBA"))


def _color_votes(src, dst, mask) -> dict[str, Counter]:
    """同位不透明像素：源色 → 目标色计数。src/dst 必须同尺寸同 alpha（调用方先核对）。"""
    import numpy as np
    sel = mask & (src[..., 3] == 255)
    key = lambda px: ((px[:, 0].astype(np.int64) << 16) | (px[:, 1].astype(np.int64) << 8) | px[:, 2])  # noqa: E731
    pairs = np.stack([key(src[sel]), key(dst[sel])], axis=1)
    votes: dict[str, Counter] = defaultdict(Counter)
    if len(pairs):
        uniq, counts = np.unique(pairs, axis=0, return_counts=True)
        for (s, d), n in zip(uniq.tolist(), counts.tolist()):
            votes["%06X" % s]["%06X" % d] += int(n)
    return votes


def _mode(counter: Counter) -> tuple[str, float]:
    target, n = max(counter.items(), key=lambda kv: (kv[1], kv[0]))
    return target, n / sum(counter.values())


def doll_color_checks(pack, overrides: dict[str, Path] | None = None) -> dict[str, Any]:
    """设计 §5.1 / 风险 8 / 验收 8：特效里的小人帧必须和像素小人同色。

    - 像素参照：官方 smr22 sprite_sheet/special_sprite_sheet → ``pixel/zantetsu/out`` 同名 PNG，
      以及包内已装入（≠官方）的像素 sheet；逐源色取主映射色。
    - 特效：包内两族 sheet 只看 ``fx/zantetsu/analysis.json`` 判为 doll 的 rect 内部（去掉 S2 黄闪变体 rect），
      逐源色主映射色必须单值。
    - smr22 族（doll_lut="pixel"，与像素小人同一精灵）：像素 sheet 里有的源色，特效主映射色必须等于每个像素参照的
      主映射色（不看 fx 报告怎么说）。
    - 131044 旧小人（doll_lut="separate"，单独 LUT）：按 fx 报告逐色来源核对——pixel_mapping 色必须等于像素映射；
      old_doll_analog 色的同类源色在当前像素里的映射仍等于染色时记录的 analog_target，包内色等于报告目标。
    - 两族都：DOLL_KEEP 色（像素里没有该源色时）保持原色；没有来源说明的颜色一律报错。
    - 依赖链：fx 报告 pixel_dependency.sha256 == 当前像素报告；像素报告 outputs == pixel/out；
      fx 报告 output sha == fx manifest PNG；analysis 的源 sheet sha 与 rect 集合 == 官方母本。
    """
    import numpy as np
    root = pack.root
    paths = {"fx_report": root / FX_REPORT_REL, "fx_analysis": root / FX_ANALYSIS_REL,
             "pixel_report": root / PIXEL_REPORT_REL, "pixel_out": root / PIXEL_OUT_REL}
    paths.update({k: Path(v) for k, v in (overrides or {}).items()})
    problems: list[str] = []
    result: dict[str, Any] = {"paths": {k: str(v) for k, v in paths.items()}, "problems": problems}
    missing = [k for k in ("fx_report", "fx_analysis", "pixel_report") if not paths[k].is_file()]
    dyed, manifest_info = fx_manifest(root)
    if not dyed:
        missing.append("fx_manifest")
    if missing:
        problems.append(f"小人同色核对缺少输入 {missing}：特效小人帧无法证明与像素小人同色")
        return result
    fx_raw, px_raw = paths["fx_report"].read_bytes(), paths["pixel_report"].read_bytes()
    fx_rep, px_rep = json.loads(fx_raw), json.loads(px_raw)
    analysis = json.loads(paths["fx_analysis"].read_text(encoding="utf-8"))
    dep = fx_rep.get("pixel_dependency") or {}
    result["provenance"] = {"fx_report_sha256": _sha(fx_raw), "fx_gates_passed": fx_rep.get("gates_passed"),
                            "pixel_report_sha256": _sha(px_raw), "pixel_gates_passed": px_rep.get("gates_passed"),
                            "fx_pixel_dependency_sha256": dep.get("sha256"),
                            "fx_manifest_sha256": manifest_info["sha256"]}
    if fx_rep.get("gates_passed") is not True:
        problems.append("fx/zantetsu/out/report.json gates_passed != true")
    if px_rep.get("gates_passed") is not True:
        problems.append("pixel/zantetsu/report.json gates_passed != true（像素管线未定稿）")
    if dep.get("sha256") != _sha(px_raw):
        problems.append(f"像素报告已变（fx 染色时 sha {str(dep.get('sha256'))[:12]}…，当前 {_sha(px_raw)[:12]}…）："
                        "重跑 fx_recolor_zantetsu.py gate → --step kit → gates")

    # ---- 像素参照 LUT
    px_luts: dict[str, dict[str, Counter]] = {}
    sources: list[dict] = []
    for name in PIXEL_SHEETS:
        tpl = _rgba_array(pack.template_asset(PIXEL_SHEET.format(code=D1_CODE, name=name))[1])
        cands: list[tuple[str, bytes]] = []
        out_file = paths["pixel_out"] / f"{name}.png"
        if out_file.is_file():
            raw = out_file.read_bytes()
            want = ((px_rep.get("outputs") or {}).get(name) or {}).get("sha256")
            if want != _sha(raw):
                problems.append(f"pixel/out/{name}.png sha 与像素报告 outputs 不符（像素管线跑到一半？）")
            cands.append(("pixel_out", raw))
        pkg_file = pack.pkg_path("common", PIXEL_SHEET.format(code=CODE, name=name))
        installed = False
        if pkg_file.is_file():
            raw = pkg_file.read_bytes()
            arr = _rgba_array(raw)
            installed = not (arr.shape == tpl.shape and bool((arr == tpl).all()))
            if installed:
                cands.append(("package", raw))
        sources.append({"sheet": name, "pixel_out": str(out_file) if out_file.is_file() else None,
                        "package_installed": installed})
        for label, raw in cands:
            arr = _rgba_array(raw)
            if arr.shape != tpl.shape or not bool((arr[..., 3] == tpl[..., 3]).all()):
                problems.append(f"{label} {name}.png 尺寸/alpha 与官方 smr22 不同，无法逐色对照")
                continue
            lut = px_luts.setdefault(label, defaultdict(Counter))
            for src, counter in _color_votes(tpl, arr, np.ones(tpl.shape[:2], bool)).items():
                lut[src].update(counter)
    result["pixel_sources"] = sources
    if not px_luts:
        problems.append("没有可用的像素小人参照（pixel/out 缺失且包内仍是官方像素）")

    # ---- 两族特效 sheet 的小人帧
    families: list[dict] = []
    for fam in FAMILIES:
        sid, donor = fam["id"], fam["src_dir"].rsplit("/", 1)[-1]
        src_sheet = f"{fam['src_dir']}/{donor}.png"
        dst = f"battle/effect/skill_unique/{CODE}_{fam['subdir']}"
        dst_sheet = f"{dst}/{dst.rsplit('/', 1)[-1]}.png"
        entry: dict[str, Any] = {"family": sid, "sheet": dst_sheet, "colors": []}
        families.append(entry)
        ana = analysis.get(sid) or {}
        fx_sheet = (fx_rep.get("sheets") or {}).get(sid) or {}
        tpl_raw = pack.template_asset(src_sheet)[1]
        atlas = _amf_parse(pack.template_asset(f"{fam['src_dir']}/{donor}.atlas.amf3.deflate")[1])
        rects = {(int(e["x"]), int(e["y"]), int(e["w"]), int(e["h"])) for e in atlas}
        table = ana.get("rect_table") or []
        if ((ana.get("files") or {}).get(src_sheet) or {}).get("sha256") != _sha(tpl_raw):
            problems.append(f"{sid}: fx analysis 的源 sheet sha 与官方母本不符（analysis 过期）")
        if {tuple(r["rect"]) for r in table} != rects:
            problems.append(f"{sid}: fx analysis rect 集合与官方 atlas 不符")
        target = dyed.get(src_sheet) or dyed.get(dst_sheet)
        if target is None or (fx_sheet.get("output") or {}).get("sha256") != _sha(target.read_bytes()):
            problems.append(f"{sid}: fx 报告 output sha 与 fx manifest PNG 不符（报告与染色产物不是同一轮）")
        pkg_file = pack.pkg_path("common", dst_sheet)
        if not pkg_file.is_file():
            problems.append(f"{sid}: 包内缺 {dst_sheet}")
            continue
        tpl, pkg = _rgba_array(tpl_raw), _rgba_array(pkg_file.read_bytes())
        if tpl.shape != pkg.shape or not bool((tpl[..., 3] == pkg[..., 3]).all()):
            problems.append(f"{sid}: 包内 sheet 尺寸/alpha 与官方不同")
            continue
        mask = np.zeros(tpl.shape[:2], bool)
        for r in table:
            if r.get("cls") == "doll":
                x, y, w, h = r["rect"]
                mask[y:y + h, x:x + w] = True
        doll = fx_sheet.get("doll") or {}
        for flash in doll.get("flash") or []:           # 黄闪变体 = screen(本体, 闪光色)，不走小人 LUT
            x, y, w, h = flash["flash_rect"]
            mask[max(y - 1, 0):y + h + 1, max(x - 1, 0):x + w + 1] = False
        provenance = doll.get("provenance") or {}
        votes = _color_votes(tpl, pkg, mask)
        if not votes:
            problems.append(f"{sid}: doll rect 内没有不透明像素（analysis 分类失效？）")
        for color in sorted(votes):
            fx_target, share = _mode(votes[color])
            row: dict[str, Any] = {"source": color, "fx": fx_target, "fx_share": round(share, 4)}
            entry["colors"].append(row)
            if share != 1:
                problems.append(f"{sid}: 小人源色 #{color} 在特效里映射成多个颜色 {dict(votes[color])}")
            present = {label: _mode(lut[color])[0] for label, lut in px_luts.items() if color in lut}
            prov = provenance.get(color) or {}
            if fam["doll_lut"] == "pixel" and present:
                rule = "pixel_same_source"
            elif color in DOLL_KEEP:
                rule = "keep"
            else:
                rule = prov.get("rule")
            row["rule"] = rule
            if rule in ("pixel_same_source", "pixel_mapping"):
                row["pixel"] = present
                if not present:
                    problems.append(f"{sid}: 小人 #{color} fx 报告记为像素映射，但像素 sheet 里没有该源色")
                bad = {label: t for label, t in present.items() if t != fx_target}
                if bad:
                    problems.append(f"{sid}: 小人 #{color} 特效→#{fx_target}，像素→{bad}（重跑 fx 染色 → kit）")
            elif rule == "keep":
                if fx_target != color:
                    problems.append(f"{sid}: 保持色 #{color} 被改成 #{fx_target}")
            else:
                analog = prov.get("analog_source")
                row.update(analog_source=analog, analog_target=prov.get("analog_target"),
                           fx_report_target=prov.get("target"))
                if rule != "old_doll_analog" or not analog:
                    problems.append(f"{sid}: 小人 #{color} 没有来源（不在像素 sheet 同源色，fx 报告也不是同类源色映射）")
                    continue
                analog_now = {label: _mode(lut[analog])[0] for label, lut in px_luts.items() if analog in lut}
                row["analog_pixel"] = analog_now
                if not analog_now:
                    problems.append(f"{sid}: 同类源色 #{analog} 不在像素 sheet")
                elif any(t != prov.get("analog_target") for t in analog_now.values()):
                    problems.append(f"{sid}: 旧小人 #{color} 的同类源色 #{analog} 像素映射已变 "
                                    f"{analog_now} ≠ 染色时 #{prov.get('analog_target')}（重跑 fx 染色 → kit）")
                if prov.get("target") != fx_target:
                    problems.append(f"{sid}: 旧小人 #{color} 包内 #{fx_target} ≠ fx 报告 #{prov.get('target')}")
        entry["doll_lut"] = fam["doll_lut"]
        entry["summary"] = dict(Counter(str(r.get("rule")) for r in entry["colors"]))
    result["families"] = families
    return result


def _amf_parse(raw: bytes):
    import wf_seasonal7_common as C
    return C.amf_parse(raw)


def _family_root(family: dict) -> str:
    roots = {f["root"] for f in family["files"]}
    if len(roots) != 1:
        raise KitError(f"effect family spans roots {roots}")
    return roots.pop()


def effect_reference_problems(ctx, trees: dict[str, Any]) -> dict[str, Any]:
    """DSL 特效引用 → 客户端实际加载的 4 件（parts/timeline/sheet/atlas）在包内或 live 可解析；
    包内 parts 纹理全部落在包内 atlas。"""
    import wf_character_requirements as R
    refs = R.extract_master_asset_references({}, {}, trees, context_element=ELEMENT)
    checked, problems = [], []
    for ref in refs:
        if ref.kind != "skill_effect":
            continue
        for logical in R.required_asset_paths(ref):
            in_pkg = ctx.pack.pkg_has("common", logical)
            in_live = ctx.pack.live_locate(logical) is not None
            checked.append({"ref": ref.value, "logical": logical, "package": in_pkg, "live": in_live})
            if not (in_pkg or in_live):
                problems.append(f"unresolved {logical} (from {ref.source})")
        parts, _tl, _sheet, atlas = R.required_asset_paths(ref)
        if ctx.pack.pkg_has("common", parts):
            if not ctx.pack.pkg_has("common", atlas):
                problems.append(f"package parts without package atlas: {parts}")
                continue
            ptree = ctx.amf_parse(ctx.pack.pkg_path("common", parts).read_bytes())
            atree = ctx.amf_parse(ctx.pack.pkg_path("common", atlas).read_bytes())
            lost = sorted({i["p"] for i in ptree.get("i", []) if isinstance(i, dict)}
                          - {a["n"] for a in atree if isinstance(a, dict) and "n" in a})
            if lost:
                problems.append(f"{parts} textures missing from atlas: {lost[:5]}")
    return {"checked": checked, "problems": problems}


# ======================================================================== 指纹 / 静态门禁（build 与 gates 共用）

def kit_fingerprint(pack) -> str:
    """kit 拥有产物的内容指纹（表行明文 + DSL/特效/预览字节）。与 manifest/voice/pixel 无关。"""
    return _sha("\n".join(kit_fingerprint_parts(pack)).encode("utf-8"))


def fingerprint_part_changes(before: list[str], after: list[str]) -> list[str]:
    """两次指纹逐项差异（``<表>#<键>`` / ``<文件>`` 标签）：定位 kit 之后被谁改了哪一项。"""
    split = lambda parts: dict(p.rpartition("=")[::2] for p in parts)  # noqa: E731
    old, new = split(before), split(after)
    return sorted(k for k in old.keys() | new.keys() if old.get(k) != new.get(k))


def stance_detail_check(ctx, design: dict) -> dict[str, Any]:
    """stance_detail 设计值（官方 131044 行）与框架 tables 按母本 151117 回写值的区分。"""
    import wf_seasonal7_common as C
    import wf_seasonal7_tables as T
    spec = ctx.spec
    package = ctx.pack.pkg_flat(STANCE).get(CID) if ctx.pack.pkg_has("common", STANCE) else None
    want = design["identity"]["explicit_rows"][STANCE]["value"]
    template_char = C.csv_split(ctx.template_flat(CHAR)[spec.template_id_s])[0]      # 与 tables 同源
    template_rows = C.csv_split(ctx.template_flat(STANCE)[spec.template_id_s])
    tables_value = C.csv_join(T.stance_detail_rows(template_rows, template_char[26], spec.stance, []))
    return classify_stance_detail(package, want, tables_value)


def classify_stance_detail(package: str | None, design_value: str, tables_value: str) -> dict[str, Any]:
    ok = package == design_value
    return {"package": package, "design": design_value, "tables_template_value": tables_value, "ok": ok,
            "reverted_by_tables": (not ok) and package == tables_value}


def kit_fingerprint_parts(pack) -> list[str]:
    import wf_mod_tool as core
    import wf_seasonal7_common as C
    parts: list[str] = []
    for logical, keys in KIT_TABLE_KEYS.items():
        rows = pack.pkg_flat(logical) if pack.pkg_has("common", logical) else {}
        for key in keys:
            parts.append(f"{logical}#{key}={_sha(rows.get(key, '<missing>').encode('utf-8'))}")
    for logical, outer in KIT_NESTED_KEYS.items():
        if pack.pkg_has("common", logical):
            nested = core.load_nested_table_bytes(pack.pkg_path("common", logical).read_bytes(), logical)
            inner = nested.rows[outer].text_rows() if outer in nested.rows else {}
        else:
            inner = {}
        parts.append(f"{logical}#{outer}={_sha(json.dumps(inner, ensure_ascii=False, sort_keys=True).encode('utf-8'))}")
    files = [C.wf_dsl.dsl_logical(DONOR_PROGRAM.format(code=CODE, level=lv)) for lv in (1, 2)] + [PREVIEW]
    base = pack.package / "roots" / "common"
    for fam in FAMILIES:
        dst = f"battle/effect/skill_unique/{CODE}_{fam['subdir']}"
        d = base / Path(*dst.split("/"))
        if d.is_dir():
            files += sorted(p.relative_to(base).as_posix() for p in d.rglob("*") if p.is_file())
    for logical in files:
        path = pack.pkg_path("common", logical)
        parts.append(f"{logical}={_sha(path.read_bytes()) if path.is_file() else '<missing>'}")
    return parts


# ======================================================================== Integrate：特效存储态 / 像素小人 / 语音状态

def fx_store_bytes(file: Path) -> bytes:
    """染色 PNG 的存储态原字节：真 PNG → 小写魔数（``wf_assets.png_encode``，不经 PIL 重编码）；已是存储态原样返回。

    框架 ``clone_effect_family(png_transform=…)`` 经 ``png_store_bytes`` 以 PIL optimize 重编码写 sheet
    （逐像素等于染色 PNG，但字节 ≠ 复核过的产物存储态），kit 克隆后用本函数的字节覆盖。"""
    import wf_assets
    raw = Path(file).read_bytes()
    if raw[:8] == wf_assets.PNG_FAKE:
        return raw
    if raw[:8] != wf_assets.PNG_REAL:
        raise KitError(f"fx/pixel PNG has unknown magic {raw[:8].hex()}: {file}")
    store = wf_assets.png_encode(raw)
    if wf_assets.png_decode(store) != raw or store[:8] != wf_assets.PNG_FAKE:
        raise KitError(f"store-form roundtrip failed: {file}")
    return store


def pixel_review_verdict(text: str, key: str = KEY) -> tuple[bool, str]:
    """``pixel/REVIEW.md`` 「修复轮复核」段结论表里 ``| <key> …`` 行是否判 **PASS**（初审段已被取代，不认）。"""
    lines = text.splitlines()
    start = next((i for i, ln in enumerate(lines) if ln.startswith("## ") and PIXEL_REVIEW_HEADING in ln), None)
    if start is None:
        return False, f"REVIEW.md 尚无「{PIXEL_REVIEW_HEADING}」段"
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    rows = [ln for ln in lines[start:end] if ln.lstrip().startswith("|")
            and ln.strip().strip("|").strip().split(" ")[0] == key]
    if not rows:
        return False, f"「{PIXEL_REVIEW_HEADING}」段没有 {key} 结论行"
    cells = [c.strip() for c in rows[0].strip().strip("|").split("|")]
    if not any(c.startswith("**PASS") for c in cells):
        return False, f"{key} 修复轮复核未判 PASS: {rows[0].strip()}"
    return True, rows[0].strip()


def pixel_inputs(root: Path) -> dict[str, Any]:
    """像素染色产物是否可装包：修复轮复核 PASS + ``verify_all.json`` 本角色 pass（H 门禁全过）
    + ``pixel/zantetsu/verify.json`` all_ok + report gates 全过 + out PNG sha = report outputs = 复核 H8 sha。

    返回 ``{"ready", "problems", "review", "outputs": {name: {file, sha256}}}``；problems 非空 = pending（不装包）。"""
    probs: list[str] = []
    state: dict[str, Any] = {"ready": False, "problems": probs, "outputs": {}}
    review = root / PIXEL_REVIEW_REL
    if review.is_file():
        ok, detail = pixel_review_verdict(review.read_text(encoding="utf-8"))
        state["review"] = detail
        if not ok:
            probs.append(detail)
    else:
        probs.append(f"{PIXEL_REVIEW_REL} 不存在")
    report_path, verify_path, verify_all_path = root / PIXEL_REPORT_REL, root / PIXEL_VERIFY_REL, root / PIXEL_VERIFY_ALL_REL
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else {}
    if not report:
        probs.append(f"{PIXEL_REPORT_REL} 不存在")
    elif (report.get("key"), report.get("code")) != (KEY, D1_CODE) or report.get("gates_passed") is not True:
        probs.append(f"pixel report key/code/gates_passed = {report.get('key')}/{report.get('code')}/{report.get('gates_passed')}")
    bad_gates = sorted(k for k, g in (report.get("gates") or {}).items() if not (isinstance(g, dict) and g.get("ok") is True))
    if report and (bad_gates or not report.get("gates")):
        probs.append(f"pixel report gates not all ok: {bad_gates}")
    verify = json.loads(verify_path.read_text(encoding="utf-8")) if verify_path.is_file() else {}
    if verify.get("all_ok") is not True:
        probs.append(f"{PIXEL_VERIFY_REL} all_ok != true")
    verify_all = (json.loads(verify_all_path.read_text(encoding="utf-8")).get(KEY) or {}) if verify_all_path.is_file() else {}
    hard_bad = sorted(k for k, v in (verify_all.get("hard") or {}).items() if not (isinstance(v, dict) and v.get("ok")))
    if verify_all.get("pass") is not True or hard_bad or not verify_all.get("hard"):
        probs.append(f"pixel review verify_all {KEY}: pass={verify_all.get('pass')} hard_failed={hard_bad}")
    reviewed = ((verify_all.get("hard") or {}).get("H8_png_roundtrip") or {}).get("detail") or {}
    for name in PIXEL_SHEETS:
        png = root / PIXEL_OUT_REL / f"{name}.png"
        if not png.is_file():
            probs.append(f"pixel out 缺 {name}.png")
            continue
        digest = _sha(png.read_bytes())
        if ((report.get("outputs") or {}).get(name) or {}).get("sha256") != digest:
            probs.append(f"pixel out {name}.png sha {digest[:12]}… != report outputs")
        if (reviewed.get(name) or {}).get("sha256") != digest:
            probs.append(f"pixel out {name}.png sha {digest[:12]}… != 复核 verify_all H8 sha")
        state["outputs"][name] = {"file": str(png), "sha256": digest}
    state["ready"] = not probs
    return state


def pixel_package_problems(pack, sheet_bytes: dict[str, bytes] | None = None) -> list[str]:
    """包内像素小人核对（只读）：sheet 字节 = pixel/out PNG 的存储态；尺寸 / alpha / alpha==0 像素 RGBA = 母本；
    atlas/frame/timeline = 母本树（仅 ``character/<母本>/``→``character/<code>/``）；sheet owner=pixel、元数据未被他人登记。"""
    import numpy as np
    import wf_seasonal7_common as C
    state = pixel_inputs(pack.root)
    if not state["ready"]:
        return [f"pixel inputs not ready: {p}" for p in state["problems"]]
    probs: list[str] = []
    prefix = C.dir_prefix_map(D1_CODE, CODE)
    for name, metas in PIXEL_METADATA.items():
        logical = PIXEL_SHEET.format(code=CODE, name=name)
        tpl_logical = PIXEL_SHEET.format(code=D1_CODE, name=name)
        if sheet_bytes is not None and logical in sheet_bytes:
            raw = sheet_bytes[logical]
        elif pack.pkg_has("common", logical):
            raw = pack.pkg_path("common", logical).read_bytes()
        else:
            probs.append(f"package pixel sheet missing {logical}")
            continue
        if raw != fx_store_bytes(Path(state["outputs"][name]["file"])):
            probs.append(f"{logical} bytes != store form of pixel/zantetsu/out/{name}.png")
        _r, tpl_raw, _src = pack.template_asset(tpl_logical)
        pkg_arr, tpl_arr = np.asarray(C.png_open(raw)), np.asarray(C.png_open(tpl_raw))
        if pkg_arr.shape != tpl_arr.shape:
            probs.append(f"{logical} size {pkg_arr.shape} != template {tpl_arr.shape}")
        else:
            if not bool((pkg_arr[..., 3] == tpl_arr[..., 3]).all()):
                probs.append(f"{logical} alpha differs from template {tpl_logical}")
            clear = tpl_arr[..., 3] == 0
            if not bool((pkg_arr[clear] == tpl_arr[clear]).all()):
                probs.append(f"{logical} alpha==0 RGBA differs from template")
        if sheet_bytes is None and pack.owner_of("common", logical) != "pixel":
            probs.append(f"{logical} owner={pack.owner_of('common', logical)} (expected pixel)")
        for meta in metas:
            pkg_meta = PIXEL_SHEET.format(code=CODE, name=name).rsplit("/", 1)[0] + f"/{meta}"
            tpl_meta = tpl_logical.rsplit("/", 1)[0] + f"/{meta}"
            if not pack.pkg_has("common", pkg_meta):
                probs.append(f"package pixel metadata missing {pkg_meta}")
                continue
            owner = pack.owner_of("common", pkg_meta)
            if owner not in (None, "assets"):
                probs.append(f"{pkg_meta} owner={owner} (metadata must stay the template copy)")
            want = C.replace_strings(_amf_parse(pack.template_asset(tpl_meta)[1]), prefix)
            got = _amf_parse(pack.pkg_path("common", pkg_meta).read_bytes())
            if got != want:
                probs.append(f"{pkg_meta} differs from template metadata (only the path prefix may change)")
            if f"character/{D1_CODE}/" in json.dumps(got, ensure_ascii=False):
                probs.append(f"{pkg_meta} still references character/{D1_CODE}/")
    return probs


def install_pixel(ctx) -> dict[str, Any]:
    """复核通过的像素 sheet 以存储态（小写魔数，PNG 字节不重编码）写入包，owner=pixel；元数据不动。

    幂等：字节相同时 ``write_pkg`` 不改盘，登记 sha 不变。产物未就绪时不写，返回 pending。"""
    pack = ctx.pack
    state = pixel_inputs(ctx.root)
    if not state["ready"]:
        return {"status": "pending", "problems": state["problems"], "review": state.get("review")}
    store = {PIXEL_SHEET.format(code=CODE, name=name): fx_store_bytes(Path(out["file"]))
             for name, out in state["outputs"].items()}
    before_write = pixel_package_problems(pack, store)       # 先按将写字节校验尺寸/alpha/元数据，再落盘
    if before_write:
        raise KitError(f"pixel sheets fail pre-write checks: {before_write}")
    sheets = {}
    for name, out in state["outputs"].items():
        logical = PIXEL_SHEET.format(code=CODE, name=name)
        prior = pack.pkg_path("common", logical).read_bytes() if pack.pkg_has("common", logical) else None
        ctx.write_asset("common", logical, store[logical], owner="pixel")
        sheets[logical] = {"source": f"{PIXEL_OUT_REL}/{name}.png", "source_sha256": out["sha256"],
                           "store_sha256": _sha(store[logical]),
                           "previous_package_sha256": None if prior is None else _sha(prior),
                           "changed": prior != store[logical]}
    after = pixel_package_problems(pack)
    if after:
        raise KitError(f"pixel sheets did not land in the package: {after}")
    return {"status": "installed", "review": state.get("review"), "sheets": sheets, "problems": []}


def voice_state(pack) -> dict[str, Any]:
    """只读：AI 语音是否已装包——22 槽 MP3 在包内且 owner=voice（登记后未被改过）、speech 8 行引用
    home_0..5/join/evolution、语音目录无多余文件（母本旧语音已删）、character_text c11 = VOICE_ACTOR。"""
    import wf_seasonal7_common as C
    import wf_seasonal7_voice as V
    planned = [f"character/{CODE}/voice/{s}.mp3" for s in V.SLOTS]
    missing = [lg for lg in planned if not pack.pkg_has("common", lg)]
    not_voice = [lg for lg in planned if lg not in missing and pack.owner_of("common", lg) != "voice"]
    modified = [lg for lg in planned if lg not in missing and pack.modified_since_registration("common", lg)]
    rows = pack.pkg_flat(SPEECH) if pack.pkg_has("common", SPEECH) else {}
    refs = [cells[4] for cells in C.csv_split(rows[CID])] if CID in rows else []
    want_refs = [*V.HOME_SLOTS, "ally/join", "ally/evolution"]
    common = pack.package / "roots" / "common"
    voice_dir = common / "character" / CODE / "voice"
    extra = sorted(p.relative_to(common).as_posix() for p in voice_dir.rglob("*")
                   if p.is_file() and p.relative_to(common).as_posix() not in planned) if voice_dir.is_dir() else []
    cv = pack.pkg_character_text_row()[11]
    report = pack.read_evidence("voice-report.json", None) or {}
    problems = []
    if missing:
        problems.append(f"voice slots missing: {len(missing)}")
    if not_voice:
        problems.append(f"voice files not owned by voice: {len(not_voice)}")
    if modified:
        problems.append(f"voice files modified since registration: {modified[:3]}")
    if refs != want_refs:
        problems.append(f"character_speech refs {refs} != {want_refs}")
    if extra:
        problems.append(f"stale voice files in package: {extra}")
    if cv != V.VOICE_ACTOR:
        problems.append(f"character_text c11 {cv!r} != {V.VOICE_ACTOR!r}")
    if report.get("status") != "packed":
        problems.append(f"evidence/voice-report.json status={report.get('status')}")
    return {"packed": not problems, "problems": problems, "speech_refs": refs, "extra_voice_files": extra,
            "run": report.get("run"), "voice_actor": cv}


# ======================================================================== build

def build(ctx) -> dict[str, Any]:
    import wf_mod_tool as core
    import wf_dsl
    spec = ctx.spec
    root = ctx.root
    if (spec.cid_s, spec.code, spec.element, spec.pf_type, spec.stance) != (CID, CODE, ELEMENT, 0, "Attacker"):
        raise KitError(f"spec identity mismatch: {spec.cid_s} {spec.code}")
    if spec.identity != int(CID):
        raise KitError(f"c27 identity {spec.identity} != self cid (roster c27_policy)")
    design, plan = load_revised_design(root)      # 设计文件 + 改版 20260916 文案改写
    text = design["text"]
    want_texts = {"name": text["name"], "furigana": text["name_en"], "title": text["nickname"],
                  "profile": text["profile"], "leader": text["leader_name"], "skill1": text["skill1_name"],
                  "desc1": text["skill1_desc"], "skill2": text["skill2_name"], "desc2": text["skill2_desc"],
                  "cv": text["cv"]}
    if want_texts != TEXTS or any(spec.texts[k] != v for k, v in TEXTS.items()):
        raise KitError("TEXTS drifted from design text section (or spec did not merge TEXTS)")
    notes: list[str] = []

    # ---- 1. 词条 / 队长（改版施工单逐行 donor 回放）
    rows = revision_rows(ctx, plan)
    cas_text = {c["key"]: c["value"] for c in design["custom_strings"] if c["table"] == CAS}
    if sorted(cas_text) != sorted(CAS_KEYS):
        raise KitError(f"custom strings {sorted(cas_text)} != {sorted(CAS_KEYS)}")
    row_gates = {"leader_ability": [row_gate("leader_ability", r, set(cas_text)) for r in rows["leader"]],
                 "ability": {k: [row_gate("ability", r, set(cas_text)) for r in v]
                             for k, v in rows["abilities"].items()}}
    failed_rows = [f"leader#L{i}" for i, g in enumerate(row_gates["leader_ability"]) if _row_gate_failed(g)]
    failed_rows += [f"{k}#L{i}" for k, gs in row_gates["ability"].items() for i, g in enumerate(gs) if _row_gate_failed(g)]
    if failed_rows:
        raise KitError(f"row gates failed before write: {failed_rows}: "
                       + json.dumps(row_gates, ensure_ascii=False)[:1500])
    ctx.write_flat(ABILITY, rows["abilities"])
    ctx.write_flat(LEADER, {CID: rows["leader"]})
    ctx.write_flat(CAS, {key: [[cas_text[key]]] for key in CAS_KEYS})

    # ---- 2. upskill / stance_detail 显式行（照 131044，黄→白）
    explicit = design["identity"]["explicit_rows"]
    donor_up = ctx.official_flat(UPSKILL)["131044"]
    if donor_up.replace("condition_effect_yellow_up", "condition_effect_white_up") != explicit[UPSKILL]["value"]:
        raise KitError("upskill design value does not follow official 131044 row")
    donor_stance = ctx.official_flat(STANCE)["131044"]
    if donor_stance != explicit[STANCE]["value"]:
        raise KitError("stance_detail design value does not equal official 131044 row")
    ctx.write_flat(UPSKILL, {CID: explicit[UPSKILL]["value"]})
    ctx.write_flat(STANCE, {CID: explicit[STANCE]["value"]})
    notes.append("character_stance_detail 由框架 tables 每次按母本 151117 重写为 \",1,1,1,,1,1,1\"；固定顺序 "
                 "tables → kit → assets → manifest → status，单独重跑 tables 后必须再跑 kit，发布前跑 kit gates"
                 "（stance_detail 与指纹逐项差异会拦下；框架限制，已报告主控）。")

    # ---- 3. action_skill 两档 + switched_action_skill 语音路由行
    act_official = core.load_nested_table_bytes(ctx.official_read(ACTION, "common"), ACTION)
    donor_inner = act_official.rows[D2_CODE].text_rows()
    action_rows: dict[str, list[str]] = {}
    for level in ("1", "2"):
        cells = ctx.csv_split(donor_inner[level])[0]
        if len(cells) != 24:
            raise KitError("official action_skill row width != 24")
        want = design["skills"]["action_skill_rows"][f"inner_{level}"]
        new = list(cells)
        for col, value in want.items():
            if int(col) >= 8 and new[int(col)] != value:
                raise KitError(f"action_skill donor c{col}={new[int(col)]!r} != design {value!r}")
            new[int(col)] = value
        if new[7] != ctx.program_path(level) or any(new[17:24]):
            raise KitError("action_skill program path / trailing columns unexpected")
        energy = design["skills"]["energy"][f"inner_{level}"]
        if [new[4], new[5], new[6]] != [energy["c4"], energy["c5"], energy["c6"]]:
            raise KitError("energy columns drift from design")
        action_rows[level] = new
    ctx.write_nested(ACTION, CODE, {lv: [cells] for lv, cells in action_rows.items()}, replace_inner=True)
    switched = {lv: cells[7:24] for lv, cells in action_rows.items()}
    ctx.write_nested(SWITCHED, VOICE_READY, {lv: [cells] for lv, cells in switched.items()}, replace_inner=True)

    # ---- 4. character 行（c9–c16 语音路由）+ character_text + 三层镜像
    crow = list(ctx.pack.pkg_character_row())
    cedits = design["identity"]["character_row"]
    if cedits["edits"]["14"] != VOICE_READY or [cedits["edits"][str(i)] for i in range(9, 17)] != ROUTE_COLS:
        raise KitError("design route columns drifted")
    if crow[9:17] != ROUTE_COLS and not (crow[9] == "(None)" and not any(crow[10:17])):
        raise KitError(f"character row carries an unrelated skill switch: {crow[9:17]}")
    crow[9:17] = ROUTE_COLS
    for col, value in {**cedits["edits"], **cedits["inherit_unchanged"]}.items():
        if crow[int(col)] != value:
            raise KitError(f"character c{col}={crow[int(col)]!r} != design {value!r}")
    ctx.write_flat(CHAR, {CID: [crow]})
    trow = list(text["character_text_row"])
    pkg_trow = ctx.pack.pkg_character_text_row()
    if pkg_trow != trow:
        notes.append("character_text 行与 tables 产出不同，已按设计行写入（下次 tables 会按 TEXTS 回写成同值）")
    ctx.write_flat(TEXT, {CID: [trow]})
    mirrors = ctx.sync_character_mirrors()

    # ---- 5. 特效族（sibling 形态）+ Effects 阶段染色钩子 + hit 音效改写
    dyed, fx_manifest_info = fx_manifest(root)
    fx_log: list[dict] = []
    families: dict[str, dict] = {}
    for fam in FAMILIES:
        donor = fam["src_dir"].rsplit("/", 1)[-1]
        dst_dir = f"battle/effect/skill_unique/{CODE}_{fam['subdir']}"
        want = next(c for c in design["effects"]["clone"] if c["id"] == fam["id"])
        if (want["src_dir"].rstrip("/"), want["dst"].rstrip("/"), tuple(want["fx_names"])) != (fam["src_dir"], dst_dir, fam["fx"]):
            raise KitError(f"effect family {fam['id']} drifted from design")
        transform = _png_transform_for(f"{fam['src_dir']}/{donor}.png",
                                       f"{dst_dir}/{dst_dir.rsplit('/', 1)[-1]}.png", dyed, fx_log)
        result = ctx.clone_effect_family(fam["src_dir"], fam["subdir"], fx_names=list(fam["fx"]),
                                         layout="sibling", png_transform=transform)
        if result["dst_dir"] != dst_dir or result["missing_effects"] or sorted(result["copied_bases"]) != sorted(fam["fx"]):
            raise KitError(f"effect clone incomplete for {fam['id']}: {result['missing_effects']}")
        if transform is not None:
            # 框架 clone 经 png_store_bytes（PIL optimize 重编码）写 sheet：逐像素 = 染色 PNG，字节 ≠ 产物存储态。
            # 改写为染色 PNG 的存储态原字节（owner 仍 effects），使包内 sha = 复核过的染色产物存储态 sha。
            dst_sheet = f"{dst_dir}/{dst_dir.rsplit('/', 1)[-1]}.png"
            sheet_root = next(f["root"] for f in result["files"] if f["target"] == dst_sheet)
            hits = [e for e in fx_log if e["target_sheet"] == dst_sheet]
            if len(hits) != 1:
                raise KitError(f"png_transform for {dst_sheet} ran {len(hits)} times (expected 1)")
            target = hits[0]
            exact = fx_store_bytes(Path(target["file"]))
            framework_bytes = ctx.pack.pkg_path(sheet_root, dst_sheet).read_bytes()
            if ctx.png_open(exact).tobytes() != ctx.png_open(framework_bytes).tobytes():
                raise KitError(f"fx store bytes decode differently from png_transform output: {dst_sheet}")
            ctx.write_asset(sheet_root, dst_sheet, exact, owner="effects")
            target.update({"package_sheet": dst_sheet, "root": sheet_root, "store_sha256": _sha(exact),
                           "framework_reencode_sha256": _sha(framework_bytes)})
        families[fam["id"]] = result
    matched = {e["source_sheet"] for e in fx_log} | {e["target_sheet"] for e in fx_log}
    stray_dyed = sorted(set(dyed) - matched)
    if stray_dyed:                                   # 路径写错 = 静默不装，直接拦
        raise KitError(f"fx manifest sheets match no cloned family: {stray_dyed}")
    if dyed and len(fx_log) != len(FAMILIES):
        notes.append(f"fx manifest 只覆盖 {len(fx_log)}/{len(FAMILIES)} 族 sheet，其余仍为官方原色")
    if fx_log:
        notes.append("特效 sheet 已装入 Effects 阶段染色产物（fx/zantetsu/out/manifest.json sha256="
                     f"{fx_manifest_info['sha256'][:12]}…）：" + "；".join(
                         f"{e['target_sheet']} ← {Path(e['file']).name}（存储态 {e.get('store_sha256', '?')[:12]}…，"
                         "alpha 逐字节不变）" for e in fx_log))
    # ---- 5b. 像素小人（修复轮复核 PASS 的染色 sheet，owner=pixel；未就绪时不写）
    pixel = install_pixel(ctx)
    if pixel["status"] == "installed":
        notes.append("像素小人：pixel/zantetsu/out 两张染色 sheet 已按存储态装包（owner=pixel，PNG 字节不重编码；"
                     "尺寸/alpha/透明像素 = 母本 smr22，atlas/frame/timeline 保持母本仅改路径前缀）："
                     + "；".join(f"{lg}（{v['store_sha256'][:12]}…）" for lg, v in pixel["sheets"].items()))
    else:
        notes.append("像素小人 pending（包内仍为母本像素）：" + "；".join(pixel["problems"][:4]))
    if not dyed:
        notes.append("fx/zantetsu/out/manifest.json 不存在：特效 sheet 仍是官方原色（Effects 阶段产出后重跑 kit 即自动装入）")
    ittou = families["S1_ittou"]
    hit_logical = f"{ittou['dst_dir']}/{HIT_TIMELINE_BASE}.timeline.amf3.deflate"
    hit_root = _family_root(ittou)
    hit_tree = ctx.amf_parse(ctx.pack.pkg_path(hit_root, hit_logical).read_bytes())
    sounds = [s for s in hit_tree.get("sounds") or [] if isinstance(s, dict) and s.get("path") == SE_FROM]
    if len(sounds) != 1:
        raise KitError(f"hit timeline SE {SE_FROM} not found exactly once")
    if ctx.pack.live_locate(SE_TO + ".mp3") is None:
        raise KitError(f"target SE mp3 absent from live store: {SE_TO}")
    sounds[0]["path"] = SE_TO
    ctx.write_asset(hit_root, hit_logical, ctx.amf_bytes(hit_tree), owner="kit")

    # ---- 6. 三棵树：两档技能（官方基线拼装 → 改版 delta → 特效重定向）+ 629 剑 PF（官方 knight_lv3）
    trees: dict[str, Any] = {}
    dsl_report: dict[str, Any] = {}
    reference_trees = revision_reference_trees(root)
    for level in (1, 2):
        donors = {}
        for code in (D2_CODE, D1_CODE):
            program = DONOR_PROGRAM.format(code=code, level=level)
            logical = wf_dsl.dsl_logical(program)
            official = ctx.official_read(logical, "common")
            live = ctx.live_read(logical)
            if official is None:
                raise KitError(f"official baseline lacks donor DSL {logical}")
            if _sha(official) != _sha(live):
                notes.append(f"donor DSL {logical} live != official; official used")
            donors[code] = ctx.amf_parse(official)
        base = compose_tree(donors[D2_CODE], donors[D1_CODE], level)
        proposal_path = root / PROPOSAL_REL.format(level=level)
        proposal_equal = None
        if proposal_path.is_file():                  # 上一轮提案（特效改写后）：compose_tree 未漂移的回归基准
            rewritten = copy.deepcopy(base)
            for fam_id in ("S2_kanbai", "S1_ittou"):
                rewritten, _r = ctx.rewrite_effect_refs(rewritten, families[fam_id], strict=True)
            proposal_equal = json.loads(proposal_path.read_text(encoding="utf-8")) == rewritten
            if not proposal_equal:
                raise KitError(f"composed tree {level} differs from design proposal_tree_{level}.json "
                               "(改版 delta 之前就已漂移)")
        tree = revise_tree(base, level, plan)
        revision_equal = None
        if reference_trees is not None:              # 改版探针树（特效改写前）：逐节点比对
            revision_equal = reference_trees[level] == tree
            if not revision_equal:
                raise KitError(f"revised tree {level} differs from revision dsl_validated.json")
        refs = {}
        for fam_id in ("S2_kanbai", "S1_ittou"):
            tree, refs[fam_id] = ctx.rewrite_effect_refs(tree, families[fam_id], strict=True)
        raw = ctx.amf_bytes(tree)
        gate = dsl_gates(tree, raw, level, root)
        gate["effect_refs"] = refs
        gate["design_proposal_equal"] = proposal_equal
        gate["revision_reference_equal"] = revision_equal
        if _dsl_gate_failed(gate):
            raise KitError(f"skill tree {level} gates failed: " + json.dumps(gate, ensure_ascii=False)[:1500])
        logical = ctx.write_dsl(ctx.program_path(str(level)), tree)
        trees[logical] = tree
        dsl_report[logical] = gate

    # 改版新增：能力1#3 的 629 剑 PF 动作树（官方特效路径，不随角色克隆）
    pf = build_pf_action_tree(root, plan)
    pf_gate = dsl_gates(pf, ctx.amf_bytes(pf), PF_LEVEL, root)
    pf_gate["revision_reference_equal"] = None if reference_trees is None else reference_trees[PF_LEVEL] == pf
    if pf_gate["revision_reference_equal"] is False:
        raise KitError("PF tree differs from revision dsl_validated.json")
    if _dsl_gate_failed(pf_gate):
        raise KitError("PF tree gates failed: " + json.dumps(pf_gate, ensure_ascii=False)[:1500])
    pf_logical = ctx.write_dsl(PF_PROGRAM, pf)
    trees[pf_logical] = pf
    dsl_report[pf_logical] = pf_gate

    effect_refs = effect_reference_problems(ctx, trees)
    se_checks = [c for fam in families.values() for c in timeline_se_problems(ctx, fam)]
    if effect_refs["problems"] or not all(c["ok"] for c in se_checks):
        raise KitError("effect reference gates failed: "
                       + json.dumps({"refs": effect_refs["problems"],
                                     "se": [c for c in se_checks if not c["ok"]]}, ensure_ascii=False))

    # ---- 7. 技能预览（smr22 版克隆，end_frame 300→420）
    _r, template_preview_raw, _src = ctx.pack.template_asset(TEMPLATE_PREVIEW)
    preview = ctx.amf_parse(template_preview_raw)
    if preview["config"]["end_frame"] != 300:
        raise KitError(f"template preview end_frame drifted: {preview['config']['end_frame']}")
    preview["config"]["end_frame"] = PREVIEW_END_FRAME
    ctx.write_asset("common", PREVIEW, ctx.amf_bytes(preview), owner="kit")

    # ---- 8. 认领核对：框架克隆但本 kit 不用的键撤销（本角色预期为空）
    unclaimed = []
    for claim in ctx.pack.load_claims():
        if claim["logical_path"] == CAS:
            stray = [k for k in claim["outer_keys"] if k not in CAS_KEYS]
            if stray:
                ctx.unclaim(CAS, stray)
                unclaimed.append({"table": CAS, "keys": stray})
        if claim["logical_path"] in (ACTION, SWITCHED):
            for item in claim.get("inner_keys", []):
                stray = [k for k in item["keys"] if k not in ("1", "2")]
                if stray:
                    ctx.unclaim(claim["logical_path"], inner_outer_key=item["outer_key"], inner_keys=stray)
                    unclaimed.append({"table": claim["logical_path"], "outer": item["outer_key"], "inner": stray})

    # ---- 9. 能力声明 + 证据 + 报告
    caps = sorted({c for gs in row_gates["ability"].values() for g in gs for c in g["required_client_capabilities"]}
                  | {c for g in row_gates["leader_ability"] for c in g["required_client_capabilities"]})
    if caps != sorted(REQUIRED_CAPABILITIES) or tuple(sorted(spec.required_capabilities)) != tuple(sorted(REQUIRED_CAPABILITIES)):
        raise KitError(f"row capabilities {caps} != declared {REQUIRED_CAPABILITIES} / spec {spec.required_capabilities}")
    doll = doll_color_checks(ctx.pack)
    if doll["problems"]:
        notes.append("小人同色核对未过（kit-report 保持 draft，gates 同样会拦）：" + "；".join(doll["problems"][:6]))
    voice = voice_state(ctx.pack)
    notes.append(f"语音：AI 合成配音 22 槽已装包（run={voice['run']}，speech 引用 home_0..5/join/evolution，母本旧语音已删）"
                 if voice["packed"] else
                 "语音 pending（kit 不写语音；装包后跑 impl/zantetsu/voice_merge.py）：" + "；".join(voice["problems"][:4]))
    fingerprint_parts = kit_fingerprint_parts(ctx.pack)
    fingerprint = _sha("\n".join(fingerprint_parts).encode("utf-8"))
    kit_gates = {
        "kit_fingerprint": fingerprint, "kit_fingerprint_parts": fingerprint_parts,
        "rows": row_gates, "records": rows["records"], "dsl": dsl_report,
        "effect_references": effect_refs, "timeline_sounds": se_checks,
        "fx_manifest": fx_manifest_info, "fx_ingested": fx_log, "doll_colors": doll,
        "pixel": pixel, "voice": voice,
        "required_capabilities": caps, "unclaimed": unclaimed,
        "mirrors": {"server_character": mirrors["server_character"]},
    }
    ctx.evidence_write("kit-gates.json", kit_gates)

    gates_path = root / IMPL_REL / "gates.json"
    prior = json.loads(gates_path.read_text(encoding="utf-8")) if gates_path.is_file() else {}
    ready = (bool(prior.get("all_pass")) and prior.get("kit_fingerprint") == fingerprint
             and prior.get("kit_source_sha256") == kit_source_sha256() and not doll["problems"]
             and pixel["status"] == "installed" and voice["packed"])
    panel = ["队长 L%d：%s" % (i + 1, g["describe"]) for i, g in enumerate(row_gates["leader_ability"])]
    for key, gs in row_gates["ability"].items():
        for i, g in enumerate(gs):
            panel.append(f"词条 {key}#{i + 1}：{g['describe']}")
    notes += [
        "改版 20260916：行清单真源是 revision-20260916/zantetsu/plan.json（第一轮，已在 1.4.878 上线）"
        " + revision2-20260916/zantetsu/plan2.json（第二轮增量：新增 1 条队长行 + 文案改写）"
        "⇒ 队长 8 条、词条 15 条；槽4 第1条仍是上线中的 F1/507 行"
        f"（donor=live {CID}4#1，无改动）。",
        "第二轮新增队长 L7：光共鸣 + instant_trigger 141 SkillGauge（puller 0、阈值 ≥1、上限 20 次、CT 0）"
        "→ 自身 技能伤害 25%→50%，满级累计 20×50% = 1000%（作者原话「最大 1000%」；面板由客户端渲染成"
        "「（上限 20 次）」+ 当前等级单值）。触发形沿用本角色能力3 第1条已上线的 141。"
        "先例：官方队长表 141 零行、live 队长表 1 行（139997#9，已上线并经作者试玩）；"
        "官方词条 2110036#1 就是「技能槽≥1(限12次) → 自身 技能伤害」逐格同义（只差表列位）。"
        "语义实锤：InstantAbilityTriggerMasterValueTools case 141 → CharacterCount(puller,10,阈值)，"
        "计数器 10 只由 MemberImpl._addSkillPoint 的 countUp(_,10,1,true) 递增（能力/效果/DSL 给的技能槽），"
        "普通弹射充能走 MemberImpl 里的 skillPoint.add 不计数 ⇒ 不会被每次命中刷爆。"
        "退路：真机若不触发，把同一行搬进词条槽 3（该键已有一条 141 在线），按 leader→ability 列位重排。",
        "第一轮发布后 3 条自引用 live 的 donor 已重锚（revision2 的 donor_retargets）："
        "队长 Fever 行改成按内容定位（每发一次都会顺延一位，写死序号越发越错）、"
        "能力6 两条的 edits_before 改成当前 live 实际值（donor 现在就是第一轮的产物）；"
        "row_final 逐格比对不变，锚错照样红。",
        "「随移动剧烈增加」实现为队长 L1/L2 的连击成长形 instant_trigger 12 Combo（每 30 连击、限 10 次、"
        "累计 +330% 攻击力 / +400% 技能伤害）：连击是本作里唯一可读的「移动剧烈程度」量表，"
        "客户端 ThresholdComboListener.update 每跨过一个阈值倍数就触发一次；live 队长表同形 27 行。"
        "引擎没有任何真正的移动量读数（DuringBattleAbilityThresholdKind / CharacterFloatParameterKind / "
        "BattleFloatParameterKind 三张量表均无 Distance/Move 项，92 SpeedUp 官方+live 全表 0 行）。"
        "复审修正：上一版把这两条做成 during_trigger 30（贯穿状态门）的定额提升，开局与技能间隙为 0，已推翻。",
        "队长 L8（第二轮之前是 L7）= live 已上线的「Fever 中 → 赋予全队(光) 技能伤害 100%」原样保留"
        "（edits 为空、按内容定位）：上一版以「客户端队长表上限 6 条」为由删掉它，该上限是伪约束"
        "（live 每键实测最大 15 条、官方最大 8 条），作者本轮也没有要求删除 Fever 轴。",
        "面板文案规则（作者 2026-09-16 晚补充）：① 没有上限的成长不写「无上限」——本角色玩家可见文案里"
        "该词出现 0 次（能力3 的三条 250 连击行、能力6 第1条限次写 (None)，客户端在 trigger_limit=(None) 时"
        "什么都不渲染，ui_string 只有 ability_description_instant_trigger_limit_n_times 一个上限串）；"
        "② 技能强化条目不写数字与秒——change_skill 文案改成「强化『超振动斩铁剑·寒梅一闪』的威力与"
        "「光属性抗性降低效果」」。两条都有 kit 门禁 text_rule_problems + 阴性对照测试。",
        "629 剑 PF 只把当前连击换算进伤害（CreateNormalAttack#8 enablesComboBonus，×(1+连击×0.005)），"
        "不消耗/清零连击：DSL 命令白名单里没有任何消耗连击的命令，真正的拍板才会 comboCalculator.expire()。",
        "一刀两断「RP1 为原点的 RP 再移动」是零先例组合（设计金丝雀②），退路=CRP8 node[1] 1→-18、node[4] 300→0。",
        "custom_ability_power_up_string 未写：客户端缺键按等级 1 处理不崩（CustomAbilityPowerUpStringTools），设计未要求。",
        "静态门禁 ≠ 真机验收。",
    ]
    report = {
        "summary": "斩铁·白梅 kit（改版 20260916 两轮）：23 行（15 词条+8 队长）、两棵拼装技能树 + 1 棵 629 剑 PF 树、"
                   "两族特效克隆（染色 sheet 存储态）、语音路由、预览 420 帧；像素小人 "
                   + ("已装包" if pixel["status"] == "installed" else "pending")
                   + "；AI 语音 " + ("已装包" if voice["packed"] else "pending"),
        "status": "ready-for-review" if ready else "draft",
        "skills": {"programs": sorted(trees)},
        "required_capabilities": list(REQUIRED_CAPABILITIES),
        "panel": panel,
        "notes": notes,
        "kit_fingerprint": fingerprint,
        "gates": str(gates_path),
    }
    ctx.report(report)
    return {"status": report["status"], "kit_fingerprint": fingerprint, "programs": sorted(trees),
            "effects": {k: v["dst_dir"] for k, v in families.items()}, "fx_ingested": len(fx_log),
            "pixel": pixel["status"], "voice_packed": voice["packed"],
            "unclaimed": unclaimed, "notes": notes}


# ======================================================================== 离线门禁 CLI

def run_gates() -> dict[str, Any]:
    """从包内现状复跑门禁（行/树/特效/描述/能力声明）+ 读 flow inspect 证据；结果写 impl/zantetsu/gates.json。
    全过 → 把 evidence/kit-report.json 置 ready-for-review（之后需重跑 --step manifest,status 刷新快照）。"""
    import wf_client_legality as L
    import wf_mod_tool as core
    import wf_seasonal7_build as B
    import wf_seasonal7_common as C
    import wf_seasonal7_specs as S
    spec = S.get_spec(KEY)
    pack = C.S7Pack(spec)
    ctx = B.KitContext(pack)
    root = pack.root
    impl = root / IMPL_REL
    impl.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []

    cas_keys = set(pack.pkg_flat(CAS)) if pack.pkg_has("common", CAS) else set()
    ability_rows = {k: C.csv_split(v) for k, v in pack.pkg_flat(ABILITY).items() if k in KIT_TABLE_KEYS[ABILITY]}
    leader_rows = C.csv_split(pack.pkg_flat(LEADER)[CID])
    rows = {"leader_ability": {CID: [row_gate("leader_ability", r, cas_keys) for r in leader_rows]},
            "ability": {k: [row_gate("ability", r, cas_keys) for r in ability_rows[k]] for k in sorted(ability_rows)}}
    if sorted(ability_rows) != list(KIT_TABLE_KEYS[ABILITY]):
        failures.append(f"ability keys in package {sorted(ability_rows)}")
    for kind, table in rows.items():
        for key, gs in table.items():
            for i, g in enumerate(gs):
                if _row_gate_failed(g):
                    failures.append(f"{kind} {key}#L{i}: row gate")
    design, plan = load_revised_design(root)
    expected = revision_rows(ctx, plan)
    if [list(r) for r in leader_rows] != expected["leader"] or {k: [list(r) for r in v] for k, v in ability_rows.items()} != expected["abilities"]:
        failures.append("package ability/leader rows differ from revision plan replay")
    for key in CAS_KEYS:
        if key not in cas_keys:
            failures.append(f"{key} missing from package custom_ability_string")

    row_caps = sorted({c for table in rows.values() for gs in table.values() for g in gs
                       for c in g["required_client_capabilities"]})
    manifest = json.loads((pack.package / "manifest.json").read_text(encoding="utf-8"))
    manifest_caps = sorted(manifest.get("required_capabilities") or [])
    if row_caps != manifest_caps:
        failures.append(f"manifest required_capabilities {manifest_caps} != row patch kinds {row_caps}")
    cas_caps = sorted({c for k in cas_keys if k in CAS_KEYS for c in L.required_client_capabilities(L.CUSTOM_ABILITY_STRING_KIND, [k])})
    if cas_caps:
        failures.append(f"custom_ability_string keys need panel capability {cas_caps}")

    dsl = {}
    trees = {}
    reference_trees = revision_reference_trees(root)
    for level in (1, 2, PF_LEVEL):
        program = PF_PROGRAM if level == PF_LEVEL else ctx.program_path(str(level))
        logical = C.wf_dsl.dsl_logical(program)
        if not pack.pkg_has("common", logical):
            failures.append(f"package lacks DSL program {program}")
            continue
        raw = pack.pkg_path("common", logical).read_bytes()
        tree = C.amf_parse(raw)
        gate = dsl_gates(tree, raw, level, root)
        if reference_trees is not None:
            # 包内树的特效引用已重定向到克隆目录；逐字还原成官方路径后与改版探针树逐节点比对
            gate["revision_reference_equal"] = reference_trees[level] == unrewrite_effect_refs(tree)
            if not gate["revision_reference_equal"]:
                failures.append(f"tree {level} differs from revision dsl_validated.json")
        if _dsl_gate_failed(gate):
            failures.append(f"tree {level}: dsl gate")
        dsl[logical] = gate
        trees[logical] = tree
    effect_refs = effect_reference_problems(ctx, trees)
    if effect_refs["problems"]:
        failures.append("effect references unresolved")
    families = pack.read_evidence("effect-families.json", {}) or {}
    se_checks = []
    for fam in FAMILIES:
        dst = f"battle/effect/skill_unique/{CODE}_{fam['subdir']}"
        entry = families.get(dst)
        if entry is None:
            failures.append(f"effect family not registered: {dst}")
            continue
        entry = dict(entry, files=[{"root": "common"}])
        se_checks += timeline_se_problems(ctx, entry)
    if not all(c["ok"] for c in se_checks):
        failures.append("timeline SE unresolved")
    hit = [c for c in se_checks if c["timeline"].endswith(f"{HIT_TIMELINE_BASE}.timeline.amf3.deflate")]
    if [c["se"] for c in hit] != [SE_TO]:
        failures.append(f"hit timeline SE not rewritten: {[c['se'] for c in hit]}")
    fx_sheets = fx_sheet_checks(pack)
    for check in fx_sheets["sheets"]:
        if check["problems"]:
            failures.append(f"fx sheet {check['sheet']}: {check['problems']}")

    act = core.load_nested_table_bytes(pack.pkg_path("common", ACTION).read_bytes(), ACTION).rows[CODE].text_rows()
    sw = core.load_nested_table_bytes(pack.pkg_path("common", SWITCHED).read_bytes(), SWITCHED).rows[VOICE_READY].text_rows()
    action = {k: C.csv_split(v)[0] for k, v in act.items()}
    switched = {k: C.csv_split(v)[0] for k, v in sw.items()}
    if sorted(action) != ["1", "2"] or any(switched.get(k) != action[k][7:24] for k in action):
        failures.append("switched_action_skill rows != action_skill c7..c23")
    crow = pack.pkg_character_row()
    if crow[9:17] != ROUTE_COLS:
        failures.append(f"character c9-16 {crow[9:17]} != route {ROUTE_COLS}")
    import wf_seasonal7_voice as V
    try:
        V.route_character_row(crow, V.normalize_route({"columns": ROUTE_COLS}, CODE), CODE)
        V.switched_rows({k: action[k] for k in ("1", "2")})
    except ValueError as exc:
        failures.append(f"voice pack_voice column contract: {exc}")
    if pack.pkg_character_text_row() != design["text"]["character_text_row"]:
        failures.append("character_text row != design character_text_row")
    mirror = json.loads(pack.pkg_path("server", "cdndata/character.json").read_bytes()).get(CID)
    if not (isinstance(mirror, list) and mirror and mirror[0] == crow):
        failures.append("server cdndata/character.json mirror != package character row (sync_character_mirrors)")
    if pack.pkg_flat(UPSKILL).get(CID) != design["identity"]["explicit_rows"][UPSKILL]["value"]:
        failures.append("upskill row != design")
    want_cas = {c["key"]: c["value"] for c in design["custom_strings"] if c["table"] == CAS}
    for key in CAS_KEYS:
        if C.csv_split(pack.pkg_flat(CAS).get(key, "")) != [[want_cas[key]]]:
            failures.append(f"custom_ability_string {key} text != revision plan")
    # 面板文案规则（作者 2026-09-16 晚补充）：按**包内实际文案**复查，而不是只查 design
    pkg_design = copy.deepcopy(design)
    pkg_cas = pack.pkg_flat(CAS)
    for entry in pkg_design["custom_strings"]:
        if entry["table"] == CAS and entry["key"] in pkg_cas:
            entry["value"] = C.csv_split(pkg_cas[entry["key"]])[0][0]
    pkg_design["text"] = dict(pkg_design["text"], character_text_row=list(pack.pkg_character_text_row()))
    text_rules = {"problems": text_rule_problems(pkg_design), "banned_words": list(TEXT_RULE_BANNED),
                  "texts": player_visible_texts(pkg_design)}
    for problem in text_rules["problems"]:
        failures.append(f"panel text rules: {problem}")
    claims = {(c["root"], c["logical_path"]): c for c in pack.load_claims()}
    for logical, keys in KIT_TABLE_KEYS.items():
        claim = claims.get(("common", logical))
        if claim is None or not set(keys) <= set(claim["outer_keys"]):
            failures.append(f"claim missing for {logical} {keys}")
    for logical, outer in KIT_NESTED_KEYS.items():
        claim = claims.get(("common", logical))
        inner = {i["outer_key"]: i["keys"] for i in (claim or {}).get("inner_keys", [])}
        if claim is None or sorted(inner.get(outer, [])) != ["1", "2"]:
            failures.append(f"nested claim missing for {logical}#{outer}")
    stance = stance_detail_check(ctx, design)
    if stance["reverted_by_tables"]:
        failures.append(f"stance_detail {stance['package']!r} = 框架 tables 按母本 151117 回写值（tables 在 kit 之后运行）："
                        f"按 tables → kit → assets → manifest → status 重跑 --step kit，恢复设计 {stance['design']!r}")
    elif not stance["ok"]:
        failures.append(f"stance_detail {stance['package']!r} != design {stance['design']!r}")
    doll = doll_color_checks(pack)
    for problem in doll["problems"]:
        failures.append(f"doll colors: {problem}")
    pixel_problems = pixel_package_problems(pack)
    for problem in pixel_problems:
        failures.append(f"pixel: {problem}")
    voice = voice_state(pack)
    for problem in voice["problems"]:
        failures.append(f"voice: {problem}")
    preview = C.amf_parse(pack.pkg_path("common", PREVIEW).read_bytes())
    if preview["config"]["end_frame"] != PREVIEW_END_FRAME:
        failures.append("skill preview end_frame not 420")
    owned = pack.owned_outputs()
    if owned.get(f"common:{PREVIEW}") != "kit":
        failures.append("skill preview not registered as kit output")

    inspect = pack.read_evidence("flow-inspect.json", {}) or {}
    summary = inspect.get("summary") or {}
    flow = {"master_reference": summary.get("master_reference"), "preflight": summary.get("preflight"),
            "structurally_ready": summary.get("structurally_ready"), "errors": summary.get("errors"),
            "missing_required": summary.get("missing_required"),
            "three_layer_claim_status": summary.get("three_layer_claim_status")}
    mr = summary.get("master_reference") or {}
    if mr.get("problems") != [] or mr.get("missing") not in ([], None):
        failures.append(f"inspect master_reference problems={mr.get('problems')} missing={mr.get('missing')}")
    pre = summary.get("preflight") or {}
    # 批次级 live 漂移（别家键的共享表影子）在这里就地重算，不信 inspect 写下的旧字段。
    drift = foreign_shadow_conflicts(pack, summary) if summary else {"batch_live_drift_only": False,
                                                                     "checks": {"inspect_evidence_present": False}}
    flow["foreign_shadow_conflicts"] = drift
    if not (summary.get("structurally_ready") and pre.get("can_prepare") and pre.get("conflicts") == []):
        failures.append(INSPECT_NOT_READY)
    report_status = pack.read_evidence("status.json", None)
    manifest_report = pack.read_evidence("manifest_report.json", {}) or {}
    if manifest_report.get("validate_manifest") or any((manifest_report.get("reconcile") or {}).values()):
        failures.append("manifest gate problems")
    manifest_sha = _sha((pack.package / "manifest.json").read_bytes())
    if manifest_report.get("manifest_sha256") != manifest_sha:
        failures.append("manifest_report is stale (rerun --step manifest)")

    describe = {"leader_ability": {CID: [g["describe"] for g in rows["leader_ability"][CID]]},
                "ability": {k: [g["describe"] for g in gs] for k, gs in rows["ability"].items()}}
    (impl / "describe.json").write_text(_json(describe), encoding="utf-8")
    fingerprint_parts = kit_fingerprint_parts(pack)
    fingerprint = _sha("\n".join(fingerprint_parts).encode("utf-8"))
    kit_gates = pack.read_evidence("kit-gates.json", {}) or {}
    fingerprint_changes = None
    if kit_gates.get("kit_fingerprint") != fingerprint:
        if kit_gates.get("kit_fingerprint_parts"):
            fingerprint_changes = fingerprint_part_changes(kit_gates["kit_fingerprint_parts"], fingerprint_parts)
        failures.append("package kit outputs changed since last kit build (rerun --step kit)"
                        + (f": {fingerprint_changes}" if fingerprint_changes else ""))
    # 唯一可延后的红项：批次级 live 漂移（别家键的影子），由主控发布步序里的 flow rebase 清零。
    # 判据是机器算的（foreign_shadow_conflicts 七项全真），只要有一条冲突碰到自家键就仍然是阻塞项。
    blocking, deferred = split_deferred(failures, drift)
    result = {
        "character": KEY, "cid": CID, "code": CODE,
        # all_pass = 本角色自己的活全绿（阻塞项为空）；deferred 不为空时仍然不能直接发布，
        # 看 publishable_now（= 连批次级漂移也清零，rebase 之后才会变真）。
        "all_pass": not blocking, "publishable_now": not failures,
        "failures": failures, "blocking_failures": blocking, "deferred": deferred,
        "deferred_reason": ("批次级 live 漂移：包内共享表全表载荷在别家键上落后于链尾 "
                            f"{drift.get('validated_chain_tail')}；{drift.get('clears_by')}"
                            ) if deferred else None,
        "kit_fingerprint": fingerprint, "kit_fingerprint_changes_since_kit": fingerprint_changes,
        "kit_source_sha256": kit_source_sha256(),
        "manifest_sha256": manifest_sha,
        "override": {"slot4_record1": SLOT4_OVERRIDE, "note": "112 → F1 507（主控拍板，已在 live 上线）",
                     "revision": REVISION_REL, "revision2": REVISION2_REL},
        "text_rules": text_rules,
        "stance_detail": stance, "doll_colors": doll,
        "pixel": {"problems": pixel_problems, "inputs": pixel_inputs(root)}, "voice": voice,
        "rows": rows, "row_required_capabilities": row_caps, "manifest_required_capabilities": manifest_caps,
        "dsl": dsl, "effect_references": effect_refs, "timeline_sounds": se_checks, "fx_sheets": fx_sheets,
        "flow_inspect": flow, "status_json_present": report_status is not None,
        "describe": str(impl / "describe.json"),
    }
    (impl / "gates.json").write_text(_json(result), encoding="utf-8")
    report = pack.read_evidence("kit-report.json", None)
    if isinstance(report, dict):
        # 按**阻塞项**置状态：wf_seasonal7_build.step_preflight 会拒绝 status='draft' 的包
        # （"refusing sealing preflight on a draft package"），而主控的发布步序第一步正是那次封存 preflight。
        # 只因别家键的影子漂移就把本包钉成草稿，等于把它挡在自己的发布步序之外。
        report["status"] = "ready-for-review" if not blocking else "draft"
        pack.write_evidence("kit-report.json", report)
    return {"all_pass": not blocking, "publishable_now": not failures,
            "failures": failures, "blocking_failures": blocking, "deferred": deferred,
            "gates": str(impl / "gates.json"), "kit_fingerprint": fingerprint}


# ======================================================================== 框架缺口规避：发布后的 inspect

PKG_ARCHIVE_DIRNAME = "pkgarchive"                # <仓库父目录>/pkgarchive/<package_id>-<链号>/

INSPECT_NOT_READY = "inspect: flow preflight not structurally ready"
BATCH_DRIFT_ERROR = "package preflight 尚未达到发布条件"


def foreign_shadow_conflicts(pack, summary: dict[str, Any]) -> dict[str, Any]:
    """把 flow preflight 的不就绪分成「别家键的共享表影子漂移」与「碰到自家键」两堆。

    本批 7 个角色串行发布：本包的共享表全表载荷停在 zantetsu 自己的发布点 1.4.878，
    之后 879–882 又发了四个角色，于是**别家键**在包内落后于 live，preflight 报 ``unclaimed_change``。
    这是主控 publish 前 ``flow rebase`` 负责的事（记忆卡 wf-flow-serial-publish-order /
    wf-package-shadow-table-refresh），不是本角色的缺陷。

    判定只在**全部**条件成立时才给 ``batch_live_drift_only=True``（宁可误红不可误绿）：
    冲突表非空且每条都是 ``unclaimed_change``、没有一条碰到本角色的键或认领、
    错误只有「尚未达到发布条件」这一条、master_reference 干净、必需资产不缺、三层认领一致。
    与 tekuto / philia 两个包内的同名函数同口径（多加了后四项）。
    """
    pre = summary.get("preflight") or {}
    conflicts = pre.get("conflicts")
    claimed: dict[str, set[str]] = {}
    for claim in pack.load_claims():
        keys = claimed.setdefault(claim["logical_path"], set())
        keys.update(claim.get("outer_keys") or [])
        for inner in claim.get("inner_keys") or []:
            if inner.get("outer_key"):
                keys.add(inner["outer_key"])
    own, foreign, kinds = [], [], {}
    for item in conflicts or []:
        path, _, key = str(item.get("claim", "")).partition(":")
        outer = key.split("/", 1)[0]
        kinds[item.get("kind")] = kinds.get(item.get("kind"), 0) + 1
        mine = (CID in key or CODE in key or outer in claimed.get(path, set())
                or key in claimed.get(path, set()))
        (own if mine else foreign).append(item)
    errors = list(summary.get("errors") or [])
    mr = summary.get("master_reference") or {}
    three = summary.get("three_layer_claim_status") or {}
    checks = {
        "conflicts_is_nonempty_list": isinstance(conflicts, list) and bool(conflicts),
        "all_unclaimed_change": bool(conflicts) and set(kinds) == {"unclaimed_change"},
        "no_conflict_touches_this_character": not own,
        "errors_are_only_the_known_drift_error": errors == [BATCH_DRIFT_ERROR],
        "master_reference_clean": mr.get("problems") == [] and mr.get("missing") in ([], None),
        "no_missing_required": (summary.get("missing_required") or []) == [],
        "three_layer_consistent": bool(three.get("consistent")),
    }
    return {
        "total": len(conflicts or []), "foreign": len(foreign), "own": own,  # own 非空 = 碰到自家键 = 必红
        "kinds": kinds, "checks": checks,
        "batch_live_drift_only": all(checks.values()),
        "validated_chain_tail": pre.get("validated_chain_tail"),
        "foreign_keys": sorted({str(c.get("claim", "")) for c in foreign}),
        "clears_by": "主控按 wf-flow-serial-publish-order 的 preflight → rebase → preflight → publish 走，"
                     "rebase 一步清零；本任务被要求不发布，故真实 workspace 不在此处 rebase",
    }


def inspect_should_raise(rc: int, drift: dict[str, Any]) -> bool:
    """inspect 子命令是否该抛：rc=2 永远抛（真错）；其余非 0 只在**不是**纯别家漂移时抛。
    与框架 ``wf_seasonal7_build.step_inspect`` 的 rc 语义对齐（它同样只在 rc==2 抛）。"""
    return rc == 2 or (rc != 0 and not drift.get("batch_live_drift_only"))


def split_deferred(failures: list[str], drift: dict[str, Any]) -> tuple[list[str], list[str]]:
    """把红项分成阻塞项与可延后项。可延后的**只有** ``INSPECT_NOT_READY`` 一条，
    而且必须 ``foreign_shadow_conflicts`` 判定为纯批次级漂移；其余任何红项一律阻塞。"""
    deferred = [f for f in failures if f == INSPECT_NOT_READY and drift.get("batch_live_drift_only")]
    return [f for f in failures if f not in deferred], deferred


def installed_package_candidates(root: Path, pkg_id: str) -> list[Path]:
    """已发布包的归档目录（新→旧）。角色上线后 flow preflight 必须拿到 installed manifest，
    否则报 ``active ownership hash exists but installed manifest was not supplied``。"""
    base = root.parent / PKG_ARCHIVE_DIRNAME
    if not base.is_dir():
        return []
    def version_key(path: Path):
        tail = path.name[len(pkg_id) + 1:]
        parts = [int(x) for x in re.findall(r"\d+", tail)] or [0]
        return parts
    found = [d for d in base.iterdir()
             if d.is_dir() and d.name.startswith(pkg_id + "-") and (d / "manifest.json").is_file()]
    return sorted(found, key=version_key, reverse=True)


def run_inspect(installed_dir: str | None = None) -> dict[str, Any]:
    """``--step inspect`` 的替代（框架缺口，见返回里的报告）：把 workspace 复制出去跑 flow preflight，
    并补上框架没传的 ``--installed-package-dir``。只在副本里封存；真实 workspace 字节不变。
    结果写 ``evidence/flow-inspect.json``，形状与框架一致，``gates`` 照常读。"""
    import os
    import shutil
    import wf_seasonal7_build as B
    import wf_seasonal7_common as C
    import wf_seasonal7_specs as S
    spec = S.get_spec(KEY)
    pack = C.S7Pack(spec)
    pack.check_identity()
    root = pack.root
    candidates = ([Path(installed_dir)] if installed_dir
                  else installed_package_candidates(root, spec.pkg_id))
    guarded = [pack.package / "manifest.json", pack.evidence / "status.json", pack.evidence / "hash-cache.json"]
    before = {str(f): (f.read_bytes() if f.is_file() else None) for f in guarded}
    base = pack.batch_dir / B.INSPECT_DIR
    attempts: list[dict[str, Any]] = []
    rc, payload, used = None, None, None
    for candidate in candidates or [None]:
        copy_root = base / f"{KEY}-{os.getpid()}"
        if copy_root.exists():
            shutil.rmtree(copy_root)
        try:
            copy_root.mkdir(parents=True)
            workspace_copy = copy_root / pack.workspace.name
            shutil.copytree(pack.workspace, workspace_copy)
            extra = ["--profile", "cn"]
            if candidate is not None:
                extra += ["--installed-package-dir", str(candidate)]
            rc, payload = B._flow("preflight", workspace_copy, root, extra)
        finally:
            shutil.rmtree(copy_root, ignore_errors=True)
            try:
                base.rmdir()
            except OSError:
                pass
        errors = payload.get("errors") or []
        attempts.append({"installed_package_dir": None if candidate is None else str(candidate),
                         "returncode": rc, "errors": errors})
        used = candidate
        if not any("not hash-bound" in e or "different package_id" in e for e in errors):
            break
    after = {str(f): (f.read_bytes() if f.is_file() else None) for f in guarded}
    if after != before:
        raise KitError("inspect modified the real workspace")
    text = json.dumps(payload, ensure_ascii=False)
    for old, new in ((base / f"{KEY}-{os.getpid()}" / pack.workspace.name, pack.workspace),):
        text = text.replace(json.dumps(str(old))[1:-1], json.dumps(str(new))[1:-1])
    payload = json.loads(text)
    ready, reason = B.kit_readiness(pack)
    result = B._preflight_summary(rc, payload, pack, pack.workspace)
    result.update({"sealed_real_workspace": False, "sealed_copy_only": True, "kit_ready": ready,
                   "kit_reason": reason, "structurally_ready": rc == 0,
                   "flow_next_command": result.get("next_command"),
                   "installed_package_dir": None if used is None else str(used),
                   "installed_package_attempts": attempts,
                   "framework_gap": "wf_seasonal7_build.step_inspect 不传 --installed-package-dir，"
                                    "角色上线后（active ledger 已有 ownership hash）必然 rc=2；"
                                    "本 kit 的 inspect 子命令补上该参数，其余与框架一致"})
    drift = foreign_shadow_conflicts(pack, result)
    result["foreign_shadow_conflicts"] = drift
    pack.write_evidence("flow-inspect.json", {"summary": result, "payload": payload})
    # rc 语义与框架 step_inspect 对齐：2 = 真错（必抛）；3 = "还不能发布"。
    # 角色上线后 3 几乎必然出现，原因是别家键的共享表影子漂移（主控 rebase 负责）；
    # 只有当它**不是**纯别家漂移时才抛，否则 inspect 会把整条验收链钉死在一个不是本角色缺陷的状态上。
    if inspect_should_raise(rc, drift):
        raise KitError(f"flow preflight (inspect copy) rc={rc}: {payload.get('errors')}; "
                       f"foreign_shadow_conflicts={drift['checks']}")
    if rc != 0:
        result["deferred_batch_live_drift"] = (
            f"flow preflight rc={rc}：{drift['total']} 条 unclaimed_change 全部落在别家键"
            f"（链尾 {drift['validated_chain_tail']}），{drift['clears_by']}")
    return result


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] == ["inspect"]:
        installed = args[1] if len(args) == 2 else None
        if len(args) > 2:
            print("usage: python mod-tools/wf_seasonal7_kit_zantetsu.py inspect [<installed package dir>]")
            return 2
        result = run_inspect(installed)
        print(json.dumps(result, ensure_ascii=False, indent=1))
        return 0
    if args != ["gates"]:
        print("usage: python mod-tools/wf_seasonal7_kit_zantetsu.py gates|inspect [<installed package dir>]")
        return 2
    result = run_gates()
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0 if result["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
