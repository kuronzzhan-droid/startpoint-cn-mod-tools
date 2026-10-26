"""Read selected APK bundle bytes after the existing strict index validation."""
from __future__ import annotations

import hashlib
import io
from pathlib import Path
import tempfile
import zipfile

import wf_mod_tool as core
from .bundle_keys import load_bundle_index
from .drafts import DraftError


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


class PfBundle:
    """An immutable in-memory APK bundle, identified by its verified SHA-256."""

    def __init__(self, filename, logical, cache_dir=None):
        # The shared index requires its cache outside the repository. A temporary
        # cache also keeps a catalog preview free of persistent cache writes.
        if cache_dir is None:
            with tempfile.TemporaryDirectory(prefix="wf-pf-index-") as cache:
                self.index = load_bundle_index(filename, logical_paths=[logical], cache_dir=cache)
        else:
            self.index = load_bundle_index(filename, logical_paths=[logical], cache_dir=cache_dir)
        with Path(filename).open("rb") as stream:
            before = hashlib.file_digest(stream, "sha256").hexdigest()
        if before != self.index["sha256"]:
            raise DraftError("目标 APK 在索引读取后发生变化")
        with zipfile.ZipFile(filename) as outer:
            self._raw = outer.read("assets/bundle.zip")
        with Path(filename).open("rb") as stream:
            after = hashlib.file_digest(stream, "sha256").hexdigest()
        if after != before:
            raise DraftError("目标 APK 在资源读取时发生变化")
        self.sha256 = after

    def read(self, logical):
        key = core.sha1_path(logical)
        member = "production/android_bundle/" + key[:2] + "/" + key[2:]
        with zipfile.ZipFile(io.BytesIO(self._raw)) as bundle:
            try:
                return bundle.read(member)
            except KeyError:
                return None
