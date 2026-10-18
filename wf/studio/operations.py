"""Draft operations shared by the HTTP API and ``python -m wf.studio.draft``.

Inputs are the JSON request bodies described in
``schemas/studio-draft.schema.json`` (``portraitRequest`` / ``pixelRequest`` /
``voiceRequest``); every resulting change is schema-validated by
:class:`~wf.studio.drafts.DraftStore` before it is written.
"""
from __future__ import annotations

import base64
import binascii
import io
import re

import wf_assets
import wf_ui_derive_gate as _gate

from . import voice as voice_mod
from .assets import AssetIndex
from .characters import list_characters
from .drafts import DraftError, DraftStore, new_change_id, now, sha256, status, validate
from .pixel_import import PixelImporter, decode_frame
from .portrait import GROUP_LABEL as GROUP_LABELS, GROUPS as GROUP_SPECS, SHAPE_LABEL as SHAPE_LABELS
from .portrait import SLOT_USE as SLOT_USES, PortraitService

ROOT_DIR = {"common": "common", "medium": "medium", "android": "android"}
_VOICE = re.compile(r"^[a-z0-9_]+(/[a-z0-9_]+)+$")


def b64(text: str, what: str) -> bytes:
    try:
        return base64.b64decode(text, validate=True)
    except (binascii.Error, ValueError, TypeError):
        raise DraftError(f"{what} 不是合法的 base64") from None


