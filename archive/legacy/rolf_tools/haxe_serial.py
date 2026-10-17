# -*- coding: utf-8 -*-
"""Haxe 序列化往返器(WF 离线存档 save_haxe 用)。
先做 parse→serialize 字节级恒等自检,通过后才允许改写。
支持 token: o(对象) q(IntMap) b(StringMap) a(数组) l(列表) y(字符串) R(串缓存)
r(对象缓存) i(int) d(double) z(0) n(null) t/f(bool) k(NaN) m/p(±Inf)
s(bytes) v(date) w(enum by name) j(enum by index) x(exception)
"""
from __future__ import annotations

from wf.paths import root_path
import sys, urllib.parse


class HaxeObj(dict):
    """有序对象(o...g),保留键序。"""


class IntMap(dict):
    pass


class StrMap(dict):
    pass


class HList(list):
    pass


class Enum:
    __slots__ = ("ename", "ctor", "args")
    def __init__(self, ename, ctor, args):
        self.ename, self.ctor, self.args = ename, ctor, args
    def __repr__(self):
        return f"Enum({self.ename}.{self.ctor}{self.args})"


class Bytes:
    __slots__ = ("b64",)
    def __init__(self, b64):
        self.b64 = b64


class DateV:
    __slots__ = ("s",)
    def __init__(self, s):
        self.s = s


class Hole:
    """数组空洞标记(u<n>)"""
    __slots__ = ("n",)
    def __init__(self, n):
        self.n = n


class Parser:
    def __init__(self, s: str):
        self.s = s
        self.i = 0
        self.scache: list[str] = []
        self.ocache: list = []

    def _int(self):
        s, i = self.s, self.i
        j = i
        if j < len(s) and s[j] in "+-":
            j += 1
        while j < len(s) and s[j].isdigit():
            j += 1
        v = int(s[i:j])
        self.i = j
        return v

    def _float(self):
        s, i = self.s, self.i
        j = i
        while j < len(s) and (s[j].isdigit() or s[j] in "+-.eE"):
            j += 1
        v = float(s[i:j])
        self.i = j
        return v

    def string(self):
        c = self.s[self.i]
        if c == "y":
            self.i += 1
            ln = self._int()
            assert self.s[self.i] == ":", f"y 缺冒号 @{self.i}"
            self.i += 1
            raw = self.s[self.i:self.i + ln]
            self.i += ln
            v = urllib.parse.unquote(raw)
            self.scache.append(v)
            return v
        if c == "R":
            self.i += 1
            return self.scache[self._int()]
        raise ValueError(f"期望字符串 token,得到 {c!r} @{self.i}")

    def value(self):
        s = self.s
        c = s[self.i]
        if c == "n":
            self.i += 1; return None
        if c == "t":
            self.i += 1; return True
        if c == "f":
            self.i += 1; return False
        if c == "z":
            self.i += 1; return 0
        if c == "i":
            self.i += 1; return self._int()
        if c == "d":
            self.i += 1; return self._float()
        if c == "k":
            self.i += 1; return float("nan")
        if c == "m":
            self.i += 1; return float("-inf")
        if c == "p":
            self.i += 1; return float("inf")
        if c in "yR":
            return self.string()
        if c == "r":
            self.i += 1; return self.ocache[self._int()]
        if c == "o":
            self.i += 1
            ob = HaxeObj(); self.ocache.append(ob)
            while s[self.i] != "g":
                k = self.string()
                ob[k] = self.value()
            self.i += 1
            return ob
        if c == "q":
            self.i += 1
            m = IntMap(); self.ocache.append(m)
            while s[self.i] != "h":
                assert s[self.i] == ":", f"q 段缺冒号 @{self.i}"
                self.i += 1
                k = self._int()
                m[k] = self.value()
            self.i += 1
            return m
        if c == "b":
            self.i += 1
            m = StrMap(); self.ocache.append(m)
            while s[self.i] != "h":
                k = self.string()
                m[k] = self.value()
            self.i += 1
            return m
        if c in "al":
            self.i += 1
            arr = [] if c == "a" else HList()
            self.ocache.append(arr)
            while s[self.i] != "h":
                if s[self.i] == "u":
                    self.i += 1
                    arr.append(Hole(self._int()))
                else:
                    arr.append(self.value())
            self.i += 1
            return arr
        if c == "s":
            self.i += 1
            ln = self._int()
            assert s[self.i] == ":"
            self.i += 1
            b = Bytes(s[self.i:self.i + ln]); self.i += ln
            self.ocache.append(b)
            return b
        if c == "v":
            self.i += 1
            d = DateV(s[self.i:self.i + 19]); self.i += 19
            self.ocache.append(d)
            return d
        if c == "w":
            self.i += 1
            en = self.string(); ct = self.string()
            assert s[self.i] == ":", f"w 缺冒号 @{self.i}"
            self.i += 1
            n = self._int()
            e = Enum(en, ct, [self.value() for _ in range(n)])
            self.ocache.append(e)
            return e
        if c == "j":
            self.i += 1
            en = self.string()
            assert s[self.i] == ":"
            self.i += 1
            idx = self._int()
            assert s[self.i] == ":"
            self.i += 1
            n = self._int()
            e = Enum(en, idx, [self.value() for _ in range(n)])
            self.ocache.append(e)
            return e
        raise ValueError(f"未知 token {c!r} @{self.i}: {s[max(0,self.i-30):self.i+30]!r}")


