"""Battle content compiles explicit budgets without trusting runtime prose."""
from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wf_wiki_battle_content as content


THEMES = ("fire", "water", "thunder", "wind", "light", "dark")
ELEMENTS = "火水雷风光暗"
IDS = ["c" + str(i) * 12 for i in range(1, 7)]


def phase(effects, geometry=None):
    return {"offset": 0, "selector": {"team": "enemy", "kind": "nearest", "range": 3},
            "geometry": geometry or {"kind": "single", "center": "target"},
            "effects": effects, "requiresCasterAlive": True}


def definition(cid):
    return {"id": cid, "role": "melee", "sourceSkill": "原技能", "sourceExcerpt": "突刺与护盾",
            "skill": {"name": "突刺", "description": "突刺并保护自己", "cooldown": 20,
                      "cost": 15, "phases": [phase([{"type": "damage", "budgetShare": .7}]),
                        {**phase([{"type": "shield", "budgetShare": .3, "duration": 5}]),
                         "selector": {"team": "ally", "kind": "self", "range": 0}}]}}


APPROVED = {'c29054cf9d371': '风', 'c22d4a8ac42f7': '火', 'c9a07e74081a3': '火', 'c6dc9da865066': '火', 'cb922553efea6': '火', 'c3ca327abc43c': '火', 'c1ad38008e1dd': '火', 'c907f46378c61': '火', 'cbebf6c04269f': '火', 'c393f6e9d484c': '火', 'c5057d866095d': '火', 'c14657e92a1c8': '火', 'cf2639185ac38': '火', 'cbb042f435215': '水', 'c230cb7dfddb4': '水', 'cc890cc6f5b9f': '水', 'cff8b856bd63e': '水', 'cbd4438ee04a2': '水', 'c4d91125f2dba': '水', 'cb300516a46bd': '水', 'cb911196e000f': '水', 'caa3e97fb083b': '水', 'c422f7cbecb02': '水', 'c91bf0fe8263f': '水', 'cbab087128a78': '水', 'ca92616555900': '水', 'c697b6b0e7024': '雷', 'cc052ad18584b': '雷', 'c42078d566c79': '雷', 'c2d33d8b90591': '雷', 'c9d5244189661': '雷', 'c382a022e1832': '雷', 'c453ba49676ab': '雷', 'cd06e0723b274': '雷', 'c55cd97d61417': '雷', 'cc574cfc67ca4': '雷', 'c76af6c75e9ef': '雷', 'c52f66fa91aa0': '雷', 'c1c51ad34cb8b': '雷', 'ca1c35e91f036': '光', 'cb821b8bdcf90': '风', 'c9fee4a115e72': '风', 'c7a1f80d5b642': '风', 'c06f389dc86fc': '风', 'c6dcca08975e3': '风', 'c14022e5e34c2': '风', 'c1cd6268ebf17': '风', 'c979aade7359f': '风', 'c33346bb607d9': '风', 'c4a3674faacb4': '风', 'c02ea0cac472f': '风', 'c329d2479d6db': '风', 'c277166ea1f5a': '风', 'c0160a957e45d': '风', 'c78ab5173bc00': '风', 'c2428f776c973': '风', 'c1fcbaf5fd7a3': '光', 'c1652ce208ed9': '光', 'ccae1a246e7f4': '光', 'c53f09dcbd23c': '光', 'cc8b0eb3c66c7': '光', 'cf5b7e4d65d2a': '光', 'c51427a616bca': '光', 'c63b5e6541b2c': '光', 'cd5f727aab751': '光', 'cd882590f8724': '光', 'c76f2f7163f6e': '光', 'c6ffda440dbf2': '暗', 'cc228672393a7': '暗', 'ca12720862c6d': '暗', 'c3d9841b70bac': '暗', 'c40dde4bf2116': '暗', 'c78386cf8da48': '暗', 'c24fccfc08c0b': '暗', 'c8cc94e1ff94c': '暗', 'c633b80b6a710': '暗', 'c220efe5f85db': '雷', 'c5ac94a986fd2': '光', 'c60bb1ab2ccfd': '暗', 'c41b6e2e3dbef': '暗', 'ca2c6d69b5906': '暗', 'c36859f729a9d': '暗', 'c22ca49e2f9aa': '暗', 'c78b748da3786': '暗', 'c06d6b4ae50fb': '火', 'c5d2fd33ee6b1': '雷', 'c77a2a08c6159': '风', 'ca70010c6ea6b': '暗', 'cf364400e6aa7': '光', 'cff1dc7f5049d': '火', 'c789c601e51c8': '暗', 'c5e79c24e720b': '光'}


class ContentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.site = self.root / "site"
        self.defs = self.root / "definitions"
        self.site.mkdir()
        self.defs.mkdir()
        (self.site / "media").mkdir()
        (self.site / "media" / "sprite.webp").write_bytes(b"fixture")
        (self.site / "media" / "voice.mp3").write_bytes(b"fixture")
        self.catalog = [{"id": cid, "name": f"角色{i}", "title": "称号", "theme": "通常版",
                         "aliases": ["别名"], "element": ELEMENTS[i], "origin": "新增MOD"}
                        for i, cid in enumerate(IDS)]
        self.rows = {theme: [definition(cid)] for theme, cid in zip(THEMES, IDS)}
        self.native = {}
        self.stages = {"stages": [{"id": theme, "name": theme, "bossId": cid,
                                  "theme": theme, "difficulty": round(1 + .12 * i, 2)}
                                 for i, (theme, cid) in enumerate(zip(THEMES, IDS))],
                       "endless": {"hpBase": 2000, "attackBase": 70,
                                   "vanguardHp": 450, "vanguardAttack": 30}}
        image = {"url": "media/sprite.webp", "width": 64, "height": 64,
                 "anchorX": 32, "anchorY": 64, "duration": 1, "animated": False}
        self.media = {"media": {cid: {"avatar": "media/sprite.webp",
                      "actions": {"idle": copy.deepcopy(image), "skill_ready": copy.deepcopy(image)},
                      "voices": {"deploy": ["media/voice.mp3"], "ready": [], "cast": [],
                                 "death": [], "se": []}, "missingCues": ["未收录准备语音"]}
                      for cid in IDS}, "coffin": image, "audit": {"privatePath": "private-fixture"}}

    def write_catalog(self):
        chunks = {}
        (self.site / "data").mkdir(exist_ok=True)
        for row in self.catalog:
            cid = row["id"]
            detail = self.native.get(cid, {"id": cid, "skills": [{"kind": "main", "level": "2", "gauge": 500}],
                                            "abilities": []})
            raw = ('window.WF_WIKI_CHUNKS = window.WF_WIKI_CHUNKS || {};\n' +
                   f'window.WF_WIKI_CHUNKS["character:{cid}"] = ' + json.dumps(detail) + ';\n').encode()
            digest = hashlib.sha256(raw).hexdigest()
            url = f"data/character-{cid}-{digest[:16]}.js"
            (self.site / url).write_bytes(raw)
            chunks["character:" + cid] = {"url": url, "sha256": digest, "bytes": len(raw)}
        catalog = {"characters": self.catalog, "dataManifest": {"chunks": chunks}}
        (self.site / "data.js").write_text("window.WF_WIKI = " + json.dumps(catalog) + ";", encoding="utf-8")

    def write(self):
        self.write_catalog()
        for theme, rows in self.rows.items():
            (self.defs / f"characters-{theme}.json").write_text(json.dumps({"characters": rows}), encoding="utf-8")
        (self.defs / "stages.json").write_text(json.dumps(self.stages), encoding="utf-8")

    def build(self):
        self.write()
        return content.build_content(self.site, self.defs, self.media)

    def test_single_target_budget_is_split_once(self):
        result = self.build()
        phases = result["characters"][IDS[0]]["skill"]["phases"]
        self.assertEqual(phases[0]["effects"][0]["amount"], 210)
        self.assertEqual(phases[1]["effects"][0]["ratio"], .06)
        self.assertEqual(result["characters"][IDS[0]]["stats"]["skillPower"], 60)
        self.assertNotIn("audit", result)
        self.assertNotIn("sourceExcerpt", result["characters"][IDS[0]])
        self.assertEqual(result["characters"][IDS[0]]["aliases"], ["别名"])

    def test_native_charge_replaces_runtime_cost_after_damage_budget_compilation(self):
        self.native[IDS[0]] = {"id": IDS[0], "skills": [{"kind": "main", "level": "2", "gauge": 510}],
            "abilities": [{"rows": [{"description": "自身 技能槽充能 5%",
                                      "restrictions": {"operator": "AND", "items": []}}]}]}
        skill = self.build()["characters"][IDS[0]]["skill"]
        self.assertEqual(skill["gauge"], 510)
        self.assertEqual(skill["cooldown"], 24.3)
        self.assertEqual(skill["chargeSpeed"], .05)
        self.assertNotIn("cost", skill)
        self.assertEqual(skill["phases"][0]["effects"][0]["amount"], 210)

    def test_runtime_rejects_native_gauge_duration_or_refund_mismatch(self):
        for key, value in (("gauge", True), ("cooldown", 30), ("initial", 1.1),
                           ("chargeSpeed", -1), ("cost", 15),
                           ("refund", {"ratio": .05, "ct": -1}),
                           ("refund", {"ratio": .05, "ct": 15, "limit": True})):
            result = self.build()
            result["characters"][IDS[0]]["skill"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                content.validate_content(result)

    def test_build_only_budget_shares_do_not_ship_to_runtime(self):
        result = self.build()
        effects = [e for char in result["characters"].values() for p in char["skill"]["phases"] for e in p["effects"]]
        self.assertTrue(all("budgetShare" not in effect for effect in effects))

    def test_badge_preserves_modified_official_identity(self):
        self.catalog[0]["origin"] = "改版官方"
        result = self.build()
        self.assertEqual(result["characters"][IDS[0]]["tag"], "MOD改")
        self.assertEqual(result["characters"][IDS[1]]["tag"], "MOD")
        result["characters"][IDS[0]]["tag"] = "官方"
        with self.assertRaises(ValueError):
            content.validate_content(result)

    def test_multihit_area_budget_does_not_restart_each_phase(self):
        phases = [phase([{"type": "damage", "budgetShare": .25}],
                        {"kind": "circle", "center": "target", "radius": 1.5}) for _ in range(4)]
        for i, item in enumerate(phases):
            item["offset"] = i * .25
        self.rows["fire"][0]["skill"]["phases"] = phases
        built = self.build()["characters"][IDS[0]]["skill"]["phases"]
        self.assertEqual(sum(p["effects"][0]["amount"] for p in built), 195)

    def test_dot_and_periodic_heal_keep_total_not_per_tick_amount(self):
        self.rows["fire"][0]["skill"]["phases"] = [phase([
            {"type": "dot", "budgetShare": .5, "duration": 8, "interval": 1, "targetMode": "attached"},
            {"type": "heal", "budgetShare": .5, "duration": 8, "interval": 1, "targetMode": "attached"}])]
        self.rows["fire"][0]["skill"]["phases"][0]["effects"].pop()
        heal = phase([{"type": "heal", "budgetShare": .5, "duration": 8, "interval": 1, "targetMode": "attached"}])
        heal["selector"] = {"team": "ally", "kind": "self", "range": 0}
        self.rows["fire"][0]["skill"]["phases"].append(heal)
        built = self.build()["characters"][IDS[0]]["skill"]["phases"]
        self.assertEqual(built[0]["effects"][0]["amount"], 150)
        self.assertEqual(built[1]["effects"][0]["ratio"], .125)

    def test_periodic_effects_require_explicit_target_mode(self):
        for kind in ("dot", "heal"):
            effect = {"type": kind, "budgetShare": 1, "duration": 5}
            self.rows["fire"][0]["skill"]["phases"] = [phase([effect])]
            with self.assertRaisesRegex(ValueError, "targetMode"):
                self.build()
            effect["targetMode"] = "nearest-every-tick"
            with self.assertRaisesRegex(ValueError, "targetMode"):
                self.build()
            for mode in ("area", "attached"):
                effect["targetMode"] = mode
                result = self.build()
                self.assertEqual(result["characters"][IDS[0]]["skill"]["phases"][0]["effects"][0]["targetMode"], mode)
        self.rows["fire"][0]["skill"]["phases"] = [phase([{"type": "damage", "budgetShare": 1, "targetMode": "area"}])]
        with self.assertRaisesRegex(ValueError, "targetMode"):
            self.build()

    def test_explicit_poison_and_ground_field_roster_modes(self):
        definitions = Path(__file__).resolve().parents[1] / "wiki-battle"
        attached = {"cbebf6c04269f", "c633b80b6a710", "ca2c6d69b5906", "c22ca49e2f9aa"}
        seen, heals = set(), 0
        for path in definitions.glob("characters-*.json"):
            for char in json.loads(path.read_text(encoding="utf-8"))["characters"]:
                for item in char["skill"]["phases"]:
                    for effect in item["effects"]:
                        if effect["type"] == "dot":
                            expected = "attached" if char["id"] in attached else "area"
                            self.assertEqual(effect.get("targetMode"), expected, char["id"])
                            if expected == "attached":
                                seen.add(char["id"])
                        elif effect["type"] == "heal" and "duration" in effect:
                            self.assertEqual(effect.get("targetMode"), "attached", char["id"])
                            heals += 1
        self.assertEqual(seen, attached)
        self.assertEqual(heals, 4)

    def test_media_prefix_and_picture_audio_types_are_enforced(self):
        media = self.media["media"][IDS[0]]
        for url in ("missing.webp", "media/voice.mp3", "media/script.js"):
            media["avatar"] = url
            with self.assertRaisesRegex(ValueError, "Media"):
                self.build()
        media["avatar"] = "media/sprite.webp"
        for url in ("voice.mp3", "media/sprite.webp", "media/script.js"):
            media["voices"]["deploy"] = [url]
            with self.assertRaisesRegex(ValueError, "Media"):
                self.build()

    def test_buff_refresh_copies_numeric_effect_without_new_budget(self):
        first = phase([{"type": "attackUp", "budgetShare": .4, "duration": 8}])
        first["selector"] = {"team": "ally", "kind": "all", "range": 12}
        first["geometry"] = {"kind": "all", "center": "self"}
        refresh = {**copy.deepcopy(first), "offset": 1, "effects": [], "refreshFrom": 0}
        self.rows["fire"][0]["skill"]["phases"] = [first, refresh, phase([{"type": "damage", "budgetShare": .6}])]
        self.rows["fire"][0]["skill"]["phases"][2]["offset"] = 1.5
        phases = self.build()["characters"][IDS[0]]["skill"]["phases"]
        self.assertEqual(phases[0]["effects"], phases[1]["effects"])
        self.assertEqual(phases[1]["effects"][0]["ratio"], .08)
        self.assertNotIn("refreshFrom", phases[1])
        for field, value in (("refreshFrom", 1), ("effects", [{"type": "attackUp", "budgetShare": .1, "duration": 8}])):
            original = copy.deepcopy(refresh)
            refresh[field] = value
            with self.assertRaisesRegex(ValueError, "refresh"):
                self.build()
            refresh.clear()
            refresh.update(original)
        first["effects"][0]["type"] = "shield"
        with self.assertRaisesRegex(ValueError, "refresh"):
            self.build()

    def test_haning_blue_refreshes_after_each_successful_bubble(self):
        path = Path(__file__).resolve().parents[1] / "wiki-battle/characters-water.json"
        skill = next(c["skill"] for c in json.loads(path.read_text(encoding="utf-8"))["characters"] if c["id"] == "cb911196e000f")
        result = content._compile_skill(skill, content.STATS["support"])
        phases = result["phases"]
        buffs = [(i, p) for i, p in enumerate(phases) if p["effects"][0]["type"] == "attackUp"]
        self.assertEqual([p["requiresHit"] for _, p in buffs], [0, 2, 4])
        self.assertTrue(all(p["effects"] == buffs[0][1]["effects"] for _, p in buffs))
        self.assertTrue(all(p["effects"][0]["duration"] == 8 for _, p in buffs))

    def test_followup_total_is_divided_by_proc_limit(self):
        p = phase([{"type": "followup", "budgetShare": 1, "duration": 5, "maxProcs": 5}])
        p["selector"] = {"team": "ally", "kind": "self", "range": 0}
        self.rows["fire"][0]["skill"]["phases"] = [p]
        e = self.build()["characters"][IDS[0]]["skill"]["phases"][0]["effects"][0]
        self.assertEqual(e["amount"], 60)
        self.assertEqual(e["maxProcs"], 5)

    def test_impact_dependency_preserves_real_hit_anchor_contract(self):
        self.rows["fire"][0]["skill"]["phases"][1] = {
            **phase([{"type": "damage", "budgetShare": .3}]), "offset": 1,
            "impactFrom": [0], "impactMode": "farthest"}
        phases = self.build()["characters"][IDS[0]]["skill"]["phases"]
        self.assertEqual(phases[1]["impactFrom"], [0])
        self.assertEqual(phases[1]["effects"][0]["amount"], 90)
        self.rows["fire"][0]["skill"]["phases"][1]["impactFrom"] = [1]
        with self.assertRaises(ValueError):
            self.build()

    def test_hit_targets_reference_only_prior_damage_and_attached_poison(self):
        hit = phase([{"type": "damage", "budgetShare": .7}])
        poison = {**phase([{"type": "dot", "budgetShare": .3, "duration": 8,
                           "targetMode": "attached"}]), "offset": 1, "hitTargetsFrom": [0]}
        self.rows["fire"][0]["skill"]["phases"] = [hit, poison]
        self.assertEqual(self.build()["characters"][IDS[0]]["skill"]["phases"][1]["hitTargetsFrom"], [0])
        for refs in ([], [1], [0, 0], [True], [-1]):
            poison["hitTargetsFrom"] = refs
            with self.subTest(refs=refs), self.assertRaisesRegex(ValueError, "hit-target"):
                self.build()
        poison["hitTargetsFrom"] = [0]
        poison["effects"][0]["targetMode"] = "area"
        with self.assertRaisesRegex(ValueError, "attached poison"):
            self.build()
        poison["effects"][0]["targetMode"] = "attached"
        hit["effects"] = [{"type": "attackUp", "budgetShare": .7, "duration": 5}]
        with self.assertRaisesRegex(ValueError, "hit-target"):
            self.build()

    def test_all_attached_poison_is_bound_to_explicit_prior_damage(self):
        definitions = Path(__file__).resolve().parents[1] / "wiki-battle"
        for path in definitions.glob("characters-*.json"):
            for char in json.loads(path.read_text(encoding="utf-8"))["characters"]:
                skill = content._compile_skill(char["skill"], content.STATS[char["role"]])
                for item in skill["phases"]:
                    if any(e["type"] == "dot" and e.get("targetMode") == "attached" for e in item["effects"]):
                        self.assertTrue(item.get("hitTargetsFrom"), char["id"])

    def test_verified_sound_effect_cues_are_preserved_and_path_checked(self):
        self.media["media"][IDS[0]]["seCues"] = {"deploy": [], "cast": ["media/voice.mp3"],
                                                    "attack": [], "death": []}
        result = self.build()
        self.assertEqual(result["media"][IDS[0]]["seCues"]["cast"], ["media/voice.mp3"])
        self.media["media"][IDS[0]]["seCues"]["cast"] = ["../voice.mp3"]
        with self.assertRaises(ValueError):
            self.build()

    def test_official_and_unknown_characters_are_rejected(self):
        for mode in ("official", "unknown"):
            with self.subTest(mode=mode):
                old = copy.deepcopy(self.catalog)
                if mode == "official":
                    self.catalog[0]["origin"] = "官方原版"
                else:
                    self.catalog.pop(0)
                with self.assertRaises(ValueError):
                    self.build()
                self.catalog = old

    def test_duplicate_and_missing_definitions_are_rejected(self):
        first = copy.deepcopy(self.rows["fire"])
        for rows in ([*first, *first], []):
            self.rows["fire"] = rows
            with self.assertRaises(ValueError):
                self.build()

    def test_nonfinite_negative_cooldown_and_unsupported_effect_are_rejected(self):
        for value in (float("nan"), float("inf"), -1, True):
            with self.subTest(value=value):
                self.rows["fire"][0]["skill"]["cooldown"] = value
                with self.assertRaises(ValueError):
                    self.build()
        self.rows["fire"][0]["skill"]["cooldown"] = 20
        self.rows["fire"][0]["skill"]["phases"][0]["effects"][0]["type"] = "executeScript"
        with self.assertRaises(ValueError):
            self.build()

    def test_invalid_share_and_overallocated_skill_are_rejected(self):
        effect = self.rows["fire"][0]["skill"]["phases"][0]["effects"][0]
        for value in (-.1, 1.1, .8, float("nan"), True):
            with self.subTest(value=value):
                effect["budgetShare"] = value
                with self.assertRaises(ValueError):
                    self.build()

    def test_geometry_selectors_and_unknown_fields_are_rejected(self):
        original = copy.deepcopy(self.rows["fire"])
        invalid = [("geometry", "kind", "eval"), ("geometry", "radius", -2),
                   ("geometry", "offsetX", float("inf")), ("selector", "kind", "account"),
                   ("selector", "hpBelow", 2), ("selector", "script", "untrusted")]
        for target, key, value in invalid:
            self.rows["fire"] = copy.deepcopy(original)
            self.rows["fire"][0]["skill"]["phases"][0][target][key] = value
            with self.subTest(target=target, key=key), self.assertRaises(ValueError):
                self.build()

    def test_cross_site_and_traversal_urls_are_rejected(self):
        for url in ("https://example.test/x.webp", "//example.test/x.webp", "../x.webp",
                    "media/%2e%2e/x.webp", "media\\x.webp", "/media/x.webp", "media/x.webp?q=1"):
            with self.subTest(url=url):
                self.media["media"][IDS[0]]["avatar"] = url
                with self.assertRaises(ValueError):
                    self.build()

    def test_missing_media_and_nonfinite_anchor_are_rejected(self):
        self.media["media"][IDS[0]]["actions"]["idle"]["anchorX"] = float("inf")
        with self.assertRaises(ValueError):
            self.build()
        self.media["media"].pop(IDS[0])
        with self.assertRaises(ValueError):
            self.build()

    def test_wrong_stage_reference_and_theme_are_rejected(self):
        for key, value in (("bossId", "c000000000000"), ("theme", "unlisted")):
            old = self.stages["stages"][0][key]
            self.stages["stages"][0][key] = value
            with self.assertRaises(ValueError):
                self.build()
            self.stages["stages"][0][key] = old

    def test_unsupported_runtime_payload_is_rejected(self):
        result = self.build()
        result["characters"][IDS[0]]["skill"]["phases"][0]["effects"][0]["amount"] = float("inf")
        with self.assertRaises(ValueError):
            content.validate_content(result)

    def test_metadata_assignment_is_json_not_executable_javascript(self):
        self.write()
        with (self.site / "data.js").open("a", encoding="utf-8") as file:
            file.write("\nrunUntrustedCode();")
        with self.assertRaises(ValueError):
            content.build_content(self.site, self.defs, self.media)


    def test_real_definitions_cover_all_92_approved_ids(self):
        self.defs = Path(__file__).resolve().parents[1] / "wiki-battle"
        self.catalog = [{"id": cid, "name": cid, "title": "公开称号", "theme": "公开版本",
                         "aliases": [], "element": element, "origin": "新增MOD"}
                        for cid, element in APPROVED.items()]
        self.write_catalog()
        sample = copy.deepcopy(self.media["media"][IDS[0]])
        self.media["media"] = {cid: copy.deepcopy(sample) for cid in APPROVED}
        result = content.build_content(self.site, self.defs, self.media)
        self.assertEqual(set(result["characters"]), set(APPROVED))
        self.assertEqual(Counter(c["role"] for c in result["characters"].values()),
                         {"melee": 31, "ranged": 30, "healer": 10, "support": 21})
        self.assertEqual(len(result["stages"]), 6)
        for char in result["characters"].values():
            self.assertTrue(char["skill"]["phases"])
            for phase in char["skill"]["phases"]:
                for effect in phase["effects"]:
                    self.assertTrue(effect.get("amount", 0) > 0 or effect.get("ratio", 0) > 0)
        self.real = result

    def test_distinctive_targeting_and_phase_mechanics_survive_compilation(self):
        self.test_real_definitions_cover_all_92_approved_ids()
        def phases(cid):
            return self.real["characters"][cid]["skill"]["phases"]
        self.assertTrue(any(p["selector"].get("preferBoss") for p in phases("c1cd6268ebf17")))
        self.assertTrue(any(p["geometry"].get("direction") == "down" for p in phases("c0160a957e45d")))
        self.assertTrue(any("requiresHit" in p for p in phases("cb911196e000f")))
        self.assertTrue(any(p["selector"].get("hpBelow") == .4 for p in phases("c24fccfc08c0b")))
        kinds = {p["selector"]["kind"] for p in phases("cff1dc7f5049d")}
        self.assertTrue({"leader", "lowestHp"} <= kinds)
        offsets = {(p["geometry"].get("offsetX", 0), p["geometry"].get("offsetY", 0))
                   for p in phases("ccae1a246e7f4") if p["selector"]["team"] == "enemy"}
        self.assertEqual(len(offsets), 9)
        effects = {e["type"] for p in phases("c22ca49e2f9aa") for e in p["effects"]}
        self.assertTrue({"damage", "heal", "shield", "slow", "dot"} <= effects)

if __name__ == "__main__":
    unittest.main()
