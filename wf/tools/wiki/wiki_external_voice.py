"""Export every declared voice from the selected independent character package."""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

import wf_assets
from wf_wiki_voice import SPEECH_TABLE, _CATEGORIES, _slot_key, slot_label
from wf_wiki_voice_sources import SLOT_RE, build_subtitle_index

HOME_LABELS = {"gift": "中秋赠礼", "moon": "赏月", "mooncake": "月饼",
               "robe": "月白华服", "wish": "许愿"}


def package_voices(repo: Path, character: dict, source, media) -> dict:
    index = build_subtitle_index(repo)
    speech = defaultdict(list)
    for row in source.table(SPEECH_TABLE).get(character["id"], []):
        if len(row) >= 5 and SLOT_RE.fullmatch(row[4]) and row[3].strip():
            value = row[3].strip()
            if value not in speech[row[4]]:
                speech[row[4]].append(value)
    prefix = f"character/{character['code']}/voice/"
    slots = set()
    for tier, logical in source.files.entries:
        if tier == "common" and logical.startswith(prefix) and logical.endswith(".mp3"):
            slot = logical[len(prefix):-4]
            if not SLOT_RE.fullmatch(slot):
                raise ValueError("独立角色包含未识别语音类别，拒绝静默漏收")
            slots.add(slot)
    counts = Counter(characters=0, recordings=0, withJapanese=0, withChinese=0,
                     missingJapanese=0, missingChinese=0, textConflicts=0, missingAudio=0)
    voices = []
    for slot in sorted(slots, key=_slot_key):
        logical = prefix + slot + ".mp3"
        raw = source.files.read(logical)
        match = index.match(raw, wf_assets.mp3_decode(raw))
        ja, zh = match["ja"], "\n\n".join(speech[slot]) or match["zh"]
        text_source = match["textSource"]
        if speech[slot]:
            text_source = "package-speech" + (" + " + text_source if ja else "")
        audio = media.audio(logical)
        counts["missingAudio"] += not bool(audio)
        counts["textConflicts"] += bool(match["conflict"])
        counts["recordings"] += 1
        counts["withJapanese" if ja else "missingJapanese"] += 1
        counts["withChinese" if zh else "missingChinese"] += 1
        category, filename = slot.split("/", 1)
        label = HOME_LABELS.get(filename, slot_label(slot)) if category == "home" else slot_label(slot)
        voices.append({"slot": slot, "label": label,
                       "category": _CATEGORIES.get(category, "剧情"), "audio": audio,
                       "ja": ja, "zh": zh, "textSource": text_source,
                       "status": "complete" if ja and zh else "translation-missing" if ja
                       else "original-missing" if zh else "text-missing"})
    character["voices"] = voices
    counts["characters"] = int(bool(voices))
    return dict(counts, charsWithAudio=counts["characters"], audioCount=counts["recordings"],
                jaCount=counts["withJapanese"], zhCount=counts["withChinese"],
                missingZhCount=counts["missingChinese"])
