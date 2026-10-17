"""Read-only APK/ABC method inspection; outputs remain in the task root."""
from __future__ import annotations

import hashlib
import json
import struct
import sys
import zipfile
import zlib
from pathlib import Path
from wf.paths import path as configured_path, root_path

sys.dont_write_bytecode = True
VENDOR = root_path('codex-serverfix/client-patch/author-merge-20261001')
from wf.apk import asm, bodies
from wf.apk.abcfmt import ABC
from wf.apk.swftags import iter_tags

ROOT = root_path('coop-fix-20261014')
APK = configured_path("downloads", '世界弹射测试服-v28.apk')
LABELS = [
    "BattleDerailleur/getDeferralLevel",
    "BattleDerailleur/addSocketCommand",
    "BattleDerailleur/_addSocketCommand",
    "BattleScenePlayingStateImpl/proceedBattles",
    "OtherBattleState/heartbeat",
    "OtherBattleState/addFutureCoopCommand",
]


def describe(abc, instruction):
    args = list(instruction.args)
    name = instruction.name
    if name in {"getlex", "findproperty", "findpropstrict", "getproperty", "setproperty", "initproperty", "coerce", "astype", "callproperty", "callpropvoid", "constructprop"}:
        args[0] = abc.mn_name(args[0])
    elif name == "pushstring":
        args[0] = abc.s(args[0])
    elif name == "pushint":
        args[0] = abc.ints[args[0]]
    elif name == "pushdouble":
        args[0] = abc.doubles[args[0]]
    suffix = f" -> #{instruction.target}" if instruction.target is not None else ""
    if instruction.cases is not None:
        suffix += f" default #{instruction.default}, cases {instruction.cases}"
    return f"{name} {args}{suffix}"


def main():
    with zipfile.ZipFile(APK) as archive:
        swf = archive.read("assets/worldflipper_android_release.swf")
    data = zlib.decompress(swf[8:]) if swf[:3] == b"CWS" else swf[8:]
    summary = {"apk": str(APK), "apk_sha256": hashlib.sha256(APK.read_bytes()).hexdigest(), "swf_sha256": hashlib.sha256(swf).hexdigest(), "methods": {}}
    for code, offset, header, length in iter_tags(data):
        if code != 82:
            continue
        tag = data[offset + header:offset + header + length]
        nul = tag.index(b"\0", 4)
        raw = tag[nul + 1:]
        abc = ABC(raw)
        labels = bodies.label_map(abc)
        if not any(label in labels.values() for label in LABELS):
            continue
        assert abc.serialize() == raw, "ABC round-trip differs"
        summary["abc_sha256"] = hashlib.sha256(raw).hexdigest()
        summary["bodies_total"] = len(abc.bodies)
        for label in LABELS:
            index = bodies.resolve(abc, label)
            body = abc.bodies[index]
            instructions = asm.decode(body[5])
            encoded, _ = asm.encode(instructions)
            assert encoded == body[5], label
            method = {"body": index, "method": body[0], "sha256": hashlib.sha256(body[5]).hexdigest(), "header": body[1:5], "exception_table": body[6], "instructions": len(instructions)}
            summary["methods"][label] = method
            output = [f"# {label}", json.dumps(method, ensure_ascii=False), ""]
            position = 0
            for i, instruction in enumerate(instructions):
                output.append(f"#{i:04d} ofs{position:04x}: {describe(abc, instruction)}")
                position += instruction.size()
            (ROOT / "client" / (label.replace("/", "__") + ".pcode.txt")).write_text("\n".join(output) + "\n", encoding="utf8")
    (ROOT / "analysis/client-v28-methods.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
