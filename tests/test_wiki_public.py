import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wf_wiki_public import public_catalog, public_id
from wf_wiki import merge_sources


class PublicExportTests(unittest.TestCase):
    def test_no_internal_codes_raw_source_or_numeric_ids(self):
        data = {"meta": {"sourceHashes": {"battle/secret": "abc"}}, "characters": [{
            "id": "151159", "code": "golden_dragon_jr", "name": "光龙",
            "raw": {"private": 123}, "abilities": [{"key": "551159", "rows": [{"description": "攻击力+300% 切换技能形态[cnmod_inaho_midautumn_enhance_buffs]", "values": ["sensitive", "parameter"]}]}],
            "skills": [{"program": "battle/private", "rawCommands": ["CreateNormalAttack"],
                        "numericDetails": {"rows": [{"label": "伤害", "values": [{"label": "倍率", "value": "10倍"}]}]}}],
        }], "equipment": [{"id": "5920001", "name": "悖论"}]}
        public = public_catalog(data)
        text = json.dumps(public, ensure_ascii=False)
        for private in ["golden_dragon_jr", "151159", "5920001", "551159", "CreateNormalAttack", "sensitive", "battle/private", "cnmod_inaho_midautumn"]:
            self.assertNotIn(private, text)
        self.assertIn("10倍", text)
        self.assertIn("攻击力+300%", text)
        self.assertNotEqual(public['characters'][0]['id'], public['equipment'][0]['id'])
        self.assertEqual(data['characters'][0]['code'], 'golden_dragon_jr')

    def test_route_keys_are_stable(self):
        self.assertEqual(public_id('c', 10), public_id('c', '10'))
        self.assertNotEqual(public_id('c', 10), public_id('w', 10))

    def test_translate_only_chinese_display_enums_without_touching_voice_or_machine_values(self):
        description = "赋予全队(White,Black) Delete状态减益 100%；MySelf 状态DirectAttack3 30%；形态切换Flag2"
        data = {"meta": {}, "characters": [{"id": "1", "name": "White 骑士",
            "kind": "中文MySelf", "description": description,
            "skills": [{"text": "DirectAttack3", "context": "自身Flying 3秒"}],
            "voices": [{"ja": "自身MySelf", "text": description, "zh": "光明的 White 骑士"}],
            "notes": ["魔法少女の White", "Alter Device 正常保留"],
        }]}
        character = public_catalog(data)["characters"][0]
        self.assertEqual(character["description"],
            "赋予全队(光,暗) 解除状态减益 100%；自身 状态直接攻击3段（伤害修正） 30%；形态切换标记2")
        self.assertEqual(character["kind"], "中文MySelf")
        self.assertEqual(character["name"], "White 骑士")
        self.assertEqual(character["skills"], [{"text": "DirectAttack3", "context": "自身浮游 3秒"}])
        self.assertEqual(character["voices"], data["characters"][0]["voices"])
        self.assertEqual(character["notes"], data["characters"][0]["notes"])

    def test_module_source_drift_cannot_overwrite_earlier_fingerprint(self):
        meta = {'sourceHashes': {'master/shared': 'old'}}
        with self.assertRaisesRegex(RuntimeError, '不同版本'):
            merge_sources(meta, {'sourceHashes': {'master/shared': 'new'}})
        self.assertEqual(meta['sourceHashes']['master/shared'], 'old')
        with self.assertRaisesRegex(RuntimeError, '缺失变为存在'):
            merge_sources(meta, {'sourceMissing': ['master/shared']})


if __name__ == '__main__':
    unittest.main()
