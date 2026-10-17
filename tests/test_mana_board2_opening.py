"""未来开放日期只修指定角色；原压缩外行、结束日期和顺序保持。"""
from datetime import datetime, timezone, timedelta
import importlib
from pathlib import Path
import sys
import unittest
import zlib

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import wf_mod_tool as core


def encoded(rows, level=6):
    return zlib.compress(core.write_csv_lines(rows).rstrip('\n').encode(),level)


def fixture():
    keys=['151002','129998','149994','159999','149993','119970','129970','139970','149970','700010']
    rows=[]
    for key in keys:
        start='2026-08-31 00:00:00' if key in ('119970','129970','139970','149970') else '2026-08-30 12:00:00'
        if key=='151002':start='2015-03-01 12:00:00'
        if key=='700010':start='2050-03-01 12:00:00'
        rows.append(encoded([[start,'2199-12-31 23:59:59']],9))
    return core.build_orderedmap_raw_rows(core.OrderedMap('test',keys,rows,Path('test')))


class ManaBoard2OpeningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fix=importlib.import_module('wf_mana_board2_opening')

    def test_only_eight_starts_change_and_foreign_raw_order_is_exact(self):
        raw=fixture();before=core.read_orderedmap_raw_rows_from_bytes(raw)
        output,report=self.fix.patch_table(raw)
        after=core.read_orderedmap_raw_rows_from_bytes(output)
        self.assertEqual(before.keys,after.keys)
        self.assertEqual(set(report['changed_keys']),set(self.fix.TARGET_STARTS))
        for key,a,b in zip(before.keys,before.rows,after.rows):
            if key not in self.fix.TARGET_STARTS:self.assertEqual(a,b)
            else:
                old=core.read_csv_lines(zlib.decompress(a).decode())
                new=core.read_csv_lines(zlib.decompress(b).decode())
                self.assertEqual(new,[[self.fix.OPEN_START,old[0][1]]])
        self.assertEqual(report['foreign_rows_preserved'],2)

    def test_simulated_game_2025_opens_without_altering_character_level(self):
        # Native canManaBoard2Open compares JST master dates to server epoch;
        # it does not read current level or overLimitStep.
        epoch=1755387430
        jst=timezone(timedelta(hours=9))
        def opens(row):
            start,end=(datetime.strptime(s,'%Y-%m-%d %H:%M:%S').replace(tzinfo=jst).timestamp() for s in row)
            return start<=epoch<=end
        for cid,start in self.fix.TARGET_STARTS.items():
            before=[start,'2199-12-31 23:59:59']
            self.assertFalse(opens(before))
            self.assertTrue(opens(self.fix.opening_row(cid,before)))

    def test_idempotence_keeps_all_packed_bytes(self):
        once,_=self.fix.patch_table(fixture());twice,report=self.fix.patch_table(once)
        self.assertEqual(once,twice);self.assertEqual(report['changed_keys'],[])

    def test_preserves_end_and_caller_input(self):
        row=['2026-08-30 12:00:00','2198-01-02 03:04:05'];old=row.copy()
        result=self.fix.opening_row('159999',row)
        self.assertEqual(row,old);self.assertEqual(result[1],old[1])

    def test_unknown_missing_malformed_and_unreviewed_date_rejected(self):
        for cid,row in [('151002',['2026-08-30 12:00:00','2199-12-31 23:59:59']),
                        ('159999',['2027-01-01 00:00:00','2199-12-31 23:59:59']),
                        ('159999',['2026-08-30 12:00:00']),
                        ('159999',['2026-08-30 12:00:00','(None)'])]:
            with self.assertRaises(ValueError):self.fix.opening_row(cid,row)
        table=core.read_orderedmap_raw_rows_from_bytes(fixture());table.keys.pop(1);table.rows.pop(1)
        with self.assertRaises(ValueError):self.fix.patch_table(core.build_orderedmap_raw_rows(table))


if __name__=='__main__':unittest.main()
