import unittest
from copy import deepcopy
from wf_zehr_spin_animation import smooth_parts


class SpinAnimationTest(unittest.TestCase):
    def source(self):
        return dict(m=[],i=[{}],a=[1],t=[],g=[dict(t=33,s=[dict(s=2<<30,i=1,l=[
            dict(m=255,t=33,r=(2<<30)|2)])]),dict(t=33,s=[dict(s=1,i=0,l=[
            dict(m=255,t=(2<<16)|10),dict(m=255,t=22)])])])

    def test_tween_bits_and_child_phase_are_retimed_without_freeze(self):
        source=self.source();before=deepcopy(source);result=smooth_parts(source)
        self.assertEqual(source,before)
        self.assertEqual(result['g'][0]['t'],100)
        self.assertEqual(result['g'][0]['s'][0]['l'][0]['r'],(2<<30)|6)
        strip=result['g'][1]['s'][0]
        self.assertEqual(strip['s'],3)
        self.assertEqual(strip['l'][0]['t']>>16,2)
        self.assertEqual(strip['l'][0]['t']&0xffff,30)

    def test_ornament_uses_existing_textures_and_bounded_alpha(self):
        source=self.source();result=smooth_parts(source,ornament=True)
        self.assertEqual(result['i'],source['i'])
        self.assertEqual(len(result['g']),3)
        self.assertEqual([s['l'][0]['m']&255 for s in result['g'][0]['s']],[255,64])
        self.assertTrue(all(s['i']==2 for s in result['g'][0]['s']))

    def test_rounding_does_not_restart_child_on_last_frame(self):
        source=self.source()
        source['g'][0]=dict(t=104,s=[dict(s=2<<30,i=1,l=[
            dict(m=255,t=41,r=2<<30),dict(m=255,t=63,r=2<<30)])])
        source['g'][1]['t']=63
        result=smooth_parts(source)
        keys=result['g'][0]['s'][0]['l']
        self.assertEqual(keys[1]['t'],191)
        self.assertEqual(result['g'][1]['t'],190)
        self.assertEqual(keys[1]['r']>>30,1)


if __name__=='__main__':unittest.main()
