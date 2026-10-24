"""Layered read-only data source for the studio.

Wraps :class:`wf.view.base149.HistoricalView` (store131 + kulo active ZIPs up
to a TIP version, plus optional extra ZIPs) and exposes the same duck-typed
``table`` / ``tree`` / ``citation`` interface that ``wf_wiki_catalog`` expects
from ``WikiSource``. All reads are in-memory; nothing is written.
"""
from __future__ import annotations

import os
import re
import threading
import zlib
from pathlib import Path

import wf_dsl
import wf_mod_tool as core
from wf.paths import path
from wf.view.base149 import HistoricalView
from wf_wiki_catalog_source import TABLES

EDGE = re.compile(r"^pinball-(\d+)\.(\d+)\.(\d+)-(\d+)\.(\d+)\.(\d+)-(\d+)-(.*)\.zip$")


def active_dir() -> Path:
    return path("kulo") / "assets/asset-patch/active"


def edge_versions(name: str) -> tuple[int, int] | None:
    """Return (from_patch, to_patch) minor numbers of a ``pinball-1.4.a-1.4.b`` ZIP name."""
    match = EDGE.match(name)
    if not match:
        return None
    return int(match[3]), int(match[6])


def newest_tip(directory: Path | None = None) -> int:
    """Highest ``to`` version among active edges: the default view TIP."""
    directory = directory or active_dir()
    versions = [v[1] for p in directory.iterdir() if (v := edge_versions(p.name)) and "candidate" not in p.name]
    if not versions:
        raise FileNotFoundError(f"没有可用的补丁边: {directory}")
    return max(versions)


def read_extra_list(files) -> list[Path]:
    result: list[Path] = []
    for file in files or ():
        for line in Path(file).read_text("utf-8-sig").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                result.append(Path(line))
    return result


class StudioSource:
    """Duck-typed replacement for ``WikiSource`` reading a ``HistoricalView``."""

    def __init__(self, view: HistoricalView, *, official_root: Path | None = None):
        self.view = view
        self.official_root = official_root
        self._lock = threading.RLock()
        self._raw: dict[tuple[str, bool], tuple[bytes | None, str | None]] = {}
        self._tables: dict[tuple[str, bool], dict] = {}
        self._trees: dict[str, object] = {}
        self._baseline = None
        self.baseline_error: str | None = None
        self.chain = None  # ChainResult when built from a chain manifest

    # -- identity -------------------------------------------------------
    @property
    def version(self) -> str:
        top = self.view.tip
        if isinstance(top, str):
            return top  # ManifestView already binds a complete version string.
        for archive in self.view.zips:
            versions = edge_versions(Path(archive).name)
            if versions:
                top = max(top, versions[1])
        return f"1.4.{top}"

    def describe(self) -> dict:
        extras = [Path(p).name for p in self.view.zips if Path(p).parent != Path(self.view.active)]
        chain = None
        if self.chain is not None:
            chain = {"manifest": str(self.chain.manifest), "resolved": len(self.chain.zips),
                     "missing": self.chain.missing}
        return {"version": self.version, "tip": self.view.tip, "zipCount": len(self.view.zips),
                "memberCount": len(self.view.index), "extraZips": extras, "chain": chain,
                "officialBaseline": self.baseline_error is None and self._baseline is not None,
                "officialBaselineError": self.baseline_error}

    # -- raw access -----------------------------------------------------
    def _official(self):
        if self._baseline is None and self.baseline_error is None:
            try:
                from wf_enhancement_policy import OfficialBaseline
                root = self.official_root or path("kulo") / ".cdn/cn"
                if not root.is_dir():
                    raise FileNotFoundError(str(root))
                self._baseline = OfficialBaseline(root, write_cache=False)
            except Exception as exc:  # noqa: BLE001 - surfaced to the UI honestly
                self.baseline_error = f"{type(exc).__name__}: {exc}"
        return self._baseline

    def raw_with_origin(self, logical: str, official: bool = False) -> tuple[bytes | None, str | None]:
        key = logical, official
        with self._lock:
            if key not in self._raw:
                if official:
                    baseline = self._official()
                    raw = None
                    if baseline is not None:
                        digest = core.sha1_path(logical)
                        try:
                            raw = baseline.get("common", digest[:2] + "/" + digest[2:])
                        except Exception as exc:  # noqa: BLE001
                            self.baseline_error = f"{type(exc).__name__}: {exc}"
                    self._raw[key] = (raw, "official" if raw is not None else None)
                else:
                    try:
                        self._raw[key] = self.view.read_raw(logical)
                    except (FileNotFoundError, KeyError):
                        self._raw[key] = (None, None)
            return self._raw[key]

    def raw(self, logical: str, official: bool = False) -> bytes | None:
        return self.raw_with_origin(logical, official)[0]

    def table(self, name: str, official: bool = False) -> dict:
        logical = TABLES.get(name, name)
        key = logical, official
        with self._lock:
            if key in self._tables:
                return self._tables[key]
            raw = self.raw(logical, official)
            if raw is None:
                result: dict = {}
            elif logical == TABLES["status"]:
                outer = core.read_orderedmap_raw_rows_from_bytes(raw, logical)
                result = {k: core.decode_status_row(v) for k, v in zip(outer.keys, outer.rows)}
            elif logical in (TABLES["skill"], TABLES["switched"]):
                outer = core.read_orderedmap_raw_rows_from_bytes(raw, logical)
                result = {k: {level: core.read_csv_lines(row) for level, row in
                              core.read_orderedmap_file_from_bytes(v).items()}
                          for k, v in zip(outer.keys, outer.rows)}
            else:
                result = {k: core.read_csv_lines(v)
                          for k, v in core.read_orderedmap_file_from_bytes(raw).items()}
            self._tables[key] = result
            return result

    def tree(self, logical: str, official: bool = False):
        with self._lock:
            if logical not in self._trees:
                raw = self.raw(logical)
                self._trees[logical] = None if raw is None else wf_dsl.parse_dsl(
                    zlib.decompress(raw, -15))["tree"]
            return self._trees[logical]

    def citation(self, name: str) -> dict:
        logical = TABLES.get(name, name)
        origin = self.raw_with_origin(logical)[1]
        return {"logical": logical, "source": origin}


