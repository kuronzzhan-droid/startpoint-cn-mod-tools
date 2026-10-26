"""Generate the reviewable master enum -> client string-key crosswalk.

Run from the repository: py -3 scripts/generate_ability_official.py --as3 <scripts>
Only AS3 files are read. The generated JSON is needed at runtime without AS3.
"""
from __future__ import annotations

import argparse
from collections import Counter
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.ability_as3 import EnumValue, Reader, matching, split_args
from scripts.ability_as3_bindings import merge_binding
from scripts.ability_as3_terms import element_group_keys
from wf.studio.ability_vocabulary import GROUPS, enum_groups

def snake(name):
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)).lower()


def generate(root):
    if not (root / "pinball/common/data/ability").is_dir():
        raise FileNotFoundError("--as3 must contain pinball/common/data/ability")
    reader = Reader(root)
    group_keys = element_group_keys(reader)
    lookup = lru_cache(maxsize=None)(reader.trace_for)
    known = {k for src in reader.sources.values() for k in re.findall(r'"(ability_description_\w+)"', src)}
    groups = {}
    for group, options in enum_groups().items():
        enum = GROUPS[group][1]
        branches = {}
        if enum:
            for value, file, body, line in reader.master_branches(enum):
                branches.setdefault(value, []).append((file, body, line))
        entries = {}
        for value, option in options.items():
            keys = {}
            supported = not enum or reader.enums.get((enum, option["en"])) == int(value)
            for file, body, line in branches.get(value, []) if supported else []:
                constructors = [(ctor, [f"{file}:{number}"]) for ctor, number in reader.constructors(body, line)]
                # The enemy-damage family delegates its two runtime variants.
                for call in re.finditer(r"InstantAbilitySource\.resolveEnemyDamageContent\(", body):
                    args = split_args(body[call.end():matching(body, call.end() - 1)])
                    helper = next(f for f in reader.functions if f["name"] == "resolveEnemyDamageContent")
                    env = {f"param{i + 1}": reader.evaluate(a, {}) for i, a in enumerate(args)}
                    constructors += [(ctor, [f"{file}:{line + body.count(chr(10), 0, call.start())}", f'{helper["path"]}:{number}'])
                                     for ctor, number in reader.constructors(helper["body"], helper["line"], env)]
                for ctor, provenance in constructors:
                    # Preserve outer effects and their parameter nouns separately;
                    # runtime role selection must never promote a noun to an effect.
                    trace = lookup(ctor)
                    for key, evidence in trace["keys"].items():
                        if re.search(r"^ability_description_(?:separator|conjunction|unisonable|strength|percent|count|times|second|n_times|n_second)(?:_|$)", key):
                            continue
                        record = keys.setdefault(key, {"key": key, "status": "as3",
                                                       "evidence": [*provenance, *evidence]})
                        for slot, bindings in trace["bindings"].get(key, {}).items():
                            target = record.setdefault("bindings", {}).setdefault(slot, [])
                            for binding in bindings:
                                binding = {**binding, "evidence": list(dict.fromkeys([*provenance, *binding["evidence"]]))}
                                merge_binding(target, binding)
            # Frozen is fatigue on party members, slow on enemies. The master
            # resolver distinguishes these uses before the shared stringifier.
            if "Frozen" in option["en"]:
                member = option["en"].startswith(("ConditionFrozen", "ConditionCountFrozen", "ConditionKeepFrameFrozen", "FrozenPrevent", "FrozenExtend"))
                rejected = "enemy_frozen" if member else "member_frozen"
                keys = {k: v for k, v in keys.items() if rejected not in k}
            if group == "precontent_target" and supported:
                ctor = EnumValue(enum, int(value))
                for key, evidence in lookup(ctor)["keys"].items():
                    keys.setdefault(key, {"key": key, "status": "as3", "evidence": evidence})
            if group == "opening" and supported and not keys:
                for key, evidence in lookup(EnumValue("OpeningAbilityKind", int(value)))["keys"].items():
                    keys[key] = {"key": key, "status": "as3", "evidence": evidence}
            if group == "element":
                fn = next((f for f in reader.functions if f["name"] == "stringfyElementTarget"), None)
                if fn:
                    for number, text, _ in reader.select(fn["body"], fn["line"], {"param1": int(value)}):
                        for key in re.findall(r'"(element_kind_\w+_full)"', text):
                            keys[key] = {"key": key, "status": "as3", "evidence": [f'{fn["path"]}:{number}']}
            if group == "character_group":
                keys.update({k["key"]: k for k in group_keys.get(value, [])})
            if not keys:
                suffix = snake(option["en"])
                # Candidate names are not promoted to proven mappings even when
                # the key itself occurs elsewhere in the client.
                for prefix in (f"{group}_kind_", f"{group}_", "common_content_", "instant_content_"):
                    key = "ability_description_" + prefix + suffix
                    if key in known:
                        keys[key] = {"key": key, "status": "guess", "evidence": [], "reason": "constructor snake_case"}
            entries[value] = {"en": option["en"], "keys": list(keys.values())}
        groups[group] = entries
    used = {e.rsplit(":", 1)[0] for entries in groups.values() for entry in entries.values()
            for key in entry["keys"] for e in key["evidence"]}
    return {"schemaVersion": 2, "generator": "scripts/generate_ability_official.py",
            "note": "as3 = master resolver and typed description branch; bindings record outer template, env.push slot and type-known noun/element with evidence. Keys may be conditional alternatives. guess = name-only candidate. Paths are relative to --as3.",
            "sources": {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in sorted(used)},
            "groups": groups}


def coverage(result):
    for group, entries in result["groups"].items():
        count = Counter("as3" if any(k["status"] == "as3" for k in e["keys"]) else "guess" if e["keys"] else "none"
                        for e in entries.values())
        print(f"{group}: {len(entries)} = as3 {count['as3']} / guess {count['guess']} / none {count['none']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as3", type=Path, required=True, help="只读客户端反编译 scripts 根目录")
    parser.add_argument("--out", type=Path, default=ROOT / "ability_official_map.json")
    args = parser.parse_args()
    result = generate(args.as3)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    coverage(result)
