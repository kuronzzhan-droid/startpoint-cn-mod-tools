# -*- coding: utf-8 -*-
"""冈达葛萨（129987 / 水 / ★5 / Supporter）kit。

把 ``work/character_packs/midautumn-20260920/design/ghandagoza.json`` 的机制计划装进现包
``work/character_packs/gbf-ghandagoza-20260919``：队长 4 行、6 个能力键共 21 行、2 个固有状态
（含 48×48 图标）、9 条面板文案、3 棵 DSL、技能文案/能量、以及超预算特效表的重打。

纪律（裁决 §6 / §8）：
- 行一律「官方 donor 行 + 逐格改」，每行过 ``wf_client_legality`` 与 ``wf_describe`` 回读；
- DSL 用 ``wf_gbf_duo_dsl`` 的构造助手拼，写完与设计稿机读树逐字比对，再过六道闸门 + 裸树往返；
- 只写候选包（``package/``）与 ``evidence/``；不碰 live store / ``assets/`` / ``.cdn`` / 设备。
"""
from __future__ import annotations

from wf.paths import root_path

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    pass  # Imports resolve from this checkout/package, not external source copies.

import wf_client_legality as L  # noqa: E402
import wf_dsl  # noqa: E402
import wf_gbf_duo_dsl as D  # noqa: E402
import wf_midautumn_kitlib as K  # noqa: E402
import wf_seasonal7_common as C  # noqa: E402

CODE = "ghandagoza"
CID = 129987
ELEMENT = 1                                   # 水（character c3）
BREAK = "12998701"                            # 敌方「瓦解」
SEABREAK = "12998702"                         # 我方「破海」（技能 15 秒窗口标记）
OPENING = "ability_skill_ghandagoza_opening"
OPENING_PROGRAM = f"battle/action/skill/action/ability_skill/{OPENING}${OPENING}"
FX_DIR = "battle/effect/skill_unique/ghandagoza/a68b8280c4ea"
FX_SHEET = f"{FX_DIR}/a68b8280c4ea.png"
FX_ATLAS = f"{FX_DIR}/a68b8280c4ea.atlas.amf3.deflate"
FX_PARTS = f"{FX_DIR}/effect.parts.amf3.deflate"
FX_SCALE = 0.32                               # 4096 / 0.32 = 12800，parts 矩阵 a/d 保持整数
PLACEHOLDER_CAPABILITY = "gbf-ghandagoza-mechanics-v1"

# 一键一值的雕像组（裁决 §8：官方 790 个多记录键 0 个混用）。选取依据见 DEVIATIONS。
STATUE_GROUP = {"1299871": "attack_common", "1299872": "special", "1299873": "special",
                "1299874": "attack_common", "1299875": "attack_common", "1299876": "special"}

DESIGN_REL = "work/character_packs/midautumn-20260920/design/ghandagoza.json"


def load_design(ctx) -> dict:
    path = ctx.root / DESIGN_REL
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- 固有状态

def unique_rows(ctx):
    """两个 8 位固有状态。donor 取官方 unique_condition 同形行，逐格改。"""
    spec = ctx.spec
    break_key, break_row = K.unique_row(
        ctx, spec, 1, "13",                       # official unique_devil_leader：c9=false/c10=true/c11=1
        {0: "unique_ghandagoza_break", 2: f"battle/common/unique_condition/unique_ghandagoza_break",
         3: "99999999", 4: "5", 9: "false", 10: "true", 11: "1", 12: "0", 13: "true"},
        name="瓦解")
    sea_key, sea_row = K.unique_row(
        ctx, spec, 2, "3",                        # official unique_zeta：900 帧、可驱散
        {0: "unique_ghandagoza_seabreak", 2: f"battle/common/unique_condition/unique_ghandagoza_seabreak",
         3: "900", 4: "1", 9: "true", 10: "false", 11: "0", 12: "0", 13: "true"},
        name="破海")
    if (break_key, sea_key) != (BREAK, SEABREAK):
        raise K.KitError(f"unique ids drifted: {break_key}/{sea_key}")
    return {break_key: break_row, sea_key: sea_row}


