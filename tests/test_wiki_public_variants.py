"""The public package must include only the verified lazy character-family index."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wf_wiki_categories import HIDDEN_CHARACTER_IDS
from wf_wiki_public import public_id
from wf_wiki_public_variants import INDEX, JSON_INDEX, variant_plan


class PublicVariantPlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name)
        (self.source / "data").mkdir()
        self.ids = [public_id("c", value) for value in ("1", "2", "3")]
        self.catalog = {"meta": {}, "characters": [{"id": cid} for cid in self.ids]}
        self.value = {"schemaVersion": 1, "groups": {cid: self.ids[:2] for cid in self.ids[:2]}}
        self.write()

    def write(self):
        payload = {key: self.value[key] for key in ("schemaVersion", "groups")}
        version = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]
        self.value["dataVersion"] = version
        self.catalog["meta"]["characterVariants"] = {"url": INDEX, "version": version, "schemaVersion": 1}
        raw = json.dumps(self.value, separators=(",", ":"))
        (self.source / JSON_INDEX).write_text(raw, encoding="utf-8")
        (self.source / INDEX).write_text("window.WF_CHARACTER_VARIANTS=" + raw + ";\n", encoding="utf-8")

    def test_exact_js_plan_watches_json_and_keeps_orphans_out_without_writes(self):
        (self.source / "data/old-character.js").write_text("must not publish")
        before = {p: p.read_bytes() for p in (self.source / "data").iterdir()}
        plan, watched, audit = variant_plan(self.source, self.catalog)
        self.assertEqual([entry["path"] for entry in plan], [INDEX])
        self.assertEqual(set(watched), {INDEX, JSON_INDEX})
        self.assertEqual((audit["groups"], audit["characters"]), (1, 2))
        self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_hidden_members_and_unknown_keys_are_rejected(self):
        for cid in (public_id("c", next(iter(HIDDEN_CHARACTER_IDS))), public_id("c", "999999"), "111002"):
            self.value["groups"][cid] = [self.ids[0], cid]
            self.write()
            with self.assertRaisesRegex(ValueError, "白名单"):
                variant_plan(self.source, self.catalog)
            del self.value["groups"][cid]
        hidden = public_id("c", next(iter(HIDDEN_CHARACTER_IDS)))
        self.catalog["characters"].append({"id": hidden})
        with self.assertRaisesRegex(ValueError, "隐藏角色"):
            variant_plan(self.source, self.catalog)

    def test_duplicate_singleton_and_asymmetric_groups_are_rejected(self):
        original = copy.deepcopy(self.value)
        for members in ([self.ids[0]], [self.ids[0], self.ids[0]], self.ids,
                        [self.ids[1], self.ids[0]], [self.ids[0], public_id("c", "99")]):
            self.value = copy.deepcopy(original)
            self.value["groups"][self.ids[0]] = members
            self.write()
            with self.assertRaisesRegex(ValueError, "成员|反向关系"):
                variant_plan(self.source, self.catalog)

    def test_json_mismatch_and_extra_code_are_rejected(self):
        good = (self.source / INDEX).read_text(encoding="utf-8")
        for value in ("window.WF_CHARACTER_VARIANTS={};", good + "alert(1);", good.replace("WF_CHARACTER_VARIANTS", "WRONG")):
            (self.source / INDEX).write_text(value, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "索引不同|额外代码"):
                variant_plan(self.source, self.catalog)

    def test_stale_metadata_and_unsafe_index_reference_are_rejected(self):
        for key, value in (("version", "b" * 16), ("url", "../private.js"), ("schemaVersion", 2)):
            self.write()
            self.catalog["meta"]["characterVariants"][key] = value
            with self.assertRaises(ValueError):
                variant_plan(self.source, self.catalog)

    def test_source_fields_and_missing_index_are_rejected(self):
        self.value["code"] = "private-source-code"
        self.write()
        with self.assertRaisesRegex(ValueError, "格式"):
            variant_plan(self.source, self.catalog)
        (self.source / INDEX).unlink()
        with self.assertRaises(OSError):
            variant_plan(self.source, self.catalog)

    def test_empty_groups_are_valid_and_links_fail_closed(self):
        self.value["groups"] = {}
        self.write()
        self.assertEqual(variant_plan(self.source, self.catalog)[2]["characters"], 0)
        with patch.object(Path, "is_symlink", lambda p: p.name == "character-variants.js"):
            with self.assertRaisesRegex(ValueError, "链接"):
                variant_plan(self.source, self.catalog)

    def test_existing_frontend_fixed_fallback_accepts_snapshot_without_metadata(self):
        del self.catalog["meta"]["characterVariants"]
        plan, _, audit = variant_plan(self.source, self.catalog)
        self.assertEqual([p["path"] for p in plan], [INDEX])
        self.assertFalse(audit["metadataDeclared"])


if __name__ == "__main__":
    unittest.main()
