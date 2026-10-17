# -*- coding: utf-8 -*-
"""五重决战 v2 构建器（2026-09-28）。

设计：mod-tools/docs/五重决战重做设计-20260928.md。数值与阵容在 five_boss_v2_spec.json。

## 做什么
从 spec 生成五重自有的全部表键与文件，过门禁后暂存到工作目录（stage/common/<逻辑路径> + plan.json），
由 wf_five_boss_v2_publish.py 写 live 并走 wf_publish 铸边。本模块不写 store、不发布。

- 变体 = 一个 BothBoss 隐藏关（R0 第 0 轮 / R1 第 1 轮）：quest 行 + field_data + zone + 每变体独立的 boss 克隆。
- 路由：R0 × R1 全组合写进 both_boss_map，每行一个恒真条件（Attack ≥ -99999），三人候选池相同
  ⇒ V7 随机选图补丁按房号种子抽到同一行；结算解散房间 ⇒ 下一局重抽。末尾保留兜底行（id 最大）。
- 词缀：玩家侧/敌方侧效果写成新的 action DSL，挂在「载体」boss 的出场动作 c109（逗号并列）。
  c22=1（顺序出场）时每只都是载体；c22=0（同屏）时每波第一只是载体（波切换会清场地效果）。
- 血量/眩晕：每个克隆有自己的 boss_level 行 ⇒ 按目标血量反算段数 c2，眩晕基数改用 tp_normal 曲线后反算 c12；
  quest c99/c105 固定为 1。
- 修复：还原 1.4.802 在官方共用 routine 上做的嫉妒试炼 ×3（外溢官方 1033001–04）。
- 美术（spec.art）：事件页头图/横幅/缩略图同尺寸原位替换；两轮各一行自有 field（背景四件套从母本行克隆，
  只换 PNG 与子纹理名）；入场券图标追加进 item_icon 共享图集（既有条目不动），道具行 c3/c4 要等图集那条边
  上线后的下一次暂存才出现（c4 不在已加载图集 ⇒ C8004）。

## 门禁（任一不过 ⇒ 拒绝暂存）
站位名 ⊆ 地形 CUSTOM_POSITION；召唤组 ⊆ 地形 FUNNEL_SPAWNn；DSL 构造名只用官方先例；
每个隐藏关的 boss 贴图并集（含出招 DSL 特效闭包与属性色替弹幕）≤ 6.0 Mpx（≤5.5 通过，之间警告）；
克隆代号不得与非自有代号冲突；路由行全部指向本次生成的隐藏关；文件只落自有目录或 spec 点名的路径，
图集 PNG 与 atlas 同边；共享表（stage_node、item）只改 spec 点名的键；field_data 指向的 field 行必须存在。
"""
from __future__ import annotations

import argparse
import colorsys
import copy
import csv
import hashlib
import io
import json
import re
import struct
import sys
import zlib
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    pass  # Imports resolve from this checkout/package, not external source copies.

import wf_assets  # noqa: E402
import wf_dsl  # noqa: E402
import wf_mod_tool as core  # noqa: E402
import wf_quest_lib as q  # noqa: E402
import wf_share_update_codec as X  # noqa: E402

SPEC_PATH = TOOLS / "five_boss_v2_spec.json"

T_BBQ = "master/quest/boss_battle_quest.orderedmap"
T_BBG = "master/quest/both_boss/both_boss_group.orderedmap"
T_BBM = "master/quest/both_boss/both_boss_map.orderedmap"
T_FD = "master/battle/field_data.orderedmap"
T_ZONE = "master/battle/zone.orderedmap"
T_GB = "master/battle/boss/general_boss.orderedmap"
T_BL = "master/battle/boss/boss_level.orderedmap"
T_GBS = "master/battle/boss/general_boss_state.orderedmap"
T_GBV = "master/battle/boss/general_boss_variable.orderedmap"
T_GEW = "master/battle/boss/general_enemy_watch.orderedmap"
T_AR = "master/reward/event/additional_reward.orderedmap"
T_FIELD = "master/battle/field.orderedmap"
T_NODE = "master/quest/boss_battle_stage_node.orderedmap"
T_ITEM = "master/item/item.orderedmap"
T_SHOP = "master/shop/boss_coin_shop.orderedmap"

TABLES = (T_BBQ, T_BBG, T_BBM, T_FD, T_ZONE, T_GB, T_BL, T_GBS, T_GBV, T_GEW, T_AR, T_FIELD, T_NODE, T_ITEM, T_SHOP)

DSL_SUFFIX = ".action.dsl.amf3.deflate"
TERRAIN_SUFFIX = ".amf3.deflate"
OWN_CODE_PREFIX = "mod_fb2_"
OWN_DSL_DIR = "battle/action/enemy/action/mod/five_boss_v2/"
OWN_TERRAIN_DIR = "battle/terrain/mod/five_boss_v2/"
OWN_FIELD_DIR = "battle/field/mod/five_boss_v2/"
OWN_BOSS_DIR = "battle/boss/mod/five_boss_v2/"
# 美术：field 背景 = PartsAnimation 四件套；item_icon 是共享 TextureAtlas（item 表 c4 只能指它的子纹理）
PARTS_SUFFIXES = (".parts.amf3.deflate", ".atlas.amf3.deflate", ".timeline.amf3.deflate")
FIELD_BG_COL = 0
ITEM_ATLAS = "item_icon/sprite_sheet"
ITEM_ATLAS_FILES = (ITEM_ATLAS + ".png", ITEM_ATLAS + ".atlas.amf3.deflate")
ITEM_THUMB_COL, ITEM_SMALL_COL = 3, 4
ATLAS_GAP = 2                       # 子纹理之间留 2px（与既有条目 x=1/44/87 的间距一致）
LEVEL = 80
GENERAL_HP_K_LV80 = 2250.0          # 375·partyAtk·hitHpBasic @lv80（wf_rogue_build.GENERAL_HP_LEVEL_SCALE）
TP_NORMAL_LV80 = 2.0                # tp_normal 曲线 lv80（取 89 档）；现网 sand c12=100×c105=36 → 7200 反推
TP_CURVE = "tp_normal"
ALWAYS_TRUE_THRESHOLD = -99999      # Attack ≥ 该值恒真（诅咒武器能把队长攻击汇总压成负数）

# general_boss 列位（BossBattle 反编译 GeneralBossValues.as；0905 调研 T4）
GB_NAME, GB_ANIM, GB_POS, GB_ROUTINE, GB_PRE, GB_PRE_RERUN = 1, 2, 41, 42, 109, 110
GB_ACTION_FIRST, GB_ACTION_LAST = 111, 160
GB_ANIM_COLS = list(range(2, 15)) + [25, 26]
# boss_level 列位
BL_HP_HITS, BL_HP_MUL, BL_HP_CORR, BL_ATK_CORR, BL_TP_CURVE, BL_TP_BASE = 2, 3, 4, 10, 11, 12
# 克隆统一用 store 里有数值的曲线（部分官方 boss 用客户端内置曲线，无法按目标反算）
HP_CURVE_NORM, ATK_CURVE_NORM = "hit_hp_boss", "atk_multi"
# boss_battle_quest 列位（BossBattleQuestValues.as；0928 盘点 A §1）
Q_NAME = 2
Q_ENEMY_STATE = range(74, 84)       # 5 槽 (kind, strength)
Q_HP = (97, 98, 99)                 # zako, funnel, boss
Q_ATK = (100, 101, 102)
Q_TP = (103, 104, 105)
Q_LEVEL, Q_FEVER_CAP, Q_FIELD_DATA, Q_TIME = 106, 108, 109, 111
Q_IS_BOTH, Q_HIDDEN = 122, 123
# zone 列位（ZoneValues.as）：c22 分组方式；boss1..3 (kind,id) 单人 c23/24,c27/28,c31/32；多人 c25/26,c29/30,c33/34
Z_GROUP = 22
Z_BOSS_SLOTS = ((23, 24, 25, 26), (27, 28, 29, 30), (31, 32, 33, 34))

# 构造名白名单：本模块只拼这些官方先例节点（形状逐字照抄官方 DSL，见 dsl_* 函数注释）
DSL_CONSTRUCTORS = frozenset({
    "ActionDsl", "None", "Block", "Event", "Repeat", "Wait", "Command", "FindAllSubjects", "DoNothing",
    "CreateCondition", "DeleteCondition", "DCAll", "Default", "SubtractSkillPoint", "StartModifierField",
    "SubtractFeverPoint", "AddFeverPoint", "GenericConditionHitEffect",
    "ACAttackPoint", "ACToleranceOfElement", "ACSkillDamage", "ACDirectDamage", "ACSilence",
    "ACFeverPoint", "ACSkillGaugeCharging", "ACHealRejection",
    "BuffRejection", "HealRejection", "SkillGaugeCharging", "ComboRestriction", "Slip",
    "MemberDirectAttack", "TotalOfParty", "PowerFlip", "Condition", "DCAttackPoint",
})


class BuildError(RuntimeError):
    pass


# ============================================================ 存储读写（只读 live）

def store_file(logical: str) -> Path:
    return q.store_path(logical)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_rows(text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(text)))


def write_rows(rows: list[list[str]], trailing_newline: bool = False) -> str:
    s = io.StringIO(newline="")
    csv.writer(s, lineterminator="\n").writerows(rows)
    text = s.getvalue()
    return text if trailing_newline else text[:-1] if text.endswith("\n") else text


def num(v: float) -> str:
    """CSV 数值：不用科学计数法（客户端 parseFloat/parseInt 口径），去掉多余的 0。"""
    s = f"{float(v):.6f}".rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


def one_row(text: str) -> list[str]:
    rows = read_rows(text)
    if len(rows) != 1:
        raise BuildError(f"expected one CSV row, got {len(rows)}: {text[:80]!r}")
    return rows[0]


def build_map(keys: list[str], chunks: list[bytes]) -> bytes:
    key_blob = b""
    row_blob = b""
    pairs = []
    for key, chunk in zip(keys, chunks):
        key_blob += key.encode("utf-8")
        row_blob += chunk
        pairs.append((len(key_blob), len(row_blob)))
    index = bytearray(struct.pack("<I", len(pairs)))
    for k_end, r_end in pairs:
        index += struct.pack("<II", k_end, r_end)
    index += key_blob
    packed = zlib.compress(bytes(index))
    return struct.pack("<I", len(packed)) + packed + row_blob


def replace_in_chunk(chunk: bytes, path: list[str], new_node) -> bytes:
    """只改 path 指向的子节点；兄弟节点原字节保留（避免整表重压缩的伪变更）。new_node=None 表示删除。"""
    if not path:
        return q.build_node(new_node)
    parsed = q._try_parse_map(chunk)  # noqa: SLF001 — wf_quest_lib 的严格 map 解析
    if parsed is None:
        raise BuildError(f"not a map at {path}")
    keys, chunks = list(parsed[0]), list(parsed[1])
    head, rest = path[0], path[1:]
    if head in keys:
        i = keys.index(head)
        if new_node is None and not rest:
            del keys[i], chunks[i]
        else:
            chunks[i] = replace_in_chunk(chunks[i], rest, new_node)
    else:
        if new_node is None:
            return chunk
        node = new_node
        for part in reversed(rest):
            node = {part: node}
        keys.append(head)
        chunks.append(q.build_node(node))
    return build_map(keys, chunks)


