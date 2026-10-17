# -*- coding: utf-8 -*-
'稻穗「秋灯雷华妖狐姬」（139995 fox_oracle_autumn）：2026-09-27 第二批追加（作者 09-27 追加）。\n\n作者原话（2026-09-27）：「秋九尾的能力1fever模式中自身发动技能除自身外的雷属性角色技能槽+5%添加ct5s,\n进入fever时自身余晖上升移动到能力3,fever模式中发动强化弹射雷属性角色技能槽+5%移动到能力3添加共鸣限制」。\n\n按 live 1.4.1051 推导（第一批改过能力3、第二批改过队长/能力4/双段 PF 之后）。行号 0 基（``#n``）。\n\n1. 能力1（1399951）#5「雷·编成≥6 且 Fever 时：技能发动≥1（trigger 23，puller c28=0 自身）→ 赋予除自身全员\n   （c48=1、c49=(None)）技能槽 5%」：CT c35 0 → 300（帧，5 秒），其余逐格不动。\n   雷共鸣（编成≥6）下全队都是雷属性，「除自身全员」即作者说的「除自身外的雷属性角色」，对象列不改。\n   官方同型（trigger 23 自身施技 → 211 带 CT）：2510085#0 / 2310442#0。\n2. 能力1 #3「雷·编成≥6 时：Fever≥1（trigger 8）→ 自身 状态固有 461（余辉 1399952 +1 层）」：从能力1 删除，\n   追加到能力3（1399953）末尾（#8）。只改 c0 → ``fox_oracle_autumn_3``、c1 true → false（跟能力3 整键），\n   触发/内容/数值/前置逐格保留。\n3. 能力1 #2「Fever 时（前置 12）：强化弹射 Lv3≥1（trigger 65）→ 赋予全队(雷) 技能槽 2.5%→5%」：从能力1 删除，\n   追加到能力3 末尾（#7），并加雷属性共鸣前置（kind 2 / 600000 / 600000 / Yellow）。\n   前置写法照同角色 live 行 1399951#5（本条改后仍在能力1 #3）：共鸣在前置1（c6）、Fever 挪到前置2（c13），\n   改后 c6–c26 前置块与该行逐字相同；官方同形 1511713#1 / 1511593#1 / 1511593#2 / 1511473#2\n   （c1=false、c6=2 共鸣、c13=12 Fever）。「Fever 在 c6、共鸣在 c13」官方与 live 均零先例，故不按「第一个空闲槽」写。\n   c0/c1 同第 2 条，触发/内容/数值逐格保留。\n\n整键主位：能力3 整键 c1=false（仅主位生效）。作者说「移动到能力3」即接受：搬过去的两行只在稻穗为主位时生效。\n- 余辉获得行：余辉的全部消费者都要求稻穗是队长——队长 during 134 每层行（#1/#4/#5/#6/#9）只在当队长时存在、\n  能力6 #1（余辉≥10 且非 Fever 时 PF → Fever 槽 +15%）带前置 42（仅队长）。队长必是主位，所以当队长时每次进\n  Fever 仍是「队长行 #10 + 能力3 #8」两源相加 +2 层（记忆卡 wf-fox-fever-afterglow-fix），层数与所有依赖行语义不变；\n  差别只在稻穗当合击副位时不再给（合击位「自身」= 主位角色）挂一个没人读取的余辉状态。\n- PF Lv3 充能行：由「任意位置、无共鸣」收窄为「主位 + 雷共鸣 + Fever」，这是作者要的限制。\n\n面板：能力1 / 能力3 都没有覆盖文案（``desc_override_fox_oracle_autumn_1`` / ``_3`` 在 live 不存在，客户端按行自动\n生成，行4 自动拼「（CT: 5 秒）」）；本模块确认两键仍不存在（存在即拒绝，fail closed），不写 cas。\n队长覆盖文案「每进入一次FEVER模式「余辉」累积1层」描述的是队长行 #10，本次未动，不改。\n\n生成器：1399951 / 1399953 没有可重跑的现行生成器。历史链（wf_inaho_fever_revision / wf_inaho_pf3_balance /\nwf_inaho_fever_growth_data / wf_inaho_growth_detail_data / wf_inaho_native_pf_r2）全部锁定历史输入哈希，\n对新旧两态重跑都拒绝；第一批 ``wf_balance_20260927_inaho.ability3_rows`` 锁 1.4.1049 前像，对现 live 同样拒绝。\n本模块是这两个键现行的唯一生成源（测试断言：live 1399953 == 第一批输出，本模块输出前 7 行 == 第一批输出）。\n\n候选（work/character_packs/fox_oracle_autumn）：1399953 与 live 逐字相同；1399951 候选 #5 c51/c52 仍是 10000\n（1.4.864 改成 5000 后未回写），本模块按 live 整键替换，回写后候选与 live 一致。\n\n跨单元（发布后 live 1399951 只剩 4 行，#2 起行号内容变了）：测试全仓扫描别的单元按 live 行号读 1399951 / 1399953\n的引用，发布后行内容会变的必须登记在 ``INDEXED_LIVE_REFERENCES``（登记的必须仍能扫到；状态含义见该常量）。\n两处 kit 已在 2026-09-27 修复轮改成与行号无关，发布前后回放逐字相同，**与本单元发布不再绑定**：\n- 秋水 soriz：``wf_gbf_kit_soriz.py`` 的 A3#8 content donor 改为 store 键 ``1399951`` 内按内容取（第一条 mode I、\n  ck=724；发布前在 #4、发布后在 #2，同一行逐字不变），设计镜像 ``midautumn-20260920/design/soriz.json`` 的标签同改为\n  ``store:ability[1399951]{mode=I,ck=724}``。扫描不再扫到 ⇒ 已移出登记表。**不要**改回 ``idx=2`` / ``#2``\n  （会重新按行号钉死，design_drift 也会报漂移）。\n- 泽赫尔 zehr：``seasonal7-20260916/revision-20260916/zehr/plan.json`` 的 donor ``ability LIVE:1399951#2``（带 old_values）\n  字符串保留（plan.json 是第一轮证据，不改写）；``wf_seasonal7_kit_zehr.FROZEN_DONORS`` 把它钉成发布前的 live 行\n  （逐格 + sha256），``donor_row`` 不再读 live ⇒ 登记为 ``pinned``。**不能**改指 1399953#7（该行 c0/c6/c9–c11/c13\n  已变，old_values 仍不匹配）。\n- 提交：本登记表（不含 soriz）与 soriz 按内容取的改动须同一批落地，分开提交时登记表测试会红（扫描结果与登记表必须一致）。\n- 暂存：``stage_batch.py`` 的 SNAPSHOT / evidence_name 对第二批所有单元共用（``revision_20260927b`` /\n  ``revision-20260927b.json``），本单元暂存会整份覆盖稻穗第二批的回写证据与 manifest.snapshot 条目；由编排者决定\n  改用独立键（如 ``revision_20260927b_inaho2``）或先归档现有证据。本模块不暂存，不处理。\n\n纯函数：只转换 ``read()`` 给出的 live 输入，不写任何文件；候选回写、发布由批次暂存脚本统一做\n（接口见 ${WF_ROOT}/out/平衡调整批次-20260927/module_contract.md，第二批 b 后缀）。\n'
from __future__ import annotations

