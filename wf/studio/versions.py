"""Next chain version, skipping the repository's explicit version reservations."""
import json
import re
from pathlib import Path

from .drafts import DraftError, REPOSITORY

DEFAULT_RESERVATIONS = REPOSITORY / "release-contracts/version-reservations.json"


def read_reservations(filename=None):
    location = Path(filename) if filename is not None else DEFAULT_RESERVATIONS
    if not location.is_file():
        if filename is not None:
            raise DraftError(f"版本预留文件不存在: {location}")
        return {}, location
    import jsonschema
    try:
        document = json.loads(location.read_text("utf-8-sig"))
    except (ValueError, OSError) as exc:
        raise DraftError(f"无法读取版本预留登记 {location}: {exc}") from exc
    schema = json.loads((REPOSITORY / "schemas/version-reservations.schema.json").read_text("utf-8"))
    problems = list(jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).iter_errors(document))
    if problems:
        raise DraftError(f"版本预留登记无效 {location}: {problems[0].message}")
    if any(not re.fullmatch(r"1\.4\.(0|[1-9][0-9]*)", value) for value in document):
        raise DraftError(f"版本预留登记版本号不得有前导零: {location}")
    return document, location


def declared_versions(source):
    """An older selected tip must not reallocate later manifest declarations."""
    from wf.view.chain import ARCHIVE, manifest_entries, VERSION
    view = getattr(source, "view", None)
    manifest = getattr(view, "manifest", None)
    if manifest is None:
        active = getattr(view, "active", None)
        if active is None:
            return {}
        result = {}
        try:
            for archive in Path(active).iterdir():
                match = ARCHIVE.fullmatch(archive.name)
                if match and archive.is_file() and "candidate" not in archive.name:
                    for version in match.group(1, 2):
                        result[version] = {"source": "active", "location": str(archive)}
        except OSError as exc:
            raise DraftError(f"无法读取历史视图版本目录 {active}: {exc}") from exc
        return result
    try:
        entries = manifest_entries(manifest, view.search_dirs, view.manifests)
    except (ValueError, OSError) as exc:
        raise DraftError(f"无法读取视图版本登记 {manifest}: {exc}") from exc
    return {entry["version"]: {"source": "manifest", "location": str(manifest)}
            for entry in entries if isinstance(entry.get("version"), str)
            and VERSION.fullmatch(entry["version"])}


def next_version(source, *, view_name=None, reservations_file=None):
    current = str(source.version)
    match = re.fullmatch(r"(\d+\.\d+)\.(\d+)", current)
    if not match:
        raise DraftError(f"视图版本无效: {current}")
    reservations, location = read_reservations(reservations_file)
    allocated = declared_versions(source)
    patch = int(match[2]) + 1
    skipped = []
    while f"{match[1]}.{patch}" in reservations or f"{match[1]}.{patch}" in allocated:
        version = f"{match[1]}.{patch}"
        skipped.append({"version": version, **reservations.get(version, allocated.get(version, {}))})
        patch += 1
    return {"view": view_name or getattr(getattr(source, "view", None), "view_name", None),
            "current": current, "next": f"{match[1]}.{patch}",
            "skipped": skipped, "reservationsFile": str(location), "reserved": False}
