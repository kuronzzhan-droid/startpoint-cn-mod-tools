# -*- coding: utf-8 -*-
"""武器扭蛋 990003：只读 live 的数据构建器 + 暂存（stage）。

设计稿：``${WF_ROOT}/out/武器扭蛋-20260928/设计.md``（§2 卡池行、§3 池子与概率、§4 券、
§5 五重商店、§6 兑换、§10 W2/W3、§12.2 测试）。本文件是 W2 的实现，池子逻辑迁自设计目录的
``design/build_pool_draft.py``（结果与 ``pool_draft.json`` 逐行一致）。

## 产物

客户端（common 层，只动本池自有键）：
  - ``master/gacha/gacha.orderedmap`` 键 990003（47 列）；
  - ``master/gacha/gacha_feature_content.orderedmap`` 外层键 990003（缺它 C2032）；
  - 4 张新 raw_outer 嵌套表 ``master/gacha_odds/cnmod_weapon_gacha_{rarity,3,4,5}.orderedmap``，
    内层每行各自 zlib（与服务端 odds 逐行同序同值，行由 ``wf_gacha_odds_sync.odds_line`` 生成）；
  - ``master/rich_text/rich_text_html.orderedmap`` 键 ``rich_text/cnmod_weapon_gacha_note``（空值）+
    正文 ``rich_text/cnmod_weapon_gacha_note.html.deflate``（raw deflate，照 990001/990002 先例）；
  - ``master/item/item.orderedmap`` 券 999019/999020（23 列，图标复用图集里官方装备券的子纹理）；
  - ``master/shop/boss_coin_shop.orderedmap`` 990099032/033（50 列，模板 990099002）与 990099034
    （禁忌星铁），删除诅咒本体 990099003–031（发布时要 ``--allow-key-deletion``）。
    **价格（武器觉醒与新掉落 0928，设计 ${WF_ROOT}/out/武器觉醒与新掉落-20260928/设计.md §5.4/§5.5）**：
    032 = 深界王币 ×1、033 = 深界王币 ×10、034 = 深界王币 ×500 + 五王心核 ×5 + 深渊觉醒核 ×10 → 禁忌星铁 ×1
    （作者 0928 晚改价，每人限购 60：客户端 c29 max_frequency / c28 单次上限、服务端 stock 同值）；c9 = 6/5/4。
    王币 10000310 / 禁忌星铁 10000311 的道具行与图标由 ``wf_weapon_awaken.py`` 的边 E1/E2 上线；
    它们还没上线、或五重掉落还没发王币（设计 §7 第 7 步；``five_boss_drop_live``，核实后可传 ``--drop-live``）时，
    本构建器**暂缓**这三个商品（既不写回旧价，也不提前写新价），摘要里报出原因。
    ``wf_weapon_awaken.py stage-e3`` 用同一组函数产出同样的目标行；
  - 横幅 ``dynamic/gacha_list_banner/cnmod_weapon_gacha.png``（common）与封面
    ``dynamic/gacha_banner/cnmod_weapon_gacha.png``（**medium 层**），源图在 ``mod-tools/assets/weapon-gacha/``，
    缺图时照样暂存其余内容并在摘要里报出。
服务端（``assets/``，全部**文本级拼接**，别人的 WIP 逐字节不动）：
  ``gacha.json`` +990003、``boss_coin_shop.json["99"]`` −003..031 +032/033、
  ``boss_coin_shop_item_category_map.json`` 同步、``item_sale/item_lookup/item_ids`` +999019/999020、
  镜像 ``cdndata/gacha.json``、``cdndata/gacha_feature_content.json`` +990003。

## 两条纪律

1. **只读 live。** 本文件从不写 store、``.cdn``、``assets/``，也不调用 wf_publish。
   ``stage <workdir>`` 只写 ``<workdir>/stage/**`` 与 ``<workdir>/plan.json``（诅咒武器
   ``apply_fix.py`` 的合同），落 live 与铸边由调用方完成。
2. **幂等。** 构建的是「目标态」，暂存时与 live 逐键比较：已经一致的键不进 plan，
   live 已上线后再跑只会得到空 plan。

用法::

    python mod-tools/wf_weapon_gacha.py check            # 只读体检：摘要 + problems
    python mod-tools/wf_weapon_gacha.py stage <workdir>  # problems 非空时拒绝
    （两者都可加 ``--drop-live``：已核实五重掉落发王币，032–034 才会上架）
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import re
import shutil
import sys
import zipfile
import zlib
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable, Iterable

TOOLS = Path(__file__).resolve().parents[3]  # 仓库根（本文件在 wf/tools/<组>/ 下）
REPO = TOOLS.parent
if str(TOOLS) not in sys.path:
    pass  # Imports resolve from this checkout/package, not external source copies.

import wf_assets as assets  # noqa: E402
import wf_gacha_odds_sync as odds  # noqa: E402
import wf_mod_tool as core  # noqa: E402
import wf_share_update_codec as codec  # noqa: E402

# ---------------------------------------------------------------------------
# 合同常量（改口径只改这里，然后重跑 check / stage）
# ---------------------------------------------------------------------------

GACHA_ID = 990003
GACHA_KEY = str(GACHA_ID)
CODE_NAME = "cnmod_weapon_gacha"
TITLE = "武器扭蛋"
LIST_ORDER = "3"                          # c2，升序；990001=1、990002=2
GACHA_START = "2000-01-01 00:00:00"       # 服务端时间钉在 2025-08-05，起点必须更早
GACHA_END = "2199-12-31 23:59:59"
RANK_RATES = {"normal": [150, 250, 600], "multiGuarantee": [150, 850]}   # 千分比 5★/4★/3★
GUARANTEE_RARITY = 4
EQUIPMENT_MOVIE_PROBABILITY_ID = "1"
REASON_IDS = ("73", "74")                 # c33/c34，照官方装备池
EXCHANGE_COST = 250                       # 全局兑换价（客户端 equipment_exchange_rate 与服务端常量），本池不改
SERVER_COSTS = (75, 750, 25)              # pageKind 2 下不生效，照官方装备池填满类型

ONCE_TICKET_ID = 999019
TEN_TICKET_ID = 999020
ITEM_START = GACHA_START
ITEM_END = GACHA_END

KING_COIN_ID = 10000310                   # 深界王币（五重掉落；道具行由 wf_weapon_awaken 边 E2 上线）
STAR_STEEL_ID = 10000311                  # 禁忌星铁（通用突破材料；同上）
STAR_STEEL_THUMB = "item/materials/mod/cursed/forbidden_star_steel"   # 禁忌星铁 c3（设计 §5.2/§6.4；边 E1 上线）
FIVE_KING_CORE_ID = 10000147              # 五王心核（五重材料，已上线）
ABYSS_CORE_ID = 2370100                   # 深渊觉醒核（深渊连战材料，已上线）
#: PARADOX 的类别称呼。作者 0928「武器PARADOX归类为悖论武器，除了武器名字，其他地方都不要英文的，写悖论」：
#: 装备名「PARADOX」、强化名「PARADOX·终式」以外的玩家可见文字一律写「悖论武器」。
PARADOX_CLASS = "悖论武器"
#: 五重掉落（设计 §4.3、§7 第 6 步，五重线实现）：源码与编译产物（服务端跑的是 out/）都出现王币 ID 才算上线。
FIVE_BOSS_DROP_SOURCES = (REPO / "src" / "multi" / "five-boss", REPO / "out" / "multi" / "five-boss")
SHOP_CATEGORY = "99"
SHOP_TEMPLATE_KEY = "990099002"
SHOP_START = "2000-01-01 00:00:00"
SHOP_END = "2099-12-31 23:59:59"
SHOP_STOCK = 9999                         # 服务端 stock：不限购的商品
SHOP_PER_PURCHASE = "99"                  # c28 buy_max_count：单次购买上限
SHOP_DESC_LIMIT = 60                      # 官方 boss_coin_shop c10 实测上限
DELETED_SHOP_KEYS = tuple(str(k) for k in range(990099003, 990099032))   # 诅咒本体 29 键


@dataclass(frozen=True)
class Ticket:
    item_id: int
    code: str
    name: str
    icon: str                       # 必须是 item/sprite_sheet 图集里已有的子纹理，否则 C8004
    description: str
    gacha_ticket_type: str          # item c13：3=装备单抽 4=装备十连（照 20005/20006）
    template_item: str              # 形状核对用的官方装备券
    shop_key: str
    shop_order: str                 # boss_coin_shop c9，领主币商店按 c9 倒序
    costs: tuple                    # ((item_id, amount), ...)
    shop_description: str


TICKETS = (
    Ticket(ONCE_TICKET_ID, "mod_weapon_gacha_once", "武器扭蛋券",
           "item/spends/tickets/ticket_equipment_001",
           "可进行1次「武器扭蛋」抽取的专用扭蛋券（五重决战兑换）。", "3", "20005",
           "990099032", "6", ((KING_COIN_ID, 1),),
           "消耗深界王币兑换「武器扭蛋」单抽券。持有武器扭蛋券时才会显示该卡池；兑换点数不会丢失。"),
    Ticket(TEN_TICKET_ID, "mod_weapon_gacha_ten", "武器扭蛋十连券",
           "item/spends/tickets/ticket_equipment_002",
           "可进行1次「武器扭蛋」10连抽取的专用扭蛋券（五重决战兑换）。", "4", "20006",
           "990099033", "5", ((KING_COIN_ID, 10),),
           "消耗深界王币兑换「武器扭蛋」十连券。持有武器扭蛋券时才会显示该卡池；兑换点数不会丢失。"),
)


@dataclass(frozen=True)
class ShopProduct:
    """五重商店（类目 99）的一件商品：c6 名称、c9 排序、c10 说明、c12 商品图、c13 框、c17–c24 成本、c33 奖励道具。"""

    shop_key: str
    name: str
    icon: str
    shop_order: str
    costs: tuple                    # ((item_id, amount), ...)
    shop_description: str
    reward_item_id: int
    frame: str = "5"                # c13
    #: 每人限购（None = 不限）：客户端 c29 max_frequency、c28 单次上限取 min(99, 限购)、服务端 stock 同值
    #: （先例：五重商店 990099001 死亡使者 c28 = c29 = 5、服务端 stock 5）
    limit: int | None = None


def ticket_product(ticket: Ticket) -> ShopProduct:
    return ShopProduct(ticket.shop_key, ticket.name, ticket.icon, ticket.shop_order, ticket.costs,
                       ticket.shop_description, ticket.item_id)


#: 990099034：500 王币 + 5 五王心核 + 10 深渊觉醒核 → 1 禁忌星铁，每人限购 60（作者 0928「一个钢要500个币5个五王核心
#: 10个深渊觉醒核，限购60个」；设计 §5.4 原价 500 王币）。c12 是禁忌星铁的 c3 独立 PNG（边 E1）。
STAR_STEEL_LIMIT = 60
STAR_STEEL_PRODUCT = ShopProduct(
    "990099034", "禁忌星铁", STAR_STEEL_THUMB, "4", ((KING_COIN_ID, 500), (FIVE_KING_CORE_ID, 5), (ABYSS_CORE_ID, 10)),
    f"消耗深界王币、五王心核与深渊觉醒核兑换禁忌星铁。可代替本体突破诅咒武器与{PARADOX_CLASS}（每次突破1个）。",
    STAR_STEEL_ID, limit=STAR_STEEL_LIMIT)


def shop_products() -> tuple:
    """五重商店自有商品，按 c9 倒序即界面自上而下：单抽券 6、十连券 5、禁忌星铁 4（设计 §5.4）。"""
    return tuple(ticket_product(t) for t in TICKETS) + (STAR_STEEL_PRODUCT,)


def five_boss_drop_live(sources: Iterable = FIVE_BOSS_DROP_SOURCES) -> bool:
    """只读：五重掉落是否已经发王币。``sources`` 里每一项（目录则扫其下 .ts/.js，测试文件除外）都要
    出现 ``KING_COIN_ID``——源码写了但没 tsc，服务端跑的仍是旧 out/，不算上线。"""
    pattern = re.compile(rf"(?<![0-9]){KING_COIN_ID}(?![0-9])")
    for source in sources:
        source = Path(source)
        files = sorted(f for ext in ("*.ts", "*.js") for f in source.glob(ext)) if source.is_dir() else [source]
        hit = False
        for path in files:
            if ".test." in path.name:
                continue
            try:
                if pattern.search(path.read_text(encoding="utf-8")):
                    hit = True
                    break
            except OSError:
                continue
        if not hit:
            return False
    return True


def shop_prerequisites(item_rows: dict, has_file: Callable[[str], bool], *, drop_live: bool) -> list:
    """032–034 能否上架。-> 未满足的原因（空 = 可上架）。

    ``item_rows`` 是 item 表的 {键: 行}，``has_file(逻辑路径)`` 判断 store 里有没有该文件（缺行 C8601、缺图）；
    ``drop_live`` = 五重掉落已发王币（设计 §7 第 7 步：否则券不再收结晶、王币却没有来源）。
    wf_weapon_awaken 的 ``--after`` 叠加视图也走这个函数；掉落不能靠叠加满足。"""
    waiting: list = []
    if not drop_live:
        waiting.append(f"五重掉落还没有深界王币 {KING_COIN_ID}（src/ 与 out/multi/five-boss；五重线发布后重跑，"
                       f"或核实后传 --drop-live）")
    needed = sorted({i for p in shop_products() for i, _ in p.costs} | {p.reward_item_id for p in shop_products()})
    for item_id in needed:
        if str(item_id) not in item_rows:
            waiting.append(f"道具 {item_id} 不在 live item 表（先发 wf_weapon_awaken 边 E2）")
    for product in shop_products()[len(TICKETS):]:      # 券的商品图是 item/sprite_sheet 图集子纹理，另查
        if not has_file(product.icon + ".png"):
            waiting.append(f"商品 {product.shop_key} 的商品图 {product.icon}.png 不在 store（先发 wf_weapon_awaken 边 E1）")
    return waiting

# ---- 池子 ------------------------------------------------------------------
DEATHBRINGER = 5900101
PARADOX = 5920001
CURSED = tuple(range(5910101, 5910130))           # 29 把
ABYSS = tuple(range(8000101, 8000116))            # 15 把
EXCLUDED_OFFICIAL = {5095000: "官方表名称/说明均为「占位」，不是实装武器"}
CURSED_EACH_PCT = Fraction(3, 10)                 # 每把 0.3%
DEATHBRINGER_PCT = Fraction(1, 10)                # 0.1%，UP

# 「全部官方武器」= 官方 1.4.0 全量档装备表（钉哈希；live 里多出的 57 行全是非官方）
OFFICIAL_ARCHIVE_DIR = "archive-common-full"
OFFICIAL_ARCHIVE_HINT = "pinball-1.4.0-96-*.zip"
OFFICIAL_ARCHIVE_GLOB = "pinball-1.4.0-*.zip"
OFFICIAL_EQUIPMENT_SHA256 = "e45920b55bb64115cc29a567e714be4cf5f77ad778583a1b94263b04317c032f"
OFFICIAL_WEAPON_COUNTS = {1: 3, 2: 6, 3: 37, 4: 80, 5: 290}     # 魂珠/奖杯/NPC 专用已排除
POOL_RANKS = (5, 4, 3)                            # 客户端装备池只有 3 张概率表，★1/★2 放不进
GROUP_OF_RANK = {rank: group for group, rank in odds.GROUP_RANK.items()}

# ---- 逻辑路径 --------------------------------------------------------------
GACHA_LOGICAL = "master/gacha/gacha.orderedmap"
FEATURE_LOGICAL = "master/gacha/gacha_feature_content.orderedmap"
RICH_TEXT_MASTER_LOGICAL = "master/rich_text/rich_text_html.orderedmap"
ITEM_LOGICAL = "master/item/item.orderedmap"
SHOP_LOGICAL = "master/shop/boss_coin_shop.orderedmap"
EQUIPMENT_LOGICAL = "master/item/equipment.orderedmap"
ITEM_ATLAS_LOGICAL = "item/sprite_sheet.atlas.amf3.deflate"

RARITY_ODDS_ID = f"{CODE_NAME}_rarity"
EQUIPMENT_ODDS_IDS = {3: f"{CODE_NAME}_3", 4: f"{CODE_NAME}_4", 5: f"{CODE_NAME}_5"}
RICH_TEXT_ID = f"rich_text/{CODE_NAME}_note"
RICH_TEXT_BODY_LOGICAL = f"{RICH_TEXT_ID}.html.deflate"
LIST_BANNER = f"dynamic/gacha_list_banner/{CODE_NAME}"
COVER = f"dynamic/gacha_banner/{CODE_NAME}"
MEDIUM_PREFIX = "medium:"


def odds_logical(string_id: str) -> str:
    return f"master/gacha_odds/{string_id}.orderedmap"


ODDS_LOGICALS = tuple(odds_logical(s) for s in (RARITY_ODDS_ID, *(EQUIPMENT_ODDS_IDS[r] for r in (3, 4, 5))))


@dataclass(frozen=True)
class Art:
    source: str                     # mod-tools/assets/weapon-gacha/ 下的文件名
    logical: str
    root: str                       # upload | medium
    size: tuple
    opaque: bool

    @property
    def plan_key(self) -> str:
        """wf_publish --tables 认的写法：medium 层带 ``medium:`` 前缀。"""
        return (MEDIUM_PREFIX if self.root == "medium" else "") + self.logical


ART_DIR = TOOLS / "assets" / "weapon-gacha"
ARTS = (
    Art("list_banner.png", f"{LIST_BANNER}.png", "upload", (510, 180), False),
    Art("cover.png", f"{COVER}.png", "medium", (1440, 1789), True),
)

# ---- 服务端文件（相对 assets/） -------------------------------------------
SERVER_GACHA = "gacha.json"
SERVER_CDN_GACHA = "cdndata/gacha.json"
SERVER_CDN_FEATURE = "cdndata/gacha_feature_content.json"
SERVER_SHOP = "boss_coin_shop.json"
SERVER_SHOP_MAP = "boss_coin_shop_item_category_map.json"
SERVER_ITEM_SALE = "item_sale.json"
SERVER_ITEM_LOOKUP = "item_lookup.json"
SERVER_ITEM_IDS = "item_ids.json"
SERVER_EQUIPMENT_IDS = "equipment_ids.json"
SERVER_MAX_LEVEL = "equipment_max_level.json"

# 发布顺序（设计 §11 第 4 步），只列实际暂存了的
PUBLISH_ORDER = (GACHA_LOGICAL, FEATURE_LOGICAL, *ODDS_LOGICALS, RICH_TEXT_MASTER_LOGICAL,
                 RICH_TEXT_BODY_LOGICAL, ITEM_LOGICAL, SHOP_LOGICAL, *(a.plan_key for a in ARTS))


class SpliceError(ValueError):
    """服务端 JSON 文本级拼接无法安全完成（样式探测失败/往返不一致）。"""


# ---------------------------------------------------------------------------
# live 只读接口
# ---------------------------------------------------------------------------

def _default_cdn_root() -> Path:
    try:
        return Path(core.resolve_cdn_root())
    except Exception:  # noqa: BLE001 - 解析失败就退回仓内默认位置
        return REPO / ".cdn" / "cn"


class Live:
    """只读 live：store 三根、服务端 ``assets/``、官方 1.4.0 全量档。全部带缓存，从不写。"""

    def __init__(self, store: Path | None = None, assets_dir: Path | None = None,
                 cdn_root: Path | None = None):
        resolved = store or core.resolve_active_store(REPO)
        if not resolved:
            raise SystemExit("未找到 store。" + core.TARGET_STORE_HINT)
        self.store = Path(resolved).resolve()
        self.assets_dir = Path(assets_dir or REPO / "assets").resolve()
        self.cdn_root = Path(cdn_root or _default_cdn_root())
        self._raw: dict = {}
        self._rows: dict = {}
        self._flat: dict = {}
        self._server: dict = {}
        self._json: dict = {}

    # -- store --------------------------------------------------------------
    def path(self, logical: str, root: str = "upload") -> Path:
        return assets.path_in_root(self.store, root, logical)

    def raw(self, logical: str, root: str = "upload") -> bytes | None:
        key = (root, logical)
        if key not in self._raw:
            path = self.path(logical, root)
            self._raw[key] = path.read_bytes() if path.is_file() else None
        return self._raw[key]

    def rows(self, logical: str) -> dict:
        """外层 orderedmap 的原始行字节（压缩态/嵌套态原样）。"""
        if logical not in self._rows:
            raw = self.raw(logical)
            if raw is None:
                raise FileNotFoundError(f"store 里没有 {logical}")
            self._rows[logical] = codec.unpack(raw)
        return self._rows[logical]

    def flat(self, logical: str) -> dict:
        """平表：{键: 首行单元格}；空行给 []。"""
        if logical not in self._flat:
            out = {}
            for key, blob in self.rows(logical).items():
                text = zlib.decompress(blob).decode("utf-8") if blob else ""
                parsed = core.read_csv_lines(text)
                out[key] = parsed[0] if parsed else []
            self._flat[logical] = out
        return self._flat[logical]

    def atlas_names(self) -> set:
        raw = self.raw(ITEM_ATLAS_LOGICAL)
        if raw is None:
            return set()
        entries = core.AMF3Reader(zlib.decompress(raw, -15)).read_value()
        return {str(e["n"]) for e in entries if isinstance(e, dict) and "n" in e}

    # -- 服务端 ------------------------------------------------------------------
    def server_bytes(self, name: str) -> bytes | None:
        if name not in self._server:
            path = self.assets_dir / name
            self._server[name] = path.read_bytes() if path.is_file() else None
        return self._server[name]

    def server_text(self, name: str) -> str | None:
        raw = self.server_bytes(name)
        return None if raw is None else raw.decode("utf-8")   # 不走文本模式：CRLF 必须原样

    def server_json(self, name: str) -> Any:
        if name not in self._json:
            text = self.server_text(name)
            self._json[name] = None if text is None else json.loads(text)
        return self._json[name]

    # -- 官方基准 ------------------------------------------------------------------
    def official_equipment(self) -> bytes:
        digest = core.sha1_path(EQUIPMENT_LOGICAL)
        member = f"production/upload/{digest[:2]}/{digest[2:]}"
        base = self.cdn_root / OFFICIAL_ARCHIVE_DIR
        hinted = sorted(base.glob(OFFICIAL_ARCHIVE_HINT))
        rest = [p for p in sorted(base.glob(OFFICIAL_ARCHIVE_GLOB)) if p not in hinted]
        for path in hinted + rest:
            with zipfile.ZipFile(path) as archive:
                try:
                    return archive.read(member)
                except KeyError:
                    continue
        raise FileNotFoundError(f"官方 1.4.0 全量档里找不到 {EQUIPMENT_LOGICAL}（{base}）")


# ---------------------------------------------------------------------------
# 池子与概率
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PoolRow:
    id: int
    rank: int
    weight: int
    rate_up: bool
    limited: bool
    exchangeable: bool

    def server_entry(self) -> dict:
        return {"id": self.id, "rank": self.rank, "odds": self.weight, "isRateUp": self.rate_up,
                "isLimited": self.limited, "isExchangeable": self.exchangeable, "rarity": 0.0}


def official_weapons(raw: bytes) -> dict:
    """官方装备表 -> {星级: [武器 id 升序]}。排除魂珠（c2=1）、奖杯、NPC 专用。"""
    by_rank: dict = {}
    rows = codec.unpack(raw)
    for key in sorted(rows, key=int):
        blob = rows[key]
        if not blob:
            continue
        row = core.read_csv_lines(zlib.decompress(blob).decode("utf-8"))[0]
        string_id = row[0]
        if row[2] != "0" or "trophy" in string_id or string_id.startswith("non_playable"):
            continue
        by_rank.setdefault(int(row[11]), []).append(int(key))
    return by_rank


def five_star_weights(n_other: int) -> tuple:
    """5★ 档内整数权重：诅咒各 0.3%、死亡使者 0.1%，其余 n_other 把均分剩余。

    -> (诅咒每把, 死亡使者, 其余每把, 档内合计)；按最小公倍数取整，概率是精确值。
    """
    tier_pct = Fraction(RANK_RATES["normal"][0] * 100, sum(RANK_RATES["normal"]))
    cursed_share = CURSED_EACH_PCT / tier_pct
    deathbringer_share = DEATHBRINGER_PCT / tier_pct
    other_share = (1 - len(CURSED) * cursed_share - deathbringer_share) / n_other
    if other_share <= 0:
        raise ValueError(f"5★ 档剩余份额 {other_share} ≤ 0，诅咒/死亡使者概率超出 5★ 合计")
    den = math.lcm(cursed_share.denominator, deathbringer_share.denominator, other_share.denominator)
    weights = (int(cursed_share * den), int(deathbringer_share * den), int(other_share * den))
    total = len(CURSED) * weights[0] + weights[1] + n_other * weights[2]
    if total != den:
        raise ValueError(f"5★ 权重合计 {total} != {den}")
    return (*weights, den)


def build_tiers(official: dict) -> dict:
    """{星级: [PoolRow]}。顺序 = 概率页与兑换列表的显示顺序：
    死亡使者（UP）→ 诅咒 → PARADOX → 深渊 → 官方（id 升序）。"""
    off5 = [i for i in official.get(5, []) if i not in EXCLUDED_OFFICIAL]
    w_cursed, w_deathbringer, w_other, _ = five_star_weights(len(ABYSS) + len(off5))
    rows5 = [PoolRow(DEATHBRINGER, 5, w_deathbringer, True, True, False)]
    rows5 += [PoolRow(i, 5, w_cursed, False, True, True) for i in CURSED]
    rows5 += [PoolRow(PARADOX, 5, 0, False, True, False)]
    rows5 += [PoolRow(i, 5, w_other, False, True, False) for i in ABYSS]
    rows5 += [PoolRow(i, 5, w_other, False, False, False) for i in off5]
    return {5: rows5,
            4: [PoolRow(i, 4, 1, False, False, False) for i in official.get(4, [])],
            3: [PoolRow(i, 3, 1, False, False, False) for i in official.get(3, [])]}


def rarity_weight(rank: int) -> int:
    return dict(zip((5, 4, 3), RANK_RATES["normal"]))[rank]


def guarantee_weight(rank: int) -> int:
    """GachaRarityOddsLogic.getRarityWeight(保底位)：保底星级吃掉更低档的权重，高档不变。"""
    if rank < GUARANTEE_RARITY:
        return 0
    if rank == GUARANTEE_RARITY:
        return sum(rarity_weight(r) for r in (3, 4) if r <= GUARANTEE_RARITY)
    return rarity_weight(rank)


def exact_rates(tiers: dict) -> dict:
    """{id: 精确百分比 Fraction}（通常位）。"""
    total = sum(RANK_RATES["normal"])
    out = {}
    for rank, rows in tiers.items():
        tier_total = sum(r.weight for r in rows)
        for row in rows:
            out[row.id] = Fraction(row.weight * rarity_weight(rank) * 100, tier_total * total)
    return out


def client_display(tiers: dict, *, guarantee: bool = False) -> dict:
    """客户端概率页显示串（不带 %）：GachaOddsEquipmentLogic.as:41 浮点式 + 向下取整到 3 位。"""
    total = sum(RANK_RATES["normal"])
    out = {}
    for rank, rows in tiers.items():
        tier_total = sum(r.weight for r in rows)
        rank_w = guarantee_weight(rank) if guarantee else rarity_weight(rank)
        for row in rows:
            out[row.id] = odds.fmt_odds(float(row.weight) * rank_w * 100 / (tier_total * total))
    return out


def server_pool(tiers: dict) -> dict:
    return {GROUP_OF_RANK[rank]: [row.server_entry() for row in tiers[rank]] for rank in POOL_RANKS}


def server_gacha(tiers: dict) -> dict:
    single, multi, discount = SERVER_COSTS
    return {
        "type": 1, "paymentType": 0, "pageKind": 2,
        "singleCost": single, "multiCost": multi, "discountCost": discount,
        "onceTicketItemId": ONCE_TICKET_ID, "tenTicketItemId": TEN_TICKET_ID,
        "wildcardTicketAvailable": False,
        "rarityOddsId": RARITY_ODDS_ID, "guaranteeRarity": GUARANTEE_RARITY,
        "rankRates": {"normal": list(RANK_RATES["normal"]),
                      "multiGuarantee": list(RANK_RATES["multiGuarantee"])},
        "equipmentMovieProbabilityId": EQUIPMENT_MOVIE_PROBABILITY_ID,
        "startDate": GACHA_START, "endDate": GACHA_END, "name": TITLE,
        "pool": server_pool(tiers),
    }


def odds_tables(pool: dict) -> dict:
    """{odds stringId: [内层明文行]}，直接由服务端池条目生成（同序同值）。"""
    out = {RARITY_ODDS_ID: odds.rarity_lines(RANK_RATES["normal"])}
    for rank in POOL_RANKS:
        out[EQUIPMENT_ODDS_IDS[rank]] = [odds.odds_line(e, rank, odds.EQUIPMENT_BOOL_FIELDS)
                                         for e in pool[GROUP_OF_RANK[rank]]]
    return out


def nested_bytes(string_id: str, lines: list) -> bytes:
    return odds.build_nested(string_id, [str(i) for i in range(len(lines))], lines)


def read_nested_bytes(raw: bytes, label: str) -> tuple:
    """-> (外层键, 内层键, 明文行)；与 wf_gacha_odds_sync.read_nested 同义，只是吃字节。"""
    outer = codec.unpack(raw)
    if len(outer) != 1:
        raise ValueError(f"{label}: 外层应恰好 1 个键，实际 {len(outer)}")
    (outer_key, inner_raw), = outer.items()
    inner = codec.unpack(inner_raw)
    return outer_key, list(inner), [zlib.decompress(v).decode("utf-8") for v in inner.values()]


# ---------------------------------------------------------------------------
# 客户端行
# ---------------------------------------------------------------------------

def gacha_row() -> list:
    """47 列（设计 §2.2）。"""
    return [
        CODE_NAME, TITLE, LIST_ORDER, LIST_BANNER, "2",           # c0-c4：page_kind 2 = TicketOnly
        "", "", "", "",                                           # c5-c8：page_kind 2 不读
        "1", str(GUARANTEE_RARITY), RARITY_ODDS_ID, RICH_TEXT_ID, "1",   # c9-c13：c13=1 装备池
        "", "", "", "", "", "", "", "",                           # c14-c21：角色池专用
        EQUIPMENT_ODDS_IDS[3], EQUIPMENT_ODDS_IDS[4], EQUIPMENT_ODDS_IDS[5],   # c22-c24
        EQUIPMENT_MOVIE_PROBABILITY_ID, "false",                  # c25 演出概率；c26 禁用通用装备券
        str(ONCE_TICKET_ID), str(TEN_TICKET_ID),                  # c27/c28 专用券
        GACHA_START, GACHA_END, "(None)", "false",                # c29-c32
        REASON_IDS[0], REASON_IDS[1], "(None)", "(None)", "(None)",   # c33-c37
        "false", "(None)", "(None)", "(None)", "(None)",          # c38-c42
        "false", "true", "(None)", "false",                       # c43；c44=兑换按钮；c45；c46
    ]


def feature_cells() -> list:
    """gacha_feature_content 内层行 "1"：kind-1 静态封面（9 列）。"""
    return ["1", COVER, "", "", "", "", "(None)", "", ""]


def item_row(ticket: Ticket) -> list:
    """23 列（设计 §4.1）；c6=8 GachaTicket、c14=4 背包「兑换券」页。"""
    return [ticket.code, str(ticket.item_id), ticket.name, ticket.icon, "(None)", ticket.description,
            "8", "", "", "", "", "", "", ticket.gacha_ticket_type, "4", "(None)", "100", "5", "9999",
            ITEM_START, ITEM_END, "false", ""]


def shop_row(product: ShopProduct, template: list) -> list:
    """50 列，以 990099002 为模板，只改本商品自有列（设计 §5.1；武器觉醒设计 §5.4）。"""
    row = list(template)
    row[6] = product.name
    row[9] = product.shop_order
    row[10] = product.shop_description
    row[12] = product.icon
    row[13] = product.frame
    cells: list = []
    for item_id, amount in product.costs:
        cells += [str(item_id), str(amount)]
    while len(cells) < 8:
        cells += ["(None)", ""]
    row[17:25] = cells
    row[25], row[26] = SHOP_START, SHOP_END
    row[27], row[28] = "1", SHOP_PER_PURCHASE
    row[29], row[30], row[31] = "(None)", "(None)", "(None)"
    if product.limit is not None:                                               # c28 单次上限 / c29 max_frequency
        row[28], row[29] = str(min(int(SHOP_PER_PURCHASE), product.limit)), str(product.limit)
    row[32], row[33], row[34] = "0", str(product.reward_item_id), "1"          # c32=0 Item
    return row


def server_shop_entry(product: ShopProduct) -> dict:
    return {"costs": [{"id": i, "amount": a} for i, a in product.costs],
            "rewards": [{"type": 0, "id": product.reward_item_id, "count": 1}],   # ShopItemRewardType 0 = ITEM
            "availableFrom": SHOP_START, "availableUntil": SHOP_END,
            "stock": SHOP_STOCK if product.limit is None else product.limit}


def shop_targets(template: list) -> tuple:
    """-> ({商店键: 50 列行}, {商店键: 服务端条目}, problems)。wf_weapon_awaken stage-e3 共用。"""
    problems: list = []
    rows: dict = {}
    if len(template) != 50 or template[0] != SHOP_CATEGORY:
        return {}, {}, [f"商店模板 {SHOP_TEMPLATE_KEY} 形状漂移: {len(template)} 列"]
    for product in shop_products():
        rows[product.shop_key] = shop_row(product, template)
        if len(rows[product.shop_key]) != 50:
            problems.append(f"商店 {product.shop_key} {len(rows[product.shop_key])} 列 != 50")
        if len(product.shop_description) > SHOP_DESC_LIMIT or "," in product.shop_description \
                or "\n" in product.shop_description:
            problems.append(f"商店 {product.shop_key} 说明超 {SHOP_DESC_LIMIT} 字或含半角逗号/换行")
        if "PARADOX" in product.shop_description:
            problems.append(f"商店 {product.shop_key} 说明写了英文 PARADOX（作者 0928：武器名以外写「{PARADOX_CLASS}」）")
        if not 1 <= len(product.costs) <= 4:
            problems.append(f"商店 {product.shop_key} 成本 {len(product.costs)} 项，客户端只有 c17–c24 四格")
        if product.limit is not None and not 1 <= product.limit <= SHOP_STOCK:
            problems.append(f"商店 {product.shop_key} 限购 {product.limit} 须在 1–{SHOP_STOCK}")
    orders = [int(p.shop_order) for p in shop_products()]
    if orders != sorted(orders, reverse=True) or len(set(orders)) != len(orders):
        problems.append(f"商店 c9 不是严格倒序: {orders}")
    return rows, {p.shop_key: server_shop_entry(p) for p in shop_products()}, problems


def shop_occupancy_problems(live_shop: dict, live_shop_server: dict) -> list:
    """同一商店键在 live 里若奖励的不是本商品（客户端 c33 / 服务端 rewards），视为被占用。"""
    problems: list = []
    for product in shop_products():
        current = live_shop.get(product.shop_key)
        if current and current[33:34] != [str(product.reward_item_id)]:
            problems.append(f"商店 {product.shop_key} 已被占用: {current[6:7]}")
        have = live_shop_server.get(product.shop_key)
        want = server_shop_entry(product)["rewards"]
        if have is not None and have.get("rewards") != want:
            problems.append(f"服务端商店 {product.shop_key} 已被占用: {have.get('rewards')}")
    return problems


def _pct(value: Fraction) -> str:
    """精确百分比写成有限小数（最多 4 位）；除不尽时给 4 位近似并加「约」。"""
    for places in range(5):
        scaled = value * 10 ** places
        if scaled.denominator == 1:
            return f"{float(value):.{places}f}%"
    return f"约{float(value):.4f}%"


def rich_text_html(tiers: dict, names: dict, capped: int) -> str:
    """注意事项正文（设计 §2.3 各点），格式照 990001/990002 先例。数字全部由池子精确推导。"""
    rates = exact_rates(tiers)
    total = sum(RANK_RATES["normal"])
    g_total = sum(RANK_RATES["multiGuarantee"])
    p5, p4, p3 = (Fraction(100 * w, total) for w in RANK_RATES["normal"])
    g5, g4 = (Fraction(100 * w, g_total) for w in RANK_RATES["multiGuarantee"])
    others = [r for r in tiers[5] if r.id not in (DEATHBRINGER, PARADOX) and r.id not in CURSED]
    n_abyss = sum(1 for r in others if r.id in ABYSS)
    other_each = {rates[r.id] for r in others}
    if len(other_each) != 1:
        raise ValueError(f"其余 5★ 概率不唯一: {sorted(other_each)[:3]}")
    four_each = {rates[r.id] for r in tiers[4]}
    three_each = {rates[r.id] for r in tiers[3]}
    if len(four_each) != 1 or len(three_each) != 1:
        raise ValueError("4★/3★ 档内不是等权")
    cursed_each = rates[CURSED[0]]
    lines = [
        "本扭蛋长期开放，仅可使用武器扭蛋券或武器扭蛋十连券抽取；两种券可在五重决战的「兑换道具」中使用五重决战材料兑换。",
        "本扭蛋不接受星导石或付费星导石抽取，也不接受通用装备扭蛋券。",
        f"★5武器总出现概率为{_pct(p5)}，★4武器为{_pct(p4)}，★3武器为{_pct(p3)}。",
        f"{names[DEATHBRINGER]}概率UP，出现概率为{_pct(rates[DEATHBRINGER])}。",
        f"{len(CURSED)}把诅咒武器各为{_pct(cursed_each)}，合计{_pct(cursed_each * len(CURSED))}。",
        f"{PARADOX_CLASS}登记于本扭蛋但出现概率为{_pct(rates[PARADOX])}，不会被抽出，且不可兑换。",
        f"其余{len(others)}把★5武器（深渊武器{n_abyss}把、常规★5武器{len(others) - n_abyss}把）"
        f"各{_pct(next(iter(other_each)))}，合计{_pct(sum(rates[r.id] for r in others))}。",
        f"★4武器{len(tiers[4])}把各{_pct(next(iter(four_each)))}；"
        f"★3武器{len(tiers[3])}把各{_pct(next(iter(three_each)))}。",
        "使用1张武器扭蛋券可抽取1次；使用1张武器扭蛋十连券可连续抽取10次。",
        f"10连抽取的第10次必定获得★{GUARANTEE_RARITY}以上武器，其中★5武器的出现概率仍为{_pct(g5)}，"
        f"★4武器为{_pct(g4)}。",
        f"每次抽取累计1点兑换点数；每{EXCHANGE_COST}点可在「兑换装备」中兑换1把任选的诅咒武器，其他武器不可兑换。",
        "重复获得已持有的武器时会累积重复数，可用于突破。"
        + (f"池中{capped}把活动奖励武器无法突破，重复获得后没有额外用途。" if capped else ""),
        "未持有武器扭蛋券时本扭蛋不会显示在扭蛋列表中；已累计的兑换点数不会丢失，可先兑换1张武器扭蛋券再进入本扭蛋兑换。",
        "因各武器显示的获得概率仅精确至小数点后3位，获得概率总和可能不会达到100%。",
    ]
    body = "<br/>\n".join(f"    <p>・{line}</p>" for line in lines)
    return f"""<!DOCTYPE html/>
