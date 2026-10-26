# -*- coding: utf-8 -*-
"""泳装希尔媞灰版资源补齐（``wf_balance_20260927c_swimassets``；作者 2026-09-27「对方补了资源」）。

夹具 ``fixtures/balance_20260927c_swimassets.json``：BEFORE 覆盖的 14 个 live ``file_sha256`` + character_speech /
character 的 149996 行（本地链尾 1.4.1054，extra5 ``make_read(live_only=True)`` 只读取数；键 ``"<kind>|<json key>"``；
character_quest 1499960{1,2,3} 在 live 不存在，夹具 reader 对缺键抛 KeyError）。

来源字节不进夹具（游戏语音/美术），分三层跑：
- 任何机器：接口常量、BEFORE/夹具一致、漂移拒绝（在读来源之前）、引用门禁、合成 MP3/PNG 的校验器用例；
- 本机有解出目录（``work/gray3/handoff_v2``）或交付包 zip：真来源 revise 全量断言、extract、zip 直读回退；
- 本机有 live store / 灰链归档：live 旧版实测、官方横幅尺寸、表引用扫描、灰链 1.4.88 出处。
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import zipfile
import zlib

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_assets as A  # noqa: E402
import wf_balance_20260927c_swimassets as M  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927c_swimassets.json'
DATA = json.loads(FIXTURE.read_text(encoding="utf-8"))
LOCAL_STORE = (ROOT / "mod-tools/profiles.json").is_file()
GRAY_CHAIN = ROOT / M.GRAY_CHAIN_ZIP
HAS_ZIP = Path(M.HANDOFF).is_file()
HAS_EXTRACTED = all(M.HandoffSource().path(*M.split_member(m)).is_file() for m in M.FILES)
VOICES = sorted(m for m in M.FILES if M.is_voice(m))
EXPECTED_VOICES = sorted(
    f"common:character/wind_spgirl_swim/voice/{name}.mp3"
    for name in ("ally/evolution", "ally/join", "battle/battle_start_0", "battle/battle_start_1", "battle/outhole_0",
                 "battle/outhole_1", "battle/power_flip_0", "battle/power_flip_1", "battle/skill_0", "battle/skill_1",
                 "battle/skill_ready", "battle/win_0", "battle/win_1"))
SPEECH_KEY = f"table|{json.dumps([M.SPEECH, M.CID], ensure_ascii=False)}"
CHAR_KEY = f"table|{json.dumps([M.CHAR, M.CID], ensure_ascii=False)}"


def live_key(kind, key) -> str:
    return f"{kind}|{json.dumps(list(key) if isinstance(key, tuple) else key, ensure_ascii=False)}"


def reader(live: dict):
    def read(kind, key):
        name = live_key(kind, key)
        if name not in live:
            raise KeyError(name)
        return deepcopy(live[name])
    return read


class TrapSource:
    """门禁必须在读来源之前拒绝：任何来源访问都算失败。"""

    def raw(self, tier, logical):
        raise AssertionError(f"source touched: {tier}:{logical}")

    def file_path(self, tier, logical):
        raise AssertionError(f"source touched: {tier}:{logical}")


def run(live=None, source=None):
    return M.revise(reader(deepcopy(DATA["live"]) if live is None else live),
                    TrapSource() if source is None else source)


# ---------------------------------------------------------------- 合成字节（校验器用例）

def mp3_frame(bitrate_index=7, first=0xFF) -> bytes:
    """MPEG-1 Layer III、44.1 kHz、单声道、无填充；96 kbps（索引 7）一帧 313 字节。"""
    bitrate = A._BITRATE_V1[bitrate_index]
    size = int(144 * bitrate / 44100 + 2e-10)
    return bytes([first, 0xFB, bitrate_index << 4, 0xC0]) + b"\0" * (size - 4)


def id3v2(frames: bytes = b"TIT2\0\0\0\x05\0\0\x00test", padding: int = 64) -> bytes:
    size = len(frames) + padding
    syncsafe = bytes([(size >> 21) & 0x7F, (size >> 14) & 0x7F, (size >> 7) & 0x7F, size & 0x7F])
    return b"ID3\x03\x00\x00" + syncsafe + frames + b"\0" * padding


def stored_mp3(frames: list[bytes], tag: bytes | None = None) -> bytes:
    """标准 MP3 → 存储态（帧头首字节 0xFF → 0x7F）。"""
    return A.mp3_encode((id3v2() if tag is None else tag) + b"".join(frames))


def png_chunk(kind: bytes, body: bytes) -> bytes:
    return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))


def stored_png(width=4, height=2, rows: bytes | None = None, trailing=b"", idat_body: bytes | None = None) -> bytes:
    rows = rows if rows is not None else b"".join(b"\0" + b"\x10\x20\x30\xff" * width for _ in range(height))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    body = idat_body if idat_body is not None else zlib.compress(rows)
    standard = A.PNG_REAL + png_chunk(b"IHDR", ihdr) + png_chunk(b"IDAT", body) + png_chunk(b"IEND", b"") + trailing
    return A.png_encode(standard)


class ContractTests(unittest.TestCase):
    """任何机器都跑：接口、基线、门禁、校验器。"""

    def test_contract_constants(self):
        self.assertEqual((M.CID, M.CODE, M.PACKAGES, M.PACKAGE_VERSION), ("149996", "wind_spgirl_swim", [], {}))
        self.assertEqual((M.CAPABILITIES, M.REVIEWED_DRIFT), ([], {}))
        (unit,) = M.UNITS
        self.assertEqual((unit["CID"], unit["CODE"], unit["PACKAGES"], unit["PACKAGE_VERSION"]),
                         (M.CID, M.CODE, [], {}))
        self.assertEqual((unit["CAPABILITIES"], unit["REVIEWED_DRIFT"]), ([], {}))
        self.assertIs(unit["BEFORE"], M.BEFORE)
        self.assertIs(unit["revise"], M.revise)
        self.assertEqual(M.HANDOFF_ROOT, M.REPO / "work" / "gray3" / "handoff_v2")     # /work/ 已 gitignore
        self.assertEqual(M.HANDOFF_SHA256, "00db9a563597bf5a132197ba7a32acd6681be4c5f7838dd529bbaf3781bfbce2")

    def test_the_fourteen_members(self):
        self.assertEqual(len(M.FILES), 14)
        self.assertEqual(VOICES, EXPECTED_VOICES)
        self.assertEqual(sorted(set(M.FILES) - set(VOICES)), [M.BANNER])
        self.assertEqual(M.BANNER, "medium:character/wind_spgirl_swim/ui/episode_banner_0.png")
        self.assertEqual(set(M.DECODED_SHA256), set(M.FILES))
        self.assertEqual(set(M.LIVE_VOICE), set(VOICES))
        for member, want in M.FILES.items():
            self.assertRegex(want, r"^[0-9a-f]{64}$", member)
            self.assertNotEqual(want, M.DECODED_SHA256[member], member)                # 存储态 ≠ 标准态
            self.assertTrue(M.cdn_member(member).startswith(M.HANDOFF_DIR + "/cdn/"), member)
            self.assertTrue(M.decoded_member(member).startswith(M.HANDOFF_DIR + "/decoded/character/"), member)

    def test_before_is_the_live_sha_of_every_target(self):
        self.assertEqual(set(M.BEFORE), {("file_sha256", M.split_member(m)) for m in M.FILES})
        self.assertEqual(M.BEFORE["file_sha256", M.split_member(M.BANNER)], M.digest(None))   # live 没有横幅
        for member in VOICES:
            live = M.LIVE_VOICE[member]
            self.assertEqual(M.BEFORE["file_sha256", M.split_member(member)], M.digest(live["sha256"]), member)
            self.assertNotEqual(live["sha256"], M.FILES[member], member)             # 13 条都与灰版不同

    def test_fixture_is_the_before_baseline(self):
        before_keys = {live_key(kind, key) for kind, key in M.BEFORE}
        self.assertEqual(set(DATA["live"]), before_keys | {SPEECH_KEY, CHAR_KEY})
        for (kind, key), want in M.BEFORE.items():
            self.assertEqual(M.digest(DATA["live"][live_key(kind, key)]), want, (kind, key))
        self.assertEqual(DATA["_meta"]["absent"], [live_key("table", (M.CHARACTER_QUEST, k)) for k in M.QUEST_KEYS])

    def test_before_drift_is_rejected_before_touching_the_source(self):
        for kind, key in M.BEFORE:
            live = deepcopy(DATA["live"])
            live[live_key(kind, key)] = "0" * 64
            with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
                run(live=live)
        live = deepcopy(DATA["live"])
        del live[live_key("file_sha256", M.split_member(VOICES[0]))]
        with self.assertRaisesRegex(ValueError, "live input unreadable"):
            run(live=live)

    def test_not_reapplicable_after_import(self):
        after = deepcopy(DATA["live"])
        for member, pin in M.FILES.items():
            after[live_key("file_sha256", M.split_member(member))] = pin
        with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
            run(live=after)
        # 只有横幅已落地、语音未落地也拒绝（半导入）。
        half = deepcopy(DATA["live"])
        half[live_key("file_sha256", M.split_member(M.BANNER))] = M.FILES[M.BANNER]
        with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
            run(live=half)

    def test_reference_gates_run_before_the_source(self):
        speech = DATA["live"][SPEECH_KEY]
        paths = {row[0]: row[4] for row in speech if row[0] in ("1", "2")}
        self.assertEqual(paths, {"2": "ally/join", "1": "ally/evolution"})           # live 已指向这些逻辑路径
        self.assertEqual(DATA["live"][CHAR_KEY][0][0], M.CODE)
        self.assertEqual(DATA["live"][CHAR_KEY][0][8], M.CODE)

        live = deepcopy(DATA["live"])
        for row in live[SPEECH_KEY]:
            if row[0] == "2":
                row[4] = "ally/join_x"
        with self.assertRaisesRegex(ValueError, "voice_path drift"):
            run(live=live)
        live = deepcopy(DATA["live"])
        live[SPEECH_KEY] = [row for row in live[SPEECH_KEY] if row[0] != "1"]
        with self.assertRaisesRegex(ValueError, "voice_path drift"):
            run(live=live)
        for column in (0, 8):
            live = deepcopy(DATA["live"])
            live[CHAR_KEY][0][column] = "wind_spgirl"
            with self.assertRaisesRegex(ValueError, "c0/c8"):
                run(live=live)
        live = deepcopy(DATA["live"])
        live[live_key("table", (M.CHARACTER_QUEST, M.QUEST_KEYS[0]))] = [["1"]]
        with self.assertRaisesRegex(ValueError, "character_quest rows appeared"):
            run(live=live)
        live = deepcopy(DATA["live"])
        del live[SPEECH_KEY]
        with self.assertRaisesRegex(ValueError, "live input unreadable"):
            run(live=live)

    def test_source_bytes_are_rechecked_by_revise(self):
        class Tampered:
            def raw(self, tier, logical):
                return b"not the pinned bytes"

            def file_path(self, tier, logical):
                raise AssertionError("file_path before the sha check")
        with self.assertRaisesRegex(ValueError, "handoff member changed"):
            run(source=Tampered())

    # ------------------------------------------------------------ 校验器（合成字节）

    def test_mp3_facts_accepts_cbr_storage_state(self):
        data = stored_mp3([mp3_frame()] * 10)
        self.assertEqual(data[len(id3v2())], 0x7F)                                   # 存储态帧头
        facts = M.mp3_facts(data)
        self.assertEqual((facts["frames"], facts["bitrate_kbps"], facts["sample_rate"], facts["mpeg"], facts["channels"]),
                         (10, 96, 44100, "1", "mono"))
        self.assertEqual(facts["duration_s"], round(10 * 1152 / 44100, 4))
        self.assertEqual((facts["id3v2_bytes"], facts["id3v2_padding"]), (len(id3v2()), 64))
        self.assertEqual(facts["audio_sha256"], hashlib.sha256(data[len(id3v2()):]).hexdigest())
        # 只改标签填充：音频摘要与标签头/帧区摘要不变。
        shorter = stored_mp3([mp3_frame()] * 10, tag=id3v2(padding=20))
        other = M.mp3_facts(shorter)
        self.assertEqual((other["audio_sha256"], other["id3v2_head_frames_sha256"]),
                         (facts["audio_sha256"], facts["id3v2_head_frames_sha256"]))
        self.assertTrue(M.id3v2_layout(shorter)["padding_zero"])
        self.assertNotEqual(hashlib.sha256(shorter).hexdigest(), hashlib.sha256(data).hexdigest())
        self.assertEqual(other["id3v2_padding"] - facts["id3v2_padding"], len(shorter) - len(data))

    def test_mp3_facts_rejects_broken_audio(self):
        good = stored_mp3([mp3_frame()] * 4)
        with self.assertRaisesRegex(ValueError, "MP3 strict check failed: VBR"):
            M.mp3_facts(A._mp3_convert(id3v2() + mp3_frame() + mp3_frame(9) + mp3_frame(), 2047, 1023))
        with self.assertRaisesRegex(ValueError, "MP3 strict check failed"):         # 尾部含未转换的标准帧
            M.mp3_facts(good + mp3_frame()[:200] + b"\xff\xfb" + b"\0" * 700)
        with self.assertRaisesRegex(ValueError, "do not cover the file"):           # ≤512B 无同步字的杂质
            M.mp3_facts(good + b"\1" * 40)
        with self.assertRaisesRegex(ValueError, "round trip differs"):              # 标准态（未转存储态）
            M.mp3_facts(id3v2() + mp3_frame() * 4)
        with self.assertRaisesRegex(ValueError, "MP3 strict check failed"):
            M.mp3_facts(b"RIFF" + b"\0" * 100)

    def test_png_facts(self):
        facts = M.png_facts(stored_png())
        self.assertEqual((facts["size"], facts["mode"], facts["bit_depth"], facts["stored_magic"]),
                         ([4, 2], "RGBA", 8, "png"))
        with self.assertRaisesRegex(ValueError, "storage state"):
            M.png_facts(A.png_decode(stored_png()))
        corrupt = bytearray(stored_png())
        corrupt[40] ^= 0xFF
        with self.assertRaisesRegex(ValueError, "CRC|length|pixel"):
            M.png_facts(bytes(corrupt))
        with self.assertRaisesRegex(ValueError, "trailing"):
            M.png_facts(stored_png(trailing=b"junk"))
        with self.assertRaisesRegex(ValueError, "pixel data"):
            M.png_facts(stored_png(rows=b"\0" * 5))
        with self.assertRaisesRegex(ValueError, "pixel data"):
            M.png_facts(stored_png(rows=b"".join(b"\x07" + b"\0" * 16 for _ in range(2))))   # 滤波字节 7

    def test_handoff_source_guards(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = M.HandoffSource(root=Path(tmp) / "root", archive=Path(tmp) / "missing.zip")
            tier, logical = M.split_member(VOICES[0])
            with self.assertRaisesRegex(ValueError, "not a handoff import member"):
                source.raw("common", "character/wind_spgirl_swim/voice/home/kuga.mp3")
            with self.assertRaisesRegex(ValueError, "handoff member missing"):
                source.raw(tier, logical)
            with self.assertRaisesRegex(ValueError, "extracted member missing"):
                source.file_path(tier, logical)
            path = source.path(tier, logical)
            path.parent.mkdir(parents=True)
            path.write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "handoff member changed"):
                source.file_path(tier, logical)
            bad = Path(tmp) / "bad.zip"
            with zipfile.ZipFile(bad, "w") as zf:
                zf.writestr("x", b"y")
            with self.assertRaisesRegex(ValueError, "sha256 mismatch"):
                M.extract(Path(tmp) / "out", bad)
            with self.assertRaisesRegex(ValueError, "not found"):
                M.open_handoff(Path(tmp) / "missing.zip")
            self.assertFalse((Path(tmp) / "out").exists())


@unittest.skipUnless(HAS_EXTRACTED, "交付包解出目录（work/gray3/handoff_v2）不在本机；先跑 extract")
class RealSourceTests(unittest.TestCase):
    """本机真来源：解出目录里的 14 个文件。"""

    @classmethod
    def setUpClass(cls):
        cls.live = deepcopy(DATA["live"])
        cls.out = M.revise(reader(cls.live))                                          # 默认 HandoffSource()

    def test_files_are_the_extracted_pinned_bytes(self):
        files = self.out["files"]
        self.assertEqual(sorted(files), sorted(M.FILES))
        for member, path in files.items():
            self.assertTrue(Path(path).is_relative_to(M.HANDOFF_ROOT), path)
            self.assertEqual(Path(path), M.HANDOFF_ROOT.joinpath(*M.split_member(member)))
            self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(), M.FILES[member], member)
        self.assertEqual(self.out["notes"]["file_sha256"], M.FILES)                  # extra5 暂存后复核的钉子
        for kind in ("ability", "leader", "cas", "text", "table", "action", "dsl", "server_text",
                     "server_character", "nested_table", "presentation_table"):
            self.assertEqual(self.out[kind], {}, kind)
        self.assertEqual(self.out["new_programs"], [])
        json.dumps(self.out["notes"], ensure_ascii=False)

    def test_voices_only_differ_in_id3_padding(self):
        voices = self.out["notes"]["voices"]
        self.assertEqual((voices["count"], voices["audio_frames_identical"]), (13, 13))
        by_member = voices["by_member"]
        self.assertEqual(sorted(by_member), EXPECTED_VOICES)
        deltas = []
        for member, v in by_member.items():
            gray, live = v["gray"], v["live"]
            self.assertEqual(live, M.LIVE_VOICE[member], member)
            for facts in (gray, live):
                self.assertEqual((facts["bitrate_kbps"], facts["sample_rate"], facts["mpeg"], facts["channels"]),
                                 (96, 44100, "1", "mono"), member)
            self.assertEqual(gray["bytes"], len(Path(self.out["files"][member]).read_bytes()))
            self.assertTrue(v["audio_frames_identical"], member)
            self.assertTrue(v["id3v2_head_and_frames_identical"], member)
            self.assertEqual((v["delta_frames"], v["delta_duration_s"]), (0, 0.0), member)
            self.assertEqual(gray["duration_s"], live["duration_s"], member)
            self.assertEqual(v["id3v2_padding_delta"], v["delta_bytes"], member)       # 全部差异 = 填充
            self.assertEqual(live["id3v2_padding"], 2048, member)
            deltas.append(v["delta_bytes"])
            expected_ref = ("character_speech" if member.endswith(("ally/join.mp3", "ally/evolution.mp3"))
                            else "engine fixed name (CharacterShortVoiceLogic)")
            self.assertEqual(v["referenced_by"], expected_ref, member)
        self.assertEqual((min(deltas), max(deltas)), (-107, -9))
        durations = {m.rsplit("/", 1)[1]: v["gray"]["duration_s"] for m, v in by_member.items()}
        self.assertEqual((durations["evolution.mp3"], durations["skill_ready.mp3"]), (12.3037, 0.7314))

    def test_banner_matches_the_official_shape_and_is_dormant(self):
        banner = self.out["notes"]["banner"]
        self.assertEqual(banner["member"], M.BANNER)
        self.assertEqual(banner["facts"], {"bytes": 130883, "size": [430, 215], "bit_depth": 8, "mode": "RGBA",
                                           "stored_magic": "png"})
        self.assertEqual(banner["facts"]["size"], M.OFFICIAL_BANNER["size"])
        self.assertEqual(banner["table_references"]["hits"], 0)
        self.assertIn("休眠", banner["status"])
        refs = self.out["notes"]["references"]
        self.assertEqual((refs["string_id"], refs["image_prefix"]), (M.CODE, M.CODE))
        self.assertEqual(refs["character_quest_keys_absent"], ["14999601", "14999602", "14999603"])
        self.assertEqual(len(refs["speech_voice_paths"]), 8)
        self.assertTrue({"ally/join", "ally/evolution"} <= set(refs["speech_voice_paths"]))
        self.assertEqual(self.out["notes"]["tables_changed"][:1], "无")

    def test_not_in_handoff_home_voices(self):
        home = self.out["notes"]["not_in_handoff"]["home_voices"]
        self.assertEqual(len(home), 6)
        self.assertEqual({m.rsplit("/", 1)[1][:-4] for m in home},
                         {row[4].split("/", 1)[1] for row in DATA["live"][SPEECH_KEY] if row[4].startswith("home/")})
        for member, v in home.items():
            self.assertNotIn(member, M.FILES)
            self.assertTrue(v["audio_frames_identical"], member)
            self.assertLess(v["gray_chain_bytes"], v["live_bytes"], member)

    def test_inputs_not_mutated_and_output_detached(self):
        self.assertEqual(self.live, DATA["live"])
        out = M.revise(reader(deepcopy(DATA["live"])))
        member = VOICES[0]
        out["notes"]["voices"]["by_member"][member]["live"]["bytes"] = -1
        out["notes"]["banner"]["official"]["size"][0] = -1
        out["notes"]["not_in_handoff"]["home_voices"].clear()
        out["notes"]["file_sha256"].clear()
        self.assertEqual(M.LIVE_VOICE[member]["bytes"], self.out["notes"]["voices"]["by_member"][member]["live"]["bytes"])
        self.assertEqual(M.OFFICIAL_BANNER["size"], [430, 215])
        self.assertEqual(len(M.HOME_NOT_IN_HANDOFF), 6)
        self.assertEqual(len(M.FILES), 14)


@unittest.skipUnless(HAS_ZIP, "对方交付包 zip 不在本机")
class HandoffArchiveTests(unittest.TestCase):
    def test_extract_is_pinned_and_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "handoff_v2"
            self.assertEqual(M.extract(root), 14)
            self.assertEqual(M.extract(root), 0)
            written = sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())
            self.assertEqual(written, sorted(m.replace(":", "/", 1) for m in M.FILES))
            victim = root.joinpath(*M.split_member(M.BANNER))
            victim.write_bytes(b"x")
            self.assertEqual(M.extract(root), 1)
            self.assertEqual(hashlib.sha256(victim.read_bytes()).hexdigest(), M.FILES[M.BANNER])

    def test_zip_fallback_reads_every_member(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = M.HandoffSource(root=Path(tmp) / "empty")
            for member in M.FILES:
                tier, logical = M.split_member(member)
                self.assertEqual(hashlib.sha256(source.raw(tier, logical)).hexdigest(), M.FILES[member])
            with self.assertRaisesRegex(ValueError, "extracted member missing"):
                source.file_path(*M.split_member(M.BANNER))

    def test_decoded_members_are_the_standard_forms(self):
        with M.open_handoff() as zf:
            for member in M.FILES:
                stored = zf.read(M.cdn_member(member))
                decoded = zf.read(M.decoded_member(member))
                self.assertEqual(hashlib.sha256(decoded).hexdigest(), M.DECODED_SHA256[member])
                self.assertEqual(M.decode_standard(member, stored), decoded, member)
                if M.is_voice(member):
                    self.assertEqual(A.mp3_encode(decoded), stored, member)
                    head = M.id3v2_size(decoded)
                    self.assertEqual((decoded[head], stored[head]), (0xFF, 0x7F), member)
                else:
                    self.assertEqual((decoded[:4], stored[:4]), (b"\x89PNG", b"\x89png"))
            report = json.loads(zf.read(M.HANDOFF_DIR + "/HANDOFF_COMPLETE_REPORT.json"))
        self.assertEqual((report["character_id"], report["resource_tail"]), (M.CID, M.HANDOFF_RESOURCE_TAIL))
        self.assertEqual(report["coverage"]["voice"], 13)                            # 交付包只带 13 条语音


@unittest.skipUnless(LOCAL_STORE, "local live store required")
class LiveStoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import wf_mod_tool as core
        import wf_share_update_codec as X
        cls.core, cls.X = core, X
        cls.store = Path(core.resolve_active_store())

    def live_path(self, tier, logical):
        if tier == "common":
            return self.core.table_path(self.store, logical)
        return A.path_in_root(self.store, tier, logical)

    def table(self, logical):
        return self.X.unpack(self.core.table_path(self.store, logical).read_bytes())

    def test_live_is_either_the_baseline_or_the_import(self):
        for member in M.FILES:
            tier, logical = M.split_member(member)
            path = self.live_path(tier, logical)
            current = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
            self.assertIn(M.digest(current), {M.BEFORE["file_sha256", (tier, logical)], M.digest(M.FILES[member])},
                          member)
            if member in M.LIVE_VOICE and current == M.LIVE_VOICE[member]["sha256"]:
                self.assertEqual(dict(sha256=current, **M.mp3_facts(path.read_bytes())), M.LIVE_VOICE[member])

    def test_live_references(self):
        speech = self.X.csv_read(self.table(M.SPEECH)[M.CID])
        self.assertEqual({row[0]: row[4] for row in speech if row[0] in M.SPEECH_VOICES}, M.SPEECH_VOICES)
        character = self.X.csv_read(self.table(M.CHAR)[M.CID])[0]
        self.assertEqual((character[0], character[8]), (M.CODE, M.CODE))
        quests = self.table(M.CHARACTER_QUEST)
        self.assertFalse([k for k in quests if k.startswith(M.CID)])
        for home in M.HOME_NOT_IN_HANDOFF:
            tier, logical = M.split_member(home)
            data = self.live_path(tier, logical).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), M.HOME_NOT_IN_HANDOFF[home]["live_sha256"])

    def test_official_banners(self):
        sizes, second = {}, 0
        for value in self.table(M.CHAR).values():
            code = self.X.csv_read(value)[0][0]
            if code == M.CODE:
                continue
            found = A.locate(self.store, f"character/{code}/ui/episode_banner_0.png")
            if found:
                self.assertEqual(found[0], M.OFFICIAL_BANNER["tier"], code)
                data = found[1].read_bytes()
                self.assertEqual(data[:4], b"\x89png", code)
                sizes[code] = list(A.png_dims(data))
            second += bool(A.locate(self.store, f"character/{code}/ui/episode_banner_1.png"))
        self.assertEqual(len(sizes), M.OFFICIAL_BANNER["count"])
        self.assertEqual({tuple(s) for s in sizes.values()}, {tuple(M.OFFICIAL_BANNER["size"])})
        self.assertEqual(second, M.OFFICIAL_BANNER["slot_1_count"])
        for logical, size in M.OFFICIAL_BANNER["examples"].items():
            self.assertEqual(sizes[logical.split("/")[1]], size)

    def test_no_table_references_episode_banner(self):
        lines = (ROOT / "mod-tools/WF_PATHLIST_recovered.txt").read_text(encoding="utf-8", errors="replace").splitlines()
        masters = sorted({line.strip() for line in lines
                          if line.startswith("master/") and line.strip().endswith(".orderedmap")})
        self.assertEqual(len(masters), M.BANNER_TABLE_SCAN["pathlist_master_tables"])
        needles = [n.encode() for n in M.BANNER_TABLE_SCAN["needles"]]

        def blobs(raw, depth=0):
            yield raw
            if depth > 3:
                return
            try:
                inner = self.X.unpack(raw)
            except Exception:
                inner = None
            if isinstance(inner, dict):
                for value in inner.values():
                    if isinstance(value, bytes):
                        yield from blobs(value, depth + 1)
                return
            try:
                yield from blobs(zlib.decompress(raw), depth + 1)
            except Exception:
                pass

        present, hits = 0, []
        for logical in masters:
            path = self.core.table_path(self.store, logical)
            if not path.is_file():
                continue
            present += 1
            if any(n in blob for blob in blobs(path.read_bytes()) for n in needles):
                hits.append(logical)
        self.assertEqual((present, hits), (M.BANNER_TABLE_SCAN["present_in_live"], []))


@unittest.skipUnless(GRAY_CHAIN.is_file(), "灰链归档（gray-audit-20260830）不在本机")
class GrayChainProvenanceTests(unittest.TestCase):
    def test_handoff_bytes_are_the_gray_1488_bytes(self):
        import wf_mod_tool as core
        self.assertEqual(M._sha256_file(GRAY_CHAIN), M.GRAY_CHAIN_ZIP_SHA256)
        with zipfile.ZipFile(GRAY_CHAIN) as zf:
            by_tail = {}
            for name in zf.namelist():
                parts = name.split("/")
                if len(parts) >= 3:
                    by_tail[parts[-3], parts[-2] + parts[-1]] = name
            for member, pin in M.FILES.items():
                tier, logical = M.split_member(member)
                name = by_tail[M.TIER_ROOTS[tier], core.sha1_path(logical)]
                self.assertEqual(hashlib.sha256(zf.read(name)).hexdigest(), pin, member)
            for member, v in M.HOME_NOT_IN_HANDOFF.items():
                name = by_tail["upload", core.sha1_path(M.split_member(member)[1])]
                data = zf.read(name)
                self.assertEqual(hashlib.sha256(data).hexdigest(), v["gray_chain_sha256"], member)
                self.assertEqual(len(data), v["gray_chain_bytes"], member)
                self.assertEqual(M.mp3_facts(data)["duration_s"], v["duration_s"], member)


if __name__ == "__main__":
    unittest.main()
