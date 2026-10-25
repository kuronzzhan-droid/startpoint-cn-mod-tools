"""Manifest-derived, read-only asset view with reproducible input locks."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import re
import zipfile

from .base149 import HistoricalView, member
from .chain import digest, manifest_tip, resolve_archives, resolve_chain
from .config import view_config, view_options
from .safety import local_output

CDN_ROOTS = ("upload", "small_upload", "medium_upload", "android_upload", "ios_upload")
CDN_MEMBER = re.compile(r"^production/(upload|small_upload|medium_upload|android_upload|ios_upload)/[0-9a-f]{2}/[0-9a-f]{38}$")


class ManifestView(HistoricalView):
    """A store baseline plus exactly the enabled dependency chain up to tip.

    ``lock=None`` records inputs for a new lock. A supplied lock is enforced,
    including an empty store_members mapping (which forbids every fallback).
    """

    def __init__(self, tip=None, *, store=None, manifest=None, search_dirs=None,
                 base_version=None, lock=None, manifests=None, view_name=None, extra_zips=()):
        self.view_name, options = view_options(view_name)
        base_version = base_version or options.get("base_version", "1.4.131")
        tip = tip if tip is not None else options.get("tip")
        self.store, self.manifest, self.search_dirs, self.manifests = view_config(
            store=store, manifest=manifest, search_dirs=search_dirs, manifests=manifests, view_name=view_name)
        self.active = self.manifest.parent / "active"
        if tip is None:
            tip = manifest_tip(self.manifest, self.search_dirs, base_version, self.manifests)
        self.tip, self.base_version = tip, base_version
        self.edges = resolve_chain(self.manifest, self.search_dirs, base_version, tip, self.manifests)
        self.zips, self.zip_records = resolve_archives(self.edges, self.search_dirs)
        self.extra_zips = [Path(p).resolve() for p in extra_zips]
        self.zips.extend(self.extra_zips)
        self.zip_records.extend({"name": p.name, "sha256": digest(p)} for p in self.extra_zips)
        self.read_members, self.index, self._store_reads = {}, {}, {}
        self._lock = json.loads(Path(lock).read_text(encoding="utf-8-sig")) if isinstance(lock, (str, Path)) else copy.deepcopy(lock)
        self.store_member_sha256 = None
        if self._lock is not None:
            expected = self._lock
            if not isinstance(expected, dict):
                raise ValueError("view lock must be an object")
            if (expected.get("schema"), expected.get("base_version"), expected.get("tip")) != (
                    "wf-view-lock/1", base_version, tip):
                raise ValueError("view lock schema, baseline or tip mismatch")
            if expected.get("zips") != self.zip_records:
                raise ValueError("view lock ZIP list or SHA-256 mismatch")
            self.store_member_sha256 = expected.get("store_members")
            if not isinstance(self.store_member_sha256, dict):
                raise ValueError("view lock requires store_members, including an empty mapping")
        self._stats = {}
        for archive in self.zips:
            with zipfile.ZipFile(archive) as z:
                names = [info.filename for info in z.infolist() if not info.is_dir()]
                if len(set(names)) != len(names):
                    raise ValueError(f"duplicate ZIP member: {archive.name}")
                for name in names:
                    self._validate_member(name)
                    self.index[name] = archive
            self._stats[archive] = self._stat(archive)
        for name in self.store_member_sha256 or {}:
            self.read_store_member(name)

    @staticmethod
    def _stat(archive):
        stat = archive.stat()
        return stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns

    @staticmethod
    def _validate_member(name):
        if not CDN_MEMBER.fullmatch(name):
            raise ValueError(f"invalid CDN member: {name}")

    def read_store_member(self, name):
        self._validate_member(name)
        data = super().read_store_member(name)
        sha256 = hashlib.sha256(data).hexdigest()
        if name in self._store_reads and self._store_reads[name] != sha256:
            raise ValueError(f"used store member changed during use: {name}")
        self._store_reads[name] = sha256
        return data

    def read_member(self, name):
        self._validate_member(name)
        archive = self.index.get(name)
        if archive is not None and self._stat(archive) != self._stats[archive]:
            # Refuse mid-session edits even when the caller did not supply a lock.
            expected = self.zip_records[self.zips.index(archive)]["sha256"]
            if digest(archive) != expected:
                raise ValueError(f"view ZIP changed while reading: {archive.name}")
            self._stats[archive] = self._stat(archive)
        return super().read_member(name)

    def verify(self):
        """Recheck discovery, all ZIP bytes and every used store member."""
        edges = resolve_chain(self.manifest, self.search_dirs, self.base_version, self.tip, self.manifests)
        archives, records = resolve_archives(edges, self.search_dirs)
        archives.extend(self.extra_zips)
        records.extend({"name": p.name, "sha256": digest(p)} for p in self.extra_zips)
        if archives != self.zips or records != self.zip_records:
            raise ValueError("view inputs changed during use")
        for name, sha256 in list(self._store_reads.items()):
            if hashlib.sha256(self.read_store_member(name)).hexdigest() != sha256:
                raise ValueError(f"used store member changed during use: {name}")
        return self.lock_data()

    def lock_data(self):
        members = dict(self.store_member_sha256 or {})
        members.update(self._store_reads)
        return {"schema": "wf-view-lock/1", "base_version": self.base_version, "tip": self.tip,
                "zips": copy.deepcopy(self.zip_records), "store_members": dict(sorted(members.items()))}

    def save_lock(self, destination):
        document = self.verify()
        target = local_output(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return target

    def characters(self):
        return self.load("master/character/character.orderedmap")


def build_view(tip, **options):
    return ManifestView(tip, **options)
