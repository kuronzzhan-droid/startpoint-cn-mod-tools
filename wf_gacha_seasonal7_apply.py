# -*- coding: utf-8 -*-
"""把 `wf_gacha_seasonal7_pools.revise()` 的结果落到 `assets/gacha.json`。

`assets/gacha.json` 是作者 WIP 文件，全文重新序列化会改动与本次无关的上万行
（官方段用 `json.dumps` 默认分隔符，两个 mod 卡池段用紧凑分隔符）。所以这里做
**文本级拼接**：只替换 `"990001": {...}` 与 `"990002": {...}` 两段，其余字节原样保留。
落盘前先证明「原样读出再按紧凑分隔符写回 == 原始字节」，不通过就拒绝写。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    pass  # Imports resolve from this checkout/package, not external source copies.

import wf_gacha_seasonal7_pools as rev  # noqa: E402

GACHA_JSON = TOOLS.parent / "assets" / "gacha.json"
COMPACT = (",", ":")


def locate(raw: str, pool_id: str) -> tuple[int, int, dict]:
    marker = f'"{pool_id}": '
    at = raw.index(marker)
    start = at + len(marker)
    obj, end = json.JSONDecoder().raw_decode(raw, start)
    return start, end, obj


def splice(raw: str, updated: dict) -> str:
    spans = []
    for pool_id in (rev.ABYSS, rev.RACING):
        start, end, obj = locate(raw, pool_id)
        if json.dumps(obj, ensure_ascii=False, separators=COMPACT) != raw[start:end]:
            raise SystemExit(f"{pool_id}: 紧凑序列化往返自检不通过，拒绝写入")
        spans.append((start, end, pool_id))
    out = raw
    for start, end, pool_id in sorted(spans, reverse=True):
        out = out[:start] + json.dumps(updated[pool_id], ensure_ascii=False,
                                       separators=COMPACT) + out[end:]
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="不加则只预演")
    args = parser.parse_args(argv)

    raw = GACHA_JSON.read_text(encoding="utf-8")
    before = json.loads(raw)
    after = rev.revise(before)
    out = splice(raw, after)
    if json.loads(out) != after:
        raise SystemExit("拼接后的 JSON 与预期对象不一致，拒绝写入")

    report = {"applied": args.apply, "bytes": [len(raw), len(out)], "pools": {}}
    for pool_id, rate in ((rev.ABYSS, 15.0), (rev.RACING, 95.0)):
        rows = after[pool_id]["pool"]["1"]
        total = sum(int(e["odds"]) for e in rows)
        buckets: dict[str, int] = {}
        for e in rows:
            key = "%.3f%%" % (rate * int(e["odds"]) / total)
            buckets[key] = buckets.get(key, 0) + 1
        report["pools"][pool_id] = {
            "rows": [len(before[pool_id]["pool"]["1"]), len(rows)],
            "weight_total": total,
            "top": [int(e["id"]) for e in rows[:7]],
            "display_buckets": dict(sorted(buckets.items(),
                                           key=lambda kv: -float(kv[0].rstrip("%")))),
        }
    if args.apply:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        backup = GACHA_JSON.with_name(GACHA_JSON.name + f".bak-s7pools-{stamp}")
        backup.write_text(raw, encoding="utf-8", newline="")
        report["backup"] = backup.name
        GACHA_JSON.write_text(out, encoding="utf-8", newline="")
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
