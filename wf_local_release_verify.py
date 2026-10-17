#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline CI verification and thin CLI for a local-live release receipt."""
from __future__ import annotations

import argparse
import io
import json
import struct
import sys
import zipfile
from pathlib import Path
from typing import Mapping, cast

import wf_local_release_receipt as model
import wf_local_server_contract as server_contract
import wf_release_inventory as inventory
from wf_release_inventory_contract import InventoryContract, InventoryError, MemberKey


def _expect_fields(value: object, fields: set[str], label: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != fields:
        raise model.ReceiptError(
            f"{label}: fields must be exactly {sorted(fields)}"
        )
    return value


def _verify_contracts(context: model.ReleaseContext, value: object) -> None:
    if not isinstance(value, list):
        raise model.ReceiptError("contracts must be an array")
    expected = [{
        "role": binding.role,
        "path": binding.relative_path,
        "contract_id": binding.contract_id,
        "size": len(binding.raw),
        "sha256": model._sha(binding.raw),
    } for binding in context.contract_bindings]
    if value != expected:
        raise model.ReceiptError("contract hash/id binding mismatch")


def _assert_dense_layout(
    blob: bytes, infos: list[zipfile.ZipInfo], path: str
) -> None:
    """Prove the archive is exactly its declared members, with nothing hidden.

    This replaces a re-deflate-and-compare.  That comparison tied verification
    to the verifier's own zlib build: the same receipt verified on the machine
    that published it and failed everywhere else, which is the opposite of what
    an offline receipt is for.  (It did exactly that -- green on Python 3.14
    locally, "archive is not canonical byte-for-byte" on CI's 3.11.)

    What the comparison was really standing in for is that no bytes exist
    outside the declared members: no prefix, no padding between entries, no
    appended data, no second central directory.  Check that structurally.
    Every entry's metadata, payload digest and CRC is verified by the caller,
    so a dense layout plus those checks pins the whole file.
    """
    position = 0
    for info in infos:
        if info.header_offset != position:
            raise model.ReceiptError(
                f"archive has a gap or overlap before {info.filename}: {path}"
            )
        # flag_bits == 0 and extra == b"" are enforced by the caller, so the
        # local header is exactly 30 bytes plus the name, with no descriptor.
        position += 30 + len(info.filename.encode("utf-8")) + info.compress_size
    directory_offset = position
    for info in infos:
        position += (
            46
            + len(info.filename.encode("utf-8"))
            + len(info.extra)
            + len(info.comment)
        )
    directory_size = position - directory_offset

    if len(blob) < 22:
        raise model.ReceiptError(f"archive is too short to hold a directory: {path}")
    end = blob[-22:]
    if end[:4] != b"PK\x05\x06":
        raise model.ReceiptError(
            f"archive does not end with its central directory: {path}"
        )
    (
        disk, directory_disk, disk_entries, total_entries,
        recorded_size, recorded_offset, comment_length,
    ) = struct.unpack("<HHHHIIH", end[4:])
    if (
        disk
        or directory_disk
        or comment_length
        or disk_entries != len(infos)
        or total_entries != len(infos)
        or recorded_offset != directory_offset
        or recorded_size != directory_size
        or directory_offset + directory_size + 22 != len(blob)
    ):
        raise model.ReceiptError(
            f"archive has trailing, hidden, or misdeclared bytes: {path}"
        )


def _read_zip_record(
    edge: dict[str, object],
    raw_record: object,
    index: int,
    archive_blobs: Mapping[str, bytes],
) -> dict[tuple[str, str], bytes]:
    record = _expect_fields(
        raw_record,
        {"root", "name", "path", "size", "sha256", "members"},
        "archive",
    )
    root, name, path = record["root"], record["name"], record["path"]
    expected_name = (
        f"pinball-{edge['from_version']}-{edge['to_version']}-{index}-"
        f"{edge['tag']}.zip"
    )
    if (
        root not in model.ROOT_PREFIX
        or name != expected_name
        or path != f"active/{name}"
        or not isinstance(path, str)
    ):
        raise model.ReceiptError("archive root/name/path/sequence mismatch")
    blob = archive_blobs.get(path)
    if blob is None:
        raise model.ReceiptError(f"archive is missing: {path}")
    if (
        len(blob) > model.ZIP_CAP
        or len(blob) != record["size"]
        or model._sha(blob) != record["sha256"]
    ):
        raise model.ReceiptError(f"archive size or sha256 mismatch: {path}")
    payloads: dict[tuple[str, str], bytes] = {}
    members: list[dict[str, object]] = []
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as zipped:
            infos = zipped.infolist()
            names = [info.filename for info in infos]
            if not names or names != sorted(names) or len(names) != len(set(names)):
                raise model.ReceiptError(f"archive member order/duplicates: {path}")
            for info in infos:
                if (
                    info.date_time != model.ZIP_TIMESTAMP
                    or info.compress_type != zipfile.ZIP_DEFLATED
                    or info.create_system != 3
                    or info.external_attr != model.ZIP_MODE
                    or info.flag_bits != 0
                    or info.extra != b""
                    or info.comment != b""
                    or info.is_dir()
                    or not info.filename.startswith(model.ROOT_PREFIX[cast(str, root)])
                ):
                    raise model.ReceiptError(
                        f"archive metadata/root drift: {path}!{info.filename}"
                    )
                payload = zipped.read(info)
                payloads[(cast(str, root), info.filename)] = payload
                members.append({
                    "name": info.filename,
                    "size": len(payload),
                    "sha256": model._sha(payload),
                })
            if zipped.comment or zipped.testzip() is not None:
                raise model.ReceiptError(f"archive CRC/comment drift: {path}")
            _assert_dense_layout(blob, infos, cast(str, path))
    except model.ReceiptError:
        raise
    except (OSError, zipfile.BadZipFile, RuntimeError) as error:
        raise model.ReceiptError(f"cannot read archive {path}: {error}") from error
    if members != record["members"]:
        raise model.ReceiptError(f"archive member evidence mismatch: {path}")
    return payloads


def _archive_evidence(
    edge: dict[str, object], archive_blobs: Mapping[str, bytes]
) -> tuple[dict[tuple[str, str], bytes], set[str]]:
    raw_archives = edge.get("archives")
    if not isinstance(raw_archives, list):
        raise model.ReceiptError("edge archives must be an array")
    payloads: dict[tuple[str, str], bytes] = {}
    paths: set[str] = set()
    last_root = -1
    for index, record in enumerate(raw_archives, start=1):
        if not isinstance(record, dict) or not isinstance(record.get("root"), str):
            raise model.ReceiptError("archive record/root is invalid")
        root = cast(str, record["root"])
        if root not in model.ROOTS or model.ROOTS.index(root) < last_root:
            raise model.ReceiptError("archive roots are not in canonical order")
        last_root = model.ROOTS.index(root)
        path = record.get("path")
        if not isinstance(path, str) or path in paths:
            raise model.ReceiptError("archive path is invalid or duplicated")
        paths.add(path)
        for key, payload in _read_zip_record(
            edge, record, index, archive_blobs
        ).items():
            if key in payloads:
                raise model.ReceiptError("archive member repeated across parts")
            payloads[key] = payload
    if set(archive_blobs) != paths:
        raise model.ReceiptError("archive blob coverage mismatch")
    return payloads, paths


def _verify_path(
    context: model.ReleaseContext,
    version: str,
    members_by_path: Mapping[MemberKey, tuple[inventory.InventoryMember, ...]],
    raw_path: object,
    archive_paths: set[str],
    payloads: Mapping[tuple[str, str], bytes],
) -> tuple[MemberKey, tuple[str, str] | None, int]:
    if not isinstance(raw_path, dict):
        raise model.ReceiptError("path evidence must be an object")
    root, logical = raw_path.get("root"), raw_path.get("logical_path")
    key = cast(MemberKey, (root, logical))
    if key not in members_by_path:
        raise model.ReceiptError("path coverage contains an unknown path")
    members = members_by_path[key]
    is_table = members[0].kind == "table"
    fields = {
        "root", "logical_path", "baseline", "output_size", "output_sha256",
        "claims", "disposition", "archive", "archive_member",
    }
    if is_table:
        fields |= {"unclaimed_before_sha256", "unclaimed_after_sha256"}
    path_record = _expect_fields(raw_path, fields, "path")
    expected_claims = [model._claim_record(member) for member in members]
    if path_record["claims"] != expected_claims:
        raise model.ReceiptError(
            f"terminal claim evidence mismatch for {root}:{logical}"
        )
    descriptor = context.baseline_descriptors[version][key]
    expected_baseline = None if not descriptor.present else {
        "size": descriptor.size, "sha256": descriptor.sha256,
    }
    if path_record["baseline"] != expected_baseline:
        raise model.ReceiptError(f"baseline evidence mismatch for {root}:{logical}")
    member_name = model.archive_member_name(cast(str, root), cast(str, logical))
    used: tuple[str, str] | None = None
    if path_record["disposition"] == "included":
        archive_path = path_record["archive"]
        if not isinstance(archive_path, str) or archive_path not in archive_paths:
            raise model.ReceiptError(
                f"included path has invalid archive for {root}:{logical}"
            )
        payload = payloads.get((cast(str, root), member_name))
        if payload is None or path_record["archive_member"] != member_name:
            raise model.ReceiptError(
                f"included path missing ZIP member for {root}:{logical}"
            )
        used = cast(tuple[str, str], (root, member_name))
        if (
            len(payload) != path_record["output_size"]
            or model._sha(payload) != path_record["output_sha256"]
        ):
            raise model.ReceiptError(
                f"included output hash mismatch for {root}:{logical}"
            )
        inventory.attest_contract(
            InventoryContract(context.terminal.contract_id, members),
            lambda _member, raw=payload: raw,
        )
        if not descriptor.present:
            source_size, source_sha256 = model._terminal_source_anchor(members)
            if len(payload) != source_size or model._sha(payload) != source_sha256:
                raise model.ReceiptError(
                    f"absent baseline output differs from terminal source for "
                    f"{root}:{logical}"
                )
        if (
            is_table
            and model._unclaimed_sha(payload, members)
            != path_record["unclaimed_after_sha256"]
        ):
            raise model.ReceiptError(
                f"unclaimed output digest mismatch for {root}:{logical}"
            )
    elif path_record["disposition"] == "omitted_equal":
        if path_record["archive"] is not None or path_record["archive_member"] is not None:
            raise model.ReceiptError("omitted path unexpectedly names an archive")
        if (
            not descriptor.present
            or path_record["output_size"] != descriptor.size
            or path_record["output_sha256"] != descriptor.sha256
        ):
            raise model.ReceiptError(
                f"omitted path is not baseline-equal for {root}:{logical}"
            )
        if not model._baseline_terminal_equivalent(
            members, context.baselines[version]
        ):
            raise model.ReceiptError(
                f"omitted path lacks terminal baseline claim for {root}:{logical}"
            )
    else:
        raise model.ReceiptError(
            f"invalid path disposition {path_record['disposition']!r}"
        )
    if (
        is_table
        and path_record["unclaimed_before_sha256"]
        != path_record["unclaimed_after_sha256"]
    ):
        raise model.ReceiptError(f"unclaimed rows changed for {root}:{logical}")
    if is_table and descriptor.present:
        if (
            descriptor.unclaimed_sha256 is None
            or path_record["unclaimed_before_sha256"]
            != descriptor.unclaimed_sha256
        ):
            raise model.ReceiptError(
                f"baseline unclaimed sha256 mismatch for {root}:{logical}"
            )
    elif descriptor.unclaimed_sha256 is not None:
        raise model.ReceiptError(
            f"unexpected baseline unclaimed anchor for {root}:{logical}"
        )
    return key, used, len(expected_claims)


def _verify_manifest(
    value: object,
    manifest_raw: bytes,
    edges: list[dict[str, object]],
    policy: model.ReleasePolicy,
) -> None:
    evidence = _expect_fields(value, {
        "preimage_sha256", "output_sha256", "cdn_version",
        "preimage_patch_count", "appended_patches",
    }, "manifest evidence")
    if (
        evidence["preimage_sha256"] != policy.manifest_preimage_sha256
        or evidence["cdn_version"] != policy.manifest_cdn_version
        or evidence["preimage_patch_count"]
        != policy.manifest_preimage_patch_count
    ):
        raise model.ReceiptError("manifest policy baseline mismatch")
    manifest = model._json(manifest_raw, "manifest")
    if not isinstance(manifest, dict) or manifest.get("cdn_version") != evidence["cdn_version"]:
        raise model.ReceiptError("manifest cdn_version mismatch")
    rendered_output = (
        json.dumps(manifest, ensure_ascii=False, indent=1) + "\n"
    ).encode("utf-8")
    if manifest_raw != rendered_output:
        raise model.ReceiptError("manifest output is not canonical renderer bytes")
    patches, appended = manifest.get("patches"), evidence["appended_patches"]
    preimage_count = evidence["preimage_patch_count"]
    if (
        not isinstance(patches, list)
        or not isinstance(appended, list)
        or not appended
        or not isinstance(preimage_count, int)
        or preimage_count < 0
        or len(patches) < preimage_count + len(appended)
        # 判据从「必须在末尾」改成「必须在它当初写入的那个位置」。
        # manifest 是 append-only 的:后续发布会继续往尾部追加(第一例是
        # 1.4.312→1.4.318 的 local-live-fixups),旧回执不该因此被判失效。
        # 钉住绝对位置比钉住「末尾」更严——它同时否掉了「插队到前面」。
        or patches[preimage_count:preimage_count + len(appended)] != appended
    ):
        raise model.ReceiptError("manifest appended patch mismatch")
    if len(appended) != len(edges):
        raise model.ReceiptError("manifest must describe exactly both edges")
    old_patches = patches[:preimage_count]
    # 回执只对**它自己那次追加**负责,所以 output_sha256 比的是
    # 「发布当时的 manifest」而不是这个文件的永恒字节。整文件仍然被上面的
    # canonical-render 检查覆盖,后续追加条目的完整性由 manifest 自己的
    # archive_integrity + 图侧校验负责。
    at_release = dict(manifest)
    at_release["patches"] = patches[:preimage_count + len(appended)]
    rendered_at_release = (
        json.dumps(at_release, ensure_ascii=False, indent=1) + "\n"
    ).encode("utf-8")
    if model._sha(rendered_at_release) != evidence["output_sha256"]:
        raise model.ReceiptError("manifest output sha256 mismatch")
    preimage = dict(manifest)
    preimage["patches"] = old_patches
    rendered_preimage = (
        json.dumps(preimage, ensure_ascii=False, indent=1) + "\n"
    ).encode("utf-8")
    if (
        model._sha(rendered_preimage) != evidence["preimage_sha256"]
        or preimage.get("cdn_version") != evidence["cdn_version"]
    ):
        raise model.ReceiptError("manifest preimage sha256/cdn_version mismatch")
    for patch, edge in zip(appended, edges):
        archives = cast(list[dict[str, object]], edge["archives"])
        integrity = [
            {
                "name": archive["name"],
                "size": archive["size"],
                "sha256": archive["sha256"],
            }
            for archive in archives
        ]
        if (
            not isinstance(patch, dict)
            or patch.get("id") != edge["patch_id"]
            or patch.get("version") != edge["to_version"]
            or patch.get("depends_on") != edge["from_version"]
            or patch.get("enabled") is not True
            or patch.get("chain") != [archive["name"] for archive in archives]
            or patch.get("archive_integrity") != integrity
        ):
            raise model.ReceiptError(
                "manifest edge/chain/archive_integrity evidence mismatch"
            )


def _verify_receipt(
    context: model.ReleaseContext,
    policy: model.ReleasePolicy,
    receipt_raw: bytes,
    *,
    archive_blobs: Mapping[str, bytes],
    manifest_raw: bytes,
    server_files: Mapping[str, bytes],
) -> model.VerificationReport:
    keys = model._validate_context(context, policy)
    value = model.parse_receipt(receipt_raw)
    if receipt_raw != model.canonical_receipt(value):
        raise model.ReceiptError("receipt encoding is not canonical UTF-8 JSON")
    top = _expect_fields(value, {
        "schema", "release_id", "target_version", "terminal_contract_id",
        "terminal_member_count", "unique_path_count", "contracts", "edges",
        "manifest", "server", "client_migrations", "receipt_sha256",
    }, "receipt")
    stored_digest = top.pop("receipt_sha256")
    if (
        not isinstance(stored_digest, str)
        or model._sha(model.canonical_receipt(top)) != stored_digest
    ):
        raise model.ReceiptError("receipt sha256 mismatch")
    if (
        top["schema"] != model.SCHEMA
        or top["release_id"] != policy.release_id
        or top["target_version"] != "1.4.312"
        or top["terminal_contract_id"] != policy.terminal_contract_id
        or top["terminal_member_count"] != policy.terminal_member_count
        or top["unique_path_count"] != policy.unique_path_count
    ):
        raise model.ReceiptError("receipt fixed release identity/count mismatch")
    _verify_contracts(context, top["contracts"])
    raw_edges = top["edges"]
    if not isinstance(raw_edges, list) or len(raw_edges) != len(policy.baseline_versions):
        raise model.ReceiptError("receipt must contain both edges")
    members_by_path = model._members_by_path(context.terminal)
    all_archive_paths: set[str] = set()
    for edge_index, raw_edge in enumerate(raw_edges):
        edge = _expect_fields(raw_edge, {
            "from_version", "to_version", "patch_id", "tag", "archives", "paths"
        }, "edge")
        version = policy.baseline_versions[edge_index]
        if edge["from_version"] != version or edge["to_version"] != "1.4.312":
            raise model.ReceiptError("edge version/order mismatch")
        declared_paths = {
            cast(str, record.get("path"))
            for record in cast(list[dict[str, object]], edge["archives"])
            if isinstance(record, dict)
        }
        if all_archive_paths & declared_paths:
            raise model.ReceiptError("archive path reused across edges")
        edge_blobs = {
            path: archive_blobs[path]
            for path in declared_paths if path in archive_blobs
        }
        payloads, archive_paths = _archive_evidence(edge, edge_blobs)
        all_archive_paths.update(archive_paths)
        raw_paths = edge["paths"]
        if not isinstance(raw_paths, list) or len(raw_paths) != len(keys):
            raise model.ReceiptError("edge path coverage mismatch")
        actual_keys: list[MemberKey] = []
        used: set[tuple[str, str]] = set()
        claim_count = 0
        for raw_path in raw_paths:
            key, payload_key, path_claims = _verify_path(
                context, version, members_by_path, raw_path,
                archive_paths, payloads,
            )
            actual_keys.append(key)
            if payload_key is not None:
                used.add(payload_key)
            claim_count += path_claims
        if tuple(actual_keys) != keys:
            raise model.ReceiptError("edge path coverage/order mismatch")
        if claim_count != policy.terminal_member_count:
            raise model.ReceiptError("edge terminal claim coverage mismatch")
        if used != set(payloads):
            raise model.ReceiptError("ZIP payload coverage mismatch")
    if set(archive_blobs) != all_archive_paths:
        raise model.ReceiptError("archive blob coverage mismatch")
    _verify_manifest(
        top["manifest"], manifest_raw,
        cast(list[dict[str, object]], raw_edges),
        policy,
    )
    server_value = _expect_fields(
        top["server"], {"remaining_changes", "files"}, "server evidence"
    )
    expected_server, expected_clients = model._server_evidence(context, server_files)
    if server_value != {"remaining_changes": 0, "files": expected_server}:
        raise model.ReceiptError("server terminal evidence mismatch")
    if top["client_migrations"] != expected_clients:
        raise model.ReceiptError("client migration terminal evidence mismatch")
    return model.VerificationReport(
        len(raw_edges), len(keys), policy.terminal_member_count
    )


def verify_receipt(
    context: model.ReleaseContext,
    policy: model.ReleasePolicy,
    receipt_raw: bytes,
    *,
    archive_blobs: Mapping[str, bytes],
    manifest_raw: bytes,
    server_files: Mapping[str, bytes],
) -> model.VerificationReport:
    """Verify committed receipt evidence without consulting live/CDN state."""
    try:
        return _verify_receipt(
            context, policy, receipt_raw, archive_blobs=archive_blobs,
            manifest_raw=manifest_raw, server_files=server_files,
        )
    except model.ReceiptError:
        raise
    except (
        InventoryError, server_contract.MigrationError,
        KeyError, TypeError, ValueError,
    ) as error:
        raise model.ReceiptError(f"cannot verify release receipt: {error}") from error


def _contained_read(root: Path, relative: str) -> bytes:
    model._safe_relative(relative, "offline input")
    resolved_root = root.resolve(strict=True)
    candidate = root.joinpath(*relative.split("/"))
    if candidate.is_symlink():
        raise model.ReceiptError(f"offline input is a symlink: {relative}")
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(resolved_root)
    except (OSError, ValueError) as error:
        raise model.ReceiptError(
            f"offline input escapes or is missing: {relative}"
        ) from error
    if not resolved.is_file():
        raise model.ReceiptError(f"offline input is not a file: {relative}")
    return resolved.read_bytes()


def _parser() -> argparse.ArgumentParser:
    repo = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--contracts", type=Path,
        default=repo / "mod-tools" / "release-contracts",
    )
    parser.add_argument(
        "--receipt", type=Path,
        default=repo / "assets" / "asset-patch" / "release-receipts"
        / "local-live-1.4.312.json",
    )
    parser.add_argument(
        "--patch-root", type=Path, default=repo / "assets" / "asset-patch"
    )
    parser.add_argument(
        "--manifest", type=Path,
        default=repo / "assets" / "asset-patch" / "manifest.json",
    )
    parser.add_argument("--server-root", type=Path, default=repo / "assets")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        context = model.load_local_context(args.contracts)
        receipt_raw = args.receipt.read_bytes()
        value = model.parse_receipt(receipt_raw)
        edges = value.get("edges")
        if not isinstance(edges, list):
            raise model.ReceiptError("receipt edges must be an array")
        archive_paths = {
            cast(str, archive["path"])
            for edge in edges if isinstance(edge, dict)
            for archive in cast(list[dict[str, object]], edge.get("archives", []))
            if isinstance(archive, dict) and isinstance(archive.get("path"), str)
        }
        archive_blobs = {
            path: _contained_read(args.patch_root, path) for path in archive_paths
        }
        logicals = {member.logical_path for member in context.migration.server_members}
        server_files = {
            logical: _contained_read(args.server_root, logical)
            for logical in logicals
        }
        report = verify_receipt(
            context, model.LOCAL_POLICY, receipt_raw,
            archive_blobs=archive_blobs,
            manifest_raw=args.manifest.read_bytes(),
            server_files=server_files,
        )
        print(json.dumps({
            "ok": True,
            "edges": report.edge_count,
            "paths_per_edge": report.path_count_per_edge,
            "claims_per_edge": report.claim_count_per_edge,
        }, sort_keys=True, separators=(",", ":")))
        return 0
    except (OSError, model.ReceiptError) as error:
        print(json.dumps(
            {"ok": False, "error": str(error)},
            ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
