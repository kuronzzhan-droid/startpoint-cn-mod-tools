"""Root ``wf_*.py`` files moved into ``wf/tools`` stay importable and runnable by their old paths."""
import importlib
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_TARGET = re.compile(r'run_as_main\("(wf\.tools\.[A-Za-z0-9_.]+)"\)')


def moved() -> dict[str, str]:
    """Old root module name -> new dotted module, read from each entry point."""
    found = {}
    for path in sorted(ROOT.glob("wf_*.py")):
        match = _TARGET.search(path.read_text(encoding="utf-8"))
        if match:
            found[path.stem] = match.group(1)
    return found


class RootEntryPointTests(unittest.TestCase):
    def test_entry_points_follow_naming_rule(self):
        self.assertTrue(moved())
        for old, new in moved().items():
            with self.subTest(old=old):
                self.assertEqual(new.rsplit(".", 1)[1], old.removeprefix("wf_"))
                self.assertTrue((ROOT / (new.replace(".", "/") + ".py")).is_file())

    def test_old_import_is_the_moved_module(self):
        for old, new in moved().items():
            with self.subTest(old=old):
                self.assertIs(importlib.import_module(old), importlib.import_module(new))

    def test_old_path_runs_from_another_directory(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "wf_weapon_gacha.py"), "--help"],
            cwd=ROOT / "tests", capture_output=True, text=True, encoding="utf-8", check=True)
        self.assertTrue(result.stdout.startswith("usage: wf_weapon_gacha.py"), result.stdout)


if __name__ == "__main__":
    unittest.main()
