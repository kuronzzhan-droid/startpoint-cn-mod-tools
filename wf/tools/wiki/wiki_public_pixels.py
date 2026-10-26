"""Read-only, exact file plan for publishing the rendered Wiki pixel previews."""
from __future__ import annotations

import io
import json
from pathlib import Path
import re

from PIL import Image
from wf_wiki_categories import HIDDEN_CHARACTER_IDS
from wf_wiki_pixel_output import PixelOutput, checked_path, digest
from wf_wiki_pixels import NOTE
from wf_wiki_public import public_id

INDEX = "data/pixel-previews.js"
JSON_INDEX = "data/pixel-previews.json"
SHA = re.compile(r"[0-9a-f]{64}")


def require(condition, message):
    if not condition:
        raise ValueError(message)


class PublicPixelFiles(PixelOutput):
    """Reuse the exporter's shape/hash validator without creating output folders."""

    def __init__(self, source):
        self.root = checked_path(source)
        self.verified = {}


def pixel_plan(source: Path, catalog: dict) -> tuple[list[dict], dict, dict]:
    """Return files, watched hashes and audit; JSON index is watched but not copied.

    Only the fixed public script and media actually referenced by the current
    visible roster are allowed. Old chunks, orphan frames and source files never
    enter this plan. Missing or mismatched indices fail closed.
    """
    files = PublicPixelFiles(source)
    raw_json = files.path(JSON_INDEX).read_bytes()
    raw_js = files.path(INDEX).read_bytes()
    index = json.loads(raw_json)
    match = re.fullmatch(r"\s*window\.WF_PIXEL_PREVIEWS\s*=\s*(\{.*\})\s*;\s*", raw_js.decode("utf-8"), re.S)
    require(match is not None and json.loads(match[1]) == index, "像素 JSON 与脚本索引不同或脚本含额外代码")
    require(set(index) == {"format", "version", "catalogVersion", "revision", "characters", "summary"}
            and index["format"] == 1, "像素索引格式不受支持")
    version = catalog["meta"]["version"]
    require(index["version"] == index["catalogVersion"] == version, "像素索引与角色目录版本不同")
    visible = [row["id"] for row in catalog["characters"]]
    require(visible and len(set(visible)) == len(visible)
            and all(isinstance(cid, str) and re.fullmatch(r"c[0-9a-f]{12}", cid) for cid in visible),
            "像素发布需要唯一公开角色目录")
    require(not set(visible) & {public_id("c", cid) for cid in HIDDEN_CHARACTER_IDS}, "像素目录含隐藏角色")
    characters = index["characters"]
    require(isinstance(characters, dict) and set(characters) == set(visible), "像素索引与可见角色白名单不同")
    expected_revision = digest(json.dumps(characters, ensure_ascii=False, sort_keys=True).encode("utf-8"))
    require(index["revision"] == expected_revision, "像素索引摘要不同")
    unavailable, actions_count = [], 0
    decoded = {}

    def first_frame(media):
        url = media["url"]
        if url not in decoded:
            with Image.open(io.BytesIO(files.path(url).read_bytes())) as image:
                require(image.format == "WEBP", "像素媒体并非 WebP")
                frame = image.convert("RGBA")
                # Animated WebP may discard RGB under fully transparent pixels.
                # Compare visible RGBA only; differing invisible RGB is harmless.
                frame.paste((0, 0, 0, 0), mask=frame.getchannel("A").point(lambda alpha: 0 if alpha else 255))
                decoded[url] = (frame.size, digest(frame.tobytes()), image.n_frames)
        value = decoded[url]
        require(value[0] == (media["width"], media["height"]), "像素媒体尺寸与索引不同")
        return value

    for cid, row in characters.items():
        revision = row.get("sourceRevision") if isinstance(row, dict) else None
        require(isinstance(revision, str) and SHA.fullmatch(revision)
                and row.get("note") == NOTE and files.reusable(row, revision), "像素条目结构、来源摘要或媒体哈希无效")
        require(row["poster"] == row["actions"][0]["poster"], "角色默认首帧不是首个动作预览")
        for action in row["actions"]:
            poster, animation = first_frame(action["poster"]), first_frame(action)
            require(poster[2] == 1 and poster[:2] == animation[:2], "像素首帧与动作不一致")
            require(action["animated"] == (animation[2] > 1), "像素动画标志与媒体不同")
        actions_count += len(row["actions"])
        unavailable.extend({"characterId": cid, **item} for item in row["unavailable"])
    summary = {"characters": len(characters), "actions": actions_count,
               "files": len(files.verified), "bytes": sum(files.verified.values()),
               "unavailableActions": unavailable}
    require(index["summary"] == summary, "像素汇总与实际引用不同")
    plan = [{"path": INDEX, "bytes": len(raw_js), "sha256": digest(raw_js)}]
    plan += [{"path": url, "bytes": size, "sha256": Path(url).stem}
             for url, size in sorted(files.verified.items())]
    watched = {INDEX: digest(raw_js), JSON_INDEX: digest(raw_json)}
    return plan, watched, {**summary, "revision": index["revision"], "publicIndex": INDEX,
                           "jsonIndexExcluded": True, "mediaHashVerified": True}
