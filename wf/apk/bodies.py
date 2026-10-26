#!/usr/bin/env python3
"""按「类名/方法名」在主 ABC 里唯一定位方法体下标。

为什么需要它:**体下标不是稳定标识**。V9 用 FFDec 整类回编替换了三个类
(`ActionEvaluator` / `MemberImpl` / `AbilityDamageShot`),FFDec 把这三个类的
方法体从原位摘走再追加到表尾 —— 从体 51410 起,39,849 个体的下标整体漂移。
V13 改从 V8 基线重建链时,V12 两个模块里锁死的 V11 下标因此全部作废,
但**方法名**没变,基线 code 的 sha256 也逐字节没变(已实测)。

所以定位一律按名字,再用各模块锁定的 code sha256 复核 —— 名字选错的话
sha256 会当场拦下,两道门是互相独立的。

标签写法与两个 V12 模块 `TARGETS` 的键完全一致:

  * ``"BallImpl/update"``            —— 实例方法
  * ``"AbilityValues$/parseAt47"``   —— 类(静态)方法,类名后带 ``$``
  * ``"Foo/<ctor>"``                 —— 实例构造器(``iinit``)
  * ``"Foo$/<cinit>"``               —— 类初始化(``cinit``)
  * ``"Foo/bar|get"`` / ``"Foo/bar|set"`` —— getter / setter

类名只取 ``::`` 之后的短名(与模块里的写法一致);短名在全 ABC 内不唯一时,
`resolve` 拒绝猜,直接报错并列出候选。
"""
from __future__ import annotations

from .asm import AsmError

_CACHE = {}


def label_map(abc) -> dict:
    """{方法体下标: 标签}。匿名 / 函数闭包体不在表里。"""
    key = id(abc)
    cached = _CACHE.get(key)
    if cached is not None and cached[0] is abc:
        return cached[1]
    body_of = {}
    for index, body in enumerate(abc.bodies):
        body_of[body[0]] = index
    labels = {}

    def put(method_index, class_name, method_name, static):
        index = body_of.get(method_index)
        if index is None:                      # 接口 / native,没有方法体
            return
        labels[index] = "%s%s/%s" % (class_name, "$" if static else "", method_name)

    for position, instance in enumerate(abc.instances):
        class_name = abc.mn_name(instance[0]).split("::")[-1]
        put(instance[5], class_name, "<ctor>", False)
        for trait in instance[6]:
            if trait.data[0] == "method":
                put(trait.data[2], class_name, _trait_name(abc, trait), False)
        klass = abc.classes[position]
        put(klass[0], class_name, "<cinit>", True)
        for trait in klass[1]:
            if trait.data[0] == "method":
                put(trait.data[2], class_name, _trait_name(abc, trait), True)
    _CACHE[key] = (abc, labels)
    return labels


def _trait_name(abc, trait) -> str:
    name = abc.mn_name(trait.name).split("::")[-1]
    if trait.kind == 2:
        return name + "|get"
    if trait.kind == 3:
        return name + "|set"
    return name


def resolve(abc, label: str) -> int:
    """标签 -> 唯一的方法体下标。找不到或不唯一都当场报错,绝不猜。"""
    matches = [index for index, value in label_map(abc).items() if value == label]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise AsmError("no method body is named %r in this ABC" % label)
    raise AsmError("%r is ambiguous: %d method bodies carry that name (%s)"
                   % (label, len(matches), ", ".join(str(x) for x in sorted(matches))))


def resolve_all(abc, labels) -> dict:
    """{标签: 体下标}。任何一个标签解析失败都整体报错。"""
    return {label: resolve(abc, label) for label in labels}
