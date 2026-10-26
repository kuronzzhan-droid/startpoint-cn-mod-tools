#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""增强开关引擎:在「官方原版」与「已冻结的增强态」之间按地址逐格取值。

面板要解决的问题:自服里的个人增强(全角色平衡、解除主位限制、武器魂珠上修、
boss 血量上调、白虎重做……)现在是**一坨烤在 store 里的既成事实**,想关掉某一类
或全部切回官方,没有可逆的路径。

## 为什么不复用 wf_balance_suite --apply

`wf_balance_suite --apply` 第一件事是把 6 张表从 `.bak-wfmod-balance-20260709-*`
等锁定基准整文件覆盖回去。实测那份基准early于三自制角色与 15 把深渊武器:
ability live 375595 B vs 基准 311219 B、ability_soul live 42638 B vs 基准 38313 B
(差额里正是 wf_rogue_rewards 写的 8000101-8000115)。**任何按钮只要落到 --apply,
就等于把 20 天的角色/武器工作静默回滚。** 而且那份基准本身已带一轮增强
(ability 2652 行 vs 官方 2972 行),"全关"也回不到官方。

所以本引擎不重算、不 import、不 subprocess 平衡套件,只在三份字节之间取值:

  official  = wf_enhancement_policy.OfficialBaseline(官方 CDN 归档,唯一 ground truth)
  enhanced  = 增强基线快照(一次性冻结当前 store,见 snapshot_freeze 的守卫)
  live      = store 现字节(只读 + 受控写)

## 地址模型(CSV 表与嵌套表统一)

每张表 = key → 叶子(逗号分隔的一行)。叶子可能直接挂在 key 上(ability),也可能
嵌在下一层(leader_ability 的多行、character_status 的等级、rush_event_quest 的关卡)。
统一展平成 `(key, path, col)` 三级地址:

  - 双方叶子都在、列数相同 → 逐格比较,格级归属
  - 只在 enhanced 里 → 追加行,行级归属
  - 只在 official 里 → 被增强删掉的行,行级归属(关掉该开关时补回)
  - 列数不同/无法解析 → 整叶子二选一

## 两条护栏(不靠用户自律)

  R1 枚举·哨兵锁行:某叶子的差异触碰了 kind/target/trigger_limit/string_id/
     action_path/powerflip_override 等枚举或哨兵列时,该叶子整行由父开关决定
     —— 避免拼出「增强的 kind + 官方的强度」这类客户端 C7050/静默死行。
  R2 子桶跨越锁行:统一增强的三个子开关(强度/手感/门槛)只在「该叶子的全部差异格
     都落在同一子桶」时独立生效;平衡套件的补偿对(层强度写 strength、压缩后的层数写
     trigger_limit)必然跨桶,会被自动升格为整行,并在报告里如实计数。

## 自检等式(不成立即拒写)

  E1 全部关 → 官方地址上逐格等于 official
  E2 全部开 → 官方地址上逐格等于 enhanced
两条都在 plan 阶段跑,任一不成立说明归属表有洞(有地址没人认领或被重复认领),拒绝写盘。

CLI:
  python mod-tools/wf_enhancement_switch.py status
  python mod-tools/wf_enhancement_switch.py snapshot --tag base
  python mod-tools/wf_enhancement_switch.py plan  --off char.main_position
  python mod-tools/wf_enhancement_switch.py apply --preset official --scope character
  python mod-tools/wf_enhancement_switch.py rollback --preimage <id>
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence

MOD_DIR = Path(__file__).resolve().parent
ROOT = MOD_DIR.parent
sys.path.insert(0, str(MOD_DIR))

import wf_enhancement_policy as pol  # noqa: E402
import wf_mod_tool as core  # noqa: E402
import wf_quest_lib as quest  # noqa: E402

WORK_DIR = MOD_DIR / "work" / "enhancement-switch"
SNAP_DIR = WORK_DIR / "snapshots"
PREIMAGE_DIR = WORK_DIR / "preimages"
STATE_PATH = WORK_DIR / "state.json"
LAYOUTS_PATH = MOD_DIR / "ability_enum_map.json"

ABILITY = "master/ability/ability.orderedmap"
LEADER = "master/ability/leader_ability.orderedmap"
SOUL = "master/ability/ability_soul.orderedmap"
WAB = "master/equipment_enhancement/equipment_enhancement_ability.orderedmap"
CHARACTER = "master/character/character.orderedmap"
CHAR_STATUS = "master/character/character_status.orderedmap"
ACTION_SKILL = "master/skill/action_skill.orderedmap"
BOSS_LEVEL = "master/battle/boss/boss_level.orderedmap"
CHAR_IMAGE = "master/generated/character_image.orderedmap"
TRIMMED_IMAGE = "master/generated/trimmed_image.orderedmap"
EQUIP_STATUS = "master/item/equipment_status.orderedmap"
EVENT_SHOP = "master/shop/event_item_shop.orderedmap"
RUSH_QUEST = "master/quest/event/rush_event_quest.orderedmap"
RUSH_CORRECTION = "master/quest/event/rush_event_battle_quest_correction.orderedmap"
CHALLENGE_QUEST = "master/quest/event/challenge_dungeon_event_quest.orderedmap"
WHITE_TIGER_DSL = pol.DROP_LOGICALS[0]

# 被换皮的官方资产:整文件二选一(引擎默认的 drop 语义对自服等于什么都不做)
OFFICIAL_ART_FILES = (
    "character/alice/ui/skill_cutin_0.png",
    "character/alice/ui/skill_cutin_0.atf.deflate",
    "character/light_chapter12/ui/full_shot_1440_1920_0.png",
    "character/pirates_girl/ui/full_shot_1440_1920_0.png",
)

MANAGED_TABLES = (
    ABILITY, LEADER, SOUL, WAB, CHARACTER, CHAR_STATUS, ACTION_SKILL,
    BOSS_LEVEL, CHAR_IMAGE, TRIMMED_IMAGE, EQUIP_STATUS, EVENT_SHOP,
    RUSH_QUEST, RUSH_CORRECTION, CHALLENGE_QUEST,
)
MANAGED_ASSETS = (WHITE_TIGER_DSL, *OFFICIAL_ART_FILES)

# 主线剧情宝珠/证章:live 少行(负面副作用行被删),行对齐会错位,只能整键二选一
MAINLINE_ORBS = frozenset({
    "100011", "100012", "200001", "200002", "200003",
    "200004", "200005", "200006", "5090054",
})
WHITE_TIGER_ABILITY_KEYS = frozenset({"81", "85", "86"})
WHITE_TIGER_LEADER_KEY = "3"
WHITE_TIGER_CHARACTER_KEY = "10"
WHITE_TIGER_SKILL_KEY = "white_tiger"


class SwitchError(RuntimeError):
    """前置条件不满足(快照缺失/守卫未过/自检不成立)。"""


class ForeignDriftError(SwitchError):
    """store 里有快照之后的第三方改动,未经确认不覆盖。"""


# ------------------------------------------------------------------ 列布局

@dataclass(frozen=True)
class TableLayout:
    logical: str
    ncols: int
    blocks: dict[str, int]
    field_index: dict[str, dict[str, int]]

    def col(self, block: str, field_name: str) -> int:
        base = "precondition" if block.startswith("precondition") else block
        return self.blocks[block] + self.field_index[base][field_name]

    def field_at(self, col: int) -> tuple[str, str] | None:
        """列号 → (块名, 字段名);头部列返回 None。"""
        best: tuple[str, int] | None = None
        for block, offset in self.blocks.items():
            if offset <= col and (best is None or offset > best[1]):
                best = (block, offset)
        if best is None:
            return None
        block, offset = best
        base = "precondition" if block.startswith("precondition") else block
        fields = self.field_index[base]
        for name, index in fields.items():
            if offset + index == col:
                return block, name
        return None


