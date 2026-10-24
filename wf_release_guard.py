"""Compatibility entry point: this tool now lives in ``wf/tools/release/release_guard.py``.

``python wf_release_guard.py ...`` and ``import wf_release_guard`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.release.release_guard")
else:
    import importlib as _importlib

    _sys.modules[__name__] = _importlib.import_module("wf.tools.release.release_guard")
