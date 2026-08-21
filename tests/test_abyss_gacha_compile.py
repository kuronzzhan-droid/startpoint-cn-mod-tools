import copy
from datetime import datetime
import json
import unittest
import zlib
from pathlib import Path

import wf_mod_tool as core
from wf_character_pack import TableClaim, DEFAULT_CODECS
from wf_release import JsonObjectCodec

try:
    import wf_abyss_gacha_contract as contract
    from wf_abyss_gacha_compile import compile_abyss_limited_gacha
except ImportError:
    contract = None
    compile_abyss_limited_gacha = None


IDS = (
    129999, 139997, 139998, 139999, 149998,
    149999, 169998, 169999, 179999,
)
NON_EXCHANGEABLE_IDS = (139997,)
STANDARD_EXCHANGE_IDS = (141129, 161141, 123001, 131182)
EXPECTED_CLAIMS = {
    ("common", "master/gacha/gacha.orderedmap", "flat", ("990001",)),
    (
        "common", "master/gacha/gacha_feature_content.orderedmap",
        "raw_outer", ("990001",),
    ),
    (
        "common", "master/gacha_odds/cnmod_abyss_limited_gacha_rarity.orderedmap",
        "raw_outer", ("cnmod_abyss_limited_gacha_rarity",),
    ),
    (
        "common",
        "master/gacha_odds/cnmod_abyss_limited_gacha_character_3.orderedmap",
        "raw_outer", ("cnmod_abyss_limited_gacha_character_3",),
    ),
    (
        "common",
        "master/gacha_odds/cnmod_abyss_limited_gacha_character_4.orderedmap",
        "raw_outer", ("cnmod_abyss_limited_gacha_character_4",),
    ),
    (
        "common",
        "master/gacha_odds/cnmod_abyss_limited_gacha_character_5.orderedmap",
        "raw_outer", ("cnmod_abyss_limited_gacha_character_5",),
    ),
    (
        "common", "master/rich_text/rich_text_html.orderedmap", "flat",
        ("rich_text/cnmod_abyss_limited_gacha_note",),
    ),
    ("server", "gacha.json", "json_object", ("990001",)),
    ("server", "cdndata/gacha.json", "json_object", ("990001",)),
    (
        "server", "cdndata/gacha_feature_content.json", "json_object",
        ("990001",),
    ),
}
OFFICIAL_57 = [
    "fukubukuro_gacha_ny2021", "2021年福袋扭蛋", "97",
    "dynamic/gacha_list_banner/fukubukuro_gacha_ny2021", "2", "", "", "", "",
    "1", "4", "normal_rarity", "rich_text/gacha_note", "0",
    "new_character_pickup_28_character_3",
    "new_character_pickup_28_character_4",
    "new_character_pickup_28_character_5", "normal", "normal_guarantee",
    "false", "false", "false", "", "", "", "", "", "20065", "20064",
    "2020-12-31 12:00:00", "2023-12-31 11:59:59", "(None)", "false",
    "116", "117", "169", "170", "(None)", "false", "(None)", "(None)",
    "(None)", "(None)", "false", "false", "(None)", "false",
]


def _flat(logical, rows):
    return core.build_orderedmap(core.OrderedMap(
        logical, list(rows), [value.encode("utf-8") for value in rows.values()], Path("<fixture>")
    ))


def _raw_outer(logical, rows):
    return core.build_orderedmap_raw_rows(core.OrderedMap(
        logical, list(rows), list(rows.values()), Path("<fixture>")
    ))


def _nested_row(rows):
    inner = core.OrderedMap(
        "<inner>", list(rows), [value.encode("utf-8") for value in rows.values()], Path("<fixture>")
    )
    return core.build_orderedmap(inner)


def _json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _character_row(character_id, rarity=5):
    row = [f"custom_{character_id}", "1", str(rarity)] + [""] * 34
    row[17] = str(character_id)
    return core.write_csv_lines([row])


