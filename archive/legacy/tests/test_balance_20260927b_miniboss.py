"""五名小动物 2026-09-27 第二批（Down）：技能单目标总削韧 ≤30、629（触发 CT ≤3 秒）每次 ≤1、Sec 自身眩晕蓄积 150%→100%。"""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
from unittest import mock
import zlib

ROOT = Path(__file__).resolve().parents[2]
pass  # Imports resolve from this checkout/package, not external source copies.
import wf_balance_20260927b_miniboss as M
import wf_dsl
from wf_character_revision import encode_tree
from wf_client_legality import (client_legality_problems, declared_block_field_problems,
                                invoke_skill_string_problems)
from wf_midautumn_kit_hibiki import dsl_problems as kit_dsl_problems
from wf_midautumn_kitlib import panel_problems
from wf_miniboss_kits import build_abilities
from wf_miniboss_text import MAIN, ability_panel_rows

FIXTURE = Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927b_miniboss.json'
P = M.program
#: 作者口径 / 设计稿给出的单目标每次削韧（改前, 改后）；技能 ≤30；629 两名的触发 CT=0 ≤3 秒 ⇒ 每次 ≤1（口径 B3）。
EXPECTED_TOTALS = {
    P('129998', '1'): (51, 25.5), P('129998', '2'): (60, 30),
    P('129998', 'hitodama_lv1'): (7, 0.35), P('129998', 'hitodama_lv2'): (18, 0.9),
    P('129998', 'hitodama_lv3'): (18, 0.9),
    P('139996', '2'): (42, 30),
    P('149994', '2'): (46, 29.9), P('149994', 'claw_lv1'): (4, 0.32),
    P('149994', 'claw_lv2'): (8, 0.64), P('149994', 'claw_lv3'): (12, 0.96),
    P('159999', '2'): (40, 29.8),
    P('119995', '1'): (48, 28.8), P('119995', '2'): (48, 28.8),
}
INVOKE_PROGRAMS = {p for p in EXPECTED_TOTALS if 'hitodama' in p or 'claw' in p}
#: 引擎实值（CreateHitArea p16 eliminatedOnHit 的 Single 区只命中 1 次）：只有水灵幽魂的人魂区受影响；
#: Sec 弹幕是逐颗消除的 NWay（命中数随几何），不估（None）。其余程序与口径值相同。
ENGINE_TOTALS = {
    P('129998', '1'): (33, 16.5), P('129998', '2'): (35, 17.5),
    P('129998', 'hitodama_lv1'): (1, 0.05), P('129998', 'hitodama_lv2'): (2, 0.1),
    P('129998', 'hitodama_lv3'): (3, 0.15),
    P('159999', '2'): (None, None),
}
#: 按口径不动的 lv1 技能（fixture context，不进 BEFORE）。
UNTOUCHED_LV1 = {P('159999', '1'): 31.5, P('139996', '1'): 21, P('149994', '1'): 24}
SEC_PANEL = 'desc_override_security_robot_playable_1'


def unit(cid):
    return next(u for u in M.UNITS if u['CID'] == cid)


def version(text):
    return tuple(int(x) for x in text.split('.'))


def cna_args(tree):
    return list(wf_dsl.iter_dsl_commands(tree, 'CreateNormalAttack'))


class MinibossDownBalanceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data = json.loads(FIXTURE.read_bytes())
        cls.inputs, cls.context = data['inputs'], data['context']
        cls.pristine = deepcopy(cls.inputs)
        cls.outs = {u['CID']: u['revise'](cls.read_from(cls.inputs)) for u in M.UNITS}

    @staticmethod
    def read_from(inputs):
        return lambda kind, key: inputs[kind].get(key)

    def merged(self, kind):
        return {k: v for out in self.outs.values() for k, v in out[kind].items()}

    # ---- 基线与单元形状 -------------------------------------------------------

    def test_fixture_is_the_reviewed_baseline(self):
        self.assertEqual(17, len(M.BEFORE))
        for (kind, key), want in M.BEFORE.items():
            self.assertEqual(want, M.digest(self.inputs[kind][key]), (kind, key))

    def test_one_unit_per_character_owned_by_its_top_level_workspace(self):
        self.assertEqual(['129998', '139996', '149994', '159999', '119995'], [u['CID'] for u in M.UNITS])
        for u in M.UNITS:
            code = u['CODE']
            self.assertEqual(([code], {code: '1.0.2'}, [], {}),
                             (u['PACKAGES'], u['PACKAGE_VERSION'], u['CAPABILITIES'], u['REVIEWED_DRIFT']))
            for kind, key in u['BEFORE']:
                if kind == 'ability':
                    self.assertEqual(u['CID'], key[:6])
                elif kind == 'cas':
                    self.assertTrue(key.startswith(f'desc_override_{code}_'), key)
                else:
                    self.assertTrue(key.startswith(f'{M.R5}{code}${code}_'), key)
        self.assertEqual(M.BEFORE, {k: v for u in M.UNITS for k, v in u['BEFORE'].items()})

    def test_package_version_never_downgrades_the_candidate(self):
        for u in M.UNITS:
            package = u['PACKAGES'][0]
            ws = ROOT / 'work/character_packs' / package
            if not (ws / 'package/manifest.json').exists():
                self.skipTest('local candidate workspaces are not checked out')
            manifest = json.loads((ws / 'package/manifest.json').read_bytes())
            identity = json.loads((ws / 'workspace.json').read_bytes())
            self.assertEqual((int(u['CID']), u['CODE']),
                             (identity['character_id'], identity['code_name']), package)
            # 第三轮面板合并（wf_balance_20260927c_panels）暂存回写后候选再升一版（队长面板合并），上限取那一版。
            import wf_balance_20260927c_panels as P3
            ceiling = P3.staged_version(manifest, package) or u['PACKAGE_VERSION'][package]
            self.assertLessEqual(version(manifest['package_version']), version(ceiling), package)
            if manifest.get('snapshot', {}).get('revision_20260927b') is not None:   # 已回写 ⇒ 恰好等于
                self.assertEqual(ceiling, manifest['package_version'], package)

    def test_outputs_follow_the_contract_shape(self):
        keys = {'ability', 'leader', 'cas', 'text', 'table', 'action', 'dsl', 'server_text',
                'new_programs', 'notes'}
        for cid, out in self.outs.items():
            self.assertEqual(keys, set(out))
            for kind in ('leader', 'text', 'table', 'action', 'server_text'):
                self.assertEqual({}, out[kind], (cid, kind))
            self.assertEqual([], out['new_programs'])
            self.assertEqual({P(cid, suffix) for suffix in M.DSL_PLAN[cid]}, set(out['dsl']))
            self.assertFalse(out['notes']['runtime_verified'])
            json.dumps(out['notes'], ensure_ascii=False)
        self.assertEqual(set(EXPECTED_TOTALS), set(self.merged('dsl')))
        self.assertEqual({'1599991'}, set(self.merged('ability')))
        self.assertEqual({SEC_PANEL}, set(self.merged('cas')))

    # ---- DSL：只动 p13 -------------------------------------------------------

    def test_only_create_normal_attack_p13_changes(self):
        for path, new in self.merged('dsl').items():
            old = self.inputs['dsl'][path]
            olds, news = cna_args(old), cna_args(new)
            self.assertEqual(len(olds), len(news), path)
            restored = deepcopy(new)
            for a, b in zip(cna_args(restored), olds):
                a[13] = deepcopy(b[13])
            # 整树（连 int/float 类型）逐字回到 live：p13 之外没有任何节点被动过。
            self.assertEqual(json.dumps(old), json.dumps(restored), path)
            for a, b in zip(olds, news):
                self.assertEqual(a[:13] + a[14:], b[:13] + b[14:], path)

    def test_p13_values_follow_the_reviewed_mapping(self):
        seen = {}
        for cid, plan in M.DSL_PLAN.items():
            for suffix, (mapping, census, _, _) in plan.items():
                path = P(cid, suffix)
                pairs = [(a[13], b[13]) for a, b in zip(cna_args(self.inputs['dsl'][path]),
                                                        cna_args(self.outs[cid]['dsl'][path]))]
                for old, new in pairs:
                    self.assertEqual(1, len(new))
                    self.assertEqual(new[0]['min'], new[0]['max'])
                    want = mapping.get(old[0]['max'], old[0]['max'])
                    self.assertEqual(want, new[0]['max'], path)
                seen[path] = sorted({(o[0]['max'], n[0]['max']) for o, n in pairs})
        self.assertEqual([(1, 0.75), (1.5, 1.1)], seen[P('159999', '2')])
        self.assertEqual([(1, 1), (5, 3)], seen[P('139996', '2')])   # 弹幕 p13=1 不动
        self.assertEqual([(1, 0.5), (10, 5)], seen[P('129998', '1')])
        self.assertEqual([(1, 0.5), (10, 5)], seen[P('129998', '2')])
        self.assertEqual([(1, 0.65)], seen[P('149994', '2')])
        for lv in (1, 2, 3):   # 设计稿 0.15 / 0.25 同比例再收 1/3（CT ≤3 秒 ⇒ 每次 ≤1）
            self.assertEqual([(1, 0.05)], seen[P('129998', f'hitodama_lv{lv}')])
            self.assertEqual([(1, 0.08)], seen[P('149994', f'claw_lv{lv}')])
        for lv in ('1', '2'):
            self.assertEqual([(1, 0.6)], seen[P('119995', lv)])
        # 整数原值换成整数（冲击波 3、彼岸 5），其余为小数；p14 不随 p13 改。
        ring = [a[13][0]['max'] for a in cna_args(self.outs['139996']['dsl'][P('139996', '2')])]
        self.assertEqual([1, 3, 3], ring)
        self.assertTrue(all(type(v) is int for v in ring))

    def test_single_target_detoughness_before_and_after(self):
        for path, (before, after) in EXPECTED_TOTALS.items():
            new = self.merged('dsl')[path]
            self.assertAlmostEqual(before, M.detoughness(self.inputs['dsl'][path]), places=9, msg=path)
            self.assertAlmostEqual(after, M.detoughness(new), places=9, msg=path)
            cap = 1 if path in INVOKE_PROGRAMS else 30   # 两名 629 的触发 CT 都是 0 帧 ≤3 秒
            self.assertLessEqual(round(M.detoughness(new), 9), cap, path)
        notes = {n['program']: n for out in self.outs.values() for n in out['notes']['dsl']}
        for path, note in notes.items():
            self.assertEqual(1 if path in INVOKE_PROGRAMS else 30, note['cap'], path)
            self.assertEqual(list(EXPECTED_TOTALS[path]), note['single_target_detoughness'], path)

    def test_engine_count_of_single_hit_areas_is_reported(self):
        notes = {n['program']: n for out in self.outs.values() for n in out['notes']['dsl']}
        for path, (before, after) in EXPECTED_TOTALS.items():
            want = list(ENGINE_TOTALS.get(path, (before, after)))
            got = notes[path]['engine_eliminated_on_hit']
            self.assertEqual(want, [None if v is None else round(v, 9) for v in got], path)
            # 口径值是上界：引擎实值不超过它，所以按口径封顶也封住实值。
            if got[1] is not None:
                self.assertLessEqual(got[1], after + 1e-9, path)
        with self.assertRaisesRegex(ValueError, 'geometry-dependent'):
            M.detoughness(self.inputs['dsl'][P('159999', '2')], eliminated_single_hit=True)
        self.assertTrue(any('eliminatedOnHit' in line for line in self.outs['129998']['notes']['open_points']))
        self.assertTrue(any('lv1' in line for line in self.outs['159999']['notes']['open_points']))

    def test_short_cooldown_invoke_programs_are_capped_at_one(self):
        # 设计稿值（p13 0.15 → 人魂 2.7/次）只满足 ≤3；CT=0 的 629 按口径 B3 必须 ≤1，否则 revise 拒绝。
        design = ({1: 0.15}, {1: 2}, 18, 2.7)
        with mock.patch.dict(M.DSL_PLAN['129998'], {'hitodama_lv2': design}):
            with self.assertRaisesRegex(ValueError, 'per-call detoughness cap exceeded'):
                unit('129998')['revise'](self.read_from(self.inputs))
        self.assertEqual((1, 1, 3, 3), tuple(M.invoke_cap(ct) for ct in ('0', '180', '181', '300')))

    def test_untouched_lv1_skills_are_not_returned(self):
        dsl = self.merged('dsl')
        for path, total in UNTOUCHED_LV1.items():
            self.assertNotIn(path, dsl)
            self.assertAlmostEqual(total, M.detoughness(self.context['dsl'][path]), places=9, msg=path)

    def test_detoughness_counter_rejects_unreviewed_shapes(self):
        tree = deepcopy(self.inputs['dsl'][P('119995', '1')])
        branch = deepcopy(tree)
        branch[11][1].append(['Command', ['Wait', ['ConditionalsProbability', []]]])
        with self.assertRaisesRegex(ValueError, 'unreviewed branch'):
            M.detoughness(branch)
        uneven = deepcopy(tree)
        cna_args(uneven)[0][13] = [{'min': 0.5, 'max': 1}]
        with self.assertRaisesRegex(ValueError, 'p13 shape'):
            M.detoughness(uneven)
        with self.assertRaisesRegex(ValueError, 'p13 preimage drift'):
            M.revise_tree(tree, {1: 0.6}, {1: 5})
        loose = deepcopy(tree)
        loose[11][1].append(deepcopy(['Command', cna_args(tree)[0]]))
        with self.assertRaisesRegex(ValueError, 'outside a hit area'):
            M.detoughness(loose)

    def test_dsl_gates_and_amf3_roundtrip(self):
        for cid, out in self.outs.items():
            element = M.ELEMENT[M.BY_ID[cid].group]
            for path, tree in out['dsl'].items():
                self.assertEqual([], M.dsl_problems(tree, element), path)
                back = wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))['tree']
                self.assertEqual(json.dumps(tree), json.dumps(back), path)
                raw = encode_tree(tree)
                self.assertEqual(tree, wf_dsl.parse_dsl(zlib.decompress(raw, -15))['tree'])
                # 更严的 kit 门禁：不新增问题（live 已有的同名 id 复用、召唤 p11 null 原样保留）。
                self.assertEqual(kit_dsl_problems(self.inputs['dsl'][path], element=element),
                                 kit_dsl_problems(tree, element=element), path)

    # ---- 629：触发与 CT 核对 --------------------------------------------------

    def test_invoke_rows_are_power_flip_levels_without_cooldown(self):
        for cid, key in (('129998', '1299983'), ('149994', '1499943')):
            checked = self.outs[cid]['notes']['invoke_629_ct_check']
            self.assertEqual(['PowerFlipLv1', 'PowerFlipLv2', 'PowerFlipLv3'], [c['trigger'] for c in checked])
            self.assertEqual({0}, {c['cooltime_frames'] for c in checked})
            self.assertEqual({1}, {c['per_call_cap'] for c in checked})   # CT ≤3 秒 ⇒ 每次 ≤1
            rows = self.inputs['ability'][key]
            for index, (trigger, suffix) in enumerate(zip(('63', '64', '65'),
                                                         [c['program'] for c in checked])):
                self.assertEqual(('629', trigger, '0', P(cid, suffix)),
                                 (rows[index][47], rows[index][27], rows[index][35], rows[index][71]))
            self.assertNotIn(key, self.outs[cid]['ability'])   # 行本身不改
        for cid in ('139996', '159999', '119995'):
            self.assertEqual([], self.outs[cid]['notes']['invoke_629_ct_check'])

    def test_invoke_row_cooldown_change_forces_a_recheck(self):
        inputs = {('ability', '1299983'): deepcopy(self.inputs['ability']['1299983'])}
        inputs['ability', '1299983'][1][35] = '120'
        with self.assertRaisesRegex(ValueError, '629 invoke row drift'):
            M._check_invoke_rows('129998', inputs)
        drifted = deepcopy(self.inputs)
        drifted['ability']['1499943'][2][35] = '60'
        with self.assertRaisesRegex(ValueError, 'unreviewed live baseline'):
            unit('149994')['revise'](self.read_from(drifted))

    # ---- Sec 能力1 与面板 -----------------------------------------------------

    def test_sec_ability1_changes_only_row1_strength(self):
        old, new = self.inputs['ability']['1599991'], self.outs['159999']['ability']['1599991']
        self.assertEqual(2, len(new))
        diff = {i: {c: (x, y) for c, (x, y) in enumerate(zip(a, b)) if x != y}
                for i, (a, b) in enumerate(zip(old, new)) if a != b}
        self.assertEqual({0: {51: ('150000', '100000'), 52: ('150000', '100000')}}, diff)
        self.assertEqual(['0', '51', '0'], [new[0][5], new[0][47], new[0][48]])
        self.assertEqual(old[1], new[1])   # 光队对眩晕敌人伤害 +60% 不动
        self.assertEqual(126, len(new[0]))

    def test_sec_panel_keeps_the_small_animal_single_line_format(self):
        text = self.outs['159999']['cas'][SEC_PANEL][0][0]
        self.assertEqual('自身眩晕积蓄+100%；光属性角色对眩晕敌人的伤害+60%。', text)
        self.assertEqual(self.inputs['cas'][SEC_PANEL][0][0].replace('+150%', '+100%'), text)
        self.assertEqual([], panel_problems(text))
        for banned in ('\n', '／', '＋', MAIN.strip(), '自身为队长时', '觉醒后', '生命值100%以下'):
            self.assertNotIn(banned, text)

    def test_every_returned_row_passes_client_gates(self):
        cas = set(self.merged('cas'))
        for key, rows in self.merged('ability').items():
            for row in rows:
                self.assertEqual([], client_legality_problems('ability', row), key)
                self.assertEqual([], declared_block_field_problems('ability', row), key)
                self.assertEqual([], invoke_skill_string_problems(row, cas, 'ability'), key)

    # ---- 生成器一致性 ---------------------------------------------------------

    def test_generator_equals_revision(self):
        kit, _ = build_abilities('159999')
        self.assertEqual(self.outs['159999']['ability']['1599991'], kit['1599991'])
        panels = ability_panel_rows('159999', kit)
        self.assertEqual(self.outs['159999']['cas'][SEC_PANEL], panels[SEC_PANEL])
        # 其余四名本批不改能力与面板：生成器里没有第二批的能力/面板改动。
        for cid in ('129998', '139996', '149994', '119995'):
            self.assertEqual({}, self.outs[cid]['ability'])
            self.assertEqual({}, self.outs[cid]['cas'])

    def test_generator_drift_is_rejected(self):
        kit, meta = build_abilities('159999')
        kit['1599991'] = deepcopy(self.inputs['ability']['1599991'])   # 未同步的生成器（仍是 150%）
        with mock.patch.object(M, 'build_abilities', lambda cid: (deepcopy(kit), meta)):
            with self.assertRaisesRegex(ValueError, 'generator differs'):
                unit('159999')['revise'](self.read_from(self.inputs))

    # ---- fail closed / 纯函数 -------------------------------------------------

    def test_live_drift_is_rejected(self):
        for u in M.UNITS:
            for kind, key in u['BEFORE']:
                drifted = deepcopy(self.inputs)
                value = drifted[kind][key]
                if kind == 'dsl':
                    value[10] = 4
                else:
                    value[0][-1] += 'x'
                with self.assertRaisesRegex(ValueError, 'unreviewed live baseline', msg=key):
                    u['revise'](self.read_from(drifted))
                missing = deepcopy(self.inputs)
                del missing[kind][key]
                with self.assertRaisesRegex(ValueError, 'unreviewed live baseline', msg=key):
                    u['revise'](self.read_from(missing))

    def test_already_revised_live_is_not_revised_twice(self):
        for cid, out in self.outs.items():
            live = deepcopy(self.inputs)
            for kind in ('ability', 'cas', 'dsl'):
                live[kind].update(deepcopy(out[kind]))
            with self.assertRaisesRegex(ValueError, 'unreviewed live baseline'):
                unit(cid)['revise'](self.read_from(live))

    def test_revise_does_not_modify_read_results(self):
        self.assertEqual(self.pristine, self.inputs)
        shared = deepcopy(self.inputs)
        for u in M.UNITS:
            u['revise'](lambda kind, key: shared[kind][key])
        self.assertEqual(self.pristine, shared)

    # ---- 候选回写（本机工作区） ------------------------------------------------

    def test_candidates_splice_dry_without_reviewed_drift(self):
        from wf_character_revision import RevisionCandidate
        if not (ROOT / 'mod-tools/profiles.json').is_file():
            self.skipTest('local candidate workspaces are not checked out')
        for u in M.UNITS:
            package = u['PACKAGES'][0]
            ws = ROOT / 'work/character_packs' / package
            if not (ws / 'package/manifest.json').is_file():
                self.skipTest('local candidate workspaces are not checked out')
            out = self.outs[u['CID']]
            manifest = ws / 'package/manifest.json'
            before = manifest.read_bytes()
            kwargs = dict(character_id=u['CID'], code_name=u['CODE'], snapshot_key='revision_20260927b',
                          package_version=u['PACKAGE_VERSION'][package],
                          baseline_factory=lambda *a, **k: None)
            candidate = RevisionCandidate(ROOT, ws, **kwargs)
            written_back = json.loads(before).get('snapshot', {}).get('revision_20260927b') is not None
            for path, tree in out['dsl'].items():
                raw = candidate.read('common', wf_dsl.dsl_logical(path))
                want = tree if written_back else self.inputs['dsl'][path]
                self.assertEqual(want, wf_dsl.parse_dsl(zlib.decompress(raw, -15))['tree'], path)
            if written_back:
                # 已回写：版本 == 本模块版本，能力行/面板串也 == revise() 输出（树已在上面逐棵比对）。
                import wf_share_update_codec as X
                import wf_balance_20260927c_panels as P3   # 第三轮面板合并回写后再升一版
                self.assertEqual(P3.staged_version(json.loads(before), package) or u['PACKAGE_VERSION'][package],
                                 json.loads(before)['package_version'])
                for logical, part in (('master/ability/ability.orderedmap', 'ability'),
                                      ('master/string/custom_ability_string.orderedmap', 'cas')):
                    if out[part]:
                        rows = X.unpack(candidate.read('common', logical))
                        for key, value in out[part].items():
                            self.assertEqual(value, X.csv_read(rows[key]), (package, key))
                self.assertEqual(before, manifest.read_bytes())
                continue
            if out['ability']:
                candidate.splice('master/ability/ability.orderedmap', out['ability'])
            if out['cas']:
                candidate.splice('master/string/custom_ability_string.orderedmap', out['cas'])
            for path, tree in out['dsl'].items():
                candidate.emit('common', wf_dsl.dsl_logical(path), encode_tree(tree))
            evidence = candidate.finish({'dry_run': True}, apply=False)
            self.assertFalse(evidence['applied'])
            self.assertEqual(len(out['dsl']) + bool(out['ability']) + bool(out['cas']),
                             len(evidence['changed_files']), package)
            self.assertEqual(before, manifest.read_bytes())


if __name__ == '__main__':
    unittest.main()
