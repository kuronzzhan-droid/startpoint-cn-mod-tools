"""立绘替换 → 裁剪模板 → 派生 UI 图（只写草稿）。

派生直接复用生产代码 ``wf.chars.support.images``（万圣/季节批次用的同一套
``make_icons`` / ``make_cutin``）：每组图标的裁剪框 = 以脸锚为参照、高度
``squareHeight × factor``、按本组主槽宽高比、脸锚落在框内 ``anchor`` 处；带形状
的槽再与官方统计蒙版取 min。编辑台只是把这些参数做成可拖动的框。

蒙版来自当前视图中「官方原版」角色同名图标 alpha 的逐像素中位数（和
``wf.chars.support.masks`` 同口径），首次使用时统计并缓存在草稿目录。
"""
from __future__ import annotations

import io
import json
import threading
from pathlib import Path

import numpy as np
from PIL import Image

import wf_assets
import wf_atf
import wf_dsl
import wf_mod_tool as core
import wf_ui_derive_gate as gate
from wf.chars.support import images

from .drafts import DraftError, sha256
from .deliver_media import read_root

FULL_SHOT = "ui/full_shot_1440_1920_{form}.png"
CUTIN = "ui/skill_cutin_{form}.png"
CUTIN_ATF = "ui/skill_cutin_{form}.atf.deflate"
SHEET = "ui/illustration_setting_sprite_sheet.png"
SHEET_ATLAS = "ui/illustration_setting_sprite_sheet.atlas.amf3.deflate"
CANVAS = 2000
FACE_TARGET = (1000, 509)  # 官方 face 中位（memory: wf-illustration-slot-system）

# 组名 = 该组主槽；成员与默认 (fx, fy, factor) 来自 images.GROUPS（生产值）。
GROUPS = {slots[0]: {"slots": list(slots), "anchor": [fx, fy], "factor": factor}
          for slots, (fx, fy, factor) in images.GROUPS}
GROUP_LABEL = {
    "square": "方形头像（square / 132 / 圆角 136 / 圆角 95）",
    "thumb_level_up": "升级卡 / 合击卡（thumb_level_up / thumb_party_unison）",
    "battle_member_status": "战斗状态圆头像（battle_member_status）",
    "battle_control_board": "技能准备竖条（battle_control_board）",
    "cutin_skill_chain": "技能连锁六边形（cutin_skill_chain）",
    "thumb_party_main": "队伍主位卡（thumb_party_main）",
}
SHAPE_LABEL = {
    "square_round_136_136": "圆角方", "square_round_95_95": "圆角方", "battle_member_status": "圆形",
    "battle_control_board": "竖圆角条", "cutin_skill_chain": "六边形",
    "thumb_level_up": "极小圆角", "thumb_party_main": "极小圆角", "thumb_party_unison": "极小圆角",
}
SLOT_USE = {
    "square": "抽卡结果/礼物/登录奖励", "square_132_132": "首页/图鉴",
    "square_round_136_136": "战斗内", "square_round_95_95": "战斗内",
    "battle_member_status": "战斗状态条", "battle_control_board": "技能准备",
    "cutin_skill_chain": "技能连锁", "thumb_level_up": "升级", "thumb_party_main": "队伍主位",
    "thumb_party_unison": "队伍合击位", "skill_cutin": "技能发动（真机读 ATF）",
}
# 元素 → 图标底色（径向渐变 内/外）。只是默认值，可在模板里改。
BACKDROPS = {
    "火": ([139, 68, 53], [51, 29, 42]), "水": ([52, 104, 150], [24, 33, 60]),
    "雷": ([150, 128, 52], [52, 40, 30]), "风": ([63, 132, 107], [27, 42, 57]),
    "光": ([170, 150, 110], [70, 60, 60]), "暗": ([115, 86, 144], [34, 30, 55]),
}
MASK_SAMPLE = 60


def decode_png(raw: bytes) -> Image.Image:
    image = Image.open(io.BytesIO(wf_assets.png_decode(raw)))
    image.load()
    return image


def png_bytes(image: Image.Image) -> bytes:
    out = io.BytesIO()
    image.save(out, "PNG", optimize=True)
    return out.getvalue()


