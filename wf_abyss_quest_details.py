"""Compatibility entry point for ``wf.tools.rogue.abyss_quest_details``."""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main
    run_as_main("wf.tools.rogue.abyss_quest_details")
else:
    import importlib as _importlib
    _sys.modules[__name__] = _importlib.import_module("wf.tools.rogue.abyss_quest_details")
