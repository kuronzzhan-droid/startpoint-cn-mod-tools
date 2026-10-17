"""墨斯伊克 149997 2026-09-27 第三轮：PF 风刃倍率跟灰服 1.4.85 降到 7.5/6.0/4.5，削韧保持第二批 10/20/25；
面板覆盖（同条件合并）：新建队长 / 能力1 / 能力4 三块 desc_override，能力 2/3/5/6 保持自动生成。"""
from collections import Counter
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import unittest
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[2]
pass  # Imports resolve from this checkout/package, not external source copies.
sys.setrecursionlimit(10000)
import wf_balance_20260927c_mosiyike as M
import wf_balance_20260927b_mosiyike as B
import wf_balance_20260927b_gray3 as G3
import wf_dsl
import wf_mod_tool as core
from wf_character_revision import encode_tree

FIXTURE = Path(__file__).parent / 'fixtures/balance_20260927c_mosiyike.json'
FIXTURE_B = Path(__file__).parent / 'fixtures/balance_20260927b_mosiyike.json'
WORKSPACE = ROOT / 'work/character_packs' / M.PACKAGES[0]
PF1, PF2, PF3 = (M.PF_PROGRAMS[level] for level in M.PF_LEVELS)
NEW_TOTALS = {1: 15.0, 2: 30.0, 3: 45.0}
CAS_TABLE = 'master/string/custom_ability_string.orderedmap'

#: 三块新覆盖面板逐字（覆盖文案替换整块面板：每条数据行都有归属）。
PANEL_TEXTS = {
    'desc_override_mosiyike': (
        '追加「苍穹风刃」特殊强化弹射\n'
        '队伍中编入3名以上龙族角色时，龙族角色攻击力＋240%、技能充能速度＋30%\n'
        '强化弹射Lv3所需连击数－8\n'
        '战斗开始时，连击＋5'),
    'desc_override_mosiyike_1': (
        '玛纳获得数量＋100%\n'
        '龙族角色生命值＋15%，队长攻击力＋100%\n'
        '队伍中编入3名以上龙族角色时，龙族角色攻击力＋240%'),
    'desc_override_mosiyike_4': (
        '发动强化弹射Lv1时，自身「翔风」＋1层\n'
        '发动强化弹射Lv2时，自身「翔风」＋2层\n'
        '发动强化弹射Lv3时，自身「翔风」＋3层\n'
        '自身发动技能时，自身「翔风」＋2层\n'
        '每1层「翔风」，龙族角色攻击力＋20%、技能充能速度＋3%，强化弹射伤害＋15%（最多5层）\n'
        '自身「翔风」达到5层以上期间，发动强化弹射时，队伍全体的最大速度固定效果持续时间＋30%'),
}
#: 合并前（每条数据行单独一行、同一措辞）：check_merge 的原文侧。
UNMERGED = {
    'desc_override_mosiyike': (
        '追加「苍穹风刃」特殊强化弹射\n'
        '队伍中编入3名以上龙族角色时，龙族角色攻击力＋240%\n'
        '队伍中编入3名以上龙族角色时，龙族角色技能充能速度＋30%\n'
        '强化弹射Lv3所需连击数－8\n'
        '战斗开始时，连击＋5'),
    'desc_override_mosiyike_1': (
        '玛纳获得数量＋100%\n'
        '龙族角色生命值＋15%\n'
        '队长攻击力＋100%\n'
        '队伍中编入3名以上龙族角色时，龙族角色攻击力＋240%'),
    'desc_override_mosiyike_4': (
        '发动强化弹射Lv1时，自身「翔风」＋1层\n'
        '发动强化弹射Lv2时，自身「翔风」＋2层\n'
        '发动强化弹射Lv3时，自身「翔风」＋3层\n'
        '自身发动技能时，自身「翔风」＋2层\n'
        '每1层「翔风」，龙族角色攻击力＋20%（最多5层）\n'
        '每1层「翔风」，龙族角色技能充能速度＋3%（最多5层）\n'
        '每1层「翔风」，强化弹射伤害＋15%（最多5层）\n'
        '自身「翔风」达到5层以上期间，发动强化弹射时，队伍全体的最大速度固定效果持续时间＋30%'),
}


def pct(value):
    """强度 ×1000 = 1%（只接受整百分数）。"""
    assert int(value) % 1000 == 0, value
    return int(value) // 1000


def cnt(value):
    """次数 / 层数 / 连击 ×100000 = 1。"""
    assert int(value) % 100000 == 0, value
    return int(value) // 100000


def numbers(line):
    return Counter(int(n) for n in re.findall(r'\d+', line))


def load_check_merge():
    import wf_panel_merge_check          # 仓库内面板合并校验器（硬依赖）
    return wf_panel_merge_check


def _key(kind, key):
    return '|'.join(key) if kind == 'table' else key


def leaf_diff(a, b, path=()):
    """两棵树逐叶比对（含 int/float 类型），返回不同处的路径。"""
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        return [p for i, (x, y) in enumerate(zip(a, b)) for p in leaf_diff(x, y, (*path, i))]
    if isinstance(a, dict) and isinstance(b, dict) and a.keys() == b.keys():
        return [p for k in a for p in leaf_diff(a[k], b[k], (*path, k))]
    return [] if (type(a) is type(b) and a == b) else [path]


def at(tree, path):
    for step in path:
        tree = tree[step]
    return tree


def attack_paths(node, path=()):
    """树里每个 CreateNormalAttack 参数表的路径（按树序）。"""
    if isinstance(node, list):
        if len(node) > 1 and node[0] == 'Command' and isinstance(node[1], list) \
                and node[1][0] == 'CreateNormalAttack':
            return [(*path, 1)]
        return [p for i, child in enumerate(node) for p in attack_paths(child, (*path, i))]
    return []


def slv_leaves(tree, index):
    return sorted((*p, index, 0, side) for p in attack_paths(tree) for side in ('min', 'max'))


def slv(value):
    return [{'min': value, 'max': value}]