class Live:
    """live store 的只读快照（原始字节 + 解析树），全部修改都在内存里进行。"""

    def __init__(self, loader: Callable[[str], bytes] | None = None):
        self._loader = loader or (lambda lg: store_file(lg).read_bytes())
        self.raw: dict[str, bytes] = {}
        self.tree: dict[str, dict] = {}

    def table(self, logical: str) -> dict:
        if logical not in self.tree:
            raw = self._loader(logical)
            self.raw[logical] = raw
            parsed = q.parse_node(raw)
            if not isinstance(parsed, dict):
                raise BuildError(f"{logical} is not a map")
            self.tree[logical] = parsed
        return self.tree[logical]

    def file(self, logical: str) -> bytes | None:
        try:
            return self._loader(logical)
        except FileNotFoundError:
            return None


def get_path(tree: dict, path: Iterable[str]):
    node = tree
    for part in path:
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


# ============================================================ spec

@dataclass
class BossSlot:
    alias: str
    hp_e8: float                     # 目标血量（亿，多人、quest c99=1）
    position: str | None = None      # 覆盖 c41；None = 沿用母本


@dataclass
class Variant:
    quest: int
    round: str                       # "r0" | "r1"
    name: str
    waves: list[list[BossSlot]]
    group_kind: int                  # zone c22：1 顺序出场 / 0 同屏
    enemy_states: list[tuple[int, float | None]] = field(default_factory=list)
    affixes: list[str] = field(default_factory=list)          # 每波载体都挂
    entry_affixes: list[str] = field(default_factory=list)    # 只挂在第 0 波载体（R1 进场清算）
    field: str | None = None                                  # None = 用 round 默认 field 行


def load_spec(path: Path = SPEC_PATH) -> dict:
    spec = json.loads(path.read_text(encoding="utf-8"))
    variants = []
    for v in spec["variants"]:
        waves = [[BossSlot(**s) for s in wave] for wave in v["waves"]]
        variants.append(Variant(quest=int(v["quest"]), round=v["round"], name=v["name"], waves=waves,
                                group_kind=int(v["group_kind"]),
                                enemy_states=[(int(k), s) for k, s in v.get("enemy_states", [])],
                                affixes=list(v.get("affixes", [])), entry_affixes=list(v.get("entry_affixes", [])),
                                field=v.get("field")))
    spec["_variants"] = variants
    return spec


# ============================================================ DSL：词缀程序（节点形状逐字照抄官方）

def _range(v) -> list[dict]:
    return [{"min": v, "max": v}]


def _root(block: list, looping: bool = False) -> list:
    # 官方 boss_halfanv3$field_condition2 / five_boss_curse 的根：["ActionDsl",1,["None"],f,f,f,f,f,<bool>,f,0,Block]
    return ["ActionDsl", 1, ["None"], False, False, False, False, False, looping, False, 0, ["Block", block]]


def _cmd(node: list) -> list:
    return ["Command", node]


def _find_all(search: int, block: list) -> list:
    # FindAllSubjects(0, 33=主小队, [],[],[],[],[], DoNothing, Block)；51=全部 boss
    return _cmd(["FindAllSubjects", 0, search, [], [], [], [], [], ["DoNothing"], ["Block", block]])


def _repeat(interval: int, count: int, key: str, block: list) -> list:
    return ["Event", ["Repeat", interval, count, key, ["Block", block]]]


def _wait(frames: int, block: list) -> list:
    return ["Event", ["Wait", frames, "*", ["Block", block]]]


def _cond(subject: int, ac: list, *, cancelable: bool = True, key: str = "", force: bool = False) -> list:
    # 官方 envy_80$mist / empress_dark_form1$skill1 形状；第 10 参 3=成员，末参 forceApply
    return _cmd(["CreateCondition", subject, [ac], _range(1), ["GenericConditionHitEffect"], cancelable, False,
                 key, None, False, 3, _range(1), force])


def _ac_value(kind: str, frames: int, value: float, layers: int) -> list:
    return [kind, _range(frames), _range(value), _range(layers)]


def dsl_enrage(interval: int, atk: float, atk_layers: int, res: float, res_layers: int, count: int) -> list:
    """敌方：全 boss 周期自叠攻 + 全属性耐性（沿用 1.4.758 五重诅咒 FA51 形状）。"""
    boss_block = [
        _cmd(["CreateCondition", 0, [_ac_value("ACAttackPoint", 9999999, atk, atk_layers)], _range(1),
              ["GenericConditionHitEffect"], True, True, "mod_fb2_enrage_atk", None, False, 3, _range(1), False]),
        _cmd(["CreateCondition", 0, [["ACToleranceOfElement", _range(9999999), 254, _range(res), _range(res_layers)]],
              _range(1), ["GenericConditionHitEffect"], True, True, "mod_fb2_enrage_res", None, False, 3, _range(1),
              False]),
    ]
    return _root([_repeat(interval, count, "mod_fb2_enrage", [_find_all(51, boss_block)])])


def dsl_weaken_rotation(period: int, frames: int, value: float, count: int) -> list:
    """玩家：攻击 / 技伤 / 直击 -X% 轮换（1.4.758 五重诅咒同形）。"""
    third = period // 3
    def one(kind: str, key: str):
        return _repeat(period, count, key, [_find_all(33, [_cond(0, _ac_value(kind, frames, value, 1))])])
    return _root([
        one("ACAttackPoint", "mod_fb2_weak_atk"),
        _wait(third, [one("ACSkillDamage", "mod_fb2_weak_skill")]),
        _wait(third * 2, [one("ACDirectDamage", "mod_fb2_weak_direct")]),
    ])


def dsl_field(kind_node: list, cancel: list, duration: int = 9999999) -> list:
    """场地效果：只作用玩家侧。形状照 chapter12_boss$field_start1 / epuration_highest$field_debuff。"""
    return _root([_cmd(["StartModifierField", duration, [kind_node], cancel])])


def dsl_silence_waves(interval: int, frames: int, count: int) -> list:
    """玩家：周期沉默窗口（ghost_fox_ex$shot8 的 ACSilence 形状，强制施加）。"""
    return _root([_repeat(interval, count, "mod_fb2_silence",
                          [_find_all(33, [_cond(0, ["ACSilence", _range(frames)], force=True)])])])


def dsl_fever_drain(value: float) -> list:
    """玩家：Fever 获取 -X%（noroi_waraboss$…skill_shot3 的 ACFeverPoint 形状，永续、不可驱散）。"""
    return _root([_find_all(33, [_cond(0, _ac_value("ACFeverPoint", 9999999, value, 1), cancelable=False,
                                       key="mod_fb2_fever_drain")])])


def dsl_purge(buff_reject_frames: int, periodic_interval: int, periodic_count: int, periodic_limit: int) -> list:
    """R1 进场清算：boss_halfanv3$field_condition2（清增益 + 技能槽清零 + 禁益场）改为强制驱散（kind 2，
    boss_halfanv3$wave2 先例，可摘不可驱散/固有层）；禁益场限时；之后周期强制驱散最新 N 个增益。"""
    purge_now = _find_all(33, [
        _cmd(["DeleteCondition", 0, ["DCAll", 2], 99, 2, "", ["Default"]]),
        _cmd(["SubtractSkillPoint", 0, _range(1)]),
    ])
    reject = _cmd(["StartModifierField", buff_reject_frames, [["BuffRejection"]], ["None"]])
    periodic = _repeat(periodic_interval, periodic_count, "mod_fb2_purge",
                       [_find_all(33, [_cmd(["DeleteCondition", 0, ["DCAll", 2], periodic_limit, 2, "",
                                             ["Default"]])])])
    return _root([purge_now, reject, periodic])


def dsl_signature(interval: int, count: int, key: str, effects: list | None = None, drain: float | None = None,
                  silence: int | None = None, purge: int | None = None, on_entry: bool = False) -> list:
    """自制 boss 的签名招式：周期对全体成员施加一组效果。只拼已有形状，不引入新构造：
    减益 = weaken_rotation 同形；沉默 = silence_waves 的强制 ACSilence（技能封印）；扣槽 = purge 的
    SubtractSkillPoint；驱散 = purge 的强制 DeleteCondition DCAll（kind 2，可摘不可驱散层）。
    on_entry=True 时登场先执行一次，再按周期重复。"""
    block = [_cond(0, _ac_value(kind, frames, value, 1)) for kind, frames, value in (effects or [])]
    if silence:
        block.append(_cond(0, ["ACSilence", _range(silence)], force=True))
    if drain:
        block.append(_cmd(["SubtractSkillPoint", 0, _range(drain)]))
    if purge:
        block.append(_cmd(["DeleteCondition", 0, ["DCAll", 2], purge, 2, "", ["Default"]]))
    loop = _repeat(interval, count, key, [_find_all(33, copy.deepcopy(block))])
    return _root(([_find_all(33, block)] if on_entry else []) + [loop])


def affix_library(params: dict) -> dict[str, list]:
    """词缀名 → DSL 树。数值来自 spec['affix_params']，便于作者调参。"""
    p = params
    sigs = {name: dsl_signature(**cfg) for name, cfg in p.items() if name.startswith("sig_")}
    return sigs | {
        "enrage_r0": dsl_enrage(**p["enrage_r0"]),
        "enrage_r1": dsl_enrage(**p["enrage_r1"]),
        "weaken_rotation": dsl_weaken_rotation(**p["weaken_rotation"]),
        "heal_seal": dsl_field(["HealRejection"],
                               ["MemberDirectAttack", p["heal_seal"]["cancel_direct_hits"], ["TotalOfParty", []]]),
        "combo_cap": dsl_field(["ComboRestriction", p["combo_cap"]["cap"]],
                               ["PowerFlip", p["combo_cap"]["cancel_powerflips"]]),
        "slow_charge": dsl_field(["SkillGaugeCharging", p["slow_charge"]["value"]],
                                 ["MemberDirectAttack", p["slow_charge"]["cancel_direct_hits"], ["TotalOfParty", []]]),
        "slip": dsl_field(["Slip", p["slip"]["value"]],
                          ["Condition", p["slip"]["cancel_conditions"], ["TotalOfParty", []], ["DCAttackPoint", 2]]),
        "silence_waves": dsl_silence_waves(**p["silence_waves"]),
        "fever_drain": dsl_fever_drain(**p["fever_drain"]),
        "purge_r1": dsl_purge(**p["purge_r1"]),
    }


def affix_program(name: str) -> str:
    return f"{OWN_DSL_DIR}fb2_affix${name}"


def dsl_constructor_problems(tree) -> list[str]:
    """树里出现的枚举构造名（形如 ["Name", ...] 的首元素）必须在白名单。"""
    bad = []

    def walk(n):
        if isinstance(n, list):
            if n and isinstance(n[0], str) and n[0][:1].isupper() and n[0] not in DSL_CONSTRUCTORS:
                bad.append(n[0])
            for x in n:
                walk(x)
        elif isinstance(n, dict):
            for x in n.values():
                walk(x)

    walk(tree)
    return sorted(set(bad))


def encode_dsl(tree) -> bytes:
    raw = wf_dsl.encode_amf3(tree)
    back = wf_dsl.parse_dsl(raw)["tree"]
    if back != tree:
        raise BuildError("DSL encode round-trip mismatch")
    comp = zlib.compressobj(9, zlib.DEFLATED, -15)
    return comp.compress(raw) + comp.flush()


# ============================================================ 地形

def load_terrain_tree(live: Live, logical: str) -> dict:
    raw = live.file(logical + TERRAIN_SUFFIX)
    if raw is None:
        raise BuildError(f"terrain missing: {logical}")
    tree = wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]
    if not isinstance(tree, dict):
        raise BuildError(f"terrain has no tree: {logical}")
    return tree


def object_layers(tree: dict) -> list[dict]:
    return [L for L in tree.get("layers", []) if L.get("type") == "objectgroup"]


