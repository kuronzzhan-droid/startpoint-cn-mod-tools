"""Evaluate the original and patched method's actual instructions at boundaries."""
from __future__ import annotations

import json
import math
import zipfile

from inspect_v28 import APK, ROOT, asm
from patch_coop_grace import patch


def int32(value):
    integer = int(value) & 0xffffffff
    return integer - 0x100000000 if integer & 0x80000000 else integer


def evaluate(abc, body, receiver):
    code = asm.decode(body[5])
    stack, locals_, pc = [], [receiver, None, None], 0
    constants = {"MULTI_BATTLE_SLOWDOWN_THRESHOLD": 48, "MULTI_BATTLE_SLOWDOWN_SPAN": 24}
    for _ in range(200):
        item = code[pc]
        pc += 1
        name = item.name
        if name.startswith("getlocal_"):
            stack.append(locals_[int(name[-1])])
        elif name.startswith("setlocal_"):
            locals_[int(name[-1])] = stack.pop()
        elif name == "pushscope":
            stack.pop()
        elif name == "findproperty":
            stack.append(receiver)
        elif name == "getproperty":
            stack.append(stack.pop()[abc.mn_name(item.args[0])])
        elif name == "getlex":
            assert abc.mn_name(item.args[0]) == "pinball.scene.battle.battle::BattleConstants"
            stack.append(constants)
        elif name in {"pushbyte", "pushint", "pushdouble"}:
            value = item.args[0]
            if name == "pushint":
                value = abc.ints[value]
            elif name == "pushdouble":
                value = abc.doubles[value]
            stack.append(value)
        elif name in {"subtract_i", "add_i", "subtract", "add", "divide"}:
            right, left = stack.pop(), stack.pop()
            value = left - right if name.startswith("subtract") else left + right if name.startswith("add") else left / right
            stack.append(int32(value) if name.endswith("_i") else value)
        elif name in {"convert_i", "convert_d"}:
            stack.append(int32(stack.pop()) if name == "convert_i" else float(stack.pop()))
        elif name == "iffalse":
            if not stack.pop():
                pc = item.target
        elif name == "ifnlt":
            right, left = stack.pop(), stack.pop()
            if not left < right:
                pc = item.target
        elif name == "jump":
            pc = item.target
        elif name == "returnvalue":
            assert len(stack) == 1
            return stack.pop()
        else:
            raise AssertionError("unsupported real instruction " + name)
    raise AssertionError("method did not terminate")


def main():
    with zipfile.ZipFile(APK) as archive:
        original_swf = archive.read("assets/worldflipper_android_release.swf")
    output, report, old, new, index = patch(original_swf)
    expected = [
        (-15, 0, 0), (0, 0, 0), (47, 0, 0), (48, 0, 0),
        (239, 7, 0), (240, 8, 0), (1607, 64, 0), (1608, 65, 0),
        (1632, 66, 1), (1776, 72, 7), (1799, 72, 7), (1800, 73, 8), (1824, 74, 9),
    ]
    assertions, rows = 0, []
    for d, before, after in expected:
        for gap in (-15, 0, 1, 15, 300):
            receiver = {"isLeaved": False, "battle": {"currentFrame": 1200}, "lastProcessableFrame": 1200 + gap, "processableFrameStandstillCount": d - gap}
            a, b = evaluate(old, old.bodies[index], receiver), evaluate(new, new.bodies[index], receiver)
            assert (a, b) == (before, after), (d, gap, a, b)
            assertions += 1
        rows.append({"D": d, "original_level": before, "patched_level": after})
    for d in range(-30, 4200):
        receiver = {"isLeaved": False, "battle": {"currentFrame": 500}, "lastProcessableFrame": 501, "processableFrameStandstillCount": d - 1}
        actual = evaluate(new, new.bodies[index], receiver)
        expected_level = 0 if d < 1608 else math.floor((d - 1608) / 24)
        assert actual == expected_level
        assert (actual >= 8) == (d >= 1800), d
        assertions += 2
        receiver["isLeaved"] = True
        assert evaluate(new, new.bodies[index], receiver) == evaluate(old, old.bodies[index], receiver) == 0
        assertions += 1
    # A resumed command frontier resets standstill in the unchanged proceed method;
    # the patched level correctly returns to zero for ordinary small forward gaps.
    for gap in range(0, 31):
        receiver = {"isLeaved": False, "battle": {"currentFrame": 1000}, "lastProcessableFrame": 1000 + gap, "processableFrameStandstillCount": 0}
        assert evaluate(new, new.bodies[index], receiver) == 0
        assertions += 1
    try:
        patch(output)
        raise AssertionError("already-patched baseline was accepted")
    except ValueError:
        assertions += 1
    with zipfile.ZipFile(ROOT / "client/baseline-v28-local.apk") as archive:
        _, local_report, _, local, local_index = patch(archive.read("assets/worldflipper_android_release.swf"))
    assert local.bodies[local_index][5] == new.bodies[index][5]
    assertions += 1
    result = {"passed": True, "assertions": assertions, "evaluated_real_bytecode": True, "boundary_rows": rows, "both_baselines_patch_same_target_body": True, "unknown_or_already_patched_input_rejected": True, "body_changes": report["bodies_changed"], "runtime_verified": False, "note": "Tests establish method arithmetic, stack and bytewise scope; device behavior remains pending."}
    (ROOT / "analysis/client-coop-grace-tests.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print(json.dumps({"passed": True, "assertions": assertions, "real_bytecode": True, "runtime_verified": False}))


if __name__ == "__main__":
    main()
