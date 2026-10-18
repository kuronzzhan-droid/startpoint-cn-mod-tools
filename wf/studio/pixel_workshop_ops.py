"""像素工坊：拆解 / 母本映射 / 程序化动作 / 画板 —— HTTP 与 CLI 共用的操作。

写入全部走草稿：
* 母本映射 → ``pixel_family`` 改动（整族四件文件存在草稿里，生成时按母本 + 映射表重算并逐字节核对）；
* 程序化动作、画板 → 复用 ``pixel_action``（``DraftOps.pixel_save``），帧是 256² 帧框、锚点 (128,128)。
"""
from __future__ import annotations

import base64
import io

import wf_assets
from PIL import Image

from .deliver_media import read_root
from .drafts import DraftError, sha256, validate
from .pixel_generate import LABELS as GENERATE_LABELS, RECIPES, generate, trim
from .pixel_workshop import (FAMILY_FILES, UNIVERSAL_RANGES, analyze, decode_family, family_paths,
                             normalize_mapping, read_family_raw, remap_family, suggest_mapping)
from wf_pixelart_vfx import restore_frame


def png_b64(image: Image.Image) -> str:
    out = io.BytesIO()
    image.save(out, "PNG", optimize=True)
    return base64.b64encode(out.getvalue()).decode("ascii")