LAYOUT_TABLES = {
    ABILITY: "ability", LEADER: "leader_ability",
    SOUL: "ability_soul", WAB: "equipment_enhancement_ability",
}
# 模块加载期断言:布局漂了就别启动(off-by-one 会把整片列错位)
EXPECTED_NCOLS = {ABILITY: 126, LEADER: 124, SOUL: 123, WAB: 126}

# 枚举/哨兵字段:叶子里只要有一格属于这些字段发生变化,整叶子锁定为父开关二选一
ENUM_SENTINEL_FIELDS = frozenset({
    "kind", "target", "target.character_groups", "target.multiball_group_id",
    "trigger_puller", "trigger_puller.character_groups", "trigger_limit",
    "character_groups", "string_id", "action_path", "element",
    "unique_condition_id", "multiball_group_id", "by_each_trigger_puller",
    "multiply_trigger", "mt.trigger_limit", "mt.trigger_puller",
    "mt.tp.character_groups", "cancelable", "even_if_owner_dead",
    "powerflip_override.id", "powerflip_override.levels",
    "powerflip_override.description_id",
})
# 统一增强的三个子桶
SUB_POWER = frozenset({
    "strength.power1", "strength.first_max", "strength2.power1",
    "strength2.first_max", "strength3.power1", "strength3.first_max",
    "number.power1", "number.first_max", "max_accumulation",
    "frame.power1", "frame.first_max", "initial_multiply",
    "mt.additional_multiply", "power.power1", "power.first_max", "time",
})
SUB_FEEL = frozenset({
    "cooltime", "flip_limit", "power_flip_limit", "end_power_flip_limit",
    "end_power_flip_accepted_levels", "instant_delay", "limit",
})
SUB_GATE = frozenset({
    "threshold.power1", "threshold.first_max", "threshold2.power1",
    "threshold2.first_max", "start_threshold.power1", "start_threshold.first_max",
    "mt.threshold.power1", "mt.threshold.first_max",
})
SUB_BUCKETS = {"power": SUB_POWER, "feel": SUB_FEEL, "gate": SUB_GATE}

_LAYOUTS: dict[str, TableLayout] | None = None


def load_layouts(path: Path = LAYOUTS_PATH) -> dict[str, TableLayout]:
    global _LAYOUTS
    if _LAYOUTS is not None:
        return _LAYOUTS
    payload = json.loads(path.read_text(encoding="utf-8"))
    block_fields = {
        name: {field_name: index for index, field_name, *_rest in rows}
        for name, rows in payload["block_fields"].items()
    }
    layouts: dict[str, TableLayout] = {}
    for logical, name in LAYOUT_TABLES.items():
        spec = payload["layouts"][name]
        layout = TableLayout(logical, int(spec["ncols"]), dict(spec["blocks"]), block_fields)
        expected = EXPECTED_NCOLS[logical]
        if layout.ncols != expected:
            raise SwitchError(
                f"{name} 列布局变了(ncols={layout.ncols} 期望 {expected}):"
                "ability_enum_map.json 与实际表不符,拒绝启动")
        layouts[logical] = layout
    _LAYOUTS = layouts
    return layouts


def layout_of(logical: str) -> TableLayout | None:
    return load_layouts().get(logical)


# ------------------------------------------------------------------ 地址模型

Path_ = tuple[str, ...]
LeafMap = dict[Path_, str]


def leaves(node) -> LeafMap:
    """节点 → {嵌套路径: 叶子字符串}。CSV 表与嵌套表统一成同一张地址表。"""
    out: LeafMap = {}

    def walk(value, path: Path_) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                walk(child, (*path, key))
        else:
            out[path] = value

    walk(node, ())
    return out


def put_leaf(node: dict, key: str, path: Path_, value) -> None:
    """把叶子写回 key 下的嵌套位置(按需建中间层,保持插入序)。"""
    if not path:
        node[key] = value
        return
    cursor = node.setdefault(key, {})
    if not isinstance(cursor, dict):
        cursor = node[key] = {}
    for part in path[:-1]:
        nxt = cursor.get(part)
        if not isinstance(nxt, dict):
            nxt = cursor[part] = {}
        cursor = nxt
    cursor[path[-1]] = value


def drop_leaf(node: dict, key: str, path: Path_) -> None:
    if not path:
        node.pop(key, None)
        return
    cursor = node.get(key)
    for part in path[:-1]:
        if not isinstance(cursor, dict):
            return
        cursor = cursor.get(part)
    if isinstance(cursor, dict):
        cursor.pop(path[-1], None)


# ------------------------------------------------------------------ 开关定义

@dataclass(frozen=True)
class ToggleSpec:
    id: str
    label: str
    scope: str                       # character | weapon | enemy | other
    tables: tuple[str, ...]
    priority: int
    default: bool
    off_equals_official: bool = True
    subs: tuple[str, ...] = ()
    warn: str = ""
    note: str = ""
    gui_readonly: bool = False       # 需要服务端/存档联动,GUI 只展示不切换


TOGGLES: tuple[ToggleSpec, ...] = (
    ToggleSpec("char.white_tiger", "角色 · 白虎专项重做(4★→5★)", "character",
               (ABILITY, LEADER, CHARACTER, ACTION_SKILL, WHITE_TIGER_DSL), 90, True,
               off_equals_official=False, gui_readonly=True,
               warn="关掉要同时改服务端 assets/character.json 与 cdndata 并钳存档,"
                    "只在 CLI 加 --allow-white-tiger 时可切",
               note="客户端 4★ 配服务端 5★ 会撞 characterExpCaps 越界"),
    ToggleSpec("weapon.orb", "武器 · 主线宝珠/证章 ×4", "weapon", (SOUL,), 90, True,
               note="live 少行(负面副作用行被删),只能整键二选一"),
    ToggleSpec("char.leader_pf", "角色 · 队长专属强化弹射", "character", (LEADER,), 80, True,
               off_equals_official=False,
               note="队长位=队伍 0 号位,不是主位三格;仅影响官方角色白虎"),
    ToggleSpec("char.main_position", "角色 · 解除主位限制(协力位也吃词条)", "character",
               (ABILITY, LEADER), 70, True,
               note="只认官方值 false 的 unisonable 与官方值 202 的前置 kind"),
    ToggleSpec("char.extra_rows", "角色 · 专属追加词条与趣味队长技", "character",
               (ABILITY, LEADER), 60, True),
    ToggleSpec("weapon.soul_rows", "武器 · 魂珠追加词条行", "weapon", (SOUL,), 60, True),
    ToggleSpec("char.growth", "角色 · 三四星成长曲线拉平", "character", (CHAR_STATUS,), 50, True),
    ToggleSpec("enemy.boss_hp", "敌人 · Boss 血量上调", "enemy", (BOSS_LEVEL,), 50, True),
    ToggleSpec("enemy.dummy_hp", "敌人 · 练习木桩血量上调", "enemy", (BOSS_LEVEL,), 50, True),
    ToggleSpec("weapon.wab", "武器 · 官方强化槽词条上修(29 把)", "weapon", (WAB,), 50, False,
               warn="store 是增强态、CDN 链上已是官方值(1.4.106 还原过);"
                    "开启并发布会把它重新推上线"),
    ToggleSpec("other.official_art", "美术 · 官方立绘/切入图换皮", "other",
               (CHAR_IMAGE, TRIMMED_IMAGE, *OFFICIAL_ART_FILES), 50, True,
               note="skill_cutin 真机读 ATF 不读 PNG,两文件成对处理"),
    ToggleSpec("other.rush_700007", "关卡 · 官方无尽战斗 700007 改动", "other",
               (RUSH_QUEST, RUSH_CORRECTION), 50, True),
    ToggleSpec("other.treasure_2001", "关卡 · 宝物域【暗】2001 场地改造", "other",
               (CHALLENGE_QUEST,), 50, True,
               warn="深渊武器商品文案宣传了这个玩法,关掉会让文案落空;不进任何一键预设"),
    ToggleSpec("other.shop_700099", "商店 · 官方商品 700099 缺失(生成器撞号副产物)", "other",
               (EVENT_SHOP,), 50, True, gui_readonly=True,
               warn="补回客户端行还要同步服务端 event_item_shop.json 与 id_map,"
                    "否则商品可见但购买必失败;只在 CLI 加 --allow-shop 时可切",
               note="默认保持现状(缺失)。建议择机关掉本项把官方商品补回来——"
                    "这不是有意的增强,是 wf_rogue_shop 的 EVENT_ID 与官方键撞号的副产物"),
    ToggleSpec("other.equip_debug", "装备 · 官方装备 100012 调试数值", "other",
               (EQUIP_STATUS,), 50, False,
               note="99999/99999,像调试残留,从未发布过"),
    ToggleSpec("weapon.soul", "武器 · 官方魂珠词条增强", "weapon", (SOUL,), 10, True),
    ToggleSpec("char.tuning", "角色 · 统一增强(数值/手感/门槛)", "character",
               (ABILITY, LEADER), 10, True, subs=("power", "feel", "gate")),
)
TOGGLE_BY_ID = {spec.id: spec for spec in TOGGLES}
SCOPES = ("character", "weapon", "enemy", "other")
# 谨慎项:永不进任何一键预设,必须单独勾
PRESET_EXCLUDED = frozenset({"other.treasure_2001"})
# 需要服务端/存档联动的项:预设不碰,显式切换还要额外的 CLI 开关
GUARDED_TOGGLES = {
    "char.white_tiger": "--allow-white-tiger",
    "other.shop_700099": "--allow-shop",
}


