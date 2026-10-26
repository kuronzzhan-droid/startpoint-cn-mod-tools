"""数据补丁回归：候选漂移隔离、原始行保留、JSON片段和输入竞态。"""
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zlib

pass  # Imports resolve from this checkout/package, not external source copies.
import wf_mod_tool as core
import wf_content_revision_patch as patch


def ordered(rows):
    return core.build_orderedmap_raw_rows(core.OrderedMap('test',list(rows),list(rows.values()),Path('.')))


def compressed(text):
    return zlib.compress(text.encode('utf-8'),1)


class ContentRevisionPatchTests(unittest.TestCase):
    def test_ordered_changes_only_selected_rows_and_keeps_exact_foreign_bytes(self):
        live = ordered({'own':compressed('old'),'foreign':compressed('original')})
        candidate = ordered({'own':compressed('new'),'foreign':compressed('STALE')})
        merged, report = patch.merge_ordered(live,candidate,{'own'})
        rows = core.read_orderedmap_raw_rows_from_bytes(merged)
        self.assertEqual(rows.rows[1],compressed('original'))
        self.assertEqual(rows.rows[0],compressed('new'))
        self.assertEqual(report['changed_keys'],['own'])
        self.assertEqual(report['preserved_row_count'],1)
        self.assertEqual(report['excluded_candidate_differences'],['foreign'])

    def test_ordered_no_change_returns_original_file_bytes_and_new_panel_key_allowed(self):
        live = ordered({'own':compressed('same'),'foreign':compressed('x')})
        candidate = ordered({'own':compressed('same'),'foreign':compressed('stale')})
        merged, report = patch.merge_ordered(live,candidate,{'own'})
        self.assertIs(merged,live)
        self.assertEqual(report['changed_keys'],[])
        candidate = ordered({'own':compressed('same'),'panel':compressed('new')})
        merged, report = patch.merge_ordered(live,candidate,{'panel'})
        self.assertEqual(core.read_orderedmap_raw_rows_from_bytes(merged).keys,['own','foreign','panel'])
        self.assertEqual(report['changed_keys'],['panel'])

    def test_missing_candidate_claim_does_not_delete_live(self):
        with self.assertRaisesRegex(ValueError,'missing candidate'):
            patch.merge_ordered(ordered({'a':b'1'}),ordered({'b':b'2'}),{'a'})

    def test_json_preserves_all_non_target_utf8_formatting_and_value_bytes(self):
        live = '{\n  "甲" : [ "old" ],\n  "foreign" : { "quoted":"a,}\\\"b", "number": 1.00 },\n "next": [3, 4]\n}\n'.encode()
        candidate = json.dumps({'甲':['新'],'foreign':'stale','next':[100]},ensure_ascii=False).encode()
        merged, report = patch.merge_json(live,candidate,{'甲'})
        self.assertEqual(merged,live.replace(b'[ "old" ]','["新"]'.encode()))
        self.assertEqual(report['changed_keys'],['甲'])
        self.assertEqual(report['preserved_row_count'],2)
        self.assertEqual(report['excluded_candidate_differences'],['foreign','next'])

    def test_json_no_semantic_change_and_duplicate_keys_rejected(self):
        live=b'{ "a" : 1.00, "other": [2] }\n'
        self.assertIs(patch.merge_json(live,b'{"a":1,"other":3}',{'a'})[0],live)
        for raw in (b'{"a":1,"a":2}', b'{"a":{"x":1,"x":2}}', b'{"a":NaN}'):
            with self.assertRaises(ValueError):patch.merge_json(raw,b'{"a":2}',{'a'})

    def test_action_description_and_character_text_reject_other_cell_changes(self):
        before=core.encode_action_skill_row([('1',['Name','old','cost']),('2',['Name+','old','cost'])])
        allowed=core.encode_action_skill_row([('1',['Name','new','cost']),('2',['Name+','new','cost'])])
        patch.validate_text_only(patch.ACTION,before,allowed)
        wrong=core.encode_action_skill_row([('1',['Name','new','CHANGED']),('2',['Name+','new','cost'])])
        with self.assertRaises(ValueError):patch.validate_text_only(patch.ACTION,before,wrong)
        old=[['name','a','b','c','skill','old','skill+','old']]
        new=[['name','a','b','c','skill','new','skill+','new']]
        pack=lambda value: zlib.compress(core.write_csv_lines(value).rstrip('\n').encode())
        patch.validate_text_only(patch.TEXT,pack(old),pack(new))
        new[0][0]='other identity'
        with self.assertRaises(ValueError):patch.validate_text_only(patch.TEXT,pack(old),pack(new))

    def test_apply_rechecks_sources_before_creating_output_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); source=root/'input';source.write_bytes(b'base')
            output=root/'work/codex_out/patch'
            result=patch.PatchResult(root,output,{('common','master/test.orderedmap'):b'new'},
                {'files':[]},{source:b'base'})
            source.write_bytes(b'drift')
            with self.assertRaisesRegex(ValueError,'changed after plan'):result.write()
            self.assertFalse(output.exists())
            source.write_bytes(b'base');result.write()
            self.assertEqual((output/'roots/common/master/test.orderedmap').read_bytes(),b'new')
            self.assertEqual(source.read_bytes(),b'base')
            with self.assertRaisesRegex(ValueError,'already exists'):result.write()

    def test_output_cannot_escape_ignored_roots_or_symlink_to_live(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            with self.assertRaises(ValueError):patch.PatchResult(root,root/'assets',{}, {},{})
            with self.assertRaises(ValueError):patch.PatchResult(root,root/'work/codex_out/../../assets',{}, {},{})
            with self.assertRaises(ValueError):patch.PatchResult(root,root/'work/codex_out/patch',
                {('common','../escape'):b'x'}, {},{})


if __name__=='__main__':unittest.main()
