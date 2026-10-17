#!/usr/bin/env python3
"""读写 SWF 里那一个 `boot_ffc6` DoABC2 标签,并提供常量池的「只增不改」编辑器。

约束(与 client-patch 其余模块一致):
  * 只碰 `boot_ffc6` 那一个标签,其余标签逐字节原样搬运;
  * 常量池只允许**追加**,已有条目一律复用 —— 任何一条已存在的索引被挪动
    都会让全 ABC 的引用错位,所以这里根本不提供改写接口;
  * ABC 解析器往返必须逐字节相等,不相等直接拒绝干活。
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

from .asm import AsmError, load_abc_module

abcfmt = load_abc_module("abcfmt")
swftags = load_abc_module("swftags")

MAIN_ABC_NAME = b"boot_ffc6"


class SwfAbc:
    """一份 SWF + 它的主 ABC。`save()` 只重写主 ABC 标签。"""

    def __init__(self, path: Path):
        path = Path(path)
        self.path = path
        signature, version, _declared, body = swftags.load_swf(str(path))
        self.signature = signature
        self.version = version
        self.body = body
        found = []
        for code, offset, header, length in swftags.iter_tags(body):
            if code != 82:
                continue
            content = body[offset + header:offset + header + length]
            nul = content.index(b"\0", 4)
            if content[4:nul] == MAIN_ABC_NAME:
                found.append((offset, header + length, content[:nul + 1], content[nul + 1:]))
        if len(found) != 1:
            raise AsmError("expected exactly one %r DoABC2 tag, found %d"
                           % (MAIN_ABC_NAME.decode(), len(found)))
        self._offset, self._length, self._prefix, self._raw = found[0]
        self.abc = abcfmt.ABC(self._raw)
        if self.abc.serialize() != self._raw:
            raise AsmError("ABC parser roundtrip is not byte-exact")

    def serialize(self) -> bytes:
        raw = self.abc.serialize()
        content = self._prefix + raw
        tag = struct.pack("<HI", (82 << 6) | 63, len(content)) + content
        body = self.body[:self._offset] + tag + self.body[self._offset + self._length:]
        payload = zlib.compress(body) if self.signature == b"CWS" else body
        return self.signature + bytes([self.version]) \
            + struct.pack("<I", len(body) + 8) + payload

    def save(self, path: Path) -> None:
        path = Path(path)
        if path.resolve() == self.path.resolve():
            raise AsmError("the input SWF must stay immutable")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.serialize())


class PoolEditor:
    """常量池「只增不改」编辑器。复用已有条目,新条目一律追加在末尾。"""

    def __init__(self, abc):
        self.abc = abc
        self._strings = {}
        for index, value in enumerate(abc.strings):
            self._strings.setdefault(value, index)
        self._base_string_count = len(abc.strings)
        self._base_multiname_count = len(abc.multinames)
        self._base_int_count = len(abc.ints)
        self.added_strings = []
        self.added_multinames = []
        self.added_ints = []

    def string(self, text) -> int:
        raw = text.encode("utf-8") if isinstance(text, str) else text
        index = self._strings.get(raw)
        if index is not None:
            return index
        index = len(self.abc.strings)
        self.abc.strings.append(raw)
        self._strings[raw] = index
        self.added_strings.append(raw)
        return index

    def integer(self, value: int) -> int:
        """int 池里拿一个常量的下标;没有就追加(只增不改,和字符串池同一条纪律)。

        `pushshort` 的操作数宽度在各家 AVM2 实现上有歧义(u30 还是 s16),
        所以超出 pushbyte 范围的整数一律走 `pushint` + int 池,不赌。
        """
        for index in range(1, len(self.abc.ints)):
            if self.abc.ints[index] == value:
                return index
        index = len(self.abc.ints)
        self.abc.ints.append(value)
        self.added_ints.append(value)
        return index

    def public_qname(self, name: str, namespace_of: int) -> int:
        """在与 `namespace_of`(一个已有 QName 的索引)相同的命名空间里造一个 QName。"""
        kind, existing_namespace, _name = self.abc.multinames[namespace_of]
        if kind != abcfmt.MN_QName:
            raise AsmError("namespace donor %d is not a QName" % namespace_of)
        string_index = self.string(name)
        for index in range(1, len(self.abc.multinames)):
            entry = self.abc.multinames[index]
            if entry[0] == abcfmt.MN_QName and entry[1] == existing_namespace \
                    and entry[2] == string_index:
                return index
        index = len(self.abc.multinames)
        self.abc.multinames.append((abcfmt.MN_QName, existing_namespace, string_index))
        self.added_multinames.append(name)
        return index

    def report(self) -> dict:
        return {
            "added_strings": [x.decode("utf-8", "replace") for x in self.added_strings],
            "added_multinames": list(self.added_multinames),
            "added_ints": list(self.added_ints),
            "base_string_count": self._base_string_count,
            "base_multiname_count": self._base_multiname_count,
            "base_int_count": self._base_int_count,
        }