class DraftOps:
    def __init__(self, source, *, store: DraftStore | None = None, assets: AssetIndex | None = None,
                 characters=None):
        self.source = source
        self.store = store or DraftStore()
        self.assets = assets or AssetIndex(source)
        self._characters = characters
        self.portraits = PortraitService(source, self.assets, self.store)
        self.pixels = PixelImporter(source)

    # -- character identity -------------------------------------------
    def character_list(self) -> list[dict]:
        if callable(self._characters):
            return self._characters()
        if self._characters is None:
            self._characters = list_characters(self.source)
        return self._characters

    def character(self, cid: str) -> dict:
        rows = self.source.table("character").get(cid)
        if not rows or not rows[0]:
            raise DraftError(f"角色 {cid} 不在当前视图")
        summary = next((c for c in self.character_list() if c["id"] == cid), {})
        return {"id": cid, "code": rows[0][0], "element": summary.get("element", ""),
                "name": summary.get("name", "")}

    def official_codes(self) -> list[str]:
        items = self.character_list()
        codes = [c["code"] for c in items if c.get("origin") == "official"]
        return codes or [c["code"] for c in items]

    # -- helpers ----------------------------------------------------------
    def _file_maker(self, cid: str):
        def make(logical: str, root: str, data: bytes, encoding: str, *, approximate: bool, note: str = "") -> dict:
            relative = f"files/{ROOT_DIR[root]}/{logical}"
            self.store.write_file(cid, relative, data)
            from .deliver_media import read_root
            base_raw = read_root(self.source, root, logical)
            entry = {"logical": logical, "root": root, "draft": relative, "sha256": sha256(data), "size": len(data),
                     "encoding": encoding,
                     "base": {"sha256": sha256(base_raw) if base_raw is not None else None,
                              "layer": self.assets.locate(logical)},
                     "approximate": approximate}
            if encoding == "png":
                entry["storeSha256"] = sha256(wf_assets.png_encode(data))
            elif encoding == "mp3":
                entry["storeSha256"] = sha256(wf_assets.mp3_encode(data))
            if note:
                entry["note"] = note
            return entry
        return make

    def _commit(self, cid: str, code: str, kind: str, built: dict) -> dict:
        change = {"id": new_change_id(), "kind": kind, "title": built["title"], "createdAt": now(),
                  "target": built["target"], "params": built["params"], "files": built["files"],
                  "pending": built["pending"], "checks": built["checks"]}
        changeset = self.store.put_change(cid, code, self.source.version, change)
        return {"change": change, "changeset": changeset, "status": status(changeset)}

    # -- read -----------------------------------------------------------
    def draft(self, cid: str) -> dict:
        changeset = self.store.load(cid)
        return {"characterId": cid, "changeset": changeset, "status": status(changeset),
                "actions": ACTIONS}

    # -- portrait -------------------------------------------------------
    def portrait_info(self, cid: str, form: str) -> dict:
        info = self.character(cid)
        result = self.portraits.source_info(cid, info["code"], form, info["element"])
        result["groups"] = [{"name": name, "label": GROUP_LABELS[name], **spec} for name, spec in GROUP_SPECS.items()]
        result["slotSizes"] = SLOT_SIZES
        result["shapeSlots"] = list(SHAPE_SLOTS)
        result["shapeLabels"] = SHAPE_LABELS
        result["slotUse"] = SLOT_USES
        result["notes"] = PORTRAIT_NOTES
        return result

    def portrait_upload(self, cid: str, form: str, png_b64: str) -> dict:
        if form not in ("0", "1"):
            raise DraftError("立绘槽只有 _0 / _1")
        self.character(cid)
        uploaded = self.portraits.upload_source(cid, form, b64(png_b64, "PNG"))
        return {"upload": uploaded, "info": self.portrait_info(cid, form)}

    def portrait_save(self, cid: str, request: dict) -> dict:
        validate(request, "portraitRequest")
        info = self.character(cid)
        built = self.portraits.build_change(cid=cid, code=info["code"], element=info["element"], request=request,
                                            official_codes=self.official_codes(),
                                            make_file=self._file_maker(cid))
        return self._commit(cid, info["code"], "portrait", built)

    def mask_png(self, slot: str) -> bytes:
        return self.portraits.mask_png(slot, self.official_codes())

    # -- pixel ----------------------------------------------------------
    def pixel_save(self, cid: str, request: dict) -> dict:
        validate(request, "pixelRequest")
        info = self.character(cid)
        frames = []
        for index, item in enumerate(request["frames"]):
            if "png" not in item:
                raise DraftError(f"第 {index + 1} 帧缺少 png")
            frames.append(decode_frame(item["png"], index))
        durations = [int(item["duration"]) for item in request["frames"]]
        result = self.pixels.check(info["code"], request["family"], request["action"], frames, durations)
        for index, (image, item) in enumerate(zip(frames, request["frames"])):
            x, y = item["anchor"]
            if not (-image.width <= x <= image.width * 2 and -image.height <= y <= image.height * 2):
                result["checks"].append({"level": "warn", "code": "pixel.anchor_far",
                                         "message": f"第 {index + 1} 帧锚点远离帧图"})
        if request.get("dryRun"):
            return {"dryRun": True, **result}
        if any(c["level"] == "error" for c in result["checks"]):
            raise DraftError("检查未通过：" + "；".join(c["message"] for c in result["checks"] if c["level"] == "error"))
        family, action = request["family"], request["action"]
        stored = []
        for index, (image, item) in enumerate(zip(frames, request["frames"])):
            out = io.BytesIO()
            image.save(out, "PNG", optimize=True)
            data = out.getvalue()
            relative = f"files/pixel/{family}/{action}/frame_{index:03d}.png"
            self.store.write_file(cid, relative, data)
            stored.append({"file": relative, "sha256": sha256(data), "duration": int(item["duration"]),
                           "anchor": [round(float(v), 2) for v in item["anchor"]],
                           "width": image.width, "height": image.height})
        base = f"character/{info['code']}/pixelart/"
        sheet = "sprite_sheet" if family == "pixelart" else "special_sprite_sheet"
        reason = f"生成时把 {action} 的新帧与其它动作一起重新装箱、改写时间轴（wf deliver，M1 分支）"
        built = {
            "title": f"像素 {family}/{action}（{len(stored)} 帧）",
            "target": {"family": family, "action": action},
            "params": {"frames": stored, "totalFrames": sum(f["duration"] for f in stored),
                       "originalTotalFrames": result["originalTotalFrames"], "budget": result["budget"],
                       **({"origin": request["origin"]} if isinstance(request.get("origin"), dict) else {})},
            "files": [],
            "pending": [{"logical": base + sheet + ".png", "reason": reason},
                        {"logical": base + sheet + ".atlas.amf3.deflate", "reason": reason},
                        {"logical": base + family + ".timeline.amf3.deflate", "reason": reason}],
            "checks": result["checks"],
        }
        return self._commit(cid, info["code"], "pixel_action", built)

    # -- voice ----------------------------------------------------------
    def voice_lines(self, cid: str) -> dict:
        info = self.character(cid)
        code = info["code"]
        rows = self.assets.speech_rows(cid)
        lines, seen = [], set()
        for number, cells in enumerate(rows, 1):
            cells = cells + [""] * (5 - len(cells))
            voice = cells[4]
            entry = {"voice": voice if voice and voice != "(None)" else None, "speechRow": number,
                     "kind": cells[0], "subtitle": cells[3]}
            if entry["voice"]:
                seen.add(voice)
            lines.append(entry)
        for voice in voice_mod.FIXED_LINES:
            if voice not in seen and self.assets.locate(f"character/{code}/voice/{voice}.mp3"):
                lines.append({"voice": voice, "speechRow": None, "kind": "", "subtitle": ""})
                seen.add(voice)
        changeset = self.store.load(cid) or {"changes": []}
        drafts = {c["target"]["voice"]: c for c in changeset["changes"] if c["kind"] == "voice_line"}
        result = []
        for entry in lines:
            voice = entry["voice"]
            item = {**entry, "label": voice_mod.label_for(voice) if voice else "（无声字幕）"}
            if voice:
                logical = f"character/{code}/voice/{voice}.mp3"
                raw = self.assets.read(logical)
                item.update({"path": logical, "present": raw is not None, "layer": self.assets.locate(logical),
                             "durationSeconds": round(voice_mod.mp3_duration(raw), 2) if raw else None,
                             "loudness": voice_mod.LOUDNESS[voice_mod.category(voice)]})
                if voice in drafts:
                    change = drafts[voice]
                    item["draft"] = {"id": change["id"], "file": change["files"][0]["draft"],
                                     "durationSeconds": change["params"]["durationSeconds"],
                                     "checks": change["checks"], "sourceName": change["params"]["sourceName"]}
            result.append(item)
        return {"characterId": cid, "code": code, "lines": result,
                "format": "44.1kHz · 单声道 · 96kbps CBR（官方 40/40 抽样）",
                "note": "台词来自 character_speech（主页/入队/觉醒）与固定名战斗语音；只替换已有路径，"
                        "新增台词需要改 speech 表（M3.3）。"}

    def voice_save(self, cid: str, request: dict) -> dict:
        validate(request, "voiceRequest")
        info = self.character(cid)
        voice = request["voice"]
        if not _VOICE.match(voice):
            raise DraftError("语音路径无效")
        known = {line["voice"] for line in self.voice_lines(cid)["lines"] if line["voice"]}
        if voice not in known:
            raise DraftError(f"{voice} 不是这个角色已有的语音路径（新增台词需要改 speech 表，M3.3）")
        audio = b64(request["audio"], "音频")
        if not audio:
            raise DraftError("音频为空")
        loudness = float(request.get("loudness", voice_mod.LOUDNESS[voice_mod.category(voice)]))
        mp3, fmt = voice_mod.convert(audio, request["filename"], loudness)
        seconds = round(voice_mod.mp3_duration(mp3), 2)
        logical = f"character/{info['code']}/voice/{voice}.mp3"
        original = self.assets.read(logical)
        ext = re.sub(r"[^a-z0-9]", "", request["filename"].rsplit(".", 1)[-1].lower())[:5] or "bin"
        source_rel = f"sources/voice/{voice.replace('/', '__')}.{ext}"
        self.store.write_file(cid, source_rel, audio)
        make = self._file_maker(cid)
        checks = voice_mod.duration_checks(voice, seconds)
        subtitle = next((l["subtitle"] for l in self.voice_lines(cid)["lines"] if l["voice"] == voice), "")
        built = {
            "title": f"语音 {voice_mod.label_for(voice)}（{voice}）",
            "target": {"voice": voice},
            "params": {"sourceName": request["filename"][:120], "sourceFile": source_rel, "loudness": loudness,
                       "durationSeconds": seconds,
                       "originalDurationSeconds": round(voice_mod.mp3_duration(original), 2) if original else None,
                       "format": fmt, "subtitle": subtitle},
            "files": [make(logical, "common", mp3, "mp3", approximate=False,
                           note=f"ffmpeg 两遍 loudnorm → {loudness} LUFS，CBR 96k；已通过 mp3_encode 存储态校验")],
            "pending": [],
            "checks": checks,
        }
        return self._commit(cid, info["code"], "voice_line", built)

    # -- lifecycle --------------------------------------------------------
    def revert(self, cid: str, change_id: str) -> dict:
        changeset = self.store.revert(cid, change_id)
        return {"changeset": changeset, "status": status(changeset)}

    def save(self, cid: str) -> dict:
        changeset = self.store.save(cid)
        return {"changeset": changeset, "status": status(changeset)}


