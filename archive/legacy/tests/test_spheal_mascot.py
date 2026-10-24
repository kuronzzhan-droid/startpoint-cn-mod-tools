"""海豹球候选集成检查：在有本地候选包时运行，不依赖服务器/模拟器。"""
import json
import sys
import unittest
from pathlib import Path

pass  # Imports resolve from this checkout/package, not external source copies.
import wf_seasonal7_common as C
import wf_client_legality
import wf_character_workspace as W

WORKSPACE = Path(__file__).resolve().parents[2] / "work/character_packs/spheal-mascot-20260919"


@unittest.skipUnless((WORKSPACE / "evidence/spheal-media.json").exists(), "需要本地海豹球候选")
class SphealCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from wf_spheal_mascot import context
        cls.pack = context()

    def rows(self, logical, key):
        return C.csv_split(self.pack.pkg_flat(logical)[key])

    def test_energy_all_levels(self):
        lg = "master/skill/action_skill.orderedmap"
        table = C.core.load_nested_table_bytes(self.pack.pkg_path("common",lg).read_bytes(),lg)
        for text in table.rows["spheal_mascot"].text_rows().values():
            row = C.csv_split(text)[0]
            self.assertEqual(row[4:6], ["250", "250"])

    def test_leader_only_local_charge(self):
        rows = self.rows("master/ability/leader_ability.orderedmap", "129990")
        charges = [r for r in rows if r[45] == "211"]
        self.assertEqual(len(charges),1)
        self.assertEqual([charges[0][25],charges[0][46],charges[0][49],charges[0][50]],
                         ["0","5","100000","100000"])
        for lg in self.pack.pkg_dsl_programs():
            self.assertFalse(C.commands(C.amf_parse(self.pack.pkg_path("common",lg).read_bytes()), "AddSkillPoint"))

    def test_global_attack_is_eternal_and_does_not_stack(self):
        tree = C.amf_parse(self.pack.pkg_path("common", "battle/action/skill/ability/ability_skill_spheal_mascot_leader.action.dsl.amf3.deflate").read_bytes())
        commands = C.commands(tree,"CreateCondition")
        self.assertEqual({c[1] for c in commands},{1,-33})
        for command in commands:
            effect = command[2][0]
            self.assertEqual(effect[0], "ACAttackPoint")
            self.assertEqual(effect[1],[{"min":99999,"max":99999}])
            self.assertEqual(effect[2:],[ [{"min":1,"max":1}], [{"min":1,"max":1}] ])
            self.assertFalse(command[5])

    def test_party_targets_use_native_absent_group_sentinel(self):
        # Blank is Some([]), which renders null and is not unrestricted Party(None).
        leader = self.rows("master/ability/leader_ability.orderedmap", "129990")
        charge = next(r for r in leader if r[45] == "211")
        hp = self.rows("master/ability/ability.orderedmap", "1299903")[0]
        self.assertEqual(charge[46:48], ["5", "(None)"])
        self.assertEqual(hp[48:50], ["5", "(None)"])

    def test_mascot_abilities_and_client_abi(self):
        rows=[self.rows("master/ability/ability.orderedmap",f"129990{i}")[0] for i in range(1,7)]
        self.assertEqual([r[47] for r in rows],["205","37","205","205","33","206"])
        self.assertEqual(rows[2][1],"false")
        self.assertEqual(rows[2][48],"5")
        self.assertEqual((rows[5][27],rows[5][34]),("23","5"))
        for r in rows:
            self.assertEqual(wf_client_legality.client_legality_problems("ability",r),[])

    def test_healing_skill_has_no_attack(self):
        for lg in self.pack.pkg_dsl_programs():
            if "/action/rare5/" not in lg:
                continue
            tree=C.amf_parse(self.pack.pkg_path("common",lg).read_bytes())
            self.assertFalse(C.commands(tree,"CreateNormalAttack"))
            heals=C.commands(tree,"CreateRatioHeal")
            self.assertEqual(len(heals),3)
            self.assertIn(-33,[h[1] for h in heals])
            self.assertTrue(all(h[3][0]["max"] <= .04 for h in heals))

    def test_portraits_and_pixels_are_own_media(self):
        from PIL import Image
        import numpy as np
        for i in range(2):
            image=Image.open(self.pack.evidence_path(f"masters/spheal-{i}.png"))
            self.assertEqual(image.mode,"RGBA")
            self.assertGreater(float((np.asarray(image)[:,:,3]==0).mean()),.1)
        report=self.pack.read_evidence("pixel-report.json")
        self.assertEqual(len(report["regular"]["sequences"]),9)
        self.assertEqual(len(report["special"]["sequences"]),2)

    def test_pixel_click_special_follows_native_playhead_contract(self):
        prefix="character/spheal_mascot/pixelart/"
        timeline=C.amf_parse(self.pack.pkg_path("common",prefix+"special.timeline.amf3.deflate").read_bytes())
        sequences=timeline["sequences"]
        # Four/five-star PixelArtCharacter calls special_land, then special_pose.
        self.assertEqual([(s["name"],s["kind"]) for s in sequences],
                         [("special_land","pass"),("special_pose","once")])
        atlas=C.amf_parse(self.pack.pkg_path("common",prefix+"special_sprite_sheet.atlas.amf3.deflate").read_bytes())
        frame=C.amf_parse(self.pack.pkg_path("common",prefix+"special.frame.amf3.deflate").read_bytes())
        from PIL import Image
        sheet=C.png_open(self.pack.pkg_path("common",prefix+"special_sprite_sheet.png").read_bytes())
        names={entry["n"] for entry in atlas}
        for sequence in sequences:
            self.assertIn(f'{frame["name"]}{sequence["begin"]:04d}',names)
            self.assertGreaterEqual(sequence["end"],sequence["begin"])
        self.assertEqual(sequences[1]["begin"],sequences[0]["end"]+1)
        for entry in atlas:
            self.assertLessEqual(entry["x"]+entry["w"],sheet.width)
            self.assertLessEqual(entry["y"]+entry["h"],sheet.height)
        regular=C.amf_parse(self.pack.pkg_path("common",prefix+"pixelart.timeline.amf3.deflate").read_bytes())
        kinds={s["name"]:s["kind"] for s in regular["sequences"]}
        self.assertEqual([kinds[n] for n in ("into_coffin","ghost_raise")],["pass","pass"])

    def test_before_and_after_have_safe_speech(self):
        rows=self.rows("master/character/character_speech.orderedmap","129990")
        self.assertEqual({r[1] for r in rows if r[0]=="0"},{"0","1"})
        self.assertTrue(all(r[4]=="(None)" for r in rows))
        self.assertFalse(list(self.pack.pkg_path("common","character/spheal_mascot/voice").glob("**/*.mp3")))

    def test_join_and_evolution_speeches_resolve_without_c2265(self):
        # CharacterSpeechRepository.getJoinSpeech requires kind=2;
        # getSpecificEvolutionSpeech(1) requires kind=1, column 2=1.
        # Two Home rows alone pass asset checks but crash first acquisition.
        rows=self.rows("master/character/character_speech.orderedmap","129990")
        joins=[r for r in rows if r[0]=="2"]
        evolutions=[r for r in rows if r[0]=="1" and r[2]=="1"]
        self.assertEqual(len(joins),1,"C2265: missing join speech")
        self.assertEqual(len(evolutions),1,"C2265: missing evolution speech")
        for row in joins+evolutions:
            self.assertTrue(row[3].strip())
            self.assertEqual(row[4],"(None)")

    def test_required_assets_and_three_layers(self):
        status=W.workspace_status(W.load_workspace(WORKSPACE),persist=False)
        self.assertEqual(status.requirement_report["required_present"],37)
        self.assertFalse(status.manifest_errors)
        self.assertTrue(status.three_layer_claim_status["consistent"])


if __name__ == "__main__":
    unittest.main()