def _official_runtime_57():
    return {
        "type": 0, "paymentType": 0, "pageKind": 2,
        "singleCost": 150, "multiCost": 1500, "discountCost": 50,
        "onceTicketItemId": 20065, "tenTicketItemId": 20064,
        "wildcardTicketAvailable": False, "rarityOddsId": "normal_rarity",
        "guaranteeRarity": 4,
        "rankRates": {"normal": [50, 250, 700], "multiGuarantee": [50, 950]},
        "movieName": "normal", "guaranteeMovieName": "normal_guarantee",
        "toUseOddsUpAsTrialReading": False, "canBeStartDashExchange": False,
        "startDate": "2020-12-31 12:00:00", "endDate": "2023-12-31 11:59:59",
        "name": "2021年福袋扭蛋", "pool": {"1": [], "2": [], "3": []},
    }


def _standard_donor_runtime():
    def item(character_id, rank, odds, *, limited=False):
        return {
            "id": character_id,
            "rank": rank,
            "odds": odds,
            "isRateUp": True,
            "isLimited": limited,
            "isExchangeable": True,
            "rarity": 500.0,
            "trialReadingForced": True,
        }

    return {
        "rankRates": {"normal": [50, 250, 700], "multiGuarantee": [50, 950]},
        "pool": {
            "1": [
                item(111001, 5, 9),
                item(111002, 5, 7),
                item(111003, 5, 5, limited=True),
            ],
            "2": [item(211001, 4, 31), item(221001, 4, 29)],
            "3": [item(311001, 3, 17), item(321001, 3, 13)],
        },
    }


def _sources():
    character_rows = {"1": _character_row(1)}
    character_rows.update({str(value): _character_row(value) for value in IDS})
    character_rows.update({
        str(value): _character_row(value) for value in STANDARD_EXCHANGE_IDS
    })
    character_rows.update({
        "111001": _character_row(111001, 5),
        "111002": _character_row(111002, 5),
        "111003": _character_row(111003, 5),
        "211001": _character_row(211001, 4),
        "221001": _character_row(221001, 4),
        "311001": _character_row(311001, 3),
        "321001": _character_row(321001, 3),
    })
    common = {
        "master/character/character.orderedmap": _flat(
            "master/character/character.orderedmap", character_rows
        ),
        "master/gacha/gacha.orderedmap": _flat(
            "master/gacha/gacha.orderedmap",
            {"1": "legacy,row", "57": core.write_csv_lines([OFFICIAL_57])},
        ),
        "master/gacha/gacha_feature_content.orderedmap": _raw_outer(
            "master/gacha/gacha_feature_content.orderedmap",
            {
                "1": _nested_row({"1": "1,legacy,,,,,(None),,"}),
                "57": _nested_row({
                    "1": "1,dynamic/gacha_banner/fukubukuro_gacha_ny2021,"
                    ",,,,(None),,"
                }),
            },
        ),
        "master/rich_text/rich_text_html.orderedmap": _flat(
            "master/rich_text/rich_text_html.orderedmap", {"rich_text/gacha_note": ""}
        ),
    }
    server_character = {"1": {"name": "legacy", "rarity": 1}}
    server_character.update({str(value): {"name": str(value), "rarity": 5} for value in IDS})
    server_character.update({
        str(value): {"name": str(value), "rarity": 5}
        for value in STANDARD_EXCHANGE_IDS
    })
    server_character.update({
        "111001": {"name": "111001", "rarity": 5},
        "111002": {"name": "111002", "rarity": 5},
        "111003": {"name": "111003", "rarity": 5},
        "211001": {"name": "211001", "rarity": 4},
        "221001": {"name": "221001", "rarity": 4},
        "311001": {"name": "311001", "rarity": 3},
        "321001": {"name": "321001", "rarity": 3},
    })
    server = {
        "character.json": _json(server_character),
        "gacha.json": _json({
            "1": {"pool": {"1": [{"id": 111001}], "2": [], "3": []}},
            "57": _official_runtime_57(),
            "700004": _standard_donor_runtime(),
        }),
        "cdndata/gacha.json": _json({"1": [["legacy"]], "57": [OFFICIAL_57]}),
        "cdndata/gacha_feature_content.json": _json({
            "1": {"1": [["1", "legacy", "", "", "", "", "(None)", "", ""]]},
            "57": {"1": [[
                "1", "dynamic/gacha_banner/fukubukuro_gacha_ny2021",
                "gacha/feature_movie/release_gacha/top/feature", "", "", "",
                "(None)", "", "",
            ]]},
        }),
    }
    return common, server


