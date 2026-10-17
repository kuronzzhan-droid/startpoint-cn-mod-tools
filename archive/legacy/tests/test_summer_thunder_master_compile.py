import copy
import hashlib
import unittest
from pathlib import Path
from unittest import mock

import wf_mod_tool as core
import wf_quest_lib as quest
import wf_character_pack as character_pack
from wf_summer_thunder_ability_compile import build_summer_thunder_ability_rows
from wf_summer_thunder_voice_compile import (
    build_summer_thunder_character_speech_rows,
)

try:
    import wf_summer_thunder_master_compile as master_compile
except ImportError:
    master_compile = None


CHARACTER_ID = "139998"
CODE_NAME = "cnmod_thunder_dragon_ascendant"


def _flat(logical, rows):
    table = core.OrderedMap(
        logical,
        list(rows),
        [value.encode("utf-8") for value in rows.values()],
        Path("<fixture>"),
    )
    return core.build_orderedmap(table)


def _raw(logical, rows):
    table = core.OrderedMap(
        logical,
        list(rows),
        list(rows.values()),
        Path("<fixture>"),
    )
    return core.build_orderedmap_raw_rows(table)


def _csv(values):
    return core.write_csv_lines([list(map(str, values))])


def _action_row(name, program):
    return [
        name,
        "old description",
        "dynamic/skill/atk_nearest",
        "true",
        "440",
        "390",
        "0",
        program,
        "1",
        "2",
        "2400",
        "3000",
        "0",
        "0",
        "0",
        "0",
        "(None)",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
    ]


def _mana_trees():
    board = {"1": {}, "2": {}}
    nodes = {"1": {}, "2": {}}
    for board_key, count, base in (("1", 23, 279996200), ("2", 18, 279996400)):
        previous = "(None)"
        for index in range(1, count + 1):
            node_id = str(base + index)
            board[board_key][str(index)] = _csv(
                [node_id, -index, index, "qqqqq", 2 if index == 1 else 0, previous]
            )
            nodes[board_key][str(index)] = _csv(
                [node_id, 0, 9, 3, 60, 0, int(board_key)]
            )
            previous = node_id
    return board, nodes


def _compiled_core():
    character = [
        CODE_NAME, "1", "5", "2", "Dragon", "", "4", "Female",
        CODE_NAME, "(None)", "", "", "", "", "", "", "",
        CHARACTER_ID, "碧海雷鸣的共振",
        *(f"{CHARACTER_ID}{slot}" for slot in range(1, 7)),
        "0", "Attacker", "231001", "(None)", "1", "false", "false",
        "0", "0", "1", "true", "6,6,6,6,6,6",
    ]
    description = (
        "向前方释放由中心扩散的黄蓝雷波，对扇形范围内的敌人造成雷属性伤害"
        "（合计55倍／55段），并赋予自身「雷电增幅」效果（10秒）。"
    )
    character_text = [
        "拉姆斯", "LAMUSI", "summer dragon", "鸣彻碧海的雷龙",
        "碧海雷潮", description, "碧海雷潮＋", description,
        "(None)", "(None)", "碧海雷鸣的共振", "",
    ]
    return {
        "tables": {
            "character": {CHARACTER_ID: _csv(character)},
            "character_status": {
                CHARACTER_ID: core.encode_status_row([
                    ("10", 445, 129),
                    ("1", 45, 13),
                    ("80", 2670, 774),
                    ("100", 2937, 852),
                ])
            },
            "character_text": {CHARACTER_ID: _csv(character_text)},
            "character_awake_status": {},
        },
        "report": {
            "character_id": 139998,
            "code_name": CODE_NAME,
            "package_id": CODE_NAME,
            "writes_live": False,
        },
    }


