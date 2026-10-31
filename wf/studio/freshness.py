"""Cheap read-only manifest freshness; never rebuild or hash a view."""
import json
from pathlib import Path

from wf.view.chain import manifest_tip, version


def freshness(source):
    result = {"loaded": source.version, "latest": None, "stale": False}
    view = getattr(source, "view", None)
    manifest = getattr(view, "manifest", None)
    if manifest is None:
        return result
    try:
        latest = manifest_tip(manifest, getattr(view, "search_dirs", []),
                              getattr(view, "base_version", "1.4.131"),
                              getattr(view, "manifests", None))
        header = json.loads(Path(manifest).read_text("utf-8-sig"))
        if header.get("cdn_version") is not None:
            latest = max((latest, header["cdn_version"]), key=version)
        stale = version(latest) > version(source.version)
        result.update(latest=latest, stale=stale)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result
