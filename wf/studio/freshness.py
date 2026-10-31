"""Cheap read-only manifest freshness; never rebuild or hash a view."""
from wf.view.chain import manifest_entries, version


def freshness(source):
    result = {"loaded": source.version, "latest": None, "stale": False}
    view = getattr(source, "view", None)
    manifest = getattr(view, "manifest", None)
    if manifest is None:
        return result
    try:
        entries = manifest_entries(manifest, getattr(view, "search_dirs", []),
                                   getattr(view, "manifests", []))
        versions = [entry["version"] for entry in entries
                    if entry.get("enabled", True) is not False and entry.get("version") is not None]
        latest = max(versions, key=version) if versions else None
        result["latest"] = latest
        result["stale"] = latest is not None and version(latest) > version(source.version)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result
