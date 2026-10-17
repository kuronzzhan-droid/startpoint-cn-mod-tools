'稻穗「秋灯雷华妖狐姬」（139995 fox_oracle_autumn）：2026-09-27 作者确认的平衡修订。\n\n只改能力3（ability:1399953，整键 c1=false 仅主位），行序不变：\n\n1. 行4「进入 Fever（trigger 8）→ 全队雷技能槽 5%→10%」加 CT 10 秒：c35 0 → 600（单位帧；\n   官方同型先例 1310203 rec_android_1anv_3 = trigger 8 + CT 1800 + 211 + c1=false）。\n2. 行2 / 行3 / 行7 的 300%（持续·Fever：23 强化弹射伤害 / 154 能力伤害 / 0 攻击力）改为常驻：\n   转成瞬发 Initial 行（c5=0、c27=0、c39=(None)、c46=0，持续列 c85–c125 清空），\n   瞬发内容 55（c48 空，PF 类无对象）/ 388（c48=0 自身）/ 32（c48=0 自身），c51/c52=300000。\n   行形与本键行1、官方 1412012#1（55）、2510411#1（388）、1511652#0（32）同构。\n3. 行1（雷共鸣 Fever 时间 -20%）、行5（Fever 中全队雷技能槽最大值 +10%）、行6（Fever 冲刺连击）不动。\n\n不改：特殊 PF 三档 DSL（核实 live 无衰减结构）、能力1 行5（Fever 中 PF 扣槽 724）、队长行9（kind 200）；\n能力3 没有覆盖文案，客户端自动生成（瞬发 Initial 行无触发前缀，行4 自动拼「（CT: 10 秒）」），不新增。\n\n纯函数：只转换 ``read()`` 给出的 live 输入，不写任何文件；候选回写、发布由批次暂存脚本统一做\n（接口见 ${WF_ROOT}/out/平衡调整批次-20260927/module_contract.md）。\n\n生成器：稻穗历次 revision 链（wf_inaho_* / wf_kyubi_* / wf_native_pf_r2* / wf_newchars_r3*）\n都锁定历史输入哈希、只写历史克隆，重跑会拒绝而不会回退本次改动；本模块是 1399953 现行的唯一生成源。\n其中 wf_inaho_pf3_balance.revise_native 追加的「Fever 攻击 300%」行（现行7）已被本次常驻化取代。\n'
from __future__ import annotations

from copy import deepcopy
import hashlib
import json

import wf_client_description_legality as description
import wf_client_legality as legality

CID = "139995"
CODE = "fox_oracle_autumn"
PACKAGES = ["fox_oracle_autumn"]
PACKAGE_VERSION = {"fox_oracle_autumn": "0.20260927"}
#: live 1399951#4、1399956#1 的 724 AddFeverPointRatio 早已依赖它，候选 manifest 一直漏登记。
CAPABILITIES = ["kyubi-fever-ratio-v1"]
#: 候选 manifest 自身零哈希漂移；候选与 live 的内容差（leader:139995、1399951 行6）不在本次 splice 范围。
REVIEWED_DRIFT: dict = {}

ABILITY3 = f"{CID}3"
WIDTH = 126
BEFORE = {
    ("ability", ABILITY3): "fe9df7cff87ad9621885662aaed458f6e0b758fcaf99878bc222fd6149684a25",
}

# ability 表列位（wf_describe.layout("ability")["blocks"]，0 起）。
MODE = 5            # 0=Instant 1=During
TRIGGER = 27        # instant_trigger.kind（0 = Initial 战斗开始）
COOLTIME = 35       # instant_trigger.cooltime（帧）
PRECONTENT = 39     # instant_precontent.kind
DELAY = 46          # instant_delay
CONTENT = 47        # instant_content.kind；48 target、51/52 strength
DURING = 85         # during_accumulation_trigger 起，至 c125 都是持续/开幕块

CT_ROW = 3          # 行4（0 起 #3）
CT_FRAMES = "600"   # 10 秒
STRENGTH = "300000"
#: 0 起行号 -> (持续内容 kind, 持续对象, 瞬发内容 kind, 瞬发对象)
PERMANENT = {
    1: ("23", "", "55", ""),     # PowerFlipDamage：PF 类内容无对象
    2: ("154", "0", "388", "0"),  # AbilityDamage 自身
    6: ("0", "0", "32", "0"),     # AttackPoint 自身
}
UNCHANGED_ROWS = (0, 4, 5)


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _baseline(read) -> dict:
    """读取并锁定全部输入；任何一项漂移都拒绝（fail closed）。"""
    inputs = {}
    for kind, key in BEFORE:
        value = read(kind, key)
        if value is None or digest(value) != BEFORE[kind, key]:
            raise ValueError(f"unreviewed live baseline: {kind}:{key}")
        inputs[kind, key] = deepcopy(value)
    return inputs


