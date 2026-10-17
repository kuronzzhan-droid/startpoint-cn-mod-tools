"""Copy reference tooling (read-only sources) into ROOT/tools."""
import shutil
from pathlib import Path
from wf.paths import root_path

DEST = Path(__file__).resolve().parent
VENDOR = root_path('codex-serverfix/client-patch/author-merge-20261001')
COOP = root_path('coop-fix-20261014/client')
DECOMP = root_path('decompile-complete-20261014/tools')

def main():
    for name in ("asm.py", "bodies.py", "swfabc.py"):
        shutil.copy(VENDOR / "abcasm" / name, DEST / name)
    for name in ("abcfmt.py", "opwalk.py", "swftags.py"):
        shutil.copy(VENDOR / "rank-button-p1" / "abc" / name, DEST / name)
    for name in ("patch_coop_grace.py", "build_coop_apk.py", "verify_coop_apk.py", "test_coop_grace.py",
                 "build_local_baseline.py", "inspect_v28.py", "patch_local_endpoints.py", "verify_local_baseline.py"):
        shutil.copy(COOP / name, DEST / ("ref_" + name))
    for name in ("abc_reader.py", "pcode_utils.py"):
        shutil.copy(DECOMP / name, DEST / ("ref_" + name))
    print(sorted(p.name for p in DEST.iterdir()))


if __name__ == "__main__":
    main()
