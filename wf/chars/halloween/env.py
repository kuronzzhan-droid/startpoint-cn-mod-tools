"""Explicit read-only inputs and checkout-local outputs for replay."""
import os
from pathlib import Path
from wf.paths import path, root_path, REPOSITORY
INPUT = root_path("out/万圣新角色-20261016")
OUT = INPUT
RUN = os.environ.get("WF_REPLAY_RUN", "historical221-run1")
if not RUN.replace("-", "").isalnum():
    raise ValueError("WF_REPLAY_RUN must be an alphanumeric run name")
RUN_ROOT = path("output", "halloween-full", RUN)
ROOT = RUN_ROOT / "pkgroot"
if os.name == "nt":
    ROOT = Path("\\\\?\\" + str(ROOT.resolve()))
STORE = INPUT / "viewstore/production/upload"
SERVER_BASE = path("kulo", "assets")
SCRIPTS = Path.home() / "Downloads"
TEMP = RUN_ROOT / "tmp"
