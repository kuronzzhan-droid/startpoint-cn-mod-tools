# -*- coding: utf-8 -*-
"""诅咒武器第四轮 + 深渊武器二期：在 kulo 1.4.149 视图上组装一个客户端补丁 zip + 服务端 JSON 全量副本。

前置：python patch_generator.py（生成 wf_cursed_weapons_r4.py）；图标定稿在 ../art/final/<slug>.png、<slug>_lv120.png。
用法：python stage_all.py [--allow-missing-art]
产物：../patch/<zip> + integrity json；../server/*.json + server_diff.md；../stage_report.json
只读 kulo；不碰 manifest / active / 服务端进程。
"""
from __future__ import annotations

import copy
import csv
import hashlib
import io
import json
import shutil
import sys
import zipfile
from pathlib import Path

from live149 import *  # noqa: F401,F403  (flat/nested/server/read_raw/load/member/KULO/ASSETS/q)
import wf_cursed_weapons_r4 as W
sys.modules["wf_cursed_weapons"] = W          # abyss2 复用同一套行构建器
import abyss2  # noqa: E402
import wf_dsl  # noqa: E402
from wf_character_revision import encode_tree  # noqa: E402
from PIL import Image  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
ART = OUT / "art" / "final"
import os
STAGE = Path(os.environ.get("CA_STAGE_DIR", str(OUT)))   # 全量重建目录（默认 = 1.4.150 交付目录）
PATCH = STAGE / "patch"
SERVER_OUT = STAGE / "server"
ZIP_NAME = "pinball-1.4.149-1.4.150-1-cursed-r4-abyss2-local.zip"
SOUL_TINT = (44, 204, 254)        # 现有深渊魂珠图标 = 本体 ×0.7 + 青色 ×0.3（15 把拟合，B 通道误差 <0.3）


def csv_text(rows: list[list[str]]) -> str:
    s = io.StringIO(newline="")
    csv.writer(s, lineterminator="\n").writerows(rows)
    return s.getvalue()


def png_cdn(im: Image.Image) -> bytes:
    buf = io.BytesIO()
    im.convert("RGBA").save(buf, format="PNG", optimize=True)
    data = buf.getvalue()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return b"\x89png" + data[4:]


def soul_icon(im: Image.Image) -> Image.Image:
    px = im.convert("RGBA").load()
    out = Image.new("RGBA", im.size)
    po = out.load()
    for y in range(im.size[1]):
        for x in range(im.size[0]):
            r, g, b, a = px[x, y]
            po[x, y] = tuple(int(round(c * 0.7 + t * 0.3)) for c, t in zip((r, g, b), SOUL_TINT)) + (a,) if a else (0, 0, 0, 0)
    return out


