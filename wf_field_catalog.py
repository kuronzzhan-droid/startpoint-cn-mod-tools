#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""wf_field_catalog.py — 全库场地效果程序目录(深渊法阵弹药库)。

扫描 store 里所有 action DSL,解出 StartBuffField / StartModifierField /
CreateFlood 命令的**效果种类+数值+时长**,过滤掉带攻击判定的脏程序,
自动分类(加成/诅咒/场地/领域)产出 rogue_field_menu.json:
    [{label, program, note, cat, kinds, duration_s, src, cmd}]
wf_rogue_build.FIELD_MENU 与 GUI 图鉴均以此为单一事实源(缺文件回退内置菜单)。

用法(项目根):
  python mod-tools/wf_field_catalog.py            # 干跑:打印统计
  python mod-tools/wf_field_catalog.py --write    # 写 mod-tools/rogue_field_menu.json
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
import zlib
from pathlib import Path

MOD_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(MOD_DIR))
import wf_quest_lib as q  # noqa: E402

PATHLIST = MOD_DIR / "WF_PATHLIST_recovered.txt"
OUT_JSON = MOD_DIR / "rogue_field_menu.json"

# ---- 场命令三类(2026-07-29 全库命令词表普查:action DSL 一共只有 14 个命令)----
# ① 数值领域(原始三件套):预载 resolver case 80/84/65 **静态实锤全覆盖**,最安全。
FIELD_CMDS = {"StartBuffField", "StartModifierField", "CreateFlood"}
# ② 环境场:会推球/打人,但**参数里不引用任何外部资产**——CreateWindAttack 是
#    [方向, 强度, 时长帧];CreateGravitationalField 是 [.., 时长, 半径.., ["Center"],
#    ["Center"], ..] 用语义锚点。没有资产路径 ⇒ 不存在"预载集合外的引用"这条 C8016
#    路径,是这批里唯一敢碰的。用户 2026-07-29 需求「刮风/落雷这类再多一点」。
#    ⚠ resolver 对这两个 case 的资产解析**未经实锤**,首次上线须走钉选实验层。
ENV_CMDS = {"CreateWindAttack", "CreateGravitationalField"}
# ③ 脏命令:带攻击判定/位移/召唤,当法阵会被载体反复施放。
#    ⚠ CreateTornado 留在这里**不是**因为它打人,而是它的参数带**绝对坐标 +
#      外部特效资产路径**(["CreateTornado",-2,324,1656,...,"battle/action/.../
#      tornado_shot1",true]):坐标烤死在老家地形(C14102 位移炸弹同型)、资产跨场
#      缺预载(C8016),两个已知失败模式一起踩。要放行得先解决预载,不在本轮范围。
SCAN_CMDS: set = set()   # 见文件末 = FIELD_CMDS | ENV_CMDS(定义在 DIRTY 之后)
DIRTY_CMDS = {"CreateNormalAttack", "CreateRatioAttack", "CreateFixedAttack",
              "CreateOnlyHitAttack", "CreateHitArea", "CreateShockWaveAttack",
              "CreateTargetAttack", "CreateTornado",
              "SpawnFunnel", "MoveBall", "Revive"}
SCAN_CMDS = FIELD_CMDS | ENV_CMDS

KIND_CN = {"Attack": "攻击", "SkillDamage": "技能伤害", "AbilityDamage": "能力伤害",
           "ElementResistance": "元素耐性", "Regeneration": "再生", "Slip": "滑行损血",
           "Frozen": "冰冻", "FeverPoint": "FEVER点", "Stunify": "眩晕",
           "PinchSlayer": "背水", "DebuffResistance": "减益耐性", "Piercing": "贯通",
           "Flying": "飞行", "PowerFlipDamage": "强化弹射", "DirectDamage": "直击",
           "Silence": "沉默", "AdditionalDirectAttack": "追击", "Speedup": "加速",
           "BuffRejection": "禁增益", "HealRejection": "禁疗", "Adversity": "逆境",
           "ComboBoost": "连击加成", "ComboRestriction": "连击限制",
           "SkillGaugeCharging": "充能", "ConvertToAttack": "转化攻击",
           "SeparatedTerm2ndDamage": "二段伤害"}


# ---------------------------------------------------------------- AMF3 微解析
def _u29(d: bytes, i: int) -> tuple[int, int]:
    v = 0
    for n in range(4):
        b = d[i]
        i += 1
        if n == 3:
            v = (v << 8) | b
            break
        v = (v << 7) | (b & 0x7F)
        if not (b & 0x80):
            break
    return v, i


