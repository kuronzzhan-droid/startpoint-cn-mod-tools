from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from unittest import mock


MOD_DIR = Path(__file__).resolve().parents[1]
GUI_PATH = MOD_DIR / "wf_gui.py"
HTML_PATH = MOD_DIR / "wf_gui.html"


class _MaterializeCardParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._div_depth = 0
        self._card_depth: int | None = None
        self.inputs: dict[str, dict[str, str | None]] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "div":
            self._div_depth += 1
            if attributes.get("data-tool") == "store_materialize":
                self._card_depth = self._div_depth
        if self._card_depth is not None and tag == "input":
            name = attributes.get("data-a")
            if name:
                self.inputs[name] = attributes

    def handle_endtag(self, tag: str) -> None:
        if tag != "div":
            return
        if self._card_depth == self._div_depth:
            self._card_depth = None
        self._div_depth -= 1


def _load_gui(target_store: Path):
    module_name = "_wf_gui_toolbox_materialize_test"
    spec = importlib.util.spec_from_file_location(module_name, GUI_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {GUI_PATH}")
    module = importlib.util.module_from_spec(spec)
    old_target = os.environ.get("WF_TARGET_STORE")
    os.environ["WF_TARGET_STORE"] = str(target_store)
    sys.path.insert(0, str(MOD_DIR))
    try:
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(module_name, None)
        sys.path.remove(str(MOD_DIR))
        if old_target is None:
            os.environ.pop("WF_TARGET_STORE", None)
        else:
            os.environ["WF_TARGET_STORE"] = old_target
    return module


class GuiToolboxMaterializeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._temp = tempfile.TemporaryDirectory()
        cls.target_store = Path(cls._temp.name) / "existing-store-for-import-only"
        cls.target_store.mkdir()
        cls.gui = _load_gui(cls.target_store)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temp.cleanup()

    def setUp(self) -> None:
        self.gui._TB.update(
            seq=0,
            tool="",
            title="",
            state="idle",
            log=[],
            rc=None,
            started=0.0,
            ended=0.0,
            cmd="",
        )
        self.gui._TB_PROC = None

    def _run_without_starting_process(self, args: dict[str, object]) -> dict:
        with (
            mock.patch.object(self.gui.subprocess, "Popen", return_value=object()),
            mock.patch.object(self.gui.threading, "Thread"),
        ):
            result = self.gui.toolbox_run("store_materialize", args)
        self.assertTrue(result["ok"])
        return result

    def test_materialize_card_exposes_only_the_safe_cli_contract(self) -> None:
        parser = _MaterializeCardParser()
        parser.feed(HTML_PATH.read_text(encoding="utf-8"))

        expected_args = {
            "dest",
            "official-only",
            "verify",
            "apply",
            "write-profile",
        }
        self.assertEqual(expected_args, set(parser.inputs))
        self.assertIn("required", parser.inputs["dest"])
        for flag in expected_args - {"dest"}:
            self.assertEqual("checkbox", parser.inputs[flag].get("type"))
            self.assertNotIn("checked", parser.inputs[flag])
        self.assertEqual(
            expected_args,
            set(self.gui.TOOLBOX_ARG_WHITELIST["store_materialize"]),
        )

    def test_materialize_preview_command_omits_write_flags_and_unknown_args(self) -> None:
        result = self._run_without_starting_process(
            {
                "dest": r"D:\wf-materialized-fresh",
                "official-only": True,
                "verify": True,
                "apply": False,
                "write-profile": False,
                "not-allowed": "escape",
            }
        )

        command = result["cmd"]
        self.assertIn("wf_store_materialize.py", command)
        self.assertIn(r"--dest D:\wf-materialized-fresh", command)
        self.assertIn("--official-only", command)
        self.assertIn("--verify", command)
        self.assertNotIn("--apply", command)
        self.assertNotIn("--write-profile", command)
        self.assertNotIn("not-allowed", command)
        self.assertNotIn("escape", command)

    def test_materialize_apply_command_forwards_explicit_write_flags(self) -> None:
        result = self._run_without_starting_process(
            {
                "dest": r"D:\wf-materialized-fresh",
                "apply": True,
                "write-profile": True,
            }
        )

        self.assertIn("--apply", result["cmd"])
        self.assertIn("--write-profile", result["cmd"])


if __name__ == "__main__":
    unittest.main()
