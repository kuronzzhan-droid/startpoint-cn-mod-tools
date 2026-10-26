from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
import hashlib
import json
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wf_assets
import wf_voice_additions_install as installer


class VoiceAdditionInstallTests(unittest.TestCase):
    def test_replay_keeps_prior_delivery_and_original_preimage(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);package=root/'package';package.mkdir()
            evidence=root/'evidence';evidence.mkdir()
            ws=SimpleNamespace(package_dir=package,evidence_dir=evidence,code_name='test_actor',character_id=1)
            older={'delivery_sha256':'earlier','rebuild_command':'earlier input'}
            manifest={'roots':{'common':[]},'snapshot':{'voice_additions_20260924':older},'qa':{}}
            (package/'manifest.json').write_text(json.dumps(manifest),'utf8')
            delivery=root/'delivery';delivery.mkdir()
            raw=wf_assets.mp3_encode(b'\xff\xfb\x90\x00'+bytes(413))
            (delivery/'ready.mp3').write_bytes(raw)
            record={'technical_checks_passed':True,'selection':[{'code':'test_actor','slot':'battle/skill_ready_alt_1',
                'files':{'native':{'path':'ready.mp3','sha256':hashlib.sha256(raw).hexdigest()}}}]}
            (delivery/'交付清单.json').write_text(json.dumps(record),'utf8')
            with patch.object(installer.workspace,'load_workspace',return_value=ws):
                first=installer.install(root,'pack',delivery,apply=True)
                saved=(package/'manifest.json').read_bytes()
                second=installer.install(root,'pack',delivery,apply=True)
            self.assertEqual(first,second)
            self.assertIsNone(first['changed'][0]['before_sha256'])
            self.assertEqual(saved,(package/'manifest.json').read_bytes())
            history=json.loads(saved)['snapshot']['voice_addition_history']
            self.assertEqual(history[0],older)
            self.assertEqual(len(history),2)

    def test_delivery_hash_mismatch_is_rejected_before_candidate_write(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);package=root/'package';package.mkdir()
            original=b'{"roots":{"common":[]},"snapshot":{},"qa":{}}'
            (package/'manifest.json').write_bytes(original)
            ws=SimpleNamespace(package_dir=package,code_name='test_actor',character_id=1)
            (root/'ready.mp3').write_bytes(b'changed')
            document={'technical_checks_passed':True,'selection':[{'code':'test_actor','slot':'battle/skill_ready_alt_1',
                'files':{'native':{'path':'ready.mp3','sha256':'wrong'}}}]}
            (root/'交付清单.json').write_text(json.dumps(document),'utf8')
            with patch.object(installer.workspace,'load_workspace',return_value=ws),self.assertRaisesRegex(ValueError,'changed after review'):
                installer.install(root,'pack',root,apply=True)
            self.assertEqual((package/'manifest.json').read_bytes(),original)


if __name__=='__main__':unittest.main()