def build_terrain(live: Live, spec_t: dict) -> tuple[dict, dict]:
    """返回 (新地形树, 报告)。remove_types 整类删除；add_from 从别的地形逐层复制指定类型对象（坐标原样）。"""
    tree = copy.deepcopy(load_terrain_tree(live, spec_t["base"]))
    report = {"removed": 0, "added": 0}
    remove = set(spec_t.get("remove_types", []))
    layers = object_layers(tree)
    for L in layers:
        before = len(L.get("objects", []))
        L["objects"] = [o for o in L.get("objects", []) if o.get("type") not in remove]
        report["removed"] += before - len(L["objects"])
    add = spec_t.get("add_from")
    if add:
        src = load_terrain_tree(live, add["terrain"])
        src_layers = {L.get("name"): L for L in object_layers(src)}
        next_id = max([int(o.get("id", 0)) for L in layers for o in L.get("objects", [])] + [0]) + 1
        for L in layers:
            sl = src_layers.get(add.get("layer_map", {}).get(L.get("name"), L.get("name")))
            if sl is None:
                continue
            have = {o.get("type") for o in L["objects"]}
            for o in sl.get("objects", []):
                if o.get("type") in add["types"] and o.get("type") not in have:
                    c = copy.deepcopy(o)
                    if "id" in c:
                        c["id"] = next_id
                        next_id += 1
                    L["objects"].append(c)
                    report["added"] += 1
        if "nextobjectid" in tree:
            tree["nextobjectid"] = max(int(tree["nextobjectid"]), next_id)
    overrides = spec_t.get("object_overrides")
    if overrides:
        # 按「相对本层 BOUNDS 左上角」给出的矩形整类重设（召唤锚语义随母本地形，不能跨地形照搬坐标）
        next_id = max([int(o.get("id", 0)) for L in layers for o in L.get("objects", [])] + [0]) + 1
        for L in layers:
            bounds = next((o for o in L["objects"] if o.get("type") == "BOUNDS"), None)
            if bounds is None:
                raise BuildError(f"layer {L.get('name')} has no BOUNDS")
            template = next((o for o in L["objects"] if str(o.get("type", "")).startswith("FUNNEL_SPAWN")), None)
            if template is None:
                raise BuildError(f"layer {L.get('name')} has no FUNNEL_SPAWN template object")
            bx, by = float(bounds["x"]), float(bounds["y"])
            for typ, rects in overrides.items():
                before = len(L["objects"])
                L["objects"] = [o for o in L["objects"] if o.get("type") != typ]
                report["removed"] += before - len(L["objects"])
                for rx, ry, rw, rh in rects:
                    c = copy.deepcopy(template)
                    c.update({"type": typ, "x": bx + rx, "y": by + ry, "width": rw, "height": rh})
                    if "id" in c:
                        c["id"] = next_id
                        next_id += 1
                    L["objects"].append(c)
                    report["added"] += 1
        if "nextobjectid" in tree:
            tree["nextobjectid"] = max(int(tree["nextobjectid"]), next_id)
    pos_over = spec_t.get("position_overrides") or {}
    if pos_over:
        # 按层重设站位（相对本层 BOUNDS）：站位名的语义随 boss 母本地形（memory wf-terrain-position-name-collision），
        # 某层只给一只 boss 用时，把该层站位对齐到它的原生地形，避免整体偏向一侧
        next_id = max([int(o.get("id", 0)) for L in layers for o in L.get("objects", [])] + [0]) + 1
        for li_str, names in pos_over.items():
            li = int(li_str)
            if li >= len(layers):
                raise BuildError(f"position_overrides: terrain has no layer {li}")
            L = layers[li]
            bounds = next((o for o in L["objects"] if o.get("type") == "BOUNDS"), None)
            template = next((o for o in L["objects"] if o.get("type") == "CUSTOM_POSITION"), None)
            if bounds is None or template is None:
                raise BuildError(f"layer {li} lacks BOUNDS or CUSTOM_POSITION")
            bx, by = float(bounds["x"]), float(bounds["y"])
            for name, (rx, ry) in names.items():
                hits = [o for o in L["objects"] if o.get("type") == "CUSTOM_POSITION" and o.get("name") == name]
                if not hits:
                    c = copy.deepcopy(template)
                    c["name"] = name
                    if "id" in c:
                        c["id"] = next_id
                        next_id += 1
                    L["objects"].append(c)
                    hits = [c]
                for o in hits:
                    o["x"], o["y"] = bx + rx, by + ry
                report["moved"] = report.get("moved", 0) + len(hits)
        if "nextobjectid" in tree:
            tree["nextobjectid"] = max(int(tree["nextobjectid"]), next_id)
    return tree, report


def encode_terrain(tree: dict) -> bytes:
    raw = wf_dsl.encode_amf3(tree)
    back = wf_dsl.parse_dsl(raw)["tree"]
    if back != tree or "<objRef" in json.dumps(back, ensure_ascii=False):
        raise BuildError("terrain encode round-trip mismatch")
    comp = zlib.compressobj(9, zlib.DEFLATED, -15)
    return comp.compress(raw) + comp.flush()


def terrain_positions(tree: dict) -> list[set[str]]:
    return [{o.get("name") for o in L.get("objects", []) if o.get("type") == "CUSTOM_POSITION" and o.get("name")}
            for L in object_layers(tree)]


def terrain_funnel_groups(tree: dict) -> list[set[int]]:
    out = []
    for L in object_layers(tree):
        g = set()
        for o in L.get("objects", []):
            m = re.fullmatch(r"FUNNEL_SPAWN(\d+)", str(o.get("type", "")))
            if m:
                g.add(int(m.group(1)))
        out.append(g)
    return out


# ============================================================ boss 克隆

def gb_tiers(live: Live, code: str) -> dict[str, list[str]]:
    node = live.table(T_GB).get(code)
    if not isinstance(node, dict):
        raise BuildError(f"general_boss missing: {code}")
    return {tier: one_row(text) for tier, text in node.items()}


def tier_for_level(tiers: Iterable[str], level: int = LEVEL) -> str:
    nums = sorted(int(t) for t in tiers if t.isdigit())
    for n in nums:
        if n >= level:
            return str(n)
    raise BuildError(f"no general_boss tier >= {level}: {sorted(tiers)}")


def split_programs(cell: str) -> list[str]:
    if not cell or cell == "(None)":
        return []
    return [p for p in cell.split(",") if p and p != "(None)"]


def strip_v1_curse(programs: list[str]) -> list[str]:
    return [p for p in programs if "/mod/five_boss/" not in p]


def curve_hp_corr(name: str, level: int = LEVEL) -> float:
    import wf_rogue_build as rb  # 延迟导入：大模块
    v = rb.curve_value("hp", name, level)
    if not v:
        raise BuildError(f"unknown hp correction curve {name}")
    return float(v)


def hits_for_hp(bl_row: list[str], hp_e8: float) -> float:
    unit = GENERAL_HP_K_LV80 * float(bl_row[BL_HP_MUL]) * curve_hp_corr(bl_row[BL_HP_CORR])
    return round(hp_e8 * 1e8 / unit, 4)


def watch_copies(gew: dict, mother: str, clone: str) -> list[tuple[list[str], Any]]:
    """general_enemy_watch：自身子树 + 作为 partner 出现的子树都复制一份（官方 envy_80_single 先例）。"""
    out = []
    for kind, selfs in gew.items():
        if not isinstance(selfs, dict):
            continue
        if mother in selfs and isinstance(selfs[mother], dict) and mother in selfs[mother]:
            out.append(([kind, clone], {clone: copy.deepcopy(selfs[mother][mother])}))
        for self_code, wrap in selfs.items():
            inner = wrap.get(self_code) if isinstance(wrap, dict) else None
            if not isinstance(inner, dict):
                continue
            for pkind, partners in inner.items():
                if isinstance(partners, dict) and mother in partners and isinstance(partners[mother], dict) \
                        and mother in partners[mother]:
                    out.append(([kind, self_code, self_code, pkind, clone],
                                {clone: copy.deepcopy(partners[mother][mother])}))
    return out


# ============================================================ 计划

@dataclass
class Plan:
    edits: dict[str, list[tuple[list[str], Any]]] = field(default_factory=dict)   # 表 → [(path, 新节点|None)]
    files: dict[str, bytes] = field(default_factory=dict)                        # 逻辑路径 → 新文件字节
    clones: dict[str, dict] = field(default_factory=dict)                        # 克隆代号 → 说明
    report: dict = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    routine_sources: dict[str, str] = field(default_factory=dict)                # 自有 routine → 官方母本 routine

    def put(self, table: str, path: list[str], node) -> None:
        self.edits.setdefault(table, []).append((list(path), node))


def resolve_action(live: Live, src) -> str:
    """招式槽来源：直接给程序路径，或 {"from": 官方 boss 代号, "slot": 1..50} 取其 lv80 档该槽的程序
    （marker 时间轴里的 enemy_actionNN 标记按槽号触发，所以换槽内程序 = 同一时机放别的招）。"""
    if isinstance(src, str):
        return src
    tiers = gb_tiers(live, src["from"])
    prog = tiers[tier_for_level(tiers)][GB_ACTION_FIRST + int(src["slot"]) - 1]
    if not prog or prog == "(None)":
        raise BuildError(f"action donor {src['from']} slot {src['slot']} is empty")
    return prog


def resolve_by_element_nodes(tree) -> list[tuple[str, int]]:
    out, stack = [], [tree]
    while stack:
        n = stack.pop()
        if isinstance(n, list):
            if len(n) >= 3 and n[0] == "ResolveByElement" and isinstance(n[1], str):
                out.append((n[1], int(n[2])))
            stack.extend(n)
        elif isinstance(n, dict):
            stack.extend(n.values())
    return out


def orphan_endless_loops(live: Live, row: list[str], extra: dict[str, bytes]) -> list[str]:
    """无限循环要有人收：招式槽程序里次数 ≥1000 的 Repeat 靠同一钥匙的 RemoveEventFromOwner/RemoveEvent 撤除。
    借来的招式离开原主就没人撤，每放一次多一套循环，越打越卡（深界王借「暗影领域」，1.4.1097–1102 实机卡顿）。
    返回招式组里没有撤除者的循环钥匙。出场动作（词缀，登场只跑一次）不在此列。"""
    roots = [row[c] for c in range(GB_ACTION_FIRST, GB_ACTION_LAST + 1) if c < len(row) and row[c] not in ("", "(None)")]
    endless, removed = set(), set()
    for prog in dsl_closure(live, roots, extra)[0]:
        stack = [dsl_tree(live, prog, extra)]
        while stack:
            n = stack.pop()
            if isinstance(n, list):
                if len(n) > 3 and n[0] == "Repeat" and isinstance(n[2], (int, float)) and n[2] >= 1000:
                    endless.add(str(n[3]))
                if len(n) > 1 and n[0] in ("RemoveEventFromOwner", "RemoveEvent") and isinstance(n[1], str):
                    removed.add(n[1])
                stack.extend(n)
            elif isinstance(n, dict):
                stack.extend(n.values())
    return sorted(endless - removed)


def element_variant_anim(base: str, suffix: str) -> str:
    name = base.rsplit("/", 1)[-1]
    return f"{base}/{name}_{suffix}/{name}_{suffix}"


def element_variant_live(live: Live, base: str, suffix: str) -> bool:
    anim = element_variant_anim(base, suffix)
    sheet = sheet_of(anim)
    return live.file(anim + ".timeline.amf3.deflate") is not None and bool(sheet and png_dims(live, sheet + ".png"))


