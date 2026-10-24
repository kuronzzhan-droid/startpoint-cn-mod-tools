#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""自制称号铭牌(degree)工具:造表行 + 造铭牌图 + 授予玩家存档。

## 机制一句话

一个称号 = `master/degree/degree.orderedmap` 里的一行(9 列) + 一张 **320×50 的
PNG 铭牌**(文字是烤进图里的,不是运行时排版)。玩家"拥有哪些称号"完全由服务端
`/profile/get_degree_list` 返回的 `degree_ids` 决定;"正佩戴哪个"是 `players.degree_id`。

证据指针(反编译源在 `弹国服/scripts/`):
  * 列布局   `pinball/master/generated/DegreeValues.as:36-48`(param1[0..8])
  * 表注册   `boot_ffc6.as:3632-3635`  path=/degree/degree
  * 铭牌渲染 `pinball/ui/component/degree/DegreeView.as:170-176`
             → `view.asset.setTexture(AssetGroupKind.Degree, degree_image, cb)`
  * 文字烤进图 `pinball/scene/degreeSelect/list/DegreeListCellContentView.as`
             的 apply():`getText("name").renderingEnabled = false`
  * 扩展名   `pinball/asset/file/FileReader.as:486-499` 固定补 ".png"
             (`isPlatformDependent` 只对 character/**/ui/skill_cutin_* 为真 ⇒ 称号无 ATF 分支;
              `isScaledAsset` 也不含 dynamic/degree/ ⇒ 无 medium_/small_ 分包)
  * 拥有清单 `pinball/loading/degree/DegreeSelectLoadingTask.as:126-206`
             (列表 = get_degree_list 的 degree_ids ∪ 任务奖励里的称号)

## 子命令

    list      列官方 + 自制称号(--custom / --contains / --json)
    create    造一个自制称号:写表行 + 写铭牌 PNG + 进 sync_pending
    grant     把称号授予某个玩家存档(可 --wear 直接佩戴)
    revoke    收回
    verify    对已存在的称号做一次全链体检(表行合法性 + 铭牌存在/尺寸)

所有子命令都支持 `--dry-run`(只打印计划,不落盘)。

## 与发布链的关系

`create` **不发布**。它只把改动写进本机 store 并追加到
`mod-tools/work/sync_pending.json`,发布仍然走 `wf_publish.py`(见 --print-publish)。
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sqlite3
import sys
import time
from dataclasses import dataclass
from pathlib import Path

pass  # Imports resolve from this checkout/package, not external source copies.
import wf_assets  # noqa: E402
import wf_client_legality as legality  # noqa: E402
import wf_mod_tool as core  # noqa: E402

ROOT = Path(__file__).resolve().parents[4]
WORK = Path(__file__).resolve().parents[3] / "work"
PENDING = WORK / "sync_pending.json"
CHANGELOG = WORK / "changelog.jsonl"

DEGREE_LOGICAL = "master/degree/degree.orderedmap"
DEGREE_CATEGORY_LOGICAL = "master/degree/degree_category.orderedmap"

COLUMNS = legality.DEGREE_COLUMNS
NCOLS = legality.DEGREE_NCOLS
ICON_BASE_IMAGE = legality.DEGREE_ICON_BASE_IMAGE
ICON_DOT_IMAGE = legality.DEGREE_ICON_DOT_IMAGE
IMAGE_PREFIX = legality.DEGREE_IMAGE_PREFIX

# 官方 1485/1485 张铭牌都是 320×50(2026-08-27 全表实测)。尺寸不一样不会崩,
# 但 DegreeView 用 alignPivot(CENTER) 摆放,大小不对就是错位/溢出。
PLATE_SIZE = (320, 50)

# 自制号段:官方 id 最大 1900010、display_order 最大 750037(且 1485 个 order 互不相同)。
# 留出整整一个数量级,任何官方新表都撞不上。
CUSTOM_ID_MIN = 9900001
CUSTOM_ORDER_MIN = 990000

DEFAULT_TEMPLATE = "1"          # degree_default「周游世界之人」——最干净的纯色缎带
DEFAULT_CATEGORY = "8"          # 其他
DEFAULT_CONDITION = "获得条件：自制称号"
STRING_ID_PREFIX = "degree_mod_"
STRING_ID_RE = re.compile(r"^[a-z0-9_]+$")

# 只在这些字体里挑(必须本机真实存在,不凭空发明路径)
FONT_CANDIDATES = (
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\Dengb.ttf",
    r"C:\Windows\Fonts\simhei.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
)


class DegreeError(RuntimeError):
    """工具级失败(配置/输入/合法性),对使用者是可读的一句话。"""


