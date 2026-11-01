"""Offline Preact handler regression: stale gates, read-only opening and input errors."""
import shutil
import subprocess
from pathlib import Path

import pytest


def test_studio_e_frontend_handlers():
    root = Path(__file__).resolve().parents[1]
    node = shutil.which("node")
    if not node or not (root / "studio/node_modules/typescript").exists():
        pytest.skip("requires Node and studio TypeScript/Preact dependencies")
    result = subprocess.run([node, str(root / "tests/studio_e_frontend.cjs")], cwd=root,
                            capture_output=True, text=True, encoding="utf8")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "24 scenarios passed" in result.stdout