from copy import deepcopy
import hashlib
import json

import wf_client_description_legality as description
import wf_client_legality as legality

CID = "139995"
CODE = "fox_oracle_autumn"
PACKAGES = ["fox_oracle_autumn"]
#: 候选 manifest 现值 0.20260927.1（第二批 wf_balance_20260927b_inaho 回写）→ 递增。
PACKAGE_VERSION = {"fox_oracle_autumn": "0.20260927.2"}
#: 返回的 1399951 仍含 724 行（#2，Fever 中 PF 扣 Fever 槽），依赖该补丁；候选 manifest 已登记，这里声明以便门禁核对。
CAPABILITIES = ["kyubi-fever-ratio-v1"]
#: 候选 manifest 自身零哈希漂移。
REVIEWED_DRIFT: dict = {}
ELEMENT = 2  # master/character c3：雷（0 基内部元素）

ABILITY1, ABILITY3, ABILITY6 = f"{CID}1", f"{CID}3", f"{CID}6"
LEADER = CID
AFTERGLOW = "1399952"  # 固有「余辉」（unique_condition c4=99）
A1_ID, A3_ID = f"{CODE}_1", f"{CODE}_3"

#: 别的工作单元按「live 行号」读 1399951 / 1399953、且本次发布后该行号内容会变的全部引用
#: （测试扫描 mod-tools/*.py 与 work/character_packs 的 design/*.json、plan.json：会变的引用必须登记，登记的必须仍能扫到）。
#: "edit" = 所属单元须与本单元发布同批修改（须列进 notes.needed_edits_elsewhere；现无）；
#: "pinned" = 引用字符串保留，所属 kit 已把该 donor 钉成发布前的冻结行（带 sha256），回放不读 live；
#: "reference_only" = 上一轮基线 / 说明，kit 不重放它。
#: 秋水 soriz 的 A3#8 donor 已改为键内按内容取（不带行号），扫描不到，故不在表内。
INDEXED_LIVE_REFERENCES = {
    ("work/character_packs/seasonal7-20260916/revision-20260916/zehr/plan.json", ABILITY1, 2): "pinned",
    ("work/character_packs/seasonal7-20260916/design/zehr.json", ABILITY1, 2): "reference_only",
    ("work/character_packs/seasonal7-20260916/design/regis.json", ABILITY1, 2): "reference_only",
}
#: 泽赫尔 plan.json 那条 donor 回放时逐格核对的旧值（/tables/ability/keys/1599975[1]）；测试用它证明发布后
#: 1399951#2 与搬走后的 1399953#7 都对不上（只能钉冻结行，不能改指；泽赫尔 kit 的 FROZEN_DONORS 已钉）。
ZEHR_DONOR_OLD_VALUES = {0: "fox_oracle_autumn_1", 2: "attack_yellow", 6: "12", 9: "", 10: "", 11: "",
                         49: "Yellow", 51: "2500", 52: "5000"}