# ---------------------------------------------------------------- store / 表


def resolve_store(explicit: str | None = None) -> Path:
    if explicit:
        store = Path(explicit)
        if not store.exists():
            raise DegreeError(f"--store 不存在: {store}")
        return store
    store = core.resolve_active_store()
    if store is None:
        raise DegreeError(
            "找不到 store(…/WorldFlipper/dummy/download/production/upload)。"
            "用 --store 指定,或设 WF_TARGET_STORE。"
        )
    return store


def load_degree_table(store: Path) -> core.OrderedMap:
    return core.load_table(DEGREE_LOGICAL, store)


def load_category_ids(store: Path) -> frozenset[str]:
    return frozenset(core.load_table(DEGREE_CATEGORY_LOGICAL, store).keys)


def row_of(table: core.OrderedMap, key: str) -> list[str]:
    text = table.text_rows()[key]
    rows = core.read_csv_lines(text)
    if len(rows) != 1:
        raise DegreeError(f"称号 {key} 的行不是单条 CSV(实际 {len(rows)} 条)")
    return core.normalize_row_length(rows[0], NCOLS)


def find_key(table: core.OrderedMap, token: str) -> str:
    """按 id 或 string_id 定位一行。"""
    token = str(token).strip()
    if token in table.keys:
        return token
    text_rows = table.text_rows()
    for key in table.keys:
        rows = core.read_csv_lines(text_rows[key])
        if rows and rows[0] and rows[0][0] == token:
            return key
    raise DegreeError(f"找不到称号: {token!r}(既不是 id 也不是 string_id)")


def is_custom(key: str) -> bool:
    return key.isdigit() and int(key) >= CUSTOM_ID_MIN


def next_free_id(table: core.OrderedMap) -> str:
    used = {int(k) for k in table.keys if k.isdigit()}
    candidate = CUSTOM_ID_MIN
    while candidate in used:
        candidate += 1
    return str(candidate)


def next_free_order(table: core.OrderedMap) -> str:
    """display_order 官方 1485 个互不相同,自制号段也保持唯一,避免列表排序抖动。"""
    used: set[int] = set()
    text_rows = table.text_rows()
    for key in table.keys:
        rows = core.read_csv_lines(text_rows[key])
        if rows and len(rows[0]) > 1 and rows[0][1].strip().isdigit():
            used.add(int(rows[0][1].strip()))
    candidate = CUSTOM_ORDER_MIN
    while candidate in used:
        candidate += 1
    return str(candidate)


