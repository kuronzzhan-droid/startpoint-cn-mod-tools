# -*- coding: utf-8 -*-
'武器觉醒与新掉落：只读 live 的数据构建器 + 分边暂存（stage-e1 / stage-e2 / stage-e3）。\n\n设计稿 ``${WF_ROOT}/out/武器觉醒与新掉落-20260928/设计.md``：§2.5 觉醒数据、§4.2 分工、§5 物品/商店/价格、\n§5.6 本构建器、§6.4–§6.6 图标与图集、§7 发布顺序。作者 0928 定稿：诅咒武器 5910101–5910129 与 PARADOX\n5920001 只能用重复本体或「禁忌星铁」10000311 觉醒（1 个 = 1 级，锻造石 25/级照旧）；新掉落「深界王币」\n10000310（五重每局 10–15，由五重线在 rewards.ts 实现，本线不改）；五重商店 032 = 王币×1、033 = 王币×10、\n新增 034 = 王币×500 → 禁忌星铁×1；旧囤货不转换。\n\n## 三条边（发布顺序 E1 → E2 → 五重线掉落 → E3，一条边一个子命令）\n\nE1 图标文件（``stage-e1``）\n  ``item_icon/sprite_sheet.png`` 与 ``item_icon/sprite_sheet.atlas.amf3.deflate``（**必须同一条边**），\n  以及各道具 c3 独立 PNG。图集只追加新名字的子纹理（本线自有名字允许原位换像素），旧条目逐键、\n  旧像素逐字节不动，不扩画布；c4 = c3×2 最近邻。源图与交付合同在 ``mod-tools/assets/weapon-awaken/``\n  （图标单元的 ``build_icons.py`` 生成 ``icons/*.png`` 与 ``manifest.json``）：每张图的逻辑路径、c3/c4\n  解码后 RGBA sha256 必须与 manifest 逐项一致，否则拒绝。PARADOX 两件（设计 §6.4 归我方）用重画版：\n  c3 换新逻辑名 ``*_v2``，c4 是 ``item_icon/materials/mod/paradox/*`` 专属子纹理。\n  **作者确认预览**（设计 §6.5 第 3 步、§7 第 2 步）登记在 ``approved.json``（``approve`` 子命令写，\n  记每张图的 c3 RGBA sha256）；要发的图没登记或像素已变 → blocked「待作者确认预览」。\nE2 道具与觉醒数据（``stage-e2``）\n  ``master/item/item.orderedmap``：新行 10000310/10000311（23 列；禁忌星铁 c6=1，**不能是 6**），\n  已上线新图的 10000144–147（c3/c4 改指 _v2）与 10000301/302（c3/c4 **同一条边**改指重画版）；\n  ``master/reward/event/additional_reward.orderedmap`` 的 ``[590010000][5]``（嵌套表，只加内层键 5）；\n  ``master/string/custom_ability_string.orderedmap`` 30 条 ``awakening_material_<装备ID>`` = ``10000311``；\n  ``master/string/ui_string.orderedmap`` 两键「星铁钢」→「觉醒素材」。\n  服务端 ``item_ids/item_lookup/item_sale`` 追加两道具；``equipment_awakening_material.json`` 的\n  ``materialByEquipment`` 与 CAS 键逐项对齐，``rarityOverrides`` 按 live 装备表 c11 重建（凡 c11 ≠ floor(id/1e6)\n  都要登记，多余的删掉；文件由服务端白名单单元创建，这里只做键级拼接）。``check`` 同样跑这两道门禁。\nE3 五重商店（``stage-e3``）\n  ``master/shop/boss_coin_shop.orderedmap`` 032/033 改价、新增 034（行由 ``wf_weapon_gacha`` 的同一组函数\n  生成，两边永远一致）；服务端 ``boss_coin_shop.json["99"]`` 与 ``boss_coin_shop_item_category_map.json``。\n  前提含五重掉落已发王币（``wf_weapon_gacha.five_boss_drop_live``：src/ 与 out/multi/five-boss 都有 10000310，\n  或核实后传 ``--drop-live``），未上线 = blocked，``wf_weapon_gacha`` 同样暂缓 032–034；\n  ``--stage-node-c9`` 时另改 ``boss_battle_stage_node[1][99]`` c9 10000146→10000310（须五重线同意）。\n\nE4 作者 0928 晚修订（``stage-e4``，E1–E3 上线之后）\n  E1/E2/E3 按 live 重算的差集合成一条边，外加武器扭蛋注意事项正文（``wf_weapon_gacha`` 的 rich text）：\n  禁忌星铁图回到紫灰锭（37a2d165 的像素，非彩虹件；图集子纹理原位换像素 + c3 独立 PNG）；\n  ``custom_ability_string`` 的 ``rarity_frame_override_<星铁 c3>`` = PARADOX Lv200 蓝金框（客户端补丁换 ★5 彩虹底框）；\n  「PARADOX」只留在武器名里，其余文案写「悖论武器」（禁忌星铁说明、034 说明、扭蛋说明）；\n  034 = 王币 ×500 + 五王心核 ×5 + 深渊觉醒核 ×10，每人限购 60（c28/c29 与服务端 stock）；\n  990099002 深界连战凭证 c13 4 → 5（金框 → 彩虹框，与道具 c17 一致）。\n\n## 纪律\n\n1. **只读 live**：从不写 store、``.cdn``、``assets/``，不调用 wf_publish。暂存只写\n   ``<workdir>/stage/{common,server}/**`` 与计划文件（合同同 ``wf_weapon_gacha``：tables/files/server/deleted，\n   每项带 live_sha256；服务端 JSON 全部文本级拼接，别人的 WIP 逐字节不动）。\n2. **幂等**：构建目标态，与 live 逐键比较；已上线后再跑得空计划。\n3. **顺序门禁**：一条边的前提（E1 需作者确认预览；E2 需 E1 的图已上线；E3 需 E2 的道具行、E1 的商品图\n   与五重掉落）——\n   - live 已满足 → ``plan.json``（唯一可 apply 的计划）；\n   - 只能靠 ``--after <前一条边 workdir>`` 满足 → ``plan.pending.json``（附 requires：前一条边落地后的 sha），\n     前一条边上线后重跑本边才得到 ``plan.json``；\n   - 不满足（例如图还没画）→ ``plan.blocked.json``（附 blocked 原因），只供审阅。\n   ``problems``（违反合同）非空时一律拒绝，什么都不写。\n\n用法::\n\n    python mod-tools/wf_weapon_awaken.py check [--art-dir DIR] [--drop-live]\n    python mod-tools/wf_weapon_awaken.py approve --by 作者 --evidence "<作者原话/时间>" [--art-dir DIR] [--only STEM ...]\n    python mod-tools/wf_weapon_awaken.py stage-e1 <workdir> [--art-dir DIR]\n    python mod-tools/wf_weapon_awaken.py stage-e2 <workdir> [--after <E1 workdir>]\n    python mod-tools/wf_weapon_awaken.py stage-e3 <workdir> [--after <E1 workdir> --after <E2 workdir>] [--stage-node-c9]\n        [--drop-live]\n    python mod-tools/wf_weapon_awaken.py stage-e4 <workdir> [--art-dir DIR] [--drop-live]\n\n``approve`` 只在作者看过预览并确认后运行：它把当前通过门禁、且与 manifest 一致的图的 c3 sha 写进\n``approved.json``；图再改就要重新确认。\n\n退出码：0 = plan.json，3 = plan.pending.json，4 = plan.blocked.json，2 = problems 拒绝。\n'
from __future__ import annotations

import argparse
import colorsys
import copy
import hashlib
import io
import json
import re
import shutil
import sys
import zlib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
if str(TOOLS) not in sys.path:
    pass  # Imports resolve from this checkout/package, not external source copies.

import wf_assets as assets  # noqa: E402
import wf_dsl  # noqa: E402
import wf_weapon_gacha as G  # noqa: E402
from wf_weapon_gacha import codec, core  # noqa: E402

# ---------------------------------------------------------------------------
# 合同常量（改口径只改这里）
# ---------------------------------------------------------------------------

KING_COIN_ID = G.KING_COIN_ID                       # 10000310 深界王币
STAR_STEEL_ID = G.STAR_STEEL_ID                     # 10000311 禁忌星铁
RESTRICTED_EQUIPMENT = tuple(G.CURSED) + (G.PARADOX,)   # 29 把诅咒武器 + PARADOX（分档键 5921001–5923001 不加）
CAS_PREFIX = "awakening_material_"
AWAKENING_EFFECT = "6"                              # item c6 EquipmentAwakingCrystal
OFFICIAL_AWAKENING_ITEMS = {"12001": ("4", "true"), "12002": ("5", "false")}   # live c6=6 只有这两行（c10, c11）
EQUIPMENT_RARITY_COL = 11                           # equipment c11 = 客户端稀有度（EquipmentValues.as:105-111）
SERVER_RARITIES = range(1, 6)                       # 服务端 parseAwakeningMaterialRules 只收 1–5，越界服务起不来
ITEM_START = "2000-01-01 00:00:00"                  # 服务端时间钉在 2025-08-05，起点必须更早

ITEM_LOGICAL = G.ITEM_LOGICAL
EQUIPMENT_LOGICAL = G.EQUIPMENT_LOGICAL
SHOP_LOGICAL = G.SHOP_LOGICAL
CAS_LOGICAL = "master/string/custom_ability_string.orderedmap"
UI_LOGICAL = "master/string/ui_string.orderedmap"
REWARD_LOGICAL = "master/reward/event/additional_reward.orderedmap"
NODE_LOGICAL = "master/quest/boss_battle_stage_node.orderedmap"
ATLAS_PNG = "item_icon/sprite_sheet.png"
ATLAS_MAP = "item_icon/sprite_sheet.atlas.amf3.deflate"

REWARD_GROUP = "590010000"                          # 五重结算展示组（不在五重 v2 自有键里；590010001 会被它整组重写）
REWARD_INDEX = "5"
REWARD_ROW = ["five_boss_king_coin", "0", str(KING_COIN_ID), "1", "1"]
REWARD_EXPECTED = {"1": "10000144", "2": "10000145", "3": "10000146", "4": "10000147"}   # 内层 1–4 的 c2（形状核对）

UI_RENAMES = {   # 键: (live 官方值, 目标值)；只改这两键（设计 §2.5）
    "equipment_awaking_crystal": ("星铁钢", "觉醒素材"),
    "equipment_list_not_upgradable_reason_not_enough_awaking_items":
        ("无可用于此装备的重复数或星铁钢", "无可用于此装备的重复数或觉醒素材"),
}

