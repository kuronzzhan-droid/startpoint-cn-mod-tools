# -*- coding: utf-8 -*-
"""风巨蜥「荒岚霸主＋」149998 ``land_dragon_wind_playable``（风，作者口中的「风恐龙」）：2026-09-27 平衡第二批。

作者原话（2026-09-27，聊天请求 (1)）：「风恐龙能力1的boss负面标记也去掉,去掉风恐龙的能力1和2,4,5,6的主位限制,
能力3的自身发动技能fever+3固定值改为+30%,CT不变,能力和队长技全部添加风属性共鸣条件,加成也变成风属性全队攻击力和能力加成」。

落点（行号 0 基，``#n``；作者/任务书口中的「行 n+1」）：

1. 能力1（1499981）#2–#8：全面限制 7 行（c0 = ``cnmod_boss_limit``：tag_boss 编成≥2 → 全队攻击 −999% / 封印 219 /
   增益拒绝 479 / 固有 180002 标记 461 + 3 条 Revival 18 重挂）整段删除，只留 #0–#1。
   作者追加「风巨蜥的tag_boss标签也去掉」：角色表 ②``master/character/character.orderedmap`` 149998 c5 与
   ①``assets/cdndata/character.json`` 149998 [0][5] 去掉 ``tag_boss``（两层同步）⇒ 其他 boss 的全面限制行
   （前置 tag_boss 编成≥2）不再把风巨蜥计入 boss 人数。
2. 去主位限制：能力1 #0–#1、能力4 #0、能力5 #0–#2 前置 c6 202 → 0；能力6 整键 c1 false → true（行内无 202）。
   能力2 本就不限主位（#3 是 203 合击位锁槽，属于限制，保留）；能力3 保持主位（整键 c1=false、无 202，作者没列）。
3. 能力3 #4：Fever 中（前置 12）自身施技（触发 23、CT 600 帧不变）追加 Fever 点 213 22500000/45000000
   → Fever 槽 724 AddFeverPointRatio +30%（c51/c52 = 30000；c48 空，同 live 724 行形）。
   Fever 中 213 以外只有 724 / DSL AddFeverPoint 能写槽（记忆卡 wf-fever-gauge-write-channels）。
4. 风属性共鸣（前置 kind 2 / 600000 / 600000 / Green）写进每行第一个空闲前置槽：能力 c6（能力2 #0–#1 c6 已是 186，
   写 c13；官方先例 navy_officer_6 1210756#1 c13=2），队长 c4（= 能力列号 − 2）。例外：能力2 #3 合击位锁槽不加
   （加了会让非风队绕开限制）。队长 #9（722 强化弹射覆盖）按官方 141201#1（wind_spgirl_4anv，722 + 风共鸣）同形加；
   不满足时 override 查询回落角色原生 PF（与非队长位相同路径）。
5. 自身攻击/能伤加成 → 赋予全队(风)（c48/c110 = 5，组 c49/c111 = Green，数值不变）：能力1 #0（388）、能力3 #1（持续 154）、
   能力6 #0（388 限 5 次，官方 1510273#1 同形）、能力6 #2（持续 412，live 1199893#5 / 1799994#4）。
   技能槽 211、充能 3、Fever 时间 56、Fever 点 21、724 保持自身；队长 #0/#1/#4–#6 已是风队，#2 全队 Fever 点目标不变。
6. 面板：只有能力2 有覆盖 ``desc_override_land_dragon_wind_playable_2``，前两行加「风属性共鸣时，」，锁槽行照旧；
   其余槽与队长技没有覆盖键（键 = desc_override_ + 首行 string_id：``wind_dragon`` / ``wind_dragon_1`` …），
   由客户端按行自动生成（本模块开头确认这些键在 live 仍不存在，fail closed）。

生成器：``wf_wind_dragon_revision.revision_20260927b`` / ``a2_panel``（纯函数，测试断言其输出 == :func:`revise`，
且对自身输出重跑为空操作）；``work/character_packs/land_dragon_wind_poc/build_workspace.py`` 的行表同步改了语义常量（不运行）。
全面限制的 44 boss 批量生成器在仓库内不存在（1.4.679–682 为一次性施工，施工规格
``work/agent-coordination/全面限制机制-施工规格-20260901.md``），无处加排除：见 notes ``boss_limit_generator``。

本模块只读 ``read()`` 给的 live 值并返回新值；不写 live store / assets / .cdn / 候选包，不发布，不 git。
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any, Callable

CID = "149998"
CODE = "land_dragon_wind_playable"
#: flow owner（``.cdn/cn/character-releases/active.json`` base_package_owners 登记 land_dragon_wind_poc）。
PACKAGES = ["land_dragon_wind_poc"]
#: 候选 manifest 现值 0.20260925.1（09-25 C8016 修订）⇒ 0.20260927.1（只升不降）。
PACKAGE_VERSION = {"land_dragon_wind_poc": "0.20260927.1"}
#: 能力3 #4 改用 724（kyubi-fever-ratio-v1）；候选 manifest 现有 damage-type-rules-v1 / gauge-gain-rules-v1 /
#: panel-description-override-v2，缺这一项。
CAPABILITIES = ["kyubi-fever-ratio-v1"]
#: 候选 ability / leader / custom_ability_string 三表的本角色键与 live 逐字一致（2026-09-27 只读比对）。
REVIEWED_DRIFT: dict = {}

ELEMENT = 3                          # master/character c3：风（0 基内部元素）
WIND = "Green"
ABILITY = {slot: f"{CID}{slot}" for slot in range(1, 7)}
LEADER = CID
ABILITY_WIDTH, LEADER_WIDTH = 126, 124
BOSS_LIMIT = "cnmod_boss_limit"
BOSS_LIMIT_MARK = "180002"
MAIN_ONLY_SLOTS = frozenset({3})     # 09-27 起只有能力 3 保留主位限制
INVOKE_SKILL_STRINGS = frozenset({"ability_skill_land_dragon_wind_ring_lv2",
                                  "ability_skill_land_dragon_wind_laser_lv3"})

CHAR_TABLE = "master/character/character.orderedmap"
TAG_COL = 5                          # character c5 = tags（逗号分隔；空串是绝大多数角色的常态）
TAG_BOSS = "tag_boss"

PANEL_A2 = f"desc_override_{CODE}_2"
#: 客户端按「desc_override_ + 首行 string_id」取覆盖；这些键在 live 不存在 ⇒ 面板自动生成（存在即拒绝）。
AUTO_PANEL_KEYS = ("desc_override_wind_dragon",
                   *(f"desc_override_wind_dragon_{slot}" for slot in (1, 3, 4, 5, 6)))
RESONANCE_TEXT = "风属性共鸣时，"
MAIN_ICON = " <icon id='main'>  "   # 与 wf_featured_main_ability.MAIN 逐字一致（能力2 不限主位，不应出现）

#: live 输入基线（2026-09-27 本地链尾 1.4.1049，stage_batch.make_read(live_only=True) 只读取数）。
#: 值 = :func:`digest` (read(kind, key))；任一不符 ⇒ revise() 拒绝（fail closed）。
BEFORE: dict[tuple[str, str], str] = {
    ("ability", ABILITY[1]): "1156a0b70717d2cca90186b0d0f1d91a4fc118a6516de1a53d6f1d9f1e9fa06e",
    ("ability", ABILITY[2]): "dbf88e2a641316a935643f233964a561255406a2b62687814e0c4798cf758b04",
    ("ability", ABILITY[3]): "947b4471c7013ad6865facef3512ee08a36af5cc0b34fc0bc9893dde8f0cedeb",
    ("ability", ABILITY[4]): "6f706cdafa10215e49132de2fc2462224e07d12da9dad3d8b15dde2b516d711f",
    ("ability", ABILITY[5]): "64b5f602465a944209cda02f248a0e93379833454c0c9d72ac5bdcf751ec3349",
    ("ability", ABILITY[6]): "021724f3898da4d98c1335e71d00b38c24d798eb0e1276e475ecd0149e9f9250",
    ("leader", LEADER): "f127d546fa28f60bdb8b96a1d4847e621ba741016a756e7e5bb7ba851ec0f0fd",
    ("cas", PANEL_A2): "3f34a29ff085c79c8b8fa5721e0b0deb8ceb7c4d5820b580a1f06e9f290fc923",
    ("table", (CHAR_TABLE, CID)): "7d44b1796a84cd5f3aa4bca6c87622ac480b1018b8a32469a5dc5320e2157001",
    ("server_character", CID): "7d44b1796a84cd5f3aa4bca6c87622ac480b1018b8a32469a5dc5320e2157001",
}

# ------------------------------------------------------------------ 逐格改动（col: (改前, 改后)）


def _res(col: int, old_kind: str = "0") -> dict[int, tuple[str, str]]:
    """风共鸣写进以 ``col`` 起的前置槽：kind 2、阈值 +3/+4 = 600000、组 +5 = Green。"""
    return {col: (old_kind, "2"), col + 3: ("", "600000"), col + 4: ("", "600000"), col + 5: ("", WIND)}


RES_C6 = _res(6)
RES_C6_FROM_MAIN = _res(6, "202")    # 去 202 主位后 c6 即空闲槽
RES_C13 = _res(13)
RES_LEADER = _res(4)
PARTY_INSTANT = {48: ("0", "5"), 49: ("", WIND)}
PARTY_DURING = {110: ("0", "5"), 111: ("", WIND)}
OPEN_KEY = {1: ("false", "true")}
FEVER_RATIO = {47: ("213", "724"), 48: ("0", ""), 51: ("22500000", "30000"), 52: ("45000000", "30000")}

#: {(外层键, live 行号): {col: (改前, 改后)}}；不在表中的行（能力2 #3）逐字保留。
EDITS: dict[tuple[str, int], dict[int, tuple[str, str]]] = {
    (ABILITY[1], 0): {**RES_C6_FROM_MAIN, **PARTY_INSTANT},          # 388 能伤 → 全队(风)
    (ABILITY[1], 1): RES_C6_FROM_MAIN,                               # 施技 → 自身 Fever 点 21（非攻击，保持自身）
    (ABILITY[2], 0): RES_C13,                                        # c6 已是 186 非 Fever
    (ABILITY[2], 1): RES_C13,
    (ABILITY[2], 2): RES_C6,
    (ABILITY[3], 0): RES_C6,
    (ABILITY[3], 1): {**RES_C6, **PARTY_DURING},                     # 持续 154 能伤 → 全队(风)
    (ABILITY[3], 2): RES_C6,
    (ABILITY[3], 3): RES_C6,                                         # c13=12 Fever 保留
    (ABILITY[3], 4): {**RES_C6, **FEVER_RATIO},                      # 213 → 724 +30%，CT 600 不变
    (ABILITY[4], 0): RES_C6_FROM_MAIN,
    (ABILITY[5], 0): RES_C6_FROM_MAIN,
    (ABILITY[5], 1): RES_C6_FROM_MAIN,
    (ABILITY[5], 2): RES_C6_FROM_MAIN,
    (ABILITY[6], 0): {**OPEN_KEY, **RES_C6, **PARTY_INSTANT},        # 388 限 5 次 → 全队(风)
    (ABILITY[6], 1): {**OPEN_KEY, **RES_C6},
    (ABILITY[6], 2): {**OPEN_KEY, **RES_C6, **PARTY_DURING},         # 持续 412 独立乘区能伤 → 全队(风)
    **{(LEADER, index): RES_LEADER for index in range(10)},          # #9 = 722 强化弹射覆盖
}
#: 能力2 #3：仅合击位（203）持续 423 全队禁回槽 —— 限制行，不加共鸣、不动。
UNISON_LOCK = (ABILITY[2], 3)
UNISON_LOCK_CELLS = {1: "true", 5: "1", 6: "203", 109: "423", 110: "5", 111: "(None)", 118: "12"}

#: 全面限制 7 行（能力1 #2–#8）的指纹：前置 kind 2 + tag_boss ≥2；触发 0/18；内容 kind 序列。
BOSS_LIMIT_ROWS = tuple(range(2, 9))
BOSS_LIMIT_GATE = {0: BOSS_LIMIT, 5: "0", 6: "2", 9: "200000", 10: "200000", 11: "tag_boss"}
BOSS_LIMIT_KINDS = (("0", "0"), ("0", "219"), ("0", "479"), ("0", "461"),
                    ("18", "0"), ("18", "219"), ("18", "479"))           # (c27 触发, c47 内容)

#: 每个外层键的行数与首列（string_id）；leader #9 的 c0 是克隆 donor 的 ``black_wolf_knight``（live 原样）。
ROW_NAMES = {
    ABILITY[1]: ("wind_dragon_1",) * 2 + (BOSS_LIMIT,) * 7,
    ABILITY[2]: (f"{CODE}_2",) * 4,
    ABILITY[3]: ("wind_dragon_3",) * 5,
    ABILITY[4]: ("wind_dragon_4",),
    ABILITY[5]: ("wind_dragon_5",) * 3,
    ABILITY[6]: ("wind_dragon_6",) * 3,
    LEADER: ("wind_dragon",) * 9 + ("black_wolf_knight",),
}

# ------------------------------------------------------------------ 面板

PANEL_A2_BEFORE = (
    "非Fever状态下，每达成10连击，Fever槽+150；每达成15连击，Fever槽+300。",
    "每达成25连击，自身技能槽+5%。",
    "作为合击角色编成时，全队无法因技能或能力效果增加技能槽（战斗开始时除外）。",
)
#: 行 1 ↔ 能力2 #0/#1、行 2 ↔ #2（都加了风共鸣）；行 3 ↔ #3 锁槽（没加共鸣，照旧）。
PANEL_A2_AFTER = (RESONANCE_TEXT + PANEL_A2_BEFORE[0], RESONANCE_TEXT + PANEL_A2_BEFORE[1], PANEL_A2_BEFORE[2])


class WindDinoBalanceError(ValueError):
    """输入漂移或结构不符：拒绝修订（fail closed）。"""


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise WindDinoBalanceError(f"{CID} balance 20260927b: {message}")


def _checked(read: Callable[[str, Any], Any], kind: str, key: str) -> Any:
    value = read(kind, key)
    got = digest(value)
    if got != BEFORE[(kind, key)]:
        raise WindDinoBalanceError(f"unreviewed live baseline for {kind}:{key} "
                                   f"({got} != {BEFORE[(kind, key)]})")
    return deepcopy(value)


def _absent(read: Callable[[str, Any], Any], kind: str, key: str) -> bool:
    try:
        return read(kind, key) is None
    except KeyError:
        return True


def _shape(key: str, rows: list[list[str]]) -> None:
    width = LEADER_WIDTH if key == LEADER else ABILITY_WIDTH
    names = ROW_NAMES[key]
    _require(len(rows) == len(names), f"{key}: expected {len(names)} records, got {len(rows)}")
    for index, (row, name) in enumerate(zip(rows, names)):
        _require(len(row) == width and row[0] == name, f"{key}#{index}: expected {width} columns with c0={name}")


def _edit(key: str, index: int, row: list[str]) -> list[str]:
    out = list(row)
    for col, (old, new) in EDITS[(key, index)].items():
        _require(row[col] == old, f"{key}#{index} c{col}: expected {old!r}, got {row[col]!r}")
        out[col] = new
    return out


def _is_boss_limit(row: list[str], position: int) -> bool:
    trigger, kind = BOSS_LIMIT_KINDS[position]
    return (all(row[col] == value for col, value in BOSS_LIMIT_GATE.items())
            and (row[27], row[47]) == (trigger, kind)
            and (row[68] == BOSS_LIMIT_MARK) == (kind == "461"))


def ability_rows(key: str, rows: list[list[str]]) -> list[list[str]]:
    """一个能力键的改后行：能力1 删全面限制 7 行；其余按 :data:`EDITS` 逐格改（改前值不符即拒绝）。"""
    _shape(key, rows)
    out = []
    for index, row in enumerate(rows):
        if key == ABILITY[1] and index in BOSS_LIMIT_ROWS:
            _require(_is_boss_limit(row, index - BOSS_LIMIT_ROWS[0]), f"{key}#{index} is not the reviewed boss-limit row")
            continue
        if (key, index) == UNISON_LOCK:
            _require(all(row[col] == value for col, value in UNISON_LOCK_CELLS.items()),
                     f"{key}#{index} is not the reviewed unison gauge lock")
            out.append(list(row))
            continue
        out.append(_edit(key, index, row))
    slot = int(key[-1])
    _require(all(r[1] == ("false" if slot in MAIN_ONLY_SLOTS else "true") for r in out),
             f"{key}: main-slot flag mismatch after revision")
    _require(all("202" not in (r[6], r[13], r[20]) for r in out), f"{key}: OwnerIsMain remains")
    return out


def leader_rows(rows: list[list[str]]) -> list[list[str]]:
    """队长 10 行全部在 c4 加风共鸣（含 #9 的 722 强化弹射覆盖）。"""
    _shape(LEADER, rows)
    _require(rows[9][45] == "722" and rows[9][80] == "land_dragon_wind_pf", "leader #9 is not the PF override")
    return [_edit(LEADER, index, row) for index, row in enumerate(rows)]


