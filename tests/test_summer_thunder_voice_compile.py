import hashlib
import unittest
from pathlib import Path
from unittest import mock

import wf_assets
import wf_mod_tool as core
import wf_summer_thunder_voice_compile as voice_compile
from wf_summer_thunder_voice_compile import (
    AUTHOR_CUT_RELATIVES,
    CHARACTER_ID,
    CHARACTER_SPEECH_LOGICAL,
    CODE_NAME,
    INGEST_RELATIVES,
    KNOWN_CONTENT_DEVIATIONS,
    LOCKED_VOICE_SHA256,
    build_summer_thunder_character_speech_rows,
    compile_summer_thunder_voice_assets,
    patch_summer_thunder_character_speech_table,
)


VOICE_BUILD_ROOT = Path(
    r"D:\WF\wf-mod-tools\work\builds\cnmod_thunder_dragon_ascendant\art\voice"
)
AUTHOR_ROOT = VOICE_BUILD_ROOT / "author_cut_v1/candidate_mp3/character" / CODE_NAME / "voice"
INGEST_ROOT = VOICE_BUILD_ROOT / "ingest_v1/candidate_mp3/character" / CODE_NAME / "voice"
HAS_LOCAL_ACCEPTED_VOICES = all(
    (AUTHOR_ROOT / relative).is_file() for relative in AUTHOR_CUT_RELATIVES
) and all((INGEST_ROOT / relative).is_file() for relative in INGEST_RELATIVES)


EXPECTED_SHA256 = {
    "ally/evolution.mp3": "9d1b174a9c239c2e34905504ccfd3375e607a175d2215a389d85b02b6dc50a49",
    "ally/join.mp3": "e1361f83a4f81d948b95695ba549da7a6c9d167cdce9155542b8d60e558c15f7",
    "battle/battle_start_0.mp3": "ed1bf5c81388ca02358063e2c41cb186d28c3472a34d2b65ad43ef01916f2c5e",
    "battle/battle_start_1.mp3": "72acb4a12a660bbf65db399686b66998787c59f196b7e1b12a9590fa695551bd",
    "battle/outhole_0.mp3": "02fb651cca729b5650980b6ab79a5803ef079f159bdb7a0452cb6060a9dbe234",
    "battle/power_flip_0.mp3": "0de0a390e6ddc6a0d122a7361b675174d6632b7ea72df5d9fa305c1b8ad4391a",
    "battle/power_flip_1.mp3": "c64dda5e60c67c38b2cd5d369b5d36cfbd73a2a779f64163c34ee59cca4a629c",
    "battle/skill_0.mp3": "068529c1ba8a540305bd51290d3ac1133d10233d086f52737209c2bd7aed8cfa",
    "battle/skill_1.mp3": "b30d5dcf31d0714f0ae348011760355ce471ba00f4880b390918945afae741a3",
    "battle/skill_ready.mp3": "beaf4a9ff9952fb221677c645957f61eaad3f4a6071409b900276c74d6f414df",
    "battle/win_0.mp3": "fcabf8a2bd548e677cbe9e196fa4d68a28782a532d94b29a7b275c62ee0b578c",
    "battle/win_1.mp3": "d05eea1a52a0d2f99e146cca111f02c5ad4c63aa75bc2c24745e0ac4d485a095",
    "home/isekaidewa.mp3": "c6e37828566bb1caaf41537a4ad329a46d13858aba373c8d0e8bcf4f68de8cbd",
    "home/kono.mp3": "7e6bd007a57bbf65e954f0987521a4caf4625c6a6fb145eab277618d0bc8b79b",
    "home/mukashiwa.mp3": "69ec217378b4a3a85191b2bbfea425eb1d546de72c605f5b6421ccca2c1cc306",
    "home/sono.mp3": "e3e17de39fe6ea984f3e87d088ca0b42c58934c934909896dda17f01d89fe289",
    "home/watashiwa.mp3": "c83bc6e1c5d20a0a4f9543a45fd61169f953df9fbd8148416be92a5a9194e509",
}


