"""Independent adversarial verification for wf-release-v1 archives."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import stat
import struct
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import zlib

from tests.release_v1_fixtures import make_patch_overlay, make_sealed_character_workspace
from tests.release_v1_schema_support import requirements_wire
from wf_release_v1.canonical import canonical_json_bytes, load_json_strict_bytes
from wf_release_v1.errors import ReleaseError
from wf_release_v1.schema import compute_release_id, parse_requirements


ROOT = "wf-release-v1/"
RELEASE = ROOT + "release-manifest.json"
REQUIRES = ROOT + "requires.json"
OWNERSHIP = ROOT + "ownership.json"
FIXED_MODE = stat.S_IFREG | 0o644


def _classic_store(members: list[tuple[str, bytes]], *, comment: bytes = b"") -> bytes:
    locals_: list[bytes] = []
    centrals: list[bytes] = []
    offset = 0
    for name, payload in members:
        encoded = name.encode("utf-8")
        checksum = zlib.crc32(payload) & 0xFFFFFFFF
        local = struct.pack(
            "<IHHHHHIIIHH", 0x04034B50, 20, 0x800, 0, 0, 33,
            checksum, len(payload), len(payload), len(encoded), 0,
        ) + encoded + payload
        central = struct.pack(
            "<IHHHHHHIIIHHHHHII", 0x02014B50, 0x314, 20, 0x800,
            0, 0, 33, checksum, len(payload), len(payload), len(encoded),
            0, 0, 0, 0, FIXED_MODE << 16, offset,
        ) + encoded
        locals_.append(local)
        centrals.append(central)
        offset += len(local)
    local_raw = b"".join(locals_)
    central_raw = b"".join(centrals)
    return local_raw + central_raw + struct.pack(
        "<IHHHHIIH", 0x06054B50, 0, 0, len(members), len(members),
        len(central_raw), len(local_raw), len(comment),
    ) + comment


def _members(raw: bytes) -> list[tuple[str, bytes]]:
    with zipfile.ZipFile(__import__("io").BytesIO(raw)) as bundle:
        return [(item.filename, bundle.read(item)) for item in bundle.infolist()]


def _replace_release(
    members: list[tuple[str, bytes]],
    mutate,
) -> list[tuple[str, bytes]]:
    release = load_json_strict_bytes(dict(members)[RELEASE], label=RELEASE)
    if not isinstance(release, dict):
        raise AssertionError("release manifest fixture is not an object")
    mutate(release)
    body = copy.deepcopy(release)
    body.pop("releaseId", None)
    release["releaseId"] = compute_release_id(body)
    replacement = canonical_json_bytes(release)
    return [(name, replacement if name == RELEASE else raw) for name, raw in members]


def _replace_release_unchecked(
    members: list[tuple[str, bytes]], mutate
) -> list[tuple[str, bytes]]:
    release = json.loads(dict(members)[RELEASE])
    mutate(release)
    replacement = canonical_json_bytes(release)
    return [(name, replacement if name == RELEASE else raw) for name, raw in members]


def _replace_payload(
    members: list[tuple[str, bytes]], member_name: str, payload: bytes
) -> list[tuple[str, bytes]]:
    changed = [(name, payload if name == member_name else raw) for name, raw in members]
    def bind(release: dict[str, object]) -> None:
        for item in release["files"]:  # type: ignore[index]
            if item["path"] == member_name.removeprefix(ROOT):
                item["size"] = len(payload)
                item["sha256"] = hashlib.sha256(payload).hexdigest()
    return _replace_release(changed, bind)


def _central_offsets(raw: bytes) -> tuple[int, list[int]]:
    eocd = len(raw) - 22
    central_at = struct.unpack_from("<I", raw, eocd + 16)[0]
    count = struct.unpack_from("<H", raw, eocd + 10)[0]
    offsets: list[int] = []
    cursor = central_at
    for _ in range(count):
        offsets.append(cursor)
        name_len, extra_len, comment_len = struct.unpack_from("<HHH", raw, cursor + 28)
        cursor += 46 + name_len + extra_len + comment_len
    return central_at, offsets


class VerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from wf_release_v1.producer import BuildRequest, build_character_release

        cls._temporary = tempfile.TemporaryDirectory()
        root = Path(cls._temporary.name)
        workspace = make_sealed_character_workspace(root / "workspace")
        overlay = make_patch_overlay(
            root / "source" / "worldflipper-overlay-1.4.54-to-1.4.55.zip",
            from_version="1.4.54", target_version="1.4.55",
        )
        output = root / "valid.zip"
        build_character_release(BuildRequest(
            name="seris-dragon-king", version="1.0.0", workspace=workspace,
            overlay_archives=(overlay,), output=output,
            requirements=parse_requirements(requirements_wire()),
        ))
        cls.valid_raw = output.read_bytes()
        overlay_two = make_patch_overlay(
            root / "source" / "worldflipper-overlay-1.4.55-to-1.4.56.zip",
            from_version="1.4.55", target_version="1.4.56",
        )
        chain_output = root / "valid-chain.zip"
        build_character_release(BuildRequest(
            name="seris-dragon-king", version="1.0.1", workspace=workspace,
            overlay_archives=(overlay, overlay_two), output=chain_output,
            requirements=parse_requirements(requirements_wire()),
        ))
        cls.chain_raw = chain_output.read_bytes()

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temporary.cleanup()

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def _verify(self, raw: bytes | None = None):
        from wf_release_v1.verifier import verify_release

        path = self.root / "candidate.zip"
        path.write_bytes(self.valid_raw if raw is None else raw)
        return verify_release(path)

    def _rejects(self, raw: bytes, code: str = "WFREL_ARCHIVE_INVALID") -> None:
        with self.assertRaises(ReleaseError) as raised:
            self._verify(raw)
        self.assertEqual(code, raised.exception.code)
        self.assertNotIn(str(self.root), str(raised.exception.details))

    def test_valid_archive_reports_only_verified_facts(self) -> None:
        report = self._verify()
        self.assertTrue(report.release_id.startswith("sha256:"))
        self.assertEqual(("content",), report.components)
        self.assertEqual(1, report.file_count)
        payload = next(raw for name, raw in _members(self.valid_raw) if "/content/" in name)
        self.assertEqual(len(payload), report.payload_bytes)

    def test_asset_before_evidence_and_exclusive_claims_are_exactly_cross_bound(self) -> None:
        """A recomputed Release cannot drop or invent shared-asset ownership."""
        base = _members(self.valid_raw)

        def rebuilt(*, replacements: list[dict[str, object]] | None,
                    asset_claims: list[str], omit_path: bool = False) -> bytes:
            by_name = dict(base)
            ownership = json.loads(by_name[OWNERSHIP])
            ownership["records"] = sorted(
                [
                    item for item in ownership["records"]
                    if not item.startswith("asset:")
                ] + asset_claims,
                key=lambda item: item.encode("utf-8"),
            )
            if replacements is not None and not omit_path:
                ownership["paths"] = sorted(
                    {
                        *ownership["paths"],
                        *(item["logicalPath"] for item in replacements),
                    },
                    key=lambda item: item.encode("utf-8"),
                )
            if omit_path:
                ownership["paths"] = [
                    item for item in ownership["paths"]
                    if item != "item/sprite_sheet.png"
                ]
            ownership_raw = canonical_json_bytes(ownership)
            release = json.loads(by_name[RELEASE])
            if replacements is not None:
                release["sourceEvidence"] = {
                    "acceptedAssetReplacements": replacements,
                    "kind": "character-workspace-v2",
                    "workspaceInputSha256": "a" * 64,
                }
            release["metadataSha256"]["ownership"] = hashlib.sha256(
                ownership_raw
            ).hexdigest()
            body = copy.deepcopy(release)
            body.pop("releaseId")
            release["releaseId"] = compute_release_id(body)
            release_raw = canonical_json_bytes(release)
            return _classic_store([
                (
                    name,
                    release_raw if name == RELEASE else
                    ownership_raw if name == OWNERSHIP else raw,
                )
                for name, raw in base
            ])

        replacement = {
            "beforeSha256": "b" * 64,
            "beforeSize": 12,
            "logicalPath": "item/sprite_sheet.png",
            "root": "common",
        }
        cases = (
            rebuilt(replacements=[replacement], asset_claims=[]),
            rebuilt(
                replacements=[replacement],
                asset_claims=[
                    "asset:common/item/extra.png",
                    "asset:common/item/sprite_sheet.png",
                ],
            ),
            rebuilt(
                replacements=[replacement],
                asset_claims=["asset:common/item/sprite_sheet.png"],
                omit_path=True,
            ),
        )
        for raw in cases:
            with self.subTest(case=hashlib.sha256(raw).hexdigest()):
                self._rejects(raw, "WFREL_OWNERSHIP_INVALID")

        valid_v2 = rebuilt(
            replacements=[replacement],
            asset_claims=["asset:common/item/sprite_sheet.png"],
        )
        self.assertTrue(self._verify(valid_v2).release_id.startswith("sha256:"))

        legacy_asset_record = rebuilt(
            replacements=None,
            asset_claims=["asset:legacy-record-kept-for-v1"],
        )
        self.assertTrue(self._verify(legacy_asset_record).release_id.startswith("sha256:"))

    def test_valid_payload_is_streamed_and_hashed_once(self) -> None:
        import wf_release_v1.verifier as verifier

        original = verifier.copy_hash_member
        calls: list[str] = []
        def counted(stream, member, destination=None):
            calls.append(member.name)
            return original(stream, member, destination)
        with patch.object(verifier, "copy_hash_member", side_effect=counted):
            self._verify()
        self.assertEqual(1, len(calls))
        self.assertIn("/content/", calls[0])

    def test_valid_archive_does_not_call_producer_or_release_archive_helpers(self) -> None:
        import wf_release_v1.producer as producer
        import wf_release_v1.patch_overlay_source as patch_overlay_source
        import wf_release_v1.release_archive as release_archive
        import wf_release_v1.verifier as verifier
        import wf_release_v1.verifier_overlay as verifier_overlay
        import wf_release_v1.verifier_zip as verifier_zip

        exploding = RuntimeError("producer state must be irrelevant")
        with patch.object(producer, "build_character_release", side_effect=exploding), patch.object(
            release_archive, "readback_archive", side_effect=exploding
        ), patch.object(patch_overlay_source, "inspect_patch_overlay_chain", side_effect=exploding):
            self._verify()
        sources = "\n".join(
            Path(module.__file__).read_text(encoding="utf-8")
            for module in (verifier, verifier_overlay, verifier_zip)
        )
        self.assertNotIn("from .producer", sources)
        self.assertNotIn("from .release_archive", sources)
        self.assertNotIn("from .patch_overlay_source", sources)

    def test_rejects_wrong_root_and_unknown_top_level(self) -> None:
        self._rejects(self.valid_raw.replace(b"wf-release-v1/", b"xf-release-v1/"))
        self._rejects(self.valid_raw.replace(b"/content/", b"/garbage/"))

    def test_rejects_missing_extra_or_duplicate_members(self) -> None:
        members = _members(self.valid_raw)
        self._rejects(_classic_store([item for item in members if item[0] != REQUIRES]))
        self._rejects(_classic_store(members[:-1] + [(ROOT + "extra.bin", b"x")] + members[-1:]))
        self._rejects(_classic_store(members[:-1] + [members[0]] + members[-1:]))

    def test_rejects_directory_compression_time_permission_and_comment(self) -> None:
        members = _members(self.valid_raw)
        self._rejects(_classic_store(members[:-1] + [(ROOT + "content/", b"")] + members[-1:]))
        for local_offset, central_offset, replacement in (
            (8, 10, 8),       # compression method
            (10, 12, 2),      # DOS time
        ):
            raw = bytearray(self.valid_raw)
            _, centrals = _central_offsets(raw)
            struct.pack_into("<H", raw, local_offset, replacement)
            struct.pack_into("<H", raw, centrals[0] + central_offset, replacement)
            self._rejects(bytes(raw))
        raw = bytearray(self.valid_raw)
        _, centrals = _central_offsets(raw)
        struct.pack_into("<I", raw, centrals[0] + 38, 0o600 << 16)
        self._rejects(bytes(raw))
        self._rejects(_classic_store(members, comment=b"comment"))

    def test_rejects_local_central_name_disagreement_crc_and_truncation(self) -> None:
        raw = bytearray(self.valid_raw)
        _, centrals = _central_offsets(raw)
        name_at = centrals[0] + 46
        raw[name_at] = ord("x")
        self._rejects(bytes(raw))

        raw = bytearray(self.valid_raw)
        _, centrals = _central_offsets(raw)
        struct.pack_into("<I", raw, 14, 0)
        struct.pack_into("<I", raw, centrals[0] + 16, 0)
        self._rejects(bytes(raw))
        self._rejects(self.valid_raw[:-1])

    def test_rejects_zip64_gap_extra_and_noncanonical_order(self) -> None:
        raw = bytearray(self.valid_raw)
        eocd = len(raw) - 22
        struct.pack_into("<H", raw, eocd + 10, 0xFFFF)
        self._rejects(bytes(raw))

        central_at, _ = _central_offsets(self.valid_raw)
        gap = b"hidden-gap"
        raw = bytearray(self.valid_raw[:central_at] + gap + self.valid_raw[central_at:])
        eocd = len(raw) - 22
        struct.pack_into("<I", raw, eocd + 16, central_at + len(gap))
        self._rejects(bytes(raw))

        raw = bytearray(self.valid_raw)
        _, centrals = _central_offsets(raw)
        struct.pack_into("<H", raw, centrals[0] + 30, 1)
        self._rejects(bytes(raw))

        members = _members(self.valid_raw)
        self._rejects(_classic_store([members[-1], *members[:-1]]))

    def test_rejects_prefix_trailing_multidisk_flags_and_header_variants(self) -> None:
        self._rejects(b"prefix" + self.valid_raw)
        self._rejects(self.valid_raw + b"trailing")
        for eocd_offset, value in ((4, 1), (6, 1), (8, 1)):
            raw = bytearray(self.valid_raw)
            struct.pack_into("<H", raw, len(raw) - 22 + eocd_offset, value)
            self._rejects(bytes(raw))
        for local_offset, central_offset, fmt, value in (
            (6, 8, "<H", 0x808),
            (4, 6, "<H", 45),
            (0, 4, "<H", 0x214),
            (0, 36, "<H", 1),
            (0, 38, "<I", 0),
        ):
            raw = bytearray(self.valid_raw)
            _, centrals = _central_offsets(raw)
            if local_offset:
                struct.pack_into(fmt, raw, local_offset, value)
            struct.pack_into(fmt, raw, centrals[0] + central_offset, value)
            self._rejects(bytes(raw))

    def test_rejects_nonportable_raw_member_names_and_casefold_collisions(self) -> None:
        members = _members(self.valid_raw)
        payload_name, payload = members[0]
        bad_relatives = (
            "content\\bad.zip", "content/bad\x00.zip", "content/C:.zip",
            "content/../bad.zip", "content//bad.zip", "/absolute.zip",
            "content/e\u0301.zip", "content/bad.zip ",
            "content/CON.zip",
        )
        for relative in bad_relatives:
            changed = [(ROOT + relative, payload) if name == payload_name else (name, raw) for name, raw in members]
            self._rejects(_classic_store(changed))
        relative = payload_name.removeprefix(ROOT)
        directory, basename = relative.rsplit("/", 1)
        changed = members[:-1] + [(ROOT + directory + "/" + basename.upper(), payload)] + members[-1:]
        self._rejects(_classic_store(changed))

    def test_rejects_windows_superscript_and_console_device_payload_names(self) -> None:
        members = _members(self.valid_raw)
        original_name, payload = members[0]
        for basename in ("COM¹.zip", "com².ZIP", "COM³.data.zip", "CONIN$.zip", "conout$.ZIP"):
            with self.subTest(basename=basename):
                replacement_name = ROOT + "content/" + basename
                changed = [
                    (replacement_name, payload) if name == original_name else (name, raw)
                    for name, raw in members
                ]
                def bind(value: dict[str, object]) -> None:
                    item = value["files"][0]  # type: ignore[index]
                    item["path"] = "content/" + basename
                    item["size"] = len(payload)
                    item["sha256"] = hashlib.sha256(payload).hexdigest()
                rebound = _replace_release(changed, bind)
                rebound = sorted(rebound[:-1], key=lambda item: item[0].encode("utf-8")) + rebound[-1:]
                self._rejects(_classic_store(rebound))

    def test_accepts_normal_nfc_unicode_payload_name(self) -> None:
        members = _members(self.valid_raw)
        original_name, payload = members[0]
        replacement_name = ROOT + "content/角色-overlay.zip"
        changed = [
            (replacement_name, payload) if name == original_name else (name, raw)
            for name, raw in members
        ]
        def bind(value: dict[str, object]) -> None:
            item = value["files"][0]  # type: ignore[index]
            item["path"] = "content/角色-overlay.zip"
            item["size"] = len(payload)
            item["sha256"] = hashlib.sha256(payload).hexdigest()
        rebound = _replace_release(changed, bind)
        rebound = sorted(rebound[:-1], key=lambda item: item[0].encode("utf-8")) + rebound[-1:]
        report = self._verify(_classic_store(rebound))
        self.assertEqual(("content",), report.components)

    def test_enforces_raw_and_metadata_limits_without_large_allocations(self) -> None:
        import wf_release_v1.verifier as verifier
        import wf_release_v1.verifier_zip as verifier_zip

        with patch.object(verifier_zip, "MAX_MEMBERS", 1):
            self._rejects(self.valid_raw)
        with patch.object(verifier_zip, "MAX_MEMBER_BYTES", 1):
            self._rejects(self.valid_raw)
        with patch.object(verifier_zip, "MAX_TOTAL_BYTES", 1):
            self._rejects(self.valid_raw)
        with patch.object(verifier_zip, "MAX_CENTRAL_BYTES", 1):
            self._rejects(self.valid_raw)
        with patch.object(verifier, "_MAX_METADATA_BYTES", 1):
            self._rejects(self.valid_raw, "WFREL_ARCHIVE_LIMIT")

    def test_rejects_missing_extra_size_or_hash_mismatched_payloads(self) -> None:
        members = _members(self.valid_raw)
        payload_name = members[0][0]
        self._rejects(_classic_store([item for item in members if item[0] != payload_name]))
        self._rejects(_classic_store(members[:-1] + [(ROOT + "content/extra.zip", b"x")] + members[-1:]))
        self._rejects(_classic_store(_replace_release(members, lambda value: value["files"][0].__setitem__("size", 1))), "WFREL_HASH_MISMATCH")  # type: ignore[index]
        self._rejects(_classic_store(_replace_release(members, lambda value: value["files"][0].__setitem__("sha256", "0" * 64))), "WFREL_HASH_MISMATCH")  # type: ignore[index]

    def test_rejects_noncanonical_or_unbound_metadata_and_release_id(self) -> None:
        members = _members(self.valid_raw)
        requires = json.loads(dict(members)[REQUIRES])
        pretty = json.dumps(requires, indent=2).encode("utf-8") + b"\n"
        changed = [(name, pretty if name == REQUIRES else raw) for name, raw in members]
        self._rejects(_classic_store(changed))

        changed = _replace_release(members, lambda value: value["metadataSha256"].__setitem__("requires", "0" * 64))  # type: ignore[index]
        self._rejects(_classic_store(changed), "WFREL_HASH_MISMATCH")

        release = json.loads(dict(members)[RELEASE])
        release["releaseId"] = "sha256:" + "0" * 64
        changed = [(name, canonical_json_bytes(release) if name == RELEASE else raw) for name, raw in members]
        self._rejects(_classic_store(changed), "WFREL_HASH_MISMATCH")

    def test_rejects_empty_unknown_and_unimplemented_components(self) -> None:
        members = _members(self.valid_raw)
        changed = _replace_release_unchecked(members, lambda value: value["components"].append({"kind": "server", "root": "server"}))  # type: ignore[index]
        self._rejects(_classic_store(changed), "WFREL_SCHEMA_INVALID")

        changed = _replace_release_unchecked(members, lambda value: value["components"].__setitem__(0, {"kind": "unknown", "root": "unknown"}))  # type: ignore[index]
        self._rejects(_classic_store(changed), "WFREL_SCHEMA_INVALID")

        payload = members[0][1]
        server_name = ROOT + "server/server-manifest.json"
        changed = [(server_name, payload) if name == members[0][0] else (name, raw) for name, raw in members]
        def server_manifest(value: dict[str, object]) -> None:
            value["components"] = [{"kind": "server", "root": "server"}]
            value["files"] = [{"path": "server/server-manifest.json", "size": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}]
        server_members = _replace_release(changed, server_manifest)
        server_members = sorted(server_members[:-1], key=lambda item: item[0].encode("utf-8")) + server_members[-1:]
        self._rejects(_classic_store(server_members), "WFREL_COMPONENT_UNSUPPORTED")

    def test_rejects_invalid_embedded_overlay_and_target_mismatch(self) -> None:
        members = _members(self.valid_raw)
        payload_name, payload = members[0]
        with zipfile.ZipFile(__import__("io").BytesIO(payload)) as bundle:
            overlay_members = [(item.filename, bundle.read(item)) for item in bundle.infolist()]
        manifest = json.loads(dict(overlay_members)["patch-manifest.json"])
        manifest["schema"] = 2
        bad_overlay = _classic_store([
            (name, canonical_json_bytes(manifest) if name == "patch-manifest.json" else raw)
            for name, raw in overlay_members
        ])
        self._rejects(_classic_store(_replace_payload(members, payload_name, bad_overlay)), "WFREL_OVERLAY_INVALID")

        changed = _replace_release(members, lambda value: value["expectedState"].__setitem__("cdnTargetVersion", "1.4.99"))  # type: ignore[index]
        self._rejects(_classic_store(changed), "WFREL_COMPONENT_INVALID")



if __name__ == "__main__":
    unittest.main()