def _fixture_base():
    if master_compile is None:
        return {}, {}

    board, nodes = _mana_trees()
    action_inner = core.OrderedMap(
        f"{master_compile.ACTION_SKILL_LOGICAL}#{CODE_NAME}",
        ["1", "2", "3"],
        [
            _csv(_action_row("old", "battle/action/skill/action/rare4/thunder_dragon$thunder_dragon_1")).encode(),
            _csv(_action_row("old+", "battle/action/skill/action/rare4/thunder_dragon$thunder_dragon_2")).encode(),
            _csv(_action_row("old++", "battle/action/skill/action/rare4/thunder_dragon_awake$thunder_dragon_3")).encode(),
        ],
        Path("<fixture>"),
    )
    official_inner = core.OrderedMap(
        f"{master_compile.ACTION_SKILL_LOGICAL}#official_skill",
        ["1"],
        [_csv(_action_row("official", "official/program")).encode()],
        Path("<fixture>"),
    )

    structural = {
        master_compile.SKILL_PREVIEW_LOGICAL: b"903,false,false,903,false,false,(None),(None),",
        master_compile.MANA_OPEN_LOGICAL: b"2015-03-01 12:00:00,2199-12-31 23:59:59",
        master_compile.UPSKILL_LOGICAL: (
            b"common_attack_up,(None),(None),(None),(None),(None),"
            b"common_attack_up,(None),(None),(None),(None),(None)"
        ),
        master_compile.STANCE_LOGICAL: b",1,1,2,,1,1,2",
        master_compile.GACHA_SOUND_LOGICAL: quest.build_node({
            "11": "sound_effect/monster/se_dragon_flying",
            "71": "sound_effect/monster/se_scream2",
            "77": "sound_effect/thunder/se_thunder_charge_smash",
            "159": "sound_effect/thunder/se_thunder_wide_area_electricity",
        }),
        master_compile.MANA_BOARD_LOGICAL: quest.build_node(board),
        master_compile.MANA_NODE_LOGICAL: quest.build_node(nodes),
        master_compile.ACTION_SKILL_LOGICAL: core.build_orderedmap(action_inner),
    }
    locked_hashes = {
        logical: hashlib.sha256(payload).hexdigest()
        for logical, payload in structural.items()
    }

    flat_targets = {
        master_compile.CHARACTER_LOGICAL: [CHARACTER_ID],
        master_compile.CHARACTER_TEXT_LOGICAL: [CHARACTER_ID],
        master_compile.CHARACTER_SPEECH_LOGICAL: [CHARACTER_ID],
        master_compile.ABILITY_LOGICAL: [f"{CHARACTER_ID}{slot}" for slot in range(1, 7)],
        master_compile.LEADER_LOGICAL: [CHARACTER_ID],
        # unique_condition is genuinely new in the authoring baseline.
        master_compile.UNIQUE_LOGICAL: [],
        master_compile.SKILL_PREVIEW_LOGICAL: [CHARACTER_ID],
        master_compile.MANA_OPEN_LOGICAL: [CHARACTER_ID],
        master_compile.UPSKILL_LOGICAL: [CHARACTER_ID],
        master_compile.STANCE_LOGICAL: [CHARACTER_ID],
    }
    base = {}
    for logical, target_keys in flat_targets.items():
        rows = {"official": f"official:{logical}"}
        for key in target_keys:
            payload = structural.get(logical, b"stale scaffold")
            rows[key] = payload.decode("utf-8")
        base[logical] = _flat(logical, rows)

    raw_targets = {
        master_compile.STATUS_LOGICAL: core.encode_status_row([("1", 1, 1)]),
        master_compile.CHARACTER_IMAGE_LOGICAL: quest.build_node({
            "0": "29,159,1936,1742", "1": "109,9,1769,1519"
        }),
        master_compile.FULL_SHOT_LOGICAL: quest.build_node({
            "0": "1000,1000,1,947,492", "1": "1000,1000,1,1194,605"
        }),
        master_compile.MANA_BOARD_LOGICAL: structural[master_compile.MANA_BOARD_LOGICAL],
        master_compile.MANA_NODE_LOGICAL: structural[master_compile.MANA_NODE_LOGICAL],
        master_compile.GACHA_SOUND_LOGICAL: structural[master_compile.GACHA_SOUND_LOGICAL],
    }
    for logical, target in raw_targets.items():
        base[logical] = _raw(logical, {"official": b"official raw", CHARACTER_ID: target})

    base[master_compile.ACTION_SKILL_LOGICAL] = _raw(
        master_compile.ACTION_SKILL_LOGICAL,
        {
            "official_skill": core.build_orderedmap(official_inner),
            CODE_NAME: structural[master_compile.ACTION_SKILL_LOGICAL],
        },
    )
    base[master_compile.TRIMMED_IMAGE_LOGICAL] = _flat(
        master_compile.TRIMMED_IMAGE_LOGICAL,
        {"official/trim": "1,2,3,4"},
    )
    return base, locked_hashes


