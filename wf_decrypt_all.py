#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
WF 数据包 完全解密 —— **单文件、零依赖(仅标准库)**。

一个脚本同时做两件事:
  (1) 复原每个加密哈希文件的原始逻辑路径
  (2) 按客户端逻辑解密内容,建成逻辑路径目录树

**不 import wf_mod_tool / 不读 DataCatalog / PathList / mod-tools 任何文件**。
唯一必须的外部数据 = 路径表 `.pathlist`(提取工具留下的无扩展名逻辑路径清单)。
其余输入都是数据包本身(要解密的对象),voiceLines 目录可选(补语音名)。

哈希(AssetPathTools.getHashedPath):
  文件名 = SHA1( 规范化([/\\]+->/,去开头/)(逻辑路径+扩展名) + SALT )
  存储位置 = 文件名[:2]/文件名[2:] ;前缀 store(upload/bundle/... )只决定文件夹,不进哈希。

内容混淆(fileFaker.converter / FileReader,全部内联实现):
  混淆PNG(头3字节+0x20) · MP3(首字节0xff->0x7f/明文ID3) · zlib+AMF3->json ·
  orderedmap(含嵌套表)->csv · ATF/OGG/HTML/XML/JPEG 原样。

用法:
  python wf_decrypt_all.py --base <download production> --bundle <bundle production> \
      --pathlist <.pathlist> --voice <角色语音目录(可选)> --out <输出目录> --workers 16
  # --only-bundle 只做 bundle ; --limit N 小样验证 ; --no-skip 不跳过已存在
