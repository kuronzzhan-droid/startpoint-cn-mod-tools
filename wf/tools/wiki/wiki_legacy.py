"""Optional, explicitly attributed notes from the author's older offline wiki."""
from __future__ import annotations

import hashlib
import json
import lzma
from pathlib import Path

from wf_wiki_availability import enrich_availability


SOURCE = "WF Wiki 离线版 v3.0.0（前人 Wiki）"


def decode_legacy_json(encoded: str):
    """The JS compressor writes an ALONE header with a raw LZMA1 payload.

    Its end marker does not satisfy Python's ALONE integrity check. Decode the
    declared byte count as RAW and require a complete JSON value of that length.
    No downloaded or packaged JavaScript is executed.
    """
    raw = bytes.fromhex(encoded)
    if len(raw) < 14 or raw[0] >= 225:
        raise ValueError("旧 Wiki 压缩数据头无效")
    props, dictionary, length = raw[0], int.from_bytes(raw[1:5], "little"), int.from_bytes(raw[5:13], "little")
    if not 0 < dictionary <= 64 * 1024 * 1024 or not 0 < length <= 1024 * 1024:
        raise ValueError("旧 Wiki 单角色数据超过解码限额")
    decoder = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=[{
        "id": lzma.FILTER_LZMA1, "dict_size": dictionary,
        "lc": props % 9, "lp": props // 9 % 5, "pb": props // 45,
    }])
    decoded = decoder.decompress(raw[13:], max_length=length)
    if len(decoded) != length:
        raise ValueError("旧 Wiki 单角色数据不完整")
    return json.loads(decoded.decode("utf-8"))


def reference_skills(role: dict) -> list[dict]:
    skills = []
    for entry in decode_legacy_json(role["jsonCn"]):
        if entry.get("t") != 0:
            continue
        label = "旧 Wiki 强化后" if entry.get("ie") == 1 else "旧 Wiki 强化前"
        for effect in entry.get("s", []):
            values = []
            # Verified against old frontend/js/0.js labels, not inferred from keys.
            for key, title, suffix in (("h", "攻击段数", ""), ("m", "伤害倍率", "倍")):
                value = effect.get(key)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    values.append({"label": title, "value": f"{value:g}{suffix}"})
            skills.append({"label": label, "description": str(effect.get("d", "")),
                           "numericDetails": {"rows": [{"label": "旧稿技能数值", "kind": "reference",
                               "context": [], "values": values}], "notes": []}})
    return skills


def enrich_legacy_reference(catalog: dict, path: Path) -> dict:
    """Read an optional localApi.json before public sanitization; never replace live values."""
    raw = Path(path).read_bytes()
    roles = json.loads(raw)["roleData"]
    by_code = {role["codeName"]: role for role in roles if isinstance(role, dict) and role.get("codeName")}
    counts = {"charactersWithAliases": 0, "referenceAppendices": 0}
    for character in catalog["characters"]:
        if character.get("origin") not in {"官方原版", "改版官方"}:
            continue
        role = by_code.get(character.get("code"))
        if not role or role.get("nameCn") != character.get("name"):
            continue
        aliases = json.loads(role.get("alias") or "[]")
        if not isinstance(aliases, list):
            raise ValueError("旧 Wiki 别名应为数组")
        existing = character.setdefault("aliases", [])
        added = [alias.strip() for alias in aliases if isinstance(alias, str) and
                 alias.strip() and alias.strip() not in existing]
        if added:
            character["aliases"] = list(dict.fromkeys([*existing, *added]))
            character["aliasSource"] = SOURCE
            counts["charactersWithAliases"] += 1
        # Only this verified same character has a missing current skill program.
        if character.get("id") == "1" and character.get("code") == "alk" and any(
                skill.get("warning") == "技能程序文件缺失" for skill in character.get("skills", [])):
            character["legacyReference"] = {"source": SOURCE, "updatedAt": role.get("updateTime", ""),
                "note": "前人 Wiki 的历史参考，未核对当前技能程序。强化前/后是旧站的强化分类，不对应普通、进化或二次进化技能层级。现行程序缺失提示保留。",
                "skills": reference_skills(role)}
            counts["referenceAppendices"] += 1
    enrich_availability(catalog, roles)
    catalog["meta"]["legacyReference"] = {"source": SOURCE, "sha256": hashlib.sha256(raw).hexdigest(),
        "note": "借鉴准确对应角色的检索别名及国服限定/常驻标记；缺失程序的历史技能数值另列参考。", **counts}
    return counts