<html lang="zh-CN">
<head>
  <meta charset="utf-8"/>
  <title>{TITLE}注意事项</title>
  <link rel="stylesheet" type="text/css" href="style.css"/>
</head>
<body class="body" style_id="1">
  <div class="container">
{body}
  </div>
</body>
</html>
"""


def deflate_raw(text: str) -> bytes:
    compressor = zlib.compressobj(level=9, wbits=-15)
    return compressor.compress(text.encode("utf-8")) + compressor.flush()


def inflate_raw(raw: bytes) -> str:
    return zlib.decompress(raw, -15).decode("utf-8")


# ---------------------------------------------------------------------------
# 构建（目标态 + problems）
# ---------------------------------------------------------------------------

@dataclass
class ServerEdit:
    """一个服务端 JSON 的键级改动。path=容器所在路径；style=新值的排版（由兄弟键验证）。"""

    path: tuple = ()
    upsert: dict = field(default_factory=dict)
    delete: tuple = ()
    append: tuple = ()
    style: str = "default"
    siblings: tuple = ()


def build(live: Live, *, drop_live: bool | None = None) -> dict:
    """只读 live，返回目标态。``problems`` 非空时 stage 拒绝。

    ``drop_live``：None = 按 ``five_boss_drop_live()`` 检测；True = 调用方已核实五重掉落上线（``--drop-live``）。"""
    problems: list = []
    report: dict = {}

    # -- 官方基准与池子 ----------------------------------------------------------
    official_raw = live.official_equipment()
    official_sha = hashlib.sha256(official_raw).hexdigest()
    if official_sha != OFFICIAL_EQUIPMENT_SHA256:
        problems.append(f"官方 1.4.0 装备表哈希漂移: {official_sha}")
    official = official_weapons(official_raw)
    counts = {rank: len(ids) for rank, ids in sorted(official.items())}
    if counts != OFFICIAL_WEAPON_COUNTS:
        problems.append(f"官方武器分档数漂移: {counts} != {OFFICIAL_WEAPON_COUNTS}")
    for excluded in EXCLUDED_OFFICIAL:
        if excluded not in official.get(5, []):
            problems.append(f"排除项 {excluded} 不在官方 ★5 里（口径漂移）")
    custom_in_official = sorted(set(CURSED + ABYSS + (DEATHBRINGER, PARADOX))
                                & {i for ids in official.values() for i in ids})
    if custom_in_official:
        problems.append(f"自制武器出现在官方基准里: {custom_in_official}")

    tiers = build_tiers(official)
    equipment = live.flat(EQUIPMENT_LOGICAL)
    server_equipment_ids = set(live.server_json(SERVER_EQUIPMENT_IDS) or [])
    seen: set = set()
    for rank, rows in tiers.items():
        for row in rows:
            cells = equipment.get(str(row.id))
            if not cells:
                problems.append(f"池内 {row.id} 不在 live 装备表")
            else:
                if len(cells) <= 11 or cells[11] != str(rank):
                    problems.append(f"池内 {row.id} 星级 {cells[11] if len(cells) > 11 else '?'} != 档 {rank}")
                if cells[2] != "0":
                    problems.append(f"池内 {row.id} c2={cells[2]} 不是武器")
            if row.id in seen:
                problems.append(f"池内重复 id {row.id}")
            seen.add(row.id)
            if row.id not in server_equipment_ids:
                problems.append(f"池内 {row.id} 不在服务端 {SERVER_EQUIPMENT_IDS}")

    rates = exact_rates(tiers)
    if sum(rates.values()) != 100:
        problems.append(f"精确概率合计 {sum(rates.values())} != 100")
    five_total = sum(rates[r.id] for r in tiers[5])
    if five_total != Fraction(RANK_RATES["normal"][0] * 100, sum(RANK_RATES["normal"])):
        problems.append(f"★5 合计 {five_total}")
    if any(rates[i] != CURSED_EACH_PCT for i in CURSED):
        problems.append("诅咒武器不是每把 0.3%")
    if rates[DEATHBRINGER] != DEATHBRINGER_PCT or rates[PARADOX] != 0:
        problems.append("死亡使者/PARADOX 概率不符")
    exchangeable = [r.id for rank in POOL_RANKS for r in tiers[rank] if r.exchangeable]
    if exchangeable != list(CURSED):
        problems.append(f"可兑换集合不是 29 把诅咒武器: {exchangeable[:5]}...")
    display = client_display(tiers)
    for item_id, want in ((CURSED[0], "0.300"), (DEATHBRINGER, "0.100"), (PARADOX, "0.000")):
        if display[item_id] != want:
            problems.append(f"{item_id} 显示 {display[item_id]}% != {want}%")
    guarantee_display = [odds.fmt_rarity(guarantee_weight(r) / 10) for r in (5, 4)]
    expected_guarantee = [odds.fmt_rarity(v / 10) for v in RANK_RATES["multiGuarantee"]]
    if guarantee_display != expected_guarantee:
        problems.append(f"客户端保底位显示 {guarantee_display} 与服务端 multiGuarantee {expected_guarantee} 不一致")

    pool = server_pool(tiers)
    odds_lines = odds_tables(pool)
    for rank in POOL_RANKS:
        parsed = [line.split(",") for line in odds_lines[EQUIPMENT_ODDS_IDS[rank]]]
        entries = pool[GROUP_OF_RANK[rank]]
        if [(int(p[0]), int(p[1]), int(p[2])) for p in parsed] != [(e["id"], e["rank"], e["odds"]) for e in entries]:
            problems.append(f"客户端 {EQUIPMENT_ODDS_IDS[rank]} 与服务端 odds 不一致")
        if any(len(p) != odds.EQUIPMENT_LAYOUT.width for p in parsed):
            problems.append(f"{EQUIPMENT_ODDS_IDS[rank]} 行宽不是 6")

    # -- 客户端表 --------------------------------------------------------------
    row = gacha_row()
    if len(row) != 47:
        problems.append(f"gacha 行 {len(row)} 列 != 47")
    live_gacha = live.flat(GACHA_LOGICAL)
    if GACHA_KEY in live_gacha and live_gacha[GACHA_KEY][:1] != [CODE_NAME]:
        problems.append(f"gacha {GACHA_KEY} 已被占用: {live_gacha[GACHA_KEY][:2]}")
    feature = feature_cells()
    live_feature = live.rows(FEATURE_LOGICAL)
    if GACHA_KEY in live_feature:
        inner = codec.unpack(live_feature[GACHA_KEY])
        cells = core.read_csv_lines(zlib.decompress(inner.get("1", b"")).decode("utf-8")) if inner.get("1") else []
        if not cells or cells[0][1:2] != [COVER]:
            problems.append(f"gacha_feature_content {GACHA_KEY} 已被占用")

    live_items = live.flat(ITEM_LOGICAL)
    atlas = live.atlas_names()
    items = {}
    for ticket in TICKETS:
        key = str(ticket.item_id)
        items[key] = item_row(ticket)
        if len(items[key]) != 23:
            problems.append(f"item {key} {len(items[key])} 列 != 23")
        if key in live_items and live_items[key][:1] != [ticket.code]:
            problems.append(f"item {key} 已被占用: {live_items[key][:3]}")
        if ticket.icon not in atlas:
            problems.append(f"券图标 {ticket.icon} 不在 item/sprite_sheet 图集（会 C8004）")
        template = live_items.get(ticket.template_item, [])
        if len(template) != 23 or template[6] != "8" or template[13] != ticket.gacha_ticket_type \
                or template[3] != ticket.icon:
            problems.append(f"官方装备券模板 {ticket.template_item} 形状漂移: {template[:4]}")
        if "," in ticket.description or "\n" in ticket.description:
            problems.append(f"item {key} 说明含半角逗号/换行")

    live_shop = live.flat(SHOP_LOGICAL)
    template = live_shop.get(SHOP_TEMPLATE_KEY, [])
    shop_target, shop_server_target, shop_problems = shop_targets(template)
    problems += shop_problems
    live_shop_server = (live.server_json(SERVER_SHOP) or {}).get(SHOP_CATEGORY)
    if live_shop_server is None:
        problems.append(f"服务端 {SERVER_SHOP} 缺分类 {SHOP_CATEGORY}")
        live_shop_server = {}
    problems += shop_occupancy_problems(live_shop, live_shop_server)
    # 王币/禁忌星铁的道具行与商品图没上线前，032–034 整组暂缓：不写回旧价，也不提前写新价
    if drop_live is None:
        drop_live = five_boss_drop_live()
    shop_waiting = shop_prerequisites(live_items, lambda logical: live.raw(logical) is not None, drop_live=drop_live)
    shop = {} if shop_waiting else dict(shop_target)
    shop_server = {} if shop_waiting else dict(shop_server_target)
    warnings = [f"五重商店 032–034 暂缓：{reason}" for reason in shop_waiting]
    for key in DELETED_SHOP_KEYS:
        cells = live_shop.get(key)
        if cells is not None and (len(cells) < 34 or cells[0] != SHOP_CATEGORY or cells[32] != "4"
                                  or not cells[33].isdigit() or int(cells[33]) not in CURSED):
            problems.append(f"待删商店键 {key} 不是诅咒本体行: {cells[6:7]} c32={cells[32:33]} c33={cells[33:34]}")

    names = {i: equipment.get(str(i), ["", str(i)])[1] for i in (DEATHBRINGER, PARADOX)}
    max_level = live.server_json(SERVER_MAX_LEVEL) or {}
    capped = sum(1 for r in tiers[5] + tiers[4] + tiers[3] if max_level.get(str(r.id)) == 1)
    html = rich_text_html(tiers, names, capped)

    rows = {
        GACHA_LOGICAL: {GACHA_KEY: row},
        RICH_TEXT_MASTER_LOGICAL: {RICH_TEXT_ID: None},        # None = 空值行（照先例）
        ITEM_LOGICAL: items,
        SHOP_LOGICAL: shop,
    }
    files = {odds_logical(sid): nested_bytes(sid, lines) for sid, lines in odds_lines.items()}
    files[RICH_TEXT_BODY_LOGICAL] = deflate_raw(html)

    # -- 服务端 ------------------------------------------------------------------
    gacha_value = server_gacha(tiers)
    live_server_gacha = live.server_json(SERVER_GACHA) or {}
    current = live_server_gacha.get(GACHA_KEY)
    if current is not None and current.get("rarityOddsId") != RARITY_ODDS_ID:
        problems.append(f"服务端 {SERVER_GACHA} {GACHA_KEY} 已被占用: {current.get('name')}")
    for key in DELETED_SHOP_KEYS:
        entry = live_shop_server.get(key)
        if entry is not None:
            rewards = entry.get("rewards") or []
            if len(rewards) != 1 or rewards[0].get("type") != 4 or rewards[0].get("id") not in CURSED:
                problems.append(f"服务端待删 {key} 不是诅咒本体: {rewards}")
    shop_map = live.server_json(SERVER_SHOP_MAP) or {}
    for key in DELETED_SHOP_KEYS:
        if key in shop_map and shop_map[key] != int(SHOP_CATEGORY):
            problems.append(f"{SERVER_SHOP_MAP} {key} 不属于分类 {SHOP_CATEGORY}")
    sale = {str(t.item_id): {"category": 4, "sale_price": 100, "sellable": False} for t in TICKETS}
    lookup = {str(t.item_id): t.name for t in TICKETS}
    for name, want in ((SERVER_ITEM_SALE, sale), (SERVER_ITEM_LOOKUP, lookup)):
        have = live.server_json(name) or {}
        for key, value in want.items():
            if key in have and have[key] != value:
                problems.append(f"服务端 {name} {key} 已被占用: {have[key]!r}")

    server = {
        SERVER_GACHA: ServerEdit(upsert={GACHA_KEY: gacha_value}, style="compact",
                                 siblings=("990002", "990001")),
        SERVER_CDN_GACHA: ServerEdit(upsert={GACHA_KEY: [row]}, siblings=("990002", "990001")),
        SERVER_CDN_FEATURE: ServerEdit(upsert={GACHA_KEY: {"1": [feature]}}, siblings=("990002", "990001")),
        SERVER_SHOP: ServerEdit(path=(SHOP_CATEGORY,), upsert=shop_server, delete=DELETED_SHOP_KEYS,
                                style="indent", siblings=(SHOP_TEMPLATE_KEY,)),
        SERVER_SHOP_MAP: ServerEdit(upsert={k: int(SHOP_CATEGORY) for k in shop_server},
                                    delete=DELETED_SHOP_KEYS, style="indent", siblings=(SHOP_TEMPLATE_KEY,)),
        SERVER_ITEM_SALE: ServerEdit(upsert=sale, style="indent", siblings=("999018", "999017")),
        SERVER_ITEM_LOOKUP: ServerEdit(upsert=lookup, siblings=("999018", "999017")),
        SERVER_ITEM_IDS: ServerEdit(append=tuple(t.item_id for t in TICKETS)),
    }
    for name in server:
        if live.server_bytes(name) is None:
            problems.append(f"服务端文件缺失: assets/{name}")

    report.update({
        "counts": {"5": len(tiers[5]), "4": len(tiers[4]), "3": len(tiers[3]),
                   "official_5": len(tiers[5]) - 2 - len(CURSED) - len(ABYSS), "abyss": len(ABYSS),
                   "cursed": len(CURSED), "max_level_1": capped},
        "shop_deferred": shop_waiting,
        "weights_5": dict(zip(("cursed_each", "deathbringer", "other_each", "total"),
                              five_star_weights(len(tiers[5]) - 2 - len(CURSED)))),
        "display": {k: display[i] + "%" for k, i in (("deathbringer", DEATHBRINGER), ("cursed", CURSED[0]),
                                                     ("paradox", PARADOX), ("abyss", ABYSS[0]),
                                                     ("official_5", tiers[5][-1].id),
                                                     ("official_4", tiers[4][0].id),
                                                     ("official_3", tiers[3][0].id))},
        "display_sum": f"{sum(float(v) for v in display.values()):.3f}",
    })
    return {
        "tiers": tiers, "server_gacha": gacha_value, "odds": odds_lines, "html": html,
        "rows": rows, "flat_delete": {SHOP_LOGICAL: DELETED_SHOP_KEYS},
        "feature": {GACHA_KEY: {"1": feature}},
        "shop_target": {"rows": shop_target, "server": shop_server_target,
                        "map": {k: int(SHOP_CATEGORY) for k in shop_server_target}},
        "files": files, "server": server, "problems": problems, "warnings": warnings, "report": report,
    }


# ---------------------------------------------------------------------------
# 客户端表重打包（只动本池键，其余行字节原样）
# ---------------------------------------------------------------------------

def _flat_text(blob: bytes) -> str:
    return zlib.decompress(blob).decode("utf-8") if blob else ""


def _feature_cells(blob: bytes) -> dict:
    return {k: _flat_text(v) for k, v in codec.unpack(blob).items()}


def repack(raw: bytes, upsert: dict, delete: Iterable = (), *, nested: bool = False) -> tuple:
    """-> (新字节, changed, deleted)。

    平表 upsert 值是整行 CSV 文本（``None``/空串 = 空值行）；嵌套表（gacha_feature_content）
    upsert 值是 {内层键: CSV 文本}。与 live 已一致的键跳过；已有键原位替换，新键追加到末尾；
    其余键的存储字节逐字节保持（重打包后再解一遍核对）。
    """
    rows = codec.unpack(raw)
    old = dict(rows)
    changed: list = []
    deleted: list = []
    for key in delete:
        if key in rows:
            del rows[key]
            deleted.append(key)
    for key, value in upsert.items():
        if nested:
            if key in rows and _feature_cells(rows[key]) == value:
                continue
            blob = codec.pack({k: zlib.compress(v.encode("utf-8")) for k, v in value.items()})
        else:
            text = value or ""
            if key in rows and _flat_text(rows[key]) == text:
                continue
            blob = zlib.compress(text.encode("utf-8")) if text else b""
        rows[key] = blob
        changed.append(key)
    if not changed and not deleted:
        return raw, [], []
    staged = codec.pack(rows)
    back = codec.unpack(staged)
    untouched = [k for k in old if k not in changed and k not in deleted]
    if any(back.get(k) != old[k] for k in untouched):
        raise AssertionError("重打包后非本池键的字节变了")
    if set(back) != (set(old) - set(deleted)) | set(upsert):
        raise AssertionError("重打包后键集合不符")
    if [k for k in back if k in old and k not in deleted] != [k for k in old if k not in deleted]:
        raise AssertionError("重打包后原有键的顺序变了")
    return staged, changed, deleted


# ---------------------------------------------------------------------------
# 服务端 JSON 文本级拼接
# ---------------------------------------------------------------------------

_WS = re.compile(r"[ \t\n\r]*")
_DECODER = json.JSONDecoder()


@dataclass(frozen=True)
class _Entry:
    key: str | None
    start: int
    key_end: int
    value_start: int
    end: int


def _container_entries(text: str, open_at: int) -> tuple:
    opener = text[open_at]
    closer = {"{": "}", "[": "]"}.get(opener)
    if closer is None:
        raise SpliceError(f"位置 {open_at} 不是容器")
    pos = _WS.match(text, open_at + 1).end()
    entries: list = []
    if text[pos] == closer:
        return entries, pos
    while True:
        start = pos
        key = None
        key_end = pos
        if opener == "{":
            if text[pos] != '"':
                raise SpliceError(f"位置 {pos} 期望键")
            key, key_end = json.decoder.scanstring(text, pos + 1)
            pos = _WS.match(text, key_end).end()
            if text[pos] != ":":
                raise SpliceError(f"位置 {pos} 期望冒号")
            pos = _WS.match(text, pos + 1).end()
        _, end = _DECODER.raw_decode(text, pos)
        entries.append(_Entry(key, start, key_end, pos, end))
        pos = _WS.match(text, end).end()
        if text[pos] == ",":
            pos = _WS.match(text, pos + 1).end()
            continue
        if text[pos] == closer:
            return entries, pos
        raise SpliceError(f"位置 {pos} 期望逗号或 {closer}")


def _formatter(style: str, sep: str) -> Callable:
    if style == "compact":
        return lambda v: json.dumps(v, ensure_ascii=False, separators=(",", ":"))
    if style == "default":
        return lambda v: json.dumps(v, ensure_ascii=False)
    if style == "indent":
        match = re.fullmatch(r",(\r?\n)( *)", sep)
        if match is None:
            raise SpliceError(f"缩进样式的分隔符不符: {sep!r}")
        newline, base = match.groups()
        return lambda v: json.dumps(v, ensure_ascii=False, indent=2).replace("\n", newline + base)
    raise SpliceError(f"未知样式 {style}")


def _locate(text: str, path: tuple) -> int:
    open_at = _WS.match(text, 0).end()
    for key in path:
        entries, _ = _container_entries(text, open_at)
        match = [e for e in entries if e.key == key]
        if len(match) != 1:
            raise SpliceError(f"路径 {path} 找不到 {key!r}")
        open_at = match[0].value_start
    return open_at


def splice_json(text: str, edit: ServerEdit) -> tuple:
    """-> (新文本, added, deleted, updated)。

    只改 ``edit.path`` 指向的那个容器：保留下来的条目原文逐字节照抄，用原分隔符重新拼接，
    新值按兄弟键验证过的排版序列化后追加到末尾。容器以外的字节原样。无改动时原文返回。
    """
    open_at = _locate(text, edit.path)
    entries, close_at = _container_entries(text, open_at)
    if len(entries) < 2:
        raise SpliceError(f"{edit.path}: 条目少于 2 个，无法学习分隔符")
    seps = {text[a.end:b.start] for a, b in zip(entries, entries[1:])}
    if len(seps) != 1:
        raise SpliceError(f"{edit.path}: 分隔符不统一 {sorted(seps)[:3]!r}")
    sep = seps.pop()
    fmt = _formatter(edit.style, sep)
    is_object = text[open_at] == "{"

    if is_object:
        kv_seps = {text[e.key_end:e.value_start] for e in entries}
        if len(kv_seps) != 1:
            raise SpliceError(f"{edit.path}: 键值分隔符不统一 {sorted(kv_seps)!r}")
        kv = kv_seps.pop()
        by_key = {e.key: e for e in entries}
        sibling = next((by_key[k] for k in edit.siblings if k in by_key), None)
        if sibling is None:
            raise SpliceError(f"{edit.path}: 找不到样式兄弟键 {edit.siblings}")
        values = {e.key: json.loads(text[e.value_start:e.end]) for e in entries
                  if e.key in edit.upsert}
        deleted = [e.key for e in entries if e.key in edit.delete]
        updated = [k for k, v in edit.upsert.items() if k in values and values[k] != v]
        added = [k for k in edit.upsert if k not in by_key]
    else:
        sibling = entries[0]
        present = {json.loads(text[e.value_start:e.end]) for e in entries}
        deleted, updated = [], []
        added = [v for v in edit.append if v not in present]
    sibling_text = text[sibling.value_start:sibling.end]
    if fmt(json.loads(sibling_text)) != sibling_text:
        raise SpliceError(f"{edit.path}: 样式 {edit.style} 复现不了兄弟键 {sibling.key!r} 的原文")
    if not added and not deleted and not updated:
        return text, [], [], []

    parts: list = []
    if is_object:
        for e in entries:
            if e.key in deleted:
                continue
            if e.key in updated:
                parts.append(text[e.start:e.value_start] + fmt(edit.upsert[e.key]))
            else:
                parts.append(text[e.start:e.end])
        parts += [json.dumps(k, ensure_ascii=False) + kv + fmt(edit.upsert[k]) for k in added]
    else:
        parts = [text[e.start:e.end] for e in entries] + [fmt(v) for v in added]
    if not parts:
        raise SpliceError(f"{edit.path}: 不支持删空容器")
    head = text[:entries[0].start]
    tail = text[entries[-1].end:]
    new_text = head + sep.join(parts) + tail
    verify_splice(text, new_text, edit, added, deleted, updated)
    return new_text, [str(k) for k in added], deleted, updated


def verify_splice(old_text: str, new_text: str, edit: ServerEdit, added: list, deleted: list,
                  updated: list) -> None:
    """拼接后 json.loads，逐键证明只有本次意图内的键不同；容器外字节原样。"""
    old = json.loads(old_text)
    new = json.loads(new_text)
    open_at = _locate(old_text, edit.path)
    if new_text[:open_at] != old_text[:open_at]:
        raise SpliceError("容器之前的字节变了")
    _, close_old = _container_entries(old_text, open_at)
    _, close_new = _container_entries(new_text, open_at)
    if new_text[close_new:] != old_text[close_old:]:
        raise SpliceError("容器之后的字节变了")
    old_node, new_node = old, new
    for depth, key in enumerate(edit.path):
        if set(old_node) != set(new_node):
            raise SpliceError(f"第 {depth} 层键集合变了")
        for other in old_node:
            if other != key and old_node[other] != new_node[other]:
                raise SpliceError(f"意图外的键 {other!r} 变了")
        old_node, new_node = old_node[key], new_node[key]
    if isinstance(old_node, list):
        if new_node != old_node + list(added):
            raise SpliceError("列表追加结果不符")
        return
    expected_keys = (set(old_node) - set(deleted)) | set(added)
    if set(new_node) != expected_keys:
        raise SpliceError("容器键集合不符")
    for key in new_node:
        if key in added or key in updated:
            if new_node[key] != edit.upsert[key]:
                raise SpliceError(f"{key} 写入值不符")
        elif new_node[key] != old_node[key]:
            raise SpliceError(f"意图外的键 {key!r} 变了")


def stage_server(live: Live, out: dict) -> tuple:
    """-> ({文件名: (新字节, added, deleted, updated)}, problems)。只含真有改动的文件。"""
    staged: dict = {}
    problems: list = []
    for name, edit in out["server"].items():
        text = live.server_text(name)
        if text is None:
            problems.append(f"服务端文件缺失: assets/{name}")
            continue
        try:
            new_text, added, deleted, updated = splice_json(text, edit)
        except (SpliceError, ValueError) as exc:
            problems.append(f"assets/{name}: {exc}")
            continue
        if new_text != text:
            staged[name] = (new_text.encode("utf-8"), added, deleted, updated)
    return staged, problems


# ---------------------------------------------------------------------------
# 暂存
# ---------------------------------------------------------------------------

def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def art_payload(source: Path, art: Art) -> tuple:
    """-> (store 态字节, problems)。统一存 RGBA 8 位 PNG，魔数混淆。"""
    from PIL import Image  # 只在有图时才需要

    problems: list = []
    with Image.open(source) as image:
        image.load()
        rgba = image.convert("RGBA")
    if rgba.size != art.size:
        problems.append(f"{source.name}: 尺寸 {rgba.size} != {art.size}")
    if art.opaque and rgba.getextrema()[3][0] < 255:
        problems.append(f"{source.name}: 封面须不透明")
    buf = io.BytesIO()
    rgba.save(buf, format="PNG", optimize=True)
    return assets.png_encode(buf.getvalue()), problems


def _same_pixels(stored: bytes, source: Path) -> bool:
    from PIL import Image

    with Image.open(io.BytesIO(assets.png_decode(stored))) as a, Image.open(source) as b:
        a, b = a.convert("RGBA"), b.convert("RGBA")
        return a.size == b.size and a.tobytes() == b.tobytes()


def stage_payloads(live: Live, out: dict, *, art_dir: Path = ART_DIR, server: bool = True) -> dict:
    """在内存里算出全部暂存内容与 plan（不写盘）。server=False 跳过服务端拼接（只看客户端时省 1 秒）。"""
    problems = list(out["problems"])
    tables: dict = {}
    for logical, rows in out["rows"].items():
        raw = live.raw(logical)
        if raw is None:
            problems.append(f"store 里没有 {logical}")
            continue
        upsert = {k: (None if v is None else core.write_csv_lines([v])) for k, v in rows.items()}
        staged, changed, deleted = repack(raw, upsert, out["flat_delete"].get(logical, ()))
        if changed or deleted:
            tables[logical] = (staged, changed, deleted)
    raw = live.raw(FEATURE_LOGICAL)
    if raw is None:
        problems.append(f"store 里没有 {FEATURE_LOGICAL}")
    else:
        feature = {k: {ik: core.write_csv_lines([cells]) for ik, cells in v.items()}
                   for k, v in out["feature"].items()}
        staged, changed, deleted = repack(raw, feature, nested=True)
        if changed:
            tables[FEATURE_LOGICAL] = (staged, changed, deleted)
    files: dict = {}
    for logical, payload in out["files"].items():
        current = live.raw(logical)
        if current is not None:
            if logical.endswith(".deflate"):
                if inflate_raw(current) == inflate_raw(payload):
                    continue
            elif read_nested_bytes(current, logical) == read_nested_bytes(payload, logical):
                continue
        files[logical] = {"root": "upload", "logical": logical, "payload": payload,
                          "live_sha256": None if current is None else sha256(current)}
    missing_art: list = []
    for art in ARTS:
        source = art_dir / art.source
        if not source.is_file():
            missing_art.append(str(source))
            continue
        payload, art_problems = art_payload(source, art)
        problems += art_problems
        current = live.raw(art.logical, art.root)
        if current is not None and _same_pixels(current, source):
            continue
        files[art.plan_key] = {"root": art.root, "logical": art.logical, "payload": payload,
                               "live_sha256": None if current is None else sha256(current)}
    staged_server: dict = {}
    if server:
        staged_server, server_problems = stage_server(live, out)
        problems += server_problems
    publish = [p for p in PUBLISH_ORDER if p in tables or p in files]
    return {"tables": tables, "files": files, "server": staged_server, "problems": problems,
            "missing_art": missing_art, "publish_tables": publish}


def _refuse_live_workdir(live: Live, workdir: Path) -> None:
    guarded = [live.store.parent, live.assets_dir, live.cdn_root]
    target = workdir.resolve()
    for root in guarded:
        root = root.resolve()
        if target == root or root in target.parents:
            raise SystemExit(f"拒绝把暂存目录放进 live 路径: {target}（{root}）")


def stage(workdir: Path, live: Live | None = None, *, art_dir: Path = ART_DIR,
          out: dict | None = None, drop_live: bool | None = None) -> dict:
    """写 <workdir>/stage/{common,medium,server}/** 与 <workdir>/plan.json；problems 非空时拒绝。

    medium 层文件写在 ``stage/medium/<逻辑路径>``，plan["files"] 的键带 ``medium:`` 前缀
    （即 wf_publish ``--tables`` 的写法）。
    """
    live = live or Live()
    workdir = Path(workdir)
    _refuse_live_workdir(live, workdir)
    out = out or build(live, drop_live=drop_live)
    if out["problems"]:
        return {"refused": True, "problems": list(out["problems"])}
    payloads = stage_payloads(live, out, art_dir=art_dir)
    if payloads["problems"]:
        return {"refused": True, "problems": payloads["problems"]}
    stage_dir = workdir / "stage"
    if stage_dir.exists():
        shutil.rmtree(stage_dir)
    plan: dict = {"tables": {}, "files": {}, "server": {}, "deleted": {}}
    for logical, (staged, changed, deleted) in payloads["tables"].items():
        _write(stage_dir / "common" / logical, staged)
        plan["tables"][logical] = {"changed": sorted(changed + deleted),
                                   "live_sha256": sha256(live.raw(logical)), "staged_sha256": sha256(staged)}
        if deleted:
            plan["deleted"][logical] = sorted(deleted)
    for key, info in payloads["files"].items():
        root_dir = "medium" if info["root"] == "medium" else "common"
        _write(stage_dir / root_dir / info["logical"], info["payload"])
        plan["files"][key] = {"live_sha256": info["live_sha256"], "staged_sha256": sha256(info["payload"]),
                              "root": info["root"]}
    for name, (staged, added, deleted, updated) in payloads["server"].items():
        _write(stage_dir / "server" / name, staged)
        plan["server"][name] = {"live_sha256": sha256(live.server_bytes(name)), "staged_sha256": sha256(staged),
                                "added": added, "deleted": deleted, "updated": updated}
    workdir.mkdir(parents=True, exist_ok=True)
    (workdir / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"refused": False, "plan": plan, "missing_art": payloads["missing_art"],
            "publish_tables": payloads["publish_tables"],
            "sizes": {**{k: len(v[0]) for k, v in payloads["tables"].items()},
                      **{k: len(v["payload"]) for k, v in payloads["files"].items()},
                      **{f"assets/{k}": len(v[0]) for k, v in payloads["server"].items()}},
            "report": out["report"], "warnings": out["warnings"]}


def _write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def check(live: Live | None = None, *, drop_live: bool | None = None) -> dict:
    live = live or Live()
    out = build(live, drop_live=drop_live)
    payloads = stage_payloads(live, out)
    return {"store": str(live.store), "report": out["report"], "problems": payloads["problems"],
            "warnings": out["warnings"],
            "would_stage": {"tables": {k: {"changed": len(v[1]), "deleted": len(v[2])}
                                       for k, v in payloads["tables"].items()},
                            "files": sorted(payloads["files"]),
                            "server": {k: {"added": v[1], "deleted": len(v[2]), "updated": v[3]}
                                       for k, v in payloads["server"].items()}},
            "missing_art": payloads["missing_art"],
            "publish_tables": ",".join(payloads["publish_tables"])}


def main(argv: list | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    check_parser = sub.add_parser("check", help="只读体检：摘要与 problems")
    stage_parser = sub.add_parser("stage", help="写 <workdir>/stage/** 与 plan.json")
    stage_parser.add_argument("workdir", type=Path)
    for p in (check_parser, stage_parser):
        p.add_argument("--drop-live", action="store_true",
                       help="已核实五重掉落上线（发王币）；不传则按 src/、out/multi/five-boss 检测，未上线时 032–034 暂缓")
    args = parser.parse_args(argv)
    drop_live = True if args.drop_live else None
    if args.command == "check":
        result = check(drop_live=drop_live)
        print(json.dumps(result, ensure_ascii=False, indent=1))
        return 0 if not result["problems"] else 2
    result = stage(args.workdir, drop_live=drop_live)
    if result["refused"]:
        print(json.dumps({"refused": True, "problems": result["problems"]}, ensure_ascii=False, indent=1))
        return 2
    plan = result["plan"]
    print(json.dumps({
        "workdir": str(args.workdir),
        "tables": {k: {"changed": len(v["changed"]), "deleted": len(plan["deleted"].get(k, []))}
                   for k, v in plan["tables"].items()},
        "files": list(plan["files"]),
        "server": {k: {"added": v["added"], "deleted": len(v["deleted"]), "updated": v["updated"]}
                   for k, v in plan["server"].items()},
        "sizes": result["sizes"],
        "missing_art": result["missing_art"],
        "publish_tables": ",".join(result["publish_tables"]),
        "report": result["report"],
        "warnings": result["warnings"],
    }, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