#: 缩略图底框换图（作者 0928「保持那个和现在的200级悖论武器品质底色」）：禁忌星铁的 ★5 彩虹底框换成 PARADOX Lv200 的
#: 蓝金框（144×144，已随 PARADOX Lv200 上线；= wf_paradox_weapon.FRAME_BLUEGOLD）。客户端补丁按缩略图**显示的图标路径**
#: 查 ``rarity_frame_override_<图标路径>``：道具缩略图 = item c3，五重商店 034 的商品图 c12 也是同一路径，一键两处。
#: 行为型：未装补丁的客户端不读这个键，照旧显示 ★5 彩虹底框、不崩。
RARITY_FRAME_PREFIX = "rarity_frame_override_"      # client-patch/item-rarity-frame-override rules.PREFIX
RARITY_FRAME_CAP = "item-rarity-frame-override-v1"  # 同上 rules.CAPABILITY（cosmetic：缺补丁只是不换框）
RARITY_FRAME_BLUEGOLD = "item/equipment/mod/paradox/paradox_frame_bluegold"
RARITY_FRAME_KEYS = {RARITY_FRAME_PREFIX + G.STAR_STEEL_THUMB: RARITY_FRAME_BLUEGOLD}

#: 五重商店里不归本线的商品只修底框（c13 稀有度 = 缩略图底框）：键 → (live 旧值, 目标值, 奖励道具)。
#: 作者 0928「连战凭证也有底图变成金色的情况，应该是彩色」：990099002 深界连战凭证 c13=4（金框），道具 10000143 c17=5（彩虹）。
SHOP_FRAME_COL = 13
SHOP_FRAME_FIXES = {"990099002": ("4", "5", "10000143")}
ITEM_RARITY_COL = 17

NODE_PATH = ("1", "99")                             # boss_battle_stage_node[1][99]
NODE_HOLDING_COL = 9                                # 五重页/多人房/商店头部显示持有数的第 4 格
NODE_HOLDING_OLD = "10000146"                       # 五重决战之证（终身 1 个）

SERVER_ITEM_IDS = G.SERVER_ITEM_IDS
SERVER_ITEM_LOOKUP = G.SERVER_ITEM_LOOKUP
SERVER_ITEM_SALE = G.SERVER_ITEM_SALE
SERVER_MATERIAL = "equipment_awakening_material.json"
SERVER_SHOP = G.SERVER_SHOP
SERVER_SHOP_MAP = G.SERVER_SHOP_MAP

ART_DIR = TOOLS / "assets" / "weapon-awaken"
MANIFEST_NAME = "manifest.json"                     # 图标单元 build_icons.py 生成的交付合同（勿手改）
APPROVAL_NAME = "approved.json"                     # 作者确认预览的登记（approve 子命令写）
PLAN_NAMES = {"ready": "plan.json", "pending": "plan.pending.json", "blocked": "plan.blocked.json"}
EXIT_CODES = {"ready": 0, "pending": 3, "blocked": 4}


@dataclass(frozen=True)
class Icon:
    item_id: str
    stem: str               # 源图文件名（不含 .png）= manifest 的 key
    c3: str                 # 道具 c3：独立 PNG 的逻辑路径（不含 .png）
    c4: str                 # item_icon 图集子纹理名（新名字，只追加）
    bbox_min: int           # 包围盒长边下限（设计 §6.2：★3≈14、★4≈16、★5 与代币 19）
    required: bool          # 新道具行引用它 ⇒ E2 的前提；False = 重画件，有图才改指
    rainbow: bool = False   # ★5 彩虹渐变类（母本 ★5 星铁钢）：免色数、描边集中度与描边色相门禁


def _c4_of(c3: str) -> str:
    """c4 与 c3 同名（item/… → item_icon/…），设计 §6.4「同名」。"""
    if not c3.startswith("item/"):
        raise ValueError(c3)
    return "item_icon/" + c3[len("item/"):]


def _icon(item_id, stem, c3, bbox_min, required, **kw) -> Icon:
    return Icon(item_id, stem, c3, _c4_of(c3), bbox_min, required, **kw)


FIVE_BOSS_DIR = "item/materials/mod/five_boss"
PARADOX_DIR = "materials/mod/paradox"
# 逻辑路径 = 设计 §5.2/§6.4（王币 five_boss/、禁忌星铁 cursed/），与图标单元 manifest.json 逐项核对。
ICONS = (
    _icon("10000310", "king_coin", f"{FIVE_BOSS_DIR}/king_coin", 19, True),
    # 禁忌星铁按暗紫锭画（≤17 色、描边压暗），不是彩虹件，门禁全口径适用。作者 0928 撤回彩虹重画
    # （「禁忌星铁上版那个紫灰挺好的」，回到 37a2d165 的像素）；缩略图底框改走 RARITY_FRAME_KEYS 的蓝金框（客户端补丁）。
    _icon("10000311", "forbidden_star_steel", G.STAR_STEEL_THUMB, 19, True),
    _icon("10000144", "deathbringer_blueprint_v2", f"{FIVE_BOSS_DIR}/deathbringer_blueprint_v2", 14, False),
    _icon("10000145", "deep_crystal_v2", f"{FIVE_BOSS_DIR}/deep_crystal_v2", 16, False),
    _icon("10000146", "fivefold_clear_badge_v2", f"{FIVE_BOSS_DIR}/fivefold_clear_badge_v2", 14, False),
    _icon("10000147", "five_king_core_v2", f"{FIVE_BOSS_DIR}/five_king_core_v2", 19, False),
    # PARADOX 重画版（设计 §6.3/§6.4）：c3 用新逻辑名 _v2——旧名仍是 wf_paradox_weapon MATERIALS 的源图，原位覆盖
    # 会与它互相改回；c4 用 paradox 自有子纹理（不再借五重的）。E2 同一条边一起改指 c3/c4。
    Icon("10000301", "contradiction_crystal", f"item/{PARADOX_DIR}/contradiction_crystal_v2",
         f"item_icon/{PARADOX_DIR}/contradiction_crystal", 16, False),
    Icon("10000302", "paradox_core", f"item/{PARADOX_DIR}/paradox_core_v2",
         f"item_icon/{PARADOX_DIR}/paradox_core", 19, False),
)
ICON_BY_ITEM = {i.item_id: i for i in ICONS}
OWNED_ATLAS_NAMES = frozenset(i.c4 for i in ICONS)
PARADOX_TOOL = TOOLS / "wf_paradox_weapon.py"       # 只读：它的 MATERIALS 是否已同步到重画版逻辑路径

# §6.2/§6.5 图标门禁（口径同图标单元 build_icons.gate：描边只看最大 8 连通块，角上十字星点不算描边）
ICON_SIZE = (20, 20)
SPECKLE_MAX = 0.10          # 孤立杂色像素占比（官方中位约 0.05）
COLORS_MAX = 17             # 非彩虹件不透明色数
OUTLINE_TOP2_MIN = 0.9      # 描边（主体贴透明的外圈像素）前两种颜色占比
OUTLINE_MIN_CHANNEL = 40    # 描边主色的最大通道 < 40 视为近纯黑（官方最暗 (45,44,29)；我方旧图 (1,0,36)）
OUTLINE_SAT_MIN = 0.4       # 描边 = 主色相压暗：要有彩度（灰描边不合格；比官方严，官方银币/灰铁是灰描边）
OUTLINE_VAL_RANGE = (0.2, 0.5)    # 明度（设计 §6.2「约 25–45%」；官方有彩描边最暗 0.25、交付件最暗 0.24；
                                  # 比图标单元的 0.15 严：旧 PARADOX 的 (24,24,42) 明度 0.16 要拦下）
OUTLINE_HUE_TOL = 45        # 描边色相与主体有彩像素的色相差上限（度）
OUTLINE_HUE_SHARE_MIN = 0.2  # 主体有彩像素里色相落在描边 ±45° 内的占比下限（非彩虹件；交付件最低 0.25）
HUE_SAMPLE = (0.25, 0.2)    # 「有彩像素」：饱和度 ≥0.25 且明度 ≥0.2（高光白、暗部黑不算）
ATLAS_GAP = 2               # 子纹理间距（与五重 v2 相同）


def item_rows() -> dict:
    """两行新道具（23 列，设计 §5.2；c3/c4 取 ICONS）。"""
    coin, steel = ICON_BY_ITEM[str(KING_COIN_ID)], ICON_BY_ITEM[str(STAR_STEEL_ID)]
    return {
        str(KING_COIN_ID): [
            "mod_five_boss_king_coin", str(KING_COIN_ID), "深界王币", coin.c3, coin.c4,
            "镌刻着五王纹章的古币。可在五重决战商店兑换武器扭蛋券与禁忌星铁。",
            "15", "", "", "", "", "", "", "",          # c6=15 TradeItem（同官方领主币）；c7–c13 空
            "6", "(None)", "1", "4", "999999",           # c14=6 交换道具页；c15 非银币；c16 售价 1；★4；上限 999999
            ITEM_START, "(None)", "false", ""],          # c21=false 不可出售（1 个 = 1 次单抽）
        str(STAR_STEEL_ID): [
            "mod_forbidden_star_steel", str(STAR_STEEL_ID), "禁忌星铁", steel.c3, steel.c4,
            f"只回应诅咒与悖论之力的星铁。可代替本体突破诅咒武器与{G.PARADOX_CLASS}。",
            "1", "", "", "", "", "", "", "",           # c6=1（绝不能是 6：会被原生逻辑提供给所有 ★5）；c10/c11 空
            "2", "(None)", "50", "5", "9999",            # c14=2 与星铁钢同页；★5；上限 9999
            ITEM_START, "(None)", "false", ""],
    }


def server_item_sale(row: list) -> dict:
    return {"category": int(row[14]), "sale_price": int(row[16]), "sellable": row[21] == "true"}


def cas_rows() -> dict:
    """30 条 ``awakening_material_<装备ID>`` = ``10000311``（单列行，补丁读 row.string）。"""
    return {f"{CAS_PREFIX}{eid}": [str(STAR_STEEL_ID)] for eid in RESTRICTED_EQUIPMENT}


def material_map() -> dict:
    """服务端 ``materialByEquipment``：与 CAS 键同源。"""
    return {str(eid): STAR_STEEL_ID for eid in RESTRICTED_EQUIPMENT}


def rarity_frame_rows() -> dict:
    """``rarity_frame_override_<缩略图图标路径>`` = 框底图路径（单列行，补丁读 row.string）。"""
    return {key: [value] for key, value in RARITY_FRAME_KEYS.items()}


def rarity_overrides(equipment: dict) -> tuple:
    """服务端 ``rarityOverrides``：装备表里 c11 ≠ floor(id/1e6) 的每一行 → c11。-> (映射, problems)。

    服务端 ``resolveEquipmentRarity`` 先查这张表、查不到才按 ID 百万位算；漏登记一把就会让它与客户端给出的
    官方觉醒晶对不上（例：深渊 80001xx 按 ID 算成 8 → 12002 被拒）。c11 不是整数、或需要登记却不在 1–5，
    都算违反合同（后者写进去服务会启动失败）。"""
    out: dict = {}
    problems: list = []
    for key in sorted(equipment, key=lambda k: (not k.isdigit(), int(k) if k.isdigit() else 0, k)):
        cells = equipment[key]
        raw = cells[EQUIPMENT_RARITY_COL] if len(cells) > EQUIPMENT_RARITY_COL else ""
        if not key.isdigit() or not re.fullmatch(r"-?[0-9]+", raw):
            problems.append(f"装备 {key} 的键或 c{EQUIPMENT_RARITY_COL} 不是整数: {raw!r}")
            continue
        rarity = int(raw)
        if rarity == int(key) // 1_000_000:
            continue
        if rarity not in SERVER_RARITIES:
            problems.append(f"装备 {key} c{EQUIPMENT_RARITY_COL}={rarity} 须登记 rarityOverrides，但服务端只收 1–5")
            continue
        out[key] = rarity
    return out, problems


