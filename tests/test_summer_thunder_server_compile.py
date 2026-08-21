import json
import unittest
from copy import deepcopy

from wf_character_pack import SERVER_LOGICAL_PATHS, TableClaim
from wf_release import JsonObjectCodec

try:
    from wf_summer_thunder_server_compile import (
        CHARACTER_ID,
        SERVER_PATHS,
        compile_summer_thunder_server_files,
    )
except ImportError:
    CHARACTER_ID = None
    SERVER_PATHS = None
    compile_summer_thunder_server_files = None


def _encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()


def _mana_nodes():
    def node(index):
        return {
            "field1": "0",
            "field5": "0",
            "field6": "1",
            "items": {"9": index},
            "manaCost": index,
        }

    return {
        "1": {str(279996200 + i): node(i) for i in range(1, 24)},
        "2": {str(279996400 + i): node(i) for i in range(1, 19)},
    }


CHARACTER_ROW = [
    "cnmod_thunder_dragon_ascendant", "1", "5", "2", "Dragon", "",
    "4", "Female", "cnmod_thunder_dragon_ascendant", "(None)", "", "",
    "", "", "", "", "", "139998", "碧海雷鸣的共振",
    "1399981", "1399982", "1399983", "1399984", "1399985", "1399986",
    "0", "Attacker", "231001", "(None)", "1", "false", "false", "0",
    "0", "1", "true", "6,6,6,6,6,6",
]

CHARACTER_TEXT_ROW = [
    "拉姆斯", "LAMUSI", "角色简介", "鸣彻碧海的雷龙", "碧海雷潮",
    "技能说明", "碧海雷潮＋", "技能说明", "(None)", "(None)",
    "碧海雷鸣的共振", "",
]