def _drop_tag(tags: str) -> str:
    parts = [tag for tag in tags.split(",") if tag]
    _require(parts.count(TAG_BOSS) == 1, f"character tags {tags!r}: expected exactly one {TAG_BOSS}")
    return ",".join(tag for tag in parts if tag != TAG_BOSS)


def character_rows(rows: list[list[str]]) -> list[list[str]]:
    """②角色表：只把 c5 标签里的 tag_boss 去掉，其余格逐字保留。"""
    _require(len(rows) == 1 and rows[0][0] == CODE and rows[0][17] == CID, "character row identity mismatch")
    out = deepcopy(rows)
    out[0][TAG_COL] = _drop_tag(rows[0][TAG_COL])
    return out


def server_character(value: list) -> list:
    """①服务端 cdndata/character.json：同一个标签格 [0][5]，其余逐字保留。"""
    _require(len(value) == 1 and value[0][0] == CODE and value[0][17] == CID,
             "server character row identity mismatch")
    out = deepcopy(value)
    out[0][TAG_COL] = _drop_tag(value[0][TAG_COL])
    return out


def panel_a2(rows: list[list[str]]) -> list[list[str]]:
    """能力2 覆盖面板：前两行加「风属性共鸣时，」，锁槽行不变（不限主位，无 Ⓜ）。"""
    _require(len(rows) == 1 and len(rows[0]) == 1, f"{PANEL_A2}: expected one single-column row")
    _require(tuple(rows[0][0].split("\n")) == PANEL_A2_BEFORE, f"{PANEL_A2}: unexpected panel text")
    return [["\n".join(PANEL_A2_AFTER)]]


