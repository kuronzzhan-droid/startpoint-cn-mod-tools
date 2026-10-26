"""季节换装七角色框架：规格唯一性/占用、认领合并幂等、表写入累积、manifest 重跑幂等与门禁。

真实产物不变量（需要 live store / 官方基线时自动跳过）：
tables→assets→manifest 后 validate_manifest==[]、_parse_transaction_claims 通过、对账全空、37/37；
重跑 tables 不覆盖 kit/美术产物；重跑 assets 不覆盖 art/voice 产物，也不静默回滚未登记改动。
"""
from __future__ import annotations

import dataclasses
import json
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest import mock

pass  # Imports resolve from this checkout/package, not external source copies.
import numpy as np  # noqa: E402

import wf_assets  # noqa: E402
import wf_mod_tool as core  # noqa: E402
import wf_seasonal7_art as ART  # noqa: E402
import wf_seasonal7_assets as A  # noqa: E402
import wf_seasonal7_build as B  # noqa: E402
import wf_seasonal7_common as C  # noqa: E402
import wf_seasonal7_manifest as M  # noqa: E402
import wf_seasonal7_specs as S  # noqa: E402
import wf_seasonal7_tables as T  # noqa: E402


def _flat_bytes(rows: dict[str, str]) -> bytes:
    return core.build_orderedmap(core.OrderedMap("t", list(rows), [v.encode("utf-8") for v in rows.values()],
                                                 Path("t")))


def _temp_pack(folder: Path, key: str = "regis") -> C.S7Pack:
    spec = S.get_spec(key, with_kit=False)
    store = folder / "store" / "upload"
    store.mkdir(parents=True)
    (folder / "assets").mkdir()
    pack = C.S7Pack(spec, root=folder, store=store, workspace=folder / "ws" / f"s7-{key}",
                    server_base=folder / "assets", use_official=False)
    B.step_init(pack)
    return pack


def _put_store_table(pack: C.S7Pack, logical: str, raw: bytes) -> None:
    path = core.table_path(pack.store, logical)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)


# 一帧静音 MPEG1 Layer3：只用来占位，`assets` 步只判存在不解码。
_SILENT_MP3 = b"\xff\xfb\x90\x64" + b"\x00" * 100


def _stub_speech_voices(pack: C.S7Pack) -> list[str]:
    """补齐母本没有同名文件的 voice_path。

    真实产线里 `wf_seasonal7_voice.py pack` 先于 `--step assets` 跑，自制语音已经在包里；
    重建类测试从空 workspace 出发没有这一步，所以在这里放占位文件，
    让「母本没有这条 voice_path」不再被当成产线缺陷。
    """
    stubbed = []
    for voice in A.speech_voice_logicals(pack):
        new_logical = f"character/{pack.spec.code}/voice/{voice}.mp3"
        if pack.pkg_has("common", new_logical):
            continue
        try:
            pack.template_asset(f"character/{pack.spec.template_code}/voice/{voice}.mp3")
        except FileNotFoundError:
            path = pack.pkg_path("common", new_logical)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(_SILENT_MP3)
            stubbed.append(voice)
    return stubbed


def _live_before_this_batch(pack_cls=C.S7Pack):
    """把 live 视图回退到「本角色尚未发布」的状态：只摘掉本角色自己的键。

    从空 workspace 重建一个**已经上线**的角色时，产线会（正确地）把 live 上那几行
    当成既有内容——占用闸门报 `already occupied in live`，`write_flat(only_missing=True)`
    也会保留线上行。真实流程走 `--installed-package-dir` / rebase，包里本来就带着这些键，
    重建类测试没有这一步。这里在 live 读取的两个入口上摘掉 `code` 与 `cid` 开头的键，
    别家的键一个不动，所以真·撞键仍然会红。
    """
    original_flat, original_base = pack_cls.live_flat, pack_cls.table_base

    def mine(spec, key: str) -> bool:
        return spec.code in key or key.startswith(spec.cid_s)

    def patched_flat(self, logical):
        return {k: v for k, v in original_flat(self, logical).items() if not mine(self.spec, k)}

    def patched_base(self, root, logical):
        raw, origin = original_base(self, root, logical)
        if logical.endswith(".json"):
            data = json.loads(raw)
            kept_json = {k: v for k, v in data.items() if not mine(self.spec, k)}
            if len(kept_json) == len(data):
                return raw, origin
            return json.dumps(kept_json, ensure_ascii=False).encode("utf-8"), origin
        table = core.read_orderedmap_raw_rows_from_bytes(raw, logical)
        kept = [(k, chunk) for k, chunk in zip(table.keys, table.rows) if not mine(self.spec, k)]
        if len(kept) == len(table.keys):
            return raw, origin
        return core.build_orderedmap_raw_rows(core.OrderedMap(
            logical, [k for k, _ in kept], [c for _, c in kept], Path(logical))), origin

    return mock.patch.multiple(pack_cls, live_flat=patched_flat, table_base=patched_base)


def _nested_bytes(logical: str, outer: dict[str, dict[str, str]]) -> bytes:
    blobs = [core.build_orderedmap(core.OrderedMap("i", list(inner), [v.encode("utf-8") for v in inner.values()],
                                                   Path("i"))) for inner in outer.values()]
    return core.build_orderedmap_raw_rows(core.OrderedMap(logical, list(outer), blobs, Path("x")))


def _live_available() -> bool:
    profile = core.resolve_profile()
    return (profile is not None and profile.store.is_dir()
            and (core.project_root() / "assets" / "mana_node.json").is_file()
            and (core.project_root() / ".cdn" / "cn").is_dir())


_LIVE = _live_available()


