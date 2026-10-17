"""雷皇女 莉莉丝 2026-09-27 修订：直击口径换强化弹射，冲刺行换 629 + 配对 248。"""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
pass  # Imports resolve from this checkout/package, not external source copies.
import wf_balance_20260927_lilith as M
import wf_dsl
import wf_share_update_codec as X
import zlib
from wf_client_legality import (client_legality_problems, declared_block_field_problems,
                                invoke_skill_string_problems, required_client_capabilities)
from wf_character_revision import encode_tree
from wf_midautumn_kit_hibiki import dsl_problems as kit_dsl_problems

FIXTURE = Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927_lilith.json'
WORKSPACE = ROOT / 'work/character_packs' / M.PACKAGES[0]
A1, A2, A3, A4, A5 = (M.ABILITY[i] for i in range(1, 6))


def _key(kind, key):
    return '|'.join(key) if kind == 'table' else key


class LilithBalanceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data = json.loads(FIXTURE.read_bytes())
        cls.inputs, cls.donors = data['inputs'], data['donors']
        cls.out = M.revise(cls.read_from(cls.inputs))

    @staticmethod
    def read_from(inputs):
        return lambda kind, key: inputs[kind][_key(kind, key)]

    def old(self, kind, key):
        return self.inputs[kind][key]

    def test_fixture_is_the_reviewed_baseline(self):
        for (kind, key), want in M.BEFORE.items():
            self.assertEqual(want, M.digest(self.inputs[kind][_key(kind, key)]), (kind, key))

    def test_only_reviewed_cells_change_outside_the_burst_rows(self):
        expected = {
            (A2, 3): {109: ('1', '23'), 110: ('0', '')},
            (A3, 0): {27: ('20', '2'), 28: ('0', '')},
            (A3, 2): {27: ('20', '2'), 28: ('0', '')},
            (A4, 1): {47: ('33', '55'), 48: ('0', '')},
            (A5, 1): {47: ('201', '200'), 48: ('0', ''), 51: ('100000', '300000'),
                      52: ('100000', '300000')},
        }
        seen = {}
        for key in (A2, A3, A4, A5):
            old, new = self.old('ability', key), self.out['ability'][key]
            self.assertEqual(len(old), len(new), key)
            for i, (a, b) in enumerate(zip(old, new)):
                diff = {c: (x, y) for c, (x, y) in enumerate(zip(a, b)) if x != y}
                self.assertEqual(126, len(b))
                if diff:
                    seen[key, i] = diff
        self.assertEqual(expected, seen)
        old, new = self.old('leader', M.LEADER), self.out['leader'][M.LEADER]
        self.assertEqual(9, len(new))
        seen = {i: {c: (x, y) for c, (x, y) in enumerate(zip(a, b)) if x != y}
                for i, (a, b) in enumerate(zip(old, new)) if a != b}
        self.assertEqual({3: {45: ('33', '55'), 46: ('5', ''), 47: ('Yellow', '')},
                          5: {107: ('1', '23'), 108: ('5', ''), 109: ('Yellow', '')}}, seen)
        self.assertEqual({'ability', 'leader', 'cas', 'dsl', 'new_programs', 'notes', 'text',
                          'table', 'action', 'server_text'}, set(self.out))
        self.assertEqual({A1, A2, A3, A4, A5}, set(self.out['ability']))
        for kind in ('text', 'table', 'action', 'server_text'):
            self.assertEqual({}, self.out[kind])

    def test_ability1_dash_row_is_replaced_in_place_by_invoke_and_count(self):
        old, new = self.old('ability', A1), self.out['ability'][A1]
        self.assertEqual('420', old[2][109])
        self.assertEqual(old[:2], new[:2])
        self.assertEqual(4, len(new))
        self.assertNotIn('420', [r[109] for r in new])
        self.assertEqual(['true'] * 4, [r[1] for r in new])  # whole key stays unisonable
        invoke, count = new[2], new[3]
        for row in (invoke, count):
            self.assertEqual(('resistance_princess_ex_1', 'power_flip', '0', '202'),
                             (row[0], row[2], row[5], row[6]))
            self.assertEqual(['144', '0', '', '1000000', '1000000', '', '', '(None)', '300'],
                             row[27:36])
            self.assertEqual(('0', '0', '(None)', '0'), (row[13], row[20], row[39], row[46]))
            self.assertEqual([''] * 6, row[7:13])
        self.assertEqual(['629', ''], invoke[47:49])
        self.assertEqual([M.BURST_KEY, M.BURST_PROGRAM], invoke[70:72])
        self.assertEqual(['', ''], invoke[51:53])
        self.assertEqual(['248', ''], count[47:49])
        self.assertEqual(['100000', '100000'], count[51:53])
        self.assertEqual(['', ''], count[70:72])

    def test_burst_pair_shares_every_gate_and_cooldown_column(self):
        invoke, count = self.out['ability'][A1][2:4]
        self.assertEqual(invoke[:47], count[:47])
        self.assertEqual({47, 51, 52, 70, 71},
                         {c for c in range(47, 126) if invoke[c] != count[c]})

    def test_burst_rows_keep_the_live_629_and_official_248_row_shapes(self):
        invoke, count = self.out['ability'][A1][2:4]
        zantetsu = self.donors['ability:1599981'][2]
        self.assertEqual('629', zantetsu[47])
        self.assertLessEqual({c for c in range(126) if invoke[c] != zantetsu[c]},
                             {0, 2, 13, 16, 17, 18, 27, 30, 31, 35, 70, 71})
        official = self.donors['ability:3110096'][0]
        self.assertEqual('248', official[47])
        self.assertLessEqual({c for c in range(126) if count[c] != official[c]},
                             {0, 6, 27, 28, 30, 31, 35})
        # 澄波响队长 248 行与 629 行同门槛、同 CT，这里同一约定。
        hibiki = self.donors['leader:169988']
        self.assertEqual(hibiki[5][:45], hibiki[8][:45])

    def test_invoke_string_is_registered_in_the_same_batch(self):
        self.assertEqual({M.BURST_KEY: [[M.BURST_TEXT]]}, self.out['cas'])
        self.assertTrue(M.BURST_KEY.startswith('change_skill_' + M.CODE))
        self.assertEqual('立即发动强化弹射Lv3「剑之斩击」，伤害以强化弹射伤害计算', M.BURST_TEXT)
        invoke = self.out['ability'][A1][2]
        self.assertEqual([], invoke_skill_string_problems(invoke, set(self.out['cas'])))
        self.assertTrue(invoke_skill_string_problems(invoke, set()))
        self.assertEqual({M.BURST_PROGRAM, *M.SKILL_PROGRAMS}, set(self.out['dsl']))
        self.assertEqual([invoke[71]], self.out['new_programs'])

    def test_skill_resistance_down_becomes_thunder_and_nothing_else_moves(self):
        for program in M.SKILL_PROGRAMS:
            old, new = self.inputs['dsl'][program], self.out['dsl'][program]
            olds, news = M._resistance_nodes(old, []), M._resistance_nodes(new, [])
            self.assertEqual([2], [n[2] for n in olds], program)
            self.assertEqual([3], [n[2] for n in news], program)
            restored = deepcopy(new)
            M._resistance_nodes(restored, [])[0][2] = 2
            self.assertEqual(old, restored, program)
            self.assertEqual([], M.dsl_problems(new), program)
            with self.assertRaisesRegex(ValueError, 'resistance-down preimage drift'):
                M.skill_resistance_tree(new)

    def test_no_direct_attack_wording_or_dash_row_remains(self):
        for key, rows in self.out['ability'].items():
            for row in rows:
                if row[5] == '0':
                    self.assertNotEqual('20', row[27], key)
                    self.assertNotIn(row[47], ('33', '201'), key)
                else:
                    self.assertNotIn(row[109], ('1', '420'), key)
        for row in self.out['leader'][M.LEADER]:
            self.assertNotEqual('20', row[25])
            self.assertNotEqual('33', row[45])
            self.assertNotEqual('1', row[107])

    def test_power_flip_kinds_have_no_target_and_keep_strength(self):
        leader = self.out['leader'][M.LEADER]
        self.assertEqual(['55', '', '', '', '200000', '200000'], leader[3][45:51])
        self.assertEqual(('1', '227', '0', '50000', '50000'),
                         tuple(leader[5][i] for i in (3, 95, 96, 98, 99)))
        self.assertEqual(['23', '', '', '', '200000', '200000'], leader[5][107:113])
        a2 = self.out['ability'][A2][3]
        self.assertEqual(('227', '0', '50000', '50000'), tuple(a2[i] for i in (97, 98, 100, 101)))
        self.assertEqual(['23', '', '', '', '200000', '200000'], a2[109:115])
        a4 = self.out['ability'][A4][1]
        self.assertEqual(['55', '', '', '', '50000', '100000'], a4[47:53])
        a5 = self.out['ability'][A5][1]
        self.assertEqual(['200', '', '', '', '300000', '300000'], a5[47:53])

    def test_ability3_uses_power_flip_trigger_without_puller(self):
        rows, old = self.out['ability'][A3], self.old('ability', A3)
        for i, content, cooltime in ((0, '354', '30'), (2, '211', '60')):
            self.assertEqual(['2', ''], rows[i][27:29])
            self.assertEqual(['100000', '100000', '', '', '(None)', cooltime], rows[i][30:36])
            self.assertEqual(content, rows[i][47])
            self.assertEqual(old[i][6:27], rows[i][6:27])  # 202 + 雷≥6 + 固有139997 保持
        self.assertEqual(old[1], rows[1])

    def test_burst_tree_is_the_pf3_sword_segment_settled_as_pf3(self):
        source = self.inputs['dsl'][M.PF_LV3]
        tree = self.out['dsl'][M.BURST_PROGRAM]
        self.assertEqual(['ActionDsl', 1, ['None'], *[False] * 7, 133], tree[:11])
        self.assertEqual(133, M.BURST_BTA)
        body = tree[11][1]
        self.assertEqual(1, len(body))
        area = body[0][1]
        self.assertEqual('CreateHitArea', area[0])
        self.assertEqual(0, area[24])
        self.assertEqual(['CalculatedUsingMaxNumOfHits', 5], area[14])
        attacks = list(wf_dsl.iter_dsl_commands(tree, 'CreateNormalAttack'))
        self.assertEqual(1, len(attacks))
        self.assertEqual(255, attacks[0][2])
        self.assertEqual([{'min': 11.7, 'max': 11.7}], attacks[0][6])
        self.assertAlmostEqual(58.5, 5 * attacks[0][6][0]['max'])
        restored = deepcopy(body[0])
        next(wf_dsl.iter_dsl_commands(restored, 'CreateNormalAttack'))[6] = [
            {'min': 6.3, 'max': 6.3}]
        self.assertEqual(source[11][1][1], restored)  # nothing else in the sword block moved
        tags = set(M._tags(tree))
        for name in ('SetPowerFilpSuppress', 'NotifyPowerflipEnd', 'CollisionOfBallAndEnemy'):
            self.assertNotIn(name, tags)
        effects = {n[2][1] for n in wf_dsl.iter_dsl_commands(tree, 'ShowEffect')}
        self.assertEqual({'battle/effect/powerflip/resistance_princess_ex_pf_spin/'
                          'powerflip_attack_spin_three'}, effects)

    def test_burst_tree_passes_dsl_gates_and_roundtrips(self):
        tree = self.out['dsl'][M.BURST_PROGRAM]
        self.assertEqual([], M.dsl_problems(tree))
        self.assertEqual([], kit_dsl_problems(tree, element=None))
        encode_tree(tree)

    def test_every_returned_row_passes_client_gates(self):
        cas = set(self.out['cas'])
        for kind, table in (('ability', self.out['ability']),
                            ('leader_ability', self.out['leader'])):
            for key, rows in table.items():
                for row in rows:
                    self.assertEqual([], client_legality_problems(kind, row), key)
                    self.assertEqual([], declared_block_field_problems(kind, row), key)
                    self.assertEqual([], invoke_skill_string_problems(row, cas, kind), key)
                    self.assertEqual([], required_client_capabilities(kind, row), key)

    def test_live_drift_is_rejected_and_inputs_are_not_mutated(self):
        original = deepcopy(self.inputs)
        M.revise(self.read_from(self.inputs))
        self.assertEqual(original, self.inputs)
        for kind, key in M.BEFORE:
            drifted = deepcopy(self.inputs)
            value = drifted[kind][_key(kind, key)]
            if kind == 'dsl':
                value[10] = 4
            else:
                value[0][-1] = value[0][-1] + 'x'
            with self.assertRaisesRegex(ValueError, 'unreviewed live baseline'):
                M.revise(self.read_from(drifted))
            missing = deepcopy(self.inputs)
            missing[kind][_key(kind, key)] = None
            with self.assertRaises(ValueError):
                M.revise(self.read_from(missing))

    def test_already_revised_live_is_not_revised_twice(self):
        live = deepcopy(self.inputs)
        live['ability'].update(deepcopy(self.out['ability']))
        live['leader'].update(deepcopy(self.out['leader']))
        with self.assertRaisesRegex(ValueError, 'unreviewed live baseline'):
            M.revise(self.read_from(live))

    def test_module_contract_constants(self):
        self.assertEqual(('139997', 'resistance_princess_ex'), (M.CID, M.CODE))
        self.assertEqual(['resistance_princess_ex'], M.PACKAGES)
        self.assertEqual({'resistance_princess_ex': '0.1.1'}, M.PACKAGE_VERSION)
        self.assertEqual(['damage-type-rules-v1'], M.CAPABILITIES)
        self.assertEqual(2, len(M.REVIEWED_DRIFT))
        for (tier, logical), sha in M.REVIEWED_DRIFT.items():
            self.assertEqual('common', tier)
            self.assertRegex(logical, r'^battle/action/skill/action/rare5/resistance_princess_ex\$'
                                      r'resistance_princess_ex_[12]\.action\.dsl\.amf3\.deflate$')
            self.assertRegex(sha, r'^[0-9a-f]{64}$')
        self.assertFalse(self.out['notes']['runtime_verified'])
        json.dumps(self.out['notes'], ensure_ascii=False)

    @unittest.skipUnless((WORKSPACE / 'package/manifest.json').is_file()
                         and (ROOT / 'mod-tools/profiles.json').is_file(),
                         'local candidate workspace required')
    def test_candidate_accepts_only_the_reviewed_skill_drift_and_splices_dry(self):
        from wf_character_revision import RevisionCandidate
        manifest = WORKSPACE / 'package/manifest.json'
        before = manifest.read_bytes()
        current = json.loads(before)['package_version']
        # 第二批（wf_balance_20260927b_lilith，突袭树 p13 3→0.5）经主会话暂存回写（snapshot
        # revision_20260927b）后，候选 = 第一批输出 + 第二批覆盖，版本随第二批递增；回写前不走这条。
        import wf_balance_20260927b_lilith as B2
        batch2 = json.loads(before).get('snapshot', {}).get('revision_20260927b') is not None
        owner = B2 if batch2 else M
        self.assertGreaterEqual(tuple(map(int, owner.PACKAGE_VERSION[M.PACKAGES[0]].split('.'))),
                                tuple(map(int, current.split('.'))))
        kwargs = dict(character_id=M.CID, code_name=M.CODE, snapshot_key='revision_20260927',
                      package_version=M.PACKAGE_VERSION[M.PACKAGES[0]],
                      baseline_factory=lambda *a, **k: None)
        written_back = json.loads(before).get('snapshot', {}).get('revision_20260927') is not None
        if written_back:
            # 回写后：两档技能树已与 manifest 一致（live 改雷后与候选相同），不再需要已审漂移。
            self.assertEqual(owner.PACKAGE_VERSION[M.PACKAGES[0]], current)
            candidate = RevisionCandidate(ROOT, WORKSPACE, **kwargs)
            common = X.unpack(candidate.read('common', 'master/ability/ability.orderedmap'))
            for key, rows in self.out['ability'].items():
                self.assertEqual(X.csv_write(rows), common[key], key)
            expected = dict(self.out['dsl'])
            if batch2:
                expected[M.BURST_PROGRAM] = B2.revise_burst_tree(self.out['dsl'][M.BURST_PROGRAM])
            for program, tree in expected.items():
                raw = candidate.read('common', wf_dsl.dsl_logical(program))
                self.assertEqual(tree, wf_dsl.parse_dsl(zlib.decompress(raw, -15))['tree'], program)
            self.assertEqual(before, manifest.read_bytes())
            return
        with self.assertRaisesRegex(ValueError, 'candidate drift'):
            RevisionCandidate(ROOT, WORKSPACE, **kwargs)
        candidate = RevisionCandidate(ROOT, WORKSPACE, reviewed_input_drift=M.REVIEWED_DRIFT,
                                      **kwargs)
        candidate.splice('master/ability/ability.orderedmap', self.out['ability'])
        candidate.splice('master/ability/leader_ability.orderedmap', self.out['leader'])
        candidate.splice('master/string/custom_ability_string.orderedmap', self.out['cas'])
        for program, tree in self.out['dsl'].items():
            candidate.emit('common', wf_dsl.dsl_logical(program), encode_tree(tree))
        evidence = candidate.finish({'dry_run': True}, apply=False)
        self.assertFalse(evidence['applied'])
        self.assertEqual(6, len(evidence['changed_files']))
        self.assertEqual(before, manifest.read_bytes())


if __name__ == '__main__':
    unittest.main()
