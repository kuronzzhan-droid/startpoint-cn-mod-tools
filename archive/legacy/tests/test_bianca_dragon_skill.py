"""协力幼龙分支、标记结算顺序和像素来源的回归约束。"""
import io
import math
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

pass  # Imports resolve from this checkout/package, not external source copies.

from PIL import Image

import wf_assets
import wf_dsl
import wf_bianca_dragon_skill as skill
import wf_bianca_dragon_pixels as pixels
import wf_character_pack as character_pack
import wf_client_legality as client_legality
from wf_campus_bianca_data import validate_skill, walk_commands
from wf_dsl_sig import COMMANDS
from wf_pixelart_vfx import entry_for_frame, frame_index, restore_frame


def commands(tree):
    return list(walk_commands(tree))


class DragonSkillTests(unittest.TestCase):
    def test_exact_owned_dragon_and_recall_only_when_absent(self):
        tree = skill.build_skill(2)
        selector = next(c for c in commands(tree) if c[0] == "FindMultiballSubjects")
        self.assertEqual(selector[1:5], [10, 11, True, [1199891]])
        absent, present = selector[5:7]
        self.assertEqual(sum(c[0] == "CreateSummonsMultiball" for c in commands(absent)), 1)
        self.assertFalse(any(c[0] == "CreateSummonsMultiball" for c in commands(present)))
        self.assertFalse(any(c[0] == "CreateCondition" and c[2][0][0] == "ACInvincible"
                             for c in commands(absent)))
        remove = next(c for c in commands(present) if c[0] == "RemoveMultiball")
        self.assertEqual(remove, ["RemoveMultiball", True, [1199891]])

    def test_support_damage_has_time_to_resolve_before_removal(self):
        tree = skill.build_skill(2)
        present = next(c for c in commands(tree) if c[0] == "FindMultiballSubjects")[6]
        breath = next(node[1] for node in present[1] if node[0] == "Event")
        self.assertEqual(breath[0:2], ["Wait", 24])
        actions = breath[3][1]
        guard = actions[-2][1]
        self.assertEqual(guard[:6], ["FindMultiballSubjects", 10, 11, True, [1199891], ["Block", []]])
        self.assertEqual(guard[6][1][0][1][1:3], [11, [["ACUnique", 11998902, skill.value(1)]]])
        signal = actions[-1][1]
        self.assertEqual(signal[0:2], ["Wait", 1])
        self.assertEqual(signal[3][1][0][1][1], -17)
        self.assertEqual(len(signal[3][1]), 2)  # Self marker and Fever remain per cast.
        depart = present[1][-1][1]
        self.assertEqual(depart[0:2], ["Wait", 29])
        self.assertEqual(depart[3][1][0][1], ["RemoveMultiball", True, [1199891]])
        self.assertEqual(present[1][0], skill.command("RemoveEventFromOwner", "campus_dragon_depart"))
        self.assertFalse(any("Attack" in c[0] for c in commands(tree)))

    def test_native_timed_resists_and_top_down_breath(self):
        tree = skill.build_skill(2)
        cs = commands(tree)
        effects = [c for c in cs if c[0] == "CreateCondition"]
        status = {c[2][0][0]: c[2][0] for c in effects if c[2][0][0] != "ACUnique"}
        self.assertEqual(status["ACAttackPoint"][1:], [skill.value(900), skill.value(-.2), skill.value(1)])
        self.assertEqual(status["ACToleranceOfElement"][1:], [skill.value(900), 1, skill.value(-.25), skill.value(1)])
        self.assertEqual(status["ACAbilityDamageResistance"][1:], [skill.value(900), skill.value(-.2), skill.value(1)])
        enhanced = next(c for c in cs if c[0] == "ConditionalsChangeSkillFlag")
        self.assertEqual(enhanced[1], 1)
        self.assertTrue(any(c[0] == "CreateCondition" for c in commands(enhanced[2])))
        self.assertEqual(enhanced[3], ["Block", []])
        visual = next(c for c in cs if c[0] == "ShowEffect" and c[1] == "campus_dragon_descent")
        self.assertEqual(visual[9], math.pi)
        invincible = next(c for c in effects if c[2][0][0] == "ACInvincible")
        self.assertEqual(invincible[1], 11)
        self.assertEqual(invincible[2], [["ACInvincible", skill.value(60)]])
        self.assertTrue(invincible[-1])
        self.assertEqual(sum(c[-1] is True for c in effects), 1)
        ascent = next(c for c in cs if c[0] == "MoveHitArea")
        self.assertEqual(ascent[1:5], [12, ["AB"], 0, 120])
        self.assertFalse(any(c[0] == "MoveBall" for c in cs))

    def test_activation_marks_member_and_does_not_expire_in_fifteen_seconds(self):
        summon = next(c for c in commands(skill.build_skill(1)) if c[0] == "CreateSummonsMultiball")
        self.assertEqual(summon[1:4], [1, 1199891, skill.value(2147483647)])
        mark = summon[12][1][0][1]
        self.assertEqual(mark[1:3], [-17, [["ACUnique", 11998901, skill.value(1)]]])
        selector = next(c for c in commands(skill.build_skill(1)) if c[0] == "FindMultiballSubjects")
        self.assertEqual(selector[5][1][:4], [skill.command("RemoveEventFromOwner", name)
            for name in ("campus_dragon_breath_begin", "campus_dragon_breath_signal",
                         "campus_dragon_depart", "campus_dragon_activated")])

    def test_both_levels_roundtrip_and_native_signatures(self):
        for level in (1, 2):
            tree = skill.build_skill(level)
            self.assertEqual(wf_dsl.parse_dsl(zlib.decompress(skill.amf_bytes(tree), -15))["tree"], tree)
            validate_skill(tree)
            for c in commands(tree):
                self.assertEqual(len(c)-1, len(COMMANDS[c[0]]), c[0])
        with self.assertRaises(ValueError):
            skill.build_skill(3)

    def test_multiball_data_has_private_body_and_support(self):
        donor = ["original", "original", "5", "0", "Mystery", "", "1", "Unknown", "false", "(None)"] + [""]*10 + ["(None)"]*4 + ["1", "0", "false", "false"]
        level = [["curve", "304", "1", "curve", "455", "1"]]
        result = skill.build_multiball_tables({"1111711": [donor]}, {"1111711": level})
        row = result["master/battle/multiball/multiball.orderedmap"]["1199891"][0]
        self.assertEqual(row[1], "lady_summoner_campus_dragon")
        self.assertEqual(row[3:5], ["0", "Dragon"])
        self.assertEqual(row[20:24], ["11998991", "(None)", "(None)", "(None)"])
        self.assertEqual(donor[0], "original")
        actual_level = result["master/battle/multiball/multiball_level.orderedmap"]["1199891"][0]
        self.assertEqual(actual_level, ["curve", "5000", "0.15151515151515152",
                                        "curve", "5000", "0.15151515151515152"])
        self.assertEqual(level, [["curve", "304", "1", "curve", "455", "1"]])
        self.assertEqual(len(result), 2)  # 复用已存在的成长曲线，不新增master依赖。
        # AS3 MultiballFactory以Number依次乘base、curve和correction，最后加两次eps取整。
        # 100级必须正好5000，不能直接把原表base设5000而长成33000，也不能舍入成4999。
        for curve, expected in ((.1, 75), (1, 757), (6, 4545), (6.6, 5000)):
            for basic_index in (1, 4):
                raw = int(actual_level[basic_index]) * curve * float(actual_level[basic_index + 1])
                self.assertEqual(math.floor(raw + 1e-10 + 1e-10), expected)
                if curve == 6.6:
                    self.assertEqual(raw, 5000.0)

    def test_pixel_frames_preserve_native_texels_and_have_collision(self):
        keys = sorted({k for seq in pixels.SEQUENCES.values() for k in seq}
                      | set(pixels.CALL_PARTICLE_KEYS + pixels.FLIGHT_POSES + pixels.DISAPPEAR_POSES))
        source = Image.new("RGBA", (len(keys)*12, 12))
        atlas = []
        originals = {}
        for index, key in enumerate(keys):
            tile = Image.new("RGBA", (10, 10), (index*17, 21, 127, 255))
            source.paste(tile, (index*12, 0)); originals[key] = tile
            atlas.append(dict(n="source/"+key, x=index*12, y=0, w=10, h=10))
        buf = io.BytesIO(); source.save(buf, format="PNG")
        fixture = {pixels.SOURCE+".png": wf_assets.png_encode(buf.getvalue()),
                   pixels.SOURCE+".atlas.amf3.deflate": skill.amf_bytes(atlas)}
        files, report = pixels.build_dragon_assets(fixture.__getitem__)
        prefix = "character/lady_summoner_campus_dragon/pixelart/"
        sheet = Image.open(io.BytesIO(wf_assets.png_decode(files["common", prefix+"sprite_sheet.png"])))
        def read(stem):
            return wf_dsl.parse_dsl(zlib.decompress(files["common", prefix+stem+".amf3.deflate"], -15))["tree"]
        idx = frame_index(read("sprite_sheet.atlas"), prefix+"pixelart")
        for item in report["frames"]:
            frame = restore_frame(sheet, entry_for_frame(idx, item["end"]))
            tile = frame.crop(frame.getchannel("A").getbbox())
            self.assertEqual(tile.tobytes(), originals[item["source"].rsplit("/", 1)[-1]].tobytes())
        timeline = read("pixelart.timeline")
        self.assertEqual(client_legality.pixelart_timeline_problems(timeline), [])
        self.assertEqual(report["ticks"], 216)
        self.assertEqual(len(timeline["sequences"]), 9)
        alpha_pixels = {tick: sum(alpha > 127 for alpha in
            restore_frame(sheet, entry_for_frame(idx, tick)).getchannel("A").get_flattened_data())
            for tick in range(1, report["ticks"]+1)}
        self.assertEqual(client_legality.pixelart_visibility_problems(timeline, alpha_pixels), [])
        # 调用生产preflight所用的实际package形状校验，避免仅检查本模块自建约束。
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory)
            logical = prefix + "pixelart.timeline.amf3.deflate"
            destination = package / "roots" / "common" / logical
            destination.parent.mkdir(parents=True)
            destination.write_bytes(files["common", logical])
            declared = [("common", logical, destination)]
            self.assertEqual(character_pack._client_asset_shape_errors({}, package, declared), [])
            # 旧的五段时间轴必须被同一个生产入口拒绝。
            broken = dict(timeline, sequences=timeline["sequences"][:5])
            destination.write_bytes(skill.amf_bytes(broken))
            self.assertTrue(character_pack._client_asset_shape_errors({}, package, declared))
        self.assertFalse(report["pixel_content_changed"])
        # 每个演出图层都必须命中本包原龙atlas，不能隐含借入海盗等外观。
        fx_atlas_path = skill.CALL_EFFECT + "campus_bianca_dragon_call.atlas.amf3.deflate"
        fx_atlas = wf_dsl.parse_dsl(zlib.decompress(files["common", fx_atlas_path], -15))["tree"]
        names = {entry["n"] for entry in fx_atlas}
        parts_count = 0
        for (_, logical), raw in files.items():
            if logical.endswith(".parts.amf3.deflate"):
                parts = wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]
                self.assertTrue({entry["p"] for entry in parts["i"]} <= names)
                self.assertEqual(parts["t"][0]["a"], 6*4096)
                parts_count += 1
        self.assertEqual(parts_count, 6)

    def test_idle_uses_selected_frames_and_spawn_particles_exclude_the_dragon(self):
        for sequence in ("neutral", "walk_front", "walk_back", "kachidoki", "ghost_neutral"):
            self.assertEqual(("as",) * 4, pixels.SEQUENCES[sequence])
        actor_keys = {key for sequence in pixels.SEQUENCES.values() for key in sequence}
        self.assertTrue(actor_keys.isdisjoint(pixels.CALL_PARTICLE_KEYS))
        keys = sorted(actor_keys | set(pixels.CALL_PARTICLE_KEYS + pixels.FLIGHT_POSES + pixels.DISAPPEAR_POSES))
        tiles = {key: Image.new("RGBA", (8, 8), (index * 11, 80, 160, 255))
                 for index, key in enumerate(keys)}
        files = pixels.build_call_effects(tiles)
        stem = skill.CALL_EFFECT + "campus_bianca_dragon_call"
        sheet = Image.open(io.BytesIO(wf_assets.png_decode(files["common", stem + ".png"])))
        atlas = wf_dsl.parse_dsl(zlib.decompress(
            files["common", stem + ".atlas.amf3.deflate"], -15))["tree"]
        particles = {tiles[key].tobytes() for key in pixels.CALL_PARTICLE_KEYS}
        summon = [entry for entry in atlas if any(part in entry["n"] for part in
                  ("effect_ready_generation/", "effect_ready_left/", "effect_ready_right/", "effect_appear/"))]
        self.assertEqual(16, len(summon))
        for entry in summon:
            self.assertIn(restore_frame(sheet, entry).tobytes(), particles)


if __name__ == "__main__":
    unittest.main()
