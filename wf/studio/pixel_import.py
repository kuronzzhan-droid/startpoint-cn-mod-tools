"""像素小人：按动作槽导入新帧（只写草稿，不重排游戏图集）。

草稿保存的是「源帧 + 每帧停留帧数 + 每帧锚点」。真正写回
``sprite_sheet.png / .atlas / .timeline`` 要重新装箱并改时间轴帧号，属于
「生成」（wf deliver），这里只做能在草稿阶段判定的检查：

* 帧尺寸不能超过该族帧框（官方 256×256）；必须有透明背景；
* 总时长与原动作不一致 → 生成时要平移后续动作帧号（客户端有按固定帧号取图的
  动作，例如 kachidoki 读 begin+18），提示；
* 图集预算：把本族其它动作的帧（裁空白后）与新帧一起，用客户端 MaxRects 打包器
  的 1:1 移植（``wf_atlas_budget_check.pack``）估算新 sprite_sheet 尺寸，再折算
  战斗 layer0（4096²，margin 2）占用。special 族战斗不加载，只报尺寸。
"""
from __future__ import annotations

import base64
import binascii
import io
from bisect import bisect_left

from PIL import Image

import wf_atlas_budget_check as budget
from wf_pixelart_vfx import frame_index, restore_frame

from .drafts import DraftError
from .pixels import FAMILIES, _family

OFFICIAL_SHEET_MAX_PX = 247 * 738        # fox_oracle，官方最大 sprite_sheet
OFFICIAL_CHAR_SHARE_MAX = 1.09           # 官方角色 layer0 占用最大 %
OFFICIAL_CHAR_SHARE_MEDIAN = 0.17        # 官方角色 layer0 占用中位 %


def decode_frame(text: str, index: int) -> Image.Image:
    try:
        raw = base64.b64decode(text, validate=True)
        image = Image.open(io.BytesIO(raw))
        image.load()
    except (binascii.Error, ValueError, OSError) as exc:
        raise DraftError(f"第 {index + 1} 帧不是可读的 PNG：{exc}") from None
    if image.format != "PNG":
        raise DraftError(f"第 {index + 1} 帧需要 PNG")
    return image.convert("RGBA")


def split_sheet(sheet: Image.Image, columns: int, rows: int, count: int | None = None) -> list[Image.Image]:
    if columns < 1 or rows < 1:
        raise DraftError("网格行列必须 ≥ 1")
    if sheet.width % columns or sheet.height % rows:
        raise DraftError(f"精灵图 {sheet.width}×{sheet.height} 不能被 {columns}×{rows} 整除")
    cw, ch = sheet.width // columns, sheet.height // rows
    frames = [sheet.crop((c * cw, r * ch, c * cw + cw, r * ch + ch)).convert("RGBA")
              for r in range(rows) for c in range(columns)]
    if count:
        frames = frames[:count]
    return [f for f in frames if f.getbbox()] if count is None else frames