def _decode_flat(raw, logical):
    keys, rows = core._strict_orderedmap_rows(
        raw, label=logical, compressed_rows=True
    )
    return dict(zip(keys, rows))


def _decode_raw(raw, logical):
    keys, rows = core._strict_orderedmap_rows(
        raw, label=logical, compressed_rows=False
    )
    return dict(zip(keys, rows))


class SummerThunderMasterCompileTests(unittest.TestCase):
    def _require_module(self):
        if master_compile is None:
            self.fail("wf_summer_thunder_master_compile is missing")

    def _compile(self):
        self._require_module()
        base, locked = _fixture_base()
        with mock.patch.dict(
            master_compile.LOCKED_STRUCTURE_SHA256, locked, clear=True
        ):
            result = master_compile.compile_summer_thunder_master_tables(
                base, _compiled_core()
            )
        return base, result

    def test_compiles_all_eighteen_tables_with_exact_manifest_claims(self):
        base, result = self._compile()
        self.assertEqual(set(base), set(result["files"]))
        self.assertEqual(18, len(result["files"]))
        claims = {item["logical_path"]: item for item in result["table_claims"]}
        self.assertEqual(set(base), set(claims))
        for item in claims.values():
            self.assertEqual(
                {"root", "logical_path", "codec_id", "outer_keys", "inner_keys", "semantic_claims"},
                set(item),
            )
            self.assertEqual("common", item["root"])
            self.assertEqual([], item["semantic_claims"])
        self.assertEqual(
            [CODE_NAME], claims[master_compile.ACTION_SKILL_LOGICAL]["outer_keys"]
        )
        self.assertEqual(
            [{"outer_key": CODE_NAME, "keys": ["1", "2"]}],
            claims[master_compile.ACTION_SKILL_LOGICAL]["inner_keys"],
        )
        self.assertEqual(
            sorted(master_compile.TRIM_ROWS),
            sorted(claims[master_compile.TRIMMED_IMAGE_LOGICAL]["outer_keys"]),
        )
        self.assertNotIn("character_awake_status", "\n".join(claims))
        parsed_claims = character_pack._parse_transaction_claims(
            {"tables": result["table_claims"]}
        )
        self.assertEqual(18, len(parsed_claims))

        for item in result["table_claims"]:
            claim = character_pack.TableClaim(
                item["root"],
                item["logical_path"],
                item["codec_id"],
                tuple(item["outer_keys"]),
                tuple(
                    (entry["outer_key"], tuple(entry["keys"]))
                    for entry in item["inner_keys"]
                ),
                (),
            )
            image = character_pack.DEFAULT_CODECS[item["codec_id"]].inspect(
                result["files"][item["logical_path"]], claim, ()
            )
            self.assertTrue(image.outer_rows, item["logical_path"])

    def test_readback_locks_core_abilities_speech_action_and_image_contracts(self):
        _, result = self._compile()
        files = result["files"]
        character = _decode_flat(files[master_compile.CHARACTER_LOGICAL], master_compile.CHARACTER_LOGICAL)
        self.assertEqual(CODE_NAME, core.read_csv_lines(character[CHARACTER_ID].decode())[0][0])
        self.assertEqual("5", core.read_csv_lines(character[CHARACTER_ID].decode())[0][2])

        built = build_summer_thunder_ability_rows()
        ability = _decode_flat(files[master_compile.ABILITY_LOGICAL], master_compile.ABILITY_LOGICAL)
        for key, rows in built["ability"].items():
            self.assertEqual(rows, core.read_csv_lines(ability[key].decode()))
        leader = _decode_flat(files[master_compile.LEADER_LOGICAL], master_compile.LEADER_LOGICAL)
        self.assertEqual(
            built["leader_ability"][CHARACTER_ID],
            core.read_csv_lines(leader[CHARACTER_ID].decode()),
        )
        unique = _decode_flat(files[master_compile.UNIQUE_LOGICAL], master_compile.UNIQUE_LOGICAL)
        self.assertEqual(
            [built["unique_condition"][CHARACTER_ID]],
            core.read_csv_lines(unique[CHARACTER_ID].decode()),
        )

        speech = _decode_flat(files[master_compile.CHARACTER_SPEECH_LOGICAL], master_compile.CHARACTER_SPEECH_LOGICAL)
        self.assertEqual(
            build_summer_thunder_character_speech_rows(),
            core.read_csv_lines(speech[CHARACTER_ID].decode()),
        )

        action = core.load_nested_table_bytes(
            files[master_compile.ACTION_SKILL_LOGICAL],
            master_compile.ACTION_SKILL_LOGICAL,
        )
        self.assertEqual(["1", "2"], action.rows[CODE_NAME].keys)
        for key, text in action.rows[CODE_NAME].text_rows().items():
            columns = core.read_csv_lines(text)[0]
            self.assertEqual("600", columns[4])
            self.assertEqual("600", columns[5])
            self.assertIn(CODE_NAME, columns[7])
            self.assertNotIn("thunder_dragon$", columns[7])

        raw_contracts = {
            master_compile.CHARACTER_IMAGE_LOGICAL: {
                "0": "457,276,1086,1448", "1": "457,276,1086,1448"
            },
            master_compile.FULL_SHOT_LOGICAL: {
                "0": "1000,1000,1,1022,536", "1": "1000,1000,1,842,761"
            },
        }
        for logical, expected in raw_contracts.items():
            target = _decode_raw(files[logical], logical)[CHARACTER_ID]
            self.assertEqual(expected, quest.parse_node(target))
        trim = _decode_flat(files[master_compile.TRIMMED_IMAGE_LOGICAL], master_compile.TRIMMED_IMAGE_LOGICAL)
        self.assertEqual(
            master_compile.TRIM_ROWS,
            {key: trim[key].decode() for key in master_compile.TRIM_ROWS},
        )

    def test_mana_and_locked_structural_scaffolds_pass_readback(self):
        _, result = self._compile()
        files = result["files"]
        for logical, count_by_board in (
            (master_compile.MANA_BOARD_LOGICAL, {"1": 23, "2": 18}),
            (master_compile.MANA_NODE_LOGICAL, {"1": 23, "2": 18}),
        ):
            target = _decode_raw(files[logical], logical)[CHARACTER_ID]
            tree = quest.parse_node(target)
            self.assertEqual(count_by_board, {key: len(value) for key, value in tree.items()})
        self.assertEqual(
            "903,false,false,903,false,false,(None),(None),",
            _decode_flat(files[master_compile.SKILL_PREVIEW_LOGICAL], master_compile.SKILL_PREVIEW_LOGICAL)[CHARACTER_ID].decode(),
        )
        gacha = quest.parse_node(
            _decode_raw(files[master_compile.GACHA_SOUND_LOGICAL], master_compile.GACHA_SOUND_LOGICAL)[CHARACTER_ID]
        )
        self.assertEqual({"11", "71", "77", "159"}, set(gacha))

    def test_nonowned_outer_and_action_inner_bytes_remain_unchanged(self):
        base, result = self._compile()
        for logical, raw in base.items():
            if logical == master_compile.ACTION_SKILL_LOGICAL:
                before = core.load_nested_table_bytes(raw, logical)
                after = core.load_nested_table_bytes(result["files"][logical], logical)
                self.assertEqual(
                    before.raw_rows["official_skill"],
                    after.raw_rows["official_skill"],
                )
                continue
            decoder = _decode_raw if master_compile.TABLE_CODECS[logical] == "raw_outer" else _decode_flat
            before = decoder(raw, logical)
            after = decoder(result["files"][logical], logical)
            owned = set(
                next(
                    item["outer_keys"]
                    for item in result["table_claims"]
                    if item["logical_path"] == logical
                )
            )
            for key in set(before) - owned:
                self.assertEqual(before[key], after[key], f"{logical}:{key}")

    def test_rejects_base_contract_drift_trim_collision_and_awake_payload(self):
        self._require_module()
        base, locked = _fixture_base()
        with mock.patch.dict(master_compile.LOCKED_STRUCTURE_SHA256, locked, clear=True):
            missing = dict(base)
            missing.pop(master_compile.STANCE_LOGICAL)
            with self.assertRaisesRegex(ValueError, "base tables must contain exactly"):
                master_compile.compile_summer_thunder_master_tables(missing, _compiled_core())

            drifted = dict(base)
            rows = _decode_flat(drifted[master_compile.SKILL_PREVIEW_LOGICAL], master_compile.SKILL_PREVIEW_LOGICAL)
            rows[CHARACTER_ID] += b"drift"
            drifted[master_compile.SKILL_PREVIEW_LOGICAL] = core.build_orderedmap(
                core.OrderedMap(
                    master_compile.SKILL_PREVIEW_LOGICAL,
                    list(rows),
                    list(rows.values()),
                    Path("<fixture>"),
                )
            )
            with self.assertRaisesRegex(ValueError, "locked scaffold drift"):
                master_compile.compile_summer_thunder_master_tables(drifted, _compiled_core())

            collided = dict(base)
            trim = _decode_flat(collided[master_compile.TRIMMED_IMAGE_LOGICAL], master_compile.TRIMMED_IMAGE_LOGICAL)
            trim[next(iter(master_compile.TRIM_ROWS))] = b"occupied"
            collided[master_compile.TRIMMED_IMAGE_LOGICAL] = core.build_orderedmap(
                core.OrderedMap(
                    master_compile.TRIMMED_IMAGE_LOGICAL,
                    list(trim),
                    list(trim.values()),
                    Path("<fixture>"),
                )
            )
            with self.assertRaisesRegex(ValueError, "trimmed_image identity collision"):
                master_compile.compile_summer_thunder_master_tables(collided, _compiled_core())

            awake = copy.deepcopy(_compiled_core())
            awake["tables"]["character_awake_status"] = {CHARACTER_ID: b"26,0"}
            with self.assertRaisesRegex(ValueError, "awake_status must be empty"):
                master_compile.compile_summer_thunder_master_tables(base, awake)

    def test_output_is_deterministic_readback_verified_and_never_live(self):
        self._require_module()
        base, locked = _fixture_base()
        base_snapshot = dict(base)
        compiled_core = _compiled_core()
        core_snapshot = copy.deepcopy(compiled_core)
        with mock.patch.dict(master_compile.LOCKED_STRUCTURE_SHA256, locked, clear=True):
            first = master_compile.compile_summer_thunder_master_tables(base, compiled_core)
            second = master_compile.compile_summer_thunder_master_tables(base, compiled_core)
        self.assertEqual(first, second)
        self.assertEqual(base_snapshot, base)
        self.assertEqual(core_snapshot, compiled_core)
        report = first["report"]
        self.assertEqual("compiled_isolated_master_tables", report["status"])
        self.assertFalse(report["writes_live"])
        self.assertTrue(report["table_claims_eligible"])
        self.assertFalse(report["package_manifest_eligible"])
        self.assertEqual(18, report["table_count"])
        self.assertEqual(0, report["nonowned_outer_changes"])
        self.assertEqual(0, report["nonowned_inner_changes"])
        self.assertEqual(
            {logical: hashlib.sha256(payload).hexdigest() for logical, payload in first["files"].items()},
            report["output_sha256"],
        )


if __name__ == "__main__":
    unittest.main()