def slugify(name: str, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return slug or fallback


# ---------------------------------------------------------------- 铭牌美术


def _require_pillow():
    try:
        from PIL import Image, ImageDraw, ImageFont  # noqa: F401
    except ImportError as exc:  # pragma: no cover - 环境缺 Pillow 才会走到
        raise DegreeError("需要 Pillow 才能生成铭牌图:pip install pillow") from exc
    from PIL import Image, ImageDraw, ImageFont
    return Image, ImageDraw, ImageFont


def resolve_font(explicit: str | None) -> str:
    if explicit:
        if not Path(explicit).is_file():
            raise DegreeError(f"--font 不存在: {explicit}")
        return explicit
    for candidate in FONT_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    raise DegreeError(
        "本机找不到可用的中文字体,请用 --font 指定一个 .ttf/.ttc。"
        f"已试过:{', '.join(FONT_CANDIDATES)}"
    )


def read_plate(store: Path, logical: str):
    """从 store 读一张铭牌 PNG(自动翻小写魔数)。"""
    Image, _, _ = _require_pillow()
    path = core.table_path(store, logical + ".png")
    if not path.is_file():
        raise DegreeError(f"store 里没有铭牌图: {logical}.png -> {path}")
    data = wf_assets.png_decode(path.read_bytes())
    return Image.open(io.BytesIO(data)).convert("RGBA")


@dataclass(frozen=True)
class PlateGeometry:
    """从模板图量出来的排版参数(而不是猜出来的)。"""
    left: int          # 可覆写区左边界(含)
    right: int         # 可覆写区右边界(含)
    text_top: int
    text_bottom: int

    @property
    def center_x(self) -> float:
        return (self.left + self.right) / 2

    @property
    def center_y(self) -> float:
        return (self.text_top + self.text_bottom) / 2

    @property
    def text_height(self) -> int:
        return self.text_bottom - self.text_top + 1


def measure_plate(image) -> tuple[bytes, PlateGeometry]:
    """找出模板的"纯色缎带列",并量出原文字所占的行/列范围。

    纯色列出现次数不够多 = 这张模板是渐变/带插画的,不能靠"用纯色列填平"抹字,
    直接失败关闭(叫用户换模板或自带整图),不做会毁图的猜测。
    """
    from collections import Counter

    width, height = image.size
    pixels = image.load()
    columns = [
        bytes(bytearray(
            channel
            for y in range(height)
            for channel in pixels[x, y]
        ))
        for x in range(width)
    ]
    modal, count = Counter(columns).most_common(1)[0]
    if count < width // 3:
        raise DegreeError(
            f"模板不适合换字:最常见的纯色列只占 {count}/{width} 列,"
            "说明缎带是渐变或带插画的。换一张纯色模板(--template 1),"
            "或者用 --image 直接给整张 320×50 的成品图。"
        )
    indices = [x for x, col in enumerate(columns) if col == modal]
    left, right = indices[0], indices[-1]
    inner = [x for x in range(left, right + 1) if columns[x] != modal]
    if not inner:
        raise DegreeError("模板的可覆写区里没有文字,量不出排版参数;请用 --image")

    modal_pixels = [
        tuple(modal[i * 4:(i + 1) * 4]) for i in range(height)
    ]
    rows = [
        y for y in range(height)
        if any(tuple(pixels[x, y]) != modal_pixels[y] for x in inner)
    ]
    return modal, PlateGeometry(left, right, rows[0], rows[-1])


def blank_plate(image, modal: bytes, geometry: PlateGeometry):
    """把可覆写区整段替换成纯色列 —— 得到一张"没有字"的缎带。"""
    out = image.copy()
    height = out.size[1]
    modal_pixels = [tuple(modal[i * 4:(i + 1) * 4]) for i in range(height)]
    px = out.load()
    for x in range(geometry.left, geometry.right + 1):
        for y in range(height):
            px[x, y] = modal_pixels[y]
    return out


def recolor(image, hue: float, saturation: float, value: float):
    """HSV 旋转。白色文字 S≈0,天然不受 hue 影响,所以"换色"不会把字染花。"""
    import colorsys

    if hue == 0 and saturation == 1 and value == 1:
        return image
    out = image.copy()
    px = out.load()
    width, height = out.size
    cache: dict[tuple[int, int, int], tuple[int, int, int]] = {}
    for y in range(height):
        for x in range(width):
            r, g, b, a = px[x, y]
            if a == 0:
                continue
            key = (r, g, b)
            mapped = cache.get(key)
            if mapped is None:
                h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
                h = (h + hue / 360.0) % 1.0
                s = min(1.0, max(0.0, s * saturation))
                v = min(1.0, max(0.0, v * value))
                nr, ng, nb = colorsys.hsv_to_rgb(h, s, v)
                mapped = (round(nr * 255), round(ng * 255), round(nb * 255))
                cache[key] = mapped
            px[x, y] = (mapped[0], mapped[1], mapped[2], a)
    return out


def sample_text_color(image, geometry: PlateGeometry, modal: bytes) -> tuple[int, int, int, int]:
    """取原文字里最亮的实心色作为新文字色(官方缎带是 250,250,250 的近白)。"""
    height = image.size[1]
    modal_pixels = [tuple(modal[i * 4:(i + 1) * 4]) for i in range(height)]
    px = image.load()
    best = None
    for y in range(geometry.text_top, geometry.text_bottom + 1):
        for x in range(geometry.left, geometry.right + 1):
            pixel = tuple(px[x, y])
            if pixel[3] < 255 or pixel == modal_pixels[y]:
                continue
            score = pixel[0] + pixel[1] + pixel[2]
            if best is None or score > best[0]:
                best = (score, pixel)
    return best[1] if best else (250, 250, 250, 255)


def draw_title(image, text: str, geometry: PlateGeometry, font_path: str,
               color: tuple[int, int, int, int], margin: int = 8):
    """把标题画在量出来的文字框里:高度对齐原文字,过宽就自动缩号。"""
    _, ImageDraw, ImageFont = _require_pillow()
    out = image.copy()
    draw = ImageDraw.Draw(out)
    max_width = (geometry.right - geometry.left + 1) - margin * 2
    size = geometry.text_height + 4
    font = None
    while size >= 8:
        font = ImageFont.truetype(font_path, size)
        box = draw.textbbox((0, 0), text, font=font)
        if (box[2] - box[0]) <= max_width and (box[3] - box[1]) <= geometry.text_height:
            break
        size -= 1
    if font is None:
        raise DegreeError("字体加载失败")
    if size < 8:
        raise DegreeError(f"称号文案太长,{max_width}px 宽塞不下:{text!r}")
    draw.text((geometry.center_x, geometry.center_y), text, font=font,
              fill=color, anchor="mm")
    return out, size


def build_plate(store: Path, text: str, *, template: str, font_path: str,
                hue: float, saturation: float, value: float) -> tuple[bytes, dict]:
    """克隆官方模板 → 抹字 → 换色 → 写新字。返回标准 PNG 字节 + 排版报告。"""
    table = load_degree_table(store)
    key = find_key(table, template)
    logical = row_of(table, key)[COLUMNS["degree_image"]]
    source = read_plate(store, logical)
    if source.size != PLATE_SIZE:
        raise DegreeError(
            f"模板 {key} 尺寸 {source.size} 不是官方的 {PLATE_SIZE[0]}×{PLATE_SIZE[1]}"
        )
    modal, geometry = measure_plate(source)
    color = sample_text_color(source, geometry, modal)
    blank = blank_plate(source, modal, geometry)
    tinted = recolor(blank, hue, saturation, value)
    plate, size = draw_title(tinted, text, geometry, font_path, color)

    buffer = io.BytesIO()
    plate.save(buffer, format="PNG")
    report = {
        "template_key": key,
        "template_image": logical,
        "writable_span": [geometry.left, geometry.right],
        "text_band": [geometry.text_top, geometry.text_bottom],
        "font": font_path,
        "font_size": size,
        "text_color": list(color),
        "hue": hue,
        "saturation": saturation,
        "value": value,
    }
    return buffer.getvalue(), report


def check_plate_bytes(data: bytes) -> list[str]:
    """铭牌成品的硬体检(尺寸/模式/透明底)。"""
    Image, _, _ = _require_pillow()
    problems: list[str] = []
    if data[:8] != wf_assets.PNG_REAL:
        problems.append("不是标准 PNG(魔数不对);store 里那份是小写 \\x89png,先 png_decode")
        return problems
    with Image.open(io.BytesIO(data)) as image:
        image.load()
        if image.format != "PNG":
            problems.append(f"格式必须是 PNG,实际 {image.format}")
        if image.size != PLATE_SIZE:
            problems.append(
                f"尺寸必须是 {PLATE_SIZE[0]}×{PLATE_SIZE[1]},实际 "
                f"{image.size[0]}×{image.size[1]}(官方 1485/1485 张都是这个尺寸)"
            )
        if image.mode != "RGBA":
            problems.append(f"模式必须是 RGBA,实际 {image.mode}")
        else:
            low, high = image.getchannel("A").getextrema()
            if high == 0:
                problems.append("整张全透明")
    return problems


# ---------------------------------------------------------------- pending / 日志


def read_pending() -> list[str]:
    try:
        return json.loads(PENDING.read_text(encoding="utf-8"))
    except Exception:
        return []


def add_pending(store: Path, target: Path) -> str:
    rel = target.relative_to(store).as_posix()
    items = read_pending()
    if rel not in items:
        items.append(rel)
    WORK.mkdir(parents=True, exist_ok=True)
    PENDING.write_text(json.dumps(items, indent=2), encoding="utf-8")
    return rel


def record_change(logical: str, summary: str, backup: Path | str | None,
                  keys: list[str]) -> None:
    """与 wf_gui.record_change 同格式,好让 wf_publish 发布时回填版本号。"""
    try:
        WORK.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "table": "degree" if logical == DEGREE_LOGICAL else logical,
            "logical": logical,
            "keys": keys[:8],
            "summary": summary.strip(),
            "backup": (str(backup) if backup else None),
            "version": None,
        }
        with CHANGELOG.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


