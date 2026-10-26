import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wf_art_voice_routes as routes
from wf_art_voice_lines import ROLES


def fixture():
    characters, actions = {}, {}
    for role, (cid, code, _) in ROLES.items():
        row = ['preserve-' + str(i) for i in range(39)]
        row[0] = row[8] = code
        row[9:17] = ['(None)', '', '', '', '', '', '', '']
        characters[cid] = [row]
        actions[code] = {}
        for level in ('1', '2'):
            actions[code][level] = [[code + level, 'description', 'icon', 'true', '550',
                '500' if level == '2' else '550', '1',
                f'battle/action/skill/action/rare5/{code}${code}_{level}',
                '1', '0', '120', '', '0', '-300', '', '',
                '1', '0', '200', '', '0', '-250', '', '']]
    return characters, actions, {'119996': [['unique_lion_reborn_flame', '永恒之火']]}


class NativeReadyRouteTests(unittest.TestCase):
    def test_both_evolution_levels_preserve_program_autoplay_and_weight(self):
        characters, actions, unique = fixture()
        before = copy.deepcopy((characters, actions, unique))
        output = routes.build_routes(characters, actions, unique)
        self.assertEqual((characters, actions, unique), before)
        for role, (cid, code, _) in ROLES.items():
            target = output['character_rows'][cid][0]
            self.assertEqual(target[:9], characters[cid][0][:9])
            self.assertEqual(target[17:], characters[cid][0][17:])
            for level in ('1', '2'):
                switched = output['switched_rows'][routes.switch_key(code)][level][0]
                original = actions[code][level][0]
                self.assertEqual(switched, original[7:24])
                self.assertEqual(output['metadata'][role]['levels'][level]['max_skill_weight'], original[5])

    def test_four_roles_reuse_only_their_native_flag(self):
        result = routes.build_routes(*fixture())
        for role, (cid, code, _) in ROLES.items():
            if role == 'lion': continue
            self.assertEqual(result['character_rows'][cid][0][9:17],
                ['3', '', '', '', '', routes.switch_key(code), 'false', 'false'])

    def test_lion_uses_self_flame_not_enemy_brand_or_inferno(self):
        result = routes.build_routes(*fixture())
        row = result['character_rows']['119996'][0]
        self.assertEqual(row[9:12], ['1', '28', '119996'])
        self.assertNotIn('1199960', row[9:17])
        self.assertNotIn('1199969', row[9:17])
        self.assertEqual(row[15:17], ['false', 'false'])

    def test_rejects_unknown_switch_missing_level_and_wrong_flame(self):
        for mutation in ('switch', 'level', 'flame'):
            c, a, u = fixture()
            if mutation == 'switch': c['119989'][0][9] = '0'
            elif mutation == 'level': del a['lady_summoner_campus']['2']
            else: u['119996'][0][1] = '灼烙'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                routes.build_routes(c, a, u)

    def test_exact_reapplication_is_idempotent(self):
        c, a, u = fixture()
        first = routes.build_routes(c, a, u)
        second = routes.build_routes(first['character_rows'], a, u)
        self.assertEqual(first, second)

    def test_never_emits_dsl_or_action_skill_replacements_or_patch_capability(self):
        result = routes.build_routes(*fixture())
        self.assertEqual(set(result), {'character_rows', 'switched_rows', 'metadata'})
        self.assertEqual(routes.metadata()['new_client_capabilities'], [])
        self.assertEqual(len(result['character_rows']), 5)
        self.assertEqual(len(result['switched_rows']), 5)


if __name__ == '__main__': unittest.main()
