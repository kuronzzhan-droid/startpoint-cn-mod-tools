"""Independent reverse proof for the local endpoint-only APK replay clone."""
from __future__ import annotations

import json
import os
import zipfile
import zlib

from inspect_v28 import APK, ROOT, ABC, asm, bodies, iter_tags
from patch_local_endpoints import OLD_HOST, freeze, sha


def abc_tags(swf):
    data = zlib.decompress(swf[8:]) if swf[:3] == b"CWS" else swf[8:]
    output = []
    for kind, offset, header, length in iter_tags(data):
        raw = data[offset:offset + header + length]
        if kind == 82:
            tag = data[offset + header:offset + header + length]
            nul = tag.index(b"\0", 4)
            output.append((kind, tag[4:nul], raw, tag[nul + 1:]))
        else:
            output.append((kind, b"", raw, None))
    return output


def main():
    local = ROOT / "client/baseline-v28-local.apk"
    with zipfile.ZipFile(APK) as left, zipfile.ZipFile(local) as right:
        original, candidate = abc_tags(left.read("assets/worldflipper_android_release.swf")), abc_tags(right.read("assets/worldflipper_android_release.swf"))
    assert len(original) == len(candidate)
    changed, protected, unchanged_tags = [], {}, 0
    for before, after in zip(original, candidate):
        assert before[:2] == after[:2]
        if before[2] == after[2]:
            unchanged_tags += 1
            continue
        assert before[0] == 82 and before[1] in (b"boot_ffc6", b"cn/admission/ClientAdmission")
        old, new = ABC(before[3]), ABC(after[3])
        assert new.strings[:len(old.strings)] == old.strings
        assert len(old.bodies) == len(new.bodies)
        labels = bodies.label_map(new)
        for index, (a, b) in enumerate(zip(old.bodies, new.bodies)):
            if freeze(a) == freeze(b):
                label = labels.get(index)
                if label in {"BattleDerailleur/getDeferralLevel", "BattleDerailleur/_addSocketCommand", "BattleScenePlayingStateImpl/proceedBattles"}:
                    protected[label] = sha(b[5])
                continue
            before_code, after_code = asm.decode(a[5]), asm.decode(b[5])
            assert len(before_code) == len(after_code)
            for position, (c, d) in enumerate(zip(before_code, after_code)):
                if (c.op, c.args, c.target, c.cases, c.default) == (d.op, d.args, d.target, d.cases, d.default):
                    continue
                assert c.name == d.name == "pushstring"
                assert old.s(c.args[0]).replace(OLD_HOST, os.environ["WF_LEGACY_APK_LAN_HOST"]) == new.s(d.args[0])
                d.args = c.args.copy()
            assert asm.encode(after_code)[0] == a[5], "reverse endpoint patch differs"
            changed.append({"tag": before[1].decode(), "method": labels.get(index, f"anonymous-body-{index}"), "body": index})
    assert len(changed) == 7 and len(protected) == 3
    output = {"passed": True, "methods_reverse_proved": changed, "unchanged_coop_methods": protected, "unchanged_swf_tags": unchanged_tags, "changed_swf_tags": 2, "no_coop_algorithm_edits": True}
    (ROOT / "analysis/client-baseline-verify.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
