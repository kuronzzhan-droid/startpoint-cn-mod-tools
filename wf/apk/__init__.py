"""Offline, method-level SWF/ABC patching primitives.

No APK, toolchain or signing key is opened when this package is imported.
Version-specific build/sign recipes remain under archive/legacy/apk.
"""
from .patching import Refused, apply_patches

__all__ = ["Refused", "apply_patches"]
