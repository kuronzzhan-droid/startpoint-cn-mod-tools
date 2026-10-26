"""修复旧Seris分支把技能语音池缩成单条的问题；仅输出新SWF，不安装。"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

pass  # Imports resolve from this checkout/package, not external source copies.
import asm
import bodies
from swfabc import SwfAbc

METHOD = "SquadManagerImpl/invokeActionSkill"
BEFORE = "b0b50cb6cc8b125fdbb7493523a35f3ece3b3d5f898930bbff6a2f2775385e7e"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def replace_selection(instructions, abc):
    """保持指令数量及所有外部跳转目标不变；Seris自己使用两组原生语音池。"""
    ins = copy.deepcopy(instructions)
    expected = ["getlocal_3", "getproperty", "getlocal", "convert_i",
                "getproperty", "coerce", "newarray", "jump"]
    if [x.name for x in ins[113:121]] != expected or ins[120].target != 128:
        raise asm.AsmError("Seris single-voice branch differs")
    if (abc.s(ins[104].args[0]) != "ModDualForm" or
            abc.s(ins[111].args[0]) != "seris_dragon_king" or
            abc.mn_name(ins[114].args[0]) != "skillVoicePaths" or
            abc.mn_name(ins[124].args[0]) != "switchedSkillVoicePaths"):
        raise asm.AsmError("Seris identity or native voice pools differ")
    normal, switched = ins[114].args[0], ins[124].args[0]
    ins[113:121] = [
        asm.Instruction(asm.MNEMONICS["getlocal"], [6]),
        asm.Instruction(asm.MNEMONICS["iffalse"], target=118),
        asm.Instruction(asm.MNEMONICS["getlocal_3"]),
        asm.Instruction(asm.MNEMONICS["getproperty"], [switched]),
        asm.Instruction(asm.MNEMONICS["jump"], target=128),
        asm.Instruction(asm.MNEMONICS["getlocal_3"]),
        asm.Instruction(asm.MNEMONICS["getproperty"], [normal]),
        asm.Instruction(asm.MNEMONICS["jump"], target=128),
    ]
    return ins


def apply(source: Path, output: Path):
    if output.exists() or source.resolve() == output.resolve():
        raise ValueError("output must be a new path; preserve the original SWF")
    swf = SwfAbc(source)
    abc = swf.abc
    old = [b[:] for b in abc.bodies]
    idx = bodies.resolve(abc, METHOD)
    body = abc.bodies[idx]
    if sha(body[5]) != BEFORE or body[6]:
        raise asm.AsmError("unreviewed method baseline or exception table")
    ins = replace_selection(asm.decode(body[5]), abc)
    code, _ = asm.encode(ins)
    analysis = [asm.Instruction(0x02) if x.op in (0xEF, 0xF0, 0xF1) else x for x in ins]
    metrics = asm.simulate(analysis, body[3], abc.multinames)
    if metrics[0] > body[1] or metrics[1] > body[4]:
        raise asm.AsmError("new selection exceeds existing stack/scope limits")
    body[5] = code
    changed = [i for i, (before, after) in enumerate(zip(old, abc.bodies)) if before != after]
    if changed != [idx]:
        raise asm.AsmError("unexpected method changes")
    output.parent.mkdir(parents=True, exist_ok=True)
    swf.save(output)
    back = SwfAbc(output).abc
    # 独立回读：除了指定方法代码，其余主ABC字段必须逐值相等。
    back.bodies[idx][5] = old[idx][5]
    abc.bodies[idx][5] = old[idx][5]
    if back.serialize() != abc.serialize():
        raise asm.AsmError("serialized SWF changed unrelated ABC content")
    report = dict(status="static_verified_not_installed", source=str(source), output=str(output),
                  source_sha256=sha(source.read_bytes()), output_sha256=sha(output.read_bytes()),
                  method=METHOD, method_index=idx, before_sha256=BEFORE, after_sha256=sha(code),
                  changed_methods=1, unchanged_methods=len(old) - 1, metrics=metrics,
                  description="仅Seris分支按当前形态选取完整普通/真龙技能语音数组",
                  device_or_store_writes=False, runtime_verified=False)
    output.with_suffix(".json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    print(json.dumps(apply(a.source, a.output), ensure_ascii=False, indent=2))
