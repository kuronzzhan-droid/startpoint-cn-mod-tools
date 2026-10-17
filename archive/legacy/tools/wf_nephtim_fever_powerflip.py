"""奈芙提姆私有特殊型＋辅助型PF；只生成三档程序与原生特效副本。"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import io
from pathlib import Path
import zipfile
import zlib

import wf_dsl
from wf_mod_tool import sha1_path
from wf_client_legality import (
    action_dsl_element_problems,
    action_dsl_hit_area_target_problems,
    action_dsl_subject_binding_problems,
)

CODE = "ruin_girl_campus"
PF_ID = CODE + "_fever"
PF_STRING_ID = PF_ID + "_powerflip"
SUFFIX = ".action.dsl.amf3.deflate"
PROGRAM_PATHS = tuple(
    f"battle/action/power_flip/action/override/{PF_ID}${PF_ID}_lv{level}"
    for level in (1, 2, 3)
)
SOURCE_HASHES = {
    ("special", 1): "569f2082c4633bae7e71610c296d6ab141cfabe1f3c4e5e0034c46dbf3e22961",
    ("special", 2): "4ed6440b9ded6d435e2c2fb9a640541b2c3fc43c5c0068de41077bab07ad73f2",
    ("special", 3): "7bebfdd5fc3ff46f2a789f7d631ac02084afa0cd11f4f19f71037f7faba3447d",
    ("supporter", 1): "810c651c45d59324d435ec335d4071b779d6dc1ef2f80545eb9a6a98ae622a1b",
    ("supporter", 2): "a12e7b71ce3036a80d85550623665180caaf96a2c0ca30d48f6d4669a13dc4a5",
    ("supporter", 3): "ea73c6a5d745b582fc6419b49dd7ceaca0b2919ea7612a4224f9bb676bd61fff",
}
_EFFECT_ROOT = "battle/effect/powerflip/"
_FAMILIES = ("effect_powerflip_attack_special", "effect_powerflip_attack_support")
_SUBJECT_SLOTS = {
    "FindAllSubjects": (1,), "ShowEffect": (3,), "CreateCondition": (1,),
    "CreateNormalAttack": (1,), "CreateHitArea": (2, 19, 21, 22),
}
# 作者 2026-09-27 第二批 Down 口径 B.2：强化弹射每级削韧上限 15/20/25。Lv3 = 特殊型 6.25×3 + 6.25×1
# + 辅助型末段 1×1 = 26，超上限 1 → 辅助型末段 CreateNormalAttack 的削韧 p13 1 → 0（= 25）；
# 其余参数与 Lv1/Lv2（15/20，正好顶格）逐字不动。
SUPPORTER_TOUGHNESS = {3: (1, 0)}   # 档位 -> (原削韧, 新削韧)


def _supporter_toughness(donor, level):
    """只改辅助型载荷里 CreateNormalAttack 的 p13（按 SLv 的 {min,max} 都改）。"""
    if level not in SUPPORTER_TOUGHNESS:
        return
    old, new = SUPPORTER_TOUGHNESS[level]
    attacks = list(wf_dsl.iter_dsl_commands(donor, "CreateNormalAttack"))
    if len(attacks) != 1 or attacks[0][13] != [{"min": old, "max": old}]:
        raise ValueError(f"supporter PF level {level} toughness preimage drift")
    attacks[0][13] = [{"min": new, "max": new}]


def source_path(kind, level):
    if (kind, level) not in SOURCE_HASHES:
        raise ValueError("expected native special/supporter PF level 1, 2 or 3")
    return f"battle/action/power_flip/action/{kind}${kind}_lv{level}" + SUFFIX


def private_path(path):
    for family in _FAMILIES:
        if path.startswith(_EFFECT_ROOT + family + "/"):
            return _EFFECT_ROOT + PF_ID + "/" + path[len(_EFFECT_ROOT):]
    return path


def _private_references(value):
    if isinstance(value, str):
        return private_path(value)
    if isinstance(value, list):
        return [_private_references(item) for item in value]
    if isinstance(value, dict):
        return {key: _private_references(item) for key, item in value.items()}
    return value


def _decode(raw):
    return wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]


def _encode(tree):
    raw = wf_dsl.encode_amf3(tree)
    if wf_dsl.parse_dsl(raw)["tree"] != tree:
        raise ValueError("native PF AMF3 roundtrip mismatch")
    encoder = zlib.compressobj(9, zlib.DEFLATED, -15)
    return encoder.compress(raw) + encoder.flush()


def _load_source(loader, kind, level):
    raw = loader(source_path(kind, level))
    if not isinstance(raw, bytes) or hashlib.sha256(raw).hexdigest() != SOURCE_HASHES[kind, level]:
        raise ValueError(f"official {kind} PF level {level} fingerprint mismatch")
    return _decode(raw)


def with_bundle_fallback(loader, bundle_path):
    """显式选择本机bundle.zip或APK；只读，不提取或复制整个APK。"""
    source = Path(bundle_path)
    with zipfile.ZipFile(source) as archive:
        inner = archive.read("assets/bundle.zip") if "assets/bundle.zip" in archive.namelist() else None
    def archive_reader():
        return zipfile.ZipFile(io.BytesIO(inner)) if inner is not None else zipfile.ZipFile(source)
    with archive_reader() as archive:
        names = archive.namelist()
    cache = {}
    def read(logical):
        try:
            raw = loader(logical)
        except FileNotFoundError:
            raw = None
        if raw is not None:
            return raw
        if logical not in cache:
            digest = sha1_path(logical)
            tail = digest[:2] + "/" + digest[2:]
            matches = [name for name in names if name.endswith("/" + tail) or name == tail]
            if len(matches) != 1:
                raise ValueError(f"missing or ambiguous bundle asset: {logical}")
            with archive_reader() as archive:
                cache[logical] = archive.read(matches[0])
        return cache[logical]
    return read


def _effect_references(node):
    if isinstance(node, list):
        if node and node[0] == "SpecifyEffectDirectly":
            yield node[1]
        for child in node:
            yield from _effect_references(child)


def _supporter_payload(node):
    """特殊型负责结束计数；辅助只移除其结束通知并隔离正数主体槽。"""
    if not isinstance(node, list) or not node:
        return
    if node[0] == "Block":
        kept = []
        for entry in node[1]:
            if entry[0] == "Command" and entry[1][0] == "NotifyPowerflipEnd":
                continue
            _supporter_payload(entry)
            if entry[0] == "Event" and entry[1][0] == "Wait" and not entry[1][3][1]:
                continue
            kept.append(entry)
        node[1] = kept
        return
    if node[0] in ("Command", "Event"):
        command = node[1]
        for index in _SUBJECT_SLOTS.get(command[0], ()):
            if command[index] >= 0:
                command[index] += 200
        if command[0] == "ShowEffect":
            command[1] += "_nephtim_support"
    for child in node:
        if isinstance(child, list):
            _supporter_payload(child)


def build_power_flip(level, official_bytes_loader):
    """同档特殊型原树完整保留，发射时同时启动该档辅助型全部效果。"""
    base = _load_source(official_bytes_loader, "special", level)
    donor = deepcopy(_load_source(official_bytes_loader, "supporter", level)[11])
    _supporter_payload(donor)
    _supporter_toughness(donor, level)
    base[11][1].extend(donor[1])
    tree = _private_references(base)
    problems = (action_dsl_element_problems(tree, character_element=5)
                + action_dsl_hit_area_target_problems(tree)
                + action_dsl_subject_binding_problems(tree))
    if problems:
        raise ValueError("; ".join(problems))
    return tree


def power_flip_rows():
    return {PF_ID: [list(PROGRAM_PATHS)]}


def flat_string_rows():
    return {PF_STRING_ID: [["特殊型强化弹射与辅助型强化弹射同时生效，保留各档原有效果。"]]}


def action_assets(official_bytes_loader, *, bundle_path=None):
    """loader需可读取官方CDN及内置bundle；全部写入路径均为角色私有路径。"""
    if bundle_path is not None:
        official_bytes_loader = with_bundle_fallback(official_bytes_loader, bundle_path)
    result = {}
    effects = set()
    for level, program in enumerate(PROGRAM_PATHS, 1):
        tree = build_power_flip(level, official_bytes_loader)
        result["common", program + SUFFIX] = _encode(tree)
        effects.update(_effect_references(tree))
    source_effects = {
        effect.replace(_EFFECT_ROOT + PF_ID + "/", _EFFECT_ROOT, 1)
        for effect in effects
    }
    paths = set()
    for effect in source_effects:
        family = effect.rsplit("/", 1)[0]
        if family not in {_EFFECT_ROOT + name for name in _FAMILIES}:
            raise ValueError(f"unexpected native PF effect family: {effect}")
        paths.update(effect + suffix for suffix in
                     (".parts.amf3.deflate", ".timeline.amf3.deflate"))
        atlas = family + "/" + family.rsplit("/", 1)[1]
        paths.update(atlas + suffix for suffix in (".png", ".atlas.amf3.deflate"))
    for path in sorted(paths):
        raw = official_bytes_loader(path)
        if not isinstance(raw, bytes):
            raise ValueError(f"missing native PF effect asset: {path}")
        if path.endswith(".amf3.deflate"):
            raw = _encode(_private_references(_decode(raw)))
        result["common", private_path(path)] = raw
    return result


def metadata():
    return {
        "power_flip_id": PF_ID,
        "programs": list(PROGRAM_PATHS),
        "types": ["special", "supporter"],
        "levels": [1, 2, 3],
        "lifecycle": "native special collision/timeout, supporter end notification removed",
        "damage_source": "native power flip",
        "original_damage_geometry_hit_counts_and_buffs_preserved": True,
        "toughness_per_level": {"1": 15, "2": 20, "3": 25},
        "supporter_toughness_override": {"level": 3, "before": 1, "after": 0,
                                         "reason": "2026-09-27 batch 2 Down cap 15/20/25 (Lv3 26 -> 25)"},
        "private_effect_families": list(_FAMILIES),
        "native_source_sha256": {
            source_path(kind, level): digest
            for (kind, level), digest in SOURCE_HASHES.items()
        },
        "requires_new_apk": False,
    }
