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


class VerifierOverlayTests(unittest.TestCase):
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

    def test_independently_rejects_unsupported_overlay_requirement(self) -> None:
        members = _members(self.valid_raw)
        requirements = json.loads(dict(members)[REQUIRES])
        requirements["patchOverlaySchema"] = 2
        replacement = canonical_json_bytes(requirements)
        changed = [
            (name, replacement if name == REQUIRES else raw)
            for name, raw in members
        ]
        changed = _replace_release(
            changed,
            lambda value: value["metadataSha256"].__setitem__(  # type: ignore[index]
                "requires", hashlib.sha256(replacement).hexdigest()
            ),
        )

        self._rejects(_classic_store(changed), "WFREL_COMPONENT_INVALID")

    def test_independently_rejects_overlay_member_order_requirements_and_inner_crc(self) -> None:
        members = _members(self.valid_raw)
        payload_name, payload = members[0]
        overlay_members = _members(payload)

        reordered = [overlay_members[-1], *overlay_members[:-1]]
        self._rejects(
            _classic_store(_replace_payload(members, payload_name, _classic_store(reordered))),
            "WFREL_OVERLAY_INVALID",
        )

        scalar_requires = [
            (name, b"[]\n" if name == "requires.json" else raw)
            for name, raw in overlay_members
        ]
        self._rejects(
            _classic_store(_replace_payload(members, payload_name, _classic_store(scalar_requires))),
            "WFREL_OVERLAY_INVALID",
        )

        manifest = json.loads(dict(overlay_members)["patch-manifest.json"])
        inner_name = manifest["archives"][0]["relativePath"]
        inner_raw = bytearray(dict(overlay_members)[inner_name])
        inner_raw[40] ^= 1
        manifest["archives"][0]["bytes"] = len(inner_raw)
        manifest["archives"][0]["sha256"] = hashlib.sha256(inner_raw).hexdigest()
        corrupt_inner = [
            (name, bytes(inner_raw) if name == inner_name else canonical_json_bytes(manifest) if name == "patch-manifest.json" else raw)
            for name, raw in overlay_members
        ]
        self._rejects(
            _classic_store(_replace_payload(members, payload_name, _classic_store(corrupt_inner))),
            "WFREL_OVERLAY_INVALID",
        )

    def test_independently_rejects_overlay_outer_set_crc_inner_path_and_layers(self) -> None:
        members = _members(self.valid_raw)
        payload_name, payload = members[0]
        overlay_members = _members(payload)
        variants: list[bytes] = []
        variants.append(_classic_store(overlay_members[:-1] + [("extra.bin", b"x")] + overlay_members[-1:]))
        variants.append(_classic_store(overlay_members[:-1] + [overlay_members[0]] + overlay_members[-1:]))
        variants.append(_classic_store([
            ("README.md\x00hidden", raw) if name == "README.md" else (name, raw)
            for name, raw in overlay_members
        ]))

        manifest = json.loads(dict(overlay_members)["patch-manifest.json"])
        inner_name = manifest["archives"][0]["relativePath"]
        unsafe_inner = _classic_store([("../escape", b"x")])
        manifest["archives"][0]["bytes"] = len(unsafe_inner)
        manifest["archives"][0]["sha256"] = hashlib.sha256(unsafe_inner).hexdigest()
        variants.append(_classic_store([
            (name, unsafe_inner if name == inner_name else canonical_json_bytes(manifest) if name == "patch-manifest.json" else raw)
            for name, raw in overlay_members
        ]))

        manifest = json.loads(dict(overlay_members)["patch-manifest.json"])
        removed = next(item for item in manifest["archives"] if item["layer"] == "android")
        manifest["archives"].remove(removed)
        variants.append(_classic_store([
            (name, canonical_json_bytes(manifest) if name == "patch-manifest.json" else raw)
            for name, raw in overlay_members if name != removed["relativePath"]
        ]))
        for bad_overlay in variants:
            self._rejects(
                _classic_store(_replace_payload(members, payload_name, bad_overlay)),
                "WFREL_OVERLAY_INVALID",
            )

        corrupt_readme = bytearray(_classic_store(overlay_members))
        corrupt_readme[30 + len("README.md")] ^= 1
        self._rejects(
            _classic_store(_replace_payload(members, payload_name, bytes(corrupt_readme))),
            "WFREL_OVERLAY_INVALID",
        )

    def test_enforces_overlay_central_and_ratio_limits_before_expansion(self) -> None:
        import wf_release_v1.verifier_overlay as verifier_overlay

        with patch.object(verifier_overlay, "_MAX_CENTRAL_BYTES", 1):
            self._rejects(self.valid_raw, "WFREL_OVERLAY_LIMIT")
        with patch.object(verifier_overlay, "_RATIO_THRESHOLD", 1), patch.object(
            verifier_overlay, "_MAX_COMPRESSION_RATIO", 1
        ):
            self._rejects(self.valid_raw, "WFREL_OVERLAY_LIMIT")

    def test_independently_verifies_overlay_chain_graph(self) -> None:
        path = self.root / "chain.zip"
        path.write_bytes(self.chain_raw)
        from wf_release_v1.verifier import verify_release

        report = verify_release(path)
        self.assertEqual(2, report.file_count)
        members = _members(self.chain_raw)
        payloads = [(name, raw) for name, raw in members if "/content/" in name]
        duplicate_second = [(name, payloads[0][1] if name == payloads[1][0] else raw) for name, raw in members]
        def rebind(value: dict[str, object]) -> None:
            for item in value["files"]:  # type: ignore[index]
                if item["path"] == payloads[1][0].removeprefix(ROOT):
                    item["size"] = len(payloads[0][1])
                    item["sha256"] = hashlib.sha256(payloads[0][1]).hexdigest()
        self._rejects(
            _classic_store(_replace_release(duplicate_second, rebind)),
            "WFREL_OVERLAY_GRAPH",
        )

    def test_rejects_strict_metadata_bom_duplicate_key_and_missing_final_lf(self) -> None:
        members = _members(self.valid_raw)
        mutations = (
            b"\xef\xbb\xbf" + dict(members)[REQUIRES],
            b'{"schemaVersion":1,"schemaVersion":1}\n',
            dict(members)[OWNERSHIP].rstrip(b"\n"),
        )
        for index, raw_metadata in enumerate(mutations):
            target = REQUIRES if index < 2 else OWNERSHIP
            changed = [(name, raw_metadata if name == target else raw) for name, raw in members]
            expected = "WFREL_ARCHIVE_INVALID" if index == 2 else (
                "WFREL_JSON_BOM" if index == 0 else "WFREL_JSON_DUPLICATE_KEY"
            )
            self._rejects(_classic_store(changed), expected)

    def test_rejects_reparse_input_and_cleans_private_component_temp(self) -> None:
        from wf_release_v1.verifier import verify_release
        import wf_release_v1.verifier as verifier

        source = self.root / "source.zip"
        source.write_bytes(self.valid_raw)
        link = self.root / "link.zip"
        try:
            link.symlink_to(source)
        except OSError:
            link = None
        if link is not None:
            with self.assertRaises(ReleaseError) as raised:
                verify_release(link)
            self.assertEqual("WFREL_ARCHIVE_INVALID", raised.exception.code)

        parent = self.root / "private-temp"
        parent.mkdir()
        original_temporary = tempfile.TemporaryDirectory
        def private_temp(*, prefix: str):
            return original_temporary(prefix=prefix, dir=parent)
        bad = _replace_release(
            _members(self.valid_raw),
            lambda value: value["expectedState"].__setitem__("cdnTargetVersion", "1.4.99"),  # type: ignore[index]
        )
        with patch.object(verifier.tempfile, "TemporaryDirectory", side_effect=private_temp):
            self._rejects(_classic_store(bad), "WFREL_COMPONENT_INVALID")
        self.assertEqual([], list(parent.iterdir()))

    def test_rejects_input_path_replacement_during_successful_verification(self) -> None:
        import wf_release_v1.verifier as verifier

        candidate = self.root / "candidate.zip"
        candidate.write_bytes(self.valid_raw)
        displaced = self.root / "displaced.zip"
        original = verifier.copy_hash_member
        replaced = False
        def replace_after_read(stream, member, destination=None):
            nonlocal replaced
            digest = original(stream, member, destination)
            if not replaced:
                candidate.replace(displaced)
                candidate.write_bytes(self.valid_raw)
                replaced = True
            return digest
        with patch.object(verifier, "copy_hash_member", side_effect=replace_after_read):
            with self.assertRaises(ReleaseError) as raised:
                verifier.verify_release(candidate)
        self.assertEqual("WFREL_ARCHIVE_INVALID", raised.exception.code)
        self.assertNotIn(str(self.root), str(raised.exception.details))

    def test_rejects_invalid_ownership_without_claiming_overlay_inner_mapping(self) -> None:
        members = _members(self.valid_raw)
        ownership = json.loads(dict(members)[OWNERSHIP])
        ownership["paths"] = []
        ownership_raw = canonical_json_bytes(ownership)
        changed = [(name, ownership_raw if name == OWNERSHIP else raw) for name, raw in members]
        def bind(value: dict[str, object]) -> None:
            value["metadataSha256"]["ownership"] = hashlib.sha256(ownership_raw).hexdigest()  # type: ignore[index]
        self._rejects(_classic_store(_replace_release(changed, bind)), "WFREL_SCHEMA_INVALID")

        ownership = json.loads(dict(members)[OWNERSHIP])
        ownership["paths"][0] = "assets/character/*"
        ownership_raw = canonical_json_bytes(ownership)
        changed = [(name, ownership_raw if name == OWNERSHIP else raw) for name, raw in members]
        def bind_wildcard(value: dict[str, object]) -> None:
            value["metadataSha256"]["ownership"] = hashlib.sha256(ownership_raw).hexdigest()  # type: ignore[index]
        self._rejects(
            _classic_store(_replace_release(changed, bind_wildcard)),
            "WFREL_OWNERSHIP_INVALID",
        )


if __name__ == "__main__":
    unittest.main()