T_FUNNEL = "master/battle/boss/funnel/general_funnel.orderedmap"
SHIM_ELEMENT_CTORS = {"ResolveByElement": 2, "CreateNormalAttack": 2}   # 节点内「255=施法者属性」所在下标


def fired_action_slots(live: Live, marker_anim: str) -> set[int]:
    """marker 时间轴里出现过的 enemy_actionNN 点 = 会被触发的招式槽。"""
    raw = live.file(marker_anim + ".timeline.amf3.deflate") if marker_anim and marker_anim != "(None)" else None
    if raw is None:
        return set(range(1, 51))                       # 读不到就当全部会触发（不放垫片）
    out = set()
    for p in decode_amf(raw).get("points", []):
        m = re.match(r"enemy_action(\d+)$", p.get("path", ""))
        if m and any(fr.get("data") for fr in p.get("frames", [])):
            out.add(int(m.group(1)))
    return out


def spawned_funnels(live: Live, programs: Iterable[str], extra: dict[str, bytes]) -> set[str]:
    out = set()
    for prog in programs:
        stack = [dsl_tree(live, prog, extra)]
        while stack:
            n = stack.pop()
            if isinstance(n, list):
                if len(n) > 1 and n[0] == "SpawnFunnel" and isinstance(n[1], list) and n[1][:1] == ["Funnel"]:
                    out.add(n[1][1])
                stack.extend(n)
            elif isinstance(n, dict):
                stack.extend(n.values())
    return out


def plan_funnel_preload_shims(live: Live, plan: Plan, alias: str, row: list[str]) -> dict[int, str]:
    """C8016 垫片（2026-09-28 实机）：boss 改了属性后，它召唤的固定属性召唤物运行时按自身属性取图，
    预载却按 boss 属性登记 ⇒ 召唤物特效变体没预载。把召唤物招式程序各复制一份、属性码写死为召唤物属性，
    放进 marker 从不触发的空招式槽：客户端按全部 50 槽预载（ZoneSourceValues.resolveGeneralBosssAction），
    写死的属性码直接解析（ActionDslAssetResolver.resolveElement），程序本身永不执行。返回 {槽号: 程序}。"""
    cached = plan.report.setdefault("preload_shims", {}).get(alias)
    if cached is not None:
        return {int(k): v for k, v in cached.items()}
    own = int(row[0]) if row[0].isdigit() else None
    roots = split_programs(row[GB_PRE]) + [row[c] for c in range(GB_ACTION_FIRST, GB_ACTION_LAST + 1)
                                           if c < len(row) and row[c] not in ("", "(None)")]
    progs, _ = dsl_closure(live, roots, plan.files)
    funnels = live.table(T_FUNNEL)
    shims: list[str] = []
    for code in sorted(spawned_funnels(live, progs, plan.files)):
        node = funnels.get(code)
        if not isinstance(node, dict):
            continue
        frow = one_row(node[tier_for_level(node)])
        fel = int(frow[0]) if frow[0].isdigit() else None
        if fel is None or fel == own:
            continue
        fprogs, _ = dsl_closure(live, [c for c in frow if c.startswith("battle/action/")], plan.files)
        for i, prog in enumerate(sorted(fprogs)):
            tree = copy.deepcopy(dsl_tree(live, prog, plan.files))
            stack = [tree]
            while stack:
                n = stack.pop()
                if isinstance(n, list):
                    idx = SHIM_ELEMENT_CTORS.get(n[0]) if n and isinstance(n[0], str) else None
                    if idx is not None and len(n) > idx and n[idx] == 255:
                        n[idx] = fel
                    stack.extend(n)
                elif isinstance(n, dict):
                    stack.extend(n.values())
            path = f"{OWN_DSL_DIR}fb2_preload${alias}_{code}_{i}"
            plan.files[wf_dsl.dsl_logical(path)] = encode_dsl(tree)
            shims.append(path)
    free = [s for s in range(50, 0, -1) if s not in fired_action_slots(live, row[25] if len(row) > 25 else "")
            and row[GB_ACTION_FIRST + s - 1] in ("", "(None)")]
    if len(free) < len(shims):
        plan.problems.append(f"{alias}: {len(shims)} preload shims but only {len(free)} idle action slots")
        shims = shims[:len(free)]
    placed = dict(zip(free, shims))
    plan.report["preload_shims"][alias] = {str(k): v for k, v in placed.items()}
    return placed


def clone_code(variant: Variant, alias: str, wave: int, slot: int) -> str:
    return f"{OWN_CODE_PREFIX}{variant.quest % 1000:03d}_{alias}_w{wave}{slot}"


def plan_clone(live: Live, spec: dict, plan: Plan, variant: Variant, wave: int, slot: int, bs: BossSlot,
               programs: list[str], rerun: bool | None) -> str:
    bdef = spec["bosses"][bs.alias]
    mother = bdef["mother"]
    code = clone_code(variant, bs.alias, wave, slot)
    tiers = gb_tiers(live, mother)
    new_node = {}
    rc = bdef.get("recolor") or bdef.get("body")
    routine = (bdef.get("routine") or {}).get("out")
    for tier, row in tiers.items():
        r = list(row)
        if bs.position:
            r[GB_POS] = bs.position
        if routine:
            r[GB_ROUTINE] = routine
        if rc:
            # 换色/新造型：本体动画列改指新贴图（marker/影子等其余图集仍用官方件）
            for c in GB_ANIM_COLS:
                if c < len(r) and r[c] not in ("", "(None)") and sheet_of(r[c]) == rc["from"]:
                    if r[c] != rc["from"]:
                        raise BuildError(f"{mother} c{c}: {r[c]} is a sub-path of {rc['from']}; body swap unsupported")
                    r[c] = rc["out"]
        if bdef.get("element") is not None:
            r[0] = str(bdef["element"])            # 显式属性码（暗=6）；按属性取图的特效随之换色
        for action_slot, src in (bdef.get("actions") or {}).items():
            r[GB_ACTION_FIRST + int(action_slot) - 1] = resolve_action(live, src)
        for col, text in (bdef.get("texts") or {}).items():
            r[int(col)] = text
        if bdef.get("element") is not None:
            for action_slot, prog in plan_funnel_preload_shims(live, plan, bs.alias, r).items():
                r[GB_ACTION_FIRST + action_slot - 1] = prog
        signature = [affix_program(s) for s in bdef.get("signature", [])]
        pre = strip_v1_curse(split_programs(r[GB_PRE])) + list(bdef.get("pre", [])) + signature + programs
        # 官方 749 行：无出场动作一律写空串（681 行）；写 "(None)" 客户端会去加载
        # "(None).action.dsl.amf3.deflate" → 转阶段「数据不足」（2026-09-28 实机）
        r[GB_PRE] = ",".join(dict.fromkeys(pre)) if pre else ""
        if rerun is not None and pre:
            r[GB_PRE_RERUN] = "true" if rerun else "false"
        if bdef.get("name"):
            r[GB_NAME] = bdef["name"]
        new_node[tier] = write_rows([r])
    plan.put(T_GB, [code], new_node)
    # boss_level：按目标血量反算段数；眩晕改用 tp_normal
    bl_text = live.table(T_BL).get(mother)
    if not isinstance(bl_text, str):
        raise BuildError(f"boss_level missing: {mother}")
    bl = one_row(bl_text)
    if bl[0] != "0":
        raise BuildError(f"boss_level of {mother} is not Hit mode")
    # 曲线归一：hit_hp_correction_normal / atk_correction_normal / tp_basic_normal 是客户端内置曲线，
    # store 无数值 ⇒ 克隆统一改用已知曲线（lv80 下 atk_multi 与 atk_single 同值 1.992375），
    # 血量/眩晕随后按目标值重算；攻击差异由 c8 除数与 quest c102 承担。
    bl[BL_HP_CORR] = HP_CURVE_NORM
    bl[BL_ATK_CORR] = ATK_CURVE_NORM
    bl[BL_HP_HITS] = num(hits_for_hp(bl, bs.hp_e8))
    tp_target = spec["rounds"][variant.round]["tp_target"] * bdef.get("tp_scale", 1.0)
    bl[BL_TP_CURVE] = TP_CURVE
    bl[BL_TP_BASE] = num(round(tp_target / TP_NORMAL_LV80, 2))
    plan.put(T_BL, [code], write_rows([bl]))
    gbv = live.table(T_GBV).get(mother)
    if gbv is not None:
        plan.put(T_GBV, [code], copy.deepcopy(gbv))
    for path, node in watch_copies(live.table(T_GEW), mother, code):
        plan.put(T_GEW, path, node)
    tier80 = tiers[tier_for_level(tiers)]
    plan.clones[code] = {"mother": mother, "alias": bs.alias, "quest": variant.quest, "wave": wave, "slot": slot,
                         "hp_e8": bs.hp_e8, "tp": tp_target, "routine": tier80[GB_ROUTINE],
                         "position": bs.position or tier80[GB_POS], "pre": new_node[tier_for_level(tiers)]}
    return code


def plan_variant(live: Live, spec: dict, plan: Plan, variant: Variant, terrains: dict[str, dict]) -> None:
    rnd = spec["rounds"][variant.round]
    field_id = variant.field or rnd["field"]
    zone_id = f"{OWN_CODE_PREFIX}zone_{variant.quest}"
    fd_id = f"{OWN_CODE_PREFIX}fd_{variant.quest}"
    tz = rnd["zone_template"]
    zone_tpl = get_path(live.table(T_ZONE), tz)
    if not isinstance(zone_tpl, str):
        raise BuildError(f"zone template missing {tz}")
    tpl = one_row(zone_tpl)
    zone_node = {}
    for w, wave in enumerate(variant.waves):
        if len(wave) > 3:
            raise BuildError(f"{variant.quest} wave {w}: >3 boss slots")
        row = list(tpl)
        row[Z_GROUP] = str(variant.group_kind)
        for s, (k1, i1, k2, i2) in enumerate(Z_BOSS_SLOTS):
            row[k1], row[i1], row[k2], row[i2] = "(None)", "", "(None)", ""
        for s, bs in enumerate(wave):
            carrier = variant.group_kind == 1 or s == 0
            programs = []
            if carrier:
                if w == 0:
                    programs += [affix_program(a) for a in variant.entry_affixes]
                programs += [affix_program(a) for a in variant.affixes]
            rerun = False if (carrier and w == 0 and variant.entry_affixes) else None
            code = plan_clone(live, spec, plan, variant, w, s, bs, programs, rerun)
            k1, i1, k2, i2 = Z_BOSS_SLOTS[s]
            row[k1], row[i1], row[k2], row[i2] = "1", code, "1", code
        zone_node[str(w)] = write_rows([row])
    plan.put(T_ZONE, [zone_id], zone_node)
    plan.put(T_FD, [fd_id], write_rows([[field_id, terrains[variant.round]["out"], zone_id]]))
    # quest 行
    tq = rnd["quest_template"]
    qtext = get_path(live.table(T_BBQ), ["1", "99", tq])
    if not isinstance(qtext, str):
        raise BuildError(f"quest template missing 1/99/{tq}")
    r = one_row(qtext)
    r[0] = str(variant.quest)
    r[Q_NAME] = variant.name
    for c in Q_ENEMY_STATE:
        r[c] = "(None)" if (c - 74) % 2 == 0 else ""
    for i, (kind, strength) in enumerate(variant.enemy_states[:5]):
        r[74 + 2 * i] = str(kind)
        r[75 + 2 * i] = "" if strength is None else num(strength)
    r[Q_HP[0]], r[Q_HP[1]], r[Q_HP[2]] = (num(x) for x in rnd["hp_mult"])
    r[Q_ATK[0]], r[Q_ATK[1]], r[Q_ATK[2]] = (num(x) for x in rnd["atk_mult"])
    r[Q_TP[0]], r[Q_TP[1]], r[Q_TP[2]] = "1", "1", "1"
    r[Q_LEVEL] = str(LEVEL)
    r[Q_FEVER_CAP] = str(rnd["fever_cap"])
    r[Q_FIELD_DATA] = fd_id
    r[Q_TIME] = str(spec["time_limit_frames"])
    r[Q_IS_BOTH], r[Q_HIDDEN] = "false", "true"
    plan.put(T_BBQ, ["1", "99", str(variant.quest - 1099000)], write_rows([r]))


