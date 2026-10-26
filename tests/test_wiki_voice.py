"""Current audio hashes, speech binding, and extended-slot discovery regressions."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wf_assets
import wf_mod_tool as core
import wf_wiki_voice as voice
import wf_wiki_voice_sources as sources
from wf_wiki_voice_receipts import add_receipt_evidence


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


class SubtitleSourceTests(unittest.TestCase):
    def test_original_mpeg_frames_match_when_id3_tags_differ(self):
        # MPEG-1 Layer III, 96 kbps, 44.1 kHz: 313-byte frames.
        frames = (bytes.fromhex("fffb7000") + bytes(309)) * 3
        old = b"ID3\x03\x00\x00\x00\x00\x00\x04" + b"ABCD" + frames
        # A real dump bug: extra ID3 bytes, unchanged declared length.
        dump = b"ID3\x03\x00\x00\x00\x00\x00\x04" + b"ABCDEXTRA" + frames
        self.assertEqual(sources.frame_digest(old), sources.frame_digest(dump))
        changed = frames[:-1] + b"\x01"
        self.assertNotEqual(sources.frame_digest(old), sources.frame_digest(changed))
        self.assertIsNone(sources.frame_digest(frames[:-100]))

    def test_untagged_corruption_cannot_match_an_intact_suffix(self):
        frame = bytes.fromhex("fffb7000") + bytes(309)
        corrupted = b"\x00" + frame[1:]
        suffix = frame * 3
        self.assertIsNotNone(sources.frame_digest(suffix))
        for damaged in (corrupted + suffix, frame[1:] + suffix,
                        suffix + corrupted, suffix[:-50]):
            with self.subTest(size=len(damaged), prefix=damaged[:4]):
                self.assertIsNone(sources.frame_digest(damaged))

    def test_tagged_corruption_after_first_header_cannot_restart_later(self):
        frame = bytes.fromhex("fffb7000") + bytes(309)
        corrupted = b"\x00" + frame[1:]
        tag = b"ID3\x03\x00\x00\x00\x00\x00\x04ABCD"
        for damaged in (frame + corrupted + frame * 3,
                        frame * 3 + corrupted, (frame * 3)[:-50]):
            with self.subTest(size=len(damaged)):
                self.assertIsNone(sources.frame_digest(tag + damaged))

    def test_stale_script_and_reference_hash_cannot_bind_current_audio(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            write_json(root / "voices" / "test" / "交付清单.json", {"selection": [
                {"slot": "home/home_0", "ja": "古い声", "zh": "旧稿",
                 "files": {"native": {"sha256": digest(b"old")}}},
                {"slot": "home/home_0", "ja": "参考声", "zh": "参考稿",
                 "old_storage_sha256": digest(b"current"), "source_sha256": digest(b"current"),
                 "references": [{"sha256": digest(b"current")}]},
            ]})
            index = sources.build_subtitle_index(root, root / "voices")
            self.assertEqual(index.match(b"current", b"decoded")["ja"], "")
            self.assertEqual(index.match(b"old", b"decoded")["ja"], "古い声")

    def test_original_clone_matches_recording_not_codename(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = root / "voices" / "official"
            write_json(directory / "voiceLines.json", {"ally/join": "ここにいる。"})
            (directory / "ally").mkdir()
            (directory / "ally/join.mp3").write_bytes(b"same recording")
            index = sources.build_subtitle_index(root, root / "voices")
            self.assertEqual(index.match(b"stored", b"same recording")["ja"], "ここにいる。")
            self.assertEqual(index.match(b"different", b"different")["ja"], "")

    def test_conflicting_text_does_not_silently_choose_a_draft(self):
        index = sources.SubtitleIndex()
        for ja in ("one", "two"):
            index.add(digest(b"audio"), slot="battle/skill_0", ja=ja, zh="相同中文")
        found = index.match(b"audio", b"audio")
        self.assertTrue(found["conflict"])
        self.assertEqual(found["ja"], "")
        self.assertEqual(found["zh"], "相同中文")

    def test_metadata_traversal_skips_old_takes_and_never_follows_references(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ("current", "archived-takes", "references"):
                write_json(root / name / "validation.json", {})
            self.assertEqual([p.parent.name for p in sources.metadata_files(root)], ["current"])

    def test_receipt_text_requires_qc_input_chain_and_exact_mastered_audio(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            standard, receipt_path, qc_path = root / "voice.mp3", root / "receipt.json", root / "qc.json"
            standard.write_bytes(b"mastered-audio")
            receipt = {"slot": "battle/skill_0", "status": "generated", "http_status": 200,
                       "sha256": digest(b"raw-audio"), "ja": "声", "zh": "声音"}
            qc = {"slot": "battle/skill_0", "code": "hero", "source_sha256": digest(b"raw-audio"),
                  "standard": str(standard), "standard_sha256": digest(b"mastered-audio")}
            write_json(receipt_path, receipt)
            write_json(qc_path, qc)
            selected = {"roles": {"hero": {"battle/skill_0": {
                "receipt": str(receipt_path), "qc": str(qc_path)}}}}
            index = sources.SubtitleIndex()
            add_receipt_evidence(index, root / "selected.json", selected, root)
            self.assertEqual(index.match(b"stored", b"mastered-audio")["ja"], "声")
            qc["source_sha256"] = digest(b"different-request")
            write_json(qc_path, qc)
            rejected = sources.SubtitleIndex()
            add_receipt_evidence(rejected, root / "selected.json", selected, root)
            self.assertFalse(rejected.by_hash)
            qc["source_sha256"] = receipt["sha256"]
            write_json(qc_path, qc)
            standard.write_bytes(b"changed-master")
            rejected = sources.SubtitleIndex()
            add_receipt_evidence(rejected, root / "selected.json", selected, root)
            self.assertFalse(rejected.by_hash)


class VoiceExportTests(unittest.TestCase):
    def test_official_plot_is_excluded_while_mod_plot_is_preserved(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            audio = root / 'audio'; audio.write_bytes(b'voice')
            index = sources.SubtitleIndex()
            media = Mock(store=root)
            media.audio.return_value = 'media/test.mp3'
            characters = [dict(id=i, code='hero', origin=origin) for i, origin in
                          enumerate(['官方原版', '改版官方', '新增MOD'])]
            def locate(_store, logical):
                return None if logical == voice.SPEECH_TABLE else ('upload', audio)
            with patch.object(voice, 'build_subtitle_index', return_value=index), \
                 patch.object(voice, 'speech_texts', return_value={}), \
                 patch.object(voice, '_candidate_slots', return_value={'home/home_0', 'words/story_1'}), \
                 patch.object(wf_assets, 'locate', side_effect=locate):
                voice.export_voices(root, characters, media)
            self.assertEqual([len(c['voices']) for c in characters], [1, 1, 2])
            self.assertEqual({v['slot'] for v in characters[-1]['voices']}, {'home/home_0', 'words/story_1'})

    def test_live_speech_uses_csv_parser_for_multiline_text(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Path(folder) / "upload"
            target = wf_assets.path_in_root(store, "upload", voice.SPEECH_TABLE)
            target.parent.mkdir(parents=True)
            text = core.write_csv_lines([["0", "2", "", "第一行\n第二行,引号\"", "home/home_15"]])
            target.write_bytes(core.build_orderedmap(core.OrderedMap(
                voice.SPEECH_TABLE, ["123"], [text.encode()], target)))
            self.assertEqual(voice.speech_texts(store)["123"]["home/home_15"], "第一行\n第二行,引号\"")

    def test_extended_slots_only_emit_existing_live_media_and_current_subtitles(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            store = root / "upload"
            raw = b"present-live-recording"
            slots = ["home/home_15", "battle/skill_11", "battle/skill_ready_alt_5"]
            for slot in slots:
                target = wf_assets.path_in_root(store, "upload", f"character/test/voice/{slot}.mp3")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw + slot.encode())
            index = sources.SubtitleIndex()
            index.add(digest(raw + slots[0].encode()), slot=slots[0], code="test", ja="日文", zh="旧字幕")
            index.slots["test"].add("home/candidate_only")

            class Media:
                def __init__(self):
                    self.store = store
                    self.calls = []

                def audio(self, logical):
                    self.calls.append(logical)
                    return "media/audio/" + digest(logical.encode()) + ".mp3"

            media, characters = Media(), [dict(id=123, code="test")]
            with patch.object(voice, "build_subtitle_index", return_value=index), \
                    patch.object(voice, "speech_texts", return_value={"123": {slots[0]: "线上字幕"}}), \
                    patch.object(wf_assets, "dump_voices", return_value=[]), \
                    patch.object(wf_assets, "_pathlist_char_index", return_value={}), \
                    patch.object(wf_assets, "_harvest_voice_index", return_value={}):
                stats = voice.export_voices(root, characters, media)
            self.assertEqual(stats["recordings"], 3)
            self.assertEqual(stats["withJapanese"], 1)
            self.assertEqual(stats["missingChinese"], 2)
            by_slot = {row["slot"]: row for row in characters[0]["voices"]}
            self.assertEqual(set(by_slot), set(slots))
            self.assertEqual(by_slot[slots[0]]["zh"], "线上字幕")
            self.assertEqual(by_slot[slots[1]]["status"], "text-missing")
            self.assertEqual(len(media.calls), 3)
            self.assertNotIn(str(root), json.dumps(characters))

    def test_label_preserves_zero_based_asset_identity_but_reads_naturally(self):
        self.assertEqual(voice.slot_label("battle/skill_ready_alt_5"), "技能准备 6")
        self.assertEqual(voice.slot_label("home/home_15"), "主页 16")


if __name__ == "__main__":
    unittest.main()