def trim_transparent(image: Image.Image) -> tuple[Image.Image, list[int]]:
    """Remove only fully transparent borders; return the trimmed image and its box."""
    rgba = image.convert("RGBA")
    box = rgba.getchannel("A").getbbox()
    if box is None:
        raise DraftError("立绘全透明：没有可见像素")
    return rgba.crop(box), list(box)


def suggested_backdrop(element: str) -> dict:
    inner, outer = BACKDROPS.get(element, ([110, 110, 130], [40, 40, 55]))
    return {"inner": inner, "outer": outer}


def default_template(image: Image.Image, face: list[float] | None, element: str = "") -> dict:
    width, height = image.size
    if face is None:
        # 官方脸相对内容框中位 (0.502, 0.187)；只是起点，必须在编辑器里拖到两眼中点。
        face = [round(width * 0.502), round(height * 0.187)]
    square = round(height * 0.24, 1)
    head = square / 1.25
    return {
        "face": [round(float(face[0]), 1), round(float(face[1]), 1)],
        "squareHeight": square,
        "groups": {name: {"anchor": list(spec["anchor"]), "factor": spec["factor"]} for name, spec in GROUPS.items()},
        "cutin": {"center": [round(float(face[0]), 1), round(float(face[1]), 1)],
                  "height": round(512 * head / 207, 1), "anchor": [0.51, 0.44]},
        # 官方图标是透明底；元素渐变只作为作者手动打开底色时的起始色。
        "backdrop": None,
    }


def table_rows(size: tuple[int, int], face: list[float]) -> dict:
    """三张定位表的目标行（反推公式 + 夹紧，face 写真值）。草稿不写表，只记意图。"""
    width, height = size
    x = int(min(max(0, round(FACE_TARGET[0] - face[0])), CANVAS - width))
    y = int(min(max(0, round(FACE_TARGET[1] - face[1])), CANVAS - height))
    face_x, face_y = round(x + face[0]), round(y + face[1])
    return {"character_image": f"{x},{y},{width},{height}",
            "trimmed_image": f"{x},{y},{CANVAS},{CANVAS}",
            "full_shot_image_attribute": f"1000,1000,1,{face_x},{face_y}",
            "clamped": (x + face[0], y + face[1]) != (FACE_TARGET[0], FACE_TARGET[1])}


