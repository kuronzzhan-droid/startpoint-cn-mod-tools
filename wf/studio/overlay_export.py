"""Export an existing Studio layered delivery using the catalog Overlay packer."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import jsonschema

from wf.paths import REPOSITORY, profile_data, root_path
from .drafts import DraftError
from .rehearsal_io import delivery_folder, inside, read_json, protected_roots, json_bytes
from .overlay_checks import check_delivery

INTERNAL_REASON = "本交付基于内部链，共享表带着其他内容，会盖掉收方的数据；请用 dev 基线视图重新生成"
SCHEMA = REPOSITORY / "docs/studio/patch-manifest.schema.json"


def source_view(baseline):
    """Bind eligibility to the actual build view, including explicit overrides."""
    name = getattr(baseline, "view_name", None)
    config, _ = profile_data()
    view = (config.get("views") or {}).get(name) or {}
    matches = bool(name and view.get("overlay_base") is True)
    for key in ("manifest", "store"):
        configured = view.get(key)
        actual = getattr(baseline, key, None)
        if not configured or actual is None:
            matches = False
        else:
            path = Path(configured)
            path = path if path.is_absolute() else root_path() / path
            matches = matches and path.resolve() == Path(actual).resolve()
    if getattr(baseline, "extra_zips", None):
        matches = False
    if getattr(baseline, "base_version", None) != view.get("base_version", "1.4.131"):
        matches = False
    configured_manifests = view.get("manifests") or []
    configured_manifests = {(Path(p) if Path(p).is_absolute() else root_path() / p).resolve()
                            for p in configured_manifests}
    if {Path(p).resolve() for p in (getattr(baseline, "manifests", None) or [])} != configured_manifests:
        matches = False
    directories = [(Path(p) if Path(p).is_absolute() else root_path() / p).resolve()
                   for p in (view.get("zip_dirs") or [])]
    if view.get("manifest"):
        manifest = Path(view["manifest"])
        manifest = (manifest if manifest.is_absolute() else root_path() / manifest).resolve()
        active = manifest.parent / "active"
        if active.is_dir():
            directories.insert(0, active)
        if not directories:
            directories = [manifest.parent]
    if {Path(p).resolve() for p in getattr(baseline, "search_dirs", [])} != set(directories):
        matches = False
    def normalized_tip(value):
        return f"1.4.{value}" if str(value).isdigit() else value
    if view.get("tip") is not None and normalized_tip(getattr(baseline, "tip", None)) != normalized_tip(view["tip"]):
        matches = False
    return {"name": name, "overlayBase": bool(matches)}


def availability(directory):
    try:
        folder = delivery_folder(directory)
        source = read_json(inside(folder, "source-view.json"))
        config, _ = profile_data()
        view = (config.get("views") or {}).get(source.get("name")) or {}
        if source.get("overlayBase") is True and view.get("overlay_base") is True:
            try:
                check_delivery(folder)
            except (ValueError, OSError, KeyError, TypeError, AttributeError) as exc:
                return {"overlayAvailable": False, "overlayReason": "交付门禁未通过：" + str(exc)}
            return {"overlayAvailable": True, "overlayReason": "来源、交付门禁及 CN 1.8.1 能力已核对；导出时仍需验证三层文件"}
    except (ValueError, OSError, TypeError, AttributeError):
        pass
    return {"overlayAvailable": False, "overlayReason": INTERNAL_REASON}


def validate_schema(document):
    try:
        jsonschema.Draft202012Validator(read_json(SCHEMA)).validate(document)
    except jsonschema.ValidationError as exc:
        raise DraftError("Overlay schema 校验失败：" + exc.message) from exc


def _inputs(folder, compatible_client):
    from wf.tools.core import dev_catalog as catalog
    delivery = read_json(inside(folder, "delivery-manifest.json"))
    if not isinstance(delivery, dict):
        raise DraftError("delivery-manifest 必须是对象")
    upstream = inside(folder, delivery["upstream_manifest"])
    document = read_json(upstream)
    validate_schema(document)
    if compatible_client != document["compatibleClient"]:
        raise DraftError("compatibleClient 与交付分层清单不一致")
    if (document.get("baseVersion") != delivery["from_version"]
            or document["targetVersion"] != delivery["to_version"]):
        raise DraftError("Overlay baseVersion/targetVersion 必须等于交付 from/to")
    catalog._validate_staged_overlay(upstream.parent, document)
    for item in document["archives"]:
        archive = catalog._manifest_archive_input(item)
        if archive.from_version != delivery["from_version"]:
            raise DraftError("inner ZIP 起始版本与交付 from 不一致")
    return upstream.parent, document


def export_overlay(delivery_dir, compatible_client, *, out=None):
    folder = delivery_folder(delivery_dir)
    eligible = availability(folder)
    if not eligible["overlayAvailable"]:
        raise DraftError(eligible["overlayReason"])
    # Import lazily: ordinary Studio startup does not resolve CDN configuration.
    from wf.tools.core import dev_catalog as catalog
    source_root, manifest = _inputs(folder, compatible_client)
    if compatible_client != "CN 1.8.1":
        raise DraftError("Overlay 仅支持已验证的 CN 1.8.1 客户端")
    requirements = check_delivery(folder)
    parent = Path(out).resolve() if out is not None else inside(folder, "overlay")
    if not parent.is_relative_to(folder) or parent == folder:
        raise DraftError("Overlay 输出目录必须位于交付目录内的独立子目录")
    parent = inside(folder, parent.relative_to(folder).as_posix())
    if parent.relative_to(folder).parts[0] != "overlay":
        raise DraftError("Overlay 输出只允许交付目录的 overlay 专用子目录")
    for root in protected_roots():
        if parent.is_relative_to(root):
            raise DraftError("Overlay 禁止写入服务端或 CDN 目录")
    if parent.exists():
        raise DraftError("Overlay 输出目录已存在，拒绝修改已有交付文件")
    # Build beside the final directory and publish only the complete package.
    parent.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".overlay-", dir=parent.parent) as temporary:
        work = Path(temporary)
        sources = []
        for index, item in enumerate(manifest["archives"]):
            archive = catalog._manifest_archive_input(item)
            pinned = catalog._pin_overlay_source(
                archive, source_root, archive.relative_path,
                work / "sources" / str(index) / Path(archive.relative_path).name, work)
            if pinned.archive.sha256 != item["sha256"] or pinned.archive.compressed_bytes != item["bytes"]:
                raise DraftError("Overlay 来源在校验后变化：" + item["relativePath"])
            sources.append(pinned)
        package = work / "output" / manifest["targetVersion"]
        exported = catalog._stage_overlay_package(
            package, sources, sources, base_version=manifest["baseVersion"],
            min_server=None, server_features=(), client_patches=())
        # Retain the complete audited dependency evidence, then publish manifest last.
        (package / "patch-manifest.json").unlink()
        (package / "requires.json").write_bytes(json_bytes(requirements))
        catalog._publish_overlay_manifest(package, exported)
        validate_schema(exported)
        outer_name = f"worldflipper-overlay-{manifest['baseVersion']}-to-{manifest['targetVersion']}.zip"
        catalog._write_outer_overlay(package, package.parent / outer_name, exported)
        if parent.exists():
            raise DraftError("Overlay 输出目录被并发创建")
        os.rename(package.parent, parent)
    return {"ok": True, **eligible, "from": manifest["baseVersion"], "to": manifest["targetVersion"],
            "compatibleClient": compatible_client, "outputDir": str(parent),
            "zip": str(parent / outer_name), "manifest": exported,
            "restartRequired": True, "restartReason": "安装 Overlay 后需人工 npm run start:cn 重启；本工具不启停服务",
            "steps": [{"step": step, "status": "done"} for step in
                      ("view-gate", "schema", "layered-archives", "stage", "outer-zip")]}
