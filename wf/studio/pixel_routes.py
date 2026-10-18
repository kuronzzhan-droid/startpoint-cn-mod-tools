"""HTTP routes for 像素工坊 (analysis, remap, procedural actions, import, draft-state preview)
and 草稿角色 (scratch characters: create, list, pixel save, bind, build refusal)."""
from __future__ import annotations

import io
import re
import struct
import threading

from . import scratch
from .drafts import DraftError
from .pixel_workshop_ops import PixelWorkshop
from .pixels import FAMILIES, SLOTS, build_family

CID = r"(?P<cid>\d+|scratch-[a-z0-9][a-z0-9-]{0,47})"
SID = r"(?P<cid>scratch-[a-z0-9][a-z0-9-]{0,47})"


class PixelRoutes:
    def __init__(self, app):
        from .server import Response, error, json_response
        self.app = app
        self.workshop = PixelWorkshop(app.ops)
        self._json, self._error, self._response = json_response, error, Response
        self._lock = threading.Lock()
        self._draft_cache: dict[str, tuple[tuple, dict, dict]] = {}
        self._scratch: dict[tuple, PixelWorkshop] = {}
        self._raw: dict[int, tuple[bytes, bytes]] = {}

    def routes(self):
        return [
            ("GET", re.compile(rf"^/api/characters/{CID}/pixel-workshop$"), self.analyze),
            ("GET", re.compile(rf"^/api/characters/{CID}/pixel-workshop/cell/(?P<family>pixelart|special)/"
                               r"(?P<key>\d+)\.png$"), self.cell),
            ("GET", re.compile(rf"^/api/characters/{CID}/pixel-workshop/suggest$"), self.suggest),
            ("GET", re.compile(rf"^/api/characters/{CID}/pixel-workshop/bases$"), self.bases),
            ("GET", re.compile(rf"^/api/characters/{SID}/pixels$"), self.scratch_meta),
            ("GET", re.compile(rf"^/api/characters/{SID}/pixels/(?P<family>pixelart|special)\.png$"), self.scratch_sheet),
            ("GET", re.compile(rf"^/api/drafts/{CID}/pixels$"), self.draft_meta),
            ("GET", re.compile(rf"^/api/drafts/{CID}/pixels/(?P<family>pixelart|special)\.png$"), self.draft_sheet),
            ("GET", re.compile(rf"^/api/characters/{CID}/pixels/(?P<family>pixelart|special)\.rgba$"), self.view_rgba),
            ("GET", re.compile(rf"^/api/drafts/{CID}/pixels/(?P<family>pixelart|special)\.rgba$"), self.draft_rgba),
            ("GET", re.compile(rf"^/api/characters/{CID}/pixel-workshop/action/(?P<family>pixelart|special)/"
                               r"(?P<action>[a-z_]+)$"), self.action_frames),
            ("POST", re.compile(rf"^/api/drafts/{CID}/pixel-remap$"), self.remap),
            ("POST", re.compile(rf"^/api/drafts/{CID}/pixel-generate$"), self.generate),
            ("POST", re.compile(rf"^/api/drafts/{CID}/pixel-import$"), self.import_set),
            # -- 草稿角色 --
            ("GET", re.compile(r"^/api/scratch$"), self.scratch_list),
            # Every write route lives under /api/drafts/ (guard invariant).
            ("POST", re.compile(r"^/api/drafts/scratch$"), self.scratch_create),
            ("GET", re.compile(rf"^/api/scratch/{SID}$"), self.scratch_describe),
            ("POST", re.compile(rf"^/api/drafts/{SID}/pixel$"), self.scratch_pixel_save),
            ("POST", re.compile(rf"^/api/drafts/{SID}/bind$"), self.scratch_bind),
            ("POST", re.compile(rf"^/api/drafts/{SID}/build$"), self.scratch_build),
        ]

    # -- which workshop -----------------------------------------------------
    def shop(self, cid) -> PixelWorkshop:
        if not scratch.is_scratch(cid):
            return self.workshop
        changeset = self.app.ops.store.load(cid)
        if not changeset or "scratch" not in changeset:
            raise DraftError(f"没有草稿角色 {cid}")
        key = (cid, changeset["createdAt"], changeset["scratch"]["base"]["code"])
        with self._lock:
            if key not in self._scratch:
                self._scratch = {k: v for k, v in self._scratch.items() if k[0] != cid}
                self._scratch[key] = PixelWorkshop(scratch.ScratchDraftOps(self.app.ops, cid))
            return self._scratch[key]

    # -- workshop -------------------------------------------------------------
    def analyze(self, query, cid):
        draft = (query.get("state") or ["view"])[0] == "draft"
        return self._json(self.shop(cid).analyze(cid, draft=draft))

    def cell(self, query, cid, family, key):
        trimmed = (query.get("trim") or ["1"])[0] != "0"
        draft = (query.get("state") or ["view"])[0] == "draft"
        png, state = self.shop(cid).cell_png(cid, family, int(key), trimmed=trimmed, draft=draft)
        # View thumbnails never change within a process: default caching, like the pixel sheets.
        cache = "no-store" if state != "view" or scratch.is_scratch(cid) else None
        return self._response(200, png, "image/png", cache)

    def suggest(self, query, cid):
        base = (query.get("base") or [""])[0]
        if not re.fullmatch(r"[0-9]{1,9}|[a-z0-9_]+", base):
            raise DraftError("需要 base=母本角色 ID 或代码名")
        return self._json(self.shop(cid).suggest(cid, base))

    def bases(self, query, cid):
        return self._json({"bases": self.shop(cid).default_bases(cid)})

    def _families(self, source, code):
        families, sheets = [], {}
        for stem, sheet, label in FAMILIES:
            if source.raw(f"character/{code}/pixelart/{sheet}.png") is None:
                continue
            meta, png = build_family(source, code, stem, sheet)
            sheets[stem] = png
            families.append({**meta, "label": label})
        present = {a["name"] for f in families for a in f.get("actions", [])}
        return families, sheets, [{"name": n, "label": l, "present": n in present} for n, l in SLOTS]

    def _draft_family(self, cid):
        changeset = self.app.ops.store.load(cid)
        revision = (changeset["createdAt"], changeset["revision"], changeset["updatedAt"]) if changeset else None
        with self._lock:
            cached = self._draft_cache.get(cid)
            if cached and cached[0] == revision:
                return cached[1], cached[2]
        shop = self.shop(cid)
        overlay = shop.draft_source(cid)
        if overlay is None:
            return None, None
        code = shop.ops.character(cid)["code"]
        families, sheets, slots = self._families(overlay, code)
        meta = {"characterId": cid, "code": code, "families": families, "draftRevision": revision[1],
                "draftStamp": "".join(ch for ch in f"{revision[0]}{revision[1]}{revision[2]}" if ch.isalnum()),
                "slots": slots,
                "note": "草稿态：把草稿里的像素改动（整族映射/导入 + 逐动作替换）按生成时同一编译器合成后播放。"}
        with self._lock:
            self._draft_cache[cid] = (revision, meta, sheets)
        return meta, sheets

    def draft_meta(self, query, cid):
        meta, _ = self._draft_family(cid)
        return self._json(meta) if meta else self._error(404, "草稿里没有像素改动")

    def draft_sheet(self, query, cid, family):
        _, sheets = self._draft_family(cid)
        if not sheets or family not in sheets:
            return self._error(404, "草稿里没有这一族像素")
        return self._response(200, sheets[family], "image/png", "no-store")

    def _scratch_families(self, cid, shop):
        """Grid sheets of a scratch character's view (base family renamed), cached per workshop."""
        cache = getattr(shop, "_scratch_grid", None)
        if cache is None:
            with self._lock:
                cache = getattr(shop, "_scratch_grid", None)
                if cache is None:
                    cache = self._families(shop.source, shop.ops.character(cid)["code"])
                    shop._scratch_grid = cache
        return cache

    def scratch_meta(self, query, cid):
        shop = self.shop(cid)
        code = shop.ops.character(cid)["code"]
        families, _, slots = self._scratch_families(cid, shop)
        base = shop.ops.meta["base"]
        return self._json({"characterId": cid, "code": code, "families": families, "slots": slots,
                           "note": f"草稿角色的「当前视图」= 母本 {base['code']} 整族（时间轴区间、锚点、显示倍率）"
                                   f"改名到占位代码 {code}。"})

    def scratch_sheet(self, query, cid, family):
        shop = self.shop(cid)
        _, sheets, _ = self._scratch_families(cid, shop)
        if family not in sheets:
            return self._error(404, "母本没有这一族像素")
        return self._response(200, sheets[family], "image/png", "no-store")

    # -- raw RGBA (the browser never decodes pixel data through a canvas) -----
    def _rgba(self, png: bytes) -> bytes:
        """Grid sheet PNG → 8-byte header (uint32 LE width, height) + raw RGBA bytes."""
        with self._lock:
            hit = self._raw.get(id(png))
            if hit and hit[0] is png:
                return hit[1]
        from PIL import Image
        image = Image.open(io.BytesIO(png))
        image.load()
        image = image.convert("RGBA")
        body = struct.pack("<II", image.width, image.height) + image.tobytes()
        with self._lock:
            if len(self._raw) > 24:
                self._raw.clear()
            self._raw[id(png)] = (png, body)
        return body

    def view_rgba(self, query, cid, family):
        if scratch.is_scratch(cid):
            shop = self.shop(cid)
            sheets = self._scratch_families(cid, shop)[1]
        else:
            code = self.app._code(cid)
            sheets = {family: self.app.pixels.sheet(code, family)} if code else {}
        if not sheets.get(family):
            return self._error(404, "该角色没有这一组像素资源")
        return self._response(200, self._rgba(sheets[family]), "application/octet-stream",
                              "no-store" if scratch.is_scratch(cid) else None)

    def draft_rgba(self, query, cid, family):
        _, sheets = self._draft_family(cid)
        if not sheets or family not in sheets:
            return self._error(404, "草稿里没有这一族像素")
        return self._response(200, self._rgba(sheets[family]), "application/octet-stream", "no-store")

    def action_frames(self, query, cid, family, action):
        draft = (query.get("state") or ["draft"])[0] == "draft"
        return self._json(self.shop(cid).action_frames(cid, family, action, draft=draft))

    def remap(self, query, body, cid):
        return self._json(self.shop(cid).remap(cid, body))

    def generate(self, query, body, cid):
        return self._json(self.shop(cid).generate(cid, body))

    def import_set(self, query, body, cid):
        return self._json(scratch.import_set(self.app.ops, cid, body))

    # -- 草稿角色 ---------------------------------------------------------------
    def scratch_list(self, query):
        return self._json({"scratch": scratch.listing(self.app.ops), "elements": list(scratch.ELEMENTS)})

    def scratch_create(self, query, body):
        return self._json(scratch.create(self.app.ops, body))

    def scratch_describe(self, query, cid):
        return self._json(scratch.describe(self.app.ops, cid))

    def scratch_pixel_save(self, query, body, cid):
        return self._json(self.shop(cid).ops.pixel_save(cid, body))

    def scratch_bind(self, query, body, cid):
        return self._json(scratch.bind(self.app.ops, cid, body))

    def scratch_build(self, query, body, cid):
        raise DraftError(scratch.build_refusal(self.app.ops.store, cid))
