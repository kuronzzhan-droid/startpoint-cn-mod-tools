"""Compatibility entry point for ``wf.tools.rogue.rogue_canary``."""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main
    run_as_main("wf.tools.rogue.rogue_canary")
else:
    import importlib as _importlib
    _sys.modules[__name__] = _importlib.import_module("wf.tools.rogue.rogue_canary")
