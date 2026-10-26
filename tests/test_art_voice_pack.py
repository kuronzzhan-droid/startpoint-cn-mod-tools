import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wf_art_voice_pack as pack
from wf_art_voice_lines import ROLES


def plan_fixture():
    plan=[]
    for role,count in pack.EXPECTED_COUNTS.items():
        slots=['battle/skill_ready','battle/matched_skill_ready',*(f'battle/skill_{i}' for i in range(4))]
        slots += [f'home/home_{i}' for i in range(count-len(slots))]
        plan.extend(dict(role=role,slot=slot,ja='台詞'+str(i),zh='新字幕'+str(i)) for i,slot in enumerate(slots))
    return plan


class ArtVoicePackTests(unittest.TestCase):
    def test_all_native_slots_are_present_and_contiguous(self):
        plan=plan_fixture();result=pack.validate_plan(plan)
        self.assertEqual(sum(map(len,result.values())),102)
        self.assertEqual(pack.metadata(plan)['new_client_capabilities'],[])

    def test_duplicate_missing_and_unreachable_numbered_slots_rejected(self):
        for change in ('duplicate','missing','gap'):
            plan=plan_fixture()
            if change=='duplicate':plan[1]=copy.deepcopy(plan[0])
            elif change=='missing':plan.pop()
            else:plan[3]['slot']='battle/skill_6'
            with self.subTest(change=change),self.assertRaises(ValueError):pack.validate_plan(plan)

    def test_subtitles_preserve_unlock_columns_and_nonselected_lion_ally(self):
        plan=plan_fixture();source={}
        for role,(cid,_code,_persona) in ROLES.items():
            source[cid]=[['0','4','awake-marker','原字幕',row['slot']] for row in plan if row['role']==role and row['slot'].startswith('home/')]
        source['119996'].append(['2','','','保留加入台词','ally/join'])
        before=copy.deepcopy(source);after=pack.speech_rows(source,plan)
        self.assertEqual(source,before)
        for cid,rows in after.items():
            for old,new in zip(source[cid],rows):
                self.assertEqual(old[:3],new[:3]);self.assertEqual(old[4],new[4])
        self.assertEqual(after['119996'][-1],source['119996'][-1])

    def test_unbound_home_subtitle_is_hard_error(self):
        plan=plan_fixture();source={cid:[] for cid,_code,_persona in ROLES.values()}
        with self.assertRaisesRegex(ValueError,'lacks native subtitle binding'):pack.speech_rows(source,plan)

    def test_external_plan_cannot_escape_voice_namespace(self):
        for slot in ('home/../../other/ui/pixel', 'home\\home_0', '/home/home_0',
                     'home/home_0:stream', 'story/home_0'):
            plan=plan_fixture();plan[6]['slot']=slot
            with self.subTest(slot=slot), self.assertRaises(ValueError):pack.validate_plan(plan)


if __name__=='__main__':unittest.main()