class SpecTests(unittest.TestCase):
    def test_seven_specs_unique_and_legal(self):
        self.assertEqual(len(S.SPECS), 7)
        for name in ("cid", "code", "pkg_id", "workspace"):
            values = [getattr(s, name) for s in S.SPECS.values()]
            self.assertEqual(len(values), len(set(values)), name)
        abilities = [k for s in S.SPECS.values() for k in s.ability_keys]
        self.assertEqual(len(abilities), len(set(abilities)))
        prefixes = [s.mana_prefix for s in S.SPECS.values()]
        self.assertEqual(len(prefixes), len(set(prefixes)))
        for spec in S.SPECS.values():
            self.assertIn(spec.stance, S.STANCES)
            self.assertEqual(S.ELEMENT_TOKENS[spec.element], spec.element_token)
            self.assertIn(spec.identity, (spec.cid, spec.template_identity))
            self.assertEqual(spec.requires_client_base, "1.4.858")
            self.assertEqual(spec.package_version, "1.0.0")
        self.assertEqual([s.key for s in S.SPECS.values() if s.element_flip], ["philia"])
        self.assertEqual(S.SPECS["philia"].template_token, "Green")

    def test_static_validator_rejects_duplicates_and_bad_stance(self):
        regis = S.SPECS["regis"]
        with self.assertRaises(AssertionError):
            S._validate_static((regis, dataclasses.replace(regis, key="other")))
        with self.assertRaises(AssertionError):
            S._validate_static((dataclasses.replace(regis, stance="Support"),))
        with self.assertRaises(AssertionError):
            S._validate_static((dataclasses.replace(regis, element_token="White"),))

    def test_identity_accepts_self_or_template_c27_only(self):
        regis = S.SPECS["regis"]
        S._validate_static((dataclasses.replace(regis, identity=regis.template_identity),))
        S._validate_static((dataclasses.replace(regis, identity=regis.cid),))
        with self.assertRaises(AssertionError):
            S._validate_static((dataclasses.replace(regis, identity=131020),))

    def test_extra_keys_shape_validated(self):
        regis = S.SPECS["regis"]
        S._validate_static((dataclasses.replace(regis, extra_keys={"master/x/y.orderedmap": ("1",)}),))
        for bad in ({"master/x/y.csv": ("1",)}, {"master/x/y.orderedmap": "13999401"},
                    {"../assets/x.json": ("1",)}):
            with self.assertRaises(AssertionError, msg=bad):
                S._validate_static((dataclasses.replace(regis, extra_keys=bad),))

    @unittest.skipUnless(core.resolve_profile() is not None and core.resolve_profile().store.is_dir()
                         and (core.project_root() / "assets" / "character.json").is_file(),
                         "requires live store and repo assets")
    def test_live_occupancy_all_free_with_positive_control(self):
        regis = S.SPECS["regis"]
        uc = "master/character/unique_condition.orderedmap"
        control = dataclasses.replace(regis, key="control", cid=169989, code="ruin_girl_campus",
                                      identity=169989, extra_keys={uc: ("16998901", "s7_unit_shared")})
        control2 = dataclasses.replace(regis, key="control2", cid=139980, code="s7_unit_free_code",
                                       identity=139980, extra_keys={uc: ("s7_unit_shared",)})
        problems = S.occupancy_problems([*S.SPECS.values(), control, control2], repo_root=core.project_root(),
                                        store=core.resolve_profile().store)
        live_chars = core.read_orderedmap_file(
            core.table_path(core.resolve_profile().store, "master/character/character.orderedmap"),
            "master/character/character.orderedmap").text_rows()
        for key, spec in S.SPECS.items():
            if spec.cid_s not in live_chars:
                self.assertEqual(problems[key], [], key)
                continue
            # 本批已上线（1.4.868-874）：占用项必然是自己发布的那几行。
            # 断言退化为「占用的每一条都指向本角色自己的键」，别家的键混进来仍然会红。
            own = [str(spec.cid), str(spec.cid * 2), spec.code,
                   *(k for keys in spec.extra_keys.values() for k in keys)]
            for line in problems[key]:
                self.assertTrue(any(token in line for token in own), (key, line))
        joined = "\n".join(problems["control"])
        self.assertIn("live character key occupied: 169989", joined)
        self.assertIn("live ability key occupied: 1699891", joined)
        self.assertIn("code_name occupied", joined)
        self.assertIn("live asset path occupied: character/ruin_girl_campus/", joined)     # 资产路径独立正控
        self.assertIn("assets/character.json: token 169989 occupied", joined)             # assets JSON 独立正控
        self.assertRegex(joined, "mana (node )?prefix 339978 occupied")
        self.assertIn(f"live extra key occupied: {uc}#16998901", joined)
        self.assertIn(f"extra key shared within batch with control2: {uc}#s7_unit_shared", joined)
        self.assertIn(f"extra key shared within batch with control: {uc}#s7_unit_shared",
                      "\n".join(problems["control2"]))


class ClaimMergeTests(unittest.TestCase):
    A = [{"codec_id": "flat", "inner_keys": [], "logical_path": "master/x.orderedmap",
          "outer_keys": ["2"], "root": "common", "semantic_claims": []},
         {"codec_id": "action_nested", "inner_keys": [{"outer_key": "code", "keys": ["1"]}],
          "logical_path": core.ACTION_SKILL_LOGICAL, "outer_keys": ["code"], "root": "common",
          "semantic_claims": []}]
    B_ = [{"codec_id": "flat", "inner_keys": [], "logical_path": "master/x.orderedmap",
           "outer_keys": ["1", "2"], "root": "common", "semantic_claims": []},
          {"codec_id": "action_nested", "inner_keys": [{"outer_key": "code", "keys": ["2", "1"]}],
           "logical_path": core.ACTION_SKILL_LOGICAL, "outer_keys": ["code"], "root": "common",
           "semantic_claims": []},
          {"codec_id": "json_object", "inner_keys": [], "logical_path": "character.json",
           "outer_keys": ["9"], "root": "server", "semantic_claims": []}]

    def test_union_and_idempotent(self):
        once = C.merge_claims(self.A, self.B_)
        self.assertEqual(once, C.merge_claims(once, []))
        self.assertEqual(once, C.merge_claims(once, self.A + self.B_))
        self.assertEqual(once[0]["outer_keys"], ["1", "2"])
        self.assertEqual(once[1]["inner_keys"], [{"keys": ["1", "2"], "outer_key": "code"}])
        self.assertEqual([c["root"] for c in once], ["common", "common", "server"])

    def test_inner_outer_key_is_added_to_outer_keys(self):
        merged = C.merge_claims([], [{"codec_id": "switched_nested", "logical_path": "master/s.orderedmap",
                                      "inner_keys": [{"outer_key": "k_voice_ready", "keys": ["1", "2"]}],
                                      "outer_keys": [], "root": "common", "semantic_claims": []}])
        self.assertEqual(merged[0]["outer_keys"], ["k_voice_ready"])

    def test_codec_conflict_rejected(self):
        bad = [{**self.A[0], "codec_id": "raw_outer"}]
        with self.assertRaises(C.S7Error):
            C.merge_claims(self.A, bad)