def _utf_vr(d: bytes, i: int, ctx: dict) -> tuple[str, int]:
    ln, i = _u29(d, i)
    if not (ln & 1):
        idx = ln >> 1
        tab = ctx["s"]
        return (tab[idx] if idx < len(tab) else f"<ref{idx}>"), i
    n = ln >> 1
    s = d[i:i + n].decode("utf-8", "replace")
    if s:
        ctx["s"].append(s)
    return s, i + n


def _val(d: bytes, i: int, ctx: dict):
    t = d[i]
    i += 1
    if t == 0x00 or t == 0x01:
        return None, i
    if t == 0x02:
        return False, i
    if t == 0x03:
        return True, i
    if t == 0x04:
        v, i = _u29(d, i)
        if v & 0x10000000:
            v -= 0x20000000
        return v, i
    if t == 0x05:
        return struct.unpack(">d", d[i:i + 8])[0], i + 8
    if t == 0x06:
        s, i = _utf_vr(d, i, ctx)
        return s, i
    if t == 0x09:
        ln, i = _u29(d, i)
        if not (ln & 1):
            return f"<arrref{ln >> 1}>", i
        n = ln >> 1
        # assoc 部分(空键结束)
        while True:
            k, i = _utf_vr(d, i, ctx)
            if k == "":
                break
            _, i = _val(d, i, ctx)
        out = []
        for _ in range(n):
            v, i = _val(d, i, ctx)
            out.append(v)
        return out, i
    if t == 0x0A:                      # object(haxe 匿名结构)
        u, i = _u29(d, i)
        if not (u & 1):
            return "<objref>", i
        if u & 2:                      # traits 内联
            ext, dyn, nsealed = bool(u & 4), bool(u & 8), u >> 4
            cname, i = _utf_vr(d, i, ctx)
            sealed = []
            for _ in range(nsealed):
                s, i = _utf_vr(d, i, ctx)
                sealed.append(s)
            ctx["t"].append((cname, sealed, dyn, ext))
        else:                          # traits 引用
            idx = u >> 2
            cname, sealed, dyn, ext = (ctx["t"][idx] if idx < len(ctx["t"])
                                       else ("", [], True, False))
        if ext:
            raise ValueError("externalizable 对象不支持")
        obj = {}
        for name in sealed:
            v, i = _val(d, i, ctx)
            obj[name] = v
        if dyn:
            while True:
                k, i = _utf_vr(d, i, ctx)
                if k == "":
                    break
                v, i = _val(d, i, ctx)
                obj[k] = v
        return obj, i
    raise ValueError(f"未知 AMF3 标记 0x{t:02x} @ {i - 1}")


def parse_dsl(raw: bytes):
    data = zlib.decompress(raw, -15)
    v, _ = _val(data, 0, {"s": [], "t": []})
    return v


# ---------------------------------------------------------------- AMF3 写入器
def _w_u29(v: int) -> bytes:
    v &= 0x1FFFFFFF
    if v < 0x80:
        return bytes([v])
    if v < 0x4000:
        return bytes([0x80 | (v >> 7), v & 0x7F])
    if v < 0x200000:
        return bytes([0x80 | (v >> 14), 0x80 | ((v >> 7) & 0x7F), v & 0x7F])
    return bytes([0x80 | (v >> 22), 0x80 | ((v >> 15) & 0x7F),
                  0x80 | ((v >> 8) & 0x7F), v & 0xFF])


def build_val(n) -> bytes:
    """树 → AMF3 字节(字符串全内联不建引用表——合法且读取器通吃)。"""
    if n is None:
        return b"\x01"
    if n is True:
        return b"\x03"
    if n is False:
        return b"\x02"
    if isinstance(n, int):
        if -0x10000000 <= n < 0x10000000:
            return b"\x04" + _w_u29(n)
        return b"\x05" + struct.pack(">d", float(n))
    if isinstance(n, float):
        return b"\x05" + struct.pack(">d", n)
    if isinstance(n, str):
        if n.startswith("<ref") or n.startswith("<arrref") or n.startswith("<objref"):
            raise ValueError(f"树含引用占位符 {n!r},拒绝序列化")
        b = n.encode("utf-8")
        return b"\x06" + _w_u29((len(b) << 1) | 1) + b
    if isinstance(n, list):
        out = bytearray(b"\x09")
        out += _w_u29((len(n) << 1) | 1)
        out += b"\x01"                      # 空 assoc
        for c in n:
            out += build_val(c)
        return bytes(out)
    if isinstance(n, dict):
        out = bytearray(b"\x0a")
        out += _w_u29(0x0B)                 # 内联 traits/dynamic/0 sealed
        out += b"\x01"                      # classname ""
        for k, v in n.items():
            kb = k.encode("utf-8")
            out += _w_u29((len(kb) << 1) | 1) + kb
            out += build_val(v)
        out += b"\x01"                      # dynamic 结束
        return bytes(out)
    raise TypeError(f"不可序列化节点 {type(n)}")


