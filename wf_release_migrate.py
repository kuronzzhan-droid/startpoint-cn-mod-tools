"""Compatibility entry point: this tool now lives in ``wf/tools/release/release_migrate.py``.

``python wf_release_migrate.py ...`` and ``import wf_release_migrate`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.release.release_migrate")
else:
    import importlib as _importlib

    _sys.modules[__name__] = _importlib.import_module("wf.tools.release.release_migrate")
