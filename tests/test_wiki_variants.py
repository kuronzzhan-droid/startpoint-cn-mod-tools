"""Family links must not expose game keys or merge unrelated cloned characters."""
from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wf_wiki_public import public_id
from wf_wiki_variants import build_variant_index, write_character_variants


def row(identity, code="private_code"):
    return [[code, *([""] * 26), str(identity)]]


def character(cid, name, order=1):
    return {"id": public_id("c", str(cid)), "name": name, "catalogOrder": order}


class VariantTests(unittest.TestCase):
    def test_official_identity_precedes_display_name_and_mods_follow_officials(self):
        official = {"1": row(1), "2": row(1)}
        current = {**official, "900": row(900)}
        chars = [character(900, "特克托", 0), character(2, "特克托", 2), character(1, "特克托", 1)]
        result = build_variant_index(chars, current, official)
        expected = [public_id("c", str(cid)) for cid in (1, 2, 900)]
        self.assertEqual(result["groups"], {cid: expected for cid in expected})
        self.assertEqual(result["schemaVersion"], 1)

    def test_external_same_name_joins_only_one_verified_family(self):
        result = build_variant_index([character(1, "稻穗"), character(999, "稻穗")], {"1": row(1)}, {"1": row(1)})
        self.assertEqual(len(result["groups"]), 2)
        ambiguous = {"1": row(1), "2": row(2)}
        result = build_variant_index([character(1, "同名"), character(2, "同名"), character(999, "同名")], ambiguous, ambiguous)
        self.assertEqual(result["groups"], {})

    def test_valid_explicit_mod_identity_disambiguates_but_other_named_clone_is_not_family(self):
        official = {"1": row(1), "2": row(2)}
        current = {**official, "900": row(1), "901": row(1)}
        chars = [character(1, "同名"), character(2, "同名"), character(900, "同名"), character(901, "另一个人")]
        groups = build_variant_index(chars, current, official)["groups"]
        self.assertEqual(set(groups), {public_id("c", "1"), public_id("c", "900")})

    def test_sentinels_cycles_and_mod_only_shared_names_do_not_create_false_family(self):
        official = {"1": row("(None)"), "2": row("(None)"), "3": row(4), "4": row(3)}
        current = {**official, "900": row(900), "901": row(901)}
        chars = [character(cid, str(cid) if cid not in (900, 901) else "MOD同名") for cid in (1, 2, 3, 4, 900, 901)]
        self.assertEqual(build_variant_index(chars, current, official)["groups"], {})

    def test_hidden_characters_are_never_linked_even_if_caller_passes_them(self):
        official = {"1": row(1)}
        current = {**official, "119998": row(1), "119999": row(1), "129990": row(1), "900": row(900)}
        chars = [character(cid, "名字") for cid in current]
        groups = build_variant_index(chars, current, official)["groups"]
        self.assertEqual(set(groups), {public_id("c", "1"), public_id("c", "900")})
        self.assertTrue(all(set(members) == set(groups) for members in groups.values()))

    def test_index_is_deterministic_public_only_and_rejects_untrusted_ids_or_empty_baseline(self):
        rows = {"1": row(1), "2": row(1)}
        chars = [character(1, "名字"), character(2, "名字")]
        a = build_variant_index(chars, rows, rows)
        self.assertEqual(a, build_variant_index(chars, rows, rows))
        self.assertNotIn("private_code", json.dumps(a))
        with self.assertRaisesRegex(ValueError, "公开角色"):
            build_variant_index([{"id": "1", "name": "角色"}], rows, rows)
        with self.assertRaisesRegex(ValueError, "基准为空"):
            build_variant_index(chars, rows, {})

    def test_writer_checks_source_stability_and_publishes_only_public_index_files(self):
        rows = {"1": row(1), "2": row(1)}
        source = Mock(); source.table.return_value = rows
        catalog = {"characters": [character(1, "名字"), character(2, "名字")]}
        with tempfile.TemporaryDirectory() as tmp, patch("wf_wiki_catalog_source.WikiSource", return_value=source):
            output = Path(tmp)
            result = write_character_variants(Path(tmp), output, catalog, Path(tmp))
            self.assertEqual(result["groups"], 1)
            source.verify_unchanged.assert_called_once()
            payload = json.loads((output / "data/character-variants.json").read_text(encoding="utf-8"))
            self.assertEqual(result["version"], payload["dataVersion"])
            self.assertEqual(catalog["meta"]["characterVariants"]["version"], result["version"])
            self.assertNotIn("private_code", (output / "data/character-variants.js").read_text())
            source.verify_unchanged.side_effect = RuntimeError("changed")
            old = (output / "data/character-variants.json").read_bytes()
            with self.assertRaisesRegex(RuntimeError, "changed"):
                write_character_variants(Path(tmp), output, catalog, Path(tmp))
            self.assertEqual(old, (output / "data/character-variants.json").read_bytes())


if __name__ == "__main__":
    unittest.main()
