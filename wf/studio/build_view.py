"""Bind CLI builds to the selected editor view, with explicit baseline overrides."""
from pathlib import Path

from wf.paths import path
from wf.view import ManifestView
from wf.view.config import view_options

from .drafts import DraftError
from .source import StudioSource, default_chain_settings, read_extra_list


def baseline_from_args(args):
    selected, configured = view_options(args.view_name)
    manifest = args.baseline_manifest or args.manifest
    directories = args.baseline_zip_dir or args.zip_dir
    manifests = args.baseline_manifest_extra or args.manifest_extra
    if manifests is None and manifest is None:
        manifests = configured.get("manifests")
    store = args.base_store or args.store
    base_version = args.base_version or args.view_base_version
    tip = args.tip
    extras = read_extra_list(args.extra_zips_file)
    if store is not None and (Path(store) / "upload").is_dir():
        store = Path(store) / "upload"
    # Reuse the legacy studio chain configuration when no named view supplies it.
    if manifest is None and selected is None and not configured.get("manifest"):
        default_manifest, default_dirs = default_chain_settings() if not args.no_chain else (None, [])
        manifest = default_manifest or path("kulo", "assets/asset-patch/manifest.json")
        if directories is None and default_manifest is not None:
            directories = default_dirs
    # Legacy build accepted --from as the cutoff. A named view or extras retain
    # their actual selected cutoff instead of fabricating a chain to --from.
    if tip is None and selected is None and not extras and not configured.get("tip"):
        tip = args.from_version
    if isinstance(tip, int) or isinstance(tip, str) and tip.isdigit():
        tip = f"1.4.{tip}"
    view = ManifestView(tip, store=store, manifest=manifest, search_dirs=directories,
                        manifests=manifests, base_version=base_version, view_name=selected,
                        extra_zips=extras, lock=args.view_lock)
    if StudioSource(view).version != args.from_version:
        raise DraftError("所选视图实际版本与 --from 不一致，请使用当前视图版本")
    return view
