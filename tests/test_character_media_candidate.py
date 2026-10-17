from pathlib import Path
import json
import sys
import tempfile
import unittest
import zlib

sys.path.insert(0,str(Path(__file__).parents[1]))
import wf_character_media_candidate as media
import wf_character_pack as pack
import wf_quest_lib as tables
import wf_mod_tool as core


class MediaCandidateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.package=Path(self.tmp.name)/'work/character_packs/test/package'
        self.code,self.cid='test_campus','119989'
        self.row=[self.code]+['']*35
        self.row[9]='(None)'
        text=core.write_csv_lines([self.row]).rstrip('\n')
        self.source=tables.build_node({self.cid:text,'foreign':'unchanged raw row'})
        path=self.package/'roots/common'/media.CHARACTER
        path.parent.mkdir(parents=True);path.write_bytes(self.source)
        manifest=dict(character_id=int(self.cid),code_name=self.code,qa={},snapshot={},
            roots={'common':[dict(logical_path=media.CHARACTER,sha256=media.sha(self.source),size=len(self.source))],
                   'medium':[],'android':[],'server':[]},
            tables=[dict(root='common',logical_path=media.CHARACTER,codec_id='flat',outer_keys=[self.cid])])
        (self.package/'manifest.json').write_bytes(pack.canonical_manifest_bytes(manifest))

    def encoded(self,row):return zlib.compress(core.write_csv_lines([row]).rstrip('\n').encode())

    def update(self,row,key=None):
        return media.apply(self.package,tables={media.CHARACTER:dict(source=self.source,codec='flat',
            rows={key or self.cid:self.encoded(row)})})

    def test_route_changes_preserve_foreign_compressed_bytes(self):
        row=self.row.copy();row[9:17]=['3','','','','',self.code+'_voice_ready','false','false']
        result=self.update(row)
        before=core.read_orderedmap_raw_rows_from_bytes(self.source)
        after=core.read_orderedmap_raw_rows_from_bytes((self.package/'roots/common'/media.CHARACTER).read_bytes())
        self.assertEqual(before.rows[1],after.rows[1])
        self.assertTrue(result['files'][0]['changed'])
        self.assertFalse(result['writes_live'])

    def test_stat_or_foreign_key_change_refused_without_writes(self):
        row=self.row.copy();row[2]='999'
        for key in (self.cid,'other'):
            with self.assertRaises(ValueError):self.update(row,key)
        self.assertEqual((self.package/'roots/common'/media.CHARACTER).read_bytes(),self.source)

    def test_other_character_asset_and_stale_candidate_refused(self):
        with self.assertRaises(ValueError):
            media.apply(self.package,assets={('medium','character/other/ui/square_0.png'):b'bad'})
        (self.package/'roots/common'/media.CHARACTER).write_bytes(b'drift')
        with self.assertRaisesRegex(ValueError,'hash drift'):self.update(self.row)

    def test_empty_or_unknown_table_cannot_bypass_allowlist(self):
        before=(self.package/'manifest.json').read_bytes()
        for logical in (media.CHARACTER,'master/unrelated.orderedmap'):
            with self.assertRaisesRegex(ValueError,'unsupported or empty'):
                media.apply(self.package,tables={logical:dict(source=self.source,codec='flat',rows={})})
        self.assertEqual((self.package/'manifest.json').read_bytes(),before)

    def test_nested_ready_rows_claim_both_evolution_levels(self):
        key=self.code+'_voice_ready'
        row=core.encode_action_skill_row([('1',['program1']+['']*16),('2',['program2']+['']*16)])
        source=core.build_orderedmap_raw_rows(core.OrderedMap('',[],[],Path('.')))
        media.apply(self.package,tables={media.SWITCH:dict(source=source,codec='switched_nested',rows={key:row})})
        manifest=json.loads((self.package/'manifest.json').read_bytes())
        claim=next(x for x in manifest['tables'] if x['logical_path']==media.SWITCH)
        self.assertEqual(claim['inner_keys'],[dict(outer_key=key,keys=['1','2'])])


if __name__=='__main__':unittest.main()
