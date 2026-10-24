"""像素导入批量预检：一次检查一整批逐帧 PNG，按文件名归到动作槽。

画师交来的通常是一个文件夹 / zip：``neutral_01.png``、``walk_front/03.png``……
这里在写草稿之前把整批过一遍：

* 文件名 → 动作槽 + 帧号（``<动作>_<帧号>.png``、``<动作>-<帧号>.png``、
  ``<动作>/<帧号>.png``、``<动作>.png`` 单帧）；认不出的单列，不猜；
* ``_sp`` 后缀（``neutral_sp_01.png``、``neutral_01_sp.png``、``neutral_sp/01.png``）
  是本体 + 特效 / 召唤物的**合成帧**：只报出来，绝不归进待机这类基础动作；
* 每个动作逐帧走单动作替换同一套规则（``PixelImporter.check`` = 生成时的规则），
  停留帧数按原动作总长均分（非末尾动作改总长会挤动其它槽）；
* 每个动作可以标「带召唤物」和用途：没标但可见宽度明显超过原动作时提示
  「可能带召唤物」，标了就不再按体型报放大，并把标记写进草稿改动的 ``origin``。

``apply`` 时只把没有错误的动作逐个写成单动作替换（``pixel_action``），
与在「单动作替换」页一个个保存完全相同。
"""
from __future__ import annotations

import base64
import binascii
import io
import re
import zipfile

from PIL import Image

from .drafts import DraftError
from .pixel_import import default_anchor
from .pixels import SLOT_LABEL

IMPORT_LIMIT = 64 * 1024 * 1024
COMPANION_WIDTH_RATIO = 1.6
# Actions every playable character's base family carries (special_* live in the special family).
BASE_SLOTS = ("neutral", "walk_front", "walk_back", "skill_ready", "kachidoki", "into_coffin",
              "ghost_raise", "ghost_neutral", "revive")
_NAME = re.compile(r"^(?P<action>[a-z][a-z_]*?)(?P<sp>_sp)?(?:[_\-. ]?(?P<index>\d{1,4}))?(?P<sp2>_sp)?$")
_INDEX = re.compile(r"^(?P<index>\d{1,4})(?P<sp>_sp)?$")


def parse_name(path: str) -> dict | None:
    """``walk_front_03.png`` / ``walk_front/03.png`` / ``neutral_sp_01.png`` → action, index, composite."""
    parts = [p for p in path.replace("\\", "/").split("/") if p]
    if not parts or not parts[-1].lower().endswith(".png"):
        return None
    stem = parts[-1][:-4].lower()
    folder = parts[-2].lower() if len(parts) > 1 else None
    hit = _INDEX.match(stem)
    if hit and folder:
        action, sp = folder, folder.endswith("_sp") or bool(hit.group("sp"))
        action = action.removesuffix("_sp")
        if not re.fullmatch(r"[a-z][a-z_]*", action):
            return None
        return {"action": action, "index": int(hit.group("index")), "composite": sp}
    hit = _NAME.match(stem)
    if not hit:
        return None
    composite = bool(hit.group("sp") or hit.group("sp2")) or bool(folder and folder.endswith("_sp"))
    index = hit.group("index")
    return {"action": hit.group("action"), "index": int(index) if index is not None else None,
            "composite": composite}


def collect(request: dict) -> dict[str, bytes]:
    """Upload map and/or zip → {relative path: bytes} (paths kept: folders name the action)."""
    found: dict[str, bytes] = {}
    total = 0

    def add(name: str, data: bytes):
        nonlocal total
        name = name.replace("\\", "/").lstrip("/")
        if not name or any(part.startswith(".") or part == "__MACOSX" for part in name.split("/")):
            return
        total += len(data)
        if total > IMPORT_LIMIT:
            raise DraftError("这一批超过 64 MB")
        found[name] = data

    try:
        for name, text in (request.get("files") or {}).items():
            add(str(name), base64.b64decode(text, validate=True))
        if request.get("zip"):
            with zipfile.ZipFile(io.BytesIO(base64.b64decode(request["zip"], validate=True))) as archive:
                for info in archive.infolist():
                    if info.is_dir():
                        continue
                    if info.file_size > IMPORT_LIMIT:
                        raise DraftError(f"zip 成员过大：{info.filename}")
                    add(info.filename, archive.read(info))
    except (binascii.Error, ValueError) as exc:
        raise DraftError(f"上传内容不是合法 base64：{exc}") from None
    except zipfile.BadZipFile as exc:
        raise DraftError(f"zip 打不开：{exc}") from None
    if not found:
        raise DraftError("这一批里没有文件")
    return found


