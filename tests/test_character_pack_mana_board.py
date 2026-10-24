# -*- coding: utf-8 -*-
"""mana_board.json 作为可选服务端派生表进入角色包管线（临时目录 + 只读仓库）。

事实链：
1. `assets/mana_board.json` 是服务端玛纳板布局镜像，`src/lib/assets.ts` 的
   `getManaNodeAwakeCost` 查不到角色就返回 null → `/api/character/mana` 400。
2. 过去 `wf_character_pack.SERVER_LOGICAL_PATHS` 只列四项且被"恰好等于"断言钉死，
   `mana_board.json` 结构上进不了包。
3. 服务端行 = 客户端 `master/generated/mana_board.orderedmap` 三层树的 CSV 叶子
   原样：`mb[cid][board][slot] = [[nodeId,x,y,shape,pedestal,parent]]`。
   本机对 live store 全部 557 键逐字节复核通过（见 test_derivation_matches_repo_mirror）。
"""
from __future__ import annotations

import copy
import json
import sys
import unittest
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import wf_character_pack as pack  # noqa: E402
import wf_mod_tool as core  # noqa: E402
from test_character_pack import (  # noqa: E402
    _JsonFixtureCodec,
    _TransactionFixtureMixin,
    add_file,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _orderedmap(pairs: list[tuple[str, bytes]], *, compress: bool) -> bytes:
    """Build one orderedmap layer; `compress` matches the client's row encoding."""
    ordered = core.OrderedMap(
        "<fixture>", [key for key, _ in pairs], [row for _, row in pairs], Path("<fixture>")
    )
    return (
        core.build_orderedmap(ordered) if compress
        else core.build_orderedmap_raw_rows(ordered)
    )


def _client_mana_board(tree: dict[str, dict[str, dict[str, list[list[str]]]]]) -> bytes:
    """三层客户端表：外层=角色，中层=板，内层=槽（zlib CSV 叶子）。"""
    outer: list[tuple[str, bytes]] = []
    for character_id, boards in tree.items():
        middle: list[tuple[str, bytes]] = []
        for board_key, slots in boards.items():
            leaves = [
                (slot_key, core.write_csv_lines(rows).encode("utf-8"))
                for slot_key, rows in slots.items()
            ]
            middle.append((board_key, _orderedmap(leaves, compress=True)))
        outer.append((character_id, _orderedmap(middle, compress=False)))
    return _orderedmap(outer, compress=False)


_SAMPLE_TREE = {
    "149995": {
        "1": {
            "1": [["2999900", "-5", "0", "qqqqq", "2", "(None)"]],
            "2": [["2999901", "-5", "-5", "wwwww", "0", "2999900"]],
        },
        "2": {
            "1": [["2999950", "0", "0", "sssss", "0", "(None)"]],
        },
    },
    "111001": {
        "1": {"1": [["222002", "1", "2", "aaaaa", "0", "(None)"]]},
    },
}


class ServerLogicalPathContractTest(unittest.TestCase):
    """常量层：必需四项不变，mana_board.json 只是"可选"。"""

    def test_required_server_paths_are_unchanged(self) -> None:
        self.assertEqual(
            pack.REQUIRED_SERVER_LOGICAL_PATHS,
            (
                "cdndata/character.json",
                "cdndata/character_text.json",
                "character.json",
                "mana_node.json",
            ),
        )

    def test_legacy_alias_still_names_exactly_the_four_required_paths(self) -> None:
        """wf_seris_release_pack.SERVER_PATHS 直接引用该别名，不能改语义。"""
        self.assertEqual(
            pack.SERVER_LOGICAL_PATHS, pack.REQUIRED_SERVER_LOGICAL_PATHS
        )

    def test_mana_board_is_optional_not_required(self) -> None:
        self.assertIn(
            pack.SERVER_MANA_BOARD_LOGICAL, pack.OPTIONAL_SERVER_LOGICAL_PATHS
        )
        self.assertNotIn(
            pack.SERVER_MANA_BOARD_LOGICAL, pack.REQUIRED_SERVER_LOGICAL_PATHS
        )
        self.assertEqual(
            set(pack.ALLOWED_SERVER_LOGICAL_PATHS),
            set(pack.REQUIRED_SERVER_LOGICAL_PATHS)
            | set(pack.OPTIONAL_SERVER_LOGICAL_PATHS),
        )


class DeriveServerManaBoardTest(unittest.TestCase):
    """客户端三层树 → 服务端 mb[cid][board][slot]=[[...]]。"""

    def test_derives_every_character_when_no_filter_is_given(self) -> None:
        raw = _client_mana_board(_SAMPLE_TREE)
        self.assertEqual(pack.derive_server_mana_board(raw), _SAMPLE_TREE)

    def test_derives_only_the_requested_character(self) -> None:
        raw = _client_mana_board(_SAMPLE_TREE)
        self.assertEqual(
            pack.derive_server_mana_board(raw, ["149995"]),
            {"149995": _SAMPLE_TREE["149995"]},
        )

    def test_accepts_integer_character_ids(self) -> None:
        raw = _client_mana_board(_SAMPLE_TREE)
        self.assertEqual(
            set(pack.derive_server_mana_board(raw, [149995])), {"149995"}
        )

    def test_missing_character_fails_closed(self) -> None:
        raw = _client_mana_board(_SAMPLE_TREE)
        with self.assertRaises(pack.PackPreflightError):
            pack.derive_server_mana_board(raw, ["999999"])

    def test_malformed_table_fails_closed(self) -> None:
        with self.assertRaises(pack.PackPreflightError):
            pack.derive_server_mana_board(b"not-an-orderedmap")

    def test_rows_are_plain_strings_ready_for_json(self) -> None:
        raw = _client_mana_board(_SAMPLE_TREE)
        derived = pack.derive_server_mana_board(raw, ["149995"])
        json.dumps(derived, allow_nan=False)  # 必须能直接序列化进 assets/
        row = derived["149995"]["1"]["1"][0]
        self.assertEqual(len(row), 6)
        self.assertTrue(all(isinstance(cell, str) for cell in row))


class DerivationMatchesRepoMirrorTest(unittest.TestCase):
    """把派生规则钉在真数据上：live store 的客户端表 → 仓库现有服务端镜像。

    store 不在（CI/别的机器）时跳过；在的时候必须逐键逐字节相等。
    """

    LOGICAL = "master/generated/mana_board.orderedmap"

    @classmethod
    def setUpClass(cls) -> None:
        cls.mirror_path = REPO_ROOT / "assets" / "mana_board.json"
        profile = core.resolve_profile("cn")
        cls.table_path = (
            core.table_path(Path(profile.store), cls.LOGICAL)
            if profile is not None else None
        )

    def test_derivation_matches_repo_mirror(self) -> None:
        if self.table_path is None or not self.table_path.is_file():
            self.skipTest("CN live store 不可用")
        mirror = json.loads(self.mirror_path.read_text(encoding="utf-8"))
        derived = pack.derive_server_mana_board(self.table_path.read_bytes())
        shared = sorted(set(derived) & set(mirror))
        self.assertGreater(len(shared), 400, "样本太小，说明取错了表")
        mismatched = [key for key in shared if derived[key] != mirror[key]]
        self.assertEqual(mismatched[:10], [], "派生规则与仓库镜像不一致")
        self.assertEqual(
            sorted(set(derived) - set(mirror)), [],
            "客户端有玛纳板但服务端镜像没有 → /api/character/mana 会 400",
        )


class MergeServerJsonObjectTest(unittest.TestCase):
    """键级新增：不改既有键、不重排、紧凑分隔符、无尾换行。"""

    def test_appends_new_keys_and_keeps_existing_order_and_values(self) -> None:
        live = b'{"10":{"a":1},"20":{"b":2}}'
        merged = pack.merge_server_json_object(live, {"149995": {"c": 3}})
        self.assertEqual(merged, b'{"10":{"a":1},"20":{"b":2},"149995":{"c":3}}')

    def test_updates_an_existing_key_in_place_without_reordering(self) -> None:
        live = b'{"10":{"a":1},"20":{"b":2}}'
        merged = pack.merge_server_json_object(live, {"10": {"a": 9}})
        self.assertEqual(merged, b'{"10":{"a":9},"20":{"b":2}}')

    def test_uses_compact_separators_and_no_trailing_newline(self) -> None:
        merged = pack.merge_server_json_object(None, {"1": {"x": ["y"]}})
        self.assertEqual(merged, b'{"1":{"x":["y"]}}')
        self.assertFalse(merged.endswith(b"\n"))
        self.assertNotIn(b", ", merged)
        self.assertNotIn(b": ", merged)

    def test_non_ascii_is_written_verbatim_like_the_existing_mirrors(self) -> None:
        merged = pack.merge_server_json_object(None, {"1": "赛瑞斯"})
        self.assertEqual(merged.decode("utf-8"), '{"1":"赛瑞斯"}')

    def test_duplicate_keys_in_live_fail_closed(self) -> None:
        with self.assertRaises(pack.PackPreflightError):
            pack.merge_server_json_object(b'{"10":1,"10":2}', {"1": 1})

    def test_non_object_live_fails_closed(self) -> None:
        with self.assertRaises(pack.PackPreflightError):
            pack.merge_server_json_object(b"[1,2]", {"1": 1})


class BuildPackageManaBoardTest(unittest.TestCase):
    """包内客户端表 → 该包角色的服务端 mana_board 行。"""

    def setUp(self) -> None:
        self.temp = Path(
            __import__("tempfile").mkdtemp(prefix="mana-board-pack-")
        )
        self.addCleanup(
            lambda: __import__("shutil").rmtree(self.temp, ignore_errors=True)
        )
        self.package_dir = self.temp / "package"
        client = (
            self.package_dir / "roots" / "common" / "master" / "generated"
            / "mana_board.orderedmap"
        )
        client.parent.mkdir(parents=True, exist_ok=True)
        client.write_bytes(_client_mana_board(_SAMPLE_TREE))

    def test_extracts_only_the_manifest_character(self) -> None:
        rows = pack.package_server_mana_board_rows(self.package_dir, 149995)
        self.assertEqual(rows, {"149995": _SAMPLE_TREE["149995"]})

    def test_returns_none_when_the_package_has_no_client_table(self) -> None:
        empty = self.temp / "empty"
        (empty / "roots" / "common").mkdir(parents=True)
        self.assertIsNone(pack.package_server_mana_board_rows(empty, 149995))

    def test_character_absent_from_the_client_table_fails_closed(self) -> None:
        with self.assertRaises(pack.PackPreflightError):
            pack.package_server_mana_board_rows(self.package_dir, 129999)


class ServerRootContractTransactionTest(_TransactionFixtureMixin, unittest.TestCase):
    """老包（4 项）与新包（4+mana_board）都必须过 preflight；未知第五项仍拒绝。"""

    def _codecs(self) -> dict:
        return {"fixture_json": _JsonFixtureCodec(self.pack)}

    def _add_server_path(self, manifest: dict, logical_path: str) -> None:
        live_payload = {
            "outer": {"official": {"value": logical_path}},
            "inner": {},
            "semantics": {},
        }
        candidate_payload = copy.deepcopy(live_payload)
        candidate_payload["outer"]["129999"] = {
            "owner": "seris", "path": logical_path,
        }
        add_file(
            self.package_dir, manifest, "server", logical_path,
            json.dumps(candidate_payload, separators=(",", ":")).encode("utf-8"),
        )
        server_path = self.server / Path(*logical_path.split("/"))
        server_path.parent.mkdir(parents=True, exist_ok=True)
        server_path.write_bytes(
            json.dumps(live_payload, separators=(",", ":")).encode("utf-8")
        )
        manifest["tables"].append({
            "root": "server",
            "logical_path": logical_path,
            "codec_id": "fixture_json",
            "outer_keys": ["129999"],
            "inner_keys": [],
            "semantic_claims": [],
        })

    def test_legacy_four_path_package_still_preflights(self) -> None:
        self._finish_setup()
        report = self._tx(codec_registry=self._codecs()).preflight()
        self.assertTrue(report.can_prepare)

    def test_package_carrying_mana_board_preflights(self) -> None:
        self._finish_setup()
        manifest = copy.deepcopy(self.manifest)
        self._add_server_path(manifest, pack.SERVER_MANA_BOARD_LOGICAL)
        report = self._tx(
            manifest=manifest, codec_registry=self._codecs()
        ).preflight()
        self.assertTrue(report.can_prepare)
        prepared_server = {
            entry["logical_path"] for entry in manifest["roots"]["server"]
        }
        self.assertIn(pack.SERVER_MANA_BOARD_LOGICAL, prepared_server)

    def test_unknown_extra_server_path_is_still_rejected(self) -> None:
        self._finish_setup()
        manifest = copy.deepcopy(self.manifest)
        self._add_server_path(manifest, "item_lookup.json")
        with self.assertRaisesRegex(
            self.pack.PackPreflightError, "server root must contain exactly"
        ):
            self._tx(manifest=manifest, codec_registry=self._codecs()).preflight()

    def test_missing_required_server_path_is_still_rejected(self) -> None:
        self._finish_setup()
        manifest = copy.deepcopy(self.manifest)
        manifest["roots"]["server"] = [
            item for item in manifest["roots"]["server"]
            if item["logical_path"] != "mana_node.json"
        ]
        with self.assertRaisesRegex(
            self.pack.PackPreflightError, "server root must contain exactly"
        ):
            self._tx(manifest=manifest, codec_registry=self._codecs()).preflight()


if __name__ == "__main__":
    unittest.main()