EXPECTED_SPEECH_ROWS = [
    [
        "0", "2", "",
        "异世界的海与天空，也充满了陌生的回响。\n旅行真是件好事啊。\n命运又描绘出了新的波澜。",
        "home/isekaidewa",
    ],
    [
        "0", "2", "",
        "过去，我曾从云端向海面降下雷霆，把鱼儿们吓得四散。\n呵呵……放心吧。\n今天只会稍微恶作剧一下。",
        "home/mukashiwa",
    ],
    [
        "0", "2", "",
        "那个游泳圈，你觉得我也能用吗？\n……呵呵，开玩笑的。\n不过让翅膀休息一下，随波漂流倒也不坏。",
        "home/sono",
    ],
    [
        "0", "1", "",
        "这片海滩的声音真悦耳。\n海浪、笑声，还有远方的雷鸣……\n当它们交叠在一起，便成了只属于夏日的歌。",
        "home/kono",
    ],
    [
        "0", "1", "",
        "我曾以为，安静的休息实在无聊。\n但若是与你们一同度过的夏日……\n就连无所事事的时光，也令人心生爱怜。",
        "home/watashiwa",
    ],
    [
        "2", "", "",
        "我是拉姆斯·恩弗利亚。\n潮声与雷鸣交相呼应的夏日……倒也不坏。\n来吧，一同尽情享受吧。",
        "ally/join",
    ],
    [
        "1", "", "1",
        "阳光与海风，都令我的雷霆更加耀眼。\n托付给你们的梦想……\n让它轰鸣至这片夏空的尽头吧。",
        "ally/evolution",
    ],
]