# ---------------------------------------------------------------------------
# 前一条边的叠加视图（只用于前提判断，从不作为暂存基底）
# ---------------------------------------------------------------------------

class Overlay:
    """``--after`` 目录里前一条边的暂存：{逻辑路径: 暂存字节}（校验 plan 里的 staged_sha256）。"""

    def __init__(self, dirs: Iterable = ()):
        self.files: dict = {}
        self.sha: dict = {}
        self.sources: list = []
        for d in dirs:
            d = Path(d)
            found = [(status, d / name) for status, name in PLAN_NAMES.items() if (d / name).is_file()]
            if len(found) != 1:
                raise SystemExit(f"--after {d}: 须恰好有一个计划文件 {sorted(PLAN_NAMES.values())}，实际 {len(found)}")
            status, path = found[0]
            plan = json.loads(path.read_text(encoding="utf-8"))
            for logical, info in list(plan["tables"].items()) + list(plan["files"].items()):
                if logical.startswith(G.MEDIUM_PREFIX):
                    continue
                raw = (d / "stage" / "common" / logical).read_bytes()
                if G.sha256(raw) != info["staged_sha256"]:
                    raise SystemExit(f"--after {d}: {logical} 与计划里的 staged_sha256 不符")
                self.files[logical] = raw
                self.sha[logical] = info["staged_sha256"]
            self.sources.append({"dir": str(d), "edge": plan.get("edge"), "status": status})

    @property
    def blocked_sources(self) -> list:
        return [s for s in self.sources if s["status"] == "blocked"]


class View:
    """live + 叠加。``raw``/``flat``/``atlas_names``/``has_file`` 同时报告是不是靠叠加才满足。"""

    def __init__(self, live: G.Live, overlay: Overlay | None = None):
        self.live = live
        self.overlay = overlay or Overlay()
        self._flat: dict = {}

    def raw(self, logical: str) -> bytes | None:
        if logical in self.overlay.files:
            return self.overlay.files[logical]
        return self.live.raw(logical)

    def flat(self, logical: str) -> dict:
        if logical not in self._flat:
            raw = self.raw(logical)
            self._flat[logical] = {} if raw is None else flat_rows(raw)
        return self._flat[logical]

    def atlas_names(self) -> set:
        raw = self.raw(ATLAS_MAP)
        return set() if raw is None else {str(e["n"]) for e in decode_atlas(raw)}

    def has_file(self, logical: str) -> bool:
        return self.raw(logical) is not None


class Requirements:
    """本边依赖的前提；``conditional`` = 有前提只是靠 --after 叠加才满足。"""

    def __init__(self):
        self.sha256: dict = {}
        self.atlas_names: set = set()
        self.files_present: set = set()
        self.table_keys: dict = {}
        self.conditional = False

    def via_overlay(self, view: View, logicals: Iterable[str]) -> None:
        self.conditional = True
        for logical in logicals:
            if logical in view.overlay.sha:
                self.sha256[logical] = view.overlay.sha[logical]

    def as_json(self) -> dict:
        return {"sha256": dict(sorted(self.sha256.items())), "atlas_names": sorted(self.atlas_names),
                "files_present": sorted(self.files_present),
                "table_keys": {k: sorted(v) for k, v in sorted(self.table_keys.items())}}


# ---------------------------------------------------------------------------
# 表读写小件
# ---------------------------------------------------------------------------

def flat_rows(raw: bytes) -> dict:
    out = {}
    for key, blob in codec.unpack(raw).items():
        text = zlib.decompress(blob).decode("utf-8") if blob else ""
        parsed = core.read_csv_lines(text)
        out[key] = parsed[0] if parsed else []
    return out


def repack_inner(raw: bytes, outer: str, upsert: dict) -> tuple:
    """嵌套表只改一个外层键下的内层键：-> (新字节, changed 外层键列表)。

    内层 upsert 值是整行 CSV 文本；与 live 一致的内层键跳过；其余内层行、其余外层行字节原样。"""
    rows = codec.unpack(raw)
    if outer not in rows:
        raise KeyError(f"外层键 {outer} 不存在")
    inner = codec.unpack(rows[outer])
    old_inner = dict(inner)
    touched = []
    for key, text in upsert.items():
        if key in inner and inner[key] and zlib.decompress(inner[key]).decode("utf-8") == text:
            continue
        inner[key] = zlib.compress(text.encode("utf-8"))
        touched.append(key)
    if not touched:
        return raw, []
    new_rows = dict(rows)
    new_rows[outer] = codec.pack(inner)
    staged = codec.pack(new_rows)
    back = codec.unpack(staged)
    if list(back) != list(rows) or any(back[k] != rows[k] for k in rows if k != outer):
        raise AssertionError("嵌套表重打包后其他外层键变了")
    back_inner = codec.unpack(back[outer])
    if [k for k in back_inner if k in old_inner] != list(old_inner) \
            or any(back_inner[k] != old_inner[k] for k in old_inner if k not in touched):
        raise AssertionError("嵌套表重打包后其他内层键变了")
    return staged, [outer]


def decode_atlas(raw: bytes) -> list:
    return wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]


def encode_atlas(entries: list) -> bytes:
    amf = wf_dsl.encode_amf3(entries)
    if wf_dsl.parse_dsl(amf)["tree"] != entries:
        raise AssertionError("图集 AMF3 往返不一致")
    comp = zlib.compressobj(9, zlib.DEFLATED, -15)
    return comp.compress(amf) + comp.flush()


def open_png(raw: bytes):
    from PIL import Image

    image = Image.open(io.BytesIO(assets.png_decode(raw)))
    image.load()
    return image.convert("RGBA")


def store_png(image) -> bytes:
    buf = io.BytesIO()
    image.convert("RGBA").save(buf, format="PNG", optimize=True)
    return assets.png_encode(buf.getvalue())


def upscale2(image):
    from PIL import Image

    return image.resize((image.size[0] * 2, image.size[1] * 2), Image.NEAREST)


# ---------------------------------------------------------------------------
# 图标门禁（设计 §6.2/§6.5；孤立杂色的算法同 scratch/metrics.py，描边口径同图标单元 build_icons.metrics）
# ---------------------------------------------------------------------------

_N4 = ((1, 0), (-1, 0), (0, 1), (0, -1))


def _main_component(opaque: set) -> set:
    """最大的 8 连通不透明块（角上 1–3 像素的十字星点是独立小块，设计 §6.2 允许，不算描边）。"""
    best: set = set()
    seen: set = set()
    for start in sorted(opaque):
        if start in seen:
            continue
        stack, comp = [start], set()
        seen.add(start)
        while stack:
            x, y = stack.pop()
            comp.add((x, y))
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    q = (x + dx, y + dy)
                    if q in opaque and q not in seen:
                        seen.add(q)
                        stack.append(q)
        if len(comp) > len(best):
            best = comp
    return best


def _hsv(rgb) -> tuple:
    return colorsys.rgb_to_hsv(*(v / 255 for v in rgb[:3]))


def _hue_distance(a: float, b: float) -> float:
    d = abs(a - b) % 1.0
    return min(d, 1.0 - d) * 360


def icon_metrics(image) -> dict:
    rgba = image.convert("RGBA")
    width, height = rgba.size
    px = rgba.load()
    alphas = sorted({px[x, y][3] for y in range(height) for x in range(width)})
    opaque = {(x, y) for y in range(height) for x in range(width) if px[x, y][3] > 0}
    out = {"size": (width, height), "alphas": alphas}
    if not opaque:
        return {**out, "empty": True}
    xs = [p[0] for p in opaque]
    ys = [p[1] for p in opaque]
    main = _main_component(opaque)
    border = [p for p in main if any((p[0] + dx, p[1] + dy) not in opaque for dx, dy in _N4)]
    border_set = set(border)
    counts = Counter(px[p][:3] for p in border)
    top = counts.most_common(2)
    outline = top[0][0]
    hue, sat, val = _hsv(outline)
    sample = [h for h in (_hsv(px[p]) for p in main if p not in border_set)
              if h[1] >= HUE_SAMPLE[0] and h[2] >= HUE_SAMPLE[1]]
    near = sum(1 for h in sample if _hue_distance(h[0], hue) <= OUTLINE_HUE_TOL)
    speckle = 0
    for x, y in opaque:
        c = px[x, y]
        nbs = [px[x + dx, y + dy] for dx, dy in _N4 if (x + dx, y + dy) in opaque]
        if len(nbs) >= 3 and all(sum(abs(a - b) for a, b in zip(c[:3], n[:3])) > 60 for n in nbs):
            speckle += 1
    return {**out, "empty": False,
            "bbox": (max(xs) - min(xs) + 1, max(ys) - min(ys) + 1),
            "colors": len({px[p][:3] for p in opaque}),
            "outline_color": outline,
            "outline_top2": round(sum(c for _, c in top) / len(border), 3),
            "outline_sat": round(sat, 2),
            "outline_val": round(val, 2),
            "outline_hue_share": round(near / len(sample), 2) if sample else None,
            "speckle": round(speckle / len(opaque), 3)}


def icon_problems(icon: Icon, m: dict) -> list:
    name = f"图标 {icon.stem}"
    problems = []
    if tuple(m["size"]) != ICON_SIZE:
        problems.append(f"{name}: 尺寸 {m['size']} != {ICON_SIZE}")
    if not set(m["alphas"]) <= {0, 255}:
        problems.append(f"{name}: alpha 只允许 0/255，实际有 {[a for a in m['alphas'] if a not in (0, 255)][:5]}")
    if m.get("empty"):
        return problems + [f"{name}: 全透明"]
    if max(m["bbox"]) < icon.bbox_min:
        problems.append(f"{name}: 包围盒 {m['bbox']} 长边 < {icon.bbox_min}")
    if m["speckle"] > SPECKLE_MAX:
        problems.append(f"{name}: 孤立杂色占比 {m['speckle']} > {SPECKLE_MAX}")
    if max(m["outline_color"]) < OUTLINE_MIN_CHANNEL:
        problems.append(f"{name}: 描边主色 {m['outline_color']} 近纯黑（应是物件色相压暗）")
    low, high = OUTLINE_VAL_RANGE
    if m["outline_sat"] < OUTLINE_SAT_MIN or not low <= m["outline_val"] <= high:
        problems.append(f"{name}: 描边主色 {m['outline_color']} 不是主色相压暗"
                        f"（饱和度 {m['outline_sat']} 须 ≥{OUTLINE_SAT_MIN}，明度 {m['outline_val']} 须在 {low}–{high}）")
    if not icon.rainbow:
        if m["colors"] > COLORS_MAX:
            problems.append(f"{name}: 色数 {m['colors']} > {COLORS_MAX}")
        if m["outline_top2"] < OUTLINE_TOP2_MIN:
            problems.append(f"{name}: 描边前两色占比 {m['outline_top2']} < {OUTLINE_TOP2_MIN}")
        share = m["outline_hue_share"]
        if share is not None and share < OUTLINE_HUE_SHARE_MIN:
            problems.append(f"{name}: 描边色相与物件不符（主体有彩像素只有 {share} 在描边色相 ±{OUTLINE_HUE_TOL}° 内，"
                            f"须 ≥{OUTLINE_HUE_SHARE_MIN}）")
    return problems