def _decode_flat(raw, logical):
    keys, rows = core._strict_orderedmap_rows(raw, label=logical, compressed_rows=True)
    return dict(zip(keys, rows))


def _decode_nested(raw, logical):
    keys, rows = core._strict_orderedmap_rows(raw, label=logical, compressed_rows=False)
    result = {}
    for outer, inner_raw in zip(keys, rows):
        inner_keys, inner_rows = core._strict_orderedmap_rows(
            inner_raw, label=f"{logical}#{outer}", compressed_rows=True
        )
        result[outer] = dict(zip(inner_keys, inner_rows))
    return result


class AbyssGachaCompileTests(unittest.TestCase):
    def _require_module(self):
        if contract is None or compile_abyss_limited_gacha is None:
            self.fail("abyss gacha compiler modules are missing")

    def _compile(self):
        self._require_module()
        common, server = _sources()
        return common, server, compile_abyss_limited_gacha(
            common, server, existing_common_paths=set(common)
        )

    def test_contract_is_ticket_only_standard_rate_pool_with_nine_limited_rate_up_characters(self):
        _, _, result = self._compile()
        self.assertEqual(990001, contract.GACHA_ID)
        self.assertEqual("cnmod_abyss_limited_gacha", contract.CODE_NAME)
        self.assertEqual(IDS, contract.CHARACTER_IDS)
        self.assertEqual(
            NON_EXCHANGEABLE_IDS, contract.NON_EXCHANGEABLE_CHARACTER_IDS
        )
        row = core.read_csv_lines(_decode_flat(
            result["files"][contract.GACHA_MASTER_LOGICAL], contract.GACHA_MASTER_LOGICAL
        )[contract.GACHA_KEY].decode("utf-8"))[0]
        self.assertEqual(47, len(row))
        self.assertEqual("2", row[4])
        self.assertEqual(["", "", ""], row[5:8])
        self.assertEqual("4", row[10])
        self.assertEqual("false", row[20])
        self.assertEqual(["999013", "999014"], row[27:29])
        self.assertEqual("normal", row[17])
        self.assertEqual("normal_guarantee", row[18])
        self.assertEqual("true", row[44])
        start = datetime.strptime(row[29], "%Y-%m-%d %H:%M:%S")
        self.assertLessEqual(start, datetime(2024, 8, 14, 12, 0, 0))

        runtime = json.loads(result["files"]["gacha.json"])[contract.GACHA_KEY]
        self.assertEqual(2, runtime["pageKind"])
        self.assertEqual(row[29], runtime["startDate"])
        self.assertEqual(999013, runtime["onceTicketItemId"])
        self.assertEqual(999014, runtime["tenTicketItemId"])
        self.assertFalse(runtime["wildcardTicketAvailable"])
        self.assertEqual(4, runtime["guaranteeRarity"])
        self.assertEqual([50, 250, 700], runtime["rankRates"]["normal"])
        self.assertEqual([50, 950], runtime["rankRates"]["multiGuarantee"])
        self.assertEqual(
            [211001, 221001], [entry["id"] for entry in runtime["pool"]["2"]]
        )
        self.assertEqual(
            [311001, 321001], [entry["id"] for entry in runtime["pool"]["3"]]
        )
        pool = runtime["pool"]["1"]
        self.assertEqual(
            [*IDS, 111001, 111002, *STANDARD_EXCHANGE_IDS],
            [entry["id"] for entry in pool],
        )
        self.assertNotIn(111003, [entry["id"] for entry in pool])
        limited = pool[:len(IDS)]
        standard = pool[len(IDS):]
        total_weight = sum(entry["odds"] for entry in pool)
        for entry in limited:
            self.assertEqual(5, entry["rank"])
            self.assertAlmostEqual(
                1 / 900, 0.05 * entry["odds"] / total_weight, places=12
            )
            self.assertAlmostEqual(
                1000.0 * entry["odds"] / total_weight, entry["rarity"], places=9
            )
            self.assertTrue(entry["isRateUp"])
            self.assertTrue(entry["isLimited"])
            self.assertEqual(
                entry["id"] not in NON_EXCHANGEABLE_IDS, entry["isExchangeable"]
            )
        self.assertAlmostEqual(
            0.01,
            0.05 * sum(entry["odds"] for entry in limited) / total_weight,
        )
        self.assertAlmostEqual(
            0.04,
            0.05 * sum(entry["odds"] for entry in standard) / total_weight,
        )
        for entry in standard:
            self.assertFalse(entry["isRateUp"])
            self.assertFalse(entry["isLimited"])
            self.assertEqual(
                entry["id"] in STANDARD_EXCHANGE_IDS,
                entry["isExchangeable"],
            )

    def test_odds_feature_and_rich_text_read_back_exactly(self):
        _, _, result = self._compile()
        rarity = _decode_nested(
            result["files"][contract.RARITY_ODDS_LOGICAL], contract.RARITY_ODDS_LOGICAL
        )[contract.RARITY_ODDS_ID]
        self.assertEqual([b"5,50", b"4,250", b"3,700"], list(rarity.values()))
        three = _decode_nested(
            result["files"][contract.CHARACTER_3_ODDS_LOGICAL],
            contract.CHARACTER_3_ODDS_LOGICAL,
        )[contract.CHARACTER_3_ODDS_ID]
        four = _decode_nested(
            result["files"][contract.CHARACTER_4_ODDS_LOGICAL],
            contract.CHARACTER_4_ODDS_LOGICAL,
        )[contract.CHARACTER_4_ODDS_ID]
        self.assertEqual(
            [
                b"311001,3,17,false,false,false,false",
                b"321001,3,13,false,false,false,false",
            ],
            list(three.values()),
        )
        self.assertEqual(
            [
                b"211001,4,31,false,false,false,false",
                b"221001,4,29,false,false,false,false",
            ],
            list(four.values()),
        )
        five = _decode_nested(
            result["files"][contract.CHARACTER_5_ODDS_LOGICAL], contract.CHARACTER_5_ODDS_LOGICAL
        )[contract.CHARACTER_5_ODDS_ID]
        self.assertEqual(
            [
                *[
                    "{},5,6,true,true,{},false".format(
                        value, str(value not in NON_EXCHANGEABLE_IDS).lower()
                    ).encode()
                    for value in IDS
                ],
                b"111001,5,36,false,false,false,false",
                b"111002,5,36,false,false,false,false",
                *[
                    f"{value},5,36,false,false,true,false".encode()
                    for value in STANDARD_EXCHANGE_IDS
                ],
            ],
            list(five.values()),
        )
        feature = _decode_nested(
            result["files"][contract.FEATURE_LOGICAL], contract.FEATURE_LOGICAL
        )[contract.GACHA_KEY]["1"].decode("utf-8")
        client_feature = core.read_csv_lines(feature)[0]
        self.assertEqual("1", client_feature[0])
        self.assertEqual(contract.TOP_BANNER_LOGICAL, client_feature[1])
        self.assertEqual("", client_feature[2])
        server_feature = json.loads(
            result["files"]["cdndata/gacha_feature_content.json"]
        )[contract.GACHA_KEY]["1"][0]
        self.assertEqual(contract.TOP_BANNER_LOGICAL, server_feature[1])
        self.assertEqual("", server_feature[2])
        self.assertEqual(feature, core.write_csv_lines([server_feature]))
        note = zlib.decompress(result["files"][contract.RICH_TEXT_BODY_LOGICAL], -15).decode()
        self.assertIn("深渊单抽券", note)
        self.assertIn("深渊十连券", note)
        self.assertIn("仅可使用深渊单抽券或深渊十连券", note)
        self.assertIn("不接受星导石或付费星导石抽取", note)
        self.assertNotIn("每日1次付费星导石", note)
        self.assertIn("通用角色扭蛋券", note)
        self.assertIn("★5角色总出现概率为5%", note)
        self.assertIn("9名深渊限定角色合计出现概率为1%", note)
        self.assertIn("单人均为1/9%（约0.111%）", note)
        self.assertIn("其余4%由普通★5角色均分", note)
        self.assertIn("每次抽取累计1点兑换点数", note)
        self.assertIn("其中8名深渊限定角色各需250点兑换", note)
        self.assertIn("泳皇女EX（莉莉丝）不可用兑换点数兑换", note)
        self.assertIn("250点", note)
        self.assertEqual(2, note.count("250点兑换"))
        self.assertNotIn("各需50点兑换", note)
        self.assertNotIn("0.5%", note)

    def test_rejects_missing_or_malformed_standard_pool_donor(self):
        self._require_module()
        common, server = _sources()
        missing = dict(server)
        gachas = json.loads(missing["gacha.json"])
        gachas.pop("700004")
        missing["gacha.json"] = _json(gachas)
        with self.assertRaisesRegex(ValueError, "standard pool donor"):
            compile_abyss_limited_gacha(common, missing, existing_common_paths=set(common))

        malformed = dict(server)
        gachas = json.loads(malformed["gacha.json"])
        gachas["700004"]["pool"]["2"][0]["rank"] = 5
        malformed["gacha.json"] = _json(gachas)
        with self.assertRaisesRegex(ValueError, "standard pool donor"):
            compile_abyss_limited_gacha(common, malformed, existing_common_paths=set(common))

    def test_rejects_standard_pool_character_reference_missing_from_client_or_server(self):
        self._require_module()
        common, server = _sources()
        missing_client = dict(common)
        rows = _decode_flat(
            missing_client[contract.CHARACTER_MASTER_LOGICAL],
            contract.CHARACTER_MASTER_LOGICAL,
        )
        rows.pop("221001")
        missing_client[contract.CHARACTER_MASTER_LOGICAL] = _flat(
            contract.CHARACTER_MASTER_LOGICAL,
            {key: value.decode() for key, value in rows.items()},
        )
        with self.assertRaisesRegex(ValueError, "gacha pool character closure"):
            compile_abyss_limited_gacha(
                missing_client, server, existing_common_paths=set(missing_client)
            )

        missing_server = dict(server)
        characters = json.loads(missing_server["character.json"])
        characters.pop("311001")
        missing_server["character.json"] = _json(characters)
        with self.assertRaisesRegex(ValueError, "gacha pool character closure"):
            compile_abyss_limited_gacha(
                common, missing_server, existing_common_paths=set(common)
            )

    def test_compiler_preserves_nonowned_rows_and_emits_exact_claims(self):
        common, server, result = self._compile()
        self.assertEqual(11, len(result["files"]))
        self.assertEqual(10, len(result["table_claims"]))
        for logical in (
            contract.GACHA_MASTER_LOGICAL,
            contract.FEATURE_LOGICAL,
            contract.RICH_TEXT_MASTER_LOGICAL,
        ):
            decoder = _decode_nested if logical == contract.FEATURE_LOGICAL else _decode_flat
            before, after = decoder(common[logical], logical), decoder(result["files"][logical], logical)
            for key in before:
                self.assertEqual(before[key], after[key], f"nonowned client row changed: {logical}:{key}")
        for logical in contract.SERVER_OUTPUT_PATHS:
            before = json.loads(server[logical])
            after = json.loads(result["files"][logical])
            for key in before:
                self.assertEqual(before[key], after[key], f"nonowned server row changed: {logical}:{key}")

        claims = {(item["root"], item["logical_path"]): item for item in result["table_claims"]}
        self.assertEqual(10, len(claims))
        self.assertEqual(
            EXPECTED_CLAIMS,
            {
                (
                    item["root"], item["logical_path"], item["codec_id"],
                    tuple(item["outer_keys"]),
                )
                for item in result["table_claims"]
            },
        )
        for (root, logical), item in claims.items():
            claim = TableClaim(root, logical, item["codec_id"], tuple(item["outer_keys"]))
            codec = JsonObjectCodec() if root == "server" else DEFAULT_CODECS[item["codec_id"]]
            image = codec.inspect(result["files"][logical], claim, ())
            inspected = dict(image.outer_rows)
            for key in item["outer_keys"]:
                self.assertIn(key, inspected)

    def test_rejects_character_leakage_missing_rarity_and_identity_collisions(self):
        self._require_module()
        common, server = _sources()
        leaked = copy.deepcopy(server)
        gacha = json.loads(leaked["gacha.json"])
        gacha["1"]["pool"]["1"].append({"id": IDS[0]})
        leaked["gacha.json"] = _json(gacha)
        with self.assertRaisesRegex(ValueError, "already appears in gacha 1"):
            compile_abyss_limited_gacha(common, leaked, existing_common_paths=set(common))

        missing = dict(common)
        rows = _decode_flat(missing[contract.CHARACTER_MASTER_LOGICAL], contract.CHARACTER_MASTER_LOGICAL)
        rows.pop(str(IDS[-1]))
        missing[contract.CHARACTER_MASTER_LOGICAL] = _flat(
            contract.CHARACTER_MASTER_LOGICAL, {key: value.decode() for key, value in rows.items()}
        )
        with self.assertRaisesRegex(ValueError, "client character closure"):
            compile_abyss_limited_gacha(missing, server, existing_common_paths=set(missing))

        bad_server = copy.deepcopy(server)
        characters = json.loads(bad_server["character.json"])
        characters[str(IDS[1])]["rarity"] = 4
        bad_server["character.json"] = _json(characters)
        with self.assertRaisesRegex(ValueError, "server five-star closure"):
            compile_abyss_limited_gacha(common, bad_server, existing_common_paths=set(common))

        with self.assertRaisesRegex(ValueError, "new common logical path collision"):
            compile_abyss_limited_gacha(
                common, server,
                existing_common_paths={*common, contract.CHARACTER_5_ODDS_LOGICAL},
            )

    def test_rejects_official_57_drift_and_target_key_collision(self):
        self._require_module()
        common, server = _sources()
        drift = dict(common)
        rows = _decode_flat(drift[contract.GACHA_MASTER_LOGICAL], contract.GACHA_MASTER_LOGICAL)
        official = core.read_csv_lines(rows["57"].decode())[0]
        official[4] = "0"
        rows["57"] = core.write_csv_lines([official]).encode()
        drift[contract.GACHA_MASTER_LOGICAL] = _flat(
            contract.GACHA_MASTER_LOGICAL, {key: value.decode() for key, value in rows.items()}
        )
        with self.assertRaisesRegex(ValueError, "official gacha 57 drift"):
            compile_abyss_limited_gacha(drift, server, existing_common_paths=set(drift))

        collision = copy.deepcopy(server)
        runtime = json.loads(collision["gacha.json"])
        runtime["990001"] = {}
        collision["gacha.json"] = _json(runtime)
        with self.assertRaisesRegex(ValueError, "target key collision"):
            compile_abyss_limited_gacha(common, collision, existing_common_paths=set(common))

    def test_rejects_drift_in_every_official_57_client_cell(self):
        self._require_module()
        accepted = []
        for index in range(len(OFFICIAL_57)):
            common, server = _sources()
            rows = _decode_flat(
                common[contract.GACHA_MASTER_LOGICAL], contract.GACHA_MASTER_LOGICAL
            )
            row = core.read_csv_lines(rows["57"].decode())[0]
            row[index] = f"{row[index]}__drift"
            rows["57"] = core.write_csv_lines([row]).encode()
            common[contract.GACHA_MASTER_LOGICAL] = _flat(
                contract.GACHA_MASTER_LOGICAL,
                {key: value.decode() for key, value in rows.items()},
            )
            cdndata = json.loads(server["cdndata/gacha.json"])
            cdndata["57"] = [row]
            server["cdndata/gacha.json"] = _json(cdndata)
            try:
                compile_abyss_limited_gacha(
                    common, server, existing_common_paths=set(common)
                )
            except ValueError as exc:
                self.assertIn("official gacha 57 drift", str(exc))
            else:
                accepted.append(index)
        self.assertEqual([], accepted, f"client drift accepted at cells {accepted}")

    def test_rejects_drift_in_every_official_57_runtime_nonpool_field(self):
        self._require_module()
        accepted = []
        runtime_contract = _official_runtime_57()
        for field in sorted(set(runtime_contract) - {"pool"}):
            common, server = _sources()
            gachas = json.loads(server["gacha.json"])
            value = gachas["57"][field]
            if isinstance(value, bool):
                replacement = not value
            elif isinstance(value, int):
                replacement = value + 1
            elif isinstance(value, str):
                replacement = f"{value}__drift"
            elif isinstance(value, dict):
                replacement = copy.deepcopy(value)
                replacement["normal"][0] += 1
            else:
                self.fail(f"unhandled runtime fixture type for {field}: {type(value)}")
            gachas["57"][field] = replacement
            server["gacha.json"] = _json(gachas)
            try:
                compile_abyss_limited_gacha(
                    common, server, existing_common_paths=set(common)
                )
            except ValueError as exc:
                self.assertIn("official gacha 57 drift", str(exc))
            else:
                accepted.append(field)
        self.assertEqual([], accepted, f"runtime drift accepted in fields {accepted}")

    def test_rejects_malformed_or_aliased_existing_common_path_inventory(self):
        self._require_module()
        common, server = _sources()
        for inventory in (
            contract.CHARACTER_5_ODDS_LOGICAL,
            contract.CHARACTER_5_ODDS_LOGICAL.encode(),
        ):
            with self.subTest(kind=type(inventory).__name__):
                with self.assertRaisesRegex(TypeError, "collection of logical paths"):
                    compile_abyss_limited_gacha(
                        common, server, existing_common_paths=inventory
                    )

        invalid_inventories = (
            [""], [" "], ["master//gacha/table"], ["master/./gacha/table"],
            ["master/../gacha/table"], [r"master\gacha\table"], [123],
        )
        for inventory in invalid_inventories:
            with self.subTest(inventory=inventory):
                with self.assertRaisesRegex((TypeError, ValueError), "logical path"):
                    compile_abyss_limited_gacha(
                        common, server, existing_common_paths=inventory
                    )

        with self.assertRaisesRegex(ValueError, "new common logical path collision"):
            compile_abyss_limited_gacha(
                common, server,
                existing_common_paths=[contract.CHARACTER_5_ODDS_LOGICAL.upper()],
            )

    def test_output_is_deterministic_readback_verified_and_never_live(self):
        self._require_module()
        common, server = _sources()
        common_snapshot, server_snapshot = dict(common), dict(server)
        first = compile_abyss_limited_gacha(common, server, existing_common_paths=set(common))
        second = compile_abyss_limited_gacha(common, server, existing_common_paths=set(common))
        self.assertEqual(first, second)
        self.assertEqual(common_snapshot, common)
        self.assertEqual(server_snapshot, server)
        report = first["report"]
        self.assertEqual("compiled_isolated_abyss_gacha", report["status"])
        self.assertFalse(report["writes_live"])
        self.assertFalse(report["formal_workspace_written"])
        self.assertEqual(0, report["nonowned_client_changes"])
        self.assertEqual(0, report["nonowned_server_changes"])
        self.assertTrue(report["eight_character_closure"])
        self.assertEqual(list(IDS), report["character_ids"])
        self.assertEqual(
            list(NON_EXCHANGEABLE_IDS),
            report["non_exchangeable_character_ids"],
        )
        self.assertEqual(1.0, report["limited_character_rate_total_percent"])
        self.assertEqual([1, 900], report["limited_character_rate_each_ratio"])
        self.assertTrue(report["normal_page_contract"])
        self.assertTrue(report["global_ball_animation_unchanged"])
        self.assertEqual("static_kind_1_top_banner", report["feature_contract"])
        self.assertEqual(
            [
                contract.LIST_BANNER_PAYLOAD_LOGICAL,
                contract.TOP_BANNER_PAYLOAD_LOGICAL,
            ],
            report["unresolved_art_payloads"],
        )
        self.assertTrue(report["table_claims_eligible"])
        self.assertFalse(report["package_manifest_eligible"])
        self.assertEqual(
            {"exec_type": 3, "ticket_id": 999013, "pulls_per_ticket": 1},
            report["execution_contract"]["single"],
        )
        self.assertEqual(
            {"exec_type": 4, "ticket_id": 999014, "pulls_per_ticket": 10},
            report["execution_contract"]["ten"],
        )


if __name__ == "__main__":
    unittest.main()
