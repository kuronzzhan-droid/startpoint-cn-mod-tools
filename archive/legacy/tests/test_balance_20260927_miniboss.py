"""十五名小动物 2026-09-27 技能槽修订：条件加槽 5%/CT15秒、充能速度封顶 5%、开局加槽与队长不动。"""
from copy import deepcopy
import json
from pathlib import Path
import re
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
pass  # Imports resolve from this checkout/package, not external source copies.
import wf_balance_20260927_miniboss as M
import wf_balance_20260927b_miniboss as M2
from wf_client_legality import (client_legality_problems, declared_block_field_problems,
                                invoke_skill_string_problems)
from wf_miniboss_kits import build, build_abilities
from wf_miniboss_roster import ROSTER
from wf_miniboss_text import MAIN, ability_panel_rows

FIXTURE = Path(__file__).parent / 'fixtures/balance_20260927_miniboss.json'
FIXTURE_2 = Path(__file__).parent / 'fixtures/balance_20260927b_miniboss.json'   # 第二批覆盖层
OPENING = {  # 开局加槽（c27=0）：键, 行(1 基), 强度 —— 规则 3 不动
    ('1299981', 1, '75000'), ('1399961', 1, '75000'), ('1299964', 1, '60000'),
    ('1499941', 1, '75000'), ('1599994', 2, '75000'), ('1299951', 1, '70000'),
    ('1499931', 1, '70000'), ('1199952', 1, '70000'), ('1499921', 1, '75000'),
    ('1299941', 1, '75000'), ('1199931', 1, '75000'), ('1299931', 2, '70000'),
    ('1699934', 1, '75000'), ('1499912', 1, '75000'), ('1199941', 1, '70000'),
}
PER_LAYER = {('1499944', 2, '2500'), ('1199935', 1, '3000'), ('1299932', 1, '3000')}


def unit(cid):
    return next(u for u in M.UNITS if u['CID'] == cid)


def version(text):
    return tuple(int(x) for x in text.split('.'))


class MinibossGaugeBalanceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = json.loads(FIXTURE.read_bytes())['inputs']
        cls.pristine = deepcopy(cls.inputs)
        cls.outs = {u['CID']: u['revise'](cls.read_from(cls.inputs)) for u in M.UNITS}

    @staticmethod
    def read_from(inputs):
        return lambda kind, key: inputs[kind].get(key)

    def after(self, kind):
        """live 快照 + 本次修订 = 改后的 live。"""
        merged = deepcopy(self.inputs[kind])
        for out in self.outs.values():
            merged.update(deepcopy(out[kind]))
        return merged

    # ---- 基线与单元形状 -------------------------------------------------------

    def test_fixture_is_the_reviewed_baseline(self):
        self.assertEqual(62, len(M.BEFORE))
        for (kind, key), want in M.BEFORE.items():
            self.assertEqual(want, M.digest(self.inputs[kind][key]), (kind, key))

    def test_one_unit_per_roster_character_owned_by_top_level_workspace(self):
        self.assertEqual([c.cid for c in ROSTER], [u['CID'] for u in M.UNITS])
        self.assertIn('139996', [u['CID'] for u in M.UNITS])
        for char, u in zip(ROSTER, M.UNITS):
            package = 'genin' if char.cid == '169993' else char.code
            self.assertEqual((char.code, [package]), (u['CODE'], u['PACKAGES']))
            self.assertEqual({package: '1.0.1'}, u['PACKAGE_VERSION'])
            self.assertEqual(([], {}), (u['CAPABILITIES'], u['REVIEWED_DRIFT']))
            self.assertNotIn('miniboss-rework', package)
            self.assertTrue(u['BEFORE'])
            for kind, key in u['BEFORE']:
                owner = key[:6] if kind == 'ability' else key[len('desc_override_'):].rsplit('_', 1)[0]
                self.assertEqual(char.cid if kind == 'ability' else char.code, owner)
        self.assertEqual(M.BEFORE, {k: v for u in M.UNITS for k, v in u['BEFORE'].items()})

    def test_package_version_never_downgrades_the_candidate(self):
        # 第二批覆盖：wf_balance_20260927b_miniboss 把其中 5 个候选再升一版（1.0.1→1.0.2）并写入
        # snapshot revision_20260927b；这些包的版本上限取第二批的版本，回写后须恰好等于它。
        second = {p: (u['CID'], v) for u in M2.UNITS for p, v in u['PACKAGE_VERSION'].items()}
        for u in M.UNITS:
            package = u['PACKAGES'][0]
            ws = ROOT / 'work/character_packs' / package
            if not (ws / 'package/manifest.json').exists():
                self.skipTest('local candidate workspaces are not checked out')
            manifest = json.loads((ws / 'package/manifest.json').read_bytes())
            identity = json.loads((ws / 'workspace.json').read_bytes())
            self.assertEqual((int(u['CID']), u['CODE']),
                             (identity['character_id'], identity['code_name']), package)
            ceiling = u['PACKAGE_VERSION'][package]
            # 第三轮面板合并（wf_balance_20260927c_panels）暂存回写后，15 个候选各再升一版（队长面板合并）。
            import wf_balance_20260927c_panels as P3
            third = P3.staged_version(manifest, package)
            if package in second:
                self.assertEqual(u['CID'], second[package][0], package)
                self.assertGreaterEqual(version(second[package][1]), version(ceiling), package)
                ceiling = second[package][1]
                if manifest.get('snapshot', {}).get('revision_20260927b') is not None:
                    self.assertEqual(third or ceiling, manifest['package_version'], package)
            else:
                self.assertIsNone(manifest.get('snapshot', {}).get('revision_20260927b'), package)
            ceiling = third or ceiling
            self.assertLessEqual(version(manifest['package_version']), version(ceiling), package)

    # ---- 改动范围 -------------------------------------------------------------

    def test_exactly_the_reviewed_97_cells_change(self):
        cells, rows = {}, 0
        for cid, out in self.outs.items():
            for key, new in out['ability'].items():
                self.assertEqual(cid, key[:6])
                old = self.inputs['ability'][key]
                self.assertEqual(len(old), len(new), key)
                for i, (a, b) in enumerate(zip(old, new)):
                    self.assertEqual(126, len(b))
                    diff = {c: (x, y) for c, (x, y) in enumerate(zip(a, b)) if x != y}
                    if diff:
                        rows += 1
                        cells[key, i + 1] = diff
        self.assertEqual((31, 40, 97), (len({k for k, _ in cells}), rows,
                                        sum(len(d) for d in cells.values())))
        self.assertEqual({(s[0], s[1]): M.expected_cells(s) for s in M.ROWS}, cells)
        for diff in cells.values():
            for col, (_, new) in diff.items():
                self.assertEqual('900' if col == 35 else '5000', new)
        # 抽查：复活加槽保留限 2 次；原本 5% 的只改 CT。
        self.assertEqual({35: ('0', '900'), 51: ('50000', '5000'), 52: ('50000', '5000')},
                         cells['1599996', 3])
        self.assertEqual('2', self.outs['159999']['ability']['1599996'][2][34])
        for key, row in (('1299952', 2), ('1299955', 2), ('1499935', 1), ('1199955', 1),
                         ('1299942', 2)):
            self.assertEqual({35: (cells[key, row][35][0], '900')}, cells[key, row])

    def test_rule_over_all_ninety_fixture_keys_hits_only_the_plan(self):
        hit = {}
        for key, rows in self.inputs['ability'].items():
            new = M.apply_rule(rows)
            if new != rows:
                hit[key] = new
        self.assertEqual({s[0] for s in M.ROWS}, set(hit))
        self.assertEqual(hit, {k: v for out in self.outs.values() for k, v in out['ability'].items()})

    def test_opening_refills_per_layer_charge_and_leaders_stay(self):
        after = self.after('ability')
        for key, row, strength in OPENING:
            old, new = self.inputs['ability'][key][row - 1], after[key][row - 1]
            self.assertEqual(old, new, key)
            self.assertEqual(('0', '211', '0', [strength] * 2), (new[5], new[47], new[27], new[51:53]))
        for key, row, strength in PER_LAYER:
            new = after[key][row - 1]
            self.assertEqual(self.inputs['ability'][key][row - 1], new)
            self.assertEqual(('1', '3', '134', [strength] * 2), (new[5], new[109], new[97], new[113:115]))
        self.assertEqual(['35', '5', '5000', '5000'], after['1199931'][2][47:49] + after['1199931'][2][51:53])
        for out in self.outs.values():
            self.assertEqual({}, out['leader'])

    def test_rule_invariants_hold_for_every_generated_row(self):
        opening = 0
        for char in ROSTER:
            leader = self.inputs['leader'][char.cid]
            for abilities in (build_abilities(char.cid)[0], build(char.cid, source_leader=leader)[0]):
                for key, rows in abilities.items():
                    for i, row in enumerate(rows):
                        old = self.inputs['ability'][key][i]
                        if row[5] == '0' and row[47] == '211':
                            if row[27] == '0':
                                opening += 1
                                self.assertEqual(old, row, key)
                            else:
                                self.assertEqual((['5000'] * 2, '900', old[34]),
                                                 (row[51:53], row[35], row[34]), key)
                        if row[5] == '0' and row[47] == '35':
                            self.assertLessEqual(max(int(row[51]), int(row[52])), 5000, key)
                        if row[5] == '1' and row[109] == '3':
                            self.assertLessEqual(max(int(row[113]), int(row[114])), 5000, key)
        self.assertEqual(2 * len(OPENING), opening)

    # ---- 生成器一致性 ---------------------------------------------------------

    def test_generator_equals_live_after_revision(self):
        # 期望 = 第一批输出 + 第二批覆盖（2026-09-27 第二批 wf_balance_20260927b_miniboss：
        # Sec 能力1 行1 自身眩晕蓄积 150%→100% 与面板1；down 复核 T2）。第二批只覆盖第一批没动过的键。
        ability, cas = self.after('ability'), self.after('cas')
        second = json.loads(FIXTURE_2.read_bytes())['inputs']
        first_keys = {k for out in self.outs.values() for kind in ('ability', 'cas') for k in out[kind]}
        overlaid = set()
        for u in M2.UNITS:
            out = u['revise'](lambda kind, key: second[kind].get(key))
            for kind, merged in (('ability', ability), ('cas', cas)):
                for key, rows in out[kind].items():
                    self.assertNotIn(key, first_keys)
                    self.assertEqual(self.inputs[kind][key], second[kind][key], key)
                    merged[key] = rows
                    overlaid.add(key)
        self.assertEqual({'1599991', 'desc_override_security_robot_playable_1'}, overlaid)
        # 第三轮（wf_balance_20260927c_panels，主会话口径5「／」按等级拆行）：149994 能力3、169993 能力1 两块能力面板
        # 由 c 覆盖（改前 == 本批 live，本批没动过这两个键）；生成器 wf_miniboss_text.TEXTS 已同步为拆行稿。
        import wf_balance_20260927c_panels as P3
        third = {p['cas']: p for p in P3.PANELS if p['kind'] == 'ability' and p['cid'] in {c.cid for c in ROSTER}}
        self.assertEqual({'desc_override_one_eyed_rabbit_playable_3', 'desc_override_genin_playable_1'}, set(third))
        for key, panel in third.items():
            self.assertNotIn(key, first_keys | overlaid)
            self.assertEqual(cas[key], [['\n'.join(panel['before'])]], key)
            cas[key] = [['\n'.join(panel['after'])]]
        for char in ROSTER:
            leader = self.inputs['leader'][char.cid]
            kit, meta = build_abilities(char.cid)
            self.assertEqual({k: ability[k] for k in kit}, kit, char.cid)
            self.assertEqual('abilities-v2-gauge-20260927', meta['revision'])
            full, leaders, _ = build(char.cid, source_leader=leader)
            self.assertEqual(kit, full, char.cid)
            self.assertEqual({char.cid: leader}, leaders, char.cid)  # 队长技不动
            panels = ability_panel_rows(char.cid, kit)
            self.assertEqual({k: cas[k] for k in panels}, panels, char.cid)

    def test_generator_drift_is_rejected(self):
        before = deepcopy(self.outs)
        live_kit = lambda cid: ({cid + str(s): deepcopy(self.inputs['ability'][cid + str(s)])
                                 for s in range(1, 7)}, {})
        with mock.patch.object(M, 'build_abilities', live_kit):
            with self.assertRaisesRegex(ValueError, 'generator differs'):
                unit('139996')['revise'](self.read_from(self.inputs))
        self.assertEqual(before, self.outs)

    # ---- 面板 -----------------------------------------------------------------

    def test_panels_carry_only_the_new_numbers(self):
        cas = {k: v for out in self.outs.values() for k, v in out['cas'].items()}
        self.assertEqual({M.panel_key(k): [[t]] for k, t in M.PANELS.items()}, cas)
        self.assertEqual(31, len(cas))
        for key, rows in cas.items():
            text = rows[0][0]
            self.assertNotEqual(self.inputs['cas'][key], rows)
            self.assertNotIn(MAIN.strip(), text)
            for banned in ('／', '自身为队长时', '觉醒后', '生命值100%以下'):
                self.assertNotIn(banned, text)
            for m in re.finditer(r'技能槽\+(\d+)%(（[^）]*）)?', text):
                if text[:m.start()].endswith('战斗开始时，自身'):
                    continue
                self.assertEqual('5', m.group(1), key)
                self.assertRegex(m.group(2) or '', r'CT：15秒', key)
            for m in re.finditer(r'充能速度\+([\d.]+)%', text):
                self.assertLessEqual(float(m.group(1)), 5, key)
        self.assertEqual('自身发动技能时，获得交战模式，持续15秒；交战模式中，强化弹射伤害+50%；'
                         '自身复活时，自身技能槽+5%（CT：15秒，最多2次）。',
                         cas['desc_override_security_robot_playable_6'][0][0])
        self.assertIn('恢复光属性角色3%生命值（CT：3秒），并使自身技能槽+5%（CT：15秒）',
                      cas['desc_override_security_robot_playable_5'][0][0])

    def test_every_changed_ability_key_has_its_panel(self):
        for cid, out in self.outs.items():
            code = unit(cid)['CODE']
            self.assertEqual({f'desc_override_{code}_{k[6]}' for k in out['ability']}, set(out['cas']))
            for key in out['cas']:
                self.assertTrue(key.startswith('desc_override_' + code))

    # ---- fail closed / 纯函数 -------------------------------------------------

    def test_live_drift_is_rejected(self):
        for kind, key in (('ability', '1399964'), ('cas', 'desc_override_cube_boss_playable_5')):
            drifted = deepcopy(self.inputs)
            if kind == 'ability':
                drifted[kind][key][0][51] = '10000'
            else:
                drifted[kind][key][0][0] += '。'
            with self.assertRaisesRegex(ValueError, 'unreviewed live baseline'):
                unit('139996')['revise'](self.read_from(drifted))
        missing = deepcopy(self.inputs)
        del missing['ability']['1599996']
        with self.assertRaisesRegex(ValueError, 'unreviewed live baseline'):
            unit('159999')['revise'](self.read_from(missing))
        # 已修订过的 live（重复执行）同样拒绝。
        applied = deepcopy(self.inputs)
        applied['ability'].update(self.outs['129998']['ability'])
        with self.assertRaisesRegex(ValueError, 'unreviewed live baseline'):
            unit('129998')['revise'](self.read_from(applied))

    def test_revise_does_not_modify_read_results(self):
        self.assertEqual(self.pristine, self.inputs)
        shared = deepcopy(self.inputs)
        for u in M.UNITS:
            u['revise'](lambda kind, key: shared[kind][key])
        self.assertEqual(self.pristine, shared)

    def test_outputs_follow_the_contract_shape(self):
        keys = {'ability', 'leader', 'cas', 'text', 'table', 'action', 'dsl', 'server_text',
                'new_programs', 'notes'}
        for cid, out in self.outs.items():
            self.assertEqual(keys, set(out))
            for kind in ('leader', 'text', 'table', 'action', 'dsl', 'server_text'):
                self.assertEqual({}, out[kind])
            self.assertEqual([], out['new_programs'])
            self.assertFalse(out['notes']['runtime_verified'])
            self.assertEqual(sum(len(c) for k, c in M._plan_for(cid).items()),
                             len(out['notes']['changed']))
            json.dumps(out['notes'], ensure_ascii=False)

    def test_legality_gates_are_clean(self):
        cas_keys = {k for out in self.outs.values() for k in out['cas']}
        for out in self.outs.values():
            for key, rows in out['ability'].items():
                for row in rows:
                    self.assertEqual([], client_legality_problems('ability', row), key)
                    self.assertEqual([], declared_block_field_problems('ability', row), key)
                    self.assertEqual([], invoke_skill_string_problems(row, cas_keys, 'ability'), key)


if __name__ == '__main__':
    unittest.main()
