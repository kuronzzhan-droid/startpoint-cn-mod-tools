import copy,sys,unittest
from pathlib import Path
pass  # Imports resolve from this checkout/package, not external source copies.
import wf_magnus_fx_cleanup as F,wf_magnus_pf_orbit as O


class CleanupTest(unittest.TestCase):
    def test_remove_all_weapon_instances_without_touching_other_strips(self):
        strip=lambda i:{'s':0,'i':i,'l':[{'m':255,'t':4}]}
        parts={'i':[{'p':'x/zeta_lance/g'},{'p':'x/zeta_lance/h'}],
               'g':[{'s':[strip(0),strip(1),{'s':-2147483648,'i':0,'l':[]}]}], 'a':[1,1]}
        old=copy.deepcopy(parts);out,note=F.remove_weapon(parts,'zeta_lance')
        self.assertEqual(parts,old)
        self.assertEqual(out['g'][0]['s'],old['g'][0]['s'][1:])
        self.assertEqual(out['a'],parts['a']);self.assertEqual(note['removed_strips'],1)
        with self.assertRaises(ValueError):F.remove_weapon(out,'zeta_lance')

    def test_root_alpha_does_not_change_child_fades_or_lifetimes(self):
        p={'g':[{'t':79,'s':[{'l':[{'m':(7<<12)|255,'t':79,'r':123}]}]},
                {'t':79,'s':[{'l':[{'m':80,'t':40},{'m':0,'t':39}]}]}]}
        out=F.soften_burst(p);self.assertEqual(out['g'][1],p['g'][1])
        self.assertEqual(out['g'][0]['s'][0]['l'][0],{'m':(7<<12)|140,'t':79,'r':123})
        with self.assertRaises(ValueError):F.soften_burst(out)

    def test_cone_translation_copies_matrix_shared_by_children(self):
        p={'g':[{'s':[{'l':[{'m':255,'t':96,'r':0}]}]}],
           't':[{'a':4095,'b':0,'c':0,'d':4095,'x':0,'y':0}]}
        out=O.shift_cone(p)
        self.assertEqual(out['t'][0],p['t'][0]);self.assertEqual(len(out['t']),2)
        self.assertEqual(out['t'][1]['y'],105*4096)
        self.assertEqual(out['g'][0]['s'][0]['l'][0]['m'],4096+255)
        with self.assertRaises(ValueError):O.shift_cone(out)

    def test_red_slashes_stop_on_collision_and_empty_field_expiry(self):
        end=['Command',['NotifyPowerflipEnd',-18]]
        tree=[None]*11+[['Block',[
            ['Event',['Wait',90,'hit',['Block',[end]]]],
            ['Command',['ShowEffect','cone']],
            ['Event',['CollisionOfBallAndEnemy',90,1,'*',0,['Block',[
                ['Command',['HideEffect','cone']],['Command',['ShowEffect','cone_end']]]]]]]]]
        result=O.attach(tree,'cone');body=result[11][1]
        collision=next(v[1][5][1]for v in body if v[1][0]=='CollisionOfBallAndEnemy')
        expiry=next(v[1][3][1]for v in body if v[1][0]=='Wait'and v[1][1]==90)
        for commands in (collision,expiry):
            for name in O.effect_names():
                self.assertIn(['Command',['RemoveEvent',name]],commands)
                self.assertIn(['Command',['HideEffect',name]],commands)
        self.assertEqual(expiry[-1],end)
        for start,node in enumerate(O.shows()):
            show=node[1] if start==0 else node[1][3][1][0][1]
            self.assertEqual(show[2],['SpecifyEffectDirectly',O.EFFECT])
            self.assertEqual(show[4],['BacksideOfCharacter'])
            self.assertLessEqual(start*10+show[5][1],90)


if __name__=='__main__':unittest.main()
