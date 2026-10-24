"""Rewrite android:versionCode in an APK's binary AndroidManifest.xml (in place in the AXML, same length).

usage: python bump_versioncode.py IN.apk OUT.unsigned.apk NEW_CODE
Only the versionCode attribute value changes; signature files are dropped (re-sign afterwards).
"""
import struct
import sys
import zipfile

VERSION_CODE_RES_ID = 0x0101021B


def patch_axml(data: bytes, new_code: int):
    buf = bytearray(data)
    # resource map chunk (type 0x0180) gives attribute name index -> resource id
    pos, resmap = 8, []
    while pos < len(buf):
        ctype, hsize, csize = struct.unpack_from("<HHI", buf, pos)
        if ctype == 0x0180:
            n = (csize - hsize) // 4
            resmap = list(struct.unpack_from(f"<{n}I", buf, pos + hsize))
        elif ctype == 0x0102:  # start element
            attr_start, attr_size, attr_count = struct.unpack_from("<HHH", buf, pos + 16 + 8)
            base = pos + 16 + attr_start
            for i in range(attr_count):
                a = base + i * attr_size
                name_idx = struct.unpack_from("<I", buf, a + 4)[0]
                if name_idx < len(resmap) and resmap[name_idx] == VERSION_CODE_RES_ID:
                    old = struct.unpack_from("<I", buf, a + 16)[0]
                    struct.pack_into("<I", buf, a + 16, new_code)
                    return bytes(buf), old
        pos += csize
    raise SystemExit("versionCode attribute not found")


def main():
    src, dst, code = sys.argv[1], sys.argv[2], int(sys.argv[3])
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w") as zout:
        for item in zin.infolist():
            n = item.filename
            if n.startswith("META-INF/") and "/" not in n[9:] and (n.endswith((".SF", ".RSA", ".DSA", ".EC")) or n == "META-INF/MANIFEST.MF"):
                continue
            data = zin.read(n)
            if n == "AndroidManifest.xml":
                data, old = patch_axml(data, code)
                print(f"versionCode {old} -> {code}")
            zout.writestr(item, data)


if __name__ == "__main__":
    main()