def plan_routes(live: Live, spec: dict, plan: Plan) -> None:
    r0 = [v for v in spec["_variants"] if v.round == "r0"]
    r1 = [v for v in spec["_variants"] if v.round == "r1"]
    if not r0 or not r1:
        raise BuildError("need at least one R0 and one R1 variant")
    base = int(spec["map_id_base"])
    names, ids = [], []
    for a in r0:
        for b in r1:
            mid = base + len(ids) + 1
            sid = f"{OWN_CODE_PREFIX}{a.quest % 1000:03d}x{b.quest % 1000:03d}"
            row = [sid, "0", str(ALWAYS_TRUE_THRESHOLD)] + ["(None)", ""] * 4 + [str(a.quest), str(b.quest),
                                                                                "(None)", "(None)"]
            plan.put(T_BBM, [str(mid)], write_rows([row]))
            names.append(sid)
            ids.append(str(mid))
    # 兜底行：无条件、带 default（id 最大，未装补丁/条件全不中时用）
    fb = spec["fallback_map_id"]
    fb_row = [f"{OWN_CODE_PREFIX}fallback"] + ["(None)", ""] * 5 + [str(r0[0].quest), str(r1[0].quest),
                                                                    str(r0[0].quest), str(r1[0].quest)]
    plan.put(T_BBM, [str(fb)], write_rows([fb_row]))
    names.append(fb_row[0])
    ids.append(str(fb))
    if int(fb) <= int(ids[-2]):
        raise BuildError("fallback map id must be the largest")
    plan.put(T_BBG, [str(spec["entry_quest"])], write_rows([[",".join(names), ",".join(ids)]]))
    plan.report["routes"] = {"rows": len(ids) - 1, "fallback": fb}


def plan_reward_display(spec: dict, plan: Plan) -> None:
    g = spec["reward_display"]
    node = {}
    for i, eid in enumerate(range(g["first_equipment"], g["last_equipment"] + 1), start=1):
        node[str(i)] = write_rows([[f"five_boss_cursed_{eid}", "1", str(eid), "1", "1"]])
    plan.put(T_AR, [str(g["group"])], node)


def plan_envy_revert(live: Live, official_loader: Callable[[], bytes] | None, plan: Plan) -> None:
    """1.4.802 把官方 routine devil_commander_evil_envy_80 的 c23 80→240（296 行）；还原为官方 1.4.0 子树。"""
    code = "devil_commander_evil_envy_80"
    live_node = live.table(T_GBS).get(code)
    if official_loader is None:
        plan.warnings.append("envy revert skipped: no official loader")
        return
    official = q.parse_node(official_loader()).get(code)
    if official is None:
        raise BuildError("official general_boss_state lacks envy routine")
    if live_node == official:
        plan.report["envy_revert"] = "already official"
        return
    # 只允许 c23 = 3×官方 这一种差异，其他差异拒绝（防止误覆盖别人的改动）
    def rows(n, pre=()):
        if isinstance(n, dict):
            for k, v in n.items():
                yield from rows(v, pre + (k,))
        else:
            for i, r in enumerate(read_rows(n)):
                yield pre + (str(i),), r
    lo, oo = dict(rows(live_node)), dict(rows(official))
    if set(lo) != set(oo):
        raise BuildError("envy routine shape differs from official; refusing blind revert")
    for k in lo:
        a, b = lo[k], oo[k]
        if a == b:
            continue
        diff = [i for i in range(max(len(a), len(b))) if (a[i] if i < len(a) else None) != (b[i] if i < len(b) else None)]
        if diff != [23] or float(a[23]) != 3 * float(b[23]):
            raise BuildError(f"unexpected envy diff at {k}: cols {diff}")
    plan.put(T_GBS, [code], official)
    plan.report["envy_revert"] = sum(1 for k in lo if lo[k] != oo[k])


def official_table_loader(logical: str) -> Callable[[], bytes]:
    """从 .cdn/cn/archive-common-full 的官方 1.4.0 全量包里取表原字节。"""
    import zipfile
    rel = q.hashed_rel(logical)

    def load() -> bytes:
        for z in sorted((ROOT / ".cdn/cn/archive-common-full").glob("pinball-1.4.0-*.zip")):
            with zipfile.ZipFile(z) as zf:
                for n in zf.namelist():
                    if n.endswith(rel):
                        return zf.read(n)
        raise BuildError(f"official {logical} not found")
    return load


# ============================================================ 美术（UI 图、场地背景、道具图标）

def decode_amf(raw: bytes):
    return wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]


def encode_amf(tree) -> bytes:
    """atlas/parts/timeline 与 DSL 同一容器（AMF3 + raw deflate），写前往返自检。"""
    raw = wf_dsl.encode_amf3(tree)
    if wf_dsl.parse_dsl(raw)["tree"] != tree:
        raise BuildError("AMF3 encode round-trip mismatch")
    comp = zlib.compressobj(9, zlib.DEFLATED, -15)
    return comp.compress(raw) + comp.flush()


def open_png(raw: bytes):
    from PIL import Image
    im = Image.open(io.BytesIO(wf_assets.png_decode(raw)))
    im.load()
    return im


def store_png_bytes(im) -> bytes:
    """PIL 重存一遍（去掉非常规块、调色板转 RGBA）后换成 store 的混淆魔数。"""
    if im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGBA")
    buf = io.BytesIO()
    im.save(buf, format="PNG", optimize=True)
    return wf_assets.png_encode(buf.getvalue())


def extrude(im, pad: int = 1):
    """官方背景图集四周 1px 是边缘像素外扩（不是透明），防止缩放采样时边缘渗黑。"""
    from PIL import Image
    w, h = im.size
    out = Image.new(im.mode, (w + 2 * pad, h + 2 * pad))
    out.paste(im, (pad, pad))
    for i in range(pad):
        out.paste(im.crop((0, 0, w, 1)), (pad, i))
        out.paste(im.crop((0, h - 1, w, h)), (pad, h + pad + i))
    left = out.crop((pad, 0, pad + 1, h + 2 * pad))
    right = out.crop((w + pad - 1, 0, w + pad, h + 2 * pad))
    for i in range(pad):
        out.paste(left, (i, 0))
        out.paste(right, (w + pad + i, 0))
    return out


def gen_region_name(base: str) -> str:
    """flatomo 背景的子纹理名：<目录>/.gen/<文件名>/a（官方 beast_ruins/水晶神殿同式）。"""
    head, tail = base.rsplit("/", 1)
    return f"{head}/.gen/{tail}/a"


def recolor_rgb(rgb: tuple, rules: list[dict]) -> tuple:
    """按色相带逐色映射（第一条命中的规则生效）：h 区间可跨 0°，to_h 定新色相，s/v 乘加微调。"""
    h, s, v = colorsys.rgb_to_hsv(*(c / 255 for c in rgb))
    hd = h * 360
    for r in rules:
        lo, hi = r.get("h", [0, 360])
        in_h = (lo <= hd <= hi) if lo <= hi else (hd >= lo or hd <= hi)
        if not in_h or not r.get("s_min", 0) <= s <= r.get("s_max", 1) \
                or not r.get("v_min", 0) <= v <= r.get("v_max", 1):
            continue
        nh = r["to_h"] / 360 if "to_h" in r else (h + r.get("rot", 0) / 360) % 1
        ns = min(1.0, max(0.0, s * r.get("s_mul", 1) + r.get("s_add", 0)))
        nv = min(1.0, max(0.0, v * r.get("v_mul", 1) + r.get("v_add", 0)))
        return tuple(round(c * 255) for c in colorsys.hsv_to_rgb(nh, ns, nv))
    return tuple(rgb)


def gen_prefix(base: str) -> str:
    head, tail = base.rsplit("/", 1)
    return f"{head}/.gen/{tail}/"


def rename_prefix(node, old: str, new: str):
    if isinstance(node, str):
        return new + node[len(old):] if node.startswith(old) else node
    if isinstance(node, list):
        return [rename_prefix(x, old, new) for x in node]
    if isinstance(node, dict):
        return {k: rename_prefix(v, old, new) for k, v in node.items()}
    return node


def plan_recolors(live: Live, spec: dict, plan: Plan) -> None:
    """换色克隆 boss 的本体贴图：官方本体是调色板 PNG ⇒ 只改调色板条目、索引不动（像素排布、透明、
    子纹理坐标全保持）；atlas/parts 里的子纹理名换成新目录，timeline 原样。
    general 没有 ColorMatrix 字段（research D §5），换色只能出新贴图。"""
    used = {bs.alias for v in spec["_variants"] for wave in v.waves for bs in wave}
    for alias, bdef in spec["bosses"].items():
        rc = bdef.get("recolor")
        if not rc or alias not in used:
            continue
        old, new = rc["from"], rc["out"]
        if not new.startswith(OWN_BOSS_DIR) or sheet_of(new) != new:
            plan.problems.append(f"recolor {alias}: out must be {OWN_BOSS_DIR}<name>/<name>")
            continue
        raws = {suf: live.file(old + suf) for suf in (".png",) + PARTS_SUFFIXES}
        if any(v is None for v in raws.values()):
            raise BuildError(f"recolor {alias}: {old} is not a complete PartsAnimation")
        sheet = open_png(raws[".png"])
        if sheet.mode != "P":
            plan.problems.append(f"recolor {alias}: {old} is {sheet.mode}, palette sheet expected")
            continue
        pal = sheet.getpalette()
        new_pal = []
        for i in range(0, len(pal), 3):
            new_pal += recolor_rgb(tuple(pal[i:i + 3]), rc["rules"])
        out = sheet.copy()
        out.putpalette(new_pal)
        buf = io.BytesIO()
        kw = {"transparency": sheet.info["transparency"]} if "transparency" in sheet.info else {}
        out.save(buf, format="PNG", **kw)
        plan.files[new + ".png"] = wf_assets.png_encode(buf.getvalue())
        old_dir = old.rsplit("/", 1)[0] + "/"
        for suf in (".atlas.amf3.deflate", ".parts.amf3.deflate", ".timeline.amf3.deflate"):
            tree = rename_prefix(decode_amf(raws[suf]), gen_prefix(old), gen_prefix(new))
            if old_dir in json.dumps(tree, ensure_ascii=False):
                plan.problems.append(f"recolor {alias}: {suf} still references {old_dir}")
            plan.files[new + suf] = raws[suf] if suf.startswith(".timeline") else encode_amf(tree)
        changed = sum(1 for i in range(0, len(pal), 3) if tuple(pal[i:i + 3]) != tuple(new_pal[i:i + 3]))
        plan.report.setdefault("recolors", {})[alias] = {"from": old, "out": new, "palette_changed": changed}


TRIAL_KINDS = {"direct": "0", "skill": "1", "pf": "2", "skill_chain": "3"}   # general_boss_state c22


