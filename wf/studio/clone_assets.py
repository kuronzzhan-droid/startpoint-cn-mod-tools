"""Clone the shared 37-asset matrix and validate acquisition actions."""
from __future__ import annotations

import wf_character_requirements as requirements
import wf_dsl
import wf_atf
from .deliver_media import read_root, tree
from .drafts import DraftError, sha256
from .pixel_workshop import SPECIAL_REQUIRED, decode_family, family_paths, read_family_raw, remap_family

LABELS = {"reuse": "复用母本", "pending": "待替换", "derived": "已派生"}


def _roots(logical):
    if logical.endswith(".atf.deflate"):
        return ("android",)
    if "/ui/" in logical and logical.endswith(".png"):
        return ("medium", "common")
    return ("common",)


def _replace(value, old, new):
    if isinstance(value, str):
        return value.replace(f"character/{old}/", f"character/{new}/")
    if isinstance(value, list):
        return [_replace(item, old, new) for item in value]
    if isinstance(value, dict):
        return {key: _replace(item, old, new) for key, item in value.items()}
    return value


def _renamed(raw, logical, old, new):
    if not logical.endswith(".amf3.deflate"):
        return raw
    before = tree(raw)
    after = _replace(before, old, new)
    if before == after:
        return raw
    return wf_atf.deflate(wf_dsl.encode_amf3(after))


def special_checks(source, code, rarity):
    if rarity < 4:
        return []
    try:
        raw = read_family_raw(source, code, "special")
    except (ValueError, KeyError, TypeError) as exc:
        return [{"level": "error", "code": "character.special", "message": "Incomplete special family: " + str(exc)}]
    if raw is None:
        return [{"level": "error", "code": "character.special", "message": "★4+ 获取演出缺少 special 四件"}]
    try:
        data = decode_family(raw)
        if not data["keys"]:
            raise ValueError("special has no frame endpoints")
    except (ValueError, KeyError, TypeError, IndexError) as exc:
        return [{"level": "error", "code": "character.special", "message": "Invalid special family: " + str(exc)}]
    timeline = data["timeline"]
    sequences = timeline.get("sequences", []) if isinstance(timeline, dict) else None
    if not isinstance(sequences, list) or any(not isinstance(item, dict) for item in sequences):
        return [{"level": "error", "code": "character.special", "message": "Invalid special sequences"}]
    by_name = {entry.get("name"): entry for entry in sequences}
    if len(by_name) != len(sequences):
        return [{"level": "error", "code": "character.special", "message": "Duplicate special action names"}]
    missing = [name for name in SPECIAL_REQUIRED if name not in by_name]
    if missing:
        return [{"level": "error", "code": "character.special", "message": "★4+ 获取演出缺少动作：" + ", ".join(missing)}]
    for name in SPECIAL_REQUIRED:
        sequence = by_name[name]
        begin, end = sequence.get("begin"), sequence.get("end")
        if type(begin) is not int or type(end) is not int or not 1 <= begin <= end <= data["keys"][-1]:
            return [{"level": "error", "code": "character.special", "message": f"获取动作 {name} 帧区间无效"}]
    return [{"level": "info", "code": "character.special", "message": "★4+ special_land / special_pose 已保留母本帧区间与 sequence.kind；未验证真机获取演出"}]


def collect_assets(source, old, new, rarity):
    members, inputs, checklist = {}, {}, []
    required = [item for item in requirements.char_asset_requirements(new) if item.category == "required"]
    assert len(required) == 37
    for item in required:
        logical = item.logical_path
        donor = logical.replace(f"character/{new}/", f"character/{old}/", 1)
        root, raw = None, None
        for candidate in _roots(donor):
            raw = read_root(source, candidate, donor)
            if raw is not None:
                root = candidate
                break
        status = "pending" if raw is None else "reuse"
        if raw is not None:
            inputs[f"{root}:{donor}"] = sha256(raw)
            members[root, logical] = _renamed(raw, logical, old, new)
            if members[root, logical] != raw:
                status = "derived"
        checklist.append({"logical": logical, "source": donor, "root": root or _roots(donor)[0],
                          "status": status, "label": LABELS[status]})
    # Rename frame and timeline references through the existing pixel-family remapper.
    for family in ("pixelart", "special"):
        paths = family_paths(old, family)
        raw = [read_root(source, "common", logical) for logical in paths]
        if all(item is not None for item in raw):
            rebuilt = remap_family(raw, old, new, {})["stored"]
            for logical, data in zip(family_paths(new, family), rebuilt):
                members["common", logical] = data
    # Fixed battle lines and speech paths remain useful after adopting a new code.
    from .voice import FIXED_LINES
    donors = {f"character/{old}/voice/{name}.mp3" for name in FIXED_LINES}
    for speech in source.table("master/character/character_speech.orderedmap").get(next((cid for cid, rs in source.table("character").items()
                                                   if rs and rs[0][0] == old), ""), []):
        if len(speech) == 5 and speech[4] and speech[4] != "(None)":
            voice = speech[4]
            donors.add((voice if voice.startswith("character/") else f"character/{old}/voice/{voice}") + ".mp3")
    for donor in sorted(donors):
        raw = read_root(source, "common", donor)
        if raw is not None:
            inputs[f"common:{donor}"] = sha256(raw)
            members["common", donor.replace(f"character/{old}/", f"character/{new}/", 1)] = raw
    checks = special_checks(source, old, rarity)
    missing = [item["logical"] for item in checklist if item["status"] == "pending"]
    if missing:
        checks.append({"level": "error", "code": "character.assets", "message": f"37 项资产缺 {len(missing)} 项：" + ", ".join(missing)})
    return members, inputs, checklist, checks


def checklist(changeset):
    clone = next((c for c in changeset["changes"] if c["kind"] == "character_clone"), None)
    if clone is None:
        raise DraftError("不是克隆角色草稿")
    changed = {entry["logical"] for c in changeset["changes"] if c["kind"] != "character_clone" for entry in c["files"]}
    portraits = {c["target"]["form"] for c in changeset["changes"] if c["kind"] == "portrait"}
    result = []
    for item in clone["params"]["assets"]:
        derived = item["logical"] in changed or (portraits and "illustration_setting_sprite_sheet" in item["logical"])
        status = "derived" if derived else item["status"]
        result.append({**item, "status": status, "label": LABELS[status]})
    return result