class PortraitService:
    def __init__(self, source, assets, store):
        self.source, self.assets, self.store = source, assets, store
        self._mask_lock = threading.Lock()
        self._masks: dict[str, np.ndarray] | None = None
        self.mask_meta: dict | None = None

    # -- geometry tables ------------------------------------------------
    def _nested(self, logical: str, key: str) -> dict:
        raw = self.source.raw(logical)
        if raw is None:
            return {}
        outer = core.read_orderedmap_raw_rows_from_bytes(raw, logical)
        for k, v in zip(outer.keys, outer.rows):
            if k == key:
                return core.read_orderedmap_file_from_bytes(v)
        return {}

    def current_geometry(self, cid: str, form: str) -> dict:
        image_row = self._nested("master/generated/character_image.orderedmap", cid).get(form)
        attr_row = self._nested("master/character/full_shot_image_attribute.orderedmap", cid).get(form)
        result = {"characterImage": image_row, "fullShotAttribute": attr_row, "face": None}
        try:
            x, y = (int(v) for v in image_row.split(",")[:2])
            face_x, face_y = (float(v) for v in attr_row.split(",")[3:5])
            result["face"] = [face_x - x, face_y - y]
        except (AttributeError, ValueError):
            pass
        return result

    # -- masks ----------------------------------------------------------
    def masks(self, official_codes: list[str]) -> dict[str, np.ndarray]:
        with self._mask_lock:
            if self._masks is not None:
                return self._masks
            cache = self.store.root / "_cache" / "official-shape-masks.npz"
            meta_path = cache.with_suffix(".json")
            if cache.is_file() and meta_path.is_file():
                meta = json.loads(meta_path.read_text("utf-8"))
                if meta.get("sha256") == sha256(cache.read_bytes()):
                    data = np.load(cache)
                    self._masks = {slot: data[slot] for slot in gate.SHAPE_SLOTS}
                    self.mask_meta = meta
                    return self._masks
            samples: dict[str, list[np.ndarray]] = {slot: [] for slot in gate.SHAPE_SLOTS}
            used = 0
            for code in official_codes:
                if min(len(v) for v in samples.values()) >= MASK_SAMPLE * 2:
                    break
                hit = False
                for slot in gate.SHAPE_SLOTS:
                    for level in ("0", "1"):
                        raw = self.assets.read(f"character/{code}/ui/{slot}_{level}.png")
                        if raw is None:
                            continue
                        alpha = np.asarray(decode_png(raw).convert("RGBA"))[:, :, 3]
                        if alpha.shape[::-1] == gate.OFFICIAL_ICON_SIZES[slot]:
                            samples[slot].append(alpha)
                            hit = True
                used += hit
            masks = {}
            for slot, stack in samples.items():
                if len(stack) < 16:
                    raise DraftError(f"官方样本不足，无法统计形状蒙版：{slot} 只有 {len(stack)} 张")
                masks[slot] = np.median(np.stack(stack), axis=0).astype(np.uint8)
            cache.parent.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(cache, **masks)
            meta = {"method": "当前视图「官方原版」角色同名图标 alpha 逐像素中位数（_0+_1 合并）",
                    "characters": used, "samples": {k: len(v) for k, v in samples.items()},
                    "sha256": sha256(cache.read_bytes())}
            meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1), "utf-8")
            self._masks, self.mask_meta = masks, meta
            return masks

    def mask_png(self, slot: str, official_codes: list[str]) -> bytes:
        if slot not in gate.SHAPE_SLOTS:
            raise DraftError(f"{slot} 没有形状蒙版")
        alpha = self.masks(official_codes)[slot]
        rgba = np.zeros((*alpha.shape, 4), np.uint8)
        rgba[:, :, :3] = 255
        rgba[:, :, 3] = alpha
        return png_bytes(Image.fromarray(rgba, "RGBA"))

    # -- sources --------------------------------------------------------
    def view_full_shot(self, code: str, form: str) -> tuple[Image.Image, bytes] | None:
        raw = read_root(self.source, "medium", f"character/{code}/" + FULL_SHOT.format(form=form))
        return (decode_png(raw), raw) if raw is not None else None

    def upload_source(self, cid: str, form: str, png: bytes) -> dict:
        try:
            image = Image.open(io.BytesIO(png))
            image.load()
        except Exception as exc:  # noqa: BLE001
            raise DraftError(f"不是可读的 PNG：{exc}") from None
        if image.format != "PNG":
            raise DraftError(f"需要 PNG，收到 {image.format}")
        if max(image.size) > 8192:
            raise DraftError(f"图片过大：{image.size[0]}×{image.size[1]}")
        original = image.size
        trimmed, box = trim_transparent(image)
        relative = f"sources/portrait_{form}.png"
        self.store.write_file(cid, relative, png_bytes(trimmed))
        meta = {"originalSize": list(original), "trim": box, "size": list(trimmed.size),
                "hasAlpha": image.mode in ("RGBA", "LA") or "transparency" in image.info}
        self.store.write_file(cid, f"sources/portrait_{form}.json", json.dumps(meta).encode("utf-8"))
        return {"file": relative, **meta}

    def current_backdrop(self, code: str, form: str) -> tuple[bool, dict | None]:
        """Sample the backdrop of the character's existing square icon.

        Returns (found, backdrop). backdrop is None when the existing icon has a
        transparent background, so a recrop keeps the game's current look instead
        of a synthetic element gradient.
        """
        logical = f"character/{code}/ui/square_{form}.png"
        raw = None
        for root in ("medium", "common"):
            raw = read_root(self.source, root, logical)
            if raw is not None:
                break
        if raw is None:
            return False, None
        icon = decode_png(raw).convert("RGBA")
        pixels = np.asarray(icon, dtype=np.float64)
        h, w = pixels.shape[:2]
        band = max(2, round(min(w, h) * 0.06))
        ring = np.concatenate([pixels[:band].reshape(-1, 4), pixels[-band:].reshape(-1, 4),
                               pixels[:, :band].reshape(-1, 4), pixels[:, -band:].reshape(-1, 4)])
        # Official icons are cut out on a transparent canvas; the character only
        # touches some edges, so any real share of transparent border pixels means
        # the icon has no painted backdrop.
        if (ring[:, 3] < 128).mean() > 0.05:
            return True, None
        # The radial template is lighter in the middle; sample the top-centre strip
        # (usually background above the head) for inner and the corners for outer.
        top = pixels[:band, w // 3: 2 * w // 3].reshape(-1, 4)
        c = band * 2
        corners = np.concatenate([pixels[:c, :c].reshape(-1, 4), pixels[:c, -c:].reshape(-1, 4),
                                  pixels[-c:, :c].reshape(-1, 4), pixels[-c:, -c:].reshape(-1, 4)])
        def mean_rgb(block):
            opaque = block[block[:, 3] >= 128]
            return [int(round(v)) for v in (opaque if len(opaque) else block)[:, :3].mean(axis=0)]
        return True, {"inner": mean_rgb(top), "outer": mean_rgb(corners)}

    def source_info(self, cid: str, code: str, form: str, element: str) -> dict:
        geometry = self.current_geometry(cid, form)
        found, backdrop = self.current_backdrop(code, form)
        current = self.view_full_shot(code, form)
        info = {"form": form, "geometry": geometry, "current": None, "upload": None}
        if current is not None:
            image, trim = trim_transparent(current[0])
            face = None
            if geometry["face"] is not None:
                face = [geometry["face"][0] - trim[0], geometry["face"][1] - trim[1]]
            info["current"] = {"path": f"character/{code}/" + FULL_SHOT.format(form=form),
                               "size": list(image.size), "originalSize": list(current[0].size), "trim": trim,
                               "template": default_template(image, face, element)}
            info["current"]["suggestedBackdrop"] = suggested_backdrop(element)
            if found:
                info["current"]["template"]["backdrop"] = backdrop
                if backdrop is not None:
                    info["current"]["currentBackdrop"] = backdrop
                info["current"]["backdropSource"] = "取自现有 square 图标" if backdrop else "现有图标是透明底"
        uploaded = self.store.read_file(cid, f"sources/portrait_{form}.png")
        if uploaded is not None:
            meta_raw = self.store.read_file(cid, f"sources/portrait_{form}.json")
            meta = json.loads(meta_raw) if meta_raw else {}
            image = decode_png(uploaded)
            info["upload"] = {"file": f"sources/portrait_{form}.png", "size": list(image.size), **meta,
                              "template": default_template(image, None, element)}
            info["upload"]["suggestedBackdrop"] = suggested_backdrop(element)
            # A new portrait starts transparent like official icons: the existing icon's
            # painted backdrop belongs to the old art (for a clone, the parent's), so it is
            # only offered, never applied silently over the new art's transparent areas.
            info["upload"]["backdropSource"] = "透明底（官方做法）"
            if found and backdrop is not None:
                info["upload"]["currentBackdrop"] = backdrop
        return info

    # -- render ---------------------------------------------------------
    def render(self, master: Image.Image, template: dict, masks: dict, role: str) -> dict[str, Image.Image]:
        landmarks = {
            "face": template["face"], "eyes": template["face"],
            "square_height": template["squareHeight"],
            "icon_anchors": {name: tuple(spec["anchor"]) for name, spec in template["groups"].items()},
            "icon_factors": {name: float(spec["factor"]) for name, spec in template["groups"].items()},
            "transparent_icon_background": template["backdrop"] is None,
            "cutin_framing": {"center": template["cutin"]["center"], "height": template["cutin"]["height"],
                              "anchor": tuple(template["cutin"]["anchor"])},
        }
        if template["backdrop"] is not None:
            images.COLORS[role] = (tuple(template["backdrop"]["inner"]), tuple(template["backdrop"]["outer"]))
        icons = images.make_icons(master.convert("RGBA"), landmarks, masks, role)
        icons["skill_cutin"] = images.make_cutin(master.convert("RGBA"), landmarks)
        return icons

    def rebuild_sheet(self, code: str, form: str, full: Image.Image) -> Image.Image | None:
        """Redraw only this form's cells of illustration_setting_sprite_sheet (approximate fit)."""
        prefix = f"character/{code}/"
        raw_sheet = read_root(self.source, "medium", prefix + SHEET)
        raw_atlas = read_root(self.source, "common", prefix + SHEET_ATLAS)
        if raw_sheet is None or raw_atlas is None:
            return None
        sheet = decode_png(raw_sheet).convert("RGBA")
        atlas = wf_dsl.parse_dsl(wf_atf.inflate(raw_atlas))["tree"]
        touched = False
        for item in atlas:
            if not str(item.get("n", "")).endswith("_" + form):
                continue
            rotated = bool(item.get("r", False))
            size = (item["h"], item["w"]) if rotated else (item["w"], item["h"])
            tile = images.fit_rgba(full, size)
            if rotated:
                tile = tile.transpose(Image.Transpose.ROTATE_270)
            box = (item["x"], item["y"], item["x"] + tile.width, item["y"] + tile.height)
            sheet.paste(Image.new("RGBA", tile.size), box)
            sheet.alpha_composite(tile, (item["x"], item["y"]))
            touched = True
        return sheet if touched else None

    def build_change(self, *, cid: str, code: str, element: str, request: dict,
                     official_codes: list[str], make_file) -> dict:
        form = request["form"]
        template = request["template"]
        source_kind = request.get("source", "upload")
        prefix = f"character/{code}/"
        checks: list[dict] = []
        if source_kind == "upload":
            raw = self.store.read_file(cid, f"sources/portrait_{form}.png")
            if raw is None:
                raise DraftError("还没有上传这个立绘槽的新 PNG")
            master = decode_png(raw).convert("RGBA")
            meta_raw = self.store.read_file(cid, f"sources/portrait_{form}.json")
            meta = json.loads(meta_raw) if meta_raw else {}
            trim = meta.get("trim", [0, 0, *master.size])
            source_size = meta.get("originalSize", list(master.size))
        else:
            found = self.view_full_shot(code, form)
            if found is None:
                raise DraftError("当前视图里没有这个立绘")
            master, trim = trim_transparent(found[0])
            source_size = list(found[0].size)
        width, height = master.size
        face = template["face"]
        if not (0 <= face[0] < width and 0 <= face[1] < height):
            raise DraftError("脸锚在立绘之外")
        if width > CANVAS or height > CANVAS:
            raise DraftError(f"立绘 {width}×{height} 超过虚拟画布 {CANVAS}×{CANVAS}（官方宽 ≤1936、高 ≤1920）")
        alpha = np.asarray(master.getchannel("A"))
        opaque = float((alpha > 8).mean())
        corners = [alpha[0, 0], alpha[0, -1], alpha[-1, 0], alpha[-1, -1]]
        if source_kind == "upload" and max(corners) > 0 and opaque > 0.95:
            checks.append({"level": "warn", "code": "portrait.not_matted",
                           "message": "立绘没有透明背景：官方 full_shot 是透明抠图（四角 alpha=0），满幅图在主城会显示成矩形贴片"})
        if not 0.25 <= opaque <= 0.70:
            checks.append({"level": "info", "code": "portrait.coverage",
                           "message": f"不透明占比 {opaque:.2f}，官方约 0.27–0.66（不是门禁项）"})
        masks = self.masks(official_codes)
        icons = self.render(master, template, masks, role=f"studio:{cid}")
        from .icon_alpha import inspect_icons
        for item in inspect_icons(master, template, icons, masks, form=form):
            if item["status"] != "ok":
                checks.append({"level": item["level"], "code": "portrait.icon_alpha",
                               "message": item["code"] + "：" + item["message"]})
        for problem in gate.derived_icon_problems(icons, masks, level=form):
            checks.append({"level": "warn", "code": "portrait.icon_gate", "message": problem})
        files = []
        if source_kind == "upload":
            files.append(make_file(prefix + FULL_SHOT.format(form=form), "medium", png_bytes(master), "png",
                                   approximate=False, note="上传立绘去掉全透明边后原样使用"))
        else:
            files.append(make_file(prefix + FULL_SHOT.format(form=form), "medium", wf_assets.png_decode(found[1]),
                                   "png", approximate=False, note="重裁图标时保留原 full_shot 字节及其基线断言"))
        for slot, image in icons.items():
            logical = prefix + f"ui/{slot}_{form}.png"
            files.append(make_file(logical, "medium", png_bytes(image), "png", approximate=True,
                                   note=f"{SLOT_USE.get(slot, '')}；生产派生 make_icons/make_cutin，取景为模板参数"))
        if request.get("atf", True):
            atf_logical = prefix + CUTIN_ATF.format(form=form)
            ref = read_root(self.source, "android", atf_logical)
            try:
                atf = wf_atf.deflate(wf_atf.build_cutin_atf(png_bytes(icons["skill_cutin"]),
                                                            wf_atf.inflate(ref) if ref else None))
                files.append(make_file(atf_logical, "android", atf, "atf-deflate", approximate=False,
                                       note="wf_atf ETC1 重编（与 GUI replace_asset 同一编码器）；本草稿未上真机"))
            except ValueError as exc:
                checks.append({"level": "error", "code": "portrait.atf_failed", "message": f"ATF 重编失败：{exc}"})
        else:
            checks.append({"level": "warn", "code": "portrait.atf_skipped",
                           "message": "未重编 skill_cutin ATF：真机战斗只读安卓根 ATF，不读 PNG，换了 PNG 技能发动画面不会变"})
        sheet = self.rebuild_sheet(code, form, master)
        if sheet is not None:
            # Both forms share one texture. Compile it once from both form drafts
            # at delivery time, instead of letting the second save overwrite the
            # first change's source file and invalidate its recorded hash.
            checks.append({"level": "info", "code": "portrait.sheet_approx",
                           "message": "生成时统一合成两个立绘槽的 illustration_setting_sprite_sheet；本槽按 fit 整图重画，"
                                      "官方是按海报构图重裁（zoom≈0.95），属近似"})
        else:
            checks.append({"level": "warn", "code": "portrait.sheet_missing",
                           "message": "当前视图没有 illustration_setting_sprite_sheet：立绘切换界面需要它，生成时必须补"})
        attr_logical = "master/character/full_shot_image_attribute.orderedmap"
        if source_kind == "upload":
            rows = table_rows((width, height), face)
            if rows.pop("clamped"):
                checks.append({"level": "info", "code": "portrait.face_clamped",
                               "message": "脸锚无法对到 (1000,509)，已按画布夹紧并写真值（概览页取景会偏）"})
            pending = [
                {"logical": "master/generated/character_image.orderedmap", "reason": f"{cid}/{form} 行",
                 "value": rows["character_image"]},
                {"logical": "master/generated/trimmed_image.orderedmap",
                 "reason": f"{prefix}{FULL_SHOT.format(form=form)[:-4]} 行", "value": rows["trimmed_image"]},
                {"logical": attr_logical, "reason": f"{cid}/{form} 行", "value": rows["full_shot_image_attribute"]},
            ]
        else:
            # 立绘不变：定位表 x,y 不动；只有脸锚变了才改 faceX/faceY（写真值）。
            geometry = self.current_geometry(cid, form)
            rows, pending = {"character_image": geometry["characterImage"],
                             "full_shot_image_attribute": geometry["fullShotAttribute"]}, []
            try:
                x, y = (int(v) for v in geometry["characterImage"].split(",")[:2])
                x, y = x - trim[0], y - trim[1]
                value = f"1000,1000,1,{round(x + face[0])},{round(y + face[1])}"
                if value != geometry["fullShotAttribute"]:
                    rows["full_shot_image_attribute"] = value
                    pending.append({"logical": attr_logical, "reason": f"{cid}/{form} 行（脸锚移动）", "value": value})
            except (AttributeError, ValueError):
                checks.append({"level": "warn", "code": "portrait.geometry_missing",
                               "message": "当前视图缺 character_image 行，无法换算脸锚"})
        params = {"source": source_kind, "template": template, "sourceSize": [int(v) for v in source_size],
                  "trim": [int(v) for v in trim], "tableRows": rows, "atf": bool(request.get("atf", True))}
        from .deliver_portrait import snapshot_geometry
        params["tableBefore"] = snapshot_geometry(self.source, cid, code, form)
        if source_kind == "upload":
            params["sourceFile"] = f"sources/portrait_{form}.png"
        return {"target": {"form": form}, "params": params, "files": files, "pending": pending, "checks": checks,
                "title": f"立绘 _{form}（{'新立绘' if source_kind == 'upload' else '重新裁剪'}）"}
