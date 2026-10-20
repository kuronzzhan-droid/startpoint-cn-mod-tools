"""离线执行 v33 里插入的三段通用技能准备字节码（直接跑生成的指令，不另写行为模型）。"""
import json
import os
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, r"D:/WF/perf-v30-20261015/tools")
from common import ABC, abc_tags, asm, bodies  # noqa: E402
import voice_patches as V  # noqa: E402
from vm2 import run  # noqa: E402

EXISTS = 'pinball.asset.logic:ILogicAssetContainer::existsVoiceFileReader'
ADD = 'pinball.asset.logic:IAssetPathCollectionBuilder::addSoundEffect'
NONE = {'index': 1, 'params': []}


def some(p):
    return {'index': 0, 'params': [p]}


class Files:
    """严格的资源 mock：只认清单里的路径，其他一律 False；记录被问过的路径。"""
    def __init__(self, files):
        self.files, self.asked = set(files), []

    def __call__(self, p):
        assert isinstance(p, str), p
        self.asked.append(p)
        return p in self.files


def block(abc, label, at, n, tail):
    code = asm.decode(abc.bodies[bodies.resolve(abc, label)][5])[at:at + n]
    for x in code:
        if x.target is not None:
            x.target -= at
            assert 0 <= x.target <= n
    return code + asm.assemble(tail)


