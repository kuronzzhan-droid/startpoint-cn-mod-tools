"""玩法候选修订必须保留无关原始行、立绘和语音，并拒绝输入漂移。"""
import json
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

pass  # Imports resolve from this checkout/package, not external source copies.
import wf_bianca_dragon_package as package
import wf_mod_tool as core


class CandidateGuardsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.ws = self.repo / "work/character_packs/bianca"
        self.table = "master/ability/ability.orderedmap"
        (self.ws / "evidence").mkdir(parents=True)
        roots = {name: [] for name in ("common", "medium", "android", "server")}
        for name in roots:
            (self.ws / "package/roots" / name).mkdir(parents=True)
        (self.repo / "mod-tools").mkdir()
        (self.repo / "mod-tools/profiles.json").write_text(
            json.dumps({"profiles": {"cn": {"store": "store"}}}), encoding="utf-8")
        (self.ws / "workspace.json").write_text(json.dumps(dict(
            schema_version=1, character_id=119989, code_name=package.CODE,
            package_dir="package", package_id="bianca-test", template_character_id=111021)),
            encoding="utf-8")
        # 非自有行故意使用另一压缩级别，验证不能以“语义相同”重编码整表。
        self.foreign = zlib.compress(b"do-not-touch,7", 1)
        raw = core.build_orderedmap_raw_rows(core.OrderedMap(
            logical_path=self.table, source_path=Path("<memory>"),
            keys=["1110211", "1199891"], rows=[self.foreign, zlib.compress(b"old,1")]))
        self.add_file(roots, "common", self.table, raw)
        self.add_file(roots, "medium", "character/lady_summoner_campus/ui/full_shot.png", b"portrait")
        manifest = dict(character_id=119989, code_name=package.CODE, roots=roots,
                        tables=[dict(root="common", logical_path=self.table, codec_id="flat",
                                     outer_keys=["1199891"], inner_keys=[], semantic_claims=[])],
                        qa={}, snapshot={}, package_version="0.1.0")
        (self.ws / "package/manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        self.baseline = patch.object(package, "OfficialBaseline")
        self.baseline.start()
        self.addCleanup(self.baseline.stop)

    def add_file(self, roots, tier, logical, raw):
        path = self.ws / "package/roots" / tier / logical
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        roots[tier].append(dict(logical_path=logical, sha256=package.digest(raw), size=len(raw)))

    def test_foreign_row_keeps_original_compressed_bytes(self):
        candidate = package.Candidate(self.repo, self.ws)
        candidate.splice(self.table, {"1199891": [["new", "50"]], "11998990": [["support"]]})
        candidate.finish({}, apply=True)
        table = core.read_orderedmap_raw_rows_from_bytes(
            candidate.path("common", self.table).read_bytes(), self.table)
        self.assertEqual(table.rows[table.keys.index("1110211")], self.foreign)
        self.assertEqual(zlib.decompress(table.rows[table.keys.index("11998990")]), b"support")

    def test_foreign_existing_and_new_keys_are_rejected(self):
        candidate = package.Candidate(self.repo, self.ws)
        for key in ("1110211", "16998999"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                candidate.splice(self.table, {key: [["unowned"]]})

    def test_portrait_change_is_rejected(self):
        candidate = package.Candidate(self.repo, self.ws)
        candidate.emit("medium", "character/lady_summoner_campus/ui/full_shot.png", b"changed")
        with self.assertRaisesRegex(ValueError, "protected presentation"):
            candidate.finish({})

    def test_concurrent_input_change_stops_write(self):
        candidate = package.Candidate(self.repo, self.ws)
        candidate.splice(self.table, {"1199891": [["new"]]})
        candidate.path("common", self.table).write_bytes(b"other writer")
        with self.assertRaisesRegex(ValueError, "candidate changed after plan"):
            candidate.finish({}, apply=True)
        self.assertEqual(candidate.path("common", self.table).read_bytes(), b"other writer")


if __name__ == "__main__":
    unittest.main()