# ---------------------------------------------------------------- 存档(服务端 DB)


def resolve_db(explicit: str | None = None) -> Path:
    if explicit:
        path = Path(explicit)
    else:
        data_dir = os.environ.get("WF_DATABASE_DIR", "").strip()
        base = Path(data_dir) if data_dir else ROOT / ".database"
        path = base / "wdfp_data.db"
    if not path.is_file():
        raise DegreeError(f"找不到服务端存档库: {path}(用 --db 指定)")
    return path


OWNED_DEGREES_DDL = """
CREATE TABLE IF NOT EXISTS players_degrees (
        player_id INTEGER NOT NULL,
        degree_id INTEGER NOT NULL,
        PRIMARY KEY (player_id, degree_id),
        FOREIGN KEY (player_id) REFERENCES players (id) ON DELETE CASCADE
    )
"""


def open_db(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(path))
    connection.row_factory = sqlite3.Row
    return connection


def resolve_player(connection: sqlite3.Connection, token: str) -> sqlite3.Row:
    token = str(token).strip()
    if token.isdigit():
        row = connection.execute(
            "SELECT id, name, degree_id FROM players WHERE id = ?", (int(token),)
        ).fetchone()
        if row is not None:
            return row
    rows = connection.execute(
        "SELECT id, name, degree_id FROM players WHERE name = ?", (token,)
    ).fetchall()
    if len(rows) == 1:
        return rows[0]
    if len(rows) > 1:
        raise DegreeError(
            f"玩家名 {token!r} 对应多个存档: {[r['id'] for r in rows]},请改用 id"
        )
    known = connection.execute("SELECT id, name FROM players ORDER BY id").fetchall()
    listing = ", ".join(f"{r['id']}={r['name']}" for r in known)
    raise DegreeError(f"找不到玩家 {token!r}。现有存档: {listing}")


