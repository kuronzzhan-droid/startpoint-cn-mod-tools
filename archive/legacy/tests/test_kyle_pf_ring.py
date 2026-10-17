"""Native mechanics and Flatomo failure guards for Kyle's scoped PF replacement."""
import copy
import sys
import unittest
import zlib
from pathlib import Path

pass  # Imports resolve from this checkout/package, not external source copies.
import wf_dsl
import wf_client_legality as legality
import wf_kyle_pf_effect as F
import wf_kyle_pf_ring as P
import wf_kyle_pf_quick as Q
import wf_kyle_pf_hit as H
import wf_mod_tool as core
import wf_seasonal7_common as C
from wf_seasonal7_kit_zehr import apk_pf_sources


class RingAnimationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = core.project_root() / F.SOURCE
        cls.raw = (cls.source / F.PARTS).read_bytes()
        cls.original = C.amf_parse(cls.raw)

    def test_birth_fade_and_once_timeline_fit_all_hit_windows(self):
        for lifetime in F.LIFETIMES:
            parts, timeline = F.native_animation(lifetime)
            self.assertEqual(parts['g'][0]['t'], lifetime)
            self.assertEqual(timeline['sequences'], [dict(begin=1,end=lifetime,name='neutral',kind='once')])
            keys = parts['g'][0]['s'][0]['l']
            self.assertEqual(keys[0]['m'] & 255, 0)
            self.assertEqual(keys[-1]['m'] & 255, 0)
            self.assertEqual(sum(k['t'] & 65535 for k in keys), lifetime)

    def test_original_perspective_and_custom_curves_are_unchanged(self):
        for lifetime in F.LIFETIMES:
            parts, _ = F.native_animation(lifetime)
            self.assertEqual(parts['t'], self.original['t'])
            self.assertEqual(parts['c'], self.original['c'])
            self.assertEqual(len(parts['g']), len(self.original['g']))
            self.assertEqual({k['m'] >> 12 for k in parts['g'][0]['s'][0]['l']}, {0})

    def test_front_back_arcs_and_electric_layers_keep_independent_tweens(self):
        for lifetime in F.LIFETIMES:
            parts, _ = F.native_animation(lifetime)
            for group in (37,38,45,46,48,50,57,58,63,65):
                old=self.original['g'][group]['s']; new=parts['g'][group]['s']
                self.assertEqual(len(old),len(new))
                for a,b in zip(old,new):
                    self.assertEqual([k['m'] for k in a['l']],[k['m'] for k in b['l']])
                    self.assertEqual([int(k.get('t') or 1) & ~65535 for k in a['l']],
                                     [k['t'] & ~65535 for k in b['l']])

    def test_orb_images_and_central_charge_are_removed(self):
        parts,_=F.native_animation(F.LIFETIMES[2])
        self.assertTrue({i['p'].split('/')[-1]for i in parts['i']} <= F.KEEP)
        self.assertEqual(len(parts['g'][1]['s']),1)
        self.assertEqual(parts['g'][1]['s'][0]['i'],11)
        for group in (18,20,22,24,26,28,30,42,55):
            # These official direct-image groups carried the removed orb layers.
            for strip in parts['g'][group]['s']:
                self.assertNotEqual((int(strip['s']) & 0xffffffff) >> 30, 0)

    def test_native_pools_cover_every_live_nested_instance(self):
        for lifetime in F.LIFETIMES:
            parts,_=F.native_animation(lifetime)
            self.assertEqual(parts['a'], F.capacity.validate_image_capacities(parts))
            self.assertGreater(max(parts['a']), 1)
            self.assertTrue(all(n > 0 for n in parts['a']))

    def test_packed_atlas_is_closed_and_keeps_native_sprite_frames(self):
        assets,note=F.build_assets(core.project_root())
        self.assertEqual(len(assets),10)
        atlas=C.amf_parse(assets[F.SHEET+'.atlas.amf3.deflate'])
        original=C.amf_parse((self.source/(F.DONOR+'.atlas.amf3.deflate')).read_bytes())
        old={i['n'].split('/')[-1]:i for i in original if '/.gen/starbreak_hunter_meteor23_explosion/' in i['n']}
        for i in atlas:
            source=old[i['n'].split('/')[-1]]
            self.assertEqual((i['fw'],i['fh']),
                             (source.get('fw',source['h' if source.get('r') else 'w']),
                              source.get('fh',source['w' if source.get('r') else 'h'])))
        for level in (1,2,3):
            parts=C.amf_parse(assets[F.effect(level)+'.parts.amf3.deflate'])
            self.assertEqual({i['p'] for i in parts['i']},{i['n'] for i in atlas})
        self.assertFalse(note['whole_image_rotation'])
        self.assertLess(note['atlas_size'][0]*note['atlas_size'][1],60000)

    def test_source_alpha_and_brightness_are_preserved_after_api_palette_transfer(self):
        import io
        from PIL import Image, ImageChops
        import wf_assets
        old=Image.open(io.BytesIO(wf_assets.png_decode((self.source/(F.DONOR+'.png')).read_bytes()))).convert('RGBA')
        new=Image.open(self.source/'palette-atlas.png').convert('RGBA')
        self.assertEqual(old.size,new.size)
        self.assertIsNone(ImageChops.difference(old.getchannel('A'),new.getchannel('A')).getbbox())
        def value(im):
            r,g,b,_=im.split()
            return ImageChops.lighter(ImageChops.lighter(r,g),b)
        self.assertIsNone(ImageChops.difference(value(old),value(new)).getbbox())

    def test_invalid_lifetime_level_and_donor_are_rejected(self):
        with self.assertRaises(ValueError): F.native_animation(999)
        with self.assertRaises(ValueError): F.effect(4)
        with self.assertRaises(ValueError): F.filtered_native(b'corrupt')

    def test_residue_is_a_finite_electric_layer_and_reuses_existing_sheet(self):
        assets,note=F.build_assets(core.project_root())
        parts=C.amf_parse(assets[H.effect(F.DIRECTORY)+'.parts.amf3.deflate'])
        self.assertEqual(parts['g'][0]['t'],39)
        self.assertEqual(parts['g'][0]['s'][0]['i'],57)
        keys=parts['g'][0]['s'][0]['l']
        self.assertEqual((keys[0]['m'] & 255,keys[-1]['m'] & 255),(0,0))
        self.assertEqual(sum(k['t'] & 65535 for k in keys),39)
        self.assertEqual(parts['a'],F.capacity.validate_image_capacities(parts))
        self.assertEqual(sum(p.endswith('.png')for p in assets),1)