def plan_routines(live: Live, spec: dict, plan: Plan) -> None:
    """带试炼的 routine：官方母本整棵复制到自有键，只在点名的蓄力状态上挂命中检定（统领 AI 试炼
    mod_fb_hero_trial/shot3_fb_charge 同形，实机已见试炼条）：c22 种类、c23 次数、c24 倒数、c25 破条硬直；
    下一状态判定改 c29=12（HitCountCheck）：达成 → 跳到大招之后的状态（大招取消），未达成 → 原大招；
    c46/c47 把蓄力拉长为倒数时长。"""
    used = {bs.alias for v in spec["_variants"] for wave in v.waves for bs in wave}
    gbs = live.table(T_GBS)
    for alias, bdef in spec["bosses"].items():
        rt = bdef.get("routine")
        if not rt or alias not in used:
            continue
        tiers = gb_tiers(live, bdef["mother"])
        src = tiers[tier_for_level(tiers)][GB_ROUTINE]
        node = gbs.get(src)
        if not isinstance(node, dict):
            raise BuildError(f"routine missing: {src}")
        out = rt["out"]
        if not out.startswith(OWN_CODE_PREFIX):
            plan.problems.append(f"routine {out} lacks own prefix")
            continue
        new_node = copy.deepcopy(node)
        for tier, states in new_node.items():
            for state, cfg in rt.get("trials", {}).items():
                if state not in states:
                    raise BuildError(f"{src}/{tier}: no state {state}")
                r = one_row(states[state])
                fail = r[31]
                if r[29] != "0" or fail not in states:
                    raise BuildError(f"{src}/{tier}/{state}: expected an Always transition into the attack")
                success = cfg.get("success") or one_row(states[fail])[31]
                if success not in states:
                    raise BuildError(f"{src}/{tier}/{state}: success state {success} missing")
                r[22], r[23], r[24], r[25], r[26] = TRIAL_KINDS[cfg["kind"]], str(cfg["count"]), "true", \
                    "true" if cfg.get("wince", True) else "false", "(None)"
                r[29], r[30], r[31], r[32] = "12", "0", success, fail
                r[46], r[47] = "2", str(cfg["frames"])
                states[state] = write_rows([r])
        plan.put(T_GBS, [out], new_node)
        plan.routine_sources[out] = src
        plan.report.setdefault("routines", {})[out] = {"from": src, "trials": sorted(rt.get("trials", {}))}


def pack_frames(frames: list, margin: int = 1, gap: int = 2):
    """整帧画布（fw×fh）→ 裁掉透明边 → 行式打包。返回 (sheet, entries)；entries 与 frames 同序，
    键序照官方 atlas（n,w,h,x,y,fx,fy,fw,fh；fx/fy = 负的裁切偏移）。全透明帧占 1×1。"""
    from PIL import Image
    cuts = []
    for name, im in frames:
        bb = im.getchannel("A").getbbox() or (0, 0, 1, 1)
        cuts.append((name, im.crop(bb), bb, im.size))
    best = None
    for width in (128, 256, 384, 512, 768, 1024):
        if max(c[1].width for c in cuts) + 2 * margin > width:
            continue
        order = sorted(range(len(cuts)), key=lambda i: -cuts[i][1].height)
        pos, x, y, shelf = {}, margin, margin, 0
        for i in order:
            w, h = cuts[i][1].size
            if x + w + margin > width:
                x, y, shelf = margin, y + shelf + gap, 0
            pos[i] = (x, y)
            x += w + gap
            shelf = max(shelf, h)
        height = y + shelf + margin
        if best is None or width * height < best[0] * best[1]:
            best = (width, height, pos)
    width, height, pos = best
    sheet = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    entries = []
    for i, (name, reg, bb, (fw, fh)) in enumerate(cuts):
        x, y = pos[i]
        sheet.paste(reg, (x, y))
        entries.append({"n": name, "w": reg.width, "h": reg.height, "x": x, "y": y,
                        "fx": -bb[0], "fy": -bb[1], "fw": fw, "fh": fh})
    return sheet, entries


def plan_bodies(live: Live, spec: dict, plan: Plan) -> None:
    """全新造型本体：沿用官方母本的 parts/timeline（动作序列、变换矩阵、碰撞圆不变），51 张图换成新画的
    整帧（imgNN_<短名>.png，画布尺寸必须与母本一致），重新打包成自有目录的图集；子纹理名换成新目录。"""
    from PIL import Image
    used = {bs.alias for v in spec["_variants"] for wave in v.waves for bs in wave}
    for alias, bdef in spec["bosses"].items():
        body = bdef.get("body")
        if not body or alias not in used:
            continue
        old, new = body["from"], body["out"]
        if not new.startswith(OWN_BOSS_DIR) or sheet_of(new) != new:
            plan.problems.append(f"body {alias}: out must be {OWN_BOSS_DIR}<name>/<name>")
            continue
        raws = {suf: live.file(old + suf) for suf in (".png",) + PARTS_SUFFIXES}
        if any(v is None for v in raws.values()):
            raise BuildError(f"body {alias}: {old} is not a complete PartsAnimation")
        parts = decode_amf(raws[".parts.amf3.deflate"])
        atlas = {e["n"]: e for e in decode_amf(raws[".atlas.amf3.deflate"])}
        frames_dir = Path(body["frames"]) if Path(body["frames"]).is_absolute() else TOOLS / body["frames"]
        frames = []
        for i, it in enumerate(parts["i"]):
            src = atlas[it["p"]]
            short = it["p"].rsplit("/", 1)[-1]
            p = frames_dir / f"img{i:02d}_{short}.png"
            if not p.exists():
                plan.problems.append(f"body {alias}: missing frame {p.name}")
                continue
            im = Image.open(p).convert("RGBA")
            want = (src.get("fw", src["w"]), src.get("fh", src["h"]))
            if im.size != want:
                plan.problems.append(f"body {alias}: {p.name} is {im.size[0]}x{im.size[1]}, canvas {want[0]}x{want[1]}")
                continue
            if sum(im.getchannel("A").histogram()[1:255]):
                # 官方本体也有少量半透明（发光/残影）；新画的帧应为二值 alpha，这里只提醒不拦
                plan.warnings.append(f"body {alias}: {p.name} has semi-transparent pixels")
            frames.append((rename_prefix(it["p"], gen_prefix(old), gen_prefix(new)), im))
        if len(frames) != len(parts["i"]):
            continue
        sheet, entries = pack_frames(frames)
        new_parts = rename_prefix(parts, gen_prefix(old), gen_prefix(new))
        if {i["p"] for i in new_parts["i"]} != {e["n"] for e in entries}:
            raise BuildError(f"body {alias}: parts/atlas names diverged")
        plan.files[new + ".png"] = store_png_bytes(sheet)
        plan.files[new + ".atlas.amf3.deflate"] = encode_amf(entries)
        plan.files[new + ".parts.amf3.deflate"] = encode_amf(new_parts)
        plan.files[new + ".timeline.amf3.deflate"] = raws[".timeline.amf3.deflate"]
        plan.report.setdefault("bodies", {})[alias] = {"from": old, "out": new, "frames": len(frames),
                                                       "sheet": list(sheet.size)}


def plan_ui_files(live: Live, spec: dict, plan: Plan) -> None:
    """事件页头图、商店横幅、缩略图、道具小图：同尺寸原位替换；新路径须在 spec 写明尺寸。"""
    from PIL import Image
    for item in spec.get("art", {}).get("files", []):
        logical = item["logical"]
        im = Image.open(TOOLS / item["src"])
        im.load()
        cur = live.file(logical)
        if "size" in item:
            want = tuple(item["size"])
        elif cur is not None:
            want = open_png(cur).size
        else:
            plan.problems.append(f"art {logical}: new path needs an explicit size")
            continue
        if im.size != want:
            plan.problems.append(f"art {logical}: {im.size[0]}x{im.size[1]} != {want[0]}x{want[1]}")
            continue
        plan.files[logical] = store_png_bytes(im)


def plan_fields(live: Live, spec: dict, plan: Plan) -> None:
    """新建自有 field 行：背景四件套从母本行克隆，只换 PNG 与子纹理名；其余列沿用母本，可按列覆盖。
    背景像素即地形坐标（官方白虎/水晶神殿平移均为 0,0）⇒ 新图尺寸必须与母本子纹理相同。"""
    from PIL import Image
    fld = live.table(T_FIELD)
    for fid, fdef in spec.get("art", {}).get("fields", {}).items():
        mother_text = fld.get(fdef["from"])
        if not isinstance(mother_text, str):
            raise BuildError(f"field row missing: {fdef['from']}")
        row = one_row(mother_text)
        old_base, new_base = row[FIELD_BG_COL], fdef["background"]["out"]
        raws = {suf: live.file(old_base + suf) for suf in PARTS_SUFFIXES}
        if any(v is None for v in raws.values()):
            raise BuildError(f"{old_base}: background parts incomplete")
        parts = decode_amf(raws[".parts.amf3.deflate"])
        atlas = decode_amf(raws[".atlas.amf3.deflate"])
        if len(atlas) != 1 or len(parts.get("i", [])) != 1 or atlas[0]["n"] != gen_region_name(old_base) \
                or parts["i"][0]["p"] != atlas[0]["n"]:
            raise BuildError(f"{old_base}: not a single-region flatomo background")
        region = atlas[0]
        src = Image.open(TOOLS / fdef["background"]["src"])
        src.load()
        if src.size != (region["w"], region["h"]):
            plan.problems.append(f"field {fid}: background {src.size[0]}x{src.size[1]} != "
                                 f"{region['w']}x{region['h']} of {fdef['from']} (terrain alignment)")
            continue
        name = gen_region_name(new_base)
        new_parts = copy.deepcopy(parts)
        new_parts["i"][0]["p"] = name
        new_region = dict(region)
        new_region["n"] = name
        pad = region["x"]
        plan.files[new_base + ".png"] = store_png_bytes(extrude(src, pad))
        plan.files[new_base + ".parts.amf3.deflate"] = encode_amf(new_parts)
        plan.files[new_base + ".atlas.amf3.deflate"] = encode_amf([new_region])
        plan.files[new_base + ".timeline.amf3.deflate"] = raws[".timeline.amf3.deflate"]
        row[FIELD_BG_COL] = new_base
        for col, val in fdef.get("set", {}).items():
            row[int(col)] = val
        plan.put(T_FIELD, [fid], write_rows([row]))
    plan.report["fields"] = sorted(spec.get("art", {}).get("fields", {}))


def atlas_rect(e: dict) -> tuple[int, int, int, int]:
    # r=true 时 w/h 的含义两种说法都有，按外接正方形保守占位
    w, h = (max(e["w"], e["h"]),) * 2 if e.get("r") else (e["w"], e["h"])
    return e["x"], e["y"], e["x"] + w, e["y"] + h


def find_atlas_slot(entries: list[dict], sheet, size: tuple[int, int]):
    """在现有画布里找一块不与任何条目（含间隔）重叠、且连同 1px 外圈全透明的位置；
    没有就向下扩画布。既有条目的 x/y/w/h 一律不动。返回 (x, y, sheet)。"""
    from PIL import Image
    w, h = size
    W, H = sheet.size
    rects = [atlas_rect(e) for e in entries]
    xs = sorted({1} | {r[2] + ATLAS_GAP for r in rects})
    ys = sorted({1} | {r[3] + ATLAS_GAP for r in rects})
    for y in ys:
        for x in xs:
            if x + w + 1 > W or y + h + 1 > H:
                continue
            if any(x < r[2] + ATLAS_GAP and r[0] < x + w + ATLAS_GAP and
                   y < r[3] + ATLAS_GAP and r[1] < y + h + ATLAS_GAP for r in rects):
                continue
            if sheet.crop((x - 1, y - 1, x + w + 1, y + h + 1)).getextrema()[3] == (0, 0):
                return x, y, sheet
    y = max(r[3] for r in rects) + ATLAS_GAP
    grown = Image.new("RGBA", (W, y + h + 1), (0, 0, 0, 0))
    grown.paste(sheet, (0, 0))
    return 1, y, grown


