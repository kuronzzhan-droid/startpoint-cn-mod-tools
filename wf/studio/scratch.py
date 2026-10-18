"""草稿角色（scratch）：还没有游戏 ID 的角色草稿，只承载像素。

* ``work/studio-drafts/scratch-<slug>/``：自己的 changeset（``scratch`` 段记名字、属性、母本），
  占位代码 ``scratch_<slug>``，不写任何表行。
* 「当前视图」= 母本整族四件改名到占位代码（时间轴区间、锚点、frame.scale 都来自母本），
  像素工坊的拆解 / 母本映射 / 程序化动作 / 画板都在它上面工作。
* 导入：把现成的 pixelart/special 四件（文件夹或 zip）+ 可选映射表导成 ``pixel_family``
  （mode=import）改动；有映射表时逐端点对照「母本 + 映射表」，标出哪些动作是手绘。
* 绑定：选真实角色 ID 后，把全部像素改动改名到该角色代码，写进 ``work/studio-drafts/<cid>/``；
  只有绑定后的角色草稿能 ``draft build``，草稿角色本身永远不能生成交付。
"""
from __future__ import annotations

import copy
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path

from PIL import Image

from wf_pixelart_vfx import restore_frame

from .deliver_media import png, read_root
from .drafts import DraftError, now, sha256, validate
from .operations import DraftOps
from .pixel_workshop import (FAMILY_FILES, SPECIAL_REQUIRED, SQUAD_REQUIRED, UNIVERSAL_RANGES, decode_family,
                             family_paths, normalize_mapping, read_family_raw, remap_family)

SCRATCH_ID = re.compile(r"^scratch-[a-z0-9][a-z0-9-]{0,47}$")
_FRAME_NAME = re.compile(r"^character/([a-z0-9_]+)/pixelart/(pixelart|special)$")
ELEMENTS = ("火", "水", "雷", "风", "光", "暗")
IMPORT_LIMIT = 64 * 1024 * 1024


def is_scratch(cid: str | None) -> bool:
    return bool(SCRATCH_ID.match(cid or ""))


def placeholder_code(sid: str) -> str:
    return "scratch_" + sid[len("scratch-"):].replace("-", "_")


def slugify(name: str, base_code: str) -> str:
    ascii_part = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if ascii_part:
        return ascii_part[:40]
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:6]
    return f"{re.sub(r'[^a-z0-9]+', '-', base_code.lower()).strip('-')[:32]}-{digest}"


def resolve_character(ops: DraftOps, ref: str) -> dict:
    """角色 ID 或代码名 → {id, code, name, element}；只有像素文件、不在角色表的代码 id=None。"""
    ref = str(ref).strip()
    if ref.isdigit():
        return ops.character(ref)
    if is_scratch(ref):
        return ops.character(ref)
    for cid, rows in ops.source.table("character").items():
        if rows and rows[0] and rows[0][0] == ref:
            return ops.character(cid)
    if any(read_family_raw(ops.source, ref, family) is not None for family in FAMILY_FILES):
        return {"id": None, "code": ref, "name": ref, "element": ""}
    raise DraftError(f"找不到母本 {ref}：既不是角色 ID / 代码名，也没有像素文件")


class ScratchSource:
    """The view, plus the base family renamed to the placeholder code (identity remap)."""

    def __init__(self, source, code: str, base_code: str):
        self.source, self.code, self.base_code = source, code, base_code
        self.version = source.version
        self._families: dict[str, list[bytes] | None] = {}

    def _member(self, logical: str) -> bytes | None:
        for family in FAMILY_FILES:
            paths = family_paths(self.code, family)
            if logical in paths:
                if family not in self._families:
                    raws = read_family_raw(self.source, self.base_code, family)
                    self._families[family] = (remap_family(raws, self.base_code, self.code, {})["stored"]
                                              if raws is not None else None)
                stored = self._families[family]
                return stored[paths.index(logical)] if stored else None
        return None

    def read_root(self, root, logical):
        if logical.startswith(f"character/{self.code}/"):
            return self._member(logical) if root == "common" else None
        return read_root(self.source, root, logical)

    def raw(self, logical):
        if logical.startswith(f"character/{self.code}/"):
            return self._member(logical)
        return self.source.raw(logical)

    def table(self, name):
        return self.source.table(name)