def observed_vector(states: Mapping[str, ToggleState]) -> dict[str, bool]:
    """把 store 现状翻译成一个复选框向量:没被点到的开关就该保持原样。

    没有这一步,「只关主位限制」会把其余开关一并拉回 default,静默改掉用户没提的东西。
    """
    vector: dict[str, bool] = {}
    for spec in TOGGLES:
        state = states.get(spec.id)
        if state is None or state.state == "n/a":
            vector[spec.id] = spec.default
        elif state.state == "official":
            vector[spec.id] = False
        elif state.state == "enhanced":
            vector[spec.id] = True
        else:  # mixed / foreign:按多数归位,预览里会显示归位改动
            vector[spec.id] = state.enhanced >= state.official
    return vector


def preset_vector(name: str, scope: str | None = None,
                  current: Mapping[str, bool] | None = None) -> dict[str, bool]:
    """预设只是一个复选框向量,不是第二条写盘路径。"""
    base = dict(current or {spec.id: spec.default for spec in TOGGLES})
    for spec in TOGGLES:
        if scope and spec.scope != scope:
            continue
        if spec.id in PRESET_EXCLUDED or spec.id in GUARDED_TOGGLES:
            continue
        if name == "on":
            base[spec.id] = True
        elif name == "official":
            base[spec.id] = False
        elif name == "default":
            base[spec.id] = spec.default
        else:
            raise SwitchError(f"未知预设: {name}")
    return base


# ------------------------------------------------------------------ 上下文

@dataclass
class Context:
    repo: Path
    store: Path
    cdn: Path
    profile_id: str
    baseline: pol.OfficialBaseline

    def table_path(self, logical: str) -> Path:
        return self.store / quest.hashed_rel(logical)


def resolve_context(*, store: str | Path | None = None, cdn: str | Path | None = None,
                    repo: str | Path | None = None) -> Context:
    repo_root = Path(repo).resolve() if repo else ROOT
    if store:
        store_root = Path(store).resolve()
        profile_id = "explicit"
    else:
        profile = core.resolve_profile()
        if profile is None or not getattr(profile, "store", None):
            raise SwitchError(
                "没找到可用的 store(mod-tools/profiles.json 缺失或 active 档不完整)")
        store_root = Path(profile.store)
        if not store_root.is_absolute():
            store_root = repo_root / store_root
        profile_id = getattr(profile, "id", None) or getattr(profile, "key", "cn")
    if not store_root.is_dir():
        raise SwitchError(f"store 不存在: {store_root}")
    cdn_root = Path(cdn).resolve() if cdn else pol._resolve_cdn(None)
    return Context(repo_root, store_root, cdn_root, str(profile_id),
                   pol.OfficialBaseline(cdn_root))


# ------------------------------------------------------------------ 快照

@dataclass(frozen=True)
class Snapshot:
    name: str
    created: str
    store: str
    entries: dict[str, dict]
    dir: Path

    def get(self, logical: str) -> bytes | None:
        entry = self.entries.get(logical)
        if entry is None:
            return None
        blob = self.dir / "blobs" / entry["sha256"][:2] / entry["sha256"][2:]
        return blob.read_bytes()

    def as_dict(self) -> dict:
        return {"name": self.name, "created": self.created, "store": self.store,
                "entries": len(self.entries)}


def _read_live(ctx: Context, logical: str) -> bytes | None:
    path = ctx.table_path(logical)
    return path.read_bytes() if path.is_file() else None