class SummerThunderServerCompileTests(unittest.TestCase):
    def _require_module(self):
        if compile_summer_thunder_server_files is None:
            self.fail("wf_summer_thunder_server_compile is missing")

    def _server_files(self):
        return {
            "character.json": _encoded({
                "1": {"name": "legacy", "rarity": 1, "element": 0,
                      "skill_count": 1},
                "139998": {"name": "拉姆斯", "rarity": 4, "element": 2,
                           "skill_count": 6},
            }),
            "mana_node.json": _encoded({
                "1": {"legacy": True},
                "139998": _mana_nodes(),
            }),
            "cdndata/character.json": _encoded({
                "1": [["legacy"]],
                "139998": [["old"]],
            }),
            "cdndata/character_text.json": _encoded({
                "1": [["legacy text"]],
                "139998": [["old text"]],
            }),
        }

    def test_compiler_replaces_only_target_and_preserves_remapped_mana(self):
        self._require_module()
        self.assertEqual("139998", str(CHARACTER_ID))
        self.assertEqual(
            {
                "character.json",
                "mana_node.json",
                "cdndata/character.json",
                "cdndata/character_text.json",
            },
            set(SERVER_PATHS),
        )
        character_rows = [CHARACTER_ROW]
        text_rows = [CHARACTER_TEXT_ROW]
        source = self._server_files()
        source_snapshot = deepcopy(source)
        result = compile_summer_thunder_server_files(
            source, character_rows=character_rows, character_text_rows=text_rows
        )

        self.assertEqual(source_snapshot, source)

        self.assertEqual(set(SERVER_PATHS), set(result["files"]))
        decoded = {
            path: json.loads(payload.decode("utf-8"))
            for path, payload in result["files"].items()
        }
        self.assertEqual(
            {"name": "拉姆斯", "rarity": 5, "element": 2, "skill_count": 6},
            decoded["character.json"]["139998"],
        )
        self.assertEqual(
            character_rows,
            decoded["cdndata/character.json"]["139998"],
        )
        self.assertEqual(
            text_rows,
            decoded["cdndata/character_text.json"]["139998"],
        )
        self.assertEqual(
            _mana_nodes(), decoded["mana_node.json"]["139998"]
        )
        for path in decoded:
            self.assertEqual(
                json.loads(source[path].decode("utf-8"))["1"], decoded[path]["1"]
            )

        report = result["report"]
        self.assertEqual(23, report["mana_board_1_nodes"])
        self.assertEqual(18, report["mana_board_2_nodes"])
        self.assertEqual(41, report["mana_total_nodes"])
        self.assertEqual("279996", report["mana_node_prefix"])
        self.assertFalse(report["writes_live"])
        self.assertTrue(report["package_manifest_eligible"])

        claim = TableClaim("server", "character.json", "json_object", ("139998",))
        image = JsonObjectCodec().inspect(result["files"]["character.json"], claim, ())
        self.assertIn("139998", dict(image.outer_rows))

    def test_requires_exact_server_path_contract_and_exact_row_shapes(self):
        self._require_module()
        self.assertEqual(set(SERVER_LOGICAL_PATHS), set(SERVER_PATHS))
        source = self._server_files()

        bad_rows = (
            [CHARACTER_ROW[:4]],
            [CHARACTER_ROW + ["extra"]],
            [CHARACTER_ROW, CHARACTER_ROW],
        )
        for rows in bad_rows:
            with self.subTest(character_rows=rows):
                with self.assertRaisesRegex(ValueError, "one 37-column row"):
                    compile_summer_thunder_server_files(
                        source,
                        character_rows=rows,
                        character_text_rows=[CHARACTER_TEXT_ROW],
                    )

        bad_text_rows = (
            [["拉姆斯"]],
            [CHARACTER_TEXT_ROW + ["extra"]],
            [CHARACTER_TEXT_ROW, CHARACTER_TEXT_ROW],
        )
        for rows in bad_text_rows:
            with self.subTest(character_text_rows=rows):
                with self.assertRaisesRegex(ValueError, "one 12-column row"):
                    compile_summer_thunder_server_files(
                        source,
                        character_rows=[CHARACTER_ROW],
                        character_text_rows=rows,
                    )

        identity_drifts = ((8, "thunder_dragon"), (17, "42"))
        for index, value in identity_drifts:
            row = list(CHARACTER_ROW)
            row[index] = value
            with self.subTest(identity_column=index):
                with self.assertRaisesRegex(ValueError, "character row identity"):
                    compile_summer_thunder_server_files(
                        source,
                        character_rows=[row],
                        character_text_rows=[CHARACTER_TEXT_ROW],
                    )

        row = list(CHARACTER_ROW)
        row[18] = "漂移的队长技"
        with self.assertRaisesRegex(ValueError, "leader title mismatch"):
            compile_summer_thunder_server_files(
                source,
                character_rows=[row],
                character_text_rows=[CHARACTER_TEXT_ROW],
            )

    def test_rejects_non_finite_json_duplicate_keys_and_bad_node_payloads(self):
        self._require_module()
        for token in (b"NaN", b"Infinity", b"-Infinity"):
            source = self._server_files()
            source["character.json"] = (
                b'{"1":{"value":' + token
                + b'},"139998":{"name":"old"}}'
            )
            with self.subTest(token=token):
                with self.assertRaisesRegex(ValueError, "non-finite JSON constant"):
                    compile_summer_thunder_server_files(
                        source,
                        character_rows=[CHARACTER_ROW],
                        character_text_rows=[CHARACTER_TEXT_ROW],
                    )

        source = self._server_files()
        source["character.json"] = b'{"139998":{},"139998":{}}'
        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            compile_summer_thunder_server_files(
                source,
                character_rows=[CHARACTER_ROW],
                character_text_rows=[CHARACTER_TEXT_ROW],
            )

        corruptions = []
        bad = _mana_nodes()
        bad["1"]["279996201"] = "not-an-object"
        corruptions.append(bad)
        bad = _mana_nodes()
        bad["1"]["279996201"].pop("field6")
        corruptions.append(bad)
        bad = _mana_nodes()
        bad["1"]["279996201"]["items"] = {"9": True}
        corruptions.append(bad)
        bad = _mana_nodes()
        bad["1"]["279996201"]["manaCost"] = "60"
        corruptions.append(bad)
        for mana_nodes in corruptions:
            source = self._server_files()
            mana = json.loads(source["mana_node.json"].decode("utf-8"))
            mana["139998"] = mana_nodes
            source["mana_node.json"] = _encoded(mana)
            with self.subTest(corruption=mana_nodes["1"]["279996201"]):
                with self.assertRaisesRegex(ValueError, "mana node payload"):
                    compile_summer_thunder_server_files(
                        source,
                        character_rows=[CHARACTER_ROW],
                        character_text_rows=[CHARACTER_TEXT_ROW],
                    )

    def test_rejects_mana_node_count_or_foreign_prefix(self):
        self._require_module()
        source = self._server_files()
        mana = json.loads(source["mana_node.json"].decode("utf-8"))
        mana["139998"]["1"]["46200201"] = mana["139998"]["1"].pop(
            "279996201"
        )
        source["mana_node.json"] = _encoded(mana)
        with self.assertRaisesRegex(ValueError, "mana node prefix"):
            compile_summer_thunder_server_files(
                source,
                character_rows=[CHARACTER_ROW],
                character_text_rows=[CHARACTER_TEXT_ROW],
            )

        source = self._server_files()
        mana = json.loads(source["mana_node.json"].decode("utf-8"))
        mana["139998"]["2"].pop("279996418")
        source["mana_node.json"] = _encoded(mana)
        with self.assertRaisesRegex(ValueError, "mana board node counts"):
            compile_summer_thunder_server_files(
                source,
                character_rows=[CHARACTER_ROW],
                character_text_rows=[CHARACTER_TEXT_ROW],
            )


if __name__ == "__main__":
    unittest.main()
