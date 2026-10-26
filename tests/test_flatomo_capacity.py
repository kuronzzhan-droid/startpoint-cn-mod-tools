import unittest
from wf_flatomo_capacity import image_capacities, validate_image_capacities


class ImageCapacityTest(unittest.TestCase):
    def source(self):
        return dict(i=[{}],a=[1],m=[],g=[dict(t=2,s=[
            dict(s=2<<30,i=1,l=[dict(m=255,t=2,r=2<<30)]),
            dict(s=2<<30,i=1,l=[dict(m=255,t=2,r=2<<30)])]),
            dict(t=2,s=[dict(s=0,i=0,l=[dict(m=255,t=2)])])])

    def test_duplicate_nested_graphics_exhaust_native_image_pool(self):
        source=self.source()
        self.assertEqual(image_capacities(source),[2])
        with self.assertRaisesRegex(ValueError,'capacity'):validate_image_capacities(source)
        source['a']=[2]
        validate_image_capacities(source)

    def test_nonoverlapping_strips_share_pool(self):
        source=dict(i=[{}],a=[1],m=[],g=[dict(t=2,s=[
            dict(s=0,i=0,l=[dict(m=0,t=1)]),
            dict(s=1,i=0,l=[dict(m=255,t=1)])])])
        self.assertEqual(image_capacities(source),[1])

    def test_cycle_and_frame_overflow_rejected(self):
        source=self.source();source['g'][0]['s'][0]['i']=0
        with self.assertRaisesRegex(ValueError,'cycle'):image_capacities(source)
        source=self.source();source['g'][1]['s'][0]['l'][0]['t']=3
        with self.assertRaisesRegex(ValueError,'frame'):image_capacities(source)


if __name__=='__main__':unittest.main()
