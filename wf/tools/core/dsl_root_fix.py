# -*- coding: utf-8 -*-
"""扫描并修复根节点写错的 action DSL(裸 Block 缺 ActionDsl 外壳)。

## 病症
打开技能预览必崩 F1009:
    TypeError: Error #1009
      at ActionDslHandler/resolveActionDsl()
      at ActionDslHandler/readHandler()
      at OpenHandler/execute()

## 机制(逐行核对过反编译)
`ActionDslHandler.as:1486-1492` readHandler 先 `actionDslUnserializer.concrete(...)`
再 `resolveActionDsl(_loc2_.params[10])`。`ActionDsl.as:10` 的
`__constructs__ = ["ActionDsl"]`,构造签名 11 个参数
`ActionDsl(movementPriority, conditionalKind, bool x7, int, expression)`。
`typepacker/core/DataConcreter.as:230-284` concreteEnum 拿到根构造名 `"Block"`
在 ActionDsl 的构造表里查不到 -> `int(undefined)` -> 索引 0,然后按 11 个参数去读,
2..11 槽全缺 -> `concrete(type, undefined)` 走 `if(param5 == null) return null`
-> **params[10] === null** -> `resolveActionDsl` 里 `switch(param1.index)` 空引用。

## 判据
根构造名必须是 `ActionDsl` 且恰好 11 个参数。全库 1218 个技能 DSL 里 1208 合规,
84 个 PF DSL 里 72 合规 —— 不合规的全部集中在这一批新角色。
`mechanic_dragon_eater` 的 3 个 PF DSL 是**合规的**,因为它们走
`adapt_power_flip_lifecycle` 原地改官方母本,继承了母本的外壳 —— 天然对照组。

## 修法
把裸 Block 包成 `["ActionDsl", p0, ["None"], False x7, 0, <Block>]`。
p0(movementPriority)取**同一张表里合规行的众数**,不硬编码。
其余定值来自全库统计:params[1] 恒 ['None'],params[9] 恒 0,
params[2..8] 在 1109/1208 里全 False。

## 上游
生成器漏了外壳:`wf_epuration_dsl_bundle.py:211-212` `tree = ["Block", expressions]`,
`wf_epuration_task3_dsl.py:125`、`wf_epuration_task4_dsl.py:219/298` 同。
闸门也漏了:`wf_boss_player_dsl_gate.py` 走了树但从不断言根构造名。
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
import time
import zlib
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[3]
if str(TOOLS) not in sys.path:
    pass  # Imports resolve from this checkout/package, not external source copies.
import wf_mod_tool as core  # noqa: E402
import wf_dsl  # noqa: E402
import wf_pixel_rescale as rescale  # noqa: E402

PROD = Path(r"弹国服/WorldFlipper/dummy/download/production")
SUFFIX = ".action.dsl.amf3.deflate"
ROOT_NAME = "ActionDsl"
ROOT_ARITY = 11


class DslRootError(RuntimeError):
    pass


def _decode(raw: bytes):
    """返回 (tree, wbits, offset)。"""
    for wbits in (-15, 15):
        for offset in (0, 4):
            try:
                plain = zlib.decompress(raw[offset:], wbits)
            except Exception:
                continue
            try:
                tree = wf_dsl.parse_dsl(plain)
            except Exception:
                continue
            if isinstance(tree, dict) and "tree" in tree:
                tree = tree["tree"]
            return tree, wbits, offset
    raise DslRootError("DSL 解不出")


def _encode(tree, wbits: int, offset: int, raw: bytes) -> bytes:
    plain = wf_dsl.encode_amf3(tree)      # 只吃裸树,别喂 {tree,numbers} 包装壳
    comp = zlib.compressobj(9, zlib.DEFLATED, wbits)
    return raw[:offset] + comp.compress(plain) + comp.flush()


def _program_paths(store: Path) -> dict[str, set[str]]:
    """三张表里出现的 DSL program_path,按来源分组。"""
    out: dict[str, set[str]] = collections.defaultdict(set)

    def harvest(tag: str, text: str) -> None:
        for cells in core.read_csv_lines(text):
            for cell in cells:
                if cell.startswith("battle/action/"):
                    out[tag].add(cell)

    for logical, tag in (
        ("master/skill/action_skill.orderedmap", "skill"),
        ("master/skill/power_flip_action.orderedmap", "power_flip"),
        ("master/ability/ability.orderedmap", "ability"),
    ):
        path = core.table_path(store, logical)
        if not path.exists():
            continue
        try:
            # 平表(行是 zlib CSV)
            for value in core.read_orderedmap_file(path, logical).text_rows().values():
                harvest(tag, value)
            continue
        except Exception:
            pass
        # 嵌套表:action_skill 是 raw_outer,外层键是技能名,内层才是等级行
        import wf_offline_pack_apply as apply_tool
        keys, rows_ = apply_tool.read_rows(path.read_bytes(), "raw_outer", logical)
        for blob in rows_:
            inner_keys, inner_rows = core._strict_orderedmap_rows(  # type: ignore[attr-defined]
                blob, label="inner", compressed_rows=False)
            for row in inner_rows:
                try:
                    text = zlib.decompress(row).decode("utf-8")
                except Exception:
                    text = row.decode("utf-8", errors="replace")
                harvest(tag, text)
    return out


def scan(store: Path, salt: str):
    groups = _program_paths(store)
    good: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    bad: list[dict] = []
    total = 0
    for tag, paths in groups.items():
        for program in sorted(paths):
            logical = program + SUFFIX
            path = rescale.store_path(store, logical, salt)
            if not path.exists():
                continue
            total += 1
            raw = path.read_bytes()
            try:
                tree, wbits, offset = _decode(raw)
            except DslRootError:
                continue
            if (isinstance(tree, list) and tree and tree[0] == ROOT_NAME
                    and len(tree) == ROOT_ARITY + 1):
                good[tag][tree[1]] += 1
            else:
                bad.append({
                    "tag": tag, "logical": logical,
                    "root": tree[0] if isinstance(tree, list) and tree else repr(type(tree)),
                    "arity": (len(tree) - 1) if isinstance(tree, list) else None,
                    "wbits": wbits, "offset": offset, "path": path,
                })
    return total, good, bad


def fix(store: Path, salt: str, apply: bool) -> dict:
    total, good, bad = scan(store, salt)
    report = {"scanned": total, "malformed": len(bad),
              "priority_mode": {t: c.most_common(3) for t, c in good.items()},
              "fixed": []}
    stamp = time.strftime("%Y%m%d-%H%M%S")
    for entry in bad:
        tag = entry["tag"]
        if not good[tag]:
            raise DslRootError(f"{tag}: 没有合规行可取众数,拒绝硬编码优先级")
        priority = good[tag].most_common(1)[0][0]
        path: Path = entry["path"]
        raw = path.read_bytes()
        tree, wbits, offset = _decode(raw)
        if not (isinstance(tree, list) and tree and tree[0] == "Block"):
            raise DslRootError(f"{entry['logical']}: 根不是 Block 而是 {entry['root']},不自动处理")
        wrapped = [ROOT_NAME, priority, ["None"],
                   False, False, False, False, False, False, False,
                   0, tree]
        data = _encode(wrapped, wbits, offset, raw)
        back, _, _ = _decode(data)
        if back != wrapped:
            raise DslRootError(f"{entry['logical']}: 往返自检不一致")
        if back[11] != tree:
            raise DslRootError(f"{entry['logical']}: 内层 Block 被改动")
        rec = {"logical": entry["logical"], "tag": tag, "priority": priority,
               "bytes": [len(raw), len(data)], "applied": False}
        if apply:
            backup = path.with_name(path.name + f".bak-dslroot-{stamp}")
            if not backup.exists():
                backup.write_bytes(raw)
            path.write_bytes(data)
            rec["applied"] = True
        report["fixed"].append(rec)
    if apply:
        report["backup_suffix"] = f".bak-dslroot-{stamp}"
    return report


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--store", default=str(PROD / "upload"))
    p.add_argument("--apply", action="store_true")
    args = p.parse_args(argv)
    store = Path(args.store)
    report = fix(store, rescale.salt(), args.apply)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["fixed"]:
        print("\n需要发布:")
        print(",".join(e["logical"] for e in report["fixed"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
