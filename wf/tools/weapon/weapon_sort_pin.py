# -*- coding: utf-8 -*-
"""装备列表置顶：只读 live 的 ``custom_ability_string`` 键构建器 + 暂存（stage）。

方案 ``${WF_ROOT}/out/武器置顶-20260928/方案.md``（B「数据」；「目标顺序」表）。客户端补丁
``client-patch/equipment-sort-pin``（capability ``equipment-sort-pin-v1``，cosmetic）在装备一览
``EquipmentListScene.compareByEquipmentStatus`` 与编成选武器 ``EquipmentSelectThumbnailListRepository.sortByRarity``
的入口读 ``equipment_sort_pin_<装备ID>``：两件都有合法序号且不等 → 序号升序；只有一件有 → 它在前；其余原生顺序。
没打补丁的客户端不读这些行（显示原生顺序、不崩），所以数据可以先于 APK 发布。

## 产物（common 层，只动本工具自有键）

``master/string/custom_ability_string.orderedmap`` 46 行（单列 ``string``）：

  - PARADOX 5920001 → ``1000``；
  - 诅咒武器 5910101–5910129 → ``2001``–``2029``（按 ID 升序）；
  - 深渊武器 8000101–8000115 → ``3001``–``3015``（按 ID 升序）；
  - 死亡使者·终式 5900101 → ``3100``（放在深渊之后，所以不能只按 ID 分档）。

按千位分段给以后新增的武器留位置（第 30 把诅咒写 2030，不用改补丁）。服务端不读这些键（``src/`` 无引用），
本工具不产服务端文件。

## 两条纪律

1. **只读 live。** 从不写 store、``.cdn``、``assets/``，也不调用 wf_publish。``stage <workdir>`` 只写
   ``<workdir>/stage/common/<逻辑路径>`` 与 ``<workdir>/plan.json``（合同同 ``wf_weapon_gacha``：
   ``tables`` / ``files`` / ``server`` / ``deleted``，每张表带 ``changed`` / ``live_sha256`` / ``staged_sha256``），
   落 live 与铸边由调用方完成。
2. **幂等。** 构建的是目标态，暂存时与 live 逐键比较：已经一致的键不进 plan，上线后再跑只会得到空 plan。

门禁（problems 非空一律拒绝，什么都不写）：键尾装备 ID 必须在 live 装备表里；每个值过
``wf_client_legality.equipment_key_problems``（规范十进制正整数 1–999999999）且互不相同（相同序号的两件之间
客户端回落原生顺序，不是「置顶」）；live 里有合同外的 ``equipment_sort_pin_*`` 键也拒绝（避免残留行把别的装备顶上来）。

用法::

    python mod-tools/wf_weapon_sort_pin.py check            # 只读体检：摘要 + problems
    python mod-tools/wf_weapon_sort_pin.py stage <workdir>  # problems 非空时拒绝
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[3]  # 仓库根（本文件在 wf/tools/<组>/ 下）
if str(TOOLS) not in sys.path:
    pass  # Imports resolve from this checkout/package, not external source copies.

import wf_client_legality as L  # noqa: E402
import wf_weapon_gacha as G  # noqa: E402
from wf_weapon_gacha import core  # noqa: E402

# ---------------------------------------------------------------------------
# 合同常量（改口径只改这里，然后重跑 check / stage）
# ---------------------------------------------------------------------------

PREFIX = L.EQUIPMENT_SORT_PIN_KEY_PREFIX
CAPABILITY = L.EQUIPMENT_SORT_PIN
PARADOX = G.PARADOX                  # 5920001
DEATHBRINGER = G.DEATHBRINGER        # 5900101 死亡使者·终式
CURSED = tuple(G.CURSED)             # 5910101–5910129
ABYSS = tuple(G.ABYSS)               # 8000101–8000115
PARADOX_PIN = 1000
CURSED_BASE = 2001
ABYSS_BASE = 3001
DEATHBRINGER_PIN = 3100
#: 装备 ID → 置顶序号（小者在前）。
PINS = {PARADOX: PARADOX_PIN,
        **{eid: CURSED_BASE + i for i, eid in enumerate(CURSED)},
        **{eid: ABYSS_BASE + i for i, eid in enumerate(ABYSS)},
        DEATHBRINGER: DEATHBRINGER_PIN}

CAS_LOGICAL = "master/string/custom_ability_string.orderedmap"
EQUIPMENT_LOGICAL = G.EQUIPMENT_LOGICAL
PUBLISH_ORDER = (CAS_LOGICAL,)


def pin_key(equipment_id: int) -> str:
    """与补丁插入段的拼接逐字相同："equipment_sort_pin_" + int(p.id)。"""
    return PREFIX + str(int(equipment_id))


def cas_rows() -> dict:
    """46 行 ``equipment_sort_pin_<装备ID>`` = ``<序号>``（单列行，补丁读 row.string）。"""
    return {pin_key(eid): [str(pin)] for eid, pin in PINS.items()}


def pin_order() -> list:
    """置顶组的目标显示顺序（装备 ID）。"""
    return sorted(PINS, key=PINS.get)


def contract_problems(rows: dict | None = None) -> list:
    """不看 live 的合同自检：键形 / 值形（legality 门禁）、值互不相同、ID 段与数量。"""
    rows = cas_rows() if rows is None else rows
    problems = []
    for key, row in rows.items():
        if len(row) != 1:
            problems.append(f"{key} 必须恰好一格: {row}")
            continue
        problems += L.equipment_key_problems(key, row[0])
        if L.equipment_key_capability(key) != CAPABILITY:
            problems.append(f"{key} 不归 {CAPABILITY}")
    values = [row[0] for row in rows.values() if len(row) == 1]
    duplicated = sorted({v for v in values if values.count(v) > 1})
    if duplicated:
        problems.append(f"置顶序号重复（同序号的两件回落原生顺序）: {duplicated}")
    if len(rows) != 46 or len(CURSED) != 29 or len(ABYSS) != 15:
        problems.append(f"置顶件数应为 46（1 + 29 + 15 + 1），实际 {len(rows)}")
    return problems


# ---------------------------------------------------------------------------
# 构建
# ---------------------------------------------------------------------------

def build(live: G.Live) -> dict:
    """目标态 + 与 live 的逐键差异（只在内存里算，不写盘）。"""
    problems = contract_problems()
    warnings: list = []
    rows = cas_rows()
    equipment = live.flat(EQUIPMENT_LOGICAL)
    missing = sorted(eid for eid in PINS if str(eid) not in equipment)
    if missing:
        problems.append(f"置顶装备不在 live 装备表里: {missing}")
    live_cas = live.flat(CAS_LOGICAL)
    stray = sorted(k for k in live_cas if k.startswith(PREFIX) and k not in rows)
    if stray:
        problems.append(f"live 有合同外的 {PREFIX}* 键: {stray[:5]}")
    for key, row in rows.items():
        if key in live_cas and live_cas[key] != row:
            warnings.append(f"{key} live 值 {live_cas[key]} 将改为 {row}")
    tables: dict = {}
    raw = live.raw(CAS_LOGICAL)
    if raw is None:
        problems.append(f"store 里没有 {CAS_LOGICAL}")
    else:
        staged, changed, deleted = G.repack(raw, {k: core.write_csv_lines([v]) for k, v in rows.items()})
        if changed or deleted:
            tables[CAS_LOGICAL] = (staged, changed, deleted)
    already = sorted(k for k, row in rows.items() if live_cas.get(k) == row)
    report = {
        "capability": CAPABILITY, "level": "cosmetic",
        "pins": len(rows), "already_live": len(already),
        "to_change": len(tables[CAS_LOGICAL][1]) if CAS_LOGICAL in tables else 0,
        "order": [f"{eid}={PINS[eid]}" for eid in pin_order()],
        "publish_tables": ",".join(p for p in PUBLISH_ORDER if p in tables),
    }
    return {"problems": problems, "warnings": warnings, "tables": tables, "report": report}


# ---------------------------------------------------------------------------
# 暂存
# ---------------------------------------------------------------------------

def stage(workdir: Path, live: G.Live | None = None, *, out: dict | None = None) -> dict:
    """写 <workdir>/stage/common/** 与 <workdir>/plan.json；problems 非空时拒绝且什么都不写。"""
    live = live or G.Live()
    workdir = Path(workdir)
    G._refuse_live_workdir(live, workdir)  # noqa: SLF001 - 与武器扭蛋同一道防线
    out = out or build(live)
    if out["problems"]:
        return {"refused": True, "problems": list(out["problems"])}
    stage_dir = workdir / "stage"
    if stage_dir.exists():
        shutil.rmtree(stage_dir)
    plan: dict = {"tables": {}, "files": {}, "server": {}, "deleted": {}}
    for logical, (staged, changed, deleted) in out["tables"].items():
        G._write(stage_dir / "common" / logical, staged)  # noqa: SLF001
        plan["tables"][logical] = {"changed": sorted(changed + deleted),
                                   "live_sha256": G.sha256(live.raw(logical)), "staged_sha256": G.sha256(staged)}
        if deleted:
            plan["deleted"][logical] = sorted(deleted)
    workdir.mkdir(parents=True, exist_ok=True)
    (workdir / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"refused": False, "plan": plan, "report": out["report"], "warnings": out["warnings"],
            "sizes": {k: len(v[0]) for k, v in out["tables"].items()}}


def check(live: G.Live | None = None) -> dict:
    live = live or G.Live()
    out = build(live)
    return {"store": str(live.store), "report": out["report"], "problems": out["problems"],
            "warnings": out["warnings"],
            "would_stage": {k: {"changed": len(v[1]), "deleted": len(v[2])} for k, v in out["tables"].items()}}


def main(argv: list | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check", help="只读体检：摘要与 problems")
    stage_parser = sub.add_parser("stage", help="写 <workdir>/stage/** 与 plan.json")
    stage_parser.add_argument("workdir", type=Path)
    args = parser.parse_args(argv)
    if args.command == "check":
        result = check()
        print(json.dumps(result, ensure_ascii=False, indent=1))
        return 0 if not result["problems"] else 2
    result = stage(args.workdir)
    if result["refused"]:
        print(json.dumps({"refused": True, "problems": result["problems"]}, ensure_ascii=False, indent=1))
        return 2
    plan = result["plan"]
    print(json.dumps({
        "workdir": str(args.workdir),
        "tables": {k: {"changed": len(v["changed"]), "deleted": len(plan["deleted"].get(k, []))}
                   for k, v in plan["tables"].items()},
        "sizes": result["sizes"],
        "publish_tables": result["report"]["publish_tables"],
        "report": result["report"],
        "warnings": result["warnings"],
    }, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
