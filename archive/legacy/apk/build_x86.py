"""Copy a base APK and add lib/x86_64/ from a folder of x86_64 .so files (emulator-native probe builds).

usage: python build_x86.py BASE.apk LIBDIR OUT.unsigned.apk
Every lib/arm64-v8a/*.so name must have a same-named file in LIBDIR (Android loads only one ABI dir).
Stored uncompressed like the arm64 entries; zipalign -p afterwards.
"""
import hashlib
import sys
import zipfile
from pathlib import Path


def signature(name):
    return name.startswith("META-INF/") and "/" not in name[9:] and (
        name.endswith((".SF", ".RSA", ".DSA", ".EC")) or name == "META-INF/MANIFEST.MF")


def main():
    base, libdir, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    assert not out.exists(), "refusing to overwrite"
    with zipfile.ZipFile(base) as src:
        arm = [i for i in src.infolist() if i.filename.startswith("lib/arm64-v8a/") and i.filename.endswith(".so")]
        missing = [i.filename.rsplit("/", 1)[1] for i in arm if not (libdir / i.filename.rsplit("/", 1)[1]).exists()]
        assert not missing, f"missing x86_64 libs: {missing}"
        assert not any(n.startswith("lib/x86_64/") for n in src.namelist()), "base already has x86_64"
        with zipfile.ZipFile(out, "w") as dst:
            for item in src.infolist():
                if not signature(item.filename):
                    dst.writestr(item, src.read(item.filename))
            for item in arm:
                name = item.filename.rsplit("/", 1)[1]
                info = zipfile.ZipInfo("lib/x86_64/" + name, date_time=item.date_time)
                info.compress_type = item.compress_type
                info.external_attr = item.external_attr
                data = (libdir / name).read_bytes()
                dst.writestr(info, data)
                print(f"x86_64/{name} {len(data)} {hashlib.sha256(data).hexdigest()[:12]}")
    print(out, hashlib.sha256(out.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