def unique_icons(ctx) -> dict:
    """48×48 图标：8 倍画布 + LANCZOS 缩小（与上批 unique_condition 图标同法）。"""
    from PIL import Image, ImageDraw

    def canvas():
        img = Image.new("RGBA", (384, 384), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle((16, 16, 367, 367), radius=72, fill=(16, 40, 60, 255),
                               outline=(95, 200, 232, 255), width=16)
        return img, draw

    img, draw = canvas()                                        # 瓦解：碎裂对角裂痕
    crack = [(96, 320), (150, 238), (120, 214), (196, 118), (170, 196), (206, 176), (150, 300)]
    draw.polygon(crack, fill=(220, 239, 255, 255))
    draw.polygon([(x + 96, y - 24) for x, y in crack], fill=(95, 200, 232, 255))
    break_png = img.resize((48, 48), Image.LANCZOS)

    img, draw = canvas()                                        # 破海：拳印压在分开的浪纹上
    for dy, col in ((250, (63, 169, 217, 255)), (300, (63, 169, 217, 200))):
        for off in (-1, 1):
            draw.arc((60 + off * 26, dy - 42, 324 + off * 26, dy + 42), 200, 340,
                     fill=col, width=18)
    draw.rounded_rectangle((128, 96, 256, 224), radius=36, fill=(242, 247, 255, 255))
    draw.rounded_rectangle((128, 76, 256, 120), radius=22, fill=(242, 247, 255, 255))
    draw.line((150, 150, 234, 150), fill=(16, 40, 60, 255), width=10)
    sea_png = img.resize((48, 48), Image.LANCZOS)

    written = {}
    for uid, image in ((BREAK, break_png), (SEABREAK, sea_png)):
        logical = f"battle/common/unique_condition/unique_ghandagoza_" \
                  f"{'break' if uid == BREAK else 'seabreak'}.png"
        data = ctx.png_store_bytes(image)
        ctx.write_asset("common", logical, data, owner="kit")
        written[uid] = {"icon": logical, "bytes": len(data)}
    return written


# ---------------------------------------------------------------- 队长 / 能力

def build_tables(ctx, design):
    plan = design["plan"]
    evidence = []
    leader = []
    for record in plan["leader_ability"]["rows"]:
        row, ev = K.build_row(ctx, "leader_ability", donor_key(record["donor"]), record["cells"],
                              source=donor_source(record["donor"]),
                              expect_describe=record.get("desc_expected"),
                              label=f"leader#{record['index']}")
        leader.append(row)
        evidence.append(ev)

    abilities = {}
    for key, block in plan["ability"]["keys"].items():
        slot = int(key[-1])
        rows = []
        for n, record in enumerate(block["records"]):
            cells = dict(record["cells"])
            cells["2"] = STATUE_GROUP[key]
            # during 23 / 413 是 battle 级（AbilityValues.parseAt109 不取 target）：
            # 设计稿 §2 写「c110/c111 留空」，但机读 cells 省略了它们，donor 的值会留下来。
            if str(cells.get("109", "")) in ("23", "413"):
                cells.setdefault("110", "")
                cells.setdefault("111", "")
                cells["110"] = cells["111"] = ""
            row, ev = K.build_row(ctx, "ability", donor_key(record["donor"]), cells,
                                  source=donor_source(record["donor"]), element=ELEMENT,
                                  expect_describe=record.get("desc_expected"),
                                  label=f"{key}#{n}")
            rows.append(row)
            evidence.append(ev)
        K.check_ability_key(rows, key, CODE, slot)
        abilities[key] = rows
    return leader, abilities, evidence


def donor_source(donor: str) -> str:
    return "live" if donor.startswith("live") else "official"


def donor_key(donor: str) -> str:
    """``"official 1611653#2 (during110/puller9)"`` → ``"1611653#2"``。"""
    for token in donor.replace("(", " ").split():
        head = token.split("#")[0]
        if head.isdigit():
            return token
    raise K.KitError(f"cannot read donor key from {donor!r}")


# ---------------------------------------------------------------- DSL

def ally_block(enhanced: bool):
    amount = 2.5 if enhanced else 1.5
    heals = [D.wait(frame, D.cmd("CreateRatioHeal", 1, 2, D.v(0.03), [], D.v(0),
                                 ["GenericHealHitEffect"]))
             for frame in range(120, 721, 120)]
    return D.find(1, 33,
                  D.condition(1,
                              ["ACAttackPoint", D.v(900), D.v(amount), D.v(1)],
                              ["ACPowerFlipDamage", D.v(900), D.v(amount), D.v(1)],
                              # 引擎把状态来源的逆境 min/max 各钳 0.5：写 1.5 与写 0.5 同效。
                              ["ACAdversity", D.v(900), D.v(0.5), D.v(0.5), D.v(1)]),
                  D.condition(1, ["ACUnique", int(SEABREAK), D.v(1)], cancelable=False),
                  D.cmd("CreateBarrier", 1, D.v(0.25), ["GenericBarrierHitEffect"]),
                  D.cmd("ConditionalsHealthPointRatioOf", 1, 20, D.block(), D.block(*heals)),
                  elements=(2,))


def skill_tree():
    enemies = D.find(0, 49,
                     D.cmd("DeleteCondition", 0, ["DCAll", 2], 3, 0, "", ["Default"]),
                     D.condition(0,
                                 ["ACParalysis", D.v(600)],
                                 # 254 = 全属性：带 resist_element_resistance 的 boss 只放行 0/克制属性。
                                 ["ACToleranceOfElement", D.v(900), 254, D.v(-0.3), D.v(1)]))
    return D.tree(
        D.cmd("StopBall", -18, 10, ["RestoreToSpeedBeforeActionExecution"], ["EF"], 0),
        D.effect(CODE, "a68b8280c4ea", scale=0.55),
        enemies,
        D.cmd("ConditionalsChangeSkillFlag", 1, D.block(ally_block(True)), D.block(ally_block(False))))


def opening_tree():
    return D.tree(D.find(0, 33,
                         D.cmd("CreateRatioAttack", 0, 2, D.v(1.0)),
                         # 同帧「赋予状态/护盾 → 删除 → 技能链 → 伤害」：隔一帧给护盾最稳。
                         D.wait(1, D.cmd("CreateBarrier", 0, D.v(1.0), ["GenericBarrierHitEffect"])),
                         elements=(2,)))


def dsl_gate_problems(tree):
    from wf_seasonal7_kit_philia import scope_problems, signature_problems
    from wf_gbf_duo_kit import draft_subject_problems
    problems = (signature_problems(tree) + scope_problems(tree) + draft_subject_problems(tree)
                + L.action_dsl_subject_binding_problems(tree)
                + L.action_dsl_hit_area_target_problems(tree)
                + L.action_dsl_element_problems(tree, character_element=ELEMENT)
                + wf_dsl.player_side_dsl_problems(tree))
    C.amf_bytes(tree)                       # 裸树编码/回读逐字节自检
    return problems


def check_against_design(design, name, tree):
    """与设计稿机读树逐字比对（设计稿里的固有状态号笔误按 DEVIATIONS-D11 先修正）。"""
    expected = json.loads(json.dumps(design["plan"]["skills"]["trees"][name])
                          .replace("12998703", SEABREAK))
    if tree != expected:
        raise K.KitError(f"DSL {name} 与设计稿机读树不一致：\n  built={json.dumps(tree, ensure_ascii=False)[:400]}\n"
                         f"  design={json.dumps(expected, ensure_ascii=False)[:400]}")


def write_programs(ctx, design):
    trees = {"1": skill_tree(), "2": skill_tree(), "opening": opening_tree()}
    check_against_design(design, "skill", trees["1"])
    check_against_design(design, "opening", trees["opening"])
    gates = {}
    written = []
    for name, tree in trees.items():
        problems = dsl_gate_problems(tree)
        if problems:
            raise K.KitError(f"DSL {name}: {problems}")
        gates[name] = 0
        program = OPENING_PROGRAM if name == "opening" else ctx.program_path(name)
        ctx.write_dsl(program, tree)                            # write_dsl 只吃裸树
        logical = wf_dsl.dsl_logical(program)
        if ctx.amf_parse(ctx.pack.pkg_path("common", logical).read_bytes()) != tree:
            raise K.KitError(f"DSL {program}: 写后回读不一致")
        written.append(logical)                                 # manifest 的 skills.programs 收 logical
    return written, gates


# ---------------------------------------------------------------- 文案 / 技能表

def write_texts(ctx, design):
    plan = design["plan"]["texts"]
    cas = {}
    panel = []
    for record in plan["custom_ability_string"]["rows"]:
        key, text = record["key"], record["text"]
        skill_flag = key == "change_skill_ghandagoza"
        K.check_panel(text, skill_flag=skill_flag, label=key)
        cas[key] = [[text]]
        panel.append(text)
    declared = set(ctx.spec.extra_keys.get(K.CAS, ()))
    missing = [k for k in cas if k not in declared]
    if missing:
        raise K.KitError(f"custom_ability_string keys not declared in spec.extra_keys: {missing}")
    ctx.write_flat(K.CAS, cas)

    action = plan["action_skill"]
    rows = ctx.pkg_nested(CODE)
    updates = {}
    for level, cells in rows.items():
        new = list(cells)
        new[0] = action["c0"]
        new[1] = action["c1"]
        if new[4] != str(action["energy"]):
            new[4] = str(action["energy"])
        if new != list(cells):
            updates[level] = [new]
    if updates:
        ctx.write_nested(K.ACTION, CODE, updates)

    text_row = list(ctx.pack.pkg_character_text_row())
    for col, value in ((4, action["c0"]), (5, action["c1"]), (6, action["c0"]), (7, action["c1"])):
        text_row[col] = value
    ctx.write_flat("master/character/character_text.orderedmap", {str(CID): [text_row]})
    ctx.sync_character_mirrors()
    return panel, {"action_skill_levels": sorted(rows), "energy": action["energy"],
                   "custom_ability_string": sorted(cas)}


# ---------------------------------------------------------------- 特效表瘦身

def _resize_rgba(image, size):
    """带预乘的缩小：直接缩 RGBA 会在透明边缘拉出黑边。"""
    import numpy as np
    from PIL import Image
    arr = np.asarray(image, dtype=np.float64) / 255.0
    alpha = arr[..., 3:4]
    prem = np.concatenate([arr[..., :3] * alpha, alpha], axis=-1)
    small = Image.fromarray(np.clip(prem * 255.0 + 0.5, 0, 255).astype("uint8"), "RGBA")
    small = small.resize(size, Image.LANCZOS)
    out = np.asarray(small, dtype=np.float64) / 255.0
    a2 = out[..., 3:4]
    rgb = np.where(a2 > 0, out[..., :3] / np.maximum(a2, 1e-6), 0.0)
    merged = np.concatenate([np.clip(rgb, 0.0, 1.0), a2], axis=-1)
    return Image.fromarray(np.clip(merged * 255.0 + 0.5, 0, 255).astype("uint8"), "RGBA")


def original_bytes(ctx, source, logical: str) -> bytes:
    """特效族的原始字节一律从 Studio 编译产物里取，重跑 kit 不会在已缩过的图上再缩一次。"""
    import zipfile
    zip_path = Path(source or ('${WF_ROOT}/out/冈达葛萨与索利兹导入-20260919'.replace("${WF_ROOT}", str(root_path())))) / f"{CODE}-compiled.zip"
    if zip_path.is_file():
        with zipfile.ZipFile(zip_path) as zf:
            name = f"compiled/common/{logical}"
            if name in zf.namelist():
                return zf.read(name)
    return ctx.pack.pkg_path("common", logical).read_bytes()


def repack_effect(ctx, source=None, scale: float = FX_SCALE, pad: int = 2, width: int = 1024) -> dict:
    """把 Studio 自绘特效表按 ``scale`` 重打，并把 ``.parts`` 矩阵 a/d 除回（x/y 不动）。

    记忆卡 wf-ginovi-effect-atlas-fix：换分辨率只改 a/d，靠提 ``ShowEffect`` 的 scale 会把
    x/y 平移一起放大，整族错位。
    """
    from PIL import Image

    atlas = ctx.amf_parse(original_bytes(ctx, source, FX_ATLAS))
    parts = ctx.amf_parse(original_bytes(ctx, source, FX_PARTS))
    sheet = ctx.png_open(original_bytes(ctx, source, FX_SHEET)).convert("RGBA")
    before = list(sheet.size)
    if {(m["a"], m["d"]) for m in parts["t"]} != {(4096, 4096)}:
        raise K.KitError("特效族原始 parts 矩阵不是 1:1，重打前必须先核对基准")

    rects = {}
    for entry in atlas:
        rects.setdefault((entry["x"], entry["y"], entry["w"], entry["h"]), []).append(entry)
    order = sorted(rects, key=lambda r: (-int(round(r[3] * scale)) or -1, -r[2]))

    placed, x, y, shelf = {}, pad, pad, 0
    for rect in order:
        w = max(1, int(round(rect[2] * scale)))
        h = max(1, int(round(rect[3] * scale)))
        if x + w + pad > width:
            x, y, shelf = pad, y + shelf + pad, 0
        placed[rect] = (x, y, w, h)
        x += w + pad
        shelf = max(shelf, h)
    height = y + shelf + pad

    out = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    for rect, (nx, ny, nw, nh) in placed.items():
        crop = sheet.crop((rect[0], rect[1], rect[0] + rect[2], rect[1] + rect[3]))
        out.paste(_resize_rgba(crop, (nw, nh)), (nx, ny))
    if out.getchannel("A").getextrema()[0] != 0:
        raise K.KitError("repacked effect sheet has no fully transparent pixel")

    for rect, entries in rects.items():
        nx, ny, nw, nh = placed[rect]
        for entry in entries:
            entry["x"], entry["y"], entry["w"], entry["h"] = nx, ny, nw, nh

    factor = 1.0 / scale
    touched = 0
    for matrix in parts["t"][1:]:
        a, d = matrix["a"] * factor, matrix["d"] * factor
        if a != int(a) or d != int(d):
            raise K.KitError(f"parts matrix a/d would stop being integral at scale {scale}")
        matrix["a"], matrix["d"] = int(a), int(d)
        touched += 1

    ctx.write_asset("common", FX_SHEET, ctx.png_store_bytes(out), owner="kit")
    ctx.write_asset("common", FX_ATLAS, C.amf_bytes(atlas), owner="kit")
    ctx.write_asset("common", FX_PARTS, C.amf_bytes(parts), owner="kit")
    check = ctx.amf_parse(ctx.pack.pkg_path("common", FX_ATLAS).read_bytes())
    if check != atlas:
        raise K.KitError("effect atlas write-back mismatch")
    return {"scale": scale, "png_before": before, "png_after": list(out.size),
            "mpx_before": round(before[0] * before[1] / 1e6, 4),
            "mpx_after": round(width * height / 1e6, 4),
            "rects": len(rects), "matrices_scaled": touched}


def atlas_budget(ctx) -> dict:
    import subprocess
    cmd = [sys.executable, "mod-tools/wf_atlas_budget_check.py", "--pack",
           str(ctx.workspace.relative_to(ctx.root)).replace("\\", "/"), "--quiet"]
    proc = subprocess.run(cmd, cwd=ctx.root, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    payload = {"returncode": proc.returncode, "stdout_tail": proc.stdout[-2000:]}
    try:
        payload["report"] = json.loads(proc.stdout)
    except Exception:
        payload["stderr_tail"] = proc.stderr[-800:]
    return payload


# ---------------------------------------------------------------- 杂项闸门

def stale_art_problems(ctx) -> list[str]:
    """包内非表美术件不得比 live 旧：本角色 live 无任何键，只核对共享路径没有被顶掉。"""
    problems = []
    for name, record in sorted(ctx.pack.owned_outputs().items()):
        root, _, logical = name.partition(":")
        if logical.endswith((".orderedmap", ".json")):
            continue
        if f"/{CODE}/" in logical or logical.endswith(f"/{CODE}.png") or CODE in logical:
            continue
        try:
            live = ctx.live_read(logical)
        except Exception:
            continue
        if live is not None:
            problems.append(f"{root}:{logical} 与 live 同名（共享路径），需人工确认新旧")
    return problems


def drop_placeholder_capability(ctx) -> dict:
    """占位能力名必须在重建 manifest 前删掉：manifest 的 capabilities 是并集合并。"""
    path = ctx.package / "manifest.json"
    if not path.is_file():
        return {"removed": False, "reason": "manifest.json absent"}
    manifest = json.loads(path.read_text(encoding="utf-8"))
    caps = list(manifest.get("required_capabilities") or [])
    if PLACEHOLDER_CAPABILITY not in caps:
        return {"removed": False, "required_capabilities": caps}
    manifest["required_capabilities"] = [c for c in caps if c != PLACEHOLDER_CAPABILITY]
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"removed": True, "required_capabilities": manifest["required_capabilities"]}


DEVIATIONS = [
    {"id": "D-KIT-1", "item": "设计稿 design/ghandagoza.json 的技能树里 ACUnique 写 12998703",
     "landed": "改成 12998702（破海）",
     "why": "12998703 在 unique_condition 里不存在；能力1/能力6 的 during 134 读的是 12998702，"
            "不改则 421 独立乘区（追击等价与逆境等价）整条链永不触发"},
    {"id": "D-KIT-2", "item": "设计稿把 ability c2 statue_group 按行给（1299871/1299873/1299876 混用）",
     "landed": "每键单值：1299871/1299874/1299875 = attack_common，1299872/1299873/1299876 = special",
     "why": "裁决 §8：官方 790 个多记录键 0 个混用。取值按「该组在本键各 kind 上的官方先例数」择优："
            "special 覆盖 629/468/227/16/536（1299873、1299876）与 instant 413（1299872）；"
            "attack_common 覆盖 during 0/23 与 instant 211/53/118。"
            "during 421 官方零行、during 158 只在 attack_blue/green、instant 51 只在 special，"
            "这三处无论选哪组都没有同组先例，已按覆盖面最大者取舍"},
    {"id": "D-KIT-3", "item": "设计稿 §7 主案写「把 ShowEffect 的 scale 从 0.55 提到 1.28」",
     "landed": "ShowEffect scale 保持 0.55，改为把 .parts 矩阵 a/d 乘 1/0.32（4096 → 12800）",
     "why": "ShowEffect 的 scale 会把矩阵里的 x/y 平移一起放大，整族零件错位；"
            "记忆卡 wf-ginovi-effect-atlas-fix 的正解是只动 a/d、x/y 不动。"
            "缩放比取 0.32 而不是设计稿的 0.43：4096/k 必须是整数，且 0.4 时 five-boss-r1 仍装不下"
            "（layer0_pct 4.31、fits=false），0.32 给出 layer0_pct 3.32 且两个场景都 fits"},
    {"id": "D-KIT-4", "item": "共享文件 wf_gbf_duo_dsl.condition() 把 CreateCondition 下标 10 写死 1",
     "landed": "加 target_kind 参数，默认 3（Member）",
     "why": "裁决 §8 点名；FindAllSubjects 33/34/35/49/82 下官方一律 3，错配 = 施法 C16102。"
            "同一修复同时覆盖索利兹的 soriz_skill"},
    {"id": "D-KIT-5", "item": "共享文件 wf_gbf_duo_dsl 的 ghandagoza_skill/ghandagoza_opening 用 find(_, 35)",
     "landed": "改 33（己方全体含自身）",
     "why": "35 = 除自身外，冈达葛萨本人拿不到压血/护盾/技能增益，能力1「自身每损失1%」永不触发。"
            "soriz_skill 的同一处留给索利兹代理（不越权改别人的角色逻辑）"},
    {"id": "D-KIT-6", "item": "wf_gbf_duo.context() 的 texts / required_capabilities / extra_keys",
     "landed": "存在 B/design/<code>.json 时按其 spec/texts 覆盖（缺文件时行为逐字不变）",
     "why": "tables 会用 spec.texts 覆写 action_skill 的技能描述，与 kit 写的描述打架；"
            "kit 自有键（固有状态、custom_ability_string）也必须进 spec.extra_keys 才过占用断言"},
]

NOTES = [
    "未发布、未写 live store / assets / .cdn、未 git add，未重启服务。",
    "能力 3 的 8 秒无敌与 50% 屏障走触发 189 + puller 5 + target 7，组合零先例（设计稿 R5/C6）；"
    "真机若只有自己吃到，退路是回落 puller 0 / target 0。",
    "能力 3 的 468 ConditionGuts 写 target 5（官方/live 全是 target 0），设计稿 R4 已登记；"
    "金丝雀 C2 就是验这条。",
    "during 内容 421 官方零行（live 仅 1699802#4），追击等价与逆境等价全押在它上面（R3）；"
    "退路是改 during 413，作用面收窄到强化弹射。",
    "技能与开场树都不含 CreateNormalAttack，根头 tree[10] 保持 0（自动档）。",
    "副本 flow preflight：requires_client_base=1.4.933 时 rc=2，唯一红项是"
    "「cannot reach validated tail 1.4.928」——flow 账本 base 1.4.927/validated 1.4.928 落后于"
    " legacy 链尾 1.4.933（记忆卡 wf-flow-ledger-dual-tail），全批 ma-* 包同样是 1.4.933，"
    "属批次级链状态，须作者授权 reanchor 后才过。把副本 manifest 的 base 改成 1.4.928 再跑：rc=0、"
    "ok=true、can_prepare=true、conflicts=[]、writes_live=false、master_reference.release_ready=true、"
    "特效族 54 张纹理全部可解析。证据 evidence/flow-inspect.json。",
    "wf_gbf_duo_dsl.ghandagoza_skill / ghandagoza_opening 是旧草稿助手，已被本 kit 取代"
    "（本 kit 不调用它们）；本轮只修了它们的选择器与 CreateCondition 付与对象种类。",
]


def build(pack, source=None) -> dict:
    from wf_seasonal7_build import KitContext
    ctx = KitContext(pack)
    if ctx.spec.code != CODE:
        raise K.KitError(f"kit is for {CODE}, got {ctx.spec.code}")
    design = load_design(ctx)

    capability_state = drop_placeholder_capability(ctx)

    uniques = unique_rows(ctx)
    K.write_unique(ctx, ctx.spec, uniques)
    icons = unique_icons(ctx)

    leader, abilities, row_evidence = build_tables(ctx, design)
    ctx.write_flat(K.LEADER, {str(CID): leader})
    ctx.write_flat(K.ABILITY, {key: rows for key, rows in abilities.items()})

    panel, text_state = write_texts(ctx, design)
    programs, gates = write_programs(ctx, design)

    effect = repack_effect(ctx, source, scale=float(os.environ.get("WF_GHAND_FX_SCALE") or FX_SCALE))
    budget = atlas_budget(ctx)
    stale = stale_art_problems(ctx)

    capabilities = sorted({cap for ev in row_evidence for cap in ev["capabilities"]})
    ctx.evidence_write("kit-rows-ghandagoza.json",
                       {"leader": leader, "abilities": abilities, "unique": uniques,
                        "rows": row_evidence, "row_capabilities": capabilities})
    ctx.evidence_write("kit-effect-repack.json", {"repack": effect, "atlas_budget": budget})

    report = K.report(
        ctx,
        summary=f"冈达葛萨 kit：队长 {len(leader)} 行、能力 "
                f"{sum(len(v) for v in abilities.values())} 行、固有状态 2、DSL {len(programs)} 棵、"
                f"特效表 {effect['mpx_before']}→{effect['mpx_after']} Mpx",
        status=K.READY,
        panel=panel,
        notes=NOTES + [f"行级 required_client_capabilities 并集 = {capabilities or '空'}",
                       f"占位能力名处理：{capability_state}",
                       f"包内共享路径美术件核对：{stale or '无同名共享件'}"],
        programs=programs,
        unique_condition={uid: icons[uid] for uid in uniques},
        required_capabilities=ctx.spec.required_capabilities,
        deviations=DEVIATIONS,
        extra={"row_capabilities": capabilities, "effect_repack": effect,
               "atlas_budget": budget.get("report") or budget, "texts": text_state,
               "dsl_gates": gates, "stale_art": stale},
    )
    return report