# Static descriptions handed to the frontend / agents.
SLOT_SIZES = {slot: list(size) for slot, size in _gate.OFFICIAL_ICON_SIZES.items()}
SHAPE_SLOTS = _gate.SHAPE_SLOTS
PORTRAIT_NOTES = [
    "脸锚 = 两眼连线中点（与 full_shot_image_attribute 的 faceX/faceY 同语义）；拖脸锚时所有框一起移动。",
    "每个框代表一组同构图图标：框高 = squareHeight × factor，脸锚在框内 (fx, fy)；与生产派生 make_icons 参数一一对应。",
    "带形状的槽在预览里套官方统计蒙版（逐像素中位数），保存时由后端用同一蒙版取 min。",
    "skill_cutin：真机战斗只读安卓根 ATF（ETC1），保存时用 wf_atf 按原 ATF 的 mip 数重编；本草稿未上真机。",
    "立绘切换需要 illustration_setting_sprite_sheet：保存时只重画本槽格子（fit 整图，近似）。",
    "三张定位表（character_image / trimmed_image / full_shot_image_attribute）只记目标行，生成时由 wf deliver 写。",
]
ACTIONS = [
    {"id": "save", "label": "保存", "enabled": True, "note": "整体 schema 校验 + 文件哈希复核，写入草稿 changeset.json"},
    {"id": "generate", "label": "生成", "enabled": False, "note": "待接入 wf deliver（M1 分支）"},
    {"id": "export", "label": "导出", "enabled": False, "note": "待接入 wf deliver（M1 分支）"},
    {"id": "apply", "label": "应用", "enabled": False, "note": "未接入：应用到测试服需要先生成补丁"},
    {"id": "publish", "label": "发布", "enabled": False, "note": "未接入：编辑台不发布"},
]
