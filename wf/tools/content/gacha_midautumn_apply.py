# -*- coding: utf-8 -*-
"""把 `wf_gacha_midautumn_pools.revise()` 的结果落到两层数据（默认只预演）。

    服务端真抽   assets/gacha.json                              <- 文本级键级替换
    客户端显示   master/gacha_odds/<stringId>.orderedmap        <- wf_gacha_odds_sync

`assets/gacha.json` 是作者 WIP 的单行大 JSON，整文件重新序列化会改上万行无关字节
（官方段用 `json.dumps` 默认分隔符、两个 mod 卡池段用紧凑分隔符）。所以沿用
`wf_gacha_seasonal7_apply` 的做法：**只替换 `"990001": {...}` 与 `"990002": {...}` 两段**，
其余字节原样保留；替换前先证明「原样读出再按紧凑分隔符写回 == 原始字节」，不通过就拒绝写。

两层必须一起改：只改一边不会报错，只会让「提供概率」页静默说谎。

用法：

    python mod-tools/wf_gacha_midautumn_apply.py                # 预演（不写任何文件）
    python mod-tools/wf_gacha_midautumn_apply.py --apply        # 写 gacha.json + 同步显示表
    python mod-tools/wf_gacha_midautumn_apply.py --apply --skip-odds-sync

预演也会真实预测客户端显示串：把改后的 gacha 写到临时文件，让 `wf_gacha_odds_sync`
按它算一遍（全程只读 store）。
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[3]
if str(TOOLS) not in sys.path:
    pass  # Imports resolve from this checkout/package, not external source copies.

import wf_gacha_midautumn_pools as rev  # noqa: E402
import wf_gacha_odds_sync as odds_sync  # noqa: E402
import wf_gacha_seasonal7_apply as s7apply  # noqa: E402
import wf_mod_tool as core  # noqa: E402

ROOT = TOOLS.parent
GACHA_JSON = ROOT / "assets" / "gacha.json"
POOLS = (rev.ABYSS, rev.RACING)
RANK_PCT = {rev.ABYSS: 15.0, rev.RACING: 95.0}


def pool_report(before: dict, after: dict, pool_id: str) -> dict:
    rows_before = before[pool_id]["pool"]["1"]
    rows_after = after[pool_id]["pool"]["1"]
    total = sum(int(e["odds"]) for e in rows_after)
    rate = RANK_PCT[pool_id]
    buckets: dict[str, int] = {}
    for e in rows_after:
        key = "%s%%" % rev.display_percent(after[pool_id], int(e["id"]))
        buckets[key] = buckets.get(key, 0) + 1
    ids_before = {int(e["id"]) for e in rows_before}
    official_before = sum(int(e["odds"]) for e in rows_before if not rev.is_custom(int(e["id"])))
    official_after = sum(int(e["odds"]) for e in rows_after if not rev.is_custom(int(e["id"])))
    return {
        "name": after[pool_id].get("name"),
        "five_star_rate": rate,
        "rows": [len(rows_before), len(rows_after)],
        "added": sorted(({int(e["id"]) for e in rows_after} - ids_before)),
        "weight_total": [sum(int(e["odds"]) for e in rows_before), total],
        "official_weight": [official_before, official_after],
        "official_weight_unchanged": official_before == official_after,
        "top12": [int(e["id"]) for e in rows_after[:12]],
        "midautumn_rows": [
            {"id": cid,
             "odds": int(next(e for e in rows_after if int(e["id"]) == cid)["odds"]),
             "display": rev.display_percent(after[pool_id], cid) + "%",
             "isExchangeable": next(e for e in rows_after if int(e["id"]) == cid)["isExchangeable"]}
            for cid in rev.MIDAUTUMN12
        ],
        "display_buckets": dict(sorted(buckets.items(),
                                       key=lambda kv: -float(kv[0].rstrip("%")))),
    }


def odds_reports(after: dict, store: Path, *, apply: bool, stamp: str) -> list[dict]:
    """预演时让 odds_sync 读「改后的 gacha」临时文件；--apply 时读真文件并写表。"""
    if apply:
        return [odds_sync.sync_pool(pid, store, apply=True, stamp=stamp) for pid in POOLS]
    original = odds_sync.GACHA_JSON
    with tempfile.TemporaryDirectory(prefix="ma_gacha_") as tmp:
        preview = Path(tmp) / "gacha.json"
        preview.write_text(json.dumps(after, ensure_ascii=False), encoding="utf-8")
        odds_sync.GACHA_JSON = preview
        try:
            return [odds_sync.sync_pool(pid, store, apply=False, stamp=stamp) for pid in POOLS]
        finally:
            odds_sync.GACHA_JSON = original


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="不加则只预演，不写任何文件")
    parser.add_argument("--skip-odds-sync", action="store_true",
                        help="只动 assets/gacha.json，客户端显示表另外单独跑")
    parser.add_argument("--profile", default="cn")
    args = parser.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    raw = GACHA_JSON.read_text(encoding="utf-8")
    before = json.loads(raw)
    after = rev.revise(before)                      # 纯函数 + 硬断言
    out = s7apply.splice(raw, after)                # 只替换两个卡池段
    if json.loads(out) != after:
        raise SystemExit("拼接后的 JSON 与预期对象不一致，拒绝写入")
    for pool_id in POOLS:
        if json.loads(out)[pool_id] != after[pool_id]:
            raise SystemExit(f"{pool_id}: 替换后的卡池段与预期不一致，拒绝写入")

    stamp = time.strftime("%Y%m%d-%H%M%S")
    report: dict = {
        "applied": args.apply,
        # chars 是字符数（文件是 UTF-8，CJK 一个字符多字节），只用来看替换幅度
        "gacha_json": {"path": str(GACHA_JSON), "chars": [len(raw), len(out)], "backup": None},
        "pools": {pid: pool_report(before, after, pid) for pid in POOLS},
    }

    if args.apply:
        backup = GACHA_JSON.with_name(GACHA_JSON.name + f".bak-mapools-{stamp}")
        backup.write_text(raw, encoding="utf-8", newline="")
        GACHA_JSON.write_text(out, encoding="utf-8", newline="")
        report["gacha_json"]["backup"] = backup.name
        readback = json.loads(GACHA_JSON.read_text(encoding="utf-8"))
        report["gacha_json"]["readback_ok"] = all(readback[pid] == after[pid] for pid in POOLS)
        untouched = all(readback[k] == before[k] for k in before if k not in POOLS)
        report["gacha_json"]["other_pools_untouched"] = untouched
        if not (report["gacha_json"]["readback_ok"] and untouched):
            raise SystemExit("回读校验失败：请用备份还原 assets/gacha.json")

    if args.skip_odds_sync:
        report["odds_tables"] = "skipped"
        tables: list[str] = []
    else:
        store = Path(core.resolve_profile(args.profile).store).resolve()
        reports = odds_reports(after, store, apply=args.apply, stamp=stamp)
        report["store"] = str(store)
        report["odds_tables"] = [
            {k: t[k] for k in ("logical", "kind", "changed", "rows", "weight_total",
                               "display_buckets") if k in t}
            for r in reports for t in r["tables"]
        ]
        tables = [t["logical"] for t in report["odds_tables"] if t["changed"]]

    report["publish"] = {
        "tables": tables,
        "command": ("python mod-tools/wf_publish.py --tables " + ",".join(tables)) if tables
        else "(无需发布：显示表没有变化)",
    }
    report["next"] = [
        "1) 本脚本 --apply（写 assets/gacha.json + 同步 master/gacha_odds/*）",
        "2) " + report["publish"]["command"],
        "3) ./start-cn.bat -RestartOwned  （assets/gacha.json 是服务端静态 import，"
        "不重启就还是旧概率；reload_assets 不覆盖它）",
    ]
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
