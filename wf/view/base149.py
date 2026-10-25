"""Read-only store131 + ordered local ZIP view; later ZIP members win."""
from __future__ import annotations
import csv
import hashlib
import io
import os
import re
import sys
import zipfile
from pathlib import Path
from wf.paths import path
import wf_quest_lib as q
from .members import archive_members

SALT = q.SALT

def member(logical):
    digest = hashlib.sha1((logical + SALT).encode()).hexdigest()
    return f"production/upload/{digest[:2]}/{digest[2:]}"

class HistoricalView:
    def __init__(self, *, store=None, active=None, tip=149, extra_zips=(), store_member_sha256=None):
        self.store = Path(store) if store is not None else path("store131")
        self.active = Path(active) if active is not None else path("kulo", "assets/asset-patch/active")
        self.tip = int(tip)
        self.store_member_sha256 = store_member_sha256
        self.read_members = {}
        self.zips = []
        names = sorted(p.name for p in self.active.iterdir())
        for version in range(131, self.tip):
            pattern = re.compile(rf"^pinball-1\.4\.{version}-1\.4\.{version+1}-(\d+)-.*\.zip$")
            parts = [(int(match[1]), name) for name in names
                     if (match := pattern.match(name)) and "candidate" not in name]
            self.zips.extend(self.active / name for _, name in sorted(parts))
        self.zips.extend(Path(p) for p in extra_zips)
        self.index, self._zip_members = {}, {}
        for archive in self.zips:
            with zipfile.ZipFile(archive) as z:
                for name, original in archive_members(z).items():
                    self.index[name] = archive
                    self._zip_members[name] = original

    def read_raw(self, logical):
        return self.read_member(member(logical))

    def read_member(self, name):
        if name in self.index:
            archive = self.index[name]
            with zipfile.ZipFile(archive) as z:
                data, source = z.read(self._zip_members.get(name, name)), archive.name
        else:
            data, source = self.read_store_member(name), "store131"
        self.read_members[name] = {"sha256": hashlib.sha256(data).hexdigest(), "source": source}
        return data, source

    def read_store_member(self, name):
        """Reject unrecorded fallback reads whenever the recipe supplies a lock."""
        if not name.startswith("production/") or ".." in name.split("/"):
            raise ValueError(f"invalid CDN member: {name}")
        if self.store_member_sha256 is not None and name not in self.store_member_sha256:
            raise ValueError(f"unlocked store131 member: {name}")
        root, relative = name.removeprefix("production/").split("/", 1)
        directory = self.store if root == "upload" else self.store.parent / root
        data = (directory / relative).read_bytes()
        if self.store_member_sha256 is not None:
            if hashlib.sha256(data).hexdigest() != self.store_member_sha256[name]:
                raise ValueError(f"store131 member digest drift: {name}")
        return data

    def load(self, logical):
        return q.parse_node(self.read_raw(logical)[0])

_VIEW = None

def configure(*, store=None, active=None, tip=149, extra_zips=(), store_member_sha256=None):
    global _VIEW
    _VIEW = HistoricalView(store=store, active=active, tip=tip, extra_zips=extra_zips,
                           store_member_sha256=store_member_sha256)
    live = sys.modules.get("wf.view.live149")
    if live is not None:
        live.flat.cache_clear()
        live.nested.cache_clear()
    return _VIEW

def current():
    global _VIEW
    if _VIEW is None:
        _VIEW = HistoricalView(tip=os.environ.get("WF_TIP", "149"),
                               extra_zips=filter(None, os.environ.get("WF_EXTRA_ZIPS", "").split(";")))
    return _VIEW

def read_raw(logical):
    return current().read_raw(logical)

def load(logical):
    return current().load(logical)

def source(logical):
    return read_raw(logical)[1]

def row(text):
    return next(csv.reader([text]))

def rows(text):
    return list(csv.reader(io.StringIO(text, newline="")))

def join(values):
    output = io.StringIO()
    csv.writer(output, lineterminator="").writerow(values)
    return output.getvalue()

def join_rows(values):
    return "\n".join(join(value) for value in values)
