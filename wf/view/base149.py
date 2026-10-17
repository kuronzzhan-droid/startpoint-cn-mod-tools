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

SALT = q.SALT
KULO = path("kulo")
STORE131 = path("store131")
ACTIVE = KULO / "assets/asset-patch/active"

def member(logical):
    digest = hashlib.sha1((logical + SALT).encode()).hexdigest()
    return f"production/upload/{digest[:2]}/{digest[2:]}"

class HistoricalView:
    def __init__(self, *, store=STORE131, active=ACTIVE, tip=149, extra_zips=()):
        self.store, self.active, self.tip = Path(store), Path(active), int(tip)
        self.zips = []
        names = sorted(p.name for p in self.active.iterdir())
        for version in range(131, self.tip):
            pattern = re.compile(rf"^pinball-1\.4\.{version}-1\.4\.{version+1}-\d+-.*\.zip$")
            self.zips.extend(self.active / name for name in names if pattern.match(name) and "candidate" not in name)
        self.zips.extend(Path(p) for p in extra_zips)
        self.index = {}
        for archive in self.zips:
            with zipfile.ZipFile(archive) as z:
                for name in z.namelist():
                    self.index[name] = archive

    def read_raw(self, logical):
        return self.read_member(member(logical))

    def read_member(self, name):
        if name in self.index:
            archive = self.index[name]
            with zipfile.ZipFile(archive) as z:
                return z.read(name), archive.name
        if not name.startswith("production/") or ".." in name.split("/"):
            raise ValueError(f"invalid CDN member: {name}")
        root, relative = name.removeprefix("production/").split("/", 1)
        directory = self.store if root == "upload" else self.store.parent / root
        return (directory / relative).read_bytes(), "store131"

    def load(self, logical):
        return q.parse_node(self.read_raw(logical)[0])

_VIEW = None

def configure(*, store=STORE131, active=ACTIVE, tip=149, extra_zips=()):
    global _VIEW
    _VIEW = HistoricalView(store=store, active=active, tip=tip, extra_zips=extra_zips)
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
