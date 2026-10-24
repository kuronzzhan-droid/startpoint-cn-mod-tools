"""Pixelart overlays preserve body pixels, action timing and atlas geometry."""
import importlib
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    pixel = importlib.import_module("wf_pixelart_vfx")
except ModuleNotFoundError:
    pixel = None


class PixelartVfxTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(pixel, "pixelart VFX implementation is missing")

    def test_restore_rotated_crop_and_negative_trim_offsets(self):
        # Independent Starling UV oracle: local TL samples stored TR, while
        # local BR samples stored BL (u,v -> 1-v,u). No inverse helper here.
        stored = Image.new("RGBA", (3, 2))
        stored.putpixel((2, 0), (255, 0, 0, 255))
        stored.putpixel((0, 1), (0, 255, 0, 128))
        entry = dict(n="p0001", x=0, y=0, w=3, h=2, r=True,
                     fx=-2, fy=-1, fw=8, fh=8)
        restored = pixel.restore_frame(stored, entry)
        self.assertEqual(restored.getpixel((2, 1)), (255, 0, 0, 255))
        self.assertEqual(restored.getpixel((3, 3)), (0, 255, 0, 128))
        self.assertEqual(restored.size, (8, 8))

    def test_bad_crop_and_frame_offsets_fail_closed(self):
        sheet = Image.new("RGBA", (4, 4))
        for entry in [dict(x=3,y=0,w=2,h=2),
                      dict(x=0,y=0,w=2,h=2,fx=-4,fy=0,fw=4,fh=4)]:
            with self.assertRaises(ValueError):
                pixel.restore_frame(sheet, entry)

    def test_sparse_suffix_is_inclusive_endpoint_like_flatomo(self):
        entries = [dict(n="p0002", value="a"), dict(n="p0005",value="b")]
        index = pixel.frame_index(entries, "p")
        # FrameAnimationSource.as: while (filled < suffix) imageFrames[filled++]=i.
        oracle = []
        for entry in entries:
            endpoint = int(entry["n"][1:])
            while len(oracle) < endpoint:
                oracle.append(entry["value"])
        self.assertEqual([pixel.entry_for_frame(index, f)["value"] for f in range(1,6)],
                         oracle)
        self.assertEqual(oracle,["a", "a", "b", "b", "b"])
        for frame in (0,6):
            with self.assertRaises(ValueError):
                pixel.entry_for_frame(index,frame)
        with self.assertRaises(ValueError):
            pixel.frame_index(entries + [entries[0]], "p")

    def test_nonrotated_crop_preserves_pixels_and_trim(self):
        sheet = Image.new("RGBA",(3,2))
        sheet.putdata([(i,i*2,i*3,100+i) for i in range(6)])
        entry = dict(x=0,y=0,w=3,h=2,fx=-1,fy=-2,fw=6,fh=6)
        restored = pixel.restore_frame(sheet,entry)
        self.assertEqual(restored.crop((1,2,4,4)).tobytes(),sheet.tobytes())

    def test_background_overlay_keeps_every_nontransparent_body_pixel(self):
        body = Image.new("RGBA", (8,8))
        body.putpixel((4,3), (20,40,60,255))
        body.putpixel((4,4), (10,15,20,90))
        effect = Image.new("RGBA", (8,8), (0,200,255,180))
        result = pixel.overlay_behind(body, effect, (0,0), 0.5)
        for xy in [(4,3),(4,4)]:
            self.assertEqual(result.getpixel(xy), body.getpixel(xy))
        self.assertGreater(result.getpixel((0,0))[3], 0)

    def test_overlay_does_not_modify_unselected_frames_or_timing(self):
        frames = [Image.new("RGBA", (8,8)) for _ in range(6)]
        for im in frames:
            im.putpixel((4,4),(100,100,100,255))
        timeline = {"sequences":[dict(name="neutral",begin=1,end=1,kind="loop"),
                                  dict(name="walk",begin=2,end=3,kind="loop"),
                                  dict(name="skill_ready",begin=4,end=6,kind="once")]}
        effect = Image.new("RGBA", (4,4))
        effect.putpixel((0,0),(0,200,255,255))
        out, report = pixel.animate_overlays(frames,[effect],timeline,{"skill_ready"},4,0.5)
        self.assertEqual(len(out),6)
        self.assertEqual([x.tobytes() for x in out[:3]], [x.tobytes() for x in frames[:3]])
        self.assertEqual(report["body_pixels_changed"],0)
        self.assertEqual(report["actions"], ["skill_ready"])
        self.assertEqual(timeline["sequences"][2]["begin"],4)

    def test_rejects_effect_larger_than_source_canvas(self):
        image = Image.new("RGBA",(8,8))
        timeline={"sequences":[dict(name="pose",begin=1,end=1,kind="once")]}
        with self.assertRaises(ValueError):
            pixel.animate_overlays([image],[image],timeline,{"pose"},16,0.5)

    def _endpoint_source(self, root):
        """Sparse source: p0002/p0007 hold tile A, p0005 holds tile B."""
        from wf_generated_vfx import write_tree
        source = root/"source"
        source.mkdir()
        sheet = Image.new("RGBA",(4,2))
        sheet.putpixel((0,0),(255,0,0,255))   # tile A at x=0
        sheet.putpixel((2,1),(0,0,255,255))   # tile B at x=2
        sheet.save(source/"sprite_sheet.png")
        atlas = [dict(n="p0002",x=0,y=0,w=2,h=2,fx=-3,fy=-3,fw=8,fh=8),
                 dict(n="p0005",x=2,y=0,w=2,h=2,fx=-1,fy=-4,fw=8,fh=8),
                 dict(n="p0007",x=0,y=0,w=2,h=2,fx=-5,fy=-2,fw=8,fh=8)]
        frame = dict(name="p",x=-4,y=-4,scale=6,smoothing=False)
        timeline = {"sequences":[dict(name="neutral",begin=1,end=2,kind="loop"),
                                  dict(name="walk_front",begin=3,end=7,kind="loop")]}
        for name,tree in [("sprite_sheet.atlas",atlas),("pixelart.frame",frame),
                          ("pixelart.timeline",timeline)]:
            write_tree(source/(name+".amf3.deflate"),tree)
        effect = Image.new("RGBA",(4,4))
        effect.putpixel((0,0),(0,255,0,255))
        effect.save(root/"effect.png")
        return source, atlas, frame, timeline

    def test_atlas_keeps_source_endpoints_and_dedups_held_images(self):
        from wf_generated_vfx import read_image, read_tree
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source, atlas, frame, timeline = self._endpoint_source(root)
            # No action selected: every tick is the untouched source image, so the
            # pre-patch "one record per tick" expansion is an exact oracle here.
            report = pixel.assemble_pixelart(source,root/"effect.png",1,(4,4),root/"out",
                                             actions=[],vfx_size=4)
            new = read_tree(root/"out/sprite_sheet.atlas.amf3.deflate")
            self.assertEqual([e["n"] for e in new],["p0002","p0005","p0007"])
            self.assertEqual(report["source_atlas_entries"],3)
            self.assertEqual(report["output_atlas_entries"],3)
            # p0002 and p0007 hold the same tile from different canvas positions.
            self.assertEqual(report["output_atlas_rectangles"],2)
            rect = lambda e: (e["x"],e["y"],e["w"],e["h"])
            self.assertEqual(rect(new[0]),rect(new[2]))
            self.assertNotEqual(rect(new[0]),rect(new[1]))
            self.assertNotEqual((new[0]["fx"],new[0]["fy"]),(new[2]["fx"],new[2]["fy"]))
            self.assertEqual([(e["fw"],e["fh"]) for e in new],[(8,8)]*3)
            # Every tick 1..7 still resolves to the exact source pixels.
            old_index = pixel.frame_index(atlas,frame["name"])
            new_index = pixel.frame_index(new,frame["name"])
            old_sheet = read_image(source/"sprite_sheet.png")
            new_sheet = read_image(root/"out/sprite_sheet.png")
            total = max(s["end"] for s in timeline["sequences"])
            for tick in range(1,total+1):
                expanded = pixel.restore_frame(old_sheet,pixel.entry_for_frame(old_index,tick))
                packed = pixel.restore_frame(new_sheet,pixel.entry_for_frame(new_index,tick))
                self.assertEqual(packed.tobytes(),expanded.tobytes(),f"tick {tick}")

    def test_endpoints_are_clamped_to_the_timeline_and_frame_documents_untouched(self):
        from wf_generated_vfx import read_tree, write_tree
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source, _, _, timeline = self._endpoint_source(root)
            # The timeline stops at 6 while the source atlas still holds a p0007
            # record: the last record must be renumbered, never left dangling.
            timeline["sequences"][1]["end"] = 6
            write_tree(source/"pixelart.timeline.amf3.deflate",timeline)
            pixel.assemble_pixelart(source,root/"effect.png",1,(4,4),root/"out",
                                    actions=[],vfx_size=4)
            new = read_tree(root/"out/sprite_sheet.atlas.amf3.deflate")
            self.assertEqual([e["n"] for e in new],["p0002","p0005","p0006"])
            self.assertEqual((source/"pixelart.timeline.amf3.deflate").read_bytes(),
                             (root/"out/pixelart.timeline.amf3.deflate").read_bytes())

    def test_assembly_preserves_documents_and_restored_body_after_repacking(self):
        from wf_generated_vfx import read_tree, write_tree
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            source=root/"source"
            source.mkdir()
            sheet=Image.new("RGBA",(2,2))
            sheet.putpixel((0,0),(255,0,0,100))
            sheet.save(source/"sprite_sheet.png")
            stored=source/"sprite_sheet.png"
            stored.write_bytes(b"\x89png\r\n\x1a\n"+stored.read_bytes()[8:])
            atlas=[dict(n="p0005",x=0,y=0,w=2,h=2,fx=-3,fy=-3,fw=8,fh=8)]
            frame=dict(name="p",x=-4,y=-4,scale=6,smoothing=False)
            timeline={"sequences":[dict(name="neutral",begin=1,end=1,kind="loop"),
                                    dict(name="skill_ready",begin=2,end=5,kind="once")]}
            for name,tree in [("sprite_sheet.atlas",atlas),("pixelart.frame",frame),
                              ("pixelart.timeline",timeline)]:
                write_tree(source/(name+".amf3.deflate"),tree)
            effect=Image.new("RGBA",(4,4))
            effect.putpixel((0,0),(0,255,0,255))
            effect.save(root/"effect.png")
            report=pixel.assemble_pixelart(source,root/"effect.png",1,(4,4),root/"out",
                                          vfx_size=4)
            for name in ("pixelart.frame","pixelart.timeline"):
                filename=name+".amf3.deflate"
                self.assertEqual((source/filename).read_bytes(),(root/"out"/filename).read_bytes())
            self.assertEqual(report["frame_count"],5)
            newatlas=read_tree(root/"out/sprite_sheet.atlas.amf3.deflate")
            with Image.open(root/"out/sprite_sheet.png") as packed:
                for entry in newatlas:
                    self.assertEqual(pixel.restore_frame(packed,entry).getpixel((3,3)),(255,0,0,100))


if __name__ == "__main__":
    unittest.main()
