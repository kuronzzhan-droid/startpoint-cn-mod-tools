"""Compatibility entry point for ``wf.tools.rogue.standard_enemy_links``."""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main
    run_as_main("wf.tools.rogue.standard_enemy_links")
else:
    import importlib as _importlib
    _sys.modules[__name__] = _importlib.import_module("wf.tools.rogue.standard_enemy_links")