class T(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        name = os.environ.get('VOICE_SWF', 'v33')
        raw = (HERE / f'{name}.swf').read_bytes()
        cls.a = ABC({n: r for n, *_x, r in abc_tags(raw)}[b'boot_ffc6'])
        rep = json.loads((HERE / f'{name}-report.json').read_text(encoding='utf8'))
        p = {x['id']: (x['inserted_at'], x['inserted']) for x in rep['patches']}
        cls.v1 = block(cls.a, 'HudMemberStatus/update', *p['V1'], [('getlocal', 4), ('returnvalue',)])
        cls.v2 = block(cls.a, 'BattleCharacterLogic/resolveFollowingPathCollection', *p['V2'], [('returnvoid',)])
        cls.v3 = block(cls.a, 'CharacterVoiceLogic/createVoicePathMap', *p['V3'], [('getlocal', 21), ('returnvalue',)])
        strings = {abc_s.decode(errors='ignore') for abc_s in cls.a.strings[1:]}
        ints = set(cls.a.ints[1:])
        # 本包实际写死过的角色（旧包少几个，少的走通用）——按插入块里是否引用来判
        def refs(code, op, pool):
            return {(cls.a.strings[x.args[0]].decode() if op == 'pushstring' else cls.a.ints[x.args[0]])
                    for x in code if x.name == op}
        cls.skip_codes = [c for c in V.SKIP_CODES if c in refs(cls.v1, 'pushstring', strings)]
        cls.skip_ids2 = [i for i in V.SKIP_IDS if i in refs(cls.v2, 'pushint', ints)]
        cls.skip_ids3 = [i for i in V.SKIP_IDS if i in refs(cls.v3, 'pushint', ints)]
        print(name, cls.skip_codes, cls.skip_ids2, cls.skip_ids3)

    # ---------------------------------------------------------------- V1 轮换
    def hud(self, code, files):
        return {'character': {'mainCharacterStringId': code, 'logic': {'logicAssets': {EXISTS: Files(files)}}},
                'geraldReadyNext': 0}

    def ready(self, h, opt):
        return run(self.v1, self.a, [h, None, None, None, opt, None, None, None],
                   lex={'haxe.ds::Option': {'Some': some}})

    def test_v1_cycle_two_alts(self):
        b = 'character/fire_dragon_zenith/voice/battle/skill_ready'
        h = self.hud('fire_dragon_zenith', [b, b + '_alt_1', b + '_alt_2'])
        got = [self.ready(h, some(b))['params'][0] for _ in range(7)]
        self.assertEqual(got, [b, b + '_alt_1', b + '_alt_2', b, b + '_alt_1', b + '_alt_2', b])

    def test_v1_no_alt_keeps_native(self):
        b = 'character/x/voice/battle/skill_ready'
        h = self.hud('x', [b])
        self.assertEqual([self.ready(h, some(b))['params'][0] for _ in range(4)], [b] * 4)

    def test_v1_matched_path(self):
        b = 'character/x/voice/battle/matched_skill_ready'
        h = self.hud('x', [b, b + '_alt_1'])
        self.assertEqual([self.ready(h, some(b))['params'][0] for _ in range(4)], [b, b + '_alt_1', b, b + '_alt_1'])

    def test_v1_none_untouched(self):
        h = self.hud('x', [])
        self.assertIs(self.ready(h, NONE), NONE)
        self.assertEqual(h['geraldReadyNext'], 0)

    def test_v1_hardcoded_skipped(self):
        for c in self.skip_codes:
            b = f'character/{c}/voice/battle/skill_ready'
            h = self.hud(c, [b, b + '_alt_1'])
            h['geraldReadyNext'] = 3
            opt = some(b)
            self.assertIs(self.ready(h, opt), opt)
            self.assertEqual(h['geraldReadyNext'], 3)

    # ---------------------------------------------------------------- V2 预载
    def short(self, cid, ready, switched, files):
        return {'characterId': cid, 'logicAssets': {EXISTS: Files(files)},
                'get_skillReadyVoicePath': lambda: ready, 'get_switchedSkillReadyVoicePath': lambda: switched}

    def preload(self, short, plays=True):
        got = []
        args = [None] * 14
        args[1] = {ADD: got.append}
        args[3] = {'playsSkillReady': plays}
        args[5] = short
        run(self.v2, self.a, args)
        return got

    def test_v2_adds_existing_alts_stops_at_gap(self):
        b, m = 'character/x/voice/battle/skill_ready', 'character/x/voice/battle/matched_skill_ready'
        s = self.short(111183, some(b), some(m), [b + '_alt_1', b + '_alt_2', b + '_alt_4', m + '_alt_1'])
        self.assertEqual(self.preload(s), [b + '_alt_1', b + '_alt_2', m + '_alt_1'])

    def test_v2_five_max(self):
        b = 'character/x/voice/battle/skill_ready'
        s = self.short(141099, some(b), NONE, [b + f'_alt_{k}' for k in range(1, 8)])
        self.assertEqual(self.preload(s), [b + f'_alt_{k}' for k in range(1, 6)])

    def test_v2_none_options_and_flag(self):
        self.assertEqual(self.preload(self.short(111183, NONE, NONE, [])), [])
        b = 'character/x/voice/battle/skill_ready'
        self.assertEqual(self.preload(self.short(111183, some(b), NONE, [b + '_alt_1']), plays=False), [])

    def test_v2_hardcoded_skipped(self):
        b = 'character/x/voice/battle/skill_ready'
        for cid in self.skip_ids2:
            self.assertEqual(self.preload(self.short(cid, some(b), some(b), [b + '_alt_1'])), [])

    # ---------------------------------------------------------------- V3 图鉴
    def gallery(self, cid, paths, files):
        args = [None] * 39
        args[2] = {'characterId': cid, 'logicAssets': {EXISTS: Files(files)}}
        args[21] = list(paths)
        return run(self.v3, self.a, args)

    def test_v3_appends_alts(self):
        b, m = 'character/x/voice/battle/skill_ready', 'character/x/voice/battle/matched_skill_ready'
        self.assertEqual(self.gallery(141099, [b, m], [b + '_alt_1', m + '_alt_1', m + '_alt_2']),
                         [b, m, b + '_alt_1', m + '_alt_1', m + '_alt_2'])
        self.assertEqual(self.gallery(141099, [b], [b + '_alt_1']), [b, b + '_alt_1'])
        self.assertEqual(self.gallery(141099, [], []), [])

    def test_v3_white_tiger_listed_others_skipped(self):
        b = 'character/white_tiger_summer/voice/battle/skill_ready'
        self.assertEqual(self.gallery(149990, [b], [b + '_alt_1']), [b, b + '_alt_1'])
        self.assertNotIn(149990, self.skip_ids3)
        for cid in self.skip_ids3:
            self.assertEqual(self.gallery(cid, [b], [b + '_alt_1']), [b])


if __name__ == '__main__':
    unittest.main()
