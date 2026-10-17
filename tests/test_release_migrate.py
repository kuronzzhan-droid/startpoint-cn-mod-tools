# -*- coding: utf-8 -*-
"""1.4.312 终态迁移测试；全部使用临时 fixture，不读取真实 CN store。"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import wf_mod_tool as core  # noqa: E402
import wf_release_migrate as migrate  # noqa: E402


OLD_NAMES = (
    "灰烬巨剑", "熔核法杖", "深潮长枪", "冻海战锚", "雷鸣双刃",
    "轰电战锤", "裂空战镰", "苍岚长弓", "晨星圣剑", "辉环法器",
    "蚀月大剑", "冥灯魔杖", "深渊征服者", "深渊轮转核", "深渊万象铳",
)
NEW_NAMES = (
    "深渊·灰烬巨剑", "深渊·熔核法杖", "深渊·深潮长枪", "深渊·冻海战锚",
    "深渊·雷鸣双刃", "深渊·轰电战锤", "深渊·裂空战镰", "深渊·苍岚长弓",
    "深渊·晨星圣剑", "深渊·辉环法器", "深渊·蚀月大剑", "深渊·冥灯魔杖",
    "深渊·征服者", "深渊·轮转核", "深渊·万象铳",
)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def flat_table(logical: str, pairs: list[tuple[str, list[str]]]) -> bytes:
    return core.build_orderedmap(core.OrderedMap(
        logical,
        [key for key, _row in pairs],
        [core.write_csv_lines([row]).encode("utf-8") for _key, row in pairs],
        Path("fixture"),
    ))


def decode_flat(raw: bytes, logical: str) -> tuple[list[str], dict[str, bytes]]:
    keys, rows = core._strict_orderedmap_rows(  # type: ignore[attr-defined]
        raw, label=logical, compressed_rows=True,
    )
    return keys, dict(zip(keys, rows))


def row(leaf: bytes) -> list[str]:
    return core.read_csv_lines(leaf.decode("utf-8"))[0]


class Fixture:
    def __init__(self, root: Path, *, crlf_lookup: bool = True) -> None:
        self.root = root
        self.client_root = root / "client"
        self.server_root = root / "server"
        self.client_root.mkdir()
        self.server_root.mkdir()

        char_998 = [f"c998-{index}" for index in range(37)]
        char_998[0], char_998[18] = "touyakiren_ceo_ny26", "绯樱·夜宴序曲"
        char_999 = [f"c999-{index}" for index in range(37)]
        char_999[0], char_999[18] = "ginovi", "破契的黑翼"
        text_998 = [
            "拉芙", "LAFU", "新描述", "NY★绯樱夜宴", "新技能", "新技能描述",
            "新技能＋", "新技能描述", "新技能＋＋", "新技能描述", "绯樱·夜宴序曲", "冲佳苗",
        ]
        text_999 = [
            "基诺维", "GINOVI", "黑鸦描述", "破契的黑鸦", "掠影协奏", "技能描述",
            "掠影协奏＋", "技能描述", "(None)", "(None)", "破契的黑翼", "AI",
        ]
        self.client_rows = {
            (migrate.CHARACTER_LOGICAL, "169998"): char_998,
            (migrate.CHARACTER_LOGICAL, "169999"): char_999,
            (migrate.CHARACTER_TEXT_LOGICAL, "169998"): text_998,
            (migrate.CHARACTER_TEXT_LOGICAL, "169999"): text_999,
        }
        self.client = {
            migrate.CHARACTER_LOGICAL: flat_table(migrate.CHARACTER_LOGICAL, [
                ("sentinel-before", ["keep-char-before"]),
                ("169998", char_998), ("169999", char_999),
                ("sentinel-after", ["keep-char-after"]),
            ]),
            migrate.CHARACTER_TEXT_LOGICAL: flat_table(migrate.CHARACTER_TEXT_LOGICAL, [
                ("sentinel-before", ["keep-text-before"]),
                ("169998", text_998), ("169999", text_999),
                ("sentinel-after", ["keep-text-after"]),
            ]),
        }
        shop_pairs = [("sentinel-before", ["keep-shop-before"])]
        self.shop_before_rows: dict[str, bytes] = {}
        self.shop_after_rows: dict[str, bytes] = {}
        for offset, (old_name, new_name) in enumerate(zip(OLD_NAMES, NEW_NAMES)):
            key = str(9_700_101 + offset)
            cells = [f"{key}-c{column}" for column in range(51)]
            cells[7] = old_name
            before = core.write_csv_lines([cells]).encode("utf-8")
            after_cells = list(cells)
            after_cells[7] = new_name
            after = core.write_csv_lines([after_cells]).encode("utf-8")
            self.shop_before_rows[key] = before
            self.shop_after_rows[key] = after
            shop_pairs.append((key, cells))
        shop_pairs.append(("sentinel-after", ["keep-shop-after"]))
        self.client[migrate.SHOP_LOGICAL] = flat_table(migrate.SHOP_LOGICAL, shop_pairs)
        shop_keys, shop_rows = decode_flat(
            self.client[migrate.SHOP_LOGICAL], migrate.SHOP_LOGICAL,
        )
        terminal_rows = dict(shop_rows)
        terminal_rows.update(self.shop_after_rows)
        self.shop_after = core.build_orderedmap(core.OrderedMap(
            migrate.SHOP_LOGICAL, shop_keys,
            [terminal_rows[key] for key in shop_keys], Path("fixture-terminal"),
        ))

        self.server_values = {
            migrate.SERVER_CHARACTER: {
                "sentinel-before": [["keep-character-before"]],
                "169998": [[*char_998[:18], "旧绯樱夜宴", *char_998[19:]]],
                "169999": [list(char_999)],
                "sentinel-after": [["keep-character-after"]],
            },
            migrate.SERVER_CHARACTER_TEXT: {
                "sentinel-before": [["keep-text-before"]],
                "169998": [["拉芙", "LAFU", "旧描述", "旧昵称", "旧技能", "旧技能描述",
                            "旧技能＋", "旧技能描述", "旧技能＋＋", "旧技能描述", "旧队长技", "冲佳苗"]],
                "169999": [["基诺维", "LAFU", "旧描述", "旧昵称", "旧技能", "旧技能描述",
                            "旧技能＋", "旧技能描述", "(None)", "(None)", "旧队长技", "旧声优"]],
                "sentinel-after": [["keep-text-after"]],
            },
            migrate.SERVER_EQUIPMENT_LOOKUP: {
                "sentinel-before": {"name": "keep-before", "rarity": "0", "category": "剑"},
                **{
                    str(8_000_101 + offset): {
                        "name": old_name, "rarity": "5", "category": "剑" if offset % 2 == 0 else "斧",
                    }
                    for offset, old_name in enumerate(OLD_NAMES)
                },
                "sentinel-after": {"name": "keep-after", "rarity": "0", "category": "饰品"},
            },
        }
        self.server = {
            migrate.SERVER_CHARACTER: json.dumps(
                self.server_values[migrate.SERVER_CHARACTER], ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8"),
            migrate.SERVER_CHARACTER_TEXT: json.dumps(
                self.server_values[migrate.SERVER_CHARACTER_TEXT], ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8"),
            migrate.SERVER_EQUIPMENT_LOOKUP: json.dumps(
                self.server_values[migrate.SERVER_EQUIPMENT_LOOKUP], ensure_ascii=False,
                indent=1,
            ).replace("\n", "\r\n" if crlf_lookup else "\n").encode("utf-8"),
        }
        self.contract = self._contract()
        for logical, raw in self.client.items():
            path = core.table_path(self.client_root, logical)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        for relative, raw in self.server.items():
            path = self.server_root.joinpath(*relative.split("/"))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)

    def _contract(self) -> migrate.FrozenContract:
        client_specs = []
        for (logical, key), cells in self.client_rows.items():
            raw = core.write_csv_lines([cells]).encode("utf-8")
            client_specs.append(migrate.ClientRowSpec(
                logical, key, len(cells), sha(raw),
            ))
        shop_specs = tuple(
            migrate.NameRowSpec(
                str(9_700_101 + offset), old_name, new_name,
                sha(self.shop_before_rows[str(9_700_101 + offset)]),
                sha(self.shop_after_rows[str(9_700_101 + offset)]),
            )
            for offset, (old_name, new_name) in enumerate(zip(OLD_NAMES, NEW_NAMES))
        )
        server_specs = []
        source_for = {
            migrate.SERVER_CHARACTER: migrate.CHARACTER_LOGICAL,
            migrate.SERVER_CHARACTER_TEXT: migrate.CHARACTER_TEXT_LOGICAL,
        }
        for relative, logical in source_for.items():
            for key in ("169998", "169999"):
                before = self.server_values[relative][key]
                after = [self.client_rows[(logical, key)]]
                server_specs.append(migrate.ServerRowSpec(
                    relative, key, sha(canonical(before)), sha(canonical(after)),
                ))
        lookup_specs = []
        lookup = self.server_values[migrate.SERVER_EQUIPMENT_LOOKUP]
        for offset, (old_name, new_name) in enumerate(zip(OLD_NAMES, NEW_NAMES)):
            key = str(8_000_101 + offset)
            before = lookup[key]
            after = {**before, "name": new_name}
            lookup_specs.append(migrate.NameJsonSpec(
                key, old_name, new_name, sha(canonical(before)), sha(canonical(after)),
            ))
        return migrate.FrozenContract(
            migrate.ClientSourceSpec(
                len(self.client[migrate.SHOP_LOGICAL]),
                sha(self.client[migrate.SHOP_LOGICAL]),
            ),
            migrate.ClientSourceSpec(len(self.shop_after), sha(self.shop_after)),
            tuple(client_specs), shop_specs, tuple(server_specs), tuple(lookup_specs),
        )


class PlannerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.fx = Fixture(Path(self.temp.name))

    def test_exact_before_migrates_only_owned_values_and_preserves_layout(self):
        plan = migrate.plan_terminal_migration(
            self.fx.client, self.fx.server, contract=self.fx.contract,
        )

        self.assertIsNot(self.fx.client, plan.client_after)
        self.assertEqual(self.fx.client[migrate.CHARACTER_LOGICAL], plan.client_after[migrate.CHARACTER_LOGICAL])
        self.assertEqual(self.fx.client[migrate.CHARACTER_TEXT_LOGICAL], plan.client_after[migrate.CHARACTER_TEXT_LOGICAL])
        before_keys, before_shop = decode_flat(self.fx.client[migrate.SHOP_LOGICAL], migrate.SHOP_LOGICAL)
        after_keys, after_shop = decode_flat(plan.client_after[migrate.SHOP_LOGICAL], migrate.SHOP_LOGICAL)
        self.assertEqual(before_keys, after_keys)
        for key in before_keys:
            if key not in {spec.key for spec in self.fx.contract.shop_rows}:
                self.assertEqual(before_shop[key], after_shop[key])
        for offset, new_name in enumerate(NEW_NAMES):
            key = str(9_700_101 + offset)
            before_cells, after_cells = row(before_shop[key]), row(after_shop[key])
            self.assertEqual(new_name, after_cells[7])
            self.assertEqual(before_cells[:7] + before_cells[8:], after_cells[:7] + after_cells[8:])

        for relative in (migrate.SERVER_CHARACTER, migrate.SERVER_CHARACTER_TEXT):
            parsed = migrate.strict_json_object(plan.server_after[relative], relative)
            source = migrate.CHARACTER_LOGICAL if relative == migrate.SERVER_CHARACTER else migrate.CHARACTER_TEXT_LOGICAL
            self.assertEqual(list(self.fx.server_values[relative]), list(parsed))
            self.assertEqual(self.fx.server_values[relative]["sentinel-before"], parsed["sentinel-before"])
            self.assertEqual(self.fx.server_values[relative]["sentinel-after"], parsed["sentinel-after"])
            for key in ("169998", "169999"):
                self.assertEqual([self.fx.client_rows[(source, key)]], parsed[key])
            self.assertNotIn(b"\n", plan.server_after[relative])

        lookup_raw = plan.server_after[migrate.SERVER_EQUIPMENT_LOOKUP]
        self.assertIn(b"\r\n", lookup_raw)
        lookup = migrate.strict_json_object(lookup_raw, "lookup")
        self.assertEqual(list(self.fx.server_values[migrate.SERVER_EQUIPMENT_LOOKUP]), list(lookup))
        for offset, new_name in enumerate(NEW_NAMES):
            key = str(8_000_101 + offset)
            self.assertEqual(new_name, lookup[key]["name"])
            self.assertEqual(
                {k: v for k, v in self.fx.server_values[migrate.SERVER_EQUIPMENT_LOOKUP][key].items() if k != "name"},
                {k: v for k, v in lookup[key].items() if k != "name"},
            )
        self.assertTrue(plan.changes)

    def test_second_run_is_byte_identical_zero_change(self):
        first = migrate.plan_terminal_migration(self.fx.client, self.fx.server, contract=self.fx.contract)
        second = migrate.plan_terminal_migration(first.client_after, first.server_after, contract=self.fx.contract)
        self.assertEqual((), second.changes)
        self.assertEqual(first.client_after, second.client_after)
        self.assertEqual(first.server_after, second.server_after)

    def test_shop_rejects_valid_unowned_row_drift_by_whole_source_digest(self):
        client = dict(self.fx.client)
        keys, rows = decode_flat(client[migrate.SHOP_LOGICAL], migrate.SHOP_LOGICAL)
        rows["sentinel-before"] = core.write_csv_lines([["foreign-sentinel"]]).encode("utf-8")
        client[migrate.SHOP_LOGICAL] = core.build_orderedmap(core.OrderedMap(
            migrate.SHOP_LOGICAL, keys, [rows[key] for key in keys], Path("drift"),
        ))

        with self.assertRaisesRegex(migrate.MigrationError, "source|drift"):
            migrate.plan_terminal_migration(client, self.fx.server, contract=self.fx.contract)

    def test_lookup_indent1_lf_without_trailing_newline_is_preserved(self):
        second_root = Path(self.temp.name) / "lf"
        second_root.mkdir()
        fixture = Fixture(second_root, crlf_lookup=False)
        plan = migrate.plan_terminal_migration(
            fixture.client, fixture.server, contract=fixture.contract,
        )
        raw = plan.server_after[migrate.SERVER_EQUIPMENT_LOOKUP]
        self.assertIn(b"\n ", raw)
        self.assertNotIn(b"\r\n", raw)
        self.assertFalse(raw.endswith(b"\n"))

    def test_task3a_contract_adapter_keeps_exact_ids_count_and_source_gate(self):
        import wf_local_server_contract as source_contract

        source = source_contract.load_contract(migrate.DEFAULT_CONTRACT_PATH)
        source_shop = source.client_tables[0]
        contract = migrate.load_frozen_contract()
        self.assertEqual(18, contract.source_member_count)
        self.assertEqual(
            (source_shop.preimage.source_size, source_shop.preimage.source_sha256),
            (contract.shop_preimage.size, contract.shop_preimage.sha256),
        )
        self.assertEqual(
            (source_shop.terminal.source_size, source_shop.terminal.source_sha256),
            (contract.shop_terminal.size, contract.shop_terminal.sha256),
        )

    def test_task3a_contract_adapter_rejects_replaced_ignored_member_scope(self):
        payload = json.loads(migrate.DEFAULT_CONTRACT_PATH.read_text(encoding="utf-8"))
        payload["server_members"][-1]["logical_path"] = "rogue_event_alias.json"
        candidate = Path(self.temp.name) / "scope-drift.json"
        candidate.write_text(
            json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8",
        )

        with self.assertRaisesRegex(migrate.MigrationError, "scope|member"):
            migrate.load_frozen_contract(candidate)

    def test_client_character_rows_are_exact_read_only_sources(self):
        broken = dict(self.fx.client)
        keys, rows = decode_flat(broken[migrate.CHARACTER_TEXT_LOGICAL], migrate.CHARACTER_TEXT_LOGICAL)
        text = row(rows["169999"])
        text[1] = "LAFU"
        rows["169999"] = core.write_csv_lines([text]).encode("utf-8")
        broken[migrate.CHARACTER_TEXT_LOGICAL] = core.build_orderedmap(core.OrderedMap(
            migrate.CHARACTER_TEXT_LOGICAL, keys, [rows[key] for key in keys], Path("broken"),
        ))
        with self.assertRaisesRegex(migrate.MigrationError, "169999"):
            migrate.plan_terminal_migration(broken, self.fx.server, contract=self.fx.contract)

    def test_shop_rejects_non_name_drift_foreign_name_and_mixed_group(self):
        for mode in ("non-name", "foreign", "mixed"):
            with self.subTest(mode=mode):
                client = dict(self.fx.client)
                keys, rows = decode_flat(client[migrate.SHOP_LOGICAL], migrate.SHOP_LOGICAL)
                key = "9700101"
                cells = row(rows[key])
                if mode == "non-name":
                    cells[19] = "999"
                elif mode == "foreign":
                    cells[7] = "外来武器"
                else:
                    cells[7] = NEW_NAMES[0]
                rows[key] = core.write_csv_lines([cells]).encode("utf-8")
                client[migrate.SHOP_LOGICAL] = core.build_orderedmap(core.OrderedMap(
                    migrate.SHOP_LOGICAL, keys, [rows[item] for item in keys], Path("broken"),
                ))
                with self.assertRaisesRegex(migrate.MigrationError, "shop|9700101"):
                    migrate.plan_terminal_migration(client, self.fx.server, contract=self.fx.contract)

    def test_lookup_rejects_non_name_drift_foreign_name_and_mixed_group(self):
        for mode in ("non-name", "foreign", "mixed"):
            with self.subTest(mode=mode):
                server = dict(self.fx.server)
                lookup = copy.deepcopy(self.fx.server_values[migrate.SERVER_EQUIPMENT_LOOKUP])
                if mode == "non-name":
                    lookup["8000101"]["rarity"] = "4"
                elif mode == "foreign":
                    lookup["8000101"]["name"] = "外来武器"
                else:
                    lookup["8000101"]["name"] = NEW_NAMES[0]
                server[migrate.SERVER_EQUIPMENT_LOOKUP] = json.dumps(
                    lookup, ensure_ascii=False, indent=1,
                ).replace("\n", "\r\n").encode("utf-8")
                with self.assertRaisesRegex(migrate.MigrationError, "lookup|8000101"):
                    migrate.plan_terminal_migration(self.fx.client, server, contract=self.fx.contract)

    def test_server_rows_allow_expected_cross_file_mix_but_reject_foreign_value(self):
        first = migrate.plan_terminal_migration(self.fx.client, self.fx.server, contract=self.fx.contract)
        mixed = dict(self.fx.server)
        mixed[migrate.SERVER_CHARACTER] = first.server_after[migrate.SERVER_CHARACTER]
        plan = migrate.plan_terminal_migration(self.fx.client, mixed, contract=self.fx.contract)
        self.assertTrue(plan.changes)

        foreign = dict(self.fx.server)
        payload = copy.deepcopy(self.fx.server_values[migrate.SERVER_CHARACTER_TEXT])
        payload["169999"][0][2] += "x"
        foreign[migrate.SERVER_CHARACTER_TEXT] = json.dumps(
            payload, ensure_ascii=False, separators=(",", ":"),
        ).encode("utf-8")
        with self.assertRaisesRegex(migrate.MigrationError, "169999"):
            migrate.plan_terminal_migration(self.fx.client, foreign, contract=self.fx.contract)

    def test_duplicate_json_key_and_unknown_layout_are_rejected(self):
        server = dict(self.fx.server)
        server[migrate.SERVER_CHARACTER] = b'{"169998":[],"169998":[]}'
        with self.assertRaisesRegex(migrate.MigrationError, "duplicate"):
            migrate.plan_terminal_migration(self.fx.client, server, contract=self.fx.contract)

        server = dict(self.fx.server)
        value = self.fx.server_values[migrate.SERVER_EQUIPMENT_LOOKUP]
        server[migrate.SERVER_EQUIPMENT_LOOKUP] = json.dumps(
            value, ensure_ascii=False, indent=2,
        ).encode("utf-8")
        with self.assertRaisesRegex(migrate.MigrationError, "format"):
            migrate.plan_terminal_migration(self.fx.client, server, contract=self.fx.contract)


class CliTransactionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.fx = Fixture(Path(self.temp.name))
        self.args = [
            "--client-root", str(self.fx.client_root),
            "--server-root", str(self.fx.server_root),
        ]

    def snapshot(self) -> dict[Path, bytes]:
        targets = [
            core.table_path(self.fx.client_root, logical)
            for logical in migrate.CLIENT_LOGICALS
        ] + [
            self.fx.server_root.joinpath(*relative.split("/"))
            for relative in migrate.SERVER_FILES
        ]
        return {path: path.read_bytes() for path in targets}

    def test_default_dry_run_and_bad_confirmation_never_write(self):
        before = self.snapshot()
        self.assertEqual(0, migrate.main(self.args, contract=self.fx.contract))
        self.assertEqual(before, self.snapshot())
        self.assertEqual(1, migrate.main([
            *self.args, "--write", "--confirm", "WRONG",
        ], contract=self.fx.contract))
        self.assertEqual(before, self.snapshot())

    def test_write_readback_then_second_run_performs_zero_replaces(self):
        args = [*self.args, "--write", "--confirm", migrate.CONFIRM_TOKEN]
        self.assertEqual(0, migrate.main(args, contract=self.fx.contract))
        after = self.snapshot()
        with mock.patch.object(migrate, "_commit_replace") as replace:
            self.assertEqual(0, migrate.main(args, contract=self.fx.contract))
        replace.assert_not_called()
        self.assertEqual(after, self.snapshot())

    def test_late_commit_failure_rolls_back_all_exact_before_images(self):
        before = self.snapshot()
        real_replace = migrate._commit_replace
        real_restore = migrate._atomic_restore
        calls = 0
        restored: list[Path] = []

        def fail_third(staged: Path, target: Path) -> None:
            nonlocal calls
            calls += 1
            if calls == 3:
                raise OSError("injected third replace failure")
            real_replace(staged, target)

        def record_restore(target: Path, raw: bytes) -> None:
            restored.append(target)
            real_restore(target, raw)

        with mock.patch.object(migrate, "_commit_replace", side_effect=fail_third), \
                mock.patch.object(migrate, "_atomic_restore", side_effect=record_restore):
            result = migrate.main([
                *self.args, "--write", "--confirm", migrate.CONFIRM_TOKEN,
            ], contract=self.fx.contract)
        self.assertEqual(1, result)
        self.assertEqual(2, len(restored))
        self.assertEqual(before, self.snapshot())

    def test_readback_failure_rolls_back_all_exact_before_images(self):
        before = self.snapshot()
        with mock.patch.object(
            migrate, "_verify_readback", side_effect=RuntimeError("injected readback failure")
        ):
            result = migrate.main([
                *self.args, "--write", "--confirm", migrate.CONFIRM_TOKEN,
            ], contract=self.fx.contract)
        self.assertEqual(1, result)
        self.assertEqual(before, self.snapshot())

    def test_per_target_drift_rolls_back_prior_replaces_without_overwriting_drift(self):
        before = self.snapshot()
        drift_target = self.fx.server_root / "cdndata" / "character_text.json"
        foreign = b'{"foreign":"concurrent-writer"}'
        real_replace = migrate._commit_replace
        calls = 0

        def drift_before_third(staged: Path, target: Path) -> None:
            nonlocal calls
            calls += 1
            real_replace(staged, target)
            if calls == 2:
                drift_target.write_bytes(foreign)

        with mock.patch.object(migrate, "_commit_replace", side_effect=drift_before_third):
            result = migrate.main([
                *self.args, "--write", "--confirm", migrate.CONFIRM_TOKEN,
            ], contract=self.fx.contract)

        self.assertEqual(1, result)
        after = self.snapshot()
        self.assertEqual(foreign, after.pop(drift_target))
        before.pop(drift_target)
        self.assertEqual(before, after)

    def test_same_bytes_new_identity_before_third_target_is_not_overwritten(self):
        drift_target = self.fx.server_root / "cdndata" / "character_text.json"
        original = drift_target.read_bytes()
        real_replace = migrate._commit_replace
        calls = 0

        def replace_identity_before_third(staged: Path, target: Path) -> None:
            nonlocal calls
            calls += 1
            real_replace(staged, target)
            if calls == 2:
                replacement = drift_target.with_name(".concurrent-character-text")
                replacement.write_bytes(original)
                os.replace(replacement, drift_target)

        with mock.patch.object(
            migrate, "_commit_replace", side_effect=replace_identity_before_third,
        ):
            result = migrate.main([
                *self.args, "--write", "--confirm", migrate.CONFIRM_TOKEN,
            ], contract=self.fx.contract)

        self.assertEqual(1, result)
        self.assertEqual(2, calls)
        self.assertEqual(original, drift_target.read_bytes())


if __name__ == "__main__":
    unittest.main()