def revise(read: Callable[[str, Any], Any]) -> dict[str, Any]:
    abilities = {key: _checked(read, "ability", key) for key in ABILITY.values()}
    leader = _checked(read, "leader", LEADER)
    panel = _checked(read, "cas", PANEL_A2)
    character = _checked(read, "table", (CHAR_TABLE, CID))
    server_row = _checked(read, "server_character", CID)
    for key in AUTO_PANEL_KEYS:
        if not _absent(read, "cas", key):
            raise WindDinoBalanceError(f"live drift: cas:{key} now exists (panel is no longer auto-generated)")
    return {
        "ability": {key: ability_rows(key, rows) for key, rows in abilities.items()},
        "leader": {LEADER: leader_rows(leader)},
        "cas": {PANEL_A2: panel_a2(panel)},
        "table": {(CHAR_TABLE, CID): character_rows(character)},
        "server_character": {CID: server_character(server_row)},
        "text": {}, "action": {}, "dsl": {}, "server_text": {}, "new_programs": [],
        "notes": _notes(),
    }


def _notes() -> dict[str, Any]:
    return {
        "source": "wf_balance_20260927b_winddino.py",
        "spec": "作者 2026-09-27：「风恐龙能力1的boss负面标记也去掉,去掉风恐龙的能力1和2,4,5,6的主位限制,"
                "能力3的自身发动技能fever+3固定值改为+30%,CT不变,能力和队长技全部添加风属性共鸣条件,"
                "加成也变成风属性全队攻击力和能力加成」",
        "change": {
            f"ability:{ABILITY[1]}#2-#8": "全面限制 7 行（cnmod_boss_limit：攻 -999% / 封印 219 / 增益拒绝 479 / "
                                         "固有 180002 标记 461 + Revival×3）删除；键 9 行 → 2 行",
            "去主位": f"{ABILITY[1]}#0-#1、{ABILITY[4]}#0、{ABILITY[5]}#0-#2 c6 202→0；{ABILITY[6]} 整键 c1 false→true",
            f"ability:{ABILITY[3]}#4": "c47 213→724、c48 0→空、c51/c52 22500000/45000000→30000/30000"
                                      "（Fever 中自身施技 Fever 槽 +30%；CT c35=600、前置 c13=12、触发 23 不变）",
            "风共鸣": "能力 c6（能力2 #0/#1 为 c13）/ 队长 c4 = 2，阈值 600000/600000，组 Green；"
                     f"共 17 条能力行 + 10 条队长行（含 #9 722）；{UNISON_LOCK[0]}#{UNISON_LOCK[1]} 合击位锁槽不加",
            "全队(风)": f"{ABILITY[1]}#0（388）、{ABILITY[6]}#0（388 限5）c48 0→5 c49→Green；"
                       f"{ABILITY[3]}#1（持续154）、{ABILITY[6]}#2（持续412）c110 0→5 c111→Green；数值不变",
            f"cas:{PANEL_A2}": "第1、2行前加「风属性共鸣时，」；第3行锁槽照旧",
        },
        "kept": {
            f"ability:{ABILITY[3]}": "整键 c1=false 主位限制保留（作者没列），无 202",
            f"ability:{UNISON_LOCK[0]}#{UNISON_LOCK[1]}": "203 仅合击位 → 持续 423 全队禁回槽（限制，不是主位限制）逐字保留",
            "自身非攻击行": "技能槽 211、充能 3、Fever 时间 56、Fever 点 21 保持自身；队长 #2 全队 Fever 点目标不变",
            "数值": "除能力3 #4 外所有强度/触发/CT/限次逐字不变",
        },
        "tag_boss": "作者追加「风巨蜥的tag_boss标签也去掉」：②角色表 c5 与 ①assets/cdndata/character.json [0][5] "
                    "tag_boss → 空串（两层同步）。其他 boss 的全面限制行（前置 tag_boss 编成≥2）不再计入风巨蜥；"
                    "服务端 gacha-exchangeable 测试不受影响（风巨蜥两条池行本就可兑换）。候选服务端镜像该行是旧文，"
                    "整行替换会顺带刷回 live 其他列",
        "boss_limit_generator": "仓库内没有可重跑的全面限制生成器（mod-tools / work / out / scratchpad 全文检索 "
                                "cnmod_boss_limit、tag_boss 仅命中规格文档与无关代码；1.4.679–682 为一次性施工），"
                                "无处加 149998 排除；本单元以测试断言 revise() 与 wf_wind_dragon_revision 输出不含 "
                                "cnmod_boss_limit 行。若将来按规格文档重跑全面限制，须把 149998 从 44 只名单中剔除",
        "pf_override_resonance": "队长 #9 722 加风共鸣：官方 141201#1（wind_spgirl_4anv）同形；非风共鸣时 override 查询返回 "
                                 "null，回落角色原生 PF（与非队长位同一路径），不崩",
        "a6_unison": "09-25 Codex 把能力6 三行设为禁合击（c1=false）并移除旧 203，是设计取舍，不是崩溃修复"
                     "（C8016 修复在技能 DSL 预载 total_ability_damage_effect，本批不动）；能力6 无 629 行，"
                     "不涉及「629 副位禁用」，按作者请求解除",
        "unison_semantics": "解除主位后，合击位持有时这些行并入主位角色能力池，「自身」= 主位角色（引擎语义）",
        "generator": "wf_wind_dragon_revision.revision_20260927b / a2_panel（测试断言 == revise() 输出，重跑空操作）；"
                     "work/character_packs/land_dragon_wind_poc/build_workspace.py 行表同步（不运行）",
        "capabilities": list(CAPABILITIES),
        "runtime_verified": False,
    }
