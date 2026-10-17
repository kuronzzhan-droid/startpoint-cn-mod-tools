"""Read native charge semantics conservatively from the public frozen snapshot."""
from __future__ import annotations

import hashlib
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wf_wiki_battle_native as native

CID = "c123456789abc"


def ability(text, restrictions=None):
    return {"name": "能力 1", "rows": [{"index": 1, "description": text,
            "restrictions": restrictions or {"operator": "AND", "items": []}}]}


def detail(*abilities, gauge=530):
    return {"id": CID, "skills": [{"kind": "main", "level": "2", "gauge": gauge}],
            "abilities": list(abilities)}


class NativeTests(unittest.TestCase):
    def test_highest_main_level_not_switched_or_gauge_min(self):
        row = detail()
        row["skills"] += [{"kind": "switched", "level": "4", "gauge": 1},
                          {"kind": "main", "level": "3", "gauge": 450, "gaugeMin": 580}]
        result, _ = native.charge_metadata(row)
        self.assertEqual(result, {"gauge": 450, "cooldown": 22.5})

    def test_initial_sum_and_clamp_once_are_explicit(self):
        result, audit = native.charge_metadata(detail(ability("自身 技能槽 25%→50%"),
                                  ability("自身 技能槽 75%")))
        self.assertEqual(result["initial"], 1)
        self.assertEqual([row["adopted"] for row in audit], ["initial", "initial"])

    def test_speed_is_rate_and_cooldown_rounds_up_to_fixed_tick(self):
        result, _ = native.charge_metadata(detail(ability("自身 技能槽充能 5%"), gauge=510))
        self.assertEqual(result["chargeSpeed"], .05)
        self.assertEqual(result["cooldown"], 24.3)
        self.assertGreaterEqual(result["cooldown"], 510 / 20 / 1.05)
        self.assertLess(result["cooldown"], 510 / 20 / 1.05 + .05)
        self.assertEqual(native.cooldown_seconds(550, .1), 25)

    def test_main_allowed_but_or_resonance_and_unknown_restrictions_are_not(self):
        main = {"operator": "AND", "items": [{"kind": "main", "label": "仅主位"}]}
        for restriction in ({"operator": "OR", "items": []},
                            {"operator": "AND", "items": [{"kind": "resonance"}]},
                            {"operator": "AND", "items": [{"kind": "custom"}]},
                            {"operator": "AND"}):
            result, audit = native.charge_metadata(detail(ability("自身 技能槽 50%", main),
                                        ability("自身 技能槽 50%", restriction)))
            self.assertEqual(result["initial"], .5)
            self.assertIsNone(audit[1]["adopted"])

    def test_trigger_ct_limit_and_zero_defaults_survive(self):
        result, _ = native.charge_metadata(detail(ability("技能发动≥1(限4次)(CT15秒) → 自身 技能槽 10%→20%")))
        self.assertEqual(result["refund"], {"ratio": .2, "ct": 15, "limit": 4})
        result, _ = native.charge_metadata(detail(ability("技能发动≥1(限4次) → 自身 技能槽 20%")))
        self.assertEqual(result["refund"], {"ratio": .2, "ct": 0, "limit": 4})
        self.assertNotIn("initial", result)
        self.assertNotIn("chargeSpeed", result)

    def test_other_triggers_targets_conditions_and_second_gauge_never_become_self_rules(self):
        unsupported = ["自身 2号位技能槽 50%", "HP≥40% 时: 技能发动≥1 → 自身 技能槽 100%",
                       "持有者为主位 时: 自身 技能槽 100%", "赋予全队 技能槽 100%",
                       "持续·Fever → 自身 技能槽充能 10%", "自身 技能槽 50%(延迟2秒)",
                       "技能发动≥1(CT15秒) → 赋予全队 技能槽 5%"]
        result, audit = native.charge_metadata(detail(*(ability(text) for text in unsupported)))
        self.assertEqual(result, {"gauge": 530, "cooldown": 26.5})
        self.assertTrue(all(item["adopted"] is None for item in audit))

    def test_multiple_refund_rules_fail_instead_of_erasing_constraints(self):
        with self.assertRaisesRegex(ValueError, "refund"):
            native.charge_metadata(detail(ability("技能发动≥1(限4次) → 自身 技能槽 20%"),
                                          ability("技能发动≥1(CT15秒) → 自身 技能槽 5%")))

    def test_invalid_gauge_level_or_duplicate_highest_fails(self):
        for value in (0, -1, True, math.nan, math.inf, "530"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                native.charge_metadata(detail(gauge=value))
        row = detail()
        row["skills"].append(dict(row["skills"][0]))
        with self.assertRaises(ValueError):
            native.charge_metadata(row)

    def write_fixture(self, root, row):
        raw = ('window.WF_WIKI_CHUNKS = window.WF_WIKI_CHUNKS || {};\n' +
               f'window.WF_WIKI_CHUNKS["character:{CID}"] = ' + json.dumps(row) + ';\n').encode()
        digest = hashlib.sha256(raw).hexdigest()
        url = f"data/character-{CID}-{digest[:16]}.js"
        (root / "data").mkdir(exist_ok=True)
        (root / url).write_bytes(raw)
        manifest = {"dataManifest": {"chunks": {"character:" + CID:
                    {"url": url, "bytes": len(raw), "sha256": digest}}}}
        (root / "data.js").write_text("window.WF_WIKI = " + json.dumps(manifest) + ";", encoding="utf-8")
        return url, manifest

    def test_frozen_json_assignment_and_hash_are_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            url, _ = self.write_fixture(root, detail())
            self.assertEqual(native.read_native_skills(root, [CID])[CID]["gauge"], 530)
            with (root / url).open("a") as file:
                file.write("execute();")
            with self.assertRaisesRegex(ValueError, "hash|snapshot"):
                native.read_native_skills(root, [CID])

    def test_valid_hash_does_not_allow_executable_javascript_or_wrong_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            row = detail()
            row["id"] = "c000000000000"
            self.write_fixture(root, row)
            with self.assertRaisesRegex(ValueError, "identity"):
                native.read_native_skills(root, [CID])
            url, manifest = self.write_fixture(root, detail())
            raw = (root / url).read_bytes() + b"execute();"
            (root / url).write_bytes(raw)
            entry = manifest["dataManifest"]["chunks"]["character:" + CID]
            entry.update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
            (root / "data.js").write_text("window.WF_WIKI = " + json.dumps(manifest) + ";", encoding="utf-8")
            with self.assertRaises(ValueError):
                native.read_native_skills(root, [CID])

    def test_manifest_cannot_redirect_to_external_or_different_character_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, manifest = self.write_fixture(root, detail())
            entry = manifest["dataManifest"]["chunks"]["character:" + CID]
            for url in ("../private.js", "https://example.test/x.js",
                        "data/character-c000000000000-0123456789abcdef.js"):
                entry["url"] = url
                (root / "data.js").write_text("window.WF_WIKI = " + json.dumps(manifest) + ";", encoding="utf-8")
                with self.subTest(url=url), self.assertRaisesRegex(ValueError, "path"):
                    native.read_native_skills(root, [CID])


if __name__ == "__main__":
    unittest.main()
