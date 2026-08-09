"""Stable public API for the wf-release-v1 wire contract."""

from .canonical import FileIdentity
from .errors import ReleaseError
from .producer import BuildReceipt, BuildRequest, build_character_release
from .verifier import VerificationReport, verify_release


# Wire schemaVersion for all three wf-release-v1 metadata documents. This is
# not the tool version, runtimeApi, or Patch Overlay schema version.
SCHEMA_VERSION = 1

__all__ = [
    "BuildReceipt",
    "BuildRequest",
    "FileIdentity",
    "ReleaseError",
    "SCHEMA_VERSION",
    "VerificationReport",
    "build_character_release",
    "verify_release",
]