class MosiyikeBatch3Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data = json.loads(FIXTURE.read_bytes())
        cls.inputs, cls.raw_sha, cls.gray, cls.context = (data['inputs'], data['dsl_raw_sha256'],
                                                          data['gray'], data['context'])
        cls.out = M.revise(cls.read_from(cls.inputs))

    @staticmethod
    def read_from(inputs):
        return lambda kind, key: inputs[kind][_key(kind, key)]

    def tree(self, program):
        return self.inputs['dsl'][program]

    def gray_tree(self, program):
        return self.gray[program]['tree']

    # ---------------------------------------------------------------- 基线与输出形状

    def test_fixture_is_the_reviewed_baseline(self):
        self.assertEqual(16, len(M.BEFORE))       # PF 4 项 + 面板 12 项（队长、六个能力、PF 文案、两个固有状态、技能两档）
        for (kind, key), want in M.BEFORE.items():
            self.assertEqual(want, M.digest(self.inputs[kind][_key(kind, key)]), (kind, key))
        self.assertEqual([f'desc_override_mosiyike{s}' for s in ('', '_1', '_2', '_3', '_4', '_5', '_6')],
                         [key for _kind, key in M.ABSENT])
        self.assertEqual([key for _kind, key in M.ABSENT], self.context['cas_absent'])   # live 1.4.1054 全都没有
        for _kind, key in M.ABSENT:
            self.assertNotIn(key, self.inputs['cas'])
        leader = self.context['leader'][M.CID]
        self.assertEqual([('mosiyike_pf', '1,2,3')], [(r[80], r[81]) for r in leader if r[45] == '722'])
        self.assertEqual([[PF1, PF2, PF3]],
                         self.inputs['table']['master/skill/power_flip_action.orderedmap|mosiyike_pf'])
        # 输入 = 第二批 live 产物（Lv1 = 第二批输入，Lv2/Lv3 = 第二批输出）
        self.assertEqual(B.BEFORE['dsl', PF1], M.BEFORE['dsl', PF1])
        b_in = json.loads(FIXTURE_B.read_bytes())['inputs']
        b_out = B.revise(lambda kind, key: b_in[kind][_key(kind, key)])
        for program in (PF2, PF3):
            self.assertEqual(json.dumps(b_out['dsl'][program]), json.dumps(self.tree(program)), program)

    def test_all_three_levels_are_returned(self):
        self.assertEqual({'ability', 'leader', 'cas', 'text', 'table', 'action', 'dsl',
                          'server_text', 'new_programs', 'notes'}, set(self.out))
        for kind in ('leader', 'text', 'table', 'action', 'server_text'):
            self.assertEqual({}, self.out[kind], kind)
        # 能力4 只改 #7 前置 188 → 144（作者 09-27「改成按层数生效」），其余行逐字不变
        fix = M.ABILITY_KEYS[3]
        self.assertEqual([fix], list(self.out['ability']))
        old, new = self.inputs['ability'][fix], self.out['ability'][fix]
        self.assertEqual(len(old), len(new))
        diff = {(i, c) for i, (a, b) in enumerate(zip(old, new)) for c, (x, y) in enumerate(zip(a, b)) if x != y}
        self.assertEqual({(7, 6)}, diff)
        self.assertEqual(('188', '144'), (old[7][6], new[7][6]))
        import wf_client_legality as legality
        self.assertEqual([], legality.client_legality_problems('ability', new[7]))
        self.assertEqual([], legality.declared_block_field_problems('ability', new[7]))
        self.assertEqual({key: [[text]] for key, text in PANEL_TEXTS.items()}, self.out['cas'])
        self.assertEqual({PF1, PF2, PF3}, set(self.out['dsl']))
        self.assertEqual([], self.out['new_programs'])
        self.assertEqual(M.AFTER, {p: M.digest(t) for p, t in self.out['dsl'].items()})

    # ---------------------------------------------------------------- 倍率 / 削韧

    def test_wave_multiplier_follows_gray(self):
        for level, (waves, old, new) in M.MULT_PLAN.items():
            program = M.PF_PROGRAMS[level]
            paths = attack_paths(self.tree(program))
            self.assertEqual(waves, len(paths), level)
            for path in paths:
                area = at(self.out['dsl'][program], path[:-4])
                self.assertEqual(('CreateHitArea', -18, ['EF'], ['CalculatedUsingMaxNumOfHits', 1]),
                                 (area[0], area[2], area[3], area[14]))
                self.assertEqual(slv(old), at(self.tree(program), path)[6])
                self.assertEqual(slv(new), at(self.out['dsl'][program], path)[6])
                self.assertIs(float, type(at(self.out['dsl'][program], path)[6][0]['max']))
        self.assertEqual({(2, 12.5, 7.5), (5, 8.28, 6.0), (10, 6.44, 4.5)}, set(M.MULT_PLAN.values()))
        self.assertEqual({'lv1': [25.0, 15.0], 'lv2': [41.4, 30.0], 'lv3': [64.4, 45.0]},
                         self.out['notes']['pf_total_multiplier'])

    def test_detoughness_stays_at_batch2(self):
        for level, p13 in ((1, 5), (2, 4), (3, 2.5)):
            program = M.PF_PROGRAMS[level]
            self.assertEqual(p13, M.P13[level])
            for path in attack_paths(self.out['dsl'][program]):
                self.assertEqual(slv(p13), at(self.out['dsl'][program], path)[13])
                self.assertIs(type(p13), type(at(self.out['dsl'][program], path)[13][0]['max']))
        self.assertEqual({'lv1': 10, 'lv2': 20, 'lv3': 25}, self.out['notes']['pf_detoughness_unchanged'])
        for level in M.PF_LEVELS:
            program = M.PF_PROGRAMS[level]
            self.assertEqual(B.detoughness(self.tree(program)), B.detoughness(self.out['dsl'][program]))
            self.assertLessEqual(B.detoughness(self.out['dsl'][program]), M.PF_CAP[level])

    def test_only_the_multiplier_leaves_move(self):
        for program in (PF1, PF2, PF3):
            old, new = self.tree(program), self.out['dsl'][program]
            self.assertEqual(slv_leaves(old, 6), sorted(leaf_diff(old, new)), program)
            restored = deepcopy(new)
            for p in attack_paths(old):
                at(restored, p)[6] = deepcopy(at(old, p)[6])
            self.assertEqual(json.dumps(old), json.dumps(restored), program)

    # ---------------------------------------------------------------- 与灰服 1.4.85 逐节点比对

    def test_gray_changed_only_the_multiplier(self):
        """灰版 vs 我方第二批之前（第二批夹具 = live 1.4.1049）：只差每发风刃 args[6]。"""
        pre_b = json.loads(FIXTURE_B.read_bytes())['inputs']['dsl']
        for program in (PF1, PF2, PF3):
            gray = self.gray_tree(program)
            self.assertEqual(slv_leaves(gray, 6), sorted(leaf_diff(pre_b[program], gray)), program)
            self.assertTrue(all(at(gray, p)[13] == slv(5) for p in attack_paths(gray)), program)

    def test_output_is_gray_plus_batch2_p13(self):
        for level in M.PF_LEVELS:
            program = M.PF_PROGRAMS[level]
            gray, new = self.gray_tree(program), self.out['dsl'][program]
            self.assertEqual(M.GRAY_PF_TREE_DIGEST[level], M.digest(gray), level)
            want = [] if level == 1 else slv_leaves(gray, 13)          # Lv1 第二批没动 p13 ⇒ 与灰版逐字相同
            self.assertEqual(want, sorted(leaf_diff(gray, new)), level)
            self.assertEqual(json.dumps(gray), json.dumps(M.gray_view(new, level)), level)
        self.assertEqual(M.GRAY_PF_TREE_DIGEST[1], M.AFTER[PF1])
        for program in (PF1, PF2, PF3):
            hashed = core.sha1_path(wf_dsl.dsl_logical(program))
            self.assertEqual(f'production/upload/{hashed[:2]}/{hashed[2:]}', self.gray[program]['member'])

    # ---------------------------------------------------------------- 门禁 / 文案

    def test_trees_pass_dsl_gates_and_roundtrip(self):
        from wf_midautumn_kit_hibiki import dsl_problems as kit_dsl_problems
        for program, tree in self.out['dsl'].items():
            self.assertEqual([], M.dsl_problems(tree), program)
            self.assertEqual([], kit_dsl_problems(tree, element=None), program)
            rt = wf_dsl.parse_dsl(zlib.decompress(encode_tree(tree), -15))['tree']
            self.assertEqual(json.dumps(tree), json.dumps(rt), program)
        self.assertEqual(wf_dsl.encode_amf3(self.gray_tree(PF1)), wf_dsl.encode_amf3(self.out['dsl'][PF1]))

    def test_panel_text_carries_no_numbers(self):
        from wf_midautumn_kitlib import panel_problems
        self.assertEqual(['override_string_mosiyike'], self.context['cas_keys_with_code'])  # 无 desc_override 键
        text = self.context['cas']['override_string_mosiyike'][0][0]
        self.assertEqual([], panel_problems(text))
        self.assertFalse(any(ch.isdigit() for ch in text))
        leader = self.context['leader'][M.CID]
        self.assertEqual(['override_string_mosiyike'], [r[82] for r in leader if r[82]])

    # ---------------------------------------------------------------- 面板覆盖（同条件合并）

    def rows(self, panel):
        return self.inputs['leader'][M.CID] if panel == 'leader' else self.inputs['ability'][f'{M.CID}{panel}']

    def test_panel_texts_verbatim(self):
        self.assertEqual({'leader': 'desc_override_mosiyike', 1: 'desc_override_mosiyike_1',
                          4: 'desc_override_mosiyike_4'}, {p: M.PANEL_KEYS[p] for p in M.PANELS})
        for panel in M.PANELS:
            key = M.PANEL_KEYS[panel]
            self.assertEqual(PANEL_TEXTS[key], M.panel_text(panel), key)
            self.assertEqual([[PANEL_TEXTS[key]]], self.out['cas'][key], key)
        self.assertEqual({'leader': ('leader', '149997'), 1: ('ability', '1499971'), 4: ('ability', '1499974')},
                         {p: v[:2] for p, v in M.PANELS.items()})

    def test_every_data_row_has_exactly_one_line(self):
        """覆盖文案替换整块面板：每块面板的行分组覆盖全部数据行、各一次、行序不变。"""
        for panel, (_table, _key, layout) in M.PANELS.items():
            rows = self.rows(panel)
            self.assertEqual(list(range(len(rows))), [i for idx, _t in layout for i in idx], panel)
            self.assertEqual(len(layout), len(PANEL_TEXTS[M.PANEL_KEYS[panel]].split('\n')), panel)
        self.assertEqual({'leader': 5, 1: 4, 4: 8}, {p: len(self.rows(p)) for p in M.PANELS})

    def test_leader_lines_follow_the_data(self):
        """队长：数值 / 对象 / 条件逐行对数据（1000=1%、100000=1）。"""
        rows = self.rows('leader')
        lines = PANEL_TEXTS['desc_override_mosiyike'].split('\n')
        # L1 ← #0：722 覆盖 mosiyike_pf 三档，说明 = override_string（自动面板原文）
        self.assertEqual(('722', 'mosiyike_pf', '1,2,3', 'override_string_mosiyike'),
                         (rows[0][45], rows[0][80], rows[0][81], rows[0][82]))
        self.assertEqual(self.inputs['cas']['override_string_mosiyike'][0][0], lines[0])
        # L2 ← #1/#2：前置 kind 2（编成）≥3、组 Dragon；32 攻击力 / 35 充能，对象 Party+Dragon
        for i in (1, 2):
            self.assertEqual(('2', '300000', '300000', 'Dragon', '0', '0'),
                             (rows[i][4], rows[i][7], rows[i][8], rows[i][9], rows[i][3], rows[i][25]))
            self.assertEqual(('5', 'Dragon'), (rows[i][46], rows[i][47]))
            self.assertEqual(rows[i][49], rows[i][50])
        self.assertEqual(('32', '35'), (rows[1][45], rows[2][45]))
        self.assertEqual(f'队伍中编入{cnt(rows[1][7])}名以上龙族角色时，龙族角色攻击力＋{pct(rows[1][49])}%、'
                         f'技能充能速度＋{pct(rows[2][49])}%', lines[1])
        self.assertEqual(Counter([3, 240, 30]), numbers(lines[1]))
        # L3 ← #3：200 PowerFlipComboCountDown（常驻，Lv3 阈值 39 − n）；L4 ← #4：226 AddCombo（Initial ⇒ 开战一次）
        for i in (3, 4):
            self.assertEqual(('0', '0', '0'), (rows[i][3], rows[i][4], rows[i][25]))
        self.assertEqual(('200', '226'), (rows[3][45], rows[4][45]))
        self.assertEqual(f'强化弹射Lv3所需连击数－{cnt(rows[3][49])}', lines[2])
        self.assertEqual(f'战斗开始时，连击＋{cnt(rows[4][49])}', lines[3])
        self.assertEqual((Counter([3, 8]), Counter([5])), (numbers(lines[2]), numbers(lines[3])))

    def test_ability1_lines_follow_the_data(self):
        rows = self.rows(1)
        lines = PANEL_TEXTS['desc_override_mosiyike_1'].split('\n')
        self.assertTrue(all(r[1] == 'true' for r in rows))                  # 无主位限制 ⇒ 无图标
        # L1 ← #0：开幕（c5=2）玛纳加成（c123=2），强度 1.0 = 100%
        self.assertEqual(('2', '2', '1.0', '1.0'), (rows[0][5], rows[0][123], rows[0][124], rows[0][125]))
        self.assertEqual('玛纳获得数量＋100%', lines[0])
        # L2 ← #1/#2：瞬发 Initial、无前置；205 生命值 Party+Dragon 15%，32 攻击力 Leader 100%
        for i in (1, 2):
            self.assertEqual(('0', '0', '0'), (rows[i][5], rows[i][6], rows[i][27]))
        self.assertEqual(('205', '5', 'Dragon', '15000'), (rows[1][47], rows[1][48], rows[1][49], rows[1][51]))
        self.assertEqual(('32', '2', '', '100000'), (rows[2][47], rows[2][48], rows[2][49], rows[2][51]))
        self.assertEqual(f'龙族角色生命值＋{pct(rows[1][51])}%，队长攻击力＋{pct(rows[2][51])}%', lines[1])
        # L3 ← #3：前置 kind 2 ≥3 Dragon；32 攻击力 Party+Dragon 240%
        self.assertEqual(('2', '300000', '300000', 'Dragon', '32', '5', 'Dragon', '240000', '240000'),
                         tuple(rows[3][c] for c in (6, 9, 10, 11, 47, 48, 49, 51, 52)))
        self.assertEqual(f'队伍中编入{cnt(rows[3][9])}名以上龙族角色时，龙族角色攻击力＋{pct(rows[3][51])}%', lines[2])
        self.assertEqual([Counter([100]), Counter([15, 100]), Counter([3, 240])], [numbers(x) for x in lines])

    def test_ability4_lines_follow_the_data(self):
        rows = self.rows(4)
        lines = PANEL_TEXTS['desc_override_mosiyike_4'].split('\n')
        self.assertTrue(all(r[1] == 'true' and r[6] in ('0', '188') for r in rows))   # 无主位限制 ⇒ 无图标
        uq = self.inputs['table']['master/character/unique_condition.orderedmap|149997'][0]
        self.assertEqual(('翔风', '5'), (uq[1], uq[4]))
        # L1–L4 ← #0–#3：461 自身「翔风」＋strength 层（number 1、initial_multiply 1），触发 63/64/65 / 23(自身)
        for i, (trigger, layers, text) in enumerate((('63', 1, '发动强化弹射Lv1时，'), ('64', 2, '发动强化弹射Lv2时，'),
                                                     ('65', 3, '发动强化弹射Lv3时，'), ('23', 2, '自身发动技能时，'))):
            row = rows[i]
            self.assertEqual((trigger, '100000', '100000', '(None)', '0'),
                             (row[27], row[30], row[31], row[34], row[35]), i)
            self.assertEqual(('461', '0', '149997', '100000', '1', '0'),
                             (row[47], row[48], row[68], row[59], row[74], row[75]), i)
            self.assertEqual(layers, cnt(row[51]), i)
            self.assertEqual(f'{text}自身「{uq[1]}」＋{cnt(row[51])}层', lines[i])
        self.assertEqual('0', rows[3][28])                                     # 技能发动 puller = 自身
        # L5 ← #4/#5/#6：持续 134（自身「翔风」每 1 层，限 5）；0 攻击力 / 3 充能 Party+Dragon，23 强化弹射伤害（无对象）
        for i in (4, 5, 6):
            self.assertEqual(('1', '134', '0', '100000', '100000', '5', '149997', 'false'),
                             tuple(rows[i][c] for c in (5, 97, 98, 100, 101, 102, 104, 108)), i)
            self.assertEqual(rows[i][113], rows[i][114], i)
        self.assertEqual([('0', '5', 'Dragon'), ('3', '5', 'Dragon'), ('23', '0', '')],
                         [(rows[i][109], rows[i][110], rows[i][111]) for i in (4, 5, 6)])
        self.assertEqual(f'每{cnt(rows[4][100])}层「翔风」，龙族角色攻击力＋{pct(rows[4][113])}%、'
                         f'技能充能速度＋{pct(rows[5][113])}%，强化弹射伤害＋{pct(rows[6][113])}%'
                         f'（最多{rows[4][102]}层）', lines[4])
        # L6 ← #7：live 前置 188（实例个数，永不触发）→ 作者 09-27 拍板改 144（「翔风」层数 ≥5）；
        # 触发 2 强化弹射；690 最大速度固定延长（客户端固定 Party）
        self.assertEqual(('188', '0', '500000', '500000', '149997'), tuple(rows[7][c] for c in (6, 7, 9, 10, 12)))
        row = self.out['ability'][M.ABILITY_KEYS[3]][7]
        self.assertEqual(('144', '0', '500000', '500000', '149997'), tuple(row[c] for c in (6, 7, 9, 10, 12)))
        self.assertEqual(('2', '100000', '(None)', '0', '690', '30000', '30000'),
                         tuple(row[c] for c in (27, 30, 34, 35, 47, 51, 52)))
        self.assertEqual(f'自身「翔风」达到{cnt(row[9])}层以上期间，发动强化弹射时，'
                         f'队伍全体的最大速度固定效果持续时间＋{pct(row[51])}%', lines[5])
        self.assertEqual([Counter([1, 1]), Counter([2, 2]), Counter([3, 3]), Counter([2]),
                          Counter([1, 20, 3, 15, 5]), Counter([5, 30])], [numbers(x) for x in lines])

    def test_rendered_from_data_and_unmerged_form(self):
        names = M.unique_names({('table', (M.UQ, uid)): self.inputs['table'][f'{M.UQ}|{uid}'] for uid in M.UNIQUES})
        pf_text = self.inputs['cas'][M.PF_TEXT_KEY][0][0]
        for panel, (table, _key, layout) in M.PANELS.items():
            key = M.PANEL_KEYS[panel]
            rows = self.rows(panel)
            if panel == M.STACK_FIX[0]:
                rows = M.apply_stack_fix(rows)                 # 能力4 #7 按层数修正后的行
            self.assertEqual(PANEL_TEXTS[key].split('\n'), M.render_panel(table, rows, layout, names, pf_text), key)
            self.assertEqual(UNMERGED[key].split('\n'), M.unmerged_lines(table, rows, names, pf_text), key)

    def test_merge_groups_are_exactly_the_same_condition_groups(self):
        want_text = {'leader': [(1, 2)], 1: [(1, 2)], 2: [], 3: [], 4: [(4, 5, 6)], 5: [], 6: []}
        want_data = {'leader': [(1, 2), (3, 4)], 1: [(1, 2)], 2: [(0, 1)], 3: [], 4: [(4, 5, 6)], 5: [], 6: []}
        for panel in want_text:
            table = 'leader' if panel == 'leader' else 'ability'
            self.assertEqual(want_text[panel], M.condition_groups(table, self.rows(panel)), panel)
            self.assertEqual(want_data[panel], M.condition_groups(table, self.rows(panel), text=False), panel)
        self.assertEqual({'leader': (3, 4), 2: (0, 1)}, {p: v[0] for p, v in M.NOT_MERGED.items()})
        self.assertEqual((2, 3, 5, 6), M.AUTO_PANELS)
        # 不并的两组：一侧是 Initial 下开战执行一次（211 / 226），另一侧常驻
        self.assertEqual(('200', '226'), (self.rows('leader')[3][45], self.rows('leader')[4][45]))
        self.assertEqual(('211', '55'), (self.rows(2)[0][47], self.rows(2)[1][47]))
        for panel in M.PANELS:
            self.assertEqual([], M.layout_problems(panel, self.rows(panel)), panel)
        tables = {p: self.rows(p) for p in want_text}
        self.assertEqual([], M.census_problems(tables))

    def test_merge_self_checks_catch_violations(self):
        rows = deepcopy(self.rows(4))
        rows[5][102] = '4'                                   # 限层不同 ⇒ 不再同条件
        self.assertTrue(M.layout_problems(4, rows))
        with self.assertRaises(M.PanelError):
            M.render_line('ability', rows, (4, 5, 6), {'149997': '翔风', '1499970': '风蚀'}, '')
        leader = deepcopy(self.rows('leader'))
        leader[4][45] = '32'; leader[4][46] = '0'             # 226 → 常驻攻击力：与 #3 文案同条件却没并
        self.assertTrue(M.layout_problems('leader', leader))
        tables = {p: self.rows(p) for p in ('leader', 1, 2, 3, 4, 5, 6)}
        tables[3] = deepcopy(tables[3])
        tables[3][3] = deepcopy(tables[3][2])                  # 能力3 出现同条件组 ⇒ 普查不符
        self.assertTrue(M.census_problems(tables))

    def test_check_merge_passes(self):
        """面板合并校验器 wf_panel_merge_check（与 c_panels.merge_check 同一实现）：合并前 → 合并后通过，无删前缀授权。"""
        import wf_balance_20260927c_panels as P
        cm = load_check_merge()
        mappings = {'desc_override_mosiyike': {1: 1, 2: 2, 3: 2, 4: 3, 5: 4},
                    'desc_override_mosiyike_1': {1: 1, 2: 2, 3: 2, 4: 3},
                    'desc_override_mosiyike_4': {1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 5, 7: 5, 8: 6}}
        for key, text in PANEL_TEXTS.items():
            result = cm.check(UNMERGED[key], text, [])
            self.assertTrue(result['ok'], (key, result['errors']))
            self.assertEqual([], result['warnings'], key)
            self.assertEqual(mappings[key], result['columns'][0]['mapping'], key)
            self.assertTrue(P.merge_check(UNMERGED[key], text, [])['ok'], key)
        bad = PANEL_TEXTS['desc_override_mosiyike_4'].replace('＋3%', '＋5%')
        self.assertFalse(cm.check(UNMERGED['desc_override_mosiyike_4'], bad, [])['ok'])

    def test_panel_rules(self):
        from wf_midautumn_kitlib import panel_problems
        for key, text in PANEL_TEXTS.items():
            self.assertEqual([], panel_problems(text), key)                    # 非技能强化条目（无 536/704–708）
            self.assertEqual([], M.panel_problems(key, text), key)
            for word in ('自身为队长时', '觉醒后', '生命值100%以下', '／', '属性共鸣', '<icon'):
                self.assertNotIn(word, text, key)
        self.assertTrue(M.panel_problems('k', '自身为队长时，攻击力＋10%'))
        self.assertTrue(M.panel_problems('k', '火属性共鸣时：攻击力＋10%'))
        self.assertTrue(M.panel_problems('k', '攻击力＋10%／技能伤害＋10%'))
        for panel in ('leader', 1, 2, 3, 4, 5, 6):                      # 没有技能强化条目（536/704–708）
            flag_col = 45 if panel == 'leader' else 47
            self.assertFalse(any(r[flag_col] in ('536', '704', '705', '706', '707', '708') for r in self.rows(panel)),
                             panel)

    def test_resonance_omission_is_not_applicable(self):
        """逐个状态核对全部来源：两个固有状态都有不带共鸣的授予行、DSL 不引用 ⇒ 不省略；也没有带共鸣前置的行。"""
        tables = {('leader', M.CID): self.rows('leader'),
                  **{('ability', f'{M.CID}{s}'): self.rows(s) for s in range(1, 7)}}
        trees = {p: self.inputs['dsl'][p] for p in (*M.SKILL_PROGRAMS, PF1, PF2, PF3)}
        self.assertEqual([], M.state_basis_problems(tables, trees))
        for program, tree in trees.items():
            self.assertEqual([], M.dsl_uid_refs(tree), program)
        self.assertEqual({'149997': ('翔风', 5), '1499970': ('风蚀', 5)}, M.UNIQUES)
        for uid, sources in M.STATE_SOURCES.items():
            for label in sources['grant']:
                table, rest = label.split(':')
                key, index = rest.split('#')
                row = tables[table, key][int(index)]
                self.assertEqual([], M.precondition_blocks(table, row), label)     # 授予行无任何前置
        # 反例：授予行加火共鸣前置 / 依赖行加共鸣 / DSL 引用固有号 / 新增授予 ⇒ 报错
        bad = deepcopy(tables)
        bad['ability', '1499974'][0][6:12] = ['2', '', '', '600000', '600000', 'Green']
        self.assertTrue(M.state_basis_problems(bad, trees))
        bad = deepcopy(tables)
        bad['ability', '1499975'].append(deepcopy(bad['ability', '1499974'][0]))
        self.assertTrue(any('sources' in p for p in M.state_basis_problems(bad, trees)))
        bad_trees = deepcopy(trees)
        bad_trees[M.SKILL_PROGRAMS[0]].append(['Command', ['X', ['ACUnique', 149997, 1]]])
        self.assertTrue(M.state_basis_problems(tables, bad_trees))

    def test_latent_ability4_row7_never_triggers(self):
        """能力4 #7：188 ConditionCountUnique 数实例个数（461 叠层固有恒为 1 个）、阈值 ≥5 ⇒ 永不触发；照数据写，不改。"""
        rows = self.rows(4)
        self.assertEqual(('188', '500000', '149997'), (rows[7][6], rows[7][9], rows[7][12]))
        self.assertIn('188', M.PRE_UNIQUE)
        grants = [r for r in rows if r[47] == '461' and r[68] == '149997']
        self.assertEqual(4, len(grants))
        self.assertTrue(all(r[59] == '100000' for r in grants))                # 每次只给 1 个实例（叠层）
        self.assertEqual('5', self.inputs['table']['master/character/unique_condition.orderedmap|149997'][0][4])
        self.assertIn('「翔风」达到5层以上', PANEL_TEXTS['desc_override_mosiyike_4'].split('\n')[5])
        self.assertIn('ability4#7', M.LATENT)
        self.assertEqual({'ability4#7', 'ability4#2', 'leader#4'}, set(M.LATENT))
        # 能力4 #2：Lv3 强化弹射 → +3 层（461，无前置）⇒ 无同类问题
        self.assertEqual(('65', '461', '300000', '0'), (rows[2][27], rows[2][47], rows[2][51], rows[2][6]))
        # 本角色其余按固有状态判定的行都用按层计数的 134 / 171
        others = [(k, i, r[97]) for k in ('1499974', '1499976')
                  for i, r in enumerate(self.inputs['ability'][k]) if r[5] == '1' and r[97] in M.DT_UNIQUE]
        self.assertEqual([('1499974', 4, '134'), ('1499974', 5, '134'), ('1499974', 6, '134'),
                          ('1499976', 1, '171')], others)

    def test_render_is_fail_closed(self):
        names = {'149997': '翔风', '1499970': '风蚀'}
        for mutate in (lambda r: r.__setitem__(111, 'Beast'),            # 未登记的角色组
                       lambda r: r.__setitem__(114, '25000'),            # 低 / 满两端不同
                       lambda r: r.__setitem__(109, '34'),               # 未审的持续内容
                       lambda r: r.__setitem__(97, '194')):              # 数实例的持续触发
            rows = deepcopy(self.rows(4))
            mutate(rows[4])
            with self.assertRaises(M.PanelError):
                M.render_line('ability', rows, (4,), names, '')
        rows = deepcopy(self.rows(1))
        rows[3][11] = 'Green'                                              # 属性共鸣 ⇒ 未审措辞
        with self.assertRaises(M.PanelError):
            M.render_line('ability', rows, (3,), names, '')
        live = deepcopy(self.inputs)
        live['ability']['1499974'][5][113] = live['ability']['1499974'][5][114] = '5000'
        with self.assertRaisesRegex(ValueError, 'unreviewed live baseline'):
            M.revise(self.read_from(live))

    def test_panel_capability(self):
        from wf_client_legality import required_client_capabilities
        caps = sorted({c for key in self.out['cas'] for c in required_client_capabilities('custom_ability_string', [key])})
        self.assertEqual(['panel-description-override-v2'], caps)
        self.assertEqual(caps, M.CAPABILITIES)
        self.assertEqual(M.CAPABILITIES, self.out['notes']['capabilities'])

    def test_panel_notes(self):
        notes = self.out['notes']
        self.assertEqual({key: [{'rows': list(idx), 'text': text} for idx, text in M.PANELS[p][2]]
                          for p, key in ((p, M.PANEL_KEYS[p]) for p in M.PANELS)},
                         {key: v['lines'] for key, v in notes['panel_overrides'].items()})
        self.assertEqual({M.PANEL_KEYS[p] for p in M.AUTO_PANELS}, set(notes['panel_auto_kept']))
        self.assertEqual(set(M.LATENT), set(notes['latent_issues']))
        json.dumps(notes, ensure_ascii=False)

    # ---------------------------------------------------------------- fail closed

    def test_live_drift_is_rejected_and_inputs_are_not_mutated(self):
        original = deepcopy(self.inputs)
        M.revise(self.read_from(self.inputs))
        self.assertEqual(json.dumps(original), json.dumps(self.inputs))
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
        for _kind, key in M.ABSENT:                                   # 任一覆盖键已存在 ⇒ 面板不再是自动生成
            present = deepcopy(self.inputs)
            present['cas'][key] = [['x']]
            with self.assertRaisesRegex(ValueError, 'already exists'):
                M.revise(self.read_from(present))

    def test_own_output_is_not_revised_twice(self):
        live = deepcopy(self.inputs)
        live['dsl'].update(deepcopy(self.out['dsl']))
        with self.assertRaisesRegex(ValueError, 'unreviewed live baseline'):
            M.revise(self.read_from(live))
        live = deepcopy(self.inputs)
        live['cas'].update(deepcopy(self.out['cas']))
        with self.assertRaisesRegex(ValueError, 'already exists'):
            M.revise(self.read_from(live))
        for level in M.PF_LEVELS:
            with self.assertRaisesRegex(ValueError, 'wind-blade preimage drift'):
                M.revise_pf_tree(self.out['dsl'][M.PF_PROGRAMS[level]], level)

    def test_structure_guards(self):
        with self.assertRaisesRegex(ValueError, 'wind-blade preimage drift'):
            M.revise_pf_tree(self.tree(PF2), 3)                       # 档位错配（5 发 vs 10 发）
        pre_b = json.loads(FIXTURE_B.read_bytes())['inputs']['dsl']
        with self.assertRaisesRegex(ValueError, 'wind-blade preimage drift'):
            M.revise_pf_tree(pre_b[PF3], 3)                           # 第二批 p13 未落（5 而非 2.5）
        tree = deepcopy(self.tree(PF3))
        at(tree, attack_paths(tree)[4])[6] = slv(6.5)
        with self.assertRaisesRegex(ValueError, 'wind-blade preimage drift'):
            M.revise_pf_tree(tree, 3)
        tree = deepcopy(self.tree(PF1))
        at(tree, attack_paths(tree)[0])[6] = [{'min': 12.5, 'max': 13.0}]
        with self.assertRaisesRegex(ValueError, 'multiplier shape'):
            M.revise_pf_tree(tree, 1)
        tree = deepcopy(self.tree(PF2))
        at(tree, attack_paths(tree)[0][:-4])[14] = ['CalculatedUsingMaxNumOfHits', 2]
        with self.assertRaisesRegex(ValueError, 'wind-blade preimage drift'):
            M.revise_pf_tree(tree, 2)
        tree = deepcopy(self.tree(PF2))
        tree[1] = 2
        with self.assertRaisesRegex(ValueError, 'root header drift'):
            M.revise_pf_tree(tree, 2)
        tree = deepcopy(self.tree(PF2))
        self.assertEqual(['Command', ['SetPowerFilpSuppress', 90]], tree[11][1][0])
        tree[11][1][0][1][1] = 91                                     # 风刃以外的节点漂移 ⇒ 与灰版对不上
        with self.assertRaisesRegex(ValueError, 'differs from the gray 1.4.85 tree'):
            M.revise_pf_tree(tree, 2)

    def test_revise_is_deterministic(self):
        again = M.revise(self.read_from(self.inputs))
        self.assertEqual(json.dumps(self.out, sort_keys=True), json.dumps(again, sort_keys=True))

    # ---------------------------------------------------------------- 接口常量

    def test_module_contract_constants(self):
        self.assertEqual(('149997', 'mosiyike'), (M.CID, M.CODE))
        self.assertEqual(['mosiyike'], M.PACKAGES)
        self.assertEqual({'mosiyike': '0.1.3'}, M.PACKAGE_VERSION)
        version = tuple(map(int, M.PACKAGE_VERSION['mosiyike'].split('.')))
        self.assertGreater(version, tuple(map(int, G3.SPECS['149997']['version']['mosiyike'].split('.'))))
        self.assertEqual(['panel-description-override-v2'], M.CAPABILITIES)   # 三个新 desc_override 键
        for key in self.out['cas']:                                     # RevisionCandidate 命名空间（desc_override_<code>[_n]）
            self.assertRegex(key, r'^desc_override_mosiyike(_[1-6])?$')
        self.assertEqual(B.REVIEWED_DRIFT, M.REVIEWED_DRIFT)
        self.assertEqual(29, len(M.REVIEWED_DRIFT))
        self.assertTrue(all(logical not in {wf_dsl.dsl_logical(p) for p in M.PF_PROGRAMS.values()}
                            for _, logical in M.REVIEWED_DRIFT))      # PF 树本身不在已审漂移里
        self.assertFalse(self.out['notes']['runtime_verified'])
        json.dumps(self.out['notes'], ensure_ascii=False)

    # ---------------------------------------------------------------- 灰链归档 / 生成器 / 候选 / live（本机）

    @unittest.skipUnless((ROOT / M.GRAY_CHAIN / M.GRAY_ARCHIVE).is_file(), 'gray chain archive not on this machine')
    def test_gray_archive_members_are_the_pinned_bytes(self):
        with zipfile.ZipFile(ROOT / M.GRAY_CHAIN / M.GRAY_ARCHIVE) as zf:
            for level in M.PF_LEVELS:
                program = M.PF_PROGRAMS[level]
                raw = zf.read(self.gray[program]['member'])
                self.assertEqual(M.GRAY_PF_DEFLATE_SHA256[level], hashlib.sha256(raw).hexdigest(), level)
                amf = zlib.decompress(raw, -15)
                self.assertEqual(json.dumps(self.gray_tree(program)), json.dumps(wf_dsl.parse_dsl(amf)['tree']))
                self.assertEqual(amf, wf_dsl.encode_amf3(self.gray_tree(program)), level)
        self.assertEqual(zlib.decompress(zipfile.ZipFile(ROOT / M.GRAY_CHAIN / M.GRAY_ARCHIVE)
                                         .read(self.gray[PF1]['member']), -15),
                         wf_dsl.encode_amf3(self.out['dsl'][PF1]))    # Lv1 输出 AMF3 与灰版逐字节相同

    @unittest.skipUnless((WORKSPACE / 'build_pf.py').is_file() and (ROOT / 'mod-tools/profiles.json').is_file()
                         and (ROOT / '弹国服/bundle.zip').is_file(), 'local workspace kit required')
    def test_generator_sync_is_one_constant(self):
        """生成器 build_pf.py 已同步为灰服倍率（TOTALS 15/30/45），纯函数 build_level 输出 == 本模块输出（不调 main）。"""
        spec = importlib.util.spec_from_file_location('mosiyike_build_pf_c', WORKSPACE / 'build_pf.py')
        kit = importlib.util.module_from_spec(spec)
        saved, sys.dont_write_bytecode = sys.dont_write_bytecode, True
        try:
            spec.loader.exec_module(kit)
        finally:
            sys.dont_write_bytecode = saved
        self.assertEqual(NEW_TOTALS, kit.TOTALS)
        self.assertEqual(M.P13, kit.DETOUGHNESS)
        for level in M.PF_LEVELS:
            self.assertEqual(json.dumps(self.out['dsl'][M.PF_PROGRAMS[level]]), json.dumps(kit.build_level(level)),
                             level)

    @unittest.skipUnless((WORKSPACE / 'package/manifest.json').is_file()
                         and (ROOT / 'mod-tools/profiles.json').is_file(),
                         'local candidate workspace required')
    def test_candidate_opens_with_reviewed_drift_and_splices_dry(self):
        from wf_character_revision import RevisionCandidate
        manifest = WORKSPACE / 'package/manifest.json'
        before = manifest.read_bytes()
        meta = json.loads(before)
        candidate = RevisionCandidate(ROOT, WORKSPACE, reviewed_input_drift=M.REVIEWED_DRIFT,
                                      character_id=M.CID, code_name=M.CODE,
                                      snapshot_key='revision_20260927d',
                                      package_version=M.PACKAGE_VERSION[M.PACKAGES[0]],
                                      baseline_factory=lambda *a, **k: None)

        def tree_in_candidate(program):
            raw = candidate.read('common', wf_dsl.dsl_logical(program))
            return wf_dsl.parse_dsl(zlib.decompress(raw, -15))['tree']

        import wf_share_update_codec as X
        cas_rows = X.unpack(candidate.read('common', CAS_TABLE))
        if meta['snapshot'].get('revision_20260927d') is not None:
            # 主会话暂存回写之后：候选 PF 三档 = 本模块输出；三个面板覆盖键已认领且逐字相同。
            for program, tree in self.out['dsl'].items():
                self.assertEqual(json.dumps(tree), json.dumps(tree_in_candidate(program)), program)
            for key, value in self.out['cas'].items():
                self.assertEqual(value, X.csv_read(cas_rows[key]), key)
            return
        self.assertLess(tuple(map(int, meta['package_version'].split('.'))),
                        tuple(map(int, M.PACKAGE_VERSION[M.PACKAGES[0]].split('.'))))
        for program in (PF1, PF2, PF3):
            self.assertEqual(json.dumps(self.tree(program)), json.dumps(tree_in_candidate(program)), program)
        for _kind, key in M.ABSENT:                                      # 回写前候选也没有覆盖键
            self.assertNotIn(key, cas_rows)
        for program, tree in self.out['dsl'].items():
            candidate.emit('common', wf_dsl.dsl_logical(program), encode_tree(tree))
        candidate.splice(CAS_TABLE, self.out['cas'])                      # 新键在 desc_override_<code> 命名空间内
        claim = next(t for t in candidate.manifest['tables'] if t['logical_path'] == CAS_TABLE)
        self.assertEqual(sorted({'override_string_mosiyike', *self.out['cas']}), claim['outer_keys'])
        evidence = candidate.finish({'dry_run': True}, apply=False)
        self.assertFalse(evidence['applied'])
        changed = {item['logical_path']: item['before_sha256'] for item in evidence['changed_files']}
        cas_before = hashlib.sha256(candidate.original['common', CAS_TABLE]).hexdigest() \
            if ('common', CAS_TABLE) in candidate.original else None
        self.assertEqual({**{wf_dsl.dsl_logical(p): self.raw_sha[p] for p in self.out['dsl']}, CAS_TABLE: cas_before},
                         changed)
        spliced = X.unpack(candidate.outputs['common', CAS_TABLE])
        for key, value in self.out['cas'].items():
            self.assertEqual(value, X.csv_read(spliced[key]), key)
        self.assertEqual(before, manifest.read_bytes())

    @unittest.skipUnless((ROOT / 'mod-tools/profiles.json').is_file(), 'local live store required')
    def test_live_is_either_the_baseline_or_this_output(self):
        import wf_share_update_codec as X
        store = Path(core.resolve_active_store())
        for program, tree in self.out['dsl'].items():
            path = core.table_path(store, wf_dsl.dsl_logical(program))
            if not path.is_file():
                self.skipTest('live store DSL not present')
            live = wf_dsl.parse_dsl(zlib.decompress(path.read_bytes(), -15))['tree']
            self.assertIn(M.digest(live), {M.BEFORE['dsl', program], M.digest(tree)}, program)
        cas = X.unpack(core.table_path(store, CAS_TABLE).read_bytes())
        for key, value in self.out['cas'].items():                       # 面板覆盖键：未发布（无）或 = 本轮输出
            self.assertIn(X.csv_read(cas[key]) if key in cas else None, (None, value), key)
        for panel in M.AUTO_PANELS:                                     # 自动生成的面板不新建覆盖
            self.assertNotIn(M.PANEL_KEYS[panel], cas)


if __name__ == '__main__':
    unittest.main()
