"""Compatibility entry point: this tool now lives in ``wf/tools/release/local_server_status.py``.

``python wf_local_server_status.py ...`` and ``import wf_local_server_status`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.release.local_server_status")
else:
    import importlib as _importlib

    _sys.modules[__name__] = _importlib.import_module("wf.tools.release.local_server_status")