def default_chain_settings() -> tuple[Path | None, list[Path]]:
    """Chain manifest + ZIP search dirs from env/profile; None when not configured."""
    from wf.paths import profile_data, configured, root_path
    manifest = path("studio_chain_manifest") if configured("studio_chain_manifest") else None
    raw = os.environ.get("WF_STUDIO_ZIP_DIRS")
    if raw:
        dirs = [Path(p) for p in raw.split(os.pathsep) if p]
    else:
        config, _ = profile_data()
        listed = config.get("studio_zip_dirs")
        if listed:
            dirs = [p if p.is_absolute() else root_path(p) for p in map(Path, listed)]
        else:
            root = root_path()
            dirs = sorted(root.glob("rel*")) + [root / "out"] if root.is_dir() else []
    return manifest, [d for d in dirs if d.is_dir()]


def build_source(*, tip: int | None = None, extra_zips=(), extra_lists=(), chain_manifest=None,
                 search_dirs=None, use_default_chain: bool = True) -> StudioSource:
    tip = int(tip) if tip else newest_tip()
    chain = None
    if chain_manifest is None and use_default_chain:
        chain_manifest, default_dirs = default_chain_settings()
        search_dirs = default_dirs if search_dirs is None else search_dirs
    if chain_manifest is not None:
        from .chain import resolve_chain
        if search_dirs is None:
            search_dirs = default_chain_settings()[1]
        chain = resolve_chain(Path(chain_manifest), search_dirs, after_tip=tip)
    extras = list(chain.zips if chain else []) + [Path(p) for p in extra_zips] + read_extra_list(extra_lists)
    missing = [str(p) for p in extras if not p.is_file()]
    if missing:
        raise FileNotFoundError("额外补丁 ZIP 不存在: " + ", ".join(missing))
    # De-duplicate by file name (an extras list may repeat chain ZIPs); keep the first.
    unique, seen = [], set()
    for archive in extras:
        key = Path(archive).name.lower()
        if key not in seen:
            seen.add(key)
            unique.append(Path(archive))
    view = HistoricalView(tip=tip, extra_zips=unique)
    source = StudioSource(view)
    source.chain = chain
    return source
