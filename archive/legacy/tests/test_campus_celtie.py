"""Guard candidate isolation, donor fidelity, FEVER branching, and native legality."""

from wf.paths import root_path
from copy import deepcopy
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from PIL import Image

pass  # Imports resolve from this checkout/package, not external source copies.
import wf_assets
import wf_client_legality as legality
import wf_campus_celtie_common as C
import wf_campus_celtie_assets as A
import wf_campus_celtie_data as D


class CandidateIsolationTests(unittest.TestCase):
    def test_traversal_absolute_and_alternate_stream_are_rejected(self):
        for logical in ('../assets/character.json','/assets/character.json',
                ('${WF_ROOT}/startpoint-cn/assets/character.json'.replace("${WF_ROOT}", str(root_path()))),'foo:bar','character//bad.png'):
            with self.subTest(logical=logical),self.assertRaises(ValueError):
                C.output('common',logical)
        with self.assertRaises(ValueError):
            C.output('upload','test.png')

    def test_candidate_refuses_any_existing_live_identity(self):
        class Table:
            def text_rows(self):
                return {C.CID:'already occupied'}
        with patch.object(C.core,'load_table',return_value=Table()),patch.object(C,'write') as writer:
            with self.assertRaisesRegex(ValueError,'occupied'):
                C.flat('master/character/character.orderedmap',{C.CID:'replacement'})
            writer.assert_not_called()

    def test_mana_remap_only_changes_known_node_and_character_ids(self):
        old=str(int(C.TEMPLATE_ID)*2)
        self.assertEqual(str(int(C.CID)*2)+'201',C.remap(old+'201'))
        self.assertEqual(old+'20',C.remap(old+'20'))
        self.assertEqual('3141201',C.remap('3141201'))
        self.assertEqual(C.CID,C.remap(C.TEMPLATE_ID))

    def test_recolor_preserves_alpha_and_non_target_skin_and_hair(self):
        pixels=[(230,174,114,255),(255,220,150,255),(20,30,220,255),(255,0,0,0)]
        original=Image.new('RGBA',(4,1));original.putdata(pixels)
        stream=io.BytesIO();original.save(stream,format='PNG')
        stored,image,report=A.recolor(wf_assets.png_encode(stream.getvalue()))
        self.assertEqual(original.getchannel('A').tobytes(),image.getchannel('A').tobytes())
        self.assertEqual(pixels[:2],list(image.getdata())[:2])
        self.assertNotEqual(pixels[2],list(image.getdata())[2])
        self.assertEqual(1,report['changed_pixels'])
        self.assertEqual((4,1),wf_assets.png_dims(stored))


@unittest.skipUnless((C.ROOT/'.cdn/cn/archive-common-full').exists(),'local official CDN integration fixture unavailable')
class OfficialDonorIntegrationTests(unittest.TestCase):
    def test_appended_fever_command_preserves_entire_official_sword_lifecycle(self):
        for level in ('1','2'):
            base=C.amf(C.official(A.program(C.TEMPLATE_CODE,level)+A.SUFFIX))
            candidate,_=A.skill(level)
            restored=deepcopy(candidate)
            appendix=restored[11][1].pop()
            # Ignore only the deliberate independent effect-namespace remapping.
            import json
            restored=json.loads(json.dumps(restored).replace(C.CODE,C.TEMPLATE_CODE))
            self.assertEqual(base,restored)
            self.assertEqual('ConditionalsFeverMode',appendix[1][0])
            self.assertEqual(['Block',[]],appendix[1][1])
            self.assertEqual(1,len(C.commands(appendix[1][2],'AddFeverPoint')))

    def test_invalid_subject_is_rejected_before_encoding(self):
        candidate,_=A.skill('2')
        attack=C.commands(candidate,'CreateNormalAttack')[0]
        attack[1]=987654
        with self.assertRaises(ValueError):
            A.validate_dsl(candidate)

    def test_fever_kit_uses_native_wind_damage_and_cooldowns(self):
        leader,abilities,_=D.build_kit()
        damage=[row for rows in abilities.values() for row in rows if row[47]=='254']
        self.assertEqual(2,len(damage))
        self.assertEqual({'23','8'},{row[27] for row in damage})
        self.assertTrue(all(int(row[35])>=600 for row in damage))
        self.assertTrue(all(row[1]=='false' for row in damage))
        self.assertFalse(any(row[47] in ('629','724') for rows in abilities.values() for row in rows))
        for kind,rows in [('leader_ability',leader),('ability',[r for a in abilities.values() for r in a])]:
            for row in rows:
                self.assertFalse(legality.client_legality_problems(kind,row))
                self.assertFalse(legality.ability_element_column_problems(kind,row,3))


if __name__=='__main__':
    unittest.main()