def rgba_sha256(image) -> str:
    """解码后 RGBA 像素的 sha256（与图标单元 manifest 同口径，和 PNG 压缩实现无关）。"""
    return hashlib.sha256(image.convert("RGBA").tobytes()).hexdigest()


def load_rgba(path: Path):
    from PIL import Image

    with Image.open(path) as opened:
        opened.load()
        return opened.convert("RGBA")


def find_source(art_dir: Path, stem: str) -> Path | None:
    for path in (art_dir / "icons" / f"{stem}.png", art_dir / f"{stem}.png"):
        if path.is_file():
            return path
    return None


def explicit_c4_sources(art_dir: Path, stem: str) -> list:
    """手给的 c4：图标单元的 ``<stem>_c4.png``（manifest c4_file），及旧约定 ``_40`` / ``@2x``。"""
    return [p for base in (art_dir / "icons", art_dir)
            for p in (base / f"{stem}_c4.png", base / f"{stem}_40.png", base / f"{stem}@2x.png") if p.is_file()]


def load_manifest(art_dir: Path) -> tuple:
    """图标单元的 ``manifest.json`` -> ({道具 ID: 条目} 或 None（没有该文件）, problems)。"""
    path = Path(art_dir) / MANIFEST_NAME
    if not path.is_file():
        return None, []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        entries = data["icons"]
    except (ValueError, KeyError, TypeError) as exc:
        return None, [f"{path}: 读不出 icons 列表: {exc!r}"]
    out: dict = {}
    problems: list = []
    for entry in entries:
        key = str(entry.get("item_id")) if isinstance(entry, dict) else None
        if key is None or key in out:
            problems.append(f"{path}: 条目缺 item_id 或重复: {entry if key is None else key}")
            continue
        out[key] = entry
    return out, problems


def manifest_problems(icon: Icon, entry: dict) -> list:
    """manifest 条目与本构建器合同逐项对齐（键名、c3/c4 逻辑路径；manifest 写了 rainbow 时彩虹口径也要一致）。"""
    problems = []
    for field_name, want in (("key", icon.stem), ("c3_logical", icon.c3), ("c4_logical", icon.c4)):
        if entry.get(field_name) != want:
            problems.append(f"manifest {icon.item_id} {field_name}={entry.get(field_name)!r}，构建器合同是 {want!r}")
    if "rainbow" in entry and entry["rainbow"] is not icon.rainbow:
        problems.append(f"manifest {icon.item_id} rainbow={entry['rainbow']!r}，构建器合同是 {icon.rainbow!r}"
                        "（两边门禁口径会分叉）")
    return problems


def load_approvals(path: Path) -> tuple:
    """``approved.json`` -> ({stem: c3_rgba_sha256}, problems)。没有文件 = 全部未确认（不是 problem）。"""
    path = Path(path)
    if not path.is_file():
        return {}, []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        approved = data["c3_rgba_sha256"]
        by, evidence = data["approved_by"], data["evidence"]
    except (ValueError, KeyError, TypeError) as exc:
        return {}, [f"{path}: 读不出确认记录: {exc!r}"]
    if not (isinstance(approved, dict) and isinstance(by, str) and by.strip()
            and isinstance(evidence, str) and evidence.strip()):
        return {}, [f"{path}: approved_by / evidence 须非空，c3_rgba_sha256 须是 {{stem: sha}}"]
    return {str(k): str(v) for k, v in approved.items()}, []


# ---------------------------------------------------------------------------
# 图集追加（设计 §6.6）
# ---------------------------------------------------------------------------

def atlas_rect(entry: dict) -> tuple:
    # r=true 时 w/h 含义两说，按外接正方形保守占位（同五重 v2）
    w, h = (max(entry["w"], entry["h"]),) * 2 if entry.get("r") else (entry["w"], entry["h"])
    return entry["x"], entry["y"], entry["x"] + w, entry["y"] + h


def _overlaps(a: tuple, b: tuple, gap: int) -> bool:
    return a[0] < b[2] + gap and b[0] < a[2] + gap and a[1] < b[3] + gap and b[1] < a[3] + gap


def find_slot(entries: list, sheet, size: tuple):
    """画布内找一块与所有条目（含间隔）不重叠、连同 1px 外圈全透明的位置；没有就 None（不扩画布）。

    扫描顺序同 ``wf_five_boss_v2.find_atlas_slot``（y 升序、x 升序的候选点）。"""
    w, h = size
    width, height = sheet.size
    rects = [atlas_rect(e) for e in entries]
    xs = sorted({1} | {r[2] + ATLAS_GAP for r in rects})
    ys = sorted({1} | {r[3] + ATLAS_GAP for r in rects})
    for y in ys:
        for x in xs:
            if x + w + 1 > width or y + h + 1 > height:
                continue
            candidate = (x, y, x + w, y + h)
            if any(_overlaps(candidate, r, ATLAS_GAP) for r in rects):
                continue
            if sheet.crop((x - 1, y - 1, x + w + 1, y + h + 1)).getextrema()[3] == (0, 0):
                return x, y
    return None


def append_to_atlas(entries: list, sheet, additions: list) -> dict:
    """additions = [(子纹理名, RGBA 图)]。-> {entries, sheet, added, updated, problems}。

    已有的自有名字：形状相同则原位换像素；其余已有名字一律拒绝。新名字只写 {n,w,h,x,y}。"""
    new_entries = copy.deepcopy(entries)
    sheet = sheet.copy()
    added, updated, problems = [], [], []
    for name, image in additions:
        hits = [e for e in new_entries if e.get("n") == name]
        if len(hits) > 1:
            problems.append(f"图集里 {name} 重名 {len(hits)} 次")
            continue
        if hits:
            entry = hits[0]
            if name not in OWNED_ATLAS_NAMES:
                problems.append(f"图集条目 {name} 不属于本线，拒绝改动")
                continue
            if set(entry) != {"n", "w", "h", "x", "y"} or (entry["w"], entry["h"]) != image.size:
                problems.append(f"图集条目 {name} 形状不同，拒绝重排: {entry}")
                continue
            box = (entry["x"], entry["y"], entry["x"] + entry["w"], entry["y"] + entry["h"])
            if sheet.crop(box).tobytes() == image.tobytes():
                continue
            sheet.paste(image, box[:2])
            updated.append(name)
            continue
        slot = find_slot(new_entries, sheet, image.size)
        if slot is None:
            problems.append(f"图集没有 {image.size} 的空位（本构建器不扩画布）: {name}")
            continue
        sheet.paste(image, slot)
        new_entries.append({"n": name, "w": image.size[0], "h": image.size[1], "x": slot[0], "y": slot[1]})
        added.append(name)
    return {"entries": new_entries, "sheet": sheet, "added": added, "updated": updated, "problems": problems}


def verify_atlas(old_entries: list, old_sheet, new_entries: list, new_sheet, touched: Iterable[str]) -> list:
    """旧条目逐键（含键序）相等；新条目只有 {n,w,h,x,y} 且互不重叠；未触及区域逐像素相等。"""
    from PIL import Image

    problems = []
    touched = set(touched)
    n_old = len(old_entries)
    if new_entries[:n_old] != old_entries or any(list(a) != list(b) for a, b in zip(old_entries, new_entries)):
        problems.append("图集旧条目被改动")
    if new_sheet.size != old_sheet.size:
        problems.append(f"图集画布尺寸变了: {old_sheet.size} -> {new_sheet.size}")
    names = [e["n"] for e in new_entries]
    if len(names) != len(set(names)):
        problems.append("图集条目重名")
    rects = [atlas_rect(e) for e in new_entries]
    for i, entry in enumerate(new_entries[n_old:], start=n_old):
        if set(entry) != {"n", "w", "h", "x", "y"}:
            problems.append(f"新条目键不对: {entry}")
        r = rects[i]
        if r[0] < 1 or r[1] < 1 or r[2] + 1 > new_sheet.size[0] or r[3] + 1 > new_sheet.size[1]:
            problems.append(f"新条目越界: {entry}")
        for j, other in enumerate(rects):
            if j != i and _overlaps(r, other, ATLAS_GAP):
                problems.append(f"新条目与 {new_entries[j]['n']} 重叠或间距不足 {ATLAS_GAP}px")
    if new_sheet.size == old_sheet.size:
        masked_old, masked_new = old_sheet.convert("RGBA").copy(), new_sheet.convert("RGBA").copy()
        clear = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        for entry in new_entries:
            if entry["n"] in touched:
                box = (entry["x"], entry["y"], entry["x"] + entry["w"], entry["y"] + entry["h"])
                patch = clear.resize((box[2] - box[0], box[3] - box[1]))
                masked_old.paste(patch, box[:2])
                masked_new.paste(patch, box[:2])
        if masked_old.tobytes() != masked_new.tobytes():
            problems.append("图集未触及区域的像素变了")
        by_name = {e["n"]: e for e in old_entries}
        for entry in new_entries[n_old:]:
            if entry["n"] in by_name:
                continue
            box = (entry["x"] - 1, entry["y"] - 1, entry["x"] + entry["w"] + 1, entry["y"] + entry["h"] + 1)
            if old_sheet.convert("RGBA").crop(box).getextrema()[3] != (0, 0):
                problems.append(f"新条目 {entry['n']} 占用了原本不透明的像素")
    return problems


# ---------------------------------------------------------------------------
# 边 E1：图标文件
# ---------------------------------------------------------------------------

def _edge(name: str) -> dict:
    return {"edge": name, "tables": {}, "files": {}, "server": {}, "problems": [], "blocked": [], "warnings": [],
            "requires": Requirements(), "report": {}, "publish": []}


