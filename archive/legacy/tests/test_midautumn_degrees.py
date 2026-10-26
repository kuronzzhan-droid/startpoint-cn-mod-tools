import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image

pass  # Imports resolve from this checkout/package, not external source copies.
import wf_midautumn_degrees as d
import wf_share_update_codec as codec


class MidautumnDegreeTests(unittest.TestCase):
    def test_reviewed_kyle_extras_load_with_existing_ids_and_reject_wrong_identity(self):
        image = io.BytesIO()
        plate = Image.new('RGBA', (320, 50), (0, 0, 0, 0))
        plate.paste((80, 120, 220, 255), (20, 10, 300, 40))
        plate.save(image, format='PNG')
        raw = image.getvalue()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'plate.png').write_bytes(raw)
            plates = [dict(role=role, character_id=d.specs.get_spec(role).cid, state=state,
                           degree_id=9910049+2*i+state, file='plate.png',
                           sha256=hashlib.sha256(raw).hexdigest(), name=role, title='称号')
                      for i, role in enumerate(d.specs.all_keys()) for state in (0, 1)]
            plates += [dict(plates[0], role='kyle', character_id=139990, state=state,
                            degree_id=9910071+state) for state in (2, 3, 4)]
            manifest = root/'plate-manifest.json'
            manifest.write_text(json.dumps(dict(plates=plates)), encoding='utf-8')
            result = d.load_art(root)
            self.assertEqual(len(result), 27)
            self.assertEqual([x['item']['degree_id'] for x in result[-3:]], [9910073,9910074,9910075])
            self.assertEqual(result[-1]['logical'], 'dynamic/degree/degree_mod_character_139990_awake4.png')
            plates[-1]['character_id'] = 119990
            manifest.write_text(json.dumps(dict(plates=plates)), encoding='utf-8')
            with self.assertRaises(ValueError): d.load_art(root)

    def test_names_preserve_every_nontitle_cell(self):
        for logical, changes in [(d.CHARACTER, {18:d.LEADER}),
                                 (d.TEXT, {4:d.SKILL, 6:d.SKILL+'＋', 10:d.LEADER})]:
            rows = [[str(i) for i in range(40)]]
            before = copy.deepcopy(rows)
            actual = d.rename_rows(logical, rows)
            self.assertEqual(rows, before)
            for index, value in enumerate(before[0]):
                self.assertEqual(actual[0][index], changes.get(index, value))

    def test_nested_skill_only_changes_title_not_program_or_energy(self):
        rows = [['old title', 'original description', '500', '', '', '', '', 'original/program']]
        raw = codec.pack({d.NAME_KEYS[d.ACTION]: codec.pack({
            '1':codec.csv_write(rows), '2':codec.csv_write(rows)}), 'other':b'untouched'})
        operations = d.name_operations(d.ACTION, raw)
        self.assertEqual(len(operations), 2)
        for op in operations:
            self.assertEqual(op['after']['csv'][0][1:], rows[0][1:])
            self.assertEqual(op['after']['csv'][0][0], d.SKILL+('＋' if op['path'][1]=='2' else ''))

    def test_unrecognized_skill_reference_rejected(self):
        with self.assertRaises(ValueError): d.rename_rows(d.CAS, [['unrelated text']])

    def test_reference_and_rename_are_idempotent(self):
        first = d.rename_rows(d.CAS, [['强化『月下咆哮·烈焰甩尾』：光环的范围扩大']])
        self.assertEqual(first, [['强化『烈焰轰鸣』：光环的范围扩大']])
        self.assertEqual(first, d.rename_rows(d.CAS, first))


if __name__ == '__main__': unittest.main()