class PrimitiveGuardTests(unittest.TestCase):
    def test_amf_bytes_rejects_tree_numbers_wrapper(self):
        tree = ["ActionDsl", 2, ["Block", []]]
        self.assertEqual(C.amf_parse(C.amf_bytes(tree)), tree)
        with self.assertRaises(C.S7Error):
            C.amf_bytes({"tree": tree, "numbers": []})

    def test_check_identity_rejects_mismatched_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack = _temp_pack(Path(tmp))
            marker = pack.workspace / "workspace.json"
            payload = json.loads(marker.read_text(encoding="utf-8"))
            payload["code_name"] = "super_robot_tailcoat"
            marker.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(C.S7Error):
                pack.write_pkg("common", "x/y.bin", b"1")
            self.assertFalse(pack.pkg_path("common", "x/y.bin").exists())

    def test_template_asset_uses_official_when_live_was_modded(self):
        logical = "character/rec_android_1anv/pixelart/sprite_sheet.png"
        official, modded = b"\x89png-official", b"\x89png-modded-bytes"

        class FakeBaseline:
            def identity(self, root, rel):
                return (zlib.crc32(official) & 0xFFFFFFFF, len(official)) if root == "common" else None

            def get(self, root, rel):
                return official if root == "common" else None

        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / "store" / "upload"
            live = wf_assets.path_in_root(store, "upload", logical)
            live.parent.mkdir(parents=True)
            live.write_bytes(modded)
            pack = C.S7Pack(S.get_spec("regis", with_kit=False), root=Path(tmp), store=store,
                            workspace=Path(tmp) / "ws", baseline=FakeBaseline(), use_official=True)
            self.assertEqual(pack.template_asset(logical), ("common", official, "official(live differs)"))
            live.write_bytes(official)
            self.assertEqual(pack.template_asset(logical), ("common", official, "live=official"))

    def test_flip_ability_row_720_is_one_based(self):
        base = [""] * 126
        base[47] = "720"
        row = list(base)
        row[73] = "4"                     # 1 基 4 = 风
        out, changes = C.flip_ability_row(row, "ability", 3, 4)
        self.assertEqual(out[73], "5")
        self.assertEqual([c["col"] for c in changes], [73])
        row = list(base)
        row[73] = "3"                     # 1 基 3 = 雷：不是旧元素
        out, changes = C.flip_ability_row(row, "ability", 3, 4)
        self.assertEqual(out[73], "3")
        self.assertEqual(changes, [])
        row = list(base)
        row[47], row[73] = "33", "3"      # 普通 0 基
        self.assertEqual(C.flip_ability_row(row, "ability", 3, 4)[0][73], "4")

    def test_rewrite_effect_refs_only_copied_bases(self):
        src, dst = "battle/effect/skill_unique/donor", "battle/effect/skill_unique/newcode/beam"
        family = {"src_dir": src, "dst_dir": dst, "donor": "donor", "dst_name": "beam",
                  "copied_bases": ["donor_beam"]}
        tree = ["ActionDsl", [f"{src}/donor_beam", f"{src}/donor_beam_hit", f"{src}/.gen/donor_beam/0",
                              f"{src}/donor.png"]]
        new, report = C.rewrite_effect_refs(tree, family)
        self.assertEqual(new[1], [f"{dst}/donor_beam", f"{src}/donor_beam_hit", f"{dst}/.gen/donor_beam/0",
                                  f"{dst}/beam.png"])
        self.assertEqual(report["kept_donor"], [f"{src}/donor_beam_hit"])
        self.assertEqual(tree[1][0], f"{src}/donor_beam")                 # 输入不变
        with self.assertRaises(C.S7Error):
            C.rewrite_effect_refs(tree, family, strict=True)
        with self.assertRaises(C.S7Error):                                # 旧前缀映射造出的悬空引用
            C.rewrite_effect_refs(["x", f"{dst}/donor_beam_hit"], family)