def read_icon_art(art_dir: Path, icon: Icon, entry: dict | None) -> dict:
    """按 manifest 条目读一张图并跑全部门禁（E1 与 approve 共用）。

    -> {"status": "missing" | "bad" | "ok", "problems", "image", "c4", "sha", "metrics", "source"}。
    "missing" = manifest 没有这件、目录里也没有同名源图；目录里有图却没登记 = "bad"（合同断了）。"""
    art_dir = Path(art_dir)
    result = {"status": "bad", "problems": [], "image": None, "c4": None, "sha": None, "metrics": None,
              "source": None}
    problems = result["problems"]
    if entry is None:
        stray = find_source(art_dir, icon.stem)
        if stray is None:
            result["status"] = "missing"
        else:
            problems.append(f"{stray} 没登记在 {MANIFEST_NAME}（图标单元的交付合同；先跑 build_icons.py 重出 manifest）")
        return result
    problems += manifest_problems(icon, entry)
    source = art_dir / str(entry.get("c3_file") or "")
    if not entry.get("c3_file") or not source.is_file():
        problems.append(f"manifest {icon.item_id} 的 c3_file {entry.get('c3_file')!r} 不存在")
    if problems:
        return result
    image = load_rgba(source)
    metrics = icon_metrics(image)
    problems += icon_problems(icon, metrics)
    sha = rgba_sha256(image)
    if entry.get("c3_rgba_sha256") != sha:
        problems.append(f"{source.name} 的像素与 manifest {icon.item_id} 的 c3_rgba_sha256 不符（改了图没重跑 build_icons.py）")
    c4 = upscale2(image)
    if entry.get("c4_rgba_sha256") != rgba_sha256(c4):
        problems.append(f"manifest {icon.item_id} 的 c4_rgba_sha256 不等于 {source.name} 的 2 倍最近邻放大")
    c4_files = {path.resolve(): path for path in explicit_c4_sources(art_dir, icon.stem)}
    if entry.get("c4_file"):
        declared = art_dir / str(entry["c4_file"])
        if declared.is_file():
            c4_files.setdefault(declared.resolve(), declared)
        else:
            problems.append(f"manifest {icon.item_id} 的 c4_file {entry['c4_file']!r} 不存在")
    for extra in c4_files.values():
        given = load_rgba(extra)
        if given.size != c4.size or given.tobytes() != c4.tobytes():
            problems.append(f"{extra.name} 不等于 {source.name} 的 2 倍最近邻放大（c4 必须 = c3×2）")
    result.update(status="bad" if problems else "ok", image=image, c4=c4, sha=sha, metrics=metrics, source=source)
    return result


def build_e1(live: G.Live, art_dir: Path = ART_DIR, approval_path: Path | None = None) -> dict:
    out = _edge("E1")
    problems, blocked, warnings = out["problems"], out["blocked"], out["warnings"]
    art_dir = Path(art_dir)
    approval_path = Path(approval_path) if approval_path else art_dir / APPROVAL_NAME
    atlas_raw, png_raw, item_raw = live.raw(ATLAS_MAP), live.raw(ATLAS_PNG), live.raw(ITEM_LOGICAL)
    if atlas_raw is None or png_raw is None or item_raw is None:
        problems.append("store 缺 item_icon 图集或 item 表")
        return out
    entries = decode_atlas(atlas_raw)
    if wf_dsl.encode_amf3(entries) != zlib.decompress(atlas_raw, -15):
        problems.append("live 图集 AMF3 往返不是逐字节一致（无法保证旧条目原样）")
    sheet = open_png(png_raw)
    # 设计 §6.6：写入前复核 item_icon png、atlas、item 表三者的 sha（前两者在 files.live_sha256）
    out["requires"].sha256[ITEM_LOGICAL] = G.sha256(item_raw)
    manifest, manifest_errors = load_manifest(art_dir)
    problems += manifest_errors
    approvals, approval_errors = load_approvals(approval_path)
    problems += approval_errors

    additions, icons, shas = [], {}, {}
    for icon in ICONS:
        art = read_icon_art(art_dir, icon, (manifest or {}).get(icon.item_id))
        problems += art["problems"]
        if art["status"] == "missing":
            (blocked if icon.required else warnings).append(
                f"缺源图 {icon.stem}（{art_dir / MANIFEST_NAME} 没有道具 {icon.item_id}）"
                + ("" if icon.required else "：重画件本次不发"))
            icons[icon.stem] = "missing"
            continue
        if art["status"] != "ok":
            icons[icon.stem] = "bad"
            continue
        image, c3_png = art["image"], icon.c3 + ".png"
        current = live.raw(c3_png)
        live_image = None if current is None else open_png(current)
        if live_image is None or live_image.size != image.size or live_image.tobytes() != image.tobytes():
            out["files"][c3_png] = {"root": "upload", "logical": c3_png, "payload": store_png(image),
                                    "live_sha256": None if current is None else G.sha256(current)}
        additions.append((icon.c4, art["c4"]))
        shas[icon.stem] = art["sha"]
        icons[icon.stem] = {**{k: v for k, v in art["metrics"].items() if k not in ("alphas", "empty")},
                            "c3_rgba_sha256": art["sha"]}

    result = append_to_atlas(entries, sheet, additions)
    problems += result["problems"]
    touched = result["added"] + result["updated"]
    if touched:
        problems += verify_atlas(entries, sheet, result["entries"], result["sheet"], touched)
        for logical, payload, current in ((ATLAS_PNG, store_png(result["sheet"]), png_raw),
                                          (ATLAS_MAP, encode_atlas(result["entries"]), atlas_raw)):
            out["files"][logical] = {"root": "upload", "logical": logical, "payload": payload,
                                     "live_sha256": G.sha256(current)}
        staged_sheet = open_png(out["files"][ATLAS_PNG]["payload"])
        if staged_sheet.tobytes() != result["sheet"].tobytes():
            problems.append("图集 PNG 编码往返不一致")
        if decode_atlas(out["files"][ATLAS_MAP]["payload"]) != result["entries"]:
            problems.append("图集 atlas 编码往返不一致")
    # 设计 §6.5 第 3 步 / §7 第 2 步：要写进 store 的每张图都须作者看过预览（按像素 sha 登记，改图须重新确认）
    shipping = sorted(i.stem for i in ICONS if i.stem in shas and (i.c3 + ".png" in out["files"] or i.c4 in touched))
    unapproved = [stem for stem in shipping if approvals.get(stem) != shas[stem]]
    if unapproved:
        blocked.append(f"待作者确认预览（设计 §6.5 第 3 步）：{unapproved}；作者确认后运行 python "
                       f"mod-tools/wf_weapon_awaken.py approve --by 作者 --evidence \"<原话与时间>\"，"
                       f"登记到 {approval_path}")
    out["publish"] = [p for p in (ATLAS_PNG, ATLAS_MAP) if p in out["files"]] + \
        sorted(k for k in out["files"] if k not in (ATLAS_PNG, ATLAS_MAP))
    out["report"] = {"icons": icons,
                     "approval": {"file": str(approval_path), "shipping": shipping, "unapproved": unapproved},
                     "atlas": {"entries_before": len(entries), "entries_after": len(result["entries"]),
                               "added": result["added"], "updated": result["updated"], "size": list(sheet.size),
                               "placed": {e["n"]: [e["x"], e["y"], e["w"], e["h"]]
                                          for e in result["entries"] if e["n"] in touched}}}
    return out


def approve(art_dir: Path = ART_DIR, *, by: str, evidence: str, only: Iterable[str] = (),
            approval_path: Path | None = None) -> dict:
    """作者看过预览并确认后调用：把指定（默认全部已交付）图的当前 c3 RGBA sha 记进 ``approved.json``。

    每张图都先过 ``read_icon_art`` 的全部门禁与 manifest 核对，任何一张不过就什么都不写。
    已登记的其他图保留；同一张图再确认会覆盖 sha。-> {"refused", "problems", "approved", "path"}。"""
    art_dir = Path(art_dir)
    approval_path = Path(approval_path) if approval_path else art_dir / APPROVAL_NAME
    problems: list = []
    if not by.strip() or not evidence.strip():
        problems.append("--by 与 --evidence 必须写明是谁、在什么时候确认的")
    stems = {i.stem for i in ICONS}
    wanted = set(only) or stems
    if wanted - stems:
        problems.append(f"不认识的图: {sorted(wanted - stems)}（可选 {sorted(stems)}）")
    manifest, manifest_errors = load_manifest(art_dir)
    problems += manifest_errors
    if manifest is None and not manifest_errors:
        problems.append(f"{art_dir / MANIFEST_NAME} 不存在")
    existing, approval_errors = load_approvals(approval_path)
    problems += approval_errors
    record: dict = {}
    for icon in ICONS:
        if icon.stem not in wanted:
            continue
        art = read_icon_art(art_dir, icon, (manifest or {}).get(icon.item_id))
        if art["status"] == "missing":
            if only:
                problems.append(f"{icon.stem} 还没交付，不能确认")
            continue
        problems += art["problems"]
        if art["status"] == "ok":
            record[icon.stem] = art["sha"]
    if not record and not problems:
        problems.append("没有可确认的图")
    if problems:
        return {"refused": True, "problems": problems, "approved": {}, "path": str(approval_path)}
    data = json.loads(approval_path.read_text(encoding="utf-8")) if approval_path.is_file() else {}
    history = list(data.get("history") or [])
    history.append({"approved_by": by, "evidence": evidence, "stems": sorted(record)})
    data = {"_doc": "作者确认图标预览的登记（设计 §6.5 第 3 步）。wf_weapon_awaken.py approve 写入；"
                    "stage-e1 只发 sha 与此一致的图，图一改就要重新确认。",
            "approved_by": by, "evidence": evidence,
            "c3_rgba_sha256": dict(sorted({**existing, **record}.items())), "history": history}
    approval_path.parent.mkdir(parents=True, exist_ok=True)
    approval_path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8",
                             newline="\n")
    return {"refused": False, "problems": [], "approved": record, "path": str(approval_path)}


# ---------------------------------------------------------------------------
# 边 E2：道具与觉醒数据
# ---------------------------------------------------------------------------

def _icon_ready(view: View, live_names: set, view_names: set, icon: Icon, reqs: Requirements) -> str | None:
    """-> None（已满足）或未满足原因；靠叠加满足时记 requires。c3 图与 c4 子纹理都要在，才能同一条边一起改指。"""
    c3_png = icon.c3 + ".png"
    if icon.c4 in live_names and view.live.raw(c3_png) is not None:
        reqs.atlas_names.add(icon.c4)
        reqs.files_present.add(c3_png)
        return None
    if icon.c4 in view_names and view.has_file(c3_png):
        reqs.atlas_names.add(icon.c4)
        reqs.files_present.add(c3_png)
        reqs.via_overlay(view, (ATLAS_MAP, ATLAS_PNG, c3_png))
        return None
    missing = [f"子纹理 {icon.c4}"] if icon.c4 not in view_names else []
    if not view.has_file(c3_png):
        missing.append(f"c3 图 {c3_png}")
    return "、".join(missing) + " 未上线（先发边 E1）"


def paradox_tool_synced(icon: Icon, path: Path = PARADOX_TOOL) -> bool:
    """只读：wf_paradox_weapon.py 的 MATERIALS 是否已写重画版 c3/c4（没同步，它下次暂存会把道具行改回旧图）。"""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    return f'"{icon.c3}"' in text and f'"{icon.c4}"' in text