class Serializer:
    def __init__(self):
        self.out: list[str] = []
        self.scache: dict[str, int] = {}
        self.ocache: list = []

    def _oid(self, v):
        for i, x in enumerate(self.ocache):
            if x is v:
                return i
        return None

    def string(self, v: str):
        if v in self.scache:
            self.out.append(f"R{self.scache[v]}")
            return
        enc = urllib.parse.quote(v, safe="")
        self.out.append(f"y{len(enc)}:{enc}")
        self.scache[v] = len(self.scache)

    def value(self, v):
        if v is None:
            self.out.append("n"); return
        if v is True:
            self.out.append("t"); return
        if v is False:
            self.out.append("f"); return
        if isinstance(v, str):
            self.string(v); return
        if isinstance(v, int) and not isinstance(v, bool):
            self.out.append("z" if v == 0 else f"i{v}"); return
        if isinstance(v, float):
            if v != v:
                self.out.append("k"); return
            if v == float("inf"):
                self.out.append("p"); return
            if v == float("-inf"):
                self.out.append("m"); return
            # Haxe Std.string(Float):整数值不带 .0
            if v == int(v) and abs(v) < 1e21:
                self.out.append("d" + str(int(v)))
            else:
                self.out.append("d" + repr(v))
            return
        oid = self._oid(v)
        if oid is not None:
            self.out.append(f"r{oid}"); return
        if isinstance(v, HaxeObj):
            self.ocache.append(v); self.out.append("o")
            for k, val in v.items():
                self.string(k); self.value(val)
            self.out.append("g"); return
        if isinstance(v, IntMap):
            self.ocache.append(v); self.out.append("q")
            for k, val in v.items():
                self.out.append(f":{k}"); self.value(val)
            self.out.append("h"); return
        if isinstance(v, StrMap):
            self.ocache.append(v); self.out.append("b")
            for k, val in v.items():
                self.string(k); self.value(val)
            self.out.append("h"); return
        if isinstance(v, (list, HList)):
            self.ocache.append(v)
            self.out.append("l" if isinstance(v, HList) else "a")
            for x in v:
                if isinstance(x, Hole):
                    self.out.append(f"u{x.n}")
                else:
                    self.value(x)
            self.out.append("h"); return
        if isinstance(v, Bytes):
            self.ocache.append(v)
            self.out.append(f"s{len(v.b64)}:{v.b64}"); return
        if isinstance(v, DateV):
            self.ocache.append(v)
            self.out.append("v" + v.s); return
        if isinstance(v, Enum):
            self.ocache.append(v)
            if isinstance(v.ctor, int):
                self.out.append("j"); self.string(v.ename)
                self.out.append(f":{v.ctor}:{len(v.args)}")
            else:
                self.out.append("w"); self.string(v.ename); self.string(v.ctor)
                self.out.append(f":{len(v.args)}")
            for a in v.args:
                self.value(a)
            return
        raise ValueError(f"不支持的类型 {type(v).__name__}")


def loads(s: str):
    p = Parser(s)
    v = p.value()
    if p.i != len(s):
        raise ValueError(f"尾部残留 {len(s)-p.i} 字符 @{p.i}")
    return v


def dumps(v) -> str:
    s = Serializer()
    s.value(v)
    return "".join(s.out)


if __name__ == "__main__":
    from pathlib import Path
    src = Path(sys.argv[1] if len(sys.argv) > 1
               else ('${WF_ROOT}\\MuMuPlayer\\vms\\MuMuPlayer-15.0-0\\private_shared\\sv3.txt'.replace("${WF_ROOT}", str(root_path()))))
    txt = src.read_text(encoding="utf-8")
    v = loads(txt)
    out = dumps(v)
    same = out == txt
    print(f"往返自检: 原 {len(txt)} → 重出 {len(out)} | 字节恒等: {same}")
    if not same:
        for i, (a, b) in enumerate(zip(txt, out)):
            if a != b:
                print(f"  首差异 @{i}: 原 {txt[max(0,i-60):i+60]!r}")
                print(f"            新 {out[max(0,i-60):i+60]!r}")
                break
        else:
            print(f"  前缀相同,长度差 {len(out)-len(txt)}")