def build_dsl(tree) -> bytes:
    co = zlib.compressobj(9, zlib.DEFLATED, -15)
    return co.compress(build_val(tree)) + co.flush()


# ---------------------------------------------------------------- 锻造手术
def clean_tree(node):
    """剔除脏命令(['Command',[攻击类,...]] 包装),递归含嵌套 Block/对象。"""
    if isinstance(node, list):
        out = []
        for c in node:
            if (isinstance(c, list) and len(c) == 2 and c[0] == "Command"
                    and isinstance(c[1], list) and c[1]
                    and isinstance(c[1][0], str) and c[1][0] in DIRTY_CMDS):
                continue
            out.append(clean_tree(c))
        return out
    if isinstance(node, dict):
        return {k: clean_tree(v) for k, v in node.items()}
    return node


def scale_tree(node, factor: float):
    """kind 枚举([KIND,...参数])的数值参数×factor(ElementResistance 缩第 2 个数)。"""
    if isinstance(node, list):
        if node and isinstance(node[0], str) and node[0] in KIND_CN:
            out = [scale_tree(c, factor) if isinstance(c, (list, dict)) else c
                   for c in node]
            nums = [i for i, x in enumerate(out)
                    if isinstance(x, (int, float)) and not isinstance(x, bool)]
            ti = None
            if nums:
                ti = nums[1] if (node[0] == "ElementResistance" and len(nums) > 1) else nums[0]
            if ti is not None:
                v = out[ti] * factor
                out[ti] = int(round(v)) if isinstance(out[ti], int) else v
            return out
        return [scale_tree(c, factor) for c in node]
    if isinstance(node, dict):
        return {k: scale_tree(v, factor) for k, v in node.items()}
    return node


def forge(program: str, clean: bool = False, scale: float | None = None) -> str:
    """锻造变体程序:读原始 → (净化/缩放) → 写 store 新逻辑路径,返回新程序名。

    新逻辑路径 = battle/action/enemy/action/mod_rogue/f_<指纹>;store 按逻辑名
    sha1 派生,客户端同派生 → 新路径天然可寻址(自制角色资产同机制,已真机验证)。
    """
    import hashlib
    logical = program + ".action.dsl.amf3.deflate"
    tree = parse_dsl(q.store_path(logical).read_bytes())
    if clean:
        tree = clean_tree(tree)
    if scale is not None and abs(scale - 1.0) > 1e-9:
        tree = scale_tree(tree, scale)
    # 写前自校验:序列化→再解析必须等价
    blob = build_dsl(tree)
    if parse_dsl(blob) != tree:
        raise RuntimeError(f"{program} 锻造自校验失败(build→parse 不等价)")
    tag = hashlib.sha1(f"{program}|{int(clean)}|{scale or 1}".encode()).hexdigest()[:10]
    new_prog = f"battle/action/enemy/action/mod_rogue/f_{tag}"
    dst = q.store_path(new_prog + ".action.dsl.amf3.deflate")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(blob)
    return new_prog


# ---------------------------------------------------------------- 命令走查
def walk_cmds(node, out: list):
    if isinstance(node, list):
        if node and isinstance(node[0], str) and (node[0] in SCAN_CMDS or node[0] in DIRTY_CMDS):
            out.append(node)
        for c in node:
            walk_cmds(c, out)
    elif isinstance(node, dict):
        for v in node.values():
            walk_cmds(v, out)


