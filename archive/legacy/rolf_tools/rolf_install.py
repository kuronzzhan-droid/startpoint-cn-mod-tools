# -*- coding: utf-8 -*-
"""罗尔夫 179999 设备端整装(阶段1:临时区克隆+身份修正+推送集组装;零仓库写入)。
复用 wf_gui.clone_character(119999 金丝雀验证过的整套克隆),写点全部重定向临时区。"""

from wf.paths import root_path
import hashlib, io, json, re, shutil, sys, zlib
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
pass  # Imports resolve from this checkout/package, not external source copies.

SCRATCH = (root_path("work/legacy-rolf"))
TEMP = SCRATCH / "rolf_temp_store"
FSOUT = SCRATCH / "fullshot_out"
GSWAP = SCRATCH / "gerald_swap"
REPO = Path(('${WF_ROOT}\\startpoint-cn'.replace("${WF_ROOT}", str(root_path()))))
DESK = REPO / "弹国服/WorldFlipper/dummy/download/production"

if TEMP.exists():
    shutil.rmtree(TEMP)
(TEMP / "store").mkdir(parents=True)
(TEMP / "cdndata").mkdir()
# 种子:①层/服务端 json 副本(克隆要读写;真仓库文件只读)
shutil.copy2(REPO / "assets/cdndata/character.json", TEMP / "cdndata/character.json")
shutil.copy2(REPO / "assets/cdndata/character_text.json", TEMP / "cdndata/character_text.json")
shutil.copy2(REPO / "assets/character.json", TEMP / "character.json")
shutil.copy2(REPO / "assets/mana_node.json", TEMP / "mana_node.json")

import wf_gui
import wf_mod_tool as core
import wf_assets

# ---- 重定向:目标store=临时空根;来源=桌面 upload;cdndata=临时;pending/record=no-op ----
wf_gui.TARGET_STORE = TEMP / "store"
wf_gui.SOURCE_STORE = DESK / "upload"

# 预播种:_load_nested 等只认 TARGET 的表,先从桌面拷进临时区
_salt = re.search(r'SALT\s*=\s*["\']([^"\']+)["\']',
                  (REPO / "mod-tools/wf_decrypt_all.py").read_text(encoding="utf-8", errors="ignore")).group(1)
def _seed(logical):
    h = hashlib.sha1((logical + _salt).encode()).hexdigest()
    src = DESK / "upload" / h[:2] / h[2:]
    if not src.exists():
        print("  seed miss:", logical)
        return
    dst = TEMP / "store" / h[:2] / h[2:]
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
SEED = list(getattr(wf_gui, "CLONE_NESTED_TABLES", [])) + [
    "master/mana_board/mana_node.orderedmap",
    "master/mana_board/mana_board.orderedmap",
    wf_gui.CHAR_IMAGE_LOGICAL, wf_gui.FS_ATTR_LOGICAL,
]
for lg in dict.fromkeys(SEED):
    _seed(lg)
print("seeded nested tables:", len(set(SEED)))
wf_gui.CDNDATA = TEMP / "cdndata"
wf_gui.add_pending = lambda *a, **k: None
wf_gui.record_change = lambda *a, **k: None
if hasattr(wf_gui, "_char_cache"):
    wf_gui._char_cache = None

SRC_ID, NEW_ID = "149999", "179999"
SRC_CODE, NEW_CODE = "white_wolf_gerald", "black_wolf_knight_wt26"
NEW_NAME = "罗尔夫"