#: 客户端按「desc_override_ + 首行 string_id」取覆盖；这两个键在 live 不存在 ⇒ 面板自动生成（存在即拒绝）。
AUTO_PANEL_KEYS = (f"desc_override_{A1_ID}", f"desc_override_{A3_ID}")

#: live 1.4.1051 只读取数（make_read(live_only=True)）；值 = digest(read(kind, key))。
#: 能力6 / 队长只读不改：用于核对余辉的消费者都要求队长（搬行不改变其语义）。
BEFORE = {
    ("ability", ABILITY1): "7fdc2bb8587ae3dc6353f0e339ba8d8e9e89c8ad3e2d1ed067672412eed22391",
    ("ability", ABILITY3): "1cc1620fbdfad73042d4ae4489ffa6ecba86264407b3e936d808bfd6d2a02dd5",
    ("ability", ABILITY6): "9da9c6491903b9150f4cb5701910594c5a1746459b3067a15f2b0d435bae6b98",
    ("leader", LEADER): "32f678eefb352cdbefc224e98fffe98186ffbfdc802ac9cd5bf42437898b3e8b",
}

WIDTH = 126
PRE1, PRE2, PRE3 = 6, 13, 20       # 前置块起点（各 7 列：kind, …, 阈值 +3/+4, 组 +5, …）
PRE_LEN = 7
TRIGGER, COOLTIME, CONTENT = 27, 35, 47

