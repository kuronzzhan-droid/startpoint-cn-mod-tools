"""Explicit APK bundle fallback for resources absent from the CDN/store view."""
from __future__ import annotations

import hashlib
import io
from pathlib import Path
import zipfile

from wf.view.base149 import member
from wf.view.chain import digest


class BundleFallbackView:
    """Keep manifest precedence; record every APK-only member actually consumed."""

    def __init__(self, view, apk):
        self.view, self.apk = view, Path(apk)
        self.apk_sha256 = digest(self.apk)
        with zipfile.ZipFile(self.apk) as archive:
            raw = archive.read("assets/bundle.zip")
        self.bundle_sha256 = hashlib.sha256(raw).hexdigest()
        self.bundle = zipfile.ZipFile(io.BytesIO(raw))
        names = self.bundle.namelist()
        if len(names) != len(set(names)):
            raise ValueError("duplicate APK bundle member")
        self.members = {}

    def __getattr__(self, name):
        return getattr(self.view, name)

    def read_raw(self, logical):
        try:
            return self.view.read_raw(logical)
        except FileNotFoundError:
            relative = member(logical).removeprefix("production/upload/")
            candidates = [f"production/{root}/{relative}" for root in ("common_bundle", "android_bundle")]
            found = [name for name in candidates if name in self.bundle.namelist()]
            if not found:
                raise
            payloads = [self.bundle.read(name) for name in found]
            if len(set(payloads)) > 1:
                raise ValueError(f"ambiguous APK bundle payload: {logical}")
            raw = payloads[0]
            self.members[logical] = {"member": found[0], "sha256": hashlib.sha256(raw).hexdigest()}
            return raw, "apk:assets/bundle.zip/" + found[0]

    def verify(self):
        if digest(self.apk) != self.apk_sha256:
            raise ValueError("APK bundle source changed while scanning")
        return self.view.verify()

    def bundle_evidence(self):
        return {"apk_sha256": self.apk_sha256, "bundle_sha256": self.bundle_sha256,
                "members": dict(sorted(self.members.items()))}
