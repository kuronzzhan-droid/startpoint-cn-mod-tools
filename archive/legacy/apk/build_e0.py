"""E0 probe: copy v30-perf2 and add lib/x86_64/ with minimal stub .so files (one per arm64 lib name).

Each stub is a hand-built ELF64 x86_64 shared object exporting only JNI_OnLoad (returns JNI_VERSION_1_6).
Throwaway build for one logcat run on MuMu; never shipped. Output: ROOT/out/e0-x86probe.unsigned.apk
usage: python build_e0.py
"""
import hashlib
import struct
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "out" / "世界弹射测试服-v30-perf2.signed.apk"
OUT = ROOT / "out" / "e0-x86probe.unsigned.apk"


def stub_so(soname: str) -> bytes:
    code = bytes.fromhex("b806000100c3")  # mov eax,0x10006 ; ret
    dynstr = b"\0JNI_OnLoad\0" + soname.encode() + b"\0"
    shstr = b"\0.dynstr\0.dynsym\0.hash\0.text\0.dynamic\0.shstrtab\0"
    def name(s): return shstr.index(s.encode() + b"\0")
    off = {}
    blob = bytearray(0x100)
    def place(key, data, align):
        while len(blob) % align:
            blob.append(0)
        off[key] = len(blob)
        blob.extend(data)
    place("text", code, 16)
    place("dynstr", dynstr, 8)
    sym = bytes(24) + struct.pack("<IBBHQQ", 1, 0x12, 0, 4, 0, len(code))  # shndx 4 = .text
    sym = sym[:24] + struct.pack("<IBBHQQ", 1, 0x12, 0, 4, off["text"], len(code))
    place("dynsym", sym, 8)
    place("hash", struct.pack("<IIIII", 1, 2, 1, 0, 0), 8)
    dyn = b"".join(struct.pack("<qQ", t, v) for t, v in [
        (4, off["hash"]), (5, off["dynstr"]), (6, off["dynsym"]), (10, len(dynstr)), (11, 24),
        (14, 1 + len("JNI_OnLoad") + 1), (0, 0)])
    place("dynamic", dyn, 8)
    load_end = len(blob)
    place("shstr", shstr, 1)
    while len(blob) % 8:
        blob.append(0)
    shoff = len(blob)
    shdrs = [
        (0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        (name(".dynstr"), 3, 2, off["dynstr"], off["dynstr"], len(dynstr), 0, 0, 1, 0),
        (name(".dynsym"), 11, 2, off["dynsym"], off["dynsym"], 48, 1, 1, 8, 24),
        (name(".hash"), 5, 2, off["hash"], off["hash"], 20, 2, 0, 8, 4),
        (name(".text"), 1, 6, off["text"], off["text"], len(code), 0, 0, 16, 0),
        (name(".dynamic"), 6, 3, off["dynamic"], off["dynamic"], len(dyn), 1, 0, 8, 16),
        (name(".shstrtab"), 3, 0, 0, off["shstr"], len(shstr), 0, 0, 1, 0),
    ]
    for n, t, fl, addr, o, sz, link, info, al, ent in shdrs:
        blob.extend(struct.pack("<IIQQQQIIQQ", n, t, fl, addr, o, sz, link, info, al, ent))
    phdrs = [
        (1, 5, 0, 0, 0, load_end, load_end, 0x1000),          # PT_LOAD R+X
        (2, 4, off["dynamic"], off["dynamic"], off["dynamic"], len(dyn), len(dyn), 8),  # PT_DYNAMIC
        (0x6474E551, 6, 0, 0, 0, 0, 0, 16),                     # PT_GNU_STACK RW
    ]
    ph = b"".join(struct.pack("<IIQQQQQQ", *p) for p in phdrs)
    ehdr = b"\x7fELF" + bytes([2, 1, 1, 0]) + bytes(8) + struct.pack(
        "<HHIQQQIHHHHHH", 3, 62, 1, 0, 64, shoff, 0, 64, 56, len(phdrs), 64, len(shdrs), 6)
    blob[0:64] = ehdr
    blob[64:64 + len(ph)] = ph
    return bytes(blob)


def signature(name):
    return name.startswith("META-INF/") and "/" not in name[9:] and (
        name.endswith((".SF", ".RSA", ".DSA", ".EC")) or name == "META-INF/MANIFEST.MF")


def main():
    assert not OUT.exists(), "refusing to overwrite"
    with zipfile.ZipFile(SRC) as src, zipfile.ZipFile(OUT, "w") as out:
        arm = [i for i in src.infolist() if i.filename.startswith("lib/arm64-v8a/") and i.filename.endswith(".so")]
        for item in src.infolist():
            if signature(item.filename):
                continue
            out.writestr(item, src.read(item.filename))
        for item in arm:
            libname = item.filename.rsplit("/", 1)[1]
            info = zipfile.ZipInfo("lib/x86_64/" + libname, date_time=item.date_time)
            info.compress_type = item.compress_type
            info.external_attr = item.external_attr
            out.writestr(info, stub_so(libname))
        print("added", len(arm), "stubs; compress_type", {i.compress_type for i in arm})
    print(OUT, hashlib.sha256(OUT.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
