"""Verify historical materialized view inputs against the original overlay recipe."""
import hashlib
import json
from pathlib import Path
from wf.paths import root_path
from .base149 import HistoricalView

def verify_halloween_view(observed_reads):
    source = root_path("out/万圣新角色-20261016")
    extras = [Path(line.strip()) for line in (source / "build/extra_zips.txt").read_text("utf-8").splitlines() if line.strip()]
    view = HistoricalView(tip=206, extra_zips=extras)
    meta = json.loads((source / "viewstore/viewstore.json").read_text("utf-8"))
    assert [p.name for p in view.zips] == meta["zips"], "historical overlay list drifted"
    base = (source / "viewstore").resolve()
    checked = []
    for filename in sorted(observed_reads):
        if not filename.is_relative_to(base) or filename.suffix == ".json":
            continue
        member = filename.relative_to(base).as_posix()
        old, origin = view.read_member(member)
        current = filename.read_bytes()
        assert old == current, f"materialized view drift: {member} ({origin})"
        checked.append({"member": member, "sha256": hashlib.sha256(current).hexdigest(), "source": origin})
    return {"tip": meta["tip"], "overlay_zip_count": len(view.zips), "verified_read_members": len(checked), "members": checked}


def local_api_origins():
    """Fail if a replay imported any WF API from an old external tool copy."""
    import sys
    from wf.paths import REPOSITORY
    root = REPOSITORY.resolve()
    archive = root / "archive/legacy"
    result = {}
    for name, module in tuple(sys.modules.items()):
        filename = getattr(module, "__file__", None)
        location = Path(filename).resolve() if filename else None
        if location is not None and location.is_relative_to(archive):
            raise ImportError(f"recipe imported archived code: {name} ({filename})")
        if not (name == "wf" or name.startswith(("wf.", "wf_", "recipes."))):
            continue
        if location is not None:
            if not location.is_relative_to(root):
                raise ImportError(f"recipe imported external WF API: {name} ({filename})")
            result[name] = location.relative_to(root).as_posix()
    return result
