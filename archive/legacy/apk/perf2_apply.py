"""Replay the perf-v30 method-level patches onto ANY SWF that carries the same original method bodies.

usage: python perf2_apply.py IN.swf OUT.swf [--only P1,S1,...] [--report report.json]

Matching rule per patch (see perf2_core): body sha == recorded original -> patched (and the result must equal the
recorded patched sha); == recorded patched -> left as is; anything else -> the whole run is refused, nothing written.
Patch ids: P1 MasterBinaryMap/getIndex, S1 ShopFirstOpen$/productIds (helper tag cn.shop.ShopFirstOpen),
S2 ShopTopScene/listCellEnabledResolver, B1 Restore/saveBattleRestore, C1 CharacterUseCaseBase/getListCharactersInParties.
Patches touch different methods than the damage-type / v29-coop patches, so they stack as long as those bodies match.
"""
import json
import sys
from pathlib import Path

from perf2_core import Refused, apply_patches
from perf2_patches import PATCHES


def main():
    args = sys.argv[1:]
    only, report_path = None, None
    if "--only" in args:
        i = args.index("--only")
        only = set(args[i + 1].split(","))
        del args[i:i + 2]
    if "--report" in args:
        i = args.index("--report")
        report_path = Path(args[i + 1])
        del args[i:i + 2]
    if len(args) != 2:
        raise SystemExit(__doc__)
    src, dst = Path(args[0]), Path(args[1])
    if src.resolve() == dst.resolve():
        raise SystemExit("output must differ from input")
    try:
        out, report = apply_patches(src.read_bytes(), PATCHES, only)
    except Refused as error:
        raise SystemExit(f"REFUSED: {error}")
    dst.write_bytes(out)
    if report_path:
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    for p in report["patches"]:
        print(p["id"], p["status"], p["label"])
    print("output", report["output_swf_sha256"])


if __name__ == "__main__":
    main()
