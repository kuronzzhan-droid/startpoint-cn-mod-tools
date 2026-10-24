"""Export current local character audio and verified subtitle bindings."""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
from pathlib import Path
import re

import wf_assets
import wf_mod_tool as core
from wf_wiki_voice_sources import SLOT_RE, build_subtitle_index

SPEECH_TABLE = "master/character/character_speech.orderedmap"
_CATEGORIES = {"ally": "加入与觉醒", "home": "主页", "battle": "战斗", "login": "登录"}
_PREFIXES = {
    "battle_start": "战斗开始", "normal_attack": "普通攻击", "outhole": "落下",
    "power_flip": "强化弹射", "exchange_power_flip": "切换强化弹射",
    "matched_skill_ready": "切换技能准备", "skill_ready": "技能准备",
    "matched_skill": "切换技能发动", "skill": "技能发动", "win": "胜利",
    "home": "主页", "login": "登录",
}


def speech_texts(store: Path) -> dict[str, dict[str, str]]:
    """Read only the live subtitle column (c3), keyed by registered slot c4."""
    location = wf_assets.locate(store, SPEECH_TABLE)
    if not location:
        return {}
    rows = core.read_orderedmap_file_from_bytes(location[1].read_bytes())
    result = {}
    for cid, text in rows.items():
        slots = defaultdict(list)
        for row in core.read_csv_lines(text):
            if len(row) >= 5 and SLOT_RE.fullmatch(row[4]):
                value = row[3].strip()
                if value and value not in slots[row[4]]:
                    slots[row[4]].append(value)
        result[str(cid)] = {slot: "\n\n".join(values) for slot, values in slots.items()}
    return result


def _fixed_slots() -> set[str]:
    slots = {"ally/join", "ally/evolution", "battle/skill_ready", "battle/matched_skill_ready"}
    # Store probes only. Large pools and home_12..15 exist in the current MODs.
    for family in ("battle_start", "normal_attack", "outhole", "power_flip", "win",
                   "skill", "matched_skill", "exchange_power_flip", "skill_ready_alt",
                   "matched_skill_ready_alt"):
        slots.update(f"battle/{family}_{n}" for n in range(32))
    slots.update(f"home/home_{n}" for n in range(64))
    slots.update(f"login/login_{n}" for n in range(8))
    return slots


def slot_label(slot: str) -> str:
    category, name = slot.split("/", 1)
    if name == "join":
        return "加入队伍"
    if name in ("evolution", "evolve"):
        return "觉醒"
    for prefix in sorted(_PREFIXES, key=len, reverse=True):
        if name == prefix:
            return _PREFIXES[prefix]
        match = re.fullmatch(re.escape(prefix) + r"(?:_alt)?_(\d+)", name)
        if match:
            return f"{_PREFIXES[prefix]} {int(match[1]) + 1}"
    return _CATEGORIES.get(category, "剧情") + " · " + name


def _slot_key(slot: str):
    category = slot.split("/", 1)[0]
    return (list(_CATEGORIES).index(category) if category in _CATEGORIES else 9,
            tuple(int(x) if x.isdigit() else x for x in re.split(r"(\d+)", slot)))


def _candidate_slots(code: str, speech: dict, index) -> set[str]:
    slots = _fixed_slots() | set(speech) | index.slots.get(code, set())
    slots.update(f"{category}/{filename[:-4]}" for category, filename, _ in wf_assets.dump_voices(code))
    prefix = f"character/{code}/voice/"
    for logical in (wf_assets._pathlist_char_index().get(code, [])
                    + wf_assets._harvest_voice_index().get(code, [])):
        if logical.startswith(prefix) and logical.endswith(".mp3"):
            slots.add(logical[len(prefix):-4])
    # MODs may retain an official character's named Home slots; the live speech
    # table covers active Home entries without guessing the original role.
    return {slot for slot in slots if SLOT_RE.fullmatch(slot)}


def export_voices(repo: Path, characters: list[dict], media, *, official_common_only=True) -> dict:
    """Mutate c['voices']; media.audio(logical) supplies playable relative URLs.

    Counts reflect existing live assets, never files present only in a candidate.
    Missing Japanese/translations stay empty and are explicitly counted.
    """
    index = build_subtitle_index(repo)
    speech_location = wf_assets.locate(media.store, SPEECH_TABLE)
    source_hashes = ({SPEECH_TABLE: hashlib.sha256(speech_location[1].read_bytes()).hexdigest()}
                     if speech_location else {})
    speech = speech_texts(media.store)
    missing_translations = []
    counts = Counter(characters=0, recordings=0, withJapanese=0, withChinese=0,
                     missingJapanese=0, missingChinese=0, textConflicts=0, missingAudio=0)
    for character in characters:
        code, cid = character["code"], str(character["id"])
        live_text = speech.get(cid, {})
        voices = []
        for slot in sorted(_candidate_slots(code, live_text, index), key=_slot_key):
            if (official_common_only and character.get("origin") in {"官方原版", "改版官方"}
                    and slot.split("/", 1)[0] not in _CATEGORIES):
                continue
            logical = f"character/{code}/voice/{slot}.mp3"
            location = wf_assets.locate(media.store, logical)
            if not location:
                continue
            stored = location[1].read_bytes()
            matched = index.match(stored, wf_assets.mp3_decode(stored))
            ja, zh = matched["ja"], live_text.get(slot) or matched["zh"]
            source = matched["textSource"]
            if slot in live_text:
                source = "current-speech" + (" + " + source if ja else "")
            audio = media.audio(logical)
            if not audio:
                counts["missingAudio"] += 1
            status = ("complete" if ja and zh else "translation-missing" if ja else
                      "original-missing" if zh else "text-missing")
            if matched["conflict"]:
                counts["textConflicts"] += 1
            if ja and not zh:
                missing_translations.append(dict(id=cid, code=code, slot=slot,
                    audioSha=hashlib.sha256(stored).hexdigest(), ja=ja))
            if "hash-matched-script" in source:
                counts["verifiedScripts"] += 1
            voices.append(dict(slot=slot, label=slot_label(slot),
                               category=_CATEGORIES.get(slot.split("/", 1)[0], "剧情"),
                               audio=audio, ja=ja, zh=zh, textSource=source, status=status))
            counts["recordings"] += 1
            counts["withJapanese" if ja else "missingJapanese"] += 1
            counts["withChinese" if zh else "missingChinese"] += 1
        character["voices"] = voices
        if voices:
            counts["characters"] += 1
    if speech_location and hashlib.sha256(speech_location[1].read_bytes()).hexdigest() != source_hashes[SPEECH_TABLE]:
        raise RuntimeError("语音导出期间 character_speech 已改变，请重新导出")
    return dict(counts, sourceDocuments=index.documents, sourceHashes=source_hashes,
                scopeNote="官方角色收录主页、战斗、加入觉醒与登录语音，不含剧情；新增 MOD 角色保留全部已找到语音。"
                if official_common_only else "全部已找到语音",
                charsWithAudio=counts["characters"], audioCount=counts["recordings"],
                jaCount=counts["withJapanese"], zhCount=counts["withChinese"],
                missingZhCount=counts["missingChinese"], missingTranslations=missing_translations)
