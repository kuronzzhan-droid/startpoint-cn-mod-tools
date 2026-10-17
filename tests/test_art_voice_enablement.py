"""从原生 toast 分支和 CSV 字段检验，防止只有音频文件的假修复。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parents[1]))
import wf_art_voice_enablement as fix
import wf_art_voice_pack as pack
from wf_art_voice_lines import ROLES

OLD = ('ruin_girl|ruin_girl_halfanv|urban_soldier|bishop_girl|bishop_girl_smr20|'
       'red_gunner|urban_soldier_ny21|ruin_girl_smr21|magical_bayonetter|'
       'dragon_slayer|dragon_slayer_smr21|berserker')
CODES = {code for _, code, _ in ROLES.values()} | {
    'ruin_girl', 'ruin_girl_halfanv', 'ruin_girl_smr21', 'ruin_girl_3halfanv',
    'urban_soldier', 'dragon_slayer_smr21', 'ordinary_character'}


class VoiceEnablementTests(unittest.TestCase):
    def test_real_nephtim_toast_reproduced_and_other_roles_not_blocked(self):
        for role, (_, code, _) in ROLES.items():
            for slot in ('home/home_0', 'battle/skill_ready', 'battle/skill_3', 'ally/join'):
                self.assertEqual(role == 'nephtim', fix.native_excluded(f'character/{code}/voice/{slot}', OLD))

    def test_narrow_rule_preserves_official_and_other_rule_bytes(self):
        after = fix.narrow_exclusions(OLD, CODES)
        self.assertTrue(after.endswith('|'+OLD.partition('|')[2]))
        for code in CODES:
            for slot in ('home/test', 'battle/skill_0', 'ally/evolution'):
                path = f'character/{code}/voice/{slot}'
                expected = False if code == 'ruin_girl_campus' else fix.native_excluded(path, OLD)
                self.assertEqual(expected, fix.native_excluded(path, after), path)
        self.assertEqual(after, fix.narrow_exclusions(after, CODES))

    def test_full_voice_boundary_not_similar_campus_prefix(self):
        after = fix.narrow_exclusions(OLD, CODES)
        self.assertIn('character/ruin_girl/voice/', after)
        self.assertFalse(fix.native_excluded('character/ruin_girl_campus/voice/home/test', after))
        self.assertTrue(fix.native_excluded('character/ruin_girl_3halfanv/voice/home/test', after))

    def test_original_scenario_and_production_sound_exclusions_preserved(self):
        after = fix.narrow_exclusions(OLD, CODES)
        paths = ['sound_effect/unique/se_ruin_girl_special_attack']
        paths += [f'bgm/character_unique/{code}/{code}' for code in (
            'ruin_girl', 'ruin_girl_halfanv', 'ruin_girl_smr21', 'ruin_girl_3halfanv')]
        for path in paths:
            for suffix in ('', '.mp3'):
                self.assertTrue(fix.native_excluded(path+suffix, OLD))
                self.assertTrue(fix.native_excluded(path+suffix, after))

    def test_native_empty_token_and_unreviewed_broad_rules_fail_closed(self):
        for rules in ('', OLD+'|', 'character/|'+OLD, 'ruin_girl_campus|'+OLD):
            with self.assertRaises(ValueError):
                fix.narrow_exclusions(rules, CODES)

    def test_builder_returns_real_c11_without_altering_descriptions(self):
        original = {cid: [[f'{cid}:{i}' for i in range(12)]] for cid, _, _ in ROLES.values()}
        before = deepcopy(original)
        result = pack.enablement_rows(
            {code: [[code]] for code in CODES}, original, {fix.EXCLUDE_KEY: [[OLD]]})
        self.assertEqual(before, original)
        for cid, rows in result[fix.TEXT_TABLE].items():
            self.assertEqual('AI 合成配音', rows[0][11])
            self.assertEqual(before[cid][0][:11], rows[0][:11])
            self.assertNotEqual('(None)', rows[0][11])
        self.assertEqual({fix.EXCLUDE_KEY}, set(result[fix.UI_TABLE]))


if __name__ == '__main__':
    unittest.main()