def kinds_of(cmd: list) -> list[dict]:
    """StartBuffField params[2] / StartModifierField params[1] = kind 枚举数组。"""
    arr = None
    for p in cmd[1:]:
        if isinstance(p, list) and p and all(
                isinstance(k, list) and k and isinstance(k[0], str) and k[0] in KIND_CN
                for k in p):
            arr = p
            break
    if arr is None:
        return []
    out = []
    for k in arr:
        vals = [x for x in k[1:] if isinstance(x, (int, float)) and not isinstance(x, bool)]
        entry = {"kind": k[0], "value": vals[0] if vals else None}
        if k[0] == "ElementResistance" and len(vals) >= 2:
            entry = {"kind": k[0], "element": int(vals[0]), "value": vals[1]}
        out.append(entry)
    return out


def duration_of(cmd: list):
    # 环境场的时长固定在第 3 个参数(实测 CreateWindAttack[方向,强度,时长]、
    # CreateGravitationalField[?,强度,时长,半径…]),用"首个正数"会读成强度
    if cmd and cmd[0] in ENV_CMDS:
        return int(cmd[3]) if len(cmd) > 3 and isinstance(cmd[3], (int, float)) else None
    for p in cmd[1:]:
        if isinstance(p, (int, float)) and not isinstance(p, bool) and p > 0:
            return int(p)
    return None


def classify(kinds: list[dict], cmd_name: str) -> str:
    if cmd_name in ENV_CMDS:
        return "环境"
    if cmd_name == "CreateFlood":
        return "场地"
    if not kinds:
        return "领域"
    good = 0
    bad = 0
    for k in kinds:
        v = k.get("value")
        name = k["kind"]
        if name in ("BuffRejection", "HealRejection", "ComboRestriction", "Silence",
                    "Frozen", "Stunify", "Slip"):
            bad += 1
        elif name in ("ComboBoost", "SkillGaugeCharging", "Regeneration", "Piercing",
                      "Speedup", "Flying", "FeverPoint"):
            good += 1
        elif isinstance(v, (int, float)):
            # 伤害/攻击系:正=增益(给在场者),负=减益
            (good, bad) = (good + 1, bad) if v > 0 else (good, bad + 1)
    if good and not bad:
        return "加成"
    if bad and not good:
        return "诅咒"
    return "领域"


def _secs(frames) -> str:
    if not isinstance(frames, (int, float)):
        return ""
    s = frames / 60
    return f"{s:.0f}秒" if s >= 1 else f"{frames}帧"


