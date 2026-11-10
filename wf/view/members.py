"""Canonical CDN names for current and legacy patch archives."""
import re

CDN_ROOTS = ("upload", "small_upload", "medium_upload", "android_upload", "ios_upload")
CDN_MEMBER = re.compile(r"^production/(upload|small_upload|medium_upload|android_upload|ios_upload)/[0-9a-f]{2}/[0-9a-f]{38}$")
LEGACY_MEMBER = re.compile(r"^[0-9a-f]{2}/[0-9a-f]{38}$")


# Root-level bookkeeping files that patch builders add next to CDN members:
# ".empty" marks an intentionally empty archive, ".integrity.json" lists member hashes (1.4.367+).
METADATA_MEMBERS = frozenset({".empty", ".integrity.json"})


def canonical_member(name):
    if name in METADATA_MEMBERS:
        return None
    if LEGACY_MEMBER.fullmatch(name):
        return "production/upload/" + name
    if not CDN_MEMBER.fullmatch(name):
        raise ValueError(f"invalid CDN member: {name}")
    return name


def archive_members(archive):
    """Map canonical names to ZIP names, rejecting aliases within one archive."""
    result, seen = {}, set()
    for info in archive.infolist():
        if info.is_dir():
            continue
        name = info.filename
        if name in seen:
            raise ValueError(f"duplicate ZIP member: {name}")
        seen.add(name)
        canonical = canonical_member(name)
        if canonical is None:
            continue
        if canonical in result:
            raise ValueError(f"duplicate ZIP member after normalization: {canonical}")
        result[canonical] = name
    return result
