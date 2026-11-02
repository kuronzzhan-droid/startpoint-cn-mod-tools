"""Every Abyss/Rogue tool must import without invoking a CLI or local assets."""
from pathlib import Path
import subprocess
import sys


def test_all_abyss_and_rogue_tool_modules_import():
    # A fresh process catches missing module-level APIs even when another test
    # has already loaded a legacy alias or patched one of these modules.
    script = """
import importlib
import pkgutil

from wf.tools import abyss, rogue
from wf.tools.rogue import rogue_build

# These files are source sections, compiled into rogue_build's shared globals,
# rather than standalone modules. Importing rogue_build above executes all 14.
sections = {
    f"{rogue.__name__}.{name.removesuffix('.py')}"
    for name in rogue_build._SECTIONS
}
modules = {
    found.name
    for package in (abyss, rogue)
    for found in pkgutil.walk_packages(package.__path__, package.__name__ + '.')
}
errors = []
for name in sorted(modules - sections):
    try:
        importlib.import_module(name)
    except Exception as exc:
        errors.append(f'{name}: {type(exc).__name__}: {exc}')
assert modules - sections, 'No Abyss/Rogue tool modules were discovered'
assert not errors, '\\n'.join(errors)
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