#: 能力1 live 行号。
PF3_ROW, GLOW_ROW, ALLY_ROW = 2, 3, 5
KEPT_A1_ROWS = (0, 1, 4)
MOVED = (PF3_ROW, GLOW_ROW)        # 按能力1 原顺序追加到能力3 末尾
CT_FRAMES = "300"                  # 5 秒（60 帧/秒；第一批能力3 #3 的 600 = 10 秒同单位）

RESONANCE = ("2", "", "", "600000", "600000", "Yellow", "")
FEVER = ("12", "", "", "", "", "", "")
EMPTY_PRE = ("0", "", "", "", "", "", "")

_HEAD = {0: A1_ID, 1: "true", 2: "attack_yellow", 3: "0", 5: "0"}
_TRIG = {30: "100000", 31: "100000", 34: "(None)", 35: "0", 39: "(None)", 46: "0"}
#: 三条要动的能力1 行的完整非空格前像（其余列必须为空）。
PREIMAGE = {
    PF3_ROW: {**_HEAD, **_TRIG, 6: "12", 13: "0", 20: "0", 27: "65",
              47: "211", 48: "5", 49: "Yellow", 51: "2500", 52: "5000"},
    GLOW_ROW: {**_HEAD, **_TRIG, 6: "2", 9: "600000", 10: "600000", 11: "Yellow", 13: "0", 20: "0",
               27: "8", 47: "461", 48: "0", 51: "100000", 52: "100000", 59: "100000", 60: "100000",
               68: AFTERGLOW, 74: "1", 75: "0"},
    ALLY_ROW: {**_HEAD, **_TRIG, 6: "2", 9: "600000", 10: "600000", 11: "Yellow", 13: "12", 20: "0",
               27: "23", 28: "0", 47: "211", 48: "1", 49: "(None)", 51: "5000", 52: "5000"},
}
#: 保留行的身份指纹（逐字保留，只核对内容 kind 防止错位）。
KEPT_A1_KINDS = {0: "211", 1: "226", 4: "724"}
A3_KINDS = ("56", "55", "388", "211", "", "226", "32")   # 第一批输出（#4 为持续·Fever 124）


class InahoAppendError(ValueError):
    """输入漂移或结构不符：拒绝修订（fail closed）。"""


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise InahoAppendError(f"{CID} balance 20260927b-2: {message}")


def _baseline(read) -> dict:
    """读取并锁定全部输入；任何一项漂移都拒绝（fail closed）。"""
    inputs = {}
    for kind, key in BEFORE:
        value = read(kind, key)
        if value is None or digest(value) != BEFORE[kind, key]:
            raise InahoAppendError(f"unreviewed live baseline: {kind}:{key}")
        inputs[kind, key] = deepcopy(value)
    for key in AUTO_PANEL_KEYS:
        try:
            present = read("cas", key) is not None
        except KeyError:
            present = False
        if present:
            raise InahoAppendError(f"live drift: cas:{key} now exists (panel is no longer auto-generated)")
    return inputs


def _matches(row: list[str], cells: dict) -> bool:
    return (len(row) == WIDTH
            and all(row[col] == value for col, value in cells.items())
            and all(value == "" for col, value in enumerate(row) if col not in cells))


def _block(row: list[str], start: int) -> tuple:
    return tuple(row[start:start + PRE_LEN])


def moved_row(row: list[str], *, add_resonance: bool) -> list[str]:
    """能力1 行 → 能力3 行：c0/c1 跟能力3；需要共鸣时写成「共鸣 c6 + 原前置1 挪到 c13」。"""
    out = list(row)
    out[0], out[1] = A3_ID, "false"
    if add_resonance:
        _require(_block(row, PRE1) == FEVER and _block(row, PRE2) == EMPTY_PRE,
                 "PF Lv3 row precondition is not the reviewed Fever-only shape")
        out[PRE1:PRE1 + PRE_LEN] = RESONANCE
        out[PRE2:PRE2 + PRE_LEN] = FEVER
    return out