class ScratchDraftOps(DraftOps):
    """DraftOps bound to one scratch draft: its own identity and ScratchSource."""

    def __init__(self, ops: DraftOps, sid: str):
        changeset = ops.store.load(sid) if is_scratch(sid) else None
        if not changeset or not changeset.get("scratch"):
            raise DraftError(f"没有草稿角色 {sid}（先「新建草稿角色」）")
        self.real, self.sid, self.meta, self.code = ops, sid, changeset["scratch"], changeset["code"]
        super().__init__(ScratchSource(ops.source, self.code, self.meta["base"]["code"]), store=ops.store,
                         assets=ops.assets, characters=ops.character_list)

    def character(self, cid: str) -> dict:
        if cid == self.sid:
            return {"id": self.sid, "code": self.code, "element": self.meta["element"], "name": self.meta["name"]}
        return self.real.character(cid)


def ops_for(ops: DraftOps, cid: str) -> DraftOps:
    return ScratchDraftOps(ops, cid) if is_scratch(cid) else ops


# ---------------------------------------------------------------------------
# 新建 / 列表

def create(ops: DraftOps, request: dict) -> dict:
    validate(request, "scratchCreateRequest")
    base = resolve_character(ops, request["base"])
    if not any(read_family_raw(ops.source, base["code"], f) is not None for f in FAMILY_FILES):
        raise DraftError(f"母本 {base['code']} 没有像素族，不能当母本")
    slug = request.get("slug") or slugify(request["name"], base["code"])
    sid = "scratch-" + slug
    if not is_scratch(sid):
        raise DraftError(f"草稿角色标识无效：{sid}")
    if ops.store.load(sid) is not None:
        raise DraftError(f"草稿角色 {sid} 已存在")
    stamp = now()
    changeset = {"schema": "wf-studio-draft/1", "characterId": sid, "code": placeholder_code(sid),
                 "baseView": ops.source.version, "createdAt": stamp, "updatedAt": stamp, "savedAt": None,
                 "revision": 0, "savedRevision": None, "changes": [],
                 "scratch": {"name": request["name"], "element": request["element"], "slug": slug,
                             "base": {"characterId": base["id"], "code": base["code"], "name": base["name"]},
                             "note": request.get("note", ""), "boundTo": None}}
    ops.store.create(sid, changeset)
    return describe(ops, sid)


def describe(ops: DraftOps, sid: str) -> dict:
    from .drafts import status
    changeset = ops.store.load(sid)
    if not changeset or not changeset.get("scratch"):
        raise DraftError(f"没有草稿角色 {sid}")
    return {"characterId": sid, "code": changeset["code"], "baseView": changeset["baseView"],
            "scratch": changeset["scratch"], "status": status(changeset),
            "changes": [{"id": c["id"], "kind": c["kind"], "title": c["title"]} for c in changeset["changes"]],
            "buildable": False,
            "note": "草稿角色没有游戏 ID、不写表；绑定到真实角色 ID 后才能生成交付。"}


def listing(ops: DraftOps) -> list[dict]:
    return [describe(ops, item["characterId"]) for item in ops.store.characters() if is_scratch(item["characterId"])]


# ---------------------------------------------------------------------------
# 导入

