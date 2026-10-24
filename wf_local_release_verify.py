"""Compatibility entry point: this tool now lives in ``wf/tools/release/local_release_verify.py``.

``python wf_local_release_verify.py ...`` and ``import wf_local_release_verify`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.release.local_release_verify")
else:
    import importlib as _importlib

    _sys.modules[__name__] = _importlib.import_module("wf.tools.release.local_release_verify")