def main(argv: list[str]) -> int:
    allow_missing_art = "--allow-missing-art" in argv
    report: dict = {"tables": {}, "files": [], "server": {}, "problems": []}
    # ------------------------------------------------------------ 诅咒第四轮
    W._check_collisions = lambda *a, **k: None
    cur = W.build(reader(W), client_capabilities=W.PATCHED_CLIENT_CAPABILITIES)
    report["problems"] += cur["problems"]
    report["cursed_over_budget"] = W.ROUND4_OVER_BUDGET
    report["cursed_budgets"] = {r: {k: cur["budgets"][r][k] for k in ("blades", "multipliers")} for r in cur["budgets"]}
    changes: dict[str, dict[str, list[list[str]]]] = {}
    for lp, keys in cur["flat"].items():
        live = flat(lp)
        for k, v in keys.items():
            if live.get(k) != v:
                changes.setdefault(lp, {})[k] = v
    files: dict[str, bytes] = {}
    for prog, tree in cur["dsl"].items():
        lp = wf_dsl.dsl_logical(prog)
        try:
            same = dsl_tree(prog) == tree
        except Exception:
            same = False
        if not same:
            files[lp] = encode_tree(tree)
    # 服务端：诅咒自有键差异只有 kulo 额外的 enhancementPurchaseMode（不动）
    # ------------------------------------------------------------ 深渊二期
    ab = abyss2.build(flat, nested, server)
    report["problems"] += ab["problems"]
    for lp, keys in ab["flat"].items():
        live = flat(lp)
        clash = sorted(set(keys) & set(live))
        assert not clash, (lp, clash)
        for k, v in keys.items():
            changes.setdefault(lp, {})[k] = v
    for lp, keys in ab["nested"].items():
        clash = sorted(set(keys) & set(nested(lp)))
        assert not clash, (lp, clash)
    for prog, tree in ab["dsl"].items():
        lp = wf_dsl.dsl_logical(prog)
        try:
            read_raw(lp)
            raise SystemExit(f"DSL 已存在：{lp}")
        except FileNotFoundError:
            pass
        files[lp] = encode_tree(tree)
    # ------------------------------------------------------------ 平表 / 嵌套表
    for lp, keys in changes.items():
        node = load(lp)
        before = dict(node)
        for k, rows_ in keys.items():
            node[k] = csv_text(rows_)
        data = q.build_node(node)
        back = q.parse_node(data)
        assert back == node, lp
        assert all(back[k] == v for k, v in before.items() if k not in keys), lp
        for k, rows_ in keys.items():
            assert [r for r in rows(back[k]) if r] == rows_, (lp, k)
        files[lp] = data
        report["tables"][lp] = {"changed": sorted(k for k in keys if k in before), "added": sorted(k for k in keys if k not in before)}
    for lp, keys in ab["nested"].items():
        node = load(lp)
        before = copy.deepcopy(node)
        node.update(keys)
        data = q.build_node(node)
        back = q.parse_node(data)
        assert back == node and all(back[k] == v for k, v in before.items()), lp
        files[lp] = data
        report["tables"][lp] = {"changed": [], "added": sorted(keys)}
    # ------------------------------------------------------------ 图标（20×20，CDN 小写签名）
    missing = []
    for s in ab["specs"]:
        lv0, lv120 = ART / f"{s.slug}.png", ART / f"{s.slug}_lv120.png"
        if not (lv0.exists() and lv120.exists()):
            missing.append(s.slug)
            if not allow_missing_art:
                continue
            lv0 = lv120 = OUT / "art" / "ref" / "item_equipment_mod_abyss_universal_03.png"
        im0, im120 = Image.open(lv0).convert("RGBA"), Image.open(lv120).convert("RGBA")
        assert im0.size == (20, 20) and im120.size == (20, 20), s.slug
        files[f"{abyss2.IMG}/{s.slug}.png"] = png_cdn(im0)
        files[f"{abyss2.IMG}/{s.slug}_lv120.png"] = png_cdn(im120)
        files[f"{abyss2.IMG}/soul/{s.slug}.png"] = png_cdn(soul_icon(im0))
    if missing and not allow_missing_art:
        raise SystemExit(f"缺图标：{missing}")
    report["missing_art"] = missing
    for lp in files:
        if lp.endswith(".png"):
            try:
                read_raw(lp)
                raise SystemExit(f"图标路径已存在：{lp}")
            except FileNotFoundError:
                pass
            assert files[lp][:4] == b"\x89png"
    # ------------------------------------------------------------ zip
    PATCH.mkdir(parents=True, exist_ok=True)
    for old in PATCH.glob("*.zip"):
        old.unlink()
    zpath = PATCH / ZIP_NAME
    members = {member(lp): data for lp, data in files.items()}
    assert len(members) == len(files)
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(members):
            z.writestr(name, members[name])
    blob = zpath.read_bytes()
    integrity = {"name": zpath.name, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(),
                 "members": len(members), "files": sorted(members),
                 "member_sha256": {n: hashlib.sha256(members[n]).hexdigest() for n in sorted(members)},
                 "logical_paths": {member(lp): lp for lp in sorted(files)},
                 "applies_on": "1.4.149", "suggested_version": "1.4.150"}
    (PATCH / (ZIP_NAME[:-4] + ".integrity.json")).write_text(json.dumps(integrity, ensure_ascii=False, indent=2) + "\n", "utf-8")
    report["zip"] = {k: integrity[k] for k in ("name", "size", "sha256", "members")}
    # ------------------------------------------------------------ 服务端 JSON（全量副本，按原样式）
    if SERVER_OUT.exists():
        shutil.rmtree(SERVER_OUT)
    SERVER_OUT.mkdir(parents=True)
    diff_lines = ["# 服务端 JSON 改动（相对 kulo assets/ 现状）", ""]
    for name, delta in ab["server"].items():
        path = ASSETS / name
        raw = path.read_bytes()
        crlf = b"\r\n" in raw
        text = raw.decode("utf-8").replace("\r\n", "\n")
        value = json.loads(text)
        style = detect_style(text)
        assert dump_like(value, style) == text, f"{name} 无法按原样式复现"
        merged = json.loads(text)
        added = []
        if isinstance(merged, list):
            merged += [x for x in delta if x not in merged]   # 已安装（1.4.150 起）则幂等
            added = [str(x) for x in delta]
        elif name == "event_item_shop.json":
            shop = merged["11"]["700099"]
            assert all(shop[k] == v for k, v in delta.items() if k in shop), name
            shop.update(delta)
            added = list(delta)
        elif name == "equipment_awakening_material.json":
            ro = merged["rarityOverrides"]
            assert all(ro[k] == v for k, v in delta["rarityOverrides"].items() if k in ro), name
            ro.update(delta["rarityOverrides"])
            added = [f"rarityOverrides.{k}" for k in delta["rarityOverrides"]]
        else:
            clash = [k for k in delta if k in merged and merged[k] != delta[k]]
            assert not clash, (name, sorted(clash)[:5])
            merged.update(delta)
            added = list(delta)
        out = dump_like(merged, style)
        assert json.loads(out) == merged
        (SERVER_OUT / name).write_bytes((out.replace("\n", "\r\n") if crlf else out).encode("utf-8"))
        report["server"][name] = added
        diff_lines.append(f"- `{name}`：新增 {len(added)} 项：{', '.join(added)}")
    diff_lines += ["", "诅咒武器第四轮：服务端无改动（强化商店/装备登记键不变；kulo 额外的 enhancementPurchaseMode 原样保留）。",
                   "未改：equipment_degree_rewards.json（src/lib/equipment-degree-rewards.ts 写死 8000101-8000115 15 把并校验 JSON 一致，"
                   "加新 ID 会让称号配置校验失败）。"]
    (SERVER_OUT / "server_diff.md").write_text("\n".join(diff_lines) + "\n", "utf-8")
    report["dsl_files"] = sorted(lp for lp in files if lp.endswith(".deflate"))
    (STAGE / "stage_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str) + "\n", "utf-8")
    print(json.dumps({"zip": report["zip"], "problems": report["problems"], "missing_art": missing,
                      "tables": {k: {kk: len(vv) for kk, vv in v.items()} for k, v in report["tables"].items()},
                      "over_budget": W.ROUND4_OVER_BUDGET}, ensure_ascii=False, indent=1))
    return 1 if report["problems"] else 0


def detect_style(text: str) -> dict:
    indent = None
    for line in text.splitlines()[1:6]:
        stripped = line.lstrip(" ")
        if stripped and len(line) != len(stripped):
            indent = len(line) - len(stripped)
            break
    if indent is None and "\n" in text.strip():
        indent = 0
    separators = (", ", ": ") if indent is None else (",", ": ")
    if indent is None and '":' in text and '": ' not in text:
        separators = (",", ":")
    return {"indent": indent, "separators": separators, "trailing": text[len(text.rstrip()):]}


def dump_like(value, style: dict) -> str:
    return json.dumps(value, ensure_ascii=False, indent=style["indent"], separators=style["separators"]) + style["trailing"]


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
