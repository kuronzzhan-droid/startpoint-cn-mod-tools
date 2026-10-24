# -*- coding: utf-8 -*-
"""把服务端 `assets/gacha.json` 的卡池权重同步进客户端**显示用**的 CDN 概率表。

## 为什么需要这个工具

抽卡概率在本项目里是**两套数据**,改一边不改另一边不会报错,只会静默说谎:

    assets/gacha.json                  -> 服务端真抽(src/lib/gacha.ts 读 rankRates + pool[].odds)
    master/gacha_odds/<stringId>...    -> 客户端「提供概率」页显示,服务端**完全不参与**

指针在 CDN gacha 表行上:c11=rarityOddsId;c13=prize_kind 决定读哪三列——
角色池(c13=0)读 c14/c15/c16=character_3/4/5,装备池(c13=1)读 c22/c23/c24=equipment_3/4/5
(`GachaValues.as:172-197`)。
客户端 `GachaOddsTools.getRarityOddsPath()` 把 stringId 拼成 `/gacha_odds/<id>`。

显示公式(已用真机截图两次验算):

    单角色显示% = 档位%  ×  该角色权重 / 本档权重合计

档位表 `<id>_rarity` 每行 `星级,千分比`(`5,150` = 5★ 15.0%),
角色表 `<id>_character_<星级>` 每行 `角色ID,星级,权重,isRateUp,isLimited,isExchangeable,trialReadingForced`(7 列),
装备表 `<id>_<星级>` 每行 `装备ID,星级,权重,odds_up,is_limited,is_exchangeable`(6 列,
`EquipmentGachaOddsValues.as`;没有 trialReadingForced)。
**权重列与 gacha.json 的 `odds` 是同一个数**(官方 4★/3★ 两档逐值相同即为佐证)。

客户端取整是 `Math.floor`:档位 2 位小数、单角色 3 位小数,所以本工具按同样规则
预演一遍显示串,发布前就能看到玩家会看到什么。

## 表的编码

`master/gacha_odds/*.orderedmap` 是 **raw_outer 嵌套**:外层 1 个键(=stringId)→
值是一个内层 orderedmap,内层每行**各自 zlib 压缩**。用 `core.read_orderedmap_file`
读会直接抛 `zlib error -3`。读写都走 `wf_offline_pack_apply.read_rows/build_rows`。
写之前本工具会先对原文件做一次逐字节往返自检,不通过就拒绝落盘。
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
import zlib
from dataclasses import dataclass
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    pass  # Imports resolve from this checkout/package, not external source copies.
import wf_mod_tool as core  # noqa: E402
import wf_offline_pack_apply as opa  # noqa: E402

ROOT = TOOLS.parent
GACHA_JSON = ROOT / "assets" / "gacha.json"

# CDN gacha 表列位
COL_RARITY_ODDS_ID = 11
COL_PRIZE_KIND = 13                     # 0=角色池 1=装备池
COL_CHARACTER_ODDS_ID = {3: 14, 4: 15, 5: 16}
COL_EQUIPMENT_ODDS_ID = {3: 22, 4: 23, 5: 24}
# pool 分组键 -> 星级
GROUP_RANK = {"1": 5, "2": 4, "3": 3}
BOOL_FIELDS = ("isRateUp", "isLimited", "isExchangeable", "trialReadingForced")
EQUIPMENT_BOOL_FIELDS = ("isRateUp", "isLimited", "isExchangeable")


class OddsSyncError(RuntimeError):
    pass


@dataclass(frozen=True)
class OddsLayout:
    """一种卡池的显示表布局:星级 -> CDN 列位,以及行尾布尔列(决定行宽)。"""

    kind: str
    columns: dict
    bool_fields: tuple

    @property
    def width(self) -> int:
        return 3 + len(self.bool_fields)


CHARACTER_LAYOUT = OddsLayout("character", COL_CHARACTER_ODDS_ID, BOOL_FIELDS)
EQUIPMENT_LAYOUT = OddsLayout("equipment", COL_EQUIPMENT_ODDS_ID, EQUIPMENT_BOOL_FIELDS)
PRIZE_KIND_LAYOUT = {"0": CHARACTER_LAYOUT, "1": EQUIPMENT_LAYOUT}


def odds_layout(cdn_row: list[str]) -> OddsLayout:
    """按 CDN gacha 行 c13(prize_kind)选布局;未知值直接拒绝,不猜。"""
    kind = cdn_row[COL_PRIZE_KIND] if len(cdn_row) > COL_PRIZE_KIND else ""
    layout = PRIZE_KIND_LAYOUT.get(kind)
    if layout is None:
        raise OddsSyncError(f"CDN gacha 行 c{COL_PRIZE_KIND}(prize_kind)={kind!r},不认识")
    return layout


def rarity_lines(normal: list[int]) -> list[str]:
    """档位表行:`星级,千分比`,顺序 5/4/3,与 rankRates.normal 同序。"""
    return [f"{rank},{rate}" for rank, rate in zip((5, 4, 3), normal)]


def odds_line(entry: dict, rank: int, bool_fields: tuple = BOOL_FIELDS) -> str:
    """服务端池条目 -> 显示表一行。权重列就是 odds,布尔列按布局取。"""
    flags = ",".join("true" if entry.get(f) else "false" for f in bool_fields)
    return f"{entry['id']},{rank},{int(entry['odds'])},{flags}"


def _odds_path(string_id: str) -> str:
    return f"master/gacha_odds/{string_id}.orderedmap"


def read_nested(path: Path, logical: str) -> tuple[str, list[str], list[str]]:
    """-> (外层键, 内层键列表, 内层明文行列表)"""
    outer_keys, outer_blobs = opa.read_rows(path.read_bytes(), "raw_outer", logical)
    if len(outer_keys) != 1:
        raise OddsSyncError(f"{logical}: 预期外层恰好 1 个键,实际 {len(outer_keys)}")
    inner_keys, inner_blobs = core._strict_orderedmap_rows(
        outer_blobs[0], label=logical, compressed_rows=False)
    return outer_keys[0], list(inner_keys), [zlib.decompress(b).decode("utf-8") for b in inner_blobs]


def build_nested(outer_key: str, inner_keys: list[str], lines: list[str]) -> bytes:
    inner = opa.build_rows(inner_keys, [zlib.compress(l.encode("utf-8")) for l in lines],
                           compressed=False)
    return opa.build_rows([outer_key], [inner], compressed=False)


def assert_roundtrip(path: Path, logical: str) -> None:
    """写之前先证明:原样读出再写回,必须逐字节相同。"""
    original = path.read_bytes()
    ok, ik, lines = read_nested(path, logical)
    if build_nested(ok, ik, lines) != original:
        raise OddsSyncError(f"{logical}: 往返自检不通过,拒绝写入")


def fmt_rarity(pct: float) -> str:
    """客户端 GachaOddsTools.formatOddsByRarity:floor 到 2 位小数。"""
    return f"{math.floor(pct * 100 + 2e-10) / 100:.2f}"


def fmt_odds(pct: float) -> str:
    """客户端 GachaOddsTools.formatOdds:floor 到 3 位小数。"""
    return f"{math.floor(pct * 1000 + 2e-10) / 1000:.3f}"


def sync_pool(pool_id: str, store: Path, *, apply: bool, stamp: str,
              gacha_json: Path | None = None) -> dict:
    gacha = json.loads((gacha_json or GACHA_JSON).read_text(encoding="utf-8"))
    if pool_id not in gacha:
        raise OddsSyncError(f"assets/gacha.json 里没有卡池 {pool_id}")
    pool = gacha[pool_id]

    cdn_logical = "master/gacha/gacha.orderedmap"
    cdn = core.read_orderedmap_file(core.table_path(store, cdn_logical), cdn_logical).text_rows()
    if pool_id not in cdn:
        raise OddsSyncError(f"CDN gacha 表里没有卡池 {pool_id}")
    cdn_row = core.read_csv_lines(cdn[pool_id])[0]
    layout = odds_layout(cdn_row)

    rank_rates = pool.get("rankRates", {}).get("normal")
    if not rank_rates or len(rank_rates) != 3:
        raise OddsSyncError(f"{pool_id}: rankRates.normal 缺失或不是 3 项")

    report: dict = {"pool": pool_id, "name": pool.get("name"), "layout": layout.kind,
                    "tables": []}

    # --- 档位表 ---
    rarity_id = cdn_row[COL_RARITY_ODDS_ID]
    logical = _odds_path(rarity_id)
    path = core.table_path(store, logical)
    if not path.is_file():
        raise OddsSyncError(f"{logical}: store 里不存在")
    assert_roundtrip(path, logical)
    outer_key, inner_keys, old_lines = read_nested(path, logical)
    new_lines = rarity_lines(rank_rates)
    if len(new_lines) != len(inner_keys):
        inner_keys = [str(i) for i in range(len(new_lines))]
    report["tables"].append({
        "logical": logical, "kind": "rarity",
        "before": old_lines, "after": new_lines,
        "display": [f"{r}★ {fmt_rarity(v / 10)}%" for r, v in zip((5, 4, 3), rank_rates)],
        "changed": old_lines != new_lines,
    })
    if apply and old_lines != new_lines:
        path.with_name(path.name + f".bak-oddssync-{stamp}").write_bytes(path.read_bytes())
        path.write_bytes(build_nested(outer_key, inner_keys, new_lines))

    # --- 角色/装备表(按星级分档;列位与行宽由 prize_kind 决定) ---
    for group, rank in GROUP_RANK.items():
        entries = pool.get("pool", {}).get(group)
        if not entries:
            continue
        string_id = cdn_row[layout.columns[rank]]
        if not string_id:
            raise OddsSyncError(f"{pool_id}: CDN 行 c{layout.columns[rank]}({layout.kind}_{rank})为空")
        logical = _odds_path(string_id)
        path = core.table_path(store, logical)
        if not path.is_file():
            raise OddsSyncError(f"{logical}: store 里不存在")
        assert_roundtrip(path, logical)
        outer_key, inner_keys, old_lines = read_nested(path, logical)

        total = sum(int(e["odds"]) for e in entries)
        if total <= 0:
            raise OddsSyncError(f"{logical}: 权重合计为 {total},无法计算占比")
        rank_pct = rank_rates[{5: 0, 4: 1, 3: 2}[rank]] / 10.0

        new_lines = [odds_line(e, rank, layout.bool_fields) for e in entries]
        inner_keys = [str(i) for i in range(len(new_lines))]

        shown = {}
        for e in entries:
            shown.setdefault(fmt_odds(rank_pct * int(e["odds"]) / total), 0)
            shown[fmt_odds(rank_pct * int(e["odds"]) / total)] += 1
        report["tables"].append({
            "logical": logical, "kind": f"{layout.kind}_{rank}",
            "rows": [len(old_lines), len(new_lines)],
            "weight_total": total,
            "display_buckets": {f"{k}%": v for k, v in sorted(shown.items(),
                                                             key=lambda kv: -float(kv[0]))},
            "changed": old_lines != new_lines,
        })
        if apply and old_lines != new_lines:
            path.with_name(path.name + f".bak-oddssync-{stamp}").write_bytes(path.read_bytes())
            path.write_bytes(build_nested(outer_key, inner_keys, new_lines))

    return report


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--pool", action="append", required=True, help="卡池 id,可多次")
    p.add_argument("--profile", default="cn")
    p.add_argument("--apply", action="store_true", help="不加则只预演")
    args = p.parse_args(argv)

    store = Path(core.resolve_profile(args.profile).store).resolve()
    stamp = time.strftime("%Y%m%d-%H%M%S")
    reports = [sync_pool(pid, store, apply=args.apply, stamp=stamp) for pid in args.pool]
    print(json.dumps({"applied": args.apply, "reports": reports},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