def read_bundle(*, directory: Path | None = None, zip_bytes: bytes | None = None,
                files: dict[str, bytes] | None = None) -> dict[str, bytes]:
    """Collect files by basename from a folder, a zip, or an upload map (last path segment wins once)."""
    found: dict[str, bytes] = {}
    total = 0

    def add(name: str, data: bytes):
        nonlocal total
        base = name.replace("\\", "/").rsplit("/", 1)[-1]
        if not base or base.startswith("."):
            return
        total += len(data)
        if total > IMPORT_LIMIT:
            raise DraftError("导入内容超过 64 MB")
        if base in found and found[base] != data:
            raise DraftError(f"导入内容里有两个不同的 {base}")
        found[base] = data

    if directory is not None:
        for path in sorted(Path(directory).rglob("*")):
            if path.is_file():
                add(path.name, path.read_bytes())
    if zip_bytes is not None:
        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
                for info in archive.infolist():
                    if not info.is_dir():
                        if info.file_size > IMPORT_LIMIT:
                            raise DraftError(f"zip 成员过大：{info.filename}")
                        add(info.filename, archive.read(info))
        except zipfile.BadZipFile as exc:
            raise DraftError(f"不是可读的 zip：{exc}") from None
    for name, data in (files or {}).items():
        add(name, data)
    return found


def family_sets(found: dict[str, bytes]) -> dict[str, list[bytes]]:
    sets = {}
    for family, (sheet, stem) in FAMILY_FILES.items():
        names = [sheet + ".png", sheet + ".atlas.amf3.deflate", stem + ".frame.amf3.deflate",
                 stem + ".timeline.amf3.deflate"]
        present = [n for n in names if n in found]
        if not present:
            continue
        if len(present) != 4:
            raise DraftError(f"{family} 四件不全：缺 {', '.join(n for n in names if n not in found)}")
        sets[family] = [found[n] for n in names]
    if not sets:
        raise DraftError("没有找到 sprite_sheet.png / pixelart.frame 等像素文件（按文件名识别）")
    return sets