res = wf_gui.clone_character(SRC_ID, NEW_ID, NEW_NAME, dry_run=False, new_code=NEW_CODE)
(SCRATCH / "rolf_clone_result.json").write_text(
    json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print("== clone keys ==", sorted(res.keys()))
logv = res.get("log")
lines = logv if isinstance(logv, list) else [str(logv)]
for line in lines:
    print(" ", line)

# ---- 身份修正:元素→火(0),称号 ----
ct = core.load_table(core.CHARACTER_LOGICAL, wf_gui.TARGET_STORE, wf_gui.SOURCE_STORE)
parsed = {k: core.read_csv_lines(t) for k, t in ct.text_rows().items()}
# 元素列标定:141159=wind(3) 111007=fire(0)
c_wt23 = parsed["141159"][0]
c_111007 = parsed["111007"][0]
elem_col = next(i for i in range(2, 8) if c_wt23[i] == "3" and c_111007[i] == "0")
row = parsed[NEW_ID][0]
print(f"elem col={elem_col} (gerald 值 {row[elem_col]}) -> 0(火)")
row[elem_col] = "0"
# 称号列:找 gerald 原称号「毅耀守护」所在列
title_col = next((i for i, v in enumerate(parsed[SRC_ID][0]) if "守护" in str(v)), None)
if title_col is not None:
    row[title_col] = "雪夜里的炉火"
    print(f"title col={title_col} -> 雪夜里的炉火")
wf_gui._write_with_backup(ct, parsed, ["罗尔夫身份修正(元素火/称号)"])

# ---- 立绘三表:179999 行写我方值 ----
tabs = json.loads((FSOUT / "fullshot_tables.json").read_text(encoding="utf-8"))
for logical, field in ((wf_gui.CHAR_IMAGE_LOGICAL, "character_image"),
                       (wf_gui.FS_ATTR_LOGICAL, "fs_attr")):
    om = wf_gui._load_nested(logical)
    inner_rows = {lv: tabs[lv][field] for lv in ("0", "1")}
    blob = core.build_orderedmap_from_text_rows(inner_rows) if hasattr(core, "build_orderedmap_from_text_rows") else None
    if blob is None:
        # 组内层 orderedmap:借用 OrderedMap 数据类
        inner = core.OrderedMap(logical_path="inner", keys=list(inner_rows),
                                rows=[v.encode("utf-8") for v in inner_rows.values()],
                                source_path=Path("mem"))
        blob = core.build_orderedmap(inner)
    if NEW_ID in om.keys:
        om.rows[om.keys.index(NEW_ID)] = blob
    else:
        om.keys.append(NEW_ID)
        om.rows.append(blob)
    wf_gui._write_nested(om, logical, f"罗尔夫立绘表 {field}")
    print("nested ok", field)

# trimmed:全 gerald ui/story 键 → wt26 键(行照抄);full_shot 两键用我方值
tt = core.load_table(wf_gui.TRIMMED_LOGICAL, wf_gui.TARGET_STORE, wf_gui.SOURCE_STORE)
tr = tt.text_rows()
new_tr = {}
n_copy = 0
for k, v in tr.items():
    if f"character/{SRC_CODE}/" in k:
        nk = k.replace(f"character/{SRC_CODE}/", f"character/{NEW_CODE}/", 1)
        new_tr[nk] = v
        n_copy += 1
for lv in ("0", "1"):
    new_tr[f"character/{NEW_CODE}/ui/full_shot_1440_1920_{lv}"] = tabs[lv]["trimmed"]
tt.set_text_rows(new_tr)
suffix = ".bak-rolf"
core.write_table(tt, wf_gui.TARGET_STORE, suffix, no_backup=True)
print(f"trimmed: 复制 {n_copy} 键 + full_shot 2 键(我方值)")

# ---- 资产集组装(manifest:logical -> (root, 本地字节来源)) ----
push_assets = []   # (root_name, logical, bytes)
def desk_locate(logical):
    h = hashlib.sha1((logical + wf_assets.SALT if hasattr(wf_assets, 'SALT') else logical).encode()).hexdigest() if False else None
def sn(logical):
    salt = re.search(r'SALT\s*=\s*["\']([^"\']+)["\']',
                     (REPO / "mod-tools/wf_decrypt_all.py").read_text(encoding="utf-8", errors="ignore")).group(1)
    h = hashlib.sha1((logical + salt).encode()).hexdigest()
    return h[:2], h[2:]
def locate3(logical):
    d2, d38 = sn(logical)
    for root in ("upload", "medium_upload", "android_upload"):
        p = DESK / root / d2 / d38
        if p.exists():
            return root, p
    return None

OVERRIDES = {
    f"character/{NEW_CODE}/pixelart/sprite_sheet.png": GSWAP / "sprite_sheet.png",
    f"character/{NEW_CODE}/pixelart/sprite_sheet.atlas.amf3.deflate": None,  # 需前缀改写,单独处理
    f"character/{NEW_CODE}/pixelart/pixelart.frame.amf3.deflate": None,
    f"character/{NEW_CODE}/pixelart/special.frame.amf3.deflate": None,
    f"character/{NEW_CODE}/pixelart/pixelart.timeline.amf3.deflate": GSWAP / "pixelart.timeline.amf3.deflate",
    f"character/{NEW_CODE}/pixelart/special.timeline.amf3.deflate": GSWAP / "special.timeline.amf3.deflate",
    f"character/{NEW_CODE}/ui/full_shot_1440_1920_0.png": FSOUT / "full_shot_1440_1920_0.png",
    f"character/{NEW_CODE}/ui/full_shot_1440_1920_1.png": FSOUT / "full_shot_1440_1920_1.png",
    f"character/{NEW_CODE}/ui/square_0.png": FSOUT / "square_0.png",
    f"character/{NEW_CODE}/ui/square_1.png": FSOUT / "square_1.png",
}

# wt23 基的 atlas/frame 前缀改写到 wt26(像素件引用 wt23 的 .gen 名不行——sheet 是我方的)
import wf_dsl
def inflate(b):
    for raw in (b, b[4:]):
        for wb in (15, -15):
            try:
                return zlib.decompress(raw, wb)
            except Exception:
                pass
    raise RuntimeError("inflate")
def deflate_raw(d):
    co = zlib.compressobj(9, zlib.DEFLATED, -15)
    return co.compress(d) + co.flush()
WT23 = "character/black_wolf_knight_wt23/pixelart/"
NEWP = f"character/{NEW_CODE}/pixelart/"
def wt23_file(name):
    r = locate3(WT23 + name)
    return r[1].read_bytes()
atlas = wf_dsl.parse_dsl(inflate(wt23_file("sprite_sheet.atlas.amf3.deflate")))["tree"]
for e in atlas:
    e["n"] = e["n"].replace(WT23, NEWP)
OVR_BYTES = {
    f"{NEWP}sprite_sheet.atlas.amf3.deflate": deflate_raw(wf_dsl.encode_amf3(atlas)),
}
for f in ("pixelart.frame", "special.frame"):
    tree = wf_dsl.parse_dsl(inflate(wt23_file(f + ".amf3.deflate")))["tree"]
    tree["name"] = tree["name"].replace(WT23, NEWP)
    OVR_BYTES[f"{NEWP}{f}.amf3.deflate"] = deflate_raw(wf_dsl.encode_amf3(tree))

logicals = wf_assets.all_asset_logicals(wf_gui.SOURCE_STORE, SRC_CODE)
n_over = 0
for lg in sorted(set(logicals)):
    loc = locate3(lg)
    if not loc:
        continue
    root, fp = loc
    new_lg = lg.replace(f"character/{SRC_CODE}/", f"character/{NEW_CODE}/", 1)
    if new_lg in OVERRIDES and OVERRIDES[new_lg] is not None:
        data = OVERRIDES[new_lg].read_bytes()
        n_over += 1
    elif new_lg in OVR_BYTES:
        data = OVR_BYTES[new_lg]
        n_over += 1
    else:
        data = fp.read_bytes()
    push_assets.append((root, new_lg, data))
# 兜底:overrides 里不在 gerald 资产清单的(以防 all_asset_logicals 未覆盖某类)
have = {lg for _, lg, _ in push_assets}
for lg, src in list(OVERRIDES.items()) + [(k, None) for k in OVR_BYTES]:
    if lg in have:
        continue
    data = OVR_BYTES.get(lg) if src is None else (src.read_bytes() if src else None)
    if data is None:
        continue
    guess_root = "medium_upload" if "/ui/" in lg else "upload"
    push_assets.append((guess_root, lg, data))
    n_over += 1
print(f"资产集: {len(push_assets)} 件(含覆盖 {n_over});store 分布:",
      {r: sum(1 for x in push_assets if x[0] == r) for r in ('upload','medium_upload','android_upload')})

# 存 manifest 待推送
man = [(r, lg) for r, lg, _ in push_assets]
(SCRATCH / "rolf_asset_manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=0), encoding="utf-8")
import pickle
(SCRATCH / "rolf_assets.pkl").write_bytes(pickle.dumps(push_assets))
# 临时区表文件清单
tbl_files = sorted((TEMP / "store").rglob("*"))
tbl_files = [p for p in tbl_files if p.is_file() and not p.name.endswith(suffix) and ".bak" not in p.name]
print(f"临时区表文件: {len(tbl_files)}")
(SCRATCH / "rolf_tables.json").write_text(json.dumps([str(p.relative_to(TEMP / 'store')) for p in tbl_files]), encoding="utf-8")