def build_e2(live: G.Live, overlay: Overlay | None = None, *, awakening_cas: bool = True) -> dict:
    """``awakening_cas=False``：CAS 只暂存底框换图键，不带 30 条 ``awakening_material_*``（它们等客户端补丁
    equipment-awakening-material 就绪后另发；E2a 1.4.1100 起就是这样拆的）。合同门禁照跑。"""
    out = _edge("E2")
    problems, blocked, warnings, reqs = out["problems"], out["blocked"], out["warnings"], out["requires"]
    view = View(live, overlay)
    for source in view.overlay.blocked_sources:
        blocked.append(f"前一条边 {source['edge']}（{source['dir']}）本身是 blocked")
    live_names = {str(e["n"]) for e in decode_atlas(live.raw(ATLAS_MAP))} if live.raw(ATLAS_MAP) else set()
    view_names = view.atlas_names()

    # -- 道具行 ---------------------------------------------------------------
    items = live.flat(ITEM_LOGICAL)
    for key, (c10, c11) in OFFICIAL_AWAKENING_ITEMS.items():
        row = items.get(key, [])
        if len(row) != 23 or row[6] != AWAKENING_EFFECT or row[10] != c10 or row[11] != c11:
            problems.append(f"官方觉醒道具 {key} 形状漂移: c6/c10/c11={row[6:7]}{row[10:12]}")
    item_upsert: dict = {}
    for key, row in item_rows().items():
        if len(row) != 23:
            problems.append(f"item {key} {len(row)} 列 != 23")
        if "," in row[5] or "\n" in row[5]:
            problems.append(f"item {key} 说明含半角逗号/换行")
        current = items.get(key)
        if current and current[:1] != row[:1]:
            problems.append(f"item {key} 已被占用: {current[:3]}")
        reason = _icon_ready(view, live_names, view_names, ICON_BY_ITEM[key], reqs)
        if reason:
            blocked.append(f"道具 {key} 的图标：{reason}")
        item_upsert[key] = row
    steel = item_rows()[str(STAR_STEEL_ID)]
    if steel[6] == AWAKENING_EFFECT or steel[10] or steel[11]:
        problems.append("禁忌星铁 c6 不能是 6、c10/c11 必须留空（否则原生逻辑会把它提供给所有 ★5）")
    repointed, deferred = [], []
    for icon in ICONS:
        if icon.required:
            continue
        row = items.get(icon.item_id)
        if not row:
            warnings.append(f"item {icon.item_id} 不在 live，跳过改指")
            continue
        reason = _icon_ready(view, live_names, view_names, icon, reqs)
        if reason:
            deferred.append(icon.item_id)
            continue
        want = list(row)
        want[3], want[4] = icon.c3, icon.c4
        if want != row:
            item_upsert[icon.item_id] = want
            repointed.append(icon.item_id)
    if deferred:
        warnings.append(f"重画/专属 c4 未上线，暂不改指: {deferred}")
    stale_paradox = [i for i in repointed if i in ("10000301", "10000302")
                     and not paradox_tool_synced(ICON_BY_ITEM[i])]
    if stale_paradox:
        warnings.append(f"{stale_paradox} 的 c3/c4 改指重画版（{[ICON_BY_ITEM[i].c3 for i in stale_paradox]}）；"
                        "wf_paradox_weapon.py 的 MATERIALS 还写旧 c3 与五重子纹理，PARADOX 线须同步，否则它下次暂存会改回")

    # -- CAS 30 键 ------------------------------------------------------------
    equipment = live.flat(EQUIPMENT_LOGICAL)
    for eid in RESTRICTED_EQUIPMENT:
        cells = equipment.get(str(eid))
        if not cells or cells[2:3] != ["0"]:
            problems.append(f"受限装备 {eid} 不在 live 装备表或不是武器")
    cas = cas_rows()
    live_cas = live.flat(CAS_LOGICAL)
    for key, row in cas.items():
        if key in live_cas and live_cas[key] != row:
            warnings.append(f"CAS {key} live 值 {live_cas[key]} 将改为 {row}")
    stray = sorted(k for k in live_cas if k.startswith(CAS_PREFIX) and k not in cas)
    if stray:
        problems.append(f"live 有合同外的 {CAS_PREFIX}* 键: {stray[:5]}")
    frames = rarity_frame_rows()
    for key, (value,) in frames.items():
        if not live.raw(value + ".png"):
            blocked.append(f"底框换图 {key} 指向的 {value}.png 不在 store（先发 PARADOX Lv200 蓝金框）")
        reqs.files_present.add(value + ".png")

    # -- UI 字符串 --------------------------------------------------------------
    ui_live = live.flat(UI_LOGICAL)
    ui_upsert = {}
    for key, (old, new) in UI_RENAMES.items():
        have = ui_live.get(key)
        if have not in ([old], [new]):
            problems.append(f"ui_string {key} 漂移: {have}")
        ui_upsert[key] = [new]

    # -- 结算展示行 -----------------------------------------------------------------
    reward_raw = live.raw(REWARD_LOGICAL)
    reward_text = core.write_csv_lines([REWARD_ROW])
    reward_problems: list = []
    if reward_raw is None:
        reward_problems.append(f"store 里没有 {REWARD_LOGICAL}")
    else:
        groups = codec.unpack(reward_raw)
        if REWARD_GROUP not in groups:
            reward_problems.append(f"additional_reward 缺组 {REWARD_GROUP}")
        else:
            inner = {k: core.read_csv_lines(zlib.decompress(v).decode("utf-8"))[0]
                     for k, v in codec.unpack(groups[REWARD_GROUP]).items()}
            for idx, item_id in REWARD_EXPECTED.items():
                if inner.get(idx, [None] * 3)[2:3] != [item_id]:
                    reward_problems.append(f"additional_reward[{REWARD_GROUP}][{idx}] 不是 {item_id}: {inner.get(idx)}")
            if REWARD_INDEX in inner and inner[REWARD_INDEX] != REWARD_ROW:
                reward_problems.append(
                    f"additional_reward[{REWARD_GROUP}][{REWARD_INDEX}] 已被占用: {inner[REWARD_INDEX]}")
            if set(inner) - set(REWARD_EXPECTED) - {REWARD_INDEX}:
                reward_problems.append(f"additional_reward[{REWARD_GROUP}] 有合同外内层键: {sorted(inner)}")
    problems += reward_problems

    # -- 客户端暂存 ---------------------------------------------------------------
    cas_upsert = {**(cas if awakening_cas else {}), **frames}
    for logical, upsert in ((ITEM_LOGICAL, item_upsert), (CAS_LOGICAL, cas_upsert), (UI_LOGICAL, ui_upsert)):
        raw = live.raw(logical)
        if raw is None:
            problems.append(f"store 里没有 {logical}")
            continue
        staged, changed, deleted = G.repack(raw, {k: core.write_csv_lines([v]) for k, v in upsert.items()})
        if changed:
            out["tables"][logical] = (staged, changed, deleted)
    if not reward_problems:
        staged, changed = repack_inner(reward_raw, REWARD_GROUP, {REWARD_INDEX: reward_text})
        if changed:
            out["tables"][REWARD_LOGICAL] = (staged, changed, [])

    # 暂存后的全表门禁：c6=6 仍只有两行；CAS 值指向存在且 c6≠6 的行
    staged_items = flat_rows(out["tables"][ITEM_LOGICAL][0]) if ITEM_LOGICAL in out["tables"] else items
    awakening = sorted(k for k, r in staged_items.items() if r[6:7] == [AWAKENING_EFFECT])
    if awakening != sorted(OFFICIAL_AWAKENING_ITEMS):
        problems.append(f"c6=6 的觉醒道具应只有 {sorted(OFFICIAL_AWAKENING_ITEMS)}，暂存后是 {awakening}")
    for key, (value,) in cas.items():
        target = staged_items.get(value)
        if not target:
            problems.append(f"CAS {key} 指向不存在的道具 {value}")
        elif target[6:7] == [AWAKENING_EFFECT]:
            problems.append(f"CAS {key} 指向 c6=6 的道具 {value}")

    # -- 服务端 ---------------------------------------------------------------
    rows = item_rows()
    sale = {k: server_item_sale(r) for k, r in rows.items()}
    lookup = {k: r[2] for k, r in rows.items()}
    for name, want in ((SERVER_ITEM_SALE, sale), (SERVER_ITEM_LOOKUP, lookup)):
        have = live.server_json(name) or {}
        for key, value in want.items():
            if key in have and have[key] != value:
                problems.append(f"服务端 {name} {key} 已被占用: {have[key]!r}")
    edits = {
        SERVER_ITEM_IDS: G.ServerEdit(append=tuple(int(k) for k in rows)),
        SERVER_ITEM_LOOKUP: G.ServerEdit(upsert=lookup, siblings=("999020", "999019")),
        SERVER_ITEM_SALE: G.ServerEdit(upsert=sale, style="indent", siblings=("999020", "999019")),
    }
    material = live.server_json(SERVER_MATERIAL)
    if material is None:
        blocked.append(f"服务端白名单（设计 §7 第 1 步）未上线：assets/{SERVER_MATERIAL} 不存在")
    else:
        have = material.get("materialByEquipment")
        if not isinstance(have, dict):
            problems.append(f"assets/{SERVER_MATERIAL} 缺 materialByEquipment")
        else:
            extra = sorted(set(have) - set(material_map()))
            if extra:
                problems.append(f"assets/{SERVER_MATERIAL} materialByEquipment 有合同外装备: {extra[:5]}")
            edits[SERVER_MATERIAL] = G.ServerEdit(path=("materialByEquipment",), upsert=material_map(),
                                                  style="indent", siblings=tuple(str(e) for e in RESTRICTED_EQUIPMENT))
        crystals = material.get("officialCrystals")
        if crystals != {"12001": {"maxRarity": 4}, "12002": {"exactRarity": 5}}:
            warnings.append(f"assets/{SERVER_MATERIAL} officialCrystals 与设计 §2.6 不同: {crystals}")
    # rarityOverrides 由 live 装备 c11 重建（同一文件第二个容器，单独拼接在 materialByEquipment 之后）
    want_rarity, rarity_problems = rarity_overrides(equipment)
    problems += rarity_problems
    rarity_edit = None
    if material is not None:
        have_rarity = material.get("rarityOverrides")
        if not isinstance(have_rarity, dict):
            problems.append(f"assets/{SERVER_MATERIAL} 缺 rarityOverrides")
        else:
            stale = sorted(set(have_rarity) - set(want_rarity), key=lambda k: (len(k), k))
            drift = sorted(k for k, v in want_rarity.items() if have_rarity.get(k) != v)
            if stale or drift:
                warnings.append(f"assets/{SERVER_MATERIAL} rarityOverrides 与 live 装备 c{EQUIPMENT_RARITY_COL} 漂移，"
                                f"将改写 {drift[:5]}（共 {len(drift)}）、删除 {stale[:5]}（共 {len(stale)}）")
            rarity_edit = G.ServerEdit(path=("rarityOverrides",), upsert=want_rarity, delete=tuple(stale),
                                       style="indent", siblings=tuple(have_rarity))
    for name in edits:
        if live.server_bytes(name) is None and name != SERVER_MATERIAL:
            problems.append(f"服务端文件缺失: assets/{name}")
    staged_server, server_problems = G.stage_server(live, {"server": {k: v for k, v in edits.items()
                                                                        if live.server_bytes(k) is not None}})
    problems += server_problems
    if rarity_edit is not None:
        base = staged_server.get(SERVER_MATERIAL)
        text = base[0].decode("utf-8") if base else live.server_text(SERVER_MATERIAL)
        try:
            new_text, added, deleted, updated = G.splice_json(text, rarity_edit)
        except ValueError as exc:   # SpliceError 是 ValueError
            problems.append(f"assets/{SERVER_MATERIAL} rarityOverrides: {exc}")
        else:
            if new_text != text:
                tag = lambda keys: [f"rarityOverrides.{k}" for k in keys]  # noqa: E731
                prev = base[1:] if base else ([], [], [])
                staged_server[SERVER_MATERIAL] = (new_text.encode("utf-8"), prev[0] + tag(added),
                                                  prev[1] + tag(deleted), prev[2] + tag(updated))
    out["server"] = staged_server
    if material is not None:
        final = json.loads(staged_server[SERVER_MATERIAL][0]) if SERVER_MATERIAL in staged_server else material
        if SERVER_MATERIAL in edits and \
                final.get("materialByEquipment") != {k[len(CAS_PREFIX):]: int(v[0]) for k, v in cas.items()}:
            problems.append("服务端 materialByEquipment 与 CAS 键不是逐项相等")
        if final.get("rarityOverrides") != want_rarity:
            problems.append(f"服务端 rarityOverrides 与 live 装备 c{EQUIPMENT_RARITY_COL}≠floor(id/1e6) 的行不是逐项相等")

    out["publish"] = [lg for lg in (ITEM_LOGICAL, REWARD_LOGICAL, CAS_LOGICAL, UI_LOGICAL) if lg in out["tables"]]
    out["report"] = {"new_items": sorted(rows), "repointed": repointed, "repoint_deferred": deferred,
                     "capabilities": {key: RARITY_FRAME_CAP for key in frames},
                     "cas_keys": len(cas) if awakening_cas else 0, "rarity_frame_keys": sorted(frames),
                     "ui_keys": sorted(ui_upsert), "rarity_overrides": len(want_rarity),
                     "reward_row": f"[{REWARD_GROUP}][{REWARD_INDEX}] = {reward_text}"}
    return out