def plan_item_icons(live: Live, spec: dict, plan: Plan) -> None:
    """item_icon 共享图集追加子纹理；道具行 c3/c4 只在 live 已有对应资源时才改。
    顺序是硬约束：c4 指向的子纹理不在已加载图集 ⇒ 掉落展示/商店同步取图当场 C8004
    （memory wf-c8004-small-icon-atlas-rule）。所以同一次暂存里图集和道具行不会同时出现：
    先发图集这条边，下一次重暂存时道具行自动进来。图集 PNG 与 atlas 两个文件必须同边。"""
    from PIL import Image
    art = spec.get("art", {})
    entries = decode_amf(live.file(ITEM_ATLAS_FILES[1]))
    live_names = {e["n"] for e in entries}
    sheet = open_png(live.file(ITEM_ATLAS_FILES[0])).convert("RGBA")
    new_entries = copy.deepcopy(entries)
    changed = False
    for icon in art.get("atlas_icons", []):
        im = Image.open(TOOLS / icon["src"]).convert("RGBA")
        hit = next((e for e in new_entries if e["n"] == icon["name"]), None)
        if hit is not None:
            if hit.get("r") or (hit["w"], hit["h"]) != im.size:
                plan.problems.append(f"atlas {icon['name']}: existing region shape differs; refusing to repack")
                continue
            box = (hit["x"], hit["y"])
            if sheet.crop(box + (box[0] + im.size[0], box[1] + im.size[1])).tobytes() == im.tobytes():
                continue
            sheet.paste(im, box)
        else:
            x, y, sheet = find_atlas_slot(new_entries, sheet, im.size)
            sheet.paste(im, (x, y))
            new_entries.append({"n": icon["name"], "w": im.size[0], "h": im.size[1], "x": x, "y": y})
        changed = True
    if changed:
        plan.files[ITEM_ATLAS_FILES[0]] = store_png_bytes(sheet)
        plan.files[ITEM_ATLAS_FILES[1]] = encode_amf(new_entries)
        plan.report["item_atlas"] = {"entries": len(new_entries), "size": list(sheet.size)}
    items = live.table(T_ITEM)
    for iid, cols in art.get("item_icons", {}).items():
        text = items.get(iid)
        if not isinstance(text, str):
            raise BuildError(f"item row missing: {iid}")
        if cols["small"] not in live_names or live.file(cols["thumbnail"] + ".png") is None:
            plan.warnings.append(f"item {iid}: icon not live yet, c3/c4 deferred to the next edge")
            continue
        row = one_row(text)
        want = list(row)
        want[ITEM_THUMB_COL], want[ITEM_SMALL_COL] = cols["thumbnail"], cols["small"]
        if want != row:
            plan.put(T_ITEM, [iid], write_rows([want]))


def plan_shop_icons(live: Live, spec: dict, plan: Plan) -> None:
    """领主币商店商品自带商品图列（独立 PNG，与道具 c3 同通道）；同样等图上线后才改。"""
    shop = live.table(T_SHOP)
    for key, cfg in spec.get("art", {}).get("shop_icons", {}).items():
        text = shop.get(key)
        if not isinstance(text, str):
            raise BuildError(f"shop row missing: {key}")
        if live.file(cfg["value"] + ".png") is None:
            plan.warnings.append(f"shop {key}: icon not live yet, deferred to the next edge")
            continue
        row = one_row(text)
        if row[cfg["col"]] != cfg["value"]:
            row[cfg["col"]] = cfg["value"]
            plan.put(T_SHOP, [key], write_rows([row]))


def plan_node_thumbnail(live: Live, spec: dict, plan: Plan) -> None:
    cfg = spec.get("art", {}).get("node_thumbnail")
    if not cfg:
        return
    text = get_path(live.table(T_NODE), cfg["path"])
    if not isinstance(text, str):
        raise BuildError(f"stage node missing: {cfg['path']}")
    thumb = cfg["value"]
    if live.file(thumb + ".png") is None and thumb + ".png" not in plan.files:
        plan.problems.append(f"stage node thumbnail {thumb} does not exist")
        return
    row = one_row(text)
    if row[cfg["col"]] != thumb:
        row[cfg["col"]] = thumb
        plan.put(T_NODE, list(cfg["path"]), write_rows([row]))


# ============================================================ 门禁

def routine_positions(live: Live, routine: str) -> set[str]:
    node = live.table(T_GBS).get(routine)
    out: set[str] = set()

    def walk(n):
        if isinstance(n, dict):
            for v in n.values():
                walk(v)
        elif isinstance(n, str):
            for r in read_rows(n):
                if len(r) > 50 and r[50] and r[50] != "(None)":
                    out.add(r[50])
    walk(node)
    return out


PROGRAM_RE = re.compile(r"battle/action/[A-Za-z0-9_/\$\.\-]+")


def dsl_tree(live: Live, program: str, extra: dict[str, bytes]):
    lg = wf_dsl.dsl_logical(program)
    raw = extra.get(lg) or live.file(lg)
    if raw is None:
        return None
    return wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]


def dsl_closure(live: Live, roots: list[str], extra: dict[str, bytes], limit: int = 800):
    seen, strings = set(), set()
    queue = list(roots)
    while queue and len(seen) < limit:
        prog = queue.pop()
        if prog in seen:
            continue
        seen.add(prog)
        tree = dsl_tree(live, prog, extra)
        if tree is None:
            continue

        def walk(n):
            if isinstance(n, str):
                if n.startswith("battle/action/"):
                    if n not in seen:
                        queue.append(n)
                elif "/" in n and (n.startswith("battle/") or n.startswith("character/")):
                    strings.add(n)
            elif isinstance(n, list):
                for x in n:
                    walk(x)
            elif isinstance(n, dict):
                for x in n.values():
                    walk(x)
        walk(tree)
    return seen, strings


def funnel_groups(live: Live, programs: set[str], extra: dict[str, bytes]) -> set[int]:
    g = set()
    for prog in programs:
        tree = dsl_tree(live, prog, extra)
        if tree is None:
            continue
        for c in wf_dsl.iter_dsl_commands(tree, "SpawnFunnel"):
            pt = c[3] if len(c) > 3 else None
            if isinstance(pt, list) and pt and pt[0] == "FunnelGroup":
                g.add(int(pt[1]))
    return g


ELEMENT_SUFFIX = {0: "red", 1: "blue", 2: "yellow", 3: "green", 4: "white", 5: "black", 6: "colorless"}


def sheet_of(anim: str) -> str | None:
    """AssetPathCollectionBuilder.addAnimationLayout：动画路径 → 精灵表（battle/ 目录名写两遍；
    character/ 取同目录 sprite_sheet，special 取 special_sprite_sheet）。"""
    if not (anim.startswith("battle/") or anim.startswith("character/")) or anim.startswith("battle/common"):
        return None
    parts = anim.split("/")
    if anim.startswith("character/"):
        tail = "special_sprite_sheet" if parts[-1] == "special" else "sprite_sheet"
        return "/".join(parts[:-1] + [tail])
    parts = parts[:-1]
    if not parts:
        return None
    d = parts.pop()
    return "/".join(parts + [d, d])


def is_layer0(sheet: str) -> bool:
    return (sheet.startswith(("battle/effect/", "battle/field_object/", "battle/boss/", "battle/zako/",
                              "battle/funnel/", "battle/uncommon/layer0/")) or "battle/field/" in sheet
            or (sheet.startswith("character/") and "/pixelart/" in sheet))


def png_dims(live: Live, logical: str) -> tuple[int, int] | None:
    rel = q.hashed_rel(logical)
    base = q.store_path(logical).parents[1]
    for root in (base, base.parent / "medium_upload", base.parent / "android_upload"):
        p = root / rel
        if p.exists():
            with p.open("rb") as fh:
                head = fh.read(32)
            if head[1:4] in (b"PNG", b"png") and head[12:16] == b"IHDR":
                return struct.unpack(">II", head[16:24])
    return None


def boss_sheets(live: Live, code_rows: dict[str, list[str]], extra: dict[str, bytes]) -> dict[str, tuple[int, int]]:
    """一组 boss（代号 → lv80 行）的 layer0 精灵表并集：动画列 + 出场/出招 DSL 闭包，外加**施法者自身属性**的
    ResolveByElement 色替弹幕（每只 boss 单算后取并集，不做属性交叉）。"""
    anims: set[str] = set()
    for row in code_rows.values():
        roots: list[str] = []
        for c in GB_ANIM_COLS:
            v = row[c] if c < len(row) else ""
            if v and v != "(None)" and "/" in v:
                anims.add(v)
        roots += split_programs(row[GB_PRE])
        for c in range(GB_ACTION_FIRST, GB_ACTION_LAST + 1):
            if c < len(row):
                roots += PROGRAM_RE.findall(row[c] or "")
        try:
            suf = ELEMENT_SUFFIX.get(int(row[0]) - 1)
        except ValueError:
            suf = None
        progs, strings = dsl_closure(live, roots, extra)
        for s in strings:
            anims.add(s)
            if suf:
                name = s.rsplit("/", 1)[-1]
                anims.add(f"{s}/{name}_{suf}/{name}_{suf}")
        for prog in progs:                      # 写死属性码的色替（含 C8016 垫片）也要计入
            tree = dsl_tree(live, prog, extra)
            for base, el in (resolve_by_element_nodes(tree) if tree is not None else []):
                if el != 255 and ELEMENT_SUFFIX.get(el - 1):
                    anims.add(element_variant_anim(base, ELEMENT_SUFFIX[el - 1]))
    out = {}
    for a in sorted(anims):
        sh = sheet_of(a)
        if not sh or not is_layer0(sh) or sh in out:
            continue
        staged = extra.get(sh + ".png")          # 本次新生成（换色本体等）尚未上线的贴图也要计入
        d = open_png(staged).size if staged is not None else png_dims(live, sh + ".png")
        if d:
            out[sh] = d
    return out


def mpx(sheets: dict[str, tuple[int, int]]) -> float:
    return sum((w + 2) * (h + 2) for w, h in sheets.values()) / 1e6