def label_of(kinds: list[dict], cmd, src: str) -> tuple[str, str]:
    """(标签, 说明)。cmd = 主场命令整条(要读参数),不只是命令名。"""
    cmd_name = cmd[0] if isinstance(cmd, list) else cmd
    params = cmd[1:] if isinstance(cmd, list) else []
    if cmd_name == "CreateFlood":
        return "深渊之水", "全场淹水"
    # 环境场:把**强度/时长/锚点**编进说明——27 个刮风、46 个重力如果 note 全一样,
    # 计划表和图鉴里就分不出抽到的是哪一个(强度跨 20 倍、时长跨 10 倍,体感差很多)
    if cmd_name == "CreateWindAttack":
        d, power, dur = (list(params) + [None, None, None])[:3]
        tier = ("微风" if isinstance(power, (int, float)) and power <= 0.1 else
                "轻风" if isinstance(power, (int, float)) and power <= 0.3 else
                "强风" if isinstance(power, (int, float)) and power <= 0.6 else "狂风")
        return "狂风领域", f"{tier}{power}·{_secs(dur)}·方向{d}"
    if cmd_name == "CreateGravitationalField":
        power = params[1] if len(params) > 1 else None
        dur = params[2] if len(params) > 2 else None
        anchors = [p[0] for p in params if isinstance(p, list) and p
                   and isinstance(p[0], str)]
        A_CN = {"Center": "中心", "Top": "上方", "Left": "左侧", "Right": "右侧"}
        pos = "/".join(dict.fromkeys(A_CN.get(a, a) for a in anchors)) or "?"
        return "重力领域", f"引力{power}·{_secs(dur)}·{pos}"
    # 0 = 跟随本场/施法者属性(精灵兽系「炎兽/雷电领域」就是这种),不是"未知"。
    # ⚠ 254 是**未识别的哨兵值**(全库只 3 处,正常元素只有 0-7)——不猜它是"全属性"
    #   还是"无",按原值标出来,别用 ? 冒充。
    E_CN = {0: "本属性", 1: "火", 2: "水", 3: "雷", 4: "风", 5: "光", 6: "暗", 7: "无",
            254: "哨兵254"}
    parts = []
    for k in kinds[:3]:
        cn = KIND_CN.get(k["kind"], k["kind"])
        if "element" in k:
            cn = f"{E_CN.get(k['element'], '?')}耐性"
        v = k.get("value")
        if isinstance(v, (int, float)) and v and abs(v) < 50:
            parts.append(f"{cn}{'+' if v > 0 else ''}{round(v * 100) if abs(v) <= 3 else int(v)}{'%' if abs(v) <= 3 else ''}")
        else:
            parts.append(cn)
    note = "/".join(parts) if parts else "领域"
    lead = KIND_CN.get(kinds[0]["kind"], "领域") if kinds else "领域"
    return f"{lead}领域", note


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--verify", action="store_true", help="全量 build→parse 往返自校验")
    ap.add_argument("--forge-clean", action="store_true",
                    help="净化 26 个带攻击判定的混合程序并入库")
    args = ap.parse_args()

    catalog, dirty_n, fail, forged_n, rt_bad = [], 0, 0, 0, 0
    seen_sig = set()
    for line in PATHLIST.read_text(encoding="utf-8").splitlines():
        lp = line.strip()
        if ".action.dsl" not in lp:
            continue
        try:
            raw = q.store_path(lp).read_bytes()
        except Exception:
            continue
        data = zlib.decompress(raw, -15)
        if not any(c.encode() in data for c in SCAN_CMDS):
            continue
        try:
            tree = parse_dsl(raw)
        except Exception:
            fail += 1
            continue
        if args.verify:
            try:
                if parse_dsl(build_dsl(tree)) != tree:
                    rt_bad += 1
                    print("  [RT!] 往返不等价:", lp.split("/")[-1])
            except Exception as e:
                rt_bad += 1
                print("  [RT!]", lp.split("/")[-1], "->", e)
        cmds: list = []
        walk_cmds(tree, cmds)
        f_cmds = [c for c in cmds if c[0] in SCAN_CMDS]
        if not f_cmds:
            continue
        program = lp.replace(".action.dsl.amf3.deflate", "")
        base = program.split("/")[-1]
        src = base.split("$")[0].replace("boss_", "")
        is_dirty = any(c[0] in DIRTY_CMDS for c in cmds)
        forged = None
        if is_dirty:
            dirty_n += 1
            if not args.forge_clean:
                continue
            try:
                forged = forge(program, clean=True)
                forged_n += 1
            except Exception as e:
                print("  [净化失败]", base, "->", e)
                continue
        # 效果 = 全部场命令 kind 并集;含条件分支标「复合」
        kinds = []
        for c in f_cmds:
            for k in kinds_of(c):
                if k not in kinds:
                    kinds.append(k)
        composite = len(f_cmds) > 1 or b"Conditionals" in data
        main_cmd = f_cmds[0]
        cat = classify(kinds, main_cmd[0])
        lab, note = label_of(kinds, main_cmd, src)
        if forged:
            note += "·净化版"
        if composite:
            note += "·复合"
        dur = duration_of(main_cmd)
        if main_cmd[0] in ENV_CMDS:
            # 环境场没有 kind 数组,签名改用**数值参数本身**(方向/强度/时长/半径),
            # 否则所有刮风程序会压成同一个签名、目录里只剩 1 条
            sig = (main_cmd[0], tuple(p for p in main_cmd[1:]
                                      if isinstance(p, (int, float))
                                      and not isinstance(p, bool)))
        else:
            sig = (main_cmd[0],
                   tuple((k["kind"], k.get("element"), k["value"]) for k in kinds))
        first = sig not in seen_sig
        seen_sig.add(sig)
        catalog.append({
            "label": lab, "program": forged or program, "note": note, "cat": cat,
            "cmd": main_cmd[0], "src": src, "orig": program if forged else None,
            "kinds": kinds, "duration_s": round(dur / 60, 1) if dur and dur > 60 else None,
            "composite": composite, "dup": not first,
        })
    print(f"净场程序 {len(catalog)} 个(签名去重后 {len(seen_sig)});"
          f"混合程序 {dirty_n}(已净化入库 {forged_n});解析失败 {fail}"
          + (f";往返异常 {rt_bad}" if args.verify else ""))
    from collections import Counter
    print("分类:", dict(Counter(c['cat'] for c in catalog)))
    if args.write:
        OUT_JSON.write_text(json.dumps(catalog, ensure_ascii=False, indent=1),
                            encoding="utf-8")
        print(f"[OK] 已写 {OUT_JSON.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
