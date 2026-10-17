import copy
import json
import lzma
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wf_wiki_legacy import decode_legacy_json, enrich_legacy_reference


def packed(data):
    raw = json.dumps(data, ensure_ascii=False).encode()
    compressed = lzma.compress(raw, format=lzma.FORMAT_ALONE)
    return (compressed[:5] + len(raw).to_bytes(8, "little") + compressed[13:]).hex()


class LegacyReferenceTests(unittest.TestCase):
    def test_reference_is_separate_and_enhancement_is_not_evolution(self):
        previous = [{"t": 0, "s": [{"d": "火属性伤害", "h": 1, "m": 10}]},
                    {"t": 0, "ie": 1, "s": [{"d": "火属性伤害", "h": 1, "m": 20}]}]
        role = {"codeName": "alk", "nameCn": "阿尔克", "alias": '["男主"]',
                "jsonCn": packed(previous), "updateTime": "2024-08-22 19:34:23"}
        character = {"id": "1", "code": "alk", "name": "阿尔克", "origin": "官方原版", "aliases": [],
                     "skills": [{"level": "1", "gauge": 450, "warning": "技能程序文件缺失"}]}
        live = copy.deepcopy(character["skills"])
        result = {"meta": {}, "characters": [character]}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "localApi.json"
            path.write_text(json.dumps({"roleData": [role]}), encoding="utf-8")
            counts = enrich_legacy_reference(result, path)
        self.assertEqual(counts, {"charactersWithAliases": 1, "referenceAppendices": 1})
        self.assertEqual(character["skills"], live)
        reference = character["legacyReference"]
        self.assertEqual([s["label"] for s in reference["skills"]], ["旧 Wiki 强化前", "旧 Wiki 强化后"])
        self.assertIn("未核对", reference["note"])
        self.assertEqual(character["aliases"], ["男主"])

    def test_missing_live_warning_and_new_template_copy_do_not_get_reference(self):
        role = {"codeName": "alk", "nameCn": "阿尔克", "alias": '["男主"]', "jsonCn": packed([])}
        characters = [{"id": "1", "code": "alk", "name": "阿尔克", "origin": "官方原版", "skills": []},
                      {"id": "999", "code": "alk", "name": "阿尔克", "origin": "新增MOD", "skills": []}]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "localApi.json"
            path.write_text(json.dumps({"roleData": [role]}), encoding="utf-8")
            enrich_legacy_reference({"meta": {}, "characters": characters}, path)
        self.assertNotIn("legacyReference", characters[0])
        self.assertNotIn("aliases", characters[1])

    def test_decoder_rejects_truncated_or_oversized_payload(self):
        self.assertEqual(decode_legacy_json(packed([{"hello": "中文"}])), [{"hello": "中文"}])
        with self.assertRaises((ValueError, lzma.LZMAError)):
            decode_legacy_json(packed([1])[:28])
        bad = bytearray.fromhex(packed([1]))
        bad[5:13] = (2 ** 32).to_bytes(8, "little")
        with self.assertRaises(ValueError):
            decode_legacy_json(bad.hex())


if __name__ == "__main__":
    unittest.main()