class SwordMechanicsTests(unittest.TestCase):
    def test_extended_contact_window_keeps_the_ten_frame_damage_burst(self):
        for level, lifetime in enumerate((60, 68, 75), 1):
            tree = P.build_tree(self.sources[f'knight_lv{level}'], level)
            outer, inner = Q.commands(tree, 'CreateHitArea')
            self.assertEqual(outer[13][1], lifetime)
            self.assertEqual(Q.commands(tree, 'SetPowerFilpSuppress')[0][1], lifetime)
            self.assertEqual(inner[13][1], 10)
            self.assertEqual(inner[15][1][0]['min'], (3, 4, 5)[level-1])

    @classmethod
    def setUpClass(cls):
        cls.sources, _ = apk_pf_sources(core.project_root())

    def test_all_three_levels_preserve_native_end_notification(self):
        for level in (1, 2, 3):
            raw = self.sources[f'knight_lv{level}']
            original = wf_dsl.parse_dsl(zlib.decompress(raw, -15))['tree']
            tree = P.build_tree(raw, level)
            P.verify_tree(tree, original, level)
            self.assertEqual(list(wf_dsl.iter_dsl_commands(tree,'SetPowerFilpSuppress')),
                             [['SetPowerFilpSuppress',F.LIFETIMES[level-1]]])
            self.assertEqual(len(list(wf_dsl.iter_dsl_commands(tree,'NotifyPowerflipEnd'))),1)

    def test_outer_contact_triggers_only_once_per_target(self):
        for level in (1,2,3):
            tree=P.build_tree(self.sources[f'knight_lv{level}'],level)
            outer,inner=Q.commands(tree,'CreateHitArea')
            self.assertEqual(outer[14:16],[['CalculatedUsingMaxNumOfHits',1],['Some',[{'min':1,'max':1}]]])
            self.assertEqual(inner[13],['SpecifyHitAreaLifetimeDirectly',10])
            self.assertEqual(inner[14],['CalculatedUsingMaxNumOfHits',Q.HITS[level-1]])
            self.assertEqual(inner[15],['Some',[{'min':Q.HITS[level-1],'max':Q.HITS[level-1]}]])
            self.assertEqual((outer[24],inner[24]),(104,104))

    def test_burst_keeps_original_per_hit_damage_and_number(self):
        for level in (1,2,3):
            raw=self.sources[f'knight_lv{level}']
            old=wf_dsl.parse_dsl(zlib.decompress(raw,-15))['tree']
            tree=P.build_tree(raw,level)
            before=Q.commands(old,'CreateNormalAttack')[0]
            after=copy.deepcopy(Q.commands(tree,'CreateNormalAttack')[0]);self.assertEqual(after[1],7)
            after[1]=before[1];self.assertEqual(after,before)
            self.assertEqual(Q.commands(old,'CreateHitArea')[0][14][1],Q.HITS[level-1])

    def test_native_interval_accumulator_finishes_burst_within_ten_frames(self):
        # ActionHitAreaGroup allows a hit when residual interval < 1, preserves
        # fractional residual, then the manager decrements it once per frame.
        for hits,want in [(3,[0,4,8]),(4,[0,2,5,8]),(5,[0,2,4,6,8])]:
            remaining=0;actual=[]
            for frame in range(10):
                if remaining<1 and len(actual)<hits:
                    actual.append(frame);remaining=max(0,remaining)+10/(hits-.5)
                remaining-=1
            self.assertEqual(actual,want)

    def test_only_pf3_shrinks_and_perspective_plane_does_not_follow_heading(self):
        for level,radius,scale in [(1,140,2.8),(2,160,3.2),(3,238,4.76)]:
            tree=P.build_tree(self.sources[f'knight_lv{level}'],level)
            outer=Q.commands(tree,'CreateHitArea')[0];show=Q.commands(outer[20],'ShowEffect')[0]
            self.assertEqual(outer[9][1],[{'min':radius,'max':radius}])
            self.assertEqual(show[12],['Some',[{'min':scale,'max':scale}]])
            self.assertEqual(show[6],['AB']);self.assertEqual(show[10:12],[True,False])

    def test_all_levels_have_only_the_ring_and_no_impact_residue(self):
        for level in (1,2,3):
            tree=P.build_tree(self.sources[f'knight_lv{level}'],level)
            outer=Q.commands(tree,'CreateHitArea')[0]
            self.assertEqual(Q.commands(outer[23],'ShowEffect'),[])
            effects=Q.commands(tree,'ShowEffect')
            self.assertEqual(len(effects),1)
            self.assertEqual(effects[0][2],['SpecifyEffectDirectly',F.effect(level)])
            self.assertFalse(Q.commands(tree,'CreateCondition'))

    def test_celtie_contact_reference_points_remain_stationary(self):
        for level in (1,2,3):
            tree=P.build_tree(self.sources[f'knight_lv{level}'],level)
            first,second=Q.commands(tree,'CreateReferencePoint')
            self.assertEqual(first[1:8],[-18,['GH',2],0,-Q.RADII[level-1],0,False,False])
            self.assertEqual(first[9:11],[15,3])
            self.assertEqual(second[1:11],[3,['AB'],0,0,0,False,False,['Single'],50,4])

    def test_native_donor_drift_is_not_silently_accepted(self):
        with self.assertRaises(ValueError): P.build_tree(b'corrupt', 1)

    def test_native_lookup_hit_targets_and_element_are_legal(self):
        for level in (1, 2, 3):
            tree=P.build_tree(self.sources[f'knight_lv{level}'],level)
            for checker in (legality.action_dsl_subject_binding_problems,
                            legality.action_dsl_lookup_scope_problems,
                            legality.action_dsl_hit_area_target_problems):
                self.assertEqual(checker(tree),[])
            self.assertEqual(legality.action_dsl_element_problems(tree,2),[])

    def test_accidental_damage_increase_is_rejected(self):
        raw=self.sources['knight_lv3']
        original=wf_dsl.parse_dsl(zlib.decompress(raw,-15))['tree']
        tree=P.build_tree(raw,3)
        list(wf_dsl.iter_dsl_commands(tree,'CreateNormalAttack'))[0][6][0]['max']=999
        with self.assertRaises(ValueError): P.verify_tree(tree,original,3)


if __name__ == '__main__': unittest.main()