# ---------------------------------------------------------------------------
# 边 E3：五重商店
# ---------------------------------------------------------------------------

def shop_frame_fixes(live_shop: dict, items: dict) -> tuple:
    """SHOP_FRAME_FIXES 的目标行（只改 c13，其余列逐格 = live）-> ({键: 行}, problems)。

    奖励道具必须对得上、live c13 只能是旧值或目标值（别的值 = 有人改过，拒绝），目标值须与道具表 c17 一致
    （商店缩略图底框与背包里同一道具的底框相同）。"""
    rows: dict = {}
    problems: list = []
    for key, (old, new, reward) in SHOP_FRAME_FIXES.items():
        row = live_shop.get(key)
        if not row or len(row) != 50 or row[33:34] != [reward]:
            problems.append(f"五重商店 {key} 不是奖励 {reward} 的 50 列行: {(row or [])[6:7]} c33={(row or [])[33:34]}")
            continue
        if row[SHOP_FRAME_COL] not in (old, new):
            problems.append(f"五重商店 {key} c{SHOP_FRAME_COL}={row[SHOP_FRAME_COL]} 漂移（期望 {old} 或 {new}）")
            continue
        item = items.get(reward) or []
        if item[ITEM_RARITY_COL:ITEM_RARITY_COL + 1] != [new]:
            problems.append(f"道具 {reward} c{ITEM_RARITY_COL}={item[ITEM_RARITY_COL:ITEM_RARITY_COL + 1]}，"
                            f"与商店底框目标 {new} 不一致")
        want = list(row)
        want[SHOP_FRAME_COL] = new
        rows[key] = want
    return rows, problems


def build_e3(live: G.Live, overlay: Overlay | None = None, *, stage_node_c9: bool = False,
             drop_live: bool | None = None) -> dict:
    """``drop_live``：None = ``G.five_boss_drop_live()`` 检测；True = 调用方已核实五重掉落上线（``--drop-live``）。"""
    out = _edge("E3")
    problems, blocked, warnings, reqs = out["problems"], out["blocked"], out["warnings"], out["requires"]
    view = View(live, overlay)
    for source in view.overlay.blocked_sources:
        blocked.append(f"前一条边 {source['edge']}（{source['dir']}）本身是 blocked")

    if drop_live is None:
        drop_live = G.five_boss_drop_live()
    live_waiting = G.shop_prerequisites(live.flat(ITEM_LOGICAL), lambda lg: live.raw(lg) is not None,
                                        drop_live=drop_live)
    if live_waiting:   # 掉落不能靠 --after 叠加满足：没上线时 view_waiting 也含它 ⇒ blocked
        view_waiting = G.shop_prerequisites(view.flat(ITEM_LOGICAL), view.has_file, drop_live=drop_live)
        if view_waiting:
            blocked += view_waiting
        else:
            reqs.via_overlay(view, (ITEM_LOGICAL, G.STAR_STEEL_THUMB + ".png"))
    needed = sorted({str(i) for p in G.shop_products() for i, _ in p.costs} |
                    {str(p.reward_item_id) for p in G.shop_products()})
    reqs.table_keys[ITEM_LOGICAL] = set(needed)
    reqs.files_present.add(G.STAR_STEEL_THUMB + ".png")

    live_shop = live.flat(SHOP_LOGICAL)
    rows, server_entries, shop_problems = G.shop_targets(live_shop.get(G.SHOP_TEMPLATE_KEY, []))
    problems += shop_problems
    live_shop_server = (live.server_json(SERVER_SHOP) or {}).get(G.SHOP_CATEGORY)
    if live_shop_server is None:
        problems.append(f"服务端 {SERVER_SHOP} 缺分类 {G.SHOP_CATEGORY}")
        live_shop_server = {}
    problems += G.shop_occupancy_problems(live_shop, live_shop_server)
    frame_rows, frame_problems = shop_frame_fixes(live_shop, live.flat(ITEM_LOGICAL))
    problems += frame_problems
    shop_raw = live.raw(SHOP_LOGICAL)
    upsert = {**rows, **frame_rows} if rows else {}
    if shop_raw is not None and upsert:
        staged, changed, deleted = G.repack(shop_raw, {k: core.write_csv_lines([v]) for k, v in upsert.items()})
        if changed:
            out["tables"][SHOP_LOGICAL] = (staged, changed, deleted)

    if stage_node_c9:
        node_raw = live.raw(NODE_LOGICAL)
        outer, inner_key = NODE_PATH
        try:
            inner = codec.unpack(codec.unpack(node_raw)[outer])
            row = core.read_csv_lines(zlib.decompress(inner[inner_key]).decode("utf-8"))[0]
        except (KeyError, TypeError, ValueError) as exc:
            problems.append(f"boss_battle_stage_node{list(NODE_PATH)} 读不到: {exc}")
        else:
            if row[NODE_HOLDING_COL] not in (NODE_HOLDING_OLD, str(KING_COIN_ID)):
                problems.append(f"stage_node{list(NODE_PATH)} c{NODE_HOLDING_COL} 漂移: {row[NODE_HOLDING_COL]}")
            want = list(row)
            want[NODE_HOLDING_COL] = str(KING_COIN_ID)
            staged, changed = repack_inner(node_raw, outer, {inner_key: core.write_csv_lines([want])})
            if changed:
                out["tables"][NODE_LOGICAL] = (staged, changed, [])
            warnings.append("stage_node c9 换王币须五重线同意（设计 §4.2/§4.4 第 3 条）")

    edits = {
        SERVER_SHOP: G.ServerEdit(path=(G.SHOP_CATEGORY,), upsert=server_entries, style="indent",
                                  siblings=(G.SHOP_TEMPLATE_KEY,)),
        SERVER_SHOP_MAP: G.ServerEdit(upsert={k: int(G.SHOP_CATEGORY) for k in server_entries}, style="indent",
                                      siblings=(G.SHOP_TEMPLATE_KEY,)),
    }
    staged_server, server_problems = G.stage_server(live, {"server": edits})
    problems += server_problems
    out["server"] = staged_server
    out["publish"] = [lg for lg in (SHOP_LOGICAL, NODE_LOGICAL) if lg in out["tables"]]
    out["report"] = {"shop": {k: {"order": v[9], "costs": v[17:25], "buy_max": v[28], "max_frequency": v[29],
                                  "reward": v[33]} for k, v in rows.items()},
                     "server_stock": {k: v["stock"] for k, v in server_entries.items()},
                     "frame_fixes": {k: f"c{SHOP_FRAME_COL} {live_shop[k][SHOP_FRAME_COL]} -> {v[SHOP_FRAME_COL]}"
                                     for k, v in frame_rows.items()},
                     "stage_node_c9": stage_node_c9, "five_boss_drop_live": drop_live}
    return out


# ---------------------------------------------------------------------------
# 边 E4：作者 0928 晚修订（E1/E2/E3 在 live 上重算的差集 + 武器扭蛋说明）
# ---------------------------------------------------------------------------

def merge_edges(name: str, parts: Iterable[dict]) -> dict:
    """把几条边的暂存合成一条（同一文件只许一条边改，撞了进 problems）。requires 取并集，report 按原边名分开。"""
    out = _edge(name)
    reqs = out["requires"]
    for part in parts:
        for key in ("problems", "blocked", "warnings"):
            out[key] += [f"{part['edge']}: {x}" for x in part[key]]
        for section in ("tables", "files", "server"):
            clash = sorted(set(out[section]) & set(part[section]))
            if clash:
                out["problems"].append(f"{part['edge']} 与前面的边改了同一文件: {clash}")
            out[section].update(part[section])
        theirs = part["requires"]
        reqs.sha256.update(theirs.sha256)
        reqs.atlas_names |= theirs.atlas_names
        reqs.files_present |= theirs.files_present
        for logical, keys in theirs.table_keys.items():
            reqs.table_keys.setdefault(logical, set()).update(keys)
        reqs.conditional |= theirs.conditional
        out["publish"] += [p for p in part["publish"] if p not in out["publish"]]
        out["report"][part["edge"]] = part["report"]
    return out


