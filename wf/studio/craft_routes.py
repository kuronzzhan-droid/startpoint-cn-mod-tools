"""HTTP routes for the four 交稿 tools: 像素批量预检, 场地比例预览, 图集重排, 稿主交接单."""
from __future__ import annotations

import re
import threading

from . import atlas_optimize, handoff, pixel_precheck, stage_scale
from .drafts import DraftError

CID = r"(?P<cid>\d+|scratch-[a-z0-9][a-z0-9-]{0,47})"
FAMILY = ("pixelart", "special")


class CraftRoutes:
    def __init__(self, app):
        from .server import Response, json_response
        self.app = app
        self._json, self._response = json_response, Response
        self._lock = threading.Lock()
        self._repacks: dict[tuple, dict] = {}

    def routes(self):
        return [
            ("POST", re.compile(rf"^/api/drafts/{CID}/pixel-precheck$"), self.precheck),
            ("GET", re.compile(r"^/api/stage-scale$"), self.stage),
            ("GET", re.compile(rf"^/api/characters/{CID}/atlas-repack$"), self.repack),
            ("GET", re.compile(rf"^/api/characters/{CID}/atlas-repack/(?P<family>pixelart|special)\.png$"),
             self.repack_png),
            ("POST", re.compile(rf"^/api/drafts/{CID}/atlas-repack$"), self.repack_apply),
            ("GET", re.compile(rf"^/api/drafts/{CID}/handoff$"), self.handoff),
            ("POST", re.compile(rf"^/api/drafts/{CID}/handoff-notes$"), self.handoff_notes),
        ]

    def _ops(self, cid):
        return self.app.pixel_workshop.shop(cid).ops

    @staticmethod
    def _family(value) -> str:
        family = value or "pixelart"
        if family not in FAMILY:
            raise DraftError(f"未知像素族：{family}")
        return family

    # -- 像素批量预检 ---------------------------------------------------------
    def precheck(self, query, body, cid):
        return self._json(pixel_precheck.precheck(self._ops(cid), cid, body))

    # -- 场地比例 -------------------------------------------------------------
    def stage(self, query):
        quest = (query.get("quest") or [""])[0].strip()
        terrain = (query.get("terrain") or [""])[0].strip()
        if quest and not re.fullmatch(r"[0-9A-Za-z_]{1,32}", quest):
            raise DraftError("关卡 ID 只能是字母数字")
        return self._json(stage_scale.stage(self.app.source, quest or None, terrain or None))

    # -- 图集重排 -------------------------------------------------------------
    def _optimized(self, cid, family):
        key = (cid, family, getattr(self.app.source, "version", None))
        with self._lock:
            hit = self._repacks.get(key)
        if hit is None:
            hit = atlas_optimize.preview(self._ops(cid), cid, family)
            with self._lock:
                if len(self._repacks) > 8:
                    self._repacks.clear()
                self._repacks[key] = hit
        return hit

    def repack(self, query, cid):
        family = self._family((query.get("family") or [""])[0])
        return self._json(self._optimized(cid, family)["report"])

    def repack_png(self, query, cid, family):
        import wf_assets
        return self._response(200, wf_assets.png_decode(self._optimized(cid, family)["png"]), "image/png")

    def repack_apply(self, query, body, cid):
        return self._json(atlas_optimize.apply(self._ops(cid), cid, self._family(body.get("family"))))

    # -- 交接单 ---------------------------------------------------------------
    def handoff(self, query, cid):
        doc = handoff.sheet(self._ops(cid), cid)
        if (query.get("format") or [""])[0] == "md":
            return self._response(200, handoff.markdown(doc).encode("utf-8"), "text/markdown; charset=utf-8", "no-store")
        return self._json(doc)

    def handoff_notes(self, query, body, cid):
        ops = self._ops(cid)
        ops.character(cid)
        return self._json({"notes": handoff.save_notes(ops.store, cid, body)})