def ability_rows(a1: list[list[str]], a3: list[list[str]]) -> tuple[list[list[str]], list[list[str]]]:
    """返回 (新能力1, 新能力3)：能力1 删 #2/#3、#5 加 CT 5 秒；能力3 原 7 行逐字保留，末尾追加两行。"""
    a1, a3 = deepcopy(a1), deepcopy(a3)
    _require(len(a1) == 6 and all(len(r) == WIDTH and r[0] == A1_ID and r[1] == "true" for r in a1),
             "ability1 shape drift (expected 6 unisonable rows)")
    _require(len(a3) == len(A3_KINDS)
             and all(len(r) == WIDTH and (r[0], r[1]) == (A3_ID, "false") for r in a3),
             "ability3 shape drift (expected the 7 main-only rows of batch 1)")
    _require(tuple(r[CONTENT] for r in a3) == A3_KINDS, "ability3 content kinds drift")
    for index, cells in PREIMAGE.items():
        _require(_matches(a1[index], cells), f"unexpected preimage for ability1#{index}")
    for index, kind in KEPT_A1_KINDS.items():
        _require(a1[index][CONTENT] == kind, f"ability1#{index} content kind drift")

    moved = [moved_row(a1[PF3_ROW], add_resonance=True), moved_row(a1[GLOW_ROW], add_resonance=False)]
    # 头部列（c0–c4）与能力3 现有行一致。
    _require(all(row[:5] == a3[0][:5] for row in moved), "moved rows' header differs from ability3")
    # 共鸣写法与同角色 live 雷共鸣 + Fever 行（能力1 #5）的前置块逐字相同。
    _require(moved[0][PRE1:TRIGGER] == a1[ALLY_ROW][PRE1:TRIGGER], "resonance block differs from ability1#5")

    new_a1 = [a1[i] for i in range(len(a1)) if i not in MOVED]
    ally = new_a1[-1]
    _require(ally[COOLTIME] == "0", "ability1#5 already has a cooltime")
    ally[COOLTIME] = CT_FRAMES
    return new_a1, a3 + moved


def afterglow_dependencies(leader: list[list[str]], a6: list[list[str]],
                           new_a1: list[list[str]], new_a3: list[list[str]]) -> dict:
    """余辉 1399952 的来源与消费者；消费者必须都要求队长（队长表行，或能力行带前置 42）。"""
    gains, consumers = [], []
    for index, row in enumerate(leader):
        if row[45] == "461" and row[66] == AFTERGLOW:
            gains.append(f"leader#{index}")
        elif AFTERGLOW in row:
            consumers.append((f"leader#{index}", True))
    for key, rows in ((ABILITY1, new_a1), (ABILITY3, new_a3), (ABILITY6, a6)):
        for index, row in enumerate(rows):
            if row[CONTENT] == "461" and row[68] == AFTERGLOW:
                gains.append(f"{key}#{index}")
            elif AFTERGLOW in row:
                leader_gate = "42" in (row[PRE1], row[PRE2], row[PRE3])
                consumers.append((f"{key}#{index}", leader_gate))
    return {"gains": gains, "consumers": consumers}


def row_problems(kind: str, row: list[str]) -> list[str]:
    return (legality.client_legality_problems(kind, row)
            + legality.declared_block_field_problems(kind, row)
            + legality.invoke_skill_string_problems(row, set(), kind)
            + description.description_compatibility_problems(kind, row)
            + [f"needs undeclared client capability {cap}"
               for cap in legality.required_client_capabilities(kind, row) if cap not in CAPABILITIES])