def gate_variant(live: Live, spec: dict, plan: Plan, variant: Variant, terrain_tree: dict) -> dict:
    pos_layers = terrain_positions(terrain_tree)
    fs_layers = terrain_funnel_groups(terrain_tree)
    rows = {}
    for code, info in plan.clones.items():
        if info["quest"] != variant.quest:
            continue
        tiers = next(n for p, n in plan.edits[T_GB] if p == [code])
        row = one_row(tiers[tier_for_level(tiers)])
        rows[code] = row
        w = info["wave"]
        layer = min(w, len(pos_layers) - 1)
        routine = plan.routine_sources.get(row[GB_ROUTINE], row[GB_ROUTINE])   # 自有试炼 routine 按母本查站位
        need = {info["position"]} | routine_positions(live, routine)
        need.discard("(None)")
        missing = sorted(need - pos_layers[layer])
        if missing:
            plan.problems.append(f"{variant.quest} {code}: positions {missing} not in terrain layer {layer}")
        if row[GB_PRE].strip() == "(None)":
            plan.problems.append(f"{variant.quest} {code}: c109 '(None)' is loaded as a file name by the client")
        roots = split_programs(row[GB_PRE])
        for c in range(GB_ACTION_FIRST, GB_ACTION_LAST + 1):
            roots += PROGRAM_RE.findall(row[c] or "")
        progs, _ = dsl_closure(live, roots, plan.files)
        groups = funnel_groups(live, progs, plan.files)
        lack = sorted(groups - fs_layers[layer])
        if lack:
            plan.problems.append(f"{variant.quest} {code}: FUNNEL_SPAWN{lack} missing in terrain layer {layer}")
        for prog in roots:
            if dsl_tree(live, prog, plan.files) is None:
                plan.problems.append(f"{variant.quest} {code}: missing DSL {prog}")
        # 按属性取图（ResolveByElement，255=施法者属性）：换属性/借招式后变体必须存在，否则进战斗「数据不足」。
        # 一族变体在 store 里一个都没有 = 随 APK 资源包下发（客户端回落 APK），这里核不了，只记警告。
        own = ELEMENT_SUFFIX.get(int(row[0]) - 1) if row[0].isdigit() else None
        lacking, unverifiable = set(), set()
        for prog in progs:
            tree = dsl_tree(live, prog, plan.files)
            for base, el in (resolve_by_element_nodes(tree) if tree is not None else []):
                suffix = own if el == 255 else ELEMENT_SUFFIX.get(el - 1)
                if suffix is None:
                    lacking.add(f"{base} (element {el})")
                elif not element_variant_live(live, base, suffix):
                    if any(element_variant_live(live, base, s) for s in ELEMENT_SUFFIX.values()):
                        lacking.add(element_variant_anim(base, suffix))
                    else:
                        unverifiable.add(base)
        if lacking:
            plan.problems.append(f"{variant.quest} {code}: element variants missing {sorted(lacking)[:3]}")
        orphan = orphan_endless_loops(live, row, plan.files)
        if orphan:
            plan.problems.append(f"{variant.quest} {code}: endless action loops with no remover in the kit {orphan}")
        if unverifiable:
            plan.report.setdefault("element_variants_in_apk", set()).update(unverifiable)
    sheets = boss_sheets(live, rows, plan.files)
    m = mpx(sheets)
    lim = spec["budget"]
    verdict = "PASS" if m <= lim["pass_mpx"] else ("WARN" if m <= lim["fail_mpx"] else "FAIL")
    if verdict == "FAIL":
        plan.problems.append(f"{variant.quest}: boss atlas {m:.2f} Mpx > {lim['fail_mpx']}")
    elif verdict == "WARN":
        plan.warnings.append(f"{variant.quest}: boss atlas {m:.2f} Mpx (WARN band, run MC before sharing)")
    return {"mpx": round(m, 3), "verdict": verdict, "sheets": len(sheets),
            "tallest": max((h for _, h in sheets.values()), default=0)}


def gate_codes(live: Live, spec: dict, plan: Plan) -> None:
    gb = live.table(T_GB)
    owned_prefix = OWN_CODE_PREFIX
    for code in plan.clones:
        if not code.startswith(owned_prefix):
            plan.problems.append(f"clone code {code} lacks own prefix")
    for path, _ in plan.edits.get(T_GB, []):
        code = path[0]
        if code in gb and not code.startswith(owned_prefix):
            plan.problems.append(f"would overwrite non-owned general_boss {code}")
    for table in (T_ZONE, T_FD, T_FIELD):
        for path, _ in plan.edits.get(table, []):
            if not path[0].startswith(owned_prefix):
                plan.problems.append(f"{table}: non-owned key {path[0]}")
    for path, _ in plan.edits.get(T_GBS, []):
        if not path[0].startswith(owned_prefix) and path[0] != "devil_commander_evil_envy_80":   # 唯一例外：嫉妒还原
            plan.problems.append(f"{T_GBS}: non-owned routine {path[0]}")
    for prog_logical in plan.files:
        if prog_logical.endswith(DSL_SUFFIX) and not prog_logical.startswith(OWN_DSL_DIR):
            plan.problems.append(f"DSL outside own dir: {prog_logical}")
        if prog_logical.endswith(TERRAIN_SUFFIX) and prog_logical.startswith("battle/terrain/") \
                and not prog_logical.startswith(OWN_TERRAIN_DIR):
            plan.problems.append(f"terrain outside own dir: {prog_logical}")
    # 文件白名单：自有目录 + spec 点名的 UI 图 + item_icon 图集两件
    art = spec.get("art", {})
    named = {f["logical"] for f in art.get("files", [])} | set(ITEM_ATLAS_FILES)
    for logical in plan.files:
        if not logical.startswith((OWN_DSL_DIR, OWN_TERRAIN_DIR, OWN_FIELD_DIR, OWN_BOSS_DIR)) and logical not in named:
            plan.problems.append(f"file outside owned paths: {logical}")
    if (ITEM_ATLAS_FILES[0] in plan.files) != (ITEM_ATLAS_FILES[1] in plan.files):
        plan.problems.append("item_icon atlas png/atlas must ship in the same edge")
    # 共享表只许改点名的键
    node_path = (art.get("node_thumbnail") or {}).get("path")
    for path, _ in plan.edits.get(T_NODE, []):
        if path != node_path:
            plan.problems.append(f"{T_NODE}: unexpected key {path}")
    for path, _ in plan.edits.get(T_ITEM, []):
        if path[0] not in art.get("item_icons", {}):
            plan.problems.append(f"{T_ITEM}: unexpected key {path}")
    for path, _ in plan.edits.get(T_SHOP, []):
        if path[0] not in art.get("shop_icons", {}):
            plan.problems.append(f"{T_SHOP}: unexpected key {path}")
    # field_data 指向的 field 行必须存在（live 或本次新建）
    fields = set(live.table(T_FIELD)) | {p[0] for p, _ in plan.edits.get(T_FIELD, [])}
    for path, node in plan.edits.get(T_FD, []):
        fid = one_row(node)[0]
        if fid not in fields:
            plan.problems.append(f"field_data {path[0]} -> missing field row {fid}")


# ============================================================ 汇总

def build(spec: dict | None = None, live: Live | None = None, *, official_gbs: Callable[[], bytes] | None = None,
          with_envy_revert: bool = True) -> Plan:
    spec = spec or load_spec()
    live = live or Live()
    plan = Plan()
    # 词缀 DSL
    lib = affix_library(spec["affix_params"])
    used_bosses = {bs.alias for v in spec["_variants"] for wave in v.waves for bs in wave}
    signatures = {s for a in used_bosses for s in spec["bosses"][a].get("signature", [])}
    used = sorted({a for v in spec["_variants"] for a in v.affixes + v.entry_affixes} | signatures)
    for name in used:
        if name not in lib:
            raise BuildError(f"unknown affix {name}")
        tree = lib[name]
        bad = dsl_constructor_problems(tree)
        if bad:
            plan.problems.append(f"affix {name}: non-whitelisted constructors {bad}")
        plan.files[wf_dsl.dsl_logical(affix_program(name))] = encode_dsl(tree)
    # 地形
    terrains, trees = {}, {}
    for rnd, spec_t in spec["terrains"].items():
        tree, rep = build_terrain(live, spec_t)
        plan.files[spec_t["out"] + TERRAIN_SUFFIX] = encode_terrain(tree)
        terrains[rnd] = spec_t
        trees[rnd] = tree
        plan.report.setdefault("terrains", {})[rnd] = rep
    # 换色 / 新造型 boss 本体与试炼 routine（先生成文件，预算门禁要读到新贴图尺寸）
    plan_recolors(live, spec, plan)
    plan_bodies(live, spec, plan)
    plan_routines(live, spec, plan)
    # 变体 + 克隆
    for v in spec["_variants"]:
        plan_variant(live, spec, plan, v, terrains)
    plan_routes(live, spec, plan)
    plan_reward_display(spec, plan)
    plan_ui_files(live, spec, plan)
    plan_fields(live, spec, plan)
    plan_item_icons(live, spec, plan)
    plan_shop_icons(live, spec, plan)
    plan_node_thumbnail(live, spec, plan)
    if with_envy_revert:
        plan_envy_revert(live, official_gbs or official_table_loader(T_GBS), plan)
    # 门禁
    gate_codes(live, spec, plan)
    budgets = {}
    for v in spec["_variants"]:
        budgets[v.quest] = gate_variant(live, spec, plan, v, trees[v.round])
    plan.report["budget"] = budgets
    if "element_variants_in_apk" in plan.report:
        plan.report["element_variants_in_apk"] = sorted(plan.report["element_variants_in_apk"])
    plan.report["clones"] = len(plan.clones)
    plan.report["variants"] = {v.quest: v.name for v in spec["_variants"]}
    return plan


def apply_edits(live: Live, plan: Plan) -> dict[str, bytes]:
    """把表编辑落成新的整表字节（兄弟键原字节保留）。"""
    out = {}
    for table, edits in plan.edits.items():
        live.table(table)
        top = X.unpack(live.raw[table])
        for path, node in edits:
            head, rest = path[0], path[1:]
            if node is None and not rest:
                top.pop(head, None)
                continue
            if head in top:
                top[head] = replace_in_chunk(top[head], rest, node)
            else:
                wrapped = node
                for part in reversed(rest):
                    wrapped = {part: wrapped}
                top[head] = q.build_node(wrapped)
        new_raw = X.pack(top)
        # 回读自检：改动路径等于目标，未触及的顶层键原字节不变
        back = q.parse_node(new_raw)
        for path, node in edits:
            got = get_path(back, path)
            if node is None:
                if got is not None:
                    raise BuildError(f"{table} {path}: delete failed")
            elif got != node:
                raise BuildError(f"{table} {path}: write-back mismatch")
        old_top = X.unpack(live.raw[table])
        touched = {p[0] for p, _ in edits}
        for k, v in old_top.items():
            if k not in touched and X.unpack(new_raw).get(k) != v:
                raise BuildError(f"{table}: untouched key {k} changed")
        out[table] = new_raw
    return out


def stage(plan: Plan, live: Live, workdir: Path) -> dict:
    if plan.problems:
        raise BuildError("gates failed:\n  " + "\n  ".join(plan.problems))
    tables = apply_edits(live, plan)
    stage_dir = workdir / "stage" / "common"
    manifest = {"tables": {}, "files": {}}
    for logical, raw in tables.items():
        if raw == live.raw[logical]:
            continue
        dest = stage_dir / logical
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
        changed = sorted({p[0] for p, _ in plan.edits[logical]})
        manifest["tables"][logical] = {"changed": changed, "live_sha256": sha(live.raw[logical]),
                                       "staged_sha256": sha(raw)}
    for logical, raw in plan.files.items():
        cur = live.file(logical)
        if cur == raw:
            continue
        dest = stage_dir / logical
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
        manifest["files"][logical] = {"live_sha256": sha(cur) if cur is not None else None, "staged_sha256": sha(raw)}
    manifest["report"] = plan.report
    manifest["warnings"] = plan.warnings
    manifest["clones"] = plan.clones
    workdir.mkdir(parents=True, exist_ok=True)
    (workdir / "plan.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--spec", default=str(SPEC_PATH))
    ap.add_argument("--stage", metavar="WORKDIR", help="过门禁后暂存到该目录（不写 live）")
    ap.add_argument("--no-envy-revert", action="store_true")
    a = ap.parse_args(argv)
    spec = load_spec(Path(a.spec))
    live = Live()
    plan = build(spec, live, with_envy_revert=not a.no_envy_revert)
    print(json.dumps({"report": plan.report, "problems": plan.problems, "warnings": plan.warnings},
                     ensure_ascii=False, indent=1))
    if plan.problems:
        return 2
    if a.stage:
        m = stage(plan, live, Path(a.stage))
        print(json.dumps({"tables": {k: len(v["changed"]) for k, v in m["tables"].items()},
                          "files": len(m["files"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