class TableWriteTests(unittest.TestCase):
    def test_flat_raw_nested_server_writes_accumulate_and_keep_foreign_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack = _temp_pack(Path(tmp))
            flat = "master/ability/ability.orderedmap"
            live = {"100": "a,b", "200": "c,d"}
            live_raw = _flat_bytes(live)
            _put_store_table(pack, flat, live_raw)
            pack.write_flat(flat, {"1399941": [["x", "1"]]})
            pack.write_flat(flat, {"1399942": [["y", "2"]], "1399941": "kit,override"})
            pack.write_flat(flat, {"1399941": "placeholder,again"}, only_missing=True)
            rows = pack.pkg_flat(flat)
            self.assertEqual(rows["100"], "a,b")
            self.assertEqual(rows["200"], "c,d")
            self.assertEqual(rows["1399941"], "kit,override")
            self.assertEqual(rows["1399942"], "y,2")
            # 未改动行保留 live 原 zlib 字节
            live_rows = core.read_orderedmap_raw_rows_from_bytes(live_raw, flat)
            pkg_rows = core.read_orderedmap_raw_rows_from_bytes(pack.pkg_path("common", flat).read_bytes(), flat)
            self.assertEqual(dict(zip(pkg_rows.keys, pkg_rows.rows))["100"],
                             dict(zip(live_rows.keys, live_rows.rows))["100"])

            raw_logical = "master/character/character_status.orderedmap"
            _put_store_table(pack, raw_logical, core.build_orderedmap_raw_rows(
                core.OrderedMap(raw_logical, ["1"], [zlib.compress(b"9,9")], Path("x"))))
            pack.write_raw_outer(raw_logical, {"139994": zlib.compress(b"1,1")})
            pack.write_raw_outer(raw_logical, {"139995": zlib.compress(b"2,2")})
            raw = core.read_orderedmap_raw_rows_from_bytes(pack.pkg_path("common", raw_logical).read_bytes())
            self.assertEqual(raw.keys, ["1", "139994", "139995"])

            nested_logical = core.ACTION_SKILL_LOGICAL
            inner = core.build_orderedmap(core.OrderedMap("i", ["1"], [b"n,d,i,true,1,1,1,p/foreign"], Path("i")))
            _put_store_table(pack, nested_logical, core.build_orderedmap_raw_rows(
                core.OrderedMap(nested_logical, ["foreign"], [inner], Path("x"))))
            pack.write_nested(nested_logical, "rec_android_seaside", {"1": "a,b,c,true,1,1,1,p/1"})
            pack.write_nested(nested_logical, "rec_android_seaside", {"2": "a,b,c,true,1,1,1,p/2"})
            nested = core.load_nested_table_bytes(pack.pkg_path("common", nested_logical).read_bytes(),
                                                  nested_logical)
            self.assertEqual(list(nested.rows["rec_android_seaside"].text_rows()), ["1", "2"])
            self.assertEqual(nested.rows["foreign"].text_rows()["1"], "n,d,i,true,1,1,1,p/foreign")

            (pack.server_base / "character.json").write_text('{"1":{"name":"x"}}', encoding="utf-8")
            pack.write_server("character.json", {"139994": {"name": "a"}})
            pack.write_server("character.json", {"139995": {"name": "b"}})
            server = json.loads(pack.pkg_path("server", "character.json").read_bytes())
            self.assertEqual(list(server), ["1", "139994", "139995"])

            claims = {(c["root"], c["logical_path"]): c for c in pack.load_claims()}
            self.assertEqual(claims[("common", flat)]["outer_keys"], ["1399941", "1399942"])
            self.assertEqual(claims[("common", nested_logical)]["inner_keys"],
                             [{"keys": ["1", "2"], "outer_key": "rec_android_seaside"}])
            self.assertEqual(claims[("server", "character.json")]["outer_keys"], ["139994", "139995"])
            before = pack.evidence_path(C.CLAIMS_FILE).read_bytes()
            pack.write_flat(flat, {"1399942": [["y", "2"]]})
            self.assertEqual(pack.evidence_path(C.CLAIMS_FILE).read_bytes(), before)

    def test_write_flat_detects_unclaimed_row_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack = _temp_pack(Path(tmp))
            flat = "master/ability/ability.orderedmap"
            _put_store_table(pack, flat, _flat_bytes({"100": "a,b", "200": "c,d"}))
            original = core.build_orderedmap_raw_rows

            def tamper(om):
                om.rows[0] = zlib.compress(b"tampered")
                return original(om)

            with mock.patch.object(C.core, "build_orderedmap_raw_rows", side_effect=tamper):
                with self.assertRaisesRegex(C.S7Error, "unclaimed row drift"):
                    pack.write_flat(flat, {"1399941": "x,1"})
            self.assertFalse(pack.pkg_has("common", flat))

    def test_replace_inner_and_unclaim_keep_claims_in_sync_with_tables(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack = _temp_pack(Path(tmp))
            nl = core.ACTION_SKILL_LOGICAL
            _put_store_table(pack, nl, _nested_bytes(nl, {"foreign": {"1": "n,d,i,true,1,1,1,p/f"}}))
            rows = {str(i): f"a,b,c,true,1,1,1,p/{i}" for i in (1, 2, 3)}
            pack.write_nested(nl, "rec_android_seaside", rows)
            pack.write_nested(nl, "rec_android_seaside", {"1": rows["1"], "2": rows["2"]}, replace_inner=True)
            claim = next(c for c in pack.load_claims() if c["logical_path"] == nl)
            self.assertEqual(claim["inner_keys"], [{"keys": ["1", "2"], "outer_key": "rec_android_seaside"}])
            self.assertEqual(M.claimed_keys_missing(pack, claim), [])

            uc = "master/character/unique_condition.orderedmap"
            _put_store_table(pack, uc, _flat_bytes({"1": "live-row"}))
            pack.write_flat(uc, {"13999401": "a,b,"})
            pack.write_flat(uc, {"13999402": "a,b,"})
            pack.write_flat(uc, {"1": "kit-overrode-live"})
            removed = pack.unclaim(uc, ["13999401", "1"])
            self.assertEqual(removed["outer"], ["13999401", "1"])
            table = pack.pkg_flat(uc)
            self.assertNotIn("13999401", table)                       # 底表没有 = 删行
            self.assertEqual(table["1"], "live-row")                   # 底表有 = 恢复 live
            claim = next(c for c in pack.load_claims() if c["logical_path"] == uc)
            self.assertEqual(claim["outer_keys"], ["13999402"])
            pack.unclaim(uc, ["13999402"])
            self.assertFalse(any(c["logical_path"] == uc for c in pack.load_claims()))
            self.assertFalse(pack.pkg_has("common", uc))              # 与 live 相同的空认领表被删

            pack.unclaim(nl, root="common", inner_outer_key="rec_android_seaside", inner_keys=["2"])
            nested = core.load_nested_table_bytes(pack.pkg_path("common", nl).read_bytes(), nl)
            self.assertEqual(list(nested.rows["rec_android_seaside"].keys), ["1"])
            claim = next(c for c in pack.load_claims() if c["logical_path"] == nl)
            self.assertEqual(claim["inner_keys"], [{"keys": ["1"], "outer_key": "rec_android_seaside"}])

    def test_owned_outputs_are_not_overwritten_by_other_steps(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack = _temp_pack(Path(tmp))
            logical = "character/rec_android_seaside/ui/square_0.png"
            pack.write_asset("medium", logical, b"art", owner="art")
            self.assertFalse(pack.write_asset("medium", logical, b"native", respect_owner="assets"))
            self.assertEqual(pack.pkg_path("medium", logical).read_bytes(), b"art")
            self.assertTrue(pack.write_asset("medium", logical, b"art2", respect_owner="art"))
            self.assertEqual(pack.owned_record("medium", logical)["owner"], "art")
            self.assertEqual(pack.owned_record("medium", logical)["sha256"], C.sha256(b"art"))
            self.assertTrue(pack.modified_since_registration("medium", logical))   # art2 未重新登记

    def test_cell_remap_respects_prefix_codes_and_blob_bytes(self):
        spec = S.get_spec("tekuto", with_kit=False)       # super_robot → super_robot_tailcoat
        remap = T.cell_remap(spec)
        self.assertEqual(remap("super_robot"), "super_robot_tailcoat")
        self.assertEqual(remap("super_robot_3"), "super_robot_tailcoat_3")
        self.assertEqual(remap("character/super_robot/battle/character_detail_skill_preview"),
                         "character/super_robot_tailcoat/battle/character_detail_skill_preview")
        self.assertEqual(remap("change_skill_super_robot"), "change_skill_super_robot")
        self.assertEqual(remap(str(131092 * 2) + "201"), str(139993 * 2) + "201")
        self.assertEqual(remap("131092"), "139993")
        blob = zlib.compress(b"unchanged,cells", 9)
        self.assertIs(T.clone_blob(blob, remap), blob)
        key_map = T.custom_string_key_map(spec)
        self.assertEqual(key_map("change_skill_2_super_robot"), "change_skill_2_super_robot_tailcoat")
        self.assertEqual(key_map("change_skill_super_robot_2"), "change_skill_super_robot_tailcoat_2")
        self.assertIsNone(key_map("change_skill_super_robot_tailcoat"))

    def test_element_flip_helpers_report_cells(self):
        row = [""] * 126
        row[0], row[2], row[11], row[73] = "wind_oracle_meteor23_1", "attack_green", "Green,Red", "3"
        out, changes = C.flip_ability_row(row, "ability", 3, 4, label="k#L0")
        self.assertEqual((out[2], out[11], out[73]), ("attack_white", "White,Red", "4"))
        self.assertEqual({c["col"] for c in changes}, {2, 11, 73})
        tree = ["ActionDsl", ["Command", ["CreateNormalAttack", 3, 4, 1]],
                ["Command", ["FindAllSubjects", 0, 33, [4, 1]]]]
        flipped, dsl_changes = C.flip_dsl_elements(tree, 3, 4)
        self.assertEqual(flipped[1][1][2], 5)
        self.assertEqual(flipped[2][1][3], [5, 1])
        self.assertEqual(tree[1][1][2], 4)                # 输入不变
        self.assertEqual(len(dsl_changes), 2)

    def test_stance_detail_rolls_follow_new_stance(self):
        notes: list[dict] = []
        rows = [["", "1", "1", "2", "", "1", "1,5", "2"]]
        out = T.stance_detail_rows(rows, "Attacker", "Supporter", notes)
        self.assertEqual(out, [["", "1", "4", "2", "", "1", "4,5", "2"]])
        self.assertEqual({n["col"] for n in notes}, {2, 6})
        self.assertIs(T.stance_detail_rows(rows, "Attacker", "Attacker", []), rows)
        self.assertEqual(T.stance_detail_rows([["", "1", "", "2", "", "1", "", "2"]], "Attacker", "Healer", []),
                         [["", "1", "", "2", "", "1", "", "2"]])

    def test_stance_detail_rolls_capped_at_live_maximum(self):
        # 母本 Balance 没有可去掉的主 roll：131001 fox_oracle 的 "5,1" 不能变成无先例的 "4,5,1"
        rows = [["", "1,2,3,4", "5,1", "1", "", "1,2,3,4", "5,4", "1"]]
        out = T.stance_detail_rows(rows, "Balance", "Supporter", [])
        self.assertEqual(out, [["", "1,2,3,4", "4,5", "1", "", "1,2,3,4", "4,5", "1"]])
        self.assertTrue(all(len(c.split(",")) <= T.STANCE_ROLL_MAX for c in (out[0][2], out[0][6])))

    def test_element_material_map_by_kind_and_tier(self):
        def item(iid, el, kind, tier):
            cells = [f"ability_material_{iid}", str(iid), "n", "", "", "", "0", "", "", "", "", "", el, "",
                     "2", kind, "5", tier, "9999"]
            return C.csv_join([cells])
        items = {"13": item(13, "3", "9", "1"), "59": item(59, "3", "8", "3"),
                 "46": item(46, "4", "9", "1"), "65": item(65, "4", "8", "3"), "99": item(99, "", "10", "5")}
        self.assertEqual(T.element_material_map(items, 3, 4), {"13": "46", "59": "65"})
        items["47"] = item(47, "4", "9", "1")                     # 同槽两个目标 = 歧义
        with self.assertRaises(C.S7Error):
            T.element_material_map(items, 3, 4)
        mats = T.element_material_items({k: v for k, v in items.items() if k != "47"})
        blob = zlib.compress(C.csv_join([["318330201", "1", "13,59", "16,18", "100", "0", "0"]]).encode(), 9)
        changes: list[dict] = []
        out = T.remap_mana_node_items(blob, {"13": "46", "59": "65"}, changes)
        self.assertEqual(C.csv_split(zlib.decompress(out).decode())[0],
                         ["318330201", "1", "46,65", "16,18", "100", "0", "0"])
        self.assertEqual(len(changes), 1)
        self.assertEqual(T.mana_node_item_elements(out, mats), {"4": {"46", "65"}})


@unittest.skipUnless(_LIVE, "requires live store, repo assets and official baseline archives")
class LiveTablesRebuildTests(unittest.TestCase):
    def test_rebuild_keeps_kit_art_and_voice_edits_and_claims(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = S.get_spec("regis", with_kit=False)
            pack = C.S7Pack(spec, workspace=Path(tmp) / "s7-regis")
            B.step_init(pack)
            T.build(pack)
            claims_first = pack.evidence_path(C.CLAIMS_FILE).read_bytes()
            crow = pack.pkg_character_row()
            self.assertEqual((crow[0], crow[3], crow[6], crow[26], crow[27]),
                             (spec.code, "2", "2", "Supporter", str(spec.cid)))
            self.assertEqual(C.csv_split(pack.pkg_flat(T.STANCE_DETAIL)[spec.cid_s])[0][2], "4")
            # 母本词条从官方基线取（store 里 131020 被增强改过：官方 c1=false）
            ability = C.csv_split(pack.pkg_flat("master/ability/ability.orderedmap")["1399941"])
            self.assertEqual(ability[0][1], "false")
            # 模拟 kit / voice / art 改动
            edited = list(crow)
            edited[9] = "3"
            pack.write_flat(T.CHAR, {spec.cid_s: [edited]})
            pack.write_flat(T.ABILITY, {"1399941": [["kit_row", "true"]]})
            pack.write_flat(T.SPEECH, {spec.cid_s: [["0", "2", "", "voice", "home/new"],
                                                    ["1", "1", "1", "evo", "ally/evolution"]]})
            kit_tree = ["ActionDsl", 2, ["Block", []]]
            dsl_logical = pack.write_dsl(T.program_path(spec, "1"), kit_tree, owner="kit")
            kit_skill = B.KitContext(pack).pkg_nested(spec.code)["1"]
            kit_skill[4] = "777"
            pack.write_nested(T.ACTION, spec.code, {"1": [kit_skill]})
            pack.write_flat(T.LEADER, {spec.cid_s: [[spec.code, "kit_leader"]]})
            art_blob = zlib.compress(b"1,2,3,4", 9)
            pack.write_raw_outer(T.CHAR_IMAGE, {spec.cid_s: art_blob})
            T.build(pack)
            self.assertEqual(pack.pkg_character_row()[9], "3")
            self.assertEqual(pack.pkg_flat(T.ABILITY)["1399941"], "kit_row,true")
            self.assertIn("home/new", pack.pkg_flat(T.SPEECH)[spec.cid_s])
            self.assertEqual(C.amf_parse(pack.pkg_path("common", dsl_logical).read_bytes()), kit_tree)
            inner = core.load_nested_table_bytes(pack.pkg_path("common", T.ACTION).read_bytes(), T.ACTION)
            self.assertEqual(C.csv_split(inner.rows[spec.code].text_rows()["1"])[0][4], "777")
            self.assertEqual(pack.pkg_flat(T.LEADER)[spec.cid_s], f"{spec.code},kit_leader")
            image = core.read_orderedmap_raw_rows_from_bytes(pack.pkg_path("common", T.CHAR_IMAGE).read_bytes())
            self.assertEqual(dict(zip(image.keys, image.rows))[spec.cid_s], art_blob)
            self.assertEqual(pack.evidence_path(C.CLAIMS_FILE).read_bytes(), claims_first)
            mirror = json.loads(pack.pkg_path("server", "cdndata/character.json").read_bytes())
            self.assertEqual(mirror[spec.cid_s], [pack.pkg_character_row()])

    def test_philia_element_flip_covers_mana_materials_cas_and_speech_voices(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = S.get_spec("philia", with_kit=False)
            pack = C.S7Pack(spec, workspace=Path(tmp) / "s7-philia")
            B.step_init(pack)
            with _live_before_this_batch():
                report = T.build(pack)
            materials = T.element_material_items(pack.template_flat(T.ITEM))
            node_raw = core.read_orderedmap_raw_rows_from_bytes(pack.pkg_path("common", T.MANA_NODE).read_bytes())
            used = T.mana_node_item_elements(dict(zip(node_raw.keys, node_raw.rows))[spec.cid_s], materials)
            self.assertEqual(set(used), {"4"})
            server = json.loads(pack.pkg_path("server", "mana_node.json").read_bytes())[spec.cid_s]
            server_items = {i for board in server.values() for node in board.values() for i in node["items"]}
            self.assertTrue(server_items <= {"46", "47", "48", "49", "65", "66", "67", "99"}, server_items)
            self.assertEqual(report["server_mana_crosscheck"]["mana_node.json"], "match")
            self.assertTrue(any(c.get("table") == T.MANA_NODE for c in report["element_flip"]["cells"]))
            self.assertEqual(C.csv_split(pack.pkg_flat(T.STANCE_DETAIL)[spec.cid_s])[0][6], "4")
            rows = C.csv_split(pack.pkg_flat(T.ABILITY)["1599963"])
            self.assertEqual(rows[1][70], "change_skill_wind_oracle_yukata")
            cas = pack.pkg_flat(T.CAS)
            self.assertIn("change_skill_wind_oracle_yukata", cas)
            self.assertIn("change_skill_wind_oracle_yukata_2", cas)
            claims = {c["logical_path"]: c for c in pack.load_claims()}
            self.assertEqual(claims[T.CAS]["outer_keys"],
                             ["change_skill_wind_oracle_yukata", "change_skill_wind_oracle_yukata_2"])
            _stub_speech_voices(pack)
            A.build(pack)
            for cells in C.csv_split(pack.pkg_flat(T.SPEECH)[spec.cid_s]):
                if cells[4] not in ("", "(None)"):
                    self.assertTrue(pack.pkg_has("common", f"character/{spec.code}/voice/{cells[4]}.mp3"), cells[4])


@unittest.skipUnless(_LIVE, "requires live store, repo assets and official baseline archives")
class LivePipelineTests(unittest.TestCase):
    """真实包 tables→assets→manifest：清单合法、认领可解析、对账全空、37/37；重跑 assets 的所有权保护。"""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        spec = S.get_spec("regis", with_kit=False)
        cls.pack = C.S7Pack(spec, workspace=Path(cls._tmp.name) / "s7-regis")
        B.step_init(cls.pack)
        T.build(cls.pack)
        _stub_speech_voices(cls.pack)
        A.build(cls.pack)
        cls.report = M.build(cls.pack)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_manifest_contract_holds_on_real_package(self):
        import wf_character_pack as P
        pack, report = self.pack, self.report
        manifest = json.loads((pack.package / "manifest.json").read_bytes())
        self.assertEqual(report["validate_manifest"], [])
        self.assertEqual(P.validate_manifest(manifest, pack.package, require_referenced_assets=True), [])
        P._parse_transaction_claims(manifest)
        self.assertEqual(report["reconcile"], {"tables_not_in_roots": [], "root_tables_not_claimed": [],
                                               "claim_codec_mismatch": [], "claimed_keys_missing": []})
        self.assertEqual(report["required"], "37/37")
        self.assertEqual(manifest["qa"]["required_assets_present"], 37)
        self.assertEqual(manifest["qa"]["missing_required"], [])
        self.assertFalse(manifest["qa"]["release_ready"])

    def test_manifest_gate_raises_on_unclaimed_table_invalid_png_and_missing_claim(self):
        pack = self.pack
        stray = pack.pkg_path("common", "master/unit/unclaimed.orderedmap")
        stray.parent.mkdir(parents=True, exist_ok=True)
        stray.write_bytes(_flat_bytes({"1": "x"}))
        try:
            with self.assertRaisesRegex(C.S7Error, "root_tables_not_claimed"):
                M.build(pack)
        finally:
            stray.unlink()
            stray.parent.rmdir()
        bad_png = pack.pkg_path("medium", f"character/{pack.spec.code}/ui/zz_unit_bad.png")
        bad_png.write_bytes(b"not a png at all")
        try:
            with self.assertRaisesRegex(C.S7Error, "validate_manifest"):
                M.build(pack)
            self.assertTrue(any("zz_unit_bad.png" in e
                                for e in pack.read_evidence("manifest_report.json")["validate_manifest"]))
        finally:
            bad_png.unlink()
        claims_path = pack.evidence_path(C.CLAIMS_FILE)
        saved = claims_path.read_bytes()
        pack.claim(T.CHAR, ["s7_unit_absent_key"])
        try:
            with self.assertRaisesRegex(C.S7Error, "claimed_keys_missing"):
                M.build(pack)
        finally:
            claims_path.write_bytes(saved)
        M.build(pack)                                                  # 恢复后通过

    def test_assets_rerun_respects_owners_and_refuses_silent_revert(self):
        pack, code = self.pack, self.pack.spec.code
        icon = f"character/{code}/ui/square_0.png"
        pack.write_asset("medium", icon, wf_assets.png_encode(b"\x89PNG\r\n\x1a\nart"), owner="art")
        art_bytes = pack.pkg_path("medium", icon).read_bytes()
        voice = f"character/{code}/voice/ally/join.mp3"
        voice_path = pack.pkg_path("common", voice)
        native_voice = voice_path.read_bytes()
        voice_path.write_bytes(b"NEWVOICE" + native_voice[8:])            # 语音步骤直写、未登记
        frame = f"character/{code}/pixelart/pixelart.frame.amf3.deflate"
        frame_path = pack.pkg_path("common", frame)
        native_frame = frame_path.read_bytes()
        frame_path.write_bytes(native_frame + b"\0")                      # 其他步骤直写、未登记
        try:
            with self.assertRaisesRegex(C.S7Error, "refusing to overwrite"):
                A.build(pack)
            self.assertEqual(frame_path.read_bytes(), native_frame + b"\0")
            frame_path.write_bytes(native_frame)
            report = A.build(pack)
            self.assertEqual(pack.pkg_path("medium", icon).read_bytes(), art_bytes)
            self.assertEqual(voice_path.read_bytes()[:8], b"NEWVOICE")
            self.assertIn(voice, [v["target"] for v in report["kept_existing_voices"]])
            self.assertIn(icon, [v["target"] for v in report["skipped_owned_by_other_steps"]])
        finally:
            voice_path.write_bytes(native_voice)
            frame_path.write_bytes(native_frame)
            pack.pkg_path("medium", icon).unlink()
            owned = json.loads(pack.evidence_path(C.OWNED_FILE).read_text(encoding="utf-8"))
            owned.pop(f"medium:{icon}", None)
            pack.write_evidence(C.OWNED_FILE, owned)
            A.build(pack)

    def test_flow_status_evidence_is_utf8_clean(self):
        result = B.step_status(self.pack)
        payload_text = self.pack.evidence_path("flow-status.json").read_text(encoding="utf-8")
        self.assertNotIn("�", payload_text)
        self.assertRegex(payload_text, "[一-鿿]")
        self.assertEqual(result["required_present"], 37)


class BuildCliTests(unittest.TestCase):
    def test_next_command_points_at_actual_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack = _temp_pack(Path(tmp))
            payload = {"ok": True, "next_command": "python mod-tools/wf_character_flow.py preflight "
                                                   "--workspace work/character_packs/s7-regis-20260916"}
            fixed = B.summarize_status(payload, pack)["next_command"]
            self.assertNotIn("s7-regis-20260916", fixed)
            self.assertTrue(fixed.endswith("ws/s7-regis"), fixed)

    def test_flow_subprocess_forces_utf8(self):
        seen = {}

        def fake_run(cmd, **kw):
            seen.update(kw)
            return mock.Mock(returncode=0, stdout='{"ok": true, "x": "中・♪"}\n', stderr="")

        with mock.patch.object(B.subprocess, "run", side_effect=fake_run):
            rc, payload = B._flow("status", Path("ws"), Path("."))
        self.assertEqual(seen["env"]["PYTHONIOENCODING"], "utf-8")
        self.assertEqual(seen["encoding"], "utf-8")
        self.assertEqual(payload["x"], "中・♪")

    def test_status_and_preflight_gates(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack = _temp_pack(Path(tmp))
            with mock.patch.object(B, "_flow", return_value=(2, {"ok": False, "errors": ["boom"]})):
                with self.assertRaises(C.S7Error):
                    B.step_status(pack)
            with mock.patch.object(B, "_flow") as flow:
                with self.assertRaisesRegex(C.S7Error, "draft"):
                    B.step_preflight(pack)
                flow.assert_not_called()
                pack.write_evidence("kit-report.json", {"status": "draft"})
                with self.assertRaisesRegex(C.S7Error, "draft"):
                    B.step_preflight(pack)
                flow.assert_not_called()

    def test_inspect_never_touches_real_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack = _temp_pack(Path(tmp))
            manifest = pack.package / "manifest.json"
            before = manifest.read_bytes()
            copies = []

            def fake_flow(command, workspace, root, extra=None):
                copies.append(workspace)
                (workspace / "package" / "manifest.json").write_text('{"sealed": true}', encoding="utf-8")
                return 0, {"ok": True, "release_ready": True,
                           "next_command": f"publish --workspace {workspace}", "preflight": {"can_prepare": True}}

            with mock.patch.object(B, "_flow", side_effect=fake_flow):
                result = B.step_inspect(pack)
            self.assertEqual(manifest.read_bytes(), before)
            self.assertFalse(copies[0].exists())
            self.assertFalse(result["sealed_real_workspace"])
            self.assertFalse(result["kit_ready"])
            self.assertNotIn(str(copies[0]), result["flow_next_command"])
            self.assertTrue(result["flow_next_command"].endswith("ws/s7-regis"), result["flow_next_command"])
            self.assertIn("草稿包", result["next_command"])
            self.assertTrue(pack.evidence_path("flow-inspect.json").is_file())


class ArtMaskTests(unittest.TestCase):
    def test_median_mask_drops_individual_silhouettes(self):
        yy, xx = np.mgrid[:58, :58]
        circle = (((yy - 28.5) ** 2 + (xx - 28.5) ** 2) <= 27 ** 2).astype(np.uint8) * 255
        samples = []
        for i in range(21):
            alpha = circle.copy()
            band = (i % 3) * 15
            alpha[band:band + 10, 0:4] = 255                    # 每 1/3 的角色各自出框的一块
            alpha[20 + band // 3 * 2:25 + band // 3 * 2, 20:25] = 0   # 各自的透明洞（剪影）
            samples.append(alpha)
        mask = ART.shape_masks_from_samples({"battle_member_status": samples})["battle_member_status"]
        self.assertTrue(np.array_equal(mask > 127, circle > 127))
        self.assertEqual(int(mask[5, 0]), 0)
        with self.assertRaises(ValueError):
            ART.shape_masks_from_samples({"battle_member_status": samples[:3]})

    def test_mask_cache_is_sha_bound_and_not_template_derived(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack = _temp_pack(Path(tmp))
            cache = Path(tmp) / "masks.npz"
            masks = {slot: np.full(ART.gate.OFFICIAL_ICON_SIZES[slot][::-1], 255, np.uint8)
                     for slot in ART.gate.SHAPE_SLOTS}
            np.savez_compressed(cache, **masks)
            cache.with_suffix(".json").write_text(json.dumps({"method": ART.MASK_METHOD,
                                                              "cache_sha256": C.sha256(cache.read_bytes())}),
                                                  encoding="utf-8")
            loaded, source = ART._load_masks(pack, 0, cache)          # 包里没有任何母本图标也能取到
            self.assertEqual(set(loaded), set(ART.gate.SHAPE_SLOTS))
            self.assertEqual(source["method"], ART.MASK_METHOD)
            cache.write_bytes(cache.read_bytes() + b"\0")
            with self.assertRaises(ValueError):
                ART._load_masks(pack, 0, cache)


class KitContextTests(unittest.TestCase):
    def test_kit_context_writes_accumulate_and_manifest_merges_kit_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack = _temp_pack(Path(tmp))
            if S.load_kit_module("regis") is None:
                self.assertTrue(B.step_kit(pack)["skipped"])
            flat = "master/ability/leader_ability.orderedmap"
            _put_store_table(pack, flat, _flat_bytes({"1": "foreign"}))
            ctx = B.KitContext(pack)
            ctx.write_flat(flat, {"139994": [["rec_android_seaside", "0"]]})
            program = ctx.program_path("1")
            self.assertEqual(program, "battle/action/skill/action/rare5/rec_android_seaside$rec_android_seaside_1")
            logical = ctx.write_dsl(program, ["ActionDsl", 2, ["Block", []]])
            self.assertEqual(pack.owner_of("common", logical), "kit")
            ctx.report({"summary": "unit", "skills": {"programs": [logical]},
                        "unique_condition": {"13999401": {"icon": "battle/common/unique_condition/x.png"}},
                        "required_capabilities": ["panel-description-override-v2"]})
            M.build(pack)
            manifest = json.loads((pack.package / "manifest.json").read_bytes())
            self.assertEqual(manifest["skills"]["programs"], [logical])
            self.assertIn("13999401", manifest["unique_condition"])
            self.assertEqual(manifest["required_capabilities"], ["panel-description-override-v2"])
            self.assertEqual(manifest["snapshot"]["seasonal7"]["reports"]["kit"]["summary"], "unit")


class ManifestRerunTests(unittest.TestCase):
    def test_manifest_rebuild_is_byte_idempotent_and_preserves_integrations(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack = _temp_pack(Path(tmp))
            flat = "master/character/character.orderedmap"
            _put_store_table(pack, flat, _flat_bytes({"1": "x"}))
            pack.write_flat(flat, {"139994": "rec_android_seaside"})
            (pack.server_base / "character.json").write_text("{}", encoding="utf-8")
            pack.write_server("character.json", {"139994": {"name": "雷吉斯"}})
            pack.write_asset("common", "battle/action/skill/action/rare5/rec_android_seaside$rec_android_seaside_1"
                             ".action.dsl.amf3.deflate", C.amf_bytes(["ActionDsl", 2]))
            first = M.build(pack)
            raw1 = (pack.package / "manifest.json").read_bytes()
            manifest = json.loads(raw1)
            manifest["snapshot"]["seasonal7_art"] = {"visual_review_pending": True}
            manifest["unique_condition"] = {"13999401": {"icon": "x"}}
            manifest["qa"]["release_ready"] = True
            (pack.package / "manifest.json").write_bytes(json.dumps(manifest).encode("utf-8"))
            second = M.build(pack)
            raw2 = (pack.package / "manifest.json").read_bytes()
            third = M.build(pack)
            raw3 = (pack.package / "manifest.json").read_bytes()
            self.assertEqual(raw2, raw3)
            self.assertEqual(second["manifest_sha256"], third["manifest_sha256"])
            final = json.loads(raw3)
            self.assertFalse(final["qa"]["release_ready"])
            self.assertEqual(final["qa"]["workspace_input_sha256"], "")
            self.assertIn("seasonal7_art", final["snapshot"])
            self.assertEqual(final["unique_condition"], {"13999401": {"icon": "x"}})
            self.assertEqual(final["requires_client_base"], "1.4.858")
            self.assertEqual(final["package_version"], "1.0.0")
            self.assertEqual(len(final["skills"]["programs"]), 1)
            self.assertEqual(first["reconcile"]["root_tables_not_claimed"], [])
            self.assertEqual({(t["root"], t["logical_path"]) for t in final["tables"]},
                             {("common", flat), ("server", "character.json")})

    def test_manifest_gate_raises_on_unclaimed_table_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack = _temp_pack(Path(tmp))
            stray = pack.pkg_path("common", "master/unit/unclaimed.orderedmap")
            stray.parent.mkdir(parents=True)
            stray.write_bytes(_flat_bytes({"1": "x"}))
            with self.assertRaisesRegex(C.S7Error, "root_tables_not_claimed"):
                M.build(pack)
            self.assertEqual(pack.read_evidence("manifest_report.json")["reconcile"]["root_tables_not_claimed"],
                             ["common:master/unit/unclaimed.orderedmap"])


if __name__ == "__main__":
    unittest.main()