def published_degree_keys() -> set[str] | None:
    """发布链上最新那份 degree 表的键集合;读不出来返回 None(= 无法判断)。

    为什么 grant 要看这个:客户端拿到一个链上不存在的 degree id 时,
    `globalLogic.getDegree(id)` 走 MasterMapBase.getByIndex(-1) 返回 null,
    紧接着 DegreeView 读 get_degreeImagePath() 就是空引用 —— 称号列表一进就崩。
    所以"先发布、再授予"是硬顺序。
    """
    import zipfile

    try:
        import wf_publish_guard as guard
        index = guard.chain_latest_index()
    except Exception:
        return None
    digest = core.sha1_path(DEGREE_LOGICAL)
    entry = index.get(f"{digest[:2]}/{digest[2:]}")
    if entry is None:
        return None
    _version, archive_path, member = entry
    try:
        with zipfile.ZipFile(archive_path) as archive:
            keys = core.parse_index(archive.read(member))[0]
    except Exception:
        return None
    return set(keys) or None


def owned_degrees(connection: sqlite3.Connection, player_id: int) -> list[int]:
    try:
        rows = connection.execute(
            "SELECT degree_id FROM players_degrees WHERE player_id = ? "
            "ORDER BY degree_id", (player_id,)
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    return [int(r["degree_id"]) for r in rows]


# ---------------------------------------------------------------- 子命令


def cmd_list(args: argparse.Namespace) -> int:
    store = resolve_store(args.store)
    table = load_degree_table(store)
    text_rows = table.text_rows()
    records = []
    for key in table.keys:
        rows = core.read_csv_lines(text_rows[key])
        if not rows:
            continue
        row = core.normalize_row_length(rows[0], NCOLS)
        record = {
            "id": key,
            "custom": is_custom(key),
            "string_id": row[COLUMNS["string_id"]],
            "display_order": row[COLUMNS["display_order"]],
            "name": row[COLUMNS["name"]],
            "condition": row[COLUMNS["condition"]],
            "category_id": row[COLUMNS["category_id"]],
            "degree_image": row[COLUMNS["degree_image"]],
        }
        if args.custom and not record["custom"]:
            continue
        if args.contains and args.contains not in (record["name"] + record["string_id"]):
            continue
        records.append(record)
    if args.json:
        print(json.dumps(records, ensure_ascii=False, indent=2))
        return 0
    shown = records if args.limit <= 0 else records[: args.limit]
    for record in shown:
        flag = "自制" if record["custom"] else "官方"
        print(f"{record['id']:>9}  [{flag}] {record['name']}  "
              f"({record['string_id']}, order={record['display_order']}, "
              f"cat={record['category_id']})")
    print(f"-- {len(shown)}/{len(records)} 条(全表 {len(table.keys)} 个称号,"
          f"自制 {sum(1 for r in records if r['custom'])} 个)")
    return 0


def cmd_create(args: argparse.Namespace) -> int:
    store = resolve_store(args.store)
    table = load_degree_table(store)
    categories = load_category_ids(store)

    name = args.name.strip()
    if not name:
        raise DegreeError("--name 不能为空")

    degree_id = str(args.id) if args.id else next_free_id(table)
    if not degree_id.isdigit():
        raise DegreeError(f"--id 必须是数字: {degree_id!r}")
    if degree_id in table.keys and not args.replace:
        raise DegreeError(f"称号 id {degree_id} 已存在;要覆盖请加 --replace")
    if not is_custom(degree_id) and not args.allow_official_id:
        raise DegreeError(
            f"id {degree_id} 落在官方号段(<{CUSTOM_ID_MIN});"
            "自制称号请用自制号段,确要覆盖官方请显式加 --allow-official-id"
        )

    string_id = args.string_id or (STRING_ID_PREFIX + slugify(args.slug or "", degree_id))
    if not STRING_ID_RE.match(string_id):
        raise DegreeError(f"string_id 只能是小写字母/数字/下划线: {string_id!r}")
    taken = {
        core.read_csv_lines(table.text_rows()[k])[0][0]
        for k in table.keys
        if core.read_csv_lines(table.text_rows()[k])
    }
    if string_id in taken and degree_id not in table.keys:
        raise DegreeError(f"string_id {string_id!r} 已被占用")

    display_order = str(args.display_order) if args.display_order else next_free_order(table)
    image_slug = args.image_name or string_id
    if not STRING_ID_RE.match(image_slug):
        raise DegreeError(f"铭牌文件名只能是小写字母/数字/下划线: {image_slug!r}")
    image_logical = IMAGE_PREFIX + image_slug

    used_images = {
        core.normalize_row_length(core.read_csv_lines(table.text_rows()[k])[0], NCOLS)[8]
        for k in table.keys
        if core.read_csv_lines(table.text_rows()[k])
    }
    if image_logical in used_images and degree_id not in table.keys:
        raise DegreeError(f"铭牌路径 {image_logical} 已被官方/自制称号占用,换 --image-name")

    row = [""] * NCOLS
    row[COLUMNS["string_id"]] = string_id
    row[COLUMNS["display_order"]] = display_order
    row[COLUMNS["name"]] = name
    row[COLUMNS["kana"]] = args.kana or string_id[len(STRING_ID_PREFIX):] or string_id
    row[COLUMNS["condition"]] = args.condition
    row[COLUMNS["category_id"]] = str(args.category)
    row[COLUMNS["icon_base_image"]] = ICON_BASE_IMAGE
    row[COLUMNS["icon_dot_image"]] = ICON_DOT_IMAGE
    row[COLUMNS["degree_image"]] = image_logical

    problems = legality.degree_row_problems(row, category_ids=categories)
    if problems:
        raise DegreeError("表行不合法:\n  - " + "\n  - ".join(problems))

    # --- 铭牌美术
    if args.image:
        source = Path(args.image)
        if not source.is_file():
            raise DegreeError(f"--image 不存在: {source}")
        plate_bytes = source.read_bytes()
        plate_report = {"source": str(source)}
    else:
        plate_bytes, plate_report = build_plate(
            store, args.plate_text or name,
            template=args.template,
            font_path=resolve_font(args.font),
            hue=args.hue, saturation=args.saturation, value=args.value,
        )
    plate_problems = check_plate_bytes(plate_bytes)
    if plate_problems:
        raise DegreeError("铭牌图不合法:\n  - " + "\n  - ".join(plate_problems))

    table_target = core.table_path(store, DEGREE_LOGICAL)
    image_target = core.table_path(store, image_logical + ".png")

    print(f"称号 id      : {degree_id}")
    print(f"string_id    : {string_id}")
    print(f"文案         : {name}")
    print(f"条件文案     : {row[COLUMNS['condition']]}")
    print(f"分类         : {row[COLUMNS['category_id']]}")
    print(f"display_order: {display_order}")
    print(f"铭牌逻辑路径 : {image_logical}.png")
    print(f"铭牌落点     : {image_target.relative_to(store).as_posix()}")
    print(f"表落点       : {table_target.relative_to(store).as_posix()}")
    print(f"排版         : {json.dumps(plate_report, ensure_ascii=False)}")
    print(f"CSV 行       : {core.write_csv_lines([row])}")

    if args.preview:
        preview = Path(args.preview)
        preview.parent.mkdir(parents=True, exist_ok=True)
        preview.write_bytes(plate_bytes)
        print(f"预览图       : {preview}")

    if args.dry_run:
        print("\n[dry-run] 未写盘。去掉 --dry-run 才会落地。")
        return 0

    image_target.parent.mkdir(parents=True, exist_ok=True)
    image_target.write_bytes(wf_assets.png_encode(plate_bytes))
    readback = wf_assets.png_decode(image_target.read_bytes())
    if readback != plate_bytes:
        raise DegreeError(f"铭牌写后复读不一致: {image_logical}")

    table.set_text_rows({degree_id: core.write_csv_lines([row])})
    suffix = f".bak-degree-{time.strftime('%Y%m%d-%H%M%S')}"
    written = core.write_table(table, store, suffix)
    backup = written.with_name(written.name + suffix)

    rel_image = add_pending(store, image_target)
    rel_table = add_pending(store, written)
    record_change(DEGREE_LOGICAL, f"{degree_id} 新增自制称号「{name}」", backup, [degree_id])

    print(f"\n已写入 store。sync_pending 追加: {rel_table}, {rel_image}")
    print("发布(留给作者亲手做):")
    print(f"  python -X utf8 mod-tools/wf_publish.py --list")
    print(f"  python -X utf8 mod-tools/wf_publish.py "
          f"--tables degree,{image_logical}.png")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    store = resolve_store(args.store)
    table = load_degree_table(store)
    categories = load_category_ids(store)
    keys = [find_key(table, t) for t in args.degree] if args.degree else [
        k for k in table.keys if is_custom(k)
    ]
    if not keys:
        print("没有自制称号可查(自制号段 >= %d)" % CUSTOM_ID_MIN)
        return 0
    failed = 0
    for key in keys:
        row = row_of(table, key)
        problems = legality.degree_row_problems(row, category_ids=categories)
        image_logical = row[COLUMNS["degree_image"]]
        image_path = core.table_path(store, image_logical + ".png")
        if not image_path.is_file():
            problems.append(f"铭牌图缺失: {image_logical}.png -> {image_path}")
        else:
            problems.extend(
                f"铭牌图: {p}"
                for p in check_plate_bytes(wf_assets.png_decode(image_path.read_bytes()))
            )
        status = "OK" if not problems else "FAIL"
        print(f"[{status}] {key} {row[COLUMNS['name']]} ({image_logical})")
        for problem in problems:
            print(f"       - {problem}")
        failed += bool(problems)
    print(f"-- {len(keys) - failed}/{len(keys)} 通过")
    return 1 if failed else 0


def cmd_grant(args: argparse.Namespace) -> int:
    store = resolve_store(args.store)
    table = load_degree_table(store)
    key = find_key(table, args.degree)
    row = row_of(table, key)
    categories = load_category_ids(store)
    problems = legality.degree_row_problems(row, category_ids=categories)
    if problems:
        raise DegreeError(
            "拒绝授予:该称号的表行不合法,进游戏会崩。\n  - " + "\n  - ".join(problems)
        )

    published = published_degree_keys()
    if published is None:
        print("提示:读不到发布链上的 degree 表,跳过「是否已发布」检查。")
    elif key not in published and not args.allow_unpublished:
        raise DegreeError(
            f"称号 {key} 还没发布到客户端链上(链上那份 degree 表里没有这个键)。"
            "先发布、客户端更新完再授予 —— 否则客户端 getDegree 拿到 null,"
            "一进称号列表就崩。确要提前写库请加 --allow-unpublished。"
        )

    db_path = resolve_db(args.db)
    connection = open_db(db_path)
    try:
        player = resolve_player(connection, args.player)
        already = owned_degrees(connection, int(player["id"]))
        print(f"存档库       : {db_path}")
        print(f"玩家         : {player['id']} {player['name']}")
        print(f"当前佩戴     : {player['degree_id']}")
        print(f"已拥有(表)  : {already or '(空)'}")
        print(f"授予         : {key} 「{row[COLUMNS['name']]}」")
        if args.wear:
            print("并设为佩戴中 : 是")
        if args.dry_run:
            print("\n[dry-run] 未写库。")
            return 0
        with connection:
            connection.execute(OWNED_DEGREES_DDL)
            connection.execute(
                "INSERT OR IGNORE INTO players_degrees (player_id, degree_id) "
                "VALUES (?, ?)", (int(player["id"]), int(key))
            )
            if args.wear:
                connection.execute(
                    "UPDATE players SET degree_id = ? WHERE id = ?",
                    (int(key), int(player["id"])),
                )
    finally:
        connection.close()
    print("\n已写入存档库。")
    print("提醒:服务端要读 players_degrees 才能在称号列表里出现 —— "
          "改过 src/ 之后必须 tsc + 重启 8001,否则跑的是 out/ 里的旧代码。")
    return 0


def cmd_revoke(args: argparse.Namespace) -> int:
    db_path = resolve_db(args.db)
    connection = open_db(db_path)
    try:
        player = resolve_player(connection, args.player)
        degree_id = int(args.degree)
        owned = owned_degrees(connection, int(player["id"]))
        print(f"存档库       : {db_path}")
        print(f"玩家         : {player['id']} {player['name']}")
        print(f"已拥有(表)  : {owned or '(空)'}")
        print(f"收回         : {degree_id}")
        wearing = int(player["degree_id"]) == degree_id
        if wearing:
            print(f"正佩戴中,将回落到默认称号 1")
        if args.dry_run:
            print("\n[dry-run] 未写库。")
            return 0
        with connection:
            connection.execute(OWNED_DEGREES_DDL)
            connection.execute(
                "DELETE FROM players_degrees WHERE player_id = ? AND degree_id = ?",
                (int(player["id"]), degree_id),
            )
            if wearing:
                connection.execute(
                    "UPDATE players SET degree_id = 1 WHERE id = ?",
                    (int(player["id"]),),
                )
    finally:
        connection.close()
    print("\n已写入存档库。")
    return 0


# ---------------------------------------------------------------- CLI


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wf_degree",
        description="自制称号铭牌:造表行 + 造 320×50 铭牌 + 授予玩家存档",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add_store(p):
        p.add_argument("--store", help="store 根(默认按 WF_TARGET_STORE / 档案 / 仓内发现)")
        p.add_argument("--dry-run", action="store_true", help="只打印计划,不落盘")

    listing = sub.add_parser("list", help="列称号")
    listing.add_argument("--store")
    listing.add_argument("--dry-run", action="store_true", help="(list 只读,此开关无副作用)")
    listing.add_argument("--custom", action="store_true", help="只看自制号段")
    listing.add_argument("--contains", help="按名字/string_id 子串过滤")
    listing.add_argument("--limit", type=int, default=40, help="最多打印几条(0=不限)")
    listing.add_argument("--json", action="store_true")
    listing.set_defaults(func=cmd_list)

    create = sub.add_parser("create", help="造一个自制称号")
    add_store(create)
    create.add_argument("--name", required=True, help="称号文案(会烤进铭牌图)")
    create.add_argument("--id", help=f"称号 id(默认自动取 >= {CUSTOM_ID_MIN} 的空位)")
    create.add_argument("--string-id", help=f"默认 {STRING_ID_PREFIX}<slug>")
    create.add_argument("--slug", help="用于拼 string_id 的英文短名")
    create.add_argument("--kana", help="假名列(排序用,默认取 string_id 后缀)")
    create.add_argument("--condition", default=DEFAULT_CONDITION, help="获取条件文案")
    create.add_argument("--category", default=DEFAULT_CATEGORY,
                        help="degree_category 键(1玩家 2角色 3单人 4协力 5互通 6装备 7商店 8其他)")
    create.add_argument("--display-order", help="列表排序键(默认自动取自制号段空位)")
    create.add_argument("--image-name", help="铭牌文件名(默认同 string_id)")
    create.add_argument("--image", help="直接用这张 320×50 RGBA PNG,不做克隆换字")
    create.add_argument("--template", default=DEFAULT_TEMPLATE,
                        help="克隆哪张官方铭牌(id 或 string_id,默认 1=纯色缎带)")
    create.add_argument("--plate-text", help="铭牌上画的字(默认同 --name)")
    create.add_argument("--font", help="字体文件(默认在本机常见中文字体里挑)")
    create.add_argument("--hue", type=float, default=0.0, help="缎带色相旋转角度")
    create.add_argument("--saturation", type=float, default=1.0, help="饱和度倍率")
    create.add_argument("--value", type=float, default=1.0, help="明度倍率")
    create.add_argument("--preview", help="把成品铭牌另存一份到这个路径(方便肉眼看)")
    create.add_argument("--replace", action="store_true", help="允许覆盖同 id 的已有行")
    create.add_argument("--allow-official-id", action="store_true",
                        help="允许写进官方号段(危险,默认拒绝)")
    create.set_defaults(func=cmd_create)

    verify = sub.add_parser("verify", help="体检:表行合法性 + 铭牌存在/尺寸")
    add_store(verify)
    verify.add_argument("degree", nargs="*", help="不给就查全部自制称号")
    verify.set_defaults(func=cmd_verify)

    grant = sub.add_parser("grant", help="授予某个玩家存档")
    add_store(grant)
    grant.add_argument("--player", required=True, help="玩家 id 或存档名")
    grant.add_argument("--degree", required=True, help="称号 id 或 string_id")
    grant.add_argument("--wear", action="store_true", help="同时设为佩戴中")
    grant.add_argument("--allow-unpublished", action="store_true",
                       help="允许授予尚未发布到链上的称号(客户端会崩,默认拒绝)")
    grant.add_argument("--db", help="存档库路径(默认 <repo>/.database/wdfp_data.db)")
    grant.set_defaults(func=cmd_grant)

    revoke = sub.add_parser("revoke", help="从玩家存档收回")
    revoke.add_argument("--dry-run", action="store_true")
    revoke.add_argument("--player", required=True)
    revoke.add_argument("--degree", required=True, help="称号 id")
    revoke.add_argument("--db")
    revoke.set_defaults(func=cmd_revoke)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except DegreeError as error:
        print(f"错误: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
