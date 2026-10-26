"""Compatibility entry point: this tool now lives in ``wf/tools/assets/recover_pathlist.py``.

``python wf_recover_pathlist.py ...`` and ``import wf_recover_pathlist`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.assets.recover_pathlist")
else:
    import importlib as _importlib

    _sys.modules[__name__] = _importlib.import_module("wf.tools.assets.recover_pathlist")
