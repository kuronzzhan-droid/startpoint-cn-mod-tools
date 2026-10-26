import unittest
import wf_seasonal7_voice as voice
from wf_seasonal7_voice_merge import remap_slot, merge_speech, check_native_bindings


class VoiceMergeTest(unittest.TestCase):
    def test_no_collision_and_all_sources_preserved(self):
        mapped=[remap_slot(s) for s in voice.SLOTS]
        self.assertEqual(len(mapped),22)
        self.assertEqual(len(set(mapped)|set(voice.SLOTS)),44)

    def test_battle_pools_have_contiguous_native_indices(self):
        for name,count in [('skill',4),('battle_start',2),('power_flip',2),('outhole',2),('win',2)]:
            old=[f'battle/{name}_{i}' for i in range(count)]
            self.assertEqual(old+[remap_slot(s) for s in old],[f'battle/{name}_{i}' for i in range(2*count)])

    def test_preparation_routes_remain_separate(self):
        self.assertEqual(remap_slot('battle/skill_ready'),'battle/skill_ready_alt')
        self.assertEqual(remap_slot('battle/matched_skill_ready'),'battle/matched_skill_ready_alt')

    def test_invalid_slot_fails(self):
        for slot in ['battle/skill_9','home/home_6','battle/noise_0']:
            with self.assertRaises(ValueError):remap_slot(slot)

    def test_speech_preserves_kinds_unlocks_and_original_subtitles(self):
        before=[['0','2','','旧主页','home/home_0'],['1','','1','旧觉醒','ally/evolution'],
                ['2','','','旧加入','ally/join']]
        added=[{'slot':r[4],'zh':'新'+r[3]} for r in before]
        after=merge_speech(before,added)
        self.assertEqual(after[0],before[0])
        for old,new in zip(before[1:],after[1:3]):
            self.assertEqual(new[:3],old[:3])
            self.assertEqual(new[3],'新'+old[3])
            self.assertEqual(new[4],old[4])
        self.assertEqual(len(after),4)
        for old,new in zip(before[:1],after[3:]):
            self.assertEqual(old[:3],new[:3]);self.assertEqual(new[3],'新'+old[3])
            self.assertEqual(new[4],remap_slot(old[4]))

    def test_duplicate_or_missing_donor_rejected(self):
        row=['0','2','','hello','home/home_0']
        for slot in ['home/home_0','ally/join']:
            row[4]=slot
            for before in [[],[row,row]]:
                with self.assertRaises(ValueError):merge_speech(before,[{'slot':slot,'zh':'x'}])

    def test_fixed_speech_uses_new_subtitle_without_adding_rows(self):
        before=[['2','','','旧加入','ally/join'],['1','','1','旧觉醒','ally/evolution']]
        added=[{'slot':r[4],'zh':'新台词'} for r in before]
        after=merge_speech(before,added)
        self.assertEqual(len(after),len(before))
        for old,new in zip(before,after):
            self.assertEqual(new[:3],old[:3]);self.assertEqual(new[4],old[4])
            self.assertEqual(new[3],'新台词')

    def test_pre_and_post_awakening_bindings(self):
        available=set(voice.SLOTS)|{remap_slot(s) for s in voice.SLOTS}
        rows=[['0','2','','主页','home/home_0'],['2','','','加入','ally/join'],
              ['1','','1','觉醒','ally/evolution']]
        self.assertEqual(check_native_bindings(rows,available)['home_visible_by_evolution'],{'0':1,'1':1})
        for constraint in ('0','1'):
            rows[0][1]=constraint
            with self.assertRaisesRegex(ValueError,'2265'):
                check_native_bindings(rows,available)

    def test_missing_audio_and_awakening_binding_rejected(self):
        available=set(voice.SLOTS)|{remap_slot(s) for s in voice.SLOTS}
        rows=[['0','2','','主页','home/home_0'],['2','','','加入','ally/join'],
              ['1','','1','觉醒','ally/evolution']]
        for slot in ['home/home_0','battle/skill_ready','battle/skill_7']:
            with self.assertRaises(ValueError):check_native_bindings(rows,available-{slot})
        with self.assertRaises(ValueError):check_native_bindings(rows[:-1],available)


if __name__=='__main__':unittest.main()
