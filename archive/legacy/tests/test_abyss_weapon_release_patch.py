import copy
import json
import re
import subprocess
import sys
import tempfile
import unittest
import zipfile
import zlib
from collections import deque
from io import BytesIO
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
pass  # Imports resolve from this checkout/package, not external source copies.

import build_abyss_weapon_balance_patch as builder  # noqa: E402
import wf_rogue_rewards as rewards  # noqa: E402


MANIFEST = ROOT / "assets" / "asset-patch" / "manifest.json"
ARCHIVE_NAME = "pinball-1.4.105-1.4.106-1-abyssbalance0718.zip"
ARCHIVE = ROOT / "assets" / "asset-patch" / "active" / ARCHIVE_NAME
ARCHIVE_SHA256 = "e9ec4451ac5b3101f060c74278fd8901b7c207c57f19e313084ff9f9639f7272"
CURRENT_STATUS = (
    ROOT / "mod-tools" / "release-contracts" / "abyss_weapon_current.json"
)
EDGE_RE = re.compile(r"^pinball-(1\.4\.\d+)-(1\.4\.\d+)-\d+-.+\.zip$")


class AbyssWeaponReleasePatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.archive_bytes = ARCHIVE.read_bytes()
        with zipfile.ZipFile(BytesIO(cls.archive_bytes)) as archive:
            cls.members = archive.namelist()
            cls.bad_member = archive.testzip()
            cls.member_bytes = {name: archive.read(name) for name in cls.members}
            cls.infos = archive.infolist()
            cls.archive_comment = archive.comment

    def historical_inputs(self) -> tuple[bytes, dict[str, object], bytes]:
        soul_bytes = self.member_bytes[builder.SOUL_MEMBER]
        official_soul = builder.parse_table(
            builder.strip_custom_soul_rows(soul_bytes), builder.SOUL_LOGICAL
        )
        return (
            builder.checked_bridge(builder.BRIDGE_ARCHIVE),
            official_soul,
            self.member_bytes[builder.WAB_MEMBER],
        )

    def test_enabled_tail_edge_is_published(self) -> None:
        matches = [
            patch
            for patch in self.manifest["patches"]
            if patch.get("id") == "abyss-weapon-balance-v1"
        ]
        self.assertEqual(1, len(matches))
        patch = matches[0]
        self.assertTrue(patch["enabled"])
        self.assertEqual("1.4.105", patch["depends_on"])
        self.assertEqual("1.4.106", patch["version"])
        self.assertEqual([ARCHIVE_NAME], patch["chain"])
        self.assertEqual("2026-07-18", patch["created_at"])
        self.assertTrue(ARCHIVE.is_file())

    def test_enabled_chain_reaches_tail_continuously(self) -> None:
        graph: dict[str, set[str]] = {}
        for patch in self.manifest["patches"]:
            if not patch.get("enabled"):
                continue
            for archive_name in patch.get("chain", []):
                match = EDGE_RE.fullmatch(archive_name)
                self.assertIsNotNone(match, archive_name)
                source, target = match.groups()
                graph.setdefault(source, set()).add(target)

        queue = deque(["1.4.90"])
        reached = {"1.4.90"}
        while queue:
            for target in graph.get(queue.popleft(), set()):
                if target not in reached:
                    reached.add(target)
                    queue.append(target)
        self.assertIn("1.4.106", reached)

    def test_archive_has_exact_deterministic_payload_set(self) -> None:
        self.assertIsNone(self.bad_member)
        self.assertEqual(
            [
                "production/upload/49/a073fdd109e00ac9daf801113cb5e19f64a8cf",
                "production/upload/d6/a23f83f176b05f715a8504b8fc0fc1ffaff068",
                "production/upload/8d/d127a4e129d8c80dd3711704191738812f9181",
            ],
            self.members,
        )
        self.assertEqual(list(builder.ARCHIVE_MEMBERS), self.members)
        self.assertEqual(
            [builder.ZIP_TIMESTAMP] * 3,
            [info.date_time for info in self.infos],
        )
        self.assertEqual(
            [zipfile.ZIP_DEFLATED] * 3,
            [info.compress_type for info in self.infos],
        )
        self.assertEqual([0] * 3, [info.flag_bits for info in self.infos])
        self.assertEqual([b""] * 3, [info.extra for info in self.infos])
        self.assertEqual(b"", self.archive_comment)
        for info in self.infos:
            payload = self.member_bytes[info.filename]
            self.assertEqual(len(payload), info.file_size)
            self.assertEqual(zlib.crc32(payload) & 0xFFFFFFFF, info.CRC)
        self.assertEqual(115_915, len(self.archive_bytes))
        self.assertEqual(ARCHIVE_SHA256, builder.sha256(self.archive_bytes))

    def test_payloads_match_frozen_v1_contract_and_official_baselines(self) -> None:
        equipment_bytes = self.member_bytes[builder.EQUIPMENT_MEMBER]
        soul_bytes = self.member_bytes[builder.SOUL_MEMBER]
        wab_bytes = self.member_bytes[builder.WAB_MEMBER]

        official_soul = builder.parse_table(
            builder.strip_custom_soul_rows(soul_bytes), builder.SOUL_LOGICAL
        )
        self.assertEqual(
            builder.SOUL_CANONICAL_BASELINE_SHA256,
            builder.canonical_node_sha256(official_soul),
        )
        self.assertEqual(builder.WAB_BASELINE_SIZE, len(wab_bytes))
        self.assertEqual(builder.WAB_BASELINE_SHA256, builder.sha256(wab_bytes))

        bridge_bytes = builder.checked_bridge(builder.BRIDGE_ARCHIVE)
        tampered_soul = dict(official_soul)
        first_soul_id = next(iter(tampered_soul))
        tampered_soul[first_soul_id] = str(tampered_soul[first_soul_id]) + ",tamper"
        with self.assertRaisesRegex(ValueError, "canonical content"):
            builder.build_payloads_from_soul_table(
                bridge_bytes,
                tampered_soul,
                wab_bytes,
            )
        expected_payloads = builder.build_payloads_from_soul_table(
            bridge_bytes,
            official_soul,
            wab_bytes,
        )
        for rebuilt, archived, logical in (
            (expected_payloads[0], equipment_bytes, builder.EQUIPMENT_LOGICAL),
            (expected_payloads[1], soul_bytes, builder.SOUL_LOGICAL),
        ):
            expected = builder.parse_table(archived, logical)
            actual = builder.parse_table(rebuilt, logical)
            self.assertEqual(list(expected), list(actual))
            self.assertEqual(
                builder.key_sequence_sha256(expected),
                builder.key_sequence_sha256(actual),
            )
            self.assertEqual(
                builder.canonical_node_sha256(expected),
                builder.canonical_node_sha256(actual),
            )
        self.assertEqual(expected_payloads[2], wab_bytes)

        equipment = builder.parse_table(equipment_bytes, builder.EQUIPMENT_LOGICAL)
        souls = builder.parse_table(soul_bytes, builder.SOUL_LOGICAL)
        for custom_id in builder.V1_CONTRACT.custom_ids:
            self.assertEqual(
                builder.V1_CONTRACT.equipment_rows[custom_id],
                equipment[custom_id],
            )
            self.assertEqual(
                builder.V1_CONTRACT.ability_soul_rows[custom_id],
                souls[custom_id],
            )

    def test_v1_contract_loader_rejects_corruption(self) -> None:
        valid = json.loads(
            builder.RELEASE_CONTRACT_PATH.read_text(encoding="utf-8")
        )
        mutations = {
            "schema": (
                "schema_version",
                lambda doc: doc.__setitem__("schema_version", 2),
            ),
            "schema_bool": (
                "schema_version",
                lambda doc: doc.__setitem__("schema_version", True),
            ),
            "schema_float": (
                "schema_version",
                lambda doc: doc.__setitem__("schema_version", 1.0),
            ),
            "archive_sha": (
                "archive_sha256",
                lambda doc: doc["published"].__setitem__(
                    "archive_sha256", "0" * 64
                ),
            ),
            "missing_equipment": (
                "payload_rows.equipment",
                lambda doc: doc["payload_rows"]["equipment"].pop("8000101"),
            ),
            "reordered_soul": (
                "payload_rows.ability_soul",
                lambda doc: doc["payload_rows"].__setitem__(
                    "ability_soul",
                    dict(reversed(doc["payload_rows"]["ability_soul"].items())),
                ),
            ),
            "empty_leaf": (
                "payload_rows.equipment.8000101",
                lambda doc: doc["payload_rows"]["equipment"].__setitem__(
                    "8000101", ""
                ),
            ),
            "bad_digest": (
                "equipment_canonical_sha256",
                lambda doc: doc["published"].__setitem__(
                    "equipment_canonical_sha256", "ABC"
                ),
            ),
        }

        for name, (expected_field, mutate) in mutations.items():
            with self.subTest(name=name):
                document = copy.deepcopy(valid)
                mutate(document)
                with tempfile.TemporaryDirectory() as temp:
                    path = Path(temp) / "contract.json"
                    path.write_text(
                        json.dumps(document, ensure_ascii=False),
                        encoding="utf-8",
                    )
                    with self.assertRaisesRegex(
                        ValueError, re.escape(expected_field)
                    ):
                        builder.load_v1_contract(path)

    def test_v1_contract_loader_rejects_duplicate_json_keys(self) -> None:
        raw = builder.RELEASE_CONTRACT_PATH.read_text(encoding="utf-8")
        document = json.loads(raw)
        archive_line = (
            f'    "archive_sha256": "{builder.ARCHIVE_SHA256}",'
        )
        equipment_leaf = json.dumps(
            document["payload_rows"]["equipment"]["8000101"],
            ensure_ascii=False,
        )
        equipment_line = f'      "8000101": {equipment_leaf},'
        corruptions = {
            "duplicate_schema_version": (
                "schema_version",
                raw.replace(
                    '  "schema_version": 1,',
                    '  "schema_version": 1,\n  "schema_version": 1,',
                    1,
                ),
            ),
            "duplicate_published_metadata": (
                "archive_sha256",
                raw.replace(archive_line, f"{archive_line}\n{archive_line}", 1),
            ),
            "duplicate_payload_row": (
                "8000101",
                raw.replace(
                    equipment_line,
                    f"{equipment_line}\n{equipment_line}",
                    1,
                ),
            ),
        }

        for name, (expected_field, content) in corruptions.items():
            with self.subTest(name=name):
                self.assertNotEqual(raw, content)
                with tempfile.TemporaryDirectory() as temp:
                    path = Path(temp) / "contract.json"
                    path.write_text(content, encoding="utf-8")
                    with self.assertRaisesRegex(
                        ValueError, re.escape(expected_field)
                    ):
                        builder.load_v1_contract(path)

    def test_current_resonance_generator_matches_declared_semantics(self) -> None:
        self.assertTrue(CURRENT_STATUS.is_file(), CURRENT_STATUS)
        status = json.loads(CURRENT_STATUS.read_text(encoding="utf-8"))
        self.assertEqual(1, status["schema_version"])
        self.assertEqual("abyss-weapons-v3.6-thunder-light-rework", status["id"])
        self.assertEqual("pending", status["status"])
        self.assertEqual("mod-tools/wf_rogue_rewards.py", status["source"])
        self.assertEqual(
            "539c23b51f00231cf83ea96239ec5df7705e8c08",
            status["source_revision"],
        )
        self.assertIsNone(status["artifact"])

        bridge, official_soul, _ = self.historical_inputs()
        tables = rewards.MasterTables(
            items=builder.parse_table(
                builder.read_bridge_member(bridge, rewards.ITEM_T),
                rewards.ITEM_T,
            ),
            equipment=builder.parse_table(
                builder.read_bridge_member(bridge, rewards.EQUIP_T),
                rewards.EQUIP_T,
            ),
            equipment_status=builder.parse_table(
                builder.read_bridge_member(bridge, rewards.EQUIP_STATUS_T),
                rewards.EQUIP_STATUS_T,
            ),
            ability_soul=official_soul,
            rush_event=builder.parse_table(
                builder.read_bridge_member(bridge, rewards.RUSH_EVENT_T),
                rewards.RUSH_EVENT_T,
            ),
        )
        changes = rewards.build_master_changes(tables)
        semantic_node = {
            "equipment": {
                key: changes.equipment[key]
                for key in builder.V1_CONTRACT.custom_ids
            },
            "equipment_status": {
                key: changes.equipment_status[key]
                for key in builder.V1_CONTRACT.custom_ids
            },
            "ability_soul": {
                key: changes.ability_soul[key]
                for key in builder.V1_CONTRACT.custom_ids
            },
        }
        self.assertEqual(
            status["semantic_sha256"],
            builder.canonical_node_sha256(semantic_node),
        )

    def test_historical_rebuild_ignores_current_weapon_inventory(self) -> None:
        bridge, official_soul, wab = self.historical_inputs()
        original = rewards.WEAPONS
        try:
            rewards.WEAPONS = ()
            rebuilt = builder.build_payloads_from_soul_table(
                bridge, official_soul, wab
            )
        finally:
            rewards.WEAPONS = original

        for payload, member, logical in (
            (rebuilt[0], builder.EQUIPMENT_MEMBER, builder.EQUIPMENT_LOGICAL),
            (rebuilt[1], builder.SOUL_MEMBER, builder.SOUL_LOGICAL),
        ):
            expected = builder.parse_table(self.member_bytes[member], logical)
            actual = builder.parse_table(payload, logical)
            self.assertEqual(list(expected), list(actual))
            self.assertEqual(
                builder.canonical_node_sha256(expected),
                builder.canonical_node_sha256(actual),
            )

    def test_historical_builder_rebuilds_without_current_generator_module(self) -> None:
        script = f"""
import sys
import zipfile
from pathlib import Path
root = Path({str(ROOT)!r})
sys.path.insert(0, str(root / 'mod-tools'))
sys.modules['wf_rogue_rewards'] = None
import build_abyss_weapon_balance_patch as historical
with zipfile.ZipFile(historical.OUTPUT_ARCHIVE) as archive:
    soul_bytes = archive.read(historical.SOUL_MEMBER)
    wab_bytes = archive.read(historical.WAB_MEMBER)
official = historical.parse_table(
    historical.strip_custom_soul_rows(soul_bytes), historical.SOUL_LOGICAL
)
payloads = historical.build_payloads_from_soul_table(
    historical.checked_bridge(historical.BRIDGE_ARCHIVE), official, wab_bytes
)
assert len(payloads) == 3
"""
        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)

    def test_historical_rebuild_does_not_read_committed_archive(self) -> None:
        bridge, official_soul, wab = self.historical_inputs()
        original = builder.OUTPUT_ARCHIVE
        builder.OUTPUT_ARCHIVE = ROOT / "missing-historical-archive.zip"
        try:
            rebuilt = builder.build_payloads_from_soul_table(
                bridge, official_soul, wab
            )
        finally:
            builder.OUTPUT_ARCHIVE = original

        rebuilt_equipment = builder.parse_table(
            rebuilt[0], builder.EQUIPMENT_LOGICAL
        )
        archived_equipment = builder.parse_table(
            self.member_bytes[builder.EQUIPMENT_MEMBER], builder.EQUIPMENT_LOGICAL
        )
        self.assertEqual(
            builder.canonical_node_sha256(archived_equipment),
            builder.canonical_node_sha256(rebuilt_equipment),
        )

    def test_equipment_preserves_every_noncustom_bridge_row_and_order(self) -> None:
        bridge = builder.checked_bridge(builder.BRIDGE_ARCHIVE)
        bridge_equipment = builder.parse_table(
            builder.read_bridge_member(bridge, builder.EQUIPMENT_LOGICAL),
            builder.EQUIPMENT_LOGICAL,
        )
        final_equipment = builder.parse_table(
            self.member_bytes[builder.EQUIPMENT_MEMBER], builder.EQUIPMENT_LOGICAL
        )
        custom_ids = set(builder.V1_CONTRACT.custom_ids)
        bridge_noncustom = [
            (key, value)
            for key, value in bridge_equipment.items()
            if key not in custom_ids
        ]
        final_noncustom = [
            (key, value)
            for key, value in final_equipment.items()
            if key not in custom_ids
        ]
        self.assertEqual(bridge_noncustom, final_noncustom)

    def test_rebuild_is_semantically_stable_without_live_store(self) -> None:
        payloads = (
            self.member_bytes[builder.EQUIPMENT_MEMBER],
            self.member_bytes[builder.SOUL_MEMBER],
            self.member_bytes[builder.WAB_MEMBER],
        )
        first = builder.build_archive_bytes(payloads)
        second = builder.build_archive_bytes(payloads)
        self.assertEqual(first, second)
        with zipfile.ZipFile(BytesIO(first)) as rebuilt:
            self.assertEqual(self.members, rebuilt.namelist())
            for member in self.members:
                actual = self.member_bytes[member]
                candidate = rebuilt.read(member)
                if member == builder.WAB_MEMBER:
                    self.assertEqual(actual, candidate)
                else:
                    self.assertEqual(
                        builder.parse_table(actual, member),
                        builder.parse_table(candidate, member),
                    )


if __name__ == "__main__":
    unittest.main()
