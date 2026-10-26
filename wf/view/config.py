"""Explicit manifest-view configuration; no filesystem-wide discovery."""
from pathlib import Path
import os

from wf.paths import path, profile_data, root_path


def view_options(view_name=None):
    config, _ = profile_data()
    selected = view_name or os.environ.get("WF_STUDIO_VIEW") or config.get("default_view")
    views = config.get("views", {})
    if not isinstance(views, dict):
        raise ValueError("profile views must be an object")
    if selected is not None and (not isinstance(selected, str) or selected not in views):
        raise ValueError(f"unknown named view: {selected}")
    options = views[selected] if selected is not None else config.get("view", {})
    if not isinstance(options, dict):
        raise ValueError("profile view must be an object")
    return selected, options


def view_config(*, store=None, manifest=None, search_dirs=None, manifests=None, view_name=None):
    _, options = view_options(view_name)

    def resolve(value):
        if not isinstance(value, (str, Path)) or not str(value).strip():
            raise ValueError("view paths must be nonempty strings")
        location = Path(value)
        return (location if location.is_absolute() else root_path() / location).resolve()

    explicit_manifest = manifest is not None
    store = store if store is not None else options.get("store")
    manifest = manifest if manifest is not None else options.get("manifest")
    store = resolve(store) if store is not None else path("store131").resolve()
    manifest = resolve(manifest) if manifest is not None else path("kulo", "assets/asset-patch/manifest.json").resolve()
    values = search_dirs if search_dirs is not None else options.get("zip_dirs", [])
    if not isinstance(values, (list, tuple)):
        raise ValueError("view.zip_dirs must be an array")
    directories = list(dict.fromkeys(resolve(p) for p in values))
    if not store.is_dir():
        raise ValueError(f"view store is not a directory: {store}")
    if not manifest.is_file():
        raise ValueError(f"view manifest does not exist: {manifest}")
    for directory in directories:
        if not directory.is_dir():
            raise ValueError(f"view ZIP directory does not exist: {directory}")
    # active/ is a convenience, never a requirement of a standalone manifest.
    active = manifest.parent / "active"
    directories = list(dict.fromkeys(([active] if active.is_dir() else []) + directories))
    if not directories:
        directories = [manifest.parent]
    extras = manifests if manifests is not None else ([] if explicit_manifest else options.get("manifests"))
    if extras is not None and not isinstance(extras, (list, tuple)):
        raise ValueError("view.manifests must be an array")
    extras = [resolve(value) for value in extras] if extras is not None else None
    return store, manifest, directories, extras
