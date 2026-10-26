#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
技能 ActionDsl 数值编辑器。

文件:`<program_path>.action.dsl.amf3.deflate`(program_path 含 $,原样进 sha1),
raw-deflate(wbits=-15)压缩的 AMF3 序列化命令树(ActionDsl→Block→Command→...)。

编辑策略(2026-07-06 逆向落地):
  * 只改数值,不动结构 → 不需要完整 AMF3 写入器。
  * AMF3 U29 整数允许非规范前导 0x80 字节(读取算法 value=(value<<7)|(b&0x7f)),
    因此可以把新值**补位到与原编码等长**原地覆写;double 定长 8 字节直接覆写。
  * 新值最短编码超过原有字节数 → 拒绝(提示换模板/用整技能替换)。
解析器输出每个数值叶子的 (offset, len, value, 语境路径),语境 = 最近的字符串标签
(命令名/字段名),供人看懂"这是哪个效果的哪个数"。
"""
from __future__ import annotations

import zlib
from pathlib import Path

import wf_mod_tool as core

# 常见 DSL 命令/字段的中文标注(逐步补充;未知的显示原名)
DSL_CN = {
    "CreateHitArea": "攻击判定", "Rectangle": "矩形范围", "Circle": "圆形范围",
    "StopBall": "停球", "Stop": "停止", "CreateReferencePoint": "参考点",
    "EnemyDamage": "对敌伤害", "Damage": "伤害", "Heal": "治疗",
    "Condition": "状态效果", "GiveCondition": "赋予状态", "min": "最小", "max": "最大",
    "Single": "单段", "Multiple": "多段", "frame": "帧", "Wait": "等待(帧)",
    "MoveBall": "移动球", "Shot": "发射", "SpecialAttack": "特攻",
}


def dsl_logical(program_path: str) -> str:
    return f"{program_path}.action.dsl.amf3.deflate"


def _read_u29(b: bytes, i: int) -> tuple[int, int]:
    """返回 (值, 新偏移)。"""
    v = 0
    for n in range(3):
        c = b[i]
        i += 1
        if c & 0x80:
            v = (v << 7) | (c & 0x7F)
        else:
            return (v << 7) | c, i
    return (v << 8) | b[i], i + 1


def encode_u29_padded(v: int, length: int) -> bytes:
    """把 v 编码成恰好 length 字节的 U29(用非规范前导 0x80 补位)。放不下抛错。"""
    if not (0 <= v < (1 << 29)):
        raise ValueError("数值超出 AMF3 U29 范围(0~536870911)")
    if length == 4:
        if v >= (1 << 29):
            raise ValueError("放不下")
        b3 = v & 0xFF
        rest = v >> 8
        out = [((rest >> 14) & 0x7F) | 0x80, ((rest >> 7) & 0x7F) | 0x80,
               (rest & 0x7F) | 0x80, b3]
        return bytes(out)
    # 1-3 字节:7 位/字节
    if v >= (1 << (7 * length)):
        raise ValueError(f"数值 {v} 需要更多字节(原字段只有 {length} 字节)")
    out = []
    for k in range(length - 1, -1, -1):
        part = (v >> (7 * k)) & 0x7F
        out.append(part | (0x80 if k else 0))
    return bytes(out)


class _Parser:
    """AMF3 子集解析(带引用表),记录 int/double 叶子的偏移与语境。"""

    def __init__(self, data: bytes):
        self.b = data
        self.i = 0
        self.strings: list[str] = []
        self.traits: list[tuple[str, list[str], bool]] = []
        self.numbers: list[dict] = []   # {offset,len,value,type,ctx}
        self.ctx: list[str] = []

    def _label(self) -> str:
        return ".".join(self.ctx[-4:])

    def read_string(self) -> str:
        ref, self.i = _read_u29(self.b, self.i)
        if not (ref & 1):
            return self.strings[ref >> 1]
        ln = ref >> 1
        s = self.b[self.i:self.i + ln].decode("utf-8", errors="replace")
        self.i += ln
        if s:
            self.strings.append(s)
        return s

    def read_value(self):
        m = self.b[self.i]
        self.i += 1
        if m in (0x00, 0x01, 0x02, 0x03):     # undefined/null/false/true
            return {0x00: None, 0x01: None, 0x02: False, 0x03: True}[m]
        if m == 0x04:                          # int
            off = self.i
            v, self.i = _read_u29(self.b, self.i)
            if v & 0x10000000:                 # 29 位符号
                v -= 0x20000000
            self.numbers.append({"offset": off, "len": self.i - off, "value": v,
                                 "type": "int", "ctx": self._label()})
            return v
        if m == 0x05:                          # double
            off = self.i
            import struct
            v = struct.unpack(">d", self.b[self.i:self.i + 8])[0]
            self.i += 8
            self.numbers.append({"offset": off, "len": 8, "value": v,
                                 "type": "double", "ctx": self._label()})
            return v
        if m == 0x06:                          # string
            s = self.read_string()
            return s
        if m == 0x09:                          # array
            ref, self.i = _read_u29(self.b, self.i)
            if not (ref & 1):
                return f"<arrRef {ref >> 1}>"
            count = ref >> 1
            out = {}
            while True:                        # 关联部分
                k = self.read_string()
                if k == "":
                    break
                self.ctx.append(k)
                out[k] = self.read_value()
                self.ctx.pop()
            # DSL 惯例:['命令名'/标签串, 参数...] → 首元素若为字符串,作为其余元素的语境
            dense = []
            pushed = False
            for idx in range(count):
                v = self.read_value()
                if idx == 0 and isinstance(v, str) and v:
                    self.ctx.append(v)
                    pushed = True
                dense.append(v)
            if pushed:
                self.ctx.pop()
            return {"assoc": out, "dense": dense} if out else dense
        if m == 0x0A:                          # object
            ref, self.i = _read_u29(self.b, self.i)
            if not (ref & 1):
                return f"<objRef {ref >> 1}>"
            if not (ref & 2):                  # traits 引用
                cls, sealed, dyn = self.traits[ref >> 2]
            else:
                if ref & 4:
                    raise ValueError("不支持 externalizable 对象")
                dyn = bool(ref & 8)
                n_sealed = ref >> 4
                cls = self.read_string()
                sealed = [self.read_string() for _ in range(n_sealed)]
                self.traits.append((cls, sealed, dyn))
            obj = {}
            if cls:
                self.ctx.append(cls)
            for name in sealed:
                self.ctx.append(name)
                obj[name] = self.read_value()
                self.ctx.pop()
            if dyn:
                while True:
                    k = self.read_string()
                    if k == "":
                        break
                    self.ctx.append(k)
                    obj[k] = self.read_value()
                    self.ctx.pop()
            if cls:
                self.ctx.pop()
            return obj
        raise ValueError(f"未支持的 AMF3 标记 0x{m:02x} @ {self.i - 1}")


def _walk_label_arrays(v, parser):
    """DSL 数组首元素常是命令名字符串:回填语境(解析时无法前瞻,后处理不做,保留 ctx 近似)。"""
    return v


def parse_dsl(data: bytes) -> dict:
    """解压后的 AMF3 字节 → {tree, numbers[]}。"""
    p = _Parser(data)
    tree = p.read_value()
    return {"tree": tree, "numbers": p.numbers}


# ---------------------------------------------------------------- AMF3 编码器(JSON 整树编辑用)
# 2026-07-06 全库普查(1035 个技能 DSL):标记只有 null/false/true/int/double/string/
# dense array/匿名动态 object,零引用、零 assoc、traits 唯一("",dyn)。
# → 树表示可无损映射到 JSON:null/bool/int/float/str/list/dict,编码器只需覆盖该子集。
# int/double 区分靠 Python int/float(JSON 文本 3 与 3.0);GUI 全程传 JSON 文本不经 JS 解析。

def encode_amf3(tree) -> bytes:
    """parse_dsl 的树 → AMF3 字节(canonical U29;字符串表去重与官方序列化器一致)。"""
    import struct
    out = bytearray()
    strings: dict[str, int] = {}
    traits_written = [False]

    def w_u29(v: int) -> None:
        if not (0 <= v < (1 << 29)):
            raise ValueError(f"U29 超范围: {v}")
        if v < 0x80:
            out.append(v)
        elif v < 0x4000:
            out.extend([(v >> 7) | 0x80, v & 0x7F])
        elif v < 0x200000:
            out.extend([(v >> 14) | 0x80, ((v >> 7) & 0x7F) | 0x80, v & 0x7F])
        else:
            out.extend([((v >> 22) & 0x7F) | 0x80, ((v >> 15) & 0x7F) | 0x80,
                        ((v >> 8) & 0x7F) | 0x80, v & 0xFF])

    def w_str(s: str) -> None:
        if s == "":
            w_u29(1)
            return
        if s in strings:
            w_u29(strings[s] << 1)
            return
        b = s.encode("utf-8")
        w_u29((len(b) << 1) | 1)
        out.extend(b)
        strings[s] = len(strings)

    def w(v) -> None:
        if v is None:
            out.append(0x01)
        elif v is True:
            out.append(0x03)
        elif v is False:
            out.append(0x02)
        elif isinstance(v, int):
            if -0x10000000 <= v <= 0x0FFFFFFF:
                out.append(0x04)
                w_u29(v & 0x1FFFFFFF)
            else:  # 超 29 位整数按 AMF3 惯例落 double
                out.append(0x05)
                out.extend(struct.pack(">d", float(v)))
        elif isinstance(v, float):
            out.append(0x05)
            out.extend(struct.pack(">d", v))
        elif isinstance(v, str):
            out.append(0x06)
            w_str(v)
        elif isinstance(v, list):
            out.append(0x09)
            w_u29((len(v) << 1) | 1)
            w_u29(1)  # 空关联部分终止符(空字符串)
            for x in v:
                w(x)
        elif isinstance(v, dict):
            out.append(0x0A)
            if traits_written[0]:
                w_u29(0x01)  # traits 引用 idx0(全库对象 traits 唯一)
            else:
                w_u29(0x0B)  # inline traits: dynamic, 0 sealed
                w_str("")
                traits_written[0] = True
            for k, val in v.items():
                if not isinstance(k, str) or k == "":
                    raise ValueError(f"对象键必须是非空字符串: {k!r}")
                w_str(k)
                w(val)
            w_u29(1)  # 动态部分终止符
        else:
            raise ValueError(f"不支持的节点类型: {type(v).__name__}(只允许 null/bool/int/float/str/list/dict)")

    w(tree)
    return bytes(out)


def dsl_to_json_text(data: bytes) -> str:
    """AMF3 字节 → 可编辑 JSON 文本(缩进 1;int/double 以 3 / 3.0 区分,勿改类型)。"""
    import json as _json
    return _json.dumps(parse_dsl(data)["tree"], ensure_ascii=False, indent=1)


def json_text_to_dsl(text: str) -> bytes:
    """编辑后的 JSON 文本 → AMF3 字节。编码后自校验:重新解析必须与输入树等价。"""
    import json as _json
    tree = _json.loads(text)
    data = encode_amf3(tree)
    if parse_dsl(data)["tree"] != tree:
        raise RuntimeError("编码自校验失败(encode→parse 不等价),已放弃")
    return data


def roundtrip_ok(data: bytes) -> tuple[bool, bool]:
    """(字节级一致, 语义级一致)。字节不一致但语义一致 = 原文件带非规范编码(如历史补丁)。"""
    tree = parse_dsl(data)["tree"]
    enc = encode_amf3(tree)
    if enc == data:
        return True, True
    return False, parse_dsl(enc)["tree"] == tree


def load_dsl_file(target_store: Path, program_path: str) -> tuple[Path, bytes]:
    lg = dsl_logical(program_path)
    d = core.sha1_path(lg)
    fp = target_store / d[:2] / d[2:]
    if not fp.exists():
        raise ValueError(f"效果文件不在本地数据包(部分初期角色官方未下发,无法编辑效果参数,"
                         f"可用「整技能替换」): {lg}")
    return fp, zlib.decompress(fp.read_bytes(), -15)


def cn_ctx(ctx: str) -> str:
    return ".".join(DSL_CN.get(t, t) for t in ctx.split(".") if t)


def patch_numbers(data: bytes, edits: list[dict]) -> tuple[bytes, list[str]]:
    """edits: [{offset, len, type, value}] → 原地补丁。返回 (新字节, 日志)。"""
    import struct
    buf = bytearray(data)
    log = []
    for e in sorted(edits, key=lambda x: int(x["offset"])):
        off, ln, typ = int(e["offset"]), int(e["len"]), str(e["type"])
        if typ == "double":
            old = struct.unpack(">d", bytes(buf[off:off + 8]))[0]
            buf[off:off + 8] = struct.pack(">d", float(e["value"]))
            log.append(f"@{off} double {old:g} -> {float(e['value']):g}")
        else:
            v = int(e["value"])
            if v < 0:
                v += 0x20000000  # 29 位补码
            enc = encode_u29_padded(v, ln)
            old, _ = _read_u29(bytes(buf), off)
            buf[off:off + ln] = enc
            log.append(f"@{off} int {old} -> {int(e['value'])}")
    return bytes(buf), log


def save_dsl_file(fp: Path, data: bytes, backup_suffix: str) -> None:
    if fp.exists():
        bak = fp.with_name(fp.name + backup_suffix)
        if not bak.exists():
            import shutil
            shutil.copy2(fp, bak)
    co = zlib.compressobj(9, zlib.DEFLATED, -15)
    fp.write_bytes(co.compress(data) + co.flush())


# ---------------------------------------------------------------- 方向门禁(玩家侧程序)
# 2026-08-28:歼灭者从官方敌方 boss 程序 `enemy_shot_high_epuration` 克隆特效族时
# 连朝向常量一起抄走 —— 真机表现就是「攻击方向都反了」。这一节把方向语义固化成规则。
#
# 方向语义(反编译 弹国服/scripts/pinball/scene/battle/battle/action/ActionHitArea.as):
#   calcDir():1189-1209  AB→0 / CD→target.getDirCD() / EF→getDirEF()+π/2 / GH→bearing+π/2
#   stepDir():610        r = 参数 w + calcDir()
#   矩形 pivotY:338-403  VAlign Top→+h/2 / Center→0 / Bottom→−h/2
#   moveShape():704-717  形状中心 = 锚点 + rot(pivot, r)
# ⇒ 屏幕 y 轴朝下、敌人在上方,所以 **r=0 ⇔ 朝敌方(上);r=π ⇔ 朝玩家自己(下)**。
#   独立佐证:官方 `laser_skill_invoker$laser_front/back/right/left`
#   四个程序的角度正好是 0 / 180 / 90 / 270。
#
# 正向对照(官方 store 全表,长柱 = Rectangle + VAlign Bottom + 高 ≥ 1000):
#   玩家侧 81 条:(AB,0°) 47 / (GH,0°) 21 / (CD,0°) 6 / (AB,180°) 3 / (EF,0°) 2 / (AB,±90°) 各 1
#   敌方侧 2119 条:(AB,180°) 打头,150°~230° 一大扇
#   玩家侧那 5 条例外里,3 条在 `skill_invoker/`(场地役物,不是角色技能),
#   剩下 2 条是同一个 rare2 角色 `towa_namakubi`(官方唯一先例,见单测钉死)。

# 与 TypePackerResource2.as h[24] / ActionDslCommand.as 逐位对照的参数槽
_HA_SLOTS = dict(subject=2, coord=3, dx=4, dy=5, angle=6, shape=9,
                 halign=10, valign=11, fx_block=20, dmg_block=23)
_FX_SLOTS = dict(path=2, subject=3, coord=6, angle=9)
_RP_SLOTS = dict(subject=1, coord=2)
_MV_SLOTS = dict(subject=1, coord=2)

# `getDirCD()` 在这些实现里直接 `throw "INTERNAL ERROR"`:
#   MemberImpl.as:6254 / BallImpl.as:2049 / EnemyImpl.as:3553 / Unit.as:957 / Mate.as:420
# 所以 CoordSysSource=CD 只能挂在判定区/参考点(ActionHitArea.getDirCD 返回 r)或
# Marker/ImaginaryTarget/Coffin 上。−17(自身=Member)与 −18(球=Ball)必 throw。
# 官方 6485 个程序里 CD + 内置负 id 只出现过 −33(敌方自身,另一套实现),0 例 −17/−18。
CD_FORBIDDEN_SUBJECTS = {-17: "自身(MemberImpl.getDirCD 抛 INTERNAL ERROR)",
                         -18: "球(BallImpl.getDirCD 抛 INTERNAL ERROR)"}

# 判为「长柱/光柱」的矩形最小高度:官方玩家侧长柱统计用的同一门槛
BEAM_MIN_HEIGHT = 1000.0


def _tag(v):
    """haxe enum 序列化成 [标签, 参数...];取标签。"""
    if isinstance(v, list) and v and isinstance(v[0], str):
        return v[0]
    return v


def iter_dsl_commands(node, name: str | None = None):
    """深度优先产出 ["Command",[名称, ...]] 的参数数组(name=None 则全给)。"""
    if isinstance(node, list):
        if node and node[0] == "Command" and isinstance(node[1], list):
            if name is None or node[1][0] == name:
                yield node[1]
            for x in node[1][1:]:
                yield from iter_dsl_commands(x, name)
            return
        for x in node:
            yield from iter_dsl_commands(x, name)


def _slv_max(v):
    try:
        return float(v[0]["max"])
    except Exception:
        return None


def _norm_deg(rad) -> float:
    """弧度 → [0,360) 度。"""
    import math
    try:
        return math.degrees(float(rad)) % 360.0
    except Exception:
        return 0.0


def beam_direction_problems(tree) -> list[str]:
    """玩家侧程序里「朝自己那半场发射的长柱判定」= 敌方蓝本没翻转过来。

    只判 coord=AB 的矩形长柱(AB 下 r 就是写在数据里的角度,可静态判定);
    CD/EF/GH 的朝向取决于运行时目标,静态判不了,一律放过。
    """
    probs: list[str] = []
    for c in iter_dsl_commands(tree, "CreateHitArea"):
        if len(c) <= _HA_SLOTS["valign"]:
            continue
        if _tag(c[_HA_SLOTS["coord"]]) != "AB":
            continue
        shape = c[_HA_SLOTS["shape"]]
        if _tag(shape) != "Rectangle" or len(shape) < 3:
            continue
        height = _slv_max(shape[2])
        if height is None or height < BEAM_MIN_HEIGHT:
            continue
        if _tag(c[_HA_SLOTS["valign"]]) != "Bottom":
            continue
        deg = _norm_deg(c[_HA_SLOTS["angle"]])
        if 90.0 <= deg <= 270.0:
            probs.append(
                f"CreateHitArea(bind={c[19] if len(c) > 19 else '?'}) "
                f"AB/VAlign=Bottom/高{height:g} 角度 {deg:g}° 朝向玩家自己那半场"
                "(r=0 才是朝敌方;敌方 boss 蓝本用的就是 180°,克隆时必须翻转)"
            )
    return probs


def coord_sys_source_problems(tree) -> list[str]:
    """CoordSysSource=CD 挂在 getDirCD() 会 throw 的内置 subject 上 = 进战斗必崩。"""
    probs: list[str] = []
    sites = (("CreateHitArea", _HA_SLOTS), ("CreateReferencePoint", _RP_SLOTS),
             ("ShowEffect", _FX_SLOTS), ("MoveHitArea", _MV_SLOTS))
    for name, slots in sites:
        si, ci = slots["subject"], slots["coord"]
        for c in iter_dsl_commands(tree, name):
            if len(c) <= max(si, ci):
                continue
            if _tag(c[ci]) != "CD":
                continue
            subj = c[si]
            if isinstance(subj, int) and subj in CD_FORBIDDEN_SUBJECTS:
                probs.append(f"{name} 的 CoordSysSource=CD 挂在 subject={subj} "
                             f"{CD_FORBIDDEN_SUBJECTS[subj]}")
    return probs


def player_side_dsl_problems(tree) -> list[str]:
    """玩家侧(角色技能 / 强化弹射覆盖)DSL 的方向类硬规则合集。"""
    return beam_direction_problems(tree) + coord_sys_source_problems(tree)


if __name__ == "__main__":
    import io, sys
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    pass  # Imports resolve from this checkout/package, not external source copies.
    store = core.require_active_store()
    fp, data = load_dsl_file(store, "battle/action/skill/action/rare5/fire_dragon$fire_dragon_1")
    r = parse_dsl(data)
    print("数值叶子:", len(r["numbers"]))
    for n in r["numbers"][:20]:
        print(f"  @{n['offset']:>5} {n['type']:6s} {n['value']:>12} ctx={cn_ctx(n['ctx'])}")
    # 往返:解析后不改,原字节不变(解析只读) + 补丁自测:把第一个 int 改成自己
    n0 = next(x for x in r["numbers"] if x["type"] == "int")
    patched, lg = patch_numbers(data, [{**n0}])
    print("等值补丁后一致:", patched == data or "长度不同" , lg)
