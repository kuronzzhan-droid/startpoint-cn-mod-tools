'Incrementally export native character pixel previews for an existing public Wiki.\n\nOnly writes media/pixels/* and data/pixel-previews.{json,js}; never edits game data.\npython -X utf8 mod-tools/wf_wiki_pixels.py --output ${WF_ROOT}/out/MOD角色Wiki/site\n'
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from PIL import __version__ as PIL_VERSION
import wf_mod_tool as core
from wf_wiki_catalog_source import version_at
from wf_wiki_pixel_output import PixelOutput, checked_path, digest
from wf_wiki_pixel_render import RENDER_VERSION, render_actions
from wf_wiki_pixel_sources import PixelSources, source_revision

NOTE = "仅展示角色小人动作，不含战斗场景、弹道或命中效果。"


def export_pixels(repo, output, *, catalog=None, store=None, external_package=None):
    """Accept a public_catalog result; otherwise read existing output/data.json.

    Return the same public index written as JSON and window.WF_PIXEL_PREVIEWS.
    Every action includes a static poster and a hashed lossless WebP animation.
    Source hashes plus renderer version invalidate the per-character media cache.
    """
    repo = Path(repo).resolve()
    store = Path(store) if store else core.resolve_active_store()
    destination = PixelOutput(output, repo, store)
    catalog_path, catalog_raw = None, None
    if catalog is None:
        catalog_path = checked_path(destination.root / "data.json")
        catalog_raw = catalog_path.read_bytes()
        catalog = json.loads(catalog_raw)
    ids = [row.get("id") for row in catalog["characters"]]
    if not ids or any(not isinstance(cid, str) or not re.fullmatch(r"c[0-9a-f]{12}", cid) for cid in ids):
        raise ValueError("像素导出需要已匿名化的公开角色目录")
    if len(ids) != len(set(ids)):
        raise ValueError("公开角色目录存在重复角色")
    before = version_at(repo)
    sources = PixelSources(repo, store, destination.root, external_package)
    previous, characters = destination.previous(), {}
    renderer = f"wf-pixels-{RENDER_VERSION}/pillow-{PIL_VERSION}"
    for cid in ids:
        raw = sources.read(cid)
        revision = source_revision(raw, renderer)
        old = previous.get(cid) if isinstance(previous, dict) else None
        if destination.reusable(old, revision) and old.get("note") == NOTE:
            characters[cid] = old
            continue
        unavailable = []
        actions = render_actions(raw, destination.save, unavailable)
        characters[cid] = {"sourceRevision": revision, "poster": actions[0]["poster"],
                           "actions": actions, "unavailable": unavailable, "note": NOTE}
    sources.verify()
    if version_at(repo) != before:
        raise RuntimeError("导出期间游戏资源版本发生变化，请重新导出")
    if catalog_path and catalog_path.read_bytes() != catalog_raw:
        raise RuntimeError("导出期间公开角色目录发生变化，请重新导出")
    urls = {media["url"] for row in characters.values()
            for action in row["actions"] for media in (action, action["poster"])}
    result = {"format": 1, "version": before, "catalogVersion": catalog.get("meta", {}).get("version", ""),
              "revision": digest(json.dumps(characters, ensure_ascii=False, sort_keys=True).encode("utf-8")),
              "characters": characters, "summary": {"characters": len(characters),
                  "actions": sum(len(row["actions"]) for row in characters.values()),
                  "files": len(urls), "bytes": sum(destination.verified[url] for url in urls),
                  "unavailableActions": [{"characterId": cid, **item} for cid, row in characters.items()
                                         for item in row["unavailable"]]}}
    destination.publish(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--repo", default=Path(__file__).resolve().parents[1], type=Path)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--external-package", type=Path)
    args = parser.parse_args()
    result = export_pixels(args.repo, args.output, store=args.store, external_package=args.external_package)
    print(json.dumps({"version": result["version"], "revision": result["revision"], **result["summary"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
