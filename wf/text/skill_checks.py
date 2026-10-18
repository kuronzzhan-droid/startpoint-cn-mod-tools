"""Cross-tier wording comparison; keep numeric progression and name suffixes."""
from __future__ import annotations

import re


def wording_shape(text):
    # Different duration/stack/threshold values do not mean different wording.
    # Delimiters, effect names and conditions remain exact, not semantically guessed.
    return re.sub(r"「[^」]*」|『[^』]*』|\d+(?:\.\d+)?",
                  lambda match: match[0] if match[0][0] in "「『" else "N",
                  re.sub(r"\s+", "", text))


def check_tiers(key, tiers, *, location="action_skill"):
    if len(tiers) < 2:
        return []
    descriptions = {tier: pair["c1"] for tier, pair in tiers.items()}
    if len({wording_shape(text) for text in descriptions.values()}) == 1:
        return []
    return [{"rule": "text.standard.skill-tier-wording", "state": "问题",
             "location": location, "message": "技能各档描述应采用同一套写法；数值差异已忽略",
             "evidence_nature": "作者规范", "source": "面板文案规范 v1 §9",
             "evidence": {"text": "\n".join(f"{tier}: {text}" for tier, text in descriptions.items()),
                          "matches": ["各档描述的非数值写法不同"], "skill_key": key,
                          "descriptions": descriptions}}]
