"""Compatibility entry point: this tool now lives in ``wf/tools/release/offline_release.py``.

``python wf_offline_release.py ...`` and ``import wf_offline_release`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.release.offline_release")
else:
    import importlib as _importlib

    _sys.modules[__name__] = _importlib.import_module("wf.tools.release.offline_release")
