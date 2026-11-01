"""Read-only Wiki card projection using the shared catalog serializer."""
from __future__ import annotations

from urllib.parse import quote

from .drafts import DraftError
from .deliver_media import read_root
from .translation import annotate_catalog


class CardSource:
    """Project draft rows while retaining a separate official attribution source."""
    baseline = None

    def __init__(self, source, scratch=None, *, official_source=None):
        self.source, self.scratch = source, scratch
        self.official_source = official_source if official_source is not None else source

    @property
    def baseline_error(self):
        return getattr(self.official_source, "baseline_error", None)

    def table(self, name, official=False):
        if official:
            return {} if self.scratch else self.official_source.table(name, True)
        if self.scratch:
            cid, meta, code = self.scratch
            row = [""] * 37
            row[0], row[2], row[3] = code, "0", str(["火", "水", "雷", "风", "光", "暗"].index(meta["element"]))
            if name == "character":
                return {cid: [row]}
            if name == "text":
                return {cid: [[meta["name"], "", meta.get("note", "")]]}
            return {}
        return self.source.table(name)

    def raw(self, logical, official=False):
        if official:
            return None if self.scratch else self.official_source.raw(logical, True)
        return self.source.raw(logical)

    def tree(self, logical, official=False):
        if official:
            return None if self.scratch else self.official_source.tree(logical, True)
        return self.source.tree(logical)

    def citation(self, logical):
        return {"logical": logical, "source": "草稿内存预览"}


def portrait_raw(source, logical):
    """Match the full-size portrait roots without using common-only raw access."""
    for root in ("medium", "android", "common"):
        raw = read_root(source, root, logical)
        if raw is not None:
            return raw
    return None


class CardMedia:
    def __init__(self, source, cid, draft):
        self.source, self.cid = source, cid
        self.files = {f["logical"]: f for c in (draft or {}).get("changes", []) for f in c["files"]
                      if f["encoding"] == "png" or f["logical"].endswith(".png")}

    def has(self, logical):
        return logical in self.files or portrait_raw(self.source, logical) is not None

    def image(self, logical):
        if logical in self.files:
            f = self.files[logical]
            # Plain uploads can use the draft file route; stored clones need wiki-image decoding.
            if f["encoding"] == "png":
                return f"/api/drafts/{self.cid}/file?path={quote(f['draft'])}&v={f['sha256']}"
        revision = self.files.get(logical, {}).get("sha256", "baseline")
        return f"/api/drafts/{self.cid}/wiki-image?path={quote(logical)}&v={revision}" if self.has(logical) else None

    def official_image(self, logical, baseline):
        return self.image(logical)


def image(ops, cid, logical):
    import wf_assets
    from .scratch import ops_for
    bound = ops_for(ops, cid)
    info = bound.character(cid)
    if not logical.startswith(f"character/{info['code']}/ui/") or ".." in logical.split("/") or not logical.endswith(".png"):
        raise DraftError("Wiki 图片必须属于当前草稿角色 UI")
    draft = ops.store.load(cid)
    entry = CardMedia(bound.source, cid, draft).files.get(logical)
    if entry:
        from .drafts import sha256
        raw = ops.store.read_file(cid, entry["draft"])
        if sha256(raw) != entry["sha256"]:
            raise DraftError("草稿图片摘要不符")
        return raw if entry["encoding"] == "png" else wf_assets.png_decode(raw)
    raw = portrait_raw(bound.source, logical)
    if raw is None:
        raise DraftError("卡片图片不存在")
    return wf_assets.png_decode(raw)


def preview(ops, cid, *, server_dir=None):
    from wf_wiki_catalog import character_entry
    from .ability import AbilityEditor
    from .character_clone import ops_for
    from .source import StudioSource
    draft = ops.store.load(cid)
    scratch = None
    if cid.startswith("scratch-"):
        if not draft or "scratch" not in draft:
            raise DraftError("草稿角色不存在")
        scratch = (cid, draft["scratch"], draft["code"])
        source = ops.source
        from .scratch import ops_for as scratch_ops
        media_source = scratch_ops(ops, cid).source
    else:
        source = ops_for(ops, cid).source
        media_source = source
        if draft and any(c["kind"] in {"ability_edit", "skill_template"} for c in draft["changes"]):
            state, _, _, _ = AbilityEditor(ops.source, store=ops.store, server_dir=server_dir)._base(cid)
            state = state.clone()
            state.tip, state.zips, state.extra_zips = ops.source.version, [], []
            source = StudioSource(state)
        if cid not in source.table("character"):
            raise DraftError("角色不在当前视图或草稿中")
    card_source = CardSource(source, scratch, official_source=ops.source)
    card = character_entry(card_source, cid, ["草稿预览"], CardMedia(media_source, cid, draft))
    card["origin"] = "草稿预览"
    annotate_catalog(card_source, [card["leader"], *card["abilities"]], card["skills"],
                     card["raw"]["character"][8], cid=cid, base_source=ops.source)
    return {"card": card, "readOnly": True, "draftRevision": (draft or {}).get("revision"),
            "sourceVersion": ops.source.version,
            "note": "只读 Wiki 卡片；读取已写入草稿的内容，未写入的编辑不计入。未发布。"
                    + ("像素草稿尚无正式技能/数值，卡片不继承母本战斗数据。" if scratch else "")}
