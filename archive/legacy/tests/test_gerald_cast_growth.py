"""Read the real pre-revision program; preserve normal attacks and execute semantics."""

from wf.paths import root_path
from pathlib import Path
import sys, unittest, zlib
pass  # Imports resolve from this checkout/package, not external source copies.
import wf_gerald_cast_growth as G
import wf_gerald_percent_skill as P
import wf_dsl, wf_client_legality as L
from wf_character_revision import encode_tree
from wf_wind_dragon_revision import nodes


class GeraldCastGrowthTest(unittest.TestCase):
    def test_native_current_hp_example_and_growth_without_local_assets(self):
        from wf_bianca_dragon_skill import block, command
        old=['ActionDsl',1,['None'],False,False,False,False,False,False,False,0,
             block(command('ConditionalsChangeSkillFlag',1,
                 block(P.nearest_percent_attack(.05,execute_below_percent=5)),block()))]
        new=G.rewrite(old)
        strike=next(x for x in nodes(new,'CreateRatioAttack')if len(x[3])==2)
        self.assertEqual(strike[2],1)
        for cast,damage in [(0,30000),(1,36000),(2,42000)]:
            rate=sum(v['min']*(cast if 'mul' in v else 1)for v in strike[3])
            self.assertAlmostEqual(600000*rate,damage)
        with self.assertRaises(ValueError):G.rewrite(new)

    def test_live_baseline_both_levels_snapshot_ratio_and_single_counter(self):
        base = Path(('${WF_ROOT}/out/风巨蜥与校园希尔媞调整-20260925/before/live/common'.replace("${WF_ROOT}", str(root_path()))))
        if not base.is_dir():self.skipTest('local captured resource not present')
        for logical in P.ACTIVE_PATHS.values():
            old = wf_dsl.parse_dsl(zlib.decompress((base/logical).read_bytes(), -15))['tree']
            new = G.rewrite(old)
            self.assertEqual(list(nodes(new,'CreateNormalAttack')),list(nodes(old,'CreateNormalAttack')))
            self.assertFalse(L.action_dsl_lookup_scope_problems(new))
            self.assertEqual(wf_dsl.parse_dsl(zlib.decompress(encode_tree(new),-15))['tree'],new)
            ratios=list(nodes(new,'CreateRatioAttack'))
            strike=next(x for x in ratios if len(x[3])==2)
            self.assertEqual(strike[2],1)  # remaining HP, never max HP
            # Bind 第 5 参 = 变量上限；客户端取 min(层数/1, 上限)。第二批曾封到 10（最多 15%），
            # 作者 09-27 追加撤回：成长只在当队长时强化 ⇒ 恢复 2147483647.0（浮点，与 live 解码同类型）。
            binds=list(nodes(new,'BindConditionAccumulationVariable'))
            self.assertEqual(binds,[['BindConditionAccumulationVariable',-17,G.COUNTER_VARIABLE,
                                     ['DCUnique',G.COUNTER_UID],1,G.COUNTER_CAP]])
            self.assertEqual(G.COUNTER_CAP,2147483647.0)
            self.assertIs(type(G.COUNTER_CAP),float)
            self.assertIs(type(binds[0][5]),float)
            for prior_casts,expected in [(0,.05),(1,.06),(2,.07),(10,.15),(20,.25)]:
                bound=min(prior_casts/binds[0][4],binds[0][5])
                actual=sum(v['min']*(bound if v.get('mul') else 1) for v in strike[3])
                self.assertAlmostEqual(actual,expected)
            branch=list(nodes(new,'ConditionalsHealthPointRatioOf'))[0]
            self.assertEqual(branch[2],5)
            self.assertEqual(list(nodes(branch[4],'CreateRatioAttack'))[0][2:],[1,[{'min':1.0,'max':1.0}]])
            entry=list(nodes(new,'ConditionalsChangeSkillFlag'))[0][2][1]
            self.assertEqual(entry[0][1][0],'BindConditionAccumulationVariable')
            self.assertEqual(entry[1][1][2],[['ACUnique',G.COUNTER_UID,[{'min':1,'max':1}]]])
            self.assertEqual(len(list(nodes(new,'ACUnique'))),1)
        self.assertEqual(G.counter_row()[0][10],'true')
        self.assertEqual(G.counter_row()[0][13],'false')


if __name__=='__main__':unittest.main()
