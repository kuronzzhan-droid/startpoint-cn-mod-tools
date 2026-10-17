from copy import deepcopy
from fractions import Fraction
from pathlib import Path
import sys
import unittest
import zlib

sys.path.insert(0,str(Path(__file__).parents[1]))
import wf_content_gacha_racing as fix
from wf_content_gacha import BIG_BOSS_ZERO, MINIBOSSES, probability
from wf_content_gacha_abyss import LEGACY_22, FEATURED
from wf_content_gacha_candidate import odds_definitions
from wf_gacha_odds_sync import build_nested
import wf_mod_tool as core

CUSTOM = BIG_BOSS_ZERO | MINIBOSSES | set(LEGACY_22) | set(FEATURED) | {129992,139995,129997,179999}


def source():
    assert len(CUSTOM)==68
    entries=[dict(id=cid,rank=5,odds=0 if cid in BIG_BOSS_ZERO else 10000,
                  isRateUp=cid in MINIBOSSES,isLimited=True,isExchangeable=cid not in BIG_BOSS_ZERO,
                  trialReadingForced=False) for cid in sorted(CUSTOM)]
    entries.insert(7,dict(id=111001,rank=5,odds=260000,isRateUp=False,isLimited=False,isExchangeable=False,trialReadingForced=False))
    entries.append(dict(id=111002,rank=5,odds=260000,isRateUp=True,isLimited=True,isExchangeable=True,trialReadingForced=True))
    return {'990001':{'protected':'Abyss'},'990002':dict(rankRates={'normal':[950,20,30],'multiGuarantee':[950,50]},
            pool={'1':entries,'2':[],'3':[]})}


class RacingTests(unittest.TestCase):
    def test_three_stable_groups_and_only_drawable_red(self):
        old=source();original=deepcopy(old);new=fix.revise_racing(old,CUSTOM)
        self.assertEqual(original,old);self.assertEqual(new,fix.revise_racing(new,CUSTOM))
        entries=new['990002']['pool']['1'];oldmap={e['id']:e for e in old['990002']['pool']['1']}
        self.assertEqual([e['id'] for e in old['990002']['pool']['1'] if e['id'] in CUSTOM-BIG_BOSS_ZERO],[e['id'] for e in entries[:43]])
        self.assertEqual(fix.ANNIHILATOR,entries[43]['id'])
        self.assertEqual(BIG_BOSS_ZERO,{e['id'] for e in entries[43:68]})
        self.assertEqual([111001,111002],[e['id'] for e in entries[68:]])
        for entry in entries:
            expected=deepcopy(oldmap[entry['id']])
            if entry['id'] in CUSTOM-BIG_BOSS_ZERO:expected['isRateUp']=True
            self.assertEqual(expected,entry)
            self.assertEqual(probability(old['990002'],entry['id']),probability(new['990002'],entry['id']))
        self.assertEqual(old['990001'],new['990001'])

    def test_native_uses_same_order_and_preserves_non_flag_row_bytes(self):
        old=source();new=fix.revise_racing(old,CUSTOM);pointer=['']*17;pointer[11]='r';pointer[14:17]=['c3','c4','c5']
        lines=dict(odds_definitions(pointer,old['990002']))['c5'];raw=build_nested('c5',[str(i) for i in range(len(lines))],lines)
        updated=fix.reorder_native(raw,old['990002'],new['990002'])
        def parsed(data):
            outer=core.read_orderedmap_raw_rows_from_bytes(data);inner=core.read_orderedmap_raw_rows_from_bytes(outer.rows[0])
            return [(core.read_csv_lines(zlib.decompress(row).decode())[0],row) for row in inner.rows]
        before={int(row[0]):(row,raw) for row,raw in parsed(raw)}
        self.assertEqual([e['id'] for e in new['990002']['pool']['1']],[int(row[0]) for row,_ in parsed(updated)])
        for row,chunk in parsed(updated):
            oldrow,oldchunk=before[int(row[0])]
            if row[3]==oldrow[3]:self.assertEqual(oldchunk,chunk)
            else:
                self.assertIn(int(row[0]),CUSTOM-BIG_BOSS_ZERO);row[3]=oldrow[3];self.assertEqual(oldrow,row)

    def test_unauthorized_probability_roster_and_test_characters_fail(self):
        for mutate in ('weight','missing','duplicate','test','rank'):
            data=source();entries=data['990002']['pool']['1']
            if mutate=='weight':next(e for e in entries if e['odds']==10000)['odds']=10001
            if mutate=='missing':entries.pop()
            if mutate=='duplicate':entries.append(deepcopy(entries[0]))
            if mutate=='test':entries.append(dict(id=119998,odds=0))
            if mutate=='rank':data['990002']['rankRates']['normal'][0]=951
            with self.assertRaises(ValueError,msg=mutate):fix.revise_racing(data,CUSTOM)


if __name__=='__main__':unittest.main()
