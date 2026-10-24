# -*- coding: utf-8 -*-
"""战斗图集(layer0 / layer1)预算预检 —— 发布前拦 `U_1d93f4`。

## 为什么需要它

客户端进战斗时把这一局要用的所有精灵表打进**两张 4096×4096 图集**
(`layer0_null` / `layer1_null`)。装不下就在
`MaxRectsPacker.allocateRectangle` 直接
`throw "Failed to allocate packing rectangle: size exceeded."` ——
玩家看到的是 `U_1d93f4`,房主崩 → 整个房间散。

2026-09-09 灰服五重三人房真机复发过一次;2026-09-17 的资源体量审计用客户端
真打包器实测:**9 个最重历史自制角色占主位的三人房已经吃到 86.3%**,
再让任一批新角色上协力就溢出(96.5%–110.4%)。而**发布链上没有任何一道闸门
看图集总量** —— flow preflight 只查包自洽、manifest、三层声明。这个模块补这一道。

## 判据来源(全部逐行核对过反编译客户端,不是估算)

`弹国服/scripts/pinball/loading/battle/BattleStartProductionViewService.as`:

* `setupTextureAtlas` → `pack(name, target, 4096, 4096, ...)`,
  `StarlingAtlasBuilder(..., 4096, 4096, 2, ...)` ⇒ **两张 4096×4096,margin = 2**。
  折算单张占用必须用 `(w+2)×(h+2)`。
* `autoDistribute` 的 `spriteSheet` 分支决定一张精灵表归哪一层(见 `SPRITE_SHEET_LAYERS`)。
* `autoDistribute` 的 `image` 分支里 `character/.+/ui/` 落 `packingTarget1` ⇒
  **角色 UI 图进 layer1**,不进 layer0。
* 每张精灵表**整张入箱**,是一个 `ceil(frameW)×ceil(frameH)` 的矩形,不是逐帧。

「谁会被加载」另有一层判据(`BattleCharacterLogic.resolvePathCollection`):
只加 `pixelart` 动画、四张 UI 图(`cutin_skill_chain` / `battle_member_status` /
`battle_control_board` / `square`)和 `skill_cutin`(走 `addCharacter`,**不进任何图集**)。
`pixelart/special_sprite_sheet` 只在扭蛋入队演出与角色菜单用,**战斗不加载**。

多人房把三队编成合并进**同一张** layer0(`BattleAssetPathCollectionBuilder.addMultiQuest`),
路径集合去重 ⇒ 三人房最多 18 个不同角色同时压在一张图集上。所以判断「会不会炸」
必须问「那一局房间里出现了哪些不同角色」,不是「哪一关」。

## 本工具做什么

1. 量出**一个角色包(或一组角色)进战斗会带的纹理**,分 layer0 / layer1 列清单与占用。
2. **场景模拟**:本包 + live 最重的 N 个自制角色 + 五重连战底座,用客户端打包器
   的 1:1 移植(`pack()`,与 `${WF_ROOT}/out/atlas_probe_20260909/packer.py` 同一份实现)
   实跑装箱 —— **不是面积比估算**。按面积 0.85 估会误判,真实失败点在 14.7–16.0 Mpx 之间。
3. 超阈值(默认 90%)或直接溢出就以非 0 退出码返回,并打印卡在哪一张。

## 名册 `atlas_budget_roster.json`

场景里的 live 角色、boss 底座、共享件的**纹理清单**来自 2026-09-17 审计产物
(见该文件 `sources` 字段),**尺寸默认每次运行都从当前 store 重新量**;
`--dims roster` 用名册里冻结的 09-17 尺寸(离线/测试用)。

名册还带两组 `golden_formations`:审计实测过的一 FITS 一 OVERFLOW 编队,
连同期望值一起冻结,`--self-check` 会重放它们 —— 打包器实现一变就报红。

## 退出码

* 0 = 通过
* 1 = 超阈值 / 溢出 / self-check 与黄金值不符
* 2 = 用法或数据错误

最后一行永远是一行稳定 JSON(`sort_keys`),给脚本解析用。
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import struct
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Iterable, Mapping, Sequence

TOOL_DIR = Path(__file__).resolve().parent
ROOT = TOOL_DIR.parent
ROSTER_PATH = TOOL_DIR / "atlas_budget_roster.json"

SCHEMA = "wf-atlas-budget-check/1"
ATLAS_WIDTH = 4096
ATLAS_HEIGHT = 4096
MARGIN = 2
CAPACITY = ATLAS_WIDTH * ATLAS_HEIGHT
DEFAULT_THRESHOLD = 90.0
DEFAULT_HEAVIEST = 9
DEFAULT_SCENARIOS = ("five-boss-r0", "five-boss-r1")
SUBJECT_ROLES = ("unison", "main", "main-leader")
DEFAULT_SUBJECT_ROLE = "main-leader"

# 战斗里会被加载的四张角色 UI 图(addImage);它们全部落 layer1。
BATTLE_UI_SLOTS = ("cutin_skill_chain", "battle_member_status",
                   "battle_control_board", "square")

# autoDistribute 的 spriteSheet 分支,逐条对应反编译里的 EReg。
# (匹配方式, 模式, 落哪一层)。'^' = 前缀匹配,'=' = 全等,'~' = 子串。
SPRITE_SHEET_LAYERS: tuple[tuple[str, str, str], ...] = (
    ("=", "battle/common/layer0", "layer0"),
    ("=", "battle/common/layer1", "layer1"),
    ("=", "battle/common/boss_rush_layer1", "layer1"),
    ("=", "battle/common/disguise_hp", "layer1"),
    ("=", "battle/common/score_attack", "layer1"),
    ("=", "battle/common/attention", "layer1"),
    ("^", "battle/effect/", "layer0"),
    ("^", "battle/field_object/", "layer0"),
    ("^", "battle/boss/", "layer0"),
    ("^", "battle/zako/", "layer0"),
    ("^", "battle/funnel/", "layer0"),
    ("^", "battle/tutorial/", "layer1"),
    ("^character-pixelart", "", "layer0"),          # ^character/.+/pixelart/
    ("=", "item/sprite_sheet", "layer1"),
    ("~", "battle/field/", "layer0"),
    ("^", "battle/uncommon/layer0/", "layer0"),
    ("^", "battle/uncommon/layer1/", "layer1"),
    ("=", "battle/common/score_attack2", "layer1"),
)


class RosterError(Exception):
    """名册/输入数据本身的问题(退出码 2)。"""


# --------------------------------------------------------------------------
# MaxRectsPacker —— 反编译客户端 packing/core/MaxRectsPacker.as 的 1:1 移植
# --------------------------------------------------------------------------

class Overflow(Exception):
    """对应客户端 allocateRectangle 里那句 throw(玩家看到 U_1d93f4)。"""


class _Rect:
    __slots__ = ("x", "y", "w", "h")

    def __init__(self, x: int, y: int, w: int, h: int) -> None:
        self.x, self.y, self.w, self.h = x, y, w, h


def _split(free: _Rect, placed: _Rect, out: list[_Rect]) -> bool:
    if (placed.x >= free.x + free.w or placed.x + placed.w <= free.x
            or placed.y >= free.y + free.h or placed.y + placed.h <= free.y):
        return False
    if placed.x < free.x + free.w and placed.x + placed.w > free.x:
        if free.y < placed.y < free.y + free.h:
            out.append(_Rect(free.x, free.y, free.w, placed.y - free.y))
        if placed.y + placed.h > free.y and placed.y + placed.h < free.y + free.h:
            out.append(_Rect(free.x, placed.y + placed.h, free.w,
                             free.y + free.h - (placed.y + placed.h)))
    if placed.y < free.y + free.h and placed.y + placed.h > free.y:
        if free.x < placed.x < free.x + free.w:
            out.append(_Rect(free.x, free.y, placed.x - free.x, free.h))
        if placed.x + placed.w > free.x and placed.x + placed.w < free.x + free.w:
            out.append(_Rect(placed.x + placed.w, free.y,
                             free.x + free.w - (placed.x + placed.w), free.h))
    return True


def _prune(free: list[_Rect]) -> None:
    drop = []
    n = len(free)
    for i in range(n):
        a = free[i]
        aa = a.w * a.h
        for j in range(i + 1, n):
            b = free[j]
            bb = b.w * b.h
            small, big = (a, b) if aa < bb else (b, a)
            if (small.x >= big.x and small.x + small.w <= big.x + big.w
                    and small.y >= big.y and small.y + small.h <= big.y + big.h):
                drop.append(small)
                if aa < bb:
                    break
    for r in drop:
        try:
            free.remove(r)
        except ValueError:
            pass


def pack(items: Sequence[tuple[str, int, int]], max_w: int = ATLAS_WIDTH,
         max_h: int = ATLAS_HEIGHT, margin: int = MARGIN) -> tuple[int, int]:
    """items: [(name, w, h)] -> (used_w, used_h);装不下抛 Overflow(带卡住那一张)。

    与客户端一致:按面积从大到小放,长边竖过来(短边作宽),每边加 margin,
    在自由矩形里选 min(剩宽, 剩高) 最小的那块。
    """
    pending = sorted(items, key=lambda t: (t[1] * t[2], t[0]))
    free = [_Rect(0, 0, max_w, max_h)]
    used_w = used_h = 0
    while pending:
        name, w, h = pending.pop()
        rotated = w > h
        pw = (h if rotated else w) + margin
        ph = (w if rotated else h) + margin
        best, bestscore = None, max(max_w, max_h) + 1
        for f in free:
            score = min(f.w - pw, f.h - ph)
            if 0 <= score < bestscore:
                best, bestscore = f, score
        if best is None:
            raise Overflow("%s (%dx%d -> %dx%d padded)" % (name, w, h, pw, ph))
        placed = _Rect(best.x, best.y, pw, ph)
        removed, added = [], []
        for f in free:
            if _split(f, placed, added):
                removed.append(f)
        for f in removed:
            free.remove(f)
        free.extend(added)
        _prune(free)
        used_w = max(used_w, placed.x + placed.w - margin)
        used_h = max(used_h, placed.y + placed.h - margin)
    return used_w, used_h


def rect_area(dim: Sequence[int]) -> int:
    """单张图在图集里真正吃掉的面积:margin 算进去。"""
    return (int(dim[0]) + MARGIN) * (int(dim[1]) + MARGIN)


def pack_sheets(sheets: Mapping[str, Sequence[int]]) -> dict:
    """把一组 {精灵表: [w, h]} 实跑装箱,返回判决 dict。"""
    items = [(name, int(d[0]), int(d[1])) for name, d in sheets.items()]
    total = sum(rect_area(d) for d in sheets.values())
    out = {"sheets": len(sheets), "px": total,
           "mpx": round(total / 1e6, 6),
           "fill_pct": round(100.0 * total / CAPACITY, 2)}
    try:
        used_w, used_h = pack(items)
    except Overflow as exc:
        out.update({"fits": False, "overflow_at": str(exc), "used": None})
    else:
        out.update({"fits": True, "overflow_at": None, "used": [used_w, used_h]})
    return out


# --------------------------------------------------------------------------
# 分层判据
# --------------------------------------------------------------------------

def sprite_sheet_layer(sheet: str) -> str | None:
    """一张精灵表归 layer0 / layer1;两条规则都不中返回 None(客户端会 throw)。"""
    for kind, pattern, layer in SPRITE_SHEET_LAYERS:
        if kind == "=":
            if sheet == pattern:
                return layer
        elif kind == "^":
            if sheet.startswith(pattern):
                return layer
        elif kind == "~":
            if pattern in sheet:
                return layer
        elif kind == "^character-pixelart":
            if sheet.startswith("character/") and "/pixelart/" in sheet:
                return layer
    return None


def is_layer0_sheet(sheet: str) -> bool:
    return sprite_sheet_layer(sheet) == "layer0"


def loaded_in_battle(sheet: str) -> tuple[bool, str]:
    """这张精灵表战斗里到底加不加载(resolvePathCollection 那一层)。"""
    if sheet.endswith("/pixelart/special_sprite_sheet"):
        return False, "special_sprite_sheet 只在入队演出/角色菜单加载,战斗不进图集"
    return True, ""


def battle_ui_image(logical_sheet: str) -> bool:
    """角色 UI 图里战斗真会 addImage 的那四张(两个立绘槽各一份)。"""
    if not logical_sheet.startswith("character/") or "/ui/" not in logical_sheet:
        return False
    name = logical_sheet.rsplit("/", 1)[-1]
    for slot in BATTLE_UI_SLOTS:
        if name in (slot + "_0", slot + "_1"):
            return True
    return False


# --------------------------------------------------------------------------
# 尺寸来源
# --------------------------------------------------------------------------

def png_dims_from_bytes(head: bytes) -> list[int] | None:
    """store 里的 PNG 魔数被混淆成小写 \\x89png,两种都认。"""
    if len(head) < 24 or head[1:4] not in (b"PNG", b"png") or head[12:16] != b"IHDR":
        return None
    w, h = struct.unpack(">II", head[16:24])
    return [int(w), int(h)]


class DimSource:
    """按 store → 名册快照 的顺序解析每张图的尺寸,并记录漂移。

    ``mode='roster'`` 完全不碰 store(测试/离线用)。
    ``overrides`` 优先于一切 —— 角色包自己的 PNG 字节走这里,
    因为**正要发布的就是包里那一份**,不是 store 里的旧版。
    """

    def __init__(self, roster: Mapping, mode: str = "store",
                 overrides: Mapping[str, Sequence[int]] | None = None) -> None:
        self.mode = mode
        self.roster = roster
        self.overrides = dict(overrides or {})
        self.snapshot = _roster_snapshot_dims(roster)
        self.drift: list[dict] = []
        self.missing: list[str] = []
        self._cache: dict[str, list[int] | None] = {}
        self._roots: dict[str, Path] | None = None
        self._store_error: str | None = None

    # -- store 定位 --------------------------------------------------------
    def _store_roots(self) -> dict[str, Path]:
        if self._roots is None:
            self._roots = {}
            try:
                pass  # Imports resolve from this checkout/package, not external source copies.
                import wf_assets  # noqa: PLC0415
                import wf_mod_tool as core  # noqa: PLC0415
                store = core.resolve_active_store()
                if store is None:
                    self._store_error = "未解析到目标 store(" + core.TARGET_STORE_HINT + ")"
                else:
                    self._roots = {k: v for k, v in wf_assets.roots(store).items()}
            except Exception as exc:                     # noqa: BLE001
                self._store_error = "store 不可读:%s" % exc
        return self._roots

    def _from_store(self, sheet: str) -> list[int] | None:
        roots = self._store_roots()
        if not roots:
            return None
        digest = hashlib.sha1((sheet + ".png" + _salt()).encode("utf-8")).hexdigest()
        for root in roots.values():
            path = root / digest[:2] / digest[2:]
            if path.is_file():
                with path.open("rb") as fh:
                    return png_dims_from_bytes(fh.read(32))
        return None

    # -- 对外 --------------------------------------------------------------
    def get(self, sheet: str) -> list[int] | None:
        if sheet in self._cache:
            return self._cache[sheet]
        dim = self.overrides.get(sheet)
        if dim is not None:
            dim = [int(dim[0]), int(dim[1])]
        elif self.mode == "store":
            dim = self._from_store(sheet)
            frozen = self.snapshot.get(sheet)
            if dim is None and frozen is not None:
                self.drift.append({"sheet": sheet, "roster": frozen, "store": None,
                                   "note": "store 里找不到,回退名册快照尺寸"})
                dim = list(frozen)
            elif dim is not None and frozen is not None and list(frozen) != dim:
                self.drift.append({"sheet": sheet, "roster": list(frozen), "store": dim,
                                   "note": "store 已漂移,按 store 计"})
        else:
            frozen = self.snapshot.get(sheet)
            dim = list(frozen) if frozen is not None else None
        if dim is None:
            self.missing.append(sheet)
        self._cache[sheet] = dim
        return dim

    def resolve(self, sheets: Iterable[str]) -> "OrderedDict[str, list[int]]":
        out: OrderedDict[str, list[int]] = OrderedDict()
        for sheet in sheets:
            dim = self.get(sheet)
            if dim is not None:
                out[sheet] = dim
        return out


def _salt() -> str:
    pass  # Imports resolve from this checkout/package, not external source copies.
    import wf_mod_tool as core  # noqa: PLC0415
    return core.SALT


def _roster_snapshot_dims(roster: Mapping) -> dict[str, list[int]]:
    snap: dict[str, list[int]] = {}
    snap.update({k: list(v) for k, v in roster.get("shared", {}).items()})
    for rec in roster.get("bosses", {}).values():
        for group in ("base", "effects"):
            snap.update({k: list(v) for k, v in rec.get(group, {}).items()})
    for rec in roster.get("characters", {}).values():
        for group in ("pixelart", "skill_sheets", "pf_sheets", "ui_layer1"):
            snap.update({k: list(v) for k, v in rec.get(group, {}).items()})
    return snap


# --------------------------------------------------------------------------
# 名册
# --------------------------------------------------------------------------

def load_roster(path: Path | str | None = None) -> dict:
    path = Path(path) if path else ROSTER_PATH
    if not path.is_file():
        raise RosterError("名册不存在:%s" % path)
    roster = json.loads(path.read_text(encoding="utf-8"))
    if roster.get("schema") != "wf-atlas-budget-roster/1":
        raise RosterError("名册 schema 不认识:%r" % roster.get("schema"))
    return roster


def character_sheets(roster: Mapping, code: str, role: str,
                     dims: DimSource) -> "OrderedDict[str, list[int]]":
    """名册里某个角色按位置(主位/队长/协力)会带进 layer0 的精灵表。"""
    rec = roster["characters"].get(code)
    if rec is None:
        raise RosterError("名册里没有角色 %s(用 --pack 指向包目录,或重生成名册)" % code)
    names: list[str] = []
    if role in ("main", "main-leader"):
        names += list(rec.get("pixelart", {}))
    names += list(rec.get("skill_sheets", {}))
    if role == "main-leader":
        names += list(rec.get("pf_sheets", {}))
    return dims.resolve(names)


def character_layer1(roster: Mapping, code: str,
                     dims: DimSource) -> "OrderedDict[str, list[int]]":
    rec = roster["characters"].get(code, {})
    return dims.resolve(list(rec.get("ui_layer1", {})))


def character_total_px(roster: Mapping, code: str, dims: DimSource) -> int:
    rec = roster["characters"][code]
    names = []
    for group in ("pixelart", "skill_sheets", "pf_sheets"):
        names += list(rec.get(group, {}))
    return sum(rect_area(d) for d in dims.resolve(names).values())


def heaviest_customs(roster: Mapping, count: int, dims: DimSource,
                     exclude: Iterable[str] = ()) -> list[str]:
    """按今天的尺寸排出最重的 N 个**自制**角色(官方角色不参与,它们是尺子)。"""
    skip = set(exclude)
    ranked = sorted(
        (c for c, r in roster["characters"].items()
         if r.get("group") == "custom" and c not in skip),
        key=lambda c: (-character_total_px(roster, c, dims), c))
    return ranked[:count]


def scenario_base(roster: Mapping, name: str,
                  dims: DimSource) -> "OrderedDict[str, list[int]]":
    """场景底座:共享件 + 该轮 boss 的本体与专属特效。"""
    spec = roster.get("scenarios", {}).get(name)
    if spec is None:
        raise RosterError("没有这个场景:%s(可用:%s)"
                          % (name, ", ".join(sorted(roster.get("scenarios", {})))))
    names = list(roster.get("shared", {}))
    for key in spec["bosses"]:
        rec = roster["bosses"].get(key)
        if rec is None:
            raise RosterError("名册缺 boss %s" % key)
        names += list(rec.get("base", {})) + list(rec.get("effects", {}))
    return dims.resolve(names)


def build_room(roster: Mapping, dims: DimSource, scenario: str, heaviest: int,
               subject_layer0: Mapping[str, Sequence[int]], subject_role: str,
               exclude_codes: Iterable[str] = ()) -> tuple[OrderedDict, list[str]]:
    """底座 + N 个最重自制角色主位(0/3/6 号位算队长)+ 本包按 subject_role 叠加。

    房间只有 18 个位置,本包是**叠加**在 N 人之上的上界口径:不替掉任何一个人。
    """
    sheets: OrderedDict[str, list[int]] = OrderedDict(scenario_base(roster, scenario, dims))
    codes = heaviest_customs(roster, heaviest, dims, exclude=exclude_codes)
    for index, code in enumerate(codes):
        role = "main-leader" if index % 3 == 0 else "main"
        sheets.update(character_sheets(roster, code, role, dims))
    for name, dim in subject_layer0.items():
        sheets[name] = [int(dim[0]), int(dim[1])]
    return sheets, codes


# --------------------------------------------------------------------------
# 角色包读取
# --------------------------------------------------------------------------

def _pack_root(pack_dir: Path) -> tuple[Path, Path | None]:
    """接受 workspace 目录、package 目录或 roots 目录,返回 (roots, manifest)。"""
    candidates = [pack_dir, pack_dir / "package"]
    for base in candidates:
        roots = base / "roots"
        if roots.is_dir():
            manifest = base / "manifest.json"
            return roots, manifest if manifest.is_file() else None
    if pack_dir.name == "roots" and pack_dir.is_dir():
        manifest = pack_dir.parent / "manifest.json"
        return pack_dir, manifest if manifest.is_file() else None
    raise RosterError("不是角色包目录(找不到 package/roots):%s" % pack_dir)


def read_pack(pack_dir: Path | str) -> dict:
    """列出一个角色包里会进战斗图集的纹理,分 layer0 / layer1,尺寸读**包内**字节。"""
    pack_dir = Path(pack_dir)
    roots, manifest_path = _pack_root(pack_dir)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path else {}

    layer0: OrderedDict[str, list[int]] = OrderedDict()
    layer1: OrderedDict[str, list[int]] = OrderedDict()
    pixelart: OrderedDict[str, list[int]] = OrderedDict()
    excluded: list[dict] = []
    scanned = 0

    for path in sorted(roots.rglob("*.png")):
        rel = path.relative_to(roots).as_posix()
        root_name, _, logical = rel.partition("/")
        if not logical:
            continue
        scanned += 1
        sheet = logical[:-4]
        with path.open("rb") as fh:
            dim = png_dims_from_bytes(fh.read(32))
        if dim is None:
            excluded.append({"sheet": sheet, "root": root_name, "reason": "不是可解的 PNG"})
            continue
        if battle_ui_image(sheet):
            layer1[sheet] = dim
            continue
        layer = sprite_sheet_layer(sheet)
        if layer is None:
            excluded.append({"sheet": sheet, "root": root_name,
                             "reason": "不在 autoDistribute 的任何一条分支里(战斗不加载)"})
            continue
        loaded, why = loaded_in_battle(sheet)
        if not loaded:
            excluded.append({"sheet": sheet, "root": root_name, "reason": why})
            continue
        if layer == "layer0":
            layer0[sheet] = dim
            if "/pixelart/" in sheet:
                pixelart[sheet] = dim
        else:
            layer1[sheet] = dim

    return {"path": str(pack_dir), "roots": str(roots),
            "code": manifest.get("code_name"),
            "character_id": manifest.get("character_id"),
            "package_id": manifest.get("package_id"),
            "package_version": manifest.get("package_version"),
            "png_files_scanned": scanned,
            "layer0": layer0, "layer1": layer1, "pixelart": pixelart,
            "excluded": excluded}


def subject_layer0_for_role(subject: Mapping, role: str) -> "OrderedDict[str, list[int]]":
    """协力位不带像素表(只出技能特效);主位/队长带全部。

    包里分不出「技能特效」与「PF 特效」(要走 DSL 闭包),一律按常驻计 —— 保守。
    """
    out: OrderedDict[str, list[int]] = OrderedDict()
    pixelart = set(subject.get("pixelart", {}))
    for name, dim in subject["layer0"].items():
        if role == "unison" and name in pixelart:
            continue
        out[name] = list(dim)
    return out


def merge_roster_closure(subject: dict, roster: Mapping, dims: DimSource) -> dict:
    """把名册闭包里**包没发但战斗会加载**的图补进 subject。

    包目录只看得到「这个包发了什么」。角色引用的**官方公共特效**(斩铁那颗
    `skill_general/decoration/dummy_ball_white`、夏日白引用的 `desert_commander`)
    不在包里,但进战斗照样占 layer0 —— 不补就是系统性少算。
    名册没有这个角色(全新角色首发)时什么都不做,`roster_only_sheets` 为空。
    """
    rec = roster.get("characters", {}).get(subject.get("code"))
    subject.setdefault("roster_only_sheets", [])
    if rec is None:
        return subject
    for group in ("pixelart", "skill_sheets", "pf_sheets"):
        for name in rec.get(group, {}):
            known = name in subject["layer0"]
            dim = subject["layer0"][name] if known else dims.get(name)
            if dim is None:
                continue
            if not known:
                subject["layer0"][name] = dim
                subject["roster_only_sheets"].append(name)
            if group == "pixelart":
                subject.setdefault("pixelart", OrderedDict())[name] = dim
    for name in rec.get("ui_layer1", {}):
        if name not in subject["layer1"]:
            dim = dims.get(name)
            if dim is not None:
                subject["layer1"][name] = dim
    return subject


def subject_from_codes(roster: Mapping, codes: Sequence[str],
                       dims: DimSource) -> dict:
    """用名册里已有的角色当 subject(没有包目录时的退化入口)。"""
    layer0: OrderedDict[str, list[int]] = OrderedDict()
    pixelart: OrderedDict[str, list[int]] = OrderedDict()
    layer1: OrderedDict[str, list[int]] = OrderedDict()
    for code in codes:
        layer0.update(character_sheets(roster, code, "main-leader", dims))
        pixelart.update(dims.resolve(list(roster["characters"][code].get("pixelart", {}))))
        layer1.update(character_layer1(roster, code, dims))
    return {"path": None, "roots": None, "code": ",".join(codes),
            "character_id": None, "package_id": None, "package_version": None,
            "png_files_scanned": 0,
            "layer0": layer0, "layer1": layer1, "pixelart": pixelart, "excluded": []}


def resolve_ids(roster: Mapping, ids: Sequence[str]) -> list[str]:
    by_id = {str(r.get("id")): c for c, r in roster["characters"].items() if r.get("id")}
    out, miss = [], []
    for raw in ids:
        code = by_id.get(str(raw).strip())
        if code is None:
            miss.append(str(raw).strip())
        else:
            out.append(code)
    if miss:
        raise RosterError("名册里没有这些角色 ID:%s(用 --pack 指向包目录)" % ", ".join(miss))
    return out


# --------------------------------------------------------------------------
# 评估
# --------------------------------------------------------------------------

def evaluate(subject: Mapping, roster: Mapping, dims: DimSource, *,
             scenarios: Sequence[str] = DEFAULT_SCENARIOS,
             heaviest: int = DEFAULT_HEAVIEST,
             subject_role: str = DEFAULT_SUBJECT_ROLE,
             threshold: float = DEFAULT_THRESHOLD) -> dict:
    subject_l0 = subject_layer0_for_role(subject, subject_role)
    own_l0 = pack_sheets(subject["layer0"])
    own_l1 = pack_sheets(subject["layer1"])

    exclude = {c.strip() for c in str(subject.get("code") or "").split(",") if c.strip()}
    rows = []
    for name in scenarios:
        # 先算**不含本包**的同一间房 —— 没有这条对照就分不清「这一包撑爆的」
        # 和「这间房本来就满了」,而 2026-09-17 的 live 恰好是后者。
        base_sheets, codes = build_room(roster, dims, name, heaviest, {},
                                        subject_role, exclude_codes=exclude)
        baseline = pack_sheets(base_sheets)
        sheets, _ = build_room(roster, dims, name, heaviest, subject_l0,
                               subject_role, exclude_codes=exclude)
        verdict = pack_sheets(sheets)
        verdict.update({"scenario": name,
                        "label": roster["scenarios"][name].get("label", name),
                        "subject_role": subject_role,
                        "heaviest": heaviest,
                        "room_codes": codes,
                        "baseline": baseline,
                        "marginal_px": verdict["px"] - baseline["px"],
                        "marginal_mpx": round((verdict["px"] - baseline["px"]) / 1e6, 6),
                        "marginal_pct": round(100.0 * (verdict["px"] - baseline["px"])
                                              / CAPACITY, 2),
                        "baseline_over": (not baseline["fits"]
                                          or baseline["fill_pct"] > threshold),
                        "over_threshold": (not verdict["fits"]
                                           or verdict["fill_pct"] > threshold)})
        rows.append(verdict)

    worst = max(rows, key=lambda r: (not r["fits"], r["fill_pct"])) if rows else None
    if worst is None:
        status = "OK"
    elif not worst["fits"]:
        status = "OVERFLOW"
    elif worst["fill_pct"] > threshold:
        status = "OVER_THRESHOLD"
    else:
        status = "OK"
    # 归因只看最坏那一间房:它不含本包时就已经越线 = 存量问题,本包只是压上来的最后一根。
    if status == "OK":
        attribution = "none"
    elif worst["baseline_over"]:
        attribution = "pre-existing"
    else:
        attribution = "caused-by-subject"

    return {
        "schema": SCHEMA,
        "status": status,
        "attribution": attribution,
        "exit_code": 0 if status == "OK" else 1,
        "threshold_pct": threshold,
        "atlas": {"width": ATLAS_WIDTH, "height": ATLAS_HEIGHT, "margin": MARGIN,
                  "capacity_px": CAPACITY},
        "dims_source": dims.mode,
        "dim_drift": dims.drift,
        "dim_missing": sorted(set(dims.missing)),
        "roster_generated": roster.get("generated"),
        "subject": {
            "kind": "pack" if subject.get("path") else "codes",
            "path": subject.get("path"),
            "code": subject.get("code"),
            "character_id": subject.get("character_id"),
            "package_id": subject.get("package_id"),
            "package_version": subject.get("package_version"),
            "png_files_scanned": subject.get("png_files_scanned"),
            "role_in_room": subject_role,
            "layer0": own_l0, "layer1": own_l1,
            "layer0_list": [[k, v[0], v[1]] for k, v in subject["layer0"].items()],
            "layer1_list": [[k, v[0], v[1]] for k, v in subject["layer1"].items()],
            "role_layer0_sheets": len(subject_l0),
            "roster_only_sheets": list(subject.get("roster_only_sheets", [])),
            "excluded": list(subject.get("excluded", [])),
        },
        "scenarios": rows,
        "worst": None if worst is None else {
            "scenario": worst["scenario"], "fits": worst["fits"],
            "fill_pct": worst["fill_pct"], "mpx": worst["mpx"],
            "sheets": worst["sheets"], "overflow_at": worst["overflow_at"],
            "baseline_fill_pct": worst["baseline"]["fill_pct"],
            "baseline_fits": worst["baseline"]["fits"],
            "marginal_pct": worst["marginal_pct"]},
        "notes": [
            "layer1 只统计角色自己带的 UI 图(四个战斗槽 × 两个立绘槽),"
            "官方公共件(battle/common/layer1 等)不在统计内,是**增量**不是全房占用。",
            "场景是下界:不含词条 kind 629 拉的 DSL、召唤物、助战第七人、杂兵。",
        ],
    }


def self_check(roster: Mapping) -> dict:
    """重放名册里冻结的黄金编队,核对打包器实现没变。"""
    rows = []
    ok = True
    for golden in roster.get("golden_formations", []):
        got = pack_sheets({k: v for k, v in golden["sheets"].items()})
        want = golden["expect"]
        same = (got["fits"] == want["fits"]
                and got["sheets"] == want["sheets"]
                and abs(got["mpx"] - want["mpx"]) < 1e-6
                and abs(got["fill_pct"] - want["fill_pct"]) < 1e-9
                and (got["used"] == want.get("used") if got["fits"]
                     else got["overflow_at"] == want.get("overflow_at")))
        ok = ok and same
        rows.append({"name": golden["name"], "match": same, "expect": want, "got": got})
    return {"schema": SCHEMA, "status": "OK" if ok else "GOLDEN_MISMATCH",
            "exit_code": 0 if ok else 1, "checks": rows,
            "roster_generated": roster.get("generated")}


# --------------------------------------------------------------------------
# 摘要与打印
# --------------------------------------------------------------------------

def summary(result: Mapping) -> dict:
    """最后一行那份稳定 JSON:去掉逐张清单,只留判决。"""
    subject = result.get("subject", {})
    return {
        "schema": result["schema"],
        "status": result["status"],
        "attribution": result.get("attribution"),
        "exit_code": result["exit_code"],
        "threshold_pct": result.get("threshold_pct"),
        "dims_source": result.get("dims_source"),
        "dim_drift": len(result.get("dim_drift", [])),
        "dim_missing": len(result.get("dim_missing", [])),
        "roster_generated": result.get("roster_generated"),
        "subject": {
            "kind": subject.get("kind"), "code": subject.get("code"),
            "character_id": subject.get("character_id"),
            "package_id": subject.get("package_id"),
            "role_in_room": subject.get("role_in_room"),
            "layer0_sheets": subject.get("layer0", {}).get("sheets"),
            "layer0_mpx": subject.get("layer0", {}).get("mpx"),
            "layer0_pct": subject.get("layer0", {}).get("fill_pct"),
            "layer1_sheets": subject.get("layer1", {}).get("sheets"),
            "layer1_mpx": subject.get("layer1", {}).get("mpx"),
            "layer1_pct": subject.get("layer1", {}).get("fill_pct"),
            "roster_only_sheets": len(subject.get("roster_only_sheets", [])),
        },
        "scenarios": [{"scenario": r["scenario"], "fits": r["fits"],
                       "fill_pct": r["fill_pct"], "mpx": r["mpx"],
                       "sheets": r["sheets"], "overflow_at": r["overflow_at"],
                       "over_threshold": r["over_threshold"],
                       "baseline_fill_pct": r["baseline"]["fill_pct"],
                       "baseline_fits": r["baseline"]["fits"],
                       "baseline_over": r["baseline_over"],
                       "marginal_mpx": r["marginal_mpx"],
                       "marginal_pct": r["marginal_pct"]}
                      for r in result.get("scenarios", [])],
        "worst": result.get("worst"),
    }


def render(result: Mapping, stream) -> None:
    subject = result["subject"]
    label = subject.get("code") or subject.get("path") or "(未命名)"
    print("角色包/角色:%s%s" % (label, ("  id=%s" % subject["character_id"])
                                if subject.get("character_id") else ""), file=stream)
    if subject.get("path"):
        print("  包目录:%s(扫到 %s 张 PNG)"
              % (subject["path"], subject.get("png_files_scanned")), file=stream)
    for layer in ("layer0", "layer1"):
        info = subject[layer]
        print("  %s:%d 张  %.4f Mpx  = 单张 4096² 的 %.2f%%  %s"
              % (layer, info["sheets"], info["mpx"], info["fill_pct"],
                 ("装得下 %dx%d" % tuple(info["used"])) if info["fits"]
                 else "单包就装不下:" + str(info["overflow_at"])), file=stream)
    biggest = sorted(subject["layer0_list"], key=lambda r: -rect_area((r[1], r[2])))[:8]
    for name, width, height in biggest:
        print("      %-62s %4dx%-4d %.4f Mpx"
              % (name[-62:], width, height, rect_area((width, height)) / 1e6), file=stream)
    if subject.get("roster_only_sheets"):
        print("  其中 %d 张是**包没发、但战斗会加载**的官方/既有公共件(按名册闭包补的):%s"
              % (len(subject["roster_only_sheets"]),
                 ", ".join(s.rsplit("/", 1)[-1] for s in subject["roster_only_sheets"][:4])),
              file=stream)
    if subject["excluded"]:
        print("  不进战斗图集的件:%d 个(%s…)"
              % (len(subject["excluded"]), subject["excluded"][0]["reason"]), file=stream)
    print("", file=stream)
    print("场景模拟(三人房 = 本包 + 最重 %d 个自制主位 + 底座;本包按 %s 位算):"
          % (result["scenarios"][0]["heaviest"] if result["scenarios"] else 0,
             subject.get("role_in_room")), file=stream)
    for row in result["scenarios"]:
        base = row["baseline"]
        print("  %-14s 不含本包 n=%3d %7.3f Mpx %6.2f%%  %s"
              % (row["scenario"], base["sheets"], base["mpx"], base["fill_pct"],
                 ("FITS %dx%d" % tuple(base["used"])) if base["fits"]
                 else "OVERFLOW 卡在 " + str(base["overflow_at"])), file=stream)
        print("  %-14s 含本包   n=%3d %7.3f Mpx %6.2f%%  %s   (本包边际 +%.3f Mpx / +%.2f%%)"
              % ("", row["sheets"], row["mpx"], row["fill_pct"],
                 ("FITS %dx%d" % tuple(row["used"])) if row["fits"]
                 else "OVERFLOW 卡在 " + str(row["overflow_at"]),
                 row["marginal_mpx"], row["marginal_pct"]), file=stream)
    if result["scenarios"]:
        print("  同房的 live 角色:%s"
              % ", ".join(result["scenarios"][0]["room_codes"]), file=stream)
    if result.get("dim_drift"):
        print("  [尺寸漂移] %d 张与名册快照不同(已按 store 计)"
              % len(result["dim_drift"]), file=stream)
    if result.get("dim_missing"):
        print("  [量不到] %d 张在 store 与名册里都找不到:%s"
              % (len(result["dim_missing"]), ", ".join(result["dim_missing"][:3])), file=stream)
    print("", file=stream)
    worst = result["worst"]
    if result["status"] == "OK":
        print("[OK] 最坏场景 %.2f%% <= 阈值 %.1f%%。"
              % (worst["fill_pct"], result["threshold_pct"]), file=stream)
        return
    if result["status"] == "OVER_THRESHOLD":
        print("[阻断] 最坏场景 %.2f%% 超过阈值 %.1f%%(还没溢出,但余量不够)。"
              % (worst["fill_pct"], result["threshold_pct"]), file=stream)
    else:
        print("[阻断] 最坏场景**装不下** 4096²:%s" % worst["overflow_at"], file=stream)
        print("       这就是 U_1d93f4;真机表现为房主崩溃、整房解散。", file=stream)
        print("       报出来的那一张只是 MaxRects 碎片化之后**恰好放不进去的那一块**,"
              "不代表它有罪 —— 真正的因子是总量与张数。", file=stream)
    if result["attribution"] == "pre-existing":
        print("       归因:**不是这一包的锅** —— 不含本包的同一间房已经是 %.2f%%%s。"
              % (worst["baseline_fill_pct"], "" if worst["baseline_fits"] else "(且已溢出)"),
              file=stream)
        print("       本包边际只有 +%.2f%%。要降总量得先裁最重的那几个 live 角色"
              "(审计 S1:seris_dragon_king 一个人 17.7%%)。" % worst["marginal_pct"],
              file=stream)
    else:
        print("       归因:**本包造成的** —— 不含本包时 %.2f%% 还在阈值内,"
              "加上本包的 +%.2f%% 才越线。"
              % (worst["baseline_fill_pct"], worst["marginal_pct"]), file=stream)
    print("       作者确认可以放行时:发布脚本加 -SkipAtlasCheck,"
          "或本工具 --threshold 调高。", file=stream)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="战斗图集(layer0/layer1)预算预检 —— 发布前拦 U_1d93f4")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--pack", help="角色包目录(workspace / package / roots 都认)")
    src.add_argument("--codes", help="逗号分隔的 code_name(从名册取清单)")
    src.add_argument("--ids", help="逗号分隔的角色 ID(从名册反查 code_name)")
    src.add_argument("--sheet-set", help="直接给一份 {精灵表: [w,h]} 的 JSON,只装箱")
    src.add_argument("--self-check", action="store_true",
                     help="重放名册里冻结的黄金编队,核对打包器实现")
    parser.add_argument("--scenario", default=",".join(DEFAULT_SCENARIOS),
                        help="逗号分隔的场景名(默认 %s)" % ",".join(DEFAULT_SCENARIOS))
    parser.add_argument("--heaviest", type=int, default=DEFAULT_HEAVIEST,
                        help="同房的 live 最重自制角色个数(默认 %d)" % DEFAULT_HEAVIEST)
    parser.add_argument("--subject-role", choices=SUBJECT_ROLES,
                        default=DEFAULT_SUBJECT_ROLE,
                        help="本包在房里按哪个位置算(默认 %s)" % DEFAULT_SUBJECT_ROLE)
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD,
                        help="占用率阈值,超了非 0 退出(默认 %.1f)" % DEFAULT_THRESHOLD)
    parser.add_argument("--dims", choices=("store", "roster"), default="store",
                        help="尺寸来源:store=现量(默认),roster=名册冻结快照")
    parser.add_argument("--roster", help="名册路径(默认 mod-tools/atlas_budget_roster.json)")
    parser.add_argument("--json", dest="json_out", help="把完整结果另存成 JSON")
    parser.add_argument("--quiet", action="store_true", help="只输出最后那一行 JSON")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    # --quiet 把人读的那部分丢进黑洞,只留最后一行 JSON。
    stream = io.StringIO() if args.quiet else sys.stdout

    try:
        roster = load_roster(args.roster)
        if args.self_check:
            result = self_check(roster)
            if not args.quiet:
                for row in result["checks"]:
                    print("%-52s %s" % (row["name"], "一致" if row["match"] else "不一致"),
                          file=stream)
                    if not row["match"]:
                        print("   期望 %s" % json.dumps(row["expect"], ensure_ascii=False),
                              file=stream)
                        print("   实得 %s" % json.dumps(row["got"], ensure_ascii=False),
                              file=stream)
            payload = result
            line = {k: v for k, v in result.items() if k != "checks"}
            line["checks"] = [{"name": r["name"], "match": r["match"]}
                              for r in result["checks"]]
        elif args.sheet_set:
            raw = json.loads(Path(args.sheet_set).read_text(encoding="utf-8"))
            verdict = pack_sheets({k: v for k, v in raw.items()})
            over = (not verdict["fits"]) or verdict["fill_pct"] > args.threshold
            payload = {"schema": SCHEMA,
                       "status": "OK" if not over else
                                 ("OVERFLOW" if not verdict["fits"] else "OVER_THRESHOLD"),
                       "exit_code": 0 if not over else 1,
                       "threshold_pct": args.threshold, "sheet_set": verdict}
            if not args.quiet:
                print("%d 张 %.3f Mpx %.2f%%  %s"
                      % (verdict["sheets"], verdict["mpx"], verdict["fill_pct"],
                         ("FITS %dx%d" % tuple(verdict["used"])) if verdict["fits"]
                         else "OVERFLOW " + str(verdict["overflow_at"])), file=stream)
            line = payload
        else:
            if args.pack:
                subject = read_pack(args.pack)
                # 包里那份 PNG 优先(正要发布的就是它),再补上包没发但会加载的官方公共件
                dims = DimSource(roster, args.dims, overrides=dict(subject["layer0"]))
                merge_roster_closure(subject, roster, dims)
            else:
                dims = DimSource(roster, args.dims)
                codes = ([c.strip() for c in args.codes.split(",") if c.strip()]
                         if args.codes else
                         resolve_ids(roster, [x for x in args.ids.split(",") if x.strip()]))
                subject = subject_from_codes(roster, codes, dims)
            scenarios = [s.strip() for s in args.scenario.split(",") if s.strip()]
            payload = evaluate(subject, roster, dims, scenarios=scenarios,
                               heaviest=args.heaviest, subject_role=args.subject_role,
                               threshold=args.threshold)
            if not args.quiet:
                render(payload, stream)
            line = summary(payload)
    except RosterError as exc:
        print("[错误] %s" % exc, file=sys.stderr)
        print(json.dumps({"schema": SCHEMA, "status": "ERROR", "exit_code": 2,
                          "error": str(exc)}, ensure_ascii=False, sort_keys=True))
        return 2

    if args.json_out:
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(
            json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(line, ensure_ascii=False, sort_keys=True))
    return int(payload["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
