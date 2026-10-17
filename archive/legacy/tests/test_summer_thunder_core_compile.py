import hashlib
import unittest

import wf_mod_tool as core

try:
    from wf_summer_thunder_core_compile import (
        BASE_CHARACTER_ID,
        CHARACTER_ID,
        CODE_NAME,
        PACKAGE_ID,
        compile_summer_thunder_core,
    )
except ImportError:
    BASE_CHARACTER_ID = None
    CHARACTER_ID = None
    CODE_NAME = None
    PACKAGE_ID = None
    compile_summer_thunder_core = None


EXPECTED_CHARACTER_ROW = [
    "cnmod_thunder_dragon_ascendant",  # c0 code_name
    "1",
    "5",  # c2 rarity
    "2",  # c3 Yellow
    "Dragon",
    "",
    "4",  # c6 standard special power flip
    "Female",
    "cnmod_thunder_dragon_ascendant",  # c8 action_skill key
    "(None)",
    "", "", "", "", "", "", "",
    "139998",
    "碧海雷鸣的共振",
    "1399981", "1399982", "1399983",
    "1399984", "1399985", "1399986",
    "0",
    "Attacker",
    "231001",
    "(None)",
    "1",
    "false",
    "false",  # c31 official skin semantics
    "0", "0", "1", "true",
    "6,6,6,6,6,6",
]

SKILL_DESCRIPTION = (
    "向前方释放由中心扩散的黄蓝雷波，对扇形范围内的敌人造成雷属性伤害"
    "（合计55倍／55段），并赋予自身「雷电增幅」效果（10秒）。"
)

EXPECTED_CHARACTER_TEXT_ROW = [
    "拉姆斯",
    "LAMUSI",
    "沉睡于险峻高山的雷龙，在星见镇伙伴们的邀请下第一次踏上海滨。"
    "她似乎很中意海风与潮声；而当双翼掠过碧海，悠闲的假日也会随雷鸣化作耀眼的浪潮。",
    "鸣彻碧海的雷龙",
    "碧海雷潮",
    SKILL_DESCRIPTION,
    "碧海雷潮＋",
    SKILL_DESCRIPTION,
    "(None)",
    "(None)",
    "碧海雷鸣的共振",
    "",
]

EXPECTED_STATUS = [
    ("10", 445, 129),
    ("1", 45, 13),
    ("80", 2670, 774),
    ("100", 2937, 852),
]

AUDITED_DONOR_SHA256 = {
    "thunder_dragon_character": (
        "64e267bbb2a04c642f0a5bd846c42e64a5b6dd70dc05e9a08106c7f05167c0ff"
    ),
    "dragon_skin_character": (
        "a7a20c3e79bbd6e7ab787c39d0df8dde5991cca9ef0cb90144634536e470f376"
    ),
    "summer_thunder_character": (
        "d24e176cdec6a0664db72c26c6b19c464e973e46e120ae734b3cc64ca2abb204"
    ),
    "dragon_skin_status": (
        "80d9113503e36e8a7d267a4a364cc1b78eaaf1e69a49d4cd7c30ec79688f4c6a"
    ),
    "scaffold_awake_status": (
        "444dae2059d918233728f4775784d898054b48e0b7582a8b9ad9539dc52ada26"
    ),
}


def _csv_bytes(row):
    return core.write_csv_lines([row]).encode("utf-8")


def _audited_donors():
    thunder_dragon = [
        "thunder_dragon", "1", "4", "2", "Dragon", "", "4", "Female",
        "thunder_dragon", "(None)", "", "", "", "", "", "", "",
        "231001", "共存之梦",
        "2310011", "2310012", "2310013", "2310014", "2310015", "2310016",
        "0", "Attacker", "231001", "(None)", "1", "false", "true",
        "0", "1", "", "", "6,6,6,6,6,6",
    ]
    dragon_skin = [
        "wind_dragon_wt22", "1", "5", "3", "Dragon", "", "4", "Male",
        "wind_dragon_wt22", "(None)", "", "", "", "", "", "", "",
        "141099", "知人晓爱",
        "1410991", "1410992", "1410993", "1410994", "1410995", "1410996",
        "1", "Attacker", "141008", "(None)", "1", "false", "false",
        "0", "0", "0", "true", "6,6,6,6,6,6",
    ]
    summer_thunder = [
        "combat_soldier_smr22", "1", "5", "2", "Human,Machine", "", "2",
        "Female", "combat_soldier_smr22", "0", "", "", "", "0.5",
        "combat_soldier_smr22", "false", "false", "131104", "Sky for You",
        "1311041", "1311042", "1311043", "1311044", "1311045", "1311046",
        "0", "Attacker", "151006", "(None)", "1", "false", "false",
        "0", "0", "1", "true", "6,6,6,6,6,6",
    ]
    donors = {
        "thunder_dragon_character": _csv_bytes(thunder_dragon),
        "dragon_skin_character": _csv_bytes(dragon_skin),
        "summer_thunder_character": _csv_bytes(summer_thunder),
        "dragon_skin_status": core.encode_status_row(EXPECTED_STATUS),
        "scaffold_awake_status": b"26,0",
    }
    for label, expected in AUDITED_DONOR_SHA256.items():
        actual = hashlib.sha256(donors[label]).hexdigest()
        if actual != expected:
            raise AssertionError(f"test fixture drift for {label}: {actual}")
    return donors