class PixelWorkshop:
    def __init__(self, ops):
        self.ops = ops
        self.source = ops.source
        self._analysis: dict[tuple, dict] = {}
        self._overlays: dict[str, object] = {}

    # -- read -------------------------------------------------------------
    def _state(self, cid: str, draft: bool):
        """(source, cache key): the view, or the view with this draft's pixel changes compiled in."""
        if draft:
            changeset = self.ops.store.load(cid)
            if changeset and any(c["kind"] in ("pixel_family", "pixel_action") for c in changeset["changes"]):
                # createdAt too: a discarded and recreated draft restarts its revision count.
                key = f"draft:{cid}:{changeset['createdAt']}:{changeset['revision']}:{changeset['updatedAt']}"
                if key not in self._overlays:
                    self._overlays.clear()
                    self._overlays[key] = self.draft_source(cid)
                return self._overlays[key], key
        return self.source, "view"

    def analyze(self, cid: str, *, draft: bool = False) -> dict:
        info = self.ops.character(cid)
        code = info["code"]
        source, state = self._state(cid, draft)
        cache = (code, state)
        if cache not in self._analysis:
            self._analysis[cache] = analyze(source, code)
        return {"characterId": cid, "name": info["name"], "state": "draft" if state != "view" else "view",
                **self._analysis[cache]}

    def cell_image(self, cid: str, family: str, key: int, *, trimmed: bool = True, draft: bool = True) -> Image.Image:
        code = self.ops.character(cid)["code"]
        source, _ = self._state(cid, draft)
        raws = read_family_raw(source, code, family)
        if raws is None:
            raise DraftError(f"{cid} 没有 {family} 像素族")
        data = decode_family(raws)
        if key not in data["entries"]:
            raise DraftError(f"{family} 没有端点帧 {key}")
        image = restore_frame(data["sheet"], data["entries"][key])
        return trim(image) if trimmed else image

    # -- remap ------------------------------------------------------------
    def remap(self, cid: str, request: dict) -> dict:
        validate(request, "pixelRemapRequest")
        from .scratch import resolve_character
        target = self.ops.character(cid)
        base = resolve_character(self.ops, str(request["base"]))
        mapping = normalize_mapping(request.get("mapping") or [])
        families = request.get("families") or [f for f in FAMILY_FILES
                                               if read_family_raw(self.source, base["code"], f) is not None]
        if not families:
            raise DraftError(f"母本 {base['id']} 没有像素族")
        results, changes = [], []
        for family in families:
            base_raws = read_family_raw(self.source, base["code"], family)
            if base_raws is None:
                raise DraftError(f"母本 {base['id']} 没有 {family} 像素族")
            rebuilt = remap_family(base_raws, base["code"], target["code"], mapping)
            checks = self._remap_checks(cid, target["code"], family, base_raws, rebuilt)
            used = {k for k in mapping if self._palette_has(base["code"], k)}
            item = {"family": family, "changedPixels": rebuilt["changedPixels"],
                    "renamedEntries": rebuilt["renamedEntries"], "sheet": list(rebuilt["sheet"].size),
                    "checks": checks, "mappingUsed": len(used), "mappingSize": len(mapping)}
            results.append(item)
            if request.get("dryRun"):
                continue
            if any(c["level"] == "error" for c in checks):
                raise DraftError("检查未通过：" + "；".join(c["message"] for c in checks if c["level"] == "error"))
            changes.append((family, base_raws, rebuilt, checks))
        if request.get("dryRun"):
            return {"dryRun": True, "base": base, "families": results}
        committed = []
        for family, base_raws, rebuilt, checks in changes:
            committed.append(self._commit_family(cid, target, base, family, base_raws, rebuilt, request, checks))
        return {"base": base, "families": results, "changes": [c["change"] for c in committed],
                "changeset": committed[-1]["changeset"], "status": committed[-1]["status"]}

    def _palette_has(self, code: str, rgb) -> bool:
        if (code, "view") not in self._analysis:
            self._analysis[code, "view"] = analyze(self.source, code)
        return any(tuple(p["rgb"]) == tuple(rgb) for p in self._analysis[code, "view"]["palette"])

    def _remap_checks(self, cid, code, family, base_raws, rebuilt) -> list[dict]:
        checks = []
        base = decode_family(base_raws)
        ranges = {s["name"]: (s["begin"], s["end"]) for s in base["timeline"].get("sequences", [])}
        universal = UNIVERSAL_RANGES[family]
        odd = [n for n, r in ranges.items() if universal.get(n) not in (None, r)]
        missing = [n for n in universal if n not in ranges]
        if odd or missing:
            checks.append({"level": "warn", "code": "workshop.remap_ranges",
                           "message": "母本时间轴与通用区间不一致：" + "，".join(
                               [f"{n}={ranges[n][0]}–{ranges[n][1]}" for n in odd] + [f"缺 {n}" for n in missing])})
        current = read_family_raw(self.source, code, family)
        if current is None:
            checks.append({"level": "info", "code": "workshop.remap_new_family",
                           "message": f"本角色原来没有 {family} 像素族：生成时新增四件文件"})
        else:
            mine = decode_family(current)
            mine_ranges = {s["name"]: (s["begin"], s["end"]) for s in mine["timeline"].get("sequences", [])}
            if mine_ranges != ranges:
                checks.append({"level": "info", "code": "workshop.remap_timeline_changes",
                               "message": "整族替换会改掉本角色原来的时间轴区间（技能 DSL 不按帧号引用小人，通常无影响）"})
        if base["frame"].get("scale") != 6:
            checks.append({"level": "warn", "code": "workshop.scale",
                           "message": f"母本 frame.scale = {base['frame'].get('scale')}（官方 6）"})
        if rebuilt["changedPixels"] == 0:
            checks.append({"level": "warn", "code": "workshop.remap_identity",
                           "message": "映射表没有改动任何像素：结果与母本同色"})
        width, height = rebuilt["sheet"].size
        if family == "pixelart":
            checks.append({"level": "info", "code": "workshop.remap_budget",
                           "message": f"sprite_sheet 沿用母本 {width}×{height}，layer0 {(width + 2) * (height + 2)} px"})
        draft = self.ops.store.load(cid) or {"changes": []}
        if any(c["kind"] == "pixel_action" and c["target"]["family"] == family for c in draft["changes"]):
            checks.append({"level": "warn", "code": "workshop.remap_with_actions",
                           "message": "草稿里已有本族逐动作替换：生成时先整族替换，再把逐动作替换叠在上面"})
        return checks

    def _commit_family(self, cid, target, base, family, base_raws, rebuilt, request, checks) -> dict:
        make = self.ops._file_maker(cid)
        paths = family_paths(target["code"], family)
        base_paths = family_paths(base["code"], family)
        files = [make(paths[0], "common", wf_assets.png_decode(rebuilt["stored"][0]), "png", approximate=False,
                      note=f"母本 {base['id']} 逐色映射")]
        for logical, raw in zip(paths[1:], rebuilt["stored"][1:]):
            files.append(make(logical, "common", raw, "amf3-deflate", approximate=False,
                              note="atlas/frame 只改名前缀；timeline 逐字节照搬母本"))
        mapping = sorted(({"from": "#%02x%02x%02x" % k, "to": "#%02x%02x%02x" % v}
                          for k, v in normalize_mapping(request.get("mapping") or []).items()),
                         key=lambda m: m["from"])
        built = {
            "title": f"像素整族 {family}：母本 {base['name'] or base['code']}（{base['id'] or base['code']}）逐色映射 {len(mapping)} 色",
            "target": {"family": family},
            "params": {"mode": "remap",
                       "base": {"characterId": base["id"], "code": base["code"],
                                "files": {logical: sha256(raw) for logical, raw in zip(base_paths, base_raws)}},
                       "mapping": mapping, "changedPixels": rebuilt["changedPixels"],
                       "renamedEntries": rebuilt["renamedEntries"],
                       **({"groups": request["groups"]} if isinstance(request.get("groups"), dict) else {})},
            "files": files, "pending": [], "checks": checks,
        }
        return self.ops._commit(cid, target["code"], "pixel_family", built)

    def suggest(self, cid: str, base_cid: str) -> dict:
        from .scratch import resolve_character
        mine = self.analyze(cid)  # the character's own (view) palette is the colour target
        ref = resolve_character(self.ops, base_cid)
        base = {"palette": analyze(self.source, ref["code"])["palette"]}
        return {"suggestions": suggest_mapping(base["palette"], mine["palette"])}

    # -- generate ---------------------------------------------------------
    def _base_image(self, cid: str, spec) -> Image.Image | None:
        if spec is None:
            return None
        if "png" in spec:
            try:
                image = Image.open(io.BytesIO(base64.b64decode(spec["png"], validate=True)))
                image.load()
            except (ValueError, OSError) as exc:
                raise DraftError(f"底图不是可读的 PNG：{exc}") from None
            return trim(image.convert("RGBA"))
        cell = spec["cell"]
        return self.cell_image(cid, cell["family"], int(cell["key"]))

    def default_bases(self, cid: str) -> dict:
        """正面=待机首张；背面=walk_back 首张。躺倒没有通用来源（官方 into_coffin 是升空消散），
        缺省时生成器用正面顺时针转 90° 近似。"""
        result = {}
        try:
            data = self.analyze(cid, draft=True)
        except DraftError:
            return result
        family = next((f for f in data["families"] if f["family"] == "pixelart"), None)
        if not family:
            return result
        actions = {a["name"]: a for a in family["actions"]}
        for name, action, index in (("front", "neutral", 0), ("back", "walk_back", 0)):
            if action in actions and actions[action]["cells"]:
                result[name] = {"cell": {"family": "pixelart", "key": actions[action]["cells"][index]["key"]}}
        return result

    def generate(self, cid: str, request: dict) -> dict:
        validate(request, "pixelGenerateRequest")
        action = request["action"]
        specs = {**self.default_bases(cid), **(request.get("bases") or {})}
        bases = {name: self._base_image(cid, spec) for name, spec in specs.items()}
        data = self.analyze(cid, draft=True)
        family = next((f for f in data["families"] if f["family"] == "pixelart"), None)
        total = request.get("totalFrames")
        if total is None:
            current = next((a for a in (family or {}).get("actions", []) if a["name"] == action), None)
            total = current["totalFrames"] if current else RECIPES[action]["total"]
        ground = request.get("ground")
        if ground is None:
            neutral = next((a for a in (family or {}).get("actions", []) if a["name"] == "neutral"), None)
            dys = sorted(c["dy"] for c in neutral["cells"]) if neutral and neutral["cells"] else [0]
            ground = int(round(dys[len(dys) // 2]))
        frames = generate(action, bases, total, ground=ground)
        preview = [{"png": png_b64(f["image"]), "duration": f["duration"], "dy": f["dy"], "note": f["note"],
                    "bbox": list(f["image"].getbbox() or (0, 0, 0, 0))} for f in frames]
        if not request.get("save"):
            return {"action": action, "label": GENERATE_LABELS[action], "totalFrames": total, "ground": ground,
                    "frames": preview,
                    "bases": {k: v for k, v in specs.items() if "cell" in v},
                    "anchor": [128, 128], "frameBox": [256, 256]}
        pixel_request = {"family": "pixelart", "action": action,
                         "frames": [{"png": p["png"], "duration": p["duration"], "anchor": [128, 128]} for p in preview],
                         "origin": {"mode": "generated", "recipe": action,
                                    "bases": {k: (v if "cell" in v else {"png": "uploaded"}) for k, v in specs.items()}}}
        result = self.ops.pixel_save(cid, pixel_request)
        return {**result, "frames": preview}

    # -- draft-state preview ------------------------------------------------
    def draft_source(self, cid: str):
        """A read-only source overlaying this draft's compiled pixel families on the view."""
        from .deliver_pixel import compile_pixels
        changeset = self.ops.store.load(cid)
        if not changeset or not any(c["kind"] in ("pixel_family", "pixel_action") for c in changeset["changes"]):
            return None
        compiled = compile_pixels(self.source, self.ops.store, changeset).members
        return _Overlay(self.source, compiled)


class _Overlay:
    def __init__(self, source, members: dict):
        self.source = source
        self.members = members
        self.version = source.version

    def read_root(self, root, logical):
        if (root, logical) in self.members:
            return self.members[root, logical]
        return read_root(self.source, root, logical)

    def raw(self, logical):
        if ("common", logical) in self.members:
            return self.members["common", logical]
        return self.source.raw(logical)

    def table(self, name):
        return self.source.table(name)