输入与输出目录必须由命令行显式给出,不猜测维护者工作区。
"""
from __future__ import annotations
import argparse, csv, hashlib, io, json, os, re, struct, sys, zlib, collections
from pathlib import Path


def _long(path: Path) -> Path:
    r"""Windows 上给写路径加 \\?\ 扩展前缀,绕过 260 字符 MAX_PATH 限制。"""
    if os.name == "nt":
        p = os.path.abspath(str(path))
        if not p.startswith("\\\\?\\"):
            p = "\\\\?\\" + p
        return Path(p)
    return path

# ========================= 常量 =========================
SALT = "K6R9T9Hz22OpeIGEWB0ui6c6PYFQnJGy"
DL_STORES = ["upload", "medium_upload", "android_upload"]
BUNDLE_STORES = ["bundle", "medium_bundle", "small_bundle"]
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
TEMPLATES = {"$/g", "$1/$2", "$1/hash/$2.hash", "$1/sprite_sheet"}
PATHISH = re.compile(r"^[a-z][a-z0-9_]*(?:/[a-z0-9_$.\-]+)+$")
EXTS = ["", ".png", ".mp3", ".orderedmap", ".atf.deflate", ".amf3.deflate",
        ".frame.amf3.deflate", ".movie.amf3.deflate", ".timeline.amf3.deflate",
        ".parts.amf3.deflate", ".atlas.amf3.deflate", ".layout.amf3.deflate",
        ".action.dsl.amf3.deflate", ".esdl.amf3.deflate", ".ui.amf3.deflate",
        ".gacha.amf3.deflate", ".battle.amf3.deflate", ".ball.amf3.deflate",
        ".terrain.amf3.deflate", ".html.deflate", ".xml.deflate", ".css.deflate",
        ".battle.json"]


def nh(p: str) -> str:
    p = re.sub(r"[/\\]+", "/", p)
    p = re.sub(r"^/", "", p)
    d = hashlib.sha1((p + SALT).encode("utf-8")).hexdigest()
    return d[:2] + "/" + d[2:]


# ================= orderedmap 解析(内联) =================
def parse_index(raw: bytes):
    if len(raw) < 8:
        raise ValueError("too small")
    index_len = struct.unpack_from("<I", raw, 0)[0]
    if index_len <= 0 or 4 + index_len > len(raw):
        raise ValueError("bad index len")
    index = zlib.decompress(raw[4:4 + index_len])
    count = struct.unpack_from("<I", index, 0)[0]
    pairs = []
    for i in range(count):
        key_end, row_off = struct.unpack_from("<II", index, 4 + i * 8)
        pairs.append((key_end, row_off))
    key_blob = index[4 + count * 8:]
    keys, prev = [], 0
    for key_end, _ in pairs:
        keys.append(key_blob[prev:key_end].decode("utf-8"))
        prev = key_end
    return keys, pairs, index_len


def read_csv_lines(text: str):
    if not text:
        return []
    return [next(csv.reader([ln])) for ln in text.splitlines() if ln != ""]


def orderedmap_to_csv(raw: bytes):
    """任何 orderedmap(平表 / 嵌套表)-> CSV 文本;不是 orderedmap 返回 None。"""
    try:
        keys, pairs, index_len = parse_index(raw)
    except Exception:
        return None
    if not keys:
        return None
    blob = raw[4 + index_len:]
    out = io.StringIO()
    w = csv.writer(out)
    prev = 0
    for key, (_, row_end) in zip(keys, pairs):
        chunk = blob[prev:row_end]
        prev = row_end
        if not chunk:
            w.writerow([key]); continue
        # a) 标准行:zlib CSV
        try:
            text = zlib.decompress(chunk).decode("utf-8")
            lines = read_csv_lines(text)
            if not lines:
                w.writerow([key])
            for ln in lines:
                w.writerow([key] + ln)
            continue
        except Exception:
            pass
        # b) 嵌套行:内层又是一个 orderedmap(character_status/image/mana_board 等)
        try:
            ikeys, ipairs, iidx = parse_index(chunk)
            iblob = chunk[4 + iidx:]
            iprev = 0
            for ik, (_, irow_end) in zip(ikeys, ipairs):
                ichunk = iblob[iprev:irow_end]
                iprev = irow_end
                itext = ""
                if ichunk:
                    try:
                        itext = zlib.decompress(ichunk).decode("utf-8")
                    except Exception:
                        itext = ""
                ilines = read_csv_lines(itext)
                if not ilines:
                    w.writerow([key, ik])
                for ln in ilines:
                    w.writerow([key, ik] + ln)
            continue
        except Exception:
            pass
        # c) 实在解不了的行:标注字节数,不丢表
        w.writerow([key, f"<binary {len(chunk)} bytes>"])
    return out.getvalue()


# ==================== AMF3 reader(内联) ====================
class AMF3Reader:
    def __init__(self, data: bytes):
        self.data = data; self.pos = 0
        self.string_refs = []; self.object_refs = []; self.trait_refs = []

    def read_byte(self):
        v = self.data[self.pos]; self.pos += 1; return v

    def read_u29(self):
        value = 0
        for i in range(4):
            b = self.read_byte()
            if i < 3:
                value = (value << 7) | (b & 0x7F)
                if not b & 0x80:
                    return value
            else:
                return (value << 8) | b
        return value

    def read_string_body(self):
        header = self.read_u29()
        if not header & 1:
            return self.string_refs[header >> 1]
        length = header >> 1
        if length == 0:
            return ""
        raw = self.data[self.pos:self.pos + length]; self.pos += length
        v = raw.decode("utf-8"); self.string_refs.append(v); return v

    def read_value(self):
        marker = self.read_byte()
        if marker in (0x00, 0x01):
            return None
        if marker == 0x02:
            return False
        if marker == 0x03:
            return True
        if marker == 0x04:
            v = self.read_u29(); return v - 0x20000000 if v & 0x10000000 else v
        if marker == 0x05:
            v = struct.unpack(">d", self.data[self.pos:self.pos + 8])[0]; self.pos += 8; return v
        if marker == 0x06:
            return self.read_string_body()
        if marker == 0x09:
            return self.read_array()
        if marker == 0x0A:
            return self.read_object()
        raise ValueError(f"AMF3 marker 0x{marker:02x}")

    def read_array(self):
        header = self.read_u29()
        if not header & 1:
            return self.object_refs[header >> 1]
        dense_count = header >> 1
        assoc = {}
        while True:
            key = self.read_string_body()
            if key == "":
                break
            assoc[key] = self.read_value()
        dense = []
        container = dense if not assoc else {"$assoc": assoc, "$dense": dense}
        self.object_refs.append(container)
        for _ in range(dense_count):
            dense.append(self.read_value())
        return container

    def read_object(self):
        header = self.read_u29()
        if not header & 1:
            return self.object_refs[header >> 1]
        if not header & 2:
            class_name, sealed_names, externalizable, dynamic = self.trait_refs[header >> 2]
        else:
            externalizable = bool(header & 4); dynamic = bool(header & 8)
            sealed_count = header >> 4
            class_name = self.read_string_body()
            sealed_names = [self.read_string_body() for _ in range(sealed_count)]
            self.trait_refs.append((class_name, sealed_names, externalizable, dynamic))
        if externalizable:
            raise ValueError("externalizable unsupported")
        obj = {}
        if class_name:
            obj["$class"] = class_name
        self.object_refs.append(obj)
        for name in sealed_names:
            obj[name] = self.read_value()
        if dynamic:
            while True:
                key = self.read_string_body()
                if key == "":
                    break
                obj[key] = self.read_value()
        return obj


def jsonable(o):
    if isinstance(o, dict):
        return {str(k): jsonable(v) for k, v in o.items()}
    if isinstance(o, list):
        return [jsonable(v) for v in o]
    if isinstance(o, bytes):
        return o.decode("utf-8", "replace")
    return o


# ==================== 内容解密 ====================
def deobf_png(raw):
    if len(raw) < 8 or raw[0] != 0x89:
        return None
    fixed = bytearray(raw)
    for i in (1, 2, 3):
        fixed[i] = (fixed[i] - 0x20) & 0xFF
    return bytes(fixed) if bytes(fixed[:8]) == PNG_MAGIC else None


def _mp3_frame_signature(raw):
    pos = 0
    if raw[:3] == b"ID3":
        if len(raw) < 10 or any(value & 0x80 for value in raw[6:10]):
            return None
        pos = 10 + (
            (raw[6] << 21) | (raw[7] << 14) | (raw[8] << 7) | raw[9]
        )
    if pos + 4 > len(raw) or raw[pos] not in (0x7F, 0xFF):
        return None
    if (raw[pos + 1] >> 5 & 7) != 7:
        return None
    header = int.from_bytes(raw[pos:pos + 4], "big")
    version = header >> 19 & 3
    layer = header >> 17 & 3
    bitrate_index = header >> 12 & 0x0F
    srate_index = header >> 10 & 3
    if version == 1 or layer != 1 or bitrate_index in (0, 15) or srate_index == 3:
        return None
    return raw[pos]


def deobf_mp3(raw):
    if _mp3_frame_signature(raw) != 0x7F:
        return None
    bitrate_v1 = [0, 32000, 40000, 48000, 56000, 64000, 80000, 96000, 122000,
                  128000, 160000, 192000, 224000, 256000, 320000]
    bitrate_v2 = [0, 8000, 16000, 24000, 32000, 40000, 48000, 56000, 64000,
                  80000, 96000, 112000, 128000, 144000, 160000]
    srate_v1 = [44100, 48000, 32000]
    srate_v2 = [22050, 24000, 16000]
    srate_v25 = [11025, 12000, 8000]
    fixed = bytearray(raw)
    pos = 0
    while pos + 4 <= len(fixed):
        if fixed[pos] == 0x49:
            if fixed[pos:pos + 3] != b"ID3":
                break
            size = 0
            encoded_size = int.from_bytes(fixed[pos + 6:pos + 10], "big")
            mask = 0x7F000000
            while mask:
                size >>= 1
                size |= encoded_size & mask
                mask >>= 8
            pos += size + 10
            continue
        if fixed[pos] == 0x54:
            if fixed[pos:pos + 3] != b"TAG":
                break
            pos += 128
            continue
        if fixed[pos] != 0x7F or (fixed[pos + 1] >> 5 & 7) != 7:
            break
        header = int.from_bytes(fixed[pos:pos + 4], "big")
        version = header >> 19 & 3
        layer = header >> 17 & 3
        bitrate_index = header >> 12 & 0x0F
        srate_index = header >> 10 & 3
        padding = header >> 9 & 1
        if version == 1 or layer != 1 or bitrate_index in (0, 15) or srate_index == 3:
            break
        bitrate = (bitrate_v1 if version == 3 else bitrate_v2)[bitrate_index]
        srate = (srate_v1 if version == 3 else srate_v2 if version == 2 else srate_v25)[srate_index]
        fixed[pos] = 0xFF
        pos += int(144 * bitrate / srate + padding + 2e-10)
    decoded = bytes(fixed)
    return decoded if decoded != raw else None


def try_inflate(raw):
    for buf in (raw, raw[4:]):
        for args in ((), (-15,)):
            try:
                return zlib.decompress(buf, *args)
            except Exception:
                pass
    return None


def decode(raw: bytes):
    """-> (最终后缀含点, 解出的字节)。"""
    csvtext = orderedmap_to_csv(raw)
    if csvtext is not None:
        return ".csv", csvtext.encode("utf-8-sig")
    mp3_signature = _mp3_frame_signature(raw)
    if mp3_signature == 0xFF:
        return ".mp3", raw
    if mp3_signature == 0x7F:
        return ".mp3", deobf_mp3(raw)
    if raw[:4] == b"OggS":
        return ".ogg", raw
    png = deobf_png(raw)
    if png:
        return ".png", png
    if raw[:8] == PNG_MAGIC:
        return ".png", raw
    if raw[:3] == b"\xff\xd8\xff":
        return ".jpg", raw
    dec = try_inflate(raw)
    if dec is not None:
        png = deobf_png(dec)
        if png:
            return ".png", png
        if dec[:8] == PNG_MAGIC:
            return ".png", dec
        head = dec[:32].lstrip().lower()
        if head[:9] == b"<!doctype" or head[:5] == b"<html":
            return ".html", dec
        if head[:5] == b"<?xml" or head[:6] == b"<font>":
            return ".xml", dec
        if dec[:3] == b"ATF":
            return ".atf", dec
        try:
            obj = AMF3Reader(dec).read_value()
        except Exception:
            obj = None
        if obj is not None:
            return ".json", json.dumps(jsonable(obj), ensure_ascii=False, indent=1).encode("utf-8")
        return ".bin", dec
    return ".bin", raw


def strip_container(name: str) -> str:
    for suf in (".amf3.deflate", ".deflate"):
        if name.endswith(suf):
            return name[:-len(suf)]
    if name.endswith(".orderedmap"):
        return name[:-len(".orderedmap")]
    return name


# ==================== 数据包扫描 ====================
def find_production(root: Path):
    for child in list(root.iterdir()) + [root]:
        c = child / "WorldFlipper" / "dummy" / "download" / "production"
        if c.exists():
            return c
    return None


def scan_stores(root: Path, stores, present, loc2file):
    for name in stores:
        s = present.setdefault(name, set())
        st = root / name
        if not st.exists():
            continue
        for d in st.iterdir():
            if d.is_dir() and len(d.name) == 2:
                for fp in d.iterdir():
                    if ".bak" not in fp.name:
                        loc = d.name + "/" + fp.name
                        s.add(loc)
                        loc2file[(name, loc)] = fp


# ==================== 路径复原 ====================
def recover(present, loc2file, pathlist_path: Path, voice_dir: Path | None,
            have_bundle: bool):
    allhash = set()
    for s in present.values():
        allhash |= s
    found = {}

    def mark(cand):
        loc = nh(cand)
        if loc in allhash and loc not in found:
            found[loc] = cand

    # 0. bundle 索引文件(哈希命名)
    if have_bundle:
        for pre in ("bundle", "ios_bundle"):
            for cat in ("amf", "encrypt", "copy", "compress", "png", "atf"):
                name = f"{pre}_{cat}.filelist"
                loc = nh(name)
                if loc in allhash:
                    found[loc] = name

    # 1. .pathlist
    lines = pathlist_path.read_text(encoding="utf-8", errors="replace").split("\n")
    uniq = sorted(set(l for l in lines if l != ""))
    slash = [l for l in uniq if l.startswith("/") and l not in TEMPLATES]
    full = [l for l in uniq if not l.startswith("/") and l not in TEMPLATES]
    for l in slash:
        mark("master" + l + ".orderedmap")
    for l in full:
        for e in EXTS:
            mark(l + e)
        mark("master/" + l + ".orderedmap")
    print(f"[1] pathlist       : {len(found)}/{len(allhash)} = {len(found)*100//len(allhash)}%")

    # 2. ordermap 单元格路径(只对 orderedmap 文件解码;首字节 gate 避免读整包)
    cell_paths = set()
    seen = set()
    for (_, loc), fp in loc2file.items():
        if loc in seen:
            continue
        seen.add(loc)
        try:
            with fp.open("rb") as fh:
                head = fh.read(5)
                if len(head) < 5 or head[4] != 0x78:
                    continue
                raw = head + fh.read()
            keys, pairs, index_len = parse_index(raw)
            blob = raw[4 + index_len:]
            prev = 0
            for key, (_, row_end) in zip(keys, pairs):
                if PATHISH.match(key):
                    cell_paths.add(key)
                chunk = blob[prev:row_end]; prev = row_end
                if not chunk:
                    continue
                try:
                    text = zlib.decompress(chunk).decode("utf-8")
                except Exception:
                    continue
                for cell in read_csv_lines(text):
                    for v in cell:
                        if 2 < len(v) < 90 and PATHISH.match(v):
                            cell_paths.add(v)
        except Exception:
            continue
    for p in cell_paths:
        for e in EXTS:
            mark(p + e)
        mark("master/" + p + ".orderedmap")
    print(f"[2] ordermap cells : {len(found)}/{len(allhash)} = {len(found)*100//len(allhash)}%  (cells {len(cell_paths)})")

    # 3. voiceLines.json(可选)
    if voice_dir and voice_dir.exists():
        for cd in voice_dir.iterdir():
            vf = cd / "voiceLines.json"
            if not vf.exists():
                continue
            try:
                data = json.loads(vf.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                continue
            for k in data:
                mark(f"character/{cd.name}/voice/{k}.mp3")
        print(f"[3] voiceLines     : {len(found)}/{len(allhash)} = {len(found)*100//len(allhash)}%")

    # 4. 同族交叉
    fam_keys = collections.defaultdict(set)
    fam_tail_ext = collections.defaultdict(lambda: collections.defaultdict(set))
    for cand in list(found.values()):
        if cand.startswith("master/") or "/" not in cand:
            continue
        m = re.search(r"(\.[a-z0-9.]+)$", cand)
        ext = m.group(1) if m else ""
        stem = cand[:len(cand) - len(ext)] if ext else cand
        parts = stem.split("/")
        if len(parts) >= 2:
            fam_keys[parts[0]].add(parts[1])
            fam_tail_ext[parts[0]]["/".join(parts[2:])].add(ext)
    for fam, tails in fam_tail_ext.items():
        keys = list(fam_keys[fam])
        for tail, exts in tails.items():
            for key in keys:
                stem = fam + "/" + key + ("/" + tail if tail else "")
                for e in exts:
                    mark(stem + e)
    print(f"[4] family cross   : {len(found)}/{len(allhash)} = {len(found)*100//len(allhash)}%")
    return found, allhash


def enrich_from_decoded(out: Path, found: dict, allhash: set):
    r"""解密后阶段:扫描已解出的 json/csv,把里面引用的资源路径撞回未命名哈希。
    (AMF3 剧情/动画解成 json 后,里面的路径字符串才可读——这是把 _unnamed 收回来的关键。)"""
    tok = re.compile(r"[a-z][a-z0-9_]*(?:/[a-z0-9_$.\-]+)+")
    tokens = set()
    for root, _, files in os.walk(out):
        for fn in files:
            if not (fn.endswith(".json") or fn.endswith(".csv")):
                continue
            if fn.startswith("_manifest") or fn.startswith("_pathlist"):
                continue
            try:
                txt = (Path(root) / fn).read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            for m in tok.finditer(txt):
                v = m.group(0)
                if 4 < len(v) < 120 and "/" in v and not v.startswith("http"):
                    tokens.add(v)

    def mark(cand):
        loc = nh(cand)
        if loc in allhash and loc not in found:
            found[loc] = cand
    for t in tokens:
        for e in EXTS:
            mark(t + e)
        mark("master/" + t + ".orderedmap")
    # 同族交叉再跑一遍(带上新 token 的尾串)
    fam_keys = collections.defaultdict(set)
    fam_tail_ext = collections.defaultdict(lambda: collections.defaultdict(set))
    for cand in list(found.values()):
        if cand.startswith("master/") or "/" not in cand:
            continue
        m = re.search(r"(\.[a-z0-9.]+)$", cand)
        ext = m.group(1) if m else ""
        stem = cand[:len(cand) - len(ext)] if ext else cand
        parts = stem.split("/")
        if len(parts) >= 2:
            fam_keys[parts[0]].add(parts[1])
            fam_tail_ext[parts[0]]["/".join(parts[2:])].add(ext)
    for fam, tails in fam_tail_ext.items():
        keys = list(fam_keys[fam])
        for tail, exts in tails.items():
            for key in keys:
                stem = fam + "/" + key + ("/" + tail if tail else "")
                for e in exts:
                    mark(stem + e)
    print(f"[5] decoded-content: {len(found)}/{len(allhash)} = {len(found)*100//len(allhash)}%  (tokens {len(tokens)})")
    return found


# ==================== 主流程 ====================
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", help="下载包 production 目录")
    ap.add_argument("--bundle", help="可选 bundle production 目录")
    ap.add_argument("--pathlist", required=True, help="必需的 .pathlist 文件")
    ap.add_argument("--voice", help="可选 voiceLines 根目录")
    ap.add_argument("--out", required=True, help="显式输出目录")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only-bundle", action="store_true")
    ap.add_argument("--no-skip", action="store_true")
    return ap


def main(argv=None):
    ap = build_parser()
    args = ap.parse_args(argv)
    if not args.only_bundle and not args.base:
        ap.error("--base is required unless --only-bundle is used")
    if args.only_bundle and not args.bundle:
        ap.error("--bundle is required with --only-bundle")

    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    present, loc2file = {}, {}
    if not args.only_bundle:
        base = Path(args.base)
        scan_stores(base, DL_STORES, present, loc2file)
    bundle_root = Path(args.bundle) if args.bundle else None
    have_bundle = bool(bundle_root and bundle_root.exists())
    if have_bundle:
        scan_stores(bundle_root, BUNDLE_STORES, present, loc2file)
    total = sum(len(v) for v in present.values())
    print("stores:", {k: len(v) for k, v in present.items()}, "total", total)

    # ---- 复原 ----
    voice_dir = Path(args.voice) if args.voice else None
    found, allhash = recover(present, loc2file, Path(args.pathlist), voice_dir, have_bundle)
    print(f"复原 {len(found)}/{len(allhash)} = {len(found)*100/len(allhash):.1f}%")

    # ---- 解密导出 ----
    items = list(loc2file.items())
    if args.limit:
        items = items[:args.limit]
    skip = not args.no_skip
    stat = collections.Counter()
    mrows = []

    def work(kv):
        (store, loc), fp = kv
        name = found.get(loc)
        base_rel = strip_container(name) if name else f"_unnamed/{store}/{loc}"
        try:
            ext, data = decode(fp.read_bytes())
            rel = base_rel if base_rel.endswith(ext) else base_rel + ext
            target = _long(out / rel)
            if not (skip and target.exists()):
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            return ext.lstrip("."), (store, loc, name or "", rel)
        except Exception as e:
            return f"error:{type(e).__name__}", (store, loc, name or "", "")

    print(f"解密 {len(items)} 个文件 -> {out}")
    if args.workers > 1:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            for i, (kind, mrow) in enumerate(ex.map(work, items), 1):
                stat[kind] += 1; mrows.append(mrow)
                if i % 10000 == 0:
                    print(f"  {i}/{len(items)}")
    else:
        for i, kv in enumerate(items, 1):
            kind, mrow = work(kv); stat[kind] += 1; mrows.append(mrow)
            if i % 5000 == 0:
                print(f"  {i}/{len(items)}")

    # ---- 阶段5:从已解密的 json/csv 挖回未命名文件的逻辑路径,并搬出 _unnamed ----
    if not args.limit:
        before = sum(1 for r in mrows if r[2])
        enrich_from_decoded(out, found, allhash)
        moved = 0
        new_mrows = []
        for (store, loc, name, rel) in mrows:
            if not name and found.get(loc) and rel.startswith("_unnamed/"):
                ext = rel[len(f"_unnamed/{store}/{loc}"):]
                base_new = strip_container(found[loc])
                new_rel = base_new if base_new.endswith(ext) else base_new + ext
                src = _long(out / rel); dst = _long(out / new_rel)
                try:
                    if src.exists():
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        os.replace(str(src), str(dst))
                    new_mrows.append((store, loc, found[loc], new_rel)); moved += 1
                    continue
                except Exception:
                    pass
            new_mrows.append((store, loc, name, rel))
        mrows = new_mrows
        after = sum(1 for r in mrows if r[2])
        print(f"[5] 搬出 _unnamed: +{moved} 个文件命名 ({before}->{after})")

    # ---- 清单 + 复原路径表 ----
    with (out / "_manifest.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh); w.writerow(["store", "hash_path", "logical_path", "output_path"])
        w.writerows(sorted(mrows))
    with (out / "_pathlist_recovered.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh); w.writerow(["store", "hash_path", "logical_path"])
        for (store, loc) in sorted(loc2file):
            w.writerow([store, loc, found.get(loc, "")])
    print("解密完成:")
    for k, v in stat.most_common():
        print(f"  {k}: {v}")
    print("输出树:", out, " 清单:_manifest.csv  路径表:_pathlist_recovered.csv")


if __name__ == "__main__":
    main()