class SummerThunderCoreCompileTests(unittest.TestCase):
    def _require_module(self):
        if compile_summer_thunder_core is None:
            self.fail("wf_summer_thunder_core_compile is missing")

    def test_compiler_requires_exact_audited_donor_identities(self):
        self._require_module()
        compiled = compile_summer_thunder_core(_audited_donors())
        self.assertEqual(AUDITED_DONOR_SHA256, compiled["report"]["donor_sha256"])

        drifted = _audited_donors()
        drifted["dragon_skin_character"] += b" "
        with self.assertRaisesRegex(ValueError, "dragon_skin_character donor identity drift"):
            compile_summer_thunder_core(drifted)

        missing = _audited_donors()
        missing.pop("summer_thunder_character")
        with self.assertRaisesRegex(ValueError, "donor rows must contain exactly"):
            compile_summer_thunder_core(missing)

    def test_character_row_is_complete_locked_and_csv_roundtrips(self):
        self._require_module()
        compiled = compile_summer_thunder_core(_audited_donors())
        character = compiled["tables"]["character"]
        self.assertEqual({"139998"}, set(character))
        decoded = core.read_csv_lines(character["139998"])
        self.assertEqual([EXPECTED_CHARACTER_ROW], decoded)
        self.assertEqual(37, len(decoded[0]))
        self.assertEqual(character["139998"], core.write_csv_lines(decoded))
        self.assertEqual(139998, CHARACTER_ID)
        self.assertEqual("cnmod_thunder_dragon_ascendant", CODE_NAME)
        self.assertEqual("cnmod_thunder_dragon_ascendant", PACKAGE_ID)
        self.assertEqual(231001, BASE_CHARACTER_ID)

    def test_status_uses_full_five_star_curve_and_nested_roundtrips(self):
        self._require_module()
        compiled = compile_summer_thunder_core(_audited_donors())
        status = compiled["tables"]["character_status"]
        self.assertEqual({"139998"}, set(status))
        self.assertEqual(EXPECTED_STATUS, core.decode_status_row(status["139998"]))
        self.assertEqual(status["139998"], core.encode_status_row(EXPECTED_STATUS))
        self.assertEqual(
            AUDITED_DONOR_SHA256["dragon_skin_status"],
            hashlib.sha256(status["139998"]).hexdigest(),
        )

    def test_character_text_is_chinese_and_matches_character_and_action_contract(self):
        self._require_module()
        compiled = compile_summer_thunder_core(_audited_donors())
        character_text = compiled["tables"]["character_text"]
        decoded = core.read_csv_lines(character_text["139998"])
        self.assertEqual([EXPECTED_CHARACTER_TEXT_ROW], decoded)
        self.assertEqual(character_text["139998"], core.write_csv_lines(decoded))

        character = core.read_csv_lines(compiled["tables"]["character"]["139998"])[0]
        text = decoded[0]
        self.assertEqual(character[18], text[10])
        self.assertEqual("碧海雷潮", text[4])
        self.assertEqual("碧海雷潮＋", text[6])
        self.assertEqual(text[5], text[7])
        self.assertIn("55倍／55段", text[5])
        self.assertIn("10秒", text[5])
        self.assertNotIn("额外乘区", text[5])

    def test_awake_status_is_an_owned_target_delete_not_a_zero_placeholder(self):
        self._require_module()
        compiled = compile_summer_thunder_core(_audited_donors())
        self.assertEqual({}, compiled["tables"]["character_awake_status"])
        operation = compiled["owned_replacements"]["character_awake_status"]
        self.assertEqual("owned_replace", operation["mode"])
        self.assertEqual(["139998"], operation["owned_keys"])
        self.assertEqual([], operation["set_keys"])
        self.assertEqual(["139998"], operation["delete_keys"])
        self.assertEqual(
            {"139998": AUDITED_DONOR_SHA256["scaffold_awake_status"]},
            operation["expected_existing_sha256"],
        )

    def test_report_is_explicitly_isolated_and_not_package_eligible(self):
        self._require_module()
        compiled = compile_summer_thunder_core(_audited_donors())
        report = compiled["report"]
        self.assertEqual("compiled_isolated_core_master", report["status"])
        self.assertFalse(report["writes_live"])
        self.assertFalse(report["package_manifest_eligible"])
        self.assertEqual(139998, report["character_id"])
        self.assertEqual("cnmod_thunder_dragon_ascendant", report["code_name"])
        self.assertEqual("cnmod_thunder_dragon_ascendant", report["package_id"])
        self.assertEqual(
            {"character", "character_status", "character_text", "character_awake_status"},
            set(compiled["tables"]),
        )
        self.assertEqual(
            {"character", "character_status", "character_text"},
            set(report["output_sha256"]),
        )


if __name__ == "__main__":
    unittest.main()
