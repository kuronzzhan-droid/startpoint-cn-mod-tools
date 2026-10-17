"""稻穗 139995 2026-09-27 修订：能力3 行4 加 CT 10 秒；行2/3/7 的 300% 由 Fever 中改为常驻。"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
pass  # Imports resolve from this checkout/package, not external source copies.
import wf_balance_20260927_inaho as M
import wf_describe
import wf_mod_tool as core
from wf_client_description_legality import description_compatibility_problems
from wf_client_legality import (client_legality_problems, declared_block_field_problems,
                                invoke_skill_string_problems, required_client_capabilities)

FIXTURE = Path(__file__).parent / 'fixtures/balance_20260927_inaho.json'
WORKSPACE = ROOT / 'work/character_packs' / M.PACKAGES[0]
A3 = M.ABILITY3
ABILITY_TABLE = 'master/ability/ability.orderedmap'
#: 独立核算（调研阶段在内存里拟改后得出）：改后 1399953 的 write_csv_lines 文本 sha256。
AFTER_TEXT_SHA256 = '84cc728ab0bab8b51c64d70f2362976f3348a5dbb44a645b89c0dbd94c7a00c1'
PERMANENT_DIFF = {
    1: {5: ('1', '0'), 27: ('', '0'), 39: ('', '(None)'), 46: ('', '0'), 47: ('', '55'),
        51: ('', '300000'), 52: ('', '300000'), 85: ('(None)', ''), 97: ('4', ''),
        108: ('false', ''), 109: ('23', ''), 113: ('300000', ''), 114: ('300000', '')},
    2: {5: ('1', '0'), 27: ('', '0'), 39: ('', '(None)'), 46: ('', '0'), 47: ('', '388'),
        48: ('', '0'), 51: ('', '300000'), 52: ('', '300000'), 85: ('(None)', ''),
        97: ('4', ''), 108: ('false', ''), 109: ('154', ''), 110: ('0', ''),
        113: ('300000', ''), 114: ('300000', '')},
    6: {5: ('1', '0'), 27: ('', '0'), 39: ('', '(None)'), 46: ('', '0'), 47: ('', '32'),
        48: ('', '0'), 51: ('', '300000'), 52: ('', '300000'), 85: ('(None)', ''),
        97: ('4', ''), 108: ('false', ''), 109: ('0', ''), 110: ('0', ''),
        113: ('300000', ''), 114: ('300000', '')},
}
#: 瞬发内容 -> 官方同型 Initial 先例（OfficialBaseline 官方 ability 表）。
PRECEDENT = {'55': 'official:1412012#1', '388': 'official:2510411#1', '32': 'official:1511652#0'}


def _text_sha(rows):
    return hashlib.sha256(core.write_csv_lines(rows).encode()).hexdigest()


def _diff(a, b):
    return {c: (x, y) for c, (x, y) in enumerate(zip(a, b)) if x != y}


class InahoBalance20260927Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data = json.loads(FIXTURE.read_bytes())
        cls.inputs, cls.donors = data['inputs'], data['donors']
        cls.old = cls.inputs['ability'][A3]
        cls.out = M.revise(cls.read_from(cls.inputs))
        cls.new = cls.out['ability'][A3]

    @staticmethod
    def read_from(inputs):
        return lambda kind, key: inputs[kind][key]

    def test_fixture_is_the_reviewed_baseline(self):
        for (kind, key), want in M.BEFORE.items():
            self.assertEqual(want, M.digest(self.inputs[kind][key]), (kind, key))
        self.assertEqual({('ability', A3)}, set(M.BEFORE))

    def test_only_reviewed_cells_change(self):
        self.assertEqual(7, len(self.new))
        seen = {i: _diff(a, b) for i, (a, b) in enumerate(zip(self.old, self.new)) if a != b}
        self.assertEqual({3: {35: ('0', '600')}, **PERMANENT_DIFF}, seen)
        self.assertEqual(AFTER_TEXT_SHA256, _text_sha(self.new))
        self.assertEqual({'ability', 'leader', 'cas', 'text', 'table', 'action', 'dsl',
                          'server_text', 'new_programs', 'notes'}, set(self.out))
        self.assertEqual({A3}, set(self.out['ability']))
        for kind in ('leader', 'cas', 'text', 'table', 'action', 'dsl', 'server_text'):
            self.assertEqual({}, self.out[kind], kind)
        self.assertEqual([], self.out['new_programs'])

    def test_row4_fever_gauge_gains_a_ten_second_cooltime(self):
        row = self.new[3]
        self.assertEqual(('0', '8', '100000', '100000', '(None)', '600'),
                         tuple(row[i] for i in (5, 27, 30, 31, 34, 35)))
        self.assertEqual(['211', '5', 'Yellow', '', '5000', '10000'], row[47:53])
        official = self.donors['official:1310203#0']
        # 官方同型：c1=false、进入 Fever(8)、非零 CT、211 技能槽。
        self.assertEqual(('false', '8', '(None)', '211'),
                         tuple(official[i] for i in (1, 27, 34, 47)))
        self.assertNotEqual('0', official[35])
        self.assertEqual({0, 2, 35, 48, 49, 51, 52}, set(_diff(official, row)))

    def test_fever_300_rows_become_permanent_initial_rows_in_place(self):
        for index, kind, target in ((1, '55', ''), (2, '388', '0'), (6, '32', '0')):
            row = self.new[index]
            with self.subTest(row=index + 1):
                self.assertEqual(126, len(row))
                self.assertEqual(('0', '0', '(None)', '0'), (row[5], row[27], row[39], row[46]))
                self.assertEqual([kind, target, '', '', '300000', '300000'], row[47:53])
                self.assertEqual([''] * 41, row[85:126])  # 持续块/开幕块全空
                self.assertEqual(self.old[index][:5], row[:5])
                self.assertEqual(self.old[index][6:27], row[6:27])  # 前置块 c6/c13/c20=0 原样
                set_cols = {c for c, v in enumerate(row) if v}
                self.assertEqual({0, 1, 2, 3, 5, 6, 13, 20, 27, 39, 46, 47, 51, 52}
                                 | ({48} if target else set()), set_cols)
                official = self.donors[PRECEDENT[kind]]
                self.assertEqual(kind, official[47])
                self.assertLessEqual(set(_diff(official, row)), {0, 1, 2, 51, 52})

    def test_permanent_rows_share_the_key_own_initial_row_shape(self):
        # 行1 是本键已有的瞬发 Initial 行（带雷共鸣前置）；三行常驻只在前置与内容上不同。
        base = self.new[0]
        for index in (1, 2, 6):
            self.assertLessEqual(set(_diff(base, self.new[index])), {6, 9, 10, 11, 47, 48, 51, 52})

    def test_row_order_and_untouched_rows(self):
        for index in M.UNCHANGED_ROWS:
            self.assertEqual(self.old[index], self.new[index], index)
        self.assertEqual(['0', '0', '0', '0', '1', '0', '0'], [r[5] for r in self.new])
        self.assertEqual(['56', '55', '388', '211', '', '226', '32'], [r[47] for r in self.new])
        # 行5（Fever 中全队雷技能槽最大值 +10%）仍是唯一的持续·Fever 行。
        during = [i for i, r in enumerate(self.new) if r[5] == '1']
        self.assertEqual([4], during)
        self.assertEqual(('4', '124', '5', 'Yellow', '10000'),
                         tuple(self.new[4][i] for i in (97, 109, 110, 111, 113)))
        self.assertTrue(all(r[1] == 'false' for r in self.new))  # 整键仍仅主位

    def test_auto_panel_text_drops_the_fever_prefix_and_shows_the_cooltime(self):
        lines = wf_describe.describe_rows(self.new, 'ability')
        self.assertEqual('自身 强化弹射伤害 300%', lines[1])
        self.assertEqual('自身 能力伤害 300%', lines[2])
        self.assertEqual('Fever≥1(CT10秒) → 赋予全队(雷) 技能槽 5%→10%', lines[3])
        self.assertEqual('自身 攻击力 300%', lines[6])
        old = wf_describe.describe_rows(self.old, 'ability')
        for index in M.UNCHANGED_ROWS:
            self.assertEqual(old[index], lines[index])
        for line in lines:
            self.assertNotIn('生命值', line)

    def test_every_row_passes_client_gates(self):
        for index, row in enumerate(self.new):
            with self.subTest(row=index + 1):
                self.assertEqual([], client_legality_problems('ability', row))
                self.assertEqual([], declared_block_field_problems('ability', row))
                self.assertEqual([], invoke_skill_string_problems(row, set(), 'ability'))
                self.assertEqual([], description_compatibility_problems('ability', row))
                self.assertEqual([], required_client_capabilities('ability', row))
                self.assertEqual([], M.row_problems(row))

    def test_live_drift_is_rejected_and_inputs_are_not_mutated(self):
        original = deepcopy(self.inputs)
        M.revise(self.read_from(self.inputs))
        self.assertEqual(original, self.inputs)
        for kind, key in M.BEFORE:
            drifted = deepcopy(self.inputs)
            drifted[kind][key][0][-1] += 'x'
            with self.assertRaisesRegex(ValueError, 'unreviewed live baseline'):
                M.revise(self.read_from(drifted))
            missing = deepcopy(self.inputs)
            missing[kind][key] = None
            with self.assertRaisesRegex(ValueError, 'unreviewed live baseline'):
                M.revise(self.read_from(missing))

    def test_already_revised_live_is_not_revised_twice(self):
        live = deepcopy(self.inputs)
        live['ability'].update(deepcopy(self.out['ability']))
        with self.assertRaisesRegex(ValueError, 'unreviewed live baseline'):
            M.revise(self.read_from(live))

    def test_row_preimage_guards_fail_closed(self):
        cases = {
            'row4 cooltime': (3, 35, '1800'),
            'row4 content': (3, 47, '213'),
            'row2 during kind': (1, 109, '1'),
            'row3 not fever': (2, 97, '1'),
            'row7 strength': (6, 113, '150000'),
            'row2 instant residue': (1, 30, '100000'),
            'main-only flag': (0, 1, 'true'),
        }
        for name, (index, col, value) in cases.items():
            rows = deepcopy(self.old)
            rows[index][col] = value
            with self.subTest(name), self.assertRaises(ValueError):
                M.ability3_rows(rows)
        with self.assertRaises(ValueError):
            M.ability3_rows(self.old[:6])
        with self.assertRaises(ValueError):
            M.ability3_rows(self.new)  # 已改过的行不再匹配前像
        before = deepcopy(self.old)
        M.ability3_rows(self.old)
        self.assertEqual(before, self.old)

    def test_generator_is_this_module_and_old_generators_stay_locked(self):
        self.assertEqual(M.ability3_rows(self.old), self.new)
        import wf_inaho_fever_revision
        import wf_inaho_native_pf_r2
        import wf_inaho_pf3_balance
        locked = {wf_inaho_pf3_balance.BASE_HASHES['1399953'],
                  *wf_inaho_fever_revision.HASHES['1399953'],
                  wf_inaho_native_pf_r2.ABILITY_BASE, wf_inaho_native_pf_r2.ABILITY_AFTER}
        for rows in (self.old, self.new):
            text = core.write_csv_lines(rows)
            for variant in (text, text.rstrip('\n'), text.replace('\n', '\r\n')):
                self.assertNotIn(hashlib.sha256(variant.encode()).hexdigest(), locked)

    def test_module_contract_constants(self):
        self.assertEqual(('139995', 'fox_oracle_autumn'), (M.CID, M.CODE))
        self.assertEqual(['fox_oracle_autumn'], M.PACKAGES)
        self.assertEqual({'fox_oracle_autumn': '0.20260927'}, M.PACKAGE_VERSION)
        self.assertEqual(['kyubi-fever-ratio-v1'], M.CAPABILITIES)
        self.assertEqual({}, M.REVIEWED_DRIFT)
        self.assertEqual('1399953', A3)
        blocks = wf_describe.layout('ability')['blocks']
        self.assertEqual(126, wf_describe.layout('ability')['ncols'])
        self.assertEqual((M.MODE, M.TRIGGER, M.PRECONTENT, M.DELAY, M.CONTENT, M.DURING),
                         (blocks['precondition1'] - 1, blocks['instant_trigger'],
                          blocks['instant_precontent'], blocks['instant_delay'],
                          blocks['instant_content'], blocks['during_accumulation_trigger']))
        self.assertEqual(M.TRIGGER + 8, M.COOLTIME)
        self.assertFalse(self.out['notes']['runtime_verified'])
        json.dumps(self.out['notes'], ensure_ascii=False)

    @unittest.skipUnless((WORKSPACE / 'package/manifest.json').is_file()
                         and (ROOT / 'mod-tools/profiles.json').is_file(),
                         'local candidate workspace required')
    def test_candidate_splices_only_ability3_dry(self):
        from wf_character_revision import RevisionCandidate
        import wf_share_update_codec as X
        manifest = WORKSPACE / 'package/manifest.json'
        before = manifest.read_bytes()
        current = json.loads(before)['package_version']
        mine = tuple(map(int, M.PACKAGE_VERSION[M.PACKAGES[0]].split('.')))
        if 'revision_20260927b' in json.loads(before).get('snapshot', {}):
            # 第一批输出 + 第二批覆盖：wf_balance_20260927b_inaho 回写后版本在第一批之上递增
            # （0.20260927 → 0.20260927.1）；第二批不动 1399953，下方 A3 断言照旧。
            import wf_balance_20260927b_inaho as M2
            self.assertLess(mine, tuple(map(int, current.split('.'))))
            # 作者 09-27 追加（wf_balance_20260927b_inaho2）同快照键继续回写，版本在第二批之上递增（.1 → .2）。
            self.assertLessEqual(tuple(map(int, M2.PACKAGE_VERSION[M.PACKAGES[0]].split('.'))),
                                 tuple(map(int, current.split('.'))))
        else:
            self.assertGreaterEqual(mine, tuple(map(int, current.split('.'))))
        candidate = RevisionCandidate(
            ROOT, WORKSPACE, character_id=M.CID, code_name=M.CODE,
            snapshot_key='revision_20260927', package_version=M.PACKAGE_VERSION[M.PACKAGES[0]],
            reviewed_input_drift=M.REVIEWED_DRIFT, baseline_factory=lambda *a, **k: None)
        old_table = X.unpack(candidate.read('common', ABILITY_TABLE))
        # 暂存前候选 1399953 与 live 前像一致；暂存后（snapshot revision_20260927）必须已等于本模块输出。
        cand_a3 = X.csv_read(old_table[A3])
        if len(cand_a3) == 9:
            # 作者 09-27 追加（wf_balance_20260927b_inaho2）回写后：本模块 7 行在前逐字不变，
            # 末尾追加原能力1 #2（PF Lv3 → 雷队技能槽，加雷共鸣）与 #3（进 Fever 余辉 +1）。
            self.assertEqual(['211', '461'], [r[47] for r in cand_a3[7:]])
            self.assertEqual({(f'{M.CODE}_3', 'false')}, {(r[0], r[1]) for r in cand_a3[7:]})
            cand_a3 = cand_a3[:7]
        if json.loads(before).get('snapshot', {}).get('revision_20260927') is not None:
            self.assertEqual(self.new, cand_a3)
        else:
            self.assertIn(cand_a3, (self.old, self.new))
        candidate.splice(ABILITY_TABLE, self.out['ability'])
        new_table = X.unpack(candidate.read('common', ABILITY_TABLE))
        self.assertEqual(self.new, X.csv_read(new_table[A3]))
        self.assertEqual({k: v for k, v in old_table.items() if k != A3},
                         {k: v for k, v in new_table.items() if k != A3})
        evidence = candidate.finish({'dry_run': True}, apply=False)
        self.assertFalse(evidence['applied'])
        self.assertEqual([ABILITY_TABLE], [f['logical_path'] for f in evidence['changed_files']])
        self.assertEqual(before, manifest.read_bytes())


if __name__ == '__main__':
    unittest.main()