def build_e4(live: G.Live, art_dir: Path = ART_DIR, *, drop_live: bool | None = None,
             approval_path: Path | None = None, gacha: dict | None = None) -> dict:
    """作者 0928 晚的修订合成一条边：禁忌星铁紫灰图回退（E1 的图集与 c3）、底框换图键与「悖论武器」文案（E2）、
    034 改价限购与凭证 002 彩虹框（E3）、武器扭蛋说明里的「悖论武器」（wf_weapon_gacha 的注意事项正文）。

    三条旧边都按 live 重算（已上线的内容自然是空差），所以 E4 = 当前源码与 live 的全部差异；任何一条旧边若还有
    本次修订以外的差异，也会一并进来——报告里按原边名列出，发布前核对。例外：30 条 ``awakening_material_*``
    （E2a 起就等 equipment-awakening-material 补丁另发）不进 E4，只在 warnings 里报。``gacha`` = 已算好的 ``G.build`` 结果（测试注入）。"""
    parts = [build_e1(live, art_dir, approval_path), build_e2(live, awakening_cas=False),
             build_e3(live, drop_live=drop_live)]
    out = merge_edges("E4", parts)
    pending = sorted(k for k in cas_rows() if k not in live.flat(CAS_LOGICAL))
    if pending:
        out["warnings"].append(f"{len(pending)} 条 {CAS_PREFIX}* 不在本边（等客户端补丁 equipment-awakening-material 就绪后另发）")
    try:
        gacha = gacha if gacha is not None else G.build(live, drop_live=drop_live)
    except (OSError, ValueError, KeyError) as exc:     # 官方 1.4.0 档缺失等：扭蛋说明算不出来就拒绝整条边
        out["problems"].append(f"武器扭蛋构建失败: {exc!r}")
        return out
    out["problems"] += [f"武器扭蛋: {p}" for p in gacha["problems"]]
    payload = gacha["files"][G.RICH_TEXT_BODY_LOGICAL]
    current = live.raw(G.RICH_TEXT_BODY_LOGICAL)
    if current is None:
        out["problems"].append(f"store 里没有 {G.RICH_TEXT_BODY_LOGICAL}（武器扭蛋未上线，E4 只改正文不新建）")
    elif G.inflate_raw(current) != G.inflate_raw(payload):
        out["files"][G.RICH_TEXT_BODY_LOGICAL] = {"root": "upload", "logical": G.RICH_TEXT_BODY_LOGICAL,
                                                  "payload": payload, "live_sha256": G.sha256(current)}
        out["publish"].append(G.RICH_TEXT_BODY_LOGICAL)
    # 武器扭蛋自己的五重商店目标行与 E3 同源：两边算出来必须逐行相同，否则两个生成器会互相改回
    e3_shop = out["tables"].get(SHOP_LOGICAL)
    staged_shop = flat_rows(e3_shop[0]) if e3_shop is not None else live.flat(SHOP_LOGICAL)
    for key, row in gacha["rows"][SHOP_LOGICAL].items():     # 扭蛋暂缓 032–034 时为空
        if staged_shop.get(key) != row:
            out["problems"].append(f"五重商店 {key}: E3 与 wf_weapon_gacha 的目标行不一致（两个生成器会互相改回）")
    out["report"]["gacha_note"] = {"changed": G.RICH_TEXT_BODY_LOGICAL in out["files"],
                                   "paradox_lines": [line.strip() for line in gacha["html"].splitlines()
                                                     if G.PARADOX_CLASS in line or "PARADOX" in line]}
    return out


# ---------------------------------------------------------------------------
# 暂存
# ---------------------------------------------------------------------------

def edge_status(out: dict) -> str:
    if out["blocked"]:
        return "blocked"
    return "pending" if out["requires"].conditional else "ready"


def _check_disjoint(out: dict, overlay: Overlay | None) -> None:
    if overlay is None:
        return
    clash = sorted((set(out["tables"]) | set(out["files"])) & set(overlay.files))
    if clash:
        out["problems"].append(f"本边与 --after 的前一条边改了同一文件: {clash}")


def write_stage(workdir: Path, live: G.Live, out: dict, overlay: Overlay | None = None) -> dict:
    """写 <workdir>/stage/{common,server}/** 与计划文件；problems 非空时拒绝且什么都不写。"""
    workdir = Path(workdir)
    G._refuse_live_workdir(live, workdir)  # noqa: SLF001 - 与武器扭蛋同一道防线
    _check_disjoint(out, overlay)
    if out["problems"]:
        return {"refused": True, "problems": list(out["problems"])}
    status = edge_status(out)
    stage_dir = workdir / "stage"
    if stage_dir.exists():
        shutil.rmtree(stage_dir)
    for name in PLAN_NAMES.values():
        (workdir / name).unlink(missing_ok=True)
    plan: dict = {"edge": out["edge"], "status": status, "tables": {}, "files": {}, "server": {}, "deleted": {}}
    for logical, (staged, changed, deleted) in out["tables"].items():
        G._write(stage_dir / "common" / logical, staged)  # noqa: SLF001
        plan["tables"][logical] = {"changed": sorted(changed + deleted),
                                   "live_sha256": G.sha256(live.raw(logical)), "staged_sha256": G.sha256(staged)}
        if deleted:
            plan["deleted"][logical] = sorted(deleted)
    for key, info in out["files"].items():
        G._write(stage_dir / "common" / info["logical"], info["payload"])  # noqa: SLF001
        plan["files"][key] = {"live_sha256": info["live_sha256"], "staged_sha256": G.sha256(info["payload"]),
                              "root": info["root"]}
    for name, (staged, added, deleted, updated) in out["server"].items():
        G._write(stage_dir / "server" / name, staged)  # noqa: SLF001
        plan["server"][name] = {"live_sha256": G.sha256(live.server_bytes(name)), "staged_sha256": G.sha256(staged),
                                "added": added, "deleted": deleted, "updated": updated}
    plan["requires"] = out["requires"].as_json()
    plan["after"] = overlay.sources if overlay else []
    plan["blocked"] = list(out["blocked"])
    plan["warnings"] = list(out["warnings"])
    plan["publish_tables"] = ",".join(out["publish"])
    workdir.mkdir(parents=True, exist_ok=True)
    plan_path = workdir / PLAN_NAMES[status]
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"refused": False, "status": status, "plan_path": str(plan_path), "plan": plan, "report": out["report"],
            "sizes": {**{k: len(v[0]) for k, v in out["tables"].items()},
                      **{k: len(v["payload"]) for k, v in out["files"].items()},
                      **{f"assets/{k}": len(v[0]) for k, v in out["server"].items()}}}


def summarize(out: dict) -> dict:
    return {"edge": out["edge"], "status": edge_status(out) if not out["problems"] else "refused",
            "problems": out["problems"], "blocked": out["blocked"], "warnings": out["warnings"],
            "tables": {k: {"changed": v[1], "deleted": v[2]} for k, v in out["tables"].items()},
            "files": sorted(out["files"]),
            "server": {k: {"added": v[1], "deleted": v[2], "updated": v[3]} for k, v in out["server"].items()},
            "requires": out["requires"].as_json(), "report": out["report"]}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    check_parser = sub.add_parser("check", help="只读体检：三条边各自的状态、problems、blocked、将暂存的内容")
    check_parser.add_argument("--art-dir", type=Path, default=ART_DIR)
    check_parser.add_argument("--drop-live", action="store_true", help="已核实五重掉落发王币（E3 前提）")
    approve_parser = sub.add_parser("approve", help="作者确认预览后：把当前图的 c3 sha 登记进 approved.json")
    approve_parser.add_argument("--art-dir", type=Path, default=ART_DIR)
    approve_parser.add_argument("--by", required=True, help="谁确认的（通常是「作者」）")
    approve_parser.add_argument("--evidence", required=True, help="确认的原话与时间")
    approve_parser.add_argument("--only", nargs="*", default=[], help="只登记这些图（stem）；默认全部已交付的图")
    e1 = sub.add_parser("stage-e1", help="边 E1：item_icon 图集两文件 + c3 PNG")
    e1.add_argument("workdir", type=Path)
    e1.add_argument("--art-dir", type=Path, default=ART_DIR)
    e2 = sub.add_parser("stage-e2", help="边 E2：道具行、结算展示行、CAS 30 键、UI 2 键、服务端道具与白名单")
    e2.add_argument("workdir", type=Path)
    e2.add_argument("--after", type=Path, action="append", default=[], help="前一条边（E1）的 workdir")
    e3 = sub.add_parser("stage-e3", help="边 E3：五重商店 032/033 改价、034 新增（+可选 stage_node c9）")
    e3.add_argument("workdir", type=Path)
    e3.add_argument("--after", type=Path, action="append", default=[], help="前面边（E1、E2）的 workdir")
    e3.add_argument("--stage-node-c9", action="store_true", help="五重线同意后才加：stage_node[1][99] c9 换王币")
    e3.add_argument("--drop-live", action="store_true",
                    help="已核实五重掉落发王币（不传则检测 src/、out/multi/five-boss；未上线 = blocked）")
    e4 = sub.add_parser("stage-e4", help="边 E4：作者 0928 晚修订（星铁紫灰图、底框键、悖论文案、034 改价限购、凭证彩框、扭蛋说明）")
    e4.add_argument("workdir", type=Path)
    e4.add_argument("--art-dir", type=Path, default=ART_DIR)
    e4.add_argument("--drop-live", action="store_true", help="同 stage-e3")
    args = parser.parse_args(argv)

    if args.command == "approve":
        result = approve(args.art_dir, by=args.by, evidence=args.evidence, only=args.only)
        print(json.dumps(result, ensure_ascii=False, indent=1))
        return 2 if result["refused"] else 0
    live = G.Live()
    drop_live = True if getattr(args, "drop_live", False) else None
    if args.command == "check":
        result = {"store": str(live.store),
                  "E1": summarize(build_e1(live, args.art_dir)),
                  "E2": summarize(build_e2(live)),
                  "E3": summarize(build_e3(live, drop_live=drop_live)),
                  "E4": summarize(build_e4(live, args.art_dir, drop_live=drop_live))}
        print(json.dumps(result, ensure_ascii=False, indent=1, default=str))
        return 0 if not any(result[e]["problems"] for e in ("E1", "E2", "E3", "E4")) else 2
    overlay = Overlay(getattr(args, "after", []) or [])
    if args.command == "stage-e1":
        out = build_e1(live, args.art_dir)
    elif args.command == "stage-e2":
        out = build_e2(live, overlay)
    elif args.command == "stage-e4":
        out = build_e4(live, args.art_dir, drop_live=drop_live)
    else:
        out = build_e3(live, overlay, stage_node_c9=args.stage_node_c9, drop_live=drop_live)
    result = write_stage(args.workdir, live, out, overlay)
    if result["refused"]:
        print(json.dumps({"refused": True, "problems": result["problems"]}, ensure_ascii=False, indent=1))
        return 2
    plan = result["plan"]
    print(json.dumps({
        "workdir": str(args.workdir), "edge": plan["edge"], "status": plan["status"], "plan": result["plan_path"],
        "tables": {k: {"changed": len(v["changed"]), "deleted": len(plan["deleted"].get(k, []))}
                   for k, v in plan["tables"].items()},
        "files": list(plan["files"]),
        "server": {k: {"added": v["added"], "deleted": len(v["deleted"]), "updated": v["updated"]}
                   for k, v in plan["server"].items()},
        "requires": plan["requires"], "blocked": plan["blocked"], "warnings": plan["warnings"],
        "publish_tables": plan["publish_tables"], "sizes": result["sizes"], "report": result["report"],
    }, ensure_ascii=False, indent=1, default=str))
    return EXIT_CODES[plan["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
