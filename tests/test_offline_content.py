from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from types import SimpleNamespace


MOD = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MOD))
import wf_mod_tool as core  # noqa: E402
import wf_dsl  # noqa: E402
import wf_quest_lib as quest  # noqa: E402
import wf_rogue_validate as rogue_validate  # noqa: E402
from wf_character_requirements import MasterAssetReference, required_asset_paths, unique_condition_id_columns  # noqa: E402


def load_module():
    path = MOD / "wf_offline_content.py"
    spec = importlib.util.spec_from_file_location("wf_offline_content", path)
    if spec is None or spec.loader is None:
        raise AssertionError("offline content module is missing")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class OfflineContentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.roots = self.module.StoreRoots(
            common=base / "common", medium=base / "medium", android=base / "android"
        )
        for root in (self.roots.common, self.roots.medium, self.roots.android):
            root.mkdir()
        self.spec = self.module.CharacterReleaseSpec(129999, "seris_dragon_king")
        self.required = tuple(
            item.logical_path for item in self.module.char_asset_requirements(self.spec.code_name)
            if item.category == "required"
        )
        self.phase4 = self.module.SERIS_PHASE4_ASSET_LOGICALS
        self.phase4_members = self.module.expand_seris_phase4_asset_literals(self.phase4)
        for logical in (*self.required, *sorted(self.phase4_members)):
            root = getattr(self.roots, self.module.expected_root_for_logical(logical))
            self.add_file(root, logical, logical.encode())
        self.add_master("129999")

    def add_file(self, root: Path, logical: str, data: bytes) -> Path:
        relative = self.module.hashed_rel(logical)
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def test_snapshot_access_guard_fails_before_an_unlocked_logical_is_read(self) -> None:
        accessed: list[tuple[str, str]] = []

        def reject(root_name: str, logical: str) -> None:
            accessed.append((root_name, logical))
            raise self.module.ContentGateError("unlocked logical")

        evidence = self.module._SnapshotEvidence(
            self.roots,
            access_guard=reject,
        )
        with self.assertRaisesRegex(self.module.ContentGateError, "unlocked logical"):
            evidence.resolve(self.module.CHARACTER_MASTER_LOGICAL)
        self.assertEqual(
            accessed,
            [("common", self.module.CHARACTER_MASTER_LOGICAL)],
        )

    def test_immutable_inventory_exposes_unmaterialized_wrong_root_and_equipment(self) -> None:
        character_relative = str(
            self.module.hashed_rel(self.module.CHARACTER_MASTER_LOGICAL)
        ).replace("\\", "/")
        equipment_relative = str(
            self.module.hashed_rel(self.module.PLAYER_EQUIPMENT_LOGICAL)
        ).replace("\\", "/")
        inventory = {
            "common": {character_relative, equipment_relative},
            "medium": {character_relative},
            "android": set(),
        }

        def allow_only_locked_common(root_name: str, logical: str) -> None:
            if (root_name, logical) != (
                "common",
                self.module.CHARACTER_MASTER_LOGICAL,
            ):
                raise self.module.ContentGateError("unlocked inventory logical")

        evidence = self.module._SnapshotEvidence(
            self.roots,
            access_guard=allow_only_locked_common,
            root_inventory=inventory,
        )
        with self.assertRaisesRegex(
            self.module.ContentGateError,
            "unlocked inventory logical",
        ):
            evidence.resolve(self.module.CHARACTER_MASTER_LOGICAL)
        with self.assertRaisesRegex(
            self.module.ContentGateError,
            "unlocked inventory logical",
        ):
            self.module.verify_player_1000_equipment_snapshot(
                self.roots,
                _evidence=evidence,
            )

    def valid_client_report(self, *, verified: bool = True) -> dict[str, object]:
        hashes = iter(char * 64 for char in "cdef0")
        swf0, swf1, swf2, swf3, swf4 = tuple(hashes)
        seris_sites = [
            "preload_seris_dual_form_assets",
            "switch_special_pixel_slot_preserve_frame_scale",
            "default_seris_human_power_flip",
            "dynamic_seris_skill_cutin",
            "dynamic_seris_member_status_path",
            "refresh_seris_member_status_texture",
            "dynamic_seris_control_board_path",
            "refresh_seris_control_board_texture",
            "route_seris_skill_voice_by_form",
        ]
        render_sites = ["pixel-art", "member-view", "character-cell"]
        return {
            "output_sha256": "a" * 64,
            "certificate_sha256": "b" * 64,
            "patch_order": [
                "abyss-mode-equipment", "seris-phase4", "render-scale", "resource-version",
            ],
            "stage_reports": [
                {
                    "stage": "abyss-mode-equipment", "input_sha256": swf0,
                    "output_sha256": swf1,
                    "target_class": "pinball.common.data.character.BattleCharacterLogic",
                    "before_method_sha256": "1" * 64, "after_method_sha256": "2" * 64,
                    "match_count": 1,
                },
                {
                    "input_sha256": swf1, "output_sha256": swf2,
                    "site_ids": seris_sites,
                    "before_hashes": {site: "3" * 64 for site in seris_sites},
                    "after_hashes": {site: "4" * 64 for site in seris_sites},
                    "asset_logicals": list(self.module.SERIS_PHASE4_ASSET_LOGICALS),
                    "verified": True,
                },
                {
                    "input_sha256": swf2, "output_sha256": swf3,
                    "site_ids": render_sites,
                    "before_hashes": {site: "5" * 64 for site in render_sites},
                    "after_hashes": {site: "6" * 64 for site in render_sites},
                    "verified": True,
                },
                {
                    "input_sha256": swf3, "output_sha256": swf4,
                    "source_version": "1.4.54", "output_version": "1.4.196",
                    "is_full_package": True, "verified": True,
                },
            ],
            "full_resource_version": "1.4.196",
            "aligned": True,
            "signature_schemes": {"v1": True, "v2": True, "v3": True},
            "verified": verified,
        }

    def add_master(self, outer_key: str) -> None:
        row = [""] * 37
        row[0] = self.spec.code_name if outer_key == "129999" else "stella_summer_goddess"
        for index, value in {
            1: "1", 2: "5", 3: "1", 4: "Dragon", 5: "ModDualForm", 6: "2",
            7: "Male", 8: self.spec.code_name, 9: "1", 10: "28", 11: "22",
            14: self.spec.code_name, 15: "false", 16: "false", 17: outer_key,
            18: "leader", 27: outer_key, 36: "6,6,6,6,6,6",
        }.items():
            row[index] = value
        row[19:25] = [f"{outer_key}{index}" for index in range(1, 7)]
        self.add_ordered(self.module.CHARACTER_MASTER_LOGICAL, {outer_key: core.write_csv_lines([row])})
        if outer_key != "129999":
            return

        def nested(mapping: dict[str, str | bytes], label: str) -> bytes:
            rows = [value if isinstance(value, bytes) else zlib.compress(value.encode("utf-8")) for value in mapping.values()]
            return core.build_orderedmap_raw_rows(core.OrderedMap(label, list(mapping), rows, Path("[fixture]")))

        self.add_file(
            self.roots.common, self.module.CHARACTER_STATUS_MASTER_LOGICAL,
            nested({"129999": nested({key: "1,1" for key in ("10", "1", "80", "100")}, "status-inner")}, "status"),
        )
        self.add_ordered(self.module.CHARACTER_TEXT_MASTER_LOGICAL, {
            "129999": core.write_csv_lines([["Seris", "SERIS", "desc", "title", "skill", "desc", "skill+", "desc+", "", "", "leader", "voice"]])
        })

        ability_rows: dict[str, str] = {}
        ability_row_counts = (2, 1, 5, 1, 2, 1)
        ability_main_flags = ("true", "true", "false", "true", "true", "false")
        ability_condition_column = unique_condition_id_columns(self.module.ABILITY_MASTER_LOGICAL)[0]
        for index, (row_count, main_flag) in enumerate(zip(ability_row_counts, ability_main_flags), 1):
            rows = []
            for row_index in range(row_count):
                ability = [""] * 126
                for column in (3, 5, 6, 13, 20, 27, 46, 47, 85, 97, 109, 123):
                    ability[column] = "0"
                ability[0] = f"seris_dragon_king_{index}"
                ability[1] = main_flag
                ability[2] = "action_skill"
                ability[39] = "(None)"
                ability[108] = "false"
                if index == 1 and row_index == 0:
                    ability[ability_condition_column] = "22"
                rows.append(ability)
            ability_rows[f"129999{index}"] = core.write_csv_lines(rows)
        self.add_ordered(self.module.ABILITY_MASTER_LOGICAL, ability_rows)

        leader_condition_column = unique_condition_id_columns(self.module.LEADER_ABILITY_MASTER_LOGICAL)[0]
        leader_rows = []
        for index in range(9):
            leader = [""] * 124
            for column in (1, 4, 11, 18, 25, 44, 95, 107, 121):
                leader[column] = "0"
            leader[0] = "seris_dragon_king_leader"
            leader[3] = "1"
            leader[37] = "(None)"
            leader[83] = "(None)"
            leader[106] = "false"
            leader[leader_condition_column] = "22"
            if index < len(self.module.SERIS_POWER_FLIP_KEYS):
                leader[118] = self.module.SERIS_POWER_FLIP_KEYS[index]
            leader_rows.append(leader)
        self.add_ordered(self.module.LEADER_ABILITY_MASTER_LOGICAL, {"129999": core.write_csv_lines(leader_rows)})

        action_values: dict[str, str] = {}
        for inner_key, program in zip(("1", "2"), self.module.SERIS_ACTION_PROGRAMS[:2]):
            action = [""] * 24
            action[:8] = [
                "skill", "description", "dynamic/skill/atk_common", "true",
                "520", "520", "1", program,
            ]
            action_values[inner_key] = core.write_csv_lines([action])
        self.add_file(
            self.roots.common, self.module.ACTION_SKILL_MASTER_LOGICAL,
            nested({self.spec.code_name: nested(action_values, "action-inner")}, "action"),
        )
        switched_values = {
            inner_key: core.write_csv_lines([[
                program, "0", "", "", "", "", "", "", "", "(None)",
                "", "", "", "", "", "", "",
            ]])
            for inner_key, program in zip(("1", "2"), self.module.SERIS_ACTION_PROGRAMS[2:])
        }
        self.add_file(
            self.roots.common, self.module.SWITCHED_ACTION_SKILL_MASTER_LOGICAL,
            nested({self.spec.code_name: nested(switched_values, "switched-inner")}, "switched"),
        )
        self.add_ordered(self.module.POWER_FLIP_ACTION_MASTER_LOGICAL, {
            self.module.SERIS_POWER_FLIP_KEYS[0]: core.write_csv_lines([list(self.module.SERIS_POWER_FLIP_PROGRAMS[:3])]),
            self.module.SERIS_POWER_FLIP_KEYS[1]: core.write_csv_lines([list(self.module.SERIS_POWER_FLIP_PROGRAMS[3:])]),
        })
        self.add_ordered(self.module.UNIQUE_CONDITION_MASTER_LOGICAL, {
            "22": "unique_seris_dragon_king,name,battle/common/unique_condition/unique_seris_dragon_king",
            "23": "unique_seris_wet,name,battle/common/unique_condition/unique_seris_wet",
        })

        tree = [
            ["ACUnique", 22, []], ["ACUnique", 23, []],
            *sorted(self.module.SERIS_EFFECT_BASES),
        ]
        dsl_raw = wf_dsl.encode_amf3(tree)
        compressor = zlib.compressobj(9, zlib.DEFLATED, -15)
        dsl_compressed = compressor.compress(dsl_raw) + compressor.flush()
        for program in (*self.module.SERIS_ACTION_PROGRAMS, *self.module.SERIS_POWER_FLIP_PROGRAMS):
            self.add_file(self.roots.common, wf_dsl.dsl_logical(program), dsl_compressed)
        for condition_icon in (
            "battle/common/unique_condition/unique_seris_dragon_king",
            "battle/common/unique_condition/unique_seris_wet",
        ):
            self.add_file(self.roots.common, condition_icon + ".png", b"icon")
        for effect in self.module.SERIS_EFFECT_BASES:
            reference = MasterAssetReference("skill_effect", effect, "fixture")
            for logical in required_asset_paths(reference):
                self.add_file(self.roots.common, logical, logical.encode())

        self.add_ordered(self.module.CHARACTER_SPEECH_MASTER_LOGICAL, {
            "129999": core.write_csv_lines([["0", "0", "", f"speech {index}", f"home/{index}"] for index in range(8)])
        })
        self.add_ordered(self.module.MANA_BOARD2_OPEN_MASTER_LOGICAL, {"129999": "start,end"})
        self.add_ordered(self.module.CHARACTER_AWAKE_STATUS_MASTER_LOGICAL, {"129999": "0,0"})
        for logical in (self.module.CHARACTER_IMAGE_MASTER_LOGICAL, self.module.FULL_SHOT_ATTRIBUTE_MASTER_LOGICAL):
            self.add_file(self.roots.common, logical, nested({"129999": nested({"0": "1,2", "1": "3,4"}, "image-inner")}, "image"))

        generated_board_nodes = {
            "1": ("13", "14", "16", "17", "18", "15", "7", "8", "10", "19", "20", "22", "23", "21", "11", "12", "9", "1", "2", "3", "4", "5", "6"),
            "2": tuple(str(index) for index in (*range(1, 8), *range(13, 19), *range(8, 13))),
        }
        generated_payload = {
            board: nested({node: "1,2" for node in nodes}, f"generated-{board}")
            for board, nodes in generated_board_nodes.items()
        }
        self.add_file(
            self.roots.common, self.module.GENERATED_MANA_BOARD_MASTER_LOGICAL,
            nested({"129999": nested(generated_payload, "generated-boards")}, "generated-mana-board"),
        )
        mana_payload = {}
        for board, nodes in {"1": range(1, 24), "2": range(1, 19)}.items():
            base = 200 if board == "1" else 400
            item_id = "1" if board == "1" else "2"
            field6 = "1" if board == "1" else "4"
            mana_payload[board] = nested({
                str(node): core.write_csv_lines([[
                    f"259998{base + node}", "0", item_id, "1",
                    str(base + node), "0", field6,
                ]])
                for node in nodes
            }, f"mana-node-{board}")
        self.add_file(
            self.roots.common, self.module.MANA_NODE_MASTER_LOGICAL,
            nested({"129999": nested(mana_payload, "mana-node-boards")}, "mana-node"),
        )
        self.add_ordered(self.module.TRIMMED_IMAGE_MASTER_LOGICAL, {
            f"character/seris_dragon_king/ui/{name}": "1,2,3,4"
            for name in (
                "full_shot_1440_1920_0", "skill_cutin_0", "full_shot_1440_1920_1",
                "skill_cutin_1", "skill_cutin_matched_0", "skill_cutin_matched_1", "skill_cutin_dragon",
            )
        })

    def add_ordered(self, logical: str, values: dict[str, str]) -> None:
        ordered = core.OrderedMap(
            logical,
            list(values),
            [zlib.compress(value.encode("utf-8")) for value in values.values()],
            Path("[fixture]"),
        )
        self.add_file(self.roots.common, logical, core.build_orderedmap_raw_rows(ordered))

    #: Every non-Stella release claims master/string/custom_ability_string.
    #: These keys are a hard contract mirrored by
    #: ``wf_offline_content._workspace_master_contracts``.
    CUSTOM_ABILITY_STRING_KEYS = {
        (149999, "white_wolf_gerald"): ("ability_skill_white_wolf_moon_fang",),
        (129992, "unicorn_lancer_rose"): (
            "change_skill_unicorn_lancer_rose", "override_string_unicorn_lancer_rose_dual_pf",
        ),
        (139995, "fox_oracle_autumn"): (
            "ability_skill_fox_oracle_autumn_fever_pf",
            "override_string_fox_oracle_autumn_dual_pf",
            "desc_override_fox_oracle_autumn_2",
            "desc_override_fox_oracle_autumn",
        ),
    }

    def install_published_character_snapshot(
        self, spec: object,
    ) -> None:
        """Install one complete staged-only Stella/Gerald release fixture."""

        def nested(mapping: dict[str, str | bytes], label: str) -> bytes:
            rows = [
                value if isinstance(value, bytes) else zlib.compress(value.encode("utf-8"))
                for value in mapping.values()
            ]
            return core.build_orderedmap_raw_rows(
                core.OrderedMap(label, list(mapping), rows, Path("[fixture]"))
            )

        identity = (spec.character_id, spec.code_name)
        for logical in sorted(self.module._required_37_logicals(spec.code_name)):
            root = getattr(self.roots, self.module.expected_root_for_logical(logical))
            self.add_file(root, logical, f"published:{logical}".encode())

        character = [""] * 37
        character[0] = spec.code_name
        character[2] = "5"
        character[3] = "1"
        character[8] = spec.code_name
        character[17] = str(spec.character_id)
        character[19:25] = [f"{spec.character_id}{index}" for index in range(1, 7)]
        character[27] = str(spec.character_id)
        self.add_ordered(
            self.module.CHARACTER_MASTER_LOGICAL,
            {str(spec.character_id): core.write_csv_lines([character])},
        )

        ability_values: dict[str, str] = {}
        revised_counts = {
            (129992, "unicorn_lancer_rose"): (2, 3, 5, 2, 2, 2),
            (139995, "fox_oracle_autumn"): (6, 3, 8, 2, 2, 1),
        }
        for index, row_count in enumerate(
            revised_counts.get(identity, self.module.WORKSPACE_ABILITY_ROW_COUNTS[identity]), 1
        ):
            rows = [[f"ability-{index}", *([""] * 125)] for _ in range(row_count)]
            for key, row_index, column, program in (
                self.module.WORKSPACE_ABILITY_PROGRAM_LOCATIONS[identity]
            ):
                if key == f"{spec.character_id}{index}":
                    rows[row_index][column] = program
            ability_values[f"{spec.character_id}{index}"] = core.write_csv_lines(rows)
        self.add_ordered(self.module.ABILITY_MASTER_LOGICAL, ability_values)
        leader_rows = [
            [f"leader-{index}", *([""] * 123)]
            for index in range(self.module.WORKSPACE_LEADER_ROW_COUNTS[identity])
        ]
        if identity == (149999, "white_wolf_gerald"):
            leader_rows[6][80] = self.module.GERALD_UNCLAIMED_POWER_FLIP_KEY
        if identity in self.module.DUAL_PF_KEYS:
            leader_rows[8][45] = "722"
            leader_rows[8][80] = self.module.DUAL_PF_KEYS[identity]
        self.add_ordered(
            self.module.LEADER_ABILITY_MASTER_LOGICAL,
            {str(spec.character_id): core.write_csv_lines(leader_rows)},
        )

        action_values: dict[str, str] = {}
        for inner_key, program in zip(
            ("1", "2"), self.module.WORKSPACE_ACTION_PROGRAMS[identity]
        ):
            row = [""] * 24
            row[0] = f"skill-{inner_key}"
            row[7] = program
            action_values[inner_key] = core.write_csv_lines([row])
        self.add_file(
            self.roots.common,
            self.module.ACTION_SKILL_MASTER_LOGICAL,
            nested({spec.code_name: nested(action_values, "action-inner")}, "action"),
        )

        def install_program(program: str) -> None:
            effects = set(self.module.WORKSPACE_PROGRAM_EFFECTS[program])
            marker = []
            if (identity in revised_counts
                    and program in self.module.WORKSPACE_ACTION_PROGRAMS[identity]):
                effects.add(f"battle/effect/skill_unique/{spec.code_name}_api/{spec.code_name}_api")
                if (identity == (139995, "fox_oracle_autumn")
                        and program in self.module.WORKSPACE_ACTION_PROGRAMS[identity]):
                    level = self.module.WORKSPACE_ACTION_PROGRAMS[identity].index(program)
                    marker = [["ACUnique", (139995, 1399951)[level], [{"min": 1, "max": 1}]]]
            dsl_raw = wf_dsl.encode_amf3([*sorted(effects), *marker])
            compressor = zlib.compressobj(9, zlib.DEFLATED, -15)
            self.add_file(
                self.roots.common,
                wf_dsl.dsl_logical(program),
                compressor.compress(dsl_raw) + compressor.flush(),
            )
            for effect in effects:
                reference = MasterAssetReference("skill_effect", effect, "fixture")
                for logical in required_asset_paths(reference):
                    root = getattr(
                        self.roots, self.module.expected_root_for_logical(logical)
                    )
                    self.add_file(root, logical, f"effect:{logical}".encode())

        for program in (
            *self.module.WORKSPACE_ACTION_PROGRAMS[identity],
            *self.module.WORKSPACE_ABILITY_PROGRAMS[identity],
        ):
            install_program(program)

        if identity in self.module.DUAL_PF_KEYS:
            programs = self.module.DUAL_PF_PROGRAMS[identity]
            self.add_ordered(self.module.POWER_FLIP_ACTION_MASTER_LOGICAL, {
                self.module.DUAL_PF_KEYS[identity]: core.write_csv_lines([list(programs)])
            })
            for program in programs:
                install_program(program)

        character_key = str(spec.character_id)
        flat_values = {
            self.module.CHARACTER_SPEECH_MASTER_LOGICAL: {
                character_key: "speech"
            },
            self.module.CHARACTER_TEXT_MASTER_LOGICAL: {
                character_key: core.write_csv_lines([[spec.code_name, "text", "desc", "title"]])
            },
            self.module.MANA_BOARD2_OPEN_MASTER_LOGICAL: {
                character_key: "open"
            },
        }
        raw_outer_logicals = {
            self.module.CHARACTER_STATUS_MASTER_LOGICAL,
            self.module.FULL_SHOT_ATTRIBUTE_MASTER_LOGICAL,
            self.module.CHARACTER_IMAGE_MASTER_LOGICAL,
            self.module.GENERATED_MANA_BOARD_MASTER_LOGICAL,
            self.module.MANA_NODE_MASTER_LOGICAL,
        }
        if identity == (139999, "stella_summer_goddess"):
            flat_values.update({
                self.module.SKILL_PREVIEW_CHARACTER_MASTER_LOGICAL: {
                    character_key: "preview"
                },
                self.module.CHARACTER_STANCE_DETAIL_MASTER_LOGICAL: {
                    character_key: "stance"
                },
            })
            raw_outer_logicals.add(self.module.CHARACTER_GACHA_SOUND_MASTER_LOGICAL)
        else:
            trimmed = {
                f"character/{spec.code_name}/ui/{name}": "1,2,3,4"
                for name in (
                    "full_shot_1440_1920_0", "full_shot_1440_1920_1",
                    "skill_cutin_0", "skill_cutin_1",
                )
            }
            flat_values.update({
                self.module.SKILL_PREVIEW_CHARACTER_MASTER_LOGICAL: {
                    character_key: "preview"
                },
                self.module.UPSKILL_MASTER_LOGICAL: {character_key: "upskill"},
                self.module.CHARACTER_STANCE_DETAIL_MASTER_LOGICAL: {
                    character_key: "stance"
                },
                self.module.TRIMMED_IMAGE_MASTER_LOGICAL: trimmed,
                self.module.CUSTOM_ABILITY_STRING_MASTER_LOGICAL: {
                    key: f"string:{key}"
                    for key in self.CUSTOM_ABILITY_STRING_KEYS[identity]
                },
            })
            raw_outer_logicals.add(self.module.CHARACTER_GACHA_SOUND_MASTER_LOGICAL)
        if identity in (
            (129992, "unicorn_lancer_rose"), (139995, "fox_oracle_autumn")
        ):
            flat_values[self.module.CHARACTER_AWAKE_STATUS_MASTER_LOGICAL] = {
                character_key: "awake"
            }
        if identity == (129992, "unicorn_lancer_rose"):
            flat_values[self.module.UNIQUE_CONDITION_MASTER_LOGICAL] = {
                character_key: "condition"
            }
        if identity == (139995, "fox_oracle_autumn"):
            icon = "battle/common/unique_condition/unique_fox_oracle_autumn_foxfire"
            flat_values[self.module.UNIQUE_CONDITION_MASTER_LOGICAL] = {
                key: f"foxfire_{key},foxfire,{icon},{duration},1,(None),(None),(None),(None),true,true,0,1,true,(None)"
                for key, duration in (("139995", 720), ("1399951", 900), ("1399952", 99999999))
            }
            self.add_file(self.roots.common, f"{icon}.png", b"foxfire-icon")
        if identity == (149999, "white_wolf_gerald"):
            self.add_ordered(
                self.module.POWER_FLIP_ACTION_MASTER_LOGICAL,
                {
                    self.module.GERALD_UNCLAIMED_POWER_FLIP_KEY:
                        core.write_csv_lines([list(self.module.GERALD_POWER_FLIP_PROGRAMS)])
                },
            )
            for program in self.module.GERALD_POWER_FLIP_PROGRAMS:
                install_program(program)

        for logical, values in flat_values.items():
            self.add_ordered(logical, values)
        for logical in raw_outer_logicals:
            self.add_file(
                self.roots.common,
                logical,
                nested({character_key: nested({"1": "value"}, f"{logical}-inner")}, logical),
            )

    def validate_one_published_character(self, spec: object):
        module = self.module

        class Rogue:
            ready = True

        saved = {name: getattr(module, name) for name in (
            "CHARACTERS", "validate_rogue_data", "verify_player_1000_snapshot",
            "verify_player_1000_equipment_snapshot", "_load_current_server_assets",
            "_bind_current_server_character", "load_workspace", "inspect_workspace",
            "_workspace_identity_hint",
        )}
        self.addCleanup(
            lambda: [setattr(module, name, value) for name, value in saved.items()]
        )
        module.CHARACTERS = (spec,)
        module.validate_rogue_data = lambda *_args: Rogue()
        module.verify_player_1000_snapshot = lambda *_args: None
        module.verify_player_1000_equipment_snapshot = lambda *_args: None
        module._load_current_server_assets = lambda *_args: object()
        module._bind_current_server_character = (
            lambda _spec, report, *_args, **_kwargs: report
        )

        def forbidden_workspace(*_args, **_kwargs):
            raise AssertionError("published snapshot consulted a workspace")

        module.load_workspace = forbidden_workspace
        module.inspect_workspace = forbidden_workspace
        module._workspace_identity_hint = forbidden_workspace
        return module.validate_offline_content(
            self.roots,
            workspace_sources=None,
            phase4_asset_logicals=self.phase4,
            assets_dir=Path(self.temp.name),
        )

    def test_stella_published_snapshot_is_workspace_free_and_release_ready(self) -> None:
        spec = self.module.CharacterReleaseSpec(139999, "stella_summer_goddess")
        self.install_published_character_snapshot(spec)
        result = self.validate_one_published_character(spec)
        self.assertTrue(result.ready)
        self.assertEqual(1, len(result.characters))
        report = result.characters[0]
        self.assertEqual("published-snapshot", report.evidence_mode)
        self.assertEqual((37, 37), (report.required_present, report.required_total))
        self.assertTrue(report.three_layer_consistent)
        self.assertEqual(report.seal_sha256, self.module.sha256_canonical_report(report))

    def test_gerald_published_snapshot_is_workspace_free_and_release_ready(self) -> None:
        spec = self.module.CharacterReleaseSpec(149999, "white_wolf_gerald")
        self.install_published_character_snapshot(spec)
        result = self.validate_one_published_character(spec)
        self.assertTrue(result.ready)
        self.assertEqual(1, len(result.characters))
        report = result.characters[0]
        self.assertEqual("published-snapshot", report.evidence_mode)
        self.assertEqual((37, 37), (report.required_present, report.required_total))
        self.assertTrue(report.three_layer_consistent)
        self.assertEqual(report.seal_sha256, self.module.sha256_canonical_report(report))

    def test_workspace_closure_tables_cover_every_registered_identity(self) -> None:
        """Registering a character means registering all of its hard contracts."""
        module = self.module
        for spec in module.CHARACTERS:
            self.assertIn(spec.character_id, module.EXPECTED_SERVER_SKILL_COUNTS)
        identities = sorted(
            (spec.character_id, spec.code_name)
            for spec in module.CHARACTERS
            if (spec.character_id, spec.code_name) != (129999, "seris_dragon_king")
        )
        for identity in identities:
            with self.subTest(identity=identity):
                code_name = identity[1]
                action_programs = module.WORKSPACE_ACTION_PROGRAMS[identity]
                ability_programs = module.WORKSPACE_ABILITY_PROGRAMS[identity]
                self.assertEqual(2, len(action_programs))
                self.assertEqual(
                    6, len(module.WORKSPACE_ABILITY_ROW_COUNTS[identity])
                )
                self.assertGreater(
                    module.WORKSPACE_LEADER_ROW_COUNTS[identity], 0
                )
                locations = module.WORKSPACE_ABILITY_PROGRAM_LOCATIONS[identity]
                self.assertEqual(
                    set(ability_programs),
                    {program for _key, _row, _column, program in locations},
                )
                prefix = "battle/effect/skill_unique/"
                families = set()
                for program in (*action_programs, *ability_programs):
                    for effect in module.WORKSPACE_PROGRAM_EFFECTS[program]:
                        self.assertTrue(
                            effect.startswith(prefix),
                            f"{program} leaves skill_unique: {effect}",
                        )
                        families.add(effect[len(prefix):].split("/")[0])
                # The two revised characters also own a generated API family;
                # Stella continues to reuse her sanctioned official family.
                expected_families = {code_name}
                if identity == (139999, "stella_summer_goddess"):
                    expected_families = {"stella_ballot23"}
                elif identity in ((129992, "unicorn_lancer_rose"), (139995, "fox_oracle_autumn")):
                    expected_families.add(f"{code_name}_api")
                self.assertEqual(expected_families, families)

    def test_unicorn_lancer_rose_published_snapshot_is_release_ready(self) -> None:
        spec = self.module.CharacterReleaseSpec(129992, "unicorn_lancer_rose")
        self.install_published_character_snapshot(spec)
        result = self.validate_one_published_character(spec)
        self.assertTrue(result.ready)
        self.assertEqual(1, len(result.characters))
        report = result.characters[0]
        self.assertEqual("published-snapshot", report.evidence_mode)
        self.assertEqual((37, 37), (report.required_present, report.required_total))
        self.assertTrue(report.three_layer_consistent)
        self.assertEqual(report.seal_sha256, self.module.sha256_canonical_report(report))

    def test_fox_oracle_autumn_published_snapshot_is_release_ready(self) -> None:
        spec = self.module.CharacterReleaseSpec(139995, "fox_oracle_autumn")
        self.install_published_character_snapshot(spec)
        result = self.validate_one_published_character(spec)
        self.assertTrue(result.ready)
        self.assertEqual(1, len(result.characters))
        report = result.characters[0]
        self.assertEqual("published-snapshot", report.evidence_mode)
        self.assertEqual((37, 37), (report.required_present, report.required_total))
        self.assertTrue(report.three_layer_consistent)
        self.assertEqual(report.seal_sha256, self.module.sha256_canonical_report(report))

    def test_fox_oracle_autumn_rejects_old_629_ability_program(self) -> None:
        """A native PF must not regress to a skill-kind 629 action."""
        spec = self.module.CharacterReleaseSpec(139995, "fox_oracle_autumn")
        identity = (spec.character_id, spec.code_name)
        self.install_published_character_snapshot(spec)
        program = ("battle/action/skill/action/ability_skill/"
                   "ability_skill_fox_oracle_autumn_fever_pf$"
                   "ability_skill_fox_oracle_autumn_fever_pf")
        self.assertNotIn(program, self.module.WORKSPACE_ABILITY_PROGRAMS[identity])
        leader_rows = [
            [f"leader-{index}", *([""] * 123)]
            for index in range(self.module.WORKSPACE_LEADER_ROW_COUNTS[identity])
        ]
        leader_rows[8][45] = "722"
        leader_rows[8][80] = self.module.DUAL_PF_KEYS[identity]
        leader_rows[7][69] = program
        self.add_ordered(
            self.module.LEADER_ABILITY_MASTER_LOGICAL,
            {str(spec.character_id): core.write_csv_lines(leader_rows)},
        )
        with self.assertRaisesRegex(
            self.module.ContentGateError,
            "ability action program location mismatch",
        ):
            self.module.verify_character_release(
                spec, self.roots, workspace_source=None,
                phase4_asset_logicals=self.phase4,
            )

    def test_native_dual_pf_requires_leader_override_and_all_three_programs(self) -> None:
        for character_id, code_name in self.module.DUAL_PF_KEYS:
            with self.subTest(character=code_name):
                spec = self.module.CharacterReleaseSpec(character_id, code_name)
                self.install_published_character_snapshot(spec)
                rows = [[""] * 124 for _ in range(
                    self.module.WORKSPACE_LEADER_ROW_COUNTS[(character_id, code_name)]
                )]
                rows[8][45] = "629"
                rows[8][80] = self.module.DUAL_PF_KEYS[(character_id, code_name)]
                self.add_ordered(self.module.LEADER_ABILITY_MASTER_LOGICAL, {
                    str(character_id): core.write_csv_lines(rows),
                })
                with self.assertRaisesRegex(self.module.ContentGateError,
                                            "native dual-PF leader override mismatch"):
                    self.validate_one_published_character(spec)

                self.install_published_character_snapshot(spec)
                programs = list(self.module.DUAL_PF_PROGRAMS[(character_id, code_name)])
                programs[-1] = programs[0]
                self.add_ordered(self.module.POWER_FLIP_ACTION_MASTER_LOGICAL, {
                    self.module.DUAL_PF_KEYS[(character_id, code_name)]:
                        core.write_csv_lines([programs]),
                })
                with self.assertRaisesRegex(self.module.ContentGateError,
                                            "three-level program closure mismatch"):
                    self.validate_one_published_character(spec)

    def test_gerald_leader_power_flip_key_requires_exact_row_6_column_80(self) -> None:
        spec = self.module.CharacterReleaseSpec(149999, "white_wolf_gerald")
        self.install_published_character_snapshot(spec)

        def replace_leader(location: tuple[int, int] | None) -> None:
            rows = [
                [f"leader-{index}", *([""] * 123)]
                for index in range(self.module.WORKSPACE_LEADER_ROW_COUNTS[
                    (spec.character_id, spec.code_name)
                ])
            ]
            if location is not None:
                row_index, column = location
                rows[row_index][column] = self.module.GERALD_UNCLAIMED_POWER_FLIP_KEY
            self.add_ordered(
                self.module.LEADER_ABILITY_MASTER_LOGICAL,
                {str(spec.character_id): core.write_csv_lines(rows)},
            )

        for label, location in (
            ("missing", None),
            ("wrong-row", (5, 80)),
            ("wrong-column", (6, 79)),
        ):
            with self.subTest(case=label):
                replace_leader(location)
                with self.assertRaisesRegex(
                    self.module.ContentGateError,
                    "leader power-flip location mismatch",
                ):
                    self.module.verify_character_release(
                        spec, self.roots, workspace_source=None,
                        phase4_asset_logicals=self.phase4,
                    )

    def test_explicit_workspace_mapping_requires_exact_three_character_keyset(self) -> None:
        expected = {spec.code_name for spec in self.module.CHARACTERS}
        valid = {name: Path(self.temp.name) / name for name in expected}
        invalid = (
            {},
            {"stella_summer_goddess": valid["stella_summer_goddess"]},
            {**valid, "unexpected_character": Path(self.temp.name) / "unexpected"},
            {
                key if key != "white_wolf_gerald" else "white_wolf_gerlad": value
                for key, value in valid.items()
            },
        )
        original = self.module.validate_rogue_data
        self.addCleanup(setattr, self.module, "validate_rogue_data", original)

        def forbidden_live_gate(*_args, **_kwargs):
            raise AssertionError("invalid workspace mapping reached content reads")

        self.module.validate_rogue_data = forbidden_live_gate
        for mapping in invalid:
            with self.subTest(keys=sorted(mapping)):
                with self.assertRaisesRegex(
                    self.module.ContentGateError,
                    "workspace source keys must be exactly",
                ):
                    self.module.validate_offline_content(
                        self.roots,
                        workspace_sources=mapping,
                        phase4_asset_logicals=self.phase4,
                        assets_dir=Path(self.temp.name),
                    )
        invalid_value = dict(valid)
        invalid_value["stella_summer_goddess"] = None
        with self.assertRaisesRegex(
            self.module.ContentGateError,
            "workspace source path is invalid",
        ):
            self.module.validate_offline_content(
                self.roots,
                workspace_sources=invalid_value,
                phase4_asset_logicals=self.phase4,
                assets_dir=Path(self.temp.name),
            )

    def test_published_snapshot_still_rejects_missing_and_wrong_root_assets(self) -> None:
        spec = self.module.CharacterReleaseSpec(139999, "stella_summer_goddess")
        self.install_published_character_snapshot(spec)
        required = sorted(self.module._required_37_logicals(spec.code_name))
        missing = required[0]
        missing_root = getattr(self.roots, self.module.expected_root_for_logical(missing))
        (missing_root / self.module.hashed_rel(missing)).unlink()
        with self.assertRaisesRegex(self.module.ContentGateError, "missing logical"):
            self.module.verify_character_release(
                spec, self.roots, workspace_source=None,
                phase4_asset_logicals=self.phase4,
            )

        self.add_file(missing_root, missing, b"restored")
        wrong = next(
            logical for logical in required
            if self.module.expected_root_for_logical(logical) == "medium"
        )
        right_path = self.roots.medium / self.module.hashed_rel(wrong)
        raw = right_path.read_bytes()
        right_path.unlink()
        self.add_file(self.roots.common, wrong, raw)
        with self.assertRaisesRegex(self.module.ContentGateError, "root ownership mismatch"):
            self.module.verify_character_release(
                spec, self.roots, workspace_source=None,
                phase4_asset_logicals=self.phase4,
            )

    def test_published_snapshot_rejects_hash_drift_before_seal(self) -> None:
        spec = self.module.CharacterReleaseSpec(149999, "white_wolf_gerald")
        self.install_published_character_snapshot(spec)
        target = sorted(self.module._required_37_logicals(spec.code_name))[0]
        target_root = getattr(self.roots, self.module.expected_root_for_logical(target))
        target_path = target_root / self.module.hashed_rel(target)
        original = self.module._read_file_bytes
        calls = 0

        def mutate_after_capture(root, logical, root_name):
            nonlocal calls
            result = original(root, logical, root_name)
            if logical == target:
                calls += 1
                if calls == 1:
                    target_path.write_bytes(result[1] + b"-tampered")
            return result

        self.module._read_file_bytes = mutate_after_capture
        self.addCleanup(setattr, self.module, "_read_file_bytes", original)
        with self.assertRaisesRegex(
            self.module.ContentGateError,
            "bytes changed after capture|metadata changed after capture",
        ):
            self.module.verify_character_release(
                spec, self.roots, workspace_source=None,
                phase4_asset_logicals=self.phase4,
            )

    def test_present_workspace_manifest_hash_or_seal_failure_never_falls_back(self) -> None:
        original_verify = self.module.verify_character_workspace_report
        original_published = self.module.build_published_snapshot_evidence
        self.addCleanup(
            setattr, self.module, "verify_character_workspace_report", original_verify
        )
        self.addCleanup(
            setattr, self.module, "build_published_snapshot_evidence", original_published
        )

        def forbidden_published(*_args, **_kwargs):
            raise AssertionError("invalid workspace silently fell back to snapshot evidence")

        self.module.build_published_snapshot_evidence = forbidden_published
        for spec, error in (
            (
                self.module.CharacterReleaseSpec(139999, "stella_summer_goddess"),
                "workspace server claim hash/size mismatch",
            ),
            (
                self.module.CharacterReleaseSpec(149999, "white_wolf_gerald"),
                "workspace manifest seal drift",
            ),
        ):
            with self.subTest(spec=spec.code_name, error=error):
                source = Path(self.temp.name) / f"workspace-{spec.code_name}"
                source.mkdir()
                (source / "workspace.json").write_text(
                    json.dumps({
                        "character_id": spec.character_id,
                        "code_name": spec.code_name,
                    }),
                    encoding="utf-8",
                )

                def reject(*_args, _error=error, **_kwargs):
                    raise self.module.ContentGateError(_error)

                self.module.verify_character_workspace_report = reject
                with self.assertRaisesRegex(self.module.ContentGateError, error):
                    self.module.verify_character_release(
                        spec, self.roots, workspace_source=source,
                        phase4_asset_logicals=self.phase4,
                    )

    def write_current_server_assets(self) -> Path:
        assets = Path(self.temp.name) / "current-assets"
        client_row = self.module._character_csv_row(self.roots, self.spec)
        text_raw = self.module._raw_ordered_rows(
            self.roots, self.module.CHARACTER_TEXT_MASTER_LOGICAL
        )["129999"]
        client_text = core.read_csv_lines(zlib.decompress(text_raw).decode("utf-8"))
        payloads = {
            "character.json": {
                "129999": {"element": 1, "name": "Seris", "rarity": 5, "skill_count": 6},
            },
            "cdndata/character.json": {"129999": [client_row]},
            "cdndata/character_text.json": {"129999": client_text},
            "mana_node.json": {
                "129999": {
                    "1": {
                        f"259998{suffix}": {
                            "field1": "0", "field5": "0", "field6": "1",
                            "manaCost": suffix, "items": {"1": 1},
                        }
                        for suffix in range(201, 224)
                    },
                    "2": {
                        f"259998{suffix}": {
                            "field1": "0", "field5": "0", "field6": "4",
                            "manaCost": suffix, "items": {"2": 1},
                        }
                        for suffix in range(401, 419)
                    },
                }
            },
        }
        for logical, payload in payloads.items():
            path = assets / logical
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        return assets

    def workspace_report(self, *, character_id: int, code_name: str, ready: bool) -> dict:
        return {
            "identity": {"character_id": character_id, "code_name": code_name},
            "release_ready": ready,
            "input_digest": "a" * 64,
            "requirement_report": {"required_present": 37, "required_total": 37},
            "three_layer_claim_status": {"consistent": True},
            "manifest": {
                "qa": {"workspace_input_sha256": "a" * 64},
                "roots": {"common": [], "medium": [], "android": [], "server": []},
            },
        }

    def complete_seris_manifest(self) -> tuple[dict, dict[str, bytes]]:
        """Build the complete character-specific table contract used by Phase 4."""
        client_specs = (
            (self.module.ABILITY_MASTER_LOGICAL, "flat", [f"129999{index}" for index in range(1, 7)], []),
            (self.module.LEADER_ABILITY_MASTER_LOGICAL, "flat", ["129999"], []),
            (self.module.CHARACTER_MASTER_LOGICAL, "flat", ["129999"], []),
            (self.module.CHARACTER_AWAKE_STATUS_MASTER_LOGICAL, "flat", ["129999"], []),
            (self.module.CHARACTER_SPEECH_MASTER_LOGICAL, "flat", ["129999"], []),
            (self.module.CHARACTER_STATUS_MASTER_LOGICAL, "raw_outer", ["129999"], []),
            (self.module.CHARACTER_TEXT_MASTER_LOGICAL, "flat", ["129999"], []),
            (self.module.FULL_SHOT_ATTRIBUTE_MASTER_LOGICAL, "raw_outer", ["129999"], []),
            (self.module.UNIQUE_CONDITION_MASTER_LOGICAL, "flat", ["22", "23"], []),
            (self.module.CHARACTER_IMAGE_MASTER_LOGICAL, "raw_outer", ["129999"], []),
            (self.module.GENERATED_MANA_BOARD_MASTER_LOGICAL, "raw_outer", ["129999"], []),
            (
                self.module.TRIMMED_IMAGE_MASTER_LOGICAL,
                "flat",
                [
                    f"character/seris_dragon_king/ui/{name}"
                    for name in (
                        "full_shot_1440_1920_0", "full_shot_1440_1920_1",
                        "skill_cutin_0", "skill_cutin_1", "skill_cutin_matched_0",
                        "skill_cutin_matched_1", "skill_cutin_dragon",
                    )
                ],
                [],
            ),
            (self.module.MANA_BOARD2_OPEN_MASTER_LOGICAL, "flat", ["129999"], []),
            (self.module.MANA_NODE_MASTER_LOGICAL, "raw_outer", ["129999"], []),
            (
                self.module.ACTION_SKILL_MASTER_LOGICAL,
                "action_nested",
                [self.spec.code_name],
                [{"outer_key": self.spec.code_name, "keys": ["1", "2"]}],
            ),
            (
                self.module.POWER_FLIP_ACTION_MASTER_LOGICAL,
                "flat",
                list(self.module.SERIS_POWER_FLIP_KEYS),
                [],
            ),
            (
                self.module.SWITCHED_ACTION_SKILL_MASTER_LOGICAL,
                "switched_nested",
                [self.spec.code_name],
                [{"outer_key": self.spec.code_name, "keys": ["1", "2"]}],
            ),
        )
        common_claims: list[dict[str, object]] = []
        table_claims: list[dict[str, object]] = []
        for logical, codec_id, outer_keys, inner_keys in client_specs:
            raw = (self.roots.common / self.module.hashed_rel(logical)).read_bytes()
            common_claims.append({
                "logical_path": logical,
                "size": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            })
            table_claims.append({
                "root": "common",
                "logical_path": logical,
                "codec_id": codec_id,
                "outer_keys": outer_keys,
                "inner_keys": inner_keys,
            })

        assets = self.write_current_server_assets()
        server_files = {
            logical: (assets / logical).read_bytes()
            for logical in self.module.SERVER_CHARACTER_LOGICALS
        }
        server_claims = [
            {
                "logical_path": logical,
                "size": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
            for logical, raw in server_files.items()
        ]
        table_claims.extend(
            {
                "root": "server",
                "logical_path": logical,
                "codec_id": "json_object",
                "outer_keys": ["129999"],
                "inner_keys": [],
            }
            for logical in server_files
        )
        return {
            "roots": {
                "common": common_claims,
                "medium": [],
                "android": [],
                "server": server_claims,
            },
            "tables": table_claims,
        }, server_files

    def install_synthetic_gerald_contract(self, pf_row: list[str]) -> tuple[dict, dict[str, bytes]]:
        spec = self.module.CharacterReleaseSpec(149999, "white_wolf_gerald")

        def nested(mapping: dict[str, str | bytes], label: str) -> bytes:
            rows = [
                value if isinstance(value, bytes) else zlib.compress(value.encode("utf-8"))
                for value in mapping.values()
            ]
            return core.build_orderedmap_raw_rows(
                core.OrderedMap(label, list(mapping), rows, Path("[fixture]"))
            )

        row = [""] * 37
        for index, value in {
            0: spec.code_name, 1: "1", 2: "5", 3: "1", 4: "Beast", 5: "",
            6: "2", 7: "Male", 8: spec.code_name, 17: "149999", 18: "leader",
        }.items():
            row[index] = value
        row[19:25] = [f"149999{index}" for index in range(1, 7)]
        flat_values: dict[str, dict[str, str]] = {
            self.module.CHARACTER_MASTER_LOGICAL: {"149999": core.write_csv_lines([row])},
            self.module.ABILITY_MASTER_LOGICAL: {
                f"149999{index}": f"ability-{index}" for index in range(1, 7)
            },
            self.module.LEADER_ABILITY_MASTER_LOGICAL: {"149999": "leader"},
            self.module.CHARACTER_TEXT_MASTER_LOGICAL: {"149999": "Gerald"},
            self.module.CHARACTER_SPEECH_MASTER_LOGICAL: {"149999": "speech"},
            "master/skill_preview/skill_preview_character.orderedmap": {"149999": "preview"},
            self.module.MANA_BOARD2_OPEN_MASTER_LOGICAL: {"149999": "open"},
            "master/mana_board/upskill.orderedmap": {"149999": "upskill"},
            "master/stance_detail/character_stance_detail.orderedmap": {"149999": "stance"},
            self.module.TRIMMED_IMAGE_MASTER_LOGICAL: {
                f"character/white_wolf_gerald/ui/{name}": "1,2,3,4"
                for name in (
                    "full_shot_1440_1920_0", "full_shot_1440_1920_1",
                    "skill_cutin_0", "skill_cutin_1",
                )
            },
            "master/string/custom_ability_string.orderedmap": {
                "ability_skill_white_wolf_moon_fang": "Moon Fang"
            },
            self.module.POWER_FLIP_ACTION_MASTER_LOGICAL: {
                self.module.GERALD_UNCLAIMED_POWER_FLIP_KEY: core.write_csv_lines([pf_row])
            },
        }
        for logical, values in flat_values.items():
            self.add_ordered(logical, values)
        raw_outer_logicals = (
            self.module.CHARACTER_STATUS_MASTER_LOGICAL,
            self.module.CHARACTER_IMAGE_MASTER_LOGICAL,
            self.module.FULL_SHOT_ATTRIBUTE_MASTER_LOGICAL,
            self.module.GENERATED_MANA_BOARD_MASTER_LOGICAL,
            self.module.MANA_NODE_MASTER_LOGICAL,
            "master/character/character_gacha_sound.orderedmap",
        )
        for logical in raw_outer_logicals:
            if logical == self.module.MANA_NODE_MASTER_LOGICAL:
                continue
            self.add_file(
                self.roots.common,
                logical,
                nested({"149999": nested({"1": "value"}, f"{logical}-inner")}, logical),
            )
        mana_server: dict[str, dict[str, dict[str, object]]] = {"1": {}, "2": {}}
        mana_boards: dict[str, bytes] = {}
        for board, nodes in {"1": range(1, 24), "2": range(1, 19)}.items():
            base = 200 if board == "1" else 400
            item_id = "1" if board == "1" else "2"
            field6 = "1" if board == "1" else "4"
            rows: dict[str, str] = {}
            for node in nodes:
                node_id = f"299998{base + node}"
                rows[str(node)] = core.write_csv_lines([[
                    node_id, "0", item_id, "1", str(base + node), "0", field6,
                ]])
                mana_server[board][node_id] = {
                    "field1": "0", "field5": "0", "field6": field6,
                    "items": {item_id: 1}, "manaCost": base + node,
                }
            mana_boards[board] = nested(rows, f"gerald-mana-{board}")
        self.add_file(
            self.roots.common,
            self.module.MANA_NODE_MASTER_LOGICAL,
            nested({"149999": nested(mana_boards, "gerald-mana-boards")}, "gerald-mana"),
        )
        self.add_file(
            self.roots.common,
            self.module.ACTION_SKILL_MASTER_LOGICAL,
            nested({
                spec.code_name: nested({"1": "skill-1", "2": "skill-2"}, "action-inner")
            }, "action"),
        )

        table_specs = (
            (self.module.CHARACTER_MASTER_LOGICAL, "flat", ["149999"], []),
            (self.module.ABILITY_MASTER_LOGICAL, "flat", [f"149999{i}" for i in range(1, 7)], []),
            (self.module.LEADER_ABILITY_MASTER_LOGICAL, "flat", ["149999"], []),
            (self.module.CHARACTER_TEXT_MASTER_LOGICAL, "flat", ["149999"], []),
            (self.module.CHARACTER_SPEECH_MASTER_LOGICAL, "flat", ["149999"], []),
            ("master/skill_preview/skill_preview_character.orderedmap", "flat", ["149999"], []),
            (self.module.MANA_BOARD2_OPEN_MASTER_LOGICAL, "flat", ["149999"], []),
            ("master/mana_board/upskill.orderedmap", "flat", ["149999"], []),
            ("master/stance_detail/character_stance_detail.orderedmap", "flat", ["149999"], []),
            (
                self.module.TRIMMED_IMAGE_MASTER_LOGICAL,
                "flat",
                list(flat_values[self.module.TRIMMED_IMAGE_MASTER_LOGICAL]),
                [],
            ),
            *((logical, "raw_outer", ["149999"], []) for logical in raw_outer_logicals),
            (
                self.module.ACTION_SKILL_MASTER_LOGICAL,
                "action_nested",
                [spec.code_name],
                [{"outer_key": spec.code_name, "keys": ["1", "2"]}],
            ),
            (
                "master/string/custom_ability_string.orderedmap",
                "flat",
                ["ability_skill_white_wolf_moon_fang"],
                [],
            ),
        )
        common_claims: list[dict[str, object]] = []
        table_claims: list[dict[str, object]] = []
        all_client_logicals = [spec[0] for spec in table_specs]
        all_client_logicals.append(self.module.POWER_FLIP_ACTION_MASTER_LOGICAL)
        for logical in all_client_logicals:
            raw = (self.roots.common / self.module.hashed_rel(logical)).read_bytes()
            common_claims.append({
                "logical_path": logical, "size": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            })
        for logical, codec_id, outer_keys, inner_keys in table_specs:
            table_claims.append({
                "root": "common", "logical_path": logical, "codec_id": codec_id,
                "outer_keys": outer_keys, "inner_keys": inner_keys,
            })

        client_row = self.module._character_csv_row(self.roots, spec)
        server_payloads = {
            "character.json": {
                "149999": {"name": "Gerald", "rarity": 5, "element": 1, "skill_count": 6}
            },
            "cdndata/character.json": {"149999": [client_row]},
            "cdndata/character_text.json": {"149999": [["Gerald"]]},
            "mana_node.json": {"149999": mana_server},
        }
        server_files = {
            logical: json.dumps(payload, separators=(",", ":")).encode()
            for logical, payload in server_payloads.items()
        }
        server_claims = [
            {"logical_path": logical, "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
            for logical, raw in server_files.items()
        ]
        table_claims.extend({
            "root": "server", "logical_path": logical, "codec_id": "json_object",
            "outer_keys": ["149999"], "inner_keys": [],
        } for logical in server_files)
        return {
            "roots": {"common": common_claims, "medium": [], "android": [], "server": server_claims},
            "tables": table_claims,
        }, server_files

    def test_seris_workspace_with_stella_identity_is_rejected(self) -> None:
        report = self.workspace_report(
            character_id=139999, code_name="stella_summer_goddess", ready=True
        )
        with self.assertRaisesRegex(self.module.ContentGateError, "identity mismatch"):
            self.module.verify_character_workspace_report(self.spec, report, self.roots)

    def test_seris_stella_workspace_identity_falls_back_without_reading_unreadable_package(self) -> None:
        source = Path(self.temp.name) / "misidentified-seris"
        source.mkdir()
        (source / "workspace.json").write_text(
            '{"character_id":139999,"code_name":"stella_summer_goddess"}', encoding="utf-8"
        )
        original = self.module.inspect_workspace
        self.addCleanup(setattr, self.module, "inspect_workspace", original)
        self.module.inspect_workspace = lambda *_args: (_ for _ in ()).throw(AssertionError("invalid package was read"))
        report = self.module.verify_character_release(
            self.spec, self.roots, workspace_source=source, phase4_asset_logicals=self.phase4
        )
        self.assertEqual("published-snapshot", report.evidence_mode)

    def test_workspace_identity_hint_rejects_duplicate_or_nonstandard_json(self) -> None:
        source = Path(self.temp.name) / "bad-workspace"
        source.mkdir()
        (source / "workspace.json").write_text(
            '{"character_id":129999,"character_id":139999,"code_name":"seris_dragon_king"}', encoding="utf-8"
        )
        with self.assertRaisesRegex(self.module.ContentGateError, "duplicate"):
            self.module._workspace_identity_hint(source)
        (source / "workspace.json").write_text(
            '{"character_id":NaN,"code_name":"seris_dragon_king"}', encoding="utf-8"
        )
        with self.assertRaisesRegex(self.module.ContentGateError, "non-standard"):
            self.module._workspace_identity_hint(source)

    def test_equivalent_seris_snapshot_evidence_binds_every_required_byte(self) -> None:
        report = self.module.build_published_snapshot_evidence(
            self.spec, self.roots, phase4_asset_logicals=self.phase4
        )
        self.assertEqual(report.identity, {"character_id": 129999, "code_name": "seris_dragon_king"})
        self.assertEqual((report.required_present, report.required_total), (37, 37))
        self.assertTrue(report.three_layer_consistent)
        self.assertEqual((), report.missing)
        self.assertEqual(report.seal_sha256, self.module.sha256_canonical_report(report))
        self.assertEqual(126, len(report.bound_files))

    def test_correct_seris_workspace_still_requires_every_phase4_concrete_asset(self) -> None:
        source = Path(self.temp.name) / "correct-seris"
        source.mkdir()
        (source / "workspace.json").write_text(
            '{"character_id":129999,"code_name":"seris_dragon_king"}', encoding="utf-8"
        )
        original = self.module.verify_character_workspace_report
        self.addCleanup(setattr, self.module, "verify_character_workspace_report", original)
        self.module.verify_character_workspace_report = lambda *_args, **_kwargs: self.module.CharacterEvidenceReport(
            identity={"character_id": 129999, "code_name": "seris_dragon_king"},
            evidence_mode="sealed-workspace", required_present=37, required_total=37,
            three_layer_consistent=True, bound_files=(), missing=(), seal_sha256="sealed",
        )
        extra = next(iter(set(self.phase4_members) - set(self.required)))
        root = getattr(self.roots, self.module.expected_root_for_logical(extra))
        (root / self.module.hashed_rel(extra)).unlink()
        with self.assertRaisesRegex(self.module.ContentGateError, "missing logical"):
            self.module.verify_character_release(
                self.spec, self.roots, workspace_source=source,
                phase4_asset_logicals=self.phase4,
            )

    def test_master_hash_semantics_and_final_audit_reject_a_second_version(self) -> None:
        logical = self.module.CHARACTER_MASTER_LOGICAL
        original = self.module._read_file_bytes
        path = self.roots.common / self.module.hashed_rel(logical)
        version_a = path.read_bytes()
        rows = self.module._raw_ordered_rows(self.roots, logical)
        bad_row = core.read_csv_lines(zlib.decompress(rows["129999"]).decode("utf-8"))[0]
        bad_row[0] = "swapped_version_b"
        version_b = core.build_orderedmap_raw_rows(core.OrderedMap(
            logical, ["129999"], [zlib.compress(core.write_csv_lines([bad_row]).encode("utf-8"))], Path("[fixture]")
        ))
        calls: list[bytes] = []

        def swapping(root: Path, requested: str, root_name: str):
            if requested != logical:
                return original(root, requested, root_name)
            raw = version_a if not calls else version_b
            calls.append(raw)
            return self.module.ManifestEntry(
                f"roots/{root_name}/{requested}", len(raw), hashlib.sha256(raw).hexdigest(), f"snapshot:{root_name}"
            ), raw

        self.module._read_file_bytes = swapping
        self.addCleanup(setattr, self.module, "_read_file_bytes", original)
        with self.assertRaisesRegex(self.module.ContentGateError, "bytes changed after capture"):
            self.module.build_published_snapshot_evidence(
                self.spec, self.roots, phase4_asset_logicals=self.phase4
            )
        self.assertEqual([version_a, version_b], calls)

    def test_seris_closure_rejects_missing_effect_and_dsl_unique_condition(self) -> None:
        effect = sorted(self.module.SERIS_EFFECT_BASES)[0]
        missing_asset = required_asset_paths(MasterAssetReference("skill_effect", effect, "fixture"))[0]
        (self.roots.common / self.module.hashed_rel(missing_asset)).unlink()
        with self.assertRaisesRegex(self.module.ContentGateError, "missing logical"):
            self.module.build_published_snapshot_evidence(
                self.spec, self.roots, phase4_asset_logicals=self.phase4
            )
        self.add_master("129999")
        tree = [*sorted(self.module.SERIS_EFFECT_BASES), ["ACUnique", 22, []]]
        dsl_raw = wf_dsl.encode_amf3(tree)
        for program in (*self.module.SERIS_ACTION_PROGRAMS, *self.module.SERIS_POWER_FLIP_PROGRAMS):
            compressor = zlib.compressobj(9, zlib.DEFLATED, -15)
            self.add_file(
                self.roots.common, wf_dsl.dsl_logical(program),
                compressor.compress(dsl_raw) + compressor.flush(),
            )
        with self.assertRaisesRegex(self.module.ContentGateError, "exactly 22/23"):
            self.module.build_published_snapshot_evidence(
                self.spec, self.roots, phase4_asset_logicals=self.phase4
            )

    def test_current_server_assets_are_bound_and_cross_checked(self) -> None:
        assets = self.write_current_server_assets()
        original = self.module._stable_read_path
        calls: list[str] = []

        def counted(path: Path, label: str) -> bytes:
            calls.append(Path(path).relative_to(assets).as_posix())
            return original(path, label)

        self.module._stable_read_path = counted
        self.addCleanup(setattr, self.module, "_stable_read_path", original)
        server = self.module._load_current_server_assets(assets)
        self.assertEqual(sorted(self.module.SERVER_CHARACTER_LOGICALS), sorted(calls))
        cache = self.module._SnapshotEvidence(self.roots)
        base = self.module.build_published_snapshot_evidence(
            self.spec, self.roots, phase4_asset_logicals=self.phase4, _evidence=cache
        )
        bound = self.module._bind_current_server_character(
            self.spec, base, self.roots, server, _evidence=cache
        )
        self.assertTrue(bound.three_layer_consistent)
        self.assertEqual(130, len(bound.bound_files))
        self.assertEqual(bound.seal_sha256, self.module.sha256_canonical_report(bound))
        bad = json.loads((assets / "cdndata/character.json").read_text(encoding="utf-8"))
        bad["129999"][0][0] = "wrong_code"
        (assets / "cdndata/character.json").write_text(json.dumps(bad), encoding="utf-8")
        server = self.module._load_current_server_assets(assets)
        with self.assertRaisesRegex(self.module.ContentGateError, "differs from staged client"):
            self.module._bind_current_server_character(
                self.spec, base, self.roots, server, _evidence=cache
            )

        assets = self.write_current_server_assets()
        bad = json.loads((assets / "character.json").read_text(encoding="utf-8"))
        bad["129999"]["skill_count"] = 999
        (assets / "character.json").write_text(json.dumps(bad), encoding="utf-8")
        with self.assertRaisesRegex(self.module.ContentGateError, "skill_count"):
            self.module._bind_current_server_character(
                self.spec, base, self.roots, self.module._load_current_server_assets(assets), _evidence=cache
            )

        assets = self.write_current_server_assets()
        bad = json.loads((assets / "mana_node.json").read_text(encoding="utf-8"))
        bad["129999"]["1"]["259998201"]["manaCost"] = -999
        (assets / "mana_node.json").write_text(json.dumps(bad), encoding="utf-8")
        with self.assertRaisesRegex(self.module.ContentGateError, "mana node"):
            self.module._bind_current_server_character(
                self.spec, base, self.roots, self.module._load_current_server_assets(assets), _evidence=cache
            )

    def test_seris_published_closure_requires_exact_ability_and_leader_row_counts(self) -> None:
        condition_column = unique_condition_id_columns(self.module.ABILITY_MASTER_LOGICAL)[0]
        ability_rows = {}
        for index, row_count in enumerate((1, 1, 5, 1, 2, 1), 1):
            rows = [[""] * (condition_column + 1) for _ in range(row_count)]
            if index == 1:
                rows[0][condition_column] = "22"
            ability_rows[f"129999{index}"] = core.write_csv_lines(rows)
        self.add_ordered(self.module.ABILITY_MASTER_LOGICAL, ability_rows)
        with self.assertRaisesRegex(self.module.ContentGateError, "ability row count"):
            self.module.build_published_snapshot_evidence(
                self.spec, self.roots, phase4_asset_logicals=self.phase4
            )

        self.add_master("129999")
        leader_column = unique_condition_id_columns(self.module.LEADER_ABILITY_MASTER_LOGICAL)[0]
        leader_rows = []
        for index in range(8):
            row = [""] * 119
            row[leader_column] = "22"
            if index < len(self.module.SERIS_POWER_FLIP_KEYS):
                row[118] = self.module.SERIS_POWER_FLIP_KEYS[index]
            leader_rows.append(row)
        self.add_ordered(
            self.module.LEADER_ABILITY_MASTER_LOGICAL,
            {"129999": core.write_csv_lines(leader_rows)},
        )
        with self.assertRaisesRegex(self.module.ContentGateError, "leader row count"):
            self.module.build_published_snapshot_evidence(
                self.spec, self.roots, phase4_asset_logicals=self.phase4
            )

    def test_seris_published_closure_rejects_empty_rows_with_correct_counts(self) -> None:
        condition_column = unique_condition_id_columns(self.module.ABILITY_MASTER_LOGICAL)[0]
        ability_rows = {}
        for index, row_count in enumerate((2, 1, 5, 1, 2, 1), 1):
            rows = [[""] * 126 for _ in range(row_count)]
            if index == 1:
                rows[0][condition_column] = "22"
            ability_rows[f"129999{index}"] = core.write_csv_lines(rows)
        self.add_ordered(self.module.ABILITY_MASTER_LOGICAL, ability_rows)
        with self.assertRaisesRegex(self.module.ContentGateError, "ability row semantic shape"):
            self.module.build_published_snapshot_evidence(
                self.spec, self.roots, phase4_asset_logicals=self.phase4
            )

    def test_missing_or_wrong_hash_layer_is_rejected(self) -> None:
        logical = self.required[0]
        root_name = self.module.expected_root_for_logical(logical)
        root = getattr(self.roots, root_name)
        path = root / self.module.hashed_rel(logical)
        path.unlink()
        with self.assertRaisesRegex(self.module.ContentGateError, "missing logical"):
            self.module.build_published_snapshot_evidence(
                self.spec, self.roots, phase4_asset_logicals=self.phase4
            )
        self.add_file(root, logical, b"same")
        other_root = self.roots.medium if root_name != "medium" else self.roots.common
        self.add_file(other_root, logical, b"same")
        with self.assertRaisesRegex(self.module.ContentGateError, "ambiguous"):
            self.module.build_published_snapshot_evidence(
                self.spec, self.roots, phase4_asset_logicals=self.phase4
            )
        duplicate = other_root / self.module.hashed_rel(logical)
        duplicate.unlink()
        # A declared snapshot binding must catch changed bytes, rather than
        # merely seeing a file at the calculated hash location.
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"expected")
        manifest = self.module.ManifestEntry(f"roots/{root_name}/{logical}", len(b"expecte"), hashlib.sha256(b"expecte").hexdigest(), f"snapshot:{root_name}")
        path.write_bytes(b"wrongee")
        with self.assertRaisesRegex(self.module.ContentGateError, "hash mismatch"):
            self.module.verify_manifest_entries((manifest,), self.roots)

    def test_cached_snapshot_owner_and_casefold_manifest_drift_are_rejected(self) -> None:
        logical = self.required[0]
        cache = self.module._SnapshotEvidence(self.roots)
        cache.resolve(logical)
        root_name = self.module.expected_root_for_logical(logical)
        other_root = self.roots.medium if root_name != "medium" else self.roots.common
        self.add_file(other_root, logical, b"late duplicate")
        with self.assertRaisesRegex(self.module.ContentGateError, "ownership changed|ambiguous"):
            cache.resolve(logical)

        (other_root / self.module.hashed_rel(logical)).unlink()
        cache = self.module._SnapshotEvidence(self.roots)
        _entry, captured = cache.resolve(logical)
        source = getattr(self.roots, root_name) / self.module.hashed_rel(logical)
        source.write_bytes(captured + b"drift")
        with self.assertRaisesRegex(self.module.ContentGateError, "changed after capture"):
            cache.resolve(logical)

        manifest = {
            "roots": {
                "common": [
                    {"logical_path": "Character/Seris.bin", "size": 1, "sha256": "a" * 64},
                    {"logical_path": "character/seris.bin", "size": 1, "sha256": "b" * 64},
                ],
                "medium": [], "android": [],
            }
        }
        with self.assertRaisesRegex(self.module.ContentGateError, "repeats client claim"):
            self.module._manifest_claim_entries(manifest)

    def test_cached_ordered_rows_recheck_same_length_byte_drift(self) -> None:
        logical = self.module.CHARACTER_TEXT_MASTER_LOGICAL
        cache = self.module._SnapshotEvidence(self.roots)
        cache.ordered(logical)
        path = self.roots.common / self.module.hashed_rel(logical)
        original = path.read_bytes()
        replacement = bytes([original[0] ^ 1]) + original[1:]
        self.assertEqual(len(original), len(replacement))
        path.write_bytes(replacement)
        with self.assertRaisesRegex(self.module.ContentGateError, "changed after capture"):
            cache.ordered(logical)

    def test_final_snapshot_audit_rehashes_even_when_metadata_signature_matches(self) -> None:
        logical = self.required[0]
        root_name = self.module.expected_root_for_logical(logical)
        root = getattr(self.roots, root_name)
        cache = self.module._SnapshotEvidence(self.roots)
        _entry, captured = cache.resolve(logical)
        path = root / self.module.hashed_rel(logical)
        replacement = bytes([captured[0] ^ 1]) + captured[1:]
        self.assertEqual(len(captured), len(replacement))
        path.write_bytes(replacement)
        # Simulate Windows' same-size/in-place rewrite with a restored mtime:
        # even if metadata collides exactly, final audit must compare bytes.
        cache.capture_signatures[(root_name, logical)] = cache._capture_signature(
            root_name, logical
        )
        with self.assertRaisesRegex(self.module.ContentGateError, "bytes changed after capture"):
            cache.audit()

    def test_wrong_hash_medium_and_android_are_rejected(self) -> None:
        for root_name, root in (("medium", self.roots.medium), ("android", self.roots.android)):
            logical = f"character/seris_dragon_king/test/{root_name}.bin"
            path = self.add_file(root, logical, b"expected")
            entry = self.module.ManifestEntry(
                f"roots/{root_name}/{logical}", 8, hashlib.sha256(b"expected").hexdigest(), f"snapshot:{root_name}"
            )
            path.write_bytes(b"differen")
            with self.subTest(root=root_name), self.assertRaisesRegex(self.module.ContentGateError, "hash mismatch"):
                self.module.verify_manifest_entries((entry,), self.roots)

    def test_workspace_manifest_seal_drift_reaches_the_qa_digest_gate(self) -> None:
        source = Path(self.temp.name) / "seal-drift-workspace"
        package = source / "package"
        package.mkdir(parents=True)
        (source / "workspace.json").write_text(
            '{"character_id":129999,"code_name":"seris_dragon_king"}', encoding="utf-8"
        )
        manifest = {
            "qa": {"workspace_input_sha256": "b" * 64},
            "roots": {"common": [], "medium": [], "android": [], "server": []},
        }
        (package / "manifest.json").write_text(
            json.dumps(manifest, separators=(",", ":")), encoding="utf-8"
        )
        replacements = {
            "load_workspace": lambda *_args: SimpleNamespace(package_dir=package),
            "inspect_workspace": lambda *_args: {
                "identity": {"character_id": 129999, "code_name": "seris_dragon_king"},
                "release_ready": True,
                "input_digest": "a" * 64,
                "requirement_report": {"required_present": 37, "required_total": 37},
                "three_layer_claim_status": {"consistent": True},
                "manifest_errors": [],
            },
            "_stable_workspace_package_scan": lambda *_args: (
                "a" * 64, {"manifest.json": json.dumps(manifest).encode()}
            ),
            "_validate_captured_workspace_manifest": lambda *_args: None,
        }
        originals = {name: getattr(self.module, name) for name in replacements}
        for name, replacement in replacements.items():
            setattr(self.module, name, replacement)
        self.addCleanup(
            lambda: [setattr(self.module, name, value) for name, value in originals.items()]
        )
        report = {
            "_workspace_path": str(source),
            "identity": {"character_id": 129999, "code_name": "seris_dragon_king"},
        }
        with self.assertRaisesRegex(self.module.ContentGateError, "manifest seal drift"):
            self.module.verify_character_workspace_report(self.spec, report, self.roots)

    def test_workspace_manifest_swap_during_inspection_is_rejected(self) -> None:
        source = Path(self.temp.name) / "racing-workspace"
        package = source / "package"
        package.mkdir(parents=True)
        (source / "workspace.json").write_text(
            '{"character_id":129999,"code_name":"seris_dragon_king"}', encoding="utf-8"
        )
        manifest_path = package / "manifest.json"
        manifest_path.write_text('{"version":"A"}', encoding="utf-8")
        original_load = self.module.load_workspace
        original_inspect = self.module.inspect_workspace
        self.addCleanup(setattr, self.module, "load_workspace", original_load)
        self.addCleanup(setattr, self.module, "inspect_workspace", original_inspect)
        self.module.load_workspace = lambda *_args: SimpleNamespace(package_dir=package)

        def mutate_during_scan(*_args):
            manifest_path.write_text('{"version":"B"}', encoding="utf-8")
            return {"input_digest": "0" * 64}

        self.module.inspect_workspace = mutate_during_scan
        report = {
            "_workspace_path": str(source),
            "identity": {"character_id": 129999, "code_name": "seris_dragon_king"},
        }
        with self.assertRaisesRegex(self.module.ContentGateError, "changed during inspection"):
            self.module.verify_character_workspace_report(self.spec, report, self.roots)
        report = self.workspace_report(character_id=129999, code_name=self.spec.code_name, ready=True)
        report["manifest"] = object()
        with self.assertRaisesRegex(self.module.ContentGateError, "provenance"):
            self.module.verify_character_workspace_report(self.spec, report, self.roots)

    def test_stable_workspace_scan_rechecks_every_captured_byte(self) -> None:
        package = Path(self.temp.name) / "stable-package"
        package.mkdir()
        manifest_path = package / "manifest.json"
        version_a = b'{"qa":{"workspace_input_sha256":"A"}}'
        version_b = b'{"qa":{"workspace_input_sha256":"B"}}'
        manifest_path.write_bytes(version_a)
        original = self.module._stable_read_path
        swapped = False

        def swap_after_first_read(path: Path, label: str) -> bytes:
            nonlocal swapped
            raw = original(path, label)
            if Path(path) == manifest_path and not swapped:
                swapped = True
                manifest_path.write_bytes(version_b)
            return raw

        self.module._stable_read_path = swap_after_first_read
        self.addCleanup(setattr, self.module, "_stable_read_path", original)
        with self.assertRaisesRegex(self.module.ContentGateError, "changed during stable package scan"):
            self.module._stable_workspace_package_scan(package, version_a)

    def test_captured_workspace_manifest_uses_canonical_schema_validator(self) -> None:
        manifest = {"unexpected_top_level": True}
        raw = json.dumps(manifest, separators=(",", ":")).encode()
        with self.assertRaisesRegex(self.module.ContentGateError, "unexpected top-level field"):
            self.module._validate_captured_workspace_manifest(
                manifest, {"manifest.json": raw}
            )

        base = {
            "schema_version": 1,
            "package_id": "fixture",
            "character_id": 149999,
            "code_name": "white_wolf_gerald",
            "package_version": "1.0.0",
            "requires_client_base": "1.4.54",
            "required_capabilities": [],
            "roots": {"common": [], "medium": [], "android": [], "server": []},
            "tables": [{
                "root": "common", "logical_path": "master/fixture.orderedmap",
                "codec_id": "flat", "outer_keys": ["149999"], "inner_keys": [],
            }],
            "skills": {}, "unique_condition": {},
            "qa": {
                "delivery_mode": "production", "release_ready": True,
                "required_assets_present": 37, "required_assets_total": 37,
            },
            "snapshot": {},
        }
        raw = json.dumps(base, separators=(",", ":")).encode()
        with self.assertRaisesRegex(self.module.ContentGateError, "transaction claim.*missing fields"):
            self.module._validate_captured_workspace_manifest(
                base, {"manifest.json": raw}
            )

        base["tables"] = []
        base["qa"]["delivery_mode"] = "draft"
        raw = json.dumps(base, separators=(",", ":")).encode()
        with self.assertRaisesRegex(self.module.ContentGateError, "sealed 37/37 production"):
            self.module._validate_captured_workspace_manifest(
                base, {"manifest.json": raw}
            )

    def test_workspace_semantic_claims_must_own_character_action_and_abilities(self) -> None:
        logical = self.module.CHARACTER_MASTER_LOGICAL
        path = self.roots.common / self.module.hashed_rel(logical)
        raw = path.read_bytes()
        manifest = {
            "roots": {
                "common": [{"logical_path": logical, "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}],
                "medium": [], "android": [], "server": [],
            },
            "tables": [{
                "root": "common", "logical_path": logical, "codec_id": "flat",
                "outer_keys": ["129999"], "inner_keys": [],
            }],
        }
        with self.assertRaisesRegex(self.module.ContentGateError, "semantic ownership claim missing"):
            self.module._verify_workspace_table_claims(self.spec, manifest, self.roots, {})

    def test_workspace_requires_complete_character_specific_auxiliary_contract(self) -> None:
        manifest, server_files = self.complete_seris_manifest()
        omitted = self.module.CHARACTER_SPEECH_MASTER_LOGICAL
        manifest["roots"]["common"] = [
            claim for claim in manifest["roots"]["common"]
            if claim["logical_path"] != omitted
        ]
        manifest["tables"] = [
            claim for claim in manifest["tables"]
            if claim["logical_path"] != omitted
        ]
        with self.assertRaisesRegex(self.module.ContentGateError, "character table contract missing"):
            self.module._verify_workspace_table_claims(
                self.spec, manifest, self.roots, server_files
            )

    def test_workspace_character_ability_references_must_be_exact(self) -> None:
        manifest, server_files = self.complete_seris_manifest()
        row = self.module._character_csv_row(self.roots, self.spec)
        row[19:25] = ["1299991"] * 6
        self.add_ordered(
            self.module.CHARACTER_MASTER_LOGICAL,
            {"129999": core.write_csv_lines([row])},
        )
        payload = json.loads(server_files["cdndata/character.json"])
        payload["129999"] = [row]
        server_files["cdndata/character.json"] = json.dumps(
            payload, separators=(",", ":")
        ).encode()
        with self.assertRaisesRegex(self.module.ContentGateError, "ability references"):
            self.module._verify_workspace_table_claims(
                self.spec, manifest, self.roots, server_files
            )

    def test_workspace_action_program_closure_rejects_dangling_reference(self) -> None:
        manifest, server_files = self.complete_seris_manifest()

        def nested(mapping: dict[str, str | bytes], label: str) -> bytes:
            rows = [
                value if isinstance(value, bytes) else zlib.compress(value.encode("utf-8"))
                for value in mapping.values()
            ]
            return core.build_orderedmap_raw_rows(
                core.OrderedMap(label, list(mapping), rows, Path("[fixture]"))
            )

        programs = (
            "battle/action/skill/definitely_missing/dangling_program",
            self.module.SERIS_ACTION_PROGRAMS[1],
        )
        action_rows: dict[str, str] = {}
        for inner_key, program in zip(("1", "2"), programs):
            row = [""] * 24
            row[:8] = ["skill", "description", "dynamic/skill/atk_common", "true", "520", "520", "1", program]
            action_rows[inner_key] = core.write_csv_lines([row])
        self.add_file(
            self.roots.common,
            self.module.ACTION_SKILL_MASTER_LOGICAL,
            nested({self.spec.code_name: nested(action_rows, "action-inner")}, "action"),
        )
        with self.assertRaisesRegex(self.module.ContentGateError, "action/switched program closure"):
            self.module._verify_workspace_table_claims(
                self.spec, manifest, self.roots, server_files
            )

    def test_stella_workspace_reference_closure_rejects_dangling_normal_skill(self) -> None:
        spec = self.module.CharacterReleaseSpec(139999, "stella_summer_goddess")

        def nested(mapping: dict[str, str | bytes], label: str) -> bytes:
            rows = [
                value if isinstance(value, bytes) else zlib.compress(value.encode("utf-8"))
                for value in mapping.values()
            ]
            return core.build_orderedmap_raw_rows(
                core.OrderedMap(label, list(mapping), rows, Path("[fixture]"))
            )

        character = [""] * 37
        character[0] = spec.code_name
        character[8] = spec.code_name
        character[17] = str(spec.character_id)
        character[19:25] = [f"{spec.character_id}{index}" for index in range(1, 7)]
        self.add_ordered(
            self.module.CHARACTER_MASTER_LOGICAL,
            {str(spec.character_id): core.write_csv_lines([character])},
        )
        self.add_ordered(
            self.module.ABILITY_MASTER_LOGICAL,
            {
                f"{spec.character_id}{index}": core.write_csv_lines([
                    [f"ability-{index}", *([""] * 125)]
                    for _ in range(row_count)
                ])
                for index, row_count in enumerate(
                    self.module.WORKSPACE_ABILITY_ROW_COUNTS[
                        (spec.character_id, spec.code_name)
                    ],
                    1,
                )
            },
        )
        self.add_ordered(
            self.module.LEADER_ABILITY_MASTER_LOGICAL,
            {str(spec.character_id): core.write_csv_lines([
                ["leader", *([""] * 123)]
                for _ in range(self.module.WORKSPACE_LEADER_ROW_COUNTS[
                    (spec.character_id, spec.code_name)
                ])
            ])},
        )
        programs = (
            "battle/action/skill/definitely_missing/dangling_program",
            self.module.WORKSPACE_ACTION_PROGRAMS[(spec.character_id, spec.code_name)][1],
        )
        action_rows: dict[str, str] = {}
        for inner_key, program in zip(("1", "2"), programs):
            row = [""] * 24
            row[7] = program
            action_rows[inner_key] = core.write_csv_lines([row])
        self.add_file(
            self.roots.common,
            self.module.ACTION_SKILL_MASTER_LOGICAL,
            nested({spec.code_name: nested(action_rows, "action-inner")}, "action"),
        )
        with self.assertRaisesRegex(self.module.ContentGateError, "normal action program closure"):
            self.module._bind_workspace_master_reference_closure(
                self.roots, spec, self.module._SnapshotEvidence(self.roots)
            )

        exact_programs = self.module.WORKSPACE_ACTION_PROGRAMS[
            (spec.character_id, spec.code_name)
        ]
        for inner_key, program in zip(("1", "2"), exact_programs):
            row = [""] * 24
            row[7] = program
            action_rows[inner_key] = core.write_csv_lines([row])
        extra_row = [""] * 24
        extra_row[7] = exact_programs[0]
        action_rows["1"] = core.write_csv_lines([extra_row, extra_row])
        self.add_file(
            self.roots.common,
            self.module.ACTION_SKILL_MASTER_LOGICAL,
            nested({spec.code_name: nested(action_rows, "action-inner")}, "action"),
        )
        with self.assertRaisesRegex(self.module.ContentGateError, "exactly 1x24"):
            self.module._bind_workspace_master_reference_closure(
                self.roots, spec, self.module._SnapshotEvidence(self.roots)
            )
        action_rows["1"] = core.write_csv_lines([extra_row])
        self.add_file(
            self.roots.common,
            self.module.ACTION_SKILL_MASTER_LOGICAL,
            nested({spec.code_name: nested(action_rows, "action-inner")}, "action"),
        )
        dsl_raw = wf_dsl.encode_amf3([self.module.STELLA_EFFECT])
        for program in exact_programs:
            compressor = zlib.compressobj(9, zlib.DEFLATED, -15)
            self.add_file(
                self.roots.common,
                wf_dsl.dsl_logical(program),
                compressor.compress(dsl_raw) + compressor.flush(),
            )
        with self.assertRaisesRegex(self.module.ContentGateError, "missing logical"):
            self.module._bind_workspace_master_reference_closure(
                self.roots, spec, self.module._SnapshotEvidence(self.roots)
            )

    def test_gerald_ability_program_must_stay_at_the_exact_semantic_column(self) -> None:
        spec = self.module.CharacterReleaseSpec(149999, "white_wolf_gerald")

        def nested(mapping: dict[str, str | bytes], label: str) -> bytes:
            rows = [
                value if isinstance(value, bytes) else zlib.compress(value.encode("utf-8"))
                for value in mapping.values()
            ]
            return core.build_orderedmap_raw_rows(
                core.OrderedMap(label, list(mapping), rows, Path("[fixture]"))
            )

        character = [""] * 37
        character[0] = character[8] = spec.code_name
        character[17] = str(spec.character_id)
        character[19:25] = [f"{spec.character_id}{index}" for index in range(1, 7)]
        self.add_ordered(
            self.module.CHARACTER_MASTER_LOGICAL,
            {str(spec.character_id): core.write_csv_lines([character])},
        )
        ability_values: dict[str, str] = {}
        for index, row_count in enumerate(
            self.module.WORKSPACE_ABILITY_ROW_COUNTS[(spec.character_id, spec.code_name)], 1
        ):
            rows = [[f"ability-{index}", *([""] * 125)] for _ in range(row_count)]
            if index == 5:
                rows[0][0] = self.module.WORKSPACE_ABILITY_PROGRAMS[
                    (spec.character_id, spec.code_name)
                ][0]
            ability_values[f"{spec.character_id}{index}"] = core.write_csv_lines(rows)
        self.add_ordered(self.module.ABILITY_MASTER_LOGICAL, ability_values)
        leader_rows = [
            ["leader", *([""] * 123)]
            for _ in range(self.module.WORKSPACE_LEADER_ROW_COUNTS[
                (spec.character_id, spec.code_name)
            ])
        ]
        leader_rows[6][80] = self.module.GERALD_UNCLAIMED_POWER_FLIP_KEY
        self.add_ordered(
            self.module.LEADER_ABILITY_MASTER_LOGICAL,
            {str(spec.character_id): core.write_csv_lines(leader_rows)},
        )
        action_values: dict[str, str] = {}
        for inner_key, program in zip(
            ("1", "2"),
            self.module.WORKSPACE_ACTION_PROGRAMS[(spec.character_id, spec.code_name)],
        ):
            row = [""] * 24
            row[7] = program
            action_values[inner_key] = core.write_csv_lines([row])
        self.add_file(
            self.roots.common,
            self.module.ACTION_SKILL_MASTER_LOGICAL,
            nested({spec.code_name: nested(action_values, "action-inner")}, "action"),
        )
        with self.assertRaisesRegex(self.module.ContentGateError, "program location mismatch"):
            self.module._bind_workspace_master_reference_closure(
                self.roots, spec, self.module._SnapshotEvidence(self.roots)
            )

    def test_workspace_auxiliary_claim_cannot_substitute_unrelated_outer_key(self) -> None:
        manifest, server_files = self.complete_seris_manifest()
        logical = self.module.MANA_BOARD2_OPEN_MASTER_LOGICAL
        self.add_ordered(logical, {"129999": "start,end", "999999": "unrelated"})
        claim = next(
            item for item in manifest["tables"]
            if item.get("root") == "common" and item.get("logical_path") == logical
        )
        claim["outer_keys"] = ["999999"]
        with self.assertRaisesRegex(self.module.ContentGateError, "character table contract.*129999"):
            self.module._verify_workspace_table_claims(
                self.spec, manifest, self.roots, server_files
            )

    def test_workspace_flat_target_row_must_decode_to_nonempty_csv(self) -> None:
        manifest, server_files = self.complete_seris_manifest()
        logical = self.module.CHARACTER_SPEECH_MASTER_LOGICAL
        invalid = core.build_orderedmap_raw_rows(core.OrderedMap(
            logical, ["129999"], [b"not-a-valid-row"], Path("[fixture]")
        ))
        self.add_file(self.roots.common, logical, invalid)
        with self.assertRaisesRegex(self.module.ContentGateError, "flat row is unreadable"):
            self.module._verify_workspace_table_claims(
                self.spec, manifest, self.roots, server_files
            )

    def test_workspace_nested_target_row_must_decode_to_nonempty_csv_leaves(self) -> None:
        manifest, server_files = self.complete_seris_manifest()
        logical = self.module.CHARACTER_STATUS_MASTER_LOGICAL
        invalid = core.build_orderedmap_raw_rows(core.OrderedMap(
            logical, ["129999"], [b"not-a-valid-row"], Path("[fixture]")
        ))
        self.add_file(self.roots.common, logical, invalid)
        with self.assertRaisesRegex(self.module.ContentGateError, "nested row is unreadable"):
            self.module._verify_workspace_table_claims(
                self.spec, manifest, self.roots, server_files
            )

    def test_workspace_rejects_every_extra_client_claim_in_wrong_root(self) -> None:
        manifest, _server_files = self.complete_seris_manifest()
        logical = "character/seris_dragon_king/ui/extra_release.png"
        raw = b"extra"
        self.add_file(self.roots.common, logical, raw)
        manifest["roots"]["common"].append({
            "logical_path": logical,
            "size": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        })
        with self.assertRaisesRegex(self.module.ContentGateError, "root mismatch"):
            self.module._manifest_claim_entries(manifest)

    def test_gerald_unclaimed_power_flip_row_must_be_complete_and_decodable(self) -> None:
        spec = self.module.CharacterReleaseSpec(149999, "white_wolf_gerald")
        manifest, server_files = self.install_synthetic_gerald_contract(["", "", ""])
        with self.assertRaisesRegex(self.module.ContentGateError, "exactly three programs"):
            self.module._verify_workspace_table_claims(
                spec, manifest, self.roots, server_files
            )

    def test_gerald_unclaimed_power_flip_programs_require_declared_readable_dsls(self) -> None:
        spec = self.module.CharacterReleaseSpec(149999, "white_wolf_gerald")
        programs = [
            f"battle/action/power_flip/action/override/white_wolf_gerald_pf$white_wolf_gerald_pf_lv{level}"
            for level in range(1, 4)
        ]
        manifest, server_files = self.install_synthetic_gerald_contract(programs)
        with self.assertRaisesRegex(self.module.ContentGateError, "Gerald power-flip DSL"):
            self.module._verify_workspace_table_claims(
                spec, manifest, self.roots, server_files
            )

    def test_gerald_power_flip_dsls_cannot_be_parseable_but_effectless(self) -> None:
        self.add_ordered(
            self.module.POWER_FLIP_ACTION_MASTER_LOGICAL,
            {
                self.module.GERALD_UNCLAIMED_POWER_FLIP_KEY:
                    core.write_csv_lines([list(self.module.GERALD_POWER_FLIP_PROGRAMS)])
            },
        )
        root_claims = {
            "common": {self.module.POWER_FLIP_ACTION_MASTER_LOGICAL},
            "medium": set(),
            "android": set(),
        }
        empty_tree = wf_dsl.encode_amf3([])
        for program in self.module.GERALD_POWER_FLIP_PROGRAMS:
            compressor = zlib.compressobj(9, zlib.DEFLATED, -15)
            logical = wf_dsl.dsl_logical(program)
            self.add_file(
                self.roots.common, logical,
                compressor.compress(empty_tree) + compressor.flush(),
            )
            root_claims["common"].add(logical)
        with self.assertRaisesRegex(self.module.ContentGateError, "effect closure mismatch"):
            self.module._bind_gerald_unclaimed_power_flip(
                self.module._SnapshotEvidence(self.roots), root_claims
            )

    def test_gerald_power_flip_cannot_be_bypassed_by_unrelated_table_claim(self) -> None:
        spec = self.module.CharacterReleaseSpec(149999, "white_wolf_gerald")
        manifest, server_files = self.install_synthetic_gerald_contract(["", "", ""])
        logical = self.module.POWER_FLIP_ACTION_MASTER_LOGICAL
        self.add_ordered(logical, {"not_gerald": "program1,program2,program3"})
        manifest["tables"].append({
            "root": "common", "logical_path": logical, "codec_id": "flat",
            "outer_keys": ["not_gerald"], "inner_keys": [],
        })
        with self.assertRaisesRegex(self.module.ContentGateError, "sanctioned power-flip row is missing"):
            self.module._verify_workspace_table_claims(
                spec, manifest, self.roots, server_files
            )

    def test_workspace_server_table_claims_bind_actual_manifest_shape(self) -> None:
        """The four server JSON tables use the production outer-key convention."""
        manifest, server_files = self.complete_seris_manifest()
        server_dir = Path(self.temp.name) / "package" / "roots" / "server"
        for logical, raw in server_files.items():
            path = server_dir / logical
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        workspace = SimpleNamespace(package_dir=Path(self.temp.name) / "package")
        files = self.module._verify_workspace_server_claims(manifest, workspace)
        # A per-character workspace may carry a historical master digest.  It
        # is structurally valid but evidence must bind the current staged bytes
        # after semantic verification instead.
        manifest["roots"]["common"][0]["sha256"] = "0" * 64
        self.assertEqual((), self.module._manifest_claim_entries(manifest))
        staged_entries = self.module._verify_workspace_table_claims(self.spec, manifest, self.roots, files)
        character_entry = next(entry for entry in staged_entries if entry.path.endswith(self.module.CHARACTER_MASTER_LOGICAL))
        current = (self.roots.common / self.module.hashed_rel(self.module.CHARACTER_MASTER_LOGICAL)).read_bytes()
        self.assertEqual(hashlib.sha256(current).hexdigest(), character_entry.sha256)
        non_master = "character/seris_dragon_king/non-master.bin"
        self.add_file(self.roots.common, non_master, b"current")
        manifest["roots"]["common"].append({"logical_path": non_master, "size": 7, "sha256": "0" * 64})
        with self.assertRaisesRegex(self.module.ContentGateError, "hash mismatch"):
            self.module.verify_manifest_entries(self.module._manifest_claim_entries(manifest), self.roots)
        auxiliary = self.module.SKILL_PREVIEW_CHARACTER_MASTER_LOGICAL
        self.add_ordered(auxiliary, {"129999": "preview"})
        auxiliary_raw = (self.roots.common / self.module.hashed_rel(auxiliary)).read_bytes()
        manifest["roots"]["common"].append({"logical_path": auxiliary, "size": len(auxiliary_raw), "sha256": hashlib.sha256(auxiliary_raw).hexdigest()})
        with self.assertRaisesRegex(self.module.ContentGateError, "no semantic table claim"):
            self.module._verify_workspace_table_claims(self.spec, manifest, self.roots, files)

        manifest, files = self.complete_seris_manifest()
        server_claim = next(
            claim for claim in manifest["tables"]
            if claim.get("root") == "server" and claim.get("logical_path") == "character.json"
        )
        server_claim["outer_keys"] = ["139999"]
        with self.assertRaisesRegex(self.module.ContentGateError, "server outer key missing"):
            self.module._verify_workspace_table_claims(self.spec, manifest, self.roots, files)

        manifest, files = self.complete_seris_manifest()
        payload = json.loads(files["cdndata/character.json"])
        payload["129999"][0][0] = "stella_summer_goddess"
        files["cdndata/character.json"] = json.dumps(payload, separators=(",", ":")).encode()
        with self.assertRaisesRegex(self.module.ContentGateError, "code_name mismatch"):
            self.module._verify_workspace_table_claims(self.spec, manifest, self.roots, files)

        manifest, files = self.complete_seris_manifest()
        payload = json.loads(files["character.json"])
        payload["129999"]["skill_count"] = 999
        files["character.json"] = json.dumps(payload, separators=(",", ":")).encode()
        with self.assertRaisesRegex(self.module.ContentGateError, "skill_count"):
            self.module._verify_workspace_table_claims(self.spec, manifest, self.roots, files)

        manifest, files = self.complete_seris_manifest()
        payload = json.loads(files["mana_node.json"])
        payload["129999"]["1"]["259998201"]["manaCost"] = -1
        files["mana_node.json"] = json.dumps(payload, separators=(",", ":")).encode()
        with self.assertRaisesRegex(self.module.ContentGateError, "mana node"):
            self.module._verify_workspace_table_claims(self.spec, manifest, self.roots, files)

    def test_master_outer_key_and_phase4_literal_are_required(self) -> None:
        self.add_master("139999")
        with self.assertRaisesRegex(self.module.ContentGateError, "master outer key"):
            self.module.build_published_snapshot_evidence(
                self.spec, self.roots, phase4_asset_logicals=self.phase4
            )
        self.add_master("129999")
        with self.assertRaisesRegex(self.module.ContentGateError, "Phase 4 asset literal"):
            self.module.build_published_snapshot_evidence(
                self.spec, self.roots, phase4_asset_logicals={"not/a/permitted/literal"}
            )

    def test_production_character_references_reject_wrong_code_or_missing_ability(self) -> None:
        self.module.build_published_snapshot_evidence(self.spec, self.roots, phase4_asset_logicals=self.phase4)
        row = self.module._character_csv_row(self.roots, self.spec)
        row[0] = "stella_summer_goddess"
        self.add_ordered(self.module.CHARACTER_MASTER_LOGICAL, {"129999": core.write_csv_lines([row])})
        with self.assertRaisesRegex(self.module.ContentGateError, "code_name mismatch"):
            self.module.build_published_snapshot_evidence(self.spec, self.roots, phase4_asset_logicals=self.phase4)
        self.add_master("129999")
        ability = [""] * (unique_condition_id_columns(self.module.ABILITY_MASTER_LOGICAL)[0] + 1)
        ability[unique_condition_id_columns(self.module.ABILITY_MASTER_LOGICAL)[0]] = "22"
        self.add_ordered(self.module.ABILITY_MASTER_LOGICAL, {"1299991": core.write_csv_lines([ability])})
        with self.assertRaisesRegex(self.module.ContentGateError, "ability reference missing"):
            self.module.build_published_snapshot_evidence(self.spec, self.roots, phase4_asset_logicals=self.phase4)

    def test_phase4_missing_and_ambiguous_roots_fail_closed(self) -> None:
        logical = next(iter(self.phase4_members))
        for root in (self.roots.common, self.roots.medium, self.roots.android):
            path = root / self.module.hashed_rel(logical)
            if path.exists():
                path.unlink()
        with self.assertRaisesRegex(self.module.ContentGateError, "missing logical"):
            self.module.build_published_snapshot_evidence(
                self.spec, self.roots, phase4_asset_logicals=self.phase4
            )

    def test_empty_phase4_evidence_is_rejected(self) -> None:
        with self.assertRaisesRegex(self.module.ContentGateError, "canonical contract"):
            self.module.build_published_snapshot_evidence(
                self.spec, self.roots, phase4_asset_logicals=()
            )

    def test_phase4_asset_contract_rejects_missing_extra_and_duplicate_literals(self) -> None:
        self.assertEqual(
            (
                "character/seris_dragon_king/pixelart/special",
                "character/seris_dragon_king/ui/skill_cutin_dragon",
                "character/seris_dragon_king/ui/battle_control_board_dragon",
                "character/seris_dragon_king/ui/battle_member_status_dragon",
            ),
            self.module.SERIS_PHASE4_ASSET_LOGICALS,
        )
        self.assertEqual(8, len(self.phase4_members))
        self.module.build_published_snapshot_evidence(
            self.spec, self.roots, phase4_asset_logicals=self.phase4
        )
        with self.assertRaisesRegex(self.module.ContentGateError, "missing="):
            self.module.build_published_snapshot_evidence(
                self.spec, self.roots, phase4_asset_logicals=self.phase4[:-1]
            )
        with self.assertRaisesRegex(self.module.ContentGateError, "unexpected="):
            self.module.build_published_snapshot_evidence(
                self.spec, self.roots,
                phase4_asset_logicals=(*self.phase4, "sound_effect/seris_dragon_king/unexpected.mp3"),
            )
        with self.assertRaisesRegex(self.module.ContentGateError, "duplicates"):
            self.module.build_published_snapshot_evidence(
                self.spec, self.roots, phase4_asset_logicals=(*self.phase4, self.phase4[0])
            )

    def test_snapshot_asset_in_wrong_root_is_rejected(self) -> None:
        logical = next(item for item in self.required if self.module.expected_root_for_logical(item) == "medium")
        correct = self.roots.medium / self.module.hashed_rel(logical)
        payload = correct.read_bytes()
        correct.unlink()
        self.add_file(self.roots.common, logical, payload)
        with self.assertRaisesRegex(self.module.ContentGateError, "root ownership mismatch"):
            self.module.build_published_snapshot_evidence(self.spec, self.roots, phase4_asset_logicals=self.phase4)

    def test_ui_atlas_remains_in_common_while_ui_png_uses_medium(self) -> None:
        atlas = "character/seris_dragon_king/ui/illustration_setting_sprite_sheet.atlas.amf3.deflate"
        png = "character/seris_dragon_king/ui/skill_cutin_dragon.png"
        self.assertEqual("common", self.module.expected_root_for_logical(atlas))
        self.assertEqual("medium", self.module.expected_root_for_logical(png))

    def test_rogue_validator_requires_every_release_invariant(self) -> None:
        # The pure validator is kept behind one seam so the offline gate can
        # require all weapons, event/round/token, mirrors, rewards and icons.
        class Good:
            event_id = 700099
            round_count = 15
            token_id = 2370099
            weapon_ids = tuple(range(8000101, 8000116))
            missing_logicals = ()
            ready = True

        original = self.module.validate_release_data_only
        self.module.validate_release_data_only = lambda *_args: Good()
        self.addCleanup(setattr, self.module, "validate_release_data_only", original)
        result = self.module.validate_rogue_data(self.roots.common, Path(self.temp.name))
        self.assertTrue(result.ready)
        for field, bad in (("event_id", 700098), ("round_count", 14), ("token_id", 1),
                           ("weapon_ids", (8000101,)), ("missing_logicals", ("icon",))):
            value = Good()
            setattr(value, field, bad)
            self.module.validate_release_data_only = lambda *_args, value=value: value
            with self.assertRaises(self.module.RogueValidationError):
                self.module.validate_rogue_data(self.roots.common, Path(self.temp.name))

    def test_player_1000_must_not_receive_rogue_weapons(self) -> None:
        with self.assertRaisesRegex(self.module.ContentGateError, "Player 1000"):
            self.module.assert_player_has_no_rogue_weapons(
                {"1000": {"equipment": [8000101]}}
            )
        self.module.assert_player_has_no_rogue_weapons({"1000": {"equipment": []}})

    def test_binary_player_1000_snapshot_rejects_rogue_weapon_key(self) -> None:
        def install(keys: list[str]) -> None:
            inner = core.OrderedMap(
                "player-1000", keys, [zlib.compress(b"2" if key == "1" else b"1") for key in keys], Path("[fixture]")
            )
            outer = core.OrderedMap(
                self.module.PLAYER_CHARACTER_LOGICAL,
                ["1000"], [core.build_orderedmap_raw_rows(inner)], Path("[fixture]")
            )
            self.add_file(
                self.roots.common,
                self.module.PLAYER_CHARACTER_LOGICAL,
                core.build_orderedmap_raw_rows(outer),
            )
        install(["1", "129999", "139999", "149999"])
        self.module.verify_player_1000_snapshot(self.roots)
        install(["1", "129999", "139999", "149999", "8000101"])
        with self.assertRaisesRegex(self.module.ContentGateError, "exact release overlay"):
            self.module.verify_player_1000_snapshot(self.roots)

    def test_player_item_snapshot_rejects_rogue_weapon_key_and_equipment_schema_drift(self) -> None:
        def install(keys: list[str]) -> None:
            inner = core.OrderedMap("player-1000-items", keys, [zlib.compress(b"1") for _ in keys], Path("[fixture]"))
            outer = core.OrderedMap(self.module.PLAYER_ITEM_LOGICAL, ["1000"], [core.build_orderedmap_raw_rows(inner)], Path("[fixture]"))
            self.add_file(self.roots.common, self.module.PLAYER_ITEM_LOGICAL, core.build_orderedmap_raw_rows(outer))
        install(["500001"])
        self.module.verify_player_1000_equipment_snapshot(self.roots)
        install(["500001", "8000101"])
        with self.assertRaisesRegex(self.module.ContentGateError, "must not hold rogue weapons"):
            self.module.verify_player_1000_equipment_snapshot(self.roots)
        self.add_file(self.roots.common, self.module.PLAYER_EQUIPMENT_LOGICAL, b"unexpected")
        with self.assertRaisesRegex(self.module.ContentGateError, "schema drift"):
            self.module.verify_player_1000_equipment_snapshot(self.roots)

    def test_client_gate_is_strictly_typed(self) -> None:
        report = Path(self.temp.name) / "client.json"
        valid = self.valid_client_report()
        report.write_text('{"verified":true}', encoding="utf-8")
        with self.assertRaisesRegex(self.module.ContentGateError, "fields"):
            self.module._client_gate(report)
        report.write_text(json.dumps(valid), encoding="utf-8")
        self.assertTrue(self.module._client_gate(report))
        valid["verified"] = False
        report.write_text(json.dumps(valid), encoding="utf-8")
        self.assertFalse(self.module._client_gate(report))
        valid["verified"] = True
        for field, value, error in (
            ("output_sha256", "A" * 64, "lowercase"),
            ("patch_order", [], "patch_order"),
            ("full_resource_version", "1.4.195", "version"),
            ("aligned", False, "aligned"),
            ("signature_schemes", {"v1": True}, "signature"),
        ):
            changed = dict(valid); changed[field] = value
            report.write_text(json.dumps(changed), encoding="utf-8")
            with self.subTest(field=field), self.assertRaisesRegex(self.module.ContentGateError, error):
                self.module._client_gate(report)
        changed = dict(valid); changed["extra"] = True
        report.write_text(json.dumps(changed), encoding="utf-8")
        with self.assertRaisesRegex(self.module.ContentGateError, "fields"):
            self.module._client_gate(report)
        report.write_text('{"verified":true,"verified":false}', encoding="utf-8")
        with self.assertRaisesRegex(self.module.ContentGateError, "duplicate"):
            self.module._client_gate(report)

    def test_client_gate_rejects_empty_stages_broken_chain_and_semantic_drift(self) -> None:
        report = Path(self.temp.name) / "client-stages.json"

        def rejected(changed: dict[str, object], message: str) -> None:
            report.write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaisesRegex(self.module.ContentGateError, message):
                self.module._client_gate(report)

        empty = self.valid_client_report()
        empty["stage_reports"] = [{}, {}, {}, {}]
        rejected(empty, "stage")

        broken = self.valid_client_report()
        broken_stages = [dict(stage) for stage in broken["stage_reports"]]
        broken_stages[2]["input_sha256"] = "0" * 64
        broken["stage_reports"] = broken_stages
        rejected(broken, "chain")

        wrong_sites = self.valid_client_report()
        wrong_site_stages = [dict(stage) for stage in wrong_sites["stage_reports"]]
        wrong_site_stages[1]["site_ids"] = ["preload_seris_dual_form_assets"]
        wrong_sites["stage_reports"] = wrong_site_stages
        rejected(wrong_sites, "Seris")

        wrong_version = self.valid_client_report()
        wrong_version_stages = [dict(stage) for stage in wrong_version["stage_reports"]]
        wrong_version_stages[3]["is_full_package"] = False
        wrong_version["stage_reports"] = wrong_version_stages
        rejected(wrong_version, "resource-version")

        short_abyss_class = self.valid_client_report()
        short_abyss_stages = [dict(stage) for stage in short_abyss_class["stage_reports"]]
        short_abyss_stages[0]["target_class"] = "BattleCharacterLogic"
        short_abyss_class["stage_reports"] = short_abyss_stages
        rejected(short_abyss_class, "abyss stage semantics")

        no_op = self.valid_client_report()
        no_op_stages = [dict(stage) for stage in no_op["stage_reports"]]
        for stage in no_op_stages:
            stage["input_sha256"] = "c" * 64
            stage["output_sha256"] = "c" * 64
        no_op_stages[0]["after_method_sha256"] = no_op_stages[0]["before_method_sha256"]
        no_op_stages[1]["after_hashes"] = dict(no_op_stages[1]["before_hashes"])
        no_op_stages[2]["after_hashes"] = dict(no_op_stages[2]["before_hashes"])
        no_op["stage_reports"] = no_op_stages
        rejected(no_op, "no-op")

        integer_signatures = self.valid_client_report()
        integer_signatures["signature_schemes"] = {"v1": 1, "v2": 1, "v3": 1}
        rejected(integer_signatures, "signature")

    def test_round_gate_allows_1_to_15_and_99_but_rejects_16(self) -> None:
        def install(rounds: range, *, folder_id: int = 1) -> list[str]:
            logical = rogue_validate.rogue_build.Q_QUEST
            table = {rogue_validate.rewards.EVENT_ID: {
                str(value): core.write_csv_lines([[
                    str(700099000 + value), str(folder_id), str(value),
                ]]) for value in rounds
            }}
            table[rogue_validate.rewards.EVENT_ID]["99"] = core.write_csv_lines([["700099099", "2", "0"]])
            self.add_file(self.roots.common, logical, quest.build_node(table))
            payload = {
                str(700099000 + value): {
                    "rushEventId": 700099, "rushEventFolderId": folder_id,
                    "rushEventRound": value,
                }
                for value in rounds
            }
            payload["700099099"] = {
                "rushEventId": 700099, "rushEventFolderId": 2, "rushEventRound": 0,
            }
            assets = Path(self.temp.name) / "round-assets"
            assets.mkdir(exist_ok=True)
            (assets / "rush_event_quest.json").write_text(json.dumps(payload), encoding="utf-8")
            errors: list[str] = []
            count = rogue_validate._validate_offline_rounds(self.roots.common, assets, errors)
            self.assertEqual(15 if len(rounds) > 15 else len(rounds), count)
            return errors
        self.assertEqual([], install(range(1, 16)))
        errors = install(range(1, 17))
        self.assertTrue(any("extra_rounds" in error for error in errors))
        errors = install(range(1, 16), folder_id=9)
        self.assertTrue(any("mapping" in error for error in errors))

        self.assertEqual([], install(range(1, 16)))
        keys = [str(value) for value in range(1, 16)] + ["1", "99"]
        leaves = [
            zlib.compress(core.write_csv_lines([[
                str(700099000 + (int(key) if key != "99" else 99)),
                "2" if key == "99" else "1",
                "0" if key == "99" else key,
            ]]).encode("utf-8"))
            for key in keys
        ]
        event_raw = core.build_orderedmap_raw_rows(
            core.OrderedMap("duplicate-rounds", keys, leaves, Path("[fixture]"))
        )
        top_raw = core.build_orderedmap_raw_rows(core.OrderedMap(
            "rush-event", [rogue_validate.rewards.EVENT_ID], [event_raw], Path("[fixture]")
        ))
        self.add_file(self.roots.common, rogue_validate.rogue_build.Q_QUEST, top_raw)
        duplicate_errors: list[str] = []
        rogue_validate._validate_offline_rounds(
            self.roots.common, Path(self.temp.name) / "round-assets", duplicate_errors
        )
        self.assertTrue(any("duplicate" in error for error in duplicate_errors))

    def test_data_only_never_calls_client_verification(self) -> None:
        original_data = rogue_validate._validate_release_data
        original_rounds = rogue_validate._validate_offline_rounds
        original_client = rogue_validate._validate_client_verification
        self.addCleanup(setattr, rogue_validate, "_validate_release_data", original_data)
        self.addCleanup(setattr, rogue_validate, "_validate_offline_rounds", original_rounds)
        self.addCleanup(setattr, rogue_validate, "_validate_client_verification", original_client)
        rogue_validate._validate_release_data = lambda *_args: rogue_validate.ValidationResult((), ())
        rogue_validate._validate_offline_rounds = lambda *_args: 15
        def forbidden(*_args):
            raise AssertionError("data-only validator touched client verification")
        rogue_validate._validate_client_verification = forbidden
        report = rogue_validate.validate_release_data_only(self.roots.common, Path(self.temp.name))
        self.assertTrue(report.ready)

    def test_validate_offline_content_seris_fallback_and_client_false(self) -> None:
        module = self.module
        class Rogue:
            ready = True
        def evidence(spec, mode="sealed-workspace"):
            unsigned = module.CharacterEvidenceReport(
                {"character_id": spec.character_id, "code_name": spec.code_name}, mode,
                37, 37, True, (), (), "",
            )
            return module.replace(unsigned, seal_sha256=module.sha256_canonical_report(unsigned))
        saved = {name: getattr(module, name) for name in (
            "validate_rogue_data", "verify_player_1000_snapshot", "verify_player_1000_equipment_snapshot", "inspect_workspace", "_workspace_identity_hint",
            "verify_character_workspace_report", "build_published_snapshot_evidence",
            "_load_current_server_assets", "_bind_current_server_character",
        )}
        self.addCleanup(lambda: [setattr(module, name, value) for name, value in saved.items()])
        module.validate_rogue_data = lambda *_args: Rogue()
        module.verify_player_1000_snapshot = lambda *_args: None
        module.verify_player_1000_equipment_snapshot = lambda *_args: None
        module._load_current_server_assets = lambda *_args: object()
        module._bind_current_server_character = lambda _spec, report, *_args, **_kwargs: report
        release_sources = {
            spec.code_name: Path(spec.code_name) for spec in module.CHARACTERS
        }
        identity_by_name = {
            spec.code_name: (spec.character_id, spec.code_name)
            for spec in module.CHARACTERS
        }

        def true_identity(path):
            return identity_by_name[Path(path).name]

        module._workspace_identity_hint = lambda path: (
            (139999, "stella_summer_goddess") if "seris" in str(path) or "stella" in str(path)
            else true_identity(path)
        )
        module.inspect_workspace = lambda path: {
            "identity": {"character_id": 139999 if "seris" in str(path) else 139999, "code_name": "stella_summer_goddess"},
        }
        def verify(spec, report, _roots, **_kwargs):
            if spec.character_id == 129999:
                raise module.ContentGateError("identity mismatch: expected 129999/seris_dragon_king, got 139999/stella_summer_goddess")
            return evidence(spec)
        module.verify_character_workspace_report = verify
        module.build_published_snapshot_evidence = lambda spec, *_args, **_kwargs: evidence(spec, "published-snapshot")
        result = module.validate_offline_content(
            self.roots,
            workspace_sources=release_sources,
            phase4_asset_logicals=self.phase4, assets_dir=Path(self.temp.name),
        )
        self.assertEqual(len(module.CHARACTERS), len(result.characters))
        self.assertIsNone(result.client_gate_ready)
        self.assertTrue(result.ready)
        report = Path(self.temp.name) / "false-client.json"
        report.write_text(json.dumps(self.valid_client_report(verified=False)), encoding="utf-8")
        result = module.validate_offline_content(
            self.roots,
            workspace_sources=release_sources,
            phase4_asset_logicals=self.phase4, assets_dir=Path(self.temp.name), client_report=report,
        )
        self.assertFalse(result.ready)
        def seal_broken(spec, _report, _roots, **_kwargs):
            if spec.character_id == 129999:
                raise module.ContentGateError("workspace manifest seal drift")
            return evidence(spec)
        module.verify_character_workspace_report = seal_broken
        module._workspace_identity_hint = true_identity
        with self.assertRaisesRegex(module.ContentGateError, "seal drift"):
            module.validate_offline_content(
                self.roots,
                workspace_sources=release_sources,
                phase4_asset_logicals=self.phase4, assets_dir=Path(self.temp.name),
            )


if __name__ == "__main__":
    unittest.main()