def snapshot_freeze(ctx: Context, *, tag: str, force: bool = False,
                    dry_run: bool = False) -> Snapshot:
    """一次性冻结当前 store 为「增强侧」。

    守卫(force 可跳过,但会在 manifest 里留痕):
      ① 自制内容还在(EXPECTED_CONTENT_ROWS 逐条断言)——证明这不是一份被
         wf_balance_suite --apply 洗过的 store;
      ② 增强还开着——至少一半受管开关处于 enhanced 态。在部分切回官方之后冻结,
         ON 侧会被永久钉成官方值,此后"启用增强"写的却是官方值,静默且不可恢复。
    """
    if not tag.replace("-", "").replace("_", "").isalnum():
        raise SwitchError(f"tag 只能是字母数字/-/_: {tag!r}")
    problems: list[str] = []
    notes: list[str] = []
    live_nodes: dict[str, object] = {}
    for logical in MANAGED_TABLES:
        raw = _read_live(ctx, logical)
        if raw is None:
            notes.append(f"store 缺表 {logical}(该表不参与开关)")
            continue
        live_nodes[logical] = quest.parse_node(raw)
    for logical, keys in pol.EXPECTED_CONTENT_ROWS.items():
        node = live_nodes.get(logical)
        if node is None:
            continue
        missing = [key for key in keys if key not in node]
        if missing:
            problems.append(f"{logical}: 自制内容行缺失 {missing[:4]} —— "
                            "这份 store 可能被平衡套件洗过,拒绝当增强基线")
    if problems and not force:
        raise SwitchError("冻结守卫未通过:\n  " + "\n  ".join(problems))

    name = f"{tag}-{time.strftime('%Y%m%d-%H%M%S')}"
    snap_dir = SNAP_DIR / name
    entries: dict[str, dict] = {}
    payloads: dict[str, bytes] = {}
    for logical in (*MANAGED_TABLES, *MANAGED_ASSETS):
        raw = _read_live(ctx, logical)
        if raw is None:
            continue
        digest = pol.sha256(raw)
        entries[logical] = {"rel": quest.hashed_rel(logical), "size": len(raw),
                            "sha256": digest}
        payloads[logical] = raw
    if dry_run:
        return Snapshot(name, "(dry-run)", str(ctx.store), entries, snap_dir)

    (snap_dir / "blobs").mkdir(parents=True, exist_ok=True)
    for logical, raw in payloads.items():
        digest = entries[logical]["sha256"]
        blob = snap_dir / "blobs" / digest[:2] / digest[2:]
        blob.parent.mkdir(parents=True, exist_ok=True)
        if not blob.is_file():
            blob.write_bytes(raw)
    created = time.strftime("%Y-%m-%d %H:%M:%S")
    (snap_dir / "manifest.json").write_text(json.dumps({
        "name": name, "created": created, "store": str(ctx.store),
        "profile": ctx.profile_id, "guardProblems": problems, "notes": notes,
        "forced": bool(force and problems), "entries": entries,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (WORK_DIR / "current-snapshot").write_text(name, encoding="utf-8")
    return Snapshot(name, created, str(ctx.store), entries, snap_dir)


def load_snapshot(name: str | None = None) -> Snapshot:
    if name is None:
        pointer = WORK_DIR / "current-snapshot"
        if not pointer.is_file():
            raise SwitchError(
                "还没有增强基线快照。先跑 "
                "`python mod-tools/wf_enhancement_switch.py snapshot --tag base` "
                "把当前 store 冻结成「增强侧」")
        name = pointer.read_text(encoding="utf-8").strip()
    snap_dir = SNAP_DIR / name
    manifest_path = snap_dir / "manifest.json"
    if not manifest_path.is_file():
        raise SwitchError(f"快照不存在: {name}")
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    return Snapshot(payload["name"], payload["created"], payload["store"],
                    payload["entries"], snap_dir)


def list_snapshots() -> list[dict]:
    if not SNAP_DIR.is_dir():
        return []
    out = []
    for path in sorted(SNAP_DIR.iterdir()):
        manifest = path / "manifest.json"
        if manifest.is_file():
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            out.append({"name": payload["name"], "created": payload["created"],
                        "entries": len(payload.get("entries", {})),
                        "forced": payload.get("forced", False)})
    return out


# ------------------------------------------------------------------ 归属

def split_lines(leaf: str) -> list[str]:
    """一个叶子里可能拼着多行(换行分隔),每行才是 126 列的 CSV。"""
    return leaf.split("\n")


def join_lines(lines: Sequence[str]) -> str:
    return "\n".join(lines)


@dataclass
class Address:
    """一处可切换的差异。

    kind:
      cell        —— (key, path, line, col) 单格
      line        —— 整行二选一(列数对不上/触碰哨兵)
      appended    —— 增强侧多出来的行
      key         —— 整键二选一(行数变少/无法对齐)
      deleted_key —— 官方有、增强侧整个删掉的键
      asset       —— 非表文件整文件
    """
    logical: str
    key: str
    path: Path_
    line: int | None
    col: int | None
    kind: str
    official: str | None
    enhanced: str | None
    owner: str
    sub: str | None = None


def _leaf_owner(logical: str, key: str) -> str | None:
    """key 级归属(优先级最高的几个桶)。"""
    if logical == SOUL and key in MAINLINE_ORBS:
        return "weapon.orb"
    if logical == ABILITY and key in WHITE_TIGER_ABILITY_KEYS:
        return "char.white_tiger"
    if logical == CHARACTER and key == WHITE_TIGER_CHARACTER_KEY:
        return "char.white_tiger"
    if logical == ACTION_SKILL and key == WHITE_TIGER_SKILL_KEY:
        return "char.white_tiger"
    if logical == CHAR_STATUS:
        return "char.growth"
    if logical == BOSS_LEVEL:
        return "enemy.dummy_hp" if key.startswith("waraboss") else "enemy.boss_hp"
    if logical == WAB:
        return "weapon.wab"
    if logical in (CHAR_IMAGE, TRIMMED_IMAGE):
        return "other.official_art"
    if logical in (RUSH_QUEST, RUSH_CORRECTION):
        return "other.rush_700007"
    if logical == CHALLENGE_QUEST:
        return "other.treasure_2001"
    if logical == EVENT_SHOP:
        return "other.shop_700099"
    if logical == EQUIP_STATUS:
        return "other.equip_debug"
    return None


def _rest_owner(logical: str) -> str:
    if logical == SOUL:
        return "weapon.soul"
    return "char.tuning"


def _pf_columns(layout: TableLayout | None) -> frozenset[int]:
    if layout is None:
        return frozenset()
    cols = set()
    for block in ("instant_content", "during_content"):
        try:
            cols.add(layout.col(block, "powerflip_override.id"))
        except KeyError:
            continue
    return frozenset(cols)


def _main_position_cols(layout: TableLayout | None) -> frozenset[int]:
    if layout is None:
        return frozenset()
    cols = set()
    for block in ("precondition1", "precondition2", "precondition3"):
        cols.add(layout.col(block, "kind"))
    return frozenset(cols)


def _sub_of(layout: TableLayout | None, col: int) -> str | None:
    if layout is None:
        return None
    hit = layout.field_at(col)
    if hit is None:
        return None
    _block, name = hit
    for bucket, fields in SUB_BUCKETS.items():
        if name in fields:
            return bucket
    return None


def _is_sentinel(layout: TableLayout | None, col: int) -> bool:
    if layout is None:
        return False
    hit = layout.field_at(col)
    return hit is not None and hit[1] in ENUM_SENTINEL_FIELDS


@dataclass
class TableDiff:
    logical: str
    addresses: list[Address] = field(default_factory=list)
    escalated: dict[str, int] = field(default_factory=lambda: {"R1": 0, "R2": 0})
    misaligned_keys: list[str] = field(default_factory=list)
    content_keys: int = 0

    def by_owner(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for address in self.addresses:
            counts[address.owner] = counts.get(address.owner, 0) + 1
        return counts


def diff_table(logical: str, official_raw: bytes, enhanced_raw: bytes,
               policy: pol.Policy | None = None) -> TableDiff:
    """官方 vs 增强的全部可切换地址,并逐个定好归属。

    官方基准里存在的 key 一律按官方处理——**不走内容识别**。官方 key 天然就是官方的,
    而内容识别的模式会误伤撞号的官方行(实测:商店表官方商品 700099 与模式 id 撞号)。
    """
    diff = TableDiff(logical)
    official = quest.parse_node(official_raw)
    enhanced = quest.parse_node(enhanced_raw)
    if not isinstance(official, dict) or not isinstance(enhanced, dict):
        raise SwitchError(f"{logical}: 不是顶层 orderedmap")
    layout = layout_of(logical)
    rest = _rest_owner(logical)
    pf_cols = _pf_columns(layout) if logical == LEADER else frozenset()
    mp_kind_cols = _main_position_cols(layout) if logical in (ABILITY, LEADER) else frozenset()
    ncols = layout.ncols if layout else None

    for key, official_row in official.items():
        enhanced_row = enhanced.get(key)
        key_owner = _leaf_owner(logical, key)
        if enhanced_row is None:
            diff.addresses.append(Address(logical, key, (), None, None, "deleted_key",
                                          None, None, key_owner or rest))
            continue
        if official_row == enhanced_row:
            continue
        official_leaves = leaves(official_row)
        enhanced_leaves = leaves(enhanced_row)
        # 叶子路径集合必须一致,否则整键二选一(嵌套结构变了,猜不得)
        if set(official_leaves) != set(enhanced_leaves) or key_owner is not None:
            if key_owner is None and key not in diff.misaligned_keys:
                diff.misaligned_keys.append(key)
            diff.addresses.append(Address(logical, key, (), None, None, "key",
                                          None, None, key_owner or rest))
            continue

        for path, official_leaf in official_leaves.items():
            enhanced_leaf = enhanced_leaves[path]
            if official_leaf == enhanced_leaf:
                continue
            official_lines = split_lines(official_leaf)
            enhanced_lines = split_lines(enhanced_leaf)
            if len(enhanced_lines) < len(official_lines):
                # 增强侧删了行:行号对不上,只能整键二选一(实测主线宝珠的负面行被删)
                if key not in diff.misaligned_keys:
                    diff.misaligned_keys.append(key)
                diff.addresses.append(Address(logical, key, (), None, None, "key",
                                              None, None, key_owner or rest))
                break

            for index in range(len(official_lines), len(enhanced_lines)):
                line = enhanced_lines[index]
                owner = None
                if logical == LEADER and pf_cols:
                    cells = line.split(",")
                    if any(col < len(cells) and cells[col] for col in pf_cols):
                        owner = "char.leader_pf"
                if owner is None:
                    owner = "weapon.soul_rows" if logical == SOUL else "char.extra_rows"
                diff.addresses.append(Address(logical, key, path, index, None,
                                              "appended", None, line, owner))

            for index in range(len(official_lines)):
                official_line = official_lines[index]
                enhanced_line = enhanced_lines[index]
                if official_line == enhanced_line:
                    continue
                official_cells = official_line.split(",")
                enhanced_cells = enhanced_line.split(",")
                if len(official_cells) != len(enhanced_cells) or \
                        (ncols is not None and len(official_cells) != ncols):
                    diff.addresses.append(Address(
                        logical, key, path, index, None, "line",
                        official_line, enhanced_line, rest))
                    if key not in diff.misaligned_keys:
                        diff.misaligned_keys.append(key)
                    continue

                changed = [col for col, (a, b) in
                           enumerate(zip(official_cells, enhanced_cells)) if a != b]
                cell_owners: list[tuple[int, str, str | None]] = []
                for col in changed:
                    owner = rest
                    if col in mp_kind_cols and official_cells[col] == "202":
                        owner = "char.main_position"
                    elif logical == ABILITY and col == 1 and official_cells[col] == "false":
                        owner = "char.main_position"
                    elif col in pf_cols:
                        owner = "char.leader_pf"
                    cell_owners.append((col, owner, _sub_of(layout, col)))

                # R1 只看兜底桶的格子:被点名认领的格(解除主位限制的 202/unisonable、
                # 队长 PF 覆盖)本来就是"故意改这个枚举",且带取值守卫,不该被锁掉。
                locked = any(_is_sentinel(layout, col)
                             for col, owner, _s in cell_owners if owner == rest)
                rest_subs = {sub for _c, owner, sub in cell_owners if owner == rest}
                cross_bucket = len(rest_subs) > 1
                if locked:
                    diff.escalated["R1"] += 1
                elif cross_bucket:
                    diff.escalated["R2"] += 1
                for col, owner, sub in cell_owners:
                    if owner == rest and (locked or cross_bucket):
                        sub = None
                    diff.addresses.append(Address(
                        logical, key, path, index, col, "cell",
                        official_cells[col], enhanced_cells[col], owner, sub))
    return diff


def diff_asset(logical: str, official_raw: bytes | None, enhanced_raw: bytes) -> TableDiff:
    diff = TableDiff(logical)
    if official_raw is None or official_raw == enhanced_raw:
        return diff
    diff.addresses.append(Address(logical, "", (), None, "asset", None, None,
                                  "other.official_art"))
    return diff


# ------------------------------------------------------------------ 合成

@dataclass
class ComposeDetail:
    logical: str
    changed: bool = False
    to_official: int = 0
    to_enhanced: int = 0
    rows_added: int = 0
    rows_dropped: int = 0
    rows_restored: int = 0
    foreign: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"logical": self.logical, "changed": self.changed,
                "toOfficial": self.to_official, "toEnhanced": self.to_enhanced,
                "rowsAdded": self.rows_added, "rowsDropped": self.rows_dropped,
                "rowsRestored": self.rows_restored, "foreign": self.foreign[:20],
                "foreignCount": len(self.foreign)}


def _wanted(desired: Mapping[str, bool], sub: Mapping[str, bool], address: Address) -> bool:
    on = bool(desired.get(address.owner, TOGGLE_BY_ID[address.owner].default
                          if address.owner in TOGGLE_BY_ID else True))
    if on and address.sub:
        return bool(sub.get(address.sub, True))
    return on


def compose_table(*, official_raw: bytes, enhanced_raw: bytes, live_raw: bytes,
                  diff: TableDiff, desired: Mapping[str, bool],
                  sub: Mapping[str, bool], allow_foreign: bool = False
                  ) -> tuple[bytes, ComposeDetail]:
    """以 live 为底,把 diff 里的每个地址按 desired 拨到官方值或增强值。"""
    detail = ComposeDetail(diff.logical)
    official = quest.parse_node(official_raw)
    enhanced = quest.parse_node(enhanced_raw)
    live = quest.parse_node(live_raw)
    out = copy.deepcopy(live)

    # (key, path) → 行表。先按行装配,最后再拼回叶子,避免行号在增删中漂移。
    work: dict[tuple[str, Path_], list[str | None]] = {}
    dropped_lines: set[tuple[str, Path_, int]] = set()

    def lines_of(node, key: str, path: Path_) -> list[str] | None:
        row = node.get(key)
        if row is None:
            return None
        leaf = leaves(row).get(path)
        return None if leaf is None else split_lines(leaf)

    def ensure(key: str, path: Path_) -> list[str | None] | None:
        slot = work.get((key, path))
        if slot is None:
            base = lines_of(live, key, path)
            if base is None:
                return None
            slot = work[(key, path)] = list(base)
        return slot

    for address in diff.addresses:
        want_enhanced = _wanted(desired, sub, address)
        if address.kind == "cell":
            slot = ensure(address.key, address.path)
            if slot is None or address.line >= len(slot) or slot[address.line] is None:
                continue
            cells = slot[address.line].split(",")
            if address.col >= len(cells):
                continue
            current = cells[address.col]
            if current not in (address.official, address.enhanced):
                detail.foreign.append(
                    f"{address.key}{''.join('/'+p for p in address.path)}"
                    f"#L{address.line}c{address.col} 官方={address.official}"
                    f" 增强={address.enhanced} 现值={current}")
                if not allow_foreign:
                    continue
            target = address.enhanced if want_enhanced else address.official
            if target != current:
                cells[address.col] = target
                slot[address.line] = ",".join(cells)
                detail.to_enhanced += 1 if want_enhanced else 0
                detail.to_official += 0 if want_enhanced else 1
        elif address.kind == "line":
            slot = ensure(address.key, address.path)
            if slot is None or address.line >= len(slot):
                continue
            current = slot[address.line]
            if current not in (address.official, address.enhanced):
                detail.foreign.append(
                    f"{address.key}#L{address.line} 整行第三方改动")
                if not allow_foreign:
                    continue
            target = address.enhanced if want_enhanced else address.official
            if target != current:
                slot[address.line] = target
                detail.to_enhanced += 1 if want_enhanced else 0
                detail.to_official += 0 if want_enhanced else 1
        elif address.kind == "appended":
            slot = ensure(address.key, address.path)
            if slot is None:
                continue
            present = address.line < len(slot) and slot[address.line] is not None
            if want_enhanced and not present:
                while len(slot) <= address.line:
                    slot.append(None)
                slot[address.line] = address.enhanced
                detail.rows_added += 1
            elif not want_enhanced and present:
                slot[address.line] = None
                dropped_lines.add((address.key, address.path, address.line))
                detail.rows_dropped += 1
        elif address.kind == "key":
            source = enhanced if want_enhanced else official
            value = source.get(address.key)
            current = out.get(address.key)
            if current is not None and current not in (
                    official.get(address.key), enhanced.get(address.key)):
                detail.foreign.append(f"{address.key} 整键第三方改动")
                if not allow_foreign:
                    continue
            if value is not None and current != value:
                out[address.key] = copy.deepcopy(value)
                detail.to_enhanced += 1 if want_enhanced else 0
                detail.to_official += 0 if want_enhanced else 1
        elif address.kind == "deleted_key":
            present = address.key in out
            if want_enhanced and present:
                out.pop(address.key, None)
                detail.rows_dropped += 1
            elif not want_enhanced and not present:
                value = official.get(address.key)
                if value is not None:
                    out[address.key] = copy.deepcopy(value)
                    detail.rows_restored += 1

    for (key, path), slot in work.items():
        kept = [line for line in slot if line is not None]
        if not kept:
            continue
        put_leaf(out, key, path, join_lines(kept))

    detail.changed = out != live
    if not detail.changed:
        return live_raw, detail
    rebuilt = quest.build_node(out)
    if quest.parse_node(rebuilt) != out:
        raise SwitchError(f"{diff.logical}: 合成后回读不一致,拒绝产出")
    return rebuilt, detail


# ------------------------------------------------------------------ 观测

@dataclass
class ToggleState:
    id: str
    state: str                 # official | enhanced | mixed | foreign | n/a
    official: int = 0
    enhanced: int = 0
    foreign: int = 0

    def as_dict(self) -> dict:
        return {"id": self.id, "state": self.state, "counts": {
            "official": self.official, "enhanced": self.enhanced,
            "foreign": self.foreign}}


def observe(diffs: Mapping[str, TableDiff], lives: Mapping[str, bytes],
            officials: Mapping[str, dict] | None = None,
            enhanceds: Mapping[str, dict] | None = None) -> dict[str, ToggleState]:
    """store 现字节逐地址反推每个开关的当前态。真相源永远是字节,不是 state.json。"""
    states = {spec.id: ToggleState(spec.id, "n/a") for spec in TOGGLES}
    parsed = {logical: quest.parse_node(raw) for logical, raw in lives.items()
              if raw is not None}
    for logical, diff in diffs.items():
        node = parsed.get(logical)
        if node is None:
            continue
        leaf_cache: dict[str, LeafMap] = {}
        official_rows = officials.get(logical) if officials else None
        enhanced_rows = enhanceds.get(logical) if enhanceds else None
        for address in diff.addresses:
            state = states.setdefault(address.owner, ToggleState(address.owner, "n/a"))
            row = node.get(address.key)
            if address.key not in leaf_cache:
                leaf_cache[address.key] = leaves(row) if row is not None else {}
            live_leaf = leaf_cache[address.key].get(address.path)
            live_lines = split_lines(live_leaf) if live_leaf is not None else []
            if address.kind == "cell":
                if address.line >= len(live_lines):
                    state.foreign += 1
                    continue
                cells = live_lines[address.line].split(",")
                current = cells[address.col] if address.col < len(cells) else None
                if current == address.enhanced:
                    state.enhanced += 1
                elif current == address.official:
                    state.official += 1
                else:
                    state.foreign += 1
            elif address.kind == "line":
                current = live_lines[address.line] if address.line < len(live_lines) else None
                if current == address.enhanced:
                    state.enhanced += 1
                elif current == address.official:
                    state.official += 1
                else:
                    state.foreign += 1
            elif address.kind == "appended":
                state.enhanced += 1 if address.line < len(live_lines) else 0
                state.official += 0 if address.line < len(live_lines) else 1
            elif address.kind == "key":
                current = node.get(address.key)
                if enhanced_rows is not None and current == enhanced_rows.get(address.key):
                    state.enhanced += 1
                elif official_rows is not None and current == official_rows.get(address.key):
                    state.official += 1
                else:
                    state.foreign += 1
            elif address.kind == "deleted_key":
                present = address.key in node
                state.enhanced += 0 if present else 1
                state.official += 1 if present else 0
    for state in states.values():
        total = state.official + state.enhanced + state.foreign
        if total == 0:
            state.state = "n/a"
        elif state.foreign and state.foreign == total:
            state.state = "foreign"
        elif state.enhanced == total:
            state.state = "enhanced"
        elif state.official == total:
            state.state = "official"
        else:
            state.state = "mixed"
    return states


# ------------------------------------------------------------------ 计划/写盘

@dataclass
class Plan:
    desired: dict[str, bool]
    sub: dict[str, bool]
    scope: str
    details: list[ComposeDetail]
    payloads: dict[str, bytes]
    selfcheck: dict
    escalated: dict[str, int]
    misaligned: dict[str, list[str]]
    foreign: list[str]
    digest: str

    def as_dict(self) -> dict:
        return {
            "desired": self.desired, "sub": self.sub, "scope": self.scope,
            "digest": self.digest,
            "details": [d.as_dict() for d in self.details if d.changed],
            "selfcheck": self.selfcheck, "escalated": self.escalated,
            "misaligned": self.misaligned, "foreign": self.foreign[:40],
            "foreignCount": len(self.foreign),
            "tables": [d.logical for d in self.details if d.changed],
        }


def _load_sides(ctx: Context, snap: Snapshot, policy: pol.Policy
                ) -> tuple[dict[str, TableDiff], dict[str, bytes], dict[str, bytes],
                           dict[str, bytes]]:
    diffs: dict[str, TableDiff] = {}
    officials: dict[str, bytes] = {}
    enhanced: dict[str, bytes] = {}
    lives: dict[str, bytes] = {}
    for logical in MANAGED_TABLES:
        enhanced_raw = snap.get(logical)
        live_raw = _read_live(ctx, logical)
        official_raw = ctx.baseline.get("common", quest.hashed_rel(logical))
        if enhanced_raw is None or live_raw is None or official_raw is None:
            continue
        officials[logical] = official_raw
        enhanced[logical] = enhanced_raw
        lives[logical] = live_raw
        diffs[logical] = diff_table(logical, official_raw, enhanced_raw, policy)
    return diffs, officials, enhanced, lives


def _selfcheck(diffs: Mapping[str, TableDiff], officials: Mapping[str, bytes],
               enhanced: Mapping[str, bytes], policy: pol.Policy) -> dict:
    """E1 全关 → 官方 key 逐个等于官方值;E2 全开 → 官方 key 逐个等于增强值。

    两条都不成立就说明归属表有洞(某地址没人认领,或被两个桶重复认领)。
    用快照字节当 live 起点,排除第三方漂移的干扰。
    """
    all_off = {spec.id: False for spec in TOGGLES}
    all_on = {spec.id: True for spec in TOGGLES}
    result: dict = {"E1": True, "E2": True, "e1_bad": [], "e2_bad": []}
    for logical, diff in diffs.items():
        official_raw, enhanced_raw = officials[logical], enhanced[logical]
        official = quest.parse_node(official_raw)
        target = quest.parse_node(enhanced_raw)
        off_bytes, _d = compose_table(
            official_raw=official_raw, enhanced_raw=enhanced_raw,
            live_raw=enhanced_raw, diff=diff, desired=all_off, sub={}, allow_foreign=True)
        on_bytes, _d = compose_table(
            official_raw=official_raw, enhanced_raw=enhanced_raw,
            live_raw=official_raw, diff=diff, desired=all_on, sub={}, allow_foreign=True)
        composed_off = quest.parse_node(off_bytes)
        composed_on = quest.parse_node(on_bytes)
        for key, official_row in official.items():
            if policy.is_content_key(logical, key):
                continue
            if composed_off.get(key) != official_row:
                result["E1"] = False
                result["e1_bad"].append(f"{logical}:{key}")
                break
        for key in official:
            if policy.is_content_key(logical, key):
                continue
            if composed_on.get(key) != target.get(key):
                result["E2"] = False
                result["e2_bad"].append(f"{logical}:{key}")
                break
    result["e1_bad"] = result["e1_bad"][:12]
    result["e2_bad"] = result["e2_bad"][:12]
    return result


def build_plan(ctx: Context, snap: Snapshot, desired: Mapping[str, bool], *,
               sub: Mapping[str, bool] | None = None, scope: str = "all",
               allow_foreign: bool = False, policy: pol.Policy | None = None,
               selfcheck: bool = True) -> Plan:
    policy = policy or pol.Policy()
    sub = dict(sub or {})
    desired = dict(desired)
    diffs, officials, enhanced, lives = _load_sides(ctx, snap, policy)
    scoped_tables = set()
    for spec in TOGGLES:
        if scope in ("all", spec.scope):
            scoped_tables.update(spec.tables)

    details: list[ComposeDetail] = []
    payloads: dict[str, bytes] = {}
    foreign: list[str] = []
    escalated = {"R1": 0, "R2": 0}
    misaligned: dict[str, list[str]] = {}
    for logical, diff in diffs.items():
        escalated["R1"] += diff.escalated["R1"]
        escalated["R2"] += diff.escalated["R2"]
        if diff.misaligned_keys:
            misaligned[logical] = diff.misaligned_keys[:20]
        if logical not in scoped_tables:
            continue
        blob, detail = compose_table(
            official_raw=officials[logical], enhanced_raw=enhanced[logical],
            live_raw=lives[logical], diff=diff, desired=desired, sub=sub,
            allow_foreign=allow_foreign)
        details.append(detail)
        foreign.extend(f"{logical}: {item}" for item in detail.foreign)
        if detail.changed:
            payloads[logical] = blob

    # 资产文件:整文件二选一(引擎默认的 drop 语义对自服等于什么都不做)
    for logical in MANAGED_ASSETS:
        spec_id = ("char.white_tiger" if logical == WHITE_TIGER_DSL
                   else "other.official_art")
        if scope not in ("all", TOGGLE_BY_ID[spec_id].scope):
            continue
        rel = quest.hashed_rel(logical)
        official_raw = ctx.baseline.get("common", rel)
        enhanced_raw = snap.get(logical)
        live_raw = _read_live(ctx, logical)
        if official_raw is None or enhanced_raw is None or live_raw is None:
            continue
        want = bool(desired.get(spec_id, TOGGLE_BY_ID[spec_id].default))
        target = enhanced_raw if want else official_raw
        detail = ComposeDetail(logical)
        if live_raw not in (official_raw, enhanced_raw):
            detail.foreign.append(f"{logical}: 整文件第三方改动")
            foreign.append(f"{logical}: 整文件第三方改动")
            if not allow_foreign:
                details.append(detail)
                continue
        if target != live_raw:
            detail.changed = True
            if want:
                detail.to_enhanced = 1
            else:
                detail.to_official = 1
            payloads[logical] = target
        details.append(detail)

    checks = (_selfcheck(diffs, officials, enhanced, policy) if selfcheck
              else {"E1": None, "E2": None})
    digest = hashlib.sha256(json.dumps({
        "desired": desired, "sub": sub, "scope": scope,
        "tables": {logical: pol.sha256(blob) for logical, blob in sorted(payloads.items())},
    }, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
    return Plan(desired, sub, scope, details, payloads, checks, escalated,
                misaligned, foreign, digest)


def apply_plan(ctx: Context, plan: Plan, *, dry_run: bool = False,
               allow_foreign: bool = False) -> dict:
    """原子写盘:先全量 pre-image,再逐表替换;任一失败整体回滚。"""
    if plan.selfcheck.get("E1") is False or plan.selfcheck.get("E2") is False:
        raise SwitchError(
            f"自检等式不成立(E1={plan.selfcheck['E1']} E2={plan.selfcheck['E2']}),"
            f"归属表有洞: {plan.selfcheck.get('e1_bad') or plan.selfcheck.get('e2_bad')}")
    if plan.foreign and not allow_foreign:
        raise ForeignDriftError(
            f"store 里有 {len(plan.foreign)} 处快照之后的第三方改动,未确认不覆盖:\n  "
            + "\n  ".join(plan.foreign[:5]))
    if not plan.payloads:
        return {"written": [], "preimage": None, "dry_run": dry_run, "changed": 0}
    if dry_run:
        return {"written": [str(ctx.table_path(l)) for l in plan.payloads],
                "preimage": None, "dry_run": True, "changed": len(plan.payloads)}

    preimage_id = f"pre-{time.strftime('%Y%m%d-%H%M%S')}-{plan.digest}"
    preimage_dir = PREIMAGE_DIR / preimage_id
    preimage_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"id": preimage_id, "created": time.strftime("%Y-%m-%d %H:%M:%S"),
                "store": str(ctx.store), "digest": plan.digest, "files": []}
    written: list[str] = []
    try:
        for logical in plan.payloads:
            path = ctx.table_path(logical)
            rel = quest.hashed_rel(logical)
            backup = preimage_dir / rel.replace("/", "_")
            shutil.copy2(path, backup)
            manifest["files"].append({"logical": logical, "rel": rel,
                                      "backup": backup.name,
                                      "sha256": pol.sha256(path.read_bytes())})
        (preimage_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        for logical, blob in plan.payloads.items():
            path = ctx.table_path(logical)
            temporary = path.with_name(path.name + f".enhsw-{plan.digest}.tmp")
            temporary.write_bytes(blob)
            os.replace(temporary, path)
            written.append(str(path))
    except BaseException:
        for entry in manifest["files"]:
            backup = preimage_dir / entry["backup"]
            if backup.is_file():
                shutil.copy2(backup, ctx.store / entry["rel"])
        raise
    _save_state(plan, preimage_id)
    return {"written": written, "preimage": preimage_id, "dry_run": False,
            "changed": len(plan.payloads)}


def rollback(ctx: Context, preimage_id: str, *, dry_run: bool = False) -> dict:
    manifest_path = PREIMAGE_DIR / preimage_id / "manifest.json"
    if not manifest_path.is_file():
        raise SwitchError(f"pre-image 不存在: {preimage_id}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    restored = []
    for entry in manifest["files"]:
        backup = PREIMAGE_DIR / preimage_id / entry["backup"]
        target = ctx.store / entry["rel"]
        if not backup.is_file():
            raise SwitchError(f"pre-image 缺文件: {entry['backup']}")
        if not dry_run:
            shutil.copy2(backup, target)
        restored.append(entry["logical"])
    return {"restored": restored, "dry_run": dry_run, "preimage": preimage_id}


def _save_state(plan: Plan, preimage_id: str) -> None:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps({
        "desired": plan.desired, "sub": plan.sub, "scope": plan.scope,
        "digest": plan.digest, "preimage": preimage_id,
        "applied": time.strftime("%Y-%m-%d %H:%M:%S"),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_state() -> dict:
    if STATE_PATH.is_file():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except ValueError:
            return {}
    return {}


def status(ctx: Context, snap: Snapshot | None = None, *,
           policy: pol.Policy | None = None) -> dict:
    policy = policy or pol.Policy()
    snap = snap or load_snapshot()
    diffs, officials, enhanced, lives = _load_sides(ctx, snap, policy)
    states = observe(
        diffs, lives,
        {logical: quest.parse_node(raw) for logical, raw in officials.items()},
        {logical: quest.parse_node(raw) for logical, raw in enhanced.items()})
    counts = {logical: diff.by_owner() for logical, diff in diffs.items()}
    per_toggle_tables: dict[str, list[str]] = {}
    for logical, owners in counts.items():
        for owner in owners:
            per_toggle_tables.setdefault(owner, []).append(logical)
    toggles = []
    for spec in TOGGLES:
        state = states.get(spec.id, ToggleState(spec.id, "n/a"))
        toggles.append({
            "id": spec.id, "label": spec.label, "scope": spec.scope,
            "default": spec.default, "subs": list(spec.subs),
            "offEqualsOfficial": spec.off_equals_official,
            "guiReadonly": spec.gui_readonly, "warn": spec.warn, "note": spec.note,
            "tables": sorted(per_toggle_tables.get(spec.id, [])),
            **state.as_dict(),
        })
    escalated = {"R1": sum(d.escalated["R1"] for d in diffs.values()),
                 "R2": sum(d.escalated["R2"] for d in diffs.values())}
    current = observed_vector(states)
    return {
        "store": str(ctx.store), "cdn": str(ctx.cdn), "profile": ctx.profile_id,
        "snapshot": snap.as_dict(), "toggles": toggles, "escalated": escalated,
        "misaligned": {l: d.misaligned_keys[:12] for l, d in diffs.items()
                       if d.misaligned_keys},
        "state": load_state(), "current": current,
        "presets": {name: preset_vector(name, current=current)
                    for name in ("on", "official", "default")},
        "presetExcluded": sorted(PRESET_EXCLUDED),
        "guarded": sorted(GUARDED_TOGGLES),
        "subs": sorted(SUB_BUCKETS),
    }


# ------------------------------------------------------------------ CLI

def _desired_from_args(args: argparse.Namespace,
                       observed: Mapping[str, bool]) -> dict[str, bool]:
    if args.preset:
        desired = preset_vector(args.preset, scope=None, current=dict(observed))
    else:
        desired = dict(observed)   # 没点到的开关保持现状
    explicit: set[str] = set()
    for toggle_id in args.on or ():
        if toggle_id not in TOGGLE_BY_ID:
            raise SwitchError(f"未知开关: {toggle_id}")
        desired[toggle_id] = True
        explicit.add(toggle_id)
    for toggle_id in args.off or ():
        if toggle_id not in TOGGLE_BY_ID:
            raise SwitchError(f"未知开关: {toggle_id}")
        desired[toggle_id] = False
        explicit.add(toggle_id)
    allowed = {"char.white_tiger": args.allow_white_tiger,
               "other.shop_700099": args.allow_shop}
    for toggle_id, flag in GUARDED_TOGGLES.items():
        spec = TOGGLE_BY_ID[toggle_id]
        if toggle_id in explicit and desired[toggle_id] != spec.default \
                and not allowed[toggle_id]:
            raise SwitchError(
                f"{toggle_id} 需要服务端/存档联动,要切得显式加 {flag}:{spec.warn}")
    return desired


def _print_status(payload: dict) -> None:
    snap = payload["snapshot"]
    print(f"store: {payload['store']}")
    print(f"快照: {snap['name']}({snap['created']},{snap['entries']} 项)")
    label = {"official": "官方", "enhanced": "增强", "mixed": "混合",
             "foreign": "外来", "n/a": "—"}
    print(f"\n{'开关':<22} {'状态':<6} {'官方格':>8} {'增强格':>8} {'外来':>6}  影响表")
    for toggle in payload["toggles"]:
        counts = toggle["counts"]
        print(f"{toggle['id']:<22} {label[toggle['state']]:<6} "
              f"{counts['official']:>8} {counts['enhanced']:>8} {counts['foreign']:>6}  "
              f"{','.join(t.split('/')[-1].replace('.orderedmap','') for t in toggle['tables'])}")
        if toggle["warn"]:
            print(f"    ⚠ {toggle['warn']}")
    esc = payload["escalated"]
    print(f"\n因跨规则耦合被整行处理: R1(枚举/哨兵) {esc['R1']} 行、R2(子桶跨越) {esc['R2']} 行")
    for logical, keys in payload["misaligned"].items():
        print(f"  [行对齐降级] {logical}: {keys}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--store", help="store 根(默认按 profiles.json)")
    parser.add_argument("--cdn", help="CDN 根(默认 WF_CDN_DIR 或 <repo>/.cdn/cn)")
    parser.add_argument("--repo-root", dest="repo")
    parser.add_argument("--snapshot", help="用哪份增强基线快照(默认最近冻结的)")
    sub = parser.add_subparsers(dest="command", required=True)

    snap_cmd = sub.add_parser("snapshot", help="把当前 store 冻结成「增强侧」")
    snap_cmd.add_argument("--tag", default="base")
    snap_cmd.add_argument("--force", action="store_true", help="守卫不过也冻(会留痕)")
    snap_cmd.add_argument("--dry-run", action="store_true")

    sub.add_parser("snapshots", help="列出已有快照")
    sub.add_parser("status", help="逐开关显示 store 现状")

    for name, help_text in (("plan", "预览切换结果"), ("apply", "写进 store")):
        cmd = sub.add_parser(name, help=help_text)
        cmd.add_argument("--preset", choices=("on", "official", "default"))
        cmd.add_argument("--on", action="append", metavar="开关ID")
        cmd.add_argument("--off", action="append", metavar="开关ID")
        cmd.add_argument("--scope", default="all", choices=("all", *SCOPES))
        cmd.add_argument("--sub-off", action="append", default=[],
                         choices=("power", "feel", "gate"), metavar="子桶")
        cmd.add_argument("--allow-foreign", action="store_true",
                         help="覆盖快照之后的第三方改动")
        cmd.add_argument("--allow-white-tiger", action="store_true")
        cmd.add_argument("--allow-shop", action="store_true")
        if name == "apply":
            cmd.add_argument("--dry-run", action="store_true")

    roll = sub.add_parser("rollback", help="回滚到某次 apply 之前")
    roll.add_argument("--preimage", required=True)
    roll.add_argument("--dry-run", action="store_true")

    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        if args.command == "snapshots":
            payload = list_snapshots()
            print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json
                  else "\n".join(f"{s['name']}  {s['created']}  {s['entries']} 项"
                                 + ("  [forced]" if s["forced"] else "")
                                 for s in payload) or "(还没有快照)")
            return 0
        ctx = resolve_context(store=args.store, cdn=args.cdn, repo=args.repo)
        if args.command == "snapshot":
            snap = snapshot_freeze(ctx, tag=args.tag, force=args.force,
                                   dry_run=args.dry_run)
            print(json.dumps(snap.as_dict(), ensure_ascii=False) if args.json
                  else f"已冻结增强基线 {snap.name}({len(snap.entries)} 项)"
                       f"{' [dry-run]' if args.dry_run else ''}")
            return 0
        if args.command == "rollback":
            result = rollback(ctx, args.preimage, dry_run=args.dry_run)
            print(json.dumps(result, ensure_ascii=False) if args.json
                  else f"已回滚 {len(result['restored'])} 张表"
                       f"{'(dry-run)' if result['dry_run'] else ''}")
            return 0
        snap = load_snapshot(args.snapshot)
        if args.command == "status":
            payload = status(ctx, snap)
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                _print_status(payload)
            return 0
        desired = _desired_from_args(args, status(ctx, snap)["current"])
        sub_desired = {name: name not in args.sub_off for name in SUB_BUCKETS}
        plan = build_plan(ctx, snap, desired, sub=sub_desired, scope=args.scope,
                          allow_foreign=args.allow_foreign)
        if args.command == "plan":
            if args.json:
                print(json.dumps(plan.as_dict(), ensure_ascii=False, indent=2))
            else:
                _print_plan(plan)
            return 0
        result = apply_plan(ctx, plan, dry_run=getattr(args, "dry_run", False),
                            allow_foreign=args.allow_foreign)
        print(json.dumps(result, ensure_ascii=False, indent=2) if args.json
              else f"写入 {result['changed']} 张表"
                   f"{'(dry-run)' if result['dry_run'] else ''};"
                   f"回滚用 rollback --preimage {result['preimage']}")
        return 0
    except (SwitchError, pol.BaselineUnavailable) as exc:
        print(f"[ERR] {exc}", file=sys.stderr)
        return 2


def _print_plan(plan: Plan) -> None:
    print(f"计划 digest={plan.digest} scope={plan.scope}")
    print(f"自检: E1(全关=官方)={plan.selfcheck['E1']} E2(全开=增强)={plan.selfcheck['E2']}")
    for detail in plan.details:
        if not detail.changed:
            continue
        print(f"  {detail.logical}: →官方 {detail.to_official} 格 / →增强 "
              f"{detail.to_enhanced} 格 / 加行 {detail.rows_added} / 删行 "
              f"{detail.rows_dropped} / 补回 {detail.rows_restored}")
    if not plan.payloads:
        print("  (store 已经是目标状态,无需改动)")
    print(f"整行处理: R1 {plan.escalated['R1']} 行、R2 {plan.escalated['R2']} 行")
    if plan.foreign:
        print(f"[警告] {len(plan.foreign)} 处第三方改动(未加 --allow-foreign 时保留现值):")
        for item in plan.foreign[:5]:
            print(f"    {item}")


if __name__ == "__main__":
    sys.exit(main())