def _expect(row, cells: dict, what: str):
    got = {col: row[col] for col in cells}
    if got != cells:
        raise ValueError(f"unexpected preimage for {what}: {got}")


def permanent_row(row: list[str], kind: str, target: str) -> list[str]:
    """持续·Fever 行 → 瞬发 Initial 行：保留 c0–c26（身份与前置块），瞬发块只写触发/内容/强度。"""
    out = row[:TRIGGER] + [""] * (WIDTH - TRIGGER)
    out[MODE] = "0"
    out[TRIGGER], out[PRECONTENT], out[DELAY] = "0", "(None)", "0"
    out[CONTENT], out[CONTENT + 1] = kind, target
    out[CONTENT + 4], out[CONTENT + 5] = STRENGTH, STRENGTH
    return out


def ability3_rows(rows: list[list[str]]) -> list[list[str]]:
    rows = deepcopy(rows)
    if len(rows) != 7 or any(len(r) != WIDTH for r in rows):
        raise ValueError("ability3 shape drift")
    if any((r[0], r[1]) != (f"{CODE}_3", "false") for r in rows):
        raise ValueError("ability3 identity or main-only flag drift")

    # 1. 行4：进入 Fever → 全队雷技能槽 5%→10%，只加 CT。
    _expect(rows[CT_ROW], {MODE: "0", TRIGGER: "8", 30: "100000", 31: "100000", 34: "(None)",
                           COOLTIME: "0", CONTENT: "211", 48: "5", 49: "Yellow",
                           51: "5000", 52: "10000"}, "ability3 row4")
    rows[CT_ROW][COOLTIME] = CT_FRAMES

    # 2. 行2/3/7：持续·Fever 300% → 瞬发 Initial 常驻 300%。
    for index, (during_kind, during_target, kind, target) in PERMANENT.items():
        row = rows[index]
        _expect(row, {MODE: "1", 6: "0", 13: "0", 20: "0", DURING: "(None)", 97: "4",
                      108: "false", 109: during_kind, 110: during_target,
                      113: STRENGTH, 114: STRENGTH}, f"ability3 row{index + 1}")
        if any(row[TRIGGER:DURING]):
            raise ValueError(f"ability3 row{index + 1} carries instant-block residue")
        rows[index] = permanent_row(row, kind, target)
    return rows


def row_problems(row: list[str]) -> list[str]:
    return (legality.client_legality_problems("ability", row)
            + legality.declared_block_field_problems("ability", row)
            + legality.invoke_skill_string_problems(row, set(), "ability")
            + description.description_compatibility_problems("ability", row)
            + [f"needs client capability {cap}"
               for cap in legality.required_client_capabilities("ability", row)])


def revise(read) -> dict:
    inputs = _baseline(read)
    rows = ability3_rows(inputs["ability", ABILITY3])
    problems = [f"ability {ABILITY3}#{i}: {p}"
                for i, row in enumerate(rows) for p in row_problems(row)]
    if problems:
        raise ValueError("; ".join(problems))
    return {
        "ability": {ABILITY3: rows}, "leader": {}, "cas": {}, "text": {}, "table": {},
        "action": {}, "dsl": {}, "server_text": {}, "new_programs": [],
        "notes": {
            "source": "wf_balance_20260927_inaho.py",
            "spec": "作者 2026-09-27 确认：能力3 行4 加 CT 10 秒；行2/3/7 的 300% 由 Fever 中改为常驻",
            "ability3_row4": {"cooltime_frames": int(CT_FRAMES), "cooltime_seconds": 10},
            "ability3_permanent": {f"row{i + 1}": f"during {d} -> instant Initial {k} (target "
                                                   f"{t or 'none'}) {STRENGTH}"
                                   for i, (d, _, k, t) in PERMANENT.items()},
            "unchanged": ["ability3 row1/row5/row6", "special PF DSL x3 (live has no decay)",
                          "ability1 row5 (724 Fever drain on PF)", "leader row9 (kind 200)"],
            "panel": "ability3 has no desc_override; client auto-generates the text",
            "candidate_preexisting_drift_untouched": [
                "leader:139995 candidate 12 rows vs live 11 (1.4.864 not written back)",
                "ability:1399951 row6 c51/c52 candidate 10000 vs live 5000 (1.4.864)",
            ],
            "superseded_generator": "wf_inaho_pf3_balance.revise_native Fever attack row",
            "runtime_verified": False,
        },
    }