def parse_remap_table(found: dict[str, bytes], explicit: dict | list | None) -> dict | None:
    """Optional table: {"base": code|id, "mapping": [...]|{...}} or a bare mapping."""
    value = explicit
    if value is None:
        for name in sorted(found):
            if name.endswith(".json") and ("remap" in name or "mapping" in name or "palette" in name):
                try:
                    value = json.loads(found[name].decode("utf-8-sig"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise DraftError(f"映射表 {name} 不是合法 JSON：{exc}") from None
                break
    if value is None:
        return None
    if isinstance(value, dict) and "mapping" in value:
        return {"base": value.get("base"), "mapping": normalize_mapping(value["mapping"])}
    return {"base": None, "mapping": normalize_mapping(value)}


def _old_code(raws: list[bytes]) -> str:
    from .deliver_media import tree
    frame = tree(raws[2])
    match = _FRAME_NAME.match(str(frame.get("name", "")))
    if not match:
        raise DraftError(f"frame.name 不是 character/<代码>/pixelart/<族> 形式：{frame.get('name')!r}")
    return match[1]


def validate_family(family: str, data: dict, reference: dict | None = None) -> list[dict]:
    """``reference`` = {name: (begin, end)} of the base; without one the universal ranges are used."""
    checks = []
    for key, entry in data["entries"].items():
        try:
            restore_frame(data["sheet"], entry)
        except ValueError as exc:
            raise DraftError(f"{family} 端点 {key} 越界或几何无效：{exc}") from None
    sequences = data["timeline"].get("sequences", []) or []
    names = {s.get("name") for s in sequences}
    for sequence in sequences:
        if not (type(sequence.get("begin")) is int and type(sequence.get("end")) is int
                and 1 <= sequence["begin"] <= sequence["end"] <= data["keys"][-1]):
            raise DraftError(f"{family}/{sequence.get('name')} 帧区间超出图集端点")
    required = SQUAD_REQUIRED if family == "pixelart" else SPECIAL_REQUIRED
    missing = [n for n in required if n not in names]
    if missing:
        checks.append({"level": "error" if family == "special" else "warn", "code": "workshop.missing_sequence",
                       "message": f"{family} 缺少必需动作 {', '.join(missing)}"})
    if data["frame"].get("scale") != 6:
        checks.append({"level": "warn", "code": "workshop.scale",
                       "message": f"{family} frame.scale = {data['frame'].get('scale')}（官方 6）"})
    ranges = reference if reference is not None else UNIVERSAL_RANGES[family]
    label = "母本" if reference is not None else "通用"
    odd = [f"{s['name']}={s['begin']}–{s['end']}" for s in sequences
           if ranges.get(s.get("name")) not in (None, (s["begin"], s["end"]))]
    extra = [s["name"] for s in sequences if reference is not None and s.get("name") not in ranges]
    if odd or extra:
        checks.append({"level": "warn", "code": "workshop.import_ranges",
                       "message": f"{family} 区间与{label}区间不同：{'，'.join(odd + [f'多出 {n}' for n in extra])}"})
    return checks


def provenance(ops: DraftOps, family: str, imported: dict, table: dict, base: dict, code: str) -> tuple[dict, list]:
    """Compare every endpoint with base + mapping: equal endpoints are the remap, others hand-drawn."""
    base_raws = read_family_raw(ops.source, base["code"], family)
    if base_raws is None:
        return {"base": base["code"], "comparable": False}, [{"level": "warn", "code": "workshop.import_provenance",
                                                              "message": f"母本 {base['code']} 没有 {family}，映射表无法对照"}]
    expected = decode_family(remap_family(base_raws, base["code"], code, table["mapping"])["stored"])
    from .pixel_workshop import _cells
    same, differ = 0, {}
    by_action = {}
    for sequence in imported["timeline"].get("sequences", []) or []:
        for key, _, _ in _cells(imported["keys"], sequence):
            by_action.setdefault(key, sequence["name"])
    for key in imported["keys"]:
        mine = restore_frame(imported["sheet"], imported["entries"][key])
        theirs = expected["entries"].get(key)
        if theirs is not None:
            other = restore_frame(expected["sheet"], theirs)
            if other.size == mine.size and other.tobytes() == mine.tobytes():
                same += 1
                continue
        action = by_action.get(key, "（序列外）")
        differ[action] = differ.get(action, 0) + 1
    result = {"base": base["code"], "comparable": True, "endpoints": len(imported["keys"]),
              "matchingEndpoints": same, "differingByAction": differ}
    message = (f"{family}：{same}/{len(imported['keys'])} 个端点与「母本 {base['code']} + 映射表」逐像素一致"
               + (f"；不同的端点（手绘或改动）：" + "，".join(f"{a} {n}" for a, n in differ.items()) if differ else "；全部一致"))
    return result, [{"level": "info", "code": "workshop.import_provenance", "message": message}]


def import_set(ops: DraftOps, cid: str, request: dict, *, found: dict[str, bytes] | None = None) -> dict:
    """``pixelImportRequest`` → one ``pixel_family`` (mode=import) per family found."""
    import base64
    validate(request, "pixelImportRequest")
    ops = ops_for(ops, cid)
    target = ops.character(cid)
    if found is None:
        uploads = {name: base64.b64decode(data, validate=True) for name, data in (request.get("files") or {}).items()}
        zip_bytes = base64.b64decode(request["zip"], validate=True) if request.get("zip") else None
        found = read_bundle(zip_bytes=zip_bytes, files=uploads)
    sets = family_sets(found)
    if request.get("families"):
        sets = {f: raws for f, raws in sets.items() if f in request["families"]}
        if not sets:
            raise DraftError("导入内容里没有所选的像素族")
    table = parse_remap_table(found, request.get("remap"))
    base_ref = (table or {}).get("base") or (ops.meta["base"]["code"] if isinstance(ops, ScratchDraftOps) else None)
    base = resolve_character(ops, base_ref) if base_ref else None
    results, built = [], []
    for family, raws in sets.items():
        old = _old_code(raws)
        try:
            rebuilt = remap_family(raws, old, target["code"], {})
            data = decode_family(rebuilt["stored"])
        except ValueError as exc:
            raise DraftError(f"{family} 四件解不开：{exc}") from None
        base_raws = read_family_raw(ops.source, base["code"], family) if base else None
        reference = ({s["name"]: (s["begin"], s["end"]) for s in decode_family(base_raws)["timeline"].get("sequences", [])}
                     if base_raws else None)
        checks = validate_family(family, data, reference)
        prov = None
        if table and base:
            prov, more = provenance(ops, family, data, table, base, target["code"])
            checks += more
        elif table:
            checks.append({"level": "warn", "code": "workshop.import_provenance",
                           "message": "映射表没有写母本、本草稿也没有母本：只记录，不对照"})
        if old != target["code"]:
            checks.append({"level": "info", "code": "workshop.import_renamed",
                           "message": f"{family} atlas/frame 名前缀 {old} → {target['code']}（{rebuilt['renamedEntries']} 条）"})
        item = {"family": family, "sourceCode": old, "endpoints": len(data["keys"]),
                "sheet": list(data["sheet"].size), "actions": [s["name"] for s in data["timeline"].get("sequences", [])],
                "checks": checks, "provenance": prov}
        results.append(item)
        built.append((family, raws, rebuilt, checks, prov, old))
    if request.get("dryRun"):
        return {"dryRun": True, "characterId": cid, "families": results,
                "remap": {"base": base["code"] if base else None, "colors": len(table["mapping"])} if table else None}
    if any(c["level"] == "error" for _, _, _, checks, _, _ in built for c in checks):
        raise DraftError("检查未通过：" + "；".join(c["message"] for _, _, _, checks, _, _ in built
                                                for c in checks if c["level"] == "error"))
    make = ops._file_maker(cid)
    committed = []
    name = str(request.get("name") or "导入")[:80]
    for family, raws, rebuilt, checks, prov, old in built:
        paths = family_paths(target["code"], family)
        files = [make(paths[0], "common", png_standard(rebuilt["stored"][0]), "png", approximate=False,
                      note=f"导入 {name}")]
        files += [make(p, "common", raw, "amf3-deflate", approximate=False, note="导入；只改名前缀")
                  for p, raw in zip(paths[1:], rebuilt["stored"][1:])]
        params = {"mode": "import", "source": {"name": name, "code": old,
                                               "files": {Path(p).name: sha256(r) for p, r in zip(family_paths(old, family), raws)}}}
        if table:
            params["mapping"] = [{"from": "#%02x%02x%02x" % k, "to": "#%02x%02x%02x" % v}
                                 for k, v in sorted(table["mapping"].items())]
        if base:
            params["base"] = {"characterId": base["id"], "code": base["code"]}
        if prov:
            params["provenance"] = prov
        change = {"title": f"像素整族 {family}：导入 {name}（{len(decode_family(rebuilt['stored'])['keys'])} 端点）",
                  "target": {"family": family}, "params": params, "files": files, "pending": [], "checks": checks}
        committed.append(ops._commit(cid, target["code"], "pixel_family", change))
    return {"characterId": cid, "families": results, "changes": [c["change"] for c in committed],
            "status": committed[-1]["status"]}


def png_standard(stored: bytes) -> bytes:
    import wf_assets
    return wf_assets.png_decode(stored)


# ---------------------------------------------------------------------------
# 绑定

def _draft_raws(store, sid: str, change: dict, code: str, family: str) -> list[bytes]:
    by_logical = {f["logical"]: f for f in change["files"]}
    raws = []
    for logical in family_paths(code, family):
        entry = by_logical.get(logical)
        data = store.read_file(sid, entry["draft"]) if entry else None
        if data is None or sha256(data) != entry["sha256"]:
            raise DraftError(f"草稿文件缺失或被改动：{logical}")
        raws.append(data)
    return raws


def bind(ops: DraftOps, sid: str, request: dict) -> dict:
    validate(request, "scratchBindRequest")
    scratch = ScratchDraftOps(ops, sid)
    changeset = ops.store.load(sid)
    meta = changeset["scratch"]
    if meta.get("boundTo"):
        raise DraftError(f"{sid} 已绑定到 {meta['boundTo']['characterId']}（{meta['boundTo']['code']}）；交付请对该角色 build")
    cid = request["characterId"]
    target = ops.character(cid)  # must exist in the view: building needs its table rows
    old, code = changeset["code"], target["code"]
    if not changeset["changes"]:
        raise DraftError("草稿角色还没有任何像素改动，没有可绑定的内容")
    plan = []
    for change in changeset["changes"]:
        if change["kind"] == "pixel_family":
            family = change["target"]["family"]
            raws = _draft_raws(ops.store, sid, change, old, family)
            rebuilt = remap_family(raws, old, code, {})
            params = copy.deepcopy(change["params"])
            if params.get("mode") == "remap":
                base_raws = read_family_raw(ops.source, params["base"]["code"], family)
                if base_raws is None:
                    raise DraftError(f"母本 {params['base']['code']} 缺 {family}")
                expected = remap_family(base_raws, params["base"]["code"], code, normalize_mapping(params["mapping"]))
                if (png(expected["stored"][0]).tobytes() != png(rebuilt["stored"][0]).tobytes()
                        or expected["stored"][1:] != rebuilt["stored"][1:]):
                    raise DraftError(f"{family} 母本映射与草稿不一致（母本变了？），请在草稿角色里重新映射")
            plan.append(("pixel_family", change, family, rebuilt, params))
        elif change["kind"] == "pixel_action":
            plan.append(("pixel_action", change, change["target"]["family"], None, None))
        else:
            raise DraftError(f"草稿角色只应有像素改动，遇到 {change['kind']}")
    summary = {"from": sid, "characterId": cid, "code": code, "name": target["name"],
               "renamed": f"character/{old}/ → character/{code}/",
               "changes": [{"kind": kind, "title": change["title"]} for kind, change, *_ in plan]}
    if request.get("dryRun"):
        return {"dryRun": True, **summary}
    make = ops._file_maker(cid)
    created = []
    for kind, change, family, rebuilt, params in plan:
        if kind == "pixel_family":
            paths = family_paths(code, family)
            files = [make(paths[0], "common", png_standard(rebuilt["stored"][0]), "png", approximate=False,
                          note=f"由草稿角色 {sid} 绑定")]
            files += [make(p, "common", raw, "amf3-deflate", approximate=False, note=f"由草稿角色 {sid} 绑定；改名前缀")
                      for p, raw in zip(paths[1:], rebuilt["stored"][1:])]
            built = {"title": change["title"] + f"（来自 {sid}）", "target": change["target"], "params": params,
                     "files": files, "pending": [], "checks": change["checks"]}
        else:
            frames = []
            for frame in change["params"]["frames"]:
                data = ops.store.read_file(sid, frame["file"])
                if data is None or sha256(data) != frame["sha256"]:
                    raise DraftError(f"草稿帧缺失或被改动：{frame['file']}")
                ops.store.write_file(cid, frame["file"], data)
                frames.append(dict(frame))
            params = {**copy.deepcopy(change["params"]), "frames": frames}
            pending = [{**p, "logical": p["logical"].replace(f"character/{old}/", f"character/{code}/")}
                       for p in change["pending"]]
            built = {"title": change["title"] + f"（来自 {sid}）", "target": change["target"], "params": params,
                     "files": [], "pending": pending, "checks": change["checks"]}
        created.append(ops._commit(cid, code, kind, built)["change"]["id"])
    meta = {**meta, "boundTo": {"characterId": cid, "code": code, "at": now(), "changes": created}}
    ops.store.update_scratch(sid, meta)
    return {**summary, "created": created, "draft": ops.draft(cid)["status"]}


BUILD_REFUSAL = ("草稿角色 {sid} 还没有绑定游戏角色 ID，不能生成交付：先「绑定到角色 ID」"
                 "（python -m wf.studio.draft scratch-bind {sid} --cid <角色ID>），再对该角色 build。")
BOUND_REFUSAL = "草稿角色 {sid} 已绑定到 {cid}：交付请对角色 {cid} build（草稿角色本身不生成交付）。"


def build_refusal(store, sid: str) -> str:
    changeset = store.load(sid)
    bound = (changeset or {}).get("scratch", {}).get("boundTo")
    return BOUND_REFUSAL.format(sid=sid, cid=bound["characterId"]) if bound else BUILD_REFUSAL.format(sid=sid)