def default_anchor(frames: list[Image.Image]) -> list[int]:
    """脚底锚 = 帧宽中心、逐帧可见底边的中位数（别用全局最低点）。"""
    bottoms = sorted(f.getchannel("A").getbbox()[3] for f in frames if f.getchannel("A").getbbox())
    bottom = bottoms[len(bottoms) // 2] if bottoms else frames[0].height
    return [frames[0].width // 2, bottom]


class PixelImporter:
    def __init__(self, source):
        self.source = source

    def family_frames(self, code: str, family: str):
        stem, sheet = next(((s, sh) for s, sh, _ in FAMILIES if s == family), (None, None))
        if stem is None:
            raise DraftError(f"未知像素族：{family}")
        loaded = _family(self.source, code, stem, sheet)
        if loaded is None:
            return None
        image, frame, (keys, entries), timeline = loaded
        return {"image": image, "frame": frame, "keys": keys, "entries": entries, "timeline": timeline,
                "sheet": f"character/{code}/pixelart/{sheet}.png"}

    def check(self, code: str, family: str, action: str, frames: list[Image.Image], durations: list[int]) -> dict:
        data = self.family_frames(code, family)
        checks: list[dict] = []
        if data is None:
            raise DraftError(f"这个角色没有 {family} 像素族，不能按动作槽替换（新建像素族属于 M6 建角色）")
        frame = data["frame"]
        sequences = {s.get("name"): s for s in data["timeline"].get("sequences", [])}
        sequence = sequences.get(action)
        box_w, box_h = 256, 256
        first = data["entries"][data["keys"][0]]
        box_w, box_h = int(first.get("fw", first["w"])), int(first.get("fh", first["h"]))
        original_total = None
        if sequence is None:
            checks.append({"level": "warn", "code": "pixel.new_slot",
                           "message": f"原图集没有 {action} 动作：生成时要新增时间轴序列，客户端是否读取以动作槽表为准"})
        else:
            original_total = sequence["end"] - sequence["begin"] + 1
        total = sum(durations)
        if original_total is not None and total != original_total:
            checks.append({"level": "warn", "code": "pixel.duration_changed",
                           "message": f"总时长 {total} 帧 ≠ 原动作 {original_total} 帧：生成时要平移后续动作的帧号"
                                      "（客户端按固定帧号取图的动作，如 kachidoki 读 begin+18，需要复核）"})
        for i, image in enumerate(frames):
            if image.width > box_w or image.height > box_h:
                checks.append({"level": "error", "code": "pixel.frame_too_large",
                               "message": f"第 {i + 1} 帧 {image.width}×{image.height} 超过帧框 {box_w}×{box_h}"})
            alpha = image.getchannel("A")
            if alpha.getextrema()[0] == 255:
                checks.append({"level": "error", "code": "pixel.no_alpha",
                               "message": f"第 {i + 1} 帧没有透明背景"})
            elif alpha.getbbox() is None:
                checks.append({"level": "warn", "code": "pixel.empty_frame", "message": f"第 {i + 1} 帧全透明"})
        sizes = {f.size for f in frames}
        if len(sizes) > 1:
            checks.append({"level": "info", "code": "pixel.mixed_sizes",
                           "message": "各帧尺寸不同：锚点逐帧对齐，请逐帧核对脚底"})

        # Original visible size of this action, for a scale sanity check.
        keys, entries = data["keys"], data["entries"]
        def used_keys(seq) -> set[int]:
            return {keys[bisect_left(keys, pos)] for pos in range(seq["begin"], seq["end"] + 1)
                    if pos <= keys[-1]}
        action_keys = used_keys(sequence) if sequence is not None else set()
        for name, other in sequences.items():
            if name != action and isinstance(other.get("begin"), int) and isinstance(other.get("end"), int):
                action_keys -= used_keys(other)
        def visible(entry):
            return int(entry["h"] if entry.get("r") else entry["w"]), int(entry["w"] if entry.get("r") else entry["h"])
        own = used_keys(sequence) if sequence is not None else set()
        old_h = max((visible(entries[k])[1] for k in own), default=0)
        new_boxes = [f.getbbox() for f in frames if f.getbbox()]
        new_h = max((b[3] - b[1] for b in new_boxes), default=0)
        if old_h and new_h > old_h * 1.6:
            checks.append({"level": "warn", "code": "pixel.scale",
                           "message": f"新帧可见高度 {new_h}px，原动作 {old_h}px：像素小人约 1.6 倍以上，检查是否放大了"})

        # Budget: other actions' distinct atlas regions + new trimmed frames.
        items, seen = [], set()
        for key in keys:
            if key in action_keys:
                continue
            entry = entries[key]
            region = (entry["x"], entry["y"], entry["w"], entry["h"])
            if region in seen:
                continue
            seen.add(region)
            items.append((f"old{key}", int(entry["w"]), int(entry["h"])))
        for i, box in enumerate(new_boxes):
            items.append((f"new{i}", box[2] - box[0], box[3] - box[1]))
        current = data["image"].size
        estimate, failure = None, None
        widest = max((max(w, h) for _, w, h in items), default=1)
        for width in (128, 256, 384, 512, 768, 1024, 2048):
            if width < min(widest, 2048):
                continue
            try:
                used = budget.pack(items, width, 4096, margin=1)
            except budget.Overflow as exc:
                failure = exc
                continue
            if estimate is None or used[0] * used[1] < estimate["width"] * estimate["height"]:
                estimate = {"width": used[0], "height": used[1]}
        if estimate is None:
            checks.append({"level": "error", "code": "pixel.sheet_overflow",
                           "message": f"装不进 2048×4096 精灵图：{failure}"})
        battle = family == "pixelart"
        result = {"current": {"width": current[0], "height": current[1],
                              "share": round(budget.rect_area(current) / budget.CAPACITY * 100, 3)},
                  "estimate": None, "loadedInBattle": battle, "officialShareMax": OFFICIAL_CHAR_SHARE_MAX,
                  "officialShareMedian": OFFICIAL_CHAR_SHARE_MEDIAN, "officialSheetMaxPx": OFFICIAL_SHEET_MAX_PX,
                  "method": "客户端 MaxRects 移植（wf_atlas_budget_check.pack）装箱：其它动作原区域 + 新帧裁空白后；"
                            "生成时由 wf deliver 实际打包，这里是估算"}
        if estimate:
            share = budget.rect_area((estimate["width"], estimate["height"])) / budget.CAPACITY * 100
            estimate["share"] = round(share, 3)
            estimate["px"] = estimate["width"] * estimate["height"]
            result["estimate"] = estimate
            if battle and share > OFFICIAL_CHAR_SHARE_MAX:
                checks.append({"level": "warn", "code": "pixel.atlas_budget",
                               "message": f"新 sprite_sheet 约 {estimate['width']}×{estimate['height']}，占战斗 layer0 "
                                          f"{share:.2f}%（官方角色最大 {OFFICIAL_CHAR_SHARE_MAX}%）：三人房易触发 U_1d93f4"})
            if battle and estimate["px"] > OFFICIAL_SHEET_MAX_PX:
                checks.append({"level": "warn", "code": "pixel.sheet_size",
                               "message": f"超过官方最大 sprite_sheet 面积（247×738）"})
        if not battle:
            checks.append({"level": "info", "code": "pixel.special_not_in_battle",
                           "message": "special 族只在扭蛋/角色菜单用，战斗不加载，不占 layer0"})
        return {"checks": checks, "budget": result, "originalTotalFrames": original_total,
                "frameBox": [box_w, box_h], "anchorOrigin": [-int(frame.get("x", 0)), -int(frame.get("y", 0))]}