def spread(total: int, count: int) -> list[int]:
    """Split ``total`` timeline frames over ``count`` images (the remainder goes to the last ones)."""
    base = max(1, total // count)
    out = [base] * count
    rest = total - base * count
    for i in range(count - 1, -1, -1):
        if rest <= 0:
            break
        out[i] += 1
        rest -= 1
    return out


def _decode(data: bytes, name: str) -> Image.Image:
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except OSError as exc:
        raise ValueError(f"{name} 不是可读的图片：{exc}") from None
    if image.format != "PNG":
        raise ValueError(f"{name} 不是 PNG")
    return image.convert("RGBA")


def _png_b64(image: Image.Image) -> str:
    out = io.BytesIO()
    image.save(out, "PNG")
    return base64.b64encode(out.getvalue()).decode("ascii")


def precheck(ops, cid: str, request: dict) -> dict:
    """Group a batch by action, run the single-action rules per action, optionally save the clean ones."""
    family = request.get("family") or "pixelart"
    if family not in ("pixelart", "special"):
        raise DraftError(f"未知像素族：{family}")
    marks = request.get("actions") or {}
    if not isinstance(marks, dict):
        raise DraftError("actions 需要是 {动作: {includesCompanion, purpose}}")
    files = collect(request)
    info = ops.character(cid)
    importer = ops._pixel_importer(cid, family)
    data = importer.family_frames(info["code"], family)
    if data is None:
        raise DraftError(f"这个角色没有 {family} 像素族，不能按动作槽替换")
    sequences = {s.get("name"): s for s in data["timeline"].get("sequences", [])}

    groups: dict[str, list[tuple[int | None, str]]] = {}
    composite: list[dict] = []
    unmatched: list[str] = []
    ignored: list[str] = []
    for name in sorted(files):
        if not name.lower().endswith(".png"):
            ignored.append(name)
            continue
        parsed = parse_name(name)
        if parsed is None:
            unmatched.append(name)
        elif parsed["composite"]:
            composite.append({"file": name, "action": parsed["action"], "index": parsed["index"]})
        else:
            groups.setdefault(parsed["action"], []).append((parsed["index"], name))

    checks: list[dict] = []
    if composite:
        actions = sorted({c["action"] for c in composite})
        checks.append({"level": "warn", "code": "precheck.composite",
                       "message": f"{len(composite)} 个 _sp 合成帧（本体 + 特效/召唤物合成）没有归进任何动作："
                                  f"{'、'.join(actions)}。合成帧不能当待机等基础动作导入；要用请拆开本体再交"})
    if unmatched:
        checks.append({"level": "warn", "code": "precheck.unmatched",
                       "message": f"{len(unmatched)} 个文件名认不出动作（应为 动作_帧号.png 或 动作/帧号.png）："
                                  + "、".join(unmatched[:8]) + ("……" if len(unmatched) > 8 else "")})

    results = []
    for action in sorted(groups, key=lambda a: (a not in SLOT_LABEL, list(SLOT_LABEL).index(a) if a in SLOT_LABEL else 0, a)):
        entries = groups[action]
        indexed = [i for i, _ in entries if i is not None]
        ordered = sorted(entries, key=lambda e: (e[0] is None, e[0] if e[0] is not None else 0, e[1]))
        mark = marks.get(action) if isinstance(marks.get(action), dict) else {}
        companion = bool(mark.get("includesCompanion"))
        purpose = str(mark.get("purpose") or "")[:200]
        item = {"action": action, "label": SLOT_LABEL.get(action), "files": [n for _, n in ordered],
                "includesCompanion": companion, "purpose": purpose, "checks": [], "frames": len(ordered)}
        results.append(item)
        local = item["checks"]
        if action not in SLOT_LABEL:
            local.append({"level": "error", "code": "precheck.unknown_slot",
                          "message": f"{action} 不是官方动作槽名"})
            continue
        sequence = sequences.get(action)
        if sequence is None:
            local.append({"level": "error", "code": "precheck.missing_slot",
                          "message": f"这个角色的 {family} 族没有 {action} 动作槽（只能替换已有动作）"})
            continue
        if len(set(indexed)) != len(indexed):
            local.append({"level": "error", "code": "precheck.duplicate_index", "message": "帧号重复"})
        elif indexed and sorted(indexed) != list(range(min(indexed), min(indexed) + len(indexed))):
            local.append({"level": "warn", "code": "precheck.index_gap",
                          "message": f"帧号不连续：{sorted(indexed)}"})
        if indexed and len(indexed) != len(entries):
            local.append({"level": "warn", "code": "precheck.mixed_naming",
                          "message": "同一动作里有的文件带帧号、有的不带：不带帧号的排在最后"})
        frames, bad = [], False
        for _, name in ordered:
            try:
                frames.append(_decode(files[name], name))
            except ValueError as exc:
                local.append({"level": "error", "code": "precheck.decode", "message": str(exc)})
                bad = True
        if bad or not frames:
            continue
        box = tuple(int(v) for v in _box(importer, info["code"], family))
        origin = (-int(data["frame"].get("x", 0)), -int(data["frame"].get("y", 0)))
        anchors = [list(origin) if f.size == box else default_anchor([f]) for f in frames]
        total = sequence["end"] - sequence["begin"] + 1
        durations = spread(total, len(frames))
        if len(frames) > total:
            local.append({"level": "error", "code": "precheck.too_many_frames",
                          "message": f"{len(frames)} 帧比原动作总长 {total} 个时间轴帧还多"})
            continue
        try:
            checked = importer.check(info["code"], family, action, frames, durations, anchors=anchors)
        except DraftError as exc:
            local.append({"level": "error", "code": "precheck.check", "message": str(exc)})
            continue
        own = checked["checks"]
        widths = [b[2] - b[0] for b in (f.getbbox() for f in frames) if b]
        old_w = _old_width(data, sequence)
        if companion:
            own = [c for c in own if c["code"] != "pixel.scale"]
            local.append({"level": "info", "code": "precheck.companion",
                          "message": "已标「带召唤物」：召唤物与本体同帧，锚点按本体脚底；体型提示已略过"})
        elif old_w and widths and max(widths) > old_w * COMPANION_WIDTH_RATIO:
            local.append({"level": "warn", "code": "precheck.companion_suspect",
                          "message": f"可见宽度 {max(widths)}px，原动作 {old_w}px：可能带召唤物或特效；是的话请标「带召唤物」"})
        local.extend(own)
        item.update(durations=durations, anchors=anchors, totalFrames=total,
                    sizes=sorted({f"{f.width}×{f.height}" for f in frames}), budget=checked["budget"])
        item["_frames"] = frames

    present = set(groups)
    if family == "pixelart":
        missing = [a for a in BASE_SLOTS if a in sequences and a not in present]
        if missing:
            checks.append({"level": "info", "code": "precheck.not_provided",
                           "message": "这批没有给：" + "、".join(f"{SLOT_LABEL[a]}（{a}）" for a in missing)
                                      + "，这些动作保持原样"})
    for item in results:
        item["ok"] = "_frames" in item and not any(c["level"] == "error" for c in item["checks"])

    saved = []
    if request.get("apply"):
        ready = [item for item in results if item["ok"]]
        if not ready:
            raise DraftError("没有可写入的动作（每个动作都有错误或没有帧）")
        for item in ready:
            body = {"family": family, "action": item["action"],
                    "frames": [{"png": _png_b64(f), "duration": d, "anchor": a}
                               for f, d, a in zip(item["_frames"], item["durations"], item["anchors"])],
                    "origin": {"mode": "batch", "files": item["files"],
                               "includesCompanion": item["includesCompanion"],
                               **({"purpose": item["purpose"]} if item["purpose"] else {})}}
            result = ops.pixel_save(cid, body)
            saved.append({"action": item["action"], "change": result.get("change", {}).get("id")})
    for item in results:
        item.pop("_frames", None)
    counts = {level: sum(1 for c in checks + [c for i in results for c in i["checks"]] if c["level"] == level)
              for level in ("error", "warn", "info")}
    return {"characterId": cid, "family": family, "actions": results, "composite": composite,
            "unmatched": unmatched, "ignored": ignored, "checks": checks, "counts": counts,
            "ready": [i["action"] for i in results if i["ok"]], "saved": saved, "applied": bool(saved)}


def _box(importer, code: str, family: str) -> tuple[int, int]:
    from .deliver_pixel import frame_box
    data = importer.family_frames(code, family)
    return frame_box(data["entries"], data["keys"])


def _old_width(data: dict, sequence: dict) -> int:
    from bisect import bisect_left
    keys, entries = data["keys"], data["entries"]
    used = {keys[bisect_left(keys, pos)] for pos in range(sequence["begin"], sequence["end"] + 1) if pos <= keys[-1]}
    return max((int(entries[k]["h"] if entries[k].get("r") else entries[k]["w"]) for k in used), default=0)