class SummerThunderVoiceCompileTests(unittest.TestCase):
    def _local_sources(self):
        author = {
            relative: (AUTHOR_ROOT / relative).read_bytes()
            for relative in AUTHOR_CUT_RELATIVES
        }
        ingest = {
            relative: (INGEST_ROOT / relative).read_bytes()
            for relative in INGEST_RELATIVES
        }
        return author, ingest

    def test_identity_source_split_and_all_17_sha256_are_locked(self):
        self.assertEqual(139998, CHARACTER_ID)
        self.assertEqual("cnmod_thunder_dragon_ascendant", CODE_NAME)
        self.assertEqual(9, len(AUTHOR_CUT_RELATIVES))
        self.assertEqual(8, len(INGEST_RELATIVES))
        self.assertEqual(set(), set(AUTHOR_CUT_RELATIVES) & set(INGEST_RELATIVES))
        self.assertEqual(EXPECTED_SHA256, LOCKED_VOICE_SHA256)
        self.assertEqual(
            set(EXPECTED_SHA256),
            set(AUTHOR_CUT_RELATIVES) | set(INGEST_RELATIVES),
        )

    def test_speech_rows_lock_summer_text_and_only_home_ally_paths(self):
        rows = build_summer_thunder_character_speech_rows()
        self.assertEqual(EXPECTED_SPEECH_ROWS, rows)
        self.assertEqual(7, len(rows))
        self.assertEqual(
            {
                "home/isekaidewa", "home/mukashiwa", "home/sono",
                "home/kono", "home/watashiwa", "ally/join", "ally/evolution",
            },
            {row[4] for row in rows},
        )
        self.assertFalse(any("battle/" in row[4] for row in rows))
        self.assertFalse(any("在异世界也许会遇到很多人" in row[3] for row in rows))

    def test_speech_table_patch_replaces_only_139998_and_preserves_other_rows(self):
        original = {"231001": "official donor", "139998": "stale donor speech"}
        patched = patch_summer_thunder_character_speech_table(original)
        self.assertEqual("official donor", patched["231001"])
        self.assertEqual(EXPECTED_SPEECH_ROWS, core.read_csv_lines(patched["139998"]))
        self.assertEqual(original, {"231001": "official donor", "139998": "stale donor speech"})

    def test_compile_rejects_missing_extra_swapped_or_tampered_sources(self):
        fake_author = {relative: b"not an mp3" for relative in AUTHOR_CUT_RELATIVES}
        fake_ingest = {relative: b"not an mp3" for relative in INGEST_RELATIVES}
        missing = dict(fake_author)
        missing.pop(next(iter(missing)))
        with self.assertRaisesRegex(ValueError, "author_cut paths"):
            compile_summer_thunder_voice_assets(missing, fake_ingest)
        extra = dict(fake_author, **{"battle/skill_2.mp3": b"extra"})
        with self.assertRaisesRegex(ValueError, "author_cut paths"):
            compile_summer_thunder_voice_assets(extra, fake_ingest)
        moved = dict(fake_author)
        value = moved.pop("ally/join.mp3")
        wrong_ingest = dict(fake_ingest, **{"ally/join.mp3": value})
        with self.assertRaisesRegex(ValueError, "author_cut paths"):
            compile_summer_thunder_voice_assets(moved, wrong_ingest)
        with self.assertRaisesRegex(ValueError, "locked SHA-256"):
            compile_summer_thunder_voice_assets(fake_author, fake_ingest)

    def test_synthetic_mono_cbr_set_compiles_without_local_work_dependencies(self):
        def frame(marker):
            return bytes.fromhex("fffb70c4") + bytes([marker]) * 309

        all_relatives = AUTHOR_CUT_RELATIVES + INGEST_RELATIVES
        payloads = {
            relative: frame(index + 1)
            for index, relative in enumerate(all_relatives)
        }
        synthetic_hashes = {
            relative: hashlib.sha256(payload).hexdigest()
            for relative, payload in payloads.items()
        }
        author = {relative: payloads[relative] for relative in AUTHOR_CUT_RELATIVES}
        ingest = {relative: payloads[relative] for relative in INGEST_RELATIVES}
        with mock.patch.dict(
            voice_compile.LOCKED_VOICE_SHA256,
            synthetic_hashes,
            clear=True,
        ):
            files, tables, report = compile_summer_thunder_voice_assets(author, ingest)
        self.assertEqual(17, len(files))
        self.assertEqual(17, report["voice_count"])
        self.assertEqual({"author_cut": 9, "ingest": 8}, report["source_counts"])
        self.assertEqual(
            EXPECTED_SPEECH_ROWS,
            core.read_csv_lines(tables[CHARACTER_SPEECH_LOGICAL]["139998"]),
        )
        for relative, source in payloads.items():
            stored = files[f"character/{CODE_NAME}/voice/{relative}"]
            self.assertEqual(source, wf_assets.mp3_decode(stored))

    @unittest.skipUnless(HAS_LOCAL_ACCEPTED_VOICES, "accepted local voice set unavailable")
    def test_local_accepted_17_compile_to_storage_bytes_and_isolated_report(self):
        author, ingest = self._local_sources()
        files, tables, report = compile_summer_thunder_voice_assets(author, ingest)
        self.assertEqual(17, len(files))
        self.assertEqual(
            {
                f"character/{CODE_NAME}/voice/{relative}"
                for relative in EXPECTED_SHA256
            },
            set(files),
        )
        for relative, source in {**author, **ingest}.items():
            logical = f"character/{CODE_NAME}/voice/{relative}"
            self.assertNotEqual(source, files[logical])
            self.assertEqual(source, wf_assets.mp3_decode(files[logical]))
            probe = wf_assets.mp3_probe(files[logical], 1023)
            self.assertEqual({96000}, probe["bitrates"])
            self.assertEqual({44100}, probe["srates"])
            self.assertEqual(0, probe["tail"])
            self.assertEqual(
                hashlib.sha256(files[logical]).hexdigest(),
                report["output_sha256"][logical],
            )

        self.assertEqual(
            {CHARACTER_SPEECH_LOGICAL: {"139998": core.write_csv_lines(EXPECTED_SPEECH_ROWS)}},
            tables,
        )
        self.assertFalse(report["writes_live"])
        self.assertFalse(report["package_manifest_eligible"])
        self.assertEqual(
            {
                "codec": "MPEG Layer III",
                "sample_rate_hz": 44100,
                "channels": 1,
                "bitrate_bps": 96000,
                "constant_bitrate": True,
            },
            report["encoding_contract"],
        )
        self.assertEqual(sorted(files), report["roots"]["common"])
        self.assertEqual([], report["roots"]["medium"])
        self.assertEqual([], report["roots"]["android"])
        self.assertEqual([], report["roots"]["server"])
        self.assertEqual(
            {
                "root": "common",
                "logical_path": CHARACTER_SPEECH_LOGICAL,
                "codec_id": "flat",
                "outer_keys": ["139998"],
                "inner_keys": [],
                "semantic_claims": [],
            },
            report["table_claim"],
        )
        self.assertEqual(KNOWN_CONTENT_DEVIATIONS, report["known_content_deviations"])


if __name__ == "__main__":
    unittest.main()
