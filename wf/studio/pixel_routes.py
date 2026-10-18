"""HTTP routes for 像素工坊 (analysis, remap, procedural actions, draft-state preview)."""
from __future__ import annotations

import io
import re
import threading

from .drafts import DraftError
from .pixel_workshop_ops import PixelWorkshop
from .pixels import FAMILIES, SLOTS, build_family


class PixelRoutes:
    def __init__(self, app):
        from .server import Response, error, json_response
        self.app = app
        self.workshop = PixelWorkshop(app.ops)
        self._json, self._error, self._response = json_response, error, Response
        self._lock = threading.Lock()
        self._draft_cache: dict[str, tuple[tuple, dict, dict]] = {}

    def routes(self):
        return [
            ("GET", re.compile(r"^/api/characters/(?P<cid>\d+)/pixel-workshop$"), self.analyze),
            ("GET", re.compile(r"^/api/characters/(?P<cid>\d+)/pixel-workshop/cell/(?P<family>pixelart|special)/"
                               r"(?P<key>\d+)\.png$"), self.cell),
            ("GET", re.compile(r"^/api/characters/(?P<cid>\d+)/pixel-workshop/suggest$"), self.suggest),
            ("GET", re.compile(r"^/api/characters/(?P<cid>\d+)/pixel-workshop/bases$"), self.bases),
            ("GET", re.compile(r"^/api/drafts/(?P<cid>\d+)/pixels$"), self.draft_meta),
            ("GET", re.compile(r"^/api/drafts/(?P<cid>\d+)/pixels/(?P<family>pixelart|special)\.png$"), self.draft_sheet),
            ("POST", re.compile(r"^/api/drafts/(?P<cid>\d+)/pixel-remap$"), self.remap),
            ("POST", re.compile(r"^/api/drafts/(?P<cid>\d+)/pixel-generate$"), self.generate),
        ]

    def analyze(self, query, cid):
        draft = (query.get("state") or ["view"])[0] == "draft"
        return self._json(self.workshop.analyze(cid, draft=draft))

    def cell(self, query, cid, family, key):
        trimmed = (query.get("trim") or ["1"])[0] != "0"
        draft = (query.get("state") or ["view"])[0] == "draft"
        image = self.workshop.cell_image(cid, family, int(key), trimmed=trimmed, draft=draft)
        out = io.BytesIO()
        image.save(out, "PNG")
        return self._response(200, out.getvalue(), "image/png", "no-store" if draft else None)

    def suggest(self, query, cid):
        base = (query.get("base") or [""])[0]
        if not base.isdigit():
            raise DraftError("需要 base=母本角色 ID")
        return self._json(self.workshop.suggest(cid, base))

    def bases(self, query, cid):
        return self._json({"bases": self.workshop.default_bases(cid)})

    def _draft_family(self, cid):
        changeset = self.app.ops.store.load(cid)
        revision = (changeset["createdAt"], changeset["revision"], changeset["updatedAt"]) if changeset else None
        with self._lock:
            cached = self._draft_cache.get(cid)
            if cached and cached[0] == revision:
                return cached[1], cached[2]
        overlay = self.workshop.draft_source(cid)
        if overlay is None:
            return None, None
        code = self.app.ops.character(cid)["code"]
        families, sheets = [], {}
        for stem, sheet, label in FAMILIES:
            built = build_family(overlay, code, stem, sheet) if overlay.raw(
                f"character/{code}/pixelart/{sheet}.png") is not None else None
            if built is None:
                continue
            meta, png = built
            sheets[stem] = png
            families.append({**meta, "label": label})
        present = {a["name"] for f in families for a in f.get("actions", [])}
        meta = {"characterId": cid, "code": code, "families": families, "draftRevision": revision[1],
                "draftStamp": "".join(ch for ch in f"{revision[0]}{revision[1]}{revision[2]}" if ch.isalnum()),
                "slots": [{"name": n, "label": l, "present": n in present} for n, l in SLOTS],
                "note": "草稿态：把草稿里的像素改动（整族映射 + 逐动作替换）按生成时同一编译器合成后播放。"}
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

    def remap(self, query, body, cid):
        return self._json(self.workshop.remap(cid, body))

    def generate(self, query, body, cid):
        return self._json(self.workshop.generate(cid, body))