def revise(read) -> dict:
    inputs = _baseline(read)
    new_a1, new_a3 = ability_rows(inputs["ability", ABILITY1], inputs["ability", ABILITY3])
    deps = afterglow_dependencies(inputs["leader", LEADER], inputs["ability", ABILITY6], new_a1, new_a3)
    problems = []
    if deps["gains"] != ["leader#10", f"{ABILITY3}#8"]:
        problems.append(f"afterglow gain sources drift: {deps['gains']}")
    if not deps["consumers"] or not all(gate for _, gate in deps["consumers"]):
        problems.append(f"afterglow consumer without a leader gate: {deps['consumers']}")
    problems += [f"ability {key}#{i}: {p}" for key, rows in ((ABILITY1, new_a1), (ABILITY3, new_a3))
                 for i, row in enumerate(rows) for p in row_problems("ability", row)]
    if problems:
        raise InahoAppendError("; ".join(problems))
    return {
        "ability": {ABILITY1: new_a1, ABILITY3: new_a3}, "leader": {}, "cas": {},
        "text": {}, "table": {}, "action": {}, "dsl": {}, "server_text": {}, "new_programs": [],
        "notes": _notes(deps),
    }


def _notes(deps: dict) -> dict:
    return {
        "source": "wf_balance_20260927b_inaho2.py",
        "spec": "作者 2026-09-27 追加：「秋九尾的能力1fever模式中自身发动技能除自身外的雷属性角色技能槽+5%添加ct5s,"
                "进入fever时自身余晖上升移动到能力3,fever模式中发动强化弹射雷属性角色技能槽+5%移动到能力3添加共鸣限制」",
        "change": {
            f"ability:{ABILITY1}#5": f"雷共鸣+Fever 自身施技 → 除自身全员技能槽 5%：CT c35 0 → {CT_FRAMES} 帧（5 秒）；"
                                    "c48=1/c49=(None) 不改（雷共鸣下除自身全员即除自身的雷属性角色）",
            f"ability:{ABILITY1}#3 → ability:{ABILITY3}#8": "进 Fever 自身余辉 +1（461 / 1399952）：c0 → fox_oracle_autumn_3、"
                                                          "c1 true → false，其余逐格保留",
            f"ability:{ABILITY1}#2 → ability:{ABILITY3}#7": "Fever 中 PF Lv3 → 全队(雷)技能槽 2.5%→5%：c0/c1 同上；"
                                                          "加雷共鸣（c6=2/600000/600000/Yellow），Fever 前置 12 由 c6 挪到 c13；"
                                                          "触发/内容/数值逐格保留",
            "row_counts": f"{ABILITY1} 6 → 4 行；{ABILITY3} 7 → 9 行（前 7 行逐字不变）",
        },
        "resonance_slot": "前置块照同角色 live 1399951#5（改后能力1 #3）与官方 1511713#1/1511593#1/1511593#2/1511473#2："
                          "共鸣 c6、Fever c13；「Fever c6 + 共鸣 c13」官方与 live 零先例，未按「第一个空闲前置槽」写",
        "main_slot": "能力3 整键 c1=false：搬入两行只在主位生效（作者「移动到能力3」即接受）",
        "afterglow_semantics": {
            "gains": deps["gains"],
            "consumers": [name for name, _ in deps["consumers"]],
            "reason": "余辉的消费者都要求稻穗是队长（队长 during 134 每层行 + 能力6 #1 前置 42）；队长必是主位，"
                      "当队长时每次进 Fever 仍是队长 #10 + 能力3 #8 两源相加 +2 层，逐层成长与 724 门槛语义不变；"
                      "只少了稻穗当合击副位时给主位角色挂一个无人读取的余辉",
        },
        "pf3_charge_semantics": "由任意位置、无共鸣收窄为主位 + 雷共鸣 + Fever（作者要的限制）",
        "panel": "desc_override_fox_oracle_autumn_1 / _3 在 live 不存在，客户端自动生成（能力1 #3 自动拼 CT 5 秒）；"
                 "队长覆盖文案描述的是队长 #10（未动），不改",
        "candidate_realigned": f"候选 {ABILITY1} #5 c51/c52 10000（1.4.864 改 5000 未回写），按 live 整键替换",
        "generators": "无现行生成器；wf_inaho_fever_revision / wf_inaho_pf3_balance / wf_inaho_fever_growth_data / "
                      "wf_inaho_growth_detail_data / wf_inaho_native_pf_r2 哈希锁定；第一批 ability3_rows 锁 1.4.1049 前像",
        "cross_unit_after_publish": {
            "wf_gbf_kit_soriz.py build_rows A3#8": f"content donor 已改为 store 键 {ABILITY1} 内按内容取（第一条 mode I、"
                                                   f"ck=724，标签 store:ability[{ABILITY1}]{{mode=I,ck=724}}；设计镜像 "
                                                   "work/character_packs/midautumn-20260920/design/soriz.json:1186 同改）。"
                                                   "发布前 #4、发布后 #2 是同一行（724 行逐字不变），soriz 输出逐字不变，"
                                                   "与本单元发布不再绑定；不要改回 idx=2 / \"#2\"（会重新按行号钉死，"
                                                   "design_drift 也会报漂移）",
            "wf_seasonal7_kit_zehr.py FROZEN_DONORS + seasonal7-20260916/revision-20260916/zehr/plan.json:3706":
                f"donor \"ability LIVE:{ABILITY1}#2\"（/tables/ability/keys/1599975[1]，带 old_values）字符串保留"
                "（plan.json 是第一轮证据，不改写）；kit 的 FROZEN_DONORS 把它钉成发布前的 live 行（逐格 + sha256），"
                "donor_row 不读 live，发布前后回放逐字相同（登记为 pinned）。不能改指 1399953#7"
                "（c0/c6/c9–c11/c13 已变，old_values 仍不匹配）",
            "wf_offline_content.WORKSPACE_ABILITY_ROW_COUNTS": "fox 登记 (6, 3, 8, 2, 2, 1) 早已过期（发布前 live 为 "
                                                               "(6, 2, 7, 2, 2, 2)），本次后为 (4, 2, 9, 2, 2, 2)",
        },
        #: 两处跨单元 donor 已在 2026-09-27 修复轮改成与行号无关（见 cross_unit_after_publish），无待办。
        "needed_edits_elsewhere": [],
        "cross_unit_landing": "本模块 INDEXED_LIVE_REFERENCES（已去掉 soriz 两条）须与 wf_gbf_kit_soriz.py / "
                              "midautumn design/soriz.json 的按内容取改动同一批提交；分开落地时 "
                              "test_every_indexed_live_reference_that_changes_is_registered 会红",
        "reference_only": {
            "work/character_packs/seasonal7-20260916/design/zehr.json:2677": "上一轮基线（kit 只取语音/能量/PF 树），"
                                                                              "donor 不重放",
            "work/character_packs/seasonal7-20260916/design/regis.json slot6[0]": "设计定稿只供身份/语音/能量，"
                                                                                  "行来自 revision plan.json",
        },
        "unaffected_indexed_references": "yuki（store:1399951#1，kit 带哈希）、1399953#0–#6 的引用：行内容不变",
        "staging": "stage_batch.py 的 SNAPSHOT='revision_20260927b' / evidence_name='revision-20260927b.json' 对第二批所有"
                   "单元共用：暂存本单元会整份覆盖 work/character_packs/fox_oracle_autumn/evidence/revision-20260927b.json"
                   "（第二批稻穗 08:28 的回写证据）并替换 manifest.snapshot['revision_20260927b']。暂存前由编排者决定改用独立键"
                   "（如 snapshot_key/evidence_name = revision_20260927b_inaho2）或先归档现有证据；本模块不暂存",
        "capabilities": list(CAPABILITIES),
        "runtime_verified": False,
    }
